"""Apply FVCC's reused-placeholder guard to its committed scorecard outputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.fvcc_scorecard_privacy import FVCC_CLUB_ID, sanitize_fvcc_processed_scorecards


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--club", required=True, help="Must be fvcc; other clubs are rejected.")
    parser.add_argument(
        "--processed-dir",
        type=Path,
        default=ROOT / "clubs" / FVCC_CLUB_ID / "data" / "processed",
    )
    args = parser.parse_args()
    if str(args.club).strip().casefold() != FVCC_CLUB_ID:
        parser.error("This sanitizer is restricted to the FVCC processed tree.")
    print(json.dumps(sanitize_fvcc_processed_scorecards(args.processed_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
