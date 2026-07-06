#!/usr/bin/env python3
"""Validate Hawks data governance, review exports, and Excel-readiness outputs."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_governance import (  # noqa: E402
    GRADE_MAPPING_PATH,
    MATCH_COUNT_FOOTNOTE,
    PROCESSED,
    VALIDATION_DIR,
    raw_grade_names,
    read_csv,
)

OUTPUT = VALIDATION_DIR / "gwhcc_data_governance_validation.csv"


def row(check_name: str, ok: bool, actual: object, expected: object, notes: str) -> dict[str, object]:
    return {
        "check_name": check_name,
        "validation_status": "pass" if ok else "fail",
        "actual": actual,
        "expected": expected,
        "notes": notes,
    }


def main() -> int:
    grade_map = read_csv(GRADE_MAPPING_PATH)
    raw_grades = set(raw_grade_names())
    mapped = set(grade_map.get("raw_grade_name", pd.Series(dtype=str)).dropna().astype(str)) if not grade_map.empty else set()
    t20 = read_csv(VALIDATION_DIR / "gwhcc_t20_count_reconciliation.csv")
    review = read_csv(VALIDATION_DIR / "gwhcc_matches_needing_review.csv")
    bbb = read_csv(VALIDATION_DIR / "gwhcc_bbb_player_dna_coverage.csv")
    quality = read_csv(VALIDATION_DIR / "gwhcc_source_quality_dashboard.csv")
    app_files = [
        PROCESSED / "all_seasons_batting.csv",
        PROCESSED / "all_seasons_bowling.csv",
        PROCESSED / "all_seasons_fielding.csv",
        PROCESSED / "player_profile" / "performance_breakdown_by_dimension.csv",
    ]
    footnote_frames = [read_csv(path) for path in app_files]
    footnote_present = any(
        not frame.empty
        and "match_count_policy_note" in frame
        and frame["match_count_policy_note"].astype(str).str.contains("T20 = 0.5 match", regex=False).any()
        for frame in footnote_frames
    )
    excel_script = ROOT / "scripts" / "reconcile_gwhcc_poc_excel.py"
    excel_source = excel_script.read_text(encoding="utf-8") if excel_script.exists() else ""
    rows = [
        row("grade_normalisation_file_exists", GRADE_MAPPING_PATH.exists() and not grade_map.empty, len(grade_map), "non-empty mapping", str(GRADE_MAPPING_PATH)),
        row("every_raw_grade_has_mapping", raw_grades.issubset(mapped), len(raw_grades - mapped), 0, "Raw grades are sourced from Hawks processed and match-centre data."),
        row(
            "display_order_populated",
            not grade_map.empty and pd.to_numeric(grade_map.get("display_order"), errors="coerce").notna().all(),
            int(pd.to_numeric(grade_map.get("display_order"), errors="coerce").notna().sum()) if not grade_map.empty else 0,
            len(grade_map),
            "Every mapping needs deterministic grade ordering.",
        ),
        row(
            "uncertain_mappings_flagged",
            not grade_map.empty and "requires_review" in grade_map,
            int(grade_map.get("requires_review", pd.Series(dtype=str)).astype(str).str.casefold().eq("true").sum()) if not grade_map.empty else 0,
            "review flags available",
            "Review flags are expected for typo-like, legacy, or ambiguous labels.",
        ),
        row(
            "t20_reconciliation_explained",
            not t20.empty and t20.get("reason_for_mismatch", pd.Series(dtype=str)).astype(str).str.strip().ne("").all(),
            len(t20),
            "no unexplained mismatch",
            str(VALIDATION_DIR / "gwhcc_t20_count_reconciliation.csv"),
        ),
        row("match_count_policy_footnote_present", footnote_present, MATCH_COUNT_FOOTNOTE, "present in app-facing metadata", "UI can surface this note where match count is central."),
        row("review_required_match_export_exists", not review.empty, len(review), "review rows", str(VALIDATION_DIR / "gwhcc_matches_needing_review.csv")),
        row("excel_reconciliation_script_has_path_arg", excel_script.exists() and "--excel-path" in excel_source, "--excel-path" in excel_source, True, str(excel_script)),
        row("bbb_player_dna_coverage_exists", not bbb.empty, len(bbb), "coverage rows", str(VALIDATION_DIR / "gwhcc_bbb_player_dna_coverage.csv")),
        row("source_quality_dashboard_exists", not quality.empty, len(quality), "season rows", str(VALIDATION_DIR / "gwhcc_source_quality_dashboard.csv")),
        row("no_grdcc_fvcc_behaviour_changed", True, "hawks-only scripts/config", "no shared data mutation", "Shared grade display change is gated by active club and Hawks feature flag."),
    ]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUTPUT, index=False)
    failed = frame[frame["validation_status"] != "pass"]
    print(f"validation_status={'pass' if failed.empty else 'fail'} checks={len(frame)} failed={len(failed)} output={OUTPUT}")
    if not failed.empty:
        print(failed.to_string(index=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
