#!/usr/bin/env python3
"""Scrub identity IDs from generic public processed rows without changing figures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.public_generic_identity_privacy import sanitize_public_processed_tree  # noqa: E402

ACTIVE_CLUBS = ("georges-river-district", "glen-waverley-hawks", "fvcc")


def all_configured_clubs() -> list[str]:
    return list(ACTIVE_CLUBS)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--club", help="Sanitize one explicit club tree.")
    parser.add_argument(
        "--all-public",
        action="store_true",
        help="Sanitize only the active club trees plus FVCC's explicit root fallback.",
    )
    args = parser.parse_args()
    if bool(args.club) == bool(args.all_public):
        parser.error("Choose exactly one of --club or --all-public")
    results: dict[str, object] = {}
    if args.club:
        club = str(args.club).strip().casefold()
        processed = ROOT / "clubs" / club / "data" / "processed"
        results[club] = sanitize_public_processed_tree(processed, club_id=club)
        if club == "fvcc":
            results["fvcc_root_fallback"] = sanitize_public_processed_tree(
                ROOT / "data" / "processed", club_id=club, update_metadata=False
            )
    else:
        for club in all_configured_clubs():
            results[club] = sanitize_public_processed_tree(
                ROOT / "clubs" / club / "data" / "processed", club_id=club
            )
        results["fvcc_root_fallback"] = sanitize_public_processed_tree(
            ROOT / "data" / "processed", club_id="fvcc", update_metadata=False
        )
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
