from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.data.match_centre_ownership import add_club_match_ownership, ensure_club_ownership_columns, is_selected_club_team_name
from src.data.name_normalization import normalize_ground_name, normalize_opponent_club_name
from src.data.playcricket_ingestion import read_processed_table


FVCC_NAME_TOKEN = "fiji victorian"
PLACEHOLDER_PLAYER_NAMES = {"", "nan", "none", "nat", "********", "-"}


def load_player_dna_data(app_root: str | Path) -> dict[str, Any]:
    """Load local processed data for the hidden Player DNA experience.

    This never calls external services. Match-centre data is optional and comes
    from ignored local processed CSVs when they exist.
    """
    root = Path(app_root)
    match_centre_root = root / "data" / "processed" / "match_centre"
    milestone_path = root / "data" / "processed" / "hall_of_fame" / "fastest_batting_milestones.csv"

    aggregate = {
        "batting": read_processed_table("all_seasons_batting"),
        "bowling": read_processed_table("all_seasons_bowling"),
        "fielding": read_processed_table("all_seasons_fielding"),
    }
    aggregate = {key: add_player_key(value) for key, value in aggregate.items()}

    scope = preferred_match_centre_scope(match_centre_root)
    match_centre = load_match_centre_scope(scope) if scope else empty_match_centre_frames()
    match_centre = prepare_match_centre_frames(match_centre)
    milestones = read_csv(milestone_path)
    milestones = add_player_key(milestones, name_columns=["canonical_player_name", "player_name"])

    return {
        "aggregate": aggregate,
        "match_centre": match_centre,
        "milestones": milestones,
        "match_centre_scope": scope.name if scope else "",
    }


def preferred_match_centre_scope(root: Path) -> Path | None:
    if not root.exists():
        return None
    all_available = root / "all_available"
    if (all_available / "all_matches.csv").exists():
        return all_available
    scopes = [
        path
        for path in root.iterdir()
        if path.is_dir() and (path / "all_matches.csv").exists()
    ]
    if not scopes:
        return None
    return sorted(scopes, key=lambda path: path.stat().st_mtime, reverse=True)[0]


def load_match_centre_scope(scope: Path) -> dict[str, pd.DataFrame]:
    names = {
        "matches": "all_matches.csv",
        "innings": "all_match_innings.csv",
        "batting": "all_scorecard_batting.csv",
        "bowling": "all_scorecard_bowling.csv",
        "fielding": "all_scorecard_fielding.csv",
        "fall_of_wickets": "all_fall_of_wickets.csv",
        "ball_by_ball": "all_ball_by_ball.csv",
        "overs": "all_overs.csv",
        "partnerships": "all_partnerships.csv",
        "identity": "player_identity_audit.csv",
    }
    return {key: read_csv(scope / filename) for key, filename in names.items()}


def empty_match_centre_frames() -> dict[str, pd.DataFrame]:
    return {
        "matches": pd.DataFrame(),
        "innings": pd.DataFrame(),
        "batting": pd.DataFrame(),
        "bowling": pd.DataFrame(),
        "fielding": pd.DataFrame(),
        "fall_of_wickets": pd.DataFrame(),
        "ball_by_ball": pd.DataFrame(),
        "overs": pd.DataFrame(),
        "partnerships": pd.DataFrame(),
        "identity": pd.DataFrame(),
    }


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def prepare_match_centre_frames(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    matches = prepare_matches(frames.get("matches", pd.DataFrame()))
    innings = frames.get("innings", pd.DataFrame()).copy()
    identity = prepare_identity(frames.get("identity", pd.DataFrame()))
    batting = add_match_context(frames.get("batting", pd.DataFrame()), matches)
    bowling = add_match_context(frames.get("bowling", pd.DataFrame()), matches)
    fielding = add_match_context(frames.get("fielding", pd.DataFrame()), matches)
    batting = add_identity_context(batting, identity)
    bowling = add_identity_context(bowling, identity)
    fielding = add_identity_context(fielding, identity)
    batting = calculate_team_run_contribution(batting, innings)
    bowling = calculate_wicket_share(bowling, innings)
    return {
        "matches": matches,
        "innings": innings,
        "batting": batting,
        "bowling": bowling,
        "fielding": fielding,
        "fall_of_wickets": frames.get("fall_of_wickets", pd.DataFrame()).copy(),
        "ball_by_ball": frames.get("ball_by_ball", pd.DataFrame()).copy(),
        "overs": frames.get("overs", pd.DataFrame()).copy(),
        "partnerships": frames.get("partnerships", pd.DataFrame()).copy(),
        "identity": identity,
    }


def prepare_matches(matches: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return matches.copy()
    output = matches.copy()
    for column in [
        "match_id",
        "home_team_id",
        "away_team_id",
        "home_team_name",
        "away_team_name",
        "venue_name",
        "grade_name",
        "result_text",
        "match_type",
        "first_match_day",
        "season",
    ]:
        if column not in output:
            output[column] = pd.NA
    output["match_date"] = pd.to_datetime(output["first_match_day"], errors="coerce", utc=True)
    output["match_date_display"] = output["match_date"].dt.strftime("%d %b %Y").fillna("")
    output = add_club_match_ownership(output, club_name_token=FVCC_NAME_TOKEN)
    club_is_home = output["home_team_id"].astype(str) == output["club_team_id"].astype(str)
    output["opponent_team_id"] = output["away_team_id"].where(club_is_home, output["home_team_id"])
    output["opponent_name"] = (
        output["away_team_name"].where(club_is_home, output["home_team_name"]).map(normalize_opponent_club_name)
    )
    output["venue_name"] = output["venue_name"].map(normalize_ground_name)
    output["home_away"] = club_is_home.map(lambda value: "Home" if value else "Away")
    output["format"] = output["match_type"].fillna("Unknown")
    return output


def prepare_identity(identity: pd.DataFrame) -> pd.DataFrame:
    if identity.empty:
        return pd.DataFrame(columns=["participant_id", "player_key", "player_display_name", "is_club_player", "is_fvcc_player"])
    output = identity.copy()
    output = ensure_club_ownership_columns(output)
    for column in [
        "participant_id",
        "player_name",
        "player_short_name",
        "is_club_player",
        "existing_player_match_status",
        "existing_canonical_name",
    ]:
        if column not in output:
            output[column] = pd.NA
    output["player_display_name"] = output["existing_canonical_name"].where(
        clean_series(output["existing_canonical_name"]) != "",
        output["player_name"],
    )
    output["player_key"] = output["player_display_name"].map(player_key)
    output = output[output["player_key"] != ""].copy()
    output["is_club_player"] = output["is_club_player"].map(parse_bool)
    output["is_fvcc_player"] = output["is_club_player"]
    return output.drop_duplicates(["participant_id", "player_key"])


def add_match_context(frame: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    output = frame.copy()
    if matches.empty or "match_id" not in output:
        return output
    columns = [
        "match_id",
        "match_date",
        "match_date_display",
        "season",
        "grade_name",
        "venue_name",
        "opponent_name",
        "home_away",
        "format",
        "match_type",
        "result_text",
        "club_team_id",
        "club_team_name",
        "fvcc_team_id",
        "fvcc_team_name",
    ]
    context = matches[[column for column in columns if column in matches]].drop_duplicates("match_id")
    return output.merge(context, on="match_id", how="left")


def add_identity_context(frame: pd.DataFrame, identity: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    output = frame.copy()
    if "participant_id" not in output:
        output["participant_id"] = pd.NA
    if identity.empty:
        output = add_player_key(output)
        output["player_display_name"] = output.get("player_name", output.get("player_short_name", ""))
        return output
    context = identity[
        ["participant_id", "player_key", "player_display_name", "is_club_player", "is_fvcc_player", "existing_player_match_status"]
    ].drop_duplicates("participant_id")
    output = output.merge(context, on="participant_id", how="left")
    fallback_names = output.get("player_name", output.get("player_short_name", pd.Series("", index=output.index)))
    output["player_display_name"] = output["player_display_name"].where(clean_series(output["player_display_name"]) != "", fallback_names)
    output["player_key"] = output["player_key"].where(clean_series(output["player_key"]) != "", output["player_display_name"].map(player_key))
    return output


def add_player_key(frame: pd.DataFrame, name_columns: list[str] | None = None) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    output = frame.copy()
    candidates = name_columns or ["canonical_player_name", "player_name", "player_display_name", "short_name", "player_short_name"]
    name = pd.Series("", index=output.index, dtype="object")
    for column in candidates:
        if column in output:
            cleaned = clean_series(output[column])
            name = name.where(clean_series(name) != "", cleaned)
    output["player_display_name"] = name
    output["player_key"] = name.map(player_key)
    return output


def calculate_team_run_contribution(batting: pd.DataFrame, innings: pd.DataFrame) -> pd.DataFrame:
    if batting.empty:
        return batting.copy()
    output = batting.copy()
    output["runs_scored"] = to_number(output.get("runs_scored"))
    if not innings.empty and {"innings_id", "runs_scored"}.issubset(innings.columns):
        totals = innings.set_index("innings_id")["runs_scored"].to_dict()
        output["team_total"] = output["innings_id"].map(totals)
    else:
        output["team_total"] = pd.NA
    output["team_total"] = to_number(output["team_total"]).where(
        to_number(output["team_total"]) > 0,
        output.groupby("innings_id")["runs_scored"].transform("sum") if "innings_id" in output else output["runs_scored"],
    )
    output["contribution_pct"] = output.apply(lambda row: safe_div(row["runs_scored"] * 100, row["team_total"]) or 0, axis=1)
    return output


def calculate_wicket_share(bowling: pd.DataFrame, innings: pd.DataFrame) -> pd.DataFrame:
    if bowling.empty:
        return bowling.copy()
    output = bowling.copy()
    output["wickets_taken"] = to_number(output.get("wickets_taken"))
    if not innings.empty and {"innings_id", "wickets_fallen"}.issubset(innings.columns):
        wickets = innings.set_index("innings_id")["wickets_fallen"].to_dict()
        output["opposition_wickets"] = output["innings_id"].map(wickets)
    else:
        output["opposition_wickets"] = pd.NA
    output["opposition_wickets"] = to_number(output["opposition_wickets"]).where(
        to_number(output["opposition_wickets"]) > 0,
        output.groupby("innings_id")["wickets_taken"].transform("sum") if "innings_id" in output else output["wickets_taken"],
    )
    output["wicket_share_pct"] = output.apply(lambda row: safe_div(row["wickets_taken"] * 100, row["opposition_wickets"]) or 0, axis=1)
    return output


def player_dna_options(data: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    aggregate = data.get("aggregate", {})
    for frame in [aggregate.get("batting", pd.DataFrame()), aggregate.get("bowling", pd.DataFrame()), aggregate.get("fielding", pd.DataFrame())]:
        if frame.empty:
            continue
        for _, row in frame[["player_key", "player_display_name"]].drop_duplicates().iterrows():
            key = as_text(row.get("player_key"))
            name = clean_text(row.get("player_display_name"))
            if key and name:
                rows.append({"player_key": key, "player_name": name})
    match_centre = data.get("match_centre", {})
    for frame_name in ["batting", "bowling", "fielding"]:
        frame = match_centre.get(frame_name, pd.DataFrame())
        if frame.empty:
            continue
        fvcc = frame[get_fvcc_mask(frame)].copy()
        for _, row in fvcc[["player_key", "player_display_name"]].drop_duplicates().iterrows():
            key = as_text(row.get("player_key"))
            name = clean_text(row.get("player_display_name"))
            if key and name:
                rows.append({"player_key": key, "player_name": name})
    if not rows:
        return pd.DataFrame(columns=["player_key", "player_name", "label"])
    players = pd.DataFrame(rows)
    players = players[players["player_key"] != ""].copy()
    players = players.groupby("player_key", as_index=False).agg({"player_name": first_non_empty})
    players["label"] = players["player_name"]
    return players.sort_values("label", key=lambda values: values.str.casefold()).reset_index(drop=True)


def build_player_dna_profile(data: dict[str, Any], selected_player_key: str) -> dict[str, Any]:
    selected_player_key = as_text(selected_player_key)
    aggregate = selected_aggregate_rows(data.get("aggregate", {}), selected_player_key)
    match_centre = selected_match_centre_rows(data.get("match_centre", {}), selected_player_key)
    milestones = selected_milestones(data.get("milestones", pd.DataFrame()), selected_player_key)
    player_name = resolve_player_name(aggregate, match_centre, milestones)
    summary = calculate_summary(aggregate, match_centre)
    position_splits = calculate_batting_position_splits(match_centre["batting"])
    ground_splits = calculate_ground_splits(match_centre["batting"], match_centre["bowling"])
    opponent_splits = calculate_opponent_splits(match_centre["batting"], match_centre["bowling"])
    hidden = calculate_hidden_best_performances(match_centre["batting"], match_centre["bowling"], milestones)
    fingerprint = calculate_dismissal_fingerprint(match_centre["batting"])
    ball_bonus = calculate_ball_by_ball_bonus(match_centre["batting"], match_centre["bowling"], match_centre["ball_by_ball"], milestones)
    traits = calculate_trait_scores(summary, match_centre, milestones)
    role_badge = calculate_player_role_badges(summary, traits, position_splits, ground_splits, opponent_splits)
    hero = {
        "player_name": player_name,
        "role_badge": role_badge,
        "signature_stat": signature_stat(summary, traits, milestones),
        "best_position": best_position_label(position_splits),
        "best_ground": best_split_label(ground_splits, "ground"),
        "best_opponent": best_split_label(opponent_splits, "opponent"),
        "best_hidden": hidden[0]["title"] if hidden else "Profile building as more data becomes available",
        "scope_note": data.get("match_centre_scope", ""),
    }
    return {
        "player_name": player_name,
        "summary": summary,
        "hero": hero,
        "traits": traits,
        "position_splits": position_splits,
        "ground_splits": ground_splits,
        "opponent_splits": opponent_splits,
        "hidden_performances": hidden,
        "dismissal_fingerprint": fingerprint,
        "ball_bonus": ball_bonus,
        "has_match_centre": any(not match_centre[key].empty for key in ["batting", "bowling", "fielding"]),
        "has_ball_by_ball": not match_centre["ball_by_ball"].empty,
    }


def selected_aggregate_rows(aggregate: dict[str, pd.DataFrame], selected_player_key: str) -> dict[str, pd.DataFrame]:
    output = {}
    for key in ["batting", "bowling", "fielding"]:
        frame = aggregate.get(key, pd.DataFrame())
        output[key] = frame[frame.get("player_key", pd.Series(dtype="object")).astype(str) == selected_player_key].copy() if not frame.empty else pd.DataFrame()
    return output


def selected_match_centre_rows(match_centre: dict[str, pd.DataFrame], selected_player_key: str) -> dict[str, pd.DataFrame]:
    batting = selected_fvcc_rows(match_centre.get("batting", pd.DataFrame()), selected_player_key)
    bowling = selected_fvcc_rows(match_centre.get("bowling", pd.DataFrame()), selected_player_key)
    fielding = selected_fvcc_rows(match_centre.get("fielding", pd.DataFrame()), selected_player_key)
    participant_ids = set()
    for frame in [batting, bowling, fielding]:
        if not frame.empty and "participant_id" in frame:
            participant_ids.update(frame["participant_id"].dropna().astype(str).tolist())
    identity = match_centre.get("identity", pd.DataFrame())
    if not identity.empty:
        participant_ids.update(
            identity.loc[identity.get("player_key", pd.Series(dtype="object")).astype(str) == selected_player_key, "participant_id"]
            .dropna()
            .astype(str)
            .tolist()
        )
    balls = match_centre.get("ball_by_ball", pd.DataFrame()).copy()
    if not balls.empty and participant_ids:
        striker = balls.get("striker_participant_id", pd.Series(dtype="object")).astype(str).isin(participant_ids)
        bowler = balls.get("bowler_participant_id", pd.Series(dtype="object")).astype(str).isin(participant_ids)
        balls = balls[striker | bowler].copy()
    else:
        balls = pd.DataFrame()
    return {
        "batting": batting,
        "bowling": bowling,
        "fielding": fielding,
        "ball_by_ball": balls,
    }


def selected_fvcc_rows(frame: pd.DataFrame, selected_player_key: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows = frame[frame.get("player_key", pd.Series(dtype="object")).astype(str) == selected_player_key].copy()
    if rows.empty:
        return rows
    return rows[get_fvcc_mask(rows)].copy()


def selected_milestones(milestones: pd.DataFrame, selected_player_key: str) -> pd.DataFrame:
    if milestones.empty:
        return pd.DataFrame()
    return milestones[milestones.get("player_key", pd.Series(dtype="object")).astype(str) == selected_player_key].copy()


def calculate_summary(aggregate: dict[str, pd.DataFrame], match_centre: dict[str, pd.DataFrame]) -> dict[str, Any]:
    aggregate_batting = aggregate.get("batting", pd.DataFrame())
    aggregate_bowling = aggregate.get("bowling", pd.DataFrame())
    aggregate_fielding = aggregate.get("fielding", pd.DataFrame())
    batting = match_centre.get("batting", pd.DataFrame())
    bowling = match_centre.get("bowling", pd.DataFrame())
    fielding = match_centre.get("fielding", pd.DataFrame())

    runs = numeric_sum(aggregate_batting, "battingAggregate") or numeric_sum(batting, "runs_scored")
    innings = numeric_sum(aggregate_batting, "battingInnings") or len(batting)
    not_outs = numeric_sum(aggregate_batting, "battingNotOuts")
    outs = max(float(innings) - float(not_outs), 0)
    balls = numeric_sum(aggregate_batting, "battingBallsFaced") or numeric_sum(batting, "balls_faced")
    wickets = numeric_sum(aggregate_bowling, "bowlingWickets") or numeric_sum(bowling, "wickets_taken")
    bowling_runs = numeric_sum(aggregate_bowling, "bowlingRuns") or numeric_sum(bowling, "runs_conceded")
    bowling_balls = numeric_sum(aggregate_bowling, "bowlingBalls") or overs_to_balls_sum(bowling.get("overs_bowled", pd.Series(dtype="object")))
    catches = numeric_sum(aggregate_fielding, "fieldingTotalCatches") or numeric_sum(fielding, "catches")
    stumpings = numeric_sum(aggregate_fielding, "fieldingStumpings") or numeric_sum(fielding, "stumpings")

    return {
        "runs": runs,
        "batting_innings": innings,
        "batting_average": safe_div(runs, outs),
        "strike_rate": safe_div(runs * 100, balls),
        "highest_score": numeric_max(aggregate_batting, "battingHighScore") or numeric_max(batting, "runs_scored"),
        "wickets": wickets,
        "bowling_average": safe_div(bowling_runs, wickets),
        "bowling_economy": safe_div(bowling_runs, bowling_balls / 6) if bowling_balls else None,
        "bowling_strike_rate": safe_div(bowling_balls, wickets),
        "catches": catches,
        "stumpings": stumpings,
        "team_run_contribution": weighted_pct(batting, "runs_scored", "team_total"),
        "avg_team_run_contribution": numeric_mean(batting, "contribution_pct"),
        "wicket_share": weighted_pct(bowling, "wickets_taken", "opposition_wickets"),
        "avg_wicket_share": numeric_mean(bowling, "wicket_share_pct"),
        "match_centre_batting_innings": len(batting),
        "match_centre_bowling_innings": len(bowling),
        "match_centre_fielding_rows": len(fielding),
    }


def calculate_batting_position_splits(batting: pd.DataFrame) -> pd.DataFrame:
    if batting.empty or "bat_order" not in batting:
        return pd.DataFrame()
    rows = batting.copy()
    rows["bat_order"] = to_number(rows["bat_order"]).astype("Int64")
    rows = rows[rows["bat_order"].notna()].copy()
    if rows.empty:
        return pd.DataFrame()
    rows["runs_scored"] = to_number(rows.get("runs_scored"))
    rows["balls_faced"] = to_number(rows.get("balls_faced"))
    rows["outs"] = dismissal_flags(rows).astype(int)
    grouped = rows.groupby("bat_order", as_index=False).agg(
        innings=("match_id", "count"),
        runs=("runs_scored", "sum"),
        outs=("outs", "sum"),
        balls=("balls_faced", "sum"),
        highest_score=("runs_scored", "max"),
        avg_contribution_pct=("contribution_pct", "mean"),
        team_total=("team_total", "sum"),
    )
    grouped["average"] = grouped.apply(lambda row: safe_div(row["runs"], row["outs"]), axis=1)
    grouped["strike_rate"] = grouped.apply(lambda row: safe_div(row["runs"] * 100, row["balls"]), axis=1)
    grouped["total_contribution_pct"] = grouped.apply(lambda row: safe_div(row["runs"] * 100, row["team_total"]) or 0, axis=1)
    grouped["impact_score"] = grouped.apply(
        lambda row: numeric_value(row.get("avg_contribution_pct")) * 1.2
        + numeric_value(row.get("average")) * 0.7
        + min(numeric_value(row.get("innings")), 8) * 2,
        axis=1,
    )
    return grouped.sort_values(["impact_score", "runs"], ascending=[False, False]).reset_index(drop=True)


def calculate_ground_splits(batting: pd.DataFrame, bowling: pd.DataFrame) -> list[dict[str, Any]]:
    return calculate_dimension_splits(batting, bowling, "venue_name", "ground")


def calculate_opponent_splits(batting: pd.DataFrame, bowling: pd.DataFrame) -> list[dict[str, Any]]:
    return calculate_dimension_splits(batting, bowling, "opponent_name", "opponent")


def calculate_dimension_splits(batting: pd.DataFrame, bowling: pd.DataFrame, column: str, label_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not batting.empty and column in batting:
        bat = batting.copy()
        bat[column] = clean_series(bat[column]).replace("", "Unknown")
        bat["runs_scored"] = to_number(bat.get("runs_scored"))
        bat["outs"] = dismissal_flags(bat).astype(int)
        grouped = bat.groupby(column, as_index=False).agg(
            innings=("match_id", "count"),
            runs=("runs_scored", "sum"),
            outs=("outs", "sum"),
            highest=("runs_scored", "max"),
            contribution_pct=("contribution_pct", "mean"),
        )
        grouped["average"] = grouped.apply(lambda row: safe_div(row["runs"], row["outs"]), axis=1)
        for _, row in grouped.iterrows():
            rows.append(
                {
                    label_key: clean_text(row[column], "Unknown"),
                    "mode": "Batting",
                    "primary": int(row["runs"]),
                    "primary_label": "runs",
                    "secondary": f"{format_optional_decimal(row['average'])} avg",
                    "detail": f"HS {int(row['highest'])} | {format_pct(row['contribution_pct'])} contribution",
                    "impact_score": float(row["runs"]) * 0.25 + numeric_value(row.get("contribution_pct")) + float(row["innings"]) * 3,
                }
            )
    if not bowling.empty and column in bowling:
        bowl = bowling.copy()
        bowl[column] = clean_series(bowl[column]).replace("", "Unknown")
        bowl["wickets_taken"] = to_number(bowl.get("wickets_taken"))
        bowl["runs_conceded"] = to_number(bowl.get("runs_conceded"))
        bowl["balls"] = bowl.get("overs_bowled", pd.Series(dtype="object")).map(overs_to_balls)
        grouped = bowl.groupby(column, as_index=False).agg(
            innings=("match_id", "count"),
            wickets=("wickets_taken", "sum"),
            runs_conceded=("runs_conceded", "sum"),
            balls=("balls", "sum"),
            wicket_share_pct=("wicket_share_pct", "mean"),
        )
        grouped["economy"] = grouped.apply(lambda row: safe_div(row["runs_conceded"], row["balls"] / 6), axis=1)
        for _, row in grouped.iterrows():
            rows.append(
                {
                    label_key: clean_text(row[column], "Unknown"),
                    "mode": "Bowling",
                    "primary": int(row["wickets"]),
                    "primary_label": "wickets",
                    "secondary": f"{format_optional_decimal(row['economy'])} econ",
                    "detail": f"{format_pct(row['wicket_share_pct'])} wicket share",
                    "impact_score": float(row["wickets"]) * 14
                    + numeric_value(row.get("wicket_share_pct"))
                    - numeric_value(row.get("economy")) * 2,
                }
            )
    return sorted(rows, key=lambda item: item.get("impact_score", 0), reverse=True)[:5]


def calculate_hidden_best_performances(batting: pd.DataFrame, bowling: pd.DataFrame, milestones: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not batting.empty:
        bat = batting.copy()
        bat["runs_scored"] = to_number(bat.get("runs_scored"))
        bat["contribution_pct"] = to_number(bat.get("contribution_pct"))
        top_contribution = top_row(bat, ["contribution_pct", "runs_scored"], [False, False])
        if top_contribution is not None:
            records.append(performance_record("Highest team-run share", f"{int(top_contribution['runs_scored'])} runs", context_line(top_contribution), format_pct(top_contribution.get("contribution_pct")), "Share of team total"))
        carry = bat.copy()
        carry["next_best"] = carry.apply(lambda row: next_highest_score(bat, row.get("match_id"), row.get("innings_id"), row.get("participant_id")), axis=1)
        carry["carry_margin"] = carry["runs_scored"] - carry["next_best"]
        carry_row = top_row(carry, ["carry_margin", "runs_scored"], [False, False])
        if carry_row is not None and carry_row.get("carry_margin", 0) > 0:
            records.append(performance_record("Biggest carry job", f"{int(carry_row['runs_scored'])} runs", context_line(carry_row), f"+{int(carry_row['carry_margin'])}", "Clear of next-highest teammate"))
        best_score = top_row(bat, ["runs_scored", "contribution_pct"], [False, False])
        if best_score is not None:
            records.append(performance_record("Best score in the sample", f"{int(best_score['runs_scored'])} runs", context_line(best_score), f"HS {int(best_score['runs_scored'])}", "Top match-centre innings"))
    if not milestones.empty:
        fastest_50 = top_row(milestones[milestones.get("balls_to_50").notna()], ["balls_to_50", "final_runs"], [True, False])
        if fastest_50 is not None:
            records.append(performance_record("Fastest verified 50", final_score_label(fastest_50), milestone_context(fastest_50), f"{int(float(fastest_50['balls_to_50']))} balls", "Ball-by-ball verified"))
        fastest_100 = top_row(milestones[milestones.get("balls_to_100").notna()], ["balls_to_100", "final_runs"], [True, False])
        if fastest_100 is not None:
            records.append(performance_record("Fastest verified 100", final_score_label(fastest_100), milestone_context(fastest_100), f"{int(float(fastest_100['balls_to_100']))} balls", "Ball-by-ball verified"))
    if not bowling.empty:
        bowl = bowling.copy()
        bowl["wickets_taken"] = to_number(bowl.get("wickets_taken"))
        bowl["runs_conceded"] = to_number(bowl.get("runs_conceded"))
        bowl["wicket_share_pct"] = to_number(bowl.get("wicket_share_pct"))
        wicket_share = top_row(bowl, ["wicket_share_pct", "wickets_taken"], [False, False])
        if wicket_share is not None and wicket_share.get("wickets_taken", 0) > 0:
            records.append(performance_record("Highest wicket share", bowling_figures(wicket_share), context_line(wicket_share), format_pct(wicket_share.get("wicket_share_pct")), "Share of opposition wickets"))
        best_spell = top_row(bowl, ["wickets_taken", "runs_conceded"], [False, True])
        if best_spell is not None and best_spell.get("wickets_taken", 0) > 0:
            records.append(performance_record("Best wicket-taking spell", bowling_figures(best_spell), context_line(best_spell), bowling_figures(best_spell), "Most wickets in a scorecard spell"))
        bowl["balls"] = bowl.get("overs_bowled", pd.Series(dtype="object")).map(overs_to_balls)
        economy_spell = bowl[bowl["balls"] >= 24].copy()
        economy_spell["economy"] = economy_spell.apply(lambda row: safe_div(row["runs_conceded"], row["balls"] / 6), axis=1)
        economy_row = top_row(economy_spell, ["economy", "wickets_taken"], [True, False])
        if economy_row is not None:
            records.append(performance_record("Best economy spell", bowling_figures(economy_row), context_line(economy_row), f"{float(economy_row['economy']):.2f}", "Minimum 4 overs"))
    return records[:8]


def calculate_dismissal_fingerprint(batting: pd.DataFrame) -> pd.DataFrame:
    if batting.empty:
        return pd.DataFrame(columns=["label", "count", "pct"])
    rows = batting.copy()
    dismissals = rows[dismissal_flags(rows)].copy()
    if dismissals.empty:
        return pd.DataFrame(columns=["label", "count", "pct"])
    dismissals["bucket"] = dismissals.apply(dismissal_bucket, axis=1)
    grouped = dismissals.groupby("bucket", as_index=False).size().rename(columns={"bucket": "label", "size": "count"})
    grouped["pct"] = grouped["count"] / grouped["count"].sum() * 100
    order = {"Caught": 0, "Bowled": 1, "LBW": 2, "Run out": 3, "Stumped": 4, "Other": 5}
    return grouped.sort_values("label", key=lambda values: values.map(order).fillna(99)).reset_index(drop=True)


def calculate_ball_by_ball_bonus(batting: pd.DataFrame, bowling: pd.DataFrame, balls: pd.DataFrame, milestones: pd.DataFrame) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    if not milestones.empty:
        for column, label in [("balls_to_25", "Fastest 25"), ("balls_to_50", "Fastest 50"), ("balls_to_100", "Fastest 100")]:
            if column in milestones and milestones[column].notna().any():
                best = pd.to_numeric(milestones[column], errors="coerce").min()
                if pd.notna(best):
                    cards.append({"label": label, "value": f"{int(best)} balls", "detail": "Verified from ball-by-ball"})
    if balls.empty:
        return cards
    striker_balls = balls[balls.get("striker_participant_id", pd.Series(dtype="object")).astype(str).isin(participant_ids_from_frame(batting))].copy()
    if not striker_balls.empty:
        striker_balls["is_wide"] = to_number(striker_balls.get("wides")) > 0
        faced = striker_balls[~striker_balls["is_wide"]].copy()
        if not faced.empty:
            faced["runs_bat"] = to_number(faced.get("runs_bat"))
            cards.append({"label": "Dot-ball rate", "value": format_pct((faced["runs_bat"] == 0).mean() * 100), "detail": "Balls faced, wides excluded"})
            cards.append({"label": "Boundary rate", "value": format_pct(faced["runs_bat"].isin([4, 6]).mean() * 100), "detail": "4s and 6s per ball faced"})
            acceleration = acceleration_after_20(faced)
            if acceleration is not None:
                cards.append({"label": "After 20 balls", "value": f"{acceleration:.1f} SR", "detail": "Acceleration once set"})
    bowler_balls = balls[balls.get("bowler_participant_id", pd.Series(dtype="object")).astype(str).isin(participant_ids_from_frame(bowling))].copy()
    if not bowler_balls.empty:
        bowler_balls["legal"] = bowler_balls.get("is_legal_delivery", pd.Series(dtype="object")).map(parse_bool)
        legal = bowler_balls[bowler_balls["legal"]].copy()
        if not legal.empty:
            legal["total_runs"] = to_number(legal.get("total_runs"))
            legal["runs_bat"] = to_number(legal.get("runs_bat"))
            cards.append({"label": "Bowling dot rate", "value": format_pct((legal["total_runs"] == 0).mean() * 100), "detail": "Legal balls only"})
            cards.append({"label": "Boundary conceded", "value": format_pct(legal["runs_bat"].isin([4, 6]).mean() * 100), "detail": "Boundaries per legal ball"})
    return cards[:6]


def calculate_trait_scores(summary: dict[str, Any], match_centre: dict[str, pd.DataFrame], milestones: pd.DataFrame) -> list[dict[str, Any]]:
    batting = match_centre.get("batting", pd.DataFrame())
    bowling = match_centre.get("bowling", pd.DataFrame())
    balls = match_centre.get("ball_by_ball", pd.DataFrame())
    traits = [
        trait("Team-run contribution", summary.get("team_run_contribution"), 45, "He contributes a high share of FVCC innings when he scores."),
        trait("Strike rate", summary.get("strike_rate"), 160, "Scoring tempo compared with a high-impact club benchmark."),
        trait("Consistency", consistency_score(batting), 100, "How often starts become meaningful innings."),
    ]
    boundary = batting_boundary_pct(batting, balls)
    if boundary is not None:
        traits.append(trait("Boundary threat", boundary, 18, "Boundaries per ball faced where ball-by-ball exists."))
    fastest = fastest_milestone_score(milestones)
    if fastest is not None:
        traits.append({"category": "Batting", "label": "Fast milestone threat", "score": fastest, "level": score_level(fastest), "description": "Verified speed to 50 or 100 from ball-by-ball."})
    traits.extend(
        [
            trait("Wicket share", summary.get("wicket_share"), 45, "Share of opposition wickets when he bowls.", category="Bowling"),
            inverse_trait("Economy control", summary.get("bowling_economy"), low=3.2, high=7.0, description="Run control across scorecard bowling spells."),
            inverse_trait("Strike impact", summary.get("bowling_strike_rate"), low=18, high=48, description="Balls per wicket from available bowling data."),
        ]
    )
    independent = fielding_independent_wicket_pct(match_centre.get("batting_all", pd.DataFrame()), bowling)
    if independent is not None:
        traits.append(trait("Fielding-independent wickets", independent, 70, "Bowled/LBW style wickets where dismissal detail supports it.", category="Bowling"))
    phase = bowling_dot_pct(bowling, balls)
    if phase is not None:
        traits.append(trait("Phase control", phase, 55, "Dot-ball control from ball-by-ball bowling events.", category="Bowling"))
    extras_rate = bowling_extras_rate(bowling)
    if extras_rate is not None:
        traits.append(inverse_trait("Extras control", extras_rate, low=0.0, high=1.1, description="Wides and no-balls per over from scorecards.", category="Bowling"))
    return [item for item in traits if item.get("score") is not None]


def calculate_player_role_badges(
    summary: dict[str, Any],
    traits: list[dict[str, Any]],
    positions: pd.DataFrame,
    grounds: list[dict[str, Any]],
    opponents: list[dict[str, Any]],
) -> str:
    runs = summary.get("runs") or 0
    wickets = summary.get("wickets") or 0
    contribution = summary.get("team_run_contribution") or 0
    strike_rate = summary.get("strike_rate") or 0
    wicket_share = summary.get("wicket_share") or 0
    economy = summary.get("bowling_economy")
    best_position = int(positions.iloc[0]["bat_order"]) if not positions.empty and pd.notna(positions.iloc[0]["bat_order"]) else None
    if runs >= 300 and wickets >= 15:
        return "All-Round Impact Player"
    if wickets >= 25 and wicket_share >= 32:
        return "Wicket Share Specialist"
    if wickets >= 15 and economy is not None and economy <= 4.5:
        return "Middle Overs Controller"
    if runs >= 250 and strike_rate >= 125 and best_position and best_position <= 3:
        return "Explosive Starter"
    if runs >= 250 and contribution >= 32 and best_position and best_position >= 4:
        return "Middle-Order Rescue Batter"
    if runs >= 250 and contribution >= 30:
        return "Anchor"
    if grounds and grounds[0].get("impact_score", 0) >= 50:
        return "Ground Specialist"
    if opponents and opponents[0].get("impact_score", 0) >= 50:
        return "Opponent Hunter"
    catches = summary.get("catches") or 0
    stumpings = summary.get("stumpings") or 0
    if catches + stumpings >= 15:
        return "Fielding Impact Player"
    return "Profile building as more data becomes available"


def signature_stat(summary: dict[str, Any], traits: list[dict[str, Any]], milestones: pd.DataFrame) -> str:
    if not milestones.empty and "balls_to_100" in milestones and milestones["balls_to_100"].notna().any():
        return f"{int(pd.to_numeric(milestones['balls_to_100'], errors='coerce').min())} balls to 100"
    if not milestones.empty and "balls_to_50" in milestones and milestones["balls_to_50"].notna().any():
        return f"{int(pd.to_numeric(milestones['balls_to_50'], errors='coerce').min())} balls to 50"
    if summary.get("team_run_contribution"):
        return f"{summary['team_run_contribution']:.1f}% team-run share"
    if summary.get("wicket_share"):
        return f"{summary['wicket_share']:.1f}% wicket share"
    if summary.get("runs"):
        return f"{int(summary['runs']):,} career runs"
    if summary.get("wickets"):
        return f"{int(summary['wickets']):,} career wickets"
    return "Profile building"


def trait(label: str, value: Any, elite_at: float, description: str, category: str = "Batting") -> dict[str, Any]:
    if value is None or pd.isna(value):
        return {"category": category, "label": label, "score": None, "level": "N/A", "description": description}
    score = max(0, min(float(value) / elite_at * 100, 100))
    return {"category": category, "label": label, "score": score, "level": score_level(score), "description": description}


def inverse_trait(label: str, value: Any, low: float, high: float, description: str, category: str = "Bowling") -> dict[str, Any]:
    if value is None or pd.isna(value):
        return {"category": category, "label": label, "score": None, "level": "N/A", "description": description}
    score = (high - float(value)) / (high - low) * 100
    score = max(0, min(score, 100))
    return {"category": category, "label": label, "score": score, "level": score_level(score), "description": description}


def score_level(score: float) -> str:
    if score >= 82:
        return "Elite"
    if score >= 64:
        return "Strong"
    if score >= 44:
        return "Emerging"
    return "Building"


def consistency_score(batting: pd.DataFrame) -> float | None:
    if batting.empty:
        return None
    runs = to_number(batting.get("runs_scored"))
    if runs.empty:
        return None
    starts = (runs >= 20).mean() * 100
    conversions = safe_div((runs >= 50).sum() * 100, max((runs >= 20).sum(), 1)) or 0
    return min(starts * 0.65 + conversions * 0.35, 100)


def batting_boundary_pct(batting: pd.DataFrame, balls: pd.DataFrame) -> float | None:
    if batting.empty or balls.empty:
        return None
    participant_ids = participant_ids_from_frame(batting)
    striker = balls[balls.get("striker_participant_id", pd.Series(dtype="object")).astype(str).isin(participant_ids)].copy()
    if striker.empty:
        return None
    striker["is_wide"] = to_number(striker.get("wides")) > 0
    faced = striker[~striker["is_wide"]].copy()
    if faced.empty:
        return None
    return float(to_number(faced.get("runs_bat")).isin([4, 6]).mean() * 100)


def bowling_dot_pct(bowling: pd.DataFrame, balls: pd.DataFrame) -> float | None:
    if bowling.empty or balls.empty:
        return None
    participant_ids = participant_ids_from_frame(bowling)
    bowler = balls[balls.get("bowler_participant_id", pd.Series(dtype="object")).astype(str).isin(participant_ids)].copy()
    if bowler.empty:
        return None
    bowler["legal"] = bowler.get("is_legal_delivery", pd.Series(dtype="object")).map(parse_bool)
    legal = bowler[bowler["legal"]].copy()
    if legal.empty:
        return None
    return float((to_number(legal.get("total_runs")) == 0).mean() * 100)


def bowling_extras_rate(bowling: pd.DataFrame) -> float | None:
    if bowling.empty:
        return None
    balls = bowling.get("overs_bowled", pd.Series(dtype="object")).map(overs_to_balls)
    overs = balls.sum() / 6
    if overs <= 0:
        return None
    extras = to_number(bowling.get("wides")).sum() + to_number(bowling.get("no_balls")).sum()
    return float(extras / overs)


def fastest_milestone_score(milestones: pd.DataFrame) -> float | None:
    if milestones.empty:
        return None
    scores = []
    if "balls_to_50" in milestones and milestones["balls_to_50"].notna().any():
        balls = pd.to_numeric(milestones["balls_to_50"], errors="coerce").min()
        if pd.notna(balls):
            scores.append(max(0, min((50 - float(balls)) / 25 * 100, 100)))
    if "balls_to_100" in milestones and milestones["balls_to_100"].notna().any():
        balls = pd.to_numeric(milestones["balls_to_100"], errors="coerce").min()
        if pd.notna(balls):
            scores.append(max(0, min((90 - float(balls)) / 45 * 100, 100)))
    return max(scores) if scores else None


def fielding_independent_wicket_pct(_batting_all: pd.DataFrame, _bowling: pd.DataFrame) -> float | None:
    # Reserved for a later pass that joins bowler wicket rows back to dismissal types.
    return None


def get_fvcc_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="bool")
    rows = ensure_club_ownership_columns(frame)
    if {"team_id", "club_team_id"}.issubset(rows.columns):
        return rows["team_id"].astype(str) == rows["club_team_id"].astype(str)
    if "is_club_player" in rows and rows["is_club_player"].notna().any():
        return rows["is_club_player"].map(parse_bool)
    if "team_name" in frame:
        return frame["team_name"].map(is_fvcc_team_name)
    return pd.Series([True] * len(frame), index=frame.index)


def best_position_label(positions: pd.DataFrame) -> str:
    if positions.empty:
        return "Not enough scorecard innings yet"
    row = positions.iloc[0]
    return f"No. {int(row['bat_order'])} ({format_optional_decimal(row.get('average'))} avg)"


def best_split_label(items: list[dict[str, Any]], key: str) -> str:
    if not items:
        return "Not enough match-centre data yet"
    return clean_text(items[0].get(key), "Unknown")


def performance_record(title: str, subtitle: str, context: str, value: str, explanation: str) -> dict[str, str]:
    return {
        "title": title,
        "subtitle": subtitle,
        "context": context,
        "value": value,
        "explanation": explanation,
    }


def context_line(row: pd.Series) -> str:
    parts = [row.get("opponent_name"), row.get("venue_name"), row.get("season")]
    return " | ".join([clean_text(part) for part in parts if clean_text(part)])


def milestone_context(row: pd.Series) -> str:
    parts = [row.get("opposition_team"), row.get("venue_name"), row.get("season")]
    return " | ".join([clean_text(part) for part in parts if clean_text(part)])


def final_score_label(row: pd.Series) -> str:
    display = clean_text(row.get("final_score_display"))
    if display:
        return f"{display} runs"
    final_runs = safe_int(row.get("final_runs"))
    return f"{final_runs} runs" if final_runs is not None else "Verified milestone"


def bowling_figures(row: pd.Series) -> str:
    wickets = safe_int(row.get("wickets_taken")) or 0
    runs = safe_int(row.get("runs_conceded")) or 0
    return f"{wickets}/{runs}"


def top_row(frame: pd.DataFrame, columns: list[str], ascending: list[bool]) -> pd.Series | None:
    if frame.empty:
        return None
    rows = frame.copy()
    usable_columns = [column for column in columns if column in rows]
    if not usable_columns:
        return None
    for column in usable_columns:
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    rows = rows.dropna(subset=[usable_columns[0]])
    if rows.empty:
        return None
    return rows.sort_values(usable_columns, ascending=ascending[: len(usable_columns)]).iloc[0]


def next_highest_score(batting: pd.DataFrame, match_id: Any, innings_id: Any, participant_id: Any) -> float:
    if batting.empty:
        return 0
    peers = batting[
        (batting.get("match_id", pd.Series(dtype="object")).astype(str) == as_text(match_id))
        & (batting.get("innings_id", pd.Series(dtype="object")).astype(str) == as_text(innings_id))
        & (batting.get("participant_id", pd.Series(dtype="object")).astype(str) != as_text(participant_id))
    ]
    if peers.empty:
        return 0
    return float(to_number(peers.get("runs_scored")).max())


def dismissal_flags(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="bool")
    text = clean_series(frame.get("dismissal_type", pd.Series("", index=frame.index)))
    fallback = clean_series(frame.get("dismissal_text", pd.Series("", index=frame.index)))
    combined = text.where(text != "", fallback).str.casefold()
    not_out = combined.isin({"", "not out", "retired not out", "retired hurt"})
    return ~not_out


def dismissal_bucket(row: pd.Series) -> str:
    text = f"{clean_text(row.get('dismissal_type'))} {clean_text(row.get('dismissal_text'))}".casefold()
    if "caught" in text or text.startswith("c "):
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


def participant_ids_from_frame(frame: pd.DataFrame) -> set[str]:
    if frame.empty or "participant_id" not in frame:
        return set()
    return set(frame["participant_id"].dropna().astype(str).tolist())


def acceleration_after_20(faced: pd.DataFrame) -> float | None:
    if faced.empty:
        return None
    rows = faced.sort_values(["match_id", "innings_id", "over_number", "ball_number"]).copy()
    values = []
    for _, group in rows.groupby(["match_id", "innings_id"], dropna=False):
        group = group.copy()
        group["ball_index"] = range(1, len(group) + 1)
        after = group[group["ball_index"] > 20]
        if not after.empty:
            values.append(safe_div(to_number(after.get("runs_bat")).sum() * 100, len(after)))
    values = [value for value in values if value is not None]
    return float(sum(values) / len(values)) if values else None


def weighted_pct(frame: pd.DataFrame, numerator: str, denominator: str) -> float | None:
    if frame.empty or numerator not in frame or denominator not in frame:
        return None
    den = to_number(frame[denominator]).sum()
    if den <= 0:
        return None
    return float(to_number(frame[numerator]).sum() / den * 100)


def numeric_sum(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame:
        return 0
    return float(to_number(frame[column]).sum())


def numeric_mean(frame: pd.DataFrame, column: str) -> float | None:
    if frame.empty or column not in frame:
        return None
    values = to_number(frame[column])
    return float(values.mean()) if values.notna().any() else None


def numeric_max(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame:
        return 0
    values = to_number(frame[column])
    return float(values.max()) if values.notna().any() else 0


def overs_to_balls_sum(values: pd.Series) -> int:
    if values.empty:
        return 0
    return int(values.map(overs_to_balls).sum())


def overs_to_balls(value: Any) -> int:
    if value is None or pd.isna(value):
        return 0
    text = str(value).strip()
    if not text:
        return 0
    try:
        if "." in text:
            overs, balls = text.split(".", 1)
            return int(float(overs or 0)) * 6 + int(float(balls or 0))
        return int(float(text) * 6)
    except ValueError:
        return 0


def safe_div(numerator: float, denominator: float) -> float | None:
    if denominator is None or pd.isna(denominator) or float(denominator) == 0:
        return None
    return float(numerator) / float(denominator)


def safe_int(value: Any) -> int | None:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    return int(round(float(numeric)))


def numeric_value(value: Any) -> float:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return 0.0
    return float(numeric)


def to_number(values: Any) -> pd.Series:
    if isinstance(values, pd.Series):
        return pd.to_numeric(values, errors="coerce").fillna(0)
    return pd.Series(pd.to_numeric(values, errors="coerce")).fillna(0)


def format_pct(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.1f}%"


def format_optional_decimal(value: Any) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    return f"{float(value):.2f}"


def clean_series(values: pd.Series) -> pd.Series:
    return values.fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip()


def clean_text(value: Any, fallback: str = "") -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).replace("\n", " ").strip()
    text = " ".join(text.split())
    if text.casefold() in PLACEHOLDER_PLAYER_NAMES or text.casefold().startswith("unknown player"):
        return fallback
    return text


def player_key(value: Any) -> str:
    text = clean_text(value).casefold()
    if not text:
        return ""
    return " ".join(text.split())


def is_fvcc_team_name(value: Any) -> bool:
    return is_selected_club_team_name(value, FVCC_NAME_TOKEN)


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes"}


def as_text(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value)


def first_non_empty(values: pd.Series) -> str:
    for value in values:
        text = clean_text(value)
        if text:
            return text
    return ""


def resolve_player_name(
    aggregate: dict[str, pd.DataFrame],
    match_centre: dict[str, pd.DataFrame],
    milestones: pd.DataFrame,
) -> str:
    for frame in [
        aggregate.get("batting", pd.DataFrame()),
        aggregate.get("bowling", pd.DataFrame()),
        aggregate.get("fielding", pd.DataFrame()),
        match_centre.get("batting", pd.DataFrame()),
        match_centre.get("bowling", pd.DataFrame()),
        match_centre.get("fielding", pd.DataFrame()),
        milestones,
    ]:
        if frame.empty:
            continue
        for column in ["player_display_name", "canonical_player_name", "player_name"]:
            if column in frame:
                name = first_non_empty(frame[column])
                if name:
                    return name
    return "Unknown player"
