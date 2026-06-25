#!/usr/bin/env python3
"""Export GRDCC Excel player-season review CSVs for manual visual inspection."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SUPPLEMENTAL_DIR = ROOT / "clubs" / "georges-river-district" / "data" / "processed" / "supplemental"
EXPORT_DIR = SUPPLEMENTAL_DIR / "review_exports"
BATTING_INPUT = SUPPLEMENTAL_DIR / "excel_all_seasons_batting.csv"
BOWLING_INPUT = SUPPLEMENTAL_DIR / "excel_all_seasons_bowling.csv"
BATTING_OUTPUT = EXPORT_DIR / "grdcc_excel_batting_player_season_review.csv"
BOWLING_OUTPUT = EXPORT_DIR / "grdcc_excel_bowling_player_season_review.csv"

BATTING_COLUMNS = [
    "season",
    "season_sort_key",
    "player_name",
    "team",
    "grade",
    "matches",
    "innings",
    "not_outs",
    "runs",
    "high_score",
    "average",
    "strike_rate",
    "30s",
    "50s",
    "100s",
    "ducks",
    "fours",
    "sixes",
    "source_sheet",
    "source_row",
    "source_file",
    "source_system",
    "data_confidence",
    "qa_status",
]

BOWLING_COLUMNS = [
    "season",
    "season_sort_key",
    "player_name",
    "team",
    "grade",
    "matches",
    "overs",
    "balls",
    "maidens",
    "bowling_runs_conceded",
    "wickets",
    "average",
    "strike_rate",
    "economy",
    "best_bowling",
    "3wi",
    "5wi",
    "10wm",
    "source_sheet",
    "source_row",
    "source_file",
    "source_system",
    "data_confidence",
    "qa_status",
]


def main() -> int:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    batting_source = read_csv(BATTING_INPUT)
    bowling_source = read_csv(BOWLING_INPUT)

    batting_rows, batting_missing = export_rows(batting_source, batting_mapping(), BATTING_COLUMNS)
    bowling_rows, bowling_missing = export_rows(bowling_source, bowling_mapping(), BOWLING_COLUMNS)

    write_csv(BATTING_OUTPUT, batting_rows, BATTING_COLUMNS)
    write_csv(BOWLING_OUTPUT, bowling_rows, BOWLING_COLUMNS)

    batting_failures = validate_batting(batting_rows)
    bowling_failures = validate_bowling(bowling_rows)
    h_jolly_result = h_jolly_check(bowling_rows)
    failures = batting_failures + bowling_failures + h_jolly_result["failures"]

    print_summary("batting", BATTING_OUTPUT, batting_rows, batting_missing)
    print_summary("bowling", BOWLING_OUTPUT, bowling_rows, bowling_missing)
    print(f"numeric-only player names in exported batting: {count_numeric_only_names(batting_rows)}")
    print(f"numeric-only player names in exported bowling: {count_numeric_only_names(bowling_rows)}")
    print(f"masked/blank player names in exported batting: {count_masked_or_blank_names(batting_rows)}")
    print(f"masked/blank player names in exported bowling: {count_masked_or_blank_names(bowling_rows)}")
    print(f"H Jolly Summer 1944/45 bowling check: {h_jolly_result['message']}")
    print(f"validation failures: {len(failures)}")
    for failure in failures:
        print(f"- {failure}")
    return 1 if failures else 0


def batting_mapping() -> dict[str, str]:
    return {
        "season": "season",
        "player_name": "player_name",
        "team": "team_name",
        "grade": "grade_name",
        "matches": "matches",
        "innings": "battingInnings",
        "not_outs": "battingNotOuts",
        "runs": "battingAggregate",
        "high_score": "battingHighScore",
        "average": "battingAverage",
        "strike_rate": "battingStrikeRate",
        "50s": "batting50s",
        "100s": "batting100s",
        "ducks": "batting0s",
        "fours": "battingFours",
        "sixes": "battingSixes",
        "source_sheet": "source_sheet",
        "source_row": "source_row",
        "source_file": "source_file",
        "source_system": "source_system",
        "data_confidence": "data_confidence",
    }


def bowling_mapping() -> dict[str, str]:
    return {
        "season": "season",
        "player_name": "player_name",
        "team": "team_name",
        "grade": "grade_name",
        "matches": "matches",
        "balls": "bowlingBalls",
        "maidens": "bowlingMaidens",
        "bowling_runs_conceded": "bowlingRuns",
        "wickets": "bowlingWickets",
        "average": "bowlingAverage",
        "strike_rate": "bowlingStrikeRate",
        "economy": "bowlingEconomyRate",
        "best_bowling": "bowlingBestInnings",
        "5wi": "bowling5WIs",
        "10wm": "bowling10WMs",
        "source_sheet": "source_sheet",
        "source_row": "source_row",
        "source_file": "source_file",
        "source_system": "source_system",
        "data_confidence": "data_confidence",
    }


def export_rows(source_rows: list[dict[str, str]], mapping: dict[str, str], columns: list[str]) -> tuple[list[dict[str, str]], set[str]]:
    source_columns = set(source_rows[0]) if source_rows else set()
    missing = {source for source in mapping.values() if source and source not in source_columns}
    output: list[dict[str, str]] = []
    for source_row in source_rows:
        row = {column: "" for column in columns}
        for target, source in mapping.items():
            row[target] = clean_text(source_row.get(source, ""))
        row["season_sort_key"] = str(season_sort_key(row["season"]))
        row["qa_status"] = row["qa_status"] or "clean"
        if "overs" in row:
            row["overs"] = balls_to_overs(row.get("balls", ""))
        output.append(row)
    output.sort(key=lambda row: (int(row["season_sort_key"]), clean_text(row.get("player_name")).casefold()))
    return output, missing


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing source CSV: {path}")
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def print_summary(label: str, path: Path, rows: list[dict[str, str]], missing: set[str]) -> None:
    print(f"{label} review CSV: {path.relative_to(ROOT)}")
    print(f"{label} row count: {len(rows)}")
    print(f"{label} unique seasons: {len({row.get('season') for row in rows if row.get('season')})}")
    print(f"{label} unique players: {len({row.get('player_name') for row in rows if row.get('player_name')})}")
    print(f"{label} missing source fields: {', '.join(sorted(missing)) if missing else 'none'}")
    print(f"{label} first 10 rows:")
    print_rows(rows[:10])
    print(f"{label} last 10 rows:")
    print_rows(rows[-10:])


def print_rows(rows: list[dict[str, str]]) -> None:
    for row in rows:
        print({key: row.get(key, "") for key in row})


def validate_batting(rows: list[dict[str, str]]) -> list[str]:
    failures = common_name_failures(rows, "batting")
    for idx, row in enumerate(rows, start=2):
        innings = number_or_none(row.get("innings"))
        fifties = number_or_none(row.get("50s"))
        hundreds = number_or_none(row.get("100s"))
        high_score = number_or_none(row.get("high_score"))
        runs = number_or_none(row.get("runs"))
        if innings is not None and hundreds is not None and hundreds > innings:
            failures.append(f"batting:{idx} 100s > innings")
        if innings is not None and fifties is not None and fifties > innings:
            failures.append(f"batting:{idx} 50s > innings")
        if runs is not None and high_score is not None and high_score > runs:
            failures.append(f"batting:{idx} high_score > runs")
    return failures


def validate_bowling(rows: list[dict[str, str]]) -> list[str]:
    failures = common_name_failures(rows, "bowling")
    for idx, row in enumerate(rows, start=2):
        wickets = number_or_none(row.get("wickets"))
        if wickets is not None and wickets > 100:
            failures.append(f"bowling:{idx} wickets > 100")
    return failures


def common_name_failures(rows: list[dict[str, str]], label: str) -> list[str]:
    failures = []
    for idx, row in enumerate(rows, start=2):
        player = clean_text(row.get("player_name"))
        if not player:
            failures.append(f"{label}:{idx} blank player_name")
        if is_masked_name(player):
            failures.append(f"{label}:{idx} masked player_name")
        if is_numeric_only_name(player):
            failures.append(f"{label}:{idx} numeric-only player_name")
    return failures


def h_jolly_check(rows: list[dict[str, str]]) -> dict[str, object]:
    matches = [row for row in rows if row.get("player_name") == "H Jolly" and row.get("season") == "Summer 1944/45"]
    failures: list[str] = []
    if not matches:
        return {"message": "not present in bowling review export", "failures": failures}
    good = any(row.get("wickets") == "81" and row.get("bowling_runs_conceded") == "924" for row in matches)
    bad = [row for row in matches if row.get("wickets") == "924"]
    if not good:
        failures.append("H Jolly Summer 1944/45 missing expected 81 wickets / 924 runs conceded")
    if bad:
        failures.append("H Jolly Summer 1944/45 has a 924-wicket row")
    return {"message": f"{len(matches)} row(s), expected 81 wickets / 924 runs conceded {'found' if good else 'not found'}", "failures": failures}


def count_numeric_only_names(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if is_numeric_only_name(row.get("player_name")))


def count_masked_or_blank_names(rows: list[dict[str, str]]) -> int:
    return sum(1 for row in rows if not clean_text(row.get("player_name")) or is_masked_name(row.get("player_name")))


def season_sort_key(season: str) -> int:
    match = re.search(r"(Summer|Winter)\s+(\d{4})(?:/(\d{2}))?", clean_text(season), flags=re.IGNORECASE)
    if not match:
        return 999999
    start = int(match.group(2))
    offset = 0 if match.group(1).casefold() == "summer" else 50
    return start * 100 + offset


def balls_to_overs(value: str) -> str:
    balls = number_or_none(value)
    if balls is None:
        return ""
    whole_balls = int(balls)
    return f"{whole_balls // 6}.{whole_balls % 6}"


def number_or_none(value: object) -> float | None:
    text = clean_text(value).replace(",", "")
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def clean_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def is_masked_name(value: object) -> bool:
    text = clean_text(value)
    return bool(text) and set(text) <= {"*"}


def is_numeric_only_name(value: object) -> bool:
    return bool(re.fullmatch(r"\d+", clean_text(value)))


if __name__ == "__main__":
    raise SystemExit(main())
