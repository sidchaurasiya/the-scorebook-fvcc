from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.config.club_config import get_active_club_id, load_club_config


@dataclass(frozen=True)
class ClubTemplateConfig:
    club_id: str
    display_name: str
    short_name: str
    slug: str
    data_dir: str
    logo_path: str | None
    primary_colour: str | None
    secondary_colour: str | None
    accent_colour: str | None
    background_colour: str | None
    link_colour: str | None
    link_hover_colour: str | None
    nav_active_colour: str | None
    source_systems: list[str] = field(default_factory=list)
    playhq_config: dict[str, Any] = field(default_factory=dict)
    has_historical_excel: bool = False
    has_annual_report_overrides: bool = False
    enable_match_proxy: bool = False
    enable_exact_name_nonoverlap_merge: bool = False
    enable_grade_opponent_normalisation: bool = False
    streamlit_entrypoint: str | None = None
    ga4_club_name: str | None = None


def get_club_template_config(club_id: str | None = None) -> ClubTemplateConfig:
    raw = load_club_config(club_id or get_active_club_id())
    club = raw.get("club", {})
    branding = raw.get("branding", {})
    data = raw.get("data", {})
    features = raw.get("features", {})
    active_id = str(club.get("club_id") or club_id or get_active_club_id()).strip()
    playhq_config = dict(raw.get("playhq_config") or raw.get("playhq") or {})
    for key in ("playhq_club_id", "playhq_org_id", "playcricket_club_id"):
        if key in club and key not in playhq_config:
            playhq_config[key] = club.get(key)
    return ClubTemplateConfig(
        club_id=active_id,
        display_name=str(club.get("display_name") or club.get("name") or active_id),
        short_name=str(club.get("short_name") or active_id),
        slug=str(club.get("slug") or active_id),
        data_dir=str(data.get("root_dir") or Path("clubs") / active_id / "data"),
        logo_path=branding.get("logo_path"),
        primary_colour=branding.get("primary_colour"),
        secondary_colour=branding.get("secondary_colour"),
        accent_colour=branding.get("accent_colour"),
        background_colour=branding.get("background_colour"),
        link_colour=branding.get("link_colour"),
        link_hover_colour=branding.get("link_hover_colour"),
        nav_active_colour=branding.get("nav_active_colour"),
        source_systems=list(data.get("source_systems") or []),
        playhq_config=playhq_config,
        has_historical_excel=bool(features.get("has_historical_excel", False)),
        has_annual_report_overrides=bool(features.get("has_annual_report_overrides", False)),
        enable_match_proxy=bool(features.get("enable_match_proxy", False)),
        enable_exact_name_nonoverlap_merge=bool(features.get("enable_exact_name_nonoverlap_merge", False)),
        enable_grade_opponent_normalisation=bool(features.get("enable_grade_opponent_normalisation", False)),
        streamlit_entrypoint=club.get("streamlit_entrypoint"),
        ga4_club_name=club.get("ga4_club_name"),
    )
