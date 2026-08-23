"""Central Scorebook release and build identification."""

from __future__ import annotations

import os
import subprocess
from functools import lru_cache
from pathlib import Path


SCOREBOOK_RELEASE_VERSION = "v1.0.0"
BUILD_ENVIRONMENT_KEYS = (
    "SCOREBOOK_BUILD_SHA",
    "STREAMLIT_GIT_COMMIT",
    "COMMIT_SHA",
    "GITHUB_SHA",
    "GIT_COMMIT",
    "SOURCE_VERSION",
)


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


def scorebook_version_label(club_label: str, repo_root: str | Path) -> str:
    return (
        f"Scorebook {str(club_label or 'App').strip()} | "
        f"Release: {SCOREBOOK_RELEASE_VERSION} | "
        f"Build: {scorebook_build_identifier(repo_root)}"
    )
