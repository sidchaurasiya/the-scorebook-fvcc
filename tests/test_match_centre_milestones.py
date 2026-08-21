from __future__ import annotations

import pandas as pd

from src.data.match_centre_milestones import calculate_milestones


def batting_row(runs: int, balls: int | None = 10) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "participant_id": "player-1",
                "player_name": "Test Batter",
                "runs_scored": runs,
                "balls_faced": balls,
                "dismissal_type": "not out",
                "match_date": "2026-01-01",
                "season": "Summer 2025/26",
            }
        ]
    )


def ball_rows(runs_bat: list[int], source_runs: list[int] | None = None) -> pd.DataFrame:
    source_runs = source_runs or []
    return pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "striker_participant_id": "player-1",
                "innings_order": 1,
                "over_number": index // 6,
                "ball_number": (index % 6) + 1,
                "ball_event_id": f"ball-{index + 1}",
                "runs_bat": runs,
                "is_legal_delivery": True,
                "striker_runs_scored": source_runs[index] if index < len(source_runs) else pd.NA,
            }
            for index, runs in enumerate(runs_bat)
        ]
    )


def test_bad_source_cumulative_run_jump_does_not_create_false_fastest_50() -> None:
    runs = [6, 6, 6, 6, 6, 6, 6, 6, 2, 4]
    bad_source = [0, 54, 4, 10, 16, 22, 28, 34, 50, 54]

    milestones, validation = calculate_milestones(batting_row(54), ball_rows(runs, bad_source), {})

    assert int(milestones.iloc[0]["balls_to_50"]) == 9
    assert milestones.iloc[0]["runs_source_used"] == "derived_runs_bat"
    assert validation["check_name"].str.contains("source_cumulative_runs_invalid").any()


def test_constant_final_source_runs_do_not_create_one_ball_milestone() -> None:
    runs = [6, 6, 6, 6, 6, 6, 6, 6, 2, 4]

    milestones, validation = calculate_milestones(batting_row(54), ball_rows(runs, [54] * len(runs)), {})

    assert int(milestones.iloc[0]["balls_to_50"]) == 9
    assert validation["check_name"].str.contains("source_cumulative_runs_invalid").any()


def test_zero_scorecard_balls_uses_verified_legal_ball_count() -> None:
    runs = [6, 6, 6, 6, 6, 6, 6, 6, 2, 4]

    milestones, validation = calculate_milestones(batting_row(54, balls=0), ball_rows(runs), {})

    assert int(milestones.iloc[0]["final_balls"]) == 10
    assert milestones.iloc[0]["balls_faced_source_used"] == "derived_legal_balls"
    assert validation["check_name"].str.contains("scorecard_balls_zero_treated_as_missing").any()


def test_below_threshold_fastest_50_is_excluded() -> None:
    runs = [7, 7, 7, 7, 7, 7, 7, 7]

    milestones, validation = calculate_milestones(batting_row(56, balls=8), ball_rows(runs), {})

    assert pd.isna(milestones.iloc[0]["balls_to_50"])
    excluded = validation[validation["check_name"] == "balls_to_50_below_plausibility_threshold"]
    assert not excluded.empty
    assert set(excluded["severity"]) == {"excluded"}


def test_supported_milestone_is_retained_when_final_delivery_runs_are_incomplete() -> None:
    runs = [6, 6, 6, 6, 6, 6, 6, 6, 2, 6]

    milestones, validation = calculate_milestones(batting_row(60, balls=10), ball_rows(runs), {})

    assert int(milestones.iloc[0]["balls_to_50"]) == 9
    warning = validation[validation["check_name"] == "trusted_runs_mismatch_scorecard_partial_milestones"]
    assert not warning.empty
    assert set(warning["severity"]) == {"warning"}
