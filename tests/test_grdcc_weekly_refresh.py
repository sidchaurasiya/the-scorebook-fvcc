"""Committed current-season publication invariants; no raw-cache reconstruction."""
import json
from pathlib import Path

import pandas as pd

from match_centre_source_snapshot import weekly_source_manifest

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
    expected = weekly_source_manifest()["career_anchors"]
    # The 16 November official scorecards add one verified appearance for
    # Peter Remfrey and Kevin Croom; Gavin Scott's accepted total is unchanged.
    for name, matches in [('Gavin Scott', 322), ('Peter Remfrey', 393), ('Kevin Croom', 444)]:
        row = career.loc[career.Player.eq(name)]
        assert len(row) == 1
        assert row.Matches.iloc[0] == expected[name]["matches"] == matches


def test_weekly_population_and_grdcc_career_anchors_match_source_fingerprint():
    expected = weekly_source_manifest()
    metadata = json.loads((DATA.parent / 'metadata.json').read_text())
    career = pd.read_csv(DATA / 'hall_of_fame/prepared_career_all_time.csv')
    assert len(pd.read_csv(DATA / 'all_seasons_batting.csv')) == expected['stat_rows_per_discipline']
    assert len(pd.read_csv(DATA / 'all_seasons_bowling.csv')) == expected['stat_rows_per_discipline']
    assert len(pd.read_csv(DATA / 'all_seasons_fielding.csv')) == expected['stat_rows_per_discipline']
    assert metadata['incremental_refresh']['unique_match_centre_ids'] == expected['unique_match_centre_ids']
    assert len(metadata['incremental_refresh']['finalized_match_ids']) == expected['current_match_count']
    assert int(career.canonical_player_id.notna().sum()) == expected['canonical_identity_count']
    assert len(career) == expected['governed_display_record_count']
    for name, values in expected['career_anchors'].items():
        rows = career.loc[career.Player.eq(name)]
        if values.get('report_only'):
            rows = rows.loc[rows.report_record_id.eq('report_grdcc_annual_2024_25_phil_eldridge')]
        assert len(rows) == 1
        for metric, value in values.items():
            column = {'runs': 'Runs', 'wickets': 'Wickets', 'matches': 'Matches'}.get(metric)
            if column:
                assert float(rows.iloc[0][column]) == value


def test_rebuilt_public_summary_rows_and_premiership_flags_match_source_snapshot():
    expected = weekly_source_manifest()
    paths = {
        "fastest_batting_milestones": DATA / "hall_of_fame/fastest_batting_milestones.csv",
        "player_scorecard_milestones": DATA / "hall_of_fame/player_scorecard_milestones.csv",
        "player_win_rates": DATA / "hall_of_fame/player_win_rates.csv",
        "scorecard_record_links": DATA / "hall_of_fame/scorecard_record_links.csv",
        "batting_position_summary": DATA / "player_profile/batting_position_summary.csv",
        "bowling_phase_summary": DATA / "player_profile/bowling_phase_summary.csv",
        "dismissal_fingerprint_summary": DATA / "player_profile/dismissal_fingerprint_summary.csv",
        "performance_breakdown_by_dimension": DATA / "player_profile/performance_breakdown_by_dimension.csv",
        "recent_form_batting": DATA / "player_profile/recent_form_batting.csv",
        "recent_form_bowling": DATA / "player_profile/recent_form_bowling.csv",
        "bbb_batting_rates_by_scope": DATA / "season_overview/bbb_batting_rates_by_scope.csv",
        "bbb_bowling_dot_rates_by_scope": DATA / "season_overview/bbb_bowling_dot_rates_by_scope.csv",
        "scorecard_batting_milestones_by_scope": DATA / "season_overview/scorecard_batting_milestones_by_scope.csv",
        "scorecard_bowling_milestones_by_scope": DATA / "season_overview/scorecard_bowling_milestones_by_scope.csv",
        "season_by_round_scorecards": DATA / "season_overview/season_by_round_scorecards.csv",
    }
    for name, path in paths.items():
        assert len(pd.read_csv(path, low_memory=False)) == expected["derived_public_output_rows"][name]

    rounds = pd.read_csv(paths["season_by_round_scorecards"], low_memory=False)
    assert rounds.match_id.is_unique
    flagged = set(rounds.loc[rounds.is_premiership.fillna(False).astype(bool), "match_id"].astype(str))
    assert flagged == set(expected["premiership_match_ids"])
    assert len(flagged) == expected["premiership_match_count"] == 16
