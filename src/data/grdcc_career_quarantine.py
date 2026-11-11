"""Exact-ID public career quarantine; retained source rows are never rewritten."""
from functools import lru_cache
from pathlib import Path
import pandas as pd
from src.config.club_config import REPO_ROOT, get_active_club_id, normalize_club_id

CLUB = 'georges-river-district'
PATH = REPO_ROOT / 'clubs' / CLUB / 'data/source/historical_career_quarantine.csv'
REVIEW_FLAG = 'Historical Career Under Review'
REVIEW_NOTE = 'Historical career statistics under review'
CAREER_COLUMNS = frozenset([
    'Runs','Wickets','Matches','Innings','Not Outs','Outs','Bat Avg','Bat SR','HS','BBI',
    'Bowl Avg','Bowl SR','Econ','Overs','Balls Bowled','Maidens','Catches','Stumpings',
    'Run Outs','Dismissals','50s','100s','30s','0s','4s','6s','3WI','5WI','10WM',
    'Win Matches','Win Count','Win %','BF','BBB Runs','BBB Balls','BBB Innings','BBB Matches',
    'ballByBallBatSR','ballByBallBatRuns','ballByBallBatBalls',
    'battingAggregate','battingInnings','battingNotOuts','battingBallsFaced','battingAverage',
    'battingStrikeRate','battingHighScore','batting50s','batting100s','batting0s',
    'battingFours','battingSixes','battingMinutes','bowlingWickets','bowlingRuns','bowlingBalls',
    'bowlingMaidens','bowlingOvers','bowlingAverage','bowlingStrikeRate','bowlingEconomy',
    'bowlingBestFigures','fieldingTotalCatches','fieldingCatchesNonWK','fieldingCatchesWK',
    'fieldingStumpings','fieldingRunOuts','fieldingAssistedRunOuts','fieldingUnassistedRunOuts','matches',
    'Avg','Eco','high_score','isBattingHSNotOut','catches_display','stumpings_display',
    'run_outs_display','dismissals_display','balls_faced_display','overs_bowled_display',
])


def quarantine_signature(club_id=None):
    if normalize_club_id(club_id or get_active_club_id()) != CLUB or not PATH.exists():
        return ()
    s=PATH.stat()
    code=Path(__file__).stat()
    from src.data.grdcc_historical_records import historical_record_signature
    return ('public-career-quarantine-v4',str(PATH),s.st_mtime_ns,s.st_size,code.st_mtime_ns,code.st_size,historical_record_signature(club_id))


@lru_cache(maxsize=4)
def _load(signature):
    if not signature:
        return pd.DataFrame()
    rows=pd.read_csv(PATH,dtype=str).fillna('')
    if rows.canonical_player_id.eq('').any() or rows.canonical_player_id.duplicated().any():
        raise ValueError('Career quarantine requires unique exact canonical targets')
    return rows


def quarantine_rows(club_id=None):
    rows = _load(quarantine_signature(club_id)).copy()
    if rows.empty:
        return rows
    from src.data.grdcc_historical_records import historical_record_signature
    active = rows.status.eq('public_career_quarantine')
    if not historical_record_signature(club_id):
        active |= rows.status.eq('separated_historical_records')
    return rows.loc[active]


def blocked_report_names(club_id=None):
    rows=_load(quarantine_signature(club_id)).copy()
    if not rows.empty:
        rows=rows.loc[rows.status.isin([
            'public_career_quarantine',
            'separated_historical_records',
            'reviewed_playcricket_metric_exception',
        ])]
    if rows.empty:
        return set()
    return {part.strip().casefold() for value in rows.blocked_report_names for part in value.split(';') if part.strip()}


def quarantine_mask(frame,club_id=None):
    rows=quarantine_rows(club_id)
    if rows.empty or 'canonical_player_id' not in frame:
        return pd.Series(False,index=frame.index)
    return frame.canonical_player_id.fillna('').astype(str).isin(set(rows.canonical_player_id))


def career_under_review(row):
    value=row.get(REVIEW_FLAG,False)
    return False if pd.isna(value) else str(value).strip().casefold() in {'true','1','yes'}


def apply_career_quarantine(frame,club_id=None):
    from src.data.grdcc_historical_records import apply_historical_records
    frame = apply_historical_records(frame,club_id)
    rows=quarantine_rows(club_id)
    if rows.empty or 'canonical_player_id' not in frame:
        return frame
    output=frame.copy();mask=quarantine_mask(output,club_id)
    if not mask.any():
        return frame
    output[REVIEW_FLAG]=mask
    for row in rows.itertuples():
        selected=output.canonical_player_id.fillna('').astype(str).eq(row.canonical_player_id)
        for column in ['Player','canonical_player_name']:
            if column in output:output.loc[selected,column]=row.public_name
    metric_columns=CAREER_COLUMNS.intersection(output.columns) | {
        c for c in output.columns if c.startswith(('batting','bowling','fielding','ballByBall'))
    }
    for column in metric_columns:
        if output[column].dtype==bool:output[column]=output[column].astype(object)
        output.loc[mask,column]=float('nan')
    for column in ['Matches Source','Matches Proxy','Featured Record Source','Featured Record Metric','Featured Record Source Note']:
        if column in output:output.loc[mask,column]=''
    if 'Featured Record Override' in output:output.loc[mask,'Featured Record Override']=False
    return output


def eligible_career_rows(frame,club_id=None):
    return frame.loc[~quarantine_mask(frame,club_id)].copy()
