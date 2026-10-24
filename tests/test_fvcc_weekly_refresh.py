"""Finalized-only FVCC publication guards, independent of aggregate-feed counts."""
import json
from pathlib import Path

import pandas as pd
import pytest

from scripts.build_fvcc_incremental_refresh import scored_participation
from src.utils.player_identity import filter_public_player_rows

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'clubs/fvcc/data/processed'


@pytest.fixture(scope='module')
def scope():
    return json.loads((ROOT / 'clubs/fvcc/data/metadata.json').read_text())['incremental_refresh']


@pytest.mark.parametrize('status', ['IN PROGRESS', 'LIVE', 'STUMPS', 'BAD LIGHT', 'AWAITING RESULT'])
def test_incomplete_match_cannot_publish_even_with_scoring_figures(status):
    payload = {'id': 'synthetic-incomplete', 'status': status,
        'matchSchedule': [{'startDateTime': '2026-10-17T12:30:00+11:00'}],
        'innings': [{'batting': [{'runsScored': 999999}]}],
        'teams': [{'id': 'club', 'players': [{'participantId': 'public-fixture', 'name': 'Public Fixture'}]}]}
    with pytest.raises(ValueError, match='Non-finalized'):
        scored_participation([payload], {'club'}, '2026-10-18T06:39:14+11:00')


@pytest.mark.parametrize('relative', [
    'all_seasons_matches.csv', 'all_seasons_scorecard_batting.csv',
    'all_seasons_scorecard_bowling.csv', 'all_seasons_scorecard_fielding.csv',
    'season_overview/season_by_round_scorecards.csv', 'player_profile/recent_form_batting.csv',
    'player_profile/recent_form_bowling.csv', 'hall_of_fame/fastest_batting_milestones.csv',
    'hall_of_fame/partnerships.csv',
])
def test_pending_match_ids_are_absent_from_match_outputs(scope, relative):
    frame = pd.read_csv(DATA / relative)
    assert not set(frame.match_id) & set(scope['excluded_incomplete_match_ids'])
    assert not set(frame.match_id) & set(scope.get('excluded_match_ids', []))


def test_round_cards_match_declared_finalized_partition(scope):
    frame = pd.read_csv(DATA / 'season_overview/season_by_round_scorecards.csv')
    current = frame[frame.season.eq('Summer 2026/27')]
    assert not current.match_id.duplicated().any()
    assert set(current.match_id) == set(scope['current_finalized_match_ids'])
    assert set(scope['new_match_ids']) <= set(current.match_id)
    assert set(scope['new_match_ids']) == {
        '22342e82-4bc8-4dfa-ba67-5d9cb831247d',
        'd454dfb9-b61d-4382-b6d2-f75594461198',
        '3a3a57d1-9dcf-483d-b16b-fc7d372f7bd6',
    }
    assert scope.get('excluded_match_ids') == ['6175cdef-3b87-4450-a00d-2b381f4324f7']


def test_appearances_follow_public_finalized_scorecards_not_provider_counts(scope):
    aggregate = pd.read_csv(DATA / 'all_seasons_batting.csv')
    aggregate = aggregate[aggregate.season.eq('Summer 2026/27')]
    # The selected XI is authoritative for appearances: some scorecards omit
    # unneeded DNB batting lines, which must not erase a verified appearance.
    expected = pd.Series(scope['verified_public_appearance_counts'])
    actual = aggregate.groupby('canonical_player_id').matches.sum()
    pd.testing.assert_series_equal(actual.sort_index(), expected.sort_index(), check_dtype=False, check_names=False)
    assert aggregate.provider_appearance_count.ge(aggregate.matches).all()


@pytest.mark.parametrize('kind,source_metric,aggregate_metric', [
    ('batting', 'runs', 'battingAggregate'), ('bowling', 'wickets', 'bowlingWickets'),
    ('fielding', 'catches', 'fieldingTotalCatches'),
])
def test_each_current_statistic_matches_finalized_scorecards(kind, source_metric, aggregate_metric):
    aggregate = pd.read_csv(DATA / f'all_seasons_{kind}.csv')
    aggregate = aggregate[aggregate.season.eq('Summer 2026/27')]
    source = pd.read_csv(DATA / f'all_seasons_scorecard_{kind}.csv')
    source = filter_public_player_rows(source[source.season.eq('Summer 2026/27')])
    expected = source.groupby('player_id')[source_metric].sum()
    actual = aggregate.groupby('player_id')[aggregate_metric].sum()
    pd.testing.assert_series_equal(actual.sort_index(), expected.reindex(actual.index).fillna(0).sort_index(), check_dtype=False, check_names=False)


def test_provider_counts_cannot_inflate_batting_average_or_innings():
    frame = pd.read_csv(DATA / 'all_seasons_batting.csv')
    current = frame[frame.season.eq('Summer 2026/27')]
    outs = current.battingInnings - current.battingNotOuts
    comparable = outs.gt(0) & current.battingAverage.notna()
    calculated = current.battingAggregate / outs.where(outs.gt(0))
    assert (calculated[comparable] - current.loc[comparable, 'battingAverage']).abs().le(.05).all()
    assert current.battingNotOuts.le(current.battingInnings).all()


def test_raw_provenance_and_canonical_identities_cannot_collapse():
    for kind in ['batting', 'bowling', 'fielding']:
        frame = pd.read_csv(DATA / f'all_seasons_{kind}.csv')
        current = frame[frame.season.eq('Summer 2026/27')]
        assert current.raw_player_id.notna().all()
        assert current.raw_player_name.notna().all()
        assert current.canonical_player_id.notna().all()
        assert not current.canonical_player_id.eq('unknown_player').any()
        assert len(filter_public_player_rows(current)) == len(current)


def test_not_outs_complete_coverage_is_retained():
    batting = pd.read_csv(DATA / 'all_seasons_batting.csv')
    assert batting.battingNotOuts.notna().all()
    assert batting.battingNotOuts.le(batting.battingInnings).all()
