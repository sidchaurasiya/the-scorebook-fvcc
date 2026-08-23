from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.gwhcc_document_overrides import (
    apply_historical_career_metric_decisions,
    apply_record_overrides,
    load_historical_career_metric_decisions,
)


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "clubs" / "glen-waverley-hawks" / "data"
HOF = DATA / "processed" / "hall_of_fame"
VALIDATION = DATA / "processed" / "validation"

EXPECTED_PLAYERS = {
    "Greg Mccallum",
    "John Bennett",
    "Simon Laughton",
    "Matthew Silva",
    "Stephen Quinn",
    "Seddon Randall",
    "D Brady",
    "Greg Huntington",
    "Andrew Newman",
    "Glen Davies",
    "A Loucas",
    "Mehul Somaia",
    "David Huntington",
    "Scott Davies",
    "Chris Jackson",
    "Richard Emslie",
    "Drew Davidson",
    "Scott Perkins",
    "Darren Paulin",
    "Stuart Brady",
    "Tom Waters",
}


def authoritative_frame() -> pd.DataFrame:
    base = pd.read_csv(HOF / "prepared_career_all_time.csv", low_memory=False)
    batting = pd.read_csv(HOF / "prepared_career_batting.csv", low_memory=False)
    not_outs = batting[["canonical_player_id", "battingNotOuts"]].rename(columns={"battingNotOuts": "Not Outs"})
    return apply_record_overrides(base.merge(not_outs, on="canonical_player_id", how="left"), write_decisions=False)


def test_governed_source_contains_only_approved_metric_decisions() -> None:
    decisions = load_historical_career_metric_decisions()
    assert len(decisions) == 101
    assert set(decisions["canonical_player_name"]) == EXPECTED_PLAYERS
    assert decisions["canonical_player_id"].nunique() == 21
    assert decisions["metric"].value_counts().to_dict() == {
        "runs": 21,
        "wickets": 21,
        "batting_average": 21,
        "bowling_average": 21,
        "not_outs": 17,
    }
    assert not decisions["metric"].isin({"matches", "catches", "stumpings", "run_outs"}).any()


def test_full_career_value_replaces_instead_of_adding() -> None:
    source = load_historical_career_metric_decisions()
    player_id = source.iloc[0]["canonical_player_id"]
    sample = pd.DataFrame(
        [{"canonical_player_id": player_id, "Player": source.iloc[0]["canonical_player_name"], "Runs": 100.0, "Wickets": 2.0, "Bat Avg": 10.0, "Bowl Avg": 20.0, "Matches": 8.0, "Catches": 3.0}]
    )
    result = apply_historical_career_metric_decisions(sample)
    expected_runs = float(source[(source["canonical_player_id"].eq(player_id)) & source["metric"].eq("runs")].iloc[0]["authoritative_value"])
    assert result.iloc[0]["Runs"] == expected_runs
    assert result.iloc[0]["Runs"] != expected_runs + 100.0
    assert result.iloc[0]["Matches"] == 8.0
    assert result.iloc[0]["Catches"] == 3.0


def test_metric_replacements_and_averages_match_committed_audit() -> None:
    audit = pd.read_csv(VALIDATION / "gwhcc_career_total_reconciliation_audit.csv").fillna("")
    candidates = audit[audit["recommended_authority"].eq("CAREER_MASTER_REPLACEMENT")]
    authoritative = authoritative_frame()
    for row in candidates.itertuples(index=False):
        current = authoritative[authoritative["canonical_player_id"].astype(str).eq(row.canonical_player_id)].iloc[0]
        assert current["Runs"] == float(row.proposed_runs)
        assert current["Wickets"] == float(row.proposed_wickets)
        assert current["Matches"] == float(row.scorebook_matches)
        assert current["Catches"] == float(row.scorebook_catches)
        assert abs(current["Bat Avg"] - float(row.recalculated_career_master_batting_average)) < 0.001
        assert abs(current["Bowl Avg"] - float(row.recalculated_career_master_bowling_average)) < 0.001


def test_not_outs_are_replaced_only_for_the_17_approved_players() -> None:
    decisions = load_historical_career_metric_decisions()
    approved = set(decisions[decisions["metric"].eq("not_outs")]["canonical_player_id"])
    assert len(approved) == 17
    validation = pd.read_csv(VALIDATION / "gwhcc_fb17c_historical_career_validation.csv").fillna("")
    for row in validation.itertuples(index=False):
        if row.canonical_player_id in approved:
            assert row.not_outs_authority == "career_master"
        else:
            assert row.not_outs_authority == "playcricket_or_review"
            assert float(row.not_outs_after) == float(row.not_outs_before)


def test_hof_profile_and_match_milestone_validation_passes() -> None:
    validation = pd.read_csv(VALIDATION / "gwhcc_fb17c_historical_career_validation.csv").fillna("")
    assert len(validation) == 21
    assert validation["validation_status"].eq("PASS").all()
    assert validation["public_profile_count"].eq(1).all()
    assert validation["match_band_before"].astype(str).eq(validation["match_band_after"].astype(str)).all()


def test_closed_customer_decisions_and_private_filtering_remain_unchanged() -> None:
    frame = authoritative_frame()
    expected = {
        "Greg Mccormick": (427.0, 8664.0, 393.0, 87.0),
        "James Anderson": (108.0, 300.0, 3.0, 114.0),
        "Kashif Javed": (154.5, 3510.0, 6.0, 34.0),
    }
    for name, values in expected.items():
        row = frame[frame["Player"].astype(str).str.casefold().eq(name.casefold())].iloc[0]
        assert tuple(float(row[column]) for column in ["Matches", "Runs", "Wickets", "Catches"]) == values
    decisions = load_historical_career_metric_decisions()
    assert not decisions["canonical_player_name"].astype(str).str.contains(r"\*{2,}", regex=True).any()


def test_other_clubs_are_not_modified() -> None:
    sample = pd.DataFrame([{"canonical_player_id": "x", "Player": "A Player", "Runs": 10.0}])
    assert apply_historical_career_metric_decisions(sample, club_id="fvcc").equals(sample)
    assert apply_historical_career_metric_decisions(sample, club_id="georges-river-district").equals(sample)


def test_prepared_hof_rows_and_top_ten_membership_are_unchanged() -> None:
    audit = pd.read_csv(VALIDATION / "gwhcc_career_total_reconciliation_audit.csv").fillna("")
    candidates = audit[audit["recommended_authority"].eq("CAREER_MASTER_REPLACEMENT")]
    after = authoritative_frame()
    before = after.copy()
    for row in candidates.itertuples(index=False):
        mask = before["canonical_player_id"].astype(str).eq(row.canonical_player_id)
        before.loc[mask, "Runs"] = float(row.scorebook_runs)
        before.loc[mask, "Wickets"] = float(row.scorebook_wickets)
    assert len(after) == len(before) == 1233
    for metric in ["Matches", "Runs", "Wickets", "Catches"]:
        before_top = before.sort_values([metric, "Player"], ascending=[False, True]).head(10)["canonical_player_id"].tolist()
        after_top = after.sort_values([metric, "Player"], ascending=[False, True]).head(10)["canonical_player_id"].tolist()
        assert before_top == after_top
