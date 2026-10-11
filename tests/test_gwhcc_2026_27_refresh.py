from pathlib import Path

import pandas as pd

from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
from src.ui import layout
from src.utils.player_identity import apply_player_identity_mapping, public_player_mask


CLUB = 'glen-waverley-hawks'
DATA = Path(__file__).resolve().parents[1] / 'clubs' / CLUB / 'data/processed'
SEASON = 'Summer 2026/27'


def test_current_season_is_official_and_has_seventeen_unique_played_matches():
    seasons = pd.read_csv(DATA / 'seasons.csv')
    assert seasons.loc[seasons.name.eq(SEASON), 'id'].tolist() == ['69609582-ba37-4440-9d1e-a38fa912f6d3']
    matches = pd.read_csv(DATA / 'all_seasons_matches.csv')
    assert not matches.match_id.duplicated().any()
    assert len(matches[matches.season.eq(SEASON)]) == 17
    assert len(matches[~matches.season.eq(SEASON)]) == 3475


def test_current_aggregates_use_only_verified_selected_appearances():
    for category in ['batting', 'bowling', 'fielding']:
        frame = pd.read_csv(DATA / f'all_seasons_{category}.csv')
        new = frame[frame.season.eq(SEASON)]
        assert len(new) == 180
        assert new.matches.eq(1).all()
        assert new.matches.sum() == 180
        assert not new.duplicated(['season_id', 'team_id', 'player_id']).any()
        assert new.matches.le(new.raw_playhq_matches).all()


def test_customer_confirmed_new_ids_resolve_to_existing_canonical_identities():
    source = pd.DataFrame({'player_id':['a056fec7-e0c8-45de-9341-dd39999ddfc1','0478a4db-856f-47d2-bb97-fc7383d5c0fd','1bac6d60-8cdc-4f85-89ec-3a6716707cd2'],
                           'player_name':['Jarrod Greaves','Morgan Arundell','Umesh Naga Sashank Katta']})
    mapped = apply_player_identity_mapping(source, club_id=CLUB)
    assert mapped.canonical_player_id.tolist() == ['raw_b8d2d93c_0fc0_4e1f_9671_f1fc051e10d5','raw_84c67d3b_bd0f_4a19_a446_ff1943b60a70','raw_f1bb8d00_986c_4658_867b_df54edce49eb']
    career = pd.read_csv(DATA / 'hall_of_fame/prepared_career_all_time.csv')
    for name in source.player_name:
        assert career.Player.str.casefold().eq(name.casefold()).sum() == 1


def test_prepared_snapshot_is_valid_public_and_contains_historical_population():
    prepared = load_prepared_hall_of_fame_core(CLUB, layout.HALL_OF_FAME_DATA_VERSION)
    assert prepared is not None
    career = prepared['all_time']
    assert len(career) == career.canonical_player_id.nunique() == 1289
    assert career['Debut Season'].eq(SEASON).sum() == 56
    assert public_player_mask(career).all()


def test_current_season_totals_reconcile_across_aggregate_and_scorecard_tables():
    for aggregate, scorecards, aggregate_metric, detail_metric in [
        ('batting','batting','battingAggregate','runs'),
        ('bowling','bowling','bowlingWickets','wickets'),
        ('fielding','fielding','fieldingTotalCatches','catches'),
    ]:
        source = pd.read_csv(DATA / f'all_seasons_{aggregate}.csv')
        detail = pd.read_csv(DATA / f'all_seasons_scorecard_{scorecards}.csv')
        assert source.loc[source.season.eq(SEASON),aggregate_metric].sum() == detail.loc[detail.season.eq(SEASON),detail_metric].sum()


def test_historical_captain_premiership_and_delivery_records_survive():
    breakdown = pd.read_csv(DATA / 'player_profile/performance_breakdown_by_dimension.csv',low_memory=False)
    assert breakdown.dimension.eq('Captain').sum() >= 10203
    assert len(pd.read_csv(DATA / 'hall_of_fame/premiership_wins.csv')) == 24
    assert len(pd.read_csv(DATA / 'hall_of_fame/player_premierships.csv')) == 172
    hats = pd.read_csv(DATA / 'hall_of_fame/hat_tricks.csv')
    assert hats.canonical_player_name.tolist() == ['Jai Westbury']
    fastest = pd.read_csv(DATA / 'hall_of_fame/fastest_batting_milestones.csv')
    assert len(fastest[fastest.season.ne(SEASON)]) == 780


def test_new_partnerships_keep_evidence_and_privacy_gates():
    events = pd.read_csv(DATA / 'partnerships/partnership_events.csv')
    new = events[events.season.eq(SEASON)]
    assert len(new) == 92
    assert new.privacy_status.value_counts().to_dict() == {'PUBLIC_PUBLIC':90,'PUBLIC_PRIVATE':2}
    for position in [1,2]:
        protected = new[f'player_{position}_name'].eq('Private player')
        assert new.loc[protected,f'player_{position}_canonical_id'].fillna('').eq('').all()
    records = pd.read_csv(DATA / 'hall_of_fame/partnership_records.csv')
    assert records.wicket_ordinal_status.eq('CONFIRMED').all()
    assert records.wicket_number.tolist() == list(range(1,11))
    assert not records.season.eq(SEASON).any()
