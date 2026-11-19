from types import SimpleNamespace

import pandas as pd

from src.ui import layout


def test_selected_season_frames_are_versioned_and_club_scoped(monkeypatch):
    club = "glen-waverley-hawks"
    calls = []

    def load(season_id, team, version):
        calls.append((season_id, team["id"], version))
        return {"batting": pd.DataFrame({"runs": [len(calls)]})}

    monkeypatch.setattr(layout, "get_active_club_id", lambda: club)
    monkeypatch.setattr(layout, "load_local_single_team_frames", load)
    monkeypatch.setattr(layout, "add_season_overview_detail_metrics", lambda frames, *_: frames)
    layout.prepared_season_frames.clear()
    season = {"id": "2025"}
    team = {"id": "first"}
    args = (season, team, [team], False)
    first = layout.prepared_season_frames(club, (1, "public-v1"), *args)
    first["batting"]["runs"] = [99]
    assert layout.prepared_season_frames(club, (1, "public-v1"), *args)["batting"].runs.item() == 1
    assert layout.prepared_season_frames(club, (1, "public-v2"), *args)["batting"].runs.item() == 2
    club = "fvcc"
    assert layout.prepared_season_frames(club, (1, "public-v2"), *args)["batting"].runs.item() == 3
    assert len(calls) == 3
    layout.prepared_season_frames.clear()


def test_season_detail_html_reuses_only_same_scope_and_discipline(monkeypatch):
    counts = []

    def html(frame, discipline, table_id):
        counts.append(discipline)
        return f"{table_id}:{frame.runs.item()}"

    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")
    monkeypatch.setattr(layout, "sort_batting_leaders", lambda frame: frame)
    monkeypatch.setattr(layout, "sort_bowling_leaders", lambda frame: frame)
    monkeypatch.setattr(layout, "build_full_stats_frame", lambda frame, *_: frame)
    monkeypatch.setattr(layout, "season_overview_detail_table_html", html)
    layout.prepared_season_table.clear()
    runs = pd.DataFrame({"runs": [17]})
    whole = ("fvcc", "2026", "__all_teams__")
    team = ("fvcc", "2026", "first")
    assert layout.prepared_season_table(whole, (1, "v1"), "batting", _frame=runs) == "season-detail-batting-club:17"
    layout.prepared_season_table(whole, (1, "v1"), "batting", _frame=runs)
    layout.prepared_season_table(team, (1, "v1"), "batting", _frame=runs)
    layout.prepared_season_table(team, (1, "v1"), "bowling", _frame=runs)
    assert counts == ["batting", "batting", "bowling"]
    layout.prepared_season_table.clear()


def test_season_scope_binds_actual_table_and_escapes_labels(monkeypatch):
    frames = []
    monkeypatch.setattr(layout, "components", SimpleNamespace(html=lambda doc, **kwargs: frames.append(doc)))
    scope = ("fvcc", "season-1", "team-2", "Summer 2025/26", 'First & "Second"', "run-3")
    layout.emit_season_detail_table("<table><tbody><tr><td>17</td></tr></tbody></table>", "bowling", scope)
    assert 'data-season-table="bowling"' in frames[0]
    assert 'data-team-id="team-2"' in frames[0]
    assert 'data-team-label="First &amp; &quot;Second&quot;"' in frames[0]
    assert 'data-run="run-3"' in frames[0]
    assert "<td>17</td>" in frames[0]


def test_season_table_link_cannot_expose_generic_or_nonpublic_player(monkeypatch):
    from src.data import grdcc_player_privacy

    monkeypatch.setattr(layout, "get_active_club_id", lambda: "georges-river-district")
    monkeypatch.setattr(grdcc_player_privacy, "resolve_current_privacy",
                        lambda *, canonical_player_id, club_id: ("private", "") if canonical_player_id == "withheld" else ("", ""))
    monkeypatch.setattr(layout, "request_public_lookup",
                        lambda _: (frozenset({"public-person"}), {"verified public": "public-person"}))
    for identity in ("unverified", "withheld"):
        label = layout.season_detail_player_link_cell(layout.player_profile_url(identity, "Private player"))
        assert label == "Private player"
    withheld = layout.season_detail_player_link_cell(layout.player_profile_url("withheld", "Earlier Name"))
    assert withheld == "Private player"
    public = layout.season_detail_player_link_cell(layout.player_profile_url("public-person", "Verified Public"))
    assert 'data-season-detail-link="1"' in public and 'player_id=public-person' in public
