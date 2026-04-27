from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class PlayHQAPIError(RuntimeError):
    """Raised when the PlayHQ API request fails."""


@dataclass(frozen=True)
class PlayHQClient:
    api_key: str
    tenant: str = "ca"
    base_url: str = "https://api.playhq.com"
    timeout_seconds: int = 30

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "x-api-key": self.api_key,
            "x-phq-tenant": self.tenant,
        }

    def get_json(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Call a PlayHQ JSON endpoint using public API headers."""
        if not self.api_key:
            raise PlayHQAPIError("Missing PLAYHQ_API_KEY in Streamlit secrets.")

        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        response = requests.get(
            url,
            headers=self._headers(),
            params=params,
            timeout=self.timeout_seconds,
        )

        if response.status_code >= 400:
            raise PlayHQAPIError(
                f"PlayHQ request failed: {response.status_code} {response.text[:300]}"
            )

        return response.json()

    def get_all_pages(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        items_key: str = "data",
    ) -> list[dict[str, Any]]:
        """Fetch cursor-paginated PlayHQ responses."""
        all_items: list[dict[str, Any]] = []
        request_params = dict(params or {})

        while True:
            payload = self.get_json(path, request_params)
            page_items = payload.get(items_key, [])
            if isinstance(page_items, list):
                all_items.extend(page_items)

            metadata = payload.get("metadata", {})
            if not metadata.get("hasMore"):
                return all_items

            request_params["cursor"] = metadata.get("nextCursor")

    def get_organisation_seasons(self, organisation_id: str) -> list[dict[str, Any]]:
        return self.get_all_pages(f"/v1/organisations/{organisation_id}/seasons")

    def get_season_grades(self, season_id: str) -> list[dict[str, Any]]:
        return self.get_all_pages(f"/v1/seasons/{season_id}/grades")

    def get_grade_fixture(self, grade_id: str) -> list[dict[str, Any]]:
        return self.get_all_pages(f"/v1/grades/{grade_id}/fixture")

    def get_game_summary(self, game_id: str) -> dict[str, Any]:
        return self.get_json(f"/v1/games/{game_id}/summary")
