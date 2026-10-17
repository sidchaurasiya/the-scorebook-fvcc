"""Committed current-season publication invariants; no raw-cache reconstruction."""
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'clubs/georges-river-district/data/processed'


def test_published_current_match_ids_are_unique_and_match_metadata():
    metadata = json.loads((DATA.parent / 'metadata.json').read_text())['incremental_refresh']
    rounds = pd.read_csv(DATA / 'season_overview/season_by_round_scorecards.csv')
    current = rounds.loc[rounds.season.eq(metadata['season'])]
    assert not current.match_id.duplicated().any()
    assert set(current.match_id) == set(metadata['finalized_match_ids'])
    assert not set(current.match_id) & set(rounds.loc[~rounds.season.eq(metadata['season']), 'match_id'])
    assert rounds.match_id.nunique() == metadata['unique_match_centre_ids']


def test_current_primary_partitions_have_positive_verified_participation():
    for category in ['batting', 'bowling', 'fielding']:
        frame = pd.read_csv(DATA / f'all_seasons_{category}.csv', low_memory=False)
        current = frame.loc[frame.season.eq('Summer 2026/27')]
        assert pd.to_numeric(current.matches, errors='raise').gt(0).all()
        assert not current.duplicated(['player_id', 'team_id']).any()


def test_prepared_anchors_and_canonical_uniqueness():
    career = pd.read_csv(DATA / 'hall_of_fame/prepared_career_all_time.csv')
    assert not career.canonical_player_id.dropna().duplicated().any()
    assert career.loc[career.Player.eq('Nick Condylios'), 'HS'].tolist() == ['130*']
    assert career.loc[career.Player.eq('Harry Milburn'), 'HS'].tolist() == ['110']


def test_retained_hat_tricks_and_private_partner_public_contract():
    hats = pd.read_csv(DATA / 'hall_of_fame/hat_tricks.csv')
    assert len(hats) >= 6 and not hats.event_id.duplicated().any()
    records = pd.read_csv(DATA / 'hall_of_fame/partnership_records.csv')
    assert len(records) == 10 and set(records.wicket_number) == set(range(1, 11))
    assert not records.privacy_status.eq('PRIVATE_PRIVATE').any()
    ninth = records.loc[records.wicket_number.eq(9)].iloc[0]
    assert ninth.partnership_runs == 94
    assert 'Private player' in [ninth.batter_1_public_name, ninth.batter_2_public_name]


def test_returning_players_follow_existing_primary_career_governance():
    from src.data.featured_record_overrides import apply_featured_record_overrides

    career = apply_featured_record_overrides(
        pd.read_csv(DATA / 'hall_of_fame/prepared_career_all_time.csv'),
        club_id='georges-river-district',
    )
    for name, matches in [('Gavin Scott', 322), ('Peter Remfrey', 391), ('Kevin Croom', 442)]:
        row = career.loc[career.Player.eq(name)]
        assert len(row) == 1
        assert row.Matches.iloc[0] == matches
