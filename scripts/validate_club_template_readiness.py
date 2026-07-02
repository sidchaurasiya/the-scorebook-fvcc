from __future__ import annotations

import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "processed" / "validation" / "club_template_readiness_validation.csv"


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def status_row(check_name: str, passed: bool, notes: str) -> dict[str, str]:
    return {
        "check_name": check_name,
        "validation_status": "pass" if passed else "fail",
        "notes": notes,
    }


def config_text(club_id: str) -> str:
    return read_text(f"clubs/{club_id}/club_config.yaml")


def has_flag(text: str, name: str, value: bool) -> bool:
    expected = "true" if value else "false"
    return bool(re.search(rf"^\s*{re.escape(name)}:\s*{expected}\s*$", text, re.M))


def main() -> int:
    rows: list[dict[str, str]] = []
    layout = read_text("src/ui/layout.py")
    theme = read_text("src/ui/theme.py")
    analytics = read_text("src/utils/analytics.py")
    player_identity = read_text("src/utils/player_identity.py")
    ingestion = read_text("src/data/playcricket_ingestion.py")
    featured = read_text("src/data/featured_record_overrides.py")
    premierships = read_text("src/data/premiership_honours.py")
    clubs_py = read_text("src/config/clubs.py")
    grdcc = config_text("georges-river-district")
    fvcc = config_text("fvcc")
    hawks = config_text("glen-waverley-hawks")

    shared_ui = "\n".join([layout, theme])
    grdcc_colours = ("#0B3F9F", "#082A66", "#79C8EE", "#D7193F")
    rows.append(status_row(
        "shared_ui_no_grdcc_colour_literals",
        not any(colour in shared_ui for colour in grdcc_colours),
        "Shared UI should use club CSS variables and config colours, not GRDCC literal palette values.",
    ))
    rows.append(status_row(
        "shared_ui_grdcc_branches_scoped",
        "get_active_club_id() == \"georges-river-district\"" in layout
        and "get_feature_flag(\"enable_exact_name_nonoverlap_merge\"" in layout,
        "Remaining GRDCC layout branches are scoped to the active club and exact-name merge is feature-gated.",
    ))
    rows.append(status_row(
        "grdcc_config_resolves_template_schema",
        "club_id: georges-river-district" in grdcc
        and "streamlit_entrypoint: app_grdcc.py" in grdcc
        and has_flag(grdcc, "has_historical_excel", True)
        and has_flag(grdcc, "has_annual_report_overrides", True)
        and has_flag(grdcc, "enable_match_proxy", True)
        and has_flag(grdcc, "enable_exact_name_nonoverlap_merge", True),
        "GRDCC config keeps current historical feature flags enabled.",
    ))
    rows.append(status_row(
        "fvcc_config_resolves_template_schema",
        "club_id: fvcc" in fvcc
        and "streamlit_entrypoint: app.py" in fvcc
        and has_flag(fvcc, "has_historical_excel", False)
        and has_flag(fvcc, "has_annual_report_overrides", False)
        and has_flag(fvcc, "enable_match_proxy", False)
        and has_flag(fvcc, "enable_exact_name_nonoverlap_merge", False),
        "FVCC config keeps optional historical GRDCC modules disabled.",
    ))
    rows.append(status_row(
        "glen_waverley_hawks_config_exists",
        "club_id: glen-waverley-hawks" in hawks
        and "playcricket_club_id: 50f7f1e3-86d8-eb11-a7ad-2818780da0cc" in hawks
        and "playhq_club_id: 50f7f1e3-86d8-eb11-a7ad-2818780da0cc" in hawks
        and "logo_path: clubs/glen-waverley-hawks/assets/logo.png" in hawks
        and has_flag(hawks, "has_historical_excel", False)
        and has_flag(hawks, "has_annual_report_overrides", False)
        and has_flag(hawks, "enable_match_proxy", False)
        and has_flag(hawks, "enable_exact_name_nonoverlap_merge", False),
        "Glen Waverley Hawks config has the confirmed club UUID, branding path, and optional historical modules off.",
    ))
    rows.append(status_row(
        "typed_template_config_available",
        "class ClubTemplateConfig" in clubs_py
        and "playhq_config" in clubs_py
        and "enable_match_proxy" in clubs_py,
        "Typed club template config wrapper is available for future template code.",
    ))
    rows.append(status_row(
        "optional_historical_rules_gated",
        "get_feature_flag(\"has_historical_excel\"" in ingestion
        and "get_feature_flag(\"has_annual_report_overrides\"" in featured
        and "get_feature_flag(\"has_annual_report_overrides\"" in premierships
        and "get_feature_flag(\"enable_exact_name_nonoverlap_merge\"" in player_identity
        and "get_feature_flag(\"enable_match_proxy\"" in layout,
        "Excel, Annual Report, exact-name merge, and match proxy paths are feature-gated.",
    ))
    rows.append(status_row(
        "onboarding_docs_exist",
        (ROOT / "docs" / "new_club_onboarding_template.md").exists()
        and (ROOT / "docs" / "glen_waverley_hawks_onboarding.md").exists(),
        "New-club and Glen Waverley Hawks onboarding docs exist.",
    ))
    rows.append(status_row(
        "playhq_pipeline_template_doc_exists",
        (ROOT / "docs" / "playhq_club_data_pipeline_template.md").exists(),
        "PlayHQ pipeline template doc exists.",
    ))
    rows.append(status_row(
        "dedicated_entrypoint_pattern_documented",
        "Dedicated Streamlit Cloud entrypoint for <Club Name>" in read_text("docs/new_club_onboarding_template.md")
        and "os.environ[\"CLUB_ID\"] = \"<club-id>\"" in read_text("docs/new_club_onboarding_template.md"),
        "Dedicated Streamlit entrypoint pattern is documented.",
    ))
    rows.append(status_row(
        "responsive_components_theme_driven",
        "season-round-panel-strip" in layout
        and "data-season-round-scroll-shell" in layout
        and "render_folder_tab_widget" in layout
        and "var(--club-primary" in theme
        and "var(--club-secondary" in theme,
        "Season by Round, folder tabs, and shared visual styles are reusable through club theme variables.",
    ))
    rows.append(status_row(
        "ga4_club_metadata_supported",
        "\"club_id\": _safe_active_club_id()" in analytics
        and "\"club_name\": _safe_club_name()" in analytics
        and "ga4_club_name" in grdcc
        and "ga4_club_name" in fvcc,
        "GA4 events include club_id and club_name metadata; club configs include GA display metadata.",
    ))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check_name", "validation_status", "notes"])
        writer.writeheader()
        writer.writerows(rows)

    failed = [row for row in rows if row["validation_status"] != "pass"]
    print(f"validation_status={'pass' if not failed else 'fail'} checks={len(rows)} failed={len(failed)}")
    print(f"output={OUTPUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
