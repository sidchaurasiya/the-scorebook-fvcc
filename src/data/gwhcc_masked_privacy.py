"""Keep reused masked Hawks source identifiers generic and unlinked.

The identifiers below are fingerprints of two reused masked PlayCricket
participant tokens. They are not person identities and are scoped to the
Glen Waverley Hawks only. Numeric scorecard evidence is retained.
"""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Iterable, Mapping

import pandas as pd


HAWKS_CLUB_ID = "glen-waverley-hawks"
PRIVATE_PLAYER_LABEL = "Private player"
MASKED_HAWKS_PARTICIPANT_ID_SHA256 = frozenset(
    {
        "7ac1b8d7010bb6cd3a3e84e7f90136b880bbc899e428ece49333372911ab9052",
        "90d5b0a26955772ebda61cd86cef90ec4f0a4efd29b8a7099df640bc94a8cc0a",
    }
)

ID_COLUMNS = frozenset(
    {
        "player_id",
        "participant_id",
        "raw_player_id",
        "source_participant_id",
        "striker_participant_id",
        "bowler_participant_id",
        "batter_participant_id",
        "fielder_participant_id",
        "dismissed_player_participant_id",
        "participant_1_id",
        "participant_2_id",
        "player_1_id",
        "player_2_id",
        "canonical_player_id",
        "player_key",
        "player_1_canonical_id",
        "player_2_canonical_id",
    }
)
NAME_COLUMNS = frozenset(
    {
        "player_name",
        "raw_player_name",
        "canonical_player_name",
        "display_player_name",
        "player_1_name",
        "player_2_name",
        "striker_name",
        "batter_name",
        "bowler_name",
        "fielder_name",
    }
)
GENERIC_LABELS = frozenset(
    {
        "private player",
        "anonymous player",
        "anonymised player",
        "anonymized player",
        "masked player",
        "unknown",
        "unknown player",
        "name withheld",
        "withheld",
    }
)


def text_value(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"nan", "none"} else text


def participant_fingerprint(value: object) -> str:
    return hashlib.sha256(text_value(value).encode("utf-8")).hexdigest()


def is_masked_hawks_participant_id(
    value: object,
    *,
    fingerprints: Iterable[str] = MASKED_HAWKS_PARTICIPANT_ID_SHA256,
) -> bool:
    text = text_value(value)
    return bool(text) and participant_fingerprint(text) in set(fingerprints)


def is_generic_player_label(value: object) -> bool:
    text = text_value(value)
    return (
        not text
        or text.casefold() in GENERIC_LABELS
        or set(text) <= {"*", "•"}
    )


def normalize_link_label(value: object) -> str:
    return " ".join(text_value(value).casefold().split())


def scorecard_link_key(match_id: object, name: object) -> tuple[str, str] | None:
    match_text = text_value(match_id)
    name_text = normalize_link_label(name)
    if not match_text or not name_text:
        return None
    return match_text, hashlib.sha256(name_text.encode("utf-8")).hexdigest()


def collect_ambiguous_scorecard_link_keys(
    rows: Iterable[Mapping[str, object]] | pd.DataFrame,
    *,
    fingerprints: Iterable[str] = MASKED_HAWKS_PARTICIPANT_ID_SHA256,
) -> set[tuple[str, str]]:
    records = rows.to_dict("records") if isinstance(rows, pd.DataFrame) else rows
    keys: set[tuple[str, str]] = set()
    for row in records:
        participant_id = next(
            (text_value(row.get(column)) for column in ("participant_id", "player_id", "raw_player_id")
             if text_value(row.get(column))),
            "",
        )
        if not is_masked_hawks_participant_id(participant_id, fingerprints=fingerprints):
            continue
        label = next(
            (text_value(row.get(column)) for column in ("player_name", "raw_player_name", "canonical_player_name")
             if text_value(row.get(column))),
            "",
        )
        if is_generic_player_label(label):
            continue
        key = scorecard_link_key(row.get("match_id"), label)
        if key:
            keys.add(key)
    return keys


def mask_hawks_participant_rows(
    frame: pd.DataFrame,
    *,
    id_columns: Iterable[str] | None = None,
    name_columns: Iterable[str] | None = None,
    fingerprints: Iterable[str] = MASKED_HAWKS_PARTICIPANT_ID_SHA256,
) -> tuple[pd.DataFrame, int]:
    """Mask rows by exact reused participant-token fingerprint, keeping stats."""
    output = frame.copy()
    ids = [column for column in (id_columns or ID_COLUMNS) if column in output.columns]
    names = [column for column in (name_columns or NAME_COLUMNS) if column in output.columns]
    if output.empty or not ids:
        return output, 0
    masked = masked_hawks_participant_mask(output, id_columns=ids, fingerprints=fingerprints)
    count = int(masked.sum())
    if not count:
        return output, 0
    for column in names:
        output.loc[masked, column] = PRIVATE_PLAYER_LABEL
    for column in ids:
        output.loc[masked, column] = ""
    return output, count


def masked_hawks_participant_mask(
    frame: pd.DataFrame,
    *,
    id_columns: Iterable[str] | None = None,
    fingerprints: Iterable[str] = MASKED_HAWKS_PARTICIPANT_ID_SHA256,
) -> pd.Series:
    ids = [column for column in (id_columns or ID_COLUMNS) if column in frame.columns]
    masked = pd.Series(False, index=frame.index)
    fingerprint_set = set(fingerprints)
    for column in ids:
        masked |= frame[column].map(
            lambda value: is_masked_hawks_participant_id(value, fingerprints=fingerprint_set)
        )
    return masked


def sanitize_hawks_source_frames(
    frames: Mapping[str, pd.DataFrame],
    *,
    club_id: str | None,
    fingerprints: Iterable[str] = MASKED_HAWKS_PARTICIPANT_ID_SHA256,
) -> dict[str, pd.DataFrame]:
    """Anonymize reused source tokens in memory before club-specific builders run."""
    copied = {name: frame.copy() for name, frame in frames.items()}
    if str(club_id or "").strip().casefold() != HAWKS_CLUB_ID:
        return copied
    output: dict[str, pd.DataFrame] = {}
    for name, frame in copied.items():
        if not isinstance(frame, pd.DataFrame) or frame.empty:
            output[name] = frame
            continue
        mask = masked_hawks_participant_mask(frame, fingerprints=fingerprints)
        sanitized, _ = mask_hawks_participant_rows(frame, fingerprints=fingerprints)
        if mask.any():
            sanitized["_gwhcc_masked_placeholder"] = mask
        output[name] = sanitized
    return output


def exclude_hawks_masked_source_rows(frames: Mapping[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Exclude anonymous source rows from person-level aggregate builders."""
    output: dict[str, pd.DataFrame] = {}
    for name, frame in frames.items():
        if isinstance(frame, pd.DataFrame) and "_gwhcc_masked_placeholder" in frame:
            output[name] = frame.loc[~frame["_gwhcc_masked_placeholder"].fillna(False).astype(bool)].drop(
                columns=["_gwhcc_masked_placeholder"]
            ).copy()
        else:
            output[name] = frame.copy() if isinstance(frame, pd.DataFrame) else frame
    return output


def mask_scorecard_record_links(
    frame: pd.DataFrame,
    link_keys: Iterable[tuple[str, str]],
) -> tuple[pd.DataFrame, int]:
    """Remove inferred profile identity from same-match name-only links."""
    output = frame.copy()
    key_set = set(link_keys)
    if output.empty or not {"match_id", "canonical_player_name"} <= set(output.columns):
        return output, 0
    masked = output["canonical_player_name"].map(is_generic_player_label)
    masked |= output.apply(
        lambda row: scorecard_link_key(row.get("match_id"), row.get("canonical_player_name")) in key_set,
        axis=1,
    )
    changed = pd.Series(False, index=output.index)
    for column in NAME_COLUMNS:
        if column in output:
            changed |= masked & output[column].fillna("").astype(str).ne(PRIVATE_PLAYER_LABEL)
    for column in ID_COLUMNS:
        if column in output:
            changed |= masked & output[column].fillna("").astype(str).str.strip().ne("")
    count = int(changed.sum())
    if not count:
        return output, 0
    for column in NAME_COLUMNS:
        if column in output:
            output.loc[changed, column] = PRIVATE_PLAYER_LABEL
    for column in ID_COLUMNS:
        if column in output:
            output.loc[changed, column] = ""
    return output, count


def _read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv_rows(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def sanitize_hawks_processed_tree(processed_dir: str | Path) -> dict[str, int]:
    """Idempotently sanitize public processed outputs for the two reused IDs."""
    processed = Path(processed_dir)
    scorecard_paths = [
        processed / name
        for name in (
            "all_seasons_scorecard_batting.csv",
            "all_seasons_scorecard_bowling.csv",
            "all_seasons_scorecard_fielding.csv",
        )
    ]
    source_rows: list[dict[str, str]] = []
    for path in scorecard_paths:
        if path.exists():
            _, rows = _read_csv_rows(path)
            source_rows.extend(rows)
    link_keys = collect_ambiguous_scorecard_link_keys(source_rows)
    changed: dict[str, int] = {}
    for path in sorted(processed.rglob("*.csv")):
        columns, rows = _read_csv_rows(path)
        if not rows:
            continue
        if path.name == "scorecard_record_links.csv":
            frame = pd.DataFrame(rows, columns=columns)
            sanitized, count = mask_scorecard_record_links(frame, link_keys)
            if count:
                _write_csv_rows(path, columns, sanitized.fillna("").to_dict("records"))
                changed[path.relative_to(processed).as_posix()] = count
            continue
        id_columns = [column for column in columns if column in ID_COLUMNS]
        name_columns = [column for column in columns if column in NAME_COLUMNS]
        if not id_columns:
            continue
        frame = pd.DataFrame(rows, columns=columns).fillna("")
        sanitized, count = mask_hawks_participant_rows(
            frame,
            id_columns=id_columns,
            name_columns=name_columns,
        )
        if count:
            _write_csv_rows(path, columns, sanitized.fillna("").to_dict("records"))
            changed[path.relative_to(processed).as_posix()] = count
    return changed
