"""Exercise pending Hall of Fame discipline changes with delayed prepared replies."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


FIXTURE = """
import json
import os
from pathlib import Path
import sys
import time
from zipfile import ZipFile

sys.path.insert(0, str(Path.cwd()))
import streamlit as st
from src.data.prepared_customer_views import CustomerViews
from src.ui import layout

class DelayedViews(CustomerViews):
    def read(self, key):
        if key in {"hof/fielding/html", "hof/bowling/html"}:
            time.sleep(2.5)
        return json.loads(self.archive.read(key))

layout._hof_header()

@st.fragment
def render_records():
    with ZipFile(os.environ["HOF_TEST_ARCHIVE"]) as archive:
        views = DelayedViews("georges-river-district", (), "hof-feedback-fixture", archive)
        layout.render_detailed_all_time_records(views)

render_records()
"""


def wait_ready(page, category):
    return page.wait_for_function("""category => {
        const region = document.querySelector('.st-key-hof_detail_results');
        if (!region?.getClientRects().length) return false;
        const table = region.querySelector('iframe')?.contentDocument?.getElementById('hof_' + category + '_detail');
        if (!table?.hasAttribute('data-table-ready')) return false;
        const button = table.querySelector('thead button');
        return button && !button.disabled && {
            rows: Number(table.dataset.tableReady),
            first: table.tBodies[0].rows[0]?.cells[1].textContent.trim()
        };
    }""", arg=category, timeout=30000).json_value()


def verify_pending(page, label):
    started = time.monotonic()
    page.get_by_role("radio", name=label, exact=True).click()
    notice = page.get_by_role("status").filter(has_text=f"Loading {label} records")
    notice.wait_for(timeout=1000)
    elapsed = time.monotonic() - started
    assert elapsed <= 1, elapsed
    assert not page.locator(".st-key-hof_detail_results").is_visible()
    return elapsed


def run(app_python, chrome, archive, evidence):
    evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary, socket.socket() as address:
        address.bind(("127.0.0.1", 0))
        port = address.getsockname()[1]
        address.close()
        app = Path(temporary) / "fixture.py"
        app.write_text(FIXTURE)
        origin = f"http://127.0.0.1:{port}"
        with (evidence / "fixture.log").open("w") as log:
            process = subprocess.Popen(
                [app_python, "-m", "streamlit", "run", str(app), "--server.port", str(port),
                 "--server.address", "127.0.0.1", "--server.headless", "true",
                 "--server.fileWatcherType", "none"],
                stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, "CLUB_ID": "georges-river-district",
                     "HOF_TEST_ARCHIVE": str(archive), "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"},
            )
            try:
                for _ in range(100):
                    try:
                        urlopen(origin + "/_stcore/health", timeout=1).close()
                        break
                    except OSError:
                        time.sleep(.1)
                with sync_playwright() as playwright:
                    browser = playwright.chromium.launch(executable_path=chrome)
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.goto(origin)
                    batting = wait_ready(page, "batting")
                    first_feedback = verify_pending(page, "Fielding")
                    page.wait_for_timeout(1100)
                    assert page.get_by_role("status").filter(has_text="Loading Fielding records").is_visible()
                    assert not page.locator(".st-key-hof_detail_results").is_visible()
                    page.screenshot(path=evidence / "fielding-pending.png")
                    fielding = wait_ready(page, "fielding")
                    assert fielding == {"rows": 2134, "first": "Meville Fernando"}
                    page.get_by_role("radio", name="Batting", exact=True).click()
                    assert wait_ready(page, "batting") == batting
                    verify_pending(page, "Fielding")
                    next_feedback = verify_pending(page, "Bowling")
                    bowling = wait_ready(page, "bowling")
                    assert bowling["rows"] == 2135
                    assert not page.get_by_role("status").filter(has_text="Loading Fielding").count()
                    search = page.get_by_role("combobox", name="Search player")
                    search.fill("A Randall")
                    page.get_by_role("option", name="A Randall", exact=True).click()
                    page.get_by_role("radio", name="Fielding", exact=True).click()
                    empty = page.get_by_text('No matching players in fielding records for "A Randall".', exact=True)
                    empty.wait_for(timeout=5000)
                    assert not page.get_by_role("status").filter(has_text="Loading Fielding").count()
                    assert not page.locator('[data-testid="stException"]').count()
                    (evidence / "fielding-feedback.json").write_text(json.dumps({
                        "status": "PASS", "heldPriorRowsHiddenBeyondOneSecond": True,
                        "fieldingFeedbackS": first_feedback, "fielding": fielding,
                        "bowlingFeedbackS": next_feedback, "latestSelectionWon": True, "bowling": bowling,
                        "emptyFieldingSearchClearedPending": True,
                    }, indent=2))
                    browser.close()
            finally:
                process.terminate()
                process.wait(timeout=15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-python", required=True)
    parser.add_argument("--chrome")
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    run(args.app_python, args.chrome, args.archive.resolve(), args.evidence)
