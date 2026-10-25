from pathlib import Path

import pandas as pd

from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
from src.ui import layout
from src.utils.player_identity import apply_player_identity_mapping, filter_public_player_rows, public_player_mask


CLUB = 'glen-waverley-hawks'
DATA = Path(__file__).resolve().parents[1] / 'clubs' / CLUB / 'data/processed'
SEASON = 'Summer 2026/27'


def test_current_season_is_official_and_has_thirty_seven_unique_played_matches():
    seasons = pd.read_csv(DATA / 'seasons.csv')
    assert seasons.loc[seasons.name.eq(SEASON), 'id'].tolist() == ['69609582-ba37-4440-9d1e-a38fa912f6d3']
    matches = pd.read_csv(DATA / 'all_seasons_matches.csv')
    assert not matches.match_id.duplicated().any()
    assert len(matches[matches.season.eq(SEASON)]) == 37
    assert len(matches[~matches.season.eq(SEASON)]) == 3475


def test_current_aggregates_use_only_verified_selected_appearances():
    for category in ['batting', 'bowling', 'fielding']:
        frame = pd.read_csv(DATA / f'all_seasons_{category}.csv')
        new = frame[frame.season.eq(SEASON)]
        assert len(new) == 213
        assert new.matches.ge(1).all() and new.matches.le(3).all()
        assert new.matches.sum() == 390
        assert new.raw_playhq_matches.sum() == 400
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
    # Four exact-name merges plus Cam's approved Sunil/Sunny consolidation.
    assert len(career) == career.canonical_player_id.nunique() == 1291
    assert career['Debut Season'].eq(SEASON).sum() == 63
    assert public_player_mask(career).all()


def test_current_profile_index_uses_one_existing_canonical_label(monkeypatch):
    from src.data import playcricket_ingestion
    monkeypatch.setenv('CLUB_ID', CLUB)
    # The candidate is refreshed in place; discard only the local test-process cache.
    playcricket_ingestion._read_processed_table_cached.clear()
    index = layout.load_player_profile_index.__wrapped__(CLUB, layout.metadata_mtime(), layout.player_aliases_mtime())
    assert index.id.is_unique
    assert len(index) == 1291
    for name, canonical_id in [
        ('Chris Briginshaw', 'raw_f62c84ce_8d81_4700_bd22_ee8494bab921'),
        ('Matthew Briginshaw', 'raw_289b8e53_aa95_4072_8288_588447304bcd'),
    ]:
        assert index.loc[index.id.eq(canonical_id), 'name'].tolist() == [name]
    batting = pd.read_csv(DATA / 'all_seasons_batting.csv')
    for canonical_id, raw_name, canonical_name in [
        ('raw_f62c84ce_8d81_4700_bd22_ee8494bab921', 'Briginshaw, Chris', 'Chris Briginshaw'),
        ('raw_289b8e53_aa95_4072_8288_588447304bcd', 'Briginshaw, Matthew', 'Matthew Briginshaw'),
    ]:
        row = batting[batting.canonical_player_id.eq(canonical_id) & batting.season.eq(SEASON)].iloc[0]
        assert row.raw_player_name == raw_name
        assert row.canonical_player_name == canonical_name


def test_current_season_totals_reconcile_across_aggregate_and_scorecard_tables():
    for aggregate, scorecards, aggregate_metric, detail_metric in [
        ('batting','batting','battingAggregate','runs'),
        ('bowling','bowling','bowlingWickets','wickets'),
        ('fielding','fielding','fieldingTotalCatches','catches'),
    ]:
        source = pd.read_csv(DATA / f'all_seasons_{aggregate}.csv')
        detail = pd.read_csv(DATA / f'all_seasons_scorecard_{scorecards}.csv')
        source = filter_public_player_rows(source)
        detail = filter_public_player_rows(detail)
        assert source.loc[source.season.eq(SEASON),aggregate_metric].sum() == detail.loc[detail.season.eq(SEASON),detail_metric].sum()


def test_historical_captain_premiership_and_delivery_records_survive():
    breakdown = pd.read_csv(DATA / 'player_profile/performance_breakdown_by_dimension.csv',low_memory=False)
    # Same contributions, four duplicate identity/dimension groups consolidated.
    assert breakdown.dimension.eq('Captain').sum() == 10226
    assert len(pd.read_csv(DATA / 'hall_of_fame/premiership_wins.csv')) == 24
    assert len(pd.read_csv(DATA / 'hall_of_fame/player_premierships.csv')) == 170
    hats = pd.read_csv(DATA / 'hall_of_fame/hat_tricks.csv')
    assert hats.canonical_player_name.tolist() == ['Jai Westbury']
    fastest = pd.read_csv(DATA / 'hall_of_fame/fastest_batting_milestones.csv')
    assert len(fastest[fastest.season.ne(SEASON)]) == 780


def test_new_partnerships_keep_evidence_and_privacy_gates():
    events = pd.read_csv(DATA / 'partnerships/partnership_events.csv')
    new = events[events.season.eq(SEASON)]
    assert len(new) == 215
    assert new.privacy_status.value_counts().to_dict() == {'PUBLIC_PUBLIC':211,'PUBLIC_PRIVATE':4}
    for position in [1,2]:
        protected = new[f'player_{position}_name'].eq('Private player')
        assert new.loc[protected,f'player_{position}_canonical_id'].fillna('').eq('').all()
    records = pd.read_csv(DATA / 'hall_of_fame/partnership_records.csv')
    assert records.wicket_ordinal_status.eq('CONFIRMED').all()
    assert records.wicket_number.tolist() == list(range(1,11))
    assert not records.season.eq(SEASON).any()


def test_hawks_hs_labels_require_affirmative_not_out_evidence(monkeypatch):
    monkeypatch.setenv('CLUB_ID',CLUB)
    assert layout.format_high_score_text('0') == '0'
    assert layout.format_high_score_text('38') == '38'
    assert layout.format_high_score_text('54*') == '54*'
    for missing in [None,float('nan'),pd.NA,'']:
        assert layout.parse_batting_score('38',missing) == (38,False)
    assert layout.parse_batting_score('38','Bowled') == (38,False)
    assert layout.parse_batting_score('38','Not Out') == (38,True)
    assert layout.parse_batting_score('0','Did Not Bat') == (0,False)


def test_hawks_hs_guard_preserves_current_other_club_contracts(monkeypatch):
    for club in ['fvcc','georges-river-district']:
        monkeypatch.setenv('CLUB_ID',club)
        assert layout.parse_batting_score('38') == (38,False)
        for supplied_missing in [None,float('nan'),pd.NA,'']:
            assert layout.parse_batting_score('38',supplied_missing) == (38,True)
        assert layout.parse_batting_score('38','Not Out') == (38,True)
        assert layout.parse_batting_score('38','Bowled') == (38,False)
        assert layout.parse_batting_score('54*') == (54,True)
        assert layout.parse_batting_score('0','Did Not Bat') == (0,False)
