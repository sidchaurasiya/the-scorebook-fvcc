#!/usr/bin/env python3
"""Build deploy-safe Hall of Fame match-centre summaries.

This reads local processed match-centre scopes and writes compact tracked CSVs
under data/processed/hall_of_fame/. It does not fetch data and does not make the
production app depend on ignored match-centre folders at runtime.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_player_profile_insight_exports as profile_exports  # noqa: E402
from scripts import build_season_overview_detail_exports as season_exports  # noqa: E402
from src.data.match_centre_milestones import build_batting_milestones  # noqa: E402
from src.ui import layout  # noqa: E402


OUTPUT_DIR = ROOT / "data" / "processed" / "hall_of_fame"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = profile_exports.load_player_profile_scopes()
    if frames["matches"].empty:
        print("No match-centre processed scopes found. No Hall of Fame detail exports built.")
        return 1

    batting = profile_exports.prepare_batting(frames)
    bowling = profile_exports.prepare_bowling(frames)
    fielding = profile_exports.prepare_fielding(frames)
    balls = profile_exports.prepare_ball_rows(frames)

    outputs = {
        "player_win_rates.csv": build_player_win_rates(frames["matches"], batting, bowling, fielding),
        "player_bbb_batting_rates.csv": build_player_bbb_batting_rates(batting, balls),
        "player_scorecard_milestones.csv": build_player_scorecard_milestones(batting),
        "player_bowling_milestones.csv": build_player_bowling_milestones(bowling),
        "scorecard_record_links.csv": build_scorecard_record_links(batting, bowling),
        "fastest_batting_milestones.csv": build_fastest_batting_milestones(),
    }
    for filename, frame in outputs.items():
        frame.to_csv(OUTPUT_DIR / filename, index=False)

    print("Hall of Fame deploy-safe detail exports rebuilt")
    for filename, frame in outputs.items():
        print(f"- {OUTPUT_DIR / filename}: {len(frame):,} rows")
    return 0


def build_player_win_rates(
    matches: pd.DataFrame,
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
) -> pd.DataFrame:
    if matches.empty:
        return pd.DataFrame()
    match_lookup = matches.copy()
    match_lookup["match_id"] = match_lookup["match_id"].astype(str)
    result_by_match = match_lookup.set_index("match_id")["result_text"].fillna("").astype(str).to_dict()
    parts = []
    for frame in [batting, bowling, fielding]:
        if frame.empty or "match_id" not in frame:
            continue
        rows = frame[["canonical_player_id", "canonical_player_name", "display_player_name", "match_id"]].copy()
        rows["match_id"] = rows["match_id"].astype(str)
        parts.append(rows)
    if not parts:
        return pd.DataFrame()
    appearances = pd.concat(parts, ignore_index=True, sort=False).drop_duplicates(["canonical_player_id", "match_id"])
    appearances["win"] = appearances["match_id"].map(result_by_match).fillna("").str.contains("fiji victorian", case=False, na=False)
    grouped = appearances.groupby(["canonical_player_id", "canonical_player_name", "display_player_name"], dropna=False, as_index=False).agg(
        matches_with_result=("match_id", "nunique"),
        wins=("win", "sum"),
    )
    grouped["losses"] = grouped["matches_with_result"] - grouped["wins"]
    grouped["win_pct"] = grouped.apply(lambda row: layout.divide_or_none(row["wins"] * 100, row["matches_with_result"]), axis=1)
    grouped["player_key"] = grouped["canonical_player_id"]
    grouped["player_name_key"] = grouped["display_player_name"].map(layout.player_name_match_key)
    grouped["source_coverage_note"] = "Tracked deploy-safe summary from local match-centre result rows."
    return grouped[
        [
            "player_key",
            "canonical_player_id",
            "canonical_player_name",
            "display_player_name",
            "player_name_key",
            "matches_with_result",
            "wins",
            "losses",
            "win_pct",
            "source_coverage_note",
        ]
    ].sort_values("display_player_name")


def build_player_bbb_batting_rates(batting: pd.DataFrame, balls: pd.DataFrame) -> pd.DataFrame:
    if batting.empty or balls.empty:
        return pd.DataFrame()
    rows = batting.copy()
    rows["career_scope"] = "career"
    grouped = profile_exports.build_dimension_bbb_batting(rows, balls, "career_scope")
    if grouped.empty:
        return pd.DataFrame()
    grouped = grouped.rename(columns={"canonical_player_id": "player_key"})
    grouped["canonical_player_id"] = grouped["player_key"]
    grouped["bbb_batting_innings"] = pd.NA
    grouped["bbb_matches"] = pd.NA
    grouped = grouped[
        ["player_key", "canonical_player_id", "canonical_player_name", "display_player_name", "bbb_runs", "bbb_balls_faced", "bbb_batting_innings", "bbb_matches"]
    ].copy()
    coverage = rows.groupby("canonical_player_id", as_index=False).agg(
        bbb_batting_innings=("innings_id", "nunique"),
        bbb_matches=("match_id", "nunique"),
    )
    grouped = grouped.drop(columns=["bbb_batting_innings", "bbb_matches"]).merge(
        coverage.rename(columns={"canonical_player_id": "player_key"}),
        on="player_key",
        how="left",
    )
    grouped["bat_sr"] = grouped.apply(lambda row: layout.divide_or_none(row["bbb_runs"] * 100, row["bbb_balls_faced"]), axis=1)
    return grouped.sort_values("display_player_name")


def build_player_scorecard_milestones(batting: pd.DataFrame) -> pd.DataFrame:
    if batting.empty:
        return pd.DataFrame()
    grouped = batting.groupby(["canonical_player_id", "canonical_player_name", "display_player_name"], dropna=False, as_index=False).agg(
        thirties=("is_30", "sum"),
        fifties=("is_50", "sum"),
        hundreds=("is_100", "sum"),
        ducks=("is_duck", "sum"),
        hs=("score_display", layout.best_high_score_from_display_values),
        hs_sort=("high_score_sort", "max"),
    )
    grouped["player_key"] = grouped["canonical_player_id"]
    return grouped[
        ["player_key", "canonical_player_id", "canonical_player_name", "display_player_name", "thirties", "fifties", "hundreds", "ducks", "hs", "hs_sort"]
    ].sort_values("display_player_name")


def build_player_bowling_milestones(bowling: pd.DataFrame) -> pd.DataFrame:
    if bowling.empty:
        return pd.DataFrame()
    match_wickets = bowling.groupby(["canonical_player_id", "match_id"], dropna=False, as_index=False).agg(wickets=("wickets_numeric", "sum"))
    ten_wicket = match_wickets[match_wickets["wickets"].ge(10)].groupby("canonical_player_id", as_index=False).size().rename(columns={"size": "ten_wicket_matches"})
    grouped = bowling.groupby(["canonical_player_id", "canonical_player_name", "display_player_name"], dropna=False, as_index=False).agg(
        three_wicket_innings=("is_3wi", "sum"),
        five_wicket_innings=("is_5wi", "sum"),
        bbi=("bbi_display", layout.best_bbi_from_display_values),
    )
    grouped = grouped.merge(ten_wicket, on="canonical_player_id", how="left")
    grouped["ten_wicket_matches"] = pd.to_numeric(grouped["ten_wicket_matches"], errors="coerce").fillna(0).astype(int)
    parsed = grouped["bbi"].map(parse_bbi)
    grouped["bbi_wickets_sort"] = [item[0] for item in parsed]
    grouped["bbi_runs_sort"] = [item[1] for item in parsed]
    grouped["player_key"] = grouped["canonical_player_id"]
    return grouped[
        [
            "player_key",
            "canonical_player_id",
            "canonical_player_name",
            "display_player_name",
            "three_wicket_innings",
            "five_wicket_innings",
            "ten_wicket_matches",
            "bbi",
            "bbi_wickets_sort",
            "bbi_runs_sort",
        ]
    ].sort_values("display_player_name")


def build_scorecard_record_links(batting: pd.DataFrame, bowling: pd.DataFrame) -> pd.DataFrame:
    frames = []
    if not batting.empty:
        bat = batting.copy()
        bat["mode"] = "batting"
        bat["wickets_taken"] = pd.NA
        bat["runs_conceded"] = pd.NA
        frames.append(bat)
    if not bowling.empty:
        bowl = bowling.copy()
        bowl["mode"] = "bowling"
        bowl["runs_scored"] = pd.NA
        bowl["balls_faced"] = pd.NA
        frames.append(bowl)
    if not frames:
        return pd.DataFrame()
    rows = pd.concat(frames, ignore_index=True, sort=False)
    columns = [
        "mode",
        "canonical_player_id",
        "canonical_player_name",
        "season",
        "match_id",
        "first_match_day",
        "runs_scored",
        "balls_faced",
        "wickets_taken",
        "runs_conceded",
    ]
    for column in columns:
        if column not in rows:
            rows[column] = pd.NA
    return rows[columns].sort_values(["mode", "canonical_player_name", "first_match_day"])


def build_fastest_batting_milestones() -> pd.DataFrame:
    result = build_batting_milestones(
        ROOT / "data" / "processed" / "match_centre",
        players_path=ROOT / "data" / "processed" / "players.csv",
        aliases_path=ROOT / "data" / "player_aliases.csv",
    )
    return result.milestones


def parse_bbi(value: object) -> tuple[int, int]:
    text = str(value or "")
    if "/" in text:
        wickets, runs = text.split("/", 1)
    elif "-" in text:
        wickets, runs = text.split("-", 1)
    else:
        return 0, 9999
    wickets_number = pd.to_numeric(wickets, errors="coerce")
    runs_number = pd.to_numeric(runs, errors="coerce")
    return (
        0 if pd.isna(wickets_number) else int(wickets_number),
        9999 if pd.isna(runs_number) else int(runs_number),
    )


if __name__ == "__main__":
    raise SystemExit(main())
