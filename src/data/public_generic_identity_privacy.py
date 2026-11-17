"""Club-scoped privacy cleanup for generic public processed records.

Numeric scorecard, delivery, career, and event values are retained. Generic or
currently private participant IDs are removed from public artifacts; GRDCC
identities with an exact current-public source decision can be displayed by
their verified name. Raw source payloads remain in protected receipts.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


PUBLIC_IDENTITY_POLICY_VERSION = "public-generic-identity-v8"
GENERIC_LABEL = "Private player"
SUPPORTED_CLUB_IDS = frozenset(
    {
        "georges-river-district",
        "glen-waverley-hawks",
        "fvcc",
        "ashwood",
        "plenty",
        "reynella",
        "southside-east-caulfield",
    }
)

IDENTITY_ID_COLUMNS = frozenset(
    {
        "player_id",
        "participant_id",
        "raw_player_id",
        "source_player_id",
        "source_participant_id",
        "source_raw_player_id",
        "source_canonical_player_id",
        "canonical_ids",
        "canonical_player_id",
        "player_key",
        "player_1_id",
        "player_2_id",
        "player_1_canonical_id",
        "player_2_canonical_id",
        "participant_1_id",
        "participant_2_id",
        "striker_participant_id",
        "bowler_participant_id",
        "batter_participant_id",
        "fielder_participant_id",
        "dismissed_player_participant_id",
    }
)
IDENTITY_NAME_TO_IDS = {
    "canonical_player_name": ("canonical_player_id", "player_key", "player_id"),
    "display_player_name": ("canonical_player_id", "player_key", "player_id"),
    "raw_player_name": ("raw_player_id", "source_player_id", "source_participant_id", "source_raw_player_id"),
    "source_player_name": ("source_player_id", "source_participant_id"),
    "source_raw_player_name": ("source_raw_player_id", "raw_player_id", "source_player_id"),
    "source_canonical_player_name": ("source_canonical_player_id", "canonical_player_id", "player_key"),
    "player_name": (
        "player_id",
        "participant_id",
        "source_player_id",
        "source_participant_id",
        "canonical_player_id",
        "raw_player_id",
        "player_key",
    ),
    "Player": ("player_id", "canonical_player_id", "raw_player_id"),
    "player_1_name": ("player_1_canonical_id", "player_1_id", "participant_1_id"),
    "player_2_name": ("player_2_canonical_id", "player_2_id", "participant_2_id"),
    "striker_name": ("striker_participant_id",),
    "batter_name": ("batter_participant_id",),
    "bowler_name": ("bowler_participant_id",),
    "fielder_name": ("fielder_participant_id",),
}
SOURCE_ID_COLUMNS = frozenset(
    {
        "raw_player_id",
        "source_player_id",
        "source_participant_id",
        "participant_id",
        "participant_1_id",
        "participant_2_id",
        "striker_participant_id",
        "bowler_participant_id",
        "batter_participant_id",
        "fielder_participant_id",
        "dismissed_player_participant_id",
        "source_raw_player_id",
        "source_canonical_player_id",
        "canonical_ids",
    }
)
PUBLIC_DISPLAY_COLUMNS = frozenset(
    {
        "canonical_player_name",
        "display_player_name",
        "raw_player_name",
        "source_player_name",
        "source_raw_player_name",
        "source_canonical_player_name",
        "player_name",
        "Player",
        "player_1_name",
        "player_2_name",
        "striker_name",
        "batter_name",
        "bowler_name",
        "fielder_name",
    }
)
PUBLIC_DISPLAY_COLUMNS_CASEFOLDED = frozenset(column.casefold() for column in PUBLIC_DISPLAY_COLUMNS)
CANONICAL_ID_COLUMNS = frozenset({"canonical_player_id", "player_key"})
PRIVATE_FLAG_COLUMNS = frozenset(
    {"is_private", "is_anonymised", "is_anonymized", "privacy_flag", "player_is_private"}
)


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def _explicit_private_flag(row: dict[str, Any]) -> bool:
    return any(
        _text(value).casefold() in {"true", "1", "yes", "y", "private", "anonymous"}
        for column, value in row.items()
        if str(column).casefold() in PRIVATE_FLAG_COLUMNS
    )


def _mask_generic_dismissal_text(value: object) -> str:
    """Keep the dismissal classification and remove actor names on generic rows."""
    text = _text(value)
    if not text:
        return text
    normalized = re.sub(r"\s+", " ", text).strip().casefold()
    if normalized in {
        "not out",
        "did not bat",
        "retired not out",
        "retired hurt",
        "absent hurt",
        "absent",
        "retired out",
    }:
        return text
    classifications = (
        ("caught and bowled", ("c&b", "caught and bowled")),
        ("caught", ("caught", "c:")),
        ("stumped", ("stumped", "st:")),
        ("run out", ("run out", "runout")),
        ("lbw", ("lbw", "leg before")),
        ("bowled", ("bowled", "b:")),
        ("hit wicket", ("hit wicket",)),
        ("retired hurt", ("retired hurt",)),
        ("retired out", ("retired out",)),
        ("obstructing the field", ("obstructing the field",)),
        ("handled the ball", ("handled the ball",)),
        ("hit the ball twice", ("hit the ball twice",)),
    )
    for label, tokens in classifications:
        if any(token in normalized for token in tokens):
            return label.title()
    return "Dismissal recorded"


def _is_generic(value: object) -> bool:
    from src.utils.player_identity import is_private_or_anonymised_player

    return is_private_or_anonymised_player(value)


def _current_grdcc_status(
    id_columns: tuple[str, ...],
    row: dict[str, Any],
    *,
    club_id: str,
) -> tuple[str, str]:
    if club_id != "georges-river-district":
        return "", ""
    from src.data.grdcc_player_privacy import resolve_current_privacy

    canonical_values = [
        _text(row.get(column, ""))
        for column in id_columns
        if "canonical" in column.casefold() and _text(row.get(column, ""))
    ]
    source_values = [
        _text(row.get(column, ""))
        for column in id_columns
        if "canonical" not in column.casefold() and _text(row.get(column, ""))
    ]
    if not canonical_values and not source_values:
        return "", ""
    pairs = [(canonical, source) for canonical in (canonical_values or [""]) for source in (source_values or [""])]
    decisions = [
        resolve_current_privacy(
            canonical_player_id=canonical,
            source_participant_id=source,
            club_id=club_id,
        )
        for canonical, source in pairs
    ]
    statuses = {status for status, _ in decisions if status}
    if not statuses:
        return "", ""
    if "private" in statuses or len(statuses) > 1:
        return "private", ""
    names = {name.strip() for status, name in decisions if status == "public" and name.strip()}
    if statuses == {"public"} and len(names) == 1:
        return "public", next(iter(names))
    return "private", ""


def _event_key_column(relative_path: str) -> str | None:
    name = Path(relative_path).name.casefold()
    if name.startswith(("all_seasons_scorecard_", "all_scorecard_")):
        return "public_scorecard_row_key"
    if name == "fastest_batting_milestones.csv" or (
        name.startswith("scorecard_") and name.endswith("_milestones_by_scope.csv")
    ):
        return "public_record_row_key"
    return None


def _apply_event_keys(
    frame: pd.DataFrame,
    *,
    club_id: str,
    relative_path: str,
) -> tuple[pd.DataFrame, int]:
    key_column = _event_key_column(relative_path)
    if key_column is None or "match_id" not in frame:
        return frame, 0
    name_columns = [column for column in IDENTITY_NAME_TO_IDS if column in frame]
    if not name_columns:
        return frame, 0
    generic = pd.Series(False, index=frame.index)
    for column in name_columns:
        generic |= frame[column].map(_is_generic).astype(bool)
    generic &= frame["match_id"].fillna("").astype(str).str.strip().ne("")
    if not generic.any():
        return frame, 0
    output = frame.copy()
    if key_column not in output:
        output[key_column] = ""
    else:
        output[key_column] = output[key_column].fillna("").astype(str)
    context_columns = [
        column
        for column in ("match_id", "innings_id", "team_id", "team_name", "season", "grade_id", "grade_name", "mode")
        if column in output
    ]
    ignored = IDENTITY_ID_COLUMNS | frozenset(IDENTITY_NAME_TO_IDS) | frozenset(
        {"public_scorecard_row_key", "public_record_row_key", "all_involved_player_names"}
    )
    ignored_casefolded = {column.casefold() for column in ignored}
    payload_columns = [column for column in output.columns if column.casefold() not in ignored_casefolded]
    ordinals: dict[tuple[tuple[str, ...], str], int] = {}
    generated = 0
    for index in output.index[generic]:
        if _text(output.at[index, key_column]):
            continue
        context = tuple(_text(output.at[index, column]) for column in context_columns)
        payload = tuple(
            (column, _text(output.at[index, column]))
            for column in payload_columns
        )
        payload_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
        ordinal_key = (context, payload_hash)
        ordinals[ordinal_key] = ordinals.get(ordinal_key, 0) + 1
        material = "|".join(
            (club_id, relative_path, *context, payload_hash, "duplicate", str(ordinals[ordinal_key]))
        )
        key = hashlib.sha256(material.encode("utf-8")).hexdigest()
        output.at[index, key_column] = f"anon-{key}"
        generated += 1
    keys = output.loc[generic, key_column].astype(str)
    if keys.eq("").any() or keys.duplicated().any():
        raise ValueError(f"Anonymous public event keys must be present and unique: {relative_path}")
    return output, generated


def sanitize_public_identity_frame(
    frame: pd.DataFrame,
    *,
    club_id: str,
    relative_path: str = "",
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Mask generic/verified-private IDs and honor GRDCC exact-public names."""
    output = frame.copy()
    stats = {
        "rows_before": len(frame),
        "rows_after": len(frame),
        "identifier_cells_cleared": 0,
        "private_names_masked": 0,
        "current_public_names_restored": 0,
        "anonymous_event_keys_added": 0,
    }
    if output.empty or str(club_id).strip().casefold() not in SUPPORTED_CLUB_IDS:
        return output, stats
    ids_available = [column for column in output.columns if column.casefold() in IDENTITY_ID_COLUMNS]
    original_identity_names = [column for column in IDENTITY_NAME_TO_IDS if column in output]
    generic_identity_rows = pd.Series(False, index=output.index)
    for column in original_identity_names:
        generic_identity_rows |= output[column].map(_is_generic).astype(bool)
    # GRDCC review exports can carry a delimited list of duplicate-player
    # aliases beside a generic source row. Those names are diagnostic only;
    # retain the numeric audit evidence while replacing the unsafe list.
    if "all_involved_player_names" in output:
        for index in output.index[generic_identity_rows]:
            if _text(output.at[index, "all_involved_player_names"]):
                output.at[index, "all_involved_player_names"] = GENERIC_LABEL
                stats["private_names_masked"] += 1

    # A normal one-player row can use the accepted exact-ID snapshot directly.
    # Partnership rows are handled below per partner so one side's decision
    # cannot propagate to the other side.
    if ids_available and club_id == "georges-river-district" and not any(
        column in output for column in ("player_1_name", "player_2_name")
    ):
        from src.data.grdcc_player_privacy import current_privacy_overrides

        statuses, public_names = current_privacy_overrides(output, club_id)
        name_columns = [column for column in IDENTITY_NAME_TO_IDS if column in output]
        for index in output.index[statuses.eq("private")]:
            for column in name_columns:
                if _text(output.at[index, column]) and not _is_generic(output.at[index, column]):
                    output.at[index, column] = GENERIC_LABEL
                    stats["private_names_masked"] += 1
            for column in ids_available:
                if _text(output.at[index, column]):
                    output.at[index, column] = ""
                    stats["identifier_cells_cleared"] += 1
            for column in ("dismissal", "dismissal_text"):
                if column in output:
                    output.at[index, column] = _mask_generic_dismissal_text(output.at[index, column])
        for index in output.index[statuses.eq("public")]:
            public_name = _text(public_names.at[index])
            if not public_name:
                continue
            for column in name_columns:
                if column.casefold() in PUBLIC_DISPLAY_COLUMNS_CASEFOLDED and _text(output.at[index, column]):
                    if str(output.at[index, column]).strip() != public_name:
                        output.at[index, column] = public_name
                        stats["current_public_names_restored"] += 1
            for column in ids_available:
                if column.casefold() not in CANONICAL_ID_COLUMNS and "canonical" not in column.casefold() and _text(output.at[index, column]):
                    output.at[index, column] = ""
                    stats["identifier_cells_cleared"] += 1

    flag_columns = [column for column in output.columns if column.casefold() in PRIVATE_FLAG_COLUMNS]
    if flag_columns:
        for index in output.index:
            row = output.loc[index].to_dict()
            if not _explicit_private_flag(row):
                continue
            status = (
                _current_grdcc_status(tuple(ids_available), row, club_id=club_id)[0]
                if ids_available
                else ""
            )
            if status == "public":
                continue
            for column in IDENTITY_NAME_TO_IDS:
                if column in output and _text(output.at[index, column]) and not _is_generic(output.at[index, column]):
                    output.at[index, column] = GENERIC_LABEL
                    stats["private_names_masked"] += 1
            for column in ids_available:
                if _text(output.at[index, column]):
                    output.at[index, column] = ""
                    stats["identifier_cells_cleared"] += 1
            for column in ("dismissal", "dismissal_text"):
                if column in output:
                    output.at[index, column] = _mask_generic_dismissal_text(output.at[index, column])

    has_partnership_identity = any(
        column in output for column in ("player_1_name", "player_2_name")
    )
    if not has_partnership_identity:
        single_person_name_columns = [
            column
            for column in IDENTITY_NAME_TO_IDS
            if column in output and column not in {"player_1_name", "player_2_name"}
        ]
        for index in output.index:
            if not any(_is_generic(output.at[index, column]) for column in single_person_name_columns):
                continue
            row = output.loc[index].to_dict()
            status, public_name = (
                _current_grdcc_status(tuple(ids_available), row, club_id=club_id)
                if ids_available
                else ("", "")
            )
            if status == "public" and public_name:
                for column in single_person_name_columns:
                    if column.casefold() in PUBLIC_DISPLAY_COLUMNS_CASEFOLDED and _text(output.at[index, column]):
                        if _text(output.at[index, column]) != public_name:
                            output.at[index, column] = public_name
                            stats["current_public_names_restored"] += 1
                for column in ids_available:
                    if column.casefold() not in CANONICAL_ID_COLUMNS and "canonical" not in column.casefold() and _text(output.at[index, column]):
                        output.at[index, column] = ""
                        stats["identifier_cells_cleared"] += 1
                continue
            for column in single_person_name_columns:
                if _text(output.at[index, column]) and not _is_generic(output.at[index, column]):
                    output.at[index, column] = GENERIC_LABEL
                    stats["private_names_masked"] += 1
            for column in ids_available:
                if _text(output.at[index, column]):
                    output.at[index, column] = ""
                    stats["identifier_cells_cleared"] += 1
            for column in ("dismissal", "dismissal_text"):
                if column in output:
                    output.at[index, column] = _mask_generic_dismissal_text(output.at[index, column])

    for name_column, allowed_id_columns in IDENTITY_NAME_TO_IDS.items():
        if name_column not in output:
            continue
        id_columns = [column for column in allowed_id_columns if column in output]
        if not id_columns:
            continue
        for index in output.index:
            name = _text(output.at[index, name_column])
            row = output.loc[index].to_dict()
            id_values = [_text(row.get(column, "")) for column in id_columns]
            if not any(id_values):
                continue
            generic = _is_generic(name)
            if (
                not generic
                and not _explicit_private_flag(row)
                and not (club_id == "georges-river-district" and has_partnership_identity)
            ):
                # Non-partnership GRDCC rows were resolved in the vector
                # privacy pass above. Other clubs only need generic/flagged
                # rows inspected here.
                continue
            status, public_name = _current_grdcc_status(tuple(id_columns), row, club_id=club_id)
            if status == "public":
                if name_column.casefold() in PUBLIC_DISPLAY_COLUMNS_CASEFOLDED and public_name and name != public_name:
                    output.at[index, name_column] = public_name
                    stats["current_public_names_restored"] += 1
                for column in id_columns:
                    if column.casefold() not in CANONICAL_ID_COLUMNS and "canonical" not in column.casefold() and _text(output.at[index, column]):
                        output.at[index, column] = ""
                        stats["identifier_cells_cleared"] += 1
                continue

            if status == "private":
                if name and not generic:
                    output.at[index, name_column] = GENERIC_LABEL
                    stats["private_names_masked"] += 1
                for column in id_columns:
                    if _text(output.at[index, column]):
                        output.at[index, column] = ""
                        stats["identifier_cells_cleared"] += 1
                continue

            if generic:
                for column in id_columns:
                    if _text(output.at[index, column]):
                        output.at[index, column] = ""
                        stats["identifier_cells_cleared"] += 1

    # Generic singleton records sometimes expose several aliases for the same
    # person while only one of those aliases is present in the column map.
    # Once the row has a generic identity and only one public player label,
    # remove every person-specific ID in that row. Multi-person rows keep the
    # per-side mappings above so one partner's privacy cannot hide the other.
    name_columns = [column for column in IDENTITY_NAME_TO_IDS if column in output]
    if ids_available and name_columns:
        for index in output.index:
            generic_names = [column for column in name_columns if _is_generic(output.at[index, column])]
            if not generic_names:
                continue
            nonempty_names = [column for column in name_columns if _text(output.at[index, column])]
            if len(nonempty_names) != 1:
                continue
            row = output.loc[index].to_dict()
            if not any(_text(row.get(column, "")) for column in ids_available):
                continue
            status, _ = _current_grdcc_status(tuple(ids_available), output.loc[index].to_dict(), club_id=club_id)
            if status == "public":
                continue
            for column in ids_available:
                if _text(output.at[index, column]):
                    output.at[index, column] = ""
                    stats["identifier_cells_cleared"] += 1

    output, keys_added = _apply_event_keys(output, club_id=club_id, relative_path=relative_path)
    stats["anonymous_event_keys_added"] = keys_added
    return output, stats


def _projection(frame: pd.DataFrame) -> Counter[tuple[str, ...]]:
    ignored = IDENTITY_ID_COLUMNS | frozenset(IDENTITY_NAME_TO_IDS) | frozenset(
        {"public_scorecard_row_key", "public_record_row_key", "all_involved_player_names"}
    )
    ignored_casefolded = {column.casefold() for column in ignored}
    columns = [column for column in frame.columns if column.casefold() not in ignored_casefolded]
    return Counter(tuple("" if pd.isna(value) else str(value) for value in row) for row in frame[columns].itertuples(index=False, name=None))


def _privacy_safe_projection_before(frame: pd.DataFrame, *, club_id: str) -> pd.DataFrame:
    """Allow only the approved removal of actor names from generic/private dismissals.

    Dismissal text may embed a fielder or bowler name even when the batter is
    generic. All score, result, event, and other context values remain part of
    the strict projection comparison.
    """
    expected = frame.copy()
    name_columns = [column for column in IDENTITY_NAME_TO_IDS if column in expected]
    id_columns = [column for column in expected if column.casefold() in IDENTITY_ID_COLUMNS]
    for index in expected.index:
        row = expected.loc[index].to_dict()
        generic = any(_is_generic(row.get(column, "")) for column in name_columns)
        flagged = _explicit_private_flag(row)
        protected = generic or flagged
        if club_id == "georges-river-district" and id_columns:
            status = _current_grdcc_status(tuple(id_columns), row, club_id=club_id)[0]
            if status == "public":
                protected = False
            elif status == "private":
                protected = True
        if not protected:
            continue
        for column in ("dismissal", "dismissal_text"):
            if column in expected:
                expected.at[index, column] = _mask_generic_dismissal_text(expected.at[index, column])
    return expected


def sanitize_public_processed_tree(
    processed_root: Path | str,
    *,
    club_id: str,
    include_json_scan: bool = True,
    update_metadata: bool = True,
) -> dict[str, Any]:
    """Sanitize every processed CSV for one explicit club and preserve data values."""
    root = Path(processed_root)
    result: dict[str, Any] = {
        "club_id": club_id,
        "files": {},
        "rows_processed": 0,
        "metadata_revision_updates": [],
        "skipped_empty_files": [],
    }
    if not root.exists():
        result["missing_root"] = str(root)
        return result
    for path in sorted(root.rglob("*.csv")):
        before_bytes = path.read_bytes()
        relative = path.relative_to(root).as_posix()
        try:
            before = pd.read_csv(path, dtype=str, keep_default_na=False)
        except pd.errors.EmptyDataError:
            if before_bytes.strip():
                raise
            result["skipped_empty_files"].append(
                {"path": relative, "sha256": hashlib.sha256(before_bytes).hexdigest()}
            )
            continue
        after, stats = sanitize_public_identity_frame(before, club_id=club_id, relative_path=relative)
        expected_projection = _privacy_safe_projection_before(before, club_id=club_id)
        if len(before) != len(after) or _projection(expected_projection) != _projection(after):
            raise ValueError(f"Privacy sanitizer changed row count or numeric/context projection: {relative}")
        changed = not after.equals(before)
        if changed:
            line_ending = "\r\n" if b"\r\n" in before_bytes else "\n"
            bom = before_bytes.startswith(b"\xef\xbb\xbf")
            encoding = "utf-8-sig" if bom else "utf-8"
            temporary = path.with_name(f".{path.name}.privacy-tmp")
            with temporary.open("w", newline="", encoding=encoding) as handle:
                writer = csv.DictWriter(handle, fieldnames=list(after.columns), lineterminator=line_ending, extrasaction="ignore")
                writer.writeheader()
                writer.writerows(after.where(pd.notna(after), "").to_dict("records"))
            temporary.replace(path)
        result["rows_processed"] += len(before)
        if changed:
            result["files"][relative] = {
                **stats,
                "changed": True,
                "sha256_before": hashlib.sha256(before_bytes).hexdigest(),
                "sha256_after": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
    metadata_paths = (
        (root.parent / "metadata.json", root / "metadata" / "fvcc_data_version.json")
        if update_metadata
        else (root / "metadata" / "fvcc_data_version.json",)
    )
    for metadata_path in metadata_paths:
        if not metadata_path.is_file():
            continue
        try:
            before_bytes = metadata_path.read_bytes()
            document = json.loads(before_bytes)
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(document, dict) or document.get("public_generic_identity_revision") == PUBLIC_IDENTITY_POLICY_VERSION:
            continue
        # Keep a club's own identity/privacy revision intact.  This shared
        # sanitizer has a separate revision so Hawks' match-scoped placeholder
        # guard (and future club-specific cache signatures) cannot be erased.
        document["public_generic_identity_revision"] = PUBLIC_IDENTITY_POLICY_VERSION
        after_bytes = (json.dumps(document, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        temporary = metadata_path.with_name(f".{metadata_path.name}.privacy-tmp")
        temporary.write_bytes(after_bytes)
        temporary.replace(metadata_path)
        result["metadata_revision_updates"].append(
            {
                "path": metadata_path.relative_to(root.parent.parent if root.name == "processed" else root.parent).as_posix(),
                "sha256_before": hashlib.sha256(before_bytes).hexdigest(),
                "sha256_after": hashlib.sha256(after_bytes).hexdigest(),
            }
        )
    if include_json_scan:
        residuals = scan_generic_id_pairs_in_json(root)
        if residuals:
            raise ValueError(f"Generic-label identity fields remain in processed JSON: {len(residuals)}")
    return result


def scan_generic_id_pairs_in_json(root: Path | str) -> list[dict[str, str]]:
    """Return path-only findings; JSON identity values are never emitted."""
    root = Path(root)
    name_keys = {key.casefold() for key in IDENTITY_NAME_TO_IDS}
    id_keys = IDENTITY_ID_COLUMNS
    findings: list[dict[str, str]] = []

    def visit(value: Any, file_path: Path) -> None:
        if isinstance(value, dict):
            normalized = {str(key).casefold(): child for key, child in value.items()}
            has_generic = any(key in normalized and _is_generic(normalized[key]) for key in name_keys)
            has_id = any(key in normalized and str(normalized[key] or "").strip() for key in id_keys)
            if has_generic and has_id:
                findings.append({"path": file_path.relative_to(root).as_posix()})
            for child in value.values():
                visit(child, file_path)
        elif isinstance(value, list):
            for child in value:
                visit(child, file_path)

    for path in sorted(root.rglob("*.json")):
        try:
            visit(json.loads(path.read_text(encoding="utf-8")), path)
        except (OSError, json.JSONDecodeError):
            continue
    return findings
