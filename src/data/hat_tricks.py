"""Shared, source-driven cricket hat-trick detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from src.utils.player_identity import filter_public_player_rows, is_private_or_anonymised_player


BOWLER_WICKET_DISMISSALS = {
    "bowled",
    "caught",
    "lbw",
    "stumped",
    "hit wicket",
}
NON_BOWLER_DISMISSALS = {
    "run out",
    "retired",
    "retired hurt",
    "retired out",
    "retired not out",
    "obstructing the field",
    "timed out",
    "hit the ball twice",
    "not out",
    "did not bat",
    "absent",
}
AUDIT_COLUMNS = [
    "event_id",
    "player",
    "canonical_player_id",
    "season",
    "match_id",
    "innings_id",
    "opponent",
    "team_name",
    "delivery_1",
    "dismissal_1",
    "dismissed_player_id_1",
    "wides_1",
    "no_balls_1",
    "delivery_2",
    "dismissal_2",
    "dismissed_player_id_2",
    "wides_2",
    "no_balls_2",
    "delivery_3",
    "dismissal_3",
    "dismissed_player_id_3",
    "wides_3",
    "no_balls_3",
    "spans_overs",
    "spans_innings",
    "source_evidence",
    "scorecard_wickets",
    "batting_dismissals_verified",
    "validation_status",
    "exclusion_reason",
    "is_private_player",
]
EVENT_COLUMNS = [
    "event_id",
    "canonical_player_id",
    "canonical_player_name",
    "season",
    "match_id",
    "innings_id",
    "match_date",
    "team_name",
    "opponent",
    "grade_name",
    "delivery_sequence",
    "dismissal_sequence",
    "spans_overs",
    "spans_innings",
    "scorecard_wickets",
    "evidence_source",
    "confidence",
    "scoreboard_url",
    "source_coverage_note",
]


@dataclass(frozen=True)
class HatTrickDetectionResult:
    events: pd.DataFrame
    audit: pd.DataFrame
    coverage: dict[str, object]


def detect_hat_tricks(
    ball_by_ball: pd.DataFrame,
    *,
    matches: pd.DataFrame | None = None,
    bowling_scorecard: pd.DataFrame | None = None,
    batting_scorecard: pd.DataFrame | None = None,
    selected_team_ids_by_match: Mapping[str, set[str]] | None = None,
    identity_lookup: Mapping[str, Mapping[str, str]] | None = None,
    coverage_note: str = "Hat-tricks identified from available detailed records.",
) -> HatTrickDetectionResult:
    if ball_by_ball.empty:
        return HatTrickDetectionResult(empty_events(), empty_audit(), empty_coverage())

    rows, duplicates_removed = prepare_delivery_rows(ball_by_ball)
    selected_team_ids_by_match = selected_team_ids_by_match or {}
    if selected_team_ids_by_match:
        rows = rows[
            rows.apply(
                lambda row: str(row.get("bowling_team_id"))
                in selected_team_ids_by_match.get(str(row.get("match_id")), set()),
                axis=1,
            )
        ].copy()
    match_lookup = frame_lookup(matches, "match_id")
    bowling_lookup = prepare_bowling_lookup(bowling_scorecard)
    batting_lookup = prepare_batting_lookup(batting_scorecard)
    identity_lookup = identity_lookup or {}
    rows["_canonical_bowler_id"] = rows["bowler_participant_id"].map(
        lambda value: clean_text(identity_lookup.get(str(value), {}).get("canonical_player_id")) or str(value)
    )
    rows["_canonical_bowler_name"] = rows.apply(
        lambda row: clean_text(identity_lookup.get(str(row.get("bowler_participant_id")), {}).get("canonical_player_name"))
        or clean_text(row.get("bowler_short_name"))
        or "Unknown player",
        axis=1,
    )
    conflict_coordinates = conflicting_delivery_coordinates(rows)

    audit_rows: list[dict[str, object]] = []
    confirmed_rows: list[dict[str, object]] = []
    group_columns = ["match_id", "_canonical_bowler_id"]
    for (match_id, canonical_id), group in rows.groupby(group_columns, dropna=False, sort=False):
        ordered = group.sort_values(
            ["innings_order", "over_number", "ball_number", "_source_order", "ball_event_id"],
            na_position="last",
            kind="mergesort",
        ).reset_index(drop=True)
        for position in range(max(len(ordered) - 2, 0)):
            sequence = ordered.iloc[position : position + 3].copy()
            if not sequence["is_wicket_bool"].all():
                continue
            player_name = clean_text(sequence.iloc[0].get("_canonical_bowler_name")) or "Unknown player"
            innings_ids = list(dict.fromkeys(sequence["innings_id"].dropna().astype(str)))
            innings_label = " | ".join(innings_ids)
            match = match_lookup.get(str(match_id), {})
            team_name, opponent = team_and_opponent(sequence.iloc[0], match)
            scorecard_wickets = bowling_wickets_for_candidate(
                bowling_lookup,
                str(match_id),
                sequence,
            )
            batting_verified = verified_batting_dismissal_count(
                sequence,
                batting_lookup,
                str(match_id),
                str(canonical_id),
                identity_lookup,
            )
            status, reason = classify_candidate(
                sequence,
                scorecard_wickets=scorecard_wickets,
                batting_verified=batting_verified,
                conflict_coordinates=conflict_coordinates,
            )
            labels = [delivery_label(row) for _, row in sequence.iterrows()]
            dismissals = [clean_text(value) for value in sequence["dismissal_type"]]
            dismissed_ids = [clean_text(value) for value in sequence["dismissed_participant_id"]]
            wide_values = [numeric_extra(row.get("wides")) for _, row in sequence.iterrows()]
            no_ball_values = [numeric_extra(row.get("no_balls")) for _, row in sequence.iterrows()]
            event_id = hat_trick_event_id(str(match_id), innings_ids, sequence)
            source_evidence = (
                "PlayCricket ball-by-ball"
                f"; bowling scorecard wickets={format_optional_number(scorecard_wickets)}"
                f"; batting dismissals verified={batting_verified}/3"
            )
            audit_row = {
                "event_id": event_id,
                "player": player_name,
                "canonical_player_id": canonical_id,
                "season": clean_text(match.get("season")),
                "match_id": str(match_id),
                "innings_id": innings_label,
                "opponent": opponent,
                "team_name": team_name,
                "delivery_1": labels[0],
                "dismissal_1": dismissals[0],
                "dismissed_player_id_1": dismissed_ids[0],
                "wides_1": wide_values[0],
                "no_balls_1": no_ball_values[0],
                "delivery_2": labels[1],
                "dismissal_2": dismissals[1],
                "dismissed_player_id_2": dismissed_ids[1],
                "wides_2": wide_values[1],
                "no_balls_2": no_ball_values[1],
                "delivery_3": labels[2],
                "dismissal_3": dismissals[2],
                "dismissed_player_id_3": dismissed_ids[2],
                "wides_3": wide_values[2],
                "no_balls_3": no_ball_values[2],
                "spans_overs": sequence_spans_overs(sequence),
                "spans_innings": len(innings_ids) > 1,
                "source_evidence": source_evidence,
                "scorecard_wickets": scorecard_wickets,
                "batting_dismissals_verified": batting_verified,
                "validation_status": status,
                "exclusion_reason": reason,
                "is_private_player": is_private_or_anonymised_player(player_name),
            }
            audit_rows.append(audit_row)
            if status == "CONFIRMED":
                confirmed_rows.append(
                    {
                        "event_id": event_id,
                        "canonical_player_id": canonical_id,
                        "canonical_player_name": player_name,
                        "season": clean_text(match.get("season")),
                        "match_id": str(match_id),
                        "innings_id": innings_label,
                        "match_date": clean_text(match.get("first_match_day"))[:10],
                        "team_name": team_name,
                        "opponent": opponent,
                        "grade_name": clean_text(match.get("grade_name")),
                        "delivery_sequence": " · ".join(labels),
                        "dismissal_sequence": " · ".join(dismissals),
                        "spans_overs": sequence_spans_overs(sequence),
                        "spans_innings": len(innings_ids) > 1,
                        "scorecard_wickets": scorecard_wickets,
                        "evidence_source": "PlayCricket ball-by-ball + bowling and batting scorecards",
                        "confidence": "high",
                        "scoreboard_url": f"https://play.cricket.com.au/match/{match_id}",
                        "source_coverage_note": coverage_note,
                    }
                )

    audit = pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS)
    events = pd.DataFrame(confirmed_rows, columns=EVENT_COLUMNS)
    if not audit.empty:
        audit = audit.drop_duplicates("event_id").sort_values(["season", "match_id", "player", "delivery_1"]).reset_index(drop=True)
    if not events.empty:
        events = events.drop_duplicates("event_id").sort_values(["season", "match_date", "canonical_player_name"]).reset_index(drop=True)
    coverage = {
        "source_delivery_rows": int(len(ball_by_ball)),
        "semantic_duplicate_rows_removed": int(duplicates_removed),
        "eligible_bowling_delivery_rows": int(len(rows)),
        "eligible_bowling_innings": int(rows["innings_id"].nunique()),
        "matches_with_ball_by_ball": int(rows["match_id"].nunique()),
        "candidate_windows": int(len(audit)),
        "confirmed": int((audit.get("validation_status") == "CONFIRMED").sum()) if not audit.empty else 0,
        "rejected": int((audit.get("validation_status") == "REJECTED").sum()) if not audit.empty else 0,
        "ambiguous": int((audit.get("validation_status") == "AMBIGUOUS / REVIEW").sum()) if not audit.empty else 0,
    }
    return HatTrickDetectionResult(events, audit, coverage)


def public_hat_trick_events(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    return filter_public_player_rows(events)


def prepare_delivery_rows(ball_by_ball: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    rows = ball_by_ball.copy().reset_index(drop=True)
    rows["_source_order"] = range(len(rows))
    rows = rows.drop_duplicates("ball_event_id", keep="first") if "ball_event_id" in rows else rows.drop_duplicates()
    rows["is_wicket_bool"] = bool_series(rows.get("is_wicket"))
    rows["is_legal_bool"] = bool_series(rows.get("is_legal_delivery"))
    rows["dismissal_key"] = rows.get("dismissal_type", pd.Series("", index=rows.index)).map(normalize_dismissal_type)
    no_balls = pd.to_numeric(rows.get("no_balls", pd.Series(0, index=rows.index)), errors="coerce").fillna(0)
    rows["bowler_wicket"] = (
        rows["is_wicket_bool"]
        & rows["dismissal_key"].isin(BOWLER_WICKET_DISMISSALS)
        & no_balls.eq(0)
        & rows.get("dismissed_participant_id", pd.Series("", index=rows.index)).fillna("").astype(str).str.strip().ne("")
    )
    semantic_columns = [
        "match_id",
        "innings_id",
        "over_number",
        "ball_number",
        "bowler_participant_id",
        "striker_participant_id",
        "non_striker_participant_id",
        "runs_bat",
        "wides",
        "no_balls",
        "leg_byes",
        "byes",
        "penalty_runs",
        "total_runs",
        "is_wicket_bool",
        "dismissal_key",
        "dismissed_participant_id",
        "progress_runs",
        "progress_wickets",
    ]
    semantic_columns = [column for column in semantic_columns if column in rows]
    before = len(rows)
    rows = rows.drop_duplicates(semantic_columns, keep="first").copy()
    return rows, before - len(rows)


def classify_candidate(
    sequence: pd.DataFrame,
    *,
    scorecard_wickets: float | None,
    batting_verified: int,
    conflict_coordinates: set[tuple[str, ...]],
) -> tuple[str, str]:
    non_bowler = [
        f"delivery {index + 1} {clean_text(row.get('dismissal_type')) or 'unknown dismissal'} is not credited to the bowler"
        for index, (_, row) in enumerate(sequence.iterrows())
        if not bool(row.get("bowler_wicket"))
    ]
    if non_bowler:
        return "REJECTED", "; ".join(non_bowler)
    dismissed = [clean_text(value) for value in sequence["dismissed_participant_id"]]
    if any(not value for value in dismissed) or len(set(dismissed)) != 3:
        return "AMBIGUOUS / REVIEW", "Three bowler-wicket rows do not identify three distinct dismissed participants."
    candidate_coordinates = {delivery_coordinate(row) for _, row in sequence.iterrows()}
    if candidate_coordinates & conflict_coordinates:
        return "AMBIGUOUS / REVIEW", "Provider has conflicting rows for a delivery in the candidate sequence."
    if scorecard_wickets is None:
        return "AMBIGUOUS / REVIEW", "No matching bowling scorecard row is available for cross-checking."
    if scorecard_wickets < 3:
        return "AMBIGUOUS / REVIEW", f"Bowling scorecard credits only {format_optional_number(scorecard_wickets)} wickets."
    if batting_verified < 3:
        return "AMBIGUOUS / REVIEW", f"Only {batting_verified} of 3 batting dismissals reconcile to this bowler."
    return "CONFIRMED", "Three consecutive bowler deliveries, three distinct bowler-credited wickets, and matching scorecard evidence."


def normalize_dismissal_type(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", clean_text(value).casefold())
    text = re.sub(r"\s+", " ", text).strip()
    if text in {"caught bowled", "caught and bowled", "caught b"}:
        return "caught"
    if text.startswith("caught"):
        return "caught"
    return text


def conflicting_delivery_coordinates(rows: pd.DataFrame) -> set[tuple[str, ...]]:
    coordinate_columns = ["match_id", "innings_id", "over_number", "ball_number", "bowler_participant_id"]
    conflicts: set[tuple[str, ...]] = set()
    for key, group in rows.groupby(coordinate_columns, dropna=False):
        if len(group) <= 1:
            continue
        legal_count = int(group["is_legal_bool"].sum())
        if legal_count > 1:
            conflicts.add(tuple(str(value) for value in key))
    return conflicts


def delivery_coordinate(row: pd.Series) -> tuple[str, ...]:
    return tuple(
        str(row.get(column))
        for column in ["match_id", "innings_id", "over_number", "ball_number", "bowler_participant_id"]
    )


def sequence_spans_overs(sequence: pd.DataFrame) -> bool:
    coordinates = {
        (clean_text(row.get("innings_id")), clean_text(row.get("over_number")))
        for _, row in sequence.iterrows()
    }
    return len(coordinates) > 1


def prepare_bowling_lookup(frame: pd.DataFrame | None) -> dict[tuple[str, str, str], float]:
    if frame is None or frame.empty:
        return {}
    rows = frame.copy()
    rows["wickets_taken"] = pd.to_numeric(rows.get("wickets_taken"), errors="coerce")
    grouped = rows.groupby(["match_id", "innings_id", "participant_id"], dropna=False)["wickets_taken"].max()
    return {tuple(str(value) for value in key): float(value) for key, value in grouped.items() if pd.notna(value)}


def prepare_batting_lookup(frame: pd.DataFrame | None) -> dict[tuple[str, str, str], dict[str, str]]:
    if frame is None or frame.empty:
        return {}
    rows = frame.drop_duplicates([column for column in ["match_id", "innings_id", "participant_id", "bat_instance"] if column in frame])
    lookup: dict[tuple[str, str, str], dict[str, str]] = {}
    for _, row in rows.iterrows():
        key = (str(row.get("match_id")), str(row.get("innings_id")), str(row.get("participant_id")))
        lookup[key] = {
            "dismissal_type": normalize_dismissal_type(row.get("dismissal_type")),
            "bowler_participant_id": clean_text(row.get("bowler_participant_id")),
        }
    return lookup


def verified_batting_dismissal_count(
    sequence: pd.DataFrame,
    lookup: Mapping[tuple[str, str, str], Mapping[str, str]],
    match_id: str,
    canonical_bowler_id: str,
    identity_lookup: Mapping[str, Mapping[str, str]],
) -> int:
    verified = 0
    for _, row in sequence.iterrows():
        innings_id = clean_text(row.get("innings_id"))
        dismissed_id = clean_text(row.get("dismissed_participant_id"))
        batting = lookup.get((match_id, innings_id, dismissed_id), {})
        batting_bowler_id = str(batting.get("bowler_participant_id", ""))
        batting_canonical_id = clean_text(identity_lookup.get(batting_bowler_id, {}).get("canonical_player_id")) or batting_bowler_id
        if batting.get("dismissal_type") in BOWLER_WICKET_DISMISSALS and batting_canonical_id == canonical_bowler_id:
            verified += 1
    return verified


def bowling_wickets_for_candidate(
    lookup: Mapping[tuple[str, str, str], float],
    match_id: str,
    sequence: pd.DataFrame,
) -> float | None:
    scorecard_keys = {
        (match_id, clean_text(row.get("innings_id")), clean_text(row.get("bowler_participant_id")))
        for _, row in sequence.iterrows()
    }
    values = [lookup[key] for key in scorecard_keys if key in lookup]
    return sum(values) if values else None


def frame_lookup(frame: pd.DataFrame | None, key_column: str) -> dict[str, dict[str, object]]:
    if frame is None or frame.empty or key_column not in frame:
        return {}
    rows = frame.drop_duplicates(key_column).copy()
    rows[key_column] = rows[key_column].astype(str)
    return rows.set_index(key_column).to_dict("index")


def team_and_opponent(ball: pd.Series, match: Mapping[str, object]) -> tuple[str, str]:
    bowling_id = clean_text(ball.get("bowling_team_id"))
    batting_id = clean_text(ball.get("batting_team_id"))
    home_id = clean_text(match.get("home_team_id"))
    away_id = clean_text(match.get("away_team_id"))
    home_name = clean_text(match.get("home_team_name"))
    away_name = clean_text(match.get("away_team_name"))
    team_name = home_name if bowling_id == home_id else away_name if bowling_id == away_id else ""
    opponent = home_name if batting_id == home_id else away_name if batting_id == away_id else ""
    return team_name, opponent


def delivery_label(row: pd.Series) -> str:
    over = pd.to_numeric(row.get("over_number"), errors="coerce")
    ball = pd.to_numeric(row.get("ball_number"), errors="coerce")
    if pd.notna(over) and pd.notna(ball):
        return f"{int(over)}.{int(ball)}"
    return clean_text(row.get("ball_display_number")) or clean_text(row.get("ball_event_id"))


def hat_trick_event_id(match_id: str, innings_ids: list[str], sequence: pd.DataFrame) -> str:
    first = clean_text(sequence.iloc[0].get("ball_event_id"))
    last = clean_text(sequence.iloc[-1].get("ball_event_id"))
    innings_key = ">".join(innings_ids)
    return f"{match_id}:{innings_key}:{first}:{last}"


def bool_series(values: object) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.map(lambda value: value if isinstance(value, bool) else str(value).strip().casefold() in {"true", "1", "yes"})
    return pd.Series(dtype=bool)


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"", "nan", "none", "nat"} else text


def format_optional_number(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "missing"
    return str(int(value)) if float(value).is_integer() else str(value)


def numeric_extra(value: object) -> int | float:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return 0
    return int(number) if float(number).is_integer() else float(number)


def empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_COLUMNS)


def empty_audit() -> pd.DataFrame:
    return pd.DataFrame(columns=AUDIT_COLUMNS)


def empty_coverage() -> dict[str, object]:
    return {
        "source_delivery_rows": 0,
        "semantic_duplicate_rows_removed": 0,
        "eligible_bowling_delivery_rows": 0,
        "eligible_bowling_innings": 0,
        "matches_with_ball_by_ball": 0,
        "candidate_windows": 0,
        "confirmed": 0,
        "rejected": 0,
        "ambiguous": 0,
    }
