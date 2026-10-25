from types import SimpleNamespace

from src.ui import layout


def test_hawks_profile_state_is_pruned_only_when_leaving_profile():
    state = {
        "player_profile_selector_id": "james-anderson-id",
        "selected_player_id": "james-anderson-id",
        "selected_player_profile_id": "james-anderson-id",
        "player_profile_valid_ids": ["james-anderson-id"],
        "player_profile_name_to_id": {"James Anderson": "james-anderson-id"},
        "last_player_profile_query_param": "james-anderson-id",
        "manual_player_profile_selection": True,
        "player_profile_selector_label": "James Anderson",
        "pending_player_profile_id": "james-anderson-id",
        "unrelated_page_state": "keep",
    }

    layout.reset_hawks_profile_selector_on_route_exit(
        state,
        "player-profile",
        "season-overview",
        "glen-waverley-hawks",
    )

    assert not any(key.startswith("player_profile_") for key in state)
    assert "selected_player_id" not in state
    assert "selected_player_profile_id" not in state
    assert "last_player_profile_query_param" not in state
    assert "manual_player_profile_selection" not in state
    assert "pending_player_profile_id" not in state
    assert state["unrelated_page_state"] == "keep"


def test_profile_state_is_preserved_for_same_page_and_other_clubs():
    state = {"player_profile_selector_id": "james-anderson-id"}

    layout.reset_hawks_profile_selector_on_route_exit(
        state,
        "player-profile",
        "player-profile",
        "glen-waverley-hawks",
    )
    layout.reset_hawks_profile_selector_on_route_exit(
        state,
        "player-profile",
        "season-overview",
        "fvcc",
    )

    assert state["player_profile_selector_id"] == "james-anderson-id"


def test_in_app_navigation_replaces_stale_profile_query_params(monkeypatch):
    params = {"page": "player-profile", "player_id": "james-anderson-id", "season": "old-season"}
    monkeypatch.setattr(layout, "st", SimpleNamespace(query_params=params))

    layout.navigate_to_page_in_session("season-overview")

    assert params == {"page": "season-overview"}
