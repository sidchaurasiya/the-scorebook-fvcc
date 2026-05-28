#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.player_identity import apply_player_identity_mapping, load_player_aliases  # noqa: E402


DEFAULT_CLUBS = [
    "fvcc",
    "southside-east-caulfield",
    "glen-waverley-hawks",
    "ashwood",
    "plenty",
    "reynella",
    "georges-river-district",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Player Profile match totals and BBB dismissal metrics.")
    parser.add_argument("--clubs", nargs="*", default=DEFAULT_CLUBS)
    parser.add_argument("--limit", type=int, default=6, help="Rows to print per club.")
    return parser.parse_args()


def read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.exists() else pd.DataFrame()


def processed_root(club_id: str) -> Path:
    return ROOT / "clubs" / club_id / "data" / "processed"


def hall_of_fame_root(club_id: str) -> Path:
    return processed_root(club_id) / "hall_of_fame"


def mapped_processed_table(club_id: str, name: str) -> pd.DataFrame:
    frame = read_csv(processed_root(club_id) / f"{name}.csv")
    if frame.empty:
        return frame
    aliases = load_player_aliases(club_id=club_id)
    return apply_player_identity_mapping(frame, aliases_df=aliases, club_id=club_id)


def compute_match_totals(club_id: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for category in ["batting", "bowling", "fielding"]:
        frame = mapped_processed_table(club_id, f"all_seasons_{category}")
        if frame.empty or "canonical_player_id" not in frame or "matches" not in frame:
            continue
        frame = frame.copy()
        frame["matches"] = pd.to_numeric(frame["matches"], errors="coerce").fillna(0)
        group_cols = [column for column in ["canonical_player_id", "canonical_player_name", "season", "team_id"] if column in frame]
        frames.append(frame.groupby(group_cols, dropna=False, as_index=False)["matches"].max())
    if not frames:
        return pd.DataFrame(columns=["canonical_player_id", "canonical_player_name", "career_matches"])
    combined = pd.concat(frames, ignore_index=True)
    combined = combined.groupby(["canonical_player_id", "canonical_player_name", "season", "team_id"], dropna=False, as_index=False)["matches"].max()
    return (
        combined.groupby(["canonical_player_id", "canonical_player_name"], dropna=False, as_index=False)["matches"]
        .sum()
        .rename(columns={"matches": "career_matches"})
    )


def compute_innings_totals(club_id: str) -> pd.DataFrame:
    batting = mapped_processed_table(club_id, "all_seasons_batting")
    if batting.empty or "canonical_player_id" not in batting:
        return pd.DataFrame(columns=["canonical_player_id", "canonical_player_name", "total_innings"])
    batting["battingInnings"] = pd.to_numeric(batting.get("battingInnings"), errors="coerce").fillna(0)
    return batting.groupby(["canonical_player_id", "canonical_player_name"], dropna=False, as_index=False).agg(
        total_innings=("battingInnings", "sum"),
    )


def compute_duplicate_name_rows(club_id: str) -> pd.DataFrame:
    players = read_csv(processed_root(club_id) / "players.csv")
    if players.empty:
        return pd.DataFrame(columns=["player_name", "raw_profile_rows"])
    return (
        players.groupby("player_name", dropna=False, as_index=False)
        .size()
        .rename(columns={"size": "raw_profile_rows"})
        .sort_values(["raw_profile_rows", "player_name"], ascending=[False, True])
    )


def compute_bbb_audit(club_id: str) -> pd.DataFrame:
    bbb = read_csv(hall_of_fame_root(club_id) / "player_bbb_batting_rates.csv")
    if bbb.empty:
        return pd.DataFrame(
            columns=[
                "club_id",
                "player_name",
                "verified_bbb_balls_faced",
                "verified_bbb_dismissals",
                "balls_per_dismissal",
                "non_bbb_innings_excluded",
                "metric_state",
            ]
        )
    innings = compute_innings_totals(club_id)
    output = bbb.merge(
        innings,
        on=["canonical_player_id", "canonical_player_name"],
        how="left",
    )
    output["bbb_balls_faced"] = pd.to_numeric(output.get("bbb_balls_faced"), errors="coerce").fillna(0)
    output["bbb_dismissals"] = pd.to_numeric(output.get("bbb_dismissals"), errors="coerce").fillna(0)
    output["bbb_batting_innings"] = pd.to_numeric(output.get("bbb_batting_innings"), errors="coerce").fillna(0)
    output["total_innings"] = pd.to_numeric(output.get("total_innings"), errors="coerce").fillna(0)
    output["balls_per_dismissal"] = output.apply(
        lambda row: (float(row["bbb_balls_faced"]) / float(row["bbb_dismissals"])) if row["bbb_dismissals"] > 0 else pd.NA,
        axis=1,
    )
    output["non_bbb_innings_excluded"] = (output["total_innings"] - output["bbb_batting_innings"]).clip(lower=0)
    output["metric_state"] = output.apply(
        lambda row: "shown"
        if row["bbb_balls_faced"] > 0 and row["bbb_dismissals"] > 0
        else "not dismissed in BBB sample"
        if row["bbb_balls_faced"] > 0
        else "N/A",
        axis=1,
    )
    output["club_id"] = club_id
    output["player_name"] = output["display_player_name"].fillna(output["canonical_player_name"])
    return output[
        [
            "club_id",
            "canonical_player_id",
            "player_name",
            "bbb_balls_faced",
            "bbb_dismissals",
            "balls_per_dismissal",
            "non_bbb_innings_excluded",
            "metric_state",
        ]
    ].rename(
        columns={
            "bbb_balls_faced": "verified_bbb_balls_faced",
            "bbb_dismissals": "verified_bbb_dismissals",
        }
    )


def select_suspicious_rows(club_id: str, limit: int) -> pd.DataFrame:
    rows = compute_bbb_audit(club_id)
    if rows.empty:
        return rows
    suspicious = rows.sort_values(
        ["non_bbb_innings_excluded", "verified_bbb_balls_faced", "player_name"],
        ascending=[False, False, True],
    )
    jimmy = suspicious[suspicious["player_name"].astype(str).str.casefold().eq("jimmy sharma")]
    selected = pd.concat([jimmy, suspicious], ignore_index=True).drop_duplicates("canonical_player_id").head(limit)
    return selected


def main() -> int:
    args = parse_args()
    for club_id in args.clubs:
        print(f"\n=== {club_id} ===")
        match_totals = compute_match_totals(club_id)
        duplicates = compute_duplicate_name_rows(club_id)
        bbb_rows = select_suspicious_rows(club_id, args.limit)
        if club_id == "fvcc":
            jimmy = match_totals[match_totals["canonical_player_name"].astype(str).str.casefold().eq("jimmy sharma")]
            if not jimmy.empty:
                print(
                    "Jimmy Sharma aggregate matches:",
                    int(pd.to_numeric(jimmy.iloc[0]["career_matches"], errors="coerce") or 0),
                )
        duplicate_count = int((duplicates["raw_profile_rows"] > 1).sum()) if not duplicates.empty else 0
        print(f"Duplicate display names in players.csv: {duplicate_count}")
        if not bbb_rows.empty:
            display = bbb_rows.copy()
            display["balls_per_dismissal"] = pd.to_numeric(display["balls_per_dismissal"], errors="coerce").round(2)
            print(display.to_string(index=False))
        else:
            print("No BBB batting-rate rows found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
