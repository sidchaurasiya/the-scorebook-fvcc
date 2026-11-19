from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pandas as pd
import pytest

from src.ui import layout


@pytest.mark.parametrize("discipline", ["Batting", "Fielding", "Bowling"])
def test_requested_breakdown_only_builds_full_view_when_required(monkeypatch, discipline):
    profile = {"player_info": {"canonical_player_id": "public"}}
    prepared = pd.DataFrame({"dimension": ["Season", "Grade"], "discipline": [discipline, discipline],
                             "breakdown_label": ["Summer 2026/27", "First"]})
    view = {"season_table": pd.DataFrame({"Extras %": [5]})}
    full_view = Mock(return_value=view)
    display = Mock()
    replacements = {
        "st": SimpleNamespace(container=lambda **_: nullcontext()),
        "section_run": lambda _: nullcontext(),
        "render_section_heading": Mock(),
        "render_hawks_match_count_footnote": Mock(),
        "selected_profile_breakdown_view": lambda: "season",
        "selected_profile_discipline_view": lambda: discipline,
        "render_profile_breakdown_tabs": Mock(),
        "render_profile_breakdown_controls": Mock(),
        "player_detail_inputs": lambda _: {"performance_breakdown": prepared},
        "player_profile_source_rows": lambda source, _: source,
        "player_profile_view_signature": tuple,
        "build_player_profile_view": full_view,
        "render_profile_performance_table": display,
    }
    for name, value in replacements.items():
        monkeypatch.setattr(layout, name, value)

    layout.render_player_performance_breakdown.__wrapped__(None, profile=profile)

    display.assert_called_once()
    rows, label, mode, supplied_view = display.call_args.args
    assert list(rows.breakdown_label) == ["Summer 2026/27"]
    assert (label, mode) == ("Season", discipline)
    if discipline == "Bowling":
        full_view.assert_called_once()
        assert supplied_view is view
    else:
        full_view.assert_not_called()
        assert supplied_view is None


def test_analysis_reserves_original_order_but_emits_breakdown_first(monkeypatch):
    allocation = []
    workload = []
    upper = Mock()
    upper.__enter__ = Mock()
    upper.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(layout, "st", SimpleNamespace(container=lambda: allocation.append("upper") or upper))
    names = ("performance_breakdown", "breakdown", "recent_form", "highlights", "intelligence",
             "peer_comparison", "trends", "milestones")
    for name in names:
        monkeypatch.setattr(layout, f"render_player_{name}", lambda *_, name=name: workload.append(name))
    profile = {"career": pd.DataFrame({"Player": ["Public Person"]}), "season_table": pd.DataFrame()}

    layout.render_player_profile_analysis(profile)

    assert allocation == ["upper"]
    assert workload == list(names)
    upper.__enter__.assert_called_once()


def test_report_scope_never_emits_early_breakdown(monkeypatch):
    render = Mock()
    monkeypatch.setattr(layout, "render_player_performance_breakdown", render)
    monkeypatch.setattr(layout, "is_scoped_historical", lambda _: True)
    assert layout.emit_requested_profile_breakdown({}, pd.Series({"Player": "Historical"})) is None
    render.assert_not_called()
