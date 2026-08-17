from __future__ import annotations

import re

import pandas as pd

from src.utils.player_identity import canonical_group_key


def format_high_score(row: pd.Series) -> str:
    score = row.get("battingHighScore")
    if pd.isna(score):
        return "-"

    suffix = "*" if _as_bool(row.get("isBattingHSNotOut")) else ""
    return f"{int(score)}{suffix}"


def _as_bool(value: object) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, str):
        return value.strip().casefold() in {"true", "1", "yes", "y", "not out", "notout"}
    return bool(value)


def add_batting_display_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    output = df.copy()
    output["high_score"] = output.apply(format_high_score, axis=1)
    return output


def build_club_snapshot(
    batting_df: pd.DataFrame,
    bowling_df: pd.DataFrame,
    champion_df: pd.DataFrame,
) -> dict[str, int]:
    players = set()
    for frame in [batting_df, bowling_df, champion_df]:
        if not frame.empty and "player_name" in frame:
            players.update(frame["player_name"].dropna().tolist())

    return {
        "players": len(players),
        "matches": int(champion_df["matches"].max()) if "matches" in champion_df else 0,
        "runs": int(batting_df["battingAggregate"].sum())
        if "battingAggregate" in batting_df
        else 0,
        "wickets": int(bowling_df["bowlingWickets"].sum())
        if "bowlingWickets" in bowling_df
        else 0,
    }


def combine_player_rows(df: pd.DataFrame, category: str) -> pd.DataFrame:
    """Merge whole-club rows when the same player appears in multiple teams."""
    if df.empty or "player_name" not in df:
        return df

    output_rows = []
    group_key = _build_player_group_key(df)

    for _, group in df.groupby(group_key, dropna=False, sort=False):
        row = _first_identity_values(group)
        row.update(_joined_labels(group))
        row.update(_summed_stat_values(group))
        row.update(_best_batting_score(group))
        row.update(_best_bowling_figures(group))
        _recalculate_derived_stats(row, group, category)
        output_rows.append(row)

    return pd.DataFrame(output_rows)


def _build_player_group_key(df: pd.DataFrame) -> pd.Series:
    if "canonical_player_id" in df:
        return canonical_group_key(df)

    fallback = df["player_name"].fillna("").astype(str).str.strip().str.casefold()
    if "player_id" not in df:
        return fallback

    player_id = df["player_id"].fillna("").astype(str).str.strip()
    return player_id.where(player_id != "", fallback)


def _first_identity_values(group: pd.DataFrame) -> dict[str, object]:
    identity_columns = [
        "player_id",
        "player_name",
        "short_name",
        "club",
        "raw_player_id",
        "raw_player_name",
        "canonical_player_id",
        "canonical_player_name",
    ]
    row = {}

    for column in identity_columns:
        if column in group:
            value = group[column].dropna()
            row[column] = value.iloc[0] if not value.empty else None

    if row.get("canonical_player_name"):
        row["player_name"] = row["canonical_player_name"]
    if row.get("canonical_player_id"):
        row["player_id"] = row["canonical_player_id"]

    return row


def _joined_labels(group: pd.DataFrame) -> dict[str, str]:
    labels = {}
    for column in ["team_id", "team_name", "grade_id", "grade_name"]:
        if column in group:
            values = [
                str(value)
                for value in group[column].dropna().drop_duplicates().tolist()
                if str(value).strip()
            ]
            labels[column] = ", ".join(values)

    return labels


def _summed_stat_values(group: pd.DataFrame) -> dict[str, object]:
    skipped_columns = {
        "player_id",
        "player_name",
        "short_name",
        "club",
        "team_id",
        "team_name",
        "grade_id",
        "grade_name",
        "battingAverage",
        "battingStrikeRate",
        "battingHighScore",
        "isBattingHSNotOut",
        "high_score",
        "bowlingAverage",
        "bowlingEconomyRate",
        "bowlingBestInnings",
    }
    totals = {}

    for column in group.columns:
        if column in skipped_columns:
            continue

        numeric_values = pd.to_numeric(group[column], errors="coerce")
        if numeric_values.notna().any():
            totals[column] = numeric_values.sum()

    return totals


def _best_batting_score(group: pd.DataFrame) -> dict[str, object]:
    if "battingHighScore" not in group:
        return {}

    scores = pd.to_numeric(group["battingHighScore"], errors="coerce")
    if not scores.notna().any():
        return {}

    sort_frame = group.copy()
    sort_frame["_score_sort"] = scores
    sort_frame["_not_out_sort"] = group["isBattingHSNotOut"].map(_as_bool) if "isBattingHSNotOut" in group else False
    best_index = sort_frame.sort_values(["_score_sort", "_not_out_sort"], ascending=[False, False]).index[0]
    is_not_out = False
    if "isBattingHSNotOut" in group:
        is_not_out = _as_bool(group.loc[best_index, "isBattingHSNotOut"])

    return {
        "battingHighScore": scores.loc[best_index],
        "isBattingHSNotOut": is_not_out,
    }


def _best_bowling_figures(group: pd.DataFrame) -> dict[str, object]:
    if "bowlingBestInnings" not in group:
        return {}

    figures = group["bowlingBestInnings"].dropna()
    if figures.empty:
        return {}

    best = max(figures.astype(str), key=_bowling_figure_sort_key)
    return {"bowlingBestInnings": best}


def _bowling_figure_sort_key(value: str) -> tuple[int, int]:
    match = re.search(r"(\d+)\s*[-/]\s*(\d+)", value)
    if not match:
        return (0, 0)

    wickets = int(match.group(1))
    runs = int(match.group(2))
    return (wickets, -runs)


def _recalculate_derived_stats(
    row: dict[str, object],
    group: pd.DataFrame,
    category: str,
) -> None:
    if category == "batting":
        _recalculate_batting_stats(row, group)
    elif category == "bowling":
        _recalculate_bowling_stats(row, group)


def _recalculate_batting_stats(row: dict[str, object], group: pd.DataFrame) -> None:
    runs = _number(row.get("battingAggregate"))
    balls = _number(row.get("ballsFaced") or row.get("battingBallsFaced"))
    innings = _number(row.get("innings") or row.get("battingInnings"))
    not_outs = _number(row.get("notOuts") or row.get("battingNotOuts"))

    dismissals = innings - not_outs
    if runs is not None and dismissals and dismissals > 0:
        row["battingAverage"] = runs / dismissals
    elif "battingAverage" in group:
        row["battingAverage"] = _weighted_average(group, "battingAverage", "matches")

    if runs is not None and balls and balls > 0:
        row["battingStrikeRate"] = runs / balls * 100
    elif "battingStrikeRate" in group:
        row["battingStrikeRate"] = _weighted_average(group, "battingStrikeRate", "matches")


def _recalculate_bowling_stats(row: dict[str, object], group: pd.DataFrame) -> None:
    wickets = _number(row.get("bowlingWickets"))
    runs_conceded = _number(
        row.get("bowlingRunsConceded")
        or row.get("bowlingRuns")
        or row.get("runsConceded")
        or row.get("runs_conceded")
    )
    overs_notation = row.get("overs") or row.get("bowlingOvers") or row.get("oversBowled")
    overs = _decimal_overs(overs_notation)
    balls = _number(row.get("ballsBowled") or row.get("bowlingBalls") or row.get("bowlingBallsBowled"))
    if balls is not None:
        overs = balls / 6

    if wickets and wickets > 0 and runs_conceded is not None:
        row["bowlingAverage"] = runs_conceded / wickets
    elif "bowlingAverage" in group:
        row["bowlingAverage"] = _weighted_average(group, "bowlingAverage", "matches")

    if overs and overs > 0 and runs_conceded is not None:
        row["bowlingEconomyRate"] = runs_conceded / overs
    elif "bowlingEconomyRate" in group:
        row["bowlingEconomyRate"] = _weighted_average(
            group,
            "bowlingEconomyRate",
            "matches",
        )

    if wickets and wickets > 0 and balls is not None:
        row["bowlingStrikeRate"] = balls / wickets
    elif "bowlingStrikeRate" in group:
        row["bowlingStrikeRate"] = _weighted_average(
            group,
            "bowlingStrikeRate",
            "bowlingWickets",
        )


def _decimal_overs(value: object) -> float | None:
    """Convert cricket over notation (for example 3.5) to decimal overs."""
    if value is None or pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        whole_text, _, ball_text = text.partition(".")
        whole = int(whole_text)
        balls = int(ball_text or "0")
    except (TypeError, ValueError):
        return None
    if whole < 0 or balls < 0 or balls > 5:
        return None
    return (whole * 6 + balls) / 6

def _weighted_average(
    group: pd.DataFrame,
    value_column: str,
    weight_column: str,
) -> float | None:
    values = pd.to_numeric(group[value_column], errors="coerce")
    if weight_column in group:
        weights = pd.to_numeric(group[weight_column], errors="coerce").fillna(0)
    else:
        weights = pd.Series([1] * len(group), index=group.index)

    valid = values.notna() & (weights > 0)
    if not valid.any():
        return None

    return (values[valid] * weights[valid]).sum() / weights[valid].sum()


def _number(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def top_rows(df: pd.DataFrame, sort_column: str, limit: int = 10) -> pd.DataFrame:
    if df.empty or sort_column not in df:
        return df.head(0)

    return df.sort_values(sort_column, ascending=False).head(limit)
