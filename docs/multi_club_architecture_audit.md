# Multi-Club Architecture Audit

Last updated: 2026-05-21

This audit captures FVCC-specific assumptions found while introducing the multi-club foundation. Phase 1 moved low-risk display identity and contact values into config. Phase 2 adds read-side path helpers while FVCC still points to the existing `data/...` layout.

## Config-Driven Now

| Area | Current hard-coded value | Files / functions | Action | Risk |
| --- | --- | --- | --- | --- |
| Club display name | `Fiji Victorian Cricket Club` | `src/ui/layout.py` page headers and labels | Read from `clubs/fvcc/club_config.yaml` | Low |
| Club short name | `FVCC` | `src/ui/layout.py` sidebar brand | Read from config `club.short_name` | Low |
| Sidebar shield text | `FV` | `src/ui/layout.py` sidebar brand | Derive from config short name | Low |
| Creator credit | `Siddhanth Chaurasiya`, `Preet Kaur` | `src/ui/layout.py` sidebar/mobile footer/context line | Read from config `contact.creators` | Low |
| Feedback email | `siddhanthchaurasiya@gmail.com` | `src/ui/layout.py` sidebar/mobile footer | Read from config `contact.feedback_email` | Low |
| App branding colours | current purple, maroon, lavender | `.streamlit/config.toml`, `src/ui/theme.py` | Record in config only; CSS still unchanged | Low |
| Runtime processed reads | existing `data/processed` folders | `src/config/club_config.py`, `src/data/playcricket_ingestion.py`, `src/ui/layout.py` | Read through club-aware helpers while still resolving to legacy paths | Low |
| Deploy-safe HOF reads | `data/processed/hall_of_fame/...` | `src/ui/layout.py` | Read through `get_hall_of_fame_path(...)` | Low |
| Deploy-safe Season Overview reads | `data/processed/season_overview/...` | `src/ui/layout.py` | Read through `get_season_overview_path(...)` | Low |

## Config Later

| Area | Current assumption | Files / functions affected | Recommended phase | Risk |
| --- | --- | --- | --- | --- |
| PlayCricket club ID / URL | FVCC UUID and club URL | `src/data/playcricket_ingestion.py`, `scripts/refresh_data.py` | Phase 4 refresh workflow | Medium |
| Processed data write paths | `data/processed/...` | refresh/export scripts under `scripts/` | Phase 4 refresh workflow | Medium |
| Deploy-safe export paths | `data/processed/hall_of_fame/...`, `data/processed/season_overview/...` | HOF and Season Overview export scripts | Phase 4 | Medium |
| Player alias and merge files | `data/player_aliases.csv`, `data/manual_player_merges.csv` | `src/utils/player_identity.py`, merge audit UI | Phase 3 | High |
| Team/grade labels | FVCC teams, NMCA grade naming, FVCC short-code assumptions | `src/utils/team_grade.py` | Phase 5 onboarding | High |
| Grade sort order | FVCC/NMCA grade ordering | `src/utils/team_grade.py`, UI sort helpers | Phase 2 config read, Phase 5 per-club mapping | Medium |
| Opponent normalization | reviewed FVCC opponent mappings | `src/data/name_normalization.py` | Phase 5 onboarding and review pack | High |
| Ground normalization | reviewed FVCC venue mappings | `src/data/name_normalization.py` | Phase 5 onboarding and review pack | High |
| Home ground assumptions | inferred from FVCC match context and reviewed venue labels | analytics/export scripts | Phase 6 QA pack | High |
| Match-centre FVCC filters | `is_fvcc_team_name`, `fvcc_team_id`, FVCC-only scorecard rows | `src/analytics/match_centre_advanced.py`, `src/data/match_centre_milestones.py`, `src/ui/layout.py` | Phase 4/5 | High |
| Refresh/backfill defaults | FVCC season/team IDs and local folders | `scripts/refresh_data.py`, `scripts/backfill_match_centre_available.py`, `scripts/pilot_match_centre_one_team_season.py` | Phase 4 | High |

## Remain Global

| Area | Reason |
| --- | --- |
| Cricket metric formulas | Batting average, strike rate, bowling average, BBI parsing, innings counting, and milestone definitions are sport rules rather than club rules. |
| Routing mechanics | Query-param routing and GA4 event wiring should stay shared across clubs. |
| Streamlit layout primitives | Card/table CSS structure can remain shared, with future branding overrides layered through config. |
| Experimental visibility default | `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES = False` remains a product safety default, not a club-specific setting in Phase 1. |

## Too Risky For Phase 1

- Refactoring `is_fvcc_team_name` and FVCC scorecard filters could change match ownership and player/opposition inclusion.
- Moving `data/...` into `clubs/fvcc/data` would touch every page and export script at once.
- Generalizing player aliases/merges before a club data layout exists would risk breaking canonical player records.
- Moving opponent/ground mappings into config without a review workflow would make data quality harder to audit.
- Changing refresh/backfill scripts before the app can read club-aware paths would create a split-brain workflow.

## Recommended Migration Order

1. Keep Phase 1 limited to config files, loader, display identity, docs, and validation.
2. Introduce read-only club-aware path helpers behind existing `data/...` defaults.
3. Move FVCC data under `clubs/fvcc/data` with a compatibility shim and prove pages still load.
4. Add `refresh_club.py --club fvcc` to centralize refresh paths and club IDs.
5. Add onboarding tools for new club config, team/grade mappings, identity aliases, and reviewed opponent/ground mappings.
6. Generate per-club QA reports before any new club is deployable.
