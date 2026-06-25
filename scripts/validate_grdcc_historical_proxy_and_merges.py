from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd


os.environ.setdefault("CLUB_ID", "georges-river-district")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT_DIR = ROOT / "clubs/georges-river-district/data/processed/validation/hof"
BOWLING_AUDIT_PATH = OUTPUT_DIR / "grdcc_zero_matches_bowling_proxy_audit.csv"
MERGE_AUDIT_PATH = OUTPUT_DIR / "grdcc_exact_name_nonoverlap_merge_audit.csv"
VALIDATION_PATH = OUTPUT_DIR / "grdcc_historical_proxy_and_merges_validation.csv"
LAYOUT_PATH = ROOT / "src/ui/layout.py"


def number(value: object) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return None if pd.isna(parsed) else float(parsed)


def clean_link_label(value: object) -> str:
    text = str(value or "").strip()
    return text.rsplit("#", 1)[-1].replace("%20", " ") if "#" in text else text


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def changed_paths() -> list[str]:
    result = subprocess.run(
        ["git", "status", "--short"], cwd=ROOT, check=True, capture_output=True, text=True
    )
    return [line[3:] for line in result.stdout.splitlines() if len(line) > 3]


def source_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    from src.data.playcricket_ingestion import read_processed_table

    return read_processed_table("all_seasons_batting"), read_processed_table("all_seasons_bowling")


def merge_audit(batting: pd.DataFrame, bowling: pd.DataFrame) -> list[dict[str, object]]:
    from src.utils.player_identity import apply_player_identity_mapping, normalize_player_name_for_strict_merge

    source_columns = ["raw_player_id", "raw_player_name", "player_name", "season", "source_system"]
    frames = []
    for frame in [batting, bowling]:
        available = [column for column in source_columns if column in frame]
        frames.append(frame[available].copy())
    source = pd.concat(frames, ignore_index=True).drop_duplicates()
    source["raw_player_id"] = source.get("raw_player_id", "").fillna("").astype(str)
    source["display_name"] = source.get("raw_player_name", source.get("player_name", "")).fillna("").astype(str)
    source["normalized"] = source["display_name"].map(normalize_player_name_for_strict_merge)
    historical = source["raw_player_id"].str.startswith("excel_")
    source = source.loc[historical].copy()

    mapped = apply_player_identity_mapping(pd.concat([batting, bowling], ignore_index=True, sort=False), club_id="georges-river-district")
    mapped["normalized"] = mapped.get("raw_player_name", mapped.get("player_name", "")).map(normalize_player_name_for_strict_merge)
    rows: list[dict[str, object]] = []
    for normalized, group in source.groupby("normalized", sort=True):
        raw_ids = sorted(set(group["raw_player_id"]) - {""})
        tokens = normalized.split()
        if len(raw_ids) < 2 or len(tokens) < 2 or any(len(token) == 1 or token.isdigit() for token in tokens):
            continue
        season_sets = {
            raw_id: set(group.loc[group["raw_player_id"].eq(raw_id), "season"].dropna().astype(str))
            for raw_id in raw_ids
        }
        overlap = any(
            season_sets[left] & season_sets[right]
            for index, left in enumerate(raw_ids)
            for right in raw_ids[index + 1 :]
        )
        mapped_raw_ids = mapped.get("raw_player_id", pd.Series("", index=mapped.index)).fillna("").astype(str)
        mapped_group = mapped[mapped["normalized"].eq(normalized) & mapped_raw_ids.str.startswith("excel_")]
        after_ids = set(mapped_group.get("canonical_player_id", pd.Series(dtype=str)).dropna().astype(str))
        merged = not overlap and len(after_ids) == 1
        seasons = sorted(set(group["season"].dropna().astype(str)))
        rows.append(
            {
                "normalized_player_name": normalized,
                "display_names": ", ".join(sorted(set(group["display_name"]))),
                "source_systems": ", ".join(sorted(set(group.get("source_system", pd.Series("excel", index=group.index)).astype(str)))) or "excel",
                "profile_count_before": len(raw_ids),
                "profile_count_after": len(after_ids),
                "seasons_before": ", ".join(seasons),
                "seasons_after": ", ".join(seasons),
                "season_overlap_found": "yes" if overlap else "no",
                "merged": "yes" if merged else "no",
                "merge_reason": (
                    "Skipped: the exact-name profiles overlap in season."
                    if overlap
                    else "Merged: exact full normalized name with non-overlapping historical Excel seasons."
                ),
                "validation_status": "pass" if merged or overlap else "fail",
                "notes": "Initial-only and partial-name candidates are excluded from automatic merging.",
            }
        )
    return rows


def load_hof_data() -> dict[str, object]:
    from src.data.featured_record_overrides import featured_record_overrides_mtime
    from src.data.playcricket_ingestion import metadata_mtime
    from src.ui import layout
    from src.utils.player_identity import player_aliases_mtime

    layout.load_hall_of_fame_data.clear()
    layout.get_hall_of_fame_data.clear()
    return layout.get_hall_of_fame_data(
        metadata_mtime(),
        player_aliases_mtime(),
        layout.HALL_OF_FAME_DATA_VERSION,
        featured_record_overrides_mtime(),
        club_id="georges-river-district",
    )


def bowling_audit(data: dict[str, object]) -> list[dict[str, object]]:
    from src.data.featured_record_overrides import normalize_featured_player_name
    from src.ui import layout

    table = data["detailed_tables"]["bowling"].copy()
    rows: list[dict[str, object]] = []
    for _, row in table.iterrows():
        original_matches = number(row.get("Matches"))
        wickets = number(row.get("Wickets")) or 0
        maidens = number(row.get("Maidens")) or 0
        balls = layout.cricket_overs_to_balls(row.get("Overs"))
        has_bowling_stats = wickets > 0 or maidens > 0 or (balls or 0) > 0
        if (original_matches or 0) > 0 or not has_bowling_stats:
            continue
        display, sort_value, used_proxy = layout.historical_matches_display_text(row)
        player_name = clean_link_label(row.get("Player"))
        innings = number(row.get("Innings"))
        rows.append(
            {
                "player_name": player_name,
                "normalized_player_name": normalize_featured_player_name(player_name),
                "season_count": int(number(row.get("Seasons")) or 0),
                "debut_season": "",
                "latest_season": row.get("Proxy Season", ""),
                "original_matches": "" if original_matches is None else int(original_matches),
                "batting_innings": "" if innings is None else int(innings),
                "bowling_innings_or_appearances": "",
                "overs": row.get("Overs", ""),
                "balls": "" if balls is None else int(balls),
                "maidens": int(maidens),
                "wickets": int(wickets),
                "bowling_runs_conceded": "",
                "displayed_matches": display,
                "used_proxy": "yes" if used_proxy else "no",
                "proxy_source": "same-player historical batting innings" if used_proxy else "",
                "sort_value": "" if sort_value is None else int(sort_value),
                "reason": (
                    "Historical match count unavailable; batting innings provide the available appearance proxy."
                    if used_proxy
                    else "Historical bowling record exists but no credible innings/appearance proxy is available."
                ),
                "validation_status": "pass" if (used_proxy and display.endswith("*")) or (not used_proxy and display == "") else "fail",
                "notes": "The asterisk identifies a proxy, not an exact match count.",
            }
        )
    return rows


def main() -> int:
    from src.ui import layout

    batting, bowling = source_frames()
    merge_rows = merge_audit(batting, bowling)
    data = load_hof_data()
    bowling_rows = bowling_audit(data)

    write_csv(
        BOWLING_AUDIT_PATH,
        bowling_rows,
        [
            "player_name", "normalized_player_name", "season_count", "debut_season", "latest_season",
            "original_matches", "batting_innings", "bowling_innings_or_appearances", "overs", "balls",
            "maidens", "wickets", "bowling_runs_conceded", "displayed_matches", "used_proxy",
            "proxy_source", "sort_value", "reason", "validation_status", "notes",
        ],
    )
    write_csv(
        MERGE_AUDIT_PATH,
        merge_rows,
        [
            "normalized_player_name", "display_names", "source_systems", "profile_count_before",
            "profile_count_after", "seasons_before", "seasons_after", "season_overlap_found", "merged",
            "merge_reason", "validation_status", "notes",
        ],
    )

    all_time = data["all_time"]
    batting_detail = data["detailed_tables"]["batting"]
    by_name = lambda frame, name: frame[frame["Player"].astype(str).str.contains(name, case=False, regex=False, na=False)]
    harry = by_name(all_time, "Harry Milburn")
    harry_display = layout.historical_matches_display_text(harry.iloc[0])[0] if not harry.empty else ""
    examples = {name: [row for row in bowling_rows if row["player_name"] == name] for name in ["D Morton", "D Murden", "D Warburton", "D Winspear"]}
    alan_cox = by_name(batting_detail, "Alan Cox")
    alan_ferguson = by_name(batting_detail, "Alan Ferguson")
    merged_overlap = [row for row in merge_rows if row["season_overlap_found"] == "yes" and row["merged"] == "yes"]

    changed = changed_paths()
    raw_changed = [path for path in changed if "/raw/" in path or path.startswith("clubs/georges-river-district/data/source/")]
    fvcc_changed = [
        path for path in changed
        if path.startswith("clubs/fvcc/")
        and path != "clubs/fvcc/data/processed/validation/performance/fvcc_localhost_load_profile.csv"
    ]
    layout_text = LAYOUT_PATH.read_text(encoding="utf-8")
    checks = [
        ("bowling_examples_proxy", all(examples[name] and all(row["displayed_matches"].endswith("*") for row in examples[name]) for name in examples), str({name: [row["displayed_matches"] for row in value] for name, value in examples.items()})),
        ("bowling_proxy_numeric_sort", all(isinstance(row["sort_value"], int) for row in bowling_rows if row["used_proxy"] == "yes"), f"rows={len(bowling_rows)}"),
        ("bowling_no_proxy_blank", all(row["displayed_matches"] == "" for row in bowling_rows if row["used_proxy"] == "no"), "Unsupported historical rows are blank."),
        ("harry_412_proxy", harry_display == "412*", harry_display),
        ("footnote_preserved", "For historical records where match counts were not captured" in layout_text and ".hof-matches-footnote" in layout_text, "Footnote wording and styling remain."),
        ("alan_cox_merged", len(alan_cox) == 1 and int(number(alan_cox.iloc[0].get("Seasons")) or 0) > 1, f"rows={len(alan_cox)}"),
        ("alan_ferguson_merged", len(alan_ferguson) == 1 and int(number(alan_ferguson.iloc[0].get("Seasons")) or 0) > 1, f"rows={len(alan_ferguson)}"),
        ("overlap_not_merged", not merged_overlap, f"incorrect={len(merged_overlap)}"),
        ("merge_decisions_audited", bool(merge_rows) and all(row["validation_status"] == "pass" for row in merge_rows), f"candidates={len(merge_rows)}"),
        ("no_raw_source_changes", not raw_changed, ", ".join(raw_changed)),
        ("fvcc_unchanged", not fvcc_changed, ", ".join(fvcc_changed)),
    ]
    validation_rows = [
        {"check": check, "validation_status": "pass" if passed else "fail", "details": details}
        for check, passed, details in checks
    ]
    write_csv(VALIDATION_PATH, validation_rows, ["check", "validation_status", "details"])
    failed = [check for check, passed, _ in checks if not passed]
    print(
        f"validation_status={'fail' if failed else 'pass'} checks={len(checks)} "
        f"bowling_proxy={sum(row['used_proxy'] == 'yes' for row in bowling_rows)} "
        f"bowling_blank={sum(row['used_proxy'] == 'no' for row in bowling_rows)} "
        f"merged={sum(row['merged'] == 'yes' for row in merge_rows)} overlap_skipped={sum(row['season_overlap_found'] == 'yes' for row in merge_rows)}"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
