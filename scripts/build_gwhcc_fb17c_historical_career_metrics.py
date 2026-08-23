#!/usr/bin/env python3
"""Build governed FB17C metric decisions from the committed Career Master audit."""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CLUB_ROOT = ROOT / "clubs" / "glen-waverley-hawks"
AUDIT = CLUB_ROOT / "data" / "processed" / "validation" / "gwhcc_career_total_reconciliation_audit.csv"
OUTPUT = CLUB_ROOT / "data" / "source" / "document_overrides" / "gwhcc_historical_career_metric_decisions.csv"

COLUMNS = [
    "canonical_player_id",
    "canonical_player_name",
    "metric",
    "authoritative_value",
    "authority_source",
    "coverage_scope",
    "source_document",
    "source_sheet",
    "source_row",
    "confidence",
    "decision_status",
    "decision_reason",
]


def add_decision(rows: list[dict[str, object]], source: pd.Series, metric: str, value_column: str) -> None:
    value = pd.to_numeric(source.get(value_column), errors="coerce")
    if pd.isna(value):
        raise ValueError(f"Missing {metric} value for {source.get('player_name')}")
    rows.append(
        {
            "canonical_player_id": str(source["canonical_player_id"]),
            "canonical_player_name": str(source["player_name"]),
            "metric": metric,
            "authoritative_value": float(value),
            "authority_source": "career_master",
            "coverage_scope": "full_gwhcc_career",
            "source_document": str(source["source_workbook"]),
            "source_sheet": str(source["source_sheet"]),
            "source_row": str(source["source_rows"]),
            "confidence": "high",
            "decision_status": "approved_fb17c",
            "decision_reason": "FB17B confirmed identity, earlier verified GWHCC history, clean source arithmetic, and full-career replacement authority; value is not additive to PlayCricket.",
        }
    )


def main() -> int:
    audit = pd.read_csv(AUDIT, dtype=str).fillna("")
    approved = audit[audit["recommended_authority"].eq("CAREER_MASTER_REPLACEMENT")].copy()
    if len(approved) != 21 or approved["canonical_player_id"].nunique() != 21:
        raise SystemExit(f"Expected 21 unique FB17C candidates, found rows={len(approved)} ids={approved['canonical_player_id'].nunique()}")
    if approved["source_rows"].str.contains(";").any():
        raise SystemExit("FB17C candidates must resolve to one Career Master source row each.")

    rows: list[dict[str, object]] = []
    for _, source in approved.sort_values(["player_name", "canonical_player_id"]).iterrows():
        if source["runs_authority"] != "CAREER_MASTER_REPLACEMENT" or source["wickets_authority"] != "CAREER_MASTER_REPLACEMENT":
            raise SystemExit(f"Runs/wickets authority is not approved for {source['player_name']}")
        if source["batting_average_quality_flag"] != "PASS" or source["bowling_average_quality_flag"] != "PASS":
            raise SystemExit(f"Career Master average does not reconcile for {source['player_name']}")
        add_decision(rows, source, "runs", "career_master_runs")
        add_decision(rows, source, "wickets", "career_master_wickets")
        add_decision(rows, source, "batting_average", "recalculated_career_master_batting_average")
        add_decision(rows, source, "bowling_average", "recalculated_career_master_bowling_average")
        if source["not_outs_authority"] == "CAREER_MASTER_REPLACEMENT":
            add_decision(rows, source, "not_outs", "career_master_not_outs")

    decisions = pd.DataFrame(rows, columns=COLUMNS)
    metric_counts = decisions["metric"].value_counts().to_dict()
    expected = {"runs": 21, "wickets": 21, "batting_average": 21, "bowling_average": 21, "not_outs": 17}
    if metric_counts != expected:
        raise SystemExit(f"Unexpected FB17C metric counts: {metric_counts}")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    decisions.to_csv(OUTPUT, index=False)
    print(f"fb17c_source=pass players=21 rows={len(decisions)} metrics={metric_counts} output={OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
