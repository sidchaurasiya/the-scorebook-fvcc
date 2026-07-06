#!/usr/bin/env python3
"""Refresh GWHCC app-facing data from existing local PlayHQ/PlayCricket pulls."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.data.gwhcc_match_policy import CLUB_ID, apply_hawks_match_policy_to_app_data  # noqa: E402
from src.data.gwhcc_document_overrides import extract_documents  # noqa: E402


def run_script(name: str, *args: str) -> None:
    command = [sys.executable, str(ROOT / "scripts" / name), *args]
    print(f"Running: {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


def main() -> int:
    print("GWHCC app-data refresh from existing local PlayHQ/PlayCricket data")
    print(f"- club_id: {CLUB_ID}")
    print("- external fetch: no")

    run_script("build_club_app_facing_scorecards.py", "--club", CLUB_ID)
    run_script("build_match_centre_milestones.py", "--club", CLUB_ID)

    policy_result = apply_hawks_match_policy_to_app_data()
    print("Applied Hawks match-count policy")
    for item in policy_result.get("files", []):
        print(f"- {item['path']}: rows={item['rows']:,} matches {item['matches_before']:.1f} -> {item['matches_after']:.1f}")

    run_script("refresh_club_outputs.py", "--club", CLUB_ID)
    apply_hawks_match_policy_to_app_data()
    extraction = extract_documents()
    print(
        "Applied Hawks document override extraction "
        f"(raw_files={extraction['raw_files']}, record_overrides={extraction['record_overrides']}, "
        f"premierships={extraction['premierships']})"
    )
    run_script("audit_gwhcc_playhq_season_coverage.py")
    run_script("validate_gwhcc_match_count_policy.py")
    run_script("export_gwhcc_matches_needing_review.py")
    run_script("validate_gwhcc_data_governance.py")
    run_script("validate_gwhcc_document_overrides.py")
    run_script("validate_gwhcc_template_application.py")
    print("GWHCC refresh complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
