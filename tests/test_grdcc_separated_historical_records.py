"""Synthetic governance fixtures; real report figures are independently audited."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

from src.data import grdcc_historical_records as h, grdcc_career_refresh as refresh
from src.data import grdcc_career_quarantine as q
from src.ui import layout


@pytest.fixture
def policy(tmp_path, monkeypatch):
    path=tmp_path/'records.csv'
    rows=[{'record_id':rid,'record_kind':kind,'public_name':name,'metric':metric,
           'value':value,'through_season_start':2024,'scope':scope,'source_reference':'Synthetic reviewed source',
           'status':'source_verified'} for rid,kind,name,metric,value,scope in [
        ('historical_fixture','primary_historical','Historical Fixture','Runs',2208,'all_grades_cumulative'),
        ('historical_fixture','primary_historical','Historical Fixture','Wickets',184,'recorded_worksheet_only'),
        ('report_fixture','annual_report_record','Report Fixture','Wickets',227,'all_grades_cumulative')]]
    pd.DataFrame(rows).to_csv(path,index=False)
    monkeypatch.setattr(h,'PATH',path)
    monkeypatch.setattr(h,'get_active_club_id',lambda:h.CLUB)
    monkeypatch.setattr(layout,'get_active_club_id',lambda:h.CLUB)
    def public_source(category):
        field={'batting':'battingAggregate','bowling':'bowlingWickets'}[category]
        return pd.DataFrame({'canonical_player_id':['historical_fixture']*3,
                             'season':['Summer 2024/25','Summer 2025/26','Summer 2026/27'],
                             field:[1000,0,0]})
    monkeypatch.setattr(refresh,'public_career_source',public_source)
    return path


def source():
    return pd.DataFrame([{'canonical_player_id':'historical_fixture','player_key':'historical_fixture',
        'Player':'Unsupported Fixture','Runs':2250.,'Wickets':227.,'Matches':23.,'Innings':201.,
        'Bowl Avg':17.23,'Bowl SR':24.02,'Econ':4.3,'Bat Avg':12.5,'HS':'68'},
        {'canonical_player_id':'other_fixture','player_key':'other_fixture','Player':'Other Fixture',
         'Runs':3539.,'Wickets':10.,'Matches':172.,'Innings':172.,'Bowl Avg':20.,'Bowl SR':30.,
         'Econ':4.,'Bat Avg':22.54,'HS':'130*'}])


def test_exact_identity_and_report_record_are_distinct(policy):
    original=source();original['Seasons Played']=[15,10]
    out=h.apply_historical_records(original,h.CLUB,add_report_records=True)
    assert out.canonical_player_id.dropna().tolist()==original.canonical_player_id.tolist()
    primary=out.iloc[0];report=out.iloc[2]
    assert primary.Player=='Historical Fixture' and primary.Runs==2208 and primary.Wickets==184
    assert report.Player=='Report Fixture' and report.Wickets==227
    assert pd.isna(report.canonical_player_id) and report.report_record_id=='report_fixture'
    assert report[['Runs','Matches','Innings','Bowl Avg','Bowl SR','Econ','HS']].isna().all()
    assert primary[['Matches','Innings','Bowl Avg','Bowl SR','Econ','Bat Avg','HS']].isna().all()
    assert pd.isna(primary['Seasons Played'])
    pd.testing.assert_frame_equal(original,source().assign(**{'Seasons Played':[15,10]}))
    pd.testing.assert_series_equal(out.iloc[1][original.columns],original.iloc[1],check_names=False,check_dtype=False)


def test_idempotence_order_and_unknown_values(policy):
    out=h.apply_historical_records(source(),h.CLUB,add_report_records=True)
    pd.testing.assert_frame_equal(out,h.apply_historical_records(out,h.CLUB,add_report_records=True))
    other=h.apply_historical_records(source().iloc[::-1],h.CLUB,add_report_records=True)
    pd.testing.assert_frame_equal(out.sort_values('Player').reset_index(drop=True),other.sort_values('Player').reset_index(drop=True))


def test_cutoff_adds_only_public_later_counters_once(policy,monkeypatch):
    monkeypatch.setattr(refresh,'public_career_source',lambda category:pd.DataFrame({
        'canonical_player_id':['historical_fixture']*3,'season':['Summer 2024/25','Summer 2025/26','Summer 2026/27'],
        'battingAggregate':[999,10,7],'bowlingWickets':[999,2,1]}))
    out=h.apply_historical_records(source(),h.CLUB,add_report_records=True)
    assert out.iloc[0].Runs==2225 and out.iloc[0].Wickets==187 and out.iloc[2].Wickets==227
    pd.testing.assert_frame_equal(out,h.apply_historical_records(out,h.CLUB,add_report_records=True))


def test_incomplete_later_counter_fails_closed(policy,monkeypatch):
    monkeypatch.setattr(refresh,'public_career_source',lambda category:pd.DataFrame({
        'canonical_player_id':['historical_fixture'],'season':['Summer 2025/26'],
        'battingAggregate':[float('nan')],'bowlingWickets':[0]}))
    with pytest.raises(ValueError,match='Incomplete eligible'):
        h.apply_historical_records(source(),h.CLUB)


def test_filtered_scope_cannot_publish_whole_career_or_report_identity(policy):
    data=source();data[h.FILTERED_SCOPE]=[True,False]
    out=h.apply_historical_records(data,h.CLUB)
    assert len(out)==2 and out.iloc[0][['Runs','Wickets','Bat Avg','Bowl Avg']].isna().all()
    assert 'filter' in out.iloc[0][h.SOURCE_NOTE]


@pytest.mark.parametrize('club',['fvcc','glen-waverley-hawks'])
def test_other_clubs_unchanged(policy,club):
    pd.testing.assert_frame_equal(source(),h.apply_historical_records(source(),club,add_report_records=True))
    assert h.report_profile_index(club).empty


def test_explicit_ranking_and_minimum_threshold_scope(policy):
    data=h.apply_historical_records(source(),h.CLUB,add_report_records=True)
    assert set(h.ranked_historical_rows(data,'Runs',h.CLUB).Player)=={'Historical Fixture','Other Fixture'}
    assert set(h.ranked_historical_rows(data,'Wickets',h.CLUB).Player)=={'Report Fixture','Other Fixture'}
    assert h.undated_historical_rows(data).Player.tolist()==['Other Fixture']
    text=layout.milestone_club_card_html(data.loc[data.Wickets.ge(100)],100,'wickets','Wickets')
    assert '184 wickets (recorded worksheet minimum)' in text
    assert '227 wickets (Annual Report)' in text and 'player_id=report_fixture' in text
    assert '>2 records</div>' in text


def test_report_profile_links_do_not_use_nan_or_primary_id(policy):
    data=h.apply_historical_records(source(),h.CLUB,add_report_records=True)
    assert layout.player_id_from_row(data.iloc[2])=='report_fixture'
    linked=layout.link_player_column(data[['canonical_player_id','report_record_id','Player']])
    assert 'player_id=historical_fixture' in linked.Player.iloc[0]
    assert 'player_id=report_fixture' in linked.Player.iloc[2] and 'player_id=nan' not in linked.Player.iloc[2]
    labels=layout.player_profile_selector_labels(dict(zip(h.report_profile_index(h.CLUB).id,h.report_profile_index(h.CLUB).name)),h.CLUB)
    assert labels['report_fixture']=='Report Fixture (Annual Report record)'


def test_separated_policy_keeps_legacy_alias_block_but_lifts_whole_mask(policy,tmp_path,monkeypatch):
    path=tmp_path/'quarantine.csv'
    pd.DataFrame([{'canonical_player_id':'historical_fixture','public_name':'Historical Fixture',
       'blocked_report_names':'Unsupported Fixture;Historical Fixture','status':'separated_historical_records'}]).to_csv(path,index=False)
    monkeypatch.setattr(q,'PATH',path)
    assert q.quarantine_rows(h.CLUB).empty
    assert 'unsupported fixture' in q.blocked_report_names(h.CLUB)
    assert q.apply_career_quarantine(source(),h.CLUB).Runs.iloc[0]==2208


def test_missing_separation_ledger_restores_fail_closed_quarantine(policy,tmp_path,monkeypatch):
    path=tmp_path/'quarantine.csv'
    pd.DataFrame([{'canonical_player_id':'historical_fixture','public_name':'Historical Fixture',
       'blocked_report_names':'Unsupported Fixture','status':'separated_historical_records'}]).to_csv(path,index=False)
    monkeypatch.setattr(q,'PATH',path)
    monkeypatch.setattr(h,'PATH',tmp_path/'unavailable.csv')
    result=q.apply_career_quarantine(source(),h.CLUB)
    assert result.iloc[0][['Runs','Wickets','Bat Avg','Bowl Avg']].isna().all()
    assert q.career_under_review(result.iloc[0])


def test_policy_change_invalidates_serving_and_search_cache_keys(policy,monkeypatch):
    first=h.historical_record_signature(h.CLUB)
    data=pd.read_csv(policy);data.loc[0,'source_reference']='Updated verified source';data.to_csv(policy,index=False)
    assert first!=h.historical_record_signature(h.CLUB)
    calls=[]
    monkeypatch.setattr(layout,'_load_player_profile_index_cached',lambda *args:calls.append(args[-1]))
    layout.load_player_profile_index(h.CLUB,0,0)
    data.loc[0,'source_reference']='Another verified source';data.to_csv(policy,index=False)
    layout.load_player_profile_index(h.CLUB,0,0)
    assert calls[0]!=calls[1]


def test_builder_rejects_new_initial_only_full_name_equivalence(monkeypatch):
    spec=importlib.util.spec_from_file_location('separated_builder',Path('scripts/build_grdcc_override_player_supplements.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    from src.data import featured_record_overrides as overrides
    monkeypatch.setattr(overrides,'load_report_identity_governance',lambda club:pd.DataFrame())
    rows=module.prepare_frame(pd.DataFrame({'player_name':['Paula Example','Peter Example']}))
    matched,_,_=module.match_rows(rows,'Paula Example','paula example')
    assert matched.player_name.tolist()==['Paula Example']
    assert module.match_rows(rows,'Phil Example','phil example')[0].empty


def test_reviewed_canonical_alias_remains_supported_without_new_initial_expansion(monkeypatch):
    spec=importlib.util.spec_from_file_location('saved_alias_builder',Path('scripts/build_grdcc_override_player_supplements.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    from src.data import featured_record_overrides as overrides
    monkeypatch.setattr(overrides,'load_report_identity_governance',lambda club:pd.DataFrame([
        {'report_name':'Verified Example','canonical_player_id':'approved_fixture','status':'MATCHED_EXISTING_CANONICAL_PLAYER'}]))
    rows=module.prepare_frame(pd.DataFrame({'player_name':['V Example','Vera Example'],
                                          'canonical_player_id':['approved_fixture','separate_fixture']}))
    matched,_,_=module.match_rows(rows,'Verified Example','verified example')
    assert matched.player_name.tolist()==['V Example']
