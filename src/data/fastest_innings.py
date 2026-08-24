"""Govern and publish fastest-innings records from local delivery evidence.

This module deliberately sits after the match-centre milestone detector.  The
detector reconstructs candidate crossings; this layer decides whether a row is
safe to publish, needs review, or must be rejected.  It never fetches data and
is not imported by Streamlit rendering code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data.match_centre_milestones import (
    add_batting_context,
    add_match_context,
    available_scope_dirs,
    build_batting_milestones,
    load_scope,
)
from src.utils.player_identity import apply_player_identity_mapping, is_private_or_anonymised_player


EVENT_KEY_COLUMNS = ["match_id", "innings_id", "participant_id"]
MILESTONE_TARGETS = (25, 50, 100, 150)
MIN_PLAUSIBLE_MILESTONE_BALLS = {50: 9, 100: 17}
FATAL_RUN_RECONCILIATION_CHECKS = {
    "trusted_runs_mismatch_scorecard_excluded",
}
ADVISORY_RUN_RECONCILIATION_CHECKS = {
    "derived_runs_mismatch_scorecard",
    "final_runs_match_scorecard",
    "trusted_runs_mismatch_scorecard_partial_milestones",
}
FATAL_DETECTOR_CHECKS = {
    "duplicate_player_match_milestone",
    *FATAL_RUN_RECONCILIATION_CHECKS,
}
ADVISORY_BALL_RECONCILIATION_CHECKS = {
    "final_balls_match_scorecard",
}


@dataclass(frozen=True)
class FastestInningsGovernanceResult:
    published: pd.DataFrame
    review: pd.DataFrame
    rejected: pd.DataFrame
    audit: pd.DataFrame


@dataclass(frozen=True)
class FastestInningsBuildResult:
    governance: FastestInningsGovernanceResult
    detector_validation: pd.DataFrame
    coverage: pd.DataFrame
    scorecard_only_achievements: pd.DataFrame
    scopes: tuple[str, ...]


def build_governed_fastest_innings(
    *,
    club_id: str,
    processed_root: Path,
    players_path: Path,
    aliases_path: Path,
    club_team_ids: set[str],
    club_name_token: str,
) -> FastestInningsBuildResult:
    """Build publishable rows from ignored local match-centre source folders."""
    detected = build_batting_milestones(
        processed_root,
        players_path=players_path,
        aliases_path=aliases_path,
        club_team_ids=club_team_ids,
        club_name_token=club_name_token,
    )
    if not detected.scopes:
        raise FileNotFoundError(
            f"No reproducible match-centre scopes found under {processed_root}. "
            "Restore or refresh the ignored delivery sources before rebuilding fastest innings."
        )
    candidates = resolve_candidate_identities(detected.milestones, club_id=club_id)
    candidates = apply_detector_evidence(candidates, detected.validation)
    governance = govern_fastest_innings_candidates(candidates, detected.validation)
    coverage, scorecard_only = build_fastest_innings_coverage(
        processed_root,
        club_team_ids=club_team_ids,
        club_name_token=club_name_token,
    )
    scorecard_only = resolve_candidate_identities(scorecard_only, club_id=club_id)
    if not scorecard_only.empty:
        safe_scorecard_only = ~scorecard_only.apply(private_candidate, axis=1)
        safe_scorecard_only &= ~scorecard_only.apply(unresolved_candidate_identity, axis=1)
        scorecard_only = stable_sort(scorecard_only.loc[safe_scorecard_only].copy()).reset_index(drop=True)
    return FastestInningsBuildResult(
        governance=governance,
        detector_validation=detected.validation.copy(),
        coverage=coverage,
        scorecard_only_achievements=scorecard_only,
        scopes=tuple(detected.scopes),
    )


def write_fastest_innings_outputs(
    result: FastestInningsBuildResult,
    *,
    output: Path,
    validation_dir: Path,
    prefix: str,
) -> None:
    """Write only the compact prepared output and its directly related audits."""
    governance = result.governance
    validation_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_csv_atomic(governance.published, output)
    write_csv_atomic(governance.audit, validation_dir / f"{prefix}_fastest_innings_validation.csv")
    write_csv_atomic(governance.review, validation_dir / f"{prefix}_fastest_innings_review_candidates.csv")
    write_csv_atomic(governance.rejected, validation_dir / f"{prefix}_fastest_innings_rejected_candidates.csv")
    write_csv_atomic(result.coverage, validation_dir / f"{prefix}_fastest_innings_coverage.csv")
    write_csv_atomic(
        result.scorecard_only_achievements,
        validation_dir / f"{prefix}_scorecard_only_batting_achievements.csv",
    )
    write_csv_atomic(
        result.detector_validation,
        validation_dir / f"{prefix}_fastest_innings_detector_validation.csv",
    )


def write_csv_atomic(frame: pd.DataFrame, path: Path) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    frame.to_csv(temporary, index=False)
    temporary.replace(path)


def resolve_candidate_identities(candidates: pd.DataFrame, *, club_id: str) -> pd.DataFrame:
    """Attach the current canonical profile identity to every detector row."""
    if candidates.empty:
        output = candidates.copy()
        if "canonical_player_id" not in output:
            output["canonical_player_id"] = pd.Series(dtype="object")
        return output
    output = candidates.copy()
    output["raw_player_id"] = output.get("participant_id", "")
    output["raw_player_name"] = output.get("player_name", "")
    mapped = apply_player_identity_mapping(output, club_id=club_id)
    mapped["player_id"] = mapped["canonical_player_id"]
    mapped["canonical_player_name"] = mapped["canonical_player_name"].fillna(mapped.get("player_name"))
    return mapped.drop(columns=["raw_player_id", "raw_player_name"], errors="ignore")


def apply_detector_evidence(candidates: pd.DataFrame, validation: pd.DataFrame) -> pd.DataFrame:
    """Prefer verified delivery final balls when scorecard balls disagree."""
    if candidates.empty:
        return candidates.copy()
    output = candidates.copy()
    evidence = detector_evidence_by_event(validation)
    scorecard_values = []
    delivery_values = []
    source_labels = []
    unresolved = []
    final_values = []
    for _, row in output.iterrows():
        item = evidence.get(event_key(row), {})
        scorecard_balls = positive_number(item.get("scorecard_final_balls"))
        delivery_balls = positive_number(item.get("source_final_balls"))
        mismatch = "final_balls_match_scorecard" in item.get("checks", set())
        final_balls = number(row.get("final_balls"))
        if mismatch and delivery_balls is not None:
            final_balls = delivery_balls
            source_label = "verified_delivery_override_scorecard"
            needs_review = False
        elif mismatch:
            source_label = "unresolved_scorecard_delivery_mismatch"
            needs_review = True
        else:
            source_label = clean_text(row.get("balls_faced_source_used")) or "detector_final_balls"
            needs_review = False
        scorecard_values.append(scorecard_balls)
        delivery_values.append(delivery_balls)
        source_labels.append(source_label)
        unresolved.append(needs_review)
        final_values.append(final_balls)
    output["scorecard_final_balls"] = scorecard_values
    output["verified_delivery_final_balls"] = delivery_values
    output["governance_final_balls_source"] = source_labels
    output["_final_balls_reconciliation_unresolved"] = unresolved
    output["final_balls"] = final_values
    return output


def govern_fastest_innings_candidates(
    candidates: pd.DataFrame,
    detector_validation: pd.DataFrame,
) -> FastestInningsGovernanceResult:
    """Classify detector candidates using strict publication governance."""
    if candidates.empty:
        empty = candidates.copy()
        return FastestInningsGovernanceResult(empty, empty, empty, empty_audit())

    rows = candidates.copy()
    for column in [*EVENT_KEY_COLUMNS, "canonical_player_id", "canonical_player_name"]:
        if column not in rows:
            rows[column] = ""
    duplicate_keys = rows.duplicated(EVENT_KEY_COLUMNS, keep=False)
    detector_checks = detector_checks_by_event(detector_validation)
    classifications: list[dict[str, object]] = []

    for position, (_, row) in enumerate(rows.iterrows()):
        key = event_key(row)
        reasons: list[str] = []
        status = "published"

        if any(not part for part in key):
            reasons.append("missing_event_key")
        if bool(duplicate_keys.iloc[position]):
            reasons.append("duplicate_event")
        if private_candidate(row):
            reasons.append("private_or_masked_player")
        if unresolved_candidate_identity(row):
            reasons.append("unresolved_identity")
        if not bool_value(row.get("source_ball_by_ball_available")):
            status = "review"
            reasons.append("scorecard_only_not_fastest_evidence")
        if bool_value(row.get("_final_balls_reconciliation_unresolved")):
            status = "review"
            reasons.append("unresolved_scorecard_delivery_ball_mismatch")

        milestone_reasons = validate_milestone_values(row)
        reasons.extend(milestone_reasons)

        checks = detector_checks.get(key, set())
        fatal_checks = sorted(
            check for check in checks if check in FATAL_DETECTOR_CHECKS or check.startswith("excluded:")
        )
        advisory_checks = sorted(checks & ADVISORY_RUN_RECONCILIATION_CHECKS)
        advisory_checks.extend(sorted(checks & ADVISORY_BALL_RECONCILIATION_CHECKS))
        if fatal_checks:
            reasons.extend(f"detector:{check}" for check in fatal_checks)
        if advisory_checks:
            reasons.extend(f"detector_advisory:{check}" for check in advisory_checks)

        hard_reasons = [
            reason
            for reason in reasons
            if reason != "scorecard_only_not_fastest_evidence"
            and reason != "unresolved_scorecard_delivery_ball_mismatch"
            and not reason.startswith("detector_advisory:")
        ]
        if hard_reasons:
            status = "rejected"

        classifications.append(
            {
                "governance_status": status,
                "reason_codes": "|".join(dict.fromkeys(reasons)) or "verified_delivery_and_scorecard_reconciliation",
            }
        )

    classified = pd.concat([rows.reset_index(drop=True), pd.DataFrame(classifications)], axis=1)
    classified = stable_sort(classified)
    published = classified[classified["governance_status"].eq("published")].drop(
        columns=[
            "governance_status",
            "reason_codes",
            "_final_balls_reconciliation_unresolved",
        ],
        errors="ignore",
    )
    review = classified[classified["governance_status"].eq("review")].copy()
    rejected = classified[classified["governance_status"].eq("rejected")].copy()
    audit_columns = [
        *EVENT_KEY_COLUMNS,
        "canonical_player_id",
        "canonical_player_name",
        "final_runs",
        "final_balls",
        *[f"balls_to_{target}" for target in MILESTONE_TARGETS],
        "source_ball_by_ball_available",
        "scorecard_final_balls",
        "verified_delivery_final_balls",
        "governance_final_balls_source",
        "runs_source_used",
        "balls_faced_source_used",
        "governance_status",
        "reason_codes",
    ]
    for column in audit_columns:
        if column not in classified:
            classified[column] = pd.NA
    audit = classified[audit_columns].copy()
    return FastestInningsGovernanceResult(
        published.reset_index(drop=True),
        review.reset_index(drop=True),
        rejected.reset_index(drop=True),
        audit.reset_index(drop=True),
    )


def validate_milestone_values(row: pd.Series) -> list[str]:
    reasons: list[str] = []
    final_runs = number(row.get("final_runs"))
    final_balls = number(row.get("final_balls"))
    values: list[tuple[int, float]] = []
    for target in MILESTONE_TARGETS:
        milestone = number(row.get(f"balls_to_{target}"))
        if milestone is None:
            continue
        values.append((target, milestone))
        if milestone <= 0:
            reasons.append(f"balls_to_{target}_not_positive")
        if final_runs is None or final_runs < target:
            reasons.append(f"balls_to_{target}_exceeds_final_runs")
        if final_balls is None or final_balls <= 0:
            reasons.append("missing_reliable_final_balls")
        elif milestone > final_balls:
            reasons.append(f"balls_to_{target}_exceeds_final_balls")
        minimum = MIN_PLAUSIBLE_MILESTONE_BALLS.get(target)
        if minimum is not None and milestone < minimum:
            reasons.append(f"balls_to_{target}_below_plausibility_threshold")
    if not values:
        reasons.append("no_delivery_milestone")
    for (_, previous), (target, current) in zip(values, values[1:]):
        if current < previous:
            reasons.append(f"balls_to_{target}_before_prior_milestone")
    return reasons


def build_fastest_innings_coverage(
    processed_root: Path,
    *,
    club_team_ids: set[str],
    club_name_token: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Profile exact scorecard and delivery coverage from the rebuild inputs."""
    scopes = available_scope_dirs(processed_root)
    frames = [load_scope(scope) for scope in scopes]
    frames = [frame for frame in frames if not frame["matches"].empty]
    if not frames:
        return empty_coverage(), pd.DataFrame()

    matches = pd.concat([frame["matches"] for frame in frames], ignore_index=True).drop_duplicates("match_id")
    batting = pd.concat([frame["batting"] for frame in frames], ignore_index=True).drop_duplicates(
        ["match_id", "innings_id", "participant_id", "bat_instance"]
    )
    balls = pd.concat([frame["balls"] for frame in frames], ignore_index=True).drop_duplicates(
        ["match_id", "innings_id", "ball_event_id"]
    )
    innings = pd.concat([frame["innings"] for frame in frames], ignore_index=True).drop_duplicates("innings_id")
    matches = add_match_context(
        matches,
        frames,
        club_team_ids=club_team_ids,
        club_name_token=club_name_token,
    )
    batting = add_batting_context(batting, matches, innings)
    if batting.empty:
        return coverage_rows(matches, batting, balls), pd.DataFrame()

    ball_keys = set(
        zip(
            balls.get("match_id", pd.Series(dtype="object")).astype(str),
            balls.get("innings_id", pd.Series(dtype="object")).astype(str),
            balls.get("striker_participant_id", pd.Series(dtype="object")).astype(str),
        )
    )
    batting["has_delivery_balls"] = [
        (str(row.match_id), str(row.innings_id), str(row.participant_id)) in ball_keys
        for row in batting.itertuples()
    ]
    batting["scorecard_runs"] = pd.to_numeric(batting.get("runs_scored"), errors="coerce")
    scorecard_only = batting[batting["scorecard_runs"].ge(50) & ~batting["has_delivery_balls"]].copy()
    scorecard_only["confirmed_50"] = True
    scorecard_only["confirmed_100"] = scorecard_only["scorecard_runs"].ge(100)
    scorecard_only["fastest_eligibility"] = "not_eligible_without_delivery_data"
    columns = [
        "match_id",
        "innings_id",
        "participant_id",
        "player_name",
        "match_date",
        "season",
        "team_name",
        "grade_name",
        "opposition_team",
        "scorecard_runs",
        "balls_faced",
        "confirmed_50",
        "confirmed_100",
        "fastest_eligibility",
    ]
    for column in columns:
        if column not in scorecard_only:
            scorecard_only[column] = pd.NA
    return coverage_rows(matches, batting, balls), scorecard_only[columns]


def coverage_rows(matches: pd.DataFrame, batting: pd.DataFrame, balls: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    rows.append(coverage_summary_row("overall", matches, batting, balls))
    if not batting.empty and "season" in batting:
        for season, season_batting in batting.groupby("season", dropna=False, sort=True):
            match_ids = set(season_batting["match_id"].dropna().astype(str))
            rows.append(
                coverage_summary_row(
                    str(season or "unknown"),
                    matches[matches["match_id"].astype(str).isin(match_ids)],
                    season_batting,
                    balls[balls.get("match_id", pd.Series(dtype="object")).astype(str).isin(match_ids)],
                )
            )
    return pd.DataFrame(rows, columns=empty_coverage().columns)


def coverage_summary_row(
    scope: str,
    matches: pd.DataFrame,
    batting: pd.DataFrame,
    balls: pd.DataFrame,
) -> dict[str, object]:
    has_delivery = batting.get("has_delivery_balls", pd.Series(False, index=batting.index)).fillna(False).astype(bool)
    scorecard_runs = pd.to_numeric(
        batting.get("scorecard_runs", pd.Series(pd.NA, index=batting.index)),
        errors="coerce",
    )
    return {
        "scope": scope,
        "total_matches": unique_count(matches, "match_id"),
        "matches_with_scorecards": unique_count(batting, "match_id"),
        "matches_with_ball_by_ball": unique_count(balls, "match_id"),
        "scorecard_batting_innings": len(batting),
        "innings_with_reliable_delivery_balls": int(has_delivery.sum()),
        "innings_without_reliable_delivery_balls": int((~has_delivery).sum()),
        "scorecard_only_50_plus": int((scorecard_runs.ge(50) & ~has_delivery).sum()),
        "scorecard_only_100_plus": int((scorecard_runs.ge(100) & ~has_delivery).sum()),
        "ball_events": len(balls),
    }


def detector_checks_by_event(validation: pd.DataFrame) -> dict[tuple[str, str, str], set[str]]:
    output: dict[tuple[str, str, str], set[str]] = {}
    if validation.empty:
        return output
    for row in validation.to_dict("records"):
        key = (
            clean_text(row.get("match_id")),
            clean_text(row.get("innings_id")),
            clean_text(row.get("player_id")),
        )
        check = clean_text(row.get("check_name"))
        severity = clean_text(row.get("severity")).casefold()
        if check and (
            severity == "excluded"
            or check in FATAL_DETECTOR_CHECKS
            or check in ADVISORY_BALL_RECONCILIATION_CHECKS
            or check in ADVISORY_RUN_RECONCILIATION_CHECKS
        ):
            stored_check = f"excluded:{check}" if severity == "excluded" else check
            output.setdefault(key, set()).add(stored_check)
    return output


def detector_evidence_by_event(validation: pd.DataFrame) -> dict[tuple[str, str, str], dict[str, object]]:
    output: dict[tuple[str, str, str], dict[str, object]] = {}
    if validation.empty:
        return output
    for row in validation.to_dict("records"):
        key = (
            clean_text(row.get("match_id")),
            clean_text(row.get("innings_id")),
            clean_text(row.get("player_id")),
        )
        item = output.setdefault(key, {"checks": set()})
        check = clean_text(row.get("check_name"))
        if check:
            item["checks"].add(check)
        for column in ["scorecard_final_balls", "source_final_balls"]:
            value = positive_number(row.get(column))
            if value is not None:
                item[column] = value
    return output


def private_candidate(row: pd.Series) -> bool:
    return any(
        is_private_or_anonymised_player(row.get(column))
        for column in ["player_name", "canonical_player_name"]
    )


def unresolved_candidate_identity(row: pd.Series) -> bool:
    participant_id = clean_text(row.get("participant_id"))
    canonical_id = clean_text(row.get("canonical_player_id"))
    return (
        not canonical_id
        or participant_id.startswith("00000000-0000-0000-0000")
        or canonical_id.startswith("raw_00000000_0000_0000_0000")
    )


def event_key(row: pd.Series) -> tuple[str, str, str]:
    return tuple(clean_text(row.get(column)) for column in EVENT_KEY_COLUMNS)  # type: ignore[return-value]


def stable_sort(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["_match_date_sort"] = pd.to_datetime(output.get("match_date"), errors="coerce")
    sort_columns = [
        column
        for column in ["_match_date_sort", "canonical_player_name", *EVENT_KEY_COLUMNS]
        if column in output
    ]
    ascending = [False] + [True] * (len(sort_columns) - 1)
    return output.sort_values(sort_columns, ascending=ascending, kind="mergesort", na_position="last").drop(
        columns="_match_date_sort"
    )


def empty_audit() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            *EVENT_KEY_COLUMNS,
            "canonical_player_id",
            "canonical_player_name",
            "governance_status",
            "reason_codes",
        ]
    )


def empty_coverage() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "scope",
            "total_matches",
            "matches_with_scorecards",
            "matches_with_ball_by_ball",
            "scorecard_batting_innings",
            "innings_with_reliable_delivery_balls",
            "innings_without_reliable_delivery_balls",
            "scorecard_only_50_plus",
            "scorecard_only_100_plus",
            "ball_events",
        ]
    )


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def number(value: object) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(parsed) else float(parsed)


def positive_number(value: object) -> float | None:
    parsed = number(value)
    return parsed if parsed is not None and parsed > 0 else None


def bool_value(value: object) -> bool:
    return value is True or str(value).strip().casefold() in {"true", "1", "yes"}


def unique_count(frame: pd.DataFrame, column: str) -> int:
    return int(frame[column].nunique()) if column in frame else 0
