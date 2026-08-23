from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "clubs" / "glen-waverley-hawks" / "data"
VALIDATION = DATA / "processed" / "validation"
HOF = DATA / "processed" / "hall_of_fame"
SOURCE = DATA / "source" / "document_overrides"


def identity_audit() -> pd.DataFrame:
    return pd.read_csv(VALIDATION / "gwhcc_career_master_identity_audit.csv").fillna("")


def total_audit() -> pd.DataFrame:
    return pd.read_csv(VALIDATION / "gwhcc_career_total_reconciliation_audit.csv").fillna("")


def test_all_career_master_rows_have_traceable_identity_decisions() -> None:
    audit = identity_audit()
    assert len(audit) == 881
    assert set(audit["identity_status"]) <= {"CONFIRMED", "HIGH_CONFIDENCE", "REVIEW", "UNRESOLVED", "CONFLICT"}
    assert audit["source_row"].nunique() == 881
    assert audit["evidence"].astype(str).str.strip().ne("").all()


def test_governed_priority_baselines_are_preserved() -> None:
    audit = identity_audit()
    assert audit["previous_identity_review"].astype(str).str.casefold().eq("true").sum() == 374
    assert audit["higher_total_case"].astype(str).str.casefold().eq("true").sum() == 314
    higher = audit[audit["higher_total_case"].astype(str).str.casefold().eq("true")]
    assert higher["higher_total_category"].ne("").all()


def test_closed_greg_james_and_kash_decisions_remain_playcricket() -> None:
    totals = total_audit()
    greg = totals[totals["player_name"].str.casefold().eq("greg mccormick")].iloc[0]
    assert greg["recommended_authority"] == "PLAYCRICKET"
    assert (greg["scorebook_matches"], greg["scorebook_runs"], greg["scorebook_wickets"], greg["scorebook_catches"]) == (427.0, 8664.0, 393.0, 87.0)

    james = totals[totals["player_name"].eq("James Anderson")].iloc[0]
    assert james["recommended_authority"] == "PLAYCRICKET"
    assert james["source_rows"] == "22;23"
    assert (james["scorebook_matches"], james["scorebook_runs"], james["scorebook_wickets"], james["scorebook_catches"]) == (108.0, 300.0, 3.0, 114.0)

    kash = totals[totals["source_names"].eq("JAVED.K")].iloc[0]
    assert kash["recommended_authority"] == "PLAYCRICKET"
    assert kash["player_name"] == "Kashif Javed"
    assert kash["scorebook_matches"] == 154.5


def test_fielding_and_match_policy_are_not_replaced_from_career_master() -> None:
    totals = total_audit()
    assert totals["catches_authority"].eq("PLAYCRICKET").all()
    assert not totals["matches_authority"].eq("CAREER_MASTER_REPLACEMENT").any()
    assert totals["career_master_catches"].astype(str).str.strip().eq("").all()


def test_source_anomalies_are_held_out_of_replacement_authority() -> None:
    totals = total_audit()
    chelvan = totals[totals["source_names"].eq("CHELVAN.A")].iloc[0]
    gondal = totals[totals["source_names"].eq("GONDAL.H")].iloc[0]
    assert chelvan["batting_average_quality_flag"] == "REVIEW"
    assert gondal["batting_average_quality_flag"] == "REVIEW"
    assert chelvan["recommended_authority"] != "CAREER_MASTER_REPLACEMENT"
    assert gondal["recommended_authority"] != "CAREER_MASTER_REPLACEMENT"


def test_historical_only_rows_are_not_created_as_production_identities() -> None:
    audit = identity_audit()
    historical = audit[audit["historical_only"].astype(str).str.casefold().eq("true")]
    assert len(historical) == 60
    assert historical["canonical_player_id"].eq("").all()
    assert historical["earliest_source_season"].ne("").all()


def test_simulation_does_not_change_production_baselines() -> None:
    assert len(pd.read_csv(HOF / "prepared_career_all_time.csv", low_memory=False)) == 1233
    assert len(pd.read_csv(SOURCE / "gwhcc_historical_centuries.csv")) == 65
    assert len(pd.read_csv(HOF / "premiership_wins.csv")) + len(pd.read_csv(SOURCE / "gwhcc_historical_premiership_events.csv")) == 53
    assert len(pd.read_csv(HOF / "partnership_records.csv")) == 10
    assert len(pd.read_csv(HOF / "hat_tricks.csv")) == 1
    assert len(pd.read_csv(HOF / "fastest_batting_milestones.csv")) == 780
