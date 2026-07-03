#!/usr/bin/env python3
"""Validate FVCC Player Profile sections use refreshed app-facing data."""

from __future__ import annotations

import math
import os
import sys
from pathlib import Path

import pandas as pd

os.environ.setdefault("CLUB_ID", "fvcc")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.audit_fvcc_player_profile_full_propagation import (  # noqa: E402
    TARGET_PLAYER,
    TARGET_SEASON,
    audit_rows,
)
from src.ui.layout import (  # noqa: E402
    active_wickets_chart_colour,
    build_player_profile_view,
    build_player_recent_form,
    get_player_peer_comparison,
    load_player_profile_index,
    metadata_mtime,
    player_aliases_mtime,
    player_peer_grade_scope,
    player_profile_view_signature,
)
from src.utils.player_identity import get_player_profile_data  # noqa: E402


OUTPUT_PATH = Path(
    "clubs/fvcc/data/processed/validation/fvcc_player_profile_full_propagation_validation.csv"
)


def _num(value: object) -> float:
    number = pd.to_numeric(value, errors="coerce")
    return float(number) if pd.notna(number) and math.isfinite(float(number)) else float("nan")


def _check(name: str, passed: bool, actual: object, expected: object, notes: str = "") -> dict[str, object]:
    return {
        "check_name": name,
        "status": "pass" if passed else "fail",
        "actual": actual,
        "expected": expected,
        "notes": notes,
    }


def _load_target_view() -> tuple[pd.Series, dict[str, pd.DataFrame], dict[str, list[dict[str, object]]], dict[str, list[dict[str, object]]]]:
    club_id = "fvcc"
    local_version = metadata_mtime()
    identity_version = player_aliases_mtime()
    index = load_player_profile_index(club_id, local_version, identity_version, "2026-07-profile-index-v2")
    rows = index[index["name"].astype(str).str.casefold().eq(TARGET_PLAYER.casefold())]
    if rows.empty:
        raise RuntimeError(f"{TARGET_PLAYER} missing from FVCC Player Profile index")
    player_id = str(rows.iloc[0]["id"])
    profile = get_player_profile_data(player_id, local_version, identity_version, club_id=club_id)
    view = build_player_profile_view(profile, player_profile_view_signature())
    career = view["career"].iloc[0]
    recent = build_player_recent_form(career)
    seasons = tuple(sorted(view["season_table"]["Season"].dropna().astype(str).unique()))
    peers = get_player_peer_comparison(
        str(career.get("canonical_player_id", "")),
        seasons,
        player_peer_grade_scope(view),
        local_version,
        identity_version,
        club_id,
    )
    return career, view, recent, peers


def build_checks() -> list[dict[str, object]]:
    career, view, recent, peers = _load_target_view()
    season_table = view["season_table"].copy()
    season_row = season_table[season_table["Season"].astype(str).eq(TARGET_SEASON)]
    checks: list[dict[str, object]] = []

    if season_row.empty:
        checks.append(_check("siddhanth_winter_2026_row_present", False, "missing", "present"))
        winter_matches = winter_wickets = float("nan")
    else:
        winter_matches = _num(season_row.iloc[0].get("Matches"))
        winter_wickets = _num(season_row.iloc[0].get("Wickets"))
        checks.append(_check("siddhanth_winter_2026_row_present", True, "present", "present"))

    checks.extend(
        [
            _check("career_breakdown_winter_2026_matches", winter_matches == 6, winter_matches, 6),
            _check("career_breakdown_winter_2026_wickets", winter_wickets == 10, winter_wickets, 10),
            _check(
                "recent_form_latest_bowling_present",
                bool(recent.get("bowling")) and str(recent["bowling"][0].get("label")) == "2/50",
                " | ".join(str(item.get("label")) for item in recent.get("bowling", [])[:5]),
                "first bowling chip 2/50",
            ),
            _check(
                "recent_form_batting_present",
                bool(recent.get("batting")),
                " | ".join(str(item.get("label")) for item in recent.get("batting", [])[:5]),
                "at least one batting chip",
            ),
            _check(
                "competition_grade_winter_updated",
                not view.get("grade_table", pd.DataFrame()).empty
                and pd.to_numeric(
                    view["grade_table"]
                    .loc[
                        view["grade_table"]["Grade"].astype(str).str.contains("Winter", case=False, na=False),
                        "Wickets",
                    ],
                    errors="coerce",
                ).fillna(0).max()
                >= 10,
                "winter grade max wickets >= 10",
                ">=10 wickets in Winter grade row",
            ),
            _check(
                "player_dna_batting_position_source_present",
                not view.get("batting_position", pd.DataFrame()).empty,
                len(view.get("batting_position", pd.DataFrame())),
                ">0 rows",
            ),
            _check(
                "player_dna_bowling_phase_source_present",
                not view.get("bowling_phase", pd.DataFrame()).empty,
                len(view.get("bowling_phase", pd.DataFrame())),
                ">0 rows",
            ),
            _check(
                "player_dna_dismissal_source_present",
                not view.get("dismissal_fingerprint", pd.DataFrame()).empty,
                len(view.get("dismissal_fingerprint", pd.DataFrame())),
                ">0 rows",
            ),
            _check(
                "player_vs_peers_source_present",
                bool(peers.get("batting")) and bool(peers.get("bowling")),
                f"batting={len(peers.get('batting', []))} bowling={len(peers.get('bowling', []))}",
                "batting and bowling peer rows",
            ),
            _check(
                "season_trends_winter_2026_matches_current",
                winter_matches == 6,
                winter_matches,
                6,
                "Season Trends uses the same season table as Career Breakdown",
            ),
            _check(
                "wickets_by_season_uses_fvcc_burgundy",
                active_wickets_chart_colour().casefold() == "#a31952",
                active_wickets_chart_colour(),
                "#A31952",
            ),
        ]
    )

    audit = audit_rows()
    checks.append(
        _check(
            "audit_layers_present",
            all(row["status"] == "present" for row in audit),
            "; ".join(f"{row['layer']}={row['status']}" for row in audit),
            "all app-facing PP audit layers present",
        )
    )

    stale = season_table[
        (season_table["Season"].astype(str).eq(TARGET_SEASON))
        & (
            (pd.to_numeric(season_table.get("Matches"), errors="coerce").fillna(0) == 5)
            | (pd.to_numeric(season_table.get("Wickets"), errors="coerce").fillna(0) == 8)
        )
    ]
    checks.append(_check("no_stale_winter_2026_5_match_or_8_wicket_row", stale.empty, len(stale), 0))
    return checks


def main() -> int:
    checks = build_checks()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(checks).to_csv(OUTPUT_PATH, index=False)
    failed = [check for check in checks if check["status"] != "pass"]
    print(f"validation_status={'pass' if not failed else 'fail'} checks={len(checks)} failed={len(failed)}")
    if failed:
        print("failed_checks=" + ",".join(str(check["check_name"]) for check in failed))
    print(f"wrote {OUTPUT_PATH}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
