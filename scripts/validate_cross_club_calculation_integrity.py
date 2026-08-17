#!/usr/bin/env python3
"""Audit shared Scorebook calculations and dismissal semantics across clubs."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_season_overview_detail_exports as season_exports  # noqa: E402
from src.analytics.playcricket_stats import _decimal_overs  # noqa: E402
from src.data.dismissal_status import batting_innings_mask, dismissed_mask, not_out_mask  # noqa: E402
from src.ui.layout import calculate_bowling_impact_score, calculate_extras_pct  # noqa: E402


CLUBS = ["fvcc", "georges-river-district", "glen-waverley-hawks"]
VALIDATION_DIR = ROOT / "data" / "processed" / "validation"
RESULT_PATH = VALIDATION_DIR / "cross_club_calculation_integrity_validation.csv"
CORRECTION_PATH = VALIDATION_DIR / "dismissal_denominator_corrections.csv"
TOLERANCE = 0.011


def read_csv(path: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(path)
    except (FileNotFoundError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def number(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame.get(column, pd.Series(index=frame.index, dtype="object")), errors="coerce")


def mismatch_count(actual: pd.Series, expected: pd.Series, valid: pd.Series) -> int:
    actual = pd.to_numeric(actual, errors="coerce")
    expected = pd.to_numeric(expected, errors="coerce")
    valid = valid.fillna(False) & expected.notna()
    return int((valid & (actual.isna() | actual.sub(expected).abs().gt(TOLERANCE))).sum())


def add_formula_check(
    results: list[dict[str, object]],
    club_id: str,
    check_name: str,
    frame: pd.DataFrame,
    actual_column: str,
    expected: pd.Series,
    valid: pd.Series,
) -> None:
    if frame.empty or actual_column not in frame:
        results.append(result(club_id, check_name, "WARN", 0, "Source or displayed column unavailable"))
        return
    mismatches = mismatch_count(frame[actual_column], expected, valid)
    results.append(result(club_id, check_name, "PASS" if mismatches == 0 else "FAIL", mismatches, f"{len(frame):,} rows checked"))


def result(club_id: str, check_name: str, status: str, affected_rows: int, notes: str) -> dict[str, object]:
    return {
        "club_id": club_id,
        "check_name": check_name,
        "status": status,
        "affected_rows": affected_rows,
        "notes": notes,
    }


def audit_club_formulas(club_id: str, results: list[dict[str, object]]) -> None:
    root = ROOT / "clubs" / club_id / "data" / "processed"
    batting = read_csv(root / "all_seasons_batting.csv")
    if not batting.empty:
        runs = number(batting, "battingAggregate")
        innings = number(batting, "battingInnings")
        not_outs = number(batting, "battingNotOuts").fillna(0)
        balls = number(batting, "battingBallsFaced")
        outs = innings - not_outs
        add_formula_check(results, club_id, "batting_average", batting, "battingAverage", runs.div(outs), outs.gt(0))
        add_formula_check(results, club_id, "batting_strike_rate", batting, "battingStrikeRate", runs.mul(100).div(balls), balls.gt(0))

    bowling = read_csv(root / "all_seasons_bowling.csv")
    if not bowling.empty:
        wickets = number(bowling, "bowlingWickets")
        runs_against = number(bowling, "bowlingRuns")
        balls = number(bowling, "bowlingBalls")
        add_formula_check(results, club_id, "bowling_average", bowling, "bowlingAverage", runs_against.div(wickets), wickets.gt(0))
        add_formula_check(results, club_id, "bowling_strike_rate", bowling, "bowlingStrikeRate", balls.div(wickets), wickets.gt(0))
        add_formula_check(results, club_id, "bowling_economy", bowling, "bowlingEconomyRate", runs_against.mul(6).div(balls), balls.gt(0))

    bbb_batting = read_csv(root / "season_overview" / "bbb_batting_rates_by_scope.csv")
    if not bbb_batting.empty:
        runs = number(bbb_batting, "bbb_runs")
        balls = number(bbb_batting, "bbb_balls_faced")
        dot_balls = number(bbb_batting, "bbb_dot_balls")
        dot_denominator = number(bbb_batting, "bbb_dot_ball_balls_faced")
        add_formula_check(results, club_id, "bbb_batting_strike_rate", bbb_batting, "bat_sr", runs.mul(100).div(balls), balls.gt(0))
        add_formula_check(results, club_id, "bbb_batting_dot_pct", bbb_batting, "batting_dot_ball_pct", dot_balls.mul(100).div(dot_denominator), dot_denominator.gt(0))

    bbb_bowling = read_csv(root / "season_overview" / "bbb_bowling_dot_rates_by_scope.csv")
    if not bbb_bowling.empty:
        legal_balls = number(bbb_bowling, "legal_balls")
        dots = number(bbb_bowling, "dot_balls")
        add_formula_check(results, club_id, "bbb_bowling_dot_pct", bbb_bowling, "dot_ball_pct", dots.mul(100).div(legal_balls), legal_balls.gt(0))

    profile = read_csv(root / "player_profile" / "performance_breakdown_by_dimension.csv")
    if not profile.empty:
        batting_rows = profile[profile.get("discipline", pd.Series(index=profile.index, dtype="object")).eq("Batting")].copy()
        outs = number(batting_rows, "outs")
        bbb_balls = number(batting_rows, "bbb_balls_faced")
        add_formula_check(results, club_id, "profile_batting_average", batting_rows, "bat_avg", number(batting_rows, "runs").div(outs), outs.gt(0))
        add_formula_check(results, club_id, "profile_batting_strike_rate", batting_rows, "strike_rate", number(batting_rows, "bbb_runs").mul(100).div(bbb_balls), bbb_balls.gt(0))

        bowling_rows = profile[profile.get("discipline", pd.Series(index=profile.index, dtype="object")).eq("Bowling")].copy()
        wickets = number(bowling_rows, "wickets")
        bowl_balls = number(bowling_rows, "balls_bowled")
        runs_against = number(bowling_rows, "runs_against")
        add_formula_check(results, club_id, "profile_bowling_average", bowling_rows, "bowl_avg", runs_against.div(wickets), wickets.gt(0))
        add_formula_check(results, club_id, "profile_bowling_strike_rate", bowling_rows, "bowl_sr", bowl_balls.div(wickets), wickets.gt(0))
        add_formula_check(results, club_id, "profile_bowling_economy", bowling_rows, "eco", runs_against.mul(6).div(bowl_balls), bowl_balls.gt(0))
        if {"wides", "no_balls", "extras_pct"}.issubset(bowling_rows.columns):
            extras = number(bowling_rows, "wides").fillna(0) + number(bowling_rows, "no_balls").fillna(0)
            add_formula_check(results, club_id, "profile_bowling_extras_pct", bowling_rows, "extras_pct", extras.mul(100).div(bowl_balls), bowl_balls.gt(0))
        elif {"bowlingWides", "bowlingNoBalls", "bowlingBalls"}.issubset(bowling.columns):
            source_balls = number(bowling, "bowlingBalls")
            source_wides = number(bowling, "bowlingWides").fillna(0)
            source_no_balls = number(bowling, "bowlingNoBalls").fillna(0)
            valid = source_balls.gt(0)
            expected = source_no_balls.add(source_wides).mul(100).div(source_balls)
            calculated = bowling.apply(
                lambda row: calculate_extras_pct(
                    row.get("bowlingNoBalls"),
                    row.get("bowlingWides"),
                    row.get("bowlingBalls"),
                ),
                axis=1,
            )
            mismatches = mismatch_count(calculated, expected, valid)
            status = "PASS" if mismatches == 0 else "FAIL"
            results.append(
                result(
                    club_id,
                    "profile_bowling_extras_pct",
                    status,
                    mismatches,
                    f"{int(valid.sum()):,} render-time source rows checked (bowlingWides + bowlingNoBalls)",
                )
            )
        else:
            results.append(result(club_id, "profile_bowling_extras_pct", "WARN", 0, "No wides/no-balls source is available"))

    phases = read_csv(root / "player_profile" / "bowling_phase_summary.csv")
    if not phases.empty:
        balls = number(phases, "legal_balls")
        wickets = number(phases, "wickets")
        runs_against = number(phases, "runs_conceded")
        add_formula_check(results, club_id, "phase_bowling_average", phases, "avg", runs_against.div(wickets), wickets.gt(0))
        add_formula_check(results, club_id, "phase_bowling_strike_rate", phases, "sr", balls.div(wickets), wickets.gt(0))
        add_formula_check(results, club_id, "phase_bowling_economy", phases, "eco", runs_against.mul(6).div(balls), balls.gt(0))
        add_formula_check(results, club_id, "phase_dot_pct", phases, "dot_ball_pct", number(phases, "dot_balls").mul(100).div(balls), balls.gt(0))
        add_formula_check(results, club_id, "phase_boundary_pct", phases, "boundary_rate", number(phases, "boundary_balls").mul(100).div(balls), balls.gt(0))

    fingerprint = read_csv(root / "player_profile" / "dismissal_fingerprint_summary.csv")
    if not fingerprint.empty:
        expected = number(fingerprint, "count").mul(100).div(number(fingerprint, "total_dismissals"))
        add_formula_check(results, club_id, "dismissal_fingerprint_pct", fingerprint, "pct", expected, number(fingerprint, "total_dismissals").gt(0))
        group_columns = [column for column in ["canonical_player_id", "scope"] if column in fingerprint]
        sums = fingerprint.groupby(group_columns, dropna=False)["pct"].sum() if group_columns else pd.Series(dtype=float)
        bad_groups = int(sums.sub(100).abs().gt(TOLERANCE).sum())
        results.append(result(club_id, "dismissal_fingerprint_pct_total", "PASS" if bad_groups == 0 else "FAIL", bad_groups, f"{len(sums):,} groups checked"))

    wins = read_csv(root / "hall_of_fame" / "player_win_rates.csv")
    if not wins.empty:
        matches = number(wins, "matches_with_result")
        expected = number(wins, "wins").mul(100).div(matches)
        add_formula_check(results, club_id, "win_pct", wins, "win_pct", expected, matches.gt(0))


def audit_dismissal_source(
    club_id: str,
    results: list[dict[str, object]],
    corrections: list[dict[str, object]],
) -> None:
    frames = season_exports.load_match_centre_scopes(club_id=club_id)
    if frames.get("matches", pd.DataFrame()).empty:
        audit_deployed_dismissal_exports(club_id, results)
        return
    batting = season_exports.prepare_scorecard_rows(frames["batting"], frames["matches"], club_id=club_id)
    balls = frames.get("balls", pd.DataFrame()).copy()
    if batting.empty or balls.empty:
        audit_deployed_dismissal_exports(club_id, results)
        return
    batting = batting.drop_duplicates(["match_id", "innings_id", "participant_id", "bat_instance"]).copy()
    for column in ["match_id", "innings_id", "participant_id"]:
        batting[column] = batting[column].astype(str)
    ball_keys = balls[["match_id", "innings_id", "striker_participant_id"]].drop_duplicates().rename(
        columns={"striker_participant_id": "participant_id"}
    )
    for column in ["match_id", "innings_id", "participant_id"]:
        ball_keys[column] = ball_keys[column].astype(str)
    batting = batting.merge(ball_keys, on=["match_id", "innings_id", "participant_id"], how="inner")
    text = pd.Series("", index=batting.index)
    for column in ["dismissal_type", "dismissal_text"]:
        text = text.str.cat(batting.get(column, pd.Series("", index=batting.index)).fillna("").astype(str).str.casefold().str.strip(), sep=" ")
    text = text.str.replace(r"\s+", " ", regex=True).str.strip()
    old_dismissed = ~text.isin({"", "not out", "retired not out", "retired hurt"})
    corrected = old_dismissed & ~dismissed_mask(batting)
    affected = batting[corrected].copy()
    if affected.empty:
        results.append(result(club_id, "dismissal_source_semantics", "PASS", 0, "No false dismissals found"))
        return
    name_column = "display_player_name" if "display_player_name" in affected else "canonical_player_name"
    if name_column not in affected:
        name_column = "player_name"
    grouped = affected.groupby(name_column, dropna=False).size().sort_values(ascending=False)
    for player, count in grouped.items():
        corrections.append(
            {
                "club_id": club_id,
                "player": player,
                "false_dismissals_removed": int(count),
                "issue": "Duplicate/variant not-out or non-innings text was counted as dismissed",
            }
        )
    results.append(result(club_id, "dismissal_source_semantics", "PASS", int(corrected.sum()), f"Corrected {len(grouped):,} players in rebuilt sources"))


def audit_deployed_dismissal_exports(club_id: str, results: list[dict[str, object]]) -> None:
    """Reconcile tracked BBB denominators when raw match-centre caches are not deployed."""
    root = ROOT / "clubs" / club_id / "data" / "processed"
    profile = read_csv(root / "player_profile" / "performance_breakdown_by_dimension.csv")
    hall_of_fame = read_csv(root / "hall_of_fame" / "player_bbb_batting_rates.csv")
    metrics = ["bbb_runs", "bbb_balls_faced", "bbb_dismissals", "bbb_batting_innings", "bbb_matches"]
    required = {"canonical_player_id", *metrics}
    if profile.empty or hall_of_fame.empty or not required.issubset(profile.columns) or not required.issubset(hall_of_fame.columns):
        results.append(result(club_id, "dismissal_source_semantics", "WARN", 0, "Neither raw BBB rows nor two deploy-safe BBB aggregates are available"))
        return

    profile = profile[
        profile.get("dimension", pd.Series(index=profile.index, dtype="object")).eq("Season")
        & profile.get("discipline", pd.Series(index=profile.index, dtype="object")).eq("Batting")
    ].copy()
    profile = profile[profile[metrics].notna().any(axis=1)].copy()
    hall_of_fame = hall_of_fame[hall_of_fame[metrics].notna().any(axis=1)].copy()
    if profile.empty or hall_of_fame.empty:
        results.append(result(club_id, "dismissal_source_semantics", "WARN", 0, "Deploy-safe BBB aggregates contain no comparable batting rows"))
        return

    invalid_bounds = 0
    for frame in [profile, hall_of_fame]:
        dismissals = number(frame, "bbb_dismissals")
        innings = number(frame, "bbb_batting_innings")
        invalid_bounds += int((dismissals.lt(0) | innings.lt(0) | dismissals.gt(innings)).fillna(False).sum())

    profile_totals = profile.groupby("canonical_player_id", dropna=False)[metrics].sum(min_count=1)
    hall_totals = hall_of_fame.groupby("canonical_player_id", dropna=False)[metrics].sum(min_count=1)
    missing_ids = profile_totals.index.symmetric_difference(hall_totals.index)
    joined = profile_totals.join(hall_totals, how="inner", lsuffix="_profile", rsuffix="_hof")
    mismatches = 0
    for metric in metrics:
        left = pd.to_numeric(joined[f"{metric}_profile"], errors="coerce")
        right = pd.to_numeric(joined[f"{metric}_hof"], errors="coerce")
        mismatches += int((~left.fillna(-1).eq(right.fillna(-1))).sum())

    affected = invalid_bounds + len(missing_ids) + mismatches
    status = "PASS" if affected == 0 else "FAIL"
    notes = (
        f"{len(joined):,} canonical players reconciled across Player Profile and Hall of Fame; "
        "raw match-centre cache is not a deployed dependency"
    )
    results.append(result(club_id, "dismissal_source_semantics", status, affected, notes))


def audit_semantic_examples(results: list[dict[str, object]]) -> None:
    examples = pd.DataFrame(
        [
            ("Not Out", "not out", True, True, False),
            ("Retired Hurt", "", True, True, False),
            ("Retired Not Out", "retired not out", True, True, False),
            ("Absent", "absent hurt", False, False, False),
            ("Did Not Bat", "", False, False, False),
            ("Caught", "c Smith b Jones", True, False, True),
            ("", "", True, True, False),
        ],
        columns=["dismissal_type", "dismissal_text", "expected_innings", "expected_not_out", "expected_dismissed"],
    )
    actual = pd.DataFrame(
        {
            "innings": batting_innings_mask(examples),
            "not_out": not_out_mask(examples),
            "dismissed": dismissed_mask(examples),
        }
    )
    expected = examples[["expected_innings", "expected_not_out", "expected_dismissed"]].copy()
    expected.columns = actual.columns
    mismatches = int(actual.ne(expected).any(axis=1).sum())
    results.append(result("shared", "dismissal_semantic_examples", "PASS" if mismatches == 0 else "FAIL", mismatches, f"{len(examples)} edge cases checked"))

    overs_ok = _decimal_overs("3.5") == 23 / 6 and _decimal_overs("9.5") == 59 / 6 and _decimal_overs("3.6") is None
    results.append(result("shared", "cricket_overs_conversion", "PASS" if overs_ok else "FAIL", 0 if overs_ok else 1, "3.5 and 9.5 interpreted as cricket notation"))
    impact = calculate_bowling_impact_score(pd.DataFrame([{"wickets_taken": 0, "economy": 0, "maidens_bowled": 0, "overs_bowled": "3.5"}]))
    impact_ok = abs(float(impact.iloc[0]["bowling_impact_score"]) - 23 / 6) < 1e-9
    results.append(result("shared", "bowling_impact_cricket_overs", "PASS" if impact_ok else "FAIL", 0 if impact_ok else 1, "Impact score uses balls/6"))


def main() -> int:
    results: list[dict[str, object]] = []
    corrections: list[dict[str, object]] = []
    audit_semantic_examples(results)
    for club_id in CLUBS:
        audit_club_formulas(club_id, results)
        audit_dismissal_source(club_id, results, corrections)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    result_frame = pd.DataFrame(results)
    correction_frame = pd.DataFrame(corrections)
    result_frame.to_csv(RESULT_PATH, index=False)
    correction_frame.to_csv(CORRECTION_PATH, index=False)
    failed = result_frame[result_frame["status"].eq("FAIL")]
    print(result_frame.groupby(["status"], dropna=False).size().to_string())
    print(f"Corrections: {len(correction_frame):,} player rows")
    print(f"Validation: {RESULT_PATH}")
    print(f"Corrections: {CORRECTION_PATH}")
    return 1 if not failed.empty else 0


if __name__ == "__main__":
    raise SystemExit(main())
