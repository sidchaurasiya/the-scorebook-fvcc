#!/usr/bin/env python3
"""Reconcile Hawks POC Excel career stats against current app-facing data.

This script is review-only. It never mutates PlayCricket/raw data or app
outputs. It parses the POC workbook's fixed "1980-2026 career" layout and
exports row-level differences for manual approval.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_document_overrides import apply_record_overrides, load_document_player_aliases, normalize_name  # noqa: E402
from src.data.gwhcc_governance import VALIDATION_DIR  # noqa: E402
from src.data.gwhcc_match_policy import PROCESSED, read_csv  # noqa: E402

SUMMARY = VALIDATION_DIR / "gwhcc_excel_reconciliation_summary.csv"
PLAYER_DIFFS = VALIDATION_DIR / "gwhcc_excel_reconciliation_player_differences.csv"
UNMATCHED = VALIDATION_DIR / "gwhcc_excel_reconciliation_unmatched_players.csv"
PARSED_ROWS = VALIDATION_DIR / "gwhcc_excel_reconciliation_parsed_rows.csv"
TOP_DIFFS = VALIDATION_DIR / "gwhcc_excel_reconciliation_top_differences.csv"
PREMIERSHIP_DIFFS = VALIDATION_DIR / "gwhcc_excel_reconciliation_premiership_differences.csv"
GRADE_SEASON_DIFFS = VALIDATION_DIR / "gwhcc_excel_reconciliation_grade_season_differences.csv"

SHEET_NAME = "Sheet1"
EXCEL_COLUMNS = {
    "player_name_excel": 0,
    "career_games": 1,
    "career_runs": 2,
    "career_innings": 3,
    "career_not_outs": 4,
    "career_batting_average": 5,
    "career_wickets": 6,
    "career_bowling_runs": 7,
    "career_bowling_average": 8,
    "one_day_games": 11,
    "one_day_runs": 12,
    "one_day_innings": 13,
    "one_day_not_outs": 14,
    "one_day_batting_average": 15,
    "one_day_wickets": 16,
    "one_day_bowling_runs": 17,
    "one_day_bowling_average": 18,
    "t20_games": 20,
    "t20_runs": 21,
    "t20_innings": 22,
    "t20_not_outs": 23,
    "t20_batting_average": 24,
    "t20_wickets": 25,
    "t20_bowling_runs": 26,
    "t20_bowling_average": 27,
    "club_games_formula": 30,
}
DIFF_METRICS = [
    "career_games",
    "career_runs",
    "career_innings",
    "career_not_outs",
    "career_batting_average",
    "career_wickets",
    "career_bowling_runs",
    "career_bowling_average",
    "one_day_games",
    "one_day_runs",
    "one_day_innings",
    "one_day_not_outs",
    "one_day_batting_average",
    "one_day_wickets",
    "one_day_bowling_runs",
    "one_day_bowling_average",
    "t20_games",
    "t20_runs",
    "t20_innings",
    "t20_not_outs",
    "t20_batting_average",
    "t20_wickets",
    "t20_bowling_runs",
    "t20_bowling_average",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--excel-path", required=True, help="Path to the POC-provided Excel workbook.")
    return parser.parse_args()


def excel_player_key(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", "", text)
    if "." in text:
        surname, given = text.split(".", 1)
        given_initial = re.sub(r"[^A-Za-z]", "", given)[:1]
        surname = re.sub(r"[^A-Za-z]", "", surname)
        if surname and given_initial:
            return f"{given_initial.casefold()} {surname.casefold()}"
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) >= 2:
        return f"{words[-1][0].casefold()} {words[0].casefold()}"
    return normalize_name(text)


def display_number(value: object) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    return float(number)


def safe_divide(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return numerator / denominator


def parse_excel(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=SHEET_NAME, header=None, skiprows=3)
    rows: list[dict[str, object]] = []
    for idx, row in raw.iterrows():
        player = str(row.get(EXCEL_COLUMNS["player_name_excel"], "") or "").strip()
        if not player or player.casefold() == "note" or player.startswith("Scorebook") or player.startswith("Does not"):
            continue
        if not re.search(r"[A-Za-z]", player):
            continue
        parsed = {"source_row_number": idx + 4}
        for name, column in EXCEL_COLUMNS.items():
            parsed[name] = row.get(column, "")
        parsed["excel_player_key"] = excel_player_key(player)
        rows.append(parsed)
    frame = pd.DataFrame(rows)
    for column in DIFF_METRICS:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    return frame


def aggregate_metric(frame: pd.DataFrame, value_column: str, scope: str) -> pd.DataFrame:
    source = frame.copy()
    if scope == "senior_t20":
        source = source[source["record_scope"].astype(str).isin(["Senior/open", "T20"])].copy()
    elif scope == "one_day":
        source = source[source["format"].astype(str).eq("One Day")].copy()
    elif scope == "t20":
        source = source[source["format"].astype(str).eq("T20")].copy()
    if source.empty or value_column not in source:
        return pd.DataFrame(columns=["canonical_player_name", value_column])
    source[value_column] = pd.to_numeric(source[value_column], errors="coerce").fillna(0)
    return source.groupby("canonical_player_name", as_index=False)[value_column].sum()


def current_totals() -> pd.DataFrame:
    batting = read_csv(PROCESSED / "all_seasons_batting.csv")
    bowling = read_csv(PROCESSED / "all_seasons_bowling.csv")
    fielding = read_csv(PROCESSED / "all_seasons_fielding.csv")
    all_names = sorted(
        set(batting.get("canonical_player_name", pd.Series(dtype=str)).dropna().astype(str))
        | set(bowling.get("canonical_player_name", pd.Series(dtype=str)).dropna().astype(str))
        | set(fielding.get("canonical_player_name", pd.Series(dtype=str)).dropna().astype(str))
    )
    output = pd.DataFrame({"current_player_name": all_names})
    output["current_player_key"] = output["current_player_name"].map(normalize_name)
    output["excel_match_key"] = output["current_player_name"].map(lambda name: excel_player_key(".".join(reversed(str(name).split(" ", 1))) if " " in str(name) else name))
    for scope_prefix, scope in [("current", "senior_t20"), ("whole_club", "whole_club"), ("one_day", "one_day"), ("t20", "t20")]:
        metrics = [
            ("games", batting, "matches"),
            ("runs", batting, "battingAggregate"),
            ("innings", batting, "battingInnings"),
            ("not_outs", batting, "battingNotOuts"),
            ("wickets", bowling, "bowlingWickets"),
            ("bowling_runs", bowling, "bowlingRuns"),
        ]
        for metric_name, frame, column in metrics:
            agg = aggregate_metric(frame, column, scope)
            if agg.empty:
                output[f"{scope_prefix}_{metric_name}"] = 0.0
                continue
            agg = agg.rename(columns={"canonical_player_name": "current_player_name", column: f"{scope_prefix}_{metric_name}"})
            output = output.merge(agg, on="current_player_name", how="left")
            output[f"{scope_prefix}_{metric_name}"] = pd.to_numeric(output[f"{scope_prefix}_{metric_name}"], errors="coerce").fillna(0)
        outs = output[f"{scope_prefix}_innings"] - output[f"{scope_prefix}_not_outs"]
        output[f"{scope_prefix}_batting_average"] = [safe_divide(runs, out) for runs, out in zip(output[f"{scope_prefix}_runs"], outs)]
        output[f"{scope_prefix}_bowling_average"] = [
            safe_divide(runs, wickets) for runs, wickets in zip(output[f"{scope_prefix}_bowling_runs"], output[f"{scope_prefix}_wickets"])
        ]
    return apply_current_record_overrides(output)


def apply_current_record_overrides(current: pd.DataFrame) -> pd.DataFrame:
    all_time = current[
        ["current_player_name", "current_games", "current_runs", "current_wickets"]
    ].rename(columns={"current_player_name": "Player", "current_games": "Matches", "current_runs": "Runs", "current_wickets": "Wickets"})
    overridden = apply_record_overrides(all_time, write_decisions=False)
    lookup = overridden.set_index("Player").to_dict("index") if not overridden.empty else {}
    for index, row in current.iterrows():
        values = lookup.get(row["current_player_name"], {})
        current.at[index, "display_games"] = values.get("Matches", row.get("current_games", 0))
        current.at[index, "display_runs"] = values.get("Runs", row.get("current_runs", 0))
        current.at[index, "display_wickets"] = values.get("Wickets", row.get("current_wickets", 0))
    return current


def current_alias_lookup(current: pd.DataFrame) -> dict[str, str]:
    pairs: dict[str, set[str]] = {}
    for _, row in current.iterrows():
        pairs.setdefault(str(row["excel_match_key"]), set()).add(str(row["current_player_key"]))
    lookup = {key: next(iter(values)) for key, values in pairs.items() if key and len(values) == 1}
    manual = load_document_player_aliases("all")
    lookup.update({excel_player_key(document): current_key for document, current_key in manual.items()})
    return lookup


def difference_action(excel_value: float | None, current_value: float | None, metric: str, matched: bool) -> tuple[str, str]:
    if not matched:
        return "identity_review_required", "low"
    if excel_value is None and current_value is None:
        return "no_value", "medium"
    if excel_value is None:
        return "missing_from_excel", "medium"
    if current_value is None:
        return "missing_from_current_app", "low"
    tolerance = 0.02 if "average" in metric else 0.01
    diff = abs(float(excel_value) - float(current_value))
    if diff <= tolerance:
        return "matches_current", "high"
    if metric in {"career_games", "career_runs", "career_wickets"} and excel_value > current_value:
        return "manual_override_candidate", "medium"
    return "review_difference", "medium"


def build_differences(excel: pd.DataFrame, current: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    lookup = current_alias_lookup(current)
    current_by_key = current.drop_duplicates("current_player_key").set_index("current_player_key")
    metric_map = {
        "career_games": "display_games",
        "career_runs": "display_runs",
        "career_innings": "current_innings",
        "career_not_outs": "current_not_outs",
        "career_batting_average": "current_batting_average",
        "career_wickets": "display_wickets",
        "career_bowling_runs": "current_bowling_runs",
        "career_bowling_average": "current_bowling_average",
        "one_day_games": "one_day_games",
        "one_day_runs": "one_day_runs",
        "one_day_innings": "one_day_innings",
        "one_day_not_outs": "one_day_not_outs",
        "one_day_batting_average": "one_day_batting_average",
        "one_day_wickets": "one_day_wickets",
        "one_day_bowling_runs": "one_day_bowling_runs",
        "one_day_bowling_average": "one_day_bowling_average",
        "t20_games": "t20_games",
        "t20_runs": "t20_runs",
        "t20_innings": "t20_innings",
        "t20_not_outs": "t20_not_outs",
        "t20_batting_average": "t20_batting_average",
        "t20_wickets": "t20_wickets",
        "t20_bowling_runs": "t20_bowling_runs",
        "t20_bowling_average": "t20_bowling_average",
    }
    diff_rows: list[dict[str, object]] = []
    unmatched_rows: list[dict[str, object]] = []
    for _, row in excel.iterrows():
        current_key = lookup.get(str(row["excel_player_key"]), "")
        matched = bool(current_key and current_key in current_by_key.index)
        current_row = current_by_key.loc[current_key].to_dict() if matched else {}
        if not matched:
            unmatched_rows.append(
                {
                    "excel_player_name": row.get("player_name_excel"),
                    "excel_match_key": row.get("excel_player_key"),
                    "source_row_number": row.get("source_row_number"),
                    "suggested_action": "identity_review_required",
                    "notes": "No unique current PlayCricket player matched by surname + initial or confirmed document alias.",
                }
            )
        for metric, current_column in metric_map.items():
            excel_value = display_number(row.get(metric))
            current_value = display_number(current_row.get(current_column)) if matched else None
            action, confidence = difference_action(excel_value, current_value, metric, matched)
            diff_rows.append(
                {
                    "excel_player_name": row.get("player_name_excel"),
                    "matched_current_player_name": current_row.get("current_player_name", ""),
                    "excel_match_key": row.get("excel_player_key"),
                    "source_row_number": row.get("source_row_number"),
                    "metric": metric,
                    "current_scope": "Senior/open + T20 for career; format-specific for One Day/T20; document overrides applied for career games/runs/wickets",
                    "current_value": current_value,
                    "excel_value": excel_value,
                    "difference_excel_minus_current": None if excel_value is None or current_value is None else excel_value - current_value,
                    "suggested_action": action,
                    "confidence": confidence,
                    "notes": "Review-only. No app values were changed.",
                }
            )
    return pd.DataFrame(diff_rows), pd.DataFrame(unmatched_rows)


def write_empty_outputs(reason: str) -> int:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"area": "workbook", "status": "not_run", "notes": reason}]).to_csv(SUMMARY, index=False)
    pd.DataFrame().to_csv(PLAYER_DIFFS, index=False)
    pd.DataFrame().to_csv(UNMATCHED, index=False)
    pd.DataFrame().to_csv(PARSED_ROWS, index=False)
    print(f"excel_reconciliation_status=not_run reason={reason} summary={SUMMARY}")
    return 0


def main() -> int:
    args = parse_args()
    excel_path = Path(args.excel_path).expanduser()
    if not excel_path.exists():
        return write_empty_outputs(f"Excel file not found: {excel_path}")
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    excel = parse_excel(excel_path)
    current = current_totals()
    diffs, unmatched = build_differences(excel, current)
    excel.to_csv(PARSED_ROWS, index=False)
    diffs.to_csv(PLAYER_DIFFS, index=False)
    unmatched.to_csv(UNMATCHED, index=False)
    pd.DataFrame(columns=["season", "grade", "playhq_value", "excel_value", "difference", "suggested_action", "confidence", "notes"]).to_csv(PREMIERSHIP_DIFFS, index=False)
    pd.DataFrame(columns=["season", "grade", "metric", "playhq_value", "excel_value", "difference", "suggested_action", "confidence", "notes"]).to_csv(GRADE_SEASON_DIFFS, index=False)
    review = diffs[diffs["suggested_action"].isin(["manual_override_candidate", "review_difference", "missing_from_current_app"])]
    top = review.copy()
    top["_abs_diff"] = pd.to_numeric(top["difference_excel_minus_current"], errors="coerce").abs()
    top = top.sort_values(["suggested_action", "_abs_diff"], ascending=[True, False]).drop(columns=["_abs_diff"]).head(250)
    top.to_csv(TOP_DIFFS, index=False)
    summary_rows = []
    for action, group in diffs.groupby("suggested_action", dropna=False):
        summary_rows.append(
            {
                "area": "player_metric",
                "status": str(action),
                "current_value": "",
                "excel_value": "",
                "difference": len(group),
                "suggested_action": str(action),
                "confidence": "",
                "notes": f"{len(group)} metric rows",
            }
        )
    summary_rows.extend(
        [
            {
                "area": "workbook",
                "status": "completed",
                "current_value": len(current),
                "excel_value": len(excel),
                "difference": len(excel) - len(current),
                "suggested_action": "review_excel",
                "confidence": "medium",
                "notes": "Parsed Sheet1 career totals. Review player differences before approving overrides.",
            },
            {
                "area": "identity",
                "status": "unmatched_excel_players",
                "current_value": "",
                "excel_value": len(unmatched),
                "difference": "",
                "suggested_action": "identity_review_required",
                "confidence": "low",
                "notes": str(UNMATCHED),
            },
        ]
    )
    pd.DataFrame(summary_rows).to_csv(SUMMARY, index=False)
    print(
        "excel_reconciliation_status=pass "
        f"excel_players={len(excel)} current_players={len(current)} "
        f"difference_rows={len(diffs)} unmatched_players={len(unmatched)} summary={SUMMARY}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
