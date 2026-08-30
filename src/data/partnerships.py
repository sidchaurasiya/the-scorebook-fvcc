"""Reusable validation and preparation for cricket batting partnerships."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping

import pandas as pd

from src.data.match_centre_parser import build_ball_partnerships
from src.utils.player_identity import apply_player_identity_mapping, is_private_or_anonymised_player


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
    "privacy_status",
]
AUDIT_COLUMNS = EVENT_COLUMNS + [
    "validation_status",
    "review_reason",
    "innings_partnership_runs",
    "innings_scorecard_runs",
    "innings_runs_difference",
    "is_private_player",
]
UNRESOLVED_PARTNERSHIP_REVIEW_REASONS = frozenset(
    {
        "Canonical identity is missing for one or both batters.",
        "Incomplete or invalid two-batter delivery sequence.",
    }
)
PUBLIC_PARTNERSHIP_COLUMNS = [
    "partnership_id",
    "batter_1",
    "batter_2",
    "batter_1_public_name",
    "batter_2_public_name",
    "partnership_runs",
    "balls_faced",
    "wicket_number",
    "match_id",
    "season",
    "grade",
    "opponent",
    "innings",
    "innings_id",
    "batting_team",
    "end_context",
    "reconciliation_status",
    "innings_scorecard_total",
    "innings_reconstructed_total",
    "reconciliation_difference",
    "privacy_status",
    "match_date",
    "scorecard_url",
    "source_detail",
]


@dataclass(frozen=True)
class PartnershipPreparationResult:
    events: pd.DataFrame
    audit: pd.DataFrame
    coverage: dict[str, object]


@dataclass(frozen=True)
class GovernedClubPartnershipResult:
    events: pd.DataFrame
    records: pd.DataFrame
    coverage: pd.DataFrame
    privacy_audit: pd.DataFrame
    identity_audit: pd.DataFrame
    reconciliation_audit: pd.DataFrame
    rejected: pd.DataFrame
    record_selection_audit: pd.DataFrame


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
        player_1 = governed_batter_identity(
            row.get("batter_1_participant_id"), row.get("batter_1_name"), identity_lookup
        )
        player_2 = governed_batter_identity(
            row.get("batter_2_participant_id"), row.get("batter_2_name"), identity_lookup
        )
        privacy_status = governed_partnership_privacy_status(player_1, player_2)
        public_1 = public_batter_identity(player_1)
        public_2 = public_batter_identity(player_2)
        raw_grade = clean_text(match.get("grade_name"))
        display_grade = grade_display(raw_grade) if grade_display else raw_grade
        team_name, opponent = team_and_opponent(row, match)
        wicket_number = numeric_int(row.get("partnership_number"))
        event = {
            "record_id": f"bbb:{match_id}:{innings_id}:{wicket_number or 'unknown'}",
            "player_1_canonical_id": public_1[0],
            "player_1_name": public_1[1],
            "player_2_canonical_id": public_2[0],
            "player_2_name": public_2[1],
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
            "privacy_status": privacy_status,
        }
        status, reason = partnership_validation_status(row, player_1, player_2, privacy_status)
        audit_row = {
            **event,
            "validation_status": status,
            "review_reason": reason,
            "innings_partnership_runs": numeric_number(row.get("innings_partnership_runs")),
            "innings_scorecard_runs": numeric_number(row.get("innings_scorecard_runs")),
            "innings_runs_difference": numeric_number(row.get("innings_runs_difference")),
            "is_private_player": privacy_status != "PUBLIC_PUBLIC",
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
        "public_public_events": int(events.get("privacy_status", pd.Series(dtype=str)).eq("PUBLIC_PUBLIC").sum()),
        "public_private_events": int(events.get("privacy_status", pd.Series(dtype=str)).eq("PUBLIC_PRIVATE").sum()),
        "private_private_events_excluded": int(
            audit.get("privacy_status", pd.Series(dtype=str)).eq("PRIVATE_PRIVATE").sum()
        ),
        "unresolved_events_excluded": int(
            unresolved_partnership_review_mask(audit.get("review_reason", pd.Series(dtype=str))).sum()
        ),
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
    if "privacy_status" in rows:
        rows = rows[rows["privacy_status"].isin({"PUBLIC_PUBLIC", "PUBLIC_PRIVATE"})].copy()
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
    player_1: Mapping[str, object],
    player_2: Mapping[str, object],
    privacy_status: str,
) -> tuple[str, str]:
    if bool(row.get("_duplicate_key")):
        return "REVIEW", "Duplicate match/innings/partnership key."
    raw_ids = [clean_text(player_1.get("raw_id")), clean_text(player_2.get("raw_id"))]
    if not all(raw_ids) or raw_ids[0] == raw_ids[1]:
        return "REVIEW", "Incomplete or invalid two-batter delivery sequence."
    if privacy_status == "PRIVATE_PRIVATE":
        return "EXCLUDED_PRIVATE", "Both batters are private or masked."
    public_players = [player for player in [player_1, player_2] if not bool(player.get("private"))]
    if any(not bool(player.get("resolved")) for player in public_players):
        return "REVIEW", "Canonical identity is missing for one or both batters."
    canonical_ids = [clean_text(player_1.get("canonical_id")), clean_text(player_2.get("canonical_id"))]
    if all(canonical_ids) and canonical_ids[0] == canonical_ids[1]:
        return "REVIEW", "Both source participants resolve to the same canonical player."
    runs = pd.to_numeric(row.get("runs"), errors="coerce")
    if pd.isna(runs) or float(runs) < 0:
        return "REVIEW", "Partnership runs are missing or invalid."
    difference = pd.to_numeric(row.get("innings_runs_difference"), errors="coerce")
    if pd.isna(difference) or abs(float(difference)) > 1e-9:
        return "REVIEW", "Partnership rows do not reconcile to the innings scorecard total."
    if privacy_status == "PUBLIC_PRIVATE":
        return "CONFIRMED", "Public batter identity and redacted private partner reconcile to the innings scorecard total."
    return "CONFIRMED", "Canonical batter pair and delivery-derived runs reconcile to the innings scorecard total."


def unresolved_partnership_review_mask(values: pd.Series) -> pd.Series:
    return values.fillna("").astype(str).str.strip().isin(UNRESOLVED_PARTNERSHIP_REVIEW_REASONS)


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


def build_governed_club_partnerships(
    *,
    club_id: str,
    match_centre_root: Path,
) -> GovernedClubPartnershipResult:
    """Build safe, delivery-only club partnerships without changing GWHCC policy."""
    matches, innings, balls, batting, source_delivery_rows, duplicates_removed = load_partnership_sources(
        match_centre_root
    )
    selected = {
        str(row.match_id): parse_source_team_ids(row.source_team_ids)
        for row in matches.itertuples()
    }
    club_balls = balls[
        balls.apply(
            lambda row: clean_text(row.get("batting_team_id"))
            in selected.get(clean_text(row.get("match_id")), set()),
            axis=1,
        )
    ].copy()
    partnership_rows = build_ball_partnerships(club_balls)
    identity_lookup = build_club_partnership_identity_lookup(batting, selected, club_id)
    match_lookup = frame_lookup(matches, "match_id")
    innings_lookup = frame_lookup(innings, "innings_id")

    partnership_rows["runs"] = pd.to_numeric(partnership_rows.get("runs"), errors="coerce")
    partnership_rows["balls"] = pd.to_numeric(partnership_rows.get("balls"), errors="coerce")
    partnership_rows["partnership_number"] = pd.to_numeric(
        partnership_rows.get("partnership_number"), errors="coerce"
    )
    key_columns = ["match_id", "innings_id", "partnership_number"]
    partnership_rows["_duplicate_key"] = partnership_rows.duplicated(key_columns, keep=False)
    innings_totals = (
        partnership_rows.groupby(["match_id", "innings_id"], as_index=False)["runs"]
        .sum(min_count=1)
        .rename(columns={"runs": "innings_reconstructed_total"})
    )
    scorecard_totals = innings[["match_id", "innings_id", "runs_scored"]].drop_duplicates(
        ["match_id", "innings_id"]
    )
    scorecard_totals = scorecard_totals.rename(columns={"runs_scored": "innings_scorecard_total"})
    innings_totals = innings_totals.merge(scorecard_totals, on=["match_id", "innings_id"], how="left")
    innings_totals["innings_scorecard_total"] = pd.to_numeric(
        innings_totals["innings_scorecard_total"], errors="coerce"
    )
    innings_totals["reconciliation_difference"] = (
        innings_totals["innings_reconstructed_total"] - innings_totals["innings_scorecard_total"]
    )
    partnership_rows = partnership_rows.merge(innings_totals, on=["match_id", "innings_id"], how="left")

    event_rows: list[dict[str, object]] = []
    rejected_rows: list[dict[str, object]] = []
    identity_rows: list[dict[str, object]] = []
    for _, row in partnership_rows.iterrows():
        match_id = clean_text(row.get("match_id"))
        innings_id = clean_text(row.get("innings_id"))
        number = numeric_int(row.get("partnership_number"))
        partnership_id = f"bbb:{match_id}:{innings_id}:{number or 'unknown'}"
        match = match_lookup.get(match_id, {})
        innings_context = innings_lookup.get(innings_id, {})
        player_1 = governed_batter_identity(
            row.get("batter_1_participant_id"), row.get("batter_1_name"), identity_lookup
        )
        player_2 = governed_batter_identity(
            row.get("batter_2_participant_id"), row.get("batter_2_name"), identity_lookup
        )
        privacy_status = governed_partnership_privacy_status(player_1, player_2)
        reason = governed_partnership_rejection_reason(row, player_1, player_2, privacy_status)
        team_name, opponent = team_and_opponent(row, match)
        base_context = {
            "partnership_id": partnership_id,
            "match_id": match_id,
            "innings_id": innings_id,
            "partnership_number": number,
            "season": clean_text(match.get("season")),
            "grade": clean_text(match.get("grade_name")),
            "opponent": opponent,
            "batting_team": team_name,
            "privacy_status": privacy_status,
        }
        if reason:
            rejected_rows.append({**base_context, "rejection_reason": reason})
            if any(label in reason.casefold() for label in ["unresolved", "incomplete"]):
                identity_rows.append(
                    {
                        **base_context,
                        "unresolved_batter_slots": int(not player_1["resolved"]) + int(not player_2["resolved"]),
                        "identity_status": "UNRESOLVED" if "unresolved" in reason.casefold() else "INCOMPLETE_PAIR",
                    }
                )
            continue

        scorecard_total = numeric_number(row.get("innings_scorecard_total"))
        reconstructed_total = numeric_number(row.get("innings_reconstructed_total"))
        difference = numeric_number(row.get("reconciliation_difference"))
        reconciliation_status = "MATCHED" if difference == 0 else "SCORE_DIFFERENCE_ACCEPTED"
        public_1 = public_batter_identity(player_1)
        public_2 = public_batter_identity(player_2)
        end_context = clean_text(row.get("dismissal_type"))
        if end_context:
            end_context = f"Partnership ended: {end_context}"
        elif clean_text(row.get("wicket_ending_participant_id")):
            end_context = "Partnership ended with a wicket event"
        else:
            end_context = "Innings ended or partnership remained unbroken"
        event_rows.append(
            {
                "partnership_id": partnership_id,
                "batter_1": public_1[0],
                "batter_2": public_2[0],
                "batter_1_public_name": public_1[1],
                "batter_2_public_name": public_2[1],
                "partnership_runs": numeric_number(row.get("runs")),
                "balls_faced": numeric_number(row.get("balls")),
                "wicket_number": number,
                "match_id": match_id,
                "season": clean_text(match.get("season")),
                "grade": clean_text(match.get("grade_name")),
                "opponent": opponent,
                "innings": numeric_int(innings_context.get("innings_number"))
                or numeric_int(innings_context.get("innings_order")),
                "innings_id": innings_id,
                "batting_team": team_name,
                "end_context": end_context,
                "reconciliation_status": reconciliation_status,
                "innings_scorecard_total": scorecard_total,
                "innings_reconstructed_total": reconstructed_total,
                "reconciliation_difference": difference,
                "privacy_status": privacy_status,
                "match_date": clean_text(match.get("first_match_day"))[:10],
                "scorecard_url": f"https://play.cricket.com.au/match/{match_id}",
                "source_detail": "Verified PlayCricket chronological ball-by-ball deliveries.",
            }
        )

    events = pd.DataFrame(event_rows, columns=PUBLIC_PARTNERSHIP_COLUMNS)
    if not events.empty:
        events["_match_date_sort"] = pd.to_datetime(events["match_date"], errors="coerce")
        events = events.sort_values(
            ["_match_date_sort", "match_id", "innings", "partnership_id"],
            ascending=[False, True, True, True],
            kind="mergesort",
            na_position="last",
        ).drop(columns="_match_date_sort").reset_index(drop=True)
    rejected = pd.DataFrame(
        rejected_rows,
        columns=[
            "partnership_id",
            "match_id",
            "innings_id",
            "partnership_number",
            "season",
            "grade",
            "opponent",
            "batting_team",
            "privacy_status",
            "rejection_reason",
        ],
    )
    identity_audit = pd.DataFrame(
        identity_rows,
        columns=[
            "partnership_id",
            "match_id",
            "innings_id",
            "partnership_number",
            "season",
            "grade",
            "opponent",
            "batting_team",
            "privacy_status",
            "unresolved_batter_slots",
            "identity_status",
        ],
    )
    reconciliation = events[events.get("reconciliation_status", pd.Series(dtype=str)).eq(
        "SCORE_DIFFERENCE_ACCEPTED"
    )].copy()
    reconciliation_columns = [
        "partnership_id",
        "match_id",
        "season",
        "grade",
        "opponent",
        "innings",
        "innings_id",
        "batting_team",
        "batter_1_public_name",
        "batter_2_public_name",
        "partnership_runs",
        "innings_scorecard_total",
        "innings_reconstructed_total",
        "reconciliation_difference",
        "reconciliation_status",
        "privacy_status",
        "source_detail",
    ]
    reconciliation = reconciliation.reindex(columns=reconciliation_columns)
    records, record_selection_audit = build_verified_partnership_record_holders(events)
    privacy_audit = build_partnership_privacy_audit(partnership_rows, events, rejected)
    coverage = pd.DataFrame(
        [
            {
                "club_id": club_id,
                "source_matches": int(matches["match_id"].nunique()),
                "source_matches_with_ball_by_ball": int(
                    bool_series(matches.get("is_ball_by_ball", pd.Series(False, index=matches.index))).sum()
                ),
                "matches_with_usable_batting_deliveries": int(club_balls["match_id"].nunique()),
                "source_delivery_rows": source_delivery_rows,
                "semantic_duplicate_delivery_rows_removed": duplicates_removed,
                "delivery_rows_examined": int(len(balls)),
                "reconstructable_innings": int(club_balls["innings_id"].nunique()),
                "candidate_partnership_rows": int(len(partnership_rows)),
                "published_partnership_rows": int(len(events)),
                "rejected_partnership_rows": int(len(rejected)),
                "matched_rows": int(events.get("reconciliation_status", pd.Series(dtype=str)).eq("MATCHED").sum()),
                "score_difference_accepted_rows": int(
                    events.get("reconciliation_status", pd.Series(dtype=str)).eq("SCORE_DIFFERENCE_ACCEPTED").sum()
                ),
                "duplicate_partnership_keys": int(partnership_rows["_duplicate_key"].sum()),
                "public_public_rows": int(events.get("privacy_status", pd.Series(dtype=str)).eq("PUBLIC_PUBLIC").sum()),
                "public_private_rows": int(events.get("privacy_status", pd.Series(dtype=str)).eq("PUBLIC_PRIVATE").sum()),
                "private_private_rows": int(
                    rejected.get("privacy_status", pd.Series(dtype=str)).eq("PRIVATE_PRIVATE").sum()
                ),
                "incomplete_identity_rows": int(len(identity_audit)),
                "record_holder_rows": int(len(records)),
            }
        ]
    )
    return GovernedClubPartnershipResult(
        events=events,
        records=records,
        coverage=coverage,
        privacy_audit=privacy_audit,
        identity_audit=identity_audit,
        reconciliation_audit=reconciliation,
        rejected=rejected,
        record_selection_audit=record_selection_audit,
    )


def build_verified_partnership_record_holders(
    events: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Select one verified maximum per wicket with stable, documented tie-breaking.

    Ties resolve by more partnership balls, then earlier match date, match ID,
    innings ID, and partnership ID. Input dataframe ordering is never used.
    """
    audit_columns = [
        "wicket_number",
        "candidate_rows",
        "selected_partnership_id",
        "selected_runs",
        "selected_balls",
        "maximum_runs",
        "maximum_run_ties",
        "selection_status",
        "validation_status",
        "tie_break_rule",
    ]
    if events.empty:
        audit = pd.DataFrame(
            [
                {
                    "wicket_number": wicket,
                    "candidate_rows": 0,
                    "selected_partnership_id": "",
                    "selected_runs": pd.NA,
                    "selected_balls": pd.NA,
                    "maximum_runs": pd.NA,
                    "maximum_run_ties": 0,
                    "selection_status": "NO_VERIFIED_RECORD",
                    "validation_status": "PASS",
                    "tie_break_rule": "runs desc; balls desc; match date asc; match ID asc; innings ID asc; partnership ID asc",
                }
                for wicket in range(1, 11)
            ],
            columns=audit_columns,
        )
        return pd.DataFrame(columns=PUBLIC_PARTNERSHIP_COLUMNS), audit

    rows = events.copy()
    rows["wicket_number"] = pd.to_numeric(rows.get("wicket_number"), errors="coerce")
    rows["partnership_runs"] = pd.to_numeric(rows.get("partnership_runs"), errors="coerce")
    rows["balls_faced"] = pd.to_numeric(rows.get("balls_faced"), errors="coerce")
    rows["_match_date_sort"] = pd.to_datetime(rows.get("match_date"), errors="coerce")
    eligible = rows[
        rows["wicket_number"].between(1, 10, inclusive="both")
        & rows["partnership_runs"].notna()
        & rows["partnership_runs"].ge(0)
        & rows.get("reconciliation_status", pd.Series("", index=rows.index)).isin(
            {"MATCHED", "SCORE_DIFFERENCE_ACCEPTED"}
        )
        & rows.get("privacy_status", pd.Series("", index=rows.index)).isin(
            {"PUBLIC_PUBLIC", "PUBLIC_PRIVATE"}
        )
    ].copy()
    eligible = eligible.drop_duplicates("partnership_id", keep="first")
    selected_rows: list[pd.Series] = []
    audit_rows: list[dict[str, object]] = []
    tie_rule = "runs desc; balls desc; match date asc; match ID asc; innings ID asc; partnership ID asc"
    for wicket in range(1, 11):
        candidates = eligible[eligible["wicket_number"].eq(wicket)].copy()
        if candidates.empty:
            audit_rows.append(
                {
                    "wicket_number": wicket,
                    "candidate_rows": 0,
                    "selected_partnership_id": "",
                    "selected_runs": pd.NA,
                    "selected_balls": pd.NA,
                    "maximum_runs": pd.NA,
                    "maximum_run_ties": 0,
                    "selection_status": "NO_VERIFIED_RECORD",
                    "validation_status": "PASS",
                    "tie_break_rule": tie_rule,
                }
            )
            continue
        maximum_runs = float(candidates["partnership_runs"].max())
        maximum_ties = int(candidates["partnership_runs"].eq(maximum_runs).sum())
        candidates = candidates.sort_values(
            [
                "partnership_runs",
                "balls_faced",
                "_match_date_sort",
                "match_id",
                "innings_id",
                "partnership_id",
            ],
            ascending=[False, False, True, True, True, True],
            kind="mergesort",
            na_position="last",
        )
        selected = candidates.iloc[0]
        selected_rows.append(selected)
        valid = (
            int(selected["wicket_number"]) == wicket
            and float(selected["partnership_runs"]) == maximum_runs
            and clean_text(selected.get("match_id")) != ""
            and clean_text(selected.get("innings_id")) != ""
        )
        audit_rows.append(
            {
                "wicket_number": wicket,
                "candidate_rows": len(candidates),
                "selected_partnership_id": clean_text(selected.get("partnership_id")),
                "selected_runs": numeric_number(selected.get("partnership_runs")),
                "selected_balls": numeric_number(selected.get("balls_faced")),
                "maximum_runs": numeric_number(maximum_runs),
                "maximum_run_ties": maximum_ties,
                "selection_status": "SELECTED",
                "validation_status": "PASS" if valid else "FAIL",
                "tie_break_rule": tie_rule,
            }
        )
    if selected_rows:
        records = pd.DataFrame(selected_rows).drop(columns="_match_date_sort", errors="ignore")
        records = records[PUBLIC_PARTNERSHIP_COLUMNS].sort_values("wicket_number").reset_index(drop=True)
    else:
        records = pd.DataFrame(columns=PUBLIC_PARTNERSHIP_COLUMNS)
    audit = pd.DataFrame(audit_rows, columns=audit_columns)
    return records, audit


def load_partnership_sources(
    match_centre_root: Path,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, int, int]:
    required = (
        "all_matches.csv",
        "all_match_innings.csv",
        "all_ball_by_ball.csv",
        "all_scorecard_batting.csv",
    )
    scopes = [match_centre_root] if all((match_centre_root / name).exists() for name in required) else []
    scopes.extend(
        child
        for child in sorted(match_centre_root.iterdir() if match_centre_root.exists() else [])
        if child.is_dir() and all((child / name).exists() for name in required)
    )
    if not scopes:
        raise FileNotFoundError(f"No complete restored match-centre scope found under {match_centre_root}.")
    matches = pd.concat([pd.read_csv(scope / required[0], low_memory=False) for scope in scopes], ignore_index=True)
    innings = pd.concat([pd.read_csv(scope / required[1], low_memory=False) for scope in scopes], ignore_index=True)
    balls = pd.concat([pd.read_csv(scope / required[2], low_memory=False) for scope in scopes], ignore_index=True)
    batting = pd.concat([pd.read_csv(scope / required[3], low_memory=False) for scope in scopes], ignore_index=True)
    matches = matches.drop_duplicates("match_id", keep="last").reset_index(drop=True)
    innings = innings.drop_duplicates("innings_id", keep="last").reset_index(drop=True)
    batting = batting.drop_duplicates(
        ["match_id", "innings_id", "participant_id", "bat_instance"], keep="last"
    ).reset_index(drop=True)
    balls = balls.drop_duplicates("ball_event_id", keep="last").reset_index(drop=True)
    source_delivery_rows = len(balls)
    balls, duplicates_removed = deduplicate_partnership_deliveries(balls)
    return matches, innings, balls, batting, source_delivery_rows, duplicates_removed


def deduplicate_partnership_deliveries(ball_by_ball: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    rows = ball_by_ball.copy().reset_index(drop=True)
    rows["is_wicket"] = bool_series(rows.get("is_wicket", pd.Series(False, index=rows.index)))
    rows["is_legal_delivery"] = bool_series(
        rows.get("is_legal_delivery", pd.Series(False, index=rows.index))
    )
    semantic_columns = [
        "match_id",
        "innings_id",
        "over_number",
        "ball_number",
        "batting_team_id",
        "striker_participant_id",
        "non_striker_participant_id",
        "bowler_participant_id",
        "runs_bat",
        "wides",
        "no_balls",
        "leg_byes",
        "byes",
        "penalty_runs",
        "total_runs",
        "is_wicket",
        "dismissal_type",
        "dismissed_participant_id",
        "progress_runs",
        "progress_wickets",
    ]
    semantic_columns = [column for column in semantic_columns if column in rows]
    before = len(rows)
    rows = rows.drop_duplicates(semantic_columns, keep="first").copy()
    return rows, before - len(rows)


def build_club_partnership_identity_lookup(
    batting: pd.DataFrame,
    selected_team_ids_by_match: Mapping[str, set[str]],
    club_id: str,
) -> dict[str, dict[str, str]]:
    rows = batting[
        batting.apply(
            lambda row: clean_text(row.get("team_id"))
            in selected_team_ids_by_match.get(clean_text(row.get("match_id")), set()),
            axis=1,
        )
    ].copy()
    rows["raw_player_id"] = rows["participant_id"].fillna("").astype(str)
    rows["raw_player_name"] = rows["player_name"]
    mapped = apply_player_identity_mapping(rows, club_id=club_id).drop_duplicates("raw_player_id")
    return {
        clean_text(row.raw_player_id): {
            "canonical_player_id": clean_text(row.canonical_player_id),
            "canonical_player_name": clean_text(row.canonical_player_name),
        }
        for row in mapped.itertuples()
        if clean_text(row.raw_player_id)
    }


def governed_batter_identity(
    participant_id: object,
    source_name: object,
    identity_lookup: Mapping[str, Mapping[str, str]],
) -> dict[str, object]:
    raw_id = clean_text(participant_id)
    raw_name = clean_text(source_name)
    mapped = identity_lookup.get(raw_id, {})
    canonical_id = clean_text(mapped.get("canonical_player_id"))
    canonical_name = clean_text(mapped.get("canonical_player_name"))
    return {
        "raw_id": raw_id,
        "canonical_id": canonical_id,
        "canonical_name": canonical_name,
        "resolved": bool(canonical_id and canonical_name),
        "private": is_private_or_anonymised_player(raw_name)
        or is_private_or_anonymised_player(canonical_name),
    }


def governed_partnership_privacy_status(
    player_1: Mapping[str, object], player_2: Mapping[str, object]
) -> str:
    private_count = int(bool(player_1.get("private"))) + int(bool(player_2.get("private")))
    if private_count == 2:
        return "PRIVATE_PRIVATE"
    if private_count == 1:
        return "PUBLIC_PRIVATE"
    return "PUBLIC_PUBLIC"


def governed_partnership_rejection_reason(
    row: pd.Series,
    player_1: Mapping[str, object],
    player_2: Mapping[str, object],
    privacy_status: str,
) -> str:
    if bool(row.get("_duplicate_key")):
        return "Duplicate match/innings/partnership key."
    raw_ids = [clean_text(player_1.get("raw_id")), clean_text(player_2.get("raw_id"))]
    if not all(raw_ids) or raw_ids[0] == raw_ids[1]:
        return "Incomplete or invalid two-batter delivery sequence."
    if not bool(player_1.get("resolved")) or not bool(player_2.get("resolved")):
        return "Canonical identity is unresolved for one or both batters."
    if privacy_status == "PRIVATE_PRIVATE":
        return "Both batters are private or masked."
    if clean_text(player_1.get("canonical_id")) == clean_text(player_2.get("canonical_id")):
        return "Both source participants resolve to the same canonical player."
    runs = pd.to_numeric(row.get("runs"), errors="coerce")
    if pd.isna(runs) or float(runs) < 0:
        return "Partnership runs are missing or invalid."
    if pd.isna(pd.to_numeric(row.get("innings_scorecard_total"), errors="coerce")):
        return "Scorecard innings total is unavailable for reconciliation disclosure."
    if pd.isna(pd.to_numeric(row.get("innings_reconstructed_total"), errors="coerce")):
        return "Reconstructed innings total is unavailable."
    return ""


def public_batter_identity(player: Mapping[str, object]) -> tuple[str, str]:
    if bool(player.get("private")):
        return "", "Private player"
    return clean_text(player.get("canonical_id")), clean_text(player.get("canonical_name"))


def build_partnership_privacy_audit(
    partnership_rows: pd.DataFrame,
    events: pd.DataFrame,
    rejected: pd.DataFrame,
) -> pd.DataFrame:
    rejection_reasons = rejected.get("rejection_reason", pd.Series("", index=rejected.index)).fillna("").astype(str)
    unresolved_mask = rejection_reasons.str.contains("unresolved|incomplete", case=False, regex=True)
    privacy_rejected = rejected.loc[~unresolved_mask]
    candidate_counts = privacy_rejected.get("privacy_status", pd.Series(dtype=str)).value_counts().add(
        events.get("privacy_status", pd.Series(dtype=str)).value_counts(), fill_value=0
    )
    rows = []
    for status in ["PUBLIC_PUBLIC", "PUBLIC_PRIVATE", "PRIVATE_PRIVATE"]:
        rows.append(
            {
                "privacy_status": status,
                "candidate_rows": int(candidate_counts.get(status, 0)),
                "published_rows": int(events.get("privacy_status", pd.Series(dtype=str)).eq(status).sum()),
                "rejected_rows": int(
                    privacy_rejected.get("privacy_status", pd.Series(dtype=str)).eq(status).sum()
                ),
                "private_identity_exposed": False,
            }
        )
    unresolved = int(unresolved_mask.sum())
    if unresolved:
        rows.append(
            {
                "privacy_status": "UNRESOLVED",
                "candidate_rows": unresolved,
                "published_rows": 0,
                "rejected_rows": unresolved,
                "private_identity_exposed": False,
            }
        )
    return pd.DataFrame(rows)


def parse_source_team_ids(value: object) -> set[str]:
    text = clean_text(value).replace(";", ",").replace("|", ",")
    return {token.strip() for token in text.split(",") if token.strip()}


def bool_series(values: object) -> pd.Series:
    if isinstance(values, pd.Series):
        return values.map(
            lambda value: value
            if isinstance(value, bool)
            else clean_text(value).casefold() in {"true", "1", "yes"}
        )
    return pd.Series(dtype=bool)


def write_governed_club_partnership_outputs(
    result: GovernedClubPartnershipResult,
    *,
    output: Path,
    validation_dir: Path,
    prefix: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)
    write_csv_atomic(result.events, output)
    write_csv_atomic(result.records, output.with_name("partnership_records.csv"))
    write_csv_atomic(result.coverage, validation_dir / f"{prefix}_partnership_coverage_audit.csv")
    write_csv_atomic(result.privacy_audit, validation_dir / f"{prefix}_partnership_privacy_audit.csv")
    write_csv_atomic(result.identity_audit, validation_dir / f"{prefix}_partnership_identity_audit.csv")
    write_csv_atomic(
        result.reconciliation_audit,
        validation_dir / f"{prefix}_partnership_reconciliation_failures.csv",
    )
    write_csv_atomic(result.rejected, validation_dir / f"{prefix}_partnership_rejected_records.csv")
    write_csv_atomic(
        result.record_selection_audit,
        validation_dir / f"{prefix}_partnership_record_selection_audit.csv",
    )


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
        "source_partnership_rows": 0,
        "club_ball_by_ball_rows": 0,
        "confirmed_events": 0,
        "review_events": 0,
        "private_events_excluded": 0,
        "matches": 0,
        "innings": 0,
    }
