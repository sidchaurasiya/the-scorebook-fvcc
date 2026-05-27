# Southside Private Deployment Checklist

Date: 2026-05-27
Target branch: `onboarding/multi-club-positive-responses`
Target club: `southside-east-caulfield`
Baseline commit: `9864950 Prepare Southside private preview review`

## Purpose

Prepare a private Streamlit deployment test for Southside East Caulfield Cricket Club using the current multi-club Scorebook app. This is a private preview and data-quality review, not a public launch or merge-to-main release.

## Required Streamlit Secrets / Environment

Set these for the private deployment:

| Key | Value / status |
|---|---|
| `CLUB_ID` | `southside-east-caulfield` |
| `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES` | `false` |
| `GA4_MEASUREMENT_ID` | Optional: use the existing shared GA4 measurement ID if available. Do not create a separate Southside ID for this test. |

Do not set `FVCC_SHOW_EXPERIMENTAL=1` for the private preview. The current app code keeps `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES = False`, and the deployment should keep experimental routes hidden.

No PlayHQ/PlayCricket fetch secrets are required for this deployment test because the app should run from committed processed files only. Do not run refresh, match-centre, or backfill jobs from the preview deployment.

Expected app URL: `<streamlit-private-preview-url-to-be-created>`

## Production Files

Verified present and tracked for Southside:

- `clubs/southside-east-caulfield/club_config.yaml`
- `clubs/southside-east-caulfield/manual_player_merges.csv`
- `clubs/southside-east-caulfield/player_aliases.csv`
- `clubs/southside-east-caulfield/team_grade_mappings.csv`
- `clubs/southside-east-caulfield/opponent_mappings.csv`
- `clubs/southside-east-caulfield/ground_mappings.csv`
- `clubs/southside-east-caulfield/data/processed/`
- `clubs/southside-east-caulfield/data/processed/hall_of_fame/`
- `clubs/southside-east-caulfield/data/processed/season_overview/`
- `clubs/southside-east-caulfield/data/processed/player_profile/`

Tracked Southside processed runtime files: 29.

Generated match-centre and review-pack folders are not tracked:

- `data/raw/match_centre/`: 0 tracked files
- `data/processed/match_centre/`: 0 tracked files
- `data/processed/experimental/`: 0 tracked files
- `data/cache/`: 0 tracked files

Note: the repository already contains two historical tracked files under `data/backups/`. They were not changed for this deployment-readiness pass and should not be staged or expanded during deployment work.

## Local Validation

Local production-style Southside smoke passed with:

```bash
CLUB_ID=southside-east-caulfield SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false ./.venv-app/bin/streamlit run app.py --server.port 8508
```

Checks passed:

- Hall of Fame loaded.
- Detailed Records loaded.
- Premierships showed the clean empty state.
- All-Time Leaders and Record Holders loaded.
- Season Overview loaded.
- Season by Round loaded.
- Milestone loaded.
- Player Profile loaded for Puneet Bhardwaj.
- Recent Form loaded.
- Player DNA and bowling phase sections loaded from available verified coverage.
- PlayCricket scorecard link hrefs were present and shaped correctly.
- No FVCC text/data appeared in Southside pages.
- No traceback, missing-file error, visible `NaN`, visible `None`, or raw GUID text was seen.
- Narrow viewport spot check loaded Hall of Fame without traceback.

FVCC regression smoke passed separately with:

```bash
CLUB_ID=fvcc SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false ./.venv-app/bin/streamlit run app.py --server.port 8502
```

FVCC Hall of Fame, Season Overview, and Player Profile loaded with FVCC branding and no traceback.

## Known Caveats

Carry these caveats into the private preview:

- 14 manual duplicate groups remain.
- Premiership wins are populated from 5 verified local completed Grand Final scorecards; captain fields remain blank until verified.
- Player premiership participation is inferred from winning-team scorecard participation and should be reviewed by the club.
- Opponent and ground mappings are conservative starter mappings.
- External PlayCricket scorecard links were URL-shape checked, not fully opened during this pass.
- Final human mobile/narrow visual review is recommended before sharing beyond the first private reviewer group.
- Ball-by-ball sections only cover verified ball-by-ball matches; they are not all-history complete.

## What Not To Commit

Do not stage or commit:

- `data/raw/match_centre/`
- `data/processed/match_centre/`
- `data/processed/experimental/`
- Review packs
- Raw PlayCricket JSON
- `data/cache/`
- `data/backups/`
- Debug CSVs
- Any FVCC data changes

## Rollback Plan

If the private preview misbehaves:

1. Disable or delete the private preview deployment.
2. If testing on a shared deployment, switch `CLUB_ID` back to `fvcc`.
3. Do not merge this branch to `main` until the preview is approved.
4. Do not run refresh, match-centre, or backfill as part of rollback.

## Post-Deployment Checks

After the private deployment is live:

1. Confirm the deployed app URL opens with Southside branding.
2. Confirm the sidebar shows `SECCC`, not FVCC.
3. Open Hall of Fame and verify the Southside premiership wins render with scorecard links and blank captain fields.
4. Open Detailed Records and spot-check Win % and 30s for top players.
5. Open Season Overview and Season by Round.
6. Open Milestone.
7. Open Player Profile and select/search Puneet Bhardwaj.
8. Confirm Recent Form and Player DNA/phase sections load or cleanly explain unavailable coverage.
9. Confirm scorecard links point to PlayCricket match URLs.
10. Confirm no traceback, `NaN`, `None`, raw GUIDs, or FVCC data/text appears.
11. Confirm GA4 receives club-aware events if `GA4_MEASUREMENT_ID` is configured.

## Deployment Readiness

Ready to push for a private deployment test after explicit approval. Do not merge to `main` and do not push until approved.
