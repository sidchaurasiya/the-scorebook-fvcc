#!/usr/bin/env python3
"""Audit GRDCC discrepancies between overlapping PlayCricket and Excel data."""

from __future__ import annotations

import csv
import math
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLUB_DIR = ROOT / "clubs" / "georges-river-district"
PROCESSED_DIR = CLUB_DIR / "data" / "processed"
SUPPLEMENTAL_DIR = PROCESSED_DIR / "supplemental"
VALIDATION_DIR = PROCESSED_DIR / "validation"
SOURCE_COVERAGE_DIR = VALIDATION_DIR / "source_coverage"
OUTPUT_DIR = VALIDATION_DIR / "source_overlap"
DOC_PATH = ROOT / "docs" / "georges_river_source_overlap_discrepancy_report.md"

PC_BATTING = PROCESSED_DIR / "all_seasons_batting.csv"
PC_BOWLING = PROCESSED_DIR / "all_seasons_bowling.csv"
PC_FIELDING = PROCESSED_DIR / "all_seasons_fielding.csv"
EXCEL_BATTING = SUPPLEMENTAL_DIR / "excel_all_seasons_batting.csv"
EXCEL_BOWLING = SUPPLEMENTAL_DIR / "excel_all_seasons_bowling.csv"
COVERAGE_BY_SEASON = SOURCE_COVERAGE_DIR / "grdcc_source_coverage_by_season.csv"
PC_REVIEW = VALIDATION_DIR / "review_exports" / "playcricket_all_anomalies_decision_review_with_data.csv"
EXCEL_REVIEW = VALIDATION_DIR / "review_exports" / "excel_all_anomalies_decision_review_with_data.csv"

BATTING_METRICS = [
    ("matches", "matches", "matches"),
    ("innings", "battingInnings", "battingInnings"),
    ("not_outs", "battingNotOuts", "battingNotOuts"),
    ("runs", "battingAggregate", "battingAggregate"),
    ("high_score", "battingHighScore", "battingHighScore"),
    ("batting_average", "battingAverage", "battingAverage"),
    ("batting_strike_rate", "battingStrikeRate", "battingStrikeRate"),
    ("balls_faced", "battingBallsFaced", "battingBallsFaced"),
    ("50s", "batting50s", "batting50s"),
    ("100s", "batting100s", "batting100s"),
    ("ducks", "batting0s", "batting0s"),
    ("fours", "battingFours", "battingFours"),
    ("sixes", "battingSixes", "battingSixes"),
]

BOWLING_METRICS = [
    ("balls", "bowlingBalls", "bowlingBalls"),
    ("maidens", "bowlingMaidens", "bowlingMaidens"),
    ("bowling_runs_conceded", "bowlingRuns", "bowlingRuns"),
    ("wickets", "bowlingWickets", "bowlingWickets"),
    ("bowling_average", "bowlingAverage", "bowlingAverage"),
    ("economy", "bowlingEconomyRate", "bowlingEconomyRate"),
    ("bowling_strike_rate", "bowlingStrikeRate", "bowlingStrikeRate"),
    ("best_bowling", "bowlingBestInnings", "bowlingBestInnings"),
    ("5wi", "bowling5WIs", "bowling5WIs"),
    ("10wm", "bowling10WMs", "bowling10WMs"),
]

CORE_BATTING_METRICS = {"runs", "innings", "not_outs", "high_score", "batting_average", "50s", "100s", "ducks"}
HEADLINE_BATTING_METRICS = {"runs", "high_score", "50s", "100s"}
UNRELIABLE_EXCEL_BATTING_METRICS = {"matches", "balls_faced", "batting_strike_rate", "fours", "sixes"}
CORE_BOWLING_METRICS = {
    "wickets",
    "balls",
    "overs",
    "bowling_runs_conceded",
    "bowling_average",
    "economy",
    "bowling_strike_rate",
}
HEADLINE_BOWLING_METRICS = {"wickets"}

SUM_COLUMNS = {
    "matches",
    "battingInnings",
    "battingNotOuts",
    "battingAggregate",
    "battingBallsFaced",
    "batting50s",
    "batting100s",
    "batting0s",
    "battingFours",
    "battingSixes",
    "bowlingWickets",
    "bowlingMaidens",
    "bowlingRuns",
    "bowlingBalls",
    "bowling5WIs",
    "bowling10WMs",
}

MAX_COLUMNS = {"battingHighScore"}


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pc_batting_rows = read_csv(PC_BATTING)
    pc_bowling_rows = read_csv(PC_BOWLING)
    pc_fielding_rows = read_csv(PC_FIELDING)
    excel_batting_rows = read_csv(EXCEL_BATTING)
    excel_bowling_rows = read_csv(EXCEL_BOWLING)

    overlap_seasons = load_overlap_seasons()
    pc_quality = load_quality_lookup(PC_REVIEW)
    excel_quality = load_quality_lookup(EXCEL_REVIEW)

    pc_batting = aggregate_rows(pc_batting_rows, "playcricket", "batting", overlap_seasons)
    excel_batting = aggregate_rows(excel_batting_rows, "excel", "batting", overlap_seasons)
    pc_bowling = aggregate_rows(pc_bowling_rows, "playcricket", "bowling", overlap_seasons)
    excel_bowling = aggregate_rows(excel_bowling_rows, "excel", "bowling", overlap_seasons)

    match_audit = build_match_audit(excel_batting, pc_batting, excel_bowling, pc_bowling)
    batting_discrepancies = compare_group(
        excel_batting,
        pc_batting,
        BATTING_METRICS,
        "batting",
        pc_quality,
        excel_quality,
    )
    bowling_discrepancies = compare_group(
        excel_bowling,
        pc_bowling,
        BOWLING_METRICS,
        "bowling",
        pc_quality,
        excel_quality,
    )
    recommendations = build_recommendations(batting_discrepancies, bowling_discrepancies)
    high_priority_review = build_high_priority_review(batting_discrepancies, bowling_discrepancies)
    priority_rules = build_source_priority_rules()
    summary = build_summary(
        overlap_seasons,
        excel_batting,
        pc_batting,
        excel_bowling,
        pc_bowling,
        batting_discrepancies,
        bowling_discrepancies,
        recommendations,
    )
    review_summary = build_review_summary(summary, high_priority_review)
    markdown = build_report(
        overlap_seasons,
        match_audit,
        batting_discrepancies,
        bowling_discrepancies,
        recommendations,
        summary,
        high_priority_review,
        review_summary,
    )

    write_csv(OUTPUT_DIR / "grdcc_batting_overlap_discrepancies.csv", batting_discrepancies)
    write_csv(OUTPUT_DIR / "grdcc_bowling_overlap_discrepancies.csv", bowling_discrepancies)
    write_csv(OUTPUT_DIR / "grdcc_player_match_overlap_audit.csv", match_audit)
    write_csv(OUTPUT_DIR / "grdcc_overlap_discrepancy_summary.csv", summary)
    write_csv(OUTPUT_DIR / "grdcc_overlap_source_priority_recommendations.csv", recommendations)
    write_csv(OUTPUT_DIR / "grdcc_overlap_high_priority_review.csv", high_priority_review)
    write_csv(OUTPUT_DIR / "grdcc_source_priority_rules.csv", priority_rules)
    write_csv(OUTPUT_DIR / "grdcc_overlap_review_summary.csv", review_summary)
    DOC_PATH.write_text(markdown, encoding="utf-8")

    print(f"Overlap seasons count: {len(overlap_seasons)}")
    print(f"Batting metric comparisons: {len(batting_discrepancies)}")
    print(f"Bowling metric comparisons: {len(bowling_discrepancies)}")
    print(f"High discrepancy count: {count_discrepancies(batting_discrepancies + bowling_discrepancies, 'high')}")
    print(f"Medium discrepancy count: {count_discrepancies(batting_discrepancies + bowling_discrepancies, 'medium')}")
    print(f"Manual review count: {sum(1 for row in recommendations if row['manual_review_required'] == 'yes')}")
    print(f"High-priority review row count: {len(high_priority_review)}")
    print(f"P1 count: {sum(1 for row in high_priority_review if row['review_priority'] == 'P1')}")
    print(f"P2 count: {sum(1 for row in high_priority_review if row['review_priority'] == 'P2')}")
    print(f"Private preview blocker count: {sum(1 for row in high_priority_review if row['likely_app_impact'] == 'private_preview_blocker')}")
    print(f"Source priority rules: {(OUTPUT_DIR / 'grdcc_source_priority_rules.csv').relative_to(ROOT)}")
    print(f"Review summary: {(OUTPUT_DIR / 'grdcc_overlap_review_summary.csv').relative_to(ROOT)}")
    print("outputs:")
    for path in [
        OUTPUT_DIR / "grdcc_batting_overlap_discrepancies.csv",
        OUTPUT_DIR / "grdcc_bowling_overlap_discrepancies.csv",
        OUTPUT_DIR / "grdcc_player_match_overlap_audit.csv",
        OUTPUT_DIR / "grdcc_overlap_discrepancy_summary.csv",
        OUTPUT_DIR / "grdcc_overlap_source_priority_recommendations.csv",
        OUTPUT_DIR / "grdcc_overlap_high_priority_review.csv",
        OUTPUT_DIR / "grdcc_source_priority_rules.csv",
        OUTPUT_DIR / "grdcc_overlap_review_summary.csv",
        DOC_PATH,
    ]:
        print(f"- {path.relative_to(ROOT)}")
    return 0


def load_overlap_seasons() -> set[str]:
    rows = read_csv(COVERAGE_BY_SEASON)
    return {
        clean(row.get("season"))
        for row in rows
        if clean(row.get("source_coverage_category")) == "both_sources"
    }


def aggregate_rows(rows: list[dict[str, str]], source: str, group: str, overlap_seasons: set[str]) -> dict[tuple[str, str], dict[str, object]]:
    buckets: dict[tuple[str, str], dict[str, object]] = {}
    for line, row in enumerate(rows, start=2):
        season = clean(row.get("season"))
        if season not in overlap_seasons:
            continue
        name = display_name(row)
        normalized = normalize_name(name)
        if not normalized:
            continue
        key = (season, normalized)
        bucket = buckets.setdefault(
            key,
            {
                "source": source,
                "metric_group": group,
                "season": season,
                "player_name": name,
                "normalized_player_name": normalized,
                "canonical_player_ids": set(),
                "source_rows": [],
                "data_confidences": set(),
                "rows": [],
            },
        )
        bucket["source_rows"].append(str(line))
        bucket["rows"].append(row)
        canonical = clean(row.get("canonical_player_id"))
        if canonical:
            bucket["canonical_player_ids"].add(canonical)
        confidence = clean(row.get("data_confidence"))
        if confidence:
            bucket["data_confidences"].add(confidence)
        for column in SUM_COLUMNS:
            value = number(row.get(column))
            if value is not None:
                bucket[column] = float(bucket.get(column, 0) or 0) + value
        for column in MAX_COLUMNS:
            value = number(row.get(column))
            if value is not None:
                bucket[column] = max(float(bucket.get(column, 0) or 0), value)
        bbi = clean(row.get("bowlingBestInnings"))
        if bbi and not bucket.get("bowlingBestInnings"):
            bucket["bowlingBestInnings"] = bbi
    for bucket in buckets.values():
        derive_calculated_metrics(bucket)
    return buckets


def derive_calculated_metrics(bucket: dict[str, object]) -> None:
    runs = as_float(bucket.get("battingAggregate"))
    innings = as_float(bucket.get("battingInnings"))
    not_outs = as_float(bucket.get("battingNotOuts"))
    balls_faced = as_float(bucket.get("battingBallsFaced"))
    if runs is not None and innings is not None and not_outs is not None and innings > not_outs:
        bucket["battingAverage"] = runs / (innings - not_outs)
    if runs is not None and balls_faced and balls_faced > 0:
        bucket["battingStrikeRate"] = runs / balls_faced * 100
    bowling_runs = as_float(bucket.get("bowlingRuns"))
    wickets = as_float(bucket.get("bowlingWickets"))
    balls = as_float(bucket.get("bowlingBalls"))
    if bowling_runs is not None and wickets and wickets > 0:
        bucket["bowlingAverage"] = bowling_runs / wickets
    if bowling_runs is not None and balls and balls > 0:
        bucket["bowlingEconomyRate"] = bowling_runs * 6 / balls
    if balls is not None and wickets and wickets > 0:
        bucket["bowlingStrikeRate"] = balls / wickets


def load_quality_lookup(path: Path) -> dict[tuple[str, str, str], dict[str, object]]:
    rows = read_csv(path)
    lookup: dict[tuple[str, str, str], dict[str, object]] = defaultdict(lambda: {"statuses": set(), "severities": set(), "decisions": set(), "rows": 0})
    for row in rows:
        season = clean(row.get("season"))
        normalized = normalize_name(row.get("player_name"))
        group = clean(row.get("metric_group"))
        if not season or not normalized or not group:
            continue
        key = (season, normalized, group)
        lookup[key]["statuses"].add(clean(row.get("current_app_status") or row.get("qa_status")))
        lookup[key]["severities"].add(clean(row.get("highest_severity")))
        lookup[key]["decisions"].add(clean(row.get("suggested_decision")))
        lookup[key]["rows"] += 1
    return lookup


def build_match_audit(
    excel_batting: dict[tuple[str, str], dict[str, object]],
    pc_batting: dict[tuple[str, str], dict[str, object]],
    excel_bowling: dict[tuple[str, str], dict[str, object]],
    pc_bowling: dict[tuple[str, str], dict[str, object]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    keys = sorted(set(excel_batting) | set(pc_batting) | set(excel_bowling) | set(pc_bowling), key=lambda key: (season_sort_key(key[0]), key[1]))
    for season, normalized in keys:
        excel_row = excel_batting.get((season, normalized)) or excel_bowling.get((season, normalized))
        pc_row = pc_batting.get((season, normalized)) or pc_bowling.get((season, normalized))
        if excel_row and pc_row:
            excel_ids = set(excel_row.get("canonical_player_ids") or [])
            pc_ids = set(pc_row.get("canonical_player_ids") or [])
            if excel_ids and pc_ids and excel_ids & pc_ids:
                method = "canonical_id"
                confidence = "high"
                issue = ""
                notes = "Shared canonical player ID."
            elif len(pc_ids) > 1 or len(excel_ids) > 1:
                method = "ambiguous"
                confidence = "low"
                issue = "multiple_canonical_ids"
                notes = "Same normalized name maps to multiple canonical IDs."
            else:
                method = "normalized_name"
                confidence = "medium"
                issue = ""
                notes = "Matched by normalized player name and season."
        elif excel_row:
            method = "no_match"
            confidence = "low"
            issue = "excel_only_player_season"
            notes = "Excel player-season has no normalized PlayCricket match."
        else:
            method = "no_match"
            confidence = "low"
            issue = "playcricket_only_player_season"
            notes = "PlayCricket player-season has no normalized Excel match."
        rows.append(
            {
                "season": season,
                "excel_player_name": excel_row.get("player_name", "") if excel_row else "",
                "playcricket_player_name": pc_row.get("player_name", "") if pc_row else "",
                "normalized_player_name": normalized,
                "excel_canonical_player_id": join_set(excel_row.get("canonical_player_ids", set())) if excel_row else "",
                "playcricket_canonical_player_id": join_set(pc_row.get("canonical_player_ids", set())) if pc_row else "",
                "match_method": method,
                "match_confidence": confidence,
                "identity_issue": issue,
                "notes": notes,
            }
        )
    return rows


def compare_group(
    excel: dict[tuple[str, str], dict[str, object]],
    pc: dict[tuple[str, str], dict[str, object]],
    metrics: list[tuple[str, str, str]],
    group: str,
    pc_quality: dict[tuple[str, str, str], dict[str, object]],
    excel_quality: dict[tuple[str, str, str], dict[str, object]],
) -> list[dict[str, object]]:
    comparisons: list[dict[str, object]] = []
    for key in sorted(set(excel) & set(pc), key=lambda key: (season_sort_key(key[0]), key[1])):
        season, normalized = key
        excel_row = excel[key]
        pc_row = pc[key]
        match_method, match_confidence, identity_issue = match_info(excel_row, pc_row)
        for metric, excel_col, pc_col in metrics:
            comparison = compare_metric(metric, excel_row.get(excel_col), pc_row.get(pc_col), group)
            quality_key = (season, normalized, group)
            pc_status = quality_status(pc_quality.get(quality_key, {}))
            excel_status = quality_status(excel_quality.get(quality_key, {}), default="clean")
            recommended, reason = recommend_source(
                comparison,
                metric,
                group,
                excel_row,
                pc_row,
                pc_status,
                excel_status,
                match_confidence,
                identity_issue,
            )
            comparisons.append(
                {
                    "season": season,
                    "player_name": excel_row.get("player_name") or pc_row.get("player_name"),
                    "normalized_player_name": normalized,
                    "match_method": match_method,
                    "match_confidence": match_confidence,
                    "metric": metric,
                    "excel_value": format_value(excel_row.get(excel_col)),
                    "playcricket_value": format_value(pc_row.get(pc_col)),
                    "absolute_difference": comparison["absolute_difference"],
                    "percentage_difference": comparison["percentage_difference"],
                    "discrepancy_type": comparison["discrepancy_type"] if not identity_issue else "identity_ambiguous",
                    "discrepancy_severity": "high" if identity_issue else comparison["discrepancy_severity"],
                    "recommended_source": recommended,
                    "reason": reason,
                    "excel_source_row": ", ".join(excel_row.get("source_rows", [])),
                    "playcricket_source_row": ", ".join(pc_row.get("source_rows", [])),
                    "excel_data_confidence": join_set(excel_row.get("data_confidences", set())) or excel_status,
                    "playcricket_anomaly_status": pc_status,
                    "notes": identity_issue,
                }
            )
    return comparisons


def compare_metric(metric: str, excel_value: object, pc_value: object, group: str) -> dict[str, object]:
    if metric in {"best_bowling"}:
        if not clean(excel_value) and not clean(pc_value):
            dtype, severity = "both_missing", "low"
        elif not clean(excel_value) or not clean(pc_value):
            dtype, severity = "source_not_comparable", "low"
        elif clean(excel_value) == clean(pc_value):
            dtype, severity = "exact_match", "low"
        else:
            dtype, severity = "source_not_comparable", "low"
        return {"absolute_difference": "", "percentage_difference": "", "discrepancy_type": dtype, "discrepancy_severity": severity}
    ev = number(excel_value)
    pv = number(pc_value)
    if ev is None and pv is None:
        return {"absolute_difference": "", "percentage_difference": "", "discrepancy_type": "both_missing", "discrepancy_severity": "low"}
    if ev is None:
        return {"absolute_difference": "", "percentage_difference": "", "discrepancy_type": "excel_missing", "discrepancy_severity": missing_severity(metric, pv)}
    if pv is None:
        return {"absolute_difference": "", "percentage_difference": "", "discrepancy_type": "playcricket_missing", "discrepancy_severity": missing_severity(metric, ev)}
    diff = abs(ev - pv)
    pct = diff / abs(pv) * 100 if pv else (100.0 if diff else 0.0)
    if diff == 0:
        dtype, severity = "exact_match", "low"
    elif is_close(metric, diff, pct):
        dtype, severity = "close_match", "low"
    else:
        dtype, severity = "material_difference", severity_for_difference(group, metric, diff, pct)
    return {
        "absolute_difference": round(diff, 4),
        "percentage_difference": round(pct, 2),
        "discrepancy_type": dtype,
        "discrepancy_severity": severity,
    }


def recommend_source(
    comparison: dict[str, object],
    metric: str,
    group: str,
    excel_row: dict[str, object],
    pc_row: dict[str, object],
    pc_status: str,
    excel_status: str,
    match_confidence: str,
    identity_issue: str,
) -> tuple[str, str]:
    if identity_issue or match_confidence == "low":
        return "manual_review", "Identity ambiguity requires manual review."
    if metric in {"batting_strike_rate", "balls_faced"} and group == "batting":
        return "playcricket", "Aggregate PlayCricket is preferred for modern strike-rate context; BBB-only metrics still require verified ball-by-ball."
    if "excluded_from_app" in pc_status or "high" in pc_status:
        if "clean" in excel_status or excel_row:
            return "excel", "PlayCricket row has high-severity/excluded anomaly status and Excel has clean app-facing data."
    if "rejected" in excel_status or "excluded_from_app" in excel_status or "needs_manual_review" in excel_status:
        return "playcricket", "Excel row is review/rejected/low-confidence; use sane PlayCricket if not anomalous."
    dtype = comparison["discrepancy_type"]
    severity = comparison["discrepancy_severity"]
    if dtype in {"exact_match", "close_match"}:
        return "playcricket", "Sources agree closely; prefer PlayCricket / PlayHQ as modern default and use Excel as corroboration."
    if severity in {"high", "medium"}:
        return "manual_review", "Sources differ materially for the same player-season metric."
    if dtype == "excel_missing":
        return "playcricket", "Only PlayCricket has this metric in the overlap row."
    if dtype == "playcricket_missing":
        return "excel", "Only Excel has this metric in the overlap row."
    if dtype == "source_not_comparable":
        return "manual_review", "Metric is not comparable between sources."
    return "manual_review", "Default to manual review for unresolved overlap."


def build_recommendations(*groups: list[dict[str, object]]) -> list[dict[str, object]]:
    buckets: dict[tuple[str, str, str], list[dict[str, object]]] = defaultdict(list)
    for rows in groups:
        for row in rows:
            buckets[(clean(row["season"]), clean(row["normalized_player_name"]), "batting" if row in groups[0] else "bowling")].append(row)
    output = []
    for (season, normalized, group), rows in sorted(buckets.items(), key=lambda item: (season_sort_key(item[0][0]), item[0][1], item[0][2])):
        severities = Counter(row["discrepancy_severity"] for row in rows)
        recommended_counts = Counter(row["recommended_source"] for row in rows)
        manual_required = severities["high"] > 0 or severities["medium"] > 0 or recommended_counts["manual_review"] > 0
        excel_complete = completeness_score(rows, "excel_value")
        pc_complete = completeness_score(rows, "playcricket_value")
        recommended = recommended_counts.most_common(1)[0][0] if recommended_counts else "manual_review"
        if recommended_counts["manual_review"]:
            recommended = "manual_review"
        output.append(
            {
                "season": season,
                "player_name": rows[0]["player_name"],
                "metric_group": group,
                "match_confidence": rows[0]["match_confidence"],
                "discrepancy_count": sum(1 for row in rows if row["discrepancy_type"] not in {"exact_match", "close_match", "both_missing"}),
                "high_discrepancy_count": severities["high"],
                "medium_discrepancy_count": severities["medium"],
                "low_discrepancy_count": severities["low"],
                "excel_complete_score": excel_complete,
                "playcricket_complete_score": pc_complete,
                "excel_quality_status": rows[0]["excel_data_confidence"],
                "playcricket_quality_status": rows[0]["playcricket_anomaly_status"],
                "recommended_source": recommended,
                "reason": recommendation_reason(rows, recommended),
                "manual_review_required": "yes" if manual_required else "no",
            }
        )
    return output


def build_high_priority_review(
    batting: list[dict[str, object]], bowling: list[dict[str, object]]
) -> list[dict[str, object]]:
    output = []
    for metric_group, rows in (("batting", batting), ("bowling", bowling)):
        core_metrics = CORE_BATTING_METRICS if metric_group == "batting" else CORE_BOWLING_METRICS
        headline_metrics = HEADLINE_BATTING_METRICS if metric_group == "batting" else HEADLINE_BOWLING_METRICS
        for row in rows:
            metric = clean(row["metric"])
            dtype = clean(row["discrepancy_type"])
            severity = clean(row["discrepancy_severity"])
            match_method = clean(row["match_method"])
            anomaly_status = clean(row["playcricket_anomaly_status"]).lower()
            identity_ambiguous = match_method == "ambiguous" or clean(row["match_confidence"]) == "low"
            high_anomaly = "high" in anomaly_status
            already_excluded = "excluded_from_app" in anomaly_status or "already_excluded" in anomaly_status

            if dtype in {"both_missing", "exact_match", "close_match"} or severity == "low":
                continue
            if (
                metric_group == "batting"
                and metric in UNRELIABLE_EXCEL_BATTING_METRICS
                and dtype in {"excel_missing", "playcricket_missing", "source_not_comparable"}
                and not identity_ambiguous
                and not high_anomaly
            ):
                continue
            if not (severity == "high" or (severity == "medium" and metric in core_metrics) or identity_ambiguous or high_anomaly):
                continue

            is_headline = metric in headline_metrics
            if identity_ambiguous or (severity == "high" and is_headline) or (high_anomaly and is_headline):
                priority = "P1"
            elif metric in core_metrics or clean(row["recommended_source"]) in {"excel", "playcricket"}:
                priority = "P2"
            else:
                priority = "P3"

            if already_excluded:
                app_impact = "already_excluded"
                suggested_decision = "confirm_existing_exclusion"
            elif severity == "high" and is_headline:
                app_impact = "private_preview_blocker"
                suggested_decision = source_decision(row)
            elif is_headline:
                app_impact = "headline_record_review"
                suggested_decision = source_decision(row)
            elif metric in core_metrics:
                app_impact = "core_metric_review"
                suggested_decision = source_decision(row)
            else:
                app_impact = "supporting_metric_review"
                suggested_decision = source_decision(row)

            output.append(
                {
                    "review_priority": priority,
                    "player_name": row["player_name"],
                    "season": row["season"],
                    "metric_group": metric_group,
                    "metric": metric,
                    "excel_value": row["excel_value"],
                    "playcricket_value": row["playcricket_value"],
                    "absolute_difference": row["absolute_difference"],
                    "percentage_difference": row["percentage_difference"],
                    "discrepancy_type": dtype,
                    "discrepancy_severity": severity,
                    "recommended_source": row["recommended_source"],
                    "reason": row["reason"],
                    "match_method": row["match_method"],
                    "match_confidence": row["match_confidence"],
                    "excel_source_row": row["excel_source_row"],
                    "playcricket_source_row": row["playcricket_source_row"],
                    "excel_data_confidence": row["excel_data_confidence"],
                    "playcricket_anomaly_status": row["playcricket_anomaly_status"],
                    "likely_app_impact": app_impact,
                    "suggested_decision": suggested_decision,
                    "reviewer_decision": "",
                    "reviewer_notes": "",
                }
            )

    priority_order = {"P1": 0, "P2": 1, "P3": 2}
    severity_order = {"high": 0, "medium": 1, "low": 2}
    return sorted(
        output,
        key=lambda row: (
            priority_order.get(clean(row["review_priority"]), 9),
            severity_order.get(clean(row["discrepancy_severity"]), 9),
            clean(row["metric_group"]),
            season_sort_key(clean(row["season"])),
            clean(row["player_name"]).lower(),
            clean(row["metric"]),
        ),
    )


def source_decision(row: dict[str, object]) -> str:
    recommended = clean(row["recommended_source"])
    if clean(row["match_method"]) == "ambiguous" or clean(row["match_confidence"]) == "low":
        return "manual_identity_review"
    if recommended == "excel":
        return "use_excel_for_player_season_metric"
    if recommended == "playcricket":
        return "use_playcricket_for_player_season_metric"
    return "manual_source_priority_review"


def build_source_priority_rules() -> list[dict[str, str]]:
    return [
        priority_rule("batting", "excel_only", "aggregate batting", "excel", "none", "Use clean Excel for historical seasons absent from PlayCricket.", "Only clean or manually approved rows may feed records."),
        priority_rule("batting", "playcricket_only", "aggregate batting", "playcricket", "none", "Use sane PlayCricket / PlayHQ data.", "High-severity anomalies remain excluded."),
        priority_rule("batting", "overlap", "aggregate batting", "playcricket", "excel", "Use sane PlayCricket by default; use Excel when the PlayCricket row is a high-severity anomaly.", "Material core-metric differences require review; never sum both sources for one player-season."),
        priority_rule("batting", "overlap", "core metrics", "manual_review", "playcricket", "Review material differences in runs, innings, not outs, high score, average, 50s, 100s, or ducks.", "PlayCricket remains the default when both rows are sane and close."),
        priority_rule("bowling", "excel_only", "aggregate bowling", "excel", "none", "Use clean Excel for historical bowling seasons absent from PlayCricket.", "Excel BBI, 5WI, and 10WM remain unavailable unless explicitly verified."),
        priority_rule("bowling", "playcricket_only", "aggregate bowling", "playcricket", "none", "Use sane PlayCricket / PlayHQ data, including seasons after Excel bowling coverage ends.", "Exclude high-severity anomalies unless manually approved."),
        priority_rule("bowling", "overlap", "aggregate bowling", "manual_review", "none", "Do not automatically merge overlap rows; there are currently no matched bowling player-seasons.", "Choose one verified source per player-season and never sum sources."),
        priority_rule("fielding", "all", "fielding aggregates", "playcricket", "none", "Use PlayCricket / PlayHQ only.", "Historical Excel does not provide an app-facing fielding source."),
        priority_rule("bbb_only", "all", "delivery-level metrics", "verified_ball_by_ball_only", "none", "Use verified ball-by-ball data only.", "Never derive BBB-only metrics from Excel or aggregate PlayCricket files."),
    ]


def priority_rule(metric_group: str, season_category: str, metric: str, default_source: str, fallback_source: str, rule: str, caveat: str) -> dict[str, str]:
    return {
        "metric_group": metric_group,
        "season_category": season_category,
        "metric": metric,
        "default_source": default_source,
        "fallback_source": fallback_source,
        "rule": rule,
        "caveat": caveat,
    }


def build_review_summary(summary: list[dict[str, object]], review: list[dict[str, object]]) -> list[dict[str, object]]:
    source_summary = {clean(row["metric"]): row["value"] for row in summary}
    priorities = Counter(clean(row["review_priority"]) for row in review)
    high_core_batting = sum(
        1 for row in review if row["metric_group"] == "batting" and row["metric"] in CORE_BATTING_METRICS and row["discrepancy_severity"] == "high"
    )
    medium_core_batting = sum(
        1 for row in review if row["metric_group"] == "batting" and row["metric"] in CORE_BATTING_METRICS and row["discrepancy_severity"] == "medium"
    )
    return [
        {"metric": "total_overlap_metric_comparisons", "value": source_summary.get("total_metric_comparisons", 0)},
        {"metric": "high_priority_review_rows", "value": len(review)},
        {"metric": "p1_rows", "value": priorities["P1"]},
        {"metric": "p2_rows", "value": priorities["P2"]},
        {"metric": "p3_rows", "value": priorities["P3"]},
        {"metric": "matched_batting_player_seasons", "value": source_summary.get("matched_player_season_batting_rows", 0)},
        {"metric": "matched_bowling_player_seasons", "value": source_summary.get("matched_player_season_bowling_rows", 0)},
        {"metric": "high_core_batting_discrepancies", "value": high_core_batting},
        {"metric": "medium_core_batting_discrepancies", "value": medium_core_batting},
        {"metric": "identity_ambiguous_rows", "value": sum(1 for row in review if row["match_method"] == "ambiguous" or row["match_confidence"] == "low")},
        {"metric": "recommended_default_overlap_source", "value": "playcricket_when_sane"},
        {"metric": "private_preview_blocker_count", "value": sum(1 for row in review if row["likely_app_impact"] == "private_preview_blocker")},
    ]


def build_summary(
    overlap_seasons: set[str],
    excel_batting: dict[tuple[str, str], dict[str, object]],
    pc_batting: dict[tuple[str, str], dict[str, object]],
    excel_bowling: dict[tuple[str, str], dict[str, object]],
    pc_bowling: dict[tuple[str, str], dict[str, object]],
    batting: list[dict[str, object]],
    bowling: list[dict[str, object]],
    recommendations: list[dict[str, object]],
) -> list[dict[str, object]]:
    all_comparisons = batting + bowling
    type_counts = Counter(row["discrepancy_type"] for row in all_comparisons)
    severity_counts = Counter(row["discrepancy_severity"] for row in all_comparisons)
    rec_counts = Counter(row["recommended_source"] for row in recommendations)
    batting_season_overlap = {key[0] for key in excel_batting} & {key[0] for key in pc_batting}
    bowling_season_overlap = {key[0] for key in excel_bowling} & {key[0] for key in pc_bowling}
    return [
        {"metric": "overlap_seasons_count", "value": len(overlap_seasons)},
        {"metric": "batting_overlap_seasons", "value": len(batting_season_overlap)},
        {"metric": "bowling_overlap_seasons", "value": len(bowling_season_overlap)},
        {"metric": "matched_player_season_batting_rows", "value": len(set(excel_batting) & set(pc_batting))},
        {"metric": "unmatched_excel_batting_rows", "value": len(set(excel_batting) - set(pc_batting))},
        {"metric": "unmatched_playcricket_batting_rows", "value": len(set(pc_batting) - set(excel_batting))},
        {"metric": "matched_player_season_bowling_rows", "value": len(set(excel_bowling) & set(pc_bowling))},
        {"metric": "unmatched_excel_bowling_rows", "value": len(set(excel_bowling) - set(pc_bowling))},
        {"metric": "unmatched_playcricket_bowling_rows", "value": len(set(pc_bowling) - set(excel_bowling))},
        {"metric": "total_metric_comparisons", "value": len(all_comparisons)},
        {"metric": "exact_matches", "value": type_counts["exact_match"]},
        {"metric": "close_matches", "value": type_counts["close_match"]},
        {"metric": "material_differences", "value": type_counts["material_difference"]},
        {"metric": "high_discrepancies", "value": severity_counts["high"]},
        {"metric": "medium_discrepancies", "value": severity_counts["medium"]},
        {"metric": "low_discrepancies", "value": severity_counts["low"]},
        {"metric": "manual_review_required_count", "value": sum(1 for row in recommendations if row["manual_review_required"] == "yes")},
        {"metric": "recommended_excel_count", "value": rec_counts["excel"]},
        {"metric": "recommended_playcricket_count", "value": rec_counts["playcricket"]},
        {"metric": "recommended_manual_review_count", "value": rec_counts["manual_review"]},
    ]


def build_report(
    overlap_seasons: set[str],
    match_audit: list[dict[str, object]],
    batting: list[dict[str, object]],
    bowling: list[dict[str, object]],
    recommendations: list[dict[str, object]],
    summary: list[dict[str, object]],
    high_priority_review: list[dict[str, object]],
    review_summary: list[dict[str, object]],
) -> str:
    s = {row["metric"]: row["value"] for row in summary}
    rs = {row["metric"]: row["value"] for row in review_summary}
    high_batting = [row for row in batting if row["discrepancy_severity"] == "high"][:20]
    high_bowling = [row for row in bowling if row["discrepancy_severity"] == "high"][:20]
    lines = [
        "# Georges River Source Overlap Discrepancy Report",
        "",
        "## Executive Summary",
        "",
        f"- Overlap seasons compared: {len(overlap_seasons)}.",
        f"- Matched batting player-season rows: {s.get('matched_player_season_batting_rows', 0)}.",
        f"- Matched bowling player-season rows: {s.get('matched_player_season_bowling_rows', 0)}.",
        f"- Total metric comparisons: {s.get('total_metric_comparisons', 0)}.",
        f"- Exact matches: {s.get('exact_matches', 0)}; close matches: {s.get('close_matches', 0)}; material differences: {s.get('material_differences', 0)}.",
        f"- Manual review required recommendations: {s.get('manual_review_required_count', 0)}.",
        "",
        "## Batting Overlap",
        "",
        f"- Seasons compared: {s.get('batting_overlap_seasons', 0)}.",
        f"- Matched player-seasons: {s.get('matched_player_season_batting_rows', 0)}.",
        f"- Unmatched Excel batting player-seasons: {s.get('unmatched_excel_batting_rows', 0)}.",
        f"- Unmatched PlayCricket batting player-seasons: {s.get('unmatched_playcricket_batting_rows', 0)}.",
        "- Major differences are concentrated where the same player-season aggregate totals differ materially or one source lacks a major stat.",
        "",
        "### Top High-Severity Batting Discrepancies",
        "",
        *markdown_discrepancy_table(high_batting),
        "",
        "## Bowling Overlap",
        "",
        f"- Seasons compared: {s.get('bowling_overlap_seasons', 0)}.",
        f"- Matched player-seasons: {s.get('matched_player_season_bowling_rows', 0)}.",
        f"- Unmatched Excel bowling player-seasons: {s.get('unmatched_excel_bowling_rows', 0)}.",
        f"- Unmatched PlayCricket bowling player-seasons: {s.get('unmatched_playcricket_bowling_rows', 0)}.",
        "- Excel bowling overlap is limited; BBI/5WI/10WM are marked not comparable unless both sources explicitly capture them.",
        "",
        "### Top High-Severity Bowling Discrepancies",
        "",
        *markdown_discrepancy_table(high_bowling),
        "",
        "## Source Priority Recommendations",
        "",
        f"- Recommended Excel rows: {s.get('recommended_excel_count', 0)}.",
        f"- Recommended PlayCricket rows: {s.get('recommended_playcricket_count', 0)}.",
        f"- Recommended manual review rows: {s.get('recommended_manual_review_count', 0)}.",
        "- Use PlayCricket when both sources are sane and agree closely, especially for modern/current aggregate records.",
        "- Use Excel when PlayCricket has high-severity anomaly status and Excel is clean and complete.",
        "- Use manual review when values differ materially or identity matching is ambiguous.",
        "- Use neither source for BBB-only metrics unless verified ball-by-ball data exists.",
        "",
        "## Why Manual Review Count Is High",
        "",
        "- The original recommendation count is player-season level and becomes conservative when any one of many compared fields is missing or differs.",
        "- Excel does not reliably capture several modern fields such as balls faced, strike rate, fours, sixes, and some match counts, so exhaustive comparison creates noise that does not affect client-visible records.",
        "- The high-priority export removes exact, close, low-severity, both-missing, and expected non-core Excel gaps.",
        "",
        "## What Actually Needs Review Before Preview",
        "",
        f"- High-priority discrepancy rows: {rs.get('high_priority_review_rows', 0)}.",
        f"- P1 rows: {rs.get('p1_rows', 0)}; P2 rows: {rs.get('p2_rows', 0)}; P3 rows: {rs.get('p3_rows', 0)}.",
        f"- Private preview blockers: {rs.get('private_preview_blocker_count', 0)}.",
        "- Review P1 headline and identity rows first. P2 rows affect core aggregates or source choice. P3 rows are supporting context.",
        "",
        "## Recommended Source Rules",
        "",
        "- Excel-only seasons: use clean Excel aggregates.",
        "- PlayCricket-only seasons: use sane PlayCricket / PlayHQ aggregates.",
        "- Overlap batting seasons: prefer sane PlayCricket; fall back to clean Excel when PlayCricket has a high-severity anomaly.",
        "- Material core-metric differences require a source decision, and the two sources must never be summed for the same player-season.",
        "- Bowling overlap has no matched player-season rows, so do not automatically merge it. Fielding remains PlayCricket-only.",
        "- BBB-only metrics require verified ball-by-ball data.",
        "",
        "## High-Priority Overlap Review File",
        "",
        "- Use `grdcc_overlap_high_priority_review.csv` as the working decision file.",
        "- It contains one row per decision-relevant player-season-metric discrepancy with blank reviewer decision and notes fields.",
        "- The operating rules are recorded in `grdcc_source_priority_rules.csv`; compact counts are in `grdcc_overlap_review_summary.csv`.",
        "",
        "## Private Preview Blocker Definition",
        "",
        "- A discrepancy blocks private preview only when it is app-facing, high severity, not already excluded, and affects a headline record metric.",
        "- Non-headline P2/P3 differences and already excluded anomalies remain review work but do not automatically block preview.",
        "",
        "## Caveats",
        "",
        "- Excel matches are weak/incomplete in some seasons and are grouped by normalized player name, not a manual merge decision.",
        "- Excel bowling coverage is limited to early seasons.",
        "- PlayCricket has anomaly rows that must remain filtered unless manually approved.",
        "- Player identity matching by normalized name can be imperfect; ambiguous rows are flagged rather than merged.",
        "",
        "## Recommended Next Step",
        "",
        "- Review high-severity overlap discrepancies first.",
        "- Then decide source priority for overlap seasons.",
        "- Do not block private preview if discrepancies are not driving headline records.",
    ]
    return "\n".join(lines) + "\n"


def match_info(excel_row: dict[str, object], pc_row: dict[str, object]) -> tuple[str, str, str]:
    excel_ids = set(excel_row.get("canonical_player_ids") or [])
    pc_ids = set(pc_row.get("canonical_player_ids") or [])
    if excel_ids and pc_ids and excel_ids & pc_ids:
        return "canonical_id", "high", ""
    if len(excel_ids) > 1 or len(pc_ids) > 1:
        return "ambiguous", "low", "multiple_canonical_ids"
    return "normalized_name", "medium", ""


def quality_status(quality: dict[str, object], default: str = "none") -> str:
    if not quality:
        return default
    parts = []
    for key in ["statuses", "severities", "decisions"]:
        values = sorted(v for v in quality.get(key, set()) if v)
        if values:
            parts.append(f"{key}={','.join(values)}")
    return " | ".join(parts) if parts else default


def missing_severity(metric: str, present_value: float | None) -> str:
    if present_value is None:
        return "low"
    if metric in {"runs", "innings", "high_score", "wickets", "bowling_runs_conceded", "balls"} and present_value > 0:
        return "high"
    return "low"


def is_close(metric: str, diff: float, pct: float) -> bool:
    if metric in {"batting_average", "bowling_average", "economy", "bowling_strike_rate"}:
        return diff <= 0.1
    return diff <= 1 or pct <= 1


def severity_for_difference(group: str, metric: str, diff: float, pct: float) -> str:
    if group == "batting":
        if metric == "runs":
            return "high" if diff > 100 else "medium" if diff >= 20 else "low"
        if metric == "innings":
            return "high" if diff > 5 else "medium" if diff >= 2 else "low"
        if metric in {"high_score", "50s", "100s"}:
            return "high"
        if metric in {"batting_average", "batting_strike_rate"}:
            return "medium" if diff > 1 else "low"
    if group == "bowling":
        if metric == "wickets":
            return "high" if diff > 10 else "medium" if diff >= 3 else "low"
        if metric == "bowling_runs_conceded":
            return "high" if diff > 100 else "medium" if diff >= 30 else "low"
        if metric == "balls":
            return "high" if diff > 60 else "medium" if diff >= 18 else "low"
        if metric in {"bowling_average", "economy", "bowling_strike_rate"}:
            return "medium" if pct > 20 else "low"
    return "medium" if pct > 10 else "low"


def completeness_score(rows: list[dict[str, object]], field: str) -> float:
    if not rows:
        return 0.0
    present = sum(1 for row in rows if clean(row.get(field)) != "")
    return round(present / len(rows), 3)


def recommendation_reason(rows: list[dict[str, object]], recommended: str) -> str:
    if recommended == "manual_review":
        return "At least one metric has material discrepancy, anomaly, or non-comparable source status."
    if recommended == "excel":
        return "Excel is cleaner or more complete for the compared overlap row."
    if recommended == "playcricket":
        return "PlayCricket is sane/preferred for modern aggregate data or is the only comparable source."
    return "Review required."


def count_discrepancies(rows: list[dict[str, object]], severity: str) -> int:
    return sum(1 for row in rows if row["discrepancy_severity"] == severity)


def markdown_discrepancy_table(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["- None."]
    output = ["| Season | Player | Metric | Excel | PlayCricket | Severity | Recommended |", "|---|---|---|---:|---:|---|---|"]
    for row in rows:
        output.append(
            f"| {row['season']} | {row['player_name']} | {row['metric']} | {row['excel_value']} | {row['playcricket_value']} | {row['discrepancy_severity']} | {row['recommended_source']} |"
        )
    return output


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = ordered_columns(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def ordered_columns(rows: list[dict[str, object]]) -> list[str]:
    columns = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                columns.append(key)
                seen.add(key)
    return columns


def display_name(row: dict[str, str]) -> str:
    return clean(row.get("canonical_player_name") or row.get("player_name") or row.get("raw_player_name"))


def normalize_name(value: object) -> str:
    text = clean(value).casefold()
    text = re.sub(r"[*]+", "", text)
    text = re.sub(r"[^a-z0-9\s]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def number(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def as_float(value: object) -> float | None:
    if isinstance(value, (int, float)) and not math.isnan(float(value)):
        return float(value)
    return number(value)


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def format_value(value: object) -> str:
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return clean(value)


def join_set(values: set[str]) -> str:
    return " | ".join(sorted(v for v in values if v))


def season_sort_key(season: object) -> int:
    match = re.search(r"(18|19|20)\d{2}", clean(season))
    return int(match.group()) if match else -1


if __name__ == "__main__":
    raise SystemExit(main())
