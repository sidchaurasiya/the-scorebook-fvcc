"""Versioned public presentation assets for the four standard Scorebook routes."""
from __future__ import annotations

import hashlib
import io
import json
import os
from contextlib import contextmanager
from contextvars import ContextVar
from types import MappingProxyType
from dataclasses import dataclass, field
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import streamlit as st

from src.config.club_config import REPO_ROOT
from src.data.grdcc_profile_bundle import file_stamp, profile_generation
from src.data.hall_of_fame_prepared import _file_signature
from src.utils.profile_trace import event


def archive_path(club):
    return REPO_ROOT / "clubs" / club / "prepared_views" / "public_views.zip"


def generation(club):
    # The GRDCC inventory omits its own derived profile bundle. These views
    # can consume that bundle, so include it explicitly.
    from src.data.grdcc_profile_bundle import profile_bundle_path
    stamps = set(profile_generation(club))
    for path in (profile_bundle_path(club), REPO_ROOT / "requirements.txt",
                 REPO_ROOT / "scripts" / "build_public_customer_views.py",
                 REPO_ROOT / "scripts" / "prepare_profile_details.py",
                 REPO_ROOT / "scripts" / "grdcc_incremental_summaries.py"):
        if path.is_file():
            stamps.add(file_stamp(path))
    return tuple(sorted(stamps))


def content_digest(stamps):
    sources = [_file_signature(Path(stamp[0])) for stamp in stamps]
    return hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()


@dataclass(frozen=True)
class CustomerViews:
    club: str
    artifact: tuple
    source_digest: str
    archive: ZipFile = field(compare=False, repr=False)

    def cache_key(self):
        return self.club, self.source_digest, self.artifact

    def read(self, key):
        return json.loads(_member(self, key))


@st.cache_resource(show_spinner=False, max_entries=40, hash_funcs={CustomerViews: CustomerViews.cache_key})
def _member(view: CustomerViews, key: str):
    return view.archive.read(key)


@st.cache_resource(show_spinner=False, max_entries=6)
def _validate(club, stamps, artifact):
    # Pin immutable bytes. An atomic file replacement after validation must
    # never make a previously approved resource read another generation.
    event("view_validation_start")
    archive = ZipFile(io.BytesIO(Path(artifact[0]).read_bytes()))
    try:
        manifest = json.loads(archive.read("manifest"))
        digest = content_digest(stamps)
        if (manifest != {"club": club, "schema": 1, "source_digest": digest}
                or archive.testzip() is not None
                or generation(club) != stamps or file_stamp(Path(artifact[0])) != artifact):
            archive.close()
            return None
        event("view_validation_accepted")
        return CustomerViews(club, artifact, digest, archive)
    except Exception:
        archive.close()
        raise



def load_views(club):
    if (club not in {"fvcc", "glen-waverley-hawks", "georges-river-district"}
            or os.getenv("SCOREBOOK_IGNORE_PREPARED_HOF", "").strip() == "1"
            or os.getenv("FVCC_RUNTIME_IDENTITY_MAINTENANCE", "").strip() == "1"):
        return None
    try:
        artifact = file_stamp(archive_path(club))
        if artifact[-1] is None:
            return None
        event("view_inventory_start")
        stamps = generation(club)
        event("view_lookup_start", inputs=len(stamps))
        result = _validate(club, stamps, artifact)
        event("view_lookup_end", accepted=result is not None)
        return result
    except (OSError, ValueError, KeyError, BadZipFile):
        return None


_request_lookups = ContextVar("scorebook_request_lookups", default=None)


@contextmanager
def navigation_scope():
    token = _request_lookups.set({})
    try:
        yield
    finally:
        _request_lookups.reset(token)


@st.cache_resource(show_spinner=False, max_entries=6, hash_funcs={CustomerViews: CustomerViews.cache_key})
def _public_lookup(views):
    index = views.read("public/index")
    by_name = {}
    for record_id, name in index:
        key = name.strip().casefold()
        if key:
            by_name.setdefault(key,set()).add(record_id)
    return frozenset(i for i,_ in index), MappingProxyType({
        name:next(iter(ids)) for name,ids in by_name.items() if len(ids)==1})


def request_public_lookup(club):
    lookups = _request_lookups.get()
    if lookups is None:
        return None
    if club not in lookups:
        views = load_views(club)
        lookups[club] = _public_lookup(views) if views is not None else None
    return lookups[club]
