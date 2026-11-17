from contextlib import contextmanager, nullcontext
from types import SimpleNamespace

import pandas as pd
import pytest

from src.ui import layout


@pytest.mark.parametrize(
    ("club_id", "report_only"),
    [
        ("georges-river-district", False),
        ("georges-river-district", True),
        ("glen-waverley-hawks", False),
        ("fvcc", False),
    ],
)
def test_profile_loading_replaces_the_grdcc_record_before_building_it(monkeypatch, club_id, report_only):
    record_id = "public-test-record"
    index = pd.DataFrame({"id": [record_id], "name": ["Example player"]})
    career = pd.DataFrame({"report_record_id": [record_id]})
    rendered = []

    class ProfileSlot:
        def info(self, text):
            assert text == "Loading player profile…"
            rendered.append("loading")

        @contextmanager
        def container(self):
            rendered.append("replace loading")
            yield

    def load_record(*args, **kwargs):
        rendered.append("load")
        return career

    stub = SimpleNamespace(
        session_state={},
        markdown=lambda *args, **kwargs: None,
        container=lambda **kwargs: nullcontext(),
        selectbox=lambda *args, **kwargs: record_id,
        empty=ProfileSlot,
    )
    monkeypatch.setattr(layout, "st", stub)
    monkeypatch.setattr(layout, "get_active_club_id", lambda: club_id)
    monkeypatch.setattr(layout, "configured_club_label_html", lambda: "")
    monkeypatch.setattr(layout, "metadata_mtime", lambda: 0)
    monkeypatch.setattr(layout, "player_aliases_mtime", lambda: 0)
    monkeypatch.setattr(layout, "load_player_profile_index", lambda *args: index)
    monkeypatch.setattr(layout, "current_player_query_token", lambda: "")
    monkeypatch.setattr(layout, "sync_player_profile_query", lambda _selected_id: None)
    monkeypatch.setattr(layout, "report_profile_index", lambda _club: index if report_only else index.iloc[:0])
    monkeypatch.setattr(layout, "hall_of_fame_override_signature", tuple)
    monkeypatch.setattr(layout, "get_authoritative_career_totals", load_record)
    monkeypatch.setattr(layout, "get_player_profile_data", load_record)
    monkeypatch.setattr(layout, "player_profile_view_signature", tuple)
    monkeypatch.setattr(layout, "build_player_profile_view", lambda raw, _signature: {"career": raw})
    monkeypatch.setattr(layout, "track_event_once", lambda *args, **kwargs: None)
    monkeypatch.setattr(layout, "is_scoped_historical", lambda _career: True)
    monkeypatch.setattr(layout, "render_scoped_historical_profile", lambda _profile: rendered.append("render"))

    layout.render_player_profile_page()

    if club_id == "georges-river-district":
        assert rendered == ["loading", "load", "replace loading", "render"]
    else:
        assert rendered == ["load", "render"]


@pytest.mark.parametrize(
    ("club_id", "analytics_enabled"),
    [
        ("georges-river-district", True),
        ("georges-river-district", False),
        ("glen-waverley-hawks", True),
        ("fvcc", True),
    ],
)
def test_profile_rerun_keeps_grdcc_output_position_when_analytics_is_skipped(
    monkeypatch, club_id, analytics_enabled
):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    from src.utils import analytics

    monkeypatch.setattr(layout, "get_active_club_id", lambda: club_id)
    monkeypatch.setattr(analytics, "_measurement_id", lambda: "G-LOCALTEST1" if analytics_enabled else "")
    monkeypatch.setattr(layout, "inject_theme", lambda: st.markdown("Layout start"))
    monkeypatch.setattr(layout, "render_mobile_page_footer", lambda: None)

    def navigation():
        st.markdown("Profile navigation")
        return "player-profile"

    def profile():
        player = st.selectbox("Player", ["Mark Burgess", "Ryan Croom"])
        st.markdown(f"Selected profile: {player}")

    def result_slot(app, name):
        return next(
            slot
            for slot, element in app.main.children.items()
            if getattr(element, "value", None) == f"Selected profile: {name}"
        )

    monkeypatch.setattr(layout, "render_sidebar", navigation)
    monkeypatch.setattr(layout, "render_player_profile_page", profile)
    app = AppTest.from_string("from src.ui import layout\nlayout.render_page()").run()
    assert not app.exception
    assert len(app.get("iframe")) == (3 if analytics_enabled else 0)
    first_slot = result_slot(app, "Mark Burgess")
    if club_id != "georges-river-district":
        # Other clubs continue to render their analytics at the original root level.
        assert sum(child.type == "iframe" for child in app.main.children.values()) == 3

    app.selectbox[0].select("Ryan Croom").run()
    assert not app.exception
    assert not app.get("iframe")
    assert "Selected profile: Mark Burgess" not in [item.value for item in app.markdown]
    switched_slot = result_slot(app, "Ryan Croom")
    if club_id == "georges-river-district":
        assert switched_slot == first_slot
