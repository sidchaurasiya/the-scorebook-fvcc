#!/usr/bin/env python3
"""Validate that GRDCC Excel supplemental app-facing outputs are clean-only."""

from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("CLUB_ID", "georges-river-district")

SUPPLEMENTAL_DIR = ROOT / "clubs" / "georges-river-district" / "data" / "processed" / "supplemental"
PROCESSED_DIR = ROOT / "clubs" / "georges-river-district" / "data" / "processed"
APP_FACING_FILES = [
    "excel_all_seasons_batting.csv",
    "excel_all_seasons_bowling.csv",
]
AUDIT_ONLY_FILES = [
    "excel_player_season_summary.csv",
    "excel_clean_rows.csv",
    "excel_review_rows.csv",
    "excel_rejected_rows.csv",
    "excel_outlier_audit.csv",
]


def main() -> int:
    failures: list[str] = []
    rows_checked = 0
    h_jolly_result = "not found"

    for filename in APP_FACING_FILES:
        path = SUPPLEMENTAL_DIR / filename
        if not path.exists():
            failures.append(f"Missing app-facing file: {path.relative_to(ROOT)}")
            continue
        rows = read_csv(path)
        rows_checked += len(rows)
        for row_number, row in enumerate(rows, start=2):
            player = clean_text(row.get("player_name"))
            season = clean_text(row.get("season"))
            if not player:
                failures.append(f"{filename}:{row_number} missing player_name")
            if is_masked_name(player):
                failures.append(f"{filename}:{row_number} masked player_name {player!r}")
            if is_numeric_only_name(player):
                failures.append(f"{filename}:{row_number} numeric-only player_name {player!r}")
            if clean_text(row.get("qa_status")).casefold() in {"review", "rejected"}:
                failures.append(f"{filename}:{row_number} contains non-clean qa_status {row.get('qa_status')!r}")
            if filename.endswith("bowling.csv"):
                wickets = number_or_none(row.get("bowlingWickets"))
                if wickets is not None and wickets > 100:
                    failures.append(f"{filename}:{row_number} bowlingWickets > 100 ({wickets:g})")
                if player == "H Jolly" and season == "Summer 1944/45":
                    h_jolly_result = f"wickets={row.get('bowlingWickets')} bowlingRuns={row.get('bowlingRuns')}"
                    if clean_text(row.get("bowlingWickets")) != "81" or clean_text(row.get("bowlingRuns")) != "924":
                        failures.append(f"{filename}:{row_number} H Jolly regression mismatch: {h_jolly_result}")
                if player == "H Jolly" and clean_text(row.get("bowlingWickets")) == "924":
                    failures.append(f"{filename}:{row_number} H Jolly has 924 wickets")
            if filename.endswith("batting.csv"):
                innings = number_or_none(row.get("battingInnings"))
                hundreds = number_or_none(row.get("batting100s"))
                fifties = number_or_none(row.get("batting50s"))
                high_score = number_or_none(row.get("battingHighScore"))
                runs = number_or_none(row.get("battingAggregate"))
                if innings is not None and hundreds is not None and hundreds > innings:
                    failures.append(f"{filename}:{row_number} batting100s > innings")
                if innings is not None and fifties is not None and fifties > innings:
                    failures.append(f"{filename}:{row_number} batting50s > innings")
                if runs is not None and high_score is not None and high_score > runs:
                    failures.append(f"{filename}:{row_number} high score > total runs")

    loaded_result = validate_loaded_app_bowling()
    failures.extend(loaded_result["failures"])
    lineage_result = validate_loader_source_boundaries()
    failures.extend(lineage_result["failures"])

    print("files checked:")
    for filename in APP_FACING_FILES:
        print(f"- {filename}")
    print("audit-only files not app-facing:")
    for filename in AUDIT_ONLY_FILES:
        print(f"- {filename}")
    print(f"rows checked: {rows_checked}")
    print(f"loaded app-facing bowling rows checked: {loaded_result['rows_checked']}")
    print(f"Nathan Percy app-facing regression result: {loaded_result['nathan_percy_result']}")
    print(f"loader source boundary result: {lineage_result['message']}")
    print(f"failures found: {len(failures)}")
    print(f"H Jolly regression result: {h_jolly_result}")
    print("app-facing clean-only confirmation: " + ("passed" if not failures else "failed"))

    if failures:
        print("failures:")
        for failure in failures[:100]:
            print(f"- {failure}")
        if len(failures) > 100:
            print(f"- ... {len(failures) - 100} more")
        return 1
    return 0


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def validate_loaded_app_bowling() -> dict[str, object]:
    failures: list[str] = []
    primary = read_csv(PROCESSED_DIR / "all_seasons_bowling.csv")
    supplemental = read_csv(SUPPLEMENTAL_DIR / "excel_all_seasons_bowling.csv")
    primary = [row for row in primary if not invalid_grdcc_primary_bowling_row(row)]
    primary_seasons = {clean_text(row.get("season")) for row in primary if clean_text(row.get("season"))}
    supplemental = [row for row in supplemental if clean_text(row.get("season")) not in primary_seasons]
    bowling = primary + supplemental
    if not bowling:
        return {"failures": ["Loaded app-facing all_seasons_bowling is empty"], "rows_checked": 0, "nathan_percy_result": "not checked"}
    rows_checked = len(bowling)
    for idx, row in enumerate(bowling):
        player = clean_text(row.get("canonical_player_name") or row.get("player_name"))
        season = clean_text(row.get("season"))
        wickets = number_or_none(row.get("bowlingWickets"))
        matches = number_or_none(row.get("matches"))
        average = number_or_none(row.get("bowlingAverage"))
        best_bowling = clean_text(row.get("bowlingBestInnings"))
        five_wi = number_or_none(row.get("bowling5WIs"))
        ten_wm = number_or_none(row.get("bowling10WMs"))
        bbi_wickets = best_bowling_wickets(best_bowling)
        if wickets is not None and wickets > 100:
            failures.append(f"loaded bowling row {idx + 2}: bowlingWickets > 100 ({wickets:g})")
        if matches is not None and matches <= 0 and wickets is not None and wickets > 0:
            failures.append(f"loaded bowling row {idx + 2}: matches=0 with wickets > 0")
        if average is not None and average <= 0 and wickets is not None and wickets > 0:
            failures.append(f"loaded bowling row {idx + 2}: bowlingAverage <= 0 with wickets > 0")
        if bbi_wickets is not None and wickets is not None and bbi_wickets > wickets:
            failures.append(f"loaded bowling row {idx + 2}: BBI wickets > season wickets")
        if five_wi is not None and matches is not None and five_wi > matches:
            failures.append(f"loaded bowling row {idx + 2}: 5WI > matches")
        if ten_wm is not None and matches is not None and ten_wm > matches:
            failures.append(f"loaded bowling row {idx + 2}: 10WM > matches")

    nathan = [
        row
        for row in bowling
        if clean_text(row.get("season")) == "Summer 1995/96"
        and clean_text(row.get("canonical_player_name") or row.get("player_name")) == "Nathan Percy"
    ]
    nathan_wickets = sum(number_or_none(row.get("bowlingWickets")) or 0 for row in nathan)
    nathan_result = f"loaded rows={len(nathan)}, wickets_sum={nathan_wickets:g}"
    if nathan_wickets >= 101:
        failures.append("Nathan Percy Summer 1995/96 still aggregates to 101+ wickets in loaded app-facing bowling")
    return {"failures": failures, "rows_checked": rows_checked, "nathan_percy_result": nathan_result}


def invalid_grdcc_primary_bowling_row(row: dict[str, str]) -> bool:
    wickets = number_or_none(row.get("bowlingWickets")) or 0
    runs = number_or_none(row.get("bowlingRuns")) or 0
    balls = number_or_none(row.get("bowlingBalls")) or 0
    bbi_wickets = best_bowling_wickets(row.get("bowlingBestInnings"))
    if bbi_wickets is not None and bbi_wickets > wickets:
        return True
    if wickets <= 0:
        return False
    average = runs / wickets if wickets > 0 else None
    economy = runs * 6 / balls if balls > 0 else None
    return bool(
        ((balls <= 0) and wickets > 0)
        or (average is not None and average <= 0)
        or ((wickets >= 10) and (runs < wickets))
        or ((wickets >= 10) and average is not None and average < 1)
        or ((balls >= 60) and economy is not None and economy < 0.5)
        or wickets > balls
    )


def validate_loader_source_boundaries() -> dict[str, object]:
    failures: list[str] = []
    loader_path = ROOT / "src" / "data" / "playcricket_ingestion.py"
    text = loader_path.read_text(encoding="utf-8")
    blocked = ["excel_player_season_summary.csv", "excel_review_rows.csv", "excel_rejected_rows.csv", "excel_outlier_audit.csv"]
    used = [name for name in blocked if name in text]
    if used:
        failures.append(f"App loader references audit/review files: {', '.join(used)}")
    return {"failures": failures, "message": "app loader uses clean batting/bowling supplemental files only" if not failures else "failed"}


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def is_masked_name(value: object) -> bool:
    text = clean_text(value)
    return bool(text) and set(text) <= {"*"}


def is_numeric_only_name(value: object) -> bool:
    return bool(re.fullmatch(r"\d+", clean_text(value)))


def number_or_none(value: object) -> float | None:
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def best_bowling_wickets(value: object) -> float | None:
    text = clean_text(value)
    match = re.match(r"(\d+)[-/]", text)
    return float(match.group(1)) if match else None


if __name__ == "__main__":
    raise SystemExit(main())
