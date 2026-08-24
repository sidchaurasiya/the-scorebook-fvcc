"""Central Scorebook release and build identification."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


SCOREBOOK_RELEASE_VERSION = "v1.0.0"


@dataclass(frozen=True)
class ScorebookRelease:
    club_label: str
    release_version: str


SCOREBOOK_RELEASES = {
    "fvcc": ScorebookRelease("FVCC", "v1.0.0"),
    "georges-river-district": ScorebookRelease("GRDCC", "v1.0.0"),
    "glen-waverley-hawks": ScorebookRelease("GWHCC", "v1.0.0"),
}
BUILD_ENVIRONMENT_KEYS = (
    "SCOREBOOK_BUILD_SHA",
    "STREAMLIT_GIT_COMMIT",
    "COMMIT_SHA",
    "GITHUB_SHA",
    "GIT_COMMIT",
    "SOURCE_VERSION",
)


def scorebook_release_config(club_id: str) -> ScorebookRelease | None:
    return SCOREBOOK_RELEASES.get(str(club_id or "").strip().casefold())


@lru_cache(maxsize=4)
def scorebook_build_identifier(repo_root: str | Path) -> str:
    for env_name in BUILD_ENVIRONMENT_KEYS:
        value = str(os.getenv(env_name, "") or "").strip()
        if value:
            return value[:7]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(repo_root),
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return "unavailable"
    return result.stdout.strip() or "unavailable"


def scorebook_version_label(
    club_label: str,
    repo_root: str | Path,
    release_version: str = SCOREBOOK_RELEASE_VERSION,
) -> str:
    return (
        f"Scorebook {str(club_label or 'App').strip()} | "
        f"Release: {str(release_version or SCOREBOOK_RELEASE_VERSION).strip()} | "
        f"Build: {scorebook_build_identifier(repo_root)}"
    )
