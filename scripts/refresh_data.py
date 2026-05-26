#!/usr/bin/env python3
"""Weekly club PlayCricket aggregate data refresh.

This script is intentionally local-data-first:
- It keeps existing raw JSON backups.
- It refreshes the live/current season from PlayCricket.
- It rebuilds processed CSVs, canonical player fields, and team/grade audits.
- It runs aggregate data only unless --with-current-match-centre is passed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import re
import subprocess
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
    CACHE_DIR,
    EXPORTS_DIR,
    METADATA_PATH,
    PLAYCRICKET_PUBLIC_BASE_URL,
    PROCESSED_DIR,
    PUBLIC_HEADERS,
    RAW_DIR,
    RefreshSummary,
    refresh_playcricket_backup,
)
from scripts.club_refresh_utils import print_club_header, print_outputs, print_paths, resolve_club_id  # noqa: E402
from src.config.club_config import (  # noqa: E402
    allow_legacy_fallback,
    get_data_root,
    get_hall_of_fame_dir,
    get_mapping_path,
    get_processed_dir,
    get_processed_match_centre_dir,
    get_player_profile_dir,
    get_season_overview_dir,
    load_club_config,
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
AGGREGATE_OUTPUT_TABLES = (
    "seasons",
    "teams",
    "players",
    "all_seasons_batting",
    "all_seasons_bowling",
    "all_seasons_fielding",
    "all_seasons_matches",
    "all_seasons_scorecard_batting",
    "all_seasons_scorecard_bowling",
    "all_seasons_scorecard_fielding",
)


@dataclass
class TableSnapshot:
    rows: dict[str, int]
    seasons: list[str]
    latest_season: str
    estimated_matches: int


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh PlayCricket aggregate data for The Scorebook.")
    parser.add_argument("--club", default=None, help="Club config id. Defaults to CLUB_ID or fvcc.")
    parser.add_argument("--dry-run", action="store_true", help="Print the club-aware refresh plan without network requests or writes.")
    parser.add_argument(
        "--legacy-output",
        action="store_true",
        help="Write aggregate processed CSVs to legacy data/processed instead of the active club folder.",
    )
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
    parser.add_argument(
        "--with-current-match-centre",
        action="store_true",
        help="After aggregate refresh, also run the current-season match-centre refresh and deploy-safe builders.",
    )
    parser.add_argument(
        "--local-only-identity-rebuild",
        action="store_true",
        help="Reapply club player/team mappings to existing processed aggregate CSVs without network requests.",
    )
    args = parser.parse_args()
    club_id = resolve_club_id(args.club)
    club_config = load_club_config(club_id)
    playcricket_club_id = configured_playcricket_club_id(club_config, club_id)
    processed_output_dir = PROCESSED_DIR if args.legacy_output else get_processed_dir(club_id=club_id)
    raw_output_dir = RAW_DIR
    cache_output_dir = CACHE_DIR
    exports_output_dir = EXPORTS_DIR
    metadata_output_path = METADATA_PATH if args.legacy_output else get_data_root(club_id=club_id) / "metadata.json"

    print("The Scorebook PlayCricket refresh")
    print(f"Project: {ROOT}")
    mode = "dry run plan" if args.dry_run else "local-only identity rebuild" if args.local_only_identity_rebuild else "normal refresh"
    print(f"Mode: {mode}")
    print_club_header("Club context", club_id)
    print()

    if args.dry_run:
        print_refresh_plan(
            club_id,
            playcricket_club_id=playcricket_club_id,
            processed_dir=processed_output_dir,
            raw_dir=raw_output_dir,
            cache_dir=cache_output_dir,
            metadata_path=metadata_output_path,
        )
        print()
        print("Dry run complete. No network requests were made and no files were written.")
        return 0

    if args.local_only_identity_rebuild:
        before = capture_snapshot(processed_output_dir)
        print_snapshot("Current local data", before)
        print("Local-only identity rebuild selected. No network requests will be made.")
        identity_summary = rebuild_identity_and_audits(processed_output_dir, club_id=club_id)
        after = capture_snapshot(processed_output_dir)
        print()
        print_snapshot("Rebuilt local data", after)
        print_delta(before, after)
        print()
        print("Identity and audit rebuild")
        for label, value in identity_summary.items():
            print(f"- {label}: {value}")
        return 0

    before = capture_snapshot(processed_output_dir)
    print_snapshot("Current local data", before)

    live_seasons = fetch_live_seasons(playcricket_club_id)
    latest_live = first_season_name(live_seasons)
    current_ids = current_season_ids(live_seasons)
    print(f"Live seasons found: {len(live_seasons)}")
    print(f"Latest live season: {latest_live or 'unknown'}")
    print(f"Current/live season ids to force-refresh weekly: {len(current_ids)}")

    backup_path = create_timestamped_backup(
        processed_dir=processed_output_dir,
        raw_dir=raw_output_dir,
        metadata_path=metadata_output_path,
    )
    print()
    print(f"Rollback snapshot saved: {backup_path}")

    summary = refresh_playcricket_backup(
        playcricket_club_id,
        force=args.force_all,
        season_limit=args.season_limit,
        force_seasons=True,
        force_season_ids=None if args.force_all else current_ids,
        processed_dir=processed_output_dir,
        raw_dir=raw_output_dir,
        metadata_path=metadata_output_path,
        cache_dir=cache_output_dir,
        exports_dir=exports_output_dir,
    )
    print_refresh_summary(summary)

    identity_summary = rebuild_identity_and_audits(processed_output_dir, club_id=club_id)
    if args.with_current_match_centre:
        match_centre_summary = refresh_current_match_centre_summaries(current_ids, club_id=club_id, processed_dir=processed_output_dir)
    else:
        match_centre_summary = {
            "current scopes refreshed": 0,
            "detail exports rebuilt": "skipped; pass --with-current-match-centre to run match-centre refresh",
        }
    after = capture_snapshot(processed_output_dir)

    print()
    print_snapshot("Refreshed local data", after)
    print_delta(before, after)
    print()
    print("Identity and audit rebuild")
    for label, value in identity_summary.items():
        print(f"- {label}: {value}")
    print()
    print("Current-season match-centre and deploy-safe detail summaries")
    for label, value in match_centre_summary.items():
        print(f"- {label}: {value}")

    print()
    print("Next step")
    print(f"./.venv-app/bin/python scripts/refresh_club_outputs.py --club {club_id}")
    print(f"CLUB_ID={club_id} ./.venv-app/bin/streamlit run app.py --server.port 8502")
    return 0 if not summary.failed_requests else 1


def configured_playcricket_club_id(config: dict[str, Any], club_id: str) -> str:
    playcricket_club_id = str(config.get("club", {}).get("playcricket_club_id") or "").strip()
    if not playcricket_club_id:
        raise SystemExit(f"Club '{club_id}' is missing club.playcricket_club_id in clubs/{club_id}/club_config.yaml.")
    return playcricket_club_id


def print_refresh_plan(
    club_id: str,
    *,
    playcricket_club_id: str,
    processed_dir: Path,
    raw_dir: Path,
    cache_dir: Path,
    metadata_path: Path,
) -> None:
    print("Refresh plan")
    print(f"- PlayCricket club ID: {playcricket_club_id}")
    print_paths("Aggregate refresh roots", [processed_dir, raw_dir, cache_dir, metadata_path.parent])
    print_outputs("Planned aggregate CSV outputs", aggregate_output_paths(processed_dir))
    print_outputs("Planned metadata output", [metadata_path])
    print_paths("Match-centre generated root", [get_processed_match_centre_dir(club_id=club_id)])
    print_paths(
        "Deploy-safe output roots",
        [
            get_hall_of_fame_dir(club_id=club_id),
            get_season_overview_dir(club_id=club_id),
            get_player_profile_dir(club_id=club_id),
        ],
    )
    commands = [
        f"scripts/refresh_data.py --club {club_id} --with-current-match-centre (optional current match-centre scope)",
        f"scripts/build_season_overview_detail_exports.py --club {club_id}",
        f"scripts/build_player_profile_insight_exports.py --club {club_id}",
        f"scripts/build_hall_of_fame_detail_exports.py --club {club_id}",
        f"scripts/build_premiership_hall_of_fame_exports.py --club {club_id}",
    ]
    print("Would run after live aggregate refresh:")
    for command in commands:
        print(f"- {command}")
    print(f"Next deploy-safe rebuild command: scripts/refresh_club_outputs.py --club {club_id}")


def aggregate_output_paths(processed_dir: Path) -> list[Path]:
    return [processed_dir / f"{table}.csv" for table in AGGREGATE_OUTPUT_TABLES]


def capture_snapshot(processed_dir: Path) -> TableSnapshot:
    rows: dict[str, int] = {}
    for table in PROCESSED_TABLES:
        frame = read_processed(table, processed_dir=processed_dir)
        rows[table] = len(frame)

    seasons_frame = read_processed("seasons", processed_dir=processed_dir)
    seasons = seasons_frame["name"].dropna().astype(str).tolist() if "name" in seasons_frame else []
    latest = seasons[0] if seasons else ""
    estimated_matches = estimate_total_matches_from_processed(processed_dir)
    return TableSnapshot(rows=rows, seasons=seasons, latest_season=latest, estimated_matches=estimated_matches)


def read_processed(table: str, *, processed_dir: Path) -> pd.DataFrame:
    path = processed_dir / f"{table}.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def estimate_total_matches_from_processed(processed_dir: Path) -> int:
    team_totals: dict[tuple[str, str], float] = {}
    for table in ("all_seasons_batting", "all_seasons_bowling", "all_seasons_fielding"):
        frame = read_processed(table, processed_dir=processed_dir)
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


def create_timestamped_backup(*, processed_dir: Path, raw_dir: Path, metadata_path: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    target = BACKUP_DIR / f"data_snapshot_{timestamp}"
    target.mkdir(parents=True, exist_ok=False)
    for source in [raw_dir, processed_dir]:
        if source.exists():
            shutil.copytree(source, target / source.name)
    if metadata_path.exists():
        shutil.copy2(metadata_path, target / metadata_path.name)
    return target


def rebuild_identity_and_audits(processed_dir: Path, *, club_id: str) -> dict[str, object]:
    source = combined_processed_frames(apply_identity=False, processed_dir=processed_dir)
    if allow_legacy_fallback(club_id):
        mapping_update = ensure_player_alias_mappings(source, club_id=club_id)
    else:
        mapping_update = {"added": 0, "conflicts": 0, "manual_candidates": 0, "auto_candidates": 0}
    canonical_counts = rebuild_canonical_processed_tables(processed_dir=processed_dir, club_id=club_id)
    aliases = load_player_aliases(club_id=club_id)
    canonical_source = combined_processed_frames(apply_identity=True, aliases=aliases, processed_dir=processed_dir, club_id=club_id)
    identity_exports = ensure_identity_exports(canonical_source, aliases, club_id=club_id)
    audit_frames = [
        read_processed("all_seasons_batting", processed_dir=processed_dir),
        read_processed("all_seasons_bowling", processed_dir=processed_dir),
        read_processed("all_seasons_fielding", processed_dir=processed_dir),
        read_processed("teams", processed_dir=processed_dir),
    ]
    export_team_grade_display_audit(audit_frames, path=get_mapping_path("team_grade_display_audit.csv", club_id=club_id))
    return {
        "mapping rows added": mapping_update.get("added", 0),
        "mapping conflicts": mapping_update.get("conflicts", 0),
        "manual mapping candidates": mapping_update.get("manual_candidates", 0),
        "auto mapping candidates": mapping_update.get("auto_candidates", 0),
        "canonical table rows": canonical_counts,
        "identity summary rows": identity_exports.get("summary_rows", 0),
        "possible duplicate rows": identity_exports.get("possible_duplicates", 0),
    }


def refresh_current_match_centre_summaries(current_season_ids: set[str], *, club_id: str, processed_dir: Path) -> dict[str, object]:
    teams = read_processed("teams", processed_dir=processed_dir)
    if teams.empty or not current_season_ids:
        return {"current scopes refreshed": 0, "detail exports rebuilt": "no current teams found"}
    current = teams[teams["season_id"].astype(str).isin(current_season_ids)].copy()
    current = current.drop_duplicates(["season_id", "team_id"])
    if current.empty:
        return {"current scopes refreshed": 0, "detail exports rebuilt": "no current teams found"}

    scopes: list[str] = []
    for season_id, group in current.groupby("season_id", sort=False):
        season_name = str(group["season"].dropna().iloc[0] if "season" in group and not group["season"].dropna().empty else season_id)
        scope_name = f"current_{slugify(season_name)}"
        command = [
            sys.executable,
            str(ROOT / "scripts" / "refresh_match_centre_data.py"),
            "--season-id",
            str(season_id),
            "--club",
            club_id,
            "--output-scope-name",
            scope_name,
            "--sleep-seconds",
            "0.5",
            "--force-refresh",
        ]
        for team_id in group["team_id"].dropna().astype(str).drop_duplicates():
            command.extend(["--team-id", team_id])
        subprocess.run(command, cwd=ROOT, check=True)
        scopes.append(scope_name)

    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_season_overview_detail_exports.py"), "--club", club_id],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_player_profile_insight_exports.py"), "--club", club_id],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_hall_of_fame_detail_exports.py"), "--club", club_id],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "build_premiership_hall_of_fame_exports.py"), "--club", club_id],
        cwd=ROOT,
        check=True,
    )
    return {
        "current scopes refreshed": len(scopes),
        "scopes": ", ".join(scopes),
        "detail exports rebuilt": "yes",
        "player profile insight exports rebuilt": "yes",
        "hall of fame detail exports rebuilt": "yes",
        "premiership exports rebuilt": "yes",
    }


def slugify(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "_", value.strip().casefold())
    return text.strip("_") or "current_season"


def combined_processed_frames(
    *,
    apply_identity: bool,
    processed_dir: Path,
    aliases: pd.DataFrame | None = None,
    club_id: str | None = None,
) -> pd.DataFrame:
    frames = []
    for table in ("all_seasons_batting", "all_seasons_bowling", "all_seasons_fielding"):
        frame = read_processed(table, processed_dir=processed_dir)
        if frame.empty:
            continue
        frames.append(apply_player_identity_mapping(frame, aliases, club_id=club_id) if apply_identity else frame)
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
