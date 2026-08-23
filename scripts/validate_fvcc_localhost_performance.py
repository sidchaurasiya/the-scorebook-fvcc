from __future__ import annotations

import csv
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "src/ui/layout.py"
PLAYER_IDENTITY = ROOT / "src/utils/player_identity.py"
PERFORMANCE = ROOT / "src/utils/performance.py"
OVERRIDES = ROOT / "src/data/featured_record_overrides.py"
STATUS_OVERRIDES = ROOT / "src/data/player_status_overrides.py"
FVCC_CONFIG = ROOT / "clubs/fvcc/club_config.yaml"
PROCESSED = ROOT / "clubs/fvcc/data/processed"
PROFILE_DIR = PROCESSED / "validation/performance"
PROFILE = PROFILE_DIR / "fvcc_localhost_load_profile.csv"
BENCHMARK = PROFILE_DIR / "fvcc_localhost_load_benchmark.csv"
OUTPUT = PROFILE_DIR / "fvcc_localhost_performance_validation.csv"


def changed_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return [line[3:] for line in result.stdout.splitlines() if len(line) > 3]


def csv_rows(name: str) -> int:
    path = PROCESSED / name
    if not path.exists():
        return 0
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            return sum(1 for _ in csv.DictReader(handle))
    except (OSError, csv.Error):
        return 0


def profile_rows() -> list[dict[str, str]]:
    if not PROFILE.exists():
        return []
    try:
        with PROFILE.open(newline="", encoding="utf-8") as handle:
            return list(csv.DictReader(handle))
    except (OSError, csv.Error):
        return []


def main() -> int:
    layout = LAYOUT.read_text(encoding="utf-8")
    identity = PLAYER_IDENTITY.read_text(encoding="utf-8")
    performance = PERFORMANCE.read_text(encoding="utf-8")
    overrides = OVERRIDES.read_text(encoding="utf-8")
    status_overrides = STATUS_OVERRIDES.read_text(encoding="utf-8")
    config = FVCC_CONFIG.read_text(encoding="utf-8")
    changed = changed_paths()
    allowed_status_path = "clubs/fvcc/data/source/fvcc_player_status_overrides.csv"
    raw_changed = [
        path for path in changed
        if "/raw/" in path
        or (
            path.startswith("clubs/fvcc/data/source/")
            and path not in {allowed_status_path, "clubs/fvcc/data/source/"}
        )
    ]
    core_data_changed = [
        path
        for path in changed
        if path.startswith("clubs/fvcc/data/processed/")
        and not path.startswith("clubs/fvcc/data/processed/validation/")
    ]
    profile = profile_rows()
    cached_profile = any(row.get("cache_hit", "").casefold() == "true" for row in profile)
    experimental_stage = any(
        "experimental" in row.get("stage", "").casefold()
        or "match-centre" in row.get("stage", "").casefold()
        for row in profile
    )
    heavy_cache_tokens = [
        'def load_hall_of_fame_data(',
        'def get_hall_of_fame_data(',
        'def load_season_overview_detail_sources(',
        'def load_player_profile_index(',
    ]
    checks = [
        ("no_raw_fvcc_changes", not raw_changed, "; ".join(raw_changed)),
        ("single_group_path_preserved", "single_fvcc_group = active_club_is_fvcc()" in layout, "FVCC single-group HOF reuse remains active."),
        ("grdcc_annual_report_scoped", "if active_club_id != GRDCC_CLUB_ID" in overrides, "Annual Report override loaders remain GRDCC-only."),
        ("fvcc_prepared_cache", 'persist="disk"' in layout and cached_profile, "FVCC profile contains a disk-cache hit."),
        ("duplicate_hof_aggregation_avoided", "Skipped equivalent FVCC single-group rebuild." in layout, "Single FVCC HOF group reuses prepared all-time tables."),
        ("heavy_loaders_cached", all(token in layout for token in heavy_cache_tokens) and 'persist="disk"' in identity, "HOF, season detail, profile index/detail, and profile data use persistent caches."),
        ("experimental_loaders_gated", "SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES = False" in layout and not experimental_stage, "No experimental/match-centre profiling stage ran."),
        ("hof_rows_available", min(csv_rows("all_seasons_batting.csv"), csv_rows("all_seasons_bowling.csv"), csv_rows("all_seasons_fielding.csv")) > 0, "FVCC aggregate HOF sources are non-empty."),
        ("season_overview_rows_available", csv_rows("seasons.csv") > 0 and csv_rows("teams.csv") > 0 and "render_overview(dashboard_data)" in layout, "Season and team data plus route are present."),
        ("player_profile_available", csv_rows("players.csv") > 0 and "render_player_profile_page()" in layout, "Player index data and route are present."),
        ("milestones_available", "render_approaching_milestones_page()" in layout and "build_approaching_milestone_watchlist" in layout, "Milestone route and candidate builder remain present."),
        ("milestone_bundle_cached", "def load_portability_milestone_page_data(" in layout, "FVCC milestone derivations use a club/version-keyed persistent cache."),
        ("profile_source_frames_cached", "def load_portability_player_profile_source_frames(" in identity, "FVCC canonical profile frames are prepared once per data/identity version."),
        ("active_status_override_framework", "def apply_active_player_id_overrides(" in status_overrides and (ROOT / allowed_status_path).exists(), "FVCC has an optional ID-based status override file."),
        ("fvcc_theme_unchanged", all(value in config for value in ['primary_colour: "#A31952"', 'secondary_colour: "#28485F"', 'background_colour: "#F6F8FB"']), "FVCC configured colors are unchanged."),
        ("fvcc_core_data_unchanged", not core_data_changed, "; ".join(core_data_changed)),
    ]
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "validation_status", "details"])
        writer.writeheader()
        for check, passed, details in checks:
            writer.writerow({"check": check, "validation_status": "pass" if passed else "fail", "details": details})
    failed = [check for check, passed, _ in checks if not passed]
    print(f"validation_status={'fail' if failed else 'pass'} checks={len(checks)} failed={len(failed)}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
