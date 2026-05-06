#!/usr/bin/env python3
"""Build deploy-safe Hall of Fame premiership exports.

Reads the local premiership exploration outputs and writes small tracked CSVs
under data/processed/hall_of_fame/. The Streamlit app uses these deploy-safe
files instead of ignored experimental audit outputs.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.utils.player_identity import display_player_name


EXPLORATION_DIR = REPO_ROOT / "data" / "processed" / "experimental" / "premiership_exploration"
MATCH_CENTRE_DIR = REPO_ROOT / "data" / "processed" / "match_centre" / "all_available"
OUTPUT_DIR = REPO_ROOT / "data" / "processed" / "hall_of_fame"


def main() -> None:
    wins = read_csv(EXPLORATION_DIR / "fvcc_premiership_win_candidates.csv")
    players = read_csv(EXPLORATION_DIR / "premiership_players_candidate.csv")
    matches = read_csv(MATCH_CENTRE_DIR / "all_matches.csv")

    if wins.empty:
        raise SystemExit("No premiership win candidates found. Run scripts/explore_premierships.py first.")

    wins_export = build_premiership_wins(wins, matches)
    players_export = build_player_premierships(players, wins_export)

    validate_exports(wins_export, players_export)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    wins_export.to_csv(OUTPUT_DIR / "premiership_wins.csv", index=False)
    players_export.to_csv(OUTPUT_DIR / "player_premierships.csv", index=False)

    print(f"Wrote {len(wins_export)} premiership wins")
    print(f"Wrote {len(players_export)} player premiership records")


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def build_premiership_wins(wins: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    output = wins.copy()
    output = output[output.get("confidence", "").astype(str).str.casefold() == "high"].copy()

    match_columns = [
        "match_id",
        "venue_name",
        "first_match_day",
        "last_match_day",
        "home_team_name",
        "away_team_name",
    ]
    if not matches.empty:
        context = matches[[column for column in match_columns if column in matches]].drop_duplicates("match_id")
        output = output.merge(context, on="match_id", how="left")

    output["captain_name"] = output.get("fvcc_captain_name", "").map(display_or_blank)
    output["match_date"] = output.get("match_date", "").where(output.get("match_date", "") != "", output.get("first_match_day", ""))
    output["result_margin_display"] = output.apply(result_margin_display, axis=1)
    output["scoreboard_url"] = output["match_id"].map(playcricket_scorecard_url)
    output["venue_name"] = output.get("venue_name", "").map(clean_text)
    output["opponent_team_name"] = output.get("opponent_team_name", "").map(clean_text)
    output["fvcc_team_name"] = output.get("fvcc_team_name", "").map(clean_text)

    columns = [
        "match_id",
        "season",
        "grade_name",
        "round_name",
        "match_date",
        "fvcc_team_name",
        "opponent_team_name",
        "captain_name",
        "result_text",
        "result_margin_display",
        "venue_name",
        "scoreboard_url",
        "confidence",
        "detection_reason",
    ]
    for column in columns:
        if column not in output:
            output[column] = ""

    return (
        output[columns]
        .drop_duplicates("match_id")
        .sort_values(["season", "grade_name", "match_date"], na_position="last")
        .reset_index(drop=True)
    )


def build_player_premierships(players: pd.DataFrame, wins: pd.DataFrame) -> pd.DataFrame:
    if players.empty or wins.empty:
        return pd.DataFrame(
            columns=[
                "canonical_player_name",
                "display_player_name",
                "premiership_count",
                "seasons",
                "grades",
                "teams",
                "latest_premiership_season",
                "evidence_match_ids",
                "confidence",
            ]
        )

    valid_matches = set(wins["match_id"].astype(str))
    merged = players[players["match_id"].astype(str).isin(valid_matches)].copy()
    merged["display_player_name"] = merged["canonical_player_name"].map(display_or_blank)
    merged["season_sort"] = merged["season"].map(season_sort_key)

    records = []
    for player_name, group in merged.groupby("display_player_name", dropna=False):
        if not player_name:
            continue
        unique_matches = sorted(group["match_id"].dropna().astype(str).unique())
        seasons = sorted(group["season"].dropna().astype(str).unique(), key=season_sort_key)
        latest = seasons[-1] if seasons else ""
        records.append(
            {
                "canonical_player_name": player_name,
                "display_player_name": player_name,
                "premiership_count": len(unique_matches),
                "seasons": ", ".join(seasons),
                "grades": join_unique(group["grade_name"]),
                "teams": join_unique(group["fvcc_team_name"]),
                "latest_premiership_season": latest,
                "evidence_match_ids": ", ".join(unique_matches),
                "confidence": combine_confidence(group.get("confidence", pd.Series(dtype=str))),
            }
        )

    output = pd.DataFrame(records)
    if output.empty:
        return output
    return output.sort_values(
        ["premiership_count", "latest_premiership_season", "display_player_name"],
        ascending=[False, False, True],
        key=lambda series: series.map(season_sort_key) if series.name == "latest_premiership_season" else series,
    ).reset_index(drop=True)


def validate_exports(wins: pd.DataFrame, players: pd.DataFrame) -> None:
    duplicate_matches = wins["match_id"][wins["match_id"].duplicated()].tolist() if "match_id" in wins else []
    if duplicate_matches:
        raise SystemExit(f"Duplicate premiership match rows: {duplicate_matches}")

    if not players.empty:
        for _, row in players.iterrows():
            match_ids = [part.strip() for part in str(row.get("evidence_match_ids", "")).split(",") if part.strip()]
            expected = len(set(match_ids))
            actual = int(row.get("premiership_count", 0))
            if actual != expected:
                raise SystemExit(f"Premiership count mismatch for {row.get('display_player_name')}: {actual} != {expected}")

    bad_urls = [
        url
        for url in wins.get("scoreboard_url", pd.Series(dtype=str)).dropna().astype(str)
        if url and not url.startswith("https://play.cricket.com.au/match/")
    ]
    if bad_urls:
        raise SystemExit(f"Unexpected scoreboard URL format: {bad_urls[:3]}")


def result_margin_display(row: pd.Series) -> str:
    result = clean_text(row.get("result_text"))
    team = clean_text(row.get("fvcc_team_name"))
    if not result:
        return ""
    if team and result.casefold().startswith(team.casefold()):
        return result[len(team) :].strip().capitalize()
    match = re.search(r"\bwon\b(.*)$", result, flags=re.IGNORECASE)
    if match:
        suffix = match.group(0).strip()
        return suffix[0].upper() + suffix[1:] if suffix else ""
    return result


def playcricket_scorecard_url(match_id: object) -> str:
    match_id_text = clean_text(match_id)
    if not match_id_text:
        return ""
    return f"https://play.cricket.com.au/match/{match_id_text}?tab=scorecard"


def display_or_blank(value: object) -> str:
    text = clean_text(value)
    return display_player_name(text) if text else ""


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.casefold() in {"", "nan", "none", "nat"}:
        return ""
    return re.sub(r"\s+", " ", text)


def join_unique(values: pd.Series) -> str:
    labels = []
    for value in values.dropna().astype(str):
        text = clean_text(value)
        if text and text not in labels:
            labels.append(text)
    return ", ".join(labels)


def combine_confidence(values: pd.Series) -> str:
    labels = {clean_text(value).casefold() for value in values if clean_text(value)}
    if "low" in labels:
        return "low"
    if "medium" in labels:
        return "medium"
    return "high" if labels else ""


def season_sort_key(value: object) -> int:
    text = clean_text(value)
    years = [int(year) for year in re.findall(r"(?:19|20)\d{2}", text)]
    if not years:
        return 0
    return max(years)


if __name__ == "__main__":
    main()
