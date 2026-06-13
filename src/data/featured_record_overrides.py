"""Load and apply approved, club-scoped featured-record overrides."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.config.club_config import REPO_ROOT, get_active_club_id, normalize_club_id


GRDCC_CLUB_ID = "georges-river-district"
APPROVED_STATUSES = {"approved", "annual_report_authoritative"}
METRIC_COLUMNS = {
    "career_runs": "Runs",
    "career_wickets": "Wickets",
}
ANNUAL_REPORT_LEADER_COLUMNS = {
    "most_runs": "Runs",
    "most_wickets": "Wickets",
}


def normalize_featured_player_name(value: object) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


def featured_record_override_path(club_id: str | None = None) -> Path:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    return REPO_ROOT / "clubs" / active_club_id / "data" / "source" / "annual_report_featured_record_overrides.csv"


def annual_report_all_time_leaders_path() -> Path:
    return (
        REPO_ROOT
        / "clubs"
        / GRDCC_CLUB_ID
        / "data"
        / "processed"
        / "validation"
        / "annual_report_2024_25"
        / "grdcc_annual_report_all_time_leaders_for_app.csv"
    )


def load_annual_report_all_time_leaders(club_id: str | None = None) -> pd.DataFrame:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    path = annual_report_all_time_leaders_path()
    if active_club_id != GRDCC_CLUB_ID or not path.exists():
        return pd.DataFrame()
    rows = pd.read_csv(path, dtype=str).fillna("")
    required = {"section", "player_name", "normalized_player_name", "displayed_value", "included_in_app"}
    if not required.issubset(rows.columns):
        return pd.DataFrame()
    included = rows["included_in_app"].astype(str).str.strip().str.casefold().isin({"1", "true", "yes"})
    rows = rows[included].copy()
    rows["displayed_value"] = pd.to_numeric(rows["displayed_value"], errors="coerce")
    return rows[rows["displayed_value"].notna()].reset_index(drop=True)


def load_featured_record_overrides(club_id: str | None = None) -> pd.DataFrame:
    """Return approved featured records for the active club, or an empty frame."""
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    if active_club_id != GRDCC_CLUB_ID:
        return pd.DataFrame()

    path = featured_record_override_path(active_club_id)
    if not path.exists():
        return pd.DataFrame()

    overrides = pd.read_csv(path, dtype=str).fillna("")
    required = {"club_id", "metric", "player_name", "authoritative_value", "reviewer_status"}
    if not required.issubset(overrides.columns):
        return pd.DataFrame()

    statuses = overrides["reviewer_status"].astype(str).str.strip().str.casefold()
    club_ids = overrides["club_id"].map(normalize_club_id)
    overrides = overrides[club_ids.eq(active_club_id) & statuses.isin(APPROVED_STATUSES)].copy()
    if overrides.empty:
        return overrides

    overrides["normalized_player_name"] = overrides["player_name"].map(normalize_featured_player_name)
    overrides["authoritative_value"] = pd.to_numeric(overrides["authoritative_value"], errors="coerce")
    return overrides[overrides["authoritative_value"].notna()].reset_index(drop=True)


def apply_featured_record_overrides(all_time: pd.DataFrame, club_id: str | None = None) -> pd.DataFrame:
    """Apply approved overrides to a presentation copy of an all-time table."""
    output = all_time.copy()
    if output.empty or "Player" not in output.columns:
        return output

    normalized_players = output["Player"].map(normalize_featured_player_name)
    overrides = load_featured_record_overrides(club_id)
    for _, override in overrides.iterrows():
        metric = str(override.get("metric", "")).strip()
        target_column = METRIC_COLUMNS.get(metric)
        if target_column is None or target_column not in output.columns:
            continue
        matches = normalized_players.eq(str(override["normalized_player_name"]))
        if not matches.any():
            continue
        matching_rows = output.loc[matches].copy()
        metric_values = pd.to_numeric(matching_rows[target_column], errors="coerce").fillna(0)
        featured_index = metric_values.idxmax()
        duplicate_indices = matching_rows.index.difference([featured_index])
        if len(duplicate_indices):
            output = output.drop(index=duplicate_indices)
            normalized_players = output["Player"].map(normalize_featured_player_name)
        output.loc[featured_index, target_column] = float(override["authoritative_value"])
        output.loc[featured_index, "Featured Record Override"] = True
        output.loc[featured_index, "Featured Record Metric"] = metric
        output.loc[featured_index, "Featured Record Source"] = str(override.get("annual_report_source", ""))
        output.loc[featured_index, "Featured Record Source Note"] = str(override.get("source_note", ""))

    annual_leaders = load_annual_report_all_time_leaders(club_id)
    for _, leader in annual_leaders.iterrows():
        target_column = ANNUAL_REPORT_LEADER_COLUMNS.get(str(leader.get("section", "")).strip())
        if target_column is None or target_column not in output.columns:
            continue
        normalized_name = str(leader.get("normalized_player_name", "")).strip()
        matches = normalized_players.eq(normalized_name)
        if matches.any():
            matching_rows = output.loc[matches].copy()
            current_values = pd.to_numeric(matching_rows[target_column], errors="coerce").fillna(0)
            featured_index = current_values.idxmax()
            duplicate_indices = matching_rows.index.difference([featured_index])
            if len(duplicate_indices):
                output = output.drop(index=duplicate_indices)
        else:
            featured_index = len(output)
            output.loc[featured_index, "Player"] = str(leader.get("player_name", "")).strip()
        current_value = pd.to_numeric(pd.Series([output.loc[featured_index, target_column]]), errors="coerce").fillna(0).iloc[0]
        output.loc[featured_index, target_column] = max(float(current_value), float(leader["displayed_value"]))
        output.loc[featured_index, "Featured Record Override"] = True
        output.loc[featured_index, "Featured Record Metric"] = str(leader.get("metric", ""))
        output.loc[featured_index, "Featured Record Source"] = "GRDCC 2024/25 Annual Report"
        normalized_players = output["Player"].map(normalize_featured_player_name)
    return output
