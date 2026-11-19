import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep

import pytest

from src.data import grdcc_profile_bundle as bundles
from src.data import hall_of_fame_prepared as prepared


@pytest.fixture
def fixture_bundle(tmp_path, monkeypatch):
    root = tmp_path / "data"
    source = root / "source" / "privacy.csv"
    source.parent.mkdir(parents=True)
    source.write_text("public", encoding="utf-8")
    processed = root / "processed"
    path = processed / "player_profile" / bundles.BUNDLE_FILENAME
    path.parent.mkdir(parents=True)
    (tmp_path / "src").mkdir()
    monkeypatch.setattr(bundles, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(prepared, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(bundles, "get_data_root", lambda club: root)
    monkeypatch.setattr(bundles, "get_processed_dir", lambda club: processed)
    monkeypatch.setattr(bundles, "get_mapping_dir", lambda club: root / "mapping")
    monkeypatch.delenv("SCOREBOOK_IGNORE_PREPARED_HOF", raising=False)
    bundles._build_grdcc_profile_bundle.clear()

    def write(*, public=True):
        path.write_text(json.dumps({
            "club": bundles.CLUB,
            "schema": 1,
            "sources": bundles.profile_content_signature(bundles.CLUB),
            "index": [["player", "Public Player"]] if public else [],
            "summaries": {"player": {"Runs": 0, "Wickets": None}} if public else {},
            "reportOnly": [],
        }), encoding="utf-8")

    write()
    yield source, write
    bundles._build_grdcc_profile_bundle.clear()


def test_privacy_edit_invalidates_same_size_and_mtime(fixture_bundle):
    source, write = fixture_bundle
    club = bundles.CLUB
    result = bundles.load_grdcc_profile_bundle(club)
    assert dict(result.summaries["player"]) == {"Runs": 0, "Wickets": None}
    with pytest.raises(TypeError):
        result.summaries["player"] = ()
    original = source.stat()
    source.write_text("masked", encoding="utf-8")
    os.utime(source, ns=(original.st_atime_ns, original.st_mtime_ns))
    assert bundles.load_grdcc_profile_bundle(club) is None
    write(public=False)
    assert bundles.load_grdcc_profile_bundle(club).index == ()


def test_source_and_governance_inventory_invalidates_on_addition_and_removal(fixture_bundle):
    source, write = fixture_bundle
    club = bundles.CLUB
    governance = bundles.REPO_ROOT / "src" / "new_privacy_rule.py"
    assert bundles.load_grdcc_profile_bundle(club) is not None
    governance.write_text("# rule\n", encoding="utf-8")
    assert bundles.load_grdcc_profile_bundle(club) is None
    write()
    assert bundles.load_grdcc_profile_bundle(club) is not None
    source.unlink()
    assert bundles.load_grdcc_profile_bundle(club) is None


def test_shared_preparation_runs_once_and_only_for_grdcc(fixture_bundle, monkeypatch):
    original = bundles.profile_content_signature
    calls = []

    def slow_signature(club):
        calls.append(club)
        sleep(0.05)
        return original(club)

    monkeypatch.setattr(bundles, "profile_content_signature", slow_signature)
    assert bundles.load_grdcc_profile_bundle("fvcc") is None
    assert bundles.load_grdcc_profile_bundle("glen-waverley-hawks") is None
    assert not calls

    ready = Barrier(2)

    def load():
        ready.wait(timeout=5)
        return bundles.load_grdcc_profile_bundle(bundles.CLUB)

    with ThreadPoolExecutor(max_workers=2) as executor:
        left, right = executor.submit(load), executor.submit(load)
        first, second = left.result(timeout=5), right.result(timeout=5)
    assert first is not None and first is second
    assert bundles.load_grdcc_profile_bundle(bundles.CLUB) is first
    assert calls == [bundles.CLUB]
    monkeypatch.setenv("SCOREBOOK_IGNORE_PREPARED_HOF", "1")
    assert bundles.load_grdcc_profile_bundle(bundles.CLUB) is None


def test_authority_reader_opens_only_all_time_table(tmp_path, monkeypatch):
    seen = []
    for name in prepared.FRAME_FILENAMES.values():
        (tmp_path / name).write_text("Runs\n225\n", encoding="utf-8")
    (tmp_path / prepared.GREATEST_SEASONS_FILENAME).write_text("{}", encoding="utf-8")
    original = prepared.pd.read_csv

    def read(path, **kwargs):
        seen.append(path.name)
        return original(path, **kwargs)

    monkeypatch.setattr(prepared.pd, "read_csv", read)
    monkeypatch.setattr(prepared, "_validated_prepared_directory", lambda *_: tmp_path)
    summary = prepared.load_prepared_hall_of_fame_all_time(bundles.CLUB, "version")
    assert seen == [prepared.FRAME_FILENAMES["all_time"]]
    seen.clear()
    full = prepared.load_prepared_hall_of_fame_core(bundles.CLUB, "version")
    assert seen == list(prepared.FRAME_FILENAMES.values())
    assert summary.equals(full["all_time"])


def test_unchanged_directory_plan_still_detects_nested_source_changes(fixture_bundle, monkeypatch):
    source, _ = fixture_bundle
    original = bundles.os.scandir
    visits = []

    def record(path):
        visits.append(path)
        return original(path)

    monkeypatch.setattr(bundles.os, "scandir", record)
    initial = bundles.profile_generation(bundles.CLUB)
    visits.clear()
    assert bundles.profile_generation(bundles.CLUB) == initial
    assert not visits
    directory = source.parent / "new_season"
    directory.mkdir()
    extra = directory / "coverage.csv"
    extra.write_text("coverage", encoding="utf-8")
    assert bundles.profile_generation(bundles.CLUB) != initial
    assert visits
    extra.unlink()
    directory.rmdir()
    assert bundles.profile_generation(bundles.CLUB) == initial


@pytest.mark.parametrize("replacement", ["removed", "directory", "file"])
def test_racing_directory_rejects_even_warm_snapshot(fixture_bundle, monkeypatch, replacement):
    source, _ = fixture_bundle
    assert bundles.load_grdcc_profile_bundle(bundles.CLUB) is not None
    racing = source.parent / "incoming"
    racing.mkdir()
    original = bundles.os.scandir
    attempted = []

    def scan(path):
        if path == racing and not attempted:
            attempted.append(True)
            racing.rmdir()
            if replacement == "directory":
                racing.mkdir()
            elif replacement == "file":
                racing.write_text("replaced", encoding="utf-8")
        return original(path)

    monkeypatch.setattr(bundles.os, "scandir", scan)
    assert bundles.load_grdcc_profile_bundle(bundles.CLUB) is None
    assert attempted
    assert bundles.load_grdcc_profile_bundle(bundles.CLUB) is not None


def test_membership_change_during_warm_file_stamps_rejects_cached_bundle(fixture_bundle, monkeypatch):
    source, _ = fixture_bundle
    assert bundles.load_grdcc_profile_bundle(bundles.CLUB) is not None
    original = bundles.file_stamp
    added = source.parent / "another.csv"

    def stamp(path):
        if path == source and not added.exists():
            added.write_text("new source", encoding="utf-8")
        return original(path)

    monkeypatch.setattr(bundles, "file_stamp", stamp)
    assert bundles.load_grdcc_profile_bundle(bundles.CLUB) is None
    assert not bundles._inventory_dirs
    assert bundles.load_grdcc_profile_bundle(bundles.CLUB) is None


def test_record_link_cache_keys_include_club_and_source_generation(monkeypatch):
    import pandas as pd
    from src.ui import layout

    club = ["fvcc"]
    calls = []

    def load(active_club):
        calls.append(active_club)
        return {"batting": pd.DataFrame({"revision": [len(calls)]})}

    monkeypatch.setattr(layout, "get_active_club_id", lambda: club[0])
    monkeypatch.setattr(layout, "load_deploy_scorecard_record_rows", load)
    layout.load_scorecard_record_rows.clear()
    for active_club, generation, revision in [
        ("fvcc", "one", 1), ("fvcc", "one", 1), ("fvcc", "two", 2),
        ("georges-river-district", "two", 3),
    ]:
        club[0] = active_club
        assert layout.load_scorecard_record_rows((generation,))["batting"].revision.tolist() == [revision]
    layout.load_scorecard_record_rows.clear()
