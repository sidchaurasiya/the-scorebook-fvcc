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
    data_config = load_club_config(club_id).get("data", {})
    if key not in data_config:
        raise KeyError(f"Data path '{key}' is not configured for club '{club_id or get_active_club_id()}'.")
    path = Path(str(data_config[key]))
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.joinpath(*parts)


def get_feature_flag(name: str, default: bool = False, club_id: str | None = None) -> bool:
    features = load_club_config(club_id).get("features", {})
    value = features.get(name, default)
    if isinstance(value, str):
        return value.strip().casefold() in {"1", "true", "yes", "on"}
    return bool(value)


def get_branding_value(name: str, default: Any = None, club_id: str | None = None) -> Any:
    branding = load_club_config(club_id).get("branding", {})
    return branding.get(name, default)


def normalize_club_id(value: object) -> str:
    club_id = str(value or DEFAULT_CLUB_ID).strip().casefold().replace(" ", "-")
    return club_id or DEFAULT_CLUB_ID


@lru_cache(maxsize=None)
def _load_club_config_cached(club_id: str) -> dict[str, Any]:
    config_path = CLUBS_ROOT / club_id / "club_config.yaml"
    if not config_path.exists():
        raise RuntimeError(
            f"Club config not found for '{club_id}'. Expected file: {config_path}"
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
    if value.casefold() == "true":
        return True
    if value.casefold() == "false":
        return False
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value
