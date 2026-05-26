import base64
import html
import math
import os
import re
import subprocess
import textwrap
import time
from urllib.parse import quote, unquote
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.analytics.playcricket_stats import (
    add_batting_display_columns,
    combine_player_rows,
    top_rows,
)
from src.analytics.match_centre_advanced import (
    bowling_phase_splits,
    calculate_batting_splits,
    calculate_best_hidden_performances,
    calculate_bowling_splits,
    calculate_fastest_milestones,
    player_options,
    player_summary,
    prepare_match_centre_frames,
    selected_player_rows,
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
from src.config.club_config import (
    allow_legacy_fallback,
    get_club_name,
    get_club_short_name,
    get_hall_of_fame_path,
    get_mapping_path,
    get_processed_dir,
    get_processed_match_centre_dir,
    get_processed_path,
    get_player_profile_path,
    get_season_overview_path,
    load_club_config,
)
from src.data import player_dna_analytics as player_dna
from src.data import scorebook_lab_analytics as scorebook_lab
from src.data import season_story_analytics as season_story
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
    player_identity_path,
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
    normalize_spaces,
)
from src.utils.analytics import (
    ga4_link_onclick,
    inject_ga4,
    render_analytics_debug_status,
    track_event_once,
    track_page_view,
)


APP_ROOT = Path(__file__).resolve().parents[2]
ICON_ASSET_DIR = APP_ROOT / "assets" / "icons"
DEBUG_BIGGEST_IMPROVERS_PATH = APP_ROOT / "data" / "debug_biggest_improvers.csv"
DEBUG_PLAYER_VS_PEERS_PATH = APP_ROOT / "data" / "debug_player_vs_peers.csv"
MATCH_CENTRE_PROCESSED_ROOT = get_processed_match_centre_dir()
SEASON_OVERVIEW_PROCESSED_ROOT = get_season_overview_path()
SEASON_OVERVIEW_BBB_BATTING_RATES_PATH = SEASON_OVERVIEW_PROCESSED_ROOT / "bbb_batting_rates_by_scope.csv"
SEASON_OVERVIEW_BBB_BOWLING_DOT_RATES_PATH = SEASON_OVERVIEW_PROCESSED_ROOT / "bbb_bowling_dot_rates_by_scope.csv"
SEASON_OVERVIEW_SCORECARD_BATTING_MILESTONES_PATH = SEASON_OVERVIEW_PROCESSED_ROOT / "scorecard_batting_milestones_by_scope.csv"
SEASON_OVERVIEW_SCORECARD_BOWLING_MILESTONES_PATH = SEASON_OVERVIEW_PROCESSED_ROOT / "scorecard_bowling_milestones_by_scope.csv"
SEASON_OVERVIEW_SEASON_BY_ROUND_PATH = SEASON_OVERVIEW_PROCESSED_ROOT / "season_by_round_scorecards.csv"
PLAYER_PROFILE_PROCESSED_ROOT = get_player_profile_path()
PLAYER_PROFILE_PERFORMANCE_BREAKDOWN_PATH = PLAYER_PROFILE_PROCESSED_ROOT / "performance_breakdown_by_dimension.csv"
PLAYER_PROFILE_BATTING_POSITION_PATH = PLAYER_PROFILE_PROCESSED_ROOT / "batting_position_summary.csv"
PLAYER_PROFILE_BOWLING_PHASE_PATH = PLAYER_PROFILE_PROCESSED_ROOT / "bowling_phase_summary.csv"
PLAYER_PROFILE_DISMISSAL_FINGERPRINT_PATH = PLAYER_PROFILE_PROCESSED_ROOT / "dismissal_fingerprint_summary.csv"
PLAYER_PROFILE_RECENT_FORM_BATTING_PATH = PLAYER_PROFILE_PROCESSED_ROOT / "recent_form_batting.csv"
PLAYER_PROFILE_RECENT_FORM_BOWLING_PATH = PLAYER_PROFILE_PROCESSED_ROOT / "recent_form_bowling.csv"
HALL_OF_FAME_FASTEST_BATTING_MILESTONES_PATH = get_hall_of_fame_path("fastest_batting_milestones.csv")
HALL_OF_FAME_SCORECARD_RECORD_LINKS_PATH = get_hall_of_fame_path("scorecard_record_links.csv")
HALL_OF_FAME_PREMIERSHIP_WINS_PATH = get_hall_of_fame_path("premiership_wins.csv")
HALL_OF_FAME_PLAYER_PREMIERSHIPS_PATH = get_hall_of_fame_path("player_premierships.csv")
HALL_OF_FAME_PLAYER_WIN_RATES_PATH = get_hall_of_fame_path("player_win_rates.csv")
HALL_OF_FAME_BBB_BATTING_RATES_PATH = get_hall_of_fame_path("player_bbb_batting_rates.csv")
HALL_OF_FAME_SCORECARD_MILESTONES_PATH = get_hall_of_fame_path("player_scorecard_milestones.csv")
HALL_OF_FAME_BOWLING_MILESTONES_PATH = get_hall_of_fame_path("player_bowling_milestones.csv")
DEBUG_HOF_TIMINGS = os.getenv("FVCC_DEBUG_TIMINGS") == "1"
SHOW_ROUTING_DEBUG = os.getenv("FVCC_SHOW_ROUTING_DEBUG") == "1"
PLAYER_PEERS_RELIABLE_SEASON = "Winter 2025"
SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES = False
SHOW_SEASON_OVERVIEW_V2 = os.getenv("FVCC_SHOW_EXPERIMENTAL") == "1"
SHOW_HALL_OF_FAME_V2 = os.getenv("FVCC_SHOW_EXPERIMENTAL") == "1"
SHOW_PLAYER_PROFILE_V2 = os.getenv("FVCC_SHOW_EXPERIMENTAL") == "1"
FASTEST_MILESTONE_RECORD_LIMIT = 10
PREMIERSHIP_PLAYER_DEFAULT_LIMIT = 6
PREMIERSHIP_PLAYER_EXPANDED_LIMIT = 10
HALL_OF_FAME_DATA_VERSION = "hof-detail-win-season-label-v1"
PLAYER_PROFILE_PAGE_LABEL = "♙ Player Profile"
PLAYER_PROFILE_QUERY_PAGE = "player-profile"
PLAYER_PROFILE_V2_QUERY_PAGE = "player-profile-v2"
SEASON_OVERVIEW_PAGE_LABEL = "⌂ Season Overview"
SEASON_OVERVIEW_QUERY_PAGE = "season-overview"
SEASON_OVERVIEW_V2_QUERY_PAGE = "season-overview-v2"
HALL_OF_FAME_V2_QUERY_PAGE = "hall-of-fame-v2"

BASE_PAGE_DEFINITIONS = (
    ("hall-of-fame", "♕ Hall of Fame", "Hall of Fame"),
    (SEASON_OVERVIEW_QUERY_PAGE, SEASON_OVERVIEW_PAGE_LABEL, "Season Overview"),
    ("milestone", "☆ Milestone", "Milestone"),
    (PLAYER_PROFILE_QUERY_PAGE, PLAYER_PROFILE_PAGE_LABEL, "Player Profile"),
)
EXPERIMENTAL_PAGE_DEFINITIONS = (
    ("match-insights", "▦ Match Insights", "Match Insights"),
    ("advanced-analytics", "◈ Advanced Analytics", "Advanced Analytics"),
    ("player-dna", "◇ Player DNA", "Player DNA"),
    ("scorebook-lab", "▣ Scorebook Lab", "Scorebook Lab"),
)
SEASON_OVERVIEW_V2_PAGE_DEFINITIONS = (
    (SEASON_OVERVIEW_V2_QUERY_PAGE, "✦ Season Overview v2", "Season Overview v2"),
)
HALL_OF_FAME_V2_PAGE_DEFINITIONS = (
    (HALL_OF_FAME_V2_QUERY_PAGE, "♛ Hall of Fame v2", "Hall of Fame v2"),
)
PLAYER_PROFILE_V2_PAGE_DEFINITIONS = (
    (PLAYER_PROFILE_V2_QUERY_PAGE, "♙ Player Profile v2", "Player Profile v2"),
)
LEGACY_PAGE_SLUGS = {
    "season_overview": SEASON_OVERVIEW_QUERY_PAGE,
}


def log_hof_timing(label: str, started_at: float) -> None:
    if DEBUG_HOF_TIMINGS:
        print(f"[hall-of-fame] {label}: {(time.perf_counter() - started_at) * 1000:.1f} ms")


def get_page_definitions() -> tuple[tuple[str, str, str], ...]:
    definitions = list(BASE_PAGE_DEFINITIONS)
    if SHOW_HALL_OF_FAME_V2:
        definitions.extend(HALL_OF_FAME_V2_PAGE_DEFINITIONS)
    if SHOW_SEASON_OVERVIEW_V2:
        definitions.extend(SEASON_OVERVIEW_V2_PAGE_DEFINITIONS)
    if SHOW_PLAYER_PROFILE_V2:
        definitions.extend(PLAYER_PROFILE_V2_PAGE_DEFINITIONS)
    if SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES:
        definitions.extend(EXPERIMENTAL_PAGE_DEFINITIONS)
    return tuple(definitions)


def page_label_by_slug() -> dict[str, str]:
    return {slug: label for slug, label, _ in get_page_definitions()}


def page_title_by_slug() -> dict[str, str]:
    return {slug: title for slug, _, title in get_page_definitions()}


def canonical_page_slug(value: object) -> str:
    slug = str(value or "").strip().casefold()
    return LEGACY_PAGE_SLUGS.get(slug, slug)


def default_page_slug() -> str:
    return BASE_PAGE_DEFINITIONS[0][0]


def valid_page_slugs() -> set[str]:
    return set(page_label_by_slug())


def page_label_for_slug(slug: str) -> str:
    labels = page_label_by_slug()
    return labels.get(slug, labels[default_page_slug()])


def page_title_for_slug(slug: str) -> str:
    titles = page_title_by_slug()
    return titles.get(slug, titles[default_page_slug()])


def page_slug_from_query() -> str:
    requested_page = canonical_page_slug(query_param_value("page"))
    requested_player = unquote(query_param_value("player") or query_param_value("player_id"))
    requested_season = unquote(query_param_value("season"))
    requested_slug = requested_page
    if not requested_slug and requested_player:
        requested_slug = PLAYER_PROFILE_QUERY_PAGE
    elif not requested_slug and requested_season:
        requested_slug = SEASON_OVERVIEW_QUERY_PAGE
    if requested_slug not in valid_page_slugs():
        requested_slug = default_page_slug()
    return requested_slug


def query_param_value(name: str) -> str:
    value = st.query_params.get(name, "")
    if isinstance(value, list):
        value = value[0] if value else ""
    return str(value).strip()


def configured_club_label_html(class_name: str = "club-label") -> str:
    return f'<div class="{html.escape(class_name)}">{html.escape(get_club_name())}</div>'


def configured_club_short_name() -> str:
    return get_club_short_name()


def configured_club_shield_text() -> str:
    short_name = configured_club_short_name()
    return short_name[:2].upper() if short_name else "FV"


def configured_contact() -> dict[str, object]:
    contact = load_club_config().get("contact", {})
    return contact if isinstance(contact, dict) else {}


def configured_creator_names(separator: str = " | ") -> str:
    creators = configured_contact().get("creators", [])
    if not isinstance(creators, list):
        creators = []
    cleaned = [str(name).strip() for name in creators if str(name).strip()]
    return separator.join(cleaned) if cleaned else "Siddhanth Chaurasiya | Preet Kaur"


def configured_creator_names_html(separator: str = " |<br>") -> str:
    creators = configured_contact().get("creators", [])
    if not isinstance(creators, list):
        creators = []
    cleaned = [str(name).strip() for name in creators if str(name).strip()]
    if not cleaned:
        cleaned = ["Siddhanth Chaurasiya", "Preet Kaur"]
    return separator.join(html.escape(name) for name in cleaned)


def configured_feedback_email() -> str:
    email = str(configured_contact().get("feedback_email", "")).strip()
    return email or "siddhanthchaurasiya@gmail.com"


def configured_feedback_email_html() -> str:
    return html.escape(configured_feedback_email()).replace("@", "<br>@")


def resolve_current_page_from_query() -> str:
    current_page = page_slug_from_query()
    st.session_state["current_page"] = current_page
    if query_param_value("page") != current_page:
        # Root URL without page param must initialize to hall-of-fame and sync query params.
        st.query_params["page"] = current_page
    return current_page


def nav_href(slug: str) -> str:
    return f"?page={quote(slug, safe='')}"


def render_sidebar_nav_link(label: str, slug: str, current_page: str) -> str:
    icon, text = label.split(" ", 1) if " " in label else ("", label)
    active_class = " active" if slug == current_page else ""
    return (
        f'<a class="side-nav-item{active_class}" href="{html.escape(nav_href(slug), quote=True)}" target="_self">'
        f'<span>{html.escape(icon)}</span>{html.escape(text)}</a>'
    )


def render_mobile_nav_link(label: str, slug: str, current_page: str) -> str:
    active_class = " active" if slug == current_page else ""
    return (
        f'<a class="mobile-nav-link{active_class}" href="{html.escape(nav_href(slug), quote=True)}" target="_self">'
        f"{html.escape(label)}</a>"
    )


def player_profile_url(player_id: object, player_name: object | None = None) -> str:
    player_id_text = str(player_id or "").strip()
    player_name_text = str(player_name or "").strip()
    if player_id_text:
        url = f"?page={PLAYER_PROFILE_QUERY_PAGE}&player_id={quote(player_id_text, safe='')}"
    elif player_name_text:
        url = f"?page={PLAYER_PROFILE_QUERY_PAGE}&player={quote(player_name_text, safe='')}"
    else:
        return ""
    if player_name_text:
        url = f"{url}#{player_name_text}"
    return url


def player_profile_link_html(player_id: object, player_name: object, class_name: str = "player-profile-link") -> str:
    player_name_text = str(player_name or "-")
    url = player_profile_url(player_id, player_name_text)
    if not url:
        return html.escape(player_name_text)
    return (
        f'<a class="{html.escape(class_name)}" href="{html.escape(url, quote=True)}" '
        f'target="_self" title="Open Player Profile for {html.escape(player_name_text, quote=True)}">'
        f"{html.escape(player_name_text)}</a>"
    )


def season_overview_url(season: object) -> str:
    season_text = safe_season_label(season)
    if not season_text:
        return ""
    return f"?page={SEASON_OVERVIEW_QUERY_PAGE}&season={quote(season_text, safe='')}#{season_text}"


def season_overview_link_html(season: object, class_name: str = "season-overview-link") -> str:
    season_text = safe_season_label(season)
    url = season_overview_url(season_text)
    if not url:
        return html.escape(str(season or ""))
    return (
        f'<a class="{html.escape(class_name)}" href="{html.escape(url, quote=True)}" '
        f'target="_self" title="Open Season Overview for {html.escape(season_text, quote=True)}">'
        f"{html.escape(season_text)}</a>"
    )


def playcricket_scorecard_url(match_id: object) -> str:
    match_id_text = str(match_id or "").strip()
    if not match_id_text or match_id_text.casefold() in {"nan", "none", "nat"}:
        return ""
    return f"https://play.cricket.com.au/match/{quote(match_id_text, safe='')}?tab=scorecard"


def scorecard_link_html(
    match_id: object,
    label: str = "View scorecard ↗",
    class_name: str = "scorecard-link",
    *,
    page_slug: str | None = None,
    section_name: str = "scorecard",
) -> str:
    url = playcricket_scorecard_url(match_id)
    if not url:
        return ""
    match_id_text = str(match_id or "").strip()
    onclick = ga4_link_onclick(
        "playcricket_scorecard_click",
        {
            "page_slug": page_slug or page_slug_from_query(),
            "match_id": match_id_text,
            "section_name": section_name,
        },
    )
    return (
        f'<a class="{html.escape(class_name)}" href="{html.escape(url, quote=True)}" '
        'target="_blank" rel="noopener noreferrer" '
        f'{onclick} '
        f'title="Open PlayCricket scorecard">{html.escape(label)}</a>'
    )


def scorecard_url_link_html(
    url: object,
    match_id: object = "",
    label: str = "View scorecard",
    class_name: str = "scorecard-link",
    *,
    page_slug: str | None = None,
    section_name: str = "scorecard",
) -> str:
    url_text = safe_record_text(url)
    if not url_text or not url_text.startswith("https://play.cricket.com.au/match/"):
        return scorecard_link_html(
            match_id,
            label=label,
            class_name=class_name,
            page_slug=page_slug,
            section_name=section_name,
        )
    match_id_text = safe_record_text(match_id)
    onclick = ga4_link_onclick(
        "playcricket_scorecard_click",
        {
            "page_slug": page_slug or page_slug_from_query(),
            "match_id": match_id_text,
            "section_name": section_name,
        },
    )
    return (
        f'<a class="{html.escape(class_name)}" href="{html.escape(url_text, quote=True)}" '
        'target="_blank" rel="noopener noreferrer" '
        f'{onclick} '
        f'title="Open PlayCricket scorecard">{html.escape(label)}</a>'
    )


def resolve_player_profile_selector_value(value: object) -> str:
    text = str(value or "").strip()
    if not text or text == "Select a player...":
        return ""
    valid_ids = set(st.session_state.get("player_profile_valid_ids", []))
    if text in valid_ids:
        return text
    name_to_id = st.session_state.get("player_profile_name_to_id", {})
    return str(name_to_id.get(text, "") or "").strip()


def resolve_player_query_to_id(player_names_by_id: dict[str, str]) -> str:
    query_player_id = unquote(query_param_value("player_id"))
    if query_player_id in player_names_by_id:
        return query_player_id

    query_player = unquote(query_param_value("player"))
    if query_player in player_names_by_id:
        return query_player
    if not query_player:
        return ""

    target_name = query_player.strip().casefold()
    matches = [
        player_id
        for player_id, player_name in player_names_by_id.items()
        if str(player_name).strip().casefold() == target_name
    ]
    return matches[0] if len(matches) == 1 else ""


def current_player_query_token() -> str:
    return query_param_value("player_id") or query_param_value("player")


def analytics_player_slug(player_name: object, fallback_id: object = "") -> str:
    source = str(player_name or fallback_id or "").strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", source)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "unknown-player"


def sync_player_profile_query(player_id: object, page_slug: str = PLAYER_PROFILE_QUERY_PAGE) -> None:
    player_id_text = str(player_id or "").strip()
    st.query_params["page"] = page_slug
    if player_id_text:
        st.query_params["player_id"] = player_id_text
        st.query_params.pop("player", None)


def safe_season_label(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "nat", "—"}:
        return ""
    return text


def player_id_from_row(row: pd.Series | dict[str, object]) -> str:
    for column in ["canonical_player_id", "player_key", "player_id"]:
        value = row.get(column, "") if hasattr(row, "get") else ""
        value = str(value or "").strip()
        if value:
            return value
    return ""


def profile_link_display_pattern() -> str:
    return r"#(.+)$"


def overview_link_display_pattern() -> str:
    return r"#(.+)$"


def link_player_column(table: pd.DataFrame, id_column: str = "canonical_player_id") -> pd.DataFrame:
    if table.empty or "Player" not in table or id_column not in table:
        return table
    output = table.copy()
    output["Player"] = [
        player_profile_url(player_id, player)
        for player_id, player in zip(output[id_column], output["Player"])
    ]
    return output.drop(columns=[id_column], errors="ignore")


def link_season_columns(table: pd.DataFrame, columns: list[str] | None = None) -> pd.DataFrame:
    if table.empty:
        return table
    output = table.copy()
    for column in columns or ["Season", "Debut Season", "Latest Season"]:
        if column in output:
            output[column] = output[column].map(lambda value: season_overview_url(value) or value)
    return output


def add_missing_canonical_player_ids(table: pd.DataFrame) -> pd.DataFrame:
    if table.empty or "canonical_player_id" in table:
        return table
    name_column = "canonical_player_name" if "canonical_player_name" in table else "player_name"
    if name_column not in table:
        return table
    output = table.copy()
    if "player_name" not in output:
        output["player_name"] = output[name_column]
    if "raw_player_id" not in output:
        if "participant_id" in output:
            output["raw_player_id"] = output["participant_id"]
        elif "player_id" in output:
            output["raw_player_id"] = output["player_id"]
    if "raw_player_name" not in output:
        output["raw_player_name"] = output[name_column]
    output = apply_player_identity_mapping(output, load_player_aliases())
    return output


@st.cache_data(show_spinner=False)
def app_build_commit() -> str:
    for env_name in ("STREAMLIT_GIT_COMMIT", "COMMIT_SHA", "GIT_COMMIT", "SOURCE_VERSION"):
        value = str(os.getenv(env_name, "") or "").strip()
        if value:
            return value[:7]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=APP_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return "unknown"
    return result.stdout.strip() or "unknown"


def render_routing_debug_line() -> None:
    if not SHOW_ROUTING_DEBUG:
        return
    st.sidebar.markdown(
        f"""
        <div class="routing-debug">
            Build: {html.escape(app_build_commit())}<br>
            current_page: {html.escape(str(st.session_state.get("current_page", "")))}<br>
            query page: {html.escape(query_param_value("page") or "-")}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_page() -> None:
    """Render the dashboard."""
    inject_theme()
    inject_ga4()
    selected_page = render_sidebar()
    track_page_view(selected_page, page_title_for_slug(selected_page))
    if selected_page == "hall-of-fame":
        render_hall_of_fame_page()
    elif SHOW_HALL_OF_FAME_V2 and selected_page == HALL_OF_FAME_V2_QUERY_PAGE:
        render_hall_of_fame_v2_page()
    elif selected_page == SEASON_OVERVIEW_QUERY_PAGE:
        dashboard_data = render_data_source_panel()
        render_overview(dashboard_data)
    elif SHOW_SEASON_OVERVIEW_V2 and selected_page == SEASON_OVERVIEW_V2_QUERY_PAGE:
        dashboard_data = render_data_source_panel(
            page_slug=SEASON_OVERVIEW_V2_QUERY_PAGE,
            page_marker_class="season-v2-page",
            header_title="Season Overview v2 ✨",
            header_description="A premium season story built from scorecards, records and match-centre insights.",
        )
        render_season_overview_v2(dashboard_data)
    elif selected_page == "milestone":
        render_approaching_milestones_page()
    elif selected_page == PLAYER_PROFILE_QUERY_PAGE:
        render_player_profile_page()
    elif SHOW_PLAYER_PROFILE_V2 and selected_page == PLAYER_PROFILE_V2_QUERY_PAGE:
        render_player_profile_v2_page()
    elif SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES and selected_page == "match-insights":
        render_match_centre_page()
    elif SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES and selected_page == "advanced-analytics":
        render_advanced_analytics_page()
    elif SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES and selected_page == "player-dna":
        render_player_dna_page()
    elif SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES and selected_page == "scorebook-lab":
        render_scorebook_lab_page()
    else:
        render_hall_of_fame_page()
    render_mobile_page_footer()


def render_sidebar() -> str:
    page_definitions = get_page_definitions()
    current_page = resolve_current_page_from_query()
    mobile_links = "".join(
        render_mobile_nav_link(label, slug, current_page)
        for slug, label, _ in page_definitions
    )
    help_text_by_slug = {
        "hall-of-fame": ("Hall of Fame 🏆", "All-time club records, leaders, and iconic performances."),
        HALL_OF_FAME_V2_QUERY_PAGE: (
            "Hall of Fame v2 🏛️",
            "Hidden preview for a museum-style club record book and premium Hall of Fame redesign.",
        ),
        SEASON_OVERVIEW_QUERY_PAGE: (
            "Season Overview 🧭",
            "Season stats, team leaders, and detailed batting/bowling/fielding tables.",
        ),
        SEASON_OVERVIEW_V2_QUERY_PAGE: (
            "Season Overview v2 ✨",
            "Hidden preview for season stories, awards, pulse cards, and role maps.",
        ),
        "milestone": ("Milestone 💪", "Active players closing in on major club milestones."),
        PLAYER_PROFILE_QUERY_PAGE: ("Player Profile 🏏", "Search any player and view their career record."),
        PLAYER_PROFILE_V2_QUERY_PAGE: (
            "Player Profile v2 🧬",
            "Hidden preview for a scouting-card style player profile with coach-focused insights.",
        ),
        "match-insights": ("Match Insights", "Scorebook-only analysis from reviewed match-centre refresh outputs."),
        "advanced-analytics": ("Advanced Analytics", "Player-level splits powered by match-centre scorecards and ball-by-ball data."),
        "player-dna": ("Player DNA", "Experimental player identity cards, traits, and hidden impact patterns."),
        "scorebook-lab": ("Scorebook Lab", "Experimental hidden records, matchup stories, MVP cards, and partnership insights."),
    }
    mobile_help_items = []
    for slug, _, _ in page_definitions:
        title, description = help_text_by_slug.get(slug, (page_title_for_slug(slug), ""))
        if description:
            mobile_help_items.append(
                f"<p><strong>{html.escape(title)}</strong><br>{html.escape(description)}</p>"
            )
    mobile_help_html = "".join(mobile_help_items)

    with st.container(key="mobile_nav_fallback"):
        st.markdown(
            f"""
            <details class="mobile-nav-help">
                <summary>
                    <span class="mobile-nav-label">Choose a page</span>
                    <span class="mobile-info-icon">ⓘ</span>
                </summary>
                <div class="mobile-nav-help-panel">
                    {mobile_help_html}
                </div>
            </details>
            <div class="mobile-nav-links">
                {mobile_links}
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.sidebar.markdown(
        f"""
        <div class="side-brand">
            <div class="side-shield">{html.escape(configured_club_shield_text())}</div>
            <div>
                <div class="side-title">{html.escape(configured_club_short_name())}</div>
                <div class="side-subtitle">Stats Hub</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    nav_links = "".join(
        render_sidebar_nav_link(label, slug, current_page)
        for slug, label, _ in page_definitions
    )
    st.sidebar.markdown(f'<nav class="side-nav">{nav_links}</nav>', unsafe_allow_html=True)
    st.sidebar.markdown(
        f"""
        <div class="side-footer">
            <div class="side-footer-label">App created by</div>
            <div class="side-footer-names">{configured_creator_names_html()}</div>
            <div class="side-footer-contact">
                <div>For feedback/enquiries:</div>
                <a href="mailto:{html.escape(configured_feedback_email())}">{configured_feedback_email_html()}</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_routing_debug_line()
    render_analytics_debug_status()
    return current_page


def render_mobile_page_footer() -> None:
    st.markdown(
        f"""
        <div class="mobile-page-footer">
            <div class="mobile-footer-label">App created by</div>
            <div class="mobile-footer-names">{configured_creator_names_html()}</div>
            <div class="mobile-footer-contact">
                <div>For feedback/enquiries:</div>
                <a href="mailto:{html.escape(configured_feedback_email())}">{configured_feedback_email_html()}</a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_analytics_debug_status(sidebar=False)


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


def render_data_source_panel(
    page_slug: str = SEASON_OVERVIEW_QUERY_PAGE,
    page_marker_class: str = "seasons-page",
    header_title: str = "Season Overview 🧭",
    header_description: str = "Track team performance, player leaders, and season-by-season club trends.",
) -> dict[str, object] | None:
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
    selected_season_key = "season_overview_selected_season"
    requested_season_name = (
        str(st.session_state.pop("pending_season_overview_name", "") or "").strip()
        or unquote(query_param_value("season"))
    )
    requested_season_id = query_param_value("season_id")
    requested_index = next(
        (
            index
            for index, season in enumerate(seasons)
            if (
                requested_season_id
                and str(season.get("id", "")).strip() == requested_season_id
            )
            or (
                requested_season_name
                and str(season.get("name", "")).strip().casefold() == requested_season_name.casefold()
            )
        ),
        None,
    )
    if requested_index is not None:
        current_season_index = requested_index
        requested_token = f"{seasons[requested_index].get('id', '')}|{seasons[requested_index].get('name', '')}"
        if st.session_state.get("season_overview_requested_token") != requested_token:
            st.session_state[selected_season_key] = seasons[requested_index]
            st.session_state["season_overview_requested_token"] = requested_token
    elif not requested_season_name and not requested_season_id:
        current = seasons[current_season_index]
        current_token = f"{current.get('id', '')}|{current.get('name', '')}"
        if st.session_state.get("season_overview_requested_token") != current_token:
            st.session_state[selected_season_key] = current
            st.session_state["season_overview_requested_token"] = current_token

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
                key=selected_season_key,
            )
            selected_season_name_for_url = str(selected_season.get("name", "") or "").strip()
            if selected_season_name_for_url and query_param_value("season") != selected_season_name_for_url:
                st.query_params["season"] = selected_season_name_for_url
            selected_token = f"{selected_season.get('id', '')}|{selected_season.get('name', '')}"
            st.session_state["season_overview_requested_token"] = selected_token

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
        selected_season_name = str(selected_season.get("name", "") or "")
        selected_team_label = format_team_option(selected_team)
        selected_team_id = str(selected_team.get("id", "") or "")
        selected_grade_id = str(grade.get("id", "") or "")
        track_event_once(
            "season_filter_change",
            {
                "page_slug": page_slug,
                "selected_season": selected_season_name,
                "selected_team": selected_team_label,
            },
            key=f"{page_slug}:season-filter:{selected_season.get('id')}",
        )
        track_event_once(
            "team_filter_change",
            {
                "page_slug": page_slug,
                "selected_season": selected_season_name,
                "selected_team": selected_team_label,
            },
            key=f"{page_slug}:team-filter:{selected_season.get('id')}:{selected_team_id}:{selected_grade_id}",
        )

    with st.container(key="header_intro"):
        st.markdown(
            f"""
            <div class="{html.escape(page_marker_class)}"></div>
            <h1 class="page-title">{html.escape(header_title)}</h1>
            {configured_club_label_html()}
            <div class="page-subtitle">{html.escape(header_description)}</div>
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

    dashboard_frames = add_season_overview_detail_metrics(
        dashboard_frames,
        selected_season,
        teams if is_all_teams else [selected_team],
    )

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
        "page_slug": page_slug,
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


def season_overview_detail_source_signature() -> tuple[tuple[str, float], ...]:
    paths = [
        SEASON_OVERVIEW_BBB_BATTING_RATES_PATH,
        SEASON_OVERVIEW_BBB_BOWLING_DOT_RATES_PATH,
        SEASON_OVERVIEW_SCORECARD_BATTING_MILESTONES_PATH,
        SEASON_OVERVIEW_SCORECARD_BOWLING_MILESTONES_PATH,
        SEASON_OVERVIEW_SEASON_BY_ROUND_PATH,
    ]
    return tuple((str(path), path.stat().st_mtime) for path in paths if path.exists())


@st.cache_data(show_spinner=False)
def load_season_overview_detail_sources(signature: tuple[tuple[str, float], ...]) -> dict[str, pd.DataFrame]:
    return {
        "bbb_batting": read_match_centre_csv(SEASON_OVERVIEW_BBB_BATTING_RATES_PATH),
        "bbb_bowling": read_match_centre_csv(SEASON_OVERVIEW_BBB_BOWLING_DOT_RATES_PATH),
        "scorecard_batting": read_match_centre_csv(SEASON_OVERVIEW_SCORECARD_BATTING_MILESTONES_PATH),
        "scorecard_bowling": read_match_centre_csv(SEASON_OVERVIEW_SCORECARD_BOWLING_MILESTONES_PATH),
        "season_by_round": read_match_centre_csv(SEASON_OVERVIEW_SEASON_BY_ROUND_PATH),
    }


def add_season_overview_detail_metrics(
    frames: dict[str, pd.DataFrame],
    selected_season: dict,
    teams: list[dict],
) -> dict[str, pd.DataFrame]:
    output = {key: value.copy() if isinstance(value, pd.DataFrame) else value for key, value in frames.items()}
    sources = load_season_overview_detail_sources(season_overview_detail_source_signature())
    team_ids = {str(team.get("id", "")) for team in teams if str(team.get("id", "")).strip()}
    season_id = str(selected_season.get("id", "") or "")
    season_name = str(selected_season.get("name", "") or "")

    batting = output.get("batting", pd.DataFrame()).copy()
    if not batting.empty:
        batting = merge_player_metric_frame(
            batting,
            scoped_bbb_batting_rates(sources.get("bbb_batting", pd.DataFrame()), season_id, season_name, team_ids),
        )
        batting = merge_player_metric_frame(
            batting,
            scoped_scorecard_batting_counts(sources.get("scorecard_batting", pd.DataFrame()), season_id, season_name, team_ids),
        )
        output["batting"] = batting

    bowling = output.get("bowling", pd.DataFrame()).copy()
    if not bowling.empty:
        bowling = merge_player_metric_frame(
            bowling,
            scoped_bbb_bowling_dot_rates(sources.get("bbb_bowling", pd.DataFrame()), season_id, season_name, team_ids),
        )
        bowling = merge_player_metric_frame(
            bowling,
            scoped_scorecard_bowling_counts(sources.get("scorecard_bowling", pd.DataFrame()), season_id, season_name, team_ids),
        )
        output["bowling"] = bowling
    return output


def scoped_source_rows(frame: pd.DataFrame, season_id: str, season_name: str, team_ids: set[str]) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    output = frame.copy()
    if season_id and "season_id" in output:
        output = output[output["season_id"].astype(str) == season_id]
    elif season_name and "season" in output:
        output = output[output["season"].astype(str).str.casefold() == season_name.casefold()]
    if team_ids and "team_id" in output:
        output = output[output["team_id"].astype(str).isin(team_ids)]
    return output.copy()


def scoped_bbb_batting_rates(frame: pd.DataFrame, season_id: str, season_name: str, team_ids: set[str]) -> pd.DataFrame:
    rows = scoped_source_rows(frame, season_id, season_name, team_ids)
    if rows.empty:
        return pd.DataFrame(columns=["player_key", "seasonDetailBatSR", "seasonDetailBatDotBallPct"])
    has_dot_ball_source = "bbb_dot_balls" in rows
    for column in ["bbb_runs", "bbb_balls_faced"]:
        if column not in rows:
            rows[column] = 0
        rows[column] = pd.to_numeric(rows[column], errors="coerce").fillna(0)
    if has_dot_ball_source:
        rows["bbb_dot_balls"] = pd.to_numeric(rows["bbb_dot_balls"], errors="coerce").fillna(0)
        dot_denominator_column = "bbb_dot_ball_balls_faced" if "bbb_dot_ball_balls_faced" in rows else "bbb_balls_faced"
        rows[dot_denominator_column] = pd.to_numeric(rows[dot_denominator_column], errors="coerce").fillna(0)
    else:
        rows["bbb_dot_balls"] = pd.NA
        dot_denominator_column = "bbb_balls_faced"
    grouped = rows.groupby("player_key", as_index=False).agg(
        seasonDetailBatRuns=("bbb_runs", "sum"),
        seasonDetailBatBalls=("bbb_balls_faced", "sum"),
        seasonDetailBatDotBalls=("bbb_dot_balls", "sum"),
        seasonDetailBatDotBallBalls=(dot_denominator_column, "sum"),
    )
    grouped["seasonDetailBatSR"] = grouped.apply(
        lambda row: divide_or_none(float(row["seasonDetailBatRuns"]) * 100, float(row["seasonDetailBatBalls"])),
        axis=1,
    )
    if has_dot_ball_source:
        grouped["seasonDetailBatDotBallPct"] = grouped.apply(
            lambda row: divide_or_none(float(row["seasonDetailBatDotBalls"]) * 100, float(row["seasonDetailBatDotBallBalls"])),
            axis=1,
        )
    else:
        grouped["seasonDetailBatDotBallPct"] = pd.NA
    return grouped[["player_key", "seasonDetailBatSR", "seasonDetailBatDotBallPct"]]


def scoped_scorecard_batting_counts(frame: pd.DataFrame, season_id: str, season_name: str, team_ids: set[str]) -> pd.DataFrame:
    rows = scoped_source_rows(frame, season_id, season_name, team_ids)
    if rows.empty:
        return pd.DataFrame(columns=["player_key", "seasonDetail30s"])
    rows["thirties"] = pd.to_numeric(rows.get("thirties"), errors="coerce").fillna(0)
    grouped = rows.groupby("player_key", as_index=False).agg(seasonDetail30s=("thirties", "sum"))
    grouped["seasonDetail30s"] = pd.to_numeric(grouped["seasonDetail30s"], errors="coerce").fillna(0).astype(int)
    return grouped


def scoped_bbb_bowling_dot_rates(frame: pd.DataFrame, season_id: str, season_name: str, team_ids: set[str]) -> pd.DataFrame:
    rows = scoped_source_rows(frame, season_id, season_name, team_ids)
    if rows.empty:
        return pd.DataFrame(columns=["player_key", "seasonDetailDotBallPct"])
    for column in ["dot_balls", "legal_balls"]:
        rows[column] = pd.to_numeric(rows.get(column), errors="coerce").fillna(0)
    grouped = rows.groupby("player_key", as_index=False).agg(
        seasonDetailDotBalls=("dot_balls", "sum"),
        seasonDetailLegalBalls=("legal_balls", "sum"),
    )
    grouped["seasonDetailDotBallPct"] = grouped.apply(
        lambda row: divide_or_none(float(row["seasonDetailDotBalls"]) * 100, float(row["seasonDetailLegalBalls"])),
        axis=1,
    )
    return grouped[["player_key", "seasonDetailDotBallPct"]]


def scoped_scorecard_bowling_counts(frame: pd.DataFrame, season_id: str, season_name: str, team_ids: set[str]) -> pd.DataFrame:
    rows = scoped_source_rows(frame, season_id, season_name, team_ids)
    if rows.empty:
        return pd.DataFrame(columns=["player_key", "seasonDetail3WIs", "seasonDetail5WIs"])
    for column in ["three_wicket_innings", "five_wicket_innings"]:
        rows[column] = pd.to_numeric(rows.get(column), errors="coerce").fillna(0)
    grouped = rows.groupby("player_key", as_index=False).agg(
        seasonDetail3WIs=("three_wicket_innings", "sum"),
        seasonDetail5WIs=("five_wicket_innings", "sum"),
    )
    for column in ["seasonDetail3WIs", "seasonDetail5WIs"]:
        grouped[column] = pd.to_numeric(grouped[column], errors="coerce").fillna(0).astype(int)
    return grouped


def merge_player_metric_frame(base: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    if base.empty or metrics.empty or "player_key" not in metrics:
        return base
    output = base.copy()
    output["player_key"] = player_keys(add_missing_canonical_player_ids(output))
    output = output.merge(metrics, on="player_key", how="left")
    return output.drop(columns=["player_key"], errors="ignore")


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

    render_season_by_round(dashboard_data)
    render_overall_section(dashboard_data)
    render_team_specific_leaders(dashboard_data)
    render_full_stats_section(dashboard_data)


def all_available_match_centre_scope() -> Path:
    return MATCH_CENTRE_PROCESSED_ROOT / "all_available"


def all_available_match_centre_signature() -> tuple[tuple[str, float], ...]:
    return match_centre_scope_signature(all_available_match_centre_scope())


@st.cache_data(show_spinner=False)
def load_all_available_match_centre_sources(
    _signature: tuple[tuple[str, float], ...],
    _identity_version: float | None = None,
) -> dict[str, pd.DataFrame]:
    scope = all_available_match_centre_scope()
    if not scope.exists():
        return {"matches": pd.DataFrame(), "batting": pd.DataFrame(), "bowling": pd.DataFrame()}
    matches = read_match_centre_csv(scope / "all_matches.csv")
    batting = read_match_centre_csv(scope / "all_scorecard_batting.csv")
    bowling = read_match_centre_csv(scope / "all_scorecard_bowling.csv")
    if not matches.empty:
        matches = build_match_archive_frame(matches)
    if not batting.empty:
        batting = add_missing_canonical_player_ids(batting)
    if not bowling.empty:
        bowling = add_missing_canonical_player_ids(bowling)
    return {"matches": matches, "batting": batting, "bowling": bowling}


def match_centre_sources_for_scorecards() -> dict[str, pd.DataFrame]:
    return load_all_available_match_centre_sources(
        all_available_match_centre_signature(),
        player_aliases_mtime(),
    )


def render_season_by_round(dashboard_data: dict[str, object]) -> None:
    render_section_heading("Season by Round 🗓️")
    sources = load_season_overview_detail_sources(season_overview_detail_source_signature())
    rows = build_season_round_rows(dashboard_data, sources.get("season_by_round", pd.DataFrame()))
    options = season_round_grade_options(dashboard_data, rows)
    selected_slug = options[0][0] if options else ""
    if len(options) > 1:
        selected_slug = selected_season_round_grade_filter(options, dashboard_data)

    with st.container(key="season_by_round_card"):
        if not options:
            render_season_round_empty_state()
            return

        visible_rows = [row for row in rows if row.get("grade_slug") == selected_slug]
        if not visible_rows:
            render_season_round_empty_state("Round-by-round scorecards are not available for this grade yet.")
            return
        st.markdown(season_round_cards_html(visible_rows), unsafe_allow_html=True)


def render_season_round_empty_state(message: str = "Round-by-round scorecards are not available for this season yet.") -> None:
    st.markdown(
        f'<div class="season-round-empty">{html.escape(message)}</div>',
        unsafe_allow_html=True,
    )


def selected_season_round_grade_filter(
    options: list[tuple[str, str]],
    dashboard_data: dict[str, object],
) -> str:
    season_id = re.sub(r"[^a-zA-Z0-9_]+", "_", str(dashboard_data.get("season", {}).get("id", "season") or "season"))
    scope_id = "all" if dashboard_data.get("is_all_teams") else str(dashboard_data.get("team", {}).get("id", "team") or "team")
    scope_id = re.sub(r"[^a-zA-Z0-9_]+", "_", scope_id)
    key = f"season_round_grade_filter_{season_id}_{scope_id}"
    valid = [slug for slug, _label in options]
    if key not in st.session_state or st.session_state.get(key) not in valid:
        st.session_state[key] = valid[0]
    selected = render_folder_tab_widget(
        "Season by Round grade",
        options,
        key=key,
        control_key="season_round_grade_folder_tabs",
    )
    selected_slug = str(selected or st.session_state.get(key) or valid[0])
    if selected_slug not in valid:
        selected_slug = valid[0]
        st.session_state[key] = selected_slug
    return selected_slug


def build_season_round_rows(
    dashboard_data: dict[str, object],
    source: pd.DataFrame,
) -> list[dict[str, object]]:
    rows_frame = source.copy()
    if rows_frame.empty:
        return []
    season = dashboard_data.get("season", {}) or {}
    season_id = str(season.get("id", "") or "").strip()
    season_name = str(season.get("name", "") or "").strip()
    if season_id and "season_id" in rows_frame:
        rows_frame = rows_frame[rows_frame["season_id"].astype(str) == season_id].copy()
    elif season_name and "season" in rows_frame:
        rows_frame = rows_frame[rows_frame["season"].astype(str).str.casefold() == season_name.casefold()].copy()
    if rows_frame.empty:
        return []

    team_ids = {
        str(team.get("id", "") or "").strip()
        for team in dashboard_data.get("teams", []) or []
        if str(team.get("id", "") or "").strip()
    }
    if team_ids:
        scope_mask = pd.Series(False, index=rows_frame.index)
        if "fvcc_team_id" in rows_frame:
            scope_mask = scope_mask | rows_frame["fvcc_team_id"].astype(str).isin(team_ids)
        if "source_team_ids" in rows_frame:
            scope_mask = scope_mask | rows_frame["source_team_ids"].map(lambda value: match_source_contains_team(value, team_ids))
        rows_frame = rows_frame[scope_mask].copy()
    if rows_frame.empty:
        return []

    option_lookup = season_round_team_option_lookup(dashboard_data)
    rows = []
    for _, match in rows_frame.iterrows():
        match_id = str(match.get("match_id", "") or "").strip()
        team_id = str(match.get("fvcc_team_id", "") or "").strip()
        option = season_round_option_for_match(team_id, match.get("source_team_ids"), option_lookup)
        if option:
            grade_slug, grade_label = option
        else:
            grade_label = safe_record_text(match.get("grade_label"), "Team")
            grade_slug = make_player_slug(grade_label or "grade")
        is_premiership = parse_bool(match.get("is_premiership"))
        result_class = safe_record_text(match.get("result_class"), "none")
        result_text = safe_record_text(match.get("result_text"), "no result")
        rows.append(
            {
                "match_id": match_id,
                "round": safe_record_text(match.get("round_display"), "Round"),
                "round_sort": pd.to_numeric(match.get("round_sort"), errors="coerce"),
                "grade": grade_label,
                "grade_slug": grade_slug,
                "is_premiership": is_premiership,
                "opponent": safe_record_text(match.get("opponent_name"), "Unknown opponent"),
                "result_label": safe_record_text(match.get("result_label"), "No Result"),
                "result_class": result_class,
                "result_text": f"{result_text} 🏆" if is_premiership and result_class == "win" else result_text,
                "best_batter": safe_record_text(match.get("best_batter"), "—"),
                "best_bowler": safe_record_text(match.get("best_bowler"), "—"),
                "scorecard": scorecard_link_html(
                    match_id,
                    label="View scorecard ↗",
                    class_name="season-round-scorecard-link",
                    page_slug=SEASON_OVERVIEW_QUERY_PAGE,
                    section_name="season_by_round",
                )
                or '<span class="season-round-pending">Scorecard pending</span>',
                "match_date": match.get("match_date"),
            }
        )
    return sorted(
        rows,
        key=lambda row: (
            -1 if pd.isna(row.get("round_sort")) else int(row.get("round_sort")),
            pd.Timestamp(row["match_date"]).timestamp() if pd.notna(row.get("match_date")) else -1,
            str(row.get("grade", "")).casefold(),
        ),
        reverse=True,
    )


def match_source_contains_team(value: object, team_ids: set[str]) -> bool:
    text = str(value or "")
    if not text:
        return False
    tokens = {token.strip() for token in re.split(r"[,;|]", text) if token.strip()}
    return bool(tokens & team_ids)


def season_round_grade_label(match: pd.Series) -> str:
    team = clean_team_name(match.get("fvcc_team_name"))
    grade = clean_grade_name(match.get("grade_name"))
    if team and grade and team.casefold() not in grade.casefold():
        return f"{team} - {grade}"
    return grade or team or "Team"


def season_round_grade_options(
    dashboard_data: dict[str, object],
    rows: list[dict[str, object]],
) -> list[tuple[str, str]]:
    seen: dict[str, tuple[str, str]] = {}
    for slug, label in season_round_dashboard_team_options(dashboard_data):
        seen.setdefault(slug, (season_round_toggle_label(label), label))
    for row in rows:
        slug = str(row.get("grade_slug") or "").strip()
        label = str(row.get("grade") or "").strip()
        if slug and label:
            seen.setdefault(slug, (season_round_toggle_label(label), label))
    return [
        (slug, display_label)
        for slug, (display_label, sort_label) in sorted(
            seen.items(),
            key=lambda item: grade_sort_key(item[1][1]),
        )
    ]


def season_round_toggle_label(label: object) -> str:
    text = safe_record_text(label, "Team")
    replacements = {
        "Jika Shield": "Jika",
        "Jack Quick Shield": "Jack Quick",
        "Jack Kelly Shield": "Jack Kelly",
        "John Adams Shield": "John Adams",
        "Les Horne Shield": "Les Horne",
        "Robert Young Shield": "Robert Young",
    }
    for full, short in replacements.items():
        text = text.replace(full, short)
    return re.sub(r"\s+", " ", text).strip()


def season_round_dashboard_team_options(dashboard_data: dict[str, object]) -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = []
    for team in dashboard_data.get("teams", []) or []:
        team_id = str(team.get("id", "") or "").strip()
        if not team_id or team_id == "__all_teams__":
            continue
        label = team_card_title(team)
        if not label:
            continue
        options.append((season_round_team_slug(team), label))
    return options


def season_round_team_option_lookup(dashboard_data: dict[str, object]) -> dict[str, tuple[str, str]]:
    lookup: dict[str, tuple[str, str]] = {}
    for team in dashboard_data.get("teams", []) or []:
        team_id = str(team.get("id", "") or "").strip()
        if not team_id or team_id == "__all_teams__":
            continue
        lookup[team_id] = (season_round_team_slug(team), team_card_title(team))
    return lookup


def season_round_team_slug(team: dict[str, object]) -> str:
    team_id = str(team.get("id", "") or "").strip()
    if team_id:
        return f"team_{make_player_slug(team_id)}"
    return make_player_slug(team_card_title(team))


def season_round_option_for_match(
    team_id: str,
    source_team_ids: object,
    option_lookup: dict[str, tuple[str, str]],
) -> tuple[str, str] | None:
    if team_id in option_lookup:
        return option_lookup[team_id]
    for token in re.split(r"[,;|]", str(source_team_ids or "")):
        token = token.strip()
        if token in option_lookup:
            return option_lookup[token]
    return None


def season_round_cards_html(rows: list[dict[str, object]], show_grade_column: bool = False) -> str:
    grouped: dict[str, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(str(row.get("grade") or "Team"), []).append(row)
    cards = []
    for grade_label, grade_rows in sorted(grouped.items(), key=lambda item: grade_sort_key(item[0])):
        record = season_round_record_label(grade_rows)
        trophy = ' <span class="season-round-grade-trophy">🏆</span>' if any(row.get("is_premiership") for row in grade_rows) else ""
        record_html = f'<span class="season-round-record">{html.escape(record)}</span>' if record else ""
        row_html = "".join(season_round_row_html(row, show_grade_column=show_grade_column) for row in grade_rows)
        head_cols = (
            '<div class="season-round-row season-round-head">'
            '<span>Round</span>'
            + ('<span>Grade</span>' if show_grade_column else "")
            + '<span>Opponent</span><span>Result</span><span>Best Batter</span><span>Best Bowler</span><span>Scorecard</span>'
            '</div>'
        )
        card_class = "season-round-grade-card single-grade" if show_grade_column else "season-round-grade-card"
        cards.append(
            f'<article class="{card_class}">'
            '<div class="season-round-grade-head">'
            f'<h3>{html.escape(grade_label)}{trophy}</h3>'
            f'{record_html}'
            '</div>'
            f'<div class="season-round-scroll"><div class="season-round-grid">{head_cols}{row_html}</div></div>'
            '</article>'
        )
    return "".join(cards)


def season_round_row_html(row: dict[str, object], show_grade_column: bool = False) -> str:
    scorecard = str(row.get("scorecard") or '<span class="season-round-pending">Scorecard pending</span>')
    row_class = "season-round-row season-round-premiership-row" if row.get("is_premiership") else "season-round-row"
    return (
        f'<div class="{row_class}">'
        f'<strong>{html.escape(str(row.get("round") or "—"))}</strong>'
        + (f'<span class="season-round-grade-cell">{html.escape(str(row.get("grade") or "—"))}</span>' if show_grade_column else "")
        + f'<span class="season-round-opponent">vs {html.escape(str(row.get("opponent") or "Unknown opponent"))}</span>'
        '<span class="season-round-result">'
        f'<b class="season-result-pill {html.escape(str(row.get("result_class") or "none"))}">{html.escape(str(row.get("result_label") or "No Result"))}</b>'
        f'<span>{html.escape(str(row.get("result_text") or "no result"))}</span>'
        '</span>'
        f'<span class="season-round-performer"><span class="mobile-label">Batter: </span>{html.escape(str(row.get("best_batter") or "—"))}</span>'
        f'<span class="season-round-performer"><span class="mobile-label">Bowler: </span>{html.escape(str(row.get("best_bowler") or "—"))}</span>'
        f'<span class="season-round-scorecard">{scorecard}</span>'
        '</div>'
    )


def season_round_premiership_match_ids() -> set[str]:
    wins, _players = load_premiership_records(premiership_records_signature())
    if wins.empty or "match_id" not in wins:
        return set()
    return {str(match_id).strip() for match_id in wins["match_id"].dropna() if str(match_id).strip()}


def season_round_record_label(rows: list[dict[str, object]]) -> str:
    counts = {"win": 0, "loss": 0, "draw": 0, "tie": 0, "none": 0}
    for row in rows:
        result_class = str(row.get("result_class") or "none")
        counts[result_class if result_class in counts else "none"] += 1
    parts = [f"{counts['win']}W", f"{counts['loss']}L"]
    if counts["draw"]:
        parts.append(f"{counts['draw']}D")
    if counts["tie"]:
        parts.append(f"{counts['tie']}T")
    if counts["none"]:
        parts.append(f"{counts['none']}NR")
    return " - ".join(parts)


def season_round_display(value: object) -> str:
    label = safe_record_text(value, "Round")
    if "final" in label.casefold():
        return re.sub(r"\bRound\s+(\d+)\b", r"R\1", label, flags=re.IGNORECASE)
    match = re.search(r"(\d+)", label)
    if match and "round" in label.casefold():
        return f"R{int(match.group(1))}"
    return label


def season_round_sort_value(value: object) -> int:
    text = str(value or "").casefold()
    if "grand final" in text:
        return 1003
    if "preliminary" in text:
        return 1002
    if "semi" in text:
        return 1001
    if "final" in text:
        return 1000
    match = re.search(r"(\d+)", text)
    return int(match.group(1)) if match else -1


def season_round_result(match: pd.Series) -> dict[str, str]:
    text = normalize_result_wording(safe_record_text(match.get("result_text"), ""))
    lowered = text.casefold()
    if not text or any(token in lowered for token in ["no result", "abandoned", "washout", "rain"]):
        reason = "rain" if "rain" in lowered else "abandoned" if "abandoned" in lowered else ""
        return {"label": "No Result", "class": "none", "text": f"no result{' - ' + reason if reason else ''}"}
    if "draw" in lowered or "drawn" in lowered or "points shared" in lowered:
        return {"label": "Draw", "class": "draw", "text": "draw"}
    if "tie" in lowered or "tied" in lowered:
        return {"label": "Tie", "class": "tie", "text": "tie"}

    winner = text.split(" won", 1)[0].strip() if " won" in lowered else ""
    margin = ""
    margin_match = re.search(r"\bwon\b\s*(.*)$", text, flags=re.IGNORECASE)
    if margin_match:
        margin = margin_match.group(1).strip()
    margin = normalize_result_wording(margin)
    if winner:
        prefix = "won" if is_fvcc_team_name(winner) else "lost"
        return {
            "label": "Win" if prefix == "won" else "Loss",
            "class": "win" if prefix == "won" else "loss",
            "text": normalize_spaces(f"{prefix} {margin}").strip(),
        }
    return {"label": "No Result", "class": "none", "text": text}


def normalize_result_wording(value: object) -> str:
    text = normalize_spaces(str(value or ""))
    replacements = {
        r"\bwkts\b": "wickets",
        r"\bwkt\b": "wicket",
        r"\brns\b": "runs",
    }
    for pattern, replacement in replacements.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return normalize_spaces(text)


def best_batters_by_match(
    batting: pd.DataFrame,
    matches: pd.DataFrame,
    innings: pd.DataFrame | None = None,
    *,
    compact_names: bool = True,
) -> dict[str, str]:
    if batting.empty or matches.empty or "match_id" not in batting:
        return {}
    context = matches[["match_id", "fvcc_team_id", "match_date"]].drop_duplicates("match_id")
    rows = batting.merge(context, on="match_id", how="inner")
    rows = rows[rows["team_id"].astype(str) == rows["fvcc_team_id"].astype(str)].copy()
    rows = add_missing_canonical_player_ids(rows)
    rows = add_season_round_innings_order(rows, innings)
    rows = rows[~rows.get("dismissal_type", pd.Series(index=rows.index, dtype=str)).astype(str).str.casefold().isin({"did not bat", "absent"})]
    rows["runs_scored"] = pd.to_numeric(rows.get("runs_scored"), errors="coerce").fillna(0)
    rows["balls_faced"] = pd.to_numeric(rows.get("balls_faced"), errors="coerce")
    rows["_player_key"] = season_round_player_key(rows)
    rows["_innings_sort"] = pd.to_numeric(rows.get("innings_order"), errors="coerce")
    if rows["_innings_sort"].isna().all():
        rows["_innings_sort"] = pd.to_numeric(rows.get("bat_instance"), errors="coerce")
    rows["_innings_sort"] = rows["_innings_sort"].fillna(99)
    rows["_bat_order_sort"] = pd.to_numeric(rows.get("bat_order"), errors="coerce").fillna(99)
    rows = rows.sort_values(["match_id", "_player_key", "_innings_sort", "_bat_order_sort"], ascending=[True, True, True, True])
    candidates: list[dict[str, object]] = []
    for (match_id, player_key), group in rows.groupby(["match_id", "_player_key"], sort=False):
        if not str(player_key or "").strip():
            continue
        total_runs = float(group["runs_scored"].sum())
        high_score = float(group["runs_scored"].max())
        total_balls = pd.to_numeric(group.get("balls_faced"), errors="coerce").sum(min_count=1)
        name = season_round_player_display_name(group.iloc[0], compact=compact_names and len(group) > 1)
        scores = [format_scorecard_batting_score(row, include_balls=False) for _, row in group.iterrows()]
        candidates.append(
            {
                "match_id": str(match_id),
                "player": name,
                "display": f"{name} {' & '.join(score for score in scores if score)}".strip(),
                "total_runs": total_runs,
                "high_score": high_score,
                "total_balls": float(total_balls) if pd.notna(total_balls) else 9999.0,
            }
        )
    output = {}
    if not candidates:
        return output
    candidate_frame = pd.DataFrame(candidates)
    for match_id, group in candidate_frame.groupby("match_id", sort=False):
        group = group.sort_values(
            ["total_runs", "high_score", "total_balls", "player"],
            ascending=[False, False, True, True],
        )
        output[str(match_id)] = str(group.iloc[0]["display"])
    return output


def best_bowlers_by_match(
    bowling: pd.DataFrame,
    matches: pd.DataFrame,
    innings: pd.DataFrame | None = None,
    *,
    compact_names: bool = True,
) -> dict[str, str]:
    if bowling.empty or matches.empty or "match_id" not in bowling:
        return {}
    context = matches[["match_id", "fvcc_team_id", "match_date"]].drop_duplicates("match_id")
    rows = bowling.merge(context, on="match_id", how="inner")
    rows = rows[rows["team_id"].astype(str) == rows["fvcc_team_id"].astype(str)].copy()
    rows = add_missing_canonical_player_ids(rows)
    rows = add_season_round_innings_order(rows, innings)
    rows = filter_real_scorecard_bowling_rows(rows)
    if rows.empty:
        return {}
    rows["wickets_taken"] = pd.to_numeric(rows.get("wickets_taken"), errors="coerce").fillna(0)
    rows["runs_conceded"] = pd.to_numeric(rows.get("runs_conceded"), errors="coerce").fillna(0)
    rows["_player_key"] = season_round_player_key(rows)
    rows["_innings_sort"] = pd.to_numeric(rows.get("innings_order"), errors="coerce").fillna(99)
    rows["_bowl_order_sort"] = pd.to_numeric(rows.get("bowl_order"), errors="coerce").fillna(99)
    rows["_single_figures_sort"] = rows["wickets_taken"] * 10000 - rows["runs_conceded"]
    rows = rows.sort_values(["match_id", "_player_key", "_innings_sort", "_bowl_order_sort"], ascending=[True, True, True, True])
    candidates: list[dict[str, object]] = []
    for (match_id, player_key), group in rows.groupby(["match_id", "_player_key"], sort=False):
        if not str(player_key or "").strip():
            continue
        total_wickets = float(group["wickets_taken"].sum())
        total_runs = float(group["runs_conceded"].sum())
        name = season_round_player_display_name(group.iloc[0], compact=compact_names and len(group) > 1)
        figures = [format_scorecard_bowling_figures(row, separator="-") for _, row in group.iterrows()]
        candidates.append(
            {
                "match_id": str(match_id),
                "player": name,
                "display": f"{name} {' & '.join(figure for figure in figures if figure)}".strip(),
                "total_wickets": total_wickets,
                "total_runs": total_runs,
                "best_single": float(group["_single_figures_sort"].max()),
            }
        )
    output = {}
    if not candidates:
        return output
    candidate_frame = pd.DataFrame(candidates)
    for match_id, group in candidate_frame.groupby("match_id", sort=False):
        group = group.sort_values(
            ["total_wickets", "total_runs", "best_single", "player"],
            ascending=[False, True, False, True],
        )
        output[str(match_id)] = str(group.iloc[0]["display"])
    return output


def add_season_round_innings_order(rows: pd.DataFrame, innings: pd.DataFrame | None) -> pd.DataFrame:
    if rows.empty or innings is None or innings.empty or "innings_id" not in rows or "innings_id" not in innings:
        return rows.copy()
    order_columns = [column for column in ["match_id", "innings_id", "innings_order", "innings_number"] if column in innings]
    if "innings_order" not in order_columns and "innings_number" not in order_columns:
        return rows.copy()
    order_lookup = innings[order_columns].drop_duplicates(["match_id", "innings_id"] if "match_id" in order_columns else ["innings_id"])
    return rows.merge(order_lookup, on=[column for column in ["match_id", "innings_id"] if column in rows and column in order_lookup], how="left")


def season_round_player_key(rows: pd.DataFrame) -> pd.Series:
    key = pd.Series("", index=rows.index, dtype="object")
    for column in ["canonical_player_id", "participant_id", "raw_player_id", "canonical_player_name", "player_name"]:
        if column in rows:
            values = rows[column].fillna("").astype(str).str.strip()
            key = key.where(key.astype(str).str.strip().ne(""), values)
    return key


def season_round_player_display_name(row: pd.Series, compact: bool = False) -> str:
    name = display_player_name(row.get("canonical_player_name") or row.get("player_name") or row.get("player_short_name") or "Unknown player")
    return format_player_name_compact(name, compact=compact)


def format_player_name_compact(name: object, compact: bool = False) -> str:
    text = safe_record_text(display_player_name(name), "Unknown player")
    if not compact:
        return text
    first = re.split(r"\s+", text.strip())[0] if text.strip() else ""
    return first or text


def format_scorecard_batting_score(row: pd.Series, include_balls: bool = True) -> str:
    runs = pd.to_numeric(row.get("runs_scored"), errors="coerce")
    runs_text = "0" if pd.isna(runs) else str(int(runs))
    dismissal = str(row.get("dismissal_type", "") or "").casefold()
    if "not out" in dismissal:
        runs_text += "*"
    balls = pd.to_numeric(row.get("balls_faced"), errors="coerce")
    if include_balls and pd.notna(balls) and float(balls) > 0:
        runs_text += f"({int(balls)})"
    return runs_text


def format_scorecard_bowling_figures(row: pd.Series, separator: str = "/") -> str:
    wickets = pd.to_numeric(row.get("wickets_taken"), errors="coerce")
    runs = pd.to_numeric(row.get("runs_conceded"), errors="coerce")
    wickets_text = "0" if pd.isna(wickets) else str(int(wickets))
    runs_text = "0" if pd.isna(runs) else str(int(runs))
    return f"{wickets_text}{separator}{runs_text}"


def render_season_overview_v2(dashboard_data: dict[str, object] | None) -> None:
    if not dashboard_data:
        st.info("Load public PlayCricket stats to view the season story.")
        return

    match_data = season_story.load_match_centre_scope(MATCH_CENTRE_PROCESSED_ROOT)
    story = season_story.build_season_story_summary(dashboard_data, match_data)
    ended_today = season_story.build_if_season_ended_today(dashboard_data, match_data)
    awards = season_story.build_season_awards(dashboard_data, match_data)
    pulse = season_story.build_season_pulse(dashboard_data, match_data)
    performances = season_story.build_top_performances(dashboard_data, match_data)
    depth_chart = season_story.build_batting_depth_chart(dashboard_data, match_data)
    role_map = season_story.build_bowling_role_map(dashboard_data, match_data)
    records = season_story.build_records_broken(dashboard_data, match_data)
    strengths_watchouts = season_story.build_strengths_watchouts(dashboard_data, match_data)

    render_season_story_hero(story)
    render_season_v2_awards_section("If the Season Ended Today 🏁", ended_today)
    render_season_v2_awards_section("Season Awards 🏅", awards)
    render_season_pulse_section(pulse)
    render_top_performances_section(performances)
    render_depth_and_role_section(depth_chart, role_map)
    render_records_broken_section(records)
    render_strengths_watchouts_section(strengths_watchouts)
    render_team_specific_leaders(dashboard_data)
    render_full_stats_section(dashboard_data)


def render_season_story_hero(story: dict[str, object]) -> None:
    tiles = story.get("tiles", [])
    tile_html = "".join(
        (
            '<div class="season-v2-hero-tile">'
            f'<div class="season-v2-tile-label">{html.escape(str(tile.get("label", "")))}</div>'
            f'<div class="season-v2-tile-value">{html.escape(str(tile.get("value", "-")))}</div>'
            f'<div class="season-v2-tile-detail">{html.escape(str(tile.get("detail", "")))}</div>'
            "</div>"
        )
        for tile in tiles
    )
    st.markdown(
        f"""
        <section class="season-v2-hero">
            <div class="season-v2-hero-copy">
                <div class="season-v2-eyebrow">Season Story</div>
                <h2>{html.escape(str(story.get("identity", "Season story")))}</h2>
                <p>{html.escape(str(story.get("statement", "")))}</p>
            </div>
            <div class="season-v2-hero-grid">{tile_html}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_season_v2_awards_section(title: str, awards: list[dict[str, object]]) -> None:
    render_section_heading(title)
    if not awards:
        render_empty_story_card("Awards will appear once this selection has enough scorecard data.")
        return
    cards = "".join(render_award_card_html(award) for award in awards)
    st.markdown(f'<div class="season-v2-card-grid">{cards}</div>', unsafe_allow_html=True)


def render_award_card_html(award: dict[str, object]) -> str:
    player = player_profile_link_html(award.get("player_id"), award.get("player"))
    value = season_v2_value(award.get("value"), award.get("unit"))
    reason = str(award.get("reason") or award.get("unit") or "")
    return (
        '<article class="season-v2-award-card">'
        f'<div class="season-v2-card-kicker">{html.escape(str(award.get("title", "")))}</div>'
        f'<div class="season-v2-card-player">{player}</div>'
        f'<div class="season-v2-card-value">{html.escape(value)}</div>'
        f'<div class="season-v2-card-reason">{html.escape(reason)}</div>'
        "</article>"
    )


def render_season_pulse_section(pulse: list[dict[str, object]]) -> None:
    render_section_heading("Season Pulse 🧭")
    render_section_subtext("Match-by-match story from available scorecards.")
    if not pulse:
        render_empty_story_card("Match-by-match story will appear when scorecard-level data is available for this season.")
        return
    cards = []
    for item in pulse:
        result = str(item.get("result", "UNKNOWN"))
        top = item.get("top_batter") or {}
        best = item.get("best_bowler") or {}
        scorecard = scorecard_link_html(
            item.get("match_id"),
            page_slug=SEASON_OVERVIEW_V2_QUERY_PAGE,
            section_name="season_pulse",
        )
        cards.append(
            '<article class="season-v2-pulse-card">'
            f'<div class="season-v2-result {html.escape(result.casefold())}">{html.escape(result)}</div>'
            f'<div class="season-v2-pulse-opponent">vs {html.escape(str(item.get("opponent", "Opponent unknown")))}</div>'
            f'<div class="season-v2-pulse-meta">{html.escape(str(item.get("grade", "")))} · {html.escape(str(item.get("date", "")))}</div>'
            f'<div class="season-v2-pulse-line">Top: {html.escape(str(top.get("player", "-")))} {html.escape(str(top.get("value", "")))}</div>'
            f'<div class="season-v2-pulse-line">Best: {html.escape(str(best.get("player", "-")))} {html.escape(str(best.get("value", "")))}</div>'
            f'<div class="season-v2-pulse-link">{scorecard}</div>'
            "</article>"
        )
    st.markdown(f'<div class="season-v2-pulse-strip">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_top_performances_section(performances: list[dict[str, object]]) -> None:
    render_section_heading("Top Performances of the Season 🔥")
    if not performances:
        render_empty_story_card("Top performances will appear when scorecard-level data is available.")
        return
    cards = []
    for item in performances:
        scorecard = scorecard_link_html(
            item.get("match_id"),
            page_slug=SEASON_OVERVIEW_V2_QUERY_PAGE,
            section_name="top_performances",
        )
        cards.append(
            '<article class="season-v2-performance-card">'
            f'<div class="season-v2-card-kicker">{html.escape(str(item.get("title", "")))}</div>'
            f'<div class="season-v2-performance-value">{html.escape(str(item.get("value", "-")))}</div>'
            f'<div class="season-v2-card-player">{html.escape(str(item.get("player", "-")))}</div>'
            f'<div class="season-v2-card-reason">{html.escape(str(item.get("context", "")))}</div>'
            f'<div class="season-v2-pulse-link">{scorecard}</div>'
            "</article>"
        )
    st.markdown(f'<div class="season-v2-performance-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_depth_and_role_section(depth_chart: list[dict[str, object]], roles: list[dict[str, object]]) -> None:
    left, right = st.columns(2, gap="large")
    with left:
        render_section_heading("Batting Depth Chart 🪜")
        if depth_chart:
            max_share = max([float(row.get("share") or 0) for row in depth_chart] + [1.0])
            rows = []
            for row in depth_chart:
                share = float(row.get("share") or 0)
                width = max(4, min(100, share / max_share * 100))
                avg = row.get("average")
                avg_text = "Avg. —" if pd.isna(avg) else f"Avg. {float(avg):.1f}"
                rows.append(
                    '<div class="season-v2-depth-row">'
                    f'<div class="season-v2-depth-label">{html.escape(str(row.get("bucket", "")))}</div>'
                    '<div class="season-v2-depth-track">'
                    f'<span style="width:{width:.0f}%"></span>'
                    "</div>"
                    f'<div class="season-v2-depth-meta">{int(row.get("runs", 0))} runs · {avg_text}</div>'
                    "</div>"
                )
            st.markdown(f'<div class="season-v2-panel">{"".join(rows)}</div>', unsafe_allow_html=True)
        else:
            render_empty_story_card("Batting order insights will appear when scorecard order data is available.")
    with right:
        render_section_heading("Bowling Role Map 🎯")
        if roles:
            cards = "".join(render_role_card_html(role) for role in roles)
            st.markdown(f'<div class="season-v2-role-grid">{cards}</div>', unsafe_allow_html=True)
        else:
            render_empty_story_card("Bowling role cards will appear once bowling scorecard data is available.")


def render_role_card_html(role: dict[str, object]) -> str:
    player = player_profile_link_html(role.get("player_id"), role.get("player"))
    return (
        '<article class="season-v2-role-card">'
        f'<div class="season-v2-card-kicker">{html.escape(str(role.get("title", "")))}</div>'
        f'<div class="season-v2-card-player">{player}</div>'
        f'<div class="season-v2-card-value">{html.escape(season_v2_value(role.get("value"), ""))}</div>'
        f'<div class="season-v2-card-reason">{html.escape(str(role.get("reason", "")))}</div>'
        "</article>"
    )


def render_records_broken_section(records: list[dict[str, object]]) -> None:
    render_section_heading("Season Records Broken 🧨")
    if not records:
        render_empty_story_card("No verified record-breaking moments found for this season.")
        return
    cards = []
    for item in records:
        cards.append(
            '<article class="season-v2-record-card">'
            f'<div class="season-v2-record-badge">{html.escape(str(item.get("badge", "Season note")))}</div>'
            f'<div class="season-v2-card-kicker">{html.escape(str(item.get("title", "")))}</div>'
            f'<div class="season-v2-performance-value">{html.escape(str(item.get("value", "-")))}</div>'
            f'<div class="season-v2-card-player">{html.escape(str(item.get("player", "-")))}</div>'
            "</article>"
        )
    st.markdown(f'<div class="season-v2-card-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_strengths_watchouts_section(items: dict[str, list[str]]) -> None:
    render_section_heading("Club Strengths & Watchouts 🧠")
    cards = []
    for title, key in [("Strengths", "strengths"), ("Watchouts", "watchouts")]:
        bullets = "".join(f"<li>{html.escape(str(item))}</li>" for item in items.get(key, []))
        cards.append(
            '<article class="season-v2-insight-card">'
            f"<h3>{html.escape(title)}</h3>"
            f"<ul>{bullets}</ul>"
            "</article>"
        )
    st.markdown(f'<div class="season-v2-insight-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


def render_empty_story_card(message: str) -> None:
    st.markdown(f'<div class="season-v2-empty">{html.escape(message)}</div>', unsafe_allow_html=True)


def season_v2_value(value: object, unit: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    parsed = pd.to_numeric(value, errors="coerce")
    if pd.isna(parsed):
        return "-"
    suffix = str(unit or "").strip()
    if suffix in {"avg", "econ", "wickets/match"}:
        return f"{float(parsed):.2f}"
    if suffix == "impact pts":
        return f"{float(parsed):.0f} pts"
    if suffix:
        return f"{float(parsed):,.0f} {suffix}"
    return f"{float(parsed):,.1f}" if float(parsed) % 1 else f"{float(parsed):,.0f}"


def render_match_centre_page() -> None:
    st.markdown(
        f"""
        <h1 class="page-title">Match Insights</h1>
        {configured_club_label_html()}
        <div class="page-subtitle">Scorebook-only match stories, player trends, and records from match-centre data.</div>
        """,
        unsafe_allow_html=True,
    )

    scopes = available_match_centre_scopes()
    if not MATCH_CENTRE_PROCESSED_ROOT.exists():
        st.info(
            "No match-centre data folder was found. Run `scripts/refresh_match_centre_data.py` "
            "for a reviewed season/team scope to create the archive data."
        )
        return
    if not scopes:
        st.info(
            "No processed match-centre CSVs were found yet. Run `scripts/refresh_match_centre_data.py` "
            "and then reload this page."
        )
        return

    scope_options = [scope.name for scope in scopes]
    selected_scope_name = st.selectbox(
        "Match-centre data scope",
        scope_options,
        index=0,
        help="Latest local processed scope is selected by default. Change this to review another generated scope.",
    )
    selected_scope = MATCH_CENTRE_PROCESSED_ROOT / selected_scope_name
    data = load_match_centre_archive(selected_scope_name, match_centre_scope_signature(selected_scope))
    if data["matches"].empty:
        st.info("This match-centre scope does not contain any match rows yet.")
        return

    matches = build_match_archive_frame(data["matches"])
    filtered_matches = render_match_centre_filters(matches)
    if filtered_matches.empty:
        st.info("No matches match the selected filters.")
        return

    render_section_heading("Choose A Match")
    match_list = filtered_matches[
        [
            "match_date_display",
            "fvcc_team_name",
            "opponent_name",
            "grade_name",
            "venue_name",
            "result_text",
            "ball_by_ball_badge",
        ]
    ].rename(
        columns={
            "match_date_display": "Date",
            "fvcc_team_name": "FVCC Team",
            "opponent_name": "Opponent",
            "grade_name": "Grade",
            "venue_name": "Venue",
            "result_text": "Result",
            "ball_by_ball_badge": "Ball-by-ball",
        }
    )
    st.dataframe(match_list, use_container_width=True, hide_index=True, height=table_height(match_list, max_rows=12))

    selected_label = st.selectbox(
        "Match to analyse",
        filtered_matches["match_selector_label"].tolist(),
        index=0,
    )
    selected_match = filtered_matches[filtered_matches["match_selector_label"] == selected_label].iloc[0]
    render_match_centre_detail(selected_match, data)


def render_advanced_analytics_page() -> None:
    st.markdown(
        f"""
        <h1 class="page-title">Advanced Analytics</h1>
        {configured_club_label_html()}
        <div class="page-subtitle">Player-level splits that go beyond the standard PlayCricket scorecard.</div>
        """,
        unsafe_allow_html=True,
    )

    scopes = available_match_centre_scopes()
    if not MATCH_CENTRE_PROCESSED_ROOT.exists():
        st.info(
            "No match-centre data folder was found. Run `scripts/refresh_match_centre_data.py` "
            "for a reviewed season/team scope to create advanced analytics data."
        )
        return
    if not scopes:
        st.info(
            "No processed match-centre CSVs were found yet. Run `scripts/refresh_match_centre_data.py` "
            "and then reload this page."
        )
        return

    selected_scope = scopes[0]
    data = load_match_centre_archive(selected_scope.name, match_centre_scope_signature(selected_scope))
    frames = prepare_match_centre_frames(data)
    players = player_options(frames)
    if players.empty:
        st.info("No FVCC player rows were found in the available match-centre scope.")
        return

    st.caption(f"Using latest local match-centre scope: {selected_scope.name}")
    selected_label = st.selectbox("Player", players["label"].tolist())
    participant_id = str(players.loc[players["label"] == selected_label, "participant_id"].iloc[0])
    rows = selected_player_rows(frames, participant_id)

    render_advanced_player_summary(rows)
    selected_section = st.radio("View", ["Batting", "Bowling"], horizontal=True, label_visibility="collapsed")
    if selected_section == "Batting":
        render_advanced_batting_section(rows, frames, participant_id)
    else:
        render_advanced_bowling_section(rows, frames, participant_id)
    render_fastest_milestones_section(rows, frames, participant_id)
    render_hidden_performances_section(rows, frames, participant_id)


def render_advanced_player_summary(rows: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Player Impact")
    summary = player_summary(rows)
    cards = [
        ("Total runs", format_advanced_value(summary["Total runs"], "int")),
        ("Batting innings", format_advanced_value(summary["Batting innings"], "int")),
        ("Batting average", format_advanced_value(summary["Batting average"], "decimal")),
        ("Strike rate", format_advanced_value(summary["Strike rate"], "decimal")),
        ("Highest score", format_advanced_value(summary["Highest score"], "int")),
        ("Total wickets", format_advanced_value(summary["Total wickets"], "int")),
        ("Bowling innings", format_advanced_value(summary["Bowling innings"], "int")),
        ("Bowling average", format_advanced_value(summary["Bowling average"], "decimal")),
        ("Economy", format_advanced_value(summary["Economy"], "decimal")),
        ("Best bowling", str(summary["Best bowling"]),
        ),
        ("Bat contribution", format_advanced_value(summary["Batting team-run contribution %"], "percent")),
        ("Wicket contribution", format_advanced_value(summary["Bowling wicket contribution %"], "percent")),
    ]
    for start in range(0, len(cards), 4):
        columns = st.columns(4)
        for column, (label, value) in zip(columns, cards[start : start + 4]):
            column.metric(label, value)


def render_advanced_batting_section(rows: dict[str, pd.DataFrame], frames: dict[str, pd.DataFrame], participant_id: str) -> None:
    batting = rows["batting"]
    if batting.empty:
        st.info("This player has no batting rows in the selected match-centre scope.")
        return
    ball_by_ball = frames["ball_by_ball"]
    available_innings = ball_by_ball[
        ball_by_ball.get("striker_participant_id", pd.Series(dtype="object")).astype(str) == participant_id
    ]["innings_id"].nunique() if not ball_by_ball.empty and "innings_id" in ball_by_ball else 0
    if available_innings:
        st.caption(f"Dot and boundary rates use ball-by-ball events for {available_innings} batting innings where available.")
    else:
        st.caption("Dot and boundary rates need ball-by-ball data. Scorecard splits are still available.")

    tables = [
        ("Batting by position", calculate_batting_splits(batting.assign(bat_order=batting.get("bat_order").fillna("Unknown")), ball_by_ball, "bat_order", "Position")),
        ("Batting by home/away", calculate_batting_splits(batting, ball_by_ball, "home_away", "Home/Away")),
        ("Batting by ground", calculate_batting_splits(batting, ball_by_ball, "venue_name", "Ground")),
        ("Batting by opposition team", calculate_batting_splits(batting, ball_by_ball, "opponent_name", "Opposition")),
        ("Batting by match format", calculate_batting_splits(batting, ball_by_ball, "format", "Format")),
    ]
    for title, table in tables:
        render_advanced_table(title, table)


def render_advanced_bowling_section(rows: dict[str, pd.DataFrame], frames: dict[str, pd.DataFrame], participant_id: str) -> None:
    bowling = rows["bowling"]
    player_balls = frames["ball_by_ball"][
        frames["ball_by_ball"].get("bowler_participant_id", pd.Series(dtype="object")).astype(str) == participant_id
    ].copy() if not frames["ball_by_ball"].empty else pd.DataFrame()
    render_section_heading("Bowling Phase Analytics")
    if player_balls.empty:
        st.info("Bowling phase analytics need ball-by-ball data. Scorecard-based bowling splits are still available below.")
    else:
        render_advanced_table("Bowling by game phase", bowling_phase_splits(frames["ball_by_ball"], frames["matches"], participant_id))

    if bowling.empty:
        st.info("This player has no bowling rows in the selected match-centre scope.")
        return
    tables = [
        ("Bowling by home/away", calculate_bowling_splits(bowling, "home_away", "Home/Away")),
        ("Bowling by ground", calculate_bowling_splits(bowling, "venue_name", "Ground")),
        ("Bowling by opposition team", calculate_bowling_splits(bowling, "opponent_name", "Opposition")),
        ("Bowling by match format", calculate_bowling_splits(bowling, "format", "Format")),
    ]
    for title, table in tables:
        render_advanced_table(title, table)


def render_fastest_milestones_section(rows: dict[str, pd.DataFrame], frames: dict[str, pd.DataFrame], participant_id: str) -> None:
    render_section_heading("Fastest 50s And 100s")
    milestones = calculate_fastest_milestones(rows["batting"], frames["ball_by_ball"], participant_id)
    if milestones.empty:
        st.info("No 50 or 100 milestones could be calculated from the available ball-by-ball data for this player.")
        return
    render_advanced_table("Milestones from ball-by-ball", milestones)


def render_hidden_performances_section(rows: dict[str, pd.DataFrame], frames: dict[str, pd.DataFrame], participant_id: str) -> None:
    render_section_heading("Best Hidden Performances")
    hidden = calculate_best_hidden_performances(rows["batting"], rows["bowling"], frames["ball_by_ball"], participant_id)
    render_advanced_table("Notable innings and spells", hidden)


def render_player_dna_page() -> None:
    render_player_dna_html(
        f"""
        <div class="player-dna-page"></div>
        <h1 class="page-title">Player DNA</h1>
        {configured_club_label_html()}
        <div class="page-subtitle">A hidden experimental lens on player identity, strengths, and match-centre patterns.</div>
        """
    )

    data = load_player_dna_cached(metadata_mtime(), player_aliases_mtime(), player_dna_data_signature())
    options = player_dna.player_dna_options(data)
    if options.empty:
        render_empty_insight_card(
            "Player DNA is still building",
            "No player records were found in the processed Scorebook data.",
            "Refresh the existing app data first, then reload this hidden page.",
        )
        return

    selected_label = st.selectbox("Player", options["label"].tolist())
    selected_key = str(options.loc[options["label"] == selected_label, "player_key"].iloc[0])
    profile = player_dna.build_player_dna_profile(data, selected_key)

    if not profile["has_match_centre"]:
        st.caption("Scorebook aggregate data is available. Match-centre insights will appear when local processed match-centre data is present.")
    elif data.get("match_centre_scope"):
        st.caption(f"Using local match-centre scope: {data['match_centre_scope']}")

    render_player_dna_hero_card(profile["hero"])
    render_trait_bars(profile["traits"])

    columns = st.columns([1.05, 0.95])
    with columns[0]:
        render_position_ladder(profile["position_splits"])
    with columns[1]:
        render_dismissal_fingerprint(profile["dismissal_fingerprint"])

    columns = st.columns(2)
    with columns[0]:
        render_ground_hunter_card(profile["ground_splits"])
    with columns[1]:
        render_opponent_hunter_card(profile["opponent_splits"])

    render_hidden_best_cards(profile["hidden_performances"])
    render_ball_by_ball_bonus(profile["ball_bonus"], profile["has_ball_by_ball"])


@st.cache_data(show_spinner=False)
def load_player_dna_cached(
    _local_version: float,
    _identity_version: float | None,
    _signature: tuple[tuple[str, float], ...],
) -> dict[str, object]:
    return player_dna.load_player_dna_data(APP_ROOT)


def player_dna_data_signature() -> tuple[tuple[str, float], ...]:
    paths: list[Path] = []
    if HALL_OF_FAME_FASTEST_BATTING_MILESTONES_PATH.exists():
        paths.append(HALL_OF_FAME_FASTEST_BATTING_MILESTONES_PATH)
    scope = MATCH_CENTRE_PROCESSED_ROOT / "all_available"
    if not (scope / "all_matches.csv").exists():
        scopes = available_match_centre_scopes()
        scope = scopes[0] if scopes else scope
    if scope.exists():
        paths.extend(sorted(path for path in scope.glob("*.csv") if path.is_file()))
    return tuple((str(path.relative_to(APP_ROOT)), path.stat().st_mtime) for path in paths)


def render_player_dna_hero_card(hero: dict[str, object]) -> None:
    player_name = dna_text(hero.get("player_name"), "Unknown player")
    role = dna_text(hero.get("role_badge"), "Profile building as more data becomes available")
    signature = dna_text(hero.get("signature_stat"), "Profile building")
    tiles = [
        ("Signature stat", signature),
        ("Best batting position", dna_text(hero.get("best_position"), "Not enough innings yet")),
        ("Best ground", dna_text(hero.get("best_ground"), "Not enough match-centre data yet")),
        ("Best opponent", dna_text(hero.get("best_opponent"), "Not enough match-centre data yet")),
        ("Hidden performance", dna_text(hero.get("best_hidden"), "Profile building")),
    ]
    tile_html = "".join(
        compact_html(
            f"""
            <div class="dna-hero-tile">
                <span>{html.escape(label)}</span>
                <strong>{html.escape(value)}</strong>
            </div>
            """
        )
        for label, value in tiles
    )
    render_player_dna_html(
        f"""
        <div class="dna-hero-card">
            <div class="dna-hero-main">
                <div class="dna-kicker">Player identity profile</div>
                <div class="dna-player-name">{html.escape(player_name)}</div>
                <div class="dna-role-badge">{html.escape(role)}</div>
            </div>
            <div class="dna-hero-grid">{tile_html}</div>
        </div>
        """
    )


def render_trait_bars(traits: list[dict[str, object]]) -> None:
    render_section_heading("Trait Map")
    if not traits:
        render_empty_insight_card(
            "Traits need more data",
            "There is not enough scorecard or ball-by-ball data to build a trait profile yet.",
            "This will sharpen as match-centre coverage improves.",
        )
        return
    batting = [trait for trait in traits if trait.get("category") == "Batting"]
    bowling = [trait for trait in traits if trait.get("category") == "Bowling"]
    columns = st.columns(2)
    with columns[0]:
        render_trait_group("Batting DNA", batting, "No batting traits available yet.")
    with columns[1]:
        render_trait_group("Bowling DNA", bowling, "No bowling traits available yet.")


def render_trait_group(title: str, traits: list[dict[str, object]], empty_message: str) -> None:
    if not traits:
        render_empty_insight_card(title, empty_message, "Scorecard-based traits will appear once this player has matching rows.")
        return
    with st.container(border=True):
        st.markdown(f"#### {title}")
        for trait in traits:
            render_trait_bar(trait)


def render_trait_bar(trait: dict[str, object]) -> None:
    score = dna_float(trait.get("score"))
    width = max(0, min(score, 100))
    label = dna_text(trait.get("label"), "Trait")
    level = dna_text(trait.get("level"), "Building")
    description = dna_text(trait.get("description"))
    label_col, value_col = st.columns([0.62, 0.38])
    label_col.markdown(f"**{label}**")
    value_col.markdown(f"**{level} · {width:.0f}/100**")
    st.progress(width / 100)
    st.caption(description)


def compact_html(markup: str) -> str:
    return textwrap.dedent(markup).strip()


def render_player_dna_html(markup: str) -> None:
    st.markdown(compact_html(markup), unsafe_allow_html=True)


def render_position_ladder(positions: pd.DataFrame) -> None:
    render_section_heading("Best Position")
    if positions.empty:
        render_empty_insight_card(
            "Batting position ladder",
            "No match-centre batting position data is available for this player yet.",
            "Scorecard batting-order rows are needed to build this view.",
        )
        return
    max_score = max(float(positions["impact_score"].max()), 1)
    rows = []
    for index, row in positions.head(6).iterrows():
        width = max(10, min(float(row.get("impact_score", 0)) / max_score * 100, 100))
        position = int(row["bat_order"])
        meta = (
            f"{int(row['innings'])} inns | {int(row['runs'])} runs | "
            f"{dna_decimal(row.get('average'))} avg | {dna_pct(row.get('avg_contribution_pct'))} contribution"
        )
        best_badge = '<span class="dna-mini-badge">Best fit</span>' if index == 0 else ""
        rows.append(
            compact_html(
            f"""
            <div class="dna-ladder-row">
                <div class="dna-ladder-top">
                    <strong>No. {position}</strong>
                    <span>{html.escape(meta)} {best_badge}</span>
                </div>
                <div class="dna-contribution-track"><div style="width:{width:.0f}%"></div></div>
            </div>
            """
            )
        )
    render_player_dna_html(f'<div class="dna-card"><div class="dna-card-title">Batting-position ladder</div>{"".join(rows)}</div>')


def render_ground_hunter_card(grounds: list[dict[str, object]]) -> None:
    render_hunter_card(
        "Ground Hunter",
        "This is the ground where this player has had the biggest impact.",
        grounds,
        "ground",
        "No ground split is available yet.",
    )


def render_opponent_hunter_card(opponents: list[dict[str, object]]) -> None:
    render_hunter_card(
        "Opponent Hunter",
        "This opponent brings out their best cricket.",
        opponents,
        "opponent",
        "No opponent split is available yet.",
    )


def render_hunter_card(title: str, insight: str, rows: list[dict[str, object]], label_key: str, empty_message: str) -> None:
    render_section_heading(title)
    if not rows:
        render_empty_insight_card(title, empty_message, "More match-centre scorecards will fill this out.")
        return
    row_html = []
    for rank, row in enumerate(rows[:4], start=1):
        label = dna_text(row.get(label_key), "Unknown")
        primary = dna_text(row.get("primary"), "0")
        primary_label = dna_text(row.get("primary_label"))
        secondary = dna_text(row.get("secondary"))
        detail = dna_text(row.get("detail"))
        mode = dna_text(row.get("mode"))
        row_html.append(
            compact_html(
            f"""
            <div class="dna-rank-row">
                <span class="progress-rank">{rank_badge(rank)}</span>
                <div class="dna-rank-main">
                    <strong>{html.escape(label)}</strong>
                    <span>{html.escape(mode)} | {html.escape(secondary)} | {html.escape(detail)}</span>
                </div>
                <div class="dna-rank-value">{html.escape(primary)}<span>{html.escape(primary_label)}</span></div>
            </div>
            """
            )
        )
    render_player_dna_html(
        f"""
        <div class="dna-card">
            <div class="dna-card-title">{html.escape(title)}</div>
            <div class="dna-insight-line">{html.escape(insight)}</div>
            {"".join(row_html)}
        </div>
        """
    )


def render_hidden_best_cards(records: list[dict[str, object]]) -> None:
    render_section_heading("Hidden Best Performances")
    if not records:
        render_empty_insight_card(
            "Hidden performances",
            "No hidden performance cards can be built for this player yet.",
            "Contribution, bowling share, and milestone cards need match-centre scorecards or ball-by-ball data.",
        )
        return
    cards = "".join(render_ranked_insight_card(rank, record) for rank, record in enumerate(records[:6], start=1))
    render_player_dna_html(f'<div class="dna-performance-grid">{cards}</div>')


def render_ranked_insight_card(rank: int, record: dict[str, object]) -> str:
    return compact_html(
        f"""
        <div class="dna-performance-card">
            <div class="dna-performance-rank">{rank_badge(rank)}</div>
            <div class="dna-performance-body">
                <strong>{html.escape(dna_text(record.get("title"), "Performance"))}</strong>
                <span>{html.escape(dna_text(record.get("subtitle")))}</span>
                <em>{html.escape(dna_text(record.get("context")))}</em>
                <small>{html.escape(dna_text(record.get("explanation")))}</small>
            </div>
            <div class="dna-performance-value">{html.escape(dna_text(record.get("value")))}</div>
        </div>
        """
    )


def render_dismissal_fingerprint(fingerprint: pd.DataFrame) -> None:
    render_section_heading("Dismissal Fingerprint")
    if fingerprint.empty:
        render_empty_insight_card(
            "Dismissal fingerprint",
            "No dismissal pattern is available yet.",
            "This needs match-centre batting dismissal fields.",
        )
        return
    rows = []
    for _, row in fingerprint.iterrows():
        pct = dna_float(row.get("pct"))
        rows.append(
            compact_html(
            f"""
            <div class="dna-fingerprint-row">
                <div class="dna-fingerprint-label">
                    <strong>{html.escape(dna_text(row.get("label")))}</strong>
                    <span>{int(row.get("count", 0))} dismissals</span>
                </div>
                <div class="dna-fingerprint-track"><div style="width:{max(4, min(pct, 100)):.0f}%"></div></div>
                <div class="dna-fingerprint-pct">{pct:.1f}%</div>
            </div>
            """
            )
        )
    top = fingerprint.sort_values("pct", ascending=False).iloc[0]
    insight = f"Most dismissals are {dna_text(top.get('label')).casefold()}, suggesting a pattern worth reviewing."
    render_player_dna_html(
        f"""
        <div class="dna-card">
            <div class="dna-card-title">Dismissal fingerprint</div>
            {"".join(rows)}
            <div class="dna-insight-line">{html.escape(insight)}</div>
        </div>
        """
    )


def render_ball_by_ball_bonus(cards: list[dict[str, object]], has_ball_by_ball: bool) -> None:
    render_section_heading("Ball-By-Ball Bonus")
    if not cards:
        message = (
            "Ball-by-ball profile will grow as more scored matches become available."
            if not has_ball_by_ball
            else "No player-specific ball-by-ball traits were found yet."
        )
        render_empty_insight_card("Ball-by-ball profile", message, "Scorecard-based Player DNA remains available above.")
        return
    card_html = "".join(
        compact_html(
            f"""
            <div class="dna-bonus-card">
                <span>{html.escape(dna_text(card.get("label")))}</span>
                <strong>{html.escape(dna_text(card.get("value")))}</strong>
                <em>{html.escape(dna_text(card.get("detail")))}</em>
            </div>
            """
        )
        for card in cards
    )
    render_player_dna_html(f'<div class="dna-bonus-grid">{card_html}</div>')


def render_empty_insight_card(title: str, message: str, detail: str = "") -> None:
    render_player_dna_html(
        f"""
        <div class="dna-card dna-empty-card">
            <div class="dna-card-title">{html.escape(title)}</div>
            <div class="dna-empty-message">{html.escape(message)}</div>
            <div class="dna-empty-detail">{html.escape(detail)}</div>
        </div>
        """
    )


def dna_text(value: object, fallback: str = "") -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "nat"}:
        return fallback
    return " ".join(text.split())


def dna_float(value: object) -> float:
    numeric = pd.to_numeric(value, errors="coerce")
    return 0.0 if pd.isna(numeric) else float(numeric)


def dna_decimal(value: object) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    return "N/A" if pd.isna(numeric) else f"{float(numeric):.2f}"


def dna_pct(value: object) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    return "N/A" if pd.isna(numeric) else f"{float(numeric):.1f}%"


def render_scorebook_lab_page() -> None:
    render_player_dna_html(
        f"""
        <div class="scorebook-lab-page"></div>
        <h1 class="page-title">Scorebook Lab</h1>
        {configured_club_label_html()}
        <div class="page-subtitle">Experimental hidden records, matchup stories, MVP cards, and scorecard intelligence.</div>
        """
    )

    data = load_scorebook_lab_cached(metadata_mtime(), player_aliases_mtime(), player_dna_data_signature())
    lab = data.get("lab", {})
    if lab_missing(lab):
        render_empty_insight_card(
            "Scorebook Lab is waiting for match-centre data",
            "Run the reviewed match-centre refresh locally to unlock hidden records and match stories.",
            "The stable app pages continue to use the existing aggregate pipeline.",
        )
        return

    if data.get("match_centre_scope"):
        st.caption(f"Using local match-centre scope: {data['match_centre_scope']}")

    section = st.radio(
        "Lab section",
        ["Hidden Records", "Ground Hunter", "Opponent Hunter", "Position Intelligence", "Match Story", "Partnership Chemistry"],
        horizontal=True,
    )
    if section == "Hidden Records":
        render_scorebook_lab_hidden_records(lab)
    elif section == "Ground Hunter":
        render_scorebook_lab_ground_hunter(lab)
    elif section == "Opponent Hunter":
        render_scorebook_lab_opponent_hunter(lab)
    elif section == "Position Intelligence":
        render_scorebook_lab_position_intelligence(lab)
    elif section == "Match Story":
        render_scorebook_lab_match_story(lab)
    else:
        render_scorebook_lab_partnerships(lab)


@st.cache_data(show_spinner=False)
def load_scorebook_lab_cached(
    _local_version: float,
    _identity_version: float | None,
    _signature: tuple[tuple[str, float], ...],
) -> dict[str, object]:
    return scorebook_lab.load_scorebook_lab_data(APP_ROOT)


def lab_missing(lab: dict[str, pd.DataFrame]) -> bool:
    return not lab or all(lab.get(name, pd.DataFrame()).empty for name in ["batting", "bowling", "fielding", "matches"])


def render_scorebook_lab_hidden_records(lab: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Hidden Records")
    render_insight_sentence_card(
        "These are the performances that normal scorecards tend to flatten.",
        "Contribution share, wicket share, fielding involvement, and simple all-round impact are all scorecard-first metrics.",
    )
    rows = [
        ("Biggest Carry Jobs", scorebook_lab.calculate_carry_jobs(lab["batting"]), "This was not just a score. It was the spine of the innings."),
        ("Highest Team-Run Contribution", scorebook_lab.calculate_team_run_contribution_records(lab["batting"]), "A pure look at who owned the largest share of an FVCC total."),
        ("Wicket Share Dominance", scorebook_lab.calculate_wicket_share_dominance(lab["bowling"]), "He took a serious chunk of every wicket FVCC claimed."),
        ("Best All-Round Match Impact", scorebook_lab.calculate_all_round_match_impact(lab["batting"], lab["bowling"], lab["fielding"]), "A simple blend of batting contribution, wicket share, and fielding involvement."),
        ("Best Fielding Impact", scorebook_lab.calculate_fielding_impact(lab["fielding"]), "Fielding moments that changed the scorecard without becoming headline batting or bowling figures."),
    ]
    for start in range(0, len(rows), 2):
        columns = st.columns(2)
        for column, (title, records, insight) in zip(columns, rows[start : start + 2]):
            with column:
                render_lab_ranked_card(title, records[:5], insight)


def render_scorebook_lab_ground_hunter(lab: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Ground Hunter")
    grounds = scorebook_lab.selector_options(lab["matches"], "venue_name")
    if not grounds:
        render_empty_insight_card("Ground Hunter", "No venue data is available yet.", "Match-centre scorecards need venue names to power this view.")
        return
    selected = st.selectbox("Ground", grounds)
    profile = scorebook_lab.calculate_ground_hunter(lab["matches"], lab["innings"], lab["batting"], lab["bowling"], lab["fielding"], selected)
    render_lab_profile_hero(profile, "Ground profile", profile.get("insight", "This ground has a distinct profile in the current archive."))
    render_lab_feature_cards([profile.get("top_batter"), profile.get("top_bowler"), profile.get("best_innings"), profile.get("best_bowling"), profile.get("best_fielding")])
    render_lab_heatmap_list("Player impact at this ground", profile.get("heatmap", []))


def render_scorebook_lab_opponent_hunter(lab: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Opponent Hunter")
    opponents = scorebook_lab.selector_options(lab["matches"], "opponent_name")
    if not opponents:
        render_empty_insight_card("Opponent Hunter", "No opponent data is available yet.", "Match-centre scorecards need opponent names to power this view.")
        return
    selected = st.selectbox("Opponent", opponents)
    profile = scorebook_lab.calculate_opponent_hunter(lab["matches"], lab["innings"], lab["batting"], lab["bowling"], lab["fielding"], selected)
    subtitle = f"FVCC avg: {profile.get('average_score', 'N/A')} | Opp avg: {profile.get('opponent_average_score', 'N/A')}"
    render_lab_profile_hero(profile, subtitle, profile.get("insight", "This opponent brings out their best cricket."))
    render_lab_feature_cards([profile.get("top_batter"), profile.get("top_bowler"), profile.get("best_innings"), profile.get("best_bowling"), profile.get("best_fielding"), profile.get("dismissal")])
    render_lab_heatmap_list("Player impact against this opponent", profile.get("heatmap", []))


def render_scorebook_lab_position_intelligence(lab: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Position Intelligence")
    players = scorebook_lab.position_player_options(lab["batting"])
    if players.empty:
        render_empty_insight_card("Position Intelligence", "No batting-order rows are available yet.", "Scorecard batting order is required for this view.")
        return
    selected = st.selectbox("Player", players["label"].tolist())
    player_key = str(players.loc[players["label"] == selected, "player_key"].iloc[0])
    profile = scorebook_lab.calculate_position_intelligence(lab["batting"], player_key)
    render_insight_sentence_card("Batting order is a role, not just a number.", profile.get("insight", "Position profile is building."))
    render_lab_position_ladder(profile.get("player_positions", pd.DataFrame()))
    render_lab_ranked_card("Team-Level Best By Position", profile.get("team_positions", [])[:8], "A quick read on who has owned each batting role in the archive.")


def render_scorebook_lab_match_story(lab: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Match Story")
    options = scorebook_lab.match_options(lab["matches"])
    if options.empty:
        render_empty_insight_card("Match Story", "No match list is available yet.", "Match-centre match rows are required for match stories.")
        return
    selected = st.selectbox("Match", options["label"].tolist())
    match_id = str(options.loc[options["label"] == selected, "match_id"].iloc[0])
    match = lab["matches"][lab["matches"]["match_id"].astype(str) == match_id].iloc[0]
    mvp = scorebook_lab.calculate_hidden_match_mvp(match, lab["batting"], lab["bowling"], lab["fielding"])
    story = scorebook_lab.calculate_match_story(match, lab["innings"], lab["batting"], lab["bowling"], lab["fielding"], lab["partnerships"])
    render_hidden_mvp_card(mvp)
    render_match_story_cards(mvp)
    render_story_timeline(story)


def render_scorebook_lab_partnerships(lab: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Partnership Chemistry")
    profile = scorebook_lab.calculate_partnership_chemistry(lab["partnerships"])
    render_insight_sentence_card("Partnerships are treated as a confidence-ranked experiment.", profile.get("insight", "Partnership rows are still building."))
    if profile.get("quality") != "usable":
        render_empty_insight_card("Partnership Chemistry", profile.get("insight", "No partnership rows are available yet."), "This section stays cautious until batter-pair names and runs are reliable.")
        return
    render_lab_ranked_card("Best Batting Pairs", profile.get("pairs", [])[:8], "These two score together better than the archive baseline.")


def render_insight_sentence_card(title: str, sentence: str) -> None:
    render_player_dna_html(
        f"""
        <div class="dna-card lab-sentence-card">
            <div class="dna-card-title">{html.escape(title)}</div>
            <div class="dna-insight-line">{html.escape(sentence)}</div>
        </div>
        """
    )


def render_lab_profile_hero(profile: dict[str, object], subtitle: str, insight: str) -> None:
    tiles = [
        ("Archive record", dna_text(profile.get("record"), "Unavailable")),
        ("Average FVCC score", dna_text(profile.get("average_score"), "N/A")),
        ("Matches", dna_text(profile.get("subtitle"), "Building")),
    ]
    tile_html = "".join(
        compact_html(
            f"""
            <div class="dna-hero-tile">
                <span>{html.escape(label)}</span>
                <strong>{html.escape(value)}</strong>
            </div>
            """
        )
        for label, value in tiles
    )
    render_player_dna_html(
        f"""
        <div class="dna-hero-card lab-hero-card">
            <div class="dna-hero-main">
                <div class="dna-kicker">{html.escape(subtitle)}</div>
                <div class="dna-player-name">{html.escape(dna_text(profile.get("title"), "Scorebook Lab"))}</div>
                <div class="dna-role-badge">{html.escape(insight)}</div>
            </div>
            <div class="dna-hero-grid">{tile_html}</div>
        </div>
        """
    )


def render_lab_feature_cards(records: list[dict[str, object] | None]) -> None:
    usable = [record for record in records if record]
    if not usable:
        render_empty_insight_card("Feature cards", "Not enough data for feature cards yet.", "This will fill as scorecard coverage improves.")
        return
    card_html = "".join(render_lab_mini_card(record) for record in usable)
    render_player_dna_html(f'<div class="dna-bonus-grid lab-feature-grid">{card_html}</div>')


def render_lab_mini_card(record: dict[str, object]) -> str:
    return compact_html(
        f"""
        <div class="dna-bonus-card">
            <span>{html.escape(dna_text(record.get("badge"), "Insight"))}</span>
            <strong>{html.escape(dna_text(record.get("title"), "Unknown"))}</strong>
            <em>{html.escape(dna_text(record.get("value")))} · {html.escape(dna_text(record.get("subtitle")))}</em>
            <div class="dna-insight-line">{html.escape(dna_text(record.get("detail")))}</div>
        </div>
        """
    )


def render_lab_ranked_card(title: str, records: list[dict[str, object]], insight: str) -> None:
    if not records:
        render_empty_insight_card(title, "No qualifying records yet.", "This card will fill as scorecard coverage improves.")
        return
    rows = "".join(render_lab_rank_row(rank, record) for rank, record in enumerate(records, start=1))
    render_player_dna_html(
        f"""
        <div class="dna-card lab-ranked-card">
            <div class="dna-card-title">{html.escape(title)}</div>
            <div class="dna-insight-line">{html.escape(insight)}</div>
            {rows}
        </div>
        """
    )


def render_lab_rank_row(rank: int, record: dict[str, object]) -> str:
    return compact_html(
        f"""
        <div class="dna-rank-row">
            <span class="progress-rank">{rank_badge(rank)}</span>
            <div class="dna-rank-main">
                <strong>{html.escape(dna_text(record.get("title"), "Unknown"))}</strong>
                <span>{html.escape(dna_text(record.get("subtitle")))} | {html.escape(dna_text(record.get("detail") or record.get("context")))}</span>
                <span class="lab-badge-line">{html.escape(dna_text(record.get("badge")))}</span>
            </div>
            <div class="dna-rank-value">{html.escape(dna_text(record.get("value")))}<span>{html.escape(dna_text(record.get("value_label")))}</span></div>
        </div>
        """
    )


def render_lab_heatmap_list(title: str, records: list[dict[str, object]]) -> None:
    if not records:
        render_empty_insight_card(title, "No ranked impact rows yet.", "This view needs batting or bowling scorecard rows.")
        return
    values = [lab_numeric_value(record.get("value")) for record in records]
    max_value = max(values + [1])
    rows = []
    for record, raw in zip(records[:8], values[:8]):
        width = 20 if raw <= 0 else max(12, min(float(raw) / float(max_value) * 100, 100))
        rows.append(
            compact_html(
                f"""
                <div class="dna-ladder-row">
                    <div class="dna-ladder-top">
                        <strong>{html.escape(dna_text(record.get("title"), "Unknown"))}</strong>
                        <span>{html.escape(dna_text(record.get("value")))} · {html.escape(dna_text(record.get("subtitle")))}</span>
                    </div>
                    <div class="dna-contribution-track"><div style="width:{width:.0f}%"></div></div>
                    <div class="dna-trait-copy">{html.escape(dna_text(record.get("detail")))}</div>
                </div>
                """
            )
        )
    render_player_dna_html(f'<div class="dna-card"><div class="dna-card-title">{html.escape(title)}</div>{"".join(rows)}</div>')


def render_lab_position_ladder(positions: pd.DataFrame) -> None:
    if positions.empty:
        render_empty_insight_card("Player position ladder", "This player has no match-centre batting-order rows yet.", "Try another player with scorecard batting entries.")
        return
    max_impact = max(float(positions["impact"].max()), 1)
    rows = []
    for index, row in positions.head(8).iterrows():
        width = max(10, min(float(row.get("impact", 0)) / max_impact * 100, 100))
        badge = '<span class="dna-mini-badge">Best role</span>' if index == positions.index[0] else ""
        meta = f"{int(row['innings'])} inns | {int(row['runs'])} runs | {dna_decimal(row.get('average'))} avg | {dna_pct(row.get('contribution_pct'))} contribution"
        rows.append(
            compact_html(
                f"""
                <div class="dna-ladder-row">
                    <div class="dna-ladder-top">
                        <strong>No. {int(row['bat_order'])}</strong>
                        <span>{html.escape(meta)} {badge}</span>
                    </div>
                    <div class="dna-contribution-track"><div style="width:{width:.0f}%"></div></div>
                </div>
                """
            )
        )
    render_player_dna_html(f'<div class="dna-card"><div class="dna-card-title">Selected player batting-order ladder</div>{"".join(rows)}</div>')


def render_hidden_mvp_card(mvp: dict[str, object]) -> None:
    player = mvp.get("mvp", {})
    batting_width = lab_width(player.get("batting"), player.get("total"))
    bowling_width = lab_width(player.get("bowling"), player.get("total"))
    fielding_width = lab_width(player.get("fielding"), player.get("total"))
    lines = " | ".join(player.get("lines", [])[:3]) if isinstance(player.get("lines"), list) else ""
    render_player_dna_html(
        f"""
        <div class="dna-hero-card lab-hero-card">
            <div class="dna-hero-main">
                <div class="dna-kicker">{html.escape(dna_text(mvp.get("match_title"), "Match Story"))}</div>
                <div class="dna-player-name">{html.escape(dna_text(player.get("player"), "Hidden MVP"))}</div>
                <div class="dna-role-badge">Scorebook MVP · {html.escape(f"{dna_float(player.get('total')):.0f}")} impact points</div>
            </div>
            <div class="lab-impact-stack">
                {lab_stack_row("Batting", batting_width)}
                {lab_stack_row("Bowling", bowling_width)}
                {lab_stack_row("Fielding", fielding_width)}
                <div class="dna-insight-line">{html.escape(lines or dna_text(mvp.get("result"), "MVP built from available scorecard impact."))}</div>
            </div>
        </div>
        """
    )


def lab_stack_row(label: str, width: float) -> str:
    return compact_html(
        f"""
        <div class="lab-stack-row">
            <span>{html.escape(label)}</span>
            <div class="dna-contribution-track"><div style="width:{width:.0f}%"></div></div>
        </div>
        """
    )


def render_match_story_cards(mvp: dict[str, object]) -> None:
    cards = [mvp.get("top_batting"), mvp.get("top_bowling"), mvp.get("top_fielding")]
    render_lab_feature_cards(cards)


def render_story_timeline(story: list[dict[str, str]]) -> None:
    rows = "".join(
        compact_html(
            f"""
            <div class="lab-story-row">
                <span></span>
                <div>
                    <strong>{html.escape(dna_text(item.get("title"), "Moment"))}</strong>
                    <p>{html.escape(dna_text(item.get("text")))}</p>
                </div>
            </div>
            """
        )
        for item in story
    )
    render_player_dna_html(f'<div class="dna-card lab-story-card"><div class="dna-card-title">Match story timeline</div>{rows}</div>')


def lab_width(value: object, total: object) -> float:
    total_value = dna_float(total)
    if total_value <= 0:
        return 0
    return max(4, min(dna_float(value) / total_value * 100, 100))


def lab_numeric_value(value: object) -> float:
    numeric = pd.to_numeric(str(value or "0").replace("%", "").replace(",", ""), errors="coerce")
    return 0.0 if pd.isna(numeric) else float(numeric)


def render_advanced_table(title: str, table: pd.DataFrame) -> None:
    st.markdown(f"### {html.escape(title)}")
    if table.empty:
        st.info("No data available for this split yet.")
        return
    display = format_advanced_table(table)
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        height=table_height(display, max_rows=9),
        column_config=numeric_column_config(display.columns.tolist()),
    )


def format_advanced_table(table: pd.DataFrame) -> pd.DataFrame:
    output = table.copy()
    for column in output.columns:
        if column.endswith("%") or "contribution" in column.casefold() or "Dot %" in column or "Boundary" in column:
            output[column] = output[column].map(lambda value: format_advanced_value(value, "percent"))
        elif column in {"Average", "Strike rate", "Economy"}:
            output[column] = output[column].map(lambda value: format_advanced_value(value, "decimal"))
        elif column in {"Runs", "Outs", "Innings", "Highest score", "Balls faced", "4s", "6s", "Wickets", "Runs conceded", "Balls", "Extras", "Final score", "Final balls faced", "Balls to 50", "Balls to 100"}:
            output[column] = output[column].map(lambda value: format_advanced_value(value, "int"))
        else:
            output[column] = output[column].fillna("N/A").replace("", "N/A")
    return output


def format_advanced_value(value: object, kind: str) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return str(value) if str(value).strip() else "N/A"
    if kind == "int":
        return f"{int(round(float(numeric))):,}"
    if kind == "percent":
        return f"{float(numeric):.1f}%"
    if kind == "decimal":
        return f"{float(numeric):.2f}"
    return str(value)


def available_match_centre_scopes() -> list[Path]:
    if not MATCH_CENTRE_PROCESSED_ROOT.exists():
        return []
    scopes = [
        path
        for path in MATCH_CENTRE_PROCESSED_ROOT.iterdir()
        if path.is_dir() and (path / "all_matches.csv").exists()
    ]
    return sorted(scopes, key=lambda path: path.stat().st_mtime, reverse=True)


def match_centre_scope_signature(scope_path: Path) -> tuple[tuple[str, float], ...]:
    if not scope_path.exists():
        return tuple()
    return tuple(
        sorted(
            (path.name, path.stat().st_mtime)
            for path in scope_path.glob("*.csv")
            if path.is_file()
        )
    )


@st.cache_data(show_spinner=False)
def load_match_centre_archive(scope_name: str, _signature: tuple[tuple[str, float], ...]) -> dict[str, pd.DataFrame]:
    scope_path = MATCH_CENTRE_PROCESSED_ROOT / scope_name
    table_names = [
        "all_matches",
        "all_match_innings",
        "all_scorecard_batting",
        "all_scorecard_bowling",
        "all_match_officials",
        "all_ball_by_ball",
        "all_overs",
        "all_partnerships",
    ]
    return {name.removeprefix("all_"): read_match_centre_csv(scope_path / f"{name}.csv") for name in table_names}


def read_match_centre_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def build_match_archive_frame(matches: pd.DataFrame) -> pd.DataFrame:
    from src.data.name_normalization import normalize_ground_name, normalize_opponent_club_name

    output = matches.copy()
    for column in [
        "home_team_name",
        "away_team_name",
        "home_team_id",
        "away_team_id",
        "grade_name",
        "venue_name",
        "result_text",
        "round_name",
        "first_match_day",
        "is_ball_by_ball",
    ]:
        if column not in output:
            output[column] = pd.NA

    output["match_date"] = pd.to_datetime(output["first_match_day"], errors="coerce", utc=True)
    output["match_date_display"] = output["match_date"].dt.strftime("%d %b %Y").fillna("Date TBC")
    fvcc_is_home = output["home_team_name"].map(is_fvcc_team_name)
    output["fvcc_team_id"] = output["home_team_id"].where(fvcc_is_home, output["away_team_id"])
    output["fvcc_team_name"] = output["home_team_name"].where(fvcc_is_home, output["away_team_name"]).fillna("FVCC")
    output["opponent_team_id"] = output["away_team_id"].where(fvcc_is_home, output["home_team_id"])
    output["opponent_name"] = (
        output["away_team_name"].where(fvcc_is_home, output["home_team_name"]).map(normalize_opponent_club_name)
    )
    output["venue_name"] = output["venue_name"].map(normalize_ground_name)
    output["is_ball_by_ball_bool"] = output["is_ball_by_ball"].map(parse_bool)
    output["ball_by_ball_badge"] = output["is_ball_by_ball_bool"].map(lambda value: "Yes" if value else "No")
    output["match_title"] = output["fvcc_team_name"].fillna("FVCC") + " vs " + output["opponent_name"].fillna("Unknown opponent")
    output["match_selector_label"] = (
        output["match_date_display"].astype(str)
        + " - "
        + output["fvcc_team_name"].astype(str)
        + " vs "
        + output["opponent_name"].astype(str)
        + " - "
        + output["result_text"].fillna("Result unavailable").astype(str)
    )
    output = output.sort_values(["match_date", "grade_name", "fvcc_team_name"], ascending=[False, True, True])
    return output.reset_index(drop=True)


def render_match_centre_filters(matches: pd.DataFrame) -> pd.DataFrame:
    with st.container(key="match_centre_filters"):
        filter_cols = st.columns([1.1, 1.0, 1.2, 1.2, 0.9], gap="small")
        team = filter_cols[0].selectbox("Team", ["All"] + sorted_options(matches["fvcc_team_name"]))
        grade = filter_cols[1].selectbox("Grade", ["All"] + sorted_options(matches["grade_name"]))
        opponent = filter_cols[2].selectbox("Opponent", ["All"] + sorted_options(matches["opponent_name"]))
        venue = filter_cols[3].selectbox("Venue", ["All"] + sorted_options(matches["venue_name"]))
        ball_by_ball = filter_cols[4].selectbox("Ball-by-ball available", ["All", "Yes", "No"])

    filtered = matches.copy()
    if team != "All":
        filtered = filtered[filtered["fvcc_team_name"] == team]
    if grade != "All":
        filtered = filtered[filtered["grade_name"] == grade]
    if opponent != "All":
        filtered = filtered[filtered["opponent_name"] == opponent]
    if venue != "All":
        filtered = filtered[filtered["venue_name"] == venue]
    if ball_by_ball != "All":
        filtered = filtered[filtered["ball_by_ball_badge"] == ball_by_ball]
    return filtered


def render_match_centre_detail(match: pd.Series, data: dict[str, pd.DataFrame]) -> None:
    match_id = str(match.get("match_id", ""))
    st.markdown("---")
    badge = "Ball-by-ball available" if bool(match.get("is_ball_by_ball_bool")) else "Scorecard only"
    st.markdown(f"## {html.escape(str(match.get('match_title', 'Selected match')))}")
    detail_cols = st.columns(4)
    detail_cols[0].metric("Date", safe_display(match.get("match_date_display")))
    detail_cols[1].metric("Grade", safe_display(match.get("grade_name")))
    detail_cols[2].metric("Round", safe_display(match.get("round_name")))
    detail_cols[3].metric("Mode", badge)
    st.caption(
        " | ".join(
            part
            for part in [
                f"Venue: {safe_display(match.get('venue_name'))}",
                f"Result: {safe_display(match.get('result_text'))}",
            ]
            if part
        )
    )
    render_match_officials(match_id, data["match_officials"])
    match_context = build_selected_match_context(match, data)
    render_match_story(match, match_context)
    render_player_insights(match, data)
    render_records_lab(data)
    with st.expander("View raw scorecard", expanded=False):
        render_match_scorecards(match, data)


def build_selected_match_context(match: pd.Series, data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    match_id = str(match.get("match_id", ""))
    fvcc_team_id = str(match.get("fvcc_team_id", ""))
    innings = match_rows(data["match_innings"], match_id)
    batting = add_innings_context(match_rows(data["scorecard_batting"], match_id), innings)
    bowling = add_innings_context(match_rows(data["scorecard_bowling"], match_id), innings)
    batting = calculate_batting_contribution_percentage(batting, innings)
    bowling = calculate_bowling_impact_score(bowling)
    ball_by_ball = match_rows(data["ball_by_ball"], match_id)
    overs = match_rows(data["overs"], match_id)
    partnerships = match_rows(data["partnerships"], match_id)
    return {
        "innings": innings,
        "batting": batting,
        "bowling": bowling,
        "fvcc_batting": team_rows(batting, fvcc_team_id),
        "fvcc_bowling": team_rows(bowling, fvcc_team_id),
        "ball_by_ball": ball_by_ball,
        "overs": overs,
        "partnerships": partnerships,
    }


def render_match_story(match: pd.Series, context: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Match Story")
    fvcc_batting = context["fvcc_batting"]
    fvcc_bowling = context["fvcc_bowling"]
    partnerships = context["partnerships"]
    ball_by_ball = context["ball_by_ball"]
    overs = context["overs"]
    fvcc_team_id = str(match.get("fvcc_team_id", ""))

    top_batter = top_row(fvcc_batting, "contribution_pct")
    top_bowler = top_row(fvcc_bowling, "bowling_impact_score")
    support = biggest_batting_support(fvcc_batting, partnerships, fvcc_team_id)
    all_rounder = top_row(calculate_all_round_impact(fvcc_batting, fvcc_bowling), "all_round_impact")

    cards = [
        (
            "Top batting contribution",
            insight_player_label(top_batter),
            batting_contribution_label(top_batter),
        ),
        (
            "Top bowling impact",
            insight_player_label(top_bowler),
            bowling_impact_label(top_bowler),
        ),
        (
            "Biggest batting support",
            support.get("label", "-"),
            support.get("detail", "No support innings found."),
        ),
        (
            "Best all-round contributor",
            insight_player_label(all_rounder),
            all_round_label(all_rounder),
        ),
        (
            "Ball-by-ball",
            "Available" if bool(match.get("is_ball_by_ball_bool")) else "Not available",
            "Optional enrichment layer" if bool(match.get("is_ball_by_ball_bool")) else "Scorecard insights still available",
        ),
    ]
    render_insight_cards(cards)

    if not bool(match.get("is_ball_by_ball_bool")) or ball_by_ball.empty:
        st.info("Advanced ball-by-ball insights are not available for this match, but scorecard-based insights are available.")
        return

    milestones = detect_quickest_milestones(ball_by_ball, fvcc_team_id)
    biggest_over = biggest_fvcc_over(overs, fvcc_team_id)
    burst = detect_wicket_burst(ball_by_ball, fvcc_team_id)
    dot_pct = calculate_dot_ball_percentage(ball_by_ball, fvcc_team_id)
    boundary_pct = calculate_boundary_percentage(ball_by_ball, fvcc_team_id)
    advanced_cards = [
        ("Quickest milestone", milestone_label(milestones), milestone_detail(milestones)),
        ("Biggest FVCC over", biggest_over.get("label", "-"), biggest_over.get("detail", "No over data found.")),
        ("Wicket burst", burst.get("label", "-"), burst.get("detail", "No 2-wicket burst found.")),
        ("FVCC bowling dots", format_percent(dot_pct), "Legal deliveries with no runs scored"),
        ("FVCC batting boundaries", format_percent(boundary_pct), "Legal balls that went for 4 or 6"),
    ]
    render_insight_cards(advanced_cards)


def render_insight_cards(cards: list[tuple[str, str, str]]) -> None:
    columns = st.columns(len(cards))
    for column, (title, value, detail) in zip(columns, cards):
        with column:
            st.metric(title, value)
            st.caption(detail)


def render_player_insights(match: pd.Series, data: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Player Insights")
    matches = build_match_archive_frame(data["matches"])
    batting = calculate_batting_contribution_percentage(
        add_match_context(data["scorecard_batting"], matches),
        data["match_innings"],
    )
    bowling = calculate_bowling_impact_score(add_match_context(data["scorecard_bowling"], matches))
    fvcc_team_ids = set(matches["fvcc_team_id"].dropna().astype(str).tolist()) if not matches.empty else set()
    fvcc_batting = batting[batting["team_id"].astype(str).isin(fvcc_team_ids)].copy() if "team_id" in batting else pd.DataFrame()
    fvcc_bowling = bowling[bowling["team_id"].astype(str).isin(fvcc_team_ids)].copy() if "team_id" in bowling else pd.DataFrame()

    tab1, tab2, tab3, tab4 = st.tabs(["Runs", "Wickets", "Best Innings", "Dismissals"])
    with tab1:
        left, right = st.columns(2)
        with left:
            render_compact_insight_table(calculate_player_vs_opponent(fvcc_batting, "runs_scored"), "Runs by opponent")
        with right:
            render_compact_insight_table(calculate_player_vs_venue(fvcc_batting, "runs_scored"), "Runs by venue")
    with tab2:
        left, right = st.columns(2)
        with left:
            render_compact_insight_table(calculate_player_vs_opponent(fvcc_bowling, "wickets_taken"), "Wickets by opponent")
        with right:
            render_compact_insight_table(calculate_player_vs_venue(fvcc_bowling, "wickets_taken"), "Wickets by venue")
    with tab3:
        best_batting = fvcc_batting.sort_values(["contribution_pct", "runs_scored"], ascending=[False, False])
        render_compact_insight_table(
            display_table(
                best_batting.head(10),
                ["player_name", "opponent_name", "venue_name", "runs_scored", "team_total", "contribution_pct"],
                {
                    "player_name": "Player",
                    "opponent_name": "Opponent",
                    "venue_name": "Venue",
                    "runs_scored": "Runs",
                    "team_total": "Team Runs",
                    "contribution_pct": "Contribution %",
                },
            ),
            "Best batting innings by contribution",
        )
        best_bowling = fvcc_bowling.sort_values(["wickets_taken", "runs_conceded"], ascending=[False, True])
        render_compact_insight_table(
            display_table(
                best_bowling.head(10),
                ["player_name", "opponent_name", "wickets_taken", "runs_conceded", "overs_bowled", "economy"],
                {
                    "player_name": "Player",
                    "opponent_name": "Opponent",
                    "wickets_taken": "Wickets",
                    "runs_conceded": "Runs",
                    "overs_bowled": "Overs",
                    "economy": "Economy",
                },
            ),
            "Best bowling figures by opponent",
        )
    with tab4:
        dismissals = dismissal_type_breakdown(fvcc_batting)
        render_compact_insight_table(dismissals, "Dismissal type breakdown")


def render_records_lab(data: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Records Lab")
    matches = build_match_archive_frame(data["matches"])
    batting = calculate_batting_contribution_percentage(
        add_match_context(data["scorecard_batting"], matches),
        data["match_innings"],
    )
    bowling = calculate_bowling_impact_score(add_match_context(data["scorecard_bowling"], matches))
    fvcc_team_ids = set(matches["fvcc_team_id"].dropna().astype(str).tolist()) if not matches.empty else set()
    fvcc_batting = batting[batting["team_id"].astype(str).isin(fvcc_team_ids)].copy() if "team_id" in batting else pd.DataFrame()
    fvcc_bowling = bowling[bowling["team_id"].astype(str).isin(fvcc_team_ids)].copy() if "team_id" in bowling else pd.DataFrame()

    tabs = st.tabs(["Batting", "Bowling", "All-round", "Ball-by-ball"])
    with tabs[0]:
        left, right = st.columns(2)
        with left:
            render_compact_insight_table(record_batting_contribution(fvcc_batting), "Highest FVCC contribution percentage")
            render_compact_insight_table(record_batting_by_dimension(fvcc_batting, "venue_name", "Venue"), "Best FVCC innings by venue")
        with right:
            render_compact_insight_table(record_batting_by_dimension(fvcc_batting, "opponent_name", "Opponent"), "Best FVCC innings by opponent")
    with tabs[1]:
        left, right = st.columns(2)
        with left:
            render_compact_insight_table(record_bowling_by_dimension(fvcc_bowling, "venue_name", "Venue"), "Best FVCC bowling figures by venue")
        with right:
            render_compact_insight_table(record_bowling_by_dimension(fvcc_bowling, "opponent_name", "Opponent"), "Best FVCC bowling figures by opponent")
    with tabs[2]:
        render_compact_insight_table(record_all_round_matches(fvcc_batting, fvcc_bowling), "Best all-round match performance")
    with tabs[3]:
        if data["ball_by_ball"].empty:
            st.info("Fastest milestones and bowling phase records need ball-by-ball data.")
            return
        milestones = all_fastest_milestones(data["ball_by_ball"], fvcc_team_ids)
        phase = best_opening_spell(data["overs"], fvcc_team_ids)
        left, right = st.columns(2)
        with left:
            render_compact_insight_table(milestones[milestones["Milestone"].isin(["50", "100"])], "Fastest 50s and 100s")
        with right:
            render_compact_insight_table(phase, "Best opening spell / phase")


def render_compact_insight_table(table: pd.DataFrame, title: str) -> None:
    st.markdown(f"#### {html.escape(title)}")
    if table.empty:
        st.info("No data available for this insight yet.")
        return
    st.dataframe(
        coerce_display_numbers(table),
        use_container_width=True,
        hide_index=True,
        height=table_height(table, max_rows=8),
        column_config=numeric_column_config(table.columns.tolist()),
    )


def render_match_officials(match_id: str, officials: pd.DataFrame) -> None:
    if officials.empty or "match_id" not in officials:
        st.caption("Officials: not available.")
        return
    rows = officials[officials["match_id"].astype(str) == match_id].copy()
    if rows.empty:
        st.caption("Officials: not available.")
        return
    labels = []
    for _, row in rows.iterrows():
        role = safe_display(row.get("role"), "Official")
        name = safe_display(row.get("official_name"), safe_display(row.get("official_short_name"), "Unknown"))
        labels.append(f"{role}: {name}")
    st.caption("Officials: " + " | ".join(labels))


def render_match_scorecards(match: pd.Series, data: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Scorecards")
    fvcc_team_id = str(match.get("fvcc_team_id", ""))
    opponent_team_id = str(match.get("opponent_team_id", ""))
    match_id = str(match.get("match_id", ""))
    innings = match_rows(data["match_innings"], match_id)
    batting = add_innings_context(match_rows(data["scorecard_batting"], match_id), innings)
    bowling = add_innings_context(match_rows(data["scorecard_bowling"], match_id), innings)

    tabs = st.tabs(["FVCC Batting", "FVCC Bowling", "Opposition Batting", "Opposition Bowling"])
    with tabs[0]:
        render_scorecard_batting_table(team_rows(batting, fvcc_team_id), "No FVCC batting data is available for this match.")
    with tabs[1]:
        render_scorecard_bowling_table(team_rows(bowling, fvcc_team_id), "No FVCC bowling data is available for this match.")
    with tabs[2]:
        render_scorecard_batting_table(team_rows(batting, opponent_team_id), "No opposition batting data is available for this match.")
    with tabs[3]:
        render_scorecard_bowling_table(team_rows(bowling, opponent_team_id), "No opposition bowling data is available for this match.")


def render_scorecard_batting_table(rows: pd.DataFrame, empty_message: str) -> None:
    if rows.empty:
        st.info(empty_message)
        return
    display = rows.sort_values(["innings_order", "bat_order"]).copy()
    columns = ["player_name", "runs_scored", "balls_faced", "fours_scored", "sixes_scored", "strike_rate", "dismissal_text"]
    rename_map = {
        "player_name": "Player",
        "runs_scored": "Runs",
        "balls_faced": "Balls",
        "fours_scored": "4s",
        "sixes_scored": "6s",
        "strike_rate": "SR",
        "dismissal_text": "Dismissal",
    }
    if display["innings_name"].nunique(dropna=True) > 1:
        columns.insert(0, "innings_name")
        rename_map["innings_name"] = "Innings"
    table = display_table(display, columns, rename_map)
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=table_height(table, max_rows=12),
        column_config=numeric_column_config(table.columns.tolist()),
    )


def render_scorecard_bowling_table(rows: pd.DataFrame, empty_message: str) -> None:
    if rows.empty:
        st.info(empty_message)
        return
    display = rows.sort_values(["innings_order", "bowl_order"]).copy()
    columns = ["player_name", "overs_bowled", "maidens_bowled", "runs_conceded", "wickets_taken", "economy", "wides", "no_balls"]
    rename_map = {
        "player_name": "Player",
        "overs_bowled": "Overs",
        "maidens_bowled": "Maidens",
        "runs_conceded": "Runs",
        "wickets_taken": "Wickets",
        "economy": "Economy",
        "wides": "Wides",
        "no_balls": "No-balls",
    }
    if display["innings_name"].nunique(dropna=True) > 1:
        columns.insert(0, "innings_name")
        rename_map["innings_name"] = "Innings"
    table = display_table(display, columns, rename_map)
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        height=table_height(table, max_rows=12),
        column_config=numeric_column_config(table.columns.tolist()),
    )


def render_ball_by_ball_summary(match: pd.Series, data: dict[str, pd.DataFrame]) -> None:
    render_section_heading("Ball-by-ball Summary")
    if not bool(match.get("is_ball_by_ball_bool")):
        st.info("Ball-by-ball data is not available for this match, but scorecard analytics are still available.")
        return
    match_id = str(match.get("match_id", ""))
    ball_events = len(match_rows(data["ball_by_ball"], match_id))
    overs = len(match_rows(data["overs"], match_id))
    partnerships = len(match_rows(data["partnerships"], match_id))
    cols = st.columns(3)
    cols[0].metric("Ball events", f"{ball_events:,}")
    cols[1].metric("Overs rows", f"{overs:,}")
    cols[2].metric("Partnership rows", f"{partnerships:,}")


def calculate_team_total(innings: pd.DataFrame, innings_id: object, fallback_runs: object = 0) -> float:
    if innings.empty or "innings_id" not in innings or "runs_scored" not in innings:
        return float(pd.to_numeric(pd.Series([fallback_runs]), errors="coerce").fillna(0).iloc[0])
    rows = innings[innings["innings_id"].astype(str) == str(innings_id)]
    if rows.empty:
        return float(pd.to_numeric(pd.Series([fallback_runs]), errors="coerce").fillna(0).iloc[0])
    return float(pd.to_numeric(rows["runs_scored"], errors="coerce").fillna(0).max())


def calculate_batting_contribution_percentage(batting: pd.DataFrame, innings: pd.DataFrame) -> pd.DataFrame:
    if batting.empty:
        return batting
    output = batting.copy()
    output["runs_scored"] = pd.to_numeric(output.get("runs_scored"), errors="coerce").fillna(0)
    team_totals = []
    for _, row in output.iterrows():
        team_total = calculate_team_total(innings, row.get("innings_id"), output.loc[output["innings_id"] == row.get("innings_id"), "runs_scored"].sum())
        team_totals.append(team_total)
    output["team_total"] = team_totals
    output["contribution_pct"] = output.apply(
        lambda row: (float(row["runs_scored"]) / float(row["team_total"]) * 100) if float(row["team_total"] or 0) > 0 else 0,
        axis=1,
    )
    return output


def calculate_bowling_impact_score(bowling: pd.DataFrame) -> pd.DataFrame:
    if bowling.empty:
        return bowling
    output = bowling.copy()
    output["wickets_taken"] = pd.to_numeric(output.get("wickets_taken"), errors="coerce").fillna(0)
    output["economy"] = pd.to_numeric(output.get("economy"), errors="coerce").fillna(0)
    output["maidens_bowled"] = pd.to_numeric(output.get("maidens_bowled"), errors="coerce").fillna(0)
    output["overs_bowled"] = pd.to_numeric(output.get("overs_bowled"), errors="coerce").fillna(0)
    output["bowling_impact_score"] = (
        output["wickets_taken"] * 25
        + output["maidens_bowled"] * 4
        + output["overs_bowled"].clip(upper=8)
        - output["economy"] * 2
    )
    return output


def calculate_all_round_impact(batting: pd.DataFrame, bowling: pd.DataFrame) -> pd.DataFrame:
    bat = pd.DataFrame(columns=["participant_id", "player_name", "runs_scored", "contribution_pct"])
    bowl = pd.DataFrame(columns=["participant_id", "player_name", "wickets_taken", "bowling_impact_score"])
    if not batting.empty:
        bat = batting.copy()
        bat["runs_scored"] = pd.to_numeric(bat.get("runs_scored"), errors="coerce").fillna(0)
        bat["contribution_pct"] = pd.to_numeric(bat.get("contribution_pct"), errors="coerce").fillna(0)
        bat = bat.groupby(["participant_id", "player_name"], dropna=False, as_index=False).agg({"runs_scored": "sum", "contribution_pct": "max"})
    if not bowling.empty:
        bowl = bowling.copy()
        bowl["wickets_taken"] = pd.to_numeric(bowl.get("wickets_taken"), errors="coerce").fillna(0)
        bowl["bowling_impact_score"] = pd.to_numeric(bowl.get("bowling_impact_score"), errors="coerce").fillna(0)
        bowl = bowl.groupby(["participant_id", "player_name"], dropna=False, as_index=False).agg({"wickets_taken": "sum", "bowling_impact_score": "max"})
    combined = bat.merge(bowl, on=["participant_id", "player_name"], how="outer").fillna(0)
    if combined.empty:
        return combined
    combined = combined[(combined["runs_scored"] > 0) & ((combined["wickets_taken"] > 0) | (combined["bowling_impact_score"] > 0))].copy()
    combined["all_round_impact"] = combined["runs_scored"] + combined["contribution_pct"] * 0.4 + combined["wickets_taken"] * 25 + combined["bowling_impact_score"]
    return combined


def detect_quickest_milestones(ball_by_ball: pd.DataFrame, fvcc_team_id: str) -> pd.DataFrame:
    if ball_by_ball.empty:
        return pd.DataFrame(columns=["Milestone", "Player", "Balls", "Runs"])
    balls = ball_by_ball[ball_by_ball["batting_team_id"].astype(str) == str(fvcc_team_id)].copy()
    if balls.empty:
        return pd.DataFrame(columns=["Milestone", "Player", "Balls", "Runs"])
    for column in ["runs_bat", "is_legal_delivery"]:
        if column not in balls:
            balls[column] = 0
    balls["runs_bat"] = pd.to_numeric(balls["runs_bat"], errors="coerce").fillna(0)
    balls["legal_ball"] = balls["is_legal_delivery"].map(parse_bool).astype(int)
    rows = []
    for _, group in balls.groupby("striker_participant_id", dropna=False):
        group = group.sort_values(["innings_order", "over_number", "ball_number"])
        group["batter_runs"] = group["runs_bat"].cumsum()
        group["balls_faced"] = group["legal_ball"].cumsum()
        player = safe_display(group["striker_short_name"].dropna().iloc[0] if not group["striker_short_name"].dropna().empty else "")
        for milestone in [25, 50, 100]:
            reached = group[group["batter_runs"] >= milestone]
            if reached.empty:
                continue
            row = reached.iloc[0]
            rows.append({"Milestone": str(milestone), "Player": player, "Balls": int(row["balls_faced"]), "Runs": int(row["batter_runs"])})
    if not rows:
        return pd.DataFrame(columns=["Milestone", "Player", "Balls", "Runs"])
    return pd.DataFrame(rows).sort_values(["Milestone", "Balls", "Runs"], ascending=[True, True, False]).drop_duplicates("Milestone")


def calculate_dot_ball_percentage(ball_by_ball: pd.DataFrame, fvcc_team_id: str) -> float | None:
    balls = legal_ball_rows(ball_by_ball, "bowling_team_id", fvcc_team_id)
    if balls.empty:
        return None
    totals = pd.to_numeric(balls.get("total_runs"), errors="coerce").fillna(0)
    return float((totals == 0).mean() * 100)


def calculate_boundary_percentage(ball_by_ball: pd.DataFrame, fvcc_team_id: str) -> float | None:
    balls = legal_ball_rows(ball_by_ball, "batting_team_id", fvcc_team_id)
    if balls.empty:
        return None
    bat_runs = pd.to_numeric(balls.get("runs_bat"), errors="coerce").fillna(0)
    return float(bat_runs.isin([4, 6]).mean() * 100)


def calculate_player_vs_opponent(frame: pd.DataFrame, value_column: str) -> pd.DataFrame:
    return calculate_player_dimension(frame, "opponent_name", "Opponent", value_column)


def calculate_player_vs_venue(frame: pd.DataFrame, value_column: str) -> pd.DataFrame:
    return calculate_player_dimension(frame, "venue_name", "Venue", value_column)


def calculate_player_dimension(frame: pd.DataFrame, dimension: str, dimension_label: str, value_column: str) -> pd.DataFrame:
    if frame.empty or value_column not in frame:
        return pd.DataFrame()
    output = frame.copy()
    output[value_column] = pd.to_numeric(output[value_column], errors="coerce").fillna(0)
    grouped = (
        output.groupby(["player_name", dimension], dropna=False, as_index=False)
        .agg({value_column: "sum", "match_id": "nunique"})
        .rename(columns={"player_name": "Player", dimension: dimension_label, value_column: "Value", "match_id": "Matches"})
        .sort_values("Value", ascending=False)
        .head(10)
    )
    metric_name = "Runs" if value_column == "runs_scored" else "Wickets"
    return grouped.rename(columns={"Value": metric_name})


def legal_ball_rows(ball_by_ball: pd.DataFrame, team_column: str, team_id: str) -> pd.DataFrame:
    if ball_by_ball.empty or team_column not in ball_by_ball:
        return pd.DataFrame()
    balls = ball_by_ball[ball_by_ball[team_column].astype(str) == str(team_id)].copy()
    if "is_legal_delivery" not in balls:
        return pd.DataFrame()
    return balls[balls["is_legal_delivery"].map(parse_bool)].copy()


def top_row(frame: pd.DataFrame, column: str) -> pd.Series:
    if frame.empty or column not in frame:
        return pd.Series(dtype="object")
    ranked = frame.copy()
    ranked[column] = pd.to_numeric(ranked[column], errors="coerce").fillna(0)
    ranked = ranked.sort_values(column, ascending=False)
    return ranked.iloc[0] if not ranked.empty else pd.Series(dtype="object")


def insight_player_label(row: pd.Series) -> str:
    return safe_display(row.get("player_name") if not row.empty else None)


def batting_contribution_label(row: pd.Series) -> str:
    if row.empty:
        return "No batting scorecard data"
    return f"{int(float(row.get('runs_scored', 0))):,} runs, {float(row.get('contribution_pct', 0)):.1f}% of team runs"


def bowling_impact_label(row: pd.Series) -> str:
    if row.empty:
        return "No bowling scorecard data"
    return f"{int(float(row.get('wickets_taken', 0)))} wickets, econ {float(row.get('economy', 0)):.2f}"


def all_round_label(row: pd.Series) -> str:
    if row.empty:
        return "No all-round scorecard impact found"
    return f"{int(float(row.get('runs_scored', 0)))} runs and {int(float(row.get('wickets_taken', 0)))} wickets"


def biggest_batting_support(batting: pd.DataFrame, partnerships: pd.DataFrame, fvcc_team_id: str) -> dict[str, str]:
    if not partnerships.empty and "batting_team_id" in partnerships:
        rows = partnerships[partnerships["batting_team_id"].astype(str) == str(fvcc_team_id)].copy()
        if not rows.empty:
            rows["runs"] = pd.to_numeric(rows.get("runs"), errors="coerce").fillna(0)
            best = rows.sort_values("runs", ascending=False).iloc[0]
            names = " & ".join([safe_display(best.get("batter_1_name")), safe_display(best.get("batter_2_name"))]).replace(" -", "")
            return {"label": names, "detail": f"{int(best['runs'])} run partnership"}
    if batting.empty:
        return {"label": "-", "detail": "No batting support data."}
    rows = batting.copy()
    rows["runs_scored"] = pd.to_numeric(rows.get("runs_scored"), errors="coerce").fillna(0)
    rows = rows.sort_values("runs_scored", ascending=False)
    if len(rows) < 2:
        return {"label": "-", "detail": "No second scorer found."}
    second = rows.iloc[1]
    return {"label": safe_display(second.get("player_name")), "detail": f"{int(second['runs_scored'])} runs"}


def milestone_label(milestones: pd.DataFrame) -> str:
    if milestones.empty:
        return "-"
    row = milestones.iloc[0]
    return f"{row['Player']} to {row['Milestone']}"


def milestone_detail(milestones: pd.DataFrame) -> str:
    if milestones.empty:
        return "No 25/50/100 milestone found."
    row = milestones.iloc[0]
    return f"Reached in {int(row['Balls'])} balls"


def biggest_fvcc_over(overs: pd.DataFrame, fvcc_team_id: str) -> dict[str, str]:
    if overs.empty or "batting_team_id" not in overs:
        return {"label": "-", "detail": "No over data found."}
    rows = overs[overs["batting_team_id"].astype(str) == str(fvcc_team_id)].copy()
    if rows.empty:
        return {"label": "-", "detail": "No FVCC batting over data found."}
    rows["runs"] = pd.to_numeric(rows.get("runs"), errors="coerce").fillna(0)
    best = rows.sort_values("runs", ascending=False).iloc[0]
    return {"label": f"{int(best['runs'])} runs", "detail": f"Over {int(float(best.get('over_number', 0))) + 1}"}


def detect_wicket_burst(ball_by_ball: pd.DataFrame, fvcc_team_id: str, window: int = 12) -> dict[str, str]:
    balls = legal_ball_rows(ball_by_ball, "bowling_team_id", fvcc_team_id)
    if balls.empty or "is_wicket" not in balls:
        return {"label": "-", "detail": "No wicket burst found."}
    balls = balls.sort_values(["innings_order", "over_number", "ball_number"]).reset_index(drop=True)
    balls["wicket_flag"] = balls["is_wicket"].map(parse_bool).astype(int)
    for start in range(0, max(len(balls) - 1, 0)):
        window_rows = balls.iloc[start : start + window]
        wickets = int(window_rows["wicket_flag"].sum())
        if wickets >= 2:
            bowler = safe_display(window_rows[window_rows["wicket_flag"] == 1].iloc[0].get("bowler_short_name"))
            return {"label": f"{wickets} wickets", "detail": f"Within {len(window_rows)} legal balls, led by {bowler}"}
    return {"label": "-", "detail": "No 2-wicket burst found."}


def format_percent(value: float | None) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):.1f}%"


def add_match_context(frame: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or matches.empty or "match_id" not in frame:
        return frame.copy()
    columns = [
        "match_id",
        "match_date_display",
        "fvcc_team_id",
        "opponent_name",
        "venue_name",
        "grade_name",
        "result_text",
    ]
    context = matches[[column for column in columns if column in matches]].drop_duplicates("match_id")
    return frame.merge(context, on="match_id", how="left")


def dismissal_type_breakdown(batting: pd.DataFrame) -> pd.DataFrame:
    if batting.empty or "dismissal_type" not in batting:
        return pd.DataFrame()
    rows = batting.copy()
    rows["dismissal_type"] = rows["dismissal_type"].fillna("Not out / unknown").replace("", "Not out / unknown")
    return (
        rows.groupby("dismissal_type", as_index=False)
        .size()
        .rename(columns={"dismissal_type": "Dismissal", "size": "Count"})
        .sort_values("Count", ascending=False)
    )


def record_batting_contribution(batting: pd.DataFrame) -> pd.DataFrame:
    if batting.empty:
        return pd.DataFrame()
    return display_table(
        batting.sort_values(["contribution_pct", "runs_scored"], ascending=[False, False]).head(10),
        ["player_name", "opponent_name", "venue_name", "runs_scored", "team_total", "contribution_pct"],
        {
            "player_name": "Player",
            "opponent_name": "Opponent",
            "venue_name": "Venue",
            "runs_scored": "Runs",
            "team_total": "Team Runs",
            "contribution_pct": "Contribution %",
        },
    )


def record_batting_by_dimension(batting: pd.DataFrame, dimension: str, label: str) -> pd.DataFrame:
    if batting.empty or dimension not in batting:
        return pd.DataFrame()
    rows = batting.sort_values(["runs_scored", "contribution_pct"], ascending=[False, False]).drop_duplicates(dimension).head(10)
    return display_table(
        rows,
        [dimension, "player_name", "runs_scored", "contribution_pct"],
        {dimension: label, "player_name": "Player", "runs_scored": "Runs", "contribution_pct": "Contribution %"},
    )


def record_bowling_by_dimension(bowling: pd.DataFrame, dimension: str, label: str) -> pd.DataFrame:
    if bowling.empty or dimension not in bowling:
        return pd.DataFrame()
    rows = bowling.sort_values(["wickets_taken", "runs_conceded"], ascending=[False, True]).drop_duplicates(dimension).head(10)
    return display_table(
        rows,
        [dimension, "player_name", "wickets_taken", "runs_conceded", "overs_bowled", "economy"],
        {
            dimension: label,
            "player_name": "Player",
            "wickets_taken": "Wickets",
            "runs_conceded": "Runs",
            "overs_bowled": "Overs",
            "economy": "Economy",
        },
    )


def record_all_round_matches(batting: pd.DataFrame, bowling: pd.DataFrame) -> pd.DataFrame:
    if batting.empty and bowling.empty:
        return pd.DataFrame()
    batting_summary = batting.groupby(["match_id", "player_name"], as_index=False).agg({"runs_scored": "sum", "contribution_pct": "max"})
    bowling_summary = bowling.groupby(["match_id", "player_name"], as_index=False).agg({"wickets_taken": "sum", "bowling_impact_score": "max"})
    combined = batting_summary.merge(bowling_summary, on=["match_id", "player_name"], how="outer").fillna(0)
    combined = combined[(combined["runs_scored"] > 0) & (combined["wickets_taken"] > 0)].copy()
    if combined.empty:
        return pd.DataFrame()
    combined["all_round_impact"] = combined["runs_scored"] + combined["contribution_pct"] * 0.4 + combined["wickets_taken"] * 25 + combined["bowling_impact_score"]
    return display_table(
        combined.sort_values("all_round_impact", ascending=False).head(10),
        ["player_name", "runs_scored", "wickets_taken", "all_round_impact"],
        {"player_name": "Player", "runs_scored": "Runs", "wickets_taken": "Wickets", "all_round_impact": "Impact"},
    )


def all_fastest_milestones(ball_by_ball: pd.DataFrame, fvcc_team_ids: set[str]) -> pd.DataFrame:
    frames = [detect_quickest_milestones(ball_by_ball, team_id) for team_id in fvcc_team_ids]
    frames = [frame for frame in frames if not frame.empty]
    if not frames:
        return pd.DataFrame(columns=["Milestone", "Player", "Balls", "Runs"])
    return pd.concat(frames, ignore_index=True).sort_values(["Milestone", "Balls", "Runs"], ascending=[True, True, False]).head(20)


def best_opening_spell(overs: pd.DataFrame, fvcc_team_ids: set[str]) -> pd.DataFrame:
    if overs.empty or "bowling_team_id" not in overs:
        return pd.DataFrame()
    rows = overs[overs["bowling_team_id"].astype(str).isin(fvcc_team_ids)].copy()
    rows["over_number"] = pd.to_numeric(rows.get("over_number"), errors="coerce").fillna(999)
    rows = rows[rows["over_number"] < 6]
    if rows.empty:
        return pd.DataFrame()
    for column in ["runs", "wickets", "legal_balls"]:
        rows[column] = pd.to_numeric(rows.get(column), errors="coerce").fillna(0)
    grouped = rows.groupby(["match_id", "bowler_short_name"], as_index=False).agg({"runs": "sum", "wickets": "sum", "legal_balls": "sum"})
    grouped["Economy"] = grouped.apply(lambda row: (row["runs"] / (row["legal_balls"] / 6)) if row["legal_balls"] else 0, axis=1)
    grouped = grouped.rename(columns={"bowler_short_name": "Bowler", "runs": "Runs", "wickets": "Wickets", "legal_balls": "Balls"})
    return grouped.sort_values(["Wickets", "Economy"], ascending=[False, True]).head(10)


def add_innings_context(rows: pd.DataFrame, innings: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows
    output = rows.copy()
    if "innings_id" not in output:
        output["innings_id"] = pd.NA
    if innings.empty or "innings_id" not in innings:
        output["innings_name"] = ""
        output["innings_order"] = 0
        return output
    context_columns = ["innings_id", "innings_name", "innings_order"]
    context = innings[[column for column in context_columns if column in innings]].drop_duplicates("innings_id")
    output = output.merge(context, on="innings_id", how="left", suffixes=("", "_context"))
    output["innings_name"] = output.get("innings_name", pd.Series(index=output.index, dtype="object")).fillna("")
    output["innings_order"] = pd.to_numeric(output.get("innings_order"), errors="coerce").fillna(0)
    return output


def match_rows(frame: pd.DataFrame, match_id: str) -> pd.DataFrame:
    if frame.empty or "match_id" not in frame:
        return pd.DataFrame()
    return frame[frame["match_id"].astype(str) == match_id].copy()


def team_rows(frame: pd.DataFrame, team_id: str) -> pd.DataFrame:
    if frame.empty or "team_id" not in frame:
        return pd.DataFrame()
    return frame[frame["team_id"].astype(str) == team_id].copy()


def display_table(frame: pd.DataFrame, columns: list[str], rename_map: dict[str, str]) -> pd.DataFrame:
    output = add_missing_canonical_player_ids(frame)
    player_profile_ids = (
        output["canonical_player_id"].copy()
        if "canonical_player_id" in output and "player_name" in columns
        else pd.Series([""] * len(output), index=output.index)
    )
    for column in columns:
        if column not in output:
            output[column] = pd.NA
    output = output[columns].rename(columns=rename_map)
    if "Player" in output:
        output["Player"] = [
            player_profile_url(player_id, player)
            for player_id, player in zip(player_profile_ids, output["Player"])
        ]
    return coerce_display_numbers(output)


def sorted_options(values: pd.Series) -> list[str]:
    cleaned = values.dropna().astype(str)
    cleaned = cleaned[cleaned.str.strip() != ""]
    return sorted(cleaned.unique().tolist())


def is_fvcc_team_name(value: object) -> bool:
    return "fiji victorian" in str(value).casefold()


def safe_display(value: object, fallback: str = "-") -> str:
    if pd.isna(value) or str(value).strip() == "":
        return fallback
    return str(value)


def render_hall_of_fame_page() -> None:
    started_at = time.perf_counter()
    hall_of_fame_data = get_hall_of_fame_data(metadata_mtime(), player_aliases_mtime(), HALL_OF_FAME_DATA_VERSION)
    log_hof_timing("load prepared Hall of Fame data", started_at)
    if hall_of_fame_data is None:
        st.info("Historical data is not available yet. Refresh local backup to build the Hall of Fame.")
        return
    track_event_once(
        "hall_of_fame_view",
        {"page_slug": "hall-of-fame"},
        key="hall-of-fame-view",
    )

    st.markdown(
        f"""
        <div class="hall-of-fame-page"></div>
        <h1 class="page-title">Hall of Fame 🏆</h1>
        {configured_club_label_html()}
        <div class="page-subtitle">The players who shaped the club’s history.</div>
        <div class="page-note">Players with multiple PlayCricket profiles are merged into one profile.</div>
        """,
        unsafe_allow_html=True,
    )
    render_premiership_records()
    render_hall_of_fame_leaders(hall_of_fame_data["all_time"])
    render_match_winning_performances(hall_of_fame_data)
    render_fastest_batting_milestone_records()
    render_record_holders(hall_of_fame_data)
    render_best_ever_seasons(hall_of_fame_data)
    render_detailed_all_time_records(hall_of_fame_data["detailed_tables"])


def render_hall_of_fame_v2_page() -> None:
    started_at = time.perf_counter()
    hall_of_fame_data = get_hall_of_fame_data(metadata_mtime(), player_aliases_mtime(), HALL_OF_FAME_DATA_VERSION)
    log_hof_timing("load prepared Hall of Fame v2 data", started_at)
    if hall_of_fame_data is None:
        st.info("Historical data is not available yet. Refresh local backup to build the Hall of Fame.")
        return
    track_event_once(
        "hall_of_fame_v2_view",
        {"page_slug": HALL_OF_FAME_V2_QUERY_PAGE},
        key="hall-of-fame-v2-view",
    )

    st.markdown('<div class="hall-of-fame-page hall-of-fame-v2-page"></div>', unsafe_allow_html=True)
    render_hall_of_fame_v2_hero(hall_of_fame_data)
    render_hall_of_fame_v2_nav()
    render_hall_of_fame_v2_premiership_wall()
    render_hall_of_fame_v2_club_legends(hall_of_fame_data["all_time"])
    render_hall_of_fame_v2_iconic_performances(hall_of_fame_data)
    render_hall_of_fame_v2_fastest_verified()
    render_hall_of_fame_v2_record_holders(hall_of_fame_data)
    render_hall_of_fame_v2_greatest_seasons(hall_of_fame_data)
    render_hall_of_fame_v2_detailed_records(hall_of_fame_data["detailed_tables"])
    render_hall_of_fame_v2_recommendations()


def render_hall_of_fame_v2_hero(data: dict[str, object]) -> None:
    kpis = data.get("kpis", {})
    fastest_count = hall_of_fame_v2_verified_fastest_count()
    stats = [
        ("Seasons covered", format_int(kpis.get("total_seasons"))),
        ("Matches recorded", format_int(kpis.get("total_matches"))),
        ("Players recorded", format_int(kpis.get("total_players"))),
        ("Verified fastest records", format_int(fastest_count)),
    ]
    stat_html = "".join(
        '<div class="hof-v2-hero-stat">'
        f"<strong>{html.escape(value or '0')}</strong>"
        f"<span>{html.escape(label)}</span>"
        "</div>"
        for label, value in stats
    )
    st.markdown(
        f"""
        <section class="hof-v2-hero" id="top">
            <div class="hof-v2-hero-grid">
                <div>
                    {configured_club_label_html("hof-v2-eyebrow")}
                    <h1>Hall of Fame 🏛️</h1>
                    <p class="hof-v2-hero-copy">A club record book for FVCC legends, premierships and iconic performances.</p>
                    <div class="hof-v2-source-badges">
                        <span>Scorecard records</span>
                        <span>Verified ball-by-ball</span>
                        <span>Premiership evidence</span>
                    </div>
                </div>
                <div class="hof-v2-hero-stats">{stat_html}</div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def hall_of_fame_v2_verified_fastest_count() -> int:
    milestone_path = batting_milestones_path()
    milestones = load_batting_milestone_records(
        str(milestone_path) if milestone_path else None,
        match_centre_milestones_mtime(),
    )
    if milestones.empty:
        return 0
    columns = [column for column in ["balls_to_50", "balls_to_100"] if column in milestones]
    if not columns:
        return int(len(milestones))
    return int(milestones[columns].notna().any(axis=1).sum())


def render_hall_of_fame_v2_nav() -> None:
    items = [
        ("Premierships", "#premierships"),
        ("Legends", "#legends"),
        ("Records", "#records"),
        ("Performances", "#performances"),
        ("Fastest", "#fastest"),
        ("Seasons", "#seasons"),
        ("Detailed", "#detailed"),
    ]
    links = "".join(
        f'<a href="{html.escape(url, quote=True)}" target="_self" class="{"active" if index == 0 else ""}">{html.escape(label)}</a>'
        for index, (label, url) in enumerate(items)
    )
    st.markdown(f'<nav class="hof-v2-record-nav">{links}</nav>', unsafe_allow_html=True)


def hof_v2_section_heading_html(section_id: str, title: str, copy: str, badge: str = "") -> str:
    badge_html = f'<span class="hof-v2-trust-chip">{html.escape(badge)}</span>' if badge else ""
    return (
        f'<section class="hof-v2-section" id="{html.escape(section_id, quote=True)}">'
        '<div class="hof-v2-section-head">'
        '<div class="hof-v2-section-title">'
        f"<h2>{html.escape(title)}</h2>"
        f"<p>{html.escape(copy)}</p>"
        "</div>"
        f"{badge_html}"
        "</div>"
    )


def render_hall_of_fame_v2_premiership_wall() -> None:
    wins, players = load_premiership_records(premiership_records_signature())
    st.markdown(
        (
            hof_v2_section_heading_html(
                "premierships",
                "Premiership Wall 🏆",
                "The trophy story sits directly below the hero because premierships are club-defining, verified and scorecard-linked.",
                "Premiership evidence",
            )
            + '<div class="hof-v2-grid-2">'
            + hall_of_fame_v2_premiership_wins_card_html(wins)
            + hall_of_fame_v2_player_premierships_card_html(players)
            + "</div></section>"
        ),
        unsafe_allow_html=True,
    )


def hall_of_fame_v2_premiership_wins_card_html(wins: pd.DataFrame) -> str:
    if wins.empty:
        return (
            '<article class="hof-v2-card hof-v2-gold-card">'
            '<div class="hof-v2-kicker">FVCC premiership wins</div>'
            '<p class="hof-v2-muted">Premiership records are being prepared from verified finals scorecards.</p>'
            "</article>"
        )
    rows = wins.copy()
    if "match_date" in rows:
        rows["_date_sort"] = pd.to_datetime(rows["match_date"], errors="coerce", utc=True)
        rows = rows.sort_values(["_date_sort", "season"], ascending=[True, True], na_position="last")
    row_html = "".join(hall_of_fame_v2_premiership_win_row_html(row) for _, row in rows.iterrows())
    return (
        '<article class="hof-v2-card hof-v2-gold-card">'
        '<div class="hof-v2-kicker">FVCC premiership wins</div>'
        f'<div class="hof-v2-timeline">{row_html}</div>'
        "</article>"
    )


def hall_of_fame_v2_premiership_win_row_html(row: pd.Series) -> str:
    season = safe_record_text(row.get("season"), "Unknown season")
    grade = clean_grade_label_for_record(row.get("grade_name")) or "Grade not recorded"
    team = safe_record_text(row.get("fvcc_team_name"), "FVCC")
    opponent = clean_opponent_label(row.get("opponent_team_name"), "Opposition")
    captain = safe_record_text(row.get("captain_name"))
    result = safe_record_text(row.get("result_margin_display")) or safe_record_text(row.get("result_text"), "Won")
    scorecard = scorecard_url_link_html(
        row.get("scoreboard_url"),
        row.get("match_id"),
        label="View scorecard ↗",
        page_slug=HALL_OF_FAME_V2_QUERY_PAGE,
        section_name="premiership_wall",
        class_name="hof-v2-subtle-link",
    )
    captain_text = f"Captain: {captain}" if captain else "Captain not recorded"
    return (
        '<div class="hof-v2-trophy-row">'
        f'<div class="hof-v2-trophy-year">{season_overview_link_html(season)}</div>'
        '<div class="hof-v2-trophy-main">'
        f"<strong>{html.escape(grade)}</strong>"
        f"<span>{html.escape(team)} defeated {html.escape(opponent)} · {html.escape(captain_text)}</span>"
        "</div>"
        '<div class="hof-v2-trophy-result">'
        f'<span class="hof-v2-result-pill">{html.escape(result)}</span>'
        f"{scorecard}"
        "</div>"
        "</div>"
    )


def hall_of_fame_v2_player_premierships_card_html(players: pd.DataFrame) -> str:
    if players.empty:
        return (
            '<article class="hof-v2-card">'
            '<div class="hof-v2-kicker">Most premierships</div>'
            '<h3>Trophy cabinet leaders</h3>'
            '<p class="hof-v2-muted">No verified player premiership records available yet.</p>'
            "</article>"
        )
    rows = players.head(10).copy()
    leader_rows = []
    for rank, (_, row) in enumerate(rows.iterrows(), start=1):
        player = safe_record_text(row.get("display_player_name") or row.get("canonical_player_name"), "Unknown player")
        count = safe_record_int(row.get("premiership_count")) or 0
        leader_rows.append(
            '<div class="hof-v2-rank-row">'
            f'<span class="hof-v2-rank gold">{rank}</span>'
            f"<strong>{player_profile_link_html('', player)}</strong>"
            f"<span>{count:,} premiership{'s' if count != 1 else ''}</span>"
            "</div>"
        )
    return (
        '<article class="hof-v2-card">'
        '<div class="hof-v2-kicker">Most premierships</div>'
        '<h3>Trophy cabinet leaders</h3>'
        f'<div class="hof-v2-leader-list">{"".join(leader_rows)}</div>'
        '<p class="hof-v2-muted">Sorted by premiership count, matches, earliest premiership and player name.</p>'
        "</article>"
    )


def render_hall_of_fame_v2_club_legends(all_time: pd.DataFrame) -> None:
    specs = [
        ("Most matches", "Durability Kings", "Matches", "fielding", "matches"),
        ("Most runs", "Run Mountain", "Runs", "batting", "runs"),
        ("Most wickets", "Wicket Wall", "Wickets", "bowling", "wickets"),
        ("Most catches", "Safe Hands", "Catches", "fielding", "catches"),
    ]
    cards = "".join(hall_of_fame_v2_legend_card_html(all_time, *spec) for spec in specs)
    st.markdown(
        (
            hof_v2_section_heading_html(
                "legends",
                "Club Legends 👑",
                "All-Time Leaders become a more screenshot-worthy legends row while keeping the same trusted rankings.",
                "All-time aggregates",
            )
            + f'<div class="hof-v2-grid-4">{cards}</div></section>'
        ),
        unsafe_allow_html=True,
    )


def hall_of_fame_v2_legend_card_html(
    all_time: pd.DataFrame,
    kicker: str,
    title: str,
    metric: str,
    mode: str,
    unit: str,
) -> str:
    if all_time.empty or metric not in all_time:
        return ""
    leaders = all_time.copy()
    leaders[metric] = pd.to_numeric(leaders[metric], errors="coerce").fillna(0)
    leaders = leaders[leaders[metric] > 0]
    leaders = sort_hof_leaders(leaders, metric, mode).head(3)
    rows = []
    for rank, (_, row) in enumerate(leaders.iterrows(), start=1):
        value = safe_record_int(row.get(metric)) or 0
        rows.append(
            '<div class="hof-v2-rank-row">'
            f'<span class="hof-v2-rank">{rank}</span>'
            f"<strong>{player_profile_link_html(player_id_from_row(row), row['Player'])}</strong>"
            f"<span>{value:,} {html.escape(unit)}</span>"
            "</div>"
        )
    return (
        '<article class="hof-v2-card hof-v2-leader-card">'
        f'<div class="hof-v2-kicker">{html.escape(kicker)}</div>'
        f"<h3>{html.escape(title)}</h3>"
        f'<div class="hof-v2-leader-list">{"".join(rows)}</div>'
        "</article>"
    )


def render_hall_of_fame_v2_iconic_performances(data: dict[str, object]) -> None:
    batting = data.get("iconic_batting", pd.DataFrame())
    bowling = data.get("iconic_bowling", pd.DataFrame())
    batting_card = hall_of_fame_v2_performance_hero_html(batting, "Highest individual score", "batting")
    bowling_card = hall_of_fame_v2_performance_hero_html(bowling, "Best bowling innings", "bowling")
    future_cards = (
        '<article class="hof-v2-card">'
        '<div class="hof-v2-kicker">Recommended future card</div>'
        '<div class="hof-v2-record-player">Best all-round display</div>'
        '<div class="hof-v2-record-value">Runs + wickets impact</div>'
        '<p class="hof-v2-muted">Show only once innings-level data is reliable enough to avoid overclaiming.</p>'
        "</article>"
        '<article class="hof-v2-card">'
        '<div class="hof-v2-kicker">Recommended future card</div>'
        '<div class="hof-v2-record-player">Best fielding display</div>'
        '<div class="hof-v2-record-value">Catches / stumpings / run outs</div>'
        '<p class="hof-v2-muted">Useful if match-level fielding dismissals are consistently available.</p>'
        "</article>"
    )
    st.markdown(
        (
            hof_v2_section_heading_html(
                "performances",
                "Iconic Performances 🌟",
                "Individual brilliance becomes cinematic, scorecard-linked and context-rich.",
                "Scorecard records",
            )
            + f'<div class="hof-v2-grid-2">{batting_card}{bowling_card}</div>'
            + f'<div class="hof-v2-grid-2 hof-v2-top-gap">{future_cards}</div></section>'
        ),
        unsafe_allow_html=True,
    )


def hall_of_fame_v2_performance_hero_html(records: pd.DataFrame, title: str, mode: str) -> str:
    if records is None or records.empty:
        return (
            '<article class="hof-v2-card hof-v2-performance-hero">'
            f'<div class="hof-v2-kicker">{html.escape(title)}</div>'
            '<div class="hof-v2-performance-value">N/A</div>'
            '<div class="hof-v2-performance-player">Record pending</div>'
            '<p class="hof-v2-muted">Scorecard-linked record data is not available yet.</p>'
            "</article>"
        )
    row = records.iloc[0]
    if mode == "batting":
        value = format_high_score_value(row)
    else:
        value = safe_record_text(row.get("bowlingBestInnings"), "N/A")
    player = safe_record_text(row.get("canonical_player_name") or row.get("player_name"), "Unknown player")
    grade = clean_grade_label_for_record(row.get("grade_name"))
    season = safe_record_text(row.get("season"))
    meta_parts = [part for part in [season_overview_link_html(season) if season else "", html.escape(grade) if grade else ""] if part]
    scorecard = scorecard_link_html(
        row.get("match_id"),
        label="View scorecard ↗",
        class_name="hof-v2-subtle-link",
        page_slug=HALL_OF_FAME_V2_QUERY_PAGE,
        section_name="iconic_performances",
    )
    return (
        '<article class="hof-v2-card hof-v2-performance-hero">'
        f'<div class="hof-v2-kicker">{html.escape(title)}</div>'
        f'<div class="hof-v2-performance-value">{html.escape(str(value))}</div>'
        f'<div class="hof-v2-performance-player">{player_profile_link_html(player_id_from_row(row), player)}</div>'
        f'<p class="hof-v2-muted">{" · ".join(meta_parts)}</p>'
        f"{scorecard}"
        "</article>"
    )


def render_hall_of_fame_v2_fastest_verified() -> None:
    milestone_path = batting_milestones_path()
    milestones = load_batting_milestone_records(
        str(milestone_path) if milestone_path else None,
        match_centre_milestones_mtime(),
    )
    st.markdown(
        (
            hof_v2_section_heading_html(
                "fastest",
                "Fastest Verified Innings ⚡",
                "Verified ball-by-ball records are visually separated from scorecard-only records, which makes the trust boundary obvious.",
                "Verified ball-by-ball only",
            )
            + '<div class="hof-v2-fastest-panel"><span class="hof-v2-verified-badge">Verified ball-by-ball only</span>'
            + '<div class="hof-v2-grid-2">'
            + hall_of_fame_v2_fastest_list_html(milestones, "Fastest 50s", "balls_to_50")
            + hall_of_fame_v2_fastest_list_html(milestones, "Fastest 100s", "balls_to_100")
            + "</div></div></section>"
        ),
        unsafe_allow_html=True,
    )


def hall_of_fame_v2_fastest_list_html(records: pd.DataFrame, title: str, value_col: str) -> str:
    if records.empty or value_col not in records:
        return (
            '<div><div class="hof-v2-kicker">'
            f"{html.escape(title)}"
            '</div><div class="hof-v2-race-list"><div class="hof-v2-race-row">'
            '<span class="hof-v2-rank">–</span><strong>No verified records yet <span>Appears when ball-by-ball confirms it</span></strong><span class="hof-v2-race-time">—</span>'
            "</div></div></div>"
        )
    rows = records[records[value_col].notna()].copy()
    if rows.empty:
        return hall_of_fame_v2_fastest_list_html(pd.DataFrame(), title, value_col)
    rows = add_missing_canonical_player_ids(rows)
    rows["match_date_sort"] = pd.to_datetime(rows.get("match_date"), errors="coerce")
    rows = rows.sort_values([value_col, "final_runs", "match_date_sort"], ascending=[True, False, False]).head(3)
    row_html = "".join(
        hall_of_fame_v2_fastest_row_html(rank, row, value_col)
        for rank, (_, row) in enumerate(rows.iterrows(), start=1)
    )
    return f'<div><div class="hof-v2-kicker">{html.escape(title)}</div><div class="hof-v2-race-list">{row_html}</div></div>'


def hall_of_fame_v2_fastest_row_html(rank: int, row: pd.Series, value_col: str) -> str:
    player = safe_record_text(row.get("canonical_player_name") or row.get("player_name"), "Unknown player")
    final_score = safe_record_text(row.get("final_score_display"))
    if not final_score:
        final_runs = safe_record_int(row.get("final_runs"))
        final_score = str(final_runs) if final_runs else ""
    opponent = clean_opponent_label(row.get("opposition_team"), "")
    value = safe_record_int(row.get(value_col))
    context = " · ".join([part for part in [final_score, f"vs {opponent}" if opponent else ""] if part])
    return (
        '<div class="hof-v2-race-row">'
        f'<span class="hof-v2-rank">{rank}</span>'
        f'<strong>{player_profile_link_html(player_id_from_row(row), player)} <span>{html.escape(context)}</span></strong>'
        f'<span class="hof-v2-race-time">{value if value else "N/A"} balls</span>'
        "</div>"
    )


def render_hall_of_fame_v2_record_holders(data: dict[str, object]) -> None:
    cards = data.get("record_holder_cards") or build_record_holder_cards(data)
    primary_cards = [card for card in cards if card.get("title") != "Ducks"]
    duck_cards = [card for card in cards if card.get("title") == "Ducks"]
    cards_html = "".join(hall_of_fame_v2_record_card_html(card) for card in primary_cards)
    cards_html += hall_of_fame_v2_quirky_record_card_html(duck_cards[0] if duck_cards else None)
    st.markdown(
        (
            hof_v2_section_heading_html(
                "records",
                "Record Holders 📘",
                "Hard records stay prominent, while ducks move into a smaller quirky-record treatment rather than the headline grid.",
            )
            + f'<div class="hof-v2-record-grid">{cards_html}</div></section>'
        ),
        unsafe_allow_html=True,
    )


def hall_of_fame_v2_record_card_html(card: dict[str, str]) -> str:
    player = safe_record_text(card.get("player"), "Unknown player")
    meta = safe_record_text(card.get("meta"))
    meta_html = f'<span class="hof-v2-muted">{html.escape(meta)}</span>' if meta else ""
    return (
        '<article class="hof-v2-card hof-v2-record-card">'
        f'<div class="hof-v2-record-title">{html.escape(str(card.get("title", "Record")))}</div>'
        f'<div class="hof-v2-record-player">{player_profile_link_html(card.get("player_id"), player)}</div>'
        f'<div class="hof-v2-record-value">{html.escape(str(card.get("value", "-")))}</div>'
        f"{meta_html}"
        "</article>"
    )


def hall_of_fame_v2_quirky_record_card_html(card: dict[str, str] | None) -> str:
    if not card:
        value = "Interesting extras"
        player = "Ducks corner"
        meta = "Useful context, not a headline achievement."
    else:
        value = safe_record_text(card.get("value"), "Interesting extras")
        player = player_profile_link_html(card.get("player_id"), safe_record_text(card.get("player"), "Ducks corner"))
        meta = safe_record_text(card.get("meta"), "Useful context, not a headline achievement.")
    return (
        '<article class="hof-v2-card hof-v2-record-card hof-v2-burgundy-card">'
        '<div class="hof-v2-record-title">Quirky Records</div>'
        f'<div class="hof-v2-record-player">{player}</div>'
        f'<div class="hof-v2-record-value">{html.escape(value)}</div>'
        f'<span class="hof-v2-muted">{html.escape(meta)}</span>'
        "</article>"
    )


def render_hall_of_fame_v2_greatest_seasons(data: dict[str, object]) -> None:
    cards = []
    batting = data.get("best_batting_season")
    bowling = data.get("best_bowling_season")
    if batting is not None:
        cards.append(hall_of_fame_v2_best_season_card_html("Best batting season", batting, "batting"))
    if bowling is not None:
        cards.append(hall_of_fame_v2_best_season_card_html("Best bowling season", bowling, "bowling"))
    cards.append(
        '<article class="hof-v2-card hof-v2-season-card">'
        '<div><div class="hof-v2-kicker">Recommended future card</div>'
        '<h3>All-round season</h3>'
        '<p class="hof-v2-muted">Use only after a simple, agreed all-round impact formula is approved.</p></div>'
        '<div class="hof-v2-season-score">TBC</div>'
        "</article>"
    )
    st.markdown(
        (
            hof_v2_section_heading_html(
                "seasons",
                "Greatest Individual Seasons 🎖️",
                "Season-long excellence gets a premium treatment, with future all-round records clearly marked until the formula is trusted.",
                "Season aggregate records",
            )
            + f'<div class="hof-v2-grid-3">{"".join(cards)}</div></section>'
        ),
        unsafe_allow_html=True,
    )


def hall_of_fame_v2_best_season_card_html(title: str, row: dict[str, object], mode: str) -> str:
    if mode == "batting":
        primary = f'{format_int(row.get("runs"))} runs'
        meta = f'{format_int(row.get("matches"))} matches · HS {html.escape(str(row.get("hs", "—")))}'
    else:
        primary = f'{format_int(row.get("wickets"))} wkts'
        meta = f'{row.get("overs", "—")} overs · BBI {html.escape(str(row.get("bbi", "—")))}'
    return (
        '<article class="hof-v2-card hof-v2-season-card">'
        "<div>"
        f'<div class="hof-v2-kicker">{html.escape(title)}</div>'
        f'<h3>{player_profile_link_html(row.get("player_id"), row.get("player"))}</h3>'
        f'<p class="hof-v2-muted">{season_overview_link_html(row.get("season"))} · {meta}</p>'
        "</div>"
        f'<div class="hof-v2-season-score">{html.escape(primary)}</div>'
        "</article>"
    )


def render_hall_of_fame_v2_detailed_records(detailed_tables: dict[str, pd.DataFrame]) -> None:
    st.markdown(
        (
            hof_v2_section_heading_html(
            "detailed",
            "Detailed Records 📊",
            "The audit layer stays near the bottom as full sortable batting, bowling and fielding tables.",
            "Sortable audit tables",
            )
            + "</section>"
        ),
        unsafe_allow_html=True,
    )
    with st.container(key="hof_v2_detailed_records"):
        batting_tab, bowling_tab, fielding_tab = st.tabs(["Batting", "Bowling", "Fielding"])
        with batting_tab:
            render_all_time_detail_table(detailed_tables["batting"], "hof_v2_batting_detail")
        with bowling_tab:
            render_all_time_detail_table(detailed_tables["bowling"], "hof_v2_bowling_detail")
        with fielding_tab:
            render_all_time_detail_table(detailed_tables["fielding"], "hof_v2_fielding_detail")
    st.markdown(
        (
            '<div class="hof-v2-card hof-v2-trust-note">'
            '<strong>Trust note:</strong> Bat SR uses verified ball-by-ball only. '
            '30s use scorecard innings from 30 to 49 inclusive. 3WI means exactly 3 or 4 wickets. '
            '5WI means 5+. HS ignores the not-out star for sorting; BBI sorts wickets descending, then runs ascending.'
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def render_hall_of_fame_v2_recommendations() -> None:
    st.markdown(
        """
        <section class="hof-v2-section">
            <div class="hof-v2-section-head">
                <div class="hof-v2-section-title">
                    <h2>Design Recommendations</h2>
                    <p>The redesign keeps the trusted records, changes the hierarchy, and makes the top half feel like a club museum wall instead of a spreadsheet.</p>
                </div>
            </div>
            <div class="hof-v2-decision-panel">
                <div class="hof-v2-decision">
                    <h3>Keep</h3>
                    <ul>
                        <li>All existing Hall of Fame calculations.</li>
                        <li>Premierships, leaders, records, fastest innings, seasons and detailed tables.</li>
                        <li>Player, season and scorecard links.</li>
                    </ul>
                </div>
                <div class="hof-v2-decision">
                    <h3>Merge / Reorder</h3>
                    <ul>
                        <li>All-Time Leaders become Club Legends.</li>
                        <li>Premierships move directly below the hero.</li>
                        <li>Detailed Records move to the bottom as the audit layer.</li>
                    </ul>
                </div>
                <div class="hof-v2-decision">
                    <h3>Guardrails</h3>
                    <ul>
                        <li>Ducks move into Quirky Records.</li>
                        <li>Future all-round/fielding cards need reliability labels.</li>
                        <li>Do not call anything a club record unless all-time comparison confirms it.</li>
                    </ul>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_approaching_milestones_page() -> None:
    historical_data = load_hall_of_fame_data(metadata_mtime(), player_aliases_mtime())
    if historical_data is None:
        st.info("Historical data is not available yet. Refresh local backup to build the milestone watchlist.")
        return

    active_players = recent_active_canonical_players(historical_data)
    watchlist = build_approaching_milestone_watchlist(historical_data["all_time"])
    if active_players:
        watchlist = watchlist[watchlist["Player"].isin(active_players)].copy()
    season_window = milestone_achievement_season_window(historical_data)
    achieved = build_achieved_milestones(historical_data, season_window)
    hall_of_fame_watch = build_hall_of_fame_watch(historical_data["all_time"], active_players)
    hall_of_fame_movements = build_hall_of_fame_movements(historical_data, season_window)
    selected_view = selected_milestone_page_view()
    st.markdown(
        f"""
        <div class="near-milestones-page"></div>
        <h1 class="page-title">Players approaching major milestones 🎯</h1>
        {configured_club_label_html()}
        """,
        unsafe_allow_html=True,
    )
    if selected_view == "achieved":
        render_achieved_milestones_view(achieved, season_window, hall_of_fame_movements)
    elif selected_view == "exclusive":
        render_milestone_club(historical_data["all_time"], selected_milestone_club_category())
    else:
        render_career_milestone_cards(watchlist, hall_of_fame_watch)


def milestone_page_view_options() -> list[tuple[str, str]]:
    return [
        ("upcoming", "Upcoming"),
        ("achieved", "Achieved"),
        ("exclusive", "Exclusive Club"),
    ]


def milestone_club_category_options() -> list[tuple[str, str]]:
    return [
        ("matches", "Matches"),
        ("runs", "Runs"),
        ("wickets", "Wickets"),
        ("catches", "Catches"),
    ]


def selected_milestone_page_view() -> str:
    valid = {slug for slug, _ in milestone_page_view_options()}
    state_key = "milestone_page_view"
    if state_key not in st.session_state:
        requested = query_param_value("milestone_view").casefold()
        st.session_state[state_key] = requested if requested in valid else "upcoming"
    selected = str(st.session_state.get(state_key, "upcoming")).casefold()
    if selected not in valid:
        selected = "upcoming"
        st.session_state[state_key] = selected
    return selected


def selected_milestone_club_category() -> str:
    valid = {slug for slug, _ in milestone_club_category_options()}
    state_key = "milestone_club_category"
    if state_key not in st.session_state:
        requested = query_param_value("club_category").casefold()
        st.session_state[state_key] = requested if requested in valid else "matches"
    selected = str(st.session_state.get(state_key, "matches")).casefold()
    if selected not in valid:
        selected = "matches"
        st.session_state[state_key] = selected
    return selected


def milestone_page_url(view: str, club_category: str | None = None) -> str:
    url = f"?page=milestone&milestone_view={quote(view, safe='')}"
    if club_category:
        url = f"{url}&club_category={quote(club_category, safe='')}"
    return url


def render_milestone_view_selector(selected_view: str) -> None:
    del selected_view
    render_folder_tab_widget(
        "Milestone page view",
        milestone_page_view_options(),
        key="milestone_page_view",
        control_key="milestone_page_view_folder_tabs",
    )


def render_milestone_club_selector(selected_category: str) -> None:
    del selected_category
    render_profile_segmented_widget(
        "Exclusive club category",
        milestone_club_category_options(),
        key="milestone_club_category",
        compact=True,
    )


def render_milestone_segmented_links(
    items: list[tuple[str, str, bool]],
    aria_label: str,
    compact: bool = False,
) -> None:
    class_name = "milestone-segmented milestone-segmented-compact" if compact else "milestone-segmented"
    links = "".join(
        (
            f'<a class="milestone-segment{" active" if active else ""}" '
            f'href="{html.escape(url, quote=True)}" target="_self" role="tab" '
            f'aria-selected="{str(active).lower()}">{milestone_segment_label_html(label, compact)}</a>'
        )
        for label, url, active in items
    )
    st.markdown(
        f'<nav class="{class_name}" aria-label="{html.escape(aria_label, quote=True)}">{links}</nav>',
        unsafe_allow_html=True,
    )


def milestone_segment_label_html(label: str, compact: bool = False) -> str:
    if compact:
        return html.escape(label)
    mobile_labels = {
        "Upcoming Milestones": "Upcoming",
        "Achieved Milestones": "Achieved",
        "Exclusive Clubs": "Exclusive Club",
    }
    mobile_label = mobile_labels.get(label, label)
    if mobile_label == label:
        return html.escape(label)
    return (
        f'<span class="milestone-label-desktop">{html.escape(label)}</span>'
        f'<span class="milestone-label-mobile">{html.escape(mobile_label)}</span>'
    )


def milestone_achievement_season_window(historical_data: dict[str, object]) -> list[str]:
    season_table = read_processed_table("seasons")
    ordered = ordered_milestone_seasons(season_table)
    if not ordered:
        activity_frames = [
            frame
            for frame in [
                historical_data.get("batting_raw"),
                historical_data.get("bowling_raw"),
                historical_data.get("fielding_raw"),
            ]
            if isinstance(frame, pd.DataFrame) and not frame.empty
        ]
        activity = pd.concat(activity_frames, ignore_index=True, sort=False) if activity_frames else pd.DataFrame()
        ordered = latest_activity_seasons(activity, 12) if not activity.empty else []
    if not ordered:
        return []

    latest = ordered[0]
    if "winter" not in latest.casefold():
        return [latest]

    previous_summer = next(
        (season for season in ordered[1:] if "summer" in season.casefold()),
        "",
    )
    return [season for season in [latest, previous_summer] if season]


def ordered_milestone_seasons(season_table: pd.DataFrame) -> list[str]:
    if season_table.empty or "name" not in season_table:
        return []
    output = season_table.copy()
    if "startDate" in output:
        output["season_sort"] = pd.to_datetime(output["startDate"], errors="coerce", utc=True)
    else:
        output["season_sort"] = output["name"].map(season_sort_value)
    output = output.sort_values(["season_sort", "name"], ascending=[False, False])
    return output["name"].dropna().astype(str).drop_duplicates().tolist()


def milestone_achievement_specs() -> list[dict[str, object]]:
    return [
        {"category": "Matches", "metric": "Matches", "unit": "matches", "thresholds": [100, 200, 300, 400, 500, 600]},
        {"category": "Runs", "metric": "Runs", "unit": "runs", "thresholds": [1000, 2000, 3000, 4000, 5000, 6000]},
        {"category": "Wickets", "metric": "Wickets", "unit": "wickets", "thresholds": [100, 200, 300, 400]},
        {"category": "Catches", "metric": "Catches", "unit": "catches", "thresholds": [100, 200]},
    ]


def build_achieved_milestones(
    historical_data: dict[str, object],
    season_window: list[str],
) -> pd.DataFrame:
    columns = [
        "Player",
        "canonical_player_id",
        "Category",
        "Milestone",
        "Threshold",
        "Current Total",
        "Season",
        "Unit",
    ]
    if not season_window:
        return pd.DataFrame(columns=columns)

    all_time = historical_data["all_time"].copy()
    period_totals = build_milestone_period_totals(historical_data, season_window)
    season_totals = build_milestone_period_totals_by_season(historical_data, season_window)
    if all_time.empty or period_totals.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    season_label = milestone_season_window_label(season_window)
    for spec in milestone_achievement_specs():
        metric = str(spec["metric"])
        if metric not in all_time or metric not in period_totals:
            continue
        source = all_time[["player_key", "canonical_player_id", "Player", metric]].copy()
        source[metric] = pd.to_numeric(source[metric], errors="coerce").fillna(0)
        window_values = period_totals[["player_key", metric]].copy()
        window_values[metric] = pd.to_numeric(window_values[metric], errors="coerce").fillna(0)
        merged = source.merge(window_values, on="player_key", how="left", suffixes=("_current", "_window"))
        merged[f"{metric}_window"] = pd.to_numeric(merged[f"{metric}_window"], errors="coerce").fillna(0)
        merged[f"{metric}_previous"] = (merged[f"{metric}_current"] - merged[f"{metric}_window"]).clip(lower=0)
        for _, player in merged[merged[f"{metric}_window"] > 0].iterrows():
            current_total = float(player[f"{metric}_current"])
            previous_total = float(player[f"{metric}_previous"])
            for threshold in spec["thresholds"]:
                threshold_value = float(threshold)
                if previous_total < threshold_value <= current_total:
                    rows.append(
                        {
                            "Player": player["Player"],
                            "canonical_player_id": player.get("canonical_player_id", ""),
                            "Category": spec["category"],
                            "Milestone": f"{int(threshold_value):,} {spec['unit']} reached",
                            "Threshold": int(threshold_value),
                            "Current Total": int(round(current_total)),
                            "Season": milestone_reached_season(
                                season_totals,
                                str(player["player_key"]),
                                metric,
                                previous_total,
                                threshold_value,
                                season_label,
                            ),
                            "Unit": spec["unit"],
                        }
                    )

    if not rows:
        return pd.DataFrame(columns=columns)
    output = pd.DataFrame(rows).drop_duplicates(["canonical_player_id", "Category", "Threshold"])
    output["category_order"] = output["Category"].map(
        {str(spec["category"]): index for index, spec in enumerate(milestone_achievement_specs())}
    )
    output = output.sort_values(["category_order", "Threshold", "Player"], ascending=[True, False, True])
    return output.drop(columns=["category_order"], errors="ignore")[columns]


def build_hall_of_fame_watch(all_time: pd.DataFrame, active_players: set[str] | None = None) -> pd.DataFrame:
    columns = [
        "Player",
        "canonical_player_id",
        "Category",
        "Metric",
        "Current Total",
        "Top 5 Target",
        "Remaining",
        "Unit",
    ]
    if all_time.empty:
        return pd.DataFrame(columns=columns)

    thresholds = {
        "Matches": 10,
        "Runs": 100,
        "Wickets": 10,
        "Catches": 10,
    }
    units = {
        "Matches": "matches",
        "Runs": "runs",
        "Wickets": "wickets",
        "Catches": "catches",
    }
    active_players = active_players or set()
    rows: list[dict[str, object]] = []
    for metric, close_threshold in thresholds.items():
        if metric not in all_time:
            continue
        players = all_time[["Player", "canonical_player_id", metric]].copy()
        players[metric] = pd.to_numeric(players[metric], errors="coerce").fillna(0)
        players = players[players[metric] > 0].sort_values([metric, "Player"], ascending=[False, True]).copy()
        if len(players) < 5:
            continue
        players["rank"] = players[metric].rank(method="min", ascending=False)
        top_five_target = float(players.iloc[4][metric])
        candidates = players[players["rank"] > 5].copy()
        if active_players:
            candidates = candidates[candidates["Player"].isin(active_players)].copy()
        candidates["Remaining"] = top_five_target - candidates[metric]
        candidates = candidates[(candidates["Remaining"] > 0) & (candidates["Remaining"] <= close_threshold)]
        candidates = candidates.sort_values(["Remaining", metric], ascending=[True, False]).head(3)
        for _, row in candidates.iterrows():
            rows.append(
                {
                    "Player": row["Player"],
                    "canonical_player_id": row.get("canonical_player_id", ""),
                    "Category": metric,
                    "Metric": metric.casefold(),
                    "Current Total": int(round(float(row[metric]))),
                    "Top 5 Target": int(round(top_five_target)),
                    "Remaining": int(round(float(row["Remaining"]))),
                    "Unit": units[metric],
                }
            )

    if not rows:
        return pd.DataFrame(columns=columns)
    output = pd.DataFrame(rows)
    output["category_order"] = output["Category"].map({metric: index for index, metric in enumerate(thresholds)})
    output = output.sort_values(["category_order", "Remaining", "Current Total"], ascending=[True, True, False])
    return output.drop(columns=["category_order"], errors="ignore")[columns]


def build_hall_of_fame_movements(
    historical_data: dict[str, object],
    season_window: list[str],
) -> pd.DataFrame:
    columns = [
        "Player",
        "canonical_player_id",
        "Category",
        "Metric",
        "Current Rank",
        "Previous Rank",
        "Current Total",
        "Season",
        "Unit",
    ]
    if not season_window:
        return pd.DataFrame(columns=columns)

    all_time = historical_data["all_time"].copy()
    period_totals = build_milestone_period_totals(historical_data, season_window)
    if all_time.empty or period_totals.empty:
        return pd.DataFrame(columns=columns)

    rows: list[dict[str, object]] = []
    units = {
        "Matches": "matches",
        "Runs": "runs",
        "Wickets": "wickets",
        "Catches": "catches",
    }
    season_label = milestone_season_window_label(season_window)
    for metric, unit in units.items():
        if metric not in all_time or metric not in period_totals:
            continue
        source = all_time[["player_key", "canonical_player_id", "Player", metric]].copy()
        source[metric] = pd.to_numeric(source[metric], errors="coerce").fillna(0)
        window_values = period_totals[["player_key", metric]].copy()
        window_values[metric] = pd.to_numeric(window_values[metric], errors="coerce").fillna(0)
        merged = source.merge(window_values, on="player_key", how="left", suffixes=("_current", "_window"))
        merged[f"{metric}_window"] = pd.to_numeric(merged[f"{metric}_window"], errors="coerce").fillna(0)
        merged[f"{metric}_previous"] = (merged[f"{metric}_current"] - merged[f"{metric}_window"]).clip(lower=0)
        merged["current_rank"] = merged[f"{metric}_current"].rank(method="min", ascending=False)
        merged["previous_rank"] = merged[f"{metric}_previous"].rank(method="min", ascending=False)
        movements = merged[
            (merged[f"{metric}_window"] > 0)
            & (merged[f"{metric}_current"] > 0)
            & (merged["current_rank"] <= 5)
            & (merged["previous_rank"] > 5)
        ].copy()
        movements = movements.sort_values(["current_rank", f"{metric}_current"], ascending=[True, False])
        for _, row in movements.iterrows():
            rows.append(
                {
                    "Player": row["Player"],
                    "canonical_player_id": row.get("canonical_player_id", ""),
                    "Category": metric,
                    "Metric": metric.casefold(),
                    "Current Rank": int(row["current_rank"]),
                    "Previous Rank": int(row["previous_rank"]),
                    "Current Total": int(round(float(row[f"{metric}_current"]))),
                    "Season": season_label,
                    "Unit": unit,
                }
            )

    if not rows:
        return pd.DataFrame(columns=columns)
    output = pd.DataFrame(rows)
    output["category_order"] = output["Category"].map({metric: index for index, metric in enumerate(units)})
    output = output.sort_values(["category_order", "Current Rank", "Player"], ascending=[True, True, True])
    return output.drop(columns=["category_order"], errors="ignore")[columns]


def build_milestone_period_totals(
    historical_data: dict[str, object],
    season_window: list[str],
) -> pd.DataFrame:
    frames = [
        filter_milestone_window_frame(historical_data.get("batting_raw"), season_window),
        filter_milestone_window_frame(historical_data.get("bowling_raw"), season_window),
        filter_milestone_window_frame(historical_data.get("fielding_raw"), season_window),
    ]
    identity = build_player_identity_frame([frame for frame in frames if not frame.empty])
    if identity.empty:
        return pd.DataFrame(columns=["player_key"])

    output = identity[["player_key", "canonical_player_id", "player_name"]].copy()
    output = output.rename(columns={"player_name": "Player"})

    matches = build_best_match_counts(frames).rename(columns={"matches": "Matches"})
    output = output.merge(matches, on="player_key", how="left")
    for frame, source_column, metric in [
        (frames[0], "battingAggregate", "Runs"),
        (frames[1], "bowlingWickets", "Wickets"),
        (add_display_stat_aliases(frames[2]), "catches_display", "Catches"),
    ]:
        totals = grouped_milestone_metric(frame, source_column, metric)
        if not totals.empty:
            output = output.merge(totals, on="player_key", how="left")

    for metric in ["Matches", "Runs", "Wickets", "Catches"]:
        if metric not in output:
            output[metric] = 0
        output[metric] = pd.to_numeric(output[metric], errors="coerce").fillna(0)
    return output


def build_milestone_period_totals_by_season(
    historical_data: dict[str, object],
    season_window: list[str],
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for season in sorted(season_window, key=season_sort_value):
        totals = build_milestone_period_totals(historical_data, [season])
        if totals.empty:
            continue
        totals = totals.copy()
        totals["season"] = season
        frames.append(totals)
    if not frames:
        return pd.DataFrame(columns=["player_key", "season", "Matches", "Runs", "Wickets", "Catches"])
    output = pd.concat(frames, ignore_index=True, sort=False)
    for metric in ["Matches", "Runs", "Wickets", "Catches"]:
        if metric not in output:
            output[metric] = 0
        output[metric] = pd.to_numeric(output[metric], errors="coerce").fillna(0)
    return output


def milestone_reached_season(
    season_totals: pd.DataFrame,
    player_key: str,
    metric: str,
    previous_total: float,
    threshold: float,
    fallback_label: str,
) -> str:
    if season_totals.empty or metric not in season_totals:
        return fallback_label
    player_rows = season_totals[season_totals["player_key"].astype(str) == str(player_key)].copy()
    if player_rows.empty:
        return fallback_label
    player_rows["season_order"] = player_rows["season"].map(season_sort_value)
    player_rows = player_rows.sort_values(["season_order", "season"], ascending=[True, True])

    running_total = float(previous_total)
    for _, row in player_rows.iterrows():
        numeric_value = pd.to_numeric(row.get(metric), errors="coerce")
        season_value = float(numeric_value) if pd.notna(numeric_value) else 0.0
        after_season_total = running_total + season_value
        if running_total < threshold <= after_season_total:
            return str(row.get("season") or fallback_label)
        running_total = after_season_total
    return fallback_label


def filter_milestone_window_frame(frame: object, season_window: list[str]) -> pd.DataFrame:
    if not isinstance(frame, pd.DataFrame) or frame.empty or "season" not in frame:
        return pd.DataFrame()
    return frame[frame["season"].isin(season_window)].copy()


def grouped_milestone_metric(frame: pd.DataFrame, source_column: str, metric: str) -> pd.DataFrame:
    if frame.empty or source_column not in frame:
        return pd.DataFrame(columns=["player_key", metric])
    output = frame.copy()
    output["player_key"] = player_keys(output)
    output[source_column] = pd.to_numeric(output[source_column], errors="coerce").fillna(0)
    return output.groupby("player_key", as_index=False)[source_column].sum().rename(columns={source_column: metric})


def milestone_season_window_label(season_window: list[str]) -> str:
    if not season_window:
        return "Current season window"
    if len(season_window) == 1:
        return season_window[0]
    return " or ".join(season_window)


def render_achieved_milestones_view(
    achieved: pd.DataFrame,
    season_window: list[str],
    hall_of_fame_movements: pd.DataFrame,
) -> None:
    window_label = milestone_season_window_label(season_window)
    groups = []
    for category in ["Matches", "Runs", "Wickets", "Catches"]:
        rows = achieved[achieved["Category"] == category].copy() if not achieved.empty else pd.DataFrame()
        cards = "".join(achievement_card_html(row) for _, row in rows.iterrows())
        if not cards:
            cards = f'<div class="milestone-empty-card">No {html.escape(category.casefold())} milestones reached in this season window.</div>'
        groups.append(
            '<div class="milestone-achievement-group">'
            f"<h3>{html.escape(category)}</h3>"
            f'<div class="achievement-grid">{cards}</div>'
            "</div>"
        )

    movement_cards = "".join(hall_of_fame_movement_card_html(row) for _, row in hall_of_fame_movements.iterrows())
    if not movement_cards:
        movement_cards = (
            '<div class="milestone-empty-card">'
            "No verified top-5 Hall of Fame movement detected for this season window."
            "</div>"
        )
    groups.append(
        '<div class="milestone-achievement-group">'
        "<h3>Hall of Fame Movement</h3>"
        f'<div class="achievement-grid">{movement_cards}</div>'
        "</div>"
    )

    render_milestone_view_selector("achieved")
    with st.container(key="milestone_achieved_panel"):
        st.markdown(
            (
                '<div class="milestone-section-heading"><h2>Achieved Milestones 🏁</h2></div>'
                f'<div class="milestone-section-subtitle">Milestones reached during {html.escape(window_label)} season</div>'
                f"{''.join(groups)}"
            ),
            unsafe_allow_html=True,
        )


def achievement_card_html(row: pd.Series) -> str:
    return (
        '<article class="achievement-card">'
        '<div class="achievement-badge">Reached</div>'
        f'<div class="achievement-player">{player_profile_link_html(player_id_from_row(row), row["Player"])}</div>'
        f'<div class="achievement-value">{html.escape(str(row["Milestone"]))}</div>'
        f'<div class="achievement-meta">{html.escape(str(row["Season"]))} · {html.escape(str(row["Category"]))}</div>'
        f'<div class="achievement-total">Current total: {int(row["Current Total"]):,} {html.escape(str(row["Unit"]))}</div>'
        "</article>"
    )


def hall_of_fame_movement_card_html(row: pd.Series) -> str:
    category = str(row["Category"])
    rank = int(row["Current Rank"])
    total = int(row["Current Total"])
    unit = str(row["Unit"])
    return (
        '<article class="achievement-card">'
        '<div class="achievement-badge achievement-badge-gold">Hall of Fame Move</div>'
        f'<div class="achievement-player">{player_profile_link_html(player_id_from_row(row), row["Player"])}</div>'
        f'<div class="achievement-value">Entered Top 5 for {html.escape(category.casefold())}</div>'
        f'<div class="achievement-meta">Current rank: #{rank} · {html.escape(str(row["Season"]))}</div>'
        f'<div class="achievement-total">Current total: {total:,} {html.escape(unit)}</div>'
        "</article>"
    )


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
def load_hall_of_fame_data(
    local_version: float,
    identity_version: float | None = None,
    data_version: str = HALL_OF_FAME_DATA_VERSION,
) -> dict[str, object] | None:
    _ = (local_version, identity_version, data_version)
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
    if allow_legacy_fallback():
        export_team_grade_display_audit(
            [batting_raw, bowling_raw, fielding_raw],
            path=get_mapping_path("team_grade_display_audit.csv"),
        )
    log_hof_timing("apply canonical player and team-grade mapping", started_at)

    identity_exports = {
        "possible_duplicates": 0,
        "summary_rows": 0,
        "mapping_rows_added": 0,
        "mapping_conflicts": 0,
    }
    if allow_legacy_fallback():
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
            rebuild_canonical_processed_tables(processed_dir=get_processed_dir())
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
        log_hof_timing("refresh runtime player identity exports", started_at)

    started_at = time.perf_counter()
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
def get_hall_of_fame_data(
    local_version: float,
    identity_version: float | None = None,
    data_version: str = HALL_OF_FAME_DATA_VERSION,
) -> dict[str, object] | None:
    started_at = time.perf_counter()
    historical_data = load_hall_of_fame_data(local_version, identity_version, data_version)
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
    iconic_batting = attach_scorecard_match_ids(top_highest_scores(historical_data["batting_raw"], limit=10), "batting")
    iconic_bowling = attach_scorecard_match_ids(top_best_bowling_innings(historical_data["bowling_raw"], limit=10), "bowling")
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
    output["player_name"] = output["player_name"].map(display_player_name)
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


def player_name_match_key(value: object) -> str:
    text = safe_record_text(value).casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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
    win_rates = build_match_centre_win_rates()
    base = base.merge(
        win_rates.drop(columns=["player_name_key"], errors="ignore"),
        on="player_key",
        how="left",
    )
    if "player_name" in base and "player_name_key" in win_rates:
        win_by_name = (
            win_rates.dropna(subset=["player_name_key"])
            .sort_values("Win Matches", ascending=False)
            .drop_duplicates("player_name_key")
            .rename(
                columns={
                    "Win Matches": "Win Matches_by_name",
                    "Win Count": "Win Count_by_name",
                    "win_pct": "win_pct_by_name",
                }
            )
        )
        base["_player_name_key"] = base["player_name"].map(player_name_match_key)
        base = base.merge(
            win_by_name[["player_name_key", "Win Matches_by_name", "Win Count_by_name", "win_pct_by_name"]],
            left_on="_player_name_key",
            right_on="player_name_key",
            how="left",
        )
        for column in ["Win Matches", "Win Count", "win_pct"]:
            fallback = f"{column}_by_name"
            if fallback in base:
                base[column] = base[column].where(base[column].notna(), base[fallback])
        base = base.drop(
            columns=["_player_name_key", "player_name_key", "Win Matches_by_name", "Win Count_by_name", "win_pct_by_name"],
            errors="ignore",
        )
    base["matches"] = pd.to_numeric(base["matches"], errors="coerce").fillna(0)
    base = base.merge(build_ball_by_ball_batting_strike_rates(), on="player_key", how="left")
    # Hall of Fame batting strike rate uses verified ball-by-ball coverage only.
    base["battingStrikeRate"] = base.get("ballByBallBatSR")
    base = base.merge(build_scorecard_detail_milestone_counts(), on="player_key", how="left")
    for column in ["batting30s", "bowling3WIs"]:
        if column in base:
            base[column] = pd.to_numeric(base[column], errors="coerce").fillna(0).astype(int)

    return base.rename(
        columns={
            "player_name": "Player",
            "teams_grades": "Teams/Grades",
            "seasons_played": "Seasons Played",
            "first_season": "Debut Season",
            "latest_season": "Latest Season",
            "matches": "Matches",
            "win_pct": "Win %",
            "battingAggregate": "Runs",
            "battingAverage": "Bat Avg",
            "battingStrikeRate": "Bat SR",
            "high_score": "HS",
            "batting30s": "30s",
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
            "bowling3WIs": "3WI",
            "bowling5WIs": "5WI",
            "bowling10WMs": "10WM",
            "catches_display": "Catches",
            "stumpings_display": "Stumpings",
            "run_outs_display": "Run Outs",
            "dismissals_display": "Dismissals",
        }
    )



def build_match_centre_win_rates() -> pd.DataFrame:
    deploy_rates = load_deploy_safe_win_rates(player_win_rates_signature())
    if not deploy_rates.empty:
        return deploy_rates
    scope = MATCH_CENTRE_PROCESSED_ROOT / "all_available"
    matches = read_match_centre_csv(scope / "all_matches.csv")
    if matches.empty or "match_id" not in matches:
        return pd.DataFrame(columns=["player_key", "Win Matches", "Win Count", "win_pct"])
    fvcc_team_ids_by_match = {}
    if "source_team_ids" in matches:
        for _, row in matches.iterrows():
            ids = {
                part.strip()
                for part in str(row.get("source_team_ids", "")).split(",")
                if part.strip() and part.strip().casefold() not in {"nan", "none"}
            }
            fvcc_team_ids_by_match[str(row.get("match_id"))] = ids
    result_lookup = matches.set_index(matches["match_id"].astype(str))["result_text"].fillna("").astype(str).to_dict()
    frames = []
    for filename in ["all_scorecard_batting.csv", "all_scorecard_bowling.csv", "all_scorecard_fielding.csv"]:
        frame = read_match_centre_csv(scope / filename)
        if frame.empty or "match_id" not in frame or "player_name" not in frame:
            continue
        rows = frame.copy()
        rows["match_id"] = rows["match_id"].astype(str)
        if "team_id" in rows and fvcc_team_ids_by_match:
            rows = rows[
                rows.apply(lambda row: str(row.get("team_id")) in fvcc_team_ids_by_match.get(str(row.get("match_id")), set()), axis=1)
            ].copy()
        if rows.empty:
            continue
        rows = apply_player_identity_mapping(rows, load_player_aliases())
        rows["player_key"] = player_keys(rows)
        name_source = rows["canonical_player_name"] if "canonical_player_name" in rows else rows["player_name"]
        rows["player_name_key"] = name_source.map(player_name_match_key)
        frames.append(rows[["match_id", "player_key", "player_name_key"]])
    if not frames:
        return pd.DataFrame(columns=["player_key", "player_name_key", "Win Matches", "Win Count", "win_pct"])
    appearances = pd.concat(frames, ignore_index=True).dropna(subset=["player_key", "match_id"]).drop_duplicates(["player_key", "match_id"])
    appearances["result_text"] = appearances["match_id"].map(result_lookup).fillna("")
    appearances["win"] = appearances["result_text"].str.contains("fiji victorian", case=False, na=False)
    grouped = appearances.groupby("player_key", as_index=False).agg(
        **{
            "player_name_key": ("player_name_key", "first"),
            "Win Matches": ("match_id", "nunique"),
            "Win Count": ("win", "sum"),
        }
    )
    grouped["win_pct"] = grouped.apply(lambda row: (row["Win Count"] * 100 / row["Win Matches"]) if row["Win Matches"] else pd.NA, axis=1)
    return grouped[["player_key", "player_name_key", "Win Matches", "Win Count", "win_pct"]]


def player_win_rates_signature() -> tuple[tuple[str, float], ...]:
    if HALL_OF_FAME_PLAYER_WIN_RATES_PATH.exists():
        return ((str(HALL_OF_FAME_PLAYER_WIN_RATES_PATH), HALL_OF_FAME_PLAYER_WIN_RATES_PATH.stat().st_mtime),)
    return tuple()


@st.cache_data(show_spinner=False)
def load_deploy_safe_win_rates(_signature: tuple[tuple[str, float], ...]) -> pd.DataFrame:
    frame = read_match_centre_csv(HALL_OF_FAME_PLAYER_WIN_RATES_PATH)
    if frame.empty:
        return pd.DataFrame(columns=["player_key", "player_name_key", "Win Matches", "Win Count", "win_pct"])
    output = frame.copy()
    if "player_key" not in output:
        output["player_key"] = output.get("canonical_player_id", "")
    if "player_name_key" not in output:
        name_source = output.get("display_player_name", output.get("canonical_player_name", pd.Series("", index=output.index)))
        output["player_name_key"] = name_source.map(player_name_match_key)
    output = output.rename(columns={"matches_with_result": "Win Matches", "wins": "Win Count"})
    for column in ["Win Matches", "Win Count", "win_pct"]:
        if column not in output:
            output[column] = pd.NA
        output[column] = pd.to_numeric(output[column], errors="coerce")
    return output[["player_key", "player_name_key", "Win Matches", "Win Count", "win_pct"]]


def hall_of_fame_detail_source_signature() -> tuple[tuple[str, float], ...]:
    paths = [
        HALL_OF_FAME_BBB_BATTING_RATES_PATH,
        HALL_OF_FAME_SCORECARD_MILESTONES_PATH,
        HALL_OF_FAME_BOWLING_MILESTONES_PATH,
    ]
    return tuple((str(path), path.stat().st_mtime) for path in paths if path.exists())


@st.cache_data(show_spinner=False)
def load_deploy_safe_bbb_batting_rates(_signature: tuple[tuple[str, float], ...]) -> pd.DataFrame:
    frame = read_match_centre_csv(HALL_OF_FAME_BBB_BATTING_RATES_PATH)
    if frame.empty:
        return pd.DataFrame(columns=["player_key", "ballByBallBatSR", "ballByBallBatRuns", "ballByBallBatBalls"])
    output = frame.copy()
    if "player_key" not in output:
        output["player_key"] = output.get("canonical_player_id", "")
    output = output.rename(
        columns={
            "bat_sr": "ballByBallBatSR",
            "bbb_runs": "ballByBallBatRuns",
            "bbb_balls_faced": "ballByBallBatBalls",
        }
    )
    for column in ["ballByBallBatSR", "ballByBallBatRuns", "ballByBallBatBalls"]:
        if column not in output:
            output[column] = pd.NA
        output[column] = pd.to_numeric(output[column], errors="coerce")
    return output[["player_key", "ballByBallBatSR", "ballByBallBatRuns", "ballByBallBatBalls"]]


@st.cache_data(show_spinner=False)
def load_deploy_safe_scorecard_detail_milestones(_signature: tuple[tuple[str, float], ...]) -> pd.DataFrame:
    batting = read_match_centre_csv(HALL_OF_FAME_SCORECARD_MILESTONES_PATH)
    bowling = read_match_centre_csv(HALL_OF_FAME_BOWLING_MILESTONES_PATH)
    frames = []
    if not batting.empty:
        bat_output = batting.copy()
        if "player_key" not in bat_output:
            bat_output["player_key"] = bat_output.get("canonical_player_id", "")
        bat_output = bat_output.rename(columns={"thirties": "batting30s"})
        if "batting30s" not in bat_output:
            bat_output["batting30s"] = 0
        bat_output["batting30s"] = pd.to_numeric(bat_output["batting30s"], errors="coerce").fillna(0).astype(int)
        frames.append(bat_output[["player_key", "batting30s"]])
    if not bowling.empty:
        bowl_output = bowling.copy()
        if "player_key" not in bowl_output:
            bowl_output["player_key"] = bowl_output.get("canonical_player_id", "")
        bowl_output = bowl_output.rename(columns={"three_wicket_innings": "bowling3WIs"})
        if "bowling3WIs" not in bowl_output:
            bowl_output["bowling3WIs"] = 0
        bowl_output["bowling3WIs"] = pd.to_numeric(bowl_output["bowling3WIs"], errors="coerce").fillna(0).astype(int)
        frames.append(bowl_output[["player_key", "bowling3WIs"]])
    if not frames:
        return pd.DataFrame(columns=["player_key", "batting30s", "bowling3WIs"])
    output = frames[0]
    for frame in frames[1:]:
        output = output.merge(frame, on="player_key", how="outer")
    for column in ["batting30s", "bowling3WIs"]:
        if column not in output:
            output[column] = 0
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0).astype(int)
    return output[["player_key", "batting30s", "bowling3WIs"]]


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
                    "canonical_player_id": key,
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
                "canonical_player_id": "first",
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


def build_all_time_matches_by_player_name() -> pd.DataFrame:
    aliases = load_player_aliases()
    frames = []
    for table, discipline in [
        ("all_seasons_batting", "batting"),
        ("all_seasons_bowling", "bowling"),
        ("all_seasons_fielding", "fielding"),
    ]:
        frame = read_processed_table(table)
        if frame.empty or "matches" not in frame:
            continue
        rows = apply_player_identity_mapping(normalise_player_names(frame), aliases)
        summary = combine_player_rows(rows, discipline)
        if summary.empty or "player_name" not in summary or "matches" not in summary:
            continue
        summary["player_name_key"] = summary["player_name"].map(player_name_match_key)
        summary["matches"] = pd.to_numeric(summary["matches"], errors="coerce").fillna(0)
        frames.append(summary[["player_name_key", "matches"]])
    if not frames:
        return pd.DataFrame(columns=["player_name_key", "matches"])
    combined = pd.concat(frames, ignore_index=True)
    return combined.groupby("player_name_key", as_index=False)["matches"].max()


def match_centre_fvcc_team_ids(matches: pd.DataFrame) -> dict[str, set[str]]:
    if matches.empty or "match_id" not in matches:
        return {}
    team_ids_by_match: dict[str, set[str]] = {}
    if "source_team_ids" in matches:
        for _, row in matches.iterrows():
            team_ids_by_match[str(row.get("match_id"))] = {
                part.strip()
                for part in str(row.get("source_team_ids", "")).split(",")
                if part.strip() and part.strip().casefold() not in {"nan", "none"}
            }
    return team_ids_by_match


def filter_match_centre_fvcc_rows(rows: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    if rows.empty or "match_id" not in rows:
        return rows.copy()
    output = rows.copy()
    output["match_id"] = output["match_id"].astype(str)
    team_ids_by_match = match_centre_fvcc_team_ids(matches)
    if "team_id" in output and team_ids_by_match:
        output = output[
            output.apply(lambda row: str(row.get("team_id")) in team_ids_by_match.get(str(row.get("match_id")), set()), axis=1)
        ].copy()
    elif "team_name" in output:
        output = output[output["team_name"].fillna("").astype(str).str.contains("Fiji Victorian", case=False, na=False)].copy()
    return output


def prepare_match_centre_identity_rows(rows: pd.DataFrame) -> pd.DataFrame:
    output = rows.copy()
    if "participant_id" in output:
        output["raw_player_id"] = output["participant_id"]
    if "player_name" in output:
        output["raw_player_name"] = output["player_name"]
    return apply_player_identity_mapping(output, load_player_aliases())


def scorecard_dedupe(rows: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    dedupe_columns = [column for column in columns if column in rows]
    return rows.drop_duplicates(dedupe_columns) if dedupe_columns else rows.drop_duplicates()


def parse_batting_score(score: object, dismissal_type: object = None) -> tuple[int | None, bool]:
    if pd.isna(score):
        return None, False
    text = str(score).strip()
    match = re.search(r"(\d+)", text)
    if not match:
        return None, False
    dismissal = str(dismissal_type or "").strip().casefold()
    return int(match.group(1)), "*" in text or "not out" in dismissal


def build_ball_by_ball_batting_strike_rates() -> pd.DataFrame:
    """Hall of Fame batting strike rate uses verified ball-by-ball coverage only."""
    deploy_rates = load_deploy_safe_bbb_batting_rates(hall_of_fame_detail_source_signature())
    if not deploy_rates.empty:
        return deploy_rates
    scope = MATCH_CENTRE_PROCESSED_ROOT / "all_available"
    matches = read_match_centre_csv(scope / "all_matches.csv")
    batting = read_match_centre_csv(scope / "all_scorecard_batting.csv")
    balls = read_match_centre_csv(scope / "all_ball_by_ball.csv")
    if batting.empty or balls.empty or matches.empty:
        return pd.DataFrame(columns=["player_key", "ballByBallBatSR", "ballByBallBatRuns", "ballByBallBatBalls"])
    required = {"match_id", "innings_id", "participant_id"}
    if not required.issubset(batting.columns) or not {"match_id", "innings_id", "striker_participant_id"}.issubset(balls.columns):
        return pd.DataFrame(columns=["player_key", "ballByBallBatSR", "ballByBallBatRuns", "ballByBallBatBalls"])

    batting = filter_match_centre_fvcc_rows(batting, matches)
    if batting.empty:
        return pd.DataFrame(columns=["player_key", "ballByBallBatSR", "ballByBallBatRuns", "ballByBallBatBalls"])
    batting = prepare_match_centre_identity_rows(batting)
    batting["player_key"] = player_keys(batting)
    batting["_match_id"] = batting["match_id"].astype(str)
    batting["_innings_id"] = batting["innings_id"].astype(str)
    batting["_participant_id"] = batting["participant_id"].astype(str)
    lookup = batting.drop_duplicates(["_match_id", "_innings_id", "_participant_id"])[
        ["_match_id", "_innings_id", "_participant_id", "player_key"]
    ]

    rows = balls.copy()
    if "ball_event_id" in rows:
        rows = rows.drop_duplicates("ball_event_id")
    rows["_match_id"] = rows["match_id"].astype(str)
    rows["_innings_id"] = rows["innings_id"].astype(str)
    rows["_participant_id"] = rows["striker_participant_id"].astype(str)
    rows = rows.merge(lookup, on=["_match_id", "_innings_id", "_participant_id"], how="inner")
    if rows.empty:
        return pd.DataFrame(columns=["player_key", "ballByBallBatSR", "ballByBallBatRuns", "ballByBallBatBalls"])

    rows["runs_bat"] = pd.to_numeric(rows.get("runs_bat"), errors="coerce").fillna(0)
    rows["wides"] = pd.to_numeric(rows.get("wides"), errors="coerce").fillna(0)
    rows = rows.sort_values(["_match_id", "_innings_id", "over_number", "ball_number", "ball_event_id"], na_position="last")
    source_balls = pd.to_numeric(rows.get("striker_balls_faced"), errors="coerce") if "striker_balls_faced" in rows else pd.Series(index=rows.index, dtype="float64")
    rows["derived_ball_faced"] = rows["wides"].eq(0).astype(int)

    innings_rows = []
    for keys, group in rows.groupby(["player_key", "_match_id", "_innings_id"], dropna=False, sort=False):
        source = pd.to_numeric(group.get("striker_balls_faced"), errors="coerce") if "striker_balls_faced" in group else source_balls.loc[group.index]
        balls_faced = source.ffill().dropna().iloc[-1] if source.notna().any() else group["derived_ball_faced"].sum()
        innings_rows.append(
            {
                "player_key": keys[0],
                "ballByBallBatRuns": float(group["runs_bat"].sum()),
                "ballByBallBatBalls": float(balls_faced or 0),
            }
        )
    if not innings_rows:
        return pd.DataFrame(columns=["player_key", "ballByBallBatSR", "ballByBallBatRuns", "ballByBallBatBalls"])
    grouped = pd.DataFrame(innings_rows).groupby("player_key", as_index=False).agg(
        ballByBallBatRuns=("ballByBallBatRuns", "sum"),
        ballByBallBatBalls=("ballByBallBatBalls", "sum"),
    )
    grouped["ballByBallBatSR"] = grouped.apply(
        lambda row: divide_or_none(float(row["ballByBallBatRuns"]) * 100, float(row["ballByBallBatBalls"])),
        axis=1,
    )
    return grouped[["player_key", "ballByBallBatSR", "ballByBallBatRuns", "ballByBallBatBalls"]]


def build_scorecard_detail_milestone_counts() -> pd.DataFrame:
    deploy_counts = load_deploy_safe_scorecard_detail_milestones(hall_of_fame_detail_source_signature())
    if not deploy_counts.empty:
        return deploy_counts
    scope = MATCH_CENTRE_PROCESSED_ROOT / "all_available"
    matches = read_match_centre_csv(scope / "all_matches.csv")
    batting = read_match_centre_csv(scope / "all_scorecard_batting.csv")
    bowling = read_match_centre_csv(scope / "all_scorecard_bowling.csv")
    frames = []
    if not batting.empty and {"match_id", "innings_id", "participant_id", "runs_scored"}.issubset(batting.columns):
        rows = filter_match_centre_fvcc_rows(batting, matches)
        rows = prepare_match_centre_identity_rows(rows)
        rows["player_key"] = player_keys(rows)
        parsed_scores = rows.apply(lambda row: parse_batting_score(row.get("runs_scored"), row.get("dismissal_type")), axis=1)
        rows["runs_scored_numeric"] = [score[0] for score in parsed_scores]
        rows = scorecard_dedupe(rows, ["match_id", "innings_id", "participant_id", "bat_instance"])
        batting_counts = rows.groupby("player_key", as_index=False).agg(
            batting30s=("runs_scored_numeric", lambda values: int(pd.to_numeric(values, errors="coerce").between(30, 49, inclusive="both").sum()))
        )
        frames.append(batting_counts)
    if not bowling.empty and {"match_id", "innings_id", "participant_id", "wickets_taken"}.issubset(bowling.columns):
        rows = filter_match_centre_fvcc_rows(bowling, matches)
        rows = prepare_match_centre_identity_rows(rows)
        rows["player_key"] = player_keys(rows)
        rows["wickets_taken"] = pd.to_numeric(rows["wickets_taken"], errors="coerce").fillna(0)
        rows = scorecard_dedupe(rows, ["match_id", "innings_id", "participant_id"])
        bowling_counts = rows.groupby("player_key", as_index=False).agg(
            bowling3WIs=("wickets_taken", lambda values: int(pd.to_numeric(values, errors="coerce").isin([3, 4]).sum()))
        )
        frames.append(bowling_counts)
    if not frames:
        return pd.DataFrame(columns=["player_key", "batting30s", "bowling3WIs"])
    output = frames[0]
    for frame in frames[1:]:
        output = output.merge(frame, on="player_key", how="outer")
    for column in ["batting30s", "bowling3WIs"]:
        if column not in output:
            output[column] = 0
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0).astype(int)
    return output[["player_key", "batting30s", "bowling3WIs"]]


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

    state_key = f"hof_leader_expanded_{re.sub(r'[^a-z0-9]+', '_', title.casefold()).strip('_')}"
    expanded = bool(st.session_state.get(state_key, False))
    displayed_leaders = leaders if expanded else leaders.head(6)
    max_value = leaders[metric].max()
    rows = []
    for rank, (_, row) in enumerate(displayed_leaders.iterrows(), start=1):
        value = float(row[metric])
        width = 0 if not max_value else value / max_value * 100
        rows.append(
            '<div class="progress-row hof-progress-row">'
            f'<span class="progress-rank">{rank_badge(rank)}</span>'
            f'<span class="progress-name">{player_profile_link_html(player_id_from_row(row), row["Player"])}</span>'
            f'<span class="progress-value"><strong>{int(value):,} {html.escape(suffix)}</strong></span>'
            f'<div class="progress-track"><div style="width:{width:.0f}%"></div></div>'
            "</div>"
        )
    st.markdown(
        f'<div class="hof-card"><div class="card-title">{html.escape(title)}</div>{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )
    render_hof_expand_control(state_key, expanded, len(leaders))


def render_hof_expand_control(state_key: str, expanded: bool, row_count: int, collapsed_limit: int = 6) -> None:
    if row_count <= collapsed_limit:
        return
    with st.container(key=f"{state_key}_control"):
        if st.button(
            "Show less ↑" if expanded else "Show top 10 ↓",
            key=f"{state_key}_toggle",
        ):
            st.session_state[state_key] = not expanded
            st.rerun()


def render_match_winning_performances(data: dict[str, object]) -> None:
    batting_records = data.get("iconic_batting")
    bowling_records = data.get("iconic_bowling")
    if batting_records is None:
        batting_records = attach_scorecard_match_ids(top_highest_scores(data["batting_raw"], limit=10), "batting")
    if bowling_records is None:
        bowling_records = attach_scorecard_match_ids(top_best_bowling_innings(data["bowling_raw"], limit=10), "bowling")
    if batting_records.empty and bowling_records.empty:
        return
    render_section_heading("Iconic Performances 🌟")
    columns = st.columns(2)
    with columns[0]:
        render_performance_card("Highest Individual Scores", batting_records, "batting")
    with columns[1]:
        render_performance_card("Best Bowling Innings", bowling_records, "bowling")


def premiership_records_signature() -> tuple[tuple[str, float], ...]:
    signature = []
    for path in [HALL_OF_FAME_PREMIERSHIP_WINS_PATH, HALL_OF_FAME_PLAYER_PREMIERSHIPS_PATH]:
        if path.exists():
            signature.append((str(path), path.stat().st_mtime))
    return tuple(signature)


@st.cache_data(show_spinner=False)
def load_premiership_records(_signature: tuple[tuple[str, float], ...]) -> tuple[pd.DataFrame, pd.DataFrame]:
    wins = read_match_centre_csv(HALL_OF_FAME_PREMIERSHIP_WINS_PATH)
    players = read_match_centre_csv(HALL_OF_FAME_PLAYER_PREMIERSHIPS_PATH)
    if not wins.empty:
        wins = wins.drop_duplicates("match_id") if "match_id" in wins else wins
        for column in ["season", "grade_name", "fvcc_team_name", "opponent_team_name", "captain_name", "result_text"]:
            if column in wins:
                wins[column] = wins[column].map(safe_record_text)
        if "scoreboard_url" in wins:
            wins["scoreboard_url"] = wins["scoreboard_url"].map(safe_record_text)
    if not players.empty:
        if {"premiership_count", "evidence_match_ids"}.issubset(players.columns):
            players["premiership_count"] = pd.to_numeric(players["premiership_count"], errors="coerce").fillna(0).astype(int)
            players = players[
                players.apply(
                    lambda row: int(row["premiership_count"]) == len({part.strip() for part in str(row["evidence_match_ids"]).split(",") if part.strip()}),
                    axis=1,
                )
            ]
        name_column = "display_player_name" if "display_player_name" in players else "canonical_player_name"
        players["_premiership_matches_sort"] = 0
        if name_column in players:
            players[name_column] = players[name_column].map(display_player_name)
            matches_lookup = build_all_time_matches_by_player_name()
            if not matches_lookup.empty:
                players["_player_name_key"] = players[name_column].map(player_name_match_key)
                players = players.merge(matches_lookup, left_on="_player_name_key", right_on="player_name_key", how="left")
            else:
                players["matches"] = pd.NA
            players["_premiership_matches_sort"] = pd.to_numeric(players.get("matches"), errors="coerce").fillna(0)
        players["_earliest_premiership_sort"] = players.get("seasons", pd.Series("", index=players.index)).map(earliest_season_sort_key)
        players = players.sort_values(
            ["premiership_count", "_premiership_matches_sort", "_earliest_premiership_sort", name_column],
            ascending=[False, False, True, True],
            na_position="last",
        ).drop(columns=["_player_name_key", "player_name_key", "_premiership_matches_sort", "_earliest_premiership_sort"], errors="ignore")
    return wins, players


def earliest_season_sort_key(value: object) -> int:
    keys = [season_sort_key(part.strip()) for part in safe_record_text(value).split(",") if part.strip()]
    return min(keys) if keys else 999999


def latest_season_sort_key(value: object) -> int:
    keys = [season_sort_key(part.strip()) for part in safe_record_text(value).split(",") if part.strip()]
    return max(keys) if keys else 999999


def render_premiership_records() -> None:
    wins, players = load_premiership_records(premiership_records_signature())
    if wins.empty and players.empty:
        render_section_heading("Premierships 🛡️")
        st.markdown(
            '<div class="hof-card premiership-empty">'
            '<div class="card-title">Premiership records</div>'
            '<p>Premiership records are being prepared from verified finals scorecards.</p>'
            "</div>",
            unsafe_allow_html=True,
        )
        return

    render_section_heading("Premierships 🛡️")
    st.markdown(
        '<div class="premiership-wall-grid">'
        f"{premiership_wins_card_html(wins)}"
        f"{player_premiership_leaders_card_html(players)}"
        "</div>",
        unsafe_allow_html=True,
    )


def premiership_wins_card_html(wins: pd.DataFrame) -> str:
    club_short_name = html.escape(get_club_short_name())
    if wins.empty:
        return (
            '<div class="hof-card premiership-wall-card premiership-empty">'
            f'<div class="premiership-card-title">{club_short_name} Premiership Wins</div>'
            f"<p>No verified {club_short_name} premiership wins available yet.</p>"
            "</div>"
        )
    rows = wins.copy()
    if "match_date" in rows:
        rows["_date_sort"] = pd.to_datetime(rows["match_date"], errors="coerce", utc=True)
        rows = rows.sort_values(["_date_sort", "season"], ascending=[True, True], na_position="last")
    row_html = "".join(premiership_win_row_html(row) for _, row in rows.iterrows())
    return (
        '<div class="hof-card premiership-wall-card premiership-wins-card">'
        f'<div class="premiership-card-title">{club_short_name} Premiership Wins</div>'
        '<div class="premiership-card-scroll">'
        f"{row_html}"
        "</div>"
        "</div>"
    )


def premiership_win_row_html(row: pd.Series) -> str:
    season = safe_record_text(row.get("season"), "Unknown season")
    grade = clean_grade_label_for_record(row.get("grade_name"))
    team = safe_record_text(row.get("fvcc_team_name"), get_club_short_name())
    opponent = clean_opponent_label(row.get("opponent_team_name"), "Opposition")
    captain = safe_record_text(row.get("captain_name"))
    result = safe_record_text(row.get("result_margin_display")) or safe_record_text(row.get("result_text"))
    scorecard = scorecard_url_link_html(
        row.get("scoreboard_url"),
        row.get("match_id"),
        label="View scorecard ↗",
        page_slug="hall-of-fame",
        section_name="premiership_wins",
    )
    grade_line = grade or "Grade not recorded"
    captain_line = f"Captain: {captain}" if captain else "Captain not recorded"
    scorecard_html = f'<div class="premiership-link">{scorecard}</div>' if scorecard else ""
    return (
        '<div class="premiership-win-row">'
        f'<div class="premiership-grade">{html.escape(grade_line)}</div>'
        '<div class="premiership-row-body">'
        '<div class="premiership-row-copy">'
        f'<div class="premiership-season">{season_overview_link_html(season)}</div>'
        f'<div class="premiership-title">{html.escape(team)} <span>defeated {html.escape(opponent)}</span></div>'
        f'<div class="premiership-captain">{html.escape(captain_line)}</div>'
        "</div>"
        '<div class="premiership-sideblock">'
        f'<div class="premiership-result">{html.escape(result)}<span class="premiership-cup">🏆</span></div>'
        f"{scorecard_html}"
        "</div>"
        "</div>"
        "</div>"
    )


def player_premiership_leaders_card_html(
    players: pd.DataFrame,
) -> str:
    if players.empty:
        return (
            '<div class="hof-card premiership-wall-card premiership-empty">'
            '<div class="premiership-card-title">Most Premierships</div>'
            "<p>No verified player premiership records available yet.</p>"
            "</div>"
        )
    limit = min(PREMIERSHIP_PLAYER_EXPANDED_LIMIT, len(players))
    rows = players.head(limit).copy()
    row_html = "".join(
        player_premiership_row_html(rank, row)
        for rank, (_, row) in enumerate(rows.iterrows(), start=1)
    )
    return (
        '<div class="hof-card premiership-wall-card performance-card premiership-player-card">'
        '<div class="premiership-card-title">Most Premierships</div>'
        '<div class="premiership-card-scroll">'
        f"{row_html}"
        "</div>"
        "</div>"
    )


def player_premiership_row_html(rank: int, row: pd.Series) -> str:
    player = safe_record_text(row.get("display_player_name") or row.get("canonical_player_name"), "Unknown player")
    count = safe_record_int(row.get("premiership_count")) or 0
    details = linked_premiership_seasons(row.get("seasons"))
    value = f"{count} premiership{'s' if count != 1 else ''}"
    return (
        '<div class="performance-row premiership-player-row">'
        f'<span class="progress-rank">{rank_badge(rank)}</span>'
        '<div class="performance-player">'
        f'<strong>{player_profile_link_html("", player)}</strong>'
        f'<span>{details}</span>'
        '</div>'
        f'<div class="performance-value">{html.escape(value)}</div>'
        "</div>"
    )


def linked_premiership_seasons(value: object, visible_limit: int = 3) -> str:
    seasons = [part.strip() for part in safe_record_text(value).split(",") if part.strip()]
    if not seasons:
        return ""
    visible = seasons[:visible_limit]
    links = [season_overview_link_html(season) for season in visible]
    if len(seasons) > visible_limit:
        links.append(f"+{len(seasons) - visible_limit} more")
    return ", ".join(links)


def compact_premiership_list(value: object, limit: int = 2) -> str:
    parts = [part.strip() for part in safe_record_text(value).split(",") if part.strip()]
    cleaned = []
    for part in parts:
        label = clean_grade_label_for_record(part)
        if label and label not in cleaned:
            cleaned.append(label)
    if len(cleaned) <= limit:
        return ", ".join(cleaned)
    return ", ".join(cleaned[:limit]) + f" +{len(cleaned) - limit} more"


def render_fastest_batting_milestone_records() -> None:
    track_event_once(
        "fastest_milestones_view",
        {"page_slug": "hall-of-fame", "section_name": "fastest_batting_milestones"},
        key="fastest-milestones-view",
    )
    render_section_heading("Fastest Innings ⚡")
    st.caption("Based on matches with verified ball-by-ball data.")
    milestone_path = batting_milestones_path()
    milestones = load_batting_milestone_records(str(milestone_path) if milestone_path else None, match_centre_milestones_mtime())
    if milestones.empty:
        render_empty_milestone_card(
            "Fastest Innings",
            "No ball-by-ball milestone data available yet.",
            "Run the match-centre milestone builder after refreshing match-centre data.",
        )
        return

    columns = st.columns(2)
    with columns[0]:
        render_ranked_record_card(
            "Fastest 50s",
            milestones,
            "balls_to_50",
            "balls",
            "No verified 50s from available ball-by-ball data yet.",
        )
    with columns[1]:
        render_ranked_record_card(
            "Fastest 100s",
            milestones,
            "balls_to_100",
            "balls",
            "No verified 100s from available ball-by-ball data yet.",
        )


@st.cache_data(show_spinner=False)
def load_batting_milestone_records(_path: str | None = None, _mtime: float | None = None) -> pd.DataFrame:
    path = batting_milestones_path()
    if path is None:
        return pd.DataFrame()
    try:
        records = pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()
    if "final_score_display" not in records:
        records["final_score_display"] = ""
    if "final_runs" in records:
        missing_display = records["final_score_display"].fillna("").astype(str).str.strip().isin(["", "nan", "None"])
        not_out = records.get("is_not_out", pd.Series(False, index=records.index)).map(parse_record_bool)
        final_runs = pd.to_numeric(records["final_runs"], errors="coerce")
        records.loc[missing_display & final_runs.notna(), "final_score_display"] = final_runs[missing_display & final_runs.notna()].astype(int).astype(str)
        star_rows = missing_display & final_runs.notna() & not_out
        records.loc[star_rows, "final_score_display"] = records.loc[star_rows, "final_score_display"].astype(str) + "*"
    return records


def batting_milestones_path() -> Path | None:
    if HALL_OF_FAME_FASTEST_BATTING_MILESTONES_PATH.exists():
        return HALL_OF_FAME_FASTEST_BATTING_MILESTONES_PATH
    all_available = MATCH_CENTRE_PROCESSED_ROOT / "all_available" / "all_batting_milestones.csv"
    root_fallback = MATCH_CENTRE_PROCESSED_ROOT / "all_batting_milestones.csv"
    if all_available.exists():
        return all_available
    if root_fallback.exists():
        return root_fallback
    scopes = available_match_centre_scopes()
    for scope in scopes:
        candidate = scope / "all_batting_milestones.csv"
        if candidate.exists():
            return candidate
    return None


def match_centre_milestones_mtime() -> float | None:
    path = batting_milestones_path()
    if path is None:
        return None
    return path.stat().st_mtime


def match_centre_all_available_signature() -> tuple[tuple[str, float], ...]:
    return match_centre_scope_signature(MATCH_CENTRE_PROCESSED_ROOT / "all_available")


def scorecard_record_rows_signature() -> tuple[tuple[str, float], ...]:
    if HALL_OF_FAME_SCORECARD_RECORD_LINKS_PATH.exists():
        return (
            (str(HALL_OF_FAME_SCORECARD_RECORD_LINKS_PATH), HALL_OF_FAME_SCORECARD_RECORD_LINKS_PATH.stat().st_mtime),
        )
    return match_centre_all_available_signature()


@st.cache_data(show_spinner=False)
def load_scorecard_record_rows(_signature: tuple[tuple[str, float], ...]) -> dict[str, pd.DataFrame]:
    deploy = load_deploy_scorecard_record_rows()
    if any(not frame.empty for frame in deploy.values()):
        return deploy
    scope = MATCH_CENTRE_PROCESSED_ROOT / "all_available"
    if not scope.exists():
        return deploy
    matches = read_match_centre_csv(scope / "all_matches.csv")
    context_columns = [column for column in ["match_id", "season", "first_match_day"] if column in matches]
    context = matches[context_columns].drop_duplicates("match_id") if "match_id" in matches else pd.DataFrame()
    output: dict[str, pd.DataFrame] = {}
    for key, filename in {"batting": "all_scorecard_batting.csv", "bowling": "all_scorecard_bowling.csv"}.items():
        frame = read_match_centre_csv(scope / filename)
        if frame.empty:
            output[key] = frame
            continue
        frame = add_missing_canonical_player_ids(frame)
        if not context.empty and "match_id" in frame:
            frame = frame.merge(context, on="match_id", how="left")
        output[key] = frame
    for key in ["batting", "bowling"]:
        if output.get(key, pd.DataFrame()).empty and not deploy.get(key, pd.DataFrame()).empty:
            output[key] = deploy[key]
    return output


def load_deploy_scorecard_record_rows() -> dict[str, pd.DataFrame]:
    frame = read_match_centre_csv(HALL_OF_FAME_SCORECARD_RECORD_LINKS_PATH)
    if frame.empty or "mode" not in frame:
        return {"batting": pd.DataFrame(), "bowling": pd.DataFrame()}
    return {
        mode: frame[frame["mode"].astype(str) == mode].drop(columns=["mode"], errors="ignore").copy()
        for mode in ["batting", "bowling"]
    }


def attach_scorecard_match_ids(records: pd.DataFrame, mode: str) -> pd.DataFrame:
    if records.empty or "match_id" in records:
        return records
    scorecards = load_scorecard_record_rows(scorecard_record_rows_signature())
    lookup = scorecards.get(mode, pd.DataFrame())
    if lookup.empty or "canonical_player_id" not in records or "canonical_player_id" not in lookup:
        return records
    output = records.copy()
    output["match_id"] = output.apply(lambda row: scorecard_match_id_for_record(row, lookup, mode), axis=1)
    return output


def scorecard_match_id_for_record(row: pd.Series, lookup: pd.DataFrame, mode: str) -> str:
    player_id = str(row.get("canonical_player_id", "")).strip()
    if not player_id:
        return ""
    candidates = lookup[lookup["canonical_player_id"].astype(str) == player_id].copy()
    season = safe_season_label(row.get("season"))
    if season and "season" in candidates:
        candidates = candidates[candidates["season"].astype(str).str.strip().str.casefold() == season.casefold()]
    if candidates.empty:
        return ""
    if mode == "batting":
        score = safe_record_int(row.get("battingHighScore"))
        if score is None or "runs_scored" not in candidates:
            return ""
        candidates = candidates[pd.to_numeric(candidates["runs_scored"], errors="coerce") == score]
        sort_columns = [column for column in ["balls_faced", "first_match_day", "match_id"] if column in candidates]
        ascending = [True, False, True][: len(sort_columns)]
    else:
        wickets, runs = parse_bowling_figures(row.get("bowlingBestInnings"))
        if wickets is None or runs is None or not {"wickets_taken", "runs_conceded"}.issubset(candidates.columns):
            return ""
        candidates = candidates[
            (pd.to_numeric(candidates["wickets_taken"], errors="coerce") == wickets)
            & (pd.to_numeric(candidates["runs_conceded"], errors="coerce") == runs)
        ]
        sort_columns = [column for column in ["first_match_day", "match_id"] if column in candidates]
        ascending = [False, True][: len(sort_columns)]
    if candidates.empty:
        return ""
    if sort_columns:
        candidates = candidates.sort_values(sort_columns, ascending=ascending, na_position="last")
    return str(candidates.iloc[0].get("match_id", "") or "").strip()


def parse_bowling_figures(value: object) -> tuple[int | None, int | None]:
    text = safe_record_text(value)
    match = re.search(r"(\d+)\s*[-/]\s*(\d+)", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def parse_record_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes"}


def render_ranked_record_card(
    title: str,
    records: pd.DataFrame,
    value_col: str,
    value_suffix: str,
    empty_message: str,
) -> None:
    if value_col not in records:
        render_empty_milestone_card(title, empty_message, "This will update as more ball-by-ball seasons are refreshed.")
        return
    rows = records[records[value_col].notna()].copy()
    if rows.empty:
        render_empty_milestone_card(title, empty_message, "This will update as more ball-by-ball seasons are refreshed.")
        return
    rows = add_missing_canonical_player_ids(rows)
    rows["match_date_sort"] = pd.to_datetime(rows.get("match_date"), errors="coerce")
    rows = rows.sort_values(
        [value_col, "final_runs", "match_date_sort"],
        ascending=[True, False, False],
    ).head(FASTEST_MILESTONE_RECORD_LIMIT)
    state_key = f"hof_ranked_record_expanded_{re.sub(r'[^a-z0-9]+', '_', title.casefold()).strip('_')}"
    expanded = bool(st.session_state.get(state_key, False))
    displayed_rows = rows if expanded else rows.head(6)
    row_html = "".join(
        milestone_record_row_html(rank, row, value_col, value_suffix)
        for rank, (_, row) in enumerate(displayed_rows.iterrows(), start=1)
    )
    st.markdown(
        f'<div class="hof-card performance-card"><div class="card-title">{html.escape(title)}</div>{row_html}</div>',
        unsafe_allow_html=True,
    )
    render_hof_expand_control(state_key, expanded, len(rows))


def milestone_record_row_html(rank: int, row: pd.Series, value_col: str, value_suffix: str) -> str:
    player = safe_record_text(row.get("canonical_player_name") or row.get("player_name"), "Unknown player")
    player_id = player_id_from_row(row)
    final_score = safe_record_text(row.get("final_score_display"))
    if not final_score:
        final_runs = safe_record_int(row.get("final_runs"))
        final_score = str(final_runs) if final_runs else ""
    opponent = clean_opponent_label(row.get("opposition_team"), "")
    if final_score and opponent:
        final_line = f"Final score: {final_score} vs {opponent}"
    elif final_score:
        final_line = f"Final score: {final_score}"
    elif opponent:
        final_line = f"vs {opponent}"
    else:
        final_line = ""
    meta_html = milestone_meta_html(row)
    scorecard_html = scorecard_link_html(
        row.get("match_id"),
        page_slug="hall-of-fame",
        section_name="fastest_batting_milestones",
    )
    value = safe_record_int(row.get(value_col))
    value_text = f"{value} {value_suffix}" if value else f"N/A {value_suffix}"
    return (
        '<div class="performance-row">'
        f'<span class="progress-rank">{rank_badge(rank)}</span>'
        '<div class="performance-player">'
        f'<strong>{player_profile_link_html(player_id, player)}</strong>'
        f'<span>{html.escape(final_line)}</span>'
        f'{meta_html}'
        f'{f"<span>{scorecard_html}</span>" if scorecard_html else ""}'
        '</div>'
        f'<div class="performance-value">{html.escape(value_text)}</div>'
        '</div>'
    )


def render_empty_milestone_card(title: str, message: str, note: str) -> None:
    st.markdown(
        (
            '<div class="hof-card performance-card">'
            f'<div class="card-title">{html.escape(title)}</div>'
            '<div class="performance-row">'
            '<span class="progress-rank">–</span>'
            '<div class="performance-player">'
            f'<strong>{html.escape(message)}</strong>'
            f'<span>{html.escape(note)}</span>'
            '</div>'
            '<div class="performance-value">N/A</div>'
            '</div>'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


def milestone_meta_html(row: pd.Series) -> str:
    parts = []
    season = safe_record_text(row.get("season"))
    if season:
        parts.append(season_overview_link_html(season))
    grade = clean_grade_label_for_record(row.get("grade_name"))
    if grade:
        parts.append(html.escape(grade))
    return f"<span>{' • '.join(parts)}</span>" if parts else ""


def clean_grade_label_for_record(value: object) -> str:
    text = safe_record_text(value)
    text = re.sub(r'^\d+\s*-\s*', "", text).strip()
    text = text.replace('"', "")
    return text


def clean_opponent_label(value: object, fallback: str = "Unknown opposition") -> str:
    from src.data.name_normalization import normalize_opponent_club_name

    text = safe_record_text(value, fallback)
    return normalize_opponent_club_name(text, fallback=fallback)


def format_record_date(value: object) -> str:
    date = pd.to_datetime(value, errors="coerce")
    if pd.isna(date):
        return ""
    return date.strftime("%d %b %Y")


def safe_record_text(value: object, fallback: str = "") -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "nat"}:
        return fallback
    return text


def safe_record_int(value: object) -> int | None:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    return int(round(float(numeric)))


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
    records = df.head(10).copy()
    state_key = f"hof_performance_expanded_{re.sub(r'[^a-z0-9]+', '_', title.casefold()).strip('_')}"
    expanded = bool(st.session_state.get(state_key, False))
    displayed_records = records if expanded else records.head(6)
    rows = []
    for rank, (_, row) in enumerate(displayed_records.iterrows(), start=1):
        if mode == "batting":
            value = format_high_score_value(row)
        else:
            value = str(row.get("bowlingBestInnings", "-"))
        meta_html = record_meta_html(row)
        scorecard_html = scorecard_link_html(
            row.get("match_id"),
            page_slug="hall-of-fame",
            section_name="iconic_performances",
        )
        name = row.get("canonical_player_name") or row.get("player_name") or "-"
        player_id = player_id_from_row(row)
        rows.append(
            '<div class="performance-row">'
            f'<span class="progress-rank">{rank_badge(rank)}</span>'
            f'<div class="performance-player"><strong>{player_profile_link_html(player_id, name)}</strong>{meta_html}{f"<span>{scorecard_html}</span>" if scorecard_html else ""}</div>'
            f'<div class="performance-value">{html.escape(str(value))}</div>'
            "</div>"
        )
    st.markdown(
        f'<div class="hof-card performance-card"><div class="card-title">{html.escape(title)}</div>{"".join(rows)}</div>',
        unsafe_allow_html=True,
    )
    render_hof_expand_control(state_key, expanded, len(records))


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
    all_time = data["all_time"]
    batting_innings_by_player = batting_innings_lookup(batting_raw)

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
        meta = record_holder_subtitle(row, metric, batting_innings_by_player)
        cards.append(
            {
                "title": title,
                "player": str(row.get("Player", "-")),
                "player_id": player_id_from_row(row),
                "value": f"{int(row[metric]):,} {suffix}",
                "meta": meta,
            }
        )
    best_win_rate = best_win_rate_record(all_time)
    if best_win_rate:
        cards.append(best_win_rate)
    return cards


def best_win_rate_record(all_time: pd.DataFrame) -> dict[str, str] | None:
    required = {"Player", "Matches", "Win %", "Win Count", "Win Matches"}
    if all_time.empty or not required.issubset(all_time.columns):
        return None
    leaders = all_time.copy()
    for column in ["Matches", "Win %", "Win Count", "Win Matches"]:
        leaders[column] = pd.to_numeric(leaders[column], errors="coerce")
    leaders = leaders[(leaders["Matches"] >= 60) & leaders["Win %"].notna() & leaders["Win Matches"].notna()]
    leaders = leaders[leaders["Win Matches"] > 0]
    if leaders.empty:
        return None
    leaders = leaders.sort_values(["Win %", "Matches", "Player"], ascending=[False, False, True])
    row = leaders.iloc[0]
    wins = safe_record_int(row.get("Win Count"))
    matches = safe_record_int(row.get("Win Matches"))
    meta = f"{wins:,} wins from {matches:,} matches" if wins is not None and matches else ""
    return {
        "title": "Best Win %",
        "player": str(row.get("Player", "-")),
        "player_id": player_id_from_row(row),
        "value": f"{float(row['Win %']):.1f}%",
        "meta": meta,
    }


def batting_innings_lookup(batting_raw: pd.DataFrame) -> dict[str, float]:
    if batting_raw.empty or "canonical_player_id" not in batting_raw or "battingInnings" not in batting_raw:
        return {}
    output = batting_raw.copy()
    output["canonical_player_id"] = output["canonical_player_id"].astype(str)
    output["battingInnings"] = pd.to_numeric(output["battingInnings"], errors="coerce").fillna(0)
    grouped = output.groupby("canonical_player_id")["battingInnings"].sum()
    return {str(player_id): float(value) for player_id, value in grouped.items()}


def record_holder_subtitle(row: pd.Series, metric: str, batting_innings_by_player: dict[str, float]) -> str:
    count = pd.to_numeric(row.get(metric), errors="coerce")
    if pd.isna(count) or float(count) <= 0:
        return ""
    player_id = str(row.get("canonical_player_id") or "").strip()
    batting_innings = batting_innings_by_player.get(player_id)
    matches = pd.to_numeric(row.get("Matches"), errors="coerce")
    match_count = None if pd.isna(matches) else float(matches)

    if metric == "100s":
        return every_text("hundred", count, batting_innings, "innings")
    if metric == "50s":
        return every_text("fifty", count, batting_innings, "innings")
    if metric == "0s":
        return every_text("duck", count, batting_innings, "innings")
    if metric == "4s":
        return per_text("fours", count, batting_innings, "innings")
    if metric == "6s":
        return per_text("sixes", count, batting_innings, "innings")
    if metric == "5WI":
        return every_text("five-wicket haul", count, match_count, "matches")
    if metric == "Maidens":
        return per_text("maidens", count, match_count, "match")
    return ""


def every_text(label: str, count: object, denominator: float | None, denominator_label: str) -> str:
    count_number = pd.to_numeric(count, errors="coerce")
    if pd.isna(count_number) or float(count_number) <= 0 or denominator is None or denominator <= 0:
        return ""
    rate = denominator / float(count_number)
    return f"1 {label} every {compact_one_decimal(rate)} {denominator_label}"


def per_text(label: str, count: object, denominator: float | None, denominator_label: str) -> str:
    count_number = pd.to_numeric(count, errors="coerce")
    if pd.isna(count_number) or denominator is None or denominator <= 0:
        return ""
    rate = float(count_number) / denominator
    return f"{compact_one_decimal(rate)} {label} per {denominator_label}"


def compact_one_decimal(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return ""
    rounded = round(float(number), 1)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:.1f}"


def render_best_ever_seasons(data: dict[str, object]) -> None:
    batting = data.get("best_batting_season")
    bowling = data.get("best_bowling_season")
    if "best_batting_season" not in data:
        batting = best_batting_season(data["batting_raw"])
    if "best_bowling_season" not in data:
        bowling = best_bowling_season(data["bowling_raw"])
    if batting is None and bowling is None:
        return

    render_section_heading("Greatest Individual Seasons 🎖️", mobile_title="Greatest Seasons 🎖️")
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
    player_id_source = "canonical_player_id" if "canonical_player_id" in frame else "player_id"
    if player_source not in frame:
        return None
    frame["_player"] = frame[player_source].fillna("").astype(str).str.strip()
    frame["_player_id"] = frame[player_id_source].fillna("").astype(str).str.strip() if player_id_source in frame else ""
    frame = frame[(frame["_player"] != "") & frame["season"].notna()]
    if frame.empty:
        return None

    rows = []
    for (player_id, player, season), group in frame.groupby(["_player_id", "_player", "season"], dropna=False):
        runs = sum_column(group, "battingAggregate")
        balls = sum_column(group, "battingBallsFaced")
        innings = sum_column(group, "battingInnings")
        not_outs = sum_column(group, "battingNotOuts")
        outs = max(innings - not_outs, 0)
        row = {
            "player": player,
            "player_id": player_id,
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
    player_id_source = "canonical_player_id" if "canonical_player_id" in frame else "player_id"
    if player_source not in frame:
        return None
    frame["_player"] = frame[player_source].fillna("").astype(str).str.strip()
    frame["_player_id"] = frame[player_id_source].fillna("").astype(str).str.strip() if player_id_source in frame else ""
    frame = frame[(frame["_player"] != "") & frame["season"].notna()]
    if frame.empty:
        return None

    rows = []
    for (player_id, player, season), group in frame.groupby(["_player_id", "_player", "season"], dropna=False):
        wickets = sum_column(group, "bowlingWickets")
        balls = sum_column(group, "bowlingBalls")
        runs = sum_column(group, "bowlingRuns")
        row = {
            "player": player,
            "player_id": player_id,
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
        f'<div class="best-season-player">{player_profile_link_html(row.get("player_id"), row["player"])}</div>'
        f'<div class="best-season-season">{season_overview_link_html(row["season"])}</div>'
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


def record_meta_html(row: pd.Series) -> str:
    parts = []
    season = row.get("season")
    if pd.notna(season):
        parts.append(season_overview_link_html(season))
    grade = row.get("canonical_grade_label") or canonical_grade_label(row.get("team_name", ""), row.get("grade_name", ""))
    if grade and grade != "—":
        parts.append(html.escape(str(grade)))
    return f"<span>{' - '.join(parts)}</span>" if parts else ""


def compact_record_team_label(team_name: object) -> str:
    raw = str(team_name)
    if raw.startswith("NMCA -"):
        return ""
    return compact_team_label(raw)


def render_record_card(card: dict[str, str]) -> None:
    st.markdown(record_card_html(card), unsafe_allow_html=True)


def record_card_html(card: dict[str, str]) -> str:
    meta = f'<div class="record-meta">{card["meta"]}</div>' if card.get("meta_html") else f'<div class="record-meta">{html.escape(card["meta"])}</div>' if card.get("meta") else ""
    scorecard = scorecard_link_html(
        card.get("match_id"),
        page_slug="hall-of-fame",
        section_name=str(card.get("section_name") or card.get("title") or "record_card"),
    )
    scorecard_meta = f'<div class="record-meta">{scorecard}</div>' if scorecard else ""
    if card.get("link_type") == "season":
        record_label = season_overview_link_html(card["player"])
    else:
        record_label = player_profile_link_html(card.get("player_id"), card["player"])
    return (
        '<div class="record-card">'
        f'<div class="record-label">{html.escape(card["title"])}</div>'
        f'<div class="record-player">{record_label}</div>'
        f'<div class="record-value">{html.escape(card["value"])}</div>'
        f"{meta}"
        f"{scorecard_meta}"
        "</div>"
    )


def exclusive_club_specs(category: str) -> list[dict[str, object]]:
    specs = {
        "matches": [
            {"metric": "Matches", "label": "matches", "thresholds": [100, 200, 300, 400]},
        ],
        "runs": [
            {"metric": "Runs", "label": "runs", "thresholds": [1000, 2000, 3000, 4000, 5000, 6000]},
        ],
        "wickets": [
            {"metric": "Wickets", "label": "wickets", "thresholds": [100, 200, 300, 400]},
        ],
        "catches": [
            {"metric": "Catches", "label": "catches", "thresholds": [100, 200]},
        ],
    }
    return specs.get(category, specs["matches"])


def render_milestone_club(all_time: pd.DataFrame, selected_category: str = "matches") -> None:
    club_entries: list[tuple[pd.DataFrame, int, str, str]] = []
    for spec in exclusive_club_specs(selected_category):
        metric = str(spec["metric"])
        thresholds = [int(value) for value in spec["thresholds"]]
        if metric not in all_time:
            continue
        players = all_time.copy()
        players[metric] = pd.to_numeric(players[metric], errors="coerce").fillna(0)
        players = players[players[metric] >= min(thresholds)].copy()
        if players.empty:
            continue
        players["milestone_band"] = players[metric].apply(lambda value: highest_reached_threshold(value, thresholds))
        players = players[players["milestone_band"].notna()].copy()
        for threshold in sorted(thresholds, reverse=True):
            club_players = players[players["milestone_band"] == threshold].sort_values(
                [metric, "Player"], ascending=[False, True]
            )
            if club_players.empty:
                continue
            club_entries.append((club_players, threshold, str(spec["label"]), metric))

    render_milestone_view_selector("exclusive")
    with st.container(key="milestone_exclusive_panel"):
        st.markdown(
            '<div class="milestone-section-heading"><h2>Exclusive Clubs 💎</h2></div>',
            unsafe_allow_html=True,
        )
        render_milestone_club_selector(selected_category)
        if not club_entries:
            st.markdown(
                '<div class="milestone-empty-card">No players have reached this exclusive club category yet.</div>',
                unsafe_allow_html=True,
            )
            return

        columns = st.columns(2)
        for index, (club_players, threshold, label, metric) in enumerate(club_entries):
            state_key = milestone_club_expand_state_key(metric, threshold)
            expanded = bool(st.session_state.get(state_key, False))
            with columns[index % 2]:
                st.markdown(
                    milestone_club_card_html(club_players, threshold, label, metric, expanded=expanded),
                    unsafe_allow_html=True,
                )
                render_milestone_club_expand_control(state_key, expanded, len(club_players))


def milestone_club_selector_html(selected_category: str) -> str:
    items = [
        (
            '<a class="milestone-segment'
            f'{" active" if slug == selected_category else ""}" '
            f'href="{html.escape(milestone_page_url("exclusive", slug), quote=True)}" '
            f'target="_self" role="tab" aria-selected="{str(slug == selected_category).lower()}">'
            f"{html.escape(label)}</a>"
        )
        for slug, label in milestone_club_category_options()
    ]
    return f'<nav class="milestone-segmented milestone-segmented-compact" aria-label="Exclusive club category">{"".join(items)}</nav>'


def milestone_club_card_html(
    players: pd.DataFrame,
    threshold: int,
    label: str,
    metric: str,
    expanded: bool = False,
) -> str:
    member_rows = []
    visible_players = players.head(10 if expanded else 5)
    for index, (_, row) in enumerate(visible_players.iterrows(), start=1):
        value = int(round(float(row[metric])))
        member_rows.append(
            '<div class="milestone-member-row">'
            f'<span>{index}. {player_profile_link_html(player_id_from_row(row), row["Player"])}</span>'
            f'<strong>{html.escape(milestone_club_value_label(value, label))}</strong>'
            "</div>"
        )
    return (
        '<article class="milestone-club-card">'
        '<div class="milestone-club-card-head">'
        f'<div class="milestone-club-name">{threshold:,}+ {html.escape(label.title())} Club</div>'
        f'<div class="milestone-club-count">{len(players):,} {"player" if len(players) == 1 else "players"}</div>'
        "</div>"
        f'<div class="milestone-member-list">{"".join(member_rows)}</div>'
        "</article>"
    )


def milestone_club_value_label(value: int, label: str) -> str:
    unit = label.casefold().strip()
    return f"{value:,} {unit}"


def milestone_club_expand_state_key(metric: str, threshold: int) -> str:
    safe_metric = re.sub(r"[^a-z0-9]+", "_", metric.casefold()).strip("_")
    return f"milestone_club_{safe_metric}_{threshold}_expanded"


def render_milestone_club_expand_control(state_key: str, expanded: bool, player_count: int) -> None:
    if player_count <= 5:
        return
    label = "Show less ↑" if expanded else "Show top 10 ↓"
    with st.container(key=f"{state_key}_control"):
        if st.button(label, key=f"{state_key}_toggle"):
            st.session_state[state_key] = not expanded
            st.rerun()


def highest_reached_threshold(value: object, thresholds: list[int]) -> int | None:
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    reached = [threshold for threshold in thresholds if float(numeric) >= threshold]
    return max(reached) if reached else None


def render_detailed_all_time_records(all_time_or_tables: pd.DataFrame | dict[str, pd.DataFrame]) -> None:
    render_section_heading("Detailed Records 📊")
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
        "canonical_player_id",
        "Player",
        "Teams/Grades",
        "Seasons Played",
        "Matches",
        "Runs",
        "Bat Avg",
        "Bat SR",
        "HS",
        "30s",
        "50s",
        "100s",
        "Wickets",
        "Bowl Avg",
        "Econ",
        "Bowl SR",
        "BBI",
        "3WI",
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
    table = link_player_column(table)
    table = link_season_columns(table)
    for column in ["Seasons Played", "Matches", "Runs", "30s", "50s", "100s", "Wickets", "3WI", "5WI", "Catches", "Stumpings", "Run Outs", "Dismissals"]:
        if column in table:
            table[column] = pd.to_numeric(table[column], errors="coerce")
    for column in ["Bat Avg", "Bowl Avg", "Econ", "Bowl SR", "Win %"]:
        if column in table:
            table[column] = pd.to_numeric(table[column], errors="coerce")
    return format_table_missing_values(table)


@st.cache_data(show_spinner=False)
def format_all_time_batting_table(all_time: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "canonical_player_id",
        "Player",
        "Seasons Played",
        "Debut Season",
        "Latest Season",
        "Matches",
        "Win %",
        "Runs",
        "Bat Avg",
        "Bat SR",
        "HS",
        "30s",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
    ]
    table = select_display_columns(all_time, columns).copy()
    if "Runs" in table:
        table = table.sort_values(["Runs", "Bat Avg", "Player"], ascending=[False, False, True], na_position="last")
    table = table.rename(columns={"Seasons Played": "Seasons"})
    table = link_player_column(table)
    table = link_season_columns(table)
    table = coerce_display_numbers(table)
    return apply_hof_table_sorting(table, "batting")


@st.cache_data(show_spinner=False)
def format_all_time_bowling_table(all_time: pd.DataFrame) -> pd.DataFrame:
    source = all_time.copy()
    if "Balls Bowled" in source:
        source["Overs"] = source["Balls Bowled"].map(format_balls_as_overs)
    columns = [
        "canonical_player_id",
        "Player",
        "Seasons Played",
        "Matches",
        "Win %",
        "Overs",
        "Maidens",
        "Wickets",
        "Avg",
        "Bowl SR",
        "Econ",
        "BBI",
        "3WI",
        "5WI",
        "10WM",
    ]
    table = select_display_columns(source, columns).copy()
    if "Bowl Avg" in source and "Avg" not in table:
        table.insert(table.columns.get_loc("Bowl SR"), "Avg", source.loc[table.index, "Bowl Avg"])
    if "Wickets" in table:
        table = table.sort_values(["Wickets", "Bowl SR", "Player"], ascending=[False, True, True], na_position="last")
    table = table.rename(columns={"Seasons Played": "Seasons"})
    table = link_player_column(table)
    table = link_season_columns(table)
    return apply_hof_table_sorting(coerce_display_numbers(table), "bowling")


@st.cache_data(show_spinner=False)
def format_all_time_fielding_table(all_time: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "canonical_player_id",
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
    table = table.rename(columns={"Seasons Played": "Seasons"})
    table = link_player_column(table)
    table = link_season_columns(table)
    return apply_hof_table_sorting(coerce_display_numbers(table), "fielding")


def render_all_time_detail_table(table: pd.DataFrame, key_prefix: str) -> None:
    started_at = time.perf_counter()
    components.html(hof_sortable_table_html(table, key_prefix), height=560, scrolling=False)
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
        .str.replace("N/A", "", regex=False)
        .str.replace("—", "", regex=False)
        .str.strip()
    )
    return pd.to_numeric(cleaned, errors="coerce")


def make_widget_key(prefix: str, column: str) -> str:
    safe_prefix = re.sub(r"[^a-zA-Z0-9_]+", "_", str(prefix)).strip("_")
    safe_column = re.sub(r"[^a-zA-Z0-9_]+", "_", str(column).replace("%", "pct")).strip("_")
    return f"{safe_prefix}_{safe_column}".lower()


def link_display_label(value: object) -> str:
    text = str(value or "")
    return unquote(text.rsplit("#", 1)[-1]).strip() if "#" in text else text.strip()


def ordered_player_link_values(values: pd.Series) -> pd.Series:
    return ordered_text_values(values, key_func=lambda value: link_display_label(value).casefold())


def ordered_season_link_values(values: pd.Series) -> pd.Series:
    return ordered_text_values(values, key_func=lambda value: season_sort_key(link_display_label(value)))


def ordered_text_values(values: pd.Series, key_func) -> pd.Series:
    labels = values.map(lambda value: "—" if pd.isna(value) or str(value).strip() == "" else str(value))
    unique_values = [value for value in labels.drop_duplicates().tolist() if value.strip()]
    categories = sorted(unique_values, key=key_func)
    return pd.Series(pd.Categorical(labels, categories=categories, ordered=True), index=values.index)


def ordered_numeric_text_values(values: pd.Series, missing_label: str = "N/A", precision: int = 1, suffix: str = "") -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce")
    labels = numeric.map(lambda value: missing_label if pd.isna(value) else f"{float(value):.{precision}f}{suffix}")
    present = sorted({label for label in labels if label != missing_label}, key=lambda label: float(label.removesuffix(suffix)))
    categories = [*present, missing_label]
    return pd.Series(pd.Categorical(labels, categories=categories, ordered=True), index=values.index)


def coerce_hof_numeric_columns(output: pd.DataFrame, table_type: str) -> pd.DataFrame:
    numeric_columns = {
        "Seasons",
        "Seasons Played",
        "Matches",
        "Win %",
        "Runs",
        "Bat Avg",
        "Bat SR",
        "30s",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
        "Maidens",
        "Wickets",
        "Avg",
        "Bowl Avg",
        "Bowl SR",
        "Econ",
        "3WI",
        "5WI",
        "10WM",
        "Catches",
        "Stumpings",
        "Run Outs",
        "Dismissals",
    }
    for column in numeric_columns.intersection(output.columns):
        output[column] = pd.to_numeric(output[column], errors="coerce")
    if "Overs" in output:
        output["Overs"] = output["Overs"].map(
            lambda value: pd.NA if cricket_overs_to_balls(value) is None else float(str(value))
        )
    return output


def ordered_high_score_values(values: pd.Series) -> pd.Series:
    labels = values.map(lambda value: "—" if pd.isna(value) or str(value).strip() == "" else str(value))
    unique_values = [value for value in labels.drop_duplicates().tolist() if value.strip()]
    categories = sorted(unique_values, key=high_score_category_sort_key)
    return pd.Series(pd.Categorical(labels, categories=categories, ordered=True), index=values.index)


def high_score_category_sort_key(value: object) -> tuple[int, int, int, str]:
    runs, not_out = parse_batting_score(value)
    if runs is None:
        return (1, 0, 0, str(value))
    return (0, -runs, -int(not_out), str(value))


def ordered_overs_values(values: pd.Series) -> pd.Series:
    labels = values.map(lambda value: "—" if pd.isna(value) or str(value).strip() == "" else str(value))
    unique_values = [value for value in labels.drop_duplicates().tolist() if value.strip()]
    categories = sorted(unique_values, key=lambda value: cricket_overs_to_balls(value) if cricket_overs_to_balls(value) is not None else 10**9)
    return pd.Series(pd.Categorical(labels, categories=categories, ordered=True), index=values.index)


def apply_hof_table_sorting(table: pd.DataFrame, table_type: str) -> pd.DataFrame:
    output = table.copy()
    output = coerce_hof_numeric_columns(output, table_type)
    if "Player" in output:
        output["Player"] = ordered_player_link_values(output["Player"])
    for column in ["Season", "Debut Season", "Latest Season"]:
        if column in output:
            output[column] = ordered_season_link_values(output[column])
    if "HS" in output:
        output["HS"] = ordered_high_score_values(output["HS"])
    if "BBI" in output:
        output["BBI"] = ordered_bbi_values(output["BBI"])
    return output


def hof_sortable_table_html(table: pd.DataFrame, key_prefix: str) -> str:
    table_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", key_prefix).strip("-") or "hof-detail-table"
    columns = table.columns.tolist()
    header_html = '<th class="hof-col-rank" aria-label="Current sorted rank">#</th>' + "".join(
        f'<th class="{hof_detail_column_class(column)}" data-column="{index + 1}" data-default-dir="{hof_detail_default_sort_dir(column)}">'
        f'<span>{html.escape(str(column))}<span class="sort-indicator"></span></span></th>'
        for index, column in enumerate(columns)
    )
    rows = []
    for row_index, (_, row) in enumerate(table.iterrows(), start=1):
        cells = [f'<td class="hof-col-rank" data-rank-cell="1">{row_index}</td>']
        for column in columns:
            value = row.get(column)
            display = hof_detail_display_value(column, value)
            sort_value, missing = hof_detail_sort_value(column, value)
            cells.append(
                f'<td class="{hof_detail_column_class(column)}" data-sort="{html.escape(sort_value, quote=True)}" data-missing="{int(missing)}">'
                f"{display}</td>"
            )
        rows.append(f"<tr>{''.join(cells)}</tr>")

    return f"""
    <style>
      :root {{
        --hof-ink: #080a3f;
        --hof-muted: #686f95;
        --hof-grid: #dfe3ee;
        --hof-soft: #f7f7fc;
        --hof-link: #6d3df7;
      }}
      html, body {{
        margin: 0;
        padding: 0;
        background: transparent;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      .hof-detail-table-wrap {{
        height: 548px;
        overflow: auto;
        border: 1px solid var(--hof-grid);
        border-radius: 18px;
        background: #fff;
      }}
      table.hof-detail-sortable {{
        border-collapse: separate;
        border-spacing: 0;
        min-width: 900px;
        width: 100%;
        color: var(--hof-ink);
        font-size: 13px;
      }}
      .hof-detail-sortable th,
      .hof-detail-sortable td {{
        border-right: 1px solid var(--hof-grid);
        border-bottom: 1px solid var(--hof-grid);
        padding: 8px 9px;
        white-space: nowrap;
        background: #fff;
      }}
      .hof-detail-sortable th {{
        position: sticky;
        top: 0;
        z-index: 3;
        background: #fbfbfe;
        color: var(--hof-muted);
        font-weight: 700;
        text-align: left;
      }}
      .hof-detail-sortable th span {{
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 5px;
      }}
      .hof-detail-sortable th.sorted-asc .sort-indicator::after {{ content: "↑"; }}
      .hof-detail-sortable th.sorted-desc .sort-indicator::after {{ content: "↓"; }}
      .hof-detail-sortable td:not(.hof-col-player):not(.hof-col-debut-season):not(.hof-col-latest-season),
      .hof-detail-sortable th:not(.hof-col-player):not(.hof-col-debut-season):not(.hof-col-latest-season) {{
        text-align: right;
      }}
      .hof-detail-sortable .hof-col-rank {{
        position: sticky;
        left: 0;
        z-index: 2;
        min-width: 38px;
        max-width: 38px;
        width: 38px;
        color: #737998;
        font-weight: 750;
        text-align: center !important;
        background: #fff;
      }}
      .hof-detail-sortable .hof-col-player {{
        position: sticky;
        left: 38px;
        z-index: 2;
        min-width: 108px;
        max-width: 118px;
        text-align: left;
        white-space: normal;
        line-height: 1.2;
        overflow-wrap: anywhere;
        box-shadow: 3px 0 8px rgba(8, 10, 63, 0.06);
      }}
      .hof-detail-sortable .hof-col-debut-season,
      .hof-detail-sortable .hof-col-latest-season {{
        min-width: 88px;
      }}
      .hof-detail-sortable th.hof-col-player {{
        z-index: 4;
      }}
      .hof-detail-sortable th.hof-col-rank {{
        z-index: 5;
        background: #fbfbfe;
      }}
      .hof-detail-sortable a {{
        color: #0072ce;
        text-decoration: none;
        font-weight: 650;
      }}
      .hof-detail-sortable a:hover {{
        color: var(--hof-link);
        text-decoration: underline;
      }}
      .hof-detail-sortable tr:hover td {{
        background: var(--hof-soft);
      }}
      .hof-detail-sortable tr:hover td.hof-col-rank,
      .hof-detail-sortable tr:hover td.hof-col-player {{
        background: var(--hof-soft);
      }}
    </style>
    <div class="hof-detail-table-wrap">
      <table id="{html.escape(table_id, quote=True)}" class="hof-detail-sortable" data-player-column-index="1">
        <thead><tr>{header_html}</tr></thead>
        <tbody>{''.join(rows)}</tbody>
      </table>
    </div>
    <script>
      (() => {{
        const table = document.getElementById({table_id!r});
        if (!table) return;
        const tbody = table.querySelector("tbody");
        const headers = Array.from(table.querySelectorAll("th[data-column]"));
        const playerColumnIndex = Number(table.dataset.playerColumnIndex || 1);
        const renumberRows = () => {{
          Array.from(tbody.querySelectorAll("tr")).forEach((row, index) => {{
            const rankCell = row.querySelector('[data-rank-cell="1"]');
            if (rankCell) rankCell.textContent = String(index + 1);
          }});
        }};
        const textValue = (row, index) => row.children[index].textContent.trim().toLocaleLowerCase();
        const sortValue = (row, index) => {{
          const cell = row.children[index];
          if (cell.dataset.missing === "1") return null;
          const raw = cell.dataset.sort;
          const numeric = Number(raw);
          return Number.isFinite(numeric) ? numeric : raw.toLocaleLowerCase();
        }};
        const compare = (a, b, index, dir) => {{
          const av = sortValue(a, index);
          const bv = sortValue(b, index);
          if (av === null && bv === null) return textValue(a, playerColumnIndex).localeCompare(textValue(b, playerColumnIndex));
          if (av === null) return 1;
          if (bv === null) return -1;
          let result = 0;
          if (typeof av === "number" && typeof bv === "number") {{
            result = av === bv ? 0 : av < bv ? -1 : 1;
          }} else {{
            result = String(av).localeCompare(String(bv), undefined, {{ numeric: true, sensitivity: "base" }});
          }}
          if (result === 0) result = textValue(a, playerColumnIndex).localeCompare(textValue(b, playerColumnIndex));
          return dir === "asc" ? result : -result;
        }};
        const sortHeader = (header, index) => {{
            const current = header.dataset.sortDir;
            const dir = current ? (current === "asc" ? "desc" : "asc") : header.dataset.defaultDir;
            headers.forEach(item => {{
              item.classList.remove("sorted-asc", "sorted-desc");
              delete item.dataset.sortDir;
            }});
            header.dataset.sortDir = dir;
            header.classList.add(`sorted-${{dir}}`);
            Array.from(tbody.querySelectorAll("tr"))
              .sort((a, b) => compare(a, b, index, dir))
              .forEach(row => tbody.appendChild(row));
            renumberRows();
        }};
        const resolveInternalHref = (href) => {{
          let base = document.referrer || window.location.href;
          try {{
            if (window.parent && window.parent.location && window.parent.location.href) {{
              base = window.parent.location.href;
            }}
          }} catch (error) {{}}
          return new URL(href, base).toString();
        }};
        table.querySelectorAll('a[data-hof-internal-link="1"]').forEach(link => {{
          const href = link.getAttribute("href");
          if (!href) return;
          link.setAttribute("href", resolveInternalHref(href));
          link.setAttribute("target", "_blank");
          link.setAttribute("rel", "noopener noreferrer");
        }});
        table.addEventListener("click", event => {{
          const link = event.target.closest('a[data-hof-internal-link="1"]');
          if (!link) return;
          const href = link.getAttribute("href");
          if (!href) return;
          let opened = null;
          try {{
            opened = window.parent.open(href, "_blank");
          }} catch (error) {{}}
          if (opened) {{
            event.preventDefault();
            return;
          }}
          try {{
            const parentDocument = window.parent.document;
            const parentLink = parentDocument.createElement("a");
            parentLink.href = href;
            parentLink.target = "_blank";
            parentLink.rel = "noopener noreferrer";
            parentLink.style.display = "none";
            parentDocument.body.appendChild(parentLink);
            parentLink.click();
            setTimeout(() => parentLink.remove(), 0);
            event.preventDefault();
            return;
          }} catch (error) {{}}
          try {{
            window.parent.location.href = href;
            event.preventDefault();
          }} catch (error) {{}}
        }});
        headers.forEach(header => {{
          header.addEventListener("click", () => sortHeader(header, Number(header.dataset.column)));
        }});
        renumberRows();
      }})();
    </script>
    """


def hof_detail_column_class(column: object) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", str(column).strip().casefold()).strip("-")
    return f"hof-col-{text or 'column'}"


def hof_detail_default_sort_dir(column: object) -> str:
    return "asc" if str(column) in {"Player", "Debut Season", "Latest Season"} else "desc"


def hof_detail_display_value(column: str, value: object) -> str:
    if column == "Player":
        return hof_detail_link_cell(value, profile_link_display_pattern())
    if column in {"Debut Season", "Latest Season"}:
        return hof_detail_link_cell(value, overview_link_display_pattern())
    if pd.isna(value) or str(value).strip() == "":
        return "N/A"
    if column == "Win %" or column == "Bat SR":
        numeric = pd.to_numeric(value, errors="coerce")
        return "N/A" if pd.isna(numeric) else f"{float(numeric):.1f}%"
    if column in {"Avg", "Bat Avg", "Bowl Avg", "Bowl SR", "Econ"}:
        numeric = pd.to_numeric(value, errors="coerce")
        return "N/A" if pd.isna(numeric) else f"{float(numeric):.2f}"
    if column == "Overs":
        balls = cricket_overs_to_balls(value)
        return "N/A" if balls is None else balls_to_overs_display(balls) or "N/A"
    if column in {"Seasons", "Seasons Played", "Matches", "Runs", "30s", "50s", "100s", "0s", "4s", "6s", "Maidens", "Wickets", "3WI", "5WI", "10WM", "Catches", "Stumpings", "Run Outs", "Dismissals"}:
        numeric = pd.to_numeric(value, errors="coerce")
        return "N/A" if pd.isna(numeric) else f"{int(numeric):,}"
    text = str(value).strip()
    return html.escape(text if text and text != "—" else "N/A")


def hof_detail_link_cell(value: object, display_pattern: str) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return "N/A"
    text = str(value).strip()
    label = link_display_label(text)
    if text.startswith("?"):
        return (
            f'<a href="{html.escape(text, quote=True)}" target="_blank" rel="noopener noreferrer" data-hof-internal-link="1">'
            f"{html.escape(label or text)}</a>"
        )
    return html.escape(label or text)


def hof_detail_sort_value(column: str, value: object) -> tuple[str, bool]:
    if pd.isna(value) or str(value).strip() in {"", "—", "N/A"}:
        return "", True
    if column == "Player":
        return link_display_label(value).casefold(), False
    if column in {"Debut Season", "Latest Season"}:
        return str(season_sort_key(link_display_label(value))), False
    if column == "HS":
        runs, _ = parse_batting_score(value)
        return ("" if runs is None else str(runs), runs is None)
    if column == "BBI":
        wickets, runs = parse_bowling_figures(value)
        if wickets is None or runs is None:
            return "", True
        return str(wickets * 10000 - runs), False
    if column == "Overs":
        balls = cricket_overs_to_balls(value)
        return ("" if balls is None else str(balls), balls is None)
    numeric = pd.to_numeric(value, errors="coerce")
    if not pd.isna(numeric):
        return str(float(numeric)), False
    return str(value).casefold(), False


def format_table_missing_values(table: pd.DataFrame) -> pd.DataFrame:
    output = table.copy()
    integer_columns = {
        "Seasons",
        "Seasons Played",
        "Matches",
        "Runs",
        "30s",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
        "Wickets",
        "Maidens",
        "3WI",
        "5WI",
        "10WM",
        "Catches",
        "Stumpings",
        "Run Outs",
        "Dismissals",
    }
    decimal_columns = {"Avg", "Bat Avg", "Bowl Avg", "Econ", "Bowl SR", "Win %"}
    for column in output.columns:
        if column in integer_columns:
            values = pd.to_numeric(output[column], errors="coerce")
            output[column] = values.map(lambda value: "—" if pd.isna(value) else f"{int(value):,}")
        elif column == "Win %":
            values = pd.to_numeric(output[column], errors="coerce")
            output[column] = values.map(lambda value: "—" if pd.isna(value) else f"{float(value):.1f}")
        elif column == "Bat SR":
            values = pd.to_numeric(output[column], errors="coerce")
            output[column] = values.map(lambda value: "N/A" if pd.isna(value) else f"{float(value):.1f}")
        elif column in decimal_columns:
            values = pd.to_numeric(output[column], errors="coerce")
            output[column] = values.map(lambda value: "—" if pd.isna(value) else f"{float(value):.2f}")
        else:
            output[column] = output[column].map(lambda value: "—" if pd.isna(value) or str(value).strip() == "" else value)
    return output


def hall_of_fame_column_config(columns: list[str]) -> dict[str, object]:
    config = {}
    config["Player"] = st.column_config.LinkColumn("Player", pinned=True, width=150, display_text=profile_link_display_pattern())
    config["Teams/Grades"] = st.column_config.TextColumn("Teams/Grades", width=150)
    for column in ["Debut Season", "Latest Season"]:
        if column in columns:
            config[column] = st.column_config.LinkColumn(column, width=145, display_text=overview_link_display_pattern())
    integer_columns = {
        "Seasons",
        "Seasons Played",
        "Matches",
        "Runs",
        "30s",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
        "Wickets",
        "Maidens",
        "3WI",
        "5WI",
        "10WM",
        "Catches",
        "Stumpings",
        "Run Outs",
        "Dismissals",
    }
    decimal_columns = {"Avg", "Bat Avg", "Bowl Avg", "Econ", "Bowl SR", "Win %"}
    percent_columns = {"Bat SR", "Win %"}
    width_overrides = {
        "Seasons": 78,
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
            if column in percent_columns:
                config[column] = st.column_config.NumberColumn(column, width=72, format="%.1f%%")
            elif column == "Overs":
                config[column] = st.column_config.NumberColumn(column, width=78, format="%.1f")
            elif column in integer_columns:
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
        ("Catches", "Catches", 100, 10, "catches", "Career Milestones"),
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
        ordered = (
            season_table.sort_values(["season_sort", "name"], ascending=[False, False])["name"]
            .dropna()
            .drop_duplicates()
            .tolist()
        )
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
        "canonical_player_id",
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

    id_column = "canonical_player_id" if "canonical_player_id" in df else "player_key"
    selected_columns = ["Player", value_col]
    if id_column in df:
        selected_columns.append(id_column)
    values = df[selected_columns].copy()
    values[value_col] = pd.to_numeric(values[value_col], errors="coerce")
    values = values[values[value_col].notna() & (values[value_col] > 0)]
    if values.empty:
        return pd.DataFrame(columns=milestone_watchlist_columns())

    # Hall of Fame data is already one row per player, but group defensively in
    # case future processed data introduces split player rows.
    group_columns = ["Player"]
    if id_column in values:
        group_columns.append(id_column)
    grouped = values.groupby(group_columns, as_index=False)[value_col].sum()
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
    if "canonical_player_id" not in grouped:
        grouped["canonical_player_id"] = grouped[id_column] if id_column in grouped else ""
    return grouped[milestone_watchlist_columns()]


def next_milestone_target(value: float, step: int) -> int:
    current = int(value)
    if current % step == 0:
        return current + step
    return ((current // step) + 1) * step


def render_milestone_kpis(watchlist: pd.DataFrame) -> None:
    near_matches = milestone_unique_players(watchlist, ["Matches"])
    near_batting = milestone_unique_players(watchlist, ["Runs"])
    near_bowling_fielding = milestone_unique_players(
        watchlist,
        ["Wickets", "Catches"],
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


def render_career_milestone_cards(watchlist: pd.DataFrame, hall_of_fame_watch: pd.DataFrame) -> None:
    category_cards = "".join(
        milestone_progress_group_html(watchlist, category)
        for category in ["Matches", "Runs", "Wickets", "Catches"]
    )
    club_short_name = html.escape(get_club_short_name())
    render_milestone_view_selector("upcoming")
    with st.container(key="milestone_upcoming_panel"):
        st.markdown(
            (
                '<div class="milestone-section-heading"><h2>Milestone Watchlist 📍</h2></div>'
                '<div class="milestone-section-subtitle">'
                f"Showing active players only — players who have appeared for {club_short_name} in the last 3 seasons."
                "</div>"
                f'<div class="milestone-watch-grid">{category_cards}</div>'
                f"{hall_of_fame_watch_html(hall_of_fame_watch)}"
            ),
            unsafe_allow_html=True,
        )


def milestone_progress_group_html(watchlist: pd.DataFrame, category: str) -> str:
    rows = milestone_category_rows(watchlist, category)
    rule = milestone_group_rule(category)
    if rows.empty:
        body = f'<div class="milestone-empty-card">{html.escape(milestone_empty_message(category))}</div>'
    else:
        body = "".join(milestone_progress_card_html(row) for _, row in rows.head(6).iterrows())
    return (
        '<article class="milestone-group-card">'
        '<div class="milestone-group-head">'
        f'<div class="milestone-group-title">{html.escape(category)}</div>'
        f'<div class="milestone-group-rule">{html.escape(rule)}</div>'
        "</div>"
        f"{body}"
        "</article>"
    )


def milestone_group_rule(category: str) -> str:
    rules = {
        "Matches": "within 10 matches",
        "Runs": "within 100 runs",
        "Wickets": "within 10 wickets",
        "Catches": "within 10 catches",
    }
    return rules.get(category, "close to milestone")


def milestone_empty_message(category: str) -> str:
    messages = {
        "Matches": "No players within 10 matches of the next 100-match milestone.",
        "Runs": "No players within 100 runs of the next 1000-run milestone.",
        "Wickets": "No players within 10 wickets of the next 100-wicket milestone.",
        "Catches": "No players within 10 catches of the next 100-catch milestone.",
    }
    return messages.get(category, "No players currently close to this milestone.")


def milestone_progress_card_html(row: pd.Series) -> str:
    progress = max(0, min(float(row["Progress %"]), 100))
    current = int(row["Current Total"])
    target = int(row["Target Milestone"])
    remaining = int(row["Remaining"])
    unit = str(row["Unit"])
    return (
        '<div class="milestone-progress-card">'
        '<div class="milestone-progress-top">'
        "<div>"
        f'<strong>{player_profile_link_html(player_id_from_row(row), row["Player"])}</strong>'
        f'<span>{current:,} / {target:,} {html.escape(unit)}</span>'
        "</div>"
        f'<div class="milestone-away">{remaining:,} {html.escape(unit)} away</div>'
        "</div>"
        f'<div class="progress-track"><div style="width:{progress:.1f}%"></div></div>'
        "</div>"
    )


def hall_of_fame_watch_html(hall_of_fame_watch: pd.DataFrame) -> str:
    if hall_of_fame_watch.empty:
        cards = '<div class="milestone-empty-card">No active players are currently close to entering an all-time top 5.</div>'
    else:
        cards = "".join(hall_of_fame_watch_card_html(row) for _, row in hall_of_fame_watch.head(8).iterrows())
    return (
        '<aside class="milestone-hof-watch">'
        '<div class="milestone-group-head">'
        "<div>"
        "<h3>Hall of Fame Watch 👀</h3>"
        '<div class="milestone-mini-subtitle">Players close to entering the all-time top 5.</div>'
        "</div>"
        '<div class="milestone-group-rule">top 5 movement</div>'
        "</div>"
        f'<div class="milestone-mini-grid">{cards}</div>'
        "</aside>"
    )


def hall_of_fame_watch_card_html(row: pd.Series) -> str:
    remaining = int(row["Remaining"])
    unit = str(row["Unit"])
    metric = str(row["Metric"])
    return (
        '<div class="milestone-mini-card">'
        f'<strong>{player_profile_link_html(player_id_from_row(row), row["Player"])}</strong>'
        f'<div>{remaining:,} {html.escape(unit)} from entering Top 5 all-time {html.escape(metric)}.</div>'
        "</div>"
    )


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
            f'<div><strong>{player_profile_link_html(player_id_from_row(row), row["Player"])}</strong>'
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

    category_options = ["All", "Matches", "Runs", "Wickets", "Catches"]
    selected_category = st.selectbox("Milestone category", category_options, key="milestone_category_filter")

    filtered = watchlist.copy()
    if selected_category != "All":
        filtered = filtered[filtered["Category"] == selected_category]

    if filtered.empty:
        st.info("No players are currently within milestone range for this category.")
        return

    table_columns = ["Player", "canonical_player_id", "Category", "Current Total", "Target Milestone", "Remaining", "Progress %"]
    table = filtered[[column for column in table_columns if column in filtered]].copy()
    table = link_player_column(table)
    for column in ["Current Total", "Target Milestone", "Remaining"]:
        if column in table:
            table[column] = pd.to_numeric(table[column], errors="coerce").round().astype("Int64")
    if "Progress %" in table:
        table["Progress %"] = pd.to_numeric(table["Progress %"], errors="coerce").round(1)
    with st.container(key="full_stats_card"):
        st.dataframe(
            table,
            use_container_width=True,
            hide_index=True,
            height=520,
            column_config={
                "Player": st.column_config.LinkColumn("Player", pinned=True, width="medium", display_text=profile_link_display_pattern()),
                "Category": st.column_config.TextColumn("Category", width="medium"),
                "Current Total": st.column_config.NumberColumn("Current Total", format="%d"),
                "Target Milestone": st.column_config.NumberColumn("Target Milestone", format="%d"),
                "Remaining": st.column_config.NumberColumn("Remaining", format="%d"),
                "Progress %": st.column_config.NumberColumn("Progress %", format="%.1f%%"),
            },
        )


def render_player_profile_page() -> None:
    index = load_player_profile_index(metadata_mtime(), player_aliases_mtime())
    st.markdown(
        f"""
        <div class="player-profile-page"></div>
        <h1 class="page-title">Player Spotlight 🏏</h1>
        {configured_club_label_html()}
        <div class="page-subtitle">Search any player and explore their career story across seasons, teams, and formats.</div>
        """,
        unsafe_allow_html=True,
    )

    if index.empty:
        st.info("Historical player data is not available yet. Refresh local backup to build player profiles.")
        return

    player_names_by_id = dict(zip(index["id"].astype(str), index["name"].astype(str)))
    option_ids = list(player_names_by_id.keys())
    st.session_state["player_profile_valid_ids"] = option_ids
    st.session_state["player_profile_name_to_id"] = {
        player_name: player_id
        for player_id, player_name in player_names_by_id.items()
        if player_id
    }

    def set_selected_player_id(player_id: object, *, manual: bool = False) -> str:
        player_id_text = str(player_id or "").strip()
        st.session_state["selected_player_id"] = player_id_text
        st.session_state["selected_player_profile_id"] = player_id_text
        if manual:
            st.session_state["manual_player_profile_selection"] = True
            st.session_state["last_player_profile_query_param"] = current_player_query_token()
        return player_id_text

    query_token = current_player_query_token()
    last_query_token = str(st.session_state.get("last_player_profile_query_param", "") or "").strip()
    if query_token and query_token != last_query_token:
        query_player_id = resolve_player_query_to_id(player_names_by_id)
        st.session_state["last_player_profile_query_param"] = query_player_id or query_token
        if query_player_id:
            set_selected_player_id(query_player_id)
            st.session_state.pop("manual_player_profile_selection", None)
            if st.session_state.get("player_profile_selector_id") != query_player_id:
                st.session_state.pop("player_profile_selector_id", None)
            if query_param_value("player_id") != query_player_id:
                sync_player_profile_query(query_player_id)
                st.session_state["last_player_profile_query_param"] = query_player_id

    pending_player_id = str(st.session_state.get("pending_player_profile_id", "") or "").strip()
    if pending_player_id in player_names_by_id:
        set_selected_player_id(pending_player_id)
        st.session_state["last_player_profile_query_param"] = pending_player_id
        st.session_state.pop("manual_player_profile_selection", None)
        st.session_state.pop("pending_player_profile_id", None)
        if st.session_state.get("player_profile_selector_id") != pending_player_id:
            st.session_state.pop("player_profile_selector_id", None)
    elif pending_player_id:
        set_selected_player_id("")
        st.session_state.pop("pending_player_profile_id", None)
        st.session_state.pop("player_profile_selector_id", None)

    selected_player_id = str(
        st.session_state.get("selected_player_id")
        or st.session_state.get("selected_player_profile_id")
        or ""
    ).strip()
    widget_player_id = str(st.session_state.get("player_profile_selector_id") or "").strip()
    if widget_player_id in player_names_by_id and widget_player_id != selected_player_id:
        selected_player_id = set_selected_player_id(widget_player_id, manual=True)
        if current_player_query_token() != selected_player_id:
            sync_player_profile_query(selected_player_id)
        st.session_state["last_player_profile_query_param"] = selected_player_id
    if selected_player_id not in player_names_by_id:
        selected_player_id = ""
        set_selected_player_id("")
    st.session_state.pop("player_profile_selector_label", None)
    with st.container(key="player_selector_card"):
        selected_id = st.selectbox(
            "Search player",
            option_ids,
            index=option_ids.index(selected_player_id) if selected_player_id in option_ids else None,
            format_func=lambda player_id: player_names_by_id.get(str(player_id), str(player_id)),
            placeholder="Select a player...",
            key="player_profile_selector_id",
        )
        selected_id = str(selected_id or "").strip()
        if selected_id != selected_player_id:
            selected_id = set_selected_player_id(selected_id, manual=True)
            if selected_id:
                sync_player_profile_query(selected_id)
                st.session_state["last_player_profile_query_param"] = selected_id
        elif (
            selected_id
            and st.session_state.get("manual_player_profile_selection")
            and current_player_query_token() != selected_id
        ):
            sync_player_profile_query(selected_id)
            st.session_state["last_player_profile_query_param"] = selected_id
        st.markdown(
            '<div class="profile-selector-help">Start typing a name to find a player from club records.</div>',
            unsafe_allow_html=True,
        )
    if not selected_id:
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

    profile = get_player_profile_data(selected_id, metadata_mtime(), player_aliases_mtime())
    profile_view = build_player_profile_view(profile)
    if profile_view["career"].empty:
        st.info("No local historical data is available for this player yet.")
        return
    profile_source = (
        "dropdown"
        if st.session_state.get("manual_player_profile_selection")
        else "deep_link"
        if current_player_query_token()
        else "dropdown"
    )
    player_name = player_names_by_id.get(selected_id, selected_id)
    track_event_once(
        "player_profile_view",
        {
            "page_slug": PLAYER_PROFILE_QUERY_PAGE,
            "player_name": player_name,
            "player_slug": analytics_player_slug(player_name, selected_id),
            "player_id": selected_id,
            "source": profile_source,
        },
        key=f"player-profile-view:{selected_id}",
    )

    render_player_header_card(profile_view)
    render_player_breakdown(profile_view["career"].iloc[0])
    render_player_recent_form(profile_view["career"].iloc[0])
    render_player_highlights(profile_view)
    render_player_intelligence(profile_view)
    render_player_peer_comparison(profile_view)
    render_player_trends(profile_view["season_table"])
    render_player_performance_breakdown(profile_view)
    render_player_milestones(profile_view["career"].iloc[0])


def render_player_profile_v2_page() -> None:
    index = load_player_profile_index(metadata_mtime(), player_aliases_mtime())
    st.markdown('<div class="player-profile-v2-page"></div>', unsafe_allow_html=True)
    st.markdown(
        """
        <div class="player-v2-topline">Player Profile v2 preview</div>
        <div class="player-v2-title-row">
            <div>
                <h1 class="player-v2-page-title">Player scouting profile 🧬</h1>
                {configured_club_label_html()}
            </div>
            <span class="player-v2-preview-badge">Hidden experimental page</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if index.empty:
        st.info("Historical player data is not available yet. Refresh local backup to build player profiles.")
        return

    player_names_by_id = dict(zip(index["id"].astype(str), index["name"].astype(str)))
    option_ids = list(player_names_by_id.keys())
    st.session_state["player_profile_valid_ids"] = option_ids
    st.session_state["player_profile_name_to_id"] = {
        player_name: player_id
        for player_id, player_name in player_names_by_id.items()
        if player_id
    }
    query_player_id = resolve_player_query_to_id(player_names_by_id)
    default_player_id = query_player_id or default_player_profile_v2_id(player_names_by_id)
    with st.container(key="player_v2_selector_card"):
        selected_id = st.selectbox(
            "Search player",
            option_ids,
            index=option_ids.index(default_player_id) if default_player_id in option_ids else 0,
            format_func=lambda player_id: player_names_by_id.get(str(player_id), str(player_id)),
            placeholder="Select a player...",
            key="player_profile_v2_selector_id",
        )
        selected_id = str(selected_id or "").strip()
        st.markdown(
            '<div class="profile-selector-help">Pick a player to view a scouting-card style profile built from club records.</div>',
            unsafe_allow_html=True,
        )
    if selected_id and query_param_value("player_id") != selected_id:
        sync_player_profile_query(selected_id, PLAYER_PROFILE_V2_QUERY_PAGE)

    profile = get_player_profile_data(selected_id, metadata_mtime(), player_aliases_mtime())
    profile_view = build_player_profile_view(profile)
    if profile_view["career"].empty:
        st.info("No local historical data is available for this player yet.")
        return

    player_name = player_names_by_id.get(selected_id, selected_id)
    track_event_once(
        "player_profile_v2_view",
        {
            "page_slug": PLAYER_PROFILE_V2_QUERY_PAGE,
            "player_name": player_name,
            "player_slug": analytics_player_slug(player_name, selected_id),
            "player_id": selected_id,
            "source": "deep_link" if current_player_query_token() else "dropdown",
        },
        key=f"player-profile-v2-view:{selected_id}",
    )

    context = build_player_profile_v2_context(profile_view)
    render_player_profile_v2_hero(profile_view, context)
    render_player_profile_v2_career_strip(profile_view["career"].iloc[0])
    render_player_profile_v2_dna(profile_view, context)
    render_player_profile_v2_coach_board(profile_view, context)
    render_player_profile_v2_peer_comparison(profile_view)
    render_player_profile_v2_advanced_grid(profile_view, context)
    render_player_profile_v2_standout_performances(profile_view)
    render_player_profile_v2_partnerships(profile_view)
    render_player_profile_v2_milestone_watch(profile_view["career"].iloc[0])
    render_player_profile_v2_timeline(profile_view, context)
    render_player_profile_v2_coverage_card(profile_view, context)
    render_player_profile_v2_breakdown(profile_view)


def default_player_profile_v2_id(player_names_by_id: dict[str, str]) -> str:
    for player_id, name in player_names_by_id.items():
        if str(name).strip().casefold() == "vinay sharma":
            return player_id
    return next(iter(player_names_by_id), "")


def build_player_profile_v2_context(profile_view: dict[str, pd.DataFrame]) -> dict[str, object]:
    career = profile_view["career"].iloc[0]
    player_id = str(career.get("canonical_player_id", "") or "").strip()
    player_name = str(career.get("Player", "") or "").strip()
    name_key = player_name_match_key(player_name)
    win_row = player_v2_lookup_row(load_deploy_safe_win_rates(player_win_rates_signature()), player_id, name_key)
    _, premierships = load_premiership_records(premiership_records_signature())
    premiership_row = player_v2_lookup_row(premierships, player_id, name_key)
    bbb_row = player_v2_lookup_row(read_match_centre_csv(HALL_OF_FAME_BBB_BATTING_RATES_PATH), player_id, name_key)
    return {
        "win_row": win_row,
        "premiership_row": premiership_row,
        "bbb_row": bbb_row,
        "win_pct": pd.to_numeric(win_row.get("win_pct"), errors="coerce") if not win_row.empty else pd.NA,
        "win_matches": pd.to_numeric(win_row.get("Win Matches"), errors="coerce") if not win_row.empty else pd.NA,
        "wins": pd.to_numeric(win_row.get("Win Count"), errors="coerce") if not win_row.empty else pd.NA,
        "premiership_count": int(pd.to_numeric(premiership_row.get("premiership_count"), errors="coerce") or 0) if not premiership_row.empty else 0,
        "premiership_seasons": safe_record_text(premiership_row.get("seasons")) if not premiership_row.empty else "",
        "bbb_runs": pd.to_numeric(bbb_row.get("bbb_runs"), errors="coerce") if not bbb_row.empty else pd.NA,
        "bbb_balls": pd.to_numeric(bbb_row.get("bbb_balls_faced"), errors="coerce") if not bbb_row.empty else pd.NA,
        "bbb_innings": pd.to_numeric(bbb_row.get("bbb_batting_innings"), errors="coerce") if not bbb_row.empty else pd.NA,
    }


def player_v2_lookup_row(frame: pd.DataFrame, player_id: str, name_key: str) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="object")
    output = frame.copy()
    if player_id:
        for column in ["canonical_player_id", "player_key", "player_id"]:
            if column in output:
                matched = output[output[column].astype(str) == player_id]
                if not matched.empty:
                    return matched.iloc[0]
    if name_key:
        for column in ["player_name_key", "_player_name_key"]:
            if column in output:
                matched = output[output[column].astype(str) == name_key]
                if not matched.empty:
                    return matched.iloc[0]
        for column in ["display_player_name", "canonical_player_name", "Player", "player_name"]:
            if column in output:
                matched = output[output[column].map(player_name_match_key) == name_key]
                if not matched.empty:
                    return matched.iloc[0]
    return pd.Series(dtype="object")


def render_player_profile_v2_hero(profile_view: dict[str, pd.DataFrame], context: dict[str, object]) -> None:
    career = profile_view["career"].iloc[0]
    badges = player_role_badges(career, profile_view)
    if int(context.get("premiership_count") or 0) > 0:
        badges.append("Premiership Player")
    if pd.notna(context.get("bbb_balls")) and float(context.get("bbb_balls") or 0) > 0:
        badges.append("Verified Ball-by-Ball Batting")
    badge_html = "".join(
        f'<span class="player-v2-badge {player_v2_badge_class(badge)}">{html.escape(badge)}</span>'
        for badge in unique_preserve_order(badges)[:7]
    )
    signature_title, signature_copy = player_v2_signature_stat(career, context)
    fact_cards = [
        ("Career span", str(career.get("Career Span", "—") or "—")),
        ("Matches", format_int(career.get("Matches"))),
        ("Runs", format_int(career.get("Runs"))),
        ("Wickets", format_int(career.get("Wickets"))),
        ("Catches", format_int(career.get("Catches"))),
        ("Win %", player_v2_percent(context.get("win_pct"))),
        ("Premierships", format_int(context.get("premiership_count")) if context.get("premiership_count") else "—"),
        ("Best fit", player_v2_best_fit(profile_view)),
    ]
    facts_html = "".join(
        f'<div class="player-v2-fact"><small>{html.escape(label)}</small><strong>{html.escape(value)}</strong></div>'
        for label, value in fact_cards
    )
    insight = player_profile_insight(career, badges)
    player_name = html.escape(str(career.get("Player", "-")))
    st.markdown(
        f"""
        <section class="player-v2-hero">
            <div class="player-v2-hero-grid">
                <div>
                    {configured_club_label_html("player-v2-club-eyebrow")}
                    <h2>{player_name}</h2>
                    <p class="player-v2-hero-copy">{html.escape(insight)}</p>
                    <div class="player-v2-badge-row">{badge_html}</div>
                </div>
                <aside class="player-v2-identity-panel">
                    <div class="player-v2-signature-card">
                        <small>Signature stat</small>
                        <strong>{html.escape(signature_title)}</strong>
                        <span>{html.escape(signature_copy)}</span>
                    </div>
                    <div class="player-v2-facts">{facts_html}</div>
                </aside>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def unique_preserve_order(values: list[str]) -> list[str]:
    seen = set()
    output = []
    for value in values:
        text = str(value or "").strip()
        key = text.casefold()
        if text and key not in seen:
            output.append(text)
            seen.add(key)
    return output


def player_v2_badge_class(label: object) -> str:
    text = str(label).casefold()
    if "premiership" in text or "legend" in text:
        return "gold"
    if "ball-by-ball" in text or "safe" in text or "winner" in text:
        return "green"
    return ""


def player_v2_signature_stat(career: pd.Series, context: dict[str, object]) -> tuple[str, str]:
    wickets = numeric_value(career, "Wickets")
    balls_bowled = numeric_value(career, "Balls Bowled")
    runs = numeric_value(career, "Runs")
    matches = numeric_value(career, "Matches")
    catches = numeric_value(career, "Catches")
    bbb_runs = pd.to_numeric(context.get("bbb_runs"), errors="coerce")
    bbb_balls = pd.to_numeric(context.get("bbb_balls"), errors="coerce")
    if wickets >= 25 and balls_bowled > 0:
        overs_per_wicket = balls_bowled / 6 / wickets
        return f"Wicket every {overs_per_wicket:.1f} overs", "Bowling impact from scorecard-safe career wicket and overs records."
    if pd.notna(bbb_runs) and pd.notna(bbb_balls) and bbb_balls > 0:
        return f"Verified SR {bbb_runs * 100 / bbb_balls:.1f}%", "Uses ball-by-ball runs and balls only, never mixed with scorecard totals."
    if runs >= 1000 and matches:
        return f"{runs / matches:.1f} runs per match", "Career scoring footprint across scorecard-safe club records."
    if catches >= 50 and matches:
        return f"{catches / matches:.2f} catches per match", "Fielding involvement from scorecard-safe dismissal records."
    return str(career.get("HS", "Record building") or "Record building"), "Profile identity will sharpen as more scorecard and ball-by-ball detail is promoted."


def player_v2_best_fit(profile_view: dict[str, pd.DataFrame]) -> str:
    grade_table = profile_view.get("grade_table", pd.DataFrame())
    if grade_table.empty or "Grade" not in grade_table:
        return "—"
    output = grade_table.copy()
    output["_impact"] = pd.to_numeric(output.get("Runs", 0), errors="coerce").fillna(0) + pd.to_numeric(output.get("Wickets", 0), errors="coerce").fillna(0) * 20
    output = output[output["_impact"] > 0].sort_values("_impact", ascending=False)
    return str(output.iloc[0].get("Grade", "—")) if not output.empty else "—"


def render_player_profile_v2_career_strip(career: pd.Series) -> None:
    cards = [
        ("Matches", format_int(career.get("Matches"))),
        ("Runs", format_int(career.get("Runs"))),
        ("Bat Avg", format_decimal(career.get("Bat Avg"))),
        ("HS", str(career.get("HS", "—") or "—")),
        ("Wickets", format_int(career.get("Wickets"))),
        ("Bowl Avg", format_decimal(career.get("Bowl Avg"))),
        ("BBI", str(career.get("BBI", "—") or "—")),
        ("Catches", format_int(career.get("Catches"))),
        ("Run Outs", format_int(career.get("Run Outs"))),
        ("Stumpings", format_int(career.get("Stumpings"))),
        ("Dismissals", format_int(career.get("Dismissals"))),
        ("Seasons", format_int(career.get("Seasons Count"))),
    ]
    html_cards = "".join(
        f'<div class="player-v2-stat-tile"><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>'
        for label, value in cards
    )
    st.markdown(f'<div class="player-v2-stat-strip">{html_cards}</div>', unsafe_allow_html=True)


def render_player_profile_v2_dna(profile_view: dict[str, pd.DataFrame], context: dict[str, object]) -> None:
    section = player_v2_section_header("Player DNA Snapshot", "Identity cards designed for quick coaching readouts.", "Scorecard-safe")
    st.markdown(section, unsafe_allow_html=True)
    cards = player_v2_dna_cards(profile_view, context)
    st.markdown(f'<div class="player-v2-grid player-v2-grid-4">{"".join(cards)}</div>', unsafe_allow_html=True)


def player_v2_dna_cards(profile_view: dict[str, pd.DataFrame], context: dict[str, object]) -> list[str]:
    career = profile_view["career"].iloc[0]
    matches = numeric_value(career, "Matches")
    runs = numeric_value(career, "Runs")
    wickets = numeric_value(career, "Wickets")
    bat_avg = numeric_value(career, "Bat Avg")
    bowl_avg = numeric_value(career, "Bowl Avg")
    econ = numeric_value(career, "Econ")
    dismissals = numeric_value(career, "Dismissals")
    bat_label = "Anchor" if bat_avg >= 20 and runs >= 300 else "Run contributor" if runs >= 300 else "Lower-order contributor"
    bowl_label = "Economy Controller" if econ and econ < 3.8 and wickets >= 25 else "Wicket Taker" if wickets >= 25 else "Occasional bowler"
    field_label = "Safe Hands" if matches and dismissals / matches >= 0.35 else "Fielding contributor"
    impact_label = "Premiership Player" if context.get("premiership_count") else "Club contributor"
    return [
        player_v2_dna_card("Batter type", bat_label, ["Bat avg " + format_decimal(career.get("Bat Avg")), f"{format_int(runs)} runs"], min(100, max(18, bat_avg * 2.5))),
        player_v2_dna_card("Bowler type", bowl_label, [f"{format_int(wickets)} wickets", "Eco " + format_decimal(career.get("Econ"))], 78 if wickets >= 100 else 58 if wickets >= 25 else 30),
        player_v2_dna_card("Fielding profile", field_label, [f"{format_int(dismissals)} dismissals", f"{format_int(career.get('Catches'))} catches"], 75 if dismissals >= 75 else 48),
        player_v2_dna_card("Match impact", impact_label, [player_v2_percent(context.get("win_pct")) + " win rate", f"{format_int(context.get('premiership_count'))} premierships"], 84 if context.get("premiership_count") else 52),
    ]


def player_v2_dna_card(title: str, headline: str, tags: list[str], width: float) -> str:
    tag_html = "".join(f'<span>{html.escape(tag)}</span>' for tag in tags if tag and tag != "—")
    return (
        '<article class="player-v2-card player-v2-dna-card">'
        f'<div class="player-v2-kicker">{html.escape(title)}</div>'
        f'<h3>{html.escape(headline)}</h3>'
        f'<div class="player-v2-traits">{tag_html}</div>'
        f'<div class="player-v2-meter"><span style="width:{max(0, min(100, width)):.0f}%"></span></div>'
        '</article>'
    )


def render_player_profile_v2_coach_board(profile_view: dict[str, pd.DataFrame], context: dict[str, object]) -> None:
    st.markdown(
        player_v2_section_header(
            "Coach Insight Board 🧠",
            "Practical selection, role and training cues from the available player record.",
            "Coach view",
        ),
        unsafe_allow_html=True,
    )
    cards = player_v2_coach_cards(profile_view, context)
    st.markdown(f'<div class="player-v2-grid player-v2-grid-3">{"".join(cards)}</div>', unsafe_allow_html=True)


def player_v2_coach_cards(profile_view: dict[str, pd.DataFrame], context: dict[str, object]) -> list[str]:
    career = profile_view["career"].iloc[0]
    season_table = profile_view.get("season_table", pd.DataFrame())
    matches = numeric_value(career, "Matches")
    runs = numeric_value(career, "Runs")
    wickets = numeric_value(career, "Wickets")
    balls_bowled = numeric_value(career, "Balls Bowled")
    bat_avg = numeric_value(career, "Bat Avg")
    dismissals = numeric_value(career, "Dismissals")
    latest = latest_player_v2_season_summary(season_table)
    role = "All-round selection option" if runs >= 500 and wickets >= 50 else "Batting-first profile" if runs >= wickets * 15 else "Bowling-first profile" if wickets >= 25 else "Squad depth profile"
    batting_cue = "Reliable run base" if bat_avg >= 20 and runs >= 500 else "Can lift scoring impact with repeatable starts"
    bowling_cue = "Use as workload bowler" if balls_bowled >= 900 else "Use in matchup spells" if wickets >= 15 else "Bowling sample is limited"
    fielding_cue = "Reliable fielding asset" if matches and dismissals / matches >= 0.35 else "Fielding impact is building"
    return [
        player_v2_coach_card("Selection fit", role, "Role recommendation based on runs, wickets and workload balance."),
        player_v2_coach_card("Batting plan", batting_cue, f"{format_int(runs)} scorecard runs at {format_decimal(career.get('Bat Avg'))}. Ball-faced rates stay in verified ball-by-ball sections."),
        player_v2_coach_card("Bowling usage", bowling_cue, f"{format_balls_as_overs(balls_bowled) if balls_bowled else '—'} career overs from scorecard records."),
        player_v2_coach_card("Field placement", fielding_cue, f"{format_int(dismissals)} fielding dismissals across {format_int(matches)} matches."),
        player_v2_coach_card("Current form read", latest[0], latest[1]),
        player_v2_coach_card("Data confidence", player_v2_coverage_label(context), "Ball-by-ball metrics are shown only when a verified deploy-safe summary exists."),
    ]


def player_v2_coach_card(title: str, headline: str, copy: str) -> str:
    return (
        '<article class="player-v2-card player-v2-coach-card">'
        f'<div class="player-v2-kicker">{html.escape(title)}</div>'
        f'<h3>{html.escape(headline)}</h3>'
        f'<p>{html.escape(copy)}</p>'
        '</article>'
    )


def latest_player_v2_season_summary(season_table: pd.DataFrame) -> tuple[str, str]:
    if season_table.empty or "Season" not in season_table:
        return "No recent season record", "Season-level profile will appear when aggregate rows exist."
    row = season_table.sort_values("Season", key=lambda series: series.map(profile_season_sort_key), ascending=False).iloc[0]
    headline = f"{row.get('Season', 'Latest season')}: {format_int(row.get('Runs'))} runs, {format_int(row.get('Wickets'))} wickets"
    return headline, str(row.get("Teams/Grades", "Latest team/grade context unavailable") or "Latest team/grade context unavailable")


def player_v2_coverage_label(context: dict[str, object]) -> str:
    bbb_balls = pd.to_numeric(context.get("bbb_balls"), errors="coerce")
    if pd.notna(bbb_balls) and bbb_balls > 0:
        return f"Verified BBB sample: {int(bbb_balls):,} balls faced"
    return "Scorecard-safe profile"


def render_player_profile_v2_peer_comparison(profile_view: dict[str, pd.DataFrame]) -> None:
    rows = player_v2_peer_rows(profile_view)
    if not rows:
        return
    st.markdown(
        player_v2_section_header(
            "Player vs Peers 📊",
            "Compared with players from the same seasons and available grade scope.",
            "Peer model",
        ),
        unsafe_allow_html=True,
    )
    cards = "".join(player_v2_peer_card(category, metrics) for category, metrics in rows.items() if metrics)
    st.markdown(f'<div class="player-v2-grid player-v2-grid-2">{cards}</div>', unsafe_allow_html=True)


def player_v2_peer_rows(profile_view: dict[str, pd.DataFrame]) -> dict[str, list[dict[str, object]]]:
    career = profile_view["career"].iloc[0]
    season_table = profile_view.get("season_table", pd.DataFrame())
    if season_table.empty or "Season" not in season_table:
        return {}
    seasons = tuple(sorted(season_table["Season"].dropna().astype(str).unique(), key=profile_season_sort_key))
    player_id = str(career.get("canonical_player_id", "") or "").strip()
    if not player_id or not seasons:
        return {}
    aliases = load_player_aliases()
    batting = apply_team_grade_display_columns(apply_player_identity_mapping(read_processed_table("all_seasons_batting"), aliases))
    bowling = apply_team_grade_display_columns(apply_player_identity_mapping(read_processed_table("all_seasons_bowling"), aliases))
    batting_rows = aggregate_peer_batting(filter_peer_scope(batting, seasons, player_peer_grade_scope(profile_view)), seasons)
    bowling_rows = aggregate_peer_bowling(filter_peer_scope(bowling, seasons, player_peer_grade_scope(profile_view)), seasons)
    return {
        "Batting": build_peer_metric_rows(
            batting_rows,
            player_id,
            [
                ("Batting Avg", "bat_avg", False, "decimal"),
                ("Boundary Rate", "boundary_rate", False, "decimal"),
                ("Innings per Duck", "innings_per_duck", False, "decimal"),
            ],
            average_overrides={
                "bat_avg": divide_or_none(sum_numeric(batting_rows, "runs"), sum_numeric(batting_rows, "outs")),
                "innings_per_duck": divide_or_none(sum_numeric(batting_rows, "innings"), sum_numeric(batting_rows, "ducks")),
            },
        ),
        "Bowling": build_peer_metric_rows(
            bowling_rows,
            player_id,
            [
                ("Bowling Avg", "bowl_avg", True, "decimal"),
                ("Bowling SR", "bowl_sr", True, "decimal"),
                ("Economy", "economy", True, "decimal"),
            ],
            average_overrides={
                "bowl_avg": divide_or_none(sum_numeric(bowling_rows, "runs_against"), sum_numeric(bowling_rows, "wickets")),
                "bowl_sr": divide_or_none(sum_numeric(bowling_rows, "balls"), sum_numeric(bowling_rows, "wickets")),
                "economy": divide_or_none(sum_numeric(bowling_rows, "runs_against") * 6, sum_numeric(bowling_rows, "balls")),
            },
        ),
    }


def player_v2_peer_card(title: str, rows: list[dict[str, object]]) -> str:
    item_html = []
    for row in rows:
        player_position = peer_marker_position(row.get("value"), row.get("minimum"), row.get("maximum"))
        average_position = peer_marker_position(row.get("average"), row.get("minimum"), row.get("maximum"))
        player_marker = f'<span class="player-v2-marker player" style="left:{player_position:.1f}%"></span>' if player_position is not None else ""
        average_marker = f'<span class="player-v2-marker peer" style="left:{average_position:.1f}%"></span>' if average_position is not None else ""
        status = str(row.get("status") or "—")
        item_html.append(
            '<div class="player-v2-peer-row">'
            '<div class="player-v2-peer-top">'
            f'<strong>{html.escape(str(row.get("label", "")))}</strong>'
            f'<span>{html.escape(format_peer_metric_value(row.get("value"), str(row.get("format", "decimal"))))}</span>'
            '</div>'
            '<div class="player-v2-peer-meta">'
            f'<span>Peer avg. {html.escape(format_peer_metric_value(row.get("average"), str(row.get("format", "decimal"))))}</span>'
            f'<em class="{peer_status_class(status)}">{html.escape(status)}</em>'
            '</div>'
            f'<div class="player-v2-range">{average_marker}{player_marker}</div>'
            '</div>'
        )
    return f'<article class="player-v2-card player-v2-peer-card"><h3>{html.escape(title)}</h3>{"".join(item_html)}</article>'


def render_player_profile_v2_advanced_grid(profile_view: dict[str, pd.DataFrame], context: dict[str, object]) -> None:
    st.markdown(
        player_v2_section_header(
            "Advanced Identity Reads",
            "Insight cards separate scorecard-safe evidence from ball-by-ball or match-centre coverage.",
            "Trust labelled",
        ),
        unsafe_allow_html=True,
    )
    cards = [
        player_v2_best_position_card(profile_view),
        player_v2_dismissal_card(profile_view),
        player_v2_favourite_grade_card(profile_view),
        player_v2_favourite_opponent_card(context),
    ]
    st.markdown(f'<div class="player-v2-grid player-v2-grid-2">{"".join(cards)}</div>', unsafe_allow_html=True)


def player_v2_best_position_card(profile_view: dict[str, pd.DataFrame]) -> str:
    grade_table = profile_view.get("grade_table", pd.DataFrame())
    if grade_table.empty:
        return player_v2_empty_advanced_card("Best batting position", "Coverage limited", "Batting-order scorecard rows are not deployed yet.")
    rows = grade_table.copy()
    rows["_runs"] = pd.to_numeric(rows.get("Runs", 0), errors="coerce").fillna(0)
    rows = rows[rows["_runs"] > 0].sort_values("_runs", ascending=False).head(4)
    if rows.empty:
        return player_v2_empty_advanced_card("Best batting position", "Coverage limited", "No batting sample available for a position-style read.")
    max_runs = max(1.0, float(rows["_runs"].max()))
    bars = "".join(
        '<div class="player-v2-break-row">'
        f'<strong>{html.escape(str(row.get("Grade", "—")))}</strong>'
        f'<div><span style="width:{float(row["_runs"]) / max_runs * 100:.1f}%"></span></div>'
        f'<em>{format_int(row.get("Runs"))}</em>'
        '</div>'
        for _, row in rows.iterrows()
    )
    return (
        '<article class="player-v2-card player-v2-advanced-card">'
        '<div class="player-v2-card-head"><div class="player-v2-kicker">Best Position</div><span>Scorecard-safe proxy</span></div>'
        '<h3>Best deployed split is by grade</h3>'
        f'{bars}'
        '<p class="player-v2-insight">True batting-position reads need per-innings batting order data; this uses grade-level scoring as a safe coaching proxy.</p>'
        '</article>'
    )


def player_v2_dismissal_card(profile_view: dict[str, pd.DataFrame]) -> str:
    career = profile_view["career"].iloc[0]
    innings = numeric_value(career, "Innings")
    outs = numeric_value(career, "Outs")
    not_outs = max(0, innings - outs)
    ducks = numeric_value(career, "0s")
    if innings <= 0:
        return player_v2_empty_advanced_card("Dismissal fingerprint", "Coverage limited", "No batting innings are available for this player.")
    values = [
        ("Outs", outs, innings),
        ("Not outs", not_outs, innings),
        ("Ducks", ducks, innings),
    ]
    bars = "".join(
        '<div class="player-v2-break-row">'
        f'<strong>{html.escape(label)}</strong>'
        f'<div><span style="width:{(value / max(1, total)) * 100:.1f}%"></span></div>'
        f'<em>{value:.0f}</em>'
        '</div>'
        for label, value, total in values
    )
    return (
        '<article class="player-v2-card player-v2-advanced-card">'
        '<div class="player-v2-card-head"><div class="player-v2-kicker">Dismissal Fingerprint</div><span>Coverage limited</span></div>'
        '<h3>Dismissal types need innings-level data</h3>'
        f'{bars}'
        '<p class="player-v2-insight">Caught/bowled/LBW fingerprinting will appear once dismissal-type scorecard rows are promoted to deploy-safe data.</p>'
        '</article>'
    )


def player_v2_favourite_grade_card(profile_view: dict[str, pd.DataFrame]) -> str:
    grade_table = profile_view.get("grade_table", pd.DataFrame())
    if grade_table.empty:
        return player_v2_empty_advanced_card("Favourite ground", "Coverage limited", "Ground-level records are not deployed for this player yet.")
    rows = grade_table.copy()
    rows["_impact"] = pd.to_numeric(rows.get("Runs", 0), errors="coerce").fillna(0) + pd.to_numeric(rows.get("Wickets", 0), errors="coerce").fillna(0) * 18
    rows = rows[rows["_impact"] > 0].sort_values("_impact", ascending=False)
    if rows.empty:
        return player_v2_empty_advanced_card("Favourite ground", "Coverage limited", "Ground-level records are not deployed for this player yet.")
    row = rows.iloc[0]
    return (
        '<article class="player-v2-card player-v2-advanced-card">'
        '<div class="player-v2-card-head"><div class="player-v2-kicker">Favourite Ground / Grade</div><span>Scorecard-safe proxy</span></div>'
        f'<h3>{html.escape(str(row.get("Grade", "Best split")))}</h3>'
        '<div class="player-v2-mini-grid">'
        f'<div><span>Runs</span><strong>{format_int(row.get("Runs"))}</strong></div>'
        f'<div><span>Wickets</span><strong>{format_int(row.get("Wickets"))}</strong></div>'
        f'<div><span>Bat avg</span><strong>{format_decimal(row.get("Bat Avg"))}</strong></div>'
        f'<div><span>Eco</span><strong>{format_decimal(row.get("Econ"))}</strong></div>'
        '</div>'
        '<p class="player-v2-insight">Ground-level favourite cards will use venue records once deployed; this safely shows the strongest grade split today.</p>'
        '</article>'
    )


def player_v2_favourite_opponent_card(context: dict[str, object]) -> str:
    if int(context.get("premiership_count") or 0) > 0:
        title = "Finals impact"
        headline = f"{format_int(context.get('premiership_count'))} premierships"
        copy = context.get("premiership_seasons") or "Verified finals evidence from premiership records."
    else:
        title = "Favourite opponent"
        headline = "Coverage limited"
        copy = "Opponent-normalised batting and bowling splits need match-level rows promoted to deploy-safe data."
    return (
        '<article class="player-v2-card player-v2-advanced-card">'
        f'<div class="player-v2-card-head"><div class="player-v2-kicker">{html.escape(title)}</div><span>Match context</span></div>'
        f'<h3>{html.escape(headline)}</h3>'
        f'<p>{html.escape(str(copy))}</p>'
        '</article>'
    )


def player_v2_empty_advanced_card(title: str, badge: str, copy: str) -> str:
    return (
        '<article class="player-v2-card player-v2-advanced-card player-v2-empty-card">'
        f'<div class="player-v2-card-head"><div class="player-v2-kicker">{html.escape(title)}</div><span>{html.escape(badge)}</span></div>'
        '<h3>Not enough deployed detail yet</h3>'
        f'<p>{html.escape(copy)}</p>'
        '</article>'
    )


def render_player_profile_v2_standout_performances(profile_view: dict[str, pd.DataFrame]) -> None:
    cards = player_highlight_cards(profile_view)[:6]
    if not cards:
        return
    st.markdown(
        player_v2_section_header(
            "Standout Performances 🔥",
            "Best innings, spells, season peaks and record-book entries.",
            "Scorecard-linked where available",
        ),
        unsafe_allow_html=True,
    )
    rendered = "".join(player_v2_performance_card(card) for card in cards)
    st.markdown(f'<div class="player-v2-grid player-v2-grid-3">{rendered}</div>', unsafe_allow_html=True)


def player_v2_performance_card(card: dict[str, str]) -> str:
    value = str(card.get("value", "—"))
    player = str(card.get("player", "—"))
    meta = str(card.get("meta", "") or "")
    if card.get("meta_html"):
        meta_html = meta
    elif card.get("link_type") == "season":
        meta_html = season_overview_link_html(player) if player else html.escape(meta)
    else:
        meta_html = html.escape(meta)
    scorecard = scorecard_link_html(card.get("match_id"), class_name="player-v2-subtle-link", page_slug=PLAYER_PROFILE_V2_QUERY_PAGE, section_name="player_profile_v2_performance") if card.get("match_id") else ""
    return (
        '<article class="player-v2-performance-card">'
        '<div class="player-v2-performance-head">'
        f'<div class="player-v2-kicker">{html.escape(str(card.get("title", "Performance")))}</div>'
        f'<div class="player-v2-performance-value">{html.escape(value)}</div>'
        '</div>'
        '<div class="player-v2-performance-body">'
        f'<h3>{html.escape(player)}</h3>'
        f'<p>{meta_html}</p>'
        f'{scorecard}'
        '</div>'
        '</article>'
    )


def render_player_profile_v2_partnerships(profile_view: dict[str, pd.DataFrame]) -> None:
    st.markdown(
        player_v2_section_header(
            "Partnerships & Chemistry",
            "Pairing cards are reserved for reliable innings or ball-by-ball partner data.",
            "Coverage aware",
        ),
        unsafe_allow_html=True,
    )
    career = profile_view["career"].iloc[0]
    cards = [
        player_v2_pair_card("Batting partnerships", "Deploy-safe summary needed", "Best partner, average stand and best stand will appear once partnership rows are promoted."),
        player_v2_pair_card("Bowling partnerships", "Scorecard pairing needed", "Useful for captaincy: combined wickets, economy and matches bowled together."),
    ]
    if numeric_value(career, "Wickets") >= 25:
        cards.append(player_v2_pair_card("Verified bowling tandems", "Ball-by-ball only", "Alternating-over tandem reads should only use verified delivery data."))
    st.markdown(f'<div class="player-v2-grid player-v2-grid-3">{"".join(cards)}</div>', unsafe_allow_html=True)


def player_v2_pair_card(title: str, headline: str, copy: str) -> str:
    initials = "".join(part[0] for part in title.split()[:2]).upper()
    return (
        '<article class="player-v2-card player-v2-pair-card">'
        f'<div class="player-v2-pair-avatar">{html.escape(initials)}</div>'
        '<div>'
        f'<div class="player-v2-kicker">{html.escape(title)}</div>'
        f'<h3>{html.escape(headline)}</h3>'
        f'<p>{html.escape(copy)}</p>'
        '</div>'
        '</article>'
    )


def render_player_profile_v2_milestone_watch(career: pd.Series) -> None:
    milestones = player_v2_milestone_rows(career)
    if not milestones:
        return
    st.markdown(
        player_v2_section_header(
            "Milestone Watch 🎯",
            "Major 100-match, 1000-run, 100-wicket and 100-catch targets.",
            "Club milestones",
        ),
        unsafe_allow_html=True,
    )
    rows = "".join(player_v2_progress_card(row) for row in milestones)
    st.markdown(f'<div class="player-v2-progress-row">{rows}</div>', unsafe_allow_html=True)


def player_v2_milestone_rows(career: pd.Series) -> list[dict[str, object]]:
    specs = [
        ("Matches", "Matches", 100, "matches"),
        ("Runs", "Runs", 1000, "runs"),
        ("Wickets", "Wickets", 100, "wickets"),
        ("Catches", "Catches", 100, "catches"),
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


def player_v2_progress_card(row: dict[str, object]) -> str:
    return (
        '<article class="player-v2-progress-card">'
        f'<strong>{html.escape(str(row["category"]))}</strong>'
        f'<span class="player-v2-away">{int(row["remaining"]):,} {html.escape(str(row["unit"]))} away</span>'
        f'<div class="player-v2-progress-value">{int(row["current"]):,} / {int(row["target"]):,} {html.escape(str(row["unit"]))}</div>'
        f'<div class="player-v2-progress-track"><span style="width:{float(row["progress"]):.1f}%"></span></div>'
        '</article>'
    )


def render_player_profile_v2_timeline(profile_view: dict[str, pd.DataFrame], context: dict[str, object]) -> None:
    season_table = profile_view.get("season_table", pd.DataFrame())
    if season_table.empty:
        return
    st.markdown(
        player_v2_section_header(
            "Season Trends + Story Timeline",
            "A quick read of career shape before the detailed tables.",
            "Season records",
        ),
        unsafe_allow_html=True,
    )
    ordered = season_table.sort_values("Season", key=lambda series: series.map(profile_season_sort_key))
    latest = ordered.tail(5)
    strip = "".join(
        '<div class="player-v2-season-strip-card">'
        f'<span>{season_overview_link_html(row.get("Season"))}</span>'
        f'<strong>{format_int(row.get("Runs"))} runs</strong>'
        f'<em>{format_int(row.get("Wickets"))} wickets</em>'
        '</div>'
        for _, row in latest.iterrows()
    )
    timeline_steps = player_v2_timeline_steps(ordered, context)
    timeline = "".join(
        '<div class="player-v2-timeline-step">'
        '<span class="player-v2-timeline-dot"></span>'
        f'<small>{html.escape(label)}</small>'
        f'<strong>{value}</strong>'
        '</div>'
        for label, value in timeline_steps
    )
    st.markdown(f'<div class="player-v2-season-strip">{strip}</div><div class="player-v2-timeline">{timeline}</div>', unsafe_allow_html=True)


def player_v2_timeline_steps(ordered: pd.DataFrame, context: dict[str, object]) -> list[tuple[str, str]]:
    debut = str(ordered.iloc[0].get("Season", "—"))
    latest = str(ordered.iloc[-1].get("Season", "—"))
    runs = ordered.copy()
    runs["_runs"] = pd.to_numeric(runs.get("Runs", 0), errors="coerce").fillna(0)
    wickets = ordered.copy()
    wickets["_wickets"] = pd.to_numeric(wickets.get("Wickets", 0), errors="coerce").fillna(0)
    best_runs = runs.sort_values("_runs", ascending=False).iloc[0]
    best_wickets = wickets.sort_values("_wickets", ascending=False).iloc[0]
    prem = str(context.get("premiership_seasons") or "").split(",")[0].strip()
    return [
        ("Debut season", season_overview_link_html(debut)),
        ("Best run season", f'{season_overview_link_html(best_runs.get("Season"))} · {format_int(best_runs.get("Runs"))} runs'),
        ("Best wicket season", f'{season_overview_link_html(best_wickets.get("Season"))} · {format_int(best_wickets.get("Wickets"))} wickets'),
        ("Premiership marker", season_overview_link_html(prem) if prem else "—"),
        ("Latest season", season_overview_link_html(latest)),
    ]


def render_player_profile_v2_coverage_card(profile_view: dict[str, pd.DataFrame], context: dict[str, object]) -> None:
    career = profile_view["career"].iloc[0]
    bbb_balls = pd.to_numeric(context.get("bbb_balls"), errors="coerce")
    bbb_text = f"{int(bbb_balls):,} verified batting balls" if pd.notna(bbb_balls) and bbb_balls > 0 else "No deploy-safe ball-by-ball batting sample for this player"
    rows = [
        ("Scorecard-safe", f"{format_int(career.get('Seasons Count'))} seasons, {format_int(career.get('Matches'))} matches, career totals and grade/season splits."),
        ("Verified ball-by-ball", f"{bbb_text}. Rates and phase-style metrics stay blank unless verified."),
        ("Coach notes", "Advanced opponent, ground, position, dismissal and partnership cards show coverage notes rather than fake values."),
    ]
    item_html = "".join(
        f'<li><strong>{html.escape(title)}</strong><span>{html.escape(copy)}</span></li>'
        for title, copy in rows
    )
    st.markdown(
        f"""
        <section class="player-v2-coverage-card">
            <div>
                <div class="player-v2-kicker">Data Coverage / Trust</div>
                <h3>Designed to protect stat trust</h3>
                <p>Ball-by-ball-only metrics never mix scorecard totals with delivery denominators. Missing coverage becomes a calm empty state.</p>
            </div>
            <ul>{item_html}</ul>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_player_profile_v2_breakdown(profile_view: dict[str, pd.DataFrame]) -> None:
    st.markdown(
        player_v2_section_header(
            "Performance Breakdown",
            "Lower audit layer for season and grade splits. Tables remain compact and sortable.",
            "Audit layer",
        ),
        unsafe_allow_html=True,
    )
    season_tab, grade_tab = st.tabs(["Season", "Grade"])
    with season_tab:
        render_player_season_table(profile_view["season_table"])
    with grade_tab:
        render_player_grade_table(profile_view["grade_table"])


def player_v2_section_header(title: str, subtitle: str = "", badge: str = "") -> str:
    badge_html = f'<span class="player-v2-trust-chip">{html.escape(badge)}</span>' if badge else ""
    subtitle_html = f'<p>{html.escape(subtitle)}</p>' if subtitle else ""
    return (
        '<section class="player-v2-section">'
        '<div class="player-v2-section-head">'
        '<div>'
        f'<h2>{html.escape(title)}</h2>'
        f'{subtitle_html}'
        '</div>'
        f'{badge_html}'
        '</div>'
        '</section>'
    )


def player_v2_percent(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    return "—" if pd.isna(number) else f"{float(number):.1f}%"


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
    detail_sources = load_player_profile_detail_sources(player_profile_detail_source_signature())
    season_table = build_player_season_table(batting, bowling, fielding)
    season_table = enrich_player_profile_season_table(season_table, profile, detail_sources)
    grade_table = build_player_grade_table(batting, bowling, fielding)
    grade_table = enrich_player_profile_grade_table(grade_table, profile, detail_sources)
    career = build_player_career_totals(season_table, batting, bowling, fielding, profile)
    career = enrich_player_profile_career(career, profile, detail_sources)
    raw_profiles = build_player_raw_profile_table(batting, bowling, fielding)
    performance_breakdown = player_profile_source_rows(detail_sources.get("performance_breakdown", pd.DataFrame()), profile)
    batting_position = player_profile_source_rows(detail_sources.get("batting_position", pd.DataFrame()), profile)
    bowling_phase = player_profile_source_rows(detail_sources.get("bowling_phase", pd.DataFrame()), profile)
    dismissal_fingerprint = player_profile_source_rows(detail_sources.get("dismissal_fingerprint", pd.DataFrame()), profile)
    club_dismissal_fingerprint = player_profile_club_rows(detail_sources.get("dismissal_fingerprint", pd.DataFrame()))
    return {
        "batting": batting,
        "bowling": bowling,
        "fielding": fielding,
        "season_table": season_table,
        "grade_table": grade_table,
        "career": career,
        "raw_profiles": raw_profiles,
        "performance_breakdown": performance_breakdown,
        "batting_position": batting_position,
        "bowling_phase": bowling_phase,
        "dismissal_fingerprint": dismissal_fingerprint,
        "club_dismissal_fingerprint": club_dismissal_fingerprint,
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
            "Wides": sum_column(bowl, "bowlingWides"),
            "No Balls": sum_column(bowl, "bowlingNoBalls"),
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
            "Wides": sum_column(bowl, "bowlingWides"),
            "No Balls": sum_column(bowl, "bowlingNoBalls"),
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
        "Wides": sum_numeric_series(season_table["Wides"]) if "Wides" in season_table else 0,
        "No Balls": sum_numeric_series(season_table["No Balls"]) if "No Balls" in season_table else 0,
        "Catches": sum_numeric_series(season_table["Catches"]),
        "Stumpings": sum_numeric_series(season_table["Stumpings"]),
        "Run Outs": sum_numeric_series(season_table["Run Outs"]),
        "Dismissals": sum_numeric_series(season_table["Dismissals"]),
        "50s": sum_numeric_series(season_table["50s"]),
        "100s": sum_numeric_series(season_table["100s"]),
        "0s": sum_numeric_series(season_table["0s"]) if "0s" in season_table else 0,
        "4s": sum_numeric_series(season_table["4s"]) if "4s" in season_table else 0,
        "6s": sum_numeric_series(season_table["6s"]) if "6s" in season_table else 0,
        "30s": sum_numeric_series(season_table["30s"]) if "30s" in season_table else 0,
        "Maidens": sum_numeric_series(season_table["Maidens"]) if "Maidens" in season_table else 0,
        "3WI": sum_numeric_series(season_table["3WI"]) if "3WI" in season_table else 0,
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


def player_profile_detail_source_signature() -> tuple[tuple[str, float], ...]:
    paths = [
        HALL_OF_FAME_BBB_BATTING_RATES_PATH,
        SEASON_OVERVIEW_BBB_BATTING_RATES_PATH,
        SEASON_OVERVIEW_SCORECARD_BATTING_MILESTONES_PATH,
        SEASON_OVERVIEW_SCORECARD_BOWLING_MILESTONES_PATH,
        PLAYER_PROFILE_PERFORMANCE_BREAKDOWN_PATH,
        PLAYER_PROFILE_BATTING_POSITION_PATH,
        PLAYER_PROFILE_BOWLING_PHASE_PATH,
        PLAYER_PROFILE_DISMISSAL_FINGERPRINT_PATH,
        PLAYER_PROFILE_RECENT_FORM_BATTING_PATH,
        PLAYER_PROFILE_RECENT_FORM_BOWLING_PATH,
    ]
    return tuple((str(path), path.stat().st_mtime) for path in paths if path.exists())


@st.cache_data(show_spinner=False)
def load_player_profile_detail_sources(_signature: tuple[tuple[str, float], ...]) -> dict[str, pd.DataFrame]:
    return {
        "career_bbb_batting": read_match_centre_csv(HALL_OF_FAME_BBB_BATTING_RATES_PATH),
        "scope_bbb_batting": read_match_centre_csv(SEASON_OVERVIEW_BBB_BATTING_RATES_PATH),
        "scorecard_batting": read_match_centre_csv(SEASON_OVERVIEW_SCORECARD_BATTING_MILESTONES_PATH),
        "scorecard_bowling": read_match_centre_csv(SEASON_OVERVIEW_SCORECARD_BOWLING_MILESTONES_PATH),
        "performance_breakdown": read_match_centre_csv(PLAYER_PROFILE_PERFORMANCE_BREAKDOWN_PATH),
        "batting_position": read_match_centre_csv(PLAYER_PROFILE_BATTING_POSITION_PATH),
        "bowling_phase": read_match_centre_csv(PLAYER_PROFILE_BOWLING_PHASE_PATH),
        "dismissal_fingerprint": read_match_centre_csv(PLAYER_PROFILE_DISMISSAL_FINGERPRINT_PATH),
        "recent_form_batting": read_match_centre_csv(PLAYER_PROFILE_RECENT_FORM_BATTING_PATH),
        "recent_form_bowling": read_match_centre_csv(PLAYER_PROFILE_RECENT_FORM_BOWLING_PATH),
    }


def player_profile_identity_keys(profile: dict[str, object]) -> tuple[str, str]:
    player_info = profile.get("player_info", {}) if isinstance(profile, dict) else {}
    player_id = str(player_info.get("canonical_player_id", "") or "").strip()
    player_name = str(player_info.get("canonical_player_name", "") or "").strip()
    return player_id, player_name_match_key(player_name)


def player_profile_source_rows(frame: pd.DataFrame, profile: dict[str, object]) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    player_id, name_key = player_profile_identity_keys(profile)
    output = frame.copy()
    id_mask = pd.Series(False, index=output.index)
    if player_id:
        for column in ["canonical_player_id", "player_key", "player_id"]:
            if column in output:
                id_mask = id_mask | (output[column].astype(str).str.strip() == player_id)
    if id_mask.any():
        return output[id_mask].copy()
    name_mask = pd.Series(False, index=output.index)
    if name_key:
        for column in ["canonical_player_name", "display_player_name", "player_name", "raw_player_name"]:
            if column in output:
                name_mask = name_mask | (output[column].map(player_name_match_key) == name_key)
    return output[name_mask].copy() if name_mask.any() else output.head(0).copy()


def player_profile_club_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    output = frame.copy()
    if "scope" in output:
        return output[output["scope"].astype(str).str.casefold() == "club"].copy()
    if "canonical_player_id" in output:
        return output[output["canonical_player_id"].astype(str).str.strip() == "__club__"].copy()
    return output.head(0).copy()


def profile_source_grade_label(row: pd.Series) -> str:
    grade = clean_profile_grade_label(row.get("grade_name", ""))
    if grade and grade != "—":
        return grade
    team = clean_profile_team_label(row.get("team_name", ""))
    return team or "Unknown grade"


def player_profile_bbb_aggregate(rows: pd.DataFrame) -> dict[str, float | None]:
    if rows.empty:
        return {"bbb_runs": 0.0, "bbb_balls": 0.0, "bbb_innings": 0.0, "bbb_matches": 0.0, "bat_sr": None}
    for column in ["bbb_runs", "bbb_balls_faced", "bbb_batting_innings", "bbb_matches"]:
        if column not in rows:
            rows[column] = 0
        rows[column] = pd.to_numeric(rows[column], errors="coerce").fillna(0)
    runs = float(rows["bbb_runs"].sum())
    balls = float(rows["bbb_balls_faced"].sum())
    return {
        "bbb_runs": runs,
        "bbb_balls": balls,
        "bbb_innings": float(rows["bbb_batting_innings"].sum()),
        "bbb_matches": float(rows["bbb_matches"].sum()),
        "bat_sr": divide_or_none(runs * 100, balls),
    }


def player_profile_bbb_rates_by_scope(rows: pd.DataFrame, scope_column: str) -> pd.DataFrame:
    if rows.empty or scope_column not in rows:
        return pd.DataFrame(columns=[scope_column, "BBB Runs", "BBB Balls", "BBB Innings", "BBB Matches", "Bat SR"])
    output = rows.copy()
    for column in ["bbb_runs", "bbb_balls_faced", "bbb_batting_innings", "bbb_matches"]:
        if column not in output:
            output[column] = 0
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)
    grouped = output.groupby(scope_column, dropna=False, as_index=False).agg(
        **{
            "BBB Runs": ("bbb_runs", "sum"),
            "BBB Balls": ("bbb_balls_faced", "sum"),
            "BBB Innings": ("bbb_batting_innings", "sum"),
            "BBB Matches": ("bbb_matches", "sum"),
        }
    )
    grouped["Bat SR"] = grouped.apply(lambda row: divide_or_none(float(row["BBB Runs"]) * 100, float(row["BBB Balls"])), axis=1)
    return grouped


def player_profile_scorecard_batting_counts_by_scope(rows: pd.DataFrame, scope_column: str) -> pd.DataFrame:
    if rows.empty or scope_column not in rows:
        return pd.DataFrame(columns=[scope_column, "30s"])
    output = rows.copy()
    if "thirties" not in output:
        output["thirties"] = 0
    output["thirties"] = pd.to_numeric(output["thirties"], errors="coerce").fillna(0)
    grouped = output.groupby(scope_column, dropna=False, as_index=False)["thirties"].sum()
    return grouped.rename(columns={"thirties": "30s"})


def player_profile_scorecard_bowling_counts_by_scope(rows: pd.DataFrame, scope_column: str) -> pd.DataFrame:
    if rows.empty or scope_column not in rows:
        return pd.DataFrame(columns=[scope_column, "3WI", "5WI"])
    output = rows.copy()
    for column in ["three_wicket_innings", "five_wicket_innings"]:
        if column not in output:
            output[column] = 0
        output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)
    grouped = output.groupby(scope_column, dropna=False, as_index=False).agg(
        **{
            "3WI": ("three_wicket_innings", "sum"),
            "5WI": ("five_wicket_innings", "sum"),
        }
    )
    return grouped


def enrich_player_profile_season_table(
    season_table: pd.DataFrame,
    profile: dict[str, object],
    sources: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    if season_table.empty:
        return season_table
    output = season_table.copy()
    player_bbb = player_profile_source_rows(sources.get("scope_bbb_batting", pd.DataFrame()), profile)
    bbb_by_season = player_profile_bbb_rates_by_scope(player_bbb, "season")
    output = output.drop(columns=["Bat SR"], errors="ignore")
    if not bbb_by_season.empty:
        output = output.merge(bbb_by_season, left_on="Season", right_on="season", how="left").drop(columns=["season"], errors="ignore")
    else:
        output[["BBB Runs", "BBB Balls", "BBB Innings", "BBB Matches"]] = 0.0
        output["Bat SR"] = pd.NA

    batting_counts = player_profile_source_rows(sources.get("scorecard_batting", pd.DataFrame()), profile)
    thirties = player_profile_scorecard_batting_counts_by_scope(batting_counts, "season")
    if not thirties.empty:
        output = output.merge(thirties, left_on="Season", right_on="season", how="left", suffixes=("", "_scorecard")).drop(columns=["season"], errors="ignore")
        output["30s"] = pd.to_numeric(output.get("30s"), errors="coerce").fillna(0)
    else:
        output["30s"] = 0

    bowling_counts = player_profile_source_rows(sources.get("scorecard_bowling", pd.DataFrame()), profile)
    bowling_milestones = player_profile_scorecard_bowling_counts_by_scope(bowling_counts, "season")
    if not bowling_milestones.empty:
        output = output.merge(bowling_milestones, left_on="Season", right_on="season", how="left", suffixes=("", "_scorecard")).drop(columns=["season"], errors="ignore")
        output["3WI"] = pd.to_numeric(output.get("3WI"), errors="coerce").fillna(0)
        if "5WI_scorecard" in output:
            scorecard_five = pd.to_numeric(output["5WI_scorecard"], errors="coerce")
            existing_five = pd.to_numeric(output.get("5WI"), errors="coerce")
            output["5WI"] = existing_five.where(scorecard_five.isna(), scorecard_five)
            output = output.drop(columns=["5WI_scorecard"])
    else:
        output["3WI"] = 0

    output["Bat SR"] = pd.to_numeric(output.get("Bat SR"), errors="coerce")
    for column in ["30s", "3WI", "5WI", "BBB Runs", "BBB Balls", "BBB Innings", "BBB Matches"]:
        if column in output:
            output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)
    return output


def enrich_player_profile_grade_table(
    grade_table: pd.DataFrame,
    profile: dict[str, object],
    sources: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    if grade_table.empty:
        return grade_table
    output = grade_table.copy()
    player_bbb = player_profile_source_rows(sources.get("scope_bbb_batting", pd.DataFrame()), profile)
    if not player_bbb.empty:
        player_bbb = player_bbb.copy()
        player_bbb["Grade"] = player_bbb.apply(profile_source_grade_label, axis=1)
    bbb_by_grade = player_profile_bbb_rates_by_scope(player_bbb, "Grade")
    output = output.drop(columns=["Bat SR"], errors="ignore")
    if not bbb_by_grade.empty:
        output = output.merge(bbb_by_grade, on="Grade", how="left")
    else:
        output[["BBB Runs", "BBB Balls", "BBB Innings", "BBB Matches"]] = 0.0
        output["Bat SR"] = pd.NA

    batting_counts = player_profile_source_rows(sources.get("scorecard_batting", pd.DataFrame()), profile)
    if not batting_counts.empty:
        batting_counts = batting_counts.copy()
        batting_counts["Grade"] = batting_counts.apply(profile_source_grade_label, axis=1)
    thirties = player_profile_scorecard_batting_counts_by_scope(batting_counts, "Grade")
    if not thirties.empty:
        output = output.merge(thirties, on="Grade", how="left", suffixes=("", "_scorecard"))
        output["30s"] = pd.to_numeric(output.get("30s"), errors="coerce").fillna(0)
    else:
        output["30s"] = 0

    bowling_counts = player_profile_source_rows(sources.get("scorecard_bowling", pd.DataFrame()), profile)
    if not bowling_counts.empty:
        bowling_counts = bowling_counts.copy()
        bowling_counts["Grade"] = bowling_counts.apply(profile_source_grade_label, axis=1)
    bowling_milestones = player_profile_scorecard_bowling_counts_by_scope(bowling_counts, "Grade")
    if not bowling_milestones.empty:
        output = output.merge(bowling_milestones, on="Grade", how="left", suffixes=("", "_scorecard"))
        output["3WI"] = pd.to_numeric(output.get("3WI"), errors="coerce").fillna(0)
        if "5WI_scorecard" in output:
            scorecard_five = pd.to_numeric(output["5WI_scorecard"], errors="coerce")
            existing_five = pd.to_numeric(output.get("5WI"), errors="coerce")
            output["5WI"] = existing_five.where(scorecard_five.isna(), scorecard_five)
            output = output.drop(columns=["5WI_scorecard"])
    else:
        output["3WI"] = 0

    output["Bat SR"] = pd.to_numeric(output.get("Bat SR"), errors="coerce")
    for column in ["30s", "3WI", "5WI", "BBB Runs", "BBB Balls", "BBB Innings", "BBB Matches"]:
        if column in output:
            output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0)
    return output


def enrich_player_profile_career(
    career: pd.DataFrame,
    profile: dict[str, object],
    sources: dict[str, pd.DataFrame],
) -> pd.DataFrame:
    if career.empty:
        return career
    output = career.copy()
    bbb_rows = player_profile_source_rows(sources.get("career_bbb_batting", pd.DataFrame()), profile)
    bbb = player_profile_bbb_aggregate(bbb_rows)
    output.loc[output.index[0], "BBB Runs"] = bbb["bbb_runs"]
    output.loc[output.index[0], "BBB Balls"] = bbb["bbb_balls"]
    output.loc[output.index[0], "BBB Innings"] = bbb["bbb_innings"]
    output.loc[output.index[0], "BBB Matches"] = bbb["bbb_matches"]
    output.loc[output.index[0], "Bat SR"] = bbb["bat_sr"] if bbb["bat_sr"] is not None else pd.NA
    return output


def render_player_header_card(profile_view: dict[str, pd.DataFrame]) -> None:
    career = profile_view["career"].iloc[0]
    badges = player_role_badges(career, profile_view)
    badge_html = "".join(
        f'<span class="{profile_badge_class(badge)}">{html.escape(badge)}</span>'
        for badge in badges
    )
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
            f'<div class="profile-badges">{badge_html}</div>'
            '</div>'
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
    leader_details = player_leader_details(profile_view)
    bbb_balls = numeric_value(career, "BBB Balls")
    bbb_runs = numeric_value(career, "BBB Runs")
    reliable_bat_sr = numeric_value(career, "Bat SR")
    season_table = profile_view.get("season_table", pd.DataFrame())
    standout_count = player_unique_standout_season_count(leader_details)
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
    add_candidate("Quick Scorer", "style", 15, matches_20 and reliable_bat_sr >= 90 and bbb_balls >= 125 and bbb_runs >= 125)
    add_candidate("Boundary Maker", "style", 15, matches_20 and matches and (fours + sixes) / matches > 2.5 and not big_hitter and not gap_finder)
    add_candidate("Workhorse", "bowling", 16, overs >= 250 and matches >= 30)
    add_candidate("Safe Hands", "fielding", 17, stumpings <= 0 and matches_20 and matches and dismissals / matches > 0.4)
    add_candidate("Keeper Impact", "fielding", 18, stumpings > 0)
    for premiership_badge in player_premiership_profile_badges(career):
        add_candidate(premiership_badge, "achievement", 18, True)
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
    return "Season Standout" if count <= 1 else f"Season Standout x{count}"


def base_badge_label(label: str) -> str:
    return re.sub(r"\s+x\s*\d+$", "", str(label)).strip()


def profile_badge_class(label: str) -> str:
    base = base_badge_label(label)
    if base in {"Premiership Winner", "Premiership Winning Captain"}:
        return "profile-badge profile-badge-gold"
    return "profile-badge"


def counted_profile_badge(label: str, count: int) -> str:
    return label if count <= 1 else f"{label} x{count}"


def player_unique_standout_season_count(details: dict[str, list[str]]) -> int:
    seasons: set[str] = set()
    for values in details.values():
        for detail in values:
            season = str(detail or "").partition(" · ")[0].strip()
            if season:
                seasons.add(season)
    return len(seasons)


def player_premiership_profile_badges(career: pd.Series) -> list[str]:
    player_name = str(career.get("Player", "") or "").strip()
    name_key = player_name_match_key(player_name)
    if not name_key:
        return []
    wins, players = load_premiership_records(premiership_records_signature())
    badges: list[str] = []
    winner_count = 0
    if not players.empty:
        output = players.copy()
        name_column = "display_player_name" if "display_player_name" in output else "canonical_player_name"
        if name_column in output:
            matched = output[output[name_column].map(player_name_match_key) == name_key]
            if not matched.empty:
                winner_value = pd.to_numeric(matched.iloc[0].get("premiership_count"), errors="coerce")
                winner_count = 0 if pd.isna(winner_value) else int(winner_value)
    captain_count = 0
    if not wins.empty and "captain_name" in wins:
        captain_rows = wins[wins["captain_name"].map(player_name_match_key) == name_key].copy()
        if not captain_rows.empty:
            captain_count = int(captain_rows["match_id"].astype(str).nunique()) if "match_id" in captain_rows else int(len(captain_rows))
    if captain_count > 0:
        badges.append(counted_profile_badge("Premiership Winning Captain", captain_count))
    if winner_count > 0:
        badges.append(counted_profile_badge("Premiership Winner", winner_count))
    return badges


def select_profile_badges(candidates: list[dict[str, object]]) -> list[str]:
    ordered = sorted(candidates, key=profile_badge_sort_key)
    selected: list[str] = []
    for candidate in ordered:
        label = str(candidate["label"])
        if label not in selected:
            selected.append(label)
    return selected


def profile_badge_sort_key(candidate: dict[str, object]) -> tuple[int, int]:
    base = base_badge_label(str(candidate.get("label", "")))
    if base == "Premiership Winning Captain":
        return (0, int(candidate["priority"]))
    if base == "Premiership Winner":
        return (1, int(candidate["priority"]))
    return (2, int(candidate["priority"]))


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
    st.markdown(
        f'<div class="profile-highlights-grid">{"".join(record_card_html(card) for card in cards)}</div>',
        unsafe_allow_html=True,
    )


def player_highlight_cards(profile_view: dict[str, pd.DataFrame]) -> list[dict[str, str]]:
    career = profile_view["career"].iloc[0]
    season_table = profile_view["season_table"]
    batting = profile_view["batting"]
    bowling = profile_view["bowling"]
    cards = []
    leader_counts = player_leader_counts(profile_view)
    if str(career.get("HS", "—")) != "—":
        row = best_high_score_row(batting)
        cards.append({"title": "Highest Score", "player": str(career["Player"]), "value": str(career["HS"]), "meta": profile_record_meta_html(row), "meta_html": True, "match_id": scorecard_match_id_for_profile_record(row, "batting")})
    if str(career.get("BBI", "—")) != "—":
        row = best_bowling_row(bowling)
        cards.append({"title": "Best Bowling Figures", "player": str(career["Player"]), "value": str(career["BBI"]), "meta": profile_record_meta_html(row), "meta_html": True, "match_id": scorecard_match_id_for_profile_record(row, "bowling")})
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
                cards.append({"title": title, "player": str(row["Season"]), "value": f"{int(row[metric]):,} {suffix}", "meta": str(row.get("Teams/Grades", "")), "link_type": "season"})
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
            details = leader_details.get(key, [])
            label = suffix if value == 1 else f"{suffix}s"
            cards.append(
                {
                    "title": title,
                    "player": leader_highlight_primary_context(details),
                    "value": f"{value:,} {label}",
                    "meta": leader_highlight_secondary_context(details, by_grade=("grade" in key)),
                    "link_type": "season",
                }
            )
    return cards[:10]


def player_leader_counts(profile_view: dict[str, pd.DataFrame]) -> dict[str, int]:
    return {key: len(values) for key, values in player_leader_details(profile_view).items()}


def scorecard_match_id_for_profile_record(row: pd.Series, mode: str) -> str:
    if row.empty:
        return ""
    lookup = load_scorecard_record_rows(scorecard_record_rows_signature()).get(mode, pd.DataFrame())
    if lookup.empty:
        return ""
    return scorecard_match_id_for_record(row, lookup, mode)


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


def compact_leader_detail_meta_html(details: list[str], limit: int = 3) -> str:
    if not details:
        return ""
    visible = details[:limit]
    remaining = len(details) - len(visible)
    rendered = []
    for detail in visible:
        season, separator, rest = str(detail).partition(" · ")
        linked = season_overview_link_html(season)
        rendered.append(f"{linked}{html.escape(separator + rest) if separator else ''}")
    if remaining > 0:
        rendered.append(html.escape(f"+{remaining} more"))
    return ", ".join(rendered)


def leader_highlight_primary_context(details: list[str]) -> str:
    if not details:
        return "Season not recorded"
    season = str(details[0]).partition(" · ")[0].strip()
    return season or "Season not recorded"


def leader_highlight_secondary_context(details: list[str], *, by_grade: bool) -> str:
    scope = "Whole club"
    if details:
        _season, separator, rest = str(details[0]).partition(" · ")
        if by_grade and separator and rest.strip():
            scope = rest.strip()
    remaining = max(0, len(details) - 1)
    return f"{scope} · +{remaining} more" if remaining else scope


def render_player_intelligence(profile_view: dict[str, pd.DataFrame]) -> None:
    career = profile_view["career"].iloc[0]
    is_batsman, is_bowler = player_profile_role_flags(career)
    if not (is_batsman or is_bowler) and profile_view.get("dismissal_fingerprint", pd.DataFrame()).empty:
        return

    render_section_heading("Player DNA 🧬")

    top_columns = st.columns(2)
    with top_columns[0]:
        if is_batsman:
            render_batting_position_intelligence(profile_view)
        else:
            render_profile_intelligence_empty(
                "Batting Position",
                "This module appears once the player has enough batting innings to identify a stable role.",
            )
    with top_columns[1]:
        render_dismissal_fingerprint(profile_view)
    if is_bowler:
        render_bowling_phase_intelligence(profile_view)


def player_profile_role_flags(career: pd.Series) -> tuple[bool, bool]:
    innings = numeric_value(career, "Innings")
    runs = numeric_value(career, "Runs")
    balls_bowled = numeric_value(career, "Balls Bowled")
    wickets = numeric_value(career, "Wickets")
    # These thresholds intentionally classify broad cricket roles, not talent.
    is_batsman = (innings >= 15 and runs >= 250) or runs >= 500
    is_bowler = (balls_bowled >= 300 and wickets >= 15) or wickets >= 50
    return is_batsman, is_bowler


def render_batting_position_intelligence(profile_view: dict[str, pd.DataFrame]) -> None:
    rows = profile_view.get("batting_position", pd.DataFrame()).copy()
    if rows.empty:
        render_profile_intelligence_empty("Batting Position", "Scorecard batting-order data is not available for this player yet.")
        return
    rows["position_order"] = pd.to_numeric(rows.get("position_order"), errors="coerce").fillna(99)
    rows["innings"] = pd.to_numeric(rows.get("innings"), errors="coerce").fillna(0)
    rows["runs"] = pd.to_numeric(rows.get("runs"), errors="coerce").fillna(0)
    rows["average"] = pd.to_numeric(rows.get("average"), errors="coerce")
    rows = rows.sort_values("position_order")
    best = profile_best_position_label(rows)
    best_note = (
        '<p class="profile-intelligence-note profile-position-footnote">Best fit requires 4+ innings in a position.</p>'
        if best
        else '<p class="profile-intelligence-note profile-position-footnote">Best fit needs 4+ innings in a position.</p>'
    )
    max_runs = max(1.0, float(rows["runs"].max()))
    row_html = []
    for _, row in rows.iterrows():
        label = str(row.get("position_group", "—"))
        runs = float(row.get("runs", 0) or 0)
        width = max(4.0, min(100.0, (runs / max_runs) * 100))
        best_badge = '<span class="profile-best-badge">Best fit</span>' if label == best else ""
        summary = (
            f'{format_int(row.get("innings"))} inn'
            f' · {format_int(row.get("runs"))} runs'
            f' · Avg {format_decimal(row.get("average"))}'
        )
        row_html.append(
            '<div class="position-row">'
            '<div class="position-row-top">'
            '<div class="position-row-label">'
            f'<strong>{html.escape(label)}</strong>{best_badge}'
            '</div>'
            f'<span class="position-row-summary">{html.escape(summary)}</span>'
            '</div>'
            '<div class="position-track">'
            f'<div style="width:{width:.1f}%"></div>'
            '</div>'
            '</div>'
        )
    st.markdown(
        (
            '<article class="profile-intelligence-card">'
            '<div class="profile-intelligence-card-head">'
            '<div class="profile-card-title">Batting Position</div>'
            '</div>'
            f'{"".join(row_html)}'
            f'{best_note}'
            '</article>'
        ),
        unsafe_allow_html=True,
    )


def profile_best_position_label(rows: pd.DataFrame) -> str:
    if rows.empty:
        return ""
    eligible = rows[pd.to_numeric(rows.get("innings"), errors="coerce").fillna(0) >= 4].copy()
    eligible = eligible[pd.to_numeric(eligible.get("average"), errors="coerce").notna()].copy()
    if eligible.empty:
        return ""
    eligible["_average_sort"] = pd.to_numeric(eligible.get("average"), errors="coerce")
    eligible["_position_sort"] = pd.to_numeric(eligible.get("position_order"), errors="coerce").fillna(99)
    eligible = eligible.sort_values(["_average_sort", "_position_sort"], ascending=[False, True])
    return str(eligible.iloc[0].get("position_group", ""))


def render_bowling_phase_intelligence(profile_view: dict[str, pd.DataFrame]) -> None:
    rows = profile_view.get("bowling_phase", pd.DataFrame()).copy()
    selected = selected_profile_phase_model()
    with st.container(key="profile_bowling_phase_card"):
        st.markdown(
            '<div class="profile-intelligence-card-head">'
            '<div class="profile-card-title">Bowling by Phase</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        if rows.empty:
            render_profile_empty_state(
                "Bowling phase data is not available for this player yet.",
                "Verified ball-by-ball coverage is needed before phase splits can be shown.",
            )
            return
        render_profile_phase_selector(profile_view, selected)
        rows = rows[rows.get("phase_model", pd.Series(dtype=str)).astype(str).str.casefold() == selected.casefold()].copy()
        if rows.empty:
            render_profile_empty_state(
                "Bowling phase data is not available for this format yet.",
                "Try another format, or check back when verified ball-by-ball coverage exists.",
            )
            return
        rows["phase_order"] = pd.to_numeric(rows.get("phase_order"), errors="coerce").fillna(99)
        for column in ["legal_balls", "wickets", "dot_balls", "boundary_balls"]:
            rows[column] = pd.to_numeric(rows.get(column), errors="coerce").fillna(0)
        for column in ["eco", "sr", "avg", "dot_ball_pct", "boundary_rate"]:
            rows[column] = pd.to_numeric(rows.get(column), errors="coerce")
        rows = rows[rows["legal_balls"] > 0].sort_values("phase_order")
        if rows.empty:
            render_profile_empty_state(
                "Bowling phase data is not available for this format yet.",
                "Verified legal deliveries are required for these bowling phase metrics.",
            )
            return
        best_phase = profile_best_phase_label(rows)
        phase_rows = []
        for _, row in rows.iterrows():
            label = str(row.get("phase", "—"))
            best_badge = '<span class="profile-best-badge">Best phase</span>' if label == best_phase else ""
            phase_rows.append(
                '<div class="phase-table-row">'
                f'<div class="phase-table-phase"><strong>{html.escape(label)}</strong>{best_badge}</div>'
                f'<span>{html.escape(str(row.get("overs", "—")))}</span>'
                f'<span>{format_int(row.get("wickets"))}</span>'
                f'<span>{format_phase_metric(row.get("avg"))}</span>'
                f'<span>{format_phase_metric(row.get("sr"))}</span>'
                f'<span>{format_phase_metric(row.get("eco"))}</span>'
                f'<span>{format_phase_metric(row.get("dot_ball_pct"), percent=True)}</span>'
                f'<span>{format_phase_metric(row.get("boundary_rate"), percent=True)}</span>'
                '</div>'
            )
        st.markdown(
            (
                '<div class="phase-table">'
                '<div class="phase-table-row phase-table-head">'
                '<span>Phase</span><span>O</span><span>W</span><span>Avg</span>'
                '<span>SR</span><span>Eco</span><span>Dot Ball %</span><span>Boundary %</span>'
                '</div>'
                f'{"".join(phase_rows)}'
                '</div>'
                '<p class="profile-phase-footnote">Phase metrics require ball-by-ball data.</p>'
            ),
            unsafe_allow_html=True,
        )


def profile_best_phase_label(rows: pd.DataFrame) -> str:
    if rows.empty:
        return ""
    output = rows.copy()
    output["_wickets_sort"] = pd.to_numeric(output.get("wickets"), errors="coerce").fillna(0)
    output["_eco_sort"] = pd.to_numeric(output.get("eco"), errors="coerce").fillna(999)
    output["_balls_sort"] = pd.to_numeric(output.get("legal_balls"), errors="coerce").fillna(0)
    output = output.sort_values(["_wickets_sort", "_eco_sort", "_balls_sort"], ascending=[False, True, False])
    return str(output.iloc[0].get("phase", ""))


def format_phase_metric(value: object, *, percent: bool = False) -> str:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number) or not math.isfinite(float(number)):
        return "N/A"
    suffix = "%" if percent else ""
    return f"{float(number):.1f}{suffix}" if percent else f"{float(number):.2f}"


def selected_profile_phase_model() -> str:
    options = {slug: label for slug, label in profile_phase_model_options()}
    key = "player_profile_phase_model"
    if key not in st.session_state:
        requested = query_param_value("profile_phase_model").casefold()
        st.session_state[key] = requested if requested in options else "one-day"
    selected = str(st.session_state.get(key, "one-day")).casefold()
    if selected not in options:
        selected = "one-day"
        st.session_state[key] = selected
    return options[selected]


def profile_phase_model_options() -> list[tuple[str, str]]:
    return [("t20", "T20"), ("one-day", "One Day"), ("two-day", "Two Day")]


def render_profile_phase_selector(profile_view: dict[str, pd.DataFrame], selected_label: str) -> None:
    del profile_view
    del selected_label
    render_profile_segmented_widget(
        "Bowling phase model",
        profile_phase_model_options(),
        key="player_profile_phase_model",
        compact=True,
    )


def render_dismissal_fingerprint(profile_view: dict[str, pd.DataFrame]) -> None:
    player_rows = profile_view.get("dismissal_fingerprint", pd.DataFrame()).copy()
    club_rows = profile_view.get("club_dismissal_fingerprint", pd.DataFrame()).copy()
    if player_rows.empty:
        render_profile_intelligence_empty("Dismissal Fingerprint", "Dismissal detail is not available for this player yet.")
        return
    player_rows = player_rows[player_rows.get("scope", pd.Series(dtype=str)).astype(str).str.casefold().eq("player")].copy()
    if player_rows.empty:
        render_profile_intelligence_empty("Dismissal Fingerprint", "Dismissal detail is not available for this player yet.")
        return
    buckets = ["Caught", "Bowled", "LBW", "Run out", "Stumped", "Other"]
    player_map = profile_dismissal_pct_map(player_rows)
    club_map = profile_dismissal_pct_map(club_rows)
    row_html = []
    for bucket in buckets:
        player_pct = player_map.get(bucket, 0.0)
        club_pct = club_map.get(bucket, 0.0)
        detail = profile_dismissal_detail_text(player_pct, club_pct)
        average_marker = f'<span class="peer-marker avg-marker" style="left:{max(0.0, min(100.0, club_pct)):.1f}%;"></span>'
        row_html.append(
            '<div class="fingerprint-row">'
            '<div class="fingerprint-top">'
            '<div class="fingerprint-label-block">'
            f'<strong>{html.escape(bucket)}</strong>'
            f'<span class="fingerprint-detail">{html.escape(detail)}</span>'
            '</div>'
            f'<span class="fingerprint-player-pct">{player_pct:.1f}%</span>'
            '</div>'
            f'{comparison_bar_html(average_marker, fill_percent=max(2.0, min(100.0, player_pct)))}'
            '</div>'
        )
    player_name = str(profile_view["career"].iloc[0].get("Player", "This player"))
    st.markdown(
        (
            '<article class="profile-intelligence-card profile-fingerprint-card">'
            '<div class="profile-intelligence-card-head">'
            '<div class="profile-card-title">Dismissal Fingerprint</div>'
            '</div>'
            '<div class="fingerprint-legend"><span><i class="player"></i> Player</span><span><i class="club"></i> Club average</span></div>'
            f'{"".join(row_html)}'
            f'<p class="profile-intelligence-note">{html.escape(profile_dismissal_insight(player_name, player_map, club_map))}</p>'
            '</article>'
        ),
        unsafe_allow_html=True,
    )


def profile_dismissal_pct_map(rows: pd.DataFrame) -> dict[str, float]:
    if rows.empty:
        return {}
    output = rows.copy()
    output["pct"] = pd.to_numeric(output.get("pct"), errors="coerce").fillna(0)
    return {
        str(row.get("dismissal_bucket", "")).strip(): float(row.get("pct", 0) or 0)
        for _, row in output.iterrows()
    }


def profile_dismissal_detail_text(player_pct: float, club_pct: float) -> str:
    diff = player_pct - club_pct
    return f"Club avg {club_pct:.1f}% | {diff:+.1f} pts"


def profile_dismissal_insight(player_name: str, player_map: dict[str, float], club_map: dict[str, float]) -> str:
    first_name = str(player_name or "This player").split()[0]
    diffs = []
    labels = {"Caught": "caught", "Bowled": "bowled", "LBW": "LBW", "Run out": "run out", "Stumped": "stumped", "Other": "other ways"}
    for bucket, player_pct in player_map.items():
        diff = player_pct - club_map.get(bucket, 0.0)
        if diff >= 3:
            diffs.append((diff, labels.get(bucket, bucket.lower())))
    if not diffs:
        return f"{first_name}'s dismissal mix is broadly in line with the club average."
    selected = [label for _diff, label in sorted(diffs, reverse=True)[:2]]
    if len(selected) == 1:
        return f"{first_name} is dismissed {selected[0]} more often than the club average."
    return f"{first_name} is dismissed {selected[0]} and {selected[1]} more often than the club average."


def render_profile_intelligence_empty(title: str, copy: str) -> None:
    st.markdown(
        (
            '<article class="profile-intelligence-card profile-empty-card">'
            '<div class="profile-intelligence-card-head">'
            '<span>Coverage limited</span>'
            f'<div class="profile-card-title">{html.escape(title)}</div>'
            '</div>'
            f'<p>{html.escape(copy)}</p>'
            '</article>'
        ),
        unsafe_allow_html=True,
    )


def render_profile_empty_state(title: str, copy: str = "") -> None:
    body = f"<span>{html.escape(copy)}</span>" if copy else ""
    st.markdown(
        (
            '<div class="profile-breakdown-empty">'
            f'<strong>{html.escape(title)}</strong>'
            f'{body}'
            '</div>'
        ),
        unsafe_allow_html=True,
    )


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
    peer_scope = player_peer_grade_scope(profile_view)
    player_id = str(career.get("canonical_player_id", "")).strip()
    if not player_id or not seasons:
        return

    comparison = get_player_peer_comparison(player_id, seasons, peer_scope, metadata_mtime(), player_aliases_mtime())
    if not comparison.get("batting") and not comparison.get("bowling"):
        return

    render_section_heading("Player vs Peers 📊")
    render_section_subtext("Compared against players from the same seasons and grades.")
    st.markdown(
        """
        <div class="peer-explainer">
            <div class="peer-legend">
                <span><i class="legend-dot player-dot"></i> Player</span>
                <span><i class="legend-marker avg-dot"></i> Peer avg.</span>
            </div>
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
    peer_scope: tuple[str, ...],
    local_version: float,
    identity_version: float,
) -> dict[str, list[dict[str, object]]]:
    _ = (local_version, identity_version)
    aliases = load_player_aliases()
    batting = apply_team_grade_display_columns(apply_player_identity_mapping(read_processed_table("all_seasons_batting"), aliases))
    bowling = apply_team_grade_display_columns(apply_player_identity_mapping(read_processed_table("all_seasons_bowling"), aliases))
    batting_scope = filter_peer_scope(batting, seasons, peer_scope)
    bowling_scope = filter_peer_scope(bowling, seasons, peer_scope)
    batting_rows = aggregate_peer_batting(batting_scope, seasons)
    batting_rows = add_bbb_peer_batting_rates(batting_rows, seasons, peer_scope)
    bowling_rows = aggregate_peer_bowling(bowling_scope, seasons)
    player_batting_row = batting_rows[batting_rows["canonical_player_id"].astype(str) == player_id] if not batting_rows.empty else pd.DataFrame()
    player_innings = float(player_batting_row["innings"].iloc[0]) if not player_batting_row.empty and "innings" in player_batting_row else 0.0
    player_ducks = float(player_batting_row["ducks"].iloc[0]) if not player_batting_row.empty and "ducks" in player_batting_row else 0.0
    batting_status_overrides: dict[str, str] = {}
    if player_ducks == 0:
        batting_status_overrides["innings_per_duck"] = "Better than avg" if player_innings >= 10 else ""
    batting_average_overrides = {
        "bat_avg": divide_or_none(sum_numeric(batting_rows, "runs"), sum_numeric(batting_rows, "outs")),
        "bat_sr": divide_or_none(
            sum_numeric(batting_rows, "bbb_runs") * 100,
            sum_numeric(batting_rows, "bbb_balls"),
        ),
        "balls_per_dismissal": divide_or_none(sum_numeric(batting_rows, "reliable_balls"), sum_numeric(batting_rows, "reliable_outs")),
        "minutes_per_dismissal": divide_or_none(sum_numeric(batting_rows, "reliable_minutes"), sum_numeric(batting_rows, "reliable_outs")),
        "boundary_rate": divide_or_none(sum_numeric(batting_rows, "boundaries"), sum_numeric(batting_rows, "innings")),
        "innings_per_duck": divide_or_none(sum_numeric(batting_rows, "innings"), sum_numeric(batting_rows, "ducks")),
    }
    bowling_average_overrides = {
        "bowl_avg": divide_or_none(sum_numeric(bowling_rows, "runs_against"), sum_numeric(bowling_rows, "wickets")),
        "bowl_sr": divide_or_none(sum_numeric(bowling_rows, "balls"), sum_numeric(bowling_rows, "wickets")),
        "economy": divide_or_none(sum_numeric(bowling_rows, "runs_against") * 6, sum_numeric(bowling_rows, "balls")),
        "overs_per_maiden": divide_or_none(sum_numeric(bowling_rows, "overs"), sum_numeric(bowling_rows, "maidens")),
        "balls_per_extra": divide_or_none(sum_numeric(bowling_rows, "balls"), sum_numeric(bowling_rows, "extras")),
    }
    batting_metrics = build_peer_metric_rows(
        batting_rows,
        player_id,
        [
            ("Batting Avg", "bat_avg", False, "decimal"),
            ("Strike Rate", "bat_sr", False, "percent"),
            ("Balls per Dismissal", "balls_per_dismissal", False, "decimal"),
            ("Minutes per Dismissal", "minutes_per_dismissal", False, "decimal"),
            ("Boundary Rate", "boundary_rate", False, "decimal"),
            ("Innings per Duck", "innings_per_duck", False, "decimal"),
        ],
        average_overrides=batting_average_overrides,
        status_overrides=batting_status_overrides,
    )
    bowling_metrics = build_peer_metric_rows(
        bowling_rows,
        player_id,
        [
            ("Bowling Avg", "bowl_avg", True, "decimal"),
            ("Bowling SR", "bowl_sr", True, "decimal"),
            ("Economy Rate", "economy", True, "decimal"),
            ("Overs per Maiden", "overs_per_maiden", True, "decimal"),
            ("Balls per Extra", "balls_per_extra", False, "decimal"),
        ],
        average_overrides=bowling_average_overrides,
    )
    export_player_vs_peers_debug(player_id, peer_scope, batting_metrics, bowling_metrics)
    return {
        "batting": batting_metrics,
        "bowling": bowling_metrics,
    }


def player_peer_grade_scope(profile_view: dict[str, pd.DataFrame]) -> tuple[str, ...]:
    scope = set()
    for key in ["batting", "bowling", "fielding"]:
        frame = profile_view.get(key, pd.DataFrame())
        if frame.empty or "season" not in frame:
            continue
        frame = apply_team_grade_display_columns(frame)
        for _, row in frame.iterrows():
            season = str(row.get("season", "")).strip()
            grade = peer_scope_grade_label(row)
            if season and grade:
                scope.add(peer_scope_key(season, grade))
    return tuple(sorted(scope))


def peer_scope_grade_label(row: pd.Series) -> str:
    grade = str(row.get("canonical_grade_label") or "").strip()
    if grade:
        return grade
    display = str(row.get("team_grade_display") or "").strip()
    if display and display != "—":
        return display
    team = str(row.get("canonical_team_label") or row.get("clean_team_name") or "").strip()
    return team or "Unknown grade"


def peer_scope_key(season: object, grade: object) -> str:
    return f"{str(season).strip()}||{str(grade).strip()}"


def filter_peer_scope(frame: pd.DataFrame, seasons: tuple[str, ...], peer_scope: tuple[str, ...]) -> pd.DataFrame:
    if frame.empty or "season" not in frame:
        return pd.DataFrame()
    scoped = frame[frame["season"].astype(str).isin(seasons)].copy()
    if scoped.empty or not peer_scope:
        return scoped
    scoped = apply_team_grade_display_columns(scoped)
    scoped["_peer_scope_key"] = scoped.apply(lambda row: peer_scope_key(row.get("season", ""), peer_scope_grade_label(row)), axis=1)
    matched = scoped[scoped["_peer_scope_key"].isin(peer_scope)].drop(columns=["_peer_scope_key"], errors="ignore")
    # Some older rows can have incomplete grade metadata. In that case we fall back to same-season peers
    # instead of hiding the section entirely.
    return matched if not matched.empty else scoped.drop(columns=["_peer_scope_key"], errors="ignore")


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
        reliable_balls = balls
        reliable_outs = outs
        reliable_minutes = sum_column(group, "battingMinutes")
        boundaries = sum_column(group, "battingFours") + sum_column(group, "battingSixes")
        ducks = sum_column(group, "batting0s")
        rows.append(
            {
                "canonical_player_id": player_id,
                "runs": runs,
                "balls_faced": balls,
                "innings": innings,
                "outs": outs,
                "bbb_runs": 0.0,
                "bbb_balls": 0.0,
                "reliable_balls": reliable_balls,
                "reliable_outs": reliable_outs,
                "reliable_minutes": reliable_minutes,
                "bat_avg": divide_or_none(runs, outs),
                "bat_sr": None,
                "balls_per_dismissal": divide_or_none(reliable_balls, reliable_outs),
                "minutes_per_dismissal": divide_or_none(reliable_minutes, reliable_outs) if reliable_minutes > 0 else None,
                "boundaries": boundaries,
                "boundary_rate": divide_or_none(boundaries, innings),
                "ducks": ducks,
                "innings_per_duck": divide_or_none(innings, ducks),
            }
        )
    return pd.DataFrame(rows)


def add_bbb_peer_batting_rates(batting_rows: pd.DataFrame, seasons: tuple[str, ...], peer_scope: tuple[str, ...]) -> pd.DataFrame:
    if batting_rows.empty:
        return batting_rows
    source = read_match_centre_csv(HALL_OF_FAME_BBB_BATTING_RATES_PATH)
    if source.empty or "canonical_player_id" not in source:
        return batting_rows
    for column in ["bbb_runs", "bbb_balls_faced"]:
        if column not in source:
            source[column] = 0
        source[column] = pd.to_numeric(source[column], errors="coerce").fillna(0)
    grouped = source.groupby("canonical_player_id", dropna=False, as_index=False).agg(
        bbb_runs=("bbb_runs", "sum"),
        bbb_balls=("bbb_balls_faced", "sum"),
    )
    grouped["bat_sr_bbb"] = grouped.apply(lambda row: divide_or_none(float(row["bbb_runs"]) * 100, float(row["bbb_balls"])), axis=1)
    output = batting_rows.drop(columns=["bbb_runs", "bbb_balls", "bat_sr"], errors="ignore").merge(
        grouped,
        on="canonical_player_id",
        how="left",
    )
    output["bbb_runs"] = pd.to_numeric(output.get("bbb_runs"), errors="coerce").fillna(0)
    output["bbb_balls"] = pd.to_numeric(output.get("bbb_balls"), errors="coerce").fillna(0)
    output["bat_sr"] = pd.to_numeric(output.get("bat_sr_bbb"), errors="coerce")
    return output.drop(columns=["bat_sr_bbb"], errors="ignore")


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
        extras = sum_column(group, "bowlingWides") + sum_column(group, "bowlingNoBalls")
        unassisted_wickets = sum_column(group, "bowlingWicketsUnassisted")
        overs = balls / 6 if balls else 0.0
        rows.append(
            {
                "canonical_player_id": player_id,
                "wickets": wickets,
                "runs_against": runs_against,
                "balls": balls,
                "overs": overs,
                "extras": extras,
                "unassisted_wickets": unassisted_wickets,
                "bowl_avg": divide_or_none(runs_against, wickets),
                "bowl_sr": divide_or_none(balls, wickets),
                "economy": divide_or_none(runs_against * 6, balls),
                "maidens": maidens,
                "overs_per_maiden": divide_or_none(overs, maidens),
                "balls_per_extra": divide_or_none(balls, extras),
                "unassisted_wicket_pct": divide_or_none(unassisted_wickets * 100, wickets),
            }
        )
    return pd.DataFrame(rows)


def build_peer_metric_rows(
    data: pd.DataFrame,
    player_id: str,
    metrics: list[tuple[str, str, bool, str]],
    average_overrides: dict[str, float | None] | None = None,
    status_overrides: dict[str, str] | None = None,
) -> list[dict[str, object]]:
    if data.empty or "canonical_player_id" not in data:
        return []
    average_overrides = average_overrides or {}
    status_overrides = status_overrides or {}
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
            continue
        minimum = float(valid_values.min())
        maximum = float(valid_values.max())
        if column in average_overrides:
            override_average = average_overrides[column]
            average = float(override_average) if override_average is not None else None
        else:
            average = float(valid_values.mean())
        status = status_overrides.get(column)
        if status is None:
            status = peer_metric_status(value, average, minimum, maximum, lower_is_better)
        rows.append(
            {
                "label": label,
                "value": value,
                "average": average,
                "minimum": minimum,
                "maximum": maximum,
                "lower_is_better": lower_is_better,
                "format": value_format,
                "peer_count": int(valid_values.shape[0]),
                "status": status,
            }
        )
    return rows


def sum_numeric(data: pd.DataFrame, column: str) -> float:
    if data.empty or column not in data:
        return 0.0
    return float(pd.to_numeric(data[column], errors="coerce").fillna(0).sum())


def export_player_vs_peers_debug(
    player_id: str,
    peer_scope: tuple[str, ...],
    batting_metrics: list[dict[str, object]],
    bowling_metrics: list[dict[str, object]],
) -> None:
    rows = []
    for category, metrics in [("Batting", batting_metrics), ("Bowling", bowling_metrics)]:
        for metric in metrics:
            rows.append(
                {
                    "canonical_player_id": player_id,
                    "peer_grade_scope": " | ".join(peer_scope),
                    "peer_count": metric.get("peer_count"),
                    "category": category,
                    "metric": metric.get("label"),
                    "player_value": metric.get("value"),
                    "peer_avg": metric.get("average"),
                    "peer_min": metric.get("minimum"),
                    "peer_max": metric.get("maximum"),
                    "better_direction": "lower" if metric.get("lower_is_better") else "higher",
                    "comparison_label": metric.get("status"),
                }
            )
    if not rows:
        return
    DEBUG_PLAYER_VS_PEERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(DEBUG_PLAYER_VS_PEERS_PATH, index=False)


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
    if (
        value is None
        or average is None
        or minimum is None
        or maximum is None
        or pd.isna(value)
        or pd.isna(average)
        or pd.isna(minimum)
        or pd.isna(maximum)
        or average == 0
    ):
        return "—"
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
        return "N/A"
    numeric = float(value)
    if value_format == "percent":
        return f"{numeric:.1f}%"
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
        "Strike Rate": "Verified ball-by-ball only",
        "Boundary Rate": "4s + 6s per innings",
        "Innings per Duck": "Higher means fewer ducks",
        "Overs per Maiden": "Lower means maidens are more frequent",
        "Balls per Extra": "Higher means fewer wides/no-balls",
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
        status = str(row.get("status") if row.get("status") is not None else peer_metric_status(
            value,
            average,
            minimum,
            maximum,
            bool(row.get("lower_is_better")),
        ))
        status_html = (
            f'<strong class="peer-status {peer_status_class(status)}">{html.escape(status)}</strong>'
            if status
            else ""
        )
        row_html.append(
            '<div class="peer-row">'
            '<div class="peer-row-top">'
            f'<span class="peer-metric">{metric_label}</span>'
            f'<span class="peer-value">{html.escape(format_peer_metric_value(value, str(row["format"])))}</span>'
            "</div>"
            '<div class="peer-row-meta">'
            f'<span>Peer avg. {html.escape(format_peer_metric_value(average, str(row["format"])))}</span>'
            f"{status_html}"
            "</div>"
            f"{comparison_bar_html(average_marker, player_marker)}"
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


def comparison_bar_html(average_marker: str = "", player_marker: str = "", fill_percent: float | None = None) -> str:
    fill_html = ""
    if fill_percent is not None:
        fill_width = max(0.0, min(100.0, float(fill_percent)))
        fill_html = f'<div class="peer-fill" style="width:{fill_width:.1f}%;"></div>'
    return f'<div class="peer-range">{fill_html}{average_marker}{player_marker}</div>'


def render_player_trends(season_table: pd.DataFrame) -> None:
    if season_table.empty:
        return
    render_section_heading("Season Trends 📈")
    chart_data = season_table.sort_values("Season", key=lambda series: series.map(profile_season_sort_key), ascending=True)
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
                    chart_height = min(340, max(150, 30 * season_count))
                    max_value = float(values[metric].max()) if not values.empty else 0.0
                    base = (
                        alt.Chart(values)
                        .encode(
                            y=alt.Y(
                                "Season:N",
                                sort=list(values["Season"]),
                                axis=alt.Axis(labelColor="#737998", labelLimit=110, title=None),
                                scale=alt.Scale(paddingInner=0.22, paddingOuter=0.12),
                            ),
                            x=alt.X(
                                f"{metric}:Q",
                                axis=alt.Axis(grid=False, labels=False, ticks=False, title=None),
                                scale=alt.Scale(domain=[0, max(max_value * 1.08, 1.0)], nice=False),
                            ),
                            tooltip=[alt.Tooltip("Season:N"), alt.Tooltip(f"{metric}:Q", format=",.0f")],
                        )
                    )
                    chart = (
                        base.mark_bar(cornerRadiusTopRight=7, cornerRadiusBottomRight=7, color=color)
                        + base.mark_text(
                            align="right",
                            baseline="middle",
                            color="#ffffff",
                            dx=-7,
                            fontSize=10,
                            fontWeight=800,
                        ).encode(text=alt.Text(f"{metric}:Q", format=",.0f"))
                    ).properties(height=chart_height, padding={"left": 4, "right": 10, "top": 8, "bottom": 4}).configure(background="#FFFFFF").configure_view(fill="#FFFFFF", stroke=None)
                    st.altair_chart(chart, use_container_width=True)


def render_player_best_season_cards(chart_data: pd.DataFrame) -> None:
    batting = best_player_batting_season_card(chart_data)
    bowling = best_player_bowling_season_card(chart_data)
    if not batting and not bowling:
        return
    columns = st.columns(2)
    for column, card in zip(columns, [batting, bowling]):
        if not card:
            continue
        with column:
            st.markdown(player_best_season_card_html(card), unsafe_allow_html=True)


def best_player_batting_season_card(chart_data: pd.DataFrame) -> dict[str, str] | None:
    if chart_data.empty or "Runs" not in chart_data:
        return None
    rows = chart_data.copy()
    rows["Runs"] = pd.to_numeric(rows["Runs"], errors="coerce").fillna(0)
    rows = rows[rows["Runs"] > 0].sort_values(["Runs", "Bat Avg"], ascending=[False, False])
    if rows.empty:
        return None
    row = rows.iloc[0]
    fifties = int(numeric_value(row, "50s"))
    hundreds = int(numeric_value(row, "100s"))
    milestones = []
    if fifties:
        milestones.append(f"{fifties} x 50")
    if hundreds:
        milestones.append(f"{hundreds} x 100")
    return {
        "label": "Best Batting Season",
        "season": str(row.get("Season", "—")),
        "value": f"{int(row['Runs']):,} runs",
        "meta": f"Avg {format_decimal(row.get('Bat Avg'))} · HS {row.get('HS', '—')}",
        "insight": "Peak run-scoring season" + (f" with {' and '.join(milestones)}." if milestones else "."),
    }


def best_player_bowling_season_card(chart_data: pd.DataFrame) -> dict[str, str] | None:
    if chart_data.empty or "Wickets" not in chart_data:
        return None
    rows = chart_data.copy()
    rows["Wickets"] = pd.to_numeric(rows["Wickets"], errors="coerce").fillna(0)
    rows = rows[rows["Wickets"] > 0].sort_values(["Wickets", "Bowl Avg"], ascending=[False, True])
    if rows.empty:
        return None
    row = rows.iloc[0]
    return {
        "label": "Best Bowling Season",
        "season": str(row.get("Season", "—")),
        "value": f"{int(row['Wickets']):,} wickets",
        "meta": f"Avg {format_decimal(row.get('Bowl Avg'))} · Eco {format_decimal(row.get('Econ'))} · BBI {row.get('BBI', '—')}",
        "insight": "Peak wicket-taking season from scorecard bowling records.",
    }


def player_best_season_card_html(card: dict[str, str]) -> str:
    return (
        '<article class="profile-season-summary-card">'
        f'<span>{html.escape(card["label"])}</span>'
        f'<h4>{season_overview_link_html(card["season"])}</h4>'
        f'<strong>{html.escape(card["value"])}</strong>'
        f'<div>{html.escape(card["meta"])}</div>'
        f'<p>{html.escape(card["insight"])}</p>'
        '</article>'
    )


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


def render_player_performance_breakdown(profile_view: dict[str, pd.DataFrame]) -> None:
    source = profile_view.get("performance_breakdown", pd.DataFrame()).copy()
    if source.empty:
        return
    render_section_heading("Career Breakdown 🧭")
    selected = selected_profile_breakdown_view()
    selected_discipline = selected_profile_discipline_view()
    render_profile_breakdown_tabs()
    with st.container(key="player_profile_performance_breakdown"):
        render_profile_breakdown_controls(profile_view, selected, selected_discipline)
        label = profile_breakdown_label(selected)
        rows = source[source["dimension"].astype(str) == label].copy() if "dimension" in source else source.head(0)
        if rows.empty:
            render_profile_empty_state(*profile_performance_empty_copy(label, selected_discipline))
            return
        render_profile_performance_table(rows, label, selected_discipline)


def profile_breakdown_options() -> list[tuple[str, str]]:
    return [
        ("season", "Season"),
        ("grade", "Grade"),
        ("opponent", "Opponent"),
        ("ground", "Ground"),
        ("ha", "Home/Away"),
        ("captain", "Captain"),
    ]


def selected_profile_breakdown_view() -> str:
    valid = {slug for slug, _label in profile_breakdown_options()}
    key = "player_profile_breakdown_view"
    if key not in st.session_state:
        requested = query_param_value("profile_breakdown").casefold()
        st.session_state[key] = requested if requested in valid else "season"
    selected = str(st.session_state.get(key, "season")).casefold()
    if selected not in valid:
        selected = "season"
        st.session_state[key] = selected
    return selected


def profile_discipline_options() -> list[tuple[str, str]]:
    return [("batting", "Batting"), ("bowling", "Bowling"), ("fielding", "Fielding")]


def selected_profile_discipline_view() -> str:
    options = {slug: label for slug, label in profile_discipline_options()}
    key = "player_profile_discipline_view"
    if key not in st.session_state:
        requested = query_param_value("profile_discipline").casefold()
        st.session_state[key] = requested if requested in options else "batting"
    selected = str(st.session_state.get(key, "batting")).casefold()
    if selected not in options:
        selected = "batting"
        st.session_state[key] = selected
    return options[selected]


def profile_breakdown_label(slug: str) -> str:
    if slug == "ha":
        return "H/A"
    return dict(profile_breakdown_options()).get(slug, "Season")


def render_profile_breakdown_controls(profile_view: dict[str, pd.DataFrame], selected_breakdown: str, selected_discipline: str) -> None:
    del profile_view
    del selected_breakdown
    del selected_discipline
    with st.container(key="profile_breakdown_controls"):
        render_profile_segmented_widget(
            "Career breakdown discipline",
            profile_discipline_options(),
            key="player_profile_discipline_view",
        )


def render_profile_breakdown_tabs() -> None:
    render_folder_tab_widget(
        "Career breakdown view",
        profile_breakdown_options(),
        key="player_profile_breakdown_view",
        control_key="player_profile_breakdown_folder_tabs",
    )


def player_profile_section_url(player_id: object, **params: str) -> str:
    query = {
        "page": PLAYER_PROFILE_QUERY_PAGE,
        "player_id": str(player_id or "").strip(),
    }
    for key in ["profile_breakdown", "profile_discipline", "profile_phase_model"]:
        existing = query_param_value(key)
        if existing:
            query[key] = existing
    query.update({key: str(value) for key, value in params.items() if str(value or "").strip()})
    return "?" + "&".join(f"{quote(key, safe='')}={quote(value, safe='')}" for key, value in query.items() if value)


def render_profile_segmented_links(
    items: list[tuple[str, str, bool]],
    aria_label: str,
    compact: bool = False,
) -> None:
    class_name = "profile-segmented profile-segmented-compact" if compact else "profile-segmented"
    st.markdown(
        profile_segmented_links_html(items, aria_label, class_name=class_name),
        unsafe_allow_html=True,
    )


def render_profile_segmented_widget(
    label: str,
    options: list[tuple[str, str]],
    key: str,
    compact: bool = False,
) -> str:
    option_slugs = [slug for slug, _label in options]
    label_map = dict(options)
    if key not in st.session_state or str(st.session_state.get(key)).casefold() not in option_slugs:
        st.session_state[key] = option_slugs[0]
    with st.container(key=f"{key}_control"):
        selected = st.segmented_control(
            label,
            option_slugs,
            format_func=lambda slug: label_map.get(slug, str(slug)),
            key=key,
            label_visibility="collapsed",
        )
    selected_slug = str(selected or st.session_state.get(key) or option_slugs[0]).casefold()
    if selected_slug not in option_slugs:
        selected_slug = option_slugs[0]
        st.session_state[key] = selected_slug
    return label_map.get(selected_slug, label_map[option_slugs[0]])


def render_folder_tab_widget(
    label: str,
    options: list[tuple[str, str]],
    key: str,
    control_key: str | None = None,
) -> str:
    option_slugs = [slug for slug, _label in options]
    option_slug_lookup = {str(slug).casefold(): slug for slug in option_slugs}
    label_map = dict(options)
    if not option_slugs:
        return ""
    current_key = str(st.session_state.get(key)).casefold()
    if key not in st.session_state or current_key not in option_slug_lookup:
        st.session_state[key] = option_slugs[0]
    elif st.session_state.get(key) != option_slug_lookup[current_key]:
        st.session_state[key] = option_slug_lookup[current_key]
    container_key = control_key or f"{key}_folder_tabs"
    with st.container(key=container_key):
        selected = st.segmented_control(
            label,
            option_slugs,
            format_func=lambda slug: label_map.get(slug, str(slug)),
            key=key,
            label_visibility="collapsed",
        )
    selected_key = str(selected or st.session_state.get(key) or option_slugs[0]).casefold()
    selected_slug = option_slug_lookup.get(selected_key, option_slugs[0])
    if selected_slug not in option_slugs:
        selected_slug = option_slugs[0]
        st.session_state[key] = selected_slug
    return selected_slug


def profile_segmented_links_html(
    items: list[tuple[str, str, bool]],
    aria_label: str,
    class_name: str = "profile-segmented",
) -> str:
    links = "".join(
        (
            f'<a class="profile-segment{" active" if active else ""}" '
            f'href="{html.escape(url, quote=True)}" target="_self" role="tab" '
            f'aria-selected="{str(active).lower()}">{html.escape(label)}</a>'
        )
        for label, url, active in items
    )
    return f'<nav class="{class_name}" aria-label="{html.escape(aria_label, quote=True)}">{links}</nav>'


def render_profile_breakdown_empty(label: str) -> None:
    render_profile_empty_state(
        f"No {label.lower()} breakdown available yet.",
        "This view will appear when reliable scorecard context exists for the selected player.",
    )


def profile_performance_empty_copy(label_column: str, discipline: str) -> tuple[str, str]:
    label = "Home/Away" if label_column == "H/A" else label_column
    discipline_label = str(discipline).lower()
    if label_column == "Captain":
        return (
            "Captain breakdown is not available for this player yet.",
            "This split appears only when reliable match captain data exists for the selected player's scorecard rows.",
        )
    if label_column == "Opponent":
        return (
            f"No opponent-level {discipline_label} split is available for this player yet.",
            "Opponent rows appear once the scorecard source includes enough matched opposition context.",
        )
    if label_column == "Ground":
        return (
            f"No ground-level {discipline_label} split is available for this player yet.",
            "Ground rows appear once the scorecard source includes enough matched venue context.",
        )
    if label_column == "H/A":
        return (
            f"No home/away {discipline_label} split is available for this player yet.",
            "Home/away rows depend on reliable match venue and team-side context.",
        )
    return (
        f"No {label.lower()} {discipline_label} split is available for this player yet.",
        "This is usually a data coverage or discipline-specific gap, not an error.",
    )


def render_profile_performance_table(rows: pd.DataFrame, label_column: str, discipline: str) -> None:
    filtered = rows[rows["discipline"].astype(str) == discipline].copy() if "discipline" in rows else rows.head(0)
    filtered = filtered[filtered["breakdown_label"].astype(str).str.strip() != ""].copy() if "breakdown_label" in filtered else filtered
    if filtered.empty:
        render_profile_empty_state(*profile_performance_empty_copy(label_column, discipline))
        return
    if discipline == "Batting":
        table = filtered.rename(
            columns={
                "breakdown_label": label_column,
                "innings": "Inn",
                "runs": "Runs",
                "bat_avg": "Avg",
                "strike_rate": "Strike Rate",
                "high_score": "HS",
                "thirties": "30s",
                "fifties": "50s",
                "hundreds": "100s",
                "ducks": "0s",
                "fours": "4s",
                "sixes": "6s",
            }
        )
        columns = [label_column, "Inn", "Runs", "Avg", "Strike Rate", "HS", "30s", "50s", "100s", "0s", "4s", "6s"]
        activity_columns = ["Inn", "Runs", "30s", "50s", "100s"]
    elif discipline == "Bowling":
        table = filtered.rename(
            columns={
                "breakdown_label": label_column,
                "matches": "M",
                "wickets": "W",
                "bowl_avg": "Avg",
                "bowl_sr": "SR",
                "eco": "Eco",
                "bbi": "BBI",
                "three_wicket_innings": "3WI",
                "five_wicket_innings": "5WI",
            }
        )
        table["Overs"] = table["balls_bowled"].map(format_balls_as_overs) if "balls_bowled" in table else "—"
        columns = [label_column, "M", "Overs", "W", "Avg", "SR", "Eco", "BBI", "3WI", "5WI"]
        activity_columns = ["W", "balls_bowled", "3WI", "5WI"]
    else:
        table = filtered.rename(
            columns={
                "breakdown_label": label_column,
                "run_outs": "RO",
                "catches": "Catches",
                "stumpings": "Stumpings",
                "dismissals": "Dismissals",
            }
        )
        columns = [label_column, "Catches", "Stumpings", "RO", "Dismissals"]
        activity_columns = ["Catches", "Stumpings", "RO", "Dismissals"]

    table = select_display_columns(table, columns).copy()
    activity = pd.Series(False, index=table.index)
    for column in activity_columns:
        if column in table:
            activity = activity | (pd.to_numeric(table[column], errors="coerce").fillna(0) > 0)
        elif column == "balls_bowled" and "Overs" in table:
            activity = activity | (table["Overs"].map(cricket_overs_to_balls).fillna(0) > 0)
    table = table.loc[activity].copy()
    if table.empty:
        render_profile_empty_state(*profile_performance_empty_copy(label_column, discipline))
        return

    table = sort_profile_performance_table(table, label_column, discipline)
    display = format_profile_sortable_table(table)
    if label_column == "Season":
        display = link_season_columns(display, ["Season"])
    height = min(460, max(170, 38 * (len(display) + 1)))
    components.html(
        profile_performance_table_html(
            display,
            label_column=label_column,
            discipline=discipline,
            table_id=f"profile-performance-{label_column}-{discipline}",
            height=height,
        ),
        height=height,
        scrolling=False,
    )


def profile_performance_table_html(
    table: pd.DataFrame,
    label_column: str,
    discipline: str,
    table_id: str,
    height: int,
) -> str:
    safe_table_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", table_id).strip("-") or "profile-performance-table"
    columns = table.columns.tolist()
    colgroup = "".join(
        f'<col class="{profile_performance_column_class(column, label_column)}">'
        for column in columns
    )
    header_html = "".join(
        (
            f'<th class="{profile_performance_column_class(column, label_column)}" data-column="{index}" '
            f'data-default-dir="{profile_performance_default_sort_dir(column, label_column)}">'
            f'<button type="button">{html.escape(str(column))}<span class="sort-indicator"></span></button></th>'
        )
        for index, column in enumerate(columns)
    )
    body_rows = []
    for _, row in table.iterrows():
        cells = []
        for column in columns:
            value = row.get(column)
            display = profile_performance_display_value(column, value, label_column)
            sort_value, missing = profile_performance_sort_value(column, value, label_column)
            cells.append(
                f'<td class="{profile_performance_column_class(column, label_column)}" '
                f'data-sort="{html.escape(sort_value, quote=True)}" data-missing="{int(missing)}">'
                f'{display}</td>'
            )
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    empty_state = (
        '<tr><td class="profile-performance-empty" colspan="'
        f'{max(len(columns), 1)}">No {html.escape(discipline.lower())} data available for this view.</td></tr>'
        if table.empty
        else ""
    )
    return f"""
    <style>
      html, body {{
        background: transparent;
        color-scheme: light;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 0;
        padding: 0;
      }}
      .profile-performance-table-wrap {{
        background: #ffffff;
        border: 1px solid #dfe3ee;
        border-radius: 16px;
        box-shadow: 0 12px 28px rgba(23, 27, 77, 0.055);
        height: {max(160, height - 12)}px;
        overflow: auto;
      }}
      table.profile-performance-table {{
        border-collapse: separate;
        border-spacing: 0;
        color: #080a3f;
        font-size: 12.5px;
        min-width: 100%;
        table-layout: fixed;
        width: max-content;
      }}
      .profile-performance-table col.profile-col-label {{ width: 184px; }}
      .profile-performance-table col.profile-col-inn,
      .profile-performance-table col.profile-col-m,
      .profile-performance-table col.profile-col-w,
      .profile-performance-table col.profile-col-30s,
      .profile-performance-table col.profile-col-50s,
      .profile-performance-table col.profile-col-100s,
      .profile-performance-table col.profile-col-0s,
      .profile-performance-table col.profile-col-4s,
      .profile-performance-table col.profile-col-6s,
      .profile-performance-table col.profile-col-3wi,
      .profile-performance-table col.profile-col-5wi,
      .profile-performance-table col.profile-col-ro {{ width: 48px; }}
      .profile-performance-table col.profile-col-runs,
      .profile-performance-table col.profile-col-hs,
      .profile-performance-table col.profile-col-overs,
      .profile-performance-table col.profile-col-eco,
      .profile-performance-table col.profile-col-bbi,
      .profile-performance-table col.profile-col-catches,
      .profile-performance-table col.profile-col-stumpings {{ width: 64px; }}
      .profile-performance-table col.profile-col-avg,
      .profile-performance-table col.profile-col-sr,
      .profile-performance-table col.profile-col-strike-rate,
      .profile-performance-table col.profile-col-dismissals {{ width: 82px; }}
      .profile-performance-table th,
      .profile-performance-table td {{
        background: #ffffff;
        border-bottom: 1px solid #dfe3ee;
        border-right: 1px solid #dfe3ee;
        box-sizing: border-box;
        line-height: 1.14;
        padding: 7px 7px;
        text-align: right;
        vertical-align: middle;
        white-space: nowrap;
      }}
      .profile-performance-table th {{
        background: #fbfbfe;
        color: #687093;
        font-weight: 800;
        position: sticky;
        top: 0;
        z-index: 3;
      }}
      .profile-performance-table th button {{
        align-items: center;
        background: transparent;
        border: 0;
        color: inherit;
        cursor: pointer;
        display: inline-flex;
        font: inherit;
        gap: 4px;
        justify-content: flex-end;
        margin: 0;
        padding: 0;
        width: 100%;
      }}
      .profile-performance-table th.sorted-asc .sort-indicator::after {{ content: "↑"; }}
      .profile-performance-table th.sorted-desc .sort-indicator::after {{ content: "↓"; }}
      .profile-performance-table .profile-col-label {{
        left: 0;
        position: sticky;
        text-align: left;
        white-space: normal;
        z-index: 2;
        box-shadow: 4px 0 8px rgba(8, 10, 63, 0.08);
      }}
      .profile-performance-table th.profile-col-label {{
        z-index: 4;
      }}
      .profile-performance-table .profile-label-text,
      .profile-performance-table .profile-label-link {{
        color: #0072ce;
        display: block;
        font-weight: 750;
        line-height: 1.13;
        overflow-wrap: anywhere;
        text-decoration: none;
        white-space: normal;
        word-break: normal;
      }}
      .profile-performance-table .profile-label-text {{
        color: #11154b;
      }}
      .profile-performance-table .profile-label-link:hover {{
        color: #5b3df5;
        text-decoration: underline;
      }}
      .profile-performance-table tr:nth-child(even) td {{
        background: #fbfcff;
      }}
      .profile-performance-table tr:hover td {{
        background: #f7f5ff;
      }}
      .profile-performance-empty {{
        color: #7a819f;
        font-weight: 800;
        padding: 22px !important;
        text-align: center !important;
      }}
      @media (max-width: 760px) {{
        .profile-performance-table-wrap {{
          border-radius: 14px;
        }}
        table.profile-performance-table {{
          font-size: 11.5px;
        }}
        .profile-performance-table col.profile-col-label {{ width: 126px; }}
        .profile-performance-table col.profile-col-inn,
        .profile-performance-table col.profile-col-m,
        .profile-performance-table col.profile-col-w,
        .profile-performance-table col.profile-col-30s,
        .profile-performance-table col.profile-col-50s,
        .profile-performance-table col.profile-col-100s,
        .profile-performance-table col.profile-col-0s,
        .profile-performance-table col.profile-col-4s,
        .profile-performance-table col.profile-col-6s,
        .profile-performance-table col.profile-col-3wi,
        .profile-performance-table col.profile-col-5wi,
        .profile-performance-table col.profile-col-ro {{ width: 42px; }}
        .profile-performance-table col.profile-col-runs,
        .profile-performance-table col.profile-col-hs,
        .profile-performance-table col.profile-col-overs,
        .profile-performance-table col.profile-col-eco,
        .profile-performance-table col.profile-col-bbi,
        .profile-performance-table col.profile-col-catches,
        .profile-performance-table col.profile-col-stumpings {{ width: 56px; }}
        .profile-performance-table col.profile-col-avg,
        .profile-performance-table col.profile-col-sr,
        .profile-performance-table col.profile-col-strike-rate,
        .profile-performance-table col.profile-col-dismissals {{ width: 70px; }}
        .profile-performance-table th,
        .profile-performance-table td {{
          padding: 6px 5px;
        }}
      }}
    </style>
    <div class="profile-performance-table-wrap">
      <table id="{html.escape(safe_table_id, quote=True)}" class="profile-performance-table">
        <colgroup>{colgroup}</colgroup>
        <thead><tr>{header_html}</tr></thead>
        <tbody>{empty_state if table.empty else ''.join(body_rows)}</tbody>
      </table>
    </div>
    <script>
      (() => {{
        const table = document.getElementById({safe_table_id!r});
        if (!table) return;
        const tbody = table.querySelector("tbody");
        const headers = Array.from(table.querySelectorAll("th"));
        const textValue = (row, index) => row.children[index].textContent.trim().toLocaleLowerCase();
        const sortValue = (row, index) => {{
          const cell = row.children[index];
          if (!cell || cell.dataset.missing === "1") return null;
          const raw = cell.dataset.sort || "";
          const numeric = Number(raw);
          return Number.isFinite(numeric) && raw.trim() !== "" ? numeric : raw.toLocaleLowerCase();
        }};
        const compare = (a, b, index, dir) => {{
          const av = sortValue(a, index);
          const bv = sortValue(b, index);
          if (av === null && bv === null) return textValue(a, 0).localeCompare(textValue(b, 0));
          if (av === null) return 1;
          if (bv === null) return -1;
          let result = 0;
          if (typeof av === "number" && typeof bv === "number") {{
            result = av === bv ? 0 : av < bv ? -1 : 1;
          }} else {{
            result = String(av).localeCompare(String(bv), undefined, {{ numeric: true, sensitivity: "base" }});
          }}
          if (result === 0) result = textValue(a, 0).localeCompare(textValue(b, 0));
          return dir === "asc" ? result : -result;
        }};
        const sortHeader = (header, index) => {{
          const current = header.dataset.sortDir;
          const dir = current ? (current === "asc" ? "desc" : "asc") : (header.dataset.defaultDir || "desc");
          headers.forEach(item => {{
            item.classList.remove("sorted-asc", "sorted-desc");
            delete item.dataset.sortDir;
          }});
          header.dataset.sortDir = dir;
          header.classList.add(`sorted-${{dir}}`);
          Array.from(tbody.querySelectorAll("tr"))
            .sort((a, b) => compare(a, b, index, dir))
            .forEach(row => tbody.appendChild(row));
        }};
        const resolveInternalHref = (href) => {{
          let base = document.referrer || window.location.href;
          try {{
            if (window.parent && window.parent.location && window.parent.location.href) base = window.parent.location.href;
          }} catch (error) {{}}
          return new URL(href, base).toString();
        }};
        table.addEventListener("click", event => {{
          const link = event.target.closest('a[data-profile-performance-link="1"]');
          if (!link) return;
          const href = resolveInternalHref(link.getAttribute("href") || "");
          if (!href) return;
          try {{
            window.parent.location.href = href;
            event.preventDefault();
          }} catch (error) {{
            link.setAttribute("href", href);
            link.setAttribute("target", "_blank");
            link.setAttribute("rel", "noopener noreferrer");
          }}
        }});
        headers.forEach((header, index) => header.addEventListener("click", () => sortHeader(header, index)));
      }})();
    </script>
    """


def profile_performance_column_class(column: object, label_column: str) -> str:
    if str(column) == str(label_column):
        return "profile-col-label"
    text = re.sub(r"[^a-zA-Z0-9]+", "-", str(column).strip().casefold()).strip("-")
    return f"profile-col-{text or 'column'}"


def profile_performance_default_sort_dir(column: object, label_column: str) -> str:
    return "asc" if str(column) == str(label_column) else "desc"


def profile_performance_display_value(column: str, value: object, label_column: str) -> str:
    if str(column) == str(label_column):
        return profile_performance_label_cell(value)
    if pd.isna(value) or str(value).strip() in {"", "—", "N/A", "None", "nan"}:
        return "N/A"
    if column == "Strike Rate":
        numeric = pd.to_numeric(value, errors="coerce")
        return "N/A" if pd.isna(numeric) else f"{float(numeric):.1f}%"
    if column in {"Avg", "SR", "Eco"}:
        numeric = pd.to_numeric(value, errors="coerce")
        return "N/A" if pd.isna(numeric) else f"{float(numeric):.2f}"
    if column in {"Inn", "Runs", "30s", "50s", "100s", "0s", "4s", "6s", "M", "W", "3WI", "5WI", "Catches", "Stumpings", "RO", "Dismissals"}:
        numeric = pd.to_numeric(value, errors="coerce")
        return "N/A" if pd.isna(numeric) else f"{int(numeric):,}"
    text = str(value).strip()
    return html.escape(text if text and text.casefold() not in {"none", "nan"} else "N/A")


def profile_performance_label_cell(value: object) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return '<span class="profile-label-text">N/A</span>'
    text = str(value).strip()
    label = link_display_label(text)
    if text.startswith("?"):
        return (
            f'<a class="profile-label-link" href="{html.escape(text, quote=True)}" '
            f'data-profile-performance-link="1" target="_top" '
            f'title="Open {html.escape(label or text, quote=True)}">'
            f'{html.escape(label or text)}</a>'
        )
    return f'<span class="profile-label-text">{html.escape(label or text)}</span>'


def profile_performance_sort_value(column: str, value: object, label_column: str) -> tuple[str, bool]:
    if pd.isna(value) or str(value).strip() in {"", "—", "N/A", "None", "nan"}:
        return "", True
    if str(column) == str(label_column):
        label = link_display_label(value)
        if str(label_column) == "Season":
            return str(profile_season_sort_key(label)), False
        if str(label_column) == "Grade":
            return str(grade_sort_key(label)), False
        return str(label).casefold(), False
    if column == "HS":
        runs, not_out = parse_batting_score(value)
        if runs is None:
            return "", True
        return str(runs * 10 + int(not_out)), False
    if column == "BBI":
        wickets, runs = parse_bowling_figures(value)
        if wickets is None or runs is None:
            return "", True
        return str(wickets * 10000 - runs), False
    if column == "Overs":
        balls = cricket_overs_to_balls(value)
        return ("" if balls is None else str(balls), balls is None)
    numeric = pd.to_numeric(value, errors="coerce")
    if not pd.isna(numeric):
        return str(float(numeric)), False
    return str(value).casefold(), False


def sort_profile_performance_table(table: pd.DataFrame, label_column: str, discipline: str) -> pd.DataFrame:
    output = table.copy()
    if label_column == "Season":
        return output.sort_values(label_column, key=lambda series: series.map(profile_season_sort_key), ascending=False)
    if label_column == "Grade":
        output["_sort_key"] = output[label_column].map(grade_sort_key)
        return output.sort_values("_sort_key").drop(columns="_sort_key")
    numeric_sort = "Runs" if discipline == "Batting" and "Runs" in output else "W" if discipline == "Bowling" and "W" in output else "Dismissals"
    if numeric_sort in output:
        output["_sort_key"] = pd.to_numeric(output[numeric_sort], errors="coerce").fillna(0)
        return output.sort_values(["_sort_key", label_column], ascending=[False, True]).drop(columns="_sort_key")
    return output.sort_values(label_column)


def render_player_season_table(season_table: pd.DataFrame) -> None:
    render_section_heading("Season History 📅")
    with st.container(key="player_profile_season_table"):
        batting_tab, bowling_tab, fielding_tab = st.tabs(["Batting", "Bowling", "Fielding"])
        with batting_tab:
            columns = ["Season", "Innings", "Runs", "Bat Avg", "Bat SR", "HS", "30s", "50s", "100s", "0s", "4s", "6s"]
            render_profile_season_stat_table(season_table, columns, ["Innings", "Runs", "30s", "50s", "100s"])
        with bowling_tab:
            table = season_table.copy()
            table["Overs"] = table["Balls Bowled"].map(format_balls_as_overs) if "Balls Bowled" in table else "—"
            table = table.rename(columns={"Econ": "Eco"})
            render_profile_season_stat_table(
                table,
                ["Season", "Matches", "Overs", "Wickets", "Bowl Avg", "Bowl SR", "Eco", "BBI", "3WI", "5WI"],
                ["Balls Bowled", "Runs Against", "Wickets", "Wides", "No Balls", "3WI", "5WI"],
            )
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
            columns = ["Grade", "Innings", "Runs", "Bat Avg", "Bat SR", "HS", "30s", "50s", "100s", "0s", "4s", "6s"]
            render_profile_group_stat_table(grade_table, columns, ["Innings", "Runs", "30s", "50s", "100s"], "Grade")
        with bowling_tab:
            table = grade_table.copy()
            table["Overs"] = table["Balls Bowled"].map(format_balls_as_overs) if "Balls Bowled" in table else "—"
            table = table.rename(columns={"Econ": "Eco"})
            columns = ["Grade", "Matches", "Overs", "Wickets", "Bowl Avg", "Bowl SR", "Eco", "BBI", "3WI", "5WI"]
            render_profile_group_stat_table(
                table,
                columns,
                ["Balls Bowled", "Runs Against", "Wickets", "Wides", "No Balls", "3WI", "5WI"],
                "Grade",
            )
        with fielding_tab:
            columns = ["Grade", "Matches", "Catches", "Stumpings", "Run Outs", "Dismissals"]
            render_profile_group_stat_table(grade_table, columns, ["Catches", "Stumpings", "Run Outs", "Dismissals"], "Grade")


def render_profile_season_stat_table(season_table: pd.DataFrame, columns: list[str], activity_columns: list[str]) -> None:
    table = select_display_columns(season_table, columns).copy()
    if table.empty:
        st.caption("No data available for this view.")
        return
    activity = pd.Series(False, index=season_table.index)
    for column in activity_columns:
        if column in season_table:
            activity = activity | (pd.to_numeric(season_table[column], errors="coerce").fillna(0) > 0)
    table = table.loc[activity.reindex(table.index, fill_value=False)].copy()
    if table.empty:
        st.caption("No data available for this view.")
        return
    table = table.sort_values("Season", key=lambda series: series.map(profile_season_sort_key), ascending=False)
    display = link_season_columns(format_profile_sortable_table(table), ["Season"])
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
    integer_columns = {
        "M",
        "Matches",
        "Inn",
        "Innings",
        "Runs",
        "BF",
        "BBB Runs",
        "BBB Balls",
        "BBB Innings",
        "BBB Matches",
        "30s",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
        "Maidens",
        "W",
        "Wickets",
        "3WI",
        "5WI",
        "Catches",
        "Stumpings",
        "RO",
        "Run Outs",
        "Dismissals",
    }
    percent_columns = {"Bat SR", "Strike Rate"}
    decimal_columns = {"Avg", "Bat Avg", "Bowl Avg", "Bowl SR", "SR", "Econ", "Eco"}
    for column in columns:
        if column == pinned_column:
            if column == "Season":
                config[column] = st.column_config.LinkColumn(column, pinned=True, width="medium", display_text=overview_link_display_pattern())
            else:
                config[column] = st.column_config.TextColumn(column, pinned=True, width="medium")
        elif column in {"Player", "Grade"}:
            config[column] = st.column_config.TextColumn(column, width="medium")
        elif column == "Season":
            config[column] = st.column_config.LinkColumn(column, width="small", display_text=overview_link_display_pattern())
        elif column in {"BBI", "HS", "Overs"}:
            config[column] = st.column_config.TextColumn(column, width="small")
        elif column in integer_columns:
            config[column] = st.column_config.NumberColumn(column, width="small", format="%d")
        elif column in percent_columns:
            config[column] = st.column_config.NumberColumn(column, width="small", format="%.1f%%")
        elif column in decimal_columns:
            config[column] = st.column_config.NumberColumn(column, width="small", format="%.2f")
        else:
            config[column] = st.column_config.TextColumn(column, width="small")
    return config


def render_profile_table_totals(table: pd.DataFrame, label_column: str) -> None:
    totals = []
    for column in ["Matches", "Innings", "Runs", "30s", "4s", "6s", "Wickets", "3WI", "5WI", "Catches", "Stumpings", "Run Outs", "Dismissals"]:
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
    activity = pd.Series(False, index=group_table.index)
    for column in activity_columns:
        if column in group_table:
            activity = activity | (pd.to_numeric(group_table[column], errors="coerce").fillna(0) > 0)
    table = table.loc[activity.reindex(table.index, fill_value=False)].copy()
    if table.empty:
        st.caption("No data available for this view.")
        return
    if label_column == "Grade":
        table["_sort_key"] = table[label_column].map(grade_sort_key)
        table = table.sort_values("_sort_key").drop(columns="_sort_key")
    else:
        table = table.sort_values(label_column)
    display = format_profile_sortable_table(table)
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

    for column in ["Matches", "Innings", "Runs", "BF", "30s", "50s", "100s", "0s", "4s", "6s", "Wickets", "3WI", "5WI", "Catches", "Stumpings", "Run Outs", "Dismissals"]:
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
        sr_runs = sum_numeric_series(source_rows["BBB Runs"]) if "BBB Runs" in source_rows else 0
        sr_balls = sum_numeric_series(source_rows["BBB Balls"]) if "BBB Balls" in source_rows else 0
        row["Bat SR"] = divide_or_none(sr_runs * 100, sr_balls)
    if "HS" in columns and "HS" in source_rows:
        row["HS"] = best_high_score_from_display_values(source_rows["HS"])
    if "Overs" in columns:
        row["Overs"] = format_balls_as_overs(balls_bowled) if balls_bowled else "—"
    if "Bowl Avg" in columns:
        row["Bowl Avg"] = divide_or_none(runs_against, wickets)
    if "Econ" in columns:
        row["Econ"] = divide_or_none(runs_against * 6, balls_bowled)
    if "Eco" in columns:
        row["Eco"] = divide_or_none(runs_against * 6, balls_bowled)
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
    render_section_heading("Career Overview 🧩")
    keeper_class = "profile-card-keeper" if player_profile_is_keeper(career) else "profile-card-nonkeeper"
    cards = [
        ("Batting", [("Matches/Innings", f"{format_int(career.get('Matches'))} / {format_int(career.get('Innings'))}"), ("Runs", format_int(career.get("Runs"))), ("Average", format_decimal(career.get("Bat Avg"))), ("Strike Rate", format_bat_sr_display(career.get("Bat SR"))), ("0s", format_int(career.get("0s"))), ("HS", str(career.get("HS", "—")))]),
        ("Bowling", [("Wickets", format_int(career.get("Wickets"))), ("Overs", str(career.get("Overs", "—"))), ("Average", format_decimal(career.get("Bowl Avg"))), ("Strike Rate", format_decimal(career.get("Bowl SR"))), ("Economy", format_decimal(career.get("Econ"))), ("BBI", str(career.get("BBI", "—")))]),
        ("Fielding", [("Catches", format_int(career.get("Catches"))), ("Stumpings", format_int(career.get("Stumpings"))), ("Run Outs", format_int(career.get("Run Outs"))), ("Dismissals", format_int(career.get("Dismissals")))]),
    ]
    columns = st.columns(3)
    for column, (title, metrics) in zip(columns, cards):
        with column:
            metric_html = "".join(f'<div><span>{html.escape(label)}</span><strong>{html.escape(value)}</strong></div>' for label, value in metrics)
            card_slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
            card_classes = f"profile-breakdown-card profile-career-overview-card profile-career-card-{card_slug} {keeper_class}"
            st.markdown(f'<div class="{card_classes}"><h4>{html.escape(title)}</h4>{metric_html}</div>', unsafe_allow_html=True)


def render_player_recent_form(career: pd.Series) -> None:
    recent = build_player_recent_form(career)
    render_section_heading("Recent Form ⚡")
    batting_html = recent_form_line_html(
        "Batting scores",
        "",
        recent["batting"],
        "bat",
        "No recent batting scores available.",
    )
    bowling_html = recent_form_line_html(
        "Bowling figures",
        "",
        recent["bowling"],
        "bowl",
        "No recent bowling figures available.",
    )
    st.markdown(f'<div class="recent-form-card">{batting_html}{bowling_html}</div>', unsafe_allow_html=True)


def build_player_recent_form(career: pd.Series) -> dict[str, list[dict[str, object]]]:
    player_id = str(career.get("canonical_player_id", "") or "").strip()
    player_name_key = player_name_match_key(career.get("Player", ""))
    sources = load_player_profile_detail_sources(player_profile_detail_source_signature())
    batting = player_recent_form_deploy_rows(sources.get("recent_form_batting", pd.DataFrame()), player_id, player_name_key)
    bowling = player_recent_form_deploy_rows(sources.get("recent_form_bowling", pd.DataFrame()), player_id, player_name_key)
    return {
        "batting": [
            {
                "label": safe_record_text(row.get("display_value"), "—"),
                "classes": safe_record_text(row.get("chip_classes"), ""),
            }
            for _, row in batting.head(10).iterrows()
        ],
        "bowling": [
            {
                "label": safe_record_text(row.get("display_value"), "—"),
                "classes": safe_record_text(row.get("chip_classes"), ""),
            }
            for _, row in bowling.head(10).iterrows()
        ],
    }


def player_recent_form_deploy_rows(frame: pd.DataFrame, player_id: str, player_name_key_value: str) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows = filter_recent_form_player_rows(frame, player_id, player_name_key_value)
    if rows.empty:
        return rows
    if "match_date" in rows:
        rows["match_date_sort"] = pd.to_datetime(rows["match_date"], errors="coerce", utc=True)
    else:
        rows["match_date_sort"] = pd.NaT
    if "order_sort" not in rows:
        rows["order_sort"] = 0
    rows["order_sort"] = pd.to_numeric(rows["order_sort"], errors="coerce").fillna(0)
    return rows.sort_values(["match_date_sort", "order_sort"], ascending=[False, True])


def player_recent_batting_rows(
    batting: pd.DataFrame,
    context: pd.DataFrame,
    player_id: str,
    player_name_key_value: str,
) -> pd.DataFrame:
    if batting.empty or context.empty or "match_id" not in batting:
        return pd.DataFrame()
    rows = batting.merge(context, on="match_id", how="inner")
    rows = rows[rows["team_id"].astype(str) == rows["fvcc_team_id"].astype(str)].copy()
    rows = filter_recent_form_player_rows(rows, player_id, player_name_key_value)
    if rows.empty:
        return rows
    dismissal = rows.get("dismissal_type", pd.Series(index=rows.index, dtype=str)).astype(str).str.casefold()
    rows = rows[~dismissal.isin({"did not bat", "absent"})].copy()
    rows["match_date"] = pd.to_datetime(rows.get("match_date"), errors="coerce", utc=True)
    rows["bat_instance_sort"] = pd.to_numeric(rows.get("bat_instance"), errors="coerce").fillna(0)
    rows["bat_order_sort"] = pd.to_numeric(rows.get("bat_order"), errors="coerce").fillna(99)
    return rows.sort_values(["match_date", "bat_instance_sort", "bat_order_sort"], ascending=[False, False, True])


def player_recent_bowling_rows(
    bowling: pd.DataFrame,
    context: pd.DataFrame,
    player_id: str,
    player_name_key_value: str,
) -> pd.DataFrame:
    if bowling.empty or context.empty or "match_id" not in bowling:
        return pd.DataFrame()
    rows = bowling.merge(context, on="match_id", how="inner")
    rows = rows[rows["team_id"].astype(str) == rows["fvcc_team_id"].astype(str)].copy()
    rows = filter_recent_form_player_rows(rows, player_id, player_name_key_value)
    rows = filter_real_scorecard_bowling_rows(rows)
    if rows.empty:
        return rows
    rows["match_date"] = pd.to_datetime(rows.get("match_date"), errors="coerce", utc=True)
    rows["bowl_order_sort"] = pd.to_numeric(rows.get("bowl_order"), errors="coerce").fillna(99)
    return rows.sort_values(["match_date", "bowl_order_sort"], ascending=[False, True])


def filter_real_scorecard_bowling_rows(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return rows.copy()
    output = rows.copy()
    output["_bowling_balls"] = output.apply(scorecard_bowling_balls_bowled, axis=1)
    output["_bowling_balls"] = pd.to_numeric(output["_bowling_balls"], errors="coerce").fillna(0)
    output = output[output["_bowling_balls"].gt(0)].copy()
    return output.drop(columns=["_bowling_balls"], errors="ignore")


def scorecard_bowling_balls_bowled(row: pd.Series) -> int | None:
    for column in ["balls_bowled", "legal_balls"]:
        if column in row:
            value = pd.to_numeric(row.get(column), errors="coerce")
            if pd.notna(value):
                return int(value)
    return cricket_overs_to_balls(row.get("overs_bowled"))


def filter_recent_form_player_rows(rows: pd.DataFrame, player_id: str, player_name_key_value: str) -> pd.DataFrame:
    if rows.empty:
        return rows
    mask = pd.Series(False, index=rows.index)
    if player_id and "canonical_player_id" in rows:
        mask = mask | (rows["canonical_player_id"].astype(str).str.strip() == player_id)
    if player_id and "participant_id" in rows:
        mask = mask | (rows["participant_id"].astype(str).str.strip() == player_id)
    if player_name_key_value:
        for column in ["canonical_player_name", "player_name", "raw_player_name"]:
            if column in rows:
                mask = mask | (rows[column].map(player_name_match_key) == player_name_key_value)
    return rows[mask].copy()


def recent_form_line_html(
    label: str,
    meta: str,
    chips: list[dict[str, object]],
    tone: str,
    empty_copy: str,
) -> str:
    meta_html = f"<small>{html.escape(meta)}</small>" if str(meta).strip() else ""
    if chips:
        chip_html = "".join(
            f'<span class="recent-form-chip {html.escape(tone)} {html.escape(str(chip.get("classes") or ""))}">{html.escape(str(chip.get("label") or "—"))}</span>'
            for chip in chips
        )
    else:
        chip_html = f'<span class="recent-form-empty">{html.escape(empty_copy)}</span>'
    return (
        '<div class="recent-form-line">'
        f'<div class="recent-form-label">{html.escape(label)}{meta_html}</div>'
        f'<div class="recent-form-chip-row">{chip_html}</div>'
        '</div>'
    )


def recent_batting_chip_classes(row: pd.Series) -> str:
    classes = []
    runs = pd.to_numeric(row.get("runs_scored"), errors="coerce")
    dismissal = str(row.get("dismissal_type", "") or "").casefold()
    if pd.notna(runs) and float(runs) >= 50:
        classes.append("hot")
    if "not out" in dismissal:
        classes.append("notout")
    if pd.notna(runs) and float(runs) == 0:
        classes.append("quiet")
    return " ".join(classes)


def recent_bowling_chip_classes(row: pd.Series) -> str:
    classes = []
    wickets = pd.to_numeric(row.get("wickets_taken"), errors="coerce")
    if pd.notna(wickets) and float(wickets) >= 3:
        classes.append("hot")
    if pd.notna(wickets) and float(wickets) == 0:
        classes.append("quiet")
    return " ".join(classes)


def player_profile_is_keeper(career: pd.Series) -> bool:
    return numeric_value(career, "Stumpings") > 0


def format_bat_sr_display(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    return "N/A" if pd.isna(number) else f"{float(number):.1f}%"


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


def profile_record_meta_html(row: pd.Series) -> str:
    if row.empty:
        return ""
    parts = []
    season = row.get("season")
    if pd.notna(season):
        parts.append(season_overview_link_html(season))
    grade = row.get("canonical_grade_label") or canonical_grade_label(row.get("team_name", ""), row.get("grade_name", ""))
    if grade and grade != "—":
        parts.append(html.escape(str(grade)))
    return " - ".join(parts)


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
    label = safe_record_text(value)
    years = [int(year) for year in re.findall(r"(20\d{2}|19\d{2})", label)]
    if not years:
        return 999999
    if "winter" in label.casefold():
        return years[0] * 10
    if "summer" in label.casefold():
        return years[0] * 10 + 5
    return years[0] * 10


def format_int(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    return "—" if pd.isna(number) else f"{int(number):,}"


def format_decimal(value: object) -> str:
    number = pd.to_numeric(value, errors="coerce")
    return "—" if pd.isna(number) else f"{float(number):.2f}"


def format_profile_table(table: pd.DataFrame) -> pd.DataFrame:
    output = table.copy()
    decimal_columns = {"Avg", "Bat Avg", "Bat SR", "Strike Rate", "Bowl Avg", "Econ", "Eco", "Bowl SR", "SR"}
    integer_columns = {"M", "Matches", "Inn", "Innings", "Runs", "BBB Runs", "BBB Balls", "BBB Innings", "BBB Matches", "30s", "50s", "100s", "0s", "4s", "6s", "W", "Wickets", "Maidens", "3WI", "5WI", "Catches", "Stumpings", "RO", "Run Outs", "Dismissals"}
    for column in output.columns:
        if column in decimal_columns:
            output[column] = pd.to_numeric(output[column], errors="coerce").map(lambda value: "—" if pd.isna(value) else f"{float(value):.2f}")
        elif column in integer_columns:
            output[column] = pd.to_numeric(output[column], errors="coerce").map(lambda value: "—" if pd.isna(value) else f"{int(value):,}")
        else:
            output[column] = output[column].map(lambda value: "—" if pd.isna(value) or str(value).strip() == "" else value)
    return output


def format_profile_sortable_table(table: pd.DataFrame) -> pd.DataFrame:
    output = table.copy()
    decimal_columns = {"Avg", "Bat Avg", "Bat SR", "Strike Rate", "Bowl Avg", "Econ", "Eco", "Bowl SR", "SR"}
    integer_columns = {
        "M",
        "Matches",
        "Inn",
        "Innings",
        "Runs",
        "BF",
        "BBB Runs",
        "BBB Balls",
        "BBB Innings",
        "BBB Matches",
        "30s",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
        "Wickets",
        "Maidens",
        "W",
        "3WI",
        "5WI",
        "Catches",
        "Stumpings",
        "RO",
        "Run Outs",
        "Dismissals",
    }
    text_columns = {"Season", "Grade", "Opponent", "Ground", "H/A", "HS", "BBI", "Overs", "Teams", "Grades", "Teams/Grades"}
    for column in output.columns:
        if column in decimal_columns:
            output[column] = pd.to_numeric(output[column], errors="coerce").round(2)
        elif column in integer_columns:
            output[column] = pd.to_numeric(output[column], errors="coerce").round().astype("Int64")
        elif column in text_columns:
            output[column] = output[column].map(lambda value: "—" if pd.isna(value) or str(value).strip() == "" else str(value))
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
        f"""
        <div class="page-kicker">Admin audit</div>
        {configured_club_label_html()}
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
    path = player_identity_path(DUPLICATE_AUDIT_PATH.name)
    if path.exists():
        return pd.read_csv(path, dtype=str).fillna("")
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
            path = player_identity_path(DUPLICATE_AUDIT_PATH.name)
            suggestions.to_csv(path, index=False)
            st.success(f"Saved {path}")


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
    output["Action Note"] = "Manual review only. Add to the active club player_aliases.csv if confirmed."
    with st.container(key="duplicate_suggestions_card"):
        st.dataframe(output, use_container_width=True, hide_index=True, height=520)


def render_context_line(dashboard_data: dict[str, object]) -> None:
    st.markdown(
        f"""
        <div class="context-line">
            <span>{html.escape(str(dashboard_data["context_description"]))}</span>
            <span class="source-note">App created by {html.escape(configured_creator_names())}</span>
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


def render_section_heading(title: str, mobile_title: str | None = None) -> None:
    if mobile_title and mobile_title != title:
        title_html = (
            f"<span class='section-title-desktop'>{html.escape(title)}</span>"
            f"<span class='section-title-mobile'>{html.escape(mobile_title)}</span>"
        )
    else:
        title_html = html.escape(title)
    st.markdown(f"<h2 class='overview-section-title'>{title_html}</h2>", unsafe_allow_html=True)


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
    min_matches_required = improver_min_matches_required(selected_type)
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
        min_matches_required,
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
        min_matches_required,
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
        min_matches_required,
        previous_min_overs=15,
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


def improver_min_matches_required(season_type: object) -> int:
    return 5 if str(season_type or "").casefold() == "winter" else 8


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


def season_bowling_overs_totals(
    season_id: str,
    scope: dict[str, object],
    local_version: float,
    identity_version: float | None,
    column_name: str = "overs",
) -> pd.DataFrame:
    totals = season_metric_totals("bowling", season_id, scope, "bowlingBalls", local_version, identity_version)
    if totals.empty:
        return pd.DataFrame(columns=["player_key", column_name])
    output = totals[["player_key", "bowlingBalls"]].copy()
    output[column_name] = pd.to_numeric(output["bowlingBalls"], errors="coerce").fillna(0) / 6
    return output[["player_key", column_name]]


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
    min_matches_required: int,
    previous_min_overs: float | None = None,
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
    merged = merged[
        (merged["current_matches"] >= min_matches_required)
        & (merged["previous_matches"] >= min_matches_required)
    ].copy()
    if previous_min_overs is not None:
        previous_overs = season_bowling_overs_totals(previous_season_id, scope, local_version, identity_version, "previous_overs")
        merged = merged.merge(previous_overs, on="player_key", how="left")
        merged["previous_overs"] = pd.to_numeric(merged["previous_overs"], errors="coerce").fillna(0)
        merged = merged[merged["previous_overs"] >= previous_min_overs].copy()
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
        "player_id": str(row["player_key"]),
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
    min_matches_required: int,
) -> pd.DataFrame:
    selected_type = season_type_label(current_season.get("name"))
    previous_same_type = previous_season.get("name", "")
    comparison_type = improver_comparison_type(selected_type)
    current_runs = season_metric_totals("batting", current_season_id, scope, "battingAggregate", local_version, identity_version)
    previous_runs = season_metric_totals("batting", previous_season_id, scope, "battingAggregate", local_version, identity_version)
    current_wickets = season_metric_totals("bowling", current_season_id, scope, "bowlingWickets", local_version, identity_version)
    previous_wickets = season_metric_totals("bowling", previous_season_id, scope, "bowlingWickets", local_version, identity_version)
    current_overs = season_bowling_overs_totals(current_season_id, scope, local_version, identity_version, "current_overs")
    previous_overs = season_bowling_overs_totals(previous_season_id, scope, local_version, identity_version, "previous_overs")

    debug = pd.DataFrame({"player_key": sorted(set().union(
        set(current_matches.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(previous_matches.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(current_runs.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(previous_runs.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(current_wickets.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(previous_wickets.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(current_overs.get("player_key", pd.Series(dtype=str)).astype(str)),
        set(previous_overs.get("player_key", pd.Series(dtype=str)).astype(str)),
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
                    "min_matches_required": min_matches_required,
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
    debug = debug.merge(current_overs, on="player_key", how="left")
    debug = debug.merge(previous_overs, on="player_key", how="left")
    for column in [
        "current_matches",
        "previous_matches",
        "current_runs",
        "previous_runs",
        "current_wickets",
        "previous_wickets",
        "current_overs",
        "previous_overs",
    ]:
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
    debug["min_matches_required"] = min_matches_required
    debug["qualifies_matches_rule"] = (
        (debug["current_matches"] >= min_matches_required)
        & (debug["previous_matches"] >= min_matches_required)
    )
    debug["qualifies_runs"] = (
        debug["qualifies_matches_rule"]
        & (debug["runs_improvement"] > 0)
    )
    debug["qualifies_wickets"] = (
        debug["qualifies_matches_rule"]
        & (debug["previous_overs"] >= 15)
        & (debug["wickets_improvement"] > 0)
    )
    debug["qualifies_wickets_overs_rule"] = debug["previous_overs"] >= 15
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
        "min_matches_required",
        "current_matches",
        "previous_matches",
        "current_runs",
        "previous_runs",
        "runs_improvement",
        "runs_improvement_pct",
        "current_wickets",
        "previous_wickets",
        "current_overs",
        "previous_overs",
        "wickets_improvement",
        "wickets_improvement_pct",
        "qualifies_matches_rule",
        "qualifies_runs",
        "qualifies_wickets",
        "qualifies_wickets_overs_rule",
        "reason_if_excluded",
    ]
    return debug[columns].sort_values(["qualifies_runs", "qualifies_wickets", "runs_improvement", "wickets_improvement"], ascending=[False, False, False, False])


def improver_exclusion_reason(row: pd.Series) -> str:
    reasons = []
    min_matches = int(row.get("min_matches_required", 8) or 8)
    if row["current_matches"] < min_matches:
        reasons.append(f"current matches below {min_matches}")
    if row["previous_matches"] < min_matches:
        reasons.append(f"previous matches below {min_matches}")
    if row.get("previous_overs", 0) < 15 and row.get("wickets_improvement", 0) > 0:
        reasons.append("wickets excluded: previous season overs below 15")
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
        "min_matches_required",
        "current_matches",
        "previous_matches",
        "current_runs",
        "previous_runs",
        "runs_improvement",
        "runs_improvement_pct",
        "current_wickets",
        "previous_wickets",
        "current_overs",
        "previous_overs",
        "wickets_improvement",
        "wickets_improvement_pct",
        "qualifies_matches_rule",
        "qualifies_runs",
        "qualifies_wickets",
        "qualifies_wickets_overs_rule",
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
        f'<div class="improver-player">{player_profile_link_html(card.get("player_id"), card["player"])}</div>'
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
                <span class="progress-name">{player_profile_link_html(player_id_from_row(row), row["player_name"])}</span>
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

    render_section_heading("Team/Grade Leaders 👥")
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
    player_id = player_id_from_row(row)
    average_html = average_stat_html(average, average_label)
    return (
        "<div class=\"mini-leader\">"
        "<div class=\"mini-label-row\">"
        f"<span class=\"mini-icon\">{html.escape(icon)}</span>"
        f"<span class=\"mini-label\">{html.escape(label)}</span>"
        "</div>"
        "<div class=\"mini-value-row\">"
        f"<div class=\"mini-player\">{player_profile_link_html(player_id, player_name)}</div>"
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
            f"<strong>{player_profile_link_html(player_id_from_row(row), row['player_name'])}</strong>"
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
                columns=["player_name", "matches", "battingAggregate", "battingAverage", "seasonDetailBatSR", "high_score"],
                rename_map={
                    "player_name": "Player",
                    "matches": "M",
                    "battingAggregate": "Runs",
                    "battingAverage": "Avg",
                    "seasonDetailBatSR": "SR",
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
    render_section_heading("Detailed Stats 📊")
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
    player_name = display_player_name(row["player_name"])
    if "team_name" in row and pd.notna(row.get("team_name")):
        return f"{player_name} ({compact_team_label(row['team_name'])})"
    return player_name


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
    return balls_to_overs_display(value)


def balls_to_overs_display(value: object) -> str | None:
    if pd.isna(value):
        return None
    numeric = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric):
        return None
    balls = int(numeric)
    return f"{balls // 6}.{balls % 6}"


def cricket_overs_to_balls(value: object) -> int | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text or text in {"—", "N/A"}:
        return None
    match = re.match(r"^(\d+)(?:\.(\d+))?$", text)
    if not match:
        numeric = pd.to_numeric(text, errors="coerce")
        return None if pd.isna(numeric) else int(round(float(numeric) * 6))
    overs = int(match.group(1))
    balls = int((match.group(2) or "0")[:1])
    return overs * 6 + min(balls, 5)


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
    output = add_missing_canonical_player_ids(add_display_stat_aliases(df))
    player_profile_ids = (
        output["canonical_player_id"].copy()
        if "canonical_player_id" in output and "player_name" in columns
        else pd.Series([""] * len(output), index=output.index)
    )
    for column in columns:
        if column not in output:
            output[column] = pd.NA

    output = output[columns].rename(columns=rename_map)
    if "Player" in output:
        output["Player"] = [
            player_profile_url(player_id, player)
            for player_id, player in zip(player_profile_ids, output["Player"])
        ]
    if "Team" in output:
        output["Team"] = output["Team"].map(compact_team_label)

    return coerce_display_numbers(output)


def standard_column_config() -> dict[str, object]:
    return {
        "Player": st.column_config.LinkColumn("Player", pinned=True, width="medium", display_text=profile_link_display_pattern()),
        "Scorecard": st.column_config.LinkColumn("Scorecard", width="small", display_text=r"scorecard$"),
        "Team": st.column_config.TextColumn("Team", width="small"),
    }


def numeric_column_config(columns: list[str]) -> dict[str, object]:
    config = standard_column_config()
    integer_columns = {
        "M",
        "Inn",
        "Innings",
        "Matches",
        "Seasons Played",
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
        "Maidens",
        "Runs Against",
        "4W",
        "5W",
        "Balls",
        "30s",
        "3WI",
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
    decimal_columns = {"Avg", "SR", "Bat Avg", "Bat SR", "Bowl Avg", "Eco", "Econ", "Economy", "Bowl SR"}
    for column in columns:
        if column in integer_columns:
            config[column] = st.column_config.NumberColumn(format="%d")
        elif column == "Dot Ball %":
            config[column] = st.column_config.NumberColumn(format="%.1f%%")
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
        "seasonDetailBatSR",
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
                "seasonDetailBatSR": "SR",
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
    components.html(
        season_overview_detail_table_html(
            output,
            category=category,
            table_id=f"season-detail-{category}-{'team' if show_team else 'club'}",
        ),
        height=560,
        scrolling=False,
    )


def season_overview_detail_table_html(table: pd.DataFrame, category: str, table_id: str) -> str:
    safe_table_id = re.sub(r"[^a-zA-Z0-9_-]+", "-", table_id).strip("-") or "season-detail-table"
    columns = table.columns.tolist()
    colgroup = "".join(
        f'<col class="{season_detail_column_class(column)}">'
        for column in columns
    )
    header_html = "".join(
        (
            f'<th class="{season_detail_column_class(column)}" data-column="{index}" '
            f'data-default-dir="{season_detail_default_sort_dir(column)}">'
            f'<button type="button">{html.escape(str(column))}<span class="sort-indicator"></span></button></th>'
        )
        for index, column in enumerate(columns)
    )
    rows = []
    for _, row in table.iterrows():
        cells = []
        for column in columns:
            value = row.get(column)
            display = season_detail_display_value(column, value)
            sort_value, missing = season_detail_sort_value(column, value)
            cells.append(
                f'<td class="{season_detail_column_class(column)}" '
                f'data-sort="{html.escape(sort_value, quote=True)}" data-missing="{int(missing)}">'
                f"{display}</td>"
            )
        rows.append(f"<tr>{''.join(cells)}</tr>")
    empty_state = (
        '<tr><td class="season-detail-empty" colspan="'
        f'{max(len(columns), 1)}">No {html.escape(category)} data available.</td></tr>'
        if table.empty
        else ""
    )
    return f"""
    <style>
      html, body {{
        background: transparent;
        color-scheme: light;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        margin: 0;
        padding: 0;
      }}
      .season-detail-table-wrap {{
        background: #ffffff;
        border: 1px solid #dfe3ee;
        border-radius: 18px;
        box-shadow: 0 12px 28px rgba(23, 27, 77, 0.055);
        height: 548px;
        overflow: auto;
      }}
      table.season-detail-table {{
        border-collapse: separate;
        border-spacing: 0;
        color: #080a3f;
        font-size: 13px;
        min-width: 100%;
        table-layout: fixed;
        width: max-content;
      }}
      .season-detail-table col.season-col-player {{ width: 148px; }}
      .season-detail-table col.season-col-team {{ width: 112px; }}
      .season-detail-table col.season-col-m,
      .season-detail-table col.season-col-mat,
      .season-detail-table col.season-col-inn,
      .season-detail-table col.season-col-mdns,
      .season-detail-table col.season-col-w,
      .season-detail-table col.season-col-ct,
      .season-detail-table col.season-col-st,
      .season-detail-table col.season-col-ro,
      .season-detail-table col.season-col-0s,
      .season-detail-table col.season-col-4s,
      .season-detail-table col.season-col-6s,
      .season-detail-table col.season-col-3wi,
      .season-detail-table col.season-col-5wi,
      .season-detail-table col.season-col-dis {{ width: 48px; }}
      .season-detail-table col.season-col-30s,
      .season-detail-table col.season-col-50s,
      .season-detail-table col.season-col-100s {{ width: 54px; }}
      .season-detail-table col.season-col-runs,
      .season-detail-table col.season-col-hs,
      .season-detail-table col.season-col-eco,
      .season-detail-table col.season-col-bbi,
      .season-detail-table col.season-col-overs,
      .season-detail-table col.season-col-maidens,
      .season-detail-table col.season-col-wickets,
      .season-detail-table col.season-col-catches,
      .season-detail-table col.season-col-run-outs,
      .season-detail-table col.season-col-stumpings {{ width: 66px; }}
      .season-detail-table col.season-col-bat-avg,
      .season-detail-table col.season-col-bat-sr,
      .season-detail-table col.season-col-bowl-avg,
      .season-detail-table col.season-col-bowl-sr,
      .season-detail-table col.season-col-total-dismissals {{ width: 82px; }}
      .season-detail-table th,
      .season-detail-table td {{
        background: #ffffff;
        border-bottom: 1px solid #dfe3ee;
        border-right: 1px solid #dfe3ee;
        box-sizing: border-box;
        line-height: 1.18;
        padding: 8px 9px;
        text-align: right;
        vertical-align: middle;
        white-space: nowrap;
      }}
      .season-detail-table th {{
        background: #fbfbfe;
        color: #687093;
        font-weight: 780;
        position: sticky;
        top: 0;
        z-index: 3;
      }}
      .season-detail-table th button {{
        align-items: center;
        background: transparent;
        border: 0;
        color: inherit;
        cursor: pointer;
        display: inline-flex;
        font: inherit;
        gap: 4px;
        justify-content: flex-end;
        margin: 0;
        padding: 0;
        width: 100%;
      }}
      .season-detail-table th.sorted-asc .sort-indicator::after {{ content: "↑"; }}
      .season-detail-table th.sorted-desc .sort-indicator::after {{ content: "↓"; }}
      .season-detail-table .season-col-player,
      .season-detail-table .season-col-team {{
        left: 0;
        position: sticky;
        text-align: left;
        white-space: normal;
        z-index: 2;
      }}
      .season-detail-table th.season-col-player,
      .season-detail-table th.season-col-team {{
        z-index: 4;
      }}
      .season-detail-table .season-col-player {{
        box-shadow: 4px 0 8px rgba(8, 10, 63, 0.08);
      }}
      .season-detail-table .season-col-player a {{
        color: #0072ce;
        display: block;
        font-weight: 700;
        line-height: 1.13;
        max-width: 100%;
        overflow-wrap: break-word;
        text-decoration: none;
        white-space: normal;
        word-break: normal;
      }}
      .season-detail-table .season-col-player a:hover {{
        color: #5b3df5;
        text-decoration: underline;
      }}
      .season-detail-table tr:nth-child(even) td {{
        background: #fbfcff;
      }}
      .season-detail-table tr:hover td {{
        background: #f7f5ff;
      }}
      .season-detail-empty {{
        color: #7a819f;
        font-weight: 800;
        padding: 22px !important;
        text-align: center !important;
      }}
      @media (max-width: 760px) {{
        .season-detail-table-wrap {{
          border-radius: 14px;
          height: 538px;
        }}
        table.season-detail-table {{
          font-size: 12px;
        }}
        .season-detail-table col.season-col-player {{ width: 110px; }}
        .season-detail-table col.season-col-team {{ width: 92px; }}
        .season-detail-table col.season-col-m,
        .season-detail-table col.season-col-mat,
        .season-detail-table col.season-col-mdns,
        .season-detail-table col.season-col-w,
        .season-detail-table col.season-col-ct,
        .season-detail-table col.season-col-st,
        .season-detail-table col.season-col-ro,
        .season-detail-table col.season-col-0s,
        .season-detail-table col.season-col-4s,
        .season-detail-table col.season-col-6s,
        .season-detail-table col.season-col-3wi,
        .season-detail-table col.season-col-5wi {{ width: 42px; }}
        .season-detail-table col.season-col-dis {{ width: 46px; }}
        .season-detail-table col.season-col-inn,
        .season-detail-table col.season-col-30s,
        .season-detail-table col.season-col-50s {{ width: 46px; }}
        .season-detail-table col.season-col-100s {{ width: 50px; }}
        .season-detail-table col.season-col-runs,
        .season-detail-table col.season-col-hs,
        .season-detail-table col.season-col-eco,
        .season-detail-table col.season-col-bbi {{ width: 56px; }}
        .season-detail-table col.season-col-overs,
        .season-detail-table col.season-col-maidens,
        .season-detail-table col.season-col-wickets,
        .season-detail-table col.season-col-catches,
        .season-detail-table col.season-col-run-outs,
        .season-detail-table col.season-col-stumpings {{ width: 58px; }}
        .season-detail-table col.season-col-total-dismissals {{ width: 64px; }}
        .season-detail-table col.season-col-bat-avg,
        .season-detail-table col.season-col-bat-sr,
        .season-detail-table col.season-col-bowl-avg,
        .season-detail-table col.season-col-bowl-sr {{ width: 72px; }}
        .season-detail-table th,
        .season-detail-table td {{
          padding: 7px 6px;
        }}
        .season-detail-table .season-col-player a {{
          line-height: 1.12;
        }}
      }}
    </style>
    <div class="season-detail-table-wrap">
      <table id="{html.escape(safe_table_id, quote=True)}" class="season-detail-table">
        <colgroup>{colgroup}</colgroup>
        <thead><tr>{header_html}</tr></thead>
        <tbody>{empty_state if table.empty else ''.join(rows)}</tbody>
      </table>
    </div>
    <script>
      (() => {{
        const table = document.getElementById({safe_table_id!r});
        if (!table) return;
        const tbody = table.querySelector("tbody");
        const headers = Array.from(table.querySelectorAll("th"));
        const textValue = (row, index) => row.children[index].textContent.trim().toLocaleLowerCase();
        const sortValue = (row, index) => {{
          const cell = row.children[index];
          if (!cell || cell.dataset.missing === "1") return null;
          const raw = cell.dataset.sort || "";
          const numeric = Number(raw);
          return Number.isFinite(numeric) && raw.trim() !== "" ? numeric : raw.toLocaleLowerCase();
        }};
        const compare = (a, b, index, dir) => {{
          const av = sortValue(a, index);
          const bv = sortValue(b, index);
          if (av === null && bv === null) return textValue(a, 0).localeCompare(textValue(b, 0));
          if (av === null) return 1;
          if (bv === null) return -1;
          let result = 0;
          if (typeof av === "number" && typeof bv === "number") {{
            result = av === bv ? 0 : av < bv ? -1 : 1;
          }} else {{
            result = String(av).localeCompare(String(bv), undefined, {{ numeric: true, sensitivity: "base" }});
          }}
          if (result === 0) result = textValue(a, 0).localeCompare(textValue(b, 0));
          return dir === "asc" ? result : -result;
        }};
        const sortHeader = (header, index) => {{
          const current = header.dataset.sortDir;
          const dir = current ? (current === "asc" ? "desc" : "asc") : (header.dataset.defaultDir || "desc");
          headers.forEach(item => {{
            item.classList.remove("sorted-asc", "sorted-desc");
            delete item.dataset.sortDir;
          }});
          header.dataset.sortDir = dir;
          header.classList.add(`sorted-${{dir}}`);
          Array.from(tbody.querySelectorAll("tr"))
            .sort((a, b) => compare(a, b, index, dir))
            .forEach(row => tbody.appendChild(row));
        }};
        const resolveInternalHref = (href) => {{
          let base = document.referrer || window.location.href;
          try {{
            if (window.parent && window.parent.location && window.parent.location.href) base = window.parent.location.href;
          }} catch (error) {{}}
          return new URL(href, base).toString();
        }};
        table.addEventListener("click", event => {{
          const link = event.target.closest('a[data-season-detail-link="1"]');
          if (!link) return;
          const href = resolveInternalHref(link.getAttribute("href") || "");
          if (!href) return;
          try {{
            window.parent.location.href = href;
            event.preventDefault();
          }} catch (error) {{
            link.setAttribute("href", href);
            link.setAttribute("target", "_blank");
            link.setAttribute("rel", "noopener noreferrer");
          }}
        }});
        headers.forEach((header, index) => header.addEventListener("click", () => sortHeader(header, index)));
      }})();
    </script>
    """


def season_detail_column_class(column: object) -> str:
    text = re.sub(r"[^a-zA-Z0-9]+", "-", str(column).strip().casefold()).strip("-")
    return f"season-col-{text or 'column'}"


def season_detail_default_sort_dir(column: object) -> str:
    return "asc" if str(column) in {"Player", "Team"} else "desc"


def season_detail_display_value(column: str, value: object) -> str:
    if column == "Player":
        return season_detail_player_link_cell(value)
    if pd.isna(value) or str(value).strip() == "":
        return "N/A"
    if column == "Bat SR":
        numeric = pd.to_numeric(value, errors="coerce")
        return "N/A" if pd.isna(numeric) else f"{float(numeric):.1f}%"
    if column in {"Bat Avg", "Bowl Avg", "Bowl SR", "Eco"}:
        numeric = pd.to_numeric(value, errors="coerce")
        return "N/A" if pd.isna(numeric) else f"{float(numeric):.2f}"
    if column == "Overs":
        balls = cricket_overs_to_balls(value)
        return "N/A" if balls is None else balls_to_overs_display(balls) or "N/A"
    if column in {
        "M",
        "Mat",
        "Inn",
        "Runs",
        "30s",
        "50s",
        "100s",
        "0s",
        "4s",
        "6s",
        "Maidens",
        "Mdns",
        "Wickets",
        "W",
        "3WI",
        "5WI",
        "Catches",
        "Ct",
        "Stumpings",
        "St",
        "Run Outs",
        "RO",
        "Total Dismissals",
        "Dis",
    }:
        numeric = pd.to_numeric(value, errors="coerce")
        return "N/A" if pd.isna(numeric) else f"{int(numeric):,}"
    text = str(value).strip()
    return html.escape(text if text and text not in {"—", "None", "nan"} else "N/A")


def season_detail_player_link_cell(value: object) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return "N/A"
    text = str(value).strip()
    label = link_display_label(text)
    if text.startswith("?"):
        return (
            f'<a href="{html.escape(text, quote=True)}" data-season-detail-link="1" target="_top" '
            f'title="Open Player Profile for {html.escape(label or text, quote=True)}">'
            f"{html.escape(label or text)}</a>"
        )
    return html.escape(label or text)


def season_detail_sort_value(column: str, value: object) -> tuple[str, bool]:
    if pd.isna(value) or str(value).strip() in {"", "—", "N/A", "None", "nan"}:
        return "", True
    if column in {"Player", "Team"}:
        return link_display_label(value).casefold(), False
    if column == "HS":
        runs, not_out = parse_batting_score(value)
        if runs is None:
            return "", True
        return str(runs * 10 + int(not_out)), False
    if column == "BBI":
        wickets, runs = parse_bowling_figures(value)
        if wickets is None or runs is None:
            return "", True
        return str(wickets * 10000 - runs), False
    if column == "Overs":
        balls = cricket_overs_to_balls(value)
        return ("" if balls is None else str(balls), balls is None)
    numeric = pd.to_numeric(value, errors="coerce")
    if not pd.isna(numeric):
        return str(float(numeric)), False
    return str(value).casefold(), False


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
    if category == "bowling" and "Overs" in output:
        output["Overs"] = ordered_overs_values(output["Overs"])
    if "BBI" in output:
        output["BBI"] = ordered_bbi_values(output["BBI"])
    if "HS" in output:
        output["HS"] = ordered_high_score_values(output["HS"])

    return output


def get_batting_display_df(df: pd.DataFrame) -> pd.DataFrame:
    output = prepare_curated_display_frame(
        df,
        [
            "player_name",
            "team_name",
            "matches",
            "battingInnings",
            "battingAggregate",
            "battingAverage",
            "seasonDetailBatSR",
            "high_score",
            "seasonDetail30s",
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
            "Inn",
            "Runs",
            "Bat Avg",
            "Bat SR",
            "HS",
            "30s",
            "50s",
            "100s",
            "0s",
            "4s",
            "6s",
        ],
    )
    return apply_batting_detail_fallbacks(output)


def apply_batting_detail_fallbacks(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    if "30s" in output:
        thirties = pd.to_numeric(output["30s"], errors="coerce").fillna(0)
        if "HS" in output:
            hs_runs = output["HS"].map(lambda value: parse_batting_score(value)[0])
            hs_fallback = pd.to_numeric(hs_runs, errors="coerce").between(30, 49, inclusive="both") & (thirties <= 0)
            thirties = thirties.mask(hs_fallback, 1)
        output["30s"] = thirties.astype(int)
    return output


def get_bowling_display_df(df: pd.DataFrame) -> pd.DataFrame:
    output = prepare_curated_display_frame(
        df,
        [
            "player_name",
            "team_name",
            "matches",
            "overs_bowled_display",
            "bowlingMaidens",
            "bowlingWickets",
            "bowlingAverage",
            "bowlingStrikeRate",
            "bowlingEconomyRate",
            "bowlingBestInnings",
            "seasonDetail3WIs",
            "seasonDetail5WIs",
        ],
        [
            "Player",
            "Team",
            "M",
            "Overs",
            "Maidens",
            "Wickets",
            "Bowl Avg",
            "Bowl SR",
            "Eco",
            "BBI",
            "3WI",
            "5WI",
        ],
    )
    return output.rename(columns={"M": "Mat", "Maidens": "Mdns", "Wickets": "W"})


def get_fielding_display_df(df: pd.DataFrame) -> pd.DataFrame:
    output = prepare_curated_display_frame(
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
    return output.rename(
        columns={"Catches": "Ct", "Stumpings": "St", "Run Outs": "RO", "Total Dismissals": "Dis"}
    )


def prepare_curated_display_frame(
    df: pd.DataFrame,
    columns: list[str],
    display_columns: list[str],
) -> pd.DataFrame:
    output = add_display_stat_aliases(df)
    player_profile_ids = (
        output["canonical_player_id"].copy()
        if "canonical_player_id" in output and "player_name" in columns
        else pd.Series([""] * len(output), index=output.index)
    )
    available_columns = [column for column in columns if column in output.columns]
    output = output[available_columns].rename(columns=pretty_column_name_map())
    output = select_display_columns(output, display_columns)
    if "Player" in output:
        output["Player"] = [
            player_profile_url(player_id, player)
            for player_id, player in zip(player_profile_ids, output["Player"])
        ]
    return coerce_display_numbers(output)


def select_display_columns(df: pd.DataFrame, desired_columns: list[str]) -> pd.DataFrame:
    return df[[column for column in desired_columns if column in df.columns]]


def coerce_display_numbers(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    text_columns = {"Player", "Team", "HS", "BBI", "Overs", "Scorecard"}
    for column in output.columns:
        if column not in text_columns:
            numeric_values = pd.to_numeric(output[column], errors="coerce")
            if numeric_values.notna().any():
                output[column] = numeric_values
    return output


def ordered_bbi_values(values: pd.Series) -> pd.Series:
    labels = values.map(lambda value: "—" if pd.isna(value) or str(value).strip() == "" else str(value))
    unique_values = labels.drop_duplicates().tolist()
    categories = sorted(
        unique_values,
        key=bbi_category_sort_key,
    )
    return pd.Series(
        pd.Categorical(labels, categories=categories, ordered=True),
        index=values.index,
    )


def parse_bowling_figures(value: object) -> tuple[int | None, int | None]:
    if pd.isna(value):
        return None, None
    parsed = pd.Series([str(value)]).str.extract(r"(\d+)\s*[-/]\s*(\d+)").iloc[0]
    wickets = pd.to_numeric(parsed[0], errors="coerce")
    runs = pd.to_numeric(parsed[1], errors="coerce")
    if pd.isna(wickets) or pd.isna(runs):
        return None, None
    return int(wickets), int(runs)


def bbi_sort_key(value: str) -> tuple[int, int]:
    wickets, runs = parse_bowling_figures(value)
    if wickets is None or runs is None:
        return (0, -999)
    return (wickets, -runs)


def bbi_category_sort_key(value: object) -> tuple[int, int, int, str]:
    wickets, runs = parse_bowling_figures(value)
    if wickets is None or runs is None:
        return (1, 0, 0, str(value))
    return (0, -wickets, runs, str(value))


def pretty_column_name_map() -> dict[str, str]:
    return {
        "player_name": "Player",
        "team_name": "Team",
        "grade_name": "Grade",
        "matches": "M",
        "innings": "Innings",
        "battingInnings": "Inn",
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
        "seasonDetailBatSR": "Bat SR",
        "seasonDetailBatDotBallPct": "Dot Ball %",
        "seasonDetail30s": "30s",
        "high_score": "HS",
        "battingHighScore": "Raw HS",
        "bowlingWickets": "Wickets",
        "overs_bowled_display": "Overs",
        "oversBowled": "Overs",
        "bowlingOvers": "Overs",
        "overs": "Overs",
        "bowlingAverage": "Bowl Avg",
        "bowlingEconomyRate": "Eco",
        "bowlingStrikeRate": "Bowl SR",
        "seasonDetailDotBallPct": "Dot Ball %",
        "bowlingBestInnings": "BBI",
        "bowlingBalls": "Balls",
        "bowlingRuns": "Runs",
        "bowlingMaidens": "Maidens",
        "bowling4Wickets": "4W",
        "bowling5WIs": "5W",
        "seasonDetail3WIs": "3WI",
        "seasonDetail5WIs": "5WI",
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
