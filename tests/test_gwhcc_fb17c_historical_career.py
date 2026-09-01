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


def test_governed_replacements_recompute_hof_top_ten_without_double_counting() -> None:
    audit = pd.read_csv(VALIDATION / "gwhcc_career_total_reconciliation_audit.csv").fillna("")
    candidates = audit[audit["recommended_authority"].eq("CAREER_MASTER_REPLACEMENT")]
    after = authoritative_frame()
    before = after.copy()
    for row in candidates.itertuples(index=False):
        mask = before["canonical_player_id"].astype(str).eq(row.canonical_player_id)
        before.loc[mask, "Runs"] = float(row.scorebook_runs)
        before.loc[mask, "Wickets"] = float(row.scorebook_wickets)
    assert len(after) == len(before) == 1233

    def ranked(frame: pd.DataFrame, metric: str) -> pd.DataFrame:
        return frame.sort_values([metric, "Player"], ascending=[False, True]).reset_index(drop=True)

    def rank_for(frame: pd.DataFrame, metric: str, player_id: str) -> int:
        ranking = ranked(frame, metric)
        return int(ranking.index[ranking["canonical_player_id"].astype(str).eq(player_id)][0]) + 1

    decisions = load_historical_career_metric_decisions()
    stephen_id = "raw_2ecad9ed_3966_4cba_85f3_644b5191db5c"
    chris_id = "raw_b42006f6_92c7_4345_ae8b_c7b7080cac2c"
    stephen = after[after["canonical_player_id"].astype(str).eq(stephen_id)].iloc[0]
    chris = after[after["canonical_player_id"].astype(str).eq(chris_id)].iloc[0]
    stephen_audit = candidates[candidates["canonical_player_id"].eq(stephen_id)].iloc[0]
    chris_audit = candidates[candidates["canonical_player_id"].eq(chris_id)].iloc[0]
    stephen_decision = decisions[(decisions["canonical_player_id"].eq(stephen_id)) & decisions["metric"].eq("runs")].iloc[0]
    chris_decision = decisions[(decisions["canonical_player_id"].eq(chris_id)) & decisions["metric"].eq("wickets")].iloc[0]

    assert float(stephen["Runs"]) == float(stephen_decision["authoritative_value"]) == 4921.0
    assert float(stephen["Runs"]) != float(stephen_audit["scorebook_runs"]) + float(stephen_decision["authoritative_value"])
    assert float(chris["Wickets"]) == float(chris_decision["authoritative_value"]) == 248.0
    assert float(chris["Wickets"]) != float(chris_audit["scorebook_wickets"]) + float(chris_decision["authoritative_value"])

    assert rank_for(before, "Runs", stephen_id) == 16
    assert rank_for(after, "Runs", stephen_id) == 10
    assert rank_for(before, "Wickets", chris_id) == 57
    assert rank_for(after, "Wickets", chris_id) == 10
    assert rank_for(after, "Runs", "paul_young") == 11
    assert rank_for(after, "Wickets", "raw_e8f5b374_e618_4735_9419_cc4e8c4511e8") == 11

    assert ranked(after, "Runs").head(10)["Player"].tolist() == [
        "Greg Mccormick",
        "Glen Mahoney",
        "Sunny Somaia",
        "Stuart Wynd",
        "Apurwa Sarve",
        "Chris Briginshaw",
        "Brooke Calder",
        "Grant Haye",
        "Jarrod Greaves",
        "Stephen Quinn",
    ]
    assert ranked(after, "Wickets").head(10)["Player"].tolist() == [
        "Matthew Briginshaw",
        "Greg Mccormick",
        "Nathan Bungey",
        "Luke Galle",
        "Arun Chelvan",
        "Stuart Wynd",
        "Chris Perkins",
        "Patrick Eldridge",
        "Shane Vanin",
        "Chris Jackson",
    ]
    assert float(after.loc[after["Player"].eq("Glen Mahoney"), "Runs"].iloc[0]) == 7734.0
    assert after["canonical_player_id"].nunique() == before["canonical_player_id"].nunique()
