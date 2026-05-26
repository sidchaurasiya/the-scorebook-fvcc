from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

from scripts import refresh_data
from src.config.club_config import REPO_ROOT, allow_legacy_fallback, get_processed_path
from src.utils import analytics


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
