#!/usr/bin/env python3
"""Validate the FVCC production visual regression fixes."""

from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYOUT_PATH = ROOT / "src/ui/layout.py"
THEME_PATH = ROOT / "src/ui/theme.py"
FVCC_ROOT = ROOT / "clubs/fvcc"
PREMIERSHIP_PATH = FVCC_ROOT / "data/processed/hall_of_fame/premiership_wins.csv"
OUTPUT_PATH = FVCC_ROOT / "data/processed/validation/hof/fvcc_prod_visual_regression_validation.csv"


def function_source(source: str, name: str, next_name: str) -> str:
    match = re.search(rf"def {name}\([\s\S]*?(?=\ndef {next_name}\()", source)
    return match.group(0) if match else ""


def season_key(value: object) -> int:
    text = str(value or "")
    years = [int(year) for year in re.findall(r"(?:19|20)\d{2}", text)]
    if not years:
        return -1
    if "summer" in text.casefold() and len(years) == 1:
        short_year = re.search(r"/(\d{2})", text)
        if short_year:
            end_year = (years[0] // 100) * 100 + int(short_year.group(1))
            return end_year + (100 if end_year < years[0] else 0)
    return max(years)


def git_unchanged(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    return subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", relative],
        cwd=ROOT,
        check=False,
    ).returncode == 0


def main() -> int:
    layout = LAYOUT_PATH.read_text()
    theme = THEME_PATH.read_text()
    premierships = pd.read_csv(PREMIERSHIP_PATH)
    season_keys = premierships["season"].map(season_key)

    ranked = function_source(layout, "render_ranked_record_card", "milestone_record_row_html")
    iconic = function_source(layout, "render_performance_card", "sort_hof_leaders")
    leaders = function_source(layout, "render_hof_leader_card", "render_hof_expand_control")
    season_cards = function_source(layout, "season_round_cards_html", "season_round_row_html")

    checks = [
        ("premiership_reverse_chronological", "sort_values(\"_season_sort\", ascending=False" in layout and season_keys.max() == season_key("Summer 2024/25"), "Stable latest-first season ordering is configured; latest source season is Summer 2024/25."),
        ("premiership_desktop_six", 'data-desktop-visible-rows="6"' in layout and "max-height: calc(6 * 111px)" in theme, "Desktop target is six rows."),
        ("premiership_mobile_five", 'data-mobile-visible-rows="5"' in layout and theme.count("max-height: 826px") >= 1, "Mobile target is five measured compact rows."),
        ("premiership_scroll_enabled", 'class="premiership-card-scroll premiership-wins-scroll"' in layout and "overflow-y: auto" in theme, "One continuous scroll container is present."),
        ("premiership_row_count_unchanged", git_unchanged(PREMIERSHIP_PATH), f"Source remains unchanged with {len(premierships)} rows."),
        ("leaders_scroll", 'class="hof-leader-scroll"' in leaders and 'data-mobile-visible-rows="5"' in leaders and "if not scrollable:" in leaders and "scrollable=True" in layout, "All-Time Leaders use the scroll renderer and bypass the expand control."),
        ("fastest_scroll", "hof-responsive-record-scroll" in ranked and 'data-mobile-visible-rows="5"' in ranked and "not grdcc_scroll and not fvcc_scroll" in ranked, "FVCC Fastest Innings uses responsive scrolling and suppresses the old control."),
        ("iconic_scroll", "hof-responsive-record-scroll iconic-performance-scroll" in iconic and 'data-mobile-visible-rows="5"' in iconic and "not grdcc_scroll and not fvcc_scroll" in iconic, "FVCC Iconic Performances use responsive scrolling and suppress the old control."),
        ("hof_desktop_six", "max-height: 606px" in theme and "max-height: 474px" in theme and layout.count('data-desktop-visible-rows="6"') >= 3, "Responsive record lists use measured six-row desktop viewports."),
        ("hof_mobile_five", "max-height: 505px" in theme and "max-height: 395px" in theme and layout.count('data-mobile-visible-rows="5"') >= 4, "Leader and record lists use measured five-row mobile viewports."),
        ("season_round_no_folder", 'data-internal-folder-selector="false"' in season_cards and "def selected_season_round_grade_filter(" not in layout, "Internal folder selector is absent."),
        ("season_round_horizontal_scroll", all(token in theme for token in [".season-round-panel-strip", "display: flex", "flex-wrap: nowrap", "overflow-x: auto", "-webkit-overflow-scrolling: touch"]), "Horizontal non-wrapping touch scroll is configured."),
        ("season_round_panel_width", "flex: 0 0 min(980px, 92vw)" in theme and "scroll-snap-align: start" in theme, "Panels retain a fixed scrollable width and snap point."),
        ("global_slicers_preserved", 'st.selectbox(\n                "Season"' in layout and 'st.selectbox(\n                "Team"' in layout, "Top season and team/grade slicers remain."),
        ("fvcc_palette_unchanged", git_unchanged(FVCC_ROOT / "club_config.yaml") and all(token in theme for token in ['"primary_colour": "#A31952"', '"secondary_colour": "#28485F"', '"accent_colour": "#D4A83A"', '"background_colour": "#F6F8FB"']), "FVCC config and production palette tokens are unchanged."),
        ("fvcc_stats_unchanged", all(git_unchanged(path) for path in (FVCC_ROOT / "data/processed").glob("*.csv")) and all(git_unchanged(path) for path in (FVCC_ROOT / "data/processed/hall_of_fame").glob("*.csv")), "FVCC aggregate and Hall of Fame source CSVs are unchanged."),
        ("grdcc_branch_unchanged", 'get_active_club_id() == "georges-river-district"' in ranked and 'get_active_club_id() == "georges-river-district"' in iconic, "GRDCC keeps its existing dedicated scroll branch."),
    ]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "notes"])
        writer.writeheader()
        for name, passed, notes in checks:
            writer.writerow({"check": name, "status": "pass" if passed else "fail", "notes": notes})

    failed = [name for name, passed, _ in checks if not passed]
    print(f"validation_status={'pass' if not failed else 'fail'} checks={len(checks)} failed={len(failed)}")
    if failed:
        print("failed_checks=" + ",".join(failed))
        return 1
    print(f"premiership_rows={len(premierships)} latest_season={premierships.loc[season_keys.idxmax(), 'season']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
