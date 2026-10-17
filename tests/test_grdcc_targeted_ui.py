import pytest

from src.ui import theme


@pytest.mark.parametrize('club', ['fvcc', 'glen-waverley-hawks', 'georges-river-district'])
def test_grdcc_pill_rules_are_club_and_control_scoped(monkeypatch, club):
    monkeypatch.setenv('CLUB_ID', club)
    css = theme.active_club_theme_css()
    rules = theme.grdcc_hof_refinements_css()
    assert (rules in css) == (club == 'georges-river-district')
    assert '.st-key-hof_detailed_records_controls .st-key-hof_detailed_records_category_control' in rules
    assert 'border-radius: 999px' in rules
    assert 'repeat(3, minmax(0, 1fr))' in rules
    assert 'min-height: 44px' in rules
    assert 'max-width: none !important' in rules
    assert 'flex: none !important' in rules
    # The legacy mobile rule has a class plus an attribute; retain greater
    # specificity so percentage widths cannot be applied inside each grid cell.
    button_selector = '.st-key-hof_detailed_records_controls .st-key-hof_detailed_records_category_control [data-testid="stButtonGroup"] button {'
    assert button_selector in rules
    assert 'width: 100% !important' in rules.split(button_selector, 1)[1].split('}', 1)[0]
    assert '@media (max-width: 640px)' in rules
    assert '[kind="segmented_controlActive"]' in rules


def test_grdcc_pills_use_existing_palette_and_contrast(monkeypatch):
    monkeypatch.setenv('CLUB_ID', 'georges-river-district')
    css = theme.active_club_theme_css()
    rules = theme.grdcc_hof_refinements_css()
    for token in ['primary', 'surface', 'muted', 'border', 'bg']:
        assert f'var(--club-{token})' in rules
    assert '--club-primary: #0B3F9F' in css
    assert '--club-surface: #FFFFFF' in css
    assert '#F1ECFF' not in rules and '#4B37D8' not in rules
    def luminance(hex_colour):
        channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(linear, [0.2126, 0.7152, 0.0722]))
    assert (luminance('#FFFFFF') + 0.05) / (luminance('#0B3F9F') + 0.05) >= 4.5


def test_grdcc_refinement_does_not_hide_source_qualifications_or_change_logo():
    rules = theme.grdcc_hof_refinements_css()
    assert 'display: none' not in rules
    assert 'caption' not in rules
    assert 'side-shield' not in rules
    assert 'img' not in rules
