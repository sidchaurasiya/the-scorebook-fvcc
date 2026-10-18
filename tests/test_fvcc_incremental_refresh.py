from __future__ import annotations

import pandas as pd
import pytest
from pathlib import Path

from scripts.build_fvcc_incremental_refresh import append_disjoint, scored_participation
from scripts.grdcc_incremental_summaries import merge_summary


def payload(status='COMPLETED', scored=True):
    return {'id':'new-match','status':status,'matchSchedule':[{'startDateTime':'2026-10-10T12:30:00+11:00'}],
            'innings':[{'batting':[{'runsScored':10}]}] if scored else [],
            'teams':[{'id':'fvcc-team','players':[{'participantId':'known-id','name':'Public Player'}]},
                     {'id':'opponent','players':[{'participantId':'other-id','name':'Opponent'}]}]}


@pytest.mark.parametrize('status',['UPCOMING','LIVE','STUMPS','CANCELLED','BYE'])
def test_non_finalized_participation_is_excluded(status):
    with pytest.raises(ValueError,match='Non-finalized'):
        scored_participation([payload(status)],{'fvcc-team'},'2026-10-13T00:53:25+11:00')


def test_future_completed_scorecard_is_rejected():
    with pytest.raises(ValueError,match='after-cutoff'):
        scored_participation([payload()],{'fvcc-team'},'2026-10-09T00:00:00+11:00')


def test_non_scoring_abandonment_does_not_count():
    with pytest.raises(ValueError,match='scored participation'):
        scored_participation([payload('ABANDONED',False)],{'fvcc-team'},'2026-10-13T00:00:00+11:00')


def test_scored_abandonment_retains_supported_participation():
    rows=scored_participation([payload('ABANDONED')],{'fvcc-team'},'2026-10-13T00:00:00+11:00')
    assert rows.player_id.tolist()==['known-id']


def test_source_match_deduplication_and_club_ownership():
    rows=scored_participation([payload(),payload()],{'fvcc-team'},'2026-10-13T00:00:00+11:00')
    assert len(rows)==1
    assert rows.team_id.tolist()==['fvcc-team']


def test_missing_source_identity_fails_closed():
    source=payload()
    source['teams'][0]['players'][0]['participantId']=None
    with pytest.raises(ValueError,match='source participant'):
        scored_participation([source],{'fvcc-team'},'2026-10-13T00:00:00+11:00')


def test_historical_overlap_is_rejected():
    old=pd.DataFrame({'match_id':['existing'],'runs':[20]})
    with pytest.raises(ValueError,match='Overlapping'):
        append_disjoint(old,old.copy(),['match_id'])


def test_historical_key_values_are_retained():
    old=pd.DataFrame({'match_id':['existing'],'runs':[20]})
    new=pd.DataFrame({'match_id':['new'],'runs':[10]})
    result=append_disjoint(old,new,['match_id'])
    pd.testing.assert_frame_equal(result.iloc[:1].reset_index(drop=True),old)


def test_summary_ratios_and_not_out_marker_use_sufficient_statistics():
    old=pd.DataFrame({'id':['player'],'runs':[144.0],'outs':[4.0],'high_score':['144'],'bat_avg':[36.0]})
    new=pd.DataFrame({'id':['player'],'runs':[20.0],'outs':[0.0],'high_score':['20*'],'bat_avg':[None]})
    result=merge_summary(old,new,['id'],{'old-match'},{'new-match'})
    assert result.iloc[0]['high_score']=='144'
    assert result.iloc[0]['runs']==164
    assert result.iloc[0]['bat_avg']==41


def test_unknown_historical_outs_do_not_become_zero():
    old=pd.DataFrame({'id':['player'],'runs':[100.0],'outs':[float('nan')],'bat_avg':[None]})
    new=pd.DataFrame({'id':['player'],'runs':[20.0],'outs':[1.0],'bat_avg':[20.0]})
    result=merge_summary(old,new,['id'],{'old-match'},{'new-match'})
    assert pd.isna(result.iloc[0]['outs'])
    assert pd.isna(result.iloc[0]['bat_avg'])


def test_captain_historical_keys_survive_new_evidence():
    old=pd.DataFrame({'id':['player'],'breakdown_label':['Former Captain'],'runs':[100.0]})
    new=pd.DataFrame({'id':['player'],'breakdown_label':['Current Captain'],'runs':[20.0]})
    result=merge_summary(old,new,['id','breakdown_label'],{'old-match'},{'new-match'})
    assert set(result.breakdown_label)=={'Former Captain','Current Captain'}
    assert result.iloc[0]['runs']==100


def test_verified_current_fvcc_contributions_and_excluded_cancelled_counts():
    root=Path(__file__).resolve().parents[1]/'clubs/fvcc/data/processed'
    cases=[('batting','battingAggregate',539),('bowling','bowlingWickets',30),('fielding','fieldingTotalCatches',12)]
    for kind,metric,expected in cases:
        frame=pd.read_csv(root/f'all_seasons_{kind}.csv')
        current=frame[frame.season.eq('Summer 2026/27')]
        assert len(current)==49
        assert current.matches.sum()==55
        assert current.matches.isin([1,2]).all()
        assert current[metric].sum()==expected
        assert not current.duplicated(['season_id','team_id','player_id']).any()


def test_current_fvcc_prepared_snapshot_matches_public_player_population():
    from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
    from src.ui import layout
    from src.utils.player_identity import filter_public_player_rows
    core=load_prepared_hall_of_fame_core('fvcc',layout.HALL_OF_FAME_DATA_VERSION)
    assert core is not None
    assert len(core['all_time'])==296
    assert len(filter_public_player_rows(core['all_time']))==296
    assert not core['all_time'].canonical_player_id.duplicated().any()


def test_current_fvcc_new_player_and_hs_governance():
    from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
    from src.ui import layout
    core=load_prepared_hall_of_fame_core('fvcc',layout.HALL_OF_FAME_DATA_VERSION)
    career=core['all_time'].set_index('Player')
    assert career.loc['Paul Silva','Runs']==13
    assert career.loc['Paul Silva','Wickets']==2
    assert career.loc['Paul Silva','Matches']==1
    assert career.loc['Danny Singh','HS']=='144'
    assert career.loc['Kalpeshkumar Patel','HS']=='86*'
