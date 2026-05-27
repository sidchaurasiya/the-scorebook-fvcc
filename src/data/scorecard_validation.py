"""Validation helpers for scorecard-derived deploy-safe metrics."""

from __future__ import annotations

import pandas as pd


MAX_WICKETS_IN_BOWLING_INNINGS = 10


def filter_plausible_bowling_figures(
    rows: pd.DataFrame,
    *,
    wickets_column: str,
    runs_column: str,
) -> pd.DataFrame:
    """Remove impossible bowling innings before deriving records.

    PlayCricket scorecard rows can occasionally contain malformed bowling
    figures. Bowling records should not surface impossible figures such as
    41/0, even when the source row is otherwise parseable.
    """
    if rows.empty or wickets_column not in rows or runs_column not in rows:
        return rows
    wickets = pd.to_numeric(rows[wickets_column], errors="coerce")
    runs = pd.to_numeric(rows[runs_column], errors="coerce")
    plausible = wickets.between(0, MAX_WICKETS_IN_BOWLING_INNINGS, inclusive="both") & runs.ge(0)
    return rows[plausible.fillna(False)].copy()
