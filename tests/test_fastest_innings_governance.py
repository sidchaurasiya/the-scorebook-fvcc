from __future__ import annotations

import pandas as pd
import pytest

from src.data.fastest_innings import (
    apply_detector_evidence,
    build_governed_fastest_innings,
    coverage_summary_row,
    govern_fastest_innings_candidates,
)


def candidate(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "match_id": "match-1",
        "innings_id": "innings-1",
        "participant_id": "player-1",
        "player_id": "player-1",
        "player_name": "Public Player",
        "canonical_player_id": "player-1",
        "canonical_player_name": "Public Player",
        "match_date": "2026-01-01",
        "final_runs": 60,
        "final_balls": 40,
        "balls_to_25": 18,
        "balls_to_50": 35,
        "balls_to_100": pd.NA,
        "balls_to_150": pd.NA,
        "source_ball_by_ball_available": True,
        "runs_source_used": "derived_runs_bat",
        "balls_faced_source_used": "derived_legal_balls",
    }
    row.update(overrides)
    return row


def detector_row(check_name: str, severity: str = "warning") -> dict[str, object]:
    return {
        "check_name": check_name,
        "severity": severity,
        "match_id": "match-1",
        "innings_id": "innings-1",
        "player_id": "player-1",
    }


def test_valid_reconciled_delivery_candidate_is_published() -> None:
    result = govern_fastest_innings_candidates(pd.DataFrame([candidate()]), pd.DataFrame())

    assert len(result.published) == 1
    assert result.review.empty
    assert result.rejected.empty
    assert result.audit.iloc[0]["governance_status"] == "published"


def test_supported_partial_milestone_survives_final_run_total_mismatch() -> None:
    validation = pd.DataFrame([detector_row("trusted_runs_mismatch_scorecard_partial_milestones")])

    result = govern_fastest_innings_candidates(pd.DataFrame([candidate()]), validation)

    assert len(result.published) == 1
    assert result.rejected.empty
    assert "detector_advisory:trusted_runs_mismatch" in result.audit.iloc[0]["reason_codes"]


def test_verified_delivery_final_balls_override_incorrect_scorecard_balls() -> None:
    validation = pd.DataFrame(
        [
            {
                **detector_row("final_balls_match_scorecard"),
                "scorecard_final_balls": 43,
                "source_final_balls": 45,
            }
        ]
    )
    candidates = apply_detector_evidence(
        pd.DataFrame([candidate(final_runs=54, final_balls=43, balls_to_50=45)]),
        validation,
    )

    result = govern_fastest_innings_candidates(candidates, validation)

    assert len(result.published) == 1
    assert int(result.published.iloc[0]["final_balls"]) == 45
    assert result.published.iloc[0]["governance_final_balls_source"] == "verified_delivery_override_scorecard"


def test_any_detector_exclusion_is_rejected() -> None:
    validation = pd.DataFrame([detector_row("future_detector_exclusion", severity="excluded")])

    result = govern_fastest_innings_candidates(pd.DataFrame([candidate()]), validation)

    assert result.published.empty
    assert "excluded:future_detector_exclusion" in result.rejected.iloc[0]["reason_codes"]


def test_impossible_and_private_candidates_are_rejected() -> None:
    rows = pd.DataFrame(
        [
            candidate(balls_to_50=45, final_balls=43),
            candidate(
                match_id="match-2",
                innings_id="innings-2",
                participant_id="00000000-0000-0000-0000-000000000001",
                canonical_player_id="raw_00000000_0000_0000_0000_000000000001",
                player_name="********",
                canonical_player_name="********",
            ),
        ]
    )

    result = govern_fastest_innings_candidates(rows, pd.DataFrame())

    assert result.published.empty
    assert len(result.rejected) == 2
    assert result.rejected["reason_codes"].str.contains("exceeds_final_balls").any()
    assert result.rejected["reason_codes"].str.contains("private_or_masked_player").any()


def test_scorecard_only_candidate_is_review_only() -> None:
    result = govern_fastest_innings_candidates(
        pd.DataFrame([candidate(source_ball_by_ball_available=False)]),
        pd.DataFrame(),
    )

    assert result.published.empty
    assert len(result.review) == 1
    assert result.review.iloc[0]["reason_codes"] == "scorecard_only_not_fastest_evidence"


def test_duplicate_events_are_rejected_and_output_is_reproducible() -> None:
    duplicate = candidate()
    candidates = pd.DataFrame([duplicate, duplicate])

    first = govern_fastest_innings_candidates(candidates, pd.DataFrame())
    second = govern_fastest_innings_candidates(candidates.sample(frac=1, random_state=7), pd.DataFrame())

    assert first.published.empty
    assert len(first.rejected) == 2
    pd.testing.assert_frame_equal(first.audit, second.audit)


def test_rebuild_fails_closed_when_delivery_sources_are_missing(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="Restore or refresh the ignored delivery sources"):
        build_governed_fastest_innings(
            club_id="fvcc",
            processed_root=tmp_path / "missing-match-centre",
            players_path=tmp_path / "players.csv",
            aliases_path=tmp_path / "aliases.csv",
            club_team_ids=set(),
            club_name_token="Fiji Victorian Cricket Club",
        )


def test_coverage_keeps_scorecard_only_achievements_separate() -> None:
    matches = pd.DataFrame({"match_id": ["match-1", "match-2"]})
    batting = pd.DataFrame(
        {
            "match_id": ["match-1", "match-2", "match-2"],
            "has_delivery_balls": [True, False, False],
            "scorecard_runs": [55, 105, 20],
        }
    )
    balls = pd.DataFrame({"match_id": ["match-1", "match-1"]})

    coverage = coverage_summary_row("overall", matches, batting, balls)

    assert coverage["matches_with_ball_by_ball"] == 1
    assert coverage["innings_with_reliable_delivery_balls"] == 1
    assert coverage["innings_without_reliable_delivery_balls"] == 2
    assert coverage["scorecard_only_50_plus"] == 1
    assert coverage["scorecard_only_100_plus"] == 1
