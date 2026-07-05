#!/usr/bin/env python3
"""Audit GWHCC PlayHQ/PlayCricket season coverage and match-count policy inputs."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_match_policy import (  # noqa: E402
    CLUB_ID,
    MATCH_CENTRE,
    PROCESSED,
    build_match_policy_table,
    load_policy_frames,
    player_season_weights,
    read_csv,
)

OUTPUT_CSV = PROCESSED / "validation" / "gwhcc_playhq_season_coverage_audit.csv"
OUTPUT_MD = PROCESSED / "validation" / "gwhcc_playhq_season_coverage_summary.md"


def pct(numerator: float, denominator: float) -> float:
    return round(numerator * 100 / denominator, 2) if denominator else 0.0


def unique_join(values: pd.Series, limit: int = 12) -> str:
    cleaned = sorted({str(value).strip() for value in values.dropna() if str(value).strip()})
    if len(cleaned) > limit:
        return "; ".join(cleaned[:limit]) + f"; +{len(cleaned) - limit} more"
    return "; ".join(cleaned)


def season_start_year(season: object) -> int | str:
    text = str(season)
    for token in text.replace("/", " ").split():
        if token.isdigit() and len(token) == 4:
            return int(token)
    return ""


def main() -> int:
    frames = load_policy_frames()
    policy = build_match_policy_table(frames)
    weights = player_season_weights(policy)
    batting = frames["batting"].copy()
    bowling = frames["bowling"].copy()
    fielding = frames["fielding"].copy()
    balls = frames["balls"].copy()
    teams = frames["teams"].copy()
    players = frames["players"].copy()
    app_profile = read_csv(PROCESSED / "player_profile" / "performance_breakdown_by_dimension.csv")

    if policy.empty:
        raise SystemExit("No GWHCC match policy rows could be built.")

    for frame in [batting, bowling, fielding, balls]:
        if not frame.empty and "match_id" in frame:
            frame["match_id"] = frame["match_id"].astype(str)

    team_counts = (
        teams.groupby("season", dropna=False)
        .agg(
            teams_count=("team_id", "nunique"),
            team_names=("team_name", unique_join),
            grades_count=("grade_id", "nunique"),
            grade_names=("grade_name", unique_join),
        )
        .reset_index()
        if not teams.empty
        else pd.DataFrame(columns=["season", "teams_count", "team_names", "grades_count", "grade_names"])
    )

    player_counts = (
        weights.groupby("season", dropna=False)
        .agg(players_count=("player_id", "nunique"))
        .reset_index()
        if not weights.empty
        else pd.DataFrame(columns=["season", "players_count"])
    )

    profile_counts = (
        app_profile.groupby("breakdown_label", dropna=False)
        .agg(players_with_player_profile=("canonical_player_id", "nunique"))
        .reset_index()
        .rename(columns={"breakdown_label": "season"})
        if not app_profile.empty and {"breakdown_label", "canonical_player_id"}.issubset(app_profile.columns)
        else pd.DataFrame(columns=["season", "players_with_player_profile"])
    )

    rows = []
    for season, group in policy.groupby("season", dropna=False):
        match_ids = set(group["match_id"].astype(str))
        bat = batting[batting["match_id"].astype(str).isin(match_ids)] if not batting.empty else pd.DataFrame()
        bowl = bowling[bowling["match_id"].astype(str).isin(match_ids)] if not bowling.empty else pd.DataFrame()
        field = fielding[fielding["match_id"].astype(str).isin(match_ids)] if not fielding.empty else pd.DataFrame()
        bbb = balls[balls["match_id"].astype(str).isin(match_ids)] if not balls.empty else pd.DataFrame()
        matches_total = int(group["match_id"].nunique())
        scorecard_match_ids = set(bat.get("match_id", pd.Series(dtype=str)).astype(str)) | set(
            bowl.get("match_id", pd.Series(dtype=str)).astype(str)
        ) | set(field.get("match_id", pd.Series(dtype=str)).astype(str))
        no_play = int(group["is_no_play"].sum())
        t20 = int(group["detected_match_format"].eq("T20").sum())
        weighted_total = round(float(group["match_weight"].sum()), 2)
        gap_notes = []
        if no_play:
            gap_notes.append(f"{no_play} no-play/no-activity matches excluded")
        missing_scorecards = matches_total - len(scorecard_match_ids)
        if missing_scorecards:
            gap_notes.append(f"{missing_scorecards} matches without scorecard rows")
        unknown_formats = int(group["detected_match_format"].eq("Unknown").sum())
        if unknown_formats:
            gap_notes.append(f"{unknown_formats} played/known matches have unknown format")
        review_required = int(group["review_required"].sum())
        if review_required:
            gap_notes.append(f"{review_required} matches need scorecard/no-play review")
        rows.append(
            {
                "season": season,
                "season_start_year": season_start_year(season),
                "teams_count": 0,
                "team_names": "",
                "grades_count": int(group["grade_id"].nunique()),
                "grade_names": unique_join(group["grade_name"]),
                "matches_total_playhq": matches_total,
                "matches_with_scorecards": len(scorecard_match_ids),
                "matches_with_batting_rows": int(bat["match_id"].nunique()) if not bat.empty else 0,
                "matches_with_bowling_rows": int(bowl["match_id"].nunique()) if not bowl.empty else 0,
                "matches_with_fielding_rows": int(field["match_id"].nunique()) if not field.empty else 0,
                "matches_with_bbb": int(bbb["match_id"].nunique()) if not bbb.empty else 0,
                "matches_without_scorecard": missing_scorecards,
                "matches_no_play": no_play,
                "matches_forfeit_or_abandoned_no_ball": int((group["status_no_play_signal"] & group["is_no_play"]).sum()),
                "matches_t20": t20,
                "matches_non_t20": int((~group["detected_match_format"].eq("T20") & ~group["is_no_play"]).sum()),
                "weighted_matches_total": weighted_total,
                "players_count": 0,
                "players_with_batting": int(bat["participant_id"].nunique()) if not bat.empty else 0,
                "players_with_bowling": int(bowl["participant_id"].nunique()) if not bowl.empty else 0,
                "players_with_fielding": int(field["participant_id"].nunique()) if not field.empty else 0,
                "players_with_player_profile": 0,
                "earliest_match_date": str(pd.to_datetime(group["first_match_day"], errors="coerce", utc=True).min().date()),
                "latest_match_date": str(pd.to_datetime(group["first_match_day"], errors="coerce", utc=True).max().date()),
                "total_innings_rows": int(group["innings_rows"].sum()),
                "total_overs_balls_detected": int(group["total_balls_detected"].sum()),
                "total_runs": int(group["innings_runs"].sum()),
                "total_wickets": int(group["innings_wickets"].sum()),
                "unique_opponents": int(
                    pd.concat([group.get("home_team_name", pd.Series(dtype=str)), group.get("away_team_name", pd.Series(dtype=str))])
                    .dropna()
                    .astype(str)
                    .nunique()
                ),
                "unique_grounds": int(group["venue_name"].nunique()) if "venue_name" in group else 0,
                "unique_competitions_grades": int(group["grade_name"].nunique()) if "grade_name" in group else 0,
                "scorecard_coverage_pct": pct(len(scorecard_match_ids), matches_total),
                "bbb_coverage_pct": pct(int(bbb["match_id"].nunique()) if not bbb.empty else 0, matches_total),
                "finals_count": int(group["round_name"].fillna("").astype(str).str.contains("final", case=False).sum())
                if "round_name" in group
                else 0,
                "matches_with_missing_result": int(group["result_text"].fillna("").astype(str).str.strip().isin(["", "Result pending"]).sum()),
                "matches_selected_squad_no_play": no_play,
                "data_quality_status": "review_required" if review_required or unknown_formats else "pass_with_gaps" if gap_notes else "pass",
                "gap_notes": "; ".join(gap_notes) if gap_notes else "No material PlayHQ coverage gaps detected for this season.",
            }
        )

    audit = pd.DataFrame(rows).sort_values(["season_start_year", "season"], na_position="last")
    audit = audit.merge(team_counts, on="season", how="left", suffixes=("", "_team"))
    for column in ["teams_count", "team_names", "grades_count", "grade_names"]:
        team_column = f"{column}_team"
        if team_column in audit:
            audit[column] = audit[team_column].combine_first(audit[column])
            audit = audit.drop(columns=[team_column])
    audit = audit.merge(player_counts, on="season", how="left", suffixes=("", "_weighted"))
    if "players_count_weighted" in audit:
        audit["players_count"] = audit["players_count_weighted"].combine_first(audit["players_count"])
        audit = audit.drop(columns=["players_count_weighted"])
    audit = audit.merge(profile_counts, on="season", how="left", suffixes=("", "_profile"))
    if "players_with_player_profile_profile" in audit:
        audit["players_with_player_profile"] = audit["players_with_player_profile_profile"].combine_first(audit["players_with_player_profile"])
        audit = audit.drop(columns=["players_with_player_profile_profile"])
    for column in ["teams_count", "grades_count", "players_count", "players_with_player_profile"]:
        audit[column] = pd.to_numeric(audit[column], errors="coerce").fillna(0).astype(int)
    for column in ["team_names", "grade_names"]:
        audit[column] = audit[column].fillna("")

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(OUTPUT_CSV, index=False)
    write_summary(audit)
    print(f"coverage_status=pass seasons={len(audit)} output={OUTPUT_CSV}")
    print(f"summary={OUTPUT_MD}")
    return 0


def write_summary(audit: pd.DataFrame) -> None:
    totals = {
        "seasons": len(audit),
        "teams": int(audit["teams_count"].sum()),
        "matches": int(audit["matches_total_playhq"].sum()),
        "scorecards": int(audit["matches_with_scorecards"].sum()),
        "bbb": int(audit["matches_with_bbb"].sum()),
        "players": int(audit["players_count"].max()) if not audit.empty else 0,
        "no_play": int(audit["matches_no_play"].sum()),
        "t20": int(audit["matches_t20"].sum()),
        "weighted": round(float(audit["weighted_matches_total"].sum()), 2),
    }
    lines = [
        "# GWHCC PlayHQ Season Coverage Audit",
        "",
        f"- Club ID: `{CLUB_ID}`",
        f"- Source: `{MATCH_CENTRE}`",
        f"- Seasons audited: {totals['seasons']}",
        f"- Total matches: {totals['matches']}",
        f"- Matches with scorecards: {totals['scorecards']}",
        f"- Matches with BBB: {totals['bbb']}",
        f"- No-play matches excluded by policy: {totals['no_play']}",
        f"- T20 matches half-counted by policy: {totals['t20']}",
        f"- Weighted match total: {totals['weighted']}",
        "",
        "| Season | Teams | Matches | Played | No-play | T20 | Weighted | Scorecard % | BBB % | Players | Gap notes |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in audit.itertuples(index=False):
        played = int(row.matches_total_playhq - row.matches_no_play)
        lines.append(
            f"| {row.season} | {row.teams_count} | {row.matches_total_playhq} | {played} | "
            f"{row.matches_no_play} | {row.matches_t20} | {row.weighted_matches_total:g} | "
            f"{row.scorecard_coverage_pct:g}% | {row.bbb_coverage_pct:g}% | {row.players_count} | {row.gap_notes} |"
        )
    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
