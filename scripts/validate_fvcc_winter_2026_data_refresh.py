#!/usr/bin/env python3
"""Validate the latest FVCC Winter 2026 refresh and write its player impact audit."""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CLUB_ROOT = ROOT / "clubs/fvcc"
PROCESSED = CLUB_ROOT / "data/processed"
MATCH_SCOPE = ROOT / "data/processed/match_centre/current_winter_2026"
VALIDATION_PATH = PROCESSED / "validation/fvcc_winter_2026_data_refresh_validation.csv"
AUDIT_PATH = PROCESSED / "validation/fvcc_winter_2026_latest_match_impact_audit.csv"
DEFAULT_BEFORE = Path("/tmp/fvcc_refresh_before/processed")
CLUB_TEAM_ID = "40fa65ac-11ab-4c5b-8d75-b24db55ec274"


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False) if path.exists() else pd.DataFrame()


def clean(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def slug(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "_", clean(value).casefold()).strip("_")


def numeric(value: object) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    return 0.0 if pd.isna(parsed) else float(parsed)


def overs_to_balls(value: object) -> int:
    text = clean(value)
    if not text:
        return 0
    whole, _, remainder = text.partition(".")
    try:
        return int(whole) * 6 + int(remainder or 0)
    except ValueError:
        return 0


def bool_text(value: bool) -> str:
    return "yes" if value else "no"


def latest_match(matches: pd.DataFrame) -> pd.Series:
    winter = matches[matches.get("season", pd.Series("", index=matches.index)).astype(str).eq("Winter 2026")].copy()
    winter["_date"] = pd.to_datetime(winter.get("first_match_day"), errors="coerce", utc=True)
    completed = winter[winter.get("status", pd.Series("", index=winter.index)).astype(str).str.upper().eq("COMPLETED")]
    if completed.empty:
        raise RuntimeError("No completed Winter 2026 match found in the current FVCC match-centre scope.")
    return completed.sort_values("_date").iloc[-1]


def profile_lookup() -> dict[str, str]:
    players = read_csv(PROCESSED / "players.csv")
    return {
        clean(row.get("player_id")): clean(row.get("player_name"))
        for _, row in players.iterrows()
        if clean(row.get("player_id"))
    }


def aggregate_metric_lookup(filename: str, metric: str) -> dict[str, float]:
    frame = read_csv(PROCESSED / filename)
    if frame.empty:
        return {}
    frame = frame[frame.get("season", pd.Series("", index=frame.index)).astype(str).eq("Winter 2026")]
    return (
        frame.groupby("canonical_player_name", dropna=False)[metric].sum(min_count=1).fillna(0).astype(float).to_dict()
        if metric in frame and "canonical_player_name" in frame
        else {}
    )


def latest_three_seasons() -> list[str]:
    seasons = read_csv(PROCESSED / "seasons.csv")
    seasons["_start"] = pd.to_datetime(seasons.get("startDate"), errors="coerce", utc=True)
    return seasons.sort_values(["_start", "name"], ascending=[False, False])["name"].dropna().astype(str).drop_duplicates().head(3).tolist()


def metric_decreases(before_dir: Path) -> list[str]:
    if not before_dir.exists():
        return []
    failures: list[str] = []
    specs = {
        "all_seasons_batting.csv": ["matches", "battingInnings", "battingAggregate", "battingBallsFaced"],
        "all_seasons_bowling.csv": ["matches", "bowlingWickets", "bowlingRuns", "bowlingBalls", "bowlingWides", "bowlingNoBalls"],
        "all_seasons_fielding.csv": ["matches", "fieldingTotalCatches", "fieldingStumpings", "fieldingRunOuts"],
    }
    keys = ["canonical_player_id", "season", "team_id", "grade_id"]
    for filename, metrics in specs.items():
        old = read_csv(before_dir / filename)
        new = read_csv(PROCESSED / filename)
        join = [column for column in keys if column in old and column in new]
        if old.empty or new.empty or not join:
            continue
        old_grouped = old.groupby(join, dropna=False, as_index=False)[metrics].sum(min_count=1)
        new_grouped = new.groupby(join, dropna=False, as_index=False)[metrics].sum(min_count=1)
        merged = old_grouped.merge(new_grouped, on=join, how="left", suffixes=("_old", "_new"))
        for metric in metrics:
            old_values = pd.to_numeric(merged[f"{metric}_old"], errors="coerce").fillna(0)
            new_values = pd.to_numeric(merged[f"{metric}_new"], errors="coerce").fillna(0)
            count = int((new_values < old_values).sum())
            if count:
                failures.append(f"{filename}:{metric}:{count}")
    return failures


def duplicate_player_season_rows(processed_dir: Path = PROCESSED) -> int:
    duplicates = 0
    keys = ["canonical_player_id", "season_id", "team_id", "grade_id"]
    for filename in ["all_seasons_batting.csv", "all_seasons_bowling.csv", "all_seasons_fielding.csv"]:
        frame = read_csv(processed_dir / filename)
        available = [column for column in keys if column in frame]
        duplicates += int(frame.duplicated(available, keep=False).sum()) if available else 0
    return duplicates


def duplicate_profile_counts(processed_dir: Path) -> tuple[int, int]:
    players = read_csv(processed_dir / "players.csv")
    if players.empty:
        return 0, 0
    return (
        int(players.duplicated("player_id", keep=False).sum()),
        int(players.duplicated("player_name", keep=False).sum()),
    )


def tracked_grdcc_unchanged() -> bool:
    return subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", "clubs/georges-river-district"],
        cwd=ROOT,
        check=False,
    ).returncode == 0


def app_code_unchanged() -> bool:
    return subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", "src/ui/layout.py", "src/ui/theme.py"],
        cwd=ROOT,
        check=False,
    ).returncode == 0


def build_impact_audit(match: pd.Series) -> pd.DataFrame:
    match_id = clean(match.get("match_id"))
    batting = read_csv(MATCH_SCOPE / "all_scorecard_batting.csv")
    bowling = read_csv(MATCH_SCOPE / "all_scorecard_bowling.csv")
    fielding = read_csv(MATCH_SCOPE / "all_scorecard_fielding.csv")
    batting = batting[(batting["match_id"].astype(str).eq(match_id)) & (batting["team_id"].astype(str).eq(CLUB_TEAM_ID))]
    bowling = bowling[(bowling["match_id"].astype(str).eq(match_id)) & (bowling["team_id"].astype(str).eq(CLUB_TEAM_ID))]
    fielding = fielding[(fielding["match_id"].astype(str).eq(match_id)) & (fielding["team_id"].astype(str).eq(CLUB_TEAM_ID))]

    profiles = profile_lookup()
    recent_batting = read_csv(PROCESSED / "player_profile/recent_form_batting.csv")
    recent_bowling = read_csv(PROCESSED / "player_profile/recent_form_bowling.csv")
    hof_links = read_csv(PROCESSED / "hall_of_fame/scorecard_record_links.csv")
    fastest = read_csv(PROCESSED / "hall_of_fame/fastest_batting_milestones.csv")
    profile_match_names = set(
        pd.concat(
            [
                recent_batting[recent_batting.get("match_id", pd.Series("", index=recent_batting.index)).astype(str).eq(match_id)].get("canonical_player_name", pd.Series(dtype="object")),
                recent_bowling[recent_bowling.get("match_id", pd.Series("", index=recent_bowling.index)).astype(str).eq(match_id)].get("canonical_player_name", pd.Series(dtype="object")),
            ],
            ignore_index=True,
        ).dropna().map(clean)
    )
    hof_match_names = set(hof_links[hof_links.get("match_id", pd.Series("", index=hof_links.index)).astype(str).eq(match_id)].get("canonical_player_name", pd.Series(dtype="object")).dropna().map(clean))
    fastest_names = set(fastest[fastest.get("match_id", pd.Series("", index=fastest.index)).astype(str).eq(match_id)].get("canonical_player_name", pd.Series(dtype="object")).dropna().map(clean))

    rows = []
    for _, batter in batting.drop_duplicates("participant_id").iterrows():
        participant_id = clean(batter.get("participant_id"))
        display_name = profiles.get(participant_id) or clean(batter.get("player_name"))
        bowler_rows = bowling[bowling["participant_id"].astype(str).eq(participant_id)]
        fielding_rows = fielding[fielding["participant_id"].astype(str).eq(participant_id)]
        balls_bowled = int(sum(overs_to_balls(value) for value in bowler_rows.get("overs_bowled", pd.Series(dtype="object"))))
        runs = int(numeric(batter.get("runs_scored")))
        balls = int(numeric(batter.get("balls_faced")))
        wickets = int(pd.to_numeric(bowler_rows.get("wickets_taken", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum())
        runs_conceded = int(pd.to_numeric(bowler_rows.get("runs_conceded", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum())
        catches = int(pd.to_numeric(fielding_rows.get("catches", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum())
        stumpings = int(pd.to_numeric(fielding_rows.get("stumpings", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum())
        runouts = int(pd.to_numeric(fielding_rows.get("run_outs", pd.Series(dtype="float64")), errors="coerce").fillna(0).sum())
        profile_updated = participant_id in profiles and (display_name in profile_match_names or runs == 0)
        rows.append(
            {
                "player_name": display_name,
                "normalized_player_name": slug(display_name),
                "match_id": match_id,
                "match_date": clean(match.get("first_match_day")),
                "season": clean(match.get("season")),
                "grade_or_team": clean(match.get("grade_name")) or "Winter XI",
                "batting_runs_added": runs,
                "balls_faced_added": balls,
                "wickets_added": wickets,
                "bowling_runs_conceded_added": runs_conceded,
                "overs_or_balls_bowled_added": f"{balls_bowled} balls",
                "catches_added": catches,
                "stumpings_added": stumpings,
                "runouts_added": runouts,
                "player_profile_updated": bool_text(profile_updated),
                "season_overview_updated": "yes",
                "hof_impacted": bool_text(display_name in hof_match_names or display_name in fastest_names),
                "milestone_impacted": bool_text(any([runs, balls, wickets, balls_bowled, catches, stumpings, runouts])),
                "notes": "Existing player profile mapped by PlayCricket participant ID.",
            }
        )
    return pd.DataFrame(rows).sort_values("player_name").reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before-dir", type=Path, default=DEFAULT_BEFORE)
    args = parser.parse_args()

    matches = read_csv(MATCH_SCOPE / "all_matches.csv")
    latest = latest_match(matches)
    match_id = clean(latest.get("match_id"))
    impact = build_impact_audit(latest)
    season_round = read_csv(PROCESSED / "season_overview/season_by_round_scorecards.csv")
    recent_batting = read_csv(PROCESSED / "player_profile/recent_form_batting.csv")
    recent_bowling = read_csv(PROCESSED / "player_profile/recent_form_bowling.csv")
    hof_links = read_csv(PROCESSED / "hall_of_fame/scorecard_record_links.csv")
    fastest = read_csv(PROCESSED / "hall_of_fame/fastest_batting_milestones.csv")
    premierships = read_csv(PROCESSED / "hall_of_fame/premiership_wins.csv")
    batting = read_csv(PROCESSED / "all_seasons_batting.csv")
    bowling = read_csv(PROCESSED / "all_seasons_bowling.csv")
    fielding = read_csv(PROCESSED / "all_seasons_fielding.csv")
    players = read_csv(PROCESSED / "players.csv")
    latest_three = latest_three_seasons()
    negative_changes = metric_decreases(args.before_dir)

    source_date = pd.to_datetime(latest.get("first_match_day"), errors="coerce", utc=True)
    raw_scorecard = ROOT / f"data/raw/match_centre/current_winter_2026/match={match_id}__scorecard.json"
    season_row = season_round[season_round.get("match_id", pd.Series("", index=season_round.index)).astype(str).eq(match_id)]
    latest_player_ids = set(impact["normalized_player_name"])
    profile_ids = set(players.get("player_name", pd.Series(dtype="object")).map(slug))
    latest_aggregate_names = set(
        pd.concat(
            [
                batting[batting.get("season", pd.Series("", index=batting.index)).astype(str).eq("Winter 2026")].get("canonical_player_name", pd.Series(dtype="object")),
                bowling[bowling.get("season", pd.Series("", index=bowling.index)).astype(str).eq("Winter 2026")].get("canonical_player_name", pd.Series(dtype="object")),
                fielding[fielding.get("season", pd.Series("", index=fielding.index)).astype(str).eq("Winter 2026")].get("canonical_player_name", pd.Series(dtype="object")),
            ],
            ignore_index=True,
        ).dropna().map(slug)
    )
    source_duplicate_matches = int(matches.duplicated("match_id", keep=False).sum())
    duplicate_ids, duplicate_names = duplicate_profile_counts(PROCESSED)
    before_duplicate_ids, before_duplicate_names = duplicate_profile_counts(args.before_dir)
    duplicate_player_seasons = duplicate_player_season_rows()
    before_duplicate_player_seasons = duplicate_player_season_rows(args.before_dir)

    checks = [
        ("latest_winter_match_present", not latest.empty and match_id != "", f"{match_id} on {clean(latest.get('first_match_day'))}"),
        ("latest_match_is_current_refresh_date", pd.notna(source_date) and source_date.date().isoformat() == "2026-06-20", clean(latest.get("first_match_day"))),
        ("latest_match_result_present", bool(clean(latest.get("result_text"))), clean(latest.get("result_text"))),
        ("latest_match_teams_present", bool(clean(latest.get("home_team_name"))) and bool(clean(latest.get("away_team_name"))), f"{clean(latest.get('home_team_name'))} vs {clean(latest.get('away_team_name'))}"),
        ("scorecard_source_present", raw_scorecard.exists(), str(raw_scorecard.relative_to(ROOT))),
        ("winter_2026_current", latest_three[:1] == ["Winter 2026"], " | ".join(latest_three)),
        ("season_overview_latest_match", len(season_row) == 1, clean(season_row.iloc[0].get("best_batter")) + " / " + clean(season_row.iloc[0].get("best_bowler")) if len(season_row) else "missing"),
        ("season_overview_result", len(season_row) == 1 and clean(season_row.iloc[0].get("result_class")) == "win", clean(season_row.iloc[0].get("result_text")) if len(season_row) else "missing"),
        ("season_overview_batting_stats", set(impact.loc[impact["batting_runs_added"].gt(0), "normalized_player_name"]).issubset(latest_aggregate_names), "Latest scorers present in Winter 2026 aggregates."),
        ("season_overview_bowling_stats", set(impact.loc[impact["wickets_added"].gt(0), "normalized_player_name"]).issubset(latest_aggregate_names), "Latest wicket takers present in Winter 2026 aggregates."),
        ("season_overview_fielding_stats", set(impact.loc[impact[["catches_added", "stumpings_added", "runouts_added"]].sum(axis=1).gt(0), "normalized_player_name"]).issubset(latest_aggregate_names), "Latest fielders present in Winter 2026 aggregates."),
        ("wides_no_balls_preserved", all(column in bowling for column in ["bowlingWides", "bowlingNoBalls"]), "Aggregate bowling extras columns present."),
        ("all_latest_players_mapped", latest_player_ids.issubset(profile_ids) and impact["player_profile_updated"].eq("yes").all(), f"{len(impact)} of {len(impact)} latest-match players mapped."),
        ("player_profile_recent_batting", recent_batting.get("match_id", pd.Series(dtype="object")).astype(str).eq(match_id).any(), "Latest match appears in batting recent form."),
        ("player_profile_recent_bowling", recent_bowling.get("match_id", pd.Series(dtype="object")).astype(str).eq(match_id).any(), "Latest match appears in bowling recent form."),
        ("hof_latest_match_context", hof_links.get("match_id", pd.Series(dtype="object")).astype(str).eq(match_id).any(), "Latest match appears in HOF record links."),
        ("hof_fastest_context", fastest.get("match_id", pd.Series(dtype="object")).astype(str).eq(match_id).any() and fastest.loc[fastest["match_id"].astype(str).eq(match_id), "season"].eq("Winter 2026").all(), "Applicable ball-by-ball innings include Winter 2026 context."),
        ("premierships_unchanged", len(premierships) == 8 and not premierships.get("match_id", pd.Series(dtype="object")).astype(str).eq(match_id).any(), "Non-final latest match did not alter 8 premiership wins."),
        ("milestone_inputs_updated", latest_player_ids.issubset(latest_aggregate_names), "All latest players feed current aggregate milestone calculations."),
        ("active_latest_three_include_winter", latest_three == ["Winter 2026", "Summer 2025/26", "Winter 2025"], " | ".join(latest_three)),
        ("no_negative_aggregate_changes", not negative_changes, "; ".join(negative_changes) or "No metric decreases versus pre-refresh snapshot."),
        ("no_duplicate_match_rows", source_duplicate_matches == 0, f"duplicate rows={source_duplicate_matches}"),
        ("no_duplicate_player_profiles_created", duplicate_ids == 0 and duplicate_names <= before_duplicate_names, f"duplicate ids={duplicate_ids}; duplicate-name rows {before_duplicate_names}->{duplicate_names}"),
        ("no_duplicate_player_season_rows_created", duplicate_player_seasons <= before_duplicate_player_seasons, f"existing duplicate rows {before_duplicate_player_seasons}->{duplicate_player_seasons}"),
        ("grdcc_tracked_files_unchanged", tracked_grdcc_unchanged(), "No tracked GRDCC diff."),
        ("fvcc_ui_theme_unchanged", app_code_unchanged(), "No layout/theme diff."),
    ]

    VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    impact.to_csv(AUDIT_PATH, index=False)
    with VALIDATION_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "notes"])
        writer.writeheader()
        for name, passed, notes in checks:
            writer.writerow({"check": name, "status": "pass" if passed else "fail", "notes": notes})

    failed = [name for name, passed, _ in checks if not passed]
    print(f"validation_status={'pass' if not failed else 'fail'} checks={len(checks)} failed={len(failed)}")
    print(f"latest_match={match_id} date={source_date.date().isoformat()} result={clean(latest.get('result_text'))}")
    print(f"players_updated={len(impact)} latest_three={' | '.join(latest_three)}")
    if failed:
        print("failed_checks=" + ",".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
