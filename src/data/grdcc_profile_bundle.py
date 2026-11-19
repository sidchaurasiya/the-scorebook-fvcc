"""Versioned, public-only snapshots of the governed GRDCC profile entry path."""
from __future__ import annotations

import hashlib
import json
import os
import time
from uuid import uuid4
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from types import MappingProxyType
from typing import Mapping

import streamlit as st

from src.config.club_config import REPO_ROOT, get_data_root, get_mapping_dir, get_processed_dir
from src.data.hall_of_fame_prepared import _file_signature

from src.utils.profile_trace import WORKER, event

CLUB = "georges-river-district"
BUNDLE_FILENAME = "prepared_profile_summaries.json"


def profile_bundle_path(club_id: str) -> Path:
    return get_processed_dir(club_id) / "player_profile" / BUNDLE_FILENAME


@dataclass(frozen=True)
class ProfileBundle:
    index: tuple[tuple[str, str], ...]
    summaries: Mapping[str, tuple[tuple[str, object], ...]]
    report_only: frozenset[str]


# A directory stamp changes on entry creation, rename or removal. File stamps
# are still read on every request, including for same-size privacy edits.
_inventory_lock = RLock()
_inventory_roots = ()
_inventory_dirs = ()
_inventory_paths = ()


def profile_inputs(club_id: str) -> tuple[Path, ...]:
    global _inventory_roots, _inventory_dirs, _inventory_paths
    root = get_data_root(club_id)
    processed = get_processed_dir(club_id)
    roots = (root / "source", processed, get_mapping_dir(club_id), REPO_ROOT / "src")
    fixed = (root / "metadata.json", REPO_ROOT / "clubs" / club_id / "club_config.yaml")
    excluded = profile_bundle_path(club_id)
    with _inventory_lock:
        if roots != _inventory_roots or any(
            file_stamp(path) != stamp for path, stamp in _inventory_dirs
        ):
            # Publish a plan only after a complete, stable scan.
            _inventory_roots = _inventory_dirs = _inventory_paths = ()
            paths = []
            directories = {}
            for top in roots:
                suffixes = {".py"} if top == roots[-1] else {".csv", ".json", ".xlsx", ".parquet"}
                pending = [top]
                while pending:
                    directory = pending.pop()
                    directories[directory] = file_stamp(directory)
                    if directories[directory][-1] is None:
                        if directory != top:
                            raise FileNotFoundError(directory)
                        continue
                    with os.scandir(directory) as entries:
                        for entry in entries:
                            if entry.is_dir(follow_symlinks=False):
                                pending.append(Path(entry.path))
                            elif os.path.splitext(entry.name)[1] in suffixes and entry.is_file():
                                path = Path(entry.path)
                                if path != excluded:
                                    paths.append(path)
            if any(file_stamp(path) != stamp for path, stamp in directories.items()):
                raise OSError("Profile directory changed during inventory")
            _inventory_paths = tuple(sorted(set(paths)))
            _inventory_dirs = tuple(directories.items())
            _inventory_roots = roots
        return tuple(sorted((*_inventory_paths, *(p for p in fixed if p.is_file()))))


def profile_generation(club_id: str) -> tuple[tuple[object, ...], ...]:
    global _inventory_roots, _inventory_dirs, _inventory_paths
    with _inventory_lock:
        try:
            event("inventory_start")
            paths = profile_inputs(club_id)
            event("inventory_listed", files=len(paths))
            stamps = tuple(file_stamp(p) for p in paths)
            if any(stamp[-1] is None for stamp in stamps) or any(
                file_stamp(directory) != stamp for directory, stamp in _inventory_dirs
            ):
                raise OSError("Profile inventory changed while reading file stamps")
            event("stamps_ready")
            return stamps
        except OSError:
            _inventory_roots = _inventory_dirs = _inventory_paths = ()
            raise


def governed_generation_key(club_id: str) -> str:
    try:
        generation = profile_generation(club_id)
    except OSError:
        # Governed readers must recompute if a reusable key cannot be verified.
        return uuid4().hex
    return hashlib.sha256(repr(generation).encode()).hexdigest()


def file_stamp(path: Path) -> tuple[object, ...]:
    try:
        info = path.stat()
    except FileNotFoundError:
        return (str(path), None)
    return (str(path), info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino)


def profile_content_signature(club_id: str) -> list[dict[str, object]]:
    """Portable manifest hashes, run once when the observed filesystem generation moves."""
    return [_file_signature(path) for path in profile_inputs(club_id)]


def load_grdcc_profile_bundle(club_id: str) -> ProfileBundle | None:
    if club_id != CLUB or os.getenv("SCOREBOOK_IGNORE_PREPARED_HOF", "").strip() == "1":
        return None
    path = profile_bundle_path(club_id)
    stamp = file_stamp(path)
    if stamp[-1] is None:
        event("rejected", reason="missing_artifact")
        return None
    try:
        generation = profile_generation(club_id)
    except OSError as exc:
        event("rejected", reason=type(exc).__name__)
        return None
    event("lookup_start", generation=hashlib.sha256(repr(generation).encode()).hexdigest()[:12])
    result = _build_grdcc_profile_bundle(club_id, generation, stamp)
    event("lookup_end", accepted=result is not None)
    return result


@st.cache_resource(show_spinner=False, max_entries=2)
def _build_grdcc_profile_bundle(
    club_id: str,
    generation: tuple[tuple[object, ...], ...],
    artifact: tuple[object, ...],
) -> ProfileBundle | None:
    if club_id != CLUB:
        return None
    try:
        started = time.perf_counter()
        event("validation_start")
        p = Path(str(artifact[0]))
        bundle = json.loads(p.read_text(encoding="utf-8"))
        if bundle["club"] != club_id or bundle["schema"] != 1:
            event("rejected", reason="schema_or_club")
            return None
        observed = profile_content_signature(club_id)
        if bundle["sources"] != observed:
            old = {x["path"]: x["sha256"] for x in bundle["sources"]}
            new = {x["path"]: x["sha256"] for x in observed}
            event("rejected", reason="source_manifest", differing_paths=[hashlib.sha256(k.encode()).hexdigest()[:12] for k in sorted(old.keys() | new.keys()) if old.get(k) != new.get(k)][:8])
            return None
        if generation != profile_generation(club_id) or artifact != file_stamp(p):
            event("rejected", reason="generation_changed")
            return None
        index = tuple((key, name) for key, name in bundle["index"])
        report_only = frozenset(bundle["reportOnly"])
        summaries = {
            key: tuple(row.items())
            for key, row in bundle["summaries"].items()
        }
        keys = {key for key, _ in index}
        if len(keys) != len(index) or not summaries.keys() <= keys or not report_only <= keys:
            event("rejected", reason="invalid_keys")
            return None
        print("GRDCC_SNAPSHOT_VALIDATED " + json.dumps({
            "worker": WORKER, "epoch": time.time(), "duration_s": time.perf_counter()-started,
            "sources": len(observed), "profiles": len(index),
        }), flush=True)
        event("validated")
        return ProfileBundle(index, MappingProxyType(summaries), report_only)
    except (KeyError, OSError, TypeError, ValueError, AttributeError) as exc:
        event("rejected", reason=type(exc).__name__)
        return None
