from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ALL_MATCHES_COLUMNS = [
    "match_id",
    "status",
    "status_id",
    "result_text",
    "match_type",
    "match_type_id",
    "is_ball_by_ball",
    "grade_id",
    "grade_name",
    "round_id",
    "round_name",
    "venue_id",
    "venue_name",
    "playing_surface_id",
    "playing_surface_name",
    "home_team_id",
    "home_team_name",
    "away_team_id",
    "away_team_name",
    "match_day_count",
    "first_match_day",
    "last_match_day",
    "source_fetched_at",
]

ALL_MATCH_INNINGS_COLUMNS = [
    "match_id",
    "innings_id",
    "innings_number",
    "innings_order",
    "innings_name",
    "batting_team_id",
    "bowling_team_id",
    "innings_close_type",
    "is_declared",
    "is_follow_on",
    "runs_scored",
    "wickets_fallen",
    "overs_bowled",
    "total_extras",
    "byes_runs",
    "leg_byes_runs",
    "no_balls",
    "wides",
    "penalties",
]

ALL_SCORECARD_BATTING_COLUMNS = [
    "match_id",
    "innings_id",
    "team_id",
    "participant_id",
    "player_name",
    "player_short_name",
    "bat_order",
    "bat_instance",
    "runs_scored",
    "balls_faced",
    "fours_scored",
    "sixes_scored",
    "strike_rate",
    "batting_minutes",
    "dismissal_type_id",
    "dismissal_type",
    "dismissal_text",
    "bowler_participant_id",
    "fielder_participant_id",
    "fielder_assist_participant_id",
]

ALL_SCORECARD_BOWLING_COLUMNS = [
    "match_id",
    "innings_id",
    "team_id",
    "participant_id",
    "player_name",
    "player_short_name",
    "bowl_order",
    "overs_bowled",
    "maidens_bowled",
    "runs_conceded",
    "wickets_taken",
    "wides",
    "no_balls",
    "economy",
]

ALL_SCORECARD_FIELDING_COLUMNS = [
    "match_id",
    "innings_id",
    "team_id",
    "participant_id",
    "player_name",
    "player_short_name",
    "catches",
    "run_outs",
    "stumpings",
    "assisted_run_outs",
]

ALL_FALL_OF_WICKETS_COLUMNS = [
    "match_id",
    "innings_id",
    "batting_team_id",
    "wicket_number",
    "runs",
    "over_number",
    "ball_number",
    "dismissed_participant_id",
    "dismissed_player_name",
    "not_out_participant_id",
    "not_out_player_name",
]

ALL_MATCH_OFFICIALS_COLUMNS = [
    "match_id",
    "official_id",
    "official_name",
    "official_short_name",
    "role",
    "role_id",
]

ALL_BALL_BY_BALL_COLUMNS = [
    "match_id",
    "innings_id",
    "innings_number",
    "innings_order",
    "batting_team_id",
    "bowling_team_id",
    "ball_event_id",
    "over_number",
    "ball_number",
    "ball_display_number",
    "ball_time",
    "striker_participant_id",
    "striker_short_name",
    "non_striker_participant_id",
    "non_striker_short_name",
    "bowler_participant_id",
    "bowler_short_name",
    "runs_bat",
    "wides",
    "no_balls",
    "leg_byes",
    "byes",
    "penalty_runs",
    "total_runs",
    "is_legal_delivery",
    "is_wicket",
    "dismissal_type_id",
    "dismissal_type",
    "dismissed_participant_id",
    "fielder_participant_id",
    "fielder_assist_participant_id",
    "progress_runs",
    "progress_wickets",
    "progress_score",
    "short_description",
    "description",
]

ALL_OVERS_COLUMNS = [
    "match_id",
    "innings_id",
    "batting_team_id",
    "bowling_team_id",
    "over_number",
    "bowler_participant_id",
    "bowler_short_name",
    "runs",
    "wickets",
    "legal_balls",
    "wides",
    "no_balls",
    "boundaries",
    "run_rate_after_over",
]

ALL_PARTNERSHIPS_COLUMNS = [
    "match_id",
    "innings_id",
    "batting_team_id",
    "partnership_number",
    "batter_1_participant_id",
    "batter_1_name",
    "batter_2_participant_id",
    "batter_2_name",
    "start_score",
    "end_score",
    "runs",
    "balls",
    "source",
    "wicket_ending_participant_id",
    "dismissal_type",
]

VALIDATION_REPORT_COLUMNS = [
    "check_name",
    "match_id",
    "innings_id",
    "entity_id",
    "status",
    "severity",
    "expected_value",
    "actual_value",
    "detail",
]


@dataclass(frozen=True)
class MatchCentrePayloads:
    manifest: dict[str, Any]
    scorecard: dict[str, Any]
    balls: dict[str, Any]
    officials: dict[str, Any]


def parse_sample_directory(sample_dir: Path) -> dict[str, pd.DataFrame]:
    payloads = load_sample_payloads(sample_dir)
    scorecard = payloads.scorecard
    match_id = str(scorecard.get("id", ""))
    team_ids = [str(team.get("id")) for team in scorecard.get("teams", []) if team.get("id")]
    player_lookup = build_player_lookup(scorecard.get("teams", []) or [])
    innings_lookup = build_scorecard_innings_lookup(scorecard, team_ids)
    ball_innings = build_ball_innings_lookup(payloads.balls)

    all_ball_by_ball = build_ball_by_ball(match_id, ball_innings, team_ids)
    wicket_lookup = build_wicket_lookup(all_ball_by_ball)

    all_match_innings = build_match_innings(match_id, innings_lookup)
    all_scorecard_batting = build_scorecard_batting(match_id, innings_lookup, player_lookup, wicket_lookup)
    all_scorecard_bowling = build_scorecard_bowling(match_id, innings_lookup, player_lookup)
    all_scorecard_fielding = build_scorecard_fielding(match_id, innings_lookup, player_lookup)
    all_fall_of_wickets = build_fall_of_wickets(match_id, innings_lookup, player_lookup)

    frames = {
        "all_matches": build_matches(payloads, ball_innings),
        "all_match_innings": all_match_innings,
        "all_scorecard_batting": all_scorecard_batting,
        "all_scorecard_bowling": all_scorecard_bowling,
        "all_scorecard_fielding": all_scorecard_fielding,
        "all_fall_of_wickets": all_fall_of_wickets,
        "all_match_officials": build_match_officials(match_id, payloads.officials),
        "all_ball_by_ball": all_ball_by_ball,
        "all_overs": build_overs(all_ball_by_ball),
        "all_partnerships": build_partnerships(all_ball_by_ball, all_fall_of_wickets),
    }
    frames["validation_report"] = build_validation_report(
        scorecard=scorecard,
        innings_lookup=innings_lookup,
        ball_innings=ball_innings,
        all_match_innings=all_match_innings,
        all_scorecard_batting=all_scorecard_batting,
        all_scorecard_bowling=all_scorecard_bowling,
        all_scorecard_fielding=all_scorecard_fielding,
        all_ball_by_ball=all_ball_by_ball,
    )
    return frames


def load_sample_payloads(sample_dir: Path) -> MatchCentrePayloads:
    return MatchCentrePayloads(
        manifest=read_json(sample_dir / "manifest.json"),
        scorecard=read_json(next(sample_dir.glob("match_scorecard_*.json"))).get("payload", {}),
        balls=read_json(next(sample_dir.glob("match_balls_*.json"))).get("payload", {}),
        officials=read_json(next(sample_dir.glob("match_officials_*.json"))).get("payload", {}),
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_player_lookup(teams: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for team in teams:
        team_id = team.get("id")
        for player in team.get("players", []) or []:
            participant_id = player.get("participantId")
            if participant_id:
                lookup[str(participant_id)] = {
                    "participant_id": participant_id,
                    "player_name": player.get("name"),
                    "player_short_name": player.get("shortName"),
                    "team_id": team_id,
                }
    return lookup


def build_scorecard_innings_lookup(scorecard: dict[str, Any], team_ids: list[str]) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for innings in scorecard.get("innings", []) or []:
        innings_id = innings.get("id")
        if not innings_id:
            continue
        batting_team_id = innings.get("battingTeamId")
        bowling_team_id = next((team_id for team_id in team_ids if team_id != batting_team_id), None)
        lookup[str(innings_id)] = {
            "raw": innings,
            "innings_id": innings_id,
            "innings_number": innings.get("inningsNumber"),
            "innings_order": innings.get("inningsOrder"),
            "innings_name": innings.get("name") or innings.get("inningsName"),
            "batting_team_id": batting_team_id,
            "bowling_team_id": bowling_team_id,
        }
    return lookup


def build_ball_innings_lookup(balls_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(innings.get("id")): innings
        for innings in balls_payload.get("innings", []) or []
        if innings.get("id")
    }


def build_matches(payloads: MatchCentrePayloads, ball_innings: dict[str, dict[str, Any]]) -> pd.DataFrame:
    scorecard = payloads.scorecard
    summary = scorecard.get("matchSummary", {}) or {}
    summary_teams = summary.get("teams", []) or []
    home = next((team for team in summary_teams if team.get("isHome")), {})
    away = next((team for team in summary_teams if team.get("isHome") is False), {})
    venue = scorecard.get("venue", {}) or {}
    surface = venue.get("playingSurface", {}) or {}
    grade = scorecard.get("grade", {}) or {}
    round_data = scorecard.get("round", {}) or {}
    schedule = scorecard.get("matchSchedule", []) or []
    dates = [item.get("startDateTime") for item in schedule if item.get("startDateTime")]

    return pd.DataFrame(
        [
            {
                "match_id": scorecard.get("id"),
                "status": scorecard.get("status"),
                "status_id": scorecard.get("statusId"),
                "result_text": summary.get("resultText"),
                "match_type": scorecard.get("matchType"),
                "match_type_id": scorecard.get("matchTypeId"),
                "is_ball_by_ball": bool(scorecard.get("isBallByBall") and ball_innings),
                "grade_id": grade.get("id"),
                "grade_name": grade.get("name"),
                "round_id": round_data.get("id"),
                "round_name": round_data.get("name"),
                "venue_id": venue.get("id"),
                "venue_name": venue.get("name"),
                "playing_surface_id": surface.get("id"),
                "playing_surface_name": surface.get("name"),
                "home_team_id": home.get("id"),
                "home_team_name": home.get("displayName"),
                "away_team_id": away.get("id"),
                "away_team_name": away.get("displayName"),
                "match_day_count": len(schedule),
                "first_match_day": min(dates) if dates else None,
                "last_match_day": max(dates) if dates else None,
                "source_fetched_at": payloads.manifest.get("fetched_at"),
            }
        ],
        columns=ALL_MATCHES_COLUMNS,
    )


def build_match_innings(match_id: str, innings_lookup: dict[str, dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for meta in innings_lookup.values():
        raw = meta["raw"]
        rows.append(
            {
                "match_id": match_id,
                "innings_id": meta["innings_id"],
                "innings_number": meta["innings_number"],
                "innings_order": meta["innings_order"],
                "innings_name": meta["innings_name"],
                "batting_team_id": meta["batting_team_id"],
                "bowling_team_id": meta["bowling_team_id"],
                "innings_close_type": raw.get("inningsCloseType"),
                "is_declared": bool(raw.get("isDeclared")),
                "is_follow_on": bool(raw.get("isFollowOn")),
                "runs_scored": raw.get("runsScored"),
                "wickets_fallen": raw.get("numberOfWicketsFallen"),
                "overs_bowled": raw.get("oversBowled"),
                "total_extras": raw.get("totalExtras"),
                "byes_runs": raw.get("byesRuns"),
                "leg_byes_runs": raw.get("legByesRuns"),
                "no_balls": raw.get("noBalls"),
                "wides": raw.get("wideBalls"),
                "penalties": raw.get("penalties"),
            }
        )
    return pd.DataFrame(rows, columns=ALL_MATCH_INNINGS_COLUMNS)


def build_scorecard_batting(
    match_id: str,
    innings_lookup: dict[str, dict[str, Any]],
    player_lookup: dict[str, dict[str, Any]],
    wicket_lookup: dict[tuple[str, str], dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for meta in innings_lookup.values():
        for batter in meta["raw"].get("batting", []) or []:
            participant_id = batter.get("participantId")
            player = player_lookup.get(str(participant_id), {})
            wicket = wicket_lookup.get((str(meta["innings_id"]), str(participant_id)), {})
            rows.append(
                {
                    "match_id": match_id,
                    "innings_id": meta["innings_id"],
                    "team_id": meta["batting_team_id"],
                    "participant_id": participant_id,
                    "player_name": player.get("player_name"),
                    "player_short_name": batter.get("playerShortName") or player.get("player_short_name"),
                    "bat_order": batter.get("batOrder"),
                    "bat_instance": batter.get("batInstance"),
                    "runs_scored": batter.get("runsScored"),
                    "balls_faced": batter.get("ballsFaced"),
                    "fours_scored": batter.get("foursScored"),
                    "sixes_scored": batter.get("sixesScored"),
                    "strike_rate": batter.get("strikeRate"),
                    "batting_minutes": batter.get("battingMinutes"),
                    "dismissal_type_id": batter.get("dismissalTypeId"),
                    "dismissal_type": batter.get("dismissalType"),
                    "dismissal_text": batter.get("dismissalText"),
                    "bowler_participant_id": wicket.get("bowler_participant_id"),
                    "fielder_participant_id": wicket.get("fielder_participant_id"),
                    "fielder_assist_participant_id": wicket.get("fielder_assist_participant_id"),
                }
            )
    return pd.DataFrame(rows, columns=ALL_SCORECARD_BATTING_COLUMNS)


def build_scorecard_bowling(
    match_id: str,
    innings_lookup: dict[str, dict[str, Any]],
    player_lookup: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for meta in innings_lookup.values():
        for bowler in meta["raw"].get("bowling", []) or []:
            participant_id = bowler.get("participantId")
            player = player_lookup.get(str(participant_id), {})
            rows.append(
                {
                    "match_id": match_id,
                    "innings_id": meta["innings_id"],
                    "team_id": meta["bowling_team_id"],
                    "participant_id": participant_id,
                    "player_name": player.get("player_name"),
                    "player_short_name": bowler.get("playerShortName") or player.get("player_short_name"),
                    "bowl_order": bowler.get("bowlOrder"),
                    "overs_bowled": bowler.get("oversBowled"),
                    "maidens_bowled": bowler.get("maidensBowled"),
                    "runs_conceded": bowler.get("runsConceded"),
                    "wickets_taken": bowler.get("wicketsTaken"),
                    "wides": bowler.get("wideBalls"),
                    "no_balls": bowler.get("noBalls"),
                    "economy": bowler.get("economy"),
                }
            )
    return pd.DataFrame(rows, columns=ALL_SCORECARD_BOWLING_COLUMNS)


def build_scorecard_fielding(
    match_id: str,
    innings_lookup: dict[str, dict[str, Any]],
    player_lookup: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for meta in innings_lookup.values():
        for fielder in meta["raw"].get("fielding", []) or []:
            participant_id = fielder.get("participantId")
            player = player_lookup.get(str(participant_id), {})
            rows.append(
                {
                    "match_id": match_id,
                    "innings_id": meta["innings_id"],
                    "team_id": meta["bowling_team_id"],
                    "participant_id": participant_id,
                    "player_name": player.get("player_name"),
                    "player_short_name": fielder.get("playerShortName") or player.get("player_short_name"),
                    "catches": fielder.get("totalCatches", fielder.get("catches")),
                    "run_outs": fielder.get("runOuts"),
                    "stumpings": fielder.get("stumpings"),
                    "assisted_run_outs": fielder.get("assistedRunOuts"),
                }
            )
    return pd.DataFrame(rows, columns=ALL_SCORECARD_FIELDING_COLUMNS)


def build_fall_of_wickets(
    match_id: str,
    innings_lookup: dict[str, dict[str, Any]],
    player_lookup: dict[str, dict[str, Any]],
) -> pd.DataFrame:
    rows = []
    for meta in innings_lookup.values():
        for wicket in meta["raw"].get("fallOfWickets", []) or []:
            dismissed_id = first_present(wicket, ["dismissedParticipantId", "participantId"])
            not_out_id = first_present(wicket, ["notOutParticipantId", "notOutBatterParticipantId"])
            rows.append(
                {
                    "match_id": match_id,
                    "innings_id": meta["innings_id"],
                    "batting_team_id": meta["batting_team_id"],
                    "wicket_number": first_present(wicket, ["wicketNumber", "wicket"]),
                    "runs": first_present(wicket, ["runs", "score", "teamRuns"]),
                    "over_number": first_present(wicket, ["overNumber", "over"]),
                    "ball_number": first_present(wicket, ["ballNumber", "ball"]),
                    "dismissed_participant_id": dismissed_id,
                    "dismissed_player_name": player_lookup.get(str(dismissed_id), {}).get("player_name"),
                    "not_out_participant_id": not_out_id,
                    "not_out_player_name": player_lookup.get(str(not_out_id), {}).get("player_name"),
                }
            )
    return pd.DataFrame(rows, columns=ALL_FALL_OF_WICKETS_COLUMNS)


def build_match_officials(match_id: str, officials_payload: dict[str, Any]) -> pd.DataFrame:
    rows = []
    for official in officials_payload.get("officials", []) or []:
        rows.append(
            {
                "match_id": match_id,
                "official_id": official.get("id"),
                "official_name": official.get("name"),
                "official_short_name": official.get("shortName"),
                "role": official.get("role"),
                "role_id": official.get("roleId"),
            }
        )
    return pd.DataFrame(rows, columns=ALL_MATCH_OFFICIALS_COLUMNS)


def build_ball_by_ball(
    match_id: str,
    ball_innings: dict[str, dict[str, Any]],
    team_ids: list[str],
) -> pd.DataFrame:
    rows = []
    for innings_id, innings in ball_innings.items():
        batting_team_id = innings.get("battingTeamId")
        bowling_team_id = next((team_id for team_id in team_ids if team_id != batting_team_id), None)
        for ball in innings.get("balls", []) or []:
            wides = to_int(ball.get("wides"))
            no_balls = to_int(ball.get("noBalls"))
            row = {
                "match_id": match_id,
                "innings_id": innings_id,
                "innings_number": innings.get("inningsNumber"),
                "innings_order": innings.get("inningsOrder"),
                "batting_team_id": batting_team_id,
                "bowling_team_id": bowling_team_id,
                "ball_event_id": ball.get("id"),
                "over_number": ball.get("overNumber"),
                "ball_number": ball.get("ballNumber"),
                "ball_display_number": ball.get("ballDisplayNumber"),
                "ball_time": ball.get("ballTime"),
                "striker_participant_id": ball.get("strikerParticipantId"),
                "striker_short_name": ball.get("strikerShortName"),
                "non_striker_participant_id": ball.get("nonStrikerParticipantId"),
                "non_striker_short_name": ball.get("nonStrikerShortName"),
                "bowler_participant_id": ball.get("bowlerParticipantId"),
                "bowler_short_name": ball.get("bowlerShortName"),
                "runs_bat": to_int(ball.get("runsBat")),
                "wides": wides,
                "no_balls": no_balls,
                "leg_byes": to_int(ball.get("legByes")),
                "byes": to_int(ball.get("byes")),
                "penalty_runs": to_int(ball.get("penaltyRuns")),
                "is_legal_delivery": wides == 0 and no_balls == 0,
                "is_wicket": is_wicket(ball),
                "dismissal_type_id": ball.get("dismissalTypeId"),
                "dismissal_type": ball.get("dismissalType"),
                "dismissed_participant_id": ball.get("dismissedParticipantId"),
                "fielder_participant_id": ball.get("fielderParticipantId"),
                "fielder_assist_participant_id": ball.get("fielderAssistParticipantId"),
                "progress_runs": ball.get("progressRuns"),
                "progress_wickets": ball.get("progressWickets"),
                "progress_score": ball.get("progressScore"),
                "short_description": ball.get("shortDescription"),
                "description": ball.get("description"),
            }
            row["total_runs"] = sum(
                row[key] for key in ["runs_bat", "wides", "no_balls", "leg_byes", "byes", "penalty_runs"]
            )
            rows.append(row)
    return pd.DataFrame(rows, columns=ALL_BALL_BY_BALL_COLUMNS)


def build_wicket_lookup(ball_by_ball: pd.DataFrame) -> dict[tuple[str, str], dict[str, Any]]:
    if ball_by_ball.empty:
        return {}
    lookup = {}
    wickets = ball_by_ball[ball_by_ball["is_wicket"]]
    for _, wicket in wickets.iterrows():
        dismissed_id = wicket.get("dismissed_participant_id")
        if pd.isna(dismissed_id):
            continue
        lookup[(str(wicket["innings_id"]), str(dismissed_id))] = {
            "bowler_participant_id": wicket.get("bowler_participant_id"),
            "fielder_participant_id": wicket.get("fielder_participant_id"),
            "fielder_assist_participant_id": wicket.get("fielder_assist_participant_id"),
        }
    return lookup


def build_overs(ball_by_ball: pd.DataFrame) -> pd.DataFrame:
    if ball_by_ball.empty:
        return pd.DataFrame(columns=ALL_OVERS_COLUMNS)
    rows = []
    for keys, group in ball_by_ball.groupby(
        ["match_id", "innings_id", "batting_team_id", "bowling_team_id", "over_number"],
        dropna=False,
        sort=True,
    ):
        last = group.iloc[-1]
        legal_balls_to_date = int(
            ball_by_ball[
                (ball_by_ball["innings_id"] == keys[1])
                & (
                    (ball_by_ball["over_number"] < keys[4])
                    | (
                        (ball_by_ball["over_number"] == keys[4])
                        & (ball_by_ball.index <= group.index.max())
                    )
                )
            ]["is_legal_delivery"].sum()
        )
        progress_runs = to_int(last.get("progress_runs"))
        run_rate = round(progress_runs / legal_balls_to_date * 6, 2) if legal_balls_to_date else None
        rows.append(
            {
                "match_id": keys[0],
                "innings_id": keys[1],
                "batting_team_id": keys[2],
                "bowling_team_id": keys[3],
                "over_number": keys[4],
                "bowler_participant_id": first_non_empty(group["bowler_participant_id"]),
                "bowler_short_name": first_non_empty(group["bowler_short_name"]),
                "runs": int(group["total_runs"].sum()),
                "wickets": int(group["is_wicket"].sum()),
                "legal_balls": int(group["is_legal_delivery"].sum()),
                "wides": int(group["wides"].sum()),
                "no_balls": int(group["no_balls"].sum()),
                "boundaries": int(group["runs_bat"].isin([4, 6]).sum()),
                "run_rate_after_over": run_rate,
            }
        )
    return pd.DataFrame(rows, columns=ALL_OVERS_COLUMNS)


def build_partnerships(ball_by_ball: pd.DataFrame, fall_of_wickets: pd.DataFrame) -> pd.DataFrame:
    if not ball_by_ball.empty:
        return build_ball_partnerships(ball_by_ball)
    return build_fow_partnerships(fall_of_wickets)


def build_ball_partnerships(ball_by_ball: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, innings in ball_by_ball.groupby(["match_id", "innings_id", "batting_team_id"], dropna=False, sort=True):
        current: list[pd.Series] = []
        start_score = "0-0"
        partnership_number = 1
        for _, ball in innings.sort_values(["over_number", "ball_number", "ball_event_id"]).iterrows():
            current.append(ball)
            if bool(ball["is_wicket"]):
                rows.append(ball_partnership_row(keys, partnership_number, current, start_score, ball))
                start_score = ball.get("progress_score")
                current = []
                partnership_number += 1
        if current:
            rows.append(ball_partnership_row(keys, partnership_number, current, start_score, None))
    return pd.DataFrame(rows, columns=ALL_PARTNERSHIPS_COLUMNS)


def ball_partnership_row(
    keys: tuple[Any, ...],
    partnership_number: int,
    balls: list[pd.Series],
    start_score: Any,
    wicket_ball: pd.Series | None,
) -> dict[str, Any]:
    batters = batter_pair_from_balls(balls)
    last = balls[-1]
    return {
        "match_id": keys[0],
        "innings_id": keys[1],
        "batting_team_id": keys[2],
        "partnership_number": partnership_number,
        "batter_1_participant_id": batters[0][0] if len(batters) > 0 else None,
        "batter_1_name": batters[0][1] if len(batters) > 0 else None,
        "batter_2_participant_id": batters[1][0] if len(batters) > 1 else None,
        "batter_2_name": batters[1][1] if len(batters) > 1 else None,
        "start_score": start_score,
        "end_score": last.get("progress_score"),
        "runs": int(sum(ball["total_runs"] for ball in balls)),
        "balls": int(sum(bool(ball["is_legal_delivery"]) for ball in balls)),
        "source": "ball_by_ball",
        "wicket_ending_participant_id": wicket_ball.get("dismissed_participant_id") if wicket_ball is not None else None,
        "dismissal_type": wicket_ball.get("dismissal_type") if wicket_ball is not None else None,
    }


def build_fow_partnerships(fall_of_wickets: pd.DataFrame) -> pd.DataFrame:
    if fall_of_wickets.empty:
        return pd.DataFrame(columns=ALL_PARTNERSHIPS_COLUMNS)
    rows = []
    for keys, wickets in fall_of_wickets.groupby(["match_id", "innings_id", "batting_team_id"], dropna=False, sort=True):
        previous_runs = 0
        previous_score = "0-0"
        for _, wicket in wickets.sort_values("wicket_number").iterrows():
            runs = to_int(wicket.get("runs")) - previous_runs
            end_score = f"{wicket.get('runs')}-{wicket.get('wicket_number')}"
            rows.append(
                {
                    "match_id": keys[0],
                    "innings_id": keys[1],
                    "batting_team_id": keys[2],
                    "partnership_number": wicket.get("wicket_number"),
                    "batter_1_participant_id": wicket.get("dismissed_participant_id"),
                    "batter_1_name": wicket.get("dismissed_player_name"),
                    "batter_2_participant_id": wicket.get("not_out_participant_id"),
                    "batter_2_name": wicket.get("not_out_player_name"),
                    "start_score": previous_score,
                    "end_score": end_score,
                    "runs": runs,
                    "balls": None,
                    "source": "fall_of_wickets",
                    "wicket_ending_participant_id": wicket.get("dismissed_participant_id"),
                    "dismissal_type": None,
                }
            )
            previous_runs = to_int(wicket.get("runs"))
            previous_score = end_score
    return pd.DataFrame(rows, columns=ALL_PARTNERSHIPS_COLUMNS)


def build_validation_report(
    *,
    scorecard: dict[str, Any],
    innings_lookup: dict[str, dict[str, Any]],
    ball_innings: dict[str, dict[str, Any]],
    all_match_innings: pd.DataFrame,
    all_scorecard_batting: pd.DataFrame,
    all_scorecard_bowling: pd.DataFrame,
    all_scorecard_fielding: pd.DataFrame,
    all_ball_by_ball: pd.DataFrame,
) -> pd.DataFrame:
    match_id = str(scorecard.get("id", ""))
    rows = []
    rows.extend(validate_required_match_fields(scorecard))

    for _, innings in all_match_innings.iterrows():
        innings_id = str(innings["innings_id"])
        batting = all_scorecard_batting[all_scorecard_batting["innings_id"] == innings_id]
        bowling = all_scorecard_bowling[all_scorecard_bowling["innings_id"] == innings_id]
        balls = all_ball_by_ball[all_ball_by_ball["innings_id"] == innings_id] if not all_ball_by_ball.empty else pd.DataFrame()

        extras = to_int(innings.get("total_extras"))
        batting_runs = int(pd.to_numeric(batting["runs_scored"], errors="coerce").fillna(0).sum()) if not batting.empty else 0
        expected_total = batting_runs + extras
        rows.append(report_row("scorecard_innings_runs_vs_batting_plus_extras", match_id, innings_id, None, innings.get("runs_scored"), expected_total))

        dismissed = dismissed_batter_mask(batting)
        dismissal_count = int(dismissed.sum()) if not batting.empty else 0
        rows.append(report_row("scorecard_wickets_vs_batting_dismissals", match_id, innings_id, None, innings.get("wickets_fallen"), dismissal_count))

        bowling_wickets = int(pd.to_numeric(bowling["wickets_taken"], errors="coerce").fillna(0).sum()) if not bowling.empty else 0
        bowler_credited = dismissed & batting["bowler_participant_id"].notna() & ~run_out_batter_mask(batting)
        bowler_credited_dismissals = int(bowler_credited.sum()) if not batting.empty else 0
        rows.append(
            report_row(
                "scorecard_bowling_wickets_vs_batting_dismissals",
                match_id,
                innings_id,
                None,
                bowling_wickets,
                bowler_credited_dismissals,
            )
        )

        if not balls.empty:
            last = balls.iloc[-1]
            rows.append(report_row("scorecard_innings_total_vs_ball_progress_runs", match_id, innings_id, None, innings.get("runs_scored"), last.get("progress_runs")))
        elif scorecard.get("isBallByBall"):
            rows.append(
                report_row(
                    "scorecard_innings_missing_from_ball_by_ball",
                    match_id,
                    innings_id,
                    None,
                    "present",
                    "missing",
                    "warning",
                    "Scorecard innings has no ball-event innings. Keep scorecard data and do not invent balls.",
                )
            )

    scorecard_ids = set(innings_lookup)
    ball_ids = set(ball_innings)
    for innings_id in sorted(ball_ids - scorecard_ids):
        rows.append(report_row("ball_by_ball_innings_missing_from_scorecard", match_id, innings_id, None, "missing", "present", "warning"))

    for table_name, frame, id_column in [
        ("scorecard_batting", all_scorecard_batting, "participant_id"),
        ("scorecard_bowling", all_scorecard_bowling, "participant_id"),
        ("scorecard_fielding", all_scorecard_fielding, "participant_id"),
        ("ball_by_ball", all_ball_by_ball, "ball_event_id"),
    ]:
        if frame.empty:
            continue
        missing = int(frame[id_column].isna().sum() + (frame[id_column].astype(str).str.strip() == "").sum())
        rows.append(report_row(f"missing_player_or_source_ids_{table_name}", match_id, None, id_column, 0, missing, "pass" if missing == 0 else "warning"))

    if not all_scorecard_batting.empty:
        dismissed = all_scorecard_batting[dismissed_batter_mask(all_scorecard_batting)]
        missing_dismissal_text = int(dismissed["dismissal_text"].isna().sum() + (dismissed["dismissal_text"].astype(str).str.strip() == "").sum())
        rows.append(report_row("missing_dismissal_fields", match_id, None, "dismissal_text", 0, missing_dismissal_text, "pass" if missing_dismissal_text == 0 else "warning"))

    return pd.DataFrame(rows, columns=VALIDATION_REPORT_COLUMNS)


def validate_required_match_fields(scorecard: dict[str, Any]) -> list[dict[str, Any]]:
    match_id = str(scorecard.get("id", ""))
    venue = scorecard.get("venue", {}) or {}
    grade = scorecard.get("grade", {}) or {}
    teams = scorecard.get("matchSummary", {}).get("teams", []) or []
    checks = [
        ("missing_venue_fields", "venue_id", venue.get("id")),
        ("missing_venue_fields", "venue_name", venue.get("name")),
        ("missing_grade_fields", "grade_id", grade.get("id")),
        ("missing_grade_fields", "grade_name", grade.get("name")),
        ("missing_team_fields", "teams", len(teams) if teams else None),
    ]
    rows = []
    for check_name, entity_id, value in checks:
        missing = value in (None, "")
        rows.append(
            report_row(
                check_name,
                match_id,
                None,
                entity_id,
                "present",
                "missing" if missing else "present",
                "warning" if missing else "pass",
            )
        )
    return rows


def report_row(
    check_name: str,
    match_id: str,
    innings_id: Any,
    entity_id: Any,
    expected_value: Any,
    actual_value: Any,
    status: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    resolved_status = status or ("pass" if value_equal(expected_value, actual_value) else "warning")
    return {
        "check_name": check_name,
        "match_id": match_id,
        "innings_id": innings_id,
        "entity_id": entity_id,
        "status": resolved_status,
        "severity": "info" if resolved_status == "pass" else "warning",
        "expected_value": expected_value,
        "actual_value": actual_value,
        "detail": detail or ("Values match." if resolved_status == "pass" else "Values differ or are missing; inspect raw source."),
    }


def batter_pair_from_balls(balls: list[pd.Series]) -> list[tuple[Any, Any]]:
    seen: dict[Any, Any] = {}
    order: list[Any] = []
    for ball in balls:
        for id_col, name_col in [
            ("striker_participant_id", "striker_short_name"),
            ("non_striker_participant_id", "non_striker_short_name"),
        ]:
            participant_id = ball.get(id_col)
            if pd.notna(participant_id) and participant_id not in seen:
                seen[participant_id] = ball.get(name_col)
                order.append(participant_id)
    return [(participant_id, seen[participant_id]) for participant_id in order[:2]]


def first_present(row: dict[str, Any], keys: list[str]) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def first_non_empty(values: pd.Series) -> Any:
    clean = values.dropna()
    clean = clean[clean.astype(str).str.strip() != ""]
    return clean.iloc[0] if not clean.empty else None


def is_wicket(ball: dict[str, Any]) -> bool:
    return bool(ball.get("dismissedParticipantId") or ball.get("dismissalTypeId"))


def dismissed_batter_mask(batting: pd.DataFrame) -> pd.Series:
    if batting.empty:
        return pd.Series(dtype=bool)
    dismissal_type = batting["dismissal_type"].fillna("").astype(str).str.casefold()
    dismissal_text = batting["dismissal_text"].fillna("").astype(str).str.casefold()
    return ~(
        dismissal_type.isin(["", "not out", "did not bat"])
        | dismissal_text.isin(["", "not out", "did not bat"])
    )


def run_out_batter_mask(batting: pd.DataFrame) -> pd.Series:
    if batting.empty:
        return pd.Series(dtype=bool)
    dismissal_type = batting["dismissal_type"].fillna("").astype(str).str.casefold()
    return dismissal_type == "run out"


def to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def value_equal(left: Any, right: Any) -> bool:
    if pd.isna(left) and pd.isna(right):
        return True
    if isinstance(left, (int, float)) or isinstance(right, (int, float)):
        try:
            return float(left) == float(right)
        except (TypeError, ValueError):
            return False
    return str(left) == str(right)


def parse_score_wickets(score: Any) -> tuple[int | None, int | None]:
    if not isinstance(score, str):
        return None, None
    match = re.match(r"^\s*(\d+)-(\d+)", score)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))
