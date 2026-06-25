#!/usr/bin/env python3
"""Validate shared FVCC/GRDCC percentage metrics and Fastest Innings scrolling."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ui import layout  # noqa: E402


CLUBS = ("fvcc", "georges-river-district")


def check(rows: list[dict[str, object]], name: str, passed: bool, details: str = "") -> None:
    rows.append({"check": name, "passed": bool(passed), "details": details})


def source_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def validate_club(club_id: str) -> pd.DataFrame:
    os.environ["CLUB_ID"] = club_id
    rows: list[dict[str, object]] = []
    layout_source = source_text("src/ui/layout.py")
    theme_source = source_text("src/ui/theme.py")

    check(rows, "fastest innings desktop target 5", 'data-desktop-visible-rows="5"' in layout_source)
    check(rows, "fastest innings mobile target 5", 'data-mobile-visible-rows="5"' in layout_source)
    check(rows, "fastest innings scroll enabled", 'data-scroll-enabled="true"' in layout_source and "overflow-y: auto" in theme_source)
    fastest_block = layout_source[layout_source.index("def render_ranked_record_card"):layout_source.index("def milestone_record_row_html")]
    check(rows, "fastest innings no top 10 control", "Show top 10" not in fastest_block)

    check(rows, "extras formula", layout.calculate_extras_pct(2, 1, 60) == 5.0)
    check(rows, "maiden formula", layout.calculate_maiden_pct(2, 8) == 25.0)
    check(rows, "duck formula", layout.calculate_duck_pct(2, 12, 2) == 20.0)
    check(rows, "zero denominators blank", all(value is None for value in (
        layout.calculate_extras_pct(1, 1, 0),
        layout.calculate_maiden_pct(1, 0),
        layout.calculate_duck_pct(1, 1, 1),
    )))

    bowling_source = pd.DataFrame([{
        "player_name": "Sample Player",
        "team_name": "Sample Team",
        "matches": 1,
        "overs_bowled_display": "10.0",
        "bowlingBalls": 60,
        "bowlingMaidens": 2,
        "bowlingWickets": 3,
        "bowlingAverage": 10.0,
        "bowlingStrikeRate": 20.0,
        "bowlingEconomyRate": 3.0,
        "bowlingBestInnings": "3-30",
        "seasonDetail3WIs": 1,
        "seasonDetail5WIs": 0,
        "bowlingNoBalls": 1,
        "bowlingWides": 2,
    }])
    display = layout.get_bowling_display_df(bowling_source)
    check(rows, "season overview extras present", "Extras %" in display.columns)
    check(rows, "season overview extras after wides", list(display.columns)[-2:] == ["Wides", "Extras %"])
    check(rows, "season overview extras numeric", pd.api.types.is_numeric_dtype(display["Extras %"]))
    check(rows, "season overview extras value", float(display["Extras %"].iloc[0]) == 5.0)

    batting = pd.DataFrame([{
        "season": "Winter 2026", "canonical_player_id": "sample", "battingAggregate": 100,
        "battingInnings": 12, "battingNotOuts": 2, "battingBallsFaced": 100,
        "battingFours": 10, "battingSixes": 1, "batting0s": 2,
    }])
    bowling = pd.DataFrame([{
        "season": "Winter 2026", "canonical_player_id": "sample", "bowlingWickets": 4,
        "bowlingRuns": 80, "bowlingBalls": 120, "bowlingMaidens": 4,
        "bowlingWides": 3, "bowlingNoBalls": 1, "bowlingWicketsUnassisted": 2,
    }])
    batting_peer = layout.aggregate_peer_batting(batting, ("Winter 2026",)).iloc[0]
    bowling_peer = layout.aggregate_peer_bowling(bowling, ("Winter 2026",)).iloc[0]
    check(rows, "peer duck percentage", float(batting_peer["duck_pct"]) == 20.0)
    check(rows, "peer maiden percentage", float(bowling_peer["maiden_pct"]) == 20.0)
    check(rows, "peer extras percentage", float(bowling_peer["extras_pct"]) == (4 * 100 / 120))
    check(rows, "old peer metrics removed", not any(label in layout_source for label in (
        "Balls per Extra", "Overs per Maiden", "Innings per Duck",
    )))
    check(rows, "new peer metrics present", all(label in layout_source for label in (
        '"Extras %"', '"Maiden %"', '"Duck %"',
    )))
    check(rows, "career extras after 5wi", '"3WI", "5WI", "Extras %"' in layout_source)
    check(rows, "percentage display numeric", 'NumberColumn(column, width="small", format="%.1f%%")' in layout_source)
    breakdown = pd.DataFrame({"Season": ["Winter 2026"], "extras_pct": [pd.NA]})
    profile_view = {"season_table": pd.DataFrame({"Season": ["Winter 2026"], "Extras %": [5.0]})}
    breakdown_values = layout.profile_breakdown_extras_pct(breakdown, "Season", profile_view)
    check(rows, "career breakdown aggregate fallback", float(breakdown_values.iloc[0]) == 5.0)

    processed = ROOT / "clubs" / club_id / "data" / "processed"
    actual_bowling = pd.read_csv(processed / "all_seasons_bowling.csv", low_memory=False)
    actual_batting = pd.read_csv(processed / "all_seasons_batting.csv", low_memory=False)
    eligible_bowling = actual_bowling[pd.to_numeric(actual_bowling.get("bowlingBalls"), errors="coerce").fillna(0).gt(0)].copy()
    actual_display = layout.get_bowling_display_df(eligible_bowling.head(20))
    check(rows, "actual season bowling extras numeric", "Extras %" in actual_display and pd.api.types.is_numeric_dtype(actual_display["Extras %"]))
    sample = eligible_bowling.iloc[0]
    expected_extras = layout.calculate_extras_pct(sample.get("bowlingNoBalls"), sample.get("bowlingWides"), sample.get("bowlingBalls"))
    actual_extras = float(actual_display["Extras %"].iloc[0])
    check(rows, "actual season bowling formula", expected_extras is not None and abs(actual_extras - expected_extras) < 1e-9)

    peer_bowling = layout.aggregate_peer_bowling(actual_bowling, tuple(actual_bowling["season"].dropna().astype(str).unique()))
    peer_batting = layout.aggregate_peer_batting(actual_batting, tuple(actual_batting["season"].dropna().astype(str).unique()))
    check(rows, "actual peer extras numeric", "extras_pct" in peer_bowling and pd.api.types.is_numeric_dtype(peer_bowling["extras_pct"]))
    check(rows, "actual peer maiden numeric", "maiden_pct" in peer_bowling and pd.api.types.is_numeric_dtype(peer_bowling["maiden_pct"]))
    check(rows, "actual peer duck numeric", "duck_pct" in peer_batting and pd.api.types.is_numeric_dtype(peer_batting["duck_pct"]))

    changed = subprocess.run(
        ["git", "diff", "--name-only"], cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout.splitlines()
    check(rows, "raw data unchanged", not any(path.startswith("data/raw/") for path in changed))
    check(rows, "annual report sources unchanged", not any("annual_report" in path for path in changed))
    check(rows, "club theme configs unchanged", not any(path.endswith("club_config.yaml") for path in changed))

    return pd.DataFrame(rows)


def main() -> int:
    passed = 0
    total = 0
    for club_id in CLUBS:
        results = validate_club(club_id)
        output = ROOT / "clubs" / club_id / "data" / "processed" / "validation" / f"{club_id.replace('-', '_')}_bowling_peer_metrics_validation.csv"
        output.parent.mkdir(parents=True, exist_ok=True)
        results.to_csv(output, index=False)
        club_passed = int(results["passed"].sum())
        passed += club_passed
        total += len(results)
        print(f"{club_id}: {club_passed}/{len(results)} checks passed -> {output}")
    print(f"Cross-club validation: {passed}/{total} checks passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
