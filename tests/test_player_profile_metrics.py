from __future__ import annotations

import math
import re
from pathlib import Path

import pandas as pd

from scripts.build_player_profile_insight_exports import build_dimension_bbb_batting
from scripts.audit_player_profile_qa import parse_bbi


ROOT = Path(__file__).resolve().parents[1]
PLAYER_PROFILE_DIR = ROOT / "data" / "processed" / "player_profile"
HOF_DIR = ROOT / "data" / "processed" / "hall_of_fame"
SEASON_OVERVIEW_DIR = ROOT / "data" / "processed" / "season_overview"


def read_csv(path: Path) -> pd.DataFrame:
    assert path.exists(), f"Missing required test fixture: {path}"
    return pd.read_csv(path)


def assert_close(left: object, right: float, tolerance: float = 0.02) -> None:
    left_num = pd.to_numeric(left, errors="coerce")
    assert pd.notna(left_num), f"Expected numeric value, got {left!r}"
    assert abs(float(left_num) - right) <= tolerance


def count_thirties(scores: list[int]) -> int:
    return sum(1 for score in scores if 30 <= score <= 49)


def test_batting_average_uses_outs() -> None:
    performance = read_csv(PLAYER_PROFILE_DIR / "performance_breakdown_by_dimension.csv")
    batting = performance[performance["discipline"].astype(str).eq("Batting")].copy()
    batting["runs"] = pd.to_numeric(batting["runs"], errors="coerce").fillna(0)
    batting["outs"] = pd.to_numeric(batting["outs"], errors="coerce").fillna(0)
    with_outs = batting[batting["outs"] > 0]
    assert not with_outs.empty
    for _, row in with_outs.iterrows():
        assert_close(row["bat_avg"], float(row["runs"]) / float(row["outs"]))
    not_out_only = batting[(batting["outs"] == 0) & (batting["runs"] > 0)]
    if not not_out_only.empty:
        assert not_out_only["bat_avg"].isna().all()


def test_bbb_strike_rate_uses_bbb_runs_and_balls() -> None:
    performance = read_csv(PLAYER_PROFILE_DIR / "performance_breakdown_by_dimension.csv")
    batting = performance[performance["discipline"].astype(str).eq("Batting")].copy()
    batting["bbb_runs"] = pd.to_numeric(batting["bbb_runs"], errors="coerce")
    batting["bbb_balls_faced"] = pd.to_numeric(batting["bbb_balls_faced"], errors="coerce")
    covered = batting[batting["bbb_balls_faced"] > 0]
    assert not covered.empty
    for _, row in covered.iterrows():
        assert_close(row["strike_rate"], float(row["bbb_runs"]) * 100 / float(row["bbb_balls_faced"]))

    career = read_csv(HOF_DIR / "player_bbb_batting_rates.csv")
    career = career[pd.to_numeric(career["bbb_balls_faced"], errors="coerce") > 0]
    assert not career.empty
    for _, row in career.iterrows():
        assert_close(row["bat_sr"], float(row["bbb_runs"]) * 100 / float(row["bbb_balls_faced"]))


def test_missing_bbb_is_na_not_zero() -> None:
    performance = read_csv(PLAYER_PROFILE_DIR / "performance_breakdown_by_dimension.csv")
    batting = performance[performance["discipline"].astype(str).eq("Batting")].copy()
    batting["innings"] = pd.to_numeric(batting["innings"], errors="coerce").fillna(0)
    batting["bbb_balls_faced"] = pd.to_numeric(batting["bbb_balls_faced"], errors="coerce")
    missing_bbb = batting[(batting["innings"] > 0) & (batting["bbb_balls_faced"].isna() | batting["bbb_balls_faced"].le(0))]
    assert not missing_bbb.empty
    assert missing_bbb["strike_rate"].isna().all()


def sample_bbb_batting_inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    batting = pd.DataFrame(
        [
            {
                "canonical_player_id": "jimmy_sharma",
                "canonical_player_name": "Jimmy Sharma",
                "display_player_name": "Jimmy Sharma",
                "Scope": "Career",
                "match_id": "m1",
                "innings_id": "i1",
                "participant_id": "p1",
                "runs_numeric": 20,
                "balls_numeric": 10,
                "out": 1,
            },
            {
                "canonical_player_id": "jimmy_sharma",
                "canonical_player_name": "Jimmy Sharma",
                "display_player_name": "Jimmy Sharma",
                "Scope": "Career",
                "match_id": "m2",
                "innings_id": "i2",
                "participant_id": "p1",
                "runs_numeric": 15,
                "balls_numeric": 5,
                "out": 0,
            },
            {
                "canonical_player_id": "jimmy_sharma",
                "canonical_player_name": "Jimmy Sharma",
                "display_player_name": "Jimmy Sharma",
                "Scope": "Career",
                "match_id": "m3",
                "innings_id": "i3",
                "participant_id": "p1",
                "runs_numeric": 30,
                "balls_numeric": 12,
                "out": 1,
            },
        ]
    )
    balls = pd.DataFrame(
        [
            *[
                {
                    "match_id": "m1",
                    "innings_id": "i1",
                    "striker_participant_id": "p1",
                    "wides": 0,
                    "runs_bat_numeric": 2,
                    "striker_runs_scored": 20,
                    "striker_balls_faced": 10,
                }
                for _ in range(10)
            ],
            *[
                {
                    "match_id": "m2",
                    "innings_id": "i2",
                    "striker_participant_id": "p1",
                    "wides": 0,
                    "runs_bat_numeric": value,
                    "striker_runs_scored": 15,
                    "striker_balls_faced": 5,
                }
                for value in [4, 4, 3, 2, 2]
            ],
            {
                "match_id": "m2",
                "innings_id": "i2",
                "striker_participant_id": "p1",
                "wides": 1,
                "runs_bat_numeric": 0,
                "striker_runs_scored": 15,
                "striker_balls_faced": 5,
            },
        ]
    )
    return batting, balls


def test_bbb_balls_per_dismissal_uses_bbb_innings_only() -> None:
    batting, balls = sample_bbb_batting_inputs()
    grouped = build_dimension_bbb_batting(batting, balls, "Scope")
    assert len(grouped) == 1
    row = grouped.iloc[0]
    assert float(row["bbb_runs"]) == 35
    assert float(row["bbb_balls_faced"]) == 15
    assert float(row["bbb_dismissals"]) == 1
    assert float(row["bbb_batting_innings"]) == 2
    assert float(row["bbb_matches"]) == 2
    assert_close(float(row["bbb_balls_faced"]) / float(row["bbb_dismissals"]), 15.0)


def test_bbb_not_out_innings_add_balls_without_dismissal() -> None:
    batting, balls = sample_bbb_batting_inputs()
    grouped = build_dimension_bbb_batting(batting, balls, "Scope")
    row = grouped.iloc[0]
    assert float(row["bbb_balls_faced"]) == 15
    assert float(row["bbb_dismissals"]) == 1


def test_non_bbb_innings_are_excluded_from_balls_per_dismissal() -> None:
    batting, balls = sample_bbb_batting_inputs()
    grouped = build_dimension_bbb_batting(batting, balls, "Scope")
    row = grouped.iloc[0]
    # The third innings is a scorecard-only dismissal. It must not increase BBB dismissals.
    assert float(row["bbb_dismissals"]) == 1


def test_no_bbb_coverage_returns_empty_bbb_summary() -> None:
    batting, _balls = sample_bbb_batting_inputs()
    grouped = build_dimension_bbb_batting(batting, pd.DataFrame(), "Scope")
    assert grouped.empty


def test_thirties_are_30_to_49_inclusive() -> None:
    assert count_thirties([29, 30, 31, 49, 50, 100, 0]) == 3
    milestones = read_csv(SEASON_OVERVIEW_DIR / "scorecard_batting_milestones_by_scope.csv")
    milestones["innings"] = pd.to_numeric(milestones["innings"], errors="coerce").fillna(0)
    milestones["thirties"] = pd.to_numeric(milestones["thirties"], errors="coerce").fillna(0)
    assert milestones["thirties"].ge(0).all()
    assert (milestones["thirties"] <= milestones["innings"]).all()


def test_three_wicket_innings_excludes_five_wicket_hauls() -> None:
    bowling = read_csv(SEASON_OVERVIEW_DIR / "scorecard_bowling_milestones_by_scope.csv")
    bowling["three_wicket_innings"] = pd.to_numeric(bowling["three_wicket_innings"], errors="coerce").fillna(0)
    bowling["five_wicket_innings"] = pd.to_numeric(bowling["five_wicket_innings"], errors="coerce").fillna(0)
    assert bowling["three_wicket_innings"].ge(0).all()
    assert bowling["five_wicket_innings"].ge(0).all()


def test_bbi_parses_wickets_then_runs() -> None:
    values = ["5/17", "5-21", "4/3", "3-9", "2/1"]
    parsed = sorted(values, key=lambda value: parse_bbi(value), reverse=True)
    assert parsed[:2] == ["5-21", "5/17"]
    best = sorted(values, key=lambda value: (parse_bbi(value)[0] or -1, -(parse_bbi(value)[1] or math.inf)), reverse=True)
    assert best[0] == "5/17"


def test_bowling_phase_respects_match_type() -> None:
    phase = read_csv(PLAYER_PROFILE_DIR / "bowling_phase_summary.csv")
    assert set(phase["phase_model"].dropna().unique()).issubset({"T20", "One Day", "Two Day"})
    allowed = {
        "T20": {"Opening", "Middle", "Death"},
        "One Day": {"Opening", "Middle", "Death"},
        "Two Day": {"New Ball", "Older Ball"},
    }
    for _, row in phase.iterrows():
        assert row["phase"] in allowed[row["phase_model"]]


def test_known_aliases_resolve_to_one_canonical_profile() -> None:
    aliases = read_csv(ROOT / "data" / "player_aliases.csv")
    for name in ["Faraz Khan", "Gopi Krishna", "Ravi Chowdary", "Predheesh Valayil Sivanandan", "Sandeep Gill"]:
        rows = aliases[
            aliases["canonical_player_name"].astype(str).str.casefold().eq(name.casefold())
            | aliases["alias_name"].astype(str).str.casefold().eq(name.casefold())
            | aliases["raw_player_name"].astype(str).str.casefold().eq(name.casefold())
        ]
        if not rows.empty:
            assert rows["canonical_player_id"].nunique() == 1
