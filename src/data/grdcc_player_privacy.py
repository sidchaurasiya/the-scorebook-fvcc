"""Exact-ID GRDCC privacy status from the latest verified public source."""

from __future__ import annotations

from functools import lru_cache
import hashlib
from pathlib import Path

import pandas as pd

from src.config.club_config import REPO_ROOT, get_active_club_id, normalize_club_id


CLUB_ID = "georges-river-district"
SNAPSHOT_PATH = (
    REPO_ROOT
    / "clubs"
    / CLUB_ID
    / "data"
    / "source"
    / "grdcc_current_privacy_status.csv"
)
SNAPSHOT_COLUMNS = (
    "canonical_player_id_sha256",
    "source_participant_id_sha256",
    "status",
    "public_name",
    "verified_at",
    "source",
    "source_record_sha256",
    "source_payload_sha256",
)
IDENTITY_COLUMNS = (
    "canonical_player_id",
    "raw_player_id",
    "player_id",
    "participant_id",
)


def privacy_snapshot_path(club_id: str | None = None) -> Path:
    if normalize_club_id(club_id or get_active_club_id()) != CLUB_ID:
        return Path()
    return SNAPSHOT_PATH


def privacy_snapshot_signature(club_id: str | None = None) -> tuple[object, ...]:
    path = privacy_snapshot_path(club_id)
    if not str(path) or not path.is_file():
        return ()
    stat = path.stat()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return (str(path), stat.st_mtime_ns, stat.st_size, digest)


@lru_cache(maxsize=8)
def _load_snapshot(signature: tuple[object, ...]) -> pd.DataFrame:
    if not signature:
        return pd.DataFrame(columns=SNAPSHOT_COLUMNS)
    path = Path(str(signature[0]))
    rows = pd.read_csv(path, dtype=str).fillna("")
    missing = set(SNAPSHOT_COLUMNS) - set(rows.columns)
    if missing:
        raise ValueError(f"GRDCC privacy snapshot is missing fields: {sorted(missing)}")
    rows = rows[list(SNAPSHOT_COLUMNS)].copy()
    rows["status"] = rows["status"].astype(str).str.strip().str.casefold()
    if not rows["status"].isin({"public", "private"}).all():
        raise ValueError("GRDCC privacy snapshot contains an unsupported status")
    if rows["canonical_player_id_sha256"].duplicated().any():
        raise ValueError("GRDCC privacy snapshot requires one row per canonical identity")
    if rows["canonical_player_id_sha256"].astype(str).str.fullmatch(r"[0-9a-f]{64}").ne(True).any():
        raise ValueError("GRDCC privacy snapshot canonical identifiers must be SHA-256 fingerprints")
    if rows["source_participant_id_sha256"].astype(str).str.fullmatch(r"[0-9a-f]{64}").ne(True).any():
        raise ValueError("GRDCC privacy snapshot source identifiers must be SHA-256 fingerprints")
    public = rows["status"].eq("public")
    private = rows["status"].eq("private")
    if rows.loc[public, "public_name"].astype(str).str.strip().eq("").any():
        raise ValueError("Verified public privacy rows require a current public display name")
    if rows.loc[private, "public_name"].astype(str).str.strip().ne("").any():
        raise ValueError("Private privacy rows must not contain a public display name")
    for column in ("source_record_sha256", "source_payload_sha256"):
        if rows[column].astype(str).str.fullmatch(r"[0-9a-f]{64}").ne(True).any():
            raise ValueError(f"GRDCC privacy snapshot {column} must contain SHA-256 fingerprints")
    return rows.reset_index(drop=True)


def load_current_privacy_snapshot(club_id: str | None = None) -> pd.DataFrame:
    return _load_snapshot(privacy_snapshot_signature(club_id)).copy()


def _fingerprint(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "<na>"}:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@lru_cache(maxsize=8)
def _status_index_for_signature(signature: tuple[object, ...]) -> dict[str, dict[str, str]]:
    rows = _load_snapshot(signature)
    index: dict[str, dict[str, str]] = {}
    records = rows.to_dict("records")
    for row in records:
        fingerprint = str(row.get("canonical_player_id_sha256", "")).strip()
        if fingerprint:
            entry = {"status": row["status"], "public_name": row["public_name"]}
            existing = index.get(fingerprint)
            if existing and existing != entry:
                raise ValueError("Conflicting exact-ID GRDCC privacy decisions")
            index[fingerprint] = entry

    # A source participant key shared by multiple canonical records cannot
    # establish which person took part. Treat it as private/ambiguous even if
    # every row currently carries the same public label.
    source_counts = rows["source_participant_id_sha256"].astype(str).value_counts()
    for row in records:
        fingerprint = str(row.get("source_participant_id_sha256", "")).strip()
        if not fingerprint:
            continue
        entry = {"status": row["status"], "public_name": row["public_name"]}
        if int(source_counts.get(fingerprint, 0)) > 1:
            index[fingerprint] = {"status": "private", "public_name": ""}
            continue
        existing = index.get(fingerprint)
        if existing and existing != entry:
            index[fingerprint] = {"status": "private", "public_name": ""}
        else:
            index[fingerprint] = entry
    return index


def _status_index(club_id: str | None = None) -> dict[str, dict[str, str]]:
    return _status_index_for_signature(privacy_snapshot_signature(club_id))


def _resolve_from_index(
    index: dict[str, dict[str, str]],
    canonical_player_id: object,
    source_participant_id: object,
) -> tuple[str, str]:
    entries = [
        index[fingerprint]
        for fingerprint in (
            _fingerprint(canonical_player_id),
            _fingerprint(source_participant_id),
        )
        if fingerprint and fingerprint in index
    ]
    if not entries:
        return "", ""
    statuses = {entry["status"] for entry in entries}
    if statuses == {"private"} or len(statuses) > 1:
        return "private", ""
    names = {entry["public_name"].strip() for entry in entries if entry["public_name"].strip()}
    if len(names) != 1:
        return "private", ""
    return "public", next(iter(names))


def resolve_current_privacy(
    *,
    canonical_player_id: object = "",
    source_participant_id: object = "",
    club_id: str | None = None,
) -> tuple[str, str]:
    """Resolve exact current status; conflicting aliases fail closed as private."""
    if normalize_club_id(club_id or get_active_club_id()) != CLUB_ID:
        return "", ""
    return _resolve_from_index(
        _status_index(club_id), canonical_player_id, source_participant_id
    )


def current_privacy_overrides(
    frame: pd.DataFrame,
    club_id: str | None = None,
) -> tuple[pd.Series, pd.Series]:
    statuses = pd.Series("", index=frame.index, dtype="string")
    names = pd.Series("", index=frame.index, dtype="string")
    if frame.empty or normalize_club_id(club_id or get_active_club_id()) != CLUB_ID:
        return statuses, names

    status_index = _status_index(club_id)
    columns = [column for column in IDENTITY_COLUMNS[1:] if column in frame]
    identity = frame.reindex(columns=["canonical_player_id", *columns], fill_value="")
    decisions = []
    for canonical_id, *participants in identity.itertuples(index=False, name=None):
        participant_id = next((value for value in participants if str(value).strip()), "")
        decisions.append(_resolve_from_index(status_index, canonical_id, participant_id))
    status_values, name_values = zip(*decisions)
    return (
        pd.Series(status_values, index=frame.index, dtype="string"),
        pd.Series(name_values, index=frame.index, dtype="string"),
    )


def apply_current_privacy_presentation(
    frame: pd.DataFrame,
    club_id: str | None = None,
) -> pd.DataFrame:
    output = frame.copy()
    statuses, names = current_privacy_overrides(output, club_id)
    public = statuses.eq("public")
    if not public.any():
        return output
    for column in ("canonical_player_name", "Player", "display_player_name", "player_name"):
        if column in output:
            output.loc[public, column] = names.loc[public]
    return output
