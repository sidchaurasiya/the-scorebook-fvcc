"""Chrome regression for stale Season Overview results during a filter rerun."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


FIXTURE = """
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path.cwd()))
from src.ui import layout
from src.utils import analytics
analytics._measurement_id = lambda: ""
from app import main

original = layout.render_data_source_panel

def delayed(**kwargs):
    control = Path(os.environ["SCOREBOOK_TEST_CONTROL"])
    delay = control / "delay"
    if delay.exists():
        (control / "blocked").touch()
        deadline = time.monotonic() + 20
        while delay.exists() and time.monotonic() < deadline:
            time.sleep(.02)
    return original(**kwargs)

layout.render_data_source_panel = delayed
try:
    main()
finally:
    layout.render_data_source_panel = original
"""


def wait_for_scope(page, season, prior=None):
    return page.wait_for_function("""([label, prior]) => {
        const region = document.querySelector('.st-key-season_scope_results');
        if (!region?.getClientRects().length) return false;
        const context = region.querySelector('[data-season-context]');
        const feed = region.querySelector('[data-season-feed]');
        const complete = region.querySelector('[data-season-complete]');
        const frame = region.querySelector('[role=tabpanel]:not([hidden]) iframe[title]');
        const doc = frame?.contentDocument;
        const table = doc?.querySelector('[data-season-table]');
        if (!complete || !feed || !table || context?.dataset.seasonLabel !== label) return false;
        const run = complete.dataset.run;
        if (run === prior || [context, feed, table].some(marker => marker.dataset.run !== run)) return false;
        const rows = doc.querySelector('tbody')?.rows;
        return rows?.length && {
            run, seasonId:table.dataset.seasonId, teamId:table.dataset.teamId,
            discipline:table.dataset.seasonTable, rows:rows.length, first:rows[0].innerText,
            feed:region.querySelector('.st-key-season_by_round_card').innerText.slice(0, 220),
        };
    }""", arg=[season, prior], timeout=120000).json_value()


def select(page, option):
    page.get_by_role("combobox", name="Season", exact=True).click()
    page.get_by_role("option", name=option, exact=True).click()


def assert_pending(page, season, control, screenshot):
    notice = page.get_by_role("status").filter(has_text=f"Loading {season}")
    notice.wait_for(timeout=3000)
    assert notice.count() == 1
    deadline = time.monotonic() + 3
    while not (control / "blocked").exists() and time.monotonic() < deadline:
        time.sleep(.02)
    assert (control / "blocked").exists()
    assert not page.locator("[data-season-context]").is_visible()
    assert not page.locator(".st-key-season_by_round_card").is_visible()
    assert not page.locator(".st-key-full_stats_card").is_visible()
    page.screenshot(path=screenshot)


def run(app_python, chrome, evidence):
    with tempfile.TemporaryDirectory() as temporary:
        control = Path(temporary)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        app = control / "fixture.py"
        app.write_text(FIXTURE)
        origin = f"http://127.0.0.1:{port}/"
        with (evidence / "fixture.log").open("w") as log:
            process = subprocess.Popen(
                [app_python, "-m", "streamlit", "run", str(app), "--server.port", str(port),
                 "--server.address", "127.0.0.1", "--server.headless", "true", "--server.fileWatcherType", "none"],
                stdout=log, stderr=subprocess.STDOUT, env={**os.environ, "CLUB_ID": "fvcc",
                 "SCOREBOOK_TEST_CONTROL": temporary, "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"},
            )
            try:
                for _ in range(100):
                    try:
                        urlopen(origin + "_stcore/health", timeout=1).close()
                        break
                    except OSError:
                        time.sleep(.1)
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=chrome)
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    current, previous = "Summer 2026/27", "Summer 2025/26"
                    page.goto(origin + "?page=season-overview")
                    original = wait_for_scope(page, current)
                    (control / "delay").touch()
                    select(page, previous)
                    assert_pending(page, previous, control, evidence / "season-pending.png")
                    (control / "delay").unlink()
                    selected = wait_for_scope(page, previous, original["run"])
                    assert original["seasonId"] != selected["seasonId"]
                    assert original["feed"] != selected["feed"] and original["first"] != selected["first"]
                    (control / "blocked").unlink()
                    (control / "delay").touch()
                    select(page, current)
                    assert_pending(page, current, control, evidence / "season-overlap-initial.png")
                    select(page, previous)
                    assert_pending(page, previous, control, evidence / "season-overlap-latest.png")
                    (control / "delay").unlink()
                    final = wait_for_scope(page, previous, selected["run"])
                    assert {k: v for k, v in final.items() if k != "run"} == {
                        k: v for k, v in selected.items() if k != "run"
                    }
                    assert not page.locator('[data-testid="stException"]').count()
                    page.screenshot(path=evidence / "season-settled.png")
                    (evidence / "season-scope.json").write_text(json.dumps({
                        "status": "PASS", "oldContextFeedTableHidden": True, "latestSelectionWon": True,
                        "initial": original, "selected": selected, "superseding": final,
                    }, indent=2))
                    browser.close()
            finally:
                (control / "delay").unlink(missing_ok=True)
                process.terminate()
                process.wait(timeout=15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-python", default=sys.executable)
    parser.add_argument("--chrome")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    run(args.app_python, args.chrome, args.evidence)
