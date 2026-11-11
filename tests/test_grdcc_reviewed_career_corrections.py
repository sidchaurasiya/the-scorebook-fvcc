import pandas as pd
import pytest
from src.data.grdcc_career_refresh import apply_reviewed_baseline_corrections


def example():
    baseline=pd.DataFrame([{'canonical_player_id':'public_fixture','metric':'Runs','through_season_start':2025,'governed_value':3981},
                           {'canonical_player_id':'another_fixture','metric':'Runs','through_season_start':2025,'governed_value':900}])
    corrections=pd.DataFrame([{'canonical_player_id':'public_fixture','metric':'Runs','through_season_start':2025,'previous_governed_value':3981,'corrected_value':3522,'status':'source_verified'}])
    return baseline,corrections


def test_reviewed_overlap_and_cutoff_correction_is_exact_and_idempotent():
    baseline,corrections=example();old=baseline.copy(deep=True)
    result=apply_reviewed_baseline_corrections(baseline,corrections)
    assert result.governed_value.tolist()==[3522,900]
    assert result.correction_applied.tolist()==[True,False]
    pd.testing.assert_frame_equal(result,apply_reviewed_baseline_corrections(result,corrections))
    pd.testing.assert_frame_equal(baseline,old)
    assert 3259+263+17==3539 and 722-263==459


def test_unknown_source_decision_cannot_change_baseline():
    baseline,corrections=example();corrections['status']='needs_source_confirmation'
    assert apply_reviewed_baseline_corrections(baseline,corrections).governed_value.tolist()==[3981,900]


def test_duplicate_or_changed_seed_fails_closed():
    baseline,corrections=example()
    with pytest.raises(ValueError,match='Duplicate'):
        apply_reviewed_baseline_corrections(baseline,pd.concat([corrections,corrections]))
    baseline.loc[0,'governed_value']=9999
    with pytest.raises(ValueError,match='changed'):
        apply_reviewed_baseline_corrections(baseline,corrections)


def test_unrelated_metric_does_not_receive_a_runs_correction():
    baseline,corrections=example();baseline.loc[0,'metric']='Wickets'
    with pytest.raises(ValueError,match='exact'):
        apply_reviewed_baseline_corrections(baseline,corrections)


def test_reviewed_correction_applies_with_no_later_season_rows(monkeypatch,tmp_path):
    from src.data import grdcc_career_refresh as refresh
    from src.utils import player_identity as identity
    baseline,corrections=example()
    baseline_path=tmp_path/'baselines.csv';baseline.to_csv(baseline_path,index=False)
    corrections.to_csv(tmp_path/'reviewed_career_baseline_corrections.csv',index=False)
    source=pd.DataFrame([{'season':'Summer 2025/26','canonical_player_id':'public_fixture','battingAggregate':3522,'bowlingWickets':0}])
    path=tmp_path/'source.csv';source.to_csv(path,index=False)
    monkeypatch.setattr(refresh,'BASELINE_PATH',baseline_path)
    monkeypatch.setattr(refresh,'get_processed_path',lambda *args,**kwargs:path)
    monkeypatch.setattr(identity,'apply_player_identity_mapping',lambda frame,**kwargs:frame)
    monkeypatch.setattr(identity,'filter_public_player_rows',lambda frame,*args,**kwargs:frame)
    frame=pd.DataFrame([{'canonical_player_id':'public_fixture','Runs':3981}])
    assert refresh.apply_later_season_totals(frame,'georges-river-district').Runs.iloc[0]==3522
    assert refresh.apply_later_season_totals(frame,'fvcc').Runs.iloc[0]==3981
