#!/usr/bin/env python3
"""Parse the single saved FVCC match-centre discovery sample.

This is offline sample parsing only. It reads JSON files already captured under
data/raw/ball_by_ball_sample/, does not call PlayCricket or PlayHQ, is safe to
run repeatedly, and writes isolated pilot CSVs under
data/processed/match_centre_sample/. It does not affect the Streamlit app or
the existing aggregate stats refresh pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.match_centre_parser import parse_sample_directory  # noqa: E402


SAMPLE_DIR = ROOT / "data" / "raw" / "ball_by_ball_sample"
OUTPUT_DIR = ROOT / "data" / "processed" / "match_centre_sample"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = parse_sample_directory(SAMPLE_DIR)

    for name, frame in frames.items():
        frame.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)

    print("Parsed match-centre sample")
    for name, frame in frames.items():
        print(f"- {name}.csv: {len(frame):,} rows")

    validation = frames["validation_report"]
    if not validation.empty and "status" in validation:
        print(f"- validation: {validation['status'].value_counts().to_dict()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

