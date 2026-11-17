"""Remove zero-activity GRDCC current partitions unsupported by exact scorecards.

This is a narrowly scoped post-refresh validation step, not a GRDCC candidate
builder. A zero aggregate row is removed only when all of its numeric cricket
metrics are zero and no official current scorecard identifies the same exact
participant and team. A scorecard-backed zero aggregate is left for explicit
source reconciliation and stops the operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
CLUB_ID = "georges-river-district"
DATA_DIR = ROOT / "clubs" / CLUB_ID / "data" / "processed"
CATEGORIES = ("batting", "bowling", "fielding")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"nan", "none", "null", "<na>"} else text


def _identity_candidates(row: pd.Series) -> set[str]:
    candidates = {
        _text(row.get(column, ""))
        for column in ("player_id", "raw_player_id", "canonical_player_id", "participant_id")
    }
    candidates.discard("")
    # Processed canonical IDs use the same slug form as default_canonical_id.
    candidates.update(f"raw_{re.sub(r'[^a-z0-9]+', '_', value.casefold()).strip('_')}" for value in list(candidates))
    candidates.discard("raw_")
    return candidates


def _scorecard_identity_index(scorecards: dict[str, pd.DataFrame]) -> set[tuple[str, str]]:
    index: set[tuple[str, str]] = set()
    for frame in scorecards.values():
        if not {"participant_id", "team_id"}.issubset(frame.columns):
            raise ValueError("Official scorecard source is missing participant_id or team_id")
        for row in frame[["participant_id", "team_id"]].itertuples(index=False, name=None):
            participant_id, team_id = map(_text, row)
            if not participant_id or not team_id:
                continue
            index.add((team_id, participant_id))
            slug = re.sub(r"[^a-z0-9]+", "_", participant_id.casefold()).strip("_")
            if slug:
                index.add((team_id, f"raw_{slug}"))
    return index


def _numeric_metrics_are_zero(row: pd.Series, category: str) -> bool:
    prefix = f"{category}"
    metric_columns = [
        column
        for column in row.index
        if str(column).startswith(prefix)
        and column not in {"battingHighScore", "bowlingBestInnings"}
    ]
    for column in metric_columns:
        value = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
        if pd.notna(value) and float(value) != 0:
            return False
    return True


def filter_zero_current_partitions(
    frames: dict[str, pd.DataFrame],
    scorecards: dict[str, pd.DataFrame],
    *,
    season: str,
) -> tuple[dict[str, pd.DataFrame], dict[str, Any]]:
    """Drop only current zero-stat keys with no exact scorecard participant."""
    if set(frames) != set(CATEGORIES) or set(scorecards) != set(CATEGORIES):
        raise ValueError("All three GRDCC stat and scorecard categories are required")
    scorecard_index = _scorecard_identity_index(scorecards)
    candidate_keys: set[tuple[str, str]] = set()
    candidate_hashes: set[str] = set()
    zero_rows_by_category: dict[str, int] = {}

    for category, frame in frames.items():
        if not {"season", "matches", "team_id"}.issubset(frame.columns):
            raise ValueError(f"{category} aggregate is missing required columns")
        current = frame.loc[frame["season"].astype(str).eq(season)]
        matches = pd.to_numeric(current["matches"], errors="coerce")
        zero = current.loc[matches.fillna(-1).eq(0)]
        zero_rows_by_category[category] = len(zero)
        for _, row in zero.iterrows():
            team_id = _text(row.get("team_id"))
            identities = _identity_candidates(row)
            if not team_id or not identities:
                raise ValueError(f"{category} has a zero-activity row without an exact team and identity key")
            if not _numeric_metrics_are_zero(row, category):
                raise ValueError(f"{category} has a zero-match row with non-zero cricket metrics")
            if any((team_id, identity) in scorecard_index for identity in identities):
                raise ValueError(
                    f"{category} has an exact scorecard participant with zero aggregate matches; reconcile figures before filtering"
                )
            candidate_keys.update((team_id, identity) for identity in identities)
            for identity in identities:
                candidate_hashes.add(hashlib.sha256(identity.encode("utf-8")).hexdigest())

    filtered: dict[str, pd.DataFrame] = {}
    removed_by_category: dict[str, int] = {}
    for category, frame in frames.items():
        current = frame["season"].astype(str).eq(season)
        zero = pd.to_numeric(frame["matches"], errors="coerce").fillna(-1).eq(0)
        remove = pd.Series(False, index=frame.index)
        for index, row in frame.loc[current & zero].iterrows():
            team_id = _text(row.get("team_id"))
            remove.loc[index] = any(
                (team_id, identity) in candidate_keys for identity in _identity_candidates(row)
            )
        filtered[category] = frame.loc[~remove].copy()
        removed_by_category[category] = int(remove.sum())

    receipt = {
        "club_id": CLUB_ID,
        "season": season,
        "source_identity_match_policy": "exact participant and team ID across official scorecards; no name joins",
        "zero_rows_before_by_category": zero_rows_by_category,
        "rows_removed_by_category": removed_by_category,
        "candidate_identity_fingerprints": sorted(candidate_hashes),
        "numeric_contributions_changed": False,
    }
    return filtered, receipt


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--season", required=True, help="Exact current-season label, such as Summer 2026/27")
    parser.add_argument("--source-dir", required=True, type=Path, help="Parsed official source bundle directory")
    parser.add_argument("--receipt", required=True, type=Path, help="Restricted receipt output path")
    parser.add_argument("--apply", action="store_true", help="Write filtered active-club stat tables")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    scorecards = {
        category: pd.read_csv(args.source_dir / f"all_scorecard_{category}.csv", dtype=str).fillna("")
        for category in CATEGORIES
    }
    paths = {category: DATA_DIR / f"all_seasons_{category}.csv" for category in CATEGORIES}
    frames = {category: pd.read_csv(path, low_memory=False).fillna("") for category, path in paths.items()}
    filtered, receipt = filter_zero_current_partitions(frames, scorecards, season=args.season)
    receipt["apply_requested"] = bool(args.apply)
    receipt["source_file_sha256"] = {
        category: _sha256(args.source_dir / f"all_scorecard_{category}.csv") for category in CATEGORIES
    }
    receipt["output_before_sha256"] = {category: _sha256(path) for category, path in paths.items()}
    receipt["output_rows_before"] = {category: len(frames[category]) for category in CATEGORIES}
    receipt["output_rows_after"] = {category: len(filtered[category]) for category in CATEGORIES}
    receipt["output_after_sha256"] = {}
    if args.apply:
        for category, path in paths.items():
            filtered[category].to_csv(path, index=False)
            receipt["output_after_sha256"][category] = _sha256(path)
    else:
        receipt["output_after_sha256"] = receipt["output_before_sha256"]
    args.receipt.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    args.receipt.chmod(0o600)
    print(json.dumps({k: v for k, v in receipt.items() if k != "candidate_identity_fingerprints"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
