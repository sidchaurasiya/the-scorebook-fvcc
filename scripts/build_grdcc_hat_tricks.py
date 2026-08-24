#!/usr/bin/env python3
"""Build governed GRDCC Hall of Fame hat-trick outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.club_config import get_hall_of_fame_dir, get_processed_match_centre_dir, get_processed_path  # noqa: E402
from src.data.hat_tricks import build_governed_club_hat_tricks, write_governed_hat_trick_outputs  # noqa: E402


CLUB_ID = "georges-river-district"
PREFIX = "grdcc"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=None, help="Write to a deterministic staging directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = get_processed_match_centre_dir(club_id=CLUB_ID)
    processed = get_processed_path(club_id=CLUB_ID)
    if args.output_dir is None:
        output = get_hall_of_fame_dir(club_id=CLUB_ID) / "hat_tricks.csv"
        validation_dir = processed / "validation"
    else:
        output = args.output_dir.resolve() / "hat_tricks.csv"
        validation_dir = args.output_dir.resolve() / "validation"
    result = build_governed_club_hat_tricks(
        club_id=CLUB_ID,
        match_centre_root=source,
        club_processed_root=processed,
    )
    write_governed_hat_trick_outputs(
        result,
        hall_of_fame_output=output,
        validation_dir=validation_dir,
        prefix=PREFIX,
    )
    failures = result.validation[result.validation["status"].eq("FAIL")]
    coverage = result.coverage.iloc[0]
    print(
        f"GRDCC hat-tricks: candidates={coverage['candidate_sequences']} "
        f"confirmed={coverage['confirmed_candidates']} rejected={coverage['rejected_candidates']} "
        f"review={coverage['review_candidates']}"
    )
    return 1 if not failures.empty else 0


if __name__ == "__main__":
    raise SystemExit(main())
