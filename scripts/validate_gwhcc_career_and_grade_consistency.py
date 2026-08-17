from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
CLUB_ID = "glen-waverley-hawks"
VALIDATION_DIR = ROOT / "clubs" / CLUB_ID / "data" / "processed" / "validation"
CAREER_OUTPUT = VALIDATION_DIR / "gwhcc_cross_page_career_totals_validation.csv"
GRADE_OUTPUT = VALIDATION_DIR / "gwhcc_current_team_grade_governance_validation.csv"
SUMMARY_OUTPUT = VALIDATION_DIR / "gwhcc_career_and_grade_consistency_validation.csv"
DUPLICATE_OUTPUT = VALIDATION_DIR / "gwhcc_duplicate_identity_review.csv"

DUPLICATE_REVIEW = {
    "********": ("CONFIRMED DIFFERENT PEOPLE", "Retain four distinct backend identities; exclude all from public UI."),
    "Nathan Bungey": ("CONFIRMED SAME PERSON", "Merged through governed manual identity mapping after non-overlapping continuity review."),
    "Aaditya Sharma": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Same display name is insufficient evidence for a merge."),
    "Ahilan Sivakumaran": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Same display name is insufficient evidence for a merge."),
    "Ashton Scott": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Overlapping source history requires club confirmation."),
    "Darsh Singh": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Same display name is insufficient evidence for a merge."),
    "Greg Mccormick": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Same display name is insufficient evidence for a merge."),
    "Krish Agrawal": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Multiple source identities require club confirmation."),
    "Liam O'Rourke": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Same display name is insufficient evidence for a merge."),
    "Martin Fleming": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Overlapping source history requires club confirmation."),
    "Mitchell Kohne": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Same display name is insufficient evidence for a merge."),
    "N Cameron": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Initial-only given name is not safe to merge."),
    "Neeraj Kochhar": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Overlapping source history requires club confirmation."),
    "Peter Schultz": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Three source identities require club confirmation."),
    "Reece Anderson": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Same display name is insufficient evidence for a merge."),
    "Sandeep Gadgil": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Overlapping source history requires club confirmation."),
    "Scott Mills": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Overlapping source history requires club confirmation."),
    "Thilanga Jayasuriya": ("AMBIGUOUS / NEEDS CLUB REVIEW", "Overlapping source history requires club confirmation."),
}


def check_row(name: str, passed: bool, notes: str) -> dict[str, str]:
    return {
        "check_name": name,
        "validation_status": "pass" if passed else "fail",
        "notes": notes,
    }


def numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_numeric(frame.get(column, pd.Series(0, index=frame.index)), errors="coerce").fillna(0)


def sample_career_rows(all_time: pd.DataFrame, active_ids: set[str]) -> pd.DataFrame:
    selected: list[str] = []

    def add_ids(values: pd.Series) -> None:
        for value in values.dropna().astype(str):
            if value and value not in selected:
                selected.append(value)

    paul = all_time[all_time["Player"].astype(str).str.casefold().eq("paul young")]
    add_ids(paul["canonical_player_id"])
    for required_name in ["grant haye", "nathan bungey", "aansh pandya"]:
        add_ids(all_time.loc[all_time["Player"].astype(str).str.casefold().eq(required_name), "canonical_player_id"])

    override_columns = [column for column in all_time if column.endswith("_override_applied")]
    if override_columns:
        override_mask = pd.Series(False, index=all_time.index)
        for column in override_columns:
            override_mask |= all_time[column].astype(str).str.casefold().isin({"yes", "true", "1"})
        add_ids(all_time.loc[override_mask, "canonical_player_id"].head(6))

    manual_path = ROOT / "clubs" / CLUB_ID / "manual_player_merges.csv"
    manual = pd.read_csv(manual_path, dtype=str).fillna("") if manual_path.exists() else pd.DataFrame()
    if not manual.empty:
        merged_names = manual.groupby("canonical_player_name")["raw_player_id"].nunique()
        merged_names = merged_names[merged_names > 1].index.astype(str)
        add_ids(all_time.loc[all_time["Player"].isin(merged_names), "canonical_player_id"].head(4))

    ranked = all_time.assign(_runs=numeric(all_time, "Runs")).sort_values("_runs", ascending=False)
    add_ids(ranked["canonical_player_id"].head(8))

    active_low = all_time[all_time["canonical_player_id"].astype(str).isin(active_ids)].copy()
    active_low["_career_total"] = numeric(active_low, "Runs") + numeric(active_low, "Wickets") + numeric(active_low, "Catches")
    add_ids(active_low.sort_values("_career_total")["canonical_player_id"].head(4))
    return all_time[all_time["canonical_player_id"].astype(str).isin(selected[:16])].copy()


def duplicate_identity_review() -> pd.DataFrame:
    frames = []
    for category in ["batting", "bowling", "fielding"]:
        path = ROOT / "clubs" / CLUB_ID / "data" / "processed" / f"all_seasons_{category}.csv"
        frame = pd.read_csv(path, dtype=str, low_memory=False).fillna("")
        columns = [column for column in ["raw_player_id", "player_id", "raw_player_name", "player_name", "season"] if column in frame]
        frames.append(frame[columns].copy())
    source = pd.concat(frames, ignore_index=True, sort=False)
    source["review_name"] = source.get("raw_player_name", source.get("player_name", "")).astype(str).str.strip()
    source["review_id"] = source.get("raw_player_id", source.get("player_id", "")).astype(str).str.strip()
    rows = []
    for display_name, (classification, action) in DUPLICATE_REVIEW.items():
        selected = source[source["review_name"].str.casefold().eq(display_name.casefold())]
        rows.append(
            {
                "display_name": display_name,
                "source_ids": " | ".join(sorted(value for value in selected["review_id"].unique() if value)),
                "seasons": " | ".join(sorted(value for value in selected.get("season", pd.Series(dtype=str)).unique() if value)),
                "classification": classification,
                "action": action,
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    os.environ["CLUB_ID"] = CLUB_ID
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from src.data.gwhcc_governance import annotate_grade_metadata, load_grade_mapping
    from src.data.hall_of_fame_prepared import load_prepared_hall_of_fame_core
    from src.data.playcricket_ingestion import read_processed_table
    from src.ui import layout
    from src.utils.player_identity import get_player_profile_data, is_private_or_anonymised_player

    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)
    prepared = layout.get_hall_of_fame_data(
        layout.metadata_mtime(),
        layout.player_aliases_mtime(),
        layout.HALL_OF_FAME_DATA_VERSION,
        layout.hall_of_fame_override_signature(CLUB_ID),
        club_id=CLUB_ID,
    )
    if prepared is None:
        print("FAIL: GWHCC prepared career data is unavailable.")
        return 1

    hof = prepared["all_time"].copy()
    milestone = prepared["all_time"].copy()
    active_ids = layout.recent_active_canonical_players(prepared)
    samples = sample_career_rows(hof, active_ids)
    comparison = samples[["canonical_player_id", "Player"]].copy()
    comparison = comparison.rename(columns={"Player": "Canonical Player"})
    milestone_by_id = milestone.set_index("canonical_player_id")
    for metric in ["Matches", "Runs", "Wickets", "Catches"]:
        comparison[f"Hall of Fame {metric}"] = numeric(samples, metric).values
        comparison[f"Milestone {metric}"] = comparison["canonical_player_id"].map(
            pd.to_numeric(milestone_by_id[metric], errors="coerce").fillna(0)
        )
    profile_values: dict[str, dict[str, float]] = {}
    for canonical_id in comparison["canonical_player_id"].astype(str):
        profile = get_player_profile_data(
            canonical_id,
            layout.metadata_mtime(),
            layout.player_aliases_mtime(club_id=CLUB_ID),
            club_id=CLUB_ID,
        )
        view = layout.build_player_profile_view(profile, layout.player_profile_view_signature())
        row = view["career"].iloc[0] if not view["career"].empty else pd.Series(dtype=object)
        profile_values[canonical_id] = {}
        for metric in ["Matches", "Runs", "Wickets", "Catches"]:
            value = pd.to_numeric(row.get(metric), errors="coerce")
            profile_values[canonical_id][metric] = 0.0 if pd.isna(value) else float(value)
    for metric in ["Matches", "Runs", "Wickets", "Catches"]:
        comparison[f"Player Profile {metric}"] = comparison["canonical_player_id"].map(
            lambda player_id, m=metric: profile_values.get(player_id, {}).get(m, 0)
        )
    comparison["totals_match"] = comparison.apply(
        lambda row: all(
            row[f"Hall of Fame {metric}"] == row[f"Milestone {metric}"] == row[f"Player Profile {metric}"]
            for metric in ["Matches", "Runs", "Wickets", "Catches"]
        ),
        axis=1,
    )
    comparison = comparison.sort_values(["Canonical Player", "canonical_player_id"])
    comparison.to_csv(CAREER_OUTPUT, index=False)

    persisted_teams = read_processed_table("teams")
    persisted_teams = persisted_teams[persisted_teams["season"].astype(str).eq("Summer 2025/26")].copy()
    persisted_teams["persisted_governance_category"] = persisted_teams.get("grade_group", "")
    expected_teams = annotate_grade_metadata(persisted_teams.drop(columns=["grade_group"], errors="ignore"), grade_column="grade_name")
    expected_teams["expected_governance_category"] = expected_teams["grade_group"]
    expected_teams["source_team_sequence"] = expected_teams.apply(
        lambda row: layout.gwhcc_team_source_sequence({"name": row.get("team_name", "")}),
        axis=1,
    )
    grade_audit = expected_teams[
        ["team_id", "team_name", "grade_name", "display_grade_name", "source_team_sequence", "expected_governance_category", "persisted_governance_category"]
    ].rename(
        columns={
            "team_name": "source_team_name",
            "grade_name": "raw_grade_name",
        }
    )
    grade_audit = grade_audit.sort_values(
        ["source_team_sequence", "source_team_name"],
        na_position="last",
    )
    grade_audit.to_csv(GRADE_OUTPUT, index=False)
    duplicate_review = duplicate_identity_review()
    duplicate_review.to_csv(DUPLICATE_OUTPUT, index=False)

    mapping = load_grade_mapping()
    activity = pd.concat(
        [prepared["batting_raw"], prepared["bowling_raw"], prepared["fielding_raw"]],
        ignore_index=True,
        sort=False,
    )
    latest_three = layout.latest_activity_seasons(activity, 3)
    paul = hof[hof["Player"].astype(str).str.casefold().eq("paul young")]
    watchlist = layout.build_approaching_milestone_watchlist(hof)
    duplicate_watch = watchlist.duplicated(["canonical_player_id", "Category"], keep=False)
    known_junior = mapping["raw_grade_name"].astype(str).str.contains(
        r"Super 7|Fast 9|\bU(?:12|13|14|16)\b|Girls Stage 1",
        case=False,
        regex=True,
        na=False,
    )
    junior_failures = mapping[known_junior & ~mapping["grade_group"].astype(str).eq("Junior")]
    canonical_label = mapping.loc[
        mapping["raw_grade_name"].astype(str).str.contains("Compare & Conect", case=False, na=False),
        "display_grade_name",
    ]
    first_three = grade_audit[grade_audit["source_team_sequence"].isin([1.0, 2.0, 3.0])]
    first_three_labels = first_three.sort_values("source_team_sequence")["display_grade_name"].tolist()
    expected_first_three = ["Compare & Connect Dorothy McIntosh Shield", "C Grade", "D Grade"]
    prepared_core = load_prepared_hall_of_fame_core(CLUB_ID, layout.HALL_OF_FAME_DATA_VERSION)
    wrong_version_core = load_prepared_hall_of_fame_core(CLUB_ID, f"{layout.HALL_OF_FAME_DATA_VERSION}-stale")
    private_visible = hof[hof["Player"].map(is_private_or_anonymised_player)]
    nathan = hof[hof["Player"].astype(str).str.casefold().eq("nathan bungey")]
    governance_matches = grade_audit["expected_governance_category"].astype(str).eq(
        grade_audit["persisted_governance_category"].astype(str)
    )

    checks = [
        check_row("prepared_career_ids_unique", not hof["canonical_player_id"].duplicated().any(), f"rows={len(hof)}; duplicate canonical IDs={int(hof['canonical_player_id'].duplicated().sum())}."),
        check_row("paul_young_resolves_once", len(paul) == 1 and paul.iloc[0]["canonical_player_id"] == "paul_young", f"Paul Young prepared rows={len(paul)}."),
        check_row("nathan_bungey_resolves_once", len(nathan) == 1 and nathan.iloc[0]["canonical_player_id"] == "nathan_bungey", f"Nathan Bungey prepared rows={len(nathan)}."),
        check_row("private_players_excluded_from_authoritative_career", private_visible.empty, f"Visible private rows={len(private_visible)}."),
        check_row("hof_milestone_totals_match", len(comparison) >= 10 and comparison["totals_match"].all(), f"Compared {len(comparison)} authoritative player rows."),
        check_row("milestone_no_duplicate_player_metric", not duplicate_watch.any(), f"Duplicate canonical player/category rows={int(duplicate_watch.sum())}."),
        check_row("gwhcc_active_window_three_relevant_seasons", len(latest_three) == 3 and set(latest_three).issubset(set(activity["season"].astype(str))), f"Active seasons={latest_three}."),
        check_row("compare_connect_canonical_display", not canonical_label.empty and canonical_label.eq("Compare & Connect Dorothy McIntosh Shield").all(), f"Canonical labels={canonical_label.tolist()}."),
        check_row("known_juniors_governed_as_junior", junior_failures.empty, f"Incorrect known junior mappings={len(junior_failures)}."),
        check_row("persisted_governance_matches_expected", governance_matches.all(), f"Mismatched persisted rows={int((~governance_matches).sum())}."),
        check_row("summer_2025_26_first_three_team_order", first_three_labels == expected_first_three, f"First three={first_three_labels}."),
        check_row("summer_2025_26_team_ids_preserved", grade_audit["team_id"].nunique() == len(grade_audit), f"Rows={len(grade_audit)}; unique team IDs={grade_audit['team_id'].nunique()}."),
        check_row(
            "prepared_hof_core_current",
            prepared_core is not None and len(prepared_core.get("all_time", [])) == len(hof),
            f"Prepared rows={len(prepared_core.get('all_time', [])) if prepared_core else 0}; authoritative rows={len(hof)}.",
        ),
        check_row(
            "prepared_hof_core_version_guard",
            wrong_version_core is None,
            "A mismatched Hall of Fame data version must reject the prepared snapshot.",
        ),
    ]
    summary = pd.DataFrame(checks)
    summary.to_csv(SUMMARY_OUTPUT, index=False)
    failures = summary[summary["validation_status"].eq("fail")]
    print(f"GWHCC career/grade consistency: {len(summary) - len(failures)}/{len(summary)} checks passed")
    print(f"Career comparison: {CAREER_OUTPUT}")
    print(f"Grade governance: {GRADE_OUTPUT}")
    print(f"Duplicate identity review: {DUPLICATE_OUTPUT}")
    if not failures.empty:
        print(failures[["check_name", "notes"]].to_string(index=False))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
