from __future__ import annotations

import argparse
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

MATCH_COLUMNS = [
    "season",
    "match_id",
    "date",
    "team",
    "opponent",
    "venue",
    "competition",
    "result",
    "runs_for",
    "wickets_for",
    "runs_against",
    "wickets_against",
]
BATTING_COLUMNS = [
    "season",
    "match_id",
    "player_id",
    "player_name",
    "runs",
    "balls",
    "fours",
    "sixes",
    "strike_rate",
    "dismissal",
]
BOWLING_COLUMNS = [
    "season",
    "match_id",
    "player_id",
    "player_name",
    "overs",
    "maidens",
    "runs_conceded",
    "wickets",
    "wides",
    "no_balls",
    "economy",
]
FIELDING_COLUMNS = [
    "season",
    "match_id",
    "player_id",
    "player_name",
    "catches",
    "stumpings",
    "run_outs",
]


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(path)
    return pd.read_csv(path)


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def pick_club_team(row: pd.Series, club_team_ids: set[str]) -> tuple[str, str, str, str]:
    home_id = clean_text(row.get("home_team_id"))
    away_id = clean_text(row.get("away_team_id"))
    if home_id in club_team_ids:
        return (
            home_id,
            clean_text(row.get("home_team_name")),
            away_id,
            clean_text(row.get("away_team_name")),
        )
    if away_id in club_team_ids:
        return (
            away_id,
            clean_text(row.get("away_team_name")),
            home_id,
            clean_text(row.get("home_team_name")),
        )
    source_ids = str(row.get("source_team_ids", "")).split("|")
    for team_id in source_ids:
        if team_id in club_team_ids:
            return team_id, clean_text(row.get("home_team_name")), "", clean_text(row.get("away_team_name"))
    return "", "", "", ""


def build_match_rows(matches: pd.DataFrame, innings: pd.DataFrame, teams: pd.DataFrame) -> pd.DataFrame:
    club_team_ids = set(teams["team_id"].dropna().astype(str))
    team_names = dict(zip(teams["team_id"].astype(str), teams["team_name"].astype(str), strict=False))
    innings_totals = (
        innings.groupby(["match_id", "batting_team_id"], dropna=False)
        .agg({"runs_scored": "sum", "wickets_fallen": "sum"})
        .reset_index()
    )
    innings_lookup = {
        (str(row.match_id), str(row.batting_team_id)): (
            int(row.runs_scored) if pd.notna(row.runs_scored) else 0,
            int(row.wickets_fallen) if pd.notna(row.wickets_fallen) else 0,
        )
        for row in innings_totals.itertuples(index=False)
    }
    rows: list[dict[str, object]] = []
    for _, match in matches.iterrows():
        team_id, team_name, opponent_id, opponent_name = pick_club_team(match, club_team_ids)
        if not team_id:
            continue
        runs_for, wickets_for = innings_lookup.get((str(match["match_id"]), team_id), (None, None))
        runs_against, wickets_against = innings_lookup.get((str(match["match_id"]), opponent_id), (None, None))
        rows.append(
            {
                "season": match.get("season", ""),
                "match_id": match.get("match_id", ""),
                "date": pd.to_datetime(match.get("first_match_day"), errors="coerce").date().isoformat()
                if pd.notna(pd.to_datetime(match.get("first_match_day"), errors="coerce"))
                else "",
                "team": team_names.get(team_id, team_name),
                "opponent": opponent_name,
                "venue": match.get("venue_name", ""),
                "competition": match.get("grade_name", ""),
                "result": match.get("result_text", ""),
                "runs_for": runs_for,
                "wickets_for": wickets_for,
                "runs_against": runs_against,
                "wickets_against": wickets_against,
            }
        )
    return pd.DataFrame(rows, columns=MATCH_COLUMNS)


def with_match_season(df: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    return df.merge(matches[["match_id", "season"]], on="match_id", how="left")


def build_batting_rows(batting: pd.DataFrame, matches: pd.DataFrame, club_team_ids: set[str]) -> pd.DataFrame:
    rows = batting[batting["team_id"].astype(str).isin(club_team_ids)].copy()
    rows = with_match_season(rows, matches)
    out = pd.DataFrame(
        {
            "season": rows["season"],
            "match_id": rows["match_id"],
            "player_id": rows["participant_id"],
            "player_name": rows["player_name"],
            "runs": rows["runs_scored"],
            "balls": rows["balls_faced"],
            "fours": rows["fours_scored"],
            "sixes": rows["sixes_scored"],
            "strike_rate": rows["strike_rate"],
            "dismissal": rows["dismissal_text"],
        }
    )
    return out[BATTING_COLUMNS]


def build_bowling_rows(bowling: pd.DataFrame, matches: pd.DataFrame, club_team_ids: set[str]) -> pd.DataFrame:
    rows = bowling[bowling["team_id"].astype(str).isin(club_team_ids)].copy()
    rows = with_match_season(rows, matches)
    out = pd.DataFrame(
        {
            "season": rows["season"],
            "match_id": rows["match_id"],
            "player_id": rows["participant_id"],
            "player_name": rows["player_name"],
            "overs": rows["overs_bowled"],
            "maidens": rows["maidens_bowled"],
            "runs_conceded": rows["runs_conceded"],
            "wickets": rows["wickets_taken"],
            "wides": rows["wides"],
            "no_balls": rows["no_balls"],
            "economy": rows["economy"],
        }
    )
    return out[BOWLING_COLUMNS]


def build_fielding_rows(fielding: pd.DataFrame, matches: pd.DataFrame, club_team_ids: set[str]) -> pd.DataFrame:
    rows = fielding[fielding["team_id"].astype(str).isin(club_team_ids)].copy()
    rows = with_match_season(rows, matches)
    run_outs = rows.get("run_outs", 0).fillna(0) + rows.get("assisted_run_outs", 0).fillna(0)
    out = pd.DataFrame(
        {
            "season": rows["season"],
            "match_id": rows["match_id"],
            "player_id": rows["participant_id"],
            "player_name": rows["player_name"],
            "catches": rows["catches"],
            "stumpings": rows["stumpings"],
            "run_outs": run_outs,
        }
    )
    return out[FIELDING_COLUMNS]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build app-facing scorecard CSVs from club match-centre outputs.")
    parser.add_argument("--club", default=os.environ.get("CLUB_ID", "glen-waverley-hawks"))
    args = parser.parse_args()

    club_id = args.club
    match_root = ROOT / "data" / "processed" / "match_centre" / club_id / "all_available"
    processed = ROOT / "clubs" / club_id / "data" / "processed"
    teams = read_csv(processed / "teams.csv")
    club_team_ids = set(teams["team_id"].dropna().astype(str))

    matches = read_csv(match_root / "all_matches.csv")
    innings = read_csv(match_root / "all_match_innings.csv")
    batting = read_csv(match_root / "all_scorecard_batting.csv")
    bowling = read_csv(match_root / "all_scorecard_bowling.csv")
    fielding = read_csv(match_root / "all_scorecard_fielding.csv")

    outputs = {
        "all_seasons_matches.csv": build_match_rows(matches, innings, teams),
        "all_seasons_scorecard_batting.csv": build_batting_rows(batting, matches, club_team_ids),
        "all_seasons_scorecard_bowling.csv": build_bowling_rows(bowling, matches, club_team_ids),
        "all_seasons_scorecard_fielding.csv": build_fielding_rows(fielding, matches, club_team_ids),
    }

    processed.mkdir(parents=True, exist_ok=True)
    for filename, frame in outputs.items():
        path = processed / filename
        frame.to_csv(path, index=False)
        print(f"{path}: {len(frame):,} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
