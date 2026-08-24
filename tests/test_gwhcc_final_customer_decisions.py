from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.gwhcc_document_overrides import load_document_player_aliases, parse_leading_player_records


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "clubs" / "glen-waverley-hawks" / "data" / "source" / "document_overrides"
PROCESSED = ROOT / "clubs" / "glen-waverley-hawks" / "data" / "processed"

def test_greg_decision_uses_approved_scorebook_totals() -> None:
    records = pd.read_csv(SOURCE / "gwhcc_record_overrides.csv")
    greg = records[records["player_name"].eq("G. McCormick")]
    assert dict(zip(greg["metric"], greg["document_value"])) == {"runs": 8664.0, "wickets": 393.0, "games": 427.0}
    assert greg["confidence"].eq("confirmed").all()
    assert greg["notes"].str.contains("Career Master alternatives remain retained evidence").all()

    extracted = pd.DataFrame(parse_leading_player_records("gwhcc_leading_players_source.pdf"))
    extracted_greg = extracted[extracted["player_name"].eq("G. McCormick")]
    assert extracted_greg["confidence"].eq("confirmed").all()


def test_james_customer_labels_resolve_to_one_existing_scorebook_identity() -> None:
    aliases = load_document_player_aliases("career")
    assert aliases["anderson j"] == "james anderson"
    assert aliases["anderson j c"] == "james anderson"

    source_ids = set()
    for category in ["batting", "bowling", "fielding"]:
        rows = pd.read_csv(PROCESSED / f"all_seasons_{category}.csv", low_memory=False)
        james = rows[rows["player_name"].astype(str).str.casefold().eq("james anderson")]
        source_ids.update(james["player_id"].dropna().astype(str))
    assert source_ids == {"7da2b1b9-d764-4449-a12b-db21c554ba9a"}


def test_kash_and_partnership_decisions_are_closed_without_data_overrides() -> None:
    decisions = pd.read_csv(SOURCE / "gwhcc_customer_decisions.csv")
    kash = decisions[decisions["entity"].eq("Kash Javed")].iloc[0]
    assert kash["status"] == "closed_no_issue"
    assert "GWHCC-only" in kash["decision"]
    partnership = decisions[decisions["entity"].eq("source hierarchy")].iloc[0]
    assert partnership["authoritative_source"] == "PlayCricket / scorecard"
