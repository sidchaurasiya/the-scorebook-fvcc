"""Finalised-only Hawks sufficient statistics, with explicit provider reconciliation."""
from __future__ import annotations

import math
import json
import pandas as pd

FIELDS = {
    'batting': {'battingInnings':None, 'battingAggregate':'runs_numeric', 'battingNotOuts':'not_out',
                'battingBallsFaced':'balls_numeric', 'batting50s':'is_50', 'batting100s':'is_100',
                'batting0s':'is_duck', 'battingFours':'fours_numeric', 'battingSixes':'sixes_numeric'},
    'bowling': {'bowlingWickets':'wickets_numeric', 'bowlingMaidens':'maidens_bowled',
                'bowlingRuns':'runs_against_numeric', 'bowlingBalls':'balls_numeric',
                'bowling5WIs':'is_5wi', 'bowlingWides':'wides_numeric', 'bowlingNoBalls':'no_balls_numeric'},
    'fielding': {'fieldingTotalCatches':'catches', 'fieldingStumpings':'stumpings', 'fieldingRunOuts':'run_outs'},
}


def missing_provider_rows(provider: pd.DataFrame, appearances: pd.DataFrame,
                            source_frames: dict[str, pd.DataFrame], public_ids: set[str],
                            kind: str | None = None, corrections: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reconcile a known public player's missing provider row without inventing figures.

    Unknown/protected identities are never created here. An absent provider row
    with an actual performance requires independently verified source fields,
    not a zero statistic. The caller verifies source payloads and totals again.
    """
    existing = set(zip(provider.team_id,provider.player_id))
    additions=[]
    candidates=appearances[appearances.canonical_player_id.isin(public_ids)].drop_duplicates(['team_id','player_id'])
    metadata={'player_id','player_name','short_name','club','team_id','team_name','grade_id','grade_name','season_id','season'}
    missing_values={'matches','battingMinutes','battingHighScore','battingAverage','battingStrikeRate',
                    'bowlingBestInnings','bowlingAverage','bowlingStrikeRate','bowlingEconomyRate'}
    for actor in candidates.to_dict('records'):
        key=(actor['team_id'],actor['player_id'])
        if key in existing:
            continue
        certificate = (corrections.loc[corrections.discipline.eq(kind) & corrections.team_id.eq(key[0]) &
                                       corrections.source_player_id.eq(key[1]) & corrections.metric.eq('__missing_row__')]
                       if corrections is not None and not corrections.empty else pd.DataFrame())
        certified = len(certificate)==1 and certificate.iloc[0].evidence_status=='independently_reconciled_scorecard_and_delivery'
        for discipline,columns in {
            'batting':['runs_scored','balls_faced','fours_scored','sixes_scored'],
            'bowling':['overs_bowled','runs_conceded','wickets_taken','wides','no_balls'],
            'fielding':['catches','stumpings','run_outs','assisted_run_outs'],
        }.items():
            frame=source_frames[discipline]
            rows=frame[frame.team_id.eq(key[0]) & frame.participant_id.eq(key[1])]
            if rows[columns].apply(pd.to_numeric,errors='raise').fillna(0).gt(0).any().any() and not certified:
                raise ValueError('Missing provider performance must be independently reconciled')
            if discipline=='batting' and not rows.empty:
                from src.data.dismissal_status import batting_innings_mask
                if batting_innings_mask(rows).any() and not certified:
                    raise ValueError('Cannot invent a zero-performance row for an actual batting innings')
        context=provider[provider.team_id.eq(key[0])]
        if context.empty:
            raise ValueError('Participation-only row requires verified team/grade metadata')
        row=context.iloc[0].to_dict()
        for column in provider:
            if column not in metadata:
                row[column]=pd.NA if column in missing_values else False if column=='isBattingHSNotOut' else 0
        row.update(player_id=key[1],player_name=actor['player_name'],short_name=pd.NA,
                   source_coverage_note='Verified selected-team participation; DNB/no individual performance recorded.')
        if certified:
            values=json.loads(certificate.iloc[0].source_fields_json)
            if not set(values).issubset(set(provider.columns)-metadata-{'matches'}):
                raise ValueError('Source certificate cannot replace identity or team metadata')
            row.update({key:pd.NA if value is None else value for key,value in values.items()})
            row['source_coverage_note']='Selected-team participation and figures verified from scorecard/deliveries; provider aggregate row absent.'
        additions.append(row)
    if not additions:
        return provider.copy(),pd.DataFrame()
    return pd.concat([provider,pd.DataFrame(additions)],ignore_index=True),pd.DataFrame(additions)


def finalised_aggregate(provider: pd.DataFrame, completed: pd.DataFrame,
                        excluded: pd.DataFrame, kind: str,
                        corrections: pd.DataFrame | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Reconcile raw-ID/team aggregates before removing excluded fixture contributions.

    Batting/bowling inputs use the existing scorecard preparation rules. Fielding
    uses normalized source totals (not the profile assisted-run-out adapter).
    Never infer a discrepancy's scope just from its magnitude or a player's name.
    """
    mapping = FIELDS[kind]
    keys = ['team_id', 'participant_id']
    groups = [{key:group for key,group in frame.groupby(keys)} if not frame.empty else {}
              for frame in [completed, excluded]]
    if provider.duplicated(['team_id','player_id']).any():
        raise ValueError('Duplicate provider player/team aggregate')
    output = provider.copy()
    changes = []
    verified = corrections if corrections is not None else pd.DataFrame()
    if not verified.empty and verified.duplicated(['discipline','team_id','source_player_id','metric']).any():
        raise ValueError('Duplicate source correction certificate')
    for index, row in provider.iterrows():
        key = (row.team_id, row.player_id)
        done, other = [group.get(key, pd.DataFrame()) for group in groups]
        changed = False
        for target, source in mapping.items():
            values = []
            for group in [done, other]:
                if group.empty:
                    values.append(0.0)
                elif source is None:
                    values.append(float(len(group)))
                else:
                    numeric = pd.to_numeric(group[source], errors='raise')
                    if numeric.isna().any() or numeric.lt(0).any():
                        raise ValueError(f'Unknown or negative scorecard metric: {target}')
                    values.append(float(numeric.sum()))
            final, omitted = values
            actual = float(row[target])
            known_partition = math.isclose(actual, final, abs_tol=1e-9) or math.isclose(actual, final+omitted, abs_tol=1e-9)
            certificate = verified.loc[verified.discipline.eq(kind) & verified.team_id.eq(key[0]) &
                                       verified.source_player_id.eq(key[1]) & verified.metric.eq(target)] if not verified.empty else verified
            certified = (len(certificate)==1 and certificate.iloc[0].evidence_status=='independently_reconciled_scorecard_and_delivery'
                         and math.isclose(float(certificate.iloc[0].provider_value),actual,abs_tol=1e-9)
                         and math.isclose(float(certificate.iloc[0].finalised_scorecard_value),final,abs_tol=1e-9))
            if not math.isfinite(actual) or not (known_partition or certified):
                raise ValueError(f'Unreconciled provider scope: {kind}:{key}:{target}')
            if not math.isclose(actual, final, abs_tol=1e-9):
                if kind == 'fielding':
                    raise ValueError('Fielding components require an explicit keeper/run-out scope reconciliation')
                output.at[index,target] = final
                changed = True
                changes.append({'team_id':key[0], 'source_player_id':key[1], 'metric':target,
                                'provider_value':actual, 'finalised_value':final,
                                'excluded_value':omitted})
        if not changed:
            continue
        def ratio(numerator, denominator, scale=1):
            return numerator*scale/denominator if denominator else float('nan')
        if kind == 'batting':
            runs = float(output.at[index,'battingAggregate'])
            outs = float(output.at[index,'battingInnings'])-float(output.at[index,'battingNotOuts'])
            output.at[index,'battingAverage'] = ratio(runs,outs)
            output.at[index,'battingStrikeRate'] = ratio(runs,float(output.at[index,'battingBallsFaced']),100)
            best = done.sort_values(['runs_numeric','not_out'],ascending=False).iloc[0] if not done.empty else None
            output.at[index,'battingHighScore'] = best.runs_numeric if best is not None else float('nan')
            output.at[index,'isBattingHSNotOut'] = bool(best.not_out) if best is not None else False
            if pd.notna(row.get('battingMinutes')) and float(row['battingMinutes']) != 0:
                raise ValueError('Contaminated batting minutes lack a matching scorecard scope')
        elif kind == 'bowling':
            wickets = float(output.at[index,'bowlingWickets'])
            runs = float(output.at[index,'bowlingRuns'])
            balls = float(output.at[index,'bowlingBalls'])
            output.at[index,'bowlingAverage'] = ratio(runs,wickets)
            output.at[index,'bowlingStrikeRate'] = ratio(balls,wickets)
            output.at[index,'bowlingEconomyRate'] = ratio(runs,balls,6)
            best = done.sort_values(['wickets_numeric','runs_against_numeric'],ascending=[False,True]).iloc[0] if not done.empty else None
            output.at[index,'bowlingBestInnings'] = f'{int(best.wickets_numeric)}-{int(best.runs_against_numeric)}' if best is not None else pd.NA
            output.at[index,'bowling10WMs'] = int(done.groupby('match_id').wickets_numeric.sum().ge(10).sum()) if not done.empty else 0
    return output, pd.DataFrame(changes)
