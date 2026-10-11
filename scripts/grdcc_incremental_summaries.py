"""Merge verified, disjoint GRDCC summary partitions without historical JSON."""
from __future__ import annotations

import pandas as pd

ADDITIVE = {
    'innings', 'runs', 'outs', 'thirties', 'fifties', 'hundreds', 'ducks', 'fours', 'sixes',
    'bbb_runs', 'bbb_balls_faced', 'bbb_dismissals', 'bbb_batting_innings', 'bbb_matches',
    'matches', 'balls_bowled', 'runs_against', 'wickets', 'three_wicket_innings',
    'five_wicket_innings', 'ten_wicket_matches', 'catches', 'stumpings', 'run_outs',
    'dismissals', 'legal_balls', 'runs_conceded', 'dot_balls', 'boundary_balls',
    'match_count', 'count', 'matches_with_result', 'wins', 'losses',
}
RATIOS = {
    'bat_avg': ('runs', 'outs', 1), 'average': ('runs', 'outs', 1),
    'strike_rate': ('bbb_runs', 'bbb_balls_faced', 100), 'bat_sr': ('bbb_runs', 'bbb_balls_faced', 100),
    'bowl_avg': ('runs_against', 'wickets', 1), 'bowl_sr': ('balls_bowled', 'wickets', 1),
    'eco': ('runs_against', 'balls_bowled', 6), 'win_pct': ('wins', 'matches_with_result', 100),
    'avg': ('runs_conceded', 'wickets', 1), 'sr': ('legal_balls', 'wickets', 1),
    'dot_ball_pct': ('dot_balls', 'legal_balls', 100), 'boundary_rate': ('boundary_balls', 'legal_balls', 100),
}
VERIFIED_COVERAGE = {
    'bbb_runs', 'bbb_balls_faced', 'bbb_dismissals', 'bbb_batting_innings', 'bbb_matches',
}


def require_disjoint(history_ids, increment_ids):
    overlap = set(history_ids) & set(increment_ids)
    if overlap:
        raise ValueError(f'Overlapping source partitions: {len(overlap)} matches')
    if len(increment_ids) != len(set(increment_ids)):
        raise ValueError('Duplicate increment match IDs')


def merge_summary(history, increment, keys, history_ids, increment_ids):
    """Keep untouched historical rows exact; update only sufficient-statistic keys."""
    require_disjoint(history_ids, increment_ids)
    if increment.empty:
        return history.copy()
    from scripts.build_player_profile_insight_exports import best_high_score_from_labels, best_bbi_from_labels

    old = history.copy().set_index(keys, drop=False)
    new = increment.copy().set_index(keys, drop=False)
    if old.index.duplicated().any() or new.index.duplicated().any():
        raise ValueError('Non-unique summary key; cannot safely aggregate')
    columns = list(history.columns)
    rows = [row.copy() for key, row in old.iterrows() if key not in new.index]
    for key, delta in new.iterrows():
        if key not in old.index:
            rows.append(delta.reindex(columns))
            continue
        previous = old.loc[key]
        row = previous.copy()
        for column in ADDITIVE & set(columns):
            if column in delta and pd.notna(delta[column]):
                if pd.notna(previous[column]):
                    row[column] = float(previous[column]) + float(delta[column])
                elif column in VERIFIED_COVERAGE:
                    # Missing BBB coverage means no verified prior deliveries,
                    # not an unknown career counter such as historical Not Outs.
                    row[column] = float(delta[column])
                else:
                    row[column] = pd.NA
        for column in ['high_score', 'hs']:
            if column in columns:
                row[column] = best_high_score_from_labels(pd.Series([previous[column], delta.get(column)]))
        if 'bbi' in columns:
            row['bbi'] = best_bbi_from_labels(pd.Series([previous.bbi, delta.get('bbi')]))
        for column, (numerator, denominator, factor) in RATIOS.items():
            if column in columns and numerator in row and denominator in row:
                row[column] = row[numerator] * factor / row[denominator] if pd.notna(row[denominator]) and row[denominator] > 0 else pd.NA
        if 'eco' in columns and 'legal_balls' in row:
            row['eco'] = row.runs_conceded * 6 / row.legal_balls if row.legal_balls > 0 else pd.NA
        if 'overs' in columns:
            from src.ui.layout import format_balls_as_overs
            row['overs'] = format_balls_as_overs(row.legal_balls)
        if 'high_score_sort' in columns:
            from src.ui.layout import parse_batting_score
            score, not_out = parse_batting_score(row.high_score)
            row['high_score_sort'], row['high_score_not_out_sort'] = score, int(not_out)
        if 'hs_sort' in columns:
            from src.ui.layout import parse_batting_score
            row['hs_sort'] = parse_batting_score(row.hs)[0]
        if 'bbi_wickets_sort' in columns:
            from scripts.build_hall_of_fame_detail_exports import parse_bbi
            row['bbi_wickets_sort'], row['bbi_runs_sort'] = parse_bbi(row.bbi)
        rows.append(row)
    output = pd.DataFrame(rows).reindex(columns=columns).reset_index(drop=True)
    if 'total_dismissals' in columns:
        output['total_dismissals'] = output.groupby(['scope', 'canonical_player_id'], dropna=False)['count'].transform('sum')
        output['pct'] = output['count'] * 100 / output['total_dismissals'].where(output['total_dismissals'].gt(0))
    return output
