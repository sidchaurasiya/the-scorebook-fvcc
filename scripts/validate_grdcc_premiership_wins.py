#!/usr/bin/env python3
"""Validate GRDCC Annual Report premiership honours and app display data."""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
try:
    import pandas as pd
except ModuleNotFoundError:
    app_python = ROOT / ".venv-app" / "bin" / "python"
    if app_python.exists() and Path(sys.executable).resolve() != app_python.resolve():
        os.execv(str(app_python), [str(app_python), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.premiership_honours import (  # noqa: E402
    load_annual_report_premierships,
    merge_grdcc_premiership_honours,
    normalize_premiership_grade,
    premiership_key,
)


CLUB_ID = "georges-river-district"
HOF_WINS = ROOT / "clubs" / CLUB_ID / "data" / "processed" / "hall_of_fame" / "premiership_wins.csv"
OUTPUT_DIR = ROOT / "clubs" / CLUB_ID / "data" / "processed" / "validation" / "annual_report_2024_25"
EXTRACT_PATH = OUTPUT_DIR / "grdcc_annual_report_premiership_wins_extract.csv"
VALIDATION_PATH = OUTPUT_DIR / "grdcc_premiership_wins_validation.csv"


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    report = load_annual_report_premierships(CLUB_ID)
    existing = pd.read_csv(HOF_WINS, dtype=str).fillna("")
    existing_keys = {premiership_key(row["season"], row["grade_name"]) for _, row in existing.iterrows()}
    extract_rows = []
    for _, row in report.iterrows():
        key = premiership_key(row["season"], row["grade_or_team"])
        already = key in existing_keys
        extract_rows.append(
            {
                "report_year": row["report_year"],
                "annual_report_page": row["annual_report_page"],
                "section_heading": row["section_heading"],
                "season": row["season"],
                "season_sort_key": row["season_sort_key"],
                "grade_or_team": row["grade_or_team"],
                "premiership_label": row["premiership_label"],
                "source_text": row["source_text"],
                "extraction_confidence": row["extraction_confidence"],
                "already_in_app": "yes" if already else "no",
                "added_to_app": "no" if already else "yes",
                "notes": "Existing scorecard-backed win retained." if already else "Added from official Annual Report honours table.",
            }
        )
    write_csv(
        EXTRACT_PATH,
        extract_rows,
        [
            "report_year", "annual_report_page", "section_heading", "season", "season_sort_key",
            "grade_or_team", "premiership_label", "source_text", "extraction_confidence",
            "already_in_app", "added_to_app", "notes",
        ],
    )

    merged = merge_grdcc_premiership_honours(existing, CLUB_ID)
    merged_keys = [premiership_key(row["season"], row["grade_name"]) for _, row in merged.iterrows()]
    report_keys = {premiership_key(row["season"], row["grade_or_team"]) for _, row in report.iterrows()}
    duplicate_count = len(merged_keys) - len(set(merged_keys))
    sort_values = pd.to_numeric(merged["season_sort_key"], errors="coerce").fillna(-1).tolist()
    latest_seven = merged.head(7)
    high_confidence_missing = sorted(report_keys - set(merged_keys))
    annual_only = merged[merged.get("source_system", pd.Series("", index=merged.index)).eq("annual_report")]
    fvcc_copy = merge_grdcc_premiership_honours(existing, "fvcc")

    checks = [
        ("annual_report_extracted_wins", len(report), "22"),
        ("existing_app_wins", len(existing), "10"),
        ("newly_added_wins", int((pd.Series([row["added_to_app"] for row in extract_rows]) == "yes").sum()), "12"),
        ("final_app_wins", len(merged), "22"),
        ("duplicate_season_grade_combinations", duplicate_count, "0"),
        ("sorting_descending", sort_values == sorted(sort_values, reverse=True), "True"),
        ("latest_seven_count", len(latest_seven), "7"),
        ("high_confidence_report_wins_missing", len(high_confidence_missing), "0"),
        ("annual_report_only_scorecard_links", int(annual_only["scoreboard_url"].astype(str).str.strip().ne("").sum()), "0"),
        ("annual_report_only_match_ids", int(annual_only["match_id"].astype(str).str.strip().ne("").sum()), "0"),
        ("fvcc_rows_unchanged", len(fvcc_copy) == len(existing), "True"),
    ]
    validation_rows = [
        {
            "check": name,
            "actual": actual,
            "expected": expected,
            "status": "pass" if str(actual) == expected else "fail",
            "details": (
                "; ".join(f"{row['season']} — {normalize_premiership_grade(row['grade_name'])}" for _, row in latest_seven.iterrows())
                if name == "latest_seven_count" else ""
            ),
        }
        for name, actual, expected in checks
    ]
    write_csv(VALIDATION_PATH, validation_rows, ["check", "actual", "expected", "status", "details"])
    failures = [row for row in validation_rows if row["status"] == "fail"]

    print(f"Annual Report wins extracted: {len(report)}")
    print(f"Already present: {len(existing)}")
    print(f"Newly added: {sum(row['added_to_app'] == 'yes' for row in extract_rows)}")
    print(f"Final app wins: {len(merged)}")
    print(f"Duplicate season/grade combinations: {duplicate_count}")
    print("Latest 7:")
    for _, row in latest_seven.iterrows():
        print(f"- {row['season']} — {row['grade_name']}")
    print(f"Validation failures: {len(failures)}")
    print(f"Extract: {EXTRACT_PATH}")
    print(f"Validation: {VALIDATION_PATH}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
