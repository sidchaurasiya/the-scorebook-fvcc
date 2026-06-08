"""Visit Streamlit apps with a real browser session so they stay warm."""

from __future__ import annotations

import sys
from dataclasses import dataclass

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


@dataclass(frozen=True)
class StreamlitApp:
    name: str
    url: str


# Add FVCC, GRDCC, Southside, and other Streamlit apps here as needed.
APPS: tuple[StreamlitApp, ...] = (
    StreamlitApp(
        name="Le Page Park Hall of Fame",
        url="https://le-page-park-scorebook-demo.streamlit.app/?page=hall-of-fame",
    ),
    StreamlitApp(
        name="FVCC Production",
        url="https://the-scorebook-fvcc.streamlit.app/",
    ),
)

PAGE_LOAD_TIMEOUT_MS = 60_000
SESSION_WARMUP_MS = 20_000


def visit_app(page, app: StreamlitApp) -> None:
    print(f"Visiting {app.name}: {app.url}", flush=True)
    response = page.goto(
        app.url,
        wait_until="domcontentloaded",
        timeout=PAGE_LOAD_TIMEOUT_MS,
    )

    if response is None:
        raise RuntimeError(f"{app.name} did not return an initial page response")

    status = response.status
    if status >= 400:
        raise RuntimeError(f"{app.name} returned HTTP {status}")

    page.wait_for_timeout(SESSION_WARMUP_MS)
    title = page.title()
    print(f"Visited {app.name} successfully (HTTP {status}, title={title!r})", flush=True)


def main() -> int:
    failures: list[str] = []

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
                    visit_app(page, app)
                except (PlaywrightError, PlaywrightTimeoutError, RuntimeError) as exc:
                    message = f"{app.name}: {exc}"
                    failures.append(message)
                    print(f"FAILED {message}", file=sys.stderr, flush=True)
        finally:
            browser.close()

    if failures:
        print("One or more Streamlit keep-awake visits failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(f"Visited {len(APPS)} Streamlit app(s).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
