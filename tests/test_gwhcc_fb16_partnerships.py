from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from src.data.match_centre_parser import build_ball_partnerships
from src.data.partnerships import build_partnership_record_holders, prepare_ball_by_ball_partnerships


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "clubs" / "glen-waverley-hawks" / "data" / "processed"


def source_context(runs: tuple[int, int] = (40, 60), pair_ids: tuple[str, str] = ("player-a", "player-b")):
    partnerships = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "batting_team_id": "hawks",
                "partnership_number": 1,
                "batter_1_participant_id": pair_ids[0],
                "batter_1_name": "A Player",
                "batter_2_participant_id": pair_ids[1],
                "batter_2_name": "B Player",
                "runs": runs[0],
                "balls": 50,
                "source": "ball_by_ball",
                "wicket_ending_participant_id": pair_ids[1],
                "dismissal_type": "Caught",
            },
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "batting_team_id": "hawks",
                "partnership_number": 2,
                "batter_1_participant_id": pair_ids[0],
                "batter_1_name": "A Player",
                "batter_2_participant_id": "player-c",
                "batter_2_name": "C Player",
                "runs": runs[1],
                "balls": 70,
                "source": "ball_by_ball",
                "wicket_ending_participant_id": "",
                "dismissal_type": "",
            },
        ]
    )
    matches = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "season": "Summer 2025/26",
                "first_match_day": "2026-01-01",
                "grade_name": "A Grade",
                "home_team_id": "hawks",
                "home_team_name": "Glen Waverley Hawks",
                "away_team_id": "opposition",
                "away_team_name": "Opposition Cricket Club",
            }
        ]
    )
    innings = pd.DataFrame([{"match_id": "match-1", "innings_id": "innings-1", "runs_scored": sum(runs)}])
    identity = {
        "player-a": {"canonical_player_id": "a_player", "canonical_player_name": "A Player"},
        "player-b": {"canonical_player_id": "b_player", "canonical_player_name": "B Player"},
        "player-c": {"canonical_player_id": "c_player", "canonical_player_name": "C Player"},
    }
    return partnerships, matches, innings, identity


def prepare(*, runs: tuple[int, int] = (40, 60), pair_ids: tuple[str, str] = ("player-a", "player-b"), identity=None):
    partnerships, matches, innings, default_identity = source_context(runs, pair_ids)
    return prepare_ball_by_ball_partnerships(
        partnerships,
        matches=matches,
        innings=innings,
        selected_team_ids_by_match={"match-1": {"hawks"}},
        identity_lookup=default_identity if identity is None else identity,
    )


def test_existing_delivery_calculator_builds_partnership_runs_and_pairs() -> None:
    balls = pd.DataFrame(
        [
            {"match_id": "m", "innings_id": "i", "batting_team_id": "t", "over_number": 1, "ball_number": 1, "ball_event_id": "1", "striker_participant_id": "a", "striker_short_name": "A", "non_striker_participant_id": "b", "non_striker_short_name": "B", "total_runs": 1, "is_legal_delivery": True, "is_wicket": False, "progress_score": "0-1", "dismissed_participant_id": "", "dismissal_type": ""},
            {"match_id": "m", "innings_id": "i", "batting_team_id": "t", "over_number": 1, "ball_number": 2, "ball_event_id": "2", "striker_participant_id": "b", "striker_short_name": "B", "non_striker_participant_id": "a", "non_striker_short_name": "A", "total_runs": 4, "is_legal_delivery": True, "is_wicket": True, "progress_score": "1-5", "dismissed_participant_id": "b", "dismissal_type": "Caught"},
            {"match_id": "m", "innings_id": "i", "batting_team_id": "t", "over_number": 1, "ball_number": 3, "ball_event_id": "3", "striker_participant_id": "a", "striker_short_name": "A", "non_striker_participant_id": "c", "non_striker_short_name": "C", "total_runs": 2, "is_legal_delivery": True, "is_wicket": False, "progress_score": "1-7", "dismissed_participant_id": "", "dismissal_type": ""},
            {"match_id": "m", "innings_id": "i", "batting_team_id": "t", "over_number": 1, "ball_number": 4, "ball_event_id": "4", "striker_participant_id": "c", "striker_short_name": "C", "non_striker_participant_id": "a", "non_striker_short_name": "A", "total_runs": 3, "is_legal_delivery": True, "is_wicket": False, "progress_score": "1-10", "dismissed_participant_id": "", "dismissal_type": ""},
        ]
    )
    result = build_ball_partnerships(balls)
    assert result["runs"].tolist() == [5, 5]
    assert result[["batter_1_name", "batter_2_name"]].values.tolist() == [["A", "B"], ["A", "C"]]


def test_partnership_preparation_reconciles_runs_and_context() -> None:
    result = prepare()
    assert len(result.events) == 2
    first = result.events.iloc[0]
    assert first["runs"] == 40
    assert first["balls"] == 50
    assert first["opponent"] == "Opposition Cricket Club"
    assert first["evidence_quality"] == "innings_total_reconciled"


def test_duplicate_canonical_identity_is_held_for_review() -> None:
    identity = {
        "player-a": {"canonical_player_id": "same", "canonical_player_name": "Same Player"},
        "player-b": {"canonical_player_id": "same", "canonical_player_name": "Same Player"},
        "player-c": {"canonical_player_id": "c_player", "canonical_player_name": "C Player"},
    }
    result = prepare(identity=identity)
    first = result.audit[result.audit["wicket_number"].eq(1)].iloc[0]
    assert first["validation_status"] == "REVIEW"
    assert "same canonical player" in first["review_reason"]


def test_missing_identity_is_held_for_review() -> None:
    result = prepare(identity={"player-a": {"canonical_player_id": "a", "canonical_player_name": "A Player"}})
    assert result.events.empty
    assert result.audit["validation_status"].eq("REVIEW").all()


def test_private_pair_is_excluded() -> None:
    identity = {
        "player-a": {"canonical_player_id": "private", "canonical_player_name": "********"},
        "player-b": {"canonical_player_id": "b", "canonical_player_name": "B Player"},
        "player-c": {"canonical_player_id": "c", "canonical_player_name": "C Player"},
    }
    result = prepare(identity=identity)
    assert result.events.empty
    assert result.audit["validation_status"].eq("EXCLUDED_PRIVATE").all()


def test_mismatched_innings_total_is_not_published() -> None:
    result = prepare(runs=(40, 50))
    # Source context expects the same supplied runs, so force the scorecard mismatch explicitly.
    partnerships, matches, innings, identity = source_context((40, 50))
    innings["runs_scored"] = 100
    result = prepare_ball_by_ball_partnerships(
        partnerships,
        matches=matches,
        innings=innings,
        selected_team_ids_by_match={"match-1": {"hawks"}},
        identity_lookup=identity,
    )
    assert result.events.empty
    assert result.audit["validation_status"].eq("REVIEW").all()


def test_preparation_and_record_selection_are_reproducible() -> None:
    first = prepare()
    second = prepare()
    assert_frame_equal(first.events, second.events)
    assert_frame_equal(build_partnership_record_holders(first.events), build_partnership_record_holders(second.events))


def test_deployed_partnership_outputs_are_public_and_validated() -> None:
    events = pd.read_csv(PROCESSED / "partnerships" / "partnership_events.csv", low_memory=False)
    records = pd.read_csv(PROCESSED / "hall_of_fame" / "partnership_records.csv", low_memory=False)
    validation = pd.read_csv(PROCESSED / "validation" / "gwhcc_partnership_validation.csv")
    assert len(events) == 3314
    assert records["wicket_number"].tolist() == list(range(1, 11))
    assert not events["player_1_name"].astype(str).str.contains(r"\*{2,}", regex=True).any()
    assert not events["player_2_name"].astype(str).str.contains(r"\*{2,}", regex=True).any()
    assert validation["status"].ne("FAIL").all()
