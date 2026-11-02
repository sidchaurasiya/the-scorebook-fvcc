"""Approved exact-source GRDCC grouping and retained offline lineage checks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pandas as pd

from src.config.club_config import get_hall_of_fame_dir
from src.utils.player_identity import is_private_or_anonymised_player, make_player_slug, public_player_mask

CLUB = 'georges-river-district'


def redirect_approved_component_id(source_id: str, candidate_ids, *, club_id: str) -> str:
    """Redirect only an exact approved component to an existing public profile."""
    if club_id != CLUB or not source_id:
        return ''
    path = Path(get_hall_of_fame_dir(club_id=club_id)) / 'legacy_display_composites.json'
    if not path.exists():
        return ''
    ledger = json.loads(path.read_text())
    if ledger.get('schema_version') != 1:
        raise ValueError('Approved grouping evidence is invalid')
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    for record in ledger['records']:
        if digest(source_id) in record['component_id_sha256']:
            matches = [value for value in candidate_ids if digest(str(value)) == record['legacy_id_sha256']]
            return str(matches[0]) if len(matches) == 1 else ''
    return ''


def approved_component_id_map(frame: pd.DataFrame, ledger: dict, *, club_id: str) -> dict[str, str]:
    """Resolve approved exact source IDs even in an intentionally filtered subset."""
    if club_id != CLUB or frame.empty:
        return {}
    if ledger.get('schema_version') != 1 or not ledger.get('records'):
        raise ValueError('Approved grouping evidence is unavailable')
    if not {'canonical_player_id', 'Player'}.issubset(frame.columns):
        raise ValueError('Canonical identities and public labels are required')
    digest = lambda value: hashlib.sha256(value.encode()).hexdigest()
    ids = frame.canonical_player_id.fillna('').astype(str)
    hashes = ids.map(digest)
    mapping = {}
    for record in ledger['records']:
        expected = record['component_id_sha256']
        if len(expected) != 3 or len(set(expected)) != 3:
            raise ValueError('Approved component evidence is invalid')
        selected = frame.loc[hashes.isin(expected)]
        if selected.empty:
            continue
        names = selected.Player.fillna('').astype(str).str.strip()
        if names.eq('').any() or names.map(is_private_or_anonymised_player).any() or names.str.casefold().nunique() != 1 or not public_player_mask(selected).all():
            raise ValueError('Approved component labels are not safely resolvable')
        label = sorted(names.tolist(), key=lambda value: (value.casefold(), value))[0]
        canonical = 'grdcc_exact_name_' + make_player_slug(label)
        if digest(canonical) != record['legacy_id_sha256']:
            raise ValueError('Approved canonical identifier does not match baseline')
        mapping.update({value: canonical for value in selected.canonical_player_id.astype(str)})
    return mapping


def approved_nonoverlap_group(all_time: pd.DataFrame, season_frames: list[pd.DataFrame], ledger: dict, *, club_id: str, allow_partial: bool = False) -> list[dict]:
    """Plan owner-approved exact-source groups; never use a label as identity evidence.

    Season frames must contain the full permitted source evidence for each source
    profile, including overlap evidence that must not itself be publicly displayed.
    This helper returns a plan only; callers must not publish those evidence frames.
    """
    if club_id != CLUB:
        return []
    if ledger.get('schema_version') != 1 or not ledger.get('records'):
        raise ValueError('Approved grouping evidence is unavailable')
    if not {'canonical_player_id', 'Player'}.issubset(all_time.columns):
        raise ValueError('Canonical identities and exact labels are required')
    digest=lambda value:hashlib.sha256(value.encode()).hexdigest()
    ids=all_time.canonical_player_id.fillna('').astype(str)
    hashed=ids.map(digest)
    output=[]
    for record in ledger['records']:
        expected=record['component_id_sha256']
        if len(expected)!=3 or len(set(expected))!=3:
            raise ValueError('Approved component evidence is invalid')
        selected=all_time.loc[hashed.isin(expected)]
        if allow_partial and len(selected) < 3:
            continue
        if len(selected)!=3 or set(hashed.loc[selected.index])!=set(expected):
            raise ValueError('Approved source components are incomplete or ambiguous')
        labels=selected.Player.fillna('').astype(str).str.strip()
        if labels.eq('').any() or labels.map(is_private_or_anonymised_player).any() or labels.str.casefold().nunique()!=1:
            raise ValueError('Approved source components do not have the same public name')
        if not public_player_mask(selected).all():
            raise ValueError('Protected source component cannot be merged')
        component_ids=tuple(sorted(selected.canonical_player_id.astype(str)))
        seasons={value:set() for value in component_ids}
        for frame in season_frames:
            if frame.empty:
                continue
            if not {'canonical_player_id','season'}.issubset(frame.columns):
                raise ValueError('Complete canonical season evidence is required')
            for row in frame.loc[frame.canonical_player_id.astype(str).isin(component_ids),['canonical_player_id','season']].itertuples(index=False):
                if pd.notna(row.season) and str(row.season).strip():
                    seasons[str(row.canonical_player_id)].add(str(row.season).strip().casefold())
        if any(not values for values in seasons.values()):
            raise ValueError('A source component has no recorded seasons')
        if any(seasons[left]&seasons[right] for i,left in enumerate(component_ids) for right in component_ids[i+1:]):
            raise ValueError('Approved source components have overlapping seasons')
        label=sorted(labels.tolist(),key=lambda value:(value.casefold(),value))[0]
        canonical_id='grdcc_exact_name_'+make_player_slug(label)
        if digest(canonical_id)!=record['legacy_id_sha256']:
            raise ValueError('Approved canonical identifier does not match baseline')
        output.append({'canonical_player_id':canonical_id,'component_ids':component_ids,'label':label})
    return output


def legacy_ledger_signature(club_id: str) -> tuple[str, str]:
    """Invalidate dependent caches on content changes and on file removal."""
    if club_id != CLUB:
        return ('not-applicable', '')
    path=Path(get_hall_of_fame_dir(club_id=club_id))/'legacy_display_composites.json'
    try:
        return ('present', hashlib.sha256(path.read_bytes()).hexdigest())
    except FileNotFoundError:
        return ('missing', '')
    except OSError:
        return ('unreadable', '')


def legacy_group_requires_separate_profiles(candidate_ids: set[str], *, club_id: str) -> bool:
    """Do not expand an approved component group to an overlapping namesake."""
    if club_id != CLUB:
        return False
    path=Path(get_hall_of_fame_dir(club_id=club_id))/'legacy_display_composites.json'
    if not path.exists():
        # Missing governance cannot authorize an ambiguous merge.
        return len(candidate_ids)>1
    try:
        ledger=json.loads(path.read_text())
        if ledger.get('schema_version')!=1:
            return len(candidate_ids)>1
        records=ledger['records']
        if not records or any(len(item['component_id_sha256'])!=3 for item in records):
            return len(candidate_ids)>1
        digests={hashlib.sha256(value.encode()).hexdigest() for value in candidate_ids if value}
        return any(set(item['component_id_sha256']).issubset(digests) for item in records)
    except (OSError,ValueError,KeyError,TypeError):
        return len(candidate_ids)>1
