#!/usr/bin/env python3
"""Run a controlled one-season PlayCricket match-centre pilot.

This script fetches explicitly scoped team(s) in one season only, using public
PlayCricket match-centre endpoints. It does not change the Streamlit app or the
existing aggregate stats pipeline. Raw responses are cached under stable scope
folders, so reruns skip already cached files and only fill gaps.
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
TEAMS_PATH = ROOT / "data" / "processed" / "teams.csv"
PLAYERS_PATH = ROOT / "data" / "processed" / "players.csv"
ALIASES_PATH = ROOT / "data" / "player_aliases.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch and parse one FVCC match-centre pilot scope.")
    parser.add_argument("--season-id", default=DEFAULT_SEASON_ID, help="PlayCricket season ID. Defaults to Winter 2025.")
    parser.add_argument("--season-name", default=None, help="Human season name for summary output.")
    parser.add_argument(
        "--team-id",
        action="append",
        dest="team_ids",
        help="PlayCricket team ID. Pass more than once for a controlled multi-team pilot.",
    )
    parser.add_argument("--raw-root", default=str(RAW_ROOT), help="Raw cache root folder.")
    parser.add_argument("--processed-dir", default=str(PROCESSED_DIR), help="Processed output folder.")
    parser.add_argument("--sleep-seconds", type=float, default=0.85, help="Delay between uncached public requests.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    team_ids = args.team_ids or [DEFAULT_TEAM_ID]
    raw_root = resolve_path(args.raw_root)
    processed_dir = resolve_path(args.processed_dir)
    raw_root.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    team_metadata = load_team_metadata(args.season_id)

    fetcher = PoliteMatchCentreFetcher(sleep_seconds=args.sleep_seconds)
    results = []
    payloads = []
    for team_id in team_ids:
        raw_dir = raw_root / f"season={args.season_id}__team={team_id}"
        result = fetcher.fetch_one_team_season(args.season_id, team_id, raw_dir)
        write_manifest(result, raw_dir / "manifest.json")
        results.append(result)
        payloads.extend(load_pilot_payloads(raw_dir))

    frames = parse_payloads(payloads)
    for name, frame in frames.items():
        frame.to_csv(processed_dir / f"{name}.csv", index=False)

    summary = build_pilot_summary(args.season_id, args.season_name, results, frames, raw_root, team_metadata)
    summary.to_csv(processed_dir / "pilot_summary.csv", index=False)
    warnings = build_validation_warnings_detail(frames)
    warnings.to_csv(processed_dir / "validation_warnings_detail.csv", index=False)
    audit = build_player_identity_audit(frames, team_metadata)
    audit.to_csv(processed_dir / "player_identity_audit.csv", index=False)

    print("Pilot match-centre fetch complete")
    print(f"- raw cache: {raw_root}")
    print(f"- teams: {len(team_ids):,}")
    print(f"- total matches found: {sum(len(result.team_matches) for result in results):,}")
    print(f"- completed matches: {sum(len(result.completed_matches) for result in results):,}")
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
    season_name: str | None,
    results: list[Any],
    frames: dict[str, pd.DataFrame],
    raw_root: Path,
    team_metadata: dict[str, dict[str, str]],
) -> pd.DataFrame:
    rows = []
    validation = frames["validation_report"]
    raw_size_by_team = raw_sizes_by_team(raw_root)
    for result in results:
        team_id = result.team_id
        metadata = team_metadata.get(team_id, {})
        match_ids = {str(match.get("id")) for match in result.completed_matches if match.get("id")}
        team_matches = frames["all_matches"][frames["all_matches"]["match_id"].astype(str).isin(match_ids)]
        status_counts = validation[validation["match_id"].astype(str).isin(match_ids)]["status"].value_counts().to_dict() if not validation.empty else {}
        matches_with_bbb = int(team_matches["is_ball_by_ball"].map(bool).sum()) if not team_matches.empty else 0
        rows.append(
            {
                "season_id": season_id,
                "season_name": season_name or metadata.get("season", ""),
                "team_id": team_id,
                "team_name": metadata.get("team_name", ""),
                "grade_name": metadata.get("grade_name", ""),
                "total_matches_found": len(result.team_matches),
                "completed_matches": len(result.completed_matches),
                "scorecards_fetched": len(team_matches),
                "matches_with_ball_by_ball": matches_with_bbb,
                "matches_without_ball_by_ball": max(len(team_matches) - matches_with_bbb, 0),
                "matches_with_officials": count_team_rows(frames["all_match_officials"], match_ids, "match_id"),
                "total_batting_rows": count_team_rows(frames["all_scorecard_batting"], match_ids, "match_id"),
                "total_bowling_rows": count_team_rows(frames["all_scorecard_bowling"], match_ids, "match_id"),
                "total_fielding_rows": count_team_rows(frames["all_scorecard_fielding"], match_ids, "match_id"),
                "total_fall_of_wickets_rows": count_team_rows(frames["all_fall_of_wickets"], match_ids, "match_id"),
                "total_ball_events": count_team_rows(frames["all_ball_by_ball"], match_ids, "match_id"),
                "validation_pass_count": int(status_counts.get("pass", 0)),
                "validation_warning_count": int(status_counts.get("warning", 0)),
                "validation_error_count": int(status_counts.get("error", 0)),
                "raw_data_size_mb": round(raw_size_by_team.get(team_id, 0.0), 3),
            }
        )
    return pd.DataFrame(rows)


def build_validation_warnings_detail(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    validation = frames["validation_report"]
    columns = [
        "check_name",
        "severity",
        "match_id",
        "match_name",
        "innings_id",
        "innings_name",
        "player_id",
        "expected_value",
        "actual_value",
        "difference",
        "message",
    ]
    if validation.empty:
        return pd.DataFrame(columns=columns)
    matches = frames["all_matches"].set_index("match_id") if not frames["all_matches"].empty else pd.DataFrame()
    innings = frames["all_match_innings"].set_index("innings_id") if not frames["all_match_innings"].empty else pd.DataFrame()
    rows = []
    for _, warning in validation[validation["status"] != "pass"].iterrows():
        match_id = warning.get("match_id")
        innings_id = warning.get("innings_id")
        match_row = matches.loc[match_id] if not matches.empty and match_id in matches.index else {}
        innings_row = innings.loc[innings_id] if not innings.empty and innings_id in innings.index else {}
        rows.append(
            {
                "check_name": warning.get("check_name"),
                "severity": warning.get("severity"),
                "match_id": match_id,
                "match_name": match_name(match_row),
                "innings_id": innings_id,
                "innings_name": get_row_value(innings_row, "innings_name"),
                "player_id": warning.get("entity_id") if str(warning.get("entity_id", "")).startswith("raw_") else "",
                "expected_value": warning.get("expected_value"),
                "actual_value": warning.get("actual_value"),
                "difference": numeric_difference(warning.get("expected_value"), warning.get("actual_value")),
                "message": warning.get("detail"),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def build_player_identity_audit(frames: dict[str, pd.DataFrame], team_metadata: dict[str, dict[str, str]]) -> pd.DataFrame:
    existing = load_existing_player_identity()
    team_lookup = build_team_lookup(frames["all_matches"], team_metadata)
    participants: dict[tuple[str, str], dict[str, Any]] = {}
    add_participants(participants, frames["all_scorecard_batting"], "batting")
    add_participants(participants, frames["all_scorecard_bowling"], "bowling")
    add_participants(participants, frames["all_scorecard_fielding"], "fielding")
    add_ball_participants(participants, frames["all_ball_by_ball"])
    rows = []
    for (participant_id, team_id), item in sorted(participants.items(), key=lambda entry: (entry[1].get("player_name", ""), entry[0])):
        identity = match_existing_identity(participant_id, item.get("player_name"), item.get("player_short_name"), existing)
        metadata = team_lookup.get(team_id, {})
        rows.append(
            {
                "source": "match_centre",
                "participant_id": participant_id,
                "player_name": item.get("player_name"),
                "player_short_name": item.get("player_short_name"),
                "team_id": team_id,
                "team_name": metadata.get("team_name", item.get("team_name", "")),
                "match_count": len(item["matches"]),
                "batting_rows": item["batting_rows"],
                "bowling_rows": item["bowling_rows"],
                "fielding_rows": item["fielding_rows"],
                "ball_event_rows": item["ball_event_rows"],
                "matched_existing_player_id_if_available": identity.get("player_id", ""),
                "matched_canonical_name_if_available": identity.get("canonical_name", ""),
                "match_status": identity.get("status", "no_match"),
            }
        )
    return pd.DataFrame(rows)


def build_team_lookup(matches: pd.DataFrame, team_metadata: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    lookup = dict(team_metadata)
    if matches.empty:
        return lookup
    for _, match in matches.iterrows():
        for id_col, name_col in [("home_team_id", "home_team_name"), ("away_team_id", "away_team_name")]:
            team_id = match.get(id_col)
            if pd.isna(team_id):
                continue
            lookup.setdefault(str(team_id), {})["team_name"] = "" if pd.isna(match.get(name_col)) else str(match.get(name_col))
    return lookup


def add_participants(participants: dict[tuple[str, str], dict[str, Any]], frame: pd.DataFrame, role: str) -> None:
    if frame.empty:
        return
    for _, row in frame.iterrows():
        participant_id = row.get("participant_id")
        team_id = row.get("team_id")
        if pd.isna(participant_id) or pd.isna(team_id):
            continue
        item = participant_item(participants, str(participant_id), str(team_id), row.get("player_name"), row.get("player_short_name"))
        item["matches"].add(str(row.get("match_id")))
        item[f"{role}_rows"] += 1


def add_ball_participants(participants: dict[tuple[str, str], dict[str, Any]], frame: pd.DataFrame) -> None:
    if frame.empty:
        return
    roles = [
        ("striker_participant_id", "striker_short_name", "batting_team_id"),
        ("non_striker_participant_id", "non_striker_short_name", "batting_team_id"),
        ("bowler_participant_id", "bowler_short_name", "bowling_team_id"),
    ]
    for _, row in frame.iterrows():
        for id_col, name_col, team_col in roles:
            participant_id = row.get(id_col)
            team_id = row.get(team_col)
            if pd.isna(participant_id) or pd.isna(team_id):
                continue
            item = participant_item(participants, str(participant_id), str(team_id), None, row.get(name_col))
            item["matches"].add(str(row.get("match_id")))
            item["ball_event_rows"] += 1


def participant_item(
    participants: dict[tuple[str, str], dict[str, Any]],
    participant_id: str,
    team_id: str,
    player_name: Any,
    player_short_name: Any,
) -> dict[str, Any]:
    key = (participant_id, team_id)
    if key not in participants:
        participants[key] = {
            "player_name": "" if pd.isna(player_name) else player_name,
            "player_short_name": "" if pd.isna(player_short_name) else player_short_name,
            "team_name": "",
            "matches": set(),
            "batting_rows": 0,
            "bowling_rows": 0,
            "fielding_rows": 0,
            "ball_event_rows": 0,
        }
    else:
        if not participants[key]["player_name"] and not pd.isna(player_name):
            participants[key]["player_name"] = player_name
        if not participants[key]["player_short_name"] and not pd.isna(player_short_name):
            participants[key]["player_short_name"] = player_short_name
    return participants[key]


def load_existing_player_identity() -> dict[str, Any]:
    players = pd.read_csv(PLAYERS_PATH) if PLAYERS_PATH.exists() else pd.DataFrame(columns=["player_id", "player_name"])
    aliases = pd.read_csv(ALIASES_PATH) if ALIASES_PATH.exists() else pd.DataFrame(columns=["raw_player_id", "canonical_player_id", "canonical_player_name", "raw_player_name"])
    by_id = {}
    by_name: dict[str, list[dict[str, str]]] = {}
    for _, row in players.iterrows():
        item = {"player_id": row.get("player_id", ""), "canonical_name": row.get("player_name", ""), "status": "exact_match"}
        by_id[str(row.get("player_id"))] = item
        by_name.setdefault(normalize_name(row.get("player_name")), []).append(item)
    for _, row in aliases.iterrows():
        item = {"player_id": row.get("canonical_player_id", ""), "canonical_name": row.get("canonical_player_name", ""), "status": "exact_match"}
        by_id[str(row.get("raw_player_id"))] = item
        by_name.setdefault(normalize_name(row.get("raw_player_name")), []).append(item)
        by_name.setdefault(normalize_name(row.get("canonical_player_name")), []).append(item)
    return {"by_id": by_id, "by_name": by_name}


def match_existing_identity(participant_id: str, player_name: Any, player_short_name: Any, existing: dict[str, Any]) -> dict[str, str]:
    if participant_id in existing["by_id"]:
        return existing["by_id"][participant_id]
    candidates = existing["by_name"].get(normalize_name(player_name), [])
    if len(candidates) == 1:
        return {**candidates[0], "status": "likely_match"}
    if len(candidates) > 1:
        return {**candidates[0], "status": "duplicate_candidate"}
    short_candidates = existing["by_name"].get(normalize_name(player_short_name), [])
    if len(short_candidates) == 1:
        return {**short_candidates[0], "status": "likely_match"}
    if len(short_candidates) > 1:
        return {**short_candidates[0], "status": "duplicate_candidate"}
    return {"player_id": "", "canonical_name": "", "status": "no_match"}


def load_team_metadata(season_id: str) -> dict[str, dict[str, str]]:
    if not TEAMS_PATH.exists():
        return {}
    teams = pd.read_csv(TEAMS_PATH)
    teams = teams[teams["season_id"].astype(str) == str(season_id)]
    return {
        str(row["team_id"]): {
            "season": str(row.get("season", "")),
            "team_name": str(row.get("team_name", "")),
            "grade_name": str(row.get("grade_name", "")),
        }
        for _, row in teams.iterrows()
    }


def count_team_rows(frame: pd.DataFrame, match_ids: set[str], match_col: str) -> int:
    if frame.empty:
        return 0
    return int(frame[frame[match_col].astype(str).isin(match_ids)].shape[0])


def raw_sizes_by_team(raw_root: Path) -> dict[str, float]:
    sizes = {}
    for path in raw_root.glob("season=*__team=*"):
        team_id = path.name.split("__team=", 1)[-1]
        sizes[team_id] = sum(file.stat().st_size for file in path.glob("*.json")) / (1024 * 1024)
    return sizes


def match_name(match_row: Any) -> str:
    home = get_row_value(match_row, "home_team_name")
    away = get_row_value(match_row, "away_team_name")
    return f"{home} vs {away}" if home or away else ""


def get_row_value(row: Any, key: str) -> Any:
    if isinstance(row, pd.Series):
        return row.get(key, "")
    if isinstance(row, dict):
        return row.get(key, "")
    return ""


def numeric_difference(left: Any, right: Any) -> Any:
    try:
        return float(left) - float(right)
    except (TypeError, ValueError):
        return ""


def normalize_name(value: Any) -> str:
    if pd.isna(value):
        return ""
    return " ".join(str(value).casefold().replace(",", " ").split())


def resolve_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
