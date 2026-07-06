#!/usr/bin/env python3
"""Create Hawks POC Excel reconciliation outputs without mutating app data."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_governance import VALIDATION_DIR  # noqa: E402
from src.data.gwhcc_match_policy import PROCESSED, read_csv  # noqa: E402

SUMMARY = VALIDATION_DIR / "gwhcc_excel_reconciliation_summary.csv"
PLAYER_DIFFS = VALIDATION_DIR / "gwhcc_excel_reconciliation_player_differences.csv"
PREMIERSHIP_DIFFS = VALIDATION_DIR / "gwhcc_excel_reconciliation_premiership_differences.csv"
GRADE_SEASON_DIFFS = VALIDATION_DIR / "gwhcc_excel_reconciliation_grade_season_differences.csv"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel-path", required=True, help="Path to the POC-provided Excel workbook.")
    return parser.parse_args()


def empty_outputs(reason: str) -> int:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "area": "workbook",
                "status": "not_run",
                "playhq_value": "",
                "excel_value": "",
                "difference": "",
                "suggested_action": "review_excel",
                "confidence": "not_applicable",
                "notes": reason,
            }
        ]
    ).to_csv(SUMMARY, index=False)
    for path, columns in [
        (PLAYER_DIFFS, ["player_name", "metric", "playhq_value", "excel_value", "difference", "suggested_action", "confidence", "notes"]),
        (PREMIERSHIP_DIFFS, ["season", "grade", "playhq_value", "excel_value", "difference", "suggested_action", "confidence", "notes"]),
        (GRADE_SEASON_DIFFS, ["season", "grade", "metric", "playhq_value", "excel_value", "difference", "suggested_action", "confidence", "notes"]),
    ]:
        pd.DataFrame(columns=columns).to_csv(path, index=False)
    print(f"excel_reconciliation_status=not_run reason={reason}")
    print(f"summary={SUMMARY}")
    return 0


def normalize_name(value: object) -> str:
    return " ".join(str(value or "").casefold().replace(",", " ").split())


def first_matching_column(frame: pd.DataFrame, candidates: list[str]) -> str:
    lookup = {column.casefold().strip(): column for column in frame.columns}
    for candidate in candidates:
        if candidate.casefold() in lookup:
            return lookup[candidate.casefold()]
    return ""


def workbook_frames(path: Path) -> dict[str, pd.DataFrame]:
    sheets = pd.read_excel(path, sheet_name=None)
    return {str(name): frame for name, frame in sheets.items() if isinstance(frame, pd.DataFrame)}


def playhq_career() -> pd.DataFrame:
    parts = []
    specs = [
        ("all_seasons_batting.csv", {"runs": "battingAggregate", "matches": "matches"}),
        ("all_seasons_bowling.csv", {"wickets": "bowlingWickets", "matches": "matches"}),
        ("all_seasons_fielding.csv", {"catches": "fieldingTotalCatches", "matches": "matches"}),
    ]
    for filename, metrics in specs:
        frame = read_csv(PROCESSED / filename)
        if frame.empty or "canonical_player_name" not in frame:
            continue
        rows = frame[["canonical_player_name"] + [col for col in metrics.values() if col in frame]].copy()
        rows = rows.rename(columns={value: key for key, value in metrics.items()})
        parts.append(rows)
    if not parts:
        return pd.DataFrame()
    merged = pd.concat(parts, ignore_index=True, sort=False).fillna(0)
    numeric = [column for column in ["matches", "runs", "wickets", "catches"] if column in merged]
    for column in numeric:
        merged[column] = pd.to_numeric(merged[column], errors="coerce").fillna(0)
    return merged.groupby("canonical_player_name", as_index=False)[numeric].max()


def player_diff_from_workbook(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    career = playhq_career()
    if career.empty:
        return pd.DataFrame(columns=["player_name", "metric", "playhq_value", "excel_value", "difference", "suggested_action", "confidence", "notes"])
    candidates = []
    for sheet_name, frame in frames.items():
        name_col = first_matching_column(frame, ["player", "player_name", "name"])
        if not name_col:
            continue
        metric_cols = {
            "matches": first_matching_column(frame, ["matches", "games"]),
            "runs": first_matching_column(frame, ["runs"]),
            "wickets": first_matching_column(frame, ["wickets"]),
            "catches": first_matching_column(frame, ["catches"]),
        }
        for metric, column in metric_cols.items():
            if not column:
                continue
            rows = frame[[name_col, column]].copy()
            rows.columns = ["player_name", "excel_value"]
            rows["metric"] = metric
            rows["sheet"] = sheet_name
            candidates.append(rows)
    if not candidates:
        return pd.DataFrame(columns=["player_name", "metric", "playhq_value", "excel_value", "difference", "suggested_action", "confidence", "notes"])
    excel = pd.concat(candidates, ignore_index=True)
    excel["player_key"] = excel["player_name"].map(normalize_name)
    career["player_key"] = career["canonical_player_name"].map(normalize_name)
    rows = []
    for metric in ["matches", "runs", "wickets", "catches"]:
        subset = excel[excel["metric"].eq(metric)].copy()
        if subset.empty or metric not in career:
            continue
        merged = subset.merge(career[["player_key", "canonical_player_name", metric]], on="player_key", how="outer")
        merged["playhq_value"] = pd.to_numeric(merged[metric], errors="coerce")
        merged["excel_value"] = pd.to_numeric(merged["excel_value"], errors="coerce")
        merged["difference"] = merged["excel_value"] - merged["playhq_value"]
        merged["suggested_action"] = merged.apply(suggest_action, axis=1)
        merged["confidence"] = merged["suggested_action"].map(lambda value: "medium" if value in {"accept_playhq", "review_excel"} else "low")
        merged["notes"] = "No PlayHQ values are overwritten by this scaffold."
        merged["player_name"] = merged["canonical_player_name"].fillna(merged["player_name"])
        rows.append(merged[["player_name", "metric", "playhq_value", "excel_value", "difference", "suggested_action", "confidence", "notes"]])
    return pd.concat(rows, ignore_index=True, sort=False) if rows else pd.DataFrame()


def suggest_action(row: pd.Series) -> str:
    playhq_missing = pd.isna(row.get("playhq_value"))
    excel_missing = pd.isna(row.get("excel_value"))
    if playhq_missing and not excel_missing:
        return "missing_from_playhq"
    if excel_missing and not playhq_missing:
        return "missing_from_excel"
    diff = row.get("difference")
    if pd.isna(diff) or float(diff) == 0:
        return "accept_playhq"
    return "manual_override_candidate" if abs(float(diff)) >= 5 else "review_excel"


def main() -> int:
    args = parse_args()
    excel_path = Path(args.excel_path).expanduser()
    if not excel_path.exists():
        return empty_outputs(f"Excel file not found: {excel_path}")
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    frames = workbook_frames(excel_path)
    player_diffs = player_diff_from_workbook(frames)
    player_diffs.to_csv(PLAYER_DIFFS, index=False)
    pd.DataFrame(columns=["season", "grade", "playhq_value", "excel_value", "difference", "suggested_action", "confidence", "notes"]).to_csv(
        PREMIERSHIP_DIFFS,
        index=False,
    )
    pd.DataFrame(columns=["season", "grade", "metric", "playhq_value", "excel_value", "difference", "suggested_action", "confidence", "notes"]).to_csv(
        GRADE_SEASON_DIFFS,
        index=False,
    )
    pd.DataFrame(
        [
            {
                "area": "player_career",
                "status": "completed",
                "playhq_value": len(playhq_career()),
                "excel_value": sum(len(frame) for frame in frames.values()),
                "difference": "",
                "suggested_action": "review_excel",
                "confidence": "medium",
                "notes": "Workbook parsed. Review difference exports before approving any manual overrides.",
            }
        ]
    ).to_csv(SUMMARY, index=False)
    print(f"excel_reconciliation_status=pass player_difference_rows={len(player_diffs)} summary={SUMMARY}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
