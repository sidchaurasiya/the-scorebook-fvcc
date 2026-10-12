"""Build a governed FVCC candidate from a frozen, disjoint source bundle.

Historical source rows and sufficient statistics are retained. This offline
builder uses existing club-aware exporters and never fetches or publishes data.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CLUB = 'fvcc'


def append_disjoint(old, new, keys):
    if new.empty:
        return old.copy()
    if old.duplicated(keys).any() or new.duplicated(keys).any():
        raise ValueError(f'Duplicate contribution keys: {keys}')
    if not old[keys].merge(new[keys], on=keys, how='inner').empty:
        raise ValueError(f'Overlapping contribution keys: {keys}')
    return pd.concat([old, new], ignore_index=True, sort=False)


def scored_participation(payloads, team_ids, cutoff):
    rows = []
    for payload in payloads:
        date = pd.Timestamp(payload['matchSchedule'][0]['startDateTime'])
        if payload.get('status') not in {'COMPLETED', 'ABANDONED'} or date > pd.Timestamp(cutoff):
            raise ValueError('Non-finalized or after-cutoff scorecard')
        innings = payload.get('innings', [])
        if not any(i.get('batting') or i.get('bowling') for i in innings):
            raise ValueError('Final result has no verified scored participation')
        for team in payload.get('teams', []):
            if team['id'] not in team_ids:
                continue
            for player in team.get('players', []):
                if not player.get('participantId'):
                    raise ValueError('Missing source participant ID')
                rows.append({'match_id':payload['id'], 'team_id':team['id'],
                             'player_id':player['participantId'], 'player_name':player['name']})
    return pd.DataFrame(rows).drop_duplicates(['match_id','team_id','player_id'])


def build(bundle: Path, candidate: Path, baseline_root: Path = ROOT):
    if candidate.exists() or candidate == ROOT or ROOT in candidate.parents:
        raise ValueError('Candidate must be a new outside-repository directory')
    os.environ['CLUB_ID'] = CLUB
    os.environ['SCOREBOOK_RUNTIME_IDENTITY_MAINTENANCE'] = '0'
    from src.config import club_config as config
    from src.data.playcricket_ingestion import normalize_players, normalize_seasons, normalize_teams
    from src.utils.player_identity import apply_player_identity_mapping, filter_public_player_rows
    # Pure disjoint sufficient-statistic merger; no GRDCC identity/count policy.
    from scripts.grdcc_incremental_summaries import merge_summary

    state = json.loads((bundle/'task_state.json').read_text())
    discovery = json.loads((bundle/'discovery.json').read_text())
    parsed_matches = pd.read_csv(bundle/'parsed_current/all_matches.csv')
    season_ids = set(parsed_matches['season_id'].dropna().astype(str))
    if len(season_ids) != 1:
        raise ValueError('Bundle must contain exactly one disjoint statistical season')
    season = next(s for s in discovery['seasons'] if s['id'] in season_ids)
    selected_teams = [t for t in discovery['teams'] if t['season_id'] == season['id']]
    team_ids = {t['id'] for t in selected_teams}
    payloads = [json.loads((bundle/'source_payloads'/f'match={mid}__scorecard.json').read_text())['payload']
                for mid in state['new_match_ids']]
    appearances = scored_participation(payloads, team_ids, state['cutoff_utc'])
    frames = {key:pd.read_csv(bundle/'parsed_current'/f'{filename}.csv', low_memory=False)
              for key,filename in {'matches':'all_matches', 'innings':'all_match_innings', 'batting':'all_scorecard_batting',
                                   'bowling':'all_scorecard_bowling', 'fielding':'all_scorecard_fielding',
                                   'balls':'all_ball_by_ball', 'partnerships':'all_partnerships', 'overs':'all_overs'}.items()}
    history_ids = set(pd.read_csv(baseline_root/'clubs/fvcc/data/processed/season_overview/season_by_round_scorecards.csv')['match_id'])
    increment_ids = set(frames['matches']['match_id'])
    if history_ids & increment_ids or len(increment_ids) != len(frames['matches']):
        raise ValueError('Historical/current match partitions overlap or contain duplicates')
    shutil.copytree(baseline_root/'clubs/fvcc',candidate/'clubs/fvcc')
    shutil.copytree(bundle/'baseline/data',candidate/'data')
    processed = candidate/'clubs/fvcc/data/processed'
    for kind in ['batting','bowling','fielding']:
        old = pd.read_csv(processed/f'all_seasons_{kind}.csv',low_memory=False)
        if old['season_id'].eq(season['id']).any():
            raise ValueError('New season already exists; incremental append would duplicate statistics')
    config.REPO_ROOT = candidate
    config.CLUBS_ROOT = candidate/'clubs'
    config._load_club_config_cached.cache_clear()

    old_seasons = pd.read_csv(processed/'seasons.csv')
    current_flags={s['id']:bool(s.get('isCurrentSeason')) for s in discovery['seasons']}
    old_seasons['isCurrentSeason']=old_seasons['id'].map(current_flags).fillna(old_seasons['isCurrentSeason'])
    seasons = normalize_seasons([season])
    append_disjoint(old_seasons, seasons, ['id']).sort_values('startDate',ascending=False).to_csv(processed/'seasons.csv',index=False)
    teams = normalize_teams(selected_teams)
    append_disjoint(pd.read_csv(processed/'teams.csv'), teams, ['season_id','team_id']).to_csv(processed/'teams.csv',index=False)
    aggregates = {}
    participation = appearances.groupby(['team_id','player_id'])['match_id'].nunique()
    identities = []
    baseline_canonical = set(pd.read_csv(bundle/'baseline_public_index.csv')['id'])
    for kind in ['batting','bowling','fielding']:
        current = pd.read_csv(bundle/f'current_aggregate_{kind}.csv')
        current = current[current['season_id'].eq(season['id'])].copy()
        current['provider_appearance_count'] = current['matches']
        current['matches'] = [participation.get((r.team_id,r.player_id),0) for r in current.itertuples()]
        current = current[current['matches'].gt(0)].copy()
        current = apply_player_identity_mapping(current, club_id=CLUB)
        if kind == 'batting':
            for row in current.drop_duplicates('player_id').to_dict('records'):
                identities.append({k:row[k] for k in ['player_id','player_name','canonical_player_id','canonical_player_name']})
        aggregates[kind] = append_disjoint(pd.read_csv(processed/f'all_seasons_{kind}.csv'), current, ['season_id','team_id','player_id'])
        aggregates[kind].to_csv(processed/f'all_seasons_{kind}.csv',index=False)
    identity = pd.DataFrame(identities)
    identity['decision'] = identity['canonical_player_id'].map(lambda value:'existing_approved_identity' if value in baseline_canonical else 'new_source_identity')
    identity.to_csv(bundle/'identity_reconciliation.csv',index=False)
    players = normalize_players(aggregates)
    old_players = pd.read_csv(processed/'players.csv')
    pd.concat([old_players[~old_players['player_id'].isin(players['player_id'])],players],ignore_index=True).to_csv(processed/'players.csv',index=False)

    from scripts import build_club_app_facing_scorecards as cards
    from scripts import build_player_profile_insight_exports as profile
    from scripts import build_season_overview_detail_exports as seasons_export
    from scripts import build_hall_of_fame_detail_exports as hof
    from src.ui import layout
    captains = {}
    for payload in payloads:
        for team in payload['teams']:
            if team['id'] in team_ids:
                captains[payload['id']] = profile.scorecard_team_captain_name(team)
    frames['matches']['club_captain_name'] = frames['matches']['match_id'].map(captains).fillna('')
    score_outputs = {
        'all_seasons_matches.csv':cards.build_match_rows(frames['matches'],frames['innings'],teams),
        'all_seasons_scorecard_batting.csv':cards.build_batting_rows(frames['batting'],frames['matches'],team_ids),
        'all_seasons_scorecard_bowling.csv':cards.build_bowling_rows(frames['bowling'],frames['matches'],team_ids),
        'all_seasons_scorecard_fielding.csv':cards.build_fielding_rows(frames['fielding'],frames['matches'],team_ids),
    }
    for filename,current in score_outputs.items():
        old = pd.read_csv(processed/filename)
        if set(old.get('match_id',[])) & increment_ids:
            raise ValueError('Scorecard overlap')
        pd.concat([old,current],ignore_index=True,sort=False).to_csv(processed/filename,index=False)
    batting = filter_public_player_rows(profile.prepare_batting(frames, club_id=CLUB))
    bowling = filter_public_player_rows(profile.prepare_bowling(frames, club_id=CLUB))
    fielding = filter_public_player_rows(profile.prepare_fielding(frames, club_id=CLUB))
    balls = profile.prepare_ball_rows(frames, club_id=CLUB)
    totals = frames['balls'].groupby('innings_id')['total_runs'].sum(min_count=1)
    reconciled = frames['innings']['innings_id'][frames['innings']['runs_scored'].eq(frames['innings']['innings_id'].map(totals))]
    phase_frames = dict(frames, balls=frames['balls'][frames['balls']['innings_id'].isin(reconciled)].copy())
    phase_balls = profile.prepare_ball_rows(phase_frames, club_id=CLUB)
    paths = []
    def summary(relative,current,keys):
        path = processed/relative
        old = pd.read_csv(path,low_memory=False)
        current = filter_public_player_rows(current)
        result = merge_summary(old,current,keys,history_ids,increment_ids)
        # Extras counters are additive too; the existing pure merger predates
        # their export. Update only keys with verified new bowling figures.
        old_lookup = {tuple(r[k] for k in keys):r for r in old.to_dict('records')}
        delta_lookup = {tuple(r[k] for k in keys):r for r in current.to_dict('records')}
        for index, row in result.iterrows():
            key = tuple(row[k] for k in keys)
            if key not in old_lookup or key not in delta_lookup:
                continue
            for column in ['wides','no_balls']:
                if column in result:
                    a, b = old_lookup[key].get(column), delta_lookup[key].get(column)
                    if pd.notna(b):
                        result.loc[index,column] = a+b if pd.notna(a) else pd.NA
        result.to_csv(path,index=False)
        paths.append(relative)
        return result
    perf = summary('player_profile/performance_breakdown_by_dimension.csv',profile.build_performance_breakdown(batting,bowling,fielding,balls),
                   ['canonical_player_id','canonical_player_name','display_player_name','dimension','discipline','breakdown_label'])
    is_bowler = perf['discipline'].eq('Bowling')
    perf.loc[is_bowler,'extras_pct'] = perf.loc[is_bowler].apply(lambda r:layout.calculate_extras_pct(r['no_balls'],r['wides'],r['balls_bowled']),axis=1)
    perf.to_csv(processed/'player_profile/performance_breakdown_by_dimension.csv',index=False)
    summary('player_profile/batting_position_summary.csv',profile.build_batting_position_summary(batting),['canonical_player_id','canonical_player_name','display_player_name','position_group'])
    summary('player_profile/bowling_phase_summary.csv',profile.build_bowling_phase_summary(bowling,phase_balls),['canonical_player_id','canonical_player_name','display_player_name','phase_model','phase'])
    summary('player_profile/dismissal_fingerprint_summary.csv',profile.build_dismissal_fingerprint_summary(batting),['canonical_player_id','canonical_player_name','display_player_name','scope','dismissal_bucket'])
    for kind, current in [('batting',profile.build_recent_form_batting(batting)),('bowling',profile.build_recent_form_bowling(bowling))]:
        path = processed/f'player_profile/recent_form_{kind}.csv'
        old = pd.read_csv(path)
        if set(old['match_id']) & set(current['match_id']):
            raise ValueError('Recent Form overlap')
        pd.concat([old,current],ignore_index=True).to_csv(path,index=False)
    season_outputs = {
        'scorecard_batting_milestones_by_scope.csv':seasons_export.build_scorecard_batting(frames,club_id=CLUB),
        'scorecard_bowling_milestones_by_scope.csv':seasons_export.build_scorecard_bowling(frames,club_id=CLUB),
        'bbb_batting_rates_by_scope.csv':seasons_export.build_bbb_batting(frames,club_id=CLUB),
        'bbb_bowling_dot_rates_by_scope.csv':seasons_export.build_bbb_bowling(phase_frames,club_id=CLUB),
        'season_by_round_scorecards.csv':seasons_export.build_season_by_round(frames,club_id=CLUB),
    }
    for filename,current in season_outputs.items():
        path = processed/'season_overview'/filename
        old = pd.read_csv(path)
        if old['season'].eq(season['name']).any():
            raise ValueError('Season detail overlap')
        pd.concat([old,filter_public_player_rows(current)],ignore_index=True,sort=False).to_csv(path,index=False)
    summary('hall_of_fame/player_bbb_batting_rates.csv',hof.build_player_bbb_batting_rates(batting,balls),['canonical_player_id','canonical_player_name','display_player_name'])
    summary('hall_of_fame/player_scorecard_milestones.csv',hof.build_player_scorecard_milestones(batting),['canonical_player_id','canonical_player_name','display_player_name'])
    summary('hall_of_fame/player_bowling_milestones.csv',hof.build_player_bowling_milestones(bowling),['canonical_player_id','canonical_player_name','display_player_name'])
    mapped = filter_public_player_rows(apply_player_identity_mapping(appearances,club_id=CLUB))
    mapped['display_player_name'] = mapped['canonical_player_name']
    summary('hall_of_fame/player_win_rates.csv',hof.build_player_win_rates(frames['matches'],mapped,pd.DataFrame(),pd.DataFrame(),club_id=CLUB),['canonical_player_id','canonical_player_name','display_player_name'])
    path = processed/'hall_of_fame/scorecard_record_links.csv'
    pd.concat([pd.read_csv(path),hof.build_scorecard_record_links(batting,bowling)],ignore_index=True).to_csv(path,index=False)

    from src.data.fastest_innings import build_governed_fastest_innings
    from src.data.partnerships import build_governed_club_partnerships, build_verified_partnership_record_holders
    from src.data.hat_tricks import build_governed_club_hat_tricks
    from src.config.club_config import get_mapping_path
    fastest = build_governed_fastest_innings(club_id=CLUB,processed_root=bundle,players_path=processed/'players.csv',
                                            aliases_path=get_mapping_path('player_aliases.csv',club_id=CLUB),club_team_ids=team_ids,club_name_token=config.get_club_name(CLUB))
    path = processed/'hall_of_fame/fastest_batting_milestones.csv'
    pd.concat([pd.read_csv(path),fastest.governance.published],ignore_index=True,sort=False).to_csv(path,index=False)
    partnerships = build_governed_club_partnerships(club_id=CLUB,match_centre_root=bundle)
    path = processed/'hall_of_fame/partnerships.csv'
    events = pd.concat([pd.read_csv(path),partnerships.events],ignore_index=True,sort=False)
    events.to_csv(path,index=False)
    records, audit = build_verified_partnership_record_holders(events)
    records.to_csv(processed/'hall_of_fame/partnership_records.csv',index=False)
    hats = build_governed_club_hat_tricks(club_id=CLUB,match_centre_root=bundle,club_processed_root=processed)
    path = processed/'hall_of_fame/hat_tricks.csv'
    pd.concat([pd.read_csv(path),hats.events],ignore_index=True,sort=False).to_csv(path,index=False)
    result = {'new_matches':len(increment_ids),'appearances':len(appearances),'public_new_identities':int(identity['decision'].eq('new_source_identity').sum()),
              'new_fastest_rows':len(fastest.governance.published),'new_partnership_events':len(partnerships.events),'new_hat_tricks':len(hats.events)}
    fastest.detector_validation.to_csv(bundle/'current_fastest_validation.csv',index=False)
    partnerships.reconciliation_audit.to_csv(bundle/'current_partnership_audit.csv',index=False)
    hats.validation.to_csv(bundle/'current_hat_trick_validation.csv',index=False)
    (bundle/'candidate_generation.json').write_text(json.dumps(result,indent=2))
    metadata_path = candidate/'clubs/fvcc/data/metadata.json'
    metadata = json.loads(metadata_path.read_text())
    metadata.update(seasons_fetched=json.loads((bundle/'source_payloads/seasons.json').read_text())['payload']['seasons'],
                    matches_fetched=len(pd.read_csv(processed/'season_overview/season_by_round_scorecards.csv')),
                    players_fetched=len(pd.read_csv(processed/'players.csv')),teams_fetched=len(pd.read_csv(processed/'teams.csv')),
                    stat_rows={k:len(v) for k,v in aggregates.items()},
                    incremental_refresh={'cutoff_utc':state['cutoff_utc'],'cutoff_melbourne':state['cutoff_melbourne'],
                                         'new_match_ids':sorted(increment_ids),'historical_rows_preserved':True,
                                         'provider_cancelled_appearances_excluded':True})
    receipt = max(json.loads(p.read_text())['request']['fetched_at'] for p in (bundle/'source_payloads').glob('*.json'))
    metadata['fetch_date_time'] = metadata['last_successful_refresh_time'] = receipt
    metadata_path.write_text(json.dumps(metadata,indent=2)+'\n')
    version_path = processed/'metadata/fvcc_data_version.json'
    version = json.loads(version_path.read_text())
    latest = frames['matches'].sort_values(['first_match_day','match_id']).iloc[-1]
    version.update(generated_app_facing_data_version=receipt,latest_refresh_timestamp=receipt,validator_status='pending',
                   cutoff_utc=state['cutoff_utc'],cutoff_melbourne=state['cutoff_melbourne'],new_match_ids=sorted(increment_ids),
                   latest_match_id=latest['match_id'],latest_match_date=latest['first_match_day'],
                   latest_match_round=latest.get('round_short_name',latest.get('round_name','')),
                   latest_match_result=latest.get('result_text',''),latest_statistical_season=season['name'])
    version_path.write_text(json.dumps(version,indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-bundle',type=Path,required=True)
    parser.add_argument('--candidate-root',type=Path,required=True)
    parser.add_argument('--baseline-root',type=Path,default=ROOT)
    args = parser.parse_args()
    print(json.dumps(build(args.source_bundle,args.candidate_root,args.baseline_root),indent=2))
