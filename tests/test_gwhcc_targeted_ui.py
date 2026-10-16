from contextlib import nullcontext

import pandas as pd
import pytest

from src.ui import layout, theme


@pytest.mark.parametrize("club", ["glen-waverley-hawks", "fvcc", "georges-river-district"])
def test_premiership_heading_is_hawks_only(monkeypatch, club):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: club)
    monkeypatch.setattr(layout, "get_club_short_name", lambda: "Original Club")
    monkeypatch.setattr(layout, "premiership_win_row_html", lambda row: "Captain: Original Captain")
    expected = "GWHCC" if club == "glen-waverley-hawks" else "Original Club"
    for wins in [pd.DataFrame(), pd.DataFrame({"season": ["Summer 2025/26"]})]:
        rendered = layout.premiership_wins_card_html(wins)
        assert f">{expected} Premiership Wins</div>" in rendered
        if not wins.empty:
            assert "Captain: Original Captain" in rendered


@pytest.mark.parametrize("club", ["glen-waverley-hawks", "fvcc", "georges-river-district"])
def test_section_captions_removed_for_hawks_only(monkeypatch, club):
    captions = []
    empty_states = []
    monkeypatch.setattr(layout, "get_active_club_id", lambda: club)
    monkeypatch.setattr(layout.st, "caption", captions.append)
    monkeypatch.setattr(layout, "track_event_once", lambda *args, **kwargs: None)
    monkeypatch.setattr(layout, "render_section_heading", lambda *args: None)
    monkeypatch.setattr(layout, "load_batting_milestone_records", lambda *args: pd.DataFrame())
    monkeypatch.setattr(layout, "load_hat_trick_records", lambda *args: pd.DataFrame())
    monkeypatch.setattr(layout, "load_partnership_records", lambda *args: pd.DataFrame())
    monkeypatch.setattr(layout, "render_empty_milestone_card", lambda *args: empty_states.append(args))
    monkeypatch.setattr(layout, "render_partnership_record_panels", lambda *args, **kwargs: None)
    layout.render_fastest_batting_milestone_records()
    layout.render_hat_trick_records()
    layout.render_partnership_records()
    assert len(empty_states) == 2  # Real missing-evidence messages are retained.
    if club == "glen-waverley-hawks":
        assert captions == []
    else:
        assert captions == [
            "Based on matches with verified ball-by-ball data.",
            "Hat-tricks identified from available verified ball-by-ball records.",
            "Wicket records combine club-supplied historical records with innings-reconciled ball-by-ball data.",
        ]


def test_detailed_records_does_not_render_general_historical_caption(monkeypatch):
    monkeypatch.setattr(layout, "render_section_heading", lambda *args: None)
    monkeypatch.setattr(layout, "render_hawks_match_count_footnote", lambda: None)
    monkeypatch.setattr(
        layout, "render_gwhcc_hof_career_coverage_note",
        lambda: pytest.fail("General historical caption must not be rendered"),
    )
    monkeypatch.setattr(layout.st, "container", lambda **kwargs: nullcontext())
    monkeypatch.setattr(layout.st, "columns", lambda *args, **kwargs: [nullcontext(), nullcontext()])
    monkeypatch.setattr(layout.st, "selectbox", lambda *args, **kwargs: None)
    monkeypatch.setattr(layout, "render_folder_tab_widget", lambda *args, **kwargs: "batting")
    monkeypatch.setattr(layout, "detailed_record_public_player_options", lambda *args: [])
    monkeypatch.setattr(layout, "render_searched_detail_table", lambda *args: None)
    layout.render_detailed_all_time_records({category: pd.DataFrame() for category in ["batting", "bowling", "fielding"]})


def test_player_level_historical_coverage_note_is_preserved(monkeypatch):
    captions = []
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    monkeypatch.setattr(layout.st, "caption", captions.append)
    layout.render_gwhcc_career_coverage_note(pd.Series({"historical_career_metrics_applied": True}))
    assert "verified historical club records" in captions[0]
    assert "season breakdowns remain PlayCricket-based" in captions[0]


@pytest.mark.parametrize("club", ["glen-waverley-hawks", "fvcc", "georges-river-district"])
def test_visual_overrides_are_hawks_scoped(monkeypatch, club):
    monkeypatch.setattr(theme, "get_active_club_id", lambda: club)
    css = theme.active_club_theme_css()
    for rule in [
        'section[data-testid="stSidebar"] .side-brand {',
        '.hof-card.premiership-wins-card .premiership-season a.season-overview-link',
        'div.st-key-hof_detailed_records_category_control [data-testid="stButtonGroup"] button:focus-visible',
    ]:
        assert (rule in css) == (club == "glen-waverley-hawks")


def test_hawks_category_palette_uses_club_tokens_without_purple(monkeypatch):
    monkeypatch.setattr(theme, "get_active_club_id", lambda: "glen-waverley-hawks")
    css = theme.active_club_theme_css()
    selector_css = css.split('div.st-key-hof_detailed_records_category_control', 1)[1].split(
        '.block-container:has(.hall-of-fame-page)', 1
    )[0]
    for token in ["surface", "border", "muted", "primary", "text"]:
        assert f"var(--club-{token})" in selector_css
    assert "outline: 2px solid var(--club-text)" in selector_css
    for old_colour in ["#F1ECFF", "#4B37D8", "#646C91", "#E5E3F7"]:
        assert old_colour not in selector_css
