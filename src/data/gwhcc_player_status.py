"""Governed GWHCC current-club player status overrides."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


CLUB_ID = "glen-waverley-hawks"
ROOT = Path(__file__).resolve().parents[2]
STATUS_PATH = ROOT / "clubs" / CLUB_ID / "data" / "source" / "gwhcc_player_status_overrides.csv"
STATUS_COLUMNS = [
    "canonical_player_id",
    "canonical_player_name",
    "status",
    "effective_season",
    "source",
    "confidence",
    "notes",
]


def normalize_name(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


def player_status_signature() -> tuple[str, int, int] | tuple[()]:
    if not STATUS_PATH.exists():
        return tuple()
    stat = STATUS_PATH.stat()
    return str(STATUS_PATH), stat.st_size, stat.st_mtime_ns


def load_player_status_overrides() -> pd.DataFrame:
    if not STATUS_PATH.exists():
        return pd.DataFrame(columns=STATUS_COLUMNS)
    frame = pd.read_csv(STATUS_PATH, dtype=str).fillna("")
    for column in STATUS_COLUMNS:
        if column not in frame:
            frame[column] = ""
    confidence = frame["confidence"].str.strip().str.casefold()
    status = frame["status"].str.strip().str.casefold()
    return frame[confidence.isin({"confirmed", "approved", "high"}) & status.isin({"active", "inactive"})][STATUS_COLUMNS].copy()


def governed_active_player_ids(default_active_ids: set[str], activity: pd.DataFrame) -> set[str]:
    """Apply current-club overrides to a recency-derived canonical ID set."""
    overrides = load_player_status_overrides()
    active = {str(value).strip() for value in default_active_ids if str(value).strip()}
    if overrides.empty:
        return active
    id_by_name = activity_identity_lookup(activity)
    for row in overrides.to_dict("records"):
        player_id = str(row.get("canonical_player_id") or "").strip()
        if not player_id:
            player_id = id_by_name.get(normalize_name(row.get("canonical_player_name")), "")
        if not player_id:
            continue
        if str(row.get("status")).strip().casefold() == "active":
            active.add(player_id)
        else:
            active.discard(player_id)
    return active


def governed_active_player_names(default_active_names: set[str]) -> set[str]:
    """Apply the same overrides to Hall of Fame name-based active badges."""
    overrides = load_player_status_overrides()
    active = {normalize_name(value) for value in default_active_names if normalize_name(value)}
    for row in overrides.to_dict("records"):
        name = normalize_name(row.get("canonical_player_name"))
        if not name:
            continue
        if str(row.get("status")).strip().casefold() == "active":
            active.add(name)
        else:
            active.discard(name)
    return active


def governed_player_active(default_active: bool, canonical_player_id: object, player_name: object) -> bool:
    overrides = load_player_status_overrides()
    player_id = str(canonical_player_id or "").strip()
    name = normalize_name(player_name)
    for row in overrides.to_dict("records"):
        override_id = str(row.get("canonical_player_id") or "").strip()
        override_name = normalize_name(row.get("canonical_player_name"))
        if (player_id and override_id == player_id) or (name and override_name == name):
            return str(row.get("status")).strip().casefold() == "active"
    return default_active


def activity_identity_lookup(activity: pd.DataFrame) -> dict[str, str]:
    if activity.empty or "canonical_player_name" not in activity or "canonical_player_id" not in activity:
        return {}
    rows = activity[["canonical_player_name", "canonical_player_id"]].dropna().drop_duplicates().copy()
    rows["_name_key"] = rows["canonical_player_name"].map(normalize_name)
    counts = rows.groupby("_name_key")["canonical_player_id"].nunique()
    unique = set(counts[counts == 1].index)
    return {
        str(row["_name_key"]): str(row["canonical_player_id"]).strip()
        for _, row in rows[rows["_name_key"].isin(unique)].iterrows()
    }
