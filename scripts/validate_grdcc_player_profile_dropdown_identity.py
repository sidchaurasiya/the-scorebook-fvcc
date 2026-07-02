#!/usr/bin/env python3
"""Validate the exact GRDCC Player Profile dropdown identity source."""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ["CLUB_ID"] = "georges-river-district"

from src.data.playcricket_ingestion import metadata_mtime, read_processed_table  # noqa: E402
from src.ui.layout import (  # noqa: E402
    PLAYER_PROFILE_INDEX_VERSION,
    load_player_profile_index,
    player_name_match_key,
)
from src.utils.player_identity import (  # noqa: E402
    display_player_name,
    grdcc_exact_name_nonoverlap_canonical_map,
    load_player_aliases,
    normalize_player_name_for_strict_merge,
    player_aliases_mtime,
)

CLUB_ID = "georges-river-district"
OUTPUT = ROOT / "clubs/georges-river-district/data/processed/validation/grdcc_player_profile_dropdown_identity_validation.csv"
EXAMPLE_NAMES = ["A Clarkson", "A Ferguson", "A Howard", "A Mostyn"]


def _row(check_name: str, passed: bool, player_name: str = "", details: str = "") -> dict[str, object]:
    return {
        "check_name": check_name,
        "validation_status": "pass" if passed else "fail",
        "player_name": player_name,
        "details": details,
    }


def _logical_raw_id(value: object) -> str:
    text = str(value or "").strip()
    return text[4:] if text.startswith("raw_excel_") else text


def _raw_identity_source() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for category in ("batting", "bowling", "fielding"):
        frame = read_processed_table(f"all_seasons_{category}")
        if frame.empty or "raw_player_id" not in frame:
            continue
        name_column = "raw_player_name" if "raw_player_name" in frame else "player_name"
        columns = [column for column in ["raw_player_id", name_column, "season"] if column in frame]
        scoped = frame[columns].copy().rename(columns={name_column: "raw_player_name"})
        scoped["source_category"] = category
        frames.append(scoped)
    if not frames:
        return pd.DataFrame(columns=["raw_player_id", "raw_player_name", "season", "strict_name", "logical_raw_id"])
    output = pd.concat(frames, ignore_index=True)
    output["raw_player_name"] = output["raw_player_name"].map(display_player_name)
    output["strict_name"] = output["raw_player_name"].map(normalize_player_name_for_strict_merge)
    output["logical_raw_id"] = output["raw_player_id"].map(_logical_raw_id)
    output["season"] = output.get("season", pd.Series("", index=output.index)).fillna("").astype(str)
    return output[output["strict_name"].ne("") & output["logical_raw_id"].ne("")].copy()


def _merged_players() -> list[str]:
    canonical_map = grdcc_exact_name_nonoverlap_canonical_map(CLUB_ID, metadata_mtime())
    raw_ids_by_canonical: dict[str, set[str]] = defaultdict(set)
    names_by_canonical: dict[str, set[str]] = defaultdict(set)
    for raw_id, (canonical_id, canonical_name) in canonical_map.items():
        raw_ids_by_canonical[str(canonical_id)].add(str(raw_id))
        names_by_canonical[str(canonical_id)].add(display_player_name(canonical_name))
    merged = []
    for canonical_id, raw_ids in raw_ids_by_canonical.items():
        if len(raw_ids) >= 2:
            names = sorted(name for name in names_by_canonical[canonical_id] if name)
            if names:
                merged.append(names[0])
    return sorted(set(merged), key=lambda value: value.casefold())


def _overlap_unmerged_names(raw_source: pd.DataFrame) -> list[str]:
    names = []
    for strict_name, group in raw_source.groupby("strict_name", sort=False):
        raw_ids = group["logical_raw_id"].dropna().astype(str).unique().tolist()
        if len(raw_ids) < 2:
            continue
        season_sets = {
            raw_id: set(group.loc[group["logical_raw_id"].astype(str).eq(raw_id), "season"].dropna().astype(str))
            for raw_id in raw_ids
        }
        if any(
            season_sets[left] & season_sets[right]
            for position, left in enumerate(raw_ids)
            for right in raw_ids[position + 1 :]
        ):
            names.append(group["raw_player_name"].mode().iloc[0])
    return sorted(set(names), key=lambda value: value.casefold())


def _dropdown_counts(index: pd.DataFrame) -> pd.DataFrame:
    if index.empty:
        return pd.DataFrame(columns=["name_key", "name", "count", "ids"])
    scoped = index.copy()
    scoped["name"] = scoped["name"].map(display_player_name)
    scoped["name_key"] = scoped["name"].map(player_name_match_key)
    grouped = (
        scoped.groupby("name_key", as_index=False)
        .agg(
            name=("name", "first"),
            count=("id", "nunique"),
            ids=("id", lambda values: "; ".join(sorted(set(map(str, values))))),
        )
        .sort_values("name", key=lambda series: series.astype(str).str.casefold())
    )
    return grouped


def main() -> int:
    if hasattr(load_player_profile_index, "clear"):
        load_player_profile_index.clear()
    raw_source = _raw_identity_source()
    merged_players = _merged_players()
    overlap_left = _overlap_unmerged_names(raw_source)
    index = load_player_profile_index(
        CLUB_ID,
        metadata_mtime(),
        player_aliases_mtime(club_id=CLUB_ID),
        PLAYER_PROFILE_INDEX_VERSION,
    )
    counts = _dropdown_counts(index)
    rows: list[dict[str, object]] = []
    merged_keys = {player_name_match_key(name) for name in merged_players}

    for player in sorted(set(merged_players + EXAMPLE_NAMES), key=lambda value: value.casefold()):
        key = player_name_match_key(player)
        matches = counts[counts["name_key"].eq(key)]
        count = int(matches["count"].iloc[0]) if not matches.empty else 0
        ids = str(matches["ids"].iloc[0]) if not matches.empty else ""
        expected_one = player in EXAMPLE_NAMES or (key in merged_keys and count > 0)
        rows.append(_row("dropdown_single_canonical_name", count == 1 if expected_one else count <= 1, player, f"count={count}; ids={ids}"))

    duplicate_rows = counts[counts["count"].gt(1)].copy()
    duplicate_rows = duplicate_rows[~duplicate_rows["name_key"].isin({player_name_match_key(name) for name in overlap_left})]
    rows.append(_row("total_duplicate_exact_name_no_overlap_count", duplicate_rows.empty, "", str(len(duplicate_rows))))
    rows.append(_row("canonical_players_merged_count", bool(merged_players), "", str(len(merged_players))))
    rows.append(_row("canonical_players_merged_list", True, "", "; ".join(merged_players)))
    rows.append(_row("exact_name_duplicates_left_unmerged_due_to_overlap", True, "", "; ".join(overlap_left)))
    if not duplicate_rows.empty:
        for _, duplicate in duplicate_rows.iterrows():
            rows.append(_row("unexpected_dropdown_duplicate", False, str(duplicate["name"]), f"count={duplicate['count']}; ids={duplicate['ids']}"))

    report = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUTPUT, index=False)
    failed = report[report["validation_status"].ne("pass")]
    print(f"validation_status={'pass' if failed.empty else 'fail'} checks={len(report)} failed={len(failed)}")
    print(f"merged_players_count={len(merged_players)}")
    print("merged_players=" + "; ".join(merged_players[:80]) + ("; ..." if len(merged_players) > 80 else ""))
    print("overlap_unmerged=" + "; ".join(overlap_left[:40]) + ("; ..." if len(overlap_left) > 40 else ""))
    return 0 if failed.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
