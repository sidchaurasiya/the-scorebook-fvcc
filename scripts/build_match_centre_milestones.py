#!/usr/bin/env python3
"""Build processed batting milestone records from local match-centre CSVs only.

This script does not call PlayCricket or PlayHQ. It reads already processed
match-centre scope outputs under data/processed/match_centre/ and writes the
Hall of Fame milestone inputs back to that processed folder.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.match_centre_milestones import build_batting_milestones  # noqa: E402


def main() -> int:
    processed_root = ROOT / "data" / "processed" / "match_centre"
    processed_root.mkdir(parents=True, exist_ok=True)
    result = build_batting_milestones(
        processed_root,
        players_path=ROOT / "data" / "processed" / "players.csv",
        aliases_path=ROOT / "data" / "player_aliases.csv",
    )
    milestones_path = processed_root / "all_batting_milestones.csv"
    validation_path = processed_root / "batting_milestones_validation.csv"
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
