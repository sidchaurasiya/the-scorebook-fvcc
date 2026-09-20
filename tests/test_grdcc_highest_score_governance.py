from pathlib import Path

import pandas as pd
import pytest

from src.data import featured_record_overrides as overrides

CLUB = 'georges-river-district'
BASE = Path('clubs') / CLUB / 'data/processed'


@pytest.mark.parametrize('original,supplement,expected', [
    ('130*', 58, '130*'), ('148*', 148, '148*'), ('84', 83, '84'),
    ('50', 60, '60'), ('100*', 101, '101'), ('100', '100*', '100*'),
    ('', None, pd.NA),
])
def test_strongest_high_score_keeps_score_and_not_out_together(original, supplement, expected):
    actual = overrides._strongest_high_score(pd.Series([original, supplement]))
    if expected is pd.NA:
        assert pd.isna(actual)
    else:
        assert actual == expected


def test_nick_scorecard_and_prepared_career_are_preserved_by_presentation():
    core = pd.read_csv(BASE / 'hall_of_fame/prepared_career_all_time.csv')
    nick = core[core.Player.eq('Nick Condylios')]
    links = pd.read_csv(BASE / 'hall_of_fame/scorecard_record_links.csv')
    evidence = links[links.canonical_player_id.eq(nick.canonical_player_id.iloc[0]) & links['mode'].eq('batting')]
    assert evidence.runs_scored.max() == 130
    assert evidence[evidence.runs_scored.eq(130)].match_id.iloc[0] == '0938f148-48b0-4998-ab5b-596ebc472738'
    assert nick.HS.iloc[0] == '130*'
    shown = overrides.apply_featured_record_overrides(nick, CLUB, add_missing_players=False)
    assert shown.HS.iloc[0] == '130*'


def test_approved_alias_collapse_keeps_maximum_hs(monkeypatch):
    monkeypatch.setattr(overrides, 'load_override_player_supplements', lambda *_: pd.DataFrame([
        dict(player_name='Full Name', normalized_player_name='full name', excel_aliases_used='F Name', excel_hs=50)
    ]))
    monkeypatch.setattr(overrides, 'load_featured_record_overrides', lambda *_: pd.DataFrame([
        dict(player_name='Full Name',normalized_player_name='full name',metric='career_runs',authoritative_value=1000)
    ]))
    monkeypatch.setattr(overrides, 'load_annual_report_override_decisions', lambda *_: pd.DataFrame())
    monkeypatch.setattr(overrides, 'load_annual_report_all_time_leaders', lambda *_: pd.DataFrame())
    frame = pd.DataFrame({'Player':['Full Name','F Name'],'HS':['40','120*'],'Runs':[900,200]})
    shown = overrides.apply_featured_record_overrides(frame, CLUB)
    assert len(shown) == 1
    assert shown.HS.iloc[0] == '120*'
    assert shown.Runs.iloc[0] == 1000
    assert frame.HS.tolist() == ['40','120*']


@pytest.mark.parametrize('club',['fvcc','glen-waverley-hawks'])
def test_other_clubs_unchanged(club):
    frame=pd.DataFrame({'Player':['Public Example'],'HS':['130*'],'Runs':[300]})
    pd.testing.assert_frame_equal(frame, overrides.apply_featured_record_overrides(frame,club))


def test_prepared_season_source_boundary(monkeypatch):
    from src.data.playcricket_ingestion import read_processed_table
    monkeypatch.setenv('CLUB_ID',CLUB)
    batting=read_processed_table('all_seasons_batting')
    years=batting.season.str.extract(r'(\d{4})')[0].astype(int)
    assert (years[batting.source_system.eq('excel')] <= 1971).all()
    assert (years[batting.source_system.eq('playcricket')] >= 1972).all()
