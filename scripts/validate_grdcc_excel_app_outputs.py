#!/usr/bin/env python3
"""Validate that GRDCC Excel supplemental app-facing outputs are clean-only."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPPLEMENTAL_DIR = ROOT / "clubs" / "georges-river-district" / "data" / "processed" / "supplemental"
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

    print("files checked:")
    for filename in APP_FACING_FILES:
        print(f"- {filename}")
    print("audit-only files not app-facing:")
    for filename in AUDIT_ONLY_FILES:
        print(f"- {filename}")
    print(f"rows checked: {rows_checked}")
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


if __name__ == "__main__":
    raise SystemExit(main())
