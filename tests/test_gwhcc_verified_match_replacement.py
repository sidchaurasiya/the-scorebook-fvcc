from pathlib import Path

import pandas as pd
import pytest

from src.data import gwhcc_document_overrides as documents
from src.data import gwhcc_historical_career as history
from src.data import gwhcc_match_policy as policy

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = pd.read_csv(ROOT / "tests/fixtures/gwhcc_clubwide_match_expected.csv")
HELD = {"noel_blacker": 106, "raw_561b5dda_3abc_467a_b91f_147590e6ed10": 25.5}


def test_exact_nine_added_and_both_closed_brother_decisions_preserved():
    anchors = history.load_dated_match_anchors().set_index("canonical_player_id")
    assert anchors.index.is_unique and len(anchors) == 11
    assert set(anchors.index) == set(EXPECTED.canonical_player_id)
    assert not set(HELD).intersection(anchors.index)
    assert anchors.loc["raw_f62c84ce_8d81_4700_bd22_ee8494bab921", "matches"] == 390.5
    assert anchors.loc["raw_289b8e53_aa95_4072_8288_588447304bcd", "matches"] == 296


@pytest.mark.parametrize("decision", EXPECTED.to_dict("records"), ids=EXPECTED.player_name.tolist())
def test_each_approved_value_reaches_one_public_profile(decision, monkeypatch):
    from src.ui import layout

    monkeypatch.setenv("CLUB_ID", history.CLUB_ID)
    monkeypatch.setattr(layout, "load_player_profile_detail_sources", lambda *args, **kwargs: {})
    pid = decision["canonical_player_id"]
    index = layout.load_player_profile_index.__wrapped__(history.CLUB_ID, layout.metadata_mtime(), layout.player_aliases_mtime())
    assert index.id.eq(pid).sum() == 1
    profile = layout.get_player_profile_data(pid, layout.metadata_mtime(), layout.player_aliases_mtime(), club_id=history.CLUB_ID)
    career = layout.build_player_profile_view.__wrapped__(profile, layout.player_profile_view_signature())["career"].iloc[0]
    assert career.Matches == decision["candidate_matches"]
    assert career.Player == decision["player_name"]
    assert decision["cutoff"] in history.career_anchor_coverage_note(career)
    watch = next(r for r in layout.player_milestone_rows(career) if r["category"] == "Matches")
    assert watch["current"] == career.Matches
    assert watch["remaining"] == watch["target"] - career.Matches


def test_held_values_have_no_direct_or_indirect_match_anchor_effect():
    prepared = pd.read_csv(history.DATA / "processed/hall_of_fame/prepared_career_all_time.csv")
    actual = documents.apply_record_overrides(prepared, write_decisions=False)
    for pid, value in HELD.items():
        row = actual[actual.canonical_player_id.eq(pid)]
        assert len(row) == 1 and row.Matches.iloc[0] == value
        assert str(row.iloc[0].get("historical_match_anchor_applied", "")).casefold() not in {"true", "1"}
        assert "Career matches use the club's verified total" not in history.career_anchor_coverage_note(row.iloc[0])
    again = documents.apply_record_overrides(actual, write_decisions=False)
    pd.testing.assert_series_equal(actual.Matches, again.Matches)


@pytest.mark.parametrize("matches,target", [(1,100),(46,100),(49.5,100),(50,100),(99.5,100),(100,200),(199.5,200),(299.5,300),(391.5,400),(400,500)])
def test_separate_first_fifty_profile_alignment_is_not_bundled(matches, target, monkeypatch):
    from src.ui import layout

    monkeypatch.setenv("CLUB_ID", history.CLUB_ID)
    row = layout.player_milestone_rows(pd.Series({"Matches": matches}))[0]
    assert row["target"] == target and row["remaining"] == target - matches
    assert 50 in layout.milestone_match_thresholds(history.CLUB_ID, extended=True)
    assert layout.next_milestone_target(49.5, 100, first_threshold=50) == 50


@pytest.mark.parametrize("club", ["fvcc", "georges-river-district"])
def test_other_club_match_counts_and_profile_thresholds_unchanged(club, monkeypatch):
    from src.ui import layout

    monkeypatch.setenv("CLUB_ID", club)
    frame = pd.DataFrame([{"canonical_player_id": "noel_blacker", "Player": "Noel Blacker", "Matches": 46}])
    pd.testing.assert_frame_equal(history.apply_dated_match_anchors(frame, club_id=club), frame)
    assert layout.player_milestone_rows(frame.iloc[0])[0]["target"] == 100


def test_existing_no_play_policy_does_not_auto_credit_completed_empty_squad(monkeypatch):
    matches = pd.DataFrame([
        {"match_id": mid, "match_type": kind, "status": "COMPLETED", "result_text": "Match drawn", "home_team_id": "hawks", "away_team_id": "other"}
        for mid, kind in [("empty-selected", "One Day"), ("unknown", "One Day"), ("played-t20", "T20"), ("played-dnb", "One Day")]
    ])
    innings = pd.DataFrame([{"match_id": mid, "innings_id": mid+"i", "runs_scored": 1, "wickets_fallen": 0, "overs_bowled": 1}
                            for mid in ["played-t20", "played-dnb"]])
    monkeypatch.setattr(policy, "raw_selected_player_counts", lambda seed: pd.DataFrame({"match_id": seed.match_id, "selected_player_count": [0 if m == "unknown" else 11 for m in seed.match_id]}))
    frames = {"matches": matches, "innings": innings, "teams": pd.DataFrame({"team_id": ["hawks"]}),
              **{k: pd.DataFrame() for k in ["balls", "overs", "batting", "bowling", "fielding"]}}
    actual = policy.build_match_policy_table(frames).set_index("match_id")
    assert actual.loc["empty-selected", "match_weight"] == 0
    assert actual.loc["unknown", "review_required"]
    assert actual.loc["played-t20", "match_weight"] == .5
    assert actual.loc["played-dnb", "match_weight"] == 1


def test_existing_noel_source_id_mapping_is_not_split_or_extended():
    annual = pd.read_csv(history.BATTING, usecols=["canonical_player_id", "raw_player_id"])
    assert set(annual.loc[annual.canonical_player_id.eq("noel_blacker"), "raw_player_id"]) == {
        "358ccd1e-70b9-4e16-a143-ff705b0830e9", "0554715b-b774-43bc-8cd3-8100a4753e9a"}
    assert set(annual.loc[annual.canonical_player_id.eq("raw_561b5dda_3abc_467a_b91f_147590e6ed10"), "raw_player_id"]) == {"561b5dda-3abc-467a-b91f-147590e6ed10"}
