#!/usr/bin/env python3
"""Rebuild Hawks prepared Hall of Fame core inside an isolated candidate root.

This offline finalization step complements ``build_gwhcc_weekly_candidate.py``.
It reads the candidate's already-built processed tables, writes only prepared
Hall of Fame core exports, and performs no PlayCricket retrieval.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

CLUB_ID = "glen-waverley-hawks"
CORE_FILES = (
    "prepared_career_batting.csv",
    "prepared_career_bowling.csv",
    "prepared_career_fielding.csv",
    "prepared_career_all_time.csv",
    "prepared_greatest_seasons.json",
    "prepared_core_manifest.json",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def frame_receipt(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, low_memory=False)
        return {
            "sha256": sha256(path),
            "rows": int(len(frame)),
            "columns": int(len(frame.columns)),
        }
    return {"sha256": sha256(path), "bytes": int(path.stat().st_size)}


def rebuild(candidate_root: Path, club_id: str = CLUB_ID) -> dict[str, Any]:
    candidate_root = candidate_root.expanduser().resolve()
    if candidate_root == ROOT or ROOT in candidate_root.parents:
        raise ValueError("Candidate root must be outside the repository")
    if club_id != CLUB_ID:
        raise ValueError(f"This candidate core builder is scoped to {CLUB_ID}")
    club_root = candidate_root / "clubs" / club_id
    data_root = club_root / "data"
    processed = data_root / "processed"
    if not (club_root / "club_config.yaml").is_file() or not processed.is_dir():
        raise FileNotFoundError("Candidate root must contain the Hawks config and processed tree")

    inputs = [
        data_root / "metadata.json",
        data_root / "player_aliases.csv",
        club_root / "player_aliases.csv",
        data_root / "source" / "disjoint_season_identity_decisions.csv",
        processed / "all_seasons_batting.csv",
        processed / "all_seasons_bowling.csv",
        processed / "all_seasons_fielding.csv",
        processed / "teams.csv",
    ]
    inputs = [path for path in inputs if path.is_file()]
    input_manifest = {
        path.relative_to(candidate_root).as_posix(): sha256(path)
        for path in sorted(inputs)
    }
    input_signature = hashlib.sha256(
        json.dumps(input_manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    import src.config.club_config as club_config

    previous_repo_root = club_config.REPO_ROOT
    previous_clubs_root = club_config.CLUBS_ROOT
    try:
        club_config.REPO_ROOT = candidate_root
        club_config.CLUBS_ROOT = candidate_root / "clubs"
        club_config._load_club_config_cached.cache_clear()
        os.environ["CLUB_ID"] = club_id
        os.environ["SCOREBOOK_IGNORE_PREPARED_HOF"] = "1"

        from src.data import playcricket_ingestion

        playcricket_ingestion._read_processed_table_cached.clear()
        from src.ui import layout

        for name in ("_load_hall_of_fame_data_cached", "_load_player_profile_index_cached"):
            cached = getattr(layout, name, None)
            if cached is not None and hasattr(cached, "clear"):
                cached.clear()

        from scripts.build_hall_of_fame_core_exports import main as build_core

        status = build_core(["--club", club_id])
        if status:
            raise RuntimeError(f"Hawks prepared Hall of Fame core build failed: {status}")

        from src.data.public_generic_identity_privacy import sanitize_public_processed_tree

        privacy = sanitize_public_processed_tree(processed, club_id=club_id)
        if privacy["files"]:
            raise RuntimeError("Prepared core build reintroduced generic identity fields")

        hof_dir = processed / "hall_of_fame"
        output_manifest = {
            name: frame_receipt(hof_dir / name)
            for name in CORE_FILES
            if (hof_dir / name).is_file()
        }
        if set(output_manifest) != set(CORE_FILES):
            raise RuntimeError("Prepared Hall of Fame core manifest is incomplete")

        receipt = {
            "club_id": club_id,
            "source_mode": "offline candidate inputs; no external fetch",
            "input_signature_sha256": input_signature,
            "input_files": input_manifest,
            "output_files": output_manifest,
            "public_privacy_postcheck": {
                "changed_processed_files_after_core_build": len(privacy["files"]),
                "generic_identity_json_findings": 0,
            },
        }
        receipt_path = candidate_root / "hawks_candidate_hof_core_receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        return {**receipt, "receipt_path": receipt_path.name}
    finally:
        club_config.REPO_ROOT = previous_repo_root
        club_config.CLUBS_ROOT = previous_clubs_root
        club_config._load_club_config_cached.cache_clear()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--club", default=CLUB_ID)
    args = parser.parse_args(argv)
    receipt = rebuild(args.candidate_root, args.club)
    print(json.dumps(receipt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
