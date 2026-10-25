from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import pytest

from src.data.gwhcc_identity import apply_profile_display_names, player_search_label
from src.utils.player_identity import resolve_approved_disjoint_player_id

ROOT = Path(__file__).resolve().parents[1]
CLUB = "glen-waverley-hawks"
ID = "raw_7ceaa8ee_ed93_4785_a4b4_8c670b67fd97"
RELEASE = "e2a9410995d31f3384723c6b832f045b557615d7"


def test_display_policy_changes_one_name_only_and_does_not_mutate_input():
    frame = pd.DataFrame({"canonical_player_id": [ID, "unrelated"],
                          "Player": ["Sunil Somaia", "Other Player"], "Runs": [8391, 55]})
    original = frame.copy(deep=True)
    after = apply_profile_display_names(frame, CLUB)
    assert after.Player.tolist() == ["Sunny Somaia", "Other Player"]
    pd.testing.assert_frame_equal(frame, original)
    pd.testing.assert_frame_equal(after.drop(columns="Player"), original.drop(columns="Player"))
    for club in ("fvcc", "georges-river-district"):
        pd.testing.assert_frame_equal(apply_profile_display_names(frame, club), frame)
        assert player_search_label("Sunil Somaia", club) == "Sunil Somaia"


def test_visible_search_has_no_alias_badge_or_second_option(monkeypatch):
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", CLUB)
    index = layout.load_player_profile_index.__wrapped__(CLUB, layout.metadata_mtime(), layout.player_aliases_mtime())
    target = index[index.id.eq(ID)]
    assert len(target) == 1
    labels = target.name.map(layout.gwhcc_player_search_label).tolist()
    assert labels == ["Sunny Somaia"]
    assert "(" not in labels[0] and "Sunil" not in labels[0]


@pytest.mark.parametrize("raw_id", ["7ceaa8ee-ed93-4785-a4b4-8c670b67fd97", "87dcf20b-a607-4346-a352-899db515d5fb"])
def test_both_original_source_routes_and_private_guard_are_unchanged(monkeypatch, raw_id):
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", CLUB)
    assert resolve_approved_disjoint_player_id(raw_id, club_id=CLUB) == ID
    monkeypatch.setattr(layout, "query_param_value", lambda key: raw_id if key == "player_id" else "")
    assert layout.resolve_player_query_to_id({ID: "Sunil Somaia"}) == ID
    assert layout.resolve_player_query_to_id({}) == ""
    monkeypatch.setattr(layout, "public_player_profile_lookup", lambda *a: (frozenset([ID]), {"sunil somaia": ID}))
    assert layout.resolve_public_profile_target("", "Sunny Somaia") == ID
    assert layout.resolve_public_profile_target("", "Private player") == ""


def test_actual_profile_view_has_final_name_and_unchanged_statistics(monkeypatch):
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", CLUB)
    premiership_dir = ROOT / "clubs" / CLUB / "data/processed/hall_of_fame"
    monkeypatch.setattr(layout, "HALL_OF_FAME_PREMIERSHIP_WINS_PATH", premiership_dir / "premiership_wins.csv")
    monkeypatch.setattr(layout, "HALL_OF_FAME_PLAYER_PREMIERSHIPS_PATH", premiership_dir / "player_premierships.csv")
    layout.load_premiership_records.clear()
    profile = layout.get_player_profile_data(ID, layout.metadata_mtime(), layout.player_aliases_mtime(), club_id=CLUB)
    view = layout.build_player_profile_view.__wrapped__(profile, layout.player_profile_view_signature())
    row = view["career"].iloc[0]
    assert row.Player == "Sunny Somaia"
    for metric, expected in {"Matches": 274, "Runs": 8391, "Wickets": 26, "Innings": 280, "Not Outs": 31, "100s": 21}.items():
        assert row[metric] == expected
    assert view["season_table"].Runs.sum() == 8391
    assert view["season_table"].Innings.sum() == 280
    assert all(card["player"] != "Sunil Somaia" for card in layout.player_highlight_cards(view))
    original_career = row.copy()
    original_career["Player"] = "Sunil Somaia"
    assert layout.player_premiership_profile_badges(row) == layout.player_premiership_profile_badges(original_career)
    assert layout.player_premiership_profile_badges(row) == ["Premiership Winning Player x5"]
    assert layout.build_player_recent_form(row) == layout.build_player_recent_form(original_career)


def test_identity_mappings_persist_across_weekly_refresh():
    paths = ["player_aliases.csv", "data/source/disjoint_season_identity_decisions.csv"]
    for relative in paths:
        path = ROOT / "clubs" / CLUB / relative
        released = subprocess.check_output(["git", "show", f"{RELEASE}:{path.relative_to(ROOT)}"], cwd=ROOT)
        assert path.read_bytes() == released
