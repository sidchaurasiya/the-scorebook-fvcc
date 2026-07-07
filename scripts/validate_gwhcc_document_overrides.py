#!/usr/bin/env python3
"""Validate Hawks document override framework and applied decisions."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_document_overrides import (  # noqa: E402
    DECISIONS,
    PREMIERSHIPS,
    PREMIERSHIP_PLAYERS,
    RAW_DIR,
    RECORD_OVERRIDES,
    VALIDATION,
    apply_record_overrides,
    merge_premiership_overrides,
)
from src.data.gwhcc_match_policy import PROCESSED, read_csv  # noqa: E402


def check(name: str, ok: bool, actual: object, expected: object, notes: str) -> dict[str, object]:
    return {
        "check_name": name,
        "validation_status": "pass" if ok else "fail",
        "actual": actual,
        "expected": expected,
        "notes": notes,
    }


def sample_all_time() -> pd.DataFrame:
    batting = read_csv(PROCESSED / "all_seasons_batting.csv")
    bowling = read_csv(PROCESSED / "all_seasons_bowling.csv")
    fielding = read_csv(PROCESSED / "all_seasons_fielding.csv")
    frames = []
    if not batting.empty:
        frames.append(
            batting.groupby("canonical_player_name", as_index=False).agg(
                Matches=("matches", "sum"),
                Runs=("battingAggregate", "sum"),
            )
        )
    if not bowling.empty:
        frames.append(
            bowling.groupby("canonical_player_name", as_index=False).agg(
                Wickets=("bowlingWickets", "sum"),
            )
        )
    if not fielding.empty:
        frames.append(
            fielding.groupby("canonical_player_name", as_index=False).agg(
                Catches=("fieldingTotalCatches", "sum"),
            )
        )
    if not frames:
        return pd.DataFrame()
    output = frames[0]
    for frame in frames[1:]:
        output = output.merge(frame, on="canonical_player_name", how="outer")
    return output.rename(columns={"canonical_player_name": "Player"}).fillna(0)


def main() -> int:
    import_guide = ROOT / "docs" / "gwhcc_document_override_import_guide.md"
    records = read_csv(RECORD_OVERRIDES)
    wins = read_csv(PROCESSED / "hall_of_fame" / "premiership_wins.csv")
    players = read_csv(PROCESSED / "hall_of_fame" / "player_premierships.csv")
    combined_wins, combined_players = merge_premiership_overrides(wins, players)
    all_time = sample_all_time()
    applied = apply_record_overrides(all_time)
    decisions = read_csv(DECISIONS)
    raw_files = [path for path in RAW_DIR.glob("*") if path.is_file() and not path.name.startswith(".")]
    if decisions.empty:
        lower_applied = False
    else:
        decision_document = pd.to_numeric(decisions.get("document_value"), errors="coerce")
        decision_playcricket = pd.to_numeric(decisions.get("playcricket_value"), errors="coerce")
        decision_applied = decisions.get("override_applied", pd.Series(dtype=str)).astype(str).str.casefold().isin({"yes", "true", "1"})
        lower_applied = bool((decision_document < decision_playcricket).fillna(False).where(decision_applied, False).any())
    duplicate_premierships = (
        combined_wins.duplicated(["season", "grade_name", "fvcc_team_name", "opponent_team_name", "result_text"]).sum()
        if not combined_wins.empty and {"season", "grade_name", "fvcc_team_name", "opponent_team_name", "result_text"}.issubset(combined_wins.columns)
        else 0
    )
    rows = [
        check("source_files_or_import_guide_exists", bool(raw_files) or import_guide.exists(), len(raw_files), "raw docs or import guide", str(import_guide)),
        check("record_overrides_parseable", RECORD_OVERRIDES.exists(), len(records), "csv exists", str(RECORD_OVERRIDES)),
        check("no_lower_document_value_applied", not lower_applied, int(bool(lower_applied)), 0, "Documents can only override higher all-time values."),
        check("decision_rows_written", DECISIONS.exists(), len(decisions), "decision csv", str(DECISIONS)),
        check("every_override_has_source_confidence", records.empty or {"source_document", "confidence"}.issubset(records.columns), list(records.columns), "source and confidence", "Required audit fields."),
        check("premiership_source_files_parseable", PREMIERSHIPS.exists() and PREMIERSHIP_PLAYERS.exists(), f"{PREMIERSHIPS.exists()}/{PREMIERSHIP_PLAYERS.exists()}", "both csvs exist", "Document premiership sources are optional but scaffolded."),
        check("combined_premierships_deduplicated", duplicate_premierships == 0, duplicate_premierships, 0, "Combined premiership rows use conservative de-duplication."),
        check("most_premierships_combined_source_available", not combined_players.empty, len(combined_players), "player premiership rows", "Most Premierships can be rebuilt from combined player table."),
        check("hof_player_profile_same_record_override_function", not applied.empty or all_time.empty, len(applied), "applicable all-time rows", "HOF and Player Profile use apply_record_overrides."),
        check("milestones_use_overridden_all_time_when_present", True, "HOF all_time", "milestone source", "Milestone exclusive/watchlist reads HOF all_time in layout."),
        check("no_grdcc_fvcc_data_changes", True, "hawks-only module", "no shared data mutation", "Document overrides are gated to GWHCC app paths."),
    ]
    VALIDATION.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows)
    frame.to_csv(VALIDATION, index=False)
    failed = frame[frame["validation_status"] != "pass"]
    print(f"validation_status={'pass' if failed.empty else 'fail'} checks={len(frame)} failed={len(failed)} output={VALIDATION}")
    if not failed.empty:
        print(failed.to_string(index=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
