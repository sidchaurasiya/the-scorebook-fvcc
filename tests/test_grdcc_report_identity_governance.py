import pandas as pd
from src.data import featured_record_overrides as mod


def output():
    core=pd.read_csv('clubs/georges-river-district/data/processed/hall_of_fame/prepared_career_all_time.csv')
    return mod.apply_featured_record_overrides(core,'georges-river-district')


def test_seven_report_identity_decisions_account_for_new_baseline():
    shown=output()
    assert len(shown)==2035
    assert not shown.canonical_player_id.dropna().duplicated().any()
    assert set(shown[shown.canonical_player_id.isna()].Player)=={'Warwick Geitz','Ben Worger'}
    assert not shown.Player.isin(['R. Davey','Matthew Grealy']).any()


def test_matched_report_records_keep_existing_canonical_ids_and_totals():
    shown=output().set_index('Player')
    for name,pid,metric,value in [
        ('Eric Reid','grdcc_excel_exact_e_reid','Runs',3985),
        ('Gordon Parsons','grdcc_excel_exact_g_parsons','Runs',2850),
        ('Frank Griggs','grdcc_excel_exact_f_griggs','Wickets',333),
    ]:
        assert shown.loc[name,'canonical_player_id']==pid
        assert shown.loc[name,metric]==value
    assert not {'E Reid','G Parsons','F Griggs'} & set(shown.index)


def test_report_only_names_do_not_generate_fake_profile_urls(monkeypatch):
    from src.ui import layout
    monkeypatch.setattr(layout,'public_player_profile_lookup',lambda *args:(frozenset(),{}))
    for name in ['Warwick Geitz','Ben Worger']:
        assert layout.player_profile_link_html(None,name)==name
        assert layout.resolve_public_profile_target(None,name)==''
    assert layout.resolve_public_profile_target(None,'********')==''


def test_existing_restored_identity_is_not_reassigned():
    shown=output()
    row=shown[shown.canonical_player_id.eq('raw_f1123ea2_70a6_4a78_a94c_70c4ebb75fa0')].iloc[0]
    assert row.Player=='Wasantha Hettiarachchi'
    assert row.HS=='8'
    assert row.Runs==8
