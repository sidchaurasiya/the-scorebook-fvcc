# Southside East Caulfield Private Preview UAT Report

Date: 2026-05-27
Branch: `onboarding/multi-club-positive-responses`
Tested commit base: `1bed61a Add Southside private deployment checklist`
Target club: `southside-east-caulfield`

## Status

**Go with caveats for a private deployment test.**

Southside East Caulfield now passes the targeted private-preview UAT across the main app pages. The app uses Southside branding, has working internal player and season routes, shows verified premiership wins from local Grand Final scorecards, and no longer shows the Season Overview widget warning seen during UAT.

## Fixes Verified

| Issue | Root cause | Fix | Result |
|---|---|---|---|
| App still looked FVCC-purple | Several shared CSS selectors and chart calls still used hard-coded purple values after the first branding pass. | Added active club CSS variables for links/highlights and expanded overrides for tabs, links, controls, progress bars, record cards, and chart colours. | Southside renders with blue/red accents; FVCC still keeps purple defaults. |
| HOF player/season links did not route reliably | Internal URLs were bare query strings in several link helpers. | Centralized app-relative URLs as `./?page=...`, including player, season, sidebar, and profile-section links. | HOF player links, season links, and app nav resolve under active club context. |
| Premierships empty despite Southside wins | Premiership exporter only consumed FVCC exploration candidate files and had no club-generic local fallback. | Added conservative local detection from completed Grand Final match-centre rows where result text names the active club team as winner. | 5 verified Southside premiership wins and 48 player premiership rows generated from local scorecards. |
| Sajan Win % inconsistency risk | HOF surfaces can diverge when fallback or stale win-rate outputs are used. | Rebuilt deploy-safe outputs and ensured fallback win-rate identity mapping uses the active club. | Best Win % shows Sajan Patel at 61.4%, 35 wins from 57 result matches, matching `player_win_rates.csv`. |
| Season Overview warning | Selectbox state was set through Session State while also passing a default index. | Initialized the selected season in session state and used `index=None`. | No visible Session State warning on linked Season Overview routes. |

## Page UAT

| Page | Result | Notes |
|---|---|---|
| Hall of Fame | Pass | Premierships, leaders, record holders, greatest seasons, scorecard links, player links, and season links render with Southside colours. No FVCC text, traceback, `NaN`, `None`, or visible raw IDs. |
| Detailed Records | Pass by source and page smoke | `player_win_rates.csv` has 420 rows, `player_scorecard_milestones.csv` has 406 rows. Key players show plausible Win % and 30s from scorecards. |
| Season Overview | Pass | Summer 2025/26 route loads, Season by Round and Detailed Stats render, result scorecard links are present, and the previous widget warning is gone. |
| Milestone | Pass | Upcoming, Achieved, and Exclusive Club sections render. Player links are present and the page keeps Southside context. |
| Player Profile | Pass | Career Overview, Recent Form, Career Highlights, Player DNA, Batting Position, Dismissal Fingerprint, Player vs Peers, Season Trends, Career Breakdown, and Milestone Watch render for data-rich players. Low-data players show cleanly reduced sections. |
| Mobile/narrow | Pass | 390px viewport smoke showed no horizontal document overflow on HOF or Puneet Bhardwaj's profile, and mobile nav remained readable. |
| GA4 | Pass by static inspection | `default_event_params()` includes `app_area=scorebook`, `club_id`, and `club_name`; events can add page, section, player, season, and team/grade context; no-op behavior remains if `GA4_MEASUREMENT_ID` is absent. |
| FVCC regression | Pass | FVCC HOF, Season Overview, Milestone, and Player Profile load on port 8502 with purple branding, premierships intact, and no traceback. |

## Data Checks

| Check | Result |
|---|---|
| Southside premiership wins | 5 verified completed Grand Final wins from local match-centre data |
| Player premiership records | 48 player rows inferred from winning-team scorecard participation |
| Captain data | Blank by design; no captain data was fabricated |
| Scorecard links | Present as PlayCricket match URLs with `?tab=scorecard`; external pages were not opened |
| BBB coverage | 195 matches / 74,758 ball events from existing local coverage; missing BBB remains empty or unavailable rather than fake `0.0` |
| Remaining manual duplicate groups | 14 groups remain, not applied |
| Opponent/ground mappings | Conservative starter mappings remain; visible labels are PlayCricket-derived |

## Key Player UAT

| Player | Category | Result |
|---|---|---|
| Puneet Bhardwaj | Top run scorer / safe duplicate merge applied | Pass; profile loads, recent form and scorecard links present, 26 scorecard 30s, 52.7% win rate from 88/167 result matches |
| Denis Shaw | High-match veteran | Pass; profile loads with recent form, scorecard links, and career breakdown |
| Francis Bernard | Fielding-heavy all-round veteran | Pass; profile loads with full profile sections |
| Jatin Bhatia | Current top batter | Pass; profile loads, 37 scorecard 30s, premiership participation present |
| Jatin Dave | All-round/current batter | Pass; profile loads with full profile sections |
| Hiren Tandel | Keeper/fielding-heavy | Pass; profile loads, fielding-heavy checks clean |
| Rajiv Chandla | Top wicket taker | Pass; profile loads, 16 scorecard 30s and wicket context present |
| Sourav Taneja | Recent/current active player | Pass; profile loads with current/recent context |
| Gurinder Sodhi | Low-data player | Pass; profile loads cleanly with reduced advanced sections where data is unavailable |
| Ankit Patel | Remaining manual duplicate-risk player | Pass; selected profile loads cleanly; duplicate risk remains for manual review |

## Known Caveats

- Fourteen manual duplicate groups remain. They were not applied because they have same-season overlap or are only similar names.
- Premiership wins are verified from local completed Grand Final scorecards, but captain fields remain blank until verified.
- Player premiership participation is inferred from scorecard participation for the winning club team; this is good preview evidence but should be reviewed by the club.
- Opponent and ground mappings are still conservative starter mappings.
- External PlayCricket scorecard links were URL-shape checked in the app; external pages were not opened during automated UAT.
- Ball-by-ball coverage is partial by nature and remains verified-coverage-only.

## Local Commands

Southside:

```bash
CLUB_ID=southside-east-caulfield SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false ./.venv-app/bin/streamlit run app.py --server.port 8508
```

FVCC regression:

```bash
CLUB_ID=fvcc SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false ./.venv-app/bin/streamlit run app.py --server.port 8502
```

## Recommendation

Proceed with a private deployment test for Southside East Caulfield only. Share as a data-quality preview, ask reviewers to focus on player identity, premiership participation, opponent/ground labels, and any grade naming concerns before wider release.
