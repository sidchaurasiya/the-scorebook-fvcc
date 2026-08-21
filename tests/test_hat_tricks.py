from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.hat_tricks import detect_hat_tricks, public_hat_trick_events


ROOT = Path(__file__).resolve().parents[1]
GWHCC_PROCESSED = ROOT / "clubs" / "glen-waverley-hawks" / "data" / "processed"


def detection(
    dismissals: list[str],
    *,
    overs: list[int] | None = None,
    balls: list[int] | None = None,
    bowler_ids: list[str] | None = None,
    dismissed_ids: list[str] | None = None,
    legal: list[bool] | None = None,
    no_balls: list[int] | None = None,
    wides: list[int] | None = None,
    innings_ids: list[str] | None = None,
    innings_orders: list[int] | None = None,
    match_ids: list[str] | None = None,
    duplicate_first: bool = False,
    match_id: str = "match-1",
    player_name: str = "Test Bowler",
    identity_lookup: dict[str, dict[str, str]] | None = None,
):
    size = len(dismissals)
    overs = overs or [1] * size
    balls = balls or list(range(1, size + 1))
    bowler_ids = bowler_ids or ["bowler-1"] * size
    dismissed_ids = dismissed_ids or [f"batter-{index}" for index in range(1, size + 1)]
    legal = legal or [True] * size
    no_balls = no_balls or [0] * size
    wides = wides or [0 if legal[index] else 1 for index in range(size)]
    innings_ids = innings_ids or ["innings-1"] * size
    innings_orders = innings_orders or [1] * size
    match_ids = match_ids or [match_id] * size
    rows = []
    for index, dismissal in enumerate(dismissals):
        is_wicket = bool(dismissal)
        rows.append(
            {
                "match_id": match_ids[index],
                "innings_id": innings_ids[index],
                "innings_order": innings_orders[index],
                "batting_team_id": "opponent",
                "bowling_team_id": "hawks",
                "ball_event_id": f"{match_ids[index]}-{innings_ids[index]}-event-{index}",
                "over_number": overs[index],
                "ball_number": balls[index],
                "striker_participant_id": dismissed_ids[index],
                "non_striker_participant_id": "non-striker",
                "bowler_participant_id": bowler_ids[index],
                "bowler_short_name": player_name,
                "runs_bat": 0,
                "wides": wides[index],
                "no_balls": no_balls[index],
                "leg_byes": 0,
                "byes": 0,
                "penalty_runs": 0,
                "total_runs": 0,
                "is_legal_delivery": legal[index],
                "is_wicket": is_wicket,
                "dismissal_type": dismissal,
                "dismissed_participant_id": dismissed_ids[index] if is_wicket else "",
                "progress_runs": 0,
                "progress_wickets": sum(bool(value) for value in dismissals[: index + 1]),
            }
        )
    if duplicate_first:
        duplicate = dict(rows[0])
        duplicate["ball_event_id"] = "provider-duplicate"
        rows.insert(1, duplicate)
    matches = pd.DataFrame(
        [
            {
                "match_id": current_match_id,
                "season": "Summer 2025/26",
                "first_match_day": "2026-01-01",
                "home_team_id": "hawks",
                "home_team_name": "Glen Waverley Hawks",
                "away_team_id": "opponent",
                "away_team_name": "Opposition Cricket Club",
                "grade_name": "A Grade",
            }
            for current_match_id in dict.fromkeys(match_ids)
        ]
    )
    unique_bowler_ids = list(dict.fromkeys(bowler_ids))
    bowling_rows = []
    for current_match_id, current_innings_id, bowler_id in dict.fromkeys(
        zip(match_ids, innings_ids, bowler_ids)
    ):
        relevant = [
            index
            for index in range(size)
            if match_ids[index] == current_match_id
            and innings_ids[index] == current_innings_id
            and bowler_ids[index] == bowler_id
        ]
        bowling_rows.append(
            {
                "match_id": current_match_id,
                "innings_id": current_innings_id,
                "participant_id": bowler_id,
                "wickets_taken": sum(
                    dismissal.casefold() in {"bowled", "caught", "caught & bowled", "lbw", "stumped", "hit wicket"}
                    and no_balls[index] == 0
                    for index in relevant
                    for dismissal in [dismissals[index]]
                ),
            }
        )
    bowling = pd.DataFrame(bowling_rows)
    batting = pd.DataFrame(
        [
            {
                "match_id": match_ids[index],
                "innings_id": innings_ids[index],
                "participant_id": dismissed_ids[index],
                "bat_instance": 1,
                "dismissal_type": dismissal,
                "bowler_participant_id": bowler_ids[index],
            }
            for index, dismissal in enumerate(dismissals)
            if dismissal
        ]
    )
    identity_lookup = identity_lookup or {
        bowler_id: {
            "canonical_player_id": "test_bowler" if bowler_id == "bowler-1" else bowler_id.replace("-", "_"),
            "canonical_player_name": player_name if bowler_id == "bowler-1" else bowler_id.replace("-", " ").title(),
        }
        for bowler_id in unique_bowler_ids
    }
    return detect_hat_tricks(
        pd.DataFrame(rows),
        matches=matches,
        bowling_scorecard=bowling,
        batting_scorecard=batting,
        selected_team_ids_by_match={current_match_id: {"hawks"} for current_match_id in match_ids},
        identity_lookup=identity_lookup,
    )


def test_three_valid_bowler_wickets_are_confirmed() -> None:
    result = detection(["Bowled", "Caught", "LBW"])
    assert len(result.events) == 1
    assert result.audit.iloc[0]["validation_status"] == "CONFIRMED"


def test_hat_trick_can_span_two_overs() -> None:
    result = detection(["Bowled", "LBW", "Caught"], overs=[4, 4, 7], balls=[5, 6, 1])
    assert len(result.events) == 1
    assert bool(result.events.iloc[0]["spans_overs"])


def test_hat_trick_can_span_two_innings_of_same_match() -> None:
    result = detection(
        ["Bowled", "Caught", "LBW"],
        innings_ids=["innings-1", "innings-1", "innings-3"],
        innings_orders=[1, 1, 3],
        overs=[30, 30, 1],
        balls=[5, 6, 1],
    )
    assert len(result.events) == 1
    assert bool(result.events.iloc[0]["spans_innings"])


def test_sequence_cannot_span_different_matches() -> None:
    result = detection(
        ["Bowled", "Caught", "LBW"],
        match_ids=["match-1", "match-1", "match-2"],
    )
    assert result.events.empty
    assert result.audit.empty


def test_another_bowlers_intervening_over_does_not_break_sequence() -> None:
    result = detection(
        ["Bowled", "Caught", "", "LBW"],
        bowler_ids=["bowler-1", "bowler-1", "other-bowler", "bowler-1"],
        overs=[1, 1, 2, 3],
        balls=[5, 6, 1, 1],
    )
    assert len(result.events) == 1


def test_run_out_interrupts_bowler_wicket_sequence() -> None:
    result = detection(["Bowled", "Run Out", "LBW"])
    assert result.events.empty
    assert result.audit.iloc[0]["validation_status"] == "REJECTED"


def test_non_bowler_dismissal_during_other_bowler_over_does_not_break_sequence() -> None:
    result = detection(
        ["Bowled", "Caught", "Run Out", "LBW"],
        bowler_ids=["bowler-1", "bowler-1", "other-bowler", "bowler-1"],
        overs=[1, 1, 2, 3],
        balls=[5, 6, 1, 1],
    )
    assert len(result.events) == 1


def test_non_bowler_dismissals_do_not_qualify() -> None:
    result = detection(["Retired Out", "Timed Out", "Obstructing the Field"])
    assert result.events.empty
    assert result.audit.iloc[0]["validation_status"] == "REJECTED"


def test_semantic_duplicate_delivery_is_removed() -> None:
    result = detection(["Bowled", "Caught", "Stumped"], duplicate_first=True)
    assert len(result.events) == 1
    assert result.coverage["semantic_duplicate_rows_removed"] == 1


def test_provider_ids_merge_to_same_canonical_bowler() -> None:
    identity = {
        "provider-a": {"canonical_player_id": "one_bowler", "canonical_player_name": "One Bowler"},
        "provider-b": {"canonical_player_id": "one_bowler", "canonical_player_name": "One Bowler"},
    }
    result = detection(
        ["Bowled", "Caught", "LBW"],
        bowler_ids=["provider-a", "provider-a", "provider-b"],
        identity_lookup=identity,
    )
    assert len(result.events) == 1
    assert result.events.iloc[0]["canonical_player_id"] == "one_bowler"


def test_private_player_is_excluded_from_public_events() -> None:
    result = detection(["Bowled", "Caught", "LBW"], player_name="********")
    assert len(result.events) == 1
    assert public_hat_trick_events(result.events).empty


def test_repeated_hat_tricks_by_same_player_remain_separate_events() -> None:
    first = detection(["Bowled", "Caught", "LBW"], match_id="match-1").events
    second = detection(["Bowled", "Caught", "LBW"], match_id="match-2").events
    combined = pd.concat([first, second], ignore_index=True)
    assert combined["canonical_player_id"].nunique() == 1
    assert combined["event_id"].nunique() == 2


def test_non_wicket_delivery_breaks_sequence() -> None:
    result = detection(["Bowled", "", "Caught", "LBW"])
    assert result.events.empty
    assert result.audit.empty


def test_incomplete_innings_can_confirm_locally_supported_sequence() -> None:
    result = detection(["Bowled", "Caught", "LBW"])
    assert result.coverage["eligible_bowling_delivery_rows"] == 3
    assert len(result.events) == 1


def test_plain_wide_by_same_bowler_breaks_sequence() -> None:
    result = detection(
        ["Bowled", "", "Caught", "LBW"],
        legal=[True, False, True, True],
        wides=[0, 1, 0, 0],
    )
    assert result.events.empty


def test_stumped_off_wide_can_count() -> None:
    result = detection(
        ["Bowled", "Stumped", "Caught"],
        legal=[True, False, True],
        wides=[0, 1, 0],
    )
    assert len(result.events) == 1


def test_hit_wicket_off_wide_can_count() -> None:
    result = detection(
        ["Bowled", "Hit Wicket", "Caught"],
        legal=[True, False, True],
        wides=[0, 1, 0],
    )
    assert len(result.events) == 1


def test_plain_no_ball_by_same_bowler_breaks_sequence() -> None:
    result = detection(
        ["Bowled", "", "Caught", "LBW"],
        legal=[True, False, True, True],
        no_balls=[0, 1, 0, 0],
    )
    assert result.events.empty


def test_hit_wicket_on_no_ball_is_not_accepted() -> None:
    result = detection(
        ["Bowled", "Hit Wicket", "Caught"],
        legal=[True, False, True],
        no_balls=[0, 1, 0],
    )
    assert result.events.empty
    assert result.audit.iloc[0]["validation_status"] == "REJECTED"


def test_caught_and_bowled_is_normalized_as_caught() -> None:
    result = detection(["Bowled", "Caught & Bowled", "LBW"])
    assert len(result.events) == 1


def test_deployed_gwhcc_hat_trick_output_matches_completeness_audit() -> None:
    events = pd.read_csv(GWHCC_PROCESSED / "hall_of_fame" / "hat_tricks.csv")
    audit = pd.read_csv(GWHCC_PROCESSED / "validation" / "gwhcc_hat_trick_candidate_audit.csv")
    validation = pd.read_csv(GWHCC_PROCESSED / "validation" / "gwhcc_hat_trick_validation.csv")
    assert len(events) == 1
    assert events.iloc[0]["canonical_player_name"] == "Jai Westbury"
    assert events.iloc[0]["match_id"] == "ae197e36-f830-4dd9-86ba-9e72eb37ddd9"
    assert audit["validation_status"].value_counts().to_dict() == {
        "REJECTED": 6,
        "CONFIRMED": 1,
        "AMBIGUOUS / REVIEW": 1,
    }
    assert validation["status"].ne("FAIL").all()
