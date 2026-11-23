from io import BytesIO
import json
import subprocess
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from scripts.public_release_boundary import (
    GRDCC, MARKER, is_private_grdcc_path, protected_pattern, require_artifact_destination,
    scan_content, scan_tree, validate_tree,
)


PRIVATE_ID = "synthetic_private_player_0001"


def zip_bytes(files):
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, body in files.items():
            archive.writestr(name, body)
    return buffer.getvalue()


def test_grdcc_generation_is_blocked_only_in_the_public_checkout(tmp_path):
    require_artifact_destination(GRDCC, tmp_path)
    (tmp_path / MARKER).touch()
    with pytest.raises(ValueError, match="private deployment checkout"):
        require_artifact_destination(GRDCC, tmp_path)
    for club in ("fvcc", "glen-waverley-hawks"):
        require_artifact_destination(club, tmp_path)


@pytest.mark.parametrize("path", [
    f"clubs/{GRDCC}/data/source/roster.json",
    f"clubs/{GRDCC}/data/processed/player.csv",
    f"clubs/{GRDCC}/prepared_views/public_views.zip",
    f"clubs/{GRDCC}/player_aliases.csv",
    f"clubs/{GRDCC}/manual_player_merges.csv",
    "tests/fixtures/grdcc_privacy_evidence.csv",
])
def test_private_club_paths_cannot_be_reintroduced(path):
    assert is_private_grdcc_path(path)
    assert not is_private_grdcc_path(f"clubs/{GRDCC}/club_config.yaml")
    assert not is_private_grdcc_path("clubs/fvcc/prepared_views/public_views.zip")


@pytest.mark.parametrize("text", [
    f"player_id,runs\n{PRIVATE_ID},17",
    json.dumps({"index": [{"key": PRIVATE_ID}]}),
    json.dumps({"href": "?player_id=" + quote(PRIVATE_ID).replace("_", "%5f")}),
    json.dumps({"career_summary": {"owner": PRIVATE_ID, "wickets": 5}}),
])
def test_exact_identity_scan_covers_public_csv_json_and_links(text):
    assert scan_content(text.encode(), protected_pattern([PRIVATE_ID])) == (True, 0)


def test_compressed_identity_leak_does_not_require_changing_anonymous_statistics():
    protected = protected_pattern([PRIVATE_ID])
    approved = b'{"player":"Private player","runs":17,"balls":24,"wickets":0}'
    archive = zip_bytes({"valid.json": approved})
    assert scan_content(archive, protected) == (False, 1)
    exposure = zip_bytes({"nested.zip": zip_bytes({"profile.json": json.dumps({"profile_id": PRIVATE_ID})})})
    assert scan_content(exposure, protected) == (True, 2)
    assert scan_content(zip_bytes({PRIVATE_ID + ".json": approved}), protected) == (True, 1)
    assert scan_content(approved, protected) == (False, 0)


def test_exact_git_tree_requires_the_boundary_and_rejects_staged_regeneration(tmp_path):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path, text=True).strip()

    git("init", "-q")
    path = f"clubs/{GRDCC}/prepared_views/public_views.zip"
    target = tmp_path / path
    target.parent.mkdir(parents=True)
    target.write_bytes(zip_bytes({"index.json": json.dumps({"id": PRIVATE_ID})}))
    (tmp_path / MARKER).touch()
    git("add", "--", MARKER, path)
    tree = git("write-tree")
    assert validate_tree(tmp_path, tree) == [path]
    assert scan_tree(tmp_path, tree, protected_pattern([PRIVATE_ID])) == {
        "files": 2, "archive_members": 1, "restricted_identity_paths": [path],
    }
