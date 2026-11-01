import pandas as pd
import pytest

from src.data.gwhcc_finalised_aggregates import FIELDS, finalised_aggregate


def bat(runs, balls, not_out):
    return pd.DataFrame([dict(team_id='team',participant_id='source',match_id='match',
                              runs_numeric=runs,balls_numeric=balls,not_out=not_out,
                              is_50=False,is_100=False,is_duck=False,fours_numeric=0,sixes_numeric=0)])


def provider(kind, final, excluded):
    row = dict(team_id='team', player_id='source', player_name='Unchanged name', matches=2)
    for target, source in FIELDS[kind].items():
        row[target] = len(final)+len(excluded) if source is None else final[source].sum()+excluded[source].sum()
    return row


def test_excluded_batting_cannot_change_innings_not_out_average_or_high_score():
    done, omitted = bat(5,2,False), bat(40,12,True)
    row=provider('batting',done,omitted)
    row.update(battingHighScore=40,isBattingHSNotOut=True,battingAverage=45,
               battingStrikeRate=45/14*100,battingMinutes=0)
    raw=pd.DataFrame([row])
    out,audit=finalised_aggregate(raw,done,omitted,'batting')
    assert out.iloc[0].battingAggregate==5
    assert out.iloc[0].battingInnings==1
    assert out.iloc[0].battingNotOuts==0
    assert out.iloc[0].battingHighScore==5
    assert not out.iloc[0].isBattingHSNotOut
    assert out.iloc[0].battingAverage==5
    assert out.iloc[0].battingStrikeRate==250
    assert out.iloc[0].player_name=='Unchanged name'
    assert raw.iloc[0].battingAggregate==45
    assert not audit.empty
    repeated,_=finalised_aggregate(out,done,omitted,'batting')
    pd.testing.assert_frame_equal(out,repeated)


def test_excluded_bowling_cannot_change_best_figures_or_rate_denominators():
    def bowl(runs, balls):
        return pd.DataFrame([dict(team_id='team',participant_id='source',match_id='game',
                                  wickets_numeric=1,runs_against_numeric=runs,balls_numeric=balls,
                                  maidens_bowled=0,is_5wi=False,wides_numeric=0,no_balls_numeric=0)])
    done, omitted=bowl(20,12),bowl(2,1)
    row=provider('bowling',done,omitted)
    row.update(bowlingBestInnings='1-2',bowlingAverage=11,bowlingStrikeRate=6.5,
               bowlingEconomyRate=22/13*6,bowling10WMs=0)
    out,_=finalised_aggregate(pd.DataFrame([row]),done,omitted,'bowling')
    assert out.iloc[0].bowlingWickets==1
    assert out.iloc[0].bowlingRuns==20
    assert out.iloc[0].bowlingBalls==12
    assert out.iloc[0].bowlingBestInnings=='1-20'
    assert out.iloc[0].bowlingAverage==20
    assert out.iloc[0].bowlingStrikeRate==12
    assert out.iloc[0].bowlingEconomyRate==10


def test_unexplained_source_difference_fails_instead_of_selecting_a_larger_total():
    done,omitted=bat(5,2,False),bat(40,12,True)
    row=provider('batting',done,omitted)
    row['battingAggregate']=46
    with pytest.raises(ValueError,match='Unreconciled provider scope'):
        finalised_aggregate(pd.DataFrame([row]),done,omitted,'batting')


def test_unknown_and_duplicate_source_fields_are_not_silently_accepted():
    done,omitted=bat(5,2,False),bat(40,12,True)
    row=provider('batting',done,omitted)
    with pytest.raises(ValueError,match='Duplicate'):
        finalised_aggregate(pd.DataFrame([row,row]),done,omitted,'batting')
    done.loc[0,'runs_numeric']=float('nan')
    with pytest.raises(ValueError,match='Unknown'):
        finalised_aggregate(pd.DataFrame([row]),done,omitted,'batting')


def test_lagging_provider_requires_an_exact_independent_source_certificate():
    done=bat(5,2,False)
    omitted=done.iloc[:0]
    row=provider('batting',done,omitted)
    row.update(battingAggregate=4,battingHighScore=4,isBattingHSNotOut=False,
               battingAverage=4,battingStrikeRate=200,battingMinutes=0)
    certificate=pd.DataFrame([dict(discipline='batting',team_id='team',source_player_id='source',
                                   metric='battingAggregate',provider_value=4,finalised_scorecard_value=5,
                                   evidence_status='independently_reconciled_scorecard_and_delivery')])
    with pytest.raises(ValueError,match='Unreconciled'):
        finalised_aggregate(pd.DataFrame([row]),done,omitted,'batting')
    out,_=finalised_aggregate(pd.DataFrame([row]),done,omitted,'batting',certificate)
    assert out.iloc[0].battingAggregate==5
    assert out.iloc[0].battingAverage==5
    certificate.loc[0,'provider_value']=3
    with pytest.raises(ValueError,match='Unreconciled'):
        finalised_aggregate(pd.DataFrame([row]),done,omitted,'batting',certificate)


def test_established_played_abandonment_is_not_mistaken_for_no_play():
    from src.data.gwhcc_incremental import eligible_match_ids
    matches=pd.DataFrame({'match_id':['played','no_play','stumps','lunch','future','forfeit'],
                          'status':['ABANDONED','ABANDONED','STUMPS','LUNCH','COMPLETED','COMPLETED'],
                          'first_match_day':['2026-10-31T01:00Z']*4+['2026-10-31T14:00Z','2026-10-31T01:00Z']})
    innings=pd.DataFrame({'match_id':matches.match_id,'runs_scored':[10,0,10,10,10,0],
                          'wickets_fallen':[0]*6,'overs_bowled':[1,0,1,1,1,0]})
    assert eligible_match_ids(matches,innings,'2026-10-31')=={'played'}


def test_participation_only_keeps_known_identity_without_inventing_performance():
    from src.data.gwhcc_finalised_aggregates import missing_provider_rows
    raw=pd.DataFrame([dict(team_id='team',player_id='other',player_name='Other',matches=1,
                           battingAggregate=10,battingHighScore=10,battingAverage=10)])
    actors=pd.DataFrame([dict(team_id='team',player_id='missing',player_name='Known',canonical_player_id='approved')])
    batting=pd.DataFrame([dict(team_id='team',participant_id='missing',runs_scored=0,balls_faced=0,
                               fours_scored=0,sixes_scored=0,dismissal_type='Did Not Bat',dismissal_text='did not bat')])
    frames={'batting':batting,
            'bowling':pd.DataFrame(columns=['team_id','participant_id','overs_bowled','runs_conceded','wickets_taken','wides','no_balls']),
            'fielding':pd.DataFrame(columns=['team_id','participant_id','catches','stumpings','run_outs','assisted_run_outs'])}
    out,added=missing_provider_rows(raw,actors,frames,{'approved'})
    assert len(added)==1 and len(out)==2
    assert added.iloc[0].battingAggregate==0
    assert pd.isna(added.iloc[0].battingHighScore)
    assert pd.isna(added.iloc[0].battingAverage)
    assert pd.isna(added.iloc[0].matches)  # Provider count is unknown; caller supplies verified weighted appearances.
    repeated, duplicate_additions = missing_provider_rows(out, actors, frames, {'approved'})
    assert duplicate_additions.empty
    pd.testing.assert_frame_equal(repeated, out)
    unchanged,_=missing_provider_rows(raw,actors,frames,set())
    pd.testing.assert_frame_equal(unchanged,raw)
    batting.loc[0,'runs_scored']=1
    with pytest.raises(ValueError,match='independently reconciled'):
        missing_provider_rows(raw,actors,frames,{'approved'})


def test_multiple_verified_missing_performers_keep_the_requested_discipline():
    import json
    from src.data.gwhcc_finalised_aggregates import missing_provider_rows
    raw=pd.DataFrame([dict(team_id='t',player_id='existing',player_name='Existing',matches=1,battingAggregate=10)])
    actors=pd.DataFrame([dict(team_id='t',player_id=pid,player_name=pid,canonical_player_id=pid) for pid in ['a','b']])
    batting=pd.DataFrame([dict(team_id='t',participant_id=pid,runs_scored=1,balls_faced=1,
                               fours_scored=0,sixes_scored=0,dismissal_type='Not Out',dismissal_text='not out') for pid in ['a','b']])
    empty_bowl=pd.DataFrame(columns=['team_id','participant_id','overs_bowled','runs_conceded','wickets_taken','wides','no_balls'])
    empty_field=pd.DataFrame(columns=['team_id','participant_id','catches','stumpings','run_outs','assisted_run_outs'])
    cert=pd.DataFrame([dict(discipline='batting',team_id='t',source_player_id=pid,metric='__missing_row__',
                            evidence_status='independently_reconciled_scorecard_and_delivery',
                            source_fields_json=json.dumps({'battingAggregate':1})) for pid in ['a','b']])
    _,added=missing_provider_rows(raw,actors,{'batting':batting,'bowling':empty_bowl,'fielding':empty_field},{'a','b'},'batting',cert)
    assert len(added)==2 and added.battingAggregate.tolist()==[1,1]
