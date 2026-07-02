#!/usr/bin/env python3
"""Validate FVCC parity for shared GRDCC polish without GRDCC-only data rules."""

from __future__ import annotations

import csv
import importlib
import math
import os
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["CLUB_ID"] = "fvcc"

OUTPUT_PATH = ROOT / "clubs" / "fvcc" / "data" / "processed" / "validation" / "fvcc_grdcc_parity_polish_validation.csv"


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def add(rows: list[dict[str, str]], check_name: str, passed: bool, notes: str = "") -> None:
    rows.append(
        {
            "check_name": check_name,
            "validation_status": "pass" if passed else "fail",
            "notes": notes,
        }
    )


def validate_bowling_phase(rows: list[dict[str, str]]) -> None:
    layout = importlib.import_module("src.ui.layout")
    sample = pd.DataFrame(
        [
            {"phase": "New Ball", "legal_balls": 198, "avg": 16.20, "phase_order": 1},
            {"phase": "Older Ball", "legal_balls": 228, "avg": 18.29, "phase_order": 2},
        ]
    )
    add(
        rows,
        "bowling_phase_best_phase_lowest_average_after_10_overs",
        layout.profile_best_phase_label(sample) == "New Ball",
        "33.0 overs at 16.20 should beat 38.0 overs at 18.29.",
    )
    below_threshold = pd.DataFrame(
        [{"phase": "New Ball", "legal_balls": 59, "avg": 1.0, "phase_order": 1}]
    )
    add(
        rows,
        "bowling_phase_requires_10_overs",
        layout.profile_best_phase_label(below_threshold) == "",
        "59 balls is below the 60-ball eligibility threshold.",
    )
    invalid_average = pd.DataFrame(
        [
            {"phase": "New Ball", "legal_balls": 72, "avg": math.inf, "phase_order": 1},
            {"phase": "Older Ball", "legal_balls": 72, "avg": None, "phase_order": 2},
        ]
    )
    add(
        rows,
        "bowling_phase_ignores_invalid_average",
        layout.profile_best_phase_label(invalid_average) == "",
        "Null or infinite averages should not win BEST PHASE.",
    )


def validate_fvcc_data_propagation(rows: list[dict[str, str]]) -> None:
    propagation_path = ROOT / "clubs" / "fvcc" / "data" / "processed" / "validation" / "fvcc_winter_2026_full_propagation_validation.csv"
    if not propagation_path.exists():
        propagation_path = ROOT / "clubs" / "fvcc" / "data" / "processed" / "validation" / "fvcc_full_data_propagation_validation.csv"
    if not propagation_path.exists():
        add(rows, "fvcc_full_data_propagation_output_exists", False, str(propagation_path))
        return
    data = pd.read_csv(propagation_path)
    status_column = "validation_status" if "validation_status" in data.columns else "status"
    failed = data[data[status_column].astype(str).str.casefold().ne("pass")] if status_column in data else data
    add(
        rows,
        "fvcc_full_data_propagation_passes",
        failed.empty,
        f"{len(data) - len(failed)}/{len(data)} checks passed",
    )


def main() -> int:
    rows: list[dict[str, str]] = []
    layout = read_text("src/ui/layout.py")
    theme = read_text("src/ui/theme.py")
    grdcc_config = read_text("clubs/georges-river-district/club_config.yaml")

    add(
        rows,
        "fvcc_best_fit_explainer_removed",
        "Best fit requires" not in layout and "Best fit needs" not in layout,
        "The threshold helper remains in player_best_position_min_innings.",
    )
    add(
        rows,
        "career_highlight_leader_chips_overflow_safe",
        "leader-highlight-chip-grade" in layout
        and "leader-highlight-chip-season" in layout
        and "grid-template-columns: minmax(0, 1fr) auto" in theme,
        "Grade and season use separate spans inside an overflow-safe chip grid.",
    )
    add(
        rows,
        "season_by_round_mobile_result_alignment_shared",
        "grid-template-columns: minmax(0, 1fr) minmax(78px, 31%)" in theme
        and ".season-round-row .season-round-result" in theme
        and "text-align: right;" in theme,
        "Mobile SBR uses left content plus right result column.",
    )
    add(
        rows,
        "season_by_round_hover_scroll_shared",
        "season_round_scroll_script_html" in layout
        and "season-round-scroll-shell" in layout
        and "wheel" in layout
        and "scrollLeft" in layout,
        "SBR hover wheel handler is injected from shared render path.",
    )
    add(
        rows,
        "milestone_mobile_tabs_one_line_shared",
        "div.st-key-milestone_page_view_folder_tabs [data-testid=\"stButtonGroup\"] > div" in theme
        and "grid-template-columns: repeat(3, minmax(0, 1fr)) !important;" in theme,
        "Three milestone tabs fit one mobile row.",
    )
    add(
        rows,
        "career_breakdown_mobile_tabs_two_rows_shared",
        "div.st-key-player_profile_breakdown_folder_tabs [data-testid=\"stButtonGroup\"] > div" in theme
        and "grid-template-columns: repeat(3, minmax(0, 1fr)) !important;" in theme,
        "Six Career Breakdown tabs render as three columns by two rows.",
    )
    add(
        rows,
        "fvcc_theme_tokens_preserved",
        "#A31952" in theme
        and "#28485F" in theme
        and "#0B3F9F" not in theme
        and 'primary_colour: "#0B3F9F"' in grdcc_config
        and "var(--club-primary" in theme,
        "FVCC production tokens remain in shared theme; GRDCC tokens live in club config and flow through variables.",
    )
    add(
        rows,
        "grdcc_specific_historical_rules_not_added_to_fvcc_validator",
        all(
            marker not in layout
            for marker in [
                "Alan Mashman",
                "Ben Saunders",
            ]
        ),
        "FVCC parity validator excludes GRDCC historical/proxy/source-priority cases.",
    )
    validate_bowling_phase(rows)
    validate_fvcc_data_propagation(rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check_name", "validation_status", "notes"])
        writer.writeheader()
        writer.writerows(rows)

    failed = [row for row in rows if row["validation_status"] != "pass"]
    print(f"FVCC/GRDCC parity polish validation: {len(rows) - len(failed)}/{len(rows)} passed")
    print(f"output: {OUTPUT_PATH}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
