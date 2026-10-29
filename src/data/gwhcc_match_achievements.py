"""Evidence-qualified Hawks match milestones; career totals do not invent dates."""

from __future__ import annotations

import math
import re

import pandas as pd

from src.data.gwhcc_historical_career import CLUB_ID, MATCH_MILESTONES, season_start
from src.utils.player_identity import is_private_or_anonymised_player


def load_match_milestone_seasons() -> pd.DataFrame:
    if not MATCH_MILESTONES.exists():
        return pd.DataFrame()
    rows = pd.read_csv(MATCH_MILESTONES, keep_default_na=False)
    controlled_ids = set(rows.canonical_player_id.astype(str)) - {""}
    rows = rows[rows.decision_status.eq("approved_source_season") & rows.confidence.eq("high")].copy()
    rows.attrs["controlled_ids"] = controlled_ids
    if rows.empty:
        return rows
    if rows.canonical_player_id.eq("").any() or rows.duplicated(["canonical_player_id", "threshold"]).any():
        raise ValueError("Match milestone seasons require one explicit identity and date per threshold")
    for row in rows.to_dict("records"):
        season_start(row["season"])
        before, threshold, after = (float(row[c]) for c in ("before_upper_bound", "threshold", "after_lower_bound"))
        if not all(math.isfinite(v) for v in (before, threshold, after)) or not 0 <= before < threshold <= after:
            raise ValueError("Source bounds do not establish a milestone crossing")
        if threshold != int(threshold) or not re.fullmatch(r"[a-f0-9]{64}", row["source_sha256"]):
            raise ValueError("Invalid milestone threshold or source fingerprint")
    return rows


def qualified_match_achievement_rows(
    historical_data: dict[str, object], all_time: pd.DataFrame,
    season_window: list[str], thresholds: list[int], *, club_id: str = CLUB_ID,
) -> tuple[list[dict[str, object]], set[str]]:
    if club_id != CLUB_ID or all_time.empty:
        return [], set()
    evidence = load_match_milestone_seasons()
    anchored = all_time.get("historical_match_anchor_applied", pd.Series(False, index=all_time.index)).astype(str).str.casefold().isin({"true", "1"})
    evidence_ids = set(evidence.attrs.get("controlled_ids", set()))
    controlled = set(all_time.loc[anchored, "canonical_player_id"]) | (evidence_ids & set(all_time.canonical_player_id))
    requested = set(season_window)
    allowed = set(thresholds)
    output = []

    def emit(player: pd.Series, threshold: int, season: str) -> None:
        if season in requested and threshold in allowed and float(player["Matches"]) >= threshold:
            output.append({"Player": player["Player"], "canonical_player_id": player["canonical_player_id"],
                           "Category": "Matches", "Milestone": f"{threshold:,} matches reached", "Threshold": threshold,
                           "Current Total": float(player["Matches"]), "Season": season, "Unit": "matches"})

    batting = historical_data.get("batting_raw")
    for pid in sorted(controlled):
        selected = all_time[all_time.canonical_player_id.eq(pid)]
        if len(selected) != 1:
            raise ValueError("Match milestone requires one public canonical career row")
        player = selected.iloc[0]
        if is_private_or_anonymised_player(player.get("Player"), metadata=player):
            continue
        if not evidence.empty:
            for row in evidence[evidence.canonical_player_id.eq(pid)].to_dict("records"):
                emit(player, int(row["threshold"]), row["season"])
        has_anchor = str(player.get("historical_match_anchor_applied", "")).casefold() in {"true", "1"}
        if not has_anchor or not isinstance(batting, pd.DataFrame) or batting.empty:
            continue
        grain = ["canonical_player_id", "season_id", "team_id", "grade_id"]
        if not {*grain, "season", "matches"}.issubset(batting):
            continue
        source = batting[batting.canonical_player_id.eq(pid)].copy()
        source["_year"] = source.season.map(season_start)
        source = source[source._year.gt(season_start(player["historical_match_anchor_through_season"]))]
        values = pd.to_numeric(source.matches, errors="coerce")
        if source[grain].isna().any().any() or source[grain].astype(str).eq("").any().any() or source.duplicated(grain).any() or values.isna().any():
            continue
        if not values.map(math.isfinite).all() or values.lt(0).any() or values.mul(2).mod(1).ne(0).any():
            continue
        running = float(player["historical_match_anchor_value"])
        if not math.isclose(running + float(values.sum()), float(player["Matches"]), abs_tol=1e-8):
            continue
        source["_weight"] = values
        for (_, season), weight in source.groupby(["_year", "season"])._weight.sum().sort_index().items():
            after = running + float(weight)
            for threshold in thresholds:
                if running < threshold <= after:
                    emit(player, threshold, season)
            running = after
    unique = {(r["canonical_player_id"], r["Threshold"], r["Season"]): r for r in output}
    return list(unique.values()), controlled
