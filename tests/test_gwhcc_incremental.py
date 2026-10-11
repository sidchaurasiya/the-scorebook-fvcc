import pandas as pd
import pytest

from src.data.gwhcc_incremental import append_disjoint, eligible_match_ids, merge_summary, reconciled_delivery_innings, preserve_compact_dismissal_type


def test_disjoint_append_preserves_history():
    old = pd.DataFrame([{'match_id': 'old', 'runs': 42}])
    new = pd.DataFrame([{'match_id': 'new', 'runs': 17}])
    result = append_disjoint(old, new, ['match_id'])
    pd.testing.assert_frame_equal(result.iloc[:1], old)


def test_overlap_is_rejected():
    data = pd.DataFrame([{'match_id': 'same'}])
    with pytest.raises(ValueError, match='overlaps'):
        append_disjoint(data, data, ['match_id'])


def test_duplicate_input_is_rejected():
    with pytest.raises(ValueError, match='duplicate'):
        append_disjoint(pd.DataFrame(columns=['id']), pd.DataFrame({'id': [1, 1]}), ['id'])


def test_summary_recomputes_rate_from_same_coverage():
    old = pd.DataFrame([{'id': 'p', 'runs': 100, 'outs': 4, 'average': 25}])
    new = pd.DataFrame([{'id': 'p', 'runs': 20, 'outs': 1, 'average': 20}])
    result = merge_summary(old, new, keys=['id'], sums=['runs', 'outs'], rates={'average': ('runs', 'outs', 1)})
    assert result.iloc[0]['runs'] == 120
    assert result.iloc[0]['average'] == 24


def test_historical_captain_key_without_new_evidence_is_unchanged():
    old = pd.DataFrame([{'id': 'p', 'captain': 'Historical Captain', 'runs': 100, 'outs': 4, 'average': 25.0}])
    new = pd.DataFrame([{'id': 'p', 'captain': 'Current Captain', 'runs': 20, 'outs': 1, 'average': 20.0}])
    result = merge_summary(old, new, keys=['id', 'captain'], sums=['runs', 'outs'], rates={'average': ('runs', 'outs', 1)})
    pd.testing.assert_frame_equal(result.iloc[:1], old)


def test_missing_metric_does_not_become_zero():
    old = pd.DataFrame([{'id': 'p', 'metric': None}])
    new = pd.DataFrame([{'id': 'p', 'metric': None}])
    assert pd.isna(merge_summary(old, new, keys=['id'], sums=['metric']).iloc[0]['metric'])


def test_unknown_denominator_does_not_create_rate():
    old = pd.DataFrame([{'id': 'p', 'runs': 100, 'outs': None}])
    new = pd.DataFrame([{'id': 'p', 'runs': 20, 'outs': None}])
    result = merge_summary(old, new, keys=['id'], sums=['runs', 'outs'], rates={'average': ('runs', 'outs', 1)})
    assert pd.isna(result.iloc[0]['average'])


def test_partial_denominator_does_not_create_hybrid_average():
    old = pd.DataFrame([{'id': 'p', 'runs': 100, 'outs': None}])
    new = pd.DataFrame([{'id': 'p', 'runs': 20, 'outs': 1}])
    result = merge_summary(old, new, keys=['id'], sums=['runs', 'outs'], rates={'average': ('runs', 'outs', 1)})
    assert pd.isna(result.iloc[0]['average'])


def test_summaries_require_unique_keys():
    old = pd.DataFrame({'id': ['p', 'p'], 'runs': [1, 2]})
    with pytest.raises(ValueError, match='Ambiguous'):
        merge_summary(old, old.iloc[:1], keys=['id'], sums=['runs'])


def test_cutoff_finality_activity_and_timezone():
    matches = pd.DataFrame([
        {'match_id': 'played', 'status': 'COMPLETED', 'first_match_day': '2026-10-11T01:00Z'},
        {'match_id': 'future', 'status': 'COMPLETED', 'first_match_day': '2026-10-11T14:00Z'},
        {'match_id': 'live', 'status': 'LIVE', 'first_match_day': '2026-10-10T01:00Z'},
        {'match_id': 'no_play', 'status': 'ABANDONED', 'first_match_day': '2026-10-10T01:00Z'},
    ])
    innings = pd.DataFrame({'match_id': matches.match_id, 'runs_scored': [1, 1, 1, 0], 'wickets_fallen': [0]*4, 'overs_bowled': [1, 1, 1, 0]})
    assert eligible_match_ids(matches, innings, '2026-10-11') == {'played'}


def test_partial_delivery_ledgers_do_not_supply_whole_innings_bowling_insights():
    innings = pd.DataFrame({'match_id':['m','m'],'innings_id':['complete','partial'],'runs_scored':[10,20]})
    balls = pd.DataFrame({'match_id':['m','m'],'innings_id':['complete','partial'],'total_runs':[10,5]})
    valid, audit = reconciled_delivery_innings(innings,balls)
    assert valid.innings_id.tolist() == ['complete']
    assert audit.reconciled.tolist() == [True,False]
    pd.testing.assert_frame_equal(balls.iloc[:1],valid)


def test_missing_delivery_runs_and_unavailable_bbb_remain_unsupported():
    innings = pd.DataFrame({'match_id':['m','m'],'innings_id':['missing','unavailable'],'runs_scored':[10,0]})
    balls = pd.DataFrame({'match_id':['m','m'],'innings_id':['missing','missing'],'total_runs':[10,None]})
    valid, audit = reconciled_delivery_innings(innings,balls)
    assert valid.empty
    assert not audit.reconciled.any()


def test_compact_scorecards_do_not_lose_dnb_or_explicit_not_out_evidence():
    source = pd.DataFrame({'dismissal_type':['Did Not Bat','Not Out','Bowled'], 'dismissal_text':[None,'','b: Public Bowler']})
    compact = preserve_compact_dismissal_type(source)
    assert compact.dismissal_text.tolist() == ['Did Not Bat','Not Out','b: Public Bowler']
    assert source.dismissal_text.isna().sum() == 1


def test_unknown_dismissal_is_not_invented():
    source = pd.DataFrame({'dismissal_type':[None], 'dismissal_text':[None]})
    assert preserve_compact_dismissal_type(source).iloc[0].dismissal_text == ''
