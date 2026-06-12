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
ENRICHMENT_PATH = OUTPUT_DIR / "grdcc_premiership_wins_playcricket_enrichment.csv"


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
    post_2008 = merged[pd.to_numeric(merged["season_sort_key"], errors="coerce").ge(2008)].copy()
    playcricket_enriched = post_2008[post_2008["match_source"].eq("playcricket")]
    last_available = merged[merged["match_context"].eq("last_available_match")]
    report_only = merged[merged["match_context"].eq("annual_report_only")]
    fvcc_copy = merge_grdcc_premiership_honours(existing, "fvcc")

    report_lookup = {
        premiership_key(row["season"], row["grade_or_team"]): row
        for _, row in report.iterrows()
    }
    enrichment_rows = []
    for _, row in merged.iterrows():
        key = premiership_key(row["season"], row["grade_name"])
        report_row = report_lookup.get(key, {})
        found = str(row.get("match_source", "")).strip() == "playcricket"
        enrichment_rows.append(
            {
                "season": row.get("season", ""),
                "season_sort_key": row.get("season_sort_key", ""),
                "grade_or_team": row.get("grade_name", ""),
                "premiership_label": report_row.get("premiership_label", "Premiers"),
                "annual_report_page": report_row.get("annual_report_page", ""),
                "annual_report_source_text": report_row.get("source_text", ""),
                "already_in_app": "yes" if key in existing_keys else "no",
                "app_displayed": "yes",
                "playcricket_match_found": "yes" if found else "no",
                "playcricket_match_id": row.get("match_id", ""),
                "playcricket_match_date": row.get("match_date", ""),
                "playcricket_grade": row.get("grade_name", ""),
                "opponent": row.get("opponent_team_name", ""),
                "result_margin": row.get("result_margin_display", ""),
                "scorecard_url": row.get("scoreboard_url", ""),
                "match_context": row.get("match_context", "annual_report_only"),
                "match_confidence": row.get("match_confidence", ""),
                "captain": row.get("captain_name", ""),
                "captain_source": row.get("captain_source", ""),
                "captain_confidence": row.get("captain_confidence", ""),
                "captain_notes": row.get("captain_notes", ""),
                "enrichment_action": (
                    "verified_final_retained" if key in existing_keys
                    else "playcricket_context_added" if found
                    else "annual_report_only_retained"
                ),
                "notes": row.get("match_notes", ""),
            }
        )
    write_csv(
        ENRICHMENT_PATH,
        enrichment_rows,
        [
            "season", "season_sort_key", "grade_or_team", "premiership_label",
            "annual_report_page", "annual_report_source_text", "already_in_app",
            "app_displayed", "playcricket_match_found", "playcricket_match_id",
            "playcricket_match_date", "playcricket_grade", "opponent", "result_margin",
            "scorecard_url", "match_context", "match_confidence", "captain", "captain_source",
            "captain_confidence", "captain_notes", "enrichment_action", "notes",
        ],
    )

    layout_text = (ROOT / "src" / "ui" / "layout.py").read_text(encoding="utf-8")
    theme_text = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
    banned_ui_phrases = [
        "Last available PlayCricket match:",
        "Last match:",
        "View last match",
        "supporting match context only",
        "Source: GRDCC 2024/25 Annual Report",
        "Official club honours list",
    ]

    checks = [
        ("annual_report_extracted_wins", len(report), "22"),
        ("existing_app_wins", len(existing), "10"),
        ("newly_added_wins", int((pd.Series([row["added_to_app"] for row in extract_rows]) == "yes").sum()), "12"),
        ("final_app_wins", len(merged), "22"),
        ("duplicate_season_grade_combinations", duplicate_count, "0"),
        ("sorting_descending", sort_values == sorted(sort_values, reverse=True), "True"),
        ("latest_seven_count", len(latest_seven), "7"),
        ("high_confidence_report_wins_missing", len(high_confidence_missing), "0"),
        ("post_2008_wins_checked", len(post_2008), "16"),
        ("post_2008_playcricket_enriched", len(playcricket_enriched), "16"),
        ("last_available_match_fallbacks", len(last_available), "5"),
        ("annual_report_only_wins", len(report_only), "6"),
        ("playcricket_context_labels_valid", set(playcricket_enriched["match_context"]).issubset({"grand_final", "final", "last_available_match"}), "True"),
        ("single_scrollable_list", "premiership-older-scroll" not in layout_text and "overflow-y: auto" in theme_text, "True"),
        ("desktop_visible_row_target", "max-height: 691px" in theme_text, "True"),
        ("mobile_visible_row_target", "max-height: 1119px" in theme_text, "True"),
        ("banned_ui_phrases_absent", not any(phrase in layout_text for phrase in banned_ui_phrases), "True"),
        ("scorecard_link_wording", "View last match" not in layout_text and "View scorecard ↗" in layout_text, "True"),
        ("known_captains_have_source", int(merged["captain_name"].astype(str).str.strip().ne("").sum()) == int(merged["captain_source"].astype(str).str.strip().ne("").sum()), "True"),
        ("rows_without_captain_use_blank_subline", "Captain not recorded" not in layout_text and "Official club honours list" not in layout_text, "True"),
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
    print(f"Post-2008/09 wins checked: {len(post_2008)}")
    print(f"PlayCricket-enriched wins: {len(playcricket_enriched)}")
    print(f"Last-available-match fallbacks: {len(last_available)}")
    print(f"Annual Report-only wins: {len(report_only)}")
    print("Latest 7:")
    for _, row in latest_seven.iterrows():
        print(f"- {row['season']} — {row['grade_name']}")
    print(f"Validation failures: {len(failures)}")
    print(f"Extract: {EXTRACT_PATH}")
    print(f"Validation: {VALIDATION_PATH}")
    print(f"Enrichment: {ENRICHMENT_PATH}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
