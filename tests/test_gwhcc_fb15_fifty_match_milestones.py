from __future__ import annotations

import pandas as pd

from src.ui import layout


CLUB_ID = "glen-waverley-hawks"


def career_rows() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"canonical_player_id": "near_fifty", "Player": "Near Fifty", "Matches": 49.5},
            {"canonical_player_id": "below_range", "Player": "Below Range", "Matches": 39.0},
            {"canonical_player_id": "fifty_club", "Player": "Fifty Club", "Matches": 50.0},
            {"canonical_player_id": "above_fifty", "Player": "Above Fifty", "Matches": 75.5},
            {"canonical_player_id": "hundred_club", "Player": "Hundred Club", "Matches": 112.5},
            {"canonical_player_id": "private", "Player": "********", "Matches": 49.5},
        ]
    )


def test_gwhcc_match_progression_includes_fifty() -> None:
    assert layout.milestone_match_thresholds(CLUB_ID) == [50, 100, 200, 300, 400]
    assert layout.milestone_achievement_specs(CLUB_ID)[0]["thresholds"] == [50, 100, 200, 300, 400, 500, 600]


def test_players_near_fifty_are_shown_with_weighted_values_unchanged() -> None:
    watchlist = layout.build_approaching_milestone_watchlist(career_rows(), CLUB_ID)
    row = watchlist[watchlist["canonical_player_id"].eq("near_fifty")].iloc[0]
    assert row["Current Total"] == 49.5
    assert row["Target Milestone"] == 50
    assert row["Remaining"] == 0.5


def test_players_below_fifty_range_are_excluded() -> None:
    watchlist = layout.build_approaching_milestone_watchlist(career_rows(), CLUB_ID)
    assert "below_range" not in set(watchlist["canonical_player_id"])
    assert layout.highest_reached_threshold(49.5, layout.milestone_match_thresholds(CLUB_ID)) is None


def test_players_above_fifty_remain_in_highest_achieved_band() -> None:
    thresholds = layout.milestone_match_thresholds(CLUB_ID)
    assert layout.highest_reached_threshold(50, thresholds) == 50
    assert layout.highest_reached_threshold(75.5, thresholds) == 50
    assert layout.highest_reached_threshold(112.5, thresholds) == 100


def test_private_players_are_excluded_from_fifty_match_watchlist() -> None:
    watchlist = layout.build_approaching_milestone_watchlist(career_rows(), CLUB_ID)
    assert "private" not in set(watchlist["canonical_player_id"])
    assert not watchlist["Player"].astype(str).str.contains(r"\*{2,}", regex=True).any()


def test_fifty_match_crossing_appears_in_achieved_milestones() -> None:
    historical = {
        "all_time": pd.DataFrame(
            [{"player_key": "crossing", "canonical_player_id": "crossing", "Player": "Crossing Player", "Matches": 50.5}]
        ),
        "batting_raw": pd.DataFrame(
            [
                {
                    "canonical_player_id": "crossing",
                    "canonical_player_name": "Crossing Player",
                    "player_name": "Crossing Player",
                    "season": "Summer 2025/26",
                    "matches": 2.0,
                    "battingAggregate": 0,
                }
            ]
        ),
        "bowling_raw": pd.DataFrame(),
        "fielding_raw": pd.DataFrame(),
    }
    achieved = layout.build_achieved_milestones(historical, ["Summer 2025/26"], CLUB_ID)
    match_rows = achieved[achieved["Category"].eq("Matches")]
    assert match_rows["Threshold"].tolist() == [50]
    assert match_rows.iloc[0]["Milestone"] == "50 matches reached"
    assert match_rows.iloc[0]["Current Total"] == 50.5
    assert "Current total: 50.5 matches" in layout.achievement_card_html(match_rows.iloc[0])


def test_other_clubs_keep_existing_match_thresholds() -> None:
    assert layout.milestone_match_thresholds("fvcc") == [100, 200, 300, 400]
    assert layout.milestone_match_thresholds("georges-river-district", extended=True) == [100, 200, 300, 400, 500, 600]
