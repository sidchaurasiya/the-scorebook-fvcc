from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.config.club_config import (
    REPO_ROOT,
    get_hall_of_fame_dir,
    get_mapping_path,
    get_processed_path,
)


MANIFEST_FILENAME = "prepared_core_manifest.json"
GREATEST_SEASONS_FILENAME = "prepared_greatest_seasons.json"
FRAME_FILENAMES = {
    "batting": "prepared_career_batting.csv",
    "bowling": "prepared_career_bowling.csv",
    "fielding": "prepared_career_fielding.csv",
    "all_time": "prepared_career_all_time.csv",
}
DETAIL_SOURCE_FILENAMES = (
    "player_win_rates.csv",
    "player_bbb_batting_rates.csv",
    "player_scorecard_milestones.csv",
    "player_bowling_milestones.csv",
)


def prepared_core_source_paths(club_id: str) -> list[Path]:
    paths = [
        get_processed_path(filename, club_id=club_id)
        for filename in (
            "all_seasons_batting.csv",
            "all_seasons_bowling.csv",
            "all_seasons_fielding.csv",
            "seasons.csv",
            "players.csv",
        )
    ]
    hall_of_fame_dir = get_hall_of_fame_dir(club_id=club_id)
    paths.extend(hall_of_fame_dir / filename for filename in DETAIL_SOURCE_FILENAMES)
    mapping_path = get_mapping_path("player_aliases.csv", club_id=club_id)
    paths.extend([mapping_path, mapping_path.with_name("manual_player_merges.csv")])
    paths.append(REPO_ROOT / "clubs" / club_id / "club_config.yaml")
    if club_id == "glen-waverley-hawks":
        paths.append(
            REPO_ROOT
            / "clubs"
            / club_id
            / "data"
            / "source"
            / "gwhcc_grade_competition_normalisation.csv"
        )
    return sorted({path.resolve() for path in paths if path.exists()}, key=str)


def prepared_core_source_signature(club_id: str) -> list[dict[str, object]]:
    return [_file_signature(path) for path in prepared_core_source_paths(club_id)]


def prepared_core_manifest_signature(club_id: str) -> tuple[object, ...]:
    path = get_hall_of_fame_dir(club_id=club_id) / MANIFEST_FILENAME
    if not path.exists():
        return tuple()
    stat = path.stat()
    return (str(path), stat.st_size, stat.st_mtime_ns)


def load_prepared_hall_of_fame_core(club_id: str, data_version: str) -> dict[str, object] | None:
    output_dir = get_hall_of_fame_dir(club_id=club_id)
    manifest_path = output_dir / MANIFEST_FILENAME
    if not manifest_path.exists():
        return None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if manifest.get("club_id") != club_id or manifest.get("data_version") != data_version:
        return None
    if manifest.get("source_signature") != prepared_core_source_signature(club_id):
        return None

    frames: dict[str, pd.DataFrame] = {}
    for key, filename in FRAME_FILENAMES.items():
        path = output_dir / filename
        if not path.exists():
            return None
        frames[key] = pd.read_csv(path, low_memory=False)
    greatest_path = output_dir / GREATEST_SEASONS_FILENAME
    if not greatest_path.exists():
        return None
    try:
        greatest = json.loads(greatest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return {
        **frames,
        "best_batting_season": greatest.get("batting"),
        "best_bowling_season": greatest.get("bowling"),
    }


def write_prepared_hall_of_fame_core(
    club_id: str,
    data_version: str,
    frames: dict[str, pd.DataFrame],
    best_batting_season: dict[str, object] | None,
    best_bowling_season: dict[str, object] | None,
    output_dir: Path | None = None,
) -> list[Path]:
    target = output_dir or get_hall_of_fame_dir(club_id=club_id)
    target.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    row_counts: dict[str, int] = {}
    for key, filename in FRAME_FILENAMES.items():
        frame = frames.get(key, pd.DataFrame())
        path = target / filename
        frame.to_csv(path, index=False)
        written.append(path)
        row_counts[key] = len(frame)

    greatest_path = target / GREATEST_SEASONS_FILENAME
    greatest_path.write_text(
        json.dumps(
            {"batting": best_batting_season, "bowling": best_bowling_season},
            indent=2,
            default=_json_default,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(greatest_path)

    manifest_path = target / MANIFEST_FILENAME
    manifest_path.write_text(
        json.dumps(
            {
                "club_id": club_id,
                "data_version": data_version,
                "source_signature": prepared_core_source_signature(club_id),
                "row_counts": row_counts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    written.append(manifest_path)
    return written


def _file_signature(path: Path) -> dict[str, object]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    try:
        relative = str(path.relative_to(REPO_ROOT))
    except ValueError:
        relative = str(path)
    return {"path": relative, "size": path.stat().st_size, "sha256": digest.hexdigest()}


def _json_default(value: Any) -> object:
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return str(value)
