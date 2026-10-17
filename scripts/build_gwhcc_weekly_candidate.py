"""Replace a Hawks season offline using a verified pre-season sufficient-statistic seed.

No network, historical JSON reconstruction, new identity decisions, or publication.
An explicit immutable historical Git ref and current approved mappings are required.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CLUB = "glen-waverley-hawks"


def summary_specs():
    sums = ["innings", "runs", "outs", "thirties", "fifties", "hundreds", "ducks", "fours", "sixes",
            "bbb_runs", "bbb_balls_faced", "bbb_dismissals", "bbb_batting_innings", "bbb_matches", "matches",
            "balls_bowled", "runs_against", "wickets", "three_wicket_innings", "five_wicket_innings", "wides",
            "no_balls", "catches", "stumpings", "run_outs", "dismissals"]
    rates = {"bat_avg": ("runs", "outs", 1), "strike_rate": ("bbb_runs", "bbb_balls_faced", 100),
             "bowl_avg": ("runs_against", "wickets", 1), "bowl_sr": ("balls_bowled", "wickets", 1),
             "eco": ("runs_against", "balls_bowled", 6)}
    return {
        "hall_of_fame/player_bbb_batting_rates.csv": (["canonical_player_id"], ["bbb_runs", "bbb_balls_faced", "bbb_dismissals", "bbb_batting_innings", "bbb_matches"], {"bat_sr": ("bbb_runs", "bbb_balls_faced", 100)}, []),
        "hall_of_fame/player_scorecard_milestones.csv": (["canonical_player_id"], ["thirties", "fifties", "hundreds", "ducks"], {}, ["hs"]),
        "hall_of_fame/player_bowling_milestones.csv": (["canonical_player_id"], ["three_wicket_innings", "five_wicket_innings", "ten_wicket_matches"], {}, ["bbi"]),
        "hall_of_fame/player_win_rates.csv": (["canonical_player_id"], ["matches_with_result", "wins", "losses", "raw_wins"], {"win_pct": ("wins", "matches_with_result", 100)}, []),
        "player_profile/batting_position_summary.csv": (["canonical_player_id", "position_group"], ["innings", "runs", "outs"], {"average": ("runs", "outs", 1)}, []),
        "player_profile/bowling_phase_summary.csv": (["canonical_player_id", "phase_model", "phase"], ["legal_balls", "wickets", "runs_conceded", "dot_balls", "boundary_balls", "match_count"], {"avg": ("runs_conceded", "wickets", 1), "eco": ("runs_conceded", "legal_balls", 6), "sr": ("legal_balls", "wickets", 1), "dot_ball_pct": ("dot_balls", "legal_balls", 100), "boundary_rate": ("boundary_balls", "legal_balls", 100)}, []),
        "player_profile/dismissal_fingerprint_summary.csv": (["canonical_player_id", "scope", "dismissal_bucket"], ["count"], {}, []),
        "player_profile/performance_breakdown_by_dimension.csv": (["canonical_player_id", "dimension", "discipline", "breakdown_label"], sums, rates, ["high_score", "bbi"]),
    }


def approved_redirects(decisions: pd.DataFrame) -> dict[str, str]:
    if not decisions["decision"].eq("customer_approved_exact_disjoint_seasons").all():
        raise ValueError("Identity continuity must already be explicitly approved")
    if not decisions["club"].eq(CLUB).all():
        raise ValueError("Cross-club identity decision")
    if decisions.groupby("previous_canonical_id")["canonical_player_id"].nunique().gt(1).any():
        raise ValueError("Conflicting approved canonical targets")
    return dict(zip(decisions.previous_canonical_id, decisions.canonical_player_id))


def canonicalise_summary(frame: pd.DataFrame, decisions: pd.DataFrame, spec, filename: str) -> pd.DataFrame:
    from scripts.reconcile_disjoint_player_identities import consolidate
    from src.ui import layout

    redirects = approved_redirects(decisions)
    affected = frame.canonical_player_id.isin(redirects)
    if not affected.any():
        return frame
    frame = frame.copy()
    for column in ["canonical_player_id", "player_key"]:
        if column in frame:
            frame[column] = frame[column].replace(redirects)
    reduced = consolidate(frame.loc[affected], *spec)
    if filename == "dismissal_fingerprint_summary.csv":
        counts = pd.to_numeric(reduced["count"], errors="raise")
        totals = counts.groupby([reduced.canonical_player_id, reduced.scope]).transform("sum")
        reduced["total_dismissals"] = totals
        reduced["pct"] = counts.div(totals.where(totals.ne(0))).mul(100).fillna(0)
    elif filename == "bowling_phase_summary.csv":
        reduced["overs"] = pd.to_numeric(reduced.legal_balls).map(layout.format_balls_as_overs)
    elif filename == "performance_breakdown_by_dimension.csv":
        for index, row in reduced.iterrows():
            if row.get("high_score", "") != "":
                reduced.loc[index, "high_score_sort"] = layout.parse_high_score_value(row.high_score)[0]
                reduced.loc[index, "high_score_not_out_sort"] = int("*" in str(row.high_score))
            if row.discipline == "Bowling":
                reduced.loc[index, "extras_pct"] = layout.calculate_extras_pct(row.no_balls, row.wides, row.balls_bowled)
    elif filename == "player_scorecard_milestones.csv":
        reduced["hs_sort"] = reduced.hs.map(lambda value: layout.parse_high_score_value(value)[0])
    elif filename == "player_bowling_milestones.csv":
        from scripts.build_hall_of_fame_detail_exports import parse_bbi
        reduced["bbi_wickets_sort"] = reduced.bbi.map(lambda value: parse_bbi(value)[0])
        reduced["bbi_runs_sort"] = reduced.bbi.map(lambda value: parse_bbi(value)[1])
    return pd.concat([frame.loc[~affected], reduced], ignore_index=True)


def historical_seed(seed: Path, historical_ref: str, season: str) -> dict:
    seed = seed.resolve()
    subprocess.run(["git", "merge-base", "--is-ancestor", historical_ref, "HEAD"], cwd=ROOT, check=True)
    if seed.exists() or ROOT == seed or ROOT in seed.parents:
        raise ValueError("Seed must be a new outside-repository directory")
    club = ROOT / "clubs" / CLUB
    shutil.copytree(club, seed / "clubs" / CLUB)
    processed = seed / "clubs" / CLUB / "data/processed"

    def committed(relative):
        path = f"clubs/{CLUB}/data/processed/{relative}"
        return pd.read_csv(io.BytesIO(subprocess.check_output(["git", "show", f"{historical_ref}:{path}"], cwd=ROOT)), dtype=str, keep_default_na=False)

    released = pd.read_csv(processed / "all_seasons_matches.csv")
    historical_ids = set(released.loc[~released.season.eq(season), "match_id"])
    reference_matches = committed("all_seasons_matches.csv")
    if reference_matches.season.eq(season).any() or set(reference_matches.match_id) != historical_ids:
        raise ValueError("Historical ref must be the complete disjoint pre-season baseline")
    current_ids = set(released.loc[released.season.eq(season), "match_id"])
    for path in [*processed.glob("all_seasons_*.csv"), *processed.glob("season_overview/*.csv"),
                 *processed.glob("player_profile/recent_form_*.csv"), processed / "hall_of_fame/fastest_batting_milestones.csv",
                 processed / "hall_of_fame/scorecard_record_links.csv", processed / "partnerships/partnership_events.csv"]:
        frame = pd.read_csv(path, low_memory=False)
        if "match_id" in frame:
            frame = frame[~frame.match_id.isin(current_ids)]
        elif "season" in frame:
            frame = frame[~frame.season.eq(season)]
        frame.to_csv(path, index=False)
    coverage_path = processed / "validation/gwhcc_partnership_coverage_audit.csv"
    coverage = pd.read_csv(coverage_path)
    coverage[~coverage.season.eq(season)].to_csv(coverage_path, index=False)
    decisions = pd.read_csv(club / "data/source/disjoint_season_identity_decisions.csv", dtype=str).fillna("")
    for relative, spec in summary_specs().items():
        path = processed / relative
        canonicalise_summary(committed(relative), decisions, spec, path.name).to_csv(path, index=False)
    return {"historical_ref": historical_ref, "historical_match_ids": len(historical_ids),
            "current_match_ids_replaced": len(current_ids), "approved_continuity_groups": decisions.canonical_player_id.nunique()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-bundle", type=Path, required=True)
    parser.add_argument("--candidate-root", type=Path, required=True)
    parser.add_argument("--historical-ref", required=True)
    parser.add_argument("--cutoff", required=True)
    args = parser.parse_args()
    args.source_bundle = args.source_bundle.resolve()
    args.candidate_root = args.candidate_root.resolve()
    os.environ["CLUB_ID"] = CLUB
    if args.candidate_root.exists() or ROOT == args.candidate_root or ROOT in args.candidate_root.parents:
        raise ValueError("Candidate must be a new outside-repository directory")
    state = json.loads((args.source_bundle / "task_state.json").read_text())
    seed = args.candidate_root.with_name(args.candidate_root.name + "-historical-seed")
    audit = historical_seed(seed, args.historical_ref, state["season"]["name"])
    bundle = args.candidate_root.with_name(args.candidate_root.name + "-source-view")
    bundle.mkdir()
    for directory in ["source_payloads", "parsed_current"]:
        (bundle / directory).symlink_to((args.source_bundle / directory).resolve(), target_is_directory=True)
    for filename in ["task_state.json", "current_aggregate_batting.csv", "current_aggregate_bowling.csv", "current_aggregate_fielding.csv"]:
        shutil.copy2(args.source_bundle / filename, bundle / filename)
    # All currently approved aliases are already in the seed; this task grants no new merges.
    pd.DataFrame(columns=["canonical_player_id", "decision_status"]).to_csv(bundle / "approved_identity_mappings.csv", index=False)
    subprocess.run([sys.executable, str(ROOT / "scripts/build_gwhcc_incremental_candidate.py"),
                    "--source-bundle", str(bundle), "--candidate-root", str(args.candidate_root),
                    "--baseline-root", str(seed), "--cutoff", args.cutoff], cwd=ROOT, check=True)
    (args.candidate_root / "weekly_seed_validation.json").write_text(json.dumps(audit, indent=2))
    print(json.dumps(audit, indent=2))


if __name__ == "__main__":
    main()
