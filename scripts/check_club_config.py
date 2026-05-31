from __future__ import annotations

import sys
import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.club_config import (  # noqa: E402
    LEGACY_DATA_PATHS,
    REPO_ROOT,
    allow_legacy_fallback,
    get_active_club_id,
    get_club_data_path,
    get_club_name,
    get_data_root,
    get_experimental_dir,
    get_hall_of_fame_dir,
    get_hall_of_fame_path,
    get_processed_dir,
    get_processed_match_centre_dir,
    get_processed_path,
    get_player_profile_dir,
    get_player_profile_path,
    get_raw_match_centre_dir,
    get_season_filter,
    get_season_overview_dir,
    get_season_overview_path,
    load_club_config,
    normalize_club_id,
)


CORE_PROCESSED_FILES = [
    "seasons.csv",
    "teams.csv",
    "players.csv",
    "all_seasons_batting.csv",
    "all_seasons_bowling.csv",
    "all_seasons_fielding.csv",
    "all_seasons_matches.csv",
    "all_seasons_scorecard_batting.csv",
    "all_seasons_scorecard_bowling.csv",
    "all_seasons_scorecard_fielding.csv",
]

HALL_OF_FAME_FILES = [
    "fastest_batting_milestones.csv",
    "player_bbb_batting_rates.csv",
    "player_bowling_milestones.csv",
    "player_premierships.csv",
    "player_scorecard_milestones.csv",
    "player_win_rates.csv",
    "premiership_wins.csv",
    "scorecard_record_links.csv",
]

SEASON_OVERVIEW_FILES = [
    "bbb_batting_rates_by_scope.csv",
    "bbb_bowling_dot_rates_by_scope.csv",
    "scorecard_batting_milestones_by_scope.csv",
    "scorecard_bowling_milestones_by_scope.csv",
    "season_by_round_scorecards.csv",
]

HELPER_PATHS = {
    "get_data_root": get_data_root,
    "get_processed_dir": get_processed_dir,
    "get_hall_of_fame_dir": get_hall_of_fame_dir,
    "get_season_overview_dir": get_season_overview_dir,
    "get_player_profile_dir": get_player_profile_dir,
    "get_raw_match_centre_dir": get_raw_match_centre_dir,
    "get_processed_match_centre_dir": get_processed_match_centre_dir,
    "get_experimental_dir": get_experimental_dir,
}

DIAGNOSTIC_HELPER_FILES = [
    ("get_processed_path", get_processed_path, "all_seasons_batting.csv"),
    ("get_hall_of_fame_path", get_hall_of_fame_path, "fastest_batting_milestones.csv"),
    ("get_season_overview_path", get_season_overview_path, "bbb_batting_rates_by_scope.csv"),
    ("get_player_profile_path", get_player_profile_path, "recent_form_batting.csv"),
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate and print resolved club config paths.")
    parser.add_argument("--club", default=None, help="Club config id. Defaults to CLUB_ID or fvcc.")
    parser.add_argument(
        "--strict-data-files",
        action="store_true",
        help="Fail if generated processed/deploy-safe files are missing.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = normalize_club_id(args.club) if args.club else get_active_club_id()
    try:
        config = load_club_config(club_id)
    except RuntimeError as error:
        print("Club config check failed:")
        print(f"- {error}")
        return 1
    failures: list[str] = []
    club_config = config.get("club", {})
    season_filter = get_season_filter(club_id, config=config)

    print(f"Active club ID: {club_id}")
    print(f"Club display name: {get_club_name(club_id)}")
    print(f"App name: {club_config.get('app_name', 'The Scorebook')}")
    print(f"PlayCricket club ID: {club_config.get('playcricket_club_id', '')}")
    print(f"Legacy fallback enabled: {allow_legacy_fallback(club_id, config=config)}")
    if season_filter["include_seasons"] or season_filter["include_season_ids"]:
        scope = ", ".join([*season_filter["include_seasons"], *season_filter["include_season_ids"]])
        print(f"Season filter: {scope}")
    else:
        print("Season filter: none")

    data_config = config.get("data", {})
    for key in [
        "root_dir",
        "processed_dir",
        "hall_of_fame_dir",
        "season_overview_dir",
        "player_profile_dir",
        "raw_match_centre_dir",
        "processed_match_centre_dir",
        "experimental_dir",
        "mapping_dir",
        "allow_legacy_fallback",
    ]:
        if key not in data_config:
            failures.append(f"Missing data path config: {key}")
            continue
        if key == "allow_legacy_fallback":
            continue
        path = get_club_data_path(key, club_id=club_id)
        status = "OK" if path.exists() else "MISSING"
        print(f"{status}: {key} -> {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
        if args.strict_data_files and key in {"root_dir", "processed_dir", "hall_of_fame_dir", "season_overview_dir", "player_profile_dir"} and not path.exists():
            failures.append(f"Required data directory does not exist: {path}")

    print("\nHelper path checks:")
    for label, helper in HELPER_PATHS.items():
        path = helper(club_id=club_id)
        status = "OK" if path.exists() else "MISSING"
        print(f"{status}: {label} -> {relative_label(path)}")
        if args.strict_data_files and label in {"get_data_root", "get_processed_dir", "get_hall_of_fame_dir", "get_season_overview_dir", "get_player_profile_dir"} and not path.exists():
            failures.append(f"Required helper path does not exist: {path}")

    print("\nExplicit helper file checks:")
    for label, helper, filename in DIAGNOSTIC_HELPER_FILES:
        require_file(helper(filename, club_id=club_id), failures, label=f'{label}("{filename}")', strict=args.strict_data_files, club_id=club_id)

    processed_dir = get_processed_dir(club_id=club_id)
    for filename in CORE_PROCESSED_FILES:
        require_file(get_processed_path(filename, club_id=club_id), failures, strict=args.strict_data_files, club_id=club_id)

    hall_of_fame_dir = get_hall_of_fame_dir(club_id=club_id)
    for filename in HALL_OF_FAME_FILES:
        require_file(get_hall_of_fame_path(filename, club_id=club_id), failures, strict=args.strict_data_files, club_id=club_id)

    season_overview_dir = get_season_overview_dir(club_id=club_id)
    for filename in SEASON_OVERVIEW_FILES:
        require_file(get_season_overview_path(filename, club_id=club_id), failures, strict=args.strict_data_files, club_id=club_id)

    require_directory(hall_of_fame_dir, failures, strict=args.strict_data_files)
    require_directory(season_overview_dir, failures, strict=args.strict_data_files)

    if failures:
        print("\nClub config check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nClub config check passed.")
    return 0


def require_file(path: Path, failures: list[str], label: str | None = None, *, strict: bool, club_id: str) -> None:
    status = "OK" if path.exists() else "MISSING"
    label_prefix = f"{label} -> " if label else ""
    print(f"{status}: {label_prefix}{relative_label(path)} [{path_source_label(path, club_id=club_id)}]")
    if strict and not path.exists():
        failures.append(f"Required file does not exist: {path}")


def require_directory(path: Path, failures: list[str], *, strict: bool) -> None:
    status = "OK" if path.exists() and path.is_dir() else "MISSING"
    print(f"{status}: directory {relative_label(path)}")
    if strict and (not path.exists() or not path.is_dir()):
        failures.append(f"Required directory does not exist: {path}")


def relative_label(path: Path) -> Path:
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


def path_source_label(path: Path, *, club_id: str) -> str:
    resolved = path.resolve()
    data_config = load_club_config(club_id).get("data", {})
    for key in [
        "root_dir",
        "processed_dir",
        "hall_of_fame_dir",
        "season_overview_dir",
        "player_profile_dir",
        "mapping_dir",
    ]:
        configured = configured_root(data_config.get(key))
        legacy = configured_root(LEGACY_DATA_PATHS.get(key))
        if configured and is_relative_to(resolved, configured):
            return "club data"
        if legacy and is_relative_to(resolved, legacy):
            return "legacy fallback"
    return "external"


def configured_root(value: object) -> Path | None:
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path.resolve()


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
