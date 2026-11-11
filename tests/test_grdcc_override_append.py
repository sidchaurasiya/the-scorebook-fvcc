import pandas as pd
from pandas.testing import assert_frame_equal
from src.data import featured_record_overrides as mod


def test_unverified_report_player_does_not_append_to_sparse_index(monkeypatch):
    monkeypatch.setattr(mod,'load_override_player_supplements',lambda *_:pd.DataFrame())
    monkeypatch.setattr(mod,'load_featured_record_overrides',lambda *_:pd.DataFrame())
    monkeypatch.setattr(mod,'load_annual_report_override_decisions',lambda *_:pd.DataFrame([
        {'player_name':'New Player','normalized_player_name':'new player','metric':'career_runs','displayed_value':165}]))
    frame=pd.DataFrame({'Player':['Existing One','Existing Two'], 'canonical_player_id':['one','two'], 'Runs':[8,10], 'HS':['8','10']},index=[0,2])
    result=mod.apply_featured_record_overrides(frame,'georges-river-district')
    assert_frame_equal(result, frame)
