"""GRDCC's performance-scoped public projection, separate from raw accounting."""
from __future__ import annotations

import pandas as pd

from src.utils.player_identity import public_player_mask

CLUB = "georges-river-district"
PERFORMANCE_KEY = ("match_id", "team_id", "participant_id")


class PublicAggregateReconciliationRequired(ValueError):
    """A mixed-visibility aggregate needs a verified public-only reducer."""


def _keys(frame: pd.DataFrame) -> pd.Series:
    if not set(PERFORMANCE_KEY).issubset(frame.columns):
        raise ValueError("Performance privacy evidence requires exact source keys")
    columns = frame.loc[:, PERFORMANCE_KEY]
    if columns.isna().any().any() or columns.astype(str).apply(lambda c: c.str.strip().eq("")).any().any():
        raise ValueError("Performance privacy evidence contains missing source keys")
    return pd.Series(list(columns.astype(str).itertuples(index=False, name=None)), index=frame.index)


def public_performance_frames(
    frames: dict[str, pd.DataFrame], *, club_id: str
) -> tuple[dict[str, pd.DataFrame], frozenset[tuple[str, str, str]]]:
    """Mask wins within a performance, never across an entire career or name alias."""
    if club_id != CLUB:
        return {key: value.copy() for key, value in frames.items()}, frozenset()
    protected = set()
    for frame in frames.values():
        if not frame.empty:
            keys = _keys(frame)
            protected.update(keys.loc[~public_player_mask(frame)])
    public = {}
    for key, frame in frames.items():
        public[key] = frame.copy() if frame.empty else frame.loc[~_keys(frame).isin(protected)].copy()
    return public, frozenset(protected)


def public_season_aggregate(
    aggregate: pd.DataFrame,
    frames: dict[str, pd.DataFrame],
    *,
    club_id: str,
) -> pd.DataFrame:
    """Withhold entirely protected current scopes; never subtract ratios or alter raw totals.

    Call with one complete season of exact scorecard evidence. Mixed public/private
    scopes fail closed until their counters and ratios are independently rebuilt.
    Earlier approved seasons must be retained separately, not passed to this helper.
    """
    if club_id != CLUB:
        return aggregate.copy()
    public, protected = public_performance_frames(frames, club_id=club_id)
    if not protected:
        return aggregate.copy()
    if not {"team_id", "player_id"}.issubset(aggregate.columns):
        raise ValueError("Aggregate projection requires exact team and source-player keys")
    if "season" in aggregate and aggregate.season.dropna().nunique() > 1:
        raise ValueError("Do not project historical and current seasons together")
    aggregate_scopes = set(aggregate[["team_id", "player_id"]].astype(str).itertuples(index=False, name=None))
    protected_scopes = {(team, player) for _, team, player in protected} & aggregate_scopes
    public_scopes = set()
    for frame in public.values():
        if not frame.empty:
            public_scopes.update((team, player) for _, team, player in _keys(frame))
    if protected_scopes & public_scopes:
        raise PublicAggregateReconciliationRequired(
            "Mixed-visibility season scope requires independently rebuilt public totals"
        )
    scope_keys = list(aggregate[["team_id", "player_id"]].astype(str).itertuples(index=False, name=None))
    keep = [key not in protected_scopes for key in scope_keys]
    return aggregate.loc[keep].copy()
