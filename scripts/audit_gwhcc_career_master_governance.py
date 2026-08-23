#!/usr/bin/env python3
"""Build read-only GWHCC Career Master identity and total-governance audits."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_document_overrides import apply_record_overrides  # noqa: E402


CLUB_ID = "glen-waverley-hawks"
CLUB_ROOT = ROOT / "clubs" / CLUB_ID
DATA = CLUB_ROOT / "data"
SOURCE = DATA / "source" / "document_overrides"
PROCESSED = DATA / "processed"
HOF = PROCESSED / "hall_of_fame"
VALIDATION = PROCESSED / "validation"
IDENTITY_OUTPUT = VALIDATION / "gwhcc_career_master_identity_audit.csv"
TOTAL_OUTPUT = VALIDATION / "gwhcc_career_total_reconciliation_audit.csv"
IMPACT_OUTPUT = VALIDATION / "gwhcc_career_master_simulated_impact.csv"

IDENTITY_COLUMNS = [
    "source_row",
    "source_name",
    "canonical_player_id",
    "canonical_player_name",
    "identity_status",
    "identity_confidence",
    "evidence",
    "earliest_source_season",
    "latest_source_season",
    "current_scorebook_seasons",
    "historical_only",
    "previous_identity_review",
    "review_reduction_category",
    "duplicate_source_name",
    "candidate_count",
    "candidate_names",
    "source_quality_flag",
    "higher_total_case",
    "higher_total_category",
    "notes",
]

TOTAL_COLUMNS = [
    "canonical_player_id",
    "player_name",
    "source_rows",
    "source_names",
    "career_master_matches",
    "scorebook_matches",
    "match_difference",
    "career_master_runs",
    "scorebook_runs",
    "run_difference",
    "career_master_wickets",
    "scorebook_wickets",
    "wicket_difference",
    "career_master_catches",
    "scorebook_catches",
    "catch_difference",
    "career_master_not_outs",
    "scorebook_not_outs",
    "not_out_difference",
    "career_master_batting_average",
    "recalculated_career_master_batting_average",
    "scorebook_batting_average",
    "batting_average_quality_flag",
    "career_master_bowling_average",
    "recalculated_career_master_bowling_average",
    "scorebook_bowling_average",
    "bowling_average_quality_flag",
    "earliest_historical_season",
    "earliest_playcricket_detail_season",
    "identity_status",
    "recommended_authority",
    "matches_authority",
    "runs_authority",
    "wickets_authority",
    "catches_authority",
    "not_outs_authority",
    "confidence",
    "reason",
    "overlap_risk",
    "customer_confirmation_required",
    "existing_override_metrics",
    "proposed_matches",
    "proposed_runs",
    "proposed_wickets",
    "proposed_catches",
    "proposed_not_outs",
    "source_metric_values",
    "source_workbook",
    "source_sheet",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    return parser.parse_args()


def clean(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", clean(value).casefold())).strip()


def compact(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean(value).casefold())


def initial_surname_key(value: object) -> str:
    text = re.sub(r"\([^)]*\)", " ", clean(value))
    initial_first = re.match(r"^([A-Za-z](?:\s*\.\s*[A-Za-z])*)\s*\.\s*([A-Za-z'-]+)", text)
    if initial_first:
        initials = compact(initial_first.group(1))
        return f"{initials} {compact(initial_first.group(2))}" if initials else ""
    surname_first = re.match(r"^([A-Za-z'-]+)\s*\.\s*([A-Za-z](?:\s*\.\s*[A-Za-z])*)", text)
    if surname_first:
        initials = compact(surname_first.group(2))
        return f"{initials} {compact(surname_first.group(1))}" if initials else ""
    return ""


def numeric(value: object) -> float | None:
    parsed = pd.to_numeric(value, errors="coerce")
    return None if pd.isna(parsed) else float(parsed)


def difference(left: object, right: object) -> float | None:
    left_number = numeric(left)
    right_number = numeric(right)
    return None if left_number is None or right_number is None else left_number - right_number


def equivalent(left: object, right: object, tolerance: float = 0.01) -> bool:
    delta = difference(left, right)
    return delta is not None and abs(delta) <= tolerance


def season_year(value: object) -> int | None:
    match = re.search(r"(\d{4})/(\d{2})", clean(value))
    return int(match.group(1)) if match else None


def source_name_parts(value: object) -> tuple[str, str, str, str]:
    original = clean(value)
    qualifiers = {"jr", "jnr", "junior", "snr", "senior"}
    parenthetical_words = [
        word
        for group in re.findall(r"\(([^)]*)\)", original)
        for word in re.findall(r"[A-Za-z]+", group)
        if word.casefold() not in qualifiers
    ]
    text = re.sub(r"\([^)]*\)", " ", original)
    if "." in text:
        surname_text, given_text = text.split(".", 1)
    else:
        words = re.findall(r"[A-Za-z]+", text)
        if len(words) < 2:
            return compact(text), "", "", compact(text)
        first_token = re.match(r"\s*([A-Za-z]+)", text)
        surname_first = bool(first_token and first_token.group(1).isupper() and len(first_token.group(1)) > 1)
        surname_text, given_text = (words[0], " ".join(words[1:])) if surname_first else (words[-1], " ".join(words[:-1]))
    surname = compact(surname_text)
    given_words = re.findall(r"[A-Za-z]+", given_text)
    if given_words and all(len(word) == 1 for word in given_words) and any(len(word) > 1 for word in parenthetical_words):
        given_words = parenthetical_words
    given = compact(" ".join(given_words))
    initials = "".join(word[0].casefold() for word in given_words if word)
    full_compact = compact(given + surname)
    return surname, given, initials, full_compact


def current_name_parts(value: object) -> tuple[set[str], str, str]:
    words = re.findall(r"[A-Za-z]+", clean(value))
    if len(words) < 2:
        return {compact(value)}, "", compact(value)
    given_words = words[:-1]
    surnames = {compact(words[-1]), compact(" ".join(words[-2:])), compact(" ".join(words[1:]))}
    initials = "".join(word[0].casefold() for word in given_words)
    return {value for value in surnames if value}, initials, compact(" ".join(words))


def recalculate_average(numerator: object, denominator: object, deduction: object = 0) -> float | None:
    top = numeric(numerator)
    base = numeric(denominator)
    less = numeric(deduction) or 0.0
    divisor = None if base is None else base - less
    return None if top is None or divisor is None or divisor <= 0 else top / divisor


def quality_flag(source_value: object, recalculated: object, workbook_flag: object) -> str:
    flag = clean(workbook_flag).upper()
    if flag in {"REVIEW", "SOURCE ERROR"}:
        return flag
    source_number = numeric(source_value)
    recalculated_number = numeric(recalculated)
    if source_number is None or recalculated_number is None:
        return "NOT_AVAILABLE"
    return "PASS" if abs(source_number - recalculated_number) <= 0.02 else "REVIEW"


def load_current_sources() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    base = pd.read_csv(HOF / "prepared_career_all_time.csv", low_memory=False)
    authoritative = apply_record_overrides(base.copy(), write_decisions=False)
    batting = pd.read_csv(HOF / "prepared_career_batting.csv", low_memory=False)
    not_outs = batting[["canonical_player_id", "battingNotOuts"]].copy()
    not_outs["battingNotOuts"] = pd.to_numeric(not_outs["battingNotOuts"], errors="coerce")
    authoritative = authoritative.merge(not_outs, on="canonical_player_id", how="left")
    return base, authoritative, batting


def current_registry(base: pd.DataFrame) -> list[dict[str, object]]:
    rows = []
    for row in base.to_dict("records"):
        name = clean(row.get("Player"))
        surnames, initials, full_compact = current_name_parts(name)
        rows.append(
            {
                "canonical_player_id": clean(row.get("canonical_player_id")),
                "canonical_player_name": name,
                "full_compact": full_compact,
                "surnames": surnames,
                "initials": initials,
                "matches": numeric(row.get("Matches")),
                "runs": numeric(row.get("Runs")),
                "wickets": numeric(row.get("Wickets")),
                "debut": clean(row.get("Debut Season")),
                "latest": clean(row.get("Latest Season")),
            }
        )
    return rows


def first_xi_evidence(workbook: Path) -> tuple[dict[str, str], dict[str, str], dict[str, dict[str, str]]]:
    first_xi = pd.read_excel(workbook, sheet_name="First XI History", header=2, dtype=object)
    metadata = pd.read_csv(SOURCE / "gwhcc_historical_career_metadata.csv", dtype=str).fillna("")
    metadata_by_row = {int(row.source_row): row for row in metadata.itertuples(index=False)}
    confirmed: dict[str, str] = {}
    source_seasons: dict[str, str] = {}
    source_details: dict[str, dict[str, str]] = {}
    for index, row in first_xi.iterrows():
        workbook_row = index + 4
        name = clean(row.get("Source Name"))
        key = normalize(name)
        match = re.search(r"(\d{4}/\d{2})", clean(row.get("First Game")))
        season = f"Summer {match.group(1)}" if match else ""
        if key and season and (key not in source_seasons or (season_year(season) or 9999) < (season_year(source_seasons[key]) or 9999)):
            source_seasons[key] = season
            source_details[key] = {"source_row": str(workbook_row), "first_game": clean(row.get("First Game"))}
        if workbook_row in metadata_by_row:
            confirmed[key] = clean(metadata_by_row[workbook_row].canonical_player_id)
    return confirmed, source_seasons, source_details


def document_aliases(registry: list[dict[str, object]]) -> dict[str, str]:
    aliases = pd.read_csv(SOURCE / "gwhcc_document_player_aliases.csv", dtype=str).fillna("")
    by_name = {normalize(row["canonical_player_name"]): row["canonical_player_id"] for row in registry}
    result: dict[str, str] = {}
    for row in aliases.to_dict("records"):
        if clean(row.get("confidence")).casefold() not in {"confirmed", "approved", "high"}:
            continue
        target = by_name.get(normalize(row.get("playcricket_player_name")))
        if target:
            result[normalize(row.get("document_player_name"))] = target
            initial_key = initial_surname_key(row.get("document_player_name"))
            if initial_key:
                result[f"initial:{initial_key}"] = target
    return result


def candidate_rows(source_row: pd.Series, registry: list[dict[str, object]]) -> tuple[list[dict[str, object]], str]:
    surname, given, initials, full_compact = source_name_parts(source_row.get("Source Name"))
    exact = [row for row in registry if full_compact and row["full_compact"] == full_compact]
    if exact:
        return exact, "exact normalized full name"
    source_text = re.sub(r"\([^)]*\)", " ", clean(source_row.get("Source Name")))
    given_text = source_text.split(".", 1)[1] if "." in source_text else source_text
    parenthetical = " ".join(re.findall(r"\(([^)]*)\)", clean(source_row.get("Source Name"))))
    source_has_full_given = any(len(word) > 1 for word in re.findall(r"[A-Za-z]+", f"{given_text} {parenthetical}"))
    if source_has_full_given:
        return [], "full given name has no exact canonical match"
    candidates = []
    for row in registry:
        if surname not in row["surnames"]:
            continue
        current_initials = str(row["initials"])
        if initials and current_initials.startswith(initials):
            candidates.append(row)
        elif given and compact(row["canonical_player_name"]).startswith(given):
            candidates.append(row)
    return candidates, "surname and given-name/initial evidence"


def fingerprint_matches(source_row: pd.Series, candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    source_values = [source_row.get("Career Games"), source_row.get("Career Runs"), source_row.get("Career Wickets")]
    matched = []
    for candidate in candidates:
        current_values = [candidate.get("matches"), candidate.get("runs"), candidate.get("wickets")]
        exact_count = sum(equivalent(left, right) for left, right in zip(source_values, current_values))
        if exact_count >= 2:
            matched.append(candidate)
    return matched


def build_identity_audit(
    career: pd.DataFrame,
    registry: list[dict[str, object]],
    aliases: dict[str, str],
    first_xi_confirmed: dict[str, str],
    first_xi_seasons: dict[str, str],
    previous_review_rows: set[int],
    higher_rows: set[int],
) -> pd.DataFrame:
    by_id = {str(row["canonical_player_id"]): row for row in registry}
    duplicate_names = set(career[career.duplicated("Source Name", keep=False)]["Source Name"].map(normalize))
    audit_rows = []
    for _, source in career.iterrows():
        source_row = int(source["Source Row"])
        source_name = clean(source["Source Name"])
        source_key = normalize(source_name)
        candidates, candidate_evidence = candidate_rows(source, registry)
        status = "UNRESOLVED"
        confidence = "low"
        resolved: dict[str, object] | None = None
        evidence = []
        historical_only = False
        malformed = not bool(re.search(r"[A-Za-z]", source_name))

        alias_target = aliases.get(source_key)
        if not alias_target and "(" not in source_name:
            alias_target = aliases.get(f"initial:{initial_surname_key(source_name)}")
        if alias_target and alias_target in by_id:
            resolved = by_id[alias_target]
            status, confidence = "CONFIRMED", "confirmed"
            evidence.append("confirmed document alias")
        elif source_key in first_xi_confirmed and first_xi_confirmed[source_key] in by_id:
            resolved = by_id[first_xi_confirmed[source_key]]
            status, confidence = "CONFIRMED", "high"
            evidence.append("governed First XI identity and career-start record")
        elif source_key == normalize("McCORMICK.G"):
            resolved = next((row for row in registry if row["canonical_player_id"] == "greg_mccormick"), None)
            status, confidence = "CONFIRMED", "confirmed"
            evidence.append("closed Greg McCormick customer decision")
        elif source_key == normalize("JAVED.K"):
            resolved = next(
                (row for row in registry if normalize(row["canonical_player_name"]) in {normalize("Kash Javed"), normalize("Kashif Javed")}),
                None,
            )
            status, confidence = "CONFIRMED", "confirmed"
            evidence.append("closed Kash Javed scope decision")
        elif len(candidates) == 1:
            resolved = candidates[0]
            _, given, initials, full_compact = source_name_parts(source_name)
            if full_compact == resolved["full_compact"] and len(given) > 1:
                status, confidence = "CONFIRMED", "high"
            elif len(initials) > 1:
                status, confidence = "HIGH_CONFIDENCE", "high"
            else:
                fingerprints = fingerprint_matches(source, candidates)
                status, confidence = ("HIGH_CONFIDENCE", "high") if len(fingerprints) == 1 else ("REVIEW", "medium")
                if fingerprints:
                    evidence.append("two or more core totals match the unique candidate")
            evidence.append(candidate_evidence)
        elif len(candidates) > 1:
            fingerprints = fingerprint_matches(source, candidates)
            if len(fingerprints) == 1:
                resolved = fingerprints[0]
                status, confidence = "HIGH_CONFIDENCE", "high"
                evidence.extend([candidate_evidence, "unique two-metric fingerprint among same-name candidates"])
            else:
                status, confidence = "CONFLICT", "low"
                evidence.append("multiple plausible canonical players")
        elif source_key in first_xi_seasons and (season_year(first_xi_seasons[source_key]) or 9999) < 1995:
            historical_only = True
            status, confidence = "UNRESOLVED", "high"
            evidence.append("First XI history confirms a pre-digital GWHCC player but no canonical PlayCricket identity exists")
        else:
            evidence.append("no evidence-backed canonical match")

        if source_key in duplicate_names and source_key not in {normalize("ANDERSON. J"), normalize("ANDERSON.J.C")}:
            status, confidence = "CONFLICT", "low"
            historical_only = False
            evidence.append("duplicate Career Master source name")
            if resolved is not None:
                resolved = None

        bat_recalc = recalculate_average(source.get("Career Runs"), source.get("Career Innings"), source.get("Career Not Outs"))
        bowl_recalc = recalculate_average(source.get("Career Bowl Runs"), source.get("Career Wickets"))
        bat_flag = quality_flag(source.get("Source Bat Avg"), bat_recalc, source.get("Bat Avg Check"))
        bowl_flag = quality_flag(source.get("Source Bowl Avg"), bowl_recalc, source.get("Bowl Avg Check"))
        quality = "PASS" if bat_flag in {"PASS", "NOT_AVAILABLE"} and bowl_flag in {"PASS", "NOT_AVAILABLE"} else "REVIEW"
        if source_key == normalize("MEDINA.A"):
            quality = "REVIEW"
            evidence.append("source conflict: curated Leading Players assigns the 300-wicket record to T. Medina")
        current_seasons = ""
        if resolved:
            current_seasons = " – ".join(value for value in [clean(resolved.get("debut")), clean(resolved.get("latest"))] if value)

        previous_review = source_row in previous_review_rows
        if previous_review:
            if status in {"CONFIRMED", "HIGH_CONFIDENCE"}:
                reduction = "safely_resolvable"
            elif malformed or source_key in duplicate_names:
                reduction = "malformed_or_duplicate"
            elif historical_only:
                reduction = "historical_only"
            elif status == "REVIEW":
                reduction = "likely_match_insufficient_evidence"
            else:
                reduction = "genuinely_ambiguous"
        else:
            reduction = "not_in_starting_review_set"

        audit_rows.append(
            {
                "source_row": source_row,
                "source_name": source_name,
                "canonical_player_id": clean(resolved.get("canonical_player_id")) if resolved else "",
                "canonical_player_name": clean(resolved.get("canonical_player_name")) if resolved else "",
                "identity_status": status,
                "identity_confidence": confidence,
                "evidence": "; ".join(evidence),
                "earliest_source_season": first_xi_seasons.get(source_key, ""),
                "latest_source_season": "Not supplied; Career Master is a full-career aggregate through 2025/26",
                "current_scorebook_seasons": current_seasons,
                "historical_only": str(historical_only).lower(),
                "previous_identity_review": str(previous_review).lower(),
                "review_reduction_category": reduction,
                "duplicate_source_name": str(source_key in duplicate_names).lower(),
                "candidate_count": len(candidates),
                "candidate_names": "; ".join(sorted({clean(row["canonical_player_name"]) for row in candidates})),
                "source_quality_flag": quality,
                "higher_total_case": str(source_row in higher_rows).lower(),
                "higher_total_category": "",
                "notes": f"Batting average check={bat_flag}; bowling average check={bowl_flag}.",
            }
        )
    return pd.DataFrame(audit_rows, columns=IDENTITY_COLUMNS)


def aggregate_current_not_outs(authoritative: pd.DataFrame, canonical_id: str) -> float | None:
    matched = authoritative[authoritative["canonical_player_id"].astype(str).eq(canonical_id)]
    return numeric(matched.iloc[0].get("battingNotOuts")) if len(matched) == 1 else None


def current_row(authoritative: pd.DataFrame, canonical_id: str) -> pd.Series | None:
    matched = authoritative[authoritative["canonical_player_id"].astype(str).eq(canonical_id)]
    return matched.iloc[0] if len(matched) == 1 else None


def override_metrics(row: pd.Series | None) -> list[str]:
    if row is None:
        return []
    result = []
    for metric in ["matches", "runs", "wickets"]:
        if str(row.get(f"{metric}_override_applied", "")).strip().casefold() in {"true", "1", "yes"}:
            result.append(metric)
    return result


def metric_authority(
    metric: str,
    source_value: object,
    scorebook_value: object,
    *,
    existing_override: bool,
    replacement_eligible: bool,
    quality_ok: bool,
    explicit_playcricket: bool,
) -> str:
    if metric == "catches":
        return "PLAYCRICKET"
    if explicit_playcricket:
        return "PLAYCRICKET"
    if existing_override:
        return "EXISTING_GOVERNED_OVERRIDE"
    if equivalent(source_value, scorebook_value):
        return "EQUIVALENT"
    if metric == "matches":
        return "REVIEW_REQUIRED"
    source_number = numeric(source_value)
    scorebook_number = numeric(scorebook_value)
    if replacement_eligible and quality_ok and source_number is not None and scorebook_number is not None and source_number >= scorebook_number:
        return "CAREER_MASTER_REPLACEMENT"
    if source_number is not None and scorebook_number is not None and source_number < scorebook_number:
        return "PLAYCRICKET"
    return "REVIEW_REQUIRED"


def build_total_audit(
    career: pd.DataFrame,
    identity: pd.DataFrame,
    base: pd.DataFrame,
    authoritative: pd.DataFrame,
    workbook_name: str,
) -> pd.DataFrame:
    source_by_row = career.set_index("Source Row")
    metadata = pd.read_csv(SOURCE / "gwhcc_historical_career_metadata.csv", dtype=str).fillna("")
    history_by_id = metadata.drop_duplicates("canonical_player_id").set_index("canonical_player_id")["earliest_documented_season"].to_dict()
    groups: list[tuple[str, pd.DataFrame]] = []
    resolved = identity[identity["canonical_player_id"].ne("")]
    for canonical_id, group in resolved.groupby("canonical_player_id", sort=True):
        groups.append((f"canonical:{canonical_id}", group))
    unresolved = identity[identity["canonical_player_id"].eq("")].copy()
    unresolved["_source_key"] = unresolved["source_name"].map(normalize)
    for source_key, group in unresolved.groupby("_source_key", sort=True):
        groups.append((f"source:{source_key}", group))

    output = []
    for group_key, identity_group in groups:
        source_rows = sorted(identity_group["source_row"].astype(int).tolist())
        source_records = career[career["Source Row"].isin(source_rows)].copy()
        canonical_id = clean(identity_group.iloc[0].get("canonical_player_id"))
        canonical_name = clean(identity_group.iloc[0].get("canonical_player_name"))
        statuses = set(identity_group["identity_status"].astype(str))
        identity_status = "CONFLICT" if "CONFLICT" in statuses or len(statuses) > 1 else next(iter(statuses), "UNRESOLVED")
        current = current_row(authoritative, canonical_id) if canonical_id else None
        base_current = current_row(base, canonical_id) if canonical_id else None
        multiple_sources = len(source_records) > 1
        explicit_james = canonical_name.casefold() == "james anderson"
        explicit_greg = canonical_name.casefold() == "greg mccormick"
        explicit_kash = canonical_name.casefold() in {"kash javed", "kashif javed"} or any(
            normalize(value) == normalize("JAVED.K") for value in source_records["Source Name"]
        )
        explicit_playcricket = explicit_james or explicit_greg or explicit_kash
        existing = override_metrics(current)

        source = source_records.iloc[0] if len(source_records) == 1 else pd.Series(dtype="object")
        known_source_conflict = not source.empty and normalize(source.get("Source Name")) == normalize("MEDINA.A")
        cm_matches = numeric(source.get("Career Games")) if not source.empty else None
        cm_runs = numeric(source.get("Career Runs")) if not source.empty else None
        cm_wickets = numeric(source.get("Career Wickets")) if not source.empty else None
        cm_not_outs = numeric(source.get("Career Not Outs")) if not source.empty else None
        cm_bat_avg = numeric(source.get("Source Bat Avg")) if not source.empty else None
        cm_bowl_avg = numeric(source.get("Source Bowl Avg")) if not source.empty else None
        recalc_bat = recalculate_average(source.get("Career Runs"), source.get("Career Innings"), source.get("Career Not Outs")) if not source.empty else None
        recalc_bowl = recalculate_average(source.get("Career Bowl Runs"), source.get("Career Wickets")) if not source.empty else None
        bat_quality = quality_flag(source.get("Source Bat Avg"), recalc_bat, source.get("Bat Avg Check")) if not source.empty else "MULTIPLE_SOURCE_ROWS"
        bowl_quality = quality_flag(source.get("Source Bowl Avg"), recalc_bowl, source.get("Bowl Avg Check")) if not source.empty else "MULTIPLE_SOURCE_ROWS"

        sb_matches = numeric(current.get("Matches")) if current is not None else None
        sb_runs = numeric(current.get("Runs")) if current is not None else None
        sb_wickets = numeric(current.get("Wickets")) if current is not None else None
        sb_catches = numeric(current.get("Catches")) if current is not None else None
        sb_not_outs = aggregate_current_not_outs(authoritative, canonical_id) if canonical_id else None
        sb_bat_avg = numeric(current.get("Bat Avg")) if current is not None else None
        sb_bowl_avg = numeric(current.get("Bowl Avg")) if current is not None else None
        earliest_history = history_by_id.get(canonical_id, "")
        pc_detail = clean(base_current.get("Debut Season")) if base_current is not None else ""
        history_gap = (
            season_year(earliest_history) is not None
            and season_year(pc_detail) is not None
            and season_year(earliest_history) < season_year(pc_detail)
        )
        identity_safe = identity_status in {"CONFIRMED", "HIGH_CONFIDENCE"}
        source_clean = (
            bat_quality in {"PASS", "NOT_AVAILABLE"}
            and bowl_quality in {"PASS", "NOT_AVAILABLE"}
            and not known_source_conflict
        )
        replacement_eligible = identity_safe and history_gap and source_clean and not multiple_sources and not explicit_playcricket

        if not canonical_id:
            overall = "IDENTITY_UNRESOLVED"
            matches_authority = runs_authority = wickets_authority = not_outs_authority = "IDENTITY_UNRESOLVED"
            catches_authority = "PLAYCRICKET"
            confidence = "low"
            reason = "No approved canonical GWHCC identity exists; totals cannot be governed."
        elif multiple_sources and not explicit_james:
            overall = "REVIEW_REQUIRED"
            matches_authority = runs_authority = wickets_authority = not_outs_authority = "REVIEW_REQUIRED"
            catches_authority = "PLAYCRICKET"
            confidence = "low"
            reason = "Multiple Career Master rows map to one canonical player and cannot be combined without source review."
        else:
            matches_authority = metric_authority(
                "matches", cm_matches, sb_matches, existing_override="matches" in existing,
                replacement_eligible=replacement_eligible, quality_ok=source_clean, explicit_playcricket=explicit_playcricket,
            )
            runs_authority = metric_authority(
                "runs", cm_runs, sb_runs, existing_override="runs" in existing,
                replacement_eligible=replacement_eligible, quality_ok=bat_quality in {"PASS", "NOT_AVAILABLE"}, explicit_playcricket=explicit_playcricket,
            )
            wickets_authority = metric_authority(
                "wickets", cm_wickets, sb_wickets, existing_override="wickets" in existing,
                replacement_eligible=replacement_eligible, quality_ok=bowl_quality in {"PASS", "NOT_AVAILABLE"}, explicit_playcricket=explicit_playcricket,
            )
            catches_authority = "PLAYCRICKET"
            not_outs_authority = metric_authority(
                "not_outs", cm_not_outs, sb_not_outs, existing_override=False,
                replacement_eligible=replacement_eligible, quality_ok=bat_quality in {"PASS", "NOT_AVAILABLE"}, explicit_playcricket=explicit_playcricket,
            )
            authorities = {matches_authority, runs_authority, wickets_authority, not_outs_authority}
            if explicit_playcricket:
                overall, confidence = "PLAYCRICKET", "confirmed"
                reason = "Closed customer decision or GWHCC-only scope decision retains current Scorebook totals."
            elif existing:
                overall, confidence = "EXISTING_GOVERNED_OVERRIDE", "high"
                reason = f"Current app already applies governed override metrics: {', '.join(existing)}."
            elif "CAREER_MASTER_REPLACEMENT" in authorities:
                overall, confidence = "CAREER_MASTER_REPLACEMENT", "high"
                reason = "Confirmed identity, verified earlier GWHCC career, clean source arithmetic, and no duplicate source row support metric-level full-career replacement."
            elif authorities.issubset({"EQUIVALENT", "PLAYCRICKET"}) and "EQUIVALENT" in authorities:
                overall, confidence = "EQUIVALENT", "high"
                reason = "Available Career Master totals reconcile or are lower than current verified Scorebook values."
            elif known_source_conflict:
                overall, confidence = "REVIEW_REQUIRED", "low"
                reason = "Career Master MEDINA.A conflicts with the curated T. Medina 300-wicket record and requires customer/source confirmation."
            elif not source_clean:
                overall, confidence = "PLAYCRICKET", "high"
                reason = "Career Master arithmetic/source quality flag prevents replacement authority."
            else:
                overall, confidence = "REVIEW_REQUIRED", "medium"
                reason = "Full-career overlap or match-counting basis is not sufficiently proven."

        proposed = {
            "matches": cm_matches if matches_authority == "CAREER_MASTER_REPLACEMENT" else sb_matches,
            "runs": cm_runs if runs_authority == "CAREER_MASTER_REPLACEMENT" else sb_runs,
            "wickets": cm_wickets if wickets_authority == "CAREER_MASTER_REPLACEMENT" else sb_wickets,
            "catches": sb_catches,
            "not_outs": cm_not_outs if not_outs_authority == "CAREER_MASTER_REPLACEMENT" else sb_not_outs,
        }
        source_values = [
            {
                "source_row": int(row["Source Row"]),
                "source_name": clean(row["Source Name"]),
                "matches": numeric(row.get("Career Games")),
                "runs": numeric(row.get("Career Runs")),
                "wickets": numeric(row.get("Career Wickets")),
                "not_outs": numeric(row.get("Career Not Outs")),
            }
            for _, row in source_records.iterrows()
        ]
        overlap_risk = (
            f"Known career-start gap ({earliest_history} before {pc_detail}); Career Master remains a full-career aggregate."
            if history_gap
            else "Unknown full-career overlap; no additive use is permitted."
        )
        output.append(
            {
                "canonical_player_id": canonical_id,
                "player_name": canonical_name or "; ".join(identity_group["source_name"].astype(str)),
                "source_rows": ";".join(str(value) for value in source_rows),
                "source_names": "; ".join(source_records["Source Name"].map(clean)),
                "career_master_matches": cm_matches,
                "scorebook_matches": sb_matches,
                "match_difference": difference(cm_matches, sb_matches),
                "career_master_runs": cm_runs,
                "scorebook_runs": sb_runs,
                "run_difference": difference(cm_runs, sb_runs),
                "career_master_wickets": cm_wickets,
                "scorebook_wickets": sb_wickets,
                "wicket_difference": difference(cm_wickets, sb_wickets),
                "career_master_catches": None,
                "scorebook_catches": sb_catches,
                "catch_difference": None,
                "career_master_not_outs": cm_not_outs,
                "scorebook_not_outs": sb_not_outs,
                "not_out_difference": difference(cm_not_outs, sb_not_outs),
                "career_master_batting_average": cm_bat_avg,
                "recalculated_career_master_batting_average": recalc_bat,
                "scorebook_batting_average": sb_bat_avg,
                "batting_average_quality_flag": bat_quality,
                "career_master_bowling_average": cm_bowl_avg,
                "recalculated_career_master_bowling_average": recalc_bowl,
                "scorebook_bowling_average": sb_bowl_avg,
                "bowling_average_quality_flag": bowl_quality,
                "earliest_historical_season": earliest_history,
                "earliest_playcricket_detail_season": pc_detail,
                "identity_status": identity_status,
                "recommended_authority": overall,
                "matches_authority": matches_authority,
                "runs_authority": runs_authority,
                "wickets_authority": wickets_authority,
                "catches_authority": catches_authority,
                "not_outs_authority": not_outs_authority,
                "confidence": confidence,
                "reason": reason,
                "overlap_risk": overlap_risk,
                "customer_confirmation_required": str(overall in {"REVIEW_REQUIRED", "IDENTITY_UNRESOLVED"}).lower(),
                "existing_override_metrics": ";".join(existing),
                "proposed_matches": proposed["matches"],
                "proposed_runs": proposed["runs"],
                "proposed_wickets": proposed["wickets"],
                "proposed_catches": proposed["catches"],
                "proposed_not_outs": proposed["not_outs"],
                "source_metric_values": json.dumps(source_values, sort_keys=True),
                "source_workbook": workbook_name,
                "source_sheet": "Career Master",
            }
        )
    return pd.DataFrame(output, columns=TOTAL_COLUMNS)


def classify_higher_total_cases(identity: pd.DataFrame, totals: pd.DataFrame, career: pd.DataFrame) -> pd.DataFrame:
    result = identity.copy()
    totals_by_id = totals[totals["canonical_player_id"].ne("")].drop_duplicates("canonical_player_id").set_index("canonical_player_id")
    authority_by_id = totals_by_id["recommended_authority"].to_dict()
    career_by_row = career.set_index("Source Row")
    categories = []
    for row in result.itertuples(index=False):
        if str(row.higher_total_case).casefold() != "true":
            categories.append("")
            continue
        source = career_by_row.loc[int(row.source_row)]
        authority = authority_by_id.get(str(row.canonical_player_id), "")
        total = totals_by_id.loc[str(row.canonical_player_id)] if str(row.canonical_player_id) in totals_by_id.index else None
        if row.identity_status in {"UNRESOLVED", "CONFLICT", "REVIEW"} or str(row.duplicate_source_name).casefold() == "true":
            category = "E_DUPLICATE_OR_IDENTITY_RISK"
        elif authority == "CAREER_MASTER_REPLACEMENT":
            category = "A_HIGH_CONFIDENCE_REPLACEMENT_CANDIDATE"
        elif authority in {"PLAYCRICKET", "EXISTING_GOVERNED_OVERRIDE", "EQUIVALENT"}:
            category = "F_NO_ACTION"
        elif row.source_quality_flag != "PASS":
            category = "D_SOURCE_CONFLICT"
        elif total is not None and (difference(total.career_master_matches, total.scorebook_matches) or 0) > 0 and all(
            delta is None or abs(delta) <= 0.01
            for delta in [
                difference(total.career_master_runs, total.scorebook_runs),
                difference(total.career_master_wickets, total.scorebook_wickets),
            ]
        ):
            category = "C_MATCH_COUNTING_POLICY_DIFFERENCE"
        else:
            category = "B_LIKELY_HISTORICAL_GAP_NEEDS_REVIEW"
        categories.append(category)
    result["higher_total_category"] = categories
    return result


def build_impact_audit(authoritative: pd.DataFrame, totals: pd.DataFrame) -> pd.DataFrame:
    candidates = totals[totals["recommended_authority"].eq("CAREER_MASTER_REPLACEMENT")].copy()
    simulated = authoritative.copy()
    impact_rows = []
    for row in candidates.itertuples(index=False):
        matched = simulated["canonical_player_id"].astype(str).eq(str(row.canonical_player_id))
        if matched.sum() != 1:
            continue
        for metric, proposed in [("Runs", row.proposed_runs), ("Wickets", row.proposed_wickets), ("Matches", row.proposed_matches)]:
            current = numeric(simulated.loc[matched, metric].iloc[0])
            proposed_number = numeric(proposed)
            if proposed_number is not None and current is not None and not equivalent(current, proposed_number):
                simulated.loc[matched, metric] = proposed_number
                impact_rows.append(
                    {
                        "impact_type": "Player Profile",
                        "metric": metric,
                        "player": row.player_name,
                        "current_value": current,
                        "proposed_value": proposed_number,
                        "current_rank": None,
                        "proposed_rank": None,
                        "current_band": "",
                        "proposed_band": "",
                        "notes": "Simulation only; no production value changed.",
                    }
                )
        current_no = numeric(row.scorebook_not_outs)
        proposed_no = numeric(row.proposed_not_outs)
        if current_no is not None and proposed_no is not None and not equivalent(current_no, proposed_no):
            impact_rows.append(
                {
                    "impact_type": "Player Profile",
                    "metric": "Not Outs",
                    "player": row.player_name,
                    "current_value": current_no,
                    "proposed_value": proposed_no,
                    "current_rank": None,
                    "proposed_rank": None,
                    "current_band": "",
                    "proposed_band": "",
                    "notes": "Simulation only; current profile not-outs remain unchanged.",
                }
            )

    for metric in ["Matches", "Runs", "Wickets", "Catches"]:
        current_rank = authoritative[["canonical_player_id", "Player", metric]].copy()
        proposed_rank = simulated[["canonical_player_id", "Player", metric]].copy()
        current_rank[metric] = pd.to_numeric(current_rank[metric], errors="coerce").fillna(0)
        proposed_rank[metric] = pd.to_numeric(proposed_rank[metric], errors="coerce").fillna(0)
        current_rank = current_rank.sort_values([metric, "Player"], ascending=[False, True]).reset_index(drop=True)
        proposed_rank = proposed_rank.sort_values([metric, "Player"], ascending=[False, True]).reset_index(drop=True)
        current_positions = {row.canonical_player_id: index + 1 for index, row in current_rank.iterrows()}
        proposed_positions = {row.canonical_player_id: index + 1 for index, row in proposed_rank.iterrows()}
        for player_id in set(current_positions) | set(proposed_positions):
            before = current_positions.get(player_id)
            after = proposed_positions.get(player_id)
            if before == after or (before or 9999) > 10 and (after or 9999) > 10:
                continue
            player = clean(proposed_rank[proposed_rank["canonical_player_id"].eq(player_id)]["Player"].iloc[0])
            impact_rows.append(
                {
                    "impact_type": "Hall of Fame",
                    "metric": metric,
                    "player": player,
                    "current_value": numeric(authoritative[authoritative["canonical_player_id"].eq(player_id)][metric].iloc[0]),
                    "proposed_value": numeric(simulated[simulated["canonical_player_id"].eq(player_id)][metric].iloc[0]),
                    "current_rank": before,
                    "proposed_rank": after,
                    "current_band": "",
                    "proposed_band": "",
                    "notes": "Top-10 ranking would change under the simulated metric-level replacements.",
                }
            )

    def match_band(value: object) -> str:
        number = numeric(value) or 0.0
        bands = [50, 100, 200, 300, 400]
        achieved = [band for band in bands if number >= band]
        return str(max(achieved)) if achieved else ""

    for row in candidates.itertuples(index=False):
        before = match_band(row.scorebook_matches)
        after = match_band(row.proposed_matches)
        if before != after:
            impact_rows.append(
                {
                    "impact_type": "Milestone",
                    "metric": "Matches",
                    "player": row.player_name,
                    "current_value": row.scorebook_matches,
                    "proposed_value": row.proposed_matches,
                    "current_rank": None,
                    "proposed_rank": None,
                    "current_band": before,
                    "proposed_band": after,
                    "notes": "Highest achieved GWHCC match club would change.",
                }
            )
    columns = ["impact_type", "metric", "player", "current_value", "proposed_value", "current_rank", "proposed_rank", "current_band", "proposed_band", "notes"]
    return pd.DataFrame(impact_rows, columns=columns).drop_duplicates().sort_values(["impact_type", "metric", "player"])


def main() -> int:
    args = parse_args()
    workbook = args.workbook.resolve()
    if not workbook.exists():
        raise SystemExit(f"Workbook not found: {workbook}")
    career = pd.read_excel(workbook, sheet_name="Career Master", header=2, dtype=object)
    if len(career) != 881:
        raise SystemExit(f"Expected 881 Career Master rows, found {len(career)}")

    base, authoritative, _ = load_current_sources()
    registry = current_registry(authoritative)
    aliases = document_aliases(registry)
    first_xi_confirmed, first_xi_seasons, _ = first_xi_evidence(workbook)
    coverage_audit = pd.read_csv(VALIDATION / "gwhcc_historical_coverage_audit.csv", dtype=str).fillna("")
    career_actions = coverage_audit[coverage_audit["feature"].eq("Career Master totals")].copy()
    action_by_name = {
        clean(row["player/record"]): clean(row["action required"])
        for _, row in career_actions.drop_duplicates("player/record").iterrows()
    }
    career["_prior_action"] = career["Source Name"].map(lambda value: action_by_name.get(clean(value), ""))
    previous_review_rows = set(career[career["_prior_action"].str.startswith("Identity review required")]["Source Row"].astype(int))
    higher_rows = set(career[career["_prior_action"].str.startswith("Review season overlap")]["Source Row"].astype(int))
    # The governed 314-case baseline treats the duplicated RANJAN.R rows as one
    # source-risk case rather than two independent players.
    ranjan_rows = career[career["Source Name"].map(normalize).eq(normalize("RANJAN.R"))]["Source Row"].astype(int)
    if not ranjan_rows.empty:
        higher_rows.add(int(ranjan_rows.min()))

    identity = build_identity_audit(career, registry, aliases, first_xi_confirmed, first_xi_seasons, previous_review_rows, higher_rows)
    totals = build_total_audit(career, identity, base, authoritative, workbook.name)
    identity = classify_higher_total_cases(identity, totals, career)
    impact = build_impact_audit(authoritative, totals)

    VALIDATION.mkdir(parents=True, exist_ok=True)
    identity.to_csv(IDENTITY_OUTPUT, index=False)
    totals.to_csv(TOTAL_OUTPUT, index=False)
    impact.to_csv(IMPACT_OUTPUT, index=False)

    print(f"identity_rows={len(identity)} status={identity['identity_status'].value_counts().to_dict()}")
    print(f"starting_review_rows={identity['previous_identity_review'].eq('true').sum()} reduction={identity.loc[identity['previous_identity_review'].eq('true'), 'review_reduction_category'].value_counts().to_dict()}")
    print(f"higher_total_rows={identity['higher_total_case'].eq('true').sum()} categories={identity.loc[identity['higher_total_case'].eq('true'), 'higher_total_category'].value_counts().to_dict()}")
    print(f"total_rows={len(totals)} authority={totals['recommended_authority'].value_counts().to_dict()}")
    print(f"historical_only={identity['historical_only'].eq('true').sum()} impact_rows={len(impact)}")
    print(f"outputs={IDENTITY_OUTPUT},{TOTAL_OUTPUT},{IMPACT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
