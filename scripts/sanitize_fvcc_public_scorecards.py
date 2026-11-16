"""Apply FVCC's reused-placeholder guard to its committed scorecard outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.fvcc_scorecard_privacy import (
    FVCC_CLUB_ID,
    sanitize_fvcc_processed_scorecards,
    sanitize_fvcc_scorecard_record_link_file,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--club", required=True, help="Must be fvcc; other clubs are rejected.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=ROOT / "clubs" / FVCC_CLUB_ID / "data" / "processed",
    )
    parser.add_argument(
        "--fallback-link-path",
        type=Path,
        default=ROOT / "data" / "processed" / "hall_of_fame" / "scorecard_record_links.csv",
        help="FVCC legacy fallback link artifact; sanitized in addition to the club tree.",
    )
    args = parser.parse_args()
    if str(args.club).strip().casefold() != FVCC_CLUB_ID:
        parser.error("This sanitizer is restricted to the FVCC processed tree.")
    result = sanitize_fvcc_processed_scorecards(args.processed_dir)
    if args.fallback_link_path.resolve() != (args.processed_dir / "hall_of_fame" / "scorecard_record_links.csv").resolve():
        result[args.fallback_link_path.as_posix()] = sanitize_fvcc_scorecard_record_link_file(args.fallback_link_path)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
