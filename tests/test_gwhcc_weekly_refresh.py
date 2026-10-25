import pandas as pd
import pytest
import json
from pathlib import Path

from scripts.build_gwhcc_weekly_candidate import approved_redirects, canonicalise_summary, summary_specs
from scripts.build_gwhcc_incremental_candidate import preserve_existing_profile_names
from src.data.gwhcc_incremental import eligible_match_ids, profile_fielding_input


def decisions():
    return pd.DataFrame({"club": ["glen-waverley-hawks"] * 2,
                         "decision": ["customer_approved_exact_disjoint_seasons"] * 2,
                         "previous_canonical_id": ["retired", "survivor"],
                         "canonical_player_id": ["survivor", "survivor"],
                         "canonical_player_name": ["Survivor", "Survivor"]})


def test_weekly_seed_reuses_only_existing_approved_redirects():
    assert approved_redirects(decisions()) == {"retired": "survivor", "survivor": "survivor"}


@pytest.mark.parametrize("column,value", [("club", "fvcc"), ("decision", "review")])
def test_weekly_seed_rejects_cross_club_or_unapproved_identity(column, value):
    frame = decisions()
    frame.loc[0, column] = value
    with pytest.raises(ValueError):
        approved_redirects(frame)


def test_weekly_seed_rejects_conflicting_redirects():
    frame = decisions()
    frame.loc[1, "previous_canonical_id"] = "retired"
    frame.loc[1, "canonical_player_id"] = "someone_else"
    with pytest.raises(ValueError, match="Conflicting"):
        approved_redirects(frame)


def test_existing_profile_label_wins_without_changing_source_identity_or_name():
    frame = pd.DataFrame({
        "canonical_player_id": ["known", "new"],
        "canonical_player_name": ["Briginshaw, Chris", "New, Player"],
        "raw_player_id": ["source-known", "source-new"],
        "raw_player_name": ["Briginshaw, Chris", "New, Player"],
    })
    output = preserve_existing_profile_names(frame, {"known": "Chris Briginshaw"})
    assert output.canonical_player_id.tolist() == ["known", "new"]
    assert output.canonical_player_name.tolist() == ["Chris Briginshaw", "New, Player"]
    assert output.raw_player_name.tolist() == frame.raw_player_name.tolist()
    assert frame.canonical_player_name.tolist() == ["Briginshaw, Chris", "New, Player"]


def test_historical_sufficient_statistics_conserve_approved_identity_contributions():
    frame = pd.DataFrame({"canonical_player_id": ["retired", "survivor", "unaffected"],
                          "player_key": ["retired", "survivor", "unaffected"],
                          "bbb_runs": ["20", "40", "17"], "bbb_balls_faced": ["10", "20", "13"],
                          "bbb_dismissals": ["1", "2", "1"], "bbb_batting_innings": ["1", "2", "1"],
                          "bbb_matches": ["1", "2", "1"], "bat_sr": ["200", "200", "130.77"]})
    output = canonicalise_summary(frame, decisions(), summary_specs()["hall_of_fame/player_bbb_batting_rates.csv"], "player_bbb_batting_rates.csv")
    survivor = output[output.canonical_player_id.eq("survivor")].iloc[0]
    assert survivor.bbb_runs == 60
    assert survivor.bbb_balls_faced == 30
    assert survivor.bat_sr == 200
    pd.testing.assert_series_equal(output[output.canonical_player_id.eq("unaffected")].iloc[0], frame.iloc[2], check_names=False)
    assert pd.to_numeric(output.bbb_runs).sum() == pd.to_numeric(frame.bbb_runs).sum()


def test_exact_discovery_cutoff_does_not_include_later_same_day_fixture():
    matches = pd.DataFrame({"match_id": ["before", "boundary", "after"], "status": ["COMPLETED"] * 3,
                            "first_match_day": ["2026-10-17T11:41:41Z", "2026-10-17T11:41:42Z", "2026-10-17T11:41:43Z"]})
    innings = pd.DataFrame({"match_id": matches.match_id, "runs_scored": [1] * 3, "wickets_fallen": [0] * 3, "overs_bowled": [1] * 3})
    assert eligible_match_ids(matches, innings, "2026-10-17T22:41:42+11:00") == {"before", "boundary"}
    assert eligible_match_ids(matches, innings, "2026-10-17") == {"before", "boundary", "after"}


def test_profile_adapter_does_not_double_count_assisted_run_outs():
    source = pd.DataFrame({"run_outs": [1, 2, 1], "assisted_run_outs": [1, 1, 0]})
    adapted = profile_fielding_input(source)
    assert (adapted.run_outs + adapted.assisted_run_outs).tolist() == [1, 2, 1]
    assert source.run_outs.tolist() == [1, 2, 1]


@pytest.mark.parametrize("total,assisted", [(None, 1), (1, None), (0, 1), (1, -1)])
def test_profile_adapter_rejects_unproven_run_out_totals(total, assisted):
    with pytest.raises(ValueError, match="source totals"):
        profile_fielding_input(pd.DataFrame({"run_outs": [total], "assisted_run_outs": [assisted]}))


DATA = Path(__file__).resolve().parents[1] / "clubs/glen-waverley-hawks/data/processed"


def test_weekly_snapshot_is_disjoint_preserves_history_and_excludes_pending_results():
    validation = json.loads((DATA / "validation/gwhcc_weekly_refresh_validation.json").read_text())
    matches = pd.read_csv(DATA / "all_seasons_matches.csv")
    assert len(matches) == matches.match_id.nunique() == 3512
    assert matches.season.ne("Summer 2026/27").sum() == 3475
    assert set(validation["new_completed_match_ids"]) <= set(matches.match_id)
    assert not set(validation["pending_match_ids"]) & set(matches.match_id)
    assert validation["canonical_merges_created"] == 0
    assert validation["new_canonical_identities"] == []


def test_current_profile_fielding_matches_official_total_without_duplicate_assists():
    source = pd.read_csv(DATA / "all_seasons_fielding.csv")
    source = source[source.season.eq("Summer 2026/27")].groupby("canonical_player_id").fieldingRunOuts.sum()
    detail = pd.read_csv(DATA / "player_profile/performance_breakdown_by_dimension.csv", low_memory=False)
    detail = detail[detail.dimension.eq("Season") & detail.breakdown_label.eq("Summer 2026/27") & detail.discipline.eq("Fielding")]
    actual = detail.groupby("canonical_player_id").run_outs.sum().reindex(source.index, fill_value=0)
    assert source.eq(actual).all()


def test_weekly_headlines_preserve_four_merged_profiles_and_source_approved_history():
    career = pd.read_csv(DATA / "hall_of_fame/prepared_career_all_time.csv")
    expected = {"Aaditya Sharma": (39, 214, 21, 7), "Darsh Singh": (37, 229, 9, 0),
                "Liam O'Rourke": (140, 1618, 46, 116), "Mitchell Kohne": (151, 2404, 159, 49)}
    for name, values in expected.items():
        player = career[career.Player.eq(name)]
        assert len(player) == 1
        assert tuple(player.iloc[0][["Matches", "Runs", "Wickets", "Catches"]]) == values


def test_weekly_prepared_counts_and_governed_validation_have_no_failures():
    validation = json.loads((DATA / "validation/gwhcc_weekly_refresh_validation.json").read_text())
    assert validation["pass"] and validation["historical_preserved"]
    assert validation["source_metric_checks"] == 4686
    assert validation["run_out_source_checks"] == 639
    assert all(check["pass"] for check in validation["profile_checks"])
    assert validation["refreshed"]["current_season_matches"] == 37
    assert validation["refreshed"]["public_hof_players"] == 1291
    assert validation["refreshed"]["weighted_career_appearances"] == 29326
    assert validation["refreshed"]["career_runs"] == 433142
    assert validation["refreshed"]["career_wickets"] == 21105
    assert validation["refreshed"]["career_catches"] == 7807
    assert len(validation["new_completed_match_ids"]) == 17


def test_weekly_seed_rejects_relative_paths_inside_repository(monkeypatch):
    from scripts import build_gwhcc_weekly_candidate as weekly
    monkeypatch.chdir(weekly.ROOT)
    monkeypatch.setattr(weekly.subprocess, "run", lambda *args, **kwargs: None)
    with pytest.raises(ValueError, match="outside-repository"):
        weekly.historical_seed(Path("not-a-permitted-refresh-output"), "verified-ref", "Summer 2026/27")
    assert not (weekly.ROOT / "not-a-permitted-refresh-output").exists()
