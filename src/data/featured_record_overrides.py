"""Load and apply approved, club-scoped featured-record overrides."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from src.config.club_config import REPO_ROOT, get_active_club_id, normalize_club_id


GRDCC_CLUB_ID = "georges-river-district"
APPROVED_STATUSES = {"approved", "annual_report_authoritative"}
METRIC_COLUMNS = {
    "career_runs": "Runs",
    "career_wickets": "Wickets",
}
ANNUAL_REPORT_LEADER_COLUMNS = {
    "most_runs": "Runs",
    "most_wickets": "Wickets",
}
FEATURED_NAME_ALIASES = {
    "ben vella": "benjamin vella",
    "pat kennedy": "patrick kennedy",
    "nicholas henriques": "nick henriques",
    "christopher diehm": "chris diehm",
    "nathan e wadds": "nathan wadds",
}

SUPPLEMENT_NUMERIC_COLUMNS = {
    "override_value",
    "source_rule_derived_value",
    "excel_seasons_count",
    "excel_matches",
    "excel_innings",
    "excel_not_outs",
    "excel_runs",
    "displayed_career_runs",
    "excel_hs",
    "excel_batting_average",
    "excel_50s",
    "excel_100s",
    "excel_wickets",
    "displayed_career_wickets",
    "excel_overs",
    "excel_balls",
    "excel_maidens",
    "excel_bowling_runs_conceded",
    "excel_bowling_average",
    "excel_bowling_strike_rate",
}


def normalize_featured_player_name(value: object) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").casefold())
    normalized = re.sub(r"\s+", " ", text).strip()
    return FEATURED_NAME_ALIASES.get(normalized, normalized)


def featured_record_override_path(club_id: str | None = None) -> Path:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    return REPO_ROOT / "clubs" / active_club_id / "data" / "source" / "annual_report_featured_record_overrides.csv"


def annual_report_all_time_leaders_path() -> Path:
    return (
        REPO_ROOT
        / "clubs"
        / GRDCC_CLUB_ID
        / "data"
        / "processed"
        / "validation"
        / "annual_report_2024_25"
        / "grdcc_annual_report_all_time_leaders_for_app.csv"
    )


def annual_report_override_decisions_path() -> Path:
    return (
        REPO_ROOT
        / "clubs"
        / GRDCC_CLUB_ID
        / "data"
        / "processed"
        / "validation"
        / "annual_report_2024_25"
        / "all_time_overrides"
        / "grdcc_all_time_override_decisions.csv"
    )


def override_player_supplements_path() -> Path:
    return (
        REPO_ROOT
        / "clubs"
        / GRDCC_CLUB_ID
        / "data"
        / "processed"
        / "validation"
        / "annual_report_2024_25"
        / "all_time_overrides"
        / "grdcc_override_player_excel_supplements.csv"
    )


def load_annual_report_override_decisions(club_id: str | None = None) -> pd.DataFrame:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    path = annual_report_override_decisions_path()
    if active_club_id != GRDCC_CLUB_ID or not path.exists():
        return pd.DataFrame()
    rows = pd.read_csv(path, dtype=str).fillna("")
    required = {"player_name", "normalized_player_name", "metric", "displayed_value", "validation_status"}
    if not required.issubset(rows.columns):
        return pd.DataFrame()
    rows = rows[rows["validation_status"].astype(str).str.casefold().eq("pass")].copy()
    rows["displayed_value"] = pd.to_numeric(rows["displayed_value"], errors="coerce")
    return rows[rows["displayed_value"].notna()].reset_index(drop=True)


def _first_non_empty(series: pd.Series) -> str:
    for value in series.astype(str):
        text = value.strip()
        if text and text.casefold() not in {"nan", "none"}:
            return text
    return ""


def _split_aliases(value: object) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in text.split(";") if part.strip()]


def _normalized_name_variants(player_name: object, aliases: object = "") -> set[str]:
    variants = {normalize_featured_player_name(player_name)}
    for alias in _split_aliases(aliases):
        variants.add(normalize_featured_player_name(alias))
    return {variant for variant in variants if variant}


def _match_player_variants(normalized_players: pd.Series, variants: set[str]) -> pd.Series:
    if not variants:
        return pd.Series(False, index=normalized_players.index)
    return normalized_players.isin(variants)


def load_override_player_supplements(club_id: str | None = None) -> pd.DataFrame:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    path = override_player_supplements_path()
    if active_club_id != GRDCC_CLUB_ID or not path.exists():
        return pd.DataFrame()
    rows = pd.read_csv(path, dtype=str).fillna("")
    required = {"player_name", "normalized_player_name"}
    if not required.issubset(rows.columns):
        return pd.DataFrame()
    for column in SUPPLEMENT_NUMERIC_COLUMNS.intersection(rows.columns):
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    aggregated = (
        rows.groupby("normalized_player_name", as_index=False)
        .agg(
            {
                "player_name": _first_non_empty,
                "excel_aliases_used": _first_non_empty,
                "excel_seasons": _first_non_empty,
                "matches_source": _first_non_empty,
                "fifties_hundreds_source": _first_non_empty,
                "source_confidence": _first_non_empty,
                "notes": _first_non_empty,
                **{
                    column: "max"
                    for column in SUPPLEMENT_NUMERIC_COLUMNS
                    if column in rows.columns
                },
            }
        )
    )
    return aggregated.reset_index(drop=True)


def _season_list(value: object) -> list[str]:
    return [part.strip() for part in str(value or "").split(",") if part.strip()]


def _season_sort_key(value: object) -> int:
    text = str(value or "").strip()
    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return 999999
    year = int(match.group())
    if "winter" in text.casefold():
        return year * 10 + 1
    if "summer" in text.casefold():
        return year * 10 + 2
    return year * 10


def _career_span_from_seasons(value: object) -> str:
    seasons = sorted(_season_list(value), key=_season_sort_key)
    if not seasons:
        return ""
    if len(seasons) == 1:
        return seasons[0]
    return f"{seasons[0]} – {seasons[-1]}"


def _balls_to_overs_display(value: object) -> str:
    balls = _supplement_value(pd.Series({"balls": value}), "balls")
    if balls is None or balls <= 0:
        return ""
    whole = int(balls // 6)
    rem = int(balls % 6)
    return f"{whole}.{rem}"


def _supplement_value(row: pd.Series, column: str) -> float | None:
    if column not in row.index:
        return None
    numeric = pd.to_numeric(pd.Series([row.get(column)]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return None
    return float(numeric)


def apply_override_player_supplements(all_time: pd.DataFrame, club_id: str | None = None) -> pd.DataFrame:
    output = all_time.copy()
    if output.empty or "Player" not in output.columns:
        return output
    supplements = load_override_player_supplements(club_id)
    if supplements.empty:
        return output

    normalized_players = output["Player"].map(normalize_featured_player_name)
    for _, supplement in supplements.iterrows():
        variants = _normalized_name_variants(
            supplement.get("player_name", supplement.get("normalized_player_name", "")),
            supplement.get("excel_aliases_used", ""),
        )
        matches = _match_player_variants(normalized_players, variants)
        if not matches.any():
            continue
        index = output.index[matches][0]
        numeric_updates = {
            "Runs": _supplement_value(supplement, "displayed_career_runs"),
            "Wickets": _supplement_value(supplement, "displayed_career_wickets"),
            "Matches": _supplement_value(supplement, "excel_matches"),
            "Innings": _supplement_value(supplement, "excel_innings"),
            "HS": _supplement_value(supplement, "excel_hs"),
            "Bat Avg": _supplement_value(supplement, "excel_batting_average"),
            "50s": _supplement_value(supplement, "excel_50s"),
            "100s": _supplement_value(supplement, "excel_100s"),
            "Maidens": _supplement_value(supplement, "excel_maidens"),
            "Bowl Avg": _supplement_value(supplement, "excel_bowling_average"),
            "Bowl SR": _supplement_value(supplement, "excel_bowling_strike_rate"),
            "Balls Bowled": _supplement_value(supplement, "excel_balls"),
            "Seasons Played": _supplement_value(supplement, "excel_seasons_count"),
            "Seasons Count": _supplement_value(supplement, "excel_seasons_count"),
        }
        if numeric_updates.get("Innings") is not None and "Innings" not in output.columns:
            output["Innings"] = pd.NA
        for column, value in numeric_updates.items():
            if value is None or column not in output.columns:
                continue
            output.loc[index, column] = value
        if "Overs" in output.columns and numeric_updates.get("Balls Bowled") is not None:
            output.loc[index, "Overs"] = _balls_to_overs_display(numeric_updates["Balls Bowled"])
        if str(supplement.get("override_metric", "")).strip() == "career_wickets" and str(supplement.get("override_applies", "")).strip().casefold() == "yes":
            for column in ["Bowl Avg", "Bowl SR"]:
                if column in output.columns:
                    output.loc[index, column] = pd.NA
        output.loc[index, "Matches Source"] = str(supplement.get("matches_source", "") or "")
        output.loc[index, "Matches Proxy"] = "Yes" if str(supplement.get("matches_source", "")).strip().casefold() == "innings_proxy" else ""

        innings = _supplement_value(supplement, "excel_innings")
        not_outs = _supplement_value(supplement, "excel_not_outs")
        if innings is not None and not_outs is not None and "Outs" in output.columns:
            output.loc[index, "Outs"] = max(float(innings) - float(not_outs), 0.0)

        seasons_text = _first_non_empty(pd.Series([supplement.get("excel_seasons", "")]))
        seasons = sorted(_season_list(seasons_text), key=_season_sort_key)
        if seasons_text and "Seasons" in output.columns:
            output.loc[index, "Seasons"] = seasons_text
        if seasons:
            if "Debut Season" in output.columns:
                output.loc[index, "Debut Season"] = seasons[0]
            if "Latest Season" in output.columns:
                output.loc[index, "Latest Season"] = seasons[-1]
            if "Career Span" in output.columns:
                output.loc[index, "Career Span"] = _career_span_from_seasons(seasons_text)
        if "Featured Record Source" in output.columns:
            output.loc[index, "Featured Record Source"] = "GRDCC 2024/25 Annual Report"
        preferred_name = str(supplement.get("player_name", "") or "").strip()
        if preferred_name:
            output.loc[index, "Player"] = preferred_name
    return output


def load_annual_report_all_time_leaders(club_id: str | None = None) -> pd.DataFrame:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    path = annual_report_all_time_leaders_path()
    if active_club_id != GRDCC_CLUB_ID or not path.exists():
        return pd.DataFrame()
    rows = pd.read_csv(path, dtype=str).fillna("")
    required = {"section", "player_name", "normalized_player_name", "displayed_value", "included_in_app"}
    if not required.issubset(rows.columns):
        return pd.DataFrame()
    included = rows["included_in_app"].astype(str).str.strip().str.casefold().isin({"1", "true", "yes"})
    rows = rows[included].copy()
    rows["displayed_value"] = pd.to_numeric(rows["displayed_value"], errors="coerce")
    return rows[rows["displayed_value"].notna()].reset_index(drop=True)


def load_featured_record_overrides(club_id: str | None = None) -> pd.DataFrame:
    """Return approved featured records for the active club, or an empty frame."""
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    if active_club_id != GRDCC_CLUB_ID:
        return pd.DataFrame()

    path = featured_record_override_path(active_club_id)
    if not path.exists():
        return pd.DataFrame()

    overrides = pd.read_csv(path, dtype=str).fillna("")
    required = {"club_id", "metric", "player_name", "authoritative_value", "reviewer_status"}
    if not required.issubset(overrides.columns):
        return pd.DataFrame()

    statuses = overrides["reviewer_status"].astype(str).str.strip().str.casefold()
    club_ids = overrides["club_id"].map(normalize_club_id)
    overrides = overrides[club_ids.eq(active_club_id) & statuses.isin(APPROVED_STATUSES)].copy()
    if overrides.empty:
        return overrides

    overrides["normalized_player_name"] = overrides["player_name"].map(normalize_featured_player_name)
    overrides["authoritative_value"] = pd.to_numeric(overrides["authoritative_value"], errors="coerce")
    return overrides[overrides["authoritative_value"].notna()].reset_index(drop=True)


def apply_featured_record_overrides(
    all_time: pd.DataFrame,
    club_id: str | None = None,
    *,
    add_missing_players: bool = True,
) -> pd.DataFrame:
    """Apply approved overrides to a presentation copy of an all-time table."""
    output = all_time.copy()
    if output.empty or "Player" not in output.columns:
        return output

    normalized_players = output["Player"].map(normalize_featured_player_name)
    supplements = load_override_player_supplements(club_id)
    supplement_alias_map = (
        supplements.drop_duplicates("normalized_player_name").set_index("normalized_player_name")["excel_aliases_used"].to_dict()
        if not supplements.empty and {"normalized_player_name", "excel_aliases_used"}.issubset(supplements.columns)
        else {}
    )
    overrides = load_featured_record_overrides(club_id)
    for _, override in overrides.iterrows():
        metric = str(override.get("metric", "")).strip()
        target_column = METRIC_COLUMNS.get(metric)
        if target_column is None or target_column not in output.columns:
            continue
        normalized_name = str(override["normalized_player_name"])
        variants = _normalized_name_variants(
            override.get("player_name", normalized_name),
            supplement_alias_map.get(normalized_name, ""),
        )
        matches = _match_player_variants(normalized_players, variants)
        if not matches.any():
            continue
        matching_rows = output.loc[matches].copy()
        metric_values = pd.to_numeric(matching_rows[target_column], errors="coerce").fillna(0)
        featured_index = metric_values.idxmax()
        duplicate_indices = matching_rows.index.difference([featured_index])
        if len(duplicate_indices):
            output = output.drop(index=duplicate_indices)
            normalized_players = output["Player"].map(normalize_featured_player_name)
        current_value = pd.to_numeric(pd.Series([output.loc[featured_index, target_column]]), errors="coerce").fillna(0).iloc[0]
        preferred_name = str(override.get("player_name", "") or "").strip()
        if preferred_name:
            output.loc[featured_index, "Player"] = preferred_name
        output.loc[featured_index, target_column] = max(float(current_value), float(override["authoritative_value"]))
        output.loc[featured_index, "Featured Record Override"] = True
        output.loc[featured_index, "Featured Record Metric"] = metric
        output.loc[featured_index, "Featured Record Source"] = str(override.get("annual_report_source", ""))
        output.loc[featured_index, "Featured Record Source Note"] = str(override.get("source_note", ""))
        normalized_players = output["Player"].map(normalize_featured_player_name)

    decisions = load_annual_report_override_decisions(club_id)
    if decisions.empty:
        decisions = load_annual_report_all_time_leaders(club_id).rename(
            columns={"section": "legacy_section"}
        )
    for _, leader in decisions.iterrows():
        metric = str(leader.get("metric", "")).strip()
        target_column = METRIC_COLUMNS.get(metric)
        if target_column is None:
            target_column = ANNUAL_REPORT_LEADER_COLUMNS.get(str(leader.get("legacy_section", "")).strip())
        if target_column is None or target_column not in output.columns:
            continue
        normalized_name = str(leader.get("normalized_player_name", "")).strip()
        variants = _normalized_name_variants(
            leader.get("player_name", normalized_name),
            supplement_alias_map.get(normalized_name, ""),
        )
        matches = _match_player_variants(normalized_players, variants)
        if matches.any():
            matching_rows = output.loc[matches].copy()
            current_values = pd.to_numeric(matching_rows[target_column], errors="coerce").fillna(0)
            featured_index = current_values.idxmax()
            duplicate_indices = matching_rows.index.difference([featured_index])
            if len(duplicate_indices):
                output = output.drop(index=duplicate_indices)
        elif add_missing_players:
            featured_index = len(output)
            output.loc[featured_index, "Player"] = str(leader.get("player_name", "")).strip()
        else:
            continue
        current_value = pd.to_numeric(pd.Series([output.loc[featured_index, target_column]]), errors="coerce").fillna(0).iloc[0]
        preferred_name = str(leader.get("player_name", "") or "").strip()
        if preferred_name:
            output.loc[featured_index, "Player"] = preferred_name
        output.loc[featured_index, target_column] = max(float(current_value), float(leader["displayed_value"]))
        output.loc[featured_index, "Featured Record Override"] = True
        output.loc[featured_index, "Featured Record Metric"] = metric
        output.loc[featured_index, "Featured Record Source"] = "GRDCC 2024/25 Annual Report"
        normalized_players = output["Player"].map(normalize_featured_player_name)
    return apply_override_player_supplements(output, club_id)
