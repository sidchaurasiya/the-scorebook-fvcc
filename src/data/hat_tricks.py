"""Shared, source-driven cricket hat-trick detection."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
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
    "innings_number",
    "match_date",
    "opponent",
    "team_name",
    "grade_name",
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
    "innings_number",
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


@dataclass(frozen=True)
class GovernedHatTrickBuildResult:
    events: pd.DataFrame
    audit: pd.DataFrame
    coverage: pd.DataFrame
    source_issues: pd.DataFrame
    validation: pd.DataFrame


def detect_hat_tricks(
    ball_by_ball: pd.DataFrame,
    *,
    matches: pd.DataFrame | None = None,
    bowling_scorecard: pd.DataFrame | None = None,
    batting_scorecard: pd.DataFrame | None = None,
    selected_team_ids_by_match: Mapping[str, set[str]] | None = None,
    identity_lookup: Mapping[str, Mapping[str, str]] | None = None,
    coverage_note: str = "Hat-tricks identified from available detailed records.",
    evidence_source: str = "PlayCricket ball-by-ball + bowling and batting scorecards",
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
    rows["_raw_bowler_id"] = rows["bowler_participant_id"].map(clean_text)
    rows["_identity_resolved"] = rows["_raw_bowler_id"].map(
        lambda value: bool(
            clean_text(identity_lookup.get(value, {}).get("canonical_player_id"))
            and clean_text(identity_lookup.get(value, {}).get("canonical_player_name"))
        )
    )
    rows["_canonical_bowler_id"] = rows["_raw_bowler_id"].map(
        lambda value: clean_text(identity_lookup.get(value, {}).get("canonical_player_id")) or value
    )
    rows["_canonical_bowler_name"] = rows.apply(
        lambda row: clean_text(identity_lookup.get(clean_text(row.get("bowler_participant_id")), {}).get("canonical_player_name"))
        or clean_text(row.get("bowler_short_name"))
        or "Unknown player",
        axis=1,
    )
    conflict_coordinates = conflicting_delivery_coordinates(rows)
    missing_bowler_matches = set(
        rows.loc[rows["_raw_bowler_id"].eq(""), "match_id"].dropna().astype(str)
    )

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
            innings_number_values = pd.to_numeric(
                sequence.get("innings_number", pd.Series(index=sequence.index, dtype=float)),
                errors="coerce",
            ).dropna()
            innings_numbers = [
                str(int(value)) if float(value).is_integer() else str(value)
                for value in dict.fromkeys(innings_number_values)
            ]
            innings_number_label = " | ".join(innings_numbers)
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
            if str(match_id) in missing_bowler_matches:
                status = "AMBIGUOUS / REVIEW"
                reason = "The match contains delivery rows with missing bowler identity that could affect personal-sequence continuity."
            if not bool(sequence["_identity_resolved"].all()):
                status = "AMBIGUOUS / REVIEW"
                reason = "Bowler identity does not resolve to a canonical player ID and public name."
            private_player = is_private_or_anonymised_player(player_name)
            if private_player:
                status = "REJECTED"
                reason = "Canonical bowler identity is private or masked."
            labels = [delivery_label(row) for _, row in sequence.iterrows()]
            dismissals = [clean_text(value) for value in sequence["dismissal_type"]]
            dismissed_ids = [clean_text(value) for value in sequence["dismissed_participant_id"]]
            wide_values = [numeric_extra(row.get("wides")) for _, row in sequence.iterrows()]
            no_ball_values = [numeric_extra(row.get("no_balls")) for _, row in sequence.iterrows()]
            event_id = hat_trick_event_id(str(match_id), innings_ids, sequence)
            source_evidence = (
                "PlayCricket ball-by-ball"
                f"; scorecard credited wickets={format_optional_number(scorecard_wickets)}"
                f"; batting dismissals verified={batting_verified}/3"
            )
            audit_row = {
                "event_id": event_id,
                "player": player_name,
                "canonical_player_id": canonical_id,
                "season": clean_text(match.get("season")),
                "match_id": str(match_id),
                "innings_id": innings_label,
                "innings_number": innings_number_label,
                "match_date": clean_text(match.get("first_match_day"))[:10],
                "opponent": opponent,
                "team_name": team_name,
                "grade_name": clean_text(match.get("grade_name")),
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
                "is_private_player": private_player,
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
                        "innings_number": innings_number_label,
                        "match_date": clean_text(match.get("first_match_day"))[:10],
                        "team_name": team_name,
                        "opponent": opponent,
                        "grade_name": clean_text(match.get("grade_name")),
                        "delivery_sequence": " · ".join(labels),
                        "dismissal_sequence": " · ".join(dismissals),
                        "spans_overs": sequence_spans_overs(sequence),
                        "spans_innings": len(innings_ids) > 1,
                        "scorecard_wickets": scorecard_wickets,
                        "evidence_source": evidence_source,
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
        "matches_with_usable_bowling_evidence": int(rows.loc[rows["_raw_bowler_id"].ne(""), "match_id"].nunique()),
        "credited_bowler_wickets": int(rows["bowler_wicket"].sum()),
        "missing_bowler_identity_wickets": int(
            (
                rows["is_wicket_bool"]
                & rows["dismissal_key"].isin(BOWLER_WICKET_DISMISSALS)
                & rows["_raw_bowler_id"].eq("")
            ).sum()
        ),
        "unknown_dismissal_semantics": int(unknown_dismissal_mask(rows).sum()),
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
    original_rows = len(rows)
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
    return rows, (original_rows - before) + (before - len(rows))


def unknown_dismissal_mask(rows: pd.DataFrame) -> pd.Series:
    known = BOWLER_WICKET_DISMISSALS | NON_BOWLER_DISMISSALS
    return rows["is_wicket_bool"] & ~rows["dismissal_key"].isin(known)


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


def build_governed_club_hat_tricks(
    *,
    club_id: str,
    match_centre_root: Path,
    club_processed_root: Path,
    coverage_note: str = "Hat-tricks identified from available verified ball-by-ball records.",
) -> GovernedHatTrickBuildResult:
    """Build a club's governed public records from ignored local source files."""
    matches, balls, batting = load_hat_trick_sources(match_centre_root)
    selected = {
        str(row.match_id): parse_source_team_ids(row.source_team_ids)
        for row in matches.itertuples()
    }
    identity_lookup = build_club_identity_lookup(club_processed_root)
    bowling = derive_bowling_scorecard_from_batting(batting)
    detected = detect_hat_tricks(
        balls,
        matches=matches,
        bowling_scorecard=bowling,
        batting_scorecard=batting,
        selected_team_ids_by_match=selected,
        identity_lookup=identity_lookup,
        coverage_note=coverage_note,
        evidence_source="PlayCricket ball-by-ball + batting scorecard dismissal reconciliation",
    )
    events = public_hat_trick_events(detected.events)
    prepared_rows, _ = prepare_delivery_rows(balls)
    prepared_rows = prepared_rows[
        prepared_rows.apply(
            lambda row: clean_text(row.get("bowling_team_id"))
            in selected.get(clean_text(row.get("match_id")), set()),
            axis=1,
        )
    ].copy()
    prepared_rows["_raw_bowler_id"] = prepared_rows["bowler_participant_id"].map(clean_text)
    issues = build_hat_trick_source_issue_audit(
        prepared_rows,
        matches=matches,
        batting=batting,
        identity_lookup=identity_lookup,
        candidate_match_ids=set(detected.audit.get("match_id", pd.Series(dtype=str)).astype(str)),
    )
    club_team_ids = set().union(*selected.values()) if selected else set()
    club_scorecard_matches = int(
        batting.loc[batting.get("team_id", pd.Series(dtype=str)).astype(str).isin(club_team_ids), "match_id"].nunique()
    )
    source_bbb = bool_series(matches.get("is_ball_by_ball", pd.Series(False, index=matches.index)))
    coverage = pd.DataFrame(
        [
            {
                "club_id": club_id,
                "source_matches": int(matches["match_id"].nunique()),
                "club_scorecard_matches": club_scorecard_matches,
                "source_matches_with_ball_by_ball": int(matches.loc[source_bbb, "match_id"].nunique()),
                "matches_with_usable_bowling_evidence": detected.coverage["matches_with_usable_bowling_evidence"],
                "source_delivery_rows": detected.coverage["source_delivery_rows"],
                "delivery_rows_examined": detected.coverage["eligible_bowling_delivery_rows"],
                "credited_bowler_wickets": detected.coverage["credited_bowler_wickets"],
                "candidate_sequences": detected.coverage["candidate_windows"],
                "confirmed_candidates": detected.coverage["confirmed"],
                "rejected_candidates": detected.coverage["rejected"],
                "review_candidates": detected.coverage["ambiguous"],
                "semantic_duplicate_rows_removed": detected.coverage["semantic_duplicate_rows_removed"],
                "missing_bowler_identity_wickets": detected.coverage["missing_bowler_identity_wickets"],
                "unknown_dismissal_semantics": detected.coverage["unknown_dismissal_semantics"],
            }
        ]
    )
    validation = build_hat_trick_validation(events, detected.audit, coverage, issues)
    return GovernedHatTrickBuildResult(events, detected.audit, coverage, issues, validation)


def load_hat_trick_sources(match_centre_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    required = ("all_matches.csv", "all_ball_by_ball.csv", "all_scorecard_batting.csv")
    scopes = [match_centre_root] if all((match_centre_root / name).exists() for name in required) else []
    scopes.extend(
        child
        for child in sorted(match_centre_root.iterdir() if match_centre_root.exists() else [])
        if child.is_dir() and all((child / name).exists() for name in required)
    )
    if not scopes:
        raise FileNotFoundError(f"No complete restored match-centre scope found under {match_centre_root}.")
    matches = pd.concat([pd.read_csv(scope / required[0], low_memory=False) for scope in scopes], ignore_index=True)
    balls = pd.concat([pd.read_csv(scope / required[1], low_memory=False) for scope in scopes], ignore_index=True)
    batting = pd.concat([pd.read_csv(scope / required[2], low_memory=False) for scope in scopes], ignore_index=True)
    matches = matches.drop_duplicates("match_id", keep="last").reset_index(drop=True)
    if "ball_event_id" in balls:
        balls = balls.drop_duplicates("ball_event_id", keep="last").reset_index(drop=True)
    batting_key = [column for column in ["match_id", "innings_id", "participant_id", "bat_instance"] if column in batting]
    batting = batting.drop_duplicates(batting_key, keep="last").reset_index(drop=True)
    return matches, balls, batting


def parse_source_team_ids(value: object) -> set[str]:
    text = clean_text(value).replace(";", ",").replace("|", ",")
    return {token.strip() for token in text.split(",") if token.strip()}


def build_club_identity_lookup(club_processed_root: Path) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for filename in ["all_seasons_bowling.csv", "all_seasons_batting.csv"]:
        path = club_processed_root / filename
        if not path.exists():
            continue
        rows = pd.read_csv(path, low_memory=False)
        required = {"raw_player_id", "canonical_player_id", "canonical_player_name"}
        if not required.issubset(rows.columns):
            continue
        for row in rows[list(required)].drop_duplicates().itertuples(index=False):
            raw_id = clean_text(getattr(row, "raw_player_id"))
            canonical_id = clean_text(getattr(row, "canonical_player_id"))
            canonical_name = clean_text(getattr(row, "canonical_player_name"))
            if raw_id and canonical_id and canonical_name:
                lookup.setdefault(
                    raw_id,
                    {"canonical_player_id": canonical_id, "canonical_player_name": canonical_name},
                )
    return lookup


def derive_bowling_scorecard_from_batting(batting: pd.DataFrame) -> pd.DataFrame:
    """Derive per-innings wicket credit from independent batting scorecard rows."""
    columns = ["match_id", "innings_id", "participant_id", "wickets_taken"]
    if batting.empty or "bowler_participant_id" not in batting:
        return pd.DataFrame(columns=columns)
    rows = batting.copy()
    rows["dismissal_key"] = rows.get("dismissal_type", pd.Series("", index=rows.index)).map(normalize_dismissal_type)
    rows = rows[
        rows["dismissal_key"].isin(BOWLER_WICKET_DISMISSALS)
        & rows["bowler_participant_id"].map(clean_text).ne("")
    ].copy()
    if rows.empty:
        return pd.DataFrame(columns=columns)
    grouped = (
        rows.groupby(["match_id", "innings_id", "bowler_participant_id"], dropna=False)
        .size()
        .rename("wickets_taken")
        .reset_index()
        .rename(columns={"bowler_participant_id": "participant_id"})
    )
    return grouped[columns]


def build_hat_trick_source_issue_audit(
    rows: pd.DataFrame,
    *,
    matches: pd.DataFrame,
    batting: pd.DataFrame,
    identity_lookup: Mapping[str, Mapping[str, str]],
    candidate_match_ids: set[str],
) -> pd.DataFrame:
    columns = [
        "issue_type",
        "classification",
        "match_id",
        "innings_id",
        "season",
        "grade_name",
        "delivery",
        "dismissal_type",
        "dismissed_participant_id",
        "scorecard_bowler_participant_id",
        "scorecard_bowler_canonical_id",
        "scorecard_bowler_name",
        "affects_confirmed_candidate",
        "detail",
    ]
    if rows.empty:
        return pd.DataFrame(columns=columns)
    match_lookup = frame_lookup(matches, "match_id")
    batting_lookup = prepare_batting_lookup(batting)
    issue_rows: list[dict[str, object]] = []
    missing_bowler = (
        rows["_raw_bowler_id"].eq("")
        & rows["is_wicket_bool"]
        & rows["dismissal_key"].isin(BOWLER_WICKET_DISMISSALS)
    )
    for _, row in rows.loc[missing_bowler].iterrows():
        match_id = clean_text(row.get("match_id"))
        innings_id = clean_text(row.get("innings_id"))
        dismissed_id = clean_text(row.get("dismissed_participant_id"))
        scorecard = batting_lookup.get((match_id, innings_id, dismissed_id), {})
        scorecard_bowler = clean_text(scorecard.get("bowler_participant_id"))
        canonical = identity_lookup.get(scorecard_bowler, {})
        malformed = not dismissed_id
        issue_rows.append(
            {
                "issue_type": "missing_bowler_identity",
                "classification": "D" if malformed else "C",
                "match_id": match_id,
                "innings_id": innings_id,
                "season": clean_text(match_lookup.get(match_id, {}).get("season")),
                "grade_name": clean_text(match_lookup.get(match_id, {}).get("grade_name")),
                "delivery": delivery_label(row),
                "dismissal_type": clean_text(row.get("dismissal_type")),
                "dismissed_participant_id": dismissed_id,
                "scorecard_bowler_participant_id": scorecard_bowler,
                "scorecard_bowler_canonical_id": clean_text(canonical.get("canonical_player_id")),
                "scorecard_bowler_name": clean_text(canonical.get("canonical_player_name")),
                "affects_confirmed_candidate": match_id in candidate_match_ids,
                "detail": (
                    "Malformed wicket row has no dismissed participant, so scorecard attribution is unavailable."
                    if malformed
                    else "Batting scorecard may identify the wicket bowler, but missing delivery-level bowler data prevents governed personal-sequence reconstruction."
                ),
            }
        )
    unknown = unknown_dismissal_mask(rows)
    for _, row in rows.loc[unknown].iterrows():
        match_id = clean_text(row.get("match_id"))
        issue_rows.append(
            {
                "issue_type": "unknown_dismissal_semantics",
                "classification": "C",
                "match_id": match_id,
                "innings_id": clean_text(row.get("innings_id")),
                "season": clean_text(match_lookup.get(match_id, {}).get("season")),
                "grade_name": clean_text(match_lookup.get(match_id, {}).get("grade_name")),
                "delivery": delivery_label(row),
                "dismissal_type": clean_text(row.get("dismissal_type")),
                "dismissed_participant_id": clean_text(row.get("dismissed_participant_id")),
                "scorecard_bowler_participant_id": "",
                "scorecard_bowler_canonical_id": "",
                "scorecard_bowler_name": "",
                "affects_confirmed_candidate": match_id in candidate_match_ids,
                "detail": "Provider dismissal label is not governed as bowler-credit or non-bowler-credit.",
            }
        )
    return pd.DataFrame(issue_rows, columns=columns)


def build_hat_trick_validation(
    events: pd.DataFrame,
    audit: pd.DataFrame,
    coverage: pd.DataFrame,
    source_issues: pd.DataFrame,
) -> pd.DataFrame:
    statuses = audit.get("validation_status", pd.Series(dtype=str)).fillna("").astype(str)
    confirmed_ids = set(audit.loc[statuses.eq("CONFIRMED"), "event_id"].astype(str)) if not audit.empty else set()
    public_ids = set(events.get("event_id", pd.Series(dtype=str)).dropna().astype(str))
    affected = source_issues.get("affects_confirmed_candidate", pd.Series(False, index=source_issues.index))
    affected = affected.astype(str).str.casefold().isin({"true", "1", "yes"})
    checks = [
        ("candidate_counts_reconcile", len(audit) == int(coverage.iloc[0]["candidate_sequences"]), f"rows={len(audit)}"),
        ("confirmed_publication_reconciles", public_ids == confirmed_ids, f"public={len(public_ids)} confirmed={len(confirmed_ids)}"),
        ("no_duplicate_candidates", not audit.get("event_id", pd.Series(dtype=str)).duplicated().any(), f"rows={len(audit)}"),
        ("no_duplicate_public_events", not events.get("event_id", pd.Series(dtype=str)).duplicated().any(), f"rows={len(events)}"),
        (
            "canonical_public_identities_present",
            events.get("canonical_player_id", pd.Series(dtype=str)).map(clean_text).ne("").all()
            and events.get("canonical_player_name", pd.Series(dtype=str)).map(clean_text).ne("").all(),
            f"rows={len(events)}",
        ),
        (
            "no_private_public_players",
            not events.get("canonical_player_name", pd.Series(dtype=str)).map(is_private_or_anonymised_player).any(),
            "masked identities excluded",
        ),
        (
            "source_gaps_do_not_affect_confirmed_candidates",
            not bool(affected.any()),
            f"affected={int(affected.sum())}",
        ),
    ]
    return pd.DataFrame(
        [{"check": name, "status": "PASS" if passed else "FAIL", "detail": detail} for name, passed, detail in checks]
        + [{"check": key, "status": "INFO", "detail": str(value)} for key, value in coverage.iloc[0].items()]
    )


def write_governed_hat_trick_outputs(
    result: GovernedHatTrickBuildResult,
    *,
    hall_of_fame_output: Path,
    validation_dir: Path,
    prefix: str,
) -> None:
    hall_of_fame_output.parent.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)
    write_csv_atomic(result.events, hall_of_fame_output)
    write_csv_atomic(result.audit, validation_dir / f"{prefix}_hat_trick_candidate_audit.csv")
    write_csv_atomic(result.coverage, validation_dir / f"{prefix}_hat_trick_coverage.csv")
    write_csv_atomic(result.source_issues, validation_dir / f"{prefix}_hat_trick_source_issue_audit.csv")
    write_csv_atomic(result.validation, validation_dir / f"{prefix}_hat_trick_validation.csv")


def write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


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
        "matches_with_usable_bowling_evidence": 0,
        "credited_bowler_wickets": 0,
        "missing_bowler_identity_wickets": 0,
        "unknown_dismissal_semantics": 0,
        "candidate_windows": 0,
        "confirmed": 0,
        "rejected": 0,
        "ambiguous": 0,
    }
