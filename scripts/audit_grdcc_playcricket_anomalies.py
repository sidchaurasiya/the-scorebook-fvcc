#!/usr/bin/env python3
"""Audit GRDCC primary PlayCricket processed data for anomalous records."""

from __future__ import annotations

import csv
import difflib
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLUB_DIR = ROOT / "clubs" / "georges-river-district"
PROCESSED_DIR = CLUB_DIR / "data" / "processed"
VALIDATION_DIR = PROCESSED_DIR / "validation"
SOURCE_DIR = CLUB_DIR / "data" / "source"

PRIMARY_FILES = {
    "batting": PROCESSED_DIR / "all_seasons_batting.csv",
    "bowling": PROCESSED_DIR / "all_seasons_bowling.csv",
    "fielding": PROCESSED_DIR / "all_seasons_fielding.csv",
    "match": PROCESSED_DIR / "all_seasons_matches.csv",
}

AUDIT_COLUMNS = [
    "source_system",
    "source_file",
    "source_row",
    "player_name",
    "canonical_player_id",
    "season",
    "team",
    "grade",
    "metric_group",
    "metric_name",
    "metric_value",
    "issue_code",
    "issue_type",
    "severity",
    "reason",
    "recommended_action",
    "app_facing_allowed",
    "notes",
]

DECISION_REVIEW_COLUMNS = [
    "source_system",
    "source_file",
    "source_row",
    "player_name",
    "canonical_player_id",
    "season",
    "team",
    "grade",
    "metric_group",
    "issue_codes",
    "issue_reasons",
    "highest_severity",
    "recommended_actions",
    "app_facing_allowed",
    "current_app_status",
    "suggested_decision",
    "decision_priority",
    "notes",
]

DECISION_SUMMARY_COLUMNS = ["summary_group", "value", "count"]

DECISION_COLUMNS = [
    "source_file",
    "source_row",
    "player_name",
    "season",
    "issue_code",
    "approved",
    "corrected_metric",
    "corrected_value",
    "exclude_from_records",
    "notes",
    "reviewed_by",
    "reviewed_date",
]


def main() -> int:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    ensure_decision_template()

    rows_by_group = {group: read_csv(path) if path.exists() else [] for group, path in PRIMARY_FILES.items()}
    scanned = {str(path.relative_to(ROOT)): len(rows) for group, rows in rows_by_group.items() for path in [PRIMARY_FILES[group]]}

    anomalies: list[dict[str, object]] = []
    anomalies.extend(audit_batting(rows_by_group["batting"], PRIMARY_FILES["batting"]))
    anomalies.extend(audit_bowling(rows_by_group["bowling"], PRIMARY_FILES["bowling"]))
    anomalies.extend(audit_fielding(rows_by_group["fielding"], PRIMARY_FILES["fielding"]))

    duplicate_rows = audit_duplicates(rows_by_group)
    anomalies.extend(row for row in duplicate_rows if row.get("metric_group") == "identity")

    app_lineage = audit_app_facing_lineage(rows_by_group["bowling"], anomalies)
    anomalies.extend(app_lineage["anomalies"])

    write_csv(VALIDATION_DIR / "playcricket_anomaly_audit.csv", anomalies, AUDIT_COLUMNS)
    write_csv(VALIDATION_DIR / "playcricket_batting_anomalies.csv", [r for r in anomalies if r["metric_group"] == "batting"], AUDIT_COLUMNS)
    write_csv(VALIDATION_DIR / "playcricket_bowling_anomalies.csv", [r for r in anomalies if r["metric_group"] == "bowling"], AUDIT_COLUMNS)
    write_csv(VALIDATION_DIR / "playcricket_fielding_anomalies.csv", [r for r in anomalies if r["metric_group"] == "fielding"], AUDIT_COLUMNS)
    write_csv(VALIDATION_DIR / "playcricket_duplicate_player_season_audit.csv", duplicate_rows, AUDIT_COLUMNS)
    decision_rows = build_decision_review(anomalies)
    decision_summary_rows = build_decision_summary(decision_rows)
    write_csv(VALIDATION_DIR / "playcricket_anomaly_decision_review.csv", decision_rows, DECISION_REVIEW_COLUMNS)
    write_csv(VALIDATION_DIR / "playcricket_anomaly_decision_summary.csv", decision_summary_rows, DECISION_SUMMARY_COLUMNS)
    summary_rows = build_summary(scanned, anomalies, app_lineage)
    write_csv(VALIDATION_DIR / "playcricket_anomaly_summary.csv", summary_rows, ["metric", "value"])
    write_report(scanned, anomalies, duplicate_rows, app_lineage, rows_by_group, decision_rows, decision_summary_rows)

    severity_counts = Counter(str(row["severity"]) for row in anomalies)
    print("rows scanned:")
    for source_file, count in scanned.items():
        print(f"- {source_file}: {count}")
    print(f"high severity count: {severity_counts.get('high', 0)}")
    print(f"medium severity count: {severity_counts.get('medium', 0)}")
    print(f"low severity count: {severity_counts.get('low', 0)}")
    print(f"app-facing dangerous records: {app_lineage['dangerous_count']}")
    print(f"Nathan Percy status: {app_lineage['nathan_percy_status']}")
    print(f"John Young trace status: {app_lineage['john_young_status']}")
    print("outputs:")
    for path in [
        VALIDATION_DIR / "playcricket_anomaly_audit.csv",
        VALIDATION_DIR / "playcricket_batting_anomalies.csv",
        VALIDATION_DIR / "playcricket_bowling_anomalies.csv",
        VALIDATION_DIR / "playcricket_fielding_anomalies.csv",
        VALIDATION_DIR / "playcricket_duplicate_player_season_audit.csv",
        VALIDATION_DIR / "playcricket_anomaly_decision_review.csv",
        VALIDATION_DIR / "playcricket_anomaly_decision_summary.csv",
        VALIDATION_DIR / "playcricket_anomaly_summary.csv",
        ROOT / "docs" / "georges_river_playcricket_anomaly_audit_report.md",
        SOURCE_DIR / "playcricket_manual_anomaly_decisions.csv",
    ]:
        print(f"- {path.relative_to(ROOT)}")
    return 0


def audit_batting(rows: list[dict[str, str]], path: Path) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for line, row in enumerate(rows, start=2):
        player = clean_text(row.get("player_name"))
        season = clean_text(row.get("season"))
        runs = num(row.get("battingAggregate"))
        innings = num(row.get("battingInnings"))
        not_outs = num(row.get("battingNotOuts"))
        high_score = num(row.get("battingHighScore"))
        hundreds = num(row.get("batting100s"))
        fifties = num(row.get("batting50s"))
        ducks = num(row.get("batting0s"))
        average = num(row.get("battingAverage"))
        strike_rate = num(row.get("battingStrikeRate"))
        balls = num(row.get("battingBallsFaced"))

        if invalid_player_name(player):
            issues.append(issue(path, line, row, "batting", "player_name", player, "invalid_player_name", "missing_required", "high", "Player name is blank, masked, numeric-only, or lacks letters.", "exclude_from_records", "no"))
        for metric, value in [
            ("battingAggregate", runs),
            ("battingInnings", innings),
            ("battingNotOuts", not_outs),
            ("battingHighScore", high_score),
            ("batting100s", hundreds),
            ("batting50s", fifties),
            ("batting0s", ducks),
            ("battingAverage", average),
            ("battingStrikeRate", strike_rate),
            ("battingBallsFaced", balls),
        ]:
            if value is not None and value < 0:
                issues.append(issue(path, line, row, "batting", metric, value, "negative_batting_metric", "invalid", "high", f"{metric} is negative.", "exclude_from_records", "no"))
        if high_score is not None and runs is not None and high_score > runs:
            issues.append(issue(path, line, row, "batting", "battingHighScore", high_score, "high_score_gt_runs", "invalid", "high", "High score exceeds total season runs.", "exclude_from_records", "no"))
        for metric, value in [("batting100s", hundreds), ("batting50s", fifties), ("batting0s", ducks)]:
            if value is not None and innings is not None and value > innings:
                issues.append(issue(path, line, row, "batting", metric, value, f"{metric}_gt_innings", "invalid", "high", f"{metric} exceeds innings.", "exclude_from_records", "no"))
        if not_outs is not None and innings is not None and not_outs > innings:
            issues.append(issue(path, line, row, "batting", "battingNotOuts", not_outs, "not_outs_gt_innings", "invalid", "high", "Not-outs exceed innings.", "exclude_from_records", "no"))
        if runs is not None and runs > 0 and innings is not None and innings == 0:
            issues.append(issue(path, line, row, "batting", "battingInnings", innings, "runs_with_zero_innings", "contradiction", "high", "Runs recorded with zero innings.", "exclude_from_records", "no"))
        if runs is not None and runs > 1500:
            issues.append(issue(path, line, row, "batting", "battingAggregate", runs, "season_runs_gt_1500", "suspicious", "medium", "Season runs exceed 1500.", "needs_manual_review", "pending"))
        if innings is not None and innings > 40:
            issues.append(issue(path, line, row, "batting", "battingInnings", innings, "innings_gt_40", "suspicious", "medium", "Season innings exceed 40.", "needs_manual_review", "pending"))
        if average is not None and average > 250 and innings is not None and not_outs is not None and innings - not_outs > 0:
            issues.append(issue(path, line, row, "batting", "battingAverage", average, "batting_average_gt_250", "suspicious", "medium", "Batting average exceeds 250 with meaningful dismissals.", "needs_manual_review", "pending"))
        if strike_rate is not None and strike_rate > 300 and balls is not None and balls > 0:
            issues.append(issue(path, line, row, "batting", "battingStrikeRate", strike_rate, "batting_strike_rate_gt_300", "suspicious", "medium", "Strike rate exceeds 300 with balls faced present.", "needs_manual_review", "pending"))
        if high_score is not None and high_score > 250:
            issues.append(issue(path, line, row, "batting", "battingHighScore", high_score, "high_score_gt_250", "suspicious", "medium", "High score exceeds 250.", "needs_manual_review", "pending"))
        if runs is not None and runs > 1000 and (innings is None or innings == 0):
            issues.append(issue(path, line, row, "batting", "battingAggregate", runs, "high_runs_missing_innings", "suspicious", "medium", "Very high runs with missing innings.", "needs_manual_review", "pending"))
    issues.extend(audit_duplicate_metric_rows(rows, path, "batting", ["battingAggregate", "battingInnings", "battingHighScore"]))
    return issues


def audit_bowling(rows: list[dict[str, str]], path: Path) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for line, row in enumerate(rows, start=2):
        wickets = num(row.get("bowlingWickets"))
        runs = num(row.get("bowlingRuns"))
        balls = num(row.get("bowlingBalls"))
        overs = balls / 6 if balls is not None else None
        matches = num(row.get("matches"))
        maidens = num(row.get("bowlingMaidens"))
        average = num(row.get("bowlingAverage"))
        strike_rate = num(row.get("bowlingStrikeRate"))
        economy = num(row.get("bowlingEconomyRate"))
        five_wi = num(row.get("bowling5WIs"))
        ten_wm = num(row.get("bowling10WMs"))
        bbi_wickets, bbi_runs = parse_bbi(row.get("bowlingBestInnings"))

        if invalid_player_name(row.get("player_name")):
            issues.append(issue(path, line, row, "bowling", "player_name", row.get("player_name"), "invalid_player_name", "missing_required", "high", "Player name is blank, masked, numeric-only, or lacks letters.", "exclude_from_records", "no"))
        for metric, value in [
            ("bowlingWickets", wickets),
            ("bowlingRuns", runs),
            ("bowlingBalls", balls),
            ("bowlingMaidens", maidens),
            ("bowling5WIs", five_wi),
            ("bowling10WMs", ten_wm),
        ]:
            if value is not None and value < 0:
                issues.append(issue(path, line, row, "bowling", metric, value, "negative_bowling_metric", "invalid", "high", f"{metric} is negative.", "exclude_from_records", "no"))
        if wickets is not None and runs is not None and wickets >= 50 and runs <= 10:
            issues.append(issue(path, line, row, "bowling", "bowlingWickets", wickets, "wickets_ge_50_runs_le_10", "contradiction", "high", "At least 50 wickets with 10 or fewer runs conceded is not credible.", "exclude_from_records", "no"))
        if wickets is not None and runs is not None and wickets >= 20 and runs <= wickets:
            issues.append(issue(path, line, row, "bowling", "bowlingRuns", runs, "runs_lte_wickets_high_workload", "contradiction", "high", "Runs conceded are less than/equal to wickets for a high wicket total.", "exclude_from_records", "no"))
        if average is not None and wickets is not None and average < 1 and wickets >= 10:
            issues.append(issue(path, line, row, "bowling", "bowlingAverage", average, "bowling_average_lt_1", "contradiction", "high", "Bowling average below 1 with at least 10 wickets.", "exclude_from_records", "no"))
        if economy is not None and wickets is not None and economy < 0.5 and wickets >= 10:
            issues.append(issue(path, line, row, "bowling", "bowlingEconomyRate", economy, "economy_lt_0_5", "contradiction", "high", "Economy below 0.5 with at least 10 wickets.", "exclude_from_records", "no"))
        if wickets is not None and balls is not None and wickets > balls:
            issues.append(issue(path, line, row, "bowling", "bowlingWickets", wickets, "wickets_gt_balls", "invalid", "high", "Wickets exceed balls bowled.", "exclude_from_records", "no"))
        if wickets is not None and balls is not None and balls < wickets * 2:
            issues.append(issue(path, line, row, "bowling", "bowlingBalls", balls, "balls_lt_wickets_x2", "suspicious", "high", "Balls bowled are less than twice wickets taken.", "exclude_from_records", "no"))
        if matches is not None and matches == 0 and wickets is not None and wickets > 0:
            issues.append(issue(path, line, row, "bowling", "matches", matches, "wickets_with_zero_matches", "contradiction", "high", "Wickets with zero matches.", "exclude_from_records", "no"))
        if overs is not None and overs <= 0 and wickets is not None and wickets > 0:
            issues.append(issue(path, line, row, "bowling", "bowlingBalls", balls, "wickets_with_zero_overs", "contradiction", "high", "Wickets with zero overs/balls.", "exclude_from_records", "no"))
        if bbi_wickets is not None and wickets is not None and bbi_wickets > wickets:
            issues.append(issue(path, line, row, "bowling", "bowlingBestInnings", row.get("bowlingBestInnings"), "bbi_wickets_gt_total_wickets", "contradiction", "high", "BBI wickets exceed total season wickets.", "exclude_from_records", "no"))
        if bbi_runs is not None and runs is not None and bbi_runs > runs:
            issues.append(issue(path, line, row, "bowling", "bowlingBestInnings", row.get("bowlingBestInnings"), "bbi_runs_gt_total_runs", "contradiction", "high", "BBI runs conceded exceed total season runs conceded.", "exclude_from_records", "no"))
        if maidens is not None and overs is not None and maidens > overs:
            issues.append(issue(path, line, row, "bowling", "bowlingMaidens", maidens, "maidens_gt_overs", "invalid", "high", "Maidens exceed overs.", "exclude_from_records", "no"))
        if five_wi is not None and matches is not None and five_wi > matches:
            issues.append(issue(path, line, row, "bowling", "bowling5WIs", five_wi, "fivewi_gt_matches", "invalid", "high", "5WI count exceeds matches.", "exclude_from_records", "no"))
        if ten_wm is not None and matches is not None and ten_wm > matches:
            issues.append(issue(path, line, row, "bowling", "bowling10WMs", ten_wm, "tenwm_gt_matches", "invalid", "high", "10WM count exceeds matches.", "exclude_from_records", "no"))
        if ten_wm is not None and five_wi is not None and ten_wm > five_wi:
            issues.append(issue(path, line, row, "bowling", "bowling10WMs", ten_wm, "tenwm_gt_fivewi", "contradiction", "high", "10WM count exceeds comparable 5WI count.", "exclude_from_records", "no"))
        if wickets is not None and wickets > 100:
            issues.append(issue(path, line, row, "bowling", "bowlingWickets", wickets, "wickets_gt_100", "suspicious", "medium", "More than 100 wickets in one season.", "needs_manual_review", "pending"))
        elif wickets is not None and wickets > 80:
            issues.append(issue(path, line, row, "bowling", "bowlingWickets", wickets, "wickets_gt_80", "suspicious", "medium", "More than 80 wickets in one season.", "needs_manual_review", "pending"))
        if economy is not None and economy > 15 and balls is not None and balls >= 60:
            issues.append(issue(path, line, row, "bowling", "bowlingEconomyRate", economy, "economy_gt_15", "suspicious", "medium", "Economy above 15 with meaningful overs.", "needs_manual_review", "pending"))
        if average is not None and average > 100 and wickets is not None and wickets > 0:
            issues.append(issue(path, line, row, "bowling", "bowlingAverage", average, "bowling_average_gt_100", "suspicious", "medium", "Bowling average above 100 with wickets.", "needs_manual_review", "pending"))
        if strike_rate is not None and wickets is not None and wickets >= 10 and strike_rate < 3:
            issues.append(issue(path, line, row, "bowling", "bowlingStrikeRate", strike_rate, "strike_rate_lt_3", "suspicious", "medium", "Strike rate below 3 with at least 10 wickets.", "needs_manual_review", "pending"))
        if strike_rate is not None and wickets is not None and wickets > 0 and strike_rate > 300:
            issues.append(issue(path, line, row, "bowling", "bowlingStrikeRate", strike_rate, "strike_rate_gt_300", "suspicious", "medium", "Strike rate above 300 with wickets.", "needs_manual_review", "pending"))
        if balls is None and wickets is not None and wickets > 40:
            issues.append(issue(path, line, row, "bowling", "bowlingBalls", "", "high_wickets_missing_balls", "suspicious", "medium", "High wicket total with missing balls bowled.", "needs_manual_review", "pending"))
    issues.extend(audit_duplicate_metric_rows(rows, path, "bowling", ["bowlingWickets", "bowlingRuns", "bowlingBalls"]))
    return issues


def audit_fielding(rows: list[dict[str, str]], path: Path) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    for line, row in enumerate(rows, start=2):
        player = clean_text(row.get("player_name"))
        catches = num(row.get("fieldingTotalCatches"))
        catches_non_wk = num(row.get("fieldingCatchesNonWK"))
        catches_wk = num(row.get("fieldingCatchesWK"))
        stumpings = num(row.get("fieldingStumpings"))
        run_outs = num(row.get("fieldingRunOuts"))
        dismissals = sum(v or 0 for v in [catches, stumpings, run_outs])
        if invalid_player_name(player):
            issues.append(issue(path, line, row, "fielding", "player_name", player, "invalid_player_name", "missing_required", "high", "Player name is blank, masked, numeric-only, or lacks letters.", "exclude_from_records", "no"))
        for metric, value in [
            ("fieldingTotalCatches", catches),
            ("fieldingCatchesNonWK", catches_non_wk),
            ("fieldingCatchesWK", catches_wk),
            ("fieldingStumpings", stumpings),
            ("fieldingRunOuts", run_outs),
        ]:
            if value is not None and value < 0:
                issues.append(issue(path, line, row, "fielding", metric, value, "negative_fielding_metric", "invalid", "high", f"{metric} is negative.", "exclude_from_records", "no"))
        if catches is not None and catches_non_wk is not None and catches_wk is not None and catches < catches_non_wk + catches_wk:
            issues.append(issue(path, line, row, "fielding", "fieldingTotalCatches", catches, "dismissals_lt_catches_plus_stumpings", "invalid", "high", "Total catches less than catches components.", "exclude_from_records", "no"))
        if catches is not None and catches > 60:
            issues.append(issue(path, line, row, "fielding", "fieldingTotalCatches", catches, "catches_gt_60", "suspicious", "medium", "More than 60 catches in one season.", "needs_manual_review", "pending"))
        if stumpings is not None and stumpings > 40:
            issues.append(issue(path, line, row, "fielding", "fieldingStumpings", stumpings, "stumpings_gt_40", "suspicious", "medium", "More than 40 stumpings in one season.", "needs_manual_review", "pending"))
        if dismissals > 80:
            issues.append(issue(path, line, row, "fielding", "fielding_dismissals", dismissals, "dismissals_gt_80", "suspicious", "medium", "More than 80 fielding dismissals in one season.", "needs_manual_review", "pending"))
    issues.extend(audit_duplicate_metric_rows(rows, path, "fielding", ["fieldingTotalCatches", "fieldingStumpings", "fieldingRunOuts"]))
    return issues


def audit_duplicate_metric_rows(rows: list[dict[str, str]], path: Path, group: str, metrics: list[str]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    buckets: dict[tuple[str, str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for line, row in enumerate(rows, start=2):
        key = (clean_text(row.get("canonical_player_id") or row.get("player_id")), clean_text(row.get("season")), clean_text(row.get("grade_name")))
        if any((num(row.get(metric)) or 0) > 0 for metric in metrics):
            buckets[key].append((line, row))
    for _key, entries in buckets.items():
        if len(entries) <= 1:
            continue
        for line, row in entries:
            issues.append(issue(path, line, row, group, "duplicate_player_season_grade", len(entries), f"duplicate_{group}_player_season_grade", "duplicate", "medium", f"Same canonical player/season/grade has {len(entries)} rows with overlapping {group} metrics.", "needs_manual_review", "pending"))
    return issues


def audit_duplicates(rows_by_group: dict[str, list[dict[str, str]]]) -> list[dict[str, object]]:
    rows = rows_by_group.get("batting", []) + rows_by_group.get("bowling", []) + rows_by_group.get("fielding", [])
    output: list[dict[str, object]] = []
    by_name_season: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_canonical: dict[str, set[str]] = defaultdict(set)
    season_names: dict[str, set[str]] = defaultdict(set)
    representative: dict[tuple[str, str], dict[str, str]] = {}
    source_line: dict[tuple[str, str], int] = {}
    for line, row in enumerate(rows, start=2):
        name = clean_text(row.get("player_name"))
        canonical = clean_text(row.get("canonical_player_id") or row.get("player_id"))
        season = clean_text(row.get("season"))
        if name and season:
            by_name_season[(name.casefold(), season)].add(canonical)
            season_names[season].add(name)
            representative.setdefault((name.casefold(), season), row)
            source_line.setdefault((name.casefold(), season), line)
        if canonical:
            by_canonical[canonical].add(name)
    for (name_key, season), canonical_ids in by_name_season.items():
        if len(canonical_ids) > 1:
            row = representative[(name_key, season)]
            output.append(issue(PROCESSED_DIR / "all_seasons_batting.csv", source_line[(name_key, season)], row, "identity", "canonical_player_id", " | ".join(sorted(canonical_ids)), "same_name_season_multiple_canonical_ids", "duplicate", "medium", "Same player name and season appears with multiple canonical IDs.", "merge_candidate", "pending"))
    for canonical, names in by_canonical.items():
        clean_names = {name for name in names if name}
        if len(clean_names) > 1:
            sample_name = sorted(clean_names)[0]
            row = {"player_name": sample_name, "canonical_player_id": canonical, "season": "", "team_name": "", "grade_name": ""}
            output.append(issue(PROCESSED_DIR / "players.csv", "", row, "identity", "player_name", " | ".join(sorted(clean_names)), "same_canonical_multiple_names", "duplicate", "low", "Same canonical ID appears with multiple display names.", "accept_with_warning", "yes"))
    for season, names in season_names.items():
        sorted_names = sorted(names)
        for idx, name in enumerate(sorted_names):
            for other in sorted_names[idx + 1 : idx + 8]:
                if name[:1].casefold() != other[:1].casefold():
                    continue
                ratio = difflib.SequenceMatcher(None, name.casefold(), other.casefold()).ratio()
                if ratio >= 0.92 and name != other:
                    row = {"player_name": name, "canonical_player_id": "", "season": season, "team_name": "", "grade_name": ""}
                    output.append(issue(PROCESSED_DIR / "players.csv", "", row, "identity", "player_name", f"{name} | {other}", "minor_spelling_variant_same_season", "duplicate", "low", "Similar player names appear in the same season.", "merge_candidate", "pending"))
    return output


def audit_app_facing_lineage(bowling_rows: list[dict[str, str]], anomalies: list[dict[str, object]]) -> dict[str, object]:
    anomaly_keys = {(row["source_file"], str(row["source_row"])) for row in anomalies if row["metric_group"] == "bowling" and row["severity"] == "high"}
    dangerous = [row for row in anomalies if (row["source_file"], str(row["source_row"])) in anomaly_keys and row["recommended_action"] == "exclude_from_records"]
    nathan_rows = [row for line, row in enumerate(bowling_rows, start=2) if clean_text(row.get("player_name")) == "Nathan Percy" and clean_text(row.get("season")) == "Summer 1995/96"]
    nathan_status = "not found"
    if nathan_rows:
        total_raw = sum(num(row.get("bowlingWickets")) or 0 for row in nathan_rows)
        total_filtered = sum((num(row.get("bowlingWickets")) or 0) for row in nathan_rows if not primary_bowling_row_is_filtered(row))
        nathan_status = f"raw rows={len(nathan_rows)} raw_wickets={total_raw:g} app_facing_after_filter={total_filtered:g}"
    john_rows = [row for row in bowling_rows if clean_text(row.get("canonical_player_name") or row.get("player_name")) == "John Young" and clean_text(row.get("season")) == "Summer 1975/76"]
    john_total = sum(num(row.get("bowlingWickets")) or 0 for row in john_rows if not primary_bowling_row_is_filtered(row))
    john_status = f"rows={len(john_rows)} app_facing_wickets={john_total:g}" if john_rows else "not found"
    app_anomalies = []
    for line, row in enumerate(bowling_rows, start=2):
        if primary_bowling_row_is_filtered(row):
            app_anomalies.append(issue(PRIMARY_FILES["bowling"], line, row, "bowling", "app_facing_filter", row.get("bowlingWickets"), "app_facing_primary_bowling_excluded", "contradiction", "high", "Primary bowling row is excluded by current app-facing sanity filter.", "exclude_from_records", "no"))
    return {"dangerous_count": len(app_anomalies), "nathan_percy_status": nathan_status, "john_young_status": john_status, "anomalies": app_anomalies}


def primary_bowling_row_is_filtered(row: dict[str, str]) -> bool:
    wickets = num(row.get("bowlingWickets")) or 0
    runs = num(row.get("bowlingRuns")) or 0
    balls = num(row.get("bowlingBalls")) or 0
    bbi_wickets, _bbi_runs = parse_bbi(row.get("bowlingBestInnings"))
    if bbi_wickets is not None and bbi_wickets > wickets:
        return True
    if wickets <= 0:
        return False
    average = runs / wickets if wickets > 0 else None
    economy = runs * 6 / balls if balls > 0 else None
    return bool(
        (balls <= 0)
        or (average is not None and average <= 0)
        or (wickets >= 10 and runs < wickets)
        or (wickets >= 10 and average is not None and average < 1)
        or (balls >= 60 and economy is not None and economy < 0.5)
        or wickets > balls
    )


def build_summary(scanned: dict[str, int], anomalies: list[dict[str, object]], app_lineage: dict[str, object]) -> list[dict[str, object]]:
    severity = Counter(str(row["severity"]) for row in anomalies)
    issue_codes = Counter(str(row["issue_code"]) for row in anomalies)
    rows = [{"metric": f"rows_scanned:{key}", "value": value} for key, value in scanned.items()]
    rows.extend({"metric": f"severity:{key}", "value": value} for key, value in sorted(severity.items()))
    rows.extend({"metric": f"issue_code:{key}", "value": value} for key, value in issue_codes.most_common())
    rows.append({"metric": "app_facing_dangerous_records", "value": app_lineage["dangerous_count"]})
    rows.append({"metric": "nathan_percy_status", "value": app_lineage["nathan_percy_status"]})
    rows.append({"metric": "john_young_status", "value": app_lineage["john_young_status"]})
    return rows


def build_decision_review(anomalies: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str, str, str, str], list[dict[str, object]]] = defaultdict(list)
    for row in anomalies:
        key = (
            clean_text(row.get("source_file")),
            clean_text(row.get("source_row")),
            clean_text(row.get("player_name")),
            clean_text(row.get("season")),
            clean_text(row.get("team")),
            clean_text(row.get("grade")),
            clean_text(row.get("metric_group")),
        )
        grouped[key].append(row)

    decision_rows: list[dict[str, object]] = []
    for rows in grouped.values():
        first = rows[0]
        issue_codes = sorted({clean_text(row.get("issue_code")) for row in rows if clean_text(row.get("issue_code"))})
        reasons = sorted({clean_text(row.get("reason")) for row in rows if clean_text(row.get("reason"))})
        actions = sorted({clean_text(row.get("recommended_action")) for row in rows if clean_text(row.get("recommended_action"))})
        allowed_values = sorted({clean_text(row.get("app_facing_allowed")) for row in rows if clean_text(row.get("app_facing_allowed"))})
        allowed = combined_app_facing_allowed(allowed_values)
        suggested_decision, decision_priority = suggest_decision(issue_codes, actions)
        if invalid_player_name(first.get("player_name")):
            suggested_decision, decision_priority = "exclude_from_records", "P1"
        decision_rows.append(
            {
                "source_system": clean_text(first.get("source_system")) or "playcricket",
                "source_file": clean_text(first.get("source_file")),
                "source_row": clean_text(first.get("source_row")),
                "player_name": clean_text(first.get("player_name")),
                "canonical_player_id": clean_text(first.get("canonical_player_id")),
                "season": clean_text(first.get("season")),
                "team": clean_text(first.get("team")),
                "grade": clean_text(first.get("grade")),
                "metric_group": clean_text(first.get("metric_group")),
                "issue_codes": "; ".join(issue_codes),
                "issue_reasons": "; ".join(reasons),
                "highest_severity": highest_severity(rows),
                "recommended_actions": "; ".join(actions),
                "app_facing_allowed": allowed,
                "current_app_status": current_app_status(allowed),
                "suggested_decision": suggested_decision,
                "decision_priority": decision_priority,
                "notes": "",
            }
        )
    decision_rows.sort(key=decision_sort_key)
    return decision_rows


def build_decision_summary(decision_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    summary: list[dict[str, object]] = []
    for summary_group, field in [
        ("decision_priority", "decision_priority"),
        ("suggested_decision", "suggested_decision"),
        ("metric_group", "metric_group"),
        ("app_facing_allowed", "app_facing_allowed"),
    ]:
        counts = Counter(clean_text(row.get(field)) for row in decision_rows)
        summary.extend({"summary_group": summary_group, "value": key, "count": value} for key, value in sorted(counts.items()))

    issue_counts: Counter[str] = Counter()
    for row in decision_rows:
        for code in clean_text(row.get("issue_codes")).split("; "):
            if code:
                issue_counts[code] += 1
    summary.extend({"summary_group": "issue_code", "value": key, "count": value} for key, value in issue_counts.most_common())
    return summary


def suggest_decision(issue_codes: list[str], actions: list[str]) -> tuple[str, str]:
    code_set = set(issue_codes)
    action_set = set(actions)
    if "app_facing_primary_bowling_excluded" in code_set:
        return "already_excluded_review_source", "P1"
    if "exclude_from_records" in action_set or "invalid_player_name" in code_set:
        return "exclude_from_records", "P1"
    if issue_codes and all(is_duplicate_or_identity_issue(code) for code in issue_codes):
        return "manual_identity_review", "P2"
    if any(is_manual_stat_issue(code) for code in issue_codes):
        return "manual_stat_review", "P2"
    return "manual_stat_review", "P2"


def is_duplicate_or_identity_issue(code: str) -> bool:
    return code.startswith("duplicate_") or code.startswith("same_") or code.startswith("minor_spelling_variant")


def is_manual_stat_issue(code: str) -> bool:
    keywords = (
        "strike_rate",
        "average",
        "wickets_gt",
        "season_runs",
        "innings_gt",
        "high_score",
        "catches_gt",
        "stumpings_gt",
        "dismissals_gt",
        "economy_gt",
    )
    return any(keyword in code for keyword in keywords)


def highest_severity(rows: list[dict[str, object]]) -> str:
    order = {"high": 0, "medium": 1, "low": 2}
    return min((clean_text(row.get("severity")) for row in rows), key=lambda value: order.get(value, 99), default="")


def combined_app_facing_allowed(values: list[str]) -> str:
    if "no" in values:
        return "no"
    if "pending" in values:
        return "pending"
    if "yes" in values:
        return "yes"
    return "pending"


def current_app_status(app_facing_allowed: str) -> str:
    if app_facing_allowed == "no":
        return "excluded_from_app"
    if app_facing_allowed == "pending":
        return "not_confirmed_safe"
    return "allowed_or_audit_only"


def decision_sort_key(row: dict[str, object]) -> tuple[object, ...]:
    priority_order = {"P1": 0, "P2": 1}
    severity_order = {"high": 0, "medium": 1, "low": 2}
    return (
        priority_order.get(clean_text(row.get("decision_priority")), 99),
        severity_order.get(clean_text(row.get("highest_severity")), 99),
        clean_text(row.get("metric_group")),
        -season_sort_key(clean_text(row.get("season"))),
        clean_text(row.get("player_name")).casefold(),
    )


def season_sort_key(season: str) -> int:
    match = re.search(r"(18|19|20)\d{2}", season)
    return int(match.group()) if match else -1


def write_report(
    scanned: dict[str, int],
    anomalies: list[dict[str, object]],
    duplicate_rows: list[dict[str, object]],
    app_lineage: dict[str, object],
    rows_by_group: dict[str, list[dict[str, str]]],
    decision_rows: list[dict[str, object]],
    decision_summary_rows: list[dict[str, object]],
) -> None:
    path = ROOT / "docs" / "georges_river_playcricket_anomaly_audit_report.md"
    severity = Counter(str(row["severity"]) for row in anomalies)
    issue_codes = Counter(str(row["issue_code"]) for row in anomalies)
    high = [row for row in anomalies if row["severity"] == "high"][:30]
    medium = [row for row in anomalies if row["severity"] == "medium"][:30]
    bowling_over_70 = sorted(
        [row for row in rows_by_group["bowling"] if (num(row.get("bowlingWickets")) or 0) > 70],
        key=lambda row: -(num(row.get("bowlingWickets")) or 0),
    )
    batting_over_1000 = sorted(
        [row for row in rows_by_group["batting"] if (num(row.get("battingAggregate")) or 0) > 1000],
        key=lambda row: -(num(row.get("battingAggregate")) or 0),
    )
    lines = [
        "# Georges River PlayCricket/PlayHQ Anomaly Audit",
        "",
        "## Rows Scanned",
        "",
    ]
    lines.extend(f"- `{key}`: {value}" for key, value in scanned.items())
    lines.extend(
        [
            "",
            "## Severity Counts",
            "",
            f"- High: {severity.get('high', 0)}",
            f"- Medium: {severity.get('medium', 0)}",
            f"- Low: {severity.get('low', 0)}",
            "",
            "## Issue Code Counts",
            "",
        ]
    )
    lines.extend(f"- `{key}`: {value}" for key, value in issue_codes.most_common(30))
    lines.extend(["", "## Top 30 High-Severity Records", ""])
    lines.extend(markdown_table(high))
    lines.extend(["", "## Top 30 Medium-Severity Records", ""])
    lines.extend(markdown_table(medium))
    lines.extend(["", "## Bowling Seasons Over 70 Wickets", ""])
    lines.extend(simple_source_table(bowling_over_70, "bowlingWickets", 60))
    lines.extend(["", "## Batting Seasons Over 1000 Runs", ""])
    lines.extend(simple_source_table(batting_over_1000, "battingAggregate", 60))
    lines.extend(
        [
            "",
            "## Duplicate And Identity Risks",
            "",
            f"- Duplicate / identity audit rows: {len(duplicate_rows)}",
            "- These are report-only. No player merges were created or changed.",
            "",
            "## Decision Review Export",
            "",
            "- Source-row decision file: `clubs/georges-river-district/data/processed/validation/playcricket_anomaly_decision_review.csv`.",
            "- Summary file: `clubs/georges-river-district/data/processed/validation/playcricket_anomaly_decision_summary.csv`.",
            "- Use the decision review file for manual pre-preview review. It collapses repeated issue-level findings into one row per source file, source row, player, season, team, grade, and metric group.",
            "- `P1` = must resolve, approve, or exclude before client preview.",
            "- `P2` = manual review; preview can proceed only if the row is not app-facing dangerous.",
            f"- Decision review rows: {len(decision_rows)}.",
            f"- Current app-facing dangerous raw rows already excluded by the GRDCC app-facing sanity filter: {app_lineage['dangerous_count']}.",
            "",
            "### Decision Summary",
            "",
            *decision_summary_table(decision_summary_rows),
            "",
            "## Nathan Percy Root Cause And Status",
            "",
            "- The `Nathan Percy`, `Summer 1995/96`, `101 wickets` Hall of Fame card came from primary processed PlayCricket bowling data, not Excel.",
            "- Source row line `6163` in `all_seasons_bowling.csv` has `90` wickets, `2` runs conceded, `156` balls, BBI `1-45`, average `0.02`, and economy `0.08`.",
            "- Source row line `6219` has a plausible `11` wickets and `214` runs conceded.",
            f"- Current app-facing status: {app_lineage['nathan_percy_status']}.",
            "",
            "## John Young Current Best Bowling Season Trace",
            "",
            f"- Current trace status: {app_lineage['john_young_status']}.",
            "- John Young `Summer 1975/76` is the current app-facing Best Bowling Season after the Nathan Percy anomaly is filtered.",
            "",
            "## Recommended Manual Decisions Before Client Preview",
            "",
            "- Review all high-severity bowling contradictions before promoting any affected records.",
            "- Decide whether app-facing filtered PlayCricket rows should be corrected, permanently excluded, or escalated to source-provider review.",
            "- Review bowling seasons above 70 wickets and batting seasons above 1000 runs as plausible-but-high workloads.",
            "- Review duplicate/player identity rows before merging or renaming players.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def decision_summary_table(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["- None."]
    output = ["| Summary Group | Value | Count |", "|---|---|---:|"]
    for row in rows:
        output.append(f"| {clean_text(row.get('summary_group'))} | {clean_text(row.get('value'))} | {clean_text(row.get('count'))} |")
    return output


def markdown_table(rows: list[dict[str, object]]) -> list[str]:
    if not rows:
        return ["- None."]
    output = ["| Source | Row | Player | Season | Group | Metric | Value | Issue | Severity | Action |", "|---|---:|---|---|---|---|---:|---|---|---|"]
    for row in rows:
        output.append(
            "| "
            + " | ".join(
                clean_text(row.get(key)).replace("|", "/")
                for key in ["source_file", "source_row", "player_name", "season", "metric_group", "metric_name", "metric_value", "issue_code", "severity", "recommended_action"]
            )
            + " |"
        )
    return output


def simple_source_table(rows: list[dict[str, str]], metric: str, limit: int) -> list[str]:
    if not rows:
        return ["- None."]
    output = ["| Player | Season | Team | Grade | Metric | Value |", "|---|---|---|---|---|---:|"]
    for row in rows[:limit]:
        output.append(f"| {clean_text(row.get('player_name'))} | {clean_text(row.get('season'))} | {clean_text(row.get('team_name'))} | {clean_text(row.get('grade_name'))} | {metric} | {clean_text(row.get(metric))} |")
    return output


def ensure_decision_template() -> None:
    path = SOURCE_DIR / "playcricket_manual_anomaly_decisions.csv"
    if path.exists():
        return
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(path, [], DECISION_COLUMNS)


def issue(
    path: Path,
    line: object,
    row: dict[str, object],
    group: str,
    metric: str,
    value: object,
    code: str,
    issue_type: str,
    severity: str,
    reason: str,
    action: str,
    allowed: str,
) -> dict[str, object]:
    return {
        "source_system": "playcricket",
        "source_file": str(path.relative_to(ROOT)) if isinstance(path, Path) and path.is_absolute() else str(path),
        "source_row": line,
        "player_name": clean_text(row.get("player_name")),
        "canonical_player_id": clean_text(row.get("canonical_player_id")),
        "season": clean_text(row.get("season")),
        "team": clean_text(row.get("team_name")),
        "grade": clean_text(row.get("grade_name")),
        "metric_group": group,
        "metric_name": metric,
        "metric_value": value,
        "issue_code": code,
        "issue_type": issue_type,
        "severity": severity,
        "reason": reason,
        "recommended_action": action,
        "app_facing_allowed": allowed,
        "notes": "",
    }


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def parse_bbi(value: object) -> tuple[float | None, float | None]:
    text = clean_text(value)
    match = re.match(r"(\d+)[-/](\d+)", text)
    if not match:
        return None, None
    return float(match.group(1)), float(match.group(2))


def invalid_player_name(value: object) -> bool:
    text = clean_text(value)
    return not text or set(text) <= {"*"} or bool(re.fullmatch(r"\d+", text)) or not re.search(r"[A-Za-z]", text)


def num(value: object) -> float | None:
    text = clean_text(value).replace(",", "")
    if text == "":
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


if __name__ == "__main__":
    raise SystemExit(main())
