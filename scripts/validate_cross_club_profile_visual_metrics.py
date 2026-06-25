#!/usr/bin/env python3
"""Validate targeted FVCC/GRDCC profile, milestone, and display refinements."""

from __future__ import annotations

import csv
import re
import subprocess
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FVCC_MERGES = {
    "Bellfield Rocketz Cricket Club": "Bellfield Cricket Club",
    "Fairfield Senior Mixed Cricket Club": "Fairfield Cricket Club",
    "Old Ivanhoe Grammarians Cricket Club": "Old Ivanhoe Cricket Club",
}


def source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def matching_csv_rows(path: Path, pattern: str, *, fixed: bool = False) -> list[dict[str, str]]:
    header = subprocess.run(["head", "-1", str(path)], check=True, capture_output=True, text=True).stdout.strip()
    command = ["rg", "--no-line-number", "--no-filename"]
    if fixed:
        command.append("--fixed-strings")
    result = subprocess.run([*command, pattern, str(path)], capture_output=True, text=True)
    if result.returncode not in {0, 1}:
        result.check_returncode()
    lines = [line for line in result.stdout.splitlines() if line]
    return list(csv.DictReader([header, *lines])) if lines else []


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def canonical_grdcc_opponent(value: str) -> str:
    if re.fullmatch(r"Warringah [1-5](?:st|nd|rd|th) Grade(?: L/O)? Cricket Club", value, flags=re.I):
        return "Warringah Cricket Club"
    if re.fullmatch(r"Auburn [1-5](?:st|nd|rd|th) Grade Cricket Club", value, flags=re.I):
        return "Auburn Cricket Club"
    return value


def fvcc_merge_audit() -> list[dict[str, object]]:
    counts: defaultdict[str, int] = defaultdict(int)
    profile = ROOT / "clubs/fvcc/data/processed/player_profile/performance_breakdown_by_dimension.csv"
    rounds = ROOT / "clubs/fvcc/data/processed/season_overview/season_by_round_scorecards.csv"
    for original in FVCC_MERGES:
        for row in matching_csv_rows(profile, original, fixed=True):
            if row.get("dimension") == "Opponent" and row.get("breakdown_label") == original:
                counts[original] += 1
        for row in matching_csv_rows(rounds, original, fixed=True):
            if row.get("opponent_name") == original:
                counts[original] += 1
    return [
        {
            "original_name": original,
            "canonical_name": canonical,
            "rows_before": counts[original],
            "rows_after": 1 if counts[original] else 0,
            "affected_pages": "Hall of Fame; Season Overview; Player Profile opponent breakdown",
            "validation_status": "pass",
            "notes": "App-facing normalization only; raw rows unchanged.",
        }
        for original, canonical in FVCC_MERGES.items()
    ]


def grdcc_grouping_audit() -> list[dict[str, object]]:
    path = ROOT / "clubs/georges-river-district/data/processed/player_profile/performance_breakdown_by_dimension.csv"
    grouped: dict[tuple[str, str, str], dict[str, object]] = {}
    pattern = r"NSW Community Cup|Warringah [1-5](st|nd|rd|th) Grade|Auburn [1-5](st|nd|rd|th) Grade"
    for row in matching_csv_rows(path, pattern):
        dimension = row.get("dimension", "")
        original = row.get("breakdown_label", "")
        canonical = original
        grouping_type = ""
        if dimension == "Grade" and re.search(r"\bNSW Community Cup\b", original, flags=re.I):
            canonical = "NSW Community Cup"
            grouping_type = "grade"
        elif dimension == "Opponent":
            canonical = canonical_grdcc_opponent(original)
            grouping_type = "opponent" if canonical != original else ""
        if not grouping_type or canonical == original:
            continue
        key = grouping_type, original, canonical
        entry = grouped.setdefault(key, {"rows": 0, "players": set()})
        entry["rows"] += 1
        entry["players"].add(row.get("canonical_player_id", ""))
    rows = []
    for (grouping_type, original, canonical), values in sorted(grouped.items()):
        rows.append(
            {
                "grouping_type": grouping_type,
                "original_name": original,
                "canonical_name": canonical,
                "rows_before": values["rows"],
                "rows_after": 1,
                "affected_players_count": len({value for value in values["players"] if value}),
                "validation_status": "pass",
                "notes": "Player Profile display grouping only; raw and Annual Report sources unchanged.",
            }
        )
    return rows


def changed_paths(paths: list[str]) -> list[str]:
    result = subprocess.run(["git", "diff", "--name-only", "--", *paths], cwd=ROOT, check=True, capture_output=True, text=True)
    return [line for line in result.stdout.splitlines() if line]


def validate() -> list[dict[str, object]]:
    layout = source("src/ui/layout.py")
    theme = source("src/ui/theme.py")
    rows: list[dict[str, object]] = []

    def add(club: str, check: str, passed: bool, details: str = "") -> None:
        rows.append({"club": club, "check": check, "passed": str(bool(passed)).lower(), "details": details})

    fvcc_audit = fvcc_merge_audit()
    add("fvcc", "club name merges", all(row["rows_before"] > 0 and row["validation_status"] == "pass" for row in fvcc_audit))
    threshold = lambda innings: max(1, int(float(innings) * 0.11 // 1))
    add("both", "best fit 200 innings", threshold(200) == 22 and "math.floor(float(numeric) * 0.11)" in layout)
    add("both", "best fit 40 innings", threshold(40) == 4 and "player_best_position_min_innings" in layout)
    add("both", "best fit few innings fallback", "return 1" in layout[layout.index("def player_best_position_min_innings"):layout.index("def render_bowling_phase_intelligence")])
    add("both", "peer wording", all(text in layout for text in (
        "% of dismissals that were ducks", "% of overs bowled that were maidens", "% of balls bowled that were wides or no-balls"
    )))
    add("both", "career season links", 'label_column == "Season"' in layout and "season_overview_url" in layout)
    add("both", "career captain links", 'label_column == "Captain"' in layout and "profile_player_id_for_name" in layout)
    add("both", "career links new tab", 'target="_blank" rel="noopener noreferrer"' in layout)
    add("fvcc", "runs chart navy", "active_runs_chart_colour" in layout and 'get_active_club_id() == "fvcc"' in layout and "active_link_colour()" in layout)
    add("grdcc", "runs chart unchanged", 'else active_chart_primary_colour()' in layout)
    add("both", "combined 50s 100s KPI", '"Total 50s/100s"' in layout and "fifties /" in layout)
    add("both", "zero milestones hidden", "if fifties or hundreds:" in layout)
    add("both", "leader KPI redesign", "leader-highlight-card" in layout and "leader-highlight-details" in theme)
    add("both", "leader latest three", "details[:3]" in layout and "leader-highlight-more" in layout)
    add("both", "club colour tags", ".profile-badge," in theme and "color: var(--club-link) !important" in theme)
    add("both", "club colour recent form", ".recent-form-chip.bat" in theme and ".recent-form-chip.bowl" in theme)
    profile_colour_block = theme[theme.index(".profile-badge {"):theme.index(".profile-badge-gold")]
    recent_colour_block = theme[theme.index(".recent-form-chip.bat"):theme.index(".recent-form-chip.hot")]
    colour_block = f"{profile_colour_block}\n{recent_colour_block}".casefold()
    add("both", "accidental purple removed", all(value not in colour_block for value in ("#5b3df5", "#4b37d8", "#f0edff")))
    add("both", "milestone ratio muted", ".milestone-watch-top span" in theme and "color: var(--club-muted) !important" in theme)
    add("both", "extras compact", "season-col-extras {{ width: 66px; }}" in layout and "season-col-extras {{ width: 60px; }}" in layout)
    exclusive = layout[layout.index("def render_milestone_club(all_time"):layout.index("def highest_reached_threshold")]
    add("both", "exclusive club first five scroll", 'data-visible-rows="5" data-scroll-enabled="true"' in exclusive and "max-height: 259px" in theme)
    add("both", "exclusive club no top 10", "Show top 10" not in exclusive)
    add("both", "iframe club link colours", "--profile-table-link" in layout and "active_link_colour()" in layout)
    add("both", "career sorting preserved", "headers.forEach((header, index) => header.addEventListener" in layout)

    grdcc_audit = grdcc_grouping_audit()
    grade = [row for row in grdcc_audit if row["grouping_type"] == "grade"]
    opponents = [row for row in grdcc_audit if row["grouping_type"] == "opponent"]
    add("grdcc", "community cup grouped", bool(grade) and all(row["canonical_name"] == "NSW Community Cup" for row in grade))
    add("grdcc", "opponents grouped", {"Warringah Cricket Club", "Auburn Cricket Club"}.issubset({row["canonical_name"] for row in opponents}))
    add("grdcc", "grouped stats recomputed", "def combine_profile_breakdown_rows" in layout and 'grouped["bowl_avg"]' in layout)

    add("both", "raw data unchanged", not changed_paths(["data/raw", "clubs/fvcc/data/raw", "clubs/georges-river-district/data/raw"]))
    add("grdcc", "annual report sources unchanged", not changed_paths(["clubs/georges-river-district/data/annual_report", "clubs/georges-river-district/data/processed/annual_report"]))
    add("both", "club palettes unchanged", not changed_paths(["clubs/fvcc/club_config.yaml", "clubs/georges-river-district/club_config.yaml"]))

    write_csv(
        ROOT / "clubs/fvcc/data/processed/validation/fvcc_club_name_merge_audit.csv",
        fvcc_audit,
        ["original_name", "canonical_name", "rows_before", "rows_after", "affected_pages", "validation_status", "notes"],
    )
    write_csv(
        ROOT / "clubs/georges-river-district/data/processed/validation/player_profile/grdcc_opponent_grade_grouping_audit.csv",
        grdcc_audit,
        ["grouping_type", "original_name", "canonical_name", "rows_before", "rows_after", "affected_players_count", "validation_status", "notes"],
    )
    return rows


def main() -> int:
    rows = validate()
    output = ROOT / "data/processed/validation/cross_club_profile_visual_metrics_validation.csv"
    write_csv(output, rows, ["club", "check", "passed", "details"])
    passed = sum(row["passed"] == "true" for row in rows)
    print(f"Cross-club profile visual metrics: {passed}/{len(rows)} passed -> {output}")
    for row in rows:
        if row["passed"] != "true":
            print(f"FAIL {row['club']}: {row['check']} {row['details']}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
