from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from src.data import gwhcc_historical_career as history
from src.data import gwhcc_document_overrides as docs

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'clubs/glen-waverley-hawks/data'
CHRIS = 'raw_f62c84ce_8d81_4700_bd22_ee8494bab921'
MATTHEW = 'raw_289b8e53_aa95_4072_8288_588447304bcd'


@pytest.fixture
def match_sources(tmp_path, monkeypatch):
    anchors = tmp_path / 'match_anchors.csv'
    pd.DataFrame([{
        'canonical_player_id': 'target', 'canonical_player_name': 'Target Player',
        'anchor_through_season': 'Summer 2025/26', 'matches': 10.5,
        'source_document': 'Club source', 'source_sheet': 'Career', 'source_row': 7,
        'source_sha256': 'a' * 64, 'confidence': 'high', 'decision_status': 'approved_dated_career',
    }]).to_csv(anchors, index=False)
    batting = tmp_path / 'batting.csv'
    pd.DataFrame([
        {'canonical_player_id': 'target', 'season_id': 's25', 'season': 'Summer 2025/26', 'team_id': 'old', 'grade_id': 'g', 'matches': 99},
        {'canonical_player_id': 'target', 'season_id': 's26', 'season': 'Summer 2026/27', 'team_id': 'played', 'grade_id': 'g', 'matches': 1},
        {'canonical_player_id': 'target', 'season_id': 's26', 'season': 'Summer 2026/27', 'team_id': 't20', 'grade_id': 'g', 'matches': 0.5},
        {'canonical_player_id': 'target', 'season_id': 's26', 'season': 'Summer 2026/27', 'team_id': 'no-play', 'grade_id': 'g', 'matches': 0},
    ]).to_csv(batting, index=False)
    monkeypatch.setattr(history, 'MATCH_ANCHORS', anchors)
    monkeypatch.setattr(history, 'BATTING', batting)
    history.later_match_counts.cache_clear()
    return anchors, batting


@pytest.fixture
def career():
    return pd.DataFrame([{'canonical_player_id': 'target', 'Player': 'Target Player', 'Matches': 100.0,
                          'Runs': 900, 'Innings': 80, 'Not Outs': 9, 'Wickets': 20, 'Catches': 30,
                          'Win %': 60.0}])


def test_closed_match_anchor_replaces_overlap_and_uses_only_weighted_later_appearances(match_sources, career):
    result = history.apply_dated_match_anchors(career)
    assert result.loc[0, 'Matches'] == 12
    assert result.loc[0, 'Matches'] != 100 + 10.5 + 1.5
    assert result.loc[0, 'detailed_matches_value'] == 100
    assert result.loc[0, 'historical_match_anchor_value'] == 10.5
    pd.testing.assert_frame_equal(result[career.columns.drop('Matches')], career.drop(columns='Matches'))
    pd.testing.assert_frame_equal(history.apply_dated_match_anchors(result), result)


def test_match_only_decision_uses_the_complete_authoritative_career_boundary(match_sources, career):
    result = history.apply_dated_career_anchors(career)
    assert result.loc[0, 'Matches'] == 12
    assert result.loc[0, 'Runs'] == career.loc[0, 'Runs']


@pytest.mark.parametrize('status,confidence', [('review', 'high'), ('rejected', 'high'), ('pending', 'confirmed'),
                                               ('unknown', 'approved'), ('approved_dated_career', 'review')])
def test_unapproved_match_evidence_does_not_apply(status, confidence, match_sources, career):
    path, _ = match_sources
    rows = pd.read_csv(path)
    rows['decision_status'] = status
    rows['confidence'] = confidence
    rows.to_csv(path, index=False)
    pd.testing.assert_frame_equal(history.apply_dated_match_anchors(career), career)


@pytest.mark.parametrize('value', [-1, 0.25, float('inf'), None])
def test_invalid_historical_game_credits_fail_closed(value, match_sources, career):
    path, _ = match_sources
    rows = pd.read_csv(path)
    rows['matches'] = value
    rows.to_csv(path, index=False)
    with pytest.raises(ValueError, match='weighted match count'):
        history.apply_dated_match_anchors(career)


@pytest.mark.parametrize('problem', ['duplicate', 'missing_key', 'missing_count', 'negative', 'quarter', 'infinite', 'season', 'identity'])
def test_ambiguous_or_unknown_later_appearance_counts_fail_closed(problem, match_sources, career):
    _, path = match_sources
    rows = pd.read_csv(path)
    if problem == 'duplicate':
        rows = pd.concat([rows, rows.tail(1)], ignore_index=True)
    elif problem == 'missing_key':
        rows.loc[1, 'team_id'] = pd.NA
    elif problem == 'missing_count':
        rows.loc[1, 'matches'] = pd.NA
    elif problem == 'negative':
        rows.loc[1, 'matches'] = -1
    elif problem == 'quarter':
        rows.loc[1, 'matches'] = 0.25
    elif problem == 'infinite':
        rows.loc[1, 'matches'] = float('inf')
    elif problem == 'season':
        rows.loc[1, 'season'] = 'unknown'
    else:
        rows['canonical_player_id'] = 'another-id'
    rows.to_csv(path, index=False)
    with pytest.raises(ValueError):
        history.apply_dated_match_anchors(career)


def test_future_incremental_season_preserves_the_anchor_and_invalidates_compact_cache(match_sources, career):
    _, path = match_sources
    first = history.apply_dated_match_anchors(career)
    rows = pd.read_csv(path)
    extra = rows.iloc[2].to_dict()
    extra.update(season='Summer 2027/28', season_id='s27')
    pd.concat([rows, pd.DataFrame([extra])], ignore_index=True).to_csv(path, index=False)
    second = history.apply_dated_match_anchors(first)
    assert first.loc[0, 'Matches'] == 12
    assert second.loc[0, 'Matches'] == 12.5
    assert second.loc[0, 'historical_match_anchor_value'] == 10.5
    assert second.loc[0, 'detailed_matches_value'] == 100


@pytest.mark.parametrize('dtype', ['object', 'string[python]', 'string[pyarrow]'])
def test_source_provenance_is_string_compatible(dtype, match_sources, career):
    for column in ['matches_authority_source_row', 'matches_authority_source', 'matches_authority_scope',
                   'matches_value_source', 'historical_match_anchor_source', 'historical_match_anchor_through_season']:
        career[column] = pd.Series([''], dtype=dtype)
    result = history.apply_dated_match_anchors(career)
    assert result.loc[0, 'matches_authority_source_row'] == '7'
    assert result.loc[0, 'Matches'] == 12
    assert result.loc[0, 'matches_authority_source'] == 'dated_club_match_anchor'


def test_public_identity_boundary_and_other_clubs_are_preserved(match_sources, career):
    for club in ['fvcc', 'georges-river-district']:
        pd.testing.assert_frame_equal(history.apply_dated_match_anchors(career, club_id=club), career)
    for private in [{'Player': 'Private player'}, {'is_private': True}]:
        protected = career.assign(**private)
        pd.testing.assert_frame_equal(history.apply_dated_match_anchors(protected), protected)
    name_only = career.assign(canonical_player_id='unknown')
    pd.testing.assert_frame_equal(history.apply_dated_match_anchors(name_only), name_only)
    with pytest.raises(ValueError, match='one public canonical'):
        history.apply_dated_match_anchors(pd.concat([career, career], ignore_index=True))


def test_explicit_match_decisions_do_not_enable_old_review_overrides():
    anchors = history.load_dated_match_anchors().set_index('canonical_player_id')
    expected = pd.read_csv(ROOT / 'tests/fixtures/gwhcc_clubwide_match_expected.csv')
    assert anchors.index.is_unique and set(anchors.index) == set(expected.canonical_player_id)
    assert anchors.loc[[CHRIS, MATTHEW], 'anchor_through_season'].eq('Summer 2025/26').all()
    assert anchors.loc[CHRIS, 'matches'] == 390.5
    assert anchors.loc[MATTHEW, 'matches'] == 296
    reviews = pd.read_csv(docs.RECORD_OVERRIDES)
    rows = reviews[reviews.player_name.isin(['C. Briginshaw', 'M. Briginshaw']) & reviews.metric.eq('games')]
    assert len(rows) == 2 and rows.confidence.eq('review').all()
    assert history.load_dated_career_anchors().canonical_player_id.nunique() == 63
    assert docs.load_historical_career_metric_decisions().canonical_player_id.nunique() == 21


def test_actual_later_season_is_one_eligible_appearance_each_not_two_wickets():
    annual = pd.read_csv(history.BATTING)
    current = annual[annual.season.eq('Summer 2026/27') & annual.canonical_player_id.isin([CHRIS, MATTHEW])]
    assert current.groupby('canonical_player_id').matches.sum().to_dict() == {CHRIS: 1, MATTHEW: 1}
    batting = pd.read_csv(DATA / 'processed/all_seasons_scorecard_batting.csv')
    matches = pd.read_csv(DATA / 'processed/all_seasons_matches.csv')
    ids = set(matches.loc[matches.season.eq('Summer 2026/27'), 'match_id'])
    assert len(ids) == 37
    for pid in [CHRIS, MATTHEW]:
        raw_id = pid.removeprefix('raw_').replace('_', '-')
        selected = batting[batting.season.eq('Summer 2026/27') & batting.player_id.eq(raw_id)]
        assert set(selected.match_id) == {'75c15b5e-5677-4838-81ba-3837124bfabd'}
        assert set(selected.match_id) <= ids


def test_full_authoritative_frame_changes_only_explicit_match_counts(monkeypatch, tmp_path):
    base = pd.read_csv(DATA / 'processed/hall_of_fame/prepared_career_all_time.csv')
    with monkeypatch.context() as old:
        old.setattr(history, 'MATCH_ANCHORS', tmp_path / 'absent.csv')
        before = docs.apply_record_overrides(base, write_decisions=False)
    after = docs.apply_record_overrides(base, write_decisions=False)
    assert len(after) == 1291 and after.canonical_player_id.is_unique
    unchanged = before.columns.drop(['Matches', 'matches_override_applied', 'matches_value_source'], errors='ignore')
    pd.testing.assert_frame_equal(before[unchanged], after[unchanged], check_dtype=False)
    changed = before.Matches.ne(after.Matches)
    expected = pd.read_csv(ROOT / 'tests/fixtures/gwhcc_clubwide_match_expected.csv')
    assert set(after.loc[changed, 'canonical_player_id']) == set(expected.canonical_player_id)
    assert after.loc[after.canonical_player_id.eq(CHRIS), 'Matches'].tolist() == [391.5]
    assert after.loc[after.canonical_player_id.eq(MATTHEW), 'Matches'].tolist() == [297]
    assert (after.loc[changed, 'Matches'] - before.loc[changed, 'Matches']).sum() == pytest.approx(
        (expected.candidate_matches - expected.before_match_anchors).sum())


def test_digital_prepared_core_stays_valid_and_display_uses_the_same_authority(monkeypatch):
    from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
    from src.ui import layout
    monkeypatch.setenv('CLUB_ID', history.CLUB_ID)
    manifest = json.loads((DATA / 'processed/hall_of_fame/prepared_core_manifest.json').read_text())
    core = load_prepared_hall_of_fame_core(history.CLUB_ID, manifest['data_version'])
    assert core is not None
    raw = core['all_time']
    assert raw.loc[raw.canonical_player_id.eq(CHRIS), 'Matches'].tolist() == [334.5]
    governed = docs.apply_record_overrides(raw, write_decisions=False)
    displayed = layout.add_gwhcc_not_outs_for_display(governed, core['batting'])
    for pid, expected, target, missing in [(CHRIS, 391.5, 400, 8.5), (MATTHEW, 297, 300, 3)]:
        row = displayed[displayed.canonical_player_id.eq(pid)].iloc[0]
        assert row.Matches == expected
        milestone = {r['category']: r for r in layout.player_milestone_rows(row)}['Matches']
        assert milestone['current'] == expected
        assert milestone['target'] == target
        assert target - expected == missing
        note = history.career_anchor_coverage_note(row)
        assert 'Summer 2025/26' in note and 'Historical season/grade match detail is incomplete' in note
        assert 'Matches, fielding' not in note


def test_profile_milestone_half_credits_are_hawks_only(monkeypatch):
    from src.ui import layout
    career = pd.Series({'Matches': 391.5})
    for club in ['fvcc', 'georges-river-district']:
        monkeypatch.setenv('CLUB_ID', club)
        row = layout.player_milestone_rows(career)[0]
        assert row['current'] == 391 and row['remaining'] == 9
    monkeypatch.setenv('CLUB_ID', history.CLUB_ID)
    row = layout.player_milestone_rows(career)[0]
    assert row['current'] == 391.5 and row['remaining'] == 8.5


def test_undated_historical_match_totals_do_not_create_current_season_achievement_dates(monkeypatch):
    from src.ui import layout
    monkeypatch.setenv('CLUB_ID', history.CLUB_ID)
    raw = pd.read_csv(DATA / 'processed/hall_of_fame/prepared_career_all_time.csv')
    data = {'all_time': docs.apply_record_overrides(raw, write_decisions=False),
            **{f'{d}_raw': pd.read_csv(DATA / f'processed/all_seasons_{d}.csv', low_memory=False)
               for d in ['batting', 'bowling', 'fielding']}}
    achieved = layout.build_achieved_milestones(data, ['Summer 2026/27'], history.CLUB_ID)
    assert achieved[achieved.canonical_player_id.isin([CHRIS, MATTHEW]) & achieved.Category.eq('Matches')].empty
