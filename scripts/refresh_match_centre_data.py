#!/usr/bin/env python3
"""Refresh public PlayCricket match-centre data for an explicit scoped set.

This production pipeline is intentionally separate from the existing aggregate
stats refresh and from the Streamlit UI. It only fetches the season/team IDs
passed on the command line, uses public PlayCricket match-centre endpoints,
reuses cached raw files unless --force-refresh is set, and only requests
ball-by-ball data when a scorecard advertises isBallByBall.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.match_centre_fetcher import PoliteMatchCentreFetcher, RequestRecord  # noqa: E402
from src.data.match_centre_ownership import ensure_club_ownership_columns  # noqa: E402
from src.data.match_centre_parser import MatchCentrePayloads, parse_payloads  # noqa: E402
from scripts.club_refresh_utils import (  # noqa: E402
    add_club_args,
    get_playcricket_club_id,
    print_club_header,
    print_outputs,
    print_paths,
    resolve_club_id,
)
from src.config.club_config import get_mapping_path, get_processed_match_centre_dir, get_processed_path, get_raw_match_centre_dir  # noqa: E402


RAW_ROOT = ROOT / "data" / "raw" / "match_centre"
PROCESSED_ROOT = ROOT / "data" / "processed" / "match_centre"
TEAMS_PATH = ROOT / "data" / "processed" / "teams.csv"
PLAYERS_PATH = ROOT / "data" / "processed" / "players.csv"
ALIASES_PATH = ROOT / "data" / "player_aliases.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh scoped public PlayCricket match-centre data.")
    add_club_args(parser, legacy_output=False)
    parser.add_argument("--season-id", default=None, help="PlayCricket season ID.")
    parser.add_argument("--team-id", action="append", default=None, dest="team_ids", help="Team ID. Repeat for a controlled multi-team scope.")
    parser.add_argument("--output-scope-name", default=None, help="Folder-safe output scope name, e.g. summer_2025_26_3rd_xi.")
    parser.add_argument("--force-refresh", action="store_true", help="Refetch files even when cached raw files already exist.")
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="Delay between uncached public requests.")
    parser.add_argument("--max-matches", type=int, default=None, help="Optional cap on unique completed matches for testing.")
    args = parser.parse_args()
    if not args.dry_run:
        missing = []
        if not args.season_id:
            missing.append("--season-id")
        if not args.team_ids:
            missing.append("--team-id")
        if not args.output_scope_name:
            missing.append("--output-scope-name")
        if missing:
            parser.error(f"the following arguments are required unless --dry-run is used: {', '.join(missing)}")
    return args


def main() -> int:
    args = parse_args()
    club_id = resolve_club_id(args.club)
    playcricket_club_id = get_playcricket_club_id(club_id)
    raw_root = get_raw_match_centre_dir(club_id=club_id)
    processed_root = get_processed_match_centre_dir(club_id=club_id)
    teams_path = get_processed_path("teams.csv", club_id=club_id)
    players_path = get_processed_path("players.csv", club_id=club_id)
    aliases_path = get_mapping_path("player_aliases.csv", club_id=club_id)
    output_scope_name = args.output_scope_name or "<output-scope-name>"
    raw_dir = raw_root / output_scope_name
    processed_dir = processed_root / output_scope_name

    print_club_header("Scoped match-centre refresh", club_id)
    print(f"- PlayCricket club ID: {playcricket_club_id}")
    print(f"- mode: {'dry run' if args.dry_run else 'refresh scoped match-centre data'}")
    print(f"- external fetch: {'would fetch uncached match-centre endpoints' if not args.dry_run else 'no'}")
    print_paths("Inputs", [teams_path, players_path, aliases_path])
    print_outputs("Raw/generated outputs", [raw_dir, processed_dir])
    print("- raw/generated match-centre outputs remain legacy ignored paths in Phase 6")
    print(f"- season id: {args.season_id or '<required for real refresh>'}")
    print(f"- team ids: {', '.join(unique_ordered(args.team_ids or [])) if args.team_ids else '<required for real refresh>'}")
    print(f"- max matches: {args.max_matches if args.max_matches is not None else 'none'}")
    print()
    if args.dry_run:
        print("Dry run complete. No network requests were made and no files were written.")
        return 0

    team_ids = unique_ordered(args.team_ids)
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    team_metadata = load_team_metadata(args.season_id, teams_path=teams_path)
    fetcher = PoliteMatchCentreFetcher(sleep_seconds=args.sleep_seconds)
    team_match_rows, request_records = fetch_team_match_lists(fetcher, raw_dir, args.season_id, team_ids, args.force_refresh)
    unique_matches, source_team_map = unique_completed_matches(team_match_rows)
    if args.max_matches is not None:
        unique_matches = unique_matches[: args.max_matches]

    scorecard_paths: list[Path] = []
    officials_paths: list[Path] = []
    balls_paths: list[Path] = []
    for match in unique_matches:
        match_id = str(match.get("id"))
        scorecard_path = raw_dir / f"match={match_id}__scorecard.json"
        scorecard_payload, record = fetcher.get_json(
            f"/scores/matches/{match_id}",
            {"responseModifier": "includeScorecard", "jsconfig": "eccn:true"},
            scorecard_path,
            name="match_scorecard",
            match_id=match_id,
            force_refresh=args.force_refresh,
        )
        request_records.append(record)
        scorecard_paths.append(scorecard_path)

        officials_path = raw_dir / f"match={match_id}__officials.json"
        _, record = fetcher.get_json(
            f"/scores/matches/{match_id}/officials",
            {"jsconfig": "eccn:true"},
            officials_path,
            name="match_officials",
            match_id=match_id,
            force_refresh=args.force_refresh,
        )
        request_records.append(record)
        officials_paths.append(officials_path)

        if isinstance(scorecard_payload, dict) and scorecard_payload.get("isBallByBall"):
            balls_path = raw_dir / f"match={match_id}__balls.json"
            _, record = fetcher.get_json(
                f"/scores/matches/{match_id}/balls",
                {"jsconfig": "eccn:true"},
                balls_path,
                name="match_balls",
                match_id=match_id,
                force_refresh=args.force_refresh,
            )
            request_records.append(record)
            balls_paths.append(balls_path)

    write_refresh_manifest(
        raw_dir / "manifest.json",
        args.output_scope_name,
        args.season_id,
        team_ids,
        team_match_rows,
        unique_matches,
        request_records,
    )

    payloads = load_match_payloads(raw_dir, scorecard_paths)
    frames = parse_payloads(payloads)
    add_source_team_ids(frames["all_matches"], source_team_map)
    for name, frame in frames.items():
        frame.to_csv(processed_dir / f"{name}.csv", index=False)

    warnings = build_validation_warnings_detail(frames)
    warnings.to_csv(processed_dir / "validation_warnings_detail.csv", index=False)
    identity = build_player_identity_audit(frames, team_metadata, set(team_ids), players_path=players_path, aliases_path=aliases_path)
    identity.to_csv(processed_dir / "player_identity_audit.csv", index=False)
    summary = build_refresh_summary(
        output_scope_name=args.output_scope_name,
        season_id=args.season_id,
        team_ids=team_ids,
        team_match_rows=team_match_rows,
        unique_matches=unique_matches,
        request_records=request_records,
        frames=frames,
        identity=identity,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
    )
    summary.to_csv(processed_dir / "refresh_summary.csv", index=False)

    print("Match-centre refresh complete")
    print(f"- scope: {args.output_scope_name}")
    print(f"- team match rows: {len(team_match_rows):,}")
    print(f"- unique completed matches: {len(unique_matches):,}")
    print(f"- scorecards parsed: {len(frames['all_matches']):,}")
    print(f"- ball events parsed: {len(frames['all_ball_by_ball']):,}")
    if not frames["validation_report"].empty:
        print(f"- validation: {frames['validation_report']['status'].value_counts().to_dict()}")
    return 0


def fetch_team_match_lists(
    fetcher: PoliteMatchCentreFetcher,
    raw_dir: Path,
    season_id: str,
    team_ids: list[str],
    force_refresh: bool,
) -> tuple[list[dict[str, Any]], list[RequestRecord]]:
    rows: list[dict[str, Any]] = []
    records: list[RequestRecord] = []
    for team_id in team_ids:
        path = raw_dir / f"team_matches__season={season_id}__team={team_id}.json"
        payload, record = fetcher.get_json(
            f"/scores/teams/{team_id}/matches",
            {"seasonId": season_id, "jsconfig": "eccn:true"},
            path,
            name="team_match_list",
            force_refresh=force_refresh,
        )
        records.append(record)
        for match in payload.get("matches", []) if isinstance(payload, dict) else []:
            rows.append({**match, "source_team_id": team_id})
    return rows, records


def unique_completed_matches(team_match_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    matches: dict[str, dict[str, Any]] = {}
    source_team_map: dict[str, list[str]] = {}
    for row in team_match_rows:
        match_id = row.get("id")
        if not match_id or not is_completed_match(row):
            continue
        match_id = str(match_id)
        matches.setdefault(match_id, row)
        source_team_map.setdefault(match_id, [])
        source_team_id = str(row.get("source_team_id", ""))
        if source_team_id and source_team_id not in source_team_map[match_id]:
            source_team_map[match_id].append(source_team_id)
    return list(matches.values()), source_team_map


def load_match_payloads(raw_dir: Path, scorecard_paths: list[Path]) -> list[MatchCentrePayloads]:
    payloads = []
    for scorecard_path in sorted(set(scorecard_paths)):
        match_id = scorecard_path.name.removeprefix("match=").removesuffix("__scorecard.json")
        scorecard = read_json(scorecard_path)
        officials_path = raw_dir / f"match={match_id}__officials.json"
        balls_path = raw_dir / f"match={match_id}__balls.json"
        payloads.append(
            MatchCentrePayloads(
                manifest={"fetched_at": scorecard.get("request", {}).get("fetched_at")},
                scorecard=scorecard.get("payload", {}),
                balls=read_json(balls_path).get("payload", {}) if balls_path.exists() else {},
                officials=read_json(officials_path).get("payload", {}) if officials_path.exists() else {},
            )
        )
    return payloads


def add_source_team_ids(matches: pd.DataFrame, source_team_map: dict[str, list[str]]) -> None:
    if matches.empty:
        matches["source_team_ids"] = []
        return
    matches["source_team_ids"] = matches["match_id"].astype(str).map(
        lambda match_id: " | ".join(source_team_map.get(match_id, []))
    )


def build_refresh_summary(
    *,
    output_scope_name: str,
    season_id: str,
    team_ids: list[str],
    team_match_rows: list[dict[str, Any]],
    unique_matches: list[dict[str, Any]],
    request_records: list[RequestRecord],
    frames: dict[str, pd.DataFrame],
    identity: pd.DataFrame,
    raw_dir: Path,
    processed_dir: Path,
) -> pd.DataFrame:
    matches = frames["all_matches"]
    validation = frames["validation_report"]
    status_counts = validation["status"].value_counts().to_dict() if not validation.empty else {}
    identity = ensure_club_ownership_columns(identity)
    club_identity = identity[identity["is_club_player"] == True] if not identity.empty else pd.DataFrame()  # noqa: E712
    return pd.DataFrame(
        [
            {
                "output_scope_name": output_scope_name,
                "season_id": season_id,
                "team_ids": " | ".join(team_ids),
                "total_team_match_rows": len(team_match_rows),
                "unique_matches_found": len({str(row.get("id")) for row in team_match_rows if row.get("id")}),
                "completed_matches": len(unique_matches),
                "scorecards_fetched": len(frames["all_matches"]),
                "matches_with_ball_by_ball": int(matches["is_ball_by_ball"].map(bool).sum()) if not matches.empty else 0,
                "matches_without_ball_by_ball": int((~matches["is_ball_by_ball"].map(bool)).sum()) if not matches.empty else 0,
                "officials_files_fetched": sum(1 for record in request_records if record.name == "match_officials"),
                "total_batting_rows": len(frames["all_scorecard_batting"]),
                "total_bowling_rows": len(frames["all_scorecard_bowling"]),
                "total_fielding_rows": len(frames["all_scorecard_fielding"]),
                "total_fall_of_wickets_rows": len(frames["all_fall_of_wickets"]),
                "total_ball_events": len(frames["all_ball_by_ball"]),
                "validation_pass_count": int(status_counts.get("pass", 0)),
                "validation_warning_count": int(status_counts.get("warning", 0)),
                "validation_error_count": int(status_counts.get("error", 0)),
                "club_player_rows": len(club_identity),
                "club_exact_player_matches": count_identity(club_identity, "exact_match"),
                "club_likely_player_matches": count_identity(club_identity, "likely_match"),
                "club_no_player_matches": count_identity(club_identity, "no_match"),
                "fvcc_player_rows": len(club_identity),
                "fvcc_exact_player_matches": count_identity(club_identity, "exact_match"),
                "fvcc_likely_player_matches": count_identity(club_identity, "likely_match"),
                "fvcc_no_player_matches": count_identity(club_identity, "no_match"),
                "raw_data_size_mb": round(folder_size_mb(raw_dir), 3),
                "processed_data_size_mb": round(folder_size_mb(processed_dir), 3),
                "refreshed_at": now_iso(),
            }
        ]
    )


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


def build_player_identity_audit(
    frames: dict[str, pd.DataFrame],
    team_metadata: dict[str, dict[str, str]],
    club_team_ids: set[str],
    *,
    players_path: Path = PLAYERS_PATH,
    aliases_path: Path = ALIASES_PATH,
) -> pd.DataFrame:
    existing = load_existing_player_identity(players_path=players_path, aliases_path=aliases_path)
    team_lookup = build_team_lookup(frames["all_matches"], team_metadata)
    participants: dict[tuple[str, str], dict[str, Any]] = {}
    add_participants(participants, frames["all_scorecard_batting"], "batting")
    add_participants(participants, frames["all_scorecard_bowling"], "bowling")
    add_participants(participants, frames["all_scorecard_fielding"], "fielding")
    add_ball_participants(participants, frames["all_ball_by_ball"])
    rows = []
    for (participant_id, team_id), item in sorted(participants.items(), key=lambda entry: (entry[1].get("player_name", ""), entry[0])):
        identity = match_existing_identity(participant_id, item.get("player_name"), item.get("player_short_name"), existing)
        is_club_player = team_id in club_team_ids
        status = identity.get("status", "no_match")
        rows.append(
            {
                "source": "match_centre",
                "participant_id": participant_id,
                "player_name": item.get("player_name"),
                "player_short_name": item.get("player_short_name"),
                "team_id": team_id,
                "team_name": team_lookup.get(team_id, {}).get("team_name", item.get("team_name", "")),
                "is_club_player": is_club_player,
                "is_fvcc_player": is_club_player,
                "match_count": len(item["matches"]),
                "batting_rows": item["batting_rows"],
                "bowling_rows": item["bowling_rows"],
                "fielding_rows": item["fielding_rows"],
                "ball_event_rows": item["ball_event_rows"],
                "existing_player_match_status": status,
                "existing_player_id": identity.get("player_id", ""),
                "existing_canonical_name": identity.get("canonical_name", ""),
                "possible_reason_for_no_match": no_match_reason(is_club_player, participant_id, item, status),
            }
        )
    return pd.DataFrame(rows)


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
    for id_col, name_col, team_col in [
        ("striker_participant_id", "striker_short_name", "batting_team_id"),
        ("non_striker_participant_id", "non_striker_short_name", "batting_team_id"),
        ("bowler_participant_id", "bowler_short_name", "bowling_team_id"),
    ]:
        for _, row in frame.iterrows():
            participant_id = row.get(id_col)
            team_id = row.get(team_col)
            if pd.isna(participant_id) or pd.isna(team_id):
                continue
            item = participant_item(participants, str(participant_id), str(team_id), None, row.get(name_col))
            item["matches"].add(str(row.get("match_id")))
            item["ball_event_rows"] += 1


def participant_item(participants: dict[tuple[str, str], dict[str, Any]], participant_id: str, team_id: str, player_name: Any, short_name: Any) -> dict[str, Any]:
    key = (participant_id, team_id)
    if key not in participants:
        participants[key] = {
            "player_name": "" if pd.isna(player_name) else player_name,
            "player_short_name": "" if pd.isna(short_name) else short_name,
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
        if not participants[key]["player_short_name"] and not pd.isna(short_name):
            participants[key]["player_short_name"] = short_name
    return participants[key]


def load_existing_player_identity(
    *,
    players_path: Path = PLAYERS_PATH,
    aliases_path: Path = ALIASES_PATH,
) -> dict[str, Any]:
    players = pd.read_csv(players_path) if players_path.exists() else pd.DataFrame(columns=["player_id", "player_name"])
    aliases = pd.read_csv(aliases_path) if aliases_path.exists() else pd.DataFrame(columns=["raw_player_id", "canonical_player_id", "canonical_player_name", "raw_player_name"])
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


def no_match_reason(is_club_player: bool, participant_id: str, item: dict[str, Any], status: str) -> str:
    if status != "no_match":
        return ""
    if participant_id.startswith("00000000-0000-0000-0000"):
        return "masked_or_placeholder_participant_id"
    if str(item.get("player_name", "")).strip("* ") == "":
        return "masked_or_placeholder_name"
    if not is_club_player:
        return "opposition_player_not_expected_in_club_canonical_data"
    return "club_player_not_found_in_existing_players_or_aliases"


def write_refresh_manifest(
    path: Path,
    output_scope_name: str,
    season_id: str,
    team_ids: list[str],
    team_match_rows: list[dict[str, Any]],
    unique_matches: list[dict[str, Any]],
    request_records: list[RequestRecord],
) -> None:
    path.write_text(
        json.dumps(
            {
                "output_scope_name": output_scope_name,
                "season_id": season_id,
                "team_ids": team_ids,
                "generated_at": now_iso(),
                "total_team_match_rows": len(team_match_rows),
                "unique_matches_found": len({str(row.get("id")) for row in team_match_rows if row.get("id")}),
                "completed_matches": len(unique_matches),
                "requests": [record.as_dict() for record in request_records],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


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


def load_team_metadata(season_id: str, *, teams_path: Path = TEAMS_PATH) -> dict[str, dict[str, str]]:
    if not teams_path.exists():
        return {}
    teams = pd.read_csv(teams_path)
    teams = teams[teams["season_id"].astype(str) == str(season_id)]
    return {
        str(row["team_id"]): {
            "season": str(row.get("season", "")),
            "team_name": str(row.get("team_name", "")),
            "grade_name": str(row.get("grade_name", "")),
        }
        for _, row in teams.iterrows()
    }


def is_completed_match(match: dict[str, Any]) -> bool:
    return str(match.get("status", "")).upper() == "COMPLETED" or match.get("statusId") == 3


def unique_ordered(values: list[str]) -> list[str]:
    output = []
    for value in values:
        if value not in output:
            output.append(value)
    return output


def count_identity(frame: pd.DataFrame, status: str) -> int:
    if frame.empty:
        return 0
    return int((frame["existing_player_match_status"] == status).sum())


def folder_size_mb(path: Path) -> float:
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file()) / (1024 * 1024)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
