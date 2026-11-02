import pandas as pd
import hashlib
import json
from src.ui import layout
from src.utils.player_identity import make_player_slug


def test_grdcc_profile_uses_exact_global_canonical_governance(monkeypatch):
    governed = pd.DataFrame([
        {'canonical_player_id':'combined_example','Player':'Example Player','Matches':20,'Runs':186,'Bat SR':float('nan')},
        {'canonical_player_id':'separate_example','Player':'Example Player','Matches':480,'Runs':1000,'Bat SR':50},
    ])
    monkeypatch.setattr(layout, 'get_authoritative_career_totals', lambda *args, **kwargs: governed)
    monkeypatch.setattr(layout, 'metadata_mtime', lambda: 1)
    monkeypatch.setattr(layout, 'player_aliases_mtime', lambda **kwargs: 1)
    monkeypatch.setattr(layout, 'hall_of_fame_override_signature', lambda *args: ())
    stale = pd.DataFrame([{'Player':'Example Player','Matches':480,'Runs':1000,'Bat SR':845.45}])
    result = layout.apply_authoritative_profile_career_totals(stale, {'player_info':{'canonical_player_id':'combined_example'}}, 'georges-river-district')
    assert result.Matches.iloc[0] == 20
    assert result.Runs.iloc[0] == 186
    assert pd.isna(result['Bat SR'].iloc[0])
    separate = layout.apply_authoritative_profile_career_totals(stale, {'player_info':{'canonical_player_id':'separate_example'}}, 'georges-river-district')
    assert separate.Matches.iloc[0] == 480


def test_hof_loader_cache_key_tracks_prepared_manifest(monkeypatch):
    from src.data import grdcc_legacy_composites as governance
    observed = []
    monkeypatch.setattr(governance, 'legacy_ledger_signature', lambda club: ('present', 'synthetic'))
    monkeypatch.setattr(layout, '_load_hall_of_fame_data_cached', lambda *args: observed.append(args) or {})
    for version in ('first', 'second'):
        monkeypatch.setattr(layout, 'prepared_core_manifest_signature', lambda club: (version,))
        layout.load_hall_of_fame_data(1, 1, club_id='georges-river-district')
    assert observed[0][-1] != observed[1][-1]


def test_same_name_modern_profiles_remain_distinct_when_seasons_are_disjoint(monkeypatch):
    monkeypatch.setattr(layout,'get_active_club_id',lambda:'georges-river-district')
    monkeypatch.setattr(layout,'get_feature_flag',lambda *args,**kwargs:True)
    rows=pd.DataFrame([
        {'canonical_player_id':'raw_synthetic_a','player_key':'raw_synthetic_a','Player':'Synthetic Player','Debut Season':'Summer 2023/24','Latest Season':'Summer 2024/25','Runs':20},
        {'canonical_player_id':'raw_synthetic_b','player_key':'raw_synthetic_b','Player':'Synthetic Player','Debut Season':'Summer 2025/26','Latest Season':'Summer 2025/26','Runs':30},
    ])
    result=layout.coalesce_grdcc_exact_name_nonoverlap_all_time(rows)
    assert set(result.canonical_player_id)=={'raw_synthetic_a','raw_synthetic_b'}
    assert result.Runs.sum()==50


def test_historical_only_profiles_retain_existing_coalescing(monkeypatch):
    monkeypatch.setattr(layout,'get_active_club_id',lambda:'georges-river-district')
    monkeypatch.setattr(layout,'get_feature_flag',lambda *args,**kwargs:True)
    rows=pd.DataFrame([
        {'canonical_player_id':'raw_excel_one','player_key':'raw_excel_one','Player':'Synthetic Player','Debut Season':'Summer 1930/31','Latest Season':'Summer 1930/31','Runs':20},
        {'canonical_player_id':'raw_excel_two','player_key':'raw_excel_two','Player':'Synthetic Player','Debut Season':'Summer 1932/33','Latest Season':'Summer 1932/33','Runs':30},
    ])
    result=layout.coalesce_grdcc_exact_name_nonoverlap_all_time(rows)
    assert len(result)==1 and result.Runs.iloc[0]==50


def test_modern_identity_conservation_is_order_independent(monkeypatch):
    monkeypatch.setattr(layout,'get_active_club_id',lambda:'georges-river-district')
    monkeypatch.setattr(layout,'get_feature_flag',lambda *args,**kwargs:True)
    rows=pd.DataFrame([
        {'canonical_player_id':'raw_existing','player_key':'raw_existing','Player':'Synthetic Player','Debut Season':'Summer 2022/23','Latest Season':'Summer 2023/24','Runs':25},
        {'canonical_player_id':'raw_other','player_key':'raw_other','Player':'Synthetic Player','Debut Season':'Summer 2025/26','Latest Season':'Summer 2025/26','Runs':12},
    ])
    for frame in (rows,rows.iloc[::-1]):
        result=layout.coalesce_grdcc_exact_name_nonoverlap_all_time(frame)
        assert set(result.canonical_player_id)=={'raw_existing','raw_other'}


def test_same_name_does_not_change_other_club_outputs(monkeypatch):
    rows=pd.DataFrame([{'canonical_player_id':'raw_a','Player':'Synthetic Player'},
                       {'canonical_player_id':'raw_b','Player':'Synthetic Player'}])
    for club in ('fvcc','glen-waverley-hawks'):
        monkeypatch.setattr(layout,'get_active_club_id',lambda:club)
        pd.testing.assert_frame_equal(layout.coalesce_grdcc_exact_name_nonoverlap_all_time(rows),rows)


def test_approved_group_keeps_overlapping_profile_separate(monkeypatch, tmp_path):
    from src.config import club_config
    monkeypatch.setattr(layout, 'get_active_club_id', lambda: 'georges-river-district')
    monkeypatch.setattr(club_config, 'get_hall_of_fame_dir', lambda **kwargs: tmp_path)
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    ids = ['raw_example_a', 'raw_example_b', 'raw_example_c']
    canonical = 'grdcc_exact_name_' + make_player_slug('Example Player')
    ledger = {'schema_version': 1, 'records': [{'component_id_sha256': [digest(i) for i in ids],
                                               'legacy_id_sha256': digest(canonical)}]}
    (tmp_path / 'legacy_display_composites.json').write_text(json.dumps(ledger))
    rows = pd.DataFrame([
        {'canonical_player_id': i, 'player_key': i, 'Player': 'Example Player',
         'Debut Season': season, 'Latest Season': season, 'Runs': runs}
        for i, season, runs in zip(ids + ['raw_separate'],
                                  ['Summer 2000/01', 'Summer 2002/03', 'Summer 2004/05', 'Summer 2002/03'],
                                  [10, 20, 30, 40])
    ])
    seasons = pd.DataFrame({'canonical_player_id': ids, 'season': ['Summer 2000/01', 'Summer 2002/03', 'Summer 2004/05']})
    for frame in (rows, rows.iloc[::-1]):
        result = layout.coalesce_grdcc_approved_nonoverlap_group(frame, [seasons])
        assert set(result.canonical_player_id) == {canonical, 'raw_separate'}
        assert result.set_index('canonical_player_id').loc[canonical, 'Runs'] == 60
        assert result.set_index('canonical_player_id').loc['raw_separate', 'Runs'] == 40
    rated = rows.assign(**{'Bat Avg': 999.0, 'Bat SR': 999.0, 'Bowl Avg': 999.0, 'Bowl SR': 999.0, 'Econ': 999.0})
    batting = seasons.assign(battingAggregate=[10, 20, 30], battingInnings=[1, 1, 1],
                             battingNotOuts=[0, 1, 0], battingBallsFaced=[10, 10, 10])
    bowling = seasons.assign(bowlingRuns=[10, 10, 10], bowlingWickets=[1, 1, 1], bowlingBalls=[12, 12, 12])
    result = layout.coalesce_grdcc_approved_nonoverlap_group(rated, [batting, bowling]).set_index('canonical_player_id')
    assert result.loc[canonical, 'Bat Avg'] == 30
    assert result.loc[canonical, 'Bat SR'] == 200
    assert result.loc[canonical, 'Bowl Avg'] == 10
    assert result.loc[canonical, 'Bowl SR'] == 12
    assert result.loc[canonical, 'Econ'] == 5
    assert result.loc[canonical, 'Seasons Played'] == 3
    incomplete = batting.copy()
    incomplete.loc[0, 'battingBallsFaced'] = 0
    result = layout.coalesce_grdcc_approved_nonoverlap_group(rated, [incomplete, bowling]).set_index('canonical_player_id')
    assert pd.isna(result.loc[canonical, 'Bat SR'])
    assert result.loc[canonical, 'Runs'] == 60
    for count in (1, 2, 3):
        filtered = pd.concat([rows.iloc[:count], rows.iloc[3:]])
        result = layout.coalesce_grdcc_approved_nonoverlap_group(filtered, [seasons], full_identity_scope=False)
        assert set(result.canonical_player_id) == {canonical, 'raw_separate'}
        assert result.set_index('canonical_player_id').loc[canonical, 'Runs'] == sum([10, 20, 30][:count])
