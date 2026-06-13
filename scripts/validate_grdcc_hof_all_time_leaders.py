#!/usr/bin/env python3
"""Build and validate GRDCC Annual Report all-time leader presentation rows."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.featured_record_overrides import apply_featured_record_overrides, normalize_featured_player_name  # noqa: E402


BASE = ROOT / "clubs/georges-river-district/data/processed/validation/annual_report_2024_25"
COMPARISON_PATH = BASE / "grdcc_annual_report_vs_sources_validation.csv"
EXTRACT_PATH = BASE / "grdcc_annual_report_record_extracts.csv"
OUTPUT_PATH = BASE / "grdcc_annual_report_all_time_leaders_for_app.csv"
VALIDATION_PATH = ROOT / "clubs/georges-river-district/data/processed/validation/hof/grdcc_hof_all_time_leaders_validation.csv"
LAYOUT_PATH = ROOT / "src/ui/layout.py"
SECTIONS = {"most_runs": ("runs", "Runs"), "most_wickets": ("wickets", "Wickets")}


def number(value: object) -> float:
    parsed = pd.to_numeric(pd.Series([str(value or "").replace(",", "")]), errors="coerce").iloc[0]
    return 0.0 if pd.isna(parsed) else float(parsed)


def build_rows() -> pd.DataFrame:
    comparisons = pd.read_csv(COMPARISON_PATH, dtype=str).fillna("")
    extracts = pd.read_csv(EXTRACT_PATH, dtype=str).fillna("")
    extract_lookup = {
        (row["record_category"], normalize_featured_player_name(row["player_name"])): row
        for _, row in extracts.iterrows()
        if row["record_category"] in SECTIONS
    }
    rows = []
    for _, row in comparisons[comparisons["record_category"].isin(SECTIONS)].iterrows():
        section = row["record_category"]
        metric, _ = SECTIONS[section]
        normalized = normalize_featured_player_name(row["report_player_name"])
        annual = number(row["report_value"])
        final = number(row["matched_final_app_value"])
        playcricket = number(row["matched_playcricket_value"])
        excel = number(row["matched_excel_value"])
        candidates = [(annual, "annual_report"), (final, "current_final_logic"), (playcricket, "playcricket")]
        displayed, source = max(candidates, key=lambda item: item[0])
        evidence = extract_lookup.get((section, normalized), {})
        rows.append(
            {
                "section": section,
                "metric": metric,
                "player_name": row["report_player_name"],
                "normalized_player_name": normalized,
                "annual_report_value": int(annual),
                "current_final_logic_value": int(final) if final else "",
                "playcricket_value": int(playcricket) if playcricket else "",
                "historical_excel_value": int(excel) if excel else "",
                "displayed_value": int(displayed),
                "displayed_value_source": source,
                "reason": "Highest credible career total across Annual Report and current processed values.",
                "annual_report_page": evidence.get("page_number", row["report_page_number"]),
                "annual_report_section": evidence.get("section_heading", row["report_section_heading"]),
                "extraction_confidence": evidence.get("extraction_confidence", "high"),
                "included_in_app": "yes",
                "notes": "GRDCC Hall of Fame presentation only; raw and player-season data unchanged.",
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    rows = build_rows()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    rows.to_csv(OUTPUT_PATH, index=False)

    sample = pd.DataFrame({"Player": rows["player_name"], "Runs": 0, "Wickets": 0, "Matches": 0, "Catches": 0})
    applied = apply_featured_record_overrides(sample, "georges-river-district")
    normalized_applied = set(applied["Player"].map(normalize_featured_player_name))
    layout = LAYOUT_PATH.read_text(encoding="utf-8")
    checks = []
    for section, (_, column) in SECTIONS.items():
        expected = rows[rows["section"].eq(section)]
        comparison_values = expected[["annual_report_value", "current_final_logic_value", "playcricket_value"]].apply(
            pd.to_numeric, errors="coerce"
        ).fillna(0)
        checks.extend(
            [
                (f"{section}_rows_included", expected["normalized_player_name"].isin(normalized_applied).all(), len(expected)),
                (f"{section}_no_duplicates", not expected["normalized_player_name"].duplicated().any(), 0),
                (f"{section}_display_rule", (expected["displayed_value"] == comparison_values.max(axis=1)).all(), len(expected)),
                (f"{section}_top15_sorted", applied.sort_values(column, ascending=False).head(15)[column].is_monotonic_decreasing, 15),
            ]
        )
    checks.extend(
        [
            ("matches_report_list_absent", not rows["section"].eq("most_matches").any(), 0),
            ("catches_report_list_absent", not rows["section"].eq("most_catches").any(), 0),
            ("visible_rows_6", "visible_rows=6" in layout, 6),
            ("top_list_limit_15", "limit=15 if scrollable_grdcc_lists else 10" in layout, 15),
            ("source_note_hidden", "{source_note}</span>" not in layout and "){source_note}</strong>" not in layout, 0),
            ("premiership_final_year", "rendered.append(compact_premiership_final_year_link_html(season))" in layout, 1),
            ("premiership_wins_present", "premiership_wins_card" in layout, 1),
        ]
    )

    VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with VALIDATION_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["check", "status", "count_or_target"])
        for name, passed, count in checks:
            writer.writerow([name, "PASS" if passed else "FAIL", count])
    failures = [name for name, passed, _ in checks if not passed]
    higher = int(rows["displayed_value_source"].isin({"current_final_logic", "playcricket"}).sum())
    print(f"runs={sum(rows.section.eq('most_runs'))} wickets={sum(rows.section.eq('most_wickets'))} current_higher={higher} checks={len(checks)} failures={len(failures)}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
