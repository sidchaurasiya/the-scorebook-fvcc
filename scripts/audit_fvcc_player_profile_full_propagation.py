#!/usr/bin/env python3
"""Audit FVCC Player Profile data propagation for the latest Winter 2026 refresh."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

os.environ.setdefault("CLUB_ID", "fvcc")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ui.layout import (  # noqa: E402
    build_player_profile_view,
    build_player_recent_form,
    get_player_peer_comparison,
    load_player_profile_index,
    metadata_mtime,
    player_aliases_mtime,
    player_peer_grade_scope,
    player_profile_view_signature,
)
from src.utils.player_identity import get_player_profile_data  # noqa: E402


OUTPUT_PATH = Path(
    "clubs/fvcc/data/processed/validation/fvcc_player_profile_full_propagation_audit.csv"
)
TARGET_PLAYER = "Siddhanth Chaurasiya"
TARGET_SEASON = "Winter 2026"


def _find_player_id(index: pd.DataFrame, player_name: str) -> str:
    if index.empty or not {"id", "name"}.issubset(index.columns):
        raise RuntimeError("Player Profile index is missing expected id/name columns")
    rows = index[index["name"].astype(str).str.casefold().eq(player_name.casefold())]
    if rows.empty:
        rows = index[index["name"].astype(str).str.contains(player_name, case=False, na=False)]
    if rows.empty:
        raise RuntimeError(f"Could not find {player_name} in FVCC Player Profile index")
    return str(rows.iloc[0]["id"])


def audit_rows() -> list[dict[str, object]]:
    club_id = "fvcc"
    local_version = metadata_mtime()
    identity_version = player_aliases_mtime()
    index = load_player_profile_index(club_id, local_version, identity_version, "2026-07-profile-index-v2")
    player_id = _find_player_id(index, TARGET_PLAYER)
    profile = get_player_profile_data(player_id, local_version, identity_version, club_id=club_id)
    view = build_player_profile_view(profile, player_profile_view_signature())

    season_table = view.get("season_table", pd.DataFrame()).copy()
    career = view.get("career", pd.DataFrame()).iloc[0]
    season_row = season_table[season_table["Season"].astype(str).eq(TARGET_SEASON)]
    recent = build_player_recent_form(career)
    seasons = tuple(sorted(season_table["Season"].dropna().astype(str).unique()))
    peers = get_player_peer_comparison(
        str(career.get("canonical_player_id", "")),
        seasons,
        player_peer_grade_scope(view),
        local_version,
        identity_version,
        club_id,
    )

    winter_matches = pd.to_numeric(season_row.get("Matches", pd.Series(dtype=float)), errors="coerce")
    winter_wickets = pd.to_numeric(season_row.get("Wickets", pd.Series(dtype=float)), errors="coerce")
    grade_rows = view.get("grade_table", pd.DataFrame()).copy()
    winter_grade = grade_rows[grade_rows.get("Grade", pd.Series(dtype=str)).astype(str).str.contains("Winter", case=False, na=False)]

    rows: list[dict[str, object]] = [
        {
            "layer": "player_profile_index",
            "status": "present",
            "value": player_id,
            "notes": TARGET_PLAYER,
        },
        {
            "layer": "career_summary",
            "status": "present",
            "value": f"Matches={career.get('Matches')} Wickets={career.get('Wickets')}",
            "notes": "App-facing career row",
        },
        {
            "layer": "career_breakdown_season",
            "status": "present" if not season_row.empty else "missing",
            "value": (
                f"Matches={float(winter_matches.iloc[0]) if len(winter_matches) else 'NA'} "
                f"Wickets={float(winter_wickets.iloc[0]) if len(winter_wickets) else 'NA'}"
            ),
            "notes": TARGET_SEASON,
        },
        {
            "layer": "recent_form_bowling",
            "status": "present" if recent.get("bowling") else "missing",
            "value": " | ".join(str(item.get("label")) for item in recent.get("bowling", [])[:5]),
            "notes": "Latest bowling chip should include latest match",
        },
        {
            "layer": "recent_form_batting",
            "status": "present" if recent.get("batting") else "missing",
            "value": " | ".join(str(item.get("label")) for item in recent.get("batting", [])[:5]),
            "notes": "Latest batting chips from app-facing source",
        },
        {
            "layer": "competition_grade",
            "status": "present" if not winter_grade.empty else "missing",
            "value": winter_grade.to_dict("records")[:2],
            "notes": "Grade table rows containing Winter",
        },
        {
            "layer": "player_dna_batting_position",
            "status": "present" if not view.get("batting_position", pd.DataFrame()).empty else "missing",
            "value": len(view.get("batting_position", pd.DataFrame())),
            "notes": "App-facing batting-position source rows",
        },
        {
            "layer": "player_dna_bowling_phase",
            "status": "present" if not view.get("bowling_phase", pd.DataFrame()).empty else "missing",
            "value": len(view.get("bowling_phase", pd.DataFrame())),
            "notes": "App-facing bowling-phase source rows",
        },
        {
            "layer": "player_dna_dismissal_fingerprint",
            "status": "present" if not view.get("dismissal_fingerprint", pd.DataFrame()).empty else "missing",
            "value": len(view.get("dismissal_fingerprint", pd.DataFrame())),
            "notes": "App-facing dismissal fingerprint rows",
        },
        {
            "layer": "player_vs_peers",
            "status": "present" if peers.get("batting") or peers.get("bowling") else "missing",
            "value": f"batting={len(peers.get('batting', []))} bowling={len(peers.get('bowling', []))}",
            "notes": "Peer comparison computed from updated seasons/grades",
        },
        {
            "layer": "season_trends",
            "status": "present" if not season_table.empty else "missing",
            "value": f"rows={len(season_table)}",
            "notes": "Season Trends uses Player Profile season table",
        },
    ]
    return rows


def main() -> int:
    rows = audit_rows()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    for row in rows:
        print(f"{row['layer']}: {row['status']} {row['value']}")
    print(f"wrote {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
