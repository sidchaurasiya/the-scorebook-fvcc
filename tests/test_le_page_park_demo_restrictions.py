from __future__ import annotations

from src.config.club_config import get_demo_player_profile_allowlist
from src.data.playcricket_ingestion import metadata_mtime
from src.ui.layout import load_player_profile_index, player_profile_link_allowed, player_profile_url
from src.utils.player_identity import player_aliases_mtime


def test_le_page_park_demo_allowlist_contains_steve() -> None:
    restrictions = get_demo_player_profile_allowlist(club_id="le-page-park")
    assert restrictions["names"] == ("Steve McConchie",)


def test_le_page_park_only_steve_gets_player_profile_links(monkeypatch) -> None:
    monkeypatch.setenv("CLUB_ID", "le-page-park")
    assert player_profile_link_allowed("steve_mcconchie", "Steve McConchie")
    assert player_profile_url("steve_mcconchie", "Steve McConchie")
    assert not player_profile_link_allowed("someone_else", "Someone Else")
    assert player_profile_url("someone_else", "Someone Else") == ""


def test_le_page_park_player_profile_index_collapses_to_steve(monkeypatch) -> None:
    monkeypatch.setenv("CLUB_ID", "le-page-park")
    load_player_profile_index.clear()
    index = load_player_profile_index(metadata_mtime(), player_aliases_mtime())
    assert len(index) == 1
    assert index.iloc[0]["id"] == "steve_mcconchie"
    assert index.iloc[0]["name"] == "Steve McConchie"
