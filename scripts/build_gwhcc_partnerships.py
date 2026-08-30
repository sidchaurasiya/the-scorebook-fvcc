#!/usr/bin/env python3
"""Build deploy-safe GWHCC partnership events, records, and validation."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_governance import display_grade_name  # noqa: E402
from src.data.partnerships import (  # noqa: E402
    AUDIT_COLUMNS,
    EVENT_COLUMNS,
    build_partnership_record_holders,
    combine_partnership_events,
    partnership_type_label,
    prepare_ball_by_ball_partnerships,
    unresolved_partnership_review_mask,
)
from src.utils.player_identity import apply_player_identity_mapping, is_private_or_anonymised_player  # noqa: E402


CLUB_ID = "glen-waverley-hawks"
MATCH_CENTRE = ROOT / "data" / "processed" / "match_centre" / CLUB_ID / "all_available"
CLUB_ROOT = ROOT / "clubs" / CLUB_ID
SOURCE = CLUB_ROOT / "data" / "source" / "document_overrides" / "gwhcc_historical_partnerships.csv"
PROCESSED = CLUB_ROOT / "data" / "processed"
EVENTS_OUTPUT = PROCESSED / "partnerships" / "partnership_events.csv"
RECORDS_OUTPUT = PROCESSED / "hall_of_fame" / "partnership_records.csv"
AUDIT_OUTPUT = PROCESSED / "validation" / "gwhcc_partnership_candidate_audit.csv"
COVERAGE_OUTPUT = PROCESSED / "validation" / "gwhcc_partnership_coverage_audit.csv"
VALIDATION_OUTPUT = PROCESSED / "validation" / "gwhcc_partnership_validation.csv"


def read_match_source(name: str) -> pd.DataFrame:
    path = MATCH_CENTRE / name
    if not path.exists():
        raise FileNotFoundError(f"Required partnership source is missing: {path}")
    return pd.read_csv(path, low_memory=False)


def source_team_ids(value: object) -> set[str]:
    text = str(value or "").replace(";", ",").replace("|", ",")
    return {
        token.strip()
        for token in text.split(",")
        if token.strip() and token.strip().casefold() not in {"nan", "none", "nat"}
    }


def build_identity_lookup(
    batting: pd.DataFrame,
    selected_team_ids_by_match: dict[str, set[str]],
) -> dict[str, dict[str, str]]:
    rows = batting[
        batting.apply(
            lambda row: str(row.get("team_id"))
            in selected_team_ids_by_match.get(str(row.get("match_id")), set()),
            axis=1,
        )
    ].copy()
    rows["raw_player_id"] = rows["participant_id"].fillna("").astype(str)
    rows["raw_player_name"] = rows["player_name"]
    mapped = apply_player_identity_mapping(rows, club_id=CLUB_ID).drop_duplicates("raw_player_id")
    return {
        str(row.raw_player_id): {
            "canonical_player_id": str(row.canonical_player_id),
            "canonical_player_name": str(row.canonical_player_name),
        }
        for row in mapped.itertuples()
        if str(row.raw_player_id).strip()
    }


def historical_partnership_rows(matches: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    source = pd.read_csv(SOURCE, dtype=str).fillna("")
    match_rows = matches.drop_duplicates("match_id").copy()
    match_rows["match_id"] = match_rows["match_id"].astype(str)
    match_lookup = match_rows.set_index("match_id").to_dict("index")
    event_rows: list[dict[str, object]] = []
    audit_rows: list[dict[str, object]] = []
    for _, row in source.iterrows():
        match_id = str(row.get("match_id", "")).strip()
        match = match_lookup.get(match_id, {})
        review_required = str(row.get("review_required", "")).casefold() in {"true", "1", "yes"}
        player_1_name = str(row.get("player_1_name", "")).strip()
        player_2_name = str(row.get("player_2_name", "")).strip()
        player_1_private = is_private_or_anonymised_player(player_1_name)
        player_2_private = is_private_or_anonymised_player(player_2_name)
        privacy_status = (
            "PRIVATE_PRIVATE"
            if player_1_private and player_2_private
            else "PUBLIC_PRIVATE"
            if player_1_private or player_2_private
            else "PUBLIC_PUBLIC"
        )
        wicket_number = int(float(row["wicket_number"]))
        both_not_out = str(row.get("player_1_score", "")).endswith("*") and str(row.get("player_2_score", "")).endswith("*")
        team_name, opponent = historical_team_and_opponent(match)
        grade = str(row.get("grade_name", "")).strip()
        event = {
            "record_id": row["record_id"],
            "player_1_canonical_id": "" if player_1_private else row.get("player_1_canonical_id", ""),
            "player_1_name": "Private player" if player_1_private else player_1_name,
            "player_2_canonical_id": "" if player_2_private else row.get("player_2_canonical_id", ""),
            "player_2_name": "Private player" if player_2_private else player_2_name,
            "runs": int(float(row["runs"])),
            "balls": None,
            "wickets_lost": 0 if both_not_out else 1,
            "wicket_number": wicket_number,
            "partnership_type": partnership_type_label(wicket_number),
            "season": row["season"],
            "match_id": match_id,
            "innings_id": "",
            "match_date": str(match.get("first_match_day", ""))[:10],
            "team_name": team_name or "Glen Waverley Hawks",
            "opponent": opponent,
            "raw_grade_name": grade,
            "display_grade_name": display_grade_name(grade),
            "source_classification": "customer_document",
            "evidence_quality": "club_record_document",
            "confidence": row.get("confidence", ""),
            "scorecard_url": f"https://play.cricket.com.au/match/{match_id}" if match_id else "",
            "source_detail": f"{row['source_document']} / {row['source_sheet']} row {row['source_row']}: {row['notes']}",
            "privacy_status": privacy_status,
        }
        public_slots = [
            (event["player_1_canonical_id"], event["player_1_name"]),
            (event["player_2_canonical_id"], event["player_2_name"]),
        ]
        missing_identity = any(
            not str(player_id).strip() or not str(player_name).strip()
            for (player_id, player_name), is_private in zip(
                public_slots, [player_1_private, player_2_private]
            )
            if not is_private
        )
        if privacy_status == "PRIVATE_PRIVATE":
            status, reason = "EXCLUDED_PRIVATE", "Both document players are private or masked."
        elif review_required or missing_identity:
            status, reason = "REVIEW", row.get("notes", "Historical identity requires review.")
        else:
            status, reason = "DOCUMENT_CONFIRMED", "Explicit club partnership record with canonical player identities."
            event_rows.append(event)
        audit_rows.append(
            {
                **event,
                "validation_status": status,
                "review_reason": reason,
                "innings_partnership_runs": None,
                "innings_scorecard_runs": None,
                "innings_runs_difference": None,
                "is_private_player": privacy_status != "PUBLIC_PUBLIC",
            }
        )
    return pd.DataFrame(event_rows, columns=EVENT_COLUMNS), pd.DataFrame(audit_rows, columns=AUDIT_COLUMNS)


def historical_team_and_opponent(match: dict[str, object]) -> tuple[str, str]:
    source_ids = source_team_ids(match.get("source_team_ids"))
    home_id = str(match.get("home_team_id", ""))
    away_id = str(match.get("away_team_id", ""))
    if home_id in source_ids:
        return str(match.get("home_team_name", "")), str(match.get("away_team_name", ""))
    if away_id in source_ids:
        return str(match.get("away_team_name", "")), str(match.get("home_team_name", ""))
    return "", ""


def coverage_rows(audit: pd.DataFrame) -> pd.DataFrame:
    if audit.empty:
        return pd.DataFrame(columns=["source_classification", "season", "candidate_rows", "confirmed_rows", "review_rows", "private_rows", "public_public_rows", "public_private_rows", "private_private_rows", "unresolved_rows"])
    rows = audit.copy()
    return (
        rows.groupby(["source_classification", "season"], dropna=False)
        .agg(
            candidate_rows=("record_id", "size"),
            confirmed_rows=("validation_status", lambda values: int(pd.Series(values).isin({"CONFIRMED", "DOCUMENT_CONFIRMED"}).sum())),
            review_rows=("validation_status", lambda values: int(pd.Series(values).eq("REVIEW").sum())),
            private_rows=("validation_status", lambda values: int(pd.Series(values).eq("EXCLUDED_PRIVATE").sum())),
            public_public_rows=("privacy_status", lambda values: int(pd.Series(values).eq("PUBLIC_PUBLIC").sum())),
            public_private_rows=("privacy_status", lambda values: int(pd.Series(values).eq("PUBLIC_PRIVATE").sum())),
            private_private_rows=("privacy_status", lambda values: int(pd.Series(values).eq("PRIVATE_PRIVATE").sum())),
            unresolved_rows=("review_reason", lambda values: int(unresolved_partnership_review_mask(pd.Series(values)).sum())),
        )
        .reset_index()
        .sort_values(["source_classification", "season"])
    )


def validation_rows(events: pd.DataFrame, records: pd.DataFrame, audit: pd.DataFrame) -> pd.DataFrame:
    player_1_protected = events["player_1_name"].eq("Private player")
    player_2_protected = events["player_2_name"].eq("Private player")
    unsafe_private = (
        events["player_1_name"].map(is_private_or_anonymised_player) & ~player_1_protected
    ) | (
        events["player_2_name"].map(is_private_or_anonymised_player) & ~player_2_protected
    )
    protected_ids = (
        player_1_protected & events["player_1_canonical_id"].fillna("").astype(str).str.strip().ne("")
    ) | (
        player_2_protected & events["player_2_canonical_id"].fillna("").astype(str).str.strip().ne("")
    )
    public_private = events.get("privacy_status", pd.Series("", index=events.index)).eq("PUBLIC_PRIVATE")
    protected_count = player_1_protected.astype(int) + player_2_protected.astype(int)
    checks = [
        ("prepared_events_exist", not events.empty, f"rows={len(events)}"),
        ("record_holders_exist", not records.empty, f"rows={len(records)}"),
        ("no_duplicate_events", not events["record_id"].duplicated().any(), f"duplicates={int(events['record_id'].duplicated().sum())}"),
        ("one_record_per_wicket", not records["wicket_number"].duplicated().any(), f"wickets={records['wicket_number'].tolist()}"),
        ("no_private_name_exposure", not unsafe_private.any(), f"unsafe_private={int(unsafe_private.sum())}"),
        ("public_private_uses_exact_protected_label", protected_count.loc[public_private].eq(1).all(), f"public_private={int(public_private.sum())}"),
        ("protected_partner_has_no_public_id", not protected_ids.any(), f"protected_ids={int(protected_ids.sum())}"),
        ("all_records_from_public_events", set(records["record_id"]).issubset(set(events["record_id"])), "record IDs are event-backed"),
        ("review_rows_are_audited", int(audit["validation_status"].eq("REVIEW").sum()) > 0, f"review={int(audit['validation_status'].eq('REVIEW').sum())}"),
    ]
    standard_wickets = events[pd.to_numeric(events["wicket_number"], errors="coerce").between(1, 10, inclusive="both")]
    for wicket, group in standard_wickets.groupby("wicket_number"):
        record = records[pd.to_numeric(records["wicket_number"], errors="coerce").eq(float(wicket))]
        checks.append(
            (
                f"wicket_{int(float(wicket))}_record_is_maximum",
                not record.empty and float(record.iloc[0]["runs"]) == float(pd.to_numeric(group["runs"], errors="coerce").max()),
                f"maximum={pd.to_numeric(group['runs'], errors='coerce').max()}",
            )
        )
    return pd.DataFrame(
        [{"check": name, "status": "PASS" if passed else "FAIL", "detail": detail} for name, passed, detail in checks]
    )


def main() -> int:
    partnerships = read_match_source("all_partnerships.csv")
    matches = read_match_source("all_matches.csv")
    innings = read_match_source("all_match_innings.csv")
    batting = read_match_source("all_scorecard_batting.csv")
    selected = {str(row.match_id): source_team_ids(row.source_team_ids) for row in matches.itertuples()}
    identity_lookup = build_identity_lookup(batting, selected)
    calculated = prepare_ball_by_ball_partnerships(
        partnerships,
        matches=matches,
        innings=innings,
        selected_team_ids_by_match=selected,
        identity_lookup=identity_lookup,
        grade_display=display_grade_name,
    )
    historical_events, historical_audit = historical_partnership_rows(matches)
    events = combine_partnership_events(calculated.events, historical_events)
    audit = pd.concat([calculated.audit, historical_audit], ignore_index=True, sort=False)[AUDIT_COLUMNS]
    records = build_partnership_record_holders(events)
    coverage = coverage_rows(audit)
    validation = validation_rows(events, records, audit)

    for path in [EVENTS_OUTPUT, RECORDS_OUTPUT, AUDIT_OUTPUT, COVERAGE_OUTPUT, VALIDATION_OUTPUT]:
        path.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(EVENTS_OUTPUT, index=False)
    records.to_csv(RECORDS_OUTPUT, index=False)
    audit.to_csv(AUDIT_OUTPUT, index=False)
    coverage.to_csv(COVERAGE_OUTPUT, index=False)
    validation.to_csv(VALIDATION_OUTPUT, index=False)

    failures = validation[validation["status"].eq("FAIL")]
    print(
        "GWHCC partnerships: "
        f"calculated_confirmed={len(calculated.events)} historical_confirmed={len(historical_events)} "
        f"combined={len(events)} records={len(records)} review={int(audit['validation_status'].eq('REVIEW').sum())}"
    )
    print(f"- validation failures: {len(failures)}")
    return 1 if not failures.empty else 0


if __name__ == "__main__":
    raise SystemExit(main())
