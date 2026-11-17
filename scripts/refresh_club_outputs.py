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
from src.config.club_config import get_hall_of_fame_dir, get_player_profile_dir, get_processed_dir, get_season_overview_dir  # noqa: E402


DEPLOY_SAFE_STEPS = [
    ("Season Overview summaries", "build_season_overview_detail_exports.py"),
    ("Player Profile summaries", "build_player_profile_insight_exports.py"),
    ("Hall of Fame detail summaries", "build_hall_of_fame_detail_exports.py"),
    ("Hall of Fame premiership summaries", "build_premiership_hall_of_fame_exports.py"),
    ("Hall of Fame core aggregates", "build_hall_of_fame_core_exports.py"),
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Rebuild deploy-safe outputs for the active club.")
    add_club_args(parser)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = resolve_club_id(args.club)
    legacy_output = bool(getattr(args, "legacy_output", False))
    if legacy_output and club_id != "fvcc" and not args.dry_run:
        raise SystemExit("Privacy-safe weekly refresh refuses shared root output for non-FVCC clubs")
    from src.data.public_generic_identity_privacy import sanitize_public_processed_tree

    processed_dir = ROOT / "data" / "processed" if legacy_output else get_processed_dir(club_id=club_id)
    if not args.dry_run:
        sanitize_public_processed_tree(processed_dir, club_id=club_id, update_metadata=not legacy_output)
        if club_id == "fvcc" and not legacy_output:
            sanitize_public_processed_tree(ROOT / "data" / "processed", club_id=club_id, update_metadata=False)
    print_club_header("Club deploy-safe output refresh", club_id)
    print(f"- mode: {'dry run' if args.dry_run else 'rebuild from local inputs'}")
    print("- external fetch: no")
    print_paths(
        "Deploy-safe output roots",
        [
            get_hall_of_fame_dir(club_id=club_id),
            get_season_overview_dir(club_id=club_id),
            get_player_profile_dir(club_id=club_id),
        ],
    )

    commands = []
    for label, script_name in DEPLOY_SAFE_STEPS:
        command = [sys.executable, str(ROOT / "scripts" / script_name), "--club", club_id]
        if legacy_output:
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
    if club_id == "glen-waverley-hawks":
        from src.data.gwhcc_masked_privacy import sanitize_hawks_processed_tree

        redacted = sanitize_hawks_processed_tree(
            ROOT / "clubs" / club_id / "data" / "processed"
        )
        if redacted:
            print(f"Applied Hawks masked-participant privacy handling to {len(redacted)} processed exports.")
    privacy = sanitize_public_processed_tree(
        processed_dir, club_id=club_id, update_metadata=not legacy_output
    )
    print(f"Applied generic identity privacy handling to {len(privacy['files'])} processed exports.")
    if club_id == "fvcc" and not legacy_output:
        fallback = sanitize_public_processed_tree(
            ROOT / "data" / "processed", club_id=club_id, update_metadata=False
        )
        print(f"Applied FVCC generic identity privacy handling to {len(fallback['files'])} fallback exports.")
    if privacy["files"]:
        subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "build_hall_of_fame_core_exports.py"), "--club", club_id],
            cwd=ROOT,
            check=True,
        )
        prepared = sanitize_public_processed_tree(
            processed_dir, club_id=club_id, update_metadata=not legacy_output
        )
        if prepared["files"]:
            raise RuntimeError("Prepared Hall of Fame output reintroduced generic identity fields")
    print("Club deploy-safe outputs rebuilt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
