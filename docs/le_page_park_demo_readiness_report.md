# Le Page Park Demo Readiness Report

## Branch And Scope
- Branch: `demo/le-page-park-2022-23`
- Club: `Le Page Park Cricket Club`
- Official PlayCricket club ID: `92e3c14d-8ad8-eb11-a7ad-2818780da0cc`
- Season scope: `Summer 2022/23` and `Summer 2025/26`
- Demo default season: `Summer 2022/23`

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
- Default landing season: `Summer 2022/23`
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

## Fastest 100s Audit
- Club-owned 100+ innings across `Summer 2022/23` and `Summer 2025/26`: 8
- Those with verified ball-by-ball progression: 3
- Those included in deploy-safe Fastest 100s: 2
- Those excluded: 6
- Why they were excluded:
  - 5 innings are scorecard-only and do not have verified BBB coverage, so the balls-to-100 timing cannot be claimed.
  - 1 innings (Steve McConchie, 175) has BBB coverage but the per-delivery total does not reconcile with the scorecard total, so it remains excluded for accuracy.
- Conclusion: the current Fastest 100s output is intentionally conservative and should be presented that way in the demo.

## Recommendation
Le Page Park is ready for a private preview demo on the two-season scope of `Summer 2022/23` and `Summer 2025/26`.
