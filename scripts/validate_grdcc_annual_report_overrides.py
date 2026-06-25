#!/usr/bin/env python3
"""Validate GRDCC Annual Report featured-record overrides."""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
try:
    import pandas as pd
except ModuleNotFoundError:
    app_python = ROOT / ".venv-app" / "bin" / "python"
    if app_python.exists() and Path(sys.executable).resolve() != app_python.resolve():
        os.execv(str(app_python), [str(app_python), str(Path(__file__).resolve()), *sys.argv[1:]])
    raise

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.featured_record_overrides import (  # noqa: E402
    apply_featured_record_overrides,
    featured_record_override_path,
    load_featured_record_overrides,
)


CLUB_ID = "georges-river-district"
OUTPUT_DIR = ROOT / "clubs" / CLUB_ID / "data" / "processed" / "validation" / "annual_report_2024_25" / "featured_overrides"
VALIDATION_PATH = OUTPUT_DIR / "grdcc_annual_report_featured_overrides_validation.csv"
SUMMARY_PATH = OUTPUT_DIR / "grdcc_annual_report_featured_overrides_summary.csv"
REQUIRED_FIELDS = {
    "report_year",
    "annual_report_source",
    "record_category",
    "metric",
    "authoritative_value",
    "override_reason",
    "applies_to_app_sections",
}


def write_rows(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    override_path = featured_record_override_path(CLUB_ID)
    overrides = load_featured_record_overrides(CLUB_ID)
    checks: list[dict[str, object]] = []

    def check(name: str, passed: bool, details: str) -> None:
        checks.append({"check": name, "status": "pass" if passed else "fail", "details": details})

    check("override_file_loads", override_path.exists() and not overrides.empty, str(override_path))
    check("required_fields_present", REQUIRED_FIELDS.issubset(overrides.columns), ", ".join(sorted(REQUIRED_FIELDS)))
    if REQUIRED_FIELDS.issubset(overrides.columns):
        missing = overrides[list(REQUIRED_FIELDS)].astype(str).apply(lambda column: column.str.strip().eq("")).any(axis=1)
        check("required_values_populated", not missing.any(), f"rows with missing required values: {int(missing.sum())}")

    expected = {
        ("harry milburn", "career_runs"): (10788, 8865),
        ("gordon leslie", "career_wickets"): (707, 242),
    }
    for (player, metric), (authoritative, accounted) in expected.items():
        matches = overrides[
            overrides["normalized_player_name"].eq(player) & overrides["metric"].eq(metric)
        ]
        found = len(matches) == 1
        check(f"{player.replace(' ', '_')}_{metric}_exists", found, f"matching rows: {len(matches)}")
        if found:
            row = matches.iloc[0]
            actual = int(float(row["authoritative_value"]))
            recorded_accounted = int(float(row["accounted_value_in_final_logic"]))
            check(f"{player.replace(' ', '_')}_{metric}_value", actual == authoritative, f"value: {actual}")
            check(
                f"{player.replace(' ', '_')}_{metric}_differs_from_accounted",
                actual != recorded_accounted and recorded_accounted == accounted,
                f"authoritative={actual}; accounted={recorded_accounted}",
            )

    sample = pd.DataFrame(
        [
            {"Player": "Harry Milburn", "Runs": 8865, "Wickets": 0},
            {"Player": "Gordon Leslie", "Runs": 0, "Wickets": 242},
        ]
    )
    applied = apply_featured_record_overrides(sample, CLUB_ID)
    harry_runs = int(applied.loc[applied["Player"].eq("Harry Milburn"), "Runs"].iloc[0])
    gordon_wickets = int(applied.loc[applied["Player"].eq("Gordon Leslie"), "Wickets"].iloc[0])
    check("presentation_copy_applies_harry", harry_runs == 10788, f"display value: {harry_runs}")
    check("presentation_copy_applies_gordon", gordon_wickets == 707, f"display value: {gordon_wickets}")
    check("input_dataframe_not_mutated", int(sample.iloc[0]["Runs"]) == 8865 and int(sample.iloc[1]["Wickets"]) == 242, "source frame unchanged")
    duplicate_sample = pd.DataFrame(
        [
            {"Player": "Harry Milburn", "Runs": 7974, "Wickets": 0},
            {"Player": "Harry Milburn", "Runs": 891, "Wickets": 0},
            {"Player": "Gordon Leslie", "Runs": 0, "Wickets": 242},
            {"Player": "Gordon Leslie", "Runs": 0, "Wickets": 85},
        ]
    )
    collapsed = apply_featured_record_overrides(duplicate_sample, CLUB_ID)
    check(
        "overridden_display_names_are_unique",
        int(collapsed["Player"].eq("Harry Milburn").sum()) == 1 and int(collapsed["Player"].eq("Gordon Leslie").sum()) == 1,
        "one featured row per approved player",
    )
    check("non_grdcc_not_applied", load_featured_record_overrides("fvcc").empty, "FVCC returns no overrides")
    check("all_overrides_all_time_only", overrides["record_scope"].eq("all_time").all() and overrides["season"].eq("").all(), "no season-level overrides")
    check("report_scope_excludes_2025_26", overrides["report_year"].eq("2024/25").all(), "all rows use the 2024/25 report")
    check(
        "metrics_are_featured_career_only",
        set(overrides["metric"]).issubset({"career_runs", "career_wickets"}),
        ", ".join(sorted(set(overrides["metric"]))),
    )

    write_rows(VALIDATION_PATH, checks, ["check", "status", "details"])
    failed = [row for row in checks if row["status"] == "fail"]
    summary = [
        {"metric": "override_rows_loaded", "value": len(overrides)},
        {"metric": "validation_checks", "value": len(checks)},
        {"metric": "validation_passes", "value": len(checks) - len(failed)},
        {"metric": "validation_failures", "value": len(failed)},
        {"metric": "harry_milburn_displayed_runs", "value": harry_runs},
        {"metric": "gordon_leslie_displayed_wickets", "value": gordon_wickets},
        {"metric": "non_grdcc_override_rows", "value": len(load_featured_record_overrides("fvcc"))},
        {"metric": "season_level_override_rows", "value": int(overrides["season"].ne("").sum())},
    ]
    write_rows(SUMMARY_PATH, summary, ["metric", "value"])

    print(f"Overrides loaded: {len(overrides)}")
    print(f"Validation checks: {len(checks)}")
    print(f"Failures: {len(failed)}")
    print(f"Harry Milburn displayed runs: {harry_runs:,}")
    print(f"Gordon Leslie displayed wickets: {gordon_wickets:,}")
    print(f"Validation output: {VALIDATION_PATH}")
    print(f"Summary output: {SUMMARY_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
