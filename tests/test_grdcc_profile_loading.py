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
        def markdown(self, text, **kwargs):
            assert "Loading player profile…" in text and "Example player" in text
            rendered.append("loading")

        @contextmanager
        def container(self):
            rendered.append("details control")
            yield

    def load_record(*args, **kwargs):
        rendered.append("load")
        return career

    def markdown(text, **kwargs):
        if 'grdcc-profile-pending' in text:
            slot = ProfileSlot()
            slot.markdown(text, **kwargs)
            return slot

    stub = SimpleNamespace(
        session_state={},
        html=lambda *args, **kwargs: None,
        markdown=markdown,
        container=lambda **kwargs: nullcontext(),
        selectbox=lambda *args, **kwargs: record_id,
        empty=ProfileSlot,
        toggle=lambda *args, **kwargs: False,
    )
    monkeypatch.setattr(layout, "st", stub)
    monkeypatch.setattr(layout, "get_active_club_id", lambda: club_id)
    monkeypatch.setattr(layout, "configured_club_label_html", lambda: "")
    monkeypatch.setattr(layout, "metadata_mtime", lambda: 0)
    monkeypatch.setattr(layout, "player_aliases_mtime", lambda: 0)
    monkeypatch.setattr(layout, "load_grdcc_profile_bundle", lambda _club: None)
    monkeypatch.setattr(layout, "load_views", lambda _club: None)
    monkeypatch.setattr(layout, "load_player_profile_index", lambda *args: index)
    monkeypatch.setattr(layout, "current_player_query_token", lambda: "")
    monkeypatch.setattr(layout, "sync_player_profile_query", lambda _selected_id: None)
    monkeypatch.setattr(layout, "report_profile_index", lambda _club: index if report_only else index.iloc[:0])
    monkeypatch.setattr(layout, "hall_of_fame_override_signature", tuple)
    monkeypatch.setattr(layout, "get_authoritative_career_totals", load_record)
    monkeypatch.setattr(layout, "get_player_profile_data", load_record)
    monkeypatch.setattr(layout, "load_grdcc_profile_authority", load_record)
    monkeypatch.setattr(layout, "build_player_profile_primary", lambda raw: raw)
    monkeypatch.setattr(layout, "render_grdcc_primary_card", lambda _career, **kwargs: rendered.append("render"))
    monkeypatch.setattr(layout, "player_profile_view_signature", tuple)
    monkeypatch.setattr(layout, "build_player_profile_view", lambda raw, _signature: {"career": raw})
    monkeypatch.setattr(layout, "track_event_once", lambda *args, **kwargs: None)
    monkeypatch.setattr(layout, "is_scoped_historical", lambda _career: True)
    monkeypatch.setattr(layout, "render_scoped_historical_profile", lambda _profile: rendered.append("render"))

    layout.render_player_profile_page()

    if club_id == "georges-river-district":
        assert rendered == (["loading", "load", "render"] if report_only else ["loading", "load", "render", "details control"])
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


@pytest.mark.parametrize("scenario", ["closed", "open", "superseded", "optional_failure", "unavailable", "primary_failure"])
def test_grdcc_profile_summary_remains_available_during_optional_work(monkeypatch, scenario):
    from unittest.mock import Mock

    state = {"player_profile_selector_id": "ryan"}
    card = pd.DataFrame([{"Player": "Ryan Croom", "Runs": 6209, "Matches": 284}])
    events = []
    slot = Mock()
    slot.markdown.side_effect = lambda markup, **_: events.append(("pending", markup))
    status = Mock()
    optional = Mock()
    optional.container.return_value = nullcontext()
    slots = iter((optional, status))

    def markdown(markup, **kwargs):
        if "grdcc-profile-pending" in markup:
            slot.markdown(markup, **kwargs)
            return slot

    widgets = SimpleNamespace(
        session_state=state,
        empty=lambda: next(slots),
        container=lambda **kwargs: nullcontext(),
        toggle=lambda *args, **kwargs: scenario in {"open", "superseded", "optional_failure"},
        markdown=markdown,
    )
    primary = Mock(side_effect=lambda row, **kwargs: events.append(("primary", row.Player)))
    detailed = Mock(return_value={"career": card})
    analysis = Mock()

    def summary(_):
        if scenario == "primary_failure":
            raise ValueError("test load error")
        return card.iloc[:0] if scenario == "unavailable" else card

    def badge_work(*_):
        # The expensive work begins only after the primary card is visible.
        assert events[-1] == ("primary", "Ryan Croom")
        assert len(events) == 2
        if scenario == "superseded":
            state["player_profile_selector_id"] = "percy"
        if scenario == "optional_failure":
            raise ValueError("test badge error")
        return []

    badges = Mock(side_effect=badge_work)
    for name, implementation in {
        "st": widgets,
        "render_report_record_profile": lambda *args, **kwargs: False,
        "get_player_profile_data": lambda *args, **kwargs: {},
        "metadata_mtime": lambda: 0,
        "player_aliases_mtime": lambda: 0,
        "build_player_profile_primary": summary,
        "render_grdcc_primary_card": primary,
        "record_player_profile_view": lambda *args: None,
        "build_player_profile_view": detailed,
        "player_profile_view_signature": tuple,
        "player_role_badges": badges,
        "render_player_profile_analysis": analysis,
        "emit_requested_profile_breakdown": lambda *_: None,
    }.items():
        monkeypatch.setattr(layout, name, implementation)

    layout.render_grdcc_selected_profile("ryan", "Ryan Croom")
    assert "Ryan Croom" in events[0][1]
    if scenario in {"unavailable", "primary_failure"}:
        slot.container.assert_not_called()
        (slot.info if scenario == "unavailable" else slot.error).assert_called_once()
    else:
        primary.assert_called_once()
        assert primary.call_args.kwargs["output"] is slot
    if scenario in {"closed", "unavailable", "primary_failure"}:
        detailed.assert_not_called()
        badges.assert_not_called()
    if scenario == "open":
        analysis.assert_called_once()
    else:
        analysis.assert_not_called()
    if scenario == "optional_failure":
        status.error.assert_called_once()


def test_primary_card_qualifies_recorded_wickets_and_distinguishes_zero(monkeypatch):
    seen = []
    monkeypatch.setattr(layout, "st", SimpleNamespace(session_state={}, markdown=lambda value, **kwargs: seen.append(value)))
    monkeypatch.setattr(layout, "get_feature_flag", lambda *a, **kw: False)
    layout.render_grdcc_primary_card(pd.Series({
        "Player": "Percy Eldridge", "Runs": 2208, "Wickets": 184, "Matches": pd.NA, "Catches": 0,
        layout.RECORD_KIND: "primary_historical", layout.SOURCE_NOTE: "Recorded worksheet scope only",
    }))
    assert "<dt>Runs</dt><dd>2,208</dd>" in seen[0]
    assert "<dt>Recorded wickets</dt><dd>184</dd>" in seen[0]
    assert "<dt>Matches</dt><dd>Unavailable</dd>" in seen[0]
    assert "<dt>Catches</dt><dd>0</dd>" in seen[0]
    assert "Recorded worksheet scope only" in seen[0]


def test_grdcc_prepared_authority_reuses_governed_filters(monkeypatch):
    from unittest.mock import Mock

    prepared = pd.DataFrame({"Player": ["Sample"], "Runs": [0]})
    fallback = Mock(return_value=prepared)
    seen = []

    def pass_through(name):
        def apply(frame, club_id):
            seen.append((name, club_id))
            return frame
        return apply

    monkeypatch.delenv("SCOREBOOK_IGNORE_PREPARED_HOF", raising=False)
    monkeypatch.setattr(layout, "load_prepared_hall_of_fame_all_time", lambda club, version: prepared)
    monkeypatch.setattr(layout, "filter_public_hall_of_fame_rows", pass_through("privacy"))
    monkeypatch.setattr(layout, "apply_career_quarantine", pass_through("quarantine"))
    monkeypatch.setattr(layout, "apply_featured_record_overrides", pass_through("authority"))
    monkeypatch.setattr(layout, "get_authoritative_career_totals", fallback)
    assert layout._load_grdcc_profile_authority_cached.__wrapped__("test-generation", False).equals(prepared)
    fallback.assert_not_called()
    assert seen == [(phase, layout.GRDCC_CLUB_ID) for phase in ("privacy", "quarantine", "authority", "privacy")]
    monkeypatch.setattr(layout, "metadata_mtime", lambda: 1)
    monkeypatch.setattr(layout, "player_aliases_mtime", lambda **kwargs: 2)
    monkeypatch.setattr(layout, "hall_of_fame_override_signature", lambda _club: ())
    monkeypatch.setattr(layout, "load_prepared_hall_of_fame_all_time", lambda *args: None)
    assert layout._load_grdcc_profile_authority_cached.__wrapped__("test-generation", False).equals(prepared)
    fallback.assert_called_once()
