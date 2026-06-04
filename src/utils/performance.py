from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any


def performance_logging_enabled() -> bool:
    return os.getenv("SCOREBOOK_PERF_LOG") == "1" or os.getenv("FVCC_DEBUG_TIMINGS") == "1"


def log_timing(label: str, started_at: float, **fields: Any) -> None:
    if not performance_logging_enabled():
        return
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    details = " ".join(f"{key}={value}" for key, value in fields.items() if value is not None)
    suffix = f" {details}" if details else ""
    print(f"[scorebook-perf] {label}: {elapsed_ms:.1f} ms{suffix}", flush=True)


def file_mtime(path: str | Path) -> float:
    candidate = Path(path)
    return candidate.stat().st_mtime if candidate.exists() else 0.0
