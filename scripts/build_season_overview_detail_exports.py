#!/usr/bin/env python3
"""Build deploy-safe Season Overview detail summaries.

This reads local match-centre processed scopes, de-duplicates overlapping
matches, and writes small tracked CSVs used by Season Overview. It does not
fetch data and does not write raw/full match-centre outputs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui import layout  # noqa: E402


MATCH_CENTRE_ROOT = ROOT / "data" / "processed" / "match_centre"
OUTPUT_DIR = ROOT / "data" / "processed" / "season_overview"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = load_match_centre_scopes()
    if frames["matches"].empty:
        print("No match-centre processed scopes found. No Season Overview exports built.")
        return 1

    build_scorecard_batting(frames).to_csv(OUTPUT_DIR / "scorecard_batting_milestones_by_scope.csv", index=False)
    build_scorecard_bowling(frames).to_csv(OUTPUT_DIR / "scorecard_bowling_milestones_by_scope.csv", index=False)
    build_bbb_batting(frames).to_csv(OUTPUT_DIR / "bbb_batting_rates_by_scope.csv", index=False)
    build_bbb_bowling(frames).to_csv(OUTPUT_DIR / "bbb_bowling_dot_rates_by_scope.csv", index=False)

    print("Season Overview deploy-safe exports rebuilt")
    for path in sorted(OUTPUT_DIR.glob("*.csv")):
        rows = sum(1 for _ in path.open()) - 1
        print(f"- {path}: {rows:,} rows")
    return 0


def load_match_centre_scopes() -> dict[str, pd.DataFrame]:
    scopes = available_scopes()
    frames = {
        "matches": [],
        "batting": [],
        "bowling": [],
        "balls": [],
    }
    for scope_order, scope in enumerate(scopes):
        matches = read_csv(scope / "all_matches.csv")
        if matches.empty:
            continue
        for key, filename in {
            "matches": "all_matches.csv",
            "batting": "all_scorecard_batting.csv",
            "bowling": "all_scorecard_bowling.csv",
            "balls": "all_ball_by_ball.csv",
        }.items():
            frame = read_csv(scope / filename)
            if frame.empty:
                continue
            frame = frame.copy()
            frame["_scope_order"] = scope_order
            frame["_source_scope"] = scope.name
            frames[key].append(frame)

    return {
        key: dedupe_scope_frame(key, pd.concat(parts, ignore_index=True, sort=False) if parts else pd.DataFrame())
        for key, parts in frames.items()
    }


def available_scopes() -> list[Path]:
    if not MATCH_CENTRE_ROOT.exists():
        return []
    scopes = [path for path in MATCH_CENTRE_ROOT.iterdir() if path.is_dir() and (path / "all_matches.csv").exists()]
    return sorted(scopes, key=lambda path: (path.name != "all_available", path.name))


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def dedupe_scope_frame(key: str, frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    frame = frame.sort_values("_scope_order").copy()
    if key == "matches" and "match_id" in frame:
        return frame.drop_duplicates("match_id", keep="last")
    if key == "balls" and "ball_event_id" in frame:
        return frame.drop_duplicates("ball_event_id", keep="last")
    if key == "batting":
        return layout.scorecard_dedupe(frame, ["match_id", "innings_id", "participant_id", "bat_instance"])
    if key == "bowling":
        return layout.scorecard_dedupe(frame, ["match_id", "innings_id", "participant_id"])
    return frame.drop_duplicates()


def match_context(matches: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "match_id",
        "season_id",
        "season",
        "grade_id",
        "grade_name",
        "first_match_day",
        "last_match_day",
        "source_team_ids",
    ]
    available = [column for column in columns if column in matches]
    context = matches[available].copy()
    context["match_id"] = context["match_id"].astype(str)
    if (
        "season_id" not in context
        or "season" not in context
        or context.get("season_id", pd.Series(dtype="object")).isna().any()
        or context.get("season", pd.Series(dtype="object")).isna().any()
    ):
        team_seasons = pd.read_csv(ROOT / "data" / "processed" / "teams.csv")
        team_lookup = team_seasons.drop_duplicates("team_id").set_index("team_id")[["season_id", "season"]].to_dict("index")
        source_ids = context.get("source_team_ids", pd.Series(index=context.index, dtype="object")).fillna("").astype(str)
        first_team_ids = source_ids.map(lambda value: next((part.strip() for part in value.split("|") if part.strip()), ""))
        if "season_id" not in context:
            context["season_id"] = first_team_ids.map(lambda team_id: team_lookup.get(team_id, {}).get("season_id", ""))
        else:
            context["season_id"] = context["season_id"].fillna(
                first_team_ids.map(lambda team_id: team_lookup.get(team_id, {}).get("season_id", ""))
            )
        if "season" not in context:
            context["season"] = first_team_ids.map(lambda team_id: team_lookup.get(team_id, {}).get("season", ""))
        else:
            context["season"] = context["season"].fillna(
                first_team_ids.map(lambda team_id: team_lookup.get(team_id, {}).get("season", ""))
            )
    return context


def prepare_scorecard_rows(rows: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    output = layout.filter_match_centre_fvcc_rows(rows, matches)
    output = output.merge(match_context(matches), on="match_id", how="left", suffixes=("", "_match"))
    output = layout.prepare_match_centre_identity_rows(output)
    output["player_key"] = layout.player_keys(output)
    return output


def build_scorecard_batting(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = prepare_scorecard_rows(frames["batting"], frames["matches"])
    if rows.empty:
        return pd.DataFrame()
    rows = layout.scorecard_dedupe(rows, ["match_id", "innings_id", "participant_id", "bat_instance"])
    rows["runs_numeric"] = pd.to_numeric(rows.get("runs_scored"), errors="coerce")
    rows["is_30"] = rows["runs_numeric"].between(30, 49, inclusive="both")
    return group_scope(rows).agg(
        display_player_name=("canonical_player_name", "first"),
        innings=("innings_id", "count"),
        thirties=("is_30", "sum"),
        latest_match_date=("first_match_day", "max"),
        match_count=("match_id", "nunique"),
    ).assign(thirties=lambda df: df["thirties"].astype(int))


def build_scorecard_bowling(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = prepare_scorecard_rows(frames["bowling"], frames["matches"])
    if rows.empty:
        return pd.DataFrame()
    rows = layout.scorecard_dedupe(rows, ["match_id", "innings_id", "participant_id"])
    rows["wickets_taken"] = pd.to_numeric(rows.get("wickets_taken"), errors="coerce").fillna(0)
    rows["is_3wi"] = rows["wickets_taken"].isin([3, 4])
    rows["is_5wi"] = rows["wickets_taken"] >= 5
    return group_scope(rows).agg(
        display_player_name=("canonical_player_name", "first"),
        three_wicket_innings=("is_3wi", "sum"),
        five_wicket_innings=("is_5wi", "sum"),
        latest_match_date=("first_match_day", "max"),
        match_count=("match_id", "nunique"),
    ).assign(
        three_wicket_innings=lambda df: df["three_wicket_innings"].astype(int),
        five_wicket_innings=lambda df: df["five_wicket_innings"].astype(int),
    )


def build_bbb_batting(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    batting = prepare_scorecard_rows(frames["batting"], frames["matches"])
    balls = frames["balls"].copy()
    if batting.empty or balls.empty:
        return pd.DataFrame()
    lookup = batting.drop_duplicates(["match_id", "innings_id", "participant_id"])[
        scope_columns() + ["participant_id"]
    ].copy()
    lookup = key_lookup(lookup, "participant_id")
    rows = key_lookup(balls, "striker_participant_id").merge(lookup, on=["_match_id", "_innings_id", "_participant_id"], how="inner")
    if rows.empty:
        return pd.DataFrame()
    rows["runs_bat"] = pd.to_numeric(rows.get("runs_bat"), errors="coerce").fillna(0)
    rows["wides"] = pd.to_numeric(rows.get("wides"), errors="coerce").fillna(0)
    rows["ball_faced"] = rows["wides"].eq(0).astype(int)
    rows["batting_dot_ball"] = ((rows["ball_faced"] == 1) & (rows["runs_bat"] == 0)).astype(int)
    grouped = group_scope(rows).agg(
        display_player_name=("canonical_player_name", "first"),
        bbb_runs=("runs_bat", "sum"),
        bbb_balls_faced=("ball_faced", "sum"),
        bbb_dot_balls=("batting_dot_ball", "sum"),
        bbb_batting_innings=("innings_id_y", "nunique"),
        bbb_matches=("match_id_y", "nunique"),
        latest_match_date=("first_match_day", "max"),
    )
    grouped["bat_sr"] = grouped.apply(lambda row: layout.divide_or_none(float(row["bbb_runs"]) * 100, float(row["bbb_balls_faced"])), axis=1)
    grouped["batting_dot_ball_pct"] = grouped.apply(lambda row: layout.divide_or_none(float(row["bbb_dot_balls"]) * 100, float(row["bbb_balls_faced"])), axis=1)
    return grouped


def build_bbb_bowling(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    bowling = prepare_scorecard_rows(frames["bowling"], frames["matches"])
    balls = frames["balls"].copy()
    if bowling.empty or balls.empty:
        return pd.DataFrame()
    lookup = bowling.drop_duplicates(["match_id", "innings_id", "participant_id"])[
        scope_columns() + ["participant_id"]
    ].copy()
    lookup = key_lookup(lookup, "participant_id")
    rows = key_lookup(balls, "bowler_participant_id").merge(lookup, on=["_match_id", "_innings_id", "_participant_id"], how="inner")
    if rows.empty:
        return pd.DataFrame()
    rows["total_runs"] = pd.to_numeric(rows.get("total_runs"), errors="coerce").fillna(0)
    rows["legal_ball"] = rows.get("is_legal_delivery", pd.Series(index=rows.index, dtype="object")).map(layout.parse_bool).astype(int)
    rows["dot_ball"] = ((rows["legal_ball"] == 1) & (rows["total_runs"] == 0)).astype(int)
    grouped = group_scope(rows).agg(
        display_player_name=("canonical_player_name", "first"),
        dot_balls=("dot_ball", "sum"),
        legal_balls=("legal_ball", "sum"),
        latest_match_date=("first_match_day", "max"),
        match_count=("match_id_y", "nunique"),
    )
    grouped["dot_ball_pct"] = grouped.apply(lambda row: layout.divide_or_none(float(row["dot_balls"]) * 100, float(row["legal_balls"])), axis=1)
    return grouped


def scope_columns() -> list[str]:
    return [
        "match_id",
        "innings_id",
        "season_id",
        "season",
        "team_id",
        "grade_id",
        "grade_name",
        "first_match_day",
        "player_key",
        "canonical_player_id",
        "canonical_player_name",
    ]


def key_lookup(frame: pd.DataFrame, participant_column: str) -> pd.DataFrame:
    output = frame.copy()
    output["_match_id"] = output["match_id"].astype(str)
    output["_innings_id"] = output["innings_id"].astype(str)
    output["_participant_id"] = output[participant_column].astype(str)
    return output


def group_scope(rows: pd.DataFrame) -> pd.core.groupby.generic.DataFrameGroupBy:
    return rows.groupby(
        ["season_id", "season", "team_id", "grade_id", "grade_name", "player_key", "canonical_player_id", "canonical_player_name"],
        dropna=False,
        as_index=False,
    )


if __name__ == "__main__":
    raise SystemExit(main())
