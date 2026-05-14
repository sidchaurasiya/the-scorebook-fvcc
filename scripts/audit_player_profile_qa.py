#!/usr/bin/env python3
"""Audit Player Profile data quality across a representative player sample.

The script is intentionally read-only against app data. It writes review
artifacts under data/processed/experimental/player_profile_qa/, which is ignored
by git.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"
OUTPUT_DIR = PROCESSED / "experimental" / "player_profile_qa"

APP_BASE_URL = "http://localhost:8502/?page=player-profile"

PLAYER_PROFILE_DIR = PROCESSED / "player_profile"
HOF_DIR = PROCESSED / "hall_of_fame"
SEASON_OVERVIEW_DIR = PROCESSED / "season_overview"
MATCH_CENTRE_DIR = PROCESSED / "match_centre" / "all_available"

SEVERITY_ORDER = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3, "Info": 4}

KNOWN_SAMPLE_NAMES = [
    "Danny Singh",
    "Shandil Bhan",
    "Nitin Tanwar",
    "Kalpeshkumar Patel",
    "Vinit Naidu",
    "Damandeep Sehra",
    "Shaun Vikash",
    "Reuel Sharan",
    "Armaan Datta",
    "Siddhanth Chaurasiya",
    "Jai Bhan",
    "Vinay Sharma",
    "Priyanshu Tomar",
    "Anurag Joshi",
    "Abcin Thomas",
    "Mohaneesh Pitre",
    "Kartik Nallepalli",
    "Janaka Wijayakoon",
    "Faraz Khan",
    "Gopi Krishna",
    "Ravi Chowdary",
    "Predheesh Valayil Sivanandan",
    "Sandeep Gill",
]

MISSPELLING_PROBES = ["Moahneesh Pitre", "Sandeep Singh"]


def read_csv(path: Path, **kwargs: object) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, **kwargs)


def clean_name(value: object) -> str:
    if pd.isna(value):
        return ""
    text = re.sub(r"[^A-Za-z0-9\s]", " ", str(value).strip().casefold())
    return re.sub(r"\s+", " ", text).strip()


def display_name(value: object) -> str:
    text = "" if pd.isna(value) else re.sub(r"\s+", " ", str(value).strip())
    if not text:
        return ""
    return " ".join(part[:1].upper() + part[1:].lower() for part in text.split())


def num(value: object, default: float = 0.0) -> float:
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        return default
    return float(value)


def maybe_num(value: object) -> float | None:
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value) or not math.isfinite(float(value)):
        return None
    return float(value)


def safe_div(numerator: float, denominator: float) -> float | None:
    if not denominator:
        return None
    return numerator / denominator


def close_enough(left: object, right: object, tolerance: float = 0.015) -> bool:
    left_num = maybe_num(left)
    right_num = maybe_num(right)
    if left_num is None and right_num is None:
        return True
    if left_num is None or right_num is None:
        return False
    return abs(left_num - right_num) <= tolerance


def season_sort_key(value: object) -> int:
    text = "" if pd.isna(value) else str(value)
    years = [int(year) for year in re.findall(r"(?:19|20)\d{2}", text)]
    if not years:
        return 0
    if "Summer" in text and len(years) >= 2:
        return years[-1] * 10 + 2
    if "Summer" in text:
        return years[0] * 10 + 2
    if "Winter" in text:
        return years[0] * 10 + 1
    return years[-1] * 10


def parse_bbi(value: object) -> tuple[int | None, int | None]:
    text = "" if pd.isna(value) else str(value).strip()
    match = re.search(r"(\d+)\s*[-/]\s*(\d+)", text)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def high_score_sort_value(value: object) -> float | None:
    text = "" if pd.isna(value) else str(value)
    match = re.search(r"\d+", text)
    if not match:
        return None
    return float(match.group(0))


def balls_to_overs_text(balls: object) -> str:
    balls_num = int(num(balls, 0))
    return f"{balls_num // 6}.{balls_num % 6}"


def truthy(value: object) -> bool:
    if isinstance(value, bool):
        return value
    text = "" if pd.isna(value) else str(value).strip().casefold()
    return text in {"true", "1", "yes", "y"}


def player_url(player_id: object) -> str:
    return f"{APP_BASE_URL}&player_id={player_id}"


def add_finding(
    findings: list[dict[str, object]],
    *,
    severity: str,
    category: str,
    section: str,
    issue: str,
    detail: str,
    player_id: object = "",
    player_name: object = "",
    recommended_fix: str = "",
) -> None:
    findings.append(
        {
            "severity": severity,
            "category": category,
            "section": section,
            "issue": issue,
            "detail": detail,
            "player_id": "" if pd.isna(player_id) else str(player_id),
            "player_name": "" if pd.isna(player_name) else str(player_name),
            "recommended_fix": recommended_fix,
        }
    )


def canonical_player_frame(frames: Iterable[pd.DataFrame]) -> pd.DataFrame:
    records = []
    for frame in frames:
        if frame.empty:
            continue
        required = {"canonical_player_id", "canonical_player_name"}
        if not required.issubset(frame.columns):
            continue
        records.append(frame[["canonical_player_id", "canonical_player_name"]])
    if not records:
        return pd.DataFrame(columns=["canonical_player_id", "canonical_player_name"])
    output = pd.concat(records, ignore_index=True).dropna()
    output["name_key"] = output["canonical_player_name"].map(clean_name)
    output = output.drop_duplicates(["canonical_player_id", "name_key"])
    output["canonical_player_name"] = output["canonical_player_name"].map(display_name)
    return output.sort_values("canonical_player_name").reset_index(drop=True)


def scoped_player_rows(frame: pd.DataFrame, player_id: str, name_key: str) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    output = frame.copy()
    id_mask = pd.Series(False, index=output.index)
    for column in ["canonical_player_id", "player_key", "player_id"]:
        if column in output:
            id_mask = id_mask | output[column].fillna("").astype(str).str.strip().eq(player_id)
    if id_mask.any():
        return output[id_mask].copy()
    name_mask = pd.Series(False, index=output.index)
    for column in ["canonical_player_name", "display_player_name", "player_name", "raw_player_name"]:
        if column in output:
            name_mask = name_mask | output[column].map(clean_name).eq(name_key)
    return output[name_mask].copy() if name_mask.any() else output.head(0).copy()


def match_total(frames: list[pd.DataFrame]) -> int:
    rows = []
    for frame in frames:
        if frame.empty or "matches" not in frame:
            continue
        output = frame.copy()
        output["matches"] = pd.to_numeric(output["matches"], errors="coerce").fillna(0)
        group_cols = [column for column in ["season", "team_id"] if column in output]
        if group_cols:
            rows.append(output.groupby(group_cols, dropna=False, as_index=False)["matches"].max())
        else:
            rows.append(pd.DataFrame({"matches": [output["matches"].max()]}))
    if not rows:
        return 0
    combined = pd.concat(rows, ignore_index=True)
    group_cols = [column for column in ["season", "team_id"] if column in combined]
    if group_cols:
        return int(combined.groupby(group_cols, dropna=False)["matches"].max().sum())
    return int(combined["matches"].max())


def best_high_score(batting: pd.DataFrame) -> tuple[str, float | None]:
    if batting.empty or "battingHighScore" not in batting:
        return "N/A", None
    output = batting.copy()
    output["_score"] = pd.to_numeric(output["battingHighScore"], errors="coerce")
    output = output[output["_score"].notna()]
    if output.empty:
        return "N/A", None
    if "isBattingHSNotOut" in output:
        output["_not_out"] = output["isBattingHSNotOut"].map(truthy)
    else:
        output["_not_out"] = False
    row = output.sort_values(["_score", "_not_out"], ascending=[False, False]).iloc[0]
    star = "*" if truthy(row.get("isBattingHSNotOut", False)) else ""
    return f"{int(row['_score'])}{star}", float(row["_score"])


def best_bowling(bowling: pd.DataFrame) -> str:
    if bowling.empty or "bowlingBestInnings" not in bowling:
        return "N/A"
    rows = []
    for _, row in bowling.dropna(subset=["bowlingBestInnings"]).iterrows():
        wickets, runs = parse_bbi(row.get("bowlingBestInnings"))
        if wickets is None or wickets <= 0:
            continue
        rows.append((wickets, runs or 9999, str(row.get("bowlingBestInnings"))))
    if not rows:
        return "N/A"
    rows.sort(key=lambda item: (-item[0], item[1]))
    return rows[0][2]


def aggregate_player_metrics(
    players: pd.DataFrame,
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
    bbb_career: pd.DataFrame,
) -> pd.DataFrame:
    rows = []
    for player in players.to_dict("records"):
        player_id = str(player["canonical_player_id"])
        name = str(player["canonical_player_name"])
        key = clean_name(name)
        bat = scoped_player_rows(batting, player_id, key)
        bowl = scoped_player_rows(bowling, player_id, key)
        field = scoped_player_rows(fielding, player_id, key)
        bbb = scoped_player_rows(bbb_career, player_id, key)
        seasons = sorted(
            set(
                pd.concat(
                    [
                        bat.get("season", pd.Series(dtype=str)),
                        bowl.get("season", pd.Series(dtype=str)),
                        field.get("season", pd.Series(dtype=str)),
                    ],
                    ignore_index=True,
                )
                .dropna()
                .astype(str)
            ),
            key=season_sort_key,
        )
        grades = sorted(
            set(
                pd.concat(
                    [
                        bat.get("grade_name", pd.Series(dtype=str)),
                        bowl.get("grade_name", pd.Series(dtype=str)),
                        field.get("grade_name", pd.Series(dtype=str)),
                    ],
                    ignore_index=True,
                )
                .dropna()
                .astype(str)
            )
        )
        innings = num(bat.get("battingInnings", pd.Series(dtype=float)).sum())
        runs = num(bat.get("battingAggregate", pd.Series(dtype=float)).sum())
        not_outs = num(bat.get("battingNotOuts", pd.Series(dtype=float)).sum())
        outs = max(0.0, innings - not_outs)
        wickets = num(bowl.get("bowlingWickets", pd.Series(dtype=float)).sum())
        balls_bowled = num(bowl.get("bowlingBalls", pd.Series(dtype=float)).sum())
        runs_against = num(bowl.get("bowlingRuns", pd.Series(dtype=float)).sum())
        catches = num(field.get("fieldingTotalCatches", pd.Series(dtype=float)).sum())
        stumpings = num(field.get("fieldingStumpings", pd.Series(dtype=float)).sum())
        run_outs = num(field.get("fieldingRunOuts", pd.Series(dtype=float)).sum())
        bbb_runs = num(bbb.get("bbb_runs", pd.Series(dtype=float)).sum())
        bbb_balls = num(bbb.get("bbb_balls_faced", pd.Series(dtype=float)).sum())
        hs, hs_sort = best_high_score(bat)
        rows.append(
            {
                "canonical_player_id": player_id,
                "canonical_player_name": name,
                "name_key": key,
                "matches": match_total([bat, bowl, field]),
                "innings": innings,
                "runs": runs,
                "not_outs": not_outs,
                "outs": outs,
                "bat_avg_expected": safe_div(runs, outs),
                "balls_faced_scorecard": num(bat.get("battingBallsFaced", pd.Series(dtype=float)).sum()),
                "bbb_runs": bbb_runs,
                "bbb_balls_faced": bbb_balls,
                "bat_sr_expected": safe_div(bbb_runs * 100, bbb_balls) if bbb_balls else None,
                "high_score": hs,
                "high_score_sort": hs_sort,
                "wickets": wickets,
                "balls_bowled": balls_bowled,
                "overs": balls_to_overs_text(balls_bowled) if balls_bowled else "N/A",
                "runs_against": runs_against,
                "bowl_avg_expected": safe_div(runs_against, wickets),
                "bowl_sr_expected": safe_div(balls_bowled, wickets),
                "eco_expected": safe_div(runs_against * 6, balls_bowled),
                "bbi": best_bowling(bowl),
                "catches": catches,
                "stumpings": stumpings,
                "run_outs": run_outs,
                "dismissals": catches + stumpings + run_outs,
                "seasons": " | ".join(seasons),
                "season_count": len(seasons),
                "career_span": f"{seasons[0]} - {seasons[-1]}" if len(seasons) > 1 else (seasons[0] if seasons else ""),
                "grades_played": " | ".join(grades),
                "latest_season_key": max([season_sort_key(item) for item in seasons], default=0),
                "earliest_season_key": min([season_sort_key(item) for item in seasons], default=0),
            }
        )
    return pd.DataFrame(rows)


def select_audit_players(metrics: pd.DataFrame, findings: list[dict[str, object]]) -> pd.DataFrame:
    selected: dict[str, set[str]] = {}
    names_by_id = metrics.set_index("canonical_player_id")["canonical_player_name"].to_dict()
    by_name = {clean_name(row["canonical_player_name"]): row for row in metrics.to_dict("records")}

    def add_player(row: pd.Series | dict[str, object] | None, reason: str) -> None:
        if row is None:
            return
        player_id = str(row.get("canonical_player_id", "")).strip()
        if not player_id:
            return
        selected.setdefault(player_id, set()).add(reason)

    for name in KNOWN_SAMPLE_NAMES:
        row = by_name.get(clean_name(name))
        if row:
            add_player(row, "requested/known representative")
        else:
            add_finding(
                findings,
                severity="Medium",
                category="identity",
                section="sample selection",
                issue="Requested player not found",
                detail=f"{name} was requested for QA but was not found as a canonical profile.",
                player_name=name,
                recommended_fix="Confirm spelling or canonical merge mapping.",
            )

    for alias in MISSPELLING_PROBES:
        if clean_name(alias) in by_name:
            add_finding(
                findings,
                severity="High",
                category="identity",
                section="canonical player index",
                issue="Merge-sensitive alias appears as separate canonical profile",
                detail=f"{alias} appears as its own canonical profile.",
                player_name=alias,
                recommended_fix="Review manual player merge mapping.",
            )
        else:
            add_finding(
                findings,
                severity="Info",
                category="identity",
                section="canonical player index",
                issue="Merge-sensitive alias not present as duplicate",
                detail=f"{alias} was not found as a separate canonical player.",
                player_name=alias,
            )

    top_specs = [
        ("club legend/high matches", "matches", False, 12),
        ("batting-heavy/top runs", "runs", False, 10),
        ("batting-heavy/high average", "bat_avg_expected", False, 8),
        ("batting-heavy/high score", "high_score_sort", False, 8),
        ("bowling-heavy/top wickets", "wickets", False, 10),
        ("all-rounder", "allround_score", False, 10),
        ("fielder/keeper", "dismissals", False, 8),
        ("older inactive", "latest_season_key", True, 8),
        ("low-data edge case", "matches", True, 8),
        ("not-out-heavy edge case", "not_out_rate", False, 6),
        ("missing-BBB edge case", "bbb_balls_faced", True, 8),
    ]
    candidates = metrics.copy()
    candidates["allround_score"] = candidates["runs"].clip(lower=0) * candidates["wickets"].clip(lower=0)
    candidates["not_out_rate"] = candidates.apply(
        lambda row: safe_div(float(row["not_outs"]), float(row["innings"])) or 0,
        axis=1,
    )
    high_average = candidates[(candidates["innings"] >= 10) & (candidates["outs"] >= 5)].copy()
    low_data = candidates[(candidates["matches"] > 0) & (candidates["matches"] <= 2)].copy()
    no_bbb = candidates[(candidates["innings"] > 0) & (candidates["bbb_balls_faced"] <= 0)].copy()
    source_by_reason = {
        "batting-heavy/high average": high_average,
        "low-data edge case": low_data,
        "missing-BBB edge case": no_bbb,
    }

    for reason, column, ascending, limit in top_specs:
        source = source_by_reason.get(reason, candidates)
        if column not in source:
            continue
        source = source.sort_values(column, ascending=ascending, na_position="last")
        for _, row in source.head(limit).iterrows():
            add_player(row, reason)
            if len(selected) >= 50:
                break
        if len(selected) >= 50:
            break

    if len(selected) < 50:
        for _, row in candidates.sort_values(["matches", "runs", "wickets"], ascending=False).iterrows():
            add_player(row, "coverage filler")
            if len(selected) >= 50:
                break

    rows = []
    for player_id, reasons in selected.items():
        rows.append(
            {
                "canonical_player_id": player_id,
                "canonical_player_name": names_by_id.get(player_id, ""),
                "sample_reason": "; ".join(sorted(reasons)),
            }
        )
    sample = pd.DataFrame(rows).sort_values("canonical_player_name").head(50).reset_index(drop=True)
    return sample


def validate_identity(
    sample: pd.DataFrame,
    metrics: pd.DataFrame,
    aliases: pd.DataFrame,
    findings: list[dict[str, object]],
) -> pd.DataFrame:
    alias_counts = defaultdict(int)
    if not aliases.empty and {"canonical_player_id", "is_active"}.issubset(aliases.columns):
        active = aliases[aliases["is_active"].astype(str).str.casefold().isin({"true", "1", "yes", "y"})]
        for player_id, count in active.groupby("canonical_player_id").size().items():
            alias_counts[str(player_id)] = int(count)

    records = []
    metric_by_id = metrics.set_index("canonical_player_id").to_dict("index")
    for row in sample.to_dict("records"):
        player_id = row["canonical_player_id"]
        name = row["canonical_player_name"]
        data = metric_by_id.get(player_id, {})
        if not data:
            add_finding(
                findings,
                severity="Critical",
                category="identity",
                section="profile identity",
                issue="Selected player has no aggregate data",
                detail="The player was selected but no scorecard rows were found.",
                player_id=player_id,
                player_name=name,
            )
        if not str(name).strip() or str(name).strip().lower() == "nan":
            add_finding(
                findings,
                severity="High",
                category="identity",
                section="profile identity",
                issue="Missing display name",
                detail="Canonical player name is blank or invalid.",
                player_id=player_id,
                player_name=name,
            )
        if not data.get("career_span"):
            add_finding(
                findings,
                severity="Medium",
                category="identity",
                section="profile identity",
                issue="Career span missing",
                detail="No season labels were available for this player.",
                player_id=player_id,
                player_name=name,
            )
        if not data.get("grades_played"):
            add_finding(
                findings,
                severity="Medium",
                category="identity",
                section="profile identity",
                issue="Grades played missing",
                detail="No grade labels were available for this player.",
                player_id=player_id,
                player_name=name,
            )
        records.append(
            {
                **row,
                **{k: data.get(k) for k in data.keys()},
                "profile_url": player_url(player_id),
                "active_alias_count": alias_counts.get(str(player_id), 0),
            }
        )
    return pd.DataFrame(records)


def validate_career_overview(player_checks: pd.DataFrame, bbb_career: pd.DataFrame, findings: list[dict[str, object]]) -> None:
    bbb_by_id = bbb_career.set_index("canonical_player_id") if "canonical_player_id" in bbb_career else pd.DataFrame()
    for row in player_checks.to_dict("records"):
        player_id = row["canonical_player_id"]
        name = row["canonical_player_name"]
        expected_avg = safe_div(num(row.get("runs")), num(row.get("outs")))
        if not close_enough(row.get("bat_avg_expected"), expected_avg):
            add_finding(
                findings,
                severity="Critical",
                category="metric logic",
                section="Career Overview",
                issue="Career batting average formula mismatch",
                detail=f"Expected Runs/Outs = {expected_avg}, found {row.get('bat_avg_expected')}.",
                player_id=player_id,
                player_name=name,
                recommended_fix="Ensure career batting average uses runs divided by innings minus not-outs.",
            )
        if not bbb_by_id.empty and player_id in bbb_by_id.index:
            bbb_row = bbb_by_id.loc[player_id]
            if isinstance(bbb_row, pd.DataFrame):
                bbb_row = bbb_row.iloc[0]
            expected_sr = safe_div(num(bbb_row.get("bbb_runs")) * 100, num(bbb_row.get("bbb_balls_faced")))
            actual_sr = maybe_num(bbb_row.get("bat_sr"))
            if expected_sr is not None and not close_enough(actual_sr, expected_sr):
                add_finding(
                    findings,
                    severity="Critical",
                    category="source doctrine",
                    section="Career Overview Strike Rate",
                    issue="Career BBB strike rate formula mismatch",
                    detail=(
                        f"BBB row has {bbb_row.get('bbb_runs')} runs and {bbb_row.get('bbb_balls_faced')} balls; "
                        f"expected {expected_sr:.2f}, found {actual_sr}."
                    ),
                    player_id=player_id,
                    player_name=name,
                    recommended_fix="Use verified BBB runs divided by verified BBB balls only.",
                )
        elif num(row.get("innings")) > 0:
            add_finding(
                findings,
                severity="Low",
                category="data coverage",
                section="Career Overview Strike Rate",
                issue="No verified ball-by-ball batting coverage",
                detail="Career Strike Rate should display N/A for this player until verified BBB batting rows exist.",
                player_id=player_id,
                player_name=name,
            )


def validate_performance_breakdown(sample: pd.DataFrame, performance: pd.DataFrame, findings: list[dict[str, object]]) -> None:
    if performance.empty:
        add_finding(
            findings,
            severity="High",
            category="data source",
            section="Career Breakdown",
            issue="Performance breakdown export missing",
            detail="data/processed/player_profile/performance_breakdown_by_dimension.csv is missing or empty.",
            recommended_fix="Rebuild Player Profile insight exports.",
        )
        return
    for player in sample.to_dict("records"):
        player_id = player["canonical_player_id"]
        name = player["canonical_player_name"]
        rows = scoped_player_rows(performance, player_id, clean_name(name))
        if rows.empty:
            add_finding(
                findings,
                severity="High",
                category="data source",
                section="Career Breakdown",
                issue="No performance breakdown rows",
                detail="The selected player has no rows in the deploy-safe performance breakdown export.",
                player_id=player_id,
                player_name=name,
                recommended_fix="Check canonical identity mapping in Player Profile export builder.",
            )
            continue
        discipline_has_activity = {
            discipline: player_has_performance_discipline(rows, discipline)
            for discipline in ["Batting", "Bowling", "Fielding"]
        }
        for dimension in ["Season", "Grade", "Opponent", "Ground", "Home/Away"]:
            for discipline in ["Batting", "Bowling", "Fielding"]:
                subset = rows[
                    rows["dimension"].astype(str).eq(dimension)
                    & rows["discipline"].astype(str).eq(discipline)
                ]
                if subset.empty and dimension in {"Season", "Grade"} and discipline_has_activity.get(discipline, False):
                    add_finding(
                        findings,
                        severity="Medium",
                        category="data coverage",
                        section=f"Career Breakdown - {dimension}/{discipline}",
                        issue="Expected split is empty",
                        detail=f"No {dimension}/{discipline} rows were available for this selected player.",
                        player_id=player_id,
                        player_name=name,
                    )
        batting = rows[rows["discipline"].astype(str).eq("Batting")].copy()
        for _, row in batting.iterrows():
            label = row.get("breakdown_label")
            runs = num(row.get("runs"))
            innings = num(row.get("innings"))
            outs = num(row.get("outs"))
            actual_avg = maybe_num(row.get("bat_avg"))
            expected_avg = safe_div(runs, outs)
            if expected_avg is None:
                if actual_avg is not None:
                    add_finding(
                        findings,
                        severity="High",
                        category="metric logic",
                        section="Career Breakdown Batting",
                        issue="Not-out-only split should not show finite average",
                        detail=f"{label}: {runs} runs, {innings} innings, {outs} outs, displayed avg {actual_avg}.",
                        player_id=player_id,
                        player_name=name,
                    )
            elif not close_enough(actual_avg, expected_avg):
                denominator = "outs" if outs != innings else "innings"
                severity = "Critical" if outs != innings else "High"
                add_finding(
                    findings,
                    severity=severity,
                    category="metric logic",
                    section="Career Breakdown Batting",
                    issue="Split batting average mismatch",
                    detail=(
                        f"{label}: expected Runs/Outs {runs}/{outs} = {expected_avg:.2f}; "
                        f"display source has {actual_avg}. Denominator currently resembles {denominator}."
                    ),
                    player_id=player_id,
                    player_name=name,
                    recommended_fix="Calculate Bat Avg as runs divided by innings minus not-outs in every split.",
                )
            bbb_balls = maybe_num(row.get("bbb_balls_faced"))
            bbb_runs = maybe_num(row.get("bbb_runs"))
            sr = maybe_num(row.get("strike_rate"))
            if bbb_balls and bbb_balls > 0:
                expected_sr = safe_div((bbb_runs or 0) * 100, bbb_balls)
                if not close_enough(sr, expected_sr):
                    mixed_source = safe_div(runs * 100, bbb_balls)
                    likely_mixed = mixed_source is not None and close_enough(sr, mixed_source) and not close_enough(runs, bbb_runs)
                    add_finding(
                        findings,
                        severity="Critical",
                        category="source doctrine",
                        section="Career Breakdown Strike Rate",
                        issue="Split Strike Rate is not BBB-only",
                        detail=(
                            f"{label}: BBB {bbb_runs} runs/{bbb_balls} balls => {expected_sr:.2f}; "
                            f"found {sr}. Likely mixed scorecard runs/BBB balls: {likely_mixed}."
                        ),
                        player_id=player_id,
                        player_name=name,
                        recommended_fix="Use BBB runs and BBB balls from the same verified innings only.",
                    )
            elif sr is not None and abs(sr) <= 0.0001:
                add_finding(
                    findings,
                    severity="High",
                    category="source doctrine",
                    section="Career Breakdown Strike Rate",
                    issue="Missing BBB coverage appears as zero",
                    detail=f"{label}: BBB balls are missing but Strike Rate is 0.0 instead of N/A.",
                    player_id=player_id,
                    player_name=name,
                    recommended_fix="Render missing verified BBB coverage as N/A.",
                )
            thirties = num(row.get("thirties"))
            hs = high_score_sort_value(row.get("high_score"))
            if hs is not None and 30 <= hs <= 49 and thirties < 1:
                add_finding(
                    findings,
                    severity="Medium",
                    category="metric logic",
                    section="Career Breakdown 30s",
                    issue="High score suggests missing 30s count",
                    detail=f"{label}: HS {row.get('high_score')} but 30s count is {thirties}.",
                    player_id=player_id,
                    player_name=name,
                    recommended_fix="Verify 30s counts from scorecard innings 30-49 inclusive.",
                )
        bowling = rows[rows["discipline"].astype(str).eq("Bowling")].copy()
        for _, row in bowling.iterrows():
            label = row.get("breakdown_label")
            balls = num(row.get("balls_bowled"))
            runs_against = num(row.get("runs_against"))
            wickets = num(row.get("wickets"))
            if wickets > 0:
                if not close_enough(row.get("bowl_avg"), safe_div(runs_against, wickets)):
                    add_finding(
                        findings,
                        severity="High",
                        category="metric logic",
                        section="Career Breakdown Bowling",
                        issue="Bowling average mismatch",
                        detail=f"{label}: expected {runs_against}/{wickets}; found {row.get('bowl_avg')}.",
                        player_id=player_id,
                        player_name=name,
                    )
                if not close_enough(row.get("bowl_sr"), safe_div(balls, wickets)):
                    add_finding(
                        findings,
                        severity="High",
                        category="metric logic",
                        section="Career Breakdown Bowling",
                        issue="Bowling strike rate mismatch",
                        detail=f"{label}: expected {balls}/{wickets}; found {row.get('bowl_sr')}.",
                        player_id=player_id,
                        player_name=name,
                    )
            if balls > 0 and not close_enough(row.get("eco"), safe_div(runs_against * 6, balls)):
                add_finding(
                    findings,
                    severity="High",
                    category="metric logic",
                    section="Career Breakdown Bowling",
                    issue="Economy mismatch",
                    detail=f"{label}: expected runs*6/balls = {safe_div(runs_against * 6, balls)}; found {row.get('eco')}.",
                    player_id=player_id,
                    player_name=name,
                )
            bbi_wickets, _ = parse_bbi(row.get("bbi"))
            if wickets > 0 and bbi_wickets is None:
                add_finding(
                    findings,
                    severity="Medium",
                    category="formatting",
                    section="Career Breakdown Bowling",
                    issue="BBI missing or unparsable",
                    detail=f"{label}: {wickets} wickets but BBI value is {row.get('bbi')!r}.",
                    player_id=player_id,
                    player_name=name,
                )
            if bbi_wickets in {3, 4} and num(row.get("three_wicket_innings")) < 1:
                add_finding(
                    findings,
                    severity="Medium",
                    category="metric logic",
                    section="Career Breakdown 3WI",
                    issue="BBI suggests missing 3WI",
                    detail=f"{label}: BBI {row.get('bbi')} but 3WI count is {row.get('three_wicket_innings')}.",
                    player_id=player_id,
                    player_name=name,
                )
            if bbi_wickets is not None and bbi_wickets >= 5 and num(row.get("five_wicket_innings")) < 1:
                add_finding(
                    findings,
                    severity="Medium",
                    category="metric logic",
                    section="Career Breakdown 5WI",
                    issue="BBI suggests missing 5WI",
                    detail=f"{label}: BBI {row.get('bbi')} but 5WI count is {row.get('five_wicket_innings')}.",
                    player_id=player_id,
                    player_name=name,
                )


def player_has_performance_discipline(rows: pd.DataFrame, discipline: str) -> bool:
    subset = rows[rows.get("discipline", pd.Series(index=rows.index, dtype=object)).astype(str).eq(discipline)].copy()
    if subset.empty:
        return False
    if discipline == "Batting":
        activity_columns = ["innings", "runs", "thirties", "fifties", "hundreds"]
    elif discipline == "Bowling":
        activity_columns = ["balls_bowled", "wickets", "three_wicket_innings", "five_wicket_innings"]
    else:
        activity_columns = ["catches", "stumpings", "run_outs", "dismissals"]
    activity = pd.Series(False, index=subset.index)
    for column in activity_columns:
        if column in subset:
            activity = activity | pd.to_numeric(subset[column], errors="coerce").fillna(0).gt(0)
    return bool(activity.any())


def validate_player_dna(
    sample: pd.DataFrame,
    player_checks: pd.DataFrame,
    batting_position: pd.DataFrame,
    bowling_phase: pd.DataFrame,
    dismissal: pd.DataFrame,
    findings: list[dict[str, object]],
) -> None:
    club_dismissal = dismissal[(
        dismissal.get("scope", pd.Series(dtype=str)).astype(str).str.casefold().eq("club")
        if "scope" in dismissal
        else dismissal.get("canonical_player_id", pd.Series(dtype=str)).astype(str).eq("__club__")
    )]
    if club_dismissal.empty:
        add_finding(
            findings,
            severity="High",
            category="data source",
            section="Dismissal Fingerprint",
            issue="Club dismissal benchmark missing",
            detail="Club-average dismissal rows are required for the grey benchmark marker.",
            recommended_fix="Rebuild dismissal_fingerprint_summary.csv with __club__ benchmark rows.",
        )
    metrics_by_id = player_checks.set_index("canonical_player_id").to_dict("index")
    for player in sample.to_dict("records"):
        player_id = player["canonical_player_id"]
        name = player["canonical_player_name"]
        metrics = metrics_by_id.get(player_id, {})
        pos_rows = scoped_player_rows(batting_position, player_id, clean_name(name))
        if num(metrics.get("innings")) >= 10 and pos_rows.empty:
            add_finding(
                findings,
                severity="Medium",
                category="data coverage",
                section="Player DNA - Batting Position",
                issue="Batting position summary missing",
                detail="Player has meaningful batting innings but no batting-position summary rows.",
                player_id=player_id,
                player_name=name,
            )
        if not pos_rows.empty:
            pos_rows = pos_rows.copy()
            pos_rows["innings"] = pd.to_numeric(pos_rows.get("innings"), errors="coerce").fillna(0)
            pos_rows["average"] = pd.to_numeric(pos_rows.get("average"), errors="coerce")
            qualifying = pos_rows[pos_rows["innings"] >= 4]
            if qualifying.empty:
                add_finding(
                    findings,
                    severity="Info",
                    category="data coverage",
                    section="Player DNA - Batting Position",
                    issue="Best Fit should be withheld",
                    detail="No batting-position group has at least four innings.",
                    player_id=player_id,
                    player_name=name,
                    recommended_fix="UI should show 'Best fit needs 4+ innings in a position.'",
                )
            else:
                expected = qualifying.sort_values(["average", "innings"], ascending=[False, False]).iloc[0]
                if pd.isna(expected.get("average")):
                    add_finding(
                        findings,
                        severity="Medium",
                        category="metric logic",
                        section="Player DNA - Batting Position",
                        issue="Best Fit cannot be selected because qualifying averages are missing",
                        detail="Qualifying batting-position rows exist but average is missing.",
                        player_id=player_id,
                        player_name=name,
                    )
        dis_rows = scoped_player_rows(dismissal, player_id, clean_name(name))
        if num(metrics.get("outs")) > 0 and dis_rows.empty:
            add_finding(
                findings,
                severity="Medium",
                category="data coverage",
                section="Dismissal Fingerprint",
                issue="Dismissal fingerprint missing",
                detail="Player has batting dismissals but no player-level dismissal mix rows.",
                player_id=player_id,
                player_name=name,
            )
        phase_rows = scoped_player_rows(bowling_phase, player_id, clean_name(name))
        is_bowler = num(metrics.get("balls_bowled")) >= 300 and num(metrics.get("wickets")) >= 15
        if is_bowler and phase_rows.empty:
            add_finding(
                findings,
                severity="Low",
                category="data coverage",
                section="Bowling by Phase",
                issue="Verified BBB bowling phase coverage missing for bowler",
                detail="Player qualifies as a bowler but has no verified BBB phase rows.",
                player_id=player_id,
                player_name=name,
                recommended_fix="Show a clean BBB coverage empty state.",
            )
        for _, row in phase_rows.iterrows():
            balls = num(row.get("legal_balls"))
            wickets = num(row.get("wickets"))
            runs = num(row.get("runs_conceded"))
            dots = num(row.get("dot_balls"))
            boundaries = num(row.get("boundary_balls"))
            if wickets > 0:
                if not close_enough(row.get("avg"), safe_div(runs, wickets)):
                    add_finding(
                        findings,
                        severity="High",
                        category="metric logic",
                        section="Bowling by Phase",
                        issue="Phase bowling average mismatch",
                        detail=f"{row.get('phase_model')} {row.get('phase')}: expected {runs}/{wickets}; found {row.get('avg')}.",
                        player_id=player_id,
                        player_name=name,
                    )
                if not close_enough(row.get("sr"), safe_div(balls, wickets)):
                    add_finding(
                        findings,
                        severity="High",
                        category="metric logic",
                        section="Bowling by Phase",
                        issue="Phase bowling strike rate mismatch",
                        detail=f"{row.get('phase_model')} {row.get('phase')}: expected {balls}/{wickets}; found {row.get('sr')}.",
                        player_id=player_id,
                        player_name=name,
                    )
            if balls > 0:
                for column, expected in [
                    ("eco", safe_div(runs * 6, balls)),
                    ("dot_ball_pct", safe_div(dots * 100, balls)),
                    ("boundary_rate", safe_div(boundaries * 100, balls)),
                ]:
                    if not close_enough(row.get(column), expected):
                        add_finding(
                            findings,
                            severity="High",
                            category="source doctrine",
                            section="Bowling by Phase",
                            issue=f"Phase {column} mismatch",
                            detail=f"{row.get('phase_model')} {row.get('phase')}: expected {expected}; found {row.get(column)}.",
                            player_id=player_id,
                            player_name=name,
                        )


def validate_bowling_phase_match_types(
    sample: pd.DataFrame,
    bowling_phase: pd.DataFrame,
    aliases: pd.DataFrame,
    findings: list[dict[str, object]],
) -> pd.DataFrame:
    balls_path = MATCH_CENTRE_DIR / "all_ball_by_ball.csv"
    matches_path = MATCH_CENTRE_DIR / "all_matches.csv"
    bowling_path = MATCH_CENTRE_DIR / "all_scorecard_bowling.csv"
    if not balls_path.exists() or not matches_path.exists() or not bowling_path.exists():
        add_finding(
            findings,
            severity="Info",
            category="test coverage",
            section="Bowling by Phase",
            issue="Match-centre source unavailable for phase match-type audit",
            detail="Deploy-safe phase formulas were checked, but source match-type classification could not be rederived locally.",
        )
        return pd.DataFrame()
    balls = read_csv(balls_path, dtype=str)
    matches = read_csv(matches_path, dtype=str)
    bowling = read_csv(bowling_path, dtype=str)
    if balls.empty or matches.empty or bowling.empty:
        return pd.DataFrame()
    source = balls.merge(matches[["match_id", "match_type"]], on="match_id", how="left")
    source["is_legal_delivery"] = source["is_legal_delivery"].astype(str).str.casefold().isin({"true", "1"})
    alias_map = defaultdict(set)
    if not aliases.empty and {"canonical_player_id", "raw_player_id", "is_active"}.issubset(aliases.columns):
        active_aliases = aliases[
            aliases["is_active"].astype(str).str.casefold().isin({"true", "1", "yes", "y"})
        ].copy()
        for _, row in active_aliases.iterrows():
            canonical_id = str(row.get("canonical_player_id", "")).strip()
            raw_id = str(row.get("raw_player_id", "")).strip()
            if canonical_id and raw_id:
                alias_map[canonical_id].add(raw_id)

    raw_map = defaultdict(set)
    for _, row in bowling.iterrows():
        raw_id = str(row.get("participant_id", "")).strip()
        raw_name = clean_name(row.get("player_name", ""))
        if raw_id:
            raw_map[raw_name].add(raw_id)
    audit_rows = []
    for player in sample.to_dict("records"):
        player_id = player["canonical_player_id"]
        name = player["canonical_player_name"]
        raw_ids = set(alias_map.get(str(player_id), set()))
        if str(player_id).startswith("raw_"):
            raw_ids.add(str(player_id).replace("raw_", "").replace("_", "-"))
        raw_ids |= raw_map.get(clean_name(name), set())
        player_balls = source[source["bowler_participant_id"].astype(str).isin(raw_ids)]
        actual_counts = (
            player_balls[player_balls["is_legal_delivery"]]
            .groupby("match_type", dropna=False)["match_id"]
            .nunique()
            .to_dict()
        )
        phase_rows = scoped_player_rows(bowling_phase, player_id, clean_name(name))
        summary_models = sorted(phase_rows.get("phase_model", pd.Series(dtype=str)).dropna().astype(str).unique())
        audit_rows.append(
            {
                "canonical_player_id": player_id,
                "canonical_player_name": name,
                "actual_bbb_bowling_match_types": "; ".join(f"{k}: {v}" for k, v in sorted(actual_counts.items())),
                "summary_phase_models": " | ".join(summary_models),
                "actual_t20_bbb_bowling_matches": int(actual_counts.get("T20", 0)),
                "actual_one_day_bbb_bowling_matches": int(actual_counts.get("One Day", 0)),
                "actual_two_day_bbb_bowling_matches": int(actual_counts.get("Two Day", 0)),
            }
        )
        if "T20" in summary_models and int(actual_counts.get("T20", 0)) == 0:
            add_finding(
                findings,
                severity="Critical",
                category="source doctrine",
                section="Bowling by Phase",
                issue="T20 phase rows exist without actual T20 BBB bowling matches",
                detail=f"Summary models: {summary_models}; actual source match types: {actual_counts}.",
                player_id=player_id,
                player_name=name,
                recommended_fix="Filter bowling phase rows by actual match_type before applying phase over ranges.",
            )
    return pd.DataFrame(audit_rows)


def validate_static_ui_source(findings: list[dict[str, object]]) -> None:
    layout = (ROOT / "src" / "ui" / "layout.py").read_text(encoding="utf-8")
    theme = (ROOT / "src" / "ui" / "theme.py").read_text(encoding="utf-8")
    old_peer_line = "Line shows range from lowest to highest peer value"
    if old_peer_line in layout:
        add_finding(
            findings,
            severity="Low",
            category="copy",
            section="Player vs Peers",
            issue="Old peer explanatory line still present in source",
            detail=old_peer_line,
            recommended_fix="Remove the old explanatory sentence from Player vs Peers.",
        )
    for phrase in ["Scorecard-safe trends are separated", "Batter intelligence"]:
        if phrase in layout:
            add_finding(
                findings,
                severity="Low",
                category="copy",
                section="Player DNA",
                issue="Old trust/banner phrase still present in source",
                detail=phrase,
                recommended_fix="Keep trust notes subtle and local to relevant cards.",
            )
    for key in [
        "player_profile_breakdown_view_control",
        "player_profile_discipline_view_control",
        "player_profile_phase_model_control",
    ]:
        if key not in theme:
            add_finding(
                findings,
                severity="Medium",
                category="visual",
                section="Player Profile toggles",
                issue="Expected segmented control CSS key missing",
                detail=f"{key} was not found in theme.py.",
                recommended_fix="Scope premium segmented-control styling to this Streamlit widget key.",
            )


def build_report(
    sample: pd.DataFrame,
    player_checks: pd.DataFrame,
    findings: pd.DataFrame,
    phase_audit: pd.DataFrame,
) -> str:
    counts = findings["severity"].value_counts().to_dict() if not findings.empty else {}
    ordered_counts = {severity: int(counts.get(severity, 0)) for severity in SEVERITY_ORDER}
    top_findings = (
        findings.sort_values(["severity_rank", "category", "player_name"])
        .head(20)
        .to_dict("records")
        if not findings.empty
        else []
    )
    lines = [
        "# Player Profile QA Report",
        "",
        "## Executive summary",
        "",
        f"- Players tested: {len(sample)}",
        "- Sections checked: identity/search inputs, Career Overview, Player vs Peers source data, Player DNA, Season Trends source data, Career Breakdown split data, Standout/links source coverage, Milestone source inputs.",
        f"- Findings by severity: Critical {ordered_counts['Critical']}, High {ordered_counts['High']}, Medium {ordered_counts['Medium']}, Low {ordered_counts['Low']}, Info {ordered_counts['Info']}.",
        "- Generated outputs: player_profile_qa_summary.csv, player_profile_qa_findings.csv, player_profile_qa_player_checks.csv, player_profile_qa_report.md.",
        "",
        "## Player sample list",
        "",
    ]
    for index, row in enumerate(sample.to_dict("records"), start=1):
        lines.append(f"{index}. {row['canonical_player_name']} - {row['sample_reason']}")
    lines.extend(["", "## Major bugs found", ""])
    major = findings[findings["severity"].isin(["Critical", "High"])] if not findings.empty else pd.DataFrame()
    if major.empty:
        lines.append("- No Critical or High findings were detected by the static data audit.")
    else:
        for row in major.sort_values(["severity_rank", "category", "player_name"]).head(25).to_dict("records"):
            player = f" ({row['player_name']})" if row.get("player_name") else ""
            lines.append(f"- **{row['severity']} - {row['issue']}**{player}: {row['detail']} Recommended fix: {row.get('recommended_fix') or 'Review source and UI handling.'}")
    lines.extend(["", "## Data logic mismatches", ""])
    categories = [
        ("Bat SR", "Strike Rate is checked against verified BBB runs divided by verified BBB balls. Missing BBB should stay N/A, not zero."),
        ("Bat Avg", "Career Breakdown batting averages are checked as Runs / (Innings - Not Outs)."),
        ("30s", "30s are checked with a high-score heuristic and generated count consistency."),
        ("3WI/5WI", "BBI and milestone counts are checked so 3WI means exactly 3 or 4 wickets and 5WI means 5+."),
        ("BBI", "BBI values are checked for parseable wickets-runs notation when wickets exist."),
        ("Home/Away", "Home/Away split presence is checked from deploy-safe performance breakdown rows."),
        ("Bowling Phase", "Phase averages, economy, strike rate, dot-ball percentage, and boundary rate are checked from BBB-only phase summary rows. Match-type source rows are rechecked when local match-centre processed data is present."),
        ("Dismissal Fingerprint", "Player dismissal rows and club-average rows are checked; exact marker CSS still requires visual review."),
    ]
    for label, detail in categories:
        subset = findings[findings["section"].astype(str).str.contains(label.split("/")[0], case=False, na=False)] if not findings.empty else pd.DataFrame()
        lines.append(f"- **{label}:** {detail} Findings: {len(subset)}.")
    lines.extend(["", "## Visual/UI gaps", ""])
    lines.extend(
        [
            "- The script validates source data and static source strings; it cannot fully prove browser-only CSS details such as exact marker shape, table wrapping, or chart clipping.",
            "- Browser spot checks should focus on the same selected players listed in player_profile_qa_summary.csv, especially high-data players and low-data edge cases.",
            "- Toggle behavior is expected to remain session-state based; verify manually that changing Career Breakdown controls does not alter the URL.",
        ]
    )
    lines.extend(["", "## Future risks", ""])
    lines.extend(
        [
            "- Player Profile deploy-safe summaries can go stale if scripts/build_player_profile_insight_exports.py is not run after match-centre data refresh.",
            "- Canonical player mapping drift can split profiles for merge-sensitive names.",
            "- Opponent and ground normalization improvements should be rerun through the performance breakdown export before release.",
            "- BBB coverage gaps are expected; missing coverage must remain N/A rather than 0.0.",
            "- Bowling phase depends on reliable match_type classification before phase over ranges are applied.",
        ]
    )
    lines.extend(["", "## Recommended next actions", ""])
    if top_findings:
        for row in top_findings[:10]:
            player = f" - {row['player_name']}" if row.get("player_name") else ""
            lines.append(f"- {row['severity']}: {row['issue']}{player}. {row.get('recommended_fix') or 'Review.'}")
    else:
        lines.append("- No findings generated; add permanent pytest coverage for formulas before future refactors.")
    lines.extend(["", "## Optional permanent tests to add", ""])
    lines.extend(
        [
            "- tests/test_player_profile_metrics.py::test_batting_average_uses_outs",
            "- tests/test_player_profile_metrics.py::test_bbb_strike_rate_uses_bbb_runs_and_balls",
            "- tests/test_player_profile_metrics.py::test_missing_bbb_is_na_not_zero",
            "- tests/test_player_profile_metrics.py::test_thirties_are_30_to_49_inclusive",
            "- tests/test_player_profile_metrics.py::test_three_wicket_innings_excludes_five_wicket_hauls",
            "- tests/test_player_profile_metrics.py::test_bbi_parses_wickets_then_runs",
            "- tests/test_player_profile_metrics.py::test_bowling_phase_respects_match_type",
            "- tests/test_player_profile_metrics.py::test_known_aliases_resolve_to_one_canonical_profile",
        ]
    )
    if not phase_audit.empty:
        lines.extend(["", "## Bowling phase source match-type audit", ""])
        for row in phase_audit.head(20).to_dict("records"):
            lines.append(f"- {row['canonical_player_name']}: source types [{row['actual_bbb_bowling_match_types']}], summary models [{row['summary_phase_models']}].")
    return "\n".join(lines) + "\n"


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    batting = read_csv(PROCESSED / "all_seasons_batting.csv")
    bowling = read_csv(PROCESSED / "all_seasons_bowling.csv")
    fielding = read_csv(PROCESSED / "all_seasons_fielding.csv")
    aliases = read_csv(ROOT / "data" / "player_aliases.csv", dtype=str)
    bbb_career = read_csv(HOF_DIR / "player_bbb_batting_rates.csv")
    performance = read_csv(PLAYER_PROFILE_DIR / "performance_breakdown_by_dimension.csv")
    batting_position = read_csv(PLAYER_PROFILE_DIR / "batting_position_summary.csv")
    bowling_phase = read_csv(PLAYER_PROFILE_DIR / "bowling_phase_summary.csv")
    dismissal = read_csv(PLAYER_PROFILE_DIR / "dismissal_fingerprint_summary.csv")

    findings: list[dict[str, object]] = []
    players = canonical_player_frame([batting, bowling, fielding])
    metrics = aggregate_player_metrics(players, batting, bowling, fielding, bbb_career)
    sample = select_audit_players(metrics, findings)
    player_checks = validate_identity(sample, metrics, aliases, findings)
    validate_career_overview(player_checks, bbb_career, findings)
    validate_performance_breakdown(sample, performance, findings)
    validate_player_dna(sample, player_checks, batting_position, bowling_phase, dismissal, findings)
    phase_audit = validate_bowling_phase_match_types(sample, bowling_phase, aliases, findings)
    validate_static_ui_source(findings)

    findings_df = pd.DataFrame(findings)
    if findings_df.empty:
        findings_df = pd.DataFrame(
            columns=["severity", "category", "section", "issue", "detail", "player_id", "player_name", "recommended_fix"]
        )
    findings_df["severity_rank"] = findings_df["severity"].map(SEVERITY_ORDER).fillna(99).astype(int)
    findings_df = findings_df.sort_values(["severity_rank", "category", "section", "player_name", "issue"]).reset_index(drop=True)

    summary = pd.DataFrame(
        [
            {
                "players_tested": len(sample),
                "critical_findings": int((findings_df["severity"] == "Critical").sum()),
                "high_findings": int((findings_df["severity"] == "High").sum()),
                "medium_findings": int((findings_df["severity"] == "Medium").sum()),
                "low_findings": int((findings_df["severity"] == "Low").sum()),
                "info_findings": int((findings_df["severity"] == "Info").sum()),
                "performance_rows_checked": int(len(performance)),
                "batting_position_rows": int(len(batting_position)),
                "bowling_phase_rows": int(len(bowling_phase)),
                "dismissal_fingerprint_rows": int(len(dismissal)),
            }
        ]
    )

    sample.to_csv(OUTPUT_DIR / "player_profile_qa_sample_players.csv", index=False)
    summary.to_csv(OUTPUT_DIR / "player_profile_qa_summary.csv", index=False)
    findings_df.to_csv(OUTPUT_DIR / "player_profile_qa_findings.csv", index=False)
    player_checks.to_csv(OUTPUT_DIR / "player_profile_qa_player_checks.csv", index=False)
    if not phase_audit.empty:
        phase_audit.to_csv(OUTPUT_DIR / "player_profile_qa_bowling_phase_source_audit.csv", index=False)

    report = build_report(sample, player_checks, findings_df, phase_audit)
    (OUTPUT_DIR / "player_profile_qa_report.md").write_text(report, encoding="utf-8")

    print("Player Profile QA audit complete")
    print(f"Players tested: {len(sample)}")
    print(summary.to_string(index=False))
    print(f"Report: {OUTPUT_DIR / 'player_profile_qa_report.md'}")


if __name__ == "__main__":
    main()
