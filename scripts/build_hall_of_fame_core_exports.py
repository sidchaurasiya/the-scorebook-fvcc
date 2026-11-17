#!/usr/bin/env python3
"""Build deploy-safe Hall of Fame core aggregates from local processed data."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.club_refresh_utils import add_club_args, print_club_header, print_outputs, resolve_club_id  # noqa: E402
from src.config.club_config import get_hall_of_fame_dir  # noqa: E402
from src.data.hall_of_fame_prepared import FRAME_FILENAMES, GREATEST_SEASONS_FILENAME, MANIFEST_FILENAME  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deploy-safe Hall of Fame core aggregates.")
    add_club_args(parser)
    return parser.parse_args(argv)



def prepare_core_export_frames(club_id: str, historical: dict[str, object], layout_module) -> dict[str, object]:
    frames = {
        "batting": historical["batting"],
        "bowling": historical["bowling"],
        "fielding": historical["fielding"],
        "all_time": historical["all_time"],
    }
    if club_id != "georges-river-district":
        return frames

    from src.data.grdcc_career_refresh import (
        apply_reviewed_playcricket_career_exceptions,
        mask_unapproved_playcricket_exception_metrics,
    )

    for category in ("batting", "bowling", "fielding"):
        frames[category] = mask_unapproved_playcricket_exception_metrics(frames[category], club_id)
    all_time = layout_module.apply_featured_record_overrides(
        frames["all_time"].copy(), club_id=club_id, add_missing_players=True
    )
    all_time = layout_module.add_club_not_outs_for_display(all_time, frames["batting"], club_id)
    frames["all_time"] = apply_reviewed_playcricket_career_exceptions(all_time, club_id)
    return frames


def sanitize_core_export_frames(club_id: str, frames: dict[str, object]) -> dict[str, object]:
    """Apply the public identity projection to every prepared career frame."""
    from src.data.public_generic_identity_privacy import sanitize_public_identity_frame

    output: dict[str, object] = {}
    for key, frame in frames.items():
        if not hasattr(frame, "copy"):
            output[key] = frame
            continue
        safe, _ = sanitize_public_identity_frame(
            frame.copy(),
            club_id=club_id,
            relative_path=f"hall_of_fame/prepared_career_{key}.csv",
        )
        output[key] = safe
    return output

def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = resolve_club_id(args.club)
    os.environ["CLUB_ID"] = club_id
    os.environ["SCOREBOOK_IGNORE_PREPARED_HOF"] = "1"

    from src.data.hall_of_fame_prepared import write_prepared_hall_of_fame_core
    from src.data.playcricket_ingestion import metadata_mtime
    from src.ui import layout
    from src.utils.player_identity import player_aliases_mtime

    output_dir = ROOT / "data" / "processed" / "hall_of_fame" if args.legacy_output else get_hall_of_fame_dir(club_id=club_id)
    output_paths = [output_dir / filename for filename in (*FRAME_FILENAMES.values(), GREATEST_SEASONS_FILENAME, MANIFEST_FILENAME)]
    print_club_header("Hall of Fame deploy-safe core export builder", club_id)
    print_outputs("Outputs", output_paths)
    if args.dry_run:
        print("Dry run complete. No files were written.")
        return 0

    historical = layout.load_hall_of_fame_data(
        metadata_mtime(),
        player_aliases_mtime(club_id=club_id),
        layout.HALL_OF_FAME_DATA_VERSION,
        club_id=club_id,
    )
    if historical is None:
        print("No historical data available; Hall of Fame core exports were not built.")
        return 1
    best_batting = layout.best_batting_season(historical["batting_raw"])
    best_bowling = layout.best_bowling_season(historical["bowling_raw"])
    written = write_prepared_hall_of_fame_core(
        club_id,
        layout.HALL_OF_FAME_DATA_VERSION,
        sanitize_core_export_frames(
            club_id,
            prepare_core_export_frames(club_id, historical, layout),
        ),
        best_batting,
        best_bowling,
        output_dir=output_dir,
    )
    for path in written:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
