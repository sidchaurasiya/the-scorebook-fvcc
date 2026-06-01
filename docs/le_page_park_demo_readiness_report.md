# Le Page Park Demo Readiness Report

## Branch And Scope
- Branch: `demo/le-page-park-2022-23`
- Club: `Le Page Park Cricket Club`
- Official PlayCricket club ID: `92e3c14d-8ad8-eb11-a7ad-2818780da0cc`
- Season scope: `Summer 2022/23` and `Summer 2025/26`

## Data Summary
- Seasons: 2
- Teams: 47
- Players: 456
- Batting rows: 834
- Bowling rows: 834
- Fielding rows: 834
- Match-centre matches found: 572
- Scorecards fetched: 545
- BBB matches: 400
- BBB ball events: 132,994
- Fastest innings rows: 443
- Premiership wins: 6
- Player premiership rows: 54

## Club Setup
- Branding: Navy blue and gold
- Legacy fallback: disabled
- Winter seasons: excluded
- Season filter: `Summer 2022/23`, `Summer 2025/26`
- Manual duplicate merges: 112 strict-safe rows applied

## Duplicate Review
- Safe auto-merge candidates: 0 after applying the strict-safe set
- Manual duplicate review candidates: 6 rows across 3 groups
- Outcome: 112 strict-safe merges were applied, and the remaining manual candidates still require human review because of season overlap

## Deployment-Safe Output Check
- Hall of Fame outputs rebuilt
- Season Overview outputs rebuilt
- Player Profile outputs rebuilt
- Premiership outputs rebuilt
- Review pack generated under ignored `data/processed/experimental/le-page-park/review_pack/`
- Outputs rebuilt after the two-season refresh and safe merge application

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
- Manual duplicate review is still required for 3 remaining groups.
- Scorecard links were URL-shaped and smoke-verified locally; external PlayCricket pages were not opened automatically.
- The demo intentionally keeps winter seasons out of scope.
- External PlayCricket pages were not opened automatically during validation.

## Recommendation
Le Page Park is ready for a private preview demo on the two-season scope of `Summer 2022/23` and `Summer 2025/26`.
