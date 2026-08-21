#!/usr/bin/env python3
"""Build governed GWHCC historical supplements from the customer workbook."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.player_identity import apply_player_identity_mapping, make_player_slug  # noqa: E402


CLUB_ID = "glen-waverley-hawks"
CLUB_ROOT = ROOT / "clubs" / CLUB_ID
PROCESSED = CLUB_ROOT / "data" / "processed"
SOURCE = CLUB_ROOT / "data" / "source" / "document_overrides"
VALIDATION = PROCESSED / "validation"
CENTURY_OUTPUT = SOURCE / "gwhcc_historical_centuries.csv"
CAREER_OUTPUT = SOURCE / "gwhcc_historical_career_metadata.csv"
PREMIERSHIP_OUTPUT = SOURCE / "gwhcc_historical_premiership_events.csv"
REVIEW_OUTPUT = VALIDATION / "gwhcc_customer_feedback_source_review.csv"

CENTURY_COLUMNS = [
    "record_id",
    "canonical_player_id",
    "canonical_player_name",
    "score",
    "not_out",
    "source_document",
    "source_sheet",
    "source_row",
    "confidence",
    "notes",
]
CAREER_COLUMNS = [
    "canonical_player_id",
    "canonical_player_name",
    "earliest_documented_season",
    "scope",
    "source_document",
    "source_sheet",
    "source_row",
    "confidence",
    "notes",
]
PREMIERSHIP_COLUMNS = [
    "event_id",
    "season",
    "grade_name",
    "team",
    "opponent",
    "result",
    "captain",
    "source_document",
    "source_sheet",
    "source_row",
    "confidence",
    "review_required",
    "notes",
]
REVIEW_COLUMNS = ["category", "source_sheet", "source_row", "source_name", "reason", "details"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def normalize_name(value: object) -> str:
    text = re.sub(r"\([^)]*\)", " ", str(value or ""))
    text = re.sub(r"[^a-z0-9]+", " ", text.casefold())
    return re.sub(r"\s+", " ", text).strip()


def initial_surname_key(value: object) -> str:
    text = re.sub(r"\([^)]*\)", " ", str(value or "")).strip()
    surname_first = re.match(r"^([A-Za-z'-]+)\s*\.\s*([A-Za-z])(?:\b|\.)", text)
    if surname_first:
        return f"{surname_first.group(2).casefold()} {normalize_name(surname_first.group(1))}"
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) < 2:
        return ""
    return f"{words[0][0].casefold()} {words[-1].casefold()}"


def load_identity_rows() -> pd.DataFrame:
    frames = []
    for category in ["batting", "bowling", "fielding"]:
        path = PROCESSED / f"all_seasons_{category}.csv"
        if not path.exists():
            continue
        frame = pd.read_csv(path, low_memory=False)
        if not frame.empty:
            frames.append(apply_player_identity_mapping(frame, club_id=CLUB_ID))
    if not frames:
        return pd.DataFrame(columns=["canonical_player_id", "canonical_player_name", "season"])
    return pd.concat(frames, ignore_index=True, sort=False)


class IdentityResolver:
    def __init__(self, identity: pd.DataFrame) -> None:
        rows = identity[["canonical_player_id", "canonical_player_name"]].dropna().drop_duplicates().copy()
        rows["name_key"] = rows["canonical_player_name"].map(normalize_name)
        rows["initial_key"] = rows["canonical_player_name"].map(initial_surname_key)
        self.by_name = unique_mapping(rows, "name_key")
        self.by_initial = unique_mapping(rows[rows["initial_key"].ne("")], "initial_key")
        self.document_aliases = load_document_aliases()

    def resolve(self, value: object) -> tuple[str, str] | None:
        name_key = normalize_name(value)
        alias_key = self.document_aliases.get(name_key, name_key)
        exact = self.by_name.get(alias_key)
        if exact:
            return exact
        return self.by_initial.get(initial_surname_key(value))


def unique_mapping(rows: pd.DataFrame, key_column: str) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for key, group in rows.groupby(key_column, dropna=False):
        key = str(key or "").strip()
        identities = group[["canonical_player_id", "canonical_player_name"]].drop_duplicates()
        if key and len(identities) == 1:
            row = identities.iloc[0]
            result[key] = str(row["canonical_player_id"]), str(row["canonical_player_name"])
    return result


def load_document_aliases() -> dict[str, str]:
    path = SOURCE / "gwhcc_document_player_aliases.csv"
    if not path.exists():
        return {}
    rows = pd.read_csv(path, dtype=str).fillna("")
    return {
        normalize_name(row["document_player_name"]): normalize_name(row["playcricket_player_name"])
        for _, row in rows.iterrows()
        if normalize_name(row.get("document_player_name")) and normalize_name(row.get("playcricket_player_name"))
    }


def score_tokens(value: object) -> list[tuple[int, bool]]:
    text = str(value or "")
    rows = []
    for match in re.finditer(r"(?<!\d)(\d{3})(?:\s*([x*])|\s*(ret))?", text, flags=re.IGNORECASE):
        rows.append((int(match.group(1)), bool(match.group(2) or match.group(3))))
    return rows


def counter_subset(left: Counter[int], right: Counter[int]) -> bool:
    return all(count <= right[value] for value, count in left.items())


def known_scorecard_centuries(identity: pd.DataFrame) -> dict[str, Counter[int]]:
    path = PROCESSED / "all_seasons_scorecard_batting.csv"
    if not path.exists():
        return {}
    rows = pd.read_csv(path, low_memory=False)
    rows = rows.drop_duplicates().copy()
    rows["raw_player_id"] = rows["player_id"]
    rows["raw_player_name"] = rows["player_name"]
    rows = apply_player_identity_mapping(rows, club_id=CLUB_ID)
    rows["score"] = pd.to_numeric(rows.get("runs"), errors="coerce")
    rows = rows[rows["score"].ge(100)]
    return {
        str(player_id): Counter(int(value) for value in group["score"].dropna())
        for player_id, group in rows.groupby("canonical_player_id")
    }


def known_aggregate_century_counts(identity: pd.DataFrame) -> dict[str, int]:
    if identity.empty or "batting100s" not in identity:
        return {}
    batting = identity[identity.get("batting100s", pd.Series(index=identity.index, dtype="object")).notna()].copy()
    batting["batting100s"] = pd.to_numeric(batting["batting100s"], errors="coerce").fillna(0)
    return {
        str(player_id): int(group["batting100s"].sum())
        for player_id, group in batting.groupby("canonical_player_id")
    }


def build_centuries(workbook: Path, resolver: IdentityResolver, identity: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    source = pd.read_excel(workbook, sheet_name="Centuries", header=2, dtype=object)
    grouped: dict[str, list[dict[str, object]]] = {}
    review: list[dict[str, str]] = []
    for index, row in source.iterrows():
        name = str(row.get("Player") or "").strip()
        scores = score_tokens(row.get("Scores / annotations (raw)"))
        if not name or not scores:
            continue
        resolved = resolver.resolve(name)
        if not resolved:
            review.append(review_row("century", "Centuries", index + 4, name, "identity_review_required", row.get("Scores / annotations (raw)")))
            continue
        player_id, player_name = resolved
        grouped.setdefault(player_id, []).append(
            {"name": name, "player_name": player_name, "row": index + 4, "scores": scores, "raw": row.get("Scores / annotations (raw)")}
        )

    known = known_scorecard_centuries(identity)
    aggregate_counts = known_aggregate_century_counts(identity)
    output: list[dict[str, object]] = []
    for player_id, candidates in grouped.items():
        candidates = sorted(candidates, key=lambda item: len(item["scores"]), reverse=True)
        selected = candidates[0]
        selected_counter = Counter(score for score, _ in selected["scores"])
        if any(not counter_subset(Counter(score for score, _ in candidate["scores"]), selected_counter) for candidate in candidates[1:]):
            review.append(review_row("century", "Centuries", selected["row"], selected["name"], "conflicting_score_lists", " | ".join(str(item["raw"]) for item in candidates)))
            continue
        remaining = known.get(player_id, Counter()).copy()
        required_supplements = max(len(selected["scores"]) - aggregate_counts.get(player_id, 0), 0)
        missing_scores: list[tuple[int, bool]] = []
        for score, not_out in selected["scores"]:
            if remaining[score] > 0:
                remaining[score] -= 1
            else:
                missing_scores.append((score, not_out))
        missing_scores = missing_scores[:required_supplements]
        ordinal: Counter[int] = Counter()
        for score, not_out in missing_scores:
            ordinal[score] += 1
            output.append(
                {
                    "record_id": f"hist_century_{make_player_slug(selected['player_name'])}_{score}_{ordinal[score]}",
                    "canonical_player_id": player_id,
                    "canonical_player_name": selected["player_name"],
                    "score": score,
                    "not_out": str(bool(not_out)).lower(),
                    "source_document": workbook.name,
                    "source_sheet": "Centuries",
                    "source_row": selected["row"],
                    "confidence": "high",
                    "notes": "Customer historical century absent from the de-duplicated Scorebook scorecard innings multiset; no season or match detail was invented.",
                }
            )
    return pd.DataFrame(output, columns=CENTURY_COLUMNS), review


def season_sort(value: object) -> tuple[int, int]:
    match = re.search(r"(\d{4})/(\d{2})", str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


def build_career_metadata(workbook: Path, resolver: IdentityResolver, identity: pd.DataFrame) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    source = pd.read_excel(workbook, sheet_name="First XI History", header=2, dtype=object)
    current = (
        identity.groupby(["canonical_player_id", "canonical_player_name"], as_index=False)
        .agg(current_debut=("season", lambda values: min((str(value) for value in values if str(value).strip()), key=season_sort, default="")))
    )
    current_by_id = current.set_index("canonical_player_id").to_dict("index")
    candidates: dict[str, dict[str, object]] = {}
    review: list[dict[str, str]] = []
    for index, row in source.iterrows():
        name = str(row.get("Source Name") or "").strip()
        first_game = str(row.get("First Game") or "").strip()
        season_match = re.search(r"(\d{4}/\d{2})", first_game)
        if not name or not season_match:
            continue
        resolved = resolver.resolve(name)
        if not resolved:
            review.append(review_row("career_start", "First XI History", index + 4, name, "identity_review_required", first_game))
            continue
        player_id, player_name = resolved
        season = f"Summer {season_match.group(1)}"
        current_debut = str(current_by_id.get(player_id, {}).get("current_debut") or "")
        if current_debut and season_sort(season) >= season_sort(current_debut):
            continue
        existing = candidates.get(player_id)
        if existing and season_sort(existing["earliest_documented_season"]) <= season_sort(season):
            continue
        candidates[player_id] = {
            "canonical_player_id": player_id,
            "canonical_player_name": player_name,
            "earliest_documented_season": season,
            "scope": "First XI documented debut",
            "source_document": workbook.name,
            "source_sheet": "First XI History",
            "source_row": index + 4,
            "confidence": "high",
            "notes": f"Earliest documented GWHCC First XI season; detailed season statistics remain available only from {current_debut or 'the reconstructed source coverage' }.",
        }
    return pd.DataFrame(candidates.values(), columns=CAREER_COLUMNS), review


def canonical_season(short: str) -> str:
    start, end = [int(value) for value in short.split("-")]
    start_year = 1900 + start if start >= 80 else 2000 + start
    return f"Summer {start_year:04d}/{end:02d}"


def valid_short_season(value: object) -> bool:
    text = str(value or "").strip()
    if not re.fullmatch(r"\d{2}-\d{2}", text):
        return False
    start, end = [int(part) for part in text.split("-")]
    return (start + 1) % 100 == end


def premiership_grade_key(value: object) -> str:
    text = normalize_name(value).replace("under ", "u ")
    if "t20" in text or "twenty20" in text:
        ordinal = re.search(r"(?:t20|twenty20)\s*(\d+)", text)
        return f"t20-{ordinal.group(1)}" if ordinal else "t20"
    if "wilson shield grade 2nds" in text or text == "ws2":
        return "ws2"
    if "howard wilson" in text or text == "ws":
        return "ws"
    if "one day a" in text or "a one" in text:
        return "a-one"
    if text == "one day":
        return "a-one"
    if "one day b" in text or "b one" in text:
        return "b-one"
    age_match = re.search(r"\bu\s*(12|13|14|16)", text)
    if age_match:
        age = f"u{age_match.group(1)}"
        adjacent = re.search(rf"\bu\s*{age_match.group(1)}([a-f])\b", text)
        standalone = re.search(rf"\bu\s*{age_match.group(1)}\b.*?\b([a-f])\b", text)
        suffix = adjacent.group(1) if adjacent else (standalone.group(1) if standalone else "")
        return age + suffix
    simple = re.fullmatch(r"([a-f])\s*(\d)?(?:\s*grade)?", text)
    if simple:
        return "".join(part for part in simple.groups() if part)
    return re.sub(r"\b(grade|players|overs|fri|friday|sat|saturday)\b", " ", text).strip()


def build_premiership_events(workbook: Path) -> tuple[pd.DataFrame, list[dict[str, str]]]:
    events = pd.read_excel(workbook, sheet_name="Premiership Events", header=2, dtype=object)
    current_summary = pd.read_excel(workbook, sheet_name="2025-26 Summary", header=None, dtype=object)
    review: list[dict[str, str]] = []
    candidates: list[dict[str, object]] = []
    for index, row in events.iterrows():
        short = str(row.get("Season Raw") or "").strip()
        grade = clean_source_grade(row.get("Grade/Team Raw"))
        if short == "25-26":
            continue
        if not valid_short_season(short) or not grade or not valid_source_grade(grade):
            review.append(review_row("premiership", "Premiership Events", index + 4, row.get("Player"), "malformed_or_ambiguous_event", row.get("Event Raw")))
            continue
        candidates.append(event_row(workbook, canonical_season(short), grade, "Premiership Events", index + 4))

    for index in range(25, 30):
        grade = current_summary_grade(current_summary.iat[index, 0])
        result = str(current_summary.iat[index, 1] or "").strip()
        if not grade:
            continue
        candidates.append(event_row(workbook, "Summer 2025/26", grade, "2025-26 Summary", index + 1, result=result))

    source_rows = pd.DataFrame(candidates)
    source_rows["_grade_key"] = source_rows["grade_name"].map(premiership_grade_key)
    for season, group in source_rows.groupby("season"):
        keys = set(group["_grade_key"])
        for age in ["u12", "u13", "u14", "u16"]:
            specific = sorted(key for key in keys if re.fullmatch(rf"{age}[a-z]", key))
            if age in keys and len(specific) == 1:
                mask = source_rows["season"].eq(season) & source_rows["_grade_key"].eq(age)
                source_rows.loc[mask, "_grade_key"] = specific[0]
    source_rows = source_rows.drop_duplicates(["season", "_grade_key"]).drop(columns="_grade_key")
    current_path = PROCESSED / "hall_of_fame" / "premiership_wins.csv"
    current = pd.read_csv(current_path, low_memory=False) if current_path.exists() else pd.DataFrame()
    existing = {
        (str(row.get("season") or ""), premiership_grade_key(row.get("grade_name")))
        for _, row in current.iterrows()
    }
    additions = []
    for _, row in source_rows.iterrows():
        key = (str(row["season"]), premiership_grade_key(row["grade_name"]))
        source_grade_key = key[1]
        generic_age_matches = {
            existing_key
            for existing_season, existing_key in existing
            if existing_season == key[0] and re.fullmatch(rf"{re.escape(source_grade_key)}[a-z]", existing_key)
        } if re.fullmatch(r"u(?:12|13|14|16)", source_grade_key) else set()
        if key in existing or len(generic_age_matches) == 1:
            continue
        additions.append(row.to_dict())
    return pd.DataFrame(additions, columns=PREMIERSHIP_COLUMNS), review


def clean_source_grade(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = re.sub(r"\s+", " ", str(value)).strip()
    text = re.sub(r"^U/\.(?=\d)", "U/", text, flags=re.IGNORECASE)
    return text


def valid_source_grade(value: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:[A-F](?:\d)?|WS2?|T20(?:\s*\(\d+\))?|One Day|A-One(?: Day)?|B-One|U/?(?:12|13|14|16)(?:[A-Z])?(?:\s*\((?:Blue|Gold)\))?)",
            value,
            flags=re.IGNORECASE,
        )
    )


def current_summary_grade(value: object) -> str:
    text = clean_source_grade(value)
    mapping = {
        "2nd xi": "C",
        "u/14b": "U/14B",
        "u/13 fischer": "U/13B",
        "u/12a": "U/12A",
        "u/12c gold": "U/12C",
    }
    return mapping.get(text.casefold(), text)


def event_row(workbook: Path, season: str, grade: str, sheet: str, row: int, *, result: str = "") -> dict[str, object]:
    grade = re.sub(r"\s+", " ", grade).strip()
    event_id = f"hist_prem_{season_sort(season)[0]}_{make_player_slug(grade)}"
    return {
        "event_id": event_id,
        "season": season,
        "grade_name": grade,
        "team": "Glen Waverley Hawks",
        "opponent": "",
        "result": result,
        "captain": "",
        "source_document": workbook.name,
        "source_sheet": sheet,
        "source_row": row,
        "confidence": "high",
        "review_required": "false",
        "notes": "Governed club-supplied historical premiership event; fields absent from the source remain blank.",
    }


def review_row(category: str, sheet: str, row: object, name: object, reason: str, details: object) -> dict[str, str]:
    return {
        "category": category,
        "source_sheet": sheet,
        "source_row": str(row),
        "source_name": str(name or ""),
        "reason": reason,
        "details": str(details or ""),
    }


def main() -> int:
    args = parse_args()
    if not args.workbook.exists():
        raise SystemExit(f"Workbook not found: {args.workbook}")
    identity = load_identity_rows()
    resolver = IdentityResolver(identity)
    centuries, century_review = build_centuries(args.workbook, resolver, identity)
    career, career_review = build_career_metadata(args.workbook, resolver, identity)
    premierships, premiership_review = build_premiership_events(args.workbook)
    review = pd.DataFrame(century_review + career_review + premiership_review, columns=REVIEW_COLUMNS)
    print(f"Historical century supplements: {len(centuries)}")
    print(f"Historical career starts: {len(career)}")
    print(f"Historical premiership events: {len(premierships)}")
    print(f"Review rows: {len(review)}")
    if args.dry_run:
        return 0
    SOURCE.mkdir(parents=True, exist_ok=True)
    VALIDATION.mkdir(parents=True, exist_ok=True)
    centuries.to_csv(CENTURY_OUTPUT, index=False)
    career.to_csv(CAREER_OUTPUT, index=False)
    premierships.to_csv(PREMIERSHIP_OUTPUT, index=False)
    review.to_csv(REVIEW_OUTPUT, index=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
