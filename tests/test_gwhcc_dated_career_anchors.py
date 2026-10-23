from __future__ import annotations

import subprocess
from pathlib import Path

import pandas as pd
import pytest

from src.data import gwhcc_historical_career as history
from src.data.gwhcc_document_overrides import apply_record_overrides

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "clubs/glen-waverley-hawks/data"
CHRIS = "raw_f62c84ce_8d81_4700_bd22_ee8494bab921"
MATTHEW = "raw_289b8e53_aa95_4072_8288_588447304bcd"


@pytest.fixture
def later_sources(tmp_path, monkeypatch):
    for discipline, columns in history.SOURCE_COLUMNS.items():
        rows = []
        for pid in [CHRIS, MATTHEW]:
            for year in [2025, 2026]:
                row = {"canonical_player_id": pid, "season_id": str(year), "team_id": "team", "grade_id": "grade",
                       "season": f"Summer {year}/{(year+1)%100:02d}"}
                row.update({column: 999 if year == 2025 else 0 for column in columns.values()})
                if pid == MATTHEW and year == 2026 and discipline == "bowling":
                    row.update(bowlingWickets=2, bowlingRuns=6)
                rows.append(row)
        path = tmp_path / f"{discipline}.csv"
        pd.DataFrame(rows).to_csv(path, index=False)
        monkeypatch.setattr(history, discipline.upper(), path)
    history.later_career_counts.cache_clear()
    return tmp_path


@pytest.fixture
def source_frame():
    return pd.DataFrame([
        {"canonical_player_id": CHRIS, "Player": "Chris Briginshaw", "Matches": 334.5, "Runs": 5995,
         "Innings": 345, "Not Outs": 30, "Outs": 315, "Wickets": 28, "Runs Against": 811,
         "Catches": 95, "HS": "190", "100s": 6, "Bat Avg": 5995/315, "Bowl Avg": 811/28},
        {"canonical_player_id": MATTHEW, "Player": "Matthew Briginshaw", "Matches": 226, "Runs": 1880,
         "Innings": 186, "Not Outs": 42, "Outs": 144, "Wickets": 416, "Runs Against": 8497,
         "Catches": 49, "HS": "119*", "100s": 1, "Bat Avg": 1880/144, "Bowl Avg": 8497/416},
        {"canonical_player_id": "other", "Player": "Other Player", "Matches": 12, "Runs": 100,
         "Innings": 8, "Not Outs": 0, "Outs": 8, "Wickets": 1, "Runs Against": 10,
         "Catches": 3, "HS": "30", "100s": 0, "Bat Avg": 12.5, "Bowl Avg": 10},
    ])


def test_inherited_two_explicit_dated_sources_are_preserved():
    source = pd.read_csv(history.ANCHORS)
    assert set(source.canonical_player_id) == {CHRIS, MATTHEW}
    assert source.anchor_through_season.eq("Summer 2025/26").all()
    assert source.decision_status.eq("approved_dated_career").all()
    assert not {"matches", "catches", "highest_score", "hundreds"}.intersection(source.columns)


def test_closed_anchor_replaces_overlap_and_only_later_counts_are_added(later_sources, source_frame):
    result = history.apply_dated_career_anchors(source_frame).set_index("canonical_player_id")
    assert result.loc[CHRIS, "Runs"] == 7051
    assert result.loc[MATTHEW, "Runs"] == 2417
    assert result.loc[CHRIS, "Wickets"] == 35
    assert result.loc[MATTHEW, "Wickets"] == 535
    assert result.loc[MATTHEW, "Runs Against"] == 10606
    assert result.loc[MATTHEW, "Wickets"] != 533 + 416
    assert result.loc[CHRIS, "Runs"] != 7051 + 5995


def test_all_average_counts_have_the_same_scope_and_unrelated_values_stay_fixed(later_sources, source_frame):
    result = history.apply_dated_career_anchors(source_frame)
    pd.testing.assert_frame_equal(result[["Matches", "Catches", "HS", "100s"]], source_frame[["Matches", "Catches", "HS", "100s"]])
    pd.testing.assert_series_equal(result.iloc[2][source_frame.columns], source_frame.iloc[2], check_dtype=False)
    for row in result.head(2).to_dict("records"):
        assert row["Bat Avg"] == pytest.approx(row["Runs"] / (row["Innings"] - row["Not Outs"]))
        assert row["Bowl Avg"] == pytest.approx(row["Runs Against"] / row["Wickets"])
        assert row["Outs"] == row["Innings"] - row["Not Outs"]


def test_application_is_idempotent_and_keeps_original_detailed_values(later_sources, source_frame):
    once = history.apply_dated_career_anchors(source_frame)
    twice = history.apply_dated_career_anchors(once)
    pd.testing.assert_frame_equal(once, twice)
    assert twice.loc[0, "detailed_runs_value"] == 5995
    assert twice.loc[1, "detailed_not_outs_value"] == 42


@pytest.mark.parametrize("status", ["review", "rejected", "pending", ""])
def test_unapproved_sources_remain_audit_only(status, tmp_path, monkeypatch, source_frame):
    source = pd.read_csv(history.ANCHORS)
    source["decision_status"] = status
    path = tmp_path / "anchors.csv"
    source.to_csv(path, index=False)
    monkeypatch.setattr(history, "ANCHORS", path)
    pd.testing.assert_frame_equal(history.apply_dated_career_anchors(source_frame), source_frame)


@pytest.mark.parametrize("problem", ["duplicate", "unknown", "invalid_season", "missing_identity"])
def test_ambiguous_later_contributions_fail_closed(problem, later_sources, source_frame):
    source = pd.read_csv(history.BOWLING)
    if problem == "duplicate":
        source = pd.concat([source, source.tail(1)], ignore_index=True)
    elif problem == "unknown":
        source.loc[source.season_id.eq(2026), "bowlingRuns"] = pd.NA
    elif problem == "missing_identity":
        source = source[source.canonical_player_id.ne(MATTHEW)]
    else:
        source.loc[source.season_id.eq(2026), "season"] = "unknown"
    source.to_csv(history.BOWLING, index=False)
    with pytest.raises(ValueError):
        history.apply_dated_career_anchors(source_frame)


def test_future_refresh_keeps_closed_anchor_and_adds_a_disjoint_new_season(later_sources, source_frame):
    before = history.apply_dated_career_anchors(source_frame)
    source = pd.read_csv(history.BOWLING)
    row = source.iloc[-1].to_dict()
    row.update(season="Summer 2027/28", season_id="2027", bowlingWickets=3, bowlingRuns=30)
    pd.concat([source, pd.DataFrame([row])]).to_csv(history.BOWLING, index=False)
    after = history.apply_dated_career_anchors(source_frame)
    assert before.loc[1, "Wickets"] == 535
    assert after.loc[1, "Wickets"] == 538
    assert after.loc[1, "Runs Against"] == 10636
    assert after.loc[1, "Runs"] == 2417


def test_other_clubs_and_protected_identities_are_unchanged(later_sources, source_frame):
    for club in ["fvcc", "georges-river-district"]:
        pd.testing.assert_frame_equal(history.apply_dated_career_anchors(source_frame, club_id=club), source_frame)
    protected = source_frame.head(1).copy()
    protected["Player"] = "Private player"
    pd.testing.assert_frame_equal(history.apply_dated_career_anchors(protected), protected)
    protected["Player"] = "Chris Briginshaw"
    protected["is_private"] = True
    pd.testing.assert_frame_equal(history.apply_dated_career_anchors(protected), protected)


def test_real_authoritative_frame_changes_only_explicit_source_identities():
    from src.data import gwhcc_document_overrides as docs
    base = pd.read_csv(DATA / "processed/hall_of_fame/prepared_career_all_time.csv")
    batting = pd.read_csv(DATA / "processed/hall_of_fame/prepared_career_batting.csv")
    base = base.merge(batting[["canonical_player_id", "battingNotOuts"]].rename(columns={"battingNotOuts": "Not Outs"}), on="canonical_player_id", validate="one_to_one")
    before = docs.apply_historical_career_metric_decisions(docs.apply_historical_career_supplements(base))
    after = history.apply_dated_career_anchors(before)
    mask = ~before.canonical_player_id.isin(set(history.load_dated_career_anchors().canonical_player_id))
    pd.testing.assert_frame_equal(before.loc[mask].reset_index(drop=True), after.loc[mask, before.columns].reset_index(drop=True), check_dtype=False)
    assert len(after) == len(base) == 1284
    assert after.canonical_player_id.is_unique
    assert docs.load_historical_career_metric_decisions().canonical_player_id.nunique() == 21


@pytest.mark.parametrize("pid,name,expected", [
    (CHRIS, "Chris Briginshaw", (334.5, 7051, 407, 37, 35, 95, 6, "Summer 1989/90")),
    (MATTHEW, "Matthew Briginshaw", (226, 2417, 238, 44, 535, 49, 1, "Summer 1990/91")),
])
def test_actual_profile_search_summary_and_annual_detail(pid, name, expected, monkeypatch):
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", history.CLUB_ID)
    index = layout.load_player_profile_index(history.CLUB_ID, layout.metadata_mtime(), layout.player_aliases_mtime())
    assert index[index.id.eq(pid)].name.tolist() == [name]
    profile = layout.get_player_profile_data(pid, layout.metadata_mtime(), layout.player_aliases_mtime(), club_id=history.CLUB_ID)
    view = layout.build_player_profile_view.__wrapped__(profile, layout.player_profile_view_signature())
    row = view["career"].iloc[0]
    columns = ["Matches", "Runs", "Innings", "Not Outs", "Wickets", "Catches", "100s", "earliest_documented_season"]
    assert tuple(row[c] for c in columns) == expected
    assert row.Player == name
    assert min(view["season_table"].Season, key=history.season_start) == "Summer 1995/96"
    assert view["season_table"].Runs.sum() == (5995 if pid == CHRIS else 1880)
    assert view["season_table"].Wickets.sum() == (28 if pid == CHRIS else 416)
    assert view["season_table"].Innings.sum() == (345 if pid == CHRIS else 186)
    assert view["grade_table"].Runs.sum() == (5995 if pid == CHRIS else 1880)
    assert view["grade_table"].Wickets.sum() == (28 if pid == CHRIS else 416)
    assert history.COVERAGE_NOTE in layout.player_profile_historical_coverage_html(row, view["season_table"])
    assert dict(layout.player_profile_batting_career_metrics(row, str(expected[0])))["Not Outs"] == str(expected[3])
    all_time = pd.read_csv(DATA / "processed/hall_of_fame/prepared_career_all_time.csv")
    governed = apply_record_overrides(all_time, write_decisions=False)
    batting = pd.read_csv(DATA / "processed/hall_of_fame/prepared_career_batting.csv")
    displayed = layout.add_gwhcc_not_outs_for_display(governed, batting)
    hof = displayed[displayed.canonical_player_id.eq(pid)].iloc[0]
    assert tuple(hof[c] for c in columns) == expected
    for metric in ["Runs", "Wickets", "Not Outs", "Bat Avg", "Bowl Avg"]:
        assert row[metric] == hof[metric]
    milestones = {r["category"]: r for r in layout.player_milestone_rows(row)}
    assert milestones["Runs"]["current"] == expected[1]
    assert milestones["Runs"]["target"] == (8000 if pid == CHRIS else 3000)
    assert milestones["Wickets"]["current"] == expected[4]
    assert milestones["Wickets"]["target"] == (100 if pid == CHRIS else 600)


def test_no_source_season_snapshot_or_other_club_files_changed():
    changed = subprocess.check_output(["git", "diff", "--name-only"], cwd=ROOT, text=True).splitlines()
    assert not any("/data/processed/" in p or "source/excel" in p for p in changed)
    assert not any(p.startswith(("clubs/fvcc/", "clubs/georges-river-district/")) for p in changed)


@pytest.mark.parametrize("pid,name", [
    (CHRIS, "Chris Briginshaw"),
    (MATTHEW, "Matthew Briginshaw"),
])
def test_existing_canonical_and_name_profile_routes_are_preserved(pid, name, monkeypatch):
    from src.ui import layout
    monkeypatch.setenv("CLUB_ID", history.CLUB_ID)
    for query_key, token in [("player_id", pid), ("player", name)]:
        monkeypatch.setattr(layout, "query_param_value", lambda key: token if key == query_key else "")
        assert layout.resolve_player_query_to_id({pid: name}) == pid
