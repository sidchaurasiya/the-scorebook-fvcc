#!/usr/bin/env python3
"""Rebuild governed GRDCC fastest-innings prepared outputs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.club_refresh_utils import get_club_team_ids  # noqa: E402
from src.config.club_config import (  # noqa: E402
    get_club_name,
    get_hall_of_fame_dir,
    get_mapping_path,
    get_processed_match_centre_dir,
    get_processed_path,
)
from src.data.fastest_innings import build_governed_fastest_innings, write_fastest_innings_outputs  # noqa: E402


CLUB_ID = "georges-river-district"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Resolve inputs without writing outputs.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Write the prepared output and validation folder to a staging directory.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = get_processed_match_centre_dir(club_id=CLUB_ID)
    if args.output_dir is None:
        output = get_hall_of_fame_dir(club_id=CLUB_ID) / "fastest_batting_milestones.csv"
        validation = get_processed_path("validation", club_id=CLUB_ID)
    else:
        output_dir = args.output_dir.resolve()
        output = output_dir / "fastest_batting_milestones.csv"
        validation = output_dir / "validation"
    print(f"GRDCC fastest innings source: {source} [{'exists' if source.exists() else 'missing'}]")
    print(f"Prepared output: {output}")
    if args.dry_run:
        return 0
    try:
        result = build_governed_fastest_innings(
            club_id=CLUB_ID,
            processed_root=source,
            players_path=get_processed_path("players.csv", club_id=CLUB_ID),
            aliases_path=get_mapping_path("player_aliases.csv", club_id=CLUB_ID),
            club_team_ids=get_club_team_ids(CLUB_ID),
            club_name_token=get_club_name(CLUB_ID),
        )
    except FileNotFoundError as exc:
        print(f"Rebuild blocked: {exc}")
        return 2
    write_fastest_innings_outputs(
        result,
        output=output,
        validation_dir=validation,
        prefix="grdcc",
    )
    governance = result.governance
    print(
        f"published={len(governance.published)} review={len(governance.review)} "
        f"rejected={len(governance.rejected)} scopes={len(result.scopes)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
