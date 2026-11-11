from __future__ import annotations

import hashlib
import io
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src.data.partnerships import (
    PUBLIC_PARTNERSHIP_COLUMNS,
    build_ball_partnerships,
    build_governed_club_partnerships,
    build_verified_partnership_record_holders,
)
from src.ui import layout
from match_centre_source_snapshot import (
    cutoff_current_source_root,
    historical_source_root,
    source_manifest,
)


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
    assert_frame_equal(first.records, second.records)
    assert_frame_equal(first.record_selection_audit, second.record_selection_audit)
    assert_frame_equal(first.coverage, second.coverage)


def test_verified_partnership_ui_row_protects_private_player() -> None:
    row = pd.Series(
        {
            "player_1_canonical_id": "public-id",
            "player_2_canonical_id": "",
            "player_1_name": "Public One",
            "player_2_name": "Private player",
            "runs": 50,
            "wicket_number": 1,
            "season": "Summer 2025/26",
            "display_grade_name": "A Grade",
            "opponent": "Opposition",
            "match_id": "match-1",
            "source_classification": "ball_by_ball_calculated",
        }
    )
    rendered = layout.partnership_record_row_html(row)
    assert "Public One" in rendered
    assert "Private player" in rendered
    assert "********" not in rendered
    assert "player_id=Private" not in rendered


def record_event(
    partnership_id: str,
    *,
    wicket: int,
    runs: int,
    balls: int,
    match_date: str,
    reconciliation_status: str = "MATCHED",
) -> dict[str, object]:
    row = {column: "" for column in PUBLIC_PARTNERSHIP_COLUMNS}
    row.update(
        {
            "partnership_id": partnership_id,
            "batter_1": "one",
            "batter_2": "two",
            "batter_1_public_name": "Player One",
            "batter_2_public_name": "Player Two",
            "partnership_runs": runs,
            "balls_faced": balls,
            "wicket_number": wicket,
            "match_id": f"match-{partnership_id}",
            "innings_id": f"innings-{partnership_id}",
            "match_date": match_date,
            "privacy_status": "PUBLIC_PUBLIC",
            "reconciliation_status": reconciliation_status,
        }
    )
    return row


def test_record_selection_uses_maximum_and_never_recent_zero() -> None:
    events = pd.DataFrame(
        [
            record_event("recent-zero", wicket=1, runs=0, balls=1, match_date="2026-01-01"),
            record_event("older-record", wicket=1, runs=150, balls=180, match_date="2025-01-01"),
        ]
    )
    records, audit = build_verified_partnership_record_holders(events)
    assert records.iloc[0]["partnership_id"] == "older-record"
    assert records.iloc[0]["partnership_runs"] == 150
    assert audit.iloc[0]["maximum_runs"] == 150


def test_record_ties_use_balls_then_earlier_date_and_stable_ids() -> None:
    events = pd.DataFrame(
        [
            record_event("later", wicket=2, runs=100, balls=80, match_date="2025-02-01"),
            record_event("earlier", wicket=2, runs=100, balls=80, match_date="2025-01-01"),
            record_event("fewer-balls", wicket=2, runs=100, balls=70, match_date="2024-01-01"),
        ]
    ).sample(frac=1, random_state=7)
    records, _audit = build_verified_partnership_record_holders(events)
    assert records.iloc[0]["partnership_id"] == "earlier"


def test_both_reconciliation_statuses_are_record_eligible() -> None:
    events = pd.DataFrame(
        [
            record_event("matched", wicket=3, runs=90, balls=80, match_date="2025-01-01"),
            record_event(
                "accepted",
                wicket=3,
                runs=110,
                balls=90,
                match_date="2025-02-01",
                reconciliation_status="SCORE_DIFFERENCE_ACCEPTED",
            ),
        ]
    )
    records, _audit = build_verified_partnership_record_holders(events)
    assert records.iloc[0]["partnership_id"] == "accepted"


def test_record_selection_returns_at_most_one_row_per_wicket() -> None:
    events = pd.DataFrame(
        [
            record_event(f"wicket-{wicket}", wicket=wicket, runs=wicket * 10, balls=wicket * 12, match_date="2025-01-01")
            for wicket in range(1, 11)
        ]
    )
    records, audit = build_verified_partnership_record_holders(events)
    assert records["wicket_number"].tolist() == list(range(1, 11))
    assert not records["wicket_number"].duplicated().any()
    assert audit["validation_status"].eq("PASS").all()


@pytest.fixture(scope="module")
def current_club_builds():
    archive_root = historical_source_root()
    return {
        "fvcc": build_governed_club_partnerships(
            club_id="fvcc",
            match_centre_root=archive_root / "all_available",
        ),
        "grdcc": build_governed_club_partnerships(
            club_id="georges-river-district",
            match_centre_root=archive_root / "georges-river-district" / "all_available",
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
    assert len(grdcc.events) == 2464
    assert grdcc.events["privacy_status"].value_counts().to_dict() == {
        "PUBLIC_PUBLIC": 2320,
        "PUBLIC_PRIVATE": 144,
    }
    assert len(grdcc.rejected) == 43
    assert fvcc.records["wicket_number"].tolist() == list(range(1, 11))
    assert grdcc.records["wicket_number"].tolist() == list(range(1, 11))
    for result in [fvcc, grdcc]:
        for row in result.records.itertuples():
            candidates = result.events[result.events["wicket_number"].eq(row.wicket_number)]
            assert row.partnership_runs == candidates["partnership_runs"].max()
        assert result.record_selection_audit["validation_status"].eq("PASS").all()


def test_source_as_recorded_six_run_partnership_is_retained(current_club_builds):
    result = current_club_builds["grdcc"]
    expected = source_manifest()["source_as_recorded_exception"]
    rows = result.events.loc[
        result.events.partnership_id.map(
            lambda value: hashlib.sha256(str(value).encode("utf-8")).hexdigest()
        ).eq(expected["partnership_id_sha256"])
    ]
    assert len(rows) == 1
    event = rows.iloc[0]
    assert event.partnership_runs == expected["partnership_runs"]
    assert event.balls_faced == expected["legal_balls"]
    assert event.innings_scorecard_total == expected["scorecard_innings_runs"]
    assert event.innings_reconstructed_total == expected["ball_by_ball_reconstructed_runs"]
    assert event.reconciliation_difference == expected["difference"]
    assert event.reconciliation_status == expected["reconciliation_status"]
    assert event.privacy_status == expected["privacy_status"]

    archive_root = historical_source_root() / "georges-river-district" / "all_available"
    balls = pd.read_csv(archive_root / "all_ball_by_ball.csv", low_memory=False)
    selected_balls = balls.loc[
        balls.match_id.astype(str).eq(str(event.match_id))
        & balls.innings_id.astype(str).eq(str(event.innings_id))
    ].copy()
    assert len(selected_balls) == 201
    assert selected_balls.ball_event_id.astype(str).nunique() == 201
    assert not selected_balls.duplicated(["over_number", "ball_number"]).any()
    source_partnerships = build_ball_partnerships(selected_balls)
    source_pair = source_partnerships.loc[
        pd.to_numeric(source_partnerships.partnership_number, errors="coerce").eq(
            pd.to_numeric(pd.Series([event.wicket_number]), errors="coerce").iloc[0]
        )
    ]
    assert len(source_pair) == 1
    pair = source_pair.iloc[0]
    participant_ids = {
        str(pair.batter_1_participant_id).strip(),
        str(pair.batter_2_participant_id).strip(),
    }
    assert "" not in participant_ids and "nan" not in {value.casefold() for value in participant_ids}
    assert len(participant_ids) == 2
    batting = pd.read_csv(archive_root / "all_scorecard_batting.csv", low_memory=False)
    scorecard_ids = set(
        batting.loc[
            batting.match_id.astype(str).eq(str(event.match_id))
            & batting.innings_id.astype(str).eq(str(event.innings_id)),
            "participant_id",
        ].dropna().astype(str)
    )
    assert participant_ids.issubset(scorecard_ids)


def test_current_season_cutoff_partnership_build_is_pinned_and_privacy_safe(tmp_path):
    source_root = cutoff_current_source_root(tmp_path)
    result = build_governed_club_partnerships(
        club_id="georges-river-district",
        match_centre_root=source_root,
    )
    expected = source_manifest()["current_season_scope"]["expected_partnerships"]
    assert len(result.events) == expected["events"]
    assert result.events.privacy_status.value_counts().to_dict() == {
        "PUBLIC_PUBLIC": expected["PUBLIC_PUBLIC"],
        "PUBLIC_PRIVATE": expected["PUBLIC_PRIVATE"],
    }
    assert len(result.rejected) == expected["rejected"]
    assert result.rejected.rejection_reason.value_counts().to_dict() == {
        expected["rejected_reason"]: expected["rejected"]
    }
    assert result.events.match_date.astype(str).le("2026-10-31").all()
    assert not result.events.batter_1_public_name.astype(str).str.contains(r"\*{2,}", regex=True).any()
    assert not result.events.batter_2_public_name.astype(str).str.contains(r"\*{2,}", regex=True).any()
    assert result.records.wicket_number.tolist() == list(range(1, 11))


@pytest.fixture(scope="module")
def current_cutoff_build(tmp_path_factory):
    source_root = cutoff_current_source_root(tmp_path_factory.mktemp("grdcc-source"))
    return build_governed_club_partnerships(
        club_id="georges-river-district",
        match_centre_root=source_root,
    )


def test_full_accepted_cutoff_publication_reconciles_privacy_and_records(
    current_club_builds, current_cutoff_build
):
    historical = current_club_builds["grdcc"].events
    current = current_cutoff_build.events
    combined = pd.concat([historical, current], ignore_index=True)
    assert not combined.partnership_id.astype(str).duplicated().any()
    assert len(combined) == 2703
    assert combined.privacy_status.value_counts().to_dict() == {
        "PUBLIC_PUBLIC": 2558,
        "PUBLIC_PRIVATE": 145,
    }

    baseline_commit = source_manifest()["combined_expected_partnerships"]["baseline_commit"]
    baseline_blob = subprocess.check_output(
        [
            "git",
            "show",
            f"{baseline_commit}:clubs/georges-river-district/data/processed/hall_of_fame/partnerships.csv",
        ],
        cwd=ROOT,
    )
    old = pd.read_csv(io.BytesIO(baseline_blob), dtype=str, low_memory=False).fillna("")
    common = old[["partnership_id", "privacy_status"]].merge(
        combined[["partnership_id", "privacy_status"]],
        on="partnership_id",
        how="inner",
        suffixes=("_old", "_current"),
        validate="one_to_one",
    )
    transitions = (
        common.loc[common.privacy_status_old.ne(common.privacy_status_current)]
        .assign(
            transition=lambda rows: rows.privacy_status_old + "->" + rows.privacy_status_current
        )
        .transition.value_counts()
        .to_dict()
    )
    expected = source_manifest()["combined_expected_partnerships"]
    assert len(common) == expected["common_events"]
    assert len(combined) - len(common) == expected["added_events"]
    assert len(old) - len(common) == expected["removed_events"]
    assert transitions == expected["privacy_transitions"]

    records, audit = build_verified_partnership_record_holders(combined)
    assert len(records) == expected["record_rows"]
    assert records.wicket_number.tolist() == list(range(1, 11))
    assert audit.validation_status.eq("PASS").all()
