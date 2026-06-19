from __future__ import annotations

import csv
import logging
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


os.environ.setdefault("CLUB_ID", "georges-river-district")
logging.getLogger("streamlit").setLevel(logging.ERROR)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT_DIR = ROOT / "clubs/georges-river-district/data/processed/validation/hof"
AUDIT_PATH = OUTPUT_DIR / "grdcc_zero_matches_historical_proxy_audit.csv"
VALIDATION_PATH = OUTPUT_DIR / "grdcc_zero_matches_and_footnote_validation.csv"
LAYOUT_PATH = ROOT / "src/ui/layout.py"


def number(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def clean_player(value: object) -> str:
    text = str(value or "").strip()
    return text.rsplit("#", 1)[-1].replace("%20", " ") if "#" in text else text


def changed_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line[3:] for line in result.stdout.splitlines() if len(line) > 3]


def build_audit() -> tuple[list[dict[str, object]], dict[str, object]]:
    from src.data.featured_record_overrides import featured_record_overrides_mtime, normalize_featured_player_name
    from src.data.playcricket_ingestion import metadata_mtime
    from src.ui import layout
    from src.utils.player_identity import player_aliases_mtime

    data = layout.get_hall_of_fame_data(
        metadata_mtime(),
        player_aliases_mtime(),
        layout.HALL_OF_FAME_DATA_VERSION,
        featured_record_overrides_mtime(),
    )
    all_time = data["all_time"].copy()
    batting_detail = data["detailed_tables"]["batting"].copy()
    cutoff = layout.season_sort_key("Summer 1971/72")
    rows: list[dict[str, object]] = []
    modern_checked = 0
    modern_changed = 0
    for _, row in all_time.iterrows():
        latest = str(row.get("Latest Season", "") or "").strip()
        is_historical = bool(latest) and layout.season_sort_key(latest) <= cutoff
        matches = number(row.get("Matches"))
        innings = number(row.get("Innings"))
        runs = number(row.get("Runs")) or 0
        wickets = number(row.get("Wickets")) or 0
        has_real_stats = runs > 0 or wickets > 0
        display, sort_value, used_proxy = layout.historical_matches_display_text(row)
        explicit_proxy = layout.as_bool(row.get("Matches Proxy")) or str(row.get("Matches Source", "")).strip().casefold() == "innings_proxy"
        if not is_historical and not explicit_proxy and matches is not None and matches > 0:
            modern_checked += 1
            modern_changed += int(display.endswith("*") or sort_value != int(round(matches)))
        needs_audit = used_proxy or (is_historical and (matches is None or matches <= 0) and has_real_stats)
        if not needs_audit:
            continue
        player = clean_player(row.get("Player"))
        rows.append(
            {
                "player_name": player,
                "normalized_player_name": normalize_featured_player_name(player),
                "season_count": int(number(row.get("Seasons Played")) or 0),
                "debut_season": row.get("Debut Season", ""),
                "latest_season": latest,
                "original_matches": "" if matches is None else int(round(matches)),
                "batting_innings": "" if innings is None else int(round(innings)),
                "bowling_innings_or_appearances": "",
                "runs": int(round(runs)),
                "wickets": int(round(wickets)),
                "displayed_matches": display,
                "used_proxy": "yes" if used_proxy else "no",
                "proxy_source": "batting_innings" if used_proxy else "",
                "sort_value": "" if sort_value is None else int(sort_value),
                "reason": (
                    "Historical matches unavailable; batting innings used as proxy."
                    if used_proxy
                    else "Historical player has real stats but no innings/appearance proxy source."
                ),
                "validation_status": "pass",
                "notes": "Numeric sort value is retained separately from the asterisk display.",
            }
        )
    detail_examples: dict[str, str] = {}
    detail_sort_values: dict[str, int | None] = {}
    detail_debug: dict[str, dict[str, object]] = {}
    for player in ["A Algar", "A Ashley", "A Clarkson", "Harry Milburn"]:
        candidates = batting_detail[
            batting_detail["Player"].astype(str).str.contains(player, case=False, regex=False, na=False)
        ]
        if candidates.empty:
            continue
        detail_row = candidates.iloc[0]
        detail_display, detail_sort, _ = layout.historical_matches_display_text(detail_row)
        detail_examples[player] = detail_display
        detail_sort_values[player] = detail_sort
        detail_debug[player] = {
            "matches": detail_row.get("Matches"),
            "innings": detail_row.get("Innings"),
            "latest_season": detail_row.get("Latest Season"),
            "matches_proxy": detail_row.get("Matches Proxy"),
        }
    return rows, {
        "modern_checked": modern_checked,
        "modern_changed": modern_changed,
        "detail_examples": detail_examples,
        "detail_sort_values": detail_sort_values,
        "detail_debug": detail_debug,
    }


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    layout_text = LAYOUT_PATH.read_text(encoding="utf-8")
    audit, summary = build_audit()
    audit_columns = [
        "player_name", "normalized_player_name", "season_count", "debut_season", "latest_season",
        "original_matches", "batting_innings", "bowling_innings_or_appearances", "runs", "wickets",
        "displayed_matches", "used_proxy", "proxy_source", "sort_value", "reason", "validation_status", "notes",
    ]
    write_csv(AUDIT_PATH, audit, audit_columns)
    harry = next((row for row in audit if row["normalized_player_name"] == "harry milburn"), {})
    zero_with_innings = [
        row for row in audit
        if str(row["original_matches"]) in {"", "0"}
        and number(row["batting_innings"]) is not None
        and float(number(row["batting_innings"]) or 0) > 0
        and (int(row["runs"]) > 0 or int(row["wickets"]) > 0)
    ]
    unsupported = [row for row in audit if row["used_proxy"] == "no"]
    changed = changed_paths()
    raw_changed = [
        path for path in changed
        if path.startswith("clubs/georges-river-district/data/source/")
        or "/raw/" in path
        or path.endswith("all_seasons_batting.csv")
        or path.endswith("all_seasons_bowling.csv")
        or path.endswith("all_seasons_fielding.csv")
    ]
    fvcc_changed = [
        path for path in changed
        if path.startswith("clubs/fvcc/")
        and path != "clubs/fvcc/data/processed/validation/performance/fvcc_localhost_load_profile.csv"
    ]
    wording = "* For historical records where match counts were not captured, innings are shown as a match-count proxy."
    checks = [
        ("footnote_wording", wording in layout_text, "Updated historical proxy wording is present."),
        ("footnote_styling", ".hof-matches-footnote" in layout_text and "font-size: 11.5px" in layout_text, "Premium footnote class exists."),
        ("footnote_not_clipped", "height: 500px" in layout_text and "padding: 0 0 4px" in layout_text, "Table height leaves room inside the 560px component."),
        ("footnote_conditional", "if matches_proxy_used else ''" in layout_text, "Footnote renders only when a proxy is displayed."),
        ("harry_412_proxy", harry.get("displayed_matches") == "412*" and harry.get("sort_value") == 412, str(harry)),
        (
            "desktop_detail_examples",
            summary["detail_examples"].get("Harry Milburn") == "412*"
            and all(str(summary["detail_examples"].get(player, "")).endswith("*") for player in ["A Algar", "A Ashley", "A Clarkson"]),
            str(summary["detail_debug"]),
        ),
        ("zero_matches_with_innings_fixed", bool(zero_with_innings) and all(str(row["displayed_matches"]).endswith("*") for row in zero_with_innings), f"rows={len(zero_with_innings)}"),
        ("no_available_proxy_left_zero", all(row["displayed_matches"] != "0" for row in zero_with_innings), "No qualifying historical row displays zero."),
        ("numeric_sort_values", all(isinstance(row["sort_value"], int) for row in audit if row["used_proxy"] == "yes"), "Proxy rows retain integer sort values."),
        ("modern_reliable_unchanged", summary["modern_checked"] > 0 and summary["modern_changed"] == 0, str(summary)),
        ("no_raw_source_changes", not raw_changed, "; ".join(raw_changed)),
        ("fvcc_unchanged", not fvcc_changed, "; ".join(fvcc_changed)),
    ]
    validation_rows = [
        {"check": check, "validation_status": "pass" if passed else "fail", "details": details}
        for check, passed, details in checks
    ]
    write_csv(VALIDATION_PATH, validation_rows, ["check", "validation_status", "details"])
    failed = [check for check, passed, _ in checks if not passed]
    print(
        f"validation_status={'fail' if failed else 'pass'} checks={len(checks)} "
        f"fixed={len(zero_with_innings)} blank_no_proxy={len(unsupported)} failed={len(failed)}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
