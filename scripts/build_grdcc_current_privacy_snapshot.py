"""Build a redacted exact-ID privacy snapshot from restricted official receipts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.playcricket_public import format_player_name
from src.utils.player_identity import display_player_name


OUTPUT_COLUMNS = [
    "canonical_player_id_sha256",
    "source_participant_id_sha256",
    "status",
    "public_name",
    "verified_at",
    "source",
    "source_record_sha256",
    "source_payload_sha256",
]
PRIVATE_MARKERS = {
    "********",
    "private player",
    "anonymous player",
    "anonymised player",
    "anonymized player",
    "name withheld",
    "withheld",
}


def fingerprint(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Privacy snapshot identities must be non-empty")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def json_fingerprint(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def load_event_identity_targets(path: Path) -> dict[str, dict[str, object]]:
    import csv

    targets: dict[str, dict[str, object]] = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for event in csv.DictReader(handle):
            partners = [
                json.loads(event["current_partner_1"]),
                json.loads(event["current_partner_2"]),
            ]
            old_labels = [
                str(event["published_batter_1_label"]).strip(),
                str(event["published_batter_2_label"]).strip(),
            ]
            if event["status_transition"] == "PUBLIC_PUBLIC->PUBLIC_PRIVATE":
                changed = [
                    index
                    for index, partner in enumerate(partners)
                    if partner.get("current_private_flag") is True
                ]
            elif event["status_transition"] == "PUBLIC_PRIVATE->PUBLIC_PUBLIC":
                private_positions = [
                    index
                    for index, label in enumerate(old_labels)
                    if label.casefold() in PRIVATE_MARKERS
                ]
                if len(private_positions) != 1:
                    raise ValueError("Previously private event side is not uniquely identified")
                visible_label = old_labels[1 - private_positions[0]].casefold()
                visible_positions = [
                    index
                    for index, partner in enumerate(partners)
                    if str(partner.get("canonical_player_name", "")).strip().casefold()
                    == visible_label
                ]
                changed = [1 - visible_positions[0]] if len(visible_positions) == 1 else []
            else:
                continue

            if len(changed) != 1:
                raise ValueError("Every privacy transition must identify exactly one affected side")
            partner = partners[changed[0]]
            canonical_id = str(partner.get("canonical_player_id", "")).strip()
            participant_id = str(partner.get("participant_id", "")).strip()
            key = fingerprint(canonical_id)
            evidence = targets.setdefault(
                key,
                {
                    "canonical_player_id": canonical_id,
                    "participant_ids": set(),
                    "transitions": set(),
                },
            )
            evidence["participant_ids"].add(participant_id)
            evidence["transitions"].add(event["status_transition"])
    return targets


def build_rows(
    event_audit_path: Path,
    additional_event_review_path: Path,
    current_source_receipt_path: Path,
) -> list[dict[str, str]]:
    targets = load_event_identity_targets(event_audit_path)
    additional = json.loads(additional_event_review_path.read_text(encoding="utf-8"))
    for person in additional.get("current_source_participants", []):
        canonical_id = str(person.get("canonical_player_id", "")).strip()
        participant_id = str(person.get("participant_id", "")).strip()
        if not canonical_id or not participant_id:
            raise ValueError("Additional event participant is not mapped to exact source identity")
        key = fingerprint(canonical_id)
        target = targets.setdefault(
            key,
            {"canonical_player_id": canonical_id, "participant_ids": set(), "transitions": set()},
        )
        target["participant_ids"].add(participant_id)

    current = json.loads(current_source_receipt_path.read_text(encoding="utf-8"))
    rows_by_canonical: dict[str, dict[str, str]] = {}
    for source_row in current.get("privacy_statuses", []):
        canonical_hash = str(source_row.get("canonical_player_id_sha256", "")).strip()
        target = targets.get(canonical_hash)
        if not target:
            raise ValueError("Current privacy receipt contains an identity outside the reviewed event scope")
        participant_ids = set(target["participant_ids"])
        if len(participant_ids) != 1 or fingerprint(next(iter(participant_ids))) != source_row.get("source_participant_id_sha256"):
            raise ValueError("Current privacy status does not match the reviewed exact participant ID")

        status = str(source_row.get("status", "")).strip().casefold()
        public_name = str(source_row.get("public_name", "")).strip()
        source_record_hash = str(source_row.get("source_record_sha256", "")).strip()
        source_payload_hash = str(source_row.get("source_payload_sha256", "")).strip()
        verified_at = str(source_row.get("verified_at", "")).strip()
        source = str(source_row.get("source", "")).strip()
        if status not in {"public", "private"} or not verified_at or not source:
            raise ValueError("Current privacy receipt is incomplete or unresolved")
        if status == "public" and not public_name:
            raise ValueError("A current public exact-ID record needs a verified display name")
        if status == "private" and public_name:
            raise ValueError("Private source identities must not carry a public display name")
        if not re.fullmatch(r"[0-9a-f]{64}", source_record_hash) or not re.fullmatch(
            r"[0-9a-f]{64}", source_payload_hash
        ):
            raise ValueError("Current source evidence fingerprints are invalid")
        if canonical_hash in rows_by_canonical:
            raise ValueError("Duplicate canonical identity in current privacy receipt")
        rows_by_canonical[canonical_hash] = {
            "canonical_player_id_sha256": canonical_hash,
            "source_participant_id_sha256": source_row["source_participant_id_sha256"],
            "status": status,
            "public_name": public_name,
            "verified_at": verified_at,
            "source": source,
            "source_record_sha256": source_record_hash,
            "source_payload_sha256": source_payload_hash,
        }

    if set(rows_by_canonical) != set(targets):
        raise ValueError("Current privacy snapshot does not cover every exact-ID review target")
    return [rows_by_canonical[key] for key in sorted(rows_by_canonical)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event-audit", required=True, type=Path)
    parser.add_argument("--additional-event-review", required=True, type=Path)
    parser.add_argument("--current-source-receipt", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    rows = build_rows(args.event_audit, args.additional_event_review, args.current_source_receipt)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps({"snapshot_rows": len(rows), "statuses": dict(Counter(row["status"] for row in rows))}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
