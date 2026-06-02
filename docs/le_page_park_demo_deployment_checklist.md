# Le Page Park Demo Deployment Checklist

## Purpose
Prepare the Le Page Park private demo for a controlled client preview using the demo branch `demo/le-page-park-2022-23`.

## Branch And Scope
- Branch: `demo/le-page-park-2022-23`
- Club: `Le Page Park Cricket Club`
- Club ID: `le-page-park`
- PlayCricket club ID: `92e3c14d-8ad8-eb11-a7ad-2818780da0cc`
- Demo-visible seasons: `Summer 2022/23` and `Summer 2025/26`
- Demo landing season: `Summer 2022/23`
- Demo player profile restriction: Steve McConchie only

## Required Environment
- `CLUB_ID=le-page-park`
- `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false`
- `GA4_MEASUREMENT_ID=<existing shared measurement id if used>`

## Local Validation Command
```bash
CLUB_ID=le-page-park SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false ./.venv-app/bin/streamlit run app.py --server.port 8510
```

## Deployment Checklist
- Open Hall of Fame and confirm the Le Page Park branding renders.
- Open Season Overview and confirm only the two approved seasons appear.
- Confirm the landing season is `Summer 2022/23`.
- Open Milestone and confirm the page loads cleanly.
- Open Player Profile and confirm Steve McConchie is the only selectable profile.
- Confirm Steve player links still route correctly.
- Confirm all non-Steve player links are plain text in the demo.
- Confirm no FVCC text or data leaks into the demo.
- Confirm scorecard links are present and URL-shaped correctly.
- Confirm premiership captions display only where local scorecard evidence exists.
- Confirm the mobile/narrow layout remains readable.

## Known Caveats
- The demo intentionally excludes winter seasons.
- Only Steve McConchie is selectable in Player Profile flows.
- Non-Steve player links are intentionally disabled/plain text.
- External PlayCricket scorecard pages were not auto-opened during validation.
- 3 manual duplicate review groups remain in the local review pack.

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
- Stop or disable the preview deployment if anything looks off.
- Re-run the local smoke checks before sharing a new link.
- Do not merge the branch to `main` until the client approves the demo.

## Post-Deployment Checks
- Re-open Hall of Fame after deployment.
- Re-open Season Overview after deployment.
- Re-open Player Profile after deployment.
- Verify GA4 Realtime receives events with the club context if tracking is enabled.
- Confirm experimental pages stay hidden.

## Recommendation
Le Page Park is ready for a private demo link on the approved two-season scope, with Steve McConchie as the only selectable player in the demo UI.
