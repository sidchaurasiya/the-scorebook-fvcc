from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.ui import layout


ROOT = Path(__file__).resolve().parents[1]
GWHCC_BATTING = ROOT / "clubs" / "glen-waverley-hawks" / "data" / "processed" / "hall_of_fame" / "prepared_career_batting.csv"


def test_hof_not_outs_are_display_only_and_preserve_career_values() -> None:
    all_time = pd.DataFrame(
        [
            {"canonical_player_id": "public_one", "Player": "Public One", "Runs": 500, "Innings": 20, "Bat Avg": 33.33},
            {"canonical_player_id": "public_zero", "Player": "Public Zero", "Runs": 100, "Innings": 10, "Bat Avg": 10.0},
        ]
    )
    batting = pd.DataFrame(
        [
            {"canonical_player_id": "public_one", "player_name": "Public One", "battingNotOuts": 5},
            {"canonical_player_id": "public_zero", "player_name": "Public Zero", "battingNotOuts": 0},
        ]
    )
    result = layout.add_gwhcc_not_outs_for_display(all_time, batting)
    assert result["Not Outs"].tolist() == [5, 0]
    assert result["Runs"].tolist() == [500, 100]
    assert result["Innings"].tolist() == [20, 10]
    assert result["Bat Avg"].tolist() == [33.33, 10.0]


def test_hof_not_outs_do_not_introduce_duplicates_or_private_players() -> None:
    all_time = pd.DataFrame(
        [
            {"canonical_player_id": "public", "Player": "Public Player", "Runs": 10},
            {"canonical_player_id": "private", "Player": "********", "Runs": 9999},
        ]
    )
    batting = pd.DataFrame(
        [
            {"canonical_player_id": "public", "player_name": "Public Player", "battingNotOuts": 1},
            {"canonical_player_id": "private", "player_name": "********", "battingNotOuts": 99},
        ]
    )
    result = layout.add_gwhcc_not_outs_for_display(all_time, batting)
    assert result["canonical_player_id"].tolist() == ["public"]
    assert not result["canonical_player_id"].duplicated().any()


def test_hof_batting_table_exposes_not_outs_without_changing_rank_order() -> None:
    all_time = pd.DataFrame(
        [
            {"canonical_player_id": "second", "Player": "Second", "Runs": 100, "Not Outs": 0, "Bat Avg": 10},
            {"canonical_player_id": "first", "Player": "First", "Runs": 200, "Not Outs": 8, "Bat Avg": 20},
        ]
    )
    result = layout.format_all_time_batting_table(all_time)
    assert "Not Outs" in result.columns
    assert result["Not Outs"].tolist() == [8, 0]
    assert result["Runs"].tolist() == [200, 100]
    assert result["Bat Avg"].tolist() == [20, 10]


def test_season_overview_batting_detail_exposes_not_outs_for_gwhcc(monkeypatch) -> None:
    source = pd.DataFrame(
        [
            {
                "canonical_player_id": "player",
                "player_name": "Public Player",
                "team_name": "Glen Waverley Hawks",
                "matches": 10,
                "battingInnings": 9,
                "battingNotOuts": 3,
                "battingAggregate": 300,
                "battingAverage": 50.0,
            }
        ]
    )
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    hawks = layout.get_batting_display_df(source)
    assert hawks["Not Outs"].tolist() == [3]
    assert hawks["Runs"].tolist() == [300]
    assert hawks["Bat Avg"].tolist() == [50.0]

def test_player_profile_career_metrics_show_not_outs_without_changing_average(monkeypatch) -> None:
    career = pd.Series({"Innings": 20, "Outs": 15, "Runs": 500, "Bat Avg": 33.33, "Bat SR": 80, "0s": 2, "HS": "100*"})
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    metrics = dict(layout.player_profile_batting_career_metrics(career, "18"))
    assert metrics["Not Outs"] == "5"
    assert metrics["Runs"] == "500"
    assert metrics["Average"] == "33.33"


def test_player_profile_zero_not_outs_for_gwhcc(monkeypatch) -> None:
    career = pd.Series({"Innings": 8, "Outs": 8, "Runs": 80, "Bat Avg": 10, "Bat SR": 50, "0s": 0, "HS": 20})
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    hawks_metrics = dict(layout.player_profile_batting_career_metrics(career, "8"))
    assert hawks_metrics["Not Outs"] == "0"
    assert layout.profile_batting_table_columns("Season")[2] == "NO"

def test_gwhcc_not_outs_coverage_note_is_club_scoped(monkeypatch) -> None:
    messages: list[str] = []
    monkeypatch.setattr(layout.st, "caption", messages.append)
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    layout.render_gwhcc_not_outs_coverage_note()
    assert messages == ["Not Outs reflect available PlayCricket batting records; historical document-only totals may differ."]

    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")
    layout.render_gwhcc_not_outs_coverage_note()
    assert len(messages) == 1


def test_prepared_gwhcc_averages_still_reconcile_with_not_outs() -> None:
    batting = pd.read_csv(GWHCC_BATTING, low_memory=False)
    runs = pd.to_numeric(batting["battingAggregate"], errors="coerce")
    innings = pd.to_numeric(batting["battingInnings"], errors="coerce")
    not_outs = pd.to_numeric(batting["battingNotOuts"], errors="coerce")
    average = pd.to_numeric(batting["battingAverage"], errors="coerce")
    calculated = runs / (innings - not_outs).clip(lower=0).replace(0, pd.NA)
    comparable = average.notna() & calculated.notna()
    assert int(comparable.sum()) == 1100
    assert (average[comparable] - calculated[comparable]).abs().max() < 1e-9
    assert int(not_outs.fillna(0).eq(0).sum()) == 304
