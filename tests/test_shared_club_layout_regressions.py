from __future__ import annotations

import pandas as pd

from src.config import club_config
from src.data import grdcc_player_privacy
from src.ui import layout


GRDCC = "georges-river-district"
HAWKS = "glen-waverley-hawks"
FVCC = "fvcc"


def test_profile_index_keeps_club_scoped_report_records_and_hawks_exact_id_alias(monkeypatch, tmp_path):
    source = pd.DataFrame([{"canonical_player_id": "source-player-1", "canonical_player_name": "Martin, Lincoln"}])
    aliases = pd.DataFrame([{
        "canonical_player_id": "source-player-1",
        "canonical_player_name": "Lincoln Martin",
        "merge_source": layout.GWHCC_PROFILE_DISPLAY_NAME_SOURCE,
        "is_active": "true",
    }])
    filter_clubs = []
    report_clubs = []

    def filter_rows(frame, club_id=None):
        filter_clubs.append(club_id)
        return frame.copy()

    def report_rows(club_id=None):
        report_clubs.append(club_id)
        if club_id == GRDCC:
            return pd.DataFrame([{"id": "report_grdcc_test_player", "name": "Report Test Player"}])
        return pd.DataFrame(columns=["id", "name"])

    monkeypatch.setattr(layout, "load_player_aliases", lambda club_id=None: aliases.copy())
    monkeypatch.setattr(layout, "read_processed_table", lambda filename: source.copy())
    monkeypatch.setattr(layout, "apply_player_identity_mapping", lambda frame, alias_rows, club_id=None: frame.copy())
    monkeypatch.setattr(layout, "filter_public_player_rows", filter_rows)
    monkeypatch.setattr(layout, "canonical_player_name_casing_overrides", lambda frame: {})
    monkeypatch.setattr(layout, "report_profile_index", report_rows)
    monkeypatch.setattr(club_config, "get_hall_of_fame_dir", lambda club_id=None: tmp_path)

    indexes = {
        club: layout._load_player_profile_index_cached.__wrapped__(club, 0.0, 0.0, "integration-test")
        for club in (GRDCC, HAWKS, FVCC)
    }

    assert indexes[GRDCC].loc[indexes[GRDCC].id.eq("report_grdcc_test_player"), "name"].tolist() == ["Report Test Player"]
    assert "report_grdcc_test_player" not in set(indexes[HAWKS].id)
    assert "report_grdcc_test_player" not in set(indexes[FVCC].id)
    assert indexes[HAWKS].loc[indexes[HAWKS].id.eq("source-player-1"), "name"].tolist() == ["Lincoln Martin"]
    assert indexes[FVCC].loc[indexes[FVCC].id.eq("source-player-1"), "name"].tolist() == ["Martin, Lincoln"]
    assert set(filter_clubs) == {GRDCC, HAWKS, FVCC}
    assert report_clubs == [GRDCC]


def test_current_privacy_masking_is_resolved_with_each_active_club(monkeypatch):
    seen_clubs = []

    def current_status(frame, club_id=None):
        seen_clubs.append(club_id)
        status = "private" if club_id == GRDCC else "public"
        return (
            pd.Series([status] * len(frame), index=frame.index),
            pd.Series([""] * len(frame), index=frame.index),
        )

    def prepared(frame, source_columns, display_columns):
        return pd.DataFrame({
            "NO": frame["battingNotOuts"].copy(),
            "Bat SR": frame["seasonDetailBatSR"].copy(),
        })

    monkeypatch.setattr(grdcc_player_privacy, "current_privacy_overrides", current_status)
    monkeypatch.setattr(layout, "prepare_curated_display_frame", prepared)

    outputs = {}
    for club in (GRDCC, HAWKS, FVCC):
        monkeypatch.setattr(layout, "get_active_club_id", lambda club=club: club)
        source = pd.DataFrame([{
            "canonical_player_id": "same-source-token",
            "canonical_player_name": "Known Display Name",
            "player_name": "Known Display Name",
            "battingNotOuts": 1,
            "seasonDetailBatSR": 152.5,
        }])
        outputs[club] = layout.get_batting_display_df(source).iloc[0]

    assert pd.isna(outputs[GRDCC]["Not Outs"])
    assert outputs[HAWKS]["Not Outs"] == 1
    assert outputs[FVCC]["Not Outs"] == 1
    assert outputs[GRDCC]["Bat SR"] == 152.5
    assert outputs[FVCC]["Bat SR"] == 152.5
    assert outputs[HAWKS]["Bat SR (ball-by-ball)"] == 152.5
    assert set(seen_clubs) == {GRDCC, HAWKS, FVCC}


class _Column:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False


def test_player_breakdown_keeps_grdcc_missingness_and_hawks_delivery_provenance(monkeypatch):
    captions = []
    rendered = []

    monkeypatch.setattr(layout, "render_section_heading", lambda label: None)
    monkeypatch.setattr(layout, "render_hawks_match_count_footnote", lambda: None)
    monkeypatch.setattr(layout, "render_gwhcc_career_coverage_note", lambda career: None)
    monkeypatch.setattr(layout, "render_grdcc_not_outs_career_note", lambda career: None)
    monkeypatch.setattr(layout, "player_profile_is_keeper", lambda career: False)
    monkeypatch.setattr(layout, "historical_matches_display_text", lambda career: ("2", 2.0, False))
    monkeypatch.setattr(layout.st, "columns", lambda count: [_Column() for _ in range(count)])
    monkeypatch.setattr(layout.st, "markdown", lambda markup, **kwargs: rendered.append(markup))
    monkeypatch.setattr(layout.st, "caption", lambda text: captions.append(text))

    career = pd.Series({
        "Player": "Historical Test Player",
        "Matches": 2.0,
        "Runs": 20.0,
        "Innings": 1.0,
        "Not Outs": pd.NA,
        "Bat Avg": 20.0,
        "Bat SR": 150.0,
        "Wickets": pd.NA,
        "Bowl Avg": pd.NA,
        "Bowl SR": pd.NA,
        "Econ": pd.NA,
        "BBI": "",
        "Catches": pd.NA,
        "Stumpings": pd.NA,
        "Run Outs": pd.NA,
        "Dismissals": pd.NA,
        "Historical Record Kind": "primary_historical",
    })

    monkeypatch.setattr(layout, "get_active_club_id", lambda: GRDCC)
    grdcc_metrics = layout.player_profile_batting_career_metrics(career, "2")
    layout.render_player_breakdown(career)
    assert any(label == "Strike Rate" and value == "150.0" for label, value in grdcc_metrics)
    assert "Recorded wickets" in " ".join(rendered)
    assert "Recorded wickets</span><strong>—" in " ".join(rendered)
    assert not captions

    rendered.clear()
    monkeypatch.setattr(layout, "get_active_club_id", lambda: HAWKS)
    from src.data import gwhcc_historical_career
    monkeypatch.setattr(gwhcc_historical_career, "has_dated_career_scope", lambda career, metric_scope: False)
    hawks_metrics = layout.player_profile_batting_career_metrics(career, "2")
    layout.render_player_breakdown(career)
    assert any(label == "Strike Rate (ball-by-ball)" and value == "150.0" for label, value in hawks_metrics)
    assert layout.GWHCC_BBB_RATE_NOTE in captions
    hawks_markup = " ".join(rendered)
    assert "Recorded wickets" not in hawks_markup
    assert "Wickets</span>" in hawks_markup

    captions.clear()
    rendered.clear()
    monkeypatch.setattr(layout, "get_active_club_id", lambda: FVCC)
    fvcc_metrics = layout.player_profile_batting_career_metrics(career, "2")
    layout.render_player_breakdown(career)
    assert any(label == "Strike Rate" and value == "150.0" for label, value in fvcc_metrics)
    assert not captions
    fvcc_markup = " ".join(rendered)
    assert "Recorded wickets" not in fvcc_markup
    assert "Wickets</span>" in fvcc_markup


def test_peer_batting_strike_rate_uses_run_per_100_ball_units_for_each_club(monkeypatch):
    batting_rows = pd.DataFrame([
        {
            "canonical_player_id": "player-1",
            "runs": 1.0,
            "outs": 1.0,
            "bat_avg": 1.0,
            "bat_sr": 20.0,
            "bbb_runs": 1.0,
            "bbb_balls": 5.0,
            "bbb_dismissals": 1.0,
            "balls_per_dismissal": 5.0,
            "boundaries": 0.0,
            "innings": 1.0,
            "boundary_rate": 0.0,
            "ducks": 0.0,
        },
        {
            "canonical_player_id": "player-2",
            "runs": 559.0,
            "outs": 10.0,
            "bat_avg": 55.9,
            "bat_sr": 55.9,
            "bbb_runs": 559.0,
            "bbb_balls": 1000.0,
            "bbb_dismissals": 10.0,
            "balls_per_dismissal": 100.0,
            "boundaries": 10.0,
            "innings": 10.0,
            "boundary_rate": 1.0,
            "ducks": 0.0,
        },
    ])
    monkeypatch.setattr(layout, "load_player_peer_sources", lambda *args: (pd.DataFrame(), pd.DataFrame()))
    monkeypatch.setattr(layout, "filter_peer_scope", lambda frame, *args: frame.copy())
    monkeypatch.setattr(layout, "aggregate_peer_batting", lambda *args: batting_rows.copy())
    monkeypatch.setattr(layout, "add_bbb_peer_batting_rates", lambda frame, *args: frame.copy())
    monkeypatch.setattr(layout, "aggregate_peer_bowling", lambda *args: pd.DataFrame())
    monkeypatch.setattr(layout, "export_player_vs_peers_debug", lambda *args: None)

    for club in (GRDCC, HAWKS, FVCC):
        monkeypatch.setattr(layout, "get_active_club_id", lambda club=club: club)
        comparison = layout.get_player_peer_comparison.__wrapped__(
            "player-1", ("Summer 2026/27",), (), 0.0, 0.0, club
        )
        expected_label = "Strike Rate (ball-by-ball)" if club == HAWKS else "Strike Rate"
        strike_rate = next(row for row in comparison["batting"] if row["label"] == expected_label)

        assert strike_rate["value"] == 20.0
        assert strike_rate["format"] == "rate"
        assert layout.format_peer_metric_value(strike_rate["value"], strike_rate["format"]) == "20.0"
        assert layout.peer_metric_note(strike_rate["label"]) == "Verified ball-by-ball only"
        assert layout.format_bat_sr_display(20.0) == "20.0"
        assert layout.hof_detail_display_value("Bat SR", 20.0) == "20.0"
        assert layout.profile_performance_display_value("Strike Rate", 20.0, "Season") == "20.0"


def test_player_trend_chart_keys_change_with_profile_data_for_each_club(monkeypatch):
    chart_keys = []
    chart_specs = []
    monkeypatch.setattr(layout, "render_section_heading", lambda label: None)
    monkeypatch.setattr(layout.st, "columns", lambda count: [_Column() for _ in range(count)])
    monkeypatch.setattr(layout.st, "container", lambda **kwargs: _Column())
    monkeypatch.setattr(layout.st, "markdown", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        layout.st,
        "altair_chart",
        lambda chart, **kwargs: (chart_keys.append(kwargs["key"]), chart_specs.append(chart.to_dict())),
    )

    for club in (GRDCC, HAWKS, FVCC):
        monkeypatch.setattr(layout, "get_active_club_id", lambda club=club: club)
        first = pd.DataFrame({"Season": ["Summer 2024/25"], "Runs": [10], "Wickets": [1]})
        second = pd.DataFrame({"Season": ["Summer 2024/25"], "Runs": [20], "Wickets": [2]})
        layout.render_player_trends(first)
        layout.render_player_trends(second)
        averages_first = pd.DataFrame({"Season": ["Summer 2024/25"], "Season Average": [10.0]})
        averages_second = pd.DataFrame({"Season": ["Summer 2024/25"], "Season Average": [20.0]})
        layout.render_filled_average_chart(averages_first, ["Summer 2024/25"], "Average", "#123456", "profile_average")
        layout.render_filled_average_chart(averages_second, ["Summer 2024/25"], "Average", "#123456", "profile_average")

    assert len(chart_keys) == 18
    for offset in (0, 6, 12):
        assert chart_keys[offset] != chart_keys[offset + 2]
        assert chart_keys[offset + 1] != chart_keys[offset + 3]
        assert chart_keys[offset + 4] != chart_keys[offset + 5]
    assert all("datasets" not in spec for spec in chart_specs)
