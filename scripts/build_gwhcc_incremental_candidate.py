"""Build a disjoint-season Hawks candidate outside the repository.

Input is the checkpointed official-source bundle (parsed_current and cached
scorecards/aggregates). No fetching, historical reconstruction, or publication
occurs here. Acceptance requires a separate source/preservation validation.
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
CLUB = 'glen-waverley-hawks'


def update_metadata(bundle: Path, candidate: Path, cutoff: str) -> None:
    data = candidate / 'clubs' / CLUB / 'data'
    path = data / 'metadata.json'
    metadata = json.loads(path.read_text())
    fetched = [json.loads(file.read_text()).get('request', {}).get('fetched_at', '')
               for file in (bundle / 'source_payloads').glob('*.json')]
    fetched_at = max(fetched)
    metadata['fetch_date_time'] = fetched_at
    metadata['last_successful_refresh_time'] = fetched_at
    metadata['matches_fetched'] = len(pd.read_csv(data / 'processed/all_seasons_matches.csv'))
    metadata['players_fetched'] = len(pd.read_csv(data / 'processed/players.csv'))
    metadata['teams_fetched'] = len(pd.read_csv(data / 'processed/teams.csv'))
    metadata['stat_rows'] = {kind:len(pd.read_csv(data / f'processed/all_seasons_{kind}.csv')) for kind in ['batting','bowling','fielding']}
    season = json.loads((bundle / 'task_state.json').read_text())['season']
    metadata['incremental_refresh'] = {'season': season['name'], 'cutoff': cutoff,
                                       'timezone':'Australia/Melbourne', 'source':'PlayCricket public scorecards and team statistics',
                                       'cached_source_payload_count':len(fetched),
                                       'historical_source_rows_preserved':True}
    metadata['source_endpoints_used'] = list(dict.fromkeys([
        *metadata.get('source_endpoints_used', []),
        '/scores/teams/{team_id}/matches',
        '/scores/matches/{match_id}?responseModifier=includeScorecard',
        '/scores/matches/{match_id}/balls',
    ]))
    metadata['notes'] = [note for note in metadata.get('notes', []) if not note.startswith('Public match/result/scorecard endpoints were not available')]
    for note in [
        'Current-season source-backed incremental refresh; historical match, Captain, premiership and governed career evidence retained.',
        'Request counters describe the prior full backup; the incremental build reads cached current-season source receipts.',
    ]:
        if note not in metadata['notes']:
            metadata['notes'].append(note)
    path.write_text(json.dumps(metadata, indent=2) + '\n')


def build(bundle: Path, candidate: Path, cutoff: str, baseline_root: Path = ROOT) -> dict:
    if candidate == ROOT or ROOT in candidate.parents or candidate.exists():
        raise ValueError('Candidate must be a new outside-repository directory')
    os.environ['CLUB_ID'] = CLUB
    from src.data.gwhcc_incremental import append_disjoint, eligible_match_ids, merge_summary, reconciled_delivery_innings, preserve_compact_dismissal_type, profile_fielding_input
    from src.config import club_config as config
    from src.data.playcricket_ingestion import normalize_teams, normalize_players
    from src.utils.player_identity import apply_player_identity_mapping, filter_public_player_rows
    from src.data.gwhcc_governance import annotate_grade_metadata

    club = baseline_root / 'clubs' / CLUB
    output_club = candidate / 'clubs' / CLUB
    shutil.copytree(club, output_club)
    processed = output_club / 'data/processed'
    state = json.loads((bundle / 'task_state.json').read_text())
    season = state['season']
    cache = bundle / 'source_payloads'
    team_receipt = json.loads((cache / 'teams_2026_27.json').read_text())
    organization = config.load_club_config(CLUB)['club']['playcricket_club_id']
    if f'/organisations/{organization}/teams' not in team_receipt['request']['url']:
        raise ValueError('Team receipt is not from the configured GWHCC organization')
    teams_payload = team_receipt['payload']['teams']
    frames = {key: pd.read_csv(bundle / 'parsed_current' / f'{filename}.csv', low_memory=False)
              for key, filename in {'matches':'all_matches', 'innings':'all_match_innings', 'batting':'all_scorecard_batting',
                                    'bowling':'all_scorecard_bowling', 'fielding':'all_scorecard_fielding',
                                    'balls':'all_ball_by_ball', 'overs':'all_overs', 'partnerships':'all_partnerships'}.items()}
    if not frames['matches']['season_id'].eq(season['id']).all() or not frames['matches']['season'].eq(season['name']).all():
        raise ValueError('Parsed matches and declared source season disagree')
    included = eligible_match_ids(frames['matches'], frames['innings'], cutoff)
    historical = pd.read_csv(processed / 'all_seasons_matches.csv')
    if included & set(historical['match_id']):
        raise ValueError('Match overlap with historical application data')
    if any(pd.read_csv(processed / f'all_seasons_{kind}.csv')['season'].eq(season['name']).any()
           for kind in ['batting','bowling','fielding']):
        raise ValueError('Season already contains statistics; changed-season reconciliation required')
    frames = {key: frame[frame['match_id'].isin(included)].copy() for key, frame in frames.items()}
    # All decisions must be explicitly source-ID scoped and approved outside UI.
    approvals = pd.read_csv(bundle / 'approved_identity_mappings.csv', dtype=str).fillna('')
    if not approvals['decision_status'].eq('customer_confirmed').all():
        raise ValueError('Unapproved identity mapping')
    baseline_ids = set(pd.read_csv(processed / 'hall_of_fame/prepared_career_all_time.csv')['canonical_player_id'])
    if not set(approvals['canonical_player_id']) <= baseline_ids:
        raise ValueError('Identity continuity approval targets a nonexistent historical public profile')
    aliases_path = output_club / 'player_aliases.csv'
    aliases = pd.read_csv(aliases_path, dtype=str).fillna('')
    additions = []
    for row in approvals.to_dict('records'):
        additions.append({column: row.get(column, '') for column in aliases.columns})
    aliases = append_disjoint(aliases, pd.DataFrame(additions), ['raw_player_id'])
    aliases.to_csv(aliases_path, index=False)

    config.REPO_ROOT = candidate
    config.CLUBS_ROOT = candidate / 'clubs'
    config._load_club_config_cached.cache_clear()
    selected = {str(row.match_id): set(str(row.source_team_ids).split('|')) for row in frames['matches'].itertuples()}
    team_ids = {team['id'] for team in teams_payload}
    captains, participation = {}, []
    from src.data.gwhcc_match_policy import match_format
    for match in frames['matches'].to_dict('records'):
        payload = json.loads((cache / f"match={match['match_id']}__scorecard.json").read_text())['payload']
        weight = 0.5 if match_format(pd.Series(match)) == 'T20' else 1.0
        for team in payload.get('teams', []):
            if team['id'] not in selected[match['match_id']]:
                continue
            for player in team.get('players', []):
                if player.get('participantId'):
                    participation.append({'match_id':match['match_id'], 'team_id':team['id'], 'player_id':player['participantId'],
                                          'player_name':player.get('name',''), 'weight':weight})
                if 'Captain' in player.get('roles', []):
                    captains[match['match_id']] = player.get('name','')
    appearances = pd.DataFrame(participation).drop_duplicates(['match_id','team_id','player_id'])
    frames['matches']['club_captain_name'] = frames['matches']['match_id'].map(captains).fillna('')
    weights = appearances.groupby(['team_id','player_id'])['weight'].sum()
    new_teams = []
    for team in teams_payload:
        row = dict(team, season_id=season['id'], season=season['name'])
        new_teams.append(row)
    teams = normalize_teams(new_teams)
    teams = annotate_grade_metadata(teams, 'grade_name')
    old_teams = pd.read_csv(processed / 'teams.csv')
    pd.concat([old_teams[~old_teams['season_id'].eq(season['id'])], teams], ignore_index=True).to_csv(processed / 'teams.csv', index=False)
    aggregate_parts = {}
    for kind in ['batting','bowling','fielding']:
        new = pd.read_csv(bundle / f'current_aggregate_{kind}.csv')
        if not new['team_id'].isin(team_ids).all() or not new['season_id'].eq(season['id']).all():
            raise ValueError('Aggregate rows fall outside the discovered current GWHCC scope')
        new['raw_playhq_matches'] = new['matches']
        new['matches'] = [weights.get((row.team_id, row.player_id), 0) for row in new.itertuples()]
        new = new[new['matches'].gt(0)].copy()
        new['season_start_date'] = season['startDate']
        new['competition_name'] = new['grade_name']
        new = annotate_grade_metadata(apply_player_identity_mapping(new, club_id=CLUB), 'grade_name')
        new['record_scope'] = 'Whole club'
        new['match_count_policy_note'] = 'T20=0.5; played non-T20=1; no-play=0'
        old = pd.read_csv(processed / f'all_seasons_{kind}.csv', low_memory=False)
        combined = append_disjoint(old, new, ['season_id','team_id','player_id'])
        combined.to_csv(processed / f'all_seasons_{kind}.csv', index=False)
        aggregate_parts[kind] = combined
    players = normalize_players(aggregate_parts)
    old_players = pd.read_csv(processed / 'players.csv')
    # Keep historical-only identities absent from provider aggregate source.
    players = pd.concat([old_players[~old_players['player_id'].isin(players['player_id'])], players], ignore_index=True)
    current_players = players['player_id'].isin(appearances['player_id'])
    players.loc[current_players, 'teams_played_for'] = players.loc[current_players, 'teams_played_for'].str.rstrip()
    players.to_csv(processed / 'players.csv', index=False)

    from scripts import build_club_app_facing_scorecards as scorecards
    scorecard_outputs = {
        'all_seasons_matches.csv': scorecards.build_match_rows(frames['matches'], frames['innings'], teams),
        'all_seasons_scorecard_batting.csv': scorecards.build_batting_rows(preserve_compact_dismissal_type(frames['batting']), frames['matches'], team_ids),
        'all_seasons_scorecard_bowling.csv': scorecards.build_bowling_rows(frames['bowling'], frames['matches'], team_ids),
        'all_seasons_scorecard_fielding.csv': scorecards.build_fielding_rows(frames['fielding'], frames['matches'], team_ids),
    }
    for filename, new in scorecard_outputs.items():
        old = pd.read_csv(processed / filename, low_memory=False)
        if filename == 'all_seasons_matches.csv':
            new = annotate_grade_metadata(new, 'competition')
        if set(old['match_id']) & set(new['match_id']):
            raise ValueError('Scorecard match overlap')
        pd.concat([old, new], ignore_index=True, sort=False).to_csv(processed / filename, index=False)

    from scripts import build_player_profile_insight_exports as profile
    from scripts import build_season_overview_detail_exports as seasons
    from scripts import build_hall_of_fame_detail_exports as hof
    from src.ui import layout
    batting = profile.prepare_batting(frames, club_id=CLUB)
    bowling = profile.prepare_bowling(frames, club_id=CLUB)
    profile_fielding_frames = {**frames, 'fielding': profile_fielding_input(frames['fielding'])}
    fielding = profile.prepare_fielding(profile_fielding_frames, club_id=CLUB)
    balls = profile.prepare_ball_rows(frames, club_id=CLUB)
    bowling_frames = frames.copy()
    bowling_frames['balls'], bowling_evidence = reconciled_delivery_innings(frames['innings'], frames['balls'])
    bowling_balls = profile.prepare_ball_rows(bowling_frames, club_id=CLUB)
    bowling_evidence.to_csv(bundle/'current_bowling_delivery_evidence.csv', index=False)
    batting, bowling, fielding = [filter_public_player_rows(frame) for frame in [batting,bowling,fielding]]
    sums = ['innings','runs','outs','thirties','fifties','hundreds','ducks','fours','sixes',
            'bbb_runs','bbb_balls_faced','bbb_dismissals','bbb_batting_innings','bbb_matches',
            'matches','balls_bowled','runs_against','wickets','three_wicket_innings','five_wicket_innings','wides','no_balls',
            'catches','stumpings','run_outs','dismissals']
    rates = {'bat_avg':('runs','outs',1),'strike_rate':('bbb_runs','bbb_balls_faced',100),
             'bowl_avg':('runs_against','wickets',1),'bowl_sr':('balls_bowled','wickets',1),'eco':('runs_against','balls_bowled',6)}
    merged_paths = []
    def summary(relative, new, keys, count_columns, rate_columns=None, best=None):
        path = processed / relative
        old = pd.read_csv(path, dtype=str)
        new = filter_public_player_rows(new)
        # Established exports distinguish placeholder IDs by their source names.
        keys = list(dict.fromkeys([*keys, 'canonical_player_name', 'display_player_name']))
        result = merge_summary(old, new, keys=keys, sums=count_columns, rates=rate_columns, best=best)
        result.to_csv(path, index=False)
        merged_paths.append(relative)
        return result
    new_perf = profile.build_performance_breakdown(batting,bowling,fielding,balls)
    perf = summary('player_profile/performance_breakdown_by_dimension.csv', new_perf,
                   ['canonical_player_id','dimension','discipline','breakdown_label'], sums, rates,
                   {'high_score':profile.best_high_score_from_labels,'bbi':profile.best_bbi_from_labels})
    perf_keys = ['canonical_player_id','dimension','discipline','breakdown_label','canonical_player_name','display_player_name']
    updated_perf_keys = set(map(tuple,new_perf[perf_keys].to_numpy()))
    for index, row in perf.iterrows():
        if tuple(row[key] for key in perf_keys) not in updated_perf_keys:
            continue
        if row['discipline'] == 'Batting' and pd.notna(row.get('high_score')):
            text = str(row['high_score'])
            perf.loc[index,'high_score_sort'] = layout.parse_high_score_value(text)[0]
            perf.loc[index,'high_score_not_out_sort'] = int('*' in text)
        if row['discipline'] == 'Bowling':
            perf.loc[index,'extras_pct'] = layout.calculate_extras_pct(row['no_balls'], row['wides'], row['balls_bowled'])
    perf.to_csv(processed / 'player_profile/performance_breakdown_by_dimension.csv',index=False)
    summary('player_profile/batting_position_summary.csv', profile.build_batting_position_summary(batting),
            ['canonical_player_id','position_group'], ['innings','runs','outs'], {'average':('runs','outs',1)})
    phase = summary('player_profile/bowling_phase_summary.csv', profile.build_bowling_phase_summary(bowling,bowling_balls),
                    ['canonical_player_id','phase_model','phase'], ['legal_balls','wickets','runs_conceded','dot_balls','boundary_balls','match_count'],
                    {'avg':('runs_conceded','wickets',1),'eco':('runs_conceded','legal_balls',6),'sr':('legal_balls','wickets',1),
                     'dot_ball_pct':('dot_balls','legal_balls',100),'boundary_rate':('boundary_balls','legal_balls',100)})
    phase['overs'] = phase['legal_balls'].map(layout.format_balls_as_overs)
    phase.to_csv(processed / 'player_profile/bowling_phase_summary.csv',index=False)
    new_dismissals = profile.build_dismissal_fingerprint_summary(batting)
    dismissals = summary('player_profile/dismissal_fingerprint_summary.csv', new_dismissals,
                         ['canonical_player_id','scope','dismissal_bucket'], ['count'])
    numeric_counts = pd.to_numeric(dismissals['count'], errors='raise')
    totals = numeric_counts.groupby([dismissals['scope'], dismissals['canonical_player_id']]).transform('sum')
    affected = dismissals['canonical_player_id'].isin(new_dismissals['canonical_player_id'])
    dismissals.loc[affected, 'total_dismissals'] = totals[affected]
    dismissals.loc[affected, 'pct'] = numeric_counts[affected]*100/totals[affected]
    dismissals.to_csv(processed / 'player_profile/dismissal_fingerprint_summary.csv',index=False)
    for kind, new in [('batting',profile.build_recent_form_batting(batting)),('bowling',profile.build_recent_form_bowling(bowling))]:
        path = processed / f'player_profile/recent_form_{kind}.csv'
        old = pd.read_csv(path)
        if set(old['match_id']) & set(new['match_id']):
            raise ValueError('Recent form overlap')
        pd.concat([old,new],ignore_index=True).sort_values(['canonical_player_name','match_date','order_sort'],ascending=[True,False,True]).to_csv(path,index=False)
    season_outputs = {
        'scorecard_batting_milestones_by_scope.csv': seasons.build_scorecard_batting(frames, club_id=CLUB),
        'scorecard_bowling_milestones_by_scope.csv': seasons.build_scorecard_bowling(frames, club_id=CLUB),
        'bbb_batting_rates_by_scope.csv': seasons.build_bbb_batting(frames, club_id=CLUB),
        'bbb_bowling_dot_rates_by_scope.csv': seasons.build_bbb_bowling(bowling_frames, club_id=CLUB),
        'season_by_round_scorecards.csv': seasons.build_season_by_round(frames, club_id=CLUB),
    }
    for filename, new in season_outputs.items():
        path = processed / 'season_overview' / filename
        old = pd.read_csv(path, dtype=str)
        if old['season'].eq(season['name']).any():
            raise ValueError('Detailed season overlap')
        pd.concat([old,filter_public_player_rows(new)],ignore_index=True,sort=False).to_csv(path,index=False)
    summary('hall_of_fame/player_bbb_batting_rates.csv', hof.build_player_bbb_batting_rates(batting, balls),
            ['canonical_player_id'], ['bbb_runs','bbb_balls_faced','bbb_dismissals','bbb_batting_innings','bbb_matches'],
            {'bat_sr':('bbb_runs','bbb_balls_faced',100)})
    milestones = summary('hall_of_fame/player_scorecard_milestones.csv', hof.build_player_scorecard_milestones(batting),
                         ['canonical_player_id'], ['thirties','fifties','hundreds','ducks'], best={'hs':profile.best_high_score_from_labels})
    milestones['hs_sort'] = milestones['hs'].map(lambda value: layout.parse_high_score_value(str(value))[0])
    milestones.to_csv(processed / 'hall_of_fame/player_scorecard_milestones.csv', index=False)
    bowler_milestones = summary('hall_of_fame/player_bowling_milestones.csv', hof.build_player_bowling_milestones(bowling),
                               ['canonical_player_id'], ['three_wicket_innings','five_wicket_innings','ten_wicket_matches'],
                               best={'bbi':profile.best_bbi_from_labels})
    bowler_milestones['bbi_wickets_sort'] = bowler_milestones['bbi'].map(lambda v:hof.parse_bbi(v)[0])
    bowler_milestones['bbi_runs_sort'] = bowler_milestones['bbi'].map(lambda v:hof.parse_bbi(v)[1])
    bowler_milestones.to_csv(processed / 'hall_of_fame/player_bowling_milestones.csv',index=False)
    outcomes = hof.club_result_outcomes(frames['matches'],club_id=CLUB)
    appearances = apply_player_identity_mapping(appearances,club_id=CLUB)
    appearances = filter_public_player_rows(appearances)
    appearances['win'] = appearances['match_id'].map(outcomes)
    appearances = appearances[appearances['win'].notna()].copy()
    appearances['wins'] = appearances['win'].astype(bool)*appearances['weight']
    win = appearances.groupby(['canonical_player_id','canonical_player_name'],as_index=False).agg(matches_with_result=('weight','sum'),wins=('wins','sum'),raw_wins=('win','sum'))
    win['losses'] = win['matches_with_result']-win['wins']
    win['player_key'] = win['canonical_player_id'];win['display_player_name'] = win['canonical_player_name']
    win['player_name_key'] = win['display_player_name'].map(layout.player_name_match_key)
    win['source_coverage_note'] = 'Hawks weighted match/win policy: T20=0.5, played non-T20=1, no-play=0.'
    summary('hall_of_fame/player_win_rates.csv',win,['canonical_player_id'],['matches_with_result','wins','losses','raw_wins'],{'win_pct':('wins','matches_with_result',100)})
    path = processed / 'hall_of_fame/scorecard_record_links.csv'
    old = pd.read_csv(path,dtype=str)
    pd.concat([old,hof.build_scorecard_record_links(batting,bowling)],ignore_index=True).to_csv(path,index=False)

    from src.data.match_centre_milestones import build_batting_milestones
    fastest = build_batting_milestones(bundle, players_path=processed/'players.csv',aliases_path=aliases_path,
                                      scope_names=['parsed_current'],club_team_ids=team_ids,club_name_token='Glen Waverley Hawks')
    path = processed / 'hall_of_fame/fastest_batting_milestones.csv'
    old = pd.read_csv(path,dtype=str)
    new_fastest = filter_public_player_rows(fastest.milestones)
    pd.concat([old,new_fastest],ignore_index=True,sort=False).to_csv(path,index=False)
    fastest.validation.to_csv(bundle/'current_fastest_validation.csv',index=False)

    from scripts import build_gwhcc_partnerships as partnerships
    from scripts import build_gwhcc_hat_tricks as hats
    from src.data.partnerships import prepare_ball_by_ball_partnerships, combine_partnership_events, build_partnership_record_holders
    from src.data.hat_tricks import detect_hat_tricks, public_hat_trick_events
    from src.data.gwhcc_governance import display_grade_name
    calculated = prepare_ball_by_ball_partnerships(frames['partnerships'],matches=frames['matches'],innings=frames['innings'],
                    selected_team_ids_by_match=selected,identity_lookup=partnerships.build_identity_lookup(frames['batting'],selected),grade_display=display_grade_name)
    old_events = pd.read_csv(processed/'partnerships/partnership_events.csv',dtype=str)
    events = combine_partnership_events(old_events,calculated.events)
    pd.concat([old_events, calculated.events], ignore_index=True, sort=False).to_csv(processed/'partnerships/partnership_events.csv',index=False)
    records_path = processed/'hall_of_fame/partnership_records.csv'
    records = build_partnership_record_holders(events)
    try:
        pd.testing.assert_frame_equal(pd.read_csv(records_path), records, check_dtype=False)
    except AssertionError:
        records.to_csv(records_path,index=False)
    coverage_path = processed/'validation/gwhcc_partnership_coverage_audit.csv'
    pd.concat([pd.read_csv(coverage_path),partnerships.coverage_rows(calculated.audit)],ignore_index=True).to_csv(coverage_path,index=False)
    calculated.audit.to_csv(bundle/'current_partnership_audit.csv',index=False)
    detected = detect_hat_tricks(frames['balls'],matches=frames['matches'],bowling_scorecard=frames['bowling'],batting_scorecard=frames['batting'],
                                selected_team_ids_by_match=selected,identity_lookup=hats.build_identity_lookup(frames['bowling'],selected))
    path = processed/'hall_of_fame/hat_tricks.csv'
    old = pd.read_csv(path)
    new_hat = public_hat_trick_events(detected.events)
    if not new_hat.empty:
        append_disjoint(old,new_hat,['event_id']).to_csv(path,index=False)
    detected.audit.to_csv(bundle/'current_hat_trick_audit.csv',index=False)
    update_metadata(bundle, candidate, cutoff)
    return {'included_matches':len(included),'selected_appearances':len(participation),'captain_matches':len(captains),
            'new_fastest_rows':len(new_fastest),'new_hat_tricks':len(new_hat),'new_partnership_events':len(calculated.events),
            'profile_batting_innings':len(batting),'profile_bowling_rows':len(bowling),'candidate':str(candidate)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-bundle',type=Path,required=True)
    parser.add_argument('--candidate-root',type=Path,required=True)
    parser.add_argument('--cutoff',required=True)
    parser.add_argument('--baseline-root',type=Path,default=ROOT)
    args = parser.parse_args()
    result = build(args.source_bundle,args.candidate_root,args.cutoff,args.baseline_root)
    print(json.dumps(result,indent=2))
