import base64
import html
import os
import re
import time
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from src.analytics.playcricket_stats import (
    add_batting_display_columns,
    combine_player_rows,
    top_rows,
)
from src.data.playcricket_public import (
    PlayCricketPublicClient,
    PlayCricketPublicError,
    PlayCricketStatsRequest,
    add_team_context,
    parse_club_url,
    stats_to_dataframe,
)
from src.data.playcricket_ingestion import (
    DEFAULT_CLUB_ID,
    DEFAULT_CLUB_URL,
    local_backup_available,
    metadata_mtime,
    read_metadata,
    read_processed_table,
    refresh_playcricket_backup,
)
from src.ui.theme import inject_theme
from src.utils.player_identity import (
    DUPLICATE_AUDIT_PATH,
    EXPORTS_DIR,
    VALIDATION_COLUMNS,
    active_aliases,
    apply_player_identity_mapping,
    canonical_group_key,
    display_player_name,
    ensure_identity_exports,
    ensure_player_alias_mappings,
    get_player_profile_data,
    load_player_aliases,
    load_player_merge_validation,
    make_player_slug,
    player_aliases_mtime,
    rebuild_canonical_processed_tables,
)
from src.utils.team_grade import (
    apply_team_grade_display_columns,
    build_team_grade_display,
    canonical_grade_label,
    clean_grade_name,
    clean_team_name,
    export_team_grade_display_audit,
    grade_sort_key,
)


APP_ROOT = Path(__file__).resolve().parents[2]
ICON_ASSET_DIR = APP_ROOT / "assets" / "icons"
DEBUG_BIGGEST_IMPROVERS_PATH = APP_ROOT / "data" / "debug_biggest_improvers.csv"
DEBUG_HOF_TIMINGS = os.getenv("FVCC_DEBUG_TIMINGS") == "1"


def log_hof_timing(label: str, started_at: float) -> None:
    if DEBUG_HOF_TIMINGS:
        print(f"[hall-of-fame] {label}: {(time.perf_counter() - started_at) * 1000:.1f} ms")


def sync_selected_page(source_key: str) -> None:
    st.session_state["selected_page_label"] = st.session_state[source_key]


def render_page() -> None:
    """Render the dashboard."""
    inject_theme()
    selected_page = render_sidebar()
    if selected_page == "Hall of Fame":
        render_hall_of_fame_page()
    elif selected_page == "Season Overview":
        dashboard_data = render_data_source_panel()
        render_overview(dashboard_data)
    elif selected_page == "Milestone":
        render_approaching_milestones_page()
    elif selected_page == "Player Profile":
        render_player_profile_page()
    else:
        render_hall_of_fame_page()
    render_mobile_page_footer()


def render_sidebar() -> str:
    page_labels = [
        "♕ Hall of Fame",
        "⌂ Season Overview",
        "☆ Milestone",
        "♙ Player Profile",
    ]
    if "selected_page_label" not in st.session_state:
        st.session_state["selected_page_label"] = page_labels[0]

    current_label = st.session_state.get("selected_page_label", page_labels[0])
    if current_label not in page_labels:
        current_label = page_labels[0]
        st.session_state["selected_page_label"] = current_label
    for widget_key in ["mobile_navigation", "main_navigation"]:
        if st.session_state.get(widget_key) != current_label:
            st.session_state[widget_key] = current_label

    with st.container(key="mobile_nav_fallback"):
        st.markdown(
            """
            <details class="mobile-nav-help">
                <summary>
                    <span class="mobile-nav-label">Choose a page</span>
                    <span class="mobile-info-icon">ⓘ</span>
                </summary>
                <div class="mobile-nav-help-panel">
                    <p><strong>Hall of Fame 🏆</strong><br>All-time club records, leaders, and iconic performances.</p>
                    <p><strong>Season Overview 📊</strong><br>Season stats, team leaders, and detailed batting/bowling/fielding tables.</p>
                    <p><strong>Milestone 💪</strong><br>Active players closing in on major club milestones.</p>
                    <p><strong>Player Profile 🏏</strong><br>Search any player and view their career record.</p>
                </div>
            </details>
            """,
            unsafe_allow_html=True,
        )
        st.selectbox(
            "Choose a page",
            page_labels,
            index=page_labels.index(current_label),
            key="mobile_navigation",
            label_visibility="collapsed",
            on_change=sync_selected_page,
            args=("mobile_navigation",),
        )

    st.sidebar.markdown(
        """
        <div class="side-brand">
            <div class="side-shield">FV</div>
            <div>
                <div class="side-title">FVCC</div>
                <div class="side-subtitle">Stats Hub</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    selected_label = st.sidebar.radio(
        "Navigation",
        page_labels,
        index=page_labels.index(st.session_state.get("selected_page_label", page_labels[0])),
        label_visibility="collapsed",
        key="main_navigation",
        on_change=sync_selected_page,
        args=("main_navigation",),
    )
    st.session_state["selected_page_label"] = selected_label
    st.sidebar.markdown(
        """
        <div class="side-footer">
            <div class="side-footer-label">App created by</div>
            <div class="side-footer-names">Siddhanth Chaurasiya |<br>Preet Kaur</div>
            <div class="side-footer-contact">
                <div>For feedback/enquiries:</div>
                <a href="mailto:siddhanthchaurasiya@gmail.com">siddhanthchaurasiya@gmail.com</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    return selected_label.split(" ", 1)[1]


def render_mobile_page_footer() -> None:
    st.markdown(
        """
        <div class="mobile-page-footer">
            <div class="mobile-footer-label">App created by</div>
            <div class="mobile-footer-names">Siddhanth Chaurasiya |<br>Preet Kaur</div>
            <div class="mobile-footer-contact">
                <div>For feedback/enquiries:</div>
                <a href="mailto:siddhanthchaurasiya@gmail.com">siddhanthchaurasiya@gmail.com</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_data_refresh_control() -> None:
    with st.sidebar.expander("Data refresh", expanded=False):
        st.caption(
            "The app uses local backup files first. Refresh only when you want to call PlayCricket and update the backup."
        )
        force_refresh = st.checkbox(
            "Force full refresh",
            value=False,
            help="Leave this off to reuse cached responses and fetch only missing or stale data.",
        )
        if st.button("Refresh PlayCricket Data", use_container_width=True):
            with st.spinner("Refreshing PlayCricket data politely. This can take a while across many seasons."):
                summary = refresh_playcricket_backup(DEFAULT_CLUB_ID, force=force_refresh)
            st.cache_data.clear()
            st.success(
                f"Refresh complete: {summary.seasons_found} seasons, "
                f"{summary.teams_found} teams, {summary.live_requests} live requests, "
                f"{summary.cache_hits} cache hits."
            )
            if summary.failed_requests:
                st.warning(f"{len(summary.failed_requests)} requests failed and were logged in data/metadata.json.")


def render_data_source_panel() -> dict[str, object] | None:
    club_url = DEFAULT_CLUB_URL
    using_local_backup = local_backup_available()
    local_version = metadata_mtime()

    try:
        organisation_id = parse_club_url(club_url)
        if using_local_backup:
            seasons = load_local_playcricket_seasons(local_version)
        else:
            seasons = load_public_playcricket_seasons(organisation_id)
    except PlayCricketPublicError as error:
        if local_backup_available():
            using_local_backup = True
            local_version = metadata_mtime()
            seasons = load_local_playcricket_seasons(local_version)
            st.warning(f"Using local backup from {backup_timestamp_label()}.")
        else:
            st.error(str(error))
            seasons = []

    if not seasons:
        st.warning("No local backup is available yet. Use the sidebar refresh button to create one.")
        return None

    current_season_index = next(
        (index for index, season in enumerate(seasons) if season.get("isCurrentSeason")),
        0,
    )

    with st.container(key="season_controls"):
        season_col, team_col = st.columns([0.9, 1.35], gap="large")
        with season_col:
            st.markdown('<div class="simple-filter-label">Select season</div>', unsafe_allow_html=True)
            selected_season = st.selectbox(
                "Season",
                seasons,
                index=current_season_index,
                format_func=lambda season: season["name"],
                label_visibility="collapsed",
            )

        try:
            if using_local_backup:
                teams = load_local_playcricket_teams(selected_season["id"], local_version)
            else:
                teams = load_public_playcricket_teams(
                    organisation_id,
                    selected_season["id"],
                )
        except PlayCricketPublicError as error:
            if local_backup_available():
                using_local_backup = True
                local_version = metadata_mtime()
                teams = load_local_playcricket_teams(selected_season["id"], local_version)
                st.warning(f"Using local backup from {backup_timestamp_label()}.")
            else:
                st.error(str(error))
                teams = []

        if not teams:
            st.warning("No teams found for this club and season.")
            return None

        all_teams_option = {
            "id": "__all_teams__",
            "name": "All teams",
            "grade": {"id": "__all_grades__", "name": "Whole club"},
        }
        teams = sort_teams_by_grade_display(teams)
        team_options = [all_teams_option, *teams]

        with team_col:
            st.markdown('<div class="simple-filter-label">Select team/grade</div>', unsafe_allow_html=True)
            selected_team = st.selectbox(
                "Team",
                team_options,
                format_func=format_team_option,
                label_visibility="collapsed",
            )

        is_all_teams = selected_team["id"] == "__all_teams__"
        grade = selected_team.get("grade", {})
        context_description = build_context_description(
            selected_season,
            selected_team,
            is_all_teams,
        )

    with st.container(key="header_intro"):
        st.markdown(
            f"""
            <div class="seasons-page"></div>
            <h1 class="page-title">Season Overview 📊</h1>
            <div class="club-label">Fiji Victorian Cricket Club</div>
            <div class="page-subtitle">Track team performance, player leaders, and season-by-season club trends.</div>
            <div class="page-note">{html.escape(context_description)}</div>
            """,
            unsafe_allow_html=True,
        )

    try:
        if is_all_teams:
            dashboard_frames = (
                load_local_all_team_frames(selected_season["id"], teams, local_version)
                if using_local_backup
                else load_all_team_frames(teams)
            )
            request = None
        else:
            request = PlayCricketStatsRequest(
                grade_id=grade["id"],
                team_id=selected_team["id"],
                category="batting",
            )
            dashboard_frames = (
                load_local_single_team_frames(selected_season["id"], selected_team, local_version)
                if using_local_backup
                else load_single_team_frames(selected_team)
            )
    except PlayCricketPublicError as error:
        if local_backup_available():
            st.warning(f"Using local backup from {backup_timestamp_label()}.")
            dashboard_frames = (
                load_local_all_team_frames(selected_season["id"], teams, local_version)
                if is_all_teams
                else load_local_single_team_frames(selected_season["id"], selected_team, local_version)
            )
            request = None
        else:
            st.error(str(error))
            return None

    return {
        "request": request,
        "season": selected_season,
        "team": selected_team,
        "teams": teams if is_all_teams else [selected_team],
        "is_all_teams": is_all_teams,
        "using_local_backup": using_local_backup,
        "backup_timestamp": backup_timestamp_label() if using_local_backup else None,
        "context_description": context_description,
        "context_label": (
            f"{len(teams)} teams across {selected_season['name']}"
            if is_all_teams
            else format_team_option(selected_team)
        ),
        **dashboard_frames,
    }


@st.cache_data(ttl=60 * 60)
def load_public_playcricket_stats(
    grade_id: str,
    team_id: str | None,
    category: str,
    match_type_id: str | None,
) -> list[dict]:
    client = PlayCricketPublicClient()
    return client.get_stats(
        PlayCricketStatsRequest(
            grade_id=grade_id,
            team_id=team_id,
            category=category,
            match_type_id=match_type_id,
        )
    )


@st.cache_data(ttl=60 * 60)
def load_public_playcricket_seasons(organisation_id: str) -> list[dict]:
    client = PlayCricketPublicClient()
    return client.get_organisation_seasons(organisation_id)


@st.cache_data(ttl=60 * 60)
def load_public_playcricket_teams(
    organisation_id: str,
    season_id: str,
) -> list[dict]:
    client = PlayCricketPublicClient()
    return client.get_organisation_teams(organisation_id, season_id)


@st.cache_data
def load_local_playcricket_seasons(_local_version: float) -> list[dict]:
    seasons_df = read_processed_table("seasons")
    if seasons_df.empty:
        return []

    seasons = []
    for row in seasons_df.to_dict("records"):
        seasons.append(
            {
                "id": row.get("id"),
                "name": row.get("name"),
                "startDate": row.get("startDate"),
                "isCurrentSeason": parse_bool(row.get("isCurrentSeason")),
            }
        )
    return seasons


@st.cache_data
def load_local_playcricket_teams(season_id: str, _local_version: float) -> list[dict]:
    teams_df = read_processed_table("teams")
    if teams_df.empty:
        return []

    teams_df = teams_df[teams_df["season_id"].astype(str) == str(season_id)]
    teams = []
    for row in teams_df.to_dict("records"):
        teams.append(
            {
                "id": row.get("team_id"),
                "name": row.get("team_name"),
                "grade": {
                    "id": row.get("grade_id"),
                    "name": row.get("grade_name"),
                    "owningOrganisation": {
                        "id": row.get("competition_id"),
                        "name": row.get("competition_name"),
                    },
                },
            }
        )
    return teams


def sort_teams_by_grade_display(teams: list[dict]) -> list[dict]:
    return sorted(
        teams,
        key=lambda team: (
            grade_sort_key(team_card_title(team)),
            str(team_card_title(team)).casefold(),
        ),
    )


@st.cache_data
def load_local_category_frame(
    category: str,
    season_id: str,
    team_id: str | None,
    _local_version: float,
    _identity_version: float | None = None,
) -> pd.DataFrame:
    frame = read_processed_table(f"all_seasons_{category}")
    if frame.empty:
        return frame
    if "season_id" in frame:
        frame = frame[frame["season_id"].astype(str) == str(season_id)]
    if team_id and "team_id" in frame:
        frame = frame[frame["team_id"].astype(str) == str(team_id)]
    return apply_team_grade_display_columns(apply_player_identity_mapping(frame.copy(), load_player_aliases()))


def load_local_single_team_frames(
    season_id: str,
    team: dict,
    local_version: float,
) -> dict[str, pd.DataFrame]:
    identity_version = player_aliases_mtime()
    batting = load_local_category_frame("batting", season_id, team["id"], local_version, identity_version)
    bowling = load_local_category_frame("bowling", season_id, team["id"], local_version, identity_version)
    fielding = load_local_category_frame("fielding", season_id, team["id"], local_version, identity_version)
    return {
        "batting": add_batting_display_columns(batting),
        "bowling": bowling,
        "fielding": fielding,
        "team_batting": add_batting_display_columns(batting),
        "team_bowling": bowling,
        "team_fielding": fielding,
    }


def load_local_all_team_frames(
    season_id: str,
    teams: list[dict],
    local_version: float,
) -> dict[str, pd.DataFrame]:
    team_ids = {str(team["id"]) for team in teams}
    identity_version = player_aliases_mtime()
    frames = {}
    for category in ["batting", "bowling", "fielding"]:
        frame = load_local_category_frame(category, season_id, None, local_version, identity_version)
        if not frame.empty and "team_id" in frame:
            frame = frame[frame["team_id"].astype(str).isin(team_ids)]
        frames[category] = combine_player_rows(frame, category)

    return {
        "batting": add_batting_display_columns(frames["batting"]),
        "bowling": frames["bowling"],
        "fielding": frames["fielding"],
        "team_batting": add_batting_display_columns(frame_for_team_scope("batting", season_id, team_ids, local_version, identity_version)),
        "team_bowling": frame_for_team_scope("bowling", season_id, team_ids, local_version, identity_version),
        "team_fielding": frame_for_team_scope("fielding", season_id, team_ids, local_version, identity_version),
    }


def frame_for_team_scope(
    category: str,
    season_id: str,
    team_ids: set[str],
    local_version: float,
    identity_version: float | None = None,
) -> pd.DataFrame:
    frame = load_local_category_frame(category, season_id, None, local_version, identity_version)
    if not frame.empty and "team_id" in frame:
        frame = frame[frame["team_id"].astype(str).isin(team_ids)]
    return frame.copy()


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes"}


def backup_timestamp_label() -> str:
    metadata = read_metadata()
    return str(
        metadata.get("last_successful_refresh_time")
        or metadata.get("fetch_date_time")
        or "unknown time"
    )


def format_team_option(team: dict) -> str:
    if team["id"] == "__all_teams__":
        return "All teams - Whole club"
    return team_card_title(team)


def build_context_description(
    season: dict,
    team: dict,
    is_all_teams: bool,
) -> str:
    if is_all_teams:
        scope = "All teams • Whole club"
    else:
        scope = team_card_title(team)
    return f"Showing data for {season.get('name', '-')} • {scope}"


def load_single_team_frames(team: dict) -> dict[str, pd.DataFrame]:
    grade = team.get("grade", {})
    batting = load_team_category_frame(team, grade["id"], "batting")
    bowling = load_team_category_frame(team, grade["id"], "bowling")
    fielding = load_team_category_frame(team, grade["id"], "fielding")
    return {
        "batting": add_batting_display_columns(batting),
        "bowling": bowling,
        "fielding": fielding,
        "team_batting": add_batting_display_columns(batting),
        "team_bowling": bowling,
        "team_fielding": fielding,
    }


def load_all_team_frames(teams: list[dict]) -> dict[str, pd.DataFrame]:
    frames_by_category = {
        "batting": [],
        "bowling": [],
        "fielding": [],
    }

    progress = st.progress(0, text="Loading all teams...")
    total_requests = len(teams) * len(frames_by_category)
    completed = 0

    for team in teams:
        grade = team.get("grade", {})
        grade_id = grade.get("id")
        if not grade_id:
            continue

        for category in frames_by_category:
            frames_by_category[category].append(
                load_team_category_frame(team, grade_id, category)
            )
            completed += 1
            progress.progress(
                completed / total_requests,
                text=f"Loaded {completed} of {total_requests} team stat groups...",
            )

    progress.empty()
    team_batting = combine_frames(frames_by_category["batting"])
    team_bowling = combine_frames(frames_by_category["bowling"])
    team_fielding = combine_frames(frames_by_category["fielding"])
    batting = combine_player_rows(team_batting, "batting")
    bowling = combine_player_rows(team_bowling, "bowling")
    fielding = combine_player_rows(team_fielding, "fielding")

    return {
        "batting": add_batting_display_columns(batting),
        "bowling": bowling,
        "fielding": fielding,
        "team_batting": add_batting_display_columns(team_batting),
        "team_bowling": team_bowling,
        "team_fielding": team_fielding,
    }


def load_team_category_frame(
    team: dict,
    grade_id: str,
    category: str,
) -> pd.DataFrame:
    stats = load_public_playcricket_stats(
        grade_id,
        team["id"],
        category,
        None,
    )
    return add_team_context(stats_to_dataframe(stats), team)


def combine_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
    valid_frames = [frame for frame in frames if not frame.empty]
    if not valid_frames:
        return pd.DataFrame()

    return pd.concat(valid_frames, ignore_index=True)


def render_overview(dashboard_data: dict[str, object] | None) -> None:
    if not dashboard_data:
        st.info("Load public PlayCricket stats to view the dashboard.")
        return

    render_overall_section(dashboard_data)
    render_team_specific_leaders(dashboard_data)
    render_full_stats_section(dashboard_data)


def render_hall_of_fame_page() -> None:
    started_at = time.perf_counter()
    hall_of_fame_data = get_hall_of_fame_data(metadata_mtime(), player_aliases_mtime())
    log_hof_timing("load prepared Hall of Fame data", started_at)
    if hall_of_fame_data is None:
        st.info("Historical data is not available yet. Refresh local backup to build the Hall of Fame.")
        return

    st.markdown(
        """
        <div class="hall-of-fame-page"></div>
        <h1 class="page-title">Hall of Fame 🏆</h1>
        <div class="club-label">Fiji Victorian Cricket Club</div>
        <div class="page-subtitle">The players who shaped the club’s history.</div>
        <div class="page-note">Players with multiple PlayCricket profiles are merged into one profile.</div>
        """,
        unsafe_allow_html=True,
    )
    render_hall_of_fame_kpis(hall_of_fame_data["kpis"])
    render_hall_of_fame_leaders(hall_of_fame_data["all_time"])
    render_match_winning_performances(hall_of_fame_data)
    render_record_holders(hall_of_fame_data)
    render_best_ever_seasons(hall_of_fame_data)
    render_detailed_all_time_records(hall_of_fame_data["detailed_tables"])


def render_approaching_milestones_page() -> None:
    historical_data = load_hall_of_fame_data(metadata_mtime(), player_aliases_mtime())
    if historical_data is None:
        st.info("Historical data is not available yet. Refresh local backup to build the milestone watchlist.")
        return

    active_players = recent_active_canonical_players(historical_data)
    watchlist = build_approaching_milestone_watchlist(historical_data["all_time"])
    if active_players:
        watchlist = watchlist[watchlist["Player"].isin(active_players)].copy()
    st.markdown(
        """
        <div class="near-milestones-page"></div>
        <h1 class="page-title">Players closing in on major club milestones 🎯</h1>
        <div class="club-label">Fiji Victorian Cricket Club</div>
        <div class="page-subtitle">Showing active players only — players who have appeared for FVCC in the last 3 seasons.</div>
        """,
        unsafe_allow_html=True,
    )
    render_career_milestone_cards(watchlist)
    render_milestone_club(historical_data["all_time"])


def render_identity_info_note() -> None:
    st.markdown(
        """
        <div class="identity-note">
            Records are calculated using canonical player names. Raw PlayCricket profiles are preserved for audit.
        </div>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=False)
def load_hall_of_fame_data(_local_version: float, _identity_version: float | None = None) -> dict[str, object] | None:
    started_at = time.perf_counter()
    batting_raw = read_processed_table("all_seasons_batting")
    bowling_raw = read_processed_table("all_seasons_bowling")
    fielding_raw = read_processed_table("all_seasons_fielding")
    seasons = read_processed_table("seasons")
    players = read_processed_table("players")
    log_hof_timing("load historical local data", started_at)

    if batting_raw.empty and bowling_raw.empty and fielding_raw.empty:
        return None

    started_at = time.perf_counter()
    batting_raw = normalise_player_names(batting_raw)
    bowling_raw = normalise_player_names(bowling_raw)
    fielding_raw = normalise_player_names(fielding_raw)
    aliases = load_player_aliases()
    batting_raw = apply_player_identity_mapping(batting_raw, aliases)
    bowling_raw = apply_player_identity_mapping(bowling_raw, aliases)
    fielding_raw = apply_player_identity_mapping(fielding_raw, aliases)
    batting_raw = apply_team_grade_display_columns(batting_raw)
    bowling_raw = apply_team_grade_display_columns(bowling_raw)
    fielding_raw = apply_team_grade_display_columns(fielding_raw)
    export_team_grade_display_audit([batting_raw, bowling_raw, fielding_raw])
    log_hof_timing("apply canonical player and team-grade mapping", started_at)

    started_at = time.perf_counter()
    identity_source = pd.concat(
        [
            identity_export_frame(batting_raw, "batting"),
            identity_export_frame(bowling_raw, "bowling"),
            identity_export_frame(fielding_raw, "fielding"),
        ],
        ignore_index=True,
    )
    mapping_update = ensure_player_alias_mappings(identity_source)
    if mapping_update["added"]:
        rebuild_canonical_processed_tables()
    aliases = load_player_aliases()
    batting_raw = apply_player_identity_mapping(batting_raw, aliases)
    bowling_raw = apply_player_identity_mapping(bowling_raw, aliases)
    fielding_raw = apply_player_identity_mapping(fielding_raw, aliases)
    identity_source = pd.concat(
        [
            identity_export_frame(batting_raw, "batting"),
            identity_export_frame(bowling_raw, "bowling"),
            identity_export_frame(fielding_raw, "fielding"),
        ],
        ignore_index=True,
    )
    identity_exports = ensure_identity_exports(identity_source, aliases)
    identity_exports["mapping_rows_added"] = mapping_update["added"]
    identity_exports["mapping_conflicts"] = mapping_update["conflicts"]

    batting = add_batting_display_columns(combine_player_rows(batting_raw, "batting"))
    bowling = combine_player_rows(bowling_raw, "bowling")
    fielding = add_display_stat_aliases(combine_player_rows(add_display_stat_aliases(fielding_raw), "fielding"))
    log_hof_timing("build canonical category summaries", started_at)

    started_at = time.perf_counter()
    all_time = build_all_time_player_table(batting_raw, bowling_raw, fielding_raw, batting, bowling, fielding)
    log_hof_timing("build all-time player summary", started_at)

    return {
        "batting_raw": add_batting_display_columns(batting_raw),
        "bowling_raw": bowling_raw,
        "fielding_raw": add_display_stat_aliases(fielding_raw),
        "batting": batting,
        "bowling": bowling,
        "fielding": fielding,
        "all_time": all_time,
        "total_seasons": int(seasons["id"].nunique()) if not seasons.empty and "id" in seasons else 0,
        "total_players": int(players["player_id"].nunique()) if not players.empty and "player_id" in players else count_unique_players([batting_raw, bowling_raw, fielding_raw]),
        "total_matches": estimate_historical_matches(batting_raw, bowling_raw, fielding_raw),
        "total_runs": int(pd.to_numeric(batting.get("battingAggregate"), errors="coerce").sum()) if not batting.empty else 0,
        "total_wickets": int(pd.to_numeric(bowling.get("bowlingWickets"), errors="coerce").sum()) if not bowling.empty else 0,
        "identity_exports": identity_exports,
    }


@st.cache_data(show_spinner=False)
def get_hall_of_fame_data(_local_version: float, _identity_version: float | None = None) -> dict[str, object] | None:
    started_at = time.perf_counter()
    historical_data = load_hall_of_fame_data(_local_version, _identity_version)
    log_hof_timing("load historical data", started_at)
    if historical_data is None:
        return None

    started_at = time.perf_counter()
    all_time = historical_data["all_time"].copy()
    log_hof_timing("copy all-time summary", started_at)

    started_at = time.perf_counter()
    record_holder_cards = build_record_holder_cards(
        {
            "batting_raw": historical_data["batting_raw"].copy(),
            "bowling_raw": historical_data["bowling_raw"].copy(),
            "all_time": all_time.copy(),
        }
    )
    log_hof_timing("build Hall of Fame record holders", started_at)

    started_at = time.perf_counter()
    iconic_batting = top_highest_scores(historical_data["batting_raw"], limit=10)
    iconic_bowling = top_best_bowling_innings(historical_data["bowling_raw"], limit=10)
    log_hof_timing("build iconic performances", started_at)

    started_at = time.perf_counter()
    best_batting = best_batting_season(historical_data["batting_raw"])
    best_bowling = best_bowling_season(historical_data["bowling_raw"])
    log_hof_timing("build Greatest Individual Seasons", started_at)

    started_at = time.perf_counter()
    detailed_tables = {
        "batting": format_all_time_batting_table(all_time),
        "bowling": format_all_time_bowling_table(all_time),
        "fielding": format_all_time_fielding_table(all_time),
    }
    log_hof_timing("build Detailed All-Time Records Batting/Bowling/Fielding", started_at)

    return {
        "kpis": {
            "total_seasons": historical_data["total_seasons"],
            "total_players": historical_data["total_players"],
            "total_matches": historical_data["total_matches"],
        },
        "all_time": all_time,
        "batting_raw": historical_data["batting_raw"].copy(),
        "bowling_raw": historical_data["bowling_raw"].copy(),
        "fielding_raw": historical_data["fielding_raw"].copy(),
        "record_holder_cards": record_holder_cards,
        "iconic_batting": iconic_batting.copy(),
        "iconic_bowling": iconic_bowling.copy(),
        "best_batting_season": best_batting,
        "best_bowling_season": best_bowling,
        "detailed_tables": {key: value.copy() for key, value in detailed_tables.items()},
    }


def normalise_player_names(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "player_name" not in df:
        return df
    output = df.copy()
    output["player_name"] = output["player_name"].astype(str).str.replace(r"\s+", " ", regex=True).str.strip()
    return output


def identity_export_frame(df: pd.DataFrame, source: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    output = df.copy()
    output["identity_source"] = source
    return output


def count_unique_players(frames: list[pd.DataFrame]) -> int:
    keys = set()
    for frame in frames:
        if not frame.empty:
            keys.update(player_keys(frame).dropna().tolist())
    return len(keys)


def player_keys(df: pd.DataFrame) -> pd.Series:
    if df.empty or "player_name" not in df:
        return pd.Series(dtype="object")
    if "canonical_player_id" in df:
        return canonical_group_key(df)
    fallback = df["player_name"].fillna("").astype(str).str.strip().str.casefold()
    if "player_id" not in df:
        return fallback
    player_id = df["player_id"].fillna("").astype(str).str.strip()
    return player_id.where(player_id != "", fallback)


def build_all_time_player_table(
    batting_raw: pd.DataFrame,
    bowling_raw: pd.DataFrame,
    fielding_raw: pd.DataFrame,
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
) -> pd.DataFrame:
    base = build_player_identity_frame([batting_raw, bowling_raw, fielding_raw])
    for frame, columns in [
        (
            batting,
            [
                "player_key",
                "battingAggregate",
                "battingAverage",
                "battingStrikeRate",
                "high_score",
                "batting50s",
                "batting100s",
                "batting0s",
                "battingFours",
                "battingSixes",
            ],
        ),
        (
            bowling,
            [
                "player_key",
                "bowlingWickets",
                "bowlingAverage",
                "bowlingEconomyRate",
                "bowlingStrikeRate",
                "bowlingBestInnings",
                "bowlingBalls",
                "bowlingMaidens",
                "bowling5WIs",
                "bowling10WMs",
            ],
        ),
        (
            add_display_stat_aliases(fielding),
            [
                "player_key",
                "catches_display",
                "stumpings_display",
                "run_outs_display",
                "dismissals_display",
            ],
        ),
    ]:
        if frame.empty:
            continue
        source = frame.copy()
        source["player_key"] = player_keys(source)
        for column in columns:
            if column not in source:
                source[column] = pd.NA
        base = base.merge(source[columns], on="player_key", how="left")

    base = base.merge(build_best_match_counts([batting, bowling, fielding]), on="player_key", how="left")
    base["matches"] = pd.to_numeric(base["matches"], errors="coerce").fillna(0)
    base = base.merge(build_reliable_batting_strike_rates(batting_raw), on="player_key", how="left")
    # Balls-faced data before Summer 2024/25 is inconsistent in PlayCricket exports,
    # so all-time Bat SR is intentionally recalculated from reliable recent seasons only.
    if "reliableBattingStrikeRate" in base:
        base["battingStrikeRate"] = base["reliableBattingStrikeRate"]

    return base.rename(
        columns={
            "player_name": "Player",
            "teams_grades": "Teams/Grades",
            "seasons_played": "Seasons Played",
            "first_season": "Debut Season",
            "latest_season": "Latest Season",
            "matches": "Matches",
            "battingAggregate": "Runs",
            "battingAverage": "Bat Avg",
            "battingStrikeRate": "Bat SR",
            "high_score": "HS",
            "batting50s": "50s",
            "batting100s": "100s",
            "batting0s": "0s",
            "battingFours": "4s",
            "battingSixes": "6s",
            "bowlingWickets": "Wickets",
            "bowlingAverage": "Bowl Avg",
            "bowlingEconomyRate": "Econ",
            "bowlingStrikeRate": "Bowl SR",
            "bowlingBestInnings": "BBI",
            "bowlingBalls": "Balls Bowled",
            "bowlingMaidens": "Maidens",
            "bowling5WIs": "5WI",
            "bowling10WMs": "10WM",
            "catches_display": "Catches",
            "stumpings_display": "Stumpings",
            "run_outs_display": "Run Outs",
            "dismissals_display": "Dismissals",
        }
    )


def build_player_identity_frame(frames: list[pd.DataFrame]) -> pd.DataFrame:
    records = []
    for frame in frames:
        if frame.empty or "player_name" not in frame:
            continue
        output = frame.copy()
        output["player_key"] = player_keys(output)
        for key, group in output.groupby("player_key", dropna=False, sort=False):
            name_column = "canonical_player_name" if "canonical_player_name" in group else "player_name"
            player_names = group[name_column].dropna().astype(str)
            teams_grades = label_set(group, "team_grade_display", str)
            if not teams_grades:
                teams = team_label_set(group)
                grades = label_set(group, "canonical_grade_label", str) or label_set(group, "grade_name", compact_grade_label)
                teams_grades = [*teams[:8], *grades[:8]]
            seasons = label_set(group, "season", str)
            records.append(
                {
                    "player_key": key,
                    "player_name": player_names.iloc[0] if not player_names.empty else "-",
                    "teams_grades": ", ".join(unique_labels(teams_grades)),
                    "seasons_played": len(seasons),
                    "first_season": first_season_label(group),
                    "latest_season": latest_season_label(group),
                }
            )

    if not records:
        return pd.DataFrame(columns=["player_key", "player_name", "teams_grades", "seasons_played"])

    identity = pd.DataFrame(records)
    return (
        identity.groupby("player_key", as_index=False)
        .agg(
            {
                "player_name": "first",
                "teams_grades": join_unique_csv,
                "seasons_played": "max",
                "first_season": "first",
                "latest_season": "first",
            }
        )
        .sort_values("player_name")
    )


def first_season_label(group: pd.DataFrame) -> str:
    return edge_season_label(group, latest=False)


def latest_season_label(group: pd.DataFrame) -> str:
    return edge_season_label(group, latest=True)


def edge_season_label(group: pd.DataFrame, latest: bool) -> str:
    if "season" not in group:
        return ""
    seasons = group[["season"]].dropna().drop_duplicates().copy()
    if seasons.empty:
        return ""
    if "season_start_date" in group:
        dates = group[["season", "season_start_date"]].dropna(subset=["season"]).drop_duplicates().copy()
        dates["season_sort"] = pd.to_datetime(dates["season_start_date"], errors="coerce", utc=True)
        dates = dates.sort_values(["season_sort", "season"], ascending=[not latest, not latest])
        if not dates.empty:
            return str(dates.iloc[0]["season"])
    seasons["season_sort"] = seasons["season"].map(season_sort_value)
    seasons = seasons.sort_values(["season_sort", "season"], ascending=[not latest, not latest])
    return str(seasons.iloc[0]["season"])


def label_set(group: pd.DataFrame, column: str, formatter) -> list[str]:
    if column not in group:
        return []
    labels = []
    for value in group[column].dropna().drop_duplicates().tolist():
        label = formatter(value).strip()
        if label and label not in labels:
            labels.append(label)
    return labels


def team_label_set(group: pd.DataFrame) -> list[str]:
    if "team_name" not in group:
        return []
    labels = []
    for value in group["team_name"].dropna().drop_duplicates().tolist():
        raw = str(value)
        label = compact_team_label(raw).strip()
        if raw.startswith("NMCA -") or "Shield" in label:
            continue
        if label and label not in labels:
            labels.append(label)
    return labels


def unique_labels(labels: list[str]) -> list[str]:
    output = []
    for label in labels:
        cleaned = label.strip()
        if cleaned and cleaned not in output:
            output.append(cleaned)
    return output


def join_unique_csv(values: pd.Series) -> str:
    labels = []
    for value in values.dropna().astype(str):
        for part in value.split(","):
            label = part.strip()
            if label and label not in labels:
                labels.append(label)
    return ", ".join(labels)


def build_best_match_counts(frames: list[pd.DataFrame]) -> pd.DataFrame:
    # Match totals can appear in batting, bowling and fielding summaries. Use the
    # largest all-time total per player to avoid counting the same match three times.
    rows = []
    for frame in frames:
        if frame.empty or "matches" not in frame:
            continue
        output = frame.copy()
        output["player_key"] = player_keys(output)
        output["matches"] = pd.to_numeric(output["matches"], errors="coerce").fillna(0)
        rows.append(output.groupby("player_key", as_index=False)["matches"].sum())
    if not rows:
        return pd.DataFrame(columns=["player_key", "matches"])
    combined = pd.concat(rows, ignore_index=True)
    return combined.groupby("player_key", as_index=False)["matches"].max()


def build_reliable_batting_strike_rates(batting_raw: pd.DataFrame) -> pd.DataFrame:
    if batting_raw.empty or "season" not in batting_raw:
        return pd.DataFrame(columns=["player_key", "reliableBattingStrikeRate"])
    output = batting_raw.copy()
    output = output[output["season"].map(profile_season_sort_key) >= profile_season_sort_key("Summer 2024/25")]
    if output.empty:
        return pd.DataFrame(columns=["player_key", "reliableBattingStrikeRate"])
    output["player_key"] = player_keys(output)
    for column in ["battingAggregate", "battingBallsFaced"]:
        if column not in output:
            output[column] = 0
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)
    grouped = output.groupby("player_key", as_index=False).agg(
        reliable_runs=("battingAggregate", "sum"),
        reliable_balls=("battingBallsFaced", "sum"),
    )
    grouped["reliableBattingStrikeRate"] = grouped.apply(
        lambda row: divide_or_none(float(row["reliable_runs"]) * 100, float(row["reliable_balls"])),
        axis=1,
    )
    return grouped[["player_key", "reliableBattingStrikeRate"]]


def estimate_historical_matches(*frames: pd.DataFrame) -> int:
    team_season_counts = {}
    for frame in frames:
        if frame.empty or "matches" not in frame:
            continue
        output = frame.copy()
        output["matches"] = pd.to_numeric(output["matches"], errors="coerce").fillna(0)
        if {"team_id", "season"}.issubset(output.columns):
            for key, group in output.groupby(["season", "team_id"], dropna=False):
                team_season_counts[key] = max(team_season_counts.get(key, 0), float(group["matches"].max()))
    return int(sum(team_season_counts.values()))


def render_hall_of_fame_kpis(data: dict[str, object]) -> None:
    cards = [
        ("Seasons Analysed", f"{int(data['total_seasons']):,}", "", "team", "XI", "purple"),
        ("Matches Recorded", f"{int(data['total_matches']):,}", "", "matches", "▣", "blue"),
        ("Players Scanned", f"{int(data['total_players']):,}", "", "runs", "🏏", "green"),
    ]
    columns = st.columns(3)
    for column, card in zip(columns, cards):
        with column:
            render_kpi_card(*card)
    st.markdown("<div class='dashboard-spacer'></div>", unsafe_allow_html=True)


def render_hall_of_fame_leaders(all_time: pd.DataFrame) -> None:
    render_section_heading("All-Time Leaders 👑")
    leader_specs = [
        ("Most Matches", "Matches", "matches", "fielding"),
        ("Most Runs", "Runs", "runs", "batting"),
        ("Most Wickets", "Wickets", "wickets", "bowling"),
        ("Most Catches", "Catches", "catches", "fielding"),
    ]
    for index in range(0, len(leader_specs), 2):
        columns = st.columns(2)
        for column, (title, metric, suffix, mode) in zip(columns, leader_specs[index : index + 2]):
            with column:
                render_hof_leader_card(title, all_time, metric, suffix, mode)


def render_hof_leader_card(title: str, df: pd.DataFrame, metric: str, suffix: str, mode: str) -> None:
    if metric not in df:
        return
    leaders = df.copy()
    leaders[metric] = pd.to_numeric(leaders[metric], errors="coerce").fillna(0)
    leaders = leaders[leaders[metric] > 0]
    leaders = sort_hof_leaders(leaders, metric, mode).head(10)
    if leaders.empty:
        return

    max_value = leaders[metric].max()
    rows = []
    for rank, (_, row) in enumerate(leaders.iterrows(), start=1):
        value = float(row[metric])
        width = 0 if not max_value else value / max_value * 100
        rows.append(
            '<div class="progress-row hof-progress-row">'
            f'<span class="progress-rank">{rank_badge(rank)}</span>'
            f'<span class="progress-name">{html.escape(str(row["Player"]))}</span>'
            f'<span class="progress-value"><strong>{int(value):,} {html.escape(suffix)}</strong></span>'
            f'<div class="progress-track"><div style="width:{width:.0f}%"></div></div>'
            "</div>"
        )
    st.markdown(
        f'<div class="hof-card"><div class="card-title">{html.escape(title)}</div>{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


def render_match_winning_performances(data: dict[str, object]) -> None:
    batting_records = data.get("iconic_batting")
    bowling_records = data.get("iconic_bowling")
    if batting_records is None:
        batting_records = top_highest_scores(data["batting_raw"], limit=10)
    if bowling_records is None:
        bowling_records = top_best_bowling_innings(data["bowling_raw"], limit=10)
    if batting_records.empty and bowling_records.empty:
        return
    render_section_heading("Iconic Performances 🌟")
    columns = st.columns(2)
    with columns[0]:
        render_performance_card("Highest Individual Scores", batting_records, "batting")
    with columns[1]:
        render_performance_card("Best Bowling Innings", bowling_records, "bowling")


@st.cache_data(show_spinner=False)
def top_highest_scores(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if df.empty or "battingHighScore" not in df:
        return pd.DataFrame()
    output = df.copy()
    output["score_sort"] = pd.to_numeric(output["battingHighScore"], errors="coerce")
    output["not_out_sort"] = output.get("isBattingHSNotOut", False).map(as_bool) if "isBattingHSNotOut" in output else False
    output = output[output["score_sort"].notna() & (output["score_sort"] > 0)]
    return output.sort_values(["score_sort", "not_out_sort"], ascending=[False, False]).head(limit)


@st.cache_data(show_spinner=False)
def top_best_bowling_innings(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if df.empty or "bowlingBestInnings" not in df:
        return pd.DataFrame()
    return sort_bowling_by_bbi(df.dropna(subset=["bowlingBestInnings"])).head(limit)


def render_performance_card(title: str, df: pd.DataFrame, mode: str) -> None:
    if df.empty:
        return
    rows = []
    for rank, (_, row) in enumerate(df.iterrows(), start=1):
        if mode == "batting":
            value = format_high_score_value(row)
        else:
            value = str(row.get("bowlingBestInnings", "-"))
        meta = record_meta(row)
        meta_html = f'<span>{html.escape(meta)}</span>' if meta else ""
        name = row.get("canonical_player_name") or row.get("player_name") or "-"
        rows.append(
            '<div class="performance-row">'
            f'<span class="progress-rank">{rank_badge(rank)}</span>'
            f'<div class="performance-player"><strong>{html.escape(str(name))}</strong>{meta_html}</div>'
            f'<div class="performance-value">{html.escape(str(value))}</div>'
            "</div>"
        )
    st.markdown(
        f'<div class="hof-card performance-card"><div class="card-title">{html.escape(title)}</div>{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )


def sort_hof_leaders(df: pd.DataFrame, metric: str, mode: str) -> pd.DataFrame:
    if df.empty:
        return df
    output = df.copy()
    output["_metric_sort"] = pd.to_numeric(output.get(metric), errors="coerce").fillna(0)
    output["_name_sort"] = output.get("Player", pd.Series("", index=output.index)).fillna("").astype(str).str.casefold()
    if mode == "batting":
        output["_tie_sort"] = pd.to_numeric(output.get("Bat Avg"), errors="coerce").fillna(-1)
        return output.sort_values(["_metric_sort", "_tie_sort", "_name_sort"], ascending=[False, False, True]).drop(columns=["_metric_sort", "_tie_sort", "_name_sort"])
    if mode == "bowling":
        output["_tie_sort"] = pd.to_numeric(output.get("Bowl Avg"), errors="coerce").fillna(999999)
        return output.sort_values(["_metric_sort", "_tie_sort", "_name_sort"], ascending=[False, True, True]).drop(columns=["_metric_sort", "_tie_sort", "_name_sort"])
    output["_matches_sort"] = pd.to_numeric(output.get("Matches"), errors="coerce").fillna(999999)
    return output.sort_values(["_metric_sort", "_matches_sort", "_name_sort"], ascending=[False, True, True]).drop(columns=["_metric_sort", "_matches_sort", "_name_sort"])


def render_record_holders(data: dict[str, object]) -> None:
    cards = data.get("record_holder_cards") or build_record_holder_cards(data)
    if not cards:
        return
    render_section_heading("Record Holders 📘")
    cards_html = "".join(record_card_html(card) for card in cards)
    st.markdown(f'<div class="record-card-grid">{cards_html}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def build_record_holder_cards(data: dict[str, object]) -> list[dict[str, str]]:
    cards = []
    batting_raw = data["batting_raw"]
    bowling_raw = data["bowling_raw"]
    all_time = data["all_time"]

    for title, metric, suffix in [
        ("Most 100s", "100s", "hundreds"),
        ("Most 50s", "50s", "fifties"),
        ("Most 4s", "4s", "fours"),
        ("Most 6s", "6s", "sixes"),
        ("5 Wicket Hauls", "5WI", "five-wicket hauls"),
        ("Most Maidens", "Maidens", "maidens"),
        ("Ducks", "0s", "ducks"),
    ]:
        if metric not in all_time:
            continue
        leaders = all_time.copy()
        leaders[metric] = pd.to_numeric(leaders[metric], errors="coerce").fillna(0)
        leaders = leaders[leaders[metric] > 0].sort_values(metric, ascending=False)
        if leaders.empty:
            continue
        row = leaders.iloc[0]
        cards.append(
            {
                "title": title,
                "player": str(row.get("Player", "-")),
                "value": f"{int(row[metric]):,} {suffix}",
                "meta": "",
            }
        )
    return cards


def render_best_ever_seasons(data: dict[str, object]) -> None:
    batting = data.get("best_batting_season")
    bowling = data.get("best_bowling_season")
    if "best_batting_season" not in data:
        batting = best_batting_season(data["batting_raw"])
    if "best_bowling_season" not in data:
        bowling = best_bowling_season(data["bowling_raw"])
    if batting is None and bowling is None:
        return

    render_section_heading("Greatest Individual Seasons 🎖️")
    cards = []
    if batting is not None:
        cards.append(best_season_card_html("Best batting season", batting, "batting"))
    if bowling is not None:
        cards.append(best_season_card_html("Best bowling season", bowling, "bowling"))
    st.markdown(f'<div class="best-season-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def best_batting_season(df: pd.DataFrame) -> dict[str, object] | None:
    if df.empty or "season" not in df:
        return None
    frame = df.copy()
    player_source = "canonical_player_name" if "canonical_player_name" in frame else "player_name"
    if player_source not in frame:
        return None
    frame["_player"] = frame[player_source].fillna("").astype(str).str.strip()
    frame = frame[(frame["_player"] != "") & frame["season"].notna()]
    if frame.empty:
        return None

    rows = []
    for (player, season), group in frame.groupby(["_player", "season"], dropna=False):
        runs = sum_column(group, "battingAggregate")
        balls = sum_column(group, "battingBallsFaced")
        innings = sum_column(group, "battingInnings")
        not_outs = sum_column(group, "battingNotOuts")
        outs = max(innings - not_outs, 0)
        row = {
            "player": player,
            "season": season,
            "matches": sum_column(group, "matches"),
            "runs": runs,
            "innings": innings,
            "average": divide_or_none(runs, outs),
            "strike_rate": divide_or_none(runs * 100, balls) if profile_season_sort_key(season) >= profile_season_sort_key("Summer 2024/25") else None,
            "hs": best_high_score(group),
            "50s": sum_column(group, "batting50s"),
            "100s": sum_column(group, "batting100s"),
            "4s": sum_column(group, "battingFours"),
            "6s": sum_column(group, "battingSixes"),
            "0s": sum_column(group, "batting0s"),
        }
        if runs > 0:
            rows.append(row)
    if not rows:
        return None
    return sorted(rows, key=lambda row: (-row["runs"], -(row["average"] or 0), str(row["player"]).casefold()))[0]


@st.cache_data(show_spinner=False)
def best_bowling_season(df: pd.DataFrame) -> dict[str, object] | None:
    if df.empty or "season" not in df:
        return None
    frame = df.copy()
    player_source = "canonical_player_name" if "canonical_player_name" in frame else "player_name"
    if player_source not in frame:
        return None
    frame["_player"] = frame[player_source].fillna("").astype(str).str.strip()
    frame = frame[(frame["_player"] != "") & frame["season"].notna()]
    if frame.empty:
        return None

    rows = []
    for (player, season), group in frame.groupby(["_player", "season"], dropna=False):
        wickets = sum_column(group, "bowlingWickets")
        balls = sum_column(group, "bowlingBalls")
        runs = sum_column(group, "bowlingRuns")
        row = {
            "player": player,
            "season": season,
            "matches": sum_column(group, "matches"),
            "wickets": wickets,
            "overs": format_balls_as_overs(balls) if balls else "—",
            "maidens": sum_column(group, "bowlingMaidens"),
            "average": divide_or_none(runs, wickets),
            "economy": divide_or_none(runs * 6, balls),
            "strike_rate": divide_or_none(balls, wickets),
            "bbi": best_bowling_value(group),
            "5wi": sum_column(group, "bowling5WIs"),
            "10wm": sum_column(group, "bowling10WMs"),
        }
        if wickets > 0:
            rows.append(row)
    if not rows:
        return None
    return sorted(rows, key=lambda row: (-row["wickets"], row["average"] or 999999, str(row["player"]).casefold()))[0]


def best_season_card_html(title: str, row: dict[str, object], mode: str) -> str:
    if mode == "batting":
        primary = f'{format_int(row["runs"])} runs'
        chips = [
            ("Matches", format_int(row["matches"])),
            ("Runs", format_int(row["runs"])),
            ("Avg", format_decimal(row["average"])),
            ("SR", format_decimal(row["strike_rate"])),
            ("HS", str(row["hs"])),
            ("50s", format_int(row["50s"])),
            ("100s", format_int(row["100s"])),
            ("4s", format_int(row["4s"])),
            ("6s", format_int(row["6s"])),
            ("0s", format_int(row["0s"])),
        ]
    else:
        primary = f'{format_int(row["wickets"])} wickets'
        chips = [
            ("Matches", format_int(row["matches"])),
            ("Overs", str(row["overs"])),
            ("Mdns", format_int(row["maidens"])),
            ("Avg", format_decimal(row["average"])),
            ("Econ", format_decimal(row["economy"])),
            ("SR", format_decimal(row["strike_rate"])),
            ("BBI", str(row["bbi"])),
            ("5WI", format_int(row["5wi"])),
            ("10WM", format_int(row["10wm"])),
        ]
    chip_html = "".join(
        f'<span><b>{html.escape(label)}</b>{html.escape(value)}</span>'
        for label, value in chips
        if value and value != "—"
    )
    return (
        '<div class="best-season-card">'
        f'<div class="best-season-label">{html.escape(title)}</div>'
        f'<div class="best-season-player">{html.escape(str(row["player"]))}</div>'
        f'<div class="best-season-season">{html.escape(str(row["season"]))}</div>'
        f'<div class="best-season-primary">{html.escape(primary)}</div>'
        f'<div class="best-season-stats">{chip_html}</div>'
        "</div>"
    )


def format_high_score_value(row: pd.Series) -> str:
    score = pd.to_numeric(row.get("battingHighScore"), errors="coerce")
    if pd.isna(score):
        return "-"
    suffix = "*" if as_bool(row.get("isBattingHSNotOut")) else ""
    return f"{int(score)}{suffix}"


def as_bool(value: object) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "yes", "y", "not out", "notout"}
    return bool(value)


def record_meta(row: pd.Series) -> str:
    parts = []
    season = row.get("season")
    if pd.notna(season):
        parts.append(str(season))
    display = row.get("team_grade_display") or build_team_grade_display(row.get("team_name", ""), row.get("grade_name", ""))
    if display and display != "—":
        parts.append(str(display))
    return " · ".join(parts)


def compact_record_team_label(team_name: object) -> str:
    raw = str(team_name)
    if raw.startswith("NMCA -"):
        return ""
    return compact_team_label(raw)


def render_record_card(card: dict[str, str]) -> None:
    st.markdown(record_card_html(card), unsafe_allow_html=True)


def record_card_html(card: dict[str, str]) -> str:
    meta = f'<div class="record-meta">{html.escape(card["meta"])}</div>' if card.get("meta") else ""
    return (
        '<div class="record-card">'
        f'<div class="record-label">{html.escape(card["title"])}</div>'
        f'<div class="record-player">{html.escape(card["player"])}</div>'
        f'<div class="record-value">{html.escape(card["value"])}</div>'
        f"{meta}"
        "</div>"
    )


def render_milestone_club(all_time: pd.DataFrame) -> None:
    rendered = []
    for metric, step, suffix in [("Runs", 1000, "runs"), ("Wickets", 100, "wickets"), ("Matches", 100, "matches")]:
        if metric not in all_time:
            continue
        players = all_time.copy()
        players[metric] = pd.to_numeric(players[metric], errors="coerce").fillna(0)
        players = players[players[metric] >= step].copy()
        if players.empty:
            continue
        players["milestone_band"] = (players[metric] // step).astype(int) * step
        for band in sorted(players["milestone_band"].dropna().unique(), reverse=True):
            band_players = players[players["milestone_band"] == band].sort_values(metric, ascending=False)
            chips = "".join(
                f'<span class="milestone-chip">{html.escape(str(row["Player"]))} · {int(row[metric]):,} {html.escape(suffix)}</span>'
                for _, row in band_players.head(18).iterrows()
            )
            rendered.append(f'<div class="milestone-group"><h4>{int(band):,}+ {html.escape(metric)}</h4><div>{chips}</div></div>')
    if not rendered:
        return
    render_section_heading("Exclusive Club 💪")
    st.markdown(f'<div class="milestone-card">{"".join(rendered)}</div>', unsafe_allow_html=True)


def render_detailed_all_time_records(all_time_or_tables: pd.DataFrame | dict[str, pd.DataFrame]) -> None:
    render_section_heading("Detailed All-Time Records 📊")
    if isinstance(all_time_or_tables, dict):
        tables = {
            "batting": all_time_or_tables["batting"].copy(),
            "bowling": all_time_or_tables["bowling"].copy(),
            "fielding": all_time_or_tables["fielding"].copy(),
        }
    else:
        all_time = all_time_or_tables
        tables = {
            "batting": format_all_time_batting_table(all_time),
            "bowling": format_all_time_bowling_table(all_time),
            "fielding": format_all_time_fielding_table(all_time),
        }
    with st.container(key="full_stats_card"):
        batting_tab, bowling_tab, fielding_tab = st.tabs(["Batting", "Bowling", "Fielding"])
        with batting_tab:
            render_all_time_detail_table(tables["batting"], "hof_batting_detail")
        with bowling_tab:
            render_all_time_detail_table(tables["bowling"], "hof_bowling_detail")
        with fielding_tab:
            render_all_time_detail_table(tables["fielding"], "hof_fielding_detail")


@st.cache_data(show_spinner=False)
def format_all_time_table(all_time: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Player",
        "Teams/Grades",
        "Seasons Played",
        "Matches",
        "Runs",
        "Bat Avg",
        "Bat SR",
        "HS",
        "50s",
        "100s",
        "Wickets",
        "Bowl Avg",
        "Econ",
        "Bowl SR",
        "BBI",
        "5WI",
        "Catches",
        "Stumpings",
        "Run Outs",
        "Dismissals",
    ]
    table = select_display_columns(all_time, columns).copy()
    for column in ["Runs", "Wickets", "Matches"]:
        if column not in table:
            table[column] = 0
    table = table.sort_values(["Runs", "Wickets", "Matches"], ascending=False, na_position="last")
    for column in ["Seasons Played", "Matches", "Runs", "50s", "100s", "Wickets", "5WI", "Catches", "Stumpings", "Run Outs", "Dismissals"]:
        if column in table:
            table[column] = pd.to_numeric(table[column], errors="coerce")
    for column in ["Bat Avg", "Bat SR", "Bowl Avg", "Econ", "Bowl SR"]:
        if column in table:
            table[column] = pd.to_numeric(table[column], errors="coerce")
    return format_table_missing_values(table)


@st.cache_data(show_spinner=False)
def format_all_time_batting_table(all_time: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Player",
        "Seasons Played",
        "Debut Season",
        "Latest Season",
        "Matches",
        "Runs",
        "Bat Avg",
        "Bat SR",
        "HS",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
    ]
    table = select_display_columns(all_time, columns).copy()
    if "Runs" in table:
        table = table.sort_values(["Runs", "Bat Avg", "Player"], ascending=[False, False, True], na_position="last")
    return coerce_display_numbers(table)


@st.cache_data(show_spinner=False)
def format_all_time_bowling_table(all_time: pd.DataFrame) -> pd.DataFrame:
    source = all_time.copy()
    if "Balls Bowled" in source:
        source["Overs"] = source["Balls Bowled"].map(format_balls_as_overs)
    columns = [
        "Player",
        "Seasons Played",
        "Matches",
        "Overs",
        "Wickets",
        "Maidens",
        "Bowl Avg",
        "Econ",
        "Bowl SR",
        "BBI",
        "5WI",
        "10WM",
    ]
    table = select_display_columns(source, columns).copy()
    if "BBI" in table:
        table["BBI"] = ordered_bbi_values(table["BBI"])
    if "Wickets" in table:
        table = table.sort_values(["Wickets", "Bowl Avg", "Player"], ascending=[False, True, True], na_position="last")
    return coerce_display_numbers(table)


@st.cache_data(show_spinner=False)
def format_all_time_fielding_table(all_time: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "Player",
        "Seasons Played",
        "Matches",
        "Catches",
        "Stumpings",
        "Run Outs",
        "Dismissals",
    ]
    table = select_display_columns(all_time, columns).copy()
    if "Catches" in table:
        table = table.sort_values(["Catches", "Matches", "Player"], ascending=[False, True, True], na_position="last")
    return coerce_display_numbers(table)


def render_all_time_detail_table(table: pd.DataFrame, key_prefix: str) -> None:
    started_at = time.perf_counter()
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=560,
        column_config=hall_of_fame_column_config(table.columns.tolist()),
    )
    log_hof_timing(f"render table {key_prefix}", started_at)


def render_filterable_dataframe(
    table: pd.DataFrame,
    key_prefix: str,
    use_container_width: bool = True,
    hide_index: bool = True,
    height: int = 520,
    column_config: dict[str, object] | None = None,
    show_filters: bool = True,
) -> None:
    filtered = apply_dataframe_filters(table, key_prefix) if show_filters else table
    st.dataframe(
        filtered,
        use_container_width=use_container_width,
        hide_index=hide_index,
        height=height,
        column_config=column_config,
    )


def apply_dataframe_filters(table: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    if table.empty:
        return table
    output = table.copy()
    with st.expander("Table filters", expanded=False):
        for column in output.columns:
            series = output[column]
            numeric_series = display_numeric_series(series)
            is_numeric = numeric_series.notna().sum() >= max(2, int(len(series.dropna()) * 0.65))
            safe_key = make_widget_key(key_prefix, column)
            if is_numeric:
                available = numeric_series.dropna()
                if available.empty:
                    continue
                min_value = float(available.min())
                max_value = float(available.max())
                if min_value == max_value:
                    continue
                min_col, max_col = st.columns(2)
                with min_col:
                    lower = st.number_input(
                        f"{column} min",
                        value=min_value,
                        min_value=min_value,
                        max_value=max_value,
                        key=f"{safe_key}_min",
                    )
                with max_col:
                    upper = st.number_input(
                        f"{column} max",
                        value=max_value,
                        min_value=min_value,
                        max_value=max_value,
                        key=f"{safe_key}_max",
                    )
                output = output[numeric_series.between(lower, upper, inclusive="both") | numeric_series.isna()]
            else:
                values = sorted(
                    value
                    for value in series.dropna().astype(str).map(str.strip).unique().tolist()
                    if value and value != "—"
                )
                if not values:
                    continue
                if len(values) <= 30:
                    selected = st.multiselect(f"{column}", values, key=f"{safe_key}_values")
                    if selected:
                        output = output[output[column].astype(str).isin(selected)]
                else:
                    text = st.text_input(f"{column} contains", key=f"{safe_key}_text")
                    if text:
                        output = output[output[column].astype(str).str.contains(text, case=False, na=False)]
    return output


def display_numeric_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("%", "", regex=False)
        .str.replace("—", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def make_widget_key(prefix: str, column: str) -> str:
    safe_prefix = re.sub(r"[^a-zA-Z0-9_]+", "_", str(prefix)).strip("_")
    safe_column = re.sub(r"[^a-zA-Z0-9_]+", "_", str(column).replace("%", "pct")).strip("_")
    return f"{safe_prefix}_{safe_column}".lower()


def format_table_missing_values(table: pd.DataFrame) -> pd.DataFrame:
    output = table.copy()
    integer_columns = {
        "Seasons Played",
        "Matches",
        "Runs",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
        "Wickets",
        "Maidens",
        "5WI",
        "10WM",
        "Catches",
        "Stumpings",
        "Run Outs",
        "Dismissals",
    }
    decimal_columns = {"Bat Avg", "Bat SR", "Bowl Avg", "Econ", "Bowl SR"}
    for column in output.columns:
        if column in integer_columns:
            values = pd.to_numeric(output[column], errors="coerce")
            output[column] = values.map(lambda value: "—" if pd.isna(value) else f"{int(value):,}")
        elif column in decimal_columns:
            values = pd.to_numeric(output[column], errors="coerce")
            output[column] = values.map(lambda value: "—" if pd.isna(value) else f"{float(value):.2f}")
        else:
            output[column] = output[column].map(lambda value: "—" if pd.isna(value) or str(value).strip() == "" else value)
    return output


def hall_of_fame_column_config(columns: list[str]) -> dict[str, object]:
    config = {}
    config["Player"] = st.column_config.TextColumn("Player", pinned=True, width=150)
    config["Teams/Grades"] = st.column_config.TextColumn("Teams/Grades", width=150)
    for column in ["Debut Season", "Latest Season"]:
        if column in columns:
            config[column] = st.column_config.TextColumn(column, width=145)
    integer_columns = {
        "Seasons Played",
        "Matches",
        "Runs",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
        "Wickets",
        "Maidens",
        "5WI",
        "10WM",
        "Catches",
        "Stumpings",
        "Run Outs",
        "Dismissals",
    }
    decimal_columns = {"Bat Avg", "Bat SR", "Bowl Avg", "Econ", "Bowl SR"}
    width_overrides = {
        "Seasons Played": 95,
        "Matches": 78,
        "Runs": 76,
        "Wickets": 78,
        "Catches": 78,
        "Stumpings": 86,
        "Run Outs": 82,
        "Dismissals": 86,
    }
    for column, width in width_overrides.items():
        if column in columns and column not in {"Player", "Teams/Grades"}:
            config[column] = st.column_config.NumberColumn(column, width=width, format="%d")
    for column in columns:
        if column not in config:
            if column in integer_columns:
                config[column] = st.column_config.NumberColumn(column, width=72, format="%d")
            elif column in decimal_columns:
                config[column] = st.column_config.NumberColumn(column, width=72, format="%.2f")
            else:
                config[column] = st.column_config.TextColumn(column, width=72)
    return config


@st.cache_data(show_spinner=False)
def build_approaching_milestone_watchlist(all_time: pd.DataFrame) -> pd.DataFrame:
    specs = [
        ("Matches", "Matches", 100, 10, "matches", "Career Milestones"),
        ("Runs", "Runs", 1000, 100, "runs", "Career Milestones"),
        ("Wickets", "Wickets", 100, 10, "wickets", "Career Milestones"),
        ("Catches", "Catches", 50, 5, "catches", "Career Milestones"),
        ("Dismissals", "Dismissals", 50, 5, "dismissals", "Career Milestones"),
        ("Half-centuries", "50s", 10, 1, "half-centuries", "Special Achievements"),
        ("Centuries", "100s", 5, 1, "centuries", "Special Achievements"),
        ("Five-wicket hauls", "5WI", 5, 1, "five-wicket hauls", "Special Achievements"),
    ]
    frames = [
        build_milestone_watchlist(all_time, value_col, category, step, threshold, unit, group)
        for category, value_col, step, threshold, unit, group in specs
        if value_col in all_time
    ]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=milestone_watchlist_columns())
    watchlist = pd.concat(frames, ignore_index=True)
    return watchlist.sort_values(["Remaining", "Current Total"], ascending=[True, False])


def recent_active_canonical_players(historical_data: dict[str, object], season_count: int = 3) -> set[str]:
    frames = [
        historical_data.get("batting_raw"),
        historical_data.get("bowling_raw"),
        historical_data.get("fielding_raw"),
    ]
    frames = [frame for frame in frames if isinstance(frame, pd.DataFrame) and not frame.empty]
    if not frames:
        return set()

    activity = pd.concat(frames, ignore_index=True, sort=False)
    if activity.empty or "canonical_player_name" not in activity:
        return set()

    latest_seasons = latest_activity_seasons(activity, season_count)
    if not latest_seasons:
        return set()

    recent_activity = activity[activity["season"].isin(latest_seasons)].copy() if "season" in activity else activity.head(0)
    return set(recent_activity["canonical_player_name"].dropna().map(display_player_name).astype(str))


def latest_activity_seasons(activity: pd.DataFrame, season_count: int) -> list[str]:
    if activity.empty or "season" not in activity:
        return []

    season_table = read_processed_table("seasons")
    if not season_table.empty and {"name", "startDate"}.issubset(season_table.columns):
        season_table = season_table.copy()
        season_table["season_sort"] = pd.to_datetime(season_table["startDate"], errors="coerce", utc=True)
        current_rows = (
            season_table[season_table["isCurrentSeason"].fillna(False).astype(bool)]
            if "isCurrentSeason" in season_table
            else pd.DataFrame()
        )
        anchor = current_rows.iloc[0] if not current_rows.empty else season_table.sort_values("season_sort", ascending=False).iloc[0]
        anchor_family = str(anchor.get("name", "")).split(" ", 1)[0]
        relevant = season_table[season_table["name"].astype(str).str.startswith(f"{anchor_family} ", na=False)]
        relevant = relevant.sort_values(["season_sort", "name"], ascending=[False, False])
        ordered = relevant["name"].dropna().drop_duplicates().tolist()
        if ordered:
            return ordered[:season_count]

    seasons = activity[["season"]].dropna().drop_duplicates().copy()
    if seasons.empty:
        return []

    if "season_start_date" in activity:
        season_dates = (
            activity[["season", "season_start_date"]]
            .dropna(subset=["season"])
            .drop_duplicates()
            .copy()
        )
        season_dates["season_sort"] = pd.to_datetime(
            season_dates["season_start_date"],
            errors="coerce",
            utc=True,
        )
        season_dates = season_dates.sort_values(["season_sort", "season"], ascending=[False, False])
        ordered = season_dates["season"].dropna().drop_duplicates().tolist()
        if ordered:
            return ordered[:season_count]

    seasons["season_sort"] = seasons["season"].map(season_sort_value)
    seasons = seasons.sort_values(["season_sort", "season"], ascending=[False, False])
    return seasons["season"].tolist()[:season_count]


def season_sort_value(season: object) -> int:
    text = str(season)
    match = pd.Series([text]).str.extract(r"(\d{4})").iloc[0, 0]
    numeric = pd.to_numeric(match, errors="coerce")
    return int(numeric) if pd.notna(numeric) else 0


def milestone_watchlist_columns() -> list[str]:
    return [
        "Player",
        "Category",
        "Current Total",
        "Target Milestone",
        "Remaining",
        "Progress %",
        "Unit",
        "Group",
    ]


def build_milestone_watchlist(
    df: pd.DataFrame,
    value_col: str,
    category: str,
    step: int,
    threshold: int,
    unit: str,
    group: str,
) -> pd.DataFrame:
    if df.empty or value_col not in df or "Player" not in df:
        return pd.DataFrame(columns=milestone_watchlist_columns())

    values = df[["Player", value_col]].copy()
    values[value_col] = pd.to_numeric(values[value_col], errors="coerce")
    values = values[values[value_col].notna() & (values[value_col] > 0)]
    if values.empty:
        return pd.DataFrame(columns=milestone_watchlist_columns())

    # Hall of Fame data is already one row per player, but group defensively in
    # case future processed data introduces split player rows.
    grouped = values.groupby("Player", as_index=False)[value_col].sum()
    grouped["Current Total"] = grouped[value_col].astype(float)
    grouped["Target Milestone"] = grouped["Current Total"].map(lambda value: next_milestone_target(value, step))
    grouped["Remaining"] = grouped["Target Milestone"] - grouped["Current Total"]
    grouped = grouped[(grouped["Remaining"] > 0) & (grouped["Remaining"] <= threshold)]
    if grouped.empty:
        return pd.DataFrame(columns=milestone_watchlist_columns())

    grouped["Progress %"] = grouped["Current Total"] / grouped["Target Milestone"] * 100
    grouped["Category"] = category
    grouped["Unit"] = unit
    grouped["Group"] = group
    return grouped[milestone_watchlist_columns()]


def next_milestone_target(value: float, step: int) -> int:
    current = int(value)
    if current % step == 0:
        return current + step
    return ((current // step) + 1) * step


def render_milestone_kpis(watchlist: pd.DataFrame) -> None:
    near_matches = milestone_unique_players(watchlist, ["Matches"])
    near_batting = milestone_unique_players(watchlist, ["Runs", "Half-centuries", "Centuries"])
    near_bowling_fielding = milestone_unique_players(
        watchlist,
        ["Wickets", "Catches", "Dismissals", "Five-wicket hauls"],
    )
    cards = [
        ("Total Milestone Opportunities", f"{len(watchlist):,}", "", "milestones", "▦", "purple"),
        ("Players Near Matches", f"{near_matches:,}", "", "matches", "▣", "blue"),
        ("Players Near Batting", f"{near_batting:,}", "", "runs", "▥", "purple"),
        ("Bowling / Fielding Watch", f"{near_bowling_fielding:,}", "", "wickets", "♕", "green"),
    ]
    columns = st.columns(4)
    for column, card in zip(columns, cards):
        with column:
            render_kpi_card(*card)
    st.markdown("<div class='dashboard-spacer'></div>", unsafe_allow_html=True)


def milestone_unique_players(watchlist: pd.DataFrame, categories: list[str]) -> int:
    if watchlist.empty:
        return 0
    return int(watchlist[watchlist["Category"].isin(categories)]["Player"].nunique())


def render_career_milestone_cards(watchlist: pd.DataFrame) -> None:
    render_section_heading("Milestone Watchlist 🎯")
    column_groups = [["Matches", "Wickets"], ["Runs", "Catches"]]
    if not any(
        not milestone_category_rows(watchlist, category).empty
        for group in column_groups
        for category in group
    ):
        st.info("No players are currently within milestone range.")
        return

    columns = st.columns(2)
    for column, categories in zip(columns, column_groups):
        with column:
            for category in categories:
                if milestone_category_rows(watchlist, category).empty:
                    continue
                render_milestone_category_card(watchlist, category)


def render_milestone_category_card(watchlist: pd.DataFrame, category: str) -> None:
    rows = milestone_category_rows(watchlist, category)
    if rows.empty:
        st.markdown(
            (
                '<div class="milestone-watch-card">'
                f'<div class="card-title">{html.escape(category)}</div>'
                '<div class="empty-state">No players are currently within milestone range for this category.</div>'
                "</div>"
            ),
            unsafe_allow_html=True,
        )
        return

    html_rows = []
    for _, row in rows.head(10).iterrows():
        progress = max(0, min(float(row["Progress %"]), 100))
        current = int(row["Current Total"])
        target = int(row["Target Milestone"])
        remaining = int(row["Remaining"])
        unit = str(row["Unit"])
        html_rows.append(
            '<div class="milestone-watch-row">'
            '<div class="milestone-watch-top">'
            f'<div><strong>{html.escape(str(row["Player"]))}</strong>'
            f'<span>{current:,} / {target:,} {html.escape(unit)}</span></div>'
            f'<div class="milestone-away">{remaining:,} {html.escape(unit)} away</div>'
            "</div>"
            f'<div class="progress-track"><div style="width:{progress:.1f}%"></div></div>'
            "</div>"
        )

    st.markdown(
        f'<div class="milestone-watch-card"><div class="card-title">{html.escape(category)}</div>{"".join(html_rows)}</div>',
        unsafe_allow_html=True,
    )


def milestone_category_rows(watchlist: pd.DataFrame, category: str) -> pd.DataFrame:
    if watchlist.empty:
        return pd.DataFrame()
    rows = watchlist[watchlist["Category"] == category].copy()
    return rows.sort_values(["Remaining", "Current Total"], ascending=[True, False])


def render_milestone_watchlist_table(watchlist: pd.DataFrame) -> None:
    render_section_heading("Milestone Watchlist")
    if watchlist.empty:
        st.info("No players are currently within milestone range for this category.")
        return

    category_options = ["All", "Matches", "Runs", "Wickets", "Catches", "Dismissals"]
    if (watchlist["Group"] == "Special Achievements").any():
        category_options.append("Special Achievements")
    selected_category = st.selectbox("Milestone category", category_options, key="milestone_category_filter")

    filtered = watchlist.copy()
    if selected_category == "Special Achievements":
        filtered = filtered[filtered["Group"] == "Special Achievements"]
    elif selected_category != "All":
        filtered = filtered[filtered["Category"] == selected_category]

    if filtered.empty:
        st.info("No players are currently within milestone range for this category.")
        return

    table = filtered[["Player", "Category", "Current Total", "Target Milestone", "Remaining", "Progress %"]].copy()
    table["Current Total"] = table["Current Total"].map(lambda value: f"{int(value):,}")
    table["Target Milestone"] = table["Target Milestone"].map(lambda value: f"{int(value):,}")
    table["Remaining"] = table["Remaining"].map(lambda value: f"{int(value):,}")
    table["Progress %"] = table["Progress %"].map(lambda value: f"{float(value):.1f}%")
    with st.container(key="full_stats_card"):
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            height=520,
            column_config={
                "Player": st.column_config.TextColumn("Player", pinned=True, width="medium"),
                "Category": st.column_config.TextColumn("Category", width="medium"),
                "Current Total": st.column_config.TextColumn("Current Total"),
                "Target Milestone": st.column_config.TextColumn("Target Milestone"),
                "Remaining": st.column_config.TextColumn("Remaining"),
                "Progress %": st.column_config.TextColumn("Progress %"),
            },
        )


def render_player_profile_page() -> None:
    index = load_player_profile_index(metadata_mtime(), player_aliases_mtime())
    st.markdown(
        """
        <div class="player-profile-page"></div>
        <h1 class="page-title">Player Spotlight 🏏</h1>
        <div class="club-label">Fiji Victorian Cricket Club</div>
        <div class="page-subtitle">Search any player and explore their career story across seasons, teams, and formats.</div>
        """,
        unsafe_allow_html=True,
    )

    if index.empty:
        st.info("Historical player data is not available yet. Refresh local backup to build player profiles.")
        return

    options = [{"id": "", "name": "Select a player..."}] + index.to_dict("records")
    with st.container(key="player_selector_card"):
        selected = st.selectbox(
            "Search player",
            options,
            format_func=lambda player: player["name"],
            key="player_profile_selector",
        )
        st.markdown(
            '<div class="profile-selector-help">Start typing a name to find a player from club records.</div>',
            unsafe_allow_html=True,
        )
    if not selected.get("id"):
        st.markdown(
            """
            <div class="empty-profile-state">
                <div class="empty-profile-title">Find a player to unlock their career profile 🔎</div>
                <div class="empty-profile-copy">
                    View their all-time runs, wickets, catches, season-by-season trends, team history, and standout performances.
                </div>
                <div class="empty-profile-pill-row">
                    <span>📊 Career summary</span>
                    <span>📅 Season trends</span>
                    <span>🏆 Best performances</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    profile = get_player_profile_data(selected["id"], metadata_mtime(), player_aliases_mtime())
    profile_view = build_player_profile_view(profile)
    if profile_view["career"].empty:
        st.info("No local historical data is available for this player yet.")
        return

    render_player_header_card(profile_view)
    render_player_breakdown(profile_view["career"].iloc[0])
    render_player_highlights(profile_view)
    render_player_peer_comparison(profile_view)
    render_player_trends(profile_view["season_table"])
    render_player_season_table(profile_view["season_table"])
    render_player_grade_table(profile_view["grade_table"])
    render_player_milestones(profile_view["career"].iloc[0])


@st.cache_data
def load_player_profile_index(_local_version: float, _identity_version: float) -> pd.DataFrame:
    aliases = load_player_aliases()
    frames = []
    for category in ["batting", "bowling", "fielding"]:
        frame = read_processed_table(f"all_seasons_{category}")
        if not frame.empty:
            frames.append(apply_player_identity_mapping(frame, aliases))
    if not frames:
        return pd.DataFrame(columns=["id", "name"])

    combined = pd.concat(frames, ignore_index=True)
    if "canonical_player_id" not in combined or "canonical_player_name" not in combined:
        return pd.DataFrame(columns=["id", "name"])
    index = (
        combined[["canonical_player_id", "canonical_player_name"]]
        .dropna()
        .drop_duplicates()
        .rename(columns={"canonical_player_id": "id", "canonical_player_name": "name"})
    )
    index["name_sort"] = index["name"].astype(str).str.casefold()
    return index.sort_values("name_sort")[["id", "name"]].reset_index(drop=True)


@st.cache_data(show_spinner=False)
def build_player_profile_view(profile: dict[str, object]) -> dict[str, pd.DataFrame]:
    batting = add_batting_display_columns(apply_team_grade_display_columns(profile.get("batting", pd.DataFrame())))
    bowling = apply_team_grade_display_columns(profile.get("bowling", pd.DataFrame()))
    fielding = add_display_stat_aliases(apply_team_grade_display_columns(profile.get("fielding", pd.DataFrame())))
    season_table = build_player_season_table(batting, bowling, fielding)
    grade_table = build_player_grade_table(batting, bowling, fielding)
    career = build_player_career_totals(season_table, batting, bowling, fielding, profile)
    raw_profiles = build_player_raw_profile_table(batting, bowling, fielding)
    return {
        "batting": batting,
        "bowling": bowling,
        "fielding": fielding,
        "season_table": season_table,
        "grade_table": grade_table,
        "career": career,
        "raw_profiles": raw_profiles,
    }


def build_player_season_table(
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
) -> pd.DataFrame:
    seasons = sorted(
        set().union(
            set(batting.get("season", pd.Series(dtype=str)).dropna().astype(str)),
            set(bowling.get("season", pd.Series(dtype=str)).dropna().astype(str)),
            set(fielding.get("season", pd.Series(dtype=str)).dropna().astype(str)),
        ),
        key=profile_season_sort_key,
    )
    rows = []
    for season in seasons:
        bat = batting[batting["season"].astype(str) == season] if "season" in batting else batting.head(0)
        bowl = bowling[bowling["season"].astype(str) == season] if "season" in bowling else bowling.head(0)
        field = fielding[fielding["season"].astype(str) == season] if "season" in fielding else fielding.head(0)
        row = {
            "Season": season,
            "Teams/Grades": player_teams_grades([bat, bowl, field]),
            "Teams": player_teams([bat, bowl, field]),
            "Grades": player_grades([bat, bowl, field]),
            "Matches": player_match_total([bat, bowl, field]),
            "Innings": sum_column(bat, "battingInnings"),
            "Runs": sum_column(bat, "battingAggregate"),
            "BF": sum_column(bat, "battingBallsFaced"),
            "NO": sum_column(bat, "battingNotOuts"),
            "50s": sum_column(bat, "batting50s"),
            "100s": sum_column(bat, "batting100s"),
            "0s": sum_column(bat, "batting0s"),
            "4s": sum_column(bat, "battingFours"),
            "6s": sum_column(bat, "battingSixes"),
            "Wickets": sum_column(bowl, "bowlingWickets"),
            "Runs Against": sum_column(bowl, "bowlingRuns"),
            "Balls Bowled": sum_column(bowl, "bowlingBalls"),
            "Maidens": sum_column(bowl, "bowlingMaidens"),
            "5WI": sum_column(bowl, "bowling5WIs"),
            "Catches": sum_column(field, "fieldingTotalCatches"),
            "Stumpings": sum_column(field, "fieldingStumpings"),
            "Run Outs": sum_column(field, "fieldingRunOuts"),
        }
        row["Outs"] = max(0.0, row["Innings"] - row["NO"])
        row["Bat Avg"] = divide_or_none(row["Runs"], row["Outs"])
        row["Bat SR"] = reliable_batting_strike_rate(bat)
        row["HS"] = best_high_score(bat)
        row["Bowl Avg"] = divide_or_none(row["Runs Against"], row["Wickets"])
        row["Econ"] = divide_or_none(row["Runs Against"] * 6, row["Balls Bowled"])
        row["Bowl SR"] = divide_or_none(row["Balls Bowled"], row["Wickets"])
        row["BBI"] = best_bowling_value(bowl)
        row["Dismissals"] = row["Catches"] + row["Stumpings"] + row["Run Outs"]
        rows.append(row)

    table = pd.DataFrame(rows)
    return table.sort_values("Season", key=lambda series: series.map(profile_season_sort_key), ascending=False) if not table.empty else table


def build_player_grade_table(
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
) -> pd.DataFrame:
    frames = []
    for frame in [batting, bowling, fielding]:
        if frame.empty:
            continue
        output = frame.copy()
        output["Grade"] = output.apply(clean_profile_grade_from_row, axis=1)
        frames.append(output[["Grade"]].dropna())
    if not frames:
        return pd.DataFrame()

    grades = sorted(pd.concat(frames, ignore_index=True)["Grade"].dropna().unique(), key=grade_sort_key)
    rows = []
    for grade in grades:
        bat = batting[batting.apply(clean_profile_grade_from_row, axis=1) == grade] if not batting.empty else batting.head(0)
        bowl = bowling[bowling.apply(clean_profile_grade_from_row, axis=1) == grade] if not bowling.empty else bowling.head(0)
        field = fielding[fielding.apply(clean_profile_grade_from_row, axis=1) == grade] if not fielding.empty else fielding.head(0)
        row = {
            "Grade": grade,
            "Matches": player_match_total([bat, bowl, field]),
            "Innings": sum_column(bat, "battingInnings"),
            "Runs": sum_column(bat, "battingAggregate"),
            "BF": sum_column(bat, "battingBallsFaced"),
            "NO": sum_column(bat, "battingNotOuts"),
            "50s": sum_column(bat, "batting50s"),
            "100s": sum_column(bat, "batting100s"),
            "0s": sum_column(bat, "batting0s"),
            "4s": sum_column(bat, "battingFours"),
            "6s": sum_column(bat, "battingSixes"),
            "Wickets": sum_column(bowl, "bowlingWickets"),
            "Runs Against": sum_column(bowl, "bowlingRuns"),
            "Balls Bowled": sum_column(bowl, "bowlingBalls"),
            "Maidens": sum_column(bowl, "bowlingMaidens"),
            "5WI": sum_column(bowl, "bowling5WIs"),
            "Catches": sum_column(field, "fieldingTotalCatches"),
            "Stumpings": sum_column(field, "fieldingStumpings"),
            "Run Outs": sum_column(field, "fieldingRunOuts"),
        }
        row["Outs"] = max(0.0, row["Innings"] - row["NO"])
        row["Bat Avg"] = divide_or_none(row["Runs"], row["Outs"])
        row["Bat SR"] = reliable_batting_strike_rate(bat)
        row["HS"] = best_high_score(bat)
        row["Bowl Avg"] = divide_or_none(row["Runs Against"], row["Wickets"])
        row["Econ"] = divide_or_none(row["Runs Against"] * 6, row["Balls Bowled"])
        row["Bowl SR"] = divide_or_none(row["Balls Bowled"], row["Wickets"])
        row["BBI"] = best_bowling_value(bowl)
        row["Dismissals"] = row["Catches"] + row["Stumpings"] + row["Run Outs"]
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    output = pd.DataFrame(rows)
    output["_grade_sort"] = output["Grade"].map(grade_sort_key)
    return output.sort_values("_grade_sort").drop(columns="_grade_sort").reset_index(drop=True)


def build_player_career_totals(
    season_table: pd.DataFrame,
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
    profile: dict[str, object],
) -> pd.DataFrame:
    if season_table.empty:
        return pd.DataFrame()
    totals = {
        "Player": profile.get("player_info", {}).get("canonical_player_name", ""),
        "canonical_player_id": profile.get("player_info", {}).get("canonical_player_id", ""),
        "Teams/Grades": player_profile_team_summary(season_table),
        "Grades Played": player_unique_grades([batting, bowling, fielding]),
        "Seasons": ", ".join(sorted(season_table["Season"].dropna().astype(str), key=profile_season_sort_key)),
        "Career Span": career_span_label(season_table["Season"].dropna().astype(str).tolist()),
        "Merged Profiles": int(profile.get("raw_aliases", pd.DataFrame()).shape[0]),
        "Seasons Count": int(season_table["Season"].dropna().astype(str).nunique()),
        "Matches": sum_numeric_series(season_table["Matches"]),
        "Innings": sum_numeric_series(season_table["Innings"]),
        "Runs": sum_numeric_series(season_table["Runs"]),
        "BF": sum_numeric_series(season_table["BF"]),
        "Outs": sum_numeric_series(season_table["Outs"]),
        "Wickets": sum_numeric_series(season_table["Wickets"]),
        "Runs Against": sum_numeric_series(season_table["Runs Against"]),
        "Balls Bowled": sum_numeric_series(season_table["Balls Bowled"]),
        "Catches": sum_numeric_series(season_table["Catches"]),
        "Stumpings": sum_numeric_series(season_table["Stumpings"]),
        "Run Outs": sum_numeric_series(season_table["Run Outs"]),
        "Dismissals": sum_numeric_series(season_table["Dismissals"]),
        "50s": sum_numeric_series(season_table["50s"]),
        "100s": sum_numeric_series(season_table["100s"]),
        "0s": sum_numeric_series(season_table["0s"]) if "0s" in season_table else 0,
        "4s": sum_numeric_series(season_table["4s"]) if "4s" in season_table else 0,
        "6s": sum_numeric_series(season_table["6s"]) if "6s" in season_table else 0,
        "Maidens": sum_numeric_series(season_table["Maidens"]) if "Maidens" in season_table else 0,
        "5WI": sum_numeric_series(season_table["5WI"]),
        "HS": best_high_score(batting),
        "BBI": best_bowling_value(bowling),
    }
    totals["Bat Avg"] = divide_or_none(totals["Runs"], totals["Outs"])
    totals["Bat SR"] = reliable_batting_strike_rate(batting)
    totals["Bowl Avg"] = divide_or_none(totals["Runs Against"], totals["Wickets"])
    totals["Econ"] = divide_or_none(totals["Runs Against"] * 6, totals["Balls Bowled"])
    totals["Bowl SR"] = divide_or_none(totals["Balls Bowled"], totals["Wickets"])
    totals["Overs"] = format_balls_as_overs(totals["Balls Bowled"]) if totals["Balls Bowled"] else "—"
    return pd.DataFrame([totals])


def render_player_header_card(profile_view: dict[str, pd.DataFrame]) -> None:
    career = profile_view["career"].iloc[0]
    badges = player_role_badges(career, profile_view)
    badge_html = "".join(f'<span class="profile-badge">{html.escape(badge)}</span>' for badge in badges)
    insight = player_profile_insight(career, badges)
    st.markdown(
        (
            '<div class="player-hero-card">'
            '<div class="profile-main-block">'
            '<div class="profile-kicker">Player Profile</div>'
            f'<div class="profile-name">{html.escape(str(career.get("Player", "-")))}</div>'
            '<div class="profile-summary-stack">'
            f'<div class="profile-insight">{html.escape(insight)}</div>'
            f'<div class="profile-meta">Grades played: {html.escape(str(career.get("Grades Played", "—") or "—"))}</div>'
            f'<div class="profile-meta">Career span: {html.escape(str(career.get("Career Span", "—") or "—"))}</div>'
            '</div>'
            '</div>'
            f'<div class="profile-badges">{badge_html}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def player_role_badges(career: pd.Series, profile_view: dict[str, pd.DataFrame]) -> list[str]:
    matches = numeric_value(career, "Matches")
    runs = numeric_value(career, "Runs")
    wickets = numeric_value(career, "Wickets")
    bat_avg = numeric_value(career, "Bat Avg")
    bat_sr = numeric_value(career, "Bat SR")
    bowl_avg = numeric_value(career, "Bowl Avg")
    bowl_sr = numeric_value(career, "Bowl SR")
    economy = numeric_value(career, "Econ")
    fours = numeric_value(career, "4s")
    sixes = numeric_value(career, "6s")
    stumpings = numeric_value(career, "Stumpings")
    dismissals = numeric_value(career, "Dismissals")
    balls_faced = numeric_value(career, "BF")
    outs = numeric_value(career, "Outs")
    balls_bowled = numeric_value(career, "Balls Bowled")
    overs = balls_bowled / 6 if balls_bowled else 0
    matches_20 = matches >= 20
    matches_30 = matches >= 30
    wickets_per_match = divide_or_none(wickets, matches) or 0
    runs_per_match = divide_or_none(runs, matches) or 0
    balls_per_dismissal = divide_or_none(balls_faced, outs) or 0
    leader_counts = player_leader_counts(profile_view)
    reliable = reliable_batting_components(profile_view.get("batting", pd.DataFrame()))
    reliable_bat_sr = divide_or_none(reliable["runs"] * 100, reliable["balls"]) or 0
    season_table = profile_view.get("season_table", pd.DataFrame())
    standout_count = sum(int(value) for value in leader_counts.values())
    star_batter = matches_30 and bat_avg > 25
    big_hitter = matches_30 and matches and sixes / matches > 0.3
    gap_finder = matches_30 and matches and fours / matches > 2

    candidates: list[dict[str, object]] = []

    def add_candidate(label: str, group: str, priority: int, condition: bool) -> None:
        if condition:
            candidates.append({"label": label, "group": group, "priority": priority})

    club_legend = matches >= 200 or runs >= 4000 or wickets >= 250
    genuine_all_rounder = runs >= 1000 and wickets >= 100
    all_round_contributor = matches_30 and bat_avg > 12 and runs >= 300 and wickets >= 30
    upcoming_star = matches_20 and matches < 50 and (
        bat_avg > 20 or (0 < bowl_avg < 20 and wickets >= 15)
    )
    mr_consistent = player_has_consistent_seasons(season_table)

    add_candidate("Club Legend", "legacy", 1, club_legend)
    add_candidate("Genuine All-rounder", "role", 2, genuine_all_rounder)
    add_candidate("All-round Contributor", "role", 3, all_round_contributor and not genuine_all_rounder)
    add_candidate("Upcoming Star", "role", 4, upcoming_star)
    add_candidate("Star Batter", "batting", 5, star_batter)
    add_candidate("Star Bowler", "bowling", 6, matches_30 and wickets >= 30 and 0 < bowl_avg < 20)
    add_candidate("Run Machine", "batting", 7, runs >= 2000 or (runs_per_match >= 25 and matches >= 50))
    add_candidate("Dependable Batter", "batting", 7, matches_30 and bat_avg > 18 and not star_batter)
    add_candidate("Wicket Taker", "bowling", 8, matches_20 and wickets_per_match > 1)
    add_candidate("Golden Arm", "bowling", 9, matches_30 and wickets_per_match < 0.60 and wickets >= 15 and 0 < bowl_avg < 25)
    add_candidate("Partnership Breaker", "bowling", 10, overs > 150 and wickets >= 30 and 0 < bowl_sr < 35)
    add_candidate("Economy Controller", "bowling", 11, overs > 150 and 0 < economy < 3.5 and (wickets >= 30 or matches >= 30))
    add_candidate("Big Hitter", "style", 12, big_hitter)
    add_candidate("Values His Wicket", "style", 13, matches_20 and balls_per_dismissal >= 30)
    add_candidate("Gap Finder", "style", 14, gap_finder)
    add_candidate("Quick Scorer", "style", 15, matches_20 and reliable_bat_sr >= 90 and reliable["balls"] >= 125 and reliable["runs"] >= 125)
    add_candidate("Boundary Maker", "style", 15, matches_20 and matches and (fours + sixes) / matches > 2.5 and not big_hitter and not gap_finder)
    add_candidate("Workhorse", "bowling", 16, overs >= 250 and matches >= 30)
    add_candidate("Safe Hands", "fielding", 17, stumpings <= 0 and matches_20 and matches and dismissals / matches > 0.4)
    add_candidate("Keeper Impact", "fielding", 18, stumpings > 0)
    add_candidate(season_standout_label(standout_count), "achievement", 19, standout_count > 0)
    add_candidate("Milestone Maker", "legacy", 20, (runs >= 1000 or wickets >= 100 or matches >= 100) and not club_legend)
    add_candidate("Club Veteran", "legacy", 21, matches >= 100 and not club_legend)
    add_candidate("Mr Consistent", "achievement", 22, mr_consistent)

    if not candidates:
        return ["Club Contributor"] if matches_20 else ["Emerging Player"]
    return select_profile_badges(candidates)


def player_profile_insight(career: pd.Series, badges: list[str]) -> str:
    matches = numeric_value(career, "Matches")
    badge_set = {base_badge_label(badge) for badge in badges}
    if "Club Legend" in badge_set and ("Genuine All-rounder" in badge_set or "All-round Contributor" in badge_set):
        return "Long-serving club figure with major contributions across bat and ball."
    if "Club Legend" in badge_set and any(badge in badge_set for badge in ["Star Batter", "Run Machine", "Dependable Batter", "Big Hitter", "Gap Finder"]):
        return "Long-serving club figure with a major batting footprint across the record book."
    if "Club Legend" in badge_set and any(badge in badge_set for badge in ["Star Bowler", "Partnership Breaker", "Wicket Taker", "Economy Controller", "Workhorse"]):
        return "Long-serving club figure with sustained bowling impact across seasons."
    if "Club Legend" in badge_set and ("Safe Hands" in badge_set or "Keeper Impact" in badge_set):
        return "Long-serving club figure with strong fielding impact across the available records."
    if "Club Legend" in badge_set:
        return "Long-serving club figure with a major footprint across the record book."
    if "Genuine All-rounder" in badge_set:
        return "Strong two-skill contributor across bat and ball."
    if "All-round Contributor" in badge_set:
        return "Contributes meaningfully with both bat and ball."
    if "Upcoming Star" in badge_set:
        return "Early-career player already showing strong signs of future impact."
    if "Star Batter" in badge_set:
        return "High-impact run-maker with strong batting returns across seasons."
    if "Run Machine" in badge_set:
        return "Consistent run scorer with a strong footprint across seasons."
    if "Dependable Batter" in badge_set:
        return "Reliable batting contributor with consistent returns across the record book."
    if "Big Hitter" in badge_set:
        return "Boundary-focused batter with a strong six-hitting profile."
    if "Gap Finder" in badge_set or "Boundary Maker" in badge_set:
        return "Finds the boundary regularly through consistent four-hitting."
    if "Values His Wicket" in badge_set:
        return "Patient batter who spends time at the crease and values his wicket."
    if "Quick Scorer" in badge_set:
        return "Tempo-setting batter with strong recent scoring rate."
    if "Star Bowler" in badge_set:
        return "High-impact bowler with strong wicket-taking and average profile."
    if "Partnership Breaker" in badge_set:
        return "Regular wicket threat who can break games open with the ball."
    if "Wicket Taker" in badge_set:
        return "Consistently finds wickets across the available club records."
    if "Golden Arm" in badge_set:
        return "Makes an impact with the ball despite limited bowling volume."
    if "Economy Controller" in badge_set:
        return "Disciplined bowler who keeps scoring rates under control."
    if "Workhorse" in badge_set:
        return "Trusted to carry a heavy bowling workload across seasons."
    if "Mr Consistent" in badge_set:
        return "Delivers across seasons, not just in one standout year."
    if "Safe Hands" in badge_set:
        return "Reliable fielding contributor across the available records."
    if "Keeper Impact" in badge_set:
        return "Wicketkeeping contributor with impact behind the stumps."
    if "Season Standout" in badge_set:
        return "Has produced standout season-level performances in the club record book."
    if "Milestone Maker" in badge_set:
        return "Has crossed major club milestones across the available records."
    if "Club Veteran" in badge_set:
        return "Experienced club contributor with a long record across seasons."
    if "Emerging Player" in badge_set or matches < 20:
        return "Early career profile building across the available club records."
    return "Club contributor across the available records."


def season_standout_label(count: int) -> str:
    return "Season Standout" if count <= 1 else f"Season Standout x {count}"


def base_badge_label(label: str) -> str:
    return re.sub(r"\s+x\s+\d+$", "", str(label)).strip()


def select_profile_badges(candidates: list[dict[str, object]]) -> list[str]:
    ordered = sorted(candidates, key=lambda candidate: int(candidate["priority"]))
    selected: list[str] = []
    for candidate in ordered:
        label = str(candidate["label"])
        if label not in selected:
            selected.append(label)
    return selected


def reliable_batting_components(batting: pd.DataFrame) -> dict[str, float]:
    if batting.empty or "season" not in batting:
        return {"runs": 0.0, "balls": 0.0}
    reliable = batting[batting["season"].map(profile_season_sort_key) >= profile_season_sort_key("Summer 2024/25")].copy()
    return {
        "runs": sum_column(reliable, "battingAggregate"),
        "balls": sum_column(reliable, "battingBallsFaced"),
    }


def player_has_consistent_seasons(season_table: pd.DataFrame) -> bool:
    if season_table.empty:
        return False
    runs = pd.to_numeric(season_table.get("Runs", pd.Series(dtype=float)), errors="coerce").fillna(0)
    wickets = pd.to_numeric(season_table.get("Wickets", pd.Series(dtype=float)), errors="coerce").fillna(0)
    return int((runs >= 200).sum()) >= 3 or int((wickets >= 15).sum()) >= 3


def render_player_career_kpis(career: pd.Series) -> None:
    cards = [
        ("Matches", format_int(career.get("Matches"))),
        ("Seasons", format_int(career.get("Seasons Count"))),
        ("Runs", format_int(career.get("Runs"))),
        ("Wickets", format_int(career.get("Wickets"))),
        ("Catches", format_int(career.get("Catches"))),
        ("Batting Average", format_decimal(career.get("Bat Avg"))),
        ("Bowling Average", format_decimal(career.get("Bowl Avg"))),
        ("Bowling Strike Rate", format_decimal(career.get("Bowl SR"))),
        ("Economy Rate", format_decimal(career.get("Econ"))),
        ("Run Outs", format_int(career.get("Run Outs"))),
    ]
    if numeric_value(career, "Stumpings") > 1:
        cards.append(("Stumpings", format_int(career.get("Stumpings"))))

    for index in range(0, len(cards), 6):
        columns = st.columns(6)
        for column, (label, value) in zip(columns, cards[index : index + 6]):
            with column:
                render_profile_kpi_card(label, value)
    st.markdown("<div class='dashboard-spacer'></div>", unsafe_allow_html=True)


def render_profile_kpi_card(label: str, value: str) -> None:
    st.markdown(
        (
            '<div class="profile-kpi-card">'
            f'<div class="profile-kpi-label">{html.escape(label)}</div>'
            f'<div class="profile-kpi-value">{html.escape(str(value))}</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def render_player_highlights(profile_view: dict[str, pd.DataFrame]) -> None:
    cards = player_highlight_cards(profile_view)
    if not cards:
        return
    render_section_heading("Career Highlights 🌟")
    for index in range(0, len(cards), 4):
        columns = st.columns(4)
        for column, card in zip(columns, cards[index : index + 4]):
            with column:
                render_record_card(card)


def player_highlight_cards(profile_view: dict[str, pd.DataFrame]) -> list[dict[str, str]]:
    career = profile_view["career"].iloc[0]
    season_table = profile_view["season_table"]
    batting = profile_view["batting"]
    bowling = profile_view["bowling"]
    cards = []
    leader_counts = player_leader_counts(profile_view)
    if str(career.get("HS", "—")) != "—":
        row = best_high_score_row(batting)
        cards.append({"title": "Highest Score", "player": str(career["Player"]), "value": str(career["HS"]), "meta": profile_record_meta(row)})
    if str(career.get("BBI", "—")) != "—":
        row = best_bowling_row(bowling)
        cards.append({"title": "Best Bowling Figures", "player": str(career["Player"]), "value": str(career["BBI"]), "meta": profile_record_meta(row)})
    for title, metric, suffix in [
        ("Best Season by Runs", "Runs", "runs"),
        ("Best Season by Wickets", "Wickets", "wickets"),
    ]:
        if metric in season_table:
            output = season_table.copy()
            output[metric] = pd.to_numeric(output[metric], errors="coerce").fillna(0)
            output = output[output[metric] > 0].sort_values(metric, ascending=False)
            if not output.empty:
                row = output.iloc[0]
                cards.append({"title": title, "player": str(row["Season"]), "value": f"{int(row[metric]):,} {suffix}", "meta": str(row.get("Teams/Grades", ""))})
    for title, metric, suffix in [("Total 50s", "50s", "fifties"), ("Total 100s", "100s", "hundreds"), ("Total 5-Wicket Hauls", "5WI", "five-wicket hauls")]:
        value = numeric_value(career, metric)
        if value > 0:
            cards.append({"title": title, "player": str(career["Player"]), "value": f"{int(value):,} {suffix}", "meta": ""})
    leader_details = player_leader_details(profile_view)
    for title, key, suffix in [
        ("Highest Run Maker at Club", "club_run_leader", "season"),
        ("Highest Run Maker in Grade", "grade_run_leader", "grade season"),
        ("Highest Wicket Taker at Club", "club_wicket_leader", "season"),
        ("Highest Wicket Taker in Grade", "grade_wicket_leader", "grade season"),
    ]:
        value = int(leader_counts.get(key, 0))
        if value > 0:
            label = suffix if value == 1 else f"{suffix}s"
            cards.append(
                {
                    "title": title,
                    "player": str(career["Player"]),
                    "value": f"{value:,} {label}",
                    "meta": compact_leader_detail_meta(leader_details.get(key, [])),
                }
            )
    return cards[:10]


def player_leader_counts(profile_view: dict[str, pd.DataFrame]) -> dict[str, int]:
    return {key: len(values) for key, values in player_leader_details(profile_view).items()}


def player_leader_details(profile_view: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
    career = profile_view["career"]
    if career.empty:
        return {}
    player_id = str(career.iloc[0].get("canonical_player_id", "")).strip()
    if not player_id:
        return {}
    return cached_player_leader_details(player_id, metadata_mtime(), player_aliases_mtime())


@st.cache_data
def cached_player_leader_details(player_id: str, _local_version: float, _identity_version: float) -> dict[str, list[str]]:
    historical_data = load_hall_of_fame_data(_local_version, _identity_version)
    if historical_data is None:
        return {}
    batting = historical_data.get("batting_raw", pd.DataFrame())
    bowling = historical_data.get("bowling_raw", pd.DataFrame())
    return {
        "club_run_leader": player_season_leader_details(batting, player_id, "battingAggregate", by_grade=False),
        "grade_run_leader": player_season_leader_details(batting, player_id, "battingAggregate", by_grade=True),
        "club_wicket_leader": player_season_leader_details(bowling, player_id, "bowlingWickets", by_grade=False),
        "grade_wicket_leader": player_season_leader_details(bowling, player_id, "bowlingWickets", by_grade=True),
    }


def count_player_season_leaders(df: pd.DataFrame, player_id: str, value_column: str, by_grade: bool) -> int:
    return len(player_season_leader_details(df, player_id, value_column, by_grade))


def player_season_leader_details(df: pd.DataFrame, player_id: str, value_column: str, by_grade: bool) -> list[str]:
    required = {"season", "canonical_player_id", value_column}
    if df.empty or not required.issubset(df.columns):
        return []
    output = df.copy()
    output[value_column] = pd.to_numeric(output[value_column], errors="coerce").fillna(0)
    output = output[output[value_column] > 0]
    if output.empty:
        return []
    scope_columns = ["season"]
    if by_grade:
        output["Grade"] = output.apply(clean_profile_grade_from_row, axis=1)
        output = output[output["Grade"].astype(str).str.strip() != ""]
        scope_columns.append("Grade")
    grouped = (
        output.groupby(scope_columns + ["canonical_player_id"], dropna=False, as_index=False)[value_column]
        .sum()
    )
    grouped["_scope_max"] = grouped.groupby(scope_columns, dropna=False)[value_column].transform("max")
    leaders = grouped[
        (grouped["canonical_player_id"].astype(str) == player_id)
        & (grouped[value_column] == grouped["_scope_max"])
        & (grouped[value_column] > 0)
    ]
    if leaders.empty:
        return []
    details = []
    for _, row in leaders[scope_columns].drop_duplicates().sort_values(scope_columns).iterrows():
        season = str(row.get("season", "")).strip()
        if by_grade:
            grade = str(row.get("Grade", "")).strip()
            label = f"{season} · {grade}" if grade else season
        else:
            label = season
        if label and label not in details:
            details.append(label)
    return details


def compact_leader_detail_meta(details: list[str], limit: int = 3) -> str:
    if not details:
        return ""
    visible = details[:limit]
    remaining = len(details) - len(visible)
    suffix = f", +{remaining} more" if remaining > 0 else ""
    return ", ".join(visible) + suffix


def render_player_peer_comparison(profile_view: dict[str, pd.DataFrame]) -> None:
    career = profile_view["career"].iloc[0]
    season_table = profile_view.get("season_table", pd.DataFrame())
    if season_table.empty or "Season" not in season_table:
        return
    seasons = tuple(
        sorted(
            season_table["Season"].dropna().astype(str).unique(),
            key=profile_season_sort_key,
        )
    )
    player_id = str(career.get("canonical_player_id", "")).strip()
    if not player_id or not seasons:
        return

    comparison = get_player_peer_comparison(player_id, seasons, metadata_mtime(), player_aliases_mtime())
    if not comparison.get("batting") and not comparison.get("bowling"):
        return

    render_section_heading("Player vs Peers 📊")
    render_section_subtext("Compared against players from the same seasons.")
    st.markdown(
        """
        <div class="peer-explainer">
            <div class="peer-legend">
                <span><i class="legend-dot player-dot"></i> Player</span>
                <span><i class="legend-marker avg-dot"></i> Peer avg.</span>
            </div>
            <div class="peer-note">Line shows range from lowest to highest peer value. Strike rate uses data from Winter 2025 onward.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    columns = st.columns(2)
    with columns[0]:
        render_peer_comparison_card("Batting", comparison.get("batting", []), "#6D4DFF")
    with columns[1]:
        render_peer_comparison_card("Bowling", comparison.get("bowling", []), "#10B981")


@st.cache_data(show_spinner=False)
def get_player_peer_comparison(
    player_id: str,
    seasons: tuple[str, ...],
    local_version: float,
    identity_version: float,
) -> dict[str, list[dict[str, object]]]:
    _ = (local_version, identity_version)
    aliases = load_player_aliases()
    batting = apply_player_identity_mapping(read_processed_table("all_seasons_batting"), aliases)
    bowling = apply_player_identity_mapping(read_processed_table("all_seasons_bowling"), aliases)
    batting_rows = aggregate_peer_batting(batting, seasons)
    bowling_rows = aggregate_peer_bowling(bowling, seasons)
    return {
        "batting": build_peer_metric_rows(
            batting_rows,
            player_id,
            [
                ("Batting Avg", "bat_avg", False, "decimal"),
                ("Strike Rate", "bat_sr", False, "decimal"),
                ("Boundary Rate", "boundary_rate", False, "decimal"),
                ("Innings per Duck", "innings_per_duck", False, "decimal"),
            ],
            average_overrides={
                "bat_avg": divide_or_none(sum_numeric(batting_rows, "runs"), sum_numeric(batting_rows, "outs")),
                "bat_sr": divide_or_none(
                    sum_numeric(batting_rows, "reliable_runs") * 100,
                    sum_numeric(batting_rows, "reliable_balls"),
                ),
                "boundary_rate": divide_or_none(sum_numeric(batting_rows, "boundaries"), sum_numeric(batting_rows, "innings")),
                "innings_per_duck": divide_or_none(sum_numeric(batting_rows, "innings"), sum_numeric(batting_rows, "ducks")),
            },
        ),
        "bowling": build_peer_metric_rows(
            bowling_rows,
            player_id,
            [
                ("Bowling Avg", "bowl_avg", True, "decimal"),
                ("Bowling SR", "bowl_sr", True, "decimal"),
                ("Economy Rate", "economy", True, "decimal"),
                ("Overs per Maiden", "overs_per_maiden", True, "decimal"),
            ],
            average_overrides={
                "bowl_avg": divide_or_none(sum_numeric(bowling_rows, "runs_against"), sum_numeric(bowling_rows, "wickets")),
                "bowl_sr": divide_or_none(sum_numeric(bowling_rows, "balls"), sum_numeric(bowling_rows, "wickets")),
                "economy": divide_or_none(sum_numeric(bowling_rows, "runs_against") * 6, sum_numeric(bowling_rows, "balls")),
                "overs_per_maiden": divide_or_none(sum_numeric(bowling_rows, "overs"), sum_numeric(bowling_rows, "maidens")),
            },
        ),
    }


def aggregate_peer_batting(batting: pd.DataFrame, seasons: tuple[str, ...]) -> pd.DataFrame:
    if batting.empty or "season" not in batting or "canonical_player_id" not in batting:
        return pd.DataFrame()
    output = batting[batting["season"].astype(str).isin(seasons)].copy()
    if output.empty:
        return pd.DataFrame()
    rows = []
    for player_id, group in output.groupby("canonical_player_id", dropna=False):
        player_id = str(player_id).strip()
        if not player_id:
            continue
        runs = sum_column(group, "battingAggregate")
        innings = sum_column(group, "battingInnings")
        not_outs = sum_column(group, "battingNotOuts")
        outs = max(0.0, innings - not_outs)
        balls = sum_column(group, "battingBallsFaced")
        reliable = group[group["season"].map(profile_season_sort_key) >= profile_season_sort_key("Winter 2025")].copy()
        reliable_runs = sum_column(reliable, "battingAggregate")
        reliable_balls = sum_column(reliable, "battingBallsFaced")
        boundaries = sum_column(group, "battingFours") + sum_column(group, "battingSixes")
        ducks = sum_column(group, "batting0s")
        rows.append(
            {
                "canonical_player_id": player_id,
                "runs": runs,
                "balls_faced": balls,
                "innings": innings,
                "outs": outs,
                "reliable_runs": reliable_runs,
                "reliable_balls": reliable_balls,
                "bat_avg": divide_or_none(runs, outs),
                "bat_sr": divide_or_none(reliable_runs * 100, reliable_balls),
                "boundaries": boundaries,
                "boundary_rate": divide_or_none(boundaries, innings),
                "ducks": ducks,
                "innings_per_duck": divide_or_none(innings, ducks),
            }
        )
    return pd.DataFrame(rows)


def aggregate_peer_bowling(bowling: pd.DataFrame, seasons: tuple[str, ...]) -> pd.DataFrame:
    if bowling.empty or "season" not in bowling or "canonical_player_id" not in bowling:
        return pd.DataFrame()
    output = bowling[bowling["season"].astype(str).isin(seasons)].copy()
    if output.empty:
        return pd.DataFrame()
    rows = []
    for player_id, group in output.groupby("canonical_player_id", dropna=False):
        player_id = str(player_id).strip()
        if not player_id:
            continue
        wickets = sum_column(group, "bowlingWickets")
        runs_against = sum_column(group, "bowlingRuns")
        balls = sum_column(group, "bowlingBalls")
        maidens = sum_column(group, "bowlingMaidens")
        overs = balls / 6 if balls else 0.0
        rows.append(
            {
                "canonical_player_id": player_id,
                "wickets": wickets,
                "runs_against": runs_against,
                "balls": balls,
                "overs": overs,
                "bowl_avg": divide_or_none(runs_against, wickets),
                "bowl_sr": divide_or_none(balls, wickets),
                "economy": divide_or_none(runs_against * 6, balls),
                "maidens": maidens,
                "overs_per_maiden": divide_or_none(overs, maidens),
            }
        )
    return pd.DataFrame(rows)


def build_peer_metric_rows(
    data: pd.DataFrame,
    player_id: str,
    metrics: list[tuple[str, str, bool, str]],
    average_overrides: dict[str, float | None] | None = None,
) -> list[dict[str, object]]:
    if data.empty or "canonical_player_id" not in data:
        return []
    average_overrides = average_overrides or {}
    rows = []
    for label, column, lower_is_better, value_format in metrics:
        if column not in data:
            rows.append(empty_peer_metric_row(label, lower_is_better, value_format))
            continue
        values = pd.to_numeric(data[column], errors="coerce")
        valid_values = values.dropna()
        player_values = data.loc[data["canonical_player_id"].astype(str) == player_id, column]
        player_value = pd.to_numeric(player_values, errors="coerce").dropna()
        value = float(player_value.iloc[0]) if not player_value.empty else None
        if valid_values.empty:
            rows.append(empty_peer_metric_row(label, lower_is_better, value_format))
            continue
        minimum = float(valid_values.min())
        maximum = float(valid_values.max())
        if column in average_overrides:
            override_average = average_overrides[column]
            average = float(override_average) if override_average is not None else None
        else:
            average = float(valid_values.mean())
        rows.append(
            {
                "label": label,
                "value": value,
                "average": average,
                "minimum": minimum,
                "maximum": maximum,
                "lower_is_better": lower_is_better,
                "format": value_format,
                "status": peer_metric_status(value, average, minimum, maximum, lower_is_better),
            }
        )
    return rows


def sum_numeric(data: pd.DataFrame, column: str) -> float:
    if data.empty or column not in data:
        return 0.0
    return float(pd.to_numeric(data[column], errors="coerce").fillna(0).sum())


def empty_peer_metric_row(label: str, lower_is_better: bool, value_format: str) -> dict[str, object]:
    return {
        "label": label,
        "value": None,
        "average": None,
        "minimum": None,
        "maximum": None,
        "lower_is_better": lower_is_better,
        "format": value_format,
        "status": "—",
    }


def peer_metric_status(
    value: float | None,
    average: float | None,
    minimum: float | None,
    maximum: float | None,
    lower_is_better: bool,
) -> str:
    if value is None or average is None or minimum is None or maximum is None:
        return "—"
    if average == 0:
        return "Around avg"
    if lower_is_better:
        if value < average:
            return "Better than avg"
        if value <= average * 1.1:
            return "Around avg"
        return "Worse than avg"
    if value > average:
        return "Better than avg"
    if value >= average * 0.9:
        return "Around avg"
    return "Worse than avg"


def peer_marker_position(value: float | None, minimum: float | None, maximum: float | None) -> float | None:
    if value is None or minimum is None or maximum is None:
        return None
    if maximum <= minimum:
        return 50.0
    return max(0.0, min(100.0, ((value - minimum) / (maximum - minimum)) * 100))


def format_peer_metric_value(value: object, value_format: str) -> str:
    if value is None or pd.isna(value):
        return "—"
    numeric = float(value)
    if value_format == "number":
        return f"{int(round(numeric)):,}"
    return f"{numeric:.2f}"


def peer_status_class(status: object) -> str:
    normalized = str(status).strip().lower()
    if normalized == "better than avg":
        return "positive"
    if normalized == "worse than avg":
        return "negative"
    return "neutral"


def peer_metric_note(label: object) -> str:
    notes = {
        "Strike Rate": "From Winter 2025 onward",
        "Boundary Rate": "4s + 6s per innings",
        "Innings per Duck": "Higher means fewer ducks",
        "Overs per Maiden": "Lower means maidens are more frequent",
    }
    return notes.get(str(label), "")


def render_peer_comparison_card(title: str, rows: list[dict[str, object]], accent: str) -> None:
    if not rows:
        rows = [empty_peer_metric_row("No data", False, "number")]
    row_html = []
    for row in rows:
        value = row.get("value")
        average = row.get("average")
        minimum = row.get("minimum")
        maximum = row.get("maximum")
        player_position = peer_marker_position(value, minimum, maximum)
        average_position = peer_marker_position(average, minimum, maximum)
        player_marker = (
            f'<span class="peer-marker player-marker" style="left:{player_position:.1f}%;"></span>'
            if player_position is not None
            else ""
        )
        average_marker = (
            f'<span class="peer-marker avg-marker" style="left:{average_position:.1f}%;"></span>'
            if average_position is not None
            else ""
        )
        metric_label = html.escape(str(row["label"]))
        metric_note = peer_metric_note(row["label"])
        if metric_note:
            metric_label = f'{metric_label}<span class="peer-metric-note">{html.escape(metric_note)}</span>'
        status = str(row["status"])
        row_html.append(
            '<div class="peer-row">'
            '<div class="peer-row-top">'
            f'<span class="peer-metric">{metric_label}</span>'
            f'<span class="peer-value">{html.escape(format_peer_metric_value(value, str(row["format"])))}</span>'
            "</div>"
            '<div class="peer-row-meta">'
            f'<span>Peer avg. {html.escape(format_peer_metric_value(average, str(row["format"])))}</span>'
            f'<strong class="peer-status {peer_status_class(status)}">{html.escape(status)}</strong>'
            "</div>"
            '<div class="peer-range">'
            f"{average_marker}{player_marker}"
            "</div>"
            "</div>"
        )
    st.markdown(
        (
            '<div class="peer-card">'
            f'<h4 style="--peer-accent:{html.escape(accent)}">{html.escape(title)}</h4>'
            f'{"".join(row_html)}'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_player_trends(season_table: pd.DataFrame) -> None:
    if season_table.empty:
        return
    render_section_heading("Season Trends 📈")
    chart_data = season_table.sort_values("Season", key=lambda series: series.map(profile_season_sort_key))
    specs = [("Runs by Season", "Runs", "#6D4DFF"), ("Wickets by Season", "Wickets", "#10B981")]
    for index in range(0, len(specs), 2):
        columns = st.columns(2)
        for column, (title, metric, color) in zip(columns, specs[index : index + 2]):
            if metric not in chart_data or pd.to_numeric(chart_data[metric], errors="coerce").fillna(0).sum() <= 0:
                continue
            with column:
                with st.container(key=f"profile_chart_{metric.lower()}"):
                    st.markdown(f'<div class="profile-chart-title">{html.escape(title)}</div>', unsafe_allow_html=True)
                    values = chart_data[["Season", metric]].copy()
                    values[metric] = pd.to_numeric(values[metric], errors="coerce").fillna(0)
                    season_count = values["Season"].nunique()
                    bar_size = 10 if season_count >= 12 else 14 if season_count >= 8 else 20
                    label_size = 9 if season_count >= 8 else 10
                    base = (
                        alt.Chart(values)
                        .encode(
                            x=alt.X("Season:N", sort=list(values["Season"]), axis=alt.Axis(labelAngle=-35, labelColor="#737998", title=None)),
                            y=alt.Y(f"{metric}:Q", axis=alt.Axis(grid=False, labelColor="#737998", title=None)),
                            tooltip=[alt.Tooltip("Season:N"), alt.Tooltip(f"{metric}:Q", format=",.0f")],
                        )
                    )
                    chart = (
                        base.mark_bar(cornerRadiusTopLeft=6, cornerRadiusTopRight=6, color=color, size=bar_size)
                        + base.mark_text(
                            align="center",
                            baseline="top",
                            color="#ffffff",
                            dy=5,
                            fontSize=label_size,
                            fontWeight=800,
                        ).encode(text=alt.Text(f"{metric}:Q", format=",.0f"))
                    ).properties(height=240).configure(background="#FFFFFF").configure_view(fill="#FFFFFF", stroke=None)
                    st.altair_chart(chart, use_container_width=True)
    render_player_average_trends(chart_data)


def render_player_average_trends(chart_data: pd.DataFrame) -> None:
    rows = []
    for _, row in chart_data.sort_values("Season", key=lambda series: series.map(profile_season_sort_key)).iterrows():
        bat_avg = pd.to_numeric(row.get("Bat Avg"), errors="coerce")
        bowl_avg = pd.to_numeric(row.get("Bowl Avg"), errors="coerce")
        if pd.notna(bat_avg):
            rows.append(
                {
                    "Season": row["Season"],
                    "Season Average": float(bat_avg),
                    "Metric": "Batting average",
                }
            )
        if pd.notna(bowl_avg):
            rows.append(
                {
                    "Season": row["Season"],
                    "Season Average": float(bowl_avg),
                    "Metric": "Bowling average",
                }
            )
    if not rows:
        return
    average_data = pd.DataFrame(rows).sort_values("Season", key=lambda series: series.map(profile_season_sort_key))
    columns = st.columns(2)
    for column, metric, title, color, key in [
        (columns[0], "Batting average", "Batting Average by Season", "#6D4DFF", "profile_chart_batting_average"),
        (columns[1], "Bowling average", "Bowling Average by Season", "#10B981", "profile_chart_bowling_average"),
    ]:
        metric_data = average_data[average_data["Metric"] == metric].copy()
        if metric_data.empty:
            continue
        with column:
            render_filled_average_chart(metric_data, chart_data["Season"].tolist(), title, color, key)


def render_filled_average_chart(data: pd.DataFrame, season_order: list[str], title: str, color: str, key: str) -> None:
    with st.container(key=key):
        st.markdown(f'<div class="profile-chart-title">{html.escape(title)}</div>', unsafe_allow_html=True)
        base = alt.Chart(data).encode(
            x=alt.X("Season:N", sort=season_order, axis=alt.Axis(labelAngle=-35, labelColor="#737998", title=None)),
            y=alt.Y("Season Average:Q", axis=alt.Axis(grid=False, labelColor="#737998", title=None)),
            tooltip=[
                alt.Tooltip("Season:N"),
                alt.Tooltip("Season Average:Q", title="Season avg.", format=".2f"),
            ],
        )
        chart = (
            base.mark_area(color=color, opacity=0.15, interpolate="monotone")
            + base.mark_line(color=color, strokeWidth=3, interpolate="monotone")
            + base.mark_point(color=color, filled=True, size=58)
        ).properties(height=235).configure(background="#FFFFFF").configure_view(fill="#FFFFFF", stroke=None)
        st.altair_chart(chart, use_container_width=True)


def render_player_season_table(season_table: pd.DataFrame) -> None:
    render_section_heading("Season History 📅")
    with st.container(key="player_profile_season_table"):
        batting_tab, bowling_tab, fielding_tab = st.tabs(["Batting", "Bowling", "Fielding"])
        with batting_tab:
            columns = ["Season", "Matches", "Innings", "Runs", "Bat Avg", "Bat SR", "HS", "50s", "100s", "0s", "4s", "6s"]
            render_profile_season_stat_table(season_table, columns, ["Matches", "Innings", "Runs", "50s", "100s"])
        with bowling_tab:
            table = season_table.copy()
            table["Overs"] = table["Balls Bowled"].map(format_balls_as_overs) if "Balls Bowled" in table else "—"
            render_profile_season_stat_table(table.rename(columns={"BBI": "BBI"}), ["Season", "Matches", "Overs", "Maidens", "Wickets", "Bowl Avg", "Bowl SR", "Econ", "BBI", "5WI"], ["Balls Bowled", "Maidens", "Wickets", "5WI"])
        with fielding_tab:
            columns = ["Season", "Matches", "Catches", "Stumpings", "Run Outs", "Dismissals"]
            render_profile_season_stat_table(season_table, columns, ["Catches", "Stumpings", "Run Outs", "Dismissals"])


def render_player_grade_table(grade_table: pd.DataFrame) -> None:
    if grade_table.empty:
        return
    render_section_heading("Grade Breakdown 🧭")
    with st.container(key="player_profile_grade_table"):
        batting_tab, bowling_tab, fielding_tab = st.tabs(["Batting", "Bowling", "Fielding"])
        with batting_tab:
            columns = ["Grade", "Matches", "Innings", "Runs", "Bat Avg", "Bat SR", "HS", "50s", "100s", "0s", "4s", "6s"]
            render_profile_group_stat_table(grade_table, columns, ["Matches", "Innings", "Runs", "50s", "100s"], "Grade")
        with bowling_tab:
            table = grade_table.copy()
            table["Overs"] = table["Balls Bowled"].map(format_balls_as_overs) if "Balls Bowled" in table else "—"
            columns = ["Grade", "Matches", "Overs", "Maidens", "Wickets", "Bowl Avg", "Bowl SR", "Econ", "BBI", "5WI"]
            render_profile_group_stat_table(table, columns, ["Balls Bowled", "Maidens", "Wickets", "5WI"], "Grade")
        with fielding_tab:
            columns = ["Grade", "Matches", "Catches", "Stumpings", "Run Outs", "Dismissals"]
            render_profile_group_stat_table(grade_table, columns, ["Catches", "Stumpings", "Run Outs", "Dismissals"], "Grade")


def render_profile_season_stat_table(season_table: pd.DataFrame, columns: list[str], activity_columns: list[str]) -> None:
    table = select_display_columns(season_table, columns).copy()
    if table.empty:
        st.caption("No data available for this view.")
        return
    activity = pd.Series(False, index=table.index)
    for column in activity_columns:
        if column in table:
            activity = activity | (pd.to_numeric(table[column], errors="coerce").fillna(0) > 0)
    table = table[activity].copy()
    if table.empty:
        st.caption("No data available for this view.")
        return
    table = table.sort_values("Season", key=lambda series: series.map(profile_season_sort_key), ascending=False)
    display = format_profile_table(table)
    table_height = min(390, max(170, 42 * (len(display) + 1)))
    render_filterable_dataframe(
        display,
        key_prefix=f"profile_season_{'_'.join(columns)}",
        use_container_width=True,
        hide_index=True,
        height=table_height,
        column_config=profile_table_column_config(display.columns.tolist(), "Season"),
        show_filters=False,
    )


def profile_table_column_config(columns: list[str], pinned_column: str) -> dict[str, object]:
    config: dict[str, object] = {}
    for column in columns:
        if column == pinned_column:
            config[column] = st.column_config.TextColumn(column, pinned=True, width="medium")
        elif column in {"Player", "Grade"}:
            config[column] = st.column_config.TextColumn(column, width="medium")
        elif column in {"Season", "BBI", "HS", "Overs"}:
            config[column] = st.column_config.TextColumn(column, width="small")
        else:
            config[column] = st.column_config.TextColumn(column, width="small")
    return config


def render_profile_table_totals(table: pd.DataFrame, label_column: str) -> None:
    totals = []
    for column in ["Matches", "Innings", "Runs", "4s", "6s", "Maidens", "Wickets", "Catches", "Stumpings", "Run Outs", "Dismissals"]:
        if column in table:
            value = pd.to_numeric(table[column], errors="coerce").fillna(0).sum()
            if value:
                totals.append(f"{column}: {int(value):,}")
    if totals:
        st.markdown(
            f'<div class="table-total-line">Total across {html.escape(label_column.lower())}: {" · ".join(totals)}</div>',
            unsafe_allow_html=True,
        )


def render_profile_group_stat_table(group_table: pd.DataFrame, columns: list[str], activity_columns: list[str], label_column: str) -> None:
    table = select_display_columns(group_table, columns).copy()
    if table.empty:
        st.caption("No data available for this view.")
        return
    activity = pd.Series(False, index=table.index)
    for column in activity_columns:
        if column in table:
            activity = activity | (pd.to_numeric(table[column], errors="coerce").fillna(0) > 0)
    table = table[activity].copy()
    if table.empty:
        st.caption("No data available for this view.")
        return
    if label_column == "Grade":
        table["_sort_key"] = table[label_column].map(grade_sort_key)
        table = table.sort_values("_sort_key").drop(columns="_sort_key")
    else:
        table = table.sort_values(label_column)
    display = format_profile_table(table)
    table_height = min(390, max(170, 42 * (len(display) + 1)))
    render_filterable_dataframe(
        display,
        key_prefix=f"profile_grade_{'_'.join(columns)}",
        use_container_width=True,
        hide_index=True,
        height=table_height,
        column_config=profile_table_column_config(display.columns.tolist(), label_column),
        show_filters=False,
    )


def append_profile_total_row(
    table: pd.DataFrame,
    source_rows: pd.DataFrame,
    columns: list[str],
    label_column: str,
) -> pd.DataFrame:
    total_row = build_profile_total_row(source_rows, columns, label_column)
    if not total_row:
        return table
    return pd.concat([table, pd.DataFrame([total_row])], ignore_index=True)


def build_profile_total_row(source_rows: pd.DataFrame, columns: list[str], label_column: str) -> dict[str, object]:
    if source_rows.empty:
        return {}
    row: dict[str, object] = {column: pd.NA for column in columns}
    row[label_column] = "Total"

    for column in ["Matches", "Innings", "Runs", "BF", "50s", "100s", "0s", "4s", "6s", "Wickets", "Maidens", "5WI", "Catches", "Stumpings", "Run Outs", "Dismissals"]:
        if column in columns and column in source_rows:
            row[column] = sum_numeric_series(source_rows[column])

    runs = sum_numeric_series(source_rows["Runs"]) if "Runs" in source_rows else 0
    innings = sum_numeric_series(source_rows["Innings"]) if "Innings" in source_rows else 0
    not_outs = sum_numeric_series(source_rows["NO"]) if "NO" in source_rows else 0
    outs = sum_numeric_series(source_rows["Outs"]) if "Outs" in source_rows else max(innings - not_outs, 0)
    balls_faced = sum_numeric_series(source_rows["BF"]) if "BF" in source_rows else 0
    runs_against = sum_numeric_series(source_rows["Runs Against"]) if "Runs Against" in source_rows else 0
    balls_bowled = sum_numeric_series(source_rows["Balls Bowled"]) if "Balls Bowled" in source_rows else 0
    wickets = sum_numeric_series(source_rows["Wickets"]) if "Wickets" in source_rows else 0

    if "Bat Avg" in columns:
        row["Bat Avg"] = divide_or_none(runs, outs)
    if "Bat SR" in columns:
        reliable_rows = source_rows
        if "Season" in reliable_rows:
            reliable_rows = reliable_rows[reliable_rows["Season"].map(profile_season_sort_key) >= profile_season_sort_key("Summer 2024/25")]
            sr_runs = sum_numeric_series(reliable_rows["Runs"]) if "Runs" in reliable_rows else 0
            sr_balls = sum_numeric_series(reliable_rows["BF"]) if "BF" in reliable_rows else 0
            row["Bat SR"] = divide_or_none(sr_runs * 100, sr_balls)
        else:
            row["Bat SR"] = divide_or_none(runs * 100, balls_faced)
    if "HS" in columns and "HS" in source_rows:
        row["HS"] = best_high_score_from_display_values(source_rows["HS"])
    if "Overs" in columns:
        row["Overs"] = format_balls_as_overs(balls_bowled) if balls_bowled else "—"
    if "Bowl Avg" in columns:
        row["Bowl Avg"] = divide_or_none(runs_against, wickets)
    if "Econ" in columns:
        row["Econ"] = divide_or_none(runs_against * 6, balls_bowled)
    if "Bowl SR" in columns:
        row["Bowl SR"] = divide_or_none(balls_bowled, wickets)
    if "BBI" in columns and "BBI" in source_rows:
        row["BBI"] = best_bbi_from_display_values(source_rows["BBI"])
    return row


def best_high_score_from_display_values(values: pd.Series) -> str:
    candidates = []
    for raw in values.dropna().astype(str):
        match = re.search(r"(\d+)\s*(\*)?", raw)
        if not match:
            continue
        candidates.append((int(match.group(1)), bool(match.group(2)), raw.strip()))
    if not candidates:
        return "—"
    score, not_out, _raw = sorted(candidates, key=lambda item: (item[0], item[1]), reverse=True)[0]
    return f"{score}{'*' if not_out else ''}"


def best_bbi_from_display_values(values: pd.Series) -> str:
    candidates = [value for value in values.dropna().astype(str) if re.search(r"\d+\s*[-/]\s*\d+", value)]
    if not candidates:
        return "—"
    return max(candidates, key=bbi_sort_key)


def render_player_breakdown(career: pd.Series) -> None:
    render_section_heading("Career Breakdown 🧩")
    cards = [
        ("Batting", [("Matches", format_int(career.get("Matches"))), ("Runs", format_int(career.get("Runs"))), ("Average", format_decimal(career.get("Bat Avg"))), ("4s", format_int(career.get("4s"))), ("6s", format_int(career.get("6s"))), ("0s", format_int(career.get("0s"))), ("HS", str(career.get("HS", "—")))]),
        ("Bowling", [("Wickets", format_int(career.get("Wickets"))), ("Overs", str(career.get("Overs", "—"))), ("Maidens", format_int(career.get("Maidens"))), ("Average", format_decimal(career.get("Bowl Avg"))), ("Strike Rate", format_decimal(career.get("Bowl SR"))), ("Economy", format_decimal(career.get("Econ"))), ("BBI", str(career.get("BBI", "—")))]),
        ("Fielding", [("Catches", format_int(career.get("Catches"))), ("Stumpings", format_int(career.get("Stumpings"))), ("Run Outs", format_int(career.get("Run Outs"))), ("Dismissals", format_int(career.get("Dismissals")))]),
    ]
    columns = st.columns(3)
    for column, (title, metrics) in zip(columns, cards):
        with column:
            metric_html = "".join(f'<div><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>' for label, value in metrics)
            st.markdown(f'<div class="profile-breakdown-card"><h4>{html.escape(title)}</h4>{metric_html}</div>', unsafe_allow_html=True)


def render_player_milestones(career: pd.Series) -> None:
    milestones = player_milestone_rows(career)
    if not milestones:
        return
    render_section_heading("Milestone Watch 🎯")
    rows = []
    for milestone in milestones:
        rows.append(
            '<div class="milestone-watch-row">'
            '<div class="milestone-watch-top">'
            f'<div><strong>{html.escape(milestone["category"])}</strong><span>{milestone["current"]:,} / {milestone["target"]:,} {html.escape(milestone["unit"])}</span></div>'
            f'<div class="milestone-away">{milestone["remaining"]:,} {html.escape(milestone["unit"])} away</div>'
            "</div>"
            f'<div class="progress-track"><div style="width:{milestone["progress"]:.1f}%"></div></div>'
            "</div>"
        )
    st.markdown(f'<div class="milestone-watch-card">{"".join(rows)}</div>', unsafe_allow_html=True)


def render_player_alias_audit(raw_profiles: pd.DataFrame) -> None:
    with st.expander("Merged PlayCricket Profiles", expanded=False):
        if raw_profiles.empty:
            st.caption("No raw PlayCricket profile data is available for this player.")
            return
        if len(raw_profiles) == 1:
            st.caption("Single PlayCricket profile used for this player.")
        else:
            st.caption(f"Career totals include {len(raw_profiles)} merged PlayCricket profiles.")
        st.dataframe(format_profile_table(raw_profiles), use_container_width=True, hide_index=True)


def build_player_raw_profile_table(
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
) -> pd.DataFrame:
    raw_ids = sorted(
        set().union(
            set(batting.get("raw_player_id", pd.Series(dtype=str)).dropna().astype(str)),
            set(bowling.get("raw_player_id", pd.Series(dtype=str)).dropna().astype(str)),
            set(fielding.get("raw_player_id", pd.Series(dtype=str)).dropna().astype(str)),
        )
    )
    rows = []
    for raw_id in raw_ids:
        bat = batting[batting["raw_player_id"].astype(str) == raw_id] if "raw_player_id" in batting else batting.head(0)
        bowl = bowling[bowling["raw_player_id"].astype(str) == raw_id] if "raw_player_id" in bowling else bowling.head(0)
        field = fielding[fielding["raw_player_id"].astype(str) == raw_id] if "raw_player_id" in fielding else fielding.head(0)
        name = first_non_empty_label([bat, bowl, field], "raw_player_name")
        rows.append(
            {
                "Raw Player ID": raw_id or "—",
                "Raw Player Name": name or "—",
                "Seasons": player_seasons([bat, bowl, field]),
                "Teams": player_teams([bat, bowl, field]),
                "Matches": player_match_total([bat, bowl, field]),
                "Runs": sum_column(bat, "battingAggregate"),
                "Wickets": sum_column(bowl, "bowlingWickets"),
                "Catches": sum_column(field, "fieldingTotalCatches"),
            }
        )
    return pd.DataFrame(rows)


def player_milestone_rows(career: pd.Series) -> list[dict[str, object]]:
    specs = [
        ("Matches", "Matches", 100, "matches"),
        ("Runs", "Runs", 1000, "runs"),
        ("Wickets", "Wickets", 100, "wickets"),
        ("Catches", "Catches", 50, "catches"),
    ]
    rows = []
    for category, column, step, unit in specs:
        current = int(numeric_value(career, column))
        if current <= 0:
            continue
        target = next_milestone_target(current, step)
        remaining = target - current
        rows.append({"category": category, "current": current, "target": target, "remaining": remaining, "unit": unit, "progress": current / target * 100})
    return rows


def player_teams_grades(frames: list[pd.DataFrame]) -> str:
    labels = []
    for frame in frames:
        if frame.empty:
            continue
        for _, row in frame.iterrows():
            label = row.get("team_grade_display") or build_team_grade_display(row.get("team_name", ""), row.get("grade_name", ""))
            if label and label not in labels:
                labels.append(label)
    labels = sorted(labels, key=grade_sort_key)
    return ", ".join(labels) if labels else "—"


def player_profile_team_summary(season_table: pd.DataFrame, max_seasons: int = 5) -> str:
    if season_table.empty or "Season" not in season_table:
        return "—"
    rows = season_table.copy()
    rows = rows.sort_values("Season", key=lambda series: series.map(profile_season_sort_key), ascending=False)
    parts = []
    for _, row in rows.head(max_seasons).iterrows():
        season = clean_profile_season_label(row.get("Season", ""))
        teams = clean_profile_team_grade_text(row.get("Teams", ""))
        grades = clean_profile_team_grade_text(row.get("Grades", ""))
        detail_parts = []
        if teams and teams != "—":
            detail_parts.append(f"Teams: {teams}")
        if grades and grades != "—":
            detail_parts.append(f"Grades: {grades}")
        if season and detail_parts:
            parts.append(f"{season}: {' · '.join(detail_parts)}")
    remaining = max(0, rows["Season"].dropna().astype(str).nunique() - len(parts))
    if remaining:
        parts.append(f"+ {remaining} more season{'s' if remaining != 1 else ''}")
    return "  •  ".join(parts) if parts else "—"


def clean_profile_season_label(value: object) -> str:
    return str(value or "").strip().replace("Summer ", "")


def clean_profile_grade_from_row(row: pd.Series) -> str:
    grade = row.get("canonical_grade_label") or canonical_grade_label(row.get("team_name", ""), row.get("grade_name", ""))
    team = row.get("canonical_team_label") or clean_team_name(row.get("team_name", ""))
    return grade or team or "Unknown grade"


def clean_profile_team_grade_text(value: object) -> str:
    raw = str(value or "").strip()
    if not raw or raw == "—":
        return "—"
    labels = []
    for item in raw.split(","):
        label = item.strip()
        if not label:
            continue
        parsed = pd.Series([label]).str.extract(r"^(.*?)\s*\((.*?)\)$").iloc[0]
        team = str(parsed[0]).strip() if pd.notna(parsed[0]) else label
        grade = str(parsed[1]).strip() if pd.notna(parsed[1]) else ""
        team = clean_profile_team_label(team)
        grade = clean_profile_grade_label(grade)
        if team and grade:
            team_compare = team.replace('"', "").replace("'", "").casefold()
            grade_compare = grade.replace('"', "").replace("'", "").casefold()
            if grade_compare in team_compare or team_compare in grade_compare:
                label = team if len(team) >= len(grade) else grade
            else:
                label = f"{team} - {grade}"
        else:
            label = team or grade
        label = label.replace('"', "").replace("'", "")
        if label and label not in labels:
            labels.append(label)
    return " · ".join(labels) if labels else "—"


def clean_profile_team_label(value: object) -> str:
    return clean_team_name(value).replace("Fiji Vics", "").strip()


def clean_profile_grade_label(value: object) -> str:
    return clean_grade_name(value).replace("Designated One Day Comp.", "DODC")


def player_teams(frames: list[pd.DataFrame]) -> str:
    labels = []
    for frame in frames:
        if not frame.empty:
            for _, row in frame.iterrows():
                label = row.get("canonical_team_label") or clean_profile_team_label(row.get("team_name", ""))
                if label and label not in labels:
                    labels.append(label)
    return ", ".join(labels) if labels else "—"


def player_grades(frames: list[pd.DataFrame]) -> str:
    labels = []
    for frame in frames:
        if not frame.empty:
            for _, row in frame.iterrows():
                label = row.get("canonical_grade_label") or clean_profile_grade_from_row(row)
                if label and label not in labels:
                    labels.append(label)
    labels = sorted(labels, key=grade_sort_key)
    return ", ".join(labels) if labels else "—"


def player_unique_grades(frames: list[pd.DataFrame], limit: int = 5) -> str:
    labels = []
    for frame in frames:
        if frame.empty:
            continue
        for _, row in frame.iterrows():
            label = clean_profile_grade_from_row(row)
            label = clean_profile_grade_label(label)
            if label and label != "Unknown grade" and label not in labels:
                labels.append(label)
    labels = sorted(labels, key=grade_sort_key)
    if not labels:
        return "—"
    visible = labels[:limit]
    remaining = len(labels) - len(visible)
    if remaining > 0:
        visible.append(f"+ {remaining} more")
    return " · ".join(visible)


def player_seasons(frames: list[pd.DataFrame]) -> str:
    seasons = []
    for frame in frames:
        if not frame.empty and "season" in frame:
            for value in frame["season"].dropna().astype(str):
                if value and value not in seasons:
                    seasons.append(value)
    return ", ".join(sorted(seasons, key=profile_season_sort_key)) if seasons else "—"


def player_match_total(frames: list[pd.DataFrame]) -> int:
    rows = []
    for frame in frames:
        if frame.empty or "matches" not in frame:
            continue
        group_cols = [column for column in ["season", "team_id"] if column in frame]
        output = frame.copy()
        output["matches"] = pd.to_numeric(output["matches"], errors="coerce").fillna(0)
        if group_cols:
            rows.append(output.groupby(group_cols, dropna=False, as_index=False)["matches"].max())
        else:
            rows.append(pd.DataFrame({"matches": [output["matches"].max()]}))
    if not rows:
        return 0
    combined = pd.concat(rows, ignore_index=True)
    group_cols = [column for column in ["season", "team_id"] if column in combined]
    if group_cols:
        return int(combined.groupby(group_cols, dropna=False)["matches"].max().sum())
    return int(combined["matches"].max())


def first_non_empty_label(frames: list[pd.DataFrame], column: str) -> str:
    for frame in frames:
        if not frame.empty and column in frame:
            values = frame[column].dropna().astype(str)
            values = values[values.str.strip() != ""]
            if not values.empty:
                return values.iloc[0]
    return ""


def sum_column(df: pd.DataFrame, column: str) -> float:
    if df.empty or column not in df:
        return 0.0
    return float(pd.to_numeric(df[column], errors="coerce").fillna(0).sum())


def sum_numeric_series(series: pd.Series) -> float:
    return float(pd.to_numeric(series, errors="coerce").fillna(0).sum())


def divide_or_none(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return numerator / denominator


def best_high_score(df: pd.DataFrame) -> str:
    row = best_high_score_row(df)
    if row.empty:
        return "—"
    return format_high_score_value(row)


def best_high_score_row(df: pd.DataFrame) -> pd.Series:
    if df.empty or "battingHighScore" not in df:
        return pd.Series(dtype="object")
    output = df.copy()
    output["_score_sort"] = pd.to_numeric(output["battingHighScore"], errors="coerce")
    if not output["_score_sort"].notna().any():
        return pd.Series(dtype="object")
    output["_not_out_sort"] = output["isBattingHSNotOut"].map(as_bool) if "isBattingHSNotOut" in output else False
    output = output.sort_values(["_score_sort", "_not_out_sort"], ascending=[False, False])
    return df.loc[output.index[0]]


def best_bowling_value(df: pd.DataFrame) -> str:
    row = best_bowling_row(df)
    if row.empty:
        return "—"
    return str(row.get("bowlingBestInnings", "—"))


def best_bowling_row(df: pd.DataFrame) -> pd.Series:
    if df.empty or "bowlingBestInnings" not in df:
        return pd.Series(dtype="object")
    output = df.dropna(subset=["bowlingBestInnings"]).copy()
    parsed = output["bowlingBestInnings"].astype(str).str.extract(r"(\d+)\s*[-/]\s*(\d+)")
    output["_bbi_wickets"] = pd.to_numeric(parsed[0], errors="coerce").fillna(0)
    output = output[output["_bbi_wickets"] > 0].drop(columns=["_bbi_wickets"])
    sorted_df = sort_bowling_by_bbi(output)
    return sorted_df.iloc[0] if not sorted_df.empty else pd.Series(dtype="object")


def profile_record_meta(row: pd.Series) -> str:
    if row.empty:
        return ""
    parts = []
    season = row.get("season")
    if pd.notna(season):
        parts.append(str(season))
    display = row.get("team_grade_display") or build_team_grade_display(row.get("team_name", ""), row.get("grade_name", ""))
    if display and display != "—":
        parts.append(str(display))
    return " · ".join(parts)


def career_span_label(seasons: list[str]) -> str:
    if not seasons:
        return "—"
    ordered = sorted(seasons, key=profile_season_sort_key)
    return f"{ordered[0]} – {ordered[-1]}" if len(ordered) > 1 else ordered[0]


def profile_season_sort_key(value: object) -> int:
    label = str(value or "")
    years = [int(year) for year in pd.Series([label]).str.findall(r"20\d{2}").iloc[0]]
    if not years:
        return 0
    if "Summer" in label and len(years) >= 2:
        return years[-1] * 10 + 2
    if "Summer" in label:
        return years[0] * 10 + 2
    if "Winter" in label:
        return years[0] * 10 + 1
    return years[-1] * 10


def reliable_batting_strike_rate(batting: pd.DataFrame) -> float | None:
    # PlayCricket balls-faced data is only reliable enough for Bat SR from Summer 2024/25 onward.
    if batting.empty or "season" not in batting:
        return None
    reliable = batting[batting["season"].map(profile_season_sort_key) >= profile_season_sort_key("Summer 2024/25")].copy()
    if reliable.empty:
        return None
    runs = sum_column(reliable, "battingAggregate")
    balls = sum_column(reliable, "battingBallsFaced")
    return divide_or_none(runs * 100, balls)


def season_sort_key(value: object) -> int:
    match = pd.Series([str(value)]).str.extract(r"(20\d{2})").iloc[0, 0]
    year = pd.to_numeric(match, errors="coerce")
    return int(year) if pd.notna(year) else 0


def format_int(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    return "—" if pd.isna(number) else f"{int(number):,}"


def format_decimal(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    return "—" if pd.isna(number) else f"{float(number):.2f}"


def format_profile_table(table: pd.DataFrame) -> pd.DataFrame:
    output = table.copy()
    decimal_columns = {"Bat Avg", "Bat SR", "Bowl Avg", "Econ", "Bowl SR"}
    integer_columns = {"Matches", "Innings", "Runs", "50s", "100s", "0s", "4s", "6s", "Wickets", "Maidens", "5WI", "Catches", "Stumpings", "Run Outs", "Dismissals"}
    for column in output.columns:
        if column in decimal_columns:
            output[column] = pd.to_numeric(output[column], errors="coerce").map(lambda value: "—" if pd.isna(value) else f"{float(value):.2f}")
        elif column in integer_columns:
            output[column] = pd.to_numeric(output[column], errors="coerce").map(lambda value: "—" if pd.isna(value) else f"{int(value):,}")
        else:
            output[column] = output[column].map(lambda value: "—" if pd.isna(value) or str(value).strip() == "" else value)
    return output


def render_player_merge_audit_page() -> None:
    historical_data = load_hall_of_fame_data(metadata_mtime(), player_aliases_mtime())
    if historical_data is None:
        st.info("Historical data is not available yet. Refresh local backup to build the player merge audit.")
        return

    audit_data = build_player_merge_audit_data(historical_data)
    summary = audit_data["summary"]
    detail = audit_data["detail"]
    after = audit_data["after"]
    suggestions = audit_data["suggestions"]

    st.markdown(
        """
        <div class="page-kicker">Admin audit</div>
        <div class="club-label">Fiji Victorian Cricket Club</div>
        <h1 class="page-title">Player Merge Audit</h1>
        <div class="page-subtitle">Review merged player profiles before trusting all-time records.</div>
        """,
        unsafe_allow_html=True,
    )
    render_identity_info_note()
    render_merge_audit_kpis(summary, detail, suggestions)
    filtered = render_merge_audit_filters(summary)
    render_merge_audit_exports(filtered, detail, after, suggestions)

    render_section_heading("Merged Player Profiles")
    if filtered.empty:
        st.info(
            "No active aliases currently merge multiple raw profiles. Add confirmed mappings to data/player_aliases.csv, then refresh the page."
        )
    else:
        render_merge_summary_table(filtered)
        render_merge_detail_sections(filtered, detail, after)

    render_validation_reference()
    render_possible_duplicate_suggestions(suggestions)


def build_player_merge_audit_data(data: dict[str, object]) -> dict[str, pd.DataFrame]:
    batting = data.get("batting_raw", pd.DataFrame())
    bowling = data.get("bowling_raw", pd.DataFrame())
    fielding = data.get("fielding_raw", pd.DataFrame())
    validation = load_player_merge_validation()
    suggestions = read_duplicate_suggestions()

    detail = build_raw_profile_breakdown(batting, bowling, fielding)
    after = build_canonical_totals(detail)
    summary = build_merge_summary(detail, after, validation)
    return {
        "summary": summary,
        "detail": detail,
        "after": after,
        "suggestions": suggestions,
    }


def read_duplicate_suggestions() -> pd.DataFrame:
    if DUPLICATE_AUDIT_PATH.exists():
        return pd.read_csv(DUPLICATE_AUDIT_PATH, dtype=str).fillna("")
    return pd.DataFrame()


def build_raw_profile_breakdown(
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
) -> pd.DataFrame:
    keys = ["canonical_player_id", "canonical_player_name", "raw_profile_key", "raw_player_id", "raw_player_name"]
    batting_summary = profile_category_summary(batting, "batting")
    bowling_summary = profile_category_summary(bowling, "bowling")
    fielding_summary = profile_category_summary(fielding, "fielding")
    summaries = [frame for frame in [batting_summary, bowling_summary, fielding_summary] if not frame.empty]
    if not summaries:
        return pd.DataFrame(columns=raw_breakdown_columns())

    detail = summaries[0]
    for frame in summaries[1:]:
        detail = detail.merge(frame, on=keys, how="outer")

    for column in raw_numeric_columns():
        if column not in detail:
            detail[column] = 0
        detail[column] = pd.to_numeric(detail[column], errors="coerce").fillna(0)

    for column in ["teams", "seasons"]:
        value_columns = [column for column in detail.columns if column.startswith(f"{column}_")]
        detail[column] = detail[value_columns].apply(join_unique_row_values, axis=1) if value_columns else ""

    # PlayCricket season stat tables do not expose reliable per-player match IDs.
    # Use the largest category match total per raw profile to avoid triple-counting
    # the same match from batting, bowling and fielding tables.
    match_columns = [column for column in ["matches_batting", "matches_bowling", "matches_fielding"] if column in detail]
    detail["matches"] = detail[match_columns].max(axis=1) if match_columns else 0
    calculate_derived_audit_stats(detail)
    detail["merge_source"] = detail.apply(merge_source_for_raw_profile, axis=1)
    return detail[raw_breakdown_columns()]


def raw_breakdown_columns() -> list[str]:
    return [
        "canonical_player_id",
        "canonical_player_name",
        "raw_profile_key",
        "raw_player_id",
        "raw_player_name",
        "merge_source",
        "teams",
        "seasons",
        "matches",
        "innings",
        "runs",
        "balls_faced",
        "outs",
        "batting_average",
        "batting_strike_rate",
        "overs",
        "balls_bowled",
        "wickets",
        "runs_conceded",
        "bowling_average",
        "economy",
        "bowling_strike_rate",
        "catches",
        "stumpings",
        "run_outs",
        "dismissals",
    ]


def raw_numeric_columns() -> list[str]:
    return [
        "matches_batting",
        "matches_bowling",
        "matches_fielding",
        "innings",
        "runs",
        "balls_faced",
        "not_outs",
        "balls_bowled",
        "wickets",
        "runs_conceded",
        "catches",
        "stumpings",
        "run_outs",
    ]


def merge_source_for_raw_profile(row: pd.Series) -> str:
    aliases = active_aliases(load_player_aliases())
    if aliases.empty:
        return ""
    raw_id = str(row.get("raw_player_id", "")).strip()
    raw_name = str(row.get("raw_player_name", "")).strip()
    candidates = aliases.copy()
    if raw_id:
        matched = candidates[candidates["raw_player_id"].fillna("").astype(str).str.strip() == raw_id]
    else:
        matched = candidates.head(0)
    if matched.empty and raw_name:
        matched = candidates[candidates["raw_player_name"].fillna("").astype(str).str.strip() == raw_name]
    if matched.empty:
        return ""
    source = matched["merge_source"].dropna().astype(str)
    source = source[source.str.strip() != ""]
    return source.iloc[0] if not source.empty else "existing_alias"


def profile_category_summary(df: pd.DataFrame, category: str) -> pd.DataFrame:
    keys = ["canonical_player_id", "canonical_player_name", "raw_profile_key", "raw_player_id", "raw_player_name"]
    if df.empty or "raw_player_name" not in df:
        return pd.DataFrame(columns=keys)

    output = df.copy()
    for column in ["canonical_player_id", "canonical_player_name", "raw_player_id", "raw_player_name"]:
        if column not in output:
            output[column] = ""
    output["raw_profile_key"] = output["raw_player_id"].fillna("").astype(str).str.strip()
    output["raw_profile_key"] = output["raw_profile_key"].where(
        output["raw_profile_key"] != "",
        output["raw_player_name"].map(make_player_slug),
    )

    grouped = output.groupby(keys, dropna=False, as_index=False).agg(
        teams=(("team_name" if "team_name" in output else "raw_player_name"), join_unique_csv),
        seasons=(("season" if "season" in output else "raw_player_name"), join_unique_csv),
        matches=("matches", sum_numeric_column) if "matches" in output else ("raw_player_name", count_rows_as_zero),
    )
    grouped = grouped.rename(columns={"teams": f"teams_{category}", "seasons": f"seasons_{category}", "matches": f"matches_{category}"})

    if category == "batting":
        grouped = grouped.merge(
            aggregate_numeric(output, keys, {
                "innings": "battingInnings",
                "runs": "battingAggregate",
                "balls_faced": "battingBallsFaced",
                "not_outs": "battingNotOuts",
            }),
            on=keys,
            how="left",
        )
    elif category == "bowling":
        grouped = grouped.merge(
            aggregate_numeric(output, keys, {
                "wickets": "bowlingWickets",
                "runs_conceded": "bowlingRuns",
                "balls_bowled": "bowlingBalls",
            }),
            on=keys,
            how="left",
        )
    elif category == "fielding":
        grouped = grouped.merge(
            aggregate_numeric(output, keys, {
                "catches": "fieldingTotalCatches",
                "stumpings": "fieldingStumpings",
                "run_outs": "fieldingRunOuts",
            }),
            on=keys,
            how="left",
        )

    return grouped


def aggregate_numeric(df: pd.DataFrame, keys: list[str], columns: dict[str, str]) -> pd.DataFrame:
    output = df.copy()
    agg = {}
    for display_column, source_column in columns.items():
        if source_column not in output:
            output[source_column] = 0
        output[source_column] = pd.to_numeric(output[source_column], errors="coerce").fillna(0)
        agg[display_column] = (source_column, "sum")
    return output.groupby(keys, dropna=False, as_index=False).agg(**agg)


def sum_numeric_column(values: pd.Series) -> float:
    return float(pd.to_numeric(values, errors="coerce").fillna(0).sum())


def count_rows_as_zero(values: pd.Series) -> int:
    return 0


def join_unique_row_values(row: pd.Series) -> str:
    return join_unique_csv(pd.Series(row.dropna().astype(str).tolist()))


def calculate_derived_audit_stats(df: pd.DataFrame) -> None:
    df["outs"] = (df["innings"] - df["not_outs"]).clip(lower=0)
    df["batting_average"] = safe_divide(df["runs"], df["outs"])
    df["batting_strike_rate"] = safe_divide(df["runs"] * 100, df["balls_faced"])
    df["overs"] = df["balls_bowled"].map(format_balls_as_overs)
    df["bowling_average"] = safe_divide(df["runs_conceded"], df["wickets"])
    df["economy"] = safe_divide(df["runs_conceded"] * 6, df["balls_bowled"])
    df["bowling_strike_rate"] = safe_divide(df["balls_bowled"], df["wickets"])
    df["dismissals"] = df["catches"] + df["stumpings"] + df["run_outs"]


def safe_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    numerator = pd.to_numeric(numerator, errors="coerce")
    denominator = pd.to_numeric(denominator, errors="coerce")
    result = numerator / denominator.replace(0, pd.NA)
    return result.replace([float("inf"), float("-inf")], pd.NA)


def build_canonical_totals(detail: pd.DataFrame) -> pd.DataFrame:
    if detail.empty:
        return pd.DataFrame(columns=canonical_total_columns())

    numeric_columns = [
        "matches",
        "innings",
        "runs",
        "balls_faced",
        "outs",
        "balls_bowled",
        "wickets",
        "runs_conceded",
        "catches",
        "stumpings",
        "run_outs",
        "dismissals",
    ]
    output = detail.copy()
    for column in numeric_columns:
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)
    grouped = output.groupby(["canonical_player_id", "canonical_player_name"], as_index=False).agg(
        total_matches=("matches", "sum"),
        total_innings=("innings", "sum"),
        total_runs=("runs", "sum"),
        total_balls_faced=("balls_faced", "sum"),
        total_outs=("outs", "sum"),
        total_balls_bowled=("balls_bowled", "sum"),
        total_wickets=("wickets", "sum"),
        total_runs_conceded=("runs_conceded", "sum"),
        total_catches=("catches", "sum"),
        total_stumpings=("stumpings", "sum"),
        total_run_outs=("run_outs", "sum"),
        total_dismissals=("dismissals", "sum"),
    )
    grouped["total_overs"] = grouped["total_balls_bowled"].map(format_balls_as_overs)
    grouped["recalculated_batting_average"] = safe_divide(grouped["total_runs"], grouped["total_outs"])
    grouped["recalculated_batting_strike_rate"] = safe_divide(grouped["total_runs"] * 100, grouped["total_balls_faced"])
    grouped["recalculated_bowling_average"] = safe_divide(grouped["total_runs_conceded"], grouped["total_wickets"])
    grouped["recalculated_economy"] = safe_divide(grouped["total_runs_conceded"] * 6, grouped["total_balls_bowled"])
    grouped["recalculated_bowling_strike_rate"] = safe_divide(grouped["total_balls_bowled"], grouped["total_wickets"])
    return grouped[canonical_total_columns()]


def canonical_total_columns() -> list[str]:
    return [
        "canonical_player_id",
        "canonical_player_name",
        "total_matches",
        "total_innings",
        "total_runs",
        "total_balls_faced",
        "total_outs",
        "recalculated_batting_average",
        "recalculated_batting_strike_rate",
        "total_overs",
        "total_balls_bowled",
        "total_wickets",
        "total_runs_conceded",
        "recalculated_bowling_average",
        "recalculated_economy",
        "recalculated_bowling_strike_rate",
        "total_catches",
        "total_stumpings",
        "total_run_outs",
        "total_dismissals",
    ]


def build_merge_summary(detail: pd.DataFrame, after: pd.DataFrame, validation: pd.DataFrame) -> pd.DataFrame:
    columns = merge_summary_columns()
    if detail.empty or after.empty:
        return pd.DataFrame(columns=columns)

    summary = detail.groupby(["canonical_player_id", "canonical_player_name"], as_index=False).agg(
        number_of_raw_profiles=("raw_profile_key", "nunique"),
        raw_profile_names=("raw_player_name", join_unique_csv),
        raw_player_ids=("raw_player_id", join_unique_csv),
        merge_source=("merge_source", join_unique_csv),
        teams_represented=("teams", join_unique_csv),
        seasons_represented=("seasons", join_unique_csv),
    )
    summary = summary[summary["number_of_raw_profiles"] >= 2]
    summary = summary.merge(
        after[
            [
                "canonical_player_id",
                "total_matches",
                "total_runs",
                "total_wickets",
                "total_catches",
            ]
        ],
        on="canonical_player_id",
        how="left",
    )
    validation = validation.copy()
    if validation.empty:
        validation = pd.DataFrame(columns=VALIDATION_COLUMNS)
    summary = summary.merge(
        validation[["canonical_player_id", "validation_status", "notes"]],
        on="canonical_player_id",
        how="left",
    )
    summary["validation_status"] = summary["validation_status"].fillna("Needs review").replace("", "Needs review")
    summary["notes"] = summary["notes"].fillna("")
    return summary.rename(
        columns={
            "canonical_player_name": "Canonical Player",
            "number_of_raw_profiles": "Number of Raw Profiles",
            "raw_profile_names": "Raw Profile Names",
            "raw_player_ids": "Raw Player IDs",
            "merge_source": "Merge Source",
            "teams_represented": "Teams Represented",
            "seasons_represented": "Seasons Represented",
            "total_matches": "Total Matches After Merge",
            "total_runs": "Total Runs After Merge",
            "total_wickets": "Total Wickets After Merge",
            "total_catches": "Total Catches After Merge",
            "validation_status": "Validation Status",
            "notes": "Notes",
        }
    )[columns]


def merge_summary_columns() -> list[str]:
    return [
        "canonical_player_id",
        "Canonical Player",
        "Number of Raw Profiles",
        "Raw Profile Names",
        "Raw Player IDs",
        "Merge Source",
        "Teams Represented",
        "Seasons Represented",
        "Total Matches After Merge",
        "Total Runs After Merge",
        "Total Wickets After Merge",
        "Total Catches After Merge",
        "Validation Status",
        "Notes",
    ]


def render_merge_audit_kpis(summary: pd.DataFrame, detail: pd.DataFrame, suggestions: pd.DataFrame) -> None:
    mapped_profiles = int(pd.to_numeric(summary.get("Number of Raw Profiles"), errors="coerce").fillna(0).sum()) if not summary.empty else 0
    unmapped = count_unmapped_profiles(detail)
    cards = [
        ("Merged Players", f"{len(summary):,}", "", "players", "♙", "purple"),
        ("Raw Profiles Merged", f"{mapped_profiles:,}", "", "profiles", "▦", "blue"),
        ("Unmapped Raw Profiles", f"{unmapped:,}", "", "profiles", "▣", "purple"),
        ("Possible Duplicates", f"{len(suggestions):,}", "", "duplicates", "⚑", "green"),
    ]
    columns = st.columns(4)
    for column, card in zip(columns, cards):
        with column:
            render_kpi_card(*card)
    st.markdown("<div class='dashboard-spacer'></div>", unsafe_allow_html=True)


def count_unmapped_profiles(detail: pd.DataFrame) -> int:
    if detail.empty:
        return 0
    aliases = active_aliases(load_player_aliases())
    mapped_ids = set(aliases["raw_player_id"].dropna().astype(str).str.strip()) if not aliases.empty else set()
    mapped_names = set(aliases["raw_player_name"].dropna().astype(str).str.strip()) if not aliases.empty else set()
    profiles = detail[["raw_player_id", "raw_player_name"]].drop_duplicates()
    if not mapped_ids and not mapped_names:
        return len(profiles)
    mask = profiles["raw_player_id"].astype(str).str.strip().isin(mapped_ids) | profiles["raw_player_name"].astype(str).str.strip().isin(mapped_names)
    return int((~mask).sum())


def render_merge_audit_filters(summary: pd.DataFrame) -> pd.DataFrame:
    if summary.empty:
        return summary
    with st.container(key="merge_audit_filters"):
        player_col, status_col, min_col, search_col = st.columns([1.2, 0.9, 0.55, 1.1])
        with player_col:
            player_options = ["All", *summary["Canonical Player"].dropna().astype(str).sort_values().tolist()]
            selected_player = st.selectbox("Canonical player", player_options, key="merge_canonical_filter")
        with status_col:
            status_options = ["All", "Needs review", "Confirmed", "Incorrect merge", "Ignore for now"]
            selected_status = st.selectbox("Validation status", status_options, key="merge_status_filter")
        with min_col:
            min_profiles = st.number_input("Min profiles", min_value=2, max_value=20, value=2, step=1)
        with search_col:
            search = st.text_input("Search names", placeholder="Raw or canonical name")

        season_options = sorted(split_unique_values(summary["Seasons Represented"]))
        team_options = sorted(split_unique_values(summary["Teams Represented"]))
        season_col, team_col = st.columns(2)
        with season_col:
            seasons = st.multiselect("Season", season_options, key="merge_season_filter")
        with team_col:
            teams = st.multiselect("Team", team_options, key="merge_team_filter")

    filtered = summary.copy()
    if selected_player != "All":
        filtered = filtered[filtered["Canonical Player"] == selected_player]
    if selected_status != "All":
        filtered = filtered[filtered["Validation Status"] == selected_status]
    filtered = filtered[pd.to_numeric(filtered["Number of Raw Profiles"], errors="coerce").fillna(0) >= min_profiles]
    if search:
        needle = search.strip().casefold()
        text = (
            filtered["Canonical Player"].astype(str)
            + " "
            + filtered["Raw Profile Names"].astype(str)
            + " "
            + filtered["Raw Player IDs"].astype(str)
        ).str.casefold()
        filtered = filtered[text.str.contains(needle, na=False)]
    for selected, column in [(seasons, "Seasons Represented"), (teams, "Teams Represented")]:
        if selected:
            filtered = filtered[filtered[column].map(lambda value: any(item in str(value) for item in selected))]
    return filtered


def split_unique_values(values: pd.Series) -> set[str]:
    labels: set[str] = set()
    for value in values.dropna().astype(str):
        for part in value.split(","):
            label = part.strip()
            if label:
                labels.add(label)
    return labels


def render_merge_audit_exports(
    summary: pd.DataFrame,
    detail: pd.DataFrame,
    after: pd.DataFrame,
    suggestions: pd.DataFrame,
) -> None:
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    detail_export = build_before_after_export(detail, after)
    export_col_1, export_col_2, export_col_3 = st.columns(3)
    with export_col_1:
        if st.button("Export merge audit summary", use_container_width=True):
            summary.to_csv(EXPORTS_DIR / "player_merge_audit.csv", index=False)
            st.success("Saved exports/player_merge_audit.csv")
    with export_col_2:
        if st.button("Export before/after detail", use_container_width=True):
            detail_export.to_csv(EXPORTS_DIR / "player_merge_audit_detail.csv", index=False)
            st.success("Saved exports/player_merge_audit_detail.csv")
    with export_col_3:
        if st.button("Export duplicate suggestions", use_container_width=True):
            suggestions.to_csv(DUPLICATE_AUDIT_PATH, index=False)
            st.success("Saved data/player_duplicate_audit.csv")


def build_before_after_export(detail: pd.DataFrame, after: pd.DataFrame) -> pd.DataFrame:
    before = detail.copy()
    before.insert(0, "view", "Before Merge - Raw Profile")
    merged = after.copy()
    merged.insert(0, "view", "After Merge - Canonical Total")
    return pd.concat([before, merged], ignore_index=True, sort=False)


def render_merge_summary_table(summary: pd.DataFrame) -> None:
    display = summary.drop(columns=["canonical_player_id"], errors="ignore")
    for column in ["Number of Raw Profiles", "Total Matches After Merge", "Total Runs After Merge", "Total Wickets After Merge", "Total Catches After Merge"]:
        if column in display:
            display[column] = pd.to_numeric(display[column], errors="coerce")
    with st.container(key="merge_summary_card"):
        st.dataframe(display, use_container_width=True, hide_index=True, height=420)


def render_merge_detail_sections(summary: pd.DataFrame, detail: pd.DataFrame, after: pd.DataFrame) -> None:
    render_section_heading("Before / After Merge Detail")
    for _, row in summary.iterrows():
        canonical_id = row["canonical_player_id"]
        player_detail = detail[detail["canonical_player_id"] == canonical_id].copy()
        player_after = after[after["canonical_player_id"] == canonical_id].copy()
        with st.expander(f'{row["Canonical Player"]} · {int(row["Number of Raw Profiles"])} raw profiles', expanded=False):
            render_sanity_chips(player_detail, str(row.get("Validation Status", "Needs review")))
            st.markdown("**Before Merge — Raw Profile Breakdown**")
            st.dataframe(format_audit_table(player_detail.drop(columns=["canonical_player_id"], errors="ignore")), use_container_width=True, hide_index=True)
            st.markdown("**After Merge — Canonical Total**")
            st.dataframe(format_audit_table(player_after), use_container_width=True, hide_index=True)


def render_sanity_chips(detail: pd.DataFrame, status: str) -> None:
    chips = sanity_check_chips(detail, status)
    chip_html = "".join(f'<span class="audit-chip">{html.escape(chip)}</span>' for chip in chips)
    st.markdown(f'<div class="audit-chip-row">{chip_html}</div>', unsafe_allow_html=True)


def sanity_check_chips(detail: pd.DataFrame, status: str) -> list[str]:
    chips = []
    if status != "Confirmed":
        chips.append("Needs review")
    if detail["raw_player_id"].fillna("").astype(str).str.strip().eq("").any():
        chips.append("Missing raw ID")
    if detail["raw_player_id"].fillna("").astype(str).str.strip().duplicated().any():
        chips.append("Duplicate raw ID")
    seasons = []
    for value in detail["seasons"].dropna().astype(str):
        seasons.extend([part.strip() for part in value.split(",") if part.strip()])
    if len(seasons) != len(set(seasons)):
        chips.append("Overlapping seasons")
    names = detail["raw_player_name"].dropna().astype(str).tolist()
    if names_are_different(names):
        chips.append("Very different names")
    if ((pd.to_numeric(detail["runs"], errors="coerce").fillna(0) > 0) & (pd.to_numeric(detail["balls_faced"], errors="coerce").fillna(0) == 0)).any():
        chips.append("Runs missing balls")
    if ((pd.to_numeric(detail["wickets"], errors="coerce").fillna(0) > 0) & (pd.to_numeric(detail["balls_bowled"], errors="coerce").fillna(0) == 0)).any():
        chips.append("Wickets missing balls")
    return chips or ["No obvious issues"]


def names_are_different(names: list[str]) -> bool:
    if len(names) < 2:
        return False
    from difflib import SequenceMatcher

    cleaned = [name.strip().casefold() for name in names if name.strip()]
    for index, left in enumerate(cleaned):
        for right in cleaned[index + 1 :]:
            if SequenceMatcher(None, left, right).ratio() < 0.45:
                return True
    return False


def format_audit_table(table: pd.DataFrame) -> pd.DataFrame:
    output = table.copy()
    for column in output.columns:
        if column in {"batting_average", "batting_strike_rate", "bowling_average", "economy", "bowling_strike_rate", "recalculated_batting_average", "recalculated_batting_strike_rate", "recalculated_bowling_average", "recalculated_economy", "recalculated_bowling_strike_rate"}:
            output[column] = pd.to_numeric(output[column], errors="coerce").map(lambda value: "—" if pd.isna(value) else f"{float(value):.2f}")
        elif column not in {"canonical_player_id", "canonical_player_name", "raw_profile_key", "raw_player_id", "raw_player_name", "teams", "seasons", "overs", "total_overs"}:
            numeric = pd.to_numeric(output[column], errors="coerce")
            if numeric.notna().any():
                output[column] = numeric.map(lambda value: "—" if pd.isna(value) else f"{int(value):,}")
    return output.rename(columns=audit_pretty_names()).fillna("—").replace("", "—")


def audit_pretty_names() -> dict[str, str]:
    return {
        "canonical_player_id": "Canonical Player ID",
        "canonical_player_name": "Canonical Player",
        "raw_profile_key": "Raw Profile Key",
        "raw_player_id": "Raw Player ID",
        "raw_player_name": "Raw Player Name",
        "teams": "Teams",
        "seasons": "Seasons",
        "matches": "Matches",
        "innings": "Innings",
        "runs": "Runs",
        "balls_faced": "Balls Faced",
        "outs": "Outs",
        "batting_average": "Batting Avg",
        "batting_strike_rate": "Batting SR",
        "overs": "Overs",
        "balls_bowled": "Balls Bowled",
        "wickets": "Wickets",
        "runs_conceded": "Runs Conceded",
        "bowling_average": "Bowling Avg",
        "economy": "Economy",
        "bowling_strike_rate": "Bowling SR",
        "catches": "Catches",
        "stumpings": "Stumpings",
        "run_outs": "Run Outs",
        "dismissals": "Dismissals",
        "total_matches": "Total Matches",
        "total_innings": "Total Innings",
        "total_runs": "Total Runs",
        "total_balls_faced": "Total Balls Faced",
        "total_outs": "Total Outs",
        "recalculated_batting_average": "Recalculated Batting Avg",
        "recalculated_batting_strike_rate": "Recalculated Batting SR",
        "total_overs": "Total Overs",
        "total_balls_bowled": "Total Balls Bowled",
        "total_wickets": "Total Wickets",
        "total_runs_conceded": "Total Runs Conceded",
        "recalculated_bowling_average": "Recalculated Bowling Avg",
        "recalculated_economy": "Recalculated Economy",
        "recalculated_bowling_strike_rate": "Recalculated Bowling SR",
        "total_catches": "Total Catches",
        "total_stumpings": "Total Stumpings",
        "total_run_outs": "Total Run Outs",
        "total_dismissals": "Total Dismissals",
    }


def render_validation_reference() -> None:
    validation = load_player_merge_validation()
    render_section_heading("Validation Notes")
    if validation.empty:
        st.caption("Validation statuses live in data/player_merge_validation.csv. Add rows there when you have reviewed a merge.")
        return
    st.dataframe(validation, use_container_width=True, hide_index=True)


def render_possible_duplicate_suggestions(suggestions: pd.DataFrame) -> None:
    render_section_heading("Possible Duplicate Suggestions")
    if suggestions.empty:
        st.info("No possible duplicate suggestions found yet.")
        return
    display_columns = [
        "player_name_a",
        "player_name_b",
        "similarity_score",
        "teams_seen_a",
        "teams_seen_b",
        "seasons_seen_a",
        "seasons_seen_b",
        "suggested_reason",
    ]
    output = select_display_columns(suggestions, display_columns).rename(
        columns={
            "player_name_a": "Suggested Player A",
            "player_name_b": "Suggested Player B",
            "similarity_score": "Similarity Score",
            "teams_seen_a": "Teams A",
            "teams_seen_b": "Teams B",
            "seasons_seen_a": "Seasons A",
            "seasons_seen_b": "Seasons B",
            "suggested_reason": "Suggested Reason",
        }
    )
    output["Action Note"] = "Manual review only. Add to data/player_aliases.csv if confirmed."
    with st.container(key="duplicate_suggestions_card"):
        st.dataframe(output, use_container_width=True, hide_index=True, height=520)


def render_context_line(dashboard_data: dict[str, object]) -> None:
    st.markdown(
        f"""
        <div class="context-line">
            <span>{html.escape(str(dashboard_data["context_description"]))}</span>
            <span class="source-note">App created by Siddhanth Chaurasiya | Preet Kaur</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_dashboard_metrics(dashboard_data: dict[str, object]) -> dict[str, object]:
    batting_df = dashboard_data["batting"]
    bowling_df = dashboard_data["bowling"]
    fielding_df = dashboard_data["fielding"]
    team_batting_df = dashboard_data.get("team_batting", batting_df)
    team_bowling_df = dashboard_data.get("team_bowling", bowling_df)

    players = set()
    for frame in [batting_df, bowling_df, fielding_df]:
        if not frame.empty and "player_name" in frame:
            players.update(frame["player_name"].dropna().tolist())

    matches = estimate_total_matches(
        [
            team_batting_df,
            team_bowling_df,
            dashboard_data.get("team_fielding", fielding_df),
        ]
    )
    runs = int(numeric_sort_series(batting_df, "battingAggregate", 0).sum())
    wickets = int(numeric_sort_series(bowling_df, "bowlingWickets", 0).sum())

    top_batter = top_rows(batting_df, "battingAggregate", limit=1)
    top_bowler = top_rows(bowling_df, "bowlingWickets", limit=1)
    fielding_with_aliases = add_display_stat_aliases(fielding_df)

    return {
        "teams": len(dashboard_data.get("teams", [])) or 1,
        "matches": matches,
        "runs": runs,
        "wickets": wickets,
        "avg_batting_score": runs / matches if matches else None,
        "avg_wickets": wickets / matches if matches else None,
        "dismissals": int(pd.to_numeric(fielding_with_aliases.get("dismissals_display"), errors="coerce").sum()),
        "players": len(players),
        "top_batter": top_batter.iloc[0].to_dict() if not top_batter.empty else {},
        "top_bowler": top_bowler.iloc[0].to_dict() if not top_bowler.empty else {},
    }


def render_kpi_cards(snapshot: dict[str, object]) -> None:
    cards = [
        ("Teams", f"{snapshot['teams']:,}", "", "team", "XI", "purple"),
        ("Matches Played", f"{snapshot['matches']:,}", "", "matches", "▤", "blue"),
        ("Runs Scored", f"{snapshot['runs']:,}", f"Avg. {format_metric(snapshot['avg_batting_score'])}", "runs", "🏏", "purple"),
        ("Wickets Taken", f"{snapshot['wickets']:,}", f"Avg. {format_metric(snapshot['avg_wickets'])}", "wickets", "●", "green"),
    ]

    columns = st.columns(4)
    for column, card in zip(columns, cards):
        with column:
            render_kpi_card(*card)

    st.markdown("<div class='dashboard-spacer'></div>", unsafe_allow_html=True)


def estimate_total_matches(frames: list[pd.DataFrame]) -> int:
    team_totals: dict[str, float] = {}
    fallback = 0.0
    for frame in frames:
        if frame.empty or "matches" not in frame:
            continue
        frame_matches = pd.to_numeric(frame["matches"], errors="coerce")
        if "team_id" in frame:
            for team_id, group in frame.assign(_matches=frame_matches).groupby("team_id"):
                current = float(group["_matches"].max()) if group["_matches"].notna().any() else 0.0
                team_totals[str(team_id)] = max(team_totals.get(str(team_id), 0.0), current)
        elif frame_matches.notna().any():
            fallback = max(fallback, float(frame_matches.max()))

    total = sum(team_totals.values()) if team_totals else fallback
    return int(total)


def format_metric(value: object) -> str:
    if value is None or pd.isna(value):
        return "-"
    number = float(value)
    return f"{number:.0f}" if number.is_integer() else f"{number:.1f}"


def render_kpi_card(
    label: str,
    value: str,
    detail: str,
    icon_name: str,
    icon: str,
    tone: str,
) -> None:
    detail_html = f"<div class=\"kpi-detail\">{html.escape(detail)}</div>" if detail else ""
    icon_html = kpi_icon_html(icon_name, icon)
    st.markdown(
        (
            "<div class=\"kpi-card\">"
            "<div class=\"kpi-content\">"
            f"<div class=\"kpi-label\">{html.escape(label)}</div>"
            f"<div class=\"kpi-value\">{value}</div>"
            f"{detail_html}"
            "</div>"
            f"<div class=\"kpi-icon {tone}\">{icon_html}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def kpi_icon_html(icon_name: str, fallback: str) -> str:
    for extension, mime_type in [("svg", "image/svg+xml"), ("png", "image/png")]:
        icon_path = ICON_ASSET_DIR / f"{icon_name}.{extension}"
        if icon_path.exists():
            encoded = base64.b64encode(icon_path.read_bytes()).decode("ascii")
            asset_class = f"kpi-icon-asset kpi-icon-asset-{extension}"
            return (
                f'<img class="{asset_class}" '
                f'src="data:{mime_type};base64,{encoded}" '
                f'alt="{html.escape(icon_name)} icon">'
            )
    return f'<span class="kpi-icon-fallback">{html.escape(fallback)}</span>'


def render_overall_section(dashboard_data: dict[str, object]) -> None:
    batting_df = dashboard_data["batting"]
    bowling_df = dashboard_data["bowling"]
    render_section_heading("Season Standouts ✨")
    render_section_subtext("Top performers across the club.")
    scorers_col, wickets_col = st.columns(2)

    with scorers_col:
        with st.container(key="top_scorers_card"):
            render_leader_list_card(
                "Top Run Scorers",
                sort_batting_leaders(batting_df).head(5),
                "battingAggregate",
                "runs",
                "battingAverage",
                "Batting avg.",
            )

    with wickets_col:
        with st.container(key="top_wickets_card"):
            render_leader_list_card(
                "Top Wicket Takers",
                sort_bowling_leaders(bowling_df).head(5),
                "bowlingWickets",
                "wickets",
                "bowlingAverage",
                "Bowling avg.",
            )

    render_biggest_improvers(dashboard_data)


def render_section_heading(title: str) -> None:
    st.markdown(f"<h2 class='overview-section-title'>{html.escape(title)}</h2>", unsafe_allow_html=True)


def render_section_subtext(text: str) -> None:
    st.markdown(f"<div class='section-subtext'>{html.escape(text)}</div>", unsafe_allow_html=True)


def render_biggest_improvers(dashboard_data: dict[str, object]) -> None:
    cards = build_biggest_improvers(dashboard_data)
    render_section_heading("Biggest Improvers 📈")
    render_section_subtext("Players with the strongest improvement compared to previous season.")
    if not cards:
        st.markdown(
            '<div class="improver-empty">Not enough qualifying players for this comparison.</div>',
            unsafe_allow_html=True,
        )
        return
    card_html = "".join(biggest_improver_card_html(card) for card in cards)
    st.markdown(f'<div class="improver-grid">{card_html}</div>', unsafe_allow_html=True)


def build_biggest_improvers(dashboard_data: dict[str, object]) -> list[dict[str, object]]:
    current_season = dashboard_data.get("season", {})
    previous = previous_season_for(current_season)
    selected_type = season_type_label(current_season.get("name"))
    comparison_type = improver_comparison_type(selected_type)
    if not previous:
        export_biggest_improvers_debug(
            pd.DataFrame(
                [
                    {
                        "selected_season": current_season.get("name", ""),
                        "selected_season_type": selected_type,
                        "previous_season": "",
                        "previous_same_type_season": "",
                        "comparison_type": comparison_type,
                        "selected_scope": dashboard_data.get("context_label", ""),
                        "reason_if_excluded": f"No comparable previous {selected_type.lower()} season found",
                    }
                ]
            )
        )
        return []
    local_version = metadata_mtime()
    identity_version = player_aliases_mtime()
    current_id = str(current_season.get("id", ""))
    previous_id = str(previous.get("id", ""))
    if not current_id or not previous_id:
        return []

    scope = selected_improver_scope(dashboard_data)
    current_matches = season_player_match_counts(current_id, scope, local_version, identity_version)
    previous_matches = season_player_match_counts(previous_id, scope, local_version, identity_version)
    debug_frame = build_biggest_improvers_debug_frame(
        current_season,
        previous,
        scope,
        current_id,
        previous_id,
        current_matches,
        previous_matches,
        local_version,
        identity_version,
    )
    export_biggest_improvers_debug(debug_frame)
    cards: list[dict[str, object]] = []
    runs_card = biggest_improver_for_metric(
        "Biggest Run Improvement",
        "batting",
        "battingAggregate",
        "runs",
        current_id,
        previous_id,
        scope,
        current_matches,
        previous_matches,
        local_version,
        identity_version,
    )
    wickets_card = biggest_improver_for_metric(
        "Biggest Wickets Improvement",
        "bowling",
        "bowlingWickets",
        "wickets",
        current_id,
        previous_id,
        scope,
        current_matches,
        previous_matches,
        local_version,
        identity_version,
    )
    for card in [runs_card, wickets_card]:
        if card:
            cards.append(card)
    return cards


def previous_season_for(current_season: dict[str, object]) -> dict[str, object] | None:
    seasons = load_local_playcricket_seasons(metadata_mtime())
    if not seasons:
        return None
    current_id = str(current_season.get("id", ""))
    current_type = season_type_label(current_season.get("name"))
    ordered = sorted(
        [season for season in seasons if season_type_label(season.get("name")) == current_type],
        key=lambda season: season_sort_from_record(season),
    )
    for index, season in enumerate(ordered):
        if str(season.get("id", "")) == current_id:
            return ordered[index - 1] if index > 0 else None
    return None


def season_type_label(season_name: object) -> str:
    return "Winter" if "winter" in str(season_name or "").casefold() else "Summer"


def improver_comparison_type(season_type: str) -> str:
    normalized = season_type.casefold()
    return f"{normalized}_to_previous_{normalized}"


def season_sort_from_record(season: dict[str, object]) -> int:
    start = pd.to_datetime(season.get("startDate"), errors="coerce", utc=True)
    if pd.notna(start):
        return int(start.timestamp())
    return season_sort_value(season.get("name"))


def selected_improver_scope(dashboard_data: dict[str, object]) -> dict[str, object]:
    selected_team = dashboard_data.get("team", {}) or {}
    is_all = bool(dashboard_data.get("is_all_teams"))
    if is_all or selected_team.get("id") == "__all_teams__":
        return {
            "is_all": True,
            "label": "All teams - Whole club",
            "display": "",
            "team": "",
            "grade": "",
        }
    grade_name = selected_team.get("grade", {}).get("name", "")
    team_name = selected_team.get("name", "")
    return {
        "is_all": False,
        "label": team_card_title(selected_team),
        "display": team_card_title(selected_team),
        "team": clean_team_name(team_name),
        "grade": canonical_grade_label(team_name, grade_name),
    }


def filter_frame_to_improver_scope(frame: pd.DataFrame, scope: dict[str, object]) -> pd.DataFrame:
    if frame.empty or scope.get("is_all"):
        return frame.copy()
    scoped = apply_team_grade_display_columns(frame.copy())
    display = str(scope.get("display") or "")
    grade = str(scope.get("grade") or "")
    team = str(scope.get("team") or "")
    mask = pd.Series(False, index=scoped.index)
    if display and "team_grade_display" in scoped:
        mask = mask | (scoped["team_grade_display"].fillna("").astype(str) == display)
    if grade and "canonical_grade_label" in scoped:
        grade_match = scoped["canonical_grade_label"].fillna("").astype(str) == grade
        if team and "canonical_team_label" in scoped:
            team_match = scoped["canonical_team_label"].fillna("").astype(str).isin([team, ""])
            mask = mask | (grade_match & team_match)
        else:
            mask = mask | grade_match
    return scoped[mask].copy()


def season_player_match_counts(
    season_id: str,
    scope: dict[str, object],
    local_version: float,
    identity_version: float | None,
) -> pd.DataFrame:
    frames = []
    for category in ["batting", "bowling", "fielding"]:
        frame = load_local_category_frame(category, season_id, None, local_version, identity_version)
        frame = filter_frame_to_improver_scope(frame, scope)
        if frame.empty or "matches" not in frame:
            continue
        frame["player_key"] = player_keys(frame)
        group_cols = ["player_key"]
        if "team_id" in frame:
            group_cols.append("team_id")
        frame["matches"] = pd.to_numeric(frame["matches"], errors="coerce").fillna(0)
        frames.append(frame.groupby(group_cols, dropna=False, as_index=False)["matches"].max())
    if not frames:
        return pd.DataFrame(columns=["player_key", "matches"])
    combined = pd.concat(frames, ignore_index=True)
    group_cols = ["player_key"]
    if "team_id" in combined:
        group_cols.append("team_id")
    team_counts = combined.groupby(group_cols, dropna=False, as_index=False)["matches"].max()
    return team_counts.groupby("player_key", as_index=False)["matches"].sum()


def season_metric_totals(
    category: str,
    season_id: str,
    scope: dict[str, object],
    value_column: str,
    local_version: float,
    identity_version: float | None,
) -> pd.DataFrame:
    frame = load_local_category_frame(category, season_id, None, local_version, identity_version)
    frame = filter_frame_to_improver_scope(frame, scope)
    if frame.empty or value_column not in frame:
        return pd.DataFrame(columns=["player_key", "player_name", value_column])
    frame = frame.copy()
    frame["player_key"] = player_keys(frame)
    name_column = "canonical_player_name" if "canonical_player_name" in frame else "player_name"
    frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce").fillna(0)
    totals = (
        frame.groupby("player_key", as_index=False)
        .agg(player_name=(name_column, "first"), **{value_column: (value_column, "sum")})
    )
    return totals


def biggest_improver_for_metric(
    title: str,
    category: str,
    value_column: str,
    unit: str,
    current_season_id: str,
    previous_season_id: str,
    scope: dict[str, object],
    current_matches: pd.DataFrame,
    previous_matches: pd.DataFrame,
    local_version: float,
    identity_version: float | None,
) -> dict[str, object] | None:
    current = season_metric_totals(category, current_season_id, scope, value_column, local_version, identity_version)
    previous = season_metric_totals(category, previous_season_id, scope, value_column, local_version, identity_version)
    if current.empty or previous.empty:
        return None
    merged = current.merge(previous[["player_key", value_column]], on="player_key", how="inner", suffixes=("_current", "_previous"))
    merged = merged.merge(current_matches.rename(columns={"matches": "current_matches"}), on="player_key", how="left")
    merged = merged.merge(previous_matches.rename(columns={"matches": "previous_matches"}), on="player_key", how="left")
    merged["current_matches"] = pd.to_numeric(merged["current_matches"], errors="coerce").fillna(0)
    merged["previous_matches"] = pd.to_numeric(merged["previous_matches"], errors="coerce").fillna(0)
    merged = merged[(merged["current_matches"] >= 8) & (merged["previous_matches"] >= 8)].copy()
    if merged.empty:
        return None
    merged["improvement"] = merged[f"{value_column}_current"] - merged[f"{value_column}_previous"]
    merged = merged[merged["improvement"] > 0].copy()
    if merged.empty:
        return None
    merged = merged.sort_values(["improvement", f"{value_column}_current", "player_name"], ascending=[False, False, True])
    row = merged.iloc[0]
    previous_value = float(row[f"{value_column}_previous"])
    percentage = None if previous_value <= 0 else (float(row["improvement"]) / previous_value * 100)
    return {
        "title": title,
        "player": str(row["player_name"]),
        "current": int(row[f"{value_column}_current"]),
        "previous": int(row[f"{value_column}_previous"]),
        "improvement": int(row["improvement"]),
        "percentage": percentage,
        "unit": unit,
    }


def build_biggest_improvers_debug_frame(
    current_season: dict[str, object],
    previous_season: dict[str, object],
    scope: dict[str, object],
    current_season_id: str,
    previous_season_id: str,
    current_matches: pd.DataFrame,
    previous_matches: pd.DataFrame,
    local_version: float,
    identity_version: float | None,
) -> pd.DataFrame:
    selected_type = season_type_label(current_season.get("name"))
    previous_same_type = previous_season.get("name", "")
    comparison_type = improver_comparison_type(selected_type)
    current_runs = season_metric_totals("batting", current_season_id, scope, "battingAggregate", local_version, identity_version)
    previous_runs = season_metric_totals("batting", previous_season_id, scope, "battingAggregate", local_version, identity_version)
    current_wickets = season_metric_totals("bowling", current_season_id, scope, "bowlingWickets", local_version, identity_version)
    previous_wickets = season_metric_totals("bowling", previous_season_id, scope, "bowlingWickets", local_version, identity_version)

    debug = pd.DataFrame({"player_key": sorted(set().union(
        set(current_matches.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(previous_matches.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(current_runs.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(previous_runs.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(current_wickets.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(previous_wickets.get("player_key", pd.Series(dtype=str)).astype(str)),
    ))})
    if debug.empty:
        return pd.DataFrame(
            [
                {
                    "selected_season": current_season.get("name", ""),
                    "selected_season_type": selected_type,
                    "previous_season": previous_season.get("name", ""),
                    "previous_same_type_season": previous_same_type,
                    "comparison_type": comparison_type,
                    "selected_scope": scope.get("label", ""),
                    "reason_if_excluded": "No player rows found in current or previous scope",
                }
            ]
        )

    debug = debug.merge(current_matches.rename(columns={"matches": "current_matches"}), on="player_key", how="left")
    debug = debug.merge(previous_matches.rename(columns={"matches": "previous_matches"}), on="player_key", how="left")
    debug = debug.merge(
        current_runs.rename(columns={"player_name": "canonical_player_name", "battingAggregate": "current_runs"}),
        on="player_key",
        how="left",
    )
    debug = debug.merge(
        previous_runs.rename(columns={"player_name": "previous_player_name", "battingAggregate": "previous_runs"}),
        on="player_key",
        how="left",
    )
    debug = debug.merge(
        current_wickets.rename(columns={"player_name": "wicket_player_name", "bowlingWickets": "current_wickets"}),
        on="player_key",
        how="left",
    )
    debug = debug.merge(
        previous_wickets.rename(columns={"player_name": "previous_wicket_player_name", "bowlingWickets": "previous_wickets"}),
        on="player_key",
        how="left",
    )
    for column in ["current_matches", "previous_matches", "current_runs", "previous_runs", "current_wickets", "previous_wickets"]:
        debug[column] = pd.to_numeric(debug.get(column), errors="coerce").fillna(0)
    debug["canonical_player_name"] = (
        debug.get("canonical_player_name", pd.Series(index=debug.index, dtype=object))
        .fillna(debug.get("previous_player_name", pd.Series(index=debug.index, dtype=object)))
        .fillna(debug.get("wicket_player_name", pd.Series(index=debug.index, dtype=object)))
        .fillna(debug.get("previous_wicket_player_name", pd.Series(index=debug.index, dtype=object)))
        .fillna(debug["player_key"])
    )
    debug["runs_improvement"] = debug["current_runs"] - debug["previous_runs"]
    debug["wickets_improvement"] = debug["current_wickets"] - debug["previous_wickets"]
    debug["runs_improvement_pct"] = debug.apply(
        lambda row: None if row["previous_runs"] <= 0 else row["runs_improvement"] / row["previous_runs"] * 100,
        axis=1,
    )
    debug["wickets_improvement_pct"] = debug.apply(
        lambda row: None if row["previous_wickets"] <= 0 else row["wickets_improvement"] / row["previous_wickets"] * 100,
        axis=1,
    )
    debug["qualifies_runs"] = (
        (debug["current_matches"] >= 8)
        & (debug["previous_matches"] >= 8)
        & (debug["runs_improvement"] > 0)
    )
    debug["qualifies_wickets"] = (
        (debug["current_matches"] >= 8)
        & (debug["previous_matches"] >= 8)
        & (debug["wickets_improvement"] > 0)
    )
    debug["reason_if_excluded"] = debug.apply(improver_exclusion_reason, axis=1)
    debug.insert(0, "selected_season", current_season.get("name", ""))
    debug.insert(1, "selected_season_type", selected_type)
    debug.insert(2, "previous_season", previous_season.get("name", ""))
    debug.insert(3, "previous_same_type_season", previous_same_type)
    debug.insert(4, "comparison_type", comparison_type)
    debug.insert(5, "selected_scope", scope.get("label", ""))
    debug = debug.rename(columns={"player_key": "canonical_player_id"})
    columns = [
        "selected_season",
        "selected_season_type",
        "previous_season",
        "previous_same_type_season",
        "comparison_type",
        "selected_scope",
        "canonical_player_id",
        "canonical_player_name",
        "current_matches",
        "previous_matches",
        "current_runs",
        "previous_runs",
        "runs_improvement",
        "runs_improvement_pct",
        "current_wickets",
        "previous_wickets",
        "wickets_improvement",
        "wickets_improvement_pct",
        "qualifies_runs",
        "qualifies_wickets",
        "reason_if_excluded",
    ]
    return debug[columns].sort_values(["qualifies_runs", "qualifies_wickets", "runs_improvement", "wickets_improvement"], ascending=[False, False, False, False])


def improver_exclusion_reason(row: pd.Series) -> str:
    reasons = []
    if row["current_matches"] < 8:
        reasons.append("current matches below 8")
    if row["previous_matches"] < 8:
        reasons.append("previous matches below 8")
    if row["runs_improvement"] <= 0 and row["wickets_improvement"] <= 0:
        reasons.append("no positive runs or wickets improvement")
    if not reasons:
        return "qualifies"
    return "; ".join(reasons)


def export_biggest_improvers_debug(debug_frame: pd.DataFrame) -> None:
    columns = [
        "selected_season",
        "selected_season_type",
        "previous_season",
        "previous_same_type_season",
        "comparison_type",
        "selected_scope",
        "canonical_player_id",
        "canonical_player_name",
        "current_matches",
        "previous_matches",
        "current_runs",
        "previous_runs",
        "runs_improvement",
        "runs_improvement_pct",
        "current_wickets",
        "previous_wickets",
        "wickets_improvement",
        "wickets_improvement_pct",
        "qualifies_runs",
        "qualifies_wickets",
        "reason_if_excluded",
    ]
    debug_frame = debug_frame.copy()
    for column in columns:
        if column not in debug_frame:
            debug_frame[column] = ""
    DEBUG_BIGGEST_IMPROVERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    debug_frame[columns].to_csv(DEBUG_BIGGEST_IMPROVERS_PATH, index=False)


def biggest_improver_card_html(card: dict[str, object]) -> str:
    percentage = card.get("percentage")
    pct_text = "new entry" if percentage is None else f"▲ {percentage:.0f}%"
    unit = html.escape(str(card["unit"]))
    return (
        '<div class="improver-card">'
        f'<div class="improver-label">{html.escape(str(card["title"]))}</div>'
        f'<div class="improver-player">{html.escape(str(card["player"]))}</div>'
        f'<div class="improver-gain">+{int(card["improvement"]):,} {unit} <span>{html.escape(pct_text)}</span></div>'
        f'<div class="improver-meta">Current {int(card["current"]):,} {unit} · Previous {int(card["previous"]):,} {unit}</div>'
        '</div>'
    )


def numeric_sort_series(df: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in df:
        return pd.Series([default] * len(df), index=df.index, dtype="float64")
    return pd.to_numeric(df[column], errors="coerce").fillna(default)


def name_sort_series(df: pd.DataFrame) -> pd.Series:
    if "player_name" not in df:
        return pd.Series([""] * len(df), index=df.index)
    return df["player_name"].fillna("").astype(str).str.casefold()


def sort_batting_leaders(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    output = df.copy()
    output["_runs_sort"] = numeric_sort_series(output, "battingAggregate", 0)
    output["_bat_avg_sort"] = numeric_sort_series(output, "battingAverage", -1)
    output["_name_sort"] = name_sort_series(output)
    return output.sort_values(["_runs_sort", "_bat_avg_sort", "_name_sort"], ascending=[False, False, True]).drop(columns=["_runs_sort", "_bat_avg_sort", "_name_sort"])


def sort_bowling_leaders(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    output = df.copy()
    output["_wickets_sort"] = numeric_sort_series(output, "bowlingWickets", 0)
    output["_bowl_avg_sort"] = numeric_sort_series(output, "bowlingAverage", 999999)
    output["_name_sort"] = name_sort_series(output)
    return output.sort_values(["_wickets_sort", "_bowl_avg_sort", "_name_sort"], ascending=[False, True, True]).drop(columns=["_wickets_sort", "_bowl_avg_sort", "_name_sort"])


def sort_count_leaders(df: pd.DataFrame, count_column: str) -> pd.DataFrame:
    if df.empty:
        return df
    output = df.copy()
    output["_count_sort"] = numeric_sort_series(output, count_column, 0)
    output["_matches_sort"] = numeric_sort_series(output, "matches", 999999)
    output["_name_sort"] = name_sort_series(output)
    return output.sort_values(["_count_sort", "_matches_sort", "_name_sort"], ascending=[False, True, True]).drop(columns=["_count_sort", "_matches_sort", "_name_sort"])


def render_leader_list_card(
    title: str,
    df: pd.DataFrame,
    value_column: str,
    suffix: str,
    average_column: str,
    average_label: str,
) -> None:
    st.markdown(f"#### {html.escape(title)}")
    render_progress_list(
        df,
        value_column=value_column,
        suffix=suffix,
        average_column=average_column,
        average_label=average_label,
    )


def render_progress_list(
    df: pd.DataFrame,
    value_column: str,
    suffix: str,
    average_column: str,
    average_label: str,
) -> None:
    if df.empty or value_column not in df:
        st.caption("No data available.")
        return

    values = pd.to_numeric(df[value_column], errors="coerce").fillna(0)
    max_value = values.max()
    rows = []
    for rank, ((_, row), value) in enumerate(zip(df.iterrows(), values), start=1):
        value = float(value)
        width = 0 if not max_value else value / max_value * 100
        rows.append(
            f"""
            <div class="progress-row">
                <span class="progress-rank">{rank}</span>
                <span class="progress-name">{html.escape(str(row["player_name"]))}</span>
                <span class="progress-value">
                    <strong>{int(value):,} {html.escape(suffix)}</strong>
                    {average_line_html(row, average_column, average_label, "progress-average")}
                </span>
                <div class="progress-track"><div style="width:{width:.0f}%"></div></div>
            </div>
            """
        )

    st.markdown("".join(rows), unsafe_allow_html=True)


def render_team_specific_leaders(dashboard_data: dict[str, object]) -> None:
    team_batting = dashboard_data.get("team_batting", dashboard_data["batting"])
    team_bowling = dashboard_data.get("team_bowling", dashboard_data["bowling"])
    teams = dashboard_data.get("teams", [])

    render_section_heading("Leaders by Team/Grade 👥")
    render_section_subtext("Top performers by team/grade.")
    if not teams:
        st.caption("No teams available for this selection.")
        return

    for index in range(0, len(teams), 2):
        columns = st.columns(2)
        for column, team in zip(columns, teams[index : index + 2]):
            with column:
                render_team_leader_card(team, team_batting, team_bowling)


def render_team_leader_card(
    team: dict,
    team_batting: pd.DataFrame,
    team_bowling: pd.DataFrame,
) -> None:
    team_id = str(team.get("id"))
    batting_scope = filter_team_frame(team_batting, team_id)
    bowling_scope = filter_team_frame(team_bowling, team_id)
    top_batter = top_team_row(batting_scope, "battingAggregate")
    top_bowler = top_team_row(bowling_scope, "bowlingWickets")
    batter_value = numeric_value(top_batter, "battingAggregate")
    bowler_value = numeric_value(top_bowler, "bowlingWickets")
    batter_average = numeric_value(top_batter, "battingAverage")
    bowler_average = numeric_value(top_bowler, "bowlingAverage")
    matches = estimate_team_matches([batting_scope, bowling_scope])
    max_runs = max(
        1.0,
        float(numeric_sort_series(batting_scope, "battingAggregate", 0).max() or 0),
    )
    max_wickets = max(
        1.0,
        float(numeric_sort_series(bowling_scope, "bowlingWickets", 0).max() or 0),
    )

    st.markdown(
        (
            "<div class=\"team-leader-card\">"
            "<div class=\"team-card-header\">"
            f"<div class=\"team-card-title\">{html.escape(team_card_title(team))}</div>"
            f"<div class=\"team-card-meta\">{matches} matches</div>"
            "</div>"
            "<div class=\"mini-leader-grid\">"
            f"{mini_leader_html('Top Batter', top_batter, batter_value, 'runs', batter_value / max_runs * 100, '◷', batter_average, 'Batting avg.')}"
            f"{mini_leader_html('Top Bowler', top_bowler, bowler_value, 'wickets', bowler_value / max_wickets * 100, '◉', bowler_average, 'Bowling avg.')}"
            "</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def team_card_title(team: dict) -> str:
    if team.get("id") == "__all_teams__":
        return "All teams - Whole club"
    return build_team_grade_display(team.get("name", ""), team.get("grade", {}).get("name", ""))


def filter_team_frame(frame: pd.DataFrame, team_id: str) -> pd.DataFrame:
    if frame.empty or "team_id" not in frame:
        return frame.head(0)
    return frame[frame["team_id"].astype(str) == team_id]


def estimate_team_matches(frames: list[pd.DataFrame]) -> int:
    matches = 0.0
    for frame in frames:
        if not frame.empty and "matches" in frame:
            values = pd.to_numeric(frame["matches"], errors="coerce")
            if values.notna().any():
                matches = max(matches, float(values.max()))
    return int(matches)


def top_team_row(frame: pd.DataFrame, sort_column: str) -> pd.Series:
    if frame.empty or sort_column not in frame:
        return pd.Series(dtype="object")
    output = sort_batting_leaders(frame) if sort_column == "battingAggregate" else sort_bowling_leaders(frame)
    return output.iloc[0] if not output.empty else pd.Series(dtype="object")


def numeric_value(row: pd.Series, column: str) -> float:
    if row.empty or column not in row:
        return 0.0
    value = pd.to_numeric(row.get(column), errors="coerce")
    return 0.0 if pd.isna(value) else float(value)


def average_line_html(
    row: pd.Series,
    column: str,
    label: str,
    class_name: str,
) -> str:
    if row.empty or column not in row:
        return f'<span class="{class_name}">Avg. —</span>'

    value = pd.to_numeric(row.get(column), errors="coerce")
    if pd.isna(value) or not pd.notna(value) or value in {float("inf"), float("-inf")}:
        return f'<span class="{class_name}">Avg. —</span>'

    return f'<span class="{class_name}">{html.escape(label)} {float(value):.1f}</span>'


def mini_leader_html(
    label: str,
    row: pd.Series,
    value: float,
    suffix: str,
    width: float,
    icon: str,
    average: float,
    average_label: str,
) -> str:
    player_name = str(row.get("player_name", "-")) if not row.empty else "-"
    average_html = average_stat_html(average, average_label)
    return (
        "<div class=\"mini-leader\">"
        "<div class=\"mini-label-row\">"
        f"<span class=\"mini-icon\">{html.escape(icon)}</span>"
        f"<span class=\"mini-label\">{html.escape(label)}</span>"
        "</div>"
        "<div class=\"mini-value-row\">"
        f"<div class=\"mini-player\">{html.escape(player_name)}</div>"
        "<div class=\"mini-stat-block\">"
        f"<div class=\"mini-stat\">{int(value):,} {html.escape(suffix)}</div>"
        f"{average_html}"
        "</div>"
        "</div>"
        f"<div class=\"mini-track\"><div style=\"width:{max(0, min(width, 100)):.0f}%\"></div></div>"
        "</div>"
    )


def average_stat_html(value: float, label: str) -> str:
    if pd.isna(value) or value in {float("inf"), float("-inf")}:
        return '<div class="mini-average">Avg. —</div>'
    return f'<div class="mini-average">{html.escape(label)} {float(value):.1f}</div>'


def render_form_guide(batting_df: pd.DataFrame) -> None:
    if batting_df.empty:
        st.caption("No data available.")
        return

    leaders = batting_df.sort_values("battingAverage", ascending=False).head(5)
    rows = []
    for _, row in leaders.iterrows():
        avg = float(row.get("battingAverage", 0) or 0)
        chips = build_form_chips(row)
        rows.append(
            "<div class=\"form-row\">"
            "<div>"
            f"<strong>{html.escape(str(row['player_name']))}</strong>"
            f"<span>Avg. {avg:.1f}</span>"
            "</div>"
            f"<div class=\"pill-row\">{chips}</div>"
            "</div>"
        )

    st.markdown(
        "".join(rows)
        + (
            "<div class=\"form-legend\">"
            "<span><i class=\"legend-dot green\"></i>50+</span>"
            "<span><i class=\"legend-dot current\"></i>25–49</span>"
            "<span><i class=\"legend-dot slate\"></i>0–24</span>"
            "<span><i class=\"legend-dot red\"></i>Duck</span>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def build_form_chips(row: pd.Series) -> str:
    high_score = row.get("battingHighScore")
    avg = row.get("battingAverage")
    innings = int(row.get("battingInnings", row.get("matches", 0)) or 0)
    values = []
    for value in [high_score, avg, row.get("battingAggregate", 0) / max(innings, 1)]:
        if pd.notna(value):
            values.append(int(float(value)))

    while len(values) < 10:
        values.append(None)

    chips = []
    for value in values[:10]:
        if value is None:
            chips.append('<span class="score-dot muted">–</span>')
            continue
        if value == 0:
            css_class = "duck"
        elif value >= 50:
            css_class = "green"
        elif value >= 25:
            css_class = "purple"
        else:
            css_class = "slate"
        chips.append(f'<span class="score-dot {css_class}">{value}</span>')

    return "".join(chips)


def render_leader_cards(dashboard_data: dict[str, object]) -> None:
    batting_df = dashboard_data["batting"]
    bowling_df = dashboard_data["bowling"]
    fielding_df = dashboard_data["fielding"]
    show_team = bool(dashboard_data.get("is_all_teams"))

    bat_col, bowl_col, field_col = st.columns(3)
    with bat_col:
        with st.container(key="batting_card"):
            render_compact_leaderboard_card(
                "Batting Leaders",
                batting_df.sort_values("battingAggregate", ascending=False).head(5),
                columns=["player_name", "matches", "battingAggregate", "battingAverage", "battingStrikeRate", "high_score"],
                rename_map={
                    "player_name": "Player",
                    "matches": "M",
                    "battingAggregate": "Runs",
                    "battingAverage": "Avg",
                    "battingStrikeRate": "SR",
                    "high_score": "HS",
                },
                link_label="View full batting stats",
                target="batting",
            )
    with bowl_col:
        with st.container(key="bowling_card"):
            render_compact_leaderboard_card(
                "Bowling Leaders",
                bowling_df.sort_values("bowlingWickets", ascending=False).head(5),
                columns=["player_name", "matches", "bowlingWickets", "overs_bowled_display", "bowlingAverage", "bowlingEconomyRate", "bowlingStrikeRate"],
                rename_map={
                    "player_name": "Player",
                    "matches": "M",
                    "bowlingWickets": "Wkts",
                    "overs_bowled_display": "Overs",
                    "bowlingAverage": "Avg",
                    "bowlingEconomyRate": "Econ",
                    "bowlingStrikeRate": "SR",
                },
                link_label="View full bowling stats",
                target="bowling",
            )
    with field_col:
        with st.container(key="fielding_card"):
            render_compact_leaderboard_card(
                "Fielding Leaders",
                top_fielding_rows(fielding_df).head(5),
                columns=["player_name", "matches", "catches_display", "stumpings_display", "run_outs_display", "dismissals_display"],
                rename_map={
                    "player_name": "Player",
                    "matches": "M",
                    "catches_display": "Ct",
                    "stumpings_display": "St",
                    "run_outs_display": "RO",
                    "dismissals_display": "Dis",
                },
                link_label="View full fielding stats",
                target="fielding",
            )


def render_compact_leaderboard_card(
    title: str,
    df: pd.DataFrame,
    columns: list[str],
    rename_map: dict[str, str],
    link_label: str,
    target: str,
) -> None:
    st.markdown(
        f"""
        <div class="compact-card-header">
            <div class="card-title">{html.escape(title)}</div>
            <a href="#full-stats">{html.escape(link_label)} →</a>
        </div>
        """,
        unsafe_allow_html=True,
    )
    table = prepare_table_frame(df, columns, rename_map)
    table.insert(0, "#", [rank_badge(rank) for rank in range(1, len(table) + 1)])
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=248,
        column_config={
            "#": st.column_config.TextColumn("#", width="small"),
            **numeric_column_config(table.columns.tolist()),
        },
    )
    st.markdown(
        f'<a class="full-link" href="#full-stats">View full {html.escape(target)} stats →</a>',
        unsafe_allow_html=True,
    )


def rank_badge(rank: int) -> str:
    if rank == 1:
        return "🥇"
    if rank == 2:
        return "🥈"
    if rank == 3:
        return "🥉"
    return str(rank)


def render_full_stats_section(dashboard_data: dict[str, object]) -> None:
    st.markdown('<div id="full-stats"></div>', unsafe_allow_html=True)
    render_section_heading("Detailed Stats")
    with st.container(key="full_stats_card"):
        tabs = ["Batting", "Bowling", "Fielding"]
        batting_tab, bowling_tab, fielding_tab = st.tabs(tabs)
        with batting_tab:
            render_full_stats_table(
                sort_batting_leaders(dashboard_data["batting"]),
                "batting",
                show_team=False,
            )
        with bowling_tab:
            render_full_stats_table(
                sort_bowling_leaders(dashboard_data["bowling"]),
                "bowling",
                show_team=False,
            )
        with fielding_tab:
            render_full_stats_table(
                sort_fielding_rows(dashboard_data["fielding"]),
                "fielding",
                show_team=False,
            )


def render_dashboard(dashboard_data: dict[str, object] | None) -> None:
    leaderboard_tab, milestones_tab, records_tab, trends_tab = st.tabs(
        ["Leaderboards", "Milestones", "Records", "Trends"]
    )

    with leaderboard_tab:
        if not dashboard_data:
            st.info("Load public PlayCricket stats to view leaderboards.")
        else:
            batting_df = dashboard_data["batting"]
            bowling_df = dashboard_data["bowling"]
            fielding_df = dashboard_data["fielding"]
            show_team = bool(dashboard_data.get("is_all_teams"))

            batting_col, bowling_col = st.columns(2)

            with batting_col:
                st.markdown("### Batting Leaders")
                batting_leaders = batting_df.sort_values(
                    "battingAggregate",
                    ascending=False,
                ).head(15)
                render_batting_table(batting_leaders, batting_df, show_team=show_team)

            with bowling_col:
                st.markdown("### Bowling Leaders")
                bowling_leaders = bowling_df.sort_values(
                    "bowlingWickets",
                    ascending=False,
                ).head(15)
                render_bowling_table(bowling_leaders, bowling_df, show_team=show_team)

            st.markdown("### Fielding Leaders")
            render_fielding_table(top_fielding_rows(fielding_df), show_team=show_team)

            if show_team:
                st.markdown("### Whole Club Complete Stats")
                batting_tab, bowling_tab = st.tabs(["Batting", "Bowling"])
                with batting_tab:
                    render_full_stats_table(
                        batting_df.sort_values("battingAggregate", ascending=False),
                        "batting",
                        show_team=True,
                    )
                with bowling_tab:
                    render_full_stats_table(
                        sort_bowling_by_bbi(bowling_df),
                        "bowling",
                        show_team=True,
                    )

    with milestones_tab:
        st.info("Next we will flag players near milestones like 50 matches, 100 wickets, and 1,000 runs.")

    with records_tab:
        if not dashboard_data:
            st.info("Load public PlayCricket stats to view records.")
        else:
            batting_df = dashboard_data["batting"]
            bowling_df = dashboard_data["bowling"]
            show_team = bool(dashboard_data.get("is_all_teams"))

            record_col_1, record_col_2 = st.columns(2)
            with record_col_1:
                st.markdown("### Highest Scores")
                highest_score_columns = [
                    "player_name",
                    "high_score",
                    "battingAggregate",
                    "matches",
                ]
                if show_team:
                    highest_score_columns.insert(1, "team_name")
                st.dataframe(
                    prepare_table_frame(
                        top_rows(batting_df, "battingHighScore"),
                        highest_score_columns,
                        {
                            "player_name": "Player",
                            "team_name": "Team",
                            "high_score": "HS",
                            "battingAggregate": "Runs",
                            "matches": "Matches",
                        },
                    ),
                    use_container_width=True,
                    hide_index=True,
                    column_config=standard_column_config(),
                )
            with record_col_2:
                st.markdown("### Best Wicket Takers")
                wicket_columns = [
                    "player_name",
                    "bowlingWickets",
                    "bowlingBestInnings",
                    "matches",
                ]
                if show_team:
                    wicket_columns.insert(1, "team_name")
                st.dataframe(
                    prepare_table_frame(
                        top_bowling_figures(bowling_df),
                        wicket_columns,
                        {
                            "player_name": "Player",
                            "team_name": "Team",
                            "bowlingWickets": "Wickets",
                            "bowlingBestInnings": "BBI",
                            "matches": "Matches",
                        },
                    ),
                    use_container_width=True,
                    hide_index=True,
                    column_config=standard_column_config(),
                )

    with trends_tab:
        if not dashboard_data:
            st.info("Load public PlayCricket stats to view charts.")
        else:
            batting_df = top_rows(dashboard_data["batting"], "battingAggregate")
            bowling_df = top_rows(dashboard_data["bowling"], "bowlingWickets")

            st.markdown("### Runs")
            batting_chart = batting_df.assign(
                chart_label=batting_df.apply(make_chart_label, axis=1)
            )
            st.bar_chart(
                batting_chart.set_index("chart_label")["battingAggregate"],
                use_container_width=True,
            )

            st.markdown("### Wickets")
            bowling_chart = bowling_df.assign(
                chart_label=bowling_df.apply(make_chart_label, axis=1)
            )
            st.bar_chart(
                bowling_chart.set_index("chart_label")["bowlingWickets"],
                use_container_width=True,
            )


def make_chart_label(row: pd.Series) -> str:
    if "team_name" in row and pd.notna(row.get("team_name")):
        return f"{row['player_name']} ({compact_team_label(row['team_name'])})"
    return row["player_name"]


def compact_team_label(team_name: object) -> str:
    labels = [clean_team_name(raw_label) for raw_label in str(team_name).split(",")]
    labels = [label for label in labels if label]
    return ", ".join(labels) if labels else str(team_name)


def compact_grade_label(grade_name: object) -> str:
    return clean_grade_name(grade_name)


def add_display_stat_aliases(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    alias_map = {
        "balls_faced_display": ["ballsFaced", "battingBallsFaced"],
        "overs_bowled_display": ["oversBowled", "bowlingOvers", "overs"],
        "catches_display": ["catches", "fieldingTotalCatches", "fieldingCatches"],
        "stumpings_display": ["stumpings", "fieldingStumpings"],
        "run_outs_display": ["runOuts", "fieldingRunOuts", "fieldingAssistedRunOuts"],
        "dismissals_display": ["fieldingDismissals", "dismissals"],
    }

    for alias, candidates in alias_map.items():
        if alias not in output:
            output[alias] = first_available_column(output, candidates)

    if "overs_bowled_display" not in output or output["overs_bowled_display"].isna().all():
        if "bowlingBalls" in output:
            output["overs_bowled_display"] = output["bowlingBalls"].map(format_balls_as_overs)

    if "dismissals_display" in output and output["dismissals_display"].isna().all():
        dismissal_parts = []
        for column in ["catches_display", "stumpings_display", "run_outs_display"]:
            if column in output:
                dismissal_parts.append(
                    pd.to_numeric(output[column], errors="coerce").fillna(0)
                )
        if dismissal_parts:
            output["dismissals_display"] = sum(dismissal_parts)

    return output


def format_balls_as_overs(value: object) -> str | None:
    if pd.isna(value):
        return None

    balls = int(value)
    return f"{balls // 6}.{balls % 6}"


def first_available_column(
    df: pd.DataFrame,
    candidates: list[str],
) -> pd.Series:
    for candidate in candidates:
        if candidate in df:
            return df[candidate]

    return pd.Series([pd.NA] * len(df), index=df.index)


def prepare_table_frame(
    df: pd.DataFrame,
    columns: list[str],
    rename_map: dict[str, str],
) -> pd.DataFrame:
    output = add_display_stat_aliases(df)
    for column in columns:
        if column not in output:
            output[column] = pd.NA

    output = output[columns].rename(columns=rename_map)
    if "Team" in output:
        output["Team"] = output["Team"].map(compact_team_label)

    return output


def standard_column_config() -> dict[str, object]:
    return {
        "Player": st.column_config.TextColumn("Player", pinned=True, width="medium"),
        "Team": st.column_config.TextColumn("Team", width="small"),
    }


def numeric_column_config(columns: list[str]) -> dict[str, object]:
    config = standard_column_config()
    integer_columns = {
        "M",
        "Matches",
        "Seasons Played",
        "Inns",
        "Runs",
        "BF",
        "NO",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
        "Mins",
        "Wkts",
        "Wickets",
        "Mdns",
        "Runs Against",
        "4W",
        "5W",
        "Balls",
        "5WI",
        "10WM",
        "Wides",
        "NB",
        "Ct",
        "Ct Non-WK",
        "Ct WK",
        "St",
        "RO",
        "Assist RO",
        "Direct RO",
        "Dis",
        "Dismissals",
        "Catches",
        "Stumpings",
        "Run Outs",
        "Total Dismissals",
    }
    decimal_columns = {"Avg", "SR", "Bat Avg", "Bat SR", "Bowl Avg", "Econ", "Economy", "Bowl SR"}
    for column in columns:
        if column in integer_columns:
            config[column] = st.column_config.NumberColumn(format="%d")
        elif column in decimal_columns:
            config[column] = st.column_config.NumberColumn(format="%.2f")

    return config


def add_player_medals(
    df: pd.DataFrame,
    source_df: pd.DataFrame,
    sort_column: str,
    ascending: bool = False,
) -> pd.DataFrame:
    if df.empty or "player_name" not in df:
        return df

    output = df.copy()
    badges_by_player = {player: "" for player in output["player_name"].dropna().tolist()}
    medals = ["🥇", "🥈", "🥉"]

    if sort_column not in source_df:
        return output

    ranked = source_df.copy()
    ranked[sort_column] = pd.to_numeric(ranked[sort_column], errors="coerce")
    ranked = ranked[ranked[sort_column].notna()]
    if ranked.empty:
        return output

    ranked = ranked.sort_values(sort_column, ascending=ascending).head(3)
    for rank, player_name in enumerate(ranked["player_name"].tolist()):
        if player_name in badges_by_player:
            badges_by_player[player_name] = medals[rank]

    output["player_name"] = output["player_name"].map(
        lambda name: f"{name} {badges_by_player.get(name, '')}".strip()
    )
    return output


def top_fielding_rows(df: pd.DataFrame) -> pd.DataFrame:
    return sort_fielding_rows(df).head(10)


def sort_fielding_rows(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    output = df.copy()
    candidates = [
        "fieldingDismissals",
        "dismissals",
        "fieldingTotalCatches",
        "catches",
        "fieldingCatches",
        "stumpings",
        "fieldingStumpings",
        "runOuts",
        "fieldingRunOuts",
    ]
    sort_values = pd.Series([0] * len(output), index=output.index, dtype="float64")

    for column in candidates:
        if column in output:
            sort_values = sort_values + pd.to_numeric(output[column], errors="coerce").fillna(0)

    output["fielding_sort"] = sort_values
    return sort_count_leaders(output, "fielding_sort").drop(columns=["fielding_sort"], errors="ignore")


def top_bowling_figures(df: pd.DataFrame, limit: int = 10) -> pd.DataFrame:
    if df.empty or "bowlingBestInnings" not in df:
        return df.head(0)

    return sort_bowling_by_bbi(df).head(limit)


def sort_bowling_by_bbi(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "bowlingBestInnings" not in df:
        return df

    output = df.copy()
    parsed = output["bowlingBestInnings"].astype(str).str.extract(r"(\d+)\s*[-/]\s*(\d+)")
    output["bbi_wickets_sort"] = pd.to_numeric(parsed[0], errors="coerce").fillna(0)
    output["bbi_runs_sort"] = pd.to_numeric(parsed[1], errors="coerce").fillna(999)
    output = output.sort_values(
        ["bbi_wickets_sort", "bbi_runs_sort"],
        ascending=[False, True],
    )
    return output.drop(columns=["bbi_wickets_sort", "bbi_runs_sort"])


def table_height(df: pd.DataFrame, max_rows: int = 15) -> int:
    visible_rows = min(max(len(df), 1), max_rows)
    return 38 + (visible_rows + 1) * 35


def render_batting_table(
    df: pd.DataFrame,
    source_df: pd.DataFrame | None = None,
    show_team: bool = False,
) -> None:
    source_df = source_df if source_df is not None else df
    df = add_player_medals(
        df,
        source_df,
        "battingAggregate",
        ascending=False,
    )
    columns = [
        "player_name",
        "matches",
        "battingAggregate",
        "balls_faced_display",
        "battingAverage",
        "battingStrikeRate",
        "high_score",
    ]
    if show_team:
        columns.insert(1, "team_name")

    st.dataframe(
        prepare_table_frame(
            df,
            columns,
            {
                "player_name": "Player",
                "team_name": "Team",
                "matches": "M",
                "battingAggregate": "Runs",
                "balls_faced_display": "BF",
                "battingAverage": "Avg",
                "battingStrikeRate": "SR",
                "high_score": "HS",
            },
        ),
        use_container_width=True,
        hide_index=True,
        height=table_height(df, max_rows=10),
        column_config={
            **standard_column_config(),
            "Runs": st.column_config.NumberColumn(format="%d"),
            "BF": st.column_config.NumberColumn(format="%d"),
            "Avg": st.column_config.NumberColumn(format="%.2f"),
            "SR": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def render_bowling_table(
    df: pd.DataFrame,
    source_df: pd.DataFrame | None = None,
    show_team: bool = False,
) -> None:
    source_df = source_df if source_df is not None else df
    df = add_player_medals(
        df,
        source_df,
        "bowlingWickets",
        ascending=False,
    )
    columns = [
        "player_name",
        "matches",
        "bowlingWickets",
        "overs_bowled_display",
        "bowlingAverage",
        "bowlingEconomyRate",
        "bowlingStrikeRate",
        "bowlingBestInnings",
    ]
    if show_team:
        columns.insert(1, "team_name")

    st.dataframe(
        prepare_table_frame(
            df,
            columns,
            {
                "player_name": "Player",
                "team_name": "Team",
                "matches": "M",
                "bowlingWickets": "Wkts",
                "overs_bowled_display": "Overs",
                "bowlingAverage": "Avg",
                "bowlingEconomyRate": "Econ",
                "bowlingStrikeRate": "SR",
                "bowlingBestInnings": "BBI",
            },
        ),
        use_container_width=True,
        hide_index=True,
        height=table_height(df, max_rows=10),
        column_config={
            **standard_column_config(),
            "Wkts": st.column_config.NumberColumn(format="%d"),
            "Overs": st.column_config.TextColumn("Overs"),
            "Avg": st.column_config.NumberColumn(format="%.2f"),
            "Econ": st.column_config.NumberColumn(format="%.2f"),
            "SR": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def render_fielding_table(df, show_team: bool = False) -> None:
    columns = [
        "player_name",
        "matches",
        "catches_display",
        "stumpings_display",
        "run_outs_display",
        "dismissals_display",
    ]
    if show_team:
        columns.insert(1, "team_name")

    st.dataframe(
        prepare_table_frame(
            df,
            columns,
            {
                "player_name": "Player",
                "team_name": "Team",
                "matches": "M",
                "catches_display": "Ct",
                "stumpings_display": "St",
                "run_outs_display": "RO",
                "dismissals_display": "Dis",
            },
        ),
        use_container_width=True,
        hide_index=True,
        height=table_height(df),
        column_config={
            **standard_column_config(),
            "Ct": st.column_config.NumberColumn(format="%d"),
            "St": st.column_config.NumberColumn(format="%d"),
            "RO": st.column_config.NumberColumn(format="%d"),
            "Dis": st.column_config.NumberColumn(format="%d"),
        },
    )


def render_full_stats_table(
    df: pd.DataFrame,
    category: str,
    show_team: bool = False,
) -> None:
    output = build_full_stats_frame(df, category, show_team)
    render_filterable_dataframe(
        output,
        key_prefix=f"full_stats_{category}_{'team' if show_team else 'no_team'}",
        use_container_width=True,
        hide_index=True,
        height=520,
        column_config=numeric_column_config(output.columns.tolist()),
        show_filters=False,
    )


def build_full_stats_frame(
    df: pd.DataFrame,
    category: str,
    show_team: bool,
) -> pd.DataFrame:
    if category == "batting":
        output = get_batting_display_df(df)
    elif category == "bowling":
        output = get_bowling_display_df(df)
    elif category == "fielding":
        output = get_fielding_display_df(df)
    else:
        output = pd.DataFrame()

    if "Team" in output:
        output["Team"] = output["Team"].map(compact_team_label)
        if not show_team:
            output = output.drop(columns=["Team"])
    output = coerce_display_numbers(output)
    if "BBI" in output:
        output["BBI"] = ordered_bbi_values(output["BBI"])

    return output


def get_batting_display_df(df: pd.DataFrame) -> pd.DataFrame:
    return prepare_curated_display_frame(
        df,
        [
            "player_name",
            "team_name",
            "matches",
            "battingInnings",
            "battingAggregate",
            "balls_faced_display",
            "battingAverage",
            "battingStrikeRate",
            "high_score",
            "battingNotOuts",
            "batting50s",
            "batting100s",
            "batting0s",
            "battingFours",
            "battingSixes",
        ],
        [
            "Player",
            "Team",
            "M",
            "Inns",
            "Runs",
            "BF",
            "Bat Avg",
            "Bat SR",
            "HS",
            "NO",
            "50s",
            "100s",
            "0s",
            "4s",
            "6s",
        ],
    )


def get_bowling_display_df(df: pd.DataFrame) -> pd.DataFrame:
    return prepare_curated_display_frame(
        df,
        [
            "player_name",
            "team_name",
            "matches",
            "overs_bowled_display",
            "bowlingWickets",
            "bowlingMaidens",
            "bowlingAverage",
            "bowlingEconomyRate",
            "bowlingStrikeRate",
            "bowlingBestInnings",
            "bowling4Wickets",
            "bowling5WIs",
        ],
        [
            "Player",
            "Team",
            "M",
            "Overs",
            "Wickets",
            "Mdns",
            "Bowl Avg",
            "Economy",
            "Bowl SR",
            "BBI",
            "4W",
            "5W",
        ],
    )


def get_fielding_display_df(df: pd.DataFrame) -> pd.DataFrame:
    return prepare_curated_display_frame(
        df,
        [
            "player_name",
            "team_name",
            "matches",
            "catches_display",
            "stumpings_display",
            "run_outs_display",
            "dismissals_display",
        ],
        [
            "Player",
            "Team",
            "M",
            "Catches",
            "Stumpings",
            "Run Outs",
            "Total Dismissals",
        ],
    )


def prepare_curated_display_frame(
    df: pd.DataFrame,
    columns: list[str],
    display_columns: list[str],
) -> pd.DataFrame:
    output = add_display_stat_aliases(df)
    available_columns = [column for column in columns if column in output.columns]
    output = output[available_columns].rename(columns=pretty_column_name_map())
    return select_display_columns(output, display_columns)


def select_display_columns(df: pd.DataFrame, desired_columns: list[str]) -> pd.DataFrame:
    return df[[column for column in desired_columns if column in df.columns]]


def coerce_display_numbers(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    text_columns = {"Player", "Team", "HS", "BBI", "Overs"}
    for column in output.columns:
        if column not in text_columns:
            numeric_values = pd.to_numeric(output[column], errors="coerce")
            if numeric_values.notna().any():
                output[column] = numeric_values
    return output


def ordered_bbi_values(values: pd.Series) -> pd.Series:
    unique_values = values.dropna().astype(str).drop_duplicates().tolist()
    categories = sorted(
        unique_values,
        key=bbi_sort_key,
    )
    return pd.Series(
        pd.Categorical(values.astype(str), categories=categories, ordered=True),
        index=values.index,
    )


def bbi_sort_key(value: str) -> tuple[int, int]:
    parsed = pd.Series([value]).str.extract(r"(\d+)\s*[-/]\s*(\d+)").iloc[0]
    wickets = pd.to_numeric(parsed[0], errors="coerce")
    runs = pd.to_numeric(parsed[1], errors="coerce")
    if pd.isna(wickets) or pd.isna(runs):
        return (0, -999)
    return (int(wickets), -int(runs))


def pretty_column_name_map() -> dict[str, str]:
    return {
        "player_name": "Player",
        "team_name": "Team",
        "grade_name": "Grade",
        "matches": "M",
        "innings": "Inns",
        "battingInnings": "Inns",
        "battingAggregate": "Runs",
        "balls_faced_display": "BF",
        "ballsFaced": "BF",
        "battingBallsFaced": "BF",
        "battingNotOuts": "NO",
        "batting50s": "50s",
        "batting100s": "100s",
        "batting0s": "0s",
        "battingFours": "4s",
        "battingSixes": "6s",
        "battingMinutes": "Mins",
        "battingAverage": "Bat Avg",
        "battingStrikeRate": "Bat SR",
        "high_score": "HS",
        "battingHighScore": "Raw HS",
        "bowlingWickets": "Wickets",
        "overs_bowled_display": "Overs",
        "oversBowled": "Overs",
        "bowlingOvers": "Overs",
        "overs": "Overs",
        "bowlingAverage": "Bowl Avg",
        "bowlingEconomyRate": "Economy",
        "bowlingStrikeRate": "Bowl SR",
        "bowlingBestInnings": "BBI",
        "bowlingBalls": "Balls",
        "bowlingRuns": "Runs",
        "bowlingMaidens": "Mdns",
        "bowling4Wickets": "4W",
        "bowling5WIs": "5W",
        "bowling10WMs": "10WM",
        "bowlingWides": "Wides",
        "bowlingNoBalls": "NB",
        "catches": "Catches",
        "fieldingCatches": "Catches",
        "fieldingCatchesNonWK": "Ct Non-WK",
        "fieldingCatchesWK": "Ct WK",
        "fieldingTotalCatches": "Catches",
        "catches_display": "Catches",
        "stumpings": "Stumpings",
        "fieldingStumpings": "Stumpings",
        "stumpings_display": "Stumpings",
        "runOuts": "Run Outs",
        "fieldingRunOuts": "Run Outs",
        "fieldingAssistedRunOuts": "Assist RO",
        "fieldingUnassistedRunOuts": "Direct RO",
        "run_outs_display": "Run Outs",
        "fieldingDismissals": "Total Dismissals",
        "dismissals_display": "Total Dismissals",
    }
