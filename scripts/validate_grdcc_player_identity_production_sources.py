#!/usr/bin/env python3
"""Validate GRDCC production-facing player identity sources."""

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
from src.ui.layout import load_hall_of_fame_data, load_player_profile_index, player_name_match_key  # noqa: E402
from src.utils.player_identity import (  # noqa: E402
    apply_player_identity_mapping,
    display_player_name,
    grdcc_exact_name_nonoverlap_canonical_map,
    load_player_aliases,
    normalize_player_name_for_strict_merge,
    player_aliases_mtime,
)

CLUB_ID = "georges-river-district"
OUTPUT = ROOT / "clubs/georges-river-district/data/processed/validation/grdcc_player_identity_production_sources.csv"
EXAMPLES = ["A Clarkson", "A Ferguson", "A Howard", "A Mostyn"]


def row(check_name: str, passed: bool, player_name: str = "", details: str = "") -> dict[str, object]:
    return {
        "check_name": check_name,
        "validation_status": "pass" if passed else "fail",
        "player_name": player_name,
        "details": details,
    }


def logical_raw_id(value: object) -> str:
    text = str(value or "").strip()
    return text[4:] if text.startswith("raw_excel_") else text


def mapped_frames() -> dict[str, pd.DataFrame]:
    aliases = load_player_aliases(club_id=CLUB_ID)
    frames: dict[str, pd.DataFrame] = {}
    for category in ("batting", "bowling", "fielding"):
        frame = read_processed_table(f"all_seasons_{category}")
        frames[category] = apply_player_identity_mapping(frame, aliases, club_id=CLUB_ID) if not frame.empty else frame
    return frames


def raw_identity_source() -> pd.DataFrame:
    frames = []
    for category in ("batting", "bowling", "fielding"):
        frame = read_processed_table(f"all_seasons_{category}")
        if frame.empty or "raw_player_id" not in frame:
            continue
        name_column = "raw_player_name" if "raw_player_name" in frame else "player_name"
        columns = [column for column in ["raw_player_id", name_column, "season"] if column in frame]
        rows = frame[columns].copy()
        rows = rows.rename(columns={name_column: "raw_player_name"})
        frames.append(rows)
    if not frames:
        return pd.DataFrame(columns=["raw_player_id", "raw_player_name", "season"])
    output = pd.concat(frames, ignore_index=True)
    output["strict_name"] = output["raw_player_name"].map(normalize_player_name_for_strict_merge)
    output["logical_raw_id"] = output["raw_player_id"].map(logical_raw_id)
    output["season"] = output.get("season", pd.Series("", index=output.index)).fillna("").astype(str)
    return output[output["strict_name"].ne("") & output["logical_raw_id"].ne("")].copy()


def fixed_players_from_map(raw_source: pd.DataFrame) -> list[str]:
    canonical_map = grdcc_exact_name_nonoverlap_canonical_map(CLUB_ID, metadata_mtime())
    names_by_canonical: dict[str, set[str]] = defaultdict(set)
    ids_by_canonical: dict[str, set[str]] = defaultdict(set)
    for raw_id, (canonical_id, canonical_name) in canonical_map.items():
        names_by_canonical[canonical_id].add(display_player_name(canonical_name))
        ids_by_canonical[canonical_id].add(str(raw_id))
    fixed = []
    for canonical_id, raw_ids in ids_by_canonical.items():
        if len(raw_ids) < 2:
            continue
        display_names = sorted(name for name in names_by_canonical[canonical_id] if name)
        if display_names:
            fixed.append(display_names[0])
    return sorted(set(fixed), key=lambda value: value.casefold())


def overlap_unmerged_names(raw_source: pd.DataFrame) -> list[str]:
    names = []
    for strict_name, group in raw_source.groupby("strict_name", sort=False):
        raw_ids = group["logical_raw_id"].dropna().astype(str).unique().tolist()
        if len(raw_ids) < 2:
            continue
        season_sets = {
            raw_id: set(group.loc[group["logical_raw_id"].astype(str).eq(raw_id), "season"].dropna().astype(str))
            for raw_id in raw_ids
        }
        has_overlap = any(
            season_sets[left] & season_sets[right]
            for pos, left in enumerate(raw_ids)
            for right in raw_ids[pos + 1 :]
        )
        if has_overlap:
            display = group["raw_player_name"].map(display_player_name).mode()
            names.append(display.iloc[0] if not display.empty else strict_name)
    return sorted(set(names), key=lambda value: value.casefold())


def ids_for_name(index: pd.DataFrame, player_name: str) -> list[str]:
    if index.empty:
        return []
    mask = index["name"].astype(str).map(player_name_match_key).eq(player_name_match_key(player_name))
    return index.loc[mask, "id"].astype(str).drop_duplicates().tolist()


def canonical_count_for_name(frame: pd.DataFrame, player_name: str) -> int:
    if frame.empty:
        return 0
    name_column = "canonical_player_name" if "canonical_player_name" in frame else "Player" if "Player" in frame else ""
    if not name_column:
        return 0
    scoped = frame[frame[name_column].astype(str).map(player_name_match_key).eq(player_name_match_key(player_name))]
    id_column = "canonical_player_id" if "canonical_player_id" in scoped else "player_key" if "player_key" in scoped else ""
    return int(scoped[id_column].astype(str).nunique()) if id_column else int(len(scoped))


def main() -> int:
    for fn in [load_player_profile_index, load_hall_of_fame_data]:
        if hasattr(fn, "clear"):
            fn.clear()
    raw_source = raw_identity_source()
    fixed_players = fixed_players_from_map(raw_source)
    overlap_left = overlap_unmerged_names(raw_source)

    index = load_player_profile_index(CLUB_ID, metadata_mtime(), player_aliases_mtime(club_id=CLUB_ID))
    hof = load_hall_of_fame_data(metadata_mtime(), player_aliases_mtime(club_id=CLUB_ID), club_id=CLUB_ID)
    all_time = hof.get("all_time", pd.DataFrame()) if hof else pd.DataFrame()
    frames = mapped_frames()

    rows: list[dict[str, object]] = []
    fixed_set = {player_name_match_key(name) for name in fixed_players}
    for player in fixed_players:
        ids = ids_for_name(index, player)
        rows.append(row("profile_dropdown_single", len(ids) <= 1, player, f"ids={ids}"))
        hof_count = canonical_count_for_name(all_time, player)
        rows.append(row("hof_source_single", hof_count <= 1, player, f"canonical_ids={hof_count}"))
        rows.append(row("milestone_source_single", hof_count <= 1, player, "milestone exclusive source is HOF all_time"))
        for category, frame in frames.items():
            count = canonical_count_for_name(frame, player)
            rows.append(row(f"season_overview_{category}_single", count <= 1, player, f"canonical_ids={count}"))

    for example in EXAMPLES:
        ids = ids_for_name(index, example)
        should_be_fixed = player_name_match_key(example) in fixed_set
        rows.append(row(f"example_dropdown_{example}", len(ids) == 1 if should_be_fixed else len(ids) <= 1, example, f"ids={ids}"))

    rows.append(row("fixed_players_count", bool(fixed_players), "", str(len(fixed_players))))
    rows.append(row("fixed_players_list", True, "", "; ".join(fixed_players)))
    rows.append(row("exact_name_duplicates_left_unmerged_due_to_overlap", True, "", "; ".join(overlap_left)))

    report = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    report.to_csv(OUTPUT, index=False)
    failed = report[report["validation_status"].ne("pass")]
    print(f"validation_status={'pass' if failed.empty else 'fail'} checks={len(report)} failed={len(failed)}")
    print(f"fixed_players_count={len(fixed_players)}")
    print("fixed_players=" + "; ".join(fixed_players[:80]) + ("; ..." if len(fixed_players) > 80 else ""))
    print("overlap_unmerged=" + "; ".join(overlap_left[:40]) + ("; ..." if len(overlap_left) > 40 else ""))
    return 0 if failed.empty else 1


if __name__ == "__main__":
    raise SystemExit(main())
