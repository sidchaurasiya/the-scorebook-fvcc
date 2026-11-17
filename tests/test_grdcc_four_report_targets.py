from unittest.mock import patch
import pandas as pd
import pytest

from src.data import grdcc_career_refresh as refresh
from src.data.featured_record_overrides import apply_featured_record_overrides

CASES={'Bruce Carrington':3524,'Peter Huthnance':3240,'Ian Fleming':2558}


@pytest.fixture(scope='module')
def reviewed_outputs(tmp_path_factory):
    core=pd.read_csv('clubs/georges-river-district/data/processed/hall_of_fame/prepared_career_all_time.csv')
    reports=pd.read_csv(refresh.report_baselines_path())
    assert len(reports)==99
    assert len(reports.loc[reports.status.eq('source_verified')])==98
    original=reports.loc[~reports.player_name.isin(CASES)]
    assert len(original)==96
    path=tmp_path_factory.mktemp('prior_report_review')/'reports.csv';original.to_csv(path,index=False)
    with patch.object(refresh,'report_baselines_path',lambda:path):
        before=apply_featured_record_overrides(core,refresh.CLUB)
    after=apply_featured_record_overrides(core,refresh.CLUB)
    return core,reports,before,after


@pytest.mark.parametrize('name,total',CASES.items())
def test_named_report_performance_targets_only_existing_batting_career(reviewed_outputs,name,total):
    core,reports,before,after=reviewed_outputs
    target=reports.loc[reports.player_name.eq(name)&reports.metric.eq('Runs'),'canonical_player_id'].iloc[0]
    assert len(core.loc[core.canonical_player_id.eq(target)])==1
    row=after.loc[after.canonical_player_id.eq(target)];assert len(row)==1 and row.Runs.iloc[0]==total
    other_before=before.loc[before.Player.eq(name)&~before.canonical_player_id.eq(target)].reset_index(drop=True)
    other_after=after.loc[after.Player.eq(name)&~after.canonical_player_id.eq(target)].reset_index(drop=True)
    pd.testing.assert_frame_equal(other_before,other_after)
    assert before.canonical_player_id.fillna('').tolist()==after.canonical_player_id.fillna('').tolist()


def test_previously_reviewed_players_outside_new_targets_are_unchanged(reviewed_outputs):
    _,reports,before,after=reviewed_outputs
    targets=set(reports.loc[reports.player_name.isin(CASES),'canonical_player_id'])
    pd.testing.assert_frame_equal(before.loc[~before.canonical_player_id.isin(targets)].reset_index(drop=True),
                                  after.loc[~after.canonical_player_id.isin(targets)].reset_index(drop=True))


def test_separately_governed_report_and_worksheet_records_preserve_original_sources(reviewed_outputs):
    core,reports,_,after=reviewed_outputs
    held=reports.loc[reports.player_name.eq('Phil Eldridge')]
    assert len(held)==1 and held.status.iloc[0]=='identity_unresolved'
    assert not reports.player_name.eq('Percy Eldridge').any()
    target=held.canonical_player_id.iloc[0]
    assert core.loc[core.canonical_player_id.eq(target),'Runs'].iloc[0]==2208
    historical_records = pd.read_csv(
        'clubs/georges-river-district/data/source/separated_historical_records.csv'
    )
    percy_records = historical_records.loc[
        historical_records.record_id.eq('grdcc_excel_exact_percy_eldridge')
    ]
    assert set(percy_records.record_kind) == {'primary_historical'}
    assert set(percy_records.public_name) == {'Percy Eldridge'}
    assert percy_records.loc[percy_records.metric.eq('Runs'), 'value'].tolist() == [2208]
    assert percy_records.loc[percy_records.metric.eq('Wickets'), 'scope'].tolist() == [
        'recorded_worksheet_only'
    ]

    worksheet = pd.read_csv(
        'clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_batting.csv'
    )
    percy_worksheet = worksheet.loc[
        worksheet.player_name.eq('Percy Eldridge')
        & worksheet.source_file.eq('bexley_stats_spreadsheets.xlsx')
        & worksheet.source_sheet.notna()
    ]
    assert len(percy_worksheet) == 20
    assert percy_worksheet.season.nunique() == 14
    assert pd.to_numeric(percy_worksheet.battingAggregate, errors='coerce').sum() == 2250
    assert percy_worksheet[['source_file', 'source_sheet', 'source_row']].drop_duplicates().shape[0] == 20
    assert percy_worksheet.canonical_player_id.isna().all()
    row=after.loc[after.canonical_player_id.eq(target)].iloc[0]
    assert row.Player=='Percy Eldridge' and not bool(row['Historical Career Under Review'])
    assert row.Runs==2208 and row.Wickets==184 and pd.isna(row['Bowl Avg'])
    phil=after.loc[after.Player.eq('Phil Eldridge')]
    assert len(phil)==1 and phil.Wickets.iloc[0]==227
    assert phil.canonical_player_id.isna().all() and phil.Runs.isna().all()
