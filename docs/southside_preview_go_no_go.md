# Southside East Caulfield Private Preview Go/No-Go

Date: 2026-05-27
Branch: `onboarding/multi-club-positive-responses`
Baseline commit: `1bed61a Add Southside private deployment checklist`

## Preview Status

**Go with caveats.**

Southside East Caulfield is suitable for a first private preview deployment test. The app loads the current main experience with Southside club branding, club-specific data, fixed Hall of Fame win-rate and 30s metrics, scorecard-backed recent form, and verified local Grand Final premiership wins.

This should be shared as a private data-quality preview, not a public launch. A small reviewer group should focus on player identity, opponent/ground naming, and premiership evidence before wider release.

## Exact Local Command

```bash
CLUB_ID=southside-east-caulfield SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false ./.venv-app/bin/streamlit run app.py --server.port 8508
```

## Top 10 Checks

1. Hall of Fame loaded with Southside East Caulfield content and no FVCC data/text leakage.
2. Detailed Records source files are populated: `player_win_rates.csv` has 420 rows and `player_scorecard_milestones.csv` has 406 rows.
3. Win % is plausible after the multi-club fix: Puneet Bhardwaj shows 88 wins from 167 result matches, 52.7%.
4. Scorecard 30s are plausible after applying Southside-safe duplicate merges: Puneet Bhardwaj has 26 scorecard innings from 30 to 49.
5. Premierships render with 5 verified Grand Final wins and scorecard links from existing local match-centre data; captain fields remain blank until verified.
6. All-Time Leaders, Iconic Performances, Fastest Innings, Record Holders, and Detailed Records rendered without traceback, `NaN`, `None`, visible raw GUIDs, or broken layout in the desktop smoke.
7. Season Overview and Season by Round loaded using Southside scorecard data, with 893 season-by-round scorecard rows available.
8. Milestone loaded after Streamlit completed the heavier page build, including upcoming milestones and Hall of Fame watch cards.
9. Player Profile loaded for Puneet Bhardwaj, including Career Overview, Recent Form, Career Highlights, Player DNA, and bowling phase sections.
10. FVCC regression smoke passed separately on port 8502: Hall of Fame, Season Overview, and Player Profile loaded with FVCC branding and no traceback.

## Data Coverage

| Area | Status |
|---|---|
| Completed scorecards | 893 completed scorecards in the local match-centre backfill summary |
| Ball-by-ball coverage | 195 matches with ball-by-ball, 74,758 ball events |
| Fastest innings | Available from verified ball-by-ball-derived milestones: 415 Hall of Fame fastest milestone rows |
| Recent form | 7,045 batting rows and 4,683 bowling rows |
| Scorecard links | 11,751 Hall of Fame scorecard record links; visible link hrefs use PlayCricket match URLs with `?tab=scorecard` |
| Premierships | 5 verified completed Grand Final wins; 48 player-premiership rows inferred from winning-team scorecard participation |
| Remaining manual duplicate groups | 14 manual duplicate groups remain in the Southside review pack |

## Link And Tracking Checks

- HOF player links are present and route through the active Southside app context. The Puneet Bhardwaj profile route resolved to the correct player.
- Season Overview links are present and retain active club context.
- Scorecard links were inspected by URL shape only, without opening external PlayCricket pages, to respect the no-fetch rule.
- No raw GUIDs or internal IDs were visible in page text during smoke. Some internal route hrefs still use generated player ids for unmapped historical players, but visible labels are clean.
- GA4 remains club-aware by static inspection: `default_event_params()` includes `app_area=scorebook`, `club_id`, and `club_name`, and analytics remains a no-op when `GA4_MEASUREMENT_ID` is absent.

## Known Caveats

- Fourteen manual duplicate groups remain. None were applied in this pass.
- Premiership captain fields remain blank because no verified captain data was present locally.
- Player premiership participation is inferred from scorecard participation for the winning club team and should be reviewed by the club.
- Opponent and ground mappings are still conservative starter mappings, so some labels may read exactly as PlayCricket supplied them.
- External PlayCricket scorecard pages were not opened during smoke; only app-rendered link targets were inspected.
- Basic desktop and scroll smoke passed. A final human mobile/narrow visual review is still recommended before sharing beyond a small private group.
- Not every historical match has ball-by-ball data. Ball-by-ball sections should be treated as verified-coverage-only, not all-history complete.

## Suggested Club Wording

We have prepared a private preview of The Scorebook for Southside East Caulfield Cricket Club. It includes Hall of Fame records, verified Grand Final premiership wins, season views, player profiles, recent form, and scorecard-linked highlights from verified PlayCricket data. A few areas, including player identity review and some historical opponent and ground clean-up, are still being reviewed, so please treat this as a private data-quality preview rather than a public launch.

## Recommended Next Action

Proceed with a private deployment test for Southside East Caulfield only. Share the link with a small reviewer group, ask them to verify player identity and historical labels, then review the remaining 14 duplicate groups and any opponent/ground naming feedback before a broader client preview.
