from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup


class PublicScraperError(RuntimeError):
    """Raised when a public PlayCricket page cannot be read."""


@dataclass(frozen=True)
class PublicPageScraper:
    timeout_seconds: int = 30

    def fetch_html(self, url: str) -> str:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"}:
            raise PublicScraperError("Only public http/https URLs are supported.")

        response = requests.get(
            url,
            headers={
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "CricketClubAnalytics/0.1 public-data prototype",
            },
            timeout=self.timeout_seconds,
        )

        if response.status_code >= 400:
            raise PublicScraperError(
                f"Page request failed: {response.status_code} {response.text[:300]}"
            )

        return response.text

    def extract_tables(self, url: str) -> list[pd.DataFrame]:
        """Extract ordinary HTML tables from a public page."""
        html = self.fetch_html(url)
        try:
            return pd.read_html(html)
        except ValueError:
            return []

    def extract_visible_text(self, url: str) -> str:
        """Extract readable page text for debugging pages with no HTML tables."""
        html = self.fetch_html(url)
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        lines = [line.strip() for line in soup.get_text("\n").splitlines()]
        return "\n".join(line for line in lines if line)
