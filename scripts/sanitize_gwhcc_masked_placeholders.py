#!/usr/bin/env python3
"""Idempotently anonymize reused masked Hawks participant tokens in outputs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_masked_privacy import HAWKS_CLUB_ID, sanitize_hawks_processed_tree
from src.data.public_generic_identity_privacy import sanitize_public_processed_tree


def main() -> int:
    processed = ROOT / "clubs" / HAWKS_CLUB_ID / "data" / "processed"
    changed = sanitize_hawks_processed_tree(processed)
    generic = sanitize_public_processed_tree(processed, club_id=HAWKS_CLUB_ID)
    print(json.dumps({"club": HAWKS_CLUB_ID, "placeholder_changed_files": changed, "generic_identity_changed_files": len(generic["files"]), "rows_scanned": generic["rows_processed"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
