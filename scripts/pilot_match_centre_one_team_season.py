#!/usr/bin/env python3
"""Run a controlled one-team, one-season PlayCricket match-centre pilot.

This script fetches one team and one season only, using public PlayCricket
match-centre endpoints. It does not change the Streamlit app or the existing
aggregate stats pipeline. Raw responses are cached under a stable scope folder,
so reruns skip already cached files and only fill gaps.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.match_centre_fetcher import (  # noqa: E402
    PoliteMatchCentreFetcher,
    write_manifest,
)
from src.data.match_centre_parser import MatchCentrePayloads, parse_payloads  # noqa: E402


DEFAULT_SEASON_ID = "6169f605-4b96-4f21-87c5-0862f914624f"  # Winter 2025
DEFAULT_TEAM_ID = "b0d2ee4c-be8f-4a75-b138-0740a52970c6"  # FVCC Winter XI
RAW_ROOT = ROOT / "data" / "raw" / "match_centre_pilot"
PROCESSED_DIR = ROOT / "data" / "processed" / "match_centre_pilot"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and parse one FVCC match-centre pilot scope.")
    parser.add_argument("--season-id", default=DEFAULT_SEASON_ID, help="PlayCricket season ID. Defaults to Winter 2025.")
    parser.add_argument("--team-id", default=DEFAULT_TEAM_ID, help="PlayCricket team ID. Defaults to FVCC Winter XI.")
    parser.add_argument("--sleep-seconds", type=float, default=0.85, help="Delay between uncached public requests.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_dir = RAW_ROOT / f"season={args.season_id}__team={args.team_id}"
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    fetcher = PoliteMatchCentreFetcher(sleep_seconds=args.sleep_seconds)
    result = fetcher.fetch_one_team_season(args.season_id, args.team_id, raw_dir)
    write_manifest(result, raw_dir / "manifest.json")

    payloads = load_pilot_payloads(raw_dir)
    frames = parse_payloads(payloads)
    for name, frame in frames.items():
        frame.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)

    summary = build_pilot_summary(args.season_id, args.team_id, result, frames, raw_dir)
    summary.to_csv(PROCESSED_DIR / "pilot_summary.csv", index=False)

    print("Pilot match-centre fetch complete")
    print(f"- raw cache: {raw_dir}")
    print(f"- total matches found: {len(result.team_matches):,}")
    print(f"- completed matches: {len(result.completed_matches):,}")
    print(f"- scorecards parsed: {len(frames['all_matches']):,}")
    print(f"- ball events parsed: {len(frames['all_ball_by_ball']):,}")
    if not frames["validation_report"].empty:
        print(f"- validation: {frames['validation_report']['status'].value_counts().to_dict()}")
    return 0


def load_pilot_payloads(raw_dir: Path) -> list[MatchCentrePayloads]:
    payloads: list[MatchCentrePayloads] = []
    for scorecard_path in sorted(raw_dir.glob("match=*__scorecard.json")):
        match_id = scorecard_path.name.removeprefix("match=").removesuffix("__scorecard.json")
        scorecard_wrapper = read_json(scorecard_path)
        officials_path = raw_dir / f"match={match_id}__officials.json"
        balls_path = raw_dir / f"match={match_id}__balls.json"
        payloads.append(
            MatchCentrePayloads(
                manifest={"fetched_at": scorecard_wrapper.get("request", {}).get("fetched_at")},
                scorecard=scorecard_wrapper.get("payload", {}),
                balls=read_json(balls_path).get("payload", {}) if balls_path.exists() else {},
                officials=read_json(officials_path).get("payload", {}) if officials_path.exists() else {},
            )
        )
    return payloads


def build_pilot_summary(
    season_id: str,
    team_id: str,
    result: Any,
    frames: dict[str, pd.DataFrame],
    raw_dir: Path,
) -> pd.DataFrame:
    matches = frames["all_matches"]
    validation = frames["validation_report"]
    status_counts = validation["status"].value_counts().to_dict() if not validation.empty else {}
    matches_with_bbb = int(matches["is_ball_by_ball"].fillna(False).sum()) if not matches.empty else 0
    raw_size_mb = sum(path.stat().st_size for path in raw_dir.glob("*.json")) / (1024 * 1024)
    return pd.DataFrame(
        [
            {
                "season_id": season_id,
                "team_id": team_id,
                "total_matches_found": len(result.team_matches),
                "completed_matches": len(result.completed_matches),
                "scorecards_fetched": len(frames["all_matches"]),
                "matches_with_ball_by_ball": matches_with_bbb,
                "matches_without_ball_by_ball": max(len(frames["all_matches"]) - matches_with_bbb, 0),
                "total_batting_rows": len(frames["all_scorecard_batting"]),
                "total_bowling_rows": len(frames["all_scorecard_bowling"]),
                "total_fielding_rows": len(frames["all_scorecard_fielding"]),
                "total_ball_events": len(frames["all_ball_by_ball"]),
                "validation_pass_count": int(status_counts.get("pass", 0)),
                "validation_warning_count": int(status_counts.get("warning", 0)),
                "validation_error_count": int(status_counts.get("error", 0)),
                "raw_data_size_mb": round(raw_size_mb, 3),
            }
        ]
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())

