"""Visit Streamlit apps with a real browser session so they stay warm."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import Page
from playwright.sync_api import sync_playwright


@dataclass(frozen=True)
class StreamlitApp:
    name: str
    url: str


# Add FVCC, GRDCC, Southside, and other Streamlit apps here as needed.
APPS: tuple[StreamlitApp, ...] = (
    StreamlitApp(
        name="Le Page Park root",
        url="https://the-scorebook-le-page-park-demo.streamlit.app/?source=keep_awake",
    ),
    StreamlitApp(
        name="Le Page Park Hall of Fame",
        url="https://the-scorebook-le-page-park-demo.streamlit.app/?page=hall-of-fame&source=keep_awake",
    ),
    StreamlitApp(
        name="FVCC root",
        url="https://the-scorebook-fvcc.streamlit.app/?source=keep_awake",
    ),
    StreamlitApp(
        name="FVCC Hall of Fame",
        url="https://the-scorebook-fvcc.streamlit.app/?page=hall-of-fame&source=keep_awake",
    ),
)

PAGE_LOAD_TIMEOUT_MS = 90_000
BUTTON_CLICK_TIMEOUT_MS = 5_000
SESSION_WARMUP_MS = 25_000


def maybe_click_wake_button(page: Page) -> bool:
    """Click a visible Streamlit wake button when the app is asleep."""
    button_texts = ("wake", "up", "run", "running", "app", "yes")

    for button in page.locator("button").all():
        try:
            if not button.is_visible(timeout=1_000):
                continue

            label = " ".join(button.inner_text(timeout=1_000).lower().split())
            if not label:
                continue

            if any(token in label for token in button_texts):
                print(f"Wake button detected: {label!r}", flush=True)
                button.click(timeout=BUTTON_CLICK_TIMEOUT_MS)
                return True
        except (PlaywrightError, PlaywrightTimeoutError):
            continue

    print("Wake button detected: no", flush=True)
    return False


def visit_app(page: Page, app: StreamlitApp) -> bool:
    print(f"--- Visiting {app.name} ---", flush=True)
    print(f"URL: {app.url}", flush=True)

    response = page.goto(
        app.url,
        wait_until="domcontentloaded",
        timeout=PAGE_LOAD_TIMEOUT_MS,
    )

    if response is None:
        raise RuntimeError(f"{app.name} did not return an initial page response")

    status = response.status
    print(f"Initial HTTP status: {status}", flush=True)

    wake_button_clicked = maybe_click_wake_button(page)
    if wake_button_clicked:
        page.wait_for_load_state("domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)

    page.wait_for_timeout(SESSION_WARMUP_MS)

    try:
        title = page.title()
        print(f"Page title read: yes ({title!r})", flush=True)
    except (PlaywrightError, PlaywrightTimeoutError) as exc:
        print(f"Page title read: no ({exc})", flush=True)

    if status >= 400:
        raise RuntimeError(f"{app.name} returned HTTP {status}")

    print(f"Result: success for {app.name}", flush=True)
    return True


def main() -> int:
    failures: list[str] = []
    successes = 0

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            context = browser.new_context(
                viewport={"width": 1440, "height": 1000},
                locale="en-AU",
            )
            page = context.new_page()

            for app in APPS:
                try:
                    if visit_app(page, app):
                        successes += 1
                except (PlaywrightError, PlaywrightTimeoutError, RuntimeError) as exc:
                    message = f"{app.name}: {exc}"
                    failures.append(message)
                    print(f"Result: failure for {app.name}: {exc}", file=sys.stderr, flush=True)
        finally:
            browser.close()

    if failures:
        print("One or more Streamlit keep-awake visits failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)

    if successes == 0:
        print("WARNING: all Streamlit keep-awake visits failed.", file=sys.stderr)

    print(f"Completed {len(APPS)} visit attempt(s): {successes} succeeded, {len(failures)} failed.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
