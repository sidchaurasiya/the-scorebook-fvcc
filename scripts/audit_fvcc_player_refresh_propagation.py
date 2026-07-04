#!/usr/bin/env python3
"""Audit FVCC player refresh propagation across app-facing layers."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["CLUB_ID"] = "fvcc"

from scripts.validate_fvcc_winter_2026_full_propagation import (  # noqa: E402
    EXPECTED,
    PROCESSED,
    clean,
    int_number,
    player_mask,
    player_row,
    round_five_row,
    winter_rows,
)
from src.data.playcricket_ingestion import metadata_mtime, read_processed_table  # noqa: E402
from src.ui.layout import (  # noqa: E402
    build_player_profile_view,
    build_player_recent_form,
    load_local_category_frame,
    player_profile_view_signature,
)
from src.utils.player_identity import get_player_profile_data, player_aliases_mtime  # noqa: E402

OUTPUT_PATH = PROCESSED / "validation" / "fvcc_player_refresh_propagation_audit.csv"


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def metric_row(layer: str, player_name: str, row: pd.Series | None, match_id: str = "") -> dict[str, Any]:
    return {
        "layer": layer,
        "player_name": player_name,
        "match_id": match_id,
        "season": clean(row.get("Season") if row is not None else "Winter 2026") or "Winter 2026",
        "matches": int_number(row.get("Matches") if row is not None and "Matches" in row else row.get("matches") if row is not None else 0),
        "wickets": int_number(row.get("Wickets") if row is not None and "Wickets" in row else row.get("bowlingWickets") if row is not None else 0),
        "recent_form_latest": "",
        "notes": "present" if row is not None else "missing",
    }


def main() -> int:
    rows: list[dict[str, Any]] = []
    r5 = round_five_row()
    match_id = clean(r5.get("match_id")) if r5 is not None else ""
    match_date = clean(r5.get("match_date")) if r5 is not None else ""
    result = clean(r5.get("result_text") or r5.get("result")) if r5 is not None else ""
    opponent = clean(r5.get("opponent_name") or r5.get("opponent")) if r5 is not None else ""
    season_id = clean(r5.get("season_id")) if r5 is not None else ""
    team_id = clean(r5.get("fvcc_team_id") or r5.get("club_team_id")) if r5 is not None else ""

    rows.append(
        {
            "layer": "season_by_round",
            "player_name": "",
            "match_id": match_id,
            "season": "Winter 2026",
            "matches": "",
            "wickets": "",
            "recent_form_latest": "",
            "notes": f"date={match_date}; opponent={opponent}; result={result}",
        }
    )

    aggregate_bowling = winter_rows(read_processed_table("all_seasons_bowling"))
    app_bowling = load_local_category_frame(
        "fvcc",
        "bowling",
        season_id,
        team_id,
        metadata_mtime(),
        player_aliases_mtime(),
    )
    recent_bowling = read_csv(PROCESSED / "player_profile" / "recent_form_bowling.csv")

    for player_name in EXPECTED:
        rows.append(metric_row("player_season_aggregate_bowling", player_name, player_row(aggregate_bowling, player_name), match_id))
        rows.append(metric_row("season_overview_detailed_bowling", player_name, player_row(app_bowling, player_name), match_id))
        app_row = player_row(app_bowling, player_name)
        profile = (
            get_player_profile_data(
                app_row.get("canonical_player_id"),
                metadata_mtime(),
                player_aliases_mtime(),
                club_id="fvcc",
            )
            if app_row is not None
            else None
        )
        view = build_player_profile_view(profile, player_profile_view_signature()) if profile is not None else {}
        season_table = view.get("season_table", pd.DataFrame())
        profile_row = (
            season_table[season_table["Season"].astype(str).eq("Winter 2026")].iloc[0]
            if not season_table.empty and "Season" in season_table and season_table["Season"].astype(str).eq("Winter 2026").any()
            else None
        )
        rows.append(metric_row("player_profile_career_breakdown", player_name, profile_row, match_id))
        career = view.get("career", pd.DataFrame())
        recent = build_player_recent_form(career.iloc[0]) if not career.empty else {"bowling": []}
        recent_labels = [str(item.get("label", "")) for item in recent.get("bowling", [])]
        source_recent = recent_bowling[player_mask(recent_bowling, player_name)].head(1) if not recent_bowling.empty else pd.DataFrame()
        latest_label = clean(source_recent.iloc[0].get("display_value")) if not source_recent.empty else ""
        rows.append(
            {
                "layer": "player_profile_recent_form_bowling",
                "player_name": player_name,
                "match_id": clean(source_recent.iloc[0].get("match_id")) if not source_recent.empty else "",
                "season": "Winter 2026",
                "matches": "",
                "wickets": "",
                "recent_form_latest": latest_label,
                "notes": f"rendered_top3={recent_labels[:3]}",
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    print(f"audit_rows={len(rows)} output={OUTPUT_PATH}")
    for row in rows:
        if row["player_name"]:
            print(f"{row['layer']} {row['player_name']}: Mat={row['matches']} W={row['wickets']} recent={row['recent_form_latest']}")
        else:
            print(f"{row['layer']}: {row['notes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
