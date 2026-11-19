import pandas as pd
import pytest

import src.ui.layout as layout
from src.ui.layout import (
    GWHCC_PROFILE_DISPLAY_NAME_SOURCE,
    apply_gwhcc_profile_display_name_overrides,
    format_bat_sr_display,
    format_peer_metric_value,
    hof_detail_display_value,
    hof_detail_header_label,
    peer_metric_note,
)


def test_gwhcc_exact_id_display_override_corrects_name_without_changing_identity():
    index = pd.DataFrame(
        [
            {"id": "raw_9842b38d_712c_411b_8692_92ba5b77308e", "name": "Martin, Lincoln"},
            {"id": "raw_other_player", "name": "Other Player"},
        ]
    )
    aliases = pd.DataFrame(
        [
            {
                "canonical_player_id": "raw_9842b38d_712c_411b_8692_92ba5b77308e",
                "canonical_player_name": "Lincoln Martin",
                "raw_player_id": "9842b38d-712c-411b-8692-92ba5b77308e",
                "raw_player_name": "",
                "alias_name": "",
                "notes": "Exact source ID display correction; no merge.",
                "is_active": "true",
                "merge_source": GWHCC_PROFILE_DISPLAY_NAME_SOURCE,
            }
        ]
    )

    output = apply_gwhcc_profile_display_name_overrides(index, aliases)

    assert output.id.tolist() == index.id.tolist()
    assert output.name.tolist() == ["Lincoln Martin", "Other Player"]


def test_gwhcc_display_override_ignores_inactive_and_other_decisions():
    index = pd.DataFrame([{"id": "raw_player", "name": "Source Order, Player"}])
    aliases = pd.DataFrame(
        [
            {
                "canonical_player_id": "raw_player",
                "canonical_player_name": "Player Source Order",
                "merge_source": GWHCC_PROFILE_DISPLAY_NAME_SOURCE,
                "is_active": "false",
            },
            {
                "canonical_player_id": "raw_player",
                "canonical_player_name": "Unrelated Decision",
                "merge_source": "customer_confirmed_name_variant_disjoint_seasons",
                "is_active": "true",
            },
        ]
    )

    output = apply_gwhcc_profile_display_name_overrides(index, aliases)

    assert output.name.tolist() == ["Source Order, Player"]


def test_gwhcc_conflicting_exact_id_display_overrides_fail_closed():
    index = pd.DataFrame([{"id": "raw_player", "name": "Source Order, Player"}])
    aliases = pd.DataFrame(
        [
            {
                "canonical_player_id": "raw_player",
                "canonical_player_name": name,
                "merge_source": GWHCC_PROFILE_DISPLAY_NAME_SOURCE,
                "is_active": "true",
            }
            for name in ("Player One", "Player Two")
        ]
    )

    with pytest.raises(ValueError, match="Conflicting GWHCC exact-ID profile display-name decisions"):
        apply_gwhcc_profile_display_name_overrides(index, aliases)


def test_gwhcc_batting_tables_label_ball_by_ball_strike_rate(monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    monkeypatch.setattr(
        layout,
        "prepare_curated_display_frame",
        lambda frame, source_columns, display_columns: pd.DataFrame(
            [{"Player": "Lincoln Martin", "Bat SR": 107.5}]
        ),
    )
    monkeypatch.setattr(layout, "apply_batting_detail_fallbacks", lambda frame: frame)

    displayed = layout.get_batting_display_df(pd.DataFrame())

    assert displayed.loc[0, "Bat SR (ball-by-ball)"] == 107.5
    assert "Bat SR" not in displayed.columns
    assert layout.hof_detail_header_label("Bat SR") == "Bat SR (ball-by-ball)"
    assert peer_metric_note("Strike Rate (ball-by-ball)") == "Verified ball-by-ball only"


def test_other_club_batting_header_is_unchanged(monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")

    assert layout.hof_detail_header_label("Bat SR") == "Bat SR"


def test_gwhcc_ball_by_ball_strike_rate_uses_percent_display(monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")

    assert format_bat_sr_display(68.94) == "68.94%"
    assert hof_detail_display_value("Bat SR", 68.94) == "68.94%"
    assert format_peer_metric_value(93.24, "batting_rate") == "93.24%"
    assert peer_metric_note("Strike Rate (ball-by-ball)") == "Verified ball-by-ball only"


def test_non_hawks_strike_rate_formatting_uses_runs_per_100_balls(monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")

    assert format_bat_sr_display(68.94) == "68.94%"
    assert hof_detail_display_value("Bat SR", 68.94) == "68.94%"
    assert format_peer_metric_value(93.24, "batting_rate") == "93.24%"
