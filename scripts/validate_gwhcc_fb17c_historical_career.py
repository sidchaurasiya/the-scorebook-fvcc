#!/usr/bin/env python3
"""Validate FB17C historical career metrics across HOF and Player Profile."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


os.environ["CLUB_ID"] = "glen-waverley-hawks"
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_document_overrides import apply_record_overrides, load_historical_career_metric_decisions  # noqa: E402
from src.data.playcricket_ingestion import metadata_mtime  # noqa: E402
from src.ui import layout  # noqa: E402
from src.utils.player_identity import get_player_profile_data, player_aliases_mtime  # noqa: E402


CLUB_ID = "glen-waverley-hawks"
CLUB_ROOT = ROOT / "clubs" / CLUB_ID
PROCESSED = CLUB_ROOT / "data" / "processed"
HOF = PROCESSED / "hall_of_fame"
AUDIT = PROCESSED / "validation" / "gwhcc_career_total_reconciliation_audit.csv"
OUTPUT = PROCESSED / "validation" / "gwhcc_fb17c_historical_career_validation.csv"


def number(value: object) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(parsed) else float(parsed)


def same(left: object, right: object, tolerance: float = 0.01) -> bool:
    left_number = number(left)
    right_number = number(right)
    return left_number is None and right_number is None or (
        left_number is not None and right_number is not None and abs(left_number - right_number) <= tolerance
    )


def match_band(value: object) -> str:
    number_value = number(value) or 0.0
    reached = [threshold for threshold in [50, 100, 200, 300, 400] if number_value >= threshold]
    return str(max(reached)) if reached else ""


def authoritative_frame() -> pd.DataFrame:
    base = pd.read_csv(HOF / "prepared_career_all_time.csv", low_memory=False)
    batting = pd.read_csv(HOF / "prepared_career_batting.csv", low_memory=False)
    not_outs = batting[["canonical_player_id", "battingNotOuts"]].rename(columns={"battingNotOuts": "Not Outs"})
    base = base.drop(columns=["Not Outs"], errors="ignore").merge(not_outs, on="canonical_player_id", how="left")
    return apply_record_overrides(base, write_decisions=False)


def main() -> int:
    decisions = load_historical_career_metric_decisions()
    audit = pd.read_csv(AUDIT, dtype=str).fillna("")
    candidates = audit[audit["recommended_authority"].eq("CAREER_MASTER_REPLACEMENT")].copy()
    authoritative = authoritative_frame()
    profile_index = layout.load_player_profile_index(
        CLUB_ID,
        metadata_mtime(),
        player_aliases_mtime(club_id=CLUB_ID),
        "fb17c-validation-v1",
    )

    rows = []
    for _, source in candidates.sort_values("player_name").iterrows():
        canonical_id = source["canonical_player_id"]
        hof = authoritative[authoritative["canonical_player_id"].astype(str).eq(canonical_id)]
        profile_count = int(profile_index["id"].astype(str).eq(canonical_id).sum())
        profile_career = pd.Series(dtype="object")
        if profile_count == 1:
            profile = get_player_profile_data(
                canonical_id,
                metadata_mtime(),
                player_aliases_mtime(club_id=CLUB_ID),
                club_id=CLUB_ID,
            )
            view = layout.build_player_profile_view(profile, layout.player_profile_view_signature())
            if len(view["career"]) == 1:
                profile_career = view["career"].iloc[0]
        hof_row = hof.iloc[0] if len(hof) == 1 else pd.Series(dtype="object")
        not_outs_approved = source["not_outs_authority"] == "CAREER_MASTER_REPLACEMENT"
        expected_not_outs = source["proposed_not_outs"]
        checks = {
            "one_hof_row": len(hof) == 1,
            "one_public_profile": profile_count == 1,
            "runs_applied": same(hof_row.get("Runs"), source["proposed_runs"]),
            "wickets_applied": same(hof_row.get("Wickets"), source["proposed_wickets"]),
            "not_outs_correct": same(hof_row.get("Not Outs"), expected_not_outs),
            "matches_unchanged": same(hof_row.get("Matches"), source["scorebook_matches"]),
            "catches_unchanged": same(hof_row.get("Catches"), source["scorebook_catches"]),
            "bat_avg_governed": same(hof_row.get("Bat Avg"), source["recalculated_career_master_batting_average"]),
            "bowl_avg_governed": same(hof_row.get("Bowl Avg"), source["recalculated_career_master_bowling_average"]),
            "profile_runs_match": same(profile_career.get("Runs"), hof_row.get("Runs")),
            "profile_wickets_match": same(profile_career.get("Wickets"), hof_row.get("Wickets")),
            "profile_not_outs_match": same(profile_career.get("Not Outs"), hof_row.get("Not Outs")),
            "profile_bat_avg_match": same(profile_career.get("Bat Avg"), hof_row.get("Bat Avg")),
            "profile_bowl_avg_match": same(profile_career.get("Bowl Avg"), hof_row.get("Bowl Avg")),
            "match_band_unchanged": match_band(source["scorebook_matches"]) == match_band(hof_row.get("Matches")),
        }
        source_decisions = decisions[decisions["canonical_player_id"].astype(str).eq(canonical_id)]
        rows.append(
            {
                "canonical_player_id": canonical_id,
                "player_name": source["player_name"],
                "source_row": source["source_rows"],
                "confidence": source["confidence"],
                "runs_before": source["scorebook_runs"],
                "runs_after": number(hof_row.get("Runs")),
                "wickets_before": source["scorebook_wickets"],
                "wickets_after": number(hof_row.get("Wickets")),
                "not_outs_before": source["scorebook_not_outs"],
                "not_outs_after": number(hof_row.get("Not Outs")),
                "not_outs_authority": "career_master" if not_outs_approved else "playcricket_or_review",
                "batting_average_before": source["scorebook_batting_average"],
                "batting_average_after": number(hof_row.get("Bat Avg")),
                "batting_average_authority": "career_master_reconciled_full_career",
                "bowling_average_before": source["scorebook_bowling_average"],
                "bowling_average_after": number(hof_row.get("Bowl Avg")),
                "bowling_average_authority": "career_master_reconciled_full_career",
                "matches_before": source["scorebook_matches"],
                "matches_after": number(hof_row.get("Matches")),
                "catches_before": source["scorebook_catches"],
                "catches_after": number(hof_row.get("Catches")),
                "match_band_before": match_band(source["scorebook_matches"]),
                "match_band_after": match_band(hof_row.get("Matches")),
                "public_profile_count": profile_count,
                "governed_metric_count": len(source_decisions),
                "validation_status": "PASS" if all(checks.values()) else "FAIL",
                "failed_checks": ";".join(name for name, passed in checks.items() if not passed),
            }
        )

    output = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT, index=False)
    failures = output[output["validation_status"].ne("PASS")]
    print(f"fb17c_validation={'pass' if failures.empty else 'fail'} players={len(output)} failed={len(failures)} output={OUTPUT}")
    if not failures.empty:
        print(failures[["player_name", "failed_checks"]].to_string(index=False))
    return 0 if failures.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
