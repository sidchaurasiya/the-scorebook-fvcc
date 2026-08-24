"""Display-only Not Outs coverage helpers.

These helpers never recalculate batting averages. They preserve the difference
between a genuine zero and unavailable source data.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


NOT_OUTS_COMPLETE = "complete"
NOT_OUTS_PARTIAL = "partial"
NOT_OUTS_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class NotOutsCoverage:
    value: float | None
    status: str
    rows: int
    populated_rows: int


def not_outs_coverage(frame: pd.DataFrame, column: str = "battingNotOuts") -> NotOutsCoverage:
    if frame.empty or column not in frame:
        return NotOutsCoverage(None, NOT_OUTS_UNAVAILABLE, len(frame), 0)
    values = pd.to_numeric(frame[column], errors="coerce")
    populated = int(values.notna().sum())
    if populated == 0:
        return NotOutsCoverage(None, NOT_OUTS_UNAVAILABLE, len(frame), 0)
    status = NOT_OUTS_COMPLETE if populated == len(frame) else NOT_OUTS_PARTIAL
    return NotOutsCoverage(float(values.sum(min_count=1)), status, len(frame), populated)


def historical_excel_mask(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(False, index=frame.index, dtype=bool)
    source_system = frame.get("source_system", pd.Series("", index=frame.index)).fillna("").astype(str)
    raw_ids = frame.get("raw_player_id", pd.Series("", index=frame.index)).fillna("").astype(str)
    return source_system.str.casefold().eq("excel") | raw_ids.str.startswith("excel_")


def profile_not_outs_coverage(frame: pd.DataFrame, club_id: str) -> NotOutsCoverage:
    if str(club_id).strip().casefold() != "georges-river-district":
        return not_outs_coverage(frame)
    historical = historical_excel_mask(frame)
    digital = frame.loc[~historical].copy()
    coverage = not_outs_coverage(digital)
    if not historical.any():
        return coverage
    status = NOT_OUTS_PARTIAL if coverage.value is not None else NOT_OUTS_UNAVAILABLE
    return NotOutsCoverage(coverage.value, status, len(frame), coverage.populated_rows)


def mask_historical_not_outs(frame: pd.DataFrame, club_id: str) -> pd.DataFrame:
    output = frame.copy()
    if str(club_id).strip().casefold() != "georges-river-district" or "battingNotOuts" not in output:
        return output
    output.loc[historical_excel_mask(output), "battingNotOuts"] = pd.NA
    return output


def complete_not_outs_by_player(batting: pd.DataFrame) -> pd.DataFrame:
    """Return player totals only where every contributing row has coverage."""
    columns = ["canonical_player_id", "Not Outs"]
    if batting.empty or not {"canonical_player_id", "battingNotOuts"}.issubset(batting.columns):
        return pd.DataFrame(columns=columns)
    source = batting[["canonical_player_id", "battingNotOuts"]].copy()
    source["battingNotOuts"] = pd.to_numeric(source["battingNotOuts"], errors="coerce")
    grouped = source.groupby("canonical_player_id", dropna=False)["battingNotOuts"].agg(
        rows="size",
        populated="count",
        total=lambda values: values.sum(min_count=1),
    )
    grouped = grouped[grouped["rows"].eq(grouped["populated"]) & grouped["total"].notna()].reset_index()
    return grouped.rename(columns={"total": "Not Outs"})[columns]


def add_complete_not_outs_for_display(all_time: pd.DataFrame, batting: pd.DataFrame) -> pd.DataFrame:
    """Attach complete Not Outs totals without changing order or other metrics."""
    if all_time.empty or "canonical_player_id" not in all_time:
        return all_time.copy()
    totals = complete_not_outs_by_player(batting)
    if totals.empty:
        return all_time.copy()
    output = all_time.drop(columns=["Not Outs"], errors="ignore").copy()
    output["_not_out_row_order"] = range(len(output))
    output = output.merge(totals, on="canonical_player_id", how="left", sort=False)
    return output.sort_values("_not_out_row_order").drop(columns="_not_out_row_order").reset_index(drop=True)
