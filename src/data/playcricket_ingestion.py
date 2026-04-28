from __future__ import annotations

import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

from src.data.playcricket_public import (
    PLAYCRICKET_PUBLIC_BASE_URL,
    PlayCricketPublicError,
    PlayCricketStatsRequest,
    SUPPORTED_STAT_CATEGORIES,
    add_team_context,
    stats_to_dataframe,
)


DATA_ROOT = Path("data")
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"
CACHE_DIR = DATA_ROOT / "cache"
EXPORTS_DIR = DATA_ROOT / "exports"
METADATA_PATH = DATA_ROOT / "metadata.json"

DEFAULT_CLUB_ID = "7b78f08d-87d8-eb11-a7ad-2818780da0cc"
DEFAULT_CLUB_URL = (
    "https://play.cricket.com.au/club/fiji-victorian-cricket-club/"
    f"{DEFAULT_CLUB_ID}?tab=info"
)
PUBLIC_HEADERS = {
    "Accept": "application/json",
    "Referer": "https://play.cricket.com.au/",
    "User-Agent": "CricketClubAnalytics/0.1 local-cache polite-refresh",
}

STAT_CATEGORIES = ("batting", "bowling", "fielding")
MATCH_COLUMNS = [
    "season",
    "match_id",
    "date",
    "team",
    "opponent",
    "venue",
    "competition",
    "result",
    "runs_for",
    "wickets_for",
    "runs_against",
    "wickets_against",
]
BATTING_COLUMNS = [
    "season",
    "match_id",
    "player_id",
    "player_name",
    "runs",
    "balls",
    "fours",
    "sixes",
    "strike_rate",
    "dismissal",
]
BOWLING_COLUMNS = [
    "season",
    "match_id",
    "player_id",
    "player_name",
    "overs",
    "maidens",
    "runs_conceded",
    "wickets",
    "wides",
    "no_balls",
    "economy",
]
FIELDING_COLUMNS = [
    "season",
    "match_id",
    "player_id",
    "player_name",
    "catches",
    "stumpings",
    "run_outs",
]


@dataclass
class RefreshSummary:
    club_id: str
    started_at: str
    completed_at: str | None = None
    seasons_found: int = 0
    teams_found: int = 0
    stat_rows: dict[str, int] = field(default_factory=dict)
    live_requests: int = 0
    cache_hits: int = 0
    failed_requests: list[dict[str, Any]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "club_id": self.club_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "seasons_found": self.seasons_found,
            "teams_found": self.teams_found,
            "stat_rows": self.stat_rows,
            "live_requests": self.live_requests,
            "cache_hits": self.cache_hits,
            "failed_requests": self.failed_requests,
        }


class PolitePlayCricketFetcher:
    """Local file cached HTTP client used only for intentional refreshes.

    Responses are cached on disk so normal dashboard use can run from local
    backup files and avoid repeatedly hitting PlayCricket. Use refresh
    sparingly, especially across all historical seasons.
    """

    def __init__(
        self,
        base_url: str = PLAYCRICKET_PUBLIC_BASE_URL,
        timeout_seconds: int = 30,
        delay_range: tuple[float, float] = (1.0, 2.0),
        max_retries: int = 3,
        cache_ttl_days: int = 30,
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.delay_range = delay_range
        self.max_retries = max_retries
        self.cache_ttl = timedelta(days=cache_ttl_days)
        self.live_requests = 0
        self.cache_hits = 0

    def get_json(
        self,
        path: str,
        params: dict[str, str],
        *,
        cache_name: str,
        force: bool = False,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        ensure_data_dirs()
        cache_path = CACHE_DIR / f"{cache_name}.json"
        cached = self._read_cache(cache_path)
        if cached is not None and not force:
            self.cache_hits += 1
            return cached["payload"]

        url = f"{self.base_url}{path}"
        last_error = None
        for attempt in range(1, self.max_retries + 1):
            self._delay()
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=PUBLIC_HEADERS,
                    timeout=self.timeout_seconds,
                )
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    wait_seconds = float(retry_after) if retry_after else 2**attempt
                    time.sleep(wait_seconds)
                    last_error = PlayCricketPublicError("PlayCricket rate limit response.")
                    continue
                if response.status_code == 204:
                    payload: dict[str, Any] | list[dict[str, Any]] = {}
                elif response.status_code >= 400:
                    raise PlayCricketPublicError(
                        f"PlayCricket public request failed: {response.status_code} {response.text[:300]}"
                    )
                else:
                    payload = response.json()

                self.live_requests += 1
                self._write_cache(cache_path, url, params, payload)
                return payload
            except (requests.RequestException, ValueError, PlayCricketPublicError) as error:
                last_error = error
                if attempt < self.max_retries:
                    time.sleep(2 ** attempt)

        raise PlayCricketPublicError(str(last_error))

    def _read_cache(self, cache_path: Path) -> dict[str, Any] | None:
        if not cache_path.exists():
            return None

        try:
            cached = json.loads(cache_path.read_text(encoding="utf-8"))
            fetched_at = datetime.fromisoformat(cached["fetched_at"])
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            return None

        if datetime.now(UTC) - fetched_at > self.cache_ttl:
            return None
        return cached

    def _write_cache(
        self,
        cache_path: Path,
        url: str,
        params: dict[str, str],
        payload: dict[str, Any] | list[dict[str, Any]],
    ) -> None:
        cache_path.write_text(
            json.dumps(
                {
                    "fetched_at": now_iso(),
                    "url": url,
                    "params": params,
                    "payload": payload,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _delay(self) -> None:
        time.sleep(random.uniform(*self.delay_range))


def ensure_data_dirs() -> None:
    for directory in [RAW_DIR, PROCESSED_DIR, CACHE_DIR, EXPORTS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)


def local_backup_available() -> bool:
    required = [
        PROCESSED_DIR / "seasons.csv",
        PROCESSED_DIR / "teams.csv",
        PROCESSED_DIR / "all_seasons_batting.csv",
        PROCESSED_DIR / "all_seasons_bowling.csv",
        PROCESSED_DIR / "all_seasons_fielding.csv",
        METADATA_PATH,
    ]
    return all(path.exists() for path in required)


def metadata_mtime() -> float:
    return METADATA_PATH.stat().st_mtime if METADATA_PATH.exists() else 0.0


def read_metadata() -> dict[str, Any]:
    return _read_metadata_cached(metadata_mtime())


@st.cache_data(show_spinner=False)
def _read_metadata_cached(_metadata_version: float) -> dict[str, Any]:
    if not METADATA_PATH.exists():
        return {}
    try:
        return json.loads(METADATA_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_processed_table(name: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    return _read_processed_table_cached(name, path.stat().st_mtime)


@st.cache_data(show_spinner=False)
def _read_processed_table_cached(name: str, _file_version: float) -> pd.DataFrame:
    path = PROCESSED_DIR / f"{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (MemoryError, OSError, pd.errors.ParserError):
        return pd.DataFrame()


def refresh_playcricket_backup(
    club_id: str = DEFAULT_CLUB_ID,
    *,
    force: bool = False,
    season_limit: int | None = None,
) -> RefreshSummary:
    ensure_data_dirs()
    summary = RefreshSummary(club_id=club_id, started_at=now_iso())
    fetcher = PolitePlayCricketFetcher()
    timestamp = file_timestamp()
    source_endpoints: list[str] = []

    try:
        seasons_payload = fetcher.get_json(
            f"/fixturesladders/organisations/{club_id}/seasons",
            {"jsconfig": "eccn:true"},
            cache_name=cache_key("seasons", club_id),
            force=force,
        )
        write_raw_json(f"playcricket_seasons_{timestamp}.json", seasons_payload)
        source_endpoints.append("/fixturesladders/organisations/{club_id}/seasons")
        seasons = seasons_payload.get("seasons", []) if isinstance(seasons_payload, dict) else []
    except PlayCricketPublicError as error:
        summary.failed_requests.append({"scope": "seasons", "error": str(error)})
        seasons = []

    if season_limit:
        seasons = seasons[:season_limit]

    summary.seasons_found = len(seasons)
    all_teams: list[dict[str, Any]] = []
    frames: dict[str, list[pd.DataFrame]] = {category: [] for category in STAT_CATEGORIES}

    for season in seasons:
        season_id = season.get("id")
        if not season_id:
            continue

        season_name = season.get("name", season_id)
        try:
            teams_payload = fetcher.get_json(
                f"/fixturesladders/organisations/{club_id}/teams",
                {"seasonId": season_id, "jsconfig": "eccn:true"},
                cache_name=cache_key("teams", club_id, season_id),
                force=force,
            )
            write_raw_json(
                f"playcricket_{safe_name(season_name)}_teams_{timestamp}.json",
                teams_payload,
            )
            source_endpoints.append("/fixturesladders/organisations/{club_id}/teams")
            teams = teams_payload.get("teams", []) if isinstance(teams_payload, dict) else []
        except PlayCricketPublicError as error:
            summary.failed_requests.append(
                {"scope": "teams", "season": season_name, "error": str(error)}
            )
            continue

        for team in teams:
            team_with_season = {**team, "season_id": season_id, "season": season_name}
            all_teams.append(team_with_season)
            grade_id = team.get("grade", {}).get("id")
            team_id = team.get("id")
            if not grade_id or not team_id:
                continue

            for category in STAT_CATEGORIES:
                try:
                    stats = fetch_stats(fetcher, grade_id, team_id, category, force=force)
                    write_raw_json(
                        f"playcricket_{safe_name(season_name)}_{safe_name(team.get('name', team_id))}_{category}_{timestamp}.json",
                        stats,
                    )
                    source_endpoints.append(
                        f"/participants/grades/{{grade_id}}/{SUPPORTED_STAT_CATEGORIES[category]}"
                    )
                    frame = stats_to_dataframe(stats)
                    frame = add_team_context(frame, team)
                    frame["season_id"] = season_id
                    frame["season"] = season_name
                    frame["season_start_date"] = season.get("startDate")
                    frame["competition_name"] = (
                        team.get("grade", {}).get("owningOrganisation", {}).get("name")
                    )
                    frames[category].append(frame)
                except PlayCricketPublicError as error:
                    summary.failed_requests.append(
                        {
                            "scope": category,
                            "season": season_name,
                            "team": team.get("name"),
                            "error": str(error),
                        }
                    )

    processed = {
        category: pd.concat(category_frames, ignore_index=True)
        if category_frames
        else pd.DataFrame()
        for category, category_frames in frames.items()
    }
    seasons_df = normalize_seasons(seasons)
    teams_df = normalize_teams(all_teams)
    players_df = normalize_players(processed)

    write_processed_csv("seasons", seasons_df)
    write_processed_csv("teams", teams_df)
    for category, frame in processed.items():
        write_processed_csv(f"all_seasons_{category}", frame)
        summary.stat_rows[category] = len(frame)
    write_processed_csv("players", players_df)
    write_processed_csv("all_seasons_matches", empty_table(MATCH_COLUMNS))
    write_processed_csv("all_seasons_scorecard_batting", empty_table(BATTING_COLUMNS))
    write_processed_csv("all_seasons_scorecard_bowling", empty_table(BOWLING_COLUMNS))
    write_processed_csv("all_seasons_scorecard_fielding", empty_table(FIELDING_COLUMNS))

    summary.teams_found = len(all_teams)
    summary.live_requests = fetcher.live_requests
    summary.cache_hits = fetcher.cache_hits
    summary.completed_at = now_iso()

    metadata = {
        "club_id": club_id,
        "club_url": DEFAULT_CLUB_URL,
        "seasons_fetched": seasons_df.to_dict("records"),
        "fetch_date_time": summary.completed_at,
        "last_successful_refresh_time": summary.completed_at
        if not summary.failed_requests or any(summary.stat_rows.values())
        else None,
        "source_endpoints_used": sorted(set(source_endpoints)),
        "matches_fetched": 0,
        "players_fetched": len(players_df),
        "teams_fetched": len(teams_df),
        "stat_rows": summary.stat_rows,
        "live_requests": summary.live_requests,
        "cache_hits": summary.cache_hits,
        "failed_requests": summary.failed_requests,
        "notes": [
            "Public batting, bowling, and fielding stats are backed up locally to reduce PlayCricket load.",
            "Refresh should be used sparingly; normal dashboard usage reads data/processed first.",
            "Public match/result/scorecard endpoints were not available without API access during implementation, so stable empty tables are created for future population.",
        ],
    }
    METADATA_PATH.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return summary


def fetch_stats(
    fetcher: PolitePlayCricketFetcher,
    grade_id: str,
    team_id: str,
    category: str,
    *,
    force: bool,
) -> list[dict[str, Any]]:
    endpoint = SUPPORTED_STAT_CATEGORIES[category]
    payload = fetcher.get_json(
        f"/participants/grades/{grade_id}/{endpoint}",
        {"teamId": team_id, "jsconfig": "eccn:true"},
        cache_name=cache_key("stats", grade_id, team_id, category),
        force=force,
    )
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("participants"), list):
        return payload["participants"]
    raise PlayCricketPublicError("Unexpected PlayCricket response shape.")


def normalize_seasons(seasons: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for season in seasons:
        rows.append(
            {
                "id": season.get("id"),
                "name": season.get("name"),
                "startDate": season.get("startDate"),
                "isCurrentSeason": bool(season.get("isCurrentSeason")),
                "classification": json.dumps(season.get("classification", [])),
            }
        )
    return pd.DataFrame(rows)


def normalize_teams(teams: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for team in teams:
        grade = team.get("grade", {})
        owning_org = grade.get("owningOrganisation", {})
        rows.append(
            {
                "season_id": team.get("season_id"),
                "season": team.get("season"),
                "team_id": team.get("id"),
                "team_name": team.get("name"),
                "grade_id": grade.get("id"),
                "grade_name": grade.get("name"),
                "competition_id": owning_org.get("id"),
                "competition_name": owning_org.get("name"),
            }
        )
    return pd.DataFrame(rows)


def normalize_players(processed: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frames = []
    for frame in processed.values():
        if not frame.empty and {"player_id", "player_name"}.issubset(frame.columns):
            frames.append(frame[["player_id", "player_name", "season", "team_name"]].copy())

    if not frames:
        return pd.DataFrame(columns=["player_id", "player_name", "seasons_played", "teams_played_for"])

    players = pd.concat(frames, ignore_index=True).drop_duplicates()
    players["_key"] = players["player_id"].fillna("").astype(str)
    players["_key"] = players["_key"].where(
        players["_key"].str.strip() != "",
        players["player_name"].fillna("").astype(str).str.casefold(),
    )
    rows = []
    for _, group in players.groupby("_key", dropna=False, sort=False):
        rows.append(
            {
                "player_id": first_non_empty(group["player_id"]),
                "player_name": first_non_empty(group["player_name"]),
                "seasons_played": " | ".join(sorted(set(group["season"].dropna().astype(str)))),
                "teams_played_for": " | ".join(sorted(set(group["team_name"].dropna().astype(str)))),
            }
        )
    return pd.DataFrame(rows)


def write_raw_json(filename: str, payload: Any) -> None:
    (RAW_DIR / filename).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_processed_csv(name: str, frame: pd.DataFrame) -> None:
    frame.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)


def empty_table(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def first_non_empty(values: pd.Series) -> object:
    clean = values.dropna()
    clean = clean[clean.astype(str).str.strip() != ""]
    return clean.iloc[0] if not clean.empty else None


def cache_key(*parts: object) -> str:
    raw = "|".join(str(part) for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def safe_name(value: object) -> str:
    clean = "".join(char if char.isalnum() else "_" for char in str(value).lower())
    return "_".join(part for part in clean.split("_") if part)[:90]


def file_timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()
