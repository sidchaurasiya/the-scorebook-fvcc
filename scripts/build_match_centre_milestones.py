#!/usr/bin/env python3
"""Build processed batting milestone records from local match-centre CSVs only.

This script does not call PlayCricket or PlayHQ. It reads already processed
match-centre scope outputs under data/processed/match_centre/ and writes the
Hall of Fame milestone inputs back to that processed folder.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.club_refresh_utils import add_club_args, print_club_header, print_outputs, print_paths, resolve_club_id  # noqa: E402
from src.config.club_config import get_mapping_path, get_processed_match_centre_dir, get_processed_path  # noqa: E402
from src.data.match_centre_milestones import build_batting_milestones  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build processed batting milestone records from local match-centre CSVs only.")
    add_club_args(parser, legacy_output=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = resolve_club_id(args.club)
    processed_root = get_processed_match_centre_dir(club_id=club_id)
    players_path = get_processed_path("players.csv", club_id=club_id)
    aliases_path = get_mapping_path("player_aliases.csv", club_id=club_id)
    milestones_path = processed_root / "all_batting_milestones.csv"
    validation_path = processed_root / "batting_milestones_validation.csv"

    print_club_header("Match-centre batting milestone builder", club_id)
    print_paths("Inputs", [processed_root, players_path, aliases_path])
    print_outputs("Outputs", [milestones_path, validation_path])
    print("Note: match-centre milestone outputs remain in the configured legacy match-centre folder for Phase 4.")
    if args.dry_run:
        print("Dry run complete. No files were written.")
        return 0

    processed_root.mkdir(parents=True, exist_ok=True)
    result = build_batting_milestones(
        processed_root,
        players_path=players_path,
        aliases_path=aliases_path,
    )
    result.milestones.to_csv(milestones_path, index=False)
    result.validation.to_csv(validation_path, index=False)
    fastest_50s = int(result.milestones["balls_to_50"].notna().sum()) if "balls_to_50" in result.milestones else 0
    fastest_100s = int(result.milestones["balls_to_100"].notna().sum()) if "balls_to_100" in result.milestones else 0
    print("Built match-centre batting milestones")
    print(f"- scopes: {', '.join(result.scopes) if result.scopes else 'none'}")
    print(f"- milestone rows: {len(result.milestones):,}")
    print(f"- verified 50s: {fastest_50s:,}")
    print(f"- verified 100s: {fastest_100s:,}")
    print(f"- validation warnings: {len(result.validation):,}")
    print(f"- wrote: {milestones_path}")
    print(f"- wrote: {validation_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
