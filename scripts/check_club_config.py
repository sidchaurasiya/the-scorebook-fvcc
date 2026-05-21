from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.club_config import (  # noqa: E402
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
    get_raw_match_centre_dir,
    get_season_overview_dir,
    get_season_overview_path,
    load_club_config,
)


CORE_PROCESSED_FILES = [
    "seasons.csv",
    "teams.csv",
    "players.csv",
    "all_seasons_batting.csv",
    "all_seasons_bowling.csv",
    "all_seasons_fielding.csv",
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
    "get_raw_match_centre_dir": get_raw_match_centre_dir,
    "get_processed_match_centre_dir": get_processed_match_centre_dir,
    "get_experimental_dir": get_experimental_dir,
}

DIAGNOSTIC_HELPER_FILES = [
    ("get_processed_path", get_processed_path, "all_seasons_batting.csv"),
    ("get_hall_of_fame_path", get_hall_of_fame_path, "fastest_batting_milestones.csv"),
    ("get_season_overview_path", get_season_overview_path, "bbb_batting_rates_by_scope.csv"),
]


def main() -> int:
    club_id = get_active_club_id()
    try:
        config = load_club_config(club_id)
    except RuntimeError as error:
        print("Club config check failed:")
        print(f"- {error}")
        return 1
    failures: list[str] = []
    club_config = config.get("club", {})

    print(f"Active club ID: {club_id}")
    print(f"Club display name: {get_club_name(club_id)}")
    print(f"App name: {club_config.get('app_name', 'The Scorebook')}")

    data_config = config.get("data", {})
    for key in [
        "root_dir",
        "processed_dir",
        "hall_of_fame_dir",
        "season_overview_dir",
        "raw_match_centre_dir",
        "processed_match_centre_dir",
        "experimental_dir",
    ]:
        if key not in data_config:
            failures.append(f"Missing data path config: {key}")
            continue
        path = get_club_data_path(key, club_id=club_id)
        status = "OK" if path.exists() else "MISSING"
        print(f"{status}: {key} -> {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
        if key in {"root_dir", "processed_dir", "hall_of_fame_dir", "season_overview_dir"} and not path.exists():
            failures.append(f"Required data directory does not exist: {path}")

    print("\nHelper path checks:")
    for label, helper in HELPER_PATHS.items():
        path = helper(club_id=club_id)
        status = "OK" if path.exists() else "MISSING"
        print(f"{status}: {label} -> {relative_label(path)}")
        if label in {"get_data_root", "get_processed_dir", "get_hall_of_fame_dir", "get_season_overview_dir"} and not path.exists():
            failures.append(f"Required helper path does not exist: {path}")

    print("\nExplicit helper file checks:")
    for label, helper, filename in DIAGNOSTIC_HELPER_FILES:
        require_file(helper(filename, club_id=club_id), failures, label=f'{label}("{filename}")')

    processed_dir = get_processed_dir(club_id=club_id)
    for filename in CORE_PROCESSED_FILES:
        require_file(get_processed_path(filename, club_id=club_id), failures)

    hall_of_fame_dir = get_hall_of_fame_dir(club_id=club_id)
    for filename in HALL_OF_FAME_FILES:
        require_file(get_hall_of_fame_path(filename, club_id=club_id), failures)

    season_overview_dir = get_season_overview_dir(club_id=club_id)
    for filename in SEASON_OVERVIEW_FILES:
        require_file(get_season_overview_path(filename, club_id=club_id), failures)

    require_directory(hall_of_fame_dir, failures)
    require_directory(season_overview_dir, failures)

    if failures:
        print("\nClub config check failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("\nClub config check passed.")
    return 0


def require_file(path: Path, failures: list[str], label: str | None = None) -> None:
    status = "OK" if path.exists() else "MISSING"
    label_prefix = f"{label} -> " if label else ""
    print(f"{status}: {label_prefix}{relative_label(path)}")
    if not path.exists():
        failures.append(f"Required file does not exist: {path}")


def require_directory(path: Path, failures: list[str]) -> None:
    status = "OK" if path.exists() and path.is_dir() else "MISSING"
    print(f"{status}: directory {relative_label(path)}")
    if not path.exists() or not path.is_dir():
        failures.append(f"Required directory does not exist: {path}")


def relative_label(path: Path) -> Path:
    return path.relative_to(ROOT) if path.is_relative_to(ROOT) else path


if __name__ == "__main__":
    raise SystemExit(main())
