"""Reconcile Cam's two approved Somaia identities from an immutable release.

Only ID-attributed rows are changed. Original provider IDs, scorecards and source
names remain evidence. This is not a whole-club or current-season refresh.
"""
from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CLUB = "glen-waverley-hawks"
NAME = "Sunil Somaia"
SOURCE_NAMES = {
    "7ceaa8ee-ed93-4785-a4b4-8c670b67fd97": "Sunny Somaia",
    "87dcf20b-a607-4346-a352-899db515d5fb": "Sunil Somaia",
}
SOURCE_KEYS = {"raw_" + value.replace("-", "_") for value in SOURCE_NAMES}
CANONICAL = "raw_7ceaa8ee_ed93_4785_a4b4_8c670b67fd97"


def verify_disjoint_source_evidence(aggregates: dict, cards: dict) -> None:
    for category, frame in aggregates.items():
        rows = frame[frame.raw_player_id.isin(SOURCE_NAMES)]
        if set(rows.raw_player_id) != set(SOURCE_NAMES):
            raise ValueError(f"Missing approved source identity: {category}")
        if not all(set(rows[rows.raw_player_id.eq(id)].raw_player_name.str.casefold()) == {name.casefold()}
                   for id, name in SOURCE_NAMES.items()):
            raise ValueError("Unexpected source name for approved ID")
        a, b = [set(rows[rows.raw_player_id.eq(id)].season) for id in SOURCE_NAMES]
        if not a or not b or a & b:
            raise ValueError("Overlapping/incomplete seasons require contribution-level review")
        if rows.duplicated(["season", "team_id", "grade_id", "raw_player_id"]).any():
            raise ValueError("Duplicate source aggregate contribution")
    match_sets = {id: set() for id in SOURCE_NAMES}
    for frame in cards.values():
        for id in SOURCE_NAMES:
            match_sets[id].update(frame.loc[frame.player_id.eq(id), "match_id"])
    if set.intersection(*match_sets.values()):
        raise ValueError("Overlapping scorecards quarantined; never sum ambiguous innings")


def reconcile(baseline: str, audit: Path) -> dict:
    os.environ["CLUB_ID"] = CLUB
    from scripts.build_gwhcc_weekly_candidate import canonicalise_summary, summary_specs
    from scripts.reconcile_disjoint_player_identities import consolidate
    from src.data.gwhcc_identity import NAME_VARIANT_APPROVAL
    from src.data.hall_of_fame_prepared import FRAME_FILENAMES, prepared_core_source_signature
    from src.data.gwhcc_document_overrides import apply_record_overrides
    from src.ui import layout
    from src.utils.player_identity import ALIAS_COLUMNS, apply_player_identity_mapping

    audit.mkdir(parents=True, exist_ok=True)
    club = ROOT / "clubs" / CLUB
    data = club / "data/processed"
    changed = []

    def released(path):
        relative = str(path.relative_to(ROOT))
        value = subprocess.check_output(["git", "show", f"{baseline}:{relative}"], cwd=ROOT)
        return pd.read_csv(io.BytesIO(value), dtype=str, keep_default_na=False)

    def write(path, frame):
        old = released(path)
        if not frame.reset_index(drop=True).equals(old.reset_index(drop=True)):
            frame.to_csv(path, index=False)
            changed.append(str(path.relative_to(ROOT)))

    aggregates = {kind: released(data / f"all_seasons_{kind}.csv") for kind in ["batting", "bowling", "fielding"]}
    cards = {kind: released(data / f"all_seasons_scorecard_{kind}.csv") for kind in aggregates}
    verify_disjoint_source_evidence(aggregates, cards)
    old_decisions = released(club / "data/source/disjoint_season_identity_decisions.csv")
    old_decisions["source_name"] = ""
    new_decisions = pd.DataFrame([
        {"club": CLUB, "canonical_player_id": CANONICAL, "canonical_player_name": NAME,
         "raw_player_id": id, "previous_canonical_id": "raw_" + id.replace("-", "_"),
         "seasons": " | ".join(sorted(set(aggregates["batting"].loc[aggregates["batting"].raw_player_id.eq(id), "season"]))),
         "decision": NAME_VARIANT_APPROVAL, "source_name": name}
        for id, name in SOURCE_NAMES.items()
    ])
    write(club / "data/source/disjoint_season_identity_decisions.csv", pd.concat([old_decisions, new_decisions], ignore_index=True))
    aliases_path = club / "player_aliases.csv"
    aliases = released(aliases_path)
    additions = pd.DataFrame([
        dict(canonical_player_id=CANONICAL, canonical_player_name=NAME, raw_player_id=id,
             raw_player_name="", alias_name="", is_active="true", merge_source=NAME_VARIANT_APPROVAL,
             notes="Cam Hocart explicitly confirmed 22 October 2026: Sunil/Sunny Somaia are one player; ID-only mapping, disjoint retained histories; approved canonical display Sunil Somaia.")
        for id in SOURCE_NAMES
    ], columns=ALIAS_COLUMNS)
    write(aliases_path, pd.concat([aliases, additions], ignore_index=True))

    # Raw IDs/names and every numeric team/season contribution are conserved.
    for kind, frame in aggregates.items():
        mapped = apply_player_identity_mapping(frame, club_id=CLUB)
        affected = frame.raw_player_id.isin(SOURCE_NAMES)
        output = frame.copy()
        for column in ["canonical_player_id", "canonical_player_name"]:
            output.loc[affected, column] = mapped.loc[affected, column]
        write(data / f"all_seasons_{kind}.csv", output)

    # Preserve the identities of already-governed history, never add new totals.
    for filename in ["gwhcc_historical_centuries.csv", "gwhcc_historical_partnerships.csv"]:
        path = club / "data/source/document_overrides" / filename
        frame = released(path)
        for id_column, name_column in [("canonical_player_id", "canonical_player_name"),
                                      ("player_1_canonical_id", "player_1_name"), ("player_2_canonical_id", "player_2_name")]:
            if id_column in frame:
                affected = frame[id_column].isin(SOURCE_KEYS)
                frame.loc[affected, id_column] = CANONICAL
                frame.loc[affected, name_column] = NAME
        write(path, frame)
    path = club / "data/source/document_overrides/gwhcc_document_player_aliases.csv"
    frame = released(path)
    frame.loc[frame.playcricket_player_name.eq("Sunny Somaia"), "playcricket_player_name"] = NAME
    write(path, frame)

    specs = summary_specs()
    for path in sorted(data.rglob("*.csv")):
        if "validation" in path.parts or path.name.startswith(("all_seasons_", "prepared_")):
            continue
        frame = released(path)
        id_columns = [c for c in frame if c in {"canonical_player_id", "player_key", "player_1_canonical_id", "player_2_canonical_id"}]
        affected = pd.Series(False, index=frame.index)
        for column in id_columns:
            affected |= frame[column].isin(SOURCE_KEYS)
        if path.name == "fastest_batting_milestones.csv":
            # This evidence export retains provider IDs; change only its public name.
            affected |= frame.player_id.isin(SOURCE_NAMES)
        if not affected.any():
            continue
        relative = str(path.relative_to(data))
        if relative in specs:
            frame = canonicalise_summary(frame, new_decisions, specs[relative], path.name)
        else:
            for column in id_columns:
                matching = frame[column].isin(SOURCE_KEYS)
                frame.loc[matching, column] = CANONICAL
                names = {"player_1_canonical_id": "player_1_name", "player_2_canonical_id": "player_2_name"}
                if column in names:
                    frame.loc[matching, names[column]] = NAME
            for column in ["canonical_player_name", "display_player_name"]:
                if column in frame:
                    frame.loc[affected, column] = NAME
        if "player_name_key" in frame:
            frame.loc[frame.canonical_player_id.eq(CANONICAL), "player_name_key"] = layout.player_name_match_key(NAME)
        if path.name == "player_premierships.csv":
            selected = frame[affected]
            record = selected.iloc[0].copy()
            evidence = {part.strip() for text in selected.evidence_match_ids for part in text.split(",") if part.strip()}
            if len(evidence) != pd.to_numeric(selected.premiership_count).sum():
                raise ValueError("Premiership evidence needs overlap review")
            record["premiership_count"] = str(len(evidence))
            record["evidence_match_ids"] = ", ".join(sorted(evidence))
            seasons = {part.strip() for text in selected.seasons for part in text.split(",") if part.strip()}
            record["seasons"] = ", ".join(sorted(seasons))
            for column in ["grades", "teams"]:
                record[column] = ", ".join(selected[column].drop_duplicates())
            record["latest_premiership_season"] = max(selected.latest_premiership_season)
            frame = pd.concat([frame[~affected], pd.DataFrame([record])], ignore_index=True)
        write(path, frame)

    # Name-only round summaries are changed only with matching source-ID evidence.
    path = data / "season_overview/season_by_round_scorecards.csv"
    frame = released(path)
    for kind, column in [("batting", "best_batter"), ("bowling", "best_bowler")]:
        valid = set(cards[kind].loc[cards[kind].player_id.isin(SOURCE_NAMES), "match_id"])
        mask = frame.match_id.isin(valid) & frame[column].str.match(r"^Sunny Somaia(?:\s|$)")
        frame.loc[mask, column] = frame.loc[mask, column].str.replace(r"^Sunny Somaia", NAME, regex=True)
    write(path, frame)

    categories, raw = {}, {}
    for kind in aggregates:
        frame = pd.read_csv(data / f"all_seasons_{kind}.csv", low_memory=False)
        frame = frame[frame.raw_player_id.isin(SOURCE_NAMES)]
        raw[kind] = layout.apply_team_grade_display_columns(layout.normalise_player_names(frame))
        categories[kind] = layout.combine_player_rows(raw[kind], kind)
        if kind == "batting":
            categories[kind] = layout.add_batting_display_columns(categories[kind])
        if kind == "fielding":
            categories[kind] = layout.add_display_stat_aliases(categories[kind])
    categories["all_time"] = layout.build_all_time_player_table(raw["batting"], raw["bowling"], raw["fielding"], categories["batting"], categories["bowling"], categories["fielding"])
    before = released(data / "hall_of_fame/prepared_career_all_time.csv")
    for kind, filename in FRAME_FILENAMES.items():
        path = data / "hall_of_fame" / filename
        old = released(path)
        new = categories[kind].reindex(columns=old.columns)
        assert len(new) == 1 and new.canonical_player_id.eq(CANONICAL).all()
        write(path, pd.concat([old[~old.canonical_player_id.isin(SOURCE_KEYS)], new], ignore_index=True))
    path = data / "hall_of_fame/prepared_core_manifest.json"
    manifest = json.loads(subprocess.check_output(["git", "show", f"{baseline}:{path.relative_to(ROOT)}"], cwd=ROOT))
    manifest["source_signature"] = prepared_core_source_signature(CLUB)
    manifest["row_counts"] = {kind: len(pd.read_csv(data / "hall_of_fame" / filename)) for kind, filename in FRAME_FILENAMES.items()}
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    changed.append(str(path.relative_to(ROOT)))
    public = apply_record_overrides(categories["all_time"], write_decisions=False)
    public = layout.add_gwhcc_not_outs_for_display(public, categories["batting"])
    public.to_csv(audit / "after_authoritative_career.csv", index=False)
    before_public = apply_record_overrides(before, write_decisions=False)
    comparison = []
    for column in ["Matches", "Runs", "Innings", "Bat Avg", "HS", "50s", "100s", "Wickets", "Bowl Avg", "BBI", "Catches", "Stumpings", "Run Outs", "Dismissals"]:
        old = before_public[before_public.canonical_player_id.isin(SOURCE_KEYS)]
        comparison.append({"metric": column, "before": json.dumps(old[["Player", column]].to_dict("records")), "after": str(public.iloc[0][column])})
    pd.DataFrame(comparison).to_csv(audit / "career_before_after.csv", index=False)
    result = {"baseline": baseline, "canonical_player_id": CANONICAL, "name": NAME,
              "source_ids": SOURCE_NAMES, "changed": sorted(set(changed)), "duplicates_removed": 0,
              "source_match_overlap": 0, "public_hof_before": len(before), "public_hof_after": manifest["row_counts"]["all_time"]}
    (audit / "implementation.json").write_text(json.dumps(result, indent=2))
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(reconcile(args.baseline_ref, args.audit_dir), indent=2))
