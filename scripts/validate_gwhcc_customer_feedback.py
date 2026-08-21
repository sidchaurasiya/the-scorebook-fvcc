#!/usr/bin/env python3
"""Validate GWHCC customer feedback fixes FB01-FB11."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_hall_of_fame_detail_exports import build_fastest_batting_milestones  # noqa: E402
from src.data.gwhcc_document_overrides import apply_record_overrides, merge_premiership_overrides  # noqa: E402
from src.data.gwhcc_match_policy import build_match_policy_table, selected_player_rows  # noqa: E402
from src.data.gwhcc_player_status import governed_player_active  # noqa: E402
from src.utils.player_identity import apply_player_identity_mapping, is_private_or_anonymised_player  # noqa: E402


CLUB_ID = "glen-waverley-hawks"
CLUB_ROOT = ROOT / "clubs" / CLUB_ID
PROCESSED = CLUB_ROOT / "data" / "processed"
VALIDATION = PROCESSED / "validation"
MATCH_CENTRE = ROOT / "data" / "processed" / "match_centre" / CLUB_ID / "all_available"
CHECK_OUTPUT = VALIDATION / "gwhcc_customer_feedback_validation.csv"
IDENTITY_OUTPUT = VALIDATION / "gwhcc_customer_feedback_identity_audit.csv"
KASH_OUTPUT = VALIDATION / "gwhcc_kash_javed_match_reconciliation.csv"
FASTEST_OUTPUT = VALIDATION / "gwhcc_fastest_innings_completeness_audit.csv"


def normalize_name(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


def load_identity_activity() -> tuple[pd.DataFrame, pd.DataFrame]:
    raw_parts = []
    mapped_parts = []
    for category in ["batting", "bowling", "fielding"]:
        path = PROCESSED / f"all_seasons_{category}.csv"
        frame = pd.read_csv(path, low_memory=False)
        raw_parts.append(frame)
        mapped_parts.append(apply_player_identity_mapping(frame, club_id=CLUB_ID))
    return pd.concat(raw_parts, ignore_index=True, sort=False), pd.concat(mapped_parts, ignore_index=True, sort=False)


def build_identity_audit(raw: pd.DataFrame, mapped: pd.DataFrame) -> pd.DataFrame:
    rows = []
    source = raw[["raw_player_id", "raw_player_name", "season"]].drop_duplicates().copy()
    source["name_key"] = source["raw_player_name"].map(normalize_name)
    mapped_lookup = mapped[["raw_player_id", "canonical_player_id", "canonical_player_name"]].drop_duplicates("raw_player_id")
    source = source.merge(mapped_lookup, on="raw_player_id", how="left")
    seen: set[tuple[str, ...]] = set()
    for name_key, group in source.groupby("name_key", dropna=False):
        ids = sorted(set(group["raw_player_id"].astype(str)))
        if len(ids) < 2:
            continue
        canonical_ids = sorted(set(group["canonical_player_id"].dropna().astype(str)))
        key = tuple(ids)
        seen.add(key)
        if is_private_or_anonymised_player(group.iloc[0].get("raw_player_name")):
            classification = "LEGITIMATE SAME-NAME BACKEND PLAYERS"
            action = "Retain separate backend identities and exclude from public UI."
        elif len(canonical_ids) == 1:
            classification = "CONFIRMED DUPLICATE AND FIXED"
            action = "Governed canonical merge; match IDs remain de-duplicated by source match."
        else:
            classification = "LIKELY DUPLICATE - NEEDS REVIEW"
            action = "No merge applied without further identity evidence."
        rows.append(identity_row(group, classification, action))

    for canonical_id, group in source.groupby("canonical_player_id", dropna=False):
        ids = sorted(set(group["raw_player_id"].astype(str)))
        if len(ids) < 2 or tuple(ids) in seen:
            continue
        rows.append(identity_row(group, "CONFIRMED DUPLICATE AND FIXED", "Governed canonical merge across a documented name expansion or alias."))
    return pd.DataFrame(rows).sort_values(["classification", "display_name"]).reset_index(drop=True)


def identity_row(group: pd.DataFrame, classification: str, action: str) -> dict[str, object]:
    seasons_by_id = []
    for raw_id, rows in group.groupby("raw_player_id"):
        seasons = sorted(set(rows["season"].dropna().astype(str)))
        seasons_by_id.append(f"{raw_id}: {' | '.join(seasons)}")
    season_sets = [set(rows["season"].dropna().astype(str)) for _, rows in group.groupby("raw_player_id")]
    overlap = sorted(set.intersection(*season_sets)) if len(season_sets) > 1 else []
    return {
        "display_name": group["canonical_player_name"].dropna().astype(str).iloc[0] if group["canonical_player_name"].notna().any() else group["raw_player_name"].iloc[0],
        "source_ids": " | ".join(sorted(set(group["raw_player_id"].astype(str)))),
        "seasons_by_source_id": " || ".join(seasons_by_id),
        "overlapping_seasons": " | ".join(overlap),
        "canonical_player_ids_after": " | ".join(sorted(set(group["canonical_player_id"].dropna().astype(str)))),
        "classification": classification,
        "action": action,
    }


def build_kash_reconciliation() -> pd.DataFrame:
    policy = build_match_policy_table()
    selected = selected_player_rows(policy)
    rows = selected[selected["player_id"].astype(str).eq("3944cc2f-c318-41fa-aa71-43f922fe581c")].drop_duplicates("match_id").copy()
    rows["is_t20"] = rows["detected_match_format"].eq("T20")
    rows["is_no_play"] = rows["is_no_play"].astype(bool)
    categories = [
        ("played_non_t20", (~rows["is_t20"]) & (~rows["is_no_play"])),
        ("played_t20", rows["is_t20"] & (~rows["is_no_play"])),
        ("no_play_non_t20", (~rows["is_t20"]) & rows["is_no_play"]),
        ("no_play_t20", rows["is_t20"] & rows["is_no_play"]),
    ]
    output = []
    for category, mask in categories:
        group = rows[mask]
        output.append(
            {
                "category": category,
                "raw_appearances": int(group["match_id"].nunique()),
                "weighted_matches": float(pd.to_numeric(group["match_weight"], errors="coerce").fillna(0).sum()),
                "adjustment": float(group["match_id"].nunique() - pd.to_numeric(group["match_weight"], errors="coerce").fillna(0).sum()),
                "notes": "T20=0.5; no-play=0; other played matches=1.",
            }
        )
    output.append(
        {
            "category": "total_selected_squad_source",
            "raw_appearances": int(rows["match_id"].nunique()),
            "weighted_matches": float(pd.to_numeric(rows["match_weight"], errors="coerce").fillna(0).sum()),
            "adjustment": float(rows["match_id"].nunique() - pd.to_numeric(rows["match_weight"], errors="coerce").fillna(0).sum()),
            "notes": "Authoritative arithmetic from locally retained PlayCricket match and selected-squad records.",
        }
    )
    return pd.DataFrame(output)


def club_scorecard_batting() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    batting = pd.read_csv(MATCH_CENTRE / "all_scorecard_batting.csv", low_memory=False)
    balls = pd.read_csv(MATCH_CENTRE / "all_ball_by_ball.csv", low_memory=False)
    matches = pd.read_csv(MATCH_CENTRE / "all_matches.csv", low_memory=False)
    source_ids = {
        str(row["match_id"]): {part.strip() for part in str(row.get("source_team_ids") or "").split("|") if part.strip()}
        for _, row in matches.iterrows()
    }
    batting = batting[
        batting.apply(lambda row: str(row.get("team_id")) in source_ids.get(str(row.get("match_id")), set()), axis=1)
    ].copy()
    return batting, balls, matches


def build_fastest_completeness() -> pd.DataFrame:
    pipeline = build_fastest_batting_milestones(CLUB_ID)
    batting, balls, matches = club_scorecard_batting()
    supplement_path = CLUB_ROOT / "data" / "source" / "document_overrides" / "gwhcc_fastest_innings_supplements.csv"
    supplements = pd.read_csv(supplement_path, dtype=str).fillna("") if supplement_path.exists() else pd.DataFrame()
    ball_groups = {
        tuple(map(str, key)): group.sort_values(["innings_order", "over_number", "ball_number", "ball_event_id"]).copy()
        for key, group in balls.groupby(["match_id", "innings_id", "striker_participant_id"], dropna=False)
    }
    rows = []
    batting = batting.drop_duplicates(["match_id", "innings_id", "participant_id", "bat_instance"])
    for _, scorecard in batting.iterrows():
        final_runs = pd.to_numeric(scorecard.get("runs_scored"), errors="coerce")
        if pd.isna(final_runs) or final_runs < 50:
            continue
        key = (str(scorecard.get("match_id")), str(scorecard.get("innings_id")), str(scorecard.get("participant_id")))
        group = ball_groups.get(key)
        for target in [50, 100]:
            if final_runs < target:
                continue
            expected_balls = None
            evidence = ""
            exclusion = ""
            if group is not None and not group.empty:
                derived = pd.to_numeric(group.get("runs_bat"), errors="coerce").fillna(0).cumsum()
                legal = group.get("is_legal_delivery", pd.Series(True, index=group.index)).astype(str).str.casefold().isin({"true", "1"}).cumsum()
                reached = group.index[derived.ge(target)]
                if len(reached):
                    expected_balls = int(legal.loc[reached[0]])
                    evidence = "independent_per_delivery_reconstruction"
                else:
                    exclusion = "scorecard reaches milestone but verified per-delivery batter runs do not"
            else:
                governed = supplements[
                    supplements.get("match_id", pd.Series("", index=supplements.index)).astype(str).eq(key[0])
                    & supplements.get("participant_id", pd.Series("", index=supplements.index)).astype(str).eq(key[2])
                ] if not supplements.empty else pd.DataFrame()
                column = f"balls_to_{target}"
                value = pd.to_numeric(governed.iloc[0].get(column), errors="coerce") if len(governed) == 1 else pd.NA
                if pd.notna(value):
                    expected_balls = int(value)
                    evidence = "governed_customer_scorecard_supplement"
                else:
                    exclusion = "ball-by-ball unavailable and no governed exact milestone evidence"
            represented = pipeline[
                pipeline["match_id"].astype(str).eq(key[0])
                & pipeline["innings_id"].astype(str).eq(key[1])
                & pipeline["participant_id"].astype(str).eq(key[2])
            ]
            actual_values = pd.to_numeric(represented.get(f"balls_to_{target}", pd.Series(dtype="object")), errors="coerce").dropna()
            actual = actual_values.min() if not actual_values.empty else pd.NA
            if expected_balls is None:
                status = "explicitly_excluded"
            elif pd.isna(actual):
                status = "missing"
            elif int(actual) == expected_balls:
                status = "represented"
            else:
                status = "represented_ball_count_review"
            rows.append(
                {
                    "match_id": key[0],
                    "innings_id": key[1],
                    "participant_id": key[2],
                    "player_name": scorecard.get("player_name"),
                    "final_runs": int(final_runs),
                    "final_balls": pd.to_numeric(scorecard.get("balls_faced"), errors="coerce"),
                    "milestone": target,
                    "expected_balls": expected_balls,
                    "pipeline_balls": actual,
                    "ball_count_matches_independent_legal_count": bool(pd.notna(actual) and expected_balls is not None and int(actual) == expected_balls),
                    "evidence": evidence,
                    "status": status,
                    "exclusion_reason": exclusion,
                }
            )
    return pd.DataFrame(rows)


def check(name: str, passed: bool, actual: object, expected: object, notes: str) -> dict[str, object]:
    return {"check_name": name, "validation_status": "PASS" if passed else "FAIL", "actual": actual, "expected": expected, "notes": notes}


def main() -> int:
    VALIDATION.mkdir(parents=True, exist_ok=True)
    raw, mapped = load_identity_activity()
    identity = build_identity_audit(raw, mapped)
    identity.to_csv(IDENTITY_OUTPUT, index=False)
    kash = build_kash_reconciliation()
    kash.to_csv(KASH_OUTPUT, index=False)
    fastest = build_fastest_completeness()
    fastest.to_csv(FASTEST_OUTPUT, index=False)

    all_time = pd.read_csv(PROCESSED / "hall_of_fame" / "prepared_career_all_time.csv", low_memory=False)
    authoritative = apply_record_overrides(all_time, write_decisions=False)
    checks = []
    for name in ["Greg Mccormick", "Ahilan Sivakumaran", "Reece Anderson"]:
        rows = mapped[mapped["canonical_player_name"].astype(str).str.casefold().eq(name.casefold())]
        checks.append(check(f"identity_{normalize_name(name).replace(' ', '_')}_single_canonical", rows["canonical_player_id"].nunique() == 1, rows["canonical_player_id"].nunique(), 1, "Governed non-overlapping provider IDs resolve to one canonical identity."))
    james = mapped[mapped["canonical_player_name"].astype(str).str.casefold().eq("james anderson")]
    checks.append(check("fb04_james_single_scorebook_source", james["raw_player_id"].nunique() == 1, james["raw_player_id"].nunique(), 1, "No unsupported merge was applied to ambiguous customer workbook rows."))
    century_path = CLUB_ROOT / "data/source/document_overrides/gwhcc_historical_centuries.csv"
    century_rows = pd.read_csv(century_path) if century_path.exists() else pd.DataFrame()
    checks.append(check("historical_century_supplements_exist", len(century_rows) == 65, len(century_rows), 65, "Governed customer century rows are versioned outside raw PlayCricket data."))
    for player_name, expected in {
        "Sunny Somaia": 19,
        "Glen Mahoney": 16,
        "Stuart Wynd": 15,
        "Greg Mccormick": 8,
        "Brett Powell": 6,
        "Dulaj Madushanka": 3,
    }.items():
        player = authoritative[authoritative["Player"].astype(str).str.casefold().eq(player_name.casefold())]
        actual = pd.to_numeric(player.iloc[0].get("100s"), errors="coerce") if len(player) == 1 else pd.NA
        checks.append(check(f"fb05_{normalize_name(player_name).replace(' ', '_')}_centuries", len(player) == 1 and pd.notna(actual) and int(actual) == expected, actual, expected, "Customer score list reconciled against existing scorecard and aggregate century counts."))
    ahilan = authoritative[authoritative["Player"].astype(str).str.casefold().eq("ahilan sivakumaran")]
    ahilan_ok = len(ahilan) == 1 and all(float(ahilan.iloc[0][metric]) == value for metric, value in {"Matches": 132, "Runs": 3414, "Wickets": 45}.items())
    checks.append(check("fb02_ahilan_authoritative_totals", ahilan_ok, "missing" if ahilan.empty else f"{ahilan.iloc[0]['Matches']}/{ahilan.iloc[0]['Runs']}/{ahilan.iloc[0]['Wickets']}", "132/3414/45", "Customer Career Master supplements the confirmed merged identity."))
    adrian = authoritative[authoritative["Player"].astype(str).str.casefold().eq("adrian dale")]
    checks.append(check("fb07_adrian_documented_debut", len(adrian) == 1 and str(adrian.iloc[0].get("Debut Season")) == "Summer 1980/81", adrian.iloc[0].get("Debut Season") if len(adrian) else "missing", "Summer 1980/81", "Detailed reconstructed seasons remain unchanged."))
    checks.append(check("fb08_kash_weighted_matches", abs(float(kash.iloc[-1]["weighted_matches"]) - 154.5) < 1e-9, kash.iloc[-1]["weighted_matches"], 154.5, "Existing T20/no-play policy retained."))
    base_wins = pd.read_csv(PROCESSED / "hall_of_fame" / "premiership_wins.csv")
    base_players = pd.read_csv(PROCESSED / "hall_of_fame" / "player_premierships.csv")
    combined_wins, _ = merge_premiership_overrides(base_wins, base_players)
    checks.append(check("fb06_combined_premiership_events", len(combined_wins) == 53, len(combined_wins), 53, "24 verified PlayCricket events plus 29 non-duplicated governed historical events."))
    checks.append(check("fb09_arun_inactive", not governed_player_active(True, "arun_chelvan", "Arun Chelvan"), governed_player_active(True, "arun_chelvan", "Arun Chelvan"), False, "Explicit departed-player evidence overrides recency."))
    checks.append(check("fb09_ahilan_inactive", not governed_player_active(True, "ahilan_sivakumaran", "Ahilan Sivakumaran"), governed_player_active(True, "ahilan_sivakumaran", "Ahilan Sivakumaran"), False, "Explicit departed-player evidence overrides recency."))
    checks.append(check("fb09_nathan_active", governed_player_active(False, "nathan_bungey", "Nathan Bungey"), governed_player_active(False, "nathan_bungey", "Nathan Bungey"), True, "Current GWHCC activity is explicitly confirmed."))
    arun = fastest[(fastest["match_id"] == "4c2ca82a-a39d-4904-a122-3b532617a86b") & (fastest["participant_id"] == "7ebc3350-3efe-4d6f-88f6-2b3a0a568a8d") & (fastest["milestone"] == 50)]
    checks.append(check("fb10_arun_fastest_50", len(arun) == 1 and arun.iloc[0]["status"] == "represented" and int(arun.iloc[0]["pipeline_balls"]) == 18, arun.iloc[0]["pipeline_balls"] if len(arun) else "missing", 18, "Per-delivery runs independently reach 50 on legal ball 18."))
    luke = fastest[(fastest["match_id"] == "bd66ac0a-98d6-4733-aad4-ef7dfe1e0cea") & (fastest["participant_id"] == "5e51cdc2-8d9e-4583-badc-2922f6095d48") & (fastest["milestone"] == 100)]
    checks.append(check("fb11_luke_fastest_100", len(luke) == 1 and luke.iloc[0]["status"] == "represented" and int(luke.iloc[0]["pipeline_balls"]) == 37, luke.iloc[0]["pipeline_balls"] if len(luke) else "missing", 37, "Customer-confirmed milestone is corroborated by the 102 off 37 retired-not-out scorecard."))
    missing = fastest[fastest["status"].eq("missing")]
    checks.append(check("fastest_no_unexplained_eligible_omissions", missing.empty, len(missing), 0, "Every independently reconstructible or governed milestone candidate is represented."))
    frame = pd.DataFrame(checks)
    frame.to_csv(CHECK_OUTPUT, index=False)
    passed = int(frame["validation_status"].eq("PASS").sum())
    print(f"GWHCC customer feedback validation: {passed}/{len(frame)} passed")
    print(f"Identity audit rows: {len(identity)}")
    print(f"Kash weighted matches: {kash.iloc[-1]['weighted_matches']}")
    print(f"Fastest 50 eligible: {len(fastest[(fastest.milestone == 50) & fastest.expected_balls.notna()])}; missing={len(missing[missing.milestone == 50])}")
    print(f"Fastest 100 eligible: {len(fastest[(fastest.milestone == 100) & fastest.expected_balls.notna()])}; missing={len(missing[missing.milestone == 100])}")
    return 0 if passed == len(frame) else 1


if __name__ == "__main__":
    raise SystemExit(main())
