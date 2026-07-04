#!/usr/bin/env python3
"""Run the FVCC match-day refresh sequence and validate app-facing outputs."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh FVCC aggregate, match-centre, deploy-safe, and validation outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Print the command sequence without running it.")
    parser.add_argument(
        "--skip-live-refresh",
        action="store_true",
        help="Rebuild deploy-safe outputs and validators from existing local data only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    python = sys.executable
    commands: list[list[str]] = []
    if not args.skip_live_refresh:
        commands.append([python, "scripts/refresh_data.py", "--club", "fvcc", "--with-current-match-centre"])
    commands.extend(
        [
            [python, "scripts/refresh_club_outputs.py", "--club", "fvcc"],
            [python, "scripts/audit_fvcc_player_refresh_propagation.py"],
            [python, "scripts/validate_fvcc_app_wide_refresh_propagation.py"],
        ]
    )

    print("FVCC app data refresh sequence")
    print(f"- mode: {'dry run' if args.dry_run else 'execute'}")
    print(f"- live fetch: {'no' if args.skip_live_refresh else 'yes'}")
    for command in commands:
        print("- " + " ".join(command))

    if args.dry_run:
        return 0

    for command in commands:
        subprocess.run(command, cwd=ROOT, check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
