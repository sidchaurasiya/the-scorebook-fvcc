"""Disjoint-season preservation primitives for the Hawks offline refresh."""

from __future__ import annotations

import pandas as pd


def append_disjoint(base: pd.DataFrame, added: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if added.empty:
        return base.copy()
    for label, frame in [("historical", base), ("new", added)]:
        if frame[keys].isna().any().any() or frame.duplicated(keys).any():
            raise ValueError(f"Invalid or duplicate {label} keys: {keys}")
    overlap = base[keys].merge(added[keys], on=keys, how="inner")
    if not overlap.empty:
        raise ValueError(f"Incremental input overlaps historical keys: {keys}")
    return pd.concat([base, added], ignore_index=True, sort=False)


def merge_summary(
    base: pd.DataFrame,
    added: pd.DataFrame,
    *,
    keys: list[str],
    sums: list[str],
    best: dict[str, object] | None = None,
    rates: dict[str, tuple[str, str, float]] | None = None,
) -> pd.DataFrame:
    """Combine sufficient statistics, never average averages or infer missing zeros.

    Callers must first establish disjoint match IDs. Historical-only rows are
    returned unchanged; only keys with new evidence are recalculated.
    """
    if added.empty:
        return base.copy()
    if base.duplicated(keys).any() or added.duplicated(keys).any():
        raise ValueError(f"Ambiguous summary grain: {keys}")
    columns = list(dict.fromkeys([*base.columns, *added.columns, *(rates or {})]))
    lookup = {tuple(row[key] for key in keys): row for row in base.to_dict("records")}
    for delta in added.to_dict("records"):
        key = tuple(delta[column] for column in keys)
        previous = lookup.get(key)
        combined = delta.copy() if previous is None else previous.copy()
        if previous is not None:
            for column in sums:
                values = pd.to_numeric(pd.Series([previous.get(column), delta.get(column)]), errors="coerce")
                combined[column] = values.sum(min_count=1)
            for column, reducer in (best or {}).items():
                combined[column] = reducer(pd.Series([previous.get(column), delta.get(column)]).dropna())
        for column, (numerator, denominator, multiplier) in (rates or {}).items():
            n = combined.get(numerator)
            d = combined.get(denominator)
            incomplete_coverage = previous is not None and any(
                pd.notna(source.get(numerator)) and pd.isna(source.get(denominator))
                for source in [previous, delta]
            )
            combined[column] = n * multiplier / d if not incomplete_coverage and pd.notna(n) and pd.notna(d) and d else None
        lookup[key] = combined
    return pd.DataFrame(list(lookup.values()), columns=columns)


def eligible_match_ids(matches: pd.DataFrame, innings: pd.DataFrame, cutoff: str) -> set[str]:
    if matches['match_id'].duplicated().any():
        raise ValueError('Duplicate match IDs')
    dates = pd.to_datetime(matches['first_match_day'], utc=True, errors='coerce').dt.tz_convert('Australia/Melbourne')
    boundary = pd.Timestamp(cutoff)
    if "T" in cutoff or " " in cutoff:
        boundary = boundary.tz_localize("Australia/Melbourne") if boundary.tzinfo is None else boundary.tz_convert("Australia/Melbourne")
        through_cutoff = dates.le(boundary)
    else:
        through_cutoff = dates.dt.date.le(boundary.date())
    activity = innings.groupby('match_id')[['runs_scored', 'wickets_fallen', 'overs_bowled']].sum().gt(0).any(axis=1)
    statuses = matches['status'].isin(['COMPLETED', 'ABANDONED'])
    return set(matches.loc[through_cutoff & statuses & matches['match_id'].map(activity).fillna(False), 'match_id'])


def reconciled_delivery_innings(innings: pd.DataFrame, balls: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gate new whole-innings bowling insights without rejecting valid batting milestones."""
    source = balls.copy()
    source['_runs'] = pd.to_numeric(source['total_runs'], errors='coerce')
    totals = source.groupby(['match_id', 'innings_id'], as_index=False).agg(
        delivery_runs=('_runs', lambda values: values.sum(min_count=1)),
        missing_runs=('_runs', lambda values: int(values.isna().sum())),
    )
    audit = innings[['match_id', 'innings_id', 'runs_scored']].merge(totals, on=['match_id', 'innings_id'], how='left')
    audit['reconciled'] = audit['delivery_runs'].notna() & audit['missing_runs'].eq(0) & audit['runs_scored'].eq(audit['delivery_runs'])
    ids = set(audit.loc[audit['reconciled'], 'innings_id'])
    return balls[balls['innings_id'].isin(ids)].copy(), audit


def preserve_compact_dismissal_type(batting: pd.DataFrame) -> pd.DataFrame:
    """Retain explicit DNB/not-out evidence when exporting the text-only schema."""
    result = batting.copy()
    text = result['dismissal_text'].fillna('').astype(str)
    result['dismissal_text'] = text.where(text.str.strip().ne(''), result['dismissal_type'].fillna(''))
    return result


def profile_fielding_input(fielding: pd.DataFrame) -> pd.DataFrame:
    """Adapt PlayCricket totals to the profile export's unassisted-plus-assisted contract.

    Keep retained source rows intact. The provider's runOuts already includes
    assistedRunOuts, so adding both directly would duplicate the assisted credits.
    """
    result = fielding.copy()
    total = pd.to_numeric(result["run_outs"], errors="coerce")
    assisted = pd.to_numeric(result["assisted_run_outs"], errors="coerce")
    if (total.isna() | assisted.isna() | assisted.lt(0) | total.lt(assisted)).any():
        raise ValueError("Incomplete or inconsistent GWHCC run-out source totals")
    result["run_outs"] = total - assisted
    return result
