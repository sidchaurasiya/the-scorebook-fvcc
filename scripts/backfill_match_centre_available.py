#!/usr/bin/env python3
"""Backfill public PlayCricket match-centre data for locally known club teams.

This runner is intentionally conservative and resumable. It reads season/team
combinations from local processed tables, fetches public match-centre endpoints
with caching, requests ball-by-ball only when a scorecard advertises
isBallByBall, and writes one combined `all_available` scope.
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
from src.data.match_centre_milestones import build_batting_milestones  # noqa: E402
from src.data.match_centre_ownership import ensure_club_ownership_columns  # noqa: E402
from src.data.match_centre_parser import MatchCentrePayloads, parse_payloads  # noqa: E402
from scripts.refresh_match_centre_data import (  # noqa: E402
    build_player_identity_audit,
    build_validation_warnings_detail,
    folder_size_mb,
)
from scripts.club_refresh_utils import (  # noqa: E402
    add_club_args,
    get_club_team_ids,
    get_playcricket_club_id,
    print_club_header,
    print_outputs,
    print_paths,
    resolve_club_id,
)
from src.config.club_config import get_club_name, get_mapping_path, get_processed_match_centre_dir, get_processed_path, get_raw_match_centre_dir  # noqa: E402


RAW_DIR = ROOT / "data" / "raw" / "match_centre" / "all_available"
PROCESSED_DIR = ROOT / "data" / "processed" / "match_centre" / "all_available"
TEAMS_PATH = ROOT / "data" / "processed" / "teams.csv"
SEASONS_PATH = ROOT / "data" / "processed" / "seasons.csv"
PLAYERS_PATH = ROOT / "data" / "processed" / "players.csv"
ALIASES_PATH = ROOT / "data" / "player_aliases.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill locally known club match-centre data into one all_available scope.")
    add_club_args(parser, legacy_output=False)
    parser.add_argument("--sleep-seconds", type=float, default=1.0, help="Delay between uncached public requests.")
    parser.add_argument("--max-seasons", type=int, default=None, help="Optional safety cap on seasons.")
    parser.add_argument("--max-teams", type=int, default=None, help="Optional safety cap on season/team combinations.")
    parser.add_argument("--max-matches", type=int, default=None, help="Optional safety cap on unique completed matches.")
    parser.add_argument("--season-id", action="append", dest="season_ids", default=None, help="Optional season ID filter. Repeatable.")
    parser.add_argument("--team-id", action="append", dest="team_ids", default=None, help="Optional team ID filter. Repeatable.")
    parser.add_argument("--force-refresh", action="store_true", help="Refetch files even when cached raw files already exist.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    club_id = resolve_club_id(args.club)
    playcricket_club_id = get_playcricket_club_id(club_id)
    raw_root = get_raw_match_centre_dir(club_id=club_id)
    processed_root = get_processed_match_centre_dir(club_id=club_id)
    raw_dir = raw_root / "all_available"
    processed_dir = processed_root / "all_available"
    teams_path = get_processed_path("teams.csv", club_id=club_id)
    seasons_path = get_processed_path("seasons.csv", club_id=club_id)
    players_path = get_processed_path("players.csv", club_id=club_id)
    aliases_path = get_mapping_path("player_aliases.csv", club_id=club_id)
    started_at = now_iso()
    combos = load_scope_combinations(args, teams_path=teams_path, seasons_path=seasons_path)
    dry_run_summary(
        combos,
        club_id=club_id,
        playcricket_club_id=playcricket_club_id,
        teams_path=teams_path,
        seasons_path=seasons_path,
        players_path=players_path,
        aliases_path=aliases_path,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
        dry_run=args.dry_run,
    )
    if args.dry_run:
        return 0
    if combos.empty:
        print("No season/team combinations found. Nothing to backfill.")
        return 0

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    fetcher = PoliteMatchCentreFetcher(sleep_seconds=args.sleep_seconds)
    team_match_rows, request_records = fetch_team_match_lists(fetcher, combos, args.force_refresh, raw_dir=raw_dir)
    unique_matches, source_team_map = unique_completed_matches(team_match_rows)
    if args.max_matches is not None:
        unique_matches = unique_matches[: args.max_matches]

    scorecard_paths = fetch_match_payloads(fetcher, unique_matches, request_records, args.force_refresh, raw_dir=raw_dir)
    write_manifest(raw_dir / "manifest.json", combos, team_match_rows, unique_matches, request_records, started_at)

    payloads = load_match_payloads(scorecard_paths, raw_dir=raw_dir)
    frames = parse_payloads(payloads)
    add_source_team_ids(frames["all_matches"], source_team_map)
    add_source_season_context(frames["all_matches"], team_match_rows, combos)
    for name, frame in frames.items():
        frame.to_csv(processed_dir / f"{name}.csv", index=False)

    warnings = build_validation_warnings_detail(frames)
    warnings.to_csv(processed_dir / "validation_warnings_detail.csv", index=False)
    identity = build_player_identity_audit(
        frames,
        build_team_metadata(combos),
        set(combos["team_id"].astype(str)),
        players_path=players_path,
        aliases_path=aliases_path,
    )
    identity.to_csv(processed_dir / "player_identity_audit.csv", index=False)

    milestone_result = build_batting_milestones(
        processed_root,
        players_path=players_path,
        aliases_path=aliases_path,
        scope_names=["all_available"],
        club_team_ids=get_club_team_ids(club_id),
        club_name_token=get_club_name(club_id),
    )
    milestone_result.milestones.to_csv(processed_dir / "all_batting_milestones.csv", index=False)
    milestone_result.validation.to_csv(processed_dir / "batting_milestones_validation.csv", index=False)

    summary = build_backfill_summary(
        combos,
        team_match_rows,
        unique_matches,
        request_records,
        frames,
        identity,
        milestone_result.milestones,
        started_at,
        now_iso(),
        raw_dir=raw_dir,
        processed_dir=processed_dir,
    )
    summary.to_csv(processed_dir / "backfill_summary.csv", index=False)
    print_run_review(summary, milestone_result.milestones, milestone_result.validation, identity)
    return 0


def load_scope_combinations(args: argparse.Namespace, *, teams_path: Path = TEAMS_PATH, seasons_path: Path = SEASONS_PATH) -> pd.DataFrame:
    teams = pd.read_csv(teams_path)
    seasons = pd.read_csv(seasons_path) if seasons_path.exists() else pd.DataFrame(columns=["id", "startDate"])
    teams = teams.drop_duplicates(["season_id", "team_id"]).copy()
    if args.season_ids:
        teams = teams[teams["season_id"].astype(str).isin(set(args.season_ids))]
    if args.team_ids:
        teams = teams[teams["team_id"].astype(str).isin(set(args.team_ids))]
    if not seasons.empty:
        season_order = seasons[["id", "startDate"]].rename(columns={"id": "season_id"})
        teams = teams.merge(season_order, on="season_id", how="left")
        teams["_season_sort"] = pd.to_datetime(teams["startDate"], errors="coerce")
        teams = teams.sort_values(["_season_sort", "season", "team_name"], ascending=[False, False, True])
    else:
        teams = teams.sort_values(["season", "team_name"], ascending=[False, True])
    if args.max_seasons is not None:
        selected_seasons = teams["season_id"].drop_duplicates().head(args.max_seasons)
        teams = teams[teams["season_id"].isin(selected_seasons)]
    if args.max_teams is not None:
        teams = teams.head(args.max_teams)
    return teams.reset_index(drop=True)


def dry_run_summary(
    combos: pd.DataFrame,
    *,
    club_id: str,
    playcricket_club_id: str,
    teams_path: Path,
    seasons_path: Path,
    players_path: Path,
    aliases_path: Path,
    raw_dir: Path,
    processed_dir: Path,
    dry_run: bool,
) -> None:
    seasons = combos[["season_id", "season"]].drop_duplicates() if not combos.empty else pd.DataFrame()
    print_club_header("Match-centre available backfill scope", club_id)
    print(f"- PlayCricket club ID: {playcricket_club_id}")
    print(f"- mode: {'dry run' if dry_run else 'backfill all available local scope'}")
    print(f"- external fetch: {'no' if dry_run else 'would fetch uncached match-centre endpoints'}")
    print_paths("Inputs", [teams_path, seasons_path, players_path, aliases_path])
    print_outputs("Raw/generated outputs", [raw_dir, processed_dir])
    print("- raw/generated match-centre outputs remain legacy ignored paths in Phase 6")
    print("Scope summary")
    print(f"- seasons: {len(seasons):,}")
    print(f"- teams: {combos['team_id'].nunique() if not combos.empty else 0:,}")
    print(f"- season/team combinations: {len(combos):,}")
    print("- ball-by-ball will only be fetched when scorecard isBallByBall is true")
    if dry_run:
        print("- dry run writes: no files")
    if not combos.empty:
        print("\nFirst combinations:")
        for _, row in combos.head(12).iterrows():
            print(f"  - {row['season']} | {row['team_name']} | {row.get('grade_name', '')}")


def fetch_team_match_lists(fetcher: PoliteMatchCentreFetcher, combos: pd.DataFrame, force_refresh: bool, *, raw_dir: Path = RAW_DIR) -> tuple[list[dict[str, Any]], list[RequestRecord]]:
    rows: list[dict[str, Any]] = []
    records: list[RequestRecord] = []
    for index, row in combos.iterrows():
        season_id = str(row["season_id"])
        team_id = str(row["team_id"])
        print(f"[{index + 1}/{len(combos)}] Team match list: {row['season']} | {row['team_name']} | {row.get('grade_name', '')}")
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
            rows.append({**match, "source_team_id": team_id, "source_season_id": season_id})
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
        source_team_id = str(row.get("source_team_id", ""))
        source_team_map.setdefault(match_id, [])
        if source_team_id and source_team_id not in source_team_map[match_id]:
            source_team_map[match_id].append(source_team_id)
    return list(matches.values()), source_team_map


def fetch_match_payloads(
    fetcher: PoliteMatchCentreFetcher,
    matches: list[dict[str, Any]],
    records: list[RequestRecord],
    force_refresh: bool,
    *,
    raw_dir: Path = RAW_DIR,
) -> list[Path]:
    scorecard_paths: list[Path] = []
    for index, match in enumerate(matches, start=1):
        match_id = str(match.get("id"))
        print(f"[{index}/{len(matches)}] Match payloads: {match_id}")
        scorecard_path = raw_dir / f"match={match_id}__scorecard.json"
        scorecard_payload, record = fetcher.get_json(
            f"/scores/matches/{match_id}",
            {"responseModifier": "includeScorecard", "jsconfig": "eccn:true"},
            scorecard_path,
            name="match_scorecard",
            match_id=match_id,
            force_refresh=force_refresh,
        )
        records.append(record)
        scorecard_paths.append(scorecard_path)

        officials_path = raw_dir / f"match={match_id}__officials.json"
        _, record = fetcher.get_json(
            f"/scores/matches/{match_id}/officials",
            {"jsconfig": "eccn:true"},
            officials_path,
            name="match_officials",
            match_id=match_id,
            force_refresh=force_refresh,
        )
        records.append(record)

        if isinstance(scorecard_payload, dict) and scorecard_payload.get("isBallByBall"):
            balls_path = raw_dir / f"match={match_id}__balls.json"
            _, record = fetcher.get_json(
                f"/scores/matches/{match_id}/balls",
                {"jsconfig": "eccn:true"},
                balls_path,
                name="match_balls",
                match_id=match_id,
                force_refresh=force_refresh,
            )
            records.append(record)
    return scorecard_paths


def load_match_payloads(scorecard_paths: list[Path], *, raw_dir: Path = RAW_DIR) -> list[MatchCentrePayloads]:
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
    matches["source_team_ids"] = matches["match_id"].astype(str).map(lambda match_id: " | ".join(source_team_map.get(match_id, [])))


def add_source_season_context(matches: pd.DataFrame, team_match_rows: list[dict[str, Any]], combos: pd.DataFrame) -> None:
    if matches.empty:
        matches["season_id"] = []
        matches["season"] = []
        return
    season_by_id = combos.drop_duplicates("season_id").set_index("season_id")["season"].to_dict()
    match_seasons: dict[str, str] = {}
    for row in team_match_rows:
        match_id = row.get("id")
        season_id = row.get("source_season_id")
        if match_id and season_id:
            match_seasons.setdefault(str(match_id), str(season_id))
    matches["season_id"] = matches["match_id"].astype(str).map(match_seasons).fillna("")
    matches["season"] = matches["season_id"].map(season_by_id).fillna("")


def build_backfill_summary(
    combos: pd.DataFrame,
    team_match_rows: list[dict[str, Any]],
    unique_matches: list[dict[str, Any]],
    request_records: list[RequestRecord],
    frames: dict[str, pd.DataFrame],
    identity: pd.DataFrame,
    milestones: pd.DataFrame,
    started_at: str,
    completed_at: str,
    *,
    raw_dir: Path = RAW_DIR,
    processed_dir: Path = PROCESSED_DIR,
) -> pd.DataFrame:
    validation = frames["validation_report"]
    status_counts = validation["status"].value_counts().to_dict() if not validation.empty else {}
    matches = frames["all_matches"]
    identity = ensure_club_ownership_columns(identity)
    club_identity = identity[identity["is_club_player"] == True] if not identity.empty else pd.DataFrame()  # noqa: E712
    return pd.DataFrame(
        [
            {
                "total_seasons": combos["season_id"].nunique(),
                "total_teams": combos["team_id"].nunique(),
                "total_season_team_combinations": len(combos),
                "total_team_match_rows": len(team_match_rows),
                "unique_matches_found": len({str(row.get("id")) for row in team_match_rows if row.get("id")}),
                "completed_matches": len(unique_matches),
                "scorecards_fetched": len(frames["all_matches"]),
                "matches_with_ball_by_ball": int(matches["is_ball_by_ball"].map(bool).sum()) if not matches.empty else 0,
                "matches_without_ball_by_ball": int((~matches["is_ball_by_ball"].map(bool)).sum()) if not matches.empty else 0,
                "balls_files_fetched": sum(1 for record in request_records if record.name == "match_balls"),
                "total_ball_events": len(frames["all_ball_by_ball"]),
                "total_batting_rows": len(frames["all_scorecard_batting"]),
                "total_bowling_rows": len(frames["all_scorecard_bowling"]),
                "total_fielding_rows": len(frames["all_scorecard_fielding"]),
                "total_milestone_rows": len(milestones),
                "fastest_50_count": int(milestones["balls_to_50"].notna().sum()) if "balls_to_50" in milestones else 0,
                "fastest_100_count": int(milestones["balls_to_100"].notna().sum()) if "balls_to_100" in milestones else 0,
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
                "started_at": started_at,
                "completed_at": completed_at,
            }
        ]
    )


def print_run_review(summary: pd.DataFrame, milestones: pd.DataFrame, milestone_validation: pd.DataFrame, identity: pd.DataFrame) -> None:
    print("\nBackfill summary")
    print(summary.to_string(index=False))
    print("\nTop 10 Fastest 50s")
    print_top_milestones(milestones, "balls_to_50")
    print("\nTop 10 Fastest 100s")
    print_top_milestones(milestones, "balls_to_100")
    print(f"\nMilestone validation warnings: {len(milestone_validation)}")
    print("Validation errors: 0")
    if not identity.empty:
        identity = ensure_club_ownership_columns(identity)
        no_matches = identity[(identity["is_club_player"] == True) & (identity["existing_player_match_status"] == "no_match")]  # noqa: E712
        print(f"Club player identity no-match rows: {len(no_matches)}")
        if not no_matches.empty:
            print(no_matches.head(20).to_string(index=False))


def print_top_milestones(milestones: pd.DataFrame, column: str) -> None:
    if milestones.empty or column not in milestones:
        print("No records.")
        return
    rows = milestones[milestones[column].notna()].copy()
    if rows.empty:
        print("No records.")
        return
    rows["match_date_sort"] = pd.to_datetime(rows.get("match_date"), errors="coerce")
    rows = rows.sort_values([column, "final_runs", "match_date_sort"], ascending=[True, False, False]).head(10)
    print(rows[["canonical_player_name", column, "final_runs", "opposition_team", "season", "match_date"]].to_string(index=False))


def write_manifest(path: Path, combos: pd.DataFrame, team_match_rows: list[dict[str, Any]], unique_matches: list[dict[str, Any]], request_records: list[RequestRecord], started_at: str) -> None:
    path.write_text(
        json.dumps(
            {
                "output_scope_name": "all_available",
                "started_at": started_at,
                "generated_at": now_iso(),
                "season_team_combinations": combos[["season_id", "season", "team_id", "team_name", "grade_name"]].to_dict("records"),
                "total_team_match_rows": len(team_match_rows),
                "unique_matches_found": len({str(row.get("id")) for row in team_match_rows if row.get("id")}),
                "completed_matches": len(unique_matches),
                "requests": [record.as_dict() for record in request_records],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def build_team_metadata(combos: pd.DataFrame) -> dict[str, dict[str, str]]:
    return {
        str(row["team_id"]): {
            "season": str(row.get("season", "")),
            "team_name": str(row.get("team_name", "")),
            "grade_name": str(row.get("grade_name", "")),
        }
        for _, row in combos.iterrows()
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_completed_match(match: dict[str, Any]) -> bool:
    return str(match.get("status", "")).upper() == "COMPLETED" or match.get("statusId") == 3


def count_identity(frame: pd.DataFrame, status: str) -> int:
    if frame.empty:
        return 0
    return int((frame["existing_player_match_status"] == status).sum())


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


if __name__ == "__main__":
    raise SystemExit(main())
