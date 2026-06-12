"""Merge GRDCC Annual Report honours into the featured premiership list."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.config.club_config import REPO_ROOT, get_active_club_id


GRDCC_CLUB_ID = "georges-river-district"


def annual_report_premiership_path() -> Path:
    return REPO_ROOT / "clubs" / GRDCC_CLUB_ID / "data" / "source" / "annual_report_premiership_wins.csv"


def normalize_premiership_grade(value: object) -> str:
    label = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()
    aliases = {
        "tim creer cup": "fifth grade",
        "5th grade": "fifth grade",
        "first grade limited overs": "first grade limited overs",
        "1st grade limited overs": "first grade limited overs",
        "vintage 60s": "vintage",
        "vintage over 60s": "vintage",
        "classics foxs over 50s": "classics",
    }
    return aliases.get(label, label)


def premiership_key(season: object, grade: object) -> str:
    return f"{str(season or '').strip().casefold()}|{normalize_premiership_grade(grade)}"


def load_annual_report_premierships(club_id: str | None = None) -> pd.DataFrame:
    if (club_id or get_active_club_id()) != GRDCC_CLUB_ID:
        return pd.DataFrame()
    path = annual_report_premiership_path()
    if not path.exists():
        return pd.DataFrame()
    rows = pd.read_csv(path, dtype=str).fillna("")
    return rows[rows["extraction_confidence"].str.casefold().eq("high")].copy()


def merge_grdcc_premiership_honours(wins: pd.DataFrame, club_id: str | None = None) -> pd.DataFrame:
    active_club = club_id or get_active_club_id()
    if active_club != GRDCC_CLUB_ID:
        return wins
    report_rows = load_annual_report_premierships(active_club)
    if report_rows.empty:
        return wins

    output = wins.copy()
    existing_keys = {
        premiership_key(row.get("season"), row.get("grade_name"))
        for _, row in output.iterrows()
    }
    additions = []
    for _, row in report_rows.iterrows():
        key = premiership_key(row["season"], row["grade_or_team"])
        if key in existing_keys:
            continue
        existing_keys.add(key)
        additions.append(
            {
                "match_id": "",
                "season": row["season"],
                "grade_name": row["grade_or_team"],
                "round_name": "Premiership",
                "match_date": "",
                "club_team_id": "",
                "club_team_name": "Georges River",
                "fvcc_team_name": "Georges River",
                "opponent_team_name": "",
                "captain_name": "",
                "result_text": "Premiers",
                "result_margin_display": "Premiers",
                "venue_name": "",
                "scoreboard_url": "",
                "confidence": "high",
                "detection_reason": "GRDCC 2024/25 Annual Report official premiership honours list",
                "source_system": "annual_report",
                "source_report_year": row["report_year"],
                "source_report_page": row["annual_report_page"],
                "source_note": "Source: GRDCC 2024/25 Annual Report",
                "season_sort_key": row["season_sort_key"],
            }
        )
    if additions:
        output = pd.concat([output, pd.DataFrame(additions)], ignore_index=True, sort=False)
    output["season_sort_key"] = pd.to_numeric(output.get("season_sort_key"), errors="coerce")
    missing_keys = output["season_sort_key"].isna()
    output.loc[missing_keys, "season_sort_key"] = output.loc[missing_keys, "season"].map(season_start_year)
    output["_grade_sort"] = output["grade_name"].map(normalize_premiership_grade)
    return output.sort_values(
        ["season_sort_key", "_grade_sort"], ascending=[False, True], na_position="last"
    ).drop(columns="_grade_sort").reset_index(drop=True)


def season_start_year(value: object) -> int | None:
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    return int(match.group()) if match else None
