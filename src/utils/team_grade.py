from __future__ import annotations

import re
from pathlib import Path

import pandas as pd


AUDIT_PATH = Path("data/team_grade_display_audit.csv")


TEAM_ALIASES = {
    "fvcc 1st": "1s",
    "fvcc 1": "1s",
    "first xi": "1s",
    "1st xi": "1s",
    "fvcc 2nd": "2s",
    "fvcc 2": "2s",
    "second xi": "2s",
    "2nd xi": "2s",
    "fvcc 3rd": "3s",
    "fvcc 3": "3s",
    "third xi": "3s",
    "3rd xi": "3s",
    "fvcc 4th": "4s",
    "fvcc 4": "4s",
    "fourth xi": "4s",
    "4th xi": "4s",
}

REAL_TEAM_LABELS = {"1s", "2s", "3s", "4s", "5s", "od", "winter", "veterans", "vets"}
GRADE_WORDS = ("shield", "grade", "division", "association", "nmca", "competition", "comp.")
GRADE_ORDER = [
    "jika shield",
    "jack quick shield",
    "jack kelly shield",
    "b grade",
    "c grade",
    "d grade",
    "e grade",
    "f grade",
    "g grade",
]


def clean_team_name(value: object) -> str:
    label = clean_label(value)
    if not label:
        return ""
    lowered = label.casefold()
    if lowered in TEAM_ALIASES:
        return TEAM_ALIASES[lowered]
    label = re.sub(r"\bFVCC\s+1st\b", "1s", label, flags=re.IGNORECASE)
    label = re.sub(r"\bFVCC\s+2nd\b", "2s", label, flags=re.IGNORECASE)
    label = re.sub(r"\bFVCC\s+3rd\b", "3s", label, flags=re.IGNORECASE)
    label = re.sub(r"\bFVCC\s+4th\b", "4s", label, flags=re.IGNORECASE)
    label = re.sub(r"\bFirst\s+XI\b", "1s", label, flags=re.IGNORECASE)
    label = re.sub(r"\bSecond\s+XI\b", "2s", label, flags=re.IGNORECASE)
    label = re.sub(r"\bThird\s+XI\b", "3s", label, flags=re.IGNORECASE)
    label = re.sub(r"\bFourth\s+XI\b", "4s", label, flags=re.IGNORECASE)
    label = label.replace("Fiji Victorian CC", "").strip()
    label = re.sub(r"^1st\b", "1s", label, flags=re.IGNORECASE)
    label = re.sub(r"^2nd\b", "2s", label, flags=re.IGNORECASE)
    label = re.sub(r"^3rd\b", "3s", label, flags=re.IGNORECASE)
    label = re.sub(r"^4th\b", "4s", label, flags=re.IGNORECASE)
    label = re.sub(r"^5th\b", "5s", label, flags=re.IGNORECASE)
    label = re.sub(r"\bWinter\s+XI\b", "Winter", label, flags=re.IGNORECASE)
    label = re.sub(r"\bOD\s+XI\b", "OD", label, flags=re.IGNORECASE)
    label = re.sub(r"\s+XI$", "", label, flags=re.IGNORECASE)
    return normalize_spaces(label)


def clean_grade_name(value: object) -> str:
    label = clean_label(value)
    label = strip_leading_association(label)
    label = re.sub(r"^\d+\s*[-–]\s*", "", label).strip()
    label = label.replace("Designated One Day Comp.", "DODC")
    return normalize_spaces(label)


def clean_label(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    label = str(value).strip()
    if not label or label.casefold() in {"nan", "none", "—"}:
        return ""
    label = label.replace('""', '"').replace("''", "'")
    label = label.replace('"', "").replace("'", "")
    label = re.sub(r"\(([^)]*)\)", lambda match: f" {match.group(1)} ", label)
    label = normalize_spaces(label)
    label = remove_duplicate_tail(label)
    return normalize_spaces(label)


def remove_duplicate_tail(label: str) -> str:
    # Handles values such as "NMCA - Les Kemp Shield - E Grade (Les Kemp Shield - E Grade)"
    # after brackets have been flattened into a repeated trailing phrase.
    parts = [part.strip() for part in label.split(" - ") if part.strip()]
    if len(parts) >= 4:
        half = len(parts) // 2
        if normalized_name(" - ".join(parts[-half:])) in normalized_name(" - ".join(parts[:-half])):
            return " - ".join(parts[:-half])
    return label


def strip_leading_association(label: str) -> str:
    label = re.sub(r"^NMCA\s*-\s*", "", label, flags=re.IGNORECASE).strip()
    return label


def is_real_team_name(value: object) -> bool:
    label = clean_team_name(value)
    if not label:
        return False
    lowered = label.casefold()
    if lowered in REAL_TEAM_LABELS:
        return True
    if re.fullmatch(r"[1-9]s", lowered):
        return True
    if any(word in lowered for word in GRADE_WORDS):
        return False
    return bool(re.fullmatch(r"(fvcc\s*)?[1-9](st|nd|rd|th)?", lowered))


def is_grade_like(value: object) -> bool:
    label = clean_label(value).casefold()
    return bool(label and any(word in label for word in GRADE_WORDS))


def canonical_team_label(value: object) -> str:
    label = clean_team_name(value)
    return label if is_real_team_name(label) else ""


def canonical_grade_label(team_name: object, grade_name: object | None = None) -> str:
    grade = clean_grade_name(grade_name)
    team = clean_team_name(team_name)
    if grade:
        return grade
    if is_grade_like(team):
        return strip_leading_association(team)
    return ""


def names_are_equivalent(a: object, b: object) -> bool:
    left = normalized_name(a)
    right = normalized_name(b)
    if not left or not right:
        return False
    if left == right:
        return True
    if min(len(left), len(right)) < 4:
        return False
    return left in right or right in left


def build_team_grade_display(team_name: object, grade_name: object) -> str:
    clean_team = clean_team_name(team_name)
    clean_grade = clean_grade_name(grade_name)
    team_label = canonical_team_label(clean_team)
    grade_label = canonical_grade_label(clean_team, clean_grade)

    if team_label and grade_label and not names_are_equivalent(team_label, grade_label):
        return f"{team_label} ({grade_label})"
    if team_label and not grade_label:
        return team_label
    if grade_label:
        return grade_label
    return clean_team or clean_grade or "—"


def grade_sort_key(value: object) -> tuple[int, str]:
    label = clean_grade_name(extract_grade_for_sort(value))
    normalized = normalized_name(label)
    for index, grade in enumerate(GRADE_ORDER):
        if normalized == grade or grade in normalized:
            return (index, label.casefold())
    return (len(GRADE_ORDER), label.casefold())


def extract_grade_for_sort(value: object) -> str:
    label = str(value or "").strip()
    if not label:
        return ""
    bracket_match = re.search(r"\(([^)]*)\)", label)
    if bracket_match:
        return bracket_match.group(1)
    if re.fullmatch(r"[1-9]s", label.casefold()) or label.casefold() in REAL_TEAM_LABELS:
        return label
    return label


def apply_team_grade_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    output = df.copy()
    if "team_name" in output and "raw_team_name" not in output:
        output["raw_team_name"] = output["team_name"]
    if "grade_name" in output and "raw_grade_name" not in output:
        output["raw_grade_name"] = output["grade_name"]
    if "team_name" not in output:
        output["team_name"] = ""
    if "grade_name" not in output:
        output["grade_name"] = ""

    output["clean_team_name"] = output["team_name"].map(clean_team_name)
    output["clean_grade_name"] = output["grade_name"].map(clean_grade_name)
    output["canonical_team_label"] = output.apply(lambda row: canonical_team_label(row["clean_team_name"]), axis=1)
    output["canonical_grade_label"] = output.apply(
        lambda row: canonical_grade_label(row["clean_team_name"], row["clean_grade_name"]),
        axis=1,
    )
    output["team_grade_display"] = output.apply(
        lambda row: build_team_grade_display(row["team_name"], row["grade_name"]),
        axis=1,
    )
    return output


def export_team_grade_display_audit(frames: list[pd.DataFrame], path: Path = AUDIT_PATH) -> None:
    rows = []
    for frame in frames:
        if frame.empty:
            continue
        display = apply_team_grade_display_columns(frame)
        columns = [
            "raw_team_name",
            "raw_grade_name",
            "clean_team_name",
            "clean_grade_name",
            "canonical_team_label",
            "canonical_grade_label",
            "team_grade_display",
            "season",
        ]
        for column in columns:
            if column not in display:
                display[column] = ""
        rows.append(display[columns])
    if not rows:
        return
    audit = pd.concat(rows, ignore_index=True).drop_duplicates().sort_values(
        ["season", "raw_team_name", "raw_grade_name"],
        na_position="last",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    audit.to_csv(path, index=False)


def normalized_name(value: object) -> str:
    label = clean_label(value)
    label = strip_leading_association(label)
    label = re.sub(r"[^a-z0-9]+", " ", label.casefold())
    return normalize_spaces(label)


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()
