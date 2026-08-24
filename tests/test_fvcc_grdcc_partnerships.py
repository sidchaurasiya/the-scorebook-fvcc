from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.data.partnerships import build_governed_club_partnerships
from src.ui import layout


ROOT = Path(__file__).resolve().parents[1]


def source_scope(
    root: Path,
    *,
    player_1_name: str = "Public One",
    player_2_name: str = "Public Two",
    include_player_2_identity: bool = True,
    duplicate_delivery: bool = False,
) -> Path:
    root.mkdir(parents=True)
    pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "is_ball_by_ball": True,
                "source_team_ids": "club-team",
                "season": "Summer 2025/26",
                "first_match_day": "2026-01-01",
                "grade_name": "A Grade",
                "home_team_id": "club-team",
                "home_team_name": "Club Team",
                "away_team_id": "opponent",
                "away_team_name": "Opposition",
            }
        ]
    ).to_csv(root / "all_matches.csv", index=False)
    pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "innings_number": 1,
                "innings_order": 1,
                "runs_scored": 10,
            }
        ]
    ).to_csv(root / "all_match_innings.csv", index=False)
    ball = {
        "match_id": "match-1",
        "innings_id": "innings-1",
        "innings_number": 1,
        "innings_order": 1,
        "batting_team_id": "club-team",
        "bowling_team_id": "opponent",
        "ball_event_id": "event-1",
        "over_number": 0,
        "ball_number": 1,
        "striker_participant_id": "player-1",
        "striker_short_name": player_1_name,
        "non_striker_participant_id": "player-2",
        "non_striker_short_name": player_2_name,
        "bowler_participant_id": "bowler",
        "runs_bat": 9,
        "wides": 0,
        "no_balls": 0,
        "leg_byes": 0,
        "byes": 0,
        "penalty_runs": 0,
        "total_runs": 9,
        "is_legal_delivery": True,
        "is_wicket": False,
        "dismissal_type": "",
        "dismissed_participant_id": "",
        "progress_runs": 10,
        "progress_wickets": 0,
        "progress_score": "0-10",
    }
    balls = [ball]
    if duplicate_delivery:
        duplicate = dict(ball)
        duplicate["ball_event_id"] = "provider-duplicate"
        balls.append(duplicate)
    pd.DataFrame(balls).to_csv(root / "all_ball_by_ball.csv", index=False)
    batting = [
        {
            "match_id": "match-1",
            "innings_id": "innings-1",
            "team_id": "club-team",
            "participant_id": "player-1",
            "player_name": player_1_name,
            "bat_instance": 1,
        }
    ]
    if include_player_2_identity:
        batting.append(
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "team_id": "club-team",
                "participant_id": "player-2",
                "player_name": player_2_name,
                "bat_instance": 1,
            }
        )
    pd.DataFrame(batting).to_csv(root / "all_scorecard_batting.csv", index=False)
    return root


def test_public_public_partnership_and_score_difference_are_published(tmp_path) -> None:
    result = build_governed_club_partnerships(
        club_id="fvcc",
        match_centre_root=source_scope(tmp_path / "source"),
    )
    assert len(result.events) == 1
    event = result.events.iloc[0]
    assert event["batter_1_public_name"] == "Public One"
    assert event["batter_2_public_name"] == "Public Two"
    assert event["partnership_runs"] == 9
    assert event["balls_faced"] == 1
    assert event["reconciliation_status"] == "SCORE_DIFFERENCE_ACCEPTED"
    assert event["reconciliation_difference"] == -1


def test_public_private_partnership_is_retained_without_identity_leak(tmp_path) -> None:
    result = build_governed_club_partnerships(
        club_id="fvcc",
        match_centre_root=source_scope(tmp_path / "source", player_2_name="********"),
    )
    event = result.events.iloc[0]
    assert event["privacy_status"] == "PUBLIC_PRIVATE"
    assert event["batter_2_public_name"] == "Private player"
    assert event["batter_2"] == ""
    assert "*" not in event.astype(str).str.cat(sep="|")


def test_private_private_partnership_is_excluded(tmp_path) -> None:
    result = build_governed_club_partnerships(
        club_id="fvcc",
        match_centre_root=source_scope(
            tmp_path / "source",
            player_1_name="********",
            player_2_name="********",
        ),
    )
    assert result.events.empty
    assert result.rejected.iloc[0]["privacy_status"] == "PRIVATE_PRIVATE"


def test_unresolved_pair_is_excluded(tmp_path) -> None:
    result = build_governed_club_partnerships(
        club_id="fvcc",
        match_centre_root=source_scope(tmp_path / "source", include_player_2_identity=False),
    )
    assert result.events.empty
    assert len(result.identity_audit) == 1


def test_semantic_duplicate_delivery_is_removed(tmp_path) -> None:
    result = build_governed_club_partnerships(
        club_id="fvcc",
        match_centre_root=source_scope(tmp_path / "source", duplicate_delivery=True),
    )
    assert len(result.events) == 1
    assert result.coverage.iloc[0]["semantic_duplicate_delivery_rows_removed"] == 1


def test_missing_source_fails_closed(tmp_path) -> None:
    with pytest.raises(FileNotFoundError):
        build_governed_club_partnerships(club_id="fvcc", match_centre_root=tmp_path / "missing")


def test_rebuild_is_deterministic(tmp_path) -> None:
    source = source_scope(tmp_path / "source")
    first = build_governed_club_partnerships(club_id="fvcc", match_centre_root=source)
    second = build_governed_club_partnerships(club_id="fvcc", match_centre_root=source)
    assert_frame_equal(first.events, second.events)
    assert_frame_equal(first.coverage, second.coverage)


def test_verified_partnership_ui_row_protects_private_player() -> None:
    row = pd.Series(
        {
            "batter_1": "public-id",
            "batter_2": "",
            "batter_1_public_name": "Public One",
            "batter_2_public_name": "Private player",
            "partnership_runs": 50,
            "balls_faced": 60,
            "season": "Summer 2025/26",
            "grade": "A Grade",
            "opponent": "Opposition",
            "innings": 1,
            "match_id": "match-1",
        }
    )
    rendered = layout.verified_partnership_row_html(row)
    assert "Public One" in rendered
    assert "Private player" in rendered
    assert "********" not in rendered


@pytest.fixture(scope="module")
def current_club_builds():
    return {
        "fvcc": build_governed_club_partnerships(
            club_id="fvcc",
            match_centre_root=ROOT / "data" / "processed" / "match_centre",
        ),
        "grdcc": build_governed_club_partnerships(
            club_id="georges-river-district",
            match_centre_root=ROOT / "data" / "processed" / "match_centre" / "georges-river-district",
        ),
    }


def test_current_fvcc_and_grdcc_publication_counts(current_club_builds) -> None:
    fvcc = current_club_builds["fvcc"]
    grdcc = current_club_builds["grdcc"]
    assert len(fvcc.events) == 887
    assert fvcc.events["privacy_status"].value_counts().to_dict() == {
        "PUBLIC_PUBLIC": 872,
        "PUBLIC_PRIVATE": 15,
    }
    assert len(grdcc.events) == 2463
    assert grdcc.events["privacy_status"].value_counts().to_dict() == {
        "PUBLIC_PUBLIC": 2310,
        "PUBLIC_PRIVATE": 153,
    }
    assert len(grdcc.rejected) == 44
