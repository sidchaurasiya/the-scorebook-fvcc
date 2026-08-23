from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import app_version
from src.data.gwhcc_document_overrides import load_document_player_aliases, parse_leading_player_records
from src.ui import layout


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "clubs" / "glen-waverley-hawks" / "data" / "source" / "document_overrides"
PROCESSED = ROOT / "clubs" / "glen-waverley-hawks" / "data" / "processed"


def test_version_identifier_prefers_environment_and_has_safe_fallback(monkeypatch, tmp_path) -> None:
    app_version.scorebook_build_identifier.cache_clear()
    monkeypatch.setenv("SCOREBOOK_BUILD_SHA", "1234567890abcdef")
    assert app_version.scorebook_build_identifier(tmp_path) == "1234567"

    app_version.scorebook_build_identifier.cache_clear()
    for key in app_version.BUILD_ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(app_version.subprocess, "run", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("git unavailable")))
    assert app_version.scorebook_build_identifier(tmp_path) == "unavailable"
    app_version.scorebook_build_identifier.cache_clear()


def test_version_footer_is_visible_only_for_gwhcc(monkeypatch) -> None:
    monkeypatch.setattr(layout, "scorebook_version_label", lambda *_args: "Scorebook GWHCC | Release: v1.0.0 | Build: abc1234")
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "glen-waverley-hawks")
    assert "Scorebook GWHCC" in layout.scorebook_version_footer_html()
    assert "abc1234" in layout.scorebook_version_footer_html()

    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")
    assert layout.scorebook_version_footer_html() == ""


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
