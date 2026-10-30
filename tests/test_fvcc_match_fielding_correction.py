import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from scripts.correct_fvcc_match_fielding import (
    apply_catch_deltas, catch_delta, plan, reconcile_batting_descriptions,
    replace_match_rows, update_breakdown, validate_bowling,
    stage_transaction, replay_transaction,
)


@pytest.fixture
def aggregate():
    return pd.DataFrame([
        dict(season_id='s', team_id='t', player_id='public', matches='2',
             fieldingCatchesNonWK='1.0', fieldingCatchesWK='0.0', fieldingTotalCatches='1.0'),
        dict(season_id='history', team_id='t', player_id='public', matches='9',
             fieldingCatchesNonWK='7.0', fieldingCatchesWK='0.0', fieldingTotalCatches='7.0'),
    ])


def official(n=3):
    return {'public': dict(fieldingCatchesNonWK=n, fieldingCatchesWK=0, fieldingTotalCatches=n)}


def field(n):
    return pd.DataFrame([dict(match_id='m', player_id='public', catches=n)])


def batting(text='c: Old b: Bowler'):
    return pd.DataFrame([dict(match_id='m', player_id='public', runs='12', balls='20', fours='1', sixes='0', strike_rate='60', dismissal=text)])


def test_finalized_fielding_delta_is_new_minus_old():
    assert catch_delta(field(1), field(3)) == {'public': 2}


def test_match_rows_replace_instead_of_append():
    before = pd.concat([field(1), field(8).assign(match_id='other')], ignore_index=True)
    result = replace_match_rows(before, field(3), 'm')
    assert len(result) == 2
    assert result.match_id.tolist().count('m') == 1


def test_replacement_second_run_is_no_delta():
    result = replace_match_rows(field(1), field(3), 'm')
    assert catch_delta(result, field(3)) == {}


def test_season_catches_reconcile_independent_source(aggregate):
    result = apply_catch_deltas(aggregate, {'public': 2}, official(), 's', 't')
    assert float(result.iloc[0].fieldingTotalCatches) == 3


def test_appearances_unchanged(aggregate):
    result = apply_catch_deltas(aggregate, {'public': 2}, official(), 's', 't')
    assert result.matches.tolist() == aggregate.matches.tolist()


def test_history_unchanged(aggregate):
    result = apply_catch_deltas(aggregate, {'public': 2}, official(), 's', 't')
    assert_frame_equal(result.iloc[1:], aggregate.iloc[1:])


def test_unrelated_player_unchanged(aggregate):
    aggregate.loc[1, 'player_id'] = 'other'
    result = apply_catch_deltas(aggregate, {'public': 2}, official(), 's', 't')
    assert_frame_equal(result.iloc[1:], aggregate.iloc[1:])


def test_canonical_source_id_must_already_exist(aggregate):
    with pytest.raises(ValueError, match='existing unambiguous'):
        apply_catch_deltas(aggregate, {'new': 1}, {}, 's', 't')


def test_duplicate_aggregate_key_rejected(aggregate):
    with pytest.raises(ValueError, match='Duplicate aggregate'):
        apply_catch_deltas(pd.concat([aggregate, aggregate]), {'public': 2}, official(), 's', 't')


def test_mismatched_match_and_season_delta_rejected(aggregate):
    with pytest.raises(ValueError, match='does not reconcile'):
        apply_catch_deltas(aggregate, {'public': 1}, official(), 's', 't')


def test_keeper_components_preserved_and_verified(aggregate):
    source = official()
    source['public']['fieldingCatchesNonWK'] = 2
    source['public']['fieldingCatchesWK'] = 1
    result = apply_catch_deltas(aggregate, {'public': 2}, source, 's', 't')
    assert float(result.iloc[0].fieldingCatchesWK) == 1


def test_caught_description_replaced_without_stat_change():
    before = batting()
    result, changes = reconcile_batting_descriptions(before, batting('c: New b: Bowler'), 'm')
    assert len(changes) == 1
    assert changes[0]['statistical_type_change'] is False
    assert_frame_equal(result.drop(columns='dismissal'), before.drop(columns='dismissal'))


def test_description_repeat_is_idempotent():
    result, _ = reconcile_batting_descriptions(batting(), batting('c: New b: Bowler'), 'm')
    again, changes = reconcile_batting_descriptions(result, batting('c: New b: Bowler'), 'm')
    assert_frame_equal(result, again)
    assert changes == []


def test_not_out_transition_rejected():
    with pytest.raises(ValueError, match='Dismissal type'):
        reconcile_batting_descriptions(batting(), batting('not out'), 'm')


def test_batting_numeric_change_rejected():
    changed = batting().assign(runs='13')
    with pytest.raises(ValueError, match='Batting figure'):
        reconcile_batting_descriptions(batting(), changed, 'm')


def test_roster_change_rejected():
    with pytest.raises(ValueError, match='Roster change'):
        reconcile_batting_descriptions(batting(), batting().assign(player_id='new'), 'm')


def bowling(overs='2', player_id='bowler'):
    return pd.DataFrame([dict(player_id=player_id, overs=overs, maidens='0', runs_conceded='0', wickets='0', wides='0', no_balls='0')])


def test_zero_over_placeholders_not_legitimate_bowlers():
    validate_bowling(bowling(), pd.concat([bowling(), bowling('0', 'nonbowler')]))


def test_changed_bowling_figure_rejected():
    with pytest.raises(ValueError, match='Substantive bowling'):
        validate_bowling(bowling(), bowling().assign(wickets='1'))


def breakdown():
    return pd.DataFrame([dict(canonical_player_id='public', dimension='Season', discipline='Fielding', breakdown_label='s', catches='1.0', dismissals='2.0', stumpings='1.0', matches='')])


def test_profile_fielding_and_dismissals_propagate():
    increment = breakdown().assign(catches='2', dismissals='2', stumpings='0')
    result = update_breakdown(breakdown(), increment)
    assert float(result.iloc[0].catches) == 3
    assert float(result.iloc[0].dismissals) == 4
    assert result.iloc[0].matches == ''
    assert result.iloc[0].stumpings == '1.0'


def test_profile_new_dimension_does_not_invent_appearances():
    increment = breakdown().assign(dimension='Ground', breakdown_label='new', catches='2', dismissals='2', stumpings='0')
    result = update_breakdown(breakdown(), increment)
    assert len(result) == 2
    assert result.iloc[1].matches == ''


def test_other_clubs_rejected_before_any_source_loading():
    for club in ['glen-waverley-hawks', 'georges-river-district']:
        with pytest.raises(ValueError, match='FVCC-only'):
            plan({}, [], club_id=club)


def test_duplicate_match_fielding_identity_rejected():
    with pytest.raises(ValueError, match='Ambiguous player'):
        catch_delta(pd.concat([field(1), field(1)]), field(3))


@pytest.mark.parametrize('value', [-1, 1.5, float('nan')])
def test_invalid_match_catch_counter_rejected(value):
    with pytest.raises(ValueError, match='Invalid match catch'):
        catch_delta(field(1), field(value))


def test_pending_transaction_replays_after_partial_write(tmp_path):
    data, evidence = tmp_path / 'data', tmp_path / 'evidence'
    data.mkdir()
    (data / 'one.csv').write_text('n\n1\n')
    (data / 'two.csv').write_text('n\n2\n')
    journal = stage_transaction(data, {'one.csv': pd.DataFrame({'n': [3]}), 'two.csv': pd.DataFrame({'n': [4]})}, evidence, 'source', {})
    (data / 'one.csv').write_bytes((evidence / 'staged/one.csv').read_bytes())
    replay_transaction(data, evidence, journal, 'source')
    assert pd.read_csv(data / 'one.csv').n.tolist() == [3]
    assert pd.read_csv(data / 'two.csv').n.tolist() == [4]


def test_transaction_replay_is_byte_idempotent(tmp_path):
    data, evidence = tmp_path / 'data', tmp_path / 'evidence'
    data.mkdir(); (data / 'one.csv').write_text('n\n1\n')
    journal = stage_transaction(data, {'one.csv': pd.DataFrame({'n': [3]})}, evidence, 'source', {})
    replay_transaction(data, evidence, journal, 'source')
    first = (data / 'one.csv').read_bytes()
    replay_transaction(data, evidence, journal, 'source')
    assert first == (data / 'one.csv').read_bytes()


def test_transaction_does_not_overwrite_intervening_edit(tmp_path):
    data, evidence = tmp_path / 'data', tmp_path / 'evidence'
    data.mkdir(); (data / 'one.csv').write_text('n\n1\n')
    journal = stage_transaction(data, {'one.csv': pd.DataFrame({'n': [3]})}, evidence, 'source', {})
    (data / 'one.csv').write_text('n\n99\n')
    with pytest.raises(ValueError, match='Intervening edit'):
        replay_transaction(data, evidence, journal, 'source')
    assert (data / 'one.csv').read_text() == 'n\n99\n'
