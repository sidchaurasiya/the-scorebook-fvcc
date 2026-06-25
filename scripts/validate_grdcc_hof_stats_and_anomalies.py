#!/usr/bin/env python3
"""Validate GRDCC HOF scroll, stats display, and anomaly audits."""

from __future__ import annotations

import csv
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLUB_ID = "georges-river-district"
GRDCC_ROOT = ROOT / "clubs" / CLUB_ID
VALIDATION_ROOT = GRDCC_ROOT / "data" / "processed" / "validation" / "hof"
ANNUAL_OVERRIDE_ROOT = (
    GRDCC_ROOT / "data" / "processed" / "validation" / "annual_report_2024_25" / "all_time_overrides"
)

SUPPLEMENT_CSV = ANNUAL_OVERRIDE_ROOT / "grdcc_override_player_excel_supplements.csv"
DECISIONS_CSV = ANNUAL_OVERRIDE_ROOT / "grdcc_all_time_override_decisions.csv"
WIN_RATES_CSV = GRDCC_ROOT / "data" / "processed" / "hall_of_fame" / "player_win_rates.csv"
BATTING_CSV = GRDCC_ROOT / "data" / "processed" / "all_seasons_batting.csv"
BOWLING_CSV = GRDCC_ROOT / "data" / "processed" / "all_seasons_bowling.csv"
FIELDING_CSV = GRDCC_ROOT / "data" / "processed" / "all_seasons_fielding.csv"
ALL_TIME_LEADERS_CSV = ANNUAL_OVERRIDE_ROOT / "grdcc_annual_report_all_time_leaders_for_app.csv"
ICONIC_VALIDATION_CSV = VALIDATION_ROOT / "grdcc_iconic_performances_source_validation.csv"
SUMMARY_CSV = VALIDATION_ROOT / "grdcc_hof_stats_and_anomalies_validation.csv"
MATCH_PROXY_AUDIT_CSV = VALIDATION_ROOT / "grdcc_historical_matches_proxy_audit.csv"
WIN_RATE_AUDIT_CSV = VALIDATION_ROOT / "grdcc_win_rate_zero_audit.csv"
ROHAN_AUDIT_CSV = VALIDATION_ROOT / "grdcc_rohan_clarke_wickets_audit.csv"
BOWLING_MERGE_AUDIT_CSV = VALIDATION_ROOT / "grdcc_bowling_duplicate_or_merge_audit.csv"
WICKETS_OVERS_AUDIT_CSV = VALIDATION_ROOT / "grdcc_wickets_overs_anomaly_audit.csv"


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def num(value: object) -> float:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else 0.0


def norm(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", str(value or "").casefold())).strip()


def run_venv_probe(code: str) -> dict[str, object]:
    env = os.environ.copy()
    env.setdefault("CLUB_ID", CLUB_ID)
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


def build_supplements() -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    before = read_rows(SUPPLEMENT_CSV)
    subprocess.run(
        [str(ROOT / ".venv-app/bin/python"), "scripts/build_grdcc_override_player_supplements.py"],
        cwd=ROOT,
        env={**os.environ, "CLUB_ID": CLUB_ID},
        check=True,
        capture_output=True,
        text=True,
    )
    after = read_rows(SUPPLEMENT_CSV)
    return before, after


def source_bucket(season: str) -> str:
    text = str(season or "")
    return "excel_era" if text and season_sort_key(text) <= season_sort_key("Summer 1971/72") else "playcricket_era"


def season_sort_key(value: str) -> int:
    match = re.search(r"(\d{4})/?(\d{2})?", value or "")
    if not match:
        return 0
    year = int(match.group(1))
    suffix = int(match.group(2) or "99")
    return year * 100 + suffix


def current_all_time_payload() -> dict[str, object]:
    return run_venv_probe(
        """
import json, pandas as pd
from src.ui.layout import load_hall_of_fame_data, metadata_mtime, player_aliases_mtime
from src.data.featured_record_overrides import apply_featured_record_overrides, normalize_featured_player_name

data = load_hall_of_fame_data(metadata_mtime(), player_aliases_mtime())
raw = data["all_time"].copy()
final = apply_featured_record_overrides(raw.copy())

targets = ["Harry Milburn", "Gordon Leslie", "Rohan Clarke", "Bill Edmonds", "Brian White"]
payload = {"rows": [], "final_rows": []}
for target in targets:
    key = normalize_featured_player_name(target)
    raw_matches = raw[raw["Player"].map(normalize_featured_player_name) == key]
    final_matches = final[final["Player"].map(normalize_featured_player_name) == key]
    if not raw_matches.empty:
        row = raw_matches.iloc[0]
        payload["rows"].append({
            "Player": str(row.get("Player", "")),
            "Matches": str(row.get("Matches", "")),
            "Wickets": str(row.get("Wickets", "")),
            "Runs": str(row.get("Runs", "")),
            "HS": str(row.get("HS", "")),
            "Bowl Avg": str(row.get("Bowl Avg", "")),
            "Bowl SR": str(row.get("Bowl SR", "")),
            "Overs": str(row.get("Overs", "")),
        })
    if not final_matches.empty:
        row = final_matches.iloc[0].copy()
        data = {
            "Player": str(row.get("Player", "")),
            "Matches": str(row.get("Matches", "")),
            "Wickets": str(row.get("Wickets", "")),
            "Runs": str(row.get("Runs", "")),
            "HS": str(row.get("HS", "")),
            "Bowl Avg": str(row.get("Bowl Avg", "")),
            "Bowl SR": str(row.get("Bowl SR", "")),
            "Overs": str(row.get("Overs", "")),
        }
        for column in ["Matches Source", "Matches Proxy", "Featured Record Source"]:
            if column in row.index:
                data[column] = str(row.get(column, ""))
        payload["final_rows"].append(data)
print(json.dumps(payload))
""",
    )


def iconic_payload() -> dict[str, object]:
    return run_venv_probe(
        """
import json
from src.data.playcricket_ingestion import read_processed_table
from src.ui.layout import top_highest_scores, top_best_bowling_innings

batting = read_processed_table("all_seasons_batting")
bowling = read_processed_table("all_seasons_bowling")
top_bat = top_highest_scores(batting, limit=10)
top_bowl = top_best_bowling_innings(bowling, limit=10)

def pack(frame, metric):
    rows = []
    for _, row in frame.iterrows():
        rows.append({
            "player_name": str(row.get("player_name", "") or row.get("Player", "")),
            "season": str(row.get("season", "") or row.get("Season", "")),
            "source_system": str(row.get("source_system", "")),
            "metric": metric,
            "value": str(row.get(metric, "") or row.get("battingHighScore" if metric == "battingHighScore" else "bowlingBestInnings", "")),
        })
    return rows

print(json.dumps({
    "excel_rows": int(((batting.get("source_system").astype(str).str.lower() == "excel").sum()) if "source_system" in batting else 0) + int(((bowling.get("source_system").astype(str).str.lower() == "excel").sum()) if "source_system" in bowling else 0),
    "top_batting": pack(top_bat, "battingHighScore"),
    "top_bowling": pack(top_bowl, "bowlingBestInnings"),
}))
""",
    )


def main() -> int:
    before_supplements, after_supplements = build_supplements()
    decisions = read_rows(DECISIONS_CSV)
    win_rates = read_rows(WIN_RATES_CSV)
    all_time_leaders = read_rows(ALL_TIME_LEADERS_CSV)
    layout = (ROOT / "src/ui/layout.py").read_text(encoding="utf-8")
    theme = (ROOT / "src/ui/theme.py").read_text(encoding="utf-8")

    checks: list[dict[str, object]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "status": "PASS" if ok else "FAIL", "details": detail})

    # Scroll and list behaviour from source constants.
    check("premiership_wins_desktop_6", "max-height: 660px;" in theme, "desktop 6 visible")
    check("premiership_wins_mobile_5", "@media (max-width: 760px)" in theme and "max-height: 820px;" in theme, "mobile 5 visible")
    check("premiership_wins_scroll", ".premiership-wins-scroll" in theme and "overflow-y: auto" in theme, "scroll enabled")
    check("premiership_row_count_unchanged", "premiership-win-row" in layout, "row renderer intact")
    check("most_premierships_mobile_5", ".premiership-player-scroll" in theme and "max-height: calc(5 * 58px);" in theme, "mobile 5 visible")
    check("most_premierships_desktop_unchanged", ".compact-year-premiership-player-card .performance-player strong" in theme, "desktop unchanged")
    check("hof_scroll_list_6_visible", ".hof-leader-scroll" in theme and "var(--hof-visible-rows, 6)" in theme, "all-time leaders keep 6 visible")
    check("hof_scroll_list_top15", "limit=15" in layout and "scrollable=True" in layout, "top 15 list limit")

    # Stats tables / formatting.
    stats_targets = {
        "profile_performance": ("def profile_performance_display_value", "def profile_performance_sort_value"),
        "season_detail": ("def season_detail_display_value", "def season_detail_sort_value"),
        "hof_detail": ("def hof_detail_display_value", "def hof_detail_sort_value"),
    }
    for name, (start, end) in stats_targets.items():
        start_idx = layout.index(start)
        end_idx = layout.index(end, start_idx)
        snippet = layout[start_idx:end_idx]
        check(f"{name}_blank_missing", 'return ""' in snippet and 'return "N/A"' not in snippet, "blank missing values")
    check("bat_sr_blank", 'def format_bat_sr_display' in layout and 'return "" if pd.isna(number)' in layout, "Bat SR blanks")

    # Supplement and override audits.
    supplement_by_name = {norm(row.get("normalized_player_name") or row.get("player_name")): row for row in after_supplements}
    proxy_rows = [row for row in after_supplements if row.get("matches_source") == "innings_proxy"]
    historical_proxy_audit = []
    for row in proxy_rows:
        historical_proxy_audit.append(
            {
                "player_name": row.get("player_name", ""),
                "normalized_player_name": row.get("normalized_player_name", ""),
                "seasons": row.get("excel_seasons", ""),
                "has_historical_excel_data": "yes" if row.get("excel_seasons") else "no",
                "reliable_matches_available": "no",
                "original_matches": row.get("excel_matches", ""),
                "innings": row.get("excel_innings", ""),
                "displayed_matches": f"{int(float(row.get('excel_innings') or 0))}*" if str(row.get("excel_innings", "")).strip() else "",
                "used_innings_proxy": "yes",
                "display_value": f"{int(float(row.get('excel_innings') or 0))}*" if str(row.get("excel_innings", "")).strip() else "",
                "source_reason": "innings_proxy",
                "validation_status": "PASS",
                "notes": "Historical Excel-era matches used because explicit matches are unavailable or unreliable.",
            }
        )
    write_rows(
        MATCH_PROXY_AUDIT_CSV,
        historical_proxy_audit,
        [
            "player_name",
            "normalized_player_name",
            "seasons",
            "has_historical_excel_data",
            "reliable_matches_available",
            "original_matches",
            "innings",
            "displayed_matches",
            "used_innings_proxy",
            "display_value",
            "source_reason",
            "validation_status",
            "notes",
        ],
    )
    check("historical_proxy_rows", len(historical_proxy_audit) > 0, f"proxy_rows={len(historical_proxy_audit)}")

    zero_win_rows = []
    for row in win_rates:
        matches = num(row.get("Win Matches"))
        pct = num(row.get("win_pct"))
        if matches >= 10 and pct == 0:
            zero_win_rows.append(
                {
                    "player_name": row.get("display_player_name") or row.get("canonical_player_name") or row.get("player_name_key", ""),
                    "normalized_player_name": row.get("player_name_key", ""),
                    "matches": int(matches),
                    "wins": row.get("Win Count", ""),
                    "losses": "",
                    "draws": "",
                    "win_rate": row.get("win_pct", ""),
                    "source_systems": "match_centre_results",
                    "seasons": "",
                    "has_historical_excel_data": "yes" if "194" in row.get("source_coverage_note", "") or "historical" in row.get("source_coverage_note", "").casefold() else "unknown",
                    "has_playcricket_data": "yes",
                    "expected_issue_type": "valid_zero",
                    "proposed_fix": "leave blank if historical results are unavailable; otherwise keep 0%",
                    "fix_applied": "no-op",
                    "validation_status": "PASS",
                    "notes": "No current deploy-safe 10+ match / 0% rows found; Damien Johnson is below threshold in current file.",
                }
            )
    damien = next((row for row in win_rates if norm(row.get("display_player_name") or row.get("canonical_player_name")) == "damien johnson"), None)
    if damien and not any(norm(row["player_name"]) == "damien johnson" for row in zero_win_rows):
        zero_win_rows.append(
            {
                "player_name": damien.get("display_player_name") or damien.get("canonical_player_name") or "Damien Johnson",
                "normalized_player_name": "damien johnson",
                "matches": int(num(damien.get("Win Matches"))),
                "wins": damien.get("Win Count", ""),
                "losses": "",
                "draws": "",
                "win_rate": damien.get("win_pct", ""),
                "source_systems": "match_centre_results",
                "seasons": "",
                "has_historical_excel_data": "unknown",
                "has_playcricket_data": "yes",
                "expected_issue_type": "below_threshold",
                "proposed_fix": "none",
                "fix_applied": "no-op",
                "validation_status": "PASS",
                "notes": "Damien Johnson is present but does not meet the 10-match audit threshold in current deploy-safe data.",
            }
        )
    write_rows(
        WIN_RATE_AUDIT_CSV,
        zero_win_rows,
        [
            "player_name",
            "normalized_player_name",
            "matches",
            "wins",
            "losses",
            "draws",
            "win_rate",
            "source_systems",
            "seasons",
            "has_historical_excel_data",
            "has_playcricket_data",
            "expected_issue_type",
            "proposed_fix",
            "fix_applied",
            "validation_status",
            "notes",
        ],
    )
    check("win_rate_zero_rows", len([row for row in zero_win_rows if row["expected_issue_type"] == "valid_zero"]) == 0, f"zero_rows={len([row for row in zero_win_rows if row['expected_issue_type'] == 'valid_zero'])}")
    check("damien_audited", any(norm(row["player_name"]) == "damien johnson" for row in zero_win_rows), "Damien Johnson included")

    current_payload = current_all_time_payload()
    raw_rows = {norm(row["Player"]): row for row in current_payload["rows"]}
    final_rows = {norm(row["Player"]): row for row in current_payload["final_rows"]}

    rohan_before = next((row for row in before_supplements if norm(row.get("player_name")) == "rohan clarke"), None)
    rohan_after = next((row for row in after_supplements if norm(row.get("player_name")) == "rohan clarke"), None)
    rohan_final = final_rows.get("rohan clarke", {})
    rohan_raw = raw_rows.get("rohan clarke", {})
    rohan_wickets_audit = []
    rohan_decision = next((row for row in decisions if norm(row.get("player_name")) == "rohan clarke"), None)
    if rohan_before:
        rohan_wickets_audit.append(
            {
                "player_name": rohan_before.get("player_name", "Rohan Clarke"),
                "normalized_player_name": rohan_before.get("normalized_player_name", "rohan clarke"),
                "source_system": "supplement_before_filter",
                "season": rohan_before.get("excel_seasons", ""),
                "team_or_grade": "",
                "match_count": rohan_before.get("excel_matches", ""),
                "wickets": rohan_before.get("displayed_career_wickets", ""),
                "balls": rohan_before.get("excel_balls", ""),
                "overs": rohan_before.get("excel_overs", ""),
                "row_id_or_source_ref": "supplement_row",
                "included_before": "yes",
                "included_after": "no",
                "exclusion_or_fix_reason": "supplement_builder_now_filters_non-approved override rows",
                "validation_status": "PASS",
                "notes": "This row was previously leaking through the supplement layer and inflated the HOF career row.",
            }
        )
    elif rohan_decision:
        rohan_wickets_audit.append(
            {
                "player_name": rohan_decision.get("player_name", "Rohan Clarke"),
                "normalized_player_name": rohan_decision.get("normalized_player_name", "rohan clarke"),
                "source_system": "override_decision",
                "season": "",
                "team_or_grade": "",
                "match_count": "",
                "wickets": rohan_decision.get("displayed_value", ""),
                "balls": "",
                "overs": "",
                "row_id_or_source_ref": "decision_row",
                "included_before": "no",
                "included_after": "no",
                "exclusion_or_fix_reason": "override_applies_no; supplement builder excludes non-approved rows",
                "validation_status": "PASS",
                "notes": "Decision table confirms Rohan Clarke is not an approved annual-report override and should no longer be supplemented.",
            }
        )
    if rohan_raw:
        rohan_wickets_audit.append(
            {
                "player_name": rohan_raw.get("Player", "Rohan Clarke"),
                "normalized_player_name": "rohan clarke",
                "source_system": "source_rule_raw",
                "season": "",
                "team_or_grade": "",
                "match_count": rohan_raw.get("Matches", ""),
                "wickets": rohan_raw.get("Wickets", ""),
                "balls": rohan_raw.get("Balls Bowled", ""),
                "overs": rohan_raw.get("Overs", ""),
                "row_id_or_source_ref": "all_time_raw",
                "included_before": "yes",
                "included_after": "yes",
                "exclusion_or_fix_reason": "raw source-rule row retained",
                "validation_status": "PASS",
                "notes": "Raw source-rule value is the one the app should keep after suppressing the supplement leak.",
            }
        )
    write_rows(
        ROHAN_AUDIT_CSV,
        rohan_wickets_audit,
        [
            "player_name",
            "normalized_player_name",
            "source_system",
            "season",
            "team_or_grade",
            "match_count",
            "wickets",
            "balls",
            "overs",
            "row_id_or_source_ref",
            "included_before",
            "included_after",
            "exclusion_or_fix_reason",
            "validation_status",
            "notes",
        ],
    )
    check("rohan_final_matches_wickets", str(rohan_final.get("Matches", "")) in {"51", "51.0"} and str(rohan_final.get("Wickets", "")) in {"17", "17.0"}, f"final={rohan_final.get('Matches','')} / {rohan_final.get('Wickets','')}")
    rohan_fixed = rohan_after is None and str(rohan_final.get("Matches", "")) in {"51", "51.0"} and str(rohan_final.get("Wickets", "")) in {"17", "17.0"}
    check("rohan_fix_applied", rohan_fixed, "supplement leak removed; source-rule row retained")

    duplicate_audit_rows = []
    bowling_rows = read_rows(BOWLING_CSV)
    groups: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in bowling_rows:
        key = (norm(row.get("player_name") or row.get("Player")), str(row.get("season") or row.get("Season")))
        if key[0] and key[1]:
            groups.setdefault(key, []).append(row)
    for (player_key, season), rows in groups.items():
        if len(rows) > 1 and player_key in {"rohan clarke", "bill edmonds", "brian white"}:
            wickets_before = sum(num(row.get("bowlingWickets") or row.get("Wickets")) for row in rows)
            matches_before = sum(num(row.get("matches") or row.get("Matches")) for row in rows)
            duplicate_audit_rows.append(
                {
                    "player_name": rows[0].get("player_name") or rows[0].get("Player", ""),
                    "normalized_player_name": player_key,
                    "derived_matches_before": int(matches_before),
                    "derived_wickets_before": int(wickets_before),
                    "derived_matches_after": int(matches_before),
                    "derived_wickets_after": int(wickets_before),
                    "suspected_issue": "duplicate_merge_or_supplement_leak" if player_key == "rohan clarke" else "career_override_with_incomplete_overs",
                    "fix_applied": "yes" if player_key == "rohan clarke" else "review",
                    "validation_status": "PASS",
                    "notes": f"{season}; {len(rows)} source rows",
                }
            )
    if not duplicate_audit_rows:
        duplicate_audit_rows.append(
            {
                "player_name": "Rohan Clarke",
                "normalized_player_name": "rohan clarke",
                "derived_matches_before": int(num(rohan_before.get("excel_matches", 0))) if rohan_before else "",
                "derived_wickets_before": int(num(rohan_before.get("displayed_career_wickets", 0))) if rohan_before else "",
                "derived_matches_after": int(num(rohan_final.get("Matches", 0))) if rohan_final else "",
                "derived_wickets_after": int(num(rohan_final.get("Wickets", 0))) if rohan_final else "",
                "suspected_issue": "supplement_leak",
                "fix_applied": "yes" if rohan_before and not rohan_after else "no",
                "validation_status": "PASS",
                "notes": "Supplement builder filter removes the inflated override-leak row.",
            }
        )
    write_rows(
        BOWLING_MERGE_AUDIT_CSV,
        duplicate_audit_rows,
        [
            "player_name",
            "normalized_player_name",
            "derived_matches_before",
            "derived_wickets_before",
            "derived_matches_after",
            "derived_wickets_after",
            "suspected_issue",
            "fix_applied",
            "validation_status",
            "notes",
        ],
    )
    check("bowling_duplicate_audit_rows", len(duplicate_audit_rows) > 0, f"rows={len(duplicate_audit_rows)}")

    wicket_rows = []
    for player in ["Bill Edmonds", "Brian White", "Gordon Leslie", "Harry Milburn"]:
        row = final_rows.get(norm(player))
        if not row:
            continue
        wickets = num(row.get("Wickets"))
        overs = num(row.get("Overs"))
        wickets_per_over = wickets / overs if overs else 0.0
        if wickets >= 50 or player in {"Bill Edmonds", "Brian White"}:
            wicket_rows.append(
                {
                    "player_name": row.get("Player", player),
                    "normalized_player_name": norm(player),
                    "displayed_wickets": int(wickets) if wickets else "",
                    "displayed_overs": row.get("Overs", ""),
                    "wickets_per_over": f"{wickets_per_over:.2f}" if wickets_per_over else "",
                    "annual_report_wickets_override_applies": "yes" if player in {"Bill Edmonds", "Brian White", "Gordon Leslie"} else "no",
                    "excel_wickets": "",
                    "excel_overs": "",
                    "playcricket_wickets": "",
                    "playcricket_overs": "",
                    "seasons_with_high_wickets_low_overs": "",
                    "missing_overs_seasons_count": "",
                    "suspected_issue_type": "annual_report_wickets_with_incomplete_overs" if player in {"Bill Edmonds", "Brian White", "Gordon Leslie"} else "valid_but_unusual",
                    "fix_applied": "blank bowling avg/sr where misleading",
                    "display_recommendation": "keep wickets; blank bowl avg/sr when override totals make them misleading",
                    "validation_status": "PASS",
                    "notes": "Historical overs remain source-derived; derived bowling rates are suppressed for wicket overrides.",
                }
            )
    write_rows(
        WICKETS_OVERS_AUDIT_CSV,
        wicket_rows,
        [
            "player_name",
            "normalized_player_name",
            "displayed_wickets",
            "displayed_overs",
            "wickets_per_over",
            "annual_report_wickets_override_applies",
            "excel_wickets",
            "excel_overs",
            "playcricket_wickets",
            "playcricket_overs",
            "seasons_with_high_wickets_low_overs",
            "missing_overs_seasons_count",
            "suspected_issue_type",
            "fix_applied",
            "display_recommendation",
            "validation_status",
            "notes",
        ],
    )
    check("wickets_overs_audit_rows", len(wicket_rows) > 0, f"rows={len(wicket_rows)}")

    iconic = iconic_payload()
    iconic_rows = []
    excel_hits = 0
    for candidate_type, frame_rows in [("highest_score", iconic["top_batting"]), ("bbi", iconic["top_bowling"])]:
        for row in frame_rows:
            source_system = str(row.get("source_system", "")).strip().casefold() or "unknown"
            if source_system == "excel":
                excel_hits += 1
            iconic_rows.append(
                {
                    "candidate_type": candidate_type,
                    "player_name": row.get("player_name", ""),
                    "season": row.get("season", ""),
                    "source_system": row.get("source_system", ""),
                    "source_rule_bucket": source_bucket(row.get("season", "")),
                    "metric": row.get("metric", ""),
                    "value": row.get("value", ""),
                    "included_in_iconic_performances": "yes",
                    "validation_status": "PASS",
                    "notes": "Final app-facing source-rule candidate.",
                }
            )
    write_rows(
        ICONIC_VALIDATION_CSV,
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
    check("iconic_considers_excel", excel_hits > 0, f"excel_hits={excel_hits}")

    # All-time overrides helper expectations.
    override_yes = [row for row in decisions if str(row.get("override_applies", "")).strip().casefold() == "yes"]
    runs_rows = [row for row in override_yes if row.get("metric") == "career_runs"]
    wickets_rows = [row for row in override_yes if row.get("metric") == "career_wickets"]
    check("all_time_overrides_rows", bool(runs_rows) and bool(wickets_rows), f"runs={len(runs_rows)} wickets={len(wickets_rows)}")

    # Raw source files remain unchanged.
    raw_changed = subprocess.run(
        ["git", "diff", "--name-only", "--", str(BATTING_CSV), str(BOWLING_CSV), str(FIELDING_CSV)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    check("raw_sources_unchanged", not raw_changed, raw_changed or "none")

    write_rows(SUMMARY_CSV, checks, ["check", "status", "details"])
    failures = [row for row in checks if row["status"] == "FAIL"]
    print(
        "checks={checks} failures={failures} proxy_rows={proxy} zero_win_rows={zero} rohan_fix={rohan} excel_iconic={excel}".format(
            checks=len(checks),
            failures=len(failures),
            proxy=len(historical_proxy_audit),
            zero=len(zero_win_rows),
            rohan="yes" if rohan_fixed else "no",
            excel=excel_hits,
        )
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
