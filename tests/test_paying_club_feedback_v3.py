from pathlib import Path

import pandas as pd
import pytest

from src.ui import layout


@pytest.mark.parametrize("club,labels", [
    ("georges-river-district", ["Matches", "Runs", "Wickets", "Catches"]),
    ("glen-waverley-hawks", ["Matches", "Runs", "Wickets", "Catches"]),
    ("fvcc", ["Runs", "Matches", "Wickets", "Catches"]),
])
def test_primary_card_order_preserves_all_figures(monkeypatch, club, labels):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: club)
    career = pd.Series({"Player": "Test", "Matches": 21.5, "Runs": 3000, "Wickets": 59, "Catches": 139})
    markup = layout.grdcc_primary_card_markup(career)
    offsets = [markup.index(f"<dt>{label}</dt>") for label in labels]
    assert offsets == sorted(offsets)
    for figure in ("21.5", "3,000", "59", "139"):
        assert f"<dd>{figure}</dd>" in markup
    assert "captain-note" not in markup
    enriched = layout.grdcc_primary_card_markup(career, insight_markup='<p class="profile-insight">captain-note</p>')
    assert enriched.index("captain-note") < enriched.index("</section>")


def test_recent_form_separates_only_verified_season_changes(tmp_path):
    path = tmp_path / "match-seasons.csv"
    path.write_text("match_id,season\na,2026\nb,2026\nc,2025\nc,2024\nd,2025\n")
    seasons = layout.recent_form_match_seasons(str(path), path.stat().st_mtime_ns)
    assert seasons == {"a": "2026", "b": "2026", "d": "2025"}
    labels = [{"label": value, "season": seasons.get(match_id, "")}
              for match_id, value in zip("abcd", ("15*", "12", "1", "29"), strict=True)]
    result = layout.recent_form_line_html("Batting scores", "", labels, "bat", "No scores")
    assert result.count("recent-form-season") == 2
    fragments = ["2026:", "15*</span>", "12</span>", "1</span>", "2025:", "29</span>"]
    assert [result.index(f) for f in fragments] == sorted(result.index(f) for f in fragments)


@pytest.mark.parametrize("club", ["georges-river-district", "glen-waverley-hawks", "fvcc"])
def test_achieved_card_keeps_source_link_and_governed_totals(monkeypatch, club):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: club)
    monkeypatch.setattr(layout, "player_profile_link_html", lambda *_: "Player")
    monkeypatch.setattr(layout, "scorecard_link_html", lambda id_, **_: f"<a href='/match/{id_}'>View scorecard</a>")
    row = pd.Series({"Player": "Player", "Category": "Matches", "Season": "Summer 2026/27",
                     "Current Total": 200.5, "Milestone": "200 matches reached", "Unit": "matches",
                     "Match Evidence": "Verified exact match", "match_id": "test-match",
                     "match_date_label": "30 Oct 2026", "round": "R2", "opponent": "Opponent",
                     "match_performance": "Appearance weight 1 · 19 runs from 60 balls"})
    markup = layout.achievement_card_html(row)
    assert (row["match_performance"] in markup) == (club == "fvcc")
    for fragment in ("200 matches reached", "200.5 matches", "Summer 2026/27",
                     "30 Oct 2026 - R2: vs Opponent", "/match/test-match"):
        assert fragment in markup
    row["Match Evidence"] = "Source totals do not reconcile to the approved season contribution"
    unverified = layout.achievement_card_html(row)
    assert ("Exact match unavailable" in unverified) == (club == "fvcc")
    assert "/match/test-match" not in unverified
    assert "Summer 2026/27" in unverified


def test_captain_breakdown_rejects_a_same_name_from_another_canonical_record():
    rows = pd.DataFrame([
        {"canonical_player_id": "wrong", "canonical_player_name": "A Smith", "runs": 10},
        {"canonical_player_id": "right", "canonical_player_name": "A Smith", "runs": 18},
    ])
    profile = {"player_info": {"canonical_player_id": "right", "canonical_player_name": "A Smith"}}
    assert layout.verified_captain_profile_rows(rows, profile, None).runs.tolist() == [18]
    assert layout.verified_captain_profile_rows(rows.iloc[:1], profile, None).empty
    assert layout.verified_captain_profile_rows(rows, None, None).empty


def test_hawks_captain_export_restores_the_owner_approved_split():
    path = (Path(__file__).resolve().parents[1] / "clubs/glen-waverley-hawks/data/processed/"
            "player_profile/performance_breakdown_by_dimension.csv")
    data = pd.read_csv(path, usecols=["dimension", "breakdown_label"])
    captains = data.loc[data.dimension.eq("Captain"), "breakdown_label"]
    assert captains.eq("Harsha Krishna Mendu").sum() == 27
    assert not captains.eq("Aidan Griffin").any()
    assert captains.eq("Reece Anderson").any()


def test_hawks_date_cells_share_grdcc_placement_and_exact_link(monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    fixture = dict(match_id="exact-match", grade="C Grade", grade_slug="c", opponent="Opponent",
                   playing_dates=["2026-10-16", "2026-10-23"], round="R1",
                   scorecard='<a href="/match/exact-match?tab=scorecard">View scorecard</a>')
    rendered = layout.season_round_cards_html([fixture])
    assert 'role="columnheader">Date' in rendered
    assert rendered.count("/match/exact-match?tab=scorecard") == 1
    assert rendered.index("16-10-2026") < rendered.index("23-10-2026") < rendered.index(">R1<")


def test_hawks_batting_table_label_keeps_numerical_display(monkeypatch):
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    assert layout.hof_detail_header_label("Bat SR") == "Bat SR"
    assert "Bat SR" in layout.profile_batting_table_columns("Season")
    assert layout.hof_detail_display_value("Bat SR", 109.223) == "109.22%"
    assert layout.profile_performance_sort_value("Bat SR", 109.223, "Season") == ("109.223", False)
