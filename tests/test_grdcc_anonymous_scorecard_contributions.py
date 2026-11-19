from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from src.data.grdcc_anonymous_scorecard_contributions import (
    ANONYMOUS_FASTEST_COLUMNS,
    ANONYMOUS_SCORECARD_COLUMNS,
    PRIVATE_PLAYER_LABEL,
    build_anonymous_fastest_milestones,
    build_anonymous_scorecard_contributions,
    read_public_anonymous_fastest_milestones,
    read_public_anonymous_scorecard_contributions,
)
from match_centre_source_snapshot import weekly_source_manifest


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.strip().encode("utf-8")).hexdigest()


def _source_frames():
    token = "fixture-reused-source-token"
    other = "unrelated-source-id"
    matches = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "status": "COMPLETED",
                "season": "Summer 2025/26",
                "first_match_day": "2026-03-01",
                "grade_name": "A Grade",
            },
            {
                "match_id": "match-abandoned",
                "status": "ABANDONED",
                "season": "Summer 2025/26",
                "first_match_day": "2026-03-02",
                "grade_name": "A Grade",
            },
        ]
    )
    innings = pd.DataFrame(
        [
            {"match_id": "match-1", "innings_id": "innings-1", "innings_number": "1"},
            {"match_id": "match-abandoned", "innings_id": "innings-abandoned", "innings_number": "1"},
        ]
    )
    batting = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "team_id": "grdcc-team",
                "participant_id": token,
                "player_name": "Name from source A",
                "bat_order": "2",
                "bat_instance": "1",
                "runs_scored": "24",
                "balls_faced": "18",
                "fours_scored": "3",
                "sixes_scored": "1",
                "dismissal_type": "Caught",
            },
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "team_id": "grdcc-team",
                "participant_id": token,
                "player_name": "Name from source B",
                "bat_order": "7",
                "bat_instance": "1",
                "runs_scored": "10",
                "balls_faced": "7",
                "fours_scored": "1",
                "sixes_scored": "0",
                "dismissal_type": "Bowled",
            },
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "team_id": "opponent-team",
                "participant_id": token,
                "player_name": "Opponent name from source",
                "bat_order": "3",
                "bat_instance": "1",
                "runs_scored": "99",
                "balls_faced": "70",
                "fours_scored": "8",
                "sixes_scored": "2",
                "dismissal_type": "Caught",
            },
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "team_id": "grdcc-team",
                "participant_id": other,
                "player_name": "Unrelated public source name",
                "bat_order": "4",
                "bat_instance": "1",
                "runs_scored": "45",
                "balls_faced": "31",
                "fours_scored": "5",
                "sixes_scored": "1",
                "dismissal_type": "Caught",
            },
            {
                "match_id": "match-abandoned",
                "innings_id": "innings-abandoned",
                "team_id": "grdcc-team",
                "participant_id": token,
                "player_name": "Abandoned match name",
                "bat_order": "1",
                "bat_instance": "1",
                "runs_scored": "15",
                "balls_faced": "13",
                "fours_scored": "1",
                "sixes_scored": "0",
                "dismissal_type": "Not out",
            },
        ]
    )
    bowling = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "team_id": "grdcc-team",
                "participant_id": token,
                "player_name": "Bowling name from source",
                "bowl_order": "4",
                "overs_bowled": "3.2",
                "maidens_bowled": "0",
                "runs_conceded": "19",
                "wickets_taken": "2",
                "wides": "1",
                "no_balls": "0",
                "economy": "5.7",
            }
        ]
    )
    fielding = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "team_id": "grdcc-team",
                "participant_id": token,
                "player_name": "Fielding name from source",
                "catches": "1",
                "run_outs": "0",
                "stumpings": "0",
            }
        ]
    )
    teams = pd.DataFrame(
        [
            {"team_id": "grdcc-team", "team_name": "Georges River XI"},
        ]
    )
    return token, other, matches, innings, batting, bowling, fielding, teams


def test_anonymous_scorecard_builder_keeps_unique_grdcc_events_and_strips_identity() -> None:
    token, _, matches, innings, batting, bowling, fielding, teams = _source_frames()
    output = build_anonymous_scorecard_contributions(
        matches=matches,
        innings=innings,
        batting=batting,
        bowling=bowling,
        fielding=fielding,
        teams=teams,
        ambiguous_participant_fingerprints={_fingerprint(token)},
    )

    assert len(output) == 4
    assert output["discipline"].value_counts().to_dict() == {
        "batting": 2,
        "bowling": 1,
        "fielding": 1,
    }
    assert output["anonymous_event_key"].is_unique
    assert output["display_player_name"].eq(PRIVATE_PLAYER_LABEL).all()
    assert output.loc[output["runs_scored"].str.strip().ne(""), "runs_scored"].astype(int).sum() == 34
    assert output.loc[output["wickets_taken"].str.strip().ne(""), "wickets_taken"].astype(int).sum() == 2
    assert output.loc[output["catches"].str.strip().ne(""), "catches"].astype(int).sum() == 1
    assert output["team_name"].eq("Georges River XI").all()
    assert not ({"player_id", "participant_id", "canonical_player_id", "match_id", "innings_id"} & set(output.columns))
    serialized = output.to_csv(index=False)
    assert token not in serialized
    assert "Name from source A" not in serialized
    assert "Name from source B" not in serialized
    assert "Opponent name from source" not in serialized
    assert "Unrelated public source name" not in serialized


def test_delivery_metrics_are_event_scoped_and_not_merged_for_reused_tokens() -> None:
    token, _, matches, innings, batting, bowling, fielding, teams = _source_frames()
    ball_events = []
    cumulative_runs = 0
    for number in range(1, 50):
        batter_runs = 1 if number <= 47 else 3 if number == 48 else 5
        cumulative_runs += batter_runs
        ball_events.append(
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "batting_team_id": "grdcc-team",
                "bowling_team_id": "opponent-team",
                "ball_event_id": f"unique-ball-{number}",
                "striker_participant_id": token,
                "striker_runs_scored": str(cumulative_runs),
                "striker_balls_faced": str(number),
                "runs_bat": str(batter_runs),
                "wides": "0",
                "total_runs": str(batter_runs),
                "is_legal_delivery": "True",
            }
        )

    merged_context = build_anonymous_scorecard_contributions(
        matches=matches,
        innings=innings,
        batting=batting,
        bowling=bowling,
        fielding=fielding,
        teams=teams,
        ambiguous_participant_fingerprints={_fingerprint(token)},
        ball_events=pd.DataFrame(ball_events),
    )
    assert len(merged_context) == 4
    assert merged_context["bbb_source"].fillna("").eq("").all()

    unique_batting = batting.iloc[[0]].copy()
    unique_batting.loc[:, "runs_scored"] = "55"
    unique_batting.loc[:, "balls_faced"] = "49"
    empty_bowling = pd.DataFrame(columns=["participant_id"])
    empty_fielding = pd.DataFrame(columns=["participant_id"])
    event_scoped = build_anonymous_scorecard_contributions(
        matches=matches,
        innings=innings,
        batting=unique_batting,
        bowling=empty_bowling,
        fielding=empty_fielding,
        teams=teams,
        ambiguous_participant_fingerprints={_fingerprint(token)},
        ball_events=pd.DataFrame(ball_events),
    )
    row = event_scoped.iloc[0]
    assert row["bbb_source"] == "verified_ball_by_ball"
    assert row["bbb_batting_runs"] == "55"
    assert row["bbb_batting_balls_faced"] == "49"
    assert row["bbb_batting_strike_rate"] == "112.2"


def test_anonymous_fastest_builder_requires_verified_delivery_threshold_and_keeps_no_link() -> None:
    token, _, matches, _, batting, _, _, teams = _source_frames()
    fastest_batting = batting.iloc[[0]].copy()
    fastest_batting.loc[:, "runs_scored"] = "55"
    fastest_batting.loc[:, "balls_faced"] = "49"
    balls = []
    cumulative_runs = 0
    cumulative_balls = 0
    for number in range(1, 50):
        if number <= 47:
            batter_runs = 1
        elif number == 48:
            batter_runs = 3
        else:
            batter_runs = 5
        cumulative_runs += batter_runs
        cumulative_balls += 1
        balls.append(
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "ball_event_id": f"delivery-{number}",
                "over_number": str((number - 1) // 6),
                "ball_number": str((number - 1) % 6 + 1),
                "striker_participant_id": token,
                "striker_runs_scored": str(cumulative_runs),
                "striker_balls_faced": str(cumulative_balls),
            }
        )
    milestones = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "participant_id": token,
                "final_runs": "55",
                "balls_to_50": "48.0",
                "balls_to_100": "",
                "source_ball_by_ball_available": "True",
            },
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "participant_id": token,
                "final_runs": "34",
                "balls_to_50": "",
                "balls_to_100": "",
                "source_ball_by_ball_available": "True",
            },
        ]
    )
    output = build_anonymous_fastest_milestones(
        milestones=milestones,
        batting=fastest_batting,
        ball_events=pd.DataFrame(balls),
        matches=matches,
        teams=teams,
        ambiguous_participant_fingerprints={_fingerprint(token)},
    )

    assert len(output) == 1
    row = output.iloc[0]
    assert row["player_name"] == PRIVATE_PLAYER_LABEL
    assert row["canonical_player_name"] == PRIVATE_PLAYER_LABEL
    assert row["final_runs"] == "55"
    assert row["balls_to_50"] == "48"
    assert row["source_ball_by_ball_available"] == "True"
    assert row["anonymous_event"] == "True"
    assert row["anonymous_event_key"]
    assert not ({"player_id", "participant_id", "canonical_player_id", "match_id", "innings_id"} & set(output.columns))
    assert token not in output.to_csv(index=False)


def test_public_anonymous_loaders_are_grdcc_scoped_and_fail_closed(tmp_path) -> None:
    token, _, matches, innings, batting, bowling, fielding, teams = _source_frames()
    scorecards = build_anonymous_scorecard_contributions(
        matches=matches,
        innings=innings,
        batting=batting,
        bowling=bowling,
        fielding=fielding,
        teams=teams,
        ambiguous_participant_fingerprints={_fingerprint(token)},
    )
    scorecard_path = tmp_path / "anonymous_scorecard_contributions.csv"
    scorecards.to_csv(scorecard_path, index=False)
    assert len(read_public_anonymous_scorecard_contributions(scorecard_path, "georges-river-district")) == 4
    assert read_public_anonymous_scorecard_contributions(scorecard_path, "glen-waverley-hawks").empty
    assert read_public_anonymous_scorecard_contributions(scorecard_path, "fvcc").empty

    unsafe = scorecards.copy()
    unsafe["participant_id"] = ""
    unsafe.loc[0, "participant_id"] = token
    unsafe_path = tmp_path / "unsafe_anonymous_scorecard_contributions.csv"
    unsafe.to_csv(unsafe_path, index=False)
    assert read_public_anonymous_scorecard_contributions(unsafe_path, "georges-river-district").empty


def test_public_anonymous_fastest_loader_requires_generic_verified_rows(tmp_path) -> None:
    token, _, matches, _, batting, _, _, teams = _source_frames()
    fastest_batting = batting.iloc[[0]].copy()
    fastest_batting.loc[:, "runs_scored"] = "55"
    fastest_batting.loc[:, "balls_faced"] = "49"
    balls = []
    for number in range(1, 50):
        runs = number if number < 48 else (50 if number == 48 else 55)
        balls.append(
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "ball_event_id": f"ball-{number}",
                "over_number": str((number - 1) // 6),
                "ball_number": str((number - 1) % 6 + 1),
                "striker_participant_id": token,
                "striker_runs_scored": str(runs),
                "striker_balls_faced": str(number),
            }
        )
    milestones = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "participant_id": token,
                "final_runs": "55",
                "balls_to_50": "48",
                "balls_to_100": "",
                "source_ball_by_ball_available": "True",
            }
        ]
    )
    events = build_anonymous_fastest_milestones(
        milestones=milestones,
        batting=fastest_batting,
        ball_events=pd.DataFrame(balls),
        matches=matches,
        teams=teams,
        ambiguous_participant_fingerprints={_fingerprint(token)},
    )
    path = tmp_path / "anonymous_fastest_milestones.csv"
    events.to_csv(path, index=False)
    assert len(read_public_anonymous_fastest_milestones(path, "georges-river-district")) == 1
    assert read_public_anonymous_fastest_milestones(path, "fvcc").empty

    unsafe = events.copy()
    unsafe.loc[0, "match_id"] = "private-match-id"
    unsafe.to_csv(path, index=False)
    assert read_public_anonymous_fastest_milestones(path, "georges-river-district").empty


def test_hall_of_fame_v2_hero_copy_is_club_neutral(monkeypatch) -> None:
    from src.ui import layout

    rendered = []
    monkeypatch.setattr(layout.st, "markdown", lambda value, **_kwargs: rendered.append(value))
    monkeypatch.setattr(layout, "configured_club_label_html", lambda _class_name="club-label": "<div>GRDCC</div>")
    monkeypatch.setattr(layout, "hall_of_fame_v2_verified_fastest_count", lambda: 1)

    layout.render_hall_of_fame_v2_hero(
        {"kpis": {"total_seasons": 72, "total_matches": 3605, "total_players": 1703}}
    )

    output = "\n".join(rendered)
    assert "GRDCC" in output
    assert "A club record book for legends, premierships and iconic performances." in output
    assert "FVCC legends" not in output


def test_hall_of_fame_loads_verified_anonymous_fastest_event_without_profile_or_scorecard_link(monkeypatch) -> None:
    from src.ui import layout

    fastest_path = Path(
        "clubs/georges-river-district/data/processed/hall_of_fame/fastest_batting_milestones.csv"
    ).resolve()
    anonymous_path = Path(
        "clubs/georges-river-district/data/processed/hall_of_fame/anonymous_fastest_milestones.csv"
    ).resolve()
    safe_source_rows = read_public_anonymous_fastest_milestones(
        anonymous_path,
        "georges-river-district",
    )
    assert len(safe_source_rows) == 1
    assert not ({"player_id", "participant_id", "canonical_player_id", "match_id", "innings_id"} & set(safe_source_rows.columns))
    monkeypatch.setattr(layout, "HALL_OF_FAME_FASTEST_BATTING_MILESTONES_PATH", fastest_path)
    monkeypatch.setattr(layout, "HALL_OF_FAME_ANONYMOUS_FASTEST_MILESTONES_PATH", anonymous_path)
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "georges-river-district")
    assert layout.match_centre_milestones_mtime() == max(fastest_path.stat().st_mtime, anonymous_path.stat().st_mtime)
    assert str(anonymous_path.relative_to(layout.APP_ROOT)) in {path for path, _ in layout.player_dna_data_signature()}
    records = layout.load_batting_milestone_records(
        "georges-river-district",
        str(fastest_path),
        fastest_path.stat().st_mtime,
        (),
    )
    anonymous = records.loc[
        records.get("anonymous_event", pd.Series("", index=records.index)).astype(str).str.casefold().eq("true")
    ]
    assert len(anonymous) == 1
    row = anonymous.iloc[0]
    assert row["player_name"] == PRIVATE_PLAYER_LABEL
    assert row["canonical_player_name"] == PRIVATE_PLAYER_LABEL
    assert row["final_runs"] == 55
    assert row["balls_to_50"] == 48
    for column in ("player_id", "canonical_player_id", "participant_id", "match_id", "innings_id"):
        assert pd.isna(row.get(column)) or not str(row.get(column)).strip()
    player_id = layout.player_id_from_row(row)
    assert player_id == ""
    assert layout.player_profile_link_html(player_id, PRIVATE_PLAYER_LABEL) == PRIVATE_PLAYER_LABEL
    assert layout.scorecard_link_html(row.get("match_id"), page_slug="hall-of-fame", section_name="fastest_batting_milestones") == ""
    for club_id in ("glen-waverley-hawks", "fvcc"):
        club_fastest = Path(f"clubs/{'glen-waverley-hawks' if club_id.startswith('glen') else 'fvcc'}/data/processed/hall_of_fame/fastest_batting_milestones.csv")
        other = layout.load_batting_milestone_records(club_id, str(club_fastest), None, ())
        assert "anonymous_event" not in other or not other["anonymous_event"].fillna("").astype(str).str.casefold().eq("true").any()

    def reject_profile_id_generation(_rows):
        raise AssertionError("Anonymous milestones must not enter canonical-player generation")

    monkeypatch.setattr(layout, "add_missing_canonical_player_ids", reject_profile_id_generation)
    ranked_html = layout.hall_of_fame_v2_fastest_list_html(anonymous, "Fastest 50s", "balls_to_50")
    assert "Private player" not in ranked_html
    assert "Additional anonymous verified milestones" not in ranked_html


def test_scorecard_loader_is_club_scoped_and_privacy_signature_invalidates_cache(monkeypatch) -> None:
    from src.data import grdcc_player_privacy
    from src.ui import layout

    state = {"signature": ("snapshot-a",)}
    monkeypatch.setattr(
        grdcc_player_privacy,
        "privacy_snapshot_signature",
        lambda club_id=None: state["signature"],
    )
    first = layout.anonymous_scorecard_contributions_signature("georges-river-district")
    assert first[2] == ("snapshot-a",)
    state["signature"] = ("snapshot-b",)
    second = layout.anonymous_scorecard_contributions_signature("georges-river-district")
    assert second[2] == ("snapshot-b",)
    assert first != second
    assert layout.anonymous_scorecard_contributions_signature("glen-waverley-hawks") == ()

    events = layout.load_anonymous_scorecard_contributions(
        "georges-river-district",
        layout.anonymous_scorecard_contributions_signature("georges-river-district"),
    )
    assert len(events) == weekly_source_manifest()["anonymous_scorecard_events"] == 56
    assert events["display_player_name"].eq(PRIVATE_PLAYER_LABEL).all()
    assert layout.load_anonymous_scorecard_contributions("fvcc", ()).empty


def test_scorecard_renderer_preserves_melbourne_dates_and_undated_contributions(monkeypatch) -> None:
    from src.ui import layout

    rows = pd.DataFrame(
        [
            {
                "match_date": "2026-09-26T08:15:00.0000000+10:00",
                "grade_name": "Fifth Grade",
                "discipline": "batting",
                "runs_scored": 15,
                "balls_faced": 22,
            },
            {
                "match_date": "2026-10-04T08:15:00.0000000+11:00",
                "grade_name": "Fourth Grade",
                "discipline": "bowling",
                "overs_bowled": "3.2",
                "wickets_taken": 2,
                "runs_conceded": 19,
            },
            {
                "match_date": pd.NA,
                "grade_name": "Third Grade",
                "discipline": "fielding",
                "catches": 1,
            },
            {
                "match_date": "invalid-date",
                "grade_name": "Second Grade",
                "discipline": "batting",
                "runs_scored": 6,
                "balls_faced": 10,
            },
        ]
    ).assign(
        season="Summer 2026/27",
        team_name="GRDCC",
        innings_number="1",
        display_player_name=PRIVATE_PLAYER_LABEL,
    )
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "georges-river-district")
    monkeypatch.setattr(layout, "anonymous_scorecard_contributions_signature", lambda _club_id: ())
    monkeypatch.setattr(layout, "load_anonymous_scorecard_contributions", lambda _club_id, _signature: rows)
    markdown = []
    monkeypatch.setattr(layout.st, "markdown", lambda text, **_kwargs: markdown.append(text))
    monkeypatch.setattr(layout.st, "caption", lambda _text: None)

    layout.render_anonymous_scorecard_contributions({"season": {"name": "Summer 2026/27"}, "is_all_teams": True})

    cards = markdown[-1]
    assert cards.count('role="listitem"') == cards.count(PRIVATE_PLAYER_LABEL) == len(rows)
    assert "26 Sep 2026 · Fifth Grade · GRDCC · Innings 1" in cards
    assert "04 Oct 2026 · Fourth Grade · GRDCC · Innings 1" in cards
    assert 'meta">Third Grade · GRDCC · Innings 1' in cards
    assert 'meta">Second Grade · GRDCC · Innings 1' in cards
    assert "15 runs · 22 balls" in cards
    assert "3.2 overs · 2 wickets · 19 runs" in cards
    assert "1 catches · 0 run outs · 0 stumpings" in cards
    assert "6 runs · 10 balls" in cards
    assert "invalid-date" not in cards
    assert "<a " not in cards and "href=" not in cards
