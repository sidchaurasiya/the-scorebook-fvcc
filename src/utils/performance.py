from __future__ import annotations

import csv
import os
import threading
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_SETTINGS = {
    "fvcc": ("FVCC_PERF_PROFILE", "fvcc_localhost_load_profile.csv"),
    "georges-river-district": ("GRDCC_PERF_PROFILE", "grdcc_localhost_load_profile.csv"),
}
PROFILE_COLUMNS = [
    "timestamp",
    "stage",
    "elapsed_ms",
    "rows_loaded",
    "files_loaded",
    "cache_hit",
    "notes",
]
_PROFILE_LOCK = threading.Lock()


def record_club_load_profile(
    stage: str,
    elapsed_ms: float,
    *,
    rows_loaded: int | str | None = None,
    files_loaded: int | str | None = None,
    cache_hit: bool | str | None = None,
    notes: str = "",
) -> None:
    """Append one opt-in local timing row without affecting normal app runtime."""
    club_id = os.getenv("CLUB_ID", "fvcc").strip() or "fvcc"
    settings = PROFILE_SETTINGS.get(club_id)
    if settings is None:
        return
    env_name, filename = settings
    if os.getenv(env_name, "").strip() != "1":
        return
    profile_path = REPO_ROOT / "clubs" / club_id / "data" / "processed" / "validation" / "performance" / filename
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": str(stage),
        "elapsed_ms": f"{float(elapsed_ms):.1f}",
        "rows_loaded": "" if rows_loaded is None else str(rows_loaded),
        "files_loaded": "" if files_loaded is None else str(files_loaded),
        "cache_hit": "" if cache_hit is None else str(cache_hit).lower(),
        "notes": str(notes),
    }
    with _PROFILE_LOCK:
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        write_header = not profile_path.exists()
        with profile_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=PROFILE_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)


def record_grdcc_load_profile(*args, **kwargs) -> None:
    """Backwards-compatible name retained for GRDCC validation tooling."""
    record_club_load_profile(*args, **kwargs)
