#!/usr/bin/env python3
"""Build deploy-safe Player Profile insight summaries.

This reads local processed match-centre scopes and writes compact tracked CSVs
for the production Player Profile page. It does not fetch data and does not
write raw/full match-centre outputs.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_season_overview_detail_exports as season_exports  # noqa: E402
from src.ui import layout  # noqa: E402


MATCH_CENTRE_ROOT = ROOT / "data" / "processed" / "match_centre"
OUTPUT_DIR = ROOT / "data" / "processed" / "player_profile"

DIMENSION_ORDER = ["Season", "Grade", "Opponent", "Ground", "H/A"]
POSITION_GROUP_ORDER = {
    "Opener": 1,
    "No. 3": 3,
    "No. 4": 4,
    "No. 5": 5,
    "No. 6": 6,
    "No. 7": 7,
    "No. 8": 8,
    "No. 9": 9,
    "Tail": 10,
}
DISMISSAL_ORDER = {"Caught": 1, "Bowled": 2, "LBW": 3, "Run out": 4, "Stumped": 5, "Other": 6}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = load_player_profile_scopes()
    if frames["matches"].empty:
        print("No match-centre processed scopes found. No Player Profile insight exports built.")
        return 1

    batting = prepare_batting(frames)
    bowling = prepare_bowling(frames)
    fielding = prepare_fielding(frames)
    balls = prepare_ball_rows(frames)

    outputs = {
        "performance_breakdown_by_dimension.csv": build_performance_breakdown(batting, bowling, fielding, balls),
        "batting_position_summary.csv": build_batting_position_summary(batting),
        "bowling_phase_summary.csv": build_bowling_phase_summary(bowling, balls),
        "dismissal_fingerprint_summary.csv": build_dismissal_fingerprint_summary(batting),
    }
    for filename, frame in outputs.items():
        frame.to_csv(OUTPUT_DIR / filename, index=False)

    print("Player Profile deploy-safe insight exports rebuilt")
    for filename, frame in outputs.items():
        print(f"- {OUTPUT_DIR / filename}: {len(frame):,} rows")
    return 0


def load_player_profile_scopes() -> dict[str, pd.DataFrame]:
    frames = season_exports.load_match_centre_scopes()
    fielding_parts = []
    for scope_order, scope in enumerate(season_exports.available_scopes()):
        fielding = season_exports.read_csv(scope / "all_scorecard_fielding.csv")
        if fielding.empty:
            continue
        fielding = fielding.copy()
        fielding["_scope_order"] = scope_order
        fielding["_source_scope"] = scope.name
        fielding_parts.append(fielding)
    frames["fielding"] = (
        season_exports.dedupe_scope_frame("fielding", pd.concat(fielding_parts, ignore_index=True, sort=False))
        if fielding_parts
        else pd.DataFrame()
    )
    return frames


def prepare_batting(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = season_exports.prepare_scorecard_rows(frames["batting"], frames["matches"])
    if rows.empty:
        return rows
    rows = layout.scorecard_dedupe(rows, ["match_id", "innings_id", "participant_id", "bat_instance"])
    rows = add_match_dimensions(rows, frames["matches"])
    rows = ensure_display_player_name(rows)
    rows["runs_numeric"] = pd.to_numeric(rows.get("runs_scored"), errors="coerce").fillna(0)
    rows["balls_numeric"] = pd.to_numeric(rows.get("balls_faced"), errors="coerce").fillna(0)
    rows["fours_numeric"] = pd.to_numeric(rows.get("fours_scored"), errors="coerce").fillna(0)
    rows["sixes_numeric"] = pd.to_numeric(rows.get("sixes_scored"), errors="coerce").fillna(0)
    rows["not_out"] = rows.apply(is_not_out, axis=1)
    rows["out"] = ~rows["not_out"]
    rows["is_30"] = rows["runs_numeric"].between(30, 49, inclusive="both")
    rows["is_50"] = rows["runs_numeric"].between(50, 99, inclusive="both")
    rows["is_100"] = rows["runs_numeric"].ge(100)
    rows["is_duck"] = rows["runs_numeric"].eq(0) & rows["out"]
    rows["score_display"] = rows.apply(lambda row: f"{int(row['runs_numeric'])}{'*' if row['not_out'] else ''}", axis=1)
    rows["high_score_sort"] = rows["runs_numeric"]
    rows["high_score_not_out_sort"] = rows["not_out"].astype(int)
    rows["position_group"] = rows.get("bat_order", pd.Series(index=rows.index, dtype="object")).map(position_group)
    rows["position_order"] = rows["position_group"].map(POSITION_GROUP_ORDER).fillna(99).astype(int)
    return rows


def prepare_bowling(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = season_exports.prepare_scorecard_rows(frames["bowling"], frames["matches"])
    if rows.empty:
        return rows
    rows = layout.scorecard_dedupe(rows, ["match_id", "innings_id", "participant_id"])
    rows = add_match_dimensions(rows, frames["matches"])
    rows = ensure_display_player_name(rows)
    rows["wickets_numeric"] = pd.to_numeric(rows.get("wickets_taken"), errors="coerce").fillna(0)
    rows["runs_against_numeric"] = pd.to_numeric(rows.get("runs_conceded"), errors="coerce").fillna(0)
    rows["balls_numeric"] = rows.get("overs_bowled", pd.Series(index=rows.index, dtype="object")).map(layout.cricket_overs_to_balls).fillna(0)
    rows["is_3wi"] = rows["wickets_numeric"].isin([3, 4])
    rows["is_5wi"] = rows["wickets_numeric"].ge(5)
    rows["bbi_display"] = rows.apply(lambda row: f"{int(row['wickets_numeric'])}/{int(row['runs_against_numeric'])}", axis=1)
    return rows


def prepare_fielding(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = frames.get("fielding", pd.DataFrame())
    if frame.empty:
        return pd.DataFrame()
    rows = season_exports.prepare_scorecard_rows(frame, frames["matches"])
    rows = add_match_dimensions(rows, frames["matches"])
    rows = ensure_display_player_name(rows)
    for column in ["catches", "stumpings", "run_outs", "assisted_run_outs"]:
        if column not in rows:
            rows[column] = 0
        rows[column] = pd.to_numeric(rows[column], errors="coerce").fillna(0)
    rows["run_outs_total"] = rows["run_outs"] + rows["assisted_run_outs"]
    rows["dismissals_total"] = rows["catches"] + rows["stumpings"] + rows["run_outs_total"]
    return rows


def prepare_ball_rows(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    balls = frames.get("balls", pd.DataFrame()).copy()
    if balls.empty:
        return balls
    matches = match_dimension_context(frames["matches"])
    balls["match_id"] = balls["match_id"].astype(str)
    balls = balls.merge(matches, on="match_id", how="left", suffixes=("", "_match"))
    balls["is_legal"] = balls.get("is_legal_delivery", pd.Series(index=balls.index, dtype="object")).map(layout.parse_bool)
    balls["total_runs_numeric"] = pd.to_numeric(balls.get("total_runs"), errors="coerce").fillna(0)
    balls["runs_bat_numeric"] = pd.to_numeric(balls.get("runs_bat"), errors="coerce").fillna(0)
    balls["over_number_numeric"] = pd.to_numeric(balls.get("over_number"), errors="coerce").fillna(0).astype(int) + 1
    balls["bowler_key"] = balls.get("bowler_participant_id", pd.Series(index=balls.index, dtype="object")).astype(str)
    return balls


def ensure_display_player_name(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    output = rows.copy()
    if "canonical_player_id" not in output:
        output["canonical_player_id"] = ""
    if "canonical_player_name" not in output:
        output["canonical_player_name"] = output.get("player_name", pd.Series(index=output.index, dtype="object"))
    if "display_player_name" not in output:
        output["display_player_name"] = output["canonical_player_name"]
    return output


def match_dimension_context(matches: pd.DataFrame) -> pd.DataFrame:
    context = season_exports.match_context(matches)
    if context.empty:
        return pd.DataFrame(columns=["match_id", "opponent_label", "ground_label", "home_away_label", "match_type"])
    raw = matches.copy()
    raw["match_id"] = raw["match_id"].astype(str)
    for column in ["home_team_id", "away_team_id", "home_team_name", "away_team_name", "venue_name", "match_type"]:
        if column not in raw:
            raw[column] = ""
    fvcc_team_ids = set(season_exports.team_context()["team_id"].astype(str))
    fvcc_is_home = raw["home_team_id"].astype(str).isin(fvcc_team_ids)
    raw["opponent_label"] = raw["away_team_name"].where(fvcc_is_home, raw["home_team_name"]).map(normalize_opponent_name)
    raw["ground_label"] = raw["venue_name"].map(normalize_ground_name)
    raw["home_away_label"] = fvcc_is_home.map(lambda value: "Home" if value else "Away")
    return raw[["match_id", "opponent_label", "ground_label", "home_away_label", "match_type"]].drop_duplicates("match_id")


def add_match_dimensions(rows: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    output = rows.copy()
    output["match_id"] = output["match_id"].astype(str)
    context = match_dimension_context(matches)
    if not context.empty:
        output = output.merge(context, on="match_id", how="left", suffixes=("", "_dimension"))
    output["season_label"] = output.get("season", pd.Series(index=output.index, dtype="object")).fillna("").astype(str).replace("", "Unknown season")
    output["grade_label"] = output.apply(lambda row: layout.clean_profile_grade_label(row.get("grade_name", "")) or "Unknown grade", axis=1)
    output["opponent_label"] = output.get("opponent_label", pd.Series(index=output.index, dtype="object")).fillna("Unknown opponent")
    output["ground_label"] = output.get("ground_label", pd.Series(index=output.index, dtype="object")).fillna("Unknown ground")
    output["home_away_label"] = output.get("home_away_label", pd.Series(index=output.index, dtype="object")).fillna("")
    return output


def build_performance_breakdown(
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
    balls: pd.DataFrame,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for dimension, column in [
        ("Season", "season_label"),
        ("Grade", "grade_label"),
        ("Opponent", "opponent_label"),
        ("Ground", "ground_label"),
        ("H/A", "home_away_label"),
    ]:
        frames.append(build_batting_breakdown(batting, balls, dimension, column))
        frames.append(build_bowling_breakdown(bowling, dimension, column))
        frames.append(build_fielding_breakdown(fielding, dimension, column))
    frames = [frame for frame in frames if not frame.empty]
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def build_batting_breakdown(batting: pd.DataFrame, balls: pd.DataFrame, dimension: str, column: str) -> pd.DataFrame:
    if batting.empty or column not in batting:
        return pd.DataFrame()
    rows = batting[batting[column].astype(str).str.strip() != ""].copy()
    if rows.empty:
        return pd.DataFrame()
    grouped = rows.groupby(player_dimension_columns(column), dropna=False, as_index=False).agg(
        innings=("innings_id", "count"),
        runs=("runs_numeric", "sum"),
        outs=("out", "sum"),
        high_score=("score_display", best_high_score_from_labels),
        high_score_sort=("high_score_sort", "max"),
        high_score_not_out_sort=("high_score_not_out_sort", "max"),
        thirties=("is_30", "sum"),
        fifties=("is_50", "sum"),
        hundreds=("is_100", "sum"),
        ducks=("is_duck", "sum"),
        fours=("fours_numeric", "sum"),
        sixes=("sixes_numeric", "sum"),
    )
    grouped["bat_avg"] = grouped.apply(lambda row: divide_or_none(row["runs"], row["outs"]), axis=1)
    bbb = build_dimension_bbb_batting(rows, balls, column)
    grouped = grouped.merge(bbb, on=player_dimension_columns(column), how="left")
    grouped["strike_rate"] = grouped.apply(lambda row: divide_or_none(row.get("bbb_runs", 0) * 100, row.get("bbb_balls_faced", 0)), axis=1)
    return common_dimension_output(grouped, dimension, column, "Batting")


def build_dimension_bbb_batting(batting: pd.DataFrame, balls: pd.DataFrame, column: str) -> pd.DataFrame:
    if batting.empty or balls.empty:
        return pd.DataFrame(columns=player_dimension_columns(column) + ["bbb_runs", "bbb_balls_faced"])
    keys = batting[player_dimension_columns(column) + ["match_id", "innings_id", "participant_id"]].drop_duplicates()
    ball_source = balls.drop(columns=["season_label", "grade_label", "opponent_label", "ground_label", "home_away_label"], errors="ignore")
    source = ball_source.merge(
        keys,
        left_on=["match_id", "innings_id", "striker_participant_id"],
        right_on=["match_id", "innings_id", "participant_id"],
        how="inner",
    )
    if source.empty:
        return pd.DataFrame(columns=player_dimension_columns(column) + ["bbb_runs", "bbb_balls_faced"])
    source["wides"] = pd.to_numeric(source.get("wides"), errors="coerce").fillna(0)
    source["source_batter_runs"] = pd.to_numeric(source.get("striker_runs_scored"), errors="coerce")
    source["source_batter_balls"] = pd.to_numeric(source.get("striker_balls_faced"), errors="coerce")
    source["ball_faced"] = source["wides"].eq(0).astype(int)
    innings = source.groupby(
        player_dimension_columns(column) + ["match_id", "innings_id"],
        dropna=False,
        as_index=False,
    ).agg(
        bbb_runs=("runs_bat_numeric", "sum"),
        bbb_balls_faced=("ball_faced", "sum"),
        source_batter_runs=("source_batter_runs", "max"),
        source_batter_balls=("source_batter_balls", "max"),
    )
    innings = innings[
        innings["source_batter_runs"].notna()
        & innings["source_batter_balls"].notna()
        & innings["source_batter_balls"].gt(0)
        & innings["bbb_balls_faced"].gt(0)
        & innings["bbb_runs"].eq(innings["source_batter_runs"])
        & innings["bbb_balls_faced"].eq(innings["source_batter_balls"])
    ].copy()
    if innings.empty:
        return pd.DataFrame(columns=player_dimension_columns(column) + ["bbb_runs", "bbb_balls_faced"])
    return innings.groupby(player_dimension_columns(column), dropna=False, as_index=False).agg(
        bbb_runs=("bbb_runs", "sum"),
        bbb_balls_faced=("bbb_balls_faced", "sum"),
    )


def build_bowling_breakdown(bowling: pd.DataFrame, dimension: str, column: str) -> pd.DataFrame:
    if bowling.empty or column not in bowling:
        return pd.DataFrame()
    rows = bowling[bowling[column].astype(str).str.strip() != ""].copy()
    if rows.empty:
        return pd.DataFrame()
    grouped = rows.groupby(player_dimension_columns(column), dropna=False, as_index=False).agg(
        matches=("match_id", "nunique"),
        balls_bowled=("balls_numeric", "sum"),
        runs_against=("runs_against_numeric", "sum"),
        wickets=("wickets_numeric", "sum"),
        bbi=("bbi_display", best_bbi_from_labels),
        three_wicket_innings=("is_3wi", "sum"),
        five_wicket_innings=("is_5wi", "sum"),
    )
    grouped["bowl_avg"] = grouped.apply(lambda row: divide_or_none(row["runs_against"], row["wickets"]), axis=1)
    grouped["bowl_sr"] = grouped.apply(lambda row: divide_or_none(row["balls_bowled"], row["wickets"]), axis=1)
    grouped["eco"] = grouped.apply(lambda row: divide_or_none(row["runs_against"] * 6, row["balls_bowled"]), axis=1)
    return common_dimension_output(grouped, dimension, column, "Bowling")


def build_fielding_breakdown(fielding: pd.DataFrame, dimension: str, column: str) -> pd.DataFrame:
    if fielding.empty or column not in fielding:
        return pd.DataFrame()
    rows = fielding[fielding[column].astype(str).str.strip() != ""].copy()
    if rows.empty:
        return pd.DataFrame()
    grouped = rows.groupby(player_dimension_columns(column), dropna=False, as_index=False).agg(
        catches=("catches", "sum"),
        stumpings=("stumpings", "sum"),
        run_outs=("run_outs_total", "sum"),
        dismissals=("dismissals_total", "sum"),
    )
    return common_dimension_output(grouped, dimension, column, "Fielding")


def common_dimension_output(grouped: pd.DataFrame, dimension: str, column: str, discipline: str) -> pd.DataFrame:
    output = grouped.copy()
    output["dimension"] = dimension
    output["dimension_order"] = DIMENSION_ORDER.index(dimension)
    output["discipline"] = discipline
    output = output.rename(columns={column: "breakdown_label"})
    if "canonical_player_id" not in output:
        output["canonical_player_id"] = ""
    if "canonical_player_name" not in output:
        output["canonical_player_name"] = ""
    if "display_player_name" not in output:
        output["display_player_name"] = output["canonical_player_name"]
    return output


def build_batting_position_summary(batting: pd.DataFrame) -> pd.DataFrame:
    if batting.empty:
        return pd.DataFrame()
    rows = batting[batting["position_group"].notna()].copy()
    if rows.empty:
        return pd.DataFrame()
    grouped = rows.groupby(["canonical_player_id", "canonical_player_name", "display_player_name", "position_group", "position_order"], dropna=False, as_index=False).agg(
        innings=("innings_id", "count"),
        runs=("runs_numeric", "sum"),
        outs=("out", "sum"),
    )
    grouped["average"] = grouped.apply(lambda row: divide_or_none(row["runs"], row["outs"]), axis=1)
    return grouped.sort_values(["canonical_player_name", "position_order"])


def build_bowling_phase_summary(bowling: pd.DataFrame, balls: pd.DataFrame) -> pd.DataFrame:
    if bowling.empty or balls.empty:
        return pd.DataFrame()
    lookup = bowling[["match_id", "innings_id", "participant_id", "canonical_player_id", "canonical_player_name", "display_player_name"]].drop_duplicates()
    source = balls.merge(
        lookup,
        left_on=["match_id", "innings_id", "bowler_participant_id"],
        right_on=["match_id", "innings_id", "participant_id"],
        how="inner",
    )
    source = source[source["is_legal"]].copy()
    if "ball_event_id" in source:
        source = source.drop_duplicates("ball_event_id")
    if source.empty:
        return pd.DataFrame()
    source["wicket_credit"] = source.apply(is_bowler_wicket_ball, axis=1)
    source["phase_model"] = source.get("match_type", pd.Series(index=source.index, dtype="object")).map(phase_model_from_match_type)
    source = source[source["phase_model"].notna()].copy()
    if source.empty:
        return pd.DataFrame()
    frames = []
    for model in ["T20", "One Day", "Two Day"]:
        model_rows = source[source["phase_model"].eq(model)].copy()
        if model_rows.empty:
            continue
        model_rows["phase"] = model_rows["over_number_numeric"].map(lambda over: phase_for_model(over, model))
        model_rows["phase_order"] = model_rows["phase"].map({"Opening": 1, "Middle": 2, "Death": 3, "New Ball": 1, "Older Ball": 2})
        frames.append(model_rows)
    if not frames:
        return pd.DataFrame()
    output = pd.concat(frames, ignore_index=True)
    grouped = output.groupby(["canonical_player_id", "canonical_player_name", "display_player_name", "phase_model", "phase", "phase_order"], dropna=False, as_index=False).agg(
        legal_balls=("is_legal", "sum"),
        wickets=("wicket_credit", "sum"),
        runs_conceded=("total_runs_numeric", "sum"),
        match_count=("match_id", "nunique"),
    )
    grouped["overs"] = grouped["legal_balls"].map(layout.format_balls_as_overs)
    grouped["avg"] = grouped.apply(lambda row: divide_or_none(row["runs_conceded"], row["wickets"]), axis=1)
    grouped["eco"] = grouped.apply(lambda row: divide_or_none(row["runs_conceded"] * 6, row["legal_balls"]), axis=1)
    grouped["sr"] = grouped.apply(lambda row: divide_or_none(row["legal_balls"], row["wickets"]), axis=1)
    return grouped.sort_values(["canonical_player_name", "phase_model", "phase_order"])


def build_dismissal_fingerprint_summary(batting: pd.DataFrame) -> pd.DataFrame:
    if batting.empty:
        return pd.DataFrame()
    rows = batting[batting["out"]].copy()
    if rows.empty:
        return pd.DataFrame()
    rows["dismissal_bucket"] = rows.apply(dismissal_bucket, axis=1)
    player = rows.groupby(["canonical_player_id", "canonical_player_name", "display_player_name", "dismissal_bucket"], dropna=False, as_index=False).size().rename(columns={"size": "count"})
    player["scope"] = "player"
    club = rows.groupby("dismissal_bucket", dropna=False, as_index=False).size().rename(columns={"size": "count"})
    club["canonical_player_id"] = "__club__"
    club["canonical_player_name"] = "Club average"
    club["display_player_name"] = "Club average"
    club["scope"] = "club"
    output = pd.concat([player, club], ignore_index=True, sort=False)
    output["total_dismissals"] = output.groupby(["scope", "canonical_player_id"], dropna=False)["count"].transform("sum")
    output["pct"] = output.apply(lambda row: divide_or_none(row["count"] * 100, row["total_dismissals"]), axis=1)
    output["dismissal_order"] = output["dismissal_bucket"].map(DISMISSAL_ORDER).fillna(99).astype(int)
    return output.sort_values(["scope", "canonical_player_name", "dismissal_order"])


def player_dimension_columns(column: str) -> list[str]:
    return ["canonical_player_id", "canonical_player_name", "display_player_name", column]


def position_group(value: object) -> str | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    position = int(number)
    if position <= 0:
        return None
    if position <= 2:
        return "Opener"
    if 3 <= position <= 9:
        return f"No. {position}"
    return "Tail"


def normalize_opponent_name(value: object) -> str:
    text = clean_text(value, "Unknown opponent")
    text = re.sub(r"\b(Cricket Club|CC)\b", "CC", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(\d+(st|nd|rd|th)?\s*)?XI\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(1s|2s|3s|4s|5s)\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\b(1st|2nd|3rd|4th|5th)\s+XI\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip(" -")
    text = re.sub(r"\bCC\s+CC\b", "CC", text, flags=re.IGNORECASE)
    return text or "Unknown opponent"


def normalize_ground_name(value: object) -> str:
    text = clean_text(value, "Unknown ground")
    return re.sub(r"\s+", " ", text).strip() or "Unknown ground"


def phase_model_from_match_type(value: object) -> str | None:
    text = clean_text(value).casefold()
    if not text:
        return None
    if "t20" in text or "twenty20" in text or "twenty 20" in text:
        return "T20"
    if "one day" in text or "limited" in text or "odi" in text:
        return "One Day"
    if "two day" in text or "2 day" in text or "two-day" in text:
        return "Two Day"
    return None


def clean_text(value: object, fallback: str = "") -> str:
    if pd.isna(value):
        return fallback
    text = str(value).strip()
    return text if text else fallback


def is_not_out(row: pd.Series) -> bool:
    text = f"{row.get('dismissal_type', '')} {row.get('dismissal_text', '')}".strip().casefold()
    return text in {"", "not out"} or "not out" in text or "retired not out" in text


def dismissal_bucket(row: pd.Series) -> str:
    text = f"{row.get('dismissal_type', '')} {row.get('dismissal_text', '')}".casefold()
    if "caught" in text or re.search(r"\bc\b", text):
        return "Caught"
    if "bowled" in text:
        return "Bowled"
    if "lbw" in text:
        return "LBW"
    if "run out" in text:
        return "Run out"
    if "stump" in text:
        return "Stumped"
    return "Other"


def is_bowler_wicket_ball(row: pd.Series) -> bool:
    if not layout.parse_bool(row.get("is_wicket")):
        return False
    text = f"{row.get('dismissal_type', '')}".casefold()
    return not any(term in text for term in ["run out", "retired", "obstruct", "timed out"])


def phase_for_model(over: int, model: str) -> str:
    if model == "T20":
        if over <= 6:
            return "Opening"
        if over <= 16:
            return "Middle"
        return "Death"
    if model == "One Day":
        if over <= 10:
            return "Opening"
        if over <= 30:
            return "Middle"
        return "Death"
    return "New Ball" if over <= 15 else "Older Ball"


def best_high_score_from_labels(values: pd.Series) -> str:
    return layout.best_high_score_from_display_values(values)


def best_bbi_from_labels(values: pd.Series) -> str:
    return layout.best_bbi_from_display_values(values)


def divide_or_none(numerator: float, denominator: float) -> float | None:
    return None if not denominator else numerator / denominator


if __name__ == "__main__":
    raise SystemExit(main())
