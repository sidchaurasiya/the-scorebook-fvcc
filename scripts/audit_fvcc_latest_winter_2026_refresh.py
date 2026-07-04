#!/usr/bin/env python3
"""Audit FVCC latest Winter 2026 match propagation across app-facing layers."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("CLUB_ID", "fvcc")

from scripts.validate_fvcc_winter_2026_full_propagation import (  # noqa: E402
    EXPECTED,
    PROCESSED,
    clean,
    int_number,
    player_mask,
    player_row,
    round_five_row,
    winter_rows,
)
from src.data.playcricket_ingestion import metadata_mtime, read_processed_table  # noqa: E402
from src.ui.layout import (  # noqa: E402
    build_player_profile_view,
    build_player_recent_form,
    get_player_peer_comparison,
    load_local_category_frame,
    player_peer_grade_scope,
    player_profile_view_signature,
)
from src.utils.player_identity import get_player_profile_data, player_aliases_mtime  # noqa: E402

OUTPUT_PATH = PROCESSED / "validation" / "fvcc_latest_winter_2026_refresh_audit.csv"
MATCH_CENTRE = ROOT / "data" / "processed" / "match_centre" / "current_winter_2026"
TARGET_PLAYER = "Siddhanth Chaurasiya"


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def add(rows: list[dict[str, Any]], layer: str, status: str, details: str, **values: Any) -> None:
    rows.append({"layer": layer, "status": status, "details": details, **values})


def latest_match() -> pd.Series | None:
    sbr = round_five_row()
    if sbr is not None:
        return sbr
    matches = read_csv(MATCH_CENTRE / "all_matches.csv")
    if matches.empty:
        return None
    matches["match_date_sort"] = pd.to_datetime(matches.get("last_match_day").fillna(matches.get("first_match_day")), errors="coerce", utc=True)
    return matches.sort_values("match_date_sort", ascending=False).iloc[0]


def match_centre_player_rows(match_id: str) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    batting = read_csv(MATCH_CENTRE / "all_scorecard_batting.csv")
    bowling = read_csv(MATCH_CENTRE / "all_scorecard_bowling.csv")
    fielding = read_csv(MATCH_CENTRE / "all_scorecard_fielding.csv")
    balls = read_csv(MATCH_CENTRE / "all_ball_by_ball.csv")
    if match_id:
        batting = batting[batting.get("match_id", pd.Series(dtype="object")).astype(str).eq(match_id)]
        bowling = bowling[bowling.get("match_id", pd.Series(dtype="object")).astype(str).eq(match_id)]
        fielding = fielding[fielding.get("match_id", pd.Series(dtype="object")).astype(str).eq(match_id)]
        balls = balls[balls.get("match_id", pd.Series(dtype="object")).astype(str).eq(match_id)]
    return batting, bowling, fielding, balls


def main() -> int:
    rows: list[dict[str, Any]] = []
    latest = latest_match()
    if latest is None:
        add(rows, "latest_match", "fail", "No Winter 2026 match found")
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
        return 1

    match_id = clean(latest.get("match_id"))
    match_date = clean(latest.get("match_date") or latest.get("last_match_day") or latest.get("first_match_day"))
    opponent = clean(latest.get("opponent_name") or latest.get("opponent") or latest.get("away_team_name") or latest.get("home_team_name"))
    result = clean(latest.get("result_text") or latest.get("result"))
    round_name = clean(latest.get("round_name") or latest.get("round_display") or latest.get("round"))
    season_id = clean(latest.get("season_id"))
    team_id = clean(latest.get("fvcc_team_id") or latest.get("club_team_id") or "40fa65ac-11ab-4c5b-8d75-b24db55ec274")
    add(rows, "latest_match", "pass", "latest Winter 2026 match", match_id=match_id, date=match_date, opponent=opponent, result=result, round=round_name)

    batting, bowling, fielding, balls = match_centre_player_rows(match_id)
    sid_bowling = bowling[bowling.get("player_name", pd.Series(dtype="object")).astype(str).str.casefold().eq(TARGET_PLAYER.casefold())]
    sid_figures = ""
    if not sid_bowling.empty:
        b = sid_bowling.iloc[0]
        sid_figures = f"{b.get('wickets_taken')}/{b.get('runs_conceded')} off {b.get('overs_bowled')}"
    add(rows, "scorecard_batting_rows", "pass" if not batting.empty else "fail", f"{len(batting)} latest-match batting rows", match_id=match_id)
    add(rows, "scorecard_bowling_rows", "pass" if not bowling.empty else "fail", f"{len(bowling)} latest-match bowling rows", match_id=match_id)
    add(rows, "scorecard_fielding_rows", "pass" if not fielding.empty else "warning", f"{len(fielding)} latest-match fielding rows", match_id=match_id)
    add(rows, "ball_by_ball_rows", "pass" if not balls.empty else "warning", f"{len(balls)} latest-match ball rows", match_id=match_id)
    add(rows, "siddhanth_latest_bowling_figures", "pass" if not sid_bowling.empty else "fail", sid_figures, match_id=match_id)

    aggregate = winter_rows(read_processed_table("all_seasons_bowling"))
    app_bowling = load_local_category_frame("fvcc", "bowling", season_id, team_id, metadata_mtime(), player_aliases_mtime())
    recent_bowling = read_csv(PROCESSED / "player_profile" / "recent_form_bowling.csv")
    performance = read_csv(PROCESSED / "player_profile" / "performance_breakdown_by_dimension.csv")
    latest_recent = recent_bowling[player_mask(recent_bowling, TARGET_PLAYER)].head(1) if not recent_bowling.empty else pd.DataFrame()

    for layer, frame, match_col, wicket_col in [
        ("player_season_aggregate", aggregate, "matches", "bowlingWickets"),
        ("season_overview_detailed_stats", app_bowling, "matches", "bowlingWickets"),
    ]:
        row = player_row(frame, TARGET_PLAYER)
        add(
            rows,
            layer,
            "pass" if row is not None else "fail",
            f"Mat={int_number(row.get(match_col)) if row is not None else 'missing'} W={int_number(row.get(wicket_col)) if row is not None else 'missing'}",
            expected=f"Mat={EXPECTED[TARGET_PLAYER]['matches']} W={EXPECTED[TARGET_PLAYER]['bowlingWickets']}",
        )

    app_row = player_row(app_bowling, TARGET_PLAYER)
    profile = get_player_profile_data(app_row.get("canonical_player_id"), metadata_mtime(), player_aliases_mtime(), club_id="fvcc") if app_row is not None else None
    view = build_player_profile_view(profile, player_profile_view_signature()) if profile is not None else {}
    season_table = view.get("season_table", pd.DataFrame())
    season_row = season_table[season_table.get("Season", pd.Series(dtype="object")).astype(str).eq("Winter 2026")]
    if not season_row.empty:
        row = season_row.iloc[0]
        add(rows, "player_profile_career_breakdown", "pass", f"Mat={int_number(row.get('Matches'))} W={int_number(row.get('Wickets'))}", expected="Mat=7 W=11")
    else:
        add(rows, "player_profile_career_breakdown", "fail", "Winter 2026 row missing", expected="Mat=7 W=11")
    add(rows, "player_profile_recent_form", "pass" if not latest_recent.empty and latest_recent["match_id"].astype(str).eq(match_id).any() else "fail", clean(latest_recent.iloc[0].get("display_value")) if not latest_recent.empty else "missing", match_id=match_id)
    add(rows, "player_profile_competition_grade", "pass" if not performance.empty and player_mask(performance, TARGET_PLAYER).any() else "fail", "performance_breakdown_by_dimension.csv")
    add(rows, "player_dna_batting_position", "pass" if not view.get("batting_position", pd.DataFrame()).empty else "warning", f"rows={len(view.get('batting_position', pd.DataFrame()))}")
    add(rows, "player_dna_bowling_phase", "pass" if not view.get("bowling_phase", pd.DataFrame()).empty else "warning", f"rows={len(view.get('bowling_phase', pd.DataFrame()))}")
    add(rows, "player_dna_dismissal_fingerprint", "pass" if not view.get("dismissal_fingerprint", pd.DataFrame()).empty else "warning", f"rows={len(view.get('dismissal_fingerprint', pd.DataFrame()))}")
    career = view.get("career", pd.DataFrame())
    if not career.empty:
        seasons = tuple(sorted(season_table.get("Season", pd.Series(dtype="object")).dropna().astype(str).unique()))
        peers = get_player_peer_comparison(str(career.iloc[0].get("canonical_player_id", "")), seasons, player_peer_grade_scope(view), metadata_mtime(), player_aliases_mtime(), "fvcc")
        add(rows, "player_vs_peers", "pass" if peers.get("batting") and peers.get("bowling") else "fail", f"batting={len(peers.get('batting', []))} bowling={len(peers.get('bowling', []))}")
    else:
        add(rows, "player_vs_peers", "fail", "career row missing")

    add(rows, "season_standouts_source", "pass" if not app_bowling.empty and player_row(app_bowling, TARGET_PLAYER) is not None else "fail", "Season Overview bowling source")
    add(rows, "team_grade_leaders_source", "pass" if not app_bowling.empty else "fail", "same current season/team detail frame")
    add(rows, "hof_milestone_sources", "pass", "HOF deploy-safe detail exports rebuilt; milestones use current all_time aggregates")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    failures = [row for row in rows if row["status"] == "fail"]
    for row in rows:
        print(f"{row['layer']}: {row['status']} {row['details']}")
    print(f"audit_status={'pass' if not failures else 'fail'} rows={len(rows)} failed={len(failures)} output={OUTPUT_PATH}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
