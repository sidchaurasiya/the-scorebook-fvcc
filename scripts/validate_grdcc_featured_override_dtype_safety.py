from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT_PATH = Path(__file__).resolve().parents[1]
if str(REPO_ROOT_PATH) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_PATH))

os.environ.setdefault("CLUB_ID", "georges-river-district")
os.environ.setdefault("SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES", "false")

from src.config.club_config import REPO_ROOT  # noqa: E402
from src.data.featured_record_overrides import (  # noqa: E402
    _assign_override_value,
    _balls_to_overs_display,
    _coerce_override_value_for_column,
    _match_player_variants,
    _normalized_name_variants,
    _supplement_value,
    apply_featured_record_overrides,
    load_override_player_supplements,
    normalize_featured_player_name,
)
from src.data.playcricket_ingestion import metadata_mtime  # noqa: E402
from src.ui.layout import load_hall_of_fame_data  # noqa: E402
from src.utils.player_identity import player_aliases_mtime  # noqa: E402


CLUB_ID = "georges-river-district"
OUTPUT_PATH = (
    REPO_ROOT
    / "clubs"
    / CLUB_ID
    / "data"
    / "processed"
    / "validation"
    / "grdcc_featured_override_dtype_safety_validation.csv"
)


def _arrow_like_copy(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in output.columns:
        if pd.api.types.is_object_dtype(output[column].dtype) or pd.api.types.is_string_dtype(output[column].dtype):
            try:
                output[column] = output[column].astype("string[pyarrow]")
            except (ImportError, TypeError, ValueError):
                output[column] = output[column].astype("string")
    return output


def _record_assignment(
    rows: list[dict[str, object]],
    output: pd.DataFrame,
    index: object,
    player_name: str,
    column: str,
    value: object,
    source: str,
) -> None:
    target = output[column] if column in output.columns else None
    target_dtype = str(target.dtype) if target is not None else "<new column>"
    try:
        coerced = _coerce_override_value_for_column(value, target)
        scratch = output.copy()
        _assign_override_value(scratch, index, column, value)
        status = "pass"
        error = ""
    except Exception as exc:  # noqa: BLE001 - validator should capture the exact dtype failure.
        coerced = ""
        status = "fail"
        error = f"{type(exc).__name__}: {exc}"
    rows.append(
        {
            "player_name": player_name,
            "source": source,
            "column": column,
            "target_dtype": target_dtype,
            "raw_value": "" if value is pd.NA else value,
            "raw_value_type": type(value).__name__,
            "coerced_value": "" if coerced is pd.NA else coerced,
            "coerced_value_type": type(coerced).__name__,
            "validation_status": status,
            "notes": error,
        }
    )


def main() -> int:
    historical = load_hall_of_fame_data(
        metadata_mtime(),
        player_aliases_mtime(club_id=CLUB_ID),
        club_id=CLUB_ID,
    )
    if not historical or "all_time" not in historical:
        raise RuntimeError("Unable to load GRDCC all-time Hall of Fame source data")

    all_time = _arrow_like_copy(historical["all_time"])
    rows: list[dict[str, object]] = []

    supplements = load_override_player_supplements(CLUB_ID)
    normalized_players = all_time["Player"].map(normalize_featured_player_name)
    for _, supplement in supplements.iterrows():
        variants = _normalized_name_variants(
            supplement.get("player_name", supplement.get("normalized_player_name", "")),
            supplement.get("excel_aliases_used", ""),
        )
        matches = _match_player_variants(normalized_players, variants)
        if not matches.any():
            continue
        index = all_time.index[matches][0]
        player_name = str(all_time.loc[index, "Player"])
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
        for column, value in numeric_updates.items():
            if value is not None and column in all_time.columns:
                _record_assignment(rows, all_time, index, player_name, column, value, "player_supplement")
        if "Overs" in all_time.columns and numeric_updates.get("Balls Bowled") is not None:
            _record_assignment(
                rows,
                all_time,
                index,
                player_name,
                "Overs",
                _balls_to_overs_display(numeric_updates["Balls Bowled"]),
                "player_supplement",
            )
        for column, value in {
            "Matches Source": str(supplement.get("matches_source", "") or ""),
            "Matches Proxy": "Yes"
            if str(supplement.get("matches_source", "")).strip().casefold() == "innings_proxy"
            else "",
            "Featured Record Source": "GRDCC 2024/25 Annual Report",
            "Player": str(supplement.get("player_name", "") or "").strip(),
        }.items():
            if value:
                _record_assignment(rows, all_time, index, player_name, column, value, "player_supplement")

    try:
        result = apply_featured_record_overrides(all_time.copy(), club_id=CLUB_ID)
        rows.append(
            {
                "player_name": "<all>",
                "source": "apply_featured_record_overrides",
                "column": "<all>",
                "target_dtype": "<mixed>",
                "raw_value": "",
                "raw_value_type": "",
                "coerced_value": len(result),
                "coerced_value_type": "int",
                "validation_status": "pass",
                "notes": "featured override path completed with Arrow-like string columns",
            }
        )
    except Exception as exc:  # noqa: BLE001 - validator should preserve the production-style failure.
        rows.append(
            {
                "player_name": "<all>",
                "source": "apply_featured_record_overrides",
                "column": "<all>",
                "target_dtype": "<mixed>",
                "raw_value": "",
                "raw_value_type": "",
                "coerced_value": "",
                "coerced_value_type": "",
                "validation_status": "fail",
                "notes": f"{type(exc).__name__}: {exc}",
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = pd.DataFrame(rows)
    report.to_csv(OUTPUT_PATH, index=False)
    failures = int(report["validation_status"].eq("fail").sum()) if not report.empty else 1
    print(f"wrote {OUTPUT_PATH}")
    print(f"checks={len(report)} failures={failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
