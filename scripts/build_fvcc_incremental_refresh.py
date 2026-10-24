"""Build a governed FVCC candidate from a frozen source bundle.

Historical source rows and sufficient statistics are retained. The builder
supports a disjoint new season or a verified same-season incremental snapshot.
It uses existing club-aware exporters and never fetches or publishes data.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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


def validate_same_season_match_partitions(new_match_ids, excluded_match_ids):
    overlap = set(map(str, new_match_ids)) & set(map(str, excluded_match_ids))
    if overlap:
        raise ValueError(f"Selected and excluded match IDs overlap: {sorted(overlap)}")


CURRENT_SEASON_EXCLUDED_METRICS = {
    'batting': ['battingInnings','battingAggregate','battingNotOuts','battingBallsFaced','batting50s','batting100s','batting0s','battingFours','battingSixes','battingMinutes'],
    'bowling': ['bowlingBalls','bowlingMaidens','bowlingRuns','bowlingWickets','bowling5WIs','bowling10WMs','bowlingWides','bowlingNoBalls'],
    'fielding': ['fieldingCatchesNonWK','fieldingCatchesWK','fieldingTotalCatches','fieldingStumpings','fieldingAssistedRunOuts','fieldingUnassistedRunOuts','fieldingRunOuts'],
}


def _numeric(value, default=0.0):
    value = pd.to_numeric(pd.Series([value]), errors='coerce').iloc[0]
    return default if pd.isna(value) else float(value)


def _score_candidate(value, not_out=False):
    value = _numeric(value, default=float('nan'))
    if pd.isna(value):
        return None
    return int(value), bool(not_out)


def _high_score_not_out(value):
    if isinstance(value, bool):
        return value
    if pd.isna(value):
        return False
    return str(value).strip().casefold() in {'true','1','yes','y'}


def _parse_bbi(value):
    if pd.isna(value):
        return None
    import re
    match = re.search(r'(\d+)\s*[-/]\s*(\d+)', str(value))
    return (int(match.group(1)), int(match.group(2))) if match else None


def latest_date_by_key(old: pd.DataFrame, new: pd.DataFrame, keys: list[str]) -> dict[tuple, object]:
    """Choose the newest non-missing source date without mixing pandas dtypes."""
    old_lookup={tuple(row[k] for k in keys):row.get('latest_match_date') for row in old.to_dict('records')}
    new_lookup={tuple(row[k] for k in keys):row.get('latest_match_date') for row in new.to_dict('records')}
    result={}
    for key in set(old_lookup)|set(new_lookup):
        candidates=[value for value in [old_lookup.get(key),new_lookup.get(key)] if pd.notna(value) and str(value).strip()]
        if candidates:
            result[key]=max(candidates,key=lambda value:pd.to_datetime(value,utc=True,errors='coerce'))
    return result


def merge_same_season_aggregate(
    old: pd.DataFrame,
    current: pd.DataFrame,
    excluded: pd.DataFrame,
    *,
    season_id: str,
    participation: pd.Series,
    kind: str,
    batting_rows: pd.DataFrame,
    bowling_rows: pd.DataFrame,
    club_id: str = CLUB,
) -> pd.DataFrame:
    """Replace only one published season snapshot, excluding rejected match evidence.

    Provider aggregates are current-season totals. The excluded match delta is
    subtracted from additive source counters; public roster participation is
    recomputed from finalized selected scorecards instead of provider counts.
    All other season rows remain byte-value-equivalent after CSV round-tripping.
    """
    from src.utils.player_identity import apply_player_identity_mapping, filter_public_player_rows

    key_columns = ['season_id','team_id','player_id']
    old = old.copy()
    current = current[current['season_id'].astype(str).eq(str(season_id))].copy()
    old_current = old[old['season_id'].astype(str).eq(str(season_id))].copy()
    old_other = old[~old['season_id'].astype(str).eq(str(season_id))].copy()
    for frame in [current, old_current]:
        for column in ['season_id','team_id','player_id']:
            frame[column] = frame[column].astype(str)
        if frame.duplicated(key_columns).any():
            raise ValueError(f'Duplicate {kind} aggregate keys in current-season snapshot')
    excluded = excluded.copy()
    if not excluded.empty:
        for column in ['team_id','player_id']:
            excluded[column] = excluded[column].astype(str)
        if excluded.duplicated(['team_id','player_id']).any():
            raise ValueError(f'Duplicate {kind} excluded-match keys')
    current['_key'] = list(zip(current['team_id'], current['player_id']))
    old_current['_key'] = list(zip(old_current['team_id'], old_current['player_id']))
    excluded['_key'] = list(zip(excluded['team_id'], excluded['player_id'])) if not excluded.empty else pd.Series(dtype=object)
    source_rows = {row['_key']:row for row in current.to_dict('records')}
    old_rows = {row['_key']:row for row in old_current.to_dict('records')}
    excluded_rows = {row['_key']:row for row in excluded.to_dict('records')} if not excluded.empty else {}
    participation = participation.copy()
    participation.index = [(str(team),str(player)) for team,player in participation.index]
    participation_rows = participation.to_dict()

    # Require source-season rows for every public player selected in the new
    # matches. Missing source rows are not silently synthesized from names.
    selected_keys = set(participation_rows)
    missing = selected_keys - set(source_rows) - set(old_rows)
    if missing:
        raise ValueError(f'Missing {kind} source aggregate rows for {len(missing)} selected players')

    rows = []
    for key in sorted(set(source_rows) | set(old_rows) | set(excluded_rows) | selected_keys):
        live = source_rows.get(key)
        previous = old_rows.get(key)
        if live is None and previous is None:
            continue
        row = dict(previous or {})
        if live is not None:
            row.update(live)
        row.pop('_key',None)
        row['season_id'] = str(season_id)
        provider_count = live.get('matches') if live is not None else (previous or {}).get('provider_appearance_count',pd.NA)
        row['provider_appearance_count'] = provider_count

        rejected = excluded_rows.get(key,{})
        for metric in CURRENT_SEASON_EXCLUDED_METRICS[kind]:
            delta = _numeric(rejected.get(metric),0.0)
            if not delta:
                continue
            if metric not in row:
                raise ValueError(f'Missing {kind}.{metric} in current aggregate required to exclude match contribution')
            adjusted = _numeric(row.get(metric),0.0) - delta
            if adjusted < -1e-6:
                raise ValueError(f'Excluding verified {kind}.{metric} delta would make the aggregate negative')
            row[metric] = max(0.0,adjusted)

        previous_matches = _numeric((previous or {}).get('matches'),0.0)
        row['matches'] = int(previous_matches + int(participation_rows.get(key,0)))
        if row['matches'] <= 0:
            continue
        rows.append(row)

    if not rows:
        raise ValueError(f'No public current-season {kind} rows after match and privacy filtering')
    updated = pd.DataFrame(rows)
    # Existing rows carry canonical fields while newly seen source IDs do not.
    # Fill row-wise blanks before identity mapping so pandas' unioned columns
    # cannot turn new public players into the shared unknown_player key.
    if 'raw_player_id' not in updated:
        updated['raw_player_id']=updated.get('player_id','')
    else:
        blank=updated['raw_player_id'].isna()|updated['raw_player_id'].astype(str).str.strip().isin(['','nan','None','<NA>'])
        updated.loc[blank,'raw_player_id']=updated.loc[blank,'player_id']
    if 'raw_player_name' not in updated:
        updated['raw_player_name']=updated.get('player_name','')
    else:
        blank=updated['raw_player_name'].isna()|updated['raw_player_name'].astype(str).str.strip().isin(['','nan','None','<NA>'])
        updated.loc[blank,'raw_player_name']=updated.loc[blank,'player_name']

    # Recompute derived rates from revised source counters, never averages of
    # averages. Preserve a missing result when its denominator is unavailable.
    def ratio(numerator, denominator, factor=1.0):
        n = pd.to_numeric(updated.get(numerator),errors='coerce')
        d = pd.to_numeric(updated.get(denominator),errors='coerce')
        return (n*factor/d.where(d.gt(0))).round(2)
    if kind == 'batting':
        outs = pd.to_numeric(updated['battingInnings'],errors='coerce') - pd.to_numeric(updated['battingNotOuts'],errors='coerce')
        updated['battingAverage'] = (pd.to_numeric(updated['battingAggregate'],errors='coerce')/outs.where(outs.gt(0))).round(2)
        updated['battingStrikeRate'] = ratio('battingAggregate','battingBallsFaced',100)
        high_map = {}
        eligible = batting_rows.copy()
        if not eligible.empty:
            type_text = eligible['dismissal_type'].fillna('').astype(str).str.strip().str.casefold()
            eligible = eligible[~type_text.eq('did not bat')]
            for row in eligible.to_dict('records'):
                key = (str(row['team_id']),str(row['participant_id']))
                candidate = _score_candidate(row.get('runs_scored'),str(row.get('dismissal_type','')).strip().casefold()=='not out')
                if candidate is not None:
                    high_map.setdefault(key,[]).append(candidate)
        old_lookup = {row['_key']:row for row in old_current.to_dict('records')}
        high_scores=[]; high_not_out=[]
        for row in updated.to_dict('records'):
            key=(str(row['team_id']),str(row['player_id']))
            prior=old_lookup.get(key,{})
            candidates=[_score_candidate(prior.get('battingHighScore'),_high_score_not_out(prior.get('isBattingHSNotOut')))]
            candidates.extend(high_map.get(key,[]))
            candidates=[value for value in candidates if value is not None]
            best=max(candidates,key=lambda value:(value[0],int(value[1]))) if candidates else None
            high_scores.append(best[0] if best else pd.NA)
            high_not_out.append(best[1] if best else pd.NA)
        updated['battingHighScore']=high_scores
        updated['isBattingHSNotOut']=high_not_out
    elif kind == 'bowling':
        updated['bowlingAverage'] = ratio('bowlingRuns','bowlingWickets')
        updated['bowlingStrikeRate'] = ratio('bowlingBalls','bowlingWickets')
        updated['bowlingEconomyRate'] = ratio('bowlingRuns','bowlingBalls',6)
        bbi_map={}
        if not bowling_rows.empty:
            for row in bowling_rows.to_dict('records'):
                key=(str(row['team_id']),str(row['participant_id']))
                candidate=(_numeric(row.get('wickets_taken'),0),_numeric(row.get('runs_conceded'),0))
                bbi_map.setdefault(key,[]).append(candidate)
        old_lookup={row['_key']:row for row in old_current.to_dict('records')}
        bbi_values=[]
        for row in updated.to_dict('records'):
            key=(str(row['team_id']),str(row['player_id']))
            candidates=[_parse_bbi(old_lookup.get(key,{}).get('bowlingBestInnings'))]
            candidates.extend(bbi_map.get(key,[]))
            candidates=[value for value in candidates if value is not None]
            best=max(candidates,key=lambda value:(value[0],-value[1])) if candidates else None
            prior=old_lookup.get(key,{}).get('bowlingBestInnings')
            separator='/' if isinstance(prior,str) and '/' in prior else '-'
            bbi_values.append(f'{int(best[0])}{separator}{int(best[1])}' if best else prior)
        updated['bowlingBestInnings']=bbi_values

    updated = apply_player_identity_mapping(updated,club_id=club_id)
    updated = filter_public_player_rows(updated)
    if updated.duplicated(key_columns).any():
        raise ValueError(f'Duplicate {kind} rows after identity mapping')
    return pd.concat([old_other,updated],ignore_index=True,sort=False)


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


def add_first_innings_result_context(matches: pd.DataFrame, payloads: list[dict]) -> pd.DataFrame:
    """Retain the official first-innings decision context in customer-facing results."""
    output = matches.copy()
    if output.empty or not {'match_id', 'result_text'}.issubset(output.columns):
        return output
    for payload in payloads:
        summary = payload.get('matchSummary') or {}
        teams = summary.get('teams') or []
        winners = [team for team in teams if str(team.get('resultType', '')).upper() == 'WON_ON_FIRST_INNINGS']
        losers = [team for team in teams if str(team.get('resultType', '')).upper() == 'LOST_ON_FIRST_INNINGS']
        if not winners and not losers:
            continue
        if len(winners) != 1 or len(losers) != 1:
            raise ValueError(f"Ambiguous official first-innings result for match {payload.get('id', '')}")
        match_id = str(payload.get('id', ''))
        rows = output['match_id'].astype(str).eq(match_id)
        if int(rows.sum()) != 1:
            raise ValueError(f"Expected one match row for first-innings result {match_id}")
        source_text = str(summary.get('resultText') or output.loc[rows, 'result_text'].iloc[0] or '').strip()
        if 'first innings' not in source_text.casefold() and not re.search(r'\bwon\s+by\b', source_text, flags=re.IGNORECASE):
            output.loc[rows, 'result_text'] = f'{source_text} on first innings'.strip()
    return output


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
    same_season = state.get('mode') == 'same_season_incremental'
    if same_season:
        excluded_ids=set(map(str,state.get('excluded_match_ids',[])))
        validate_same_season_match_partitions(state.get('new_match_ids',[]),excluded_ids)
        reconciliation=json.loads((bundle/'source_aggregate_reconciliation.json').read_text())
        failed={kind:values.get('mismatch_count') for kind,values in reconciliation.get('categories',{}).items() if values.get('mismatch_count')!=0}
        if failed:
            raise ValueError(f'Live aggregate source does not reconcile to official scorecards: {failed}')
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
    frames['matches'] = add_first_innings_result_context(frames['matches'], payloads)
    history_ids = set(pd.read_csv(baseline_root/'clubs/fvcc/data/processed/season_overview/season_by_round_scorecards.csv')['match_id'])
    increment_ids = set(frames['matches']['match_id'])
    if history_ids & increment_ids or len(increment_ids) != len(frames['matches']):
        raise ValueError('Historical/current match partitions overlap or contain duplicates')
    if increment_ids != set(map(str,state['new_match_ids'])):
        raise ValueError('Parsed match partition does not exactly match the approved new_match_ids list')
    shutil.copytree(baseline_root/'clubs/fvcc',candidate/'clubs/fvcc')
    shutil.copytree(bundle/'baseline/data',candidate/'data')
    processed = candidate/'clubs/fvcc/data/processed'
    season_already_published = False
    for kind in ['batting','bowling','fielding']:
        old = pd.read_csv(processed/f'all_seasons_{kind}.csv',low_memory=False)
        season_already_published = season_already_published or old['season_id'].astype(str).eq(str(season['id'])).any()
    if season_already_published != same_season:
        raise ValueError('Bundle mode does not match the published-season state; refuse append/replace')
    config.REPO_ROOT = candidate
    config.CLUBS_ROOT = candidate/'clubs'
    config._load_club_config_cached.cache_clear()

    old_seasons = pd.read_csv(processed/'seasons.csv')
    current_flags={s['id']:bool(s.get('isCurrentSeason')) for s in discovery['seasons']}
    current_flags_series=old_seasons['id'].map(current_flags).astype('boolean')
    old_flags_series=old_seasons['isCurrentSeason'].astype('boolean')
    old_seasons['isCurrentSeason']=current_flags_series.combine_first(old_flags_series).fillna(False).astype(bool)
    seasons = normalize_seasons([season])
    if same_season:
        for column in seasons.columns:
            if column not in old_seasons:
                old_seasons[column]=pd.NA
        replacement=seasons.iloc[0].to_dict()
        mask=old_seasons['id'].astype(str).eq(str(season['id']))
        if int(mask.sum())!=1:
            raise ValueError('Expected exactly one published current-season metadata row')
        for column,value in replacement.items():
            old_seasons.loc[mask,column]=value
        old_seasons.sort_values('startDate',ascending=False).to_csv(processed/'seasons.csv',index=False)
    else:
        append_disjoint(old_seasons, seasons, ['id']).sort_values('startDate',ascending=False).to_csv(processed/'seasons.csv',index=False)
    teams = normalize_teams(selected_teams)
    old_teams=pd.read_csv(processed/'teams.csv')
    if same_season:
        old_teams=old_teams[~old_teams['season_id'].astype(str).eq(str(season['id']))]
    append_disjoint(old_teams, teams, ['season_id','team_id']).to_csv(processed/'teams.csv',index=False)
    aggregates = {}
    public_appearances=filter_public_player_rows(apply_player_identity_mapping(appearances,club_id=CLUB))
    participation=public_appearances.groupby(['team_id','player_id'])['match_id'].nunique()
    identities = []
    baseline_canonical = set(pd.read_csv(bundle/'baseline_public_index.csv')['id'])
    for kind in ['batting','bowling','fielding']:
        current = pd.read_csv(bundle/f'current_aggregate_{kind}.csv')
        current = current[current['season_id'].eq(season['id'])].copy()
        current['team_id']=current['team_id'].astype(str)
        current['player_id']=current['player_id'].astype(str)
        if same_season:
            excluded=(pd.read_csv(bundle/f'excluded_match_deltas_{kind}.csv')
                      if state.get('excluded_match_ids') else pd.DataFrame())
            old_aggregate=pd.read_csv(processed/f'all_seasons_{kind}.csv',low_memory=False)
            aggregates[kind]=merge_same_season_aggregate(
                old_aggregate,current,excluded,season_id=str(season['id']),participation=participation,
                kind=kind,batting_rows=frames['batting'],bowling_rows=frames['bowling'],club_id=CLUB)
        else:
            current['provider_appearance_count'] = current['matches']
            current['matches'] = [participation.get((str(r.team_id),str(r.player_id)),0) for r in current.itertuples()]
            current = current[current['matches'].gt(0)].copy()
            current = filter_public_player_rows(apply_player_identity_mapping(current, club_id=CLUB))
            aggregates[kind]=append_disjoint(pd.read_csv(processed/f'all_seasons_{kind}.csv',low_memory=False),current,['season_id','team_id','player_id'])
        aggregates[kind].to_csv(processed/f'all_seasons_{kind}.csv',index=False)
        current=aggregates[kind][aggregates[kind]['season_id'].astype(str).eq(str(season['id']))]
        if kind == 'batting':
            for row in current.drop_duplicates('player_id').to_dict('records'):
                identities.append({k:row[k] for k in ['player_id','player_name','canonical_player_id','canonical_player_name']})
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
        if filename != 'all_seasons_matches.csv':
            current = filter_public_player_rows(current)
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
        if 'latest_match_date' in result and 'latest_match_date' in current:
            latest_map=latest_date_by_key(old,current,keys)
            result['latest_match_date']=[latest_map.get(tuple(row[k] for k in keys),row.get('latest_match_date')) for _,row in result.iterrows()]
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
        current=filter_public_player_rows(current)
        if filename == 'season_by_round_scorecards.csv':
            if set(old['match_id'].astype(str)) & set(current['match_id'].astype(str)):
                raise ValueError('Season-by-round match overlap')
            pd.concat([old,current],ignore_index=True,sort=False).to_csv(path,index=False)
        else:
            keys=['season_id','team_id','grade_id','player_key']
            if not set(keys).issubset(old.columns) or not set(keys).issubset(current.columns):
                raise ValueError(f'Cannot merge same-season output {filename}; expected stable summary keys missing')
            result=merge_summary(old,current,keys,history_ids,increment_ids)
            if 'latest_match_date' in result and 'latest_match_date' in current:
                latest_map=latest_date_by_key(old,current,keys)
                result['latest_match_date']=[latest_map.get(tuple(row[k] for k in keys),row.get('latest_match_date')) for _,row in result.iterrows()]
            result.to_csv(path,index=False)
    summary('hall_of_fame/player_bbb_batting_rates.csv',hof.build_player_bbb_batting_rates(batting,balls),['canonical_player_id','canonical_player_name','display_player_name'])
    summary('hall_of_fame/player_scorecard_milestones.csv',hof.build_player_scorecard_milestones(batting),['canonical_player_id','canonical_player_name','display_player_name'])
    summary('hall_of_fame/player_bowling_milestones.csv',hof.build_player_bowling_milestones(bowling),['canonical_player_id','canonical_player_name','display_player_name'])
    mapped = public_appearances
    mapped['display_player_name'] = mapped['canonical_player_name']
    summary('hall_of_fame/player_win_rates.csv',hof.build_player_win_rates(frames['matches'],mapped,pd.DataFrame(),pd.DataFrame(),club_id=CLUB),['canonical_player_id','canonical_player_name','display_player_name'])
    path = processed/'hall_of_fame/scorecard_record_links.csv'
    old_links=pd.read_csv(path)
    new_links=filter_public_player_rows(hof.build_scorecard_record_links(batting,bowling))
    if 'match_id' in old_links and 'match_id' in new_links and set(old_links.match_id.astype(str)) & set(new_links.match_id.astype(str)):
        raise ValueError('Scorecard record-link match overlap')
    pd.concat([old_links,new_links],ignore_index=True).to_csv(path,index=False)

    from src.data.fastest_innings import build_governed_fastest_innings
    from src.data.partnerships import build_governed_club_partnerships, build_verified_partnership_record_holders
    from src.data.hat_tricks import build_governed_club_hat_tricks
    from src.config.club_config import get_mapping_path
    fastest = build_governed_fastest_innings(club_id=CLUB,processed_root=bundle,players_path=processed/'players.csv',
                                            aliases_path=get_mapping_path('player_aliases.csv',club_id=CLUB),club_team_ids=team_ids,club_name_token=config.get_club_name(CLUB))
    path = processed/'hall_of_fame/fastest_batting_milestones.csv'
    old_fastest=pd.read_csv(path)
    new_fastest=fastest.governance.published
    all_columns=list(dict.fromkeys([*old_fastest.columns,*new_fastest.columns]))
    combined_fastest=pd.DataFrame.from_records(
        [*old_fastest.reindex(columns=all_columns).to_dict('records'),*new_fastest.reindex(columns=all_columns).to_dict('records')],
        columns=all_columns)
    combined_fastest.to_csv(path,index=False)
    partnerships = build_governed_club_partnerships(club_id=CLUB,match_centre_root=bundle)
    path = processed/'hall_of_fame/partnerships.csv'
    events = pd.concat([pd.read_csv(path),partnerships.events],ignore_index=True,sort=False)
    events.to_csv(path,index=False)
    records, audit = build_verified_partnership_record_holders(events)
    records.to_csv(processed/'hall_of_fame/partnership_records.csv',index=False)
    hats = build_governed_club_hat_tricks(club_id=CLUB,match_centre_root=bundle,club_processed_root=processed)
    path = processed/'hall_of_fame/hat_tricks.csv'
    pd.concat([pd.read_csv(path),hats.events],ignore_index=True,sort=False).to_csv(path,index=False)
    result = {'new_matches':len(increment_ids),'appearances':len(public_appearances),'public_new_identities':int(identity['decision'].eq('new_source_identity').sum()),
              'new_fastest_rows':len(fastest.governance.published),'new_partnership_events':len(partnerships.events),'new_hat_tricks':len(hats.events)}
    fastest.detector_validation.to_csv(bundle/'current_fastest_validation.csv',index=False)
    partnerships.reconciliation_audit.to_csv(bundle/'current_partnership_audit.csv',index=False)
    hats.validation.to_csv(bundle/'current_hat_trick_validation.csv',index=False)
    (bundle/'candidate_generation.json').write_text(json.dumps(result,indent=2))
    final_match_table=pd.read_csv(processed/'season_overview/season_by_round_scorecards.csv',low_memory=False)
    current_finalized_ids=sorted(final_match_table.loc[final_match_table.season.eq(season['name']),'match_id'].astype(str).unique())
    verified_appearance_counts=(aggregates['batting'].loc[aggregates['batting'].season_id.astype(str).eq(str(season['id']))]
                                .groupby('canonical_player_id').matches.sum().astype(int).to_dict())
    version_path=processed/'metadata/fvcc_data_version.json'
    version=json.loads(version_path.read_text())
    resolved_incomplete=set(map(str,state.get('resolved_incomplete_match_ids',[])))
    remaining_incomplete=sorted(set(map(str,version.get('excluded_incomplete_match_ids',[])))-resolved_incomplete)
    metadata_path = candidate/'clubs/fvcc/data/metadata.json'
    metadata = json.loads(metadata_path.read_text())
    metadata.update(seasons_fetched=json.loads((bundle/'source_payloads/seasons.json').read_text())['payload']['seasons'],
                    matches_fetched=len(pd.read_csv(processed/'season_overview/season_by_round_scorecards.csv')),
                    players_fetched=len(pd.read_csv(processed/'players.csv')),teams_fetched=len(pd.read_csv(processed/'teams.csv')),
                    stat_rows={k:len(v) for k,v in aggregates.items()},
                    incremental_refresh={'cutoff_utc':state['cutoff_utc'],'cutoff_melbourne':state['cutoff_melbourne'],
                                         'new_match_ids':sorted(increment_ids),'historical_rows_preserved':True,
                                         'provider_cancelled_appearances_excluded':True,
                                         'current_finalized_match_ids':current_finalized_ids,
                                         'verified_public_appearance_counts':verified_appearance_counts,
                                         'excluded_incomplete_match_ids':remaining_incomplete,
                                         'excluded_match_ids':sorted(state.get('excluded_match_ids',[]))})
    receipt = max(json.loads(p.read_text())['request']['fetched_at'] for p in (bundle/'source_payloads').glob('*.json'))
    metadata['fetch_date_time'] = metadata['last_successful_refresh_time'] = receipt
    metadata_path.write_text(json.dumps(metadata,indent=2)+'\n')
    latest = frames['matches'].sort_values(['first_match_day','match_id']).iloc[-1]
    opponent=latest.get('away_team_name','') if str(latest.get('home_team_id','')) in team_ids else latest.get('home_team_name','')
    current_finalized=sorted(set(map(str,version.get('current_finalized_match_ids',[])))|increment_ids)
    source_limitations=list(version.get('source_limitations',[]))
    source_limitations.extend(note for note in state.get('source_limitations',[]) if note not in source_limitations)
    version.update(generated_app_facing_data_version=receipt,latest_refresh_timestamp=receipt,validator_status='pending',
                   cutoff_utc=state['cutoff_utc'],cutoff_melbourne=state['cutoff_melbourne'],new_match_ids=sorted(increment_ids),
                   excluded_match_ids=sorted(state.get('excluded_match_ids',[])),
                   excluded_incomplete_match_ids=remaining_incomplete,
                   current_finalized_match_ids=current_finalized,
                   source_issue_match_ids=sorted(set(map(str,version.get('source_issue_match_ids',[])))|set(map(str,state.get('excluded_match_ids',[])))),
                   source_limitations=source_limitations,
                   latest_match_id=latest['match_id'],latest_match_date=latest['first_match_day'],
                   latest_match_round=latest.get('round_short_name',latest.get('round_name','')),
                   latest_match_opponent=opponent,latest_match_result=latest.get('result_text',''),latest_statistical_season=season['name'])
    version_path.write_text(json.dumps(version,indent=2)+'\n')
    write_prepared_fvcc_core(candidate,processed)
    return result


def write_prepared_fvcc_core(candidate: Path, processed: Path) -> None:
    """Regenerate FVCC's prepared HOF snapshot from the candidate's aggregates."""
    os.environ['SCOREBOOK_IGNORE_PREPARED_HOF']='1'
    from src.data.hall_of_fame_prepared import write_prepared_hall_of_fame_core
    from src.data.playcricket_ingestion import metadata_mtime
    from src.utils.player_identity import player_aliases_mtime
    from src.ui import layout
    layout.load_hall_of_fame_data.clear()
    prepared=layout.load_hall_of_fame_data(
        metadata_mtime(),player_aliases_mtime(club_id=CLUB),layout.HALL_OF_FAME_DATA_VERSION,club_id=CLUB)
    if prepared is None:
        raise RuntimeError('Unable to build candidate prepared HOF from candidate aggregates')
    written=write_prepared_hall_of_fame_core(
        CLUB,layout.HALL_OF_FAME_DATA_VERSION,
        {'batting':prepared['batting'],'bowling':prepared['bowling'],'fielding':prepared['fielding'],'all_time':prepared['all_time']},
        layout.best_batting_season(prepared['batting_raw']),layout.best_bowling_season(prepared['bowling_raw']),
        output_dir=processed/'hall_of_fame')
    if not written:
        raise RuntimeError('Candidate prepared HOF writer produced no files')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-bundle',type=Path,required=True)
    parser.add_argument('--candidate-root',type=Path,required=True)
    parser.add_argument('--baseline-root',type=Path,default=ROOT)
    args = parser.parse_args()
    print(json.dumps(build(args.source_bundle,args.candidate_root,args.baseline_root),indent=2))
