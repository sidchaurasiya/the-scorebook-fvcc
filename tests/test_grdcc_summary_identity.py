import pandas as pd
import pytest

from src.data import grdcc_summary_identity as bridge


@pytest.fixture
def approved(tmp_path, monkeypatch):
    path = tmp_path / 'approved.csv'
    pd.DataFrame([{'legacy_summary_id': 'old-id', 'canonical_player_id': 'current-id',
                   'canonical_player_name': 'Public Player'}]).to_csv(path, index=False)
    monkeypatch.setattr(bridge, 'PATH', path)
    bridge._aliases.cache_clear()
    yield
    bridge._aliases.cache_clear()


def sample():
    return pd.DataFrame([
        {'canonical_player_id':'old-id','canonical_player_name':'Public Player','display_player_name':'Public Player',
         'dimension':'Captain','discipline':'Batting','breakdown_label':'Captain One','runs':100,'outs':4,'bat_avg':25},
        {'canonical_player_id':'current-id','canonical_player_name':'Public Player','display_player_name':'Public Player',
         'dimension':'Captain','discipline':'Batting','breakdown_label':'Captain One','runs':60,'outs':1,'bat_avg':60},
    ])


def test_old_and_current_captain_history_are_combined_not_masked(approved):
    source = sample()
    result = bridge.read_normalized_summary(source, 'performance_breakdown_by_dimension.csv', 'georges-river-district')
    assert len(result) == 1
    assert result.runs.iloc[0] == 160
    assert result.bat_avg.iloc[0] == 32
    assert source.runs.tolist() == [100,60]


@pytest.mark.parametrize('club',['fvcc','glen-waverley-hawks'])
def test_other_clubs_are_unchanged(approved, club):
    source = sample()
    pd.testing.assert_frame_equal(source, bridge.read_normalized_summary(source,'performance_breakdown_by_dimension.csv',club))


def test_name_conflicts_fail_closed(approved):
    source = sample()
    source.loc[0,'canonical_player_name'] = 'Different Player'
    with pytest.raises(ValueError, match='conflicts'):
        bridge.read_normalized_summary(source,'performance_breakdown_by_dimension.csv','georges-river-district')


def test_chunked_reader_does_not_omit_old_namespace(approved, tmp_path, monkeypatch):
    from src.ui import layout
    monkeypatch.setenv('CLUB_ID','georges-river-district')
    monkeypatch.setattr(layout,'PROFILE_SOURCE_CHUNK_SIZE',1)
    source = sample()
    path = tmp_path / 'performance_breakdown_by_dimension.csv'
    source.to_csv(path,index=False)
    result = layout.read_match_centre_csv_for_player(path,'current-id','public player')
    assert len(result) == 1 and result.runs.iloc[0] == 160


def test_absent_old_bbb_coverage_does_not_erase_verified_current_coverage(approved):
    source = sample()
    source['bbb_runs'] = [pd.NA,12]
    source['bbb_balls_faced'] = [pd.NA,10]
    source['strike_rate'] = [pd.NA,120]
    result = bridge.read_normalized_summary(source,'performance_breakdown_by_dimension.csv','georges-river-district')
    assert result.bbb_runs.iloc[0] == 12
    assert result.bbb_balls_faced.iloc[0] == 10
    assert result.strike_rate.iloc[0] == 120


def test_same_name_without_approved_source_id_is_not_merged(approved):
    source = sample()
    source.loc[0, 'canonical_player_id'] = 'unapproved-id'
    result = bridge.read_normalized_summary(source, 'performance_breakdown_by_dimension.csv', 'georges-river-district')
    assert len(result) == 2
    assert set(result.canonical_player_id) == {'unapproved-id', 'current-id'}


def test_protected_old_namespace_cannot_enter_public_career(approved):
    source = sample()
    source.loc[0, ['canonical_player_name', 'display_player_name']] = '********'
    result = bridge.read_normalized_summary(source, 'performance_breakdown_by_dimension.csv', 'georges-river-district')
    assert len(result) == 1
    assert result.runs.iloc[0] == 60
    assert result.canonical_player_id.iloc[0] == 'current-id'
