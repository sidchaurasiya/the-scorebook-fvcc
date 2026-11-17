"""Build privacy-safe, event-grain GRDCC scorecard records.

The restricted lineage file supplies participant fingerprints only so rows
with unresolved identity can be selected for masking. Fingerprints are never
used as public keys, career keys, or cross-match identity links.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from pathlib import Path
from typing import Iterable

import pandas as pd


GRDCC_CLUB_ID = "georges-river-district"
PRIVATE_PLAYER_LABEL = "Private player"

ANONYMOUS_SCORECARD_COLUMNS = [
    "anonymous_event_key",
    "season",
    "match_date",
    "grade_name",
    "team_name",
    "innings_number",
    "display_player_name",
    "discipline",
    "batting_order",
    "bowling_order",
    "runs_scored",
    "balls_faced",
    "fours_scored",
    "sixes_scored",
    "dismissal_type",
    "overs_bowled",
    "maidens_bowled",
    "runs_conceded",
    "wickets_taken",
    "wides",
    "no_balls",
    "economy",
    "catches",
    "run_outs",
    "stumpings",
    "stat_source",
    "bbb_batting_runs",
    "bbb_batting_balls_faced",
    "bbb_batting_strike_rate",
    "bbb_batting_dot_balls",
    "bbb_batting_dot_ball_rate",
    "bbb_bowling_legal_balls",
    "bbb_bowling_dot_balls",
    "bbb_bowling_dot_ball_rate",
    "bbb_source",
]

ANONYMOUS_FASTEST_COLUMNS = [
    "anonymous_event",
    "anonymous_event_key",
    "player_name",
    "canonical_player_name",
    "season",
    "grade_name",
    "final_runs",
    "final_score_display",
    "balls_to_25",
    "balls_to_50",
    "balls_to_100",
    "balls_to_150",
    "runs_source_used",
    "balls_faced_source_used",
    "source_ball_by_ball_available",
    "governance_final_balls_source",
]

_FORBIDDEN_PUBLIC_COLUMNS = {
    "player_id",
    "participant_id",
    "canonical_player_id",
    "match_id",
    "innings_id",
    "scorecard_url",
    "source_url",
    "raw_player_name",
    "raw_player_id",
    "canonical_player_name",
}

_FASTEST_FORBIDDEN_PUBLIC_COLUMNS = {
    "player_id",
    "participant_id",
    "canonical_player_id",
    "match_id",
    "innings_id",
    "scorecard_url",
    "source_url",
    "raw_player_id",
}


def source_identifier_fingerprint(value: object) -> str:
    """Fingerprint one source identifier without retaining the source value."""
    text = _text(value)
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def participant_fingerprints_from_lineage(lineage: pd.DataFrame) -> set[str]:
    """Read only the participant-ID hash column from a restricted register."""
    if "participant_id_sha256" not in lineage.columns:
        raise ValueError("Restricted lineage must contain participant_id_sha256")
    fingerprints = {
        _text(value).lower()
        for value in lineage["participant_id_sha256"].tolist()
        if _text(value)
    }
    if not fingerprints:
        raise ValueError("No ambiguous participant fingerprints were supplied")
    return fingerprints


def build_anonymous_scorecard_contributions(
    *,
    matches: pd.DataFrame,
    innings: pd.DataFrame,
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
    teams: pd.DataFrame,
    ambiguous_participant_fingerprints: set[str],
    ball_events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Return unique GRDCC scorecard event rows with no player identity fields.

    The source participant fingerprint is used only to decide which records
    receive the generic label. Each public event key is instead derived from
    its match, innings, club team, discipline, and scorecard order.
    """
    fingerprints = {str(value).strip().lower() for value in ambiguous_participant_fingerprints if str(value).strip()}
    if not fingerprints:
        raise ValueError("At least one ambiguous participant fingerprint is required")
    required_matches = {"match_id", "status", "season", "first_match_day", "grade_name"}
    required_innings = {"match_id", "innings_id", "innings_number"}
    required_teams = {"team_id", "team_name"}
    for frame, required, label in (
        (matches, required_matches, "matches"),
        (innings, required_innings, "innings"),
        (teams, required_teams, "teams"),
    ):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{label} input is missing required columns: {sorted(missing)}")

    completed_matches: dict[str, dict[str, object]] = {}
    for row in matches.to_dict("records"):
        match_id = _text(row.get("match_id"))
        if not match_id:
            continue
        if _text(row.get("status")).upper() != "COMPLETED":
            continue
        if match_id in completed_matches:
            raise ValueError("Source match IDs must be unique in the frozen match table")
        completed_matches[match_id] = row

    innings_number_by_key: dict[tuple[str, str], str] = {}
    for row in innings.to_dict("records"):
        key = (_text(row.get("match_id")), _text(row.get("innings_id")))
        if not all(key):
            continue
        if key in innings_number_by_key:
            raise ValueError("Source match/innings keys must be unique")
        innings_number_by_key[key] = _text(row.get("innings_number"))

    team_name_by_id: dict[str, str] = {}
    for row in teams.to_dict("records"):
        team_id = _text(row.get("team_id"))
        team_name = _text(row.get("team_name"))
        if team_id and team_name:
            existing = team_name_by_id.setdefault(team_id, team_name)
            if existing != team_name:
                raise ValueError("A GRDCC team ID maps to conflicting display labels")

    delivery_rows = [] if ball_events is None else ball_events.to_dict("records")
    output: list[dict[str, str]] = []
    _append_scorecard_rows(
        output,
        frame=batting,
        discipline="batting",
        ambiguous_fingerprints=fingerprints,
        completed_matches=completed_matches,
        innings_number_by_key=innings_number_by_key,
        team_name_by_id=team_name_by_id,
        ball_events=delivery_rows,
        source_order_field="bat_order",
        secondary_order_field="bat_instance",
    )
    _append_scorecard_rows(
        output,
        frame=bowling,
        discipline="bowling",
        ambiguous_fingerprints=fingerprints,
        completed_matches=completed_matches,
        innings_number_by_key=innings_number_by_key,
        team_name_by_id=team_name_by_id,
        ball_events=delivery_rows,
        source_order_field="bowl_order",
        secondary_order_field="",
    )
    _append_scorecard_rows(
        output,
        frame=fielding,
        discipline="fielding",
        ambiguous_fingerprints=fingerprints,
        completed_matches=completed_matches,
        innings_number_by_key=innings_number_by_key,
        team_name_by_id=team_name_by_id,
        ball_events=delivery_rows,
        source_order_field="",
        secondary_order_field="",
    )
    frame = pd.DataFrame(output, columns=ANONYMOUS_SCORECARD_COLUMNS).fillna("")
    if frame["anonymous_event_key"].eq("").any() or frame["anonymous_event_key"].duplicated().any():
        raise ValueError("Anonymous scorecard event keys must be present and unique")
    if not frame.empty and not frame["display_player_name"].eq(PRIVATE_PLAYER_LABEL).all():
        raise ValueError("Every anonymous scorecard row must use the generic public label")
    if _FORBIDDEN_PUBLIC_COLUMNS & set(frame.columns):
        raise ValueError("Anonymous scorecard output contains a restricted identity or locator column")
    return frame.sort_values(
        ["season", "match_date", "grade_name", "innings_number", "discipline", "anonymous_event_key"],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)


def build_anonymous_fastest_milestones(
    *,
    milestones: pd.DataFrame,
    batting: pd.DataFrame,
    ball_events: pd.DataFrame,
    matches: pd.DataFrame,
    teams: pd.DataFrame,
    ambiguous_participant_fingerprints: set[str],
) -> pd.DataFrame:
    """Return only scorecard milestones verified independently by delivery events."""
    fingerprints = {str(value).strip().lower() for value in ambiguous_participant_fingerprints if str(value).strip()}
    if not fingerprints:
        raise ValueError("At least one ambiguous participant fingerprint is required")
    required = {"match_id", "innings_id", "participant_id", "final_runs", "balls_to_50", "balls_to_100", "source_ball_by_ball_available"}
    missing = required - set(milestones.columns)
    if missing:
        raise ValueError(f"Milestone input is missing required columns: {sorted(missing)}")
    match_by_id = {_text(row.get("match_id")): row for row in matches.to_dict("records") if _text(row.get("match_id"))}
    team_names = {_text(row.get("team_id")): _text(row.get("team_name")) for row in teams.to_dict("records") if _text(row.get("team_id"))}
    club_team_ids = set(team_names)
    batting_rows = batting.to_dict("records")
    delivery_rows = ball_events.to_dict("records")
    output: list[dict[str, str]] = []
    seen_keys: set[str] = set()

    for milestone in milestones.to_dict("records"):
        participant_id = _text(milestone.get("participant_id"))
        if source_identifier_fingerprint(participant_id) not in fingerprints:
            continue
        if not _is_true(milestone.get("source_ball_by_ball_available")):
            continue
        match_id = _text(milestone.get("match_id"))
        innings_id = _text(milestone.get("innings_id"))
        match = match_by_id.get(match_id, {})
        if _text(match.get("status")).upper() != "COMPLETED":
            continue
        scorecard_rows = [
            row
            for row in batting_rows
            if _text(row.get("match_id")) == match_id
            and _text(row.get("innings_id")) == innings_id
            and _text(row.get("team_id")) in club_team_ids
            and source_identifier_fingerprint(row.get("participant_id")) in fingerprints
        ]
        if len(scorecard_rows) != 1:
            continue
        scorecard = scorecard_rows[0]
        scorecard_runs = _number_text(scorecard.get("runs_scored"))
        milestone_runs = _number_text(milestone.get("final_runs"))
        if not scorecard_runs or scorecard_runs != milestone_runs:
            continue
        verified = _verified_delivery_milestones(
            match_id=match_id,
            innings_id=innings_id,
            participant_fingerprint=source_identifier_fingerprint(participant_id),
            ball_events=delivery_rows,
        )
        if not verified:
            continue
        milestone_values: dict[str, str] = {}
        for name, threshold in (("balls_to_50", 50), ("balls_to_100", 100)):
            advertised = _number_text(milestone.get(name))
            if not advertised or int(float(scorecard_runs)) < threshold:
                continue
            if verified.get(threshold) != advertised:
                continue
            milestone_values[name] = advertised
        if not milestone_values:
            continue
        match_key = _event_key(
            [
                match_id,
                innings_id,
                _text(scorecard.get("team_id")),
                _text(scorecard.get("bat_order")),
                "fastest",
                *sorted(milestone_values),
            ]
        )
        if match_key in seen_keys:
            raise ValueError("Anonymous fastest milestone event keys must be unique")
        seen_keys.add(match_key)
        row = {column: "" for column in ANONYMOUS_FASTEST_COLUMNS}
        row.update(
            {
                "player_name": PRIVATE_PLAYER_LABEL,
                "canonical_player_name": PRIVATE_PLAYER_LABEL,
                "season": _text(match.get("season")),
                "grade_name": _text(match.get("grade_name")),
                "final_runs": scorecard_runs,
                "final_score_display": scorecard_runs,
                "source_ball_by_ball_available": "True",
                "runs_source_used": "official_scorecard",
                "balls_faced_source_used": "verified_ball_by_ball",
                "governance_final_balls_source": "verified_delivery_events",
                "anonymous_event": "True",
                "anonymous_event_key": match_key,
            }
        )
        row.update(milestone_values)
        output.append(row)
    frame = pd.DataFrame(output, columns=ANONYMOUS_FASTEST_COLUMNS).fillna("")
    if not frame.empty and frame["anonymous_event_key"].duplicated().any():
        raise ValueError("Anonymous fastest milestone event keys must be unique")
    return frame.reset_index(drop=True)


def read_public_anonymous_scorecard_contributions(path: str | Path, club_id: str) -> pd.DataFrame:
    if str(club_id).strip().casefold() != GRDCC_CLUB_ID:
        return pd.DataFrame(columns=ANONYMOUS_SCORECARD_COLUMNS)
    try:
        frame = pd.read_csv(path, dtype=str).fillna("")
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame(columns=ANONYMOUS_SCORECARD_COLUMNS)
    if set(frame.columns) != set(ANONYMOUS_SCORECARD_COLUMNS):
        return pd.DataFrame(columns=ANONYMOUS_SCORECARD_COLUMNS)
    if frame["anonymous_event_key"].eq("").any() or frame["anonymous_event_key"].duplicated().any():
        return pd.DataFrame(columns=ANONYMOUS_SCORECARD_COLUMNS)
    if not frame["anonymous_event_key"].str.fullmatch(r"[0-9a-f]{64}").all():
        return pd.DataFrame(columns=ANONYMOUS_SCORECARD_COLUMNS)
    if not frame["display_player_name"].eq(PRIVATE_PLAYER_LABEL).all():
        return pd.DataFrame(columns=ANONYMOUS_SCORECARD_COLUMNS)
    return frame[ANONYMOUS_SCORECARD_COLUMNS].copy()


def read_public_anonymous_fastest_milestones(path: str | Path, club_id: str) -> pd.DataFrame:
    if str(club_id).strip().casefold() != GRDCC_CLUB_ID:
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    try:
        frame = pd.read_csv(path, dtype=str).fillna("")
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    if set(frame.columns) != set(ANONYMOUS_FASTEST_COLUMNS):
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    if frame.empty:
        return frame
    if not frame["anonymous_event"].str.strip().str.casefold().eq("true").all():
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    if not frame["source_ball_by_ball_available"].str.strip().str.casefold().eq("true").all():
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    if not frame["player_name"].eq(PRIVATE_PLAYER_LABEL).all() or not frame["canonical_player_name"].eq(PRIVATE_PLAYER_LABEL).all():
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    if _FASTEST_FORBIDDEN_PUBLIC_COLUMNS & set(frame.columns):
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    if frame["anonymous_event_key"].eq("").any() or frame["anonymous_event_key"].duplicated().any():
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    if not frame["anonymous_event_key"].str.fullmatch(r"[0-9a-f]{64}").all():
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    has_batting_milestone = frame["balls_to_50"].str.strip().ne("") | frame["balls_to_100"].str.strip().ne("")
    if not has_batting_milestone.all():
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    if not frame["runs_source_used"].eq("official_scorecard").all():
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    if not frame["balls_faced_source_used"].eq("verified_ball_by_ball").all():
        return pd.DataFrame(columns=ANONYMOUS_FASTEST_COLUMNS)
    return frame[ANONYMOUS_FASTEST_COLUMNS].copy()


def _append_scorecard_rows(
    output: list[dict[str, str]],
    *,
    frame: pd.DataFrame,
    discipline: str,
    ambiguous_fingerprints: set[str],
    completed_matches: dict[str, dict[str, object]],
    innings_number_by_key: dict[tuple[str, str], str],
    team_name_by_id: dict[str, str],
    ball_events: list[dict[str, object]],
    source_order_field: str,
    secondary_order_field: str,
) -> None:
    if "participant_id" not in frame.columns:
        raise ValueError(f"{discipline} scorecards are missing participant_id")
    records = frame.to_dict("records")
    scoped_ordinals: dict[tuple[str, str, str], int] = {}
    context_counts: Counter[tuple[str, str, str]] = Counter()
    for source in records:
        match_id = _text(source.get("match_id"))
        innings_id = _text(source.get("innings_id"))
        team_id = _text(source.get("team_id"))
        match = completed_matches.get(match_id)
        if (
            match
            and team_id in team_name_by_id
            and source_identifier_fingerprint(source.get("participant_id")) in ambiguous_fingerprints
        ):
            context_counts[(match_id, innings_id, team_id)] += 1
    for source_index, source in enumerate(records):
        if source_identifier_fingerprint(source.get("participant_id")) not in ambiguous_fingerprints:
            continue
        match_id = _text(source.get("match_id"))
        innings_id = _text(source.get("innings_id"))
        team_id = _text(source.get("team_id"))
        match = completed_matches.get(match_id)
        team_name = team_name_by_id.get(team_id, "")
        if not match or not team_name:
            continue
        group = (match_id, innings_id, team_id)
        ordinal = scoped_ordinals.get(group, 0) + 1
        scoped_ordinals[group] = ordinal
        order = _text(source.get(source_order_field)) if source_order_field else ""
        secondary = _text(source.get(secondary_order_field)) if secondary_order_field else ""
        order_key = order or str(ordinal)
        key_parts = [match_id, innings_id, team_id, discipline, order_key, secondary or str(ordinal)]
        event_key = _event_key(key_parts)
        row = {column: "" for column in ANONYMOUS_SCORECARD_COLUMNS}
        row.update(
            {
                "anonymous_event_key": event_key,
                "season": _text(match.get("season")),
                "match_date": _text(match.get("first_match_day")),
                "grade_name": _text(match.get("grade_name") or source.get("grade_name")),
                "team_name": team_name,
                "innings_number": innings_number_by_key.get((match_id, innings_id), ""),
                "display_player_name": PRIVATE_PLAYER_LABEL,
                "discipline": discipline,
                "stat_source": "official_scorecard",
            }
        )
        if discipline == "batting":
            row.update(
                {
                    "batting_order": order,
                    "runs_scored": _text(source.get("runs_scored")),
                    "balls_faced": _text(source.get("balls_faced")),
                    "fours_scored": _text(source.get("fours_scored")),
                    "sixes_scored": _text(source.get("sixes_scored")),
                    "dismissal_type": _text(source.get("dismissal_type")),
                }
            )
            if context_counts[group] == 1:
                row.update(_anonymous_batting_delivery_metrics(
                    match_id=match_id,
                    innings_id=innings_id,
                    team_id=team_id,
                    participant_fingerprints=ambiguous_fingerprints,
                    ball_events=ball_events,
                ))
        elif discipline == "bowling":
            row.update(
                {
                    "bowling_order": order,
                    "overs_bowled": _text(source.get("overs_bowled")),
                    "maidens_bowled": _text(source.get("maidens_bowled")),
                    "runs_conceded": _text(source.get("runs_conceded")),
                    "wickets_taken": _text(source.get("wickets_taken")),
                    "wides": _text(source.get("wides")),
                    "no_balls": _text(source.get("no_balls")),
                    "economy": _text(source.get("economy")),
                }
            )
            if context_counts[group] == 1:
                row.update(_anonymous_bowling_delivery_metrics(
                    match_id=match_id,
                    innings_id=innings_id,
                    team_id=team_id,
                    participant_fingerprints=ambiguous_fingerprints,
                    ball_events=ball_events,
                ))
        else:
            row.update(
                {
                    "catches": _text(source.get("catches")),
                    "run_outs": _text(source.get("run_outs")),
                    "stumpings": _text(source.get("stumpings")),
                }
            )
        output.append(row)


def _verified_delivery_milestones(
    *,
    match_id: str,
    innings_id: str,
    participant_fingerprint: str,
    ball_events: list[dict[str, object]],
) -> dict[int, str]:
    events = [
        row
        for row in ball_events
        if _text(row.get("match_id")) == match_id
        and _text(row.get("innings_id")) == innings_id
        and source_identifier_fingerprint(row.get("striker_participant_id")) == participant_fingerprint
    ]
    events.sort(
        key=lambda row: (
            _float_order(row.get("over_number")),
            _float_order(row.get("ball_number")),
            _text(row.get("ball_event_id")),
        )
    )
    event_ids = [_text(row.get("ball_event_id")) for row in events]
    if not events or any(not value for value in event_ids) or len(event_ids) != len(set(event_ids)):
        return {}
    result: dict[int, str] = {}
    for threshold in (50, 100):
        crossing = next(
            (
                row
                for row in events
                if _at_least(row.get("striker_runs_scored"), threshold)
            ),
            None,
        )
        if crossing is not None:
            balls = _number_text(crossing.get("striker_balls_faced"))
            if balls:
                result[threshold] = balls
    return result


def _anonymous_batting_delivery_metrics(
    *,
    match_id: str,
    innings_id: str,
    team_id: str,
    participant_fingerprints: set[str],
    ball_events: list[dict[str, object]],
) -> dict[str, str]:
    deliveries = _unique_delivery_rows(
        match_id=match_id,
        innings_id=innings_id,
        team_id=team_id,
        team_column="batting_team_id",
        participant_column="striker_participant_id",
        participant_fingerprints=participant_fingerprints,
        ball_events=ball_events,
    )
    if not deliveries:
        return {}
    bbb_runs = sum(_number_value(row.get("runs_bat")) for row in deliveries)
    bbb_balls = sum(1 for row in deliveries if _number_value(row.get("wides")) == 0)
    bbb_dots = sum(
        1
        for row in deliveries
        if _number_value(row.get("wides")) == 0 and _number_value(row.get("runs_bat")) == 0
    )
    return {
        "bbb_batting_runs": _number_text(bbb_runs),
        "bbb_batting_balls_faced": _number_text(bbb_balls),
        "bbb_batting_strike_rate": _rate_text(bbb_runs, bbb_balls),
        "bbb_batting_dot_balls": _number_text(bbb_dots),
        "bbb_batting_dot_ball_rate": _rate_text(bbb_dots, bbb_balls),
        "bbb_source": "verified_ball_by_ball",
    }


def _anonymous_bowling_delivery_metrics(
    *,
    match_id: str,
    innings_id: str,
    team_id: str,
    participant_fingerprints: set[str],
    ball_events: list[dict[str, object]],
) -> dict[str, str]:
    deliveries = _unique_delivery_rows(
        match_id=match_id,
        innings_id=innings_id,
        team_id=team_id,
        team_column="bowling_team_id",
        participant_column="bowler_participant_id",
        participant_fingerprints=participant_fingerprints,
        ball_events=ball_events,
    )
    if not deliveries:
        return {}
    legal = [row for row in deliveries if _is_true(row.get("is_legal_delivery"))]
    dots = [row for row in legal if _number_value(row.get("total_runs")) == 0]
    return {
        "bbb_bowling_legal_balls": _number_text(len(legal)),
        "bbb_bowling_dot_balls": _number_text(len(dots)),
        "bbb_bowling_dot_ball_rate": _rate_text(len(dots), len(legal)),
        "bbb_source": "verified_ball_by_ball" if legal else "",
    }


def _unique_delivery_rows(
    *,
    match_id: str,
    innings_id: str,
    team_id: str,
    team_column: str,
    participant_column: str,
    participant_fingerprints: set[str],
    ball_events: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows = [
        row
        for row in ball_events
        if _text(row.get("match_id")) == match_id
        and _text(row.get("innings_id")) == innings_id
        and _text(row.get(team_column)) == team_id
        and source_identifier_fingerprint(row.get(participant_column)) in participant_fingerprints
    ]
    event_ids = [_text(row.get("ball_event_id")) for row in rows]
    if not rows or any(not value for value in event_ids) or len(event_ids) != len(set(event_ids)):
        return []
    return rows


def _rate_text(numerator: int | float, denominator: int | float) -> str:
    if denominator <= 0:
        return ""
    return f"{(float(numerator) * 100.0 / float(denominator)):.1f}"


def _number_value(value: object) -> float:
    try:
        return float(_text(value))
    except (TypeError, ValueError):
        return 0.0


def _event_key(parts: Iterable[object]) -> str:
    value = "\x1f".join(_text(part) for part in parts)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _number_text(value: object) -> str:
    text = _text(value)
    if not text:
        return ""
    try:
        number = float(text)
    except (TypeError, ValueError):
        return ""
    if not number.is_integer():
        return str(number)
    return str(int(number))


def _at_least(value: object, threshold: int) -> bool:
    try:
        return float(_text(value)) >= threshold
    except (TypeError, ValueError):
        return False


def _float_order(value: object) -> float:
    try:
        return float(_text(value))
    except (TypeError, ValueError):
        return float("inf")


def _is_true(value: object) -> bool:
    return _text(value).casefold() in {"true", "1", "yes", "y"}


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()
