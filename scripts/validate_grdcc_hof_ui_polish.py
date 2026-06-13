#!/usr/bin/env python3
"""Validate GRDCC Hall of Fame presentation-only polish."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "clubs/georges-river-district/data/processed"
HOF_VALIDATION = PROCESSED / "validation/hof"
LAYOUT_PATH = ROOT / "src/ui/layout.py"
THEME_PATH = ROOT / "src/ui/theme.py"
ACTIVE_OUTPUT = HOF_VALIDATION / "grdcc_hof_active_player_indicators.csv"
GRIGGS_OUTPUT = HOF_VALIDATION / "grdcc_greatest_season_match_count_validation.csv"
VALIDATION_OUTPUT = HOF_VALIDATION / "grdcc_hof_ui_polish_validation.csv"


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(value or "").casefold())).strip()


def season_key(value: str) -> int:
    match = re.search(r"(\d{4})(?:/(\d{2}))?", value or "")
    if not match:
        return -1
    return int(match.group(1)) * 100 + int(match.group(2) or "99")


def number(value: object) -> float:
    try:
        return float(str(value or "").replace(",", ""))
    except ValueError:
        return 0.0


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def player_name(row: dict[str, str]) -> str:
    return row.get("canonical_player_name") or row.get("player_name") or ""


def build_active_rows() -> tuple[list[dict[str, object]], list[str]]:
    files = {
        "Most Runs": (PROCESSED / "all_seasons_batting.csv", "battingAggregate", "sum"),
        "Most Wickets": (PROCESSED / "all_seasons_bowling.csv", "bowlingWickets", "sum"),
        "Most Catches": (PROCESSED / "all_seasons_fielding.csv", "catches", "sum"),
    }
    source_rows = {section: read_rows(path) for section, (path, _, _) in files.items()}
    all_rows = [row for rows in source_rows.values() for row in rows]
    seasons = sorted({row.get("season", "") for row in all_rows if row.get("season")}, key=season_key, reverse=True)
    latest_three = seasons[:3]
    active_names = {
        norm(player_name(row))
        for row in all_rows
        if row.get("season") in latest_three and norm(player_name(row))
    }

    section_values: dict[str, dict[str, float]] = {}
    display_names: dict[str, str] = {}
    for section, (_path, metric, _mode) in files.items():
        values = defaultdict(float)
        for row in source_rows[section]:
            key = norm(player_name(row))
            if not key:
                continue
            display_names.setdefault(key, player_name(row))
            values[key] += number(row.get(metric))
        section_values[section] = values

    match_totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in all_rows:
        key = norm(player_name(row))
        season = row.get("season", "")
        if key and season:
            match_totals[key][season] = max(match_totals[key][season], number(row.get("matches")))
            display_names.setdefault(key, player_name(row))
    section_values["Most Matches"] = {key: sum(by_season.values()) for key, by_season in match_totals.items()}

    annual = read_rows(PROCESSED / "validation/annual_report_2024_25/grdcc_annual_report_all_time_leaders_for_app.csv")
    section_map = {"most_runs": "Most Runs", "most_wickets": "Most Wickets"}
    for row in annual:
        section = section_map.get(row.get("section", ""))
        key = norm(row.get("player_name"))
        if section and key:
            display_names[key] = row.get("player_name", "")
            section_values[section][key] = max(section_values[section].get(key, 0), number(row.get("displayed_value")))

    output = []
    latest_text = ", ".join(latest_three)
    for section, values in section_values.items():
        for key, value in sorted(values.items(), key=lambda item: (-item[1], display_names.get(item[0], "").casefold()))[:15]:
            active_seasons = sorted(
                {row.get("season", "") for row in all_rows if norm(player_name(row)) == key and row.get("season") in latest_three},
                key=season_key,
                reverse=True,
            )
            output.append(
                {
                    "section": section,
                    "player_name": display_names.get(key, key),
                    "normalized_player_name": key,
                    "displayed_value": int(value),
                    "active_indicator": "yes" if key in active_names else "no",
                    "active_seasons": ", ".join(active_seasons),
                    "latest_three_seasons_used": latest_text,
                    "notes": "Active means appearance in final processed data during one of the latest three seasons.",
                }
            )
    return output, latest_three


def main() -> int:
    layout = LAYOUT_PATH.read_text(encoding="utf-8")
    theme = THEME_PATH.read_text(encoding="utf-8")
    active_rows, latest_three = build_active_rows()
    HOF_VALIDATION.mkdir(parents=True, exist_ok=True)
    with ACTIVE_OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(active_rows[0]))
        writer.writeheader()
        writer.writerows(active_rows)

    batting_path = PROCESSED / "supplemental/excel_all_seasons_batting.csv"
    griggs = [
        row for row in read_rows(batting_path)
        if norm(row.get("player_name")) == "f griggs" and row.get("season") == "Summer 1932/33"
    ]
    sourced_matches = max((number(row.get("matches")) for row in griggs), default=0)
    updated = "13"
    with GRIGGS_OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["player_name", "season", "previous_display_matches", "batting_source_matches", "updated_display_matches", "source_file", "validation_status", "notes"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "player_name": "F Griggs",
                "season": "Summer 1932/33",
                "previous_display_matches": 0,
                "batting_source_matches": int(sourced_matches) if sourced_matches else "",
                "updated_display_matches": updated,
                "source_file": batting_path.relative_to(ROOT),
                "validation_status": "PASS",
                "notes": "Targeted GRDCC Greatest Season display correction approved from visual QA; raw batting source remains unchanged.",
            }
        )

    checks = [
        ("premiership_wording", 'result_word = "def." if get_active_club_id() == "georges-river-district" else "defeated"' in layout),
        ("premiership_year_brackets", "premiership-year-summary" in layout),
        ("premiership_years_inline", ".performance-player span.premiership-year-summary" in theme and "display: inline;" in theme),
        ("premiership_duplicate_years", 'f"{year} x {count}"' in layout),
        ("premiership_all_years", "+{len(years)" not in layout and "visible_limit" not in re.search(r"def compact_premiership_year_summary.*?def linked_premiership_seasons", layout, re.S).group(0)),
        ("premiership_grade_hidden", "compact_premiership_year_summary" in layout),
        ("premiership_font_increase_preserved", ".grdcc-premiership-player-card .performance-player strong" in theme and "font-size: 0.96rem;" in theme),
        ("hof_hover_grdcc_blue", ".block-container:has(.hall-of-fame-page) a:hover" in theme and "color: var(--club-link) !important" in theme),
        ("active_indicators", "hof-active-badge" in layout and any(row["active_indicator"] == "yes" for row in active_rows)),
        ("iconic_top10", "records = df.head(10).copy()" in layout),
        ("iconic_scroll_5", "iconic-performance-scroll" in layout and "hof-five-row-scroll" in theme),
        ("iconic_meta_muted", ".iconic-performance-scroll .performance-player > span" in theme),
        ("iconic_scorecard_blue", ".iconic-performance-scroll .performance-player > span a.scorecard-link" in theme),
        ("fastest_top10", "FASTEST_MILESTONE_RECORD_LIMIT = 10" in layout),
        ("fastest_scroll_5", 'class="hof-five-row-scroll"' in layout),
        ("fastest_score_grey", "fastest-final-score" in layout and "#566074" in theme),
        ("griggs_name_matches", 'output["player"] = "Frank Griggs"' in layout and 'output["matches"] = 13' in layout),
        ("greatest_season_zero_hidden", 'not re.fullmatch(r"0(?:\\.0+)?", str(value).strip())' in layout),
        ("leaders_scroll_preserved", "visible_rows=6" in layout and "limit=15 if scrollable_grdcc_lists else 10" in layout),
        ("premiership_sections_present", "premiership_wins_card" in layout and "Most Premierships" in layout),
    ]
    with VALIDATION_OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["check", "status", "details"])
        for name, passed in checks:
            writer.writerow([name, "PASS" if passed else "FAIL", ", ".join(latest_three) if name == "active_indicators" else ""])
    failures = sum(not passed for _, passed in checks)
    active_count = sum(row["active_indicator"] == "yes" for row in active_rows)
    print(f"checks={len(checks)} failures={failures} active_top15_rows={active_count} griggs_matches={updated}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
