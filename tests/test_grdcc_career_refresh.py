import pandas as pd
import pytest

from src.data import grdcc_career_refresh as refresh
from src.utils import player_identity as identity


@pytest.fixture
def baseline(tmp_path, monkeypatch):
    path = tmp_path / 'baseline.csv'
    pd.DataFrame([
        {'canonical_player_id': 'public-id', 'metric': 'Runs', 'governed_value': 3981,
         'through_season_start': 2025},
        {'canonical_player_id': 'public-id', 'metric': 'Matches', 'governed_value': 85,
         'through_season_start': 2025},
    ]).to_csv(path, index=False)
    for category in refresh.METRICS:
        pd.DataFrame([
            {'canonical_player_id': 'public-id', 'player_name': 'Public Player',
             'season': 'Summer 2025/26', 'battingAggregate': 100, 'matches': 10},
            {'canonical_player_id': 'public-id', 'player_name': 'Public Player',
             'season': 'Summer 2026/27', 'battingAggregate': 7, 'matches': 2},
        ]).to_csv(tmp_path / f'all_seasons_{category}.csv', index=False)
    monkeypatch.setattr(refresh, 'BASELINE_PATH', path)
    monkeypatch.setattr(refresh, 'get_processed_path', lambda name, **_: tmp_path / name)
    monkeypatch.setattr(identity, 'apply_player_identity_mapping', lambda frame, **_: frame)
    refresh._later_totals.cache_clear()
    yield
    refresh._later_totals.cache_clear()


def test_only_later_seasons_extend_governed_totals(baseline):
    frame = pd.DataFrame([{'canonical_player_id': 'public-id', 'Runs': 3981, 'Matches': 85,
                           'HS': '130*', 'Not Outs': pd.NA}])
    output = refresh.apply_later_season_totals(frame, refresh.CLUB)
    assert output.Runs.iloc[0] == 3988
    assert output.Matches.iloc[0] == 87
    assert output.HS.iloc[0] == '130*'
    assert pd.isna(output['Not Outs'].iloc[0])
    assert frame.Runs.iloc[0] == 3981


@pytest.mark.parametrize('club', ['fvcc', 'glen-waverley-hawks'])
def test_other_clubs_are_unchanged(baseline, club):
    frame = pd.DataFrame([{'canonical_player_id': 'public-id', 'Runs': 12}])
    pd.testing.assert_frame_equal(frame, refresh.apply_later_season_totals(frame, club))


def test_missing_or_duplicate_identity_never_receives_override(baseline):
    frame = pd.DataFrame([{'canonical_player_id': None, 'Runs': 1},
                          {'canonical_player_id': 'public-id', 'Runs': 2},
                          {'canonical_player_id': 'public-id', 'Runs': 3}])
    pd.testing.assert_frame_equal(frame, refresh.apply_later_season_totals(frame, refresh.CLUB))


def test_source_change_invalidates_later_totals(baseline, tmp_path):
    frame = pd.DataFrame([{'canonical_player_id': 'public-id', 'Runs': 3981}])
    assert refresh.apply_later_season_totals(frame, refresh.CLUB).Runs.iloc[0] == 3988
    path = tmp_path / 'all_seasons_batting.csv'
    source = pd.read_csv(path)
    source.loc[source.season.eq('Summer 2026/27'), 'battingAggregate'] = 20
    source.to_csv(path, index=False)
    assert refresh.apply_later_season_totals(frame, refresh.CLUB).Runs.iloc[0] == 4001


def test_existing_exact_name_canonical_ids_remain_stable():
    assert identity.grdcc_exact_canonical_id('mark wall') == 'raw_f4ef8968_9308_4441_a3b0_c4683f91a6a0'
    assert identity.grdcc_exact_canonical_id('fraser lamont') == 'raw_3ffaba70_bd05_4eb2_99f9_92633b0652e5'
    assert identity.grdcc_exact_canonical_id('unlisted player') == 'grdcc_excel_exact_unlisted_player'


def test_modern_source_counters_are_not_frozen_by_partial_excel(baseline):
    presentation = pd.DataFrame([{'canonical_player_id': 'public-id', 'Runs': 3981,
                                  'Matches': 85, 'Bat Avg': 18.31, 'HS': '130*'}])
    source = pd.DataFrame([{'canonical_player_id': 'public-id', 'Runs': 3529,
                           'Matches': 171, 'Bat Avg': 22.6,
                           'Debut Season': 'Summer 2015/16', 'Latest Season': 'Summer 2026/27'}])
    output = refresh.apply_later_season_totals(presentation, refresh.CLUB, source_frame=source)
    assert output.Runs.iloc[0] == 3988
    assert output.Matches.iloc[0] == 171
    assert output['Bat Avg'].iloc[0] == 22.6
    assert output.HS.iloc[0] == '130*'


def test_historical_proxy_is_not_replaced_by_modern_counter_rule(baseline):
    presentation = pd.DataFrame([{'canonical_player_id': 'public-id', 'Runs': 3981, 'Matches': 85}])
    source = pd.DataFrame([{'canonical_player_id': 'public-id', 'Runs': 12, 'Matches': 0,
                           'Debut Season': 'Summer 1930/31', 'Latest Season': 'Summer 2026/27'}])
    assert refresh.apply_later_season_totals(presentation, refresh.CLUB, source_frame=source).Matches.iloc[0] == 87


@pytest.mark.parametrize('club,expected', [('georges-river-district', 'established-id'), ('fvcc', 'public_player'), ('glen-waverley-hawks', 'public_player')])
def test_verified_id_continuity_preserves_scoped_namespace(monkeypatch, club, expected):
    monkeypatch.setattr(identity, 'apply_grdcc_historical_exact_name_mapping', lambda frame, **_: frame)
    frame = pd.DataFrame([{'player_id': 'native-id', 'player_name': 'Public Player'}])
    aliases = pd.DataFrame([{'canonical_player_id': 'established-id', 'canonical_player_name': 'Public Player',
                            'raw_player_id': 'native-id', 'raw_player_name': '', 'alias_name': '', 'is_active': True,
                            'merge_source': 'verified_2026_27_source_id_continuity', 'notes': ''}])
    manual = pd.DataFrame([{'canonical_player_name': 'Public Player', 'raw_player_name': 'Public Player',
                           'raw_player_id': 'native-id', 'notes': 'confirmed same player'}])
    result = identity.apply_player_identity_mapping(frame, aliases, manual_merges_df=manual, club_id=club)
    assert result.canonical_player_id.iloc[0] == expected


def test_conflicting_verified_id_name_is_not_merged(monkeypatch):
    monkeypatch.setattr(identity, 'apply_grdcc_historical_exact_name_mapping', lambda frame, **_: frame)
    frame = pd.DataFrame([{'player_id': 'native-id', 'player_name': 'Different Player'}])
    aliases = pd.DataFrame([{'canonical_player_id': 'established-id', 'canonical_player_name': 'Public Player',
                            'raw_player_id': 'native-id', 'raw_player_name': '', 'alias_name': '', 'is_active': True,
                            'merge_source': 'verified_2026_27_source_id_continuity', 'notes': ''}])
    manual = pd.DataFrame([{'canonical_player_name': 'Different Player', 'raw_player_name': 'Different Player',
                           'raw_player_id': 'native-id', 'notes': ''}])
    with pytest.raises(ValueError, match='conflicts'):
        identity.apply_player_identity_mapping(frame, aliases, manual_merges_df=manual, club_id='georges-river-district')
