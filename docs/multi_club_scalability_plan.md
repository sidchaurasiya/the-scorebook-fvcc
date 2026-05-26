# Multi-Club Scalability Plan

Last updated: 2026-05-22

The long-term direction is one shared Scorebook codebase that can serve many cricket clubs, with each club carrying its own config, mappings, data folders, deploy-safe summaries, refresh workflow, and QA report.

## Phase 0: Audit Hard-Coded Assumptions

- Catalogue FVCC-specific app text, data paths, PlayCricket IDs, grade ordering, team/club filters, identity mappings, opponent normalization, ground normalization, and refresh defaults.
- Classify each item as config now, config later, or global shared logic.

## Phase 1: Add Club Config Foundation

- Add `clubs/fvcc/club_config.yaml` and a future-club template.
- Add `src/config/club_config.py` with FVCC as the default active club.
- Wire only low-risk display identity/contact values through config.
- Keep data files in existing `data/...` paths.

## Phase 2: Refactor Data Paths To Club-Aware Helpers

- Add central path helpers for processed, Hall of Fame, Season Overview, Player Profile, match-centre, experimental, and root mapping paths.
- Keep the default helpers pointing at the existing FVCC `data/...` layout.
- Replace low-risk runtime loaders first: aggregate processed reads, Hall of Fame deploy-safe files, Season Overview deploy-safe files, Player Profile processed summaries, and match-centre read roots.
- Leave refresh/backfill scripts, data-generation scripts, player identity generation, and normalization mappings on legacy paths until later phases.

## Phase 2.5: Validate Active Club Configuration

- Validate `scripts/check_club_config.py` with no `CLUB_ID`, with `CLUB_ID=fvcc`, and with an invalid club ID.
- Confirm the production-style app runs with `CLUB_ID=fvcc` and still loads Hall of Fame, Season Overview, Milestone, and Player Profile without exposing experimental pages.
- Keep FVCC data in the legacy `data/...` layout; no data files move in this phase.

## Phase 3: Move FVCC Data Under `clubs/fvcc/data`

- Copy FVCC production-safe processed CSVs into `clubs/fvcc/data/processed/...`.
- Prefer club-specific runtime files, with legacy `data/...` fallback for incomplete migration.
- Keep raw match-centre, experimental data, mapping files, and refresh/write workflows in legacy locations until Phase 4+.

## Phase 4: Create `refresh_club.py --club fvcc`

- Centralize club IDs, data paths, refresh outputs, and deploy-safe summary rebuilds.
- Avoid direct script-level FVCC defaults once the new command exists.
- Preserve no-network app runtime behaviour.
- Make Hall of Fame, Season Overview, Player Profile, and milestone export builders write to the active club data folder.
- Phase 4 first implementation uses `scripts/refresh_club_outputs.py --club fvcc --dry-run` as the safe deploy-summary wrapper.
- Deploy-safe builders now default to `clubs/<club_id>/data/processed/...`; legacy deploy-safe output is explicit via `--legacy-output`.
- Raw/full match-centre and experimental folders remain legacy ignored paths during this phase.
- `scripts/refresh_data.py --club fvcc --dry-run` reports the future workflow without network requests or writes.

## Phase 4.5: Validate Club-Aware Deploy-Safe Rebuild

- Ran `scripts/refresh_club_outputs.py --club fvcc` from existing local inputs only; no external data was fetched.
- Compared 19 club-specific deploy-safe CSVs before and after rebuild across Hall of Fame, Season Overview, and Player Profile.
- Row counts and SHA-256 hashes were identical for every file, so the current deploy-safe export process is deterministic for FVCC.
- No CSV changes were committed; only validation documentation was updated.

## Phase 5: Make Aggregate Refresh Club-Aware

- `scripts/refresh_data.py --club <club_id>` now resolves the active club config and uses `club.playcricket_club_id` instead of a script-level FVCC UUID.
- Aggregate processed CSV outputs default to `clubs/<club_id>/data/processed/`.
- `--dry-run` makes no network requests and no writes while showing the PlayCricket club ID, processed output directory, raw/cache/metadata paths, planned aggregate CSV outputs, and next deploy-safe rebuild command.
- `--legacy-output` remains available for explicit compatibility writes to legacy `data/processed`.
- Raw JSON backups, cache files, timestamped backups, root-level player identity mapping files, match-centre raw/generated folders, and experimental/intermediate data remain legacy/global for now.
- After aggregate refresh, run `scripts/refresh_club_outputs.py --club <club_id>` to rebuild deploy-safe summaries.

## Phase 6: Add Club-Aware Match-Centre Dry-Run Reporting

- `scripts/refresh_match_centre_data.py --club <club_id> --dry-run` now reports the active club, config PlayCricket ID, optional scope, legacy raw/generated match-centre paths, and confirms no network/no writes.
- `scripts/backfill_match_centre_available.py --club <club_id> --dry-run` now uses club-aware `teams.csv`, `seasons.csv`, and `players.csv` paths, keeps aliases global, reports scoped season/team counts, and confirms no network/no writes.
- `scripts/build_match_centre_milestones.py --club <club_id> --dry-run` reports the config PlayCricket ID and generated milestone output paths.
- Raw/full match-centre and experimental folders remain ignored legacy/global paths: `data/raw/match_centre`, `data/processed/match_centre`, and `data/processed/experimental`.
- Deploy-safe summaries remain the only production runtime dependency and continue to be built into `clubs/<club_id>/data/processed/...` with `scripts/refresh_club_outputs.py --club <club_id>`.
- Club-scoped raw/generated paths such as `data/raw/match_centre/<club_id>` and `data/processed/match_centre/<club_id>` are later-phase candidates, not part of Phase 6.

## Phase 6.5: Generalize Match-Centre Club Ownership Fields

- Match-centre parser/exporter paths now prefer neutral ownership fields: `club_team_id`, `club_team_name`, and `is_club_player`.
- Existing FVCC generated files remain compatible because readers fall back from `fvcc_team_id`, `fvcc_team_name`, and `is_fvcc_player`.
- `src/data/match_centre_ownership.py` centralizes ownership fallback and selected-club team matching.
- `scripts/check_match_centre_ownership.py --club <club_id>` provides a read-only diagnostic for local processed match-centre scopes.
- Deploy-safe FVCC outputs were rebuilt from existing local inputs and stayed identical, so no CSV schema or visible app behaviour changed.

## Shared UI Components

- The production app now has a reusable session-state folder-tab pattern for card-attached view switching.
- The first shared users are Season Overview `Season by Round`, Milestone main views, and Player Profile `Career Breakdown` dimensions.
- The component is club-neutral: no FVCC labels, data paths, or team assumptions are hard-coded in the helper/style.
- Player Profile `Captain` breakdown support is also club-neutral. Deploy-safe summary exports may emit `dimension=Captain` only when a reliable club-side captain field is present; otherwise the app shows a clean empty state instead of falling back to another club's data.
- Remaining later work: club-scoped raw/generated match-centre folders, reviewed team ownership mappings for each new club, and optional cleanup of legacy `fvcc_*` deploy-safe column names after compatibility is proven.

## Phase 7: Create `onboard_club.py`

- Generate a starter config, data folders, mapping templates, and review checklist.
- Collect PlayCricket club ID, club/team identifiers, grade order, home grounds, aliases, and display branding.

## Phase 8: Generate Club Review Pack

- Produce QA reports for player identity, team/grade labels, opponent names, ground names, missing scorecards, ball-by-ball coverage, and deploy-safe summary freshness.
- Require review before a new club is considered production-ready.
- Duplicate-player review includes a conservative safe auto-merge proposal only. `normalize_player_name_for_strict_merge()` normalizes case, spacing, accents, and punctuation/special characters without reordering names, dropping middle names, or fuzzy matching.
- A safe auto-merge candidate requires exact strict-normalized names, no season overlap across batting/bowling/fielding rows, and no match overlap where match IDs exist. Punctuation-only differences such as `D'Mello`/`Dmello` can qualify only when those overlap checks pass.
- Similar names, reordered names, initials/name expansion differences, and any same-season duplicate remain manual review only.
- Review-pack outputs `safe_auto_merge_candidates.csv` and `manual_duplicate_review_candidates.csv` stay under ignored `data/processed/experimental/<club_id>/review_pack/` paths and do not mutate club mappings.

## Phase 9: Add Per-Club Deploy-Safe Summaries

- Build Hall of Fame, Season Overview, Player Profile, and milestone summaries under each club data folder.
- Keep raw and experimental outputs out of deployable paths.

## Phase 10: Runtime / Deployment Strategy

- Decide between one deployment per club, one runtime selected by `CLUB_ID`, or a multi-club selector.
- Keep routing, GA4, and page availability consistent with the chosen deployment model.

## Phase 11: Positive-Response Pilot Club Onboarding

- Added aggregate-ready club setups for Reynella, Ashwood, Glen Waverley Hawks, Plenty, Georges River District, and Southside East Caulfield.
- Glen Waverley Hawks reused the existing `clubs/glen-waverley-hawks/` folder and was updated in place rather than duplicated.
- The approved Georges River folder is `clubs/georges-river-district/`; the official PlayCricket page identifies the club as Georges River Cricket Club.
- Every new non-FVCC club uses `allow_legacy_fallback: false`, `mapping_dir: clubs/<club_id>`, and runtime processed output paths under `clubs/<club_id>/data/processed/`.
- Starter mapping files were created with headers only: `player_aliases.csv`, `manual_player_merges.csv`, `opponent_mappings.csv`, `ground_mappings.csv`, and `team_grade_mappings.csv`.
- Aggregate refreshes completed for all six clubs. Match-centre refresh/backfill was not run and remains pending explicit per-club approval.
- Review packs were generated under ignored paths: `data/processed/experimental/<club_id>/review_pack/`. They are QA artifacts and should not be committed unless explicitly approved.
- Safe duplicate merge review files were added to those review packs. They are proposals only; no non-FVCC club uses FVCC mappings, and no `manual_player_merges.csv` files are changed unless an explicit future apply step is approved.
- The normal production app smoke-passed for Hall of Fame, Season Overview, Milestone, and Player Profile across all six clubs. Experimental match-centre pages remain hidden behind `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES = False`.
- GA4 remains shared by default through `GA4_MEASUREMENT_ID`; events are enriched with `app_area=scorebook`, `club_id`, `club_name`, page context, and relevant public player/season/team labels.

| club_id | Official PlayCricket name | PlayCricket club ID | Seasons | Players | Batting rows | Bowling rows | Fielding rows | Latest season |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `reynella` | Reynella Cricket Club | `f2d283dc-87d8-eb11-a7ad-2818780da0cc` | 20 | 1075 | 5297 | 5297 | 5297 | Summer 2025/26 |
| `ashwood` | Ashwood Cricket Club | `71d83cbe-87d8-eb11-a7ad-2818780da0cc` | 68 | 1201 | 4735 | 4735 | 4735 | Summer 2025/26 |
| `glen-waverley-hawks` | Glen Waverley Hawks Cricket Club | `50f7f1e3-86d8-eb11-a7ad-2818780da0cc` | 36 | 1288 | 5669 | 5669 | 5669 | Summer 2026/27 |
| `plenty` | Plenty Cricket Club | `1638cd53-8ad8-eb11-a7ad-2818780da0cc` | 28 | 960 | 4495 | 4495 | 4495 | Summer 2025/26 |
| `georges-river-district` | Georges River Cricket Club | `a115d93f-87d8-eb11-a7ad-2818780da0cc` | 71 | 1650 | 7789 | 7789 | 7789 | Summer 2025/26 |
| `southside-east-caulfield` | Southside East Caulfield Cricket Club | `65e9ec99-87d8-eb11-a7ad-2818780da0cc` | 47 | 463 | 1819 | 1819 | 1819 | Winter 2026 |
