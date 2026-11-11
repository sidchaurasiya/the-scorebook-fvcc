"""Disjoint-season preservation primitives for the Hawks offline refresh."""

from __future__ import annotations

import re

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
    """Keep complete source event ledgers even when scorecard totals differ.

    Arithmetic differences are recorded, not used as a proxy for delivery
    completeness. Bowling insights still require a sufficiently complete,
    uniquely identified event sequence.
    """
    source = balls.copy()
    if 'ball_event_id' not in source:
        source['ball_event_id'] = pd.NA
    source['_runs'] = pd.to_numeric(source['total_runs'], errors='coerce')
    source['_legal'] = source.get('is_legal_delivery', pd.Series(index=source.index, dtype='object')).map(_source_bool)
    totals = source.groupby(['match_id', 'innings_id'], as_index=False).agg(
        delivery_runs=('_runs', lambda values: values.sum(min_count=1)),
        missing_runs=('_runs', lambda values: int(values.isna().sum())),
        event_count=('_runs', 'size'),
        legal_balls=('_legal', lambda values: int(values.fillna(False).sum())),
        missing_legal_flags=('_legal', lambda values: int(values.isna().sum())),
        missing_event_ids=('ball_event_id', lambda values: int(values.isna().sum())),
        duplicate_event_ids=('ball_event_id', lambda values: int(values.duplicated().sum())),
    )
    audit = innings[['match_id', 'innings_id', 'runs_scored', 'overs_bowled']].merge(
        totals, on=['match_id', 'innings_id'], how='left'
    )
    for column in ['event_count', 'legal_balls', 'missing_runs', 'missing_legal_flags', 'missing_event_ids', 'duplicate_event_ids']:
        audit[column] = pd.to_numeric(audit[column], errors='coerce').fillna(0).astype(int)
    audit['expected_legal_balls'] = audit['overs_bowled'].map(overs_to_legal_balls)
    scorecard_runs = pd.to_numeric(audit['runs_scored'], errors='coerce')
    delivery_runs = pd.to_numeric(audit['delivery_runs'], errors='coerce')
    audit['run_difference_delivery_minus_scorecard'] = delivery_runs - scorecard_runs
    audit['reconciled'] = (
        delivery_runs.notna()
        & scorecard_runs.notna()
        & audit['missing_runs'].eq(0)
        & delivery_runs.eq(scorecard_runs)
    )
    audit['coverage_complete'] = (
        audit['event_count'].gt(0)
        & audit['expected_legal_balls'].notna()
        & audit['event_count'].ge(audit['expected_legal_balls'].fillna(float('inf')))
        & audit['missing_runs'].eq(0)
        & audit['missing_legal_flags'].eq(0)
        & audit['missing_event_ids'].eq(0)
        & audit['duplicate_event_ids'].eq(0)
    )
    audit['accepted_for_bowling_insights'] = audit['coverage_complete']
    audit['coverage_status'] = audit.apply(delivery_coverage_status, axis=1)
    accepted = audit.loc[audit['accepted_for_bowling_insights'], ['match_id', 'innings_id']]
    included = balls.merge(accepted.drop_duplicates(), on=['match_id', 'innings_id'], how='inner')
    return included, audit


def _source_bool(value: object) -> object:
    if pd.isna(value):
        return pd.NA
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {'true', '1', 'yes'}


def overs_to_legal_balls(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    match = re.fullmatch(r'(\d+)(?:\.([0-5]))?', text)
    if not match:
        return None
    overs = int(match.group(1))
    balls = int(match.group(2) or 0)
    return overs * 6 + balls


def delivery_coverage_status(row: pd.Series) -> str:
    if row['event_count'] == 0:
        return 'NO_DELIVERY_EVENTS'
    if pd.isna(row['expected_legal_balls']):
        return 'SCORECARD_OVERS_UNAVAILABLE'
    if row['missing_event_ids']:
        return 'EVENT_ID_MISSING'
    if row['duplicate_event_ids']:
        return 'DUPLICATE_EVENT_ID'
    if row['missing_runs']:
        return 'DELIVERY_RUNS_MISSING'
    if row['missing_legal_flags']:
        return 'LEGAL_DELIVERY_FLAG_MISSING'
    if row['event_count'] < row['expected_legal_balls']:
        return 'DELIVERY_COVERAGE_SHORT_OF_SCORECARD_OVERS'
    return 'SOURCE_AS_RECORDED_TOTALS_MATCH' if row['reconciled'] else 'SOURCE_AS_RECORDED_TOTALS_DIFFER'


def source_as_recorded_bbb_innings(
    batting: pd.DataFrame,
    balls: pd.DataFrame,
    dimension_columns: list[str],
    *,
    runs_column: str,
    balls_column: str,
    dismissed_column: str,
) -> pd.DataFrame:
    """Derive GWHCC ball metrics from unique event rows without scorecard equality gating."""
    output_columns = list(dict.fromkeys([
        *dimension_columns, "display_player_name", "match_id", "innings_id",
        "bbb_runs", "bbb_balls_faced", "bbb_dismissals", "bbb_dot_balls",
        "bbb_dot_ball_balls_faced", "bbb_batting_innings", "bbb_matches",
        "delivery_event_count", "scorecard_runs", "scorecard_balls",
        "source_cumulative_runs", "source_cumulative_balls", "latest_match_date",
        "delivery_coverage_status",
    ]))
    if batting.empty or balls.empty:
        return pd.DataFrame(columns=output_columns)

    cards = batting.copy()
    if "display_player_name" not in cards:
        fallback_name = cards.get("canonical_player_name", cards.get("player_name", pd.Series(index=cards.index, dtype="object")))
        cards["display_player_name"] = fallback_name
    dimensions = list(dict.fromkeys(
        [column for column in dimension_columns if column in cards] + ["display_player_name"]
    ))
    card_keys = list(dict.fromkeys([*dimensions, "match_id", "innings_id", "participant_id"]))
    cards["_scorecard_runs"] = pd.to_numeric(cards[runs_column], errors="coerce")
    cards["_scorecard_balls"] = pd.to_numeric(cards[balls_column], errors="coerce")
    cards["_dismissed"] = pd.to_numeric(cards[dismissed_column], errors="coerce").fillna(0)
    cards["_latest_match_date"] = cards.get("first_match_day", pd.Series(index=cards.index, dtype="object"))
    cards = cards.groupby(card_keys, dropna=False, as_index=False).agg(
        scorecard_runs=("_scorecard_runs", "sum"),
        scorecard_balls=("_scorecard_balls", "sum"),
        bbb_dismissals=("_dismissed", "max"),
        latest_match_date=("_latest_match_date", "max"),
    )

    source = balls.copy()
    if "ball_event_id" not in source:
        source["ball_event_id"] = pd.NA
    source["_runs"] = pd.to_numeric(source["runs_bat"], errors="coerce")
    source["_wides"] = pd.to_numeric(source["wides"], errors="coerce")
    source["_ball_faced"] = source["_wides"].eq(0).astype(int)
    source["_dot_ball"] = source["_ball_faced"].eq(1) & source["_runs"].eq(0)
    order = [column for column in ["innings_order", "over_number", "ball_number", "ball_event_id"] if column in source]
    if order:
        source = source.sort_values(order, kind="stable")

    def last_non_null(values: pd.Series):
        values = values.dropna()
        return values.iloc[-1] if not values.empty else pd.NA

    events = source.groupby(
        ["match_id", "innings_id", "striker_participant_id"], dropna=False, as_index=False
    ).agg(
        bbb_runs=("_runs", lambda values: values.sum(min_count=1)),
        bbb_balls_faced=("_ball_faced", "sum"),
        bbb_dot_balls=("_dot_ball", "sum"),
        delivery_event_count=("_runs", "size"),
        missing_runs=("_runs", lambda values: int(values.isna().sum())),
        missing_wides=("_wides", lambda values: int(values.isna().sum())),
        missing_event_ids=("ball_event_id", lambda values: int(values.isna().sum())),
        duplicate_event_ids=("ball_event_id", lambda values: int(values.duplicated().sum())),
        source_cumulative_runs=("striker_runs_scored", last_non_null),
        source_cumulative_balls=("striker_balls_faced", last_non_null),
    ).rename(columns={"striker_participant_id": "participant_id"})
    result = cards.merge(events, on=["match_id", "innings_id", "participant_id"], how="left")
    for column in ["delivery_event_count", "missing_runs", "missing_wides", "missing_event_ids", "duplicate_event_ids"]:
        result[column] = pd.to_numeric(result[column], errors="coerce").fillna(0).astype(int)
    result["scorecard_balls"] = pd.to_numeric(result["scorecard_balls"], errors="coerce")
    result["delivery_coverage_status"] = "SOURCE_EVENT_ROWS_COMPLETE"
    result.loc[result["delivery_event_count"].eq(0), "delivery_coverage_status"] = "NO_DELIVERY_EVENTS"
    result.loc[result["delivery_event_count"].lt(result["scorecard_balls"].fillna(float("inf"))), "delivery_coverage_status"] = "PLAYER_EVENT_SEQUENCE_SHORT_OF_SCORECARD_BALLS"
    result.loc[result["missing_runs"].gt(0) | result["missing_wides"].gt(0), "delivery_coverage_status"] = "DELIVERY_RUN_OR_WIDE_VALUE_MISSING"
    result.loc[result["missing_event_ids"].gt(0), "delivery_coverage_status"] = "EVENT_ID_MISSING"
    result.loc[result["duplicate_event_ids"].gt(0), "delivery_coverage_status"] = "DUPLICATE_EVENT_ID"
    valid = (
        result["delivery_event_count"].gt(0)
        & result["delivery_event_count"].ge(result["scorecard_balls"].fillna(float("inf")))
        & result["missing_runs"].eq(0)
        & result["missing_wides"].eq(0)
        & result["missing_event_ids"].eq(0)
        & result["duplicate_event_ids"].eq(0)
        & pd.to_numeric(result["bbb_runs"], errors="coerce").notna()
        & pd.to_numeric(result["bbb_balls_faced"], errors="coerce").gt(0)
    )
    result = result.loc[valid].copy()
    if result.empty:
        return pd.DataFrame(columns=output_columns)
    result["bbb_dot_ball_balls_faced"] = result["bbb_balls_faced"]
    result["bbb_batting_innings"] = 1
    result["bbb_matches"] = 1
    return result[output_columns]


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
