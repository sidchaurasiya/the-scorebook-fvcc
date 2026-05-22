from __future__ import annotations

from typing import Any, Iterable

import pandas as pd


NEUTRAL_TO_LEGACY_COLUMNS = {
    "club_team_id": "fvcc_team_id",
    "club_team_name": "fvcc_team_name",
    "is_club_player": "is_fvcc_player",
}


def ensure_club_ownership_columns(frame: pd.DataFrame, *, preserve_legacy: bool = True) -> pd.DataFrame:
    """Add neutral club ownership columns, falling back to legacy FVCC names."""
    if frame.empty:
        return frame.copy()
    output = frame.copy()
    for neutral_column, legacy_column in NEUTRAL_TO_LEGACY_COLUMNS.items():
        if neutral_column not in output and legacy_column in output:
            output[neutral_column] = output[legacy_column]
        if preserve_legacy and legacy_column not in output and neutral_column in output:
            output[legacy_column] = output[neutral_column]
    return output


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes", "y"}


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"", "nan", "none", "nat"} else text


def split_id_list(value: object) -> set[str]:
    return {part.strip() for part in clean_text(value).replace(",", "|").split("|") if part.strip()}


def is_selected_club_team_name(value: object, club_name_token: str | None = None) -> bool:
    token = clean_text(club_name_token).casefold()
    if not token:
        token = "fiji victorian"
    return token in clean_text(value).casefold()


def normalize_team_ids(values: Iterable[object] | None) -> set[str]:
    return {clean_text(value) for value in (values or []) if clean_text(value)}


def add_club_match_ownership(
    matches: pd.DataFrame,
    *,
    club_team_ids: Iterable[object] | None = None,
    club_name_token: str | None = None,
    preserve_legacy: bool = True,
) -> pd.DataFrame:
    """Attach neutral club-team columns to match rows without changing match semantics."""
    if matches.empty:
        return matches.copy()
    output = ensure_club_ownership_columns(matches, preserve_legacy=preserve_legacy)
    for column in ["home_team_id", "away_team_id", "home_team_name", "away_team_name"]:
        if column not in output:
            output[column] = pd.NA

    existing = output.get("club_team_id", pd.Series(index=output.index, dtype="object")).fillna("").astype(str).str.strip()
    missing = existing.eq("") | existing.str.casefold().isin({"nan", "none", "nat"})
    if not missing.any():
        return ensure_club_ownership_columns(output, preserve_legacy=preserve_legacy)

    team_ids = normalize_team_ids(club_team_ids)
    if team_ids:
        home_is_club = output["home_team_id"].astype(str).isin(team_ids)
        away_is_club = output["away_team_id"].astype(str).isin(team_ids)
    elif "source_team_ids" in output:
        source_sets = output["source_team_ids"].map(split_id_list)
        home_is_club = [
            clean_text(team_id) in source_ids
            for team_id, source_ids in zip(output["home_team_id"], source_sets)
        ]
        away_is_club = [
            clean_text(team_id) in source_ids
            for team_id, source_ids in zip(output["away_team_id"], source_sets)
        ]
        home_is_club = pd.Series(home_is_club, index=output.index)
        away_is_club = pd.Series(away_is_club, index=output.index)
    else:
        home_is_club = output["home_team_name"].map(lambda value: is_selected_club_team_name(value, club_name_token))
        away_is_club = output["away_team_name"].map(lambda value: is_selected_club_team_name(value, club_name_token))

    output.loc[missing, "club_team_id"] = output["home_team_id"].where(home_is_club, output["away_team_id"])[missing]
    output.loc[missing, "club_team_name"] = output["home_team_name"].where(home_is_club, output["away_team_name"])[missing]
    return ensure_club_ownership_columns(output, preserve_legacy=preserve_legacy)


def club_team_mask(frame: pd.DataFrame, *, team_id_column: str = "team_id") -> pd.Series:
    """Return rows belonging to the selected club team, accepting old or new columns."""
    if frame.empty:
        return pd.Series(dtype="bool")
    rows = ensure_club_ownership_columns(frame)
    if {team_id_column, "club_team_id"}.issubset(rows.columns):
        return rows[team_id_column].astype(str) == rows["club_team_id"].astype(str)
    if "is_club_player" in rows and rows["is_club_player"].notna().any():
        return rows["is_club_player"].map(parse_bool)
    return pd.Series([True] * len(rows), index=rows.index)


def club_team_ids_by_match(matches: pd.DataFrame) -> dict[str, set[str]]:
    rows = ensure_club_ownership_columns(matches)
    if rows.empty or "match_id" not in rows or "club_team_id" not in rows:
        return {}
    output: dict[str, set[str]] = {}
    for _, row in rows.iterrows():
        match_id = clean_text(row.get("match_id"))
        team_id = clean_text(row.get("club_team_id"))
        if match_id and team_id:
            output.setdefault(match_id, set()).add(team_id)
    return output
