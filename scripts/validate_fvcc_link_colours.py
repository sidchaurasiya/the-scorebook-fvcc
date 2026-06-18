#!/usr/bin/env python3
"""Validate FVCC navy player/season link styling without changing GRDCC."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def git_unchanged(*paths: str) -> bool:
    return subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *paths],
        cwd=ROOT,
        check=False,
    ).returncode == 0


def generated_styles(club_id: str) -> tuple[str, str, str]:
    os.environ["CLUB_ID"] = club_id
    from src.ui.layout import hof_sortable_table_html, season_overview_detail_table_html
    from src.ui.theme import active_club_theme_css

    table = pd.DataFrame(
        {
            "Player": ['?page=player-profile&player_id=test#Test Player'],
            "Season": ['?page=season-overview&season=Summer%202024%2F25#Summer 2024/25'],
        }
    )
    return (
        active_club_theme_css(),
        hof_sortable_table_html(table, "link-colour-validation"),
        season_overview_detail_table_html(table, "batting", "link-colour-validation"),
    )


def main() -> int:
    fvcc_theme, fvcc_hof, fvcc_season = generated_styles("fvcc")
    grdcc_theme, grdcc_hof, grdcc_season = generated_styles("georges-river-district")
    layout = (ROOT / "src/ui/layout.py").read_text()
    theme = (ROOT / "src/ui/theme.py").read_text()
    checks = [
        ("premiership_season_navy", "--club-link: #28485F;" in fvcc_theme and ".premiership-season" in fvcc_theme, "Premiership season links resolve to FVCC navy."),
        ("hof_player_links_navy", "--hof-link: #28485F;" in fvcc_hof, "HOF player links resolve to FVCC navy."),
        ("hof_player_hover_navy", "--hof-player-link-hover: #1E3748;" in fvcc_hof, "HOF player hover resolves to dark navy."),
        ("hof_season_links_navy", "--hof-link: #28485F;" in fvcc_hof and "hof-col-latest-season" in fvcc_hof, "HOF season columns share the navy link token."),
        ("season_stats_links_navy", "--season-detail-link: #28485F;" in fvcc_season, "Season Overview stats links resolve to FVCC navy."),
        ("season_stats_hover_navy", "--season-detail-link-hover: #1E3748;" in fvcc_season, "Season Overview stats hover resolves to dark navy."),
        ("player_profile_links_navy", ".player-profile-link" in fvcc_theme and "color: var(--club-link) !important" in fvcc_theme, "Player Profile links use the navy content-link token."),
        ("milestone_links_navy", ".block-container:has(.near-milestones-page) a.player-profile-link" in fvcc_theme and "color: var(--club-link) !important" in fvcc_theme, "Milestones player links use the navy content-link token with page-scoped specificity."),
        ("no_purple_fvcc_links", all(value not in (fvcc_theme + fvcc_hof + fvcc_season).upper() for value in ["#6D4DFF", "#5B4BEB", "#4B37D8"]), "Generated FVCC link styles contain no purple."),
        ("no_burgundy_player_links", "--club-link: #A31952;" not in fvcc_theme and "--hof-link: #A31952;" not in fvcc_hof, "Player/season link tokens are not burgundy."),
        ("active_nav_burgundy_preserved", "--club-sidebar-active: #A31952;" in fvcc_theme, "FVCC active navigation remains burgundy."),
        ("grdcc_theme_unchanged", "--club-link: #0B3F9F;" in grdcc_theme and "--club-link-hover: #79C8EE;" in grdcc_theme, "GRDCC page link tokens unchanged."),
        ("grdcc_tables_unchanged", "--hof-link: #0B3F9F;" in grdcc_hof and "--season-detail-link: #0B3F9F;" in grdcc_season, "GRDCC table link tokens unchanged."),
        ("fvcc_data_unchanged", git_unchanged("clubs/fvcc/data/processed/hall_of_fame", "clubs/fvcc/data/raw"), "FVCC data/stat sources unchanged."),
        ("layout_scroll_preserved", 'data-desktop-visible-rows="6"' in layout and "hof-mobile-five-row-scroll" in layout, "Recent FVCC scroll contracts retained."),
    ]
    output = ROOT / "clubs/fvcc/data/processed/validation/hof/fvcc_link_colour_validation.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "notes"])
        writer.writeheader()
        for name, passed, notes in checks:
            writer.writerow({"check": name, "status": "pass" if passed else "fail", "notes": notes})
    failed = [name for name, passed, _notes in checks if not passed]
    print(f"validation_status={'pass' if not failed else 'fail'} checks={len(checks)} failed={len(failed)}")
    if failed:
        print("failed_checks=" + ",".join(failed))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
