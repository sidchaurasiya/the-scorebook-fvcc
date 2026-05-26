#!/usr/bin/env python3
"""Build a lightweight aggregate-data review pack for one club.

The review pack uses processed aggregate CSVs only. It does not fetch data and
does not inspect ignored match-centre raw/generated folders.
"""

from __future__ import annotations

import argparse
import itertools
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.club_refresh_utils import print_club_header, print_outputs, print_paths, resolve_club_id  # noqa: E402
from src.config.club_config import get_club_name, get_experimental_dir, get_processed_dir  # noqa: E402
from src.utils.player_identity import display_player_name, normalize_player_name_for_strict_merge  # noqa: E402
from src.utils.team_grade import apply_team_grade_display_columns  # noqa: E402


AGGREGATE_FILES = {
    "seasons": "seasons.csv",
    "teams": "teams.csv",
    "players": "players.csv",
    "batting": "all_seasons_batting.csv",
    "bowling": "all_seasons_bowling.csv",
    "fielding": "all_seasons_fielding.csv",
}

SAFE_AUTO_MERGE_COLUMNS = [
    "club_id",
    "candidate_group_id",
    "normalized_strict_name",
    "raw_player_id",
    "raw_player_name",
    "seasons_seen",
    "matches_seen_count",
    "batting_rows",
    "bowling_rows",
    "fielding_rows",
    "total_runs",
    "total_wickets",
    "total_catches",
    "proposed_canonical_name",
    "reason",
    "confidence",
]

MANUAL_DUPLICATE_REVIEW_COLUMNS = [
    "club_id",
    "candidate_group_id",
    "raw_player_id",
    "raw_player_name",
    "normalized_name",
    "seasons_seen",
    "overlap_seasons",
    "possible_reason",
    "review_notes",
]

MATCH_ID_COLUMNS = ["match_id", "matchId", "fixture_id", "fixtureId", "scorecard_match_id"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an ignored review pack from club aggregate data.")
    parser.add_argument("--club", required=True, help="Club config id.")
    parser.add_argument("--dry-run", action="store_true", help="Print resolved inputs/outputs without writing files.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = resolve_club_id(args.club)
    processed_dir = get_processed_dir(club_id=club_id)
    output_dir = get_experimental_dir(club_id=club_id) / "review_pack"
    output_paths = [
        output_dir / "data_quality_summary.md",
        output_dir / "seasons_audit.csv",
        output_dir / "team_grade_audit.csv",
        output_dir / "player_duplicate_candidates.csv",
        output_dir / "player_name_audit.csv",
        output_dir / "top_players_preview.csv",
        output_dir / "safe_auto_merge_candidates.csv",
        output_dir / "manual_duplicate_review_candidates.csv",
    ]

    print_club_header("Club aggregate review pack builder", club_id)
    print_paths("Inputs", [processed_dir / filename for filename in AGGREGATE_FILES.values()])
    print_outputs("Outputs", output_paths)
    if args.dry_run:
        print("Dry run complete. No files were written.")
        return 0

    frames = {name: read_csv(processed_dir / filename) for name, filename in AGGREGATE_FILES.items()}
    output_dir.mkdir(parents=True, exist_ok=True)

    seasons_audit = build_seasons_audit(frames["seasons"])
    team_grade_audit = build_team_grade_audit(frames["teams"])
    player_name_audit = build_player_name_audit(frames)
    duplicate_candidates = build_duplicate_candidates(player_name_audit)
    safe_auto_merge_candidates, manual_duplicate_review_candidates = build_strict_duplicate_merge_review(club_id, frames)
    top_players_preview = build_top_players_preview(frames)
    warnings = build_warnings(frames, duplicate_candidates, top_players_preview)
    summary = build_summary(
        club_id,
        frames=frames,
        team_grade_audit=team_grade_audit,
        player_name_audit=player_name_audit,
        duplicate_candidates=duplicate_candidates,
        safe_auto_merge_candidates=safe_auto_merge_candidates,
        manual_duplicate_review_candidates=manual_duplicate_review_candidates,
        top_players_preview=top_players_preview,
        warnings=warnings,
    )

    seasons_audit.to_csv(output_dir / "seasons_audit.csv", index=False)
    team_grade_audit.to_csv(output_dir / "team_grade_audit.csv", index=False)
    player_name_audit.to_csv(output_dir / "player_name_audit.csv", index=False)
    duplicate_candidates.to_csv(output_dir / "player_duplicate_candidates.csv", index=False)
    safe_auto_merge_candidates.to_csv(output_dir / "safe_auto_merge_candidates.csv", index=False)
    manual_duplicate_review_candidates.to_csv(output_dir / "manual_duplicate_review_candidates.csv", index=False)
    top_players_preview.to_csv(output_dir / "top_players_preview.csv", index=False)
    (output_dir / "data_quality_summary.md").write_text(summary, encoding="utf-8")

    print(f"Review pack written: {output_dir}")
    return 0


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False)
    except (OSError, pd.errors.ParserError):
        return pd.DataFrame()


def build_seasons_audit(seasons: pd.DataFrame) -> pd.DataFrame:
    if seasons.empty:
        return pd.DataFrame(columns=["id", "name", "startDate", "isCurrentSeason"])
    columns = [column for column in ["id", "name", "startDate", "isCurrentSeason"] if column in seasons]
    return seasons[columns].copy()


def build_team_grade_audit(teams: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "season",
        "team_id",
        "team_name",
        "grade_id",
        "grade_name",
        "competition_name",
        "team_grade_display",
    ]
    if teams.empty:
        return pd.DataFrame(columns=columns)
    output = apply_team_grade_display_columns(teams)
    for column in columns:
        if column not in output:
            output[column] = ""
    return output[columns].drop_duplicates().sort_values(["season", "team_grade_display"], na_position="last")


def build_player_name_audit(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, str]] = []
    for source_name in ["players", "batting", "bowling", "fielding"]:
        frame = frames.get(source_name, pd.DataFrame())
        if frame.empty:
            continue
        for _, row in frame.iterrows():
            player_name = display_player_name(row.get("canonical_player_name") or row.get("player_name"))
            player_id = str(row.get("canonical_player_id") or row.get("player_id") or "").strip()
            if not player_name and not player_id:
                continue
            rows.append(
                {
                    "source": source_name,
                    "player_id": player_id,
                    "player_name": player_name,
                    "raw_player_id": str(row.get("raw_player_id") or row.get("player_id") or "").strip(),
                    "raw_player_name": display_player_name(row.get("raw_player_name") or row.get("player_name")),
                    "normalised_name": normalise_name(player_name),
                }
            )
    if not rows:
        return pd.DataFrame(columns=["source", "player_id", "player_name", "raw_player_id", "raw_player_name", "normalised_name"])
    return pd.DataFrame(rows).drop_duplicates().sort_values(["player_name", "source"], na_position="last")


def build_duplicate_candidates(player_name_audit: pd.DataFrame) -> pd.DataFrame:
    columns = ["player_name_a", "player_id_a", "player_name_b", "player_id_b", "similarity", "reason"]
    if player_name_audit.empty:
        return pd.DataFrame(columns=columns)
    players = (
        player_name_audit[["player_id", "player_name", "normalised_name"]]
        .drop_duplicates()
        .query("normalised_name != ''")
        .to_dict("records")
    )
    rows: list[dict[str, object]] = []
    for left, right in itertools.combinations(players, 2):
        if left["player_id"] and right["player_id"] and left["player_id"] == right["player_id"]:
            continue
        left_key = str(left["normalised_name"])
        right_key = str(right["normalised_name"])
        if left_key == right_key:
            similarity = 1.0
            reason = "same normalised name"
        else:
            similarity = SequenceMatcher(None, left_key, right_key).ratio()
            reason = "very similar normalised name"
        if similarity < 0.92:
            continue
        rows.append(
            {
                "player_name_a": left["player_name"],
                "player_id_a": left["player_id"],
                "player_name_b": right["player_name"],
                "player_id_b": right["player_id"],
                "similarity": round(float(similarity), 3),
                "reason": reason,
            }
        )
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).sort_values(["similarity", "player_name_a"], ascending=[False, True]).head(200)


def build_strict_duplicate_merge_review(club_id: str, frames: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    profiles = build_raw_player_profiles(frames)
    if not profiles:
        return pd.DataFrame(columns=SAFE_AUTO_MERGE_COLUMNS), pd.DataFrame(columns=MANUAL_DUPLICATE_REVIEW_COLUMNS)

    groups: dict[str, list[dict[str, object]]] = {}
    for profile in profiles:
        groups.setdefault(str(profile["normalized_strict_name"]), []).append(profile)

    safe_rows: list[dict[str, object]] = []
    manual_rows: list[dict[str, object]] = []
    safe_group_count = 0
    manual_group_count = 0

    for normalized_name, group_profiles in sorted(groups.items()):
        if not normalized_name or len(group_profiles) < 2:
            continue
        overlap_seasons = overlapping_values(group_profiles, "seasons_seen")
        overlap_matches = overlapping_values(group_profiles, "match_ids_seen")
        missing_season_evidence = any(not profile["seasons_seen"] for profile in group_profiles)

        if not missing_season_evidence and not overlap_seasons and not overlap_matches:
            safe_group_count += 1
            group_id = f"{club_id}-safe-{safe_group_count:04d}"
            canonical_name = proposed_canonical_name(group_profiles)
            reason = strict_merge_reason(group_profiles)
            for profile in group_profiles:
                safe_rows.append(safe_auto_merge_row(club_id, group_id, normalized_name, profile, canonical_name, reason))
            continue

        manual_group_count += 1
        group_id = f"{club_id}-manual-{manual_group_count:04d}"
        reason = manual_block_reason(missing_season_evidence, overlap_seasons, overlap_matches)
        for profile in group_profiles:
            manual_rows.append(
                manual_duplicate_row(
                    club_id,
                    group_id,
                    profile,
                    overlap_seasons=overlap_seasons,
                    possible_reason=reason,
                    review_notes="Strict name match, but safe auto-merge evidence failed.",
                )
            )

    fuzzy_rows = build_fuzzy_manual_review_rows(club_id, profiles, start_index=manual_group_count + 1)
    manual_rows.extend(fuzzy_rows)

    return (
        pd.DataFrame(safe_rows, columns=SAFE_AUTO_MERGE_COLUMNS),
        pd.DataFrame(manual_rows, columns=MANUAL_DUPLICATE_REVIEW_COLUMNS),
    )


def build_raw_player_profiles(frames: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    profiles: dict[str, dict[str, object]] = {}
    for source_name in ["batting", "bowling", "fielding"]:
        frame = frames.get(source_name, pd.DataFrame())
        if frame.empty:
            continue
        for _, row in frame.iterrows():
            raw_name = first_row_text(row, ["raw_player_name", "player_name", "canonical_player_name"])
            raw_id = first_row_text(row, ["raw_player_id", "player_id", "canonical_player_id"])
            normalized_name = normalize_player_name_for_strict_merge(raw_name)
            if not normalized_name:
                continue
            profile_key = raw_id or f"name:{normalized_name}:{raw_name}"
            profile = profiles.setdefault(
                profile_key,
                {
                    "raw_player_id": raw_id,
                    "raw_player_name": display_player_name(raw_name) or raw_name,
                    "normalized_strict_name": normalized_name,
                    "seasons_seen": set(),
                    "match_ids_seen": set(),
                    "batting_rows": 0,
                    "bowling_rows": 0,
                    "fielding_rows": 0,
                    "total_runs": 0.0,
                    "total_wickets": 0.0,
                    "total_catches": 0.0,
                },
            )
            season = first_row_text(row, ["season"])
            if season:
                profile["seasons_seen"].add(season)
            for column in MATCH_ID_COLUMNS:
                match_id = first_row_text(row, [column])
                if match_id:
                    profile["match_ids_seen"].add(match_id)
            profile[f"{source_name}_rows"] += 1
            if source_name == "batting":
                profile["total_runs"] += numeric_value(row.get("battingAggregate"))
            elif source_name == "bowling":
                profile["total_wickets"] += numeric_value(row.get("bowlingWickets"))
            elif source_name == "fielding":
                profile["total_catches"] += fielding_catches(row)

    return sorted(profiles.values(), key=lambda item: (str(item["normalized_strict_name"]), str(item["raw_player_name"]), str(item["raw_player_id"])))


def build_fuzzy_manual_review_rows(
    club_id: str,
    profiles: list[dict[str, object]],
    *,
    start_index: int,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    candidate_pairs: list[tuple[float, dict[str, object], dict[str, object], set[str]]] = []
    for left, right in itertools.combinations(profiles, 2):
        left_name = str(left["normalized_strict_name"])
        right_name = str(right["normalized_strict_name"])
        if not left_name or not right_name or left_name == right_name:
            continue
        similarity = SequenceMatcher(None, left_name, right_name).ratio()
        if similarity < 0.92:
            continue
        overlap_seasons = set(left["seasons_seen"]) & set(right["seasons_seen"])
        candidate_pairs.append((similarity, left, right, overlap_seasons))

    candidate_pairs.sort(key=lambda item: (-item[0], str(item[1]["raw_player_name"]), str(item[2]["raw_player_name"])))
    for index, (similarity, left, right, overlap_seasons) in enumerate(candidate_pairs[:500], start=start_index):
        group_id = f"{club_id}-manual-{index:04d}"
        possible_reason = "similar names only; strict-normalized names differ"
        if overlap_seasons:
            possible_reason = f"{possible_reason}; season overlap blocks safe auto-merge"
        for profile in [left, right]:
            rows.append(
                manual_duplicate_row(
                    club_id,
                    group_id,
                    profile,
                    overlap_seasons=overlap_seasons,
                    possible_reason=possible_reason,
                    review_notes=f"Manual review only. Similarity={similarity:.3f}.",
                )
            )
    return rows


def safe_auto_merge_row(
    club_id: str,
    group_id: str,
    normalized_name: str,
    profile: dict[str, object],
    canonical_name: str,
    reason: str,
) -> dict[str, object]:
    return {
        "club_id": club_id,
        "candidate_group_id": group_id,
        "normalized_strict_name": normalized_name,
        "raw_player_id": profile["raw_player_id"],
        "raw_player_name": profile["raw_player_name"],
        "seasons_seen": join_values(profile["seasons_seen"]),
        "matches_seen_count": len(profile["match_ids_seen"]),
        "batting_rows": profile["batting_rows"],
        "bowling_rows": profile["bowling_rows"],
        "fielding_rows": profile["fielding_rows"],
        "total_runs": int(profile["total_runs"]),
        "total_wickets": int(profile["total_wickets"]),
        "total_catches": int(profile["total_catches"]),
        "proposed_canonical_name": canonical_name,
        "reason": reason,
        "confidence": "high",
    }


def manual_duplicate_row(
    club_id: str,
    group_id: str,
    profile: dict[str, object],
    *,
    overlap_seasons: set[str],
    possible_reason: str,
    review_notes: str,
) -> dict[str, object]:
    return {
        "club_id": club_id,
        "candidate_group_id": group_id,
        "raw_player_id": profile["raw_player_id"],
        "raw_player_name": profile["raw_player_name"],
        "normalized_name": profile["normalized_strict_name"],
        "seasons_seen": join_values(profile["seasons_seen"]),
        "overlap_seasons": join_values(overlap_seasons),
        "possible_reason": possible_reason,
        "review_notes": review_notes,
    }


def overlapping_values(profiles: list[dict[str, object]], key: str) -> set[str]:
    overlaps: set[str] = set()
    for left, right in itertools.combinations(profiles, 2):
        overlaps.update(set(left[key]) & set(right[key]))
    return overlaps


def manual_block_reason(missing_season_evidence: bool, overlap_seasons: set[str], overlap_matches: set[str]) -> str:
    reasons = []
    if missing_season_evidence:
        reasons.append("missing season evidence blocks safe auto-merge")
    if overlap_seasons:
        reasons.append("same strict-normalized name but season overlap blocks safe auto-merge")
    if overlap_matches:
        reasons.append("same strict-normalized name but match overlap blocks safe auto-merge")
    return "; ".join(reasons) or "safe auto-merge evidence incomplete"


def strict_merge_reason(profiles: list[dict[str, object]]) -> str:
    case_keys = {case_insensitive_name_key(profile["raw_player_name"]) for profile in profiles}
    if len(case_keys) == 1:
        return "exact case-insensitive name match; no season overlap"
    return "punctuation-only name difference; no season overlap"


def proposed_canonical_name(profiles: list[dict[str, object]]) -> str:
    ranked = sorted(
        profiles,
        key=lambda profile: (
            -(int(profile["batting_rows"]) + int(profile["bowling_rows"]) + int(profile["fielding_rows"])),
            -len(str(profile["raw_player_name"])),
            str(profile["raw_player_name"]),
        ),
    )
    return str(ranked[0]["raw_player_name"])


def first_row_text(row: pd.Series, columns: list[str]) -> str:
    for column in columns:
        if column not in row:
            continue
        value = str(row.get(column) or "").strip()
        if value and value.casefold() not in {"nan", "none", "nat"}:
            return value
    return ""


def numeric_value(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def fielding_catches(row: pd.Series) -> float:
    if "fieldingTotalCatches" in row:
        return numeric_value(row.get("fieldingTotalCatches"))
    return numeric_value(row.get("fieldingCatchesNonWK")) + numeric_value(row.get("fieldingCatchesWK"))


def join_values(values: object) -> str:
    return " | ".join(sorted(str(value) for value in values if str(value).strip()))


def case_insensitive_name_key(name: object) -> str:
    return re.sub(r"\s+", " ", str(name or "").strip().casefold())


def build_top_players_preview(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    parts = [
        top_stat_rows(frames.get("batting", pd.DataFrame()), "runs", "battingAggregate", "Top run scorers"),
        top_stat_rows(frames.get("bowling", pd.DataFrame()), "wickets", "bowlingWickets", "Top wicket takers"),
        top_stat_rows(frames.get("fielding", pd.DataFrame()), "catches", "fieldingTotalCatches", "Top catches"),
    ]
    parts = [part for part in parts if not part.empty]
    if not parts:
        return pd.DataFrame(columns=["category", "rank", "player_id", "player_name", "value"])
    return pd.concat(parts, ignore_index=True)


def top_stat_rows(frame: pd.DataFrame, stat_name: str, source_column: str, category: str) -> pd.DataFrame:
    columns = ["category", "rank", "player_id", "player_name", "value"]
    if frame.empty or source_column not in frame:
        return pd.DataFrame(columns=columns)
    rows = frame.copy()
    rows["player_id"] = rows.get("canonical_player_id", rows.get("player_id", "")).fillna("").astype(str)
    rows["player_name"] = rows.get("canonical_player_name", rows.get("player_name", "")).map(display_player_name)
    rows["value"] = pd.to_numeric(rows[source_column], errors="coerce").fillna(0)
    grouped = rows.groupby(["player_id", "player_name"], dropna=False, as_index=False)["value"].sum()
    grouped = grouped[grouped["value"].gt(0)].sort_values(["value", "player_name"], ascending=[False, True]).head(20)
    if grouped.empty:
        return pd.DataFrame(columns=columns)
    grouped.insert(0, "rank", range(1, len(grouped) + 1))
    grouped.insert(0, "category", category)
    grouped["stat"] = stat_name
    return grouped[["category", "rank", "player_id", "player_name", "value"]]


def build_warnings(
    frames: dict[str, pd.DataFrame],
    duplicate_candidates: pd.DataFrame,
    top_players_preview: pd.DataFrame,
) -> list[str]:
    warnings = []
    for name, filename in AGGREGATE_FILES.items():
        if frames.get(name, pd.DataFrame()).empty:
            warnings.append(f"{filename} is missing or has no rows.")
    if not duplicate_candidates.empty:
        warnings.append(f"{len(duplicate_candidates)} likely duplicate player candidate rows need manual review.")
    if top_players_preview.empty:
        warnings.append("No non-zero batting, bowling, or fielding aggregate leaders were available.")
    return warnings


def build_summary(
    club_id: str,
    *,
    frames: dict[str, pd.DataFrame],
    team_grade_audit: pd.DataFrame,
    player_name_audit: pd.DataFrame,
    duplicate_candidates: pd.DataFrame,
    safe_auto_merge_candidates: pd.DataFrame,
    manual_duplicate_review_candidates: pd.DataFrame,
    top_players_preview: pd.DataFrame,
    warnings: list[str],
) -> str:
    seasons = frames["seasons"]
    latest_season = ""
    if not seasons.empty and "name" in seasons:
        current = seasons[seasons.get("isCurrentSeason", "").astype(str).str.casefold().isin({"true", "1", "yes"})]
        latest_season = first_text(current.get("name")) or first_text(seasons.get("name"))
    team_labels = sorted(team_grade_audit.get("team_grade_display", pd.Series(dtype="object")).dropna().astype(str).unique())
    players_count = unique_player_count(player_name_audit)

    lines = [
        f"# {get_club_name(club_id)} Aggregate Review Pack",
        "",
        f"- Club ID: {club_id}",
        f"- Seasons count: {len(seasons)}",
        f"- Latest season: {latest_season or 'unknown'}",
        f"- Team/grade rows: {len(team_grade_audit)}",
        f"- Unique team/grade display labels: {len(team_labels)}",
        f"- Players count: {players_count}",
        f"- Top player preview rows: {len(top_players_preview)}",
        f"- Likely duplicate candidates: {len(duplicate_candidates)}",
        f"- Safe auto-merge groups: {count_groups(safe_auto_merge_candidates)}",
        f"- Manual duplicate review groups: {count_groups(manual_duplicate_review_candidates)}",
        "",
        "## Team/Grade Labels",
        "",
        *(f"- {label}" for label in team_labels[:50]),
        "",
        "## Warnings",
        "",
        *(f"- {warning}" for warning in warnings),
    ]
    if not warnings:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- This pack is generated from aggregate processed CSVs only.",
            "- Match-centre, ball-by-ball, captain, and premiership coverage is not inferred here.",
        ]
    )
    return "\n".join(lines) + "\n"


def unique_player_count(player_name_audit: pd.DataFrame) -> int:
    if player_name_audit.empty:
        return 0
    if "player_id" in player_name_audit and player_name_audit["player_id"].astype(str).str.strip().ne("").any():
        return int(player_name_audit["player_id"].astype(str).str.strip().replace("", pd.NA).dropna().nunique())
    return int(player_name_audit["normalised_name"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique())


def first_text(values: pd.Series | None) -> str:
    if values is None:
        return ""
    clean = values.dropna().astype(str).str.strip()
    clean = clean[clean.ne("")]
    return clean.iloc[0] if not clean.empty else ""


def count_groups(frame: pd.DataFrame) -> int:
    if frame.empty or "candidate_group_id" not in frame:
        return 0
    return int(frame["candidate_group_id"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique())


def normalise_name(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())).strip()


if __name__ == "__main__":
    raise SystemExit(main())
