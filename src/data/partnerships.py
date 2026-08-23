"""Reusable validation and preparation for cricket batting partnerships."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

import pandas as pd

from src.utils.player_identity import is_private_or_anonymised_player


EVENT_COLUMNS = [
    "record_id",
    "player_1_canonical_id",
    "player_1_name",
    "player_2_canonical_id",
    "player_2_name",
    "runs",
    "balls",
    "wickets_lost",
    "wicket_number",
    "partnership_type",
    "season",
    "match_id",
    "innings_id",
    "match_date",
    "team_name",
    "opponent",
    "raw_grade_name",
    "display_grade_name",
    "source_classification",
    "evidence_quality",
    "confidence",
    "scorecard_url",
    "source_detail",
]
AUDIT_COLUMNS = EVENT_COLUMNS + [
    "validation_status",
    "review_reason",
    "innings_partnership_runs",
    "innings_scorecard_runs",
    "innings_runs_difference",
    "is_private_player",
]


@dataclass(frozen=True)
class PartnershipPreparationResult:
    events: pd.DataFrame
    audit: pd.DataFrame
    coverage: dict[str, object]


def prepare_ball_by_ball_partnerships(
    partnerships: pd.DataFrame,
    *,
    matches: pd.DataFrame,
    innings: pd.DataFrame,
    selected_team_ids_by_match: Mapping[str, set[str]],
    identity_lookup: Mapping[str, Mapping[str, str]],
    grade_display: Callable[[object], str] | None = None,
) -> PartnershipPreparationResult:
    if partnerships.empty:
        return PartnershipPreparationResult(empty_events(), empty_audit(), empty_coverage())

    rows = partnerships.copy().reset_index(drop=True)
    source_rows = len(rows)
    source_values = rows.get("source", pd.Series("", index=rows.index)).astype(str)
    rows = rows[source_values.eq("ball_by_ball")].copy()
    rows = rows[
        rows.apply(
            lambda row: str(row.get("batting_team_id"))
            in selected_team_ids_by_match.get(str(row.get("match_id")), set()),
            axis=1,
        )
    ].copy()
    rows["runs"] = pd.to_numeric(rows.get("runs"), errors="coerce")
    rows["balls"] = pd.to_numeric(rows.get("balls"), errors="coerce")
    rows["partnership_number"] = pd.to_numeric(rows.get("partnership_number"), errors="coerce")
    key_columns = ["match_id", "innings_id", "partnership_number"]
    rows["_duplicate_key"] = rows.duplicated(key_columns, keep=False)

    innings_runs = innings[["match_id", "innings_id", "runs_scored"]].drop_duplicates(["match_id", "innings_id"]).copy()
    innings_runs["runs_scored"] = pd.to_numeric(innings_runs["runs_scored"], errors="coerce")
    totals = rows.groupby(["match_id", "innings_id"], as_index=False)["runs"].sum(min_count=1)
    totals = totals.rename(columns={"runs": "innings_partnership_runs"})
    totals = totals.merge(innings_runs, on=["match_id", "innings_id"], how="left")
    totals = totals.rename(columns={"runs_scored": "innings_scorecard_runs"})
    totals["innings_runs_difference"] = totals["innings_partnership_runs"] - totals["innings_scorecard_runs"]
    rows = rows.merge(totals, on=["match_id", "innings_id"], how="left")

    match_lookup = frame_lookup(matches, "match_id")
    audit_rows: list[dict[str, object]] = []
    event_rows: list[dict[str, object]] = []
    for _, row in rows.iterrows():
        match_id = clean_text(row.get("match_id"))
        innings_id = clean_text(row.get("innings_id"))
        match = match_lookup.get(match_id, {})
        player_1 = resolved_player(row.get("batter_1_participant_id"), row.get("batter_1_name"), identity_lookup)
        player_2 = resolved_player(row.get("batter_2_participant_id"), row.get("batter_2_name"), identity_lookup)
        raw_grade = clean_text(match.get("grade_name"))
        display_grade = grade_display(raw_grade) if grade_display else raw_grade
        team_name, opponent = team_and_opponent(row, match)
        wicket_number = numeric_int(row.get("partnership_number"))
        event = {
            "record_id": f"bbb:{match_id}:{innings_id}:{wicket_number or 'unknown'}",
            "player_1_canonical_id": player_1[0],
            "player_1_name": player_1[1],
            "player_2_canonical_id": player_2[0],
            "player_2_name": player_2[1],
            "runs": numeric_number(row.get("runs")),
            "balls": numeric_number(row.get("balls")),
            "wickets_lost": partnership_wickets_lost(row),
            "wicket_number": wicket_number,
            "partnership_type": partnership_type_label(wicket_number),
            "season": clean_text(match.get("season")),
            "match_id": match_id,
            "innings_id": innings_id,
            "match_date": clean_text(match.get("first_match_day"))[:10],
            "team_name": team_name,
            "opponent": opponent,
            "raw_grade_name": raw_grade,
            "display_grade_name": display_grade,
            "source_classification": "ball_by_ball_calculated",
            "evidence_quality": "innings_total_reconciled",
            "confidence": "high",
            "scorecard_url": f"https://play.cricket.com.au/match/{match_id}" if match_id else "",
            "source_detail": "PlayCricket chronological delivery data; partnership totals reconcile to the innings scorecard.",
        }
        private = any(is_private_or_anonymised_player(value) for value in [player_1[1], player_2[1], row.get("batter_1_name"), row.get("batter_2_name")])
        status, reason = partnership_validation_status(row, player_1, player_2, private)
        audit_row = {
            **event,
            "validation_status": status,
            "review_reason": reason,
            "innings_partnership_runs": numeric_number(row.get("innings_partnership_runs")),
            "innings_scorecard_runs": numeric_number(row.get("innings_scorecard_runs")),
            "innings_runs_difference": numeric_number(row.get("innings_runs_difference")),
            "is_private_player": private,
        }
        audit_rows.append(audit_row)
        if status == "CONFIRMED":
            event_rows.append(event)

    audit = pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS)
    events = pd.DataFrame(event_rows, columns=EVENT_COLUMNS)
    if not audit.empty:
        audit = audit.sort_values(["season", "match_id", "innings_id", "wicket_number"], na_position="last").reset_index(drop=True)
    if not events.empty:
        events = events.drop_duplicates("record_id").sort_values(
            ["season", "match_date", "match_id", "innings_id", "wicket_number"],
            na_position="last",
        ).reset_index(drop=True)
    statuses = audit.get("validation_status", pd.Series(dtype=str))
    coverage = {
        "source_partnership_rows": source_rows,
        "club_ball_by_ball_rows": len(rows),
        "confirmed_events": int(statuses.eq("CONFIRMED").sum()),
        "review_events": int(statuses.eq("REVIEW").sum()),
        "private_events_excluded": int(statuses.eq("EXCLUDED_PRIVATE").sum()),
        "matches": int(rows["match_id"].nunique()) if not rows.empty else 0,
        "innings": int(rows["innings_id"].nunique()) if not rows.empty else 0,
    }
    return PartnershipPreparationResult(events, audit, coverage)


def build_partnership_record_holders(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return empty_events()
    rows = events.copy()
    rows["runs"] = pd.to_numeric(rows["runs"], errors="coerce")
    rows["wicket_number"] = pd.to_numeric(rows["wicket_number"], errors="coerce")
    rows = rows[rows["runs"].notna() & rows["wicket_number"].between(1, 10, inclusive="both")].copy()
    if rows.empty:
        return empty_events()
    rows["_source_priority"] = rows["source_classification"].map({"ball_by_ball_calculated": 0, "customer_document": 1}).fillna(2)
    rows = rows.sort_values(
        ["wicket_number", "runs", "_source_priority", "season", "record_id"],
        ascending=[True, False, True, False, True],
    )
    return rows.drop_duplicates("wicket_number", keep="first").drop(columns="_source_priority").reset_index(drop=True)[EVENT_COLUMNS]


def combine_partnership_events(*frames: pd.DataFrame) -> pd.DataFrame:
    available = [frame[EVENT_COLUMNS].copy() for frame in frames if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not available:
        return empty_events()
    rows = pd.concat(available, ignore_index=True).drop_duplicates("record_id", keep="first")
    pair_ids = rows[["player_1_canonical_id", "player_2_canonical_id"]].fillna("").astype(str)
    rows["_pair_key"] = pair_ids.apply(lambda row: "|".join(sorted(row.tolist())), axis=1)
    rows["_equivalent_key"] = (
        rows["season"].fillna("").astype(str)
        + "|"
        + pd.to_numeric(rows["wicket_number"], errors="coerce").fillna(-1).astype(str)
        + "|"
        + pd.to_numeric(rows["runs"], errors="coerce").fillna(-1).astype(str)
        + "|"
        + rows["_pair_key"]
    )
    primary_keys = set(rows.loc[rows["source_classification"].eq("ball_by_ball_calculated"), "_equivalent_key"])
    duplicate_document = rows["source_classification"].eq("customer_document") & rows["_equivalent_key"].isin(primary_keys)
    rows = rows.loc[~duplicate_document].copy()
    return rows.drop(columns=["_pair_key", "_equivalent_key"]).sort_values("record_id").reset_index(drop=True)[EVENT_COLUMNS]


def partnership_validation_status(
    row: pd.Series,
    player_1: tuple[str, str],
    player_2: tuple[str, str],
    private: bool,
) -> tuple[str, str]:
    if private:
        return "EXCLUDED_PRIVATE", "One or both batters are private or masked."
    if bool(row.get("_duplicate_key")):
        return "REVIEW", "Duplicate match/innings/partnership key."
    if not all([player_1[0], player_1[1], player_2[0], player_2[1]]):
        return "REVIEW", "Canonical identity is missing for one or both batters."
    if player_1[0] == player_2[0]:
        return "REVIEW", "Both source participants resolve to the same canonical player."
    runs = pd.to_numeric(row.get("runs"), errors="coerce")
    if pd.isna(runs) or float(runs) < 0:
        return "REVIEW", "Partnership runs are missing or invalid."
    difference = pd.to_numeric(row.get("innings_runs_difference"), errors="coerce")
    if pd.isna(difference) or abs(float(difference)) > 1e-9:
        return "REVIEW", "Partnership rows do not reconcile to the innings scorecard total."
    return "CONFIRMED", "Canonical batter pair and delivery-derived runs reconcile to the innings scorecard total."


def resolved_player(
    participant_id: object,
    source_name: object,
    identity_lookup: Mapping[str, Mapping[str, str]],
) -> tuple[str, str]:
    raw_id = clean_text(participant_id)
    mapped = identity_lookup.get(raw_id, {})
    return clean_text(mapped.get("canonical_player_id")), clean_text(mapped.get("canonical_player_name"))


def partnership_wickets_lost(row: pd.Series) -> int:
    dismissal = clean_text(row.get("dismissal_type")).casefold()
    if not clean_text(row.get("wicket_ending_participant_id")) or dismissal in {"", "not out", "retired not out", "retired hurt"}:
        return 0
    return 1


def partnership_type_label(wicket_number: int | None) -> str:
    if wicket_number is None:
        return "Unknown wicket"
    if wicket_number == 1:
        return "Opening partnership"
    suffix = "th" if 10 <= wicket_number % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(wicket_number % 10, "th")
    return f"{wicket_number}{suffix} wicket partnership"


def team_and_opponent(row: pd.Series, match: Mapping[str, object]) -> tuple[str, str]:
    batting_id = clean_text(row.get("batting_team_id"))
    home_id = clean_text(match.get("home_team_id"))
    away_id = clean_text(match.get("away_team_id"))
    home_name = clean_text(match.get("home_team_name"))
    away_name = clean_text(match.get("away_team_name"))
    if batting_id == home_id:
        return home_name, away_name
    if batting_id == away_id:
        return away_name, home_name
    return "", ""


def frame_lookup(frame: pd.DataFrame, key_column: str) -> dict[str, dict[str, object]]:
    if frame.empty or key_column not in frame:
        return {}
    rows = frame.drop_duplicates(key_column).copy()
    rows[key_column] = rows[key_column].astype(str)
    return rows.set_index(key_column).to_dict("index")


def numeric_number(value: object) -> int | float | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    return int(number) if float(number).is_integer() else float(number)


def numeric_int(value: object) -> int | None:
    number = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(number) else int(number)


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"", "nan", "none", "nat"} else text


def empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=EVENT_COLUMNS)


def empty_audit() -> pd.DataFrame:
    return pd.DataFrame(columns=AUDIT_COLUMNS)


def empty_coverage() -> dict[str, object]:
    return {
        "source_partnership_rows": 0,
        "club_ball_by_ball_rows": 0,
        "confirmed_events": 0,
        "review_events": 0,
        "private_events_excluded": 0,
        "matches": 0,
        "innings": 0,
    }
