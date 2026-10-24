import pandas as pd
import pytest

from scripts.grdcc_incremental_summaries import merge_summary, require_disjoint


def test_overlapping_or_duplicate_matches_are_rejected():
    with pytest.raises(ValueError, match='Overlapping'):
        require_disjoint(['old'], ['old'])
    with pytest.raises(ValueError, match='Duplicate'):
        require_disjoint(['old'], ['new', 'new'])


def test_captain_baseline_and_ratios_preserved():
    old = pd.DataFrame([
        {'id': 'affected', 'dimension': 'Captain', 'runs': 100, 'outs': 4, 'bat_avg': 25},
        {'id': 'unchanged', 'dimension': 'Captain', 'runs': 50, 'outs': 2, 'bat_avg': 25},
    ])
    delta = pd.DataFrame([{'id': 'affected', 'dimension': 'Captain', 'runs': 60, 'outs': 1, 'bat_avg': 60}])
    output = merge_summary(old, delta, ['id', 'dimension'], ['historic'], ['current']).set_index('id')
    assert output.loc['affected', 'runs'] == 160
    assert output.loc['affected', 'bat_avg'] == 32
    pd.testing.assert_series_equal(output.loc['unchanged'], old.set_index('id').loc['unchanged'], check_dtype=False)


def test_unknown_historical_counter_is_not_silently_zero():
    old = pd.DataFrame([{'id': 'p', 'runs': pd.NA}])
    delta = pd.DataFrame([{'id': 'p', 'runs': 12}])
    assert pd.isna(merge_summary(old, delta, ['id'], ['old'], ['new']).runs.iloc[0])


def test_verified_bbb_increment_survives_unavailable_old_coverage():
    old = pd.DataFrame([{'id': 'p', 'runs': pd.NA, 'outs': pd.NA,
                         'bbb_runs': pd.NA, 'bbb_balls_faced': pd.NA,
                         'bbb_dismissals': pd.NA, 'bbb_batting_innings': pd.NA,
                         'bbb_matches': pd.NA, 'strike_rate': pd.NA}])
    delta = pd.DataFrame([{'id': 'p', 'runs': 12, 'outs': 0,
                           'bbb_runs': 12, 'bbb_balls_faced': 10,
                           'bbb_dismissals': 0, 'bbb_batting_innings': 1,
                           'bbb_matches': 1, 'strike_rate': 120}])
    row = merge_summary(old, delta, ['id'], ['old'], ['new']).iloc[0]
    assert row.bbb_runs == 12 and row.bbb_balls_faced == 10
    assert row.bbb_dismissals == 0 and row.bbb_matches == 1
    assert row.bbb_batting_innings == 1 and row.strike_rate == 120
    assert pd.isna(row.runs) and pd.isna(row.outs)


def test_high_score_and_not_out_marker_stay_coupled():
    old = pd.DataFrame([{'id': 'p', 'high_score': '130*', 'high_score_sort': 130, 'high_score_not_out_sort': 1}])
    delta = pd.DataFrame([{'id': 'p', 'high_score': '140', 'high_score_sort': 140, 'high_score_not_out_sort': 0}])
    result = merge_summary(old, delta, ['id'], ['old'], ['new']).iloc[0]
    assert result.high_score == '140'
    assert result.high_score_not_out_sort == 0


def test_public_identity_does_not_inherit_protected_historical_stats():
    from src.ui import layout
    source = pd.DataFrame([
        {'canonical_player_id': 'same-id', 'canonical_player_name': '********', 'Runs': 200},
        {'canonical_player_id': 'same-id', 'canonical_player_name': 'Public Player', 'Runs': 20},
        {'canonical_player_id': 'other-private', 'canonical_player_name': '********', 'Runs': 30},
    ])
    result = layout.exclude_protected_identity_history(source, {'same-id'})
    assert result.Runs.tolist() == [20, 30]
    assert source.Runs.tolist() == [200, 20, 30]


def test_incremental_metadata_matches_published_source_partitions():
    import json
    from pathlib import Path

    root = Path('clubs/georges-river-district/data')
    metadata = json.loads((root / 'metadata.json').read_text())
    for category in ['batting', 'bowling', 'fielding']:
        frame = pd.read_csv(root / 'processed' / f'all_seasons_{category}.csv', usecols=['player_id'])
        assert metadata['stat_rows'][category] == len(frame) == 7975
    assert metadata['players_fetched'] == len(pd.read_csv(root / 'processed/players.csv'))
    assert metadata['teams_fetched'] == len(pd.read_csv(root / 'processed/teams.csv'))
    assert metadata['incremental_refresh']['unique_match_centre_ids'] == 2637
    assert metadata['incremental_refresh']['statistics_bearing_matches'] == 20
