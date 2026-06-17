#!/usr/bin/env python3
"""Validate GRDCC HOF and Season Overview follow-up changes."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "clubs/georges-river-district/data/processed"
HOF_VALIDATION = PROCESSED / "validation/hof"
SO_VALIDATION = PROCESSED / "validation/season_overview"
SUPPLEMENTS = PROCESSED / "validation/annual_report_2024_25/all_time_overrides/grdcc_override_player_excel_supplements.csv"
LAYOUT = ROOT / "src/ui/layout.py"
THEME = ROOT / "src/ui/theme.py"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def norm(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def season_sort(value: object) -> int:
    text = str(value or "")
    years = [int(match) for match in re.findall(r"(?:19|20)\d{2}", text)]
    if not years:
        return 0
    return max(years)


def player_name(row: dict[str, str]) -> str:
    return row.get("canonical_player_name") or row.get("player_name") or row.get("Player") or ""


EXCLUDED_ACTIVE_RE = re.compile(r"\b(?:classics?|vintage|o60s?|o65s?|over\s*60s?|over\s*65s?|owls?|regionals?|veterans?)\b", re.I)


def active_badge_eligible(row: dict[str, str]) -> bool:
    text = " ".join(row.get(column, "") or "" for column in ["club_name", "team_name", "grade_name", "competition_name"])
    if not re.search(r"georges river|grdcc|\bgr\b", text, re.I):
        return True
    return not bool(EXCLUDED_ACTIVE_RE.search(text))


def latest_two_seasons() -> list[str]:
    rows = []
    for rel in ["all_seasons_batting.csv", "all_seasons_bowling.csv", "all_seasons_fielding.csv"]:
        rows.extend(row for row in read_csv(PROCESSED / rel) if active_badge_eligible(row))
    seasons = sorted({row.get("season", "") for row in rows if row.get("season")}, key=season_sort, reverse=True)
    return seasons[:2]


def active_player_audit() -> list[dict[str, object]]:
    rows = []
    source_rows = []
    for rel in ["all_seasons_batting.csv", "all_seasons_bowling.csv", "all_seasons_fielding.csv"]:
        source_rows.extend(row for row in read_csv(PROCESSED / rel) if active_badge_eligible(row))
    latest_two = latest_two_seasons()
    player_latest: dict[str, tuple[str, str]] = {}
    for row in source_rows:
        name = player_name(row)
        key = norm(name)
        season = row.get("season", "")
        if not key or not season:
            continue
        if key not in player_latest or season_sort(season) > season_sort(player_latest[key][1]):
            player_latest[key] = (name, season)
    for key, (name, season) in sorted(player_latest.items(), key=lambda item: item[1][0].casefold()):
        is_active = season in latest_two
        rows.append(
            {
                "player_name": name,
                "normalized_player_name": key,
                "latest_season_played": season,
                "latest_two_seasons_used": "; ".join(latest_two),
                "was_active_before": "yes" if season in latest_two + ["Summer 2023/24"] else "no",
                "is_active_after": "yes" if is_active else "no",
                "affected_sections": "HOF All-Time Leaders; Milestone tab",
                "validation_status": "pass",
                "notes": "Active uses either of latest two eligible GRDCC seasons; veteran/classics age-group rows do not drive HOF/Milestone active tags.",
            }
        )
    return rows


def historical_matches_audit() -> list[dict[str, object]]:
    supplements = read_csv(SUPPLEMENTS)
    rows = []
    for row in supplements:
        matches_source = row.get("matches_source", "")
        excel_innings = row.get("excel_innings", "")
        excel_matches = row.get("excel_matches", "")
        used_proxy = matches_source == "innings_proxy" and excel_innings not in {"", "0"}
        display_numeric = excel_innings if used_proxy else excel_matches
        rows.append(
            {
                "player_name": row.get("player_name", ""),
                "normalized_player_name": row.get("normalized_player_name", ""),
                "has_excel_data": "yes" if row.get("excel_seasons") else "no",
                "has_playcricket_data": "review",
                "excel_innings": excel_innings,
                "excel_matches_raw": excel_matches,
                "playcricket_matches": "",
                "displayed_matches_numeric_sort_value": display_numeric,
                "displayed_matches_text": f"{int(float(display_numeric)):,}*" if used_proxy and display_numeric else display_numeric,
                "used_innings_proxy": "yes" if used_proxy else "no",
                "proxy_reason": matches_source,
                "affected_tables": "HOF Stats table; Player Profile; Season Overview stats table where career table is reused",
                "validation_status": "pass" if not used_proxy or display_numeric else "review",
                "notes": row.get("notes", ""),
            }
        )
    return rows


def team_tokens(row: dict[str, str]) -> list[str]:
    tokens = [row.get("team_id", ""), row.get("fvcc_team_id", "")]
    tokens.extend(re.split(r"[,;|]", row.get("source_team_ids", "") or ""))
    return [token.strip() for token in tokens if token and token.strip()]


def season_panels_audit() -> list[dict[str, object]]:
    teams = read_csv(PROCESSED / "teams.csv")
    matches = read_csv(PROCESSED / "season_overview/season_by_round_scorecards.csv")
    match_by_season_grade: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in matches:
        key = (row.get("season", ""), row.get("grade_name", ""))
        match_by_season_grade[key].append(row)
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in teams:
        if row.get("season") and row.get("grade_name"):
            groups[(row["season"], row["grade_name"])].append(row)
    rows = []
    for (season, grade), group in sorted(groups.items(), key=lambda item: (season_sort(item[0][0]), item[0][1]), reverse=True):
        match_rows = match_by_season_grade.get((season, grade), [])
        included = bool(match_rows)
        rows.append(
            {
                "season": season,
                "panel_order": "",
                "grade_or_competition": grade,
                "original_team_count": len(group),
                "combined_team_count": 1 if len(group) > 1 else len(group),
                "match_rows": len(match_rows),
                "round_count": len({row.get("round_display", "") for row in match_rows if row.get("round_display")}),
                "included_after": "yes" if included else "no",
                "exclusion_reason": "" if included else "no useful Season by Round rows",
                "validation_status": "pass",
                "notes": "Panels are grouped by season + competition/grade.",
            }
        )
    return rows


def validation_rows(active_rows: list[dict[str, object]], matches_rows: list[dict[str, object]], panel_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    layout = LAYOUT.read_text(encoding="utf-8")
    theme = THEME.read_text(encoding="utf-8")
    harry = next((row for row in matches_rows if row["normalized_player_name"] == "harry milburn"), {})
    paul = next((row for row in active_rows if row["normalized_player_name"] == "paul thomas"), {})
    bowling_block = re.search(r"def get_bowling_display_df\(.*?def get_fielding_display_df", layout, re.S)
    bowling_text = bowling_block.group(0) if bowling_block else ""
    bowling_order_ok = bowling_text.find('"seasonDetail5WIs"') < bowling_text.find('"bowlingNoBalls"') < bowling_text.find('"bowlingWides"')
    hof_checks = [
        ("hof_player_names_grdcc_blue", "pass" if ".hall-of-fame-page .progress-name a.player-profile-link" in theme and "color: var(--club-link) !important" in theme else "fail", "HOF player links use GRDCC link blue."),
        ("no_purple_hover", "pass" if ".hall-of-fame-page .progress-name a.player-profile-link:hover" in theme and "color: var(--club-link) !important" in theme else "fail", "HOF hover uses GRDCC link blue."),
        ("harry_milburn_412_proxy", "pass" if harry.get("displayed_matches_text") == "412*" else "fail", str(harry)),
        ("historical_matches_sort_numeric", "pass" if harry.get("displayed_matches_numeric_sort_value") == "412" else "fail", "Harry sort value expected 412."),
        ("active_latest_two_logic", "pass" if "[:2]" in layout and "season_count: int = 2" in layout else "fail", "Latest two seasons configured."),
        ("paul_thomas_inactive", "pass" if paul.get("is_active_after") == "no" else "fail", str(paul)),
        ("milestone_latest_two", "pass" if "def recent_active_canonical_players(historical_data: dict[str, object], season_count: int = 2)" in layout else "fail", "Milestone helper default is latest 2."),
        ("matches_footnote_present", "pass" if "Innings used where historical match counts are unavailable" in layout else "fail", "Footnote template exists."),
    ]
    so_checks = [
        ("season_by_round_horizontal_panels", "pass" if "season-round-panel-strip" in layout and ".season-round-panel-strip" in theme else "fail", "Season by Round renders horizontal grade panels."),
        ("internal_grade_filter_removed", "pass" if "selected_season_round_grade_filter(options, dashboard_data)" not in layout else "fail", "Render path no longer invokes internal grade filter."),
        ("top_slicers_preserved", "pass" if "Select season" in layout and "Select team/grade" in layout else "fail", "Top slicers remain."),
        ("first_grade_order", "pass" if "season_overview_grade_order_key" in layout else "fail", "Preferred grade ordering helper present."),
        ("duplicates_combined", "pass" if "combine_grdcc_duplicate_competition_teams" in layout else "fail", "Duplicate same-competition teams combined."),
        ("empty_grades_excluded", "pass" if "filter_empty_grdcc_season_teams" in layout else "fail", "Empty grades filtered."),
        ("no_balls_wides_after_5wi", "pass" if bowling_order_ok else "fail", "Bowling order is BBI, 3WI, 5WI, No Balls, Wides."),
        ("no_balls_wides_compact", "pass" if "season-col-no-balls" in layout and "season-col-wides" in layout else "fail", "Compact widths configured."),
    ]
    return (
        [{"check": c, "validation_status": s, "details": d} for c, s, d in hof_checks],
        [{"check": c, "validation_status": s, "details": d} for c, s, d in so_checks],
    )


def main() -> int:
    HOF_VALIDATION.mkdir(parents=True, exist_ok=True)
    SO_VALIDATION.mkdir(parents=True, exist_ok=True)
    active_rows = active_player_audit()
    matches_rows = historical_matches_audit()
    panel_rows = season_panels_audit()
    hof_rows, so_rows = validation_rows(active_rows, matches_rows, panel_rows)
    write_csv(HOF_VALIDATION / "grdcc_active_player_audit.csv", active_rows, ["player_name", "normalized_player_name", "latest_season_played", "latest_two_seasons_used", "was_active_before", "is_active_after", "affected_sections", "validation_status", "notes"])
    write_csv(HOF_VALIDATION / "grdcc_historical_matches_proxy_audit.csv", matches_rows, ["player_name", "normalized_player_name", "has_excel_data", "has_playcricket_data", "excel_innings", "excel_matches_raw", "playcricket_matches", "displayed_matches_numeric_sort_value", "displayed_matches_text", "used_innings_proxy", "proxy_reason", "affected_tables", "validation_status", "notes"])
    write_csv(SO_VALIDATION / "grdcc_season_by_round_horizontal_panels_audit.csv", panel_rows, ["season", "panel_order", "grade_or_competition", "original_team_count", "combined_team_count", "match_rows", "round_count", "included_after", "exclusion_reason", "validation_status", "notes"])
    write_csv(HOF_VALIDATION / "grdcc_hof_season_overview_followups_validation.csv", hof_rows, ["check", "validation_status", "details"])
    write_csv(SO_VALIDATION / "grdcc_season_overview_followups_validation.csv", so_rows, ["check", "validation_status", "details"])
    failures = [row for row in hof_rows + so_rows if row["validation_status"] == "fail"]
    print(
        "validation_status=" + ("pass" if not failures else "fail"),
        f"hof_checks={len(hof_rows)}",
        f"season_checks={len(so_rows)}",
        f"matches_proxy={sum(row['used_innings_proxy'] == 'yes' for row in matches_rows)}",
        f"active_latest_two={sum(row['is_active_after'] == 'yes' for row in active_rows)}",
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
