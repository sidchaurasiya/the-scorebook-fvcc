from __future__ import annotations

import pandas as pd

from src.ui import layout


def test_profile_detail_reader_preserves_id_first_selection_and_club_rows(tmp_path) -> None:
    source = tmp_path / "detail.csv"
    pd.DataFrame(
        [
            {"canonical_player_id": "__club__", "canonical_player_name": "Club average", "scope": "club", "value": 99},
            {"canonical_player_id": "target", "canonical_player_name": "Target Player", "scope": "player", "value": 1},
            {"canonical_player_id": "other", "canonical_player_name": "Target Player", "scope": "player", "value": 2},
        ]
    ).to_csv(source, index=False)

    result = layout.read_match_centre_csv_for_player(
        source,
        "target",
        layout.player_name_match_key("Target Player"),
        include_club_rows=True,
    )

    assert result["value"].tolist() == [1, 99]
    assert result["canonical_player_id"].tolist() == ["target", "__club__"]


def test_profile_detail_reader_falls_back_to_name_and_preserves_empty_schema(tmp_path) -> None:
    source = tmp_path / "detail.csv"
    pd.DataFrame(
        [{"canonical_player_name": "Name Only", "scope": "player", "value": 7}]
    ).to_csv(source, index=False)

    matched = layout.read_match_centre_csv_for_player(
        source,
        "missing-id",
        layout.player_name_match_key("Name Only"),
    )
    empty = layout.read_match_centre_csv_for_player(
        source,
        "missing-id",
        layout.player_name_match_key("Unknown"),
    )

    assert matched["value"].tolist() == [7]
    assert empty.empty
    assert list(empty.columns) == ["canonical_player_name", "scope", "value"]


def test_peer_source_compaction_keeps_only_peer_inputs() -> None:
    source = pd.DataFrame(
        [
            {
                "season": "Summer 2025/26",
                "canonical_player_id": "target",
                "team_name": "Team",
                "grade_name": "C Grade",
                "canonical_grade_label": "C Grade",
                "team_grade_display": "C Grade",
                "canonical_team_label": "Team",
                "clean_team_name": "Team",
                "battingAggregate": 100,
                "battingInnings": 5,
                "battingNotOuts": 1,
                "battingBallsFaced": 80,
                "battingFours": 10,
                "battingSixes": 2,
                "batting0s": 0,
                "unused_large_source_column": "discarded",
            }
        ]
    )

    result = layout.compact_player_peer_source(source, "batting")

    assert "unused_large_source_column" not in result
    assert set(result.columns) == {
        "season",
        "canonical_player_id",
        "team_name",
        "grade_name",
        "canonical_grade_label",
        "team_grade_display",
        "canonical_team_label",
        "clean_team_name",
        "battingAggregate",
        "battingInnings",
        "battingNotOuts",
        "battingBallsFaced",
        "battingFours",
        "battingSixes",
        "batting0s",
    }
