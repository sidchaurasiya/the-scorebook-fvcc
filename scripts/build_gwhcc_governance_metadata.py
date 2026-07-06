#!/usr/bin/env python3
"""Build Hawks governance metadata exports and app-facing grade annotations."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_governance import (  # noqa: E402
    annotate_app_files,
    write_bbb_player_dna_coverage,
    write_grade_normalisation,
    write_source_quality_dashboard,
    write_t20_reconciliation,
)


def main() -> int:
    grade_map = write_grade_normalisation()
    changed = annotate_app_files()
    t20 = write_t20_reconciliation()
    bbb = write_bbb_player_dna_coverage()
    quality = write_source_quality_dashboard()
    print(
        "gwhcc_governance_status=pass "
        f"raw_grades={len(grade_map)} "
        f"review_grade_mappings={grade_map['requires_review'].astype(str).str.casefold().eq('true').sum()} "
        f"annotated_files={len(changed)} "
        f"t20_reconciliation_rows={len(t20)} "
        f"bbb_coverage_rows={len(bbb)} "
        f"source_quality_rows={len(quality)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
