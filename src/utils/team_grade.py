from __future__ import annotations

import os
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
    "b grade john adams shield",
    "c grade les horne shield",
    "d grade bob herman shield",
    "e grade les kemp shield",
    "f grade syd sault shield",
    "f grade north dave manion shield",
    "f grade south harry torrens shield",
    "f grade central",
    "g grade",
    "casey radcliffe shield",
    "dodc casey radcliffe shield",
    "dodc robert young shield",
    "north division winter",
    "north division bhatia shield winter",
    "north division sunday winter",
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
    from src.config.club_config import get_feature_flag

    label = clean_label(value)
    label = strip_leading_association(label)
    label = re.sub(r"^\d+\s*[-–]\s*", "", label).strip()
    label = label.replace("Designated One Day Comp.", "DODC")
    label = canonicalize_grade_label(normalize_spaces(label))
    if active_club_id() == "georges-river-district" and get_feature_flag(
        "enable_grade_opponent_normalisation",
        False,
        club_id="georges-river-district",
    ):
        return canonicalize_grdcc_grade_label(label)
    if active_club_id() == "glen-waverley-hawks" and get_feature_flag(
        "enable_grade_opponent_normalisation",
        False,
        club_id="glen-waverley-hawks",
    ):
        return canonicalize_gwhcc_grade_label(label)
    return label


def canonicalize_grade_label(label: str) -> str:
    normalized = normalized_name_without_canonical(label)
    grade_aliases = {
        "b grade": "B Grade - John Adams Shield",
        "john adams shield b grade": "B Grade - John Adams Shield",
        "c grade": "C Grade - Les Horne Shield",
        "les horne shield c grade": "C Grade - Les Horne Shield",
        "d grade": "D Grade - Bob Herman Shield",
        "bob herman shield d grade": "D Grade - Bob Herman Shield",
        "e grade": "E Grade - Les Kemp Shield",
        "les kemp shield e grade": "E Grade - Les Kemp Shield",
        "f grade": "F Grade Central",
        "syd sault shield f grade": "F Grade - Syd Sault Shield",
        "f grade north manion shield": "F Grade North - Dave Manion Shield",
        "f grade south torrens shield": "F Grade South - Harry Torrens Shield",
        "robert young dodc": "DODC - Robert Young Shield",
        "robert young designated one day comp": "DODC - Robert Young Shield",
        "north division": "North Division (Winter)",
        "north division winter": "North Division (Winter)",
        "north division bhatia shield": "North Division - Bhatia Shield (Winter)",
        "north division bhatia shield winter": "North Division - Bhatia Shield (Winter)",
        "north division sunday": "North Division - SUNDAY (Winter)",
        "north division sunday winter": "North Division - SUNDAY (Winter)",
    }
    return grade_aliases.get(normalized, label)


def canonicalize_grdcc_grade_label(label: str) -> str:
    normalized = normalized_name_without_canonical(label)
    if not normalized:
        return label

    grade_aliases = {
        "1st grade": "First Grade The RB Clark Cup",
        "first grade": "First Grade The RB Clark Cup",
        "grdcc 1st grade": "First Grade The RB Clark Cup",
        "first grade the rb clark cup": "First Grade The RB Clark Cup",
        "2nd grade": "Second Grade The SJ Mayne Trophy",
        "second grade": "Second Grade The SJ Mayne Trophy",
        "grdcc 2nd grade": "Second Grade The SJ Mayne Trophy",
        "second grade the sj mayne trophy": "Second Grade The SJ Mayne Trophy",
        "3rd grade": "Third Grade The JB Hollander Cup",
        "third grade": "Third Grade The JB Hollander Cup",
        "grdcc 3rd grade": "Third Grade The JB Hollander Cup",
        "third grade the jb hollander cup": "Third Grade The JB Hollander Cup",
        "4th grade": "Fourth Grade The Harry Culbert Trophy",
        "fourth grade": "Fourth Grade The Harry Culbert Trophy",
        "grdcc 4th grade": "Fourth Grade The Harry Culbert Trophy",
        "fourth grade the harry culbert trophy": "Fourth Grade The Harry Culbert Trophy",
        "5th grade": "Fifth Grade The Tim Creer Cup",
        "fifth grade": "Fifth Grade The Tim Creer Cup",
        "grdcc 5th grade": "Fifth Grade The Tim Creer Cup",
        "fifth grade the tim creer cup": "Fifth Grade The Tim Creer Cup",
        "tim creer cup": "Fifth Grade The Tim Creer Cup",
        "tim creer cup 5th grade": "Fifth Grade The Tim Creer Cup",
        "tim creer cup a division": "Fifth Grade The Tim Creer Cup",
        "frank gray shield": "Frank Gray Shield",
        "grdcc fgs": "Frank Gray Shield",
        "frank gray shield thunder conference": "Frank Gray Shield",
        "frank gray shield u 24 s": "Frank Gray Shield",
        "frank gray shield u24 s": "Frank Gray Shield",
        "frank gray shield u24s": "Frank Gray Shield",
        "under 24 s": "Frank Gray Shield",
        "first grade limited overs": "First Grade Limited Overs",
        "georges river 1st grade l o": "First Grade Limited Overs",
        "nsw community cup": "NSW Community Cup",
        "nsw community cup 2023 24": "NSW Community Cup",
        "nsw community cup 2024 25": "NSW Community Cup",
        "masters": "Masters",
        "grdcc masters": "Masters",
        "sydney masters over 40 s": "Masters",
        "sydney masters over 40s": "Masters",
        "vintage": "Vintage / Over 60s",
        "grdcc vintage": "Vintage / Over 60s",
        "gr vintage": "Vintage / Over 60s",
        "sydney vintage over 60 s competition": "Vintage / Over 60s",
        "sydney vintage over 60s competition": "Vintage / Over 60s",
        "o60s regionals": "Vintage / Over 60s",
        "regional o60s": "Vintage / Over 60s",
        "regionals mens o60s": "Vintage / Over 60s",
        "regionals mens o60s thomas latto trophy": "Vintage / Over 60s",
        "o60s thomas latto trophy": "Vintage / Over 60s",
        "nsw o60s regional": "Vintage / Over 60s",
        "classics": "Classics",
        "grdcc classics": "Classics",
        "classics owls": "Classics OWLS",
        "masters owls": "Masters OWLS",
        "classics foxs": "Classics FOXS",
    }
    return grade_aliases.get(normalized, label)


def canonicalize_gwhcc_grade_label(label: str) -> str:
    try:
        from src.data.gwhcc_governance import display_grade_name, mapping_lookup

        mapping = mapping_lookup().get(clean_label(label))
        if mapping:
            return str(mapping.get("display_grade_name") or label)
        return display_grade_name(label) or label
    except Exception:
        pass
    return label


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
        if comparison_key(" - ".join(parts[-half:])) in comparison_key(" - ".join(parts[:-half])):
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
    if active_club_id() == "glen-waverley-hawks":
        try:
            from src.data.gwhcc_governance import mapping_lookup

            mapping = mapping_lookup().get(clean_label(extract_grade_for_sort(value))) or mapping_lookup().get(label)
            if mapping:
                return (int(float(mapping.get("display_order") or 999)), label.casefold())
        except Exception:
            pass
    for index, grade in enumerate(GRADE_ORDER):
        if normalized == grade:
            return (index, label.casefold())
    for index, grade in enumerate(GRADE_ORDER):
        if grade in normalized:
            return (index, label.casefold())
    return (len(GRADE_ORDER), label.casefold())


def extract_grade_for_sort(value: object) -> str:
    label = str(value or "").strip()
    if not label:
        return ""
    bracket_match = re.search(r"\(([^)]*)\)", label)
    if bracket_match and bracket_match.group(1).strip().casefold() != "winter":
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

    if active_club_id() == "glen-waverley-hawks":
        pair_values: dict[tuple[str, str], tuple[str, str, str, str, str]] = {}
        row_values = []
        for team_name, grade_name in zip(output["team_name"], output["grade_name"]):
            pair_key = (clean_label(team_name), clean_label(grade_name))
            values = pair_values.get(pair_key)
            if values is None:
                clean_team = clean_team_name(team_name)
                clean_grade = clean_grade_name(grade_name)
                values = (
                    clean_team,
                    clean_grade,
                    canonical_team_label(clean_team),
                    canonical_grade_label(clean_team, clean_grade),
                    build_team_grade_display(team_name, grade_name),
                )
                pair_values[pair_key] = values
            row_values.append(values)
        (
            output["clean_team_name"],
            output["clean_grade_name"],
            output["canonical_team_label"],
            output["canonical_grade_label"],
            output["team_grade_display"],
        ) = map(list, zip(*row_values))
        return output

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
    label = canonicalize_grade_label(label)
    label = re.sub(r"[^a-z0-9]+", " ", label.casefold())
    return normalize_spaces(label)


def normalized_name_without_canonical(value: object) -> str:
    label = clean_label(value)
    label = strip_leading_association(label)
    return comparison_key(label)


def comparison_key(value: object) -> str:
    label = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return normalize_spaces(label)


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def active_club_id() -> str:
    try:
        from src.config.club_config import get_active_club_id

        return get_active_club_id()
    except Exception:
        return str(os.getenv("CLUB_ID", "fvcc")).strip().casefold().replace(" ", "-") or "fvcc"
