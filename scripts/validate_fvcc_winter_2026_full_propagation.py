#!/usr/bin/env python3
"""Validate FVCC Winter 2026 latest-match propagation into app-facing data."""

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

from src.data.playcricket_ingestion import metadata_mtime, read_processed_table  # noqa: E402
from src.ui.layout import (  # noqa: E402
    build_player_profile_view,
    load_hall_of_fame_data,
    load_local_category_frame,
    player_profile_view_signature,
)
from src.utils.player_identity import get_player_profile_data, player_aliases_mtime  # noqa: E402

PROCESSED = ROOT / "clubs" / "fvcc" / "data" / "processed"
OUTPUT_PATH = PROCESSED / "validation" / "fvcc_winter_2026_full_propagation_validation.csv"

EXPECTED = {
    "Siddhanth Chaurasiya": {"matches": 7, "bowlingWickets": 11},
    "Kartik Nallepalli": {"matches": 7, "bowlingWickets": 7},
}


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def number(value: object) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    return float(parsed) if pd.notna(parsed) else 0.0


def int_number(value: object) -> int:
    return int(round(number(value)))


def add(rows: list[dict[str, Any]], check_name: str, passed: bool, details: str) -> None:
    rows.append(
        {
            "check_name": check_name,
            "validation_status": "pass" if passed else "fail",
            "details": details,
        }
    )


def player_mask(frame: pd.DataFrame, player_name: str) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    for column in ["canonical_player_name", "display_player_name", "player_name", "Player"]:
        if column in frame:
            mask = mask | frame[column].astype(str).str.casefold().eq(player_name.casefold())
    return mask


def player_row(frame: pd.DataFrame, player_name: str) -> pd.Series | None:
    if frame.empty:
        return None
    scoped = frame[player_mask(frame, player_name)]
    return scoped.iloc[0] if not scoped.empty else None


def winter_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "season" not in frame:
        return frame.head(0)
    return frame[frame["season"].astype(str).eq("Winter 2026")].copy()


def round_five_row() -> pd.Series | None:
    rounds = read_csv(PROCESSED / "season_overview" / "season_by_round_scorecards.csv")
    if rounds.empty:
        return None
    winter = winter_rows(rounds)
    if winter.empty:
        return None
    winter["match_date_sort"] = pd.to_datetime(winter.get("match_date"), errors="coerce", utc=True)
    after_round_four = winter[winter["match_date_sort"] > pd.Timestamp("2026-06-20", tz="UTC")]
    return after_round_four.sort_values("match_date_sort", ascending=False).iloc[0] if not after_round_four.empty else None


def validate_player_totals(
    rows: list[dict[str, Any]],
    source_name: str,
    frame: pd.DataFrame,
    match_column: str,
    wicket_column: str,
) -> None:
    for player_name, expected in EXPECTED.items():
        row = player_row(frame, player_name)
        add(rows, f"{source_name}_{player_name}_row_present", row is not None, source_name)
        if row is None:
            continue
        matches = int_number(row.get(match_column))
        wickets = int_number(row.get(wicket_column))
        add(
            rows,
            f"{source_name}_{player_name}_matches",
            matches == expected["matches"],
            f"Mat={matches}; expected={expected['matches']}",
        )
        add(
            rows,
            f"{source_name}_{player_name}_wickets",
            wickets == expected["bowlingWickets"],
            f"W={wickets}; expected={expected['bowlingWickets']}",
        )


def validate_recent_form(rows: list[dict[str, Any]], match_id: str) -> None:
    for filename in ["recent_form_batting.csv", "recent_form_bowling.csv"]:
        frame = read_csv(PROCESSED / "player_profile" / filename)
        has_round = not frame.empty and "match_id" in frame and frame["match_id"].astype(str).eq(match_id).any()
        add(rows, f"latest_match_in_player_profile_{filename}", has_round, f"{len(frame)} rows; match_id={match_id}")
        if filename == "recent_form_bowling.csv":
            for player_name in EXPECTED:
                player_has_round = (
                    has_round
                    and player_mask(frame, player_name).any()
                    and frame.loc[player_mask(frame, player_name), "match_id"].astype(str).eq(match_id).any()
                )
                add(rows, f"latest_match_{player_name}_in_{filename}", player_has_round, player_name)
        else:
            player_name = "Siddhanth Chaurasiya"
            player_has_round = (
                has_round
                and player_mask(frame, player_name).any()
                and frame.loc[player_mask(frame, player_name), "match_id"].astype(str).eq(match_id).any()
            )
            add(rows, f"latest_match_{player_name}_in_{filename}", player_has_round, player_name)


def validate_player_profile(rows: list[dict[str, Any]], app_bowling: pd.DataFrame) -> None:
    for player_name, expected in EXPECTED.items():
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
        add(rows, f"profile_source_{player_name}_available", profile is not None, "get_player_profile_data")
        if profile is None:
            continue
        view = build_player_profile_view(profile, player_profile_view_signature())
        season_table = view.get("season_table", pd.DataFrame())
        row = (
            season_table[season_table["Season"].astype(str).eq("Winter 2026")].iloc[0]
            if not season_table.empty and "Season" in season_table and season_table["Season"].astype(str).eq("Winter 2026").any()
            else None
        )
        add(rows, f"profile_career_breakdown_{player_name}_winter_row", row is not None, "Player Profile season_table")
        if row is None:
            continue
        matches = int_number(row.get("Matches"))
        wickets = int_number(row.get("Wickets"))
        add(
            rows,
            f"profile_career_breakdown_{player_name}_matches",
            matches == expected["matches"],
            f"Mat={matches}; expected={expected['matches']}",
        )
        add(
            rows,
            f"profile_career_breakdown_{player_name}_wickets",
            wickets == expected["bowlingWickets"],
            f"W={wickets}; expected={expected['bowlingWickets']}",
        )


def main() -> int:
    rows: list[dict[str, Any]] = []
    r5 = round_five_row()
    add(rows, "winter_2026_latest_match_in_season_by_round", r5 is not None, "season_by_round_scorecards.csv")
    if r5 is None:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
        print(f"validation_status=fail checks={len(rows)} failed=1")
        return 1

    match_id = clean(r5.get("match_id"))
    match_date = pd.to_datetime(r5.get("match_date"), errors="coerce", utc=True)
    opponent = clean(r5.get("opponent") or r5.get("opponent_name"))
    result = clean(r5.get("result_text") or r5.get("result"))
    season_id = clean(r5.get("season_id"))
    team_id = clean(r5.get("fvcc_team_id") or r5.get("club_team_id"))

    add(rows, "latest_match_id_present", bool(match_id), match_id)
    add(rows, "latest_match_date_after_previous_refresh", pd.notna(match_date) and match_date.date() > pd.Timestamp("2026-06-20", tz="UTC").date(), str(match_date))
    add(rows, "latest_match_opponent_present", bool(opponent), opponent)
    add(rows, "latest_match_result_present", bool(result), result)

    bowling = winter_rows(read_processed_table("all_seasons_bowling"))
    batting = winter_rows(read_processed_table("all_seasons_batting"))
    fielding = winter_rows(read_processed_table("all_seasons_fielding"))
    add(rows, "winter_bowling_aggregate_rows", not bowling.empty, f"{len(bowling)} rows")
    add(rows, "winter_batting_aggregate_rows", not batting.empty, f"{len(batting)} rows")
    add(rows, "winter_fielding_aggregate_rows", not fielding.empty, f"{len(fielding)} rows")
    validate_player_totals(rows, "aggregate_bowling", bowling, "matches", "bowlingWickets")

    app_bowling = load_local_category_frame(
        "fvcc",
        "bowling",
        season_id,
        team_id,
        metadata_mtime(),
        player_aliases_mtime(),
    )
    validate_player_totals(rows, "season_overview_detailed_stats", app_bowling, "matches", "bowlingWickets")
    stale = [
        player_name
        for player_name in EXPECTED
        if (row := player_row(app_bowling, player_name)) is not None and int_number(row.get("matches")) == 5
    ]
    add(rows, "no_stale_pre_latest_match_siddhanth_or_kartik_rows", not stale, ", ".join(stale) or "none")

    validate_recent_form(rows, match_id)
    validate_player_profile(rows, app_bowling)

    scorecard_links = read_csv(PROCESSED / "hall_of_fame" / "scorecard_record_links.csv")
    add(
        rows,
        "latest_match_in_hof_scorecard_links",
        not scorecard_links.empty and "match_id" in scorecard_links and scorecard_links["match_id"].astype(str).eq(match_id).any(),
        f"{len(scorecard_links)} rows",
    )
    hof_data = load_hall_of_fame_data(metadata_mtime(), player_aliases_mtime(), club_id="fvcc")
    all_time = hof_data.get("all_time", pd.DataFrame()) if isinstance(hof_data, dict) else pd.DataFrame()
    add(rows, "hof_all_time_available", not all_time.empty, f"{len(all_time)} rows")
    for player_name in EXPECTED:
        row = player_row(all_time, player_name)
        add(rows, f"hof_all_time_{player_name}_present", row is not None, "all_time")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    failures = [row for row in rows if row["validation_status"] != "pass"]
    status = "pass" if not failures else "fail"
    print(f"validation_status={status} checks={len(rows)} failed={len(failures)}")
    print(
        "latest_match="
        f"date={match_date.date() if pd.notna(match_date) else 'missing'} "
        f"match_id={match_id} opponent={opponent} result={result}"
    )
    for player_name in EXPECTED:
        row = player_row(app_bowling, player_name)
        if row is not None:
            print(f"{player_name}: Mat={int_number(row.get('matches'))} W={int_number(row.get('bowlingWickets'))}")
    if failures:
        print("failed_checks=" + ",".join(row["check_name"] for row in failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
