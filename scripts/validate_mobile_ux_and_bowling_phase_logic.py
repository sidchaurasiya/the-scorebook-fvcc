from __future__ import annotations

import csv
import importlib
import math
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_PATH = ROOT / "data" / "processed" / "validation" / "mobile_ux_and_bowling_phase_logic_validation.csv"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def add(rows: list[dict[str, str]], check_name: str, passed: bool, notes: str = "") -> None:
    rows.append(
        {
            "check_name": check_name,
            "status": "pass" if passed else "fail",
            "notes": notes,
        }
    )


def validate_best_phase(rows: list[dict[str, str]]) -> None:
    layout = importlib.import_module("src.ui.layout")
    sample = pd.DataFrame(
        [
            {"phase": "New Ball", "legal_balls": 198, "avg": 16.20, "phase_order": 1},
            {"phase": "Older Ball", "legal_balls": 228, "avg": 18.29, "phase_order": 2},
        ]
    )
    add(
        rows,
        "bowling phase chooses lowest average after 10 overs",
        layout.profile_best_phase_label(sample) == "New Ball",
        "New Ball 33.0 overs at 16.20 should beat Older Ball 38.0 overs at 18.29.",
    )
    below_threshold = pd.DataFrame(
        [
            {"phase": "New Ball", "legal_balls": 54, "avg": 8.0, "phase_order": 1},
            {"phase": "Older Ball", "legal_balls": 48, "avg": 9.0, "phase_order": 2},
        ]
    )
    add(
        rows,
        "bowling phase suppresses best phase below 10 overs",
        layout.profile_best_phase_label(below_threshold) == "",
        "No phase has 60 legal balls.",
    )
    invalid_average = pd.DataFrame(
        [
            {"phase": "New Ball", "legal_balls": 72, "avg": math.inf, "phase_order": 1},
            {"phase": "Older Ball", "legal_balls": 72, "avg": None, "phase_order": 2},
        ]
    )
    add(
        rows,
        "bowling phase ignores invalid averages",
        layout.profile_best_phase_label(invalid_average) == "",
        "Null or infinite averages are not eligible.",
    )


def main() -> int:
    rows: list[dict[str, str]] = []
    layout = read_text("src/ui/layout.py")
    theme = read_text("src/ui/theme.py")

    add(
        rows,
        "best fit requirement text removed",
        "Best fit requires" not in layout and "Best fit needs" not in layout,
        "The batting-position threshold still exists in player_best_position_min_innings.",
    )
    add(
        rows,
        "leader KPI overflow-safe chip spans present",
        "leader-highlight-chip-grade" in layout and "leader-highlight-chip-season" in layout,
        "Grade and season are rendered separately inside each chip.",
    )
    add(
        rows,
        "leader KPI overflow-safe CSS present",
        "grid-template-columns: minmax(0, 1fr) auto" in theme
        and ".leader-highlight-chip-grade" in theme
        and ".leader-highlight-chip-season" in theme,
        "Chip grade text can ellipsize while season stays visible.",
    )
    add(
        rows,
        "SBR mobile result right column CSS present",
        "grid-template-columns: minmax(0, 1fr) minmax(78px, 31%)" in theme
        and "grid-column: 2;" in theme
        and "text-align: right;" in theme,
        "Mobile round rows keep result badge and summary on the right.",
    )
    add(
        rows,
        "milestone mobile tabs one-row CSS present",
        "div.st-key-milestone_page_view_folder_tabs [data-testid=\"stButtonGroup\"] > div" in theme
        and "grid-template-columns: repeat(3, minmax(0, 1fr)) !important;" in theme,
        "Three milestone folders fit in one compact row on mobile.",
    )
    add(
        rows,
        "career breakdown mobile tabs two-row CSS present",
        "div.st-key-player_profile_breakdown_folder_tabs [data-testid=\"stButtonGroup\"] > div" in theme
        and "grid-template-columns: repeat(3, minmax(0, 1fr)) !important;" in theme,
        "Six Career Breakdown folders render as three columns by two rows on mobile.",
    )
    add(
        rows,
        "GRDCC Career Breakdown grade order present",
        "GRDCC_CAREER_BREAKDOWN_GRADE_ORDER" in layout
        and '"First Grade Limited Overs"' in layout
        and '"Frank Gray Shield"' in layout,
        "Requested grade order is applied to GRDCC Career Breakdown display sorting.",
    )
    validate_best_phase(rows)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check_name", "status", "notes"])
        writer.writeheader()
        writer.writerows(rows)

    passed = sum(row["status"] == "pass" for row in rows)
    total = len(rows)
    print(f"mobile UX and bowling phase validation: {passed}/{total} passed")
    print(f"output: {OUTPUT_PATH}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
