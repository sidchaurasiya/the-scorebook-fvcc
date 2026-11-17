from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

import src.data.fvcc_scorecard_privacy as privacy
from scripts import build_fvcc_incremental_refresh as incremental
from scripts import build_club_app_facing_scorecards as cards
from scripts.correct_fvcc_match_fielding import replace_match_rows
from src.data import playcricket_ingestion as ingestion
from src.utils.player_identity import is_private_or_anonymised_player


ROOT = Path(__file__).resolve().parents[1]
FVCC_PROCESSED = ROOT / "clubs" / "fvcc" / "data" / "processed"


def _masked_row(
    player_id: str,
    *,
    name: str = "********",
    runs: int = 0,
    match_id: str = "fixture-match",
) -> dict[str, object]:
    return {
        "season": "Summer 2026/27",
        "match_id": match_id,
        "player_id": player_id,
        "player_name": name,
        "runs": runs,
        "balls": 0,
        "fours": 0,
        "sixes": 0,
        "strike_rate": 0.0,
        "dismissal": "did not bat",
    }


def test_fvcc_sanitization_preserves_duplicate_anonymous_rows_and_scope():
    source = pd.DataFrame([_masked_row("opaque-one"), _masked_row("opaque-two")])
    output = privacy.sanitize_fvcc_scorecard_rows(source, club_id="fvcc", discipline="batting")

    assert len(output) == len(source) == 2
    assert output.player_id.eq("").all()
    assert output.player_name.eq("********").all()
    assert output.public_scorecard_row_key.is_unique
    assert privacy.masked_scorecard_projection(source) == privacy.masked_scorecard_projection(output)
    assert privacy.sanitize_fvcc_scorecard_rows(output, club_id="fvcc", discipline="batting").equals(output)
    assert privacy.sanitize_fvcc_scorecard_rows(source, club_id="glen-waverley-hawks", discipline="batting").equals(source)


def test_malformed_placeholder_id_is_scrubbed_even_if_source_label_changes():
    token = "00000000-0000-0000-0000-000000000099"
    source = pd.DataFrame([_masked_row(token, name="Unverified source label")])

    output = privacy.sanitize_fvcc_scorecard_rows(source, club_id="fvcc", discipline="batting")

    assert output.loc[0, "player_id"] == ""
    assert output.loc[0, "player_name"] == "Private player"
    assert output.loc[0, "public_scorecard_row_key"].startswith("fvcc-anon-")
    # The same source fingerprint has no effect in another club context.
    assert privacy.sanitize_fvcc_scorecard_rows(source, club_id="georges-river-district", discipline="batting").equals(source)


def test_fielding_correction_projection_fails_closed_on_anonymous_stat_changes():
    before = pd.DataFrame([_masked_row("old-opaque", match_id="match-one")])
    after = pd.DataFrame([_masked_row("new-opaque", match_id="match-one")])
    privacy.assert_masked_scorecard_rows_unchanged(before, after)

    changed = after.copy()
    changed.loc[0, "runs"] = 1
    try:
        privacy.assert_masked_scorecard_rows_unchanged(before, changed)
    except ValueError as error:
        assert "Anonymous FVCC scorecard" in str(error)
    else:
        raise AssertionError("Correction path must reject changed anonymous statistics")


def test_fielding_correction_replacement_retains_anonymous_row_key():
    before = pd.DataFrame([_masked_row("opaque-source-id", match_id="match-one")])
    replacement = privacy.sanitize_fvcc_scorecard_rows(before, club_id="fvcc", discipline="batting")
    columns = list(before.columns)
    columns.extend(column for column in replacement.columns if column not in columns)
    replacement = replacement.reindex(columns=columns).fillna("")

    output = replace_match_rows(before, replacement, "match-one")

    assert len(output) == 1
    assert output.loc[0, "player_id"] == ""
    assert output.loc[0, "public_scorecard_row_key"].startswith("fvcc-anon-")
    assert output.loc[0, "runs"] == 0


def test_incremental_scorecard_append_keeps_anonymous_rows_and_sanitizes_old_data():
    old = pd.DataFrame([_masked_row("old-opaque", match_id="baseline-match")])
    current = pd.DataFrame([_masked_row("new-opaque", runs=0, match_id="new-match")])

    output = incremental.append_public_scorecard_rows(
        old, current, "all_seasons_scorecard_batting.csv", club_id="fvcc"
    )

    assert len(output) == 2
    assert output.player_id.eq("").all()
    assert output.public_scorecard_row_key.notna().all()
    assert output.public_scorecard_row_key.is_unique
    assert output.runs.astype(int).sum() == 0


def test_cached_or_legacy_fallback_table_is_sanitized_after_read(monkeypatch, tmp_path):
    legacy_file = tmp_path / "all_seasons_scorecard_batting.csv"
    legacy_file.write_text("fixture")
    source = pd.DataFrame([_masked_row("legacy-opaque")])
    monkeypatch.setattr(ingestion, "get_processed_path", lambda *args, **kwargs: legacy_file)
    monkeypatch.setattr(ingestion, "get_active_club_id", lambda: "fvcc")
    monkeypatch.setattr(ingestion, "_read_processed_table_cached", lambda *args: source.copy())
    monkeypatch.setattr(ingestion, "_append_supplemental_processed_rows", lambda name, frame, **kwargs: frame)

    output = ingestion.read_processed_table("all_seasons_scorecard_batting")

    assert output.loc[0, "player_id"] == ""
    assert output.loc[0, "player_name"] == "********"
    assert output.loc[0, "public_scorecard_row_key"].startswith("anon-")


def test_app_facing_scorecard_builder_applies_only_explicit_fvcc_guard():
    matches = pd.DataFrame([{"match_id": "builder-match", "season": "Summer 2026/27"}])
    batting = pd.DataFrame(
        [{
            "team_id": "fvcc-team",
            "match_id": "builder-match",
            "participant_id": "00000000-0000-0000-0000-000000000099",
            "player_name": "Unverified source label",
            "runs_scored": 4,
            "balls_faced": 3,
            "fours_scored": 1,
            "sixes_scored": 0,
            "strike_rate": "133.33",
            "dismissal_text": "not out",
        }]
    )

    fvcc = cards.build_batting_rows(batting, matches, {"fvcc-team"}, club_id="fvcc")
    other_club = cards.build_batting_rows(
        batting, matches, {"fvcc-team"}, club_id="georges-river-district"
    )

    assert len(fvcc) == len(other_club) == 1
    assert fvcc.loc[0, "player_id"] == ""
    assert fvcc.loc[0, "player_name"] == "Private player"
    assert fvcc.loc[0, "runs"] == 4
    assert fvcc.loc[0, "public_scorecard_row_key"].startswith("fvcc-anon-")
    assert other_club.loc[0, "player_id"] == "00000000-0000-0000-0000-000000000099"


def test_accepted_fvcc_scorecard_rows_have_no_reused_tokens_and_keep_source_figures():
    snapshot = json.loads((ROOT / "tests/fixtures/fvcc_weekly_output_snapshot_2026-11-16.json").read_text())
    batting = pd.read_csv(FVCC_PROCESSED / "all_seasons_scorecard_batting.csv", dtype=str, keep_default_na=False)
    bowling = pd.read_csv(FVCC_PROCESSED / "all_seasons_scorecard_bowling.csv", dtype=str, keep_default_na=False)
    fielding = pd.read_csv(FVCC_PROCESSED / "all_seasons_scorecard_fielding.csv", dtype=str, keep_default_na=False)

    anonymous_batting = batting[batting.public_scorecard_row_key.astype(str).str.startswith("fvcc-anon-")]
    anonymous_bowling = bowling[bowling.public_scorecard_row_key.astype(str).str.startswith("fvcc-anon-")]
    assert len(batting) == snapshot["current_scorecard_rows"]["batting"]
    assert len(bowling) == snapshot["current_scorecard_rows"]["bowling"]
    assert len(fielding) == snapshot["current_scorecard_rows"]["fielding"]
    assert len(anonymous_batting) == snapshot["anonymous_scorecard_rows"]["batting"]
    assert len(anonymous_bowling) == snapshot["anonymous_scorecard_rows"]["bowling"]
    assert anonymous_batting.player_id.eq("").all()
    assert anonymous_bowling.player_id.eq("").all()
    assert anonymous_batting.player_name.eq("********").all()
    assert anonymous_bowling.player_name.eq("********").all()
    assert anonymous_batting.public_scorecard_row_key.is_unique
    assert anonymous_bowling.public_scorecard_row_key.is_unique
    assert anonymous_batting.dismissal.value_counts().to_dict() == snapshot["anonymous_scorecard_figures"]["batting_dismissals"]
    for metric, expected in snapshot["anonymous_scorecard_figures"]["batting_numeric_totals"].items():
        assert pd.to_numeric(anonymous_batting[metric]).sum() == expected
    for metric, expected in snapshot["anonymous_scorecard_figures"]["bowling_numeric_totals"].items():
        assert pd.to_numeric(anonymous_bowling[metric]).sum() == expected
    anonymous_fielding = fielding[
        fielding.player_id.eq("") | fielding.player_name.map(is_private_or_anonymised_player)
    ]
    assert len(anonymous_fielding) == snapshot["anonymous_scorecard_rows"]["fielding"]
    assert anonymous_fielding.player_id.eq("").all()
    assert anonymous_fielding.public_scorecard_row_key.astype(str).str.strip().ne("").all()
    for metric, expected in snapshot["anonymous_scorecard_figures"]["fielding_numeric_totals"].items():
        assert pd.to_numeric(anonymous_fielding[metric]).sum() == expected
    for frame in [batting, bowling, fielding]:
        assert not frame.player_id.map(privacy.is_fvcc_placeholder_participant_id).any()


def test_anonymous_scorecard_rows_have_no_public_profile_link():
    links = pd.read_csv(
        FVCC_PROCESSED / "hall_of_fame" / "scorecard_record_links.csv",
        dtype=str,
        keep_default_na=False,
    )
    identity_or_name_columns = [
        column for column in links.columns
        if column in {"player_name", "display_player_name", "canonical_player_name"}
    ]
    anonymous = pd.read_csv(
        FVCC_PROCESSED / "all_seasons_scorecard_batting.csv",
        dtype=str,
        keep_default_na=False,
    )
    match_ids = set(
        anonymous.loc[
            anonymous.public_scorecard_row_key.astype(str).str.startswith("fvcc-anon-"),
            "match_id",
        ].astype(str)
    )
    if "match_id" in links:
        links = links[links.match_id.astype(str).isin(match_ids)]
    for column in identity_or_name_columns:
        assert not links[column].map(is_private_or_anonymised_player).any()
    for column in links.columns:
        assert not links[column].map(privacy.is_fvcc_placeholder_participant_id).any()


def test_generic_fvcc_record_links_drop_ids_and_keep_every_numeric_value():
    source = pd.DataFrame(
        [
            {
                "mode": "batting",
                "canonical_player_id": "ambiguous-canonical-id",
                "canonical_player_name": "********",
                "season": "Summer 2026/27",
                "match_id": "anonymous-match",
                "runs_scored": 0,
                "balls_faced": 0,
                "wickets_taken": 0,
                "runs_conceded": 0,
            },
            {
                "mode": "batting",
                "canonical_player_id": "verified-public-id",
                "canonical_player_name": "Public Player",
                "season": "Summer 2026/27",
                "match_id": "public-match",
                "runs_scored": 44,
                "balls_faced": 30,
                "wickets_taken": 0,
                "runs_conceded": 0,
            },
        ]
    )

    output = privacy.sanitize_fvcc_scorecard_record_links(source, club_id="fvcc")

    assert len(output) == len(source) == 2
    assert output.loc[0, "canonical_player_id"] == ""
    assert output.loc[0, "canonical_player_name"] == "********"
    assert "public_scorecard_row_key" not in output
    assert output.loc[1, "canonical_player_id"] == "verified-public-id"
    assert output.loc[1, "canonical_player_name"] == "Public Player"
    assert output.loc[0, ["runs_scored", "balls_faced", "wickets_taken", "runs_conceded"]].tolist() == [0, 0, 0, 0]
    assert output.loc[1, ["runs_scored", "balls_faced", "wickets_taken", "runs_conceded"]].tolist() == [44, 30, 0, 0]
    assert privacy.sanitize_fvcc_scorecard_record_links(output, club_id="fvcc").equals(output)
    assert privacy.sanitize_fvcc_scorecard_record_links(source, club_id="glen-waverley-hawks").equals(source)


def test_incremental_record_link_builder_scrubs_old_and_new_generic_rows():
    old = pd.DataFrame(
        [{"mode": "batting", "canonical_player_id": "old-ambiguous-id", "canonical_player_name": "Private player", "match_id": "old-match", "runs_scored": 7}]
    )
    current = pd.DataFrame(
        [{"mode": "batting", "canonical_player_id": "new-ambiguous-id", "canonical_player_name": "********", "match_id": "new-match", "runs_scored": 19}]
    )

    output = incremental.append_public_scorecard_record_links(old, current, club_id="fvcc")

    assert len(output) == 2
    assert output.canonical_player_id.eq("").all()
    assert output.runs_scored.astype(int).tolist() == [7, 19]


def test_cached_and_match_centre_fallback_scorecard_links_are_sanitized(monkeypatch, tmp_path):
    from src.ui import layout

    scope = tmp_path / "all_available"
    scope.mkdir()
    monkeypatch.setattr(layout, "get_active_club_id", lambda: "fvcc")
    monkeypatch.setattr(layout, "MATCH_CENTRE_PROCESSED_ROOT", tmp_path)
    monkeypatch.setattr(layout, "HALL_OF_FAME_SCORECARD_RECORD_LINKS_PATH", tmp_path / "no-deploy-links.csv")
    monkeypatch.setattr(layout, "add_missing_canonical_player_ids", lambda frame, club_id: frame)

    def read_csv(path, **kwargs):
        filename = Path(path).name
        if filename == "all_matches.csv":
            return pd.DataFrame([{"match_id": "fallback-match", "season": "Summer 2026/27"}])
        if filename == "all_scorecard_batting.csv":
            return pd.DataFrame([{"match_id": "fallback-match", "player_id": "fallback-id", "player_name": "********", "runs_scored": 5}])
        if filename == "all_scorecard_bowling.csv":
            return pd.DataFrame(columns=["match_id", "player_id", "player_name", "wickets_taken"])
        return pd.DataFrame()

    monkeypatch.setattr(layout, "read_match_centre_csv", read_csv)
    layout.load_scorecard_record_rows.clear()
    output = layout.load_scorecard_record_rows(("fresh-test-signature",))
    layout.load_scorecard_record_rows.clear()

    batting = output["batting"]
    assert len(batting) == 1
    assert batting.loc[0, "player_id"] == ""
    assert batting.loc[0, "player_name"] == "********"
    assert batting.loc[0, "public_scorecard_row_key"].startswith("anon-")
    assert batting.loc[0, "runs_scored"] == 5


def test_deploy_link_loader_sanitizes_club_artifact_after_read(monkeypatch):
    from src.ui import layout

    source = pd.DataFrame(
        [{"mode": "batting", "canonical_player_id": "ambiguous-id", "canonical_player_name": "********", "match_id": "deploy-match", "runs_scored": 13}]
    )
    monkeypatch.setattr(layout, "read_match_centre_csv", lambda path, **kwargs: source.copy())

    batting = layout.load_deploy_scorecard_record_rows("fvcc")["batting"]

    assert len(batting) == 1
    assert batting.loc[0, "canonical_player_id"] == ""
    assert batting.loc[0, "canonical_player_name"] == "********"
    assert batting.loc[0, "runs_scored"] == 13


def test_published_fvcc_record_links_have_no_ids_for_generic_rows():
    links = pd.read_csv(
        FVCC_PROCESSED / "hall_of_fame" / "scorecard_record_links.csv",
        dtype=str,
        keep_default_na=False,
    )
    generic = links.canonical_player_name.map(is_private_or_anonymised_player)
    assert int(generic.sum()) == 35
    assert links.loc[generic, "canonical_player_id"].eq("").all()
    assert links.loc[generic, "canonical_player_id"].eq("").all()
