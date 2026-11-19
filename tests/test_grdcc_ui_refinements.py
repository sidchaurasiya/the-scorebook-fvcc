import pandas as pd
import pytest

from src.ui import layout, theme
from src.ui.grdcc_presentation import ordered_hat_tricks, overlapping_hat_trick_events, playing_dates_html, premium_css


def test_grdcc_only_theme_injection(monkeypatch):
    output = []
    monkeypatch.setattr(theme.st, 'markdown', lambda value, **kwargs: output.append(value))
    for club in ['fvcc', 'glen-waverley-hawks', 'georges-river-district']:
        output.clear()
        monkeypatch.setattr(theme, 'get_active_club_id', lambda: club)
        theme.inject_theme()
        assert any('--grdcc-body' in value for value in output) == (club == 'georges-river-district')
        if club == 'georges-river-district':
            assert output[-1].startswith('<style>')
            assert '\n<style>\n/* Injected only for GRDCC' in output[-1]


def test_premium_assets_and_accessible_rules_present():
    css = premium_css()
    assert '__MANROPE__' not in css and '__BARLOW__' not in css
    assert 'prefers-reduced-motion' in css and ':focus-visible' in css
    assert 'grid-template-columns: repeat(2' in css
    assert 'grid-template-columns: minmax(0,1fr)' in css
    assert 'transform: none !important' in css
    assert '.performance-player strong a.player-profile-link:visited' in css


def test_hall_of_fame_omits_player_career_provenance_notices(monkeypatch):
    markdown = []
    order = []
    all_time = pd.DataFrame({
        'canonical_player_id': ['percy_id', None],
        'Player': ['Percy Eldridge', 'Phil Eldridge'],
        layout.SOURCE_NOTE: [
            'Runs: Annual Report ALL GRADES through 2024/25 (p98).',
            'Annual Report record: 227 wickets through 2024/25 (p100).',
        ],
    })
    hall_of_fame_data = {'all_time': all_time, 'active_players': set(), 'detailed_tables': {}}
    monkeypatch.setattr(layout, 'load_views', lambda _club: None)
    monkeypatch.setattr(layout, 'get_hall_of_fame_data', lambda *args, **kwargs: hall_of_fame_data)
    monkeypatch.setattr(layout, 'track_event_once', lambda *args, **kwargs: None)
    monkeypatch.setattr(layout, 'log_hof_timing', lambda *args, **kwargs: None)
    monkeypatch.setattr(layout, 'configured_club_label_html', lambda: '<div>Club</div>')
    monkeypatch.setattr(layout, 'get_active_club_id', lambda: 'georges-river-district')
    monkeypatch.setattr(layout.st, 'markdown', lambda value, **kwargs: markdown.append(value))
    monkeypatch.setattr(layout, 'render_hall_of_fame_team_group_filter', lambda data: order.append('filters'))
    monkeypatch.setattr(layout, 'render_premiership_records', lambda *args, **kwargs: order.append('premierships'))
    for name in [
        'render_hall_of_fame_leaders', 'render_match_winning_performances',
        'render_fastest_batting_milestone_records', 'render_hat_trick_records',
        'render_verified_partnership_records', 'render_partnership_records',
        'render_record_holders', 'render_best_ever_seasons', 'render_detailed_all_time_records',
    ]:
        monkeypatch.setattr(layout, name, lambda *args, **kwargs: None)

    layout.render_hall_of_fame_page()

    intro = '\n'.join(markdown)
    assert 'Hall of Fame 🏆' in intro
    assert 'The players who shaped the club’s history.' in intro
    assert 'Players with multiple PlayCricket profiles are merged into one profile.' in intro
    assert 'Percy Eldridge:' not in intro
    assert 'Phil Eldridge:' not in intro
    assert 'grdcc-career-review' not in intro
    assert order == ['filters', 'premierships']


def sample_events():
    return pd.DataFrame([
        {'event_id':'second','match_id':'same','canonical_player_id':'public_one','canonical_player_name':'Example Player','match_date':'2026-10-17','delivery_sequence':'8.4 · 8.5 · 8.6'},
        {'event_id':'first','match_id':'same','canonical_player_id':'public_one','canonical_player_name':'Example Player','match_date':'2026-10-17','delivery_sequence':'8.3 · 8.4 · 8.5'},
        {'event_id':'old','match_id':'old','canonical_player_id':'public_two','canonical_player_name':'Another Player','match_date':'2024-02-01','delivery_sequence':'7.2 · 7.3 · 7.4'},
    ])


def test_hat_trick_sort_preserves_windows_and_is_order_independent():
    frame = sample_events(); before = frame.copy(deep=True)
    for source in [frame, frame.iloc[::-1]]:
        assert ordered_hat_tricks(source).event_id.tolist() == ['first','second','old']
        assert overlapping_hat_trick_events(source) == {'first','second'}
    pd.testing.assert_frame_equal(frame, before)


def test_overlap_does_not_join_different_bowlers():
    frame = sample_events(); frame.loc[1,'canonical_player_id'] = 'different_public'
    assert overlapping_hat_trick_events(frame) == set()
    frame = sample_events(); frame['innings_id'] = ['second_innings','first_innings','old_innings']
    assert overlapping_hat_trick_events(frame) == set()


def test_official_dates_are_sorted_and_never_inferred():
    dates = playing_dates_html(['2026-10-31','2026-10-24','2026-10-31'])
    assert dates.count('<time') == 2
    assert dates.index('24-10-2026') < dates.index('31-10-2026')
    assert '2026-11-07' not in dates
    assert '31-10-2026' in playing_dates_html('2026-10-30T22:30:00Z')
    assert 'Date unavailable' in playing_dates_html(None)
    assert 'Date unavailable' in playing_dates_html(0)
    assert 'Date unavailable' in playing_dates_html('2026')
    assert '<script' not in playing_dates_html('<script>bad</script>')


@pytest.mark.parametrize('club,date_present', [('georges-river-district',True),('fvcc',False),('glen-waverley-hawks',False)])
def test_round_date_column_is_club_scoped(monkeypatch, club, date_present):
    monkeypatch.setattr(layout, 'get_active_club_id', lambda: club)
    row = {'round':'R1','match_date':'2026-10-31','grade':'First Grade','opponent':'Example opposition','result_label':'Win'}
    rendered = layout.season_round_row_html(row)
    assert ('31-10-2026' in rendered) == date_present
    if date_present:
        assert rendered.index('31-10-2026') < rendered.index('R1')


def test_grdcc_scroll_script_keeps_vertical_wheel_native(monkeypatch):
    monkeypatch.setattr(layout, 'get_active_club_id', lambda: 'georges-river-district')
    script = layout.season_round_scroll_script_html('source-match-key')
    assert 'ResizeObserver' in script and 'next.hidden = !right' in script
    assert "addEventListener('wheel'" not in script
    assert 'prefers-reduced-motion' in script


def test_public_partnership_names_link_independently_and_private_does_not(monkeypatch):
    monkeypatch.setattr(layout,'player_profile_link_html',lambda identity,name,*args:f'<a href="?player_id={identity}">{name}</a>')
    row=pd.Series({'player_1_name':'Example One','player_1_canonical_id':'public_one','player_2_name':'Example Two','player_2_canonical_id':'public_two','wicket_number':1,'runs':94})
    rendered=layout.partnership_record_row_html(row)
    assert 'player_id=public_one' in rendered and 'player_id=public_two' in rendered
    row['player_2_name']='Private player';row['player_2_canonical_id']='protected_should_not_render'
    rendered=layout.partnership_record_row_html(row)
    assert 'Private player' in rendered and 'protected_should_not_render' not in rendered
