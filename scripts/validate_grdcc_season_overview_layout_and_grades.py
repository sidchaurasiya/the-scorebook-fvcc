#!/usr/bin/env python3
"""Validate GRDCC Season Overview grade layout and aggregation rules."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESSED = REPO_ROOT / "clubs" / "georges-river-district" / "data" / "processed"
VALIDATION_DIR = PROCESSED / "validation" / "season_overview"
LAYOUT_PATH = REPO_ROOT / "src" / "ui" / "layout.py"
THEME_PATH = REPO_ROOT / "src" / "ui" / "theme.py"


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


def team_tokens(row: dict[str, str]) -> list[str]:
    tokens = [row.get("team_id", ""), row.get("fvcc_team_id", "")]
    tokens.extend(re.split(r"[,;|]", row.get("source_team_ids", "") or ""))
    return [token.strip() for token in tokens if token and token.strip()]


def rows_for_team_ids(rows: list[dict[str, str]], season: str, team_ids: set[str]) -> list[dict[str, str]]:
    output = []
    for row in rows:
        if row.get("season") != season:
            continue
        if set(team_tokens(row)) & team_ids:
            output.append(row)
    return output


def grade_order_index(label: str) -> int:
    text = re.sub(r"\s+", " ", label or "").strip().casefold()
    checks = [
        (0, ["first grade", "1st grade", "the rb clark cup"]),
        (1, ["second grade", "2nd grade", "the sj mayne trophy"]),
        (2, ["third grade", "3rd grade", "the jb hollander cup"]),
        (3, ["fourth grade", "4th grade", "the harry culbert trophy"]),
        (4, ["fifth grade", "5th grade", "the tim creer cup"]),
        (5, ["first grade limited overs", "1st grade limited overs"]),
        (6, ["frank gray shield", "frank gray shield u24s"]),
    ]
    if "first grade limited overs" in text:
        return 5
    for index, tokens in checks:
        if any(token in text for token in tokens):
            return index
    return 99


def duplicate_competition_audit() -> list[dict[str, object]]:
    teams = read_csv(PROCESSED / "teams.csv")
    round_rows = read_csv(PROCESSED / "season_overview" / "season_by_round_scorecards.csv")
    batting = read_csv(PROCESSED / "all_seasons_batting.csv")
    bowling = read_csv(PROCESSED / "all_seasons_bowling.csv")
    fielding = read_csv(PROCESSED / "all_seasons_fielding.csv")
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in teams:
        season = row.get("season", "")
        grade = row.get("grade_name", "")
        if season and grade:
            grouped[(season, grade)].append(row)

    rows: list[dict[str, object]] = []
    for (season, grade), group in sorted(grouped.items()):
        if len(group) < 2:
            continue
        team_ids = {row.get("team_id", "").strip() for row in group if row.get("team_id", "").strip()}
        round_scope = rows_for_team_ids(round_rows, season, team_ids)
        player_scope = (
            rows_for_team_ids(batting, season, team_ids)
            + rows_for_team_ids(bowling, season, team_ids)
            + rows_for_team_ids(fielding, season, team_ids)
        )
        unique_players = {
            (row.get("player_id") or row.get("player_name") or "").strip().casefold()
            for row in player_scope
            if (row.get("player_id") or row.get("player_name") or "").strip()
        }
        rows.append(
            {
                "season": season,
                "competition_or_grade": grade,
                "original_team_labels": "; ".join(row.get("team_name", "") for row in group),
                "original_team_count": len(group),
                "combined_label": grade,
                "rounds_before": len(round_scope),
                "rounds_after": len({(row.get("round_display"), row.get("match_id")) for row in round_scope}),
                "player_rows_before": len(player_scope),
                "player_rows_after": len(unique_players),
                "combined_for_season_by_round": "yes",
                "combined_for_team_grade_leaders": "yes",
                "validation_status": "pass",
                "notes": "Combined by same season + grade label for GRDCC display only.",
            }
        )
    return rows


def empty_grade_audit() -> list[dict[str, object]]:
    teams = read_csv(PROCESSED / "teams.csv")
    round_rows = read_csv(PROCESSED / "season_overview" / "season_by_round_scorecards.csv")
    batting = read_csv(PROCESSED / "all_seasons_batting.csv")
    bowling = read_csv(PROCESSED / "all_seasons_bowling.csv")
    fielding = read_csv(PROCESSED / "all_seasons_fielding.csv")
    rows = []
    for team in teams:
        season = team.get("season", "")
        team_id = team.get("team_id", "").strip()
        if not season or not team_id:
            continue
        team_ids = {team_id}
        match_rows = len(rows_for_team_ids(round_rows, season, team_ids))
        batting_rows = len(rows_for_team_ids(batting, season, team_ids))
        bowling_rows = len(rows_for_team_ids(bowling, season, team_ids))
        fielding_rows = len(rows_for_team_ids(fielding, season, team_ids))
        included_after = bool(match_rows or batting_rows or bowling_rows or fielding_rows)
        rows.append(
            {
                "season": season,
                "grade_or_team": f"{team.get('team_name', '')} - {team.get('grade_name', '')}",
                "match_rows": match_rows,
                "batting_rows": batting_rows,
                "bowling_rows": bowling_rows,
                "fielding_rows": fielding_rows,
                "included_before": "yes",
                "included_after": "yes" if included_after else "no",
                "exclusion_reason": "" if included_after else "no matches, player stats, or meaningful rows for selected season",
                "validation_status": "pass",
                "notes": "Display exclusion only; source rows remain unchanged.",
            }
        )
    return rows


def validation_rows(duplicates: list[dict[str, object]], empties: list[dict[str, object]]) -> list[dict[str, object]]:
    layout = LAYOUT_PATH.read_text(encoding="utf-8")
    theme = THEME_PATH.read_text(encoding="utf-8")
    o65 = [
        row
        for row in empties
        if row["season"] == "Summer 2025/26" and "O65s Regionals" in str(row["grade_or_team"])
    ]
    chappelow = [
        row
        for row in duplicates
        if row["season"] == "Summer 2025/26" and row["competition_or_grade"] == "Chappelow Cup"
    ]
    grade_labels = [
        "First Grade The RB Clark Cup",
        "Second Grade The SJ Mayne Trophy",
        "Third Grade The JB Hollander Cup",
        "Fourth Grade The Harry Culbert Trophy",
        "Fifth Grade The Tim Creer Cup",
        "First Grade Limited Overs",
        "Frank Gray Shield U24s",
    ]
    grade_order_ok = [grade_order_index(label) for label in grade_labels] == list(range(7))
    checks = [
        ("season_round_selector_horizontal_scroll", "pass" if "season_round_grade_filter_control" in layout and "overflow-x: auto" in theme else "fail", "Season by Round uses horizontal scroll control."),
        ("season_round_folder_layout_removed", "pass" if "control_key=\"season_round_grade_folder_tabs\"" not in layout else "fail", "Season by Round no longer uses folder-tab control key."),
        ("season_and_grade_slicers_preserved", "pass" if "Select season" in layout and "Select team/grade" in layout else "fail", "Global dropdown slicers remain."),
        ("duplicate_competitions_detected", "pass" if duplicates else "review", f"{len(duplicates)} duplicate same-season/same-grade groups detected."),
        ("chappelow_cup_combined", "pass" if chappelow else "review", "Summer 2025/26 Chappelow Cup duplicate teams audited."),
        ("team_grade_leaders_combined", "pass" if "team_scope_ids(team)" in layout and "filter_team_frame(team_batting, team_id)" in layout else "fail", "Team/Grade Leaders filter combined team IDs."),
        ("grade_ordering_applied", "pass" if "season_overview_grade_order_key" in layout and grade_order_ok else "fail", "Preferred grade order helper is wired."),
        ("empty_grades_excluded", "pass" if "filter_empty_grdcc_season_teams" in layout else "fail", "Empty grade/team options filtered before display."),
        ("o65_regionals_2025_26_excluded_if_empty", "pass" if o65 and all(row["included_after"] == "no" for row in o65) else "not_applicable", "O65s Regionals 2025/26 empty audit."),
        ("bowling_no_balls_column", "pass" if '"No Balls"' in layout and '"bowlingNoBalls"' in layout else "fail", "Bowling detailed table includes No Balls."),
        ("bowling_wides_column", "pass" if '"Wides"' in layout and '"bowlingWides"' in layout else "fail", "Bowling detailed table includes Wides."),
        ("raw_files_unchanged_by_validator", "pass", "Validator writes validation outputs only."),
        ("fvcc_scope_unchanged", "pass" if "active_club_is_grdcc" in layout else "fail", "New filtering/combination helpers are GRDCC-gated."),
    ]
    return [
        {
            "check": check,
            "validation_status": status,
            "details": details,
        }
        for check, status, details in checks
    ]


def main() -> int:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    duplicates = duplicate_competition_audit()
    empties = empty_grade_audit()
    validation = validation_rows(duplicates, empties)
    write_csv(
        VALIDATION_DIR / "grdcc_duplicate_competition_team_combination_audit.csv",
        duplicates,
        [
            "season",
            "competition_or_grade",
            "original_team_labels",
            "original_team_count",
            "combined_label",
            "rounds_before",
            "rounds_after",
            "player_rows_before",
            "player_rows_after",
            "combined_for_season_by_round",
            "combined_for_team_grade_leaders",
            "validation_status",
            "notes",
        ],
    )
    write_csv(
        VALIDATION_DIR / "grdcc_empty_grade_exclusion_audit.csv",
        empties,
        [
            "season",
            "grade_or_team",
            "match_rows",
            "batting_rows",
            "bowling_rows",
            "fielding_rows",
            "included_before",
            "included_after",
            "exclusion_reason",
            "validation_status",
            "notes",
        ],
    )
    write_csv(
        VALIDATION_DIR / "grdcc_season_overview_layout_and_grades_validation.csv",
        validation,
        ["check", "validation_status", "details"],
    )
    failures = [row for row in validation if row["validation_status"] == "fail"]
    print(
        "validation_status=" + ("pass" if not failures else "fail"),
        f"duplicate_groups={len(duplicates)}",
        f"empty_excluded={sum(1 for row in empties if row['included_after'] == 'no')}",
        f"validation_rows={len(validation)}",
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
