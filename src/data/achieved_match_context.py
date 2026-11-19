"""Reconcile approved season milestones to their exact scorecard match grain."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pandas as pd
import streamlit as st

from src.config.club_config import get_processed_path
from src.data.grdcc_profile_bundle import file_stamp
from src.utils.player_identity import filter_public_player_rows


FILES = {
    "matches": "all_seasons_matches.csv",
    "batting": "all_seasons_scorecard_batting.csv",
    "bowling": "all_seasons_scorecard_bowling.csv",
    "fielding": "all_seasons_scorecard_fielding.csv",
    "rounds": "season_overview/season_by_round_scorecards.csv",
    "playing_dates": "season_overview/match_playing_dates.json",
    "verified_dates": "milestones/verified_final_playing_dates.json",
}
METRICS = {"batting": ("Runs", "runs"), "bowling": ("Wickets", "wickets"), "fielding": ("Catches", "catches")}


def resolve_crossing(matches: pd.DataFrame, expected: float, starting: float, threshold: float):
    """Require complete seasonal reconciliation and an unambiguous match order."""
    if matches.empty:
        return None, "No exact-ID match evidence"
    if matches.match_id.duplicated().any() or matches.match_id.astype(str).str.strip().eq("").any():
        return None, "Ambiguous match identity"
    values = pd.to_numeric(matches.contribution, errors="coerce")
    if values.isna().any() or not values.map(math.isfinite).all() or values.lt(0).any():
        return None, "Incomplete match figures"
    if not math.isclose(float(values.sum()), expected, rel_tol=0, abs_tol=1e-8):
        return None, "Source totals do not reconcile to the approved season contribution"
    if not 0 <= starting < threshold <= starting + expected:
        return None, "Approved starting total does not establish this crossing"
    active = matches.assign(contribution=values).loc[values.gt(0)].copy()
    if "first_verified_appearance" in active:
        # Appearance is earned on the first verified day of participation.
        # Unverified entries keep their entire match window for overlap checks.
        actual = active["first_verified_appearance"]
        active["start"] = actual.fillna(active["start"])
        active["end"] = actual.fillna(active["end"])
    if active[["start", "end"]].isna().any().any():
        return None, "Missing playing date"
    active = active.sort_values(["start", "end", "match_id"]).reset_index(drop=True)
    reach = active.index[(starting + active.contribution.cumsum()).ge(threshold)][0]
    crossing = active.iloc[reach]
    if (
        active.iloc[:reach].end.ge(crossing.start).any()
        or active.iloc[reach + 1:].start.le(crossing.end).any()
    ):
        return None, "Playing dates overlap at the threshold"
    return crossing, "Verified exact match"


def source_signature(club: str) -> tuple:
    return tuple(file_stamp(get_processed_path(file, club_id=club)) for file in FILES.values())


def clean(value) -> str:
    return "" if pd.isna(value) else str(value).strip()


def match_date(value):
    date = pd.to_datetime(value, errors="coerce")
    if pd.isna(date):
        return pd.NaT
    if date.tzinfo is not None:
        date = date.tz_convert("Australia/Melbourne").tz_localize(None)
    return date.normalize()


def read_selected(path: Path, seasons: tuple[str, ...]) -> pd.DataFrame:
    if not path.is_file():
        return pd.DataFrame()
    frames = []
    for chunk in pd.read_csv(path, chunksize=24000, dtype={"match_id": str, "player_id": str}, low_memory=False):
        if "season" not in chunk:
            return pd.DataFrame()
        frames.append(chunk.loc[chunk.season.isin(seasons)])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


@st.cache_data(show_spinner=False, max_entries=6)
def load_match_evidence(club: str, seasons: tuple[str, ...], signature: tuple):
    """Read only the released club exports and retain the selected season rows."""
    frames = {
        kind: read_selected(get_processed_path(path, club_id=club), seasons)
        for kind, path in FILES.items() if kind not in {"playing_dates", "verified_dates"}
    }
    date_path = get_processed_path(FILES["playing_dates"], club_id=club)
    dates = {}
    if club == "georges-river-district" and date_path.is_file():
        from src.ui.grdcc_presentation import load_playing_date_index
        dates = load_playing_date_index(str(date_path), date_path.stat().st_mtime_ns)
    verified = get_processed_path(FILES["verified_dates"], club_id=club)
    frames["verified_dates"] = json.loads(verified.read_text()) if verified.is_file() else {}
    return frames, dates


def match_context(frames: dict, playing_dates: dict, club: str) -> pd.DataFrame:
    rounds = frames["rounds"]
    if rounds.empty:
        return pd.DataFrame()
    rounds = rounds.drop_duplicates()
    rounds = rounds.loc[~rounds.duplicated(["season", "match_id"], keep=False)].copy()
    rounds["weight"] = 1.0
    if club == "glen-waverley-hawks":
        from src.data.gwhcc_match_policy import match_format
        matches = frames["matches"].drop_duplicates()
        if not {"season", "match_id"}.issubset(matches):
            return pd.DataFrame()
        matches = matches.loc[~matches.duplicated(["season", "match_id"], keep=False)].copy()
        matches["weight"] = matches.apply(lambda row: 0.5 if match_format(row) == "T20" else 1.0, axis=1)
        rounds = rounds.drop(columns="weight").merge(
            matches[["season", "match_id", "weight"]], on=["season", "match_id"], how="left", validate="one_to_one",
        )
    rows = []
    for row in rounds.itertuples(index=False):
        match_id = clean(row.match_id)
        start = match_date(row.match_date)
        verified = frames.get("verified_dates", {}).get(match_id, {})
        scheduled_values = verified.get("scheduled_dates") or playing_dates.get(match_id, ())
        scheduled = sorted({day for value in scheduled_values if pd.notna(day := match_date(value))})
        if scheduled:
            start, end = scheduled[0], scheduled[-1]
        else:
            end = start
        actual = match_date(verified.get("date"))
        if pd.notna(actual) and (not scheduled or actual in scheduled):
            end = actual
            text = f"{actual.day} {actual:%b %Y}"
        elif pd.notna(start):
            text = f"Final playing date unavailable (scheduled start {start.day} {start:%b %Y})"
        else:
            text = "Final playing date unavailable"
        rows.append({"season": row.season, "match_id": match_id, "start": start, "end": end,
                     "match_date_label": text, "round": clean(row.round_display),
                     "opponent": clean(row.opponent_name), "weight": row.weight})
    return pd.DataFrame(rows)


def exact_season_identity(historical: dict, seasons: tuple[str, ...], club: str) -> pd.DataFrame:
    key = ["season", "raw_player_id", "canonical_player_id"]
    frames = []
    for kind in METRICS:
        data = historical.get(kind + "_raw", pd.DataFrame())
        if set(key).issubset(data):
            public = filter_public_player_rows(data.loc[data.season.isin(seasons)].copy(), club_id=club)
            frames.append(public[key])
    if not frames:
        return pd.DataFrame(columns=key)
    exact = pd.concat(frames, ignore_index=True).dropna().astype(str)
    exact = exact.loc[exact.raw_player_id.ne("") & exact.canonical_player_id.ne("")].drop_duplicates()
    return exact.loc[~exact.duplicated(["season", "raw_player_id"], keep=False)]


def contributions(frames: dict, exact: pd.DataFrame, context: pd.DataFrame) -> dict[str, pd.DataFrame]:
    if exact.empty or context.empty:
        return {}
    grain = ["season", "match_id", "canonical_player_id"]
    players = []
    grouped = {}
    batting_lines = pd.DataFrame()
    for kind, (category, metric) in METRICS.items():
        frame = frames[kind]
        if not {"season", "match_id", "player_id", metric}.issubset(frame):
            continue
        allowed = frame.merge(exact, left_on=["season", "player_id"], right_on=["season", "raw_player_id"],
                              how="inner", validate="many_to_one")
        players.append(allowed[grain])
        if kind == "batting":
            batting_lines = allowed
        allowed["contribution"] = pd.to_numeric(allowed[metric], errors="coerce")
        # The released line items can contain multiple innings; reconcile their
        # sum at match grain and retain any missing figure as unknown.
        grouped[category] = allowed.groupby(grain, as_index=False).agg(
            contribution=("contribution", lambda v: v.sum() if v.notna().all() else float("nan")),
        )
        if kind == "bowling" and "runs_conceded" in allowed:
            allowed["conceded"] = pd.to_numeric(allowed.runs_conceded, errors="coerce")
            sums = allowed.groupby(grain, as_index=False).agg(
                conceded=("conceded", lambda v: v.sum() if v.notna().all() else float("nan")),
            )
            grouped[category] = grouped[category].merge(sums, on=grain, validate="one_to_one")
    if players:
        appearances = pd.concat(players, ignore_index=True).drop_duplicates()
        grouped["Matches"] = appearances.merge(
            context[["season", "match_id", "weight"]], on=["season", "match_id"], how="left", validate="many_to_one",
        ).rename(columns={"weight": "contribution"})
        if not batting_lines.empty:
            scores = batting_lines.groupby(grain, sort=False).apply(appearance_batting_performance, include_groups=False)
            grouped["Matches"] = grouped["Matches"].merge(
                scores.rename("batting_performance").reset_index(), on=grain, how="left", validate="one_to_one",
            )
    output = {
        kind: frame.merge(context, on=["season", "match_id"], how="inner", validate="many_to_one")
        for kind, frame in grouped.items()
    }
    if "Matches" in output:
        appearances = output["Matches"]
        verified = frames.get("verified_dates", {})
        appearances["first_verified_appearance"] = [
            match_date(verified.get(match, {}).get("first_verified_appearances", {}).get(player))
            for match, player in zip(appearances["match_id"], appearances["canonical_player_id"])
        ]
        day = appearances["first_verified_appearance"]
        appearances["first_verified_appearance"] = day.where(day.between(appearances["start"], appearances["end"]))
    return output


def appearance_batting_performance(rows: pd.DataFrame) -> str:
    dismissals = rows.get("dismissal", pd.Series("", index=rows.index)).fillna("").astype(str).str.strip().str.casefold()
    did_not_bat = dismissals.isin({"did not bat", "dnb"})
    if did_not_bat.all():
        return "Did not bat"
    innings = rows.loc[~did_not_bat]
    runs = pd.to_numeric(innings["runs"], errors="coerce")
    if runs.isna().any():
        return "Batting performance unavailable"
    balls = pd.to_numeric(innings.get("balls", pd.Series(float("nan"), index=innings.index)), errors="coerce")
    scored = int(runs.sum())
    if balls.isna().any():
        return f"{scored} runs (balls faced unavailable)"
    faced = int(balls.sum())
    return f"{scored} {'run' if scored == 1 else 'runs'} from {faced} {'ball' if faced == 1 else 'balls'}"


def season_start_total(career: pd.Series, selected: pd.DataFrame, season: str, metric: str, season_key):
    if selected.empty or selected.duplicated("season").any() or season not in set(selected.season):
        return None
    expected = float(selected.loc[selected.season.eq(season), metric].iloc[0])
    carry = selected.loc[selected.season.map(season_key).ge(season_key(season)), metric]
    starting = float(career[metric]) - float(carry.sum())
    if metric == "Matches" and str(career.get("historical_match_anchor_applied", "")).casefold() in {"true", "1"}:
        anchor_season = clean(career.get("historical_match_anchor_through_season"))
        if not anchor_season or season_key(season) <= season_key(anchor_season):
            return None
    return starting, expected


def performance(category: str, crossing: pd.Series) -> str:
    value = float(crossing.contribution)
    if category == "Matches":
        batting = clean(crossing.get("batting_performance")) or "Batting performance unavailable"
        return f"Appearance weight {value:g} · {batting}"
    if category == "Wickets" and pd.notna(crossing.get("conceded")):
        return f"Player bowling: {int(value)} wickets for {int(crossing.conceded)} runs"
    return f"Player {category.casefold()}: {value:g}"


def enrich_achieved_matches(achieved, historical, season_totals, seasons, club, season_key, signature):
    if achieved.empty:
        return achieved
    output = achieved.copy()
    output["Match Evidence"] = "Exact match unavailable"
    frames, dates = load_match_evidence(club, tuple(seasons), signature)
    context = match_context(frames, dates, club)
    exact = exact_season_identity(historical, tuple(seasons), club)
    sources = contributions(frames, exact, context)
    all_time = historical["all_time"]
    for index, row in output.iterrows():
        category, season, pid = row["Category"], row["Season"], row["canonical_player_id"]
        career = all_time.loc[all_time.canonical_player_id.eq(pid)]
        if len(career) != 1 or season_totals.empty or "canonical_player_id" not in season_totals:
            continue
        selected = season_totals.loc[season_totals.canonical_player_id.eq(pid)]
        try:
            reconciliation = season_start_total(career.iloc[0], selected, season, category, season_key)
        except (KeyError, TypeError, ValueError):
            reconciliation = None
        if reconciliation is None:
            continue
        found = sources.get(category, pd.DataFrame())
        if found.empty:
            continue
        found = found.loc[found.season.eq(season) & found.canonical_player_id.eq(pid)]
        crossing, reason = resolve_crossing(found, reconciliation[1], reconciliation[0], float(row["Threshold"]))
        output.at[index, "Match Evidence"] = reason
        if crossing is not None:
            for field in ("match_id", "match_date_label", "round", "opponent"):
                output.at[index, field] = crossing[field]
            output.at[index, "match_performance"] = performance(category, crossing)
    return output
