"""Load and apply approved, club-scoped featured-record overrides."""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.data.grdcc_career_refresh import (
    apply_later_season_totals,
    apply_reviewed_playcricket_career_exceptions,
    refresh_baseline_paths,
    report_baselines_path,
)
from src.data.grdcc_career_quarantine import apply_career_quarantine, blocked_report_names, PATH as CAREER_QUARANTINE_PATH

from src.config.club_config import REPO_ROOT, get_active_club_id, get_feature_flag, normalize_club_id


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


def _has_ambiguous_grdcc_identities(rows: pd.DataFrame, club_id: str | None, approved_aliases: str = '') -> bool:
    """Never collapse same-name people without a single verified canonical ID."""
    if normalize_club_id(club_id or get_active_club_id()) != GRDCC_CLUB_ID or len(rows) <= 1:
        return False
    if 'canonical_player_id' not in rows:
        # Legacy report supplements may explicitly identify different spellings
        # of an otherwise unkeyed historical record; identical names are never
        # enough to collapse separate records.
        names = rows['Player'].map(normalize_featured_player_name)
        if approved_aliases.strip() and names.nunique() == len(rows):
            return False
        return True
    ids = rows['canonical_player_id'].fillna('').astype(str).str.strip()
    return ids.eq('').any() or ids.nunique() != 1


def featured_record_override_path(club_id: str | None = None) -> Path:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    return REPO_ROOT / "clubs" / active_club_id / "data" / "source" / "annual_report_featured_record_overrides.csv"


def report_identity_governance_path() -> Path:
    return REPO_ROOT / 'clubs' / GRDCC_CLUB_ID / 'data/source/annual_report_player_identity_governance.csv'


def load_report_identity_governance(club_id: str | None = None) -> pd.DataFrame:
    if normalize_club_id(club_id or get_active_club_id()) != GRDCC_CLUB_ID:
        return pd.DataFrame()
    path = report_identity_governance_path()
    return _load_override_csv(path) if path.exists() else pd.DataFrame()


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


def featured_record_overrides_mtime(club_id: str | None = None) -> float:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    if active_club_id != GRDCC_CLUB_ID or not get_feature_flag(
        "has_annual_report_overrides",
        False,
        club_id=active_club_id,
    ):
        path = featured_record_override_path(active_club_id)
        return path.stat().st_mtime if path.exists() else 0.0
    paths = [
        featured_record_override_path(active_club_id),
        annual_report_all_time_leaders_path(),
        annual_report_override_decisions_path(),
        override_player_supplements_path(),
        report_identity_governance_path(),
        *refresh_baseline_paths(),
        CAREER_QUARANTINE_PATH,
    ]
    return max((path.stat().st_mtime for path in paths if path.exists()), default=0.0)


@lru_cache(maxsize=16)
def _read_override_csv(path_value: str, file_version: float) -> pd.DataFrame:
    del file_version
    return pd.read_csv(path_value, dtype=str).fillna("")


def _load_override_csv(path: Path) -> pd.DataFrame:
    return _read_override_csv(str(path), path.stat().st_mtime).copy()


def _verified_all_grades_report_baselines(club_id: str | None = None) -> pd.DataFrame:
    if normalize_club_id(club_id or get_active_club_id()) != GRDCC_CLUB_ID:
        return pd.DataFrame()
    path = report_baselines_path()
    if not path.exists():
        return pd.DataFrame()
    rows = pd.read_csv(path, dtype=str).fillna("")
    required = {
        "canonical_player_id",
        "player_name",
        "metric",
        "through_season_start",
        "governed_value",
        "status",
        "scope_type",
        "source_reference",
        "source_sha256",
    }
    if not required.issubset(rows.columns):
        return pd.DataFrame()
    rows = rows.loc[
        rows.status.eq("source_verified")
        & rows.scope_type.eq("all_grades_cumulative")
        & rows.through_season_start.eq("2024")
        & rows.metric.isin({"Runs", "Wickets"})
        & rows.canonical_player_id.astype(str).str.strip().ne("")
        & rows.source_sha256.astype(str).str.strip().ne("")
    ].copy()
    expected_page = rows.metric.map({"Runs": "p98", "Wickets": "p100"})
    source_reference = rows.source_reference.astype(str).str.casefold()
    rows = rows.loc[
        source_reference.str.contains("all grades", regex=False)
        & pd.Series(
            [page in reference for page, reference in zip(expected_page, source_reference)],
            index=rows.index,
        )
    ].copy()
    if rows.duplicated(["canonical_player_id", "metric"]).any():
        raise ValueError("Duplicate exact-ID ALL GRADES report baseline")
    rows["_exact_report_name"] = rows.player_name.astype(str).str.strip().str.casefold()
    ambiguous_names = rows.duplicated(["_exact_report_name", "metric"], keep=False)
    return rows.loc[~ambiguous_names].reset_index(drop=True)


def _verified_baseline_for_report_row(
    baselines: pd.DataFrame,
    *,
    player_name: object,
    metric: object,
    page: object,
    value: object,
) -> pd.Series | None:
    metric_name = str(metric or "").strip().casefold()
    baseline_metric = {"runs": "Runs", "career_runs": "Runs", "wickets": "Wickets", "career_wickets": "Wickets"}.get(metric_name)
    if baseline_metric is None:
        return None
    expected_page = {"Runs": "98", "Wickets": "100"}[baseline_metric]
    if str(page or "").strip() != expected_page:
        return None
    exact_name = str(player_name or "").strip().casefold()
    if not exact_name or baselines.empty:
        return None
    matches = baselines.loc[
        baselines._exact_report_name.eq(exact_name)
        & baselines.metric.eq(baseline_metric)
    ]
    if len(matches) != 1:
        return None
    actual = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    expected = pd.to_numeric(pd.Series([matches.iloc[0].governed_value]), errors="coerce").iloc[0]
    return matches.iloc[0] if pd.notna(actual) and pd.notna(expected) and float(actual) == float(expected) else None


def load_annual_report_override_decisions(club_id: str | None = None) -> pd.DataFrame:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    path = annual_report_override_decisions_path()
    if (
        active_club_id != GRDCC_CLUB_ID
        or not get_feature_flag("has_annual_report_overrides", False, club_id=active_club_id)
        or not path.exists()
    ):
        return pd.DataFrame()
    rows = _load_override_csv(path)
    required = {
        "player_name",
        "normalized_player_name",
        "metric",
        "displayed_value",
        "validation_status",
        "override_applies",
        "annual_report_pages",
    }
    if not required.issubset(rows.columns):
        return pd.DataFrame()
    rows = rows[
        rows["validation_status"].astype(str).str.casefold().eq("pass")
        & rows["override_applies"].astype(str).str.strip().str.casefold().eq("yes")
    ].copy()
    rows["displayed_value"] = pd.to_numeric(rows["displayed_value"], errors="coerce")
    baselines = _verified_all_grades_report_baselines(active_club_id)
    table = load_annual_report_all_time_leaders(active_club_id)
    if baselines.empty or table.empty:
        return pd.DataFrame()

    accepted = []
    for _, row in rows.loc[rows["displayed_value"].notna()].iterrows():
        baseline = _verified_baseline_for_report_row(
            baselines,
            player_name=row.get("player_name"),
            metric=row.get("metric"),
            page=row.get("annual_report_pages"),
            value=row.get("displayed_value"),
        )
        if baseline is None:
            continue
        same_table_row = table.loc[
            table.player_name.astype(str).str.strip().str.casefold().eq(
                str(row.get("player_name", "")).strip().casefold()
            )
            & table.metric.astype(str).str.casefold().eq(
                {"career_runs": "runs", "career_wickets": "wickets"}.get(
                    str(row.get("metric", "")).strip().casefold(), ""
                )
            )
            & table.annual_report_page.astype(str).str.strip().eq(
                str(row.get("annual_report_pages", "")).strip()
            )
            & pd.to_numeric(table["displayed_value"], errors="coerce").eq(
                float(row["displayed_value"])
            )
        ]
        if len(same_table_row) != 1:
            continue
        accepted_row = row.copy()
        accepted_row["canonical_player_id"] = baseline.canonical_player_id
        accepted_row["scope_type"] = baseline.scope_type
        accepted_row["through_season_start"] = baseline.through_season_start
        accepted_row["source_sha256"] = baseline.source_sha256
        accepted.append(accepted_row)
    return pd.DataFrame(accepted).reset_index(drop=True)


def _verified_legacy_career_target(leader: pd.Series, target_column: str) -> str:
    """Return an exact target only for a verified cumulative report baseline."""
    metric_page = {"Runs": "98", "Wickets": "100"}.get(target_column)
    if metric_page is None:
        return ""
    if str(leader.get("scope_type", "")).strip() != "all_grades_cumulative":
        return ""
    if str(leader.get("through_season_start", "")).strip() != "2024":
        return ""
    if not str(leader.get("source_sha256", "")).strip():
        return ""
    page = str(leader.get("annual_report_pages", leader.get("annual_report_page", ""))).strip()
    if page != metric_page:
        return ""
    return str(leader.get("canonical_player_id", "")).strip()


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
    if (
        active_club_id != GRDCC_CLUB_ID
        or not get_feature_flag("has_annual_report_overrides", False, club_id=active_club_id)
        or not path.exists()
    ):
        return pd.DataFrame()
    rows = _load_override_csv(path)
    required = {"player_name", "normalized_player_name"}
    if not required.issubset(rows.columns):
        return pd.DataFrame()
    for column in SUPPLEMENT_NUMERIC_COLUMNS.intersection(rows.columns):
        rows[column] = pd.to_numeric(rows[column], errors="coerce")
    for column in ['override_metric','override_applies']:
        if column not in rows:rows[column]=''
    rows['_wicket_override_applies'] = rows.override_metric.eq('career_wickets') & rows.override_applies.eq('yes')
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
                "override_metric": lambda values: '; '.join(sorted(set(values.astype(str)) - {''})),
                "override_applies": lambda values: 'yes' if values.eq('yes').any() else 'no',
                "_wicket_override_applies": 'any',
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


def _is_missing_override_value(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, (dict, list, tuple, set)):
        return False
    try:
        missing = pd.isna(value)
    except (TypeError, ValueError):
        return False
    if isinstance(missing, bool):
        return missing
    return False


def _format_override_string(value: object) -> str:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if not pd.isna(numeric) and float(numeric).is_integer():
        return str(int(numeric))
    return str(value)


def _coerce_override_value_for_column(value: object, target_series: pd.Series | None) -> object:
    if _is_missing_override_value(value):
        return pd.NA
    if target_series is None:
        return value

    dtype = target_series.dtype
    if pd.api.types.is_bool_dtype(dtype):
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes", "y"}
        return bool(value)
    if pd.api.types.is_numeric_dtype(dtype):
        numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
        return pd.NA if pd.isna(numeric) else numeric
    if pd.api.types.is_string_dtype(dtype) or str(dtype).startswith("string"):
        return _format_override_string(value)
    return value


def _assign_override_value(output: pd.DataFrame, index: object, column: str, value: object) -> None:
    target_series = output[column] if column in output.columns else None
    coerced = _coerce_override_value_for_column(value, target_series)
    if column in output.columns and (
        pd.api.types.is_string_dtype(output[column].dtype)
        or str(output[column].dtype).startswith("string")
    ):
        output[column] = output[column].astype(object)
    output.loc[index, column] = coerced


def _strongest_high_score(values: pd.Series) -> object:
    """Keep the not-out flag attached to the highest evidenced score."""
    candidates = []
    for value in values:
        match = re.fullmatch(r"\s*(\d+)(?:\.0+)?(\*)?\s*", str(value))
        if match:
            candidates.append((int(match.group(1)), bool(match.group(2))))
    if not candidates:
        return pd.NA
    runs, not_out = max(candidates)
    return f"{runs}{'*' if not_out else ''}"


def _preserve_merged_high_score(output: pd.DataFrame, index: object, rows: pd.DataFrame) -> None:
    if "HS" in rows:
        value = _strongest_high_score(rows["HS"])
        if pd.notna(value):
            output["HS"] = output["HS"].astype(object)
            output.loc[index, "HS"] = value


def _extend_career_span(output: pd.DataFrame, index: object, seasons: list[str]) -> None:
    existing = []
    for column in ("Seasons", "Debut Season", "Latest Season"):
        if column in output:
            existing.extend(_season_list(output.loc[index, column]))
    supplied = [part for value in seasons for part in _season_list(value)]
    known = sorted({s for s in existing + supplied if _season_sort_key(s) != 999999}, key=_season_sort_key)
    if not known:
        return
    for column, value in (("Debut Season", known[0]), ("Latest Season", known[-1]),
                          ("Career Span", _career_span_from_seasons(', '.join(known)))):
        if column in output:
            _assign_override_value(output, index, column, value)
    if "Seasons" in output:
        _assign_override_value(output, index, "Seasons", ', '.join(known))
    for column in ("Seasons Played", "Seasons Count"):
        if column in output:
            current = pd.to_numeric(output.loc[index, column], errors='coerce')
            _assign_override_value(output, index, column, max(len(known), current if pd.notna(current) else 0))


def apply_override_player_supplements(all_time: pd.DataFrame, club_id: str | None = None) -> pd.DataFrame:
    output = apply_career_quarantine(all_time,club_id).copy()
    if output.empty or "Player" not in output.columns:
        return output
    supplements = load_override_player_supplements(club_id)
    if supplements.empty:
        return output

    normalized_players = output["Player"].map(normalize_featured_player_name)
    for _, supplement in supplements.iterrows():
        if str(supplement.get('player_name','')).strip().casefold() in blocked_report_names(club_id):
            continue
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
            "Bat Avg": _supplement_value(supplement, "excel_batting_average"),
            "50s": _supplement_value(supplement, "excel_50s"),
            "100s": _supplement_value(supplement, "excel_100s"),
            "Maidens": _supplement_value(supplement, "excel_maidens"),
            "Bowl Avg": _supplement_value(supplement, "excel_bowling_average"),
            "Bowl SR": _supplement_value(supplement, "excel_bowling_strike_rate"),
            "Balls Bowled": _supplement_value(supplement, "excel_balls"),
        }
        if numeric_updates.get("Innings") is not None and "Innings" not in output.columns:
            output["Innings"] = pd.NA
        for column, value in numeric_updates.items():
            if value is None or column not in output.columns:
                continue
            _assign_override_value(output, index, column, value)
        if "HS" in output:
            # A historical supplement must not lower a governed career record.
            hs = _strongest_high_score(pd.Series([output.loc[index, "HS"], supplement.get("excel_hs")]))
            if pd.notna(hs):
                output["HS"] = output["HS"].astype(object)
                output.loc[index, "HS"] = hs
        if "Overs" in output.columns and numeric_updates.get("Balls Bowled") is not None:
            _assign_override_value(output, index, "Overs", _balls_to_overs_display(numeric_updates["Balls Bowled"]))
        # Preserve scope metadata for audit. Reviewed exact-ID quarantine below
        # is the compatibility guard; do not retroactively alter unaudited aliases.
        _assign_override_value(output, index, "Matches Source", str(supplement.get("matches_source", "") or ""))
        _assign_override_value(
            output,
            index,
            "Matches Proxy",
            "Yes" if str(supplement.get("matches_source", "")).strip().casefold() == "innings_proxy" else "",
        )

        innings = _supplement_value(supplement, "excel_innings")
        not_outs = _supplement_value(supplement, "excel_not_outs")
        if innings is not None and not_outs is not None and "Outs" in output.columns:
            _assign_override_value(output, index, "Outs", max(float(innings) - float(not_outs), 0.0))

        seasons_text = _first_non_empty(pd.Series([supplement.get("excel_seasons", "")]))
        seasons = sorted(_season_list(seasons_text), key=_season_sort_key)
        _extend_career_span(output, index, seasons)
        if "Featured Record Source" in output.columns:
            _assign_override_value(output, index, "Featured Record Source", "GRDCC 2024/25 Annual Report")
        preferred_name = str(supplement.get("player_name", "") or "").strip()
        if preferred_name:
            _assign_override_value(output, index, "Player", preferred_name)
    return apply_career_quarantine(output,club_id)


def load_annual_report_all_time_leaders(club_id: str | None = None) -> pd.DataFrame:
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    path = annual_report_all_time_leaders_path()
    if (
        active_club_id != GRDCC_CLUB_ID
        or not get_feature_flag("has_annual_report_overrides", False, club_id=active_club_id)
        or not path.exists()
    ):
        return pd.DataFrame()
    rows = _load_override_csv(path)
    required = {
        "section",
        "metric",
        "player_name",
        "normalized_player_name",
        "displayed_value",
        "annual_report_value",
        "annual_report_page",
        "included_in_app",
    }
    if not required.issubset(rows.columns):
        return pd.DataFrame()
    included = rows["included_in_app"].astype(str).str.strip().str.casefold().isin({"1", "true", "yes"})
    rows = rows[included].copy()
    rows["displayed_value"] = pd.to_numeric(rows["displayed_value"], errors="coerce")
    rows["annual_report_value"] = pd.to_numeric(rows["annual_report_value"], errors="coerce")
    baselines = _verified_all_grades_report_baselines(active_club_id)
    if baselines.empty:
        return pd.DataFrame()

    accepted = []
    for _, row in rows.loc[rows["annual_report_value"].notna()].iterrows():
        metric_name = str(row.get("metric", "")).strip().casefold()
        expected_section = {"runs": "most_runs", "wickets": "most_wickets"}.get(metric_name)
        if expected_section is None or str(row.get("section", "")).strip().casefold() != expected_section:
            continue
        baseline = _verified_baseline_for_report_row(
            baselines,
            player_name=row.get("player_name"),
            metric=metric_name,
            page=row.get("annual_report_page"),
            value=row.get("annual_report_value"),
        )
        if baseline is None:
            continue
        accepted_row = row.copy()
        accepted_row["canonical_player_id"] = baseline.canonical_player_id
        accepted_row["scope_type"] = baseline.scope_type
        accepted_row["through_season_start"] = baseline.through_season_start
        accepted_row["source_sha256"] = baseline.source_sha256
        # The current app extraction may contain a computed value; the report
        # figure remains authoritative for its historical cutoff.
        accepted_row["displayed_value"] = float(baseline.governed_value)
        accepted.append(accepted_row)
    result = pd.DataFrame(accepted).reset_index(drop=True)
    if not result.empty and result.duplicated(["canonical_player_id", "metric"]).any():
        raise ValueError("Annual Report HOF rows must map to unique verified canonical metrics")
    return result


def load_featured_record_overrides(club_id: str | None = None) -> pd.DataFrame:
    """Return approved featured records for the active club, or an empty frame."""
    active_club_id = normalize_club_id(club_id or get_active_club_id())
    if active_club_id != GRDCC_CLUB_ID or not get_feature_flag(
        "has_annual_report_overrides",
        False,
        club_id=active_club_id,
    ):
        return pd.DataFrame()

    path = featured_record_override_path(active_club_id)
    if not path.exists():
        return pd.DataFrame()

    overrides = _load_override_csv(path)
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
    output = apply_career_quarantine(all_time,club_id).copy()
    if output.empty or "Player" not in output.columns:
        return output

    identity_decisions = load_report_identity_governance(club_id)
    held_names = set()
    approved_targets: dict[str, set[str]] = {}
    for _, identity in identity_decisions.iterrows():
        report_name = str(identity.get('report_name', '')).strip()
        status = identity.get('status', '')
        if status in {'NEEDS_CLUB_CONFIRMATION', 'DUPLICATE_REPORT_RECORD'}:
            held_names.add(normalize_featured_player_name(report_name))
        elif status == 'MATCHED_EXISTING_CANONICAL_PLAYER' and 'canonical_player_id' in output:
            approved_targets.setdefault(normalize_featured_player_name(report_name), set()).add(str(identity.get('canonical_player_id', '')).strip())
            matched = output['canonical_player_id'].astype(str).eq(identity.get('canonical_player_id', ''))
            if matched.sum() == 1:
                output.loc[matched, 'Player'] = report_name

    normalized_players = output["Player"].map(normalize_featured_player_name)
    supplements = load_override_player_supplements(club_id)
    supplement_alias_map = (
        supplements.drop_duplicates("normalized_player_name").set_index("normalized_player_name")["excel_aliases_used"].to_dict()
        if not supplements.empty and {"normalized_player_name", "excel_aliases_used"}.issubset(supplements.columns)
        else {}
    )
    overrides = load_featured_record_overrides(club_id)
    for _, override in overrides.iterrows():
        if str(override.get('player_name','')).strip().casefold() in blocked_report_names(club_id):
            continue
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
        if _has_ambiguous_grdcc_identities(matching_rows, club_id, str(supplement_alias_map.get(normalized_name, ''))):
            ids = approved_targets.get(normalize_featured_player_name(override.get('player_name', normalized_name)), set()) - {''}
            if len(ids) != 1 or 'canonical_player_id' not in matching_rows:
                continue
            matching_rows = matching_rows.loc[matching_rows.canonical_player_id.astype(str).isin(ids)]
            if len(matching_rows) != 1:
                continue
        metric_values = pd.to_numeric(matching_rows[target_column], errors="coerce").fillna(0)
        featured_index = metric_values.idxmax()
        _preserve_merged_high_score(output, featured_index, matching_rows)
        _extend_career_span(output, featured_index, [str(v) for c in ("Debut Season", "Latest Season", "Seasons") if c in matching_rows for v in matching_rows[c].dropna()])
        duplicate_indices = matching_rows.index.difference([featured_index])
        if len(duplicate_indices):
            output = output.drop(index=duplicate_indices)
            normalized_players = output["Player"].map(normalize_featured_player_name)
        current_value = pd.to_numeric(pd.Series([output.loc[featured_index, target_column]]), errors="coerce").fillna(0).iloc[0]
        preferred_name = str(override.get("player_name", "") or "").strip()
        if preferred_name:
            _assign_override_value(output, featured_index, "Player", preferred_name)
        _assign_override_value(output, featured_index, target_column, max(float(current_value), float(override["authoritative_value"])))
        _assign_override_value(output, featured_index, "Featured Record Override", True)
        _assign_override_value(output, featured_index, "Featured Record Metric", metric)
        _assign_override_value(output, featured_index, "Featured Record Source", str(override.get("annual_report_source", "")))
        _assign_override_value(output, featured_index, "Featured Record Source Note", str(override.get("source_note", "")))
        normalized_players = output["Player"].map(normalize_featured_player_name)

    decisions = load_annual_report_override_decisions(club_id)
    if decisions.empty:
        decisions = load_annual_report_all_time_leaders(club_id).rename(
            columns={"section": "legacy_section"}
        )
    for _, leader in decisions.iterrows():
        if str(leader.get('player_name','')).strip().casefold() in blocked_report_names(club_id):
            continue
        if normalize_featured_player_name(leader.get('player_name', '')) in held_names:
            continue
        metric = str(leader.get("metric", "")).strip()
        target_column = METRIC_COLUMNS.get(metric)
        if target_column is None:
            target_column = ANNUAL_REPORT_LEADER_COLUMNS.get(str(leader.get("legacy_section", "")).strip())
        if target_column is None or target_column not in output.columns:
            continue
        canonical_player_id = _verified_legacy_career_target(leader, target_column)
        if not canonical_player_id or "canonical_player_id" not in output.columns:
            continue
        matches = output.canonical_player_id.fillna("").astype(str).eq(canonical_player_id)
        if int(matches.sum()) != 1:
            continue
        matching_rows = output.loc[matches].copy()
        featured_index = matching_rows.index[0]
        _preserve_merged_high_score(output, featured_index, matching_rows)
        _extend_career_span(output, featured_index, [str(v) for c in ("Debut Season", "Latest Season", "Seasons") if c in matching_rows for v in matching_rows[c].dropna()])
        current_value = pd.to_numeric(pd.Series([output.loc[featured_index, target_column]]), errors="coerce").fillna(0).iloc[0]
        preferred_name = str(leader.get("player_name", "") or "").strip()
        if preferred_name:
            _assign_override_value(output, featured_index, "Player", preferred_name)
        _assign_override_value(output, featured_index, target_column, max(float(current_value), float(leader["displayed_value"])))
        _assign_override_value(output, featured_index, "Featured Record Override", True)
        _assign_override_value(output, featured_index, "Featured Record Metric", metric)
        _assign_override_value(output, featured_index, "Featured Record Source", "GRDCC 2024/25 Annual Report")
        normalized_players = output["Player"].map(normalize_featured_player_name)
    from src.data.grdcc_historical_records import apply_historical_records
    governed = apply_historical_records(apply_career_quarantine(apply_later_season_totals(
        apply_override_player_supplements(output, club_id),
        club_id or get_active_club_id(), source_frame=all_time,
    ),club_id), club_id, add_report_records=add_missing_players)
    # Reviewed exact-ID exceptions must win after legacy supplements and career overlays.
    return apply_reviewed_playcricket_career_exceptions(governed, club_id or get_active_club_id())
