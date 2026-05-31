from __future__ import annotations

import copy
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import streamlit as st

try:
    import yaml
except ModuleNotFoundError:  # Local venvs may not be refreshed immediately after requirements change.
    yaml = None


REPO_ROOT = Path(__file__).resolve().parents[2]
CLUBS_ROOT = REPO_ROOT / "clubs"
DEFAULT_CLUB_ID = "fvcc"
LEGACY_DATA_PATHS = {
    "root_dir": "data",
    "processed_dir": "data/processed",
    "hall_of_fame_dir": "data/processed/hall_of_fame",
    "season_overview_dir": "data/processed/season_overview",
    "player_profile_dir": "data/processed/player_profile",
    "raw_match_centre_dir": "data/raw/match_centre",
    "processed_match_centre_dir": "data/processed/match_centre",
    "experimental_dir": "data/processed/experimental",
    "mapping_dir": "data",
}


def get_active_club_id() -> str:
    """Return the active club id, defaulting to FVCC for backwards compatibility."""
    env_value = os.getenv("CLUB_ID", "").strip()
    if env_value:
        return normalize_club_id(env_value)

    try:
        secret_value = str(st.secrets.get("CLUB_ID", "")).strip()
    except Exception:
        secret_value = ""
    return normalize_club_id(secret_value or DEFAULT_CLUB_ID)


def load_club_config(club_id: str | None = None) -> dict[str, Any]:
    """Load a club config by id and return a defensive copy."""
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    return copy.deepcopy(_load_club_config_cached(active_club_id))


def get_club_name(club_id: str | None = None) -> str:
    club = load_club_config(club_id).get("club", {})
    return str(club.get("display_name") or club.get("name") or get_active_club_id())


def get_club_short_name(club_id: str | None = None) -> str:
    club = load_club_config(club_id).get("club", {})
    return str(club.get("short_name") or club.get("club_id") or get_active_club_id()).upper()


def get_club_data_path(key: str, *parts: str | Path, club_id: str | None = None) -> Path:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    config = load_club_config(active_club_id)
    data_config = config.get("data", {})
    path_value = data_config.get(key, LEGACY_DATA_PATHS.get(key))
    if path_value is None:
        raise KeyError(f"Data path '{key}' is not configured for club '{active_club_id}'.")
    path = Path(str(path_value))
    if not path.is_absolute():
        path = REPO_ROOT / path
    configured_path = path.joinpath(*parts)
    if not parts or configured_path.exists():
        return configured_path

    if not allow_legacy_fallback(active_club_id, config=config):
        return configured_path

    legacy_value = LEGACY_DATA_PATHS.get(key)
    if legacy_value is None:
        return configured_path
    legacy_path = Path(legacy_value)
    if not legacy_path.is_absolute():
        legacy_path = REPO_ROOT / legacy_path
    legacy_candidate = legacy_path.joinpath(*parts)
    return legacy_candidate if legacy_candidate.exists() else configured_path


def get_data_root(club_id: str | None = None) -> Path:
    return get_club_data_path("root_dir", club_id=club_id)


def get_processed_dir(club_id: str | None = None) -> Path:
    return get_club_data_path("processed_dir", club_id=club_id)


def get_processed_path(*parts: str | Path, club_id: str | None = None) -> Path:
    return get_club_data_path("processed_dir", *parts, club_id=club_id)


def get_hall_of_fame_dir(club_id: str | None = None) -> Path:
    return get_club_data_path("hall_of_fame_dir", club_id=club_id)


def get_hall_of_fame_path(*parts: str | Path, club_id: str | None = None) -> Path:
    return get_club_data_path("hall_of_fame_dir", *parts, club_id=club_id)


def get_season_overview_dir(club_id: str | None = None) -> Path:
    return get_club_data_path("season_overview_dir", club_id=club_id)


def get_season_overview_path(*parts: str | Path, club_id: str | None = None) -> Path:
    return get_club_data_path("season_overview_dir", *parts, club_id=club_id)


def get_player_profile_dir(club_id: str | None = None) -> Path:
    return get_club_data_path("player_profile_dir", club_id=club_id)


def get_player_profile_path(*parts: str | Path, club_id: str | None = None) -> Path:
    return get_club_data_path("player_profile_dir", *parts, club_id=club_id)


def get_raw_match_centre_dir(club_id: str | None = None) -> Path:
    return get_club_data_path("raw_match_centre_dir", club_id=club_id)


def get_processed_match_centre_dir(club_id: str | None = None) -> Path:
    return get_club_data_path("processed_match_centre_dir", club_id=club_id)


def get_experimental_dir(club_id: str | None = None) -> Path:
    return get_club_data_path("experimental_dir", club_id=club_id)


def get_mapping_dir(club_id: str | None = None) -> Path:
    return get_club_data_path("mapping_dir", club_id=club_id)


def get_mapping_path(filename: str | Path, club_id: str | None = None) -> Path:
    return get_club_data_path("mapping_dir", filename, club_id=club_id)


def allow_legacy_fallback(club_id: str | None = None, *, config: dict[str, Any] | None = None) -> bool:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    data_config = (config or load_club_config(active_club_id)).get("data", {})
    value = data_config.get("allow_legacy_fallback")
    if value is None:
        return active_club_id == DEFAULT_CLUB_ID
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def get_feature_flag(name: str, default: bool = False, club_id: str | None = None) -> bool:
    features = load_club_config(club_id).get("features", {})
    value = features.get(name, default)
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def get_branding_value(name: str, default: Any = None, club_id: str | None = None) -> Any:
    branding = load_club_config(club_id).get("branding", {})
    return branding.get(name, default)


def get_season_filter(club_id: str | None = None, *, config: dict[str, Any] | None = None) -> dict[str, tuple[str, ...]]:
    data = (config or load_club_config(club_id)).get("data", {})
    season_filter = data.get("season_filter", {})
    if not isinstance(season_filter, dict):
        return {"include_seasons": (), "include_season_ids": ()}

    def normalize(values: object) -> tuple[str, ...]:
        if values is None:
            return ()
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, (list, tuple, set)):
            return ()
        cleaned = [str(value).strip() for value in values if str(value).strip()]
        return tuple(dict.fromkeys(cleaned))

    return {
        "include_seasons": normalize(season_filter.get("include_seasons")),
        "include_season_ids": normalize(season_filter.get("include_season_ids")),
    }


def normalize_club_id(value: object) -> str:
    club_id = str(value or DEFAULT_CLUB_ID).strip().casefold().replace(" ", "-")
    return club_id or DEFAULT_CLUB_ID


@lru_cache(maxsize=None)
def _load_club_config_cached(club_id: str) -> dict[str, Any]:
    config_path = CLUBS_ROOT / club_id / "club_config.yaml"
    if not config_path.exists():
        raise RuntimeError(
            f"Club config not found for '{club_id}'. Expected file: {config_path}. "
            f"Create clubs/{club_id}/club_config.yaml or unset CLUB_ID to use '{DEFAULT_CLUB_ID}'."
        )

    config_text = config_path.read_text(encoding="utf-8")
    if yaml is not None:
        try:
            loaded = yaml.safe_load(config_text) or {}
        except yaml.YAMLError as error:
            raise RuntimeError(f"Club config '{config_path}' is not valid YAML: {error}") from error
    else:
        loaded = _load_minimal_yaml(config_text)

    if not isinstance(loaded, dict):
        raise RuntimeError(f"Club config '{config_path}' must contain a YAML mapping.")

    club = loaded.get("club")
    if not isinstance(club, dict):
        raise RuntimeError(f"Club config '{config_path}' is missing the required 'club' section.")
    configured_id = normalize_club_id(club.get("club_id", club_id))
    if configured_id != club_id:
        raise RuntimeError(
            f"Club config id mismatch: loaded '{configured_id}' from {config_path}, expected '{club_id}'."
        )

    return loaded


def _load_minimal_yaml(text: str) -> dict[str, Any]:
    """Parse this repo's simple club-config YAML if PyYAML is not installed yet."""
    raw_lines = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        raw_lines.append((len(line) - len(line.lstrip(" ")), line.strip()))

    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any] | list[Any]]] = [(-1, root)]
    for index, (indent, stripped) in enumerate(raw_lines):
        while stack and indent <= stack[-1][0]:
            stack.pop()
        parent = stack[-1][1]
        if stripped.startswith("- "):
            if not isinstance(parent, list):
                raise RuntimeError("Minimal YAML parser expected a list parent.")
            parent.append(_parse_scalar(stripped[2:].strip()))
            continue

        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value:
            if not isinstance(parent, dict):
                raise RuntimeError("Minimal YAML parser expected a mapping parent.")
            parent[key] = _parse_scalar(value)
            continue

        next_is_list = False
        for next_indent, next_stripped in raw_lines[index + 1 :]:
            if next_indent <= indent:
                break
            next_is_list = next_stripped.startswith("- ")
            break
        child: dict[str, Any] | list[Any] = [] if next_is_list else {}
        if not isinstance(parent, dict):
            raise RuntimeError("Minimal YAML parser expected a mapping parent.")
        parent[key] = child
        stack.append((indent, child))
    return root


def _parse_scalar(value: str) -> Any:
    if value in {"null", "Null", "NULL", "~"}:
        return None
    if value == "[]":
        return []
    if value.casefold() == "true":
        return True
    if value.casefold() == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value
