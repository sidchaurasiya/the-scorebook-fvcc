#!/usr/bin/env python3
"""Export decision-ready GRDCC anomaly review CSVs with source row data."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLUB_DIR = ROOT / "clubs" / "georges-river-district"
PROCESSED_DIR = CLUB_DIR / "data" / "processed"
VALIDATION_DIR = PROCESSED_DIR / "validation"
SUPPLEMENTAL_DIR = PROCESSED_DIR / "supplemental"
EXPORT_DIR = VALIDATION_DIR / "review_exports"

PLAYCRICKET_DECISION_REVIEW = VALIDATION_DIR / "playcricket_anomaly_decision_review.csv"
PLAYCRICKET_SOURCE_FILES = {
    "batting": PROCESSED_DIR / "all_seasons_batting.csv",
    "bowling": PROCESSED_DIR / "all_seasons_bowling.csv",
    "fielding": PROCESSED_DIR / "all_seasons_fielding.csv",
}

EXCEL_STATUS_FILES = [
    ("clean", SUPPLEMENTAL_DIR / "excel_clean_rows.csv"),
    ("review", SUPPLEMENTAL_DIR / "excel_review_rows.csv"),
    ("rejected", SUPPLEMENTAL_DIR / "excel_rejected_rows.csv"),
]
EXCEL_APP_FILES = {
    "batting": SUPPLEMENTAL_DIR / "excel_all_seasons_batting.csv",
    "bowling": SUPPLEMENTAL_DIR / "excel_all_seasons_bowling.csv",
}

AUDIT_COLUMNS = [
    "decision_priority",
    "suggested_decision",
    "current_app_status",
    "app_facing_allowed",
    "highest_severity",
    "issue_codes",
    "issue_reasons",
    "recommended_actions",
    "issue_count",
    "source_system",
    "source_file",
    "source_row",
    "player_name",
    "canonical_player_id",
    "season",
    "team",
    "grade",
    "metric_group",
]

MANUAL_COLUMNS = [
    "reviewer_decision",
    "reviewer_corrected_metric",
    "reviewer_corrected_value",
    "reviewer_notes",
    "reviewed_by",
    "reviewed_date",
]

PLAYCRICKET_NORMALIZED_COLUMNS = [
    "matches",
    "innings",
    "not_outs",
    "runs",
    "balls_faced",
    "high_score",
    "batting_average",
    "batting_strike_rate",
    "30s",
    "50s",
    "100s",
    "ducks",
    "fours",
    "sixes",
    "overs",
    "balls",
    "maidens",
    "bowling_runs_conceded",
    "wickets",
    "bowling_average",
    "bowling_strike_rate",
    "economy",
    "best_bowling",
    "bbi_wickets",
    "bbi_runs",
    "3wi",
    "5wi",
    "10wm",
    "catches",
    "stumpings",
    "run_outs",
    "dismissals",
    "all_involved_player_names",
    "canonical_ids",
    "seasons_involved",
    "grades_involved",
    "row_count",
    "duplicate_grouping_key",
    "source_rows_involved",
]

EXCEL_EXTRA_COLUMNS = [
    "source_sheet",
    "qa_status",
    "data_confidence",
    "feeds_records",
]


def main() -> int:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    playcricket_rows = build_playcricket_reviews()
    excel_rows = build_excel_reviews()

    write_review("playcricket_all_anomalies_decision_review_with_data.csv", playcricket_rows)
    write_review("playcricket_batting_decision_review_with_data.csv", [r for r in playcricket_rows if r.get("metric_group") == "batting"])
    write_review("playcricket_bowling_decision_review_with_data.csv", [r for r in playcricket_rows if r.get("metric_group") == "bowling"])
    write_review("playcricket_fielding_decision_review_with_data.csv", [r for r in playcricket_rows if r.get("metric_group") == "fielding"])
    write_review("playcricket_duplicate_identity_decision_review_with_data.csv", [r for r in playcricket_rows if r.get("metric_group") == "identity"])
    write_summary("playcricket_decision_review_summary.csv", playcricket_rows)

    write_review("excel_all_anomalies_decision_review_with_data.csv", excel_rows)
    write_review("excel_batting_decision_review_with_data.csv", [r for r in excel_rows if r.get("metric_group") == "batting"])
    write_review("excel_bowling_decision_review_with_data.csv", [r for r in excel_rows if r.get("metric_group") == "bowling"])
    write_review("excel_rejected_decision_review_with_data.csv", [r for r in excel_rows if r.get("qa_status") == "rejected"])
    write_summary("excel_decision_review_summary.csv", excel_rows)

    print(f"PlayCricket decision review rows: {len(playcricket_rows)}")
    print(f"Excel decision review rows: {len(excel_rows)}")
    print(f"P1 count: {count_priority(playcricket_rows + excel_rows, 'P1')}")
    print(f"P2 count: {count_priority(playcricket_rows + excel_rows, 'P2')}")
    print(f"Rows already excluded from app: {count_status(playcricket_rows + excel_rows, 'excluded_from_app')}")
    print(f"Rows still requiring manual decision: {manual_decision_count(playcricket_rows + excel_rows)}")
    print(f"Nathan Percy status: {person_status(playcricket_rows, 'Nathan Percy', 'Summer 1995/96')}")
    print(f"Robert Southwell status: {person_status(playcricket_rows, 'Robert Southwell', 'Summer 1994/95')}")
    print(f"H Jolly status: {h_jolly_status(excel_rows)}")
    print("outputs:")
    for path in sorted(EXPORT_DIR.glob("*.csv")):
        print(f"- {path.relative_to(ROOT)}")
    return 0


def build_playcricket_reviews() -> list[dict[str, object]]:
    decision_rows = read_csv(PLAYCRICKET_DECISION_REVIEW)
    source_lookup = build_playcricket_source_lookup()
    duplicate_lookup = build_duplicate_detail_lookup()
    output: list[dict[str, object]] = []
    for row in decision_rows:
        source = source_lookup.get((clean(row.get("source_file")), clean(row.get("source_row"))), {})
        enriched = {**row}
        enriched["issue_count"] = count_issue_codes(row.get("issue_codes"))
        enriched.update(normalize_playcricket_source(source, row.get("metric_group")))
        if row.get("metric_group") == "identity":
            enriched.update(identity_fields(row, source, duplicate_lookup.get(decision_detail_key(row), {})))
        enriched.update(prefixed_source_columns(source))
        output.append(enriched)
    output.sort(key=decision_sort_key)
    return output


def build_playcricket_source_lookup() -> dict[tuple[str, str], dict[str, str]]:
    lookup: dict[tuple[str, str], dict[str, str]] = {}
    for path in PLAYCRICKET_SOURCE_FILES.values():
        rel = str(path.relative_to(ROOT))
        for line, row in enumerate(read_csv(path), start=2):
            lookup[(rel, str(line))] = row
    return lookup


def build_duplicate_detail_lookup() -> dict[tuple[str, str, str, str, str, str, str], dict[str, str]]:
    lookup: dict[tuple[str, str, str, str, str, str, str], dict[str, str]] = {}
    for row in read_csv(VALIDATION_DIR / "playcricket_duplicate_player_season_audit.csv"):
        lookup[decision_detail_key(row)] = row
    return lookup


def decision_detail_key(row: dict[str, object]) -> tuple[str, str, str, str, str, str, str]:
    return (
        clean(row.get("source_file")),
        clean(row.get("source_row")),
        clean(row.get("player_name")),
        clean(row.get("season")),
        clean(row.get("team")),
        clean(row.get("grade")),
        clean(row.get("metric_group")),
    )


def build_excel_reviews() -> list[dict[str, object]]:
    app_lookup = build_excel_app_lookup()
    grouped: dict[tuple[str, str, str, str, str, str, str, str], list[dict[str, object]]] = defaultdict(list)

    for qa_status, path in EXCEL_STATUS_FILES:
        for row in read_csv(path):
            grouped[excel_key(row)].append(status_issue_row(row, qa_status))

    for row in read_csv(SUPPLEMENTAL_DIR / "excel_outlier_audit.csv"):
        grouped[excel_key(row)].append(outlier_issue_row(row))

    for row in read_csv(SUPPLEMENTAL_DIR / "excel_reconciliation_audit.csv"):
        if clean(row.get("issue_flag")).casefold() not in {"yes", "true", "1"}:
            continue
        grouped[excel_key(row)].append(reconciliation_issue_row(row))

    # Mapping issues are sheet/block level, so they stay in the all-anomalies export as
    # low-grain review rows without player-season metrics.
    for row in read_csv(SUPPLEMENTAL_DIR / "excel_column_mapping_audit.csv"):
        if not clean(row.get("issue_flag")):
            continue
        mapped = column_mapping_issue_row(row)
        grouped[excel_key(mapped)].append(mapped)

    output: list[dict[str, object]] = []
    for rows in grouped.values():
        first = rows[0]
        source = app_lookup.get(excel_source_lookup_key(first), {})
        issue_codes = sorted({clean(row.get("issue_code")) for row in rows if clean(row.get("issue_code"))})
        reasons = sorted({clean(row.get("reason")) for row in rows if clean(row.get("reason"))})
        actions = sorted({clean(row.get("recommended_action")) for row in rows if clean(row.get("recommended_action"))})
        allowed = combined_app_facing_allowed([clean(row.get("app_facing_allowed")) for row in rows])
        qa_status = strongest_qa_status([clean(row.get("qa_status")) for row in rows])
        confidence = weakest_confidence([clean(row.get("data_confidence")) for row in rows])
        suggested, priority = excel_decision(issue_codes, actions, qa_status, allowed)
        enriched = {
            "decision_priority": priority,
            "suggested_decision": suggested,
            "current_app_status": excel_current_app_status(allowed, qa_status),
            "app_facing_allowed": allowed,
            "highest_severity": highest_severity(rows),
            "issue_codes": "; ".join(issue_codes),
            "issue_reasons": "; ".join(reasons),
            "recommended_actions": "; ".join(actions),
            "issue_count": len(issue_codes),
            "source_system": "excel",
            "source_file": clean(first.get("source_file")),
            "source_sheet": clean(first.get("source_sheet")),
            "source_row": clean(first.get("source_row")),
            "player_name": clean(first.get("player_name")),
            "canonical_player_id": clean(source.get("canonical_player_id")),
            "season": clean(first.get("season")),
            "team": clean(source.get("team_name") or first.get("team") or first.get("team_or_grade")),
            "grade": clean(source.get("grade_name") or first.get("grade") or first.get("team_or_grade")),
            "metric_group": clean(first.get("metric_group")),
            "qa_status": qa_status,
            "data_confidence": confidence,
            "feeds_records": "yes" if qa_status == "clean" and allowed == "yes" else "no",
        }
        enriched.update(normalize_playcricket_source(source, enriched.get("metric_group")))
        enriched.update(prefixed_source_columns(source))
        output.append(enriched)
    output.sort(key=decision_sort_key)
    return output


def build_excel_app_lookup() -> dict[tuple[str, str, str, str], dict[str, str]]:
    lookup: dict[tuple[str, str, str, str], dict[str, str]] = {}
    for group, path in EXCEL_APP_FILES.items():
        for row in read_csv(path):
            key = (
                clean(row.get("source_file")),
                clean(row.get("source_sheet")),
                clean(row.get("source_row")),
                group,
            )
            lookup.setdefault(key, row)
    return lookup


def status_issue_row(row: dict[str, str], qa_status: str) -> dict[str, object]:
    action = clean(row.get("action"))
    issue_codes = clean(row.get("issue_codes")) or qa_status
    reasons = clean(row.get("issue_reasons")) or f"Excel row status is {qa_status}."
    if qa_status == "clean":
        severity = "low"
        recommended = "accept_with_warning"
        allowed = "yes"
    elif qa_status == "review":
        severity = "medium"
        recommended = "needs_manual_review"
        allowed = "pending"
    else:
        severity = "high"
        recommended = "exclude_from_records"
        allowed = "no"
    return {
        **row,
        "issue_code": issue_codes,
        "reason": reasons,
        "severity": severity,
        "recommended_action": recommended if action != "excluded_from_records" else "exclude_from_records",
        "app_facing_allowed": allowed,
        "qa_status": qa_status,
    }


def outlier_issue_row(row: dict[str, str]) -> dict[str, object]:
    action = clean(row.get("action"))
    return {
        **row,
        "issue_code": clean(row.get("metric_name")) or clean(row.get("issue_type")) or "excel_outlier",
        "reason": clean(row.get("reason")),
        "recommended_action": "exclude_from_records" if action == "excluded_from_records" else action or "needs_manual_review",
        "app_facing_allowed": "no" if action == "excluded_from_records" else "pending",
        "qa_status": "review",
    }


def reconciliation_issue_row(row: dict[str, str]) -> dict[str, object]:
    action = clean(row.get("action"))
    return {
        **row,
        "issue_code": clean(row.get("check_name")) or "excel_reconciliation_issue",
        "reason": clean(row.get("reason")),
        "recommended_action": "exclude_from_records" if action == "excluded_from_records" else action or "needs_manual_review",
        "app_facing_allowed": "no" if action == "excluded_from_records" else "pending",
        "qa_status": "review",
    }


def column_mapping_issue_row(row: dict[str, str]) -> dict[str, object]:
    return {
        "source_file": "bexley_stats_spreadsheets.xlsx",
        "source_sheet": clean(row.get("source_sheet")),
        "source_row": clean(row.get("source_row_header")),
        "player_name": "",
        "season": "",
        "team_or_grade": "",
        "metric_group": clean(row.get("detected_section")) or "mapping",
        "issue_code": clean(row.get("issue_flag")) or "column_mapping_issue",
        "reason": clean(row.get("mapping_reason")),
        "severity": "medium",
        "recommended_action": "needs_manual_review",
        "app_facing_allowed": "pending",
        "qa_status": "review",
        "data_confidence": "low",
    }


def normalize_playcricket_source(source: dict[str, str], metric_group: object) -> dict[str, object]:
    group = clean(metric_group)
    balls = num(source.get("bowlingBalls"))
    bbi_wickets, bbi_runs = parse_bbi(source.get("bowlingBestInnings"))
    fields = {
        "matches": source.get("matches", ""),
        "innings": source.get("battingInnings", ""),
        "not_outs": source.get("battingNotOuts", ""),
        "runs": source.get("battingAggregate", ""),
        "balls_faced": source.get("battingBallsFaced", ""),
        "high_score": source.get("battingHighScore", ""),
        "batting_average": source.get("battingAverage", ""),
        "batting_strike_rate": source.get("battingStrikeRate", ""),
        "30s": source.get("batting30s", ""),
        "50s": source.get("batting50s", ""),
        "100s": source.get("batting100s", ""),
        "ducks": source.get("batting0s", ""),
        "fours": source.get("battingFours", ""),
        "sixes": source.get("battingSixes", ""),
        "overs": f"{balls / 6:.2f}" if balls is not None else "",
        "balls": source.get("bowlingBalls", ""),
        "maidens": source.get("bowlingMaidens", ""),
        "bowling_runs_conceded": source.get("bowlingRuns", ""),
        "wickets": source.get("bowlingWickets", ""),
        "bowling_average": source.get("bowlingAverage", ""),
        "bowling_strike_rate": source.get("bowlingStrikeRate", ""),
        "economy": source.get("bowlingEconomyRate", ""),
        "best_bowling": source.get("bowlingBestInnings", ""),
        "bbi_wickets": bbi_wickets if bbi_wickets is not None else "",
        "bbi_runs": bbi_runs if bbi_runs is not None else "",
        "3wi": source.get("bowling3WIs", ""),
        "5wi": source.get("bowling5WIs", ""),
        "10wm": source.get("bowling10WMs", ""),
        "catches": source.get("fieldingTotalCatches", ""),
        "stumpings": source.get("fieldingStumpings", ""),
        "run_outs": source.get("fieldingRunOuts", ""),
        "dismissals": fielding_dismissals(source),
    }
    if group == "batting":
        return {key: fields.get(key, "") for key in PLAYCRICKET_NORMALIZED_COLUMNS}
    if group == "bowling":
        return {key: fields.get(key, "") for key in PLAYCRICKET_NORMALIZED_COLUMNS}
    if group == "fielding":
        return {key: fields.get(key, "") for key in PLAYCRICKET_NORMALIZED_COLUMNS}
    return {key: fields.get(key, "") for key in PLAYCRICKET_NORMALIZED_COLUMNS}


def identity_fields(row: dict[str, object], source: dict[str, str], detail: dict[str, str]) -> dict[str, object]:
    issue_codes = clean(row.get("issue_codes"))
    canonical_ids = clean(detail.get("metric_value") or row.get("canonical_player_id") or source.get("canonical_player_id") or source.get("player_id"))
    canonical_id_parts = [part.strip() for part in canonical_ids.split("|") if part.strip()]
    grouping_key = "|".join(
        [
            clean(row.get("player_name")),
            clean(row.get("season")),
            clean(row.get("metric_group")),
            issue_codes,
        ]
    )
    return {
        "all_involved_player_names": clean(row.get("player_name") or source.get("player_name")),
        "canonical_ids": " | ".join(canonical_id_parts) if canonical_id_parts else canonical_ids,
        "seasons_involved": clean(row.get("season")),
        "grades_involved": clean(row.get("grade") or source.get("grade_name")),
        "row_count": len(canonical_id_parts) if canonical_id_parts else 1,
        "duplicate_grouping_key": grouping_key,
        "source_rows_involved": clean(row.get("source_row")),
    }


def prefixed_source_columns(source: dict[str, str]) -> dict[str, object]:
    return {f"source_{key}": value for key, value in source.items()}


def write_review(filename: str, rows: list[dict[str, object]]) -> None:
    base_columns = AUDIT_COLUMNS + MANUAL_COLUMNS + EXCEL_EXTRA_COLUMNS + PLAYCRICKET_NORMALIZED_COLUMNS
    write_csv(EXPORT_DIR / filename, rows, ordered_columns(rows, base_columns))


def write_summary(filename: str, rows: list[dict[str, object]]) -> None:
    summary: list[dict[str, object]] = []
    for label, field in [
        ("decision_priority", "decision_priority"),
        ("suggested_decision", "suggested_decision"),
        ("metric_group", "metric_group"),
        ("current_app_status", "current_app_status"),
        ("app_facing_allowed", "app_facing_allowed"),
        ("qa_status", "qa_status"),
    ]:
        counts = Counter(clean(row.get(field)) for row in rows if clean(row.get(field)))
        summary.extend({"summary_group": label, "value": key, "count": value} for key, value in sorted(counts.items()))
    issue_counts: Counter[str] = Counter()
    for row in rows:
        for code in clean(row.get("issue_codes")).split("; "):
            if code:
                issue_counts[code] += 1
    summary.extend({"summary_group": "issue_code", "value": key, "count": value} for key, value in issue_counts.most_common())
    write_csv(EXPORT_DIR / filename, summary, ["summary_group", "value", "count"])


def ordered_columns(rows: list[dict[str, object]], preferred: list[str]) -> list[str]:
    seen = set()
    columns = []
    for column in preferred:
        if column not in seen:
            columns.append(column)
            seen.add(column)
    for row in rows:
        for column in row:
            if column not in seen:
                columns.append(column)
                seen.add(column)
    return columns


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            output = {column: row.get(column, "") for column in columns}
            for column in MANUAL_COLUMNS:
                if column in output:
                    output[column] = ""
            writer.writerow(output)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def excel_key(row: dict[str, object]) -> tuple[str, str, str, str, str, str, str, str]:
    return (
        clean(row.get("source_file")),
        clean(row.get("source_sheet")),
        clean(row.get("source_row")),
        clean(row.get("player_name")),
        clean(row.get("season")),
        clean(row.get("team") or row.get("team_or_grade")),
        clean(row.get("grade") or row.get("team_or_grade")),
        clean(row.get("metric_group")),
    )


def excel_source_lookup_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        clean(row.get("source_file")),
        clean(row.get("source_sheet")),
        clean(row.get("source_row")),
        clean(row.get("metric_group")),
    )


def excel_decision(issue_codes: list[str], actions: list[str], qa_status: str, allowed: str) -> tuple[str, str]:
    code_set = set(issue_codes)
    action_set = set(actions)
    if qa_status == "clean" and allowed == "yes":
        return "no_decision_required", "P3"
    if "invalid_player_name" in code_set or "exclude_from_records" in action_set or qa_status == "rejected":
        return "exclude_from_records", "P1"
    if allowed == "no":
        return "already_excluded_review_source", "P1"
    return "manual_stat_review", "P2"


def excel_current_app_status(allowed: str, qa_status: str) -> str:
    if allowed == "no" or qa_status == "rejected":
        return "excluded_from_app"
    if allowed == "pending" or qa_status == "review":
        return "not_confirmed_safe"
    return "feeds_app_records"


def combined_app_facing_allowed(values: list[str]) -> str:
    cleaned = [value for value in values if value]
    if "no" in cleaned:
        return "no"
    if "pending" in cleaned:
        return "pending"
    if "yes" in cleaned:
        return "yes"
    return "pending"


def highest_severity(rows: list[dict[str, object]]) -> str:
    order = {"high": 0, "medium": 1, "low": 2}
    return min((clean(row.get("severity")) for row in rows if clean(row.get("severity"))), key=lambda value: order.get(value, 99), default="low")


def strongest_qa_status(values: list[str]) -> str:
    order = {"rejected": 0, "review": 1, "clean": 2}
    return min((value for value in values if value), key=lambda value: order.get(value, 99), default="")


def weakest_confidence(values: list[str]) -> str:
    order = {"low": 0, "medium": 1, "high": 2}
    return min((value for value in values if value), key=lambda value: order.get(value, 99), default="")


def decision_sort_key(row: dict[str, object]) -> tuple[object, ...]:
    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    severity_order = {"high": 0, "medium": 1, "low": 2}
    status_order = {"dangerous_if_visible": 0, "excluded_from_app": 1, "not_confirmed_safe": 2, "feeds_app_records": 3, "allowed_or_audit_only": 4}
    return (
        priority_order.get(clean(row.get("decision_priority")), 99),
        severity_order.get(clean(row.get("highest_severity")), 99),
        status_order.get(clean(row.get("current_app_status")), 99),
        clean(row.get("metric_group")),
        -season_sort_key(clean(row.get("season"))),
        clean(row.get("player_name")).casefold(),
    )


def count_issue_codes(value: object) -> int:
    return len([part for part in clean(value).split("; ") if part])


def count_priority(rows: list[dict[str, object]], priority: str) -> int:
    return sum(1 for row in rows if clean(row.get("decision_priority")) == priority)


def count_status(rows: list[dict[str, object]], status: str) -> int:
    return sum(1 for row in rows if clean(row.get("current_app_status")) == status)


def manual_decision_count(rows: list[dict[str, object]]) -> int:
    return sum(1 for row in rows if clean(row.get("decision_priority")) in {"P1", "P2"} and clean(row.get("suggested_decision")) != "already_excluded_review_source")


def person_status(rows: list[dict[str, object]], player: str, season: str) -> str:
    matches = [row for row in rows if clean(row.get("player_name")) == player and clean(row.get("season")) == season]
    if not matches:
        return "not found"
    return "; ".join(f"{row.get('suggested_decision')} ({row.get('current_app_status')}, row {row.get('source_row')})" for row in matches[:3])


def h_jolly_status(rows: list[dict[str, object]]) -> str:
    matches = [
        row
        for row in rows
        if clean(row.get("player_name")) == "H Jolly"
        and clean(row.get("season")) == "Summer 1944/45"
        and clean(row.get("metric_group")) == "bowling"
    ]
    if not matches:
        return "not found"
    row = matches[0]
    return f"wickets={row.get('wickets')} bowling_runs_conceded={row.get('bowling_runs_conceded')} qa_status={row.get('qa_status')}"


def fielding_dismissals(source: dict[str, str]) -> object:
    values = [num(source.get("fieldingTotalCatches")), num(source.get("fieldingStumpings")), num(source.get("fieldingRunOuts"))]
    if all(value is None for value in values):
        return ""
    return sum(value or 0 for value in values)


def parse_bbi(value: object) -> tuple[object, object]:
    match = re.match(r"(\d+)[-/](\d+)", clean(value))
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def season_sort_key(season: str) -> int:
    match = re.search(r"(18|19|20)\d{2}", season)
    return int(match.group()) if match else -1


def num(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


if __name__ == "__main__":
    raise SystemExit(main())
