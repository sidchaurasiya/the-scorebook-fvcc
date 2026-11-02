import pandas as pd
import pytest

from scripts.build_fvcc_incremental_refresh import validate_delivery_quarantine, merge_batting_dot_coverage
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'clubs/fvcc/data/processed'
DISPUTED = '68920345-6cdd-4a16-9a20-1eb13967481d'


@pytest.mark.parametrize('consumer', ['balls', 'overs', 'partnerships'])
def test_conflicted_innings_cannot_reenter_delivery_consumer(consumer):
    frames = {k: pd.DataFrame({'innings_id': ['consistent']}) for k in ['balls', 'overs', 'partnerships']}
    frames[consumer] = pd.DataFrame({'innings_id': ['conflicted']})
    with pytest.raises(ValueError, match='Quarantined delivery innings'):
        validate_delivery_quarantine(frames, ['conflicted'])


def test_scorecards_and_valid_other_innings_are_preserved():
    frames = {k: pd.DataFrame({'innings_id': ['consistent']}) for k in ['balls', 'overs', 'partnerships']}
    frames['batting'] = pd.DataFrame({'innings_id': ['conflicted'], 'runs': [23], 'balls': [62]})
    before = {k: v.copy() for k, v in frames.items()}
    validate_delivery_quarantine(frames, ['conflicted'])
    for key in frames:
        pd.testing.assert_frame_equal(frames[key], before[key])


@pytest.mark.parametrize('name', ['partnerships.csv', 'fastest_batting_milestones.csv', 'hat_tricks.csv'])
def test_public_delivery_records_exclude_disputed_innings(name):
    rows = pd.read_csv(DATA / 'hall_of_fame' / name)
    assert not rows.get('innings_id', pd.Series(dtype=str)).eq(DISPUTED).any()


def test_scorecard_values_are_not_replaced_by_delivery_reconstruction():
    rows = pd.read_csv(DATA / 'all_seasons_scorecard_batting.csv')
    rows = rows[rows.match_id.eq('4318991d-6757-42d7-b8b9-c94314a2849c')].set_index('player_id')
    assert rows.loc['a0711994-f960-4c71-bea5-c9dd9f3edd83', 'runs'] == 23
    assert rows.loc['b47cab94-0a21-43b5-ace2-ee06304e1880', 'balls'] == 62


def test_accepted_partnership_history_and_other_new_events_remain():
    rows = pd.read_csv(DATA / 'hall_of_fame/partnerships.csv')
    assert len(rows) == 963
    assert len(rows[rows.match_id.isin(['46aac372-eba8-407d-b9e2-b69640f36aef', 'e3690747-8946-449e-afdb-cbc27e8ae537'])]) == 20


def test_season_batting_dot_coverage_adds_counts_and_recomputes_percentage():
    old = pd.DataFrame([{'id':'p','scope':'s','bbb_dot_balls':10,'bbb_dot_ball_balls_faced':20,'batting_dot_ball_pct':50}])
    new = pd.DataFrame([{'id':'p','scope':'s','bbb_dot_balls':2,'bbb_dot_ball_balls_faced':10,'batting_dot_ball_pct':20}])
    result = merge_batting_dot_coverage(old, old, new, ['id','scope'])
    assert result.iloc[0].bbb_dot_balls == 12
    assert result.iloc[0].bbb_dot_ball_balls_faced == 30
    assert result.iloc[0].batting_dot_ball_pct == 40
