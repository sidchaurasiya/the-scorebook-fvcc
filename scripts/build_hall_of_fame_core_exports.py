#!/usr/bin/env python3
"""Build deploy-safe Hall of Fame core aggregates from local processed data."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.club_refresh_utils import add_club_args, print_club_header, print_outputs, resolve_club_id  # noqa: E402
from src.config.club_config import get_hall_of_fame_dir  # noqa: E402
from src.data.hall_of_fame_prepared import FRAME_FILENAMES, GREATEST_SEASONS_FILENAME, MANIFEST_FILENAME  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deploy-safe Hall of Fame core aggregates.")
    add_club_args(parser)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = resolve_club_id(args.club)
    os.environ["CLUB_ID"] = club_id
    os.environ["SCOREBOOK_IGNORE_PREPARED_HOF"] = "1"

    from src.data.hall_of_fame_prepared import write_prepared_hall_of_fame_core
    from src.data.playcricket_ingestion import metadata_mtime
    from src.ui import layout
    from src.utils.player_identity import player_aliases_mtime

    output_dir = ROOT / "data" / "processed" / "hall_of_fame" if args.legacy_output else get_hall_of_fame_dir(club_id=club_id)
    output_paths = [output_dir / filename for filename in (*FRAME_FILENAMES.values(), GREATEST_SEASONS_FILENAME, MANIFEST_FILENAME)]
    print_club_header("Hall of Fame deploy-safe core export builder", club_id)
    print_outputs("Outputs", output_paths)
    if args.dry_run:
        print("Dry run complete. No files were written.")
        return 0

    historical = layout.load_hall_of_fame_data(
        metadata_mtime(),
        player_aliases_mtime(club_id=club_id),
        layout.HALL_OF_FAME_DATA_VERSION,
        club_id=club_id,
    )
    if historical is None:
        print("No historical data available; Hall of Fame core exports were not built.")
        return 1
    best_batting = layout.best_batting_season(historical["batting_raw"])
    best_bowling = layout.best_bowling_season(historical["bowling_raw"])
    written = write_prepared_hall_of_fame_core(
        club_id,
        layout.HALL_OF_FAME_DATA_VERSION,
        {
            "batting": historical["batting"],
            "bowling": historical["bowling"],
            "fielding": historical["fielding"],
            "all_time": historical["all_time"],
        },
        best_batting,
        best_bowling,
        output_dir=output_dir,
    )
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
