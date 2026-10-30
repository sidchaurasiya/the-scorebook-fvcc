"""Replace one published FVCC match's catch contributions from frozen evidence.

This deliberately does not implement a general refresh or accept runs, wickets,
rosters, result, or dismissal-type corrections. Source receipts stay external.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CATCH_COLUMNS = ('fieldingCatchesNonWK', 'fieldingCatchesWK', 'fieldingTotalCatches')


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.' + path.name, suffix='.correction-tmp', delete=False) as handle:
        handle.write(content)
        temporary = handle.name
    os.replace(temporary, path)


def stage_transaction(processed, updates, evidence_dir, signature, report):
    entries = []
    for relative, frame in updates.items():
        content = frame.to_csv(index=False).encode()
        staged = evidence_dir / 'staged' / relative
        atomic_write(staged, content)
        entries.append({'path': relative, 'before': hashlib.sha256((processed / relative).read_bytes()).hexdigest(),
                        'after': hashlib.sha256(content).hexdigest()})
    journal = {'root': str(processed.resolve()), 'source_signature': signature, 'phase': 'pending', 'files': entries, 'report': report}
    atomic_write(evidence_dir / 'transaction.json', (json.dumps(journal, indent=2) + '\n').encode())
    return journal


def replay_transaction(processed, evidence_dir, journal, signature):
    if journal['root'] != str(processed.resolve()) or journal['source_signature'] != signature:
        raise ValueError('Pending transaction belongs to a different root or source')
    for entry in journal['files']:
        target = (processed / entry['path']).resolve()
        if not target.is_relative_to(processed.resolve()):
            raise ValueError('Invalid transaction path')
        staged = evidence_dir / 'staged' / entry['path']
        if hashlib.sha256(staged.read_bytes()).hexdigest() != entry['after']:
            raise ValueError('Staged correction content changed')
        if hashlib.sha256(target.read_bytes()).hexdigest() not in {entry['before'], entry['after']}:
            raise ValueError('Intervening edit conflicts with pending correction')
    for entry in journal['files']:
        atomic_write(processed / entry['path'], (evidence_dir / 'staged' / entry['path']).read_bytes())


def replace_match_rows(old, current, match_id):
    if set(current.match_id.astype(str)) != {str(match_id)}:
        raise ValueError('Replacement must contain exactly the selected match')
    return pd.concat([old.loc[~old.match_id.astype(str).eq(str(match_id))], current], ignore_index=True)


def catch_delta(old, current):
    def totals(frame):
        if frame.empty:
            return pd.Series(dtype=float)
        if frame.player_id.duplicated().any():
            raise ValueError('Ambiguous player fielding rows in selected match')
        values = pd.to_numeric(frame.set_index('player_id').catches, errors='raise')
        if values.isna().any() or values.lt(0).any() or values.mod(1).ne(0).any():
            raise ValueError('Invalid match catch counter')
        return values
    a, b = totals(old), totals(current)
    return b.subtract(a, fill_value=0).loc[lambda s: s.ne(0)].to_dict()


def apply_catch_deltas(aggregate, delta, official, season_id, team_id):
    output = aggregate.copy()
    keys = ['season_id', 'team_id', 'player_id']
    if output.duplicated(keys).any():
        raise ValueError('Duplicate aggregate identity keys')
    for player_id, change in delta.items():
        mask = output.season_id.eq(season_id) & output.team_id.eq(team_id) & output.player_id.eq(player_id)
        if mask.sum() != 1 or player_id not in official:
            raise ValueError('Correction requires an existing unambiguous source identity')
        index = output.index[mask][0]
        source = official[player_id]
        old_total = float(output.at[index, 'fieldingTotalCatches'])
        if abs(old_total + change - float(source['fieldingTotalCatches'])) > 1e-9:
            raise ValueError('Match delta does not reconcile with official season total')
        components = sum(float(source[c]) - float(output.at[index, c]) for c in CATCH_COLUMNS[:2])
        if abs(components - change) > 1e-9:
            raise ValueError('Keeper/nonkeeper components do not reconcile')
        for column in CATCH_COLUMNS:
            value = float(source[column])
            if value < 0 or not value.is_integer():
                raise ValueError('Invalid official catch counter')
            output.at[index, column] = str(value)
    return output


def reconcile_batting_descriptions(old, current, match_id):
    before = old.loc[old.match_id.eq(match_id)]
    if before.player_id.duplicated().any() or current.player_id.duplicated().any():
        raise ValueError('Multiple batting innings require a different evidence model')
    if set(before.player_id) != set(current.player_id):
        raise ValueError('Roster change is not a fielding-only correction')
    output = old.copy()
    changes = []
    numeric = ['runs', 'balls', 'fours', 'sixes', 'strike_rate']
    current = current.set_index('player_id')
    for index, row in before.iterrows():
        source = current.loc[row.player_id]
        for column in numeric:
            a = pd.to_numeric(pd.Series([row[column]]), errors='coerce').iloc[0]
            b = pd.to_numeric(pd.Series([source[column]]), errors='coerce').iloc[0]
            if not ((pd.isna(a) and pd.isna(b)) or (pd.notna(a) and pd.notna(b) and abs(a-b) < .005)):
                raise ValueError('Batting figure changed outside fielding scope')
        a, b = str(row.dismissal), str(source.dismissal)
        if a != b:
            # Only descriptive attribution within an already caught dismissal.
            if not (a.casefold().startswith('c:') and b.casefold().startswith('c:')):
                raise ValueError('Dismissal type changed outside correction scope')
            output.at[index, 'dismissal'] = b
            changes.append({'player_id': row.player_id, 'before': a, 'after': b, 'statistical_type_change': False})
    return output, changes


def update_breakdown(existing, increments):
    output = existing.copy()
    keys = ['canonical_player_id', 'dimension', 'discipline', 'breakdown_label']
    if output.duplicated(keys).any() or increments.duplicated(keys).any():
        raise ValueError('Ambiguous profile dimension keys')
    for row in increments.to_dict('records'):
        mask = pd.Series(True, index=output.index)
        for key in keys:
            mask &= output[key].eq(str(row[key]))
        if mask.sum() > 1:
            raise ValueError('Multiple profile rows for one correction')
        if mask.any():
            index = output.index[mask][0]
            for column in ['catches', 'dismissals']:
                value = float(output.at[index, column] or 0) + float(row[column])
                if value < 0:
                    raise ValueError('Negative profile counter after correction')
                output.at[index, column] = str(value)
        else:
            added = {column: '' for column in output.columns}
            added.update({column: str(value) for column, value in row.items() if column in added and pd.notna(value)})
            output = pd.concat([output, pd.DataFrame([added])], ignore_index=True)
    return output


def validate_bowling(old, current):
    current = current.loc[pd.to_numeric(current.overs, errors='coerce').gt(0)]
    if old.player_id.duplicated().any() or current.player_id.duplicated().any():
        raise ValueError('Ambiguous bowling innings')
    for column in ['overs', 'maidens', 'runs_conceded', 'wickets', 'wides', 'no_balls']:
        a = old.set_index('player_id')[column].pipe(pd.to_numeric).to_dict()
        b = current.set_index('player_id')[column].pipe(pd.to_numeric).to_dict()
        if a != b:
            raise ValueError('Substantive bowling contribution changed')


def plan(scorecard, season_fielding, club_id='fvcc'):
    if club_id != 'fvcc':
        raise ValueError('FVCC-only correction boundary')
    from src.data.match_centre_parser import MatchCentrePayloads, parse_match_payloads
    from src.utils.player_identity import filter_public_player_rows
    from scripts import build_club_app_facing_scorecards as cards
    from scripts import build_player_profile_insight_exports as profile

    processed = ROOT / 'clubs/fvcc/data/processed'
    read = lambda name: pd.read_csv(processed / name, dtype=str, keep_default_na=False)
    match_id = str(scorecard['id'])
    if scorecard.get('status') != 'COMPLETED':
        raise ValueError('This correction requires an officially completed match')
    teams = read('teams.csv')
    own = [t for t in scorecard['teams'] if str(t['id']) in set(teams.team_id)]
    if len(own) != 1:
        raise ValueError('Expected one FVCC team')
    team = teams.loc[teams.team_id.eq(str(own[0]['id']))]
    if len(team) != 1:
        raise ValueError('Ambiguous source team/season')
    team_id, season_id, season = team.iloc[0][['team_id', 'season_id', 'season']]
    for name in ['all_seasons_matches.csv', 'season_overview/season_by_round_scorecards.csv']:
        if read(name).match_id.eq(match_id).sum() != 1:
            raise ValueError('Selected match must already exist exactly once')
    active_innings = [i for i in scorecard['innings'] if i.get('batting') or i.get('bowling') or i.get('oversBowled')]
    if len(active_innings) != 2:
        raise ValueError('Correction supports a single played innings per team only')
    frames = parse_match_payloads(MatchCentrePayloads({}, scorecard, {}, {}))
    matches = frames['all_matches'].copy()
    matches['season'] = season
    matches['club_captain_name'] = profile.scorecard_team_captain_name(own[0])
    source_match = cards.build_match_rows(matches, frames['all_match_innings'], teams)
    published_match = read('all_seasons_matches.csv').loc[lambda d: d.match_id.eq(match_id)].iloc[0]
    if len(source_match) != 1:
        raise ValueError('Ambiguous match context')
    for column in cards.MATCH_COLUMNS:
        a, b = str(published_match[column]), str(source_match.iloc[0][column])
        try:
            equal = abs(float(a) - float(b)) < 1e-9
        except ValueError:
            equal = a == b
        if not equal:
            raise ValueError('Match context changed outside fielding scope: ' + column)
    new_bat = filter_public_player_rows(cards.build_batting_rows(frames['all_scorecard_batting'], matches, {team_id}))
    new_field = filter_public_player_rows(cards.build_fielding_rows(frames['all_scorecard_fielding'], matches, {team_id}))
    old_bat = read('all_seasons_scorecard_batting.csv')
    new_bat = new_bat.fillna('').astype(str)
    batting, descriptions = reconcile_batting_descriptions(old_bat, new_bat, match_id)
    roster = set(old_bat.loc[old_bat.match_id.eq(match_id), 'player_id'])
    if not set(new_field.player_id).issubset(roster):
        raise ValueError('Fielder not in existing roster')
    old_fields = read('all_seasons_scorecard_fielding.csv')
    previous = filter_public_player_rows(old_fields.loc[old_fields.match_id.eq(match_id)])
    delta = catch_delta(previous, new_field)
    for column in ['stumpings', 'run_outs']:
        a = previous.set_index('player_id')[column].pipe(pd.to_numeric).to_dict()
        b = new_field.set_index('player_id')[column].pipe(pd.to_numeric).to_dict()
        if any(float(a.get(k, 0)) != float(b.get(k, 0)) for k in set(a) | set(b)):
            raise ValueError('Other fielding contribution changed outside catch scope')
    new_bowl = cards.build_bowling_rows(frames['all_scorecard_bowling'], matches, {team_id})
    old_bowl = read('all_seasons_scorecard_bowling.csv').loc[lambda d: d.match_id.eq(match_id)]
    validate_bowling(old_bowl, new_bowl)
    official = {str(r['id']): r['statistics'] for r in season_fielding}
    aggregate = apply_catch_deltas(read('all_seasons_fielding.csv'), delta, official, season_id, team_id)
    scoped = aggregate.loc[aggregate.season_id.eq(season_id) & aggregate.team_id.eq(team_id)]
    for row in scoped.to_dict('records'):
        if row['player_id'] in official and float(row['fieldingTotalCatches']) != float(official[row['player_id']]['fieldingTotalCatches']):
            raise ValueError('Official season catches contain another unresolved correction')
    updates = {}
    if delta:
        updates['all_seasons_fielding.csv'] = aggregate
        replacement = new_field.reindex(columns=old_fields.columns).fillna('')
        updates['all_seasons_scorecard_fielding.csv'] = replace_match_rows(old_fields, replacement, match_id)
        raw = frames['all_scorecard_fielding'].loc[lambda d: d.participant_id.isin(delta)].copy()
        raw['catches'] = raw.participant_id.map(delta)
        raw['stumpings'] = raw['run_outs'] = raw['assisted_run_outs'] = 0
        prepared = profile.prepare_fielding({'fielding': raw, 'matches': matches}, club_id='fvcc')
        increments = profile.build_performance_breakdown(pd.DataFrame(), pd.DataFrame(), prepared, pd.DataFrame())
        updates['player_profile/performance_breakdown_by_dimension.csv'] = update_breakdown(read('player_profile/performance_breakdown_by_dimension.csv'), increments)
    if descriptions:
        updates['all_seasons_scorecard_batting.csv'] = batting
    return updates, {'match_id': match_id, 'catch_deltas': delta, 'dismissal_changes': descriptions, 'new_matches': 0, 'new_appearances': 0}


def apply(scorecard_path, season_fielding_path, evidence_dir, club_id='fvcc'):
    if club_id != 'fvcc':
        raise ValueError('FVCC-only correction boundary')
    scorecard = json.loads(scorecard_path.read_text())
    season_fielding = json.loads(season_fielding_path.read_text())
    processed = ROOT / 'clubs/fvcc/data/processed'
    signature = hashlib.sha256(scorecard_path.read_bytes() + season_fielding_path.read_bytes()).hexdigest()
    journal_path = evidence_dir / 'transaction.json'
    journal = json.loads(journal_path.read_text()) if journal_path.exists() else None
    if journal and journal['phase'] == 'pending':
        replay_transaction(processed, evidence_dir, journal, signature)
        report = journal['report']
        changed = True
    else:
        updates, report = plan(scorecard, season_fielding, club_id)
        changed = bool(updates)
        if changed:
            journal = stage_transaction(processed, updates, evidence_dir, signature, report)
            replay_transaction(processed, evidence_dir, journal, signature)
    from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
    from src.ui import layout
    if changed or load_prepared_hall_of_fame_core('fvcc', layout.HALL_OF_FAME_DATA_VERSION) is None:
        # A fresh local process loads the fallback without clearing any cache.
        os.environ['SCOREBOOK_IGNORE_PREPARED_HOF'] = '1'
        from src.data.hall_of_fame_prepared import write_prepared_hall_of_fame_core
        data = layout.load_hall_of_fame_data(0, 0, layout.HALL_OF_FAME_DATA_VERSION, club_id='fvcc')
        if data is None:
            raise RuntimeError('Prepared HOF fallback unavailable')
        write_prepared_hall_of_fame_core('fvcc', layout.HALL_OF_FAME_DATA_VERSION,
            {key: data[key] for key in ['batting', 'bowling', 'fielding', 'all_time']},
            layout.best_batting_season(data['batting_raw']), layout.best_bowling_season(data['bowling_raw']))
    version_path = processed / 'metadata/fvcc_data_version.json'
    version = json.loads(version_path.read_text())
    if changed or version.get('last_source_correction', {}).get('source_sha256') != signature:
        version['generated_app_facing_data_version'] = 'fvcc-fielding-correction-' + signature
        version['last_source_correction'] = {'match_id': report['match_id'], 'source_sha256': signature, 'policy': 'existing-match-catches-v1'}
        atomic_write(version_path, (json.dumps(version, indent=2) + '\n').encode())
    if journal and journal['phase'] == 'pending':
        journal['phase'] = 'complete'
        atomic_write(journal_path, (json.dumps(journal, indent=2) + '\n').encode())
    evidence_dir.mkdir(parents=True, exist_ok=True)
    (evidence_dir / 'correction_result.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scorecard', type=Path, required=True)
    parser.add_argument('--season-fielding', type=Path, required=True)
    parser.add_argument('--evidence-dir', type=Path, required=True)
    parser.add_argument('--apply', action='store_true', help='Write the verified correction; default is plan-only')
    args = parser.parse_args()
    if args.evidence_dir.resolve().is_relative_to(ROOT):
        parser.error('Private audit evidence must remain outside the repository')
    if args.apply:
        result = apply(args.scorecard, args.season_fielding, args.evidence_dir)
    else:
        _, result = plan(json.loads(args.scorecard.read_text()), json.loads(args.season_fielding.read_text()))
    print(json.dumps(result, indent=2))
