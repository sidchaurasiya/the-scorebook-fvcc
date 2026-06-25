#!/usr/bin/env python3
"""Summarize GRDCC PlayCricket and Historical Excel coverage by season."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLUB_DATA = ROOT / "clubs" / "georges-river-district" / "data"
PROCESSED = CLUB_DATA / "processed"
SUPPLEMENTAL = PROCESSED / "supplemental"
OUTPUT_DIR = PROCESSED / "validation" / "source_coverage"
DETAIL_PATH = OUTPUT_DIR / "grdcc_source_season_counts.csv"
SUMMARY_PATH = OUTPUT_DIR / "grdcc_source_season_counts_summary.csv"
DOC_PATH = ROOT / "docs" / "georges_river_source_season_counts_summary.md"

PLAYCRICKET = {
    "batting": PROCESSED / "all_seasons_batting.csv",
    "bowling": PROCESSED / "all_seasons_bowling.csv",
    "fielding": PROCESSED / "all_seasons_fielding.csv",
}
MATCH_CANDIDATES = [
    PROCESSED / "all_seasons_matches.csv",
    PROCESSED / "all_matches.csv",
    PROCESSED / "all_scorecards.csv",
]
EXCEL = {
    "batting": SUPPLEMENTAL / "excel_all_seasons_batting.csv",
    "bowling": SUPPLEMENTAL / "excel_all_seasons_bowling.csv",
}
EXCEL_WORKBOOK = CLUB_DATA / "source" / "bexley_stats_spreadsheets.xlsx"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    pc = {group: read_csv(path) for group, path in PLAYCRICKET.items()}
    excel = {group: read_csv(path) for group, path in EXCEL.items()}
    match_path, match_rows = first_reliable_match_file(MATCH_CANDIDATES)

    detail = build_detail_rows(pc, excel, match_path, match_rows)
    summary = build_summary(pc, excel, match_path, match_rows)
    markdown = build_markdown(detail, summary, match_path)

    write_csv(DETAIL_PATH, detail)
    write_csv(SUMMARY_PATH, summary)
    DOC_PATH.write_text(markdown, encoding="utf-8")

    values = {row["metric"]: row["value"] for row in summary}
    print(f"PlayCricket season count: {values['total_playcricket_seasons']}")
    print(f"Excel season count: {values['total_excel_seasons']}")
    print(f"Overlap season count: {values['overlap_seasons']}")
    print(f"PlayCricket players count: {values['playcricket_total_players']}")
    print(f"Excel players count: {values['excel_total_players']}")
    print(f"PlayCricket teams count: {values['playcricket_total_teams']}")
    print(f"Excel teams count: {values['excel_total_teams']}")
    print(f"PlayCricket matches count: {values['playcricket_total_matches']} (match-level available: {values['playcricket_match_count_available']})")
    print(f"Excel matches count: {values['excel_total_matches']} (match-level available: {values['excel_match_count_available']})")
    print("outputs:")
    for path in [DETAIL_PATH, SUMMARY_PATH, DOC_PATH]:
        print(f"- {path.relative_to(ROOT)}")
    return 0


def build_detail_rows(
    pc: dict[str, list[dict[str, str]]],
    excel: dict[str, list[dict[str, str]]],
    match_path: Path | None,
    match_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    output = []
    for source_system, groups, source_paths in (
        ("playcricket", pc, PLAYCRICKET),
        ("excel", excel, EXCEL),
    ):
        seasons = source_seasons(groups.values())
        if source_system == "playcricket":
            seasons |= {clean(row.get("season")) for row in match_rows if clean(row.get("season"))}
        for season in sorted(seasons, key=season_sort_key):
            batting = season_rows(groups.get("batting", []), season)
            bowling = season_rows(groups.get("bowling", []), season)
            fielding = season_rows(groups.get("fielding", []), season)
            matches = season_rows(match_rows, season) if source_system == "playcricket" else []
            all_stat_rows = batting + bowling + fielding
            team_labels = sorted(team_grade_labels(all_stat_rows) | team_grade_labels(matches), key=str.casefold)
            notes = []
            if source_system == "playcricket":
                if match_path is None:
                    notes.append("match-level file unavailable; exact matches not inferred from player-season rows")
                notes.append("team counts use distinct team and grade combinations")
            else:
                notes.append("Excel match count unavailable or incomplete; exact matches not inferred")
                notes.append("Excel team labels are generic historical club/grade values")
                notes.append("Excel has no app-facing fielding output")

            source_files = [path.name for group, path in source_paths.items() if season_rows(groups.get(group, []), season)]
            if source_system == "playcricket" and matches and match_path:
                source_files.append(match_path.name)
            if source_system == "excel" and EXCEL_WORKBOOK.exists():
                source_files.append(EXCEL_WORKBOOK.name)

            batting_players = player_keys(batting)
            bowling_players = player_keys(bowling)
            fielding_players = player_keys(fielding)
            output.append(
                {
                    "source_system": source_system,
                    "season": season,
                    "season_sort_key": season_sort_key(season),
                    "teams_count": len(team_labels),
                    "teams_list": "; ".join(team_labels),
                    "matches_count": len(unique_match_keys(matches)) if matches else 0,
                    "players_count": len(batting_players | bowling_players | fielding_players),
                    "batting_players_count": len(batting_players),
                    "bowling_players_count": len(bowling_players),
                    "fielding_players_count": len(fielding_players),
                    "batting_rows": len(batting),
                    "bowling_rows": len(bowling),
                    "fielding_rows": len(fielding),
                    "match_rows": len(matches),
                    "source_files_used": "; ".join(sorted(set(source_files))),
                    "data_quality_notes": "; ".join(notes),
                }
            )
    return sorted(output, key=lambda row: (season_sort_key(str(row["season"])), str(row["source_system"])))


def build_summary(
    pc: dict[str, list[dict[str, str]]],
    excel: dict[str, list[dict[str, str]]],
    match_path: Path | None,
    match_rows: list[dict[str, str]],
) -> list[dict[str, object]]:
    pc_seasons = source_seasons(pc.values()) | {clean(row.get("season")) for row in match_rows if clean(row.get("season"))}
    excel_seasons = source_seasons(excel.values())
    pc_players = source_player_keys(pc.values())
    excel_players = source_player_keys(excel.values())
    pc_names = source_normalized_names(pc.values())
    excel_names = source_normalized_names(excel.values())
    pc_teams = team_grade_labels([row for rows in pc.values() for row in rows] + match_rows)
    excel_teams = team_grade_labels([row for rows in excel.values() for row in rows])
    values = [
        ("total_playcricket_seasons", len(pc_seasons)),
        ("total_excel_seasons", len(excel_seasons)),
        ("playcricket_only_seasons", len(pc_seasons - excel_seasons)),
        ("excel_only_seasons", len(excel_seasons - pc_seasons)),
        ("overlap_seasons", len(pc_seasons & excel_seasons)),
        ("playcricket_total_players", len(pc_players)),
        ("excel_total_players", len(excel_players)),
        ("players_in_both_sources", len(pc_names & excel_names)),
        ("playcricket_total_teams", len(pc_teams)),
        ("excel_total_teams", len(excel_teams)),
        ("playcricket_total_matches", len(unique_match_keys(match_rows)) if match_path else 0),
        ("excel_total_matches", 0),
        ("playcricket_match_count_available", "yes" if match_path else "no"),
        ("excel_match_count_available", "no"),
        ("playcricket_batting_rows", len(pc["batting"])),
        ("playcricket_bowling_rows", len(pc["bowling"])),
        ("playcricket_fielding_rows", len(pc["fielding"])),
        ("excel_batting_rows", len(excel["batting"])),
        ("excel_bowling_rows", len(excel["bowling"])),
        ("seasons_with_playcricket_batting", len(source_seasons([pc["batting"]]))),
        ("seasons_with_playcricket_bowling", len(source_seasons([pc["bowling"]]))),
        ("seasons_with_playcricket_fielding", len(source_seasons([pc["fielding"]]))),
        ("seasons_with_excel_batting", len(source_seasons([excel["batting"]]))),
        ("seasons_with_excel_bowling", len(source_seasons([excel["bowling"]]))),
    ]
    return [{"metric": metric, "value": value} for metric, value in values]


def build_markdown(detail: list[dict[str, object]], summary: list[dict[str, object]], match_path: Path | None) -> str:
    value = {row["metric"]: row["value"] for row in summary}
    pc_rows = [row for row in detail if row["source_system"] == "playcricket"]
    excel_rows = [row for row in detail if row["source_system"] == "excel"]
    lines = [
        "# GRDCC Source Season Counts Summary",
        "",
        "## Purpose",
        "",
        "This report compares season-level coverage across GRDCC PlayCricket / PlayHQ processed data and the Historical Excel spreadsheet. Counts use source rows as supplied and do not merge or infer missing records.",
        "",
        "## Headline Counts",
        "",
        "| Source | Seasons | Players | Team/Grade Combinations | Matches | Batting Rows | Bowling Rows | Fielding Rows |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
        f"| PlayCricket / PlayHQ | {value['total_playcricket_seasons']} | {value['playcricket_total_players']} | {value['playcricket_total_teams']} | {match_display(value['playcricket_total_matches'], match_path is not None)} | {value['playcricket_batting_rows']} | {value['playcricket_bowling_rows']} | {value['playcricket_fielding_rows']} |",
        f"| Historical Excel | {value['total_excel_seasons']} | {value['excel_total_players']} | {value['excel_total_teams']} | Unavailable | {value['excel_batting_rows']} | {value['excel_bowling_rows']} | 0 |",
        "",
        "## Season-Level Coverage",
        "",
        f"- Excel-only seasons: {value['excel_only_seasons']}.",
        f"- PlayCricket-only seasons: {value['playcricket_only_seasons']}.",
        f"- Overlap seasons: {value['overlap_seasons']}.",
        f"- Seasons with Excel batting: {value['seasons_with_excel_batting']}; Excel bowling: {value['seasons_with_excel_bowling']}.",
        f"- Seasons with PlayCricket batting: {value['seasons_with_playcricket_batting']}; bowling: {value['seasons_with_playcricket_bowling']}; fielding: {value['seasons_with_playcricket_fielding']}.",
        f"- Season detail rows: {len(pc_rows)} PlayCricket and {len(excel_rows)} Excel.",
        "",
        "## Data Quality Notes",
        "",
        "- PlayCricket provides player-season aggregate batting, bowling and fielding rows.",
        "- The requested PlayCricket match-level candidates are absent or contain no data rows, so exact match counts are unavailable and are not inferred from player-season `matches` values.",
        "- Historical Excel has strong historical batting coverage and limited older-season bowling coverage.",
        "- Excel match counts are unavailable and are not inferred from player-season rows.",
        "- Excel team coverage uses a generic Georges River DCC / Historical club summary label; it should not be interpreted as a detailed team-grade history.",
        "- Player counts exclude blank, masked, numeric-only and other names without alphabetic characters.",
        "",
        "## How to Use",
        "",
        "- Use the season CSV to identify seasons present in only one source versus both sources.",
        "- Do not infer exact match counts from player-season aggregates.",
        "- Use the overlap discrepancy reports for player-season source-priority decisions.",
    ]
    return "\n".join(lines) + "\n"


def first_reliable_match_file(paths: list[Path]) -> tuple[Path | None, list[dict[str, str]]]:
    for path in paths:
        rows = read_csv(path)
        if rows and any(clean(row.get("season")) for row in rows):
            return path, rows
    return None, []


def team_grade_labels(rows: list[dict[str, str]]) -> set[str]:
    labels = set()
    for row in rows:
        team = first_value(row, ["team_name", "team", "club_team_name", "fvcc_team_name"])
        grade = first_value(row, ["grade_name", "grade", "competition", "competition_name"])
        if team and grade and normalize(team) != normalize(grade):
            labels.add(f"{team} | {grade}")
        elif team or grade:
            labels.add(team or grade)
    return labels


def player_keys(rows: list[dict[str, str]]) -> set[str]:
    keys = set()
    for row in rows:
        name = first_value(row, ["canonical_player_name", "player_name", "raw_player_name"])
        if not valid_player_name(name):
            continue
        canonical = clean(row.get("canonical_player_id"))
        keys.add(f"id:{canonical}" if canonical else f"name:{normalize(name)}")
    return keys


def source_player_keys(groups: object) -> set[str]:
    return set().union(*(player_keys(rows) for rows in groups))


def source_normalized_names(groups: object) -> set[str]:
    names = set()
    for rows in groups:
        for row in rows:
            name = first_value(row, ["canonical_player_name", "player_name", "raw_player_name"])
            if valid_player_name(name):
                names.add(normalize(name))
    return names


def valid_player_name(value: object) -> bool:
    name = clean(value)
    return bool(name and re.search(r"[A-Za-z]", name) and not set(name) <= {"*"} and not re.fullmatch(r"\d+", name))


def unique_match_keys(rows: list[dict[str, str]]) -> set[str]:
    keys = set()
    for index, row in enumerate(rows):
        match_id = first_value(row, ["match_id", "id", "matchId"])
        if match_id:
            keys.add(match_id)
        else:
            fallback = "|".join(first_value(row, [column]) for column in ["season", "date", "team", "opponent", "grade_name"])
            if fallback.strip("|"):
                keys.add(fallback)
            else:
                keys.add(f"row:{index}")
    return keys


def source_seasons(groups: object) -> set[str]:
    return {clean(row.get("season")) for rows in groups for row in rows if clean(row.get("season"))}


def season_rows(rows: list[dict[str, str]], season: str) -> list[dict[str, str]]:
    return [row for row in rows if clean(row.get("season")) == season]


def season_sort_key(value: str) -> int:
    match = re.search(r"(19|20)\d{2}", clean(value))
    return int(match.group()) if match else 999999


def first_value(row: dict[str, str], columns: list[str]) -> str:
    for column in columns:
        value = clean(row.get(column))
        if value:
            return value
    return ""


def normalize(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean(value).lower()).strip()


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def match_display(count: object, available: bool) -> str:
    return str(count) if available else "Unavailable"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0]) if rows else []
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
