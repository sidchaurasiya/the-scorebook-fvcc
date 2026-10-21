"""Read-only hosting feasibility probe. Never builds, stages, pushes or reboots.

Source receipts stay in a temporary directory. Public logs contain only counts,
fixture IDs and hashes. This probe is not a release eligibility authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['SCOREBOOK_RUNTIME_IDENTITY_MAINTENANCE'] = '0'
from src.config.club_config import load_club_config
from src.data.match_centre_fetcher import PoliteMatchCentreFetcher
from src.data.match_centre_parser import MatchCentrePayloads, parse_match_payloads

CLUBS = [('GRDCC', 'georges-river-district', 'Australia/Sydney'),
         ('GWHCC', 'glen-waverley-hawks', 'Australia/Melbourne'),
         ('FVCC', 'fvcc', 'Australia/Melbourne')]


def fingerprint(frames):
    """Probe-only statistical digest; excludes names and unused rate fields.

    Includes participant IDs privately in the hash. It cannot establish parity
    with the published CSV schema without a reviewed baseline adapter.
    """
    ignored = {'strike_rate', 'economy', 'batting_minutes'}
    tables = {}
    for name in ['all_match_innings', 'all_scorecard_batting',
                 'all_scorecard_bowling', 'all_scorecard_fielding', 'all_fall_of_wickets']:
        frame = frames[name]
        columns = sorted(c for c in frame.columns if 'name' not in c and c not in ignored)
        rows = json.loads(frame[columns].to_json(orient='records'))
        tables[name] = sorted(rows, key=lambda r: json.dumps(r, sort_keys=True))
    return hashlib.sha256(json.dumps(tables, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def check_club(short, club, zone, cutoff, directory):
    result = {'club': short, 'source_cutoff_utc': cutoff.isoformat(),
              'source_cutoff_local': cutoff.astimezone(ZoneInfo(zone)).isoformat(),
              'scope': 'one official current-season team; not full club discovery',
              'statistical_publication': 'disabled'}
    fetcher = PoliteMatchCentreFetcher(timeout_seconds=25, sleep_seconds=.5)
    counter = 0

    def get(path, params=None):
        nonlocal counter
        counter += 1
        payload, receipt = fetcher.get_json(path, {'jsconfig': 'eccn:true', **(params or {})},
            directory / f'{short}-{counter}.json', name='feasibility_probe')
        if receipt.status_code != 200 or not isinstance(payload, dict):
            raise ValueError('Unverified source response')
        return payload

    org = load_club_config(club)['club']['playcricket_club_id']
    seasons = get(f'/fixturesladders/organisations/{org}/seasons')['seasons']
    current = [s for s in seasons if s.get('isCurrentSeason')]
    if len(current) != 1:
        raise ValueError('Current season ambiguous')
    season = current[0]
    teams = get(f'/fixturesladders/organisations/{org}/teams', {'seasonId': season['id']})['teams']
    if not teams:
        raise ValueError('No current teams')
    team = sorted(teams, key=lambda t: t['id'])[0]
    fixtures = get(f"/scores/teams/{team['id']}/matches", {'seasonId': season['id']})['matches']
    result.update(current_season=season['name'], official_team_count=len(teams),
                  fixture_count_checked=len(fixtures), fixture_status_counts=dict(Counter(m.get('status', '') for m in fixtures)))
    data = ROOT / 'clubs' / club / 'data'
    metadata = json.loads((data / 'metadata.json').read_text())
    result['published_manifest_present'] = bool(metadata.get('incremental_refresh'))
    matches_path = data / 'processed/season_overview/season_by_round_scorecards.csv'
    import pandas as pd
    published = pd.read_csv(matches_path)
    published_ids = set(published.loc[published.season.eq(season['name']), 'match_id'].astype(str))
    result['published_current_finalized_ids'] = len(published_ids)
    final = []
    for fixture in fixtures:
        dates = [datetime.fromisoformat(day['startDateTime'].replace('Z', '+00:00'))
                 for day in fixture.get('matchSchedule', []) if day.get('startDateTime')]
        if dates and all(d.tzinfo for d in dates) and min(dates) <= cutoff and fixture.get('status') in {'COMPLETED', 'ABANDONED'}:
            final.append(fixture)
    result['finalized_status_candidates_in_sample'] = len(final)
    result['unpublished_status_candidates_in_sample'] = sorted(f['id'] for f in final if f['id'] not in published_ids)
    result['pending_fixture_ids_in_sample'] = sorted(f['id'] for f in fixtures if f.get('status') in {'LIVE', 'STUMPS', 'IN PROGRESS', 'PENDING'})
    if final:
        sample = sorted(final, key=lambda f: (f['id'] not in published_ids, f['id']))[0]
        score = get(f"/scores/matches/{sample['id']}", {'responseModifier': 'includeScorecard'})
        if score.get('status') != sample['status'] or score.get('id') != sample['id']:
            raise ValueError('Fixture/scorecard identity or final status disagreement')
        payload = MatchCentrePayloads(manifest={'season_id': season['id'], 'team_id': team['id']},
            scorecard=score, balls={}, officials={})
        first = parse_match_payloads(payload)
        second = parse_match_payloads(payload)
        one, two = fingerprint(first), fingerprint(second)
        if one != two:
            raise ValueError('Parser digest nondeterministic')
        result.update(sample_finalized_match=sample['id'], parsed_scorecard_fingerprint=one,
                      parser_repeat_deterministic=True, ball_by_ball_fetched=False)
    result.update(source_access='PASS', published_semantic_parity='BLOCKED: reviewed published contribution manifests absent',
                  full_candidate_build='NOT RUN: external frozen bundle/seed prerequisites absent', requests=counter)
    return result


def main():
    cutoff = datetime.now(timezone.utc)
    report = {'probe_only': True, 'started_utc': cutoff.isoformat(), 'clubs': []}
    with tempfile.TemporaryDirectory(prefix='scorebook-probe-') as tmp:
        for short, club, zone in CLUBS:
            try:
                result = check_club(short, club, zone, cutoff, Path(tmp))
            except Exception as error:
                # Never dump source response bodies or player details in public logs.
                result = {'club': short, 'source_access': 'BLOCKED', 'error_type': type(error).__name__}
            report['clubs'].append(result)
            print(json.dumps(result, sort_keys=True), flush=True)
    output = Path(os.environ.get('RUNNER_TEMP', tempfile.gettempdir())) / 'scorebook-hosted-probe.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write('## Read-only Scorebook hosting probe\n\n```json\n'+json.dumps(report, indent=2)+'\n```\n')
    return int(any(r['source_access'] != 'PASS' for r in report['clubs']))


if __name__ == '__main__':
    raise SystemExit(main())
