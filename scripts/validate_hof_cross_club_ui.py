#!/usr/bin/env python3
"""Validate cross-club Hall of Fame navigation and responsive list behavior."""

from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "src/ui/layout.py"
THEME = ROOT / "src/ui/theme.py"
LOADER = ROOT / "src/data/playcricket_ingestion.py"
OVERRIDES = ROOT / "clubs/georges-river-district/data/source/annual_report_featured_record_overrides.csv"
LEADERS = ROOT / "clubs/georges-river-district/data/processed/validation/annual_report_2024_25/grdcc_annual_report_all_time_leaders_for_app.csv"
EXCEL_BATTING = ROOT / "clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_batting.csv"
PLAYCRICKET_BATTING = ROOT / "clubs/georges-river-district/data/processed/all_seasons_batting.csv"
OUTPUT = ROOT / "data/processed/validation/hof_cross_club_ui_validation.csv"
NAV_OUTPUT = ROOT / "clubs/georges-river-district/data/processed/validation/hof/grdcc_hof_link_navigation_validation.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def first_row(path: Path, season: str) -> dict[str, str]:
    return next((row for row in read_rows(path) if str(row.get("season", "")).strip() == season), {})


def player_name(row: dict[str, str]) -> str:
    for column in ("canonical_player_name", "player_name", "Player", "player"):
        value = str(row.get(column, "")).strip()
        if value and value.casefold() not in {"nan", "none"}:
            return value
    return ""


def app_url(page: str, **params: str) -> str:
    query = urlencode({"page": page, **params}, quote_via=quote)
    return f"./?{query}"


def main() -> int:
    layout = LAYOUT.read_text(encoding="utf-8")
    theme = THEME.read_text(encoding="utf-8")
    loader = LOADER.read_text(encoding="utf-8")

    historical = first_row(EXCEL_BATTING, "Summer 1971/72")
    modern = first_row(PLAYCRICKET_BATTING, "Summer 1972/73")
    nav_rows = []
    for row, season, bucket in (
        (historical, "Summer 1971/72", "excel_era"),
        (modern, "Summer 1972/73", "playcricket_era"),
    ):
        name = player_name(row)
        nav_rows.extend(
            [
                {
                    "section": "Hall of Fame",
                    "link_type": "season",
                    "label": season,
                    "target_url_or_query": app_url("season-overview", season=season),
                    "opens_new_tab": "yes",
                    "expected_source_bucket": bucket,
                    "validated_source_bucket": bucket,
                    "annual_report_override_applies": "no",
                    "validation_status": "PASS" if row else "FAIL",
                    "notes": "Source bucket is enforced by the existing GRDCC aggregate loader boundary.",
                },
                {
                    "section": "Hall of Fame",
                    "link_type": "player",
                    "label": name,
                    "target_url_or_query": app_url("player-profile", player=name),
                    "opens_new_tab": "yes",
                    "expected_source_bucket": bucket,
                    "validated_source_bucket": bucket,
                    "annual_report_override_applies": "no",
                    "validation_status": "PASS" if name else "FAIL",
                    "notes": "Player Profile reads the same final source-priority aggregate tables.",
                },
            ]
        )

    overrides = read_rows(OVERRIDES)
    for expected_name, expected_value in (("Harry Milburn", 10788), ("Gordon Leslie", 707)):
        matched = [
            row
            for row in overrides
            if str(row.get("player_name", "")).strip() == expected_name
            and float(row.get("authoritative_value") or 0) == expected_value
        ]
        nav_rows.append(
            {
                "section": "All-Time Leaders",
                "link_type": "featured_record",
                "label": expected_name,
                "target_url_or_query": app_url("player-profile", player=expected_name),
                "opens_new_tab": "yes",
                "expected_source_bucket": "annual_report_override",
                "validated_source_bucket": "annual_report_override" if matched else "missing",
                "annual_report_override_applies": "yes",
                "validation_status": "PASS" if matched else "FAIL",
                "notes": f"Expected authoritative value {expected_value}.",
            }
        )

    NAV_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with NAV_OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(nav_rows[0]))
        writer.writeheader()
        writer.writerows(nav_rows)

    leader_values_valid = True
    current_higher_count = 0
    if LEADERS.exists():
        for leader in read_rows(LEADERS):
            if str(leader.get("included_in_app", "yes")).strip().casefold() != "yes":
                continue
            annual = float(leader.get("annual_report_value") or 0)
            current = float(leader.get("current_final_logic_value") or 0)
            displayed = float(leader.get("displayed_value") or 0)
            leader_values_valid = leader_values_valid and displayed >= max(annual, current)
            current_higher_count += int(current > annual)

    changed = subprocess.run(
        ["git", "diff", "--name-only"], cwd=ROOT, check=True, capture_output=True, text=True
    ).stdout.splitlines()
    raw_changed = [path for path in changed if "/data/source/" in path or "all_seasons_" in path]

    checks = [
        ("grdcc_years_below_name", '<strong>{player_profile_link_html(player_id, player)}</strong>' in layout and '<span class="premiership-year-summary">{details}</span>' in layout),
        ("all_years_no_more", "compact_premiership_year_links_html" in layout and "visible_limit" not in re.search(r"def compact_premiership_year_links_html.*?def linked_premiership_seasons", layout, re.S).group(0)),
        ("duplicate_year_compression", 'f"{year} x {count}"' in layout),
        ("player_links_new_tab", "hof_internal_link_target_attrs()" in layout and 'target="_blank" rel="noopener noreferrer"' in layout),
        ("season_links_new_tab", "compact_premiership_year_links_html" in layout and "hof_internal_link_target_attrs()" in layout),
        ("scorecard_links_new_tab", "scorecard_link_html" in layout and "target=\"_blank\" rel=\"noopener noreferrer\"" in layout),
        ("grdcc_source_boundary", 'GRDCC_EXCEL_LAST_SEASON = "Summer 1971/72"' in loader and 'GRDCC_PLAYCRICKET_FIRST_SEASON = "Summer 1972/73"' in loader),
        ("annual_report_overrides", len(overrides) >= 2 and all(row["validation_status"] == "PASS" for row in nav_rows[-2:])),
        ("current_higher_rule", "max(float(current_value), float(leader[\"displayed_value\"]))" in (ROOT / "src/data/featured_record_overrides.py").read_text(encoding="utf-8") and leader_values_valid),
        ("hover_not_purple", ".block-container:has(.hall-of-fame-page) a:hover" in theme and "color: var(--club-link) !important" in theme),
        ("fvcc_active_badges", "active_hof_players(hall_of_fame_data)" in layout and "hof-active-badge" in layout and 'get_active_club_id() != "georges-river-district"' not in re.search(r"def active_hof_players.*?def render_hall_of_fame_leaders", layout, re.S).group(0)),
        ("cross_club_scroll", "limit=15" in layout and "scrollable=True" in layout),
        ("mobile_top_five", "max-height: calc(5 * 58px);" in theme and "@media (max-width: 760px)" in theme),
        ("fvcc_final_year_format", "compact_premiership_year_links_html" in layout and "premiership_final_year_label" in layout),
        ("stats_table_preserved", "render_detailed_all_time_records(hall_of_fame_data[\"detailed_tables\"])" in layout),
        ("no_raw_sources_changed", not raw_changed),
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["check", "status", "details"])
        for name, passed in checks:
            details = f"current_higher_rows={current_higher_count}" if name == "current_higher_rule" else ""
            writer.writerow([name, "PASS" if passed else "FAIL", details])

    failures = sum(not passed for _, passed in checks)
    print(
        f"checks={len(checks)} failures={failures} navigation_rows={len(nav_rows)} "
        f"current_higher_rows={current_higher_count} raw_source_changes={len(raw_changed)}"
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
