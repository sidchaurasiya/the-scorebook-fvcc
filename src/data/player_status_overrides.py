"""Optional, governed current-club status overrides for FVCC and GRDCC."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.config.club_config import REPO_ROOT, normalize_club_id


SUPPORTED_CLUB_IDS = {"fvcc", "georges-river-district"}
PLAYER_STATUS_OVERRIDE_COLUMNS = [
    "player_id",
    "status",
    "reason",
    "source",
    "effective_date",
]
VALID_PLAYER_STATUSES = {"active", "inactive"}


def player_status_overrides_path(club_id: str) -> Path:
    normalized_club_id = normalize_club_id(club_id)
    return (
        REPO_ROOT
        / "clubs"
        / normalized_club_id
        / "data"
        / "source"
        / f"{normalized_club_id}_player_status_overrides.csv"
    )


def player_status_signature(club_id: str) -> tuple[str, int, int] | tuple[()]:
    normalized_club_id = normalize_club_id(club_id)
    if normalized_club_id not in SUPPORTED_CLUB_IDS:
        return tuple()
    path = player_status_overrides_path(normalized_club_id)
    if not path.exists():
        return tuple()
    stat = path.stat()
    return str(path), stat.st_size, stat.st_mtime_ns


@st.cache_data(show_spinner=False)
def load_player_status_overrides(
    club_id: str,
    file_signature: tuple[object, ...] | None = None,
) -> pd.DataFrame:
    del file_signature
    normalized_club_id = normalize_club_id(club_id)
    if normalized_club_id not in SUPPORTED_CLUB_IDS:
        return pd.DataFrame(columns=PLAYER_STATUS_OVERRIDE_COLUMNS)
    path = player_status_overrides_path(normalized_club_id)
    if not path.exists():
        return pd.DataFrame(columns=PLAYER_STATUS_OVERRIDE_COLUMNS)

    output = pd.read_csv(path, dtype=str).fillna("")
    for column in PLAYER_STATUS_OVERRIDE_COLUMNS:
        if column not in output:
            output[column] = ""
    output = output[PLAYER_STATUS_OVERRIDE_COLUMNS].copy()
    output["player_id"] = output["player_id"].astype(str).str.strip()
    output["status"] = output["status"].astype(str).str.strip().str.casefold()
    output = output[
        output["player_id"].ne("")
        & output["status"].isin(VALID_PLAYER_STATUSES)
    ].copy()
    if output.empty:
        return output

    output["_effective_sort"] = pd.to_datetime(output["effective_date"], errors="coerce", utc=True)
    output = output.sort_values(["_effective_sort", "player_id"], na_position="first")
    return output.drop_duplicates("player_id", keep="last").drop(columns="_effective_sort")


def apply_active_player_id_overrides(
    default_active_ids: set[str],
    activity: pd.DataFrame,
    *,
    club_id: str,
) -> set[str]:
    """Apply reviewed overrides only to canonical IDs present in club activity."""
    overrides = load_player_status_overrides(club_id, player_status_signature(club_id))
    active = {str(value).strip() for value in default_active_ids if str(value).strip()}
    if overrides.empty or activity.empty or "canonical_player_id" not in activity:
        return active

    known_ids = {
        str(value).strip()
        for value in activity["canonical_player_id"].dropna()
        if str(value).strip()
    }
    for row in overrides.itertuples(index=False):
        player_id = str(row.player_id).strip()
        if player_id not in known_ids:
            continue
        if row.status == "active":
            active.add(player_id)
        else:
            active.discard(player_id)
    return active


def apply_active_player_name_overrides(
    default_active_names: set[str],
    activity_frames: list[pd.DataFrame],
    *,
    club_id: str,
    name_normalizer,
) -> set[str]:
    """Resolve ID-only decisions to existing public names for HOF badges."""
    overrides = load_player_status_overrides(club_id, player_status_signature(club_id))
    active = {name_normalizer(value) for value in default_active_names if name_normalizer(value)}
    if overrides.empty:
        return active

    identity_rows = []
    for frame in activity_frames:
        if frame.empty or "canonical_player_id" not in frame:
            continue
        name_column = "canonical_player_name" if "canonical_player_name" in frame else "player_name"
        if name_column not in frame:
            continue
        identity_rows.append(
            frame[["canonical_player_id", name_column]].rename(columns={name_column: "player_name"})
        )
    if not identity_rows:
        return active

    identities = pd.concat(identity_rows, ignore_index=True).dropna().drop_duplicates()
    identities["canonical_player_id"] = identities["canonical_player_id"].astype(str).str.strip()
    identities["player_name"] = identities["player_name"].map(name_normalizer)
    identities = identities[
        identities["canonical_player_id"].ne("")
        & identities["player_name"].astype(str).str.strip().ne("")
    ]
    names_by_id = identities.groupby("canonical_player_id")["player_name"].agg(set).to_dict()
    for row in overrides.itertuples(index=False):
        names = names_by_id.get(str(row.player_id).strip(), set())
        for player_name in names:
            if row.status == "active":
                active.add(player_name)
            else:
                active.discard(player_name)
    return active
