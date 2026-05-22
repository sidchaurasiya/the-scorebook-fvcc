from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.club_config import (  # noqa: E402
    get_active_club_id,
    get_club_name,
    get_processed_path,
    load_club_config,
    normalize_club_id,
)


def add_club_args(parser: argparse.ArgumentParser, *, legacy_output: bool = True) -> None:
    parser.add_argument(
        "--club",
        default=None,
        help="Club config id. Defaults to CLUB_ID or fvcc.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print resolved inputs and outputs without writing files.",
    )
    if legacy_output:
        parser.add_argument(
            "--legacy-output",
            action="store_true",
            help="Write deploy-safe outputs to legacy data/processed folders instead of the active club folder.",
        )


def resolve_club_id(club_id: str | None) -> str:
    active_club_id = normalize_club_id(club_id) if club_id else get_active_club_id()
    load_club_config(active_club_id)
    return active_club_id


def get_playcricket_club_id(club_id: str) -> str:
    config = load_club_config(club_id)
    playcricket_club_id = str(config.get("club", {}).get("playcricket_club_id") or "").strip()
    if not playcricket_club_id:
        raise SystemExit(f"Club '{club_id}' is missing club.playcricket_club_id in clubs/{club_id}/club_config.yaml.")
    return playcricket_club_id


def get_club_team_ids(club_id: str | None) -> set[str]:
    teams_path = get_processed_path("teams.csv", club_id=club_id)
    if not teams_path.exists():
        return set()
    with teams_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return {
            str(row.get("team_id") or "").strip()
            for row in reader
            if str(row.get("team_id") or "").strip()
        }


def print_club_header(title: str, club_id: str) -> None:
    print(title)
    print(f"- active club: {club_id} ({get_club_name(club_id)})")


def print_paths(title: str, paths: list[Path]) -> None:
    print(title)
    if not paths:
        print("- none")
        return
    for path in paths:
        status = "exists" if path.exists() else "missing"
        print(f"- {relative_path(path)} [{status}]")


def print_outputs(title: str, paths: list[Path]) -> None:
    print(title)
    for path in paths:
        print(f"- {relative_path(path)}")


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)
