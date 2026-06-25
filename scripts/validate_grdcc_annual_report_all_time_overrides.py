#!/usr/bin/env python3
"""Validate GRDCC Annual Report combined career presentation overrides."""

from __future__ import annotations

import csv
import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "clubs/georges-river-district/data/processed/validation/annual_report_2024_25/all_time_overrides"
DECISIONS = OUTPUT / "grdcc_all_time_override_decisions.csv"
DETAIL = OUTPUT / "grdcc_annual_report_combined_all_time_runs_wickets.csv"
COMBINED = OUTPUT / "grdcc_annual_report_combined_all_time_by_player.csv"
CANDIDATES = OUTPUT / "grdcc_annual_report_highest_scores_bbi_extract.csv"
VALIDATION = OUTPUT / "grdcc_all_time_override_validation.csv"
SUMMARY = OUTPUT / "grdcc_all_time_override_summary.csv"


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write(path: Path, data: list[dict[str, object]], columns: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(data)


def main() -> None:
    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "status": "pass" if ok else "fail", "detail": detail})

    required_files = [DETAIL, COMBINED, DECISIONS, CANDIDATES]
    check("required_outputs_exist", all(path.exists() for path in required_files), "; ".join(path.name for path in required_files))
    if not all(path.exists() for path in required_files):
        write(VALIDATION, checks, ["check", "status", "detail"])
        raise SystemExit("Missing extraction outputs")

    detail = rows(DETAIL)
    combined = rows(COMBINED)
    decisions = rows(DECISIONS)
    candidates = rows(CANDIDATES)
    duplicate_detail = len(detail) - len({(row["normalized_player_name"], row["metric"], row["annual_report_section"]) for row in detail})
    check("section_rows_unique", duplicate_detail == 0, f"duplicate_section_rows={duplicate_detail}")
    check("shields_and_frank_gray_present", {row["annual_report_section"] for row in detail}.issuperset({"shields", "frank_gray"}), "both report sections extracted")
    check("combined_arithmetic", all(int(float(row["annual_report_combined_value"])) == sum(int(float(row[column] or 0)) for column in ["annual_report_shields_value", "annual_report_frank_gray_value", "annual_report_other_value"]) for row in combined), f"rows={len(combined)}")
    decision_rule_ok = all(
        (float(row["annual_report_combined_value"]) > float(row["source_rule_derived_value"]) and row["displayed_value_source"] == "annual_report_combined" and row["override_applies"] == "yes")
        or (float(row["annual_report_combined_value"]) <= float(row["source_rule_derived_value"]) and row["displayed_value_source"] == "source_rule_derived" and row["override_applies"] == "no")
        for row in decisions
    )
    check("max_value_decision_rule", decision_rule_ok, f"decisions={len(decisions)}")

    by_key = {(row["normalized_player_name"], row["metric"]): row for row in decisions}
    harry = by_key.get(("harry milburn", "career_runs"), {})
    gordon = by_key.get(("gordon leslie", "career_wickets"), {})
    check("harry_milburn", harry.get("displayed_value") == "10788" and harry.get("override_applies") == "yes", f"displayed={harry.get('displayed_value', '')}")
    check("gordon_leslie", gordon.get("displayed_value") == "707" and gordon.get("override_applies") == "yes", f"displayed={gordon.get('displayed_value', '')}")
    check("current_higher_case", any(row["displayed_value_source"] == "source_rule_derived" for row in decisions), f"count={sum(row['displayed_value_source'] == 'source_rule_derived' for row in decisions)}")

    layout = (ROOT / "src/ui/layout.py").read_text(encoding="utf-8")
    helper = (ROOT / "src/data/featured_record_overrides.py").read_text(encoding="utf-8")
    check("hof_all_time_prepared_before_tables", 'all_time = apply_featured_record_overrides(historical_data["all_time"].copy())' in layout, "shared HOF preparation")
    check("hof_stats_table_uses_prepared_all_time", '"batting": format_all_time_batting_table(all_time)' in layout and '"bowling": format_all_time_bowling_table(all_time)' in layout, "detailed tables built from prepared all_time")
    check("player_profile_career_override", "career = apply_featured_record_overrides(career, add_missing_players=False)" in layout, "career row only")
    check("career_only_metric_map", '"career_runs": "Runs"' in helper and '"career_wickets": "Wickets"' in helper, "no season metric mapping")
    check("no_noisy_source_text", "Official Annual Report total" not in layout, "UI template clean")

    app_probe = """
import json, pandas as pd
from src.data.featured_record_overrides import apply_featured_record_overrides
frame=pd.DataFrame([{'Player':'Harry Milburn','Runs':8865,'Wickets':0},{'Player':'Gordon Leslie','Runs':0,'Wickets':242}])
out=apply_featured_record_overrides(frame, club_id='georges-river-district', add_missing_players=False)
fv=apply_featured_record_overrides(frame, club_id='fvcc', add_missing_players=False)
print(json.dumps({'grdcc':out[['Player','Runs','Wickets']].to_dict('records'),'fvcc':fv[['Player','Runs','Wickets']].to_dict('records')}))
"""
    probe = subprocess.run([str(ROOT / ".venv-app/bin/python"), "-c", app_probe], cwd=ROOT, capture_output=True, text=True, check=True)
    payload = json.loads(probe.stdout.strip().splitlines()[-1])
    grdcc = {row["Player"]: row for row in payload["grdcc"]}
    fvcc = {row["Player"]: row for row in payload["fvcc"]}
    check("runtime_grdcc_values", int(grdcc["Harry Milburn"]["Runs"]) == 10788 and int(grdcc["Gordon Leslie"]["Wickets"]) == 707, "helper applies approved values")
    check("runtime_fvcc_unchanged", int(fvcc["Harry Milburn"]["Runs"]) == 8865 and int(fvcc["Gordon Leslie"]["Wickets"]) == 242, "club scope enforced")

    candidate_required = {"record_category", "player_name", "score_or_figures", "extraction_confidence", "candidate_for_iconic_performances"}
    check("candidate_schema", bool(candidates) and candidate_required.issubset(candidates[0]), f"rows={len(candidates)}")
    check("highest_score_candidates", any(row["record_category"] == "highest_score" for row in candidates), f"count={sum(row['record_category'] == 'highest_score' for row in candidates)}")
    check("bbi_candidates", any(row["record_category"] == "bbi" for row in candidates), f"count={sum(row['record_category'] == 'bbi' for row in candidates)}")
    check("candidate_only", all(row["candidate_for_iconic_performances"] == "yes" and "not injected" in row["notes"] for row in candidates), "no app injection")

    raw_paths = [
        "clubs/georges-river-district/data/processed/all_seasons_batting.csv",
        "clubs/georges-river-district/data/processed/all_seasons_bowling.csv",
        "clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_batting.csv",
        "clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_bowling.csv",
    ]
    changed = subprocess.run(["git", "diff", "--name-only", "--", *raw_paths], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    check("raw_sources_unchanged", not changed, changed or "none")

    write(VALIDATION, checks, ["check", "status", "detail"])
    overrides = sum(row["override_applies"] == "yes" for row in decisions)
    summary = [
        {"metric": "combined_report_rows", "value": len(detail)},
        {"metric": "override_decisions", "value": len(decisions)},
        {"metric": "overrides_applied", "value": overrides},
        {"metric": "source_rule_wins", "value": len(decisions) - overrides},
        {"metric": "highest_score_candidates", "value": sum(row["record_category"] == "highest_score" for row in candidates)},
        {"metric": "bbi_candidates", "value": sum(row["record_category"] == "bbi" for row in candidates)},
        {"metric": "validation_failures", "value": sum(row["status"] == "fail" for row in checks)},
    ]
    write(SUMMARY, summary, ["metric", "value"])
    failures = [row for row in checks if row["status"] == "fail"]
    print(f"checks={len(checks)} failures={len(failures)} overrides={overrides} source_rule_wins={len(decisions)-overrides} highest_scores={summary[4]['value']} bbi={summary[5]['value']}")
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
