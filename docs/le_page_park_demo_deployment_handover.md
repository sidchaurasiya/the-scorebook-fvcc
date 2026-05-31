# Le Page Park Demo Deployment Handover

## Overview
- Club: Le Page Park Cricket Club
- Branch: `demo/le-page-park-2022-23`
- Club ID: `le-page-park`
- PlayCricket club ID: `92e3c14d-8ad8-eb11-a7ad-2818780da0cc`
- Recommended season scope: `Summer 2022/23`

## Required Environment
- `CLUB_ID=le-page-park`
- `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false`
- `GA4_MEASUREMENT_ID=<existing shared measurement id if used>`

## Local Run Command
```bash
CLUB_ID=le-page-park SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false ./.venv-app/bin/streamlit run app.py --server.port 8510
```

## Smoke Checklist
- Open Hall of Fame
- Open Season Overview
- Open Season by Round
- Open Milestone
- Open Player Profile
- Confirm Le Page Park branding and navy/gold theme
- Confirm no FVCC text/data leakage
- Confirm player and season links work
- Confirm scorecard links are present and URL-shaped correctly
- Confirm premierships show verified captains where local scorecard evidence exists

## What Not To Commit
- `data/raw/match_centre/`
- `data/processed/match_centre/`
- `data/processed/experimental/`
- `data/cache/`
- `data/backups/`
- raw PlayCricket JSON
- debug CSVs
- generated review packs

## Rollback Plan
- Stop the preview deployment if anything looks wrong.
- Re-run the local smoke against the branch before sharing a new link.
- Do not merge to `main` until the preview is approved.

## Caveats
- 4 manual duplicate review candidates remain.
- No safe auto-merges were applied because the duplicate candidates overlap in season.
- External PlayCricket scorecard pages were not auto-opened during validation.

