import json

import pandas as pd
import pytest

from scripts.build_fvcc_incremental_refresh import (
    latest_date_by_key,
    merge_batting_dot_coverage,
    merge_fvcc_player_summary,
    update_fvcc_round_playing_dates,
)
from src.ui import layout


def test_fvcc_increment_preserves_distinct_unlinked_history():
    keys = ['player_key', 'grade_id']
    history = pd.DataFrame({
        'player_key': [None, None, 'named'],
        'grade_id': ['grade'] * 3,
        'runs': [3, 8, 20],
        'bbb_dot_balls': [1, 6, 10],
        'bbb_dot_ball_balls_faced': [4, 9, 22],
        'latest_match_date': ['2025-12-06', '2026-01-31', '2026-11-14'],
    })
    increment = pd.DataFrame({
        'player_key': ['named'], 'grade_id': ['grade'], 'runs': [5], 'bbb_dot_balls': [2],
        'bbb_dot_ball_balls_faced': [8], 'latest_match_date': ['2026-11-21'],
    })
    merged = merge_fvcc_player_summary(history, increment, keys, ['before'], ['after'])
    merged = merge_batting_dot_coverage(merged, history, increment, keys)
    pd.testing.assert_frame_equal(merged[merged.player_key.isna()].reset_index(drop=True),
                                  history.iloc[:2], check_dtype=False)
    assert merged.loc[merged.player_key.eq('named'), ['runs', 'bbb_dot_balls']].iloc[0].tolist() == [25, 12]
    assert latest_date_by_key(history, increment, keys) == {('named', 'grade'): '2026-11-21'}
    with pytest.raises(ValueError, match='Non-unique summary key'):
        merge_fvcc_player_summary(pd.concat([history, history.tail(1)]), increment, keys, ['before'], ['after'])


def test_fvcc_round_date_index_keeps_both_source_days(tmp_path, monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")
    path = tmp_path / 'dates.json'
    update_fvcc_round_playing_dates(path, [{
        'id': 'fixture',
        'matchSchedule': [{'startDateTime': '2026-11-13T23:50:00Z'},
                          {'startDateTime': '2026-11-21T12:30:00+11:00'}],
    }])
    assert json.loads(path.read_text())['matches']['fixture']['playing_dates'] == ['2026-11-14', '2026-11-21']
    html = layout.season_round_row_html({'match_id': 'fixture', 'playing_dates': ['2026-11-14', '2026-11-21']})
    assert 'datetime="2026-11-14"' in html and 'datetime="2026-11-21"' in html


def test_fvcc_primary_order_and_achievement_copy(monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")
    row = pd.Series({'Player': 'Example', 'Matches': 12, 'Runs': 33, 'Wickets': 4, 'Catches': 2})
    primary = layout.grdcc_primary_card_markup(row, insight_markup='<p>Existing insight</p>')
    names = [primary.index(f'<dt>{k}</dt>') for k in ('Matches', 'Runs', 'Wickets', 'Catches')]
    assert names == sorted(names) and '<p>Existing insight</p>' in primary
    monkeypatch.setattr(layout, "player_profile_link_html", lambda *_: "")
    row = pd.Series({'Match Evidence': 'Exact match unavailable', 'Category': 'Matches', 'Player': 'Example',
                     'Milestone': 50, 'Season': 'Summer 2026/27', 'Current Total': 52, 'Unit': 'matches'})
    card = layout.achievement_card_html(row)
    assert '52 matches' in card and '>Exact match unavailable' not in card


def test_fvcc_recent_form_can_use_verified_previous_season(tmp_path, monkeypatch):
    path = tmp_path / 'rounds.csv'
    pd.DataFrame({'match_id':['one', 'two'], 'season':['Summer 2026/27', 'Winter 2026']}).to_csv(path, index=False)
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")
    monkeypatch.setattr(layout, "get_processed_path", lambda *args, **kw: path)
    monkeypatch.setattr(layout, "player_profile_detail_source_signature", lambda: ())
    monkeypatch.setattr(layout, "load_player_profile_detail_sources", lambda *_: {"recent_form_batting": pd.DataFrame({
        'canonical_player_id':['p','p'], 'match_id':['one','two'], 'match_date':['2026-11-21','2026-07-25'],
        'display_value':['28','10*'],
    })})
    rows = layout.build_player_recent_form(pd.Series({'canonical_player_id': 'p', 'Player': 'Example'}))['batting']
    assert [(r['label'],r['season']) for r in rows] == [('28','Summer 2026/27'), ('10*','Winter 2026')]
