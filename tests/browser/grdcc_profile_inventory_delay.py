"""Real Chrome regression for a slow GRDCC inventory on a selection rerun."""
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


def verify_return_to_visible_player(browser, root, evidence):
    feedback = (root / "src/ui/grdcc_profile_feedback.html").read_text()
    results = []
    for width, height in ((1440, 1000), (390, 844)):
        page = browser.new_page(viewport={"width": width, "height": height})
        page.set_content("""
            <div class="st-key-player_selector_card">
              <input role="combobox" aria-controls="players">
              <div role="listbox" id="players">
                <button role="option">Andrew McGuiness</button>
                <button role="option">Percy Eldridge</button>
              </div>
            </div>
            <div class="st-key-grdcc_profile_region">
              <section data-profile-choice="Percy Eldridge">Percy Eldridge · 2,208 runs</section>
              <span hidden data-profile-finished="Percy Eldridge"></span>
            </div>
        """ + feedback)
        card = page.locator("[data-profile-choice]")
        notice = page.locator(".grdcc-profile-pending")
        page.get_by_role("option", name="Andrew McGuiness", exact=True).click()
        assert not card.is_visible()
        assert notice.inner_text().endswith("Andrew McGuiness")
        page.get_by_role("option", name="Percy Eldridge", exact=True).click()
        assert card.is_visible() and not notice.is_visible()
        assert "2,208 runs" in card.inner_text()
        page.screenshot(path=evidence / f"rapid-return-{width}.png")

        # A superseded response may arrive after the correct card is reused.
        card.evaluate("el => { el.dataset.profileChoice = 'Andrew McGuiness'; el.textContent = '4,699 runs'; }")
        assert not card.is_visible()
        assert notice.inner_text().endswith("Percy Eldridge")
        card.evaluate("el => { el.dataset.profileChoice = 'Percy Eldridge'; el.textContent = '2,208 runs'; }")
        assert card.is_visible() and not notice.is_visible()
        assert "2,208 runs" in card.inner_text()
        results.append({"width": width, "height": height, "samePlayerReturn": True, "staleLateCardHidden": True})
        page.close()
    (evidence / "rapid-return.json").write_text(json.dumps(results, indent=2))


def run(root, app_python, chrome, evidence):
    with tempfile.TemporaryDirectory() as temporary:
        control = Path(temporary)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        runner = control / "app_fixture.py"
        runner.write_text("""
import os, sys, time
from pathlib import Path
sys.path.insert(0, str(Path.cwd()))
os.environ["CLUB_ID"] = "georges-river-district"
from src.ui import layout
from src.utils import analytics
analytics._measurement_id = lambda: "G-LOCALTEST1"
original = layout.load_grdcc_profile_bundle
def delayed(club):
    control = Path(os.environ["PROFILE_TEST_CONTROL"])
    if (control / "armed").exists():
        (control / "waiting").touch()
        until = time.monotonic() + 20
        while not (control / "release").exists() and time.monotonic() < until:
            time.sleep(.02)
    return original(club)
layout.load_grdcc_profile_bundle = delayed
try:
    from app import main
    main()
finally:
    layout.load_grdcc_profile_bundle = original
""")
        with (evidence / "fixture.log").open("w") as log:
            proc = subprocess.Popen([app_python, "-m", "streamlit", "run", str(runner),
                "--server.port", str(port), "--server.address", "127.0.0.1", "--server.headless", "true",
                "--server.fileWatcherType", "none"], cwd=root, stdout=log, stderr=subprocess.STDOUT,
                env={**os.environ, "PROFILE_TEST_CONTROL": temporary, "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false"})
            try:
                for _ in range(100):
                    try:
                        urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=1).close()
                        break
                    except OSError:
                        time.sleep(.1)
                with sync_playwright() as pw:
                    browser = pw.chromium.launch(executable_path=chrome)
                    page = browser.new_page(viewport={"width":1440, "height":1000})
                    page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(
                        (f"http://127.0.0.1:{port}/", "data:", "about:", "blob:")) else route.abort())
                    page.goto(f"http://127.0.0.1:{port}/?page=player-profile&player=Mark+Burgess")
                    page.locator(".profile-name", has_text="Mark Burgess").wait_for(timeout=120000)
                    (control / "armed").touch()
                    search = page.get_by_role("combobox", name="Search player")
                    search.fill("Ryan Croom")
                    page.get_by_role("option", name="Ryan Croom", exact=True).click()
                    for _ in range(200):
                        if (control / "waiting").exists():
                            break
                        time.sleep(.025)
                    assert (control / "waiting").exists()
                    assert page.locator(".profile-name:visible").count() == 0
                    assert "225" not in page.locator(".st-key-grdcc_profile_region").inner_text() or not page.locator(".st-key-grdcc_profile_region").is_visible()
                    pending = page.locator(".grdcc-profile-pending:visible")
                    assert pending.count() == 1 and "Ryan Croom" in pending.inner_text()
                    page.screenshot(path=evidence / "inventory-pending.png")
                    (control / "release").touch()
                    page.locator(".profile-name:visible", has_text="Ryan Croom").wait_for(timeout=30000)
                    figures = page.locator(".grdcc-primary-figures dd").all_inner_texts()
                    assert figures[:2] == ["6,209", "284"] and not pending.count()
                    page.screenshot(path=evidence / "inventory-settled.png")
                    (evidence / "inventory-delay.json").write_text(json.dumps({
                        "status":"PASS","oldVisibleWhileBlocked":False,"visiblePendingCount":1,
                        "pendingPlayer":"Ryan Croom","settledFigures":figures},indent=2))
                    verify_return_to_visible_player(browser, root, evidence)
                    browser.close()
            finally:
                (control / "release").touch()
                proc.terminate()
                proc.wait(timeout=15)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-python", default=sys.executable)
    parser.add_argument("--chrome")
    parser.add_argument("--evidence", type=Path, required=True)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    run(Path.cwd(), args.app_python, args.chrome, args.evidence)
