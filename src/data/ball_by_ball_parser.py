from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


FVCC_ORGANISATION_ID = "7b78f08d-87d8-eb11-a7ad-2818780da0cc"

MATCH_SCORECARDS_COLUMNS = [
    "match_id",
    "status",
    "status_id",
    "match_type",
    "match_type_id",
    "is_ball_by_ball",
    "result_text",
    "grade_id",
    "grade_name",
    "round_id",
    "round_name",
    "home_team_id",
    "home_team_name",
    "away_team_id",
    "away_team_name",
    "fvcc_team_id",
    "fvcc_team_name",
    "venue_id",
    "venue_name",
    "playing_surface_id",
    "playing_surface_name",
    "start_date_time",
    "match_day_count",
    "scorecard_innings_count",
    "ball_innings_count",
]

BALL_BY_BALL_COLUMNS = [
    "match_id",
    "innings_id",
    "innings_number",
    "innings_order",
    "batting_team_id",
    "bowling_team_id",
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
    "source_ball_event_id",
]

OVERS_COLUMNS = [
    "match_id",
    "innings_id",
    "innings_number",
    "innings_order",
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
    "progress_runs_after_over",
    "progress_wickets_after_over",
]

PARTNERSHIPS_COLUMNS = [
    "match_id",
    "innings_id",
    "innings_number",
    "innings_order",
    "batting_team_id",
    "partnership_number",
    "batter_1_participant_id",
    "batter_1_short_name",
    "batter_2_participant_id",
    "batter_2_short_name",
    "start_over_number",
    "start_ball_display_number",
    "end_over_number",
    "end_ball_display_number",
    "runs",
    "legal_balls",
    "wicket_ending_participant_id",
    "dismissal_type",
]

OFFICIALS_COLUMNS = [
    "match_id",
    "official_name",
    "official_short_name",
    "official_role",
]

VALIDATION_COLUMNS = [
    "check_name",
    "match_id",
    "innings_id",
    "innings_name",
    "scorecard_value",
    "ball_events_value",
    "status",
    "detail",
]


@dataclass(frozen=True)
class SamplePayloads:
    manifest: dict[str, Any]
    scorecard: dict[str, Any]
    balls: dict[str, Any]
    officials: dict[str, Any]


def parse_sample_directory(sample_dir: Path) -> dict[str, pd.DataFrame]:
    payloads = load_sample_payloads(sample_dir)
    match_id = str(payloads.scorecard.get("id", ""))
    team_ids = [str(team.get("id", "")) for team in payloads.scorecard.get("teams", []) if team.get("id")]

    scorecard_innings = {
        str(inning.get("id")): inning
        for inning in payloads.scorecard.get("innings", [])
        if inning.get("id")
    }
    ball_innings = {
        str(inning.get("id")): inning
        for inning in payloads.balls.get("innings", [])
        if inning.get("id")
    }

    ball_by_ball = build_ball_by_ball(match_id, ball_innings, team_ids)

    return {
        "all_match_scorecards": build_match_scorecards(payloads, ball_innings),
        "all_ball_by_ball": ball_by_ball,
        "all_overs": build_overs(ball_by_ball),
        "all_partnerships": build_partnerships(ball_by_ball),
        "all_match_officials": build_officials(match_id, payloads.officials),
        "validation_report": build_validation_report(match_id, scorecard_innings, ball_innings, ball_by_ball),
    }


def load_sample_payloads(sample_dir: Path) -> SamplePayloads:
    scorecard_path = next(sample_dir.glob("match_scorecard_*.json"))
    balls_path = next(sample_dir.glob("match_balls_*.json"))
    officials_path = next(sample_dir.glob("match_officials_*.json"))
    return SamplePayloads(
        manifest=read_json(sample_dir / "manifest.json"),
        scorecard=read_json(scorecard_path).get("payload", {}),
        balls=read_json(balls_path).get("payload", {}),
        officials=read_json(officials_path).get("payload", {}),
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_match_scorecards(payloads: SamplePayloads, ball_innings: dict[str, dict[str, Any]]) -> pd.DataFrame:
    scorecard = payloads.scorecard
    summary_teams = scorecard.get("matchSummary", {}).get("teams", [])
    home = next((team for team in summary_teams if team.get("isHome")), {})
    away = next((team for team in summary_teams if team.get("isHome") is False), {})
    fvcc = find_fvcc_team(scorecard.get("teams", []), summary_teams)
    venue = scorecard.get("venue", {}) or {}
    surface = venue.get("playingSurface", {}) or {}
    schedule = scorecard.get("matchSchedule", []) or []
    grade = scorecard.get("grade", {}) or {}
    round_data = scorecard.get("round", {}) or {}

    rows = [
        {
            "match_id": scorecard.get("id"),
            "status": scorecard.get("status"),
            "status_id": scorecard.get("statusId"),
            "match_type": scorecard.get("matchType"),
            "match_type_id": scorecard.get("matchTypeId"),
            "is_ball_by_ball": bool(scorecard.get("isBallByBall")),
            "result_text": scorecard.get("matchSummary", {}).get("resultText"),
            "grade_id": grade.get("id"),
            "grade_name": grade.get("name"),
            "round_id": round_data.get("id"),
            "round_name": round_data.get("name"),
            "home_team_id": home.get("id"),
            "home_team_name": home.get("displayName"),
            "away_team_id": away.get("id"),
            "away_team_name": away.get("displayName"),
            "fvcc_team_id": fvcc.get("id"),
            "fvcc_team_name": fvcc.get("displayName") or fvcc.get("name"),
            "venue_id": venue.get("id"),
            "venue_name": venue.get("name"),
            "playing_surface_id": surface.get("id"),
            "playing_surface_name": surface.get("name"),
            "start_date_time": schedule[0].get("startDateTime") if schedule else None,
            "match_day_count": len(schedule),
            "scorecard_innings_count": len(scorecard.get("innings", []) or []),
            "ball_innings_count": len(ball_innings),
        }
    ]
    return pd.DataFrame(rows, columns=MATCH_SCORECARDS_COLUMNS)


def find_fvcc_team(scorecard_teams: list[dict[str, Any]], summary_teams: list[dict[str, Any]]) -> dict[str, Any]:
    for team in scorecard_teams:
        organisation = team.get("owningOrganisation", {}) or {}
        if organisation.get("id") == FVCC_ORGANISATION_ID:
            summary = next((item for item in summary_teams if item.get("id") == team.get("id")), {})
            return {**team, **summary}
    return {}


def build_ball_by_ball(
    match_id: str,
    ball_innings: dict[str, dict[str, Any]],
    team_ids: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
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
                "source_ball_event_id": ball.get("id"),
            }
            row["total_runs"] = (
                row["runs_bat"]
                + row["wides"]
                + row["no_balls"]
                + row["leg_byes"]
                + row["byes"]
                + row["penalty_runs"]
            )
            rows.append(row)
    return pd.DataFrame(rows, columns=BALL_BY_BALL_COLUMNS)


def build_overs(ball_by_ball: pd.DataFrame) -> pd.DataFrame:
    if ball_by_ball.empty:
        return pd.DataFrame(columns=OVERS_COLUMNS)

    rows = []
    for keys, group in ball_by_ball.groupby(
        [
            "match_id",
            "innings_id",
            "innings_number",
            "innings_order",
            "batting_team_id",
            "bowling_team_id",
            "over_number",
        ],
        dropna=False,
        sort=True,
    ):
        last = group.iloc[-1]
        bowler = group["bowler_participant_id"].dropna()
        bowler_name = group["bowler_short_name"].dropna()
        rows.append(
            {
                "match_id": keys[0],
                "innings_id": keys[1],
                "innings_number": keys[2],
                "innings_order": keys[3],
                "batting_team_id": keys[4],
                "bowling_team_id": keys[5],
                "over_number": keys[6],
                "bowler_participant_id": bowler.iloc[0] if not bowler.empty else None,
                "bowler_short_name": bowler_name.iloc[0] if not bowler_name.empty else None,
                "runs": int(group["total_runs"].sum()),
                "wickets": int(group["is_wicket"].sum()),
                "legal_balls": int(group["is_legal_delivery"].sum()),
                "wides": int(group["wides"].sum()),
                "no_balls": int(group["no_balls"].sum()),
                "boundaries": int(group["runs_bat"].isin([4, 6]).sum()),
                "progress_runs_after_over": last.get("progress_runs"),
                "progress_wickets_after_over": last.get("progress_wickets"),
            }
        )
    return pd.DataFrame(rows, columns=OVERS_COLUMNS)


def build_partnerships(ball_by_ball: pd.DataFrame) -> pd.DataFrame:
    if ball_by_ball.empty:
        return pd.DataFrame(columns=PARTNERSHIPS_COLUMNS)

    rows = []
    for keys, innings in ball_by_ball.groupby(
        ["match_id", "innings_id", "innings_number", "innings_order", "batting_team_id"],
        dropna=False,
        sort=True,
    ):
        current: list[pd.Series] = []
        partnership_number = 1
        for _, ball in innings.sort_values(["over_number", "ball_number", "source_ball_event_id"]).iterrows():
            current.append(ball)
            if bool(ball["is_wicket"]):
                rows.append(partnership_row(keys, partnership_number, current, ball))
                current = []
                partnership_number += 1
        if current:
            rows.append(partnership_row(keys, partnership_number, current, None))

    return pd.DataFrame(rows, columns=PARTNERSHIPS_COLUMNS)


def partnership_row(
    keys: tuple[Any, ...],
    partnership_number: int,
    balls: list[pd.Series],
    wicket_ball: pd.Series | None,
) -> dict[str, Any]:
    first = balls[0]
    last = balls[-1]
    batters = batter_pair_from_balls(balls)
    return {
        "match_id": keys[0],
        "innings_id": keys[1],
        "innings_number": keys[2],
        "innings_order": keys[3],
        "batting_team_id": keys[4],
        "partnership_number": partnership_number,
        "batter_1_participant_id": batters[0][0] if len(batters) > 0 else None,
        "batter_1_short_name": batters[0][1] if len(batters) > 0 else None,
        "batter_2_participant_id": batters[1][0] if len(batters) > 1 else None,
        "batter_2_short_name": batters[1][1] if len(batters) > 1 else None,
        "start_over_number": first["over_number"],
        "start_ball_display_number": first["ball_display_number"],
        "end_over_number": last["over_number"],
        "end_ball_display_number": last["ball_display_number"],
        "runs": int(sum(ball["total_runs"] for ball in balls)),
        "legal_balls": int(sum(bool(ball["is_legal_delivery"]) for ball in balls)),
        "wicket_ending_participant_id": wicket_ball.get("dismissed_participant_id") if wicket_ball is not None else None,
        "dismissal_type": wicket_ball.get("dismissal_type") if wicket_ball is not None else None,
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


def build_officials(match_id: str, officials_payload: dict[str, Any]) -> pd.DataFrame:
    rows = [
        {
            "match_id": match_id,
            "official_name": official.get("name"),
            "official_short_name": official.get("shortName"),
            "official_role": official.get("role"),
        }
        for official in officials_payload.get("officials", []) or []
    ]
    return pd.DataFrame(rows, columns=OFFICIALS_COLUMNS)


def build_validation_report(
    match_id: str,
    scorecard_innings: dict[str, dict[str, Any]],
    ball_innings: dict[str, dict[str, Any]],
    ball_by_ball: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    scorecard_ids = set(scorecard_innings)
    ball_ids = set(ball_innings)

    for innings_id in sorted(scorecard_ids - ball_ids):
        innings = scorecard_innings[innings_id]
        rows.append(validation_row(
            "scorecard_innings_missing_from_ball_events",
            match_id,
            innings_id,
            innings_name(innings),
            "present",
            "missing",
            "warning",
            "Scorecard innings has no ball-event innings. Preserve the scorecard row and do not invent balls.",
        ))

    for innings_id in sorted(ball_ids - scorecard_ids):
        innings = ball_innings[innings_id]
        rows.append(validation_row(
            "ball_events_innings_missing_from_scorecard",
            match_id,
            innings_id,
            innings_name(innings),
            "missing",
            "present",
            "warning",
            "Ball-event innings has no scorecard innings. Preserve source IDs for review.",
        ))

    for innings_id in sorted(scorecard_ids & ball_ids):
        innings = scorecard_innings[innings_id]
        balls = ball_by_ball[ball_by_ball["innings_id"] == innings_id]
        scorecard_runs = to_int(innings.get("runsScored"))
        scorecard_wickets = to_int(innings.get("numberOfWicketsFallen"))
        scorecard_legal_balls = overs_to_balls(innings.get("oversBowled"))
        ball_runs = int(balls["total_runs"].sum()) if not balls.empty else 0
        ball_wickets = int(balls["is_wicket"].sum()) if not balls.empty else 0
        ball_legal_balls = int(balls["is_legal_delivery"].sum()) if not balls.empty else 0

        rows.append(compare_row("innings_runs_match", match_id, innings, scorecard_runs, ball_runs))
        rows.append(compare_row("innings_wickets_match", match_id, innings, scorecard_wickets, ball_wickets))
        rows.append(compare_row("innings_legal_balls_match", match_id, innings, scorecard_legal_balls, ball_legal_balls))

    return pd.DataFrame(rows, columns=VALIDATION_COLUMNS)


def compare_row(check_name: str, match_id: str, innings: dict[str, Any], scorecard_value: Any, ball_value: Any) -> dict[str, Any]:
    status = "pass" if scorecard_value == ball_value else "warning"
    detail = "Values match." if status == "pass" else "Values differ; inspect raw scorecard and ball event source rows."
    return validation_row(
        check_name,
        match_id,
        str(innings.get("id")),
        innings_name(innings),
        scorecard_value,
        ball_value,
        status,
        detail,
    )


def validation_row(
    check_name: str,
    match_id: str,
    innings_id: str,
    name: str | None,
    scorecard_value: Any,
    ball_value: Any,
    status: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "check_name": check_name,
        "match_id": match_id,
        "innings_id": innings_id,
        "innings_name": name,
        "scorecard_value": scorecard_value,
        "ball_events_value": ball_value,
        "status": status,
        "detail": detail,
    }


def innings_name(innings: dict[str, Any]) -> str | None:
    return innings.get("name") or innings.get("inningsName")


def is_wicket(ball: dict[str, Any]) -> bool:
    return bool(ball.get("dismissedParticipantId") or ball.get("dismissalTypeId"))


def to_int(value: Any) -> int:
    if value in (None, ""):
        return 0
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


def overs_to_balls(value: Any) -> int:
    if value in (None, ""):
        return 0
    text = str(value)
    if "." not in text:
        return to_int(value) * 6
    overs_text, balls_text = text.split(".", 1)
    return to_int(overs_text) * 6 + to_int(balls_text[:1])

