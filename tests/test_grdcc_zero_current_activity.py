import pandas as pd
import pytest

from scripts.filter_grdcc_zero_current_activity import CATEGORIES, filter_zero_current_partitions


def _frame(category: str, rows: list[dict[str, object]]) -> pd.DataFrame:
    metric = {
        "batting": "battingAggregate",
        "bowling": "bowlingWickets",
        "fielding": "fieldingCatches",
    }[category]
    return pd.DataFrame(
        [
            {
                "season": "Summer 2026/27",
                "team_id": row.get("team_id", "team-a"),
                "player_id": row["player_id"],
                "canonical_player_id": row.get("canonical_player_id", ""),
                "canonical_player_name": row.get("name", "Player"),
                "matches": row.get("matches", 0),
                metric: row.get(metric, 0),
            }
            for row in rows
        ]
    )


def _scorecard(participant_id: str, team_id: str = "team-a") -> pd.DataFrame:
    return pd.DataFrame([{"participant_id": participant_id, "team_id": team_id}])


def test_only_exactly_unmatched_zero_partitions_are_removed_and_namesakes_stay_separate():
    frames = {
        category: _frame(
            category,
            [
                {"player_id": "historic-zero-current", "name": "Same Name", "matches": 0},
                {"player_id": "exact-current-player", "name": "Same Name", "matches": 1},
            ],
        )
        for category in CATEGORIES
    }
    scorecards = {category: _scorecard("exact-current-player") for category in CATEGORIES}

    filtered, receipt = filter_zero_current_partitions(frames, scorecards, season="Summer 2026/27")

    for category in CATEGORIES:
        assert filtered[category].player_id.tolist() == ["exact-current-player"]
    assert receipt["rows_removed_by_category"] == {category: 1 for category in CATEGORIES}
    assert receipt["numeric_contributions_changed"] is False


def test_zero_aggregate_with_exact_scorecard_participation_requires_reconciliation():
    frames = {category: _frame(category, [{"player_id": "exact-id", "matches": 0}]) for category in CATEGORIES}
    scorecards = {category: pd.DataFrame(columns=["participant_id", "team_id"]) for category in CATEGORIES}
    scorecards["bowling"] = _scorecard("exact-id")

    with pytest.raises(ValueError, match="exact scorecard participant"):
        filter_zero_current_partitions(frames, scorecards, season="Summer 2026/27")


def test_zero_match_row_with_numeric_contribution_is_not_silently_removed():
    frames = {
        category: _frame(
            category,
            [{"player_id": "unmatched-id", "matches": 0, "battingAggregate": 2}],
        )
        for category in CATEGORIES
    }
    scorecards = {category: pd.DataFrame(columns=["participant_id", "team_id"]) for category in CATEGORIES}

    with pytest.raises(ValueError, match="non-zero cricket metrics"):
        filter_zero_current_partitions(frames, scorecards, season="Summer 2026/27")
