import pandas as pd
import pytest

from scripts import build_player_profile_insight_exports as exporter


PAYING_CLUBS = ("georges-river-district", "glen-waverley-hawks")


@pytest.fixture
def profile_output(monkeypatch, tmp_path):
    output = tmp_path / "player_profile"
    monkeypatch.setattr(exporter, "get_player_profile_dir", lambda **_: output)
    monkeypatch.setattr(exporter, "OUTPUT_DIR", output)
    return output


def unexpected_source_load(**_):
    pytest.fail("This command must exit before loading its source scopes")


@pytest.mark.parametrize("club", PAYING_CLUBS)
@pytest.mark.parametrize("options", [[], ["--performance-breakdown-only"], ["--legacy-output"]])
def test_generic_paying_club_export_exits_before_creating_output(
    monkeypatch, profile_output, club, options,
):
    monkeypatch.setattr(exporter, "load_player_profile_scopes", unexpected_source_load)

    with pytest.raises(SystemExit, match=rf"{club}: generic profile export is unsafe"):
        exporter.main(["--club", club, *options])

    assert not profile_output.exists()


@pytest.mark.parametrize("club", PAYING_CLUBS)
def test_paying_club_export_leaves_existing_profile_files_intact(monkeypatch, profile_output, club):
    monkeypatch.setattr(exporter, "load_player_profile_scopes", unexpected_source_load)
    profile_output.mkdir()
    originals = {name: f"reviewed,{name}\n".encode() for name in exporter.OUTPUT_FILENAMES}
    for name, original in originals.items():
        (profile_output / name).write_bytes(original)

    with pytest.raises(SystemExit, match=rf"{club}: generic profile export is unsafe"):
        exporter.main(["--club", club])

    assert {p.name: p.read_bytes() for p in profile_output.iterdir()} == originals


@pytest.mark.parametrize("club", [*PAYING_CLUBS, "fvcc"])
def test_dry_run_does_not_create_output(monkeypatch, profile_output, club, capsys):
    monkeypatch.setattr(exporter, "load_player_profile_scopes", unexpected_source_load)

    assert exporter.main(["--club", club, "--dry-run"]) == 0

    assert "No files were written" in capsys.readouterr().out
    assert not profile_output.exists()


def test_fvcc_breakdown_export_still_writes(monkeypatch, profile_output):
    def load_scopes(*, club_id):
        assert club_id == "fvcc"
        return {"matches": pd.DataFrame({"match_id": ["match"]})}

    monkeypatch.setattr(exporter, "load_player_profile_scopes", load_scopes)
    for prepare in ("prepare_batting", "prepare_bowling", "prepare_fielding", "prepare_ball_rows"):
        monkeypatch.setattr(exporter, prepare, lambda *_, **__: pd.DataFrame())
    monkeypatch.setattr(
        exporter, "build_performance_breakdown",
        lambda *_: pd.DataFrame({"dimension": ["Captain"], "runs": [20]}),
    )

    assert exporter.main(["--club", "fvcc", "--performance-breakdown-only"]) == 0

    [result] = profile_output.iterdir()
    assert result.name == "performance_breakdown_by_dimension.csv"
    assert result.read_text() == "dimension,runs\nCaptain,20\n"
