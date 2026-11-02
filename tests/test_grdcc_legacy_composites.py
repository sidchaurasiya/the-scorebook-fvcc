import copy
import hashlib
import pandas as pd
import pytest

from src.data.grdcc_legacy_composites import approved_component_id_map, approved_nonoverlap_group
from src.ui import layout


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def example():
    components=['raw_synthetic_a','raw_synthetic_b','raw_synthetic_c']
    rows=pd.DataFrame([{'canonical_player_id':item,'Player':'Synthetic Player','Runs':i+1}
                       for i,item in enumerate(components)] + [
        {'canonical_player_id':'raw_unrelated','Player':'Synthetic Player','Runs':100}])
    ledger={'schema_version':1,'records':[{'legacy_id_sha256':digest('grdcc_exact_name_synthetic_player'),
        'component_id_sha256':[digest(item) for item in components],
        'classification':'APPROVED_EXACT_NAME_NONOVERLAP',
        'frozen_values':{'Runs':'6','Matches':'3','Wickets':'0','Catches':'0'}}]}
    return rows,ledger


def test_approved_membership_preserves_sources_and_excludes_namesake():
    rows,ledger=example();before=rows.copy(deep=True)
    result=approved_component_id_map(rows,ledger,club_id='georges-river-district')
    assert set(result)=={'raw_synthetic_a','raw_synthetic_b','raw_synthetic_c'}
    assert set(result.values())=={'grdcc_exact_name_synthetic_player'}
    pd.testing.assert_frame_equal(rows,before)


def test_additive_values_do_not_change_approved_membership():
    rows,ledger=example();rows.loc[0,'Runs']=10000
    assert approved_component_id_map(rows,ledger,club_id='georges-river-district')['raw_synthetic_a']=='grdcc_exact_name_synthetic_player'


def test_component_matching_is_order_independent_and_never_name_only():
    rows,ledger=example()
    assert approved_component_id_map(rows.iloc[::-1],ledger,club_id='georges-river-district')==approved_component_id_map(rows,ledger,club_id='georges-river-district')
    assert 'raw_unrelated' not in approved_component_id_map(rows,ledger,club_id='georges-river-district')


def test_owner_approved_three_are_planned_without_overlapping_fourth():
    rows,ledger=example()
    seasons=pd.DataFrame([
        {'canonical_player_id':'raw_synthetic_a','season':'Summer 2020/21'},
        {'canonical_player_id':'raw_synthetic_b','season':'Summer 2021/22'},
        {'canonical_player_id':'raw_synthetic_c','season':'Summer 2022/23'},
        {'canonical_player_id':'raw_unrelated','season':'Summer 2021/22'},
    ])
    first=approved_nonoverlap_group(rows,[seasons],ledger,club_id='georges-river-district')
    second=approved_nonoverlap_group(rows.iloc[::-1],[seasons.iloc[::-1]],ledger,club_id='georges-river-district')
    assert first==second
    assert set(first[0]['component_ids'])=={'raw_synthetic_a','raw_synthetic_b','raw_synthetic_c'}
    assert 'raw_unrelated' not in first[0]['component_ids']
    assert first[0]['canonical_player_id']=='grdcc_exact_name_synthetic_player'


def test_approved_group_rejects_an_actual_overlapping_season():
    rows,ledger=example()
    seasons=pd.DataFrame([{'canonical_player_id':x,'season':'Summer 2021/22'} for x in
        ['raw_synthetic_a','raw_synthetic_b','raw_synthetic_c']])
    with pytest.raises(ValueError,match='overlapping'):
        approved_nonoverlap_group(rows,[seasons],ledger,club_id='georges-river-district')


def test_private_or_ambiguous_components_fail_closed():
    rows,ledger=example();rows.loc[0,'Player']='********'
    with pytest.raises(ValueError,match='safely'):
        approved_component_id_map(rows,ledger,club_id='georges-river-district')
    rows,ledger=example();rows['is_private']=[True,False,False,False]
    with pytest.raises(ValueError,match='safely'):
        approved_component_id_map(rows,ledger,club_id='georges-river-district')
    rows,ledger=example();rows.loc[0,'Player']='Another Player'
    with pytest.raises(ValueError,match='safely'):
        approved_component_id_map(rows,ledger,club_id='georges-river-district')


def test_invalid_approved_membership_fails_closed():
    rows,ledger=example();bad=copy.deepcopy(ledger);bad['records'][0]['component_id_sha256'].pop()
    with pytest.raises(ValueError,match='invalid'):
        approved_component_id_map(rows,bad,club_id='georges-river-district')


@pytest.mark.parametrize('club',['fvcc','glen-waverley-hawks'])
def test_other_clubs_are_unaffected(club):
    rows,ledger=example()
    assert approved_component_id_map(rows,ledger,club_id=club)=={}


def test_superseded_archive_renderer_is_not_available():
    assert not hasattr(layout, 'render_grdcc_legacy_display_composites')


def test_same_name_profiles_have_distinct_safe_options_and_no_ambiguous_name_fallback():
    names={'synthetic_b':'Synthetic Player','synthetic_a':'Synthetic Player','synthetic_c':'Another Player'}
    labels=layout.player_profile_selector_labels(names,'georges-river-district')
    assert labels['synthetic_a']=='Synthetic Player (record 1)'
    assert labels['synthetic_b']=='Synthetic Player (record 2)'
    assert 'synthetic_a' not in labels['synthetic_a']
    lookup=layout.player_profile_selector_lookup(names,labels)
    assert 'Synthetic Player' not in lookup
    assert lookup['Synthetic Player (record 1)']=='synthetic_a'
    assert lookup['Another Player']=='synthetic_c'


@pytest.mark.parametrize('club',['fvcc','glen-waverley-hawks'])
def test_other_club_selector_labels_are_unchanged(club):
    names={'a':'Same Name','b':'Same Name'}
    assert layout.player_profile_selector_labels(names,club)==names


def test_ambiguous_grdcc_profile_name_is_not_resolved_to_first_match(monkeypatch):
    monkeypatch.setattr(layout,'get_active_club_id',lambda:'georges-river-district')
    monkeypatch.setattr(layout,'load_player_profile_index',lambda *args:pd.DataFrame([{'id':'a','name':'Synthetic Player'},{'id':'b','name':'Synthetic Player'}]))
    monkeypatch.setattr(layout,'metadata_mtime',lambda:0)
    monkeypatch.setattr(layout,'player_aliases_mtime',lambda:0)
    assert layout.profile_player_id_for_name('Synthetic Player')==''


def test_featured_override_does_not_collapse_distinct_canonical_people(monkeypatch):
    from src.data import featured_record_overrides as feature
    rows=pd.DataFrame([{'canonical_player_id':'source-a','Player':'Synthetic Player','Runs':10},
                       {'canonical_player_id':'source-b','Player':'Synthetic Player','Runs':20}])
    overrides=pd.DataFrame([{'player_name':'Synthetic Player','normalized_player_name':'synthetic player',
                             'metric':'career_runs','authoritative_value':100}])
    monkeypatch.setattr(feature,'load_report_identity_governance',lambda club:pd.DataFrame())
    monkeypatch.setattr(feature,'load_override_player_supplements',lambda club:pd.DataFrame())
    monkeypatch.setattr(feature,'load_featured_record_overrides',lambda club:overrides)
    monkeypatch.setattr(feature,'load_annual_report_override_decisions',lambda club:pd.DataFrame())
    monkeypatch.setattr(feature,'load_annual_report_all_time_leaders',lambda club:pd.DataFrame())
    result=feature.apply_featured_record_overrides(rows,club_id='georges-river-district')
    assert set(result.canonical_player_id)=={'source-a','source-b'}
    assert sorted(result.Runs)==[10,20]


def test_ambiguous_blank_identity_is_never_collapsed():
    from src.data.featured_record_overrides import _has_ambiguous_grdcc_identities
    rows=pd.DataFrame([{'canonical_player_id':'source-a'},{'canonical_player_id':''}])
    assert _has_ambiguous_grdcc_identities(rows,'georges-river-district')
    assert not _has_ambiguous_grdcc_identities(rows,'fvcc')


def test_approved_canonical_override_targets_one_person_without_dropping_namesake(monkeypatch):
    from src.data import featured_record_overrides as feature
    rows=pd.DataFrame([{'canonical_player_id':'source-a','Player':'Synthetic Player','Runs':10},
                       {'canonical_player_id':'source-b','Player':'Synthetic Player','Runs':20}])
    decisions=pd.DataFrame([{'report_name':'Synthetic Player','status':'MATCHED_EXISTING_CANONICAL_PLAYER','canonical_player_id':'source-a'}])
    overrides=pd.DataFrame([{'player_name':'Synthetic Player','normalized_player_name':'synthetic player','metric':'career_runs','authoritative_value':100}])
    monkeypatch.setattr(feature,'load_report_identity_governance',lambda club:decisions)
    monkeypatch.setattr(feature,'load_override_player_supplements',lambda club:pd.DataFrame())
    monkeypatch.setattr(feature,'load_featured_record_overrides',lambda club:overrides)
    monkeypatch.setattr(feature,'load_annual_report_override_decisions',lambda club:pd.DataFrame())
    monkeypatch.setattr(feature,'load_annual_report_all_time_leaders',lambda club:pd.DataFrame())
    result=feature.apply_featured_record_overrides(rows,club_id='georges-river-district').set_index('canonical_player_id')
    assert result.loc['source-a','Runs']==100 and result.loc['source-b','Runs']==20


def test_approved_group_profile_and_separate_namesake(monkeypatch,tmp_path):
    import json
    from src.utils import player_identity as identity
    from src.data import grdcc_legacy_composites as legacy
    from src.config import club_config
    ids=['raw_synthetic_a','raw_synthetic_b','raw_synthetic_c','raw_unrelated']
    frames={c:pd.DataFrame([{'canonical_player_id':pid,'canonical_player_name':'Synthetic Player',
        'player_name':'Synthetic Player','raw_player_id':pid,'raw_player_name':'Synthetic Player',
        'season':'Summer 2024/25','team_name':'Team','grade_name':'Grade','battingAggregate':i+1}
        for i,pid in enumerate(ids)]) for c in ('batting','bowling','fielding')}
    _,ledger=example()
    (tmp_path/'legacy_display_composites.json').write_text(json.dumps(ledger))
    monkeypatch.setattr(legacy,'get_hall_of_fame_dir',lambda club_id=None:tmp_path)
    monkeypatch.setattr(club_config,'get_hall_of_fame_dir',lambda club_id=None:tmp_path)
    monkeypatch.setattr(identity,'load_portability_player_profile_source_frames',lambda *args:frames)
    for selected in ids[:3] + ['grdcc_exact_name_synthetic_player']:
        profile=identity.get_player_profile_data(selected,local_version=1,identity_version=1,club_id='georges-river-district')
        assert set(profile['batting'].canonical_player_id)==set(ids[:3])
        assert len(profile['batting'])==3
    profile=identity.get_player_profile_data(ids[3],local_version=1,identity_version=1,club_id='georges-river-district')
    assert set(profile['batting'].canonical_player_id)=={ids[3]}


def test_approved_group_index_and_component_redirect(monkeypatch, tmp_path):
    import json
    from src.config import club_config
    from src.data import grdcc_legacy_composites as legacy
    rows, ledger = example()
    (tmp_path/'legacy_display_composites.json').write_text(json.dumps(ledger))
    monkeypatch.setattr(club_config, 'get_hall_of_fame_dir', lambda club_id=None: tmp_path)
    monkeypatch.setattr(legacy, 'get_hall_of_fame_dir', lambda club_id=None: tmp_path)
    source = rows.rename(columns={'Player':'canonical_player_name'})
    monkeypatch.setattr(layout, 'read_processed_table', lambda name: source.copy())
    monkeypatch.setattr(layout, 'load_player_aliases', lambda **kwargs: pd.DataFrame())
    monkeypatch.setattr(layout, 'apply_player_identity_mapping', lambda frame, aliases, **kwargs: frame)
    index = layout.load_player_profile_index.__wrapped__('georges-river-district', 1, 1, 'synthetic-test')
    target = 'grdcc_exact_name_synthetic_player'
    assert set(index.id) == {target, 'raw_unrelated'}
    assert legacy.redirect_approved_component_id('raw_synthetic_a', set(index.id), club_id='georges-river-district') == target
    assert legacy.redirect_approved_component_id('raw_unrelated', set(index.id), club_id='georges-river-district') == ''
    assert legacy.redirect_approved_component_id('raw_synthetic_a', set(index.id), club_id='fvcc') == ''


def test_missing_legacy_ledger_fails_closed_for_ambiguous_profiles(monkeypatch,tmp_path):
    from src.data import grdcc_legacy_composites as legacy
    monkeypatch.setattr(legacy,'get_hall_of_fame_dir',lambda club_id=None:tmp_path)
    assert legacy.legacy_group_requires_separate_profiles({'a','b'},club_id='georges-river-district')
    assert not legacy.legacy_group_requires_separate_profiles({'a'},club_id='georges-river-district')
    assert not legacy.legacy_group_requires_separate_profiles({'a','b'},club_id='fvcc')


def test_legacy_ledger_signature_changes_on_replacement_and_removal(monkeypatch,tmp_path):
    from src.data import grdcc_legacy_composites as legacy
    monkeypatch.setattr(legacy,'get_hall_of_fame_dir',lambda club_id=None:tmp_path)
    path=tmp_path/'legacy_display_composites.json'
    missing=legacy.legacy_ledger_signature('georges-river-district')
    path.write_text('{"schema_version":1,"records":[]}')
    first=legacy.legacy_ledger_signature('georges-river-district')
    path.write_text('{"schema_version":1,"records":[{}]}')
    second=legacy.legacy_ledger_signature('georges-river-district')
    path.unlink()
    assert missing!=first and first!=second
    assert legacy.legacy_ledger_signature('georges-river-district')==missing
    assert legacy.legacy_ledger_signature('fvcc')==('not-applicable','')


def test_empty_ledger_fails_closed_for_ambiguous_profiles(monkeypatch,tmp_path):
    import json
    from src.data import grdcc_legacy_composites as legacy
    monkeypatch.setattr(legacy,'get_hall_of_fame_dir',lambda club_id=None:tmp_path)
    (tmp_path/'legacy_display_composites.json').write_text(json.dumps({'schema_version':1,'records':[]}))
    assert legacy.legacy_group_requires_separate_profiles({'a','b'},club_id='georges-river-district')
