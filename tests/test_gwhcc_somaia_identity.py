from __future__ import annotations

import io
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from scripts.reconcile_gwhcc_somaia import CANONICAL, SOURCE_KEYS, SOURCE_NAMES, verify_disjoint_source_evidence
from scripts.build_gwhcc_weekly_candidate import approved_redirects, canonicalise_summary, summary_specs
from src.data.gwhcc_identity import NAME_VARIANT_APPROVAL, canonical_query_name, player_search_label
from src.utils.player_identity import apply_player_identity_mapping, resolve_approved_disjoint_player_id, public_player_mask

ROOT = Path(__file__).resolve().parents[1]
CLUB = "glen-waverley-hawks"
DATA = ROOT / "clubs" / CLUB / "data"
BASELINE = "49a148cf02e4307bdf37b465b7c538603c1e413d"


def before(path):
    value = subprocess.check_output(["git", "show", f"{BASELINE}:{path.relative_to(ROOT)}"], cwd=ROOT)
    return pd.read_csv(io.BytesIO(value), low_memory=False)


def read(relative):
    return pd.read_csv(DATA / "processed" / relative, low_memory=False)


@pytest.fixture
def decisions():
    frame = pd.read_csv(DATA / "source/disjoint_season_identity_decisions.csv")
    return frame[frame.decision.eq(NAME_VARIANT_APPROVAL)]


@pytest.fixture
def public(monkeypatch):
    from src.ui import layout
    from src.data.gwhcc_document_overrides import apply_record_overrides
    monkeypatch.setenv("CLUB_ID", CLUB)
    frame = apply_record_overrides(read("hall_of_fame/prepared_career_all_time.csv"), write_decisions=False)
    return layout.add_gwhcc_not_outs_for_display(frame, read("hall_of_fame/prepared_career_batting.csv"))


def test_only_two_explicit_ids_merge_and_legacy_routes_survive(decisions):
    assert set(decisions.raw_player_id) == set(SOURCE_NAMES)
    assert set(decisions.canonical_player_id) == {CANONICAL}
    assert set(decisions.canonical_player_name) == {"Sunil Somaia"}
    for value in [*SOURCE_NAMES, *SOURCE_KEYS]:
        assert resolve_approved_disjoint_player_id(value, club_id=CLUB) == CANONICAL
        for club in ("fvcc", "georges-river-district"):
            assert resolve_approved_disjoint_player_id(value, club_id=club) == value
    sample = pd.DataFrame({"player_id": [*SOURCE_NAMES, "unknown-person"],
                           "player_name": [*SOURCE_NAMES.values(), "Sunny Somaia"]})
    mapped = apply_player_identity_mapping(sample, club_id=CLUB)
    assert mapped.iloc[:2].canonical_player_id.eq(CANONICAL).all()
    assert mapped.iloc[2].canonical_player_id != CANONICAL


@pytest.mark.parametrize("query", ["Sunny", "Somaia", "Sunny Somaia"])
def test_search_aliases_offer_one_public_canonical_option(monkeypatch, query):
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", CLUB)
    frame = read("hall_of_fame/prepared_career_all_time.csv")
    names = layout.detailed_record_public_player_options({"all_time": frame})
    matches = layout.filter_detailed_record_player_suggestions(names, query)
    assert matches.count("Sunil Somaia") == 1
    assert "Sunny Somaia" not in matches
    assert player_search_label("Sunil Somaia", CLUB) == "Sunny Somaia"
    assert canonical_query_name("sunny somaia", CLUB) == "Sunil Somaia"
    assert player_search_label("Sunil Somaia", "fvcc") == "Sunil Somaia"
    assert canonical_query_name("Sunny Somaia", "georges-river-district") == "Sunny Somaia"
    monkeypatch.setattr(layout, "query_param_value", lambda key: "Sunny Somaia" if key == "player" else "")
    assert layout.resolve_player_query_to_id({CANONICAL: "Sunil Somaia"}) == CANONICAL
    assert layout.resolve_player_query_to_id({}) == ""


@pytest.mark.parametrize("kind", ["batting", "bowling", "fielding"])
def test_all_source_contributions_and_unrelated_players_are_unchanged(kind):
    path = DATA / f"processed/all_seasons_{kind}.csv"
    old, new = before(path), pd.read_csv(path, low_memory=False)
    identity = ["canonical_player_id", "canonical_player_name"]
    pd.testing.assert_frame_equal(old.drop(columns=identity), new.drop(columns=identity))
    affected = old.raw_player_id.isin(SOURCE_NAMES)
    pd.testing.assert_frame_equal(old[~affected], new[~affected])
    assert new.loc[affected, "canonical_player_id"].eq(CANONICAL).all()
    assert new.loc[affected, "canonical_player_name"].eq("Sunil Somaia").all()
    cards = DATA / f"processed/all_seasons_scorecard_{kind}.csv"
    assert cards.read_bytes() == subprocess.check_output(["git", "show", f"{BASELINE}:{cards.relative_to(ROOT)}"], cwd=ROOT)


def test_source_overlap_is_quarantined_and_multi_innings_evidence_is_retained():
    aggregates = {kind: read(f"all_seasons_{kind}.csv") for kind in ("batting", "bowling", "fielding")}
    cards = {kind: read(f"all_seasons_scorecard_{kind}.csv") for kind in aggregates}
    verify_disjoint_source_evidence(aggregates, cards)
    old, new = SOURCE_NAMES
    batting = cards["batting"][cards["batting"].player_id.eq(old)]
    assert len(batting) > batting.match_id.nunique()  # Distinct innings are not match-only duplicates.
    overlap = cards["batting"].iloc[[0]].copy()
    overlap["player_id"] = new
    overlap["match_id"] = batting.match_id.iloc[0]
    with pytest.raises(ValueError, match="Overlapping scorecards"):
        verify_disjoint_source_evidence(aggregates, {"batting": pd.concat([cards["batting"], overlap])})
    duplicate = aggregates["batting"][aggregates["batting"].raw_player_id.eq(old)].iloc[[0]]
    with pytest.raises(ValueError, match="Duplicate source aggregate"):
        verify_disjoint_source_evidence({"batting": pd.concat([aggregates["batting"], duplicate])}, cards)


def test_public_career_rates_and_historical_hundreds_reconcile(public):
    row = public[public.canonical_player_id.eq(CANONICAL)]
    assert len(row) == 1 and row.iloc[0].Player == "Sunil Somaia"
    row = row.iloc[0]
    expected = {"Matches": 274, "Runs": 8391, "Innings": 280, "50s": 34, "100s": 21,
                "Wickets": 26, "Catches": 80, "Stumpings": 28, "Run Outs": 12, "Dismissals": 120}
    for metric, value in expected.items():
        assert row[metric] == value
    assert row["Bat Avg"] == pytest.approx(8391 / (280 - 31))
    assert row["Bowl Avg"] == pytest.approx(552 / 26)
    assert str(row.HS) == "160" and row.BBI == "5-46"
    batting = read("all_seasons_batting.csv")
    batting = batting[batting.raw_player_id.isin(SOURCE_NAMES)]
    assert batting.season.nunique() == 28
    assert batting.battingAggregate.sum() == 8391
    assert batting.battingInnings.sum() == 280
    assert batting.battingNotOuts.sum() == 31
    assert batting.matches.sum() == 274
    history = pd.read_csv(DATA / "source/document_overrides/gwhcc_historical_centuries.csv")
    assert len(history[history.canonical_player_id.eq(CANONICAL)]) == 3
    milestones = read("hall_of_fame/player_scorecard_milestones.csv")
    assert milestones.loc[milestones.canonical_player_id.eq(CANONICAL), "hundreds"].tolist() == [18]


def test_prepared_frames_conserve_all_unrelated_players_and_manifest(monkeypatch):
    from src.data.hall_of_fame_prepared import FRAME_FILENAMES, load_prepared_hall_of_fame_core
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", CLUB)
    prepared = load_prepared_hall_of_fame_core(CLUB, layout.HALL_OF_FAME_DATA_VERSION)
    assert prepared is not None
    for kind, name in FRAME_FILENAMES.items():
        path = DATA / "processed/hall_of_fame" / name
        old, new = before(path), pd.read_csv(path, low_memory=False)
        assert len(new) == len(old) - 1
        assert new.canonical_player_id.is_unique and public_player_mask(new).all()
        pd.testing.assert_frame_equal(old[~old.canonical_player_id.isin(SOURCE_KEYS)].reset_index(drop=True),
                                      new[~new.canonical_player_id.eq(CANONICAL)].reset_index(drop=True))
    assert len(prepared["all_time"]) == 1284


def test_partnership_evidence_and_privacy_unchanged():
    for relative in ("partnerships/partnership_events.csv", "hall_of_fame/partnership_records.csv"):
        path = DATA / "processed" / relative
        old, new = before(path), read(relative)
        identity = ["player_1_canonical_id", "player_2_canonical_id", "player_1_name", "player_2_name"]
        pd.testing.assert_frame_equal(old.drop(columns=identity), new.drop(columns=identity))
        for position in (1, 2):
            private = new[f"player_{position}_name"].eq("Private player")
            assert new.loc[private, f"player_{position}_canonical_id"].isna().all()
            affected = old[f"player_{position}_canonical_id"].isin(SOURCE_KEYS)
            assert new.loc[affected, f"player_{position}_name"].eq("Sunil Somaia").all()


def test_fastest_evidence_keeps_source_identity_and_all_delivery_metrics():
    path = DATA / "processed/hall_of_fame/fastest_batting_milestones.csv"
    old, new = before(path), pd.read_csv(path)
    pd.testing.assert_frame_equal(old.drop(columns="canonical_player_name"), new.drop(columns="canonical_player_name"))
    affected = old.player_id.isin(SOURCE_NAMES)
    assert affected.sum() == 19
    assert new.loc[affected, "canonical_player_name"].eq("Sunil Somaia").all()


def test_future_refresh_uses_approved_variant_and_combined_denominators(decisions):
    assert set(approved_redirects(decisions).values()) == {CANONICAL}
    frame = pd.DataFrame({"canonical_player_id": list(decisions.previous_canonical_id),
                          "canonical_player_name": ["Sunny Somaia", "Sunil Somaia"],
                          "position_group": ["Top", "Top"], "innings": [2, 3],
                          "runs": [10, 60], "outs": [1, 2], "average": [10, 30]})
    merged = canonicalise_summary(frame, decisions, summary_specs()["player_profile/batting_position_summary.csv"], "batting_position_summary.csv")
    assert len(merged) == 1
    assert merged.iloc[0].canonical_player_name == "Sunil Somaia"
    assert merged.iloc[0].average == pytest.approx(70 / 3)
    bad = decisions.copy()
    bad["decision"] = "review"
    with pytest.raises(ValueError, match="explicitly approved"):
        approved_redirects(bad)


def test_breakdown_contributions_and_premiership_evidence_conserved():
    path = DATA / "processed/player_profile/performance_breakdown_by_dimension.csv"
    old, new = before(path), pd.read_csv(path, low_memory=False)
    metrics = ["innings", "runs", "outs", "wickets", "runs_against", "balls_bowled", "catches", "stumpings", "run_outs"]
    pd.testing.assert_frame_equal(old.groupby(["dimension", "discipline"])[metrics].sum(),
                                  new.groupby(["dimension", "discipline"])[metrics].sum())
    unaffected = ~old.canonical_player_id.isin(SOURCE_KEYS)
    pd.testing.assert_frame_equal(old[unaffected].reset_index(drop=True),
                                  new[~new.canonical_player_id.eq(CANONICAL)].reset_index(drop=True))
    path = DATA / "processed/hall_of_fame/player_premierships.csv"
    old, new = before(path), pd.read_csv(path)
    assert old.premiership_count.sum() == new.premiership_count.sum()
    assert new.loc[new.canonical_player_id.eq(CANONICAL), "premiership_count"].tolist() == [5]
    evidence = lambda frame: sorted(m.strip() for value in frame.evidence_match_ids for m in value.split(","))
    assert evidence(old) == evidence(new)


def test_other_governed_career_anchors(public):
    expected = {"Greg McCormick": (427, 8664, 393, 87), "James Anderson": (108, 300, 3, 114),
                "Ahilan Sivakumaran": (132, 3414, 45, 83)}
    for name, values in expected.items():
        row = public[public.Player.str.strip().str.casefold().eq(name.casefold())]
        assert len(row) == 1
        assert tuple(row.iloc[0][["Matches", "Runs", "Wickets", "Catches"]]) == values
    assert public.loc[public.Player.str.strip().eq("Kashif Javed"), "Matches"].tolist() == [154.5]
    assert public.loc[public.Player.eq("Glen Mahoney"), "Runs"].tolist() == [7734]
