"""Display semantics shared by the three interactive cricket tables."""
import html
import re

import pandas as pd


BATTING_RATES = {"bat sr", "batting sr", "strike rate", "batting strike rate"}
MATCH_COLUMNS = ("Matches", "Mat", "M", "MP", "match_count_for_sort")
COUNTS = {
    "runs", "30s", "50s", "100s", "4s", "6s", "0s", "wickets", "w", "catches", "ct",
    "stumpings", "st", "run outs", "ro", "dismissals", "total dismissals", "dis", "overs",
    "maidens", "innings", "inn", "not outs", "bf", "balls", "balls faced", "balls bowled",
    "3wi", "5wi", "10wm", "wides", "nb", "no balls", "runs conceded",
}


def metric_key(column):
    return re.sub(r"\s*\(ball-by-ball\)$", "", str(column).strip().casefold())


def is_batting_rate(column):
    return metric_key(column) in BATTING_RATES or str(column).strip().casefold() == "sr (ball-by-ball)"


def batting_rate(value):
    number = pd.to_numeric(value, errors="coerce")
    return "" if pd.isna(number) else f"{float(number):.2f}%"


def column_key(column):
    key = "bat sr" if is_batting_rate(column) else str(column).casefold()
    return re.sub(r"[^a-z0-9]+", "-", key.strip()).strip("-") or "column"


def matches_direction(column):
    key = metric_key(column)
    if key in COUNTS:
        return "asc"
    if key in {"win %", "avg", "average", "sr", "eco", "econ", "economy"} | BATTING_RATES or (
        "avg" in key or "sr" in key or "rate" in key or "%" in key
    ):
        return "desc"
    return ""


def sort_attributes(column):
    return f' data-matches-dir="{matches_direction(column)}"'


def row_attributes(row):
    matches = pd.to_numeric(next((row[k] for k in MATCH_COLUMNS if k in row), None), errors="coerce")
    identity = row.get("canonical_player_id", "")
    identity = "" if pd.isna(identity) else str(identity)
    value = "" if pd.isna(matches) else str(float(matches))
    return f' data-match-count="{value}" data-identity="{html.escape(identity, quote=True)}"'


def initial_order(table, primary, label, *, ascending=False, label_value=str):
    if primary not in table or label not in table:
        return table
    order = pd.DataFrame({
        "primary": pd.to_numeric(table[primary], errors="coerce"),
        "label": table[label].map(lambda value: "" if pd.isna(value) else label_value(value).casefold()),
        "identity": table.get("canonical_player_id", pd.Series("", index=table.index)).fillna("").astype(str),
    })
    direction = matches_direction(primary)
    if direction:
        match_column = next((c for c in MATCH_COLUMNS if c in table), None)
        order.insert(1, "matches", pd.to_numeric(table[match_column], errors="coerce") if match_column else float("nan"))
    directions = [ascending] + ([direction == "asc"] if direction else []) + [True, True]
    positions = order.reset_index(drop=True).sort_values(list(order.columns), ascending=directions, kind="stable", na_position="last").index
    return table.iloc[positions]


# Keep secondary direction independent from the clicked primary direction.
TABLE_TIE_JS = """
        const tieBreak = (a, b, index, labelIndex) => {
          const preference = headers.find(h => Number(h.dataset.column) === index)?.dataset.matchesDir;
          const ac = a.children[labelIndex], bc = b.children[labelIndex];
          if (preference) {
            const av = ac.dataset.matchCount === "" ? NaN : Number(ac.dataset.matchCount);
            const bv = bc.dataset.matchCount === "" ? NaN : Number(bc.dataset.matchCount);
            if (Number.isFinite(av) !== Number.isFinite(bv)) return Number.isFinite(av) ? -1 : 1;
            if (Number.isFinite(av) && av !== bv) return preference === "asc" ? av - bv : bv - av;
          }
          return textValue(a, labelIndex).localeCompare(textValue(b, labelIndex), undefined, {sensitivity:"base"})
            || (ac.dataset.identity || "").localeCompare(bc.dataset.identity || "");
        };
"""
