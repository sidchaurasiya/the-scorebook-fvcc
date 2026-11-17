import hashlib

import pandas as pd
import pytest

from src.data import featured_record_overrides as overrides
from src.data import grdcc_career_refresh as career_refresh
from src.data import grdcc_player_privacy as player_privacy
from src.data import grdcc_career_quarantine as quarantine
from src.data import grdcc_historical_records as historical
from src.data import hall_of_fame_prepared as prepared
from src.ui import layout


CLUB = "georges-river-district"
MARK_ID = "raw_262c4bf4_94de_4980_8f75_726bb58e34e1"


def _fixture_source_files(tmp_path, monkeypatch):
    baseline_path = tmp_path / "reviewed_annual_report_baselines.csv"
    table_path = tmp_path / "current_all_grades_table.csv"
    decisions_path = tmp_path / "legacy_override_decisions.csv"
    pd.DataFrame(
        [
            {
                "canonical_player_id": "verified_batter_id",
                "player_name": "Verified Batter",
                "metric": "Runs",
                "through_season_start": 2024,
                "governed_value": 321,
                "status": "source_verified",
                "scope_type": "all_grades_cumulative",
                "source_reference": "GRDCC Annual Report 2024/25 p98 ALL GRADES",
                "source_sha256": "a" * 64,
            }
        ]
    ).to_csv(baseline_path, index=False)
    pd.DataFrame(
        [
            {
                "section": "most_runs",
                "metric": "runs",
                "player_name": "Verified Batter",
                "normalized_player_name": "verified batter",
                "displayed_value": 999,
                "annual_report_value": 321,
                "annual_report_page": 98,
                "included_in_app": "yes",
            },
            {
                "section": "most_runs",
                "metric": "runs",
                "player_name": "Subset Batter",
                "normalized_player_name": "subset batter",
                "displayed_value": 177,
                "annual_report_value": 177,
                "annual_report_page": 99,
                "included_in_app": "yes",
            },
            {
                "section": "most_runs",
                "metric": "runs",
                "player_name": "Same Name Guess",
                "normalized_player_name": "same name guess",
                "displayed_value": 321,
                "annual_report_value": 321,
                "annual_report_page": 98,
                "included_in_app": "yes",
            },
        ]
    ).to_csv(table_path, index=False)
    pd.DataFrame(
        [
            {
                "player_name": "Verified Batter",
                "normalized_player_name": "verified batter",
                "metric": "career_runs",
                "displayed_value": 321,
                "override_applies": "yes",
                "annual_report_pages": "98",
                "validation_status": "pass",
            },
            {
                "player_name": "Subset Batter",
                "normalized_player_name": "subset batter",
                "metric": "career_runs",
                "displayed_value": 177,
                "override_applies": "yes",
                "annual_report_pages": "99",
                "validation_status": "pass",
            },
            {
                "player_name": "Verified Batter",
                "normalized_player_name": "verified batter",
                "metric": "career_runs",
                "displayed_value": 321,
                "override_applies": "yes",
                "annual_report_pages": "98;99",
                "validation_status": "pass",
            },
            {
                "player_name": "Same Name Guess",
                "normalized_player_name": "same name guess",
                "metric": "career_runs",
                "displayed_value": 321,
                "override_applies": "yes",
                "annual_report_pages": "98",
                "validation_status": "pass",
            },
            {
                "player_name": "Verified Batter",
                "normalized_player_name": "verified batter",
                "metric": "career_runs",
                "displayed_value": 321,
                "override_applies": "no",
                "annual_report_pages": "98",
                "validation_status": "pass",
            },
        ]
    ).to_csv(decisions_path, index=False)

    monkeypatch.setattr(overrides, "get_feature_flag", lambda *args, **kwargs: True)
    monkeypatch.setattr(overrides, "annual_report_all_time_leaders_path", lambda: table_path)
    monkeypatch.setattr(overrides, "annual_report_override_decisions_path", lambda: decisions_path)
    monkeypatch.setattr(overrides, "report_baselines_path", lambda: baseline_path)
    return table_path, decisions_path, baseline_path


def test_validation_pass_does_not_admit_subset_or_mixed_scope_rows(tmp_path, monkeypatch):
    _fixture_source_files(tmp_path, monkeypatch)

    leaders = overrides.load_annual_report_all_time_leaders(CLUB)
    decisions = overrides.load_annual_report_override_decisions(CLUB)

    assert leaders.player_name.tolist() == ["Verified Batter"]
    assert leaders.canonical_player_id.tolist() == ["verified_batter_id"]
    assert leaders.displayed_value.tolist() == [321]
    assert leaders.scope_type.tolist() == ["all_grades_cumulative"]
    assert leaders.through_season_start.astype(int).tolist() == [2024]
    assert decisions.player_name.tolist() == ["Verified Batter"]
    assert decisions.canonical_player_id.tolist() == ["verified_batter_id"]
    assert "Subset Batter" not in decisions.player_name.tolist()
    assert "Same Name Guess" not in decisions.player_name.tolist()


def test_repository_career_table_maps_only_the_98_reviewed_exact_baselines():
    leaders = overrides.load_annual_report_all_time_leaders(CLUB)
    assert len(leaders) == 98
    assert leaders.metric.value_counts().to_dict() == {"runs": 68, "wickets": 30}
    assert len(leaders[["canonical_player_id", "metric"]].drop_duplicates()) == 98
    assert leaders.scope_type.eq("all_grades_cumulative").all()
    assert leaders.through_season_start.astype(int).eq(2024).all()


def test_legacy_career_value_applies_only_to_exact_canonical_id(tmp_path, monkeypatch):
    _fixture_source_files(tmp_path, monkeypatch)
    monkeypatch.setattr(overrides, "load_report_identity_governance", lambda club: pd.DataFrame())
    monkeypatch.setattr(overrides, "load_override_player_supplements", lambda club: pd.DataFrame())
    monkeypatch.setattr(overrides, "load_featured_record_overrides", lambda club: pd.DataFrame())
    monkeypatch.setattr(overrides, "apply_career_quarantine", lambda frame, club=None: frame)
    monkeypatch.setattr(overrides, "apply_later_season_totals", lambda frame, *args, **kwargs: frame)
    monkeypatch.setattr(
        "src.data.grdcc_historical_records.apply_historical_records",
        lambda frame, club=None, **kwargs: frame,
    )
    source = pd.DataFrame(
        [
            {"canonical_player_id": "verified_batter_id", "Player": "Canonical Label", "Runs": 48.0},
            {"canonical_player_id": "different_person_id", "Player": "Verified Batter", "Runs": 77.0},
        ]
    )

    served = overrides.apply_featured_record_overrides(source, CLUB)

    exact = served.loc[served.canonical_player_id.eq("verified_batter_id")]
    unrelated = served.loc[served.canonical_player_id.eq("different_person_id")]
    assert len(exact) == len(unrelated) == 1
    assert exact.iloc[0].Runs == 321
    assert exact.iloc[0].Player == "Verified Batter"
    assert unrelated.iloc[0].Runs == 77
    assert len(served) == 2


def test_actual_mark_profile_serves_only_the_reviewed_225_run_career_metric():
    version = layout.HALL_OF_FAME_DATA_VERSION
    loaded = layout.load_hall_of_fame_data.__wrapped__(
        0, None, version, CLUB, ("annual-report-scope-guard-test",)
    )
    served = layout.filter_public_hall_of_fame_rows(
        overrides.apply_featured_record_overrides(loaded["all_time"], CLUB), CLUB
    )
    mark = served.loc[served.canonical_player_id.eq(MARK_ID)]

    assert len(mark) == 1
    assert not served.Player.astype(str).str.casefold().eq("matthew grealy").any()
    assert mark.iloc[0].Runs == 225
    for metric in (
        "Wickets", "Matches", "Innings", "Not Outs", "HS", "Bat Avg", "Bat SR",
        "Bowl Avg", "Bowl SR", "Econ", "Catches", "Maidens", "Balls Bowled",
    ):
        assert pd.isna(mark.iloc[0].get(metric)), metric
    assert quarantine.career_under_review(mark.iloc[0])
    assert mark.iloc[0][historical.SOURCE_NOTE].find("225") >= 0
    assert "other career statistics remain under review" in layout.player_profile_insight(mark.iloc[0], [])
    eligible = quarantine.eligible_career_rows(served, CLUB)
    assert MARK_ID in eligible.canonical_player_id.tolist()
    batting_table = layout.format_all_time_batting_table(served)
    mark_batting = batting_table.loc[batting_table.Player.astype(str).str.contains(MARK_ID, regex=False)]
    assert len(mark_batting) == 1 and mark_batting.iloc[0].Runs == 225
    watch = layout.build_approaching_milestone_watchlist(served, CLUB)
    assert MARK_ID not in watch.canonical_player_id.astype(str).tolist()
    assert layout.player_milestone_rows(mark.iloc[0]) == [
        {
            "category": "Runs", "current": 225, "target": 1000, "remaining": 775,
            "unit": "runs", "progress": 22.5,
        }
    ]

    same_name = served.loc[served.Player.astype(str).str.casefold().eq("mark burgess")]
    assert len(same_name) == 1
    assert same_name.iloc[0].canonical_player_id == MARK_ID


def test_legitimate_report_only_entries_keep_separate_report_record_ids():
    version = layout.HALL_OF_FAME_DATA_VERSION
    loaded = layout.load_hall_of_fame_data.__wrapped__(
        0, None, version, CLUB, ("report-only-source-policy-test",)
    )
    served = layout.filter_public_hall_of_fame_rows(
        overrides.apply_featured_record_overrides(loaded["all_time"], CLUB), CLUB
    )
    report_only = served.loc[served.canonical_player_id.isna()]
    expected = {
        "report_grdcc_annual_2024_25_warwick_geitz": ("Warwick Geitz", "Runs", 5119),
        "report_grdcc_annual_2024_25_ben_worger": ("Ben Worger", "Runs", 2312),
        "report_grdcc_annual_2024_25_phil_eldridge": ("Phil Eldridge", "Wickets", 227),
    }

    assert len(report_only) == 3
    assert set(report_only.report_record_id) == set(expected)
    assert set(historical.report_profile_index(CLUB).id) == set(expected)
    for record_id, (name, metric, value) in expected.items():
        row = report_only.loc[report_only.report_record_id.eq(record_id)].iloc[0]
        assert row.Player == name and row[metric] == value
        assert pd.isna(row.canonical_player_id)
        assert pd.isna(row.Matches) and pd.isna(row.Innings)
        assert "ALL GRADES through 2024/25" in row["Historical Source Scope"]


def test_served_prepared_and_forced_fallback_career_outputs_match(monkeypatch):
    monkeypatch.setenv("CLUB_ID", CLUB)
    version = layout.HALL_OF_FAME_DATA_VERSION
    prepared_core = prepared.load_prepared_hall_of_fame_core(CLUB, version)
    assert prepared_core is not None
    prepared_view = layout.filter_public_hall_of_fame_rows(
        overrides.apply_featured_record_overrides(prepared_core["all_time"].copy(), CLUB), CLUB
    )

    monkeypatch.setenv("SCOREBOOK_IGNORE_PREPARED_HOF", "1")
    raw_fallback = layout.load_hall_of_fame_data.__wrapped__(
        0, 0, version, club_id=CLUB
    )
    assert raw_fallback is not None
    fallback_view = layout.filter_public_hall_of_fame_rows(
        overrides.apply_featured_record_overrides(raw_fallback["all_time"].copy(), CLUB), CLUB
    )
    columns = [
        "canonical_player_id",
        "report_record_id",
        "Player",
        "Runs",
        "Wickets",
        "Matches",
        "Innings",
        quarantine.REVIEW_FLAG,
        "Historical Source Scope",
    ]
    for frame in (prepared_view, fallback_view):
        for column in columns:
            if column not in frame:
                frame[column] = pd.NA
        for column in columns[:3] + ["Historical Source Scope"]:
            frame[column] = frame[column].astype("string").fillna("")
        frame[quarantine.REVIEW_FLAG] = [
            False if pd.isna(value) else bool(value)
            for value in frame[quarantine.REVIEW_FLAG]
        ]
    prepared_view = prepared_view[columns].sort_values(columns[:3]).reset_index(drop=True)
    fallback_view = fallback_view[columns].sort_values(columns[:3]).reset_index(drop=True)
    pd.testing.assert_frame_equal(prepared_view, fallback_view, check_dtype=False)
    assert len(prepared_view) == 2138
    assert prepared_view.canonical_player_id.astype(str).ne("").sum() == 2135
    assert prepared_view.report_record_id.astype(str).ne("").sum() == 3
    privacy_snapshot = player_privacy.load_current_privacy_snapshot(CLUB)
    for policy in privacy_snapshot.itertuples(index=False):
        privacy_checks = []
        for frame in (prepared_view, fallback_view):
            identity_hashes = frame.canonical_player_id.astype(str).map(
                lambda value: hashlib.sha256(value.encode("utf-8")).hexdigest()
            )
            matching = frame.loc[identity_hashes.eq(policy.canonical_player_id_sha256)]
            if policy.status == "private":
                assert matching.empty
            else:
                assert len(matching) == 1
                assert matching.iloc[0].Player == policy.public_name
            privacy_checks.append(len(matching))
        assert privacy_checks[0] == privacy_checks[1]

    baselines = pd.read_csv(career_refresh.report_baselines_path())
    baselines = baselines.loc[
        baselines.status.eq("source_verified")
        & baselines.scope_type.eq("all_grades_cumulative")
        & pd.to_numeric(baselines.through_season_start, errors="coerce").eq(2024)
    ]
    assert len(baselines) == 98

    for metric, category, source_column in (
        ("Runs", "batting", "battingAggregate"),
        ("Wickets", "bowling", "bowlingWickets"),
    ):
        source = career_refresh.public_career_source(category)
        years = pd.to_numeric(
            source.season.astype(str).str.extract(r"(\d{4})")[0], errors="coerce"
        )
        later = source.loc[years.gt(2024)]
        additions = pd.to_numeric(later[source_column], errors="coerce").groupby(
            later.canonical_player_id
        ).sum(min_count=1)
        for baseline in baselines.loc[baselines.metric.eq(metric)].itertuples():
            expected = float(baseline.governed_value) + float(
                additions.get(baseline.canonical_player_id, 0) or 0
            )
            for served in (prepared_view, fallback_view):
                row = served.loc[
                    served.canonical_player_id.eq(baseline.canonical_player_id)
                ]
                assert len(row) == 1, (
                    f"{baseline.canonical_player_id} must occur once in the public {metric} view"
                )
                actual = pd.to_numeric(pd.Series([row.iloc[0][metric]]), errors="coerce").iloc[0]
                assert pd.notna(actual) and float(actual) == expected, (
                    f"{baseline.canonical_player_id} {metric}: expected official report baseline "
                    f"plus eligible later contributions ({expected}), got {actual}"
                )


def test_reviewed_source_guard_preserves_exclusive_club_membership_counts():
    from match_centre_source_snapshot import weekly_source_manifest

    version = layout.HALL_OF_FAME_DATA_VERSION
    loaded = layout.load_hall_of_fame_data.__wrapped__(
        0, None, version, CLUB, ("exclusive-club-source-policy-test",)
    )
    served = layout.filter_public_hall_of_fame_rows(
        overrides.apply_featured_record_overrides(loaded["all_time"], CLUB), CLUB
    )
    eligible = quarantine.eligible_career_rows(served, CLUB)
    # The current exact-ID report baseline is published once under its
    # governed identity. The October snapshot counted one duplicated same-name
    # report value in both Runs and Wickets; the source receipts now preserve
    # separate non-overlapping identities without counting that value twice.
    expected = weekly_source_manifest()["exclusive_membership_counts"]
    actual = {}
    for category in expected:
        spec = layout.exclusive_club_specs(category, CLUB)[0]
        metric = str(spec["metric"])
        thresholds = [int(value) for value in spec["thresholds"]]
        rows = eligible.copy()
        rows[metric] = pd.to_numeric(rows[metric], errors="coerce").fillna(0)
        rows = rows.loc[rows[metric].ge(min(thresholds))].copy()
        rows["milestone_band"] = rows[metric].map(
            lambda value: layout.highest_reached_threshold(value, thresholds)
        )
        actual[category] = int(rows.milestone_band.notna().sum())
    assert actual == expected


def test_annual_report_baselines_are_not_duplicated_across_same_name_source_ids():
    from pathlib import Path

    core = pd.read_csv(
        Path("clubs/georges-river-district/data/processed/hall_of_fame/prepared_career_all_time.csv")
    )
    graham_report = core.loc[core.canonical_player_id.eq("grdcc_excel_exact_graham_butt")].iloc[0]
    graham_separate = core.loc[
        core.canonical_player_id.eq("raw_49526263_9cbe_41c4_b8cf_a57e590ac665")
    ].iloc[0]
    john_report = core.loc[
        core.canonical_player_id.eq("raw_1b65e67d_d088_4e53_96ee_896a08605873")
    ].iloc[0]
    john_separate = core.loc[
        core.canonical_player_id.eq("grdcc_excel_exact_john_young")
    ].iloc[0]

    assert graham_report.Player == "Graham Butt" and graham_report.Runs == 2409
    assert pd.isna(graham_separate.Runs)
    assert john_report.Player == "John Young" and john_report.Wickets == 332
    assert pd.isna(john_separate.Wickets)


def test_mark_profile_sources_reconcile_without_adding_the_48_or_177_subtotals():
    digital = pd.read_csv("clubs/georges-river-district/data/processed/all_seasons_batting.csv")
    digital = digital.loc[digital.canonical_player_id.eq(MARK_ID)]
    excel = pd.read_csv(
        "clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_batting.csv"
    )
    excel = excel.loc[excel.player_name.astype(str).str.casefold().eq("mark burgess")]
    report = pd.read_csv(
        "clubs/georges-river-district/data/processed/validation/annual_report_2024_25/all_time_overrides/grdcc_all_time_override_decisions.csv"
    )
    subset = report.loc[
        report.player_name.eq("Mark Burgess") & report.annual_report_pages.astype(str).eq("99")
    ]
    exception = career_refresh.load_reviewed_playcricket_career_exceptions(CLUB)
    exception = exception.loc[exception.canonical_player_id.eq(MARK_ID)]

    assert digital.season.nunique() == 3
    assert digital.battingAggregate.sum() == 48
    digital_years = pd.to_numeric(digital.season.astype(str).str.extract(r"(\d{4})")[0], errors="coerce")
    assert digital_years.notna().all() and digital_years.le(2024).all()
    assert excel.season.nunique() == 3
    assert excel.battingAggregate.sum() == 225
    assert len(subset) == 1 and subset.iloc[0].displayed_value == 177
    assert len(exception) == 1
    assert exception.iloc[0].source_participant_id == "262c4bf4-94de-4980-8f75-726bb58e34e1"
    assert exception.iloc[0].governed_value == 225
    assert exception.iloc[0].processed_runs_same_scope == "48"
    assert exception.iloc[0].processed_runs_included_in_profile == "yes"
    assert exception.iloc[0].annual_report_subset_value == "177"
    assert exception.iloc[0].eligible_post_cutoff_rows == "0"
    assert not overrides.load_annual_report_all_time_leaders(CLUB).player_name.eq("Mark Burgess").any()


def test_mark_exception_adds_only_later_eligible_rows_once_and_is_club_scoped():
    later_source = pd.DataFrame(
        [
            {"canonical_player_id": MARK_ID, "season": "Summer 1993/94", "battingAggregate": 44},
            {"canonical_player_id": MARK_ID, "season": "Summer 1994/95", "battingAggregate": 0},
            {"canonical_player_id": MARK_ID, "season": "Summer 1995/96", "battingAggregate": 4},
            {"canonical_player_id": MARK_ID, "season": "Summer 2025/26", "battingAggregate": 12},
        ]
    )
    frame = pd.DataFrame(
        [
            {"canonical_player_id": MARK_ID, "Player": "Mark Burgess", "Runs": 48, "Wickets": 19},
            {"canonical_player_id": "different_exact_id", "Player": "Mark Burgess", "Runs": 999, "Wickets": 8},
        ]
    )

    governed = career_refresh.apply_reviewed_playcricket_career_exceptions(
        frame, CLUB, later_source=later_source
    )
    repeated = career_refresh.apply_reviewed_playcricket_career_exceptions(
        governed, CLUB, later_source=later_source
    )
    pd.testing.assert_frame_equal(governed, repeated)
    assert governed.loc[0, "Runs"] == 237
    assert pd.isna(governed.loc[0, "Wickets"])
    assert governed.loc[1, "Runs"] == 999
    for other_club in ("fvcc", "glen-waverley-hawks"):
        pd.testing.assert_frame_equal(
            career_refresh.apply_reviewed_playcricket_career_exceptions(frame, other_club), frame
        )


def test_mark_profile_career_totals_use_the_same_exact_id_exception(monkeypatch):
    governed = pd.DataFrame(
        [
            {
                "canonical_player_id": MARK_ID,
                "Player": "Mark Burgess",
                "Runs": 225,
                "Wickets": pd.NA,
                "Matches": pd.NA,
                "Innings": pd.NA,
                "Bat Avg": pd.NA,
                "Bowl Avg": pd.NA,
                quarantine.REVIEW_FLAG: True,
                "Reviewed Career Metric": "Runs",
                historical.SOURCE_NOTE: "225 verified runs for the GRDCC scope",
            }
        ]
    )
    monkeypatch.setattr(layout, "get_authoritative_career_totals", lambda *args, **kwargs: governed.copy())
    career = pd.DataFrame(
        [
            {
                "canonical_player_id": MARK_ID,
                "Player": "Mark Burgess",
                "Runs": 48,
                "Wickets": 19,
                "Matches": 3,
                "Innings": 3,
                "Bat Avg": 16.07,
                "Bowl Avg": 12.0,
            }
        ]
    )

    result = layout.apply_authoritative_profile_career_totals(
        career, {"player_info": {"canonical_player_id": MARK_ID}}, CLUB
    )

    assert result.iloc[0].Runs == 225
    assert result.iloc[0].Wickets is pd.NA or pd.isna(result.iloc[0].Wickets)
    assert pd.isna(result.iloc[0].Matches)
    assert pd.isna(result.iloc[0]["Bat Avg"])
    assert result.iloc[0]["Reviewed Career Metric"] == "Runs"
    assert result.iloc[0]["Reviewed Career Source URL"] == (
        "https://play.cricket.com.au/player/262c4bf4-94de-4980-8f75-726bb58e34e1/mark-burgess?tab=career"
    )
    assert "225 runs are verified" in layout.player_profile_insight(result.iloc[0], [])


def test_existing_review_only_profiles_tolerate_empty_reviewed_metric(monkeypatch):
    messages = []
    monkeypatch.setattr(layout.st, "info", messages.append)
    monkeypatch.setattr(layout.st, "caption", messages.append)
    career = pd.Series(
        {
            quarantine.REVIEW_FLAG: True,
            "Reviewed Career Metric": pd.NA,
            historical.SOURCE_NOTE: pd.NA,
            "Runs": pd.NA,
        }
    )

    assert layout.reviewed_career_metric_name(career) == ""
    assert quarantine.REVIEW_NOTE in layout.player_profile_insight(career, [])
    layout.render_reviewed_historical_sources({"career": pd.DataFrame([career])})
    assert quarantine.REVIEW_NOTE in messages[0]
    assert any("No career subtotal" in message for message in messages)


def test_mark_profile_presents_the_verified_official_source_link(monkeypatch):
    links = []
    monkeypatch.setattr(layout.st, "markdown", links.append)
    monkeypatch.setattr(layout.st, "caption", lambda value: None)
    career = pd.Series(
        {
            "Reviewed Career Metric": "Runs",
            "Reviewed Career Source URL": (
                "https://play.cricket.com.au/player/262c4bf4-94de-4980-8f75-726bb58e34e1/mark-burgess?tab=career"
            ),
            "Runs": 225,
            historical.SOURCE_NOTE: "225 verified career runs for Georges River Cricket Club",
        }
    )

    layout.render_reviewed_historical_sources({"career": pd.DataFrame([career])}, review_notice=False)

    assert links == [
        "[Official PlayCricket career profile (GRDCC filter)](https://play.cricket.com.au/player/262c4bf4-94de-4980-8f75-726bb58e34e1/mark-burgess?tab=career)"
    ]


def test_grdcc_governance_code_is_part_of_public_override_cache_signature():
    signature = layout.hall_of_fame_override_signature(CLUB)
    code_component = next(value for value in signature if value[0] == "grdcc_career_governance_code")
    code_paths = {entry[0].rsplit("/", 1)[-1] for entry in code_component[1]}

    assert code_paths == {"layout.py", "featured_record_overrides.py", "grdcc_career_refresh.py"}


@pytest.mark.parametrize(
    "formatter",
    [
        layout.format_all_time_batting_table,
        layout.format_all_time_bowling_table,
        layout.format_all_time_fielding_table,
    ],
)
def test_rank_table_cache_invalidates_when_career_review_policy_changes(formatter, monkeypatch):
    formatter.clear()
    state = {"include": True, "signature": "before-review"}
    monkeypatch.setattr(layout, "get_active_club_id", lambda: CLUB)
    monkeypatch.setattr(layout, "hall_of_fame_override_signature", lambda club_id=None: (state["signature"],))
    monkeypatch.setattr(
        layout,
        "eligible_career_rows",
        lambda frame, club_id=None: frame if state["include"] else frame.iloc[0:0].copy(),
    )
    monkeypatch.setattr(layout, "ranked_historical_rows", lambda frame, metric, club_id=None: frame)
    frame = pd.DataFrame(
        [
            {
                "canonical_player_id": "cache_fixture_id",
                "report_record_id": "",
                "Historical Source Scope": "",
                "Player": "Cache Fixture",
                "Seasons Played": 1,
                "Debut Season": "Summer 2024/25",
                "Latest Season": "Summer 2024/25",
                "Matches": 1,
                "Win %": 0,
                "Not Outs": 0,
                "Runs": 50,
                "Bat Avg": 50,
                "Bat SR": 100,
                "HS": "50",
                "30s": 1,
                "50s": 1,
                "100s": 0,
                "0s": 0,
                "4s": 5,
                "6s": 0,
                "Innings": 1,
                "Matches Source": "verified",
                "Matches Proxy": "",
                "Wickets": 2,
                "Balls Bowled": 24,
                "Maidens": 0,
                "Bowl Avg": 10,
                "Bowl SR": 12,
                "Econ": 5,
                "BBI": "2-10",
                "3WI": 0,
                "5WI": 0,
                "10WM": 0,
                "Catches": 1,
                "Stumpings": 0,
                "Run Outs": 0,
                "Dismissals": 1,
            }
        ]
    )

    assert len(formatter(frame)) == 1
    state["include"] = False
    state["signature"] = "under-review"
    assert len(formatter(frame)) == 0
    formatter.clear()
