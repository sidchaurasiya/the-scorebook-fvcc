"""Sanitize only the reviewed legacy-club fastest-milestone artifact paths.

This is not a club refresh. It removes non-person-unique invalid nil-UUID
participant values from four tracked legacy outputs, keeps numeric cells, and
unlinks same-match/name-only profile rows. Use --write only for a reviewed
local candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LEGACY_CLUBS = (
    "ashwood",
    "plenty",
    "reynella",
    "southside-east-caulfield",
)
FASTEST_RELATIVE = Path("data/processed/hall_of_fame/fastest_batting_milestones.csv")
LINK_RELATIVE = Path("data/processed/hall_of_fame/scorecard_record_links.csv")
PLACEHOLDER_ID_PATTERN = re.compile(r"^00000000-0000-0000-0000-0000000000[0-9]{2}$", re.IGNORECASE)
PLAYER_ID_COLUMNS = {
    "player_id",
    "participant_id",
    "raw_player_id",
    "canonical_player_id",
    "source_participant_id",
    "player_1_id",
    "player_2_id",
    "participant_1_id",
    "participant_2_id",
    "player_1_canonical_id",
    "player_2_canonical_id",
}
PLAYER_NAME_COLUMNS = {
    "player_name",
    "canonical_player_name",
    "display_player_name",
    "raw_player_name",
    "player_1_name",
    "player_2_name",
    "Player",
}
GENERIC_LABELS = {
    "********",
    "private player",
    "anonymous player",
    "anonymised player",
    "anonymized player",
    "masked player",
    "unknown",
    "unknown player",
    "name withheld",
    "withheld",
}


def _generic(value: object) -> bool:
    text = "" if value is None or pd.isna(value) else str(value).strip()
    return not text or text.casefold() in GENERIC_LABELS or set(text) <= {"*", "•"}


def _name_key(value: object) -> str:
    return " ".join(("" if value is None or pd.isna(value) else str(value)).casefold().split())


def _projection(rows: list[dict[str, str]], columns: list[str]) -> Counter[tuple[str, ...]]:
    return Counter(tuple(str(row.get(column, "") or "") for column in columns) for row in rows)


def _read(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    return list(frame.columns), frame.to_dict("records")


def _write(path: Path, columns: list[str], rows: list[dict[str, str]]) -> None:
    import csv

    temporary = path.with_name(f".{path.name}.privacy-tmp")
    with temporary.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def sanitize_legacy_public_milestones(repo_root: Path | str, *, write: bool = False) -> dict[str, object]:
    repo_root = Path(repo_root)
    report: dict[str, object] = {"clubs": {}, "write": write}
    for club_id in LEGACY_CLUBS:
        club_root = repo_root / "clubs" / club_id
        milestone_path = club_root / FASTEST_RELATIVE
        link_path = club_root / LINK_RELATIVE
        if not milestone_path.is_file():
            continue

        milestone_columns, milestone_rows = _read(milestone_path)
        identity_columns = [column for column in milestone_columns if column.casefold() in PLAYER_ID_COLUMNS]
        name_columns = [column for column in milestone_columns if column in PLAYER_NAME_COLUMNS or column.casefold() in PLAYER_NAME_COLUMNS]
        before_bytes = milestone_path.read_bytes()
        before_rows = [dict(row) for row in milestone_rows]
        link_keys: set[tuple[str, str]] = set()
        affected: list[int] = []

        for index, row in enumerate(milestone_rows):
            ids = [str(row.get(column, "")).strip() for column in identity_columns]
            matches_placeholder = any(PLACEHOLDER_ID_PATTERN.fullmatch(value) for value in ids)
            if not matches_placeholder:
                continue
            match_id = str(row.get("match_id", "")).strip()
            innings_id = str(row.get("innings_id", "")).strip()
            if not match_id:
                raise ValueError(f"Legacy anonymous milestone row lacks match_id: {milestone_path}")

            labels = [str(row.get(column, "")).strip() for column in name_columns if str(row.get(column, "")).strip()]
            for label in labels:
                # A generic source label must not keep a canonical profile ID
                # through a same-match link row.
                link_keys.add((match_id, _name_key(label)))

            for column in identity_columns:
                row[column] = ""
            if labels and any(not _generic(label) for label in labels):
                for column in name_columns:
                    row[column] = "Private player"
            affected.append(index)

        if link_path.is_file() and link_keys:
            link_columns, link_rows = _read(link_path)
            link_before = [dict(row) for row in link_rows]
            link_ids = [column for column in link_columns if column.casefold() in PLAYER_ID_COLUMNS]
            link_names = [column for column in link_columns if column in PLAYER_NAME_COLUMNS or column.casefold() in PLAYER_NAME_COLUMNS]
            link_changed: list[int] = []
            for index, row in enumerate(link_rows):
                match_id = str(row.get("match_id", "")).strip()
                if not any((match_id, _name_key(row.get(column, ""))) in link_keys for column in link_names):
                    continue
                for column in link_ids:
                    row[column] = ""
                for column in link_names:
                    row[column] = "Private player"
                link_changed.append(index)
            link_numeric = [column for column in link_columns if column not in set(link_ids) | set(link_names)]
            if _projection(link_before, link_numeric) != _projection(link_rows, link_numeric):
                raise ValueError(f"Legacy link numeric/context projection changed: {link_path}")
        else:
            link_columns, link_rows, link_before, link_changed = [], [], [], []
            link_numeric = []

        ignored = set(identity_columns) | set(name_columns)
        original_projection_columns = [column for column in before_rows[0] if column not in ignored] if before_rows else []
        if _projection(before_rows, original_projection_columns) != _projection(milestone_rows, original_projection_columns):
            raise ValueError(f"Legacy milestone numeric/context projection changed: {milestone_path}")

        after_bytes = milestone_path.read_bytes() if not write else b""
        if write:
            _write(milestone_path, milestone_columns, milestone_rows)
            after_bytes = milestone_path.read_bytes()
            if link_changed:
                _write(link_path, link_columns, link_rows)

        report["clubs"][club_id] = {
            "milestone_path": milestone_path.relative_to(repo_root).as_posix(),
            "milestone_rows_before": len(before_rows),
            "milestone_rows_after": len(milestone_rows),
            "anonymous_milestone_rows": len(affected),
            "same_match_profile_link_rows": len(link_changed),
            "link_rows_before": len(link_before),
            "link_rows_after": len(link_rows),
            "numeric_and_context_projection_equal": True,
            "before_sha256": hashlib.sha256(before_bytes).hexdigest(),
            "after_sha256": hashlib.sha256(after_bytes).hexdigest() if after_bytes else None,
            "link_path": link_path.relative_to(repo_root).as_posix() if link_path.is_file() else None,
            "link_projection_columns": link_numeric,
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--write", action="store_true", help="Write the scoped privacy correction.")
    args = parser.parse_args()
    print(json.dumps(sanitize_legacy_public_milestones(args.repo_root, write=args.write), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
