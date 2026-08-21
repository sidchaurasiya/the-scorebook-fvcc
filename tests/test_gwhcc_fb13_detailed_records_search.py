from __future__ import annotations

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
