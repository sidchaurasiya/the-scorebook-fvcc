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
    build_season_by_round(frames).to_csv(OUTPUT_DIR / "season_by_round_scorecards.csv", index=False)

    print("Season Overview deploy-safe exports rebuilt")
    for path in sorted(OUTPUT_DIR.glob("*.csv")):
        rows = sum(1 for _ in path.open()) - 1
        print(f"- {path}: {rows:,} rows")
    return 0


def load_match_centre_scopes() -> dict[str, pd.DataFrame]:
    scopes = available_scopes()
    frames = {
        "matches": [],
        "innings": [],
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
            "innings": "all_match_innings.csv",
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
        context_columns = [column for column in ["season_id", "season"] if column in frame]
        if context_columns:
            frame["_context_score"] = 0
            for column in context_columns:
                has_value = ~(frame[column].isna() | frame[column].astype(str).str.strip().isin(["", "nan", "None"]))
                frame["_context_score"] += has_value.astype(int)
            frame = frame.sort_values(["_context_score", "_scope_order"])
        return frame.drop_duplicates("match_id", keep="last").drop(columns=["_context_score"], errors="ignore")
    if key == "innings":
        return layout.scorecard_dedupe(frame, ["match_id", "innings_id"])
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
    output = filter_fvcc_team_rows(rows)
    output = output.merge(match_context(matches), on="match_id", how="left", suffixes=("", "_match"))
    output = fill_context_from_team(output)
    output = layout.prepare_match_centre_identity_rows(output)
    output["player_key"] = layout.player_keys(output)
    return output


def team_context() -> pd.DataFrame:
    teams = pd.read_csv(ROOT / "data" / "processed" / "teams.csv")
    columns = ["team_id", "team_name", "season_id", "season", "grade_id", "grade_name"]
    output = teams[[column for column in columns if column in teams]].drop_duplicates("team_id").copy()
    output["team_id"] = output["team_id"].astype(str)
    return output


def filter_fvcc_team_rows(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows.copy()
    output = rows.copy()
    if "team_id" not in output:
        return output
    fvcc_team_ids = set(team_context()["team_id"].astype(str))
    output = output[output["team_id"].astype(str).isin(fvcc_team_ids)].copy()
    return output


def fill_context_from_team(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty or "team_id" not in rows:
        return rows
    output = rows.copy()
    lookup = team_context().rename(
        columns={
            "team_name": "team_name_team",
            "season_id": "season_id_team",
            "season": "season_team",
            "grade_id": "grade_id_team",
            "grade_name": "grade_name_team",
        }
    )
    output["team_id"] = output["team_id"].astype(str)
    output = output.merge(lookup, on="team_id", how="left")
    for column in ["team_name", "season_id", "season", "grade_id", "grade_name"]:
        team_column = f"{column}_team"
        if team_column not in output:
            continue
        if column not in output:
            output[column] = output[team_column]
        else:
            current = output[column]
            missing = current.isna() | current.astype(str).str.strip().isin(["", "nan", "None"])
            output.loc[missing, column] = output.loc[missing, team_column]
        output = output.drop(columns=[team_column])
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
    batting = layout.scorecard_dedupe(batting, ["match_id", "innings_id", "participant_id", "bat_instance"])
    batting["scorecard_runs"] = pd.to_numeric(batting.get("runs_scored"), errors="coerce")
    batting["scorecard_balls"] = pd.to_numeric(batting.get("balls_faced"), errors="coerce")
    lookup = batting.drop_duplicates(["match_id", "innings_id", "participant_id"])[
        scope_columns() + ["participant_id", "scorecard_runs", "scorecard_balls"]
    ].copy()
    lookup = key_lookup(lookup, "participant_id")
    rows = key_lookup(balls, "striker_participant_id").merge(lookup, on=["_match_id", "_innings_id", "_participant_id"], how="inner")
    if rows.empty:
        return pd.DataFrame()
    rows["runs_bat"] = pd.to_numeric(rows.get("runs_bat"), errors="coerce").fillna(0)
    rows["wides"] = pd.to_numeric(rows.get("wides"), errors="coerce").fillna(0)
    rows["source_batter_runs"] = pd.to_numeric(rows.get("striker_runs_scored"), errors="coerce")
    rows["source_batter_balls"] = pd.to_numeric(rows.get("striker_balls_faced"), errors="coerce")
    rows["ball_faced"] = rows["wides"].eq(0).astype(int)
    rows["batting_dot_ball"] = ((rows["ball_faced"] == 1) & (rows["runs_bat"] == 0)).astype(int)
    innings_grouped = rows.groupby(
        group_columns() + ["match_id_y", "innings_id_y", "scorecard_runs", "scorecard_balls"],
        dropna=False,
        as_index=False,
    ).agg(
        display_player_name=("canonical_player_name", "first"),
        summed_runs=("runs_bat", "sum"),
        summed_balls_faced=("ball_faced", "sum"),
        source_batter_runs=("source_batter_runs", "max"),
        source_batter_balls=("source_batter_balls", "max"),
        bbb_dot_balls=("batting_dot_ball", "sum"),
        latest_match_date=("first_match_day", "max"),
    )
    innings_grouped["has_source_cumulative"] = innings_grouped["source_batter_runs"].notna() & innings_grouped["source_batter_balls"].notna()
    innings_grouped["bbb_runs"] = innings_grouped["source_batter_runs"].where(
        innings_grouped["has_source_cumulative"],
        innings_grouped["summed_runs"],
    )
    innings_grouped["bbb_balls_faced"] = innings_grouped["source_batter_balls"].where(
        innings_grouped["has_source_cumulative"],
        innings_grouped["summed_balls_faced"],
    )
    innings_grouped["bbb_dot_ball_balls_faced"] = innings_grouped["bbb_balls_faced"]
    innings_grouped["verified_bbb_innings"] = (
        innings_grouped["scorecard_runs"].notna()
        & innings_grouped["scorecard_balls"].notna()
        & innings_grouped["scorecard_balls"].gt(0)
        & innings_grouped["bbb_balls_faced"].gt(0)
        & innings_grouped["bbb_runs"].eq(innings_grouped["scorecard_runs"])
        & innings_grouped["bbb_balls_faced"].eq(innings_grouped["scorecard_balls"])
    )
    innings_grouped = innings_grouped[innings_grouped["verified_bbb_innings"]].copy()
    if innings_grouped.empty:
        return pd.DataFrame()
    grouped = innings_grouped.groupby(group_columns(), dropna=False, as_index=False).agg(
        display_player_name=("display_player_name", "first"),
        bbb_runs=("bbb_runs", "sum"),
        bbb_balls_faced=("bbb_balls_faced", "sum"),
        bbb_dot_balls=("bbb_dot_balls", "sum"),
        bbb_dot_ball_balls_faced=("bbb_dot_ball_balls_faced", "sum"),
        bbb_batting_innings=("innings_id_y", "nunique"),
        bbb_matches=("match_id_y", "nunique"),
        latest_match_date=("latest_match_date", "max"),
    )
    grouped["bat_sr"] = grouped.apply(lambda row: layout.divide_or_none(float(row["bbb_runs"]) * 100, float(row["bbb_balls_faced"])), axis=1)
    grouped["batting_dot_ball_pct"] = grouped.apply(
        lambda row: layout.divide_or_none(float(row["bbb_dot_balls"]) * 100, float(row["bbb_dot_ball_balls_faced"])),
        axis=1,
    )
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


def build_season_by_round(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    matches = frames["matches"].copy()
    if matches.empty:
        return pd.DataFrame()

    context = match_context(matches)
    matches = layout.build_match_archive_frame(matches)
    if not context.empty:
        matches = matches.merge(
            context[["match_id", "season_id", "season"]].drop_duplicates("match_id"),
            on="match_id",
            how="left",
            suffixes=("", "_context"),
        )
        for column in ["season_id", "season"]:
            context_column = f"{column}_context"
            if context_column not in matches:
                continue
            if column not in matches:
                matches[column] = matches[context_column]
            else:
                missing = matches[column].isna() | matches[column].astype(str).str.strip().isin(["", "nan", "None"])
                matches.loc[missing, column] = matches.loc[missing, context_column]
            matches = matches.drop(columns=[context_column])

    batting = layout.add_missing_canonical_player_ids(frames["batting"])
    bowling = layout.filter_real_scorecard_bowling_rows(layout.add_missing_canonical_player_ids(frames["bowling"]))
    best_batters = layout.best_batters_by_match(batting, matches, frames.get("innings", pd.DataFrame()))
    best_bowlers = layout.best_bowlers_by_match(bowling, matches, frames.get("innings", pd.DataFrame()))
    premiership_match_ids = layout.season_round_premiership_match_ids()

    rows = []
    for _, match in matches.iterrows():
        match_id = str(match.get("match_id", "") or "").strip()
        if not match_id:
            continue
        result = layout.season_round_result(match)
        grade_label = layout.season_round_grade_label(match)
        rows.append(
            {
                "match_id": match_id,
                "season_id": clean_value(match.get("season_id")),
                "season": clean_value(match.get("season")),
                "source_team_ids": clean_value(match.get("source_team_ids")),
                "fvcc_team_id": clean_value(match.get("fvcc_team_id")),
                "fvcc_team_name": clean_value(match.get("fvcc_team_name")),
                "grade_id": clean_value(match.get("grade_id")),
                "grade_name": clean_value(match.get("grade_name")),
                "grade_label": grade_label,
                "round_name": clean_value(match.get("round_name")),
                "round_display": layout.season_round_display(match.get("round_name")),
                "round_sort": layout.season_round_sort_value(match.get("round_name")),
                "match_date": clean_value(match.get("match_date")),
                "opponent_name": clean_value(match.get("opponent_name"), "Unknown opponent"),
                "result_label": result["label"],
                "result_class": result["class"],
                "result_text": result["text"],
                "best_batter": best_batters.get(match_id, "—"),
                "best_bowler": best_bowlers.get(match_id, "—"),
                "is_premiership": match_id in premiership_match_ids,
            }
        )
    if not rows:
        return pd.DataFrame()
    output = pd.DataFrame(rows)
    output["_match_date_sort"] = pd.to_datetime(output["match_date"], errors="coerce", utc=True)
    return output.sort_values(["season", "grade_label", "round_sort", "_match_date_sort"], ascending=[True, True, False, False]).drop(
        columns=["_match_date_sort"]
    )


def clean_value(value: object, fallback: str = "") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text and text.casefold() not in {"nan", "none", "nat"} else fallback


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
        group_columns(),
        dropna=False,
        as_index=False,
    )


def group_columns() -> list[str]:
    return ["season_id", "season", "team_id", "grade_id", "grade_name", "player_key", "canonical_player_id", "canonical_player_name"]


if __name__ == "__main__":
    raise SystemExit(main())
