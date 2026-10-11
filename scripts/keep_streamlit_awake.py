"""Wake and verify public Scorebook apps using real browser sessions."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import time
from playwright.sync_api import Error as PlaywrightError, sync_playwright

APPS = {
    "FVCC": "https://the-scorebook-fvcc.streamlit.app/?page=hall-of-fame",
    "GRDCC": "https://the-scorebook-grdcc.streamlit.app/",
    "GWHCC": "https://the-scorebook-glen-waverley-hawks-cricket-club.streamlit.app/",
}
WAKE_BUTTON = re.compile(r"^Yes, get this app back up!$", re.I)
READY_TIMEOUT = 240
ARTIFACTS = Path("keep-awake-results")


def wait_for_app(page, messages, minimum_messages=0):
    """Inspect the shell AND app iframe; a 200 response alone is not success."""
    deadline = time.monotonic() + READY_TIMEOUT
    wake_clicked = False
    while time.monotonic() < deadline:
        for frame in page.frames:
            try:
                wake = frame.get_by_role("button", name=WAKE_BUTTON)
                if not wake_clicked and wake.is_visible():
                    wake.click(timeout=5000)
                    wake_clicked = True
                    print("Clicked Streamlit wake button", flush=True)
                app = frame.locator('[data-testid="stAppViewContainer"]')
                title = frame.locator("h1").filter(has_text="Hall of Fame")
                if app.is_visible() and title.first.is_visible():
                    error = frame.locator('[data-testid="stException"]')
                    if error.count():
                        raise RuntimeError(error.first.inner_text())
                    if len(messages) > minimum_messages:
                        return frame
            except PlaywrightError:
                # Frames can be replaced while a sleeping app starts up.
                continue
        page.wait_for_timeout(1000)
    raise RuntimeError("App did not render Hall of Fame with live Streamlit WebSocket traffic within 240 seconds")


def visit(browser, name, url, attempt):
    with browser.new_context(viewport={"width": 1440, "height": 1000}, locale="en-AU") as context:
        page = context.new_page()
        messages = []

        def watch_socket(socket):
            if "/_stcore/stream" in socket.url:
                socket.on("framereceived", lambda _: messages.append(time.monotonic()))

        page.on("websocket", watch_socket)
        try:
            response = page.goto(url, wait_until="domcontentloaded", timeout=90000)
            if response is None or response.status >= 400:
                raise RuntimeError(f"Initial HTTP status: {response.status if response else 'no response'}")
            frame = wait_for_app(page, messages)
            # Explicit, harmless in-app navigation generates a real browser click.
            link = frame.locator('a.side-nav-item').filter(has_text="Hall of Fame").first
            baseline = len(messages)
            link.click(timeout=15000)
            print(f"{name}: clicked Hall of Fame navigation", flush=True)
            frame = wait_for_app(page, messages, baseline)
            page.wait_for_timeout(10000)
            frame = wait_for_app(page, messages, baseline)
            print(f"{name}: app rendered; received {len(messages)} Streamlit WebSocket messages", flush=True)
        finally:
            page.screenshot(path=str(ARTIFACTS / f"{name}-{attempt}.png"), full_page=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", choices=APPS)
    args = parser.parse_args()
    ARTIFACTS.mkdir(exist_ok=True)
    results = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for name in ([args.app] if args.app else APPS):
                for attempt in (1, 2):
                    print(f"Visiting {name}: {APPS[name]} (attempt {attempt})", flush=True)
                    try:
                        visit(browser, name, APPS[name], attempt)
                        results[name] = {"success": True, "attempt": attempt}
                        break
                    except (PlaywrightError, RuntimeError) as exc:
                        results[name] = {"success": False, "attempt": attempt, "error": str(exc)}
                        print(f"{name}: FAILED: {exc}", flush=True)
        finally:
            browser.close()
    (ARTIFACTS / "results.json").write_text(json.dumps(results, indent=2) + "\n")
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(summary, "a") as output:
            for name, result in results.items():
                status = "PASS - app loaded and clicked" if result["success"] else "FAIL - see logs and screenshots"
                output.write(f"- {name}: {status}\n")
    return 0 if all(result["success"] for result in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
