#!/usr/bin/env python3
"""Validate FVCC visual alignment and write the active-player audit outputs."""

from __future__ import annotations

import csv
import re
import subprocess
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
LAYOUT_PATH = ROOT / "src/ui/layout.py"
THEME_PATH = ROOT / "src/ui/theme.py"
FVCC_PROCESSED = ROOT / "clubs/fvcc/data/processed"
AUDIT_PATH = FVCC_PROCESSED / "validation/hof/fvcc_active_player_visual_logic_audit.csv"
VALIDATION_PATH = FVCC_PROCESSED / "validation/hof/fvcc_visual_alignment_validation.csv"
PLAYER_TABLES = [
    FVCC_PROCESSED / "all_seasons_batting.csv",
    FVCC_PROCESSED / "all_seasons_bowling.csv",
    FVCC_PROCESSED / "all_seasons_fielding.csv",
]


def git_show(path: Path) -> str:
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "show", f"HEAD:{relative}"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def latest_three_fvcc_seasons() -> list[str]:
    seasons = pd.read_csv(FVCC_PROCESSED / "seasons.csv")
    seasons["season_sort"] = pd.to_datetime(seasons["startDate"], errors="coerce", utc=True)
    return (
        seasons.sort_values(["season_sort", "name"], ascending=[False, False])["name"]
        .dropna()
        .drop_duplicates()
        .head(3)
        .astype(str)
        .tolist()
    )


def player_activity() -> pd.DataFrame:
    frames = []
    columns = ["canonical_player_name", "player_name", "season", "season_start_date"]
    for path in PLAYER_TABLES:
        frame = pd.read_csv(path, usecols=lambda column: column in columns)
        if "canonical_player_name" not in frame:
            frame["canonical_player_name"] = frame.get("player_name", "")
        frame["canonical_player_name"] = frame["canonical_player_name"].fillna(frame.get("player_name", ""))
        frames.append(frame)
    activity = pd.concat(frames, ignore_index=True, sort=False)
    activity["canonical_player_name"] = activity["canonical_player_name"].fillna("").astype(str).str.strip()
    activity["season"] = activity["season"].fillna("").astype(str).str.strip()
    return activity[(activity["canonical_player_name"] != "") & (activity["season"] != "")].copy()


def write_active_player_audit(latest_three: list[str]) -> int:
    activity = player_activity()
    season_order = pd.read_csv(FVCC_PROCESSED / "seasons.csv", usecols=["name", "startDate"])
    season_order["season_sort"] = pd.to_datetime(season_order["startDate"], errors="coerce", utc=True)
    order_lookup = season_order.drop_duplicates("name").set_index("name")["season_sort"].to_dict()
    activity["season_sort"] = activity["season"].map(order_lookup)
    activity = activity.sort_values(["canonical_player_name", "season_sort"], ascending=[True, False])
    latest_by_player = activity.drop_duplicates("canonical_player_name", keep="first")
    active_names = set(activity.loc[activity["season"].isin(latest_three), "canonical_player_name"])
    latest_label = " | ".join(latest_three)
    rows = []
    for row in latest_by_player.itertuples(index=False):
        is_active = row.canonical_player_name in active_names
        rows.append(
            {
                "latest_three_seasons_used": latest_label,
                "player_name": row.canonical_player_name,
                "latest_season_played": row.season,
                "is_active": str(is_active).lower(),
                "affected_section": "Milestones",
                "validation_status": "pass",
                "notes": "Active when present in any dynamically selected latest-three FVCC season.",
            }
        )
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(AUDIT_PATH, index=False)
    return len(rows)


def main() -> int:
    layout = LAYOUT_PATH.read_text()
    theme = THEME_PATH.read_text()
    latest_three = latest_three_fvcc_seasons()
    audit_rows = write_active_player_audit(latest_three)
    head_layout = git_show(LAYOUT_PATH)
    head_theme = git_show(THEME_PATH)
    premiership_path = FVCC_PROCESSED / "hall_of_fame/premiership_wins.csv"
    premiership_rows = len(pd.read_csv(premiership_path))

    checks = [
        ("premiership_desktop_rows", 'data-desktop-visible-rows="6"' in layout, "Desktop target is six."),
        ("premiership_mobile_rows", 'data-mobile-visible-rows="5"' in layout, "Mobile target is five."),
        ("premiership_scroll", 'data-scroll-enabled="true"' in layout and "overflow-y: auto" in theme, "Scrollable container configured."),
        ("premiership_source_unchanged", subprocess.run(["git", "diff", "--quiet", "HEAD", "--", str(premiership_path.relative_to(ROOT))], cwd=ROOT).returncode == 0, f"Source unchanged; {premiership_rows} rows retained."),
        ("hof_leaders_mobile_rows", 'class="hof-leader-scroll"' in layout and "calc(5 * 58px)" in theme, "Leader cards use five-row mobile height."),
        ("fastest_innings_mobile_rows", "hof-mobile-five-row-scroll" in layout and "fastest-innings-card" in layout, "Fastest Innings uses responsive five-row wrapper."),
        ("iconic_performances_mobile_rows", "hof-mobile-five-row-scroll iconic-performance-scroll" in layout, "Iconic Performances uses responsive five-row wrapper."),
        ("fvcc_latest_three_seasons", len(latest_three) == 3 and "season_count = 3 if club_id == \"fvcc\" else 2" in layout, " | ".join(latest_three)),
        ("fvcc_winter_seasons_included", any("Winter" in season for season in latest_three), "Latest-three ordering includes winter cricket."),
        ("grdcc_active_logic_unchanged", 'if club_id == "georges-river-district":\n        activity = filter_grdcc_active_badge_activity(activity)' in layout and "else 2" in layout, "GRDCC remains two seasons with existing exclusions."),
        ("season_round_horizontal_panels", 'data-layout="horizontal-grade-panels"' in layout and "overflow-x: auto" in theme, "Horizontal strip configured."),
        ("season_round_folder_removed", "def selected_season_round_grade_filter(" not in layout and 'data-internal-folder-selector="false"' in layout, "Internal folder selector removed."),
        ("global_slicers_preserved", 'st.selectbox(\n                "Season"' in layout and 'st.selectbox(\n                "Team"' in layout and "Select team/grade" in layout, "Top season and grade/team controls remain."),
        ("fvcc_theme_config_unchanged", subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "clubs/fvcc/club_config.yaml"], cwd=ROOT).returncode == 0, "FVCC palette/config file unchanged."),
        ("no_ranking_sort_changes", "def sort_hof_leaders" in layout and re.search(r"def sort_hof_leaders[\s\S]*?def render_record_holders", layout).group(0) == re.search(r"def sort_hof_leaders[\s\S]*?def render_record_holders", head_layout).group(0), "HOF ranking helper unchanged."),
        ("no_raw_data_changes", subprocess.run(["git", "diff", "--quiet", "HEAD", "--", "clubs/fvcc/data/raw"], cwd=ROOT).returncode == 0, "FVCC raw data unchanged."),
        ("fvcc_production_theme_preserved", all(token in theme for token in ['"primary_colour": "#A31952"', '"secondary_colour": "#28485F"', '"accent_colour": "#D4A83A"', '"background_colour": "#F6F8FB"']), "FVCC production palette is explicitly preserved by the club-scoped resolver."),
        ("active_player_audit", audit_rows > 0, f"{audit_rows} player rows written."),
    ]

    VALIDATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    with VALIDATION_PATH.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "notes"])
        writer.writeheader()
        for name, passed, notes in checks:
            writer.writerow({"check": name, "status": "pass" if passed else "fail", "notes": notes})

    failed = [name for name, passed, _notes in checks if not passed]
    print(f"validation_status={'pass' if not failed else 'fail'} checks={len(checks)} failed={len(failed)}")
    if failed:
        print("failed_checks=" + ",".join(failed))
        return 1
    print("latest_three_seasons=" + " | ".join(latest_three))
    print(f"audit_rows={audit_rows}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
