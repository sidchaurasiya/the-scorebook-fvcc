# Multi-Club Scalability Plan

Last updated: 2026-05-21

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

- Add central path helpers for processed, Hall of Fame, Season Overview, Player Profile, identity, and export paths.
- Keep the default helpers pointing at the existing FVCC `data/...` layout.
- Replace scattered path constants gradually by page/export area.

## Phase 3: Move FVCC Data Under `clubs/fvcc/data`

- Move FVCC data into a club-owned folder only after path helpers are proven.
- Keep a compatibility shim for old `data/...` paths during transition.
- Verify all stable pages and deploy-safe summaries before removing the shim.

## Phase 4: Create `refresh_club.py --club fvcc`

- Centralize club IDs, data paths, refresh outputs, and deploy-safe summary rebuilds.
- Avoid direct script-level FVCC defaults once the new command exists.
- Preserve no-network app runtime behaviour.

## Phase 5: Create `onboard_club.py`

- Generate a starter config, data folders, mapping templates, and review checklist.
- Collect PlayCricket club ID, club/team identifiers, grade order, home grounds, aliases, and display branding.

## Phase 6: Generate Club Review Pack

- Produce QA reports for player identity, team/grade labels, opponent names, ground names, missing scorecards, ball-by-ball coverage, and deploy-safe summary freshness.
- Require review before a new club is considered production-ready.

## Phase 7: Add Per-Club Deploy-Safe Summaries

- Build Hall of Fame, Season Overview, Player Profile, and milestone summaries under each club data folder.
- Keep raw and experimental outputs out of deployable paths.

## Phase 8: Runtime / Deployment Strategy

- Decide between one deployment per club, one runtime selected by `CLUB_ID`, or a multi-club selector.
- Keep routing, GA4, and page availability consistent with the chosen deployment model.
