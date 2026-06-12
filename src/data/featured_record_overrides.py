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


def normalize_featured_player_name(value: object) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


def featured_record_override_path(club_id: str | None = None) -> Path:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    return REPO_ROOT / "clubs" / active_club_id / "data" / "source" / "annual_report_featured_record_overrides.csv"


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

    overrides = load_featured_record_overrides(club_id)
    if overrides.empty:
        return output

    normalized_players = output["Player"].map(normalize_featured_player_name)
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
    return output
