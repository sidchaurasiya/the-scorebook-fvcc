#!/usr/bin/env python3
"""Rebuild deploy-safe club outputs from existing local processed inputs.

This wrapper does not fetch external data. It coordinates the small tracked
summary exports used by the production app.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.club_refresh_utils import add_club_args, print_club_header, print_paths, resolve_club_id  # noqa: E402
from src.config.club_config import get_hall_of_fame_dir, get_processed_dir, get_season_overview_dir  # noqa: E402


DEPLOY_SAFE_STEPS = [
    ("Season Overview summaries", "build_season_overview_detail_exports.py"),
    ("Player Profile summaries", "build_player_profile_insight_exports.py"),
    ("Hall of Fame detail summaries", "build_hall_of_fame_detail_exports.py"),
    ("Hall of Fame premiership summaries", "build_premiership_hall_of_fame_exports.py"),
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild deploy-safe outputs for the active club.")
    add_club_args(parser)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = resolve_club_id(args.club)
    print_club_header("Club deploy-safe output refresh", club_id)
    print(f"- mode: {'dry run' if args.dry_run else 'rebuild from local inputs'}")
    print("- external fetch: no")
    print_paths(
        "Deploy-safe output roots",
        [
            get_hall_of_fame_dir(club_id=club_id),
            get_season_overview_dir(club_id=club_id),
            get_processed_dir(club_id=club_id) / "player_profile",
        ],
    )

    commands = []
    for label, script_name in DEPLOY_SAFE_STEPS:
        command = [sys.executable, str(ROOT / "scripts" / script_name), "--club", club_id]
        if args.legacy_output:
            command.append("--legacy-output")
        if args.dry_run:
            command.append("--dry-run")
        commands.append((label, command))

    if args.dry_run:
        print("Future weekly refresh sequence:")
        print(f"- {sys.executable} {ROOT / 'scripts' / 'refresh_data.py'} --club {club_id}")
        print(
            f"- {sys.executable} {ROOT / 'scripts' / 'refresh_match_centre_data.py'} "
            f"--club {club_id} --season-id <season-id> --team-id <team-id> --output-scope-name <scope>"
        )
        print(f"- {sys.executable} {ROOT / 'scripts' / 'backfill_match_centre_available.py'} --club {club_id}")
        print(f"- {sys.executable} {ROOT / 'scripts' / 'refresh_club_outputs.py'} --club {club_id}")
        print()
        print("Would run:")
        for label, command in commands:
            print(f"- {label}: {' '.join(command)}")
        print("Dry run complete. No files were written.")
        return 0

    for label, command in commands:
        print(f"Running {label}")
        subprocess.run(command, cwd=ROOT, check=True)
    print("Club deploy-safe outputs rebuilt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
