from __future__ import annotations

from contextlib import nullcontext

import pandas as pd
from pandas.testing import assert_frame_equal

from src.ui import layout


def detailed_tables() -> dict[str, pd.DataFrame]:
    players = [
        "./?page=player-profile&player_id=greg_mccormick#Greg McCormick",
        "./?page=player-profile&player_id=glen_mahoney#Glen Mahoney",
        "./?page=player-profile&player_id=private#********",
    ]
    return {
        category: pd.DataFrame(
            {
                "Player": players,
                "Runs": [8664, 11040, 99999],
                "canonical_player_id": ["greg_mccormick", "glen_mahoney", "private"],
            }
        )
        for category in ["batting", "bowling", "fielding"]
    }


def public_source_tables() -> dict[str, pd.DataFrame]:
    return {
        category: table.iloc[:2].copy()
        for category, table in detailed_tables().items()
    }


def visible_names(table: pd.DataFrame) -> list[str]:
    return table["Player"].map(layout.link_display_label).tolist()


def test_empty_search_preserves_existing_public_tables() -> None:
    tables = public_source_tables()
    filtered = layout.filter_detailed_record_tables_by_player(tables, "")
    for category in tables:
        assert_frame_equal(filtered[category], tables[category])


def test_search_is_case_insensitive() -> None:
    filtered = layout.filter_detailed_record_tables_by_player(detailed_tables(), "gReG")
    assert visible_names(filtered["batting"]) == ["Greg McCormick"]


def test_search_supports_partial_player_names() -> None:
    filtered = layout.filter_detailed_record_tables_by_player(detailed_tables(), "mc")
    assert visible_names(filtered["batting"]) == ["Greg McCormick"]


def test_unknown_search_returns_empty_tables() -> None:
    filtered = layout.filter_detailed_record_tables_by_player(detailed_tables(), "no such player")
    assert all(table.empty for table in filtered.values())


def test_unknown_search_renders_clear_empty_state(monkeypatch) -> None:
    messages: list[str] = []
    rendered: list[pd.DataFrame] = []
    monkeypatch.setattr(layout.st, "info", messages.append)
    monkeypatch.setattr(layout, "render_all_time_detail_table", lambda table, _key: rendered.append(table))
    layout.render_searched_detail_table(pd.DataFrame(), "test_detail", "batting", "unknown")
    assert messages == ['No matching players in batting records for "unknown".']
    assert rendered == []


def test_private_players_are_excluded_even_without_search() -> None:
    filtered = layout.filter_detailed_record_tables_by_player(detailed_tables(), "")
    assert all("********" not in visible_names(table) for table in filtered.values())


def test_filter_preserves_order_values_and_canonical_ids() -> None:
    tables = detailed_tables()
    filtered = layout.filter_detailed_record_tables_by_player(tables, "g")
    batting = filtered["batting"]
    assert visible_names(batting) == ["Greg McCormick", "Glen Mahoney"]
    assert batting["Runs"].tolist() == [8664, 11040]
    assert batting["canonical_player_id"].tolist() == ["greg_mccormick", "glen_mahoney"]
    assert len(batting) == len(batting.drop_duplicates("canonical_player_id"))


def test_public_player_suggestions_are_canonical_unique_and_private_safe() -> None:
    index = pd.DataFrame(
        {
            "id": ["greg-1", "greg-2", "glen", "private"],
            "name": ["Greg McCormick", "greg mccormick", "Glen Mahoney", "********"],
        }
    )
    assert layout.canonical_public_player_names(index) == ["Glen Mahoney", "Greg McCormick"]


def test_suggestions_support_case_insensitive_partial_matching() -> None:
    names = ["Greg Huntington", "Greg McCallum", "Greg McCormick", "Glen Mahoney"]
    assert layout.filter_detailed_record_player_suggestions(names, "GrEg") == names[:3]
    assert layout.filter_detailed_record_player_suggestions(names, "mc") == [
        "Greg McCallum",
        "Greg McCormick",
    ]


def test_raw_canonical_casing_repairs_mccormick_display() -> None:
    frame = pd.DataFrame(
        {
            "canonical_player_name": ["Greg Mccormick", "Greg Mccallum"],
            "raw_player_name": ["Greg McCormick", "Greg McCallum"],
        }
    )
    assert layout.canonical_player_name_casing_overrides(frame) == {
        "greg mccormick": "Greg McCormick",
        "greg mccallum": "Greg McCallum",
    }


def test_selected_player_filter_is_exact_case_insensitive_and_clearable() -> None:
    tables = detailed_tables()
    selected = layout.filter_detailed_record_tables_by_selected_player(tables, "gReG mCcOrMiCk")
    assert visible_names(selected["batting"]) == ["Greg McCormick"]
    cleared = layout.filter_detailed_record_tables_by_selected_player(tables, None)
    assert visible_names(cleared["batting"]) == ["Greg McCormick", "Glen Mahoney"]


def test_selected_player_without_current_category_record_returns_empty() -> None:
    tables = detailed_tables()
    tables["bowling"] = tables["bowling"][
        ~tables["bowling"]["Player"].map(layout.link_display_label).eq("Greg McCormick")
    ]
    selected = layout.filter_detailed_record_tables_by_selected_player(tables, "Greg McCormick")
    assert selected["batting"].shape[0] == 1
    assert selected["bowling"].empty


def test_detailed_records_controls_share_desktop_row_and_stable_keys(monkeypatch) -> None:
    column_specs: list[tuple[list[int], str, str]] = []
    selectbox_calls: list[dict[str, object]] = []
    rendered: list[tuple[str, str, int]] = []
    monkeypatch.setattr(layout, "render_section_heading", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(layout, "render_hawks_match_count_footnote", lambda: None)
    monkeypatch.setattr(layout, "render_gwhcc_hof_career_coverage_note", lambda: None)
    monkeypatch.setattr(layout.st, "container", lambda **_kwargs: nullcontext())

    def columns(spec, *, gap="small", vertical_alignment="top"):
        column_specs.append((list(spec), gap, vertical_alignment))
        return [nullcontext(), nullcontext()]

    def selectbox(label, options, **kwargs):
        selectbox_calls.append({"label": label, "options": list(options), **kwargs})
        return "Greg McCormick"

    monkeypatch.setattr(layout.st, "columns", columns)
    monkeypatch.setattr(layout.st, "selectbox", selectbox)
    monkeypatch.setattr(layout, "render_folder_tab_widget", lambda *_args, **_kwargs: "batting")
    monkeypatch.setattr(
        layout,
        "detailed_record_public_player_options",
        lambda *_args, **_kwargs: ["Glen Mahoney", "Greg McCormick"],
    )
    monkeypatch.setattr(
        layout,
        "render_searched_detail_table",
        lambda table, key, category, _search: rendered.append((key, category, len(table))),
    )

    layout.render_detailed_all_time_records(detailed_tables())

    assert column_specs == [([3, 2], "large", "bottom")]
    assert selectbox_calls[0]["key"] == "hof_detailed_records_player_search"
    assert selectbox_calls[0]["index"] is None
    assert selectbox_calls[0]["placeholder"] == "Search player"
    assert rendered == [("hof_batting_detail", "batting", 1)]
