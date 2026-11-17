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
