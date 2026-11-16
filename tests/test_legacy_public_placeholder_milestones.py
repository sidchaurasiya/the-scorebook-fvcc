from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from scripts.sanitize_legacy_public_milestone_placeholders import (
    sanitize_legacy_public_milestones,
)


def test_legacy_milestone_redaction_is_scoped_preserves_values_and_unlinks_profile(tmp_path):
    processed = tmp_path / "clubs/ashwood/data/processed"
    hof = processed / "hall_of_fame"
    hof.mkdir(parents=True)
    milestones = hof / "fastest_batting_milestones.csv"
    links = hof / "scorecard_record_links.csv"
    with milestones.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["player_id", "participant_id", "player_name", "canonical_player_name", "match_id", "innings_id", "final_runs", "final_balls"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(
            [
                {"player_id": "00000000-0000-0000-0000-000000000099", "participant_id": "00000000-0000-0000-0000-000000000099", "player_name": "Unverified label", "canonical_player_name": "Unverified label", "match_id": "match-1", "innings_id": "innings-1", "final_runs": 54, "final_balls": 39},
                {"player_id": "00000000-0000-0000-0000-000000000098", "participant_id": "00000000-0000-0000-0000-000000000098", "player_name": "********", "canonical_player_name": "********", "match_id": "match-2", "innings_id": "innings-2", "final_runs": 25, "final_balls": 17},
                {"player_id": "verified-player", "participant_id": "verified-player", "player_name": "Public Player", "canonical_player_name": "Public Player", "match_id": "match-3", "innings_id": "innings-3", "final_runs": 31, "final_balls": 20},
            ]
        )
    with links.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["match_id", "canonical_player_id", "canonical_player_name", "runs_scored", "scorecard_url"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(
            [
                {"match_id": "match-1", "canonical_player_id": "profile-1", "canonical_player_name": "Unverified label", "runs_scored": 54, "scorecard_url": "https://example.test/match-1"},
                {"match_id": "match-2", "canonical_player_id": "profile-3", "canonical_player_name": "********", "runs_scored": 25, "scorecard_url": "https://example.test/match-2"},
                {"match_id": "match-other", "canonical_player_id": "profile-2", "canonical_player_name": "Unverified label", "runs_scored": 20, "scorecard_url": "https://example.test/match-other"},
            ]
        )
    unrelated = tmp_path / "clubs/lyndale/data/processed/hall_of_fame/fastest_batting_milestones.csv"
    unrelated.parent.mkdir(parents=True)
    unrelated.write_text("player_id,player_name,match_id,final_runs\n00000000-0000-0000-0000-000000000097,Unrelated,other,88\n")
    unrelated_before = unrelated.read_bytes()

    receipt = sanitize_legacy_public_milestones(tmp_path, write=True)
    output = pd.read_csv(milestones, dtype=str, keep_default_na=False)
    link_output = pd.read_csv(links, dtype=str, keep_default_na=False)

    assert receipt["clubs"]["ashwood"]["anonymous_milestone_rows"] == 2
    assert receipt["clubs"]["ashwood"]["same_match_profile_link_rows"] == 2
    assert len(output) == 3
    assert output.loc[0, "player_id"] == output.loc[0, "participant_id"] == ""
    assert output.loc[0, "player_name"] == output.loc[0, "canonical_player_name"] == "Private player"
    assert output.loc[1, "player_id"] == output.loc[1, "participant_id"] == ""
    assert output.loc[1, "player_name"] == "********"
    assert output.loc[2, "player_id"] == "verified-player"
    assert "public_record_row_key" not in output
    assert output.final_runs.tolist() == ["54", "25", "31"]
    assert len(link_output) == 3
    assert link_output.loc[0, "canonical_player_id"] == ""
    assert link_output.loc[0, "canonical_player_name"] == "Private player"
    assert link_output.loc[0, "runs_scored"] == "54"
    assert link_output.loc[1, "canonical_player_id"] == ""
    assert link_output.loc[1, "canonical_player_name"] == "Private player"
    assert link_output.loc[1, "runs_scored"] == "25"
    assert link_output.loc[2, "canonical_player_id"] == "profile-2"
    assert unrelated.read_bytes() == unrelated_before

    second = sanitize_legacy_public_milestones(tmp_path, write=True)
    assert second["clubs"]["ashwood"]["milestone_rows_before"] == 3
    assert output.equals(pd.read_csv(milestones, dtype=str, keep_default_na=False))
