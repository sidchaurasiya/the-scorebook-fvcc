from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.gwhcc_governance import annotate_grade_metadata, display_grade_name, grade_mapping_row
from src.data.gwhcc_document_overrides import apply_record_overrides
from src.data.gwhcc_player_status import governed_player_active
from src.ui import layout
from src.utils.player_identity import (
    apply_player_identity_mapping,
    filter_public_player_rows,
    is_private_or_anonymised_player,
)


ROOT = Path(__file__).resolve().parents[1]
CLUB_ID = "glen-waverley-hawks"
PROCESSED = ROOT / "clubs" / CLUB_ID / "data" / "processed"


def test_customer_feedback_identity_merges_are_unique_in_profile_index(monkeypatch) -> None:
    monkeypatch.setenv("CLUB_ID", CLUB_ID)
    index = layout.load_player_profile_index(
        CLUB_ID,
        layout.metadata_mtime(),
        layout.player_aliases_mtime(),
    )
    for name in ["Greg Mccormick", "Ahilan Sivakumaran", "Reece Anderson", "Dulaj Madushanka", "James Anderson"]:
        assert index["name"].str.casefold().eq(name.casefold()).sum() == 1


def test_customer_feedback_historical_centuries_and_debut_are_governed() -> None:
    all_time = pd.read_csv(PROCESSED / "hall_of_fame" / "prepared_career_all_time.csv", low_memory=False)
    authoritative = apply_record_overrides(all_time, write_decisions=False)
    expected_hundreds = {
        "Sunny Somaia": 19,
        "Glen Mahoney": 16,
        "Stuart Wynd": 15,
        "Greg Mccormick": 8,
        "Brett Powell": 6,
        "Dulaj Madushanka": 3,
    }
    for name, expected in expected_hundreds.items():
        row = authoritative[authoritative["Player"].astype(str).str.casefold().eq(name.casefold())]
        assert len(row) == 1
        assert int(row.iloc[0]["100s"]) == expected
    adrian = authoritative[authoritative["Player"].astype(str).str.casefold().eq("adrian dale")]
    assert len(adrian) == 1
    assert adrian.iloc[0]["Debut Season"] == "Summer 1980/81"


def test_gwhcc_active_status_uses_governed_current_club_evidence() -> None:
    assert not governed_player_active(True, "arun_chelvan", "Arun Chelvan")
    assert not governed_player_active(True, "ahilan_sivakumaran", "Ahilan Sivakumaran")
    assert governed_player_active(False, "nathan_bungey", "Nathan Bungey")


def test_customer_feedback_fastest_innings_are_deployed() -> None:
    records = pd.read_csv(PROCESSED / "hall_of_fame" / "fastest_batting_milestones.csv", low_memory=False)
    arun = records[
        records["match_id"].astype(str).eq("4c2ca82a-a39d-4904-a122-3b532617a86b")
        & records["participant_id"].astype(str).eq("7ebc3350-3efe-4d6f-88f6-2b3a0a568a8d")
    ]
    luke = records[
        records["match_id"].astype(str).eq("bd66ac0a-98d6-4733-aad4-ef7dfe1e0cea")
        & records["participant_id"].astype(str).eq("5e51cdc2-8d9e-4583-badc-2922f6095d48")
    ]
    assert len(arun) == 1 and int(arun.iloc[0]["balls_to_50"]) == 18
    assert len(luke) == 1 and int(luke.iloc[0]["balls_to_100"]) == 37
    assert not bool(luke.iloc[0]["source_ball_by_ball_available"])


def test_historical_profile_season_sort_supports_1900s() -> None:
    assert layout.profile_season_sort_key("Summer 1980/81") < layout.profile_season_sort_key("Summer 1995/96")
    assert layout.profile_season_sort_key("Summer 1995/96") < layout.profile_season_sort_key("Summer 2000/01")


def test_nathan_bungey_resolves_to_one_canonical_identity() -> None:
    raw_ids = [
        "59057be9-29af-4675-a662-7370e4f9cd44",
        "fc4ba90e-5a13-4348-8811-29947e4461fb",
    ]
    frame = pd.DataFrame({"player_id": raw_ids, "player_name": ["Nathan Bungey"] * 2})
    mapped = apply_player_identity_mapping(frame, club_id=CLUB_ID)
    assert mapped["canonical_player_id"].nunique() == 1
    assert mapped.iloc[0]["canonical_player_id"] == "nathan_bungey"


def test_public_profile_index_has_one_nathan_and_no_private_players() -> None:
    index = layout.load_player_profile_index(
        CLUB_ID,
        layout.metadata_mtime(),
        layout.player_aliases_mtime(),
    )
    assert index["name"].str.casefold().eq("nathan bungey").sum() == 1
    assert not index["name"].map(is_private_or_anonymised_player).any()


def test_private_players_are_filtered_without_mutating_source() -> None:
    source = pd.DataFrame({"player_name": ["********", "Public Player"], "runs": [99, 10]})
    public = filter_public_player_rows(source)
    assert source["runs"].sum() == 109
    assert public["player_name"].tolist() == ["Public Player"]
    assert is_private_or_anonymised_player("********")


def test_private_profile_links_are_not_generated(monkeypatch) -> None:
    monkeypatch.setattr(layout, "public_player_profile_lookup", lambda *_args: (frozenset({"public"}), {"public player": "public"}))
    assert layout.resolve_public_profile_target("private", "********") == ""
    assert "<a " not in layout.player_profile_link_html("private", "********")


def test_private_season_round_performance_is_redacted() -> None:
    assert layout.season_round_performer_html("******** 100*", []) == "—"
    assert layout.season_round_performer_html("******** 2-37", []) == "—"


def test_invalid_document_profile_is_plain_text(monkeypatch) -> None:
    monkeypatch.setattr(layout, "public_player_profile_lookup", lambda *_args: (frozenset({"public"}), {"public player": "public"}))
    assert layout.resolve_public_profile_target("doc_j_davies", "J. Davies") == ""
    assert "<a " not in layout.player_profile_link_html("doc_j_davies", "J. Davies")


def test_unique_document_name_can_resolve_to_public_profile(monkeypatch) -> None:
    monkeypatch.setattr(layout, "public_player_profile_lookup", lambda *_args: (frozenset({"grant_haye"}), {"grant haye": "grant_haye"}))
    assert layout.resolve_public_profile_target("doc_g_haye", "Grant Haye") == "grant_haye"


def test_authoritative_profile_headline_totals_preserve_weighted_matches(monkeypatch) -> None:
    authoritative = pd.DataFrame(
        [{"canonical_player_id": "paul_young", "Matches": 112.5, "Runs": 4282, "Wickets": 7, "Catches": 44}]
    )
    monkeypatch.setattr(layout, "get_authoritative_career_totals", lambda *_args, **_kwargs: authoritative)
    career = pd.DataFrame([{"Matches": 110, "Runs": 4200, "Wickets": 7, "Catches": 40}])
    profile = {"player_info": {"canonical_player_id": "paul_young"}}
    result = layout.apply_authoritative_profile_career_totals(career, profile, CLUB_ID)
    assert result.iloc[0]["Matches"] == 112.5
    assert result.iloc[0]["Runs"] == 4282


def test_weighted_match_formatting() -> None:
    assert layout.format_compact_number(112.5) == "112.5"
    assert layout.format_compact_number(113.0) == "113"
    row = pd.Series({"Matches": 112.5, "Innings": 100, "Runs": 1})
    assert layout.historical_matches_display_text(row)[0] == "112.5"


def test_premiership_short_season_resolves_to_canonical(monkeypatch) -> None:
    monkeypatch.setattr(
        layout,
        "canonical_season_navigation_lookup",
        lambda *_args: {"17-18": "Summer 2017/18"},
    )
    assert layout.canonical_season_navigation_value("17-18") == "Summer 2017/18"


def test_premiership_display_uses_ending_year_without_changing_navigation(monkeypatch) -> None:
    canonical = {
        "25-26": "Summer 2025/26",
        "23-24": "Summer 2023/24",
        "17-18": "Summer 2017/18",
        "12-13": "Summer 2012/13",
        "08-09": "Summer 2008/09",
    }
    monkeypatch.setattr(
        layout,
        "canonical_season_navigation_value",
        lambda season: canonical.get(str(season), str(season)),
    )
    assert layout.premiership_final_year_label("25-26") == "2026"
    assert layout.premiership_final_year_label("23-24") == "2024"
    assert layout.premiership_final_year_label("17-18") == "2018"
    assert layout.premiership_final_year_label("12-13") == "2013"
    assert layout.premiership_final_year_label("08-09") == "2009"
    assert layout.premiership_final_year_label("2013") == "2013"

    rendered = layout.compact_premiership_final_year_link_html("17-18")
    assert ">2018</a>" in rendered
    assert "season=Summer%202017%2F18" in rendered
    assert "season=2018" not in rendered


def test_latest_default_season_has_activity() -> None:
    assert layout.latest_season_with_activity(CLUB_ID, layout.metadata_mtime()) == "Summer 2025/26"


def test_fastest_innings_grade_uses_governed_label() -> None:
    assert display_grade_name("3. Compare & Conect Dorothy McIntosh Shield") == (
        "Compare & Connect Dorothy McIntosh Shield"
    )


def test_persisted_governance_matches_expected() -> None:
    teams = pd.read_csv(PROCESSED / "teams.csv", low_memory=False)
    expected = annotate_grade_metadata(teams[[column for column in teams.columns if column != "grade_group"]], "grade_name")
    assert "grade_group" in teams
    assert teams["grade_group"].fillna("").astype(str).tolist() == expected["grade_group"].fillna("").astype(str).tolist()


def test_known_junior_governance() -> None:
    for grade in ["Super 7's - Sunday Gold", "Fast 9's - Sunday Gold", "U12 A Grade", "U13 A Grade", "U14 A Grade", "U16 B Grade", "Girls Stage 1"]:
        assert grade_mapping_row(grade)["grade_group"] == "Junior"
    assert grade_mapping_row("1st XI")["grade_group"] == "Senior/open"


def test_duplicate_team_selector_labels_are_disambiguated() -> None:
    teams = [
        {"id": "a", "name": "09. Fast 9's GOLD", "display_name": "Fast 9's - Sunday Gold", "grade": {"name": "Fast 9's - Sunday Gold"}},
        {"id": "b", "name": "10. Fast 9's BROWN", "display_name": "Fast 9's - Sunday Gold", "grade": {"name": "Fast 9's - Sunday Gold"}},
        {"id": "c", "name": "02. 2nd XI", "display_name": "C Grade", "grade": {"name": "C Grade"}},
    ]
    labels = layout.team_selector_labels(teams)
    assert labels["c"] == "C Grade"
    assert labels["a"] != labels["b"]
    assert not labels["a"].startswith("09.")


def test_singular_plural_and_exclusive_threshold_order() -> None:
    assert layout.normalize_result_wording("Won by 1 wickets") == "Won by 1 wicket"
    assert layout.normalize_result_wording("won by 1 runs") == "won by 1 run"
    assert layout.grammatical_unit(1, "catches") == "catch"
    assert sorted(layout.exclusive_club_specs("matches", CLUB_ID)[0]["thresholds"], reverse=True) == [400, 300, 200, 100, 50]


def test_customer_footer_hides_build_marker_and_keeps_email_intact(monkeypatch) -> None:
    monkeypatch.setattr(layout, "SHOW_ROUTING_DEBUG", False)
    assert layout.app_build_marker_html() == ""
    monkeypatch.setattr(layout, "SHOW_ROUTING_DEBUG", True)
    assert 'class="side-build-marker"' in layout.app_build_marker_html()
    assert "<br>" not in layout.configured_feedback_email_html()
    assert "@" in layout.configured_feedback_email_html()


def test_batting_position_source_note_only_appears_for_repeated_positions() -> None:
    repeated = pd.DataFrame({"position_group": ["Opener", "Opener", "No. 3"]})
    unique = pd.DataFrame({"position_group": ["Opener", "No. 3"]})
    assert "separate historical PlayCricket source profiles" in layout.batting_position_source_note_html(repeated)
    assert layout.batting_position_source_note_html(unique) == ""


def test_unavailable_team_leader_average_displays_dash() -> None:
    assert "Avg. —" in layout.average_stat_html(float("nan"), "Batting avg.")
    assert "Batting avg. 0.0" in layout.average_stat_html(0.0, "Batting avg.")
