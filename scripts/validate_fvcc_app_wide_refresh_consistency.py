#!/usr/bin/env python3
"""Gate FVCC match-day refreshes against every app-facing data surface."""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["CLUB_ID"] = "fvcc"

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
from src.data.featured_record_overrides import featured_record_overrides_mtime  # noqa: E402
from src.ui.layout import (  # noqa: E402
    HALL_OF_FAME_DATA_VERSION,
    build_player_profile_view,
    build_player_recent_form,
    get_hall_of_fame_data,
    get_player_peer_comparison,
    load_local_category_frame,
    player_peer_grade_scope,
    player_profile_view_signature,
)
from src.utils.player_identity import get_player_profile_data, player_aliases_mtime  # noqa: E402

MATCH_CENTRE = ROOT / "data" / "processed" / "match_centre" / "current_winter_2026"
OUTPUT_PATH = PROCESSED / "validation" / "fvcc_app_wide_refresh_consistency_validation.csv"
SUMMARY_PATH = PROCESSED / "validation" / "fvcc_latest_refresh_consistency_summary.md"
VERSION_PATH = PROCESSED / "metadata" / "fvcc_data_version.json"


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def add(
    rows: list[dict[str, object]],
    check_name: str,
    status: bool,
    *,
    player: str = "",
    expected: object = "",
    actual: object = "",
    source: str = "",
    notes: str = "",
) -> None:
    rows.append(
        {
            "check_name": check_name,
            "status": "pass" if status else "fail",
            "player": player,
            "expected": expected,
            "actual": actual,
            "source_file_or_function": source,
            "notes": notes,
        }
    )


def numeric(value: object) -> float:
    number = pd.to_numeric(value, errors="coerce")
    return 0.0 if pd.isna(number) else float(number)


def latest_match_row() -> pd.Series | None:
    row = round_five_row()
    return row if row is not None else None


def latest_match_players(match_id: str, team_id: str) -> pd.DataFrame:
    frames = []
    for filename in ["all_scorecard_batting.csv", "all_scorecard_bowling.csv", "all_scorecard_fielding.csv"]:
        frame = read_csv(MATCH_CENTRE / filename)
        if frame.empty or "match_id" not in frame:
            continue
        frame = frame[frame["match_id"].astype(str).eq(str(match_id))].copy()
        if team_id and "team_id" in frame:
            frame = frame[frame["team_id"].astype(str).eq(str(team_id))].copy()
        if frame.empty:
            continue
        for column in ["canonical_player_id", "canonical_player_name", "display_player_name", "player_id", "player_name"]:
            if column not in frame:
                frame[column] = ""
        frame["source"] = filename
        frames.append(frame[["canonical_player_id", "canonical_player_name", "display_player_name", "player_id", "player_name", "source"]])
    if not frames:
        return pd.DataFrame(columns=["canonical_player_id", "canonical_player_name"])
    combined = pd.concat(frames, ignore_index=True)
    combined["canonical_player_id"] = combined["canonical_player_id"].fillna("").astype(str).str.strip()
    combined["canonical_player_name"] = combined["canonical_player_name"].fillna("").astype(str).str.strip()
    combined.loc[combined["canonical_player_name"].eq(""), "canonical_player_name"] = combined["display_player_name"].fillna("").astype(str).str.strip()
    combined.loc[combined["canonical_player_name"].eq(""), "canonical_player_name"] = combined["player_name"].fillna("").astype(str).str.strip()
    combined.loc[combined["canonical_player_id"].eq(""), "canonical_player_id"] = combined["player_id"].fillna("").astype(str).str.strip()
    return combined[["canonical_player_id", "canonical_player_name"]].drop_duplicates().sort_values("canonical_player_name")


def source_has_player_match(path: Path, match_id: str, player_name: str) -> bool:
    frame = read_csv(path)
    if frame.empty or "match_id" not in frame:
        return False
    return frame["match_id"].astype(str).eq(str(match_id)).any() and player_mask(frame, player_name).any()


def profile_for_player(app_bowling: pd.DataFrame, player_name: str) -> tuple[dict[str, object] | None, dict[str, pd.DataFrame]]:
    row = player_row(app_bowling, player_name)
    if row is None:
        return None, {}
    profile = get_player_profile_data(
        row.get("canonical_player_id"),
        metadata_mtime(),
        player_aliases_mtime(),
        club_id="fvcc",
    )
    if profile is None:
        return None, {}
    return profile, build_player_profile_view(profile, player_profile_view_signature())


def winter_profile_row(view: dict[str, pd.DataFrame]) -> pd.Series | None:
    table = view.get("season_table", pd.DataFrame())
    if table.empty or "Season" not in table:
        return None
    scoped = table[table["Season"].astype(str).eq("Winter 2026")]
    return scoped.iloc[0] if not scoped.empty else None


def grade_winter_row(view: dict[str, pd.DataFrame]) -> pd.Series | None:
    table = view.get("grade_table", pd.DataFrame())
    if table.empty:
        return None
    if "Grade" not in table:
        return None
    scoped = table[table["Grade"].astype(str).str.contains("North Division", case=False, na=False)]
    return scoped.iloc[0] if not scoped.empty else None


def write_summary(rows: list[dict[str, object]], context: dict[str, object]) -> None:
    failures = [row for row in rows if row["status"] != "pass"]
    lines = [
        "# FVCC latest refresh consistency summary",
        "",
        f"- generated_at: {datetime.now(UTC).isoformat()}",
        f"- latest_match_id: {context.get('match_id', '')}",
        f"- latest_match_date: {context.get('match_date', '')}",
        f"- round: {context.get('round', '')}",
        f"- opponent: {context.get('opponent', '')}",
        f"- result: {context.get('result', '')}",
        f"- players_validated: {context.get('players_validated', 0)}",
        f"- checks: {len(rows)}",
        f"- failures: {len(failures)}",
        f"- validator_status: {'pass' if not failures else 'fail'}",
    ]
    if failures:
        lines.append("")
        lines.append("## Failures")
        lines.extend(f"- {row['check_name']}: {row.get('player', '')} actual={row.get('actual', '')} expected={row.get('expected', '')}" for row in failures[:30])
    SUMMARY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_version_marker(context: dict[str, object], status: str, checks: int, failures: int) -> None:
    VERSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "club_id": "fvcc",
        "latest_refresh_timestamp": datetime.now(UTC).isoformat(),
        "latest_match_id": context.get("match_id", ""),
        "latest_match_date": context.get("match_date", ""),
        "latest_match_round": context.get("round", ""),
        "latest_match_opponent": context.get("opponent", ""),
        "latest_match_result": context.get("result", ""),
        "source_data_mtime": metadata_mtime(),
        "generated_app_facing_data_version": datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        "validator_status": status,
        "validator_checks": checks,
        "validator_failures": failures,
    }
    VERSION_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    rows: list[dict[str, object]] = []
    latest = latest_match_row()
    add(rows, "latest_winter_2026_match_detected", latest is not None, source="season_by_round_scorecards.csv")
    if latest is None:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
        write_summary(rows, {})
        return 1

    match_id = clean(latest.get("match_id"))
    match_date = clean(latest.get("match_date"))
    opponent = clean(latest.get("opponent_name") or latest.get("opponent"))
    result = clean(latest.get("result_text") or latest.get("result"))
    round_label = clean(latest.get("round_display") or latest.get("round_name"))
    season_id = clean(latest.get("season_id"))
    team_id = clean(latest.get("fvcc_team_id") or latest.get("club_team_id"))
    context = {
        "match_id": match_id,
        "match_date": match_date,
        "opponent": opponent,
        "result": result,
        "round": round_label,
    }

    add(rows, "latest_match_is_r7", round_label in {"R7", "Round 7", "7"}, expected="R7", actual=round_label, source="season_by_round_scorecards.csv")
    add(rows, "latest_match_scorecard_batting_exists", source_has_player_match(MATCH_CENTRE / "all_scorecard_batting.csv", match_id, "Siddhanth Chaurasiya"), player="Siddhanth Chaurasiya", source="all_scorecard_batting.csv")
    add(rows, "latest_match_scorecard_bowling_exists", source_has_player_match(MATCH_CENTRE / "all_scorecard_bowling.csv", match_id, "Siddhanth Chaurasiya"), player="Siddhanth Chaurasiya", source="all_scorecard_bowling.csv")
    bbb = read_csv(MATCH_CENTRE / "all_ball_by_ball.csv")
    add(rows, "latest_match_ball_by_ball_exists", not bbb.empty and "match_id" in bbb and bbb["match_id"].astype(str).eq(match_id).any(), actual=int(bbb[bbb["match_id"].astype(str).eq(match_id)].shape[0]) if not bbb.empty and "match_id" in bbb else 0, source="all_ball_by_ball.csv")

    players = latest_match_players(match_id, team_id)
    context["players_validated"] = int(players.shape[0])
    add(rows, "latest_match_players_detected", not players.empty, expected="players > 0", actual=int(players.shape[0]), source="scorecard rows")

    aggregate_batting = winter_rows(read_processed_table("all_seasons_batting"))
    aggregate_bowling = winter_rows(read_processed_table("all_seasons_bowling"))
    aggregate_fielding = winter_rows(read_processed_table("all_seasons_fielding"))
    app_batting = load_local_category_frame("fvcc", "batting", season_id, team_id, metadata_mtime(), player_aliases_mtime())
    app_bowling = load_local_category_frame("fvcc", "bowling", season_id, team_id, metadata_mtime(), player_aliases_mtime())
    app_fielding = load_local_category_frame("fvcc", "fielding", season_id, team_id, metadata_mtime(), player_aliases_mtime())

    for _, player in players.iterrows():
        player_name = clean(player.get("canonical_player_name"))
        if not player_name or player_name == "********":
            continue
        has_any_aggregate = any(player_row(frame, player_name) is not None for frame in [aggregate_batting, aggregate_bowling, aggregate_fielding])
        has_any_app_detail = any(player_row(frame, player_name) is not None for frame in [app_batting, app_bowling, app_fielding])
        add(rows, "latest_player_in_player_season_aggregates", has_any_aggregate, player=player_name, expected="present", actual=has_any_aggregate, source="all_seasons_*")
        add(rows, "latest_player_in_season_overview_detailed_stats", has_any_app_detail, player=player_name, expected="present", actual=has_any_app_detail, source="load_local_category_frame")

    expected = EXPECTED["Siddhanth Chaurasiya"]
    sid_aggregate = player_row(aggregate_bowling, "Siddhanth Chaurasiya")
    sid_app = player_row(app_bowling, "Siddhanth Chaurasiya")
    sid_profile, sid_view = profile_for_player(app_bowling, "Siddhanth Chaurasiya")
    sid_season = winter_profile_row(sid_view)
    sid_grade = grade_winter_row(sid_view)

    for layer, row, match_col, wicket_col, source in [
        ("player_season", sid_aggregate, "matches", "bowlingWickets", "all_seasons_bowling.csv"),
        ("season_overview_detailed_stats", sid_app, "matches", "bowlingWickets", "load_local_category_frame"),
        ("player_profile_career_breakdown", sid_season, "Matches", "Wickets", "build_player_profile_view"),
        ("player_profile_competition_grade", sid_grade, "Matches", "Wickets", "build_player_profile_view"),
    ]:
        matches = int_number(row.get(match_col)) if row is not None else 0
        wickets = int_number(row.get(wicket_col)) if row is not None else 0
        if layer == "player_profile_competition_grade":
            # The Competition/Grade card is intentionally all-time within the grade,
            # so it must include Winter 2026 rather than equal the season-only row.
            add(rows, f"siddhanth_{layer}_matches", matches >= expected["matches"], player="Siddhanth Chaurasiya", expected=f">={expected['matches']}", actual=matches, source=source)
            add(rows, f"siddhanth_{layer}_wickets", wickets >= expected["bowlingWickets"], player="Siddhanth Chaurasiya", expected=f">={expected['bowlingWickets']}", actual=wickets, source=source)
        else:
            add(rows, f"siddhanth_{layer}_matches", matches == expected["matches"], player="Siddhanth Chaurasiya", expected=expected["matches"], actual=matches, source=source)
            add(rows, f"siddhanth_{layer}_wickets", wickets == expected["bowlingWickets"], player="Siddhanth Chaurasiya", expected=expected["bowlingWickets"], actual=wickets, source=source)

    add(rows, "siddhanth_no_stale_winter_profile_values", sid_season is not None and int_number(sid_season.get("Matches")) not in {5, 6} and int_number(sid_season.get("Wickets")) not in {8, 10}, player="Siddhanth Chaurasiya", expected="not 5/8 or 6/10", actual=f"Mat={int_number(sid_season.get('Matches')) if sid_season is not None else 'missing'} W={int_number(sid_season.get('Wickets')) if sid_season is not None else 'missing'}", source="Player Profile season table")

    recent_bowling = read_csv(PROCESSED / "player_profile" / "recent_form_bowling.csv")
    recent_has_latest = not recent_bowling.empty and player_mask(recent_bowling, "Siddhanth Chaurasiya").any() and recent_bowling.loc[player_mask(recent_bowling, "Siddhanth Chaurasiya"), "match_id"].astype(str).eq(match_id).any()
    recent_first = ""
    if not recent_bowling.empty and player_mask(recent_bowling, "Siddhanth Chaurasiya").any():
        recent_first = clean(recent_bowling.loc[player_mask(recent_bowling, "Siddhanth Chaurasiya")].head(1).iloc[0].get("display_value"))
    add(rows, "siddhanth_recent_form_latest_match", recent_has_latest and recent_first == "1/10", player="Siddhanth Chaurasiya", expected="1/10", actual=recent_first, source="recent_form_bowling.csv")

    if sid_view:
        add(rows, "player_dna_batting_position_current", not sid_view.get("batting_position", pd.DataFrame()).empty, player="Siddhanth Chaurasiya", source="batting_position_summary.csv")
        phase = sid_view.get("bowling_phase", pd.DataFrame())
        phase_wickets = int(numeric(phase.get("wickets", pd.Series(dtype=float)).sum())) if not phase.empty else 0
        add(rows, "player_dna_bowling_phase_current", phase_wickets >= expected["bowlingWickets"], player="Siddhanth Chaurasiya", expected=f">={expected['bowlingWickets']}", actual=phase_wickets, source="bowling_phase_summary.csv")
        add(rows, "player_dna_dismissal_fingerprint_current", not sid_view.get("dismissal_fingerprint", pd.DataFrame()).empty, player="Siddhanth Chaurasiya", source="dismissal_fingerprint_summary.csv")
        seasons = tuple(sorted(sid_view.get("season_table", pd.DataFrame()).get("Season", pd.Series(dtype="object")).dropna().astype(str).unique()))
        career = sid_view.get("career", pd.DataFrame())
        player_id = clean(career.iloc[0].get("canonical_player_id")) if not career.empty else ""
        peers = get_player_peer_comparison(player_id, seasons, player_peer_grade_scope(sid_view), metadata_mtime(), player_aliases_mtime(), "fvcc")
        add(rows, "player_vs_peers_latest_data", bool(peers.get("batting")) and bool(peers.get("bowling")), player="Siddhanth Chaurasiya", actual=f"batting={len(peers.get('batting', []))}; bowling={len(peers.get('bowling', []))}", source="get_player_peer_comparison")
        rendered_recent = build_player_recent_form(career.iloc[0]) if not career.empty else {"bowling": []}
        labels = [str(item.get("label", "")) for item in rendered_recent.get("bowling", [])]
        add(rows, "rendered_recent_form_latest_match", "1/10" in labels, player="Siddhanth Chaurasiya", expected="1/10", actual=" | ".join(labels[:5]), source="build_player_recent_form")

    for metric, column, expected_value in [
        ("bowling_average", "bowlingAverage", 17.64),
        ("bowling_economy", "bowlingEconomyRate", 4.95),
        ("extras_inputs", "bowlingWides", None),
    ]:
        if metric == "extras_inputs":
            wides = numeric(sid_app.get("bowlingWides")) if sid_app is not None else 0.0
            no_balls = numeric(sid_app.get("bowlingNoBalls")) if sid_app is not None else 0.0
            actual = wides + no_balls
            add(rows, "derived_extras_inputs_refreshed", actual > 0, player="Siddhanth Chaurasiya", expected="wides+no_balls > 0", actual=round(actual, 2), source="Season Overview bowling")
        elif sid_aggregate is not None:
            actual = round(numeric(sid_aggregate.get(column)), 2)
            add(rows, f"derived_{metric}_refreshed", abs(actual - expected_value) < 0.05, player="Siddhanth Chaurasiya", expected=expected_value, actual=actual, source="all_seasons_bowling.csv")

    top_bowler = app_bowling.sort_values("bowlingWickets", ascending=False).iloc[0] if not app_bowling.empty and "bowlingWickets" in app_bowling else None
    add(rows, "siddhanth_season_standouts_wickets", top_bowler is not None and clean(top_bowler.get("canonical_player_name") or top_bowler.get("player_name")) == "Siddhanth Chaurasiya" and int_number(top_bowler.get("bowlingWickets")) == expected["bowlingWickets"], player="Siddhanth Chaurasiya", expected=expected["bowlingWickets"], actual=int_number(top_bowler.get("bowlingWickets")) if top_bowler is not None else "missing", source="Season Standouts source")
    add(rows, "siddhanth_team_grade_leaders_wickets", top_bowler is not None and int_number(top_bowler.get("bowlingWickets")) == expected["bowlingWickets"], player="Siddhanth Chaurasiya", expected=expected["bowlingWickets"], actual=int_number(top_bowler.get("bowlingWickets")) if top_bowler is not None else "missing", source="Team/Grade Leaders source")

    hof = get_hall_of_fame_data(metadata_mtime(), player_aliases_mtime(), HALL_OF_FAME_DATA_VERSION, featured_record_overrides_mtime(), club_id="fvcc")
    all_time = hof.get("all_time", pd.DataFrame()) if isinstance(hof, dict) else pd.DataFrame()
    hof_row = player_row(all_time, "Siddhanth Chaurasiya")
    hof_matches = int_number(hof_row.get("Matches")) if hof_row is not None else 0
    hof_wickets = int_number(hof_row.get("Wickets")) if hof_row is not None else 0
    add(rows, "siddhanth_hof_career_matches_current", hof_matches >= 60, player="Siddhanth Chaurasiya", expected=">=60", actual=hof_matches, source="get_hall_of_fame_data")
    add(rows, "siddhanth_hof_career_wickets_current", hof_wickets >= 54, player="Siddhanth Chaurasiya", expected=">=54", actual=hof_wickets, source="get_hall_of_fame_data")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT_PATH, index=False)
    failures = [row for row in rows if row["status"] != "pass"]
    status = "pass" if not failures else "fail"
    write_summary(rows, context)
    write_version_marker(context, status, len(rows), len(failures))
    print(f"validation_status={status} checks={len(rows)} failed={len(failures)}")
    print(
        "latest_match="
        f"round={round_label} date={match_date} opponent={opponent} result={result} match_id={match_id}"
    )
    print(f"players_validated={context['players_validated']}")
    print(f"Siddhanth: SO Mat={int_number(sid_app.get('matches')) if sid_app is not None else 'missing'} W={int_number(sid_app.get('bowlingWickets')) if sid_app is not None else 'missing'}; HOF Matches={hof_matches} Wickets={hof_wickets}")
    if failures:
        print("failed_checks=" + ",".join(row["check_name"] for row in failures))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
