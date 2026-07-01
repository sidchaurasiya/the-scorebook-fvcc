from __future__ import annotations

import hashlib
import json
import random
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

from src.config.club_config import (
    get_active_club_id,
    get_data_root,
    get_feature_flag,
    get_processed_dir,
    get_processed_path,
)
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

GRDCC_EXCEL_LAST_SEASON = "Summer 1971/72"
GRDCC_PLAYCRICKET_FIRST_SEASON = "Summer 1972/73"

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
        cache_dir: Path | str = CACHE_DIR,
    ) -> None:
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.delay_range = delay_range
        self.max_retries = max_retries
        self.cache_ttl = timedelta(days=cache_ttl_days)
        self.cache_dir = Path(cache_dir)
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
        ensure_data_dirs(cache_dir=self.cache_dir)
        cache_path = self.cache_dir / f"{cache_name}.json"
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


def ensure_data_dirs(
    *,
    raw_dir: Path | str = RAW_DIR,
    processed_dir: Path | str = PROCESSED_DIR,
    cache_dir: Path | str = CACHE_DIR,
    exports_dir: Path | str = EXPORTS_DIR,
) -> None:
    for directory in [Path(raw_dir), Path(processed_dir), Path(cache_dir), Path(exports_dir)]:
        directory.mkdir(parents=True, exist_ok=True)


def local_backup_available() -> bool:
    required = [
        get_processed_path("seasons.csv"),
        get_processed_path("teams.csv"),
        get_processed_path("all_seasons_batting.csv"),
        get_processed_path("all_seasons_bowling.csv"),
        get_processed_path("all_seasons_fielding.csv"),
        active_metadata_path(),
    ]
    return all(path.exists() for path in required)


def metadata_mtime() -> float:
    path = active_metadata_path()
    return path.stat().st_mtime if path.exists() else 0.0


def read_metadata() -> dict[str, Any]:
    path = active_metadata_path()
    return _read_metadata_cached(str(path), metadata_mtime())


@st.cache_data(show_spinner=False)
def _read_metadata_cached(path_value: str, _metadata_version: float) -> dict[str, Any]:
    path = Path(path_value)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def read_processed_table(name: str) -> pd.DataFrame:
    path = get_processed_path(f"{name}.csv")
    if not path.exists():
        return pd.DataFrame()
    frame = _read_processed_table_cached(str(path), path.stat().st_mtime)
    if name in {"all_seasons_batting", "all_seasons_bowling", "all_seasons_fielding"}:
        frame = _filter_grdcc_app_facing_player_rows(frame)
    if name == "all_seasons_batting":
        frame = _filter_grdcc_app_facing_batting_rows(frame)
    if name == "all_seasons_bowling":
        frame = _filter_grdcc_app_facing_bowling_rows(frame)
    combined = _append_supplemental_processed_rows(name, frame)
    if name in {"all_seasons_batting", "all_seasons_bowling"}:
        combined = _filter_grdcc_app_facing_player_rows(combined)
    if name == "all_seasons_batting":
        combined = _filter_grdcc_app_facing_batting_rows(combined)
    if name == "all_seasons_bowling":
        combined = _filter_grdcc_app_facing_bowling_rows(combined)
    return combined


@st.cache_data(show_spinner=False)
def _read_processed_table_cached(path_value: str, _file_version: float) -> pd.DataFrame:
    path = Path(path_value)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (MemoryError, OSError, pd.errors.ParserError):
        return pd.DataFrame()


def _append_supplemental_processed_rows(name: str, frame: pd.DataFrame) -> pd.DataFrame:
    """Apply the final GRDCC source split to aggregate batting and bowling tables."""
    if not get_feature_flag("has_historical_excel", False):
        return frame
    supplemental_names = {
        "all_seasons_batting": "excel_all_seasons_batting.csv",
        "all_seasons_bowling": "excel_all_seasons_bowling.csv",
    }
    supplemental_filename = supplemental_names.get(name)
    if not supplemental_filename:
        return frame

    path = get_processed_dir() / "supplemental" / supplemental_filename
    if not path.exists():
        return frame
    supplemental = _read_processed_table_cached(str(path), path.stat().st_mtime)
    if supplemental.empty:
        return frame
    supplemental = _normalise_supplemental_numeric_columns(supplemental)
    cutoff = _grdcc_season_sort_key(GRDCC_EXCEL_LAST_SEASON)
    if "season" in frame.columns:
        frame = frame[frame["season"].map(_grdcc_season_sort_key).gt(cutoff)].copy()
    if "season" in supplemental.columns:
        supplemental = supplemental[supplemental["season"].map(_grdcc_season_sort_key).le(cutoff)].copy()
    if "source_system" not in frame.columns:
        frame = frame.copy()
        frame["source_system"] = "playcricket"
    else:
        frame["source_system"] = frame["source_system"].fillna("playcricket").replace("", "playcricket")
    if "source_system" not in supplemental.columns:
        supplemental = supplemental.copy()
        supplemental["source_system"] = "excel"
    if supplemental.empty:
        return frame
    return pd.concat([frame, supplemental], ignore_index=True, sort=False)


def _grdcc_season_sort_key(value: object) -> int:
    """Return a stable chronological key for GRDCC source-boundary comparisons."""
    label = str(value or "").strip()
    match = re.search(r"(19|20)\d{2}", label)
    if not match:
        return 999999
    year = int(match.group())
    if "winter" in label.casefold():
        return year * 10 + 1
    if "summer" in label.casefold():
        return year * 10 + 2
    return year * 10


def _filter_grdcc_app_facing_bowling_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Exclude impossible GRDCC primary bowling aggregates from client-visible records."""
    if not get_feature_flag("has_historical_excel", False) or frame.empty:
        return frame
    required = {"bowlingWickets", "bowlingRuns", "bowlingBalls"}
    if not required.issubset(frame.columns):
        return frame
    output = frame.copy()
    wickets = pd.to_numeric(output["bowlingWickets"], errors="coerce").fillna(0)
    runs = pd.to_numeric(output["bowlingRuns"], errors="coerce").fillna(0)
    balls = pd.to_numeric(output["bowlingBalls"], errors="coerce").fillna(0)
    maidens = pd.to_numeric(output.get("bowlingMaidens", pd.Series(0, index=output.index)), errors="coerce").fillna(0)
    average = runs.div(wickets.where(wickets > 0))
    economy = runs.mul(6).div(balls.where(balls > 0))
    bbi_wickets = output.get("bowlingBestInnings", pd.Series("", index=output.index)).astype(str).str.extract(r"^(\d+)[-/]", expand=False)
    bbi_wickets = pd.to_numeric(bbi_wickets, errors="coerce")

    invalid = bbi_wickets.gt(wickets) | ((balls > 0) & maidens.mul(6).gt(balls)) | (
        (wickets > 0)
        & (
            ((balls <= 0) & (wickets > 0))
            | average.le(0)
            | ((wickets >= 10) & (runs < wickets))
            | ((wickets >= 10) & average.lt(1))
            | ((balls >= 60) & economy.lt(0.5))
            | wickets.gt(balls)
        )
    )
    return output.loc[~invalid].copy()


def _filter_grdcc_app_facing_batting_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Exclude structurally impossible GRDCC batting aggregates from visible records."""
    if not get_feature_flag("has_historical_excel", False) or frame.empty:
        return frame
    required = {"battingAggregate", "battingInnings", "battingNotOuts"}
    if not required.issubset(frame.columns):
        return frame
    output = frame.copy()
    runs = pd.to_numeric(output["battingAggregate"], errors="coerce").fillna(0)
    innings = pd.to_numeric(output["battingInnings"], errors="coerce").fillna(0)
    not_outs = pd.to_numeric(output["battingNotOuts"], errors="coerce").fillna(0)
    high_score = pd.to_numeric(output.get("battingHighScore", pd.Series(pd.NA, index=output.index)), errors="coerce")
    fifties = pd.to_numeric(output.get("batting50s", pd.Series(0, index=output.index)), errors="coerce").fillna(0)
    hundreds = pd.to_numeric(output.get("batting100s", pd.Series(0, index=output.index)), errors="coerce").fillna(0)
    invalid = not_outs.gt(innings) | high_score.gt(runs) | hundreds.gt(innings) | (fifties + hundreds).gt(innings)
    return output.loc[~invalid].copy()


def _filter_grdcc_app_facing_player_rows(frame: pd.DataFrame) -> pd.DataFrame:
    """Remove hidden and structurally invalid GRDCC player labels from visible data."""
    if not get_feature_flag("has_historical_excel", False) or frame.empty:
        return frame
    name_column = next((column for column in ["canonical_player_name", "player_name", "raw_player_name"] if column in frame.columns), None)
    if name_column is None:
        return frame
    names = frame[name_column].fillna("").astype(str).str.strip()
    fallback = frame.get("player_name", pd.Series("", index=frame.index)).fillna("").astype(str).str.strip()
    names = names.where(names.ne(""), fallback)
    valid = names.str.contains(r"[A-Za-z]", regex=True) & ~names.str.fullmatch(r"\*+") & ~names.str.fullmatch(r"\d+")
    return frame.loc[valid].copy()


def _normalise_supplemental_numeric_columns(frame: pd.DataFrame) -> pd.DataFrame:
    numeric_zero_columns = [
        "matches",
        "battingInnings",
        "battingAggregate",
        "battingNotOuts",
        "battingBallsFaced",
        "batting50s",
        "batting100s",
        "batting0s",
        "battingFours",
        "battingSixes",
        "battingMinutes",
        "bowlingWickets",
        "bowlingMaidens",
        "bowlingRuns",
        "bowlingBalls",
        "bowling5WIs",
        "bowling10WMs",
        "bowlingWides",
        "bowlingNoBalls",
        "bowlingWicketsUnassisted",
    ]
    output = frame.copy()
    for column in numeric_zero_columns:
        if column in output.columns:
            output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)
    for column in ["battingHighScore", "battingAverage", "battingStrikeRate", "bowlingAverage"]:
        if column in output.columns:
            output[column] = pd.to_numeric(output[column], errors="coerce")
    return output


def active_metadata_path() -> Path:
    return get_data_root() / "metadata.json"


def refresh_playcricket_backup(
    club_id: str = DEFAULT_CLUB_ID,
    *,
    force: bool = False,
    season_limit: int | None = None,
    force_seasons: bool = False,
    force_season_ids: set[str] | None = None,
    processed_dir: Path | str | None = None,
    raw_dir: Path | str | None = None,
    metadata_path: Path | str | None = None,
    cache_dir: Path | str | None = None,
    exports_dir: Path | str | None = None,
    club_url: str | None = None,
) -> RefreshSummary:
    active_processed_dir = Path(processed_dir) if processed_dir is not None else PROCESSED_DIR
    active_raw_dir = Path(raw_dir) if raw_dir is not None else RAW_DIR
    active_metadata_path = Path(metadata_path) if metadata_path is not None else METADATA_PATH
    active_cache_dir = Path(cache_dir) if cache_dir is not None else CACHE_DIR
    active_exports_dir = Path(exports_dir) if exports_dir is not None else EXPORTS_DIR

    ensure_data_dirs(
        raw_dir=active_raw_dir,
        processed_dir=active_processed_dir,
        cache_dir=active_cache_dir,
        exports_dir=active_exports_dir,
    )
    summary = RefreshSummary(club_id=club_id, started_at=now_iso())
    fetcher = PolitePlayCricketFetcher(cache_dir=active_cache_dir)
    timestamp = file_timestamp()
    source_endpoints: list[str] = []

    force_season_ids = {str(season_id) for season_id in (force_season_ids or set()) if str(season_id).strip()}

    try:
        seasons_payload = fetcher.get_json(
            f"/fixturesladders/organisations/{club_id}/seasons",
            {"jsconfig": "eccn:true"},
            cache_name=cache_key("seasons", club_id),
            force=force or force_seasons,
        )
        write_raw_json(f"playcricket_seasons_{timestamp}.json", seasons_payload, raw_dir=active_raw_dir)
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
        force_this_season = force or str(season_id) in force_season_ids
        try:
            teams_payload = fetcher.get_json(
                f"/fixturesladders/organisations/{club_id}/teams",
                {"seasonId": season_id, "jsconfig": "eccn:true"},
                cache_name=cache_key("teams", club_id, season_id),
                force=force_this_season,
            )
            write_raw_json(
                f"playcricket_{safe_name(season_name)}_teams_{timestamp}.json",
                teams_payload,
                raw_dir=active_raw_dir,
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
                    stats = fetch_stats(fetcher, grade_id, team_id, category, force=force_this_season)
                    write_raw_json(
                        f"playcricket_{safe_name(season_name)}_{safe_name(team.get('name', team_id))}_{category}_{timestamp}.json",
                        stats,
                        raw_dir=active_raw_dir,
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

    write_processed_csv("seasons", seasons_df, processed_dir=active_processed_dir)
    write_processed_csv("teams", teams_df, processed_dir=active_processed_dir)
    for category, frame in processed.items():
        write_processed_csv(f"all_seasons_{category}", frame, processed_dir=active_processed_dir)
        summary.stat_rows[category] = len(frame)
    write_processed_csv("players", players_df, processed_dir=active_processed_dir)
    write_processed_csv("all_seasons_matches", empty_table(MATCH_COLUMNS), processed_dir=active_processed_dir)
    write_processed_csv("all_seasons_scorecard_batting", empty_table(BATTING_COLUMNS), processed_dir=active_processed_dir)
    write_processed_csv("all_seasons_scorecard_bowling", empty_table(BOWLING_COLUMNS), processed_dir=active_processed_dir)
    write_processed_csv("all_seasons_scorecard_fielding", empty_table(FIELDING_COLUMNS), processed_dir=active_processed_dir)

    summary.teams_found = len(all_teams)
    summary.live_requests = fetcher.live_requests
    summary.cache_hits = fetcher.cache_hits
    summary.completed_at = now_iso()

    metadata = {
        "club_id": club_id,
        "club_url": club_url if club_url is not None else (DEFAULT_CLUB_URL if club_id == DEFAULT_CLUB_ID else ""),
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
            "Refresh should be used sparingly; normal dashboard usage reads the active club processed data first.",
            "Public match/result/scorecard endpoints were not available without API access during implementation, so stable empty tables are created for future population.",
        ],
    }
    active_metadata_path.parent.mkdir(parents=True, exist_ok=True)
    active_metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
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


def write_raw_json(filename: str, payload: Any, *, raw_dir: Path | str = RAW_DIR) -> None:
    path = Path(raw_dir) / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_processed_csv(name: str, frame: pd.DataFrame, *, processed_dir: Path | str = PROCESSED_DIR) -> None:
    path = Path(processed_dir) / f"{name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


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
