#!/usr/bin/env python3
"""Weekly FVCC PlayCricket data refresh.

This script is intentionally local-data-first:
- It keeps existing raw JSON backups.
- It refreshes the live/current season from PlayCricket.
- It rebuilds processed CSVs, canonical player fields, and team/grade audits.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.playcricket_ingestion import (  # noqa: E402
    DEFAULT_CLUB_ID,
    METADATA_PATH,
    PLAYCRICKET_PUBLIC_BASE_URL,
    PROCESSED_DIR,
    PUBLIC_HEADERS,
    RAW_DIR,
    RefreshSummary,
    refresh_playcricket_backup,
)
from src.utils.player_identity import (  # noqa: E402
    apply_player_identity_mapping,
    ensure_identity_exports,
    ensure_player_alias_mappings,
    load_player_aliases,
    rebuild_canonical_processed_tables,
)
from src.utils.team_grade import export_team_grade_display_audit  # noqa: E402


DATA_DIR = ROOT / "data"
BACKUP_DIR = DATA_DIR / "backups"
PROCESSED_TABLES = (
    "seasons",
    "teams",
    "players",
    "all_seasons_batting",
    "all_seasons_bowling",
    "all_seasons_fielding",
)


@dataclass
class TableSnapshot:
    rows: dict[str, int]
    seasons: list[str]
    latest_season: str
    estimated_matches: int


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh FVCC PlayCricket data for the Streamlit app.")
    parser.add_argument("--dry-run", action="store_true", help="Check live season availability without changing app data.")
    parser.add_argument(
        "--force-all",
        action="store_true",
        help="Force-refresh every historical season. Use sparingly; weekly refresh does not need this.",
    )
    parser.add_argument(
        "--season-limit",
        type=int,
        default=None,
        help="Optional development/testing limit for number of seasons fetched.",
    )
    args = parser.parse_args()

    print("FVCC weekly PlayCricket refresh")
    print(f"Project: {ROOT}")
    print(f"Mode: {'dry run' if args.dry_run else 'normal refresh'}")
    print()

    before = capture_snapshot()
    print_snapshot("Current local data", before)

    live_seasons = fetch_live_seasons(DEFAULT_CLUB_ID)
    latest_live = first_season_name(live_seasons)
    current_ids = current_season_ids(live_seasons)
    print(f"Live seasons found: {len(live_seasons)}")
    print(f"Latest live season: {latest_live or 'unknown'}")
    print(f"Current/live season ids to force-refresh weekly: {len(current_ids)}")

    if args.dry_run:
        local_has_latest = latest_live in before.seasons if latest_live else False
        print()
        print("Dry run complete. No raw or processed app data was changed.")
        print(f"Latest live season already local: {'yes' if local_has_latest else 'no'}")
        print("Run without --dry-run to create a timestamped backup and refresh app data.")
        return 0

    backup_path = create_timestamped_backup()
    print()
    print(f"Rollback snapshot saved: {backup_path}")

    summary = refresh_playcricket_backup(
        DEFAULT_CLUB_ID,
        force=args.force_all,
        season_limit=args.season_limit,
        force_seasons=True,
        force_season_ids=None if args.force_all else current_ids,
    )
    print_refresh_summary(summary)

    identity_summary = rebuild_identity_and_audits()
    after = capture_snapshot()

    print()
    print_snapshot("Refreshed local data", after)
    print_delta(before, after)
    print()
    print("Identity and audit rebuild")
    for label, value in identity_summary.items():
        print(f"- {label}: {value}")

    print()
    print("Next step")
    print("./.venv-app/bin/streamlit run app.py --server.port 8502")
    return 0 if not summary.failed_requests else 1


def capture_snapshot() -> TableSnapshot:
    rows: dict[str, int] = {}
    for table in PROCESSED_TABLES:
        frame = read_processed(table)
        rows[table] = len(frame)

    seasons_frame = read_processed("seasons")
    seasons = seasons_frame["name"].dropna().astype(str).tolist() if "name" in seasons_frame else []
    latest = seasons[0] if seasons else ""
    estimated_matches = estimate_total_matches_from_processed()
    return TableSnapshot(rows=rows, seasons=seasons, latest_season=latest, estimated_matches=estimated_matches)


def read_processed(table: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{table}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def estimate_total_matches_from_processed() -> int:
    team_totals: dict[tuple[str, str], float] = {}
    for table in ("all_seasons_batting", "all_seasons_bowling", "all_seasons_fielding"):
        frame = read_processed(table)
        if frame.empty or "matches" not in frame:
            continue
        frame = frame.copy()
        frame["matches"] = pd.to_numeric(frame["matches"], errors="coerce").fillna(0)
        for _, row in frame.iterrows():
            season_id = str(row.get("season_id", row.get("season", "")))
            team_id = str(row.get("team_id", row.get("team_name", "")))
            key = (season_id, team_id)
            team_totals[key] = max(team_totals.get(key, 0), float(row["matches"]))
    return int(sum(team_totals.values()))


def fetch_live_seasons(club_id: str) -> list[dict[str, Any]]:
    url = f"{PLAYCRICKET_PUBLIC_BASE_URL}/fixturesladders/organisations/{club_id}/seasons"
    response = requests.get(
        url,
        params={"jsconfig": "eccn:true"},
        headers=PUBLIC_HEADERS,
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    return payload.get("seasons", []) if isinstance(payload, dict) else []


def first_season_name(seasons: list[dict[str, Any]]) -> str:
    return str(seasons[0].get("name", "")) if seasons else ""


def current_season_ids(seasons: list[dict[str, Any]]) -> set[str]:
    current = {str(season.get("id")) for season in seasons if season.get("isCurrentSeason") and season.get("id")}
    if current:
        return current
    first = seasons[0].get("id") if seasons else None
    return {str(first)} if first else set()


def create_timestamped_backup() -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = BACKUP_DIR / f"data_snapshot_{timestamp}"
    target.mkdir(parents=True, exist_ok=False)
    for source in [RAW_DIR, PROCESSED_DIR]:
        if source.exists():
            shutil.copytree(source, target / source.name)
    if METADATA_PATH.exists():
        shutil.copy2(METADATA_PATH, target / METADATA_PATH.name)
    return target


def rebuild_identity_and_audits() -> dict[str, object]:
    source = combined_processed_frames(apply_identity=False)
    mapping_update = ensure_player_alias_mappings(source)
    canonical_counts = rebuild_canonical_processed_tables()
    aliases = load_player_aliases()
    canonical_source = combined_processed_frames(apply_identity=True, aliases=aliases)
    identity_exports = ensure_identity_exports(canonical_source, aliases)
    audit_frames = [
        read_processed("all_seasons_batting"),
        read_processed("all_seasons_bowling"),
        read_processed("all_seasons_fielding"),
        read_processed("teams"),
    ]
    export_team_grade_display_audit(audit_frames)
    return {
        "mapping rows added": mapping_update.get("added", 0),
        "mapping conflicts": mapping_update.get("conflicts", 0),
        "manual mapping candidates": mapping_update.get("manual_candidates", 0),
        "auto mapping candidates": mapping_update.get("auto_candidates", 0),
        "canonical table rows": canonical_counts,
        "identity summary rows": identity_exports.get("summary_rows", 0),
        "possible duplicate rows": identity_exports.get("possible_duplicates", 0),
    }


def combined_processed_frames(*, apply_identity: bool, aliases: pd.DataFrame | None = None) -> pd.DataFrame:
    frames = []
    for table in ("all_seasons_batting", "all_seasons_bowling", "all_seasons_fielding"):
        frame = read_processed(table)
        if frame.empty:
            continue
        frames.append(apply_player_identity_mapping(frame, aliases) if apply_identity else frame)
    return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()


def print_snapshot(title: str, snapshot: TableSnapshot) -> None:
    print(title)
    print(f"- seasons found: {snapshot.rows.get('seasons', 0)}")
    print(f"- latest season: {snapshot.latest_season or 'unknown'}")
    print(f"- teams found: {snapshot.rows.get('teams', 0)}")
    print(f"- estimated matches: {snapshot.estimated_matches}")
    for table in ("all_seasons_batting", "all_seasons_bowling", "all_seasons_fielding", "players"):
        print(f"- {table}: {snapshot.rows.get(table, 0)} rows")
    print()


def print_delta(before: TableSnapshot, after: TableSnapshot) -> None:
    print("Changes from previous local data")
    print(f"- seasons: {delta(before.rows.get('seasons', 0), after.rows.get('seasons', 0))}")
    print(f"- teams: {delta(before.rows.get('teams', 0), after.rows.get('teams', 0))}")
    print(f"- estimated matches: {delta(before.estimated_matches, after.estimated_matches)}")
    for table in ("all_seasons_batting", "all_seasons_bowling", "all_seasons_fielding", "players"):
        print(f"- {table}: {delta(before.rows.get(table, 0), after.rows.get(table, 0))}")


def delta(before: int, after: int) -> str:
    change = after - before
    sign = "+" if change >= 0 else ""
    return f"{before} -> {after} ({sign}{change})"


def print_refresh_summary(summary: RefreshSummary) -> None:
    payload = summary.as_dict()
    print()
    print("PlayCricket refresh summary")
    print(f"- seasons found: {payload.get('seasons_found', 0)}")
    print(f"- teams found: {payload.get('teams_found', 0)}")
    print(f"- stat rows: {json.dumps(payload.get('stat_rows', {}), sort_keys=True)}")
    print(f"- live requests: {payload.get('live_requests', 0)}")
    print(f"- cache hits: {payload.get('cache_hits', 0)}")
    failures = payload.get("failed_requests", [])
    if failures:
        print("- warnings/errors:")
        for failure in failures:
            print(f"  - {failure}")
    else:
        print("- warnings/errors: none")


if __name__ == "__main__":
    raise SystemExit(main())
