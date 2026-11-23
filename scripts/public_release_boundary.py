"""Enforce the club data boundary in the public Scorebook checkout."""

import argparse
import base64
import html
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
from urllib.parse import unquote
from zipfile import ZipFile


GRDCC = "georges-river-district"
MARKER = ".scorebook-public-repository"
ROOT = Path(__file__).resolve().parents[1]


def require_artifact_destination(club: str, root: Path = ROOT) -> None:
    if club == GRDCC and (root / MARKER).is_file():
        raise ValueError("Build GRDCC artifacts in its private deployment checkout")


def is_private_grdcc_path(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if parts[:2] == ("clubs", GRDCC) and len(parts) > 2:
        return parts[2] in {"data", "prepared_views", "player_aliases.csv", "manual_player_merges.csv"}
    return len(parts) > 2 and parts[:2] == ("tests", "fixtures") and parts[2].startswith("grdcc_")


def validate_tree(root: Path, ref: str) -> list[str]:
    paths = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", "-z", ref], cwd=root,
    ).decode().split("\0")
    if MARKER not in paths:
        raise ValueError("Public checkout marker is missing from the release tree")
    return sorted(path for path in paths if is_private_grdcc_path(path))


def protected_pattern(values: list[str]) -> re.Pattern:
    if not values or any(not isinstance(value, str) or len(value.strip()) < 8 for value in values):
        raise ValueError("Use a verified nonempty set of full names or exact identity tokens")
    variants = set()
    for value in values:
        value = value.strip()
        variants.update((value, value.replace("-", "_"), re.sub(r"\s+", "-", value)))
        if re.fullmatch(r"[a-zA-Z0-9_-]{16,}", value):
            variants.add(re.sub(r"[-_]", "", value))
            variants.add(base64.urlsafe_b64encode(value.encode()).decode().rstrip("="))
            variants.add(base64.b64encode(value.encode()).decode().rstrip("="))
    return re.compile("|".join(re.escape(value) for value in sorted(variants)), re.IGNORECASE)


def scan_content(data: bytes, protected: re.Pattern) -> tuple[bool, int]:
    """Inspect encoded identifiers and recursively inspect ZIP names and content."""
    if data.startswith(b"PK\x03\x04"):
        hit = False
        count = 0
        with ZipFile(io.BytesIO(data)) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                found, nested = scan_content(archive.read(member), protected)
                hit |= found or protected.search(unquote(member.filename)) is not None
                count += nested + 1
        return hit, count
    text = html.unescape(unquote(data.decode(errors="replace")))
    text = re.sub(r"\\u([0-9a-fA-F]{4})", lambda code: chr(int(code[1], 16)), text)
    return protected.search(text) is not None, 0


def scan_tree(root: Path, ref: str, protected: re.Pattern) -> dict:
    tree = subprocess.check_output(["git", "ls-tree", "-r", "-z", ref], cwd=root)
    failures = []
    member_count = 0
    count = 0
    with subprocess.Popen(["git", "cat-file", "--batch"], cwd=root,
                          stdin=subprocess.PIPE, stdout=subprocess.PIPE) as reader:
        for row in tree.split(b"\0"):
            if not row:
                continue
            info, path = row.split(b"\t", 1)
            _, kind, oid = info.split()
            if kind != b"blob":
                continue
            reader.stdin.write(oid + b"\n")
            reader.stdin.flush()
            obj, blob, size = reader.stdout.readline().split()
            if obj != oid or blob != kind:
                raise ValueError("Could not inspect an exact public Git blob")
            data = reader.stdout.read(int(size))
            if len(data) != int(size) or reader.stdout.read(1) != b"\n":
                raise ValueError("Public Git blob read was incomplete")
            found, members = scan_content(data, protected)
            count += 1
            member_count += members
            if found or protected.search(unquote(path.decode())):
                failures.append(path.decode())
        reader.stdin.close()
    return {"files": count, "archive_members": member_count, "restricted_identity_paths": failures}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ref", nargs="?", default="HEAD")
    parser.add_argument("--protected-identities", type=Path, help="Local restricted JSON array of verified tokens")
    parser.add_argument("--receipt", type=Path, help="Write the private scan result to this file")
    args = parser.parse_args()
    blocked = validate_tree(ROOT, args.ref)
    scan = None
    if args.protected_identities:
        scan = scan_tree(ROOT, args.ref, protected_pattern(json.loads(args.protected_identities.read_text())))
        print(f'Restricted identity scan verified {scan["files"]} files and {scan["archive_members"]} archive members')
    if args.receipt:
        args.receipt.write_text(json.dumps({"ref": args.ref, "blocked_data_paths": blocked, "privacy": scan}, indent=2) + "\n")
    if blocked:
        print(f"Public release includes {len(blocked)} blocked GRDCC data paths")
        return 1
    if scan and scan["restricted_identity_paths"]:
        print(f'Public release includes {len(scan["restricted_identity_paths"])} restricted identity paths')
        return 1
    print("Public GRDCC data boundary verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
