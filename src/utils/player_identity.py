from __future__ import annotations

import re
import shutil
import unicodedata
from difflib import SequenceMatcher
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config.club_config import get_active_club_id, get_feature_flag, get_mapping_path, get_processed_path
from src.data.playcricket_ingestion import metadata_mtime, read_processed_table

DATA_DIR = Path("data")
EXPORTS_DIR = Path("exports")
BACKUPS_DIR = DATA_DIR / "backups"
PROCESSED_DIR = DATA_DIR / "processed"
ALIASES_PATH = DATA_DIR / "player_aliases.csv"
MANUAL_MERGES_PATH = DATA_DIR / "manual_player_merges.csv"
DUPLICATE_AUDIT_PATH = DATA_DIR / "player_duplicate_audit.csv"
IDENTITY_SUMMARY_PATH = DATA_DIR / "player_identity_summary.csv"
VALIDATION_PATH = DATA_DIR / "player_merge_validation.csv"
MAPPING_CONFLICTS_PATH = DATA_DIR / "player_mapping_conflicts.csv"

ALIAS_COLUMNS = [
    "canonical_player_id",
    "canonical_player_name",
    "raw_player_id",
    "raw_player_name",
    "alias_name",
    "notes",
    "is_active",
    "merge_source",
]
MANUAL_MERGE_COLUMNS = [
    "canonical_player_name",
    "raw_player_name",
    "raw_player_id",
    "notes",
]
VALIDATION_COLUMNS = [
    "canonical_player_id",
    "canonical_player_name",
    "validation_status",
    "notes",
    "reviewed_by",
    "reviewed_at",
]

PRIVATE_PLAYER_MARKERS = {
    "********",
    "private player",
    "anonymous player",
    "anonymised player",
    "anonymized player",
    "name withheld",
    "withheld",
}
PRIVATE_PLAYER_FLAG_COLUMNS = (
    "is_private",
    "is_anonymised",
    "is_anonymized",
    "privacy_flag",
    "player_is_private",
)
PLAYER_NAME_COLUMNS = (
    "canonical_player_name",
    "display_player_name",
    "raw_player_name",
    "player_name",
    "Player",
)


def player_identity_path(filename: str | Path, club_id: str | None = None) -> Path:
    return get_mapping_path(filename, club_id=club_id)


def clean_player_name(name: object) -> str:
    value = "" if pd.isna(name) else str(name)
    value = value.strip().lower()
    value = re.sub(r"[^\w\s]", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def is_private_or_anonymised_player(
    value: object = "",
    *,
    metadata: dict[str, object] | pd.Series | None = None,
) -> bool:
    """Return whether a player identity must be hidden from public UI outputs."""
    if metadata is not None:
        for column in PRIVATE_PLAYER_FLAG_COLUMNS:
            flag = metadata.get(column) if hasattr(metadata, "get") else None
            if str(flag or "").strip().casefold() in {"true", "1", "yes", "y", "private", "anonymous"}:
                return True
        for column in PLAYER_NAME_COLUMNS:
            candidate = metadata.get(column) if hasattr(metadata, "get") else None
            if candidate is not None and is_private_or_anonymised_player(candidate):
                return True

    text = "" if value is None or pd.isna(value) else re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return False
    lowered = text.casefold()
    return lowered in PRIVATE_PLAYER_MARKERS or set(text) <= {"*"}


def public_player_mask(frame: pd.DataFrame) -> pd.Series:
    """Build a public-display eligibility mask without mutating backend records."""
    if frame.empty:
        return pd.Series(dtype=bool, index=frame.index)
    private = pd.Series(False, index=frame.index)
    for column in PRIVATE_PLAYER_FLAG_COLUMNS:
        if column in frame:
            private |= frame[column].fillna("").astype(str).str.strip().str.casefold().isin(
                {"true", "1", "yes", "y", "private", "anonymous"}
            )
    for column in PLAYER_NAME_COLUMNS:
        if column in frame:
            private |= frame[column].map(is_private_or_anonymised_player)
    return ~private


def filter_public_player_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Return customer-safe player rows while retaining all backend source rows."""
    if frame.empty:
        return frame.copy()
    return frame.loc[public_player_mask(frame)].copy()


def normalize_player_name_for_strict_merge(name: object) -> str:
    """Normalize only case, spacing, accents, and punctuation for safe merge review."""
    value = "" if pd.isna(name) else str(name)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(character for character in value if not unicodedata.combining(character))
    value = value.strip().casefold()

    characters: list[str] = []
    for character in value:
        if character.isalnum():
            characters.append(character)
        elif character.isspace() or unicodedata.category(character) == "Pd":
            characters.append(" ")
    return re.sub(r"\s+", " ", "".join(characters)).strip()


GRDCC_MANUAL_CANONICAL_NAME_OVERRIDES = {
    "h milburn": ("grdcc_excel_exact_harry_milburn", "Harry Milburn"),
    "harry milburn": ("grdcc_excel_exact_harry_milburn", "Harry Milburn"),
}


def grdcc_manual_canonical_name_override(name: object) -> tuple[str, str] | None:
    return GRDCC_MANUAL_CANONICAL_NAME_OVERRIDES.get(normalize_player_name_for_strict_merge(name))


def display_player_name(name: object) -> str:
    value = "" if pd.isna(name) else str(name)
    value = re.sub(r"\s+", " ", value).strip()
    if not value:
        return ""
    return " ".join(proper_case_name_part(part) for part in value.split(" "))


def proper_case_name_part(part: str) -> str:
    if not part:
        return ""
    return "-".join(proper_case_apostrophe_piece(piece) for piece in part.split("-"))


def proper_case_apostrophe_piece(piece: str) -> str:
    if not piece:
        return ""
    return "'".join(proper_case_token(token) for token in piece.split("'"))


def proper_case_token(token: str) -> str:
    if not token:
        return ""
    return token[0].upper() + token[1:].lower()


def make_player_slug(name_or_id: object) -> str:
    value = "" if pd.isna(name_or_id) else str(name_or_id)
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    return value or "unknown_player"


def load_player_aliases(path: str | Path | None = None, *, club_id: str | None = None) -> pd.DataFrame:
    path = Path(path) if path is not None else player_identity_path(ALIASES_PATH.name, club_id=club_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        aliases = pd.DataFrame(columns=ALIAS_COLUMNS)
        aliases.to_csv(path, index=False)
        return aliases

    aliases = pd.read_csv(path, dtype=str).fillna("")
    for column in ALIAS_COLUMNS:
        if column not in aliases:
            aliases[column] = ""
    aliases = aliases[ALIAS_COLUMNS]
    if list(pd.read_csv(path, nrows=0).columns) != ALIAS_COLUMNS:
        aliases.to_csv(path, index=False)
    return aliases


def load_manual_player_merges(path: str | Path | None = None, *, club_id: str | None = None) -> pd.DataFrame:
    path = Path(path) if path is not None else player_identity_path(MANUAL_MERGES_PATH.name, club_id=club_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        manual = pd.DataFrame(columns=MANUAL_MERGE_COLUMNS)
        manual.to_csv(path, index=False)
        return manual

    manual = pd.read_csv(path, dtype=str).fillna("")
    for column in MANUAL_MERGE_COLUMNS:
        if column not in manual:
            manual[column] = ""
    manual = manual[MANUAL_MERGE_COLUMNS]
    if list(pd.read_csv(path, nrows=0).columns) != MANUAL_MERGE_COLUMNS:
        manual.to_csv(path, index=False)
    return manual


def player_aliases_mtime(path: str | Path | None = None, *, club_id: str | None = None) -> float:
    path = Path(path) if path is not None else player_identity_path(ALIASES_PATH.name, club_id=club_id)
    if not path.exists():
        load_player_aliases(path)
    manual_path = path.with_name(MANUAL_MERGES_PATH.name)
    mtimes = [candidate.stat().st_mtime for candidate in (path, manual_path) if candidate.exists()]
    return max(mtimes, default=0.0)


def load_player_merge_validation(path: str | Path | None = None, *, club_id: str | None = None) -> pd.DataFrame:
    path = Path(path) if path is not None else player_identity_path(VALIDATION_PATH.name, club_id=club_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        validation = pd.DataFrame(columns=VALIDATION_COLUMNS)
        validation.to_csv(path, index=False)
        return validation

    validation = pd.read_csv(path, dtype=str).fillna("")
    for column in VALIDATION_COLUMNS:
        if column not in validation:
            validation[column] = ""
    return validation[VALIDATION_COLUMNS]


def active_aliases(aliases_df: pd.DataFrame) -> pd.DataFrame:
    if aliases_df.empty:
        return aliases_df.copy()
    active = aliases_df["is_active"].astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})
    return aliases_df[active].copy()


def apply_player_identity_mapping(
    df: pd.DataFrame,
    aliases_df: pd.DataFrame | None = None,
    *,
    manual_merges_df: pd.DataFrame | None = None,
    club_id: str | None = None,
) -> pd.DataFrame:
    if df.empty or "player_name" not in df:
        return df.copy()

    output = df.copy()
    if "raw_player_id" not in output:
        output["raw_player_id"] = output["player_id"] if "player_id" in output else ""
    if "raw_player_name" not in output:
        output["raw_player_name"] = output["player_name"]

    output["raw_player_id"] = output["raw_player_id"].fillna("").astype(str)
    output["raw_player_name"] = output["raw_player_name"].map(display_player_name)
    output["canonical_player_id"] = output.apply(default_canonical_id, axis=1)
    output["canonical_player_name"] = output["raw_player_name"]

    aliases_df = load_player_aliases(club_id=club_id) if aliases_df is None else aliases_df.copy()
    manual_merges_df = load_manual_player_merges(club_id=club_id) if manual_merges_df is None else manual_merges_df
    manual_aliases = manual_alias_candidates(manual_merges_df, output)
    if manual_aliases:
        aliases_df = pd.concat([aliases_df, pd.DataFrame(manual_aliases)], ignore_index=True)
    aliases_df = active_aliases(aliases_df)

    if aliases_df.empty:
        return apply_grdcc_historical_exact_name_mapping(output, club_id=club_id)

    id_map = {}
    name_map = {}
    for row in aliases_df.to_dict("records"):
        canonical_id = str(row.get("canonical_player_id", "")).strip()
        canonical_name = display_player_name(row.get("canonical_player_name", ""))
        if not canonical_id or not canonical_name:
            continue
        mapped = (canonical_id, canonical_name)
        raw_id = str(row.get("raw_player_id", "")).strip()
        if raw_id:
            id_map[raw_id] = mapped
        for name_column in ["raw_player_name", "alias_name"]:
            clean_name = clean_player_name(row.get(name_column, ""))
            if clean_name:
                name_map[clean_name] = mapped

    def resolve(row: pd.Series) -> tuple[str, str]:
        raw_id = str(row.get("raw_player_id", "")).strip()
        if raw_id and raw_id in id_map:
            return id_map[raw_id]
        clean_name = clean_player_name(row.get("raw_player_name", ""))
        return name_map.get(clean_name, (row["canonical_player_id"], row["canonical_player_name"]))

    resolved = output.apply(resolve, axis=1, result_type="expand")
    output["canonical_player_id"] = resolved[0]
    output["canonical_player_name"] = resolved[1]
    return apply_grdcc_historical_exact_name_mapping(output, club_id=club_id)


def apply_grdcc_historical_exact_name_mapping(
    frame: pd.DataFrame,
    *,
    club_id: str | None = None,
) -> pd.DataFrame:
    """Merge unambiguous, non-overlapping GRDCC profiles by exact name."""
    active_club = str(club_id or get_active_club_id()).strip().casefold()
    if (
        active_club != "georges-river-district"
        or not get_feature_flag("enable_exact_name_nonoverlap_merge", False, club_id=active_club)
        or frame.empty
        or "raw_player_id" not in frame
    ):
        return frame

    output = frame.copy()
    raw_ids = output["raw_player_id"].fillna("").astype(str)
    merge_candidates = raw_ids.ne("")
    if not merge_candidates.any():
        return output

    global_map = grdcc_exact_name_nonoverlap_canonical_map(active_club, metadata_mtime())
    if global_map:
        mapped_mask = raw_ids.isin(global_map)
        if mapped_mask.any():
            mapped = raw_ids.loc[mapped_mask].map(global_map)
            output.loc[mapped_mask, "canonical_player_id"] = mapped.map(lambda value: value[0])
            output.loc[mapped_mask, "canonical_player_name"] = mapped.map(lambda value: value[1])

    name_source = output.get("raw_player_name", output.get("player_name", pd.Series("", index=output.index)))
    output["_strict_historical_name"] = name_source.map(normalize_player_name_for_strict_merge)
    season_source = output.get("season", pd.Series("", index=output.index)).fillna("").astype(str)
    output["_historical_season"] = season_source

    manual_mask = output["_strict_historical_name"].isin(GRDCC_MANUAL_CANONICAL_NAME_OVERRIDES)
    if manual_mask.any():
        mapped = output.loc[manual_mask, "_strict_historical_name"].map(GRDCC_MANUAL_CANONICAL_NAME_OVERRIDES)
        output.loc[manual_mask, "canonical_player_id"] = mapped.map(lambda value: value[0])
        output.loc[manual_mask, "canonical_player_name"] = mapped.map(lambda value: value[1])

    def safe_exact_name_tokens(tokens: list[str]) -> bool:
        if len(tokens) < 2 or any(token.isdigit() for token in tokens):
            return False
        one_letter_tokens = sum(1 for token in tokens if len(token) == 1)
        if one_letter_tokens == 0:
            return True
        return one_letter_tokens == 1 and len(tokens[-1]) > 1

    def logical_raw_id(value: object) -> str:
        text = str(value or "").strip()
        return text[4:] if text.startswith("raw_excel_") else text

    candidate_rows = output.loc[merge_candidates & output["_strict_historical_name"].ne("")].copy()
    candidate_rows["_logical_raw_id"] = candidate_rows["raw_player_id"].map(logical_raw_id)
    for normalized_name, group in candidate_rows.groupby("_strict_historical_name", sort=False):
        if normalized_name in GRDCC_MANUAL_CANONICAL_NAME_OVERRIDES:
            continue
        tokens = normalized_name.split()
        if not safe_exact_name_tokens(tokens):
            continue
        grouped_ids = group["_logical_raw_id"].fillna("").astype(str).unique().tolist()
        if len(grouped_ids) < 2:
            continue
        season_sets = {
            raw_id: set(group.loc[group["_logical_raw_id"].astype(str).eq(raw_id), "_historical_season"].dropna().astype(str))
            for raw_id in grouped_ids
        }
        has_overlap = any(
            season_sets[left] & season_sets[right]
            for index, left in enumerate(grouped_ids)
            for right in grouped_ids[index + 1 :]
        )
        if has_overlap:
            continue
        display_names = name_source.loc[group.index].map(display_player_name)
        display_name = display_names.mode().iloc[0] if not display_names.mode().empty else display_names.iloc[0]
        canonical_id = f"grdcc_excel_exact_{make_player_slug(normalized_name)}"
        merge_mask = merge_candidates & output["_strict_historical_name"].eq(normalized_name)
        output.loc[merge_mask, "canonical_player_id"] = canonical_id
        output.loc[merge_mask, "canonical_player_name"] = display_name

    return output.drop(columns=["_strict_historical_name", "_historical_season"], errors="ignore")


@st.cache_data(show_spinner=False, persist="disk")
def grdcc_exact_name_nonoverlap_canonical_map(
    club_id: str,
    local_version: float | None = None,
) -> dict[str, tuple[str, str]]:
    _ = local_version
    active_club = str(club_id or "").strip().casefold()
    if active_club != "georges-river-district" or not get_feature_flag(
        "enable_exact_name_nonoverlap_merge",
        False,
        club_id=active_club,
    ):
        return {}

    frames: list[pd.DataFrame] = []
    processed_root = get_processed_path("", club_id=active_club)
    table_paths = [
        get_processed_path("all_seasons_batting.csv", club_id=active_club),
        get_processed_path("all_seasons_bowling.csv", club_id=active_club),
        get_processed_path("all_seasons_fielding.csv", club_id=active_club),
        processed_root / "supplemental" / "excel_all_seasons_batting.csv",
        processed_root / "supplemental" / "excel_all_seasons_bowling.csv",
    ]
    for path in table_paths:
        if not path.exists():
            continue
        try:
            frame = pd.read_csv(path, low_memory=False)
        except Exception:
            continue
        if frame.empty or "raw_player_id" not in frame:
            continue
        columns = [column for column in ["raw_player_id", "raw_player_name", "player_name", "season"] if column in frame]
        if "raw_player_name" not in columns and "player_name" not in columns:
            continue
        frames.append(frame[columns].copy())

    if not frames:
        return {}

    combined = pd.concat(frames, ignore_index=True)
    raw_ids = combined["raw_player_id"].fillna("").astype(str).str.strip()
    name_source = combined.get("raw_player_name", combined.get("player_name", pd.Series("", index=combined.index)))
    combined["_strict_name"] = name_source.map(normalize_player_name_for_strict_merge)
    combined["_season"] = combined.get("season", pd.Series("", index=combined.index)).fillna("").astype(str).str.strip()
    combined = combined[raw_ids.ne("") & combined["_strict_name"].ne("")].copy()
    if combined.empty:
        return {}

    def safe_exact_name_tokens(tokens: list[str]) -> bool:
        if len(tokens) < 2 or any(token.isdigit() for token in tokens):
            return False
        one_letter_tokens = sum(1 for token in tokens if len(token) == 1)
        if one_letter_tokens == 0:
            return True
        return one_letter_tokens == 1 and len(tokens[-1]) > 1

    def logical_raw_id(value: object) -> str:
        text = str(value or "").strip()
        return text[4:] if text.startswith("raw_excel_") else text

    combined["_logical_raw_id"] = combined["raw_player_id"].map(logical_raw_id)
    canonical_map: dict[str, tuple[str, str]] = {}
    for strict_name, canonical in GRDCC_MANUAL_CANONICAL_NAME_OVERRIDES.items():
        manual_rows = combined[combined["_strict_name"].eq(strict_name)]
        for raw_id in manual_rows["raw_player_id"].fillna("").astype(str).str.strip().unique().tolist():
            canonical_map[raw_id] = canonical

    for normalized_name, group in combined.groupby("_strict_name", sort=False):
        if normalized_name in GRDCC_MANUAL_CANONICAL_NAME_OVERRIDES:
            continue
        if not safe_exact_name_tokens(normalized_name.split()):
            continue
        grouped_ids = group["_logical_raw_id"].fillna("").astype(str).str.strip().unique().tolist()
        if len(grouped_ids) < 2:
            continue
        season_sets = {
            raw_id: set(group.loc[group["_logical_raw_id"].astype(str).eq(raw_id), "_season"].dropna().astype(str))
            for raw_id in grouped_ids
        }
        has_overlap = any(
            season_sets[left] & season_sets[right]
            for index, left in enumerate(grouped_ids)
            for right in grouped_ids[index + 1 :]
        )
        if has_overlap:
            continue
        display_names = name_source.loc[group.index].map(display_player_name)
        display_name = display_names.mode().iloc[0] if not display_names.mode().empty else display_names.iloc[0]
        canonical_id = f"grdcc_excel_exact_{make_player_slug(normalized_name)}"
        for raw_id in group["raw_player_id"].fillna("").astype(str).str.strip().unique().tolist():
            canonical_map[raw_id] = (canonical_id, display_name)
    return canonical_map


def default_canonical_id(row: pd.Series) -> str:
    raw_id = str(row.get("raw_player_id", "")).strip()
    if raw_id:
        if raw_id.startswith("raw_"):
            return raw_id
        return f"raw_{make_player_slug(raw_id)}"
    return make_player_slug(row.get("raw_player_name", ""))


def canonical_group_key(df: pd.DataFrame) -> pd.Series:
    if "canonical_player_id" in df:
        canonical_id = df["canonical_player_id"].fillna("").astype(str).str.strip()
        fallback = df.get("canonical_player_name", df.get("player_name", pd.Series(index=df.index, dtype="object")))
        fallback = fallback.fillna("").astype(str).str.strip().str.casefold()
        return canonical_id.where(canonical_id != "", fallback)
    if "player_id" in df:
        player_id = df["player_id"].fillna("").astype(str).str.strip()
        fallback = df["player_name"].fillna("").astype(str).str.strip().str.casefold()
        return player_id.where(player_id != "", fallback)
    return df["player_name"].fillna("").astype(str).str.strip().str.casefold()


def generate_duplicate_audit(
    df: pd.DataFrame,
    path: str | Path | None = None,
    *,
    club_id: str | None = None,
) -> pd.DataFrame:
    path = Path(path) if path is not None else player_identity_path(DUPLICATE_AUDIT_PATH.name, club_id=club_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    profiles = build_raw_profile_summary(df)
    if len(profiles) < 2:
        profiles.head(0).to_csv(path, index=False)
        return profiles.head(0)

    rows = []
    try:
        from rapidfuzz import fuzz  # type: ignore

        def similarity(a: str, b: str) -> float:
            return float(fuzz.token_sort_ratio(a, b))

    except Exception:

        def similarity(a: str, b: str) -> float:
            return SequenceMatcher(None, a, b).ratio() * 100

    records = profiles.to_dict("records")
    for index, left in enumerate(records):
        for right in records[index + 1 :]:
            if left["raw_player_id"] and left["raw_player_id"] == right["raw_player_id"]:
                continue
            score = similarity(left["clean_name"], right["clean_name"])
            initials_match = initials_signature(left["raw_player_name"]) == initials_signature(right["raw_player_name"])
            if score < 85 and not initials_match:
                continue
            rows.append(
                {
                    "player_name_a": left["raw_player_name"],
                    "player_name_b": right["raw_player_name"],
                    "raw_player_id_a": left["raw_player_id"],
                    "raw_player_id_b": right["raw_player_id"],
                    "similarity_score": round(score, 1),
                    "teams_seen_a": left["teams_seen"],
                    "teams_seen_b": right["teams_seen"],
                    "seasons_seen_a": left["seasons_seen"],
                    "seasons_seen_b": right["seasons_seen"],
                    "total_matches_a": left["total_matches"],
                    "total_matches_b": right["total_matches"],
                    "total_runs_a": left["total_runs"],
                    "total_runs_b": right["total_runs"],
                    "total_wickets_a": left["total_wickets"],
                    "total_wickets_b": right["total_wickets"],
                    "suggested_reason": "High name similarity" if score >= 85 else "Initial/name variant match",
                }
            )

    audit = pd.DataFrame(rows)
    if not audit.empty:
        audit = audit.sort_values("similarity_score", ascending=False)
    audit.to_csv(path, index=False)
    return audit


def initials_signature(name: object) -> str:
    words = clean_player_name(name).split()
    if not words:
        return ""
    return "".join(word[0] for word in words)


def build_raw_profile_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    output = apply_player_identity_mapping(df, pd.DataFrame(columns=ALIAS_COLUMNS))
    output["profile_key"] = output["raw_player_id"].where(
        output["raw_player_id"].astype(str).str.strip() != "",
        output["raw_player_name"].map(make_player_slug),
    )
    for column in ["matches", "battingAggregate", "bowlingWickets"]:
        if column not in output:
            output[column] = 0
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)
    grouped = output.groupby("profile_key", as_index=False).agg(
        raw_player_id=("raw_player_id", "first"),
        raw_player_name=("raw_player_name", "first"),
        teams_seen=("team_name", join_unique_values) if "team_name" in output else ("raw_player_name", "first"),
        seasons_seen=("season", join_unique_values) if "season" in output else ("raw_player_name", "first"),
        total_matches=("matches", "max"),
        total_runs=("battingAggregate", "sum"),
        total_wickets=("bowlingWickets", "sum"),
    )
    grouped["clean_name"] = grouped["raw_player_name"].map(clean_player_name)
    return grouped


def summarise_player_identity_mapping(
    df: pd.DataFrame,
    aliases_df: pd.DataFrame | None = None,
    path: str | Path | None = None,
    *,
    club_id: str | None = None,
) -> pd.DataFrame:
    path = Path(path) if path is not None else player_identity_path(IDENTITY_SUMMARY_PATH.name, club_id=club_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    mapped = apply_player_identity_mapping(df, aliases_df)
    raw_count = mapped[["raw_player_id", "raw_player_name"]].drop_duplicates().shape[0]
    canonical_count = mapped[["canonical_player_id", "canonical_player_name"]].drop_duplicates().shape[0]
    alias_counts = (
        mapped[["canonical_player_id", "canonical_player_name", "raw_player_id", "raw_player_name"]]
        .drop_duplicates()
        .groupby(["canonical_player_id", "canonical_player_name"], as_index=False)
        .size()
        .rename(columns={"size": "raw_profile_count"})
        .sort_values("raw_profile_count", ascending=False)
    )
    summary = alias_counts.copy()
    summary.insert(0, "raw_unique_player_identities", raw_count)
    summary.insert(1, "canonical_player_identities", canonical_count)
    summary["aliases_merged"] = (summary["raw_profile_count"] - 1).clip(lower=0)
    summary.to_csv(path, index=False)
    return summary


def join_unique_values(values: pd.Series) -> str:
    labels = []
    for value in values.dropna().astype(str):
        value = re.sub(r"\s+", " ", value).strip()
        if value and value not in labels:
            labels.append(value)
    return ", ".join(labels)


def ensure_identity_exports(
    df: pd.DataFrame,
    aliases_df: pd.DataFrame | None = None,
    *,
    club_id: str | None = None,
) -> dict[str, int]:
    aliases_df = load_player_aliases(club_id=club_id) if aliases_df is None else aliases_df
    duplicate_audit = generate_duplicate_audit(df, club_id=club_id)
    summary = summarise_player_identity_mapping(df, aliases_df, club_id=club_id)
    load_player_merge_validation(club_id=club_id)
    return {
        "possible_duplicates": len(duplicate_audit),
        "summary_rows": len(summary),
    }


def ensure_player_alias_mappings(
    source_df: pd.DataFrame | None = None,
    *,
    club_id: str | None = None,
) -> dict[str, int]:
    """Append confirmed mappings without mutating raw PlayCricket data.

    Mapping priority is:
    1. existing player_aliases.csv
    2. manual_player_merges.csv
    3. exact 100-score duplicate audit suggestions

    Conflicts are written to data/player_mapping_conflicts.csv and skipped.
    """
    aliases_path = player_identity_path(ALIASES_PATH.name, club_id=club_id)
    aliases = load_player_aliases(aliases_path)
    manual = load_manual_player_merges(club_id=club_id)
    audit = load_duplicate_audit(club_id=club_id)
    candidates = []
    candidates.extend(manual_alias_candidates(manual, source_df))
    candidates.extend(auto_similarity_100_candidates(audit, source_df))

    if not candidates:
        write_mapping_conflicts([], club_id=club_id)
        return {"added": 0, "conflicts": 0, "manual_candidates": 0, "auto_candidates": 0}

    existing_rows = aliases.to_dict("records")
    added_rows: list[dict[str, str]] = []
    conflicts: list[dict[str, str]] = []
    id_map, name_map, display_map = existing_mapping_indexes(existing_rows)

    manual_count = 0
    auto_count = 0
    for candidate in candidates:
        source = candidate.get("merge_source", "")
        if source == "manual_confirmed":
            manual_count += 1
        elif source == "auto_similarity_100":
            auto_count += 1

        conflict = mapping_conflict(candidate, id_map, name_map, display_map)
        if conflict:
            conflicts.append({**candidate, "conflict_reason": conflict})
            continue
        if alias_exists(candidate, existing_rows, added_rows):
            continue

        added_rows.append(candidate)
        register_mapping(candidate, id_map, name_map, display_map)

    if added_rows:
        backup_player_aliases(aliases_path)
        aliases = pd.concat([aliases, pd.DataFrame(added_rows)], ignore_index=True)
        aliases = aliases[ALIAS_COLUMNS].fillna("")
        aliases.to_csv(aliases_path, index=False)

    write_mapping_conflicts(conflicts, club_id=club_id)
    return {
        "added": len(added_rows),
        "conflicts": len(conflicts),
        "manual_candidates": manual_count,
        "auto_candidates": auto_count,
    }


def load_duplicate_audit(path: str | Path | None = None, *, club_id: str | None = None) -> pd.DataFrame:
    path = Path(path) if path is not None else player_identity_path(DUPLICATE_AUDIT_PATH.name, club_id=club_id)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def manual_alias_candidates(
    manual: pd.DataFrame,
    source_df: pd.DataFrame | None = None,
) -> list[dict[str, str]]:
    rows = []
    if manual.empty:
        return rows
    for item in manual.to_dict("records"):
        canonical_name = display_player_name(item.get("canonical_player_name", ""))
        raw_name = display_player_name(item.get("raw_player_name", ""))
        raw_id = str(item.get("raw_player_id", "")).strip()
        if not canonical_name or (not raw_name and not raw_id):
            continue
        raw_name = raw_name or lookup_raw_name(raw_id, source_df)
        rows.append(
            alias_row(
                canonical_name=canonical_name,
                raw_name=raw_name,
                raw_id=raw_id,
                notes=display_player_name(item.get("notes", "")) or "manual confirmed merge",
                merge_source="manual_confirmed",
            )
        )
    return rows


def auto_similarity_100_candidates(
    audit: pd.DataFrame,
    source_df: pd.DataFrame | None = None,
) -> list[dict[str, str]]:
    if audit.empty or "similarity_score" not in audit:
        return []

    exact = audit[pd.to_numeric(audit["similarity_score"], errors="coerce") == 100].copy()
    if exact.empty:
        return []

    components = connected_duplicate_components(exact)
    rows = []
    for component in components:
        canonical_name = choose_canonical_name(component, source_df)
        for raw_id, raw_name in sorted(component):
            rows.append(
                alias_row(
                    canonical_name=canonical_name,
                    raw_name=raw_name,
                    raw_id=raw_id,
                    notes="auto-added from 100 similarity duplicate audit",
                    merge_source="auto_similarity_100",
                )
            )
    return rows


def connected_duplicate_components(audit: pd.DataFrame) -> list[set[tuple[str, str]]]:
    graph: dict[tuple[str, str], set[tuple[str, str]]] = {}
    for row in audit.to_dict("records"):
        left = (str(row.get("raw_player_id_a", "")).strip(), display_player_name(row.get("player_name_a", "")))
        right = (str(row.get("raw_player_id_b", "")).strip(), display_player_name(row.get("player_name_b", "")))
        if not left[1] or not right[1]:
            continue
        graph.setdefault(left, set()).add(right)
        graph.setdefault(right, set()).add(left)

    seen = set()
    components = []
    for node in graph:
        if node in seen:
            continue
        stack = [node]
        component = set()
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.add(current)
            stack.extend(graph.get(current, set()) - seen)
        if len(component) > 1:
            components.append(component)
    return components


def choose_canonical_name(
    component: set[tuple[str, str]],
    source_df: pd.DataFrame | None = None,
) -> str:
    counts: dict[str, int] = {}
    if source_df is not None and not source_df.empty and "raw_player_name" in source_df:
        raw_ids = {raw_id for raw_id, _ in component if raw_id}
        names = {clean_player_name(name) for _, name in component}
        source = source_df.copy()
        mask = source["raw_player_id"].fillna("").astype(str).str.strip().isin(raw_ids)
        mask = mask | source["raw_player_name"].map(clean_player_name).isin(names)
        for name in source.loc[mask, "raw_player_name"].dropna().map(display_player_name):
            counts[name] = counts.get(name, 0) + 1
    for _, name in component:
        clean = display_player_name(name)
        counts.setdefault(clean, 0)
    return sorted(counts, key=lambda name: (counts[name], len(name), name), reverse=True)[0]


def alias_row(
    *,
    canonical_name: str,
    raw_name: str,
    raw_id: str,
    notes: str,
    merge_source: str,
) -> dict[str, str]:
    canonical_name = display_player_name(canonical_name)
    raw_name = display_player_name(raw_name)
    return {
        "canonical_player_id": make_player_slug(canonical_name),
        "canonical_player_name": canonical_name,
        "raw_player_id": str(raw_id).strip(),
        "raw_player_name": raw_name,
        "alias_name": raw_name,
        "notes": notes,
        "is_active": "true",
        "merge_source": merge_source,
    }


def lookup_raw_name(raw_id: str, source_df: pd.DataFrame | None) -> str:
    if source_df is None or source_df.empty or not raw_id or "raw_player_id" not in source_df:
        return ""
    matches = source_df[source_df["raw_player_id"].fillna("").astype(str).str.strip() == raw_id]
    if matches.empty or "raw_player_name" not in matches:
        return ""
    return display_player_name(matches["raw_player_name"].dropna().astype(str).mode().iloc[0])


def existing_mapping_indexes(rows: list[dict[str, str]]) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    id_map: dict[str, str] = {}
    name_map: dict[str, str] = {}
    display_map: dict[str, str] = {}
    for row in rows:
        register_mapping(row, id_map, name_map, display_map)
    return id_map, name_map, display_map


def register_mapping(
    row: dict[str, str],
    id_map: dict[str, str],
    name_map: dict[str, str],
    display_map: dict[str, str],
) -> None:
    canonical_id = str(row.get("canonical_player_id", "")).strip()
    canonical_name = display_player_name(row.get("canonical_player_name", ""))
    raw_id = str(row.get("raw_player_id", "")).strip()
    raw_name = clean_player_name(row.get("raw_player_name", ""))
    if raw_id:
        id_map[raw_id] = canonical_id
    if raw_name:
        name_map[raw_name] = canonical_id
    if canonical_name:
        display_map[clean_player_name(canonical_name)] = canonical_id


def mapping_conflict(
    row: dict[str, str],
    id_map: dict[str, str],
    name_map: dict[str, str],
    display_map: dict[str, str],
) -> str:
    canonical_id = str(row.get("canonical_player_id", "")).strip()
    raw_id = str(row.get("raw_player_id", "")).strip()
    raw_name = clean_player_name(row.get("raw_player_name", ""))
    canonical_display = clean_player_name(row.get("canonical_player_name", ""))
    if raw_id and raw_id in id_map and id_map[raw_id] != canonical_id:
        return "raw_player_id mapped to another canonical player"
    if raw_name and raw_name in name_map and name_map[raw_name] != canonical_id:
        return "raw_player_name mapped to another canonical player"
    if canonical_display and canonical_display in display_map and display_map[canonical_display] != canonical_id:
        return "canonical display name has another canonical ID"
    return ""


def alias_exists(
    row: dict[str, str],
    existing_rows: list[dict[str, str]],
    added_rows: list[dict[str, str]],
) -> bool:
    raw_id = str(row.get("raw_player_id", "")).strip()
    raw_name = clean_player_name(row.get("raw_player_name", ""))
    canonical_id = str(row.get("canonical_player_id", "")).strip()
    for existing in [*existing_rows, *added_rows]:
        existing_canonical = str(existing.get("canonical_player_id", "")).strip()
        existing_raw_id = str(existing.get("raw_player_id", "")).strip()
        existing_raw_name = clean_player_name(existing.get("raw_player_name", ""))
        if existing_canonical != canonical_id:
            continue
        if raw_id and raw_id == existing_raw_id:
            return True
        if not raw_id and raw_name and raw_name == existing_raw_name:
            return True
    return False


def backup_player_aliases(path: str | Path | None = None, *, club_id: str | None = None) -> None:
    aliases_path = Path(path) if path is not None else player_identity_path(ALIASES_PATH.name, club_id=club_id)
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)
    if aliases_path.exists():
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        shutil.copy2(aliases_path, BACKUPS_DIR / f"{aliases_path.stem}_{timestamp}.csv")


def write_mapping_conflicts(conflicts: list[dict[str, str]], *, club_id: str | None = None) -> None:
    path = player_identity_path(MAPPING_CONFLICTS_PATH.name, club_id=club_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = [*ALIAS_COLUMNS, "conflict_reason"]
    frame = pd.DataFrame(conflicts)
    for column in columns:
        if column not in frame:
            frame[column] = ""
    frame[columns].to_csv(path, index=False)


def rebuild_canonical_processed_tables(
    table_names: tuple[str, ...] = (
        "all_seasons_batting",
        "all_seasons_bowling",
        "all_seasons_fielding",
    ),
    processed_dir: str | Path = PROCESSED_DIR,
    *,
    club_id: str | None = None,
) -> dict[str, int]:
    """Persist canonical fields into processed CSVs only.

    Raw PlayCricket JSON files are never touched. If aliases are edited later,
    this function can be run again and the app also reapplies mappings at load
    time, so the workflow remains reversible.
    """
    aliases = load_player_aliases(club_id=club_id)
    processed_path = Path(processed_dir)
    row_counts: dict[str, int] = {}
    for table_name in table_names:
        path = processed_path / f"{table_name}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if frame.empty or "player_name" not in frame:
            continue
        mapped = apply_player_identity_mapping(frame, aliases, club_id=club_id)
        mapped.to_csv(path, index=False)
        row_counts[table_name] = len(mapped)
    return row_counts


@st.cache_data(show_spinner=False, persist="disk")
def load_portability_player_profile_source_frames(
    club_id: str,
    local_version: float,
    identity_version: float,
) -> dict[str, pd.DataFrame]:
    """Prepare canonical FVCC/GRDCC source frames once per governed version."""
    del local_version, identity_version
    aliases = load_player_aliases(club_id=club_id)
    frames = {}
    for category in ["batting", "bowling", "fielding"]:
        try:
            frame = read_processed_table(f"all_seasons_{category}")
            frames[category] = apply_player_identity_mapping(frame, aliases, club_id=club_id) if not frame.empty else frame
        except MemoryError:
            frames[category] = pd.DataFrame()
    return frames


@st.cache_data(show_spinner=False, persist="disk")
def get_player_profile_data(
    canonical_player_id: str,
    local_version: float | None = None,
    identity_version: float | None = None,
    club_id: str | None = None,
) -> dict[str, pd.DataFrame | dict[str, str]]:
    """Data helper for the future Player Profile page.

    Returns canonical identity, raw aliases, career source rows, season-by-season
    rows, and team/grade breakdown for one canonical player. The caller can use
    these raw totals to recalculate profile metrics without averaging averages.
    """
    local_version = metadata_mtime() if local_version is None else local_version
    identity_version = player_aliases_mtime(club_id=club_id) if identity_version is None else identity_version
    active_club_id = str(club_id or get_active_club_id()).strip().casefold()
    if active_club_id in {"fvcc", "georges-river-district"}:
        prepared_frames = load_portability_player_profile_source_frames(
            active_club_id,
            local_version,
            identity_version,
        )
        frames = {category: frame.copy() for category, frame in prepared_frames.items()}
    else:
        aliases = load_player_aliases(club_id=club_id)
        frames = {}
        for category in ["batting", "bowling", "fielding"]:
            try:
                frame = read_processed_table(f"all_seasons_{category}")
                frames[category] = apply_player_identity_mapping(frame, aliases, club_id=club_id) if not frame.empty else frame
            except MemoryError:
                frames[category] = pd.DataFrame()

    canonical_player_id = str(canonical_player_id).strip()
    selected_ids = {canonical_player_id}
    if active_club_id == "georges-river-district":
        selected_names: set[str] = set()
        for frame in frames.values():
            if frame.empty or "canonical_player_id" not in frame or "canonical_player_name" not in frame:
                continue
            matches = frame["canonical_player_id"].fillna("").astype(str).str.strip().eq(canonical_player_id)
            selected_names.update(
                frame.loc[matches, "canonical_player_name"]
                .dropna()
                .map(normalize_player_name_for_strict_merge)
                .loc[lambda series: series.ne("")]
                .tolist()
            )
        if selected_names:
            for frame in frames.values():
                if frame.empty or "canonical_player_id" not in frame or "canonical_player_name" not in frame:
                    continue
                same_name = frame["canonical_player_name"].map(normalize_player_name_for_strict_merge).isin(selected_names)
                selected_ids.update(frame.loc[same_name, "canonical_player_id"].fillna("").astype(str).str.strip().tolist())
        selected_ids.discard("")

    scoped = {}
    for category, frame in frames.items():
        if frame.empty or "canonical_player_id" not in frame:
            scoped[category] = frame.head(0).copy()
        else:
            scoped[category] = frame[frame["canonical_player_id"].fillna("").astype(str).str.strip().isin(selected_ids)].copy()
    all_rows = pd.concat([frame for frame in scoped.values() if not frame.empty], ignore_index=True) if any(not frame.empty for frame in scoped.values()) else pd.DataFrame()
    info = {
        "canonical_player_id": canonical_player_id,
        "canonical_player_name": "",
    }
    if not all_rows.empty and "canonical_player_name" in all_rows:
        info["canonical_player_name"] = display_player_name(all_rows["canonical_player_name"].dropna().astype(str).iloc[0])

    raw_aliases = (
        all_rows[["raw_player_id", "raw_player_name"]].drop_duplicates()
        if {"raw_player_id", "raw_player_name"}.issubset(all_rows.columns)
        else pd.DataFrame(columns=["raw_player_id", "raw_player_name"])
    )
    season_rows = (
        all_rows.groupby("season", as_index=False).size().rename(columns={"size": "source_rows"})
        if "season" in all_rows and not all_rows.empty
        else pd.DataFrame(columns=["season", "source_rows"])
    )
    team_grade = (
        all_rows[["season", "team_name", "grade_name"]].drop_duplicates()
        if {"season", "team_name", "grade_name"}.issubset(all_rows.columns)
        else pd.DataFrame(columns=["season", "team_name", "grade_name"])
    )
    return {
        "player_info": info,
        "raw_aliases": raw_aliases,
        "batting": scoped["batting"],
        "bowling": scoped["bowling"],
        "fielding": scoped["fielding"],
        "season_rows": season_rows,
        "team_grade_breakdown": team_grade,
    }
