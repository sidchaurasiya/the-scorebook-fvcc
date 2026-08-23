from __future__ import annotations

import pandas as pd

from src.data import player_status_overrides


def activity_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"canonical_player_id": "player-a", "canonical_player_name": "Player A"},
            {"canonical_player_id": "player-b", "canonical_player_name": "Player B"},
        ]
    )


def test_empty_overrides_preserve_recent_participation(monkeypatch) -> None:
    monkeypatch.setattr(
        player_status_overrides,
        "load_player_status_overrides",
        lambda *_args, **_kwargs: pd.DataFrame(columns=player_status_overrides.PLAYER_STATUS_OVERRIDE_COLUMNS),
    )
    result = player_status_overrides.apply_active_player_id_overrides(
        {"player-a"},
        activity_frame(),
        club_id="fvcc",
    )
    assert result == {"player-a"}


def test_id_overrides_add_remove_and_ignore_unknown_ids(monkeypatch) -> None:
    overrides = pd.DataFrame(
        [
            {"player_id": "player-a", "status": "inactive"},
            {"player_id": "player-b", "status": "active"},
            {"player_id": "private-unknown", "status": "active"},
        ]
    )
    monkeypatch.setattr(
        player_status_overrides,
        "load_player_status_overrides",
        lambda *_args, **_kwargs: overrides,
    )
    result = player_status_overrides.apply_active_player_id_overrides(
        {"player-a"},
        activity_frame(),
        club_id="georges-river-district",
    )
    assert result == {"player-b"}
    assert "private-unknown" not in result


def test_gwhcc_is_not_supported_by_generic_override_loader() -> None:
    assert player_status_overrides.player_status_signature("glen-waverley-hawks") == tuple()
