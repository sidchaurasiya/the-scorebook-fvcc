#!/usr/bin/env python3
"""Validate GWHCC premium theme, scroll, and performance contracts."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "clubs/glen-waverley-hawks/data/processed/validation/gwhcc_premium_theme_and_performance_validation.csv"
PERFORMANCE_PROFILE = ROOT / "data/processed/validation/scorebook_page_performance_profile.csv"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def status_row(check_name: str, ok: bool, notes: str) -> dict[str, str]:
    return {
        "check_name": check_name,
        "validation_status": "pass" if ok else "fail",
        "notes": notes,
    }


def function_source(source: str, start: str, end: str) -> str:
    try:
        return source[source.index(start):source.index(end)]
    except ValueError:
        return ""


def load_config() -> dict:
    with (ROOT / "clubs/glen-waverley-hawks/club_config.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def main() -> int:
    config = load_config()
    branding = config.get("branding", {})
    layout = read_text(ROOT / "src/ui/layout.py")
    theme = read_text(ROOT / "src/ui/theme.py")
    gwhcc_config = read_text(ROOT / "clubs/glen-waverley-hawks/club_config.yaml")
    fvcc_config = read_text(ROOT / "clubs/fvcc/club_config.yaml")
    grdcc_config = read_text(ROOT / "clubs/georges-river-district/club_config.yaml")

    ranked_block = function_source(layout, "def render_ranked_record_card(", "def milestone_record_row_html")
    iconic_block = function_source(layout, "def render_performance_card(", "def sort_hof_leaders")
    milestone_upcoming_block = function_source(layout, "def milestone_progress_group_html(", "def milestone_group_rule")
    milestone_achieved_block = function_source(layout, "def render_achieved_milestones_view(", "def achievement_card_html")
    sidebar_block = function_source(theme, 'section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked)', 'section[data-testid="stSidebar"] .side-nav-item,')

    performance_ok = False
    performance_notes = f"{PERFORMANCE_PROFILE} missing"
    if PERFORMANCE_PROFILE.exists():
        try:
            profile = pd.read_csv(PERFORMANCE_PROFILE)
            gwhcc_rows = profile[profile.get("club_id", pd.Series(dtype=str)).astype(str).eq("glen-waverley-hawks")]
            required = {
                "HOF data build",
                "Season Overview data build",
                "Player Profile index build",
                "Player Profile selected-player build",
                "Milestone Upcoming build",
                "Milestone Achieved build",
                "Milestone Exclusive Club build",
            }
            found = set(gwhcc_rows.get("page_or_component", pd.Series(dtype=str)).astype(str))
            performance_ok = required.issubset(found)
            performance_notes = f"GWHCC profile rows={len(gwhcc_rows)}; found={sorted(found)}"
        except Exception as exc:  # pragma: no cover - defensive validator guard
            performance_notes = f"Could not read performance profile: {exc}"

    rows = [
        status_row(
            "gwhcc_config_resolves",
            config.get("club", {}).get("club_id") == "glen-waverley-hawks",
            "GWHCC config loads and resolves the expected club id.",
        ),
        status_row(
            "gwhcc_readable_gold_value_token",
            branding.get("value_colour") in {"#A87500", "#B88600", "#C28A00"}
            and branding.get("value_colour") != branding.get("primary_colour")
            and "--club-value" in theme,
            "Readable dark-gold value token exists and does not reuse bright logo gold.",
        ),
        status_row(
            "selected_sidebar_premium_active_style",
            "rgba(255,255,255,0.20)" in sidebar_block
            and "var(--club-sidebar-active)" in sidebar_block
            and "border: 1px solid rgba(var(--club-primary-rgb), 0.58)" in sidebar_block,
            "Selected sidebar state uses layered glass/gold active styling.",
        ),
        status_row(
            "hof_player_names_and_values_use_readable_tokens",
            "color: var(--club-value) !important" in theme
            and ".premiership-player-row .performance-value" in theme
            and ".record-value" in theme,
            "HOF values use readable club value token; player links stay on club link token.",
        ),
        status_row(
            "premiership_result_text_uses_brown",
            ".premiership-result" in theme and "color: var(--club-secondary)" in theme,
            "Premiership result text resolves to GWHCC dark brown.",
        ),
        status_row(
            "premiership_season_text_uses_dark_gold",
            ".premiership-season" in theme and "color: var(--club-value)" in theme,
            "Premiership season text resolves to the dark gold value token.",
        ),
        status_row(
            "hof_top_10_controls_absent",
            "Show top 10" not in layout,
            "Legacy HOF top-10 control wording is absent.",
        ),
        status_row(
            "milestone_top_10_controls_absent",
            "Show top 10" not in milestone_upcoming_block and "Show top 10" not in milestone_achieved_block,
            "Milestone page does not expose top-10 controls.",
        ),
        status_row(
            "hof_sections_scrollable",
            "active_club_uses_premium_hof_scroll" in ranked_block
            and "hof-responsive-record-scroll" in ranked_block
            and "hof-responsive-record-scroll iconic-performance-scroll" in iconic_block
            and "premiership-card-scroll premiership-wins-scroll" in layout
            and "premiership-card-scroll premiership-player-scroll" in layout
            and "hof-leader-scroll" in layout,
            "Premiership, leaders, iconic performances, and fastest innings use scroll containers.",
        ),
        status_row(
            "milestone_long_sections_scrollable",
            "milestone-progress-list" in milestone_upcoming_block
            and "milestone-mini-scroll" in layout
            and "milestone-achievement-scroll" in milestone_achieved_block
            and "milestone-member-list" in layout,
            "Upcoming, achieved, HOF watch, and exclusive milestone sections use scroll containers.",
        ),
        status_row(
            "gwhcc_page_performance_profile_exists",
            performance_ok,
            performance_notes,
        ),
        status_row(
            "grdcc_fvcc_theme_tokens_not_modified_accidentally",
            "#A31952" in fvcc_config
            and "#28485F" in fvcc_config
            and "#D4A83A" in fvcc_config
            and "georges-river-district" in grdcc_config
            and "value_colour: \"#A87500\"" in gwhcc_config,
            "FVCC/GRDCC config tokens remain separate; readable-gold token is GWHCC-scoped.",
        ),
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUTPUT, index=False)
    failed = frame[frame["validation_status"] != "pass"]
    print(f"validation_status={'pass' if failed.empty else 'fail'} checks={len(frame)} failed={len(failed)}")
    print(f"output={OUTPUT}")
    if not failed.empty:
        print(failed.to_string(index=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
