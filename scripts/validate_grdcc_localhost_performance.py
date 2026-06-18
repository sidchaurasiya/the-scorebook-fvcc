from __future__ import annotations

import csv
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "src/ui/layout.py"
PERFORMANCE = ROOT / "src/utils/performance.py"
OVERRIDES = ROOT / "src/data/featured_record_overrides.py"
PROFILE_DIR = ROOT / "clubs/georges-river-district/data/processed/validation/performance"
PROFILE = PROFILE_DIR / "grdcc_localhost_load_profile.csv"
BENCHMARK = PROFILE_DIR / "grdcc_localhost_load_benchmark.csv"
OUTPUT = PROFILE_DIR / "grdcc_localhost_performance_validation.csv"


def changed_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line[3:] for line in result.stdout.splitlines() if len(line) > 3]


def main() -> int:
    layout = LAYOUT.read_text(encoding="utf-8")
    performance = PERFORMANCE.read_text(encoding="utf-8")
    overrides = OVERRIDES.read_text(encoding="utf-8")
    changed = changed_paths()
    raw_changed = [
        path
        for path in changed
        if path.startswith("clubs/georges-river-district/data/source/")
        or "/raw/" in path
        or path.endswith("all_seasons_batting.csv")
        or path.endswith("all_seasons_bowling.csv")
        or path.endswith("all_seasons_fielding.csv")
    ]
    fvcc_changed = [path for path in changed if path.startswith("clubs/fvcc/")]
    checks = [
        ("persistent_hof_cache", 'persist="disk"' in layout, "Prepared and lower-level HOF caches persist across localhost restarts."),
        ("single_group_rebuild_skipped", "if active_club_is_grdcc():\n            return None" in layout, "GRDCC single-team-group selection no longer rebuilds HOF data."),
        ("source_loader_cached", "_read_processed_table_cached" in layout or "read_processed_table" in layout, "Processed source reads use the existing cached loader."),
        ("override_lookup_cached", "@lru_cache(maxsize=16)" in overrides and "featured_record_overrides_mtime" in overrides, "Required Annual Report lookups are cached and included in the HOF cache key."),
        ("profiling_opt_in", "GRDCC_PERF_PROFILE" in performance, "CSV profiling is disabled during normal runtime unless explicitly enabled."),
        ("profile_output", PROFILE.exists() and PROFILE.stat().st_size > 0, "Stage profile exists."),
        ("benchmark_output", BENCHMARK.exists() and BENCHMARK.stat().st_size > 0, "Before/after benchmark exists."),
        ("annual_report_override_path", "apply_featured_record_overrides" in layout, "HOF and profile override helper remains active."),
        ("season_overview_route", "render_overview(dashboard_data)" in layout, "Season Overview route remains present."),
        ("player_profile_route", "render_player_profile_page()" in layout, "Player Profile route remains present."),
        ("milestone_route", "render_approaching_milestones_page()" in layout, "Milestone route remains present."),
        ("no_raw_source_changes", not raw_changed, "; ".join(raw_changed)),
        ("no_fvcc_data_changes", not fvcc_changed, "; ".join(fvcc_changed)),
    ]
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "validation_status", "details"])
        writer.writeheader()
        for check, passed, details in checks:
            writer.writerow(
                {
                    "check": check,
                    "validation_status": "pass" if passed else "fail",
                    "details": details,
                }
            )
    failed = [check for check, passed, _ in checks if not passed]
    print(f"validation_status={'fail' if failed else 'pass'} checks={len(checks)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
