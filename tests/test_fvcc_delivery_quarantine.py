import pandas as pd
import pytest

from scripts.build_fvcc_incremental_refresh import accepted_delivery_rows, validate_delivery_quarantine, merge_batting_dot_coverage
from pathlib import Path

DATA = Path(__file__).resolve().parents[1] / 'clubs/fvcc/data/processed'
DISPUTED = '68920345-6cdd-4a16-9a20-1eb13967481d'


@pytest.mark.parametrize('consumer', ['balls', 'overs', 'partnerships'])
def test_conflicted_innings_cannot_reenter_delivery_consumer(consumer):
    frames = {k: pd.DataFrame({'innings_id': ['consistent']}) for k in ['balls', 'overs', 'partnerships']}
    frames[consumer] = pd.DataFrame({'innings_id': ['conflicted']})
    with pytest.raises(ValueError, match='Quarantined delivery innings'):
        validate_delivery_quarantine(frames, ['conflicted'])


def test_owner_accepts_scorecard_and_bbb_values_for_their_separate_uses():
    balls = pd.DataFrame({'innings_id':['score-mismatch']*3,'total_runs':[1,2,0]})
    scorecard_runs = 205
    assert balls.total_runs.sum() == 3
    assert scorecard_runs != balls.total_runs.sum()
    retained = accepted_delivery_rows(balls, [])
    pd.testing.assert_frame_equal(retained, balls)


def test_scorecards_and_valid_other_innings_are_preserved():
    frames = {k: pd.DataFrame({'innings_id': ['consistent']}) for k in ['balls', 'overs', 'partnerships']}
    frames['batting'] = pd.DataFrame({'innings_id': ['conflicted'], 'runs': [23], 'balls': [62]})
    before = {k: v.copy() for k, v in frames.items()}
    validate_delivery_quarantine(frames, ['conflicted'])
    for key in frames:
        pd.testing.assert_frame_equal(frames[key], before[key])


def test_owner_approved_source_discrepancy_retains_authentic_records():
    inn = {
        'a0220f78-0e64-4a75-8bca-a8913e7641e0',
        'b9b17601-35dc-4c84-95a3-6de4e1a57493',
        '73c01bbf-2e62-4bd3-86e2-1b966aa608dd',
    }
    partnerships = pd.read_csv(DATA / 'hall_of_fame/partnerships.csv')
    fastest = pd.read_csv(DATA / 'hall_of_fame/fastest_batting_milestones.csv')
    assert len(partnerships[partnerships.innings_id.isin(inn)]) == 16
    assert len(fastest[fastest.innings_id.isin(inn)]) == 2


def test_authentic_delivery_rows_are_not_removed_for_scorecard_difference():
    balls=pd.DataFrame({'innings_id':['mismatch']*669,'ball_event_id':[f'event-{i}' for i in range(669)],'total_runs':[1]*669})
    assert balls.total_runs.sum()==669
    scorecard_runs=667
    assert scorecard_runs!=balls.total_runs.sum()
    retained=accepted_delivery_rows(balls,[])
    assert len(retained)==669
    assert retained.ball_event_id.is_unique
    pd.testing.assert_frame_equal(retained,balls)


def test_scorecard_values_are_not_replaced_by_delivery_reconstruction():
    rows = pd.read_csv(DATA / 'all_seasons_scorecard_batting.csv')
    rows = rows[rows.match_id.eq('4318991d-6757-42d7-b8b9-c94314a2849c')].set_index('player_id')
    assert rows.loc['a0711994-f960-4c71-bea5-c9dd9f3edd83', 'runs'] == 23
    assert rows.loc['b47cab94-0a21-43b5-ace2-ee06304e1880', 'balls'] == 62


def test_accepted_partnership_history_and_other_new_events_remain():
    rows = pd.read_csv(DATA / 'hall_of_fame/partnerships.csv')
    assert len(rows) == 1041
    new_ids=['5d2b32ff-c7c3-4900-81c9-548b1d918ffa','7e3dd365-03c0-4ac7-a601-fc0088327426','e734e2b8-d92b-4760-b9e8-489984e47547','f31cfd8e-4345-4a2a-84e0-5aabf75bafb5']
    assert len(rows[rows.match_id.isin(new_ids)]) == 35
    assert len(rows[rows.match_id.eq('8690c5cd-0280-43d7-936e-b76c3162246e')]) == 8


def test_season_batting_dot_coverage_adds_counts_and_recomputes_percentage():
    old = pd.DataFrame([{'id':'p','scope':'s','bbb_dot_balls':10,'bbb_dot_ball_balls_faced':20,'batting_dot_ball_pct':50}])
    new = pd.DataFrame([{'id':'p','scope':'s','bbb_dot_balls':2,'bbb_dot_ball_balls_faced':10,'batting_dot_ball_pct':20}])
    result = merge_batting_dot_coverage(old, old, new, ['id','scope'])
    assert result.iloc[0].bbb_dot_balls == 12
    assert result.iloc[0].bbb_dot_ball_balls_faced == 30
    assert result.iloc[0].batting_dot_ball_pct == 40
