#!/usr/bin/env python3
"""Build GRDCC Historical Excel supplements for Annual Report override players."""

from __future__ import annotations

import math
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.featured_record_overrides import normalize_featured_player_name  # noqa: E402


OVERRIDES = ROOT / "clubs/georges-river-district/data/processed/validation/annual_report_2024_25/all_time_overrides/grdcc_all_time_override_decisions.csv"
EXCEL_BATTING = ROOT / "clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_batting.csv"
EXCEL_BOWLING = ROOT / "clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_bowling.csv"
OUTPUT = ROOT / "clubs/georges-river-district/data/processed/validation/annual_report_2024_25/all_time_overrides/grdcc_override_player_excel_supplements.csv"


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str).fillna("")


def number(value: object) -> float | None:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def season_key(value: object) -> int:
    text = str(value or "").strip()
    match = pd.Series([text]).str.extract(r"((?:19|20)\d{2})", expand=False).iloc[0]
    if not match:
        return 999999
    year = int(match)
    return year * 10 + (1 if "winter" in text.casefold() else 2)


def display_name(row: pd.Series) -> str:
    for column in ["canonical_player_name", "player_name", "short_name", "raw_player_name"]:
        text = str(row.get(column, "") or "").strip()
        if text:
            return text
    return ""


def initial_surname_key(value: object) -> str:
    text = normalize_featured_player_name(value)
    parts = text.split()
    if len(parts) < 2:
        return text
    return f"{parts[0][:1]} {parts[-1]}"


def row_name_variants(row: pd.Series) -> set[str]:
    names = set()
    for column in ["canonical_player_name", "player_name", "short_name", "raw_player_name"]:
        text = str(row.get(column, "") or "").strip()
        if not text:
            continue
        names.add(normalize_featured_player_name(text))
        names.add(initial_surname_key(text))
    return {name for name in names if name}


def match_rows(frame: pd.DataFrame, player_name: str, normalized_name: str) -> tuple[pd.DataFrame, str, str]:
    if frame.empty:
        return frame.copy(), "", "low"
    target_initial = initial_surname_key(player_name)
    exact_mask = frame["_name_variants"].map(lambda values: normalized_name in values)
    initial_mask = frame["_name_variants"].map(lambda values: target_initial in values)
    exact_rows = frame[exact_mask].copy()
    initial_rows = frame[initial_mask].copy()
    if not exact_rows.empty:
        combined_rows = frame.loc[exact_rows.index.union(initial_rows.index)].copy()
        aliases = sorted({display_name(row) for _, row in combined_rows.iterrows() if display_name(row)})
        return combined_rows, "; ".join(aliases), "high"
    aliases = sorted({display_name(row) for _, row in initial_rows.iterrows() if display_name(row)})
    return initial_rows, "; ".join(aliases), ("medium" if not initial_rows.empty else "low")


def prepare_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    output = frame.copy()
    output["_name_variants"] = output.apply(row_name_variants, axis=1)
    output["_season_key"] = output["season"].map(season_key) if "season" in output else 999999
    return output


def build_season_context(batting: pd.DataFrame, bowling: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    season_total_matches: dict[str, float] = {}
    season_max_innings: dict[str, float] = {}
    for frame in [batting, bowling]:
        if frame.empty or "season" not in frame:
            continue
        if "matches" in frame:
            matches = pd.to_numeric(frame["matches"], errors="coerce")
            grouped = frame.assign(_matches=matches).groupby("season")["_matches"].max()
            for season, value in grouped.items():
                if pd.notna(value):
                    season_total_matches[season] = max(season_total_matches.get(season, 0.0), float(value))
    if not batting.empty and "season" in batting and "battingInnings" in batting:
        innings = pd.to_numeric(batting["battingInnings"], errors="coerce")
        grouped = batting.assign(_innings=innings).groupby("season")["_innings"].max()
        for season, value in grouped.items():
            if pd.notna(value):
                season_max_innings[season] = max(season_max_innings.get(season, 0.0), float(value))
    return season_total_matches, season_max_innings


def aggregate_player(player_name: str, normalized_name: str, batting_rows: pd.DataFrame, bowling_rows: pd.DataFrame, season_total_matches: dict[str, float], season_max_innings: dict[str, float], decisions: pd.DataFrame) -> dict[str, object]:
    batting_rows = batting_rows.copy()
    bowling_rows = bowling_rows.copy()
    seasons = sorted(
        set(batting_rows.get("season", pd.Series(dtype=str)).astype(str)).union(
            set(bowling_rows.get("season", pd.Series(dtype=str)).astype(str))
        ),
        key=season_key,
    )
    matches_total = 0
    matches_source = ""
    proxy_count = 0
    for season in seasons:
        bat = batting_rows[batting_rows["season"].astype(str) == season] if not batting_rows.empty else batting_rows
        bowl = bowling_rows[bowling_rows["season"].astype(str) == season] if not bowling_rows.empty else bowling_rows
        explicit = []
        for frame in [bat, bowl]:
            if not frame.empty and "matches" in frame:
                values = pd.to_numeric(frame["matches"], errors="coerce").dropna()
                if not values.empty:
                    explicit.append(float(values.max()))
        if explicit:
            matches_total += int(max(explicit))
            matches_source = "explicit_matches"
            continue
        if bat.empty or "battingInnings" not in bat:
            continue
        innings = pd.to_numeric(bat["battingInnings"], errors="coerce").fillna(0).sum()
        total_matches = season_total_matches.get(season, 0.0)
        max_innings = season_max_innings.get(season, 0.0)
        if innings > 0 and total_matches > 0 and max_innings > 0:
            estimated = min(int(total_matches), max(1, math.floor(float(innings) * float(total_matches) / float(max_innings))))
            matches_total += estimated
            proxy_count += 1
            matches_source = "innings_proxy"

    innings_total = pd.to_numeric(batting_rows.get("battingInnings"), errors="coerce").fillna(0).sum()
    not_outs_total = pd.to_numeric(batting_rows.get("battingNotOuts"), errors="coerce").fillna(0).sum()
    runs_total = pd.to_numeric(batting_rows.get("battingAggregate"), errors="coerce").fillna(0).sum()
    hs_values = pd.to_numeric(batting_rows.get("battingHighScore"), errors="coerce").dropna()
    hs_total = int(hs_values.max()) if not hs_values.empty else ""
    outs = max(float(innings_total) - float(not_outs_total), 0.0)
    batting_average = round(float(runs_total) / outs, 2) if outs > 0 else ""

    explicit_fifties = batting_rows.get("batting50s", pd.Series(dtype=object))
    explicit_hundreds = batting_rows.get("batting100s", pd.Series(dtype=object))
    explicit_counts_available = (
        explicit_fifties.astype(str).str.strip().ne("").any()
        or explicit_hundreds.astype(str).str.strip().ne("").any()
    )
    if explicit_counts_available:
        fifties = int(pd.to_numeric(explicit_fifties, errors="coerce").fillna(0).sum())
        hundreds = int(pd.to_numeric(explicit_hundreds, errors="coerce").fillna(0).sum())
        fh_source = "explicit_excel"
    else:
        fifties = 0
        hundreds = 0
        season_hs = (
            batting_rows.assign(_hs=pd.to_numeric(batting_rows.get("battingHighScore"), errors="coerce"))
            .groupby("season")["_hs"]
            .max()
        )
        for value in season_hs.dropna():
            if float(value) >= 100:
                hundreds += 1
            elif float(value) >= 50:
                fifties += 1
        fh_source = "derived_minimum_from_hs" if seasons else ""

    wickets_total = pd.to_numeric(bowling_rows.get("bowlingWickets"), errors="coerce").fillna(0).sum()
    balls_total = pd.to_numeric(bowling_rows.get("bowlingBalls"), errors="coerce").fillna(0).sum()
    maidens_total = pd.to_numeric(bowling_rows.get("bowlingMaidens"), errors="coerce").fillna(0).sum()
    runs_conceded_total = pd.to_numeric(bowling_rows.get("bowlingRuns"), errors="coerce").fillna(0).sum()
    bowl_avg = round(float(runs_conceded_total) / float(wickets_total), 2) if wickets_total > 0 else ""
    bowl_sr = round(float(balls_total) / float(wickets_total), 2) if wickets_total > 0 and balls_total > 0 else ""
    overs_total = round(float(balls_total) / 6.0, 1) if balls_total > 0 else ""

    player_decisions = decisions[decisions["normalized_player_name"].eq(normalized_name)].copy()
    displayed_runs = pd.to_numeric(
        player_decisions[player_decisions["metric"].eq("career_runs")]["displayed_value"],
        errors="coerce",
    ).dropna()
    displayed_wickets = pd.to_numeric(
        player_decisions[player_decisions["metric"].eq("career_wickets")]["displayed_value"],
        errors="coerce",
    ).dropna()

    return {
        "excel_seasons": ", ".join(seasons),
        "excel_seasons_count": len(seasons) if seasons else "",
        "excel_matches": matches_total if matches_total else "",
        "matches_source": matches_source,
        "excel_innings": int(innings_total) if innings_total else "",
        "excel_not_outs": int(not_outs_total) if not_outs_total else "",
        "excel_runs": int(runs_total) if runs_total else "",
        "displayed_career_runs": int(displayed_runs.max()) if not displayed_runs.empty else (int(runs_total) if runs_total else ""),
        "excel_hs": hs_total,
        "excel_batting_average": batting_average,
        "excel_50s": fifties if fifties else "",
        "excel_100s": hundreds if hundreds else "",
        "fifties_hundreds_source": fh_source,
        "excel_wickets": int(wickets_total) if wickets_total else "",
        "displayed_career_wickets": int(displayed_wickets.max()) if not displayed_wickets.empty else (int(wickets_total) if wickets_total else ""),
        "excel_overs": overs_total,
        "excel_balls": int(balls_total) if balls_total else "",
        "excel_maidens": int(maidens_total) if maidens_total else "",
        "excel_bowling_runs_conceded": int(runs_conceded_total) if runs_conceded_total else "",
        "excel_bowling_average": bowl_avg,
        "excel_bowling_strike_rate": bowl_sr,
        "proxy_count": proxy_count,
    }


def build_output() -> pd.DataFrame:
    decisions = read_csv(OVERRIDES)
    batting = prepare_frame(read_csv(EXCEL_BATTING))
    bowling = prepare_frame(read_csv(EXCEL_BOWLING))
    season_total_matches, season_max_innings = build_season_context(batting, bowling)

    player_cache: dict[str, dict[str, object]] = {}
    for normalized_name, rows in decisions.groupby("normalized_player_name", sort=False):
        player_name = str(rows["player_name"].iloc[0])
        matched_batting, batting_aliases, batting_confidence = match_rows(batting, player_name, normalized_name)
        matched_bowling, bowling_aliases, bowling_confidence = match_rows(bowling, player_name, normalized_name)
        aliases = "; ".join(sorted({alias for alias in [batting_aliases, bowling_aliases] if alias}))
        confidence = "high" if "high" in {batting_confidence, bowling_confidence} else ("medium" if "medium" in {batting_confidence, bowling_confidence} else "low")
        aggregate = aggregate_player(
            player_name,
            normalized_name,
            matched_batting,
            matched_bowling,
            season_total_matches,
            season_max_innings,
            decisions,
        )
        notes = []
        if aggregate["matches_source"] == "innings_proxy":
            notes.append(f"matches proxy used for {aggregate['proxy_count']} season(s)")
        if aggregate["fifties_hundreds_source"] == "derived_minimum_from_hs":
            notes.append("50s/100s are conservative minimums derived from season HS")
        player_cache[normalized_name] = {
            "player_name": player_name,
            "excel_aliases_used": aliases,
            "source_confidence": confidence,
            "notes": "; ".join(notes),
            **aggregate,
        }

    rows_out: list[dict[str, object]] = []
    for _, row in decisions.iterrows():
        normalized_name = str(row["normalized_player_name"])
        supplement = player_cache.get(normalized_name, {})
        rows_out.append(
            {
                "player_name": str(row["player_name"]),
                "normalized_player_name": normalized_name,
                "override_metric": str(row["metric"]),
                "override_value": str(row["annual_report_combined_value"]),
                "source_rule_derived_value": str(row["source_rule_derived_value"]),
                "override_applies": str(row["override_applies"]),
                "excel_aliases_used": supplement.get("excel_aliases_used", ""),
                "excel_seasons": supplement.get("excel_seasons", ""),
                "excel_seasons_count": supplement.get("excel_seasons_count", ""),
                "excel_matches": supplement.get("excel_matches", ""),
                "matches_source": supplement.get("matches_source", ""),
                "excel_innings": supplement.get("excel_innings", ""),
                "excel_not_outs": supplement.get("excel_not_outs", ""),
                "excel_runs": supplement.get("excel_runs", ""),
                "displayed_career_runs": supplement.get("displayed_career_runs", ""),
                "excel_hs": supplement.get("excel_hs", ""),
                "excel_batting_average": supplement.get("excel_batting_average", ""),
                "excel_50s": supplement.get("excel_50s", ""),
                "excel_100s": supplement.get("excel_100s", ""),
                "fifties_hundreds_source": supplement.get("fifties_hundreds_source", ""),
                "excel_wickets": supplement.get("excel_wickets", ""),
                "displayed_career_wickets": supplement.get("displayed_career_wickets", ""),
                "excel_overs": supplement.get("excel_overs", ""),
                "excel_balls": supplement.get("excel_balls", ""),
                "excel_maidens": supplement.get("excel_maidens", ""),
                "excel_bowling_runs_conceded": supplement.get("excel_bowling_runs_conceded", ""),
                "excel_bowling_average": supplement.get("excel_bowling_average", ""),
                "excel_bowling_strike_rate": supplement.get("excel_bowling_strike_rate", ""),
                "source_confidence": supplement.get("source_confidence", ""),
                "notes": supplement.get("notes", ""),
            }
        )
    return pd.DataFrame(rows_out)


def main() -> int:
    output = build_output()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(OUTPUT, index=False)
    unique_players = output["normalized_player_name"].nunique() if not output.empty else 0
    proxy_count = int((output["matches_source"] == "innings_proxy").sum())
    hs_derived = int((output["fifties_hundreds_source"] == "derived_minimum_from_hs").sum())
    print(f"rows={len(output)} players={unique_players} matches_proxy_rows={proxy_count} hs_derived_rows={hs_derived}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
