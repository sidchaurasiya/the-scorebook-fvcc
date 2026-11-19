from types import SimpleNamespace

import pandas as pd
import pytest

from src.data.achieved_match_context import contributions, resolve_crossing, season_start_total
from src.ui import layout


def test_grdcc_principal_grades_then_distinct_played_matches(monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "georges-river-district")
    labels = {
        "First Grade The RB Clark Cup": ["a"],
        "Second Grade The SJ Mayne Trophy": ["b"],
        "Third Grade The JB Hollander Cup": ["c"],
        "Fourth Grade The Harry Culbert Trophy": ["d"],
        "Fifth Grade The Tim Creer Cup": ["e"],
        "First Grade Limited Overs": ["f"],
        "Chappelow Cup": ["g", "g", "g", "h"],
        "Metropolitan Cup": ["i", "j", "k"],
    }
    rows = [dict(grade=label, match_id=id_) for label, ids in labels.items() for id_ in ids]
    order = layout.season_display_grade_order(rows)
    assert sorted(labels, key=lambda label: order[label.casefold()]) == [
        *list(labels)[:5], "Metropolitan Cup", "Chappelow Cup", "First Grade Limited Overs",
    ]
    assert order["chappelow cup"][1] == -2


@pytest.mark.parametrize("club", ["glen-waverley-hawks", "fvcc"])
def test_equivalent_xi_separate_from_t20(monkeypatch, club):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: club)
    assert layout.principal_season_grade("Shield", "Club - 2nd XI") == 1
    assert layout.principal_season_grade("T20 Shield", "Club - 1st XI") == 99
    assert layout.principal_season_grade("Junior Grade", "U12 A Grade") == 99


def test_round_scorecard_moves_under_its_own_result(monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "georges-river-district")
    item = dict(match_id="exact-match", grade="Metro", opponent="A very long opponent full name",
                result_label="Won", result_text="won by 4 wickets", round="R5",
                playing_dates=["2026-11-07", "2026-11-14"],
                scorecard='<a href="https://play.cricket.com.au/match/exact-match?tab=scorecard">View scorecard ↗</a>')
    result = layout.season_round_cards_html([item])
    assert 'role="columnheader">Scorecard' not in result
    assert 'A very long opponent full name' in result
    assert result.count('/match/exact-match?tab=scorecard') == 1
    assert result.index("won by 4 wickets") < result.index("/match/exact-match") < result.index("Batter:")
    assert "07-11-2026" in result and "14-11-2026" in result


def test_governed_multi_innings_and_fractional_appearance():
    date = pd.Timestamp("2026-11-07")
    season = "Summer 2026/27"
    eligibility = pd.DataFrame([{
        "season": season, "match_id": "m1", "start": date, "end": date + pd.Timedelta(days=7), "weight": 0.5,
    }])
    identity = pd.DataFrame([{"season": season, "raw_player_id": "raw-alpha", "canonical_player_id": "canonical-alpha"}])
    batting = pd.DataFrame([
        {"season": season, "match_id": "m1", "player_id": "raw-alpha", "runs": 31},
        {"season": season, "match_id": "m1", "player_id": "raw-alpha", "runs": 54},
        {"season": season, "match_id": "different-club-or-ineligible", "player_id": "raw-alpha", "runs": 90},
    ])
    grouped = contributions({"batting": batting, "bowling": pd.DataFrame(), "fielding": pd.DataFrame()}, identity, eligibility)
    runs, reason = resolve_crossing(grouped["Runs"], 85, 930, 1000)
    weight, _ = resolve_crossing(grouped["Matches"], 0.5, 99.5, 100)
    assert reason == "Verified exact match"
    assert runs.match_id == "m1" and runs.contribution == 85
    assert runs.end == pd.Timestamp("2026-11-14")
    assert weight.contribution == 0.5
    assert resolve_crossing(grouped["Runs"], 90, 930, 1000) == (
        None, "Source totals do not reconcile to the approved season contribution",
    )


def test_overlapping_matches_are_not_given_a_fabricated_order():
    day = pd.Timestamp("2026-11-07")
    values = pd.DataFrame([
        {"match_id": "a", "start": day, "end": day + pd.Timedelta(days=7), "contribution": 1},
        {"match_id": "b", "start": day + pd.Timedelta(days=1), "end": day + pd.Timedelta(days=1), "contribution": 1},
    ])
    assert resolve_crossing(values, 2, 99, 100) == (None, "Playing dates overlap at the threshold")


def test_approved_historical_anchor_keeps_season_only_case(monkeypatch):
    career = pd.Series({"Matches": 301, "historical_match_anchor_applied": True,
                        "historical_match_anchor_through_season": "Summer 2025/26"})
    history = pd.DataFrame([{"season": "Summer 2025/26", "Matches": 7}])
    assert season_start_total(career, history, "Summer 2025/26", "Matches", str) is None

    monkeypatch.setattr(layout, "player_profile_link_html", lambda *_: "Player A")
    row = pd.Series({"Player": "Player A", "Category": "Matches", "Season": "Summer 2025/26",
                     "Current Total": 301, "Milestone": "300 matches reached", "Unit": "matches"})
    card = layout.achievement_card_html(row)
    assert "Exact match unavailable" in card and "View scorecard" not in card


@pytest.mark.parametrize("club", ["georges-river-district", "fvcc"])
def test_match_source_change_invalidates_cached_fallback_milestones(monkeypatch, tmp_path, club):
    from src.data import achieved_match_context as context

    monkeypatch.setattr(context, "get_processed_path", lambda file, club_id: tmp_path / file)
    calls = []
    monkeypatch.setattr(layout, "load_hall_of_fame_data", lambda *args, **kwargs: {"all_time": pd.DataFrame()})
    monkeypatch.setattr(layout, "get_authoritative_career_totals", lambda *args, **kwargs: pd.DataFrame())
    monkeypatch.setattr(layout, "milestone_achievement_season_window", lambda *_: ["Summer 2026/27"])
    monkeypatch.setattr(layout, "build_hall_of_fame_movements", lambda *_: pd.DataFrame())

    def capture(*_args, match_context_signature):
        calls.append(match_context_signature)
        return pd.DataFrame()

    monkeypatch.setattr(layout, "build_achieved_milestones", capture)
    path = tmp_path / context.FILES["batting"]
    path.write_text("first")
    first = context.source_signature(club)
    load = layout.load_portability_milestone_page_data
    load.clear()
    args = (1, 1, "match-source-regression", (), (), club, "achieved")
    load(*args, match_context_signature=first)
    load(*args, match_context_signature=first)
    assert calls == [first]

    replacement = tmp_path / "next-batting"
    replacement.write_text("later")
    replacement.replace(path)
    second = context.source_signature(club)
    load(*args, match_context_signature=second)
    path.unlink()
    removed = context.source_signature(club)
    load(*args, match_context_signature=removed)
    assert len({first, second, removed}) == 3
    assert calls == [first, second, removed]
    load.clear()


def test_detailed_table_match_ties_do_not_reverse():
    from src.ui.stat_table_semantics import initial_order
    table = pd.DataFrame({
        "Player": ["Beta", "Gamma", "Alpha", "Absent", "Below"],
        "Matches": [2, 0.5, 2, None, 10],
        "Win %": [100, 100, 100, 100, 90],
        "Runs": [10, 10, 10, 10, 1],
        "0s": [0, 0, 0, 0, 1],
    })

    for ascending in (False, True):
        ties = initial_order(table, "Win %", "Player", ascending=ascending)
        assert ties.loc[ties["Win %"].eq(100), "Player"].tolist() == ["Alpha", "Beta", "Gamma", "Absent"]
        for column, value in (("Runs", 10), ("0s", 0)):
            ties = initial_order(table, column, "Player", ascending=ascending)
            assert ties.loc[ties[column].eq(value), "Player"].tolist() == ["Gamma", "Alpha", "Beta", "Absent"]


@pytest.mark.parametrize(("label", "value", "formatted"), [
    ("Bat SR", 67.164179, "67.16%"),
    ("Bat SR (ball-by-ball)", 47, "47.00%"),
    ("Strike Rate", 113.114754, "113.11%"),
    ("Strike Rate (ball-by-ball)", 0, "0.00%"),
])
def test_batting_rate_display_and_sort_precision(label, value, formatted):
    assert layout.hof_detail_display_value(label, value) == formatted
    assert layout.profile_performance_display_value(label, value, "Grade") == formatted
    assert layout.season_detail_display_value(label, value) == formatted
    assert layout.season_detail_column_class(label) == "season-col-bat-sr"
    assert float(layout.profile_performance_sort_value(label, value, "Grade")[0]) == value
    assert layout.profile_performance_display_value("SR", 0.5, "Grade") == "0.50"
    assert layout.season_detail_display_value("M", 0.5) == "0.5"


def test_hawks_grade_instructions_preserve_all_groups(monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    labels = ["Fast 9's - Sunday Gold", "U12 C Grade", "U16 Friday B Grade", "D Grade", "T20 G - Trophy",
              "Girls Super 7s", "U14 D Grade", "U12 A Grade", "Compare & Connect Shield", "C Grade", "T20 B - Shield"]
    assert sorted(labels, key=layout.hawks_season_grade_order) == [
        "Compare & Connect Shield", "C Grade", "D Grade", "T20 B - Shield", "T20 G - Trophy",
        "U16 Friday B Grade", "U14 D Grade", "U12 A Grade", "U12 C Grade",
        "Fast 9's - Sunday Gold", "Girls Super 7s",
    ]


def test_appearance_evidence_distinguishes_zero_and_not_batted():
    from src.data.achieved_match_context import appearance_batting_performance
    assert appearance_batting_performance(pd.DataFrame([dict(runs=4, balls=24)])) == "4 runs from 24 balls"
    assert appearance_batting_performance(pd.DataFrame([dict(runs=0, balls=5)])) == "0 runs from 5 balls"
    assert appearance_batting_performance(pd.DataFrame([dict(runs=0, balls=0, dismissal="did not bat")])) == "Did not bat"
    assert appearance_batting_performance(pd.DataFrame([dict(runs=None, balls=None)])) == "Batting performance unavailable"
    assert appearance_batting_performance(pd.DataFrame([dict(runs=0, balls=None)])) == "0 runs (balls faced unavailable)"


def test_match_context_uses_verified_playing_day_instead_of_schedule():
    from src.data.achieved_match_context import match_context
    fixture = pd.DataFrame([dict(season="Summer 2026/27", match_id="m", match_date="2026-10-07",
                                 round_display="R3", opponent_name="Example Cricket Club")])
    dates = {"m": ["2026-10-07", "2026-10-14"]}
    frames = {"rounds": fixture, "verified_dates": {"m": {"date": "2026-10-07", "scheduled_dates": dates["m"]}}}
    result = match_context(frames, dates, "georges-river-district").iloc[0]
    assert result.match_date_label == "7 Oct 2026" and result.end == pd.Timestamp("2026-10-07")
    frames.pop("verified_dates")
    unresolved = match_context(frames, dates, "georges-river-district").iloc[0]
    assert "Final playing date unavailable" in unresolved.match_date_label
    assert unresolved.end == pd.Timestamp("2026-10-14")


def test_profile_fallback_uses_the_shared_sorting_metadata(monkeypatch):
    markup = []
    monkeypatch.setattr(layout.components, "html", lambda body, **_: markup.append(body))
    monkeypatch.setattr(layout, "season_overview_url", lambda label: f"?page=season-overview#{label}")
    source = pd.DataFrame({"Season": ["Summer 2026/27", "Summer 2025/26"], "Runs": [9, 9], "Matches": [0.5, 2]})
    layout.render_governed_profile_table(source[["Season", "Runs"]], source, "Season")
    assert 'data-match-count="0.5"' in markup[0] and 'data-match-count="2.0"' in markup[0]
    assert 'data-matches-dir="asc"' in markup[0]
    assert "match_count_for_sort" not in markup[0]
    assert "?page=season-overview" in markup[0]


def test_verified_participation_resolves_only_the_appearance_order():
    first = pd.Timestamp("2026-10-16")
    second = pd.Timestamp("2026-10-17")
    last = pd.Timestamp("2026-10-23")
    matches = pd.DataFrame([
        dict(match_id="heathmont", start=first, end=last, contribution=1, match_date_label="23 Oct 2026"),
        dict(match_id="other", start=second, end=second, contribution=1, match_date_label="17 Oct 2026"),
    ])
    assert resolve_crossing(matches, 2, 49, 50)[0] is None
    matches["first_verified_appearance"] = [first, second]
    selected, note = resolve_crossing(matches, 2, 49, 50)
    assert note == "Verified exact match"
    assert selected.match_id == "heathmont" and selected.match_date_label == "23 Oct 2026"
    assert matches.iloc[0].end == last
