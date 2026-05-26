from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

import pandas as pd

from scripts.build_club_review_pack import build_strict_duplicate_merge_review
from scripts import refresh_data
from src.config.club_config import REPO_ROOT, allow_legacy_fallback, get_processed_path
from src.utils import analytics
from src.utils.player_identity import normalize_player_name_for_strict_merge


ROOT = Path(__file__).resolve().parents[1]


def test_non_fvcc_config_does_not_fall_back_to_legacy_processed_path() -> None:
    assert (REPO_ROOT / "data" / "processed" / "seasons.csv").exists()
    assert allow_legacy_fallback("reynella") is False
    assert get_processed_path("seasons.csv", club_id="reynella") == (
        REPO_ROOT / "clubs" / "reynella" / "data" / "processed" / "seasons.csv"
    )


def test_check_club_config_resolves_requested_club() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_club_config.py", "--club", "reynella"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Active club ID: reynella" in result.stdout
    assert "PlayCricket club ID: f2d283dc-87d8-eb11-a7ad-2818780da0cc" in result.stdout
    assert "Legacy fallback enabled: False" in result.stdout


def test_refresh_data_dry_run_does_not_run_match_centre() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/refresh_data.py", "--club", "reynella", "--dry-run"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "Dry run complete. No network requests were made and no files were written." in result.stdout
    assert "scripts/refresh_match_centre_data.py" not in result.stdout


def test_refresh_data_default_match_centre_is_flag_gated() -> None:
    source = inspect.getsource(refresh_data.main)
    assert "args.with_current_match_centre" in source
    assert "skipped; pass --with-current-match-centre" in source


def test_ga4_event_params_include_club_context(monkeypatch) -> None:
    monkeypatch.setenv("CLUB_ID", "reynella")
    params = analytics.default_event_params({"page_title": "Hall of Fame", "section_name": "batting"})
    assert params["app_area"] == "scorebook"
    assert params["club_id"] == "reynella"
    assert params["club_name"] == "Reynella Cricket Club"
    assert params["page_name"] == "Hall of Fame"
    assert params["section_name"] == "batting"


def test_ga4_noops_without_valid_measurement_id(monkeypatch) -> None:
    monkeypatch.setenv("GA4_MEASUREMENT_ID", "!")

    def fail_if_called(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("GA4 HTML injection should not run without a valid measurement ID")

    monkeypatch.setattr(analytics.components, "html", fail_if_called)
    analytics.track_event("page_view", {"page_name": "Hall of Fame"})


def test_strict_merge_name_normalization() -> None:
    assert normalize_player_name_for_strict_merge("D'Mello") == normalize_player_name_for_strict_merge("Dmello")
    assert normalize_player_name_for_strict_merge("Faraz Khan") == normalize_player_name_for_strict_merge("FARAZ   KHAN")
    assert normalize_player_name_for_strict_merge("Jean-Paul") == normalize_player_name_for_strict_merge("Jean Paul")
    assert normalize_player_name_for_strict_merge("Gopi Krishna") != normalize_player_name_for_strict_merge("Gopi Krishna Inturi")


def test_strict_merge_review_blocks_season_overlap() -> None:
    frames = {
        "batting": pd.DataFrame(
            [
                {"raw_player_id": "a", "raw_player_name": "Faraz Khan", "season": "Summer 2024/25", "battingAggregate": "10"},
                {"raw_player_id": "b", "raw_player_name": "FARAZ KHAN", "season": "Summer 2024/25", "battingAggregate": "20"},
            ]
        ),
        "bowling": pd.DataFrame(),
        "fielding": pd.DataFrame(),
    }

    safe, manual = build_strict_duplicate_merge_review("test-club", frames)

    assert safe.empty
    assert manual["possible_reason"].str.contains("season overlap").any()
    assert "Summer 2024/25" in set(manual["overlap_seasons"])


def test_strict_merge_review_allows_no_overlap_exact_names() -> None:
    frames = {
        "batting": pd.DataFrame(
            [
                {"raw_player_id": "a", "raw_player_name": "Baurel D'Mello", "season": "Summer 2023/24", "battingAggregate": "10"},
                {"raw_player_id": "b", "raw_player_name": "Baurel Dmello", "season": "Summer 2024/25", "battingAggregate": "20"},
            ]
        ),
        "bowling": pd.DataFrame(),
        "fielding": pd.DataFrame(),
    }

    safe, manual = build_strict_duplicate_merge_review("test-club", frames)

    assert manual.empty
    assert safe["candidate_group_id"].nunique() == 1
    assert set(safe["raw_player_id"]) == {"a", "b"}
    assert set(safe["confidence"]) == {"high"}
