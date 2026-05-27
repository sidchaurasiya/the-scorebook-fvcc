from __future__ import annotations

import pandas as pd

from src.data.scorecard_validation import filter_plausible_bowling_figures


def test_filter_plausible_bowling_figures_removes_impossible_wicket_counts() -> None:
    rows = pd.DataFrame(
        [
            {"player": "Valid", "wickets": 7, "runs": 22},
            {"player": "Malformed", "wickets": 41, "runs": 0},
        ]
    )

    filtered = filter_plausible_bowling_figures(rows, wickets_column="wickets", runs_column="runs")

    assert list(filtered["player"]) == ["Valid"]


def test_filter_plausible_bowling_figures_preserves_ten_wicket_innings() -> None:
    rows = pd.DataFrame([{"player": "Rare but possible", "wickets": 10, "runs": 14}])

    filtered = filter_plausible_bowling_figures(rows, wickets_column="wickets", runs_column="runs")

    assert len(filtered) == 1
