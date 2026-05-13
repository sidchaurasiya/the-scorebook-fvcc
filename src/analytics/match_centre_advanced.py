from __future__ import annotations

from typing import Any

import pandas as pd

from src.data.name_normalization import normalize_ground_name, normalize_opponent_club_name


def prepare_match_centre_frames(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    matches = build_match_context(data.get("matches", pd.DataFrame()))
    innings = data.get("match_innings", pd.DataFrame()).copy()
    batting = add_match_context(data.get("scorecard_batting", pd.DataFrame()), matches)
    bowling = add_match_context(data.get("scorecard_bowling", pd.DataFrame()), matches)
    batting = calculate_batting_contribution_percentage(batting, innings)
    bowling = calculate_bowling_wicket_contribution_percentage(bowling, innings)
    return {
        "matches": matches,
        "innings": innings,
        "batting": batting,
        "bowling": bowling,
        "ball_by_ball": data.get("ball_by_ball", pd.DataFrame()).copy(),
        "overs": data.get("overs", pd.DataFrame()).copy(),
    }


def build_match_context(matches: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return matches.copy()
    output = matches.copy()
    for column in [
        "home_team_id",
        "away_team_id",
        "home_team_name",
        "away_team_name",
        "venue_name",
        "result_text",
        "match_type",
        "first_match_day",
    ]:
        if column not in output:
            output[column] = pd.NA
    output["match_date"] = pd.to_datetime(output["first_match_day"], errors="coerce", utc=True)
    output["match_date_display"] = output["match_date"].dt.strftime("%d %b %Y").fillna("Date TBC")
    fvcc_is_home = output["home_team_name"].map(is_fvcc_team_name)
    output["fvcc_team_id"] = output["home_team_id"].where(fvcc_is_home, output["away_team_id"])
    output["fvcc_team_name"] = output["home_team_name"].where(fvcc_is_home, output["away_team_name"])
    output["opponent_team_id"] = output["away_team_id"].where(fvcc_is_home, output["home_team_id"])
    output["opponent_name"] = (
        output["away_team_name"].where(fvcc_is_home, output["home_team_name"]).map(normalize_opponent_club_name)
    )
    output["venue_name"] = output["venue_name"].map(normalize_ground_name)
    output["home_away"] = fvcc_is_home.map(lambda value: "Home" if value else "Away")
    output["format"] = output["match_type"].fillna("Unknown")
    return output


def player_options(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for source in ["batting", "bowling"]:
        frame = frames.get(source, pd.DataFrame())
        if frame.empty:
            continue
        frame = frame[frame.get("team_id", pd.Series(dtype="object")).astype(str) == frame.get("fvcc_team_id", pd.Series(dtype="object")).astype(str)]
        for _, row in frame.iterrows():
            participant_id = as_text(row.get("participant_id"))
            player_name = as_text(row.get("player_name") or row.get("player_short_name"))
            if not participant_id and not player_name:
                continue
            rows.append({"participant_id": participant_id, "player_name": player_name})
    if not rows:
        return pd.DataFrame(columns=["participant_id", "player_name", "label"])
    players = pd.DataFrame(rows).drop_duplicates()
    players = players.groupby("participant_id", as_index=False).agg({"player_name": first_non_empty})
    players["label"] = players["player_name"].where(players["player_name"].astype(str).str.strip() != "", players["participant_id"])
    duplicate_labels = players["label"].duplicated(keep=False)
    players.loc[duplicate_labels, "label"] = players.loc[duplicate_labels].apply(
        lambda row: f"{row['label']} ({str(row['participant_id'])[-4:]})",
        axis=1,
    )
    return players.sort_values("label")


def selected_player_rows(frames: dict[str, pd.DataFrame], participant_id: str) -> dict[str, pd.DataFrame]:
    batting = frames["batting"]
    bowling = frames["bowling"]
    ball_by_ball = frames["ball_by_ball"]
    fvcc_batting = batting[(batting.get("participant_id", pd.Series(dtype="object")).astype(str) == participant_id)]
    fvcc_batting = fvcc_batting[fvcc_batting.get("team_id", pd.Series(dtype="object")).astype(str) == fvcc_batting.get("fvcc_team_id", pd.Series(dtype="object")).astype(str)]
    fvcc_bowling = bowling[(bowling.get("participant_id", pd.Series(dtype="object")).astype(str) == participant_id)]
    fvcc_bowling = fvcc_bowling[fvcc_bowling.get("team_id", pd.Series(dtype="object")).astype(str) == fvcc_bowling.get("fvcc_team_id", pd.Series(dtype="object")).astype(str)]
    player_balls = pd.DataFrame()
    if not ball_by_ball.empty:
        striker = ball_by_ball.get("striker_participant_id", pd.Series(dtype="object")).astype(str) == participant_id
        bowler = ball_by_ball.get("bowler_participant_id", pd.Series(dtype="object")).astype(str) == participant_id
        player_balls = ball_by_ball[striker | bowler].copy()
    return {"batting": fvcc_batting.copy(), "bowling": fvcc_bowling.copy(), "ball_by_ball": player_balls}


def player_summary(rows: dict[str, pd.DataFrame]) -> dict[str, Any]:
    batting = rows["batting"].copy()
    bowling = rows["bowling"].copy()
    runs = numeric_sum(batting, "runs_scored")
    balls = numeric_sum(batting, "balls_faced")
    outs = int(dismissal_flags(batting).sum()) if not batting.empty else 0
    wickets = numeric_sum(bowling, "wickets_taken")
    runs_conceded = numeric_sum(bowling, "runs_conceded")
    bowling_balls = overs_to_balls_sum(bowling.get("overs_bowled", pd.Series(dtype="object"))) if not bowling.empty else 0
    return {
        "Total runs": runs,
        "Batting innings": len(batting),
        "Batting average": safe_div(runs, outs),
        "Strike rate": safe_div(runs * 100, balls),
        "Highest score": numeric_max(batting, "runs_scored"),
        "Total wickets": wickets,
        "Bowling innings": len(bowling),
        "Bowling average": safe_div(runs_conceded, wickets),
        "Economy": safe_div(runs_conceded, bowling_balls / 6) if bowling_balls else None,
        "Best bowling": best_bowling_label(bowling),
        "Batting team-run contribution %": weighted_contribution(batting, "runs_scored", "team_total"),
        "Bowling wicket contribution %": weighted_contribution(bowling, "wickets_taken", "opposition_wickets"),
    }


def calculate_batting_splits(batting: pd.DataFrame, ball_by_ball: pd.DataFrame, group_column: str, label: str) -> pd.DataFrame:
    if batting.empty:
        return pd.DataFrame()
    rows = batting.copy()
    rows[group_column] = rows.get(group_column, "Unknown").fillna("Unknown")
    rows["outs"] = dismissal_flags(rows).astype(int)
    rows["balls_faced"] = pd.to_numeric(rows.get("balls_faced"), errors="coerce").fillna(0)
    rows["runs_scored"] = pd.to_numeric(rows.get("runs_scored"), errors="coerce").fillna(0)
    rows["fours_scored"] = pd.to_numeric(rows.get("fours_scored"), errors="coerce").fillna(0)
    rows["sixes_scored"] = pd.to_numeric(rows.get("sixes_scored"), errors="coerce").fillna(0)
    grouped = rows.groupby(group_column, dropna=False).agg(
        Innings=("match_id", "count"),
        Runs=("runs_scored", "sum"),
        Outs=("outs", "sum"),
        Balls=("balls_faced", "sum"),
        **{"4s": ("fours_scored", "sum"), "6s": ("sixes_scored", "sum")},
        Highest=("runs_scored", "max"),
        team_total_sum=("team_total", "sum"),
        **{"Avg team-run contribution %": ("contribution_pct", "mean")},
    ).reset_index()
    grouped["Average"] = grouped.apply(lambda row: safe_div(row["Runs"], row["Outs"]), axis=1)
    grouped["Strike rate"] = grouped.apply(lambda row: safe_div(row["Runs"] * 100, row["Balls"]), axis=1)
    grouped["Total team-run contribution %"] = grouped.apply(lambda row: safe_div(row["Runs"] * 100, row["team_total_sum"]) or 0, axis=1)
    ball_metrics = batting_ball_metrics(ball_by_ball, rows, group_column)
    grouped = grouped.merge(ball_metrics, on=group_column, how="left")
    grouped = grouped.rename(columns={group_column: label, "Balls": "Balls faced", "Highest": "Highest score"})
    return grouped[
        [label, "Innings", "Runs", "Outs", "Average", "Strike rate", "Highest score", "Balls faced", "4s", "6s", "Dot %", "Boundary %", "Avg team-run contribution %", "Total team-run contribution %"]
    ]


def calculate_bowling_splits(bowling: pd.DataFrame, group_column: str, label: str) -> pd.DataFrame:
    if bowling.empty:
        return pd.DataFrame()
    rows = bowling.copy()
    rows[group_column] = rows.get(group_column, "Unknown").fillna("Unknown")
    for column in ["wickets_taken", "runs_conceded"]:
        rows[column] = pd.to_numeric(rows.get(column), errors="coerce").fillna(0)
    rows["balls"] = rows.get("overs_bowled", pd.Series(dtype="object")).map(overs_to_balls)
    grouped = rows.groupby(group_column, dropna=False).agg(
        Innings=("match_id", "count"),
        Balls=("balls", "sum"),
        Wickets=("wickets_taken", "sum"),
        **{"Runs conceded": ("runs_conceded", "sum"), "Wicket contribution %": ("wicket_contribution_pct", "mean")},
    ).reset_index()
    grouped["Overs"] = grouped["Balls"].map(format_balls_as_overs)
    grouped["Average"] = grouped.apply(lambda row: safe_div(row["Runs conceded"], row["Wickets"]), axis=1)
    grouped["Economy"] = grouped.apply(lambda row: safe_div(row["Runs conceded"], row["Balls"] / 6), axis=1)
    grouped["Strike rate"] = grouped.apply(lambda row: safe_div(row["Balls"], row["Wickets"]), axis=1)
    best_labels = rows.groupby(group_column).apply(best_bowling_label).rename("Best bowling").reset_index()
    grouped = grouped.merge(best_labels, on=group_column, how="left")
    grouped = grouped.rename(columns={group_column: label})
    return grouped[[label, "Innings", "Overs", "Wickets", "Runs conceded", "Average", "Economy", "Strike rate", "Best bowling", "Wicket contribution %"]]


def bowling_phase_splits(ball_by_ball: pd.DataFrame, matches: pd.DataFrame, participant_id: str) -> pd.DataFrame:
    if ball_by_ball.empty:
        return pd.DataFrame()
    balls = ball_by_ball[ball_by_ball.get("bowler_participant_id", pd.Series(dtype="object")).astype(str) == participant_id].copy()
    if balls.empty:
        return pd.DataFrame()
    balls["over_number"] = pd.to_numeric(balls.get("over_number"), errors="coerce").fillna(0)
    innings_lengths = balls.groupby(["match_id", "innings_id"])["over_number"].max().add(1).to_dict()
    match_types = matches.set_index("match_id")["match_type"].to_dict() if not matches.empty and "match_type" in matches else {}
    balls["Phase"] = balls.apply(lambda row: assign_bowling_phase(row, innings_lengths, match_types), axis=1)
    balls["legal"] = balls.get("is_legal_delivery", pd.Series(dtype="object")).map(parse_bool)
    balls["dot"] = balls["legal"] & (pd.to_numeric(balls.get("total_runs"), errors="coerce").fillna(0) == 0)
    balls["boundary"] = balls["legal"] & pd.to_numeric(balls.get("runs_bat"), errors="coerce").fillna(0).isin([4, 6])
    balls["extras"] = sum_numeric_columns(balls, ["wides", "no_balls", "leg_byes", "byes", "penalty_runs"])
    balls["runs"] = pd.to_numeric(balls.get("total_runs"), errors="coerce").fillna(0)
    balls["wicket"] = balls.get("is_wicket", pd.Series(dtype="object")).map(parse_bool)
    grouped = balls.groupby("Phase", as_index=False).agg(
        Balls=("legal", "sum"),
        **{"Runs conceded": ("runs", "sum"), "Wickets": ("wicket", "sum"), "Dot %": ("dot", "mean"), "Boundary conceded %": ("boundary", "mean"), "Extras": ("extras", "sum")},
    )
    grouped["Overs"] = grouped["Balls"].map(format_balls_as_overs)
    grouped["Average"] = grouped.apply(lambda row: safe_div(row["Runs conceded"], row["Wickets"]), axis=1)
    grouped["Economy"] = grouped.apply(lambda row: safe_div(row["Runs conceded"], row["Balls"] / 6), axis=1)
    grouped["Strike rate"] = grouped.apply(lambda row: safe_div(row["Balls"], row["Wickets"]), axis=1)
    grouped["Wicket contribution %"] = None
    grouped["Dot %"] = grouped["Dot %"] * 100
    grouped["Boundary conceded %"] = grouped["Boundary conceded %"] * 100
    order = {"Opening overs": 0, "Middle overs": 1, "Death overs": 2}
    return grouped.sort_values("Phase", key=lambda values: values.map(order)).reset_index(drop=True)


def assign_bowling_phase(row: pd.Series, innings_lengths: dict[tuple[str, str], float], match_types: dict[str, str]) -> str:
    """Assign a bowling phase from zero-based over numbers and innings length when available."""
    over = int(float(row.get("over_number", 0))) + 1
    match_id = as_text(row.get("match_id"))
    innings_id = as_text(row.get("innings_id"))
    innings_length = innings_lengths.get((match_id, innings_id))
    match_type = as_text(match_types.get(match_id)).casefold()
    if "t20" in match_type or (innings_length is not None and innings_length <= 20):
        if over <= 6:
            return "Opening overs"
        if over <= 15:
            return "Middle overs"
        return "Death overs"
    if innings_length is None or pd.isna(innings_length):
        if over <= 10:
            return "Opening overs"
        if over <= 30:
            return "Middle overs"
        return "Death overs"
    if over <= 10:
        return "Opening overs"
    if over > max(float(innings_length) - 10, 10):
        return "Death overs"
    return "Middle overs"


def calculate_fastest_milestones(batting: pd.DataFrame, ball_by_ball: pd.DataFrame, participant_id: str) -> pd.DataFrame:
    if batting.empty or ball_by_ball.empty:
        return pd.DataFrame()
    balls = ball_by_ball[ball_by_ball.get("striker_participant_id", pd.Series(dtype="object")).astype(str) == participant_id].copy()
    if balls.empty:
        return pd.DataFrame()
    balls["runs_bat"] = pd.to_numeric(balls.get("runs_bat"), errors="coerce").fillna(0)
    balls["legal"] = balls.get("is_legal_delivery", pd.Series(dtype="object")).map(parse_bool).astype(int)
    rows = []
    context = batting.set_index("innings_id", drop=False).to_dict("index") if "innings_id" in batting else {}
    for innings_id, group in balls.groupby("innings_id", dropna=False):
        group = group.sort_values(["over_number", "ball_number"])
        group["score"] = group["runs_bat"].cumsum()
        group["balls"] = group["legal"].cumsum()
        ctx = context.get(innings_id, {})
        rows.append(
            {
                "Match date": ctx.get("match_date_display", ""),
                "Opposition": ctx.get("opponent_name", ""),
                "Venue": ctx.get("venue_name", ""),
                "Final score": int(pd.to_numeric(ctx.get("runs_scored"), errors="coerce")) if pd.notna(ctx.get("runs_scored")) else None,
                "Balls to 50": milestone_ball(group, 50),
                "Balls to 100": milestone_ball(group, 100),
                "Final balls faced": int(group["legal"].sum()),
                "Strike rate": safe_div(group["runs_bat"].sum() * 100, group["legal"].sum()),
                "Team-run contribution %": ctx.get("contribution_pct"),
                "Result": ctx.get("result_text", ""),
            }
        )
    output = pd.DataFrame(rows)
    if output.empty:
        return output
    return output[output["Balls to 50"].notna() | output["Balls to 100"].notna()].sort_values(["Balls to 50", "Balls to 100"], na_position="last")


def calculate_best_hidden_performances(batting: pd.DataFrame, bowling: pd.DataFrame, ball_by_ball: pd.DataFrame, participant_id: str) -> pd.DataFrame:
    rows = []
    if not batting.empty:
        top_contribution = batting.sort_values("contribution_pct", ascending=False).head(1)
        if not top_contribution.empty:
            row = top_contribution.iloc[0]
            rows.append({"Type": "Batting", "Insight": "Highest team-run contribution", "Performance": f"{int(row['runs_scored'])} runs ({row['contribution_pct']:.1f}%)", "Context": context_label(row)})
        carry = batting.copy()
        carry["carry_margin"] = carry.apply(lambda row: row.get("runs_scored", 0) - next_highest_score(batting, row.get("match_id"), row.get("innings_id"), row.get("participant_id")), axis=1)
        if not carry.empty:
            row = carry.sort_values("carry_margin", ascending=False).iloc[0]
            rows.append({"Type": "Batting", "Insight": "Biggest carry job", "Performance": f"+{int(row['carry_margin'])} over next-highest", "Context": context_label(row)})
        sr = batting[pd.to_numeric(batting.get("balls_faced"), errors="coerce").fillna(0) >= 20].copy()
        if not sr.empty:
            row = sr.sort_values("strike_rate", ascending=False).iloc[0]
            rows.append({"Type": "Batting", "Insight": "Best strike-rate innings (20+ balls)", "Performance": f"{row['strike_rate']:.2f} SR", "Context": context_label(row)})
    if not bowling.empty:
        for insight, sort_cols, ascending, detail in [
            ("Best wicket contribution", ["wicket_contribution_pct"], [False], lambda r: f"{r['wicket_contribution_pct']:.1f}% of wickets"),
            ("Best economy spell (4+ overs)", ["economy"], [True], lambda r: f"{r['economy']:.2f} economy"),
            ("Best spell by wickets", ["wickets_taken", "runs_conceded"], [False, True], lambda r: f"{int(r['wickets_taken'])}/{int(r['runs_conceded'])}"),
        ]:
            source = bowling.copy()
            if "4+ overs" in insight:
                source = source[pd.to_numeric(source.get("overs_bowled"), errors="coerce").fillna(0) >= 4]
            if not source.empty:
                row = source.sort_values(sort_cols, ascending=ascending).iloc[0]
                rows.append({"Type": "Bowling", "Insight": insight, "Performance": detail(row), "Context": context_label(row)})
        phase = bowling_phase_splits(ball_by_ball, pd.DataFrame(), participant_id)
        if not phase.empty:
            row = phase.sort_values(["Wickets", "Dot %"], ascending=[False, False]).iloc[0]
            rows.append({"Type": "Bowling", "Insight": "Best phase spell", "Performance": f"{int(row['Wickets'])} wickets in {row['Phase']}", "Context": f"{row['Dot %']:.1f}% dots"})
    return pd.DataFrame(rows)


def calculate_batting_contribution_percentage(batting: pd.DataFrame, innings: pd.DataFrame) -> pd.DataFrame:
    if batting.empty:
        return batting.copy()
    output = batting.copy()
    output["runs_scored"] = pd.to_numeric(output.get("runs_scored"), errors="coerce").fillna(0)
    totals = innings.set_index("innings_id")["runs_scored"].to_dict() if not innings.empty and "innings_id" in innings else {}
    output["team_total"] = output["innings_id"].map(totals).fillna(output.groupby("innings_id")["runs_scored"].transform("sum"))
    output["contribution_pct"] = output.apply(lambda row: safe_div(row["runs_scored"] * 100, row["team_total"]) or 0, axis=1)
    return output


def calculate_bowling_wicket_contribution_percentage(bowling: pd.DataFrame, innings: pd.DataFrame) -> pd.DataFrame:
    if bowling.empty:
        return bowling.copy()
    output = bowling.copy()
    output["wickets_taken"] = pd.to_numeric(output.get("wickets_taken"), errors="coerce").fillna(0)
    wickets = innings.set_index("innings_id")["wickets_fallen"].to_dict() if not innings.empty and "innings_id" in innings else {}
    output["opposition_wickets"] = output["innings_id"].map(wickets).fillna(output.groupby("innings_id")["wickets_taken"].transform("sum"))
    output["wicket_contribution_pct"] = output.apply(lambda row: safe_div(row["wickets_taken"] * 100, row["opposition_wickets"]) or 0, axis=1)
    return output


def add_match_context(frame: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or matches.empty or "match_id" not in frame:
        return frame.copy()
    columns = ["match_id", "match_date_display", "fvcc_team_id", "opponent_name", "venue_name", "home_away", "format", "match_type", "result_text"]
    return frame.merge(matches[[column for column in columns if column in matches]].drop_duplicates("match_id"), on="match_id", how="left")


def batting_ball_metrics(ball_by_ball: pd.DataFrame, batting: pd.DataFrame, group_column: str) -> pd.DataFrame:
    if ball_by_ball.empty or batting.empty:
        return pd.DataFrame(columns=[group_column, "Dot %", "Boundary %"])
    keys = batting[["innings_id", "participant_id", group_column]].drop_duplicates()
    balls = ball_by_ball.merge(keys, left_on=["innings_id", "striker_participant_id"], right_on=["innings_id", "participant_id"], how="inner")
    if balls.empty:
        return pd.DataFrame(columns=[group_column, "Dot %", "Boundary %"])
    balls["legal"] = balls.get("is_legal_delivery", pd.Series(dtype="object")).map(parse_bool)
    balls = balls[balls["legal"]].copy()
    balls["dot"] = pd.to_numeric(balls.get("runs_bat"), errors="coerce").fillna(0) == 0
    balls["boundary"] = pd.to_numeric(balls.get("runs_bat"), errors="coerce").fillna(0).isin([4, 6])
    return balls.groupby(group_column, as_index=False).agg(**{"Dot %": ("dot", lambda s: s.mean() * 100), "Boundary %": ("boundary", lambda s: s.mean() * 100)})


def best_bowling_label(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "N/A"
    rows = frame.copy()
    rows["wickets_taken"] = pd.to_numeric(rows.get("wickets_taken"), errors="coerce").fillna(0)
    rows["runs_conceded"] = pd.to_numeric(rows.get("runs_conceded"), errors="coerce").fillna(0)
    best = rows.sort_values(["wickets_taken", "runs_conceded"], ascending=[False, True]).iloc[0]
    return f"{int(best['wickets_taken'])}/{int(best['runs_conceded'])}"


def dismissal_flags(frame: pd.DataFrame) -> pd.Series:
    if frame.empty or "dismissal_type" not in frame:
        return pd.Series([False] * len(frame), index=frame.index)
    values = frame["dismissal_type"].fillna("").astype(str).str.casefold().str.strip()
    return (values != "") & ~values.isin({"not out", "retired not out", "retired hurt"})


def weighted_contribution(frame: pd.DataFrame, numerator: str, denominator: str) -> float | None:
    if frame.empty or numerator not in frame or denominator not in frame:
        return None
    total_denominator = pd.to_numeric(frame[denominator], errors="coerce").fillna(0).sum()
    if total_denominator <= 0:
        return None
    return float(pd.to_numeric(frame[numerator], errors="coerce").fillna(0).sum() / total_denominator * 100)


def contribution_total_proxy(values: pd.Series) -> float:
    return float(pd.to_numeric(values, errors="coerce").fillna(0).sum())


def milestone_ball(group: pd.DataFrame, milestone: int) -> float | None:
    reached = group[group["score"] >= milestone]
    if reached.empty:
        return None
    return float(reached.iloc[0]["balls"])


def next_highest_score(batting: pd.DataFrame, match_id: object, innings_id: object, participant_id: object) -> float:
    peers = batting[(batting["match_id"] == match_id) & (batting["innings_id"] == innings_id) & (batting["participant_id"] != participant_id)]
    if peers.empty:
        return 0
    return float(pd.to_numeric(peers.get("runs_scored"), errors="coerce").fillna(0).max())


def context_label(row: pd.Series) -> str:
    return " | ".join([as_text(row.get("opponent_name")), as_text(row.get("venue_name"))]).strip(" |")


def sum_numeric_columns(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    total = pd.Series([0] * len(frame), index=frame.index, dtype="float64")
    for column in columns:
        if column in frame:
            total = total + pd.to_numeric(frame[column], errors="coerce").fillna(0)
    return total


def numeric_sum(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame:
        return 0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0).sum())


def numeric_max(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame:
        return 0
    values = pd.to_numeric(frame[column], errors="coerce")
    return float(values.max()) if values.notna().any() else 0


def overs_to_balls_sum(values: pd.Series) -> int:
    return int(values.map(overs_to_balls).sum()) if not values.empty else 0


def overs_to_balls(value: object) -> int:
    if pd.isna(value):
        return 0
    text = str(value)
    if "." in text:
        overs, balls = text.split(".", 1)
        return int(float(overs or 0)) * 6 + int(float(balls or 0))
    return int(float(text) * 6)


def format_balls_as_overs(balls: object) -> str:
    balls = int(float(balls or 0))
    return f"{balls // 6}.{balls % 6}"


def safe_div(numerator: float, denominator: float) -> float | None:
    if denominator is None or pd.isna(denominator) or float(denominator) == 0:
        return None
    return float(numerator) / float(denominator)


def is_fvcc_team_name(value: object) -> bool:
    return "fiji victorian" in str(value).casefold()


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes"}


def as_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def first_non_empty(values: pd.Series) -> str:
    for value in values:
        text = as_text(value).strip()
        if text:
            return text
    return ""
