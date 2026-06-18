from __future__ import annotations

import csv
import os
import threading
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
GRDCC_PROFILE_PATH = (
    REPO_ROOT
    / "clubs"
    / "georges-river-district"
    / "data"
    / "processed"
    / "validation"
    / "performance"
    / "grdcc_localhost_load_profile.csv"
)
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


def record_grdcc_load_profile(
    stage: str,
    elapsed_ms: float,
    *,
    rows_loaded: int | str | None = None,
    files_loaded: int | str | None = None,
    cache_hit: bool | str | None = None,
    notes: str = "",
) -> None:
    """Append one opt-in local timing row without affecting normal app runtime."""
    if os.getenv("CLUB_ID", "").strip() != "georges-river-district":
        return
    if os.getenv("GRDCC_PERF_PROFILE", "").strip() != "1":
        return
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
        GRDCC_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_header = not GRDCC_PROFILE_PATH.exists()
        with GRDCC_PROFILE_PATH.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=PROFILE_COLUMNS)
            if write_header:
                writer.writeheader()
            writer.writerow(row)
