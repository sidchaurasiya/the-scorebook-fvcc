from __future__ import annotations

import re
from typing import Any

import pandas as pd


NON_INNINGS_PATTERN = re.compile(r"\b(?:did\s+not\s+bat|dnb|absent(?:\s+hurt)?)\b", re.IGNORECASE)
NOT_OUT_PATTERN = re.compile(r"\b(?:not\s+out|retired\s+hurt)\b", re.IGNORECASE)


def _clean_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def combined_dismissal_text(frame: pd.DataFrame) -> pd.Series:
    """Combine type and text without relying on exact duplicate-free wording."""
    dismissal_type = frame.get("dismissal_type", pd.Series("", index=frame.index, dtype="object"))
    dismissal_text = frame.get("dismissal_text", pd.Series("", index=frame.index, dtype="object"))
    dismissal_type = dismissal_type.fillna("").astype(str).str.casefold().str.strip()
    dismissal_text = dismissal_text.fillna("").astype(str).str.casefold().str.strip()
    return (dismissal_type + " " + dismissal_text).str.replace(r"\s+", " ", regex=True).str.strip()


def batting_innings_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(False, index=frame.index, dtype=bool)
    text = combined_dismissal_text(frame)
    return ~text.str.contains(NON_INNINGS_PATTERN, na=False)


def not_out_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(False, index=frame.index, dtype=bool)
    text = combined_dismissal_text(frame)
    innings = batting_innings_mask(frame)
    return innings & (text.eq("") | text.str.contains(NOT_OUT_PATTERN, na=False))


def dismissed_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(False, index=frame.index, dtype=bool)
    innings = batting_innings_mask(frame)
    return innings & ~not_out_mask(frame)


def is_batting_innings_values(dismissal_type: Any = None, dismissal_text: Any = None) -> bool:
    text = f"{_clean_value(dismissal_type)} {_clean_value(dismissal_text)}".strip()
    return NON_INNINGS_PATTERN.search(text) is None


def is_not_out_values(dismissal_type: Any = None, dismissal_text: Any = None) -> bool:
    text = f"{_clean_value(dismissal_type)} {_clean_value(dismissal_text)}".strip()
    return is_batting_innings_values(dismissal_type, dismissal_text) and (
        text == "" or NOT_OUT_PATTERN.search(text) is not None
    )
