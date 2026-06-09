#!/usr/bin/env python3
"""Ingest GRDCC historical Excel season summaries into club-scoped supplemental CSVs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = "bexley_stats_spreadsheets.xlsx"
NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest GRDCC historical Excel statistics.")
    parser.add_argument("--club", default="georges-river-district")
    parser.add_argument("--input", required=True, help="Club-scoped source workbook path.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = normalize_club_id(args.club)
    source_path = (ROOT / args.input).resolve() if not Path(args.input).is_absolute() else Path(args.input)
    if club_id != "georges-river-district":
        print(f"This importer is GRDCC-specific; got --club {club_id!r}.")
        return 2
    if not source_path.exists():
        print(f"Input workbook not found: {source_path}")
        return 2

    workbook = read_xlsx(source_path)
    audit = audit_workbook(workbook)
    rows = ingest_workbook(workbook, source_path.name)
    rows = validate_and_quarantine_rows(rows)
    output_dir = ROOT / "clubs" / club_id / "data" / "processed" / "supplemental"
    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = write_outputs(output_dir, rows, audit)

    print_summary(audit, rows, outputs)
    return 0


def normalize_club_id(value: object) -> str:
    return str(value or "").strip().casefold().replace(" ", "-")


def read_xlsx(path: Path) -> dict[str, list[list[object]]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        sheet_targets = read_sheet_targets(archive)
        workbook: dict[str, list[list[object]]] = {}
        for title, target in sheet_targets:
            rows = read_sheet_rows(archive, target, shared_strings)
            workbook[title] = rows
        return workbook


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall("main:si", NS):
        parts = [node.text or "" for node in item.findall(".//main:t", NS)]
        strings.append("".join(parts))
    return strings


def read_sheet_targets(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
    rels_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    rels = {rel.attrib["Id"]: rel.attrib["Target"] for rel in rels_root.findall("rel:Relationship", NS)}
    sheets = []
    for sheet in workbook_root.findall("main:sheets/main:sheet", NS):
        title = sheet.attrib["name"]
        rel_id = sheet.attrib["{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"]
        target = rels[rel_id]
        if not target.startswith("xl/"):
            target = f"xl/{target}"
        sheets.append((title, target))
    return sheets


def read_sheet_rows(archive: zipfile.ZipFile, target: str, shared_strings: list[str]) -> list[list[object]]:
    root = ET.fromstring(archive.read(target))
    rows: list[list[object]] = []
    for row in root.findall("main:sheetData/main:row", NS):
        values: list[object] = []
        for cell in row.findall("main:c", NS):
            index = column_index(cell.attrib.get("r", "A1"))
            while len(values) < index:
                values.append("")
            values.append(cell_value(cell, shared_strings))
        rows.append(values)
    return rows


def column_index(cell_ref: str) -> int:
    letters = re.sub(r"[^A-Z]", "", cell_ref.upper())
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return max(index, 1)


def cell_value(cell: ET.Element, shared_strings: list[str]) -> object:
    cell_type = cell.attrib.get("t", "")
    value = cell.find("main:v", NS)
    if value is None:
        inline = cell.find("main:is/main:t", NS)
        return clean_text(inline.text if inline is not None else "")
    raw = value.text or ""
    if cell_type == "s":
        try:
            return clean_text(shared_strings[int(float(raw))])
        except (ValueError, IndexError):
            return ""
    if cell_type in {"str", "inlineStr"}:
        return clean_text(raw)
    try:
        number = float(raw)
    except ValueError:
        return clean_text(raw)
    return int(number) if number.is_integer() else number


def audit_workbook(workbook: dict[str, list[list[object]]]) -> dict[str, object]:
    sheets = []
    seasons: set[str] = set()
    grades: set[str] = set()
    players: set[str] = set()
    duplicate_players: Counter[str] = Counter()
    issues: set[str] = set()
    for sheet_name, rows in workbook.items():
        nonblank_rows = [row for row in rows if any(clean_text(value) for value in row)]
        headers = detect_headers(rows)
        sheet_season = sheet_to_season(sheet_name)
        if sheet_season:
            seasons.add(sheet_season)
        sheet_grades = detect_grades(rows)
        grades.update(sheet_grades)
        sheet_players = detected_players(rows)
        players.update(sheet_players)
        duplicate_players.update(f"{sheet_name}:{name}" for name, count in Counter(sheet_players).items() if count > 1)
        if not headers:
            issues.add(f"{sheet_name}: no structured cricket headers detected")
        if any(blank_header_count(header) for header in headers):
            issues.add(f"{sheet_name}: blank spacer/header columns present")
        if has_total_rows(rows):
            issues.add(f"{sheet_name}: totals rows present")
        if sheet_name != "Intro" and not sheet_grades:
            issues.add(f"{sheet_name}: no explicit grade/team heading detected")
        sheets.append(
            {
                "sheet_name": sheet_name,
                "row_count": len(nonblank_rows),
                "max_columns": max((len(row) for row in nonblank_rows), default=0),
                "column_names": " | ".join(headers[0]) if headers else "",
                "detected_season": sheet_season,
                "detected_grades": ", ".join(sorted(sheet_grades)),
                "detected_players": len(set(sheet_players)),
                "contains_batting": any("batting" in [clean_text(value).casefold() for value in row] for row in rows) or any("PLAYER" in [clean_text(value).upper() for value in row] for row in rows),
                "contains_bowling": any("bowling" in [clean_text(value).casefold() for value in row] for row in rows) or any("Wkts" in [clean_text(value) for value in row] for row in rows),
                "contains_fielding": any(clean_text(value).casefold() in {"ct", "catches", "stumpings"} for row in rows for value in row),
                "contains_match_results": any("result" in clean_text(value).casefold() for row in rows for value in row),
                "contains_scorecards": False,
            }
        )
    return {
        "sheets": sheets,
        "seasons": sorted(seasons, key=season_sort_key),
        "grades": sorted(grades),
        "players": sorted(players),
        "issues": sorted(issues),
        "duplicate_player_sheet_entries": len(duplicate_players),
    }


def detect_headers(rows: list[list[object]]) -> list[list[str]]:
    headers = []
    for row in rows[:20]:
        cleaned = [clean_text(value) for value in row]
        upper = [value.upper() for value in cleaned]
        if {"FIRST NAME", "SURNAME"}.issubset(set(upper)) or "PLAYER" in upper:
            headers.append(cleaned)
    return headers


def blank_header_count(header: list[str]) -> int:
    return sum(1 for value in header if value == "")


def detect_grades(rows: list[list[object]]) -> set[str]:
    grades = set()
    for idx, row in enumerate(rows):
        first = clean_text(row[0] if row else "")
        if not first or first.casefold() in {"batting", "bowling"}:
            continue
        nonblank = [clean_text(value) for value in row if clean_text(value)]
        next_row = [clean_text(value).casefold() for value in rows[idx + 1]] if idx + 1 < len(rows) else []
        if len(nonblank) == 1 and ("batting" in next_row or "first name" in next_row or "player" in next_row):
            grades.add(first)
    return grades


def detected_players(rows: list[list[object]]) -> list[str]:
    players = []
    for idx, row in enumerate(rows):
        header = [clean_text(value).upper() for value in row]
        if {"FIRST NAME", "SURNAME"}.issubset(set(header)):
            first_idx = header.index("FIRST NAME")
            surname_idx = header.index("SURNAME")
            players.extend(early_player_names(rows[idx + 1 :], first_idx, surname_idx))
        elif "PLAYER" in header:
            player_idx = header.index("PLAYER")
            players.extend(late_player_names(rows[idx + 1 :], player_idx))
    return players


def early_player_names(rows: list[list[object]], first_idx: int, surname_idx: int) -> list[str]:
    names = []
    for row in rows:
        first = clean_text(value_at(row, first_idx))
        surname = clean_text(value_at(row, surname_idx))
        if is_section_break(row) or is_total_name(first, surname):
            continue
        name = display_name(" ".join(part for part in [first, surname] if part))
        if name:
            names.append(name)
    return names


def late_player_names(rows: list[list[object]], player_idx: int) -> list[str]:
    names = []
    for row in rows:
        name = display_name(clean_text(value_at(row, player_idx)))
        if not name or is_total_text(name):
            continue
        names.append(name)
    return names


def ingest_workbook(workbook: dict[str, list[list[object]]], source_file: str) -> dict[str, list[dict[str, object]]]:
    batting: list[dict[str, object]] = []
    bowling: list[dict[str, object]] = []
    summary: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    for sheet_name, rows in workbook.items():
        season = sheet_to_season(sheet_name)
        if not season:
            continue
        active_grade = ""
        for idx, row in enumerate(rows):
            row_number = idx + 1
            first_cell = clean_text(row[0] if row else "")
            if first_cell and len([value for value in row if clean_text(value)]) == 1 and first_cell.casefold() not in {"batting", "bowling"}:
                active_grade = first_cell
            header = [clean_text(value).upper() for value in row]
            if {"FIRST NAME", "SURNAME"}.issubset(set(header)):
                parsed = parse_early_table(rows[idx + 1 :], idx + 2, header, sheet_name, season, active_grade, source_file)
            elif "PLAYER" in header:
                parsed = parse_late_table(rows[idx + 1 :], idx + 2, header, sheet_name, season, active_grade, source_file)
            else:
                continue
            batting.extend(parsed["batting"])
            bowling.extend(parsed["bowling"])
            summary.extend(parsed["summary"])
            rejected.extend(parsed["rejected"])
    return {"batting": batting, "bowling": bowling, "summary": summary, "rejected": rejected}


def parse_early_table(
    rows: list[list[object]],
    start_row: int,
    header: list[str],
    sheet_name: str,
    season: str,
    grade: str,
    source_file: str,
) -> dict[str, list[dict[str, object]]]:
    indexes = {name: header.index(name) for name in header if name}
    out = {"batting": [], "bowling": [], "summary": [], "rejected": []}
    for offset, row in enumerate(rows):
        source_row = start_row + offset
        if is_next_table_start(row, rows[offset + 1] if offset + 1 < len(rows) else []):
            break
        if is_section_break(row):
            continue
        first = clean_text(value_at(row, indexes.get("FIRST NAME", -1)))
        surname = clean_text(value_at(row, indexes.get("SURNAME", -1)))
        if is_total_name(first, surname):
            continue
        player_name = display_name(" ".join(part for part in [first, surname] if part))
        if not player_name:
            continue
        common = common_row(player_name, sheet_name, source_row, season, grade, source_file)
        batting_row = {
            **common,
            "matches": value_at(row, indexes.get("GAMES", -1)),
            "battingInnings": value_at(row, indexes.get("INNS", -1)),
            "battingNotOuts": value_at(row, indexes.get("NO", -1)),
            "battingHighScore": high_score_runs(value_at(row, indexes.get("HS", -1))),
            "isBattingHSNotOut": high_score_not_out(value_at(row, indexes.get("HS", -1))),
            "battingAggregate": value_at(row, indexes.get("TOTAL", -1)),
            "battingAverage": value_at(row, indexes.get("AVE", -1)),
            "batting50s": "",
            "batting100s": "",
            "batting0s": "",
        }
        bowling_row = {
            **common,
            "matches": value_at(row, indexes.get("GAMES", -1)),
            "bowlingOvers": value_at(row, indexes.get("OVERS", -1)),
            "bowlingMaidens": value_at(row, indexes.get("MDNS", -1)),
            "bowlingRuns": value_at(row, 12),
            "bowlingWickets": value_at(row, 13),
            "bowlingAverage": value_at(row, 14),
            "bowlingBestInnings": "",
            "bowling5WIs": "",
        }
        if has_batting_value(batting_row):
            out["batting"].append(to_batting_processed_row(batting_row))
        if has_bowling_value(bowling_row):
            out["bowling"].append(to_bowling_processed_row(bowling_row))
        out["summary"].append({**common, **summary_values(batting_row, bowling_row)})
    return out


def parse_late_table(
    rows: list[list[object]],
    start_row: int,
    header: list[str],
    sheet_name: str,
    season: str,
    grade: str,
    source_file: str,
) -> dict[str, list[dict[str, object]]]:
    indexes = {name: idx for idx, name in enumerate(header) if name}
    out = {"batting": [], "bowling": [], "summary": [], "rejected": []}
    for offset, row in enumerate(rows):
        source_row = start_row + offset
        if is_next_table_start(row, rows[offset + 1] if offset + 1 < len(rows) else []):
            break
        if is_section_break(row):
            continue
        player_name = display_name(clean_text(value_at(row, indexes.get("PLAYER", -1))))
        if not player_name or is_total_text(player_name):
            continue
        common = common_row(player_name, sheet_name, source_row, season, grade, source_file)
        batting_row = {
            **common,
            "matches": value_at(row, indexes.get("MAT", -1)),
            "battingInnings": value_at(row, indexes.get("INN", -1)),
            "battingNotOuts": value_at(row, indexes.get("NO", -1)),
            "battingHighScore": high_score_runs(value_at(row, indexes.get("HS", -1))),
            "isBattingHSNotOut": high_score_not_out(value_at(row, indexes.get("HS", -1))),
            "battingAggregate": value_at(row, indexes.get("RUNS", -1)),
            "battingAverage": value_at(row, indexes.get("AVE.", indexes.get("AVE", -1))),
            "battingStrikeRate": value_at(row, indexes.get("STR.", indexes.get("STR", -1))),
            "battingFours": value_at(row, indexes.get("4S", -1)),
            "battingSixes": value_at(row, indexes.get("6S", -1)),
            "battingMinutes": value_at(row, indexes.get("MINS", -1)),
            "batting50s": value_at(row, indexes.get("50S", -1)),
            "batting100s": value_at(row, indexes.get("100S", -1)),
            "batting0s": value_at(row, indexes.get("0S", -1)),
        }
        if has_batting_value(batting_row):
            out["batting"].append(to_batting_processed_row(batting_row))
            out["summary"].append({**common, **summary_values(batting_row, {})})
    return out


def common_row(player_name: str, sheet: str, source_row: int, season: str, grade: str, source_file: str) -> dict[str, object]:
    player_id = "excel_" + hashlib.sha1(f"{player_name}|{season}".encode("utf-8")).hexdigest()[:16]
    return {
        "player_id": player_id,
        "player_name": player_name,
        "short_name": short_name(player_name),
        "club": "Georges River DCC",
        "team_name": "Georges River DCC",
        "grade_name": grade or "Historical club summary",
        "season_id": "excel_" + sheet.replace("-", "_"),
        "season": season,
        "season_start_date": season_start_date(season),
        "competition_name": "Historical Excel",
        "raw_player_id": player_id,
        "raw_player_name": player_name,
        "source_system": "excel",
        "source_file": source_file,
        "source_sheet": sheet,
        "source_row": source_row,
        "data_confidence": "medium",
    }


def to_batting_processed_row(row: dict[str, object]) -> dict[str, object]:
    output = {key: row.get(key, "") for key in BASE_CONTEXT_COLUMNS}
    output.update(
        {
            "matches": clean_number(row.get("matches")),
            "battingInnings": clean_number(row.get("battingInnings")),
            "battingAggregate": clean_number(row.get("battingAggregate")),
            "battingNotOuts": clean_number(row.get("battingNotOuts")),
            "battingBallsFaced": "",
            "batting50s": clean_number(row.get("batting50s")),
            "batting100s": clean_number(row.get("batting100s")),
            "batting0s": clean_number(row.get("batting0s")),
            "battingHighScore": clean_number(row.get("battingHighScore")),
            "isBattingHSNotOut": row.get("isBattingHSNotOut", False),
            "battingAverage": clean_number(row.get("battingAverage")),
            "battingStrikeRate": clean_number(row.get("battingStrikeRate")),
            "battingFours": clean_number(row.get("battingFours")),
            "battingSixes": clean_number(row.get("battingSixes")),
            "battingMinutes": clean_number(row.get("battingMinutes")),
            "team_id": "excel_georges_river_dcc",
            "grade_id": slug(row.get("grade_name")),
            "canonical_player_id": "",
            "canonical_player_name": "",
        }
    )
    return output


def to_bowling_processed_row(row: dict[str, object]) -> dict[str, object]:
    wickets = clean_number(row.get("bowlingWickets"))
    runs = clean_number(row.get("bowlingRuns"))
    overs = clean_number(row.get("bowlingOvers"))
    balls = overs_to_balls(overs)
    output = {key: row.get(key, "") for key in BASE_CONTEXT_COLUMNS}
    output.update(
        {
            "matches": clean_number(row.get("matches")),
            "bowlingWickets": wickets,
            "bowlingMaidens": clean_number(row.get("bowlingMaidens")),
            "bowlingRuns": runs,
            "bowlingBalls": balls,
            "bowling5WIs": clean_number(row.get("bowling5WIs")),
            "bowling10WMs": "",
            "bowlingBestInnings": clean_text(row.get("bowlingBestInnings")),
            "bowlingAverage": clean_number(row.get("bowlingAverage")),
            "bowlingStrikeRate": "",
            "bowlingEconomyRate": "",
            "bowlingWides": "",
            "bowlingNoBalls": "",
            "team_id": "excel_georges_river_dcc",
            "grade_id": slug(row.get("grade_name")),
            "bowlingWicketsUnassisted": "",
            "canonical_player_id": "",
            "canonical_player_name": "",
        }
    )
    return output


BASE_CONTEXT_COLUMNS = [
    "player_id",
    "player_name",
    "short_name",
    "club",
    "team_name",
    "grade_name",
    "season_id",
    "season",
    "season_start_date",
    "competition_name",
    "raw_player_id",
    "raw_player_name",
    "source_system",
    "source_file",
    "source_sheet",
    "source_row",
    "data_confidence",
]


def summary_values(batting: dict[str, object], bowling: dict[str, object]) -> dict[str, object]:
    return {
        "matches": clean_number(batting.get("matches") or bowling.get("matches")),
        "batting_innings": clean_number(batting.get("battingInnings")),
        "batting_runs": clean_number(batting.get("battingAggregate")),
        "batting_high_score": clean_number(batting.get("battingHighScore")),
        "batting_not_outs": clean_number(batting.get("battingNotOuts")),
        "batting_50s": clean_number(batting.get("batting50s")),
        "batting_100s": clean_number(batting.get("batting100s")),
        "bowling_overs": clean_number(bowling.get("bowlingOvers")),
        "bowling_runs": clean_number(bowling.get("bowlingRuns")),
        "bowling_wickets": clean_number(bowling.get("bowlingWickets")),
    }


def validate_and_quarantine_rows(rows: dict[str, list[dict[str, object]]]) -> dict[str, list[dict[str, object]]]:
    outliers: list[dict[str, object]] = []
    clean_batting: list[dict[str, object]] = []
    clean_bowling: list[dict[str, object]] = []

    for row in rows["batting"]:
        issues = validate_batting_row(row)
        outliers.extend(issues)
        if record_row_allowed(issues):
            clean_batting.append(row)
        else:
            row["data_confidence"] = "low"

    for row in rows["bowling"]:
        issues = validate_bowling_row(row)
        outliers.extend(issues)
        if record_row_allowed(issues):
            clean_bowling.append(row)
        else:
            row["data_confidence"] = "low"

    rows["batting"] = clean_batting
    rows["bowling"] = clean_bowling
    rows["outliers"] = outliers
    return rows


def record_row_allowed(issues: list[dict[str, object]]) -> bool:
    return not any(str(issue.get("action")) == "excluded_from_records" for issue in issues)


def validate_batting_row(row: dict[str, object]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    player = clean_text(row.get("player_name"))
    season = clean_text(row.get("season"))
    runs = number_or_none(row.get("battingAggregate"))
    innings = number_or_none(row.get("battingInnings"))
    not_outs = number_or_none(row.get("battingNotOuts"))
    high_score = number_or_none(row.get("battingHighScore"))
    average = number_or_none(row.get("battingAverage"))
    strike_rate = number_or_none(row.get("battingStrikeRate"))
    fifties = number_or_none(row.get("batting50s"))
    hundreds = number_or_none(row.get("batting100s"))
    ducks = number_or_none(row.get("batting0s"))

    if not player:
        issues.append(outlier(row, "batting", "player_name", "", "missing_required", "high", "Missing player name."))
    if is_masked_name(player):
        issues.append(outlier(row, "batting", "player_name", player, "missing_required", "high", "Masked player name cannot drive records."))
    if not season:
        issues.append(outlier(row, "batting", "season", "", "missing_required", "high", "Missing season."))
    for metric, value in [
        ("battingAggregate", runs),
        ("battingInnings", innings),
        ("battingNotOuts", not_outs),
        ("battingHighScore", high_score),
        ("battingAverage", average),
        ("battingStrikeRate", strike_rate),
        ("batting50s", fifties),
        ("batting100s", hundreds),
        ("batting0s", ducks),
    ]:
        if value is not None and value < 0:
            issues.append(outlier(row, "batting", metric, value, "invalid", "high", "Negative values are invalid."))
    if runs is not None and runs > 1500:
        issues.append(outlier(row, "batting", "battingAggregate", runs, "suspicious", "medium", "Season runs above 1500 need manual review."))
    if innings is not None and innings > 40:
        issues.append(outlier(row, "batting", "battingInnings", innings, "suspicious", "medium", "Season innings above 40 need manual review."))
    if average is not None and average > 250:
        issues.append(outlier(row, "batting", "battingAverage", average, "suspicious", "medium", "Batting average above 250 needs manual review."))
    if strike_rate is not None and strike_rate > 300:
        issues.append(outlier(row, "batting", "battingStrikeRate", strike_rate, "suspicious", "medium", "Strike rate above 300 from Excel needs manual review."))
    for metric, value in [("batting100s", hundreds), ("batting50s", fifties), ("batting0s", ducks)]:
        if value is not None and innings is not None and value > innings:
            issues.append(outlier(row, "batting", metric, value, "invalid", "high", f"{metric} cannot exceed innings."))
    if high_score is not None and runs is not None and high_score > runs:
        issues.append(outlier(row, "batting", "battingHighScore", high_score, "invalid", "high", "High score cannot exceed aggregate runs."))
    if innings is not None and not_outs is not None and not_outs > innings:
        issues.append(outlier(row, "batting", "battingNotOuts", not_outs, "invalid", "high", "Not-outs cannot exceed innings."))
    return issues


def validate_bowling_row(row: dict[str, object]) -> list[dict[str, object]]:
    issues: list[dict[str, object]] = []
    player = clean_text(row.get("player_name"))
    season = clean_text(row.get("season"))
    matches = number_or_none(row.get("matches"))
    wickets = number_or_none(row.get("bowlingWickets"))
    runs = number_or_none(row.get("bowlingRuns"))
    balls = number_or_none(row.get("bowlingBalls"))
    maidens = number_or_none(row.get("bowlingMaidens"))
    five_wickets = number_or_none(row.get("bowling5WIs"))
    ten_wickets = number_or_none(row.get("bowling10WMs"))
    average = number_or_none(row.get("bowlingAverage"))
    strike_rate = number_or_none(row.get("bowlingStrikeRate"))
    economy = number_or_none(row.get("bowlingEconomyRate"))
    if economy is None and runs is not None and balls and balls > 0:
        economy = runs * 6 / balls
    if strike_rate is None and wickets and wickets > 0 and balls is not None:
        strike_rate = balls / wickets

    if not player:
        issues.append(outlier(row, "bowling", "player_name", "", "missing_required", "high", "Missing player name."))
    if is_masked_name(player):
        issues.append(outlier(row, "bowling", "player_name", player, "missing_required", "high", "Masked player name cannot drive records."))
    if not season:
        issues.append(outlier(row, "bowling", "season", "", "missing_required", "high", "Missing season."))
    for metric, value in [
        ("matches", matches),
        ("bowlingWickets", wickets),
        ("bowlingRuns", runs),
        ("bowlingBalls", balls),
        ("bowlingMaidens", maidens),
        ("bowling5WIs", five_wickets),
        ("bowling10WMs", ten_wickets),
        ("bowlingAverage", average),
        ("bowlingStrikeRate", strike_rate),
        ("bowlingEconomyRate", economy),
    ]:
        if value is not None and value < 0:
            issues.append(outlier(row, "bowling", metric, value, "invalid", "high", "Negative values are invalid."))
    if wickets is not None and wickets > 100:
        issues.append(outlier(row, "bowling", "bowlingWickets", wickets, "suspicious", "medium", "Season wickets above 100 need manual review."))
    if wickets is not None and balls is not None and wickets > balls:
        issues.append(outlier(row, "bowling", "bowlingWickets", wickets, "invalid", "high", "Wickets cannot exceed balls bowled."))
    if wickets is not None and wickets > 0 and matches is not None and matches <= 0:
        issues.append(outlier(row, "bowling", "matches", matches, "invalid", "high", "Wickets with zero matches is invalid."))
    if wickets is not None and wickets > 0 and balls is not None and balls <= 0:
        issues.append(outlier(row, "bowling", "bowlingBalls", balls, "invalid", "high", "Wickets with zero balls/overs is invalid."))
    if wickets is not None and matches is not None and matches > 0 and wickets > 10 * matches:
        issues.append(outlier(row, "bowling", "bowlingWickets", wickets, "suspicious", "medium", "Wickets exceed 10 per recorded match."))
    if economy is not None and (economy < 0.5 or economy > 15):
        issues.append(outlier(row, "bowling", "bowlingEconomyRate", round(economy, 4), "suspicious", "medium", "Season economy outside 0.5-15 needs manual review."))
    if average is not None and average == 0 and wickets and wickets > 0 and runs and runs > 0:
        issues.append(outlier(row, "bowling", "bowlingAverage", average, "suspicious", "medium", "Bowling average zero with wickets and runs conceded is suspicious."))
    if strike_rate is not None and (strike_rate < 3 or strike_rate > 300):
        issues.append(outlier(row, "bowling", "bowlingStrikeRate", round(strike_rate, 4), "suspicious", "medium", "Bowling strike rate outside 3-300 needs manual review."))
    for metric, value in [("bowling5WIs", five_wickets), ("bowling10WMs", ten_wickets)]:
        if value is not None and matches is not None and value > matches:
            issues.append(outlier(row, "bowling", metric, value, "invalid", "high", f"{metric} cannot exceed matches."))
    if runs is not None and runs >= 900:
        issues.append(
            outlier(
                row,
                "bowling",
                "legacy_misaligned_bowling_wickets_candidate",
                runs,
                "format_issue",
                "high",
                "Very high early-workbook runs value was previously at risk of being misread as wickets; exclude from headline records pending manual review.",
            )
        )
    return issues


def outlier(
    row: dict[str, object],
    metric_group: str,
    metric_name: str,
    metric_value: object,
    issue_type: str,
    severity: str,
    reason: str,
) -> dict[str, object]:
    action = "accepted_with_warning" if severity == "low" else "excluded_from_records"
    if severity == "medium":
        action = "excluded_from_records"
    return {
        "source_file": row.get("source_file", SOURCE_FILE),
        "source_sheet": row.get("source_sheet", ""),
        "source_row": row.get("source_row", ""),
        "player_name": row.get("player_name", ""),
        "season": row.get("season", ""),
        "team_or_grade": row.get("grade_name") or row.get("team_name", ""),
        "metric_group": metric_group,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "issue_type": issue_type,
        "severity": severity,
        "reason": reason,
        "action": action,
        "data_confidence": "low" if action == "excluded_from_records" else row.get("data_confidence", "medium"),
    }


def write_outputs(output_dir: Path, rows: dict[str, list[dict[str, object]]], audit: dict[str, object]) -> list[Path]:
    outputs = []
    for filename, key in [
        ("excel_all_seasons_batting.csv", "batting"),
        ("excel_all_seasons_bowling.csv", "bowling"),
        ("excel_player_season_summary.csv", "summary"),
        ("excel_rejected_rows.csv", "rejected"),
        ("excel_outlier_audit.csv", "outliers"),
    ]:
        path = output_dir / filename
        write_csv(path, rows[key])
        outputs.append(path)
    summary_rows = [
        {
            "metric": "sheets_processed",
            "value": len(audit["sheets"]),
        },
        {"metric": "rows_read", "value": sum(int(sheet["row_count"]) for sheet in audit["sheets"])},
        {"metric": "rows_accepted", "value": len(rows["summary"])},
        {"metric": "rows_rejected", "value": len(rows["rejected"])},
        {"metric": "rows_flagged", "value": len(rows.get("outliers", []))},
        {
            "metric": "rows_excluded_from_records",
            "value": len({(row.get("source_sheet"), row.get("source_row"), row.get("metric_group")) for row in rows.get("outliers", []) if row.get("action") == "excluded_from_records"}),
        },
        {"metric": "seasons_detected", "value": len(audit["seasons"])},
        {"metric": "players_detected", "value": len(audit["players"])},
    ]
    path = output_dir / "excel_ingestion_summary.csv"
    write_csv(path, summary_rows)
    outputs.append(path)
    path = output_dir / "excel_workbook_sheet_audit.csv"
    write_csv(path, audit["sheets"])
    outputs.append(path)
    return outputs


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames or ["empty"])
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def print_summary(audit: dict[str, object], rows: dict[str, list[dict[str, object]]], outputs: list[Path]) -> None:
    print(f"sheets processed: {len(audit['sheets'])}")
    print(f"rows read: {sum(int(sheet['row_count']) for sheet in audit['sheets'])}")
    print(f"rows accepted: {len(rows['summary'])}")
    print(f"rows rejected: {len(rows['rejected'])}")
    print(f"rows flagged: {len(rows.get('outliers', []))}")
    print(
        "rows excluded from records: "
        f"{len({(row.get('source_sheet'), row.get('source_row'), row.get('metric_group')) for row in rows.get('outliers', []) if row.get('action') == 'excluded_from_records'})}"
    )
    print(f"seasons detected: {', '.join(audit['seasons'])}")
    print(f"players detected: {len(audit['players'])}")
    print("outputs written:")
    for path in outputs:
        print(f"- {path.relative_to(ROOT)}")


def value_at(row: list[object], index: int) -> object:
    return row[index] if index >= 0 and index < len(row) else ""


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clean_number(value: object) -> object:
    if value in (None, ""):
        return ""
    text = clean_text(value).replace(",", "")
    if text.upper() == "NA":
        return ""
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return ""
    number = float(match.group())
    return int(number) if number.is_integer() else number


def number_or_none(value: object) -> float | None:
    number = clean_number(value)
    return None if number == "" else float(number)


def high_score_runs(value: object) -> object:
    return clean_number(value)


def high_score_not_out(value: object) -> bool:
    return "*" in clean_text(value) or "NO" in clean_text(value).upper()


def has_batting_value(row: dict[str, object]) -> bool:
    return any(clean_number(row.get(key)) != "" for key in ["battingInnings", "battingAggregate", "battingHighScore"])


def has_bowling_value(row: dict[str, object]) -> bool:
    return any(clean_number(row.get(key)) != "" for key in ["bowlingOvers", "bowlingRuns", "bowlingWickets"])


def is_section_break(row: list[object]) -> bool:
    values = [clean_text(value).casefold() for value in row if clean_text(value)]
    return values in (["batting"], ["bowling"]) or "first name" in values or "player" in values


def is_next_table_start(row: list[object], next_row: list[object]) -> bool:
    values = [clean_text(value) for value in row if clean_text(value)]
    lowered = [value.casefold() for value in values]
    if "first name" in lowered or "player" in lowered:
        return True
    next_lowered = [clean_text(value).casefold() for value in next_row if clean_text(value)]
    return len(values) == 1 and any(value in next_lowered for value in ("batting", "first name", "player"))


def is_total_name(first: str, surname: str) -> bool:
    return is_total_text(first) or is_total_text(surname)


def is_total_text(value: object) -> bool:
    text = clean_text(value).casefold()
    return text in {"total", "totals", "team total", "grand total"} or text.startswith("total ")


def is_masked_name(value: object) -> bool:
    text = clean_text(value)
    return bool(text) and set(text) <= {"*"}


def has_total_rows(rows: list[list[object]]) -> bool:
    return any(any(is_total_text(value) for value in row) for row in rows)


def display_name(value: str) -> str:
    value = clean_text(value)
    if "," in value:
        surname, given = [part.strip() for part in value.split(",", 1)]
        value = f"{given} {surname}".strip()
    return " ".join(part[:1].upper() + part[1:].lower() if part else "" for part in value.split())


def short_name(player_name: str) -> str:
    parts = player_name.split()
    if len(parts) <= 1:
        return player_name
    return f"{parts[0][0]} {' '.join(parts[1:])}"


def slug(value: object) -> str:
    text = clean_text(value).casefold()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return f"excel_{text or 'unknown'}"


def sheet_to_season(sheet_name: str) -> str:
    match = re.fullmatch(r"(\d{4})-(\d{2})", sheet_name.strip())
    if not match:
        return ""
    start = int(match.group(1))
    return f"Summer {start}/{match.group(2)}"


def season_start_date(season: str) -> str:
    match = re.search(r"(\d{4})", season)
    return f"{match.group(1)}-07-01T00:00:00.0000000+00:00" if match else ""


def season_sort_key(season: str) -> int:
    match = re.search(r"(\d{4})", season)
    return int(match.group(1)) if match else 9999


def overs_to_balls(value: object) -> object:
    text = clean_text(value)
    if not text:
        return ""
    if "." in text:
        overs, balls = text.split(".", 1)
        try:
            return int(float(overs)) * 6 + int(float(balls))
        except ValueError:
            return ""
    number = clean_number(text)
    return int(number) * 6 if number != "" else ""


if __name__ == "__main__":
    raise SystemExit(main())
