from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from scripts.reconcile_disjoint_player_identities import classify_group, exact_name_key, consolidate
from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
from src.utils.player_identity import apply_player_identity_mapping, resolve_approved_disjoint_player_id, public_player_mask

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "9181d0baf6f33ee3fffe1a66613b92813d203da3"
MERGED_RELEASE = "86ca230a9b16aa73342a86a36ab9b5190126e124"
CLUB = "glen-waverley-hawks"
DATA = ROOT / "clubs" / CLUB / "data"


def released(path, revision=BASELINE):
    relative = str(path.relative_to(ROOT))
    return pd.read_csv(io.BytesIO(subprocess.check_output(["git", "show", f"{revision}:{relative}"], cwd=ROOT)), low_memory=False)


def sample(names=("Exact Player", "EXACT PLAYER"), seasons=("Summer 2022/23", "Summer 2023/24")):
    return pd.DataFrame({"canonical_player_id": [str(i) for i in range(len(names))],
                         "canonical_player_name": names, "season": seasons})


def test_exact_unicode_casefold_and_existing_space_normalization_only():
    assert exact_name_key("  Straße  Player ") == exact_name_key("STRASSE Player")
    assert exact_name_key("John-Smith Player") != exact_name_key("John Smith Player")
    assert exact_name_key("José Player") != exact_name_key("Jose Player")
    assert classify_group(sample())[0] == "ELIGIBLE_FOR_MERGE"
    assert classify_group(sample(names=("Exact Player", "Exakt Player")))[0] == "BLOCKED_GOVERNANCE_CONFLICT"


@pytest.mark.parametrize("seasons", [("Summer 2022/23", "Summer 2022/23"), ("Summer 2022/23", "Summer 2023/24", "Summer 2022/23")])
def test_overlap_and_three_profile_ambiguity_are_not_transitive(seasons):
    assert classify_group(sample(names=("Exact Player",) * len(seasons), seasons=seasons))[0] == "NOT_ELIGIBLE_OVERLAPPING_SEASONS"


def test_private_and_initial_only_profiles_fail_closed():
    private = sample()
    private["is_private"] = [True, False]
    assert classify_group(private)[0] == "BLOCKED_GOVERNANCE_CONFLICT"
    assert classify_group(sample(names=("E Player", "E Player")))[0] == "BLOCKED_GOVERNANCE_CONFLICT"
    different_clubs = sample()
    different_clubs["identity_club_id"] = ["club-a", "club-b"]
    assert classify_group(different_clubs)[0] == "BLOCKED_GOVERNANCE_CONFLICT"
    explicitly_distinct = sample()
    explicitly_distinct["confirmed_distinct"] = True
    assert classify_group(explicitly_distinct)[0] == "NOT_ELIGIBLE_CONFIRMED_DISTINCT"


def decisions():
    frame = pd.read_csv(DATA / "source/disjoint_season_identity_decisions.csv")
    # These assertions audit the original four exact-name merges at 86ca230.
    return frame[frame.decision.eq("customer_approved_exact_disjoint_seasons")]


def test_hawks_merges_retain_every_raw_id_and_complete_season_contribution():
    approved = decisions()
    assert approved.canonical_player_name.nunique() == 4
    for kind in ("batting", "bowling", "fielding"):
        path = DATA / f"processed/all_seasons_{kind}.csv"
        before, after = released(path), released(path, MERGED_RELEASE)
        pd.testing.assert_frame_equal(before.drop(columns="canonical_player_id"), after.drop(columns="canonical_player_id"))
        assert set(before.raw_player_id) == set(after.raw_player_id)
        mapped = apply_player_identity_mapping(after, club_id=CLUB)
        affected = after.raw_player_id.isin(approved.raw_player_id)
        assert mapped.loc[affected].canonical_player_id.tolist() == after.loc[affected].canonical_player_id.tolist()
        baseline_mapped = apply_player_identity_mapping(before, club_id=CLUB)
        assert mapped.loc[~affected].canonical_player_id.tolist() == baseline_mapped.loc[~affected].canonical_player_id.tolist()
        for row in approved.itertuples():
            old = before[before.raw_player_id.eq(row.raw_player_id)]
            new = after[after.raw_player_id.eq(row.raw_player_id)]
            assert set(old.season) == set(new.season)
            assert new.canonical_player_id.eq(row.canonical_player_id).all()
            assert resolve_approved_disjoint_player_id(row.raw_player_id, club_id=CLUB) == row.canonical_player_id
            assert resolve_approved_disjoint_player_id(row.previous_canonical_id, club_id=CLUB) == row.canonical_player_id


def test_source_aliases_are_id_only_no_new_name_or_cross_club_merge():
    row = decisions().iloc[0]
    frame = pd.DataFrame({"player_id": [row.raw_player_id, "unknown-other-person"],
                          "player_name": [row.canonical_player_name, row.canonical_player_name]})
    result = apply_player_identity_mapping(frame, club_id=CLUB)
    assert result.iloc[0].canonical_player_id == row.canonical_player_id
    assert result.iloc[1].canonical_player_id != row.canonical_player_id
    for club in ("fvcc", "georges-river-district"):
        assert resolve_approved_disjoint_player_id(row.raw_player_id, club_id=club) == row.raw_player_id


def test_prepared_canonical_totals_conserve_full_history_and_unaffected_rows():
    path = DATA / "processed/hall_of_fame/prepared_career_all_time.csv"
    before, after = released(path), released(path, MERGED_RELEASE)
    assert len(before) == 1289 and len(after) == 1285
    assert after.canonical_player_id.nunique() == 1285
    assert public_player_mask(after).all()
    approved = decisions()
    metrics = ["Matches", "Runs", "Wickets", "Catches", "Stumpings", "Run Outs", "Innings", "4s", "6s"]
    pd.testing.assert_series_equal(before[metrics].sum(), after[metrics].sum())
    ids = set(approved.previous_canonical_id)
    pd.testing.assert_frame_equal(before[~before.canonical_player_id.isin(ids)].reset_index(drop=True), after[~after.canonical_player_id.isin(ids)].reset_index(drop=True))
    expected = {"Aaditya Sharma": (39, 214, 21, 7), "Darsh Singh": (37, 229, 9, 0),
                "Liam O'Rourke": (140, 1618, 46, 116), "Mitchell Kohne": (151, 2404, 159, 49)}
    for name, totals in expected.items():
        rows = after[after.Player.eq(name)]
        assert len(rows) == 1
        assert tuple(rows.iloc[0][["Matches", "Runs", "Wickets", "Catches"]]) == totals


def test_captain_and_premiership_sufficient_statistics_are_conserved():
    path = DATA / "processed/player_profile/performance_breakdown_by_dimension.csv"
    before, after = released(path), released(path, MERGED_RELEASE)
    for dimension in before.dimension.unique():
        for discipline in before.discipline.unique():
            metrics = ["runs", "innings", "outs", "wickets", "runs_against", "balls_bowled", "catches", "stumpings", "run_outs"]
            old = before[before.dimension.eq(dimension) & before.discipline.eq(discipline)]
            new = after[after.dimension.eq(dimension) & after.discipline.eq(discipline)]
            pd.testing.assert_series_equal(old[metrics].sum(), new[metrics].sum())
    path = DATA / "processed/hall_of_fame/player_premierships.csv"
    before, after = released(path), released(path, MERGED_RELEASE)
    assert before.premiership_count.sum() == after.premiership_count.sum()
    evidence = lambda f: sorted(m.strip() for s in f.evidence_match_ids for m in s.split(","))
    assert evidence(before) == evidence(after)
    assert after.loc[after.canonical_player_name.eq("Liam O'Rourke"), "premiership_count"].tolist() == [2]
    liam = after.loc[after.canonical_player_name.eq("Liam O'Rourke"), "grades"].iloc[0]
    assert "B Grade (80 Overs, 12 Players)" in liam


def test_partnership_evidence_privacy_and_selected_records_preserved():
    path = DATA / "processed/partnerships/partnership_events.csv"
    before, after = released(path), released(path, MERGED_RELEASE)
    pd.testing.assert_frame_equal(before.drop(columns=["player_1_canonical_id", "player_2_canonical_id"]), after.drop(columns=["player_1_canonical_id", "player_2_canonical_id"]))
    for position in (1, 2):
        private = after[f"player_{position}_name"].eq("Private player")
        assert after.loc[private, f"player_{position}_canonical_id"].isna().all()
    path = DATA / "processed/hall_of_fame/partnership_records.csv"
    pd.testing.assert_frame_equal(released(path), released(path, MERGED_RELEASE))


def test_shared_public_query_redirect_is_limited_to_public_index(monkeypatch):
    from src.ui import layout
    row = decisions().iloc[0]
    monkeypatch.setenv("CLUB_ID", CLUB)
    monkeypatch.setattr(layout, "query_param_value", lambda name: row.previous_canonical_id if name == "player_id" else "")
    assert layout.resolve_player_query_to_id({row.canonical_player_id:row.canonical_player_name}) == row.canonical_player_id
    assert layout.resolve_player_query_to_id({}) == ""


def test_valid_prepared_manifest_and_raw_fallback_agree(monkeypatch):
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", CLUB)
    prepared = load_prepared_hall_of_fame_core(CLUB, layout.HALL_OF_FAME_DATA_VERSION)
    assert prepared is not None
    monkeypatch.setenv("SCOREBOOK_IGNORE_PREPARED_HOF", "1")
    fallback = layout.load_hall_of_fame_data.__wrapped__(0, 0, layout.HALL_OF_FAME_DATA_VERSION, club_id=CLUB)
    for kind in ("batting", "bowling", "fielding", "all_time"):
        key = "canonical_player_id"
        for id in decisions().canonical_player_id.unique():
            a = prepared[kind][prepared[kind][key].eq(id)]
            b = fallback[kind][fallback[kind][key].eq(id)]
            assert len(a) == len(b) == 1
            columns = {"all_time": ["Matches", "Runs", "Wickets", "Catches", "HS", "Bat Avg", "Bowl Avg", "Teams/Grades"],
                       "batting":["battingAggregate", "battingNotOuts", "battingAverage"],
                       "bowling":["bowlingWickets", "bowlingRuns", "bowlingBalls"],
                       "fielding":["fieldingTotalCatches"]}[kind]
            pd.testing.assert_series_equal(a.iloc[0][columns], b.iloc[0][columns], check_names=False, check_dtype=False)


def test_summary_rates_use_combined_coverage_not_averages_of_averages():
    frame = pd.DataFrame({"id":["one", "one"], "runs":["20", "60"], "outs":["1", "2"], "avg":["20", "30"], "hs":["20*", "60"]})
    merged = consolidate(frame, ["id"], ["runs", "outs"], {"avg":("runs", "outs", 1)}, ["hs"])
    assert merged.iloc[0]["runs"] == 80
    assert merged.iloc[0]["avg"] == pytest.approx(80/3)
    assert merged.iloc[0]["hs"] == "60"
