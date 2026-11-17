"""Apply current exact-ID GRDCC privacy policy to committed processed outputs.

Run after refreshing processed GRDCC summaries and before publishing their
prepared copies. Raw PlayCricket and historical source tables are untouched.
Diagnostic validation rows for private identities are also excluded from the
committed processed tree; restricted originals belong in the local checkpoint.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.grdcc_player_privacy import load_current_privacy_snapshot
from src.utils.player_identity import filter_public_player_rows


CLUB = "georges-river-district"
PROCESSED_ARTIFACTS = (
    "clubs/georges-river-district/data/processed/season_overview/bbb_bowling_dot_rates_by_scope.csv",
    "clubs/georges-river-district/data/processed/season_overview/bbb_batting_rates_by_scope.csv",
    "clubs/georges-river-district/data/processed/season_overview/scorecard_batting_milestones_by_scope.csv",
    "clubs/georges-river-district/data/processed/season_overview/scorecard_bowling_milestones_by_scope.csv",
    "clubs/georges-river-district/data/processed/player_profile/bowling_phase_summary.csv",
    "clubs/georges-river-district/data/processed/player_profile/recent_form_batting.csv",
    "clubs/georges-river-district/data/processed/player_profile/dismissal_fingerprint_summary.csv",
    "clubs/georges-river-district/data/processed/player_profile/batting_position_summary.csv",
    "clubs/georges-river-district/data/processed/player_profile/performance_breakdown_by_dimension.csv",
    "clubs/georges-river-district/data/processed/player_profile/recent_form_bowling.csv",
    "clubs/georges-river-district/data/processed/hall_of_fame/player_scorecard_milestones.csv",
    "clubs/georges-river-district/data/processed/hall_of_fame/player_win_rates.csv",
    "clubs/georges-river-district/data/processed/hall_of_fame/scorecard_record_links.csv",
    "clubs/georges-river-district/data/processed/validation/grdcc_fastest_innings_validation.csv",
    "clubs/georges-river-district/data/processed/validation/grdcc_fastest_innings_rejected_candidates.csv",
)
PUBLIC_NAME_COLUMNS = (
    "Player",
    "player_name",
    "canonical_player_name",
    "display_player_name",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def filtered_bytes(path: Path) -> tuple[bytes, dict[str, object]]:
    original = path.read_bytes()
    frame = pd.read_csv(path, low_memory=False)
    filtered = filter_public_player_rows(frame, club_id=CLUB)
    common = frame.index.intersection(filtered.index)
    label_updates = 0
    for column in PUBLIC_NAME_COLUMNS:
        if column in frame and column in filtered:
            label_updates += int(frame.loc[common, column].astype(str).ne(filtered.loc[common, column].astype(str)).sum())

    output = filtered.to_csv(index=False, lineterminator="\n").encode("utf-8")
    report = {
        "path": str(path.relative_to(ROOT)),
        "rows_before": int(len(frame)),
        "rows_after": int(len(filtered)),
        "rows_removed": int(len(frame) - len(filtered)),
        "public_labels_updated": label_updates,
        "sha256_before": sha256(original),
        "sha256_after": sha256(output),
    }
    return output, report


def ensure_no_verified_private_ids(output: bytes, report: dict[str, object]) -> None:
    snapshot = load_current_privacy_snapshot(CLUB)
    private_hashes = set(
        snapshot.loc[snapshot.status.eq("private"), "canonical_player_id_sha256"].astype(str)
    )
    frame = pd.read_csv(io.BytesIO(output), low_memory=False)
    if "canonical_player_id" not in frame:
        raise ValueError(f"Public artifact lacks canonical_player_id: {report['path']}")
    found = frame.canonical_player_id.fillna("").astype(str).map(
        lambda value: hashlib.sha256(value.strip().encode("utf-8")).hexdigest()
        if value.strip()
        else ""
    )
    if found.isin(private_hashes).any():
        raise ValueError(f"Current-private identity remains in public artifact: {report['path']}")


def write_atomic(path: Path, data: bytes) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the filtered public artifacts. Without this flag, only report changes.",
    )
    args = parser.parse_args()

    results = []
    for relative in PROCESSED_ARTIFACTS:
        path = ROOT / relative
        if not path.is_file():
            raise FileNotFoundError(f"Expected GRDCC public summary artifact is missing: {relative}")
        output, report = filtered_bytes(path)
        ensure_no_verified_private_ids(output, report)
        if args.apply and output != path.read_bytes():
            write_atomic(path, output)
        results.append(report)

    print(
        json.dumps(
            {
                "mode": "apply" if args.apply else "check",
                "artifacts": len(results),
                "rows_removed": sum(int(row["rows_removed"]) for row in results),
                "labels_updated": sum(int(row["public_labels_updated"]) for row in results),
                "files": results,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
