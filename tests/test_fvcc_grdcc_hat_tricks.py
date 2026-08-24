from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.data.hat_tricks import (
    GovernedHatTrickBuildResult,
    build_governed_club_hat_tricks,
    write_governed_hat_trick_outputs,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def governed_builds() -> dict[str, GovernedHatTrickBuildResult]:
    return {
        "fvcc": build_governed_club_hat_tricks(
            club_id="fvcc",
            match_centre_root=ROOT / "data" / "processed" / "match_centre",
            club_processed_root=ROOT / "clubs" / "fvcc" / "data" / "processed",
        ),
        "grdcc": build_governed_club_hat_tricks(
            club_id="georges-river-district",
            match_centre_root=ROOT / "data" / "processed" / "match_centre" / "georges-river-district",
            club_processed_root=ROOT / "clubs" / "georges-river-district" / "data" / "processed",
        ),
    }


def test_fvcc_governed_rebuild_has_no_candidate(governed_builds) -> None:
    result = governed_builds["fvcc"]
    coverage = result.coverage.iloc[0]
    assert coverage["source_matches"] == 961
    assert coverage["club_scorecard_matches"] == 843
    assert coverage["source_matches_with_ball_by_ball"] == 101
    assert coverage["source_delivery_rows"] == 50379
    assert coverage["candidate_sequences"] == 0
    assert result.events.empty


def test_grdcc_governed_rebuild_confirms_four_canonical_records(governed_builds) -> None:
    result = governed_builds["grdcc"]
    coverage = result.coverage.iloc[0]
    assert coverage["source_matches"] == 2604
    assert coverage["club_scorecard_matches"] == 2167
    assert coverage["source_matches_with_ball_by_ball"] == 295
    assert coverage["source_delivery_rows"] == 155573
    assert coverage["candidate_sequences"] == 4
    assert coverage["confirmed_candidates"] == 4
    assert set(result.events["canonical_player_name"]) == {
        "Bagath Singh",
        "Daniel Yates",
        "Leroy Maurer",
        "Tom Jeffrey",
    }
    assert result.events["canonical_player_id"].astype(str).str.startswith("raw_").all()
    assert result.events["confidence"].eq("high").all()


def test_grdcc_missing_bowler_evidence_cannot_affect_confirmed_records(governed_builds) -> None:
    result = governed_builds["grdcc"]
    assert len(result.source_issues) == 23
    assert result.source_issues["classification"].value_counts().to_dict() == {"C": 22, "D": 1}
    assert not result.source_issues["affects_confirmed_candidate"].any()
    assert result.validation["status"].ne("FAIL").all()


def test_governed_outputs_are_reproducible(governed_builds, tmp_path) -> None:
    result = governed_builds["grdcc"]
    outputs = []
    for name in ["first", "second"]:
        root = tmp_path / name
        write_governed_hat_trick_outputs(
            result,
            hall_of_fame_output=root / "hat_tricks.csv",
            validation_dir=root / "validation",
            prefix="grdcc",
        )
        outputs.append(root)
    first_files = sorted(path.relative_to(outputs[0]) for path in outputs[0].rglob("*.csv"))
    second_files = sorted(path.relative_to(outputs[1]) for path in outputs[1].rglob("*.csv"))
    assert first_files == second_files
    for relative in first_files:
        assert (outputs[0] / relative).read_bytes() == (outputs[1] / relative).read_bytes()


def test_public_output_never_contains_masked_names(governed_builds) -> None:
    for result in governed_builds.values():
        names = result.events.get("canonical_player_name", pd.Series(dtype=str)).astype(str)
        assert not names.str.contains(r"\*{2,}", regex=True).any()
