"""Hawks document override layer for records and premiership supplements."""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pandas as pd

from src.data.gwhcc_match_policy import PROCESSED, read_csv

CLUB_ID = "glen-waverley-hawks"
ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "clubs" / CLUB_ID / "data" / "source" / "document_overrides"
RAW_DIR = SOURCE_ROOT / "raw"
EXTRACTED_DIR = SOURCE_ROOT / "extracted"
REVIEW_DIR = SOURCE_ROOT / "review"
VALIDATION_DIR = PROCESSED / "validation"

RECORD_OVERRIDES = SOURCE_ROOT / "gwhcc_record_overrides.csv"
PREMIERSHIPS = SOURCE_ROOT / "gwhcc_premierships.csv"
PREMIERSHIP_PLAYERS = SOURCE_ROOT / "gwhcc_premiership_players.csv"
DECISIONS = VALIDATION_DIR / "gwhcc_document_override_decisions.csv"
VALIDATION = VALIDATION_DIR / "gwhcc_document_override_validation.csv"

RECORD_COLUMNS = ["player_name", "metric", "document_value", "source_document", "confidence", "notes"]
PREMIERSHIP_COLUMNS = [
    "season",
    "grade_name",
    "team",
    "opponent",
    "result",
    "captain",
    "source_document",
    "confidence",
    "review_required",
    "notes",
]
PREMIERSHIP_PLAYER_COLUMNS = ["season", "grade_name", "player_name", "source_document", "confidence", "notes"]
DECISION_COLUMNS = [
    "player_name",
    "metric",
    "playcricket_value",
    "document_value",
    "display_value",
    "display_source",
    "override_applied",
    "confidence",
    "notes",
]

METRIC_TO_COLUMN = {
    "matches": "Matches",
    "games": "Matches",
    "runs": "Runs",
    "wickets": "Wickets",
    "catches": "Catches",
}


def ensure_document_override_dirs() -> None:
    for path in [RAW_DIR, EXTRACTED_DIR, REVIEW_DIR, VALIDATION_DIR]:
        path.mkdir(parents=True, exist_ok=True)


def document_override_signature() -> tuple[tuple[str, float], ...]:
    paths = [RECORD_OVERRIDES, PREMIERSHIPS, PREMIERSHIP_PLAYERS]
    return tuple((str(path), path.stat().st_mtime) for path in paths if path.exists())


def normalize_name(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


def numeric_value(value: object) -> float | None:
    number = pd.to_numeric(value, errors="coerce")
    if pd.isna(number):
        return None
    return float(number)


def write_empty_source_files() -> None:
    ensure_document_override_dirs()
    for path, columns in [
        (RECORD_OVERRIDES, RECORD_COLUMNS),
        (PREMIERSHIPS, PREMIERSHIP_COLUMNS),
        (PREMIERSHIP_PLAYERS, PREMIERSHIP_PLAYER_COLUMNS),
    ]:
        if not path.exists():
            pd.DataFrame(columns=columns).to_csv(path, index=False)


def load_record_overrides() -> pd.DataFrame:
    write_empty_source_files()
    frame = read_csv(RECORD_OVERRIDES)
    for column in RECORD_COLUMNS:
        if column not in frame:
            frame[column] = ""
    frame["metric_key"] = frame["metric"].map(lambda value: normalize_name(value).replace(" ", "_"))
    frame["metric_key"] = frame["metric_key"].replace({"game": "games", "match": "matches"})
    frame["document_value"] = pd.to_numeric(frame["document_value"], errors="coerce")
    return frame[RECORD_COLUMNS + ["metric_key"]].dropna(subset=["document_value"])


def apply_record_overrides(all_time: pd.DataFrame, *, write_decisions: bool = True) -> pd.DataFrame:
    if all_time.empty or "Player" not in all_time:
        return all_time
    overrides = load_record_overrides()
    output = all_time.copy()
    decisions: list[dict[str, object]] = []
    if overrides.empty:
        if write_decisions:
            write_decision_rows(decisions)
        return output

    output["_player_key_for_doc_override"] = output["Player"].map(normalize_name)
    for _, override in overrides.iterrows():
        metric_key = str(override.get("metric_key") or "").strip()
        column = METRIC_TO_COLUMN.get(metric_key)
        if not column or column not in output:
            continue
        player_key = normalize_name(override.get("player_name"))
        document_value = numeric_value(override.get("document_value"))
        if not player_key or document_value is None:
            continue
        mask = output["_player_key_for_doc_override"].eq(player_key)
        if not mask.any():
            decisions.append(decision_row(override, metric_key, None, document_value, document_value, "missing_from_playcricket", False))
            continue
        index = output.index[mask][0]
        playcricket_value = numeric_value(output.at[index, column])
        applied = playcricket_value is None or document_value > playcricket_value
        display_value = document_value if applied else playcricket_value
        output.at[index, f"playcricket_{column.lower().replace(' ', '_')}_value"] = playcricket_value
        output.at[index, f"document_{column.lower().replace(' ', '_')}_value"] = document_value
        output.at[index, f"{column.lower().replace(' ', '_')}_value_source"] = "document_override" if applied else "playcricket"
        output.at[index, f"{column.lower().replace(' ', '_')}_override_applied"] = bool(applied)
        if applied:
            output.at[index, column] = display_value
        decisions.append(
            decision_row(
                override,
                metric_key,
                playcricket_value,
                document_value,
                display_value,
                "document_override" if applied else "playcricket",
                applied,
            )
        )
    output = output.drop(columns=["_player_key_for_doc_override"], errors="ignore")
    if write_decisions:
        write_decision_rows(decisions)
    return output


def decision_row(
    override: pd.Series,
    metric: str,
    playcricket_value: float | None,
    document_value: float | None,
    display_value: float | None,
    display_source: str,
    applied: bool,
) -> dict[str, object]:
    return {
        "player_name": override.get("player_name", ""),
        "metric": metric,
        "playcricket_value": "" if playcricket_value is None else playcricket_value,
        "document_value": "" if document_value is None else document_value,
        "display_value": "" if display_value is None else display_value,
        "display_source": display_source,
        "override_applied": "yes" if applied else "no",
        "confidence": override.get("confidence", ""),
        "notes": override.get("notes", ""),
    }


def write_decision_rows(rows: list[dict[str, object]]) -> pd.DataFrame:
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(rows, columns=DECISION_COLUMNS)
    frame.to_csv(DECISIONS, index=False)
    return frame


def premiership_key(row: pd.Series) -> str:
    parts = [
        row.get("season", ""),
        row.get("grade_name", ""),
        row.get("fvcc_team_name", row.get("team", "")),
        row.get("opponent_team_name", row.get("opponent", "")),
        row.get("result_text", row.get("result", "")),
    ]
    return "|".join(normalize_name(part) for part in parts if str(part or "").strip())


def merge_premiership_overrides(wins: pd.DataFrame, players: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    write_empty_source_files()
    doc_wins = read_csv(PREMIERSHIPS)
    doc_players = read_csv(PREMIERSHIP_PLAYERS)
    combined_wins = wins.copy()
    if "source" not in combined_wins:
        combined_wins["source"] = "playcricket"
    combined_wins["review_required"] = combined_wins.get("review_required", False)
    if not doc_wins.empty:
        for column in PREMIERSHIP_COLUMNS:
            if column not in doc_wins:
                doc_wins[column] = ""
        existing_keys = {premiership_key(row) for _, row in combined_wins.iterrows()} if not combined_wins.empty else set()
        additions = []
        for _, row in doc_wins.iterrows():
            candidate = pd.Series(
                {
                    "match_id": "",
                    "season": row.get("season", ""),
                    "grade_name": row.get("grade_name", ""),
                    "round_name": "Grand Final",
                    "match_date": "",
                    "club_team_id": "",
                    "club_team_name": row.get("team", "Glen Waverley Hawks"),
                    "fvcc_team_name": row.get("team", "Glen Waverley Hawks"),
                    "opponent_team_name": row.get("opponent", ""),
                    "captain_name": row.get("captain", ""),
                    "result_text": row.get("result", ""),
                    "result_margin_display": row.get("result", ""),
                    "venue_name": "",
                    "scoreboard_url": "",
                    "confidence": row.get("confidence", "review"),
                    "detection_reason": row.get("notes", "Hawks document premiership supplement"),
                    "source": "document",
                    "review_required": row.get("review_required", True),
                }
            )
            key = premiership_key(candidate)
            if key in existing_keys:
                combined_wins.loc[[premiership_key(existing) == key for _, existing in combined_wins.iterrows()], "source"] = "combined"
                continue
            additions.append(candidate.to_dict())
        if additions:
            combined_wins = pd.concat([combined_wins, pd.DataFrame(additions)], ignore_index=True, sort=False)

    combined_players = players.copy()
    if not doc_players.empty:
        combined_players = build_combined_premiership_players(combined_players, doc_players)
    return combined_wins, combined_players


def build_combined_premiership_players(players: pd.DataFrame, doc_players: pd.DataFrame) -> pd.DataFrame:
    for column in PREMIERSHIP_PLAYER_COLUMNS:
        if column not in doc_players:
            doc_players[column] = ""
    rows = []
    if not players.empty:
        rows.append(players.copy())
    document_rows = []
    for name, group in doc_players.groupby("player_name", dropna=False):
        seasons = sorted({str(value).strip() for value in group["season"] if str(value).strip()})
        grades = sorted({str(value).strip() for value in group["grade_name"] if str(value).strip()})
        document_rows.append(
            {
                "canonical_player_id": f"doc_{normalize_name(name).replace(' ', '_')}",
                "canonical_player_name": name,
                "display_player_name": name,
                "premiership_count": len(group.drop_duplicates(["season", "grade_name"])),
                "seasons": ", ".join(seasons),
                "grades": ", ".join(grades),
                "teams": "Glen Waverley Hawks",
                "latest_premiership_season": seasons[-1] if seasons else "",
                "evidence_match_ids": "",
                "confidence": group["confidence"].replace("", pd.NA).dropna().iloc[0] if group["confidence"].replace("", pd.NA).notna().any() else "review",
                "source": "document",
            }
        )
    if document_rows:
        rows.append(pd.DataFrame(document_rows))
    if not rows:
        return pd.DataFrame()
    combined = pd.concat(rows, ignore_index=True, sort=False)
    combined["premiership_count"] = pd.to_numeric(combined["premiership_count"], errors="coerce").fillna(0).astype(int)
    return combined.sort_values(["premiership_count", "display_player_name"], ascending=[False, True])


def extract_documents() -> dict[str, object]:
    ensure_document_override_dirs()
    write_empty_source_files()
    raw_files = [path for path in RAW_DIR.glob("*") if path.is_file() and not path.name.startswith(".")]
    extracted_records = []
    extracted_premierships = []
    for path in raw_files:
        text = extract_text(path)
        if not text:
            continue
        (EXTRACTED_DIR / f"{path.stem}.txt").write_text(text, encoding="utf-8")
        extracted_records.extend(parse_record_lines(text, path.name))
        extracted_premierships.extend(parse_premiership_lines(text, path.name))
    if extracted_records:
        pd.DataFrame(extracted_records, columns=RECORD_COLUMNS).to_csv(RECORD_OVERRIDES, index=False)
    if extracted_premierships:
        pd.DataFrame(extracted_premierships, columns=PREMIERSHIP_COLUMNS).to_csv(PREMIERSHIPS, index=False)
    return {
        "raw_files": len(raw_files),
        "record_overrides": len(extracted_records),
        "premierships": len(extracted_premierships),
    }


def extract_text(path: Path) -> str:
    suffix = path.suffix.casefold()
    try:
        if suffix == ".docx":
            with zipfile.ZipFile(path) as archive:
                raw = archive.read("word/document.xml").decode("utf-8", errors="ignore")
            return re.sub(r"<[^>]+>", " ", raw)
        if suffix in {".txt", ".csv"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix in {".xlsx", ".xls"}:
            sheets = pd.read_excel(path, sheet_name=None)
            return "\n".join(frame.to_csv(index=False) for frame in sheets.values())
        if suffix == ".pdf":
            return ""
    except Exception:
        return ""
    return ""


def parse_record_lines(text: str, source_name: str) -> list[dict[str, object]]:
    rows = []
    for line in text.splitlines():
        match = re.search(r"([A-Za-z][A-Za-z .'-]{2,})\s+(\d{2,5})\s+(games|matches|runs|wickets|catches)\b", line, flags=re.IGNORECASE)
        if not match:
            continue
        rows.append(
            {
                "player_name": re.sub(r"\s+", " ", match.group(1)).strip(),
                "metric": match.group(3).casefold(),
                "document_value": match.group(2),
                "source_document": source_name,
                "confidence": "review",
                "notes": "Auto-extracted from document text; requires review before customer use.",
            }
        )
    return rows


def parse_premiership_lines(text: str, source_name: str) -> list[dict[str, object]]:
    rows = []
    for line in text.splitlines():
        if not re.search(r"premier|premiership|grand final", line, flags=re.IGNORECASE):
            continue
        season = re.search(r"(Summer\s+\d{4}/\d{2}|\d{4}/\d{2}|\d{4})", line, flags=re.IGNORECASE)
        if not season:
            continue
        rows.append(
            {
                "season": season.group(1),
                "grade_name": "",
                "team": "Glen Waverley Hawks",
                "opponent": "",
                "result": "",
                "captain": "",
                "source_document": source_name,
                "confidence": "review",
                "review_required": "true",
                "notes": line.strip()[:500],
            }
        )
    return rows
