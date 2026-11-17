"""FVCC-only public handling for reused masked scorecard participant tokens."""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from pathlib import Path

import pandas as pd


FVCC_CLUB_ID = "fvcc"

# The accepted FVCC source used invalid nil-UUID-style placeholders rather than
# person IDs. Detect that non-RFC4122 form by shape so raw values and reversible
# low-entropy hashes do not need to be stored in the public repository.
_FVCC_PLACEHOLDER_ID_PATTERN = re.compile(r"^00000000-0000-0000-0000-0000000000[0-9]{2}$", re.IGNORECASE)

SCORECARD_TABLES = {
    "all_seasons_scorecard_batting": "batting",
    "all_seasons_scorecard_bowling": "bowling",
    "all_seasons_scorecard_fielding": "fielding",
}
LINK_ID_COLUMNS = (
    "canonical_player_id",
    "player_id",
    "raw_player_id",
    "participant_id",
    "player_1_canonical_id",
    "player_2_canonical_id",
    "player_1_id",
    "player_2_id",
)
LINK_NAME_COLUMNS = (
    "canonical_player_name",
    "display_player_name",
    "player_name",
    "player_1_name",
    "player_2_name",
)


def is_fvcc_placeholder_participant_id(value: object) -> bool:
    text = "" if value is None or pd.isna(value) else str(value).strip()
    if not text or text.casefold() in {"nan", "none", "null", "<na>"}:
        return False
    return bool(_FVCC_PLACEHOLDER_ID_PATTERN.fullmatch(text))


def _generic_name_mask(frame: pd.DataFrame) -> pd.Series:
    if "player_name" not in frame:
        return pd.Series(False, index=frame.index, dtype=bool)
    from src.utils.player_identity import is_private_or_anonymised_player

    return frame["player_name"].map(is_private_or_anonymised_player).astype(bool)


def sanitize_fvcc_scorecard_rows(
    frame: pd.DataFrame,
    *,
    club_id: str | None,
    discipline: str,
) -> pd.DataFrame:
    """Remove ambiguous FVCC IDs while preserving every scorecard row and figure.

    Anonymous rows receive a deterministic key scoped to one match and one
    scorecard discipline. The key is not derived from a participant identifier
    and cannot join the same placeholder across matches.
    """
    output = frame.copy()
    if str(club_id or "").strip().casefold() != FVCC_CLUB_ID or output.empty:
        return output
    if "player_id" not in output or "player_name" not in output:
        return output

    generic = _generic_name_mask(output)
    placeholder = output["player_id"].map(is_fvcc_placeholder_participant_id)
    has_identifier = output["player_id"].fillna("").astype(str).str.strip().ne("")
    anonymous = placeholder | (generic & has_identifier)
    if not anonymous.any():
        return output
    if "match_id" not in output:
        raise ValueError("FVCC anonymous scorecard rows require a match identifier")

    output["player_id"] = output["player_id"].fillna("").astype(str)
    output.loc[anonymous, "player_id"] = ""
    # A source label that becomes non-generic must not be attached to a reused
    # placeholder token without an exact verified identity mapping.
    output.loc[placeholder & ~generic, "player_name"] = "Private player"

    if "public_scorecard_row_key" not in output:
        output["public_scorecard_row_key"] = ""
    else:
        output["public_scorecard_row_key"] = output["public_scorecard_row_key"].fillna("").astype(str)

    ordinal_by_match: dict[str, int] = {}
    for index in output.index[anonymous]:
        existing = str(output.at[index, "public_scorecard_row_key"] or "").strip()
        if existing:
            continue
        match_id = str(output.at[index, "match_id"] or "").strip()
        if not match_id:
            raise ValueError("FVCC anonymous scorecard rows require a non-empty match identifier")
        ordinal_by_match[match_id] = ordinal_by_match.get(match_id, 0) + 1
        material = f"{FVCC_CLUB_ID}|{discipline}|{match_id}|anonymous-row|{ordinal_by_match[match_id]}"
        key = hashlib.sha256(material.encode("utf-8")).hexdigest()
        output.at[index, "public_scorecard_row_key"] = f"fvcc-anon-{key}"

    keys = output.loc[anonymous, "public_scorecard_row_key"].astype(str)
    if keys.eq("").any() or keys.duplicated().any():
        raise ValueError("FVCC anonymous scorecard row keys must be present and unique")
    return output


def sanitize_fvcc_scorecard_table(
    table_name: str,
    frame: pd.DataFrame,
    *,
    club_id: str | None,
) -> pd.DataFrame:
    """Apply the FVCC guard to club data and any permitted legacy fallback."""
    discipline = SCORECARD_TABLES.get(str(table_name))
    if discipline is None or str(club_id or "").strip().casefold() != FVCC_CLUB_ID:
        return frame.copy()
    return sanitize_fvcc_scorecard_rows(frame, club_id=FVCC_CLUB_ID, discipline=discipline)


def sanitize_fvcc_scorecard_record_links(
    frame: pd.DataFrame,
    *,
    club_id: str | None,
) -> pd.DataFrame:
    """Keep generic scorecard records while removing any canonical/profile ID."""
    output = frame.copy()
    if str(club_id or "").strip().casefold() != FVCC_CLUB_ID or output.empty:
        return output
    names = [column for column in LINK_NAME_COLUMNS if column in output]
    ids = [column for column in LINK_ID_COLUMNS if column in output]
    if not ids:
        return output

    from src.utils.player_identity import is_private_or_anonymised_player

    generic = pd.Series(False, index=output.index)
    for column in names:
        generic |= output[column].map(is_private_or_anonymised_player).astype(bool)
    has_id = pd.Series(False, index=output.index)
    for column in ids:
        has_id |= output[column].fillna("").astype(str).str.strip().ne("")
    placeholder = pd.Series(False, index=output.index)
    for column in ids:
        placeholder |= output[column].map(is_fvcc_placeholder_participant_id)
    anonymous = (generic & has_id) | placeholder
    if not anonymous.any():
        return output
    if "match_id" not in output or "mode" not in output:
        raise ValueError("FVCC anonymous scorecard links require match_id and mode")

    for column in ids:
        output.loc[anonymous, column] = ""
    # If a known malformed source ID arrives with a newly visible label, keep
    # the scorecard row generic until a unique identity is verified.
    for column in names:
        public_name = ~output[column].map(is_private_or_anonymised_player).astype(bool)
        output.loc[anonymous & placeholder & public_name, column] = "Private player"

    return output


def sanitize_fvcc_scorecard_record_link_file(path: Path | str) -> dict[str, object]:
    """Sanitize one FVCC public or legacy-fallback scorecard-link artifact."""
    link_path = Path(path)
    if not link_path.is_file():
        raise FileNotFoundError(link_path)
    before_bytes = link_path.read_bytes()
    before = pd.read_csv(link_path, dtype=str, keep_default_na=False)
    after = sanitize_fvcc_scorecard_record_links(before, club_id=FVCC_CLUB_ID)
    id_columns = [column for column in LINK_ID_COLUMNS if column in before]
    identity_cells_cleared = sum(
        int(before[column].fillna("").astype(str).str.strip().ne("").where(after[column].fillna("").astype(str).str.strip().eq(""), False).sum())
        for column in id_columns
    )
    rows_with_identity_removed = int(
        pd.concat(
            [
                before[column].fillna("").astype(str).str.strip().ne("")
                & after[column].fillna("").astype(str).str.strip().eq("")
                for column in id_columns
            ],
            axis=1,
        ).any(axis=1).sum()
    ) if id_columns else 0
    changed = not after.equals(before)
    content = after.to_csv(index=False).encode("utf-8") if changed else before_bytes
    if content != before_bytes:
        temporary = link_path.with_name(f".{link_path.name}.privacy-tmp")
        temporary.write_bytes(content)
        temporary.replace(link_path)
    return {
        "rows_before": len(before),
        "rows_after": len(after),
        "sha256_before": hashlib.sha256(before_bytes).hexdigest(),
        "sha256_after": hashlib.sha256(content).hexdigest(),
        "changed": content != before_bytes,
        "rows_with_identity_removed": rows_with_identity_removed,
        "identity_cells_cleared": identity_cells_cleared,
    }


def masked_scorecard_projection(frame: pd.DataFrame) -> Counter[tuple[str, ...]]:
    """Multiset projection of anonymous scorecard rows, excluding identities/keys."""
    if frame.empty or "player_name" not in frame:
        return Counter()
    generic = _generic_name_mask(frame)
    if "public_scorecard_row_key" in frame:
        generic |= frame["public_scorecard_row_key"].fillna("").astype(str).str.startswith("fvcc-anon-")
    if "player_id" in frame:
        generic |= frame["player_id"].map(is_fvcc_placeholder_participant_id)
    columns = [
        column
        for column in frame.columns
        if column not in {"player_id", "raw_player_id", "player_name", "raw_player_name", "public_scorecard_row_key"}
    ]
    return Counter(
        tuple("" if pd.isna(value) else str(value) for value in row)
        for row in frame.loc[generic, columns].itertuples(index=False, name=None)
    )


def assert_masked_scorecard_rows_unchanged(before: pd.DataFrame, after: pd.DataFrame) -> None:
    if masked_scorecard_projection(before) != masked_scorecard_projection(after):
        raise ValueError("Anonymous FVCC scorecard values or row multiplicity changed")


def sanitize_fvcc_processed_scorecards(processed_dir: Path | str) -> dict[str, dict[str, object]]:
    """Sanitize only the three FVCC scorecard artifacts in a processed directory."""
    root = Path(processed_dir)
    result: dict[str, dict[str, object]] = {}
    for table, discipline in SCORECARD_TABLES.items():
        path = root / f"{table}.csv"
        if not path.is_file():
            raise FileNotFoundError(path)
        before_bytes = path.read_bytes()
        before = pd.read_csv(path, dtype=str, keep_default_na=False)
        after = sanitize_fvcc_scorecard_rows(before, club_id=FVCC_CLUB_ID, discipline=discipline)
        changed = not after.equals(before)
        content = after.to_csv(index=False).encode("utf-8") if changed else before_bytes
        if content != before_bytes:
            temporary = path.with_name(f".{path.name}.privacy-tmp")
            temporary.write_bytes(content)
            temporary.replace(path)
        result[path.as_posix()] = {
            "rows_before": len(before),
            "rows_after": len(after),
            "sha256_before": hashlib.sha256(before_bytes).hexdigest(),
            "sha256_after": hashlib.sha256(content).hexdigest(),
            "changed": content != before_bytes,
            "sanitized_rows": int(after.get("public_scorecard_row_key", pd.Series(dtype=str)).astype(str).str.startswith("fvcc-anon-").sum()),
        }
    link_path = root / "hall_of_fame" / "scorecard_record_links.csv"
    result[link_path.as_posix()] = sanitize_fvcc_scorecard_record_link_file(link_path)
    return result
