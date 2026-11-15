#!/usr/bin/env python3
"""Build generic GRDCC scorecard events from a frozen private source bundle.

The lineage register is restricted input. Its participant fingerprint is used
only to select ambiguous source rows for masking; it is never written to an
output file or used as an identity, career, or cross-match key.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.grdcc_anonymous_scorecard_contributions import (
    build_anonymous_fastest_milestones,
    build_anonymous_scorecard_contributions,
    participant_fingerprints_from_lineage,
)

SOURCE_FILES = (
    "all_matches.csv",
    "all_match_innings.csv",
    "all_scorecard_batting.csv",
    "all_scorecard_bowling.csv",
    "all_scorecard_fielding.csv",
    "all_batting_milestones.csv",
    "all_ball_by_ball.csv",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-root",
        type=Path,
        required=True,
        help="Frozen all_available GRDCC match-centre source directory.",
    )
    parser.add_argument(
        "--restricted-lineage",
        type=Path,
        required=True,
        help="Restricted GRDCC identity-attribution lineage CSV.",
    )
    parser.add_argument(
        "--teams",
        type=Path,
        default=ROOT / "clubs/georges-river-district/data/processed/teams.csv",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "clubs/georges-river-district/data/processed/season_overview",
    )
    parser.add_argument(
        "--fastest-output",
        type=Path,
        default=ROOT / "clubs/georges-river-district/data/processed/hall_of_fame/anonymous_fastest_milestones.csv",
    )
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path, dtype=str).fillna("")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve()
    restricted_lineage = args.restricted_lineage.resolve()
    source_paths = {name: source_root / name for name in SOURCE_FILES}
    missing = [str(path) for path in source_paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Frozen source bundle is incomplete: {missing}")

    fingerprints = participant_fingerprints_from_lineage(read_csv(restricted_lineage))
    matches = read_csv(source_paths["all_matches.csv"])
    innings = read_csv(source_paths["all_match_innings.csv"])
    batting = read_csv(source_paths["all_scorecard_batting.csv"])
    bowling = read_csv(source_paths["all_scorecard_bowling.csv"])
    fielding = read_csv(source_paths["all_scorecard_fielding.csv"])
    milestones = read_csv(source_paths["all_batting_milestones.csv"])
    ball_events = read_csv(source_paths["all_ball_by_ball.csv"])
    teams = read_csv(args.teams.resolve())

    scorecard_events = build_anonymous_scorecard_contributions(
        matches=matches,
        innings=innings,
        batting=batting,
        bowling=bowling,
        fielding=fielding,
        teams=teams,
        ambiguous_participant_fingerprints=fingerprints,
        ball_events=ball_events,
    )
    fastest_events = build_anonymous_fastest_milestones(
        milestones=milestones,
        batting=batting,
        ball_events=ball_events,
        matches=matches,
        teams=teams,
        ambiguous_participant_fingerprints=fingerprints,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.fastest_output.parent.mkdir(parents=True, exist_ok=True)
    scorecard_path = args.output_dir / "anonymous_scorecard_contributions.csv"
    scorecard_events.to_csv(scorecard_path, index=False)
    fastest_events.to_csv(args.fastest_output, index=False)

    counts = scorecard_events["discipline"].value_counts().to_dict() if not scorecard_events.empty else {}
    print(f"Anonymous scorecard event rows: {len(scorecard_events)}; disciplines: {counts}")
    print(f"Anonymous verified fastest events: {len(fastest_events)}")
    print(f"Scorecard output SHA-256: {sha256(scorecard_path)}")
    print(f"Fastest output SHA-256: {sha256(args.fastest_output)}")
    print("No participant IDs, player names, match IDs, innings IDs, or scorecard URLs were written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
