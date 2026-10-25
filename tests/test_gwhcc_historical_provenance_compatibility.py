from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path

import pandas as pd
import pytest

from src.data import gwhcc_document_overrides as documents
from src.data import gwhcc_historical_career as history

ROOT = Path(__file__).resolve().parents[1]
HOF = ROOT / "clubs/glen-waverley-hawks/data/processed/hall_of_fame"
METRICS = ["runs", "innings", "not_outs", "batting_average", "wickets", "bowling_runs", "bowling_average"]
NUMERIC = ["Runs", "Innings", "Not Outs", "Bat Avg", "Wickets", "Runs Against", "Bowl Avg", "Outs"]


@pytest.fixture(scope="module")
def career_frame():
    frame = pd.read_csv(HOF / "prepared_career_all_time.csv")
    batting = pd.read_csv(HOF / "prepared_career_batting.csv")
    return frame.merge(
        batting[["canonical_player_id", "battingNotOuts"]].rename(columns={"battingNotOuts": "Not Outs"}),
        on="canonical_player_id", validate="one_to_one",
    )


def typed_provenance(frame, dtype):
    result = frame.copy()
    columns = [f"{metric}_authority_{suffix}" for metric in METRICS for suffix in ["source", "scope", "source_row"]]
    columns += ["historical_career_anchor_through_season", "historical_career_anchor_metric_scope",
                "historical_career_anchor_source", "historical_career_batting_anchor_through_season",
                "historical_career_bowling_anchor_through_season", "runs_value_source", "wickets_value_source"]
    for column in columns:
        values = result[column] if column in result else pd.Series("", index=result.index)
        result[column] = values.astype(dtype)
    return result


def assert_all_approved_anchors(result):
    actual = result.set_index("canonical_player_id")
    anchors = history.load_dated_career_anchors()
    assert len(anchors) == 63
    assert set(anchors.metric_scope.dropna()) >= {"batting", "bowling", "batting;bowling"}
    assert result.canonical_player_id.is_unique and len(result) == 1291
    assert set(anchors.canonical_player_id).issubset(set(result.canonical_player_id))
    for anchor in anchors.to_dict("records"):
        player = actual.loc[anchor["canonical_player_id"]]
        scopes = history.anchor_scopes(anchor)
        selected = {metric for scope in scopes for metric in history.SOURCE_COLUMNS[scope]}
        selected |= ({"batting_average"} if "batting" in scopes else set())
        selected |= ({"bowling_average"} if "bowling" in scopes else set())
        for metric in selected:
            value = player[f"{metric}_authority_source_row"]
            assert isinstance(value, str)
            assert value == str(anchor["source_row"])
            assert int(value) == anchor["source_row"]


@pytest.mark.parametrize("dtype", ["object", "string[python]", "string[pyarrow]"])
def test_all_63_anchors_accept_string_provenance_without_changing_statistics(career_frame, dtype):
    prepared = documents.apply_historical_career_metric_decisions(documents.apply_historical_career_supplements(career_frame))
    frame = typed_provenance(prepared, dtype)
    before = frame.copy(deep=True)
    expected = history.apply_dated_career_anchors(prepared)
    actual = history.apply_dated_career_anchors(frame)
    assert_all_approved_anchors(actual)
    pd.testing.assert_frame_equal(actual[NUMERIC], expected[NUMERIC], check_dtype=False)
    pd.testing.assert_frame_equal(frame, before)
    untouched = ~frame.canonical_player_id.isin(history.load_dated_career_anchors().canonical_player_id)
    pd.testing.assert_frame_equal(frame.loc[untouched], actual.loc[untouched, frame.columns], check_dtype=False)
    for column in frame.columns:
        if column.endswith("_authority_source_row"):
            assert actual[column].dtype == frame[column].dtype
    twice = history.apply_dated_career_anchors(actual)
    pd.testing.assert_frame_equal(twice[NUMERIC], actual[NUMERIC])
    provenance = [column for column in actual if "_authority_" in column]
    pd.testing.assert_frame_equal(twice[provenance], actual[provenance])


@pytest.mark.parametrize("dtype", ["object", "string[python]", "string[pyarrow]", "inferred_arrow"])
def test_complete_hof_authoritative_path_preserves_all_governed_values(career_frame, dtype, monkeypatch):
    from src.ui import layout

    monkeypatch.setenv("CLUB_ID", history.CLUB_ID)
    # Only table I/O is substituted; featured, document, FB17C, dated and public gates all execute.
    frame = career_frame.copy() if dtype == "inferred_arrow" else typed_provenance(career_frame, dtype)
    monkeypatch.setattr(layout, "load_hall_of_fame_data", lambda *args, **kwargs: {"all_time": frame})
    context = pd.option_context("future.infer_string", True) if dtype == "inferred_arrow" else nullcontext()
    with context:
        actual = layout.get_authoritative_career_totals.__wrapped__(0, club_id=history.CLUB_ID)
        assert_all_approved_anchors(actual)
    expected = documents.apply_record_overrides(career_frame, write_decisions=False)
    pd.testing.assert_frame_equal(actual[NUMERIC], expected[NUMERIC], check_dtype=False, check_column_type=False)
    for name, runs, wickets in [("Anthony Medina", 1575, 62), ("Shivo Arivalakan", 44, 17)]:
        player = actual[actual.Player.eq(name)].iloc[0]
        assert (player.Runs, player.Wickets) == (runs, wickets)
    assert not actual.Player.isin(["Private player", "T. Medina"]).any()


@pytest.mark.parametrize("club_id", ["fvcc", "georges-river-district"])
def test_arrow_provenance_does_not_affect_other_clubs(career_frame, club_id):
    frame = typed_provenance(career_frame, "string[pyarrow]")
    pd.testing.assert_frame_equal(history.apply_dated_career_anchors(frame, club_id=club_id), frame)


def test_source_row_remains_numeric_in_governed_inputs():
    for path in [history.ANCHORS, history.VERIFIED_ANCHORS]:
        source = pd.read_csv(path)
        assert pd.api.types.is_integer_dtype(source.source_row)
        assert source.source_row.gt(0).all()
