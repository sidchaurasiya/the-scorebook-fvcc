"""Hawks data-governance helpers for grade labels, scopes, and review exports."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.data.gwhcc_match_policy import PROCESSED, build_match_policy_table, read_csv

CLUB_ID = "glen-waverley-hawks"
CLUB_ROOT = Path(__file__).resolve().parents[2] / "clubs" / CLUB_ID
SOURCE_DIR = CLUB_ROOT / "data" / "source"
VALIDATION_DIR = PROCESSED / "validation"
GRADE_MAPPING_PATH = SOURCE_DIR / "gwhcc_grade_competition_normalisation.csv"
MATCH_COUNT_FOOTNOTE = "* Hawks match counts apply club rules: T20 = 0.5 match; no-play games are excluded."

GRADE_COLUMNS = [
    "raw_grade_name",
    "display_grade_name",
    "grade_group",
    "grade_type",
    "format",
    "age_group",
    "gender_group",
    "display_order",
    "include_in_senior_records",
    "include_in_junior_records",
    "include_in_whole_club_records",
    "requires_review",
    "notes",
]


def clean_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def raw_grade_names() -> list[str]:
    names: set[str] = set()
    for path in [
        PROCESSED / "teams.csv",
        PROCESSED / "all_seasons_batting.csv",
        PROCESSED / "all_seasons_bowling.csv",
        PROCESSED / "all_seasons_fielding.csv",
        PROCESSED / "season_overview" / "season_by_round_scorecards.csv",
    ]:
        frame = read_csv(path)
        if not frame.empty and "grade_name" in frame:
            names.update(clean_text(value) for value in frame["grade_name"] if clean_text(value))
        if not frame.empty and "competition" in frame:
            names.update(clean_text(value) for value in frame["competition"] if clean_text(value))
    policy = build_match_policy_table()
    if not policy.empty and "grade_name" in policy:
        names.update(clean_text(value) for value in policy["grade_name"] if clean_text(value))
    return sorted(names, key=lambda value: (grade_mapping_row(value)["display_order"], value.casefold()))


def display_grade_name(raw: object) -> str:
    text = clean_text(raw)
    if not text:
        return ""
    text = re.sub(r"^\d+\.\s*", "", text)
    text = re.sub(r"^\d+\s*[-–]\s*", "", text)
    text = re.sub(r"\bCompare & Conect\b", "Compare & Connect", text, flags=re.IGNORECASE)
    text = re.sub(r"\bGlen Waverley Hawks\s*[-–]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\((?:\d+\s*Overs?|12\s*Players?|11\s*Players?|77/78 to 2000)[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bModern Orthodontics\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bUnder\s+(\d+)\b", r"U\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bFri(?:day)?\b", "Friday", text, flags=re.IGNORECASE)
    text = re.sub(r"\bSat(?:urday)?\b", "Saturday", text, flags=re.IGNORECASE)
    text = re.sub(r"\bT20\s+(.+?)\s*[-–]\s*Kookaburra Shield\b", r"T20 \1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bA Grade\b.*", "A Grade", text) if "A Grade" in text and "T20" not in text else text
    text = re.sub(r"\bC Grade\b.*", "C Grade", text) if "C Grade" in text and "T20" not in text else text
    text = re.sub(r"\bD Grade\b.*", "D Grade", text) if "D Grade" in text and "T20" not in text else text
    text = re.sub(r"\bB Grade\b.*", "B Grade", text) if "B Grade" in text and "T20" not in text else text
    text = re.sub(r"\b(\d+)(?:st|nd|rd|th)\s+XI\b", lambda m: f"{m.group(1)} XI", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*-\s*A Grade$", " A Grade", text)
    text = re.sub(r"\s*-\s*B Grade$", " B Grade", text)
    text = re.sub(r"\s*-\s*C Grade$", " C Grade", text)
    text = re.sub(r"\s*-\s*D Grade$", " D Grade", text)
    return clean_text(text)


def grade_mapping_row(raw: object) -> dict[str, object]:
    raw_text = clean_text(raw)
    display = display_grade_name(raw_text)
    lowered = raw_text.casefold()
    display_lower = display.casefold()
    age_match = re.search(r"\b(?:under\s*)?u?(\d{2})(?=[a-z]?\b)", display_lower)
    is_t20 = bool(re.search(r"\b(t20|twenty20|20\s*over|20-over)\b", lowered))
    is_fast = "fast" in lowered or "anklbytrs" in lowered or "entry" in lowered
    is_entry_junior = is_fast or "super 7" in lowered or "stage 1" in lowered
    is_junior = bool(age_match) or is_entry_junior
    is_women_girls = any(token in lowered for token in ["women", "womens", "girls", "female"])
    if is_t20:
        group = "T20"
        order = 300
        fmt = "T20"
    elif is_junior:
        age = int(age_match.group(1)) if age_match else 10
        group = "Junior"
        order = {18: 400, 16: 500, 14: 600, 13: 650, 12: 700}.get(age, 800)
        fmt = "Junior"
    elif is_women_girls:
        group = "Senior women/girls"
        order = 200
        fmt = "One Day"
    elif not raw_text or "unknown" in lowered:
        group = "Legacy / review"
        order = 900
        fmt = "Unknown"
    else:
        group = "Senior/open"
        order = 100
        fmt = "One Day"
    requires_review = (
        not raw_text
        or "anklbytrs" in lowered
        or fmt == "Unknown"
        or "grade 2nds" in lowered
        or (bool(re.search(r"\b[a-z]{2,}\d+[a-z]*\b", lowered)) and not is_junior)
    )
    grade_type = "T20" if is_t20 else "Junior" if is_junior else "Senior/open"
    record_scope = record_scope_for_mapping(group, fmt)
    notes = f"record_scope={record_scope}"
    if requires_review:
        notes += "; mapping requires POC review"
    return {
        "raw_grade_name": raw_text,
        "display_grade_name": display or raw_text,
        "grade_group": group,
        "grade_type": grade_type,
        "format": fmt,
        "age_group": f"U{age_match.group(1)}" if age_match else ("Entry junior" if is_entry_junior else "Open"),
        "gender_group": "Women/Girls" if is_women_girls else "Open/Mixed",
        "display_order": order,
        "include_in_senior_records": str(group == "Senior/open").lower(),
        "include_in_junior_records": str(group == "Junior").lower(),
        "include_in_whole_club_records": "true",
        "requires_review": str(requires_review).lower(),
        "notes": notes,
    }


def record_scope_for_mapping(group: str, fmt: str) -> str:
    if fmt == "T20":
        return "T20"
    if group == "Junior":
        return "Junior"
    if group in {"Senior/open", "Senior women/girls"}:
        return "Senior/open"
    return "Whole club"


def write_grade_normalisation() -> pd.DataFrame:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    rows = [grade_mapping_row(name) for name in raw_grade_names()]
    frame = pd.DataFrame(rows, columns=GRADE_COLUMNS).drop_duplicates("raw_grade_name")
    frame = frame.sort_values(["display_order", "display_grade_name", "raw_grade_name"])
    frame.to_csv(GRADE_MAPPING_PATH, index=False)
    return frame


def load_grade_mapping() -> pd.DataFrame:
    if not GRADE_MAPPING_PATH.exists():
        return write_grade_normalisation()
    frame = read_csv(GRADE_MAPPING_PATH)
    if frame.empty:
        return write_grade_normalisation()
    return frame


@lru_cache(maxsize=4)
def _mapping_lookup_for_version(
    mapping_path: str,
    mapping_mtime_ns: int,
) -> dict[str, dict[str, object]]:
    _ = (mapping_path, mapping_mtime_ns)
    frame = load_grade_mapping()
    return {clean_text(row["raw_grade_name"]): row.to_dict() for _, row in frame.iterrows()}


def mapping_lookup() -> dict[str, dict[str, object]]:
    mapping_mtime_ns = GRADE_MAPPING_PATH.stat().st_mtime_ns if GRADE_MAPPING_PATH.exists() else -1
    return _mapping_lookup_for_version(str(GRADE_MAPPING_PATH), mapping_mtime_ns)


def annotate_grade_metadata(frame: pd.DataFrame, grade_column: str = "grade_name") -> pd.DataFrame:
    if frame.empty or grade_column not in frame:
        return frame.copy()
    lookup = mapping_lookup()
    output = frame.copy()
    rows = output[grade_column].map(lambda value: lookup.get(clean_text(value), grade_mapping_row(value)))
    for column in GRADE_COLUMNS:
        if column == "raw_grade_name":
            continue
        output[column] = rows.map(lambda row, c=column: row.get(c, ""))
    output["record_scope"] = rows.map(lambda row: record_scope_for_mapping(str(row.get("grade_group", "")), str(row.get("format", ""))))
    output["match_count_policy_note"] = MATCH_COUNT_FOOTNOTE
    return output


def annotate_app_files() -> list[dict[str, object]]:
    changed: list[dict[str, object]] = []
    files = [
        PROCESSED / "all_seasons_batting.csv",
        PROCESSED / "all_seasons_bowling.csv",
        PROCESSED / "all_seasons_fielding.csv",
        PROCESSED / "all_seasons_matches.csv",
        PROCESSED / "teams.csv",
        PROCESSED / "season_overview" / "season_by_round_scorecards.csv",
        PROCESSED / "player_profile" / "performance_breakdown_by_dimension.csv",
    ]
    for path in files:
        frame = read_csv(path)
        if frame.empty:
            continue
        grade_column = "grade_name" if "grade_name" in frame else "competition" if "competition" in frame else ""
        if not grade_column:
            continue
        output = annotate_grade_metadata(frame, grade_column=grade_column)
        output.to_csv(path, index=False)
        changed.append({"path": str(path), "rows": len(output)})
    return changed


def build_t20_reconciliation() -> pd.DataFrame:
    policy = build_match_policy_table()
    coverage = read_csv(VALIDATION_DIR / "gwhcc_playhq_season_coverage_audit.csv")
    season_count = int(pd.to_numeric(coverage.get("matches_t20"), errors="coerce").fillna(0).sum()) if not coverage.empty else 0
    all_t20 = policy[policy["detected_match_format"].eq("T20")]
    played_t20 = all_t20[~all_t20["is_no_play"]]
    no_play_t20 = all_t20[all_t20["is_no_play"]]
    rows = [
        {
            "metric": "season_coverage_t20_count",
            "value": season_count,
            "definition": "All matches detected as T20, including no-play exclusions.",
            "authoritative": "no",
        },
        {
            "metric": "policy_validator_t20_count",
            "value": int(len(played_t20)),
            "definition": "Played T20 matches with match_weight=0.5.",
            "authoritative": "yes",
        },
        {
            "metric": "final_weighted_source_t20_count",
            "value": int(len(played_t20)),
            "definition": "T20 fixtures that contribute 0.5 to weighted player match counts.",
            "authoritative": "yes",
        },
        {
            "metric": "excluded_t20_no_play_count",
            "value": int(len(no_play_t20)),
            "definition": "Detected T20 fixtures excluded because no play/activity was detected.",
            "authoritative": "supporting",
        },
    ]
    if not no_play_t20.empty:
        for row in no_play_t20.sort_values(["season", "first_match_day", "grade_name"]).itertuples(index=False):
            rows.append(
                {
                    "metric": "excluded_t20_match",
                    "value": 1,
                    "season": getattr(row, "season", ""),
                    "match_id": getattr(row, "match_id", ""),
                    "grade_name": getattr(row, "grade_name", ""),
                    "match_date": getattr(row, "first_match_day", ""),
                    "reason": getattr(row, "gap_note", "no-play T20 excluded from weighted policy count"),
                    "definition": "Excluded T20 match detail.",
                    "authoritative": "supporting",
                }
            )
    frame = pd.DataFrame(rows)
    frame["reason_for_mismatch"] = (
        "Season coverage reports detected T20 fixtures; policy validation reports only played T20 fixtures that receive a 0.5 match weight."
    )
    frame["final_authoritative_value"] = int(len(played_t20))
    return frame


def write_t20_reconciliation() -> pd.DataFrame:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    frame = build_t20_reconciliation()
    frame.to_csv(VALIDATION_DIR / "gwhcc_t20_count_reconciliation.csv", index=False)
    return frame


def review_reason(row: pd.Series) -> str:
    reasons: list[str] = []
    if float(row.get("batting_rows", 0) or 0) == 0 or float(row.get("bowling_rows", 0) or 0) == 0:
        reasons.append("missing scorecard")
    if bool(row.get("review_required")):
        reasons.append("no-play detection uncertain")
    if bool(row.get("is_no_play")) and float(row.get("selected_player_count", 0) or 0) > 0:
        reasons.append("selected squad exists but no cricket activity")
    if not clean_text(row.get("result_text")) or clean_text(row.get("result_text")).casefold() == "result pending":
        reasons.append("missing result")
    if clean_text(row.get("detected_match_format")) == "Unknown":
        reasons.append("format unknown")
    if "t20" in clean_text(row.get("grade_name")).casefold() and clean_text(row.get("detected_match_format")) != "T20":
        reasons.append("T20 classification uncertain")
    return "; ".join(dict.fromkeys(reasons))


def build_matches_needing_review() -> pd.DataFrame:
    policy = build_match_policy_table()
    if policy.empty:
        return pd.DataFrame()
    output = policy.copy()
    output["review_reason"] = output.apply(review_reason, axis=1)
    output = output[output["review_reason"].astype(str).str.strip().ne("")].copy()
    output["date"] = output.get("first_match_day", "")
    output["team_or_grade"] = output.get("grade_name", "")
    output["opponent"] = output.apply(
        lambda row: row.get("away_team_name") if row.get("club_team_id") == row.get("home_team_id") else row.get("home_team_name"),
        axis=1,
    )
    output["scorecard_url"] = output.get("scorecard_url", "")
    output["has_scorecard"] = output[["batting_rows", "bowling_rows", "fielding_rows"]].max(axis=1).gt(0)
    output["has_batting_rows"] = output["batting_rows"].gt(0)
    output["has_bowling_rows"] = output["bowling_rows"].gt(0)
    output["has_fielding_rows"] = output["fielding_rows"].gt(0)
    output["has_bbb"] = output["bbb_rows"].gt(0)
    output["balls_detected"] = output["total_balls_detected"]
    output["no_play_detected"] = output["is_no_play"]
    output["format_detected"] = output["detected_match_format"]
    columns = [
        "season",
        "date",
        "team_or_grade",
        "opponent",
        "result_text",
        "status",
        "match_id",
        "scorecard_url",
        "has_scorecard",
        "has_batting_rows",
        "has_bowling_rows",
        "has_fielding_rows",
        "has_bbb",
        "balls_detected",
        "no_play_detected",
        "format_detected",
        "review_reason",
    ]
    output = output.rename(columns={"result_text": "result"})
    columns[4] = "result"
    for column in columns:
        if column not in output:
            output[column] = ""
    return output[columns].sort_values(["season", "date", "team_or_grade", "match_id"])


def write_matches_needing_review() -> pd.DataFrame:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    frame = build_matches_needing_review()
    output = VALIDATION_DIR / "gwhcc_matches_needing_review.csv"
    frame.to_csv(output, index=False)
    lines = [
        "# GWHCC Matches Needing Review",
        "",
        f"- Review rows: {len(frame)}",
    ]
    if not frame.empty:
        counts = frame["review_reason"].str.get_dummies(sep="; ").sum().sort_values(ascending=False)
        lines += ["", "| Reason | Matches |", "|---|---:|"]
        lines += [f"| {reason} | {int(count)} |" for reason, count in counts.items()]
    (VALIDATION_DIR / "gwhcc_matches_needing_review_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame


def build_bbb_player_dna_coverage() -> pd.DataFrame:
    policy = build_match_policy_table()
    selected = read_selected_for_bbb(policy)
    if selected.empty:
        return pd.DataFrame(columns=["player", "season", "played_matches_weighted", "matches_with_bbb", "bbb_coverage_pct", "dna_status", "notes"])
    grouped = selected.groupby(["player_id", "player_name", "season"], dropna=False, as_index=False).agg(
        played_matches_weighted=("match_weight", "sum"),
        matches_with_bbb=("has_bbb", "sum"),
    )
    grouped["bbb_coverage_pct"] = grouped.apply(
        lambda row: round(float(row["matches_with_bbb"]) * 100 / float(row["played_matches_weighted"]), 2)
        if float(row["played_matches_weighted"] or 0) > 0
        else 0.0,
        axis=1,
    )
    grouped["dna_status"] = grouped["bbb_coverage_pct"].map(
        lambda pct: "strong" if pct >= 80 else "partial" if pct >= 30 else "limited" if pct > 0 else "unavailable"
    )
    grouped["notes"] = grouped.apply(
        lambda row: f"Player DNA uses ball-by-ball data where available. Coverage: {row['matches_with_bbb']:g} of {row['played_matches_weighted']:g} weighted matches.",
        axis=1,
    )
    return grouped.rename(columns={"player_name": "player"})[
        ["player", "season", "played_matches_weighted", "matches_with_bbb", "bbb_coverage_pct", "dna_status", "notes"]
    ].sort_values(["player", "season"])


def read_selected_for_bbb(policy: pd.DataFrame) -> pd.DataFrame:
    from src.data.gwhcc_match_policy import selected_player_rows

    selected = selected_player_rows(policy)
    if selected.empty:
        return selected
    selected = selected[selected["match_weight"].gt(0)].copy()
    bbb_lookup = policy[["match_id", "bbb_rows"]].copy()
    bbb_lookup["has_bbb"] = pd.to_numeric(bbb_lookup["bbb_rows"], errors="coerce").fillna(0).gt(0)
    selected = selected.merge(bbb_lookup[["match_id", "has_bbb"]], on="match_id", how="left")
    selected["has_bbb"] = selected["has_bbb"].fillna(False).astype(int)
    return selected


def write_bbb_player_dna_coverage() -> pd.DataFrame:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    frame = build_bbb_player_dna_coverage()
    frame.to_csv(VALIDATION_DIR / "gwhcc_bbb_player_dna_coverage.csv", index=False)
    return frame


def build_source_quality_dashboard() -> pd.DataFrame:
    coverage = read_csv(VALIDATION_DIR / "gwhcc_playhq_season_coverage_audit.csv")
    review = build_matches_needing_review()
    if coverage.empty:
        return pd.DataFrame()
    review_counts = review.groupby("season").size().rename("matches_needing_review").reset_index() if not review.empty else pd.DataFrame(columns=["season", "matches_needing_review"])
    dashboard = coverage.merge(review_counts, on="season", how="left")
    dashboard["matches_needing_review"] = pd.to_numeric(dashboard["matches_needing_review"], errors="coerce").fillna(0).astype(int)
    dashboard["format_unknown_count"] = dashboard["gap_notes"].fillna("").astype(str).str.extract(r"(\d+) played/known matches have unknown format")[0]
    dashboard["format_unknown_count"] = pd.to_numeric(dashboard["format_unknown_count"], errors="coerce").fillna(0).astype(int)
    dashboard["readiness_status"] = dashboard.apply(
        lambda row: "review_required"
        if row["matches_needing_review"] or row["format_unknown_count"]
        else "ready_with_playhq",
        axis=1,
    )
    return dashboard[
        [
            "season",
            "scorecard_coverage_pct",
            "bbb_coverage_pct",
            "matches_needing_review",
            "matches_no_play",
            "matches_t20",
            "format_unknown_count",
            "players_count",
            "readiness_status",
        ]
    ].rename(
        columns={
            "matches_no_play": "no_play_exclusions",
            "matches_t20": "t20_half_counted",
        }
    )


def write_source_quality_dashboard() -> pd.DataFrame:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    frame = build_source_quality_dashboard()
    frame.to_csv(VALIDATION_DIR / "gwhcc_source_quality_dashboard.csv", index=False)
    return frame
