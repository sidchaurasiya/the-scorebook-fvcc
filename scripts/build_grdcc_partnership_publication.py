"""Rebuild GRDCC partnerships from pinned historical and cutoff current sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.partnerships import (  # noqa: E402
    build_governed_club_partnerships,
    build_verified_partnership_record_holders,
    write_csv_atomic,
)


CLUB_ID = "georges-river-district"
FILES = (
    "all_matches.csv",
    "all_ball_by_ball.csv",
    "all_scorecard_batting.csv",
    "all_match_innings.csv",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_files(root: Path, receipts: dict[str, dict[str, object]]) -> None:
    for filename in FILES:
        expected = receipts[filename]
        path = root / filename
        if not path.is_file() or sha256(path) != expected["sha256"]:
            raise ValueError(f"Pinned source fingerprint mismatch: {filename}")
        frame = pd.read_csv(path, low_memory=False)
        if len(frame) != int(expected["rows"]):
            raise ValueError(f"Pinned source row count mismatch: {filename}")


def cutoff_source(source: Path, cutoff: date, destination: Path) -> tuple[Path, dict[str, int]]:
    matches = pd.read_csv(source / "all_matches.csv", dtype=str, low_memory=False).fillna("")
    local_dates = pd.to_datetime(
        matches["first_match_day"], errors="coerce", utc=True
    ).dt.tz_convert("Australia/Sydney").dt.date
    selected_ids = set(matches.loc[local_dates.le(cutoff), "match_id"].astype(str))
    if not selected_ids:
        raise ValueError("No current-season matches fall within the approved cutoff")

    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    counts: dict[str, int] = {}
    for filename in FILES:
        frame = pd.read_csv(source / filename, dtype=str, low_memory=False).fillna("")
        filtered = frame.loc[frame.match_id.astype(str).isin(selected_ids)].copy()
        output = destination / filename
        filtered.to_csv(output, index=False)
        output.chmod(0o600)
        counts[filename] = len(filtered)

    selected_matches = matches.loc[matches.match_id.astype(str).isin(selected_ids)].copy()
    selected_matches["_local_date"] = local_dates.loc[selected_matches.index]
    if selected_matches["_local_date"].dropna().gt(cutoff).any():
        raise ValueError("Current source cutoff filtering included a later fixture")
    return destination, {"matches": len(selected_ids), **counts}


def secure_write(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    write_csv_atomic(frame, path)
    path.chmod(0o600)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-root", required=True, type=Path)
    parser.add_argument("--current-root", required=True, type=Path)
    parser.add_argument("--source-manifest", type=Path, default=ROOT / "tests/fixtures/grdcc_partnership_source_snapshot_2026-11-10.json")
    parser.add_argument("--cutoff", default="2026-10-31")
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--validation-dir", required=True, type=Path)
    args = parser.parse_args()

    manifest = json.loads(args.source_manifest.read_text(encoding="utf-8"))
    historical_scope = manifest["historical_scope"]
    current_scope = manifest["current_season_scope"]
    privacy_source = manifest["current_privacy_snapshot"]
    privacy_path = ROOT / str(privacy_source["path"])
    if not privacy_path.is_file() or sha256(privacy_path) != privacy_source["sha256"]:
        raise ValueError("Current privacy snapshot does not match its pinned source manifest")
    privacy_rows = pd.read_csv(privacy_path, dtype=str).fillna("")
    if len(privacy_rows) != privacy_source["rows"]:
        raise ValueError("Current privacy snapshot row count differs from its pinned manifest")
    if privacy_rows.status.value_counts().to_dict() != {
        "public": privacy_source["public"],
        "private": privacy_source["private"],
    }:
        raise ValueError("Current privacy distribution differs from its pinned source receipt")
    if args.cutoff != current_scope["cutoff_local_date"]:
        raise ValueError("Requested cutoff does not match the pinned candidate source snapshot")
    verify_files(args.historical_root, historical_scope["files"])
    verify_files(args.current_root, current_scope["full_snapshot_files"])

    historical = build_governed_club_partnerships(
        club_id=CLUB_ID,
        match_centre_root=args.historical_root,
    )
    with tempfile.TemporaryDirectory(prefix="grdcc-partnership-cutoff-") as temporary:
        os.chmod(temporary, 0o700)
        current_root, filtered_counts = cutoff_source(
            args.current_root,
            date.fromisoformat(args.cutoff),
            Path(temporary) / "current_scope",
        )
        current = build_governed_club_partnerships(
            club_id=CLUB_ID,
            match_centre_root=current_root,
        )

        expected_historical = historical_scope["expected_partnerships"]
        expected_current = current_scope["expected_partnerships"]
        expected_combined = manifest["combined_expected_partnerships"]
        if len(historical.events) != expected_historical["events"]:
            raise ValueError("Historical event count differs from its pinned source receipt")
        if historical.events.privacy_status.value_counts().to_dict() != {
            "PUBLIC_PUBLIC": expected_historical["PUBLIC_PUBLIC"],
            "PUBLIC_PRIVATE": expected_historical["PUBLIC_PRIVATE"],
        }:
            raise ValueError("Historical privacy distribution differs from its pinned source receipt")
        if len(current.events) != expected_current["events"]:
            raise ValueError("Cutoff current event count differs from its pinned source receipt")
        if current.events.privacy_status.value_counts().to_dict() != {
            "PUBLIC_PUBLIC": expected_current["PUBLIC_PUBLIC"],
            "PUBLIC_PRIVATE": expected_current["PUBLIC_PRIVATE"],
        }:
            raise ValueError("Cutoff current privacy distribution differs from its pinned source receipt")

        historical_events = historical.events.copy()
        current_events = current.events.copy()
        events = pd.concat([historical_events, current_events], ignore_index=True)
        if events["partnership_id"].astype(str).duplicated().any():
            raise ValueError("Historical and current source scopes contain duplicate partnership IDs")
        events = events.sort_values(
            ["match_date", "match_id", "innings", "partnership_id"],
            ascending=[False, True, True, True],
            kind="mergesort",
            na_position="last",
        ).reset_index(drop=True)
        records, selection_audit = build_verified_partnership_record_holders(events)
        if len(events) != expected_combined["events"]:
            raise ValueError("Combined partnership population differs from its pinned reconciliation")
        if events.privacy_status.value_counts().to_dict() != {
            "PUBLIC_PUBLIC": expected_combined["PUBLIC_PUBLIC"],
            "PUBLIC_PRIVATE": expected_combined["PUBLIC_PRIVATE"],
        }:
            raise ValueError("Combined privacy distribution differs from its pinned reconciliation")
        if len(records) != expected_combined["record_rows"]:
            raise ValueError("Combined partnership record-holder count differs from its pinned audit")

        args.output_dir.mkdir(parents=True, exist_ok=True)
        write_csv_atomic(events, args.output_dir / "partnerships.csv")
        write_csv_atomic(records, args.output_dir / "partnership_records.csv")

        validation = args.validation_dir
        validation.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(validation, 0o700)
        for name, frame in (
            ("historical_privacy_audit.csv", historical.privacy_audit),
            ("current_cutoff_privacy_audit.csv", current.privacy_audit),
            ("historical_identity_audit.csv", historical.identity_audit),
            ("current_cutoff_identity_audit.csv", current.identity_audit),
            ("historical_reconciliation_audit.csv", historical.reconciliation_audit),
            ("current_cutoff_reconciliation_audit.csv", current.reconciliation_audit),
            ("historical_rejected.csv", historical.rejected),
            ("current_cutoff_rejected.csv", current.rejected),
            ("combined_record_selection_audit.csv", selection_audit),
        ):
            secure_write(frame, validation / name)

        summary = {
            "candidate_base": "03b939b48ac7da265666a49588d665b29d11aa49",
            "source_manifest": str(args.source_manifest),
            "cutoff_local_date": args.cutoff,
            "current_source_rows_after_cutoff": filtered_counts,
            "historical_events": len(historical.events),
            "current_cutoff_events": len(current.events),
            "combined_events": len(events),
            "historical_privacy_counts": historical.events.privacy_status.value_counts().to_dict(),
            "current_cutoff_privacy_counts": current.events.privacy_status.value_counts().to_dict(),
            "combined_privacy_counts": events.privacy_status.value_counts().to_dict(),
            "historical_rejected": len(historical.rejected),
            "current_cutoff_rejected": len(current.rejected),
            "partnership_record_rows": len(records),
            "record_selection_audit_pass": bool(selection_audit.validation_status.eq("PASS").all()),
            "outputs": {
                path.name: {"rows": len(frame), "sha256": sha256(path)}
                for path, frame in (
                    (args.output_dir / "partnerships.csv", events),
                    (args.output_dir / "partnership_records.csv", records),
                )
            },
            "restricted_validation_dir": str(validation),
        }
        summary_path = validation / "build_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        summary_path.chmod(0o600)
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
