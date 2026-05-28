#!/usr/bin/env python3
"""Audit Hall of Fame win-rate denominators across clubs.

This compares total career appearances from aggregate processed tables with the
result-classified denominator used by deploy-safe Hall of Fame win-rate
summaries. It can also write a markdown report under docs/.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import re
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config.club_config import get_club_name  # noqa: E402


CLUBS = [
    "fvcc",
    "southside-east-caulfield",
    "glen-waverley-hawks",
    "ashwood",
    "plenty",
    "reynella",
    "georges-river-district",
]

DEFAULT_DOC = ROOT / "docs" / "multi_club_win_rate_denominator_audit.md"


@dataclass
class ClubAudit:
    club_id: str
    club_name: str
    total_players: int
    compared_players: int
    differing_players: int
    old_best_player: str
    old_best_win_pct: float | None
    old_best_total_matches: int | None
    old_best_result_matches: int | None
    new_best_player: str
    new_best_win_pct: float | None
    new_best_result_matches: int | None
    sample_rows: pd.DataFrame


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit Hall of Fame win-rate denominators across clubs.")
    parser.add_argument("--clubs", nargs="*", default=CLUBS, help="Club ids to audit")
    parser.add_argument("--write-doc", action="store_true", help="Write the markdown report")
    parser.add_argument("--doc-path", default=str(DEFAULT_DOC), help="Markdown output path")
    return parser.parse_args(argv)


def player_name_match_key(value: object) -> str:
    text = str(value or "").strip().casefold()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def compute_player_key(frame: pd.DataFrame) -> pd.Series:
    if "canonical_player_id" in frame:
        output = frame["canonical_player_id"].fillna("").astype(str).str.strip()
        fallback = frame.get("player_name", pd.Series("", index=frame.index)).map(player_name_match_key)
        return output.where(output != "", fallback)
    return frame.get("player_name", pd.Series("", index=frame.index)).map(player_name_match_key)


def load_total_matches(club_id: str) -> pd.DataFrame:
    processed_dir = ROOT / "clubs" / club_id / "data" / "processed"
    rows = []
    for filename in ["all_seasons_batting.csv", "all_seasons_bowling.csv", "all_seasons_fielding.csv"]:
        frame = pd.read_csv(processed_dir / filename)
        if frame.empty or "matches" not in frame:
            continue
        output = frame.copy()
        output["player_key"] = compute_player_key(output)
        output["matches"] = pd.to_numeric(output["matches"], errors="coerce").fillna(0)
        grouped = output.groupby("player_key", as_index=False)["matches"].sum()
        rows.append(grouped)
    if not rows:
        return pd.DataFrame(columns=["player_key", "total_matches"])
    combined = pd.concat(rows, ignore_index=True)
    combined = combined.groupby("player_key", as_index=False)["matches"].max()
    return combined.rename(columns={"matches": "total_matches"})


def load_win_rates(club_id: str) -> pd.DataFrame:
    path = ROOT / "clubs" / club_id / "data" / "processed" / "hall_of_fame" / "player_win_rates.csv"
    frame = pd.read_csv(path)
    output = frame.copy()
    if "player_key" not in output:
        output["player_key"] = output.get("canonical_player_id", "")
    output["player_key"] = output["player_key"].fillna("").astype(str).str.strip()
    output["matches_with_result"] = pd.to_numeric(output.get("matches_with_result"), errors="coerce")
    output["wins"] = pd.to_numeric(output.get("wins"), errors="coerce")
    output["losses"] = pd.to_numeric(output.get("losses"), errors="coerce")
    output["win_pct"] = pd.to_numeric(output.get("win_pct"), errors="coerce")
    return output


def build_club_audit(club_id: str) -> ClubAudit:
    totals = load_total_matches(club_id)
    win_rates = load_win_rates(club_id)
    merged = totals.merge(
        win_rates[
            [
                "player_key",
                "display_player_name",
                "matches_with_result",
                "wins",
                "losses",
                "win_pct",
            ]
        ],
        on="player_key",
        how="outer",
    )
    merged["display_player_name"] = merged["display_player_name"].fillna(merged["player_key"])
    merged["total_matches"] = pd.to_numeric(merged["total_matches"], errors="coerce")
    merged["matches_with_result"] = pd.to_numeric(merged["matches_with_result"], errors="coerce")
    compared = merged[merged["total_matches"].notna() & merged["matches_with_result"].notna()].copy()
    compared["difference"] = compared["total_matches"] - compared["matches_with_result"]
    differing = compared[compared["difference"] != 0].copy()

    old_candidates = merged[
        merged["total_matches"].fillna(0).ge(60)
        & merged["matches_with_result"].fillna(0).gt(0)
        & merged["win_pct"].notna()
    ].copy()
    old_candidates = old_candidates.sort_values(
        ["win_pct", "total_matches", "display_player_name"],
        ascending=[False, False, True],
    )

    new_candidates = merged[
        merged["matches_with_result"].fillna(0).ge(60)
        & merged["win_pct"].notna()
    ].copy()
    new_candidates = new_candidates.sort_values(
        ["win_pct", "matches_with_result", "display_player_name"],
        ascending=[False, False, True],
    )

    old_best = old_candidates.iloc[0] if not old_candidates.empty else pd.Series(dtype="object")
    new_best = new_candidates.iloc[0] if not new_candidates.empty else pd.Series(dtype="object")
    sample_rows = differing.sort_values(
        ["difference", "total_matches", "display_player_name"],
        ascending=[False, False, True],
    ).head(5)

    return ClubAudit(
        club_id=club_id,
        club_name=get_club_name(club_id),
        total_players=len(merged),
        compared_players=len(compared),
        differing_players=len(differing),
        old_best_player=str(old_best.get("display_player_name", "")),
        old_best_win_pct=safe_float(old_best.get("win_pct")),
        old_best_total_matches=safe_int(old_best.get("total_matches")),
        old_best_result_matches=safe_int(old_best.get("matches_with_result")),
        new_best_player=str(new_best.get("display_player_name", "")),
        new_best_win_pct=safe_float(new_best.get("win_pct")),
        new_best_result_matches=safe_int(new_best.get("matches_with_result")),
        sample_rows=sample_rows,
    )


def safe_int(value: object) -> int | None:
    if pd.isna(value):
        return None
    return int(round(float(value)))


def safe_float(value: object) -> float | None:
    if pd.isna(value):
        return None
    return float(value)


def render_markdown(audits: list[ClubAudit]) -> str:
    lines = [
        "# Multi-club win rate denominator audit",
        "",
        "This audit compares total Hall of Fame `Matches` against the `matches_with_result` denominator used by deploy-safe `player_win_rates.csv`.",
        "",
        "Why differences happen:",
        "- `Matches` counts total recorded club appearances from aggregate processed batting/bowling/fielding tables.",
        "- `Win %` counts only appearances in matches with a classified result from local match-centre summaries.",
        "- Pending, abandoned, cancelled, no-result, or otherwise unattributable outcomes lower the win-rate denominator without changing total appearances.",
        "",
        "UI decision:",
        "- Keep `Matches` in Detailed Records as total career appearances.",
        "- Keep `Win %` sourced from result-classified matches only.",
        "- Best Win % cards should label the denominator explicitly as `matches with results`.",
        "",
        "## Summary by club",
        "",
        "| Club | Players compared | Players with denominator mismatch | Old best-win qualifier | New best-win qualifier |",
        "| --- | ---: | ---: | --- | --- |",
    ]
    for audit in audits:
        old_label = audit.old_best_player or "—"
        if audit.old_best_win_pct is not None:
            old_label = (
                f"{old_label} ({audit.old_best_win_pct:.1f}% · "
                f"{audit.old_best_total_matches or 0} total / {audit.old_best_result_matches or 0} result)"
            )
        new_label = audit.new_best_player or "—"
        if audit.new_best_win_pct is not None:
            new_label = f"{new_label} ({audit.new_best_win_pct:.1f}% · {audit.new_best_result_matches or 0} result)"
        lines.append(
            f"| {audit.club_name} | {audit.compared_players:,} | {audit.differing_players:,} | {old_label} | {new_label} |"
        )

    for audit in audits:
        lines.extend(
            [
                "",
                f"## {audit.club_name}",
                "",
                f"- Compared players: {audit.compared_players:,}",
                f"- Players where total appearances differ from result-classified matches: {audit.differing_players:,}",
                f"- Old Best Win % qualifier basis: {audit.old_best_player or '—'}"
                + (
                    f" at {audit.old_best_win_pct:.1f}% using {audit.old_best_total_matches or 0} total matches and {audit.old_best_result_matches or 0} result-classified matches."
                    if audit.old_best_win_pct is not None
                    else "."
                ),
                f"- New Best Win % qualifier basis: {audit.new_best_player or '—'}"
                + (
                    f" at {audit.new_best_win_pct:.1f}% using {audit.new_best_result_matches or 0} matches with results."
                    if audit.new_best_win_pct is not None
                    else "."
                ),
            ]
        )
        if audit.sample_rows.empty:
            lines.append("- Example mismatches: none")
            continue
        lines.extend(
            [
                "- Example mismatches:",
                "| Player | Total matches | Matches with results | Difference | Win % |",
                "| --- | ---: | ---: | ---: | ---: |",
            ]
        )
        for _, row in audit.sample_rows.iterrows():
            lines.append(
                f"| {row['display_player_name']} | {safe_int(row['total_matches']) or 0} | "
                f"{safe_int(row['matches_with_result']) or 0} | {safe_int(row['difference']) or 0} | "
                f"{safe_float(row['win_pct']) or 0:.1f}% |"
            )

    fvcc = next((audit for audit in audits if audit.club_id == "fvcc"), None)
    if fvcc is not None:
        lines.extend(
            [
                "",
                "## Jimmy Sharma example",
                "",
                "- Before wording change: `54 wins from 82 matches` beside a Detailed Records row showing `Matches = 86` and `Win % = 65.9%`.",
                "- After wording change: `54 wins from 82 matches with results` while Detailed Records still shows `Matches = 86` and `Win % = 65.9%`.",
                "- This makes the denominator distinction explicit without changing the percentage calculation.",
            ]
        )

    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audits = [build_club_audit(club_id) for club_id in args.clubs]
    markdown = render_markdown(audits)
    print(markdown)
    if args.write_doc:
        path = Path(args.doc_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown, encoding="utf-8")
        print(f"Wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
