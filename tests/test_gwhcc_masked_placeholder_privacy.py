from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from src.data.gwhcc_masked_privacy import (
    ID_COLUMNS,
    HAWKS_CLUB_ID,
    HAWKS_SCOPED_PLACEHOLDER_MATCH_IDS,
    MASKED_HAWKS_PARTICIPANT_ID_SHA256,
    PRIVATE_PLAYER_LABEL,
    collect_ambiguous_scorecard_link_keys,
    exclude_hawks_masked_source_rows,
    is_match_scoped_hawks_placeholder,
    mask_hawks_participant_rows,
    mask_scorecard_record_links,
    mask_hawks_unscoped_match_count_diagnostic,
    masked_hawks_participant_mask,
    sanitize_hawks_source_frames,
    sanitize_hawks_processed_tree,
)
from src.ui import layout


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "clubs" / HAWKS_CLUB_ID / "data" / "processed"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def test_reused_participant_rows_are_generic_unlinked_and_keep_scorecard_values() -> None:
    token = "reused-masked-token"
    frame = pd.DataFrame(
        {
            "player_id": [token, "verified-player-id"],
            "player_name": ["Unverified source label", "Public Player"],
            "runs": [47, 12],
            "balls": [31, 8],
        }
    )

    redacted, count = mask_hawks_participant_rows(
        frame,
        id_columns=["player_id"],
        name_columns=["player_name"],
        fingerprints={_sha(token)},
    )

    assert count == 1
    assert redacted.loc[0, "player_name"] == PRIVATE_PLAYER_LABEL
    assert redacted.loc[0, "player_id"] == ""
    assert redacted.loc[0, ["runs", "balls"]].tolist() == [47, 31]
    assert redacted.loc[1].to_dict() == frame.loc[1].to_dict()


def test_link_redaction_uses_same_match_and_label_and_keeps_numeric_record() -> None:
    token = "reused-masked-token"
    source = [{"match_id": "match-1", "participant_id": token, "player_name": "Unverified source label"}]
    keys = collect_ambiguous_scorecard_link_keys(source, fingerprints={_sha(token)})
    links = pd.DataFrame(
        [
            {"match_id": "match-1", "canonical_player_id": "profile-1", "canonical_player_name": "Unverified source label", "runs_scored": 47},
            {"match_id": "match-2", "canonical_player_id": "profile-2", "canonical_player_name": "Unverified source label", "runs_scored": 12},
        ]
    )

    redacted, count = mask_scorecard_record_links(links, keys)

    assert count == 1
    assert redacted.loc[0, "canonical_player_name"] == PRIVATE_PLAYER_LABEL
    assert redacted.loc[0, "canonical_player_id"] == ""
    assert redacted.loc[0, "runs_scored"] == 47
    assert redacted.loc[1, "canonical_player_id"] == "profile-2"


def test_hawks_source_masking_is_club_scoped_and_person_aggregates_exclude_ambiguous_rows() -> None:
    token = "reused-masked-token"
    scoped_placeholder = "00000000-0000-0000-0000-000000000099"
    scoped_match = sorted(HAWKS_SCOPED_PLACEHOLDER_MATCH_IDS)[0]
    frame = pd.DataFrame(
        {
            "match_id": ["match-token", scoped_match, "other-match"],
            "participant_id": [token, scoped_placeholder, "verified-player-id"],
            "player_name": ["Unverified source label", "Another unverified label", "Public Player"],
            "runs_scored": [47, 31, 12],
        }
    )
    hashes = {_sha(token)}

    untouched = sanitize_hawks_source_frames({"batting": frame}, club_id="fvcc")
    assert untouched["batting"].equals(frame)

    masked = sanitize_hawks_source_frames(
        {"batting": frame}, club_id=HAWKS_CLUB_ID, fingerprints=hashes
    )["batting"]
    public = exclude_hawks_masked_source_rows({"batting": masked})["batting"]
    assert public["player_name"].tolist() == ["Public Player"]
    assert public["runs_scored"].tolist() == [12]
    assert masked["_gwhcc_masked_placeholder"].tolist() == [True, True, False]


def test_nil_uuid_placeholder_mask_is_scoped_to_reviewed_hawks_matches() -> None:
    placeholder = "00000000-0000-0000-0000-000000000099"
    reviewed_match = sorted(HAWKS_SCOPED_PLACEHOLDER_MATCH_IDS)[0]
    frame = pd.DataFrame(
        {
            "match_id": [reviewed_match, "unreviewed-match"],
            "player_id": [placeholder, placeholder],
            "player_name": ["Unverified source label", "Unreviewed label"],
            "runs": [47, 12],
            "balls": [31, 8],
        }
    )

    redacted, count = mask_hawks_participant_rows(
        frame, id_columns=["player_id"], name_columns=["player_name"]
    )

    assert is_match_scoped_hawks_placeholder(placeholder, reviewed_match)
    assert not is_match_scoped_hawks_placeholder(placeholder, "unreviewed-match")
    assert count == 1
    assert redacted.loc[0, "player_id"] == ""
    assert redacted.loc[0, "player_name"] == PRIVATE_PLAYER_LABEL
    assert redacted.loc[0, ["runs", "balls"]].tolist() == [47, 31]
    assert redacted.loc[1].to_dict() == frame.loc[1].to_dict()


def test_scoped_placeholder_name_only_link_is_masked_without_changing_scorecard_values() -> None:
    placeholder = "00000000-0000-0000-0000-000000000099"
    match_id = sorted(HAWKS_SCOPED_PLACEHOLDER_MATCH_IDS)[0]
    source = [{"match_id": match_id, "participant_id": placeholder, "player_name": "Unverified source label"}]
    keys = collect_ambiguous_scorecard_link_keys(source)
    links = pd.DataFrame(
        [
            {"match_id": match_id, "canonical_player_id": "profile-1", "canonical_player_name": "Unverified source label", "runs_scored": 47, "scorecard_url": "https://example.test/match"},
            {"match_id": "other-match", "canonical_player_id": "profile-2", "canonical_player_name": "Unverified source label", "runs_scored": 12, "scorecard_url": "https://example.test/other"},
        ]
    )

    redacted, count = mask_scorecard_record_links(links, keys)

    assert count == 1
    assert redacted.loc[0, "canonical_player_name"] == PRIVATE_PLAYER_LABEL
    assert redacted.loc[0, "canonical_player_id"] == ""
    assert redacted.loc[0, "runs_scored"] == 47
    assert redacted.loc[0, "scorecard_url"] == links.loc[0, "scorecard_url"]
    assert redacted.loc[1].to_dict() == links.loc[1].to_dict()


def test_hawks_match_count_diagnostic_masks_only_placeholder_shaped_ids() -> None:
    frame = pd.DataFrame(
        {
            "raw_player_id": ["00000000-0000-0000-0000-000000000099", "verified-player-id"],
            "canonical_player_name": ["Unverified source label", "Public Player"],
            "raw_playhq_matches": [20, 12],
            "weighted_matches": [10, 12],
            "match_delta": [10, 0],
        }
    )

    redacted, count = mask_hawks_unscoped_match_count_diagnostic(frame)

    assert count == 1
    assert redacted.loc[0, "raw_player_id"] == ""
    assert redacted.loc[0, "canonical_player_name"] == PRIVATE_PLAYER_LABEL
    assert redacted.loc[0, ["raw_playhq_matches", "weighted_matches", "match_delta"]].tolist() == [20, 10, 10]
    assert redacted.loc[1].to_dict() == frame.loc[1].to_dict()


def test_accepted_placeholder_fingerprints_are_two_hawks_only_tokens() -> None:
    assert len(MASKED_HAWKS_PARTICIPANT_ID_SHA256) == 2
    assert all(len(value) == 64 for value in MASKED_HAWKS_PARTICIPANT_ID_SHA256)
    assert HAWKS_CLUB_ID == "glen-waverley-hawks"


def test_processed_hawks_exports_do_not_retain_reused_participant_ids() -> None:
    for path in PROCESSED.rglob("*.csv"):
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
        if path.name == "gwhcc_match_count_policy_player_impact.csv":
            _, would_mask = mask_hawks_unscoped_match_count_diagnostic(frame)
            assert would_mask == 0, path
        else:
            assert not masked_hawks_participant_mask(frame).any(), path

    links = pd.read_csv(PROCESSED / "hall_of_fame" / "scorecard_record_links.csv", dtype=str, keep_default_na=False)
    private_links = links[links["canonical_player_name"].eq(PRIVATE_PLAYER_LABEL)]
    assert len(private_links) >= 15
    assert private_links["canonical_player_id"].eq("").all()
    assert pd.to_numeric(private_links["runs_scored"], errors="coerce").notna().any()


def test_hawks_identity_revision_invalidates_metadata_cache_signature(monkeypatch) -> None:
    metadata = json.loads((ROOT / "clubs" / HAWKS_CLUB_ID / "data" / "metadata.json").read_text())
    assert metadata["public_identity_revision"] == "hawks-masked-placeholder-event-scope-v2"
    monkeypatch.setenv("CLUB_ID", HAWKS_CLUB_ID)
    from src.ui import layout

    assert layout.metadata_mtime() == (ROOT / "clubs" / HAWKS_CLUB_ID / "data" / "metadata.json").stat().st_mtime


def test_processed_tree_redaction_is_idempotent() -> None:
    assert sanitize_hawks_processed_tree(PROCESSED) == {}


def test_hawks_match_centre_fallback_masks_placeholder_rows_without_dropping_scores(tmp_path, monkeypatch) -> None:
    import src.data.gwhcc_masked_privacy as privacy

    monkeypatch.setenv("CLUB_ID", HAWKS_CLUB_ID)
    scope = tmp_path / "all_available"
    scope.mkdir()
    pd.DataFrame([{"match_id": "match-1", "season": "Summer 2026/27", "first_match_day": "2026-10-31"}]).to_csv(
        scope / "all_matches.csv", index=False
    )
    for filename in ("all_scorecard_batting.csv", "all_scorecard_bowling.csv"):
        pd.DataFrame(
            [
                {"match_id": "match-1", "innings_id": "innings-1", "participant_id": "masked-source-id",
                 "player_id": "masked-source-id", "player_name": "Unverified source label", "runs_scored": 47,
                 "balls_faced": 30, "wickets_taken": 0, "runs_conceded": 0},
                {"match_id": "match-1", "innings_id": "innings-1", "participant_id": "public-source-id",
                 "player_id": "public-source-id", "player_name": "Public Player", "runs_scored": 12,
                 "balls_faced": 8, "wickets_taken": 0, "runs_conceded": 0},
            ]
        ).to_csv(scope / filename, index=False)
    monkeypatch.setattr(layout, "MATCH_CENTRE_PROCESSED_ROOT", tmp_path)
    monkeypatch.setattr(
        layout,
        "load_deploy_scorecard_record_rows",
        lambda club_id=None: {"batting": pd.DataFrame(), "bowling": pd.DataFrame()},
    )

    def mask_test_token(frame, *, id_columns=None, name_columns=None, **_kwargs):
        output = frame.copy()
        mask = output["participant_id"].eq("masked-source-id")
        for column in name_columns or ["player_name", "canonical_player_name", "display_player_name"]:
            if column in output:
                output.loc[mask, column] = PRIVATE_PLAYER_LABEL
        for column in id_columns or []:
            if column in output:
                output.loc[mask, column] = ""
        return output, int(mask.sum())

    monkeypatch.setattr(privacy, "mask_hawks_participant_rows", mask_test_token)
    rows = layout.load_scorecard_record_rows.__wrapped__(("fallback-test",))["batting"]
    masked = rows[rows.player_name.eq(PRIVATE_PLAYER_LABEL)]
    assert len(masked) == 1
    assert int(masked.iloc[0].runs_scored) == 47
    for column in ID_COLUMNS:
        if column in masked:
            assert masked[column].fillna("").eq("").all()
    public = rows[rows.player_name.eq("Public Player")]
    assert len(public) == 1 and public.iloc[0].canonical_player_id
