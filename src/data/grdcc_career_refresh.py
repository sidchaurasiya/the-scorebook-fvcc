"""Preserve governed career baselines while adding later official season totals."""
from functools import lru_cache

import pandas as pd

from src.config.club_config import REPO_ROOT, get_processed_path

CLUB = 'georges-river-district'
BASELINE_PATH = REPO_ROOT / 'clubs' / CLUB / 'data/source/career_refresh_baselines.csv'
METRICS = {
    'batting': {'Runs': 'battingAggregate', 'Innings': 'battingInnings', 'Matches': 'matches',
                '50s': 'batting50s', '100s': 'batting100s'},
    'bowling': {'Wickets': 'bowlingWickets', 'Maidens': 'bowlingMaidens', 'Balls Bowled': 'bowlingBalls'},
}


def refresh_baseline_paths():
    return [BASELINE_PATH]


@lru_cache(maxsize=4)
def _later_totals(signature):
    from src.utils.player_identity import apply_player_identity_mapping, filter_public_player_rows

    if not BASELINE_PATH.exists():
        return pd.DataFrame()
    baseline = pd.read_csv(BASELINE_PATH)
    result = []
    for category, metrics in METRICS.items():
        source = pd.read_csv(get_processed_path(f'all_seasons_{category}.csv', club_id=CLUB), low_memory=False)
        source = filter_public_player_rows(apply_player_identity_mapping(source, club_id=CLUB))
        years = pd.to_numeric(source.season.astype(str).str.extract(r'(\d{4})')[0], errors='coerce')
        for year, anchors in baseline.groupby('through_season_start'):
            later = source.loc[years.gt(year)].copy()
            if later.empty:
                continue
            for metric, field in metrics.items():
                if field not in later:
                    continue
                totals = pd.to_numeric(later[field], errors='coerce').groupby(later.canonical_player_id).sum(min_count=1)
                selected = anchors.loc[anchors.metric.eq(metric)].copy()
                selected['increment'] = selected.canonical_player_id.map(totals).fillna(0)
                selected['updated_value'] = selected.governed_value + selected.increment
                result.append(selected)
    return pd.concat(result, ignore_index=True) if result else pd.DataFrame()


def apply_later_season_totals(frame, club_id, source_frame=None):
    if str(club_id or '').strip().casefold() != CLUB or 'canonical_player_id' not in frame:
        return frame
    paths = [BASELINE_PATH, REPO_ROOT / 'clubs' / CLUB / 'player_aliases.csv',
             REPO_ROOT / 'clubs' / CLUB / 'manual_player_merges.csv']
    paths.extend(get_processed_path(f'all_seasons_{category}.csv', club_id=CLUB) for category in METRICS)
    signature = tuple((str(path), path.stat().st_mtime_ns, path.stat().st_size) for path in paths if path.exists())
    updates = _later_totals(signature)
    if updates.empty:
        return frame
    output = frame.copy()
    for row in updates.itertuples():
        if row.increment == 0 or row.metric not in output:
            continue
        matched = output.canonical_player_id.eq(row.canonical_player_id)
        if matched.sum() == 1:
            output.loc[matched, row.metric] = row.updated_value
    if source_frame is not None and 'canonical_player_id' in source_frame:
        anchors = set(updates.canonical_player_id)
        for _, source in source_frame.iterrows():
            player_id = source.canonical_player_id
            if player_id not in anchors:
                continue
            span = str(source.get('Career Span', ''))
            import re
            debut = re.search(r'\d{4}', str(source.get('Debut Season', span)))
            latest = re.findall(r'\d{4}', str(source.get('Latest Season', span)))
            if not debut or not latest or int(debut[0]) < 1972 or int(latest[-1]) <= 2025:
                continue
            matched = output.canonical_player_id.eq(player_id)
            if matched.sum() != 1:
                continue
            # Modern source-rule counters are not historical Excel supplements.
            for column in ['Matches', 'Innings', 'Bat Avg', '50s', '100s', 'Maidens',
                           'Balls Bowled', 'Overs', 'Outs', 'Bowl Avg', 'Bowl SR']:
                if column in output and pd.notna(source.get(column)):
                    output.loc[matched, column] = source[column]
            for column in ['Runs', 'Wickets']:
                if column in output and pd.notna(source.get(column)):
                    value = pd.to_numeric(output.loc[matched, column], errors='coerce').iloc[0]
                    output.loc[matched, column] = max(source[column], value) if pd.notna(value) else source[column]
            if 'Matches Proxy' in output:
                output.loc[matched, 'Matches Proxy'] = ''
            if 'Matches Source' in output:
                output.loc[matched, 'Matches Source'] = 'PlayCricket / PlayHQ'
    return output
