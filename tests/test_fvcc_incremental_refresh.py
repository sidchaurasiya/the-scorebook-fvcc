from __future__ import annotations

import pandas as pd
import pytest
from pathlib import Path

from scripts.build_fvcc_incremental_refresh import add_first_innings_result_context, append_disjoint, merge_same_season_aggregate, scored_participation, validate_same_season_match_partitions
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
    cases=[('batting','battingAggregate',1007),('bowling','bowlingWickets',67),('fielding','fieldingTotalCatches',34)]
    for kind,metric,expected in cases:
        frame=pd.read_csv(root/f'all_seasons_{kind}.csv')
        current=frame[frame.season.eq('Summer 2026/27')]
        assert len(current)==60
        assert current.matches.sum()==98
        assert current.matches.isin([1,2,3]).all()
        assert current[metric].sum()==expected
        assert not current.duplicated(['season_id','team_id','player_id']).any()


def test_current_fvcc_prepared_snapshot_matches_public_player_population():
    from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
    from src.ui import layout
    from src.utils.player_identity import filter_public_player_rows
    core=load_prepared_hall_of_fame_core('fvcc',layout.HALL_OF_FAME_DATA_VERSION)
    assert core is not None
    assert len(core['all_time'])==297
    assert len(filter_public_player_rows(core['all_time']))==297
    assert not core['all_time'].canonical_player_id.duplicated().any()


def test_current_fvcc_new_player_and_hs_governance():
    from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
    from src.ui import layout
    core=load_prepared_hall_of_fame_core('fvcc',layout.HALL_OF_FAME_DATA_VERSION)
    career=core['all_time'].set_index('Player')
    assert career.loc['Paul Silva','Runs']==73
    assert career.loc['Paul Silva','Wickets']==3
    assert career.loc['Paul Silva','Matches']==2
    assert career.loc['Danny Singh','HS']=='144'
    assert career.loc['Kalpeshkumar Patel','HS']=='86*'


def test_same_season_snapshot_adds_verified_roster_matches_and_subtracts_rejected_match(monkeypatch):
    monkeypatch.setenv('CLUB_ID','fvcc')
    season='summer-id'
    old=pd.DataFrame([
        {'season_id':'prior-season','season':'Summer 2025/26','team_id':'team','player_id':'existing-id','player_name':'Public Player','matches':8,'battingInnings':8,'battingAggregate':100,'battingNotOuts':2,'battingBallsFaced':120,'batting50s':1,'batting100s':0,'batting0s':1,'battingFours':10,'battingSixes':2,'battingMinutes':0,'battingHighScore':60,'isBattingHSNotOut':False,'battingAverage':16.67,'battingStrikeRate':83.33},
        {'season_id':season,'season':'Summer 2026/27','team_id':'team','player_id':'existing-id','player_name':'Public Player','raw_player_id':'existing-id','raw_player_name':'Public Player','canonical_player_id':'raw_existing_id','canonical_player_name':'Public Player','matches':2,'battingInnings':2,'battingAggregate':20,'battingNotOuts':1,'battingBallsFaced':30,'batting50s':0,'batting100s':0,'batting0s':0,'battingFours':2,'battingSixes':0,'battingMinutes':0,'battingHighScore':20,'isBattingHSNotOut':True,'battingAverage':20.0,'battingStrikeRate':66.67},
    ])
    current=pd.DataFrame([
        {'season_id':season,'season':'Summer 2026/27','team_id':'team','team_name':'Fiji Victorian 1st XI','grade_id':'grade','grade_name':'Bill Burland Shield','player_id':'existing-id','player_name':'Public Player','matches':5,'battingInnings':4,'battingAggregate':55,'battingNotOuts':2,'battingBallsFaced':48,'batting50s':0,'batting100s':0,'batting0s':1,'battingFours':6,'battingSixes':1,'battingMinutes':0,'battingHighScore':40,'isBattingHSNotOut':False,'battingAverage':55.0,'battingStrikeRate':114.58},
        {'season_id':season,'season':'Summer 2026/27','team_id':'team','team_name':'Fiji Victorian 1st XI','grade_id':'grade','grade_name':'Bill Burland Shield','player_id':'masked-id','player_name':'********','matches':1,'battingInnings':1,'battingAggregate':12,'battingNotOuts':0,'battingBallsFaced':8,'batting50s':0,'batting100s':0,'batting0s':0,'battingFours':1,'battingSixes':0,'battingMinutes':0,'battingHighScore':12,'isBattingHSNotOut':False,'battingAverage':12.0,'battingStrikeRate':150.0},
        {'season_id':season,'season':'Summer 2026/27','team_id':'team','team_name':'Fiji Victorian 1st XI','grade_id':'grade','grade_name':'Bill Burland Shield','player_id':'new-id','player_name':'New Public Player','matches':1,'battingInnings':1,'battingAggregate':2,'battingNotOuts':0,'battingBallsFaced':3,'batting50s':0,'batting100s':0,'batting0s':1,'battingFours':0,'battingSixes':0,'battingMinutes':0,'battingHighScore':2,'isBattingHSNotOut':False,'battingAverage':2.0,'battingStrikeRate':66.67},
    ])
    excluded=pd.DataFrame([
        {'team_id':'team','player_id':'existing-id','battingInnings':1,'battingAggregate':5,'battingNotOuts':0,'battingBallsFaced':6,'batting50s':0,'batting100s':0,'batting0s':0,'battingFours':1,'battingSixes':0,'battingMinutes':0},
        {'team_id':'team','player_id':'masked-id','battingInnings':1,'battingAggregate':12,'battingNotOuts':0,'battingBallsFaced':8,'batting50s':0,'batting100s':0,'batting0s':0,'battingFours':1,'battingSixes':0,'battingMinutes':0},
    ])
    participation=pd.Series([1,1],index=pd.MultiIndex.from_tuples([('team','existing-id'),('team','new-id')]))
    new_batting=pd.DataFrame([{'team_id':'team','participant_id':'existing-id','runs_scored':30,'balls_faced':12,'dismissal_type':'Not Out'},{'team_id':'team','participant_id':'new-id','runs_scored':2,'balls_faced':3,'dismissal_type':'Bowled'}])
    result=merge_same_season_aggregate(old,current,excluded,season_id=season,participation=participation,kind='batting',batting_rows=new_batting,bowling_rows=pd.DataFrame())
    current_result=result[result.season_id.eq(season)].set_index('player_id')
    player=current_result.loc['existing-id']
    assert player.matches==3
    assert player.provider_appearance_count==5
    assert player.battingAggregate==50
    assert player.battingInnings==3
    assert player.battingNotOuts==2
    assert player.battingAverage==50
    assert round(player.battingStrikeRate,2)==119.05
    assert player.battingHighScore==30
    assert bool(player.isBattingHSNotOut)
    assert 'masked-id' not in current_result.index
    assert current_result.loc['new-id','canonical_player_id']=='raw_new_id'
    assert current_result.loc['new-id','canonical_player_name']=='New Public Player'
    assert result[result.season_id.eq('prior-season')].iloc[0].battingAggregate==100


def test_same_season_bowling_best_innings_ignores_rejected_match(monkeypatch):
    monkeypatch.setenv('CLUB_ID','fvcc')
    season='summer-id'
    old=pd.DataFrame([{'season_id':season,'season':'Summer 2026/27','team_id':'team','player_id':'bowler-id','player_name':'Public Bowler','matches':2,'bowlingWickets':2,'bowlingMaidens':0,'bowlingRuns':30,'bowlingBalls':60,'bowling5WIs':0,'bowling10WMs':0,'bowlingBestInnings':'2-10','bowlingAverage':15.0,'bowlingStrikeRate':30.0,'bowlingEconomyRate':3.0,'bowlingWides':0,'bowlingNoBalls':0}])
    current=pd.DataFrame([{'season_id':season,'season':'Summer 2026/27','team_id':'team','team_name':'XI','grade_id':'grade','grade_name':'Grade','player_id':'bowler-id','player_name':'Public Bowler','matches':4,'bowlingWickets':7,'bowlingMaidens':2,'bowlingRuns':60,'bowlingBalls':120,'bowling5WIs':1,'bowling10WMs':0,'bowlingBestInnings':'5-12','bowlingAverage':8.57,'bowlingStrikeRate':17.14,'bowlingEconomyRate':3.0,'bowlingWides':1,'bowlingNoBalls':0}])
    excluded=pd.DataFrame([{'team_id':'team','player_id':'bowler-id','bowlingBalls':24,'bowlingMaidens':1,'bowlingRuns':15,'bowlingWickets':2,'bowling5WIs':0,'bowling10WMs':0,'bowlingWides':1,'bowlingNoBalls':0}])
    participation=pd.Series([1],index=pd.MultiIndex.from_tuples([('team','bowler-id')]))
    new_bowling=pd.DataFrame([{'team_id':'team','participant_id':'bowler-id','innings_id':'new-innings','wickets_taken':3,'runs_conceded':8}])
    result=merge_same_season_aggregate(old,current,excluded,season_id=season,participation=participation,kind='bowling',batting_rows=pd.DataFrame(),bowling_rows=new_bowling)
    player=result.iloc[0]
    assert player.matches==3
    assert player.bowlingWickets==5
    assert player.bowlingRuns==45
    assert player.bowlingBalls==96
    assert player.bowlingBestInnings=='3-8'
    assert round(player.bowlingAverage,2)==9.0


def test_same_season_fielding_keeps_keeper_and_runout_splits(monkeypatch):
    monkeypatch.setenv('CLUB_ID','fvcc')
    season='summer-id'
    old=pd.DataFrame([{'season_id':season,'season':'Summer 2026/27','team_id':'team','player_id':'fielder-id','player_name':'Public Fielder','matches':2,'fieldingCatchesNonWK':1,'fieldingCatchesWK':0,'fieldingTotalCatches':1,'fieldingStumpings':0,'fieldingAssistedRunOuts':0,'fieldingUnassistedRunOuts':0,'fieldingRunOuts':0}])
    current=pd.DataFrame([{'season_id':season,'season':'Summer 2026/27','team_id':'team','team_name':'XI','grade_id':'grade','grade_name':'Grade','player_id':'fielder-id','player_name':'Public Fielder','matches':4,'fieldingCatchesNonWK':2,'fieldingCatchesWK':1,'fieldingTotalCatches':3,'fieldingStumpings':1,'fieldingAssistedRunOuts':1,'fieldingUnassistedRunOuts':1,'fieldingRunOuts':2}])
    excluded=pd.DataFrame([{'team_id':'team','player_id':'fielder-id','fieldingCatchesNonWK':1,'fieldingCatchesWK':0,'fieldingTotalCatches':1,'fieldingStumpings':1,'fieldingAssistedRunOuts':0,'fieldingUnassistedRunOuts':0,'fieldingRunOuts':0}])
    participation=pd.Series([1],index=pd.MultiIndex.from_tuples([('team','fielder-id')]))
    result=merge_same_season_aggregate(old,current,excluded,season_id=season,participation=participation,kind='fielding',batting_rows=pd.DataFrame(),bowling_rows=pd.DataFrame())
    player=result.iloc[0]
    assert player.matches==3
    assert player.fieldingTotalCatches==2
    assert player.fieldingCatchesNonWK==1
    assert player.fieldingCatchesWK==1
    assert player.fieldingStumpings==0
    assert player.fieldingRunOuts==2


def test_same_season_partition_allows_no_excluded_matches():
    assert validate_same_season_match_partitions(
        ['verified-match-1', 'verified-match-2'],
        [],
    ) is None


def test_same_season_partition_rejects_a_match_selected_and_excluded():
    with pytest.raises(ValueError, match='Selected and excluded match IDs overlap'):
        validate_same_season_match_partitions(
            ['same-match'],
            ['same-match'],
        )


def test_official_first_innings_result_context_is_rendered_without_a_margin():
    matches=pd.DataFrame([{'match_id':'official-match','result_text':'Ivanhoe Mavericks 1st XI won'}])
    payload={'id':'official-match','matchSummary':{'resultText':'Ivanhoe Mavericks 1st XI won','teams':[
        {'id':'club','resultType':'LOST_ON_FIRST_INNINGS'},
        {'id':'opponent','resultType':'WON_ON_FIRST_INNINGS'},
    ]}}
    result=add_first_innings_result_context(matches,[payload])
    assert result.loc[0,'result_text']=='Ivanhoe Mavericks 1st XI won on first innings'
    assert matches.loc[0,'result_text']=='Ivanhoe Mavericks 1st XI won'


def test_non_first_innings_result_text_is_unchanged():
    matches=pd.DataFrame([{'match_id':'ordinary-match','result_text':'Other XI won by 5 runs'}])
    payload={'id':'ordinary-match','matchSummary':{'resultText':'Other XI won by 5 runs','teams':[
        {'id':'club','resultType':'LOST'},
        {'id':'opponent','resultType':'WON'},
    ]}}
    result=add_first_innings_result_context(matches,[payload])
    assert result.loc[0,'result_text']=='Other XI won by 5 runs'


def test_first_innings_result_with_official_margin_is_preserved_verbatim():
    matches=pd.DataFrame([{'match_id':'margin-match','result_text':'Other XI won by 2 wickets'}])
    payload={'id':'margin-match','matchSummary':{'resultText':'Other XI won by 2 wickets','teams':[
        {'id':'club','resultType':'LOST_ON_FIRST_INNINGS'},
        {'id':'opponent','resultType':'WON_ON_FIRST_INNINGS'},
    ]}}
    result=add_first_innings_result_context(matches,[payload])
    assert result.loc[0,'result_text']=='Other XI won by 2 wickets'
