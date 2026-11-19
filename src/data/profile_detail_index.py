"""Seek only the approved source records for a selected public profile."""
from __future__ import annotations

import io
from pathlib import Path

import pandas as pd


def read_ranges(path: Path, ranges, dtypes):
    if not ranges:
        return None
    with path.open("rb") as handle:
        header = handle.readline()
        rows = [header]
        for start, length in ranges:
            handle.seek(start)
            rows.append(handle.read(length))
    return pd.read_csv(io.BytesIO(b"".join(rows)), dtype=dtypes, low_memory=False)


def read_indexed_details(views, sources, player_id, name_key, layout):
    from src.data.prepared_customer_views import load_views
    if views is None:
        return None
    try:
        frames = _read_indexed_details(views, sources, player_id, name_key, layout)
        return frames if load_views(views.club) is views else None
    except (OSError, KeyError, ValueError, TypeError, UnicodeError):
        return None


def _read_indexed_details(views, sources, player_id, name_key, layout):
    from base64 import urlsafe_b64encode

    if views is None or not player_id:
        return None
    key = urlsafe_b64encode(player_id.encode()).decode()
    try:
        selection = views.read("detail/" + key)
    except KeyError:
        return None
    if name_key != selection["name"]:
        return None
    schema = views.read("detail-schema")
    result = {}
    for category, path in sources.items():
        batches = []
        club_batches = []
        for group, ranges in selection["rows"].get(category, []):
            frame = read_ranges(path, ranges, schema[category]["types"][group])
            if frame is not None:
                batches.append(frame)
        for group, ranges in schema[category].get("club_rows", []):
            frame = read_ranges(path, ranges, schema[category]["types"][group])
            if frame is not None:
                club_batches.append(frame)
        frames = batches + club_batches
        if not frames:
            result[category] = pd.DataFrame(columns=schema[category]["columns"])
            continue
        frame = pd.concat(frames, ignore_index=True)
        if views.club == layout.GRDCC_CLUB_ID:
            frame = layout.alias_summary_ids(layout.filter_public_player_rows(frame, club_id=views.club), views.club)
        result[category] = layout.coalesce_summary_namespaces(frame, path.name, views.club)
    return result


def profile_checksum(frames):
    import hashlib
    digest = hashlib.sha256()
    for category in ("batting", "bowling", "fielding"):
        frame = frames[category]
        digest.update(frame.to_json(orient="split", index=False, double_precision=15).encode())
    return digest.hexdigest()


def indexed_profile(views, record_id):
    """Reconstruct only this public record, cross-checking its entire governed projection."""
    from base64 import urlsafe_b64encode
    from src.config.club_config import get_processed_dir
    from src.data.playcricket_ingestion import _read_processed_table
    from src.utils.player_identity import _assemble_profile, apply_player_identity_mapping, filter_public_player_rows

    if views is None or views.club not in {"georges-river-district", "glen-waverley-hawks", "fvcc"}:
        return None
    try:
        record = views.read("profile/" + urlsafe_b64encode(record_id.encode()).decode())
        schema = views.read("profile-schema")
        def read(path, version):
            source = Path(path)
            if views.club == "fvcc" and source.parent != get_processed_dir(club_id=views.club):
                raise ValueError("The prepared index does not cover a legacy source")
            name = source.name
            spec = schema["sources"][name]
            frame = read_ranges(Path(path), record["ranges"].get(name, []), spec["dtypes"])
            if frame is None:
                return pd.DataFrame(columns=spec["columns"]).astype(spec["dtypes"])
            return frame

        frames = {}
        for category, types in record["types"].items():
            frame = _read_processed_table("all_seasons_" + category, views.club, read)
            frame = apply_player_identity_mapping(frame, club_id=views.club) if not frame.empty else frame
            if views.club == "georges-river-district":
                frame = filter_public_player_rows(frame, club_id=views.club)
            frame = frame.reindex(columns=list(types))
            if category in record["source_system"]:
                # The governed combined frame assigns this when supplemental
                # history exists, even for players with no supplemental rows.
                frame["source_system"] = record["source_system"][category]
            frames[category] = frame.astype(types)
        if profile_checksum(frames) != record["checksum"]:
            return None
        return _assemble_profile(record["target"], frames)
    except (KeyError, OSError, ValueError, TypeError):
        return None
