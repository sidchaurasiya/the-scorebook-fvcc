#!/usr/bin/env python3
"""Validate FVCC refreshed match data reaches app-facing player surfaces."""

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
    add,
    clean,
    int_number,
    player_mask,
    player_row,
    round_five_row,
    validate_player_totals,
    winter_rows,
)
from src.data.playcricket_ingestion import metadata_mtime, read_processed_table  # noqa: E402
from src.ui.layout import (  # noqa: E402
    build_player_profile_view,
    build_player_recent_form,
    get_player_peer_comparison,
    load_local_category_frame,
    player_peer_grade_scope,
    player_profile_view_signature,
)
from src.utils.player_identity import get_player_profile_data, player_aliases_mtime  # noqa: E402

OUTPUT_PATH = PROCESSED / "validation" / "fvcc_app_wide_refresh_propagation_validation.csv"


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def profile_for_player(app_bowling: pd.DataFrame, player_name: str) -> tuple[dict[str, object] | None, dict[str, pd.DataFrame]]:
    row = player_row(app_bowling, player_name)
    if row is None:
        return None, {}
    profile = get_player_profile_data(
        row.get("canonical_player_id"),
        metadata_mtime(),
        player_aliases_mtime(),
        club_id="fvcc",
    )
    if profile is None:
        return None, {}
    return profile, build_player_profile_view(profile, player_profile_view_signature())


def season_table_row(profile_view: dict[str, pd.DataFrame]) -> pd.Series | None:
    table = profile_view.get("season_table", pd.DataFrame())
    if table.empty or "Season" not in table:
        return None
    scoped = table[table["Season"].astype(str).eq("Winter 2026")]
    return scoped.iloc[0] if not scoped.empty else None


def main() -> int:
    rows: list[dict[str, Any]] = []
    r5 = round_five_row()
    add(rows, "latest_winter_2026_match_in_season_by_round", r5 is not None, "season_by_round_scorecards.csv")
    if r5 is None:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
        print("validation_status=fail checks=1 failed=1")
        return 1

    match_id = clean(r5.get("match_id"))
    season_id = clean(r5.get("season_id"))
    team_id = clean(r5.get("fvcc_team_id") or r5.get("club_team_id"))
    match_date = pd.to_datetime(r5.get("match_date"), errors="coerce", utc=True)

    add(rows, "latest_match_id_present", bool(match_id), match_id)
    add(rows, "latest_match_after_2026_06_20", pd.notna(match_date) and match_date.date() > pd.Timestamp("2026-06-20", tz="UTC").date(), str(match_date))

    aggregate_bowling = winter_rows(read_processed_table("all_seasons_bowling"))
    validate_player_totals(rows, "player_season_aggregate_bowling", aggregate_bowling, "matches", "bowlingWickets")

    app_bowling = load_local_category_frame(
        "fvcc",
        "bowling",
        season_id,
        team_id,
        metadata_mtime(),
        player_aliases_mtime(),
    )
    validate_player_totals(rows, "season_overview_detailed_bowling", app_bowling, "matches", "bowlingWickets")

    recent_bowling = read_csv(PROCESSED / "player_profile" / "recent_form_bowling.csv")
    performance = read_csv(PROCESSED / "player_profile" / "performance_breakdown_by_dimension.csv")
    add(rows, "latest_match_in_recent_form_source", not recent_bowling.empty and "match_id" in recent_bowling and recent_bowling["match_id"].astype(str).eq(match_id).any(), match_id)
    add(rows, "latest_match_in_player_profile_source", not performance.empty and player_mask(performance, "Siddhanth Chaurasiya").any(), "performance_breakdown_by_dimension.csv")

    siddhanth_view: dict[str, pd.DataFrame] = {}
    siddhanth_career = pd.DataFrame()
    for player_name, expected in EXPECTED.items():
        profile, view = profile_for_player(app_bowling, player_name)
        add(rows, f"profile_{player_name}_available", profile is not None, "get_player_profile_data")
        if profile is None:
            continue
        if player_name == "Siddhanth Chaurasiya":
            siddhanth_view = view
        row = season_table_row(view)
        add(rows, f"profile_career_breakdown_{player_name}_winter_row", row is not None, "season_table")
        if row is not None:
            matches = int_number(row.get("Matches"))
            wickets = int_number(row.get("Wickets"))
            add(rows, f"profile_career_breakdown_{player_name}_matches", matches == expected["matches"], f"Mat={matches}; expected={expected['matches']}")
            add(rows, f"profile_career_breakdown_{player_name}_wickets", wickets == expected["bowlingWickets"], f"W={wickets}; expected={expected['bowlingWickets']}")
            app_row = player_row(app_bowling, player_name)
            if app_row is not None:
                add(rows, f"season_profile_match_parity_{player_name}", matches == int_number(app_row.get("matches")), f"profile={matches}; season_overview={int_number(app_row.get('matches'))}")
                add(rows, f"season_profile_wicket_parity_{player_name}", wickets == int_number(app_row.get("bowlingWickets")), f"profile={wickets}; season_overview={int_number(app_row.get('bowlingWickets'))}")
        career = view.get("career", pd.DataFrame())
        if player_name == "Siddhanth Chaurasiya":
            siddhanth_career = career
        recent = build_player_recent_form(career.iloc[0]) if not career.empty else {"bowling": []}
        recent_labels = [str(item.get("label", "")) for item in recent.get("bowling", [])]
        source_latest = recent_bowling[player_mask(recent_bowling, player_name)].head(1) if not recent_bowling.empty else pd.DataFrame()
        expected_label = clean(source_latest.iloc[0].get("display_value")) if not source_latest.empty else ""
        add(rows, f"recent_form_{player_name}_latest_match_present", bool(expected_label) and expected_label in recent_labels, f"expected_latest={expected_label}; rendered={recent_labels[:3]}")

    stale_siddhanth = False
    sid_row = season_table_row(siddhanth_view) if siddhanth_view else None
    if sid_row is not None:
        stale_siddhanth = int_number(sid_row.get("Matches")) < EXPECTED["Siddhanth Chaurasiya"]["matches"] or int_number(sid_row.get("Wickets")) < EXPECTED["Siddhanth Chaurasiya"]["bowlingWickets"]
    add(rows, "no_stale_siddhanth_pre_latest_profile_row", not stale_siddhanth, "Siddhanth Winter 2026")

    if siddhanth_view:
        add(rows, "player_dna_batting_position_current", not siddhanth_view.get("batting_position", pd.DataFrame()).empty, "Player DNA batting-position source")
        add(rows, "player_dna_bowling_phase_current", not siddhanth_view.get("bowling_phase", pd.DataFrame()).empty, "Player DNA bowling-phase source")
        add(rows, "player_dna_dismissal_fingerprint_current", not siddhanth_view.get("dismissal_fingerprint", pd.DataFrame()).empty, "Player DNA dismissal source")
    if not siddhanth_career.empty and siddhanth_view:
        seasons = tuple(sorted(siddhanth_view.get("season_table", pd.DataFrame()).get("Season", pd.Series(dtype="object")).dropna().astype(str).unique()))
        peers = get_player_peer_comparison(
            str(siddhanth_career.iloc[0].get("canonical_player_id", "")),
            seasons,
            player_peer_grade_scope(siddhanth_view),
            metadata_mtime(),
            player_aliases_mtime(),
            "fvcc",
        )
        add(rows, "player_vs_peers_current", bool(peers.get("batting")) and bool(peers.get("bowling")), f"batting={len(peers.get('batting', []))}; bowling={len(peers.get('bowling', []))}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    failures = [row for row in rows if row["validation_status"] != "pass"]
    status = "pass" if not failures else "fail"
    print(f"validation_status={status} checks={len(rows)} failed={len(failures)}")
    if sid_row is not None:
        print(f"Siddhanth Chaurasiya: Mat={int_number(sid_row.get('Matches'))} W={int_number(sid_row.get('Wickets'))}")
    if failures:
        print("failed_checks=" + ",".join(row["check_name"] for row in failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
