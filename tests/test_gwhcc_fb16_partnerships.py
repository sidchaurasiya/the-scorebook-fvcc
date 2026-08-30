from __future__ import annotations

from pathlib import Path

import pandas as pd
from pandas.testing import assert_frame_equal

from src.data.match_centre_parser import build_ball_partnerships
from src.data.partnerships import EVENT_COLUMNS, build_partnership_record_holders, combine_partnership_events, prepare_ball_by_ball_partnerships
from src.ui import layout


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "clubs" / "glen-waverley-hawks" / "data" / "processed"


def source_context(runs: tuple[int, int] = (40, 60), pair_ids: tuple[str, str] = ("player-a", "player-b")):
    partnerships = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "batting_team_id": "hawks",
                "partnership_number": 1,
                "batter_1_participant_id": pair_ids[0],
                "batter_1_name": "A Player",
                "batter_2_participant_id": pair_ids[1],
                "batter_2_name": "B Player",
                "runs": runs[0],
                "balls": 50,
                "source": "ball_by_ball",
                "wicket_ending_participant_id": pair_ids[1],
                "dismissal_type": "Caught",
            },
            {
                "match_id": "match-1",
                "innings_id": "innings-1",
                "batting_team_id": "hawks",
                "partnership_number": 2,
                "batter_1_participant_id": pair_ids[0],
                "batter_1_name": "A Player",
                "batter_2_participant_id": "player-c",
                "batter_2_name": "C Player",
                "runs": runs[1],
                "balls": 70,
                "source": "ball_by_ball",
                "wicket_ending_participant_id": "",
                "dismissal_type": "",
            },
        ]
    )
    matches = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "season": "Summer 2025/26",
                "first_match_day": "2026-01-01",
                "grade_name": "A Grade",
                "home_team_id": "hawks",
                "home_team_name": "Glen Waverley Hawks",
                "away_team_id": "opposition",
                "away_team_name": "Opposition Cricket Club",
            }
        ]
    )
    innings = pd.DataFrame([{"match_id": "match-1", "innings_id": "innings-1", "runs_scored": sum(runs)}])
    identity = {
        "player-a": {"canonical_player_id": "a_player", "canonical_player_name": "A Player"},
        "player-b": {"canonical_player_id": "b_player", "canonical_player_name": "B Player"},
        "player-c": {"canonical_player_id": "c_player", "canonical_player_name": "C Player"},
    }
    return partnerships, matches, innings, identity


def prepare(*, runs: tuple[int, int] = (40, 60), pair_ids: tuple[str, str] = ("player-a", "player-b"), identity=None):
    partnerships, matches, innings, default_identity = source_context(runs, pair_ids)
    return prepare_ball_by_ball_partnerships(
        partnerships,
        matches=matches,
        innings=innings,
        selected_team_ids_by_match={"match-1": {"hawks"}},
        identity_lookup=default_identity if identity is None else identity,
    )


def test_existing_delivery_calculator_builds_partnership_runs_and_pairs() -> None:
    balls = pd.DataFrame(
        [
            {"match_id": "m", "innings_id": "i", "batting_team_id": "t", "over_number": 1, "ball_number": 1, "ball_event_id": "1", "striker_participant_id": "a", "striker_short_name": "A", "non_striker_participant_id": "b", "non_striker_short_name": "B", "total_runs": 1, "is_legal_delivery": True, "is_wicket": False, "progress_score": "0-1", "dismissed_participant_id": "", "dismissal_type": ""},
            {"match_id": "m", "innings_id": "i", "batting_team_id": "t", "over_number": 1, "ball_number": 2, "ball_event_id": "2", "striker_participant_id": "b", "striker_short_name": "B", "non_striker_participant_id": "a", "non_striker_short_name": "A", "total_runs": 4, "is_legal_delivery": True, "is_wicket": True, "progress_score": "1-5", "dismissed_participant_id": "b", "dismissal_type": "Caught"},
            {"match_id": "m", "innings_id": "i", "batting_team_id": "t", "over_number": 1, "ball_number": 3, "ball_event_id": "3", "striker_participant_id": "a", "striker_short_name": "A", "non_striker_participant_id": "c", "non_striker_short_name": "C", "total_runs": 2, "is_legal_delivery": True, "is_wicket": False, "progress_score": "1-7", "dismissed_participant_id": "", "dismissal_type": ""},
            {"match_id": "m", "innings_id": "i", "batting_team_id": "t", "over_number": 1, "ball_number": 4, "ball_event_id": "4", "striker_participant_id": "c", "striker_short_name": "C", "non_striker_participant_id": "a", "non_striker_short_name": "A", "total_runs": 3, "is_legal_delivery": True, "is_wicket": False, "progress_score": "1-10", "dismissed_participant_id": "", "dismissal_type": ""},
        ]
    )
    result = build_ball_partnerships(balls)
    assert result["runs"].tolist() == [5, 5]
    assert result[["batter_1_name", "batter_2_name"]].values.tolist() == [["A", "B"], ["A", "C"]]


def test_partnership_preparation_reconciles_runs_and_context() -> None:
    result = prepare()
    assert len(result.events) == 2
    assert result.events["privacy_status"].eq("PUBLIC_PUBLIC").all()
    first = result.events.iloc[0]
    assert first["runs"] == 40
    assert first["balls"] == 50
    assert first["opponent"] == "Opposition Cricket Club"
    assert first["evidence_quality"] == "innings_total_reconciled"


def test_duplicate_canonical_identity_is_held_for_review() -> None:
    identity = {
        "player-a": {"canonical_player_id": "same", "canonical_player_name": "Same Player"},
        "player-b": {"canonical_player_id": "same", "canonical_player_name": "Same Player"},
        "player-c": {"canonical_player_id": "c_player", "canonical_player_name": "C Player"},
    }
    result = prepare(identity=identity)
    first = result.audit[result.audit["wicket_number"].eq(1)].iloc[0]
    assert first["validation_status"] == "REVIEW"
    assert "same canonical player" in first["review_reason"]


def test_missing_identity_is_held_for_review() -> None:
    result = prepare(identity={"player-a": {"canonical_player_id": "a", "canonical_player_name": "A Player"}})
    assert result.events.empty
    assert result.audit["validation_status"].eq("REVIEW").all()
    assert result.coverage["unresolved_events_excluded"] == 2


def test_public_private_pair_is_redacted_and_published() -> None:
    identity = {
        "player-a": {"canonical_player_id": "private", "canonical_player_name": "********"},
        "player-b": {"canonical_player_id": "b", "canonical_player_name": "B Player"},
        "player-c": {"canonical_player_id": "c", "canonical_player_name": "C Player"},
    }
    result = prepare(identity=identity)
    assert len(result.events) == 2
    assert result.events["privacy_status"].eq("PUBLIC_PRIVATE").all()
    assert result.events["player_1_name"].eq("Private player").all()
    assert result.events["player_1_canonical_id"].fillna("").eq("").all()
    assert result.events["player_2_name"].tolist() == ["B Player", "C Player"]
    assert result.audit["validation_status"].eq("CONFIRMED").all()


def test_private_private_pair_is_excluded() -> None:
    identity = {
        "player-a": {"canonical_player_id": "private-a", "canonical_player_name": "********"},
        "player-b": {"canonical_player_id": "private-b", "canonical_player_name": "********"},
        "player-c": {"canonical_player_id": "private-c", "canonical_player_name": "********"},
    }
    result = prepare(identity=identity)
    assert result.events.empty
    assert result.audit["validation_status"].eq("EXCLUDED_PRIVATE").all()
    assert result.audit["privacy_status"].eq("PRIVATE_PRIVATE").all()


def test_mismatched_innings_total_is_not_published() -> None:
    result = prepare(runs=(40, 50))
    # Source context expects the same supplied runs, so force the scorecard mismatch explicitly.
    partnerships, matches, innings, identity = source_context((40, 50))
    innings["runs_scored"] = 100
    result = prepare_ball_by_ball_partnerships(
        partnerships,
        matches=matches,
        innings=innings,
        selected_team_ids_by_match={"match-1": {"hawks"}},
        identity_lookup=identity,
    )
    assert result.events.empty
    assert result.audit["validation_status"].eq("REVIEW").all()


def test_preparation_and_record_selection_are_reproducible() -> None:
    first = prepare()
    second = prepare()
    assert_frame_equal(first.events, second.events)
    assert_frame_equal(build_partnership_record_holders(first.events), build_partnership_record_holders(second.events))


def partnership_record_event(
    record_id: str,
    *,
    runs: int,
    privacy_status: str,
    player_1_name: str = "Public Player",
    player_2_name: str = "Second Public Player",
    match_date: str = "2025-01-01",
) -> dict[str, object]:
    row = {column: "" for column in EVENT_COLUMNS}
    row.update(
        {
            "record_id": record_id,
            "player_1_canonical_id": "public-player",
            "player_1_name": player_1_name,
            "player_2_canonical_id": "" if player_2_name == "Private player" else "second-public-player",
            "player_2_name": player_2_name,
            "runs": runs,
            "balls": 60,
            "wicket_number": 1,
            "season": "Summer 2024/25",
            "match_id": f"match-{record_id}",
            "innings_id": f"innings-{record_id}",
            "match_date": match_date,
            "source_classification": "ball_by_ball_calculated",
            "privacy_status": privacy_status,
        }
    )
    return row


def test_public_private_can_win_record_selection() -> None:
    events = pd.DataFrame(
        [
            partnership_record_event("public-public", runs=100, privacy_status="PUBLIC_PUBLIC"),
            partnership_record_event(
                "public-private",
                runs=120,
                privacy_status="PUBLIC_PRIVATE",
                player_2_name="Private player",
            ),
        ]
    )
    records = build_partnership_record_holders(events)
    assert records.iloc[0]["record_id"] == "public-private"
    assert records.iloc[0]["player_2_name"] == "Private player"
    assert records.iloc[0]["player_2_canonical_id"] == ""


def test_record_tie_remains_deterministic_after_redaction() -> None:
    events = pd.DataFrame(
        [
            partnership_record_event(
                "later",
                runs=120,
                privacy_status="PUBLIC_PRIVATE",
                player_2_name="Private player",
                match_date="2025-02-01",
            ),
            partnership_record_event(
                "earlier",
                runs=120,
                privacy_status="PUBLIC_PRIVATE",
                player_2_name="Private player",
                match_date="2025-01-01",
            ),
        ]
    ).sample(frac=1, random_state=7)
    records = build_partnership_record_holders(events)
    assert records.iloc[0]["record_id"] == "earlier"


def test_gwhcc_runtime_redaction_prevents_private_link_and_query_exposure() -> None:
    records = pd.DataFrame(
        [
            {
                "record_id": "public-private",
                "player_1_canonical_id": "public-id",
                "player_1_name": "Public Player",
                "player_2_canonical_id": "private-source-id",
                "player_2_name": "********",
                "runs": 120,
                "wicket_number": 1,
                "privacy_status": "PUBLIC_PRIVATE",
                "season": "Summer 2024/25",
                "match_id": "match-1",
                "source_classification": "ball_by_ball_calculated",
            },
            {
                "record_id": "private-private",
                "player_1_canonical_id": "private-1",
                "player_1_name": "********",
                "player_2_canonical_id": "private-2",
                "player_2_name": "********",
                "runs": 130,
                "wicket_number": 2,
                "privacy_status": "PRIVATE_PRIVATE",
            },
        ]
    )
    protected = layout.protect_gwhcc_partnership_record_privacy(records)
    assert protected["record_id"].tolist() == ["public-private"]
    row = protected.iloc[0]
    assert row["player_2_name"] == "Private player"
    assert row["player_2_canonical_id"] == ""

    rendered = layout.partnership_record_row_html(row)
    assert "Public Player" in rendered
    assert "Private player" in rendered
    assert "private-source-id" not in rendered
    assert "player_id=private" not in rendered.casefold()
    assert "********" not in rendered


def test_playcricket_precedes_equivalent_customer_partnership() -> None:
    playcricket = prepare().events.iloc[[0]].copy()
    document = playcricket.copy()
    document["record_id"] = "document-equivalent"
    document["source_classification"] = "customer_document"
    document["evidence_quality"] = "club_record_document"
    combined = combine_partnership_events(document[EVENT_COLUMNS], playcricket[EVENT_COLUMNS])
    assert len(combined) == 1
    assert combined.iloc[0]["source_classification"] == "ball_by_ball_calculated"


def test_deployed_partnership_outputs_are_public_and_validated() -> None:
    events = pd.read_csv(PROCESSED / "partnerships" / "partnership_events.csv", low_memory=False)
    records = pd.read_csv(PROCESSED / "hall_of_fame" / "partnership_records.csv", low_memory=False)
    validation = pd.read_csv(PROCESSED / "validation" / "gwhcc_partnership_validation.csv")
    assert len(events) == 3350
    assert events["privacy_status"].value_counts().to_dict() == {
        "PUBLIC_PUBLIC": 3314,
        "PUBLIC_PRIVATE": 36,
    }
    assert records["wicket_number"].tolist() == list(range(1, 11))
    assert not events["player_1_name"].astype(str).str.contains(r"\*{2,}", regex=True).any()
    assert not events["player_2_name"].astype(str).str.contains(r"\*{2,}", regex=True).any()
    private_rows = events[events["privacy_status"].eq("PUBLIC_PRIVATE")]
    protected_slots = pd.concat(
        [
            private_rows.loc[private_rows["player_1_name"].eq("Private player"), "player_1_canonical_id"],
            private_rows.loc[private_rows["player_2_name"].eq("Private player"), "player_2_canonical_id"],
        ],
        ignore_index=True,
    )
    assert len(protected_slots) == len(private_rows)
    assert protected_slots.fillna("").eq("").all()
    assert validation["status"].ne("FAIL").all()
