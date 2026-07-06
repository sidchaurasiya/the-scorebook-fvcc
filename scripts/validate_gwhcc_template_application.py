from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
CLUB_ID = "glen-waverley-hawks"
OUTPUT = (
    ROOT
    / "clubs"
    / CLUB_ID
    / "data"
    / "processed"
    / "validation"
    / "gwhcc_template_application_validation.csv"
)
EXPECTED_UUID = "50f7f1e3-86d8-eb11-a7ad-2818780da0cc"
COVERAGE_OUTPUT = OUTPUT.with_name("gwhcc_data_coverage_audit.csv")


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def row(check_name: str, passed: bool, notes: str) -> dict[str, str]:
    return {
        "check_name": check_name,
        "validation_status": "pass" if passed else "fail",
        "notes": notes,
    }


def csv_row_count(path: Path) -> int:
    if not path.exists():
        return -1
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        try:
            next(reader)
        except StopIteration:
            return 0
        return sum(1 for _ in reader)


def unique_values(path: Path, candidates: list[str]) -> set[str]:
    if not path.exists():
        return set()
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        columns = set(reader.fieldnames or [])
        field = next((name for name in candidates if name in columns), None)
        if not field:
            return set()
        return {str(row.get(field) or "").strip() for row in reader if str(row.get(field) or "").strip()}


def status_for_count(count: int, *, optional: bool = False) -> str:
    if count < 0:
        return "unavailable" if optional else "missing"
    if count == 0:
        return "unavailable" if optional else "empty"
    return "available"


def nested(config: dict[str, Any], *keys: str) -> Any:
    value: Any = config
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def load_config() -> dict[str, Any]:
    os.environ["CLUB_ID"] = CLUB_ID
    from src.config.club_config import load_club_config

    return load_club_config(CLUB_ID)


def main() -> int:
    config = load_config()
    club = config.get("club", {})
    branding = config.get("branding", {})
    features = config.get("features", {})
    processed = ROOT / "clubs" / CLUB_ID / "data" / "processed"
    layout = read_text("src/ui/layout.py")
    theme = read_text("src/ui/theme.py")
    config_text = read_text(f"clubs/{CLUB_ID}/club_config.yaml")

    required_datasets = {
        "matches": processed / "all_seasons_matches.csv",
        "batting_aggregate": processed / "all_seasons_batting.csv",
        "bowling_aggregate": processed / "all_seasons_bowling.csv",
        "fielding_aggregate": processed / "all_seasons_fielding.csv",
        "scorecard_batting": processed / "all_seasons_scorecard_batting.csv",
        "scorecard_bowling": processed / "all_seasons_scorecard_bowling.csv",
        "scorecard_fielding": processed / "all_seasons_scorecard_fielding.csv",
        "players": processed / "players.csv",
        "seasons": processed / "seasons.csv",
        "teams": processed / "teams.csv",
        "hof_win_rates": processed / "hall_of_fame" / "player_win_rates.csv",
        "hof_milestones": processed / "hall_of_fame" / "player_scorecard_milestones.csv",
        "hof_fastest_batting": processed / "hall_of_fame" / "fastest_batting_milestones.csv",
        "hof_bbb_batting": processed / "hall_of_fame" / "player_bbb_batting_rates.csv",
        "season_by_round": processed / "season_overview" / "season_by_round_scorecards.csv",
        "season_batting_scope": processed / "season_overview" / "scorecard_batting_milestones_by_scope.csv",
        "season_bowling_scope": processed / "season_overview" / "scorecard_bowling_milestones_by_scope.csv",
        "season_bbb_batting": processed / "season_overview" / "bbb_batting_rates_by_scope.csv",
        "season_bbb_bowling": processed / "season_overview" / "bbb_bowling_dot_rates_by_scope.csv",
        "player_profile_breakdown": processed / "player_profile" / "performance_breakdown_by_dimension.csv",
        "player_profile_bowling_phase": processed / "player_profile" / "bowling_phase_summary.csv",
        "player_profile_recent_batting": processed / "player_profile" / "recent_form_batting.csv",
        "player_profile_recent_bowling": processed / "player_profile" / "recent_form_bowling.csv",
    }
    counts = {name: csv_row_count(path) for name, path in required_datasets.items()}
    seasons = unique_values(required_datasets["seasons"], ["season_name", "name", "season", "display_name", "id"]) or unique_values(
        required_datasets["season_by_round"], ["season_name", "season"]
    )
    grades = unique_values(required_datasets["teams"], ["grade_name", "display_name", "team_name", "name"]) or unique_values(
        required_datasets["season_by_round"], ["grade_name", "grade_label"]
    )
    bbb_rows = counts["hof_bbb_batting"] + counts["season_bbb_batting"] + counts["season_bbb_bowling"] + counts["player_profile_bowling_phase"]
    if bbb_rows < 0:
        bbb_rows = 0

    colours = [
        branding.get("primary_colour"),
        branding.get("secondary_colour"),
        branding.get("accent_colour"),
        branding.get("muted_accent_colour"),
        branding.get("cream_accent_colour"),
        branding.get("background_colour"),
        branding.get("link_colour"),
        branding.get("link_hover_colour"),
        branding.get("nav_active_colour"),
    ]
    grdcc_fvcc_colours = {
        "#0B3F9F",
        "#082A66",
        "#79C8EE",
        "#D7193F",
        "#28A745",
        "#006D3B",
        "#FFD700",
    }
    configured_colours = {str(value).strip().upper() for value in colours if value}
    expected_colours = {"#FCD207", "#280B04", "#62431A", "#B39125", "#EDC778"}
    logo_path = ROOT / str(branding.get("logo_path") or "")
    optional_flags_off = all(
        not bool(features.get(name))
        for name in (
            "has_historical_excel",
            "has_annual_report_overrides",
            "enable_match_proxy",
            "enable_exact_name_nonoverlap_merge",
        )
    )
    grade_normalisation_path = ROOT / "clubs" / CLUB_ID / "data" / "source" / "gwhcc_grade_competition_normalisation.csv"

    rows = [
        row(
            "gwhcc_config_resolves",
            club.get("club_id") == CLUB_ID
            and club.get("display_name") == "Glen Waverley Hawks Cricket Club",
            "GWHCC club config loads through src.config.club_config.",
        ),
        row(
            "gwhcc_playhq_club_uuid_configured",
            club.get("playcricket_club_id") == EXPECTED_UUID and club.get("playhq_club_id") == EXPECTED_UUID,
            "Confirmed PlayCricket/PlayHQ club UUID is configured.",
        ),
        row(
            "gwhcc_logo_path_exists",
            bool(branding.get("logo_path")) and logo_path.exists(),
            f"Logo path should exist at {branding.get('logo_path')}.",
        ),
        row(
            "gwhcc_brand_colours_configured",
            expected_colours.issubset(configured_colours),
            "GWHCC gold/brown logo colours should be configured.",
        ),
        row(
            "gwhcc_theme_no_grdcc_fvcc_colour_copy",
            not bool(configured_colours & grdcc_fvcc_colours),
            "Configured GWHCC colours should not copy GRDCC/FVCC palette values by accident.",
        ),
        row(
            "required_app_datasets_exist",
            all(path.exists() for path in required_datasets.values()),
            "Required app-facing CSV files exist under the GWHCC processed tree.",
        ),
        row(
            "core_match_rows_available",
            counts["matches"] > 0,
            f"all_seasons_matches.csv rows={counts['matches']}.",
        ),
        row(
            "core_scorecard_rows_available",
            counts["scorecard_batting"] > 0 and counts["scorecard_bowling"] > 0 and counts["scorecard_fielding"] > 0,
            f"scorecard batting rows={counts['scorecard_batting']}; bowling rows={counts['scorecard_bowling']}; fielding rows={counts['scorecard_fielding']}.",
        ),
        row(
            "player_season_aggregates_available",
            counts["batting_aggregate"] > 0 and counts["bowling_aggregate"] > 0 and counts["fielding_aggregate"] > 0,
            f"Aggregate rows bat={counts['batting_aggregate']}; bowl={counts['bowling_aggregate']}; field={counts['fielding_aggregate']}.",
        ),
        row(
            "career_inputs_available",
            counts["players"] > 0 and counts["batting_aggregate"] > 0 and counts["bowling_aggregate"] > 0,
            f"players rows={counts['players']}; seasons={len(seasons)}; grades={len(grades)}.",
        ),
        row(
            "hof_sources_available",
            counts["hof_win_rates"] > 0 and counts["hof_milestones"] > 0,
            f"HOF win-rate rows={counts['hof_win_rates']}; scorecard milestone rows={counts['hof_milestones']}.",
        ),
        row(
            "season_overview_sources_available",
            counts["season_by_round"] > 0 and counts["season_batting_scope"] > 0 and counts["season_bowling_scope"] > 0,
            f"Season by Round rows={counts['season_by_round']}; batting scope rows={counts['season_batting_scope']}; bowling scope rows={counts['season_bowling_scope']}.",
        ),
        row(
            "player_profile_sources_available",
            counts["player_profile_breakdown"] > 0
            and counts["player_profile_recent_batting"] > 0
            and counts["player_profile_recent_bowling"] > 0,
            f"Profile breakdown rows={counts['player_profile_breakdown']}; recent bat={counts['player_profile_recent_batting']}; recent bowl={counts['player_profile_recent_bowling']}.",
        ),
        row(
            "bbb_summaries_reported",
            bbb_rows >= 0,
            f"BBB summary rows={bbb_rows}; zero means unavailable, not fabricated.",
        ),
        row(
            "sbr_template_classes_available",
            "season-round-panel-strip" in layout
            and "data-season-round-scroll-shell" in layout
            and "season-round-result" in theme,
            "Shared Season by Round responsive/scroll classes are present.",
        ),
        row(
            "kpi_card_template_available",
            "profile-kpi-card" in layout
            and "leader-highlight-card" in layout
            and ".kpi-card" in theme,
            "Shared KPI/Career Highlights card classes are present.",
        ),
        row(
            "team_grade_leaders_theme_driven",
            ".team-leader-card" in theme and "var(--club-primary" in theme and "link_colour" in theme,
            "Team/Grade Leaders styles use club CSS variables.",
        ),
        row(
            "grdcc_only_rules_disabled",
            optional_flags_off,
            "GWHCC keeps GRDCC historical/manual feature flags disabled; Hawks grade normalisation is governed by a club-local CSV.",
        ),
        row(
            "gwhcc_grade_normalisation_is_club_local",
            bool(features.get("enable_grade_opponent_normalisation")) and grade_normalisation_path.exists(),
            "Hawks grade normalisation may be enabled only with the club-local mapping CSV.",
        ),
        row(
            "no_grdcc_labels_in_gwhcc_config",
            "GRDCC" not in config_text
            and "Georges River" not in config_text
            and "georges-river-district" not in config_text,
            "GWHCC config should not contain GRDCC labels.",
        ),
        row(
            "dedicated_entrypoint_exists",
            (ROOT / "app_gwhcc.py").exists()
            and nested(config, "club", "streamlit_entrypoint") == "app_gwhcc.py",
            "Dedicated GWHCC entrypoint exists and config points to it.",
        ),
        row(
            "no_grdcc_fvcc_data_bleed_in_config_or_entrypoint",
            "georges-river-district" not in config_text
            and "GRDCC" not in config_text
            and "CLUB_ID\"] = \"glen-waverley-hawks\"" in read_text("app_gwhcc.py")
            and "CLUB_ID=fvcc" not in read_text("app_gwhcc.py"),
            "GWHCC runtime config and entrypoint should not select GRDCC/FVCC.",
        ),
    ]

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check_name", "validation_status", "notes"])
        writer.writeheader()
        writer.writerows(rows)

    write_coverage_audit(required_datasets, counts, seasons, grades, bbb_rows, failed=any(item["validation_status"] != "pass" for item in rows))

    failed = [item for item in rows if item["validation_status"] != "pass"]
    print(f"validation_status={'pass' if not failed else 'fail'} checks={len(rows)} failed={len(failed)}")
    print(f"output={OUTPUT}")
    for item in failed:
        print(f"FAIL {item['check_name']}: {item['notes']}")
    return 1 if failed else 0


def write_coverage_audit(
    datasets: dict[str, Path],
    counts: dict[str, int],
    seasons: set[str],
    grades: set[str],
    bbb_rows: int,
    *,
    failed: bool,
) -> None:
    scorecard_total = sum(max(counts[name], 0) for name in ("scorecard_batting", "scorecard_bowling", "scorecard_fielding"))
    rows = [
        {"area": "readiness", "metric": "readiness_status", "value": "blocked" if failed else "ready_for_local_smoke", "status": "fail" if failed else "pass", "notes": "Derived from GWHCC template validator."},
        {"area": "coverage", "metric": "seasons_found", "value": str(len(seasons)), "status": "available" if seasons else "missing", "notes": "; ".join(sorted(seasons)[:12])},
        {"area": "coverage", "metric": "teams_or_grades_found", "value": str(len(grades)), "status": "available" if grades else "missing", "notes": "; ".join(sorted(grades)[:12])},
        {"area": "coverage", "metric": "match_count", "value": str(counts["matches"]), "status": status_for_count(counts["matches"]), "notes": str(datasets["matches"])},
        {"area": "coverage", "metric": "scorecard_match_coverage", "value": str(scorecard_total), "status": status_for_count(scorecard_total), "notes": "All-seasons scorecard batting/bowling/fielding rows combined."},
        {"area": "coverage", "metric": "bbb_match_coverage", "value": str(bbb_rows), "status": status_for_count(bbb_rows, optional=True), "notes": "Processed BBB summary rows; unavailable is acceptable when source lacks BBB."},
        {"area": "coverage", "metric": "players_found", "value": str(counts["players"]), "status": status_for_count(counts["players"]), "notes": str(datasets["players"])},
    ]
    for name, path in datasets.items():
        rows.append(
            {
                "area": "dataset",
                "metric": name,
                "value": str(counts[name]),
                "status": status_for_count(counts[name], optional=name.startswith("season_bbb") or name.startswith("hof_bbb")),
                "notes": str(path),
            }
        )
    with COVERAGE_OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["area", "metric", "value", "status", "notes"])
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    raise SystemExit(main())
