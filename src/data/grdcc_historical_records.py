"""Separately governed historical records, not a source-person equivalence map."""
from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.config.club_config import REPO_ROOT, get_active_club_id, normalize_club_id

CLUB = 'georges-river-district'
PATH = REPO_ROOT / 'clubs' / CLUB / 'data/source/separated_historical_records.csv'
SOURCE_NOTE = 'Historical Source Scope'
RECORD_KIND = 'Historical Record Kind'
FILTERED_SCOPE = 'Historical Filtered Scope'
REPORT_URL = 'https://drive.google.com/file/d/1wbmPZ-8DDKz4GoyPG9dNza-mBnplmyUR/view'


def historical_record_signature(club_id=None):
    if normalize_club_id(club_id or get_active_club_id()) != CLUB or not PATH.exists():
        return ()
    paths = [PATH, Path(__file__)]
    from src.config.club_config import get_processed_path
    paths += [get_processed_path(f'all_seasons_{c}.csv', club_id=CLUB)
              for c in ['batting', 'bowling', 'fielding']]
    return tuple((str(p), p.stat().st_mtime_ns, p.stat().st_size) for p in paths if p.exists())


@lru_cache(maxsize=4)
def _records(signature):
    if not signature:
        return pd.DataFrame()
    rows = pd.read_csv(PATH).fillna('')
    if rows.duplicated(['record_id', 'metric']).any() or not rows.status.eq('source_verified').all():
        raise ValueError('Historical publication requires unique verified metric scopes')
    if not rows.through_season_start.eq(2024).all():
        raise ValueError('Historical report boundary must remain 2024/25')
    return rows


def historical_records(club_id=None):
    return _records(historical_record_signature(club_id)).copy()


def report_profile_index(club_id=None):
    rows = historical_records(club_id)
    if rows.empty:
        return pd.DataFrame(columns=['id', 'name'])
    return (rows.loc[rows.record_kind.eq('annual_report_record'), ['record_id', 'public_name']]
            .drop_duplicates().rename(columns={'record_id': 'id', 'public_name': 'name'}))


def is_scoped_historical(row):
    return str(row.get(RECORD_KIND, '')) in {'primary_historical', 'annual_report_record'}


def apply_historical_records(frame, club_id=None, *, add_report_records=False):
    """Apply on serving copies only. Report records never become primary source IDs."""
    rows = historical_records(club_id)
    if rows.empty or 'canonical_player_id' not in frame:
        return frame
    from src.data.grdcc_career_quarantine import CAREER_COLUMNS, REVIEW_FLAG
    from src.data.grdcc_career_refresh import public_career_source
    output = frame.copy()
    primary_present = output.canonical_player_id.fillna('').astype(str).isin(
        rows.loc[rows.record_kind.eq('primary_historical'), 'record_id']).any()
    report_present = output.get('report_record_id', pd.Series('', index=output.index)).isin(
        rows.loc[rows.record_kind.eq('annual_report_record'), 'record_id']).any()
    if not primary_present and not report_present:
        return frame
    if REVIEW_FLAG not in output:
        output[REVIEW_FLAG] = False
    else:
        output.loc[output[REVIEW_FLAG].isna(), REVIEW_FLAG] = False
    for record_id, anchors in rows.groupby('record_id', sort=True):
        anchor = anchors.iloc[0]
        report_only = anchor.record_kind == 'annual_report_record'
        if report_only:
            selected = output.get('report_record_id', pd.Series('', index=output.index)).eq(record_id)
            if not selected.any() and add_report_records and primary_present:
                index = max(output.index, default=-1) + 1
                output.loc[index, 'report_record_id'] = record_id
                output.loc[index, 'player_key'] = record_id
                selected = output.index.to_series().eq(index)
        else:
            selected = output.canonical_player_id.fillna('').astype(str).eq(record_id)
        if not selected.any():
            continue
        for column in (CAREER_COLUMNS | {'Seasons Played', 'Debut Season', 'Latest Season', 'Career Span', 'Seasons'}).intersection(output.columns) | {
            c for c in output if c.startswith(('batting', 'bowling', 'fielding', 'ballByBall'))
        }:
            if output[column].dtype == bool:
                output[column] = output[column].astype(object)
            output.loc[selected, column] = float('nan')
        output.loc[selected, 'Player'] = anchor.public_name
        if not report_only and 'canonical_player_name' in output:
            output.loc[selected, 'canonical_player_name'] = anchor.public_name
        output.loc[selected, RECORD_KIND] = anchor.record_kind
        output.loc[selected, REVIEW_FLAG] = False
        filtered = output.get(FILTERED_SCOPE, pd.Series(False, index=output.index)).fillna(False).eq(True) & selected
        for metric in anchors.itertuples():
            value = float(metric.value)
            if not report_only:
                category, field = {'Runs': ('batting', 'battingAggregate'),
                                   'Wickets': ('bowling', 'bowlingWickets')}[metric.metric]
                source = public_career_source(category)
                years = pd.to_numeric(source.season.astype(str).str.extract(r'(\d{4})')[0], errors='coerce')
                later = source.loc[source.canonical_player_id.eq(record_id) & years.gt(2024)]
                counters = pd.to_numeric(later[field], errors='coerce')
                if counters.isna().any() or counters.lt(0).any():
                    raise ValueError('Incomplete eligible later historical-record contribution')
                value += counters.sum()
            output.loc[selected & ~filtered, metric.metric] = value
        if report_only:
            source_metrics = []
            for metric in anchors.itertuples():
                page = {'Runs': 'p98', 'Wickets': 'p100'}.get(metric.metric)
                if page is None:
                    continue
                source_metrics.append(
                    f"{metric.metric}: {int(float(metric.value)):,} ALL GRADES through 2024/25 ({page})"
                )
            note = (
                'Annual Report record: ' + '; '.join(source_metrics)
                + '. Other career metrics and appearances are unavailable; this report record is not a primary player identity.'
            )
        else:
            note = 'Runs: Annual Report ALL GRADES through 2024/25 (p98). Wickets: recorded worksheet scope only (nine seasons, 1930/31-1947/48); complete bowling career unverified. Career rates unavailable.'
        output.loc[selected, SOURCE_NOTE] = note
        output.loc[filtered, SOURCE_NOTE] = 'Complete career values unavailable for this filter. See the separately labelled recorded source performances in the profile.'
        for c in ['Featured Record Source', 'Featured Record Metric', 'Featured Record Source Note', 'Matches Source', 'Matches Proxy']:
            if c in output:
                output.loc[selected, c] = ''
        if 'Featured Record Override' in output:
            output.loc[selected, 'Featured Record Override'] = False
    return output


def ranked_historical_rows(frame, metric, club_id=None):
    if not historical_record_signature(club_id) or RECORD_KIND not in frame:
        return frame
    scoped = frame[RECORD_KIND].isin(['primary_historical', 'annual_report_record'])
    # Recorded worksheet wickets are a lower bound, not a complete-career ranking.
    incompatible = scoped & pd.to_numeric(frame.get(metric, pd.Series(float('nan'), index=frame.index)), errors='coerce').isna()
    if metric == 'Wickets':
        incompatible |= frame[RECORD_KIND].eq('primary_historical')
    return frame.loc[~incompatible].copy()


def undated_historical_rows(frame):
    if RECORD_KIND not in frame:
        return frame
    return frame.loc[~frame[RECORD_KIND].isin(['primary_historical', 'annual_report_record'])].copy()
