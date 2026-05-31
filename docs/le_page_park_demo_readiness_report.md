# Le Page Park Demo Readiness Report

## Branch And Scope
- Branch: `demo/le-page-park-2022-23`
- Club: `Le Page Park Cricket Club`
- Official PlayCricket club ID: `92e3c14d-8ad8-eb11-a7ad-2818780da0cc`
- Season scope: `Summer 2022/23` only

## Data Summary
- Seasons: 1
- Teams: 22
- Players: 227
- Batting rows: 427
- Bowling rows: 427
- Fielding rows: 427
- Match-centre matches found: 248
- Scorecards fetched: 248
- BBB matches: 124
- BBB ball events: 46,140
- Fastest innings rows: 172
- Premiership wins: 4
- Player premiership rows: 39

## Club Setup
- Branding: Navy blue and gold
- Legacy fallback: disabled
- Winter seasons: excluded
- Season filter: `Summer 2022/23`
- Manual duplicate merges: none applied

## Duplicate Review
- Safe auto-merge candidates: 0
- Manual duplicate review candidates: 4
- Outcome: exact-name duplicates existed, but season overlap blocked safe auto-merge

## Deployment-Safe Output Check
- Hall of Fame outputs rebuilt
- Season Overview outputs rebuilt
- Player Profile outputs rebuilt
- Premiership outputs rebuilt
- Review pack generated under ignored `data/processed/experimental/le-page-park/review_pack/`

## Smoke Results
- Hall of Fame: passed
- Season Overview: passed
- Season by Round: passed
- Player Profile: passed
- Mobile HOF smoke: passed
- Player link routing: passed
- Season link routing: passed
- Scorecard link URLs: passed
- Premiership captains: verified where local scorecard evidence exists

## Known Caveats
- Manual duplicate review is still required for 4 candidate pairs.
- Scorecard links were URL-shaped and smoke-verified locally; external PlayCricket pages were not opened automatically.
- No safe auto-merges were applied because the duplicate candidates overlapped in season.

## Recommendation
Le Page Park is ready for a private preview demo on the 2022/23 season scope.

