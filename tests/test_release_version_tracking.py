from __future__ import annotations

import inspect
from types import SimpleNamespace

from src.config import app_version
from src.ui import layout


def clear_build_environment(monkeypatch) -> None:
    for key in app_version.BUILD_ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)
    app_version.scorebook_build_identifier.cache_clear()


def test_build_identifier_uses_documented_environment_priority(monkeypatch, tmp_path) -> None:
    clear_build_environment(monkeypatch)
    for index, key in enumerate(app_version.BUILD_ENVIRONMENT_KEYS):
        monkeypatch.setenv(key, f"{index}234567890abcdef")

    assert app_version.scorebook_build_identifier(tmp_path) == "0234567"


def test_build_identifier_supports_each_environment_and_unavailable_fallback(monkeypatch, tmp_path) -> None:
    for index, key in enumerate(app_version.BUILD_ENVIRONMENT_KEYS):
        clear_build_environment(monkeypatch)
        monkeypatch.setenv(key, f"{index}abcdef123456789")
        assert app_version.scorebook_build_identifier(tmp_path) == f"{index}abcdef"[:7]

    clear_build_environment(monkeypatch)
    monkeypatch.setattr(
        app_version.subprocess,
        "run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("git unavailable")),
    )
    assert app_version.scorebook_build_identifier(tmp_path) == "unavailable"


def test_build_identifier_updates_after_deployed_commit_changes(monkeypatch, tmp_path) -> None:
    clear_build_environment(monkeypatch)
    builds = iter(["abc1234\n", "def5678\n"])
    monkeypatch.setattr(
        app_version.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout=next(builds)),
    )

    assert app_version.scorebook_build_identifier(tmp_path) == "abc1234"
    app_version.scorebook_build_identifier.cache_clear()
    assert app_version.scorebook_build_identifier(tmp_path) == "def5678"


def test_release_footer_labels_are_club_aware_and_gwhcc_is_unchanged(monkeypatch) -> None:
    clear_build_environment(monkeypatch)
    monkeypatch.setenv("SCOREBOOK_BUILD_SHA", "abc123456789")
    expected = {
        "fvcc": "Scorebook FVCC | Release: v1.0.0 | Build: abc1234",
        "georges-river-district": "Scorebook GRDCC | Release: v1.0.0 | Build: abc1234",
        "glen-waverley-hawks": "Scorebook GWHCC | Release: v1.0.0 | Build: abc1234",
    }
    for club_id, label in expected.items():
        monkeypatch.setattr(layout, "get_active_club_id", lambda club_id=club_id: club_id)
        assert label in layout.scorebook_version_footer_html()

    monkeypatch.setattr(layout, "get_active_club_id", lambda: "plenty")
    assert layout.scorebook_version_footer_html() == ""


def test_release_footer_is_wired_to_sidebar_and_mobile_footer() -> None:
    assert "scorebook_version_footer_html()" in inspect.getsource(layout.render_sidebar)
    assert "scorebook_version_footer_html()" in inspect.getsource(layout.render_mobile_page_footer)
