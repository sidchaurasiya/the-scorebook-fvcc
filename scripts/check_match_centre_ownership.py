#!/usr/bin/env python3
"""Read-only ownership column diagnostics for local match-centre outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.club_refresh_utils import add_club_args, get_club_team_ids, print_club_header, resolve_club_id  # noqa: E402
from src.config.club_config import get_club_name, get_processed_match_centre_dir  # noqa: E402
from src.data.match_centre_ownership import add_club_match_ownership, ensure_club_ownership_columns  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check local match-centre ownership columns without fetching or writing.")
    add_club_args(parser, legacy_output=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = resolve_club_id(args.club)
    root = get_processed_match_centre_dir(club_id=club_id)
    club_team_ids = get_club_team_ids(club_id)
    print_club_header("Match-centre ownership diagnostic", club_id)
    print("- external fetch: no")
    print("- writes: no")
    print(f"- match-centre processed root: {relative(root)}")
    print(f"- configured club team IDs: {len(club_team_ids):,}")
    scopes = [path for path in sorted(root.iterdir()) if path.is_dir()] if root.exists() else []
    if not scopes:
        print("No local processed match-centre scopes found.")
        return 0

    for scope in scopes:
        print(f"\nScope: {scope.name}")
        report_matches(scope, club_team_ids, get_club_name(club_id))
        report_identity(scope)
    print("\nOwnership diagnostic complete.")
    return 0


def report_matches(scope: Path, club_team_ids: set[str], club_name: str) -> None:
    matches = read_csv(scope / "all_matches.csv")
    if matches.empty:
        print("- all_matches.csv: missing or empty")
        return
    original_columns = set(matches.columns)
    normalized = add_club_match_ownership(matches, club_team_ids=club_team_ids, club_name_token=club_name)
    team_ids = sorted(
        {
            str(value).strip()
            for value in normalized.get("club_team_id", pd.Series(dtype="object")).dropna().astype(str)
            if str(value).strip() and str(value).strip().casefold() not in {"nan", "none"}
        }
    )
    team_names = sorted(
        {
            str(value).strip()
            for value in normalized.get("club_team_name", pd.Series(dtype="object")).dropna().astype(str)
            if str(value).strip() and str(value).strip().casefold() not in {"nan", "none"}
        }
    )
    print(f"- all_matches.csv rows: {len(matches):,}")
    print(f"  old columns: {column_flags(original_columns, ['fvcc_team_id', 'fvcc_team_name'])}")
    print(f"  neutral columns: {column_flags(original_columns, ['club_team_id', 'club_team_name'])}")
    print(f"  fallback-derived club_team_id values: {len(team_ids):,}")
    if team_names:
        print(f"  club teams found: {', '.join(team_names[:8])}{' ...' if len(team_names) > 8 else ''}")


def report_identity(scope: Path) -> None:
    identity = read_csv(scope / "player_identity_audit.csv")
    if identity.empty:
        print("- player_identity_audit.csv: missing or empty")
        return
    original_columns = set(identity.columns)
    normalized = ensure_club_ownership_columns(identity)
    club_count = 0
    if "is_club_player" in normalized:
        club_count = int(normalized["is_club_player"].astype(str).str.casefold().isin({"true", "1", "yes"}).sum())
    print(f"- player_identity_audit.csv rows: {len(identity):,}")
    print(f"  old columns: {column_flags(original_columns, ['is_fvcc_player'])}")
    print(f"  neutral columns: {column_flags(original_columns, ['is_club_player'])}")
    print(f"  fallback club player rows: {club_count:,}")


def column_flags(columns: set[str], names: list[str]) -> str:
    return ", ".join(f"{name}={'yes' if name in columns else 'no'}" for name in names)


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
