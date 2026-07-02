#!/usr/bin/env python3
"""Profile production-relevant Scorebook page data preparation."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Callable

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.playcricket_ingestion import metadata_mtime  # noqa: E402
from src.ui import layout  # noqa: E402
from src.utils.player_identity import get_player_profile_data, player_aliases_mtime  # noqa: E402

OUTPUT = ROOT / "data/processed/validation/scorebook_page_performance_profile.csv"
CLUBS = ["georges-river-district", "fvcc"]


def timed(fn: Callable[[], object]) -> tuple[float, object]:
    started = time.perf_counter()
    result = fn()
    return time.perf_counter() - started, result


def rows_processed(value: object) -> int:
    if isinstance(value, pd.DataFrame):
        return len(value)
    if isinstance(value, dict):
        total = 0
        for item in value.values():
            total += rows_processed(item)
        return total
    return 0


def clear_known_caches() -> None:
    for fn in [
        layout.get_hall_of_fame_data,
        layout.load_hall_of_fame_data,
        layout.load_player_profile_index,
        layout.build_approaching_milestone_watchlist,
        layout.build_achieved_milestones,
        layout.build_hall_of_fame_watch,
        layout.build_hall_of_fame_movements,
        layout.build_milestone_period_totals,
        layout.build_milestone_period_totals_by_season,
        get_player_profile_data,
    ]:
        if hasattr(fn, "clear"):
            fn.clear()


def profile_component(club_id: str, name: str, fn: Callable[[], object], notes: str = "") -> dict[str, object]:
    clear_known_caches()
    first_seconds, first_result = timed(fn)
    cached_seconds, cached_result = timed(fn)
    return {
        "club_id": club_id,
        "page_or_component": name,
        "first_run_seconds": round(first_seconds, 3),
        "cached_run_seconds": round(cached_seconds, 3),
        "rows_processed": rows_processed(cached_result if cached_result is not None else first_result),
        "notes": notes,
    }


def load_hof(club_id: str) -> dict[str, object] | None:
    return layout.get_hall_of_fame_data(
        metadata_mtime(),
        player_aliases_mtime(club_id=club_id),
        layout.HALL_OF_FAME_DATA_VERSION,
        layout.featured_record_overrides_mtime(club_id),
        club_id=club_id,
    )


def load_season_overview(club_id: str) -> dict[str, pd.DataFrame]:
    os.environ["CLUB_ID"] = club_id
    local_version = metadata_mtime()
    seasons = layout.load_local_playcricket_seasons(club_id, local_version)
    if not seasons:
        return {}
    selected = seasons[0]
    teams = layout.load_local_playcricket_teams(club_id, selected["id"], local_version)
    teams = layout.combine_grdcc_duplicate_competition_teams(layout.sort_teams_by_grade_display(teams))
    frames = layout.load_local_all_team_frames(selected["id"], teams, local_version)
    return layout.add_season_overview_detail_metrics(frames, selected, teams)


def sample_player_id(club_id: str) -> str:
    index = layout.load_player_profile_index(
        club_id,
        metadata_mtime(),
        player_aliases_mtime(club_id=club_id),
        layout.PLAYER_PROFILE_INDEX_VERSION,
    )
    if index.empty:
        return ""
    preferred = "A Clarkson" if club_id == "georges-river-district" else "Siddhanth Chaurasiya"
    scoped = index[index["name"].astype(str).str.casefold().eq(preferred.casefold())]
    return str((scoped if not scoped.empty else index).iloc[0]["id"])


def profile_player(club_id: str) -> dict[str, pd.DataFrame] | None:
    player_id = sample_player_id(club_id)
    if not player_id:
        return None
    profile = get_player_profile_data(player_id, metadata_mtime(), player_aliases_mtime(club_id=club_id), club_id=club_id)
    return layout.build_player_profile_view(profile, layout.player_profile_view_signature())


def profile_milestones(club_id: str, view: str) -> pd.DataFrame:
    hof = load_hof(club_id)
    if not hof:
        return pd.DataFrame()
    all_time = hof.get("all_time", pd.DataFrame())
    if view == "upcoming":
        active = layout.recent_active_canonical_players(hof)
        watchlist = layout.build_approaching_milestone_watchlist(all_time)
        return watchlist[watchlist["Player"].isin(active)].copy() if active and not watchlist.empty else watchlist
    if view == "achieved":
        window = layout.milestone_achievement_season_window(hof)
        return layout.build_achieved_milestones(hof, window)
    if view == "exclusive":
        return all_time
    return pd.DataFrame()


def profile_club(club_id: str) -> list[dict[str, object]]:
    os.environ["CLUB_ID"] = club_id
    rows = [
        profile_component(club_id, "HOF data build", lambda: load_hof(club_id), "get_hall_of_fame_data"),
        profile_component(club_id, "Season Overview data build", lambda: load_season_overview(club_id), "local all-team frames + detail metrics"),
        profile_component(
            club_id,
            "Player Profile index build",
            lambda: layout.load_player_profile_index(
                club_id,
                metadata_mtime(),
                player_aliases_mtime(club_id=club_id),
                layout.PLAYER_PROFILE_INDEX_VERSION,
            ),
            "dropdown source",
        ),
        profile_component(club_id, "Player Profile selected-player build", lambda: profile_player(club_id), "sample canonical player"),
        profile_component(club_id, "Milestone Upcoming build", lambda: profile_milestones(club_id, "upcoming"), "selected tab only"),
        profile_component(club_id, "Milestone Achieved build", lambda: profile_milestones(club_id, "achieved"), "selected tab only"),
        profile_component(club_id, "Milestone Exclusive Club build", lambda: profile_milestones(club_id, "exclusive"), "selected tab only"),
    ]
    return rows


def main() -> int:
    rows: list[dict[str, object]] = []
    for club_id in CLUBS:
        rows.extend(profile_club(club_id))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUTPUT, index=False)
    print(f"output={OUTPUT}")
    for row in rows:
        print(
            f"{row['club_id']} | {row['page_or_component']} | "
            f"first={row['first_run_seconds']}s cached={row['cached_run_seconds']}s rows={row['rows_processed']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
