"""Verified external PlayCricket archive fixtures for local integration tests."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "grdcc_partnership_source_snapshot_2026-11-10.json"
WEEKLY_MANIFEST_PATH = REPO_ROOT / "tests" / "fixtures" / "grdcc_weekly_output_snapshot_2026-11-16.json"
HISTORICAL_ENV = "SCOREBOOK_MATCH_CENTRE_ROOT"
CURRENT_ENV = "SCOREBOOK_GRDCC_CURRENT_MATCH_CENTRE_ROOT"
DATASETS = ("all_matches.csv", "all_ball_by_ball.csv", "all_scorecard_batting.csv", "all_match_innings.csv")


def source_manifest() -> dict[str, object]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def weekly_source_manifest() -> dict[str, object]:
    return json.loads(WEEKLY_MANIFEST_PATH.read_text(encoding="utf-8"))


def verify_current_privacy_snapshot() -> pd.DataFrame:
    receipt = source_manifest()["current_privacy_snapshot"]
    path = REPO_ROOT / str(receipt["path"])
    assert path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt["sha256"]
    snapshot = pd.read_csv(path, dtype=str).fillna("")
    assert len(snapshot) == receipt["rows"]
    assert snapshot.status.value_counts().to_dict() == {
        "public": receipt["public"],
        "private": receipt["private"],
    }
    return snapshot


def _archive_root(env_name: str, default: Path) -> Path:
    configured = os.environ.get(env_name, "").strip()
    root = Path(configured).expanduser() if configured else default
    if not all((root / filename).is_file() for filename in DATASETS):
        pytest.skip(f"verified local archive fixture is not mounted ({env_name})")
    return root


def _assert_pinned_files(root: Path, expected: dict[str, dict[str, object]]) -> None:
    for filename, receipt in expected.items():
        path = root / filename
        assert path.is_file(), f"pinned source file missing: {filename}"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == receipt["sha256"], (
            f"pinned source fingerprint changed: {filename}"
        )
        frame = pd.read_csv(path, low_memory=False)
        assert len(frame) == receipt["rows"], f"pinned source row count changed: {filename}"


def historical_source_root() -> Path:
    configured = os.environ.get(HISTORICAL_ENV, "").strip()
    root = Path(configured).expanduser() if configured else REPO_ROOT / "data" / "processed" / "match_centre"
    if not all(
        (root / "georges-river-district" / "all_available" / filename).is_file()
        and (root / "all_available" / filename).is_file()
        for filename in DATASETS
    ):
        pytest.skip(f"verified local archive fixture is not mounted ({HISTORICAL_ENV})")
    verify_current_privacy_snapshot()
    manifest = source_manifest()["historical_scope"]
    _assert_pinned_files(root / "georges-river-district" / "all_available", manifest["files"])
    # FVCC is included in the same authenticated archive and remains an isolation control.
    all_files = source_manifest().get("fvcc_scope", {})
    if all_files:
        _assert_pinned_files(root / "all_available", all_files.get("files", {}))
    return root


def cutoff_current_source_root(tmp_path: Path) -> Path:
    current = _archive_root(
        CURRENT_ENV,
        REPO_ROOT / "data" / "processed" / "match_centre" / "current_season_snapshots" / "grdcc-summer-2026-27-finalized",
    )
    manifest = source_manifest()["current_season_scope"]
    _assert_pinned_files(current, manifest["full_snapshot_files"])
    matches = pd.read_csv(current / "all_matches.csv", dtype=str, low_memory=False).fillna("")
    local_dates = pd.to_datetime(matches["first_match_day"], errors="coerce", utc=True).dt.tz_convert(
        "Australia/Sydney"
    ).dt.date
    cutoff = date.fromisoformat(str(manifest["cutoff_local_date"]))
    match_ids = set(matches.loc[local_dates.le(cutoff), "match_id"].astype(str))
    assert len(match_ids) == manifest["cutoff_filtered_source_rows"]["matches"]
    destination = tmp_path / "grdcc-current-through-2026-10-31"
    destination.mkdir(mode=0o700)
    for filename in DATASETS:
        frame = pd.read_csv(current / filename, dtype=str, low_memory=False).fillna("")
        filtered = frame.loc[frame["match_id"].astype(str).isin(match_ids)].copy()
        assert len(filtered) == manifest["cutoff_filtered_source_rows"][
            {
                "all_matches.csv": "matches",
                "all_ball_by_ball.csv": "ball_by_ball",
                "all_scorecard_batting.csv": "scorecard_batting",
                "all_match_innings.csv": "match_innings",
            }[filename]
        ]
        output = destination / filename
        filtered.to_csv(output, index=False)
        output.chmod(0o600)
    return destination
