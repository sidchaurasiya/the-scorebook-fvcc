import pandas as pd

from scripts.build_season_overview_detail_exports import select_bbb_innings
from src.data.gwhcc_incremental import source_as_recorded_bbb_innings


def test_shared_season_export_default_still_requires_scorecard_parity():
    innings = pd.DataFrame(
        [
            {"scorecard_runs": 42, "scorecard_balls": 40, "bbb_runs": 43, "bbb_balls_faced": 41},
            {"scorecard_runs": 12, "scorecard_balls": 8, "bbb_runs": 12, "bbb_balls_faced": 8},
        ]
    )
    assert select_bbb_innings(innings).tolist() == [False, True]


def make_batting_card(runs=42, balls_faced=40):
    return pd.DataFrame(
        [{
            "season_label": "Summer 2026/27",
            "canonical_player_id": "raw_player",
            "canonical_player_name": "Example Player",
            "display_player_name": "Example Player",
            "match_id": "match-1",
            "innings_id": "innings-1",
            "participant_id": "participant-1",
            "runs_numeric": runs,
            "balls_numeric": balls_faced,
            "out": 0,
            "first_match_day": "2026-10-30",
        }]
    )


def make_delivery_rows(count=41, missing_run_index=None, duplicate_last=False):
    runs = [1] * count
    runs[-1] += 43 - sum(runs)
    rows = []
    cumulative = 0
    for index, run in enumerate(runs):
        cumulative += run
        rows.append({
            "match_id": "match-1",
            "innings_id": "innings-1",
            "striker_participant_id": "participant-1",
            "ball_event_id": f"event-{index}",
            "runs_bat": None if index == missing_run_index else run,
            "wides": 0,
            "striker_runs_scored": cumulative,
            "striker_balls_faced": index + 1,
            "innings_order": index,
            "over_number": index // 6 + 1,
            "ball_number": index % 6 + 1,
        })
    if duplicate_last:
        rows[-1]["ball_event_id"] = rows[-2]["ball_event_id"]
    return pd.DataFrame(rows)


def test_hawks_source_as_recorded_keeps_event_values_despite_scorecard_difference():
    card = make_batting_card(42, 40)
    balls = make_delivery_rows()
    balls.loc[balls.index[-1], "striker_runs_scored"] = 37
    balls.loc[balls.index[-1], "striker_balls_faced"] = 30
    innings = source_as_recorded_bbb_innings(
        card,
        balls,
        ["season_label", "canonical_player_id", "canonical_player_name"],
        runs_column="runs_numeric",
        balls_column="balls_numeric",
        dismissed_column="out",
    )
    assert len(innings) == 1
    assert innings.iloc[0].bbb_runs == 43
    assert innings.iloc[0].bbb_balls_faced == 41
    assert innings.iloc[0].scorecard_runs == 42
    assert innings.iloc[0].scorecard_balls == 40
    assert innings.iloc[0].source_cumulative_runs == 37
    assert innings.iloc[0].source_cumulative_balls == 30


def test_hawks_source_as_recorded_rejects_short_duplicate_or_incomplete_event_sequences():
    card = make_batting_card(42, 40)
    short = make_delivery_rows(count=39)
    duplicate = make_delivery_rows(duplicate_last=True)
    missing = make_delivery_rows(missing_run_index=4)
    args = (["season_label", "canonical_player_id", "canonical_player_name"],)
    kwargs = {
        "runs_column": "runs_numeric",
        "balls_column": "balls_numeric",
        "dismissed_column": "out",
    }
    assert source_as_recorded_bbb_innings(card, short, *args, **kwargs).empty
    assert source_as_recorded_bbb_innings(card, duplicate, *args, **kwargs).empty
    assert source_as_recorded_bbb_innings(card, missing, *args, **kwargs).empty
