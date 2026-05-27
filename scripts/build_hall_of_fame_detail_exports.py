#!/usr/bin/env python3
"""Build deploy-safe Hall of Fame match-centre summaries.

This reads local processed match-centre scopes and writes compact tracked CSVs
under data/processed/hall_of_fame/. It does not fetch data and does not make the
production app depend on ignored match-centre folders at runtime.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_player_profile_insight_exports as profile_exports  # noqa: E402
from scripts.club_refresh_utils import add_club_args, get_club_team_ids, print_club_header, print_outputs, print_paths, resolve_club_id  # noqa: E402
from src.config.club_config import get_club_name, get_club_short_name, get_hall_of_fame_dir, get_mapping_path, get_processed_match_centre_dir, get_processed_path  # noqa: E402
from src.data.match_centre_milestones import build_batting_milestones  # noqa: E402
from src.ui import layout  # noqa: E402


OUTPUT_DIR = ROOT / "data" / "processed" / "hall_of_fame"
OUTPUT_FILENAMES = [
    "player_win_rates.csv",
    "player_bbb_batting_rates.csv",
    "player_scorecard_milestones.csv",
    "player_bowling_milestones.csv",
    "scorecard_record_links.csv",
    "fastest_batting_milestones.csv",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deploy-safe Hall of Fame match-centre summaries.")
    add_club_args(parser)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = resolve_club_id(args.club)
    output_dir = OUTPUT_DIR if args.legacy_output else get_hall_of_fame_dir(club_id=club_id)
    output_paths = [output_dir / filename for filename in OUTPUT_FILENAMES]

    print_club_header("Hall of Fame deploy-safe detail export builder", club_id)
    print_paths(
        "Inputs",
        [
            get_processed_match_centre_dir(club_id=club_id),
            get_processed_path("players.csv", club_id=club_id),
            get_mapping_path("player_aliases.csv", club_id=club_id),
        ],
    )
    print_outputs("Outputs", output_paths)
    if args.dry_run:
        print("Dry run complete. No files were written.")
        return 0

    output_dir.mkdir(parents=True, exist_ok=True)
    frames = profile_exports.load_player_profile_scopes(club_id=club_id)
    if frames["matches"].empty:
        print("No match-centre processed scopes found. No Hall of Fame detail exports built.")
        return 1

    batting = profile_exports.prepare_batting(frames, club_id=club_id)
    bowling = profile_exports.prepare_bowling(frames, club_id=club_id)
    fielding = profile_exports.prepare_fielding(frames, club_id=club_id)
    balls = profile_exports.prepare_ball_rows(frames, club_id=club_id)

    outputs = {
        "player_win_rates.csv": build_player_win_rates(frames["matches"], batting, bowling, fielding, club_id=club_id),
        "player_bbb_batting_rates.csv": build_player_bbb_batting_rates(batting, balls),
        "player_scorecard_milestones.csv": build_player_scorecard_milestones(batting),
        "player_bowling_milestones.csv": build_player_bowling_milestones(bowling),
        "scorecard_record_links.csv": build_scorecard_record_links(batting, bowling),
        "fastest_batting_milestones.csv": build_fastest_batting_milestones(club_id=club_id),
    }
    for filename, frame in outputs.items():
        frame.to_csv(output_dir / filename, index=False)

    print("Hall of Fame deploy-safe detail exports rebuilt")
    for filename, frame in outputs.items():
        print(f"- {output_dir / filename}: {len(frame):,} rows")
    return 0


def build_player_win_rates(
    matches: pd.DataFrame,
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
    club_id: str | None = None,
) -> pd.DataFrame:
    if matches.empty:
        return pd.DataFrame()
    match_lookup = matches.copy()
    match_lookup["match_id"] = match_lookup["match_id"].astype(str)
    result_by_match = club_result_outcomes(match_lookup, club_id=club_id)
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
    appearances["win"] = appearances["match_id"].map(result_by_match)
    appearances = appearances[appearances["win"].notna()].copy()
    if appearances.empty:
        return pd.DataFrame(
            columns=[
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
        )
    appearances["win"] = appearances["win"].astype(bool)
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


def club_result_outcomes(matches: pd.DataFrame, club_id: str | None = None) -> dict[str, object]:
    """Return match_id -> selected-club win/loss outcome for attributable results.

    The PlayCricket result text names the winning side, so the safest club-aware
    interpretation is to compare that winner to the club side identified by the
    match row's fetched team ids. Pending or ambiguous rows are left as missing.
    """
    if matches.empty or "match_id" not in matches:
        return {}
    club_team_ids = get_club_team_ids(club_id)
    club_tokens = club_name_tokens(club_id)
    outcomes: dict[str, object] = {}
    for _, row in matches.iterrows():
        match_id = clean_text(row.get("match_id"))
        if not match_id:
            continue
        outcomes[match_id] = classify_club_result(row, club_team_ids=club_team_ids, club_tokens=club_tokens)
    return outcomes


def classify_club_result(row: pd.Series, *, club_team_ids: set[str], club_tokens: set[str]) -> object:
    result_text = clean_text(row.get("result_text"))
    result_key = normalize_team_name(result_text)
    if not result_key or result_key in {"result pending", "pending"}:
        return pd.NA
    if any(token in result_key for token in ["abandoned", "cancelled", "canceled", "no result"]):
        return pd.NA
    club_name, opponent_name = selected_and_opponent_team_names(row, club_team_ids=club_team_ids, club_tokens=club_tokens)
    if any(token in result_key for token in ["match drawn", "drawn", "match tied", " tied"]):
        return False if club_name else pd.NA

    winner = winner_name_from_result(result_text)
    if not winner:
        return pd.NA
    winner_key = normalize_team_name(winner)
    club_key = normalize_team_name(club_name)
    opponent_key = normalize_team_name(opponent_name)
    if club_key and names_match(winner_key, club_key):
        return True
    if opponent_key and names_match(winner_key, opponent_key):
        return False
    if club_tokens and any(names_match(winner_key, token) for token in club_tokens):
        return True
    return pd.NA


def selected_and_opponent_team_names(row: pd.Series, *, club_team_ids: set[str], club_tokens: set[str]) -> tuple[str, str]:
    home_id = clean_text(row.get("home_team_id"))
    away_id = clean_text(row.get("away_team_id"))
    home_name = clean_text(row.get("home_team_name"))
    away_name = clean_text(row.get("away_team_name"))
    source_ids = split_ids(row.get("source_team_ids"))
    selected_ids = source_ids or club_team_ids
    home_is_club = bool(home_id and home_id in selected_ids)
    away_is_club = bool(away_id and away_id in selected_ids)
    if not home_is_club and not away_is_club:
        home_key = normalize_team_name(home_name)
        away_key = normalize_team_name(away_name)
        home_is_club = bool(home_key and any(names_match(home_key, token) for token in club_tokens))
        away_is_club = bool(away_key and any(names_match(away_key, token) for token in club_tokens))
    if home_is_club and not away_is_club:
        return home_name, away_name
    if away_is_club and not home_is_club:
        return away_name, home_name
    return "", ""


def winner_name_from_result(result_text: str) -> str:
    match = re.match(r"^(?P<winner>.+?)\s+won(?:\s|$)", result_text.strip(), flags=re.IGNORECASE)
    return clean_text(match.group("winner")) if match else ""


def club_name_tokens(club_id: str | None = None) -> set[str]:
    values = {get_club_name(club_id), get_club_short_name(club_id)}
    tokens: set[str] = set()
    for value in values:
        normalized = normalize_team_name(value)
        if normalized:
            tokens.add(normalized)
            tokens.add(re.sub(r"\b(cricket|club|cc)\b", "", normalized).strip())
    return {token for token in tokens if token}


def names_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return left == right or left.startswith(f"{right} ") or right.startswith(f"{left} ")


def normalize_team_name(value: object) -> str:
    text = clean_text(value).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(cricket club|cc)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_ids(value: object) -> set[str]:
    return {part.strip() for part in re.split(r"[|,]", clean_text(value)) if part.strip()}


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"", "nan", "none", "nat"} else text


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


def build_fastest_batting_milestones(club_id: str | None = None) -> pd.DataFrame:
    result = build_batting_milestones(
        get_processed_match_centre_dir(club_id=club_id),
        players_path=get_processed_path("players.csv", club_id=club_id),
        aliases_path=get_mapping_path("player_aliases.csv", club_id=club_id),
        club_team_ids=get_club_team_ids(club_id),
        club_name_token=get_club_name(club_id),
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
