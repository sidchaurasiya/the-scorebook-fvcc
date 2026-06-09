#!/usr/bin/env python3
"""Summarize GRDCC PlayCricket/PlayHQ and Historical Excel source coverage."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLUB_DIR = ROOT / "clubs" / "georges-river-district"
PROCESSED_DIR = CLUB_DIR / "data" / "processed"
SUPPLEMENTAL_DIR = PROCESSED_DIR / "supplemental"
VALIDATION_DIR = PROCESSED_DIR / "validation"
COVERAGE_DIR = VALIDATION_DIR / "source_coverage"
DOC_PATH = ROOT / "docs" / "georges_river_data_source_coverage_summary.md"

PLAYCRICKET_FILES = {
    "batting": PROCESSED_DIR / "all_seasons_batting.csv",
    "bowling": PROCESSED_DIR / "all_seasons_bowling.csv",
    "fielding": PROCESSED_DIR / "all_seasons_fielding.csv",
    "matches": PROCESSED_DIR / "all_seasons_matches.csv",
    "all_matches": PROCESSED_DIR / "all_matches.csv",
    "scorecards": PROCESSED_DIR / "all_scorecards.csv",
}

EXCEL_FILES = {
    "batting": SUPPLEMENTAL_DIR / "excel_all_seasons_batting.csv",
    "bowling": SUPPLEMENTAL_DIR / "excel_all_seasons_bowling.csv",
    "clean": SUPPLEMENTAL_DIR / "excel_clean_rows.csv",
    "review": SUPPLEMENTAL_DIR / "excel_review_rows.csv",
    "rejected": SUPPLEMENTAL_DIR / "excel_rejected_rows.csv",
    "ingestion_summary": SUPPLEMENTAL_DIR / "excel_ingestion_summary.csv",
    "sheet_audit": SUPPLEMENTAL_DIR / "excel_workbook_sheet_audit.csv",
}

METRICS = [
    ("batting", "matches", ["matches"], ["matches"], True, True, "Safe from clean Excel and sane PlayCricket aggregate rows."),
    ("batting", "innings", ["battingInnings"], ["battingInnings"], True, True, "Safe from clean player-season summaries."),
    ("batting", "not_outs", ["battingNotOuts"], ["battingNotOuts"], True, True, "Safe when innings/not-out columns are populated."),
    ("batting", "runs", ["battingAggregate"], ["battingAggregate"], True, True, "Safe from clean Excel and sane PlayCricket aggregate rows."),
    ("batting", "high_score", ["battingHighScore"], ["battingHighScore"], True, True, "Safe when high score <= season runs."),
    ("batting", "batting_average", ["battingAverage"], ["battingAverage"], True, True, "Safe when denominators are present and QA-clean."),
    ("batting", "batting_strike_rate", ["battingStrikeRate"], ["battingStrikeRate"], False, True, "Excel strike rate is aggregate-only and not BBB verified."),
    ("batting", "balls_faced", ["battingBallsFaced"], ["battingBallsFaced"], False, True, "Use for aggregate context only; BBB-only rates remain verified-ball-by-ball only."),
    ("batting", "30s", ["batting30s"], ["batting30s"], False, False, "Unavailable unless explicitly present."),
    ("batting", "50s", ["batting50s"], ["batting50s"], True, True, "Safe where clean and count <= innings."),
    ("batting", "100s", ["batting100s"], ["batting100s"], True, True, "Safe where clean and count <= innings."),
    ("batting", "ducks", ["batting0s"], ["batting0s"], True, True, "Safe where clean and count <= innings."),
    ("batting", "fours", ["battingFours"], ["battingFours"], False, True, "Excel boundary columns are sparse; use cautiously if present."),
    ("batting", "sixes", ["battingSixes"], ["battingSixes"], False, True, "Excel boundary columns are sparse; use cautiously if present."),
    ("bowling", "matches", ["matches"], ["matches"], True, True, "Safe from clean aggregate rows."),
    ("bowling", "overs", ["bowlingBalls"], ["bowlingBalls"], True, True, "Derived from balls where available."),
    ("bowling", "balls", ["bowlingBalls"], ["bowlingBalls"], True, True, "Safe from clean aggregate rows."),
    ("bowling", "maidens", ["bowlingMaidens"], ["bowlingMaidens"], True, True, "Safe when present and <= overs."),
    ("bowling", "bowling_runs_conceded", ["bowlingRuns"], ["bowlingRuns"], True, True, "Safe from clean Excel and sane PlayCricket rows."),
    ("bowling", "wickets", ["bowlingWickets"], ["bowlingWickets"], True, True, "Safe from clean Excel and sane PlayCricket rows."),
    ("bowling", "bowling_average", ["bowlingAverage"], ["bowlingAverage"], True, True, "Safe when reconciled against runs/wickets."),
    ("bowling", "economy", ["bowlingEconomyRate"], ["bowlingEconomyRate"], True, True, "Can be calculated from runs and balls/overs for clean Excel."),
    ("bowling", "bowling_strike_rate", ["bowlingStrikeRate"], ["bowlingStrikeRate"], True, True, "Can be calculated from balls and wickets for clean Excel."),
    ("bowling", "best_bowling", ["bowlingBestInnings"], ["bowlingBestInnings"], False, True, "Excel BBI treated unavailable unless explicitly present and verified."),
    ("bowling", "bbi_wickets", ["bowlingBestInnings"], ["bowlingBestInnings"], False, True, "Derived from BBI only when present and verified."),
    ("bowling", "bbi_runs", ["bowlingBestInnings"], ["bowlingBestInnings"], False, True, "Derived from BBI only when present and verified."),
    ("bowling", "3wi", ["bowling3WIs"], ["bowling3WIs"], False, False, "Unavailable unless explicitly present."),
    ("bowling", "5wi", ["bowling5WIs"], ["bowling5WIs"], False, True, "Excel 5WI unavailable unless explicitly present and verified."),
    ("bowling", "10wm", ["bowling10WMs"], ["bowling10WMs"], False, True, "Excel 10WM unavailable unless explicitly present and verified."),
    ("fielding", "catches", [], ["fieldingTotalCatches"], False, True, "PlayCricket supports aggregate fielding; Excel app-facing fielding not produced."),
    ("fielding", "stumpings", [], ["fieldingStumpings"], False, True, "PlayCricket supports aggregate fielding; Excel app-facing fielding not produced."),
    ("fielding", "run_outs", [], ["fieldingRunOuts"], False, True, "PlayCricket supports aggregate fielding; Excel app-facing fielding not produced."),
    ("fielding", "dismissals", [], ["fieldingTotalCatches", "fieldingStumpings", "fieldingRunOuts"], False, True, "Derived fielding total from PlayCricket components."),
]


def main() -> int:
    COVERAGE_DIR.mkdir(parents=True, exist_ok=True)

    pc = {key: read_csv(path) for key, path in PLAYCRICKET_FILES.items()}
    excel = {key: read_csv(path) for key, path in EXCEL_FILES.items()}
    qa = load_qa_counts()

    season_rows = build_season_rows(pc, excel, qa)
    metric_rows = build_metric_rows(pc, excel)
    player_rows = build_player_rows(pc, excel, qa)
    overlap_rows = build_overlap_rows(season_rows, player_rows)
    markdown = build_markdown_report(pc, excel, qa, season_rows, metric_rows, player_rows, overlap_rows)

    write_csv(COVERAGE_DIR / "grdcc_source_coverage_by_season.csv", season_rows)
    write_csv(COVERAGE_DIR / "grdcc_source_coverage_by_metric.csv", metric_rows)
    write_csv(COVERAGE_DIR / "grdcc_source_coverage_by_player.csv", player_rows)
    write_csv(COVERAGE_DIR / "grdcc_source_overlap_summary.csv", overlap_rows)
    report_path = COVERAGE_DIR / "grdcc_source_coverage_summary.md"
    report_path.write_text(markdown, encoding="utf-8")
    DOC_PATH.write_text(markdown, encoding="utf-8")

    pc_players = source_unique_players([pc["batting"], pc["bowling"], pc["fielding"]])
    excel_players = source_unique_players([excel["batting"], excel["bowling"]])
    overlap = scalar(overlap_rows, "both_source_seasons")
    print(f"PlayCricket batting rows: {len(pc['batting'])}")
    print(f"PlayCricket bowling rows: {len(pc['bowling'])}")
    print(f"PlayCricket fielding rows: {len(pc['fielding'])}")
    print(f"Excel clean batting rows: {len(excel['batting'])}")
    print(f"Excel clean bowling rows: {len(excel['bowling'])}")
    print(f"PlayCricket seasons: {len(source_seasons([pc['batting'], pc['bowling'], pc['fielding']]))}")
    print(f"Excel seasons: {len(source_seasons([excel['batting'], excel['bowling']]))}")
    print(f"PlayCricket players: {len(pc_players)}")
    print(f"Excel players: {len(excel_players)}")
    print(f"Overlap seasons: {overlap}")
    print("outputs:")
    for path in [
        COVERAGE_DIR / "grdcc_source_coverage_by_season.csv",
        COVERAGE_DIR / "grdcc_source_coverage_by_metric.csv",
        COVERAGE_DIR / "grdcc_source_coverage_by_player.csv",
        COVERAGE_DIR / "grdcc_source_overlap_summary.csv",
        COVERAGE_DIR / "grdcc_source_coverage_summary.md",
        DOC_PATH,
    ]:
        print(f"- {path.relative_to(ROOT)}")
    return 0


def build_season_rows(pc: dict[str, list[dict[str, str]]], excel: dict[str, list[dict[str, str]]], qa: dict[str, object]) -> list[dict[str, object]]:
    seasons = sorted(
        source_seasons([pc["batting"], pc["bowling"], pc["fielding"], pc["matches"], excel["batting"], excel["bowling"]]),
        key=season_sort_key,
    )
    rows = []
    anomaly_seasons = qa.get("playcricket_anomaly_seasons", set())
    for season in seasons:
        eb = filter_season(excel["batting"], season)
        ebo = filter_season(excel["bowling"], season)
        pb = filter_season(pc["batting"], season)
        pbo = filter_season(pc["bowling"], season)
        pf = filter_season(pc["fielding"], season)
        pm = filter_season(pc["matches"], season)
        has_excel = bool(eb or ebo)
        has_pc = bool(pb or pbo or pf or pm)
        if has_excel and has_pc:
            category = "both_sources"
            recommended = "manual_review" if season in anomaly_seasons or material_overlap(eb, ebo, pb, pbo) else "playcricket"
            notes = "Both sources have coverage; compare app-facing totals before trusting overlap seasons."
        elif has_excel:
            category = "excel_only"
            recommended = "excel"
            notes = "Historical Excel fills a gap where PlayCricket/PlayHQ app-facing rows are absent."
        elif has_pc:
            category = "playcricket_only"
            recommended = "playcricket"
            notes = "Primary PlayCricket/PlayHQ aggregate source only."
        else:
            category = "no_app_data"
            recommended = "verified_ball_by_ball_only"
            notes = "No aggregate app data found."
        rows.append(
            {
                "season": season,
                "season_sort_key": season_sort_key(season),
                "excel_batting_rows": len(eb),
                "excel_batting_players": len(unique_players(eb)),
                "excel_bowling_rows": len(ebo),
                "excel_bowling_players": len(unique_players(ebo)),
                "playcricket_batting_rows": len(pb),
                "playcricket_batting_players": len(unique_players(pb)),
                "playcricket_bowling_rows": len(pbo),
                "playcricket_bowling_players": len(unique_players(pbo)),
                "playcricket_fielding_rows": len(pf),
                "playcricket_fielding_players": len(unique_players(pf)),
                "match_rows_available": len(pm),
                "source_coverage_category": category,
                "recommended_primary_source": recommended,
                "notes": notes,
            }
        )
    return rows


def build_metric_rows(pc: dict[str, list[dict[str, str]]], excel: dict[str, list[dict[str, str]]]) -> list[dict[str, object]]:
    rows = []
    for group, metric, excel_cols, pc_cols, excel_safe, pc_safe, note in METRICS:
        excel_rows = excel.get(group, [])
        pc_rows = pc.get(group, [])
        excel_present = any(col in header_for(excel_rows) for col in excel_cols)
        pc_present = any(col in header_for(pc_rows) for col in pc_cols)
        rows.append(
            {
                "metric_group": group,
                "metric": metric,
                "available_in_excel": yes_no(excel_present),
                "available_in_playcricket": yes_no(pc_present),
                "excel_non_null_count": non_null_count(excel_rows, excel_cols),
                "playcricket_non_null_count": non_null_count(pc_rows, pc_cols),
                "excel_season_range": season_range_for_rows(rows_with_values(excel_rows, excel_cols)),
                "playcricket_season_range": season_range_for_rows(rows_with_values(pc_rows, pc_cols)),
                "safe_to_use_from_excel": yes_no(excel_safe and excel_present),
                "safe_to_use_from_playcricket": yes_no(pc_safe and pc_present),
                "notes": note,
            }
        )
    rows.append(
        {
            "metric_group": "ball_by_ball",
            "metric": "fastest_50_100_dot_balls_phase_metrics",
            "available_in_excel": "no",
            "available_in_playcricket": "no",
            "excel_non_null_count": 0,
            "playcricket_non_null_count": 0,
            "excel_season_range": "",
            "playcricket_season_range": "",
            "safe_to_use_from_excel": "no",
            "safe_to_use_from_playcricket": "no",
            "notes": "BBB-only metrics require verified ball-by-ball data, not spreadsheet or aggregate PlayCricket rows.",
        }
    )
    return rows


def build_player_rows(pc: dict[str, list[dict[str, str]]], excel: dict[str, list[dict[str, str]]], qa: dict[str, object]) -> list[dict[str, object]]:
    buckets: dict[str, dict[str, object]] = {}
    duplicate_names = qa.get("duplicate_player_names", set())

    def add(rows: list[dict[str, str]], source: str, group: str) -> None:
        for row in rows:
            name = player_name(row)
            if not name:
                continue
            key = f"name:{name.casefold()}"
            bucket = buckets.setdefault(
                key,
                {
                    "player_name": name,
                    "canonical_player_ids": set(),
                    "excel_batting_seasons": set(),
                    "excel_bowling_seasons": set(),
                    "playcricket_batting_seasons": set(),
                    "playcricket_bowling_seasons": set(),
                    "playcricket_fielding_seasons": set(),
                    "duplicate_or_identity_risk": "no",
                    "notes": "",
                },
            )
            bucket["player_name"] = bucket.get("player_name") or name
            canonical = clean(row.get("canonical_player_id"))
            if canonical:
                bucket["canonical_player_ids"].add(canonical)
            season = clean(row.get("season"))
            if season:
                bucket[f"{source}_{group}_seasons"].add(season)
            if name.casefold() in duplicate_names:
                bucket["duplicate_or_identity_risk"] = "yes"
                bucket["notes"] = "Flagged in duplicate/player identity anomaly review."

    add(excel["batting"], "excel", "batting")
    add(excel["bowling"], "excel", "bowling")
    add(pc["batting"], "playcricket", "batting")
    add(pc["bowling"], "playcricket", "bowling")
    add(pc["fielding"], "playcricket", "fielding")

    output = []
    for bucket in buckets.values():
        excel_seasons = set(bucket["excel_batting_seasons"]) | set(bucket["excel_bowling_seasons"])
        pc_seasons = set(bucket["playcricket_batting_seasons"]) | set(bucket["playcricket_bowling_seasons"]) | set(bucket["playcricket_fielding_seasons"])
        row = {
            "player_name": bucket["player_name"],
            "canonical_player_id": " | ".join(sorted(bucket["canonical_player_ids"])),
            "excel_batting_seasons": join_seasons(bucket["excel_batting_seasons"]),
            "excel_bowling_seasons": join_seasons(bucket["excel_bowling_seasons"]),
            "playcricket_batting_seasons": join_seasons(bucket["playcricket_batting_seasons"]),
            "playcricket_bowling_seasons": join_seasons(bucket["playcricket_bowling_seasons"]),
            "playcricket_fielding_seasons": join_seasons(bucket["playcricket_fielding_seasons"]),
            "first_excel_season": first_season(excel_seasons),
            "latest_excel_season": latest_season(excel_seasons),
            "first_playcricket_season": first_season(pc_seasons),
            "latest_playcricket_season": latest_season(pc_seasons),
            "appears_in_excel_only": yes_no(bool(excel_seasons and not pc_seasons)),
            "appears_in_playcricket_only": yes_no(bool(pc_seasons and not excel_seasons)),
            "appears_in_both_sources": yes_no(bool(excel_seasons and pc_seasons)),
            "duplicate_or_identity_risk": bucket["duplicate_or_identity_risk"],
            "notes": bucket["notes"],
        }
        output.append(row)
    output.sort(key=lambda row: clean(row["player_name"]).casefold())
    return output


def build_overlap_rows(season_rows: list[dict[str, object]], player_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counts = Counter(row["source_coverage_category"] for row in season_rows)
    overlap_batting = sum(1 for row in season_rows if int(row["excel_batting_rows"]) and int(row["playcricket_batting_rows"]))
    overlap_bowling = sum(1 for row in season_rows if int(row["excel_bowling_rows"]) and int(row["playcricket_bowling_rows"]))
    values = {
        "total_seasons": len(season_rows),
        "excel_only_seasons": counts["excel_only"],
        "playcricket_only_seasons": counts["playcricket_only"],
        "both_source_seasons": counts["both_sources"],
        "excel_batting_only_seasons": sum(1 for row in season_rows if int(row["excel_batting_rows"]) and not int(row["playcricket_batting_rows"])),
        "excel_bowling_only_seasons": sum(1 for row in season_rows if int(row["excel_bowling_rows"]) and not int(row["playcricket_bowling_rows"])),
        "playcricket_batting_only_seasons": sum(1 for row in season_rows if int(row["playcricket_batting_rows"]) and not int(row["excel_batting_rows"])),
        "playcricket_bowling_only_seasons": sum(1 for row in season_rows if int(row["playcricket_bowling_rows"]) and not int(row["excel_bowling_rows"])),
        "seasons_with_batting_overlap": overlap_batting,
        "seasons_with_bowling_overlap": overlap_bowling,
        "seasons_with_playcricket_fielding_only": sum(1 for row in season_rows if int(row["playcricket_fielding_rows"]) and not int(row["excel_batting_rows"]) and not int(row["excel_bowling_rows"])),
        "seasons_needing_manual_source_priority_review": sum(1 for row in season_rows if row["recommended_primary_source"] == "manual_review"),
        "players_excel_only": sum(1 for row in player_rows if row["appears_in_excel_only"] == "yes"),
        "players_playcricket_only": sum(1 for row in player_rows if row["appears_in_playcricket_only"] == "yes"),
        "players_in_both_sources": sum(1 for row in player_rows if row["appears_in_both_sources"] == "yes"),
    }
    return [{"metric": key, "value": value} for key, value in values.items()]


def build_markdown_report(
    pc: dict[str, list[dict[str, str]]],
    excel: dict[str, list[dict[str, str]]],
    qa: dict[str, object],
    season_rows: list[dict[str, object]],
    metric_rows: list[dict[str, object]],
    player_rows: list[dict[str, object]],
    overlap_rows: list[dict[str, object]],
) -> str:
    pc_summary = source_summary("PlayCricket / PlayHQ", pc["batting"], pc["bowling"], pc["fielding"], pc["matches"], qa)
    excel_summary = excel_source_summary(excel, qa)
    overlap = {row["metric"]: row["value"] for row in overlap_rows}
    both_seasons = [row["season"] for row in season_rows if row["source_coverage_category"] == "both_sources"]
    excel_only = [row["season"] for row in season_rows if row["source_coverage_category"] == "excel_only"]
    pc_only = [row["season"] for row in season_rows if row["source_coverage_category"] == "playcricket_only"]
    metric_safe_excel = [row["metric"] for row in metric_rows if row["safe_to_use_from_excel"] == "yes"]
    metric_safe_pc = [row["metric"] for row in metric_rows if row["safe_to_use_from_playcricket"] == "yes"]

    lines = [
        "# Georges River Data Source Coverage Summary",
        "",
        "## Executive Summary",
        "",
        "- PlayCricket / PlayHQ provides the primary modern aggregate source for batting, bowling and fielding, but it includes known anomaly rows that must remain filtered or manually reviewed before driving headline records.",
        "- Historical Excel provides supplemental historical batting and bowling coverage, mostly filling older seasons and specific historical gaps not covered by PlayCricket / PlayHQ.",
        "- Overlap seasons exist and should be treated as manual source-priority review zones rather than automatically merged without QA.",
        "- Excel-derived data is suitable for clean aggregate batting and bowling summaries, but it is never suitable for ball-by-ball-only metrics.",
        "",
        "## Source 1: PlayCricket / PlayHQ",
        "",
        *summary_lines(pc_summary),
        f"- Known anomaly rows: {qa.get('playcricket_anomaly_rows', 0)}",
        f"- High severity anomaly findings: {qa.get('playcricket_high_anomalies', 0)}",
        f"- Medium severity anomaly findings: {qa.get('playcricket_medium_anomalies', 0)}",
        f"- App-facing dangerous raw rows already excluded: {qa.get('playcricket_app_excluded_rows', 0)}",
        "",
        "## Source 2: Historical Excel Spreadsheet",
        "",
        *summary_lines(excel_summary),
        f"- Clean rows: {len(excel['clean'])}",
        f"- Review rows: {len(excel['review'])}",
        f"- Rejected rows: {len(excel['rejected'])}",
        f"- Excel decision review rows: {qa.get('excel_decision_review_rows', 0)}",
        "",
        "## Season Overlap",
        "",
        "| Category | Count | Example Seasons |",
        "|---|---:|---|",
        f"| Excel only seasons | {overlap.get('excel_only_seasons', 0)} | {example_list(excel_only)} |",
        f"| PlayCricket only seasons | {overlap.get('playcricket_only_seasons', 0)} | {example_list(pc_only)} |",
        f"| Both-source seasons | {overlap.get('both_source_seasons', 0)} | {example_list(both_seasons)} |",
        f"| Seasons with batting overlap | {overlap.get('seasons_with_batting_overlap', 0)} | |",
        f"| Seasons with bowling overlap | {overlap.get('seasons_with_bowling_overlap', 0)} | |",
        f"| Seasons with PlayCricket fielding only | {overlap.get('seasons_with_playcricket_fielding_only', 0)} | |",
        "",
        "## Metric Coverage",
        "",
        f"- Safe from clean Excel: {', '.join(metric_safe_excel[:24])}.",
        f"- Safe from sane PlayCricket / PlayHQ aggregates: {', '.join(metric_safe_pc[:28])}.",
        "- Ball-by-ball-only metrics such as fastest 50/100, dot-ball rates, balls per boundary and phase metrics must remain verified-ball-by-ball-only.",
        "- Excel BBI, 3WI, 5WI and 10WM should remain unavailable unless explicitly present and manually verified.",
        "",
        "## Source Priority Rules",
        "",
        "1. PlayCricket / PlayHQ is preferred for modern/current aggregate records where rows are sane.",
        "2. Excel is preferred for historical seasons missing from PlayCricket / PlayHQ.",
        "3. In overlap seasons, use manual source priority review if both sources materially differ.",
        "4. Excel is never used for BBB-only metrics.",
        "5. Any high-severity anomaly is excluded unless manually approved.",
        "",
        "## Known Risks / Manual Review",
        "",
        f"- PlayCricket / PlayHQ anomaly findings remain in the review exports: {qa.get('playcricket_anomaly_rows', 0)} issue rows.",
        f"- Excel review/rejected rows: {len(excel['review'])} review, {len(excel['rejected'])} rejected.",
        f"- Duplicate/player identity risks: {qa.get('duplicate_identity_rows', 0)} rows.",
        f"- Seasons with overlapping source coverage needing source-priority review: {overlap.get('seasons_needing_manual_source_priority_review', 0)}.",
        "- Metrics with incomplete or unavailable coverage should remain N/A rather than inferred.",
        "",
        "## Recommended Next Step",
        "",
        "- Use this report and the season coverage CSV to decide source priority by season.",
        "- Inspect overlap seasons first, especially seasons with both batting and bowling coverage.",
        "- Do not block private preview on P2 duplicate/identity items unless they affect headline records.",
        "",
        "## Output Files",
        "",
        "- `clubs/georges-river-district/data/processed/validation/source_coverage/grdcc_source_coverage_by_season.csv`",
        "- `clubs/georges-river-district/data/processed/validation/source_coverage/grdcc_source_coverage_by_metric.csv`",
        "- `clubs/georges-river-district/data/processed/validation/source_coverage/grdcc_source_coverage_by_player.csv`",
        "- `clubs/georges-river-district/data/processed/validation/source_coverage/grdcc_source_overlap_summary.csv`",
    ]
    return "\n".join(lines) + "\n"


def source_summary(name: str, batting: list[dict[str, str]], bowling: list[dict[str, str]], fielding: list[dict[str, str]], matches: list[dict[str, str]], qa: dict[str, object]) -> dict[str, object]:
    return {
        "source": name,
        "batting_rows": len(batting),
        "bowling_rows": len(bowling),
        "fielding_rows": len(fielding),
        "match_rows": len(matches),
        "batting_seasons": len(source_seasons([batting])),
        "bowling_seasons": len(source_seasons([bowling])),
        "fielding_seasons": len(source_seasons([fielding])),
        "batting_season_range": season_range_for_rows(batting),
        "bowling_season_range": season_range_for_rows(bowling),
        "fielding_season_range": season_range_for_rows(fielding),
        "unique_batting_players": len(unique_players(batting)),
        "unique_bowling_players": len(unique_players(bowling)),
        "unique_fielding_players": len(unique_players(fielding)),
        "unique_players_overall": len(source_unique_players([batting, bowling, fielding])),
        "teams_grades_detected": len(teams_grades([batting, bowling, fielding])),
        "key_columns_present": ", ".join(sorted(header_for(batting + bowling + fielding))[:40]),
        "key_columns_missing": missing_key_columns(header_for(batting + bowling + fielding), "playcricket"),
    }


def excel_source_summary(excel: dict[str, list[dict[str, str]]], qa: dict[str, object]) -> dict[str, object]:
    batting = excel["batting"]
    bowling = excel["bowling"]
    return {
        "source": "Historical Excel Spreadsheet",
        "clean_batting_rows": len(batting),
        "clean_bowling_rows": len(bowling),
        "review_rows": len(excel["review"]),
        "rejected_rows": len(excel["rejected"]),
        "batting_seasons": len(source_seasons([batting])),
        "bowling_seasons": len(source_seasons([bowling])),
        "batting_season_range": season_range_for_rows(batting),
        "bowling_season_range": season_range_for_rows(bowling),
        "unique_batting_players": len(unique_players(batting)),
        "unique_bowling_players": len(unique_players(bowling)),
        "unique_players_overall": len(source_unique_players([batting, bowling])),
        "teams_grades_detected": len(teams_grades([batting, bowling])),
        "key_columns_present": ", ".join(sorted(header_for(batting + bowling))[:40]),
        "key_columns_missing": missing_key_columns(header_for(batting + bowling), "excel"),
    }


def load_qa_counts() -> dict[str, object]:
    qa: dict[str, object] = {
        "playcricket_anomaly_rows": 0,
        "playcricket_high_anomalies": 0,
        "playcricket_medium_anomalies": 0,
        "playcricket_app_excluded_rows": 0,
        "playcricket_anomaly_seasons": set(),
        "duplicate_player_names": set(),
        "duplicate_identity_rows": 0,
        "excel_decision_review_rows": 0,
    }
    anomaly_rows = read_csv(VALIDATION_DIR / "playcricket_anomaly_audit.csv")
    qa["playcricket_anomaly_rows"] = len(anomaly_rows)
    qa["playcricket_high_anomalies"] = sum(1 for row in anomaly_rows if row.get("severity") == "high")
    qa["playcricket_medium_anomalies"] = sum(1 for row in anomaly_rows if row.get("severity") == "medium")
    qa["playcricket_anomaly_seasons"] = {clean(row.get("season")) for row in anomaly_rows if clean(row.get("season"))}
    qa["playcricket_app_excluded_rows"] = sum(1 for row in anomaly_rows if row.get("issue_code") == "app_facing_primary_bowling_excluded")
    duplicate_rows = read_csv(VALIDATION_DIR / "playcricket_duplicate_player_season_audit.csv")
    qa["duplicate_identity_rows"] = len(duplicate_rows)
    qa["duplicate_player_names"] = {clean(row.get("player_name")).casefold() for row in duplicate_rows if clean(row.get("player_name"))}
    excel_decision = read_csv(VALIDATION_DIR / "review_exports" / "excel_all_anomalies_decision_review_with_data.csv")
    qa["excel_decision_review_rows"] = len(excel_decision)
    return qa


def summary_lines(summary: dict[str, object]) -> list[str]:
    return [f"- {key.replace('_', ' ').title()}: {value}" for key, value in summary.items() if key != "source"]


def missing_key_columns(headers: set[str], source: str) -> str:
    required = {
        "playcricket": {"player_name", "season", "team_name", "grade_name", "matches", "battingAggregate", "bowlingWickets", "fieldingTotalCatches"},
        "excel": {"player_name", "season", "team_name", "grade_name", "battingAggregate", "bowlingWickets", "source_sheet", "source_row"},
    }[source]
    missing = sorted(required - headers)
    return ", ".join(missing) if missing else "none"


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
    columns: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                columns.append(key)
                seen.add(key)
    return columns


def filter_season(rows: list[dict[str, str]], season: str) -> list[dict[str, str]]:
    return [row for row in rows if clean(row.get("season")) == season]


def material_overlap(eb: list[dict[str, str]], ebo: list[dict[str, str]], pb: list[dict[str, str]], pbo: list[dict[str, str]]) -> bool:
    return bool((eb and pb) or (ebo and pbo))


def source_seasons(groups: list[list[dict[str, str]]]) -> set[str]:
    return {clean(row.get("season")) for rows in groups for row in rows if clean(row.get("season"))}


def source_unique_players(groups: list[list[dict[str, str]]]) -> set[str]:
    return {player_key(row) for rows in groups for row in rows if player_key(row)}


def unique_players(rows: list[dict[str, str]]) -> set[str]:
    return {player_key(row) for row in rows if player_key(row)}


def player_key(row: dict[str, str]) -> str:
    return f"name:{player_name(row).casefold()}" if player_name(row) else ""


def player_name(row: dict[str, str]) -> str:
    return clean(row.get("canonical_player_name") or row.get("player_name") or row.get("raw_player_name"))


def teams_grades(groups: list[list[dict[str, str]]]) -> set[str]:
    return {f"{clean(row.get('team_name'))}|{clean(row.get('grade_name'))}" for rows in groups for row in rows if clean(row.get("team_name")) or clean(row.get("grade_name"))}


def header_for(rows: list[dict[str, str]]) -> set[str]:
    headers: set[str] = set()
    for row in rows:
        headers.update(row.keys())
    return headers


def non_null_count(rows: list[dict[str, str]], columns: list[str]) -> int:
    if not columns:
        return 0
    return sum(1 for row in rows if any(clean(row.get(col)) not in {"", "nan", "None"} for col in columns))


def rows_with_values(rows: list[dict[str, str]], columns: list[str]) -> list[dict[str, str]]:
    if not columns:
        return []
    return [row for row in rows if any(clean(row.get(col)) not in {"", "nan", "None"} for col in columns)]


def season_range_for_rows(rows: list[dict[str, str]]) -> str:
    seasons = source_seasons([rows])
    if not seasons:
        return ""
    return f"{first_season(seasons)} to {latest_season(seasons)}"


def first_season(seasons: set[str]) -> str:
    return min(seasons, key=season_sort_key) if seasons else ""


def latest_season(seasons: set[str]) -> str:
    return max(seasons, key=season_sort_key) if seasons else ""


def join_seasons(seasons: set[str]) -> str:
    return ", ".join(sorted(seasons, key=season_sort_key))


def season_sort_key(season: object) -> int:
    text = clean(season)
    match = re.search(r"(18|19|20)\d{2}", text)
    if not match:
        return -1
    return int(match.group())


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def example_list(values: list[str], limit: int = 8) -> str:
    if not values:
        return "None"
    ordered = sorted(values, key=season_sort_key)
    suffix = f", +{len(ordered) - limit} more" if len(ordered) > limit else ""
    return ", ".join(ordered[:limit]) + suffix


def scalar(rows: list[dict[str, object]], metric: str) -> object:
    for row in rows:
        if row.get("metric") == metric:
            return row.get("value")
    return 0


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


if __name__ == "__main__":
    raise SystemExit(main())
