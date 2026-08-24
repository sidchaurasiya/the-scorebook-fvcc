#!/usr/bin/env python3
"""Build governed GRDCC verified ball-by-ball partnerships."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.club_config import get_hall_of_fame_dir, get_processed_match_centre_dir, get_processed_path  # noqa: E402
from src.data.partnerships import (  # noqa: E402
    build_governed_club_partnerships,
    write_governed_club_partnership_outputs,
)


CLUB_ID = "georges-river-district"
PREFIX = "grdcc"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None, help="Write to a deterministic staging directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = get_processed_match_centre_dir(club_id=CLUB_ID)
    if args.output_dir is None:
        output = get_hall_of_fame_dir(club_id=CLUB_ID) / "partnerships.csv"
        validation = get_processed_path("validation", club_id=CLUB_ID)
    else:
        output = args.output_dir.resolve() / "partnerships.csv"
        validation = args.output_dir.resolve() / "validation"
    result = build_governed_club_partnerships(club_id=CLUB_ID, match_centre_root=source)
    write_governed_club_partnership_outputs(result, output=output, validation_dir=validation, prefix=PREFIX)
    coverage = result.coverage.iloc[0]
    print(
        f"GRDCC partnerships: candidates={coverage['candidate_partnership_rows']} "
        f"published={coverage['published_partnership_rows']} rejected={coverage['rejected_partnership_rows']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
