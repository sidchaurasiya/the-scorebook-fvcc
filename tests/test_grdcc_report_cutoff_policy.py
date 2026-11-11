import pandas as pd
import pytest

from src.data import grdcc_career_refresh as refresh
from src.utils import player_identity as identity


def report(metric='Runs', value=100):
    return pd.DataFrame([{'canonical_player_id':'public_fixture', 'metric':metric,
                          'through_season_start':2024, 'governed_value':value,
                          'scope_type':'all_grades_cumulative', 'status':'source_verified'}])


def test_report_is_authoritative_and_idempotent_not_a_maximum():
    seed=pd.DataFrame([{'canonical_player_id':'public_fixture','metric':'Runs',
                        'through_season_start':2025,'governed_value':900,'correction_applied':False}])
    original=seed.copy(deep=True)
    result=refresh.apply_report_baselines(seed,report())
    assert result.governed_value.iloc[0]==100
    assert result.through_season_start.iloc[0]==2024
    pd.testing.assert_frame_equal(result,refresh.apply_report_baselines(result,report()))
    pd.testing.assert_frame_equal(seed,original)


@pytest.mark.parametrize('column,value',[('scope_type','frank_gray_subset'),('through_season_start',2025)])
def test_subset_or_wrong_cutoff_cannot_be_a_career_baseline(column,value):
    rows=report();rows[column]=value
    with pytest.raises(ValueError,match='scope or season'):
        refresh.apply_report_baselines(pd.DataFrame(),rows)


def test_duplicate_or_unresolved_canonical_is_rejected():
    rows=report()
    with pytest.raises(ValueError,match='Duplicate'):
        refresh.apply_report_baselines(pd.DataFrame(),pd.concat([rows,rows]))
    with pytest.raises(ValueError,match='canonical seed'):
        refresh.apply_report_baselines(pd.DataFrame(columns=['canonical_player_id','metric']),rows)


def test_new_seed_requires_existing_explicit_report_identity_approval():
    empty=pd.DataFrame(columns=['canonical_player_id','metric'])
    rows=report();rows['player_name']='Public Historical Fixture'
    approved=pd.DataFrame([{'status':'MATCHED_EXISTING_CANONICAL_PLAYER','canonical_player_id':'public_fixture','report_name':'Public Historical Fixture'}])
    result=refresh.apply_report_baselines(empty,rows,approved)
    assert len(result)==1 and result.governed_value.iloc[0]==100
    rows['player_name']='Different Same-Name Guess'
    with pytest.raises(ValueError,match='canonical seed'):
        refresh.apply_report_baselines(empty,rows,approved)


@pytest.fixture
def source_boundary(tmp_path,monkeypatch):
    seed=tmp_path/'baseline.csv'
    pd.DataFrame([{'canonical_player_id':'public_fixture','metric':'Runs','through_season_start':2025,'governed_value':900}]).to_csv(seed,index=False)
    report().to_csv(tmp_path/'reviewed_annual_report_baselines.csv',index=False)
    records=[]
    for season,runs,name in [('Summer 2024/25',70,'Public Fixture'),('Summer 2024/25',30,'Public Fixture'),
                             ('Summer 2025/26',20,'Public Fixture'),('Summer 2026/27',3,'Public Fixture'),
                             ('Summer 2025/26',1000,'Private player')]:
        records.append({'canonical_player_id':'public_fixture','player_name':name,'season':season,
                        'battingAggregate':runs,'battingInnings':1,'battingNotOuts':0,
                        'bowlingWickets':0,'bowlingRuns':0,'bowlingBalls':0})
    for category in refresh.METRICS:
        pd.DataFrame(records).to_csv(tmp_path/f'all_seasons_{category}.csv',index=False)
    monkeypatch.setattr(refresh,'BASELINE_PATH',seed)
    monkeypatch.setattr(refresh,'get_processed_path',lambda filename,**kwargs:tmp_path/filename)
    monkeypatch.setattr(identity,'apply_player_identity_mapping',lambda frame,**kwargs:frame)
    refresh._later_totals.cache_clear()
    yield tmp_path
    refresh._later_totals.cache_clear()


def test_2025_and_later_added_once_masked_rows_excluded(source_boundary):
    raw=pd.DataFrame([{'canonical_player_id':'public_fixture','Runs':1200,'Bat Avg':999,'Bat SR':999,
                       'Debut Season':'Summer 2000/01','Latest Season':'Summer 2026/27',
                       'ballByBallBatRuns':12,'ballByBallBatBalls':10}])
    result=refresh.apply_later_season_totals(raw,refresh.CLUB,source_frame=raw)
    assert result.Runs.iloc[0]==123
    assert result['Bat Avg'].iloc[0]==pytest.approx(123/4)
    assert result['Bat SR'].iloc[0]==120
    assert refresh.apply_later_season_totals(result,refresh.CLUB,source_frame=raw).Runs.iloc[0]==123


def test_missing_historical_counters_withhold_rates_not_runs(source_boundary):
    path=source_boundary/'all_seasons_batting.csv';data=pd.read_csv(path)
    data.loc[0,'battingAggregate']=60;data.to_csv(path,index=False)
    raw=pd.DataFrame([{'canonical_player_id':'public_fixture','Runs':999,'Bat Avg':99,'Bat SR':99}])
    result=refresh.apply_later_season_totals(raw,refresh.CLUB,source_frame=raw)
    assert result.Runs.iloc[0]==123
    assert pd.isna(result['Bat Avg'].iloc[0]) and pd.isna(result['Bat SR'].iloc[0])


@pytest.mark.parametrize('club',['fvcc','glen-waverley-hawks'])
def test_other_clubs_remain_exactly_unchanged(source_boundary,club):
    frame=pd.DataFrame([{'canonical_player_id':'public_fixture','Runs':900}])
    pd.testing.assert_frame_equal(frame,refresh.apply_later_season_totals(frame,club,source_frame=frame))


def test_ledger_change_invalidates_cache(source_boundary):
    frame=pd.DataFrame([{'canonical_player_id':'public_fixture','Runs':900}])
    assert refresh.apply_later_season_totals(frame,refresh.CLUB).Runs.iloc[0]==123
    report(value=110).to_csv(source_boundary/'reviewed_annual_report_baselines.csv',index=False)
    assert refresh.apply_later_season_totals(frame,refresh.CLUB).Runs.iloc[0]==133


def test_unknown_report_status_cannot_override():
    seed=pd.DataFrame([{'canonical_player_id':'public_fixture','metric':'Runs','through_season_start':2025,'governed_value':900}])
    rows=report();rows['status']='identity_unresolved'
    assert refresh.apply_report_baselines(seed,rows).governed_value.iloc[0]==900


def test_reviewed_report_target_is_exact_and_invalidates_dependencies(source_boundary):
    rows=report();rows['canonical_player_id']='historical_target';rows['player_name']='Historical Fixture'
    rows.to_csv(source_boundary/'reviewed_annual_report_baselines.csv',index=False)
    frame=pd.DataFrame([{'canonical_player_id':'historical_target','Runs':900},
                        {'canonical_player_id':'unrelated_same_name','Runs':77}])
    with pytest.raises(ValueError,match='canonical seed'):
        refresh.apply_later_season_totals(frame,refresh.CLUB)
    pd.DataFrame([{'report_name':'Historical Fixture','canonical_player_id':'historical_target',
                   'status':'MATCHED_EXISTING_CANONICAL_PLAYER'}]).to_csv(source_boundary/'reviewed_annual_report_identity_targets.csv',index=False)
    assert source_boundary/'reviewed_annual_report_identity_targets.csv' in refresh.refresh_baseline_paths()
    result=refresh.apply_later_season_totals(frame,refresh.CLUB)
    assert result.Runs.tolist()==[100,77]


def test_bowling_rates_recomputed_from_verified_counters(source_boundary):
    seed=pd.DataFrame([{'canonical_player_id':'public_fixture','metric':'Wickets','through_season_start':2025,'governed_value':900}])
    seed.to_csv(source_boundary/'baseline.csv',index=False)
    report(metric='Wickets').to_csv(source_boundary/'reviewed_annual_report_baselines.csv',index=False)
    path=source_boundary/'all_seasons_bowling.csv';data=pd.read_csv(path)
    data['bowlingWickets']=[70,30,20,3,1000]
    data['bowlingRuns']=[140,60,40,6,2000];data['bowlingBalls']=[420,180,120,18,6000]
    data.to_csv(path,index=False)
    frame=pd.DataFrame([{'canonical_player_id':'public_fixture','Wickets':900,'Bowl Avg':99,'Bowl SR':99,'Econ':99,'BBI':'6-20'}])
    result=refresh.apply_later_season_totals(frame,refresh.CLUB,source_frame=frame)
    assert result.Wickets.iloc[0]==123
    assert result['Bowl Avg'].iloc[0]==2 and result['Bowl SR'].iloc[0]==6 and result.Econ.iloc[0]==2
    assert result.BBI.iloc[0]=='6-20'


def test_report_baseline_without_later_play_is_still_authoritative(source_boundary):
    for category in refresh.METRICS:
        path=source_boundary/f'all_seasons_{category}.csv';data=pd.read_csv(path)
        data=data.loc[data.season.eq('Summer 2024/25')];data.to_csv(path,index=False)
    frame=pd.DataFrame([{'canonical_player_id':'public_fixture','Runs':900,'HS':'130*'}])
    result=refresh.apply_later_season_totals(frame,refresh.CLUB,source_frame=frame)
    assert result.Runs.iloc[0]==100 and result.HS.iloc[0]=='130*'
