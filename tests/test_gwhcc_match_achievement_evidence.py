import pandas as pd
import pytest

from src.data import gwhcc_historical_career as history
from src.data import gwhcc_match_achievements as achievements


def fixture(anchor=49.5, current=51, periods=(("Summer 2026/27", .5), ("Summer 2027/28", 1))):
    player = {"canonical_player_id": "target", "Player": "Target Player", "Matches": current,
              "historical_match_anchor_applied": True, "historical_match_anchor_value": anchor,
              "historical_match_anchor_through_season": "Summer 2025/26"}
    raw = pd.DataFrame([{"canonical_player_id": "target", "season": season, "season_id": season,
                         "team_id": "team", "grade_id": "grade", "matches": weight} for season, weight in periods])
    return pd.DataFrame([player]), {"batting_raw": raw}


def test_all_four_seasons_have_independent_crossing_bounds_not_match_dates():
    evidence = achievements.load_match_milestone_seasons()
    assert set(zip(evidence.canonical_player_id, evidence.threshold, evidence.season)) == {
        ("nathan_bungey", 300, "Summer 2021/22"),
        ("raw_3aa87830_65b3_4913_92fa_de83f2a46d2b", 50, "Summer 2025/26"),
        ("anthony_stiles", 50, "Summer 2025/26"), ("noel_blacker", 100, "Summer 2025/26")}
    career = evidence.rename(columns={"canonical_player_name": "Player", "after_lower_bound": "Matches"})
    rows, _ = achievements.qualified_match_achievement_rows({}, career, evidence.season.tolist(), [50,100,300])
    assert len(rows) == 4
    assert all(set(r) == {"Player", "canonical_player_id", "Category", "Milestone", "Threshold", "Current Total", "Season", "Unit"} for r in rows)


def test_undated_anchor_preserves_attainment_but_does_not_invent_old_season():
    career, data = fixture(anchor=104, current=105, periods=(("Summer 2024/25", 10), ("Summer 2026/27", 1)))
    rows, ids = achievements.qualified_match_achievement_rows(data, career, ["Summer 2024/25", "Summer 2026/27"], [100])
    assert rows == [] and ids == {"target"} and career.Matches.iloc[0] == 105


def test_half_match_crossing_is_dated_once_and_survives_future_increment():
    career, data = fixture()
    rows, _ = achievements.qualified_match_achievement_rows(data, career, ["Summer 2026/27", "Summer 2027/28"], [50,100])
    assert [(r["Threshold"], r["Season"]) for r in rows] == [(50, "Summer 2026/27")]
    career.loc[0, "Matches"] += 1
    data["batting_raw"] = pd.concat([data["batting_raw"], pd.DataFrame([{"canonical_player_id": "target", "season": "Summer 2028/29", "season_id": "Summer 2028/29", "team_id": "team", "grade_id": "grade", "matches": 1}])], ignore_index=True)
    again, _ = achievements.qualified_match_achievement_rows(data, career, ["Summer 2026/27", "Summer 2027/28", "Summer 2028/29"], [50,100])
    assert [(r["Threshold"], r["Season"]) for r in again] == [(50, "Summer 2026/27")]


@pytest.mark.parametrize("problem", ["duplicate", "missing", "negative", "unknown", "fraction", "missing_key", "blank_key"])
def test_ambiguous_later_evidence_cannot_date_a_crossing(problem):
    career, data = fixture()
    if problem == "duplicate":
        data["batting_raw"] = pd.concat([data["batting_raw"], data["batting_raw"].iloc[[0]]], ignore_index=True)
    elif problem == "missing":
        data["batting_raw"] = data["batting_raw"].iloc[[0]]
    elif problem == "missing_key":
        data["batting_raw"] = data["batting_raw"].drop(columns="team_id")
    elif problem == "blank_key":
        data["batting_raw"].loc[0, "team_id"] = ""
    else:
        data["batting_raw"].loc[0, "matches"] = {"negative": -1, "unknown": float("nan"), "fraction": .25}[problem]
    rows, _ = achievements.qualified_match_achievement_rows(data, career, ["Summer 2026/27"], [50])
    assert rows == []


@pytest.mark.parametrize("club", ["fvcc", "georges-river-district"])
def test_other_clubs_do_not_use_hawks_season_authority(club):
    career, data = fixture()
    assert achievements.qualified_match_achievement_rows(data, career, ["Summer 2026/27"], [50], club_id=club) == ([], set())


def test_private_identity_is_never_emitted():
    career, data = fixture()
    career.loc[0, "Player"] = "Private player"
    assert achievements.qualified_match_achievement_rows(data, career, ["Summer 2026/27"], [50])[0] == []


@pytest.mark.parametrize("status", ["review", "pending", "rejected"])
def test_review_or_rejected_source_season_never_becomes_approved(status, monkeypatch, tmp_path):
    source = achievements.load_match_milestone_seasons().iloc[[0]].copy()
    source.loc[:, "decision_status"] = status
    path = tmp_path / "seasons.csv"; source.to_csv(path, index=False)
    monkeypatch.setattr(achievements, "MATCH_MILESTONES", path)
    assert achievements.load_match_milestone_seasons().empty
    career = pd.DataFrame([{"canonical_player_id": source.canonical_player_id.iloc[0],
                            "Player": "Existing Public Player", "Matches": 339}])
    rows, controlled = achievements.qualified_match_achievement_rows({}, career, ["Summer 2021/22"], [300])
    assert rows == [] and controlled == {source.canonical_player_id.iloc[0]}


def test_invalid_or_duplicate_source_season_fails_validation(monkeypatch, tmp_path):
    source = achievements.load_match_milestone_seasons().iloc[[0]].copy()
    path = tmp_path / "seasons.csv"
    pd.concat([source, source]).to_csv(path, index=False)
    monkeypatch.setattr(achievements, "MATCH_MILESTONES", path)
    with pytest.raises(ValueError, match="one explicit identity"):
        achievements.load_match_milestone_seasons()
    source.loc[:, "before_upper_bound"] = source.threshold
    source.to_csv(path, index=False)
    with pytest.raises(ValueError, match="bounds"):
        achievements.load_match_milestone_seasons()


def test_season_evidence_participates_in_existing_cache_signature():
    assert str(history.MATCH_MILESTONES) in {row[0] for row in history.dated_career_signature()}


def test_evidence_only_change_invalidates_achieved_cache_without_clearing_it(monkeypatch, tmp_path):
    from src.ui import layout

    career, data = fixture()
    career["player_key"] = "target"
    data["all_time"] = career
    totals = pd.DataFrame([{"player_key": "target", "Matches": .5}])
    monkeypatch.setattr(layout, "build_milestone_period_totals", lambda *args: totals)
    monkeypatch.setattr(layout, "build_milestone_period_totals_by_season", lambda *args: pd.DataFrame())
    state = {"threshold": 50}
    def payload(*args, **kwargs):
        return [{"Player": "Target Player", "canonical_player_id": "target", "Category": "Matches",
                 "Milestone": "Synthetic cache witness", "Threshold": state["threshold"],
                 "Current Total": 51, "Season": "Summer 2026/27", "Unit": "matches"}], {"target"}
    monkeypatch.setattr(achievements, "qualified_match_achievement_rows", payload)
    version = (str(tmp_path), 1)
    first = layout.build_achieved_milestones(data, ["Summer 2026/27"], history.CLUB_ID, match_evidence_version=version)
    state["threshold"] = 100
    cached = layout.build_achieved_milestones(data, ["Summer 2026/27"], history.CLUB_ID, match_evidence_version=version)
    changed = layout.build_achieved_milestones(data, ["Summer 2026/27"], history.CLUB_ID, match_evidence_version=(str(tmp_path), 2))
    assert first.Threshold.tolist() == cached.Threshold.tolist() == [50]
    assert changed.Threshold.tolist() == [100]
