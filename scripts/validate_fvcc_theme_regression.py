#!/usr/bin/env python3
"""Validate FVCC production colours without changing GRDCC or recent layouts."""

from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def generated_theme(club_id: str) -> str:
    os.environ["CLUB_ID"] = club_id
    from src.ui.theme import active_club_theme_css

    return active_club_theme_css()


def git_unchanged(*paths: str) -> bool:
    return subprocess.run(
        ["git", "diff", "--quiet", "HEAD", "--", *paths],
        cwd=ROOT,
        check=False,
    ).returncode == 0


def main() -> int:
    fvcc_css = generated_theme("fvcc")
    grdcc_css = generated_theme("georges-river-district")
    layout = (ROOT / "src/ui/layout.py").read_text()
    checks = [
        ("fvcc_purple_removed", "#6D4DFF" not in fvcc_css and "#5B4BEB" not in fvcc_css, "FVCC generated theme contains no purple brand tokens."),
        ("fvcc_burgundy_primary", "--club-primary: #A31952;" in fvcc_css, "Production burgundy primary restored."),
        ("fvcc_navy_sidebar", "--club-sidebar-start: #28485F;" in fvcc_css and "--club-sidebar-bg: #1E3748;" in fvcc_css, "Production navy sidebar gradient restored."),
        ("fvcc_gold_accent", "--club-accent: #D4A83A;" in fvcc_css, "Production gold supporting accent restored."),
        ("fvcc_background", "--club-bg: #F6F8FB;" in fvcc_css, "Production background restored."),
        ("fvcc_active_nav", "--club-sidebar-active: #A31952;" in fvcc_css and "linear-gradient(135deg, var(--club-sidebar-active), var(--club-secondary))" in fvcc_css, "Active navigation remains burgundy/navy."),
        ("grdcc_primary_unchanged", "--club-primary: #0B3F9F;" in grdcc_css, "GRDCC primary remains blue."),
        ("grdcc_sidebar_unchanged", "--club-sidebar-start: #0B3F9F;" in grdcc_css and "--club-sidebar-bg: #082A66;" in grdcc_css, "GRDCC sidebar tokens unchanged."),
        ("club_configs_unchanged", git_unchanged("clubs/fvcc/club_config.yaml", "clubs/georges-river-district/club_config.yaml"), "Deployment config files untouched."),
        ("fvcc_data_unchanged", git_unchanged("clubs/fvcc/data/processed/hall_of_fame", "clubs/fvcc/data/raw"), "FVCC source and stat data unchanged."),
        ("premiership_scroll_preserved", 'data-desktop-visible-rows="6"' in layout and 'data-mobile-visible-rows="5"' in layout, "Premiership scroll contract retained."),
        ("hof_mobile_scroll_preserved", "hof-mobile-five-row-scroll" in layout, "HOF mobile scroll contract retained."),
        ("season_round_panels_preserved", 'data-layout="horizontal-grade-panels"' in layout, "Season by Round horizontal panels retained."),
        ("fvcc_latest_three_preserved", 'season_count = 3 if club_id == "fvcc" else 2' in layout, "FVCC latest-three active-player logic retained."),
    ]
    output = ROOT / "clubs/fvcc/data/processed/validation/hof/fvcc_theme_regression_validation.csv"
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
