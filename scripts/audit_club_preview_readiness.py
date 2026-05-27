#!/usr/bin/env python3
"""Read-only private-preview readiness audit for a configured club.

This script inspects existing local processed, deploy-safe, and ignored
review-pack outputs. It does not fetch data, rebuild data, or write files.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.club_refresh_utils import resolve_club_id  # noqa: E402
from src.config.club_config import (  # noqa: E402
    get_club_name,
    get_club_short_name,
    get_experimental_dir,
    get_hall_of_fame_dir,
    get_player_profile_dir,
    get_processed_dir,
    get_season_overview_dir,
    load_club_config,
)


DEFAULT_CLUBS = [
    "glen-waverley-hawks",
    "ashwood",
    "plenty",
    "reynella",
    "georges-river-district",
    "southside-east-caulfield",
]

HOF_FILES = [
    "player_win_rates.csv",
    "player_scorecard_milestones.csv",
    "player_bowling_milestones.csv",
    "player_bbb_batting_rates.csv",
    "fastest_batting_milestones.csv",
    "scorecard_record_links.csv",
    "premiership_wins.csv",
    "player_premierships.csv",
]
SEASON_FILES = [
    "season_by_round_scorecards.csv",
    "scorecard_batting_milestones_by_scope.csv",
    "scorecard_bowling_milestones_by_scope.csv",
    "bbb_batting_rates_by_scope.csv",
    "bbb_bowling_dot_rates_by_scope.csv",
]
PROFILE_FILES = [
    "recent_form_batting.csv",
    "recent_form_bowling.csv",
    "performance_breakdown_by_dimension.csv",
    "batting_position_summary.csv",
    "bowling_phase_summary.csv",
    "dismissal_fingerprint_summary.csv",
]
COMMON_REVIEW_SURNAMES = {"singh", "patel", "sharma", "thomas", "khan", "kumar"}
PURPLE_PATTERNS = [
    "#5B3FF2",
    "#6D4CFF",
    "#6C3FF2",
    "#4F46E5",
    "#7C3AED",
    "purple",
    "violet",
    "indigo",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit club preview readiness from local files only.")
    parser.add_argument("--club", action="append", help="Club id to audit. Repeat for multiple clubs.")
    parser.add_argument("--all", action="store_true", help="Audit all pilot clubs.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    clubs = DEFAULT_CLUBS if args.all or not args.club else [resolve_club_id(club) for club in args.club]
    rows = [audit_club(club_id) for club_id in clubs]
    print(markdown_report(rows))
    return 0


def audit_club(club_id: str) -> dict[str, object]:
    processed_dir = get_processed_dir(club_id=club_id)
    hof_dir = get_hall_of_fame_dir(club_id=club_id)
    season_dir = get_season_overview_dir(club_id=club_id)
    profile_dir = get_player_profile_dir(club_id=club_id)
    review_dir = get_experimental_dir(club_id=club_id) / "review_pack"
    config = load_club_config(club_id)

    batting = read_csv(processed_dir / "all_seasons_batting.csv")
    bowling = read_csv(processed_dir / "all_seasons_bowling.csv")
    fielding = read_csv(processed_dir / "all_seasons_fielding.csv")
    players = read_csv(processed_dir / "players.csv")
    teams = read_csv(processed_dir / "teams.csv")
    win_rates = read_csv(hof_dir / "player_win_rates.csv")
    milestones = read_csv(hof_dir / "player_scorecard_milestones.csv")
    premiership_wins = read_csv(hof_dir / "premiership_wins.csv")
    player_premierships = read_csv(hof_dir / "player_premierships.csv")
    season_rounds = read_csv(season_dir / "season_by_round_scorecards.csv")
    safe_merges = read_csv(review_dir / "safe_auto_merge_candidates.csv")
    manual_merges = read_csv(review_dir / "manual_duplicate_review_candidates.csv")
    team_grade_audit = read_csv(review_dir / "team_grade_audit.csv")

    safe_summary = summarize_safe_merges(safe_merges)
    team_groups = team_group_values([batting, bowling, fielding, teams, team_grade_audit, premiership_wins, player_premierships])
    self_opponents = self_opponent_warnings(season_rounds, club_id)

    return {
        "club_id": club_id,
        "club_name": get_club_name(club_id),
        "processed_rows": {
            "players": len(players),
            "batting": len(batting),
            "bowling": len(bowling),
            "fielding": len(fielding),
        },
        "missing_deploy_safe_files": missing_files(hof_dir, HOF_FILES)
        + missing_files(season_dir, SEASON_FILES)
        + missing_files(profile_dir, PROFILE_FILES),
        "hof_rows": {filename: csv_row_count(hof_dir / filename) for filename in HOF_FILES},
        "season_rows": {filename: csv_row_count(season_dir / filename) for filename in SEASON_FILES},
        "profile_rows": {filename: csv_row_count(profile_dir / filename) for filename in PROFILE_FILES},
        "win_rates": summarize_win_rates(win_rates),
        "thirties": summarize_thirties(milestones),
        "link_sources": summarize_link_sources(batting, bowling, fielding, season_rounds),
        "self_opponent_warnings": self_opponents,
        "premierships": {
            "wins": len(premiership_wins),
            "player_rows": len(player_premierships),
            "captains_recorded": nonblank_count(premiership_wins, "captain_name"),
        },
        "team_groups": sorted(team_groups),
        "review": {
            "safe_auto_merge_groups": safe_summary["groups"],
            "safe_auto_merge_rows": len(safe_merges),
            "non_suspicious_safe_groups": safe_summary["non_suspicious_groups"],
            "suspicious_safe_groups": safe_summary["suspicious_groups"],
            "manual_duplicate_groups": count_groups(manual_merges),
            "team_grade_rows": len(team_grade_audit),
        },
        "branding": summarize_branding(config),
    }


def markdown_report(rows: list[dict[str, object]]) -> str:
    lines = [
        "# Multi-Club Private Preview Readiness Audit",
        "",
        "Read-only audit from existing local processed/deploy-safe outputs and ignored review packs.",
        "",
        "| club_id | missing files | win-rate coverage | 30s coverage | safe merges | manual duplicate groups | premiership rows | captain rows | team groups | self-opponent warnings | theme config |",
        "|---|---:|---|---|---|---:|---:|---:|---|---:|---|",
    ]
    for row in rows:
        win = row["win_rates"]
        thirties = row["thirties"]
        review = row["review"]
        prem = row["premierships"]
        branding = row["branding"]
        safe_text = (
            f"{review['non_suspicious_safe_groups']} non-susp / "
            f"{review['suspicious_safe_groups']} suspicious"
        )
        theme_text = "ok" if branding["complete"] else "missing " + ", ".join(branding["missing"])
        lines.append(
            "| "
            f"`{row['club_id']}` | "
            f"{len(row['missing_deploy_safe_files'])} | "
            f"{win['rows']} rows, {win['nonzero_win_pct']} non-zero | "
            f"{thirties['rows']} rows, {thirties['nonzero_thirties']} non-zero | "
            f"{safe_text} | "
            f"{review['manual_duplicate_groups']} | "
            f"{prem['wins']} | "
            f"{prem['captains_recorded']} | "
            f"{', '.join(row['team_groups']) or 'none'} | "
            f"{len(row['self_opponent_warnings'])} | "
            f"{theme_text} |"
        )
    lines.append("")

    for row in rows:
        lines.extend(
            [
                f"## {row['club_name']}",
                "",
                f"- Club ID: `{row['club_id']}`",
                f"- Deploy-safe missing files: {', '.join(row['missing_deploy_safe_files']) or 'none'}",
                f"- HOF rows: {format_counts(row['hof_rows'])}",
                f"- Season Overview rows: {format_counts(row['season_rows'])}",
                f"- Player Profile rows: {format_counts(row['profile_rows'])}",
                f"- Win-rate sanity: {row['win_rates']}",
                f"- 30s sanity: {row['thirties']}",
                f"- Link source sanity: {row['link_sources']}",
                f"- Premiership evidence: {row['premierships']}",
                f"- Team groups detected: {', '.join(row['team_groups']) or 'none'}",
                f"- Duplicate review: {row['review']}",
                f"- Self-opponent warning samples: {format_warning_samples(row['self_opponent_warnings'])}",
                f"- Theme config: {row['branding']}",
                "",
            ]
        )
    purple_hits = source_purple_hits()
    lines.extend(
        [
            "## Source Purple Audit",
            "",
            f"- Visible-source purple/violet/indigo pattern hits in `src/ui`: {purple_hits}",
            "- These are source-level hits only; runtime smoke still verifies club-specific CSS variables and visible theming.",
        ]
    )
    return "\n".join(lines) + "\n"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, dtype=str, keep_default_na=False, low_memory=False)
    except (OSError, pd.errors.ParserError):
        return pd.DataFrame()


def csv_row_count(path: Path) -> int:
    frame = read_csv(path)
    return len(frame)


def missing_files(root: Path, filenames: list[str]) -> list[str]:
    return [str(root / filename) for filename in filenames if not (root / filename).exists()]


def nonblank_count(frame: pd.DataFrame, column: str) -> int:
    if frame.empty or column not in frame:
        return 0
    return int(frame[column].fillna("").astype(str).str.strip().ne("").sum())


def summarize_win_rates(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty:
        return {"rows": 0, "with_result_matches": 0, "nonzero_win_pct": 0, "zero_win_pct": 0}
    pct = pd.to_numeric(frame.get("win_pct", pd.Series(dtype=str)), errors="coerce")
    matches = pd.to_numeric(frame.get("matches_with_result", pd.Series(dtype=str)), errors="coerce").fillna(0)
    return {
        "rows": len(frame),
        "with_result_matches": int(matches.gt(0).sum()),
        "nonzero_win_pct": int(pct.fillna(0).gt(0).sum()),
        "zero_win_pct": int((pct.fillna(-1) == 0).sum()),
    }


def summarize_thirties(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty:
        return {"rows": 0, "nonzero_thirties": 0, "nonzero_fifties": 0, "nonzero_hundreds": 0}
    return {
        "rows": len(frame),
        "nonzero_thirties": int(numeric_series(frame, "thirties").gt(0).sum()),
        "nonzero_fifties": int(numeric_series(frame, "fifties").gt(0).sum()),
        "nonzero_hundreds": int(numeric_series(frame, "hundreds").gt(0).sum()),
    }


def summarize_link_sources(
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
    season_rounds: pd.DataFrame,
) -> dict[str, int]:
    aggregate = pd.concat([frame for frame in [batting, bowling, fielding] if not frame.empty], ignore_index=True, sort=False)
    canonical_ids = nonblank_count(aggregate, "canonical_player_id") if not aggregate.empty else 0
    seasons = nonblank_count(aggregate, "season") if not aggregate.empty else 0
    round_best_batters = nonblank_count(season_rounds, "best_batter")
    round_best_bowlers = nonblank_count(season_rounds, "best_bowler")
    scorecard_links = nonblank_count(season_rounds, "match_id")
    return {
        "aggregate_rows_with_player_id": canonical_ids,
        "aggregate_rows_with_season": seasons,
        "season_round_best_batters": round_best_batters,
        "season_round_best_bowlers": round_best_bowlers,
        "season_round_scorecard_ids": scorecard_links,
    }


def summarize_safe_merges(frame: pd.DataFrame) -> dict[str, int]:
    if frame.empty or "candidate_group_id" not in frame:
        return {"groups": 0, "non_suspicious_groups": 0, "suspicious_groups": 0}
    groups = 0
    suspicious = 0
    for _, group in frame.groupby("candidate_group_id"):
        groups += 1
        if suspicious_safe_group_flags(group):
            suspicious += 1
    return {"groups": groups, "non_suspicious_groups": groups - suspicious, "suspicious_groups": suspicious}


def suspicious_safe_group_flags(group: pd.DataFrame) -> list[str]:
    flags: list[str] = []
    runs = numeric_series(group, "total_runs").sum()
    wickets = numeric_series(group, "total_wickets").sum()
    catches = numeric_series(group, "total_catches").sum()
    row_proxy = 0
    for _, row in group.iterrows():
        row_proxy += max(
            safe_int(row.get("batting_rows")),
            safe_int(row.get("bowling_rows")),
            safe_int(row.get("fielding_rows")),
            safe_int(row.get("matches_seen_count")),
        )
    if len(group) > 3:
        flags.append(">3 profiles")
    high_stats = runs >= 3000 or wickets >= 150 or catches >= 80 or row_proxy >= 40
    if high_stats:
        flags.append("high stats")
    raw_names = [str(value or "").strip() for value in group.get("raw_player_name", pd.Series(dtype=str))]
    if any(has_initial_like_token(name) for name in raw_names):
        flags.append("initial-like token")
    if len({first_middle_tokens(name) for name in raw_names}) > 1:
        flags.append("first/middle variation")
    surname = last_token(str(group.iloc[0].get("proposed_canonical_name", "")))
    if surname in COMMON_REVIEW_SURNAMES:
        flags.append("common surname")
    if adjacent_season_handoff(group) and (high_stats or len(group) > 2 or surname in COMMON_REVIEW_SURNAMES):
        flags.append("adjacent handoff caution")
    return flags


def count_groups(frame: pd.DataFrame) -> int:
    if frame.empty or "candidate_group_id" not in frame:
        return 0
    return int(frame["candidate_group_id"].dropna().astype(str).str.strip().replace("", pd.NA).dropna().nunique())


def team_group_values(frames: list[pd.DataFrame]) -> set[str]:
    groups: set[str] = set()
    for frame in frames:
        if frame.empty:
            continue
        text_columns = [
            column
            for column in [
                "team_group",
                "team_gender",
                "team_name",
                "club_team_name",
                "fvcc_team_name",
                "grade_name",
                "grade_label",
                "team_grade_display",
                "competition_name",
                "teams",
                "grades",
            ]
            if column in frame
        ]
        if not text_columns:
            continue
        for _, row in frame[text_columns].drop_duplicates().iterrows():
            groups.add(classify_team_group(" ".join(str(value) for value in row.values)))
    return {group for group in groups if group}


def classify_team_group(value: object) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    if re.search(r"\b(women|womens|woman|female|ladies)\b", normalized):
        return "women"
    return "men"


def self_opponent_warnings(season_rounds: pd.DataFrame, club_id: str) -> list[str]:
    if season_rounds.empty or "opponent_name" not in season_rounds:
        return []
    tokens = club_tokens(club_id)
    warnings: list[str] = []
    for _, row in season_rounds.iterrows():
        opponent_key = normalize_name(row.get("opponent_name"))
        if not opponent_key:
            continue
        if any(names_match(opponent_key, token) for token in tokens):
            label = " | ".join(
                str(row.get(column, "")).strip()
                for column in ["season", "grade_name", "round_display", "opponent_name", "match_id"]
                if str(row.get(column, "")).strip()
            )
            if label not in warnings:
                warnings.append(label)
        if len(warnings) >= 10:
            break
    return warnings


def club_tokens(club_id: str) -> set[str]:
    values = {get_club_name(club_id), get_club_short_name(club_id)}
    tokens: set[str] = set()
    for value in values:
        normalized = normalize_name(value)
        if not normalized:
            continue
        tokens.add(normalized)
        tokens.add(re.sub(r"\b(cricket|club|cc)\b", "", normalized).strip())
    return {token for token in tokens if token}


def normalize_name(value: object) -> str:
    text = str(value or "").casefold().replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(cricket club|cc)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def names_match(left: str, right: str) -> bool:
    return bool(left and right and (left == right or left.startswith(f"{right} ") or right.startswith(f"{left} ")))


def summarize_branding(config: dict[str, object]) -> dict[str, object]:
    branding = config.get("branding", {}) if isinstance(config, dict) else {}
    required = ["primary_colour", "secondary_colour", "background_colour", "accent_colour"]
    missing = [key for key in required if not str(branding.get(key, "") or "").strip()]
    return {
        "complete": not missing,
        "missing": missing,
        "primary": branding.get("primary_colour", ""),
        "secondary": branding.get("secondary_colour", ""),
        "accent": branding.get("accent_colour", ""),
    }


def numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series([0] * len(frame), index=frame.index, dtype="float64")
    return pd.to_numeric(frame[column], errors="coerce").fillna(0)


def safe_int(value: object) -> int:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").fillna(0).iloc[0]
    return int(numeric)


def name_tokens(name: object) -> list[str]:
    return re.findall(r"[A-Za-z0-9]+", str(name or "").casefold())


def has_initial_like_token(name: object) -> bool:
    tokens = name_tokens(name)
    return any(len(token) <= 1 for token in (tokens[:-1] or tokens[:1]))


def first_middle_tokens(name: object) -> tuple[str, ...]:
    tokens = name_tokens(name)
    return tuple(tokens[:-1])


def last_token(name: object) -> str:
    tokens = name_tokens(name)
    return tokens[-1] if tokens else ""


def adjacent_season_handoff(group: pd.DataFrame) -> bool:
    ranges: list[tuple[int, int]] = []
    for value in group.get("seasons_seen", pd.Series(dtype=str)).fillna("").astype(str):
        years = [season_start_year(season.strip()) for season in value.split("|") if season.strip()]
        clean_years = [year for year in years if year is not None]
        if clean_years:
            ranges.append((min(clean_years), max(clean_years)))
    ranges.sort()
    return any(right[0] - left[1] == 1 for left in ranges for right in ranges if left != right)


def season_start_year(season: str) -> int | None:
    match = re.search(r"(\d{4})/(\d{2})", season)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d{4})", season)
    return int(match.group(1)) if match else None


def source_purple_hits() -> int:
    total = 0
    for path in (ROOT / "src" / "ui").glob("*.py"):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for pattern in PURPLE_PATTERNS:
            total += text.casefold().count(pattern.casefold())
    return total


def format_counts(counts: dict[str, int]) -> str:
    return ", ".join(f"{name}={count}" for name, count in counts.items())


def format_warning_samples(values: list[str]) -> str:
    if not values:
        return "none"
    return "; ".join(values[:3]) + (f"; +{len(values) - 3} more" if len(values) > 3 else "")


if __name__ == "__main__":
    raise SystemExit(main())
