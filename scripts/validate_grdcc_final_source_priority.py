#!/usr/bin/env python3
"""Validate GRDCC's final Excel/PlayCricket source boundary and app-facing stats."""

from __future__ import annotations

import csv
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["CLUB_ID"] = "georges-river-district"

from src.data.playcricket_ingestion import (  # noqa: E402
    GRDCC_EXCEL_LAST_SEASON,
    GRDCC_PLAYCRICKET_FIRST_SEASON,
    read_processed_table,
)


OUTPUT_DIR = ROOT / "clubs" / "georges-river-district" / "data" / "processed" / "validation" / "final_source_priority"
VALIDATION_PATH = OUTPUT_DIR / "grdcc_final_source_priority_validation.csv"
ODD_STAT_PATH = OUTPUT_DIR / "grdcc_final_odd_stat_audit.csv"
SUMMARY_PATH = OUTPUT_DIR / "grdcc_final_source_priority_summary.csv"
CUTOFF_KEY = 1971 * 10 + 2


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    batting = read_processed_table("all_seasons_batting")
    bowling = read_processed_table("all_seasons_bowling")
    fielding = read_processed_table("all_seasons_fielding")

    validation = validate_source_split(batting, bowling)
    odd_stats = audit_odd_stats(batting, bowling)
    blockers = [row for row in odd_stats if row["preview_blocking"] == "yes"]
    failures = [row for row in validation if row["status"] == "fail"]
    summary = build_summary(batting, bowling, fielding, validation, odd_stats)

    write_csv(VALIDATION_PATH, validation)
    write_csv(ODD_STAT_PATH, odd_stats)
    write_csv(SUMMARY_PATH, summary)

    values = {row["metric"]: row["value"] for row in summary}
    print(f"Excel batting rows kept: {values['excel_batting_rows_kept']}")
    print(f"Excel bowling rows kept: {values['excel_bowling_rows_kept']}")
    print(f"PlayCricket batting rows kept: {values['playcricket_batting_rows_kept']}")
    print(f"PlayCricket bowling rows kept: {values['playcricket_bowling_rows_kept']}")
    print(f"PlayCricket fielding rows kept: {values['playcricket_fielding_rows_kept']}")
    print(f"Excel seasons: {values['excel_seasons']}")
    print(f"PlayCricket seasons: {values['playcricket_seasons']}")
    print(f"App-facing batting seasons: {values['total_app_facing_batting_seasons']}")
    print(f"App-facing bowling seasons: {values['total_app_facing_bowling_seasons']}")
    print(f"App-facing fielding seasons: {values['total_app_facing_fielding_seasons']}")
    print(f"Summer 1971/72 batting rows: {values['summer_1971_72_batting_rows']} (source: {values['summer_1971_72_batting_source']})")
    print(f"Summer 1971/72 bowling rows: {values['summer_1971_72_bowling_rows']} (source: {values['summer_1971_72_bowling_source']})")
    print(f"Summer 1972/73 batting rows: {values['summer_1972_73_batting_rows']} (source: {values['summer_1972_73_batting_source']})")
    print(f"Summer 1972/73 bowling rows: {values['summer_1972_73_bowling_rows']} (source: {values['summer_1972_73_bowling_source']})")
    print(f"Duplicate source conflicts: {values['duplicate_source_conflicts']}")
    print(f"Odd-stat findings: {len(odd_stats)}")
    print(f"Preview-blocking odd stats: {len(blockers)}")
    print(f"Source-priority validation failures: {len(failures)}")
    print("outputs:")
    for path in [VALIDATION_PATH, ODD_STAT_PATH, SUMMARY_PATH]:
        print(f"- {path.relative_to(ROOT)}")
    return 1 if failures or blockers else 0


def validate_source_split(batting: pd.DataFrame, bowling: pd.DataFrame) -> list[dict[str, object]]:
    checks = []
    for group, frame in (("batting", batting), ("bowling", bowling)):
        sources = source_series(frame)
        keys = frame.get("season", pd.Series("", index=frame.index)).map(season_sort_key)
        checks.append(check_row(f"no_modern_excel_{group}", int(((sources == "excel") & (keys > CUTOFF_KEY)).sum()) == 0, f"Excel {group} rows after {GRDCC_EXCEL_LAST_SEASON}", int(((sources == "excel") & (keys > CUTOFF_KEY)).sum())))
        checks.append(check_row(f"no_historical_playcricket_{group}", int(((sources == "playcricket") & (keys <= CUTOFF_KEY)).sum()) == 0, f"PlayCricket {group} rows through {GRDCC_EXCEL_LAST_SEASON}", int(((sources == "playcricket") & (keys <= CUTOFF_KEY)).sum())))
        conflicts = source_conflicts(frame)
        checks.append(check_row(f"no_duplicate_source_conflicts_{group}", not conflicts, f"Normalized player-season keys present in both sources for {group}", len(conflicts)))

    for season, expected in ((GRDCC_EXCEL_LAST_SEASON, "excel"), (GRDCC_PLAYCRICKET_FIRST_SEASON, "playcricket")):
        for group, frame in (("batting", batting), ("bowling", bowling)):
            rows = frame[frame.get("season", pd.Series("", index=frame.index)).astype(str) == season]
            actual = sorted(set(source_series(rows)))
            passed = not len(rows) or actual == [expected]
            checks.append(check_row(f"boundary_{season}_{group}", passed, f"{season} {group} resolves to {expected} when rows exist", f"rows={len(rows)} sources={','.join(actual) or 'none'}"))

    bowling_aggregates = aggregate_bowling(bowling)
    h_jolly_924 = [
        row for row in bowling_aggregates
        if normalize_name(row["player_name"]) == "h jolly"
        and row["season"] == "Summer 1944/45"
        and row["wickets"] == 924
    ]
    nathan_percy_101 = [
        row for row in bowling_aggregates
        if normalize_name(row["player_name"]) == "nathan percy"
        and row["season"] == "Summer 1995/96"
        and row["wickets"] >= 101
    ]
    checks.append(check_row("known_regression_h_jolly_924_wickets", not h_jolly_924, "H Jolly Summer 1944/45 is not exposed with 924 wickets", len(h_jolly_924)))
    checks.append(check_row("known_regression_nathan_percy_101_wickets", not nathan_percy_101, "Nathan Percy Summer 1995/96 does not aggregate to 101+ wickets", len(nathan_percy_101)))
    return checks


def audit_odd_stats(batting: pd.DataFrame, bowling: pd.DataFrame) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    for row in aggregate_batting(batting):
        player, season = row["player_name"], row["season"]
        add_if(findings, row["runs"] > 1500, row, "batting", "season_runs_over_1500", row["runs"], "medium", "Season runs exceed 1,500.", False)
        add_if(findings, row["innings"] >= 5 and row["average"] > 300, row, "batting", "batting_average_over_300", row["average"], "medium", "Batting average exceeds 300 with at least five innings.", False)
        add_if(findings, row["high_score"] > row["runs"], row, "batting", "high_score_over_runs", row["high_score"], "high", "High score exceeds total season runs.", True)
        add_if(findings, row["hundreds"] > row["innings"], row, "batting", "hundreds_over_innings", row["hundreds"], "high", "Hundreds exceed innings.", True)
        add_if(findings, row["fifties"] + row["hundreds"] > row["innings"], row, "batting", "milestones_over_innings", row["fifties"] + row["hundreds"], "high", "Fifties plus hundreds exceed innings.", True)
        add_if(findings, row["not_outs"] > row["innings"], row, "batting", "not_outs_over_innings", row["not_outs"], "high", "Not-outs exceed innings.", True)
        if invalid_player_name(player):
            findings.append(finding(row, "batting", "invalid_player_name", player, "high", "Player name is blank, masked, numeric-only, or has no alphabetic characters.", True))

    for row in aggregate_bowling(bowling):
        player = row["player_name"]
        add_if(findings, row["wickets"] > 100, row, "bowling", "wickets_over_100", row["wickets"], "high", "Season wickets exceed 100.", True)
        add_if(findings, row["wickets"] >= 80 and row["balls"] < row["wickets"] * 6, row, "bowling", "high_wickets_low_balls", row["balls"], "high", "At least 80 wickets recorded with unusually few balls.", True)
        add_if(findings, row["wickets"] >= 10 and row["average"] <= 1, row, "bowling", "bowling_average_at_or_below_1", row["average"], "high", "Bowling average is at or below 1 with at least 10 wickets.", True)
        add_if(findings, row["balls"] >= 60 and row["economy"] <= 0.5, row, "bowling", "economy_at_or_below_0_5", row["economy"], "high", "Economy is at or below 0.5 with at least 60 balls.", True)
        add_if(findings, row["wickets"] >= 10 and row["strike_rate"] <= 3, row, "bowling", "strike_rate_at_or_below_3", row["strike_rate"], "high", "Bowling strike rate is at or below 3 with at least 10 wickets.", True)
        add_if(findings, row["balls"] > 0 and row["wickets"] > row["balls"], row, "bowling", "wickets_over_balls", row["wickets"], "high", "Wickets exceed balls bowled.", True)
        add_if(findings, row["balls"] > 0 and row["maidens"] * 6 > row["balls"], row, "bowling", "maidens_over_overs", row["maidens"], "high", "Maidens exceed complete overs bowled.", True)
        if invalid_player_name(player):
            findings.append(finding(row, "bowling", "invalid_player_name", player, "high", "Player name is blank, masked, numeric-only, or has no alphabetic characters.", True))
    return findings


def aggregate_batting(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for (source, player, season), group in prepared_groups(frame):
        runs = total(group, "battingAggregate")
        innings = total(group, "battingInnings")
        not_outs = total(group, "battingNotOuts")
        dismissals = max(innings - not_outs, 0)
        rows.append({
            "source_system": source, "player_name": player, "season": season,
            "runs": runs, "innings": innings, "not_outs": not_outs,
            "average": runs / dismissals if dismissals else (runs if runs else 0),
            "high_score": maximum(group, "battingHighScore"),
            "fifties": total(group, "batting50s"), "hundreds": total(group, "batting100s"),
        })
    return rows


def aggregate_bowling(frame: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for (source, player, season), group in prepared_groups(frame):
        wickets = total(group, "bowlingWickets")
        runs = total(group, "bowlingRuns")
        balls = total(group, "bowlingBalls")
        rows.append({
            "source_system": source, "player_name": player, "season": season,
            "wickets": wickets, "runs_conceded": runs, "balls": balls,
            "maidens": total(group, "bowlingMaidens"),
            "average": runs / wickets if wickets else 0,
            "economy": runs * 6 / balls if balls else 0,
            "strike_rate": balls / wickets if wickets else 0,
        })
    return rows


def prepared_groups(frame: pd.DataFrame):
    output = frame.copy()
    output["_source"] = source_series(output)
    output["_player"] = player_series(output)
    output["_season"] = output.get("season", pd.Series("", index=output.index)).fillna("").astype(str).str.strip()
    return output.groupby(["_source", "_player", "_season"], dropna=False)


def build_summary(batting: pd.DataFrame, bowling: pd.DataFrame, fielding: pd.DataFrame, validation: list[dict[str, object]], odd_stats: list[dict[str, object]]) -> list[dict[str, object]]:
    bat_sources, bowl_sources = source_series(batting), source_series(bowling)
    duplicate_count = sum(int(row["observed_value"]) for row in validation if str(row["check_name"]).startswith("no_duplicate_source_conflicts"))
    metrics = [
        ("final_source_rule", f"Excel through {GRDCC_EXCEL_LAST_SEASON}; PlayCricket from {GRDCC_PLAYCRICKET_FIRST_SEASON}"),
        ("excel_batting_rows_kept", int((bat_sources == "excel").sum())),
        ("excel_bowling_rows_kept", int((bowl_sources == "excel").sum())),
        ("playcricket_batting_rows_kept", int((bat_sources == "playcricket").sum())),
        ("playcricket_bowling_rows_kept", int((bowl_sources == "playcricket").sum())),
        ("playcricket_fielding_rows_kept", len(fielding)),
        ("excel_seasons", season_count(pd.concat([batting[bat_sources == "excel"], bowling[bowl_sources == "excel"]], ignore_index=True))),
        ("playcricket_seasons", season_count(pd.concat([batting[bat_sources == "playcricket"], bowling[bowl_sources == "playcricket"]], ignore_index=True))),
        ("total_app_facing_batting_seasons", season_count(batting)),
        ("total_app_facing_bowling_seasons", season_count(bowling)),
        ("total_app_facing_fielding_seasons", season_count(fielding)),
        ("summer_1971_72_batting_rows", boundary_count(batting, GRDCC_EXCEL_LAST_SEASON)),
        ("summer_1971_72_batting_source", boundary_source(batting, GRDCC_EXCEL_LAST_SEASON)),
        ("summer_1971_72_bowling_rows", boundary_count(bowling, GRDCC_EXCEL_LAST_SEASON)),
        ("summer_1971_72_bowling_source", boundary_source(bowling, GRDCC_EXCEL_LAST_SEASON)),
        ("summer_1972_73_batting_rows", boundary_count(batting, GRDCC_PLAYCRICKET_FIRST_SEASON)),
        ("summer_1972_73_batting_source", boundary_source(batting, GRDCC_PLAYCRICKET_FIRST_SEASON)),
        ("summer_1972_73_bowling_rows", boundary_count(bowling, GRDCC_PLAYCRICKET_FIRST_SEASON)),
        ("summer_1972_73_bowling_source", boundary_source(bowling, GRDCC_PLAYCRICKET_FIRST_SEASON)),
        ("duplicate_source_conflicts", duplicate_count),
        ("odd_stat_findings", len(odd_stats)),
        ("preview_blocking_odd_stats", sum(row["preview_blocking"] == "yes" for row in odd_stats)),
        ("validation_failures", sum(row["status"] == "fail" for row in validation)),
    ]
    return [{"metric": metric, "value": value} for metric, value in metrics]


def source_conflicts(frame: pd.DataFrame) -> set[tuple[str, str]]:
    sources: dict[tuple[str, str], set[str]] = defaultdict(set)
    for source, player, season in zip(source_series(frame), player_series(frame), frame.get("season", pd.Series("", index=frame.index)).fillna("")):
        if player and season:
            sources[(normalize_name(player), str(season).strip())].add(source)
    return {key for key, values in sources.items() if len(values) > 1}


def source_series(frame: pd.DataFrame) -> pd.Series:
    if "source_system" in frame:
        return frame["source_system"].fillna("playcricket").replace("", "playcricket").astype(str).str.casefold()
    return pd.Series("playcricket", index=frame.index)


def player_series(frame: pd.DataFrame) -> pd.Series:
    for column in ["canonical_player_name", "player_name", "raw_player_name"]:
        if column in frame:
            values = frame[column].fillna("").astype(str).str.strip()
            if values.ne("").any():
                return values.where(values.ne(""), frame.get("player_name", ""))
    return pd.Series("", index=frame.index)


def season_sort_key(value: object) -> int:
    label = str(value or "")
    match = re.search(r"(19|20)\d{2}", label)
    if not match:
        return 999999
    year = int(match.group())
    return year * 10 + (1 if "winter" in label.casefold() else 2 if "summer" in label.casefold() else 0)


def invalid_player_name(value: object) -> bool:
    label = re.sub(r"\s+", " ", str(value or "")).strip()
    return not label or set(label) <= {"*"} or bool(re.fullmatch(r"\d+", label)) or not bool(re.search(r"[A-Za-z]", label))


def add_if(output: list[dict[str, object]], condition: bool, row: dict[str, object], group: str, code: str, value: object, severity: str, reason: str, blocking: bool) -> None:
    if condition:
        output.append(finding(row, group, code, value, severity, reason, blocking))


def finding(row: dict[str, object], group: str, code: str, value: object, severity: str, reason: str, blocking: bool) -> dict[str, object]:
    return {
        "source_system": row["source_system"], "player_name": row["player_name"], "season": row["season"],
        "metric_group": group, "issue_code": code, "metric_value": value, "severity": severity,
        "reason": reason, "preview_blocking": "yes" if blocking else "no",
        "recommended_action": "exclude_or_correct_before_preview" if blocking else "review_later",
    }


def check_row(name: str, passed: bool, description: str, observed: object) -> dict[str, object]:
    return {"check_name": name, "status": "pass" if passed else "fail", "description": description, "observed_value": observed}


def total(frame: pd.DataFrame, column: str) -> float:
    return float(pd.to_numeric(frame.get(column, pd.Series(dtype=float)), errors="coerce").fillna(0).sum())


def maximum(frame: pd.DataFrame, column: str) -> float:
    values = pd.to_numeric(frame.get(column, pd.Series(dtype=float)), errors="coerce").dropna()
    return float(values.max()) if not values.empty else 0


def season_count(frame: pd.DataFrame) -> int:
    return int(frame.get("season", pd.Series(dtype=str)).dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique())


def boundary_count(frame: pd.DataFrame, season: str) -> int:
    return int((frame.get("season", pd.Series("", index=frame.index)).astype(str) == season).sum())


def boundary_source(frame: pd.DataFrame, season: str) -> str:
    mask = frame.get("season", pd.Series("", index=frame.index)).astype(str) == season
    return ",".join(sorted(set(source_series(frame[mask])))) or "none"


def normalize_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    columns = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
