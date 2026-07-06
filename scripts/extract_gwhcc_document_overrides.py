#!/usr/bin/env python3
"""Extract Hawks document override source files when manually downloaded."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_document_overrides import RAW_DIR, extract_documents  # noqa: E402


def main() -> int:
    result = extract_documents()
    print(
        "gwhcc_document_extraction_status=pass "
        f"raw_files={result['raw_files']} "
        f"record_overrides={result['record_overrides']} "
        f"premierships={result['premierships']} "
        f"raw_dir={RAW_DIR}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
