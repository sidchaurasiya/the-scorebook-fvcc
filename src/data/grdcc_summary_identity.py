"""Read approved legacy summary namespaces without omitting historical evidence."""
from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.config.club_config import REPO_ROOT, get_active_club_id

PATH = REPO_ROOT / 'clubs/georges-river-district/data/source/summary_identity_namespace_aliases.csv'
IDENTITY = ['canonical_player_id', 'canonical_player_name', 'display_player_name']
KEYS = {
    'performance_breakdown_by_dimension.csv': IDENTITY + ['dimension', 'discipline', 'breakdown_label'],
    'batting_position_summary.csv': IDENTITY + ['position_group'],
    'bowling_phase_summary.csv': IDENTITY + ['phase_model', 'phase'],
    'dismissal_fingerprint_summary.csv': IDENTITY + ['scope', 'dismissal_bucket'],
    'player_win_rates.csv': IDENTITY,
    'player_bbb_batting_rates.csv': IDENTITY,
    'player_scorecard_milestones.csv': IDENTITY,
    'player_bowling_milestones.csv': IDENTITY,
}


def namespace_signature(club_id=None):
    if (club_id or get_active_club_id()) != 'georges-river-district' or not PATH.exists():
        return tuple()
    return ((str(PATH), PATH.stat().st_mtime),)


@lru_cache(maxsize=4)
def _aliases(version):
    return pd.read_csv(PATH)


def alias_summary_ids(frame, club_id=None):
    signature = namespace_signature(club_id)
    if not signature or frame.empty or 'canonical_player_id' not in frame:
        return frame.copy()
    aliases = _aliases(signature)
    from src.utils.player_identity import normalize_player_name_for_strict_merge, public_player_mask
    output = frame.copy()
    output['__summary_namespace'] = output.canonical_player_id
    for row in aliases.itertuples():
        selected = output.canonical_player_id.eq(row.legacy_summary_id) & public_player_mask(output)
        if not selected.any():
            continue
        names = output.loc[selected, 'canonical_player_name'].map(normalize_player_name_for_strict_merge)
        if not names.eq(normalize_player_name_for_strict_merge(row.canonical_player_name)).all():
            raise ValueError('Summary namespace conflicts with verified canonical name')
        output.loc[selected, 'canonical_player_id'] = row.canonical_player_id
        if 'player_key' in output:
            output.loc[selected, 'player_key'] = row.canonical_player_id
    return output


def coalesce_summary_namespaces(frame, filename, club_id=None):
    signature = namespace_signature(club_id)
    if not signature or '__summary_namespace' not in frame:
        return frame
    keys = KEYS.get(Path(filename).name)
    if not keys:
        return frame.drop(columns=['__summary_namespace'])
    targets = set(_aliases(signature).canonical_player_id)
    selected = frame.canonical_player_id.isin(targets)
    untouched = frame.loc[~selected].drop(columns=['__summary_namespace'])
    parts = frame.loc[selected]
    if parts.empty:
        return untouched
    from scripts.grdcc_incremental_summaries import merge_summary
    parts = parts.copy()
    # These are counts of verified coverage, not unavailable career Not Outs.
    # A missing coverage join contributes no verified deliveries; it must not
    # erase a later namespace's observed ball-by-ball contribution.
    for column in ['bbb_runs','bbb_balls_faced','bbb_dismissals','bbb_batting_innings','bbb_matches']:
        if column in parts:
            parts[column] = pd.to_numeric(parts[column], errors='coerce').fillna(0)
    merged = pd.DataFrame(columns=frame.drop(columns=['__summary_namespace']).columns)
    # The approval records exact-ID provenance and historical-part disjointness;
    # the current partition was separately proved disjoint from all history.
    for _, part in parts.groupby('__summary_namespace', sort=False, dropna=False):
        clean = part.drop(columns=['__summary_namespace'])
        merged = merge_summary(merged, clean, keys, [], [])
    return pd.concat([untouched, merged], ignore_index=True)


def read_normalized_summary(frame, filename, club_id=None):
    if not namespace_signature(club_id):
        return frame.copy()
    from src.utils.player_identity import filter_public_player_rows
    frame = filter_public_player_rows(frame)
    return coalesce_summary_namespaces(alias_summary_ids(frame, club_id), filename, club_id)
