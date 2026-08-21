"""Hawks document override layer for records and premiership supplements."""

from __future__ import annotations

import re
import subprocess
import zipfile
from pathlib import Path

import pandas as pd

from src.data.gwhcc_match_policy import MATCH_CENTRE, PROCESSED, read_csv

CLUB_ID = "glen-waverley-hawks"
ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = ROOT / "clubs" / CLUB_ID / "data" / "source" / "document_overrides"
RAW_DIR = SOURCE_ROOT / "raw"
EXTRACTED_DIR = SOURCE_ROOT / "extracted"
REVIEW_DIR = SOURCE_ROOT / "review"
VALIDATION_DIR = PROCESSED / "validation"

RECORD_OVERRIDES = SOURCE_ROOT / "gwhcc_record_overrides.csv"
CUSTOMER_CAREER_OVERRIDES = SOURCE_ROOT / "gwhcc_customer_career_overrides.csv"
PREMIERSHIPS = SOURCE_ROOT / "gwhcc_premierships.csv"
PREMIERSHIP_PLAYERS = SOURCE_ROOT / "gwhcc_premiership_players.csv"
PLAYER_ALIASES = SOURCE_ROOT / "gwhcc_document_player_aliases.csv"
HISTORICAL_CENTURIES = SOURCE_ROOT / "gwhcc_historical_centuries.csv"
HISTORICAL_CAREER_METADATA = SOURCE_ROOT / "gwhcc_historical_career_metadata.csv"
HISTORICAL_PREMIERSHIPS = SOURCE_ROOT / "gwhcc_historical_premiership_events.csv"
FASTEST_INNINGS_SUPPLEMENTS = SOURCE_ROOT / "gwhcc_fastest_innings_supplements.csv"
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
PLAYER_ALIAS_COLUMNS = ["document_player_name", "playcricket_player_name", "scope", "confidence", "notes"]
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
    paths = [
        RECORD_OVERRIDES,
        CUSTOMER_CAREER_OVERRIDES,
        PREMIERSHIPS,
        PREMIERSHIP_PLAYERS,
        PLAYER_ALIASES,
        HISTORICAL_CENTURIES,
        HISTORICAL_CAREER_METADATA,
        HISTORICAL_PREMIERSHIPS,
        FASTEST_INNINGS_SUPPLEMENTS,
    ]
    return tuple((str(path), path.stat().st_mtime) for path in paths if path.exists())


def normalize_name(value: object) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold())
    return re.sub(r"\s+", " ", text).strip()


def initial_surname_key(value: object) -> str:
    text = re.sub(r"\([^)]*\)", " ", str(value or ""))
    words = re.findall(r"[A-Za-z]+", text)
    if len(words) < 2:
        return ""
    return f"{words[0][0].casefold()} {words[-1].casefold()}"


def unique_alias_lookup(names: pd.Series) -> dict[str, str]:
    pairs: dict[str, set[str]] = {}
    for value in names.dropna().astype(str):
        alias = initial_surname_key(value)
        normalized = normalize_name(value)
        if alias and normalized:
            pairs.setdefault(alias, set()).add(normalized)
    return {alias: next(iter(values)) for alias, values in pairs.items() if len(values) == 1}


def load_document_player_aliases(scope: str = "") -> dict[str, str]:
    if not PLAYER_ALIASES.exists():
        return {}
    aliases = read_csv(PLAYER_ALIASES)
    for column in PLAYER_ALIAS_COLUMNS:
        if column not in aliases:
            aliases[column] = ""
    aliases = aliases[aliases["confidence"].astype(str).str.casefold().isin({"confirmed", "approved", "high"})].copy()
    if scope:
        scope_key = scope.casefold().strip()
        alias_scopes = aliases["scope"].astype(str).str.casefold().str.strip()
        aliases = aliases[alias_scopes.isin({"", "all", scope_key})].copy()
    mapping: dict[str, str] = {}
    for row in aliases.to_dict("records"):
        document_key = normalize_name(row.get("document_player_name"))
        playcricket_key = normalize_name(row.get("playcricket_player_name"))
        if document_key and playcricket_key:
            mapping[document_key] = playcricket_key
    return mapping


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
    frames = [frame for frame in [read_csv(RECORD_OVERRIDES), read_csv(CUSTOMER_CAREER_OVERRIDES)] if not frame.empty]
    frame = pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame(columns=RECORD_COLUMNS)
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
        return apply_historical_career_supplements(output)

    output["_player_key_for_doc_override"] = output["Player"].map(normalize_name)
    alias_lookup = unique_alias_lookup(output["Player"])
    manual_aliases = load_document_player_aliases("records")
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
            alias_key = initial_surname_key(override.get("player_name"))
            alias_player_key = alias_lookup.get(alias_key, "")
            if alias_player_key:
                mask = output["_player_key_for_doc_override"].eq(alias_player_key)
        if not mask.any():
            manual_player_key = manual_aliases.get(player_key, "")
            if manual_player_key:
                mask = output["_player_key_for_doc_override"].eq(manual_player_key)
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
    return apply_historical_career_supplements(output)


def apply_historical_career_supplements(all_time: pd.DataFrame) -> pd.DataFrame:
    """Apply additive century counts and documented debut metadata."""
    if all_time.empty:
        return all_time
    output = all_time.copy()
    centuries = read_csv(HISTORICAL_CENTURIES)
    if not centuries.empty and "100s" in output and "historical_100s_supplement" not in output:
        counts = centuries.groupby("canonical_player_id", as_index=False).size().rename(columns={"size": "historical_100s_supplement"})
        output = merge_supplement_by_identity(output, counts, ["historical_100s_supplement"])
        output["historical_100s_supplement"] = pd.to_numeric(output.get("historical_100s_supplement"), errors="coerce").fillna(0).astype(int)
        output["100s"] = pd.to_numeric(output["100s"], errors="coerce").fillna(0) + output["historical_100s_supplement"]
        output["hundreds_value_source"] = output["historical_100s_supplement"].gt(0).map({True: "playcricket_plus_customer_history", False: "playcricket"})

    metadata = read_csv(HISTORICAL_CAREER_METADATA)
    if not metadata.empty:
        columns = ["earliest_documented_season", "source_document", "source_sheet"]
        available = [column for column in columns if column in metadata]
        source = metadata[["canonical_player_id", *available]].drop_duplicates("canonical_player_id")
        source = source.rename(columns={"source_document": "career_start_source_document", "source_sheet": "career_start_source_sheet"})
        if "earliest_documented_season" not in output:
            output = merge_supplement_by_identity(output, source, [column for column in source.columns if column != "canonical_player_id"])
        if "Debut Season" in output:
            output["Debut Season"] = output.apply(
                lambda row: earlier_season(row.get("earliest_documented_season"), row.get("Debut Season")),
                axis=1,
            )
        if "Career Span" in output:
            output["Career Span"] = output.apply(
                lambda row: career_span_with_documented_start(row.get("Career Span"), row.get("earliest_documented_season")),
                axis=1,
            )
    return output


def merge_supplement_by_identity(output: pd.DataFrame, supplement: pd.DataFrame, value_columns: list[str]) -> pd.DataFrame:
    if supplement.empty:
        return output
    if "canonical_player_id" in output:
        return output.merge(supplement[["canonical_player_id", *value_columns]], on="canonical_player_id", how="left")
    if "Player" not in output:
        return output
    source = supplement.copy()
    if "canonical_player_name" not in source:
        return output
    source["_player_key"] = source["canonical_player_name"].map(normalize_name)
    source = source.drop_duplicates("_player_key")
    result = output.copy()
    result["_player_key"] = result["Player"].map(normalize_name)
    return result.merge(source[["_player_key", *value_columns]], on="_player_key", how="left").drop(columns="_player_key")


def season_sort_key(value: object) -> tuple[int, int]:
    match = re.search(r"(\d{4})/(\d{2})", str(value or ""))
    return (int(match.group(1)), int(match.group(2))) if match else (0, 0)


def earlier_season(documented: object, reconstructed: object) -> str:
    documented_text = clean_optional_text(documented)
    reconstructed_text = clean_optional_text(reconstructed)
    if documented_text and (not reconstructed_text or season_sort_key(documented_text) < season_sort_key(reconstructed_text)):
        return documented_text
    return reconstructed_text


def career_span_with_documented_start(current: object, documented: object) -> str:
    current_text = clean_optional_text(current)
    documented_text = clean_optional_text(documented)
    if not documented_text:
        return current_text
    if not current_text:
        return documented_text
    parts = [part.strip() for part in re.split(r"\s+[–—-]\s+", current_text) if part.strip()]
    latest = parts[-1] if parts else current_text
    start = earlier_season(documented_text, parts[0] if parts else current_text)
    return start if season_sort_key(start) == season_sort_key(latest) else f"{start} – {latest}"


def clean_optional_text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.casefold() in {"", "nan", "none", "nat"} else text


def merge_fastest_innings_supplements(milestones: pd.DataFrame) -> pd.DataFrame:
    """Merge governed scorecard-only milestone evidence without fabricating deliveries."""
    supplements = read_csv(FASTEST_INNINGS_SUPPLEMENTS)
    if supplements.empty:
        return milestones
    confidence = supplements.get("confidence", pd.Series("", index=supplements.index)).astype(str).str.casefold().str.strip()
    supplements = supplements[confidence.isin({"confirmed", "approved", "high"})].copy()
    if supplements.empty:
        return milestones

    batting = read_csv(MATCH_CENTRE / "all_scorecard_batting.csv")
    matches = read_csv(MATCH_CENTRE / "all_matches.csv")
    innings = read_csv(MATCH_CENTRE / "all_match_innings.csv")
    if batting.empty or matches.empty:
        return milestones
    rows = []
    for supplement in supplements.to_dict("records"):
        match_id = str(supplement.get("match_id") or "").strip()
        participant_id = str(supplement.get("participant_id") or "").strip()
        scorecard = batting[
            batting["match_id"].astype(str).eq(match_id)
            & batting["participant_id"].astype(str).eq(participant_id)
        ]
        match = matches[matches["match_id"].astype(str).eq(match_id)]
        if len(scorecard) != 1 or len(match) != 1:
            continue
        scorecard_row = scorecard.iloc[0]
        match_row = match.iloc[0]
        final_runs = numeric_value(scorecard_row.get("runs_scored"))
        final_balls = numeric_value(scorecard_row.get("balls_faced"))
        balls_to_50 = numeric_value(supplement.get("balls_to_50"))
        balls_to_100 = numeric_value(supplement.get("balls_to_100"))
        if not valid_governed_milestone(final_runs, final_balls, balls_to_50, 50):
            balls_to_50 = None
        if not valid_governed_milestone(final_runs, final_balls, balls_to_100, 100):
            balls_to_100 = None
        if balls_to_50 is None and balls_to_100 is None:
            continue
        team_id = str(scorecard_row.get("team_id") or "")
        home_id = str(match_row.get("home_team_id") or "")
        team_name = match_row.get("home_team_name") if team_id == home_id else match_row.get("away_team_name")
        opposition = match_row.get("away_team_name") if team_id == home_id else match_row.get("home_team_name")
        team_runs = pd.NA
        if not innings.empty:
            innings_match = innings[
                innings["match_id"].astype(str).eq(match_id)
                & innings["innings_id"].astype(str).eq(str(scorecard_row.get("innings_id") or ""))
            ]
            if not innings_match.empty:
                team_runs = pd.to_numeric(innings_match.iloc[0].get("runs_scored"), errors="coerce")
        not_out = str(scorecard_row.get("dismissal_type") or "").casefold() in {"not out", "retired not out"} or "not out" in str(scorecard_row.get("dismissal_text") or "").casefold()
        final_runs_int = int(final_runs) if final_runs is not None else 0
        rows.append(
            {
                "player_id": participant_id,
                "player_name": scorecard_row.get("player_name"),
                "canonical_player_name": supplement.get("canonical_player_name") or scorecard_row.get("player_name"),
                "match_id": match_id,
                "innings_id": scorecard_row.get("innings_id"),
                "participant_id": participant_id,
                "match_date": str(match_row.get("first_match_day") or "")[:10],
                "season": match_row.get("season"),
                "team_name": team_name,
                "grade_name": match_row.get("grade_name"),
                "opposition_team": opposition,
                "venue_name": match_row.get("venue_name"),
                "match_type": match_row.get("match_type"),
                "final_runs": final_runs_int,
                "final_balls": int(final_balls) if final_balls is not None else pd.NA,
                "final_score_display": f"{final_runs_int}{'*' if not_out else ''}",
                "balls_to_25": pd.NA,
                "balls_to_50": balls_to_50,
                "balls_to_100": balls_to_100,
                "balls_to_150": pd.NA,
                "team_runs": team_runs,
                "team_run_contribution_pct": (final_runs_int * 100 / float(team_runs)) if pd.notna(team_runs) and float(team_runs) else pd.NA,
                "result_text": match_row.get("result_text"),
                "is_not_out": not_out,
                "runs_source_used": "playcricket_scorecard",
                "balls_faced_source_used": "governed_customer_milestone",
                "source_ball_by_ball_available": False,
                "governed_source_document": supplement.get("source_document"),
                "governed_source_notes": supplement.get("notes"),
            }
        )
    if not rows:
        return milestones
    additions = pd.DataFrame(rows)
    output = milestones.copy()
    for row in additions.to_dict("records"):
        mask = (
            output.get("match_id", pd.Series("", index=output.index)).astype(str).eq(str(row["match_id"]))
            & output.get("participant_id", pd.Series("", index=output.index)).astype(str).eq(str(row["participant_id"]))
        )
        if mask.any():
            index = output.index[mask][0]
            for column in ["balls_to_50", "balls_to_100"]:
                if pd.isna(output.at[index, column]) and pd.notna(row.get(column)):
                    output.at[index, column] = row[column]
            continue
        for column in row:
            if column not in output:
                output[column] = pd.NA
        output.loc[len(output)] = [row.get(column, pd.NA) for column in output.columns]
    return output.sort_values(["match_date", "player_name"], ascending=[False, True]).reset_index(drop=True)


def valid_governed_milestone(final_runs: float | None, final_balls: float | None, milestone_balls: float | None, target: int) -> bool:
    return (
        final_runs is not None
        and final_balls is not None
        and milestone_balls is not None
        and final_runs >= target
        and 0 < milestone_balls <= final_balls
    )


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
    doc_win_frames = [frame for frame in [read_csv(PREMIERSHIPS), read_csv(HISTORICAL_PREMIERSHIPS)] if not frame.empty]
    doc_wins = pd.concat(doc_win_frames, ignore_index=True, sort=False) if doc_win_frames else pd.DataFrame()
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
    confidence = doc_players["confidence"].astype(str).str.casefold().str.strip()
    doc_players = doc_players[confidence.isin({"approved", "high"})].copy()
    document_rows: list[dict[str, object]] = []
    for name, group in doc_players.groupby("player_name", dropna=False):
        player_name = str(name or "").strip()
        if not player_name:
            continue
        seasons = sorted({str(value).strip() for value in group["season"] if str(value).strip()})
        grades = sorted({str(value).strip() for value in group["grade_name"] if str(value).strip()})
        document_rows.append(
            {
                "canonical_player_id": f"doc_{normalize_name(player_name).replace(' ', '_')}",
                "canonical_player_name": player_name,
                "display_player_name": player_name,
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

    rows = []
    if not players.empty:
        base = players.copy()
        name_column = "display_player_name" if "display_player_name" in base else "canonical_player_name"
        if name_column in base:
            base["display_player_name"] = base[name_column]
            base["_player_key"] = base["display_player_name"].map(normalize_name)
            rows.append(base)
    if document_rows:
        document = pd.DataFrame(document_rows)
        document["_player_key"] = document["display_player_name"].map(normalize_name)
        if rows:
            base = rows[0]
            alias_lookup = unique_alias_lookup(base["display_player_name"]) if "display_player_name" in base else {}
            manual_aliases = load_document_player_aliases("premierships")
            base_by_key = base.drop_duplicates("_player_key").set_index("_player_key").to_dict("index") if "_player_key" in base else {}
            for index, row in document.iterrows():
                document_key = normalize_name(row.get("display_player_name"))
                base_key = manual_aliases.get(document_key) or alias_lookup.get(initial_surname_key(row.get("display_player_name")))
                base_row = base_by_key.get(base_key or "")
                if not base_row:
                    continue
                for column in ["canonical_player_id", "canonical_player_name", "display_player_name"]:
                    if column in base_row:
                        document.at[index, column] = base_row[column]
                document.at[index, "_player_key"] = base_key
        rows.append(document)
    if not rows:
        return pd.DataFrame()
    combined = pd.concat(rows, ignore_index=True, sort=False)
    combined["premiership_count"] = pd.to_numeric(combined["premiership_count"], errors="coerce").fillna(0).astype(int)
    if "_player_key" not in combined:
        combined["_player_key"] = combined.get("display_player_name", pd.Series("", index=combined.index)).map(normalize_name)

    merged_rows = []
    for _key, group in combined.groupby("_player_key", dropna=False):
        if not str(_key or "").strip():
            continue
        group = group.copy()
        doc_group = group[group.get("source", pd.Series("", index=group.index)).astype(str).eq("document")]
        play_group = group[~group.index.isin(doc_group.index)]
        best = group.sort_values("premiership_count", ascending=False).iloc[0].to_dict()
        play_count = int(pd.to_numeric(play_group.get("premiership_count"), errors="coerce").fillna(0).max()) if not play_group.empty else 0
        doc_count = int(pd.to_numeric(doc_group.get("premiership_count"), errors="coerce").fillna(0).max()) if not doc_group.empty else 0
        best["premiership_count"] = max(play_count, doc_count)
        if play_count and doc_count:
            best["source"] = "combined"
        elif doc_count:
            best["source"] = "document"
        else:
            best["source"] = best.get("source", "playcricket") or "playcricket"
        best["document_premiership_count"] = doc_count
        best["playcricket_premiership_count"] = play_count
        best["premiership_count_source"] = "document" if doc_count > play_count else "playcricket"
        if not doc_group.empty and str(doc_group.iloc[0].get("seasons", "")).strip():
            best["document_seasons"] = doc_group.iloc[0].get("seasons", "")
            best["document_grades"] = doc_group.iloc[0].get("grades", "")
        merged_rows.append(best)
    output = pd.DataFrame(merged_rows).drop(columns=["_player_key"], errors="ignore")
    return output.sort_values(["premiership_count", "display_player_name"], ascending=[False, True])


def extract_documents() -> dict[str, object]:
    ensure_document_override_dirs()
    write_empty_source_files()
    raw_files = document_source_files()
    extracted_records = []
    extracted_premierships = []
    extracted_premiership_players = []
    for path in raw_files:
        text = extract_text(path)
        if not text:
            continue
        (EXTRACTED_DIR / f"{path.stem}.txt").write_text(text, encoding="utf-8")
        extracted_records.extend(parse_record_lines(text, path.name))
        extracted_premierships.extend(parse_premiership_lines(text, path.name))
        extracted_premiership_players.extend(parse_premiership_player_lines(text, path.name))
    if extracted_records:
        pd.DataFrame(extracted_records, columns=RECORD_COLUMNS).drop_duplicates().to_csv(RECORD_OVERRIDES, index=False)
    else:
        pd.DataFrame(columns=RECORD_COLUMNS).to_csv(RECORD_OVERRIDES, index=False)
    if extracted_premierships:
        pd.DataFrame(extracted_premierships, columns=PREMIERSHIP_COLUMNS).drop_duplicates().to_csv(PREMIERSHIPS, index=False)
    else:
        pd.DataFrame(columns=PREMIERSHIP_COLUMNS).to_csv(PREMIERSHIPS, index=False)
    if extracted_premiership_players:
        pd.DataFrame(extracted_premiership_players, columns=PREMIERSHIP_PLAYER_COLUMNS).drop_duplicates().to_csv(PREMIERSHIP_PLAYERS, index=False)
    else:
        pd.DataFrame(columns=PREMIERSHIP_PLAYER_COLUMNS).to_csv(PREMIERSHIP_PLAYERS, index=False)
    return {
        "raw_files": len(raw_files),
        "record_overrides": len(extracted_records),
        "premierships": len(extracted_premierships),
        "premiership_players": len(extracted_premiership_players),
    }


def extract_text(path: Path) -> str:
    suffix = path.suffix.casefold()
    try:
        if suffix == ".docx":
            with zipfile.ZipFile(path) as archive:
                raw = archive.read("word/document.xml").decode("utf-8", errors="ignore")
            return re.sub(r"<[^>]+>", " ", raw)
        if suffix == ".doc":
            return subprocess.check_output(["textutil", "-convert", "txt", "-stdout", str(path)], text=True, stderr=subprocess.DEVNULL)
        if suffix in {".txt", ".csv"}:
            return path.read_text(encoding="utf-8", errors="ignore")
        if suffix in {".xlsx", ".xls"}:
            sheets = pd.read_excel(path, sheet_name=None)
            return "\n".join(frame.to_csv(index=False) for frame in sheets.values())
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception:
        return ""
    return ""


def document_source_files() -> list[Path]:
    raw_files = [path for path in RAW_DIR.glob("*") if path.is_file() and not path.name.startswith(".")]
    has_canonical_download = any(
        path.suffix.casefold() in {".pdf", ".doc", ".docx", ".xlsx", ".xls"} for path in raw_files
    )
    if has_canonical_download:
        raw_files = [path for path in raw_files if not path.name.endswith("_accessibility.txt")]
    return sorted(raw_files)


def parse_record_lines(text: str, source_name: str) -> list[dict[str, object]]:
    rows = []
    if "Leading Players" in source_name or "TOP 10 BATSMEN IN CLUB HISTORY" in text:
        rows.extend(parse_leading_player_records(source_name))
        return rows
    for line in text.splitlines():
        if re.search(r"\bTOP\s+\d+\b", line, flags=re.IGNORECASE):
            continue
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
    if "PREMIERSHIP PLAYERS LIST" in text:
        return []
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


def parse_leading_player_records(source_name: str) -> list[dict[str, object]]:
    source = source_name or "gwhcc_leading_players_source"
    note = "Extracted from GWHCC Leading Players 2025-26 source document; requires review before customer use."
    rows: list[dict[str, object]] = []
    values = {
        "runs": [
            ("G. Mahoney", 11040),
            ("S. Somaia", 9621),
            ("S. Wynd", 9205),
            ("G. McCormick", 8664),
            ("B. Calder", 7636),
            ("J. Greaves", 7098),
            ("C. Briginshaw", 7051),
            ("B. Powell", 6490),
            ("G. Cuddon", 6311),
            ("G. Haye", 6215),
        ],
        "wickets": [
            ("M. Briginshaw", 533),
            ("A. Dale", 456),
            ("N. Bungey", 408),
            ("G. McCormick", 393),
            ("C. Perkins", 377),
            ("L. Galle", 357),
            ("S. Wynd", 349),
            ("A. Chelvan", 339),
            ("J. Goddard (Justin)", 333),
            ("H. Bristow", 318),
            ("T. Medina", 300),
        ],
        "games": [
            ("G. McCormick", 427),
            ("C. Briginshaw", 390.5),
            ("N. Bungey", 338),
            ("G. Powell", 337),
            ("S. Somaia", 322),
            ("B. Calder", 304),
            ("M. Briginshaw", 296),
            ("C. Perkins", 264),
        ],
    }
    for metric, metric_rows in values.items():
        for player_name, value in metric_rows:
            rows.append(
                {
                    "player_name": player_name,
                    "metric": metric,
                    "document_value": value,
                    "source_document": source,
                    "confidence": "review",
                    "notes": note,
                }
            )
    return rows


def parse_premiership_player_lines(text: str, source_name: str) -> list[dict[str, object]]:
    if "PREMIERSHIP PLAYERS LIST" not in text:
        return []
    rows: list[dict[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    confidence = "high" if source_name.casefold().endswith(".pdf") else "review"
    note_source = "PDF text" if confidence == "high" else "browser accessibility text"
    current_name = ""
    cleaned_text = re.sub(r"-\s*\n\s*(\d{1,2})", r"-\1", text.replace("–", "-"))
    for raw_line in cleaned_text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line or re.search(r"premiership players list|up to 1980", line, flags=re.IGNORECASE):
            continue
        events = parse_premiership_events(line)
        if not events:
            continue
        first_event = first_premiership_event(line)
        prefix = line[: first_event.start()].strip(" ,") if first_event else ""
        prefix = re.sub(r"^\d+\s+", "", prefix).strip()
        if prefix and re.search(r"[A-Za-z]", prefix):
            current_name = normalize_player_label(prefix)
        if not current_name:
            continue
        for event in events:
            season = event["season"]
            if not re.fullmatch(r"\d{2}-\d{2}", season):
                continue
            if season.endswith("-00") and "03-0" in line:
                continue
            name = current_name
            key = (name, event["season"], event["grade_name"])
            if key in seen:
                continue
            seen.add(key)
            rows.append(
                {
                    "season": event["season"],
                    "grade_name": event["grade_name"],
                    "player_name": name,
                    "source_document": source_name,
                    "confidence": confidence,
                    "notes": f"Extracted from GWH Premiership list 2026 {note_source}; requires review before customer use.",
                }
            )
    return rows


def first_premiership_event(segment: str) -> re.Match[str] | None:
    return premiership_event_pattern().search(segment)


def parse_premiership_events(segment: str) -> list[dict[str, str]]:
    events = []
    for match in premiership_event_pattern().finditer(segment.replace("–", "-")):
        grade = normalize_grade_label(match.group("grade"))
        start = match.group("start")
        end = match.group("end").zfill(2)
        events.append({"grade_name": grade, "season": f"{start}-{end}"})
    return events


def premiership_event_pattern() -> re.Pattern[str]:
    return re.compile(
        r"(?P<grade>U/?\.?\d{2}(?:[A-Z])?(?:\s*\([^)]+\))?|A\s*-\s*One(?:\s*Day)?|A\s*One(?:\s*Day)?|B\s*-\s*One|B\s*One|One\s*Day|T20(?:\s*\(\d\))?|WS2?|B3|A1|A2|C1|D1|[A-F])\s*"
        r"(?P<start>\d{2})\s*(?:-|/)?\s*(?P<end>\d{1,2})",
        flags=re.IGNORECASE,
    )


def normalize_player_label(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" ,")
    text = re.sub(r"\b([A-Z])\s+\.", r"\1.", text)
    text = re.sub(r"\b([A-Z])\.([A-Za-z])", r"\1. \2", text)
    return text


def normalize_grade_label(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    text = text.replace("U/.", "U/")
    text = re.sub(r"U/?(\d{2})", r"U/\1", text, flags=re.IGNORECASE)
    text = re.sub(r"\bA\s*-\s*One(?:\s*Day)?\b", "A-One Day", text, flags=re.IGNORECASE)
    text = re.sub(r"\bA\s*One(?:\s*Day)?\b", "A-One Day", text, flags=re.IGNORECASE)
    text = re.sub(r"\bB\s*-\s*One\b", "B-One", text, flags=re.IGNORECASE)
    text = re.sub(r"\bB\s*One\b", "B-One", text, flags=re.IGNORECASE)
    text = re.sub(r"T20\s*\(\s*(\d+)\s*\)", r"T20(\1)", text, flags=re.IGNORECASE)
    return text
