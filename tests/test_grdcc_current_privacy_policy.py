from __future__ import annotations

import hashlib
import json

import pandas as pd
import pytest

from src.data import grdcc_player_privacy as privacy
from src.data.fastest_innings import private_candidate
from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
from src.config.club_config import get_hall_of_fame_dir
from src.data import playcricket_ingestion
from src.data.partnerships import governed_batter_identity
from src.ui import layout
from src.data.playcricket_ingestion import metadata_mtime
from src.utils.player_identity import filter_public_player_rows, get_player_profile_data, player_aliases_mtime
from match_centre_source_snapshot import verify_current_privacy_snapshot
from scripts.build_grdcc_privacy_filtered_artifacts import PROCESSED_ARTIFACTS


CLUB = "georges-river-district"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _snapshot_row(canonical_id: str, participant_id: str, status: str, public_name: str = ""):
    return {
        "canonical_player_id_sha256": _sha(canonical_id),
        "source_participant_id_sha256": _sha(participant_id),
        "status": status,
        "public_name": public_name,
        "verified_at": "2026-11-10T08:44:25+00:00",
        "source": "pinned official-source fixture",
        "source_record_sha256": "a" * 64,
        "source_payload_sha256": "b" * 64,
    }


def _write_snapshot(tmp_path, monkeypatch, rows):
    path = tmp_path / "privacy.csv"
    pd.DataFrame(rows, columns=privacy.SNAPSHOT_COLUMNS).to_csv(path, index=False)
    monkeypatch.setattr(privacy, "SNAPSHOT_PATH", path)
    privacy._load_snapshot.cache_clear()
    privacy._status_index_for_signature.cache_clear()
    return path


def test_exact_id_public_status_overrides_old_mask_without_name_join(tmp_path, monkeypatch):
    _write_snapshot(
        tmp_path,
        monkeypatch,
        [
            _snapshot_row("public-canonical", "public-source-id", "public", "Current Public Name"),
            _snapshot_row("private-canonical", "private-source-id", "private"),
        ],
    )
    source = pd.DataFrame(
        [
            {
                "canonical_player_id": "public-canonical",
                "raw_player_id": "public-source-id",
                "Player": "Private player",
                "canonical_player_name": "Private player",
                "player_name": "********",
                "raw_player_name": "********",
            },
            {
                "canonical_player_id": "private-canonical",
                "raw_player_id": "private-source-id",
                "Player": "Stale visible name",
                "canonical_player_name": "Stale visible name",
                "player_name": "Stale visible name",
                "raw_player_name": "Stale visible name",
            },
            {
                "canonical_player_id": "different-person-id",
                "raw_player_id": "different-source-id",
                "Player": "Current Public Name",
                "canonical_player_name": "Current Public Name",
                "player_name": "Current Public Name",
                "raw_player_name": "Current Public Name",
            },
            {
                "canonical_player_id": "unknown-id",
                "raw_player_id": "unknown-source-id",
                "Player": "Private player",
                "canonical_player_name": "Private player",
                "player_name": "Private player",
                "raw_player_name": "Private player",
            },
        ]
    )

    result = filter_public_player_rows(source, club_id=CLUB)

    assert result.canonical_player_id.tolist() == [
        "public-canonical",
        "different-person-id",
    ]
    public_row = result.iloc[0]
    assert public_row.Player == "Current Public Name"
    assert public_row.canonical_player_name == "Current Public Name"
    assert public_row.raw_player_name == "********"


def test_partnership_identity_uses_current_status_by_exact_ids(tmp_path, monkeypatch):
    _write_snapshot(
        tmp_path,
        monkeypatch,
        [
            _snapshot_row("public-canonical", "public-source-id", "public", "Current Public Name"),
            _snapshot_row("private-canonical", "private-source-id", "private"),
        ],
    )
    lookup = {
        "public-source-id": {
            "canonical_player_id": "public-canonical",
            "canonical_player_name": "Private player",
        },
        "private-source-id": {
            "canonical_player_id": "private-canonical",
            "canonical_player_name": "Stale public label",
        },
    }

    now_public = governed_batter_identity(
        "public-source-id", "********", lookup, club_id=CLUB
    )
    now_private = governed_batter_identity(
        "private-source-id", "Stale public label", lookup, club_id=CLUB
    )
    unrelated_same_name = governed_batter_identity(
        "unapproved-id", "Current Public Name", lookup, club_id=CLUB
    )

    assert now_public["private"] is False
    assert now_public["canonical_name"] == "Current Public Name"
    assert now_private["private"] is True
    assert unrelated_same_name["private"] is False
    assert unrelated_same_name["canonical_id"] == ""


def test_delivery_record_privacy_uses_exact_current_identity(tmp_path, monkeypatch):
    _write_snapshot(
        tmp_path,
        monkeypatch,
        [
            _snapshot_row("public-canonical", "public-source-id", "public", "Current Public Name"),
            _snapshot_row("private-canonical", "private-source-id", "private"),
        ],
    )
    assert not private_candidate(
        pd.Series(
            {
                "canonical_player_id": "public-canonical",
                "participant_id": "public-source-id",
                "player_name": "********",
                "canonical_player_name": "Private player",
            }
        ),
        CLUB,
    )
    assert private_candidate(
        pd.Series(
            {
                "canonical_player_id": "private-canonical",
                "participant_id": "private-source-id",
                "player_name": "Stale Public Name",
                "canonical_player_name": "Stale Public Name",
            }
        ),
        CLUB,
    )


def test_hat_trick_fastest_and_partnership_loaders_apply_snapshot(tmp_path, monkeypatch):
    path = _write_snapshot(
        tmp_path,
        monkeypatch,
        [
            _snapshot_row("public-canonical", "public-source-id", "public", "Current Public Name"),
            _snapshot_row("private-canonical", "private-source-id", "private"),
        ],
    )
    events = pd.DataFrame(
        [
            {
                "event_id": "public-event",
                "canonical_player_id": "public-canonical",
                "canonical_player_name": "Private player",
                "player_name": "********",
                "match_date": "2026-01-01",
            },
            {
                "event_id": "private-event",
                "canonical_player_id": "private-canonical",
                "canonical_player_name": "Stale Public Name",
                "player_name": "Stale Public Name",
                "match_date": "2026-01-02",
            },
        ]
    )
    milestones = events.assign(final_score_display="50", final_runs=50, balls_to_50=20)
    partnerships = pd.DataFrame(
        [
            {
                "wicket_number": 1,
                "player_1_canonical_id": "public-canonical",
                "player_2_canonical_id": "partner-id",
                "player_1_name": "Private player",
                "player_2_name": "Public Partner",
                "runs": 60,
            },
            {
                "wicket_number": 2,
                "player_1_canonical_id": "private-canonical",
                "player_2_canonical_id": "partner-id-2",
                "player_1_name": "Stale Public Name",
                "player_2_name": "Public Partner",
                "runs": 70,
            },
        ]
    )
    milestones_path = tmp_path / "milestones.csv"
    partnerships_path = tmp_path / "partnerships.csv"
    milestones.to_csv(milestones_path, index=False)
    partnerships.to_csv(partnerships_path, index=False)
    signature = privacy.privacy_snapshot_signature(CLUB)
    layout.load_hat_trick_records.clear()
    layout.load_batting_milestone_records.clear()
    layout.load_partnership_records.clear()

    hat_tricks = layout.load_hat_trick_records(
        CLUB, str(milestones_path), milestones_path.stat().st_mtime, signature
    )
    fastest = layout.load_batting_milestone_records(
        CLUB, str(milestones_path), milestones_path.stat().st_mtime, signature
    )
    partnership_records = layout.load_partnership_records(
        CLUB, str(partnerships_path), partnerships_path.stat().st_mtime, signature
    )

    assert hat_tricks.event_id.tolist() == ["public-event"]
    assert hat_tricks.canonical_player_name.tolist() == ["Current Public Name"]
    assert fastest.event_id.tolist() == ["public-event"]
    assert fastest.canonical_player_name.tolist() == ["Current Public Name"]
    assert partnership_records.wicket_number.tolist() == [1, 2]
    assert partnership_records.iloc[0].player_1_name == "Current Public Name"
    assert partnership_records.iloc[0].privacy_status == "PUBLIC_PUBLIC"
    assert partnership_records.iloc[1].player_1_name == "Private player"
    assert partnership_records.iloc[1].player_1_canonical_id == ""
    assert partnership_records.iloc[1].privacy_status == "PUBLIC_PRIVATE"

    scorecard_links_path = tmp_path / "scorecard_record_links.csv"
    pd.DataFrame(
        [
            {
                "mode": "batting",
                "canonical_player_id": "public-canonical",
                "canonical_player_name": "Private player",
                "season": "Summer 2025/26",
                "record_type": "high_score",
            },
            {
                "mode": "batting",
                "canonical_player_id": "private-canonical",
                "canonical_player_name": "Stale Public Name",
                "season": "Summer 2025/26",
                "record_type": "high_score",
            },
            {
                "mode": "batting",
                "canonical_player_id": "different-person-id",
                "canonical_player_name": "Current Public Name",
                "season": "Summer 2025/26",
                "record_type": "high_score",
            },
        ]
    ).to_csv(scorecard_links_path, index=False)
    monkeypatch.setattr(layout, "HALL_OF_FAME_SCORECARD_RECORD_LINKS_PATH", scorecard_links_path)
    scorecard_rows = layout.load_deploy_scorecard_record_rows(CLUB)["batting"]
    assert set(scorecard_rows.canonical_player_id) == {
        "public-canonical",
        "different-person-id",
    }
    assert scorecard_rows.loc[
        scorecard_rows.canonical_player_id.eq("public-canonical"), "canonical_player_name"
    ].tolist() == ["Current Public Name"]

    verified_path = tmp_path / "verified_partnership_records.csv"
    pd.DataFrame(
        [
            {
                "wicket_number": 1,
                "batter_1": "public-canonical",
                "batter_2": "partner-canonical",
                "batter_1_public_name": "Private player",
                "batter_2_public_name": "Public Partner",
                "partnership_runs": 60,
                "balls_faced": 50,
            },
            {
                "wicket_number": 2,
                "batter_1": "private-canonical",
                "batter_2": "partner-canonical-2",
                "batter_1_public_name": "Stale Public Name",
                "batter_2_public_name": "Public Partner",
                "partnership_runs": 70,
                "balls_faced": 60,
            },
            {
                "wicket_number": 3,
                "batter_1": "private-canonical",
                "batter_2": "unknown-private",
                "batter_1_public_name": "Stale Public Name",
                "batter_2_public_name": "Private player",
                "partnership_runs": 80,
                "balls_faced": 70,
            },
        ]
    ).to_csv(verified_path, index=False)
    layout.load_verified_partnership_records.clear()
    verified_records = layout.load_verified_partnership_records(
        CLUB,
        str(verified_path),
        verified_path.stat().st_mtime,
        signature,
    )
    assert verified_records.wicket_number.tolist() == [1, 2]
    assert verified_records.iloc[0].player_1_name == "Current Public Name"
    assert verified_records.iloc[0].privacy_status == "PUBLIC_PUBLIC"
    assert verified_records.iloc[1].player_1_name == "Private player"
    assert verified_records.iloc[1].player_1_canonical_id == ""
    assert verified_records.iloc[1].privacy_status == "PUBLIC_PRIVATE"
    rendered_private = layout.partnership_record_row_html(verified_records.iloc[1])
    assert "Private player" in rendered_private
    assert "Private player</a>" not in rendered_private
    assert "private-canonical" not in rendered_private

    scorecard_links_path = tmp_path / "scorecard_record_links.csv"
    pd.DataFrame(
        [
            {
                "mode": "batting",
                "canonical_player_id": "public-canonical",
                "canonical_player_name": "Private player",
                "season": "Summer 2025/26",
                "record_type": "high_score",
            },
            {
                "mode": "batting",
                "canonical_player_id": "private-canonical",
                "canonical_player_name": "Stale Public Name",
                "season": "Summer 2025/26",
                "record_type": "high_score",
            },
            {
                "mode": "batting",
                "canonical_player_id": "different-person-id",
                "canonical_player_name": "Current Public Name",
                "season": "Summer 2025/26",
                "record_type": "high_score",
            },
        ]
    ).to_csv(scorecard_links_path, index=False)
    monkeypatch.setattr(layout, "HALL_OF_FAME_SCORECARD_RECORD_LINKS_PATH", scorecard_links_path)
    scorecard_rows = layout.load_deploy_scorecard_record_rows(CLUB)["batting"]
    assert set(scorecard_rows.canonical_player_id) == {
        "public-canonical",
        "different-person-id",
    }
    assert scorecard_rows.loc[
        scorecard_rows.canonical_player_id.eq("public-canonical"), "canonical_player_name"
    ].tolist() == ["Current Public Name"]


def test_unknown_or_conflicting_source_state_fails_closed(tmp_path, monkeypatch):
    path = _write_snapshot(
        tmp_path,
        monkeypatch,
        [_snapshot_row("identity", "participant", "private")],
    )
    with pytest.raises(ValueError, match="one row per canonical identity"):
        pd.concat([pd.read_csv(path), pd.read_csv(path)]).to_csv(path, index=False)
        privacy._load_snapshot.cache_clear()
        privacy.load_current_privacy_snapshot(CLUB)


def test_current_privacy_snapshot_invalidates_hof_cache_signature(tmp_path, monkeypatch):
    monkeypatch.setenv("CLUB_ID", CLUB)
    path = _write_snapshot(
        tmp_path,
        monkeypatch,
        [_snapshot_row("fixture-id", "fixture-source", "public", "Fixture Public")],
    )
    before = {
        "hof": layout.hall_of_fame_override_signature(CLUB),
        "win_rates": layout.player_win_rates_signature(),
        "career_details": layout.hall_of_fame_detail_source_signature(),
        "scorecard_record_links": layout.scorecard_record_rows_signature(),
    }
    updated = pd.read_csv(path)
    updated.loc[0, "verified_at"] = "2026-11-10T09:00:00+00:00"
    updated.to_csv(path, index=False)
    privacy._load_snapshot.cache_clear()
    privacy._status_index_for_signature.cache_clear()
    after = {
        "hof": layout.hall_of_fame_override_signature(CLUB),
        "win_rates": layout.player_win_rates_signature(),
        "career_details": layout.hall_of_fame_detail_source_signature(),
        "scorecard_record_links": layout.scorecard_record_rows_signature(),
    }
    assert all(before[key] != after[key] for key in before)


def test_grdcc_snapshot_does_not_change_fvcc_or_hawks_filtering(tmp_path, monkeypatch):
    _write_snapshot(
        tmp_path,
        monkeypatch,
        [_snapshot_row("fixture-id", "fixture-source", "public", "Visible Name")],
    )
    masked = pd.DataFrame(
        [
            {
                "canonical_player_id": "fixture-id",
                "raw_player_id": "fixture-source",
                "Player": "Private player",
            }
        ]
    )

    assert len(filter_public_player_rows(masked, club_id="fvcc")) == 0
    assert len(filter_public_player_rows(masked, club_id="glen-waverley-hawks")) == 0
    assert filter_public_player_rows(masked, club_id=CLUB).Player.tolist() == ["Visible Name"]


def test_verified_snapshot_applies_to_actual_prepared_hof_population(monkeypatch):
    monkeypatch.setenv("CLUB_ID", CLUB)
    layout._load_player_profile_index_cached.clear()
    playcricket_ingestion._read_processed_table_cached.clear()
    verify_current_privacy_snapshot()
    prepared = load_prepared_hall_of_fame_core(CLUB, layout.HALL_OF_FAME_DATA_VERSION)
    assert prepared is not None
    manifest = json.loads(
        (get_hall_of_fame_dir(club_id=CLUB) / "prepared_core_manifest.json").read_text()
    )
    assert manifest["public_filter_version"] == "grdcc-current-playcricket-privacy-and-career-v2"
    assert any(
        "grdcc_current_privacy_status.csv" in entry["path"]
        for entry in manifest["source_signature"]
    )
    raw_hof = prepared["all_time"]
    served = layout.filter_public_hall_of_fame_rows(raw_hof, CLUB)
    snapshot = privacy.load_current_privacy_snapshot(CLUB)
    assert snapshot.status.value_counts().to_dict() == {"public": 2, "private": 1}
    profile_index = layout.load_player_profile_index(
        CLUB,
        metadata_mtime(),
        player_aliases_mtime(club_id=CLUB),
    )

    for row in snapshot.itertuples(index=False):
        raw_hashes = raw_hof.canonical_player_id.astype(str).map(_sha)
        source_identity = raw_hof.loc[
            raw_hashes.eq(row.canonical_player_id_sha256), "canonical_player_id"
        ]
        served_hashes = served.canonical_player_id.astype(str).map(_sha)
        selected = served.loc[served_hashes.eq(row.canonical_player_id_sha256)]
        if row.status == "private":
            assert source_identity.astype(str).nunique() <= 1
            assert selected.empty
            assert not profile_index.id.astype(str).map(_sha).eq(row.canonical_player_id_sha256).any()
            continue
        assert source_identity.astype(str).nunique() == 1
        canonical_id = str(source_identity.iloc[0])
        assert len(selected) == 1
        shown_name = selected.iloc[0].get("Player", selected.iloc[0].get("canonical_player_name", ""))
        assert shown_name == row.public_name
        assert profile_index.loc[
            profile_index.id.astype(str).map(_sha).eq(row.canonical_player_id_sha256), "name"
        ].astype(str).tolist() == [row.public_name]
        assert layout.resolve_public_profile_target(canonical_id, "Private player") == canonical_id
        profile = get_player_profile_data(canonical_id, club_id=CLUB)
        assert profile["player_info"]["canonical_player_name"] == row.public_name


def test_rebuilt_public_partnership_artifacts_obey_current_privacy_snapshot():
    from match_centre_source_snapshot import source_manifest

    manifest = source_manifest()["combined_expected_partnerships"]
    hall_of_fame = get_hall_of_fame_dir(club_id=CLUB)
    events_path = hall_of_fame / "partnerships.csv"
    records_path = hall_of_fame / "partnership_records.csv"
    assert hashlib.sha256(events_path.read_bytes()).hexdigest() == manifest["partnerships_sha256"]
    assert hashlib.sha256(records_path.read_bytes()).hexdigest() == manifest["partnership_records_sha256"]
    events = pd.read_csv(events_path, dtype=str, low_memory=False).fillna("")
    records = pd.read_csv(records_path, dtype=str, low_memory=False).fillna("")
    assert len(events) == manifest["events"]
    assert events.privacy_status.value_counts().to_dict() == {
        "PUBLIC_PUBLIC": manifest["PUBLIC_PUBLIC"],
        "PUBLIC_PRIVATE": manifest["PUBLIC_PRIVATE"],
    }
    assert len(records) == manifest["record_rows"]
    assert not events[["batter_1_public_name", "batter_2_public_name"]].apply(
        lambda column: column.astype(str).str.contains(r"\*{2,}", regex=True)
    ).any().any()

    snapshot = privacy.load_current_privacy_snapshot(CLUB)
    for policy in snapshot.itertuples(index=False):
        public_rows = []
        for id_column, name_column in (
            ("batter_1", "batter_1_public_name"),
            ("batter_2", "batter_2_public_name"),
        ):
            matches = events.loc[
                events[id_column].astype(str).map(_sha).eq(policy.canonical_player_id_sha256)
            ]
            public_rows.extend(matches[name_column].astype(str).tolist())
        if policy.status == "public":
            assert public_rows
            assert set(public_rows) == {policy.public_name}
        else:
            assert not public_rows
            private_rows = events.loc[events.privacy_status.eq("PUBLIC_PRIVATE")]
            assert private_rows[["batter_1", "batter_2"]].astype(str).apply(
                lambda column: column.map(_sha).eq(policy.canonical_player_id_sha256)
            ).sum().sum() == 0
    assert int(events[["batter_1_public_name", "batter_2_public_name"]].eq("Private player").sum().sum()) == manifest["PUBLIC_PRIVATE"]


def test_grdcc_public_summary_artifacts_exclude_current_private_exact_ids():
    snapshot = privacy.load_current_privacy_snapshot(CLUB)
    private_hashes = set(
        snapshot.loc[snapshot.status.eq("private"), "canonical_player_id_sha256"].astype(str)
    )
    for relative_path in PROCESSED_ARTIFACTS:
        frame = pd.read_csv(relative_path, low_memory=False)
        assert "canonical_player_id" in frame.columns
        hashes = frame.canonical_player_id.fillna("").astype(str).map(
            lambda value: _sha(value.strip()) if value.strip() else ""
        )
        assert not hashes.isin(private_hashes).any(), relative_path
