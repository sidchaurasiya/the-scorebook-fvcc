#!/usr/bin/env python3
"""Parse the single saved FVCC ball-by-ball discovery sample.

This script is sample-only: it reads the JSON files already saved under
data/raw/ball_by_ball_sample/ and writes pilot CSVs under
data/processed/ball_by_ball_sample/. It does not call external endpoints, does
not pull additional matches, and is safe to run offline.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.ball_by_ball_parser import parse_sample_directory  # noqa: E402


SAMPLE_DIR = ROOT / "data" / "raw" / "ball_by_ball_sample"
OUTPUT_DIR = ROOT / "data" / "processed" / "ball_by_ball_sample"


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    frames = parse_sample_directory(SAMPLE_DIR)

    for name, frame in frames.items():
        frame.to_csv(OUTPUT_DIR / f"{name}.csv", index=False)

    print("Parsed ball-by-ball sample")
    for name, frame in frames.items():
        print(f"- {name}.csv: {len(frame):,} rows")

    validation = frames["validation_report"]
    if not validation.empty and "status" in validation:
        counts = validation["status"].value_counts().to_dict()
        print(f"- validation: {counts}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

