#!/usr/bin/env python3
"""Export Hawks PlayHQ matches that need manual data-quality review."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_governance import VALIDATION_DIR, write_matches_needing_review  # noqa: E402


def main() -> int:
    frame = write_matches_needing_review()
    print(f"matches_needing_review_status=pass rows={len(frame)} output={VALIDATION_DIR / 'gwhcc_matches_needing_review.csv'}")
    print(f"summary={VALIDATION_DIR / 'gwhcc_matches_needing_review_summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
