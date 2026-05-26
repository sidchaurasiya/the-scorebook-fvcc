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
from src.utils.player_identity import display_player_name  # noqa: E402
from src.utils.team_grade import apply_team_grade_display_columns  # noqa: E402


AGGREGATE_FILES = {
    "seasons": "seasons.csv",
    "teams": "teams.csv",
    "players": "players.csv",
    "batting": "all_seasons_batting.csv",
    "bowling": "all_seasons_bowling.csv",
    "fielding": "all_seasons_fielding.csv",
}


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
    top_players_preview = build_top_players_preview(frames)
    warnings = build_warnings(frames, duplicate_candidates, top_players_preview)
    summary = build_summary(
        club_id,
        frames=frames,
        team_grade_audit=team_grade_audit,
        player_name_audit=player_name_audit,
        duplicate_candidates=duplicate_candidates,
        top_players_preview=top_players_preview,
        warnings=warnings,
    )

    seasons_audit.to_csv(output_dir / "seasons_audit.csv", index=False)
    team_grade_audit.to_csv(output_dir / "team_grade_audit.csv", index=False)
    player_name_audit.to_csv(output_dir / "player_name_audit.csv", index=False)
    duplicate_candidates.to_csv(output_dir / "player_duplicate_candidates.csv", index=False)
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


def normalise_name(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())).strip()


if __name__ == "__main__":
    raise SystemExit(main())
