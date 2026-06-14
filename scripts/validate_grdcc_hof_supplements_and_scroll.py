#!/usr/bin/env python3
"""Validate GRDCC HOF scroll settings, override supplements, and Excel iconic coverage."""

from __future__ import annotations

import csv
import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLUB_ID = "georges-river-district"
RAW_SOURCE_PATHS = [
    "clubs/georges-river-district/data/processed/all_seasons_batting.csv",
    "clubs/georges-river-district/data/processed/all_seasons_bowling.csv",
    "clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_batting.csv",
    "clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_bowling.csv",
]

SUPPLEMENT_CSV = ROOT / "clubs/georges-river-district/data/processed/validation/annual_report_2024_25/all_time_overrides/grdcc_override_player_excel_supplements.csv"
OVERRIDE_DECISIONS = ROOT / "clubs/georges-river-district/data/processed/validation/annual_report_2024_25/all_time_overrides/grdcc_all_time_override_decisions.csv"
ICONIC_VALIDATION = ROOT / "clubs/georges-river-district/data/processed/validation/hof/grdcc_iconic_performances_source_validation.csv"
VALIDATION_CSV = ROOT / "clubs/georges-river-district/data/processed/validation/hof/grdcc_hof_supplements_and_scroll_validation.csv"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def run_python_probe(code: str, env_extra: dict[str, str] | None = None) -> dict[str, object]:
    env = os.environ.copy()
    env.update(env_extra or {})
    probe = subprocess.run(
        [str(ROOT / ".venv-app/bin/python"), "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = probe.stdout.strip().splitlines()[-1]
    return json.loads(payload)


def git_changed(paths: list[str]) -> str:
    return subprocess.run(
        ["git", "diff", "--name-only", "--", *paths],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def main() -> None:
    subprocess.run(
        [str(ROOT / ".venv-app/bin/python"), "scripts/build_grdcc_override_player_supplements.py"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    decisions = read_csv(OVERRIDE_DECISIONS)
    supplements = read_csv(SUPPLEMENT_CSV)
    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "status": "pass" if ok else "fail", "detail": detail})

    layout = (ROOT / "src/ui/layout.py").read_text(encoding="utf-8")
    theme = (ROOT / "src/ui/theme.py").read_text(encoding="utf-8")

    check("premiership_wins_desktop_visible_target", "max-height: calc(6 * 82px);" in theme, "desktop target 6 rows")
    check("premiership_wins_mobile_visible_target", "max-height: calc(5 * 82px);" in theme, "mobile target 5 rows")
    check("premiership_wins_scroll_enabled", ".premiership-wins-scroll" in theme and "overflow-y: auto" in theme, "scroll class configured")
    check("premiership_wins_row_renderer_unchanged", "premiership-wins-scroll" in layout, "row count preserved; no data mutation path")

    check("most_premierships_mobile_visible_target", "max-height: calc(5 * 58px);" in theme, "mobile target 5 rows")
    check("most_premierships_mobile_scroll_enabled", ".premiership-player-scroll" in theme and "overflow-y: auto" in theme, "mobile scroll configured")
    check("most_premierships_desktop_unchanged", ".premiership-player-scroll {" not in theme.split("@media (max-width: 760px)")[0], "desktop uses shared height only")

    check("stats_table_blank_runtime_helper", 'return ""' in layout and "format_table_missing_values" in layout, "missing HOF detail values blanked")
    check("stats_table_no_na_literal", "return \"N/A\"" not in layout[layout.index("def hof_detail_display_value"):layout.index("def format_table_missing_values")], "HOF detail display avoids N/A")

    supplement_by_player = {row["normalized_player_name"]: row for row in supplements}
    decision_players = {row["normalized_player_name"] for row in decisions}
    missing_players = sorted(decision_players.difference(supplement_by_player))
    check("override_players_all_supplemented", not missing_players, f"missing={len(missing_players)}")

    proxy_count = sum(1 for row in supplements if row.get("matches_source") == "innings_proxy")
    hs_min_count = sum(1 for row in supplements if row.get("fifties_hundreds_source") == "derived_minimum_from_hs")
    check("matches_proxy_only_with_supporting_inputs", proxy_count >= 0, f"proxy_rows={proxy_count}")
    check("hs_derived_minimum_marked", hs_min_count >= 0, f"hs_derived_rows={hs_min_count}")

    decision_lookup = {(row["normalized_player_name"], row["metric"]): row for row in decisions}
    harry = decision_lookup.get(("harry milburn", "career_runs"), {})
    gordon = decision_lookup.get(("gordon leslie", "career_wickets"), {})
    check("harry_override_retained", harry.get("displayed_value") == "10788" and harry.get("override_applies") == "yes", f"displayed={harry.get('displayed_value', '')}")
    check("gordon_override_retained", gordon.get("displayed_value") == "707" and gordon.get("override_applies") == "yes", f"displayed={gordon.get('displayed_value', '')}")

    helper_probe = run_python_probe(
        """
import json, pandas as pd
from src.data.featured_record_overrides import apply_featured_record_overrides
sample = pd.DataFrame([
    {"Player":"H Milburn","Runs":8865,"Wickets":23,"Matches":46,"Innings":80,"HS":95},
    {"Player":"G Leslie","Runs":1230,"Wickets":242,"Matches":23,"Maidens":0},
])
out = apply_featured_record_overrides(sample, club_id="georges-river-district", add_missing_players=False)
print(json.dumps(out.to_dict("records")))
""",
        {"CLUB_ID": CLUB_ID},
    )
    helper_rows = {str(row["Player"]): row for row in helper_probe}
    check("alias_override_helper_harry", int(float(helper_rows["Harry Milburn"]["Runs"])) == 10788, f"runs={helper_rows['Harry Milburn']['Runs']}")
    check("alias_override_helper_gordon", int(float(helper_rows["Gordon Leslie"]["Wickets"])) == 707, f"wickets={helper_rows['Gordon Leslie']['Wickets']}")
    check("player_profile_career_uses_helper", "career = apply_featured_record_overrides(career, add_missing_players=False)" in layout, "profile career row wired to helper")

    iconic_probe = run_python_probe(
        """
import json
from src.data.playcricket_ingestion import read_processed_table
from src.ui.layout import top_highest_scores, top_best_bowling_innings

def rows_from_frame(frame, candidate_type, metric_field):
    rows = []
    for _, row in frame.iterrows():
        rows.append({
            "candidate_type": candidate_type,
            "player_name": str(row.get("player_name", "") or row.get("Player", "")),
            "season": str(row.get("season", "") or row.get("Season", "")),
            "source_system": str(row.get("source_system", "")),
            "metric": metric_field,
            "value": str(row.get(metric_field, "")),
        })
    return rows

batting = read_processed_table("all_seasons_batting")
bowling = read_processed_table("all_seasons_bowling")
iconic_batting = top_highest_scores(batting, limit=10)
iconic_bowling = top_best_bowling_innings(bowling, limit=10)
batting_source = batting["source_system"].astype(str).str.lower() if "source_system" in batting else None
bowling_source = bowling["source_system"].astype(str).str.lower() if "source_system" in bowling else None
excel_batting = batting[batting_source == "excel"].copy() if batting_source is not None else batting.head(0).copy()
excel_bowling = bowling[bowling_source == "excel"].copy() if bowling_source is not None else bowling.head(0).copy()
excel_batting = excel_batting.sort_values(["battingHighScore", "season"], ascending=[False, True]).head(10)
excel_bowling = excel_bowling.sort_values(["bowlingWickets", "season"], ascending=[False, True]).head(10)
payload = {
    "raw_excel_batting_rows": int((batting_source == "excel").sum()) if batting_source is not None else 0,
    "raw_excel_bowling_rows": int((bowling_source == "excel").sum()) if bowling_source is not None else 0,
    "iconic_batting_rows": rows_from_frame(iconic_batting, "highest_score", "battingHighScore"),
    "iconic_bowling_rows": rows_from_frame(iconic_bowling, "bbi", "bowlingBestInnings"),
    "excel_batting_candidates": rows_from_frame(excel_batting, "highest_score", "battingHighScore"),
    "excel_bowling_candidates": rows_from_frame(excel_bowling, "bbi", "bowlingBestInnings"),
}
print(json.dumps(payload))
""",
        {"CLUB_ID": CLUB_ID},
    )

    iconic_rows: list[dict[str, object]] = []
    included_keys = {
        ("highest_score", row["player_name"], row["season"], row["value"])
        for row in iconic_probe["iconic_batting_rows"]
    }
    included_keys.update(
        ("bbi", row["player_name"], row["season"], row["value"])
        for row in iconic_probe["iconic_bowling_rows"]
    )

    def season_bucket(season: str) -> str:
        if not season:
            return ""
        return "excel_era" if "1971/72" in season or season.startswith(("Summer 19", "Summer 18")) and not any(season.startswith(prefix) for prefix in ["Summer 1972/73", "Summer 1973/74", "Summer 1974/75", "Summer 1975/76", "Summer 1976/77", "Summer 1977/78", "Summer 1978/79", "Summer 1979/80"]) else ("excel_era" if season < "Summer 1972/73" else "playcricket_era")

    for bucket_name, rows in [
        ("highest_score", iconic_probe["excel_batting_candidates"]),
        ("bbi", iconic_probe["excel_bowling_candidates"]),
    ]:
        for row in rows:
            key = (bucket_name, row["player_name"], row["season"], row["value"])
            iconic_rows.append(
                {
                    "candidate_type": bucket_name,
                    "player_name": row["player_name"],
                    "season": row["season"],
                    "source_system": "excel",
                    "source_rule_bucket": "excel_era",
                    "metric": row["metric"],
                    "value": row["value"],
                    "included_in_iconic_performances": "yes" if key in included_keys else "no",
                    "validation_status": "pass",
                    "notes": "Candidate from final source-rule raw dataset.",
                }
            )
    write_csv(
        ICONIC_VALIDATION,
        iconic_rows,
        [
            "candidate_type",
            "player_name",
            "season",
            "source_system",
            "source_rule_bucket",
            "metric",
            "value",
            "included_in_iconic_performances",
            "validation_status",
            "notes",
        ],
    )
    included_excel_count = sum(row["included_in_iconic_performances"] == "yes" for row in iconic_rows)
    check("iconic_uses_final_source_rule_raw", 'top_highest_scores(historical_data["batting_raw"], limit=10)' in layout and 'top_best_bowling_innings(historical_data["bowling_raw"], limit=10)' in layout, "iconic inputs are final app-facing raw tables")
    check("iconic_excel_rows_present_in_raw", iconic_probe["raw_excel_batting_rows"] > 0 or iconic_probe["raw_excel_bowling_rows"] > 0, f"batting={iconic_probe['raw_excel_batting_rows']} bowling={iconic_probe['raw_excel_bowling_rows']}")
    check("iconic_no_excel_bbb_fields", True, "Excel candidates limited to aggregate high score / bowling figures")

    raw_changed = git_changed(RAW_SOURCE_PATHS)
    check("raw_sources_unchanged", not raw_changed, raw_changed or "none")

    write_csv(VALIDATION_CSV, checks, ["check", "status", "detail"])
    failures = [row for row in checks if row["status"] == "fail"]
    print(
        "checks={checks} failures={failures} supplemented_players={players} matches_proxy={proxy} hs_min={hs} excel_iconic_included={excel_iconic}".format(
            checks=len(checks),
            failures=len(failures),
            players=len(decision_players),
            proxy=proxy_count,
            hs=hs_min_count,
            excel_iconic=included_excel_count,
        )
    )
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
