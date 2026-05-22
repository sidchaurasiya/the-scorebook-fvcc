from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from src.data.match_centre_ownership import add_club_match_ownership, is_selected_club_team_name


MILESTONES = [25, 50, 100, 150]


@dataclass(frozen=True)
class MilestoneBuildResult:
    milestones: pd.DataFrame
    validation: pd.DataFrame
    scopes: list[str]


def build_batting_milestones(
    processed_root: Path,
    players_path: Path | None = None,
    aliases_path: Path | None = None,
    scope_names: list[str] | None = None,
    club_team_ids: set[str] | None = None,
    club_name_token: str | None = None,
) -> MilestoneBuildResult:
    scopes = available_scope_dirs(processed_root, scope_names=scope_names)
    frames = [load_scope(scope) for scope in scopes]
    frames = [frame for frame in frames if not frame["matches"].empty]
    if not frames:
        return MilestoneBuildResult(empty_milestones(), empty_validation(), [])

    matches = pd.concat([frame["matches"] for frame in frames], ignore_index=True).drop_duplicates("match_id")
    batting = pd.concat([frame["batting"] for frame in frames], ignore_index=True).drop_duplicates(["match_id", "innings_id", "participant_id", "bat_instance"])
    balls = pd.concat([frame["balls"] for frame in frames], ignore_index=True).drop_duplicates(["match_id", "innings_id", "ball_event_id"])
    innings = pd.concat([frame["innings"] for frame in frames], ignore_index=True).drop_duplicates("innings_id")
    scope_names = [frame["scope_name"] for frame in frames]

    matches = add_match_context(matches, frames, club_team_ids=club_team_ids, club_name_token=club_name_token)
    batting = add_batting_context(batting, matches, innings)
    identity = load_identity_lookup(players_path, aliases_path)
    milestones, validation = calculate_milestones(batting, balls, identity)
    validation = pd.concat([validation, validation_warnings(batting, balls, milestones)], ignore_index=True)
    return MilestoneBuildResult(milestones.sort_values(["match_date", "player_name"], ascending=[False, True]), validation, scope_names)


def available_scope_dirs(processed_root: Path, scope_names: list[str] | None = None) -> list[Path]:
    if not processed_root.exists():
        return []
    allowed = set(scope_names or [])
    return sorted(
        [
            path
            for path in processed_root.iterdir()
            if path.is_dir()
            and (not allowed or path.name in allowed)
            and (path / "all_matches.csv").exists()
            and (path / "all_scorecard_batting.csv").exists()
            and (path / "all_ball_by_ball.csv").exists()
        ],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def load_scope(scope: Path) -> dict[str, Any]:
    return {
        "scope_name": scope.name,
        "matches": read_csv(scope / "all_matches.csv"),
        "batting": read_csv(scope / "all_scorecard_batting.csv"),
        "balls": read_csv(scope / "all_ball_by_ball.csv"),
        "innings": read_csv(scope / "all_match_innings.csv"),
        "summary": read_first_existing(scope, ["refresh_summary.csv", "pilot_summary.csv"]),
    }


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except (OSError, pd.errors.EmptyDataError, pd.errors.ParserError):
        return pd.DataFrame()


def read_first_existing(scope: Path, filenames: list[str]) -> pd.DataFrame:
    for filename in filenames:
        frame = read_csv(scope / filename)
        if not frame.empty:
            return frame
    return pd.DataFrame()


def add_match_context(
    matches: pd.DataFrame,
    frames: list[dict[str, Any]],
    *,
    club_team_ids: set[str] | None = None,
    club_name_token: str | None = None,
) -> pd.DataFrame:
    output = matches.copy()
    for column in ["home_team_id", "away_team_id", "home_team_name", "away_team_name", "first_match_day", "grade_name", "venue_name", "match_type", "result_text"]:
        if column not in output:
            output[column] = pd.NA
    match_dates = pd.to_datetime(output["first_match_day"], errors="coerce", utc=True)
    output["match_date"] = match_dates.dt.date.astype("string")
    output = add_club_match_ownership(output, club_team_ids=club_team_ids, club_name_token=club_name_token)
    home_is_club = output["home_team_id"].astype(str) == output["club_team_id"].astype(str)
    output["team_name"] = output["home_team_name"].where(home_is_club, output["away_team_name"])
    output["opposition_team"] = output["away_team_name"].where(home_is_club, output["home_team_name"])
    if "season" not in output or output["season"].fillna("").astype(str).str.strip().eq("").all():
        season_by_match: dict[str, str] = {}
        for frame in frames:
            summary = frame.get("summary", pd.DataFrame())
            season = first_value(summary, "season_name") or infer_season(frame["scope_name"])
            for match_id in frame["matches"].get("match_id", pd.Series(dtype="object")).dropna().astype(str).tolist():
                season_by_match[match_id] = season
        output["season"] = output["match_id"].astype(str).map(season_by_match).fillna("")
    else:
        output["season"] = output["season"].fillna("")
    return output


def add_batting_context(batting: pd.DataFrame, matches: pd.DataFrame, innings: pd.DataFrame) -> pd.DataFrame:
    if batting.empty:
        return batting
    output = batting.copy()
    context_columns = [
        "match_id",
        "match_date",
        "season",
        "fvcc_team_id",
        "team_name",
        "grade_name",
        "opposition_team",
        "venue_name",
        "match_type",
        "result_text",
    ]
    output = output.merge(matches[context_columns].drop_duplicates("match_id"), on="match_id", how="left")
    if not innings.empty:
        output = output.merge(
            innings[["innings_id", "runs_scored"]].rename(columns={"runs_scored": "team_runs"}),
            on="innings_id",
            how="left",
        )
    output = output[output["team_id"].astype(str) == output["fvcc_team_id"].astype(str)].copy()
    return output


def calculate_milestones(batting: pd.DataFrame, balls: pd.DataFrame, identity: dict[str, dict[str, str]]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    warnings = []
    if batting.empty or balls.empty:
        return empty_milestones(), empty_validation()

    batting_lookup = batting.set_index(["match_id", "innings_id", "participant_id"], drop=False)
    grouped_balls = balls.groupby(["match_id", "innings_id", "striker_participant_id"], dropna=False)
    for key, group in grouped_balls:
        match_id, innings_id, participant_id = [as_text(value) for value in key]
        if (match_id, innings_id, participant_id) not in batting_lookup.index:
            warnings.append(validation_row("ball_by_ball_without_scorecard", "warning", match_id, innings_id, participant_id, "", "", "Ball-by-ball batter innings has no matching FVCC scorecard batting row."))
            continue
        scorecard = batting_lookup.loc[(match_id, innings_id, participant_id)]
        if isinstance(scorecard, pd.DataFrame):
            scorecard = scorecard.iloc[0]
        group = group.sort_values(["innings_order", "over_number", "ball_number", "ball_event_id"]).copy()
        group["runs_bat"] = pd.to_numeric(group.get("runs_bat"), errors="coerce").fillna(0)
        group["legal_ball"] = group.get("is_legal_delivery", pd.Series(dtype="object")).map(parse_bool).astype(int)
        balls_source_used = "source_cumulative" if has_source_cumulative_balls(group) else "derived_legal_balls"
        group["batter_runs"] = cumulative_batter_runs(group)
        group["balls_faced"] = cumulative_balls_faced(group, balls_source_used)
        milestones = {f"balls_to_{target}": milestone_ball(group, target) for target in MILESTONES}
        if all(value is None for value in milestones.values()):
            continue
        final_runs = int(pd.to_numeric(scorecard.get("runs_scored"), errors="coerce")) if pd.notna(scorecard.get("runs_scored")) else int(group["batter_runs"].max())
        source_final_balls = safe_int(group["balls_faced"].dropna().iloc[-1]) if group["balls_faced"].notna().any() else None
        scorecard_final_balls = safe_int(scorecard.get("balls_faced"))
        final_balls = scorecard_final_balls if scorecard_final_balls is not None else source_final_balls
        team_runs = pd.to_numeric(scorecard.get("team_runs"), errors="coerce")
        identity_row = identity.get(participant_id, {})
        player_name = as_text(scorecard.get("player_name") or scorecard.get("player_short_name"))
        not_out = is_not_out(scorecard)
        final_score_display = format_final_score(final_runs, not_out)
        rows.append(
            {
                "player_id": identity_row.get("player_id") or participant_id,
                "player_name": player_name,
                "canonical_player_name": identity_row.get("canonical_name") or player_name,
                "match_id": match_id,
                "match_date": scorecard.get("match_date"),
                "season": scorecard.get("season"),
                "team_name": scorecard.get("team_name"),
                "grade_name": scorecard.get("grade_name"),
                "opposition_team": scorecard.get("opposition_team"),
                "venue_name": scorecard.get("venue_name"),
                "match_type": scorecard.get("match_type"),
                "final_runs": final_runs,
                "final_balls": final_balls,
                "final_score_display": final_score_display,
                **milestones,
                "team_runs": float(team_runs) if pd.notna(team_runs) else pd.NA,
                "team_run_contribution_pct": safe_div(final_runs * 100, float(team_runs)) if pd.notna(team_runs) else pd.NA,
                "result_text": scorecard.get("result_text"),
                "is_not_out": not_out,
                "balls_faced_source_used": balls_source_used,
                "source_ball_by_ball_available": True,
            }
        )
        derived_runs = int(group["batter_runs"].max())
        if final_runs != derived_runs:
            warnings.append(validation_row("final_runs_match_scorecard", "warning", match_id, innings_id, participant_id, final_runs, derived_runs, "Derived ball-by-ball runs differ from scorecard runs.", scorecard_final_balls, source_final_balls, milestones, balls_source_used))
        if scorecard_final_balls is not None and source_final_balls is not None and scorecard_final_balls != source_final_balls:
            warnings.append(validation_row("final_balls_match_scorecard", "warning", match_id, innings_id, participant_id, scorecard_final_balls, source_final_balls, "Ball-by-ball cumulative balls faced differ from scorecard balls faced.", scorecard_final_balls, source_final_balls, milestones, balls_source_used))
        for target in [50, 100]:
            milestone_value = milestones.get(f"balls_to_{target}")
            if scorecard_final_balls is not None and milestone_value is not None and milestone_value > scorecard_final_balls:
                warnings.append(validation_row(f"balls_to_{target}_exceeds_scorecard_balls", "warning", match_id, innings_id, participant_id, scorecard_final_balls, milestone_value, f"Balls to {target} exceeds scorecard balls faced.", scorecard_final_balls, source_final_balls, milestones, balls_source_used))
        if not_out and not has_clear_not_out_status(scorecard):
            warnings.append(validation_row("not_out_status_inferred", "warning", match_id, innings_id, participant_id, "clear not-out dismissal field", "blank dismissal field", "Final score uses a not-out star because no dismissal was recorded for this batter.", scorecard_final_balls, source_final_balls, milestones, balls_source_used))
    milestones = pd.DataFrame(rows, columns=empty_milestones().columns)
    return milestones, pd.DataFrame(warnings, columns=empty_validation().columns)


def validation_warnings(batting: pd.DataFrame, balls: pd.DataFrame, milestones: pd.DataFrame) -> pd.DataFrame:
    rows = []
    ball_keys = set()
    if not balls.empty:
        ball_keys = set(zip(balls["match_id"].astype(str), balls["innings_id"].astype(str), balls["striker_participant_id"].astype(str)))
    for _, row in batting.iterrows():
        final_runs = pd.to_numeric(row.get("runs_scored"), errors="coerce")
        key = (as_text(row.get("match_id")), as_text(row.get("innings_id")), as_text(row.get("participant_id")))
        if pd.notna(final_runs) and final_runs >= 50 and key not in ball_keys:
            rows.append(validation_row("scorecard_50_plus_missing_ball_by_ball", "warning", key[0], key[1], key[2], "ball-by-ball", "missing", "Scorecard has 50+ but no matching ball-by-ball innings, so fastest milestone cannot be verified."))
        if as_text(row.get("participant_id")).startswith("00000000-0000-0000-0000"):
            rows.append(validation_row("placeholder_player_id", "warning", key[0], key[1], key[2], "", "", "Masked or placeholder participant ID appears in scorecard batting rows."))
    if not milestones.empty:
        duplicated = milestones.duplicated(["player_id", "match_id"], keep=False)
        for _, row in milestones[duplicated].iterrows():
            rows.append(validation_row("duplicate_player_match_milestone", "warning", row.get("match_id"), "", row.get("player_id"), "", "", "Duplicate player/match milestone rows detected."))
    return pd.DataFrame(rows, columns=empty_validation().columns)


def load_identity_lookup(players_path: Path | None, aliases_path: Path | None) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    if players_path and players_path.exists():
        players = read_csv(players_path)
        for _, row in players.iterrows():
            player_id = as_text(row.get("player_id"))
            if player_id:
                lookup[player_id] = {"player_id": player_id, "canonical_name": as_text(row.get("player_name"))}
    if aliases_path and aliases_path.exists():
        aliases = read_csv(aliases_path)
        active = aliases.get("is_active", True)
        if not isinstance(active, bool):
            aliases = aliases[aliases["is_active"].map(parse_bool)] if "is_active" in aliases else aliases
        for _, row in aliases.iterrows():
            raw_id = as_text(row.get("raw_player_id"))
            if raw_id:
                lookup[raw_id] = {
                    "player_id": as_text(row.get("canonical_player_id")) or raw_id,
                    "canonical_name": as_text(row.get("canonical_player_name") or row.get("raw_player_name")),
                }
    return lookup


def cumulative_batter_runs(group: pd.DataFrame) -> pd.Series:
    source_runs = numeric_column(group, "striker_runs_scored")
    if source_runs.notna().any():
        return source_runs.ffill().fillna(0)
    return group["runs_bat"].cumsum()


def cumulative_balls_faced(group: pd.DataFrame, source_used: str) -> pd.Series:
    if source_used == "source_cumulative":
        return numeric_column(group, "striker_balls_faced").ffill()
    return group["legal_ball"].cumsum()


def has_source_cumulative_balls(group: pd.DataFrame) -> bool:
    if "striker_balls_faced" not in group:
        return False
    return pd.to_numeric(group["striker_balls_faced"], errors="coerce").notna().any()


def milestone_ball(group: pd.DataFrame, target: int) -> int | None:
    reached = group[group["batter_runs"] >= target]
    if reached.empty:
        return None
    balls_faced = reached.iloc[0]["balls_faced"]
    return safe_int(balls_faced)


def is_not_out(row: pd.Series) -> bool:
    dismissal = as_text(row.get("dismissal_type")).casefold()
    text = as_text(row.get("dismissal_text")).casefold()
    return "not out" in dismissal or "not out" in text or dismissal == ""


def has_clear_not_out_status(row: pd.Series) -> bool:
    dismissal = as_text(row.get("dismissal_type")).casefold()
    text = as_text(row.get("dismissal_text")).casefold()
    return "not out" in dismissal or "not out" in text


def format_final_score(final_runs: int, not_out: bool) -> str:
    return f"{final_runs}{'*' if not_out else ''}"


def validation_row(
    check_name: str,
    severity: str,
    match_id: object,
    innings_id: object,
    player_id: object,
    expected: object,
    actual: object,
    message: str,
    scorecard_final_balls: object = "",
    source_final_balls: object = "",
    milestones: dict[str, object] | None = None,
    balls_faced_source_used: object = "",
) -> dict[str, object]:
    milestones = milestones or {}
    return {
        "check_name": check_name,
        "severity": severity,
        "match_id": match_id,
        "innings_id": innings_id,
        "player_id": player_id,
        "expected_value": expected,
        "actual_value": actual,
        "scorecard_final_balls": scorecard_final_balls,
        "source_final_balls": source_final_balls,
        "milestone_balls_to_50": milestones.get("balls_to_50", ""),
        "milestone_balls_to_100": milestones.get("balls_to_100", ""),
        "balls_faced_source_used": balls_faced_source_used,
        "message": message,
    }


def empty_milestones() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "player_id",
            "player_name",
            "canonical_player_name",
            "match_id",
            "match_date",
            "season",
            "team_name",
            "grade_name",
            "opposition_team",
            "venue_name",
            "match_type",
            "final_runs",
            "final_balls",
            "final_score_display",
            "balls_to_25",
            "balls_to_50",
            "balls_to_100",
            "balls_to_150",
            "team_runs",
            "team_run_contribution_pct",
            "result_text",
            "is_not_out",
            "balls_faced_source_used",
            "source_ball_by_ball_available",
        ]
    )


def empty_validation() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "check_name",
            "severity",
            "match_id",
            "innings_id",
            "player_id",
            "expected_value",
            "actual_value",
            "scorecard_final_balls",
            "source_final_balls",
            "milestone_balls_to_50",
            "milestone_balls_to_100",
            "balls_faced_source_used",
            "message",
        ]
    )


def first_value(frame: pd.DataFrame, column: str) -> str:
    if frame.empty or column not in frame:
        return ""
    values = frame[column].dropna().astype(str)
    return values.iloc[0] if not values.empty else ""


def infer_season(scope_name: str) -> str:
    return scope_name.replace("_", " ").strip()


def is_fvcc_team_name(value: object) -> bool:
    return is_selected_club_team_name(value, "fiji victorian")


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"true", "1", "yes"}


def safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0 or pd.isna(denominator):
        return None
    return float(numerator) / float(denominator)


def as_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return str(value)


def safe_int(value: object) -> int | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    return int(number)


def numeric_column(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(pd.NA, index=frame.index)
    return pd.to_numeric(frame[column], errors="coerce")
