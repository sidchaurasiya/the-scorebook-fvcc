"""Merge GRDCC Annual Report honours into the featured premiership list."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.config.club_config import REPO_ROOT, get_active_club_id, get_feature_flag


GRDCC_CLUB_ID = "georges-river-district"
POST_PLAYCRICKET_PREMIERSHIP_YEAR = 2008


def annual_report_premiership_path() -> Path:
    return REPO_ROOT / "clubs" / GRDCC_CLUB_ID / "data" / "source" / "annual_report_premiership_wins.csv"


def premiership_match_context_path() -> Path:
    return (
        REPO_ROOT
        / "clubs"
        / GRDCC_CLUB_ID
        / "data"
        / "processed"
        / "season_overview"
        / "season_by_round_scorecards.csv"
    )


def premiership_scorecard_captains_path() -> Path:
    return (
        REPO_ROOT
        / "clubs"
        / GRDCC_CLUB_ID
        / "data"
        / "source"
        / "premiership_scorecard_captains.csv"
    )


def grdcc_most_premierships_path() -> Path:
    return (
        REPO_ROOT
        / "clubs"
        / GRDCC_CLUB_ID
        / "data"
        / "processed"
        / "validation"
        / "annual_report_2024_25"
        / "grdcc_most_premierships_calculated.csv"
    )


def load_grdcc_most_premierships(club_id: str | None = None) -> pd.DataFrame:
    active_club = club_id or get_active_club_id()
    if active_club != GRDCC_CLUB_ID or not get_feature_flag("has_annual_report_overrides", False, club_id=active_club):
        return pd.DataFrame()
    path = grdcc_most_premierships_path()
    if not path.exists():
        return pd.DataFrame()
    rows = pd.read_csv(path, dtype=str).fillna("")
    if rows.empty:
        return rows
    rows["display_player_name"] = rows["player_name"]
    rows["canonical_player_name"] = rows["player_name"]
    rows["canonical_player_id"] = ""
    rows["grades"] = rows["grades_or_teams"]
    rows["teams"] = "Georges River"
    rows["evidence_match_ids"] = rows["scorecard_match_ids"]
    rows["confidence"] = "high"
    rows["latest_premiership_season"] = rows["seasons"].str.split(",").str[0].str.strip()
    return rows


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
    if label in aliases:
        return aliases[label]
    if "classics" in label:
        return "classics"
    if "vintage" in label:
        return "vintage"
    if label.startswith("second grade"):
        return "second grade"
    if label.startswith("third grade"):
        return "third grade"
    if label.startswith("fourth grade"):
        return "fourth grade"
    if label.startswith("fifth grade") or "tim creer cup" in label:
        return "fifth grade"
    if label.startswith("frank gray shield"):
        return "frank gray shield"
    return label


def premiership_key(season: object, grade: object) -> str:
    return f"{str(season or '').strip().casefold()}|{normalize_premiership_grade(grade)}"


def load_annual_report_premierships(club_id: str | None = None) -> pd.DataFrame:
    active_club = club_id or get_active_club_id()
    if active_club != GRDCC_CLUB_ID or not get_feature_flag("has_annual_report_overrides", False, club_id=active_club):
        return pd.DataFrame()
    path = annual_report_premiership_path()
    if not path.exists():
        return pd.DataFrame()
    rows = pd.read_csv(path, dtype=str).fillna("")
    return rows[rows["extraction_confidence"].str.casefold().eq("high")].copy()


def merge_grdcc_premiership_honours(wins: pd.DataFrame, club_id: str | None = None) -> pd.DataFrame:
    active_club = club_id or get_active_club_id()
    if active_club != GRDCC_CLUB_ID or not get_feature_flag("has_annual_report_overrides", False, club_id=active_club):
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
    output = enrich_grdcc_premiership_matches(output)
    output["season_sort_key"] = pd.to_numeric(output.get("season_sort_key"), errors="coerce")
    missing_keys = output["season_sort_key"].isna()
    output.loc[missing_keys, "season_sort_key"] = output.loc[missing_keys, "season"].map(season_start_year)
    output["_grade_sort"] = output["grade_name"].map(normalize_premiership_grade)
    return output.sort_values(
        ["season_sort_key", "_grade_sort"], ascending=[False, True], na_position="last"
    ).drop(columns="_grade_sort").reset_index(drop=True)


def enrich_grdcc_premiership_matches(wins: pd.DataFrame) -> pd.DataFrame:
    """Attach local PlayCricket context without changing the honours authority."""
    output = wins.copy()
    defaults = {
        "match_source": "",
        "match_context": "annual_report_only",
        "match_confidence": "",
        "match_notes": "",
        "captain_source": "",
        "captain_confidence": "",
        "captain_extraction_method": "not_found",
        "captain_notes": "",
    }
    for column, default in defaults.items():
        if column not in output:
            output[column] = default

    existing_match = output.get("match_id", pd.Series("", index=output.index)).astype(str).str.strip().ne("")
    output.loc[existing_match, "match_source"] = "playcricket"
    output.loc[existing_match, "match_context"] = output.loc[existing_match, "round_name"].map(
        classify_match_context
    )
    output.loc[existing_match, "match_confidence"] = output.loc[existing_match, "confidence"].replace("", "high")
    output.loc[existing_match, "match_notes"] = "Verified finals scorecard retained from current Hall of Fame data."
    explicit_captain = existing_match & output.get("captain_name", pd.Series("", index=output.index)).astype(str).str.strip().ne("")
    output.loc[explicit_captain, "captain_source"] = "hall_of_fame_premiership_wins"
    output.loc[explicit_captain, "captain_confidence"] = "high"
    output.loc[explicit_captain, "captain_extraction_method"] = "existing_verified_captain"
    output.loc[explicit_captain, "captain_notes"] = "Existing match-level captain retained from verified premiership data."

    path = premiership_match_context_path()
    if not path.exists():
        return apply_scorecard_captains(output)
    matches = pd.read_csv(path, dtype=str).fillna("")
    if matches.empty:
        return apply_scorecard_captains(output)
    matches["_grade_key"] = matches["grade_name"].map(normalize_premiership_grade)
    matches["_match_date"] = pd.to_datetime(matches["match_date"], errors="coerce", utc=True)

    for index, row in output.loc[~existing_match].iterrows():
        if (season_start_year(row.get("season")) or 0) < POST_PLAYCRICKET_PREMIERSHIP_YEAR:
            continue
        candidates = matches[
            matches["season"].eq(str(row.get("season", "")))
            & matches["_grade_key"].eq(normalize_premiership_grade(row.get("grade_name")))
        ].copy()
        if candidates.empty:
            output.at[index, "match_notes"] = "No matching local PlayCricket grade rows were available."
            continue

        candidates["_context"] = candidates["round_name"].map(classify_match_context)
        final_rows = candidates[candidates["_context"].isin(["grand_final", "final"])]
        if not final_rows.empty:
            selected = final_rows.sort_values("_match_date").iloc[-1]
            context = str(selected["_context"])
            confidence = "high" if context == "grand_final" else "medium"
            notes = "Matched by season and grade to the latest local PlayCricket finals row."
        else:
            selected = candidates.sort_values("_match_date").iloc[-1]
            context = "last_available_match"
            confidence = "medium"
            notes = "No final was identified; attached the last available local PlayCricket match as context only."

        match_id = str(selected.get("match_id", "")).strip()
        output.at[index, "match_id"] = match_id
        output.at[index, "match_date"] = selected.get("match_date", "")
        output.at[index, "opponent_team_name"] = selected.get("opponent_name", "")
        output.at[index, "result_text"] = selected.get("result_text", "") or "Premiers"
        output.at[index, "result_margin_display"] = selected.get("result_text", "") or "Premiers"
        output.at[index, "scoreboard_url"] = (
            f"https://play.cricket.com.au/match/{match_id}?tab=scorecard" if match_id else ""
        )
        output.at[index, "match_source"] = "playcricket"
        output.at[index, "match_context"] = context
        output.at[index, "match_confidence"] = confidence
        output.at[index, "match_notes"] = notes
        output.at[index, "captain_notes"] = "Local processed scorecard data does not expose an explicit captain field."
    return apply_scorecard_captains(output)


def apply_scorecard_captains(wins: pd.DataFrame) -> pd.DataFrame:
    """Apply explicit GRDCC captain markers captured from PlayCricket summaries."""
    path = premiership_scorecard_captains_path()
    if not path.exists() or wins.empty:
        return wins
    captains = pd.read_csv(path, dtype=str).fillna("")
    if captains.empty:
        return wins

    output = wins.copy()
    lookup = captains.set_index("match_id", drop=False).to_dict("index")
    for index, row in output.iterrows():
        if str(row.get("captain_name", "")).strip():
            continue
        match_id = str(row.get("match_id", "")).strip()
        evidence = lookup.get(match_id)
        if not evidence:
            continue
        captain = str(evidence.get("captain", "")).strip()
        output.at[index, "captain_extraction_method"] = evidence.get("captain_extraction_method", "not_found")
        output.at[index, "captain_notes"] = evidence.get("captain_notes", "")
        if not captain:
            continue
        output.at[index, "captain_name"] = captain
        output.at[index, "captain_source"] = evidence.get("captain_source", "playcricket_scorecard_summary")
        output.at[index, "captain_confidence"] = evidence.get("captain_confidence", "high")
    return output


def classify_match_context(value: object) -> str:
    label = re.sub(r"\s+", " ", str(value or "").casefold()).strip()
    if "grand final" in label:
        return "grand_final"
    if "final" in label:
        return "final"
    return "last_available_match"


def season_start_year(value: object) -> int | None:
    match = re.search(r"(19|20)\d{2}", str(value or ""))
    return int(match.group()) if match else None
