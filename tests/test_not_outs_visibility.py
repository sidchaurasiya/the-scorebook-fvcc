from __future__ import annotations

import pandas as pd

from src.data.not_outs import (
    NOT_OUTS_COMPLETE,
    NOT_OUTS_PARTIAL,
    NOT_OUTS_UNAVAILABLE,
    add_complete_not_outs_for_display,
    mask_historical_not_outs,
    not_outs_coverage,
    profile_not_outs_coverage,
)
from src.ui import layout


def test_zero_not_outs_is_distinct_from_missing() -> None:
    zero = not_outs_coverage(pd.DataFrame({"battingNotOuts": [0, 0]}))
    missing = not_outs_coverage(pd.DataFrame({"battingNotOuts": [pd.NA, pd.NA]}))

    assert zero.status == NOT_OUTS_COMPLETE
    assert zero.value == 0
    assert missing.status == NOT_OUTS_UNAVAILABLE
    assert missing.value is None


def test_partial_historical_not_outs_remains_partial() -> None:
    coverage = not_outs_coverage(pd.DataFrame({"battingNotOuts": [2, pd.NA, 1]}))

    assert coverage.status == NOT_OUTS_PARTIAL
    assert coverage.value == 3


def test_grdcc_profile_uses_digital_not_outs_without_mixing_excel() -> None:
    frame = pd.DataFrame(
        [
            {"source_system": "playcricket", "raw_player_id": "modern", "battingNotOuts": 2},
            {"source_system": "excel", "raw_player_id": "excel_old", "battingNotOuts": 7},
            {"source_system": "excel", "raw_player_id": "excel_missing", "battingNotOuts": pd.NA},
        ]
    )

    coverage = profile_not_outs_coverage(frame, "georges-river-district")

    assert coverage.status == NOT_OUTS_PARTIAL
    assert coverage.value == 2


def test_grdcc_historical_season_values_are_masked_not_zeroed() -> None:
    frame = pd.DataFrame(
        [
            {"source_system": "excel", "raw_player_id": "excel_old", "battingNotOuts": 3},
            {"source_system": "playcricket", "raw_player_id": "modern", "battingNotOuts": 0},
        ]
    )

    masked = mask_historical_not_outs(frame, "georges-river-district")

    assert pd.isna(masked.iloc[0]["battingNotOuts"])
    assert masked.iloc[1]["battingNotOuts"] == 0


def test_fvcc_hof_not_outs_are_display_only_and_preserve_order_and_average() -> None:
    all_time = pd.DataFrame(
        [
            {"canonical_player_id": "one", "Player": "One", "Runs": 500, "Bat Avg": 33.33},
            {"canonical_player_id": "zero", "Player": "Zero", "Runs": 100, "Bat Avg": 10.0},
        ]
    )
    batting = pd.DataFrame(
        [
            {"canonical_player_id": "one", "battingNotOuts": 5},
            {"canonical_player_id": "zero", "battingNotOuts": 0},
        ]
    )

    result = add_complete_not_outs_for_display(all_time, batting)

    assert result["Player"].tolist() == ["One", "Zero"]
    assert result["Not Outs"].tolist() == [5, 0]
    assert result["Bat Avg"].tolist() == [33.33, 10.0]


def test_incomplete_player_total_is_not_added_to_hof() -> None:
    all_time = pd.DataFrame([{"canonical_player_id": "partial", "Player": "Partial", "Bat Avg": 20.0}])
    batting = pd.DataFrame(
        [
            {"canonical_player_id": "partial", "battingNotOuts": 2},
            {"canonical_player_id": "partial", "battingNotOuts": pd.NA},
        ]
    )

    result = add_complete_not_outs_for_display(all_time, batting)

    assert "Not Outs" not in result or result["Not Outs"].isna().all()
    assert result.iloc[0]["Bat Avg"] == 20.0


def test_player_profile_metrics_are_club_aware_without_hybrid_average(monkeypatch) -> None:
    career = pd.Series(
        {
            "Innings": 20,
            "Outs": 15,
            "Runs": 500,
            "Not Outs": 5,
            "Bat Avg": 33.33,
            "Bat SR": 80,
            "0s": 2,
            "HS": "100*",
            "not_outs_coverage_status": NOT_OUTS_PARTIAL,
        }
    )
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "georges-river-district")

    metrics = dict(layout.player_profile_batting_career_metrics(career, "20"))

    assert metrics["Not Outs"] == "5"
    assert metrics["Average"] == "33.33"


def test_fvcc_player_profile_displays_genuine_zero_not_outs(monkeypatch) -> None:
    career = pd.Series(
        {
            "Innings": 8,
            "Outs": 8,
            "Runs": 80,
            "Bat Avg": 10,
            "Bat SR": 50,
            "0s": 0,
            "HS": 20,
        }
    )
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")

    metrics = dict(layout.player_profile_batting_career_metrics(career, "8"))

    assert metrics["Not Outs"] == "0"
    assert layout.profile_batting_table_columns("Season")[2] == "Not Outs"


def test_grdcc_missing_historical_not_outs_displays_unavailable(monkeypatch) -> None:
    career = pd.Series(
        {
            "Innings": 10,
            "Outs": 10,
            "Runs": 100,
            "Not Outs": pd.NA,
            "Bat Avg": 10.0,
            "Bat SR": pd.NA,
            "0s": 1,
            "HS": 30,
            "not_outs_coverage_status": NOT_OUTS_UNAVAILABLE,
        }
    )
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "georges-river-district")

    metrics = dict(layout.player_profile_batting_career_metrics(career, "10"))

    assert metrics["Not Outs"] == "N/A"
    assert metrics["Average"] == "10.00"


def test_grdcc_hof_does_not_add_partial_not_outs(monkeypatch) -> None:
    all_time = pd.DataFrame([{"canonical_player_id": "historical", "Player": "Historical"}])
    batting = pd.DataFrame([{"canonical_player_id": "historical", "battingNotOuts": 2}])
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "georges-river-district")

    result = layout.add_club_not_outs_for_display(all_time, batting)

    assert "Not Outs" not in result.columns


def test_season_detail_not_outs_visibility_is_club_scoped(monkeypatch) -> None:
    frame = pd.DataFrame(
        [
            {
                "player_name": "Player",
                "matches": 2,
                "battingInnings": 2,
                "battingNotOuts": 0,
                "battingAggregate": 20,
            }
        ]
    )
    for club_id in ["fvcc", "georges-river-district"]:
        monkeypatch.setattr(layout, "get_active_club_id", lambda club_id=club_id: club_id)
        result = layout.get_batting_display_df(frame)
        assert result["Not Outs"].tolist() == [0]

    private = frame.copy()
    private["player_name"] = "********"
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "georges-river-district")
    assert layout.get_batting_display_df(private)["Not Outs"].isna().all()


def test_gwhcc_existing_helper_behaviour_is_unchanged() -> None:
    all_time = pd.DataFrame(
        [{"canonical_player_id": "one", "Player": "One", "Bat Avg": 25.0}]
    )
    batting = pd.DataFrame(
        [{"canonical_player_id": "one", "player_name": "One", "battingNotOuts": 3}]
    )

    result = layout.add_gwhcc_not_outs_for_display(all_time, batting)

    assert result.iloc[0]["Not Outs"] == 3
    assert result.iloc[0]["Bat Avg"] == 25.0


def test_current_fvcc_and_grdcc_sources_reconcile_without_average_changes() -> None:
    sources = [
        ("clubs/fvcc/data/processed/all_seasons_batting.csv", 1912, 1912, 0, 0),
        ("clubs/georges-river-district/data/processed/all_seasons_batting.csv", 7789, 7789, 0, 0),
        (
            "clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_batting.csv",
            4980,
            2981,
            1999,
            6,
        ),
    ]
    for path, expected_rows, expected_populated, expected_missing, expected_mismatches in sources:
        frame = pd.read_csv(path, low_memory=False)
        innings = pd.to_numeric(frame["battingInnings"], errors="coerce")
        not_outs = pd.to_numeric(frame["battingNotOuts"], errors="coerce")
        runs = pd.to_numeric(frame["battingAggregate"], errors="coerce")
        average = pd.to_numeric(frame["battingAverage"], errors="coerce")
        calculated = runs / (innings - not_outs).where((innings - not_outs) > 0)
        comparable = calculated.notna() & average.notna()

        assert len(frame) == expected_rows
        assert int(not_outs.notna().sum()) == expected_populated
        assert int(not_outs.isna().sum()) == expected_missing
        assert int((not_outs > innings).fillna(False).sum()) == 0
        assert int(((calculated - average).abs().gt(0.05) & comparable).sum()) == expected_mismatches
