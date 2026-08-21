#!/usr/bin/env python3
"""Build the GWHCC Hall of Fame hat-trick export and completeness audit."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.hat_tricks import detect_hat_tricks, public_hat_trick_events  # noqa: E402
from src.utils.player_identity import apply_player_identity_mapping  # noqa: E402


CLUB_ID = "glen-waverley-hawks"
MATCH_CENTRE = ROOT / "data" / "processed" / "match_centre" / CLUB_ID / "all_available"
CLUB_PROCESSED = ROOT / "clubs" / CLUB_ID / "data" / "processed"
HOF_OUTPUT = CLUB_PROCESSED / "hall_of_fame" / "hat_tricks.csv"
AUDIT_OUTPUT = CLUB_PROCESSED / "validation" / "gwhcc_hat_trick_candidate_audit.csv"
VALIDATION_OUTPUT = CLUB_PROCESSED / "validation" / "gwhcc_hat_trick_validation.csv"


def read_source(name: str) -> pd.DataFrame:
    path = MATCH_CENTRE / name
    if not path.exists():
        raise FileNotFoundError(f"Required match-centre source is missing: {path}")
    return pd.read_csv(path, low_memory=False)


def source_team_ids(value: object) -> set[str]:
    text = str(value or "").replace(";", ",").replace("|", ",")
    return {
        token.strip()
        for token in text.split(",")
        if token.strip() and token.strip().casefold() not in {"nan", "none", "nat"}
    }


def build_identity_lookup(
    bowling: pd.DataFrame,
    selected_team_ids_by_match: dict[str, set[str]],
) -> dict[str, dict[str, str]]:
    rows = bowling[
        bowling.apply(
            lambda row: str(row.get("team_id"))
            in selected_team_ids_by_match.get(str(row.get("match_id")), set()),
            axis=1,
        )
    ].copy()
    rows["raw_player_id"] = rows["participant_id"].fillna("").astype(str)
    rows["raw_player_name"] = rows["player_name"]
    mapped = apply_player_identity_mapping(rows, club_id=CLUB_ID)
    mapped = mapped.drop_duplicates("raw_player_id")
    return {
        str(row.raw_player_id): {
            "canonical_player_id": str(row.canonical_player_id),
            "canonical_player_name": str(row.canonical_player_name),
        }
        for row in mapped.itertuples()
        if str(row.raw_player_id).strip()
    }


def validation_rows(
    events: pd.DataFrame,
    audit: pd.DataFrame,
    coverage: dict[str, object],
    previous_event_ids: set[str],
    previous_candidate_ids: set[str],
) -> pd.DataFrame:
    statuses = audit.get("validation_status", pd.Series(dtype=str)).fillna("").astype(str)
    current_event_ids = set(events.get("event_id", pd.Series(dtype=str)).dropna().astype(str))
    current_candidate_ids = set(audit.get("event_id", pd.Series(dtype=str)).dropna().astype(str))
    private_candidates = audit.get("is_private_player", pd.Series(False, index=audit.index)).astype(str).str.casefold().isin({"true", "1", "yes"})
    expected_public_ids = set(audit.loc[statuses.eq("CONFIRMED") & ~private_candidates, "event_id"].astype(str))
    checks = [
        ("candidate_audit_complete", len(audit) == int(coverage["candidate_windows"]), f"rows={len(audit)}"),
        ("confirmed_events_exported", current_event_ids == expected_public_ids, f"public={len(events)} expected={len(expected_public_ids)}"),
        ("no_duplicate_candidate_events", not audit.get("event_id", pd.Series(dtype=str)).duplicated().any(), f"rows={len(audit)}"),
        ("no_duplicate_public_events", not events.get("event_id", pd.Series(dtype=str)).duplicated().any(), f"rows={len(events)}"),
        (
            "no_private_public_players",
            not events.get("canonical_player_name", pd.Series(dtype=str)).astype(str).str.contains(r"\*{2,}", regex=True).any(),
            "masked names excluded",
        ),
        (
            "previous_confirmed_events_retained",
            previous_event_ids.issubset(current_event_ids),
            f"missing={sorted(previous_event_ids - current_event_ids)}",
        ),
        (
            "private_confirmed_events_excluded",
            not bool(private_candidates[statuses.eq("CONFIRMED")].any()),
            f"private_confirmed={int(private_candidates[statuses.eq('CONFIRMED')].sum())}",
        ),
        ("ambiguous_candidates_visible", int((statuses == "AMBIGUOUS / REVIEW").sum()) == int(coverage["ambiguous"]), f"count={coverage['ambiguous']}"),
    ]
    return pd.DataFrame(
        [
            {
                "check": name,
                "status": "PASS" if passed else "FAIL",
                "detail": detail,
            }
            for name, passed, detail in checks
        ]
        + [
            {
                "check": "new_candidate_events",
                "status": "INFO",
                "detail": f"count={len(current_candidate_ids - previous_candidate_ids)} ids={sorted(current_candidate_ids - previous_candidate_ids)}",
            }
        ]
        + [
            {"check": key, "status": "INFO", "detail": str(value)}
            for key, value in coverage.items()
        ]
    )


def main() -> int:
    balls = read_source("all_ball_by_ball.csv")
    matches = read_source("all_matches.csv")
    bowling = read_source("all_scorecard_bowling.csv")
    batting = read_source("all_scorecard_batting.csv")
    selected = {
        str(row.match_id): source_team_ids(row.source_team_ids)
        for row in matches.itertuples()
    }
    identity_lookup = build_identity_lookup(bowling, selected)
    previous_event_ids: set[str] = set()
    previous_candidate_ids: set[str] = set()
    if HOF_OUTPUT.exists():
        previous = pd.read_csv(HOF_OUTPUT, dtype=str)
        previous_event_ids = set(previous.get("event_id", pd.Series(dtype=str)).dropna().astype(str))
    if AUDIT_OUTPUT.exists():
        previous_audit = pd.read_csv(AUDIT_OUTPUT, dtype=str)
        previous_candidate_ids = set(previous_audit.get("event_id", pd.Series(dtype=str)).dropna().astype(str))

    detected = detect_hat_tricks(
        balls,
        matches=matches,
        bowling_scorecard=bowling,
        batting_scorecard=batting,
        selected_team_ids_by_match=selected,
        identity_lookup=identity_lookup,
    )
    events = public_hat_trick_events(detected.events)
    validation = validation_rows(
        events,
        detected.audit,
        detected.coverage,
        previous_event_ids,
        previous_candidate_ids,
    )

    HOF_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    events.to_csv(HOF_OUTPUT, index=False)
    detected.audit.to_csv(AUDIT_OUTPUT, index=False)
    validation.to_csv(VALIDATION_OUTPUT, index=False)

    failures = validation[validation["status"].eq("FAIL")]
    print(
        "GWHCC hat-tricks: "
        f"candidates={detected.coverage['candidate_windows']} "
        f"confirmed={detected.coverage['confirmed']} "
        f"rejected={detected.coverage['rejected']} "
        f"ambiguous={detected.coverage['ambiguous']}"
    )
    print(f"- public export: {HOF_OUTPUT} ({len(events)} rows)")
    print(f"- candidate audit: {AUDIT_OUTPUT} ({len(detected.audit)} rows)")
    print(f"- validation: {VALIDATION_OUTPUT} ({len(failures)} failures)")
    return 1 if not failures.empty else 0


if __name__ == "__main__":
    raise SystemExit(main())
