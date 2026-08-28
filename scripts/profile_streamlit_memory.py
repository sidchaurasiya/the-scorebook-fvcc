#!/usr/bin/env python3
"""Profile Scorebook Streamlit RSS and runtime dataframe reads by club/page."""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUTPUT_ROOT = ROOT / "data" / "processed" / "validation" / "memory"

APPS = {
    "gwhcc": {
        "club_id": "glen-waverley-hawks",
        "entrypoint": "app_gwhcc.py",
        "profile_id": "nathan_bungey",
    },
    "fvcc": {
        "club_id": "fvcc",
        "entrypoint": "app.py",
        "profile_id": "danny_singh",
    },
    "grdcc": {
        "club_id": "georges-river-district",
        "entrypoint": "app_grdcc.py",
        "profile_id": "grdcc_excel_exact_paul_thomas",
    },
}
PAGES = ["hall-of-fame", "season-overview", "milestone", "player-profile"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="baseline")
    parser.add_argument("--apps", default="gwhcc,fvcc,grdcc")
    parser.add_argument("--pages", default="hall-of-fame,season-overview,milestone,player-profile,journey")
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--app")
    parser.add_argument("--page")
    parser.add_argument("--result")
    return parser.parse_args()


def mb(value: int | float) -> float:
    return round(float(value) / (1024 * 1024), 3)


def object_size_bytes(value: object) -> int:
    import pandas as pd

    if isinstance(value, pd.DataFrame):
        return int(value.memory_usage(index=True, deep=True).sum())
    if isinstance(value, pd.Series):
        return int(value.memory_usage(index=True, deep=True))
    if isinstance(value, dict):
        return sys.getsizeof(value) + sum(object_size_bytes(key) + object_size_bytes(item) for key, item in value.items())
    if isinstance(value, (list, tuple, set)):
        return sys.getsizeof(value) + sum(object_size_bytes(item) for item in value)
    try:
        return sys.getsizeof(value)
    except TypeError:
        return 0


def worker(app_key: str, page: str, result_path: Path) -> int:
    import gc
    import inspect

    import psutil

    app = APPS[app_key]
    os.environ["CLUB_ID"] = app["club_id"]
    os.environ["SCOREBOOK_RUNTIME_DEBUG_EXPORTS"] = "0"
    process = psutil.Process()
    samples: list[int] = []
    stop = threading.Event()

    def sampler() -> None:
        while not stop.is_set():
            samples.append(process.memory_info().rss)
            stop.wait(0.025)

    thread = threading.Thread(target=sampler, daemon=True)
    thread.start()
    stages: list[dict[str, object]] = []

    def stage(name: str, started: float | None = None) -> None:
        rss = process.memory_info().rss
        stages.append(
            {
                "stage": name,
                "rss_mb": mb(rss),
                "elapsed_s": round(time.perf_counter() - started, 4) if started is not None else 0.0,
            }
        )

    stage("python_process")
    import pandas as pd

    stage("pandas_imported")
    original_read_csv = pd.read_csv
    original_read_json = pd.read_json
    read_events: list[dict[str, object]] = []

    def record_frame(source: object, frame: object, source_format: str) -> None:
        if not isinstance(frame, pd.DataFrame):
            return
        try:
            path = str(Path(source).resolve()) if isinstance(source, (str, os.PathLike)) else str(source)
        except (OSError, TypeError, ValueError):
            path = str(source)
        stack = [
            f"{Path(item.filename).name}:{item.function}"
            for item in inspect.stack()[2:14]
            if "site-packages" not in item.filename and item.filename != __file__
        ]
        read_events.append(
            {
                "path": path,
                "format": source_format,
                "rows": len(frame),
                "columns": len(frame.columns),
                "deep_mb": mb(frame.memory_usage(index=True, deep=True).sum()),
                "call_stack": " > ".join(stack),
            }
        )

    def tracked_csv(*args, **kwargs):
        frame = original_read_csv(*args, **kwargs)
        if args:
            record_frame(args[0], frame, "csv")
        return frame

    def tracked_json(*args, **kwargs):
        frame = original_read_json(*args, **kwargs)
        if args:
            record_frame(args[0], frame, "json")
        return frame

    pd.read_csv = tracked_csv
    pd.read_json = tracked_json

    started = time.perf_counter()
    from src.config import club_config

    stage("config_module_loaded", started)
    started = time.perf_counter()
    club_config.load_club_config(app["club_id"])
    stage("club_config_loaded", started)
    started = time.perf_counter()
    from src.ui import layout  # noqa: F401

    stage("layout_imported", started)

    from streamlit.testing.v1 import AppTest

    run_pages = PAGES if page == "journey" else [page]
    exceptions = []
    at = None
    for selected_page in run_pages:
        at = AppTest.from_file(str(ROOT / app["entrypoint"]), default_timeout=180)
        stage(f"app_test_created_{selected_page}")
        at.query_params["page"] = selected_page
        if selected_page == "player-profile":
            at.query_params["player_id"] = app["profile_id"]
        else:
            try:
                del at.query_params["player_id"]
            except KeyError:
                pass
        started = time.perf_counter()
        at.run()
        stage(f"render_{selected_page}", started)
        exceptions.extend(str(item.value) for item in at.exception)

    session_rows = []
    try:
        state = at.session_state.filtered_state
    except Exception:
        state = {}
    for key, value in state.items():
        session_rows.append(
            {
                "key": str(key),
                "type": type(value).__name__,
                "deep_mb": mb(object_size_bytes(value)),
            }
        )
    gc.collect()
    stage("after_gc")
    stop.set()
    thread.join(timeout=1)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(
        json.dumps(
            {
                "app": app_key,
                "club_id": app["club_id"],
                "entrypoint": app["entrypoint"],
                "page": page,
                "stages": stages,
                "peak_rss_mb": mb(max(samples, default=process.memory_info().rss)),
                "reads": read_events,
                "session_state": session_rows,
                "exceptions": exceptions,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0 if not exceptions else 1


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    columns = list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def orchestrate(label: str, apps: list[str], pages: list[str]) -> int:
    raw_dir = OUTPUT_ROOT / f"raw_{label}"
    results = []
    for app in apps:
        for page in pages:
            result_path = raw_dir / f"{app}_{page}.json"
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", "--app", app, "--page", page, "--result", str(result_path)]
            completed = subprocess.run(command, cwd=ROOT, text=True, capture_output=True)
            if completed.returncode != 0:
                print(f"worker_failed app={app} page={page} code={completed.returncode}", file=sys.stderr)
                print(completed.stderr[-4000:], file=sys.stderr)
            if result_path.exists():
                results.append(json.loads(result_path.read_text(encoding="utf-8")))

    stage_rows = []
    dataset_rows = []
    session_rows = []
    for result in results:
        previous = None
        for item in result["stages"]:
            stage_rows.append(
                {
                    "label": label,
                    "app": result["app"],
                    "club_id": result["club_id"],
                    "page": result["page"],
                    "stage": item["stage"],
                    "rss_mb": item["rss_mb"],
                    "delta_mb": round(item["rss_mb"] - previous, 3) if previous is not None else 0.0,
                    "peak_rss_mb": result["peak_rss_mb"],
                    "elapsed_s": item["elapsed_s"],
                    "exception_count": len(result["exceptions"]),
                }
            )
            previous = item["rss_mb"]
        grouped: dict[str, dict[str, object]] = {}
        for event in result["reads"]:
            key = f"{event['format']}|{event['path']}"
            row = grouped.setdefault(
                key,
                {
                    "label": label,
                    "app": result["app"],
                    "page": result["page"],
                    "dataset": event["path"],
                    "format": event["format"],
                    "read_count": 0,
                    "rows": event["rows"],
                    "columns": event["columns"],
                    "max_deep_mb": 0.0,
                    "cumulative_read_mb": 0.0,
                    "call_stacks": set(),
                },
            )
            row["read_count"] += 1
            row["rows"] = max(row["rows"], event["rows"])
            row["columns"] = max(row["columns"], event["columns"])
            row["max_deep_mb"] = max(row["max_deep_mb"], event["deep_mb"])
            row["cumulative_read_mb"] += event["deep_mb"]
            row["call_stacks"].add(event["call_stack"])
        for row in grouped.values():
            row["max_deep_mb"] = round(row["max_deep_mb"], 3)
            row["cumulative_read_mb"] = round(row["cumulative_read_mb"], 3)
            row["call_stacks"] = " || ".join(sorted(row["call_stacks"]))
            dataset_rows.append(row)
        for item in result["session_state"]:
            session_rows.append({"label": label, "app": result["app"], "page": result["page"], **item})

    write_csv(OUTPUT_ROOT / f"streamlit_memory_stages_{label}.csv", stage_rows)
    write_csv(OUTPUT_ROOT / f"streamlit_runtime_datasets_{label}.csv", dataset_rows)
    write_csv(OUTPUT_ROOT / f"streamlit_session_state_{label}.csv", session_rows)
    print(f"profile_complete label={label} workers={len(results)} output={OUTPUT_ROOT}")
    return 0 if len(results) == len(apps) * len(pages) else 1


def main() -> int:
    args = parse_args()
    if args.worker:
        return worker(args.app, args.page, Path(args.result))
    apps = [value for value in args.apps.split(",") if value]
    pages = [value for value in args.pages.split(",") if value]
    return orchestrate(args.label, apps, pages)


if __name__ == "__main__":
    raise SystemExit(main())
