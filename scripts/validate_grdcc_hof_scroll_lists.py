#!/usr/bin/env python3
"""Validate the GRDCC Hall of Fame scroll-list configuration."""

from __future__ import annotations

import csv
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT_PATH = ROOT / "src/ui/layout.py"
THEME_PATH = ROOT / "src/ui/theme.py"
OUTPUT_PATH = (
    ROOT
    / "clubs/georges-river-district/data/processed/validation/hof"
    / "grdcc_hof_scroll_lists_validation.csv"
)
SECTIONS = ("Most Runs", "Most Matches", "Most Wickets", "Most Catches")


def main() -> int:
    layout = LAYOUT_PATH.read_text(encoding="utf-8")
    theme = THEME_PATH.read_text(encoding="utf-8")
    checks = []

    for section in SECTIONS:
        checks.append((f"section_present:{section}", section in layout, "configured in leader specs"))

    checks.extend(
        [
            ("grdcc_scoped", 'get_active_club_id() == "georges-river-district"' in layout, "other clubs retain existing behavior"),
            ("top_15_limit", "limit=15 if scrollable_grdcc_lists else 10" in layout, "GRDCC limit is 15"),
            ("visible_rows_6", "visible_rows=6" in layout, "six-row target configured"),
            ("continuous_scroll", 'class="hof-leader-scroll"' in layout, "single list container"),
            ("scroll_css", "overflow-y: auto" in theme and "--hof-visible-rows" in theme, "responsive internal scroll"),
            ("descending_sort_preserved", "sort_hof_leaders(leaders, metric, mode).head(limit)" in layout, "existing sort helper retained"),
            ("premiership_wins_untouched", "premiership-card-scroll" in layout, "existing renderer remains present"),
            ("most_premierships_untouched", "load_grdcc_most_premierships" in layout, "existing data path remains present"),
        ]
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["check", "status", "details"])
        for name, passed, details in checks:
            writer.writerow([name, "PASS" if passed else "FAIL", details])

    failures = [name for name, passed, _ in checks if not passed]
    print(f"checks={len(checks)} failures={len(failures)} output={OUTPUT_PATH}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
