from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data import gwhcc_document_overrides as docs
from src.data import gwhcc_historical_career as history

ROOT = Path(__file__).resolve().parents[1]
HOF = ROOT / "clubs/glen-waverley-hawks/data/processed/hall_of_fame"
EXPECTED = pd.read_csv(ROOT / "tests/fixtures/gwhcc_clubwide_expected_career_metrics.csv")


def core_frame():
    frame = pd.read_csv(HOF / "prepared_career_all_time.csv")
    batting = pd.read_csv(HOF / "prepared_career_batting.csv")
    return frame.merge(batting[["canonical_player_id", "battingNotOuts"]].rename(columns={"battingNotOuts": "Not Outs"}), on="canonical_player_id", validate="one_to_one")


def test_every_verified_decision_has_one_public_identity_and_auditable_source(monkeypatch):
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", history.CLUB_ID)
    source = history.load_dated_career_anchors()
    assert len(source) == len(EXPECTED) == 63
    assert source.canonical_player_id.is_unique
    index = layout.load_player_profile_index(history.CLUB_ID, layout.metadata_mtime(), layout.player_aliases_mtime())
    for row in source.to_dict("records"):
        assert int(index.id.eq(row["canonical_player_id"]).sum()) == 1
        assert row["source_row"]
        assert len(row["source_sha256"]) == 64
    additional = pd.read_csv(history.VERIFIED_ANCHORS)
    assert len(additional) == 61
    assert additional.identity_evidence.str.contains("existing approved|independent nonzero annual-count fingerprints", regex=True).all()
    assert not source.canonical_player_id.isin(set(docs.load_historical_career_metric_decisions().canonical_player_id)).any()


def test_all_authoritative_metrics_match_independently_reconciled_fixture():
    from src.ui import layout
    actual = docs.apply_record_overrides(core_frame(), write_decisions=False)
    displayed = layout.add_gwhcc_not_outs_for_display(actual, pd.read_csv(HOF / "prepared_career_batting.csv"))
    selected = displayed.set_index("canonical_player_id").loc[EXPECTED.canonical_player_id]
    expected = EXPECTED.set_index("canonical_player_id")
    for column in ["Runs", "Innings", "Not Outs", "Wickets", "Bat Avg", "Bowl Avg", "Matches", "Catches", "100s"]:
        left = pd.to_numeric(selected[column], errors="coerce")
        right = pd.to_numeric(expected[column], errors="coerce")
        pd.testing.assert_series_equal(left, right, check_names=False, check_dtype=False, atol=1e-9)


@pytest.mark.parametrize("pid", EXPECTED.canonical_player_id.tolist())
def test_each_real_profile_preserves_seasons_and_uses_governed_summary(pid, monkeypatch):
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", history.CLUB_ID)
    # Delivery-derived detail is unchanged and is not needed to validate historical career authority.
    monkeypatch.setattr(layout, "load_player_profile_detail_sources", lambda *args, **kwargs: {})
    profile = layout.get_player_profile_data(pid, layout.metadata_mtime(), layout.player_aliases_mtime(), club_id=history.CLUB_ID)
    view = layout.build_player_profile_view.__wrapped__(profile, layout.player_profile_view_signature())
    assert len(view["career"]) == 1
    career = view["career"].iloc[0]
    expected = EXPECTED[EXPECTED.canonical_player_id.eq(pid)].iloc[0]
    selected = {"Matches", "Catches", "100s"}
    if "batting" in str(expected.metric_scope):
        selected |= {"Runs", "Innings", "Not Outs", "Bat Avg"}
    if "bowling" in str(expected.metric_scope):
        selected |= {"Wickets", "Bowl Avg", "Runs Against"}
    for metric in selected:
        assert float(career[metric]) == pytest.approx(float(expected[metric]))
    assert str(career.Player).casefold() == str(expected.Player).casefold()
    raw_seasons = set().union(*(set(profile[d].season) for d in ["batting", "bowling", "fielding"] if not profile[d].empty))
    assert set(view["season_table"].Season) == raw_seasons
    for metric in ["Runs", "Wickets"]:
        milestone = next((r for r in layout.player_milestone_rows(career) if r["category"] == metric), None)
        if float(career[metric]) > 0:
            assert milestone["current"] == int(career[metric])
    note = history.career_anchor_coverage_note(career)
    assert note and note in layout.player_profile_historical_coverage_html(career, view["season_table"])


def test_only_approved_metric_bundles_change_and_all_other_players_are_preserved(monkeypatch):
    base = core_frame()
    with monkeypatch.context() as m:
        m.setattr(history, "VERIFIED_ANCHORS", ROOT / "not_present.csv")
        before = docs.apply_record_overrides(base, write_decisions=False)
    after = docs.apply_record_overrides(base, write_decisions=False)
    additional = pd.read_csv(history.VERIFIED_ANCHORS)
    other = ~before.canonical_player_id.isin(additional.canonical_player_id)
    pd.testing.assert_frame_equal(before.loc[other].reset_index(drop=True), after.loc[other, before.columns].reset_index(drop=True), check_dtype=False)
    for metric in ["Matches", "Catches", "Stumpings", "Run Outs", "HS", "50s", "100s", "BBI"]:
        pd.testing.assert_series_equal(before[metric], after[metric], check_dtype=False)
    assert int(other.sum()) == 1223
    assert len(after) == 1284 and after.canonical_player_id.is_unique


def test_review_rows_remain_suppressed_even_when_an_independent_anchor_has_the_same_value(monkeypatch):
    base = core_frame()
    with monkeypatch.context() as m:
        m.setattr(history, "VERIFIED_ANCHORS", ROOT / "not_present.csv")
        legacy = docs.apply_record_overrides(base, write_decisions=False)
    candidate = docs.apply_record_overrides(base, write_decisions=False)
    old = legacy[legacy.Player.eq("Glen Mahoney")].iloc[0]
    new = candidate[candidate.Player.eq("Glen Mahoney")].iloc[0]
    assert old.Runs == 7734
    assert new.Runs == 11040
    assert new.runs_value_source == "dated_career_master"
    assert int(new.runs_authority_source_row) == 498
    review = docs.load_record_overrides()
    review = review[review.player_name.eq("G. Mahoney") & review.metric_key.eq("runs")].iloc[0]
    assert review.confidence == "review" and not docs.is_production_approved_record_override(review)


def test_known_identity_and_statistical_conflicts_are_not_silently_approved():
    source = history.load_dated_career_anchors()
    assert not source.canonical_player_name.isin(["Aris Voulanas", "Steven Smoothy", "Greg Mccormick", "James Anderson", "Sunny Somaia", "Sunil Somaia"]).any()
    medina = source[source.canonical_player_name.eq("Anthony Medina")].iloc[0]
    assert medina.metric_scope == "batting"
    assert not str(medina.wickets).strip()
    actual = docs.apply_record_overrides(core_frame(), write_decisions=False)
    assert actual[actual.Player.eq("Anthony Medina")].iloc[0].Wickets == 62
    glenn = source[source.canonical_player_name.eq("Glenn Haye")].iloc[0]
    grant = source[source.canonical_player_name.eq("Grant Haye")].iloc[0]
    assert glenn.canonical_player_id != grant.canonical_player_id
    assert float(glenn.runs) == 65 and float(grant.runs) == 6215


def test_individual_cutoffs_and_current_season_contributions_survive():
    source = history.load_dated_career_anchors().set_index("canonical_player_name")
    assert source.loc["Jarrod Greaves", "batting_anchor_through_season"] == "Summer 2022/23"
    assert source.loc["Brett Powell", "batting_anchor_through_season"] == "Summer 2020/21"
    assert source.loc["Brett Powell", "bowling_anchor_through_season"] == "Summer 2025/26"
    actual = docs.apply_record_overrides(core_frame(), write_decisions=False).set_index("Player")
    assert actual.loc["Jarrod Greaves", "Runs"] == 7098 + 52
    assert actual.loc["Nathan Bungey", "Runs"] == 3330 + 50
    assert actual.loc["Matthew Briginshaw", "Wickets"] == 533 + 2


def test_partial_bundle_notes_do_not_claim_unsupported_history():
    source = docs.apply_record_overrides(core_frame(), write_decisions=False).set_index("Player")
    assert history.has_dated_career_scope(source.loc["Brooke Calder"], "batting")
    assert not history.has_dated_career_scope(source.loc["Brooke Calder"], "bowling")
    assert "Bowling, matches" in history.career_anchor_coverage_note(source.loc["Brooke Calder"])
    assert not history.has_dated_career_scope(source.loc["Shivo Arivalakan"], "batting")
    assert "Batting, matches" in history.career_anchor_coverage_note(source.loc["Shivo Arivalakan"])


@pytest.mark.parametrize("scope", ["batting", "bowling", "batting;bowling"])
def test_independent_metric_cutoffs_and_later_refreshes_do_not_overlap(scope, tmp_path, monkeypatch):
    pid = "test_metric_cutoff_identity"
    anchor = {"canonical_player_id": pid, "canonical_player_name": "Test Player", "metric_scope": scope,
              "anchor_through_season": "Summer 2023/24", "batting_anchor_through_season": "Summer 2021/22",
              "bowling_anchor_through_season": "Summer 2023/24", "runs": 100, "innings": 10, "not_outs": 2,
              "wickets": 5, "bowling_runs": 50, "source_document": "Test source", "source_sheet": "Sheet1",
              "source_row": 1, "source_sha256": "a" * 64, "confidence": "high", "decision_status": "approved_dated_career"}
    for field in (["wickets", "bowling_runs"] if scope == "batting" else ["runs", "innings", "not_outs"] if scope == "bowling" else []):
        anchor[field] = ""  # Unsupported fields are absent, not manufactured zero.
    path = tmp_path / "anchors.csv"
    pd.DataFrame([anchor]).to_csv(path, index=False)
    monkeypatch.setattr(history, "ANCHORS", path)
    monkeypatch.setattr(history, "VERIFIED_ANCHORS", tmp_path / "not_present.csv")
    for discipline in ["batting", "bowling"]:
        rows = []
        for year in [2022, 2026]:
            row = {"canonical_player_id": pid, "season_id": str(year), "season": f"Summer {year}/{(year+1)%100:02d}", "team_id": "team", "grade_id": "grade"}
            row.update(battingAggregate=20 if year == 2022 else 7, battingInnings=2 if year == 2022 else 1,
                       battingNotOuts=1 if year == 2022 else 0, bowlingWickets=2 if year == 2022 else 1, bowlingRuns=30 if year == 2022 else 6)
            rows.append(row)
        source = tmp_path / f"{discipline}.csv"
        pd.DataFrame(rows).to_csv(source, index=False)
        monkeypatch.setattr(history, discipline.upper(), source)
    frame = pd.DataFrame([{"canonical_player_id": pid, "Player": "Test Player", "Runs": 27, "Innings": 3,
                           "Not Outs": 1, "Bat Avg": 13.5, "Wickets": 3, "Runs Against": 36, "Bowl Avg": 12, "Matches": 4.5}])
    first = history.apply_dated_career_anchors(frame).iloc[0]
    assert first.Runs == (127 if "batting" in scope else 27)
    assert first.Wickets == (6 if "bowling" in scope else 3)
    if "bowling" in scope:
        # The 2022 bowling is already inside the 2023/24 anchor, not an extra two wickets.
        assert first["Runs Against"] == 56
        assert first["Bowl Avg"] == pytest.approx(56/6)
    bow = pd.read_csv(history.BOWLING)
    extra = bow.tail(1).copy()
    extra["season_id"] = "2027"; extra["season"] = "Summer 2027/28"
    pd.concat([bow, extra], ignore_index=True).to_csv(history.BOWLING, index=False)
    second = history.apply_dated_career_anchors(frame).iloc[0]
    assert second.Wickets == (7 if "bowling" in scope else 3)
    assert second.Runs == first.Runs
    assert second.Matches == frame.iloc[0].Matches


def test_restored_undated_totals_do_not_manufacture_current_season_achievement_dates(monkeypatch):
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", history.CLUB_ID)
    data = ROOT / "clubs/glen-waverley-hawks/data/processed"
    historical = {"all_time": docs.apply_record_overrides(core_frame(), write_decisions=False),
                  **{f"{d}_raw": pd.read_csv(data / f"all_seasons_{d}.csv", low_memory=False)
                     for d in ["batting", "bowling", "fielding"]}}
    achieved = layout.build_achieved_milestones(historical, ["Summer 2026/27"], history.CLUB_ID)
    if achieved.empty:
        return
    for pid, category, threshold in [("raw_2a9340d0_cfdd_447e_8601_370472fd4b41", "Runs", 11000),
                                      ("raw_b8d2d93c_0fc0_4e1f_9671_f1fc051e10d5", "Runs", 7000),
                                      ("nathan_bungey", "Wickets", 400)]:
        assert achieved[achieved.canonical_player_id.eq(pid) & achieved.Category.eq(category) & achieved.Threshold.eq(threshold)].empty
