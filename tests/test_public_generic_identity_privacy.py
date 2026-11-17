from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.data import public_generic_identity_privacy as privacy


def test_generic_hawks_scorecard_keeps_figures_and_gets_match_scoped_keys():
    source = pd.DataFrame(
        [
            {"match_id": "match-a", "season": "Summer 2026/27", "player_id": "source-a", "player_name": "Private player", "runs": 18, "balls": 14},
            {"match_id": "match-a", "season": "Summer 2026/27", "player_id": "source-b", "player_name": "********", "runs": 21, "balls": 15},
        ]
    )

    output, receipt = privacy.sanitize_public_identity_frame(
        source, club_id="glen-waverley-hawks", relative_path="all_seasons_scorecard_batting.csv"
    )
    again, _ = privacy.sanitize_public_identity_frame(
        source.assign(player_id=["different-a", "different-b"]),
        club_id="glen-waverley-hawks",
        relative_path="all_seasons_scorecard_batting.csv",
    )

    assert len(output) == len(source) == 2
    assert output.player_id.eq("").all()
    assert output.player_name.tolist() == source.player_name.tolist()
    assert output.runs.tolist() == [18, 21]
    assert output.balls.tolist() == [14, 15]
    assert output.public_scorecard_row_key.astype(str).str.startswith("anon-").all()
    assert output.public_scorecard_row_key.is_unique
    assert output.public_scorecard_row_key.tolist() == again.public_scorecard_row_key.tolist()
    assert receipt["identifier_cells_cleared"] == 2
    assert receipt["anonymous_event_keys_added"] == 2


def test_generic_identifier_cleanup_is_club_scoped_and_preserves_named_players():
    source = pd.DataFrame(
        [
            {"player_id": "masked-id", "player_name": "Private player", "runs": 7},
            {"player_id": "public-id", "player_name": "Public Player", "runs": 12},
        ]
    )

    hawks, _ = privacy.sanitize_public_identity_frame(source, club_id="glen-waverley-hawks")
    other, _ = privacy.sanitize_public_identity_frame(source, club_id="unrelated-club")

    assert hawks.loc[0, "player_id"] == ""
    assert hawks.loc[0, "runs"] == 7
    assert hawks.loc[1, "player_id"] == "public-id"
    assert hawks.loc[1, "player_name"] == "Public Player"
    pd.testing.assert_frame_equal(other, source)


def test_legacy_club_generic_identity_is_unlinked_without_losing_statistics():
    source = pd.DataFrame(
        [{
            "canonical_player_id": "reused-canonical-token",
            "player_id": "reused-source-token",
            "player_name": "Private player",
            "runs": 28,
            "matches": 1,
        }]
    )

    output, _ = privacy.sanitize_public_identity_frame(source, club_id="ashwood")

    assert output.loc[0, ["canonical_player_id", "player_id"]].eq("").all()
    assert output.loc[0, "player_name"] == "Private player"
    assert output.loc[0, ["runs", "matches"]].tolist() == [28, 1]


def test_grdcc_exact_current_public_identity_restores_verified_name(monkeypatch):
    from src.data import grdcc_player_privacy

    monkeypatch.setattr(
        grdcc_player_privacy,
        "resolve_current_privacy",
        lambda **kwargs: ("public", "Verified Public Name"),
    )
    source = pd.DataFrame(
        [{"player_id": "source-id", "canonical_player_id": "canonical-id", "player_key": "canonical-id", "raw_player_id": "source-id", "raw_player_name": "********", "player_name": "********", "canonical_player_name": "Private player", "runs": 32}]
    )

    output, receipt = privacy.sanitize_public_identity_frame(source, club_id="georges-river-district")

    assert output.loc[0, "player_name"] == "Verified Public Name"
    assert output.loc[0, "canonical_player_name"] == "Verified Public Name"
    assert output.loc[0, "raw_player_name"] == "Verified Public Name"
    assert output.loc[0, "canonical_player_id"] == "canonical-id"
    assert output.loc[0, "player_key"] == "canonical-id"
    assert output.loc[0, "raw_player_id"] == ""
    assert output.loc[0, "player_id"] == ""
    assert output.loc[0, "runs"] == 32
    assert receipt["current_public_names_restored"] == 3


def test_grdcc_exact_current_private_identity_is_masked_even_if_stored_name_is_visible(monkeypatch):
    from src.data import grdcc_player_privacy

    monkeypatch.setattr(
        grdcc_player_privacy,
        "current_privacy_overrides",
        lambda frame, club_id=None: (
            pd.Series("private", index=frame.index, dtype="string"),
            pd.Series("", index=frame.index, dtype="string"),
        ),
    )
    source = pd.DataFrame(
        [{"canonical_player_id": "private-canonical", "player_id": "private-source", "player_name": "Previously visible label", "runs": 18}]
    )

    output, receipt = privacy.sanitize_public_identity_frame(source, club_id="georges-river-district")

    assert output.loc[0, "canonical_player_id"] == ""
    assert output.loc[0, "player_id"] == ""
    assert output.loc[0, "player_name"] == "Private player"
    assert output.loc[0, "runs"] == 18
    assert receipt["private_names_masked"] == 1


def test_partnership_cleanup_masks_only_generic_partner_identity():
    source = pd.DataFrame(
        [{
            "match_id": "match-p",
            "player_1_canonical_id": "masked-partner-id",
            "player_1_name": "Private player",
            "player_2_canonical_id": "public-partner-id",
            "player_2_name": "Public Partner",
            "runs": 24,
            "balls": 19,
        }]
    )

    output, _ = privacy.sanitize_public_identity_frame(source, club_id="fvcc")

    assert output.loc[0, "player_1_canonical_id"] == ""
    assert output.loc[0, "player_1_name"] == "Private player"
    assert output.loc[0, "player_2_canonical_id"] == "public-partner-id"
    assert output.loc[0, "player_2_name"] == "Public Partner"
    assert output.loc[0, ["runs", "balls"]].tolist() == [24, 19]


def test_processed_tree_sanitizer_is_idempotent_and_checks_numeric_projection(tmp_path):
    processed = tmp_path / "clubs/glen-waverley-hawks/data/processed"
    metadata_path = processed.parent / "metadata.json"
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text('{"previous": "v1"}\n', encoding="utf-8")
    scorecards = processed / "all_seasons_scorecard_batting.csv"
    scorecards.parent.mkdir(parents=True)
    scorecards.write_text(
        "match_id,season,player_id,player_name,runs,balls\nmatch-x,Summer 2026/27,ambiguous-id,Private player,40,28\n",
        encoding="utf-8",
    )
    before_rows = pd.read_csv(scorecards, dtype=str, keep_default_na=False)

    first = privacy.sanitize_public_processed_tree(processed, club_id="glen-waverley-hawks")
    after_first = pd.read_csv(scorecards, dtype=str, keep_default_na=False)
    second = privacy.sanitize_public_processed_tree(processed, club_id="glen-waverley-hawks")
    after_second = pd.read_csv(scorecards, dtype=str, keep_default_na=False)

    assert len(before_rows) == len(after_first) == len(after_second) == 1
    assert after_first.loc[0, "player_id"] == ""
    assert after_first.loc[0, "runs"] == "40"
    assert after_first.loc[0, "balls"] == "28"
    assert after_first.public_scorecard_row_key.iloc[0].startswith("anon-")
    metadata = json.loads(metadata_path.read_text())
    assert metadata["public_generic_identity_revision"] == privacy.PUBLIC_IDENTITY_POLICY_VERSION
    assert "public_identity_revision" not in metadata
    assert after_first.equals(after_second)
    assert len(first["files"]) == 1
    assert second["files"] == {}


def test_generic_sanitizer_preserves_club_identity_revision(tmp_path):
    processed = tmp_path / "clubs/glen-waverley-hawks/data/processed"
    metadata_path = processed.parent / "metadata.json"
    metadata_path.parent.mkdir(parents=True)
    metadata_path.write_text(
        '{"public_identity_revision":"hawks-masked-placeholder-event-scope-v2"}\n',
        encoding="utf-8",
    )
    processed.mkdir(parents=True)

    privacy.sanitize_public_processed_tree(processed, club_id="glen-waverley-hawks")

    metadata = json.loads(metadata_path.read_text())
    assert metadata["public_identity_revision"] == "hawks-masked-placeholder-event-scope-v2"
    assert metadata["public_generic_identity_revision"] == privacy.PUBLIC_IDENTITY_POLICY_VERSION


def test_processed_tree_allows_only_generic_dismissal_actor_redaction(tmp_path):
    processed = tmp_path / "clubs/glen-waverley-hawks/data/processed"
    processed.mkdir(parents=True)
    scorecards = processed / "all_seasons_scorecard_batting.csv"
    scorecards.write_text(
        "match_id,innings_id,team_id,player_id,player_name,dismissal,runs,balls\n"
        "match-x,innings-x,team-x,ambiguous-id,Private player,\"c: Named Fielder b: Named Bowler\",0,1\n",
        encoding="utf-8",
    )

    receipt = privacy.sanitize_public_processed_tree(processed, club_id="glen-waverley-hawks")
    output = pd.read_csv(scorecards, dtype=str, keep_default_na=False)

    assert len(output) == 1
    assert output.loc[0, "player_id"] == ""
    assert output.loc[0, "player_name"] == "Private player"
    assert output.loc[0, "dismissal"] == "Caught"
    assert output.loc[0, ["runs", "balls"]].tolist() == ["0", "1"]
    assert output.loc[0, "public_scorecard_row_key"].startswith("anon-")
    assert receipt["files"]["all_seasons_scorecard_batting.csv"]["identifier_cells_cleared"] == 1


def test_generic_retired_not_out_keeps_the_official_dismissal_classification():
    source = pd.DataFrame(
        [{
            "match_id": "match-retired-not-out",
            "player_id": "reused-private-token",
            "player_name": "Private player",
            "dismissal": "Retired Not Out",
            "runs": 6,
            "balls": 17,
        }]
    )

    output, _ = privacy.sanitize_public_identity_frame(
        source,
        club_id="glen-waverley-hawks",
        relative_path="all_seasons_scorecard_batting.csv",
    )

    assert output.loc[0, "player_id"] == ""
    assert output.loc[0, "player_name"] == "Private player"
    assert output.loc[0, "dismissal"] == "Retired Not Out"
    assert output.loc[0, ["runs", "balls"]].tolist() == [6, 17]


def test_generic_profile_aliases_clear_all_player_keys_without_changing_career_values():
    source = pd.DataFrame(
        [{
            "canonical_player_id": "masked-canonical",
            "player_key": "masked-key",
            "player_id": "masked-source",
            "canonical_player_name": "Private player",
            "display_player_name": "Private player",
            "matches": 8,
            "runs": 215,
            "wickets": 4,
        }]
    )

    output, _ = privacy.sanitize_public_identity_frame(source, club_id="glen-waverley-hawks")

    assert output.loc[0, ["canonical_player_id", "player_key", "player_id"]].eq("").all()
    assert output.loc[0, ["matches", "runs", "wickets"]].tolist() == [8, 215, 4]
    assert output.loc[0, "canonical_player_name"] == "Private player"
    assert output.loc[0, "display_player_name"] == "Private player"


def test_prepared_hall_of_fame_builder_sanitizes_generic_identity_fields():
    from scripts.build_hall_of_fame_core_exports import sanitize_core_export_frames

    source = pd.DataFrame(
        [
            {
                "canonical_player_id": "reused-placeholder",
                "player_key": "reused-placeholder",
                "player_id": "reused-placeholder",
                "Player": "Private player",
                "canonical_player_name": "Private player",
                "Runs": 41,
                "Matches": 2,
            }
        ]
    )

    output = sanitize_core_export_frames("glen-waverley-hawks", {"all_time": source})["all_time"]

    assert output.loc[0, ["canonical_player_id", "player_key", "player_id"]].eq("").all()
    assert output.loc[0, "Player"] == "Private player"
    assert output.loc[0, "Runs"] == 41
    assert output.loc[0, "Matches"] == 2


def test_generic_source_label_cannot_retain_a_named_alias_or_profile_id():
    source = pd.DataFrame(
        [{
            "canonical_player_id": "old-canonical-id",
            "player_key": "old-canonical-id",
            "player_id": "reused-masked-token",
            "raw_player_id": "reused-masked-token",
            "canonical_player_name": "Previously assigned name",
            "display_player_name": "Previously assigned name",
            "raw_player_name": "Private player",
            "player_name": "Private player",
            "runs": 26,
        }]
    )

    output, _ = privacy.sanitize_public_identity_frame(source, club_id="glen-waverley-hawks")

    assert output.loc[0, ["canonical_player_id", "player_key", "player_id", "raw_player_id"]].eq("").all()
    assert output.loc[0, ["canonical_player_name", "display_player_name", "raw_player_name", "player_name"]].eq("Private player").all()
    assert output.loc[0, "runs"] == 26


def test_generic_review_export_scrubs_prefixed_ids_and_name_lists_without_losing_stats(tmp_path):
    source = pd.DataFrame(
        [{
            "player_name": "Private player",
            "source_player_name": "Private player",
            "source_raw_player_name": "********",
            "source_canonical_player_name": "Private player",
            "source_raw_player_id": "unresolved-source-key",
            "source_canonical_player_id": "unresolved-canonical-key",
            "canonical_ids": "person-a|person-b",
            "all_involved_player_names": "Unverified Name A; Unverified Name B",
            "source_rows_involved": "17;18",
            "runs": 28,
            "matches": 1,
        }]
    )

    output, receipt = privacy.sanitize_public_identity_frame(
        source, club_id="glen-waverley-hawks", relative_path="validation/review_exports/audit.csv"
    )

    assert output.loc[0, [
        "source_raw_player_id", "source_canonical_player_id", "canonical_ids"
    ]].eq("").all()
    assert output.loc[0, "all_involved_player_names"] == "Private player"
    assert output.loc[0, "source_rows_involved"] == "17;18"
    assert output.loc[0, ["runs", "matches"]].tolist() == [28, 1]
    assert receipt["identifier_cells_cleared"] >= 3
    assert receipt["private_names_masked"] >= 1

    processed = tmp_path / "clubs/glen-waverley-hawks/data/processed"
    processed.mkdir(parents=True)
    source_path = processed / "validation/review_exports/audit.csv"
    source_path.parent.mkdir(parents=True)
    source.to_csv(source_path, index=False)
    privacy.sanitize_public_processed_tree(processed, club_id="glen-waverley-hawks")
    served = pd.read_csv(source_path, dtype=str, keep_default_na=False)

    assert served.loc[0, [
        "source_raw_player_id", "source_canonical_player_id", "canonical_ids"
    ]].eq("").all()
    assert served.loc[0, "all_involved_player_names"] == "Private player"
    assert served.loc[0, ["runs", "matches"]].tolist() == ["28", "1"]


def test_generic_scorecard_row_masks_actor_names_inside_dismissal_text():
    source = pd.DataFrame(
        [{
            "match_id": "match-private",
            "player_id": "reused-placeholder",
            "player_name": "Private player",
            "dismissal": "c: Visible Fielder b: Visible Bowler",
            "runs": 0,
            "balls": 1,
        }]
    )

    output, _ = privacy.sanitize_public_identity_frame(
        source, club_id="fvcc", relative_path="all_seasons_scorecard_batting.csv"
    )

    assert output.loc[0, "dismissal"] == "Caught"
    assert output.loc[0, "runs"] == 0
    assert output.loc[0, "public_scorecard_row_key"].startswith("anon-")


def test_reused_generic_source_id_does_not_use_a_named_alias():
    from src.utils.player_identity import apply_player_identity_mapping

    aliases = pd.DataFrame(
        [{
            "canonical_player_id": "approved-person-id",
            "canonical_player_name": "Approved Person",
            "raw_player_id": "reused-token",
            "raw_player_name": "Old source label",
            "alias_name": "",
            "notes": "existing alias",
            "is_active": "true",
            "merge_source": "existing_approved_identity",
        }]
    )
    source = pd.DataFrame([{"player_id": "reused-token", "player_name": "Private player", "runs": 17}])

    output = apply_player_identity_mapping(source, aliases_df=aliases, club_id="glen-waverley-hawks")

    assert output.loc[0, "canonical_player_name"] == "Private player"
    assert output.loc[0, "canonical_player_id"] != "approved-person-id"
    assert output.loc[0, "runs"] == 17


def test_grdcc_exact_current_public_status_can_restore_an_approved_alias(monkeypatch):
    from src.data import grdcc_player_privacy
    from src.utils.player_identity import apply_player_identity_mapping

    monkeypatch.setattr(
        grdcc_player_privacy,
        "current_privacy_overrides",
        lambda frame, club_id=None: (
            pd.Series("public", index=frame.index, dtype="string"),
            pd.Series("Verified Current Name", index=frame.index, dtype="string"),
        ),
    )
    aliases = pd.DataFrame(
        [{
            "canonical_player_id": "known-canonical-id",
            "canonical_player_name": "Previous Name",
            "raw_player_id": "exact-source-id",
            "raw_player_name": "Private player",
            "alias_name": "",
            "notes": "existing approved identity",
            "is_active": "true",
            "merge_source": "existing_approved_identity",
        }]
    )
    source = pd.DataFrame([{"player_id": "exact-source-id", "player_name": "Private player", "runs": 17}])

    output = apply_player_identity_mapping(source, aliases_df=aliases, club_id="georges-river-district")

    assert output.loc[0, "canonical_player_id"] == "known-canonical-id"
    assert output.loc[0, "canonical_player_name"] == "Verified Current Name"
    assert output.loc[0, "runs"] == 17


def test_grdcc_exact_name_merge_never_groups_generic_source_labels(monkeypatch):
    from src.utils import player_identity

    monkeypatch.setattr(player_identity, "get_feature_flag", lambda *args, **kwargs: True)
    monkeypatch.setattr(player_identity, "grdcc_exact_name_nonoverlap_canonical_map", lambda *args, **kwargs: {})
    source = pd.DataFrame(
        [
            {"raw_player_id": "masked-a", "raw_player_name": "Private player", "canonical_player_id": "raw_masked_a", "canonical_player_name": "Private player", "season": "Season A"},
            {"raw_player_id": "masked-b", "raw_player_name": "Private player", "canonical_player_id": "raw_masked_b", "canonical_player_name": "Private player", "season": "Season B"},
        ]
    )

    output = player_identity.apply_grdcc_historical_exact_name_mapping(source, club_id="georges-river-district")

    assert output.canonical_player_id.tolist() == ["raw_masked_a", "raw_masked_b"]
    assert output.canonical_player_name.tolist() == ["Private player", "Private player"]


def test_generic_event_without_person_id_still_gets_stable_match_key():
    source = pd.DataFrame(
        [{"match_id": "match-a", "innings_id": "innings-a", "player_name": "********", "runs": 31}]
    )

    output, receipt = privacy.sanitize_public_identity_frame(
        source, club_id="fvcc", relative_path="all_seasons_scorecard_batting.csv"
    )

    assert output.loc[0, "public_scorecard_row_key"].startswith("anon-")
    assert receipt["anonymous_event_keys_added"] == 1
    assert output.loc[0, "runs"] == 31


def test_explicit_private_flag_masks_visible_label_without_a_person_id():
    source = pd.DataFrame([{"player_name": "Previously visible label", "is_private": True, "runs": 9}])

    output, _ = privacy.sanitize_public_identity_frame(source, club_id="fvcc")

    assert output.loc[0, "player_name"] == "Private player"
    assert output.loc[0, "runs"] == 9


def test_ambiguous_reused_grdcc_source_key_fails_closed(monkeypatch):
    from src.data import grdcc_player_privacy

    source_key = "a" * 64
    rows = pd.DataFrame(
        [
            {"canonical_player_id_sha256": "b" * 64, "source_participant_id_sha256": source_key, "status": "public", "public_name": "Public One"},
            {"canonical_player_id_sha256": "c" * 64, "source_participant_id_sha256": source_key, "status": "public", "public_name": "Public Two"},
        ]
    )
    grdcc_player_privacy._status_index_for_signature.cache_clear()
    monkeypatch.setattr(grdcc_player_privacy, "_load_snapshot", lambda _signature: rows)

    index = grdcc_player_privacy._status_index_for_signature(("synthetic-ambiguous-source",))

    assert index[source_key] == {"status": "private", "public_name": ""}
    assert index["b" * 64] == {"status": "public", "public_name": "Public One"}
    assert index["c" * 64] == {"status": "public", "public_name": "Public Two"}
    grdcc_player_privacy._status_index_for_signature.cache_clear()


def test_root_fallback_sanitization_does_not_change_shared_root_metadata(tmp_path):
    root = tmp_path / "data/processed"
    root.mkdir(parents=True)
    metadata = tmp_path / "data/metadata.json"
    metadata.write_text('{"version": "shared"}\n', encoding="utf-8")
    source = root / "all_seasons_scorecard_batting.csv"
    source.write_text(
        "match_id,player_id,player_name,runs\nmatch-r,masked-id,Private player,9\n",
        encoding="utf-8",
    )

    privacy.sanitize_public_processed_tree(root, club_id="fvcc", update_metadata=False)

    assert metadata.read_text(encoding="utf-8") == '{"version": "shared"}\n'
    after = pd.read_csv(source, dtype=str, keep_default_na=False)
    assert after.loc[0, "player_id"] == ""
    assert after.loc[0, "runs"] == "9"
