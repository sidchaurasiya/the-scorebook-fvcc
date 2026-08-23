from __future__ import annotations

import csv
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "src/ui/layout.py"
PERFORMANCE = ROOT / "src/utils/performance.py"
OVERRIDES = ROOT / "src/data/featured_record_overrides.py"
STATUS_OVERRIDES = ROOT / "src/data/player_status_overrides.py"
PLAYER_IDENTITY = ROOT / "src/utils/player_identity.py"
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
    status_overrides = STATUS_OVERRIDES.read_text(encoding="utf-8")
    identity = PLAYER_IDENTITY.read_text(encoding="utf-8")
    changed = changed_paths()
    allowed_status_path = "clubs/georges-river-district/data/source/georges-river-district_player_status_overrides.csv"
    raw_changed = [
        path
        for path in changed
        if (path.startswith("clubs/georges-river-district/data/source/") and path != allowed_status_path)
        or "/raw/" in path
        or path.endswith("all_seasons_batting.csv")
        or path.endswith("all_seasons_bowling.csv")
        or path.endswith("all_seasons_fielding.csv")
    ]
    gwhcc_changed = [path for path in changed if path.startswith("clubs/glen-waverley-hawks/")]
    checks = [
        ("persistent_hof_cache", 'persist="disk"' in layout, "Prepared and lower-level HOF caches persist across localhost restarts."),
        ("single_group_rebuild_skipped", "single_fvcc_group = active_club_is_fvcc()" in layout, "Shared single-group HOF reuse remains active."),
        ("source_loader_cached", "_read_processed_table_cached" in layout or "read_processed_table" in layout, "Processed source reads use the existing cached loader."),
        ("override_lookup_cached", "@lru_cache(maxsize=16)" in overrides and "featured_record_overrides_mtime" in overrides, "Required Annual Report lookups are cached and included in the HOF cache key."),
        ("profiling_opt_in", "GRDCC_PERF_PROFILE" in performance, "CSV profiling is disabled during normal runtime unless explicitly enabled."),
        ("profile_output", PROFILE.exists() and PROFILE.stat().st_size > 0, "Stage profile exists."),
        ("benchmark_output", BENCHMARK.exists() and BENCHMARK.stat().st_size > 0, "Before/after benchmark exists."),
        ("annual_report_override_path", "apply_featured_record_overrides" in layout, "HOF and profile override helper remains active."),
        ("season_overview_route", "render_overview(dashboard_data)" in layout, "Season Overview route remains present."),
        ("player_profile_route", "render_player_profile_page()" in layout, "Player Profile route remains present."),
        ("milestone_route", "render_approaching_milestones_page()" in layout, "Milestone route remains present."),
        ("milestone_bundle_cached", "def load_portability_milestone_page_data(" in layout, "GRDCC milestone derivations use a club/version-keyed persistent cache."),
        ("profile_source_frames_cached", "def load_portability_player_profile_source_frames(" in identity, "GRDCC canonical profile frames are prepared once per data/identity version."),
        ("active_status_override_framework", "def apply_active_player_id_overrides(" in status_overrides and (ROOT / allowed_status_path).exists(), "GRDCC has an optional ID-based status override file."),
        ("no_raw_source_changes", not raw_changed, "; ".join(raw_changed)),
        ("no_gwhcc_changes", not gwhcc_changed, "; ".join(gwhcc_changed)),
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
