"""Offline, club-scoped consolidation of explicitly approved disjoint histories.

Never replaces source contributions with scorecard extracts. Only canonical keys
and affected sufficient-statistic summaries are changed; raw IDs remain intact.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import io
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.utils.player_identity import (  # noqa: E402
    ALIAS_COLUMNS, apply_player_identity_mapping, public_player_mask,
)
from src.config.club_config import get_mapping_path  # noqa: E402

APPROVAL = "customer_approved_exact_disjoint_seasons"


def exact_name_key(value: object) -> str:
    return " ".join(str(value or "").split()).casefold()


def classify_group(rows: pd.DataFrame) -> tuple[str, str]:
    if "identity_club_id" in rows and rows.identity_club_id.nunique() != 1:
        return "BLOCKED_GOVERNANCE_CONFLICT", "Identities must belong to one club"
    if "confirmed_distinct" in rows and rows.confirmed_distinct.any():
        return "NOT_ELIGIBLE_CONFIRMED_DISTINCT", "Existing explicit distinct-person decision takes precedence"
    names = {exact_name_key(n) for n in rows.canonical_player_name}
    if len(names) != 1:
        return "BLOCKED_GOVERNANCE_CONFLICT", "Names are not exact casefold matches"
    name = next(iter(names))
    if len(name.split()) < 2 or any(len(t.strip(".'")) <= 1 for t in name.split()):
        return "BLOCKED_GOVERNANCE_CONFLICT", "Full given-name evidence required"
    if not public_player_mask(rows).all():
        return "BLOCKED_GOVERNANCE_CONFLICT", "Protected identity cannot be promoted"
    ids = sorted(rows.canonical_player_id.unique())
    if len(ids) < 2:
        return "ALREADY_MERGED", "One existing canonical identity"
    seasons = [set(rows.loc[rows.canonical_player_id.eq(id), "season"].dropna()) for id in ids]
    if any(not s or "" in s for s in seasons):
        return "BLOCKED_GOVERNANCE_CONFLICT", "Incomplete season evidence"
    if any(a & b for i, a in enumerate(seasons) for b in seasons[i + 1:]):
        return "NOT_ELIGIBLE_OVERLAPPING_SEASONS", "Pairwise season overlap; no partial/transitive merge"
    return "ELIGIBLE_FOR_MERGE", "Customer-approved exact full name; complete pairwise disjoint seasons"


def read(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(club: str, aliases=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    from src.data.playcricket_ingestion import read_processed_table

    parts = []
    for kind in ("batting", "bowling", "fielding"):
        # GRDCC's existing loader enforces the Excel/digital boundary and report
        # namespaces. Do not classify its digital extract as the whole history.
        frame = (read_processed_table(f"all_seasons_{kind}") if club == "georges-river-district"
                 else read(ROOT / "clubs" / club / "data/processed" / f"all_seasons_{kind}.csv"))
        frame = apply_player_identity_mapping(frame, aliases, club_id=club)
        frame["identity_club_id"] = club
        parts.append(frame)
    source = pd.concat(parts, ignore_index=True)
    source["_exact_name"] = source.canonical_player_name.map(exact_name_key)
    distinct_names = set()
    for path in (ROOT / "clubs" / club / "data/processed/validation").glob("*duplicate_identity_review.csv"):
        review = read(path)
        if {"display_name", "classification"}.issubset(review):
            distinct = review.classification.str.upper().isin({"CONFIRMED DIFFERENT PEOPLE", "CONFIRMED DISTINCT"})
            distinct_names.update(review.loc[distinct, "display_name"].map(exact_name_key))
    source["confirmed_distinct"] = source._exact_name.isin(distinct_names)
    records = []
    for name, group in source.groupby("_exact_name", sort=True):
        if group.canonical_player_id.nunique() < 2:
            continue
        status, reason = classify_group(group)
        records.append(dict(club=club, player=name, classification=status, reason=reason,
                            canonical_ids=json.dumps(sorted(group.canonical_player_id.unique())),
                            source_ids=json.dumps(sorted(group.raw_player_id.unique())),
                            seasons=json.dumps({id: sorted(set(g.season)) for id, g in group.groupby("canonical_player_id")})))
    return source, pd.DataFrame(records, columns=["club", "player", "classification", "reason", "canonical_ids", "source_ids", "seasons"])


def sum_values(values: pd.Series) -> object:
    number = pd.to_numeric(values.replace("", None), errors="raise").sum(min_count=1)
    return number if pd.notna(number) else ""


def consolidate(frame: pd.DataFrame, keys: list[str], sums: list[str], rates=None, best=None) -> pd.DataFrame:
    """Combine only the affected disjoint evidence, deriving rates from like coverage."""
    from scripts.build_player_profile_insight_exports import best_high_score_from_labels, best_bbi_from_labels
    reducers = {"hs": best_high_score_from_labels, "high_score": best_high_score_from_labels, "bbi": best_bbi_from_labels}
    records = []
    for _, group in frame.groupby(keys, sort=False, dropna=False):
        row = group.iloc[0].to_dict()
        if len(group) > 1:
            for column in sums:
                if column in group:
                    row[column] = sum_values(group[column])
            for column in best or []:
                if column in group:
                    row[column] = reducers[column](group[column].replace("", pd.NA).dropna())
            for column, (num, den, multiplier) in (rates or {}).items():
                if column not in group:
                    continue
                missing_denominator = group[num].ne("") & group[den].eq("")
                n, d = pd.to_numeric(pd.Series([row.get(num), row.get(den)]), errors="coerce")
                row[column] = n * multiplier / d if pd.notna(n) and pd.notna(d) and d and not missing_denominator.any() else ""
        records.append(row)
    return pd.DataFrame(records, columns=frame.columns)


def reconcile(club: str, audit: Path, baseline_sha: str, apply: bool = False) -> dict:
    os.environ["CLUB_ID"] = club
    base = ROOT / "clubs" / club
    processed = base / "data/processed"
    audit.mkdir(parents=True, exist_ok=True)
    def original_read(path):
        relative = str(path.relative_to(ROOT))
        data = subprocess.check_output(["git", "show", f"{baseline_sha}:{relative}"], cwd=ROOT)
        return pd.read_csv(io.BytesIO(data), dtype=str, keep_default_na=False)

    # A resumed offline run must use the immutable released inputs, not partially
    # consolidated summaries. Every successful run is reproducible from this SHA.
    alias_path = get_mapping_path("player_aliases.csv", club_id=club)
    source, groups = inventory(club, original_read(alias_path))
    groups.to_csv(audit / "duplicate_inventory.csv", index=False)
    eligible = groups[groups.classification.eq("ELIGIBLE_FOR_MERGE")]
    decisions, redirects = [], {}
    for group in eligible.itertuples():
        rows = source[source._exact_name.eq(group.player)]
        seasons = json.loads(group.seasons)
        survivor = min(seasons, key=lambda id: (min(seasons[id]), id))
        name = rows.loc[rows.canonical_player_id.eq(survivor), "canonical_player_name"].iloc[0]
        # A historical replacement is never summed into another identity implicitly.
        for path in (base / "data/source").rglob("*.csv"):
            if path.name == "disjoint_season_identity_decisions.csv":
                continue
            governed = read(path)
            if "canonical_player_id" in governed and governed.canonical_player_id.isin(seasons).any():
                raise ValueError(f"Explicit historical decision needs metric-level reconciliation: {path}")
        for raw, profile in rows.groupby("raw_player_id"):
            previous = profile.canonical_player_id.unique()
            if len(previous) != 1:
                raise ValueError("Conflicting source identity")
            decisions.append(dict(club=club, canonical_player_id=survivor, canonical_player_name=name,
                                  raw_player_id=raw, previous_canonical_id=previous[0],
                                  seasons=" | ".join(sorted(set(profile.season))), decision=APPROVAL))
            redirects[previous[0]] = survivor
    decision_frame = pd.DataFrame(decisions, columns=["club", "canonical_player_id", "canonical_player_name", "raw_player_id", "previous_canonical_id", "seasons", "decision"])
    decision_frame.to_csv(audit / "merge_decisions.csv", index=False)
    if not apply or not decisions:
        return {"club": club, "groups": len(groups), "eligible": len(eligible), "merged": 0}
    if club != "glen-waverley-hawks":
        raise ValueError("Apply requires a club-specific sufficient-statistic preservation plan; inventory is read-only for this club")

    if not (audit / "before_hashes.json").exists():
        before_hashes = {str(p.relative_to(ROOT)): fingerprint(p) for p in base.rglob("*") if p.is_file()}
        (audit / "before_hashes.json").write_text(json.dumps(before_hashes, indent=2))
    aliases = original_read(alias_path)
    new_aliases = [dict(canonical_player_id=d["canonical_player_id"], canonical_player_name=d["canonical_player_name"],
                        raw_player_id=d["raw_player_id"], raw_player_name="", alias_name="",
                        notes=f"Customer-approved exact full-name disjoint-season consolidation; source seasons {d['seasons']}; previous canonical {d['previous_canonical_id']}; retain all source contributions.",
                        is_active="true", merge_source=APPROVAL) for d in decisions]
    aliases = pd.concat([aliases, pd.DataFrame(new_aliases, columns=ALIAS_COLUMNS)], ignore_index=True)
    aliases.to_csv(alias_path, index=False)
    decision_frame.to_csv(base / "data/source/disjoint_season_identity_decisions.csv", index=False)

    # Work only on explicitly affected canonical keys. Source player_id/raw_player_id
    # remain byte-for-byte unchanged, including all old scorecards and match IDs.
    affected = set(redirects)
    summary_specs = {
        "player_bbb_batting_rates.csv": (["canonical_player_id"], ["bbb_runs", "bbb_balls_faced", "bbb_dismissals", "bbb_batting_innings", "bbb_matches"], {"bat_sr": ("bbb_runs", "bbb_balls_faced", 100)}, []),
        "player_scorecard_milestones.csv": (["canonical_player_id"], ["thirties", "fifties", "hundreds", "ducks"], {}, ["hs"]),
        "player_bowling_milestones.csv": (["canonical_player_id"], ["three_wicket_innings", "five_wicket_innings", "ten_wicket_matches"], {}, ["bbi"]),
        "player_win_rates.csv": (["canonical_player_id"], ["matches_with_result", "wins", "losses", "raw_wins"], {"win_pct": ("wins", "matches_with_result", 100)}, []),
        "batting_position_summary.csv": (["canonical_player_id", "position_group"], ["innings", "runs", "outs"], {"average": ("runs", "outs", 1)}, []),
        "bowling_phase_summary.csv": (["canonical_player_id", "phase_model", "phase"], ["legal_balls", "wickets", "runs_conceded", "dot_balls", "boundary_balls", "match_count"], {"avg": ("runs_conceded", "wickets", 1), "eco": ("runs_conceded", "legal_balls", 6), "sr": ("legal_balls", "wickets", 1), "dot_ball_pct": ("dot_balls", "legal_balls", 100), "boundary_rate": ("boundary_balls", "legal_balls", 100)}, []),
        "dismissal_fingerprint_summary.csv": (["canonical_player_id", "scope", "dismissal_bucket"], ["count"], {}, []),
        "performance_breakdown_by_dimension.csv": (["canonical_player_id", "dimension", "discipline", "breakdown_label"], ["innings", "runs", "outs", "thirties", "fifties", "hundreds", "ducks", "fours", "sixes", "bbb_runs", "bbb_balls_faced", "bbb_dismissals", "bbb_batting_innings", "bbb_matches", "matches", "balls_bowled", "runs_against", "wickets", "three_wicket_innings", "five_wicket_innings", "wides", "no_balls", "catches", "stumpings", "run_outs", "dismissals"], {"bat_avg": ("runs", "outs", 1), "strike_rate": ("bbb_runs", "bbb_balls_faced", 100), "bowl_avg": ("runs_against", "wickets", 1), "bowl_sr": ("balls_bowled", "wickets", 1), "eco": ("runs_against", "balls_bowled", 6)}, ["high_score", "bbi"]),
    }
    changed = []
    for path in sorted(processed.rglob("*.csv")):
        if "validation" in path.parts or path.name.startswith("prepared_"):
            continue
        frame = original_read(path)
        id_columns = [c for c in frame if c in {"canonical_player_id", "player_key", "player_1_canonical_id", "player_2_canonical_id"}]
        # Fastest exports deliberately store the canonical ID in player_id.
        if path.name == "fastest_batting_milestones.csv":
            id_columns += ["player_id"]
        mask = pd.Series(False, index=frame.index)
        for c in id_columns:
            mask |= frame[c].isin(affected)
        if not mask.any():
            continue
        original = frame.copy()
        for c in id_columns:
            frame[c] = frame[c].replace(redirects)
        if path.name in summary_specs:
            spec = summary_specs[path.name]
            reduced = consolidate(frame.loc[mask], *spec)
            from src.ui import layout
            if path.name == "dismissal_fingerprint_summary.csv":
                counts = pd.to_numeric(reduced["count"], errors="raise")
                totals = counts.groupby([reduced.canonical_player_id, reduced.scope]).transform("sum")
                reduced["total_dismissals"] = totals
                reduced["pct"] = counts.div(totals.where(totals.ne(0))).mul(100).fillna(0)
            if path.name == "bowling_phase_summary.csv":
                reduced["overs"] = pd.to_numeric(reduced.legal_balls).map(layout.format_balls_as_overs)
            if path.name == "performance_breakdown_by_dimension.csv":
                for i, row in reduced.iterrows():
                    if row.get("high_score", "") != "":
                        reduced.loc[i, "high_score_sort"] = layout.parse_high_score_value(row.high_score)[0]
                        reduced.loc[i, "high_score_not_out_sort"] = int("*" in str(row.high_score))
                    if row.discipline == "Bowling":
                        reduced.loc[i, "extras_pct"] = layout.calculate_extras_pct(row.no_balls, row.wides, row.balls_bowled)
            if path.name == "player_scorecard_milestones.csv":
                reduced["hs_sort"] = reduced.hs.map(lambda v: layout.parse_high_score_value(v)[0])
            if path.name == "player_bowling_milestones.csv":
                from scripts.build_hall_of_fame_detail_exports import parse_bbi
                reduced["bbi_wickets_sort"] = reduced.bbi.map(lambda v: parse_bbi(v)[0])
                reduced["bbi_runs_sort"] = reduced.bbi.map(lambda v: parse_bbi(v)[1])
            frame = pd.concat([frame.loc[~mask], reduced], ignore_index=True)
        if path.name == "player_premierships.csv":
            records = []
            for _, group in frame.loc[mask].groupby("canonical_player_id", sort=False):
                row = group.iloc[0].to_dict()
                union = lambda column: sorted({v.strip() for value in group[column] for v in str(value).split(",") if v.strip()})
                evidence = union("evidence_match_ids")
                if len(evidence) != pd.to_numeric(group.premiership_count).sum():
                    raise ValueError("Premiership evidence overlaps or is incomplete")
                row["premiership_count"] = len(evidence)
                for column in ["seasons", "evidence_match_ids"]:
                    row[column] = ", ".join(union(column))
                # Grade labels themselves contain commas; never split a label.
                for column in ["grades", "teams"]:
                    row[column] = ", ".join(group[column].drop_duplicates())
                row["latest_premiership_season"] = max(group.latest_premiership_season)
                records.append(row)
            frame = pd.concat([frame.loc[~mask], pd.DataFrame(records, columns=frame.columns)], ignore_index=True)
        if not frame.equals(original):
            frame.to_csv(path, index=False)
            changed.append(str(path.relative_to(ROOT)))

    # Rebuild only affected HOF rows from complete retained season aggregates.
    # Unaffected prepared history and governed overrides are never reconstructed.
    from src.ui import layout
    from src.data.hall_of_fame_prepared import FRAME_FILENAMES, prepared_core_source_signature
    raw, categories = {}, {}
    hof = processed / "hall_of_fame"
    for kind in ["batting", "bowling", "fielding"]:
        data = read(processed / f"all_seasons_{kind}.csv")
        data = data[data.canonical_player_id.isin(redirects.values())]
        # The standard category builder expects numeric source columns.
        raw[kind] = layout.apply_team_grade_display_columns(layout.normalise_player_names(data))
        categories[kind] = layout.combine_player_rows(raw[kind], kind)
        if kind == "batting":
            categories[kind] = layout.add_batting_display_columns(categories[kind])
        if kind == "fielding":
            categories[kind] = layout.add_display_stat_aliases(categories[kind])
    categories["all_time"] = layout.build_all_time_player_table(raw["batting"], raw["bowling"], raw["fielding"], categories["batting"], categories["bowling"], categories["fielding"])
    before = original_read(hof / FRAME_FILENAMES["all_time"])
    comparisons = []
    for key, filename in FRAME_FILENAMES.items():
        path = hof / filename
        old = original_read(path)
        new = categories[key].reindex(columns=old.columns)
        output = pd.concat([old[~old.canonical_player_id.isin(affected)], new], ignore_index=True)
        output.to_csv(path, index=False)
        changed.append(str(path.relative_to(ROOT)))
    for name, ds in pd.DataFrame(decisions).groupby("canonical_player_name"):
        old = before[before.canonical_player_id.isin(ds.previous_canonical_id)]
        new = categories["all_time"][categories["all_time"].canonical_player_id.eq(ds.iloc[0].canonical_player_id)].iloc[0]
        for metric in ["Matches", "Runs", "Wickets", "Catches"]:
            expected = pd.to_numeric(old[metric]).sum()
            if float(new[metric]) != expected:
                raise ValueError(f"Lost/duplicated complete contribution: {name} {metric}: {expected} -> {new[metric]}")
        comparisons.append(dict(club=club, player=name, canonical_player_id=ds.iloc[0].canonical_player_id,
                                before=json.dumps(old[["canonical_player_id", "Matches", "Runs", "Wickets", "Catches"]].to_dict("records")),
                                after=json.dumps({k: str(new[k]) for k in ["Matches", "Runs", "Wickets", "Catches"]}),
                                seasons=" | ".join(sorted({s for d in ds.seasons for s in d.split(" | ")}))))
    pd.DataFrame(comparisons).to_csv(audit / "identity_before_after.csv", index=False)
    manifest_path = hof / "prepared_core_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["source_signature"] = prepared_core_source_signature(club)
    manifest["row_counts"] = {key: len(read(hof / name)) for key, name in FRAME_FILENAMES.items()}
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    changed += [str(alias_path.relative_to(ROOT)), str(manifest_path.relative_to(ROOT)), str((base / "data/source/disjoint_season_identity_decisions.csv").relative_to(ROOT))]
    result = dict(club=club, groups=len(groups), eligible=len(eligible), merged=len(eligible), changed=changed,
                  hof_before=len(before), hof_after=len(read(hof / FRAME_FILENAMES["all_time"])))
    (audit / "implementation.json").write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--club", required=True, choices=["glen-waverley-hawks", "fvcc", "georges-river-district"])
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--baseline-ref", required=True, help="Immutable released source commit for reproducibility/resume")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(json.dumps(reconcile(args.club, args.audit_dir, args.baseline_ref, args.apply), indent=2))


if __name__ == "__main__":
    main()
