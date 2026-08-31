from __future__ import annotations

import json

import pandas as pd
from pandas.testing import assert_frame_equal

from src.data import hall_of_fame_prepared
from src.ui import layout


PUBLIC_ID = "public_player"
PRIVATE_ID = "private_flagged"
PRIVATE_NAME = "Synthetic Confidential Player"


def category_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "canonical_player_id": PUBLIC_ID,
                "canonical_player_name": "Public Player",
                "player_id": "public-raw",
                "player_name": "Public Player",
                "privacy_flag": "",
                "season": "Winter 2026",
                "season_start_date": "2026-01-01",
                "matches": 10,
                "battingAggregate": 100,
                "battingInnings": 5,
                "battingNotOuts": 1,
                "battingAverage": 25.0,
                "battingHighScore": 50,
                "batting50s": 1,
                "batting100s": 0,
                "batting0s": 0,
                "battingFours": 4,
                "battingSixes": 1,
                "bowlingWickets": 5,
                "bowlingBestInnings": "2/20",
                "fieldingTotalCatches": 3,
            },
            {
                "canonical_player_id": PRIVATE_ID,
                "canonical_player_name": PRIVATE_NAME,
                "player_id": "private-raw",
                "player_name": PRIVATE_NAME,
                "privacy_flag": "private",
                "season": "Winter 2026",
                "season_start_date": "2026-01-01",
                "matches": 99,
                "battingAggregate": 9999,
                "battingInnings": 99,
                "battingNotOuts": 0,
                "battingAverage": 100.0,
                "battingHighScore": 999,
                "batting50s": 99,
                "batting100s": 99,
                "batting0s": 0,
                "battingFours": 99,
                "battingSixes": 99,
                "bowlingWickets": 99,
                "bowlingBestInnings": "10/1",
                "fieldingTotalCatches": 99,
            },
            {
                "canonical_player_id": "private_marker",
                "canonical_player_name": "********",
                "player_id": "private-marker-raw",
                "player_name": "********",
                "privacy_flag": "",
                "season": "Winter 2026",
                "season_start_date": "2026-01-01",
                "matches": 98,
                "battingAggregate": 9998,
                "battingInnings": 98,
                "battingNotOuts": 0,
                "battingAverage": 100.0,
                "battingHighScore": 998,
                "batting50s": 98,
                "batting100s": 98,
                "batting0s": 0,
                "battingFours": 98,
                "battingSixes": 98,
                "bowlingWickets": 98,
                "bowlingBestInnings": "10/2",
                "fieldingTotalCatches": 98,
            },
        ]
    )


def all_time_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "canonical_player_id": PUBLIC_ID,
                "Player": "Public Player",
                "privacy_flag": "",
                "Seasons Played": 1,
                "Matches": 10,
                "Runs": 100,
                "Bat Avg": 25.0,
                "Wickets": 5,
                "Bowl Avg": 20.0,
                "Catches": 3,
                "100s": 0,
                "50s": 1,
                "4s": 4,
                "6s": 1,
                "5WI": 0,
                "Maidens": 1,
                "0s": 0,
            },
            {
                "canonical_player_id": PRIVATE_ID,
                "Player": PRIVATE_NAME,
                "privacy_flag": "private",
                "Seasons Played": 1,
                "Matches": 99,
                "Runs": 9999,
                "Bat Avg": 100.0,
                "Wickets": 99,
                "Bowl Avg": 1.0,
                "Catches": 99,
                "100s": 99,
                "50s": 99,
                "4s": 99,
                "6s": 99,
                "5WI": 99,
                "Maidens": 99,
                "0s": 99,
            },
        ]
    )


def assert_only_public(frame: pd.DataFrame, name_column: str) -> None:
    assert frame[name_column].tolist() == ["Public Player"]


def test_private_aggregate_batting_row_is_removed() -> None:
    assert_only_public(layout.filter_public_hall_of_fame_rows(category_frame(), "fvcc"), "canonical_player_name")


def test_private_aggregate_bowling_row_is_removed() -> None:
    assert_only_public(layout.filter_public_hall_of_fame_rows(category_frame(), "fvcc"), "canonical_player_name")


def test_private_aggregate_fielding_row_is_removed() -> None:
    assert_only_public(layout.filter_public_hall_of_fame_rows(category_frame(), "fvcc"), "canonical_player_name")


def test_private_identity_cannot_become_leader() -> None:
    public = layout.filter_public_hall_of_fame_rows(all_time_frame(), "fvcc")
    leader = layout.sort_hof_leaders(public, "Runs", "batting").iloc[0]
    assert leader["Player"] == "Public Player"


def test_private_identity_cannot_become_record_holder() -> None:
    public_all_time = layout.filter_public_hall_of_fame_rows(all_time_frame(), "fvcc")
    public_batting = layout.filter_public_hall_of_fame_rows(category_frame(), "fvcc")
    cards = layout.build_record_holder_cards({"batting_raw": public_batting, "all_time": public_all_time})
    assert cards
    assert {card["player"] for card in cards} == {"Public Player"}


def test_private_identity_cannot_enter_detailed_records(monkeypatch) -> None:
    public = layout.filter_public_hall_of_fame_rows(all_time_frame(), "fvcc")
    table = public[["canonical_player_id", "Player", "Runs"]].copy()
    filtered = layout.filter_detailed_record_tables_by_selected_player(
        {"batting": table, "bowling": table.copy(), "fielding": table.copy()},
        None,
    )
    assert_only_public(filtered["batting"], "Player")


def test_private_identity_cannot_enter_player_search(monkeypatch) -> None:
    source = category_frame()
    monkeypatch.setattr(layout, "read_processed_table", lambda _name: source.copy())
    monkeypatch.setattr(layout, "load_player_aliases", lambda **_kwargs: pd.DataFrame())
    monkeypatch.setattr(layout, "apply_player_identity_mapping", lambda frame, *_args, **_kwargs: frame.copy())
    index = layout.load_player_profile_index.__wrapped__("fvcc", 1.0, 1.0, "privacy-test")
    assert index.to_dict("records") == [{"id": PUBLIC_ID, "name": "Public Player"}]


def test_private_identity_receives_no_public_profile_link(monkeypatch) -> None:
    monkeypatch.setattr(layout, "public_player_profile_lookup", lambda *_args, **_kwargs: (frozenset(), {}))
    assert layout.resolve_public_profile_target(PRIVATE_ID, PRIVATE_NAME) == ""
    assert "<a " not in layout.player_profile_link_html(PRIVATE_ID, PRIVATE_NAME)


def test_private_identity_does_not_leak_through_query_parameters(monkeypatch) -> None:
    monkeypatch.setattr(layout, "public_player_profile_lookup", lambda *_args, **_kwargs: (frozenset(), {}))
    rendered = layout.player_profile_link_html(PRIVATE_ID, PRIVATE_NAME)
    assert "player_id=" not in rendered
    assert PRIVATE_ID not in rendered


def test_public_rows_remain_unchanged() -> None:
    source = category_frame().iloc[[0]].copy()
    result = layout.filter_public_hall_of_fame_rows(source, "fvcc")
    assert_frame_equal(result.reset_index(drop=True), source.reset_index(drop=True))


def test_canonical_public_aliases_still_deduplicate(monkeypatch) -> None:
    source = pd.concat([category_frame().iloc[[0]], category_frame().iloc[[0]]], ignore_index=True)
    source.loc[1, "player_id"] = "public-alias-raw"
    monkeypatch.setattr(layout, "read_processed_table", lambda _name: source.copy())
    monkeypatch.setattr(layout, "load_player_aliases", lambda **_kwargs: pd.DataFrame())
    monkeypatch.setattr(layout, "apply_player_identity_mapping", lambda frame, *_args, **_kwargs: frame.copy())
    index = layout.load_player_profile_index.__wrapped__("fvcc", 1.0, 1.0, "alias-test")
    assert index.to_dict("records") == [{"id": PUBLIC_ID, "name": "Public Player"}]


def test_legitimate_public_ranking_and_totals_are_unchanged() -> None:
    public_rows = pd.DataFrame(
        [
            {"canonical_player_id": "one", "Player": "One", "privacy_flag": "", "Runs": 200, "Bat Avg": 20.0},
            {"canonical_player_id": "two", "Player": "Two", "privacy_flag": "", "Runs": 100, "Bat Avg": 50.0},
        ]
    )
    with_private = pd.concat([public_rows, all_time_frame().iloc[[1]]], ignore_index=True)
    filtered = layout.filter_public_hall_of_fame_rows(with_private, "fvcc")
    ranked = layout.sort_hof_leaders(filtered, "Runs", "batting")
    assert ranked["Player"].tolist() == ["One", "Two"]
    assert ranked["Runs"].sum() == 300


def test_non_prepared_fvcc_path_filters_before_aggregation(monkeypatch) -> None:
    source_frame = category_frame()
    sources = {
        "all_seasons_batting": source_frame,
        "all_seasons_bowling": source_frame,
        "all_seasons_fielding": source_frame,
        "seasons": pd.DataFrame({"id": ["season"]}),
        "players": pd.DataFrame({"player_id": ["public-raw"]}),
    }
    captured: dict[str, pd.DataFrame] = {}

    def build_all_time(batting_raw, bowling_raw, fielding_raw, *_args):
        captured["batting_raw"] = batting_raw.copy()
        captured["bowling_raw"] = bowling_raw.copy()
        captured["fielding_raw"] = fielding_raw.copy()
        return pd.DataFrame({"canonical_player_id": [PUBLIC_ID], "Player": ["Public Player"]})

    monkeypatch.setattr(layout, "read_processed_table", lambda name: sources[name].copy())
    monkeypatch.setattr(layout, "normalise_player_names", lambda frame: frame.copy())
    monkeypatch.setattr(layout, "load_player_aliases", lambda: pd.DataFrame())
    monkeypatch.setattr(layout, "apply_player_identity_mapping", lambda frame, *_args, **_kwargs: frame.copy())
    monkeypatch.setattr(layout, "apply_team_grade_display_columns", lambda frame: frame.copy())
    monkeypatch.setattr(layout, "runtime_identity_maintenance_enabled", lambda: False)
    monkeypatch.setattr(layout, "allow_legacy_fallback", lambda: True)
    monkeypatch.setattr(layout, "load_prepared_hall_of_fame_core", lambda *_args: None)
    monkeypatch.setattr(layout, "combine_player_rows", lambda frame, _category: frame.copy())
    monkeypatch.setattr(layout, "add_batting_display_columns", lambda frame: frame.copy())
    monkeypatch.setattr(layout, "add_display_stat_aliases", lambda frame: frame.copy())
    monkeypatch.setattr(layout, "build_all_time_player_table", build_all_time)
    monkeypatch.setattr(layout, "estimate_historical_matches", lambda *_args: 1)
    monkeypatch.setattr(layout, "log_hof_timing", lambda *_args, **_kwargs: None)
    result = layout.load_hall_of_fame_data.__wrapped__(1.0, 1.0, club_id="fvcc")
    assert result is not None
    for frame in captured.values():
        assert_only_public(frame, "canonical_player_name")


def test_prepared_fvcc_path_filters_defensively(monkeypatch) -> None:
    public_category = category_frame().iloc[[0]].copy()
    prepared = {
        "batting": category_frame().copy(),
        "bowling": category_frame().copy(),
        "fielding": category_frame().copy(),
        "all_time": all_time_frame().copy(),
        "best_batting_season": None,
        "best_bowling_season": None,
    }
    sources = {
        "all_seasons_batting": public_category,
        "all_seasons_bowling": public_category,
        "all_seasons_fielding": public_category,
        "seasons": pd.DataFrame({"id": ["season"]}),
        "players": pd.DataFrame({"player_id": ["public-raw"]}),
    }
    monkeypatch.setattr(layout, "read_processed_table", lambda name: sources[name].copy())
    monkeypatch.setattr(layout, "normalise_player_names", lambda frame: frame.copy())
    monkeypatch.setattr(layout, "load_player_aliases", lambda: pd.DataFrame())
    monkeypatch.setattr(layout, "apply_player_identity_mapping", lambda frame, *_args, **_kwargs: frame.copy())
    monkeypatch.setattr(layout, "apply_team_grade_display_columns", lambda frame: frame.copy())
    monkeypatch.setattr(layout, "add_batting_display_columns", lambda frame: frame.copy())
    monkeypatch.setattr(layout, "add_display_stat_aliases", lambda frame: frame.copy())
    monkeypatch.setattr(layout, "runtime_identity_maintenance_enabled", lambda: False)
    monkeypatch.setattr(layout, "allow_legacy_fallback", lambda: True)
    monkeypatch.setattr(layout, "load_prepared_hall_of_fame_core", lambda *_args: prepared)
    monkeypatch.setattr(layout, "estimate_historical_matches", lambda *_args: 1)
    monkeypatch.setattr(layout, "log_hof_timing", lambda *_args, **_kwargs: None)
    result = layout.load_hall_of_fame_data.__wrapped__(1.0, 1.0, club_id="fvcc")
    assert result is not None
    assert_only_public(result["batting"], "canonical_player_name")
    assert_only_public(result["bowling"], "canonical_player_name")
    assert_only_public(result["fielding"], "canonical_player_name")
    assert_only_public(result["all_time"], "Player")


def test_fvcc_prepared_manifest_requires_public_filter_version(monkeypatch, tmp_path) -> None:
    frames = {
        "batting": category_frame().iloc[[0]].copy(),
        "bowling": category_frame().iloc[[0]].copy(),
        "fielding": category_frame().iloc[[0]].copy(),
        "all_time": all_time_frame().iloc[[0]].copy(),
    }
    monkeypatch.setattr(hall_of_fame_prepared, "prepared_core_source_signature", lambda _club: [])
    hall_of_fame_prepared.write_prepared_hall_of_fame_core(
        "fvcc",
        layout.HALL_OF_FAME_DATA_VERSION,
        frames,
        None,
        None,
        output_dir=tmp_path,
    )
    monkeypatch.setattr(hall_of_fame_prepared, "get_hall_of_fame_dir", lambda club_id=None: tmp_path)
    assert hall_of_fame_prepared.load_prepared_hall_of_fame_core(
        "fvcc", layout.HALL_OF_FAME_DATA_VERSION
    ) is not None

    manifest_path = tmp_path / hall_of_fame_prepared.MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest.pop("public_filter_version")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert hall_of_fame_prepared.load_prepared_hall_of_fame_core(
        "fvcc", layout.HALL_OF_FAME_DATA_VERSION
    ) is None


def test_fvcc_cache_signature_contains_public_filter_policy(monkeypatch) -> None:
    monkeypatch.setattr(layout, "featured_record_overrides_mtime", lambda: 0.0)
    monkeypatch.setattr(layout, "prepared_core_manifest_signature", lambda _club: tuple())
    signature = layout.hall_of_fame_override_signature("fvcc")
    assert ("public_filter", hall_of_fame_prepared.FVCC_HOF_PUBLIC_FILTER_VERSION) in signature


def test_grdcc_boundary_behavior_is_unchanged() -> None:
    source = category_frame()
    result = layout.filter_public_hall_of_fame_rows(source, "georges-river-district")
    assert_frame_equal(result.reset_index(drop=True), source.reset_index(drop=True))


def test_gwhcc_existing_public_filter_behavior_is_preserved() -> None:
    result = layout.filter_public_hall_of_fame_rows(category_frame(), "glen-waverley-hawks")
    assert_only_public(result, "canonical_player_name")
