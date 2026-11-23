"""Compile the public GRDCC profile entry snapshot from the approved dataset."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["CLUB_ID"] = "georges-river-district"

from src.data.grdcc_profile_bundle import CLUB, profile_bundle_path, profile_content_signature, profile_generation
from src.ui import layout
from src.utils.player_identity import load_portability_player_profile_source_frames, prepare_grdcc_profile_sources

CARD_FIELDS = (
    "Player", "Runs", "Matches", "Wickets", "Catches", "Innings", "Matches Source", "Matches Proxy",
    "matches_source", "Season", "season", "Latest Season", "latest_season", "Proxy Season", "Maidens",
    "Dismissals", "Overs", "Career Span", layout.SOURCE_NOTE, layout.RECORD_KIND, layout.REVIEW_FLAG,
    "Reviewed Career Metric", "Reviewed Career Source URL",
)


def compact(row, *, report_only=False):
    values = {}
    for key in CARD_FIELDS:
        if key not in row:
            continue
        value = row[key]
        values[key] = None if pd.isna(value) else value.item() if hasattr(value, "item") else value
    if layout.grdcc_primary_card_markup(row, report_only=report_only) != layout.grdcc_primary_card_markup(
        pd.Series(values), report_only=report_only,
    ):
        raise ValueError("A required public field is missing from the profile projection")
    return values


def build():
    from scripts.public_release_boundary import GRDCC, require_artifact_destination

    require_artifact_destination(GRDCC)
    start = profile_generation(CLUB)
    metadata, aliases = layout.metadata_mtime(), layout.player_aliases_mtime(club_id=CLUB)
    index = layout.load_player_profile_index(CLUB, metadata, aliases)
    source_pool = prepare_grdcc_profile_sources(load_portability_player_profile_source_frames(CLUB, metadata, aliases))
    authority = layout.load_grdcc_profile_authority()
    reports = set(layout.report_profile_index(CLUB).id)
    rows = [(str(x.id), str(x.name)) for x in index.itertuples(index=False)]
    summaries = {}
    print(f"Compiling {len(rows)} governed public profiles", flush=True)
    for i, (key, _name) in enumerate(rows, 1):
        if key in reports:
            career = authority.loc[authority["report_record_id"].eq(key)]
            if len(career) != 1:
                raise ValueError("Expected one approved annual-report record")
        else:
            career = layout.build_player_profile_primary(source_pool.profile(key), authority=authority)
        if not career.empty:
            summaries[key] = compact(career.iloc[0], report_only=key in reports)
        if i % 250 == 0:
            print(f"Compiled {i} public profiles", flush=True)
    signature = profile_content_signature(CLUB)
    if start != profile_generation(CLUB):
        raise RuntimeError("Profile inputs changed during preparation. Retry against a stable generation.")
    path = profile_bundle_path(CLUB)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({
        "club": CLUB, "schema": 1, "sources": signature, "index": rows,
        "summaries": summaries, "reportOnly": sorted(reports & {key for key, _ in rows}),
    }, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")
    tmp.replace(path)
    print(f"Validated and wrote {len(summaries)} compact summaries", flush=True)


if __name__ == "__main__":
    build()
