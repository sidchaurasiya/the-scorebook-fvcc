from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import requests


PLAYCRICKET_PUBLIC_BASE_URL = "https://grassrootsapiproxy.cricket.com.au"
PUBLIC_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://play.cricket.com.au/",
    "User-Agent": "CricketClubAnalytics/0.1 match-centre-pilot polite-cache",
}


@dataclass
class RequestRecord:
    name: str
    url: str
    status_code: int | None
    file_path: str
    cached: bool = False
    match_id: str | None = None
    row_count: int | None = None
    event_count: int | None = None
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "status_code": self.status_code,
            "file_path": self.file_path,
            "cached": self.cached,
            "match_id": self.match_id,
            "row_count": self.row_count,
            "event_count": self.event_count,
            "error": self.error,
        }


@dataclass
class PilotFetchResult:
    season_id: str
    team_id: str
    raw_dir: Path
    team_matches: list[dict[str, Any]] = field(default_factory=list)
    completed_matches: list[dict[str, Any]] = field(default_factory=list)
    scorecard_paths: list[Path] = field(default_factory=list)
    officials_paths: list[Path] = field(default_factory=list)
    balls_paths: list[Path] = field(default_factory=list)
    requests: list[RequestRecord] = field(default_factory=list)


class MatchCentreFetchError(RuntimeError):
    """Raised when a public match-centre request cannot be completed."""


class PoliteMatchCentreFetcher:
    def __init__(
        self,
        *,
        base_url: str = PLAYCRICKET_PUBLIC_BASE_URL,
        timeout_seconds: int = 30,
        sleep_seconds: float = 0.85,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.sleep_seconds = sleep_seconds

    def fetch_one_team_season(self, season_id: str, team_id: str, raw_dir: Path) -> PilotFetchResult:
        raw_dir.mkdir(parents=True, exist_ok=True)
        result = PilotFetchResult(season_id=season_id, team_id=team_id, raw_dir=raw_dir)

        team_matches_path = raw_dir / f"team_matches__season={season_id}__team={team_id}.json"
        team_payload, record = self.get_json(
            f"/scores/teams/{team_id}/matches",
            {"seasonId": season_id, "jsconfig": "eccn:true"},
            team_matches_path,
            name="team_match_list",
        )
        result.requests.append(record)
        matches = team_payload.get("matches", []) if isinstance(team_payload, dict) else []
        result.team_matches = matches
        result.completed_matches = [match for match in matches if is_completed_match(match)]

        for match in result.completed_matches:
            match_id = str(match.get("id"))
            if not match_id:
                continue

            scorecard_path = raw_dir / f"match={match_id}__scorecard.json"
            scorecard_payload, scorecard_record = self.get_json(
                f"/scores/matches/{match_id}",
                {"responseModifier": "includeScorecard", "jsconfig": "eccn:true"},
                scorecard_path,
                name="match_scorecard",
                match_id=match_id,
            )
            result.requests.append(scorecard_record)
            result.scorecard_paths.append(scorecard_path)

            officials_path = raw_dir / f"match={match_id}__officials.json"
            _, officials_record = self.get_json(
                f"/scores/matches/{match_id}/officials",
                {"jsconfig": "eccn:true"},
                officials_path,
                name="match_officials",
                match_id=match_id,
            )
            result.requests.append(officials_record)
            result.officials_paths.append(officials_path)

            if isinstance(scorecard_payload, dict) and scorecard_payload.get("isBallByBall"):
                balls_path = raw_dir / f"match={match_id}__balls.json"
                _, balls_record = self.get_json(
                    f"/scores/matches/{match_id}/balls",
                    {"jsconfig": "eccn:true"},
                    balls_path,
                    name="match_balls",
                    match_id=match_id,
                )
                result.requests.append(balls_record)
                result.balls_paths.append(balls_path)

        return result

    def get_json(
        self,
        path: str,
        params: dict[str, str],
        output_path: Path,
        *,
        name: str,
        match_id: str | None = None,
    ) -> tuple[dict[str, Any], RequestRecord]:
        url = f"{self.base_url}{path}"
        prepared = requests.Request("GET", url, params=params).prepare()
        if output_path.exists():
            cached = json.loads(output_path.read_text(encoding="utf-8"))
            payload = cached.get("payload", {})
            return payload, RequestRecord(
                name=name,
                url=cached.get("request", {}).get("url", prepared.url or url),
                status_code=cached.get("request", {}).get("status_code"),
                file_path=str(output_path),
                cached=True,
                match_id=match_id,
                row_count=count_rows(payload, name),
                event_count=count_events(payload),
            )

        time.sleep(self.sleep_seconds)
        try:
            response = requests.get(
                url,
                params=params,
                headers=PUBLIC_HEADERS,
                timeout=self.timeout_seconds,
            )
            record = RequestRecord(
                name=name,
                url=response.url,
                status_code=response.status_code,
                file_path=str(output_path),
                match_id=match_id,
            )
            if response.status_code >= 400:
                record.error = response.text[:300]
                raise MatchCentreFetchError(f"Request failed: {response.status_code} {response.text[:300]}")
            payload = response.json() if response.text else {}
            record.row_count = count_rows(payload, name)
            record.event_count = count_events(payload)
            output_path.write_text(
                json.dumps(
                    {
                        "request": {
                            "name": name,
                            "url": response.url,
                            "status_code": response.status_code,
                            "fetched_at": now_iso(),
                        },
                        "payload": payload,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            return payload, record
        except (requests.RequestException, ValueError) as error:
            raise MatchCentreFetchError(str(error)) from error


def write_manifest(result: PilotFetchResult, manifest_path: Path) -> None:
    manifest = {
        "season_id": result.season_id,
        "team_id": result.team_id,
        "raw_dir": str(result.raw_dir),
        "generated_at": now_iso(),
        "total_matches_found": len(result.team_matches),
        "completed_matches": len(result.completed_matches),
        "scorecards_fetched": len(result.scorecard_paths),
        "balls_files": len(result.balls_paths),
        "officials_files": len(result.officials_paths),
        "requests": [record.as_dict() for record in result.requests],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def is_completed_match(match: dict[str, Any]) -> bool:
    return str(match.get("status", "")).upper() == "COMPLETED" or match.get("statusId") == 3


def count_rows(payload: Any, name: str) -> int | None:
    if not isinstance(payload, dict):
        return None
    if name == "team_match_list":
        return len(payload.get("matches", []) or [])
    if name == "match_scorecard":
        return len(payload.get("innings", []) or [])
    if name == "match_officials":
        return len(payload.get("officials", []) or [])
    if name == "match_balls":
        return len(payload.get("innings", []) or [])
    return None


def count_events(payload: Any) -> int | None:
    if not isinstance(payload, dict):
        return None
    if "innings" not in payload:
        return None
    return sum(len(innings.get("balls", []) or []) for innings in payload.get("innings", []) or [])


def now_iso() -> str:
    return datetime.now(UTC).isoformat()

