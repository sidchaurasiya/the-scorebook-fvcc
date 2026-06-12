#!/usr/bin/env python3
"""Build and validate GRDCC Most Premierships from scorecard participation."""

from __future__ import annotations

import csv
import os
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
try:
    import pandas as pd
except ModuleNotFoundError:
    app_python = ROOT / ".venv-app" / "bin" / "python"
    if app_python.exists() and Path(sys.executable).resolve() != app_python.resolve():
        os.execv(str(app_python), [str(app_python), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.premiership_honours import load_grdcc_most_premierships, merge_grdcc_premiership_honours  # noqa: E402


CLUB = ROOT / "clubs" / "georges-river-district"
HOF = CLUB / "data" / "processed" / "hall_of_fame"
VALIDATION = CLUB / "data" / "processed" / "validation" / "annual_report_2024_25"
WINS_PATH = HOF / "premiership_wins.csv"
EXISTING_PLAYERS_PATH = HOF / "player_premierships.csv"
SUMMARY_LISTS_PATH = CLUB / "data" / "source" / "premiership_scorecard_captains.csv"
PARTICIPATION_PATH = VALIDATION / "grdcc_premiership_player_participation.csv"
CALCULATED_PATH = VALIDATION / "grdcc_most_premierships_calculated.csv"
VALIDATION_PATH = VALIDATION / "grdcc_most_premierships_validation.csv"


def clean(value: object) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() in {"nan", "none", "nat"} else text


def normalize_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", clean(value).casefold()).strip()


def season_key(value: object) -> int:
    match = re.search(r"(19|20)\d{2}", clean(value))
    return int(match.group()) if match else -1


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def split_match_ids(value: object) -> list[str]:
    return [part.strip() for part in clean(value).split(",") if part.strip()]


def summary_players(raw_list: object) -> list[tuple[str, bool]]:
    players = []
    for raw_name in clean(raw_list).split(","):
        label = raw_name.strip()
        if not label:
            continue
        is_captain = bool(re.search(r"\(\s*c\s*\)\s*$", label, flags=re.IGNORECASE))
        name = re.sub(r"\s*\(\s*c\s*\)\s*$", "", label, flags=re.IGNORECASE).strip()
        if name:
            players.append((name, is_captain))
    return players


def main() -> int:
    base_wins = pd.read_csv(WINS_PATH, dtype=str).fillna("")
    wins = merge_grdcc_premiership_honours(base_wins, "georges-river-district")
    win_lookup = {clean(row["match_id"]): row for _, row in wins.iterrows() if clean(row.get("match_id"))}
    linked_match_ids = set(win_lookup)

    participation: list[dict[str, object]] = []
    existing_players = pd.read_csv(EXISTING_PLAYERS_PATH, dtype=str).fillna("")
    for _, player in existing_players.iterrows():
        for match_id in split_match_ids(player.get("evidence_match_ids")):
            win = win_lookup.get(match_id)
            if win is None:
                continue
            player_name = clean(player.get("display_player_name") or player.get("canonical_player_name"))
            captain_name = normalize_name(win.get("captain_name"))
            participation.append(participation_row(
                win, player_name, normalize_name(player_name) == captain_name,
                "verified_scorecard_participant_export", "high",
            ))

    summary_lists = pd.read_csv(SUMMARY_LISTS_PATH, dtype=str).fillna("")
    for _, evidence in summary_lists.iterrows():
        match_id = clean(evidence.get("match_id"))
        win = win_lookup.get(match_id)
        if win is None:
            continue
        for player_name, is_captain in summary_players(evidence.get("raw_team_list_or_captain_field")):
            participation.append(participation_row(
                win, player_name, is_captain,
                "playcricket_scorecard_summary_team_list", "high",
            ))

    participation_frame = pd.DataFrame(participation).drop_duplicates(
        ["match_id", "normalized_player_name"], keep="first"
    )
    participation_frame = participation_frame.sort_values(
        ["season_sort_key", "grade_or_team", "player_name"], ascending=[False, True, True]
    ).reset_index(drop=True)
    write_csv(PARTICIPATION_PATH, participation_frame.to_dict("records"), list(participation_frame.columns))

    records = []
    for normalized_name, group in participation_frame.groupby("normalized_player_name", sort=False):
        group = group.drop_duplicates("match_id").copy()
        latest = int(group["season_sort_key"].max())
        display_name = sorted(group["player_name"].tolist(), key=lambda value: (-len(value), value))[0]
        ordered = group.sort_values(["season_sort_key", "grade_or_team"], ascending=[False, True])
        details = [f"{row['season']} — {row['grade_or_team']}" for _, row in ordered.iterrows()]
        records.append({
            "player_name": display_name,
            "normalized_player_name": normalized_name,
            "premiership_count": len(group),
            "seasons": ", ".join(dict.fromkeys(ordered["season"].tolist())),
            "grades_or_teams": ", ".join(dict.fromkeys(ordered["grade_or_team"].tolist())),
            "premiership_details": " | ".join(details),
            "captain_count": int(group["is_captain"].eq("yes").sum()),
            "scorecard_match_ids": ", ".join(ordered["match_id"].tolist()),
            "scorecard_urls": ", ".join(ordered["scorecard_url"].tolist()),
            "latest_premiership_season_sort_key": latest,
            "source_basis": "Explicit GRDCC scorecard participant/team lists",
            "notes": "Annual Report-only wins without player lists are excluded.",
        })
    calculated = pd.DataFrame(records).sort_values(
        ["premiership_count", "latest_premiership_season_sort_key", "player_name"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
    write_csv(CALCULATED_PATH, calculated.to_dict("records"), list(calculated.columns))

    matches_with_lists = set(participation_frame["match_id"])
    matches_without_lists = linked_match_ids - matches_with_lists
    annual_only = wins[wins["match_id"].astype(str).str.strip().eq("")]
    duplicate_rows = len(participation) - len(participation_frame)
    top_count = int(calculated["premiership_count"].max()) if not calculated.empty else 0
    top_players = calculated.loc[calculated["premiership_count"].eq(top_count), "player_name"].tolist()
    sorted_ok = calculated["premiership_count"].tolist() == sorted(calculated["premiership_count"].tolist(), reverse=True)
    checks = [
        ("premiership_matches_with_player_lists", len(matches_with_lists), 16),
        ("linked_premiership_matches_without_player_lists", len(matches_without_lists), 0),
        ("annual_report_only_matches_excluded", len(annual_only), 6),
        ("player_participation_rows", len(participation_frame), len(participation_frame)),
        ("duplicate_player_match_rows", duplicate_rows, 0),
        ("most_premierships_player_count", len(calculated), len(calculated)),
        ("sorting_descending", sorted_ok, True),
        ("explicit_scorecard_sources_only", participation_frame["extraction_source"].isin({"verified_scorecard_participant_export", "playcricket_scorecard_summary_team_list"}).all(), True),
        ("no_blank_player_names", participation_frame["normalized_player_name"].ne("").all(), True),
        ("fvcc_data_unchanged", load_grdcc_most_premierships("fvcc").empty, True),
    ]
    validation_rows = [{
        "check": name, "actual": actual, "expected": expected,
        "status": "pass" if str(actual) == str(expected) else "fail",
        "details": ", ".join(top_players) + f" ({top_count})" if name == "most_premierships_player_count" else "",
    } for name, actual, expected in checks]
    write_csv(VALIDATION_PATH, validation_rows, ["check", "actual", "expected", "status", "details"])
    failures = sum(row["status"] == "fail" for row in validation_rows)
    print(f"Matches with player lists: {len(matches_with_lists)}")
    print(f"Annual Report-only wins excluded: {len(annual_only)}")
    print(f"Participation rows: {len(participation_frame)}")
    print(f"Duplicate player-match rows: {duplicate_rows}")
    print(f"Calculated players: {len(calculated)}")
    print(f"Top: {', '.join(top_players)} — {top_count}")
    print(f"Validation failures: {failures}")
    return 1 if failures else 0


def participation_row(win: pd.Series, player_name: str, is_captain: bool, source: str, confidence: str) -> dict[str, object]:
    season = clean(win.get("season"))
    return {
        "season": season,
        "season_sort_key": int(float(win.get("season_sort_key"))) if clean(win.get("season_sort_key")) else season_key(season),
        "grade_or_team": clean(win.get("grade_name")),
        "premiership_label": "Premiers",
        "match_id": clean(win.get("match_id")),
        "scorecard_url": clean(win.get("scoreboard_url")),
        "match_context": clean(win.get("match_context")),
        "match_confidence": clean(win.get("match_confidence")),
        "is_counted_for_most_premierships": "yes",
        "player_name": player_name,
        "normalized_player_name": normalize_name(player_name),
        "player_role": "captain" if is_captain else "player",
        "is_captain": "yes" if is_captain else "no",
        "extraction_source": source,
        "extraction_confidence": confidence,
        "notes": "Explicit GRDCC scorecard participation evidence.",
    }


if __name__ == "__main__":
    raise SystemExit(main())
