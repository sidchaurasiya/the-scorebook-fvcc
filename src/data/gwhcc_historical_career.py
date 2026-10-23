"""Explicit, dated Hawks career anchors; annual detail is never reconstructed."""

from __future__ import annotations

import math
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

CLUB_ID = "glen-waverley-hawks"
DATA = Path(__file__).resolve().parents[2] / "clubs" / CLUB_ID / "data"
ANCHORS = DATA / "source/document_overrides/gwhcc_dated_career_anchors.csv"
VERIFIED_ANCHORS = DATA / "source/document_overrides/gwhcc_verified_career_anchors.csv"
BATTING = DATA / "processed/all_seasons_batting.csv"
BOWLING = DATA / "processed/all_seasons_bowling.csv"
COUNT_COLUMNS = {
    "runs": "Runs", "innings": "Innings", "not_outs": "Not Outs",
    "wickets": "Wickets", "bowling_runs": "Runs Against",
}
SOURCE_COLUMNS = {
    "batting": {"runs": "battingAggregate", "innings": "battingInnings", "not_outs": "battingNotOuts"},
    "bowling": {"wickets": "bowlingWickets", "bowling_runs": "bowlingRuns"},
}
COVERAGE_NOTE = (
    "Career runs, innings, not-outs, wickets and averages include historical club records "
    "without season-by-season detail. Matches, fielding and detailed rate, season and grade "
    "statistics reflect available digital records."
)


def season_start(value: object) -> int:
    match = re.fullmatch(r"Summer ((?:19|20)\d{2})/(\d{2})", str(value).strip())
    if not match or (int(match[1]) + 1) % 100 != int(match[2]):
        raise ValueError(f"Invalid Hawks career source season: {value}")
    return int(match[1])


def dated_career_signature() -> tuple:
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in [ANCHORS, VERIFIED_ANCHORS, BATTING, BOWLING] if p.exists())


def anchor_scopes(row: dict) -> tuple[str, ...]:
    value = str(row.get("metric_scope", "") or "").strip()
    scopes = tuple(value.split(";")) if value else ("batting", "bowling")
    if len(set(scopes)) != len(scopes) or not set(scopes).issubset(SOURCE_COLUMNS):
        raise ValueError("Unsupported or overlapping historical career metric scope")
    return scopes


def anchor_cutoff(row: dict, scope: str) -> str:
    return str(row.get(f"{scope}_anchor_through_season", "") or row["anchor_through_season"])


def has_dated_career_scope(career: pd.Series, scope: str) -> bool:
    return str(career.get("historical_career_anchor_applied", "")).casefold() == "true" and scope in str(
        career.get("historical_career_anchor_metric_scope", "batting;bowling")
    ).split(";")


def career_anchor_coverage_note(career: pd.Series) -> str:
    batting = has_dated_career_scope(career, "batting")
    bowling = has_dated_career_scope(career, "bowling")
    if batting and bowling:
        return COVERAGE_NOTE
    if batting:
        return ("Career batting totals and average include historical club records without season-by-season detail. "
                "Bowling, matches, fielding and detailed rate, season and grade statistics reflect available digital records.")
    if bowling:
        return ("Career wickets and bowling average include historical club records without season-by-season detail. "
                "Batting, matches, fielding and detailed rate, season and grade statistics reflect available digital records.")
    return ""


def load_dated_career_anchors() -> pd.DataFrame:
    sources = [pd.read_csv(path, keep_default_na=False) for path in [ANCHORS, VERIFIED_ANCHORS] if path.exists()]
    if not sources:
        return pd.DataFrame()
    rows = pd.concat(sources, ignore_index=True).fillna("")
    rows = rows[
        rows["decision_status"].eq("approved_dated_career")
        & rows["confidence"].isin({"high", "confirmed", "approved"})
    ].copy()
    if rows.empty:
        return rows
    if rows["canonical_player_id"].eq("").any() or rows["canonical_player_id"].duplicated().any():
        raise ValueError("Approved Hawks career anchors require unique canonical identities")
    for row in rows.to_dict("records"):
        scopes = anchor_scopes(row)
        for scope in scopes:
            season_start(anchor_cutoff(row, scope))
            for metric in SOURCE_COLUMNS[scope]:
                value = pd.to_numeric(row[metric], errors="coerce")
                if pd.isna(value) or not math.isfinite(value) or value < 0 or value != int(value):
                    raise ValueError(f"Incomplete or invalid Hawks historical {metric}")
        if "batting" in scopes and float(row["not_outs"]) > float(row["innings"]):
            raise ValueError("Historical not-outs exceed innings")
        if not re.fullmatch(r"[a-f0-9]{64}", str(row["source_sha256"])):
            raise ValueError("Historical career source fingerprint is missing")
    return rows


@lru_cache(maxsize=4)
def later_career_counts(signature: tuple, cutoffs: tuple) -> dict[str, dict[str, float]]:
    """Cache only compact counts, never complete season tables."""
    _ = signature
    totals = {pid: {} for pid, _, _ in cutoffs}
    for discipline, path in [("batting", BATTING), ("bowling", BOWLING)]:
        years = {pid: year for pid, scope, year in cutoffs if scope == discipline}
        if not years:
            continue
        metrics = SOURCE_COLUMNS[discipline]
        for pid in years:
            totals[pid].update(dict.fromkeys(metrics, 0.0))
        grain = ["canonical_player_id", "season_id", "team_id", "grade_id"]
        rows = pd.read_csv(path, usecols=[*grain, "season", *metrics.values()])
        rows = rows[rows["canonical_player_id"].isin(years)].copy()
        if set(years) - set(rows["canonical_player_id"]):
            raise ValueError("Historical career anchor has no retained source identity")
        rows["_year"] = rows["season"].map(season_start)
        rows = rows[rows["_year"].gt(rows["canonical_player_id"].map(years))]
        if rows[grain].isna().any().any() or rows.duplicated(grain).any():
            raise ValueError("Overlapping or incomplete post-anchor contribution keys")
        for metric, column in metrics.items():
            values = pd.to_numeric(rows[column], errors="coerce")
            if values.isna().any() or values.lt(0).any() or values.mod(1).ne(0).any():
                raise ValueError(f"Unknown post-anchor {metric}; do not infer zero")
            for pid, value in values.groupby(rows["canonical_player_id"]).sum().items():
                totals[pid][metric] = float(value)
    return totals


def apply_dated_career_anchors(frame: pd.DataFrame, *, club_id: str = CLUB_ID) -> pd.DataFrame:
    if club_id != CLUB_ID or frame.empty or "canonical_player_id" not in frame:
        return frame
    from src.utils.player_identity import is_private_or_anonymised_player

    anchors = load_dated_career_anchors()
    if anchors.empty:
        return frame
    anchors = anchors[anchors["canonical_player_id"].isin(frame["canonical_player_id"])]
    if anchors.empty:
        return frame
    cutoffs = tuple(sorted((r["canonical_player_id"], scope, season_start(anchor_cutoff(r, scope)))
                           for r in anchors.to_dict("records") for scope in anchor_scopes(r)))
    later = later_career_counts(dated_career_signature(), cutoffs)
    output = frame.copy()
    for anchor in anchors.to_dict("records"):
        pid = anchor["canonical_player_id"]
        matched = output[output["canonical_player_id"].eq(pid)]
        if len(matched) != 1 or is_private_or_anonymised_player(matched.iloc[0].get("Player"), metadata=matched.iloc[0]):
            continue
        index = matched.index[0]
        # A closed full-career source replaces the overlap; only later seasons are additive.
        scopes = anchor_scopes(anchor)
        selected = {metric for scope in scopes for metric in SOURCE_COLUMNS[scope]}
        counts = {metric: float(anchor[metric]) + later[pid][metric] for metric in selected}
        values = {COUNT_COLUMNS[k]: v for k, v in counts.items()}
        if "batting" in scopes:
            outs = counts["innings"] - counts["not_outs"]
            if outs < 0:
                raise ValueError("Post-anchor not-outs exceed innings")
            values.update({"Outs": outs, "Bat Avg": counts["runs"] / outs if outs else pd.NA})
        if "bowling" in scopes:
            values["Bowl Avg"] = counts["bowling_runs"] / counts["wickets"] if counts["wickets"] else pd.NA
        for column, value in values.items():
            if column in output and pd.api.types.is_integer_dtype(output[column]):
                output[column] = output[column].astype(float)
            metric_name = {"Bat Avg": "batting_average", "Bowl Avg": "bowling_average", "Runs Against": "bowling_runs"}.get(column, column.casefold().replace(" ", "_"))
            detailed = f"detailed_{metric_name}_value"
            if detailed not in output or pd.isna(output.at[index, detailed]):
                output.at[index, detailed] = output.at[index, column] if column in output else pd.NA
            output.at[index, column] = value
        if "NO" in output and "batting" in scopes:
            output.at[index, "NO"] = counts["not_outs"]
        output.at[index, "historical_career_anchor_applied"] = True
        output.at[index, "historical_career_anchor_through_season"] = anchor["anchor_through_season"]
        output.at[index, "historical_career_anchor_metric_scope"] = ";".join(scopes)
        for scope in scopes:
            output.at[index, f"historical_career_{scope}_anchor_through_season"] = anchor_cutoff(anchor, scope)
        output.at[index, "historical_career_anchor_source"] = f"{anchor['source_document']} / {anchor['source_sheet']} row {anchor['source_row']}"
        for metric in {"runs", "wickets"} & selected:
            output.at[index, f"{metric}_value_source"] = "dated_career_master"
            output.at[index, f"{metric}_override_applied"] = True
        for metric in selected | ({"batting_average"} if "batting" in scopes else set()) | ({"bowling_average"} if "bowling" in scopes else set()):
            output.at[index, f"{metric}_authority_source"] = "dated_career_master"
            output.at[index, f"{metric}_authority_scope"] = "full_career_anchor_plus_strictly_later_seasons"
            output.at[index, f"{metric}_authority_source_row"] = str(anchor["source_row"])
    return output
