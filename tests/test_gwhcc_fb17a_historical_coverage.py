from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.gwhcc_document_overrides import (
    historical_season_record,
    load_historical_seasons,
    merge_historical_seasons,
)
from src.ui import layout


ROOT = Path(__file__).resolve().parents[1]
CLUB_DATA = ROOT / "clubs" / "glen-waverley-hawks" / "data"
SOURCE = CLUB_DATA / "source" / "document_overrides"
PROCESSED = CLUB_DATA / "processed"


def test_verified_historical_seasons_cover_1980_81_through_1990_91() -> None:
    seasons = load_historical_seasons()
    assert seasons["season"].tolist() == [
        "Summer 1990/91",
        "Summer 1989/90",
        "Summer 1988/89",
        "Summer 1987/88",
        "Summer 1986/87",
        "Summer 1985/86",
        "Summer 1984/85",
        "Summer 1983/84",
        "Summer 1982/83",
        "Summer 1981/82",
        "Summer 1980/81",
    ]
    assert seasons["confidence"].eq("high").all()
    assert seasons["source_document"].eq("GWHCC_customer_source_consolidation.xlsx").all()


def test_historical_seasons_merge_only_for_gwhcc_without_fake_statistics() -> None:
    existing = [{"id": "playcricket-1991", "name": "Summer 1991/92", "isCurrentSeason": False}]
    merged = merge_historical_seasons(existing, "glen-waverley-hawks")
    assert len(merged) == 12
    historical = merged[-1]
    assert historical["name"] == "Summer 1980/81"
    assert historical["historicalMetadataOnly"] is True
    assert not {"matches", "players", "runs", "wickets"}.intersection(historical)
    assert historical_season_record(existing[0], "glen-waverley-hawks") is None
    assert merge_historical_seasons(existing, "fvcc") == existing
    assert merge_historical_seasons(existing, "georges-river-district") == existing


def test_historical_season_facts_are_evidence_backed() -> None:
    rows = load_historical_seasons().set_index("season")
    assert layout.historical_season_facts(rows.loc["Summer 1980/81"].to_dict()) == [
        "First XI participation confirmed"
    ]
    assert layout.historical_season_facts(rows.loc["Summer 1990/91"].to_dict()) == [
        "First XI participation confirmed",
        "Premiership: U/16",
    ]


def test_historical_coverage_state_reports_unavailable_not_zero(monkeypatch) -> None:
    season = merge_historical_seasons([], "glen-waverley-hawks")[-1]
    record = historical_season_record(season, "glen-waverley-hawks")
    captured: list[str] = []
    monkeypatch.setattr(layout.st, "markdown", lambda value, **_kwargs: captured.append(str(value)))
    layout.render_historical_season_coverage(
        {"season": season, "historical_record": record, "historical_metadata_only": True}
    )
    rendered = " ".join(captured)
    assert "Detailed PlayCricket match and player statistics are not available" in rendered
    assert "First XI participation confirmed" in rendered
    assert "0 matches" not in rendered
    assert "0 runs" not in rendered
    assert "0 wickets" not in rendered


def test_adrian_dale_profile_distinguishes_verified_start_from_detail(monkeypatch) -> None:
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    career = pd.Series({"earliest_documented_season": "Summer 1980/81"})
    seasons = pd.DataFrame({"Season": ["Summer 1995/96", "Summer 1996/97"]})
    assert layout.player_profile_historical_coverage(career, seasons) == (
        "Summer 1980/81",
        "Summer 1995/96",
    )
    rendered = layout.player_profile_historical_coverage_html(career, seasons)
    assert "Earliest verified GWHCC season: Summer 1980/81" in rendered
    assert "Detailed statistics available from: Summer 1995/96" in rendered


def test_all_34_governed_career_starts_remain_available() -> None:
    metadata = pd.read_csv(SOURCE / "gwhcc_historical_career_metadata.csv")
    assert len(metadata) == 34
    by_name = metadata.set_index("canonical_player_name")["earliest_documented_season"].to_dict()
    assert by_name["Adrian Dale"] == "Summer 1980/81"
    assert by_name["Greg Mccormick"] == "Summer 1985/86"


def test_profile_coverage_language_does_not_leak_to_other_clubs(monkeypatch) -> None:
    career = pd.Series({"earliest_documented_season": "Summer 1980/81"})
    seasons = pd.DataFrame({"Season": ["Summer 1995/96"]})
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")
    assert layout.player_profile_historical_coverage(career, seasons) == ("", "")
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "georges-river-district")
    assert layout.player_profile_historical_coverage(career, seasons) == ("", "")


def test_greg_approved_totals_and_non_additive_governance_remain_fixed() -> None:
    records = pd.read_csv(SOURCE / "gwhcc_record_overrides.csv")
    greg = records[records["player_name"].eq("G. McCormick")]
    assert dict(zip(greg["metric"], greg["document_value"])) == {
        "runs": 8664.0,
        "wickets": 393.0,
        "games": 427.0,
    }
    historical_seasons = pd.read_csv(SOURCE / "gwhcc_historical_seasons.csv")
    assert not {"matches", "runs", "wickets", "catches"}.intersection(historical_seasons.columns)


def test_existing_historical_and_bbb_outputs_are_unchanged() -> None:
    assert len(pd.read_csv(SOURCE / "gwhcc_historical_centuries.csv")) == 65
    assert len(pd.read_csv(PROCESSED / "hall_of_fame" / "premiership_wins.csv")) == 24
    assert len(pd.read_csv(SOURCE / "gwhcc_historical_premiership_events.csv")) == 29
    assert len(pd.read_csv(PROCESSED / "hall_of_fame" / "partnership_records.csv")) == 10
    assert len(pd.read_csv(PROCESSED / "hall_of_fame" / "hat_tricks.csv")) == 1
    assert len(pd.read_csv(PROCESSED / "hall_of_fame" / "fastest_batting_milestones.csv")) == 780
    assert len(pd.read_csv(PROCESSED / "hall_of_fame" / "prepared_career_all_time.csv")) == 1233


def test_private_player_filtering_outputs_remain_public() -> None:
    all_time = pd.read_csv(PROCESSED / "hall_of_fame" / "prepared_career_all_time.csv", low_memory=False)
    name_columns = [column for column in ["Player", "canonical_player_name", "player_name"] if column in all_time]
    assert name_columns
    for column in name_columns:
        assert not all_time[column].fillna("").astype(str).str.contains(r"\*{2,}", regex=True).any()
