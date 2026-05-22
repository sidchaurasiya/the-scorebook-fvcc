# Multi-Club Architecture Audit

Last updated: 2026-05-22

This audit captures FVCC-specific assumptions found while introducing the multi-club foundation. Phase 1 moved low-risk display identity and contact values into config. Phase 2 added read-side path helpers. Phase 3 copied FVCC production-safe processed data under `clubs/fvcc/data` while keeping legacy fallback paths. Phase 5 made the aggregate refresh/write path club-aware by default. Phase 6 added club-aware dry-run/reporting to match-centre workflows without moving raw/generated match-centre folders. Phase 6.5 introduced club-neutral match-centre ownership fields with fallback support for existing FVCC generated files.

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
| Club production data copies | `clubs/fvcc/data/processed/...` | `clubs/fvcc/club_config.yaml`, `src/config/club_config.py` | Prefer club-specific processed CSVs with legacy fallback | Low |

## Config Later

| Area | Current assumption | Files / functions affected | Recommended phase | Risk |
| --- | --- | --- | --- | --- |
| PlayCricket club ID / URL | FVCC UUID and club URL | `scripts/refresh_data.py`, `clubs/fvcc/club_config.yaml` | Config-driven for aggregate refresh; ingestion default remains legacy-compatible | Medium |
| Processed data write paths | `data/processed/...` | `scripts/refresh_data.py`, `src/data/playcricket_ingestion.py`, `src/utils/player_identity.py` | Aggregate refresh now writes to `clubs/<club_id>/data/processed` by default; `--legacy-output` remains explicit | Medium |
| Deploy-safe export paths | `data/processed/hall_of_fame/...`, `data/processed/season_overview/...` | HOF and Season Overview export scripts | Phase 4 | Medium |
| Player alias and merge files | `data/player_aliases.csv`, `data/manual_player_merges.csv` | `src/utils/player_identity.py`, merge audit UI | Phase 4/5 | High |
| Team/grade labels | FVCC teams, NMCA grade naming, FVCC short-code assumptions | `src/utils/team_grade.py` | Phase 5 onboarding | High |
| Grade sort order | FVCC/NMCA grade ordering | `src/utils/team_grade.py`, UI sort helpers | Phase 2 config read, Phase 5 per-club mapping | Medium |
| Opponent normalization | reviewed FVCC opponent mappings | `src/data/name_normalization.py` | Phase 5 onboarding and review pack | High |
| Ground normalization | reviewed FVCC venue mappings | `src/data/name_normalization.py` | Phase 5 onboarding and review pack | High |
| Home ground assumptions | inferred from FVCC match context and reviewed venue labels | analytics/export scripts | Phase 6 QA pack | High |
| Match-centre ownership fields | legacy `is_fvcc_team_name`, `fvcc_team_id`, `fvcc_team_name`, `is_fvcc_player` | `src/data/match_centre_ownership.py`, `src/data/ball_by_ball_parser.py`, match-centre builders/exporters | Phase 6.5 introduced neutral fields and legacy fallback; deeper UI/schema cleanup remains later | High |
| Refresh/backfill defaults | FVCC season/team IDs and local folders | `scripts/refresh_data.py`, `scripts/backfill_match_centre_available.py`, `scripts/pilot_match_centre_one_team_season.py` | Aggregate refresh is Phase 5; match-centre raw/backfill remains later | High |

## Phase 4 Refresh / Export Script Audit

| Script / module | Current inputs | Current outputs | Config usage after Phase 4 | Phase 4 action | Risk |
| --- | --- | --- | --- | --- | --- |
| `scripts/build_season_overview_detail_exports.py` | `data/processed/match_centre`, club `teams.csv` | `clubs/<club_id>/data/processed/season_overview` by default | `--club`, `get_processed_match_centre_dir`, `get_season_overview_dir`, `get_processed_path("teams.csv")` | Club-aware deploy-safe writer with `--dry-run`; legacy output only via `--legacy-output` | Medium |
| `scripts/build_player_profile_insight_exports.py` | `data/processed/match_centre` via Season Overview helper | `clubs/<club_id>/data/processed/player_profile` by default | `--club`, `get_processed_dir`, shared match-centre helper | Club-aware deploy-safe writer with `--dry-run`; legacy output only via `--legacy-output` | Medium |
| `scripts/build_hall_of_fame_detail_exports.py` | `data/processed/match_centre`, club `players.csv`, legacy `data/player_aliases.csv` fallback | `clubs/<club_id>/data/processed/hall_of_fame` by default | `--club`, `get_hall_of_fame_dir`, `get_processed_match_centre_dir`, `get_processed_path`, `get_mapping_path` | Club-aware deploy-safe writer with `--dry-run`; legacy output only via `--legacy-output` | Medium |
| `scripts/build_premiership_hall_of_fame_exports.py` | `data/processed/experimental/premiership_exploration`, `data/processed/match_centre/all_available` | `clubs/<club_id>/data/processed/hall_of_fame` by default | `--club`, `get_experimental_dir`, `get_processed_match_centre_dir`, `get_hall_of_fame_dir` | Club-aware deploy-safe writer with `--dry-run`; legacy output only via `--legacy-output` | Medium |
| `scripts/build_match_centre_milestones.py` | `data/processed/match_centre`, club `players.csv`, legacy `data/player_aliases.csv` fallback | `data/processed/match_centre` | `--club`, `get_processed_match_centre_dir`, `get_processed_path`, `get_mapping_path` | Add reporting/dry-run only; output remains ignored/generated match-centre folder | Medium |
| `scripts/refresh_data.py` | PlayCricket API, legacy raw/processed aggregate paths, legacy match-centre refresh | Legacy aggregate outputs plus club-aware deploy-safe output builders | `--club`, active club PlayCricket ID, deploy-safe builder commands | Added club-aware dry-run plan and passed `--club` to deploy-safe builders; aggregate write migration completed in Phase 5 | High |
| `scripts/refresh_match_centre_data.py` | PlayCricket match-centre API, command-line season/team IDs | `data/raw/match_centre`, `data/processed/match_centre` | None in Phase 4 | Remain legacy ignored raw/generated workflow | High |
| `scripts/backfill_match_centre_available.py` | Existing local match-centre raw files and legacy teams | `data/raw/match_centre/all_available`, `data/processed/match_centre/all_available` | None in Phase 4 | Remain legacy ignored raw/generated workflow | High |
| `src/data/playcricket_ingestion.py` | PlayCricket public API and legacy raw/processed paths | Legacy aggregate raw/processed outputs | Runtime reads are already club-aware; write helpers accept injected paths in Phase 5 | Keep default legacy-compatible; `scripts/refresh_data.py` injects club-specific processed output paths | High |

## Phase 5 Aggregate Refresh Script Audit

| Script / module | Current inputs | Current outputs after Phase 5 | Config usage | Still legacy/global | Risk |
| --- | --- | --- | --- | --- | --- |
| `scripts/refresh_data.py` | PlayCricket public aggregate endpoints, club config, legacy raw/cache folders | `clubs/<club_id>/data/processed/*.csv` by default; `data/processed/*.csv` only with `--legacy-output` | `--club`, `club.playcricket_club_id`, `get_processed_dir`, `get_data_root` | raw JSON backups, cache, timestamped backups, match-centre current-scope refresh roots | High |
| `src/data/playcricket_ingestion.py` | PlayCricket public API, optional injected paths | Injected processed/raw/cache/exports/metadata paths when supplied; legacy paths when omitted | Path injection from caller | default raw/cache/exports constants remain legacy for backwards compatibility | High |
| `src/utils/player_identity.py` | Club processed aggregate CSVs plus global alias/merge files | Canonicalized aggregate CSVs in selected processed directory | `scripts/refresh_data.py` passes selected processed dir | `data/player_aliases.csv`, `data/manual_player_merges.csv`, identity/audit CSVs stay global | High |
| `scripts/refresh_match_centre_data.py` | PlayCricket match-centre API and explicit season/team IDs | legacy ignored `data/raw/match_centre` and `data/processed/match_centre` | Phase 6 adds `--club`, config PlayCricket ID reporting, and dry-run with no required scope args | full match-centre raw/generated folders | High |
| `scripts/backfill_match_centre_available.py` | local club `teams.csv`, `seasons.csv`, `players.csv`, global aliases, PlayCricket match-centre endpoints | legacy ignored all-available match-centre folders | Phase 6 adds `--club`, club-aware input paths, config PlayCricket ID reporting, and no-network dry-run | full match-centre raw/generated folders | High |

## Phase 6 Match-Centre Workflow Audit

| Script / module | Inputs | Outputs | Config usage after Phase 6 | Dry-run behaviour | Risk / notes |
| --- | --- | --- | --- | --- | --- |
| `scripts/refresh_match_centre_data.py` | explicit season/team/scope args, club `teams.csv`, club `players.csv`, global `data/player_aliases.csv`, PlayCricket match-centre endpoints | non-dry-run still writes ignored `data/raw/match_centre/<scope>` and `data/processed/match_centre/<scope>` | `--club`, active club name, `club.playcricket_club_id`, `get_raw_match_centre_dir`, `get_processed_match_centre_dir`, `get_processed_path`, `get_mapping_path` | no network, no writes, scope args optional, prints planned inputs/outputs | High; generated roots remain legacy, but identity audit now emits `is_club_player` with `is_fvcc_player` compatibility |
| `scripts/backfill_match_centre_available.py` | club `teams.csv`, club `seasons.csv`, club `players.csv`, global aliases, PlayCricket match-centre endpoints | non-dry-run still writes ignored `data/raw/match_centre/all_available` and `data/processed/match_centre/all_available` | `--club`, active club name, `club.playcricket_club_id`, club-aware aggregate input paths | no network, no writes, prints scoped season/team counts and planned legacy outputs | High; all-available scope is still global/legacy, but ownership summaries prefer neutral fields with legacy fallback |
| `scripts/build_match_centre_milestones.py` | configured legacy match-centre processed root, club `players.csv`, global aliases | configured legacy match-centre processed root | `--club`, active club name, `club.playcricket_club_id`, club-aware players/alias paths | no network, no writes, reports generated milestone output paths | Medium; output remains generated input for deploy-safe Hall of Fame summaries |
| `scripts/refresh_club_outputs.py` | existing local deploy-safe builder inputs | deploy-safe summaries under `clubs/<club_id>/data/processed/...` | `--club`, existing deploy-safe path helpers | no network, no writes, now prints the full future weekly sequence including match-centre refresh/backfill | Low |
| `src/data/match_centre_fetcher.py` | public match-centre endpoints and local cache path chosen by caller | raw JSON files chosen by caller | caller supplies paths; no direct club config | not a CLI | Medium; safe if callers remain conservative |
| `src/data/match_centre_parser.py` | raw scorecard/balls/officials payloads | parsed data frames | no direct club config | not a CLI | Medium; schema parsing is shared and ownership compatibility is handled downstream |
| `src/data/ball_by_ball_parser.py` | parsed delivery rows | delivery-derived metrics | caller can pass `playcricket_club_id`; default remains FVCC for backwards sample use | not a CLI | Medium; now emits `club_team_id`/`club_team_name` plus legacy `fvcc_*` columns for transition |

## Phase 6.5 Match-Centre Ownership Audit

| Field / function | Current behaviour before Phase 6.5 | Neutral replacement | Fixed now / deferred | Risk |
| --- | --- | --- | --- | --- |
| `FVCC_ORGANISATION_ID` in `src/data/ball_by_ball_parser.py` | Hard-coded FVCC PlayCricket organisation/club identifier used to locate the selected club side in sample payloads | `DEFAULT_PLAYCRICKET_CLUB_ID` plus `playcricket_club_id` parameter | Fixed now; default remains FVCC for old sample calls | Medium |
| `fvcc_team_id`, `fvcc_team_name` | Generated match ownership columns named after FVCC | `club_team_id`, `club_team_name` | Fixed now in parser/helper paths; legacy columns still emitted/preserved for existing downstream CSV schemas | High |
| `is_fvcc_player` | Identity audit marked aggregate player matches with an FVCC-specific name | `is_club_player` | Fixed now in refresh/backfill identity audit builders; legacy column still emitted for compatibility | High |
| `is_fvcc_team_name(...)` | Name-token fallback looked for Fiji Victorian teams | `is_selected_club_team_name(...)` | Fixed now in shared helper; old wrapper remains for transitional callers | Medium |
| `src/data/match_centre_ownership.py` | No shared compatibility shim existed | `ensure_club_ownership_columns(...)`, `add_club_match_ownership(...)`, `club_team_mask(...)` | Added now; readers prefer neutral columns and backfill from old FVCC columns | Low |
| `scripts/check_match_centre_ownership.py` | No read-only ownership diagnostic existed | Reports old/new ownership columns, fallback mapping, club team IDs/names, and identity ownership counts | Added now | Low |
| Deploy-safe HOF/Season Overview/Profile exporters | Mixed old ownership naming in local match-centre inputs | Prefer neutral ownership columns internally, preserve legacy deploy-safe schemas where needed | Fixed now without changing deploy-safe CSV hashes | Medium |
| Hidden experimental analytics | Used `fvcc_team_id` and `is_fvcc_player` in advanced/player DNA/scorebook lab helpers | Prefer neutral columns with fallback | Fixed now for low-risk reads; visible experimental UI remains hidden | Medium |
| Production UI/deploy-safe schema names | Some visible/runtime code still expects legacy `fvcc_*` column names in existing CSVs | Future schema cleanup once new field names are proven | Deferred to avoid visible or hash changes | Medium |
| Raw/generated match-centre folder layout | `data/raw/match_centre/...`, `data/processed/match_centre/...` are global/legacy | Candidate future `data/raw/match_centre/<club_id>/` and `data/processed/match_centre/<club_id>/` | Deferred to Phase 7 | High |

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
