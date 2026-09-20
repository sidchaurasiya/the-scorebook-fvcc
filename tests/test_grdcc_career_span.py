import pandas as pd
from src.data import featured_record_overrides as mod


def test_historical_supplement_extends_but_does_not_truncate():
    frame = pd.DataFrame([{'Player':'Example','Seasons':'Summer 2024/25, Summer 2025/26',
        'Seasons Count':2,'Debut Season':'Summer 2024/25','Latest Season':'Summer 2025/26','Career Span':'','Runs':250,'HS':'130*'}])
    mod._extend_career_span(frame,0,['Summer 1971/72'])
    assert frame.loc[0,'Debut Season']=='Summer 1971/72'
    assert frame.loc[0,'Latest Season']=='Summer 2025/26'
    assert frame.loc[0,'Seasons Count']==3
    assert frame.loc[0,'Runs']==250 and frame.loc[0,'HS']=='130*'


def test_nick_span_survives_supplements():
    core=pd.read_csv('clubs/georges-river-district/data/processed/hall_of_fame/prepared_career_all_time.csv')
    nick=core[core.Player.eq('Nick Condylios')]
    output=mod.apply_featured_record_overrides(nick,'georges-river-district',add_missing_players=False)
    assert output['Latest Season'].iloc[0]=='Summer 2025/26'
    assert output['Debut Season'].iloc[0]=='Summer 2015/16'
    assert output['Seasons Played'].iloc[0]==11
    assert output.HS.iloc[0]=='130*'


def test_multi_profile_span_keeps_both_endpoints():
    frame=pd.DataFrame([{'Debut Season':'Summer 2000/01','Latest Season':'Summer 2005/06','Seasons Played':6}])
    mod._extend_career_span(frame,0,['Summer 1990/91','Summer 2025/26'])
    assert frame.loc[0,'Debut Season']=='Summer 1990/91'
    assert frame.loc[0,'Latest Season']=='Summer 2025/26'
