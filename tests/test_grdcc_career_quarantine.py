import importlib.util
from pathlib import Path
import pandas as pd
import pytest
from src.data import grdcc_career_quarantine as q,featured_record_overrides as overrides
from src.ui import layout


@pytest.fixture
def policy(tmp_path,monkeypatch):
    path=tmp_path/'quarantine.csv'
    pd.DataFrame([{'canonical_player_id':'held_fixture','public_name':'Historical Fixture',
                   'blocked_report_names':'Unverified Fixture;Historical Fixture','status':'public_career_quarantine'}]).to_csv(path,index=False)
    monkeypatch.setattr(q,'PATH',path)
    monkeypatch.setattr(q,'get_active_club_id',lambda:q.CLUB)
    monkeypatch.setattr(layout,'get_active_club_id',lambda:q.CLUB)
    return path


def frame():
    return pd.DataFrame([{'canonical_player_id':'held_fixture','Player':'Unverified Fixture','Runs':2250,'Wickets':227,'Bat Avg':12.5,'Bowl Avg':17.23,'Bowl SR':24.02,'Econ':4.3,'HS':'68','Matches':201},
                         {'canonical_player_id':'other_fixture','Player':'Other Fixture','Runs':3539,'Wickets':10,'Bat Avg':22.54,'Bowl Avg':20.,'Bowl SR':30.,'Econ':4.,'HS':'130*','Matches':172}])


def test_exact_identity_preserved_metrics_masked_idempotently(policy):
    source=frame();original=source.copy(deep=True);out=q.apply_career_quarantine(source,q.CLUB)
    assert out.canonical_player_id.tolist()==source.canonical_player_id.tolist()
    assert out.Player.tolist()==['Historical Fixture','Other Fixture']
    assert out.loc[0,list(q.CAREER_COLUMNS.intersection(out.columns))].isna().all()
    assert out.loc[1,'Runs']==3539 and out.loc[1,'HS']=='130*'
    pd.testing.assert_frame_equal(out,q.apply_career_quarantine(out,q.CLUB))
    pd.testing.assert_frame_equal(source,original)


def test_category_career_aliases_cannot_revive_withheld_values(policy):
    data=frame();data['bowlingEconomyRate']=4.3;data['bowlingBestInnings']='7-20'
    data['high_score']='68';data['catches_display']='12';data['isBattingHSNotOut']=True
    out=q.apply_career_quarantine(data,q.CLUB)
    assert out.loc[0,['bowlingEconomyRate','bowlingBestInnings','high_score','catches_display','isBattingHSNotOut']].isna().all()
    assert out.loc[1,'bowlingEconomyRate']==4.3 and out.loc[1,'high_score']=='68'


@pytest.mark.parametrize('club',['fvcc','glen-waverley-hawks'])
def test_other_clubs_passthrough(policy,club):
    pd.testing.assert_frame_equal(frame(),q.apply_career_quarantine(frame(),club))
    assert not q.blocked_report_names(club)


@pytest.mark.parametrize('club',['fvcc','glen-waverley-hawks'])
def test_explicit_other_club_milestones_do_not_use_grdcc_policy(policy,club):
    data=frame();data.loc[0,'Runs']=1998
    watch=layout.build_approaching_milestone_watchlist(data,club)
    assert watch.loc[watch.Category.eq('Runs')].canonical_player_id.eq('held_fixture').any()


def test_filter_and_threshold_paths_reject_even_unmasked_held_totals(policy):
    data=frame()
    assert q.eligible_career_rows(data,q.CLUB).canonical_player_id.tolist()==['other_fixture']
    watch=layout.build_approaching_milestone_watchlist(data,q.CLUB)
    assert not watch.canonical_player_id.eq('held_fixture').any()
    table=layout.format_all_time_batting_table(data)
    assert len(table)==1
    assert 'held_fixture' not in table.to_csv(index=False)


def test_team_filtered_not_out_enrichment_cannot_restore_withheld_counter(policy,monkeypatch):
    monkeypatch.setattr(layout,'build_all_time_player_table',lambda *args,**kwargs:frame())
    monkeypatch.setattr(layout,'apply_featured_record_overrides',lambda data,**kwargs:q.apply_career_quarantine(data,q.CLUB))
    monkeypatch.setattr(layout,'add_club_not_outs_for_display',lambda data,*args:data.assign(**{'Not Outs':21}))
    data={key:pd.DataFrame() for key in ['batting_raw','bowling_raw','fielding_raw']}
    result=layout.filter_hall_of_fame_data_by_team_group(data,'men')
    held=result['all_time'].loc[result['all_time'].canonical_player_id.eq('held_fixture')]
    assert len(held)==1 and held['Not Outs'].isna().all()


def test_legacy_decision_cannot_create_second_person_or_rename_held_record(policy,monkeypatch):
    decision=pd.DataFrame([{'player_name':'Unverified Fixture','normalized_player_name':'unverified fixture','metric':'career_wickets','displayed_value':227}])
    monkeypatch.setattr(overrides,'load_report_identity_governance',lambda club:pd.DataFrame())
    monkeypatch.setattr(overrides,'load_override_player_supplements',lambda club:pd.DataFrame())
    monkeypatch.setattr(overrides,'load_featured_record_overrides',lambda club:pd.DataFrame())
    monkeypatch.setattr(overrides,'load_annual_report_override_decisions',lambda club:decision)
    monkeypatch.setattr(overrides,'apply_later_season_totals',lambda data,*args,**kwargs:data)
    out=overrides.apply_featured_record_overrides(frame(),q.CLUB)
    assert len(out)==2 and out.Player.iloc[0]=='Historical Fixture' and pd.isna(out.Wickets.iloc[0])


def test_badges_and_highlights_do_not_reconstruct_career_achievements(policy):
    career=q.apply_career_quarantine(frame(),q.CLUB).iloc[0]
    assert layout.player_role_badges(career,{})==[]
    assert q.REVIEW_NOTE in layout.player_profile_insight(career,[])
    assert layout.player_highlight_cards({'career':pd.DataFrame([career])})==[]


def test_signature_changes_when_quarantine_status_changes(policy):
    before=q.quarantine_signature(q.CLUB);source=pd.read_csv(policy)
    source['status']='inactive';source.to_csv(policy,index=False)
    assert q.quarantine_signature(q.CLUB)!=before
    assert not q.quarantine_mask(frame(),q.CLUB).any()


def test_prepared_loader_cache_key_includes_review_policy(policy,monkeypatch):
    calls=[]
    monkeypatch.setattr(layout,'_load_hall_of_fame_data_cached',lambda *args:calls.append(args[-1]))
    layout.load_hall_of_fame_data(0,0,club_id=q.CLUB)
    source=pd.read_csv(policy);source['status']='inactive';source.to_csv(policy,index=False)
    layout.load_hall_of_fame_data(0,0,club_id=q.CLUB)
    assert calls[0]!=calls[1]


def test_builder_rejects_initial_only_bridge_for_reviewed_report(policy):
    path=Path('scripts/build_grdcc_override_player_supplements.py')
    spec=importlib.util.spec_from_file_location('quarantine_builder_test',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    source=pd.DataFrame([{'player_name':'Historical Fixture','short_name':'U Fixture'}])
    prepared=module.prepare_frame(source)
    matched,aliases,_=module.match_rows(prepared,'Unverified Fixture','unverified fixture')
    assert matched.empty and aliases==''


def test_duplicate_quarantine_ids_fail_closed(policy):
    source=pd.read_csv(policy);pd.concat([source,source]).to_csv(policy,index=False)
    with pytest.raises(ValueError,match='unique exact canonical'):
        q.quarantine_rows(q.CLUB)


@pytest.mark.parametrize('metadata',[{}, {'_wicket_override_applies':True,'override_metric':'career_wickets','override_applies':'yes'}])
def test_rate_quarantine_cannot_be_bypassed_by_missing_legacy_metadata(policy,monkeypatch,metadata):
    supplement={'player_name':'Unverified Fixture','normalized_player_name':'unverified fixture',
                'excel_aliases_used':'Historical Fixture','displayed_career_wickets':227,
                'excel_bowling_average':17.23,'excel_bowling_strike_rate':24.02,**metadata}
    monkeypatch.setattr(overrides,'load_override_player_supplements',lambda club:pd.DataFrame([supplement]))
    out=overrides.apply_override_player_supplements(frame(),q.CLUB)
    assert out.loc[0,['Runs','Wickets','Bowl Avg','Bowl SR','Econ']].isna().all()


@pytest.mark.parametrize('with_metadata',[True,False])
def test_supplement_loader_retains_scope_metadata_without_global_stat_changes(tmp_path,monkeypatch,with_metadata):
    row={'player_name':'Example Approved','normalized_player_name':'example approved',
         'excel_aliases_used':'Example Approved','excel_seasons':'Summer 1930/31',
         'matches_source':'innings_proxy','fifties_hundreds_source':'recorded',
         'source_confidence':'high','notes':'synthetic','override_metric':'career_wickets',
         'override_applies':'yes','excel_wickets':184,'displayed_career_wickets':227}
    if not with_metadata:
        row.pop('override_metric');row.pop('override_applies')
    path=tmp_path/'supplements.csv';pd.DataFrame([row]).to_csv(path,index=False)
    monkeypatch.setattr(overrides,'override_player_supplements_path',lambda:path)
    monkeypatch.setattr(overrides,'get_feature_flag',lambda *args,**kwargs:True)
    loaded=overrides.load_override_player_supplements(q.CLUB)
    assert loaded.override_metric.iloc[0]==('career_wickets' if with_metadata else '')
    assert loaded.override_applies.iloc[0]==('yes' if with_metadata else 'no')
    assert bool(loaded['_wicket_override_applies'].iloc[0])==with_metadata
