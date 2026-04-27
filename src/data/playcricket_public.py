from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qs, urlparse

import pandas as pd
import requests


PLAYCRICKET_PUBLIC_BASE_URL = "https://grassrootsapiproxy.cricket.com.au"

SUPPORTED_STAT_CATEGORIES = {
    "batting": "batting-statistics",
    "bowling": "bowling-statistics",
    "fielding": "fielding-statistics",
    "championPlayer": "champion-points",
}


class PlayCricketPublicError(RuntimeError):
    """Raised when a public PlayCricket stats request fails."""


@dataclass(frozen=True)
class PlayCricketStatsRequest:
    grade_id: str
    team_id: str | None = None
    category: str = "batting"
    match_type_id: str | None = None


def parse_club_url(url: str) -> str:
    """Parse the organisation id from a public PlayCricket club URL."""
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]

    if len(path_parts) < 3 or path_parts[0] != "club":
        raise PlayCricketPublicError("Please paste a PlayCricket club URL.")

    return path_parts[2]


def parse_stats_url(url: str) -> PlayCricketStatsRequest:
    """Parse grade, team, category, and format filters from a PlayCricket URL."""
    parsed = urlparse(url)
    path_parts = [part for part in parsed.path.split("/") if part]
    query = parse_qs(parsed.query)

    if len(path_parts) < 2 or path_parts[0] != "grade":
        raise PlayCricketPublicError("Please paste a PlayCricket grade stats URL.")

    category = query.get("category", ["batting"])[0]
    if category not in SUPPORTED_STAT_CATEGORIES:
        raise PlayCricketPublicError(
            f"Unsupported stats category '{category}'. Use batting, bowling, fielding, or championPlayer."
        )

    return PlayCricketStatsRequest(
        grade_id=path_parts[1],
        team_id=query.get("teamId", [None])[0],
        category=category,
        match_type_id=query.get("format", [None])[0],
    )


@dataclass(frozen=True)
class PlayCricketPublicClient:
    base_url: str = PLAYCRICKET_PUBLIC_BASE_URL
    timeout_seconds: int = 30

    def get_stats(self, request: PlayCricketStatsRequest) -> list[dict[str, Any]]:
        endpoint = SUPPORTED_STAT_CATEGORIES[request.category]
        url = f"{self.base_url}/participants/grades/{request.grade_id}/{endpoint}"
        params: dict[str, str] = {"jsconfig": "eccn:true"}

        if request.team_id:
            params["teamId"] = request.team_id
        if request.match_type_id and request.match_type_id != "-1":
            params["matchTypeId"] = request.match_type_id

        response = requests.get(
            url,
            params=params,
            headers={
                "Accept": "application/json",
                "Referer": "https://play.cricket.com.au/",
                "User-Agent": "CricketClubAnalytics/0.1 public-data prototype",
            },
            timeout=self.timeout_seconds,
        )

        if response.status_code >= 400:
            raise PlayCricketPublicError(
                f"PlayCricket public request failed: {response.status_code} {response.text[:300]}"
            )

        payload = response.json()
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("participants"), list):
            return payload["participants"]

        raise PlayCricketPublicError("Unexpected PlayCricket response shape.")

    def get_organisation_seasons(self, organisation_id: str) -> list[dict[str, Any]]:
        payload = self._get_json(
            f"/fixturesladders/organisations/{organisation_id}/seasons",
            {"jsconfig": "eccn:true"},
        )
        return payload.get("seasons", [])

    def get_organisation_teams(
        self,
        organisation_id: str,
        season_id: str,
    ) -> list[dict[str, Any]]:
        payload = self._get_json(
            f"/fixturesladders/organisations/{organisation_id}/teams",
            {"seasonId": season_id, "jsconfig": "eccn:true"},
        )
        return payload.get("teams", [])

    def _get_json(self, path: str, params: dict[str, str]) -> dict[str, Any]:
        response = requests.get(
            f"{self.base_url}{path}",
            params=params,
            headers={
                "Accept": "application/json",
                "Referer": "https://play.cricket.com.au/",
                "User-Agent": "CricketClubAnalytics/0.1 public-data prototype",
            },
            timeout=self.timeout_seconds,
        )

        if response.status_code == 204:
            return {}
        if response.status_code >= 400:
            raise PlayCricketPublicError(
                f"PlayCricket public request failed: {response.status_code} {response.text[:300]}"
            )

        return response.json()


def stats_to_dataframe(stats: list[dict[str, Any]]) -> pd.DataFrame:
    """Flatten PlayCricket participant stats into a dashboard-friendly table."""
    rows = []

    for player in stats:
        row = {
            "player_id": player.get("id"),
            "player_name": format_player_name(player.get("name")),
            "short_name": player.get("shortName"),
            "club": player.get("organisation", {}).get("name"),
        }
        row.update(player.get("statistics", {}))
        rows.append(row)

    return pd.DataFrame(rows)


def format_player_name(name: str | None) -> str | None:
    """Convert PlayCricket's 'Surname, First' names into 'First Surname'."""
    if not name or "," not in name:
        return name

    surname, given_names = [part.strip() for part in name.split(",", 1)]
    if not surname or not given_names:
        return name

    return f"{given_names} {surname}"


def add_team_context(
    df: pd.DataFrame,
    team: dict[str, Any],
) -> pd.DataFrame:
    """Attach team and grade labels to a flattened stats table."""
    if df.empty:
        return df

    output = df.copy()
    grade = team.get("grade", {})
    output["team_id"] = team.get("id")
    output["team_name"] = team.get("name")
    output["grade_id"] = grade.get("id")
    output["grade_name"] = grade.get("name")
    return output
