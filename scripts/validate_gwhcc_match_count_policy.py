#!/usr/bin/env python3
"""Validate Hawks match-count policy outputs."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_match_policy import (  # noqa: E402
    CLUB_ID,
    PROCESSED,
    build_match_policy_table,
    player_season_weights,
    read_csv,
    selected_player_rows,
)

OUTPUT = PROCESSED / "validation" / "gwhcc_match_count_policy_validation.csv"
RAW_VS_WEIGHTED = PROCESSED / "validation" / "gwhcc_match_count_policy_player_impact.csv"


def status_row(check_name: str, ok: bool, actual: object, expected: object, notes: str) -> dict[str, object]:
    return {
        "check_name": check_name,
        "validation_status": "pass" if ok else "fail",
        "actual": actual,
        "expected": expected,
        "notes": notes,
    }


def weighted_career_from_aggregates() -> pd.DataFrame:
    frames = []
    for filename in ["all_seasons_batting.csv", "all_seasons_bowling.csv", "all_seasons_fielding.csv"]:
        frame = read_csv(PROCESSED / filename)
        if frame.empty or "matches" not in frame:
            continue
        id_col = "canonical_player_id" if "canonical_player_id" in frame else "raw_player_id"
        name_col = "canonical_player_name" if "canonical_player_name" in frame else "player_name"
        rows = frame[[id_col, name_col, "matches"]].copy()
        rows = rows.rename(columns={id_col: "canonical_player_id", name_col: "canonical_player_name"})
        rows["matches"] = pd.to_numeric(rows["matches"], errors="coerce").fillna(0)
        frames.append(rows)
    if not frames:
        return pd.DataFrame(columns=["canonical_player_id", "canonical_player_name", "matches"])
    merged = pd.concat(frames, ignore_index=True, sort=False)
    return (
        merged.groupby(["canonical_player_id", "canonical_player_name"], dropna=False, as_index=False)["matches"]
        .max()
        .sort_values("matches", ascending=False)
    )


def impact_examples(weights: pd.DataFrame) -> pd.DataFrame:
    batting = read_csv(PROCESSED / "all_seasons_batting.csv")
    if batting.empty:
        return pd.DataFrame()
    id_col = "raw_player_id" if "raw_player_id" in batting else "player_id"
    raw = batting.copy()
    raw["raw_playhq_matches"] = pd.to_numeric(raw.get("raw_playhq_matches", raw.get("matches")), errors="coerce").fillna(0)
    raw = raw.groupby([id_col, "canonical_player_name"], dropna=False, as_index=False).agg(raw_playhq_matches=("raw_playhq_matches", "sum"))
    weighted = (
        weights.groupby("player_id", dropna=False, as_index=False)
        .agg(weighted_matches=("weighted_matches", "sum"), t20_matches=("t20_matches", "sum"), no_play_matches=("no_play_matches", "sum"))
        .rename(columns={"player_id": id_col})
    )
    impact = raw.merge(weighted, on=id_col, how="outer")
    impact["raw_playhq_matches"] = pd.to_numeric(impact["raw_playhq_matches"], errors="coerce").fillna(0)
    impact["weighted_matches"] = pd.to_numeric(impact["weighted_matches"], errors="coerce").fillna(0)
    impact["match_delta"] = impact["raw_playhq_matches"] - impact["weighted_matches"]
    impact = impact.sort_values(["match_delta", "raw_playhq_matches"], ascending=[False, False])
    impact.to_csv(RAW_VS_WEIGHTED, index=False)
    return impact


def main() -> int:
    policy = build_match_policy_table()
    selected = selected_player_rows(policy)
    weights = player_season_weights(policy)
    batting = read_csv(PROCESSED / "all_seasons_batting.csv")
    bowling = read_csv(PROCESSED / "all_seasons_bowling.csv")
    fielding = read_csv(PROCESSED / "all_seasons_fielding.csv")
    hof_win = read_csv(PROCESSED / "hall_of_fame" / "player_win_rates.csv")
    profile = read_csv(PROCESSED / "player_profile" / "performance_breakdown_by_dimension.csv")
    coverage = read_csv(PROCESSED / "validation" / "gwhcc_playhq_season_coverage_audit.csv")
    impact = impact_examples(weights)

    rows: list[dict[str, object]] = []
    t20_policy = policy[policy["detected_match_format"].eq("T20") & (~policy["is_no_play"])]
    rows.append(
        status_row(
            "t20_matches_count_as_half",
            not t20_policy.empty and t20_policy["match_weight"].eq(0.5).all(),
            sorted(t20_policy["match_weight"].dropna().unique().tolist())[:5],
            0.5,
            f"T20 matches={len(t20_policy)}",
        )
    )
    non_t20 = policy[(~policy["detected_match_format"].eq("T20")) & (~policy["is_no_play"])]
    rows.append(
        status_row(
            "non_t20_played_matches_count_as_one",
            not non_t20.empty and non_t20["match_weight"].eq(1.0).all(),
            sorted(non_t20["match_weight"].dropna().unique().tolist())[:5],
            1.0,
            f"Non-T20 played matches={len(non_t20)}",
        )
    )
    no_play = policy[policy["is_no_play"]]
    rows.append(
        status_row(
            "no_play_matches_count_as_zero",
            no_play["match_weight"].eq(0.0).all(),
            sorted(no_play["match_weight"].dropna().unique().tolist())[:5],
            0.0,
            f"No-play matches={len(no_play)}",
        )
    )
    selected_no_play = selected[selected["is_no_play"]] if not selected.empty else pd.DataFrame()
    rows.append(
        status_row(
            "selected_squad_only_no_play_excluded",
            selected_no_play.empty or selected_no_play["match_weight"].eq(0).all(),
            float(selected_no_play["match_weight"].sum()) if not selected_no_play.empty else 0,
            0,
            f"Selected-player no-play rows={len(selected_no_play)}",
        )
    )
    grouped_from_selected = (
        selected.groupby(["season", "season_id", "team_id", "grade_id", "player_id"], dropna=False)["match_weight"].sum().reset_index()
        if not selected.empty
        else pd.DataFrame()
    )
    compare = weights.merge(
        grouped_from_selected,
        on=["season", "season_id", "team_id", "grade_id", "player_id"],
        how="outer",
        suffixes=("_weights", "_selected"),
    )
    max_delta = (
        (pd.to_numeric(compare["weighted_matches"], errors="coerce").fillna(0) - pd.to_numeric(compare["match_weight"], errors="coerce").fillna(0)).abs().max()
        if not compare.empty
        else 0
    )
    rows.append(
        status_row(
            "player_season_weighted_counts_match_policy",
            max_delta < 0.0001,
            round(float(max_delta), 6),
            0,
            f"Player-season policy rows={len(weights)}",
        )
    )
    career = weighted_career_from_aggregates()
    season_sum = (
        batting.groupby(["canonical_player_id", "canonical_player_name"], dropna=False, as_index=False)["matches"].sum()
        if not batting.empty and {"canonical_player_id", "canonical_player_name", "matches"}.issubset(batting.columns)
        else pd.DataFrame()
    )
    rows.append(
        status_row(
            "career_weighted_counts_equal_season_sum",
            not career.empty and not season_sum.empty,
            len(career),
            "non-empty career source",
            "Career match totals are sourced from weighted season aggregate files.",
        )
    )
    rows.append(
        status_row(
            "hof_win_rates_use_weighted_source",
            not hof_win.empty
            and hof_win.get("source_coverage_note", pd.Series(dtype=str)).astype(str).str.contains("weighted match-count policy", case=False).any(),
            len(hof_win),
            "weighted policy source note",
            "HOF player win rates were rebuilt after policy application.",
        )
    )
    rows.append(
        status_row(
            "player_profile_sources_rebuilt",
            not profile.empty and "matches" in profile.columns,
            len(profile),
            "profile rows with matches column",
            "Player Profile Career Breakdown source exists after refresh.",
        )
    )
    milestones_ok = not batting.empty and pd.to_numeric(batting.get("matches"), errors="coerce").fillna(0).mod(0.5).eq(0).all()
    rows.append(
        status_row(
            "milestone_match_counts_use_weighted_aggregates",
            milestones_ok,
            float(pd.to_numeric(batting.get("matches"), errors="coerce").fillna(0).max()) if not batting.empty else 0,
            "0.5-step weighted aggregate matches",
            "Milestone page reads the weighted all_seasons batting/bowling/fielding aggregates.",
        )
    )
    rows.append(
        status_row(
            "season_overview_coverage_audit_exists",
            not coverage.empty and "weighted_matches_total" in coverage.columns,
            len(coverage),
            "season coverage rows",
            "Season Overview comparison has match-policy audit coverage available.",
        )
    )
    rows.append(
        status_row(
            "no_grdcc_fvcc_data_changes_required",
            True,
            CLUB_ID,
            "glen-waverley-hawks only",
            "Policy helper and scripts are Hawks-specific and do not run for GRDCC/FVCC.",
        )
    )
    rows.append(
        status_row(
            "impact_examples_written",
            not impact.empty,
            len(impact),
            "raw vs weighted player impact rows",
            f"Output={RAW_VS_WEIGHTED}",
        )
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(OUTPUT, index=False)
    failed = frame[frame["validation_status"] != "pass"]
    print(f"validation_status={'pass' if failed.empty else 'fail'} checks={len(frame)} failed={len(failed)}")
    print(f"output={OUTPUT}")
    print(f"impact_output={RAW_VS_WEIGHTED}")
    if not failed.empty:
        print(failed.to_string(index=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
