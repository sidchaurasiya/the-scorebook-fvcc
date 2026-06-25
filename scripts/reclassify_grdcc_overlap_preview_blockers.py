#!/usr/bin/env python3
"""Reclassify GRDCC overlap discrepancies against current app-visible records."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "clubs" / "georges-river-district" / "data" / "processed"
OVERLAP_DIR = PROCESSED / "validation" / "source_overlap"
REVIEW_PATH = OVERLAP_DIR / "grdcc_overlap_high_priority_review.csv"
SUMMARY_PATH = OVERLAP_DIR / "grdcc_overlap_review_summary.csv"
PRIMARY_BATTING_PATH = PROCESSED / "all_seasons_batting.csv"
BLOCKERS_PATH = OVERLAP_DIR / "grdcc_true_preview_blockers.csv"
REVIEW_LATER_PATH = OVERLAP_DIR / "grdcc_overlap_review_later.csv"
REPORT_PATH = ROOT / "docs" / "georges_river_source_overlap_discrepancy_report.md"


def main() -> int:
    review = read_csv(REVIEW_PATH)
    batting = read_csv(PRIMARY_BATTING_PATH)
    visible = build_visible_batting_index(batting)

    provisional = [row for row in review if text(row.get("likely_app_impact")) == "private_preview_blocker"]
    blocker_audit = [classify_candidate(row, visible) for row in provisional]
    true_keys = {row_key(row) for row in blocker_audit if row["true_preview_blocker"] == "yes"}

    review_later = []
    for row in review:
        key = row_key(row)
        if key in true_keys:
            continue
        classified = next((item for item in blocker_audit if row_key(item) == key), None)
        output = dict(row)
        output["reclassified_app_visible"] = classified["app_visible"] if classified else "not_checked_non_blocker"
        output["reclassified_app_section"] = classified["app_section"] if classified else ""
        output["reclassification_reason"] = (
            classified["reason"]
            if classified
            else "Source discrepancy remains a review item but did not meet the provisional headline-blocker rule."
        )
        output["review_timing"] = "review_later"
        review_later.append(output)

    write_csv(BLOCKERS_PATH, blocker_audit, blocker_columns())
    write_csv(REVIEW_LATER_PATH, review_later, list(review_later[0]) if review_later else [])

    visible_count = sum(row["app_visible"] == "yes" for row in blocker_audit)
    blocker_count = len(true_keys)
    update_summary(len(provisional), visible_count, blocker_count, len(review_later))
    update_report(len(provisional), visible_count, blocker_count, len(review_later))
    print(f"provisional blockers checked: {len(provisional)}")
    print(f"app-visible provisional rows: {visible_count}")
    print(f"true preview blockers: {blocker_count}")
    print(f"review-later rows: {len(review_later)}")
    print(f"blocker audit: {BLOCKERS_PATH.relative_to(ROOT)}")
    print(f"review later: {REVIEW_LATER_PATH.relative_to(ROOT)}")
    return 0


def build_visible_batting_index(rows: list[dict[str, str]]) -> dict[tuple[str, str, str], list[str]]:
    player_season: dict[tuple[str, str], dict[str, float]] = defaultdict(lambda: defaultdict(float))
    player_career: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    player_season_hs: dict[tuple[str, str], float] = defaultdict(float)
    player_career_hs: dict[str, float] = defaultdict(float)

    for row in rows:
        player = normalize_name(row.get("canonical_player_name") or row.get("player_name"))
        season = text(row.get("season"))
        if not player or not season:
            continue
        key = (player, season)
        runs = number(row.get("battingAggregate"))
        innings = number(row.get("battingInnings"))
        not_outs = number(row.get("battingNotOuts"))
        fifties = number(row.get("batting50s"))
        hundreds = number(row.get("batting100s"))
        ducks = number(row.get("batting0s"))
        high_score = number(row.get("battingHighScore"))
        for metric, value in {
            "runs": runs,
            "innings": innings,
            "not_outs": not_outs,
            "50s": fifties,
            "100s": hundreds,
            "ducks": ducks,
        }.items():
            player_season[key][metric] += value
            player_career[player][metric] += value
        player_season_hs[key] = max(player_season_hs[key], high_score)
        player_career_hs[player] = max(player_career_hs[player], high_score)

    visible: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    if not player_season:
        return visible

    best_season_key = max(player_season, key=lambda key: (player_season[key]["runs"], -sort_name_rank(key[0])))
    visible[(best_season_key[0], best_season_key[1], "runs")].append("Hall of Fame / Best Batting Season / Greatest Seasons")

    top_high_scores = sorted(player_season_hs, key=lambda key: (-player_season_hs[key], key[0], key[1]))[:10]
    for key in top_high_scores:
        visible[(key[0], key[1], "high_score")].append("Hall of Fame / Iconic Performances / Highest Score")

    for season in {season for _, season in player_season}:
        season_rows = [key for key in player_season if key[1] == season]
        leader = max(season_rows, key=lambda key: (player_season[key]["runs"], -sort_name_rank(key[0])))
        visible[(leader[0], leader[1], "runs")].append("Season Overview / Run Leader")
        hs_leader = max(season_rows, key=lambda key: (player_season_hs[key], -sort_name_rank(key[0])))
        visible[(hs_leader[0], hs_leader[1], "high_score")].append("Season Overview / Highest Score")

    for player in player_career:
        seasons = [key for key in player_season if key[0] == player]
        best = max(seasons, key=lambda key: (player_season[key]["runs"], key[1]))
        visible[(best[0], best[1], "runs")].append("Player Profile / Best Batting Season")
        for key in seasons:
            if player_season_hs[key] == player_career_hs[player] and player_career_hs[player] > 0:
                visible[(key[0], key[1], "high_score")].append("Player Profile / Highest Score")

    run_leader = max(player_career, key=lambda player: (player_career[player]["runs"], -sort_name_rank(player)))
    for player, season in player_season:
        if player == run_leader and player_season[(player, season)]["runs"] > 0:
            visible[(player, season, "runs")].append("Hall of Fame / All-Time Runs Leader contribution")

    for metric, section in (("50s", "Hall of Fame / Record Holders / Most 50s"), ("100s", "Hall of Fame / Record Holders / Most 100s")):
        leader = max(player_career, key=lambda player: (player_career[player][metric], -sort_name_rank(player)))
        for player, season in player_season:
            if player == leader and player_season[(player, season)][metric] > 0:
                visible[(player, season, metric)].append(section)
    return visible


def classify_candidate(row: dict[str, str], visible: dict[tuple[str, str, str], list[str]]) -> dict[str, str]:
    key = (normalize_name(row.get("player_name")), text(row.get("season")), text(row.get("metric")))
    sections = sorted(set(visible.get(key, [])))
    app_visible = "yes" if sections else "no"
    anomaly = text(row.get("playcricket_anomaly_status")).lower()
    already_excluded = "excluded_from_app" in anomaly or "already_excluded" in anomaly
    high_severity = text(row.get("discrepancy_severity")) == "high"
    playcricket_anomalous = "high" in anomaly
    true_blocker = bool(sections and high_severity and playcricket_anomalous and not already_excluded)

    if true_blocker:
        reason = "The current PlayCricket value is high-severity anomalous and drives a visible headline output."
        action = "Fix or exclude the PlayCricket source row before private preview; use clean Excel only if verified."
    elif sections:
        reason = "The PlayCricket value contributes to a visible output, but the overlap difference alone is not a confirmed data error and PlayCricket is the sane default source."
        action = "Keep PlayCricket for preview and review the Excel discrepancy later; do not sum the sources."
    else:
        reason = "The player-season-metric does not currently drive a headline card or visible leaderboard."
        action = "Move to source-priority review later; keep sane PlayCricket as the overlap default."

    return {
        "player_name": row.get("player_name", ""),
        "season": row.get("season", ""),
        "metric": row.get("metric", ""),
        "excel_value": row.get("excel_value", ""),
        "playcricket_value": row.get("playcricket_value", ""),
        "recommended_source": row.get("recommended_source", ""),
        "app_output_file": "clubs/georges-river-district/data/processed/all_seasons_batting.csv" if sections else "",
        "app_section": "; ".join(sections),
        "app_visible": app_visible,
        "true_preview_blocker": "yes" if true_blocker else "no",
        "reason": reason,
        "suggested_action": action,
    }


def blocker_columns() -> list[str]:
    return [
        "player_name", "season", "metric", "excel_value", "playcricket_value", "recommended_source",
        "app_output_file", "app_section", "app_visible", "true_preview_blocker", "reason", "suggested_action",
    ]


def update_summary(provisional_count: int, visible_count: int, blocker_count: int, review_later_count: int) -> None:
    rows = read_csv(SUMMARY_PATH)
    values = {text(row.get("metric")): row.get("value", "") for row in rows}
    values["provisional_preview_blocker_count"] = provisional_count
    values["app_visible_provisional_rows"] = visible_count
    values["private_preview_blocker_count"] = blocker_count
    values["review_later_count"] = review_later_count
    write_csv(SUMMARY_PATH, [{"metric": key, "value": value} for key, value in values.items()], ["metric", "value"])


def update_report(provisional_count: int, visible_count: int, blocker_count: int, review_later_count: int) -> None:
    if not REPORT_PATH.exists():
        return
    content = REPORT_PATH.read_text(encoding="utf-8")
    marker = "## True App-Facing Preview Blockers"
    content = content.split(marker, 1)[0].rstrip()
    section = f"""

{marker}

- Provisional headline discrepancies checked: {provisional_count}.
- Rows that contribute to a current visible headline or leaderboard: {visible_count}.
- Confirmed true private-preview blockers: {blocker_count}.
- High-priority rows moved to source review later: {review_later_count}.
- Overlap discrepancies are source-priority review items, not automatically data errors. In overlap seasons the app uses sane PlayCricket by default and does not sum Excel with PlayCricket.
- A discrepancy blocks preview only when the selected app-facing PlayCricket row is itself high-severity anomalous, has not already been excluded, and drives a headline output.
- Review `grdcc_true_preview_blockers.csv` for the visibility trace and `grdcc_overlap_review_later.csv` for deferred source decisions.
"""
    REPORT_PATH.write_text(content + section, encoding="utf-8")


def row_key(row: dict[str, str]) -> tuple[str, str, str]:
    return normalize_name(row.get("player_name")), text(row.get("season")), text(row.get("metric"))


def normalize_name(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text(value).lower()).strip()


def text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def number(value: object) -> float:
    try:
        return float(str(value or "0").replace(",", ""))
    except ValueError:
        return 0.0


def sort_name_rank(value: str) -> int:
    return sum((index + 1) * ord(char) for index, char in enumerate(value))


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
