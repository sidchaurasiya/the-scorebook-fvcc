from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd

from src.data import hall_of_fame_prepared as prepared
from src.ui import layout


CLUB_ID = "georges-river-district"
HOF_DIR = Path("clubs/georges-river-district/data/processed/hall_of_fame")
DATA_VERSION = layout.HALL_OF_FAME_DATA_VERSION


def load_core() -> dict[str, object]:
    core = prepared.load_prepared_hall_of_fame_core(CLUB_ID, DATA_VERSION)
    assert core is not None
    return core


def test_valid_manifest_loads_all_grdcc_frames() -> None:
    core = load_core()

    assert len(core["batting"]) == 2041
    assert len(core["bowling"]) == 1720
    assert len(core["fielding"]) == 1566
    assert len(core["all_time"]) == 2063


def test_missing_prepared_output_falls_back(tmp_path, monkeypatch) -> None:
    for path in HOF_DIR.glob("prepared_*"):
        shutil.copy2(path, tmp_path / path.name)
    (tmp_path / "prepared_career_batting.csv").unlink()
    monkeypatch.setattr(prepared, "get_hall_of_fame_dir", lambda club_id=None: tmp_path)

    assert prepared.load_prepared_hall_of_fame_core(CLUB_ID, DATA_VERSION) is None


def test_source_signature_mismatch_rejects_prepared_output(tmp_path, monkeypatch) -> None:
    for path in HOF_DIR.glob("prepared_*"):
        shutil.copy2(path, tmp_path / path.name)
    manifest_path = tmp_path / prepared.MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_signature"] = [{"path": "tampered", "size": 1, "sha256": "tampered"}]
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(prepared, "get_hall_of_fame_dir", lambda club_id=None: tmp_path)

    assert prepared.load_prepared_hall_of_fame_core(CLUB_ID, DATA_VERSION) is None


def test_policy_version_mismatch_rejects_prepared_output() -> None:
    assert prepared.load_prepared_hall_of_fame_core(CLUB_ID, f"{DATA_VERSION}-stale") is None


def test_prepared_canonical_player_ids_are_unique() -> None:
    frame = load_core()["all_time"]

    assert not frame["canonical_player_id"].duplicated().any()


def test_prepared_all_time_has_major_hof_metrics() -> None:
    frame = load_core()["all_time"]

    assert {"Runs", "Wickets", "Matches", "Catches"}.issubset(frame.columns)


def test_annual_report_overrides_apply_after_prepared_load() -> None:
    core = load_core()
    visible = layout.apply_featured_record_overrides(core["all_time"].copy(), club_id=CLUB_ID)

    harry = visible.loc[visible["Player"].astype(str).str.casefold() == "harry milburn", "Runs"].iloc[0]
    gordon = visible.loc[visible["Player"].astype(str).str.casefold() == "gordon leslie", "Wickets"].iloc[0]
    assert float(harry) == 10788
    assert float(gordon) == 707


def test_historical_supplement_paths_are_fingerprinted() -> None:
    paths = {path.name for path in prepared.prepared_core_source_paths(CLUB_ID)}

    assert "excel_all_seasons_batting.csv" in paths
    assert "excel_all_seasons_bowling.csv" in paths
    assert "excel_player_season_summary.csv" not in paths


def test_not_out_and_proxy_fields_survive_core_serialization() -> None:
    core = load_core()
    frame = layout.apply_featured_record_overrides(core["all_time"].copy(), club_id=CLUB_ID)

    assert "Matches Proxy" in frame.columns
    assert "battingNotOuts" in core["batting"].columns


def test_active_players_remain_runtime_derived_from_latest_two_seasons(monkeypatch) -> None:
    monkeypatch.setenv("CLUB_ID", CLUB_ID)
    activity = pd.DataFrame(
        {
            "season": ["Summer 2025/26", "Summer 2024/25", "Summer 2022/23"],
            "canonical_player_name": ["Current Player", "Current Player", "Stale Player"],
            "team_name": ["GRDCC", "GRDCC", "GRDCC"],
        }
    )

    active = layout.active_hof_players(
        {"batting_raw": activity, "bowling_raw": pd.DataFrame(), "fielding_raw": pd.DataFrame()}
    )

    assert active == {"current player"}


def test_prepared_core_does_not_freeze_active_markers() -> None:
    core = load_core()

    assert "active" not in {str(column).casefold() for column in core["all_time"].columns}


def test_prepared_core_does_not_add_privacy_display_fields() -> None:
    core = load_core()
    all_time = core["all_time"]

    assert "Private player" not in all_time.astype(str).to_string()
    assert layout.is_private_or_anonymised_player("********")


def test_valid_prepared_loader_reads_snapshot_without_runtime_builder(monkeypatch) -> None:
    def fail_if_called(*args, **kwargs):
        raise AssertionError("runtime HOF builder should not be called by prepared loader")

    monkeypatch.setattr(layout, "build_all_time_player_table", fail_if_called)
    assert prepared.load_prepared_hall_of_fame_core(CLUB_ID, DATA_VERSION) is not None
