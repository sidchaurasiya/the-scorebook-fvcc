# The Scorebook / FVCC App Wireframing Context

Last updated: 2026-05-13

This document is a detailed product, design, data, and technical context pack for wireframing The Scorebook / FVCC app with ChatGPT or another design partner. It complements `docs/project_handover.md` and records the current `main` branch shape after the hidden Season Overview v2, Hall of Fame v2, and Player Profile v2 preview pages were added.

Use this as the single brief when asking ChatGPT to design page flows, refine cards, propose dashboards, or identify gaps. The current code remains the final source of truth when this document and implementation disagree.

## 1. Product Overview

App name / working name:

- The Scorebook
- FVCC app

Purpose:

- Streamlit cricket analytics app for Fiji Victorian Cricket Club.
- Uses PlayCricket Australia public data, local processed CSVs, and reviewed match-centre/ball-by-ball summaries.
- Turns club scorecards and aggregate cricket stats into records, player profiles, season stories, milestones, and decision-friendly analytics.

Primary audience:

- FVCC players
- FVCC club administrators
- supporters/family
- selection, awards, and social-media contributors
- future users reviewing historical club records

Main product promise:

- Make club history and current-season performance feel premium, searchable, reliable, and exciting without losing cricket-stat accuracy.

Repository:

- `https://github.com/sidchaurasiya/the-scorebook-fvcc.git`

Local project path:

- `/Users/preetkaur/Documents/Codex/2026-04-24/you-are-an-expert-full-stack`

Local run command:

```bash
./.venv-app/bin/streamlit run app.py --server.port 8502
```

Experimental preview local run:

```bash
FVCC_SHOW_EXPERIMENTAL=1 ./.venv-app/bin/streamlit run app.py --server.port 8502
```

Local review URLs:

- Production pages: `http://localhost:8502/`
- Hidden Season Overview v2: `http://localhost:8502/?page=season-overview-v2`
- Hidden Hall of Fame v2: `http://localhost:8502/?page=hall-of-fame-v2`
- Hidden Player Profile v2: `http://localhost:8502/?page=player-profile-v2`

Deployment:

- Streamlit Cloud deploys from GitHub `main`.
- Push only after local review.
- Streamlit cache/server may need reboot after pushed data changes.

## Multi-Club Scalability Foundation

- The app is beginning a safe move from FVCC-specific implementation toward a repeatable club analytics product.
- FVCC remains the default active club and current visible app behaviour should stay unchanged.
- Active FVCC config: `clubs/fvcc/club_config.yaml`.
- Future-club template: `clubs/_template/club_config.yaml`.
- Active club selection uses `CLUB_ID` from the environment, then Streamlit secrets, then defaults to `fvcc`.
- Data still lives in existing `data/...` folders for this phase. Future phases will move data into club-specific folders after compatibility helpers are in place.
- The config foundation currently covers low-risk identity/contact/display values. Team/grade mappings, opponent/ground normalization, player aliases, refresh workflows, and deploy-safe data generation remain FVCC-specific until later phases.
- Phase 2 added club-aware path helpers and switched low-risk runtime loaders to use them. The configured FVCC paths still point at existing `data/...` folders; no data files have moved.
- Refresh scripts, backfill scripts, player identity generation, opponent normalization, and ground normalization remain FVCC-specific for now.
- Phase 2.5 validation confirms both no `CLUB_ID` and `CLUB_ID=fvcc` run against FVCC, while invalid club IDs return a clear checker error. Data still stays in legacy `data/...` paths until Phase 3.
- Architecture audit: `docs/multi_club_architecture_audit.md`.
- Roadmap: `docs/multi_club_scalability_plan.md`.

## 2. Navigation And Access Model

Current production navigation pages:

1. Hall of Fame
2. Season Overview
3. Milestone
4. Player Profile

## Current Player Profile Work In Progress

- Player Profile production refinements are in progress on `main`; do not push until Preet confirms the local review.
- The current production section is `Career Breakdown 🧭`; earlier `Career Overview` naming was reviewed, but the visible app section is now back to Career Breakdown.
- Player Profile now has `Career Breakdown 🧭`, which combines Season / Grade / Opponent / Ground / Home/Away breakdown views with Batting / Bowling / Fielding discipline views.
- Player Profile now has `Player DNA 🧬`, with Batting Position, Dismissal Fingerprint, and Bowling by Phase modules.
- Batting strike rate must always use verified ball-by-ball runs and verified ball-by-ball balls from the same covered innings only. Do not mix all-scorecard runs with ball-by-ball denominators.
- Season Standout profile tags must count unique standout seasons only, not multiple club/grade or batting/bowling awards in the same season.
- Premiership Winner and Premiership Winning Captain profile tags are being added from deploy-safe premiership records where evidence exists.
- Batting Position uses scorecard batting-order groups; Bowling by Phase uses verified ball-by-ball only and must filter by actual match type before applying phase buckets.
- Current UI issues being fixed: compact Batting Position rows, shared toggle styling for Career Breakdown and Bowling by Phase, Bowling by Phase table columns, dismissal benchmark marker reuse from Player vs Peers, compact/wrapped Career Breakdown tables, and no query-param navigation for in-page toggles.
- Keep Hall of Fame, Season Overview, Milestone, routing, GA4, and experimental page visibility unchanged while this work is in progress.
- Current Career Breakdown data rule: batting split averages use `Runs / Outs`, where `Outs = Innings - Not Outs`; explicit `Did Not Bat` rows must be excluded from split innings and outs.
- Current Player DNA visual rule: Dismissal Fingerprint should reuse the Player vs Peers comparison-bar/average-marker styling; Bowling by Phase remains verified ball-by-ball only but should not show a repeated visible footnote.
- Current Player Profile Strike Rate split rule: split-level Strike Rate remains BBB-only; when BBB ball rows omit per-ball striker innings audit fields, accept the innings only if aggregated BBB runs and BBB balls exactly match the scorecard innings runs and balls. Mohaneesh Pitre at Epping Recreation Reserve is the known validation case.
- Current Player Profile toggle visual rule: Career Breakdown segmented controls should match the app tab pill visual exactly, with the same rounded light container, soft lavender active pill, muted inactive labels, and no extra shadow.
- Player Profile QA status: a 50-player QA audit has been run on the production Player Profile data sources. Latest result after QA follow-up: 0 Critical, 0 High, 0 Medium, 26 Low, 9 Info findings.
- The remaining QA items are mostly coverage/empty-state issues. Missing verified ball-by-ball phase data should render a premium empty state, not zeros, global values, or stale tables.
- Recommended permanent Player Profile tests: Bat Avg uses outs, BBB Strike Rate uses BBB runs/balls only, missing BBB stays `N/A`, 30s are 30-49 inclusive, 3WI excludes 5WI, BBI sorts/parses wickets then runs, Bowling Phase respects actual match type, and known aliases merge to one canonical profile.
- Permanent lightweight Player Profile metric tests now live in `tests/test_player_profile_metrics.py`; the generated 50-player QA CSV/Markdown outputs stay ignored under `data/processed/experimental/player_profile_qa/`.
- Current Player Profile polish: premiership tags lead the profile badge order, Career Highlights leader cards show season as the main context, Batting Position Best Fit uses a 4+ innings threshold, and Dismissal Fingerprint rows include compact `Club avg` / points-difference labels next to each dismissal type.
- Current Player Profile and Milestone polish: Career Overview hides Fielding on mobile for non-keepers, Career Highlights uses a compact two-card mobile grid, Career Breakdown controls are embedded in the section card, Bowling Phase uses compact mobile table labels (`O`, `W`, `Avg`, `SR`, `Boundary %`) with a subtle BBB coverage note, Dismissal Fingerprint insight sentences now call out dismissal types when they are 3+ points above club average, and the Milestone page view toggle is embedded in the content card using the shared Player Profile segmented styling with `st.session_state` rather than query-link navigation.
- Current Milestone state: Exclusive Clubs category pills (`Matches`, `Runs`, `Wickets`, `Catches`) use `st.session_state` and shared segmented-control styling, not query-link navigation.
- Player Profile production now includes `Recent Form ⚡` below Career Overview. It is scorecard-based from deploy-safe Player Profile summaries, latest-first, desktop latest 10 chips, mobile latest 5 chips, with batting not-out stars and balls only where reliable; bowling form only shows real non-empty figures and does not pad non-bowling matches as `0/0`.
- Season Overview production now includes `Season by Round 🗓️` above Season Standouts. It is scorecard-safe from deploy-safe Season Overview summaries, uses an in-card grade/team segmented control for multi-team seasons, excludes the `All` option, keeps the desktop/tablet grade/team toggle in one horizontal row, keeps the URL unchanged, shows latest five rows before internal scroll, and uses full cricket result wording.
- Season by Round verified premiership/finals wins use exact `match_id` matches from `premiership_wins.csv` for subtle gold row/header trophy treatment. Mobile scorecard links sit on their own line to prevent overlap.
- Season by Round performer logic: Best Batter and Best Bowler combine all FVCC innings for the same player in a match, then preserve both innings in the display, for example `20 & 24*` and `3-33 & 2-42`. Best Batter ranks by combined runs, then highest individual innings; Best Bowler ranks by combined wickets, combined runs conceded, then best single-innings figure. Compact name display may use first names on mobile. Missing scorecard/match rows render a compact empty state.
- Data refresh note: weekly refresh now rebuilds aggregate/public CSVs, current-season match-centre data, and deploy-safe Season Overview, Player Profile, and Hall of Fame summaries. Winter 2026 has R1 and R2 in the refreshed match-centre scope, with Season by Round ordered latest-first.
- Mobile Season by Round grade/team pills use compact rectangular wrapping inside the card rather than a large capsule container, so long grade names stay readable.
- Current wireframing state: compact Recent Form and Season by Round wireframes remain in `docs/wireframes/` as production design references. Production changes are local only until Preet confirms; do not push.

## Opponent Name Normalization Notes

- The app now has a shared opponent club-name normalization helper for deploy-safe Player Profile summaries and visible match/opponent labels.
- Bare reviewed names and `CC` variants should display as full club-level names, for example `Donath` -> `Donath Cricket Club`, `Holy Trinity` -> `Holy Trinity Cricket Club`, `Northern Socials` variants -> `Northern Socials Cricket Club`, and `Olympic Colts` variants -> `Olympic Colts Cricket Club`.
- Keep distinct similarly named clubs separate unless explicitly mapped: examples include Bellfield / Bellfield Bulls / Bellfield Rocketz, Darebin Chargers / Deccan Chargers, Preston Footballers / Preston Baseballers / Preston Druids / Preston YCW District / Preston Himalayan, and Strathewen / Strathewen Cougars.
- The ignored audit folder `data/processed/experimental/name_normalization_audit/` is for Preet review of raw/normalized opponent and ground names and should stay out of commits.

## Ground Name Normalization Notes

- The shared normalization helper also handles venue labels used by Player Profile ground breakdowns, favourite ground-style cards, and match-context displays.
- Reviewed explicit merges: Donath Reserve East/Central/West variants -> `J.C. Donath Reserve`, and Chelsworth Park North/South -> `Chelsworth Park`.
- Reviewed punctuation cleanups include `C.H. Sullivan Memorial Park`, `H.L.T. Oulten Park`, `H.P. Zwar Park`, `T.W. Blake Park`, `J.E. Moore Park`, `I.W. Dole Reserve`, and `W. Ruthven VC Reserve`.
- Do not automatically merge directional ground names unless explicitly reviewed; North/South/East/West can be different playing surfaces at some venues.

Hidden preview pages:

- Season Overview v2
  - route slug: `season-overview-v2`
  - story-first season page with awards, match pulse, role maps, records, strengths/watchouts, and detailed stats lower down.
- Hall of Fame v2
  - route slug: `hall-of-fame-v2`
  - museum-wall record book concept with hero, premiership wall, club legends, iconic performances, fastest verified innings, record holders, greatest seasons, and detailed records lower down.
- Player Profile v2
  - route slug: `player-profile-v2`
  - scouting-card player profile concept with identity hero, DNA cards, coach insight board, player vs peers, advanced identity reads, standout performances, partnerships, milestone watch, timeline, data coverage/trust, and lower audit tables.

All hidden preview pages:

- visible only when `FVCC_SHOW_EXPERIMENTAL=1`
- should not appear in production navigation by default
- if the flag is not enabled and a user manually opens the hidden route, routing should fall back to a safe production page.

Hidden experimental match-centre pages in code:

- Match Insights
- Advanced Analytics
- Player DNA
- Scorebook Lab

Production rule:

- `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES = False`
- These pages should not appear in production navigation unless explicitly requested and reviewed.

Desktop navigation:

- Custom persistent left sidebar.
- Deep navy/purple treatment.
- Main nav links show the current page with a strong purple active state.
- Creator credit appears in the sidebar/footer area.

Mobile navigation:

- Mobile selector/dropdown style.
- Mobile info/help panel should render readable text, not escaped HTML.
- Creator credit should sit at the bottom of pages, not inside the navigation card.

Deep links:

- Player links use `?page=player-profile&player_id=<canonical_or_raw_id>`.
- Season links use `?page=season-overview&season=<season label>`.
- Scorecard links open external PlayCricket scorecards, usually in a new tab.
- GA4 analytics is separate and should not affect routing.

## 3. Visual Design System

Overall direction:

- Premium modern sports analytics dashboard.
- More "club intelligence product" than spreadsheet.
- Clean, confident, warm, and sports-led.

Core style:

- Soft lavender page background.
- White cards with subtle shadows.
- Dark navy headings/body text.
- Purple/indigo primary accents.
- Maroon/burgundy highlight only where meaningful.
- Green for positive/better states.
- Soft red/pink for negative/worse states.
- Grey/neutral for around-average or unavailable states.

Typography and spacing:

- Large page titles, but avoid awkward mobile wrapping.
- Compact table typography where many columns appear.
- Section headings use tasteful emojis sparingly.
- Card radius should stay restrained, generally 8px or close to existing app style.
- Avoid giant empty spaces, especially on mobile.

Cards:

- Cards should feel like premium dashboard modules, not marketing blocks.
- Use cards for repeated items, awards, records, and focused insights.
- Avoid nested cards inside cards where possible.

Tables:

- Light/white table backgrounds on desktop and mobile.
- Numeric columns must remain numeric where sorting matters.
- Use Streamlit `column_config` formatting rather than converting sortable numbers to text.
- Sticky/frozen first columns are valuable on mobile for wide cricket tables.
- Avoid visible `NaN`, `None`, `inf`, internal IDs, or raw debug fields.

Links:

- Player and season links should look app-native.
- Scorecard links should be subtle purple text like `View scorecard ->`.
- Expand controls should be text-style links, not large primary buttons.

Emoji usage:

- Allowed in page and section headings.
- Avoid excessive emoji density in cards.
- Hall of Fame can be more ceremonial, but still restrained.

Creator credit:

```text
App created by
Siddhanth Chaurasiya |
Preet Kaur
For feedback/enquiries:
siddhanthchaurasiya
@gmail.com
```

## 4. Data Architecture

The app is local-data-first. Production pages should render from committed processed CSVs and deploy-safe summaries, not from live API calls during normal user browsing.

Primary external source:

- PlayCricket Australia public data.

Primary aggregate endpoints currently used:

- Club seasons
- Club teams for season
- Grade/team batting statistics
- Grade/team bowling statistics
- Grade/team fielding statistics

Current public base URL documented in discovery:

- `https://grassrootsapiproxy.cricket.com.au`

Raw backup strategy:

- Raw PlayCricket JSON backups are timestamped.
- Old raw backups should never be overwritten.
- Raw historical data stays auditable.
- Processed data can be regenerated from raw backups plus mapping files.

Shared processed aggregate files:

| File | Purpose |
| --- | --- |
| `data/processed/seasons.csv` | Season selector, ordering, current/latest season logic, previous same-type season logic. |
| `data/processed/teams.csv` | Team/grade selector, team IDs, grade IDs, cleaned labels. |
| `data/processed/players.csv` | Player index. |
| `data/processed/all_seasons_batting.csv` | Aggregate batting source for Hall of Fame, Season Overview, Milestone, Player Profile, Player vs Peers. |
| `data/processed/all_seasons_bowling.csv` | Aggregate bowling source for the same shared views. |
| `data/processed/all_seasons_fielding.csv` | Aggregate fielding source for catches, stumpings, run outs, dismissals. |
| `data/processed/all_seasons_matches.csv` | Placeholder/shared match file. |
| `data/processed/all_seasons_scorecard_batting.csv` | Scorecard-level batting placeholder/shared file. |
| `data/processed/all_seasons_scorecard_bowling.csv` | Scorecard-level bowling placeholder/shared file. |
| `data/processed/all_seasons_scorecard_fielding.csv` | Scorecard-level fielding placeholder/shared file. |

Deploy-safe Hall of Fame files:

| File | Purpose |
| --- | --- |
| `data/processed/hall_of_fame/fastest_batting_milestones.csv` | Fastest 50s/100s from verified ball-by-ball data. |
| `data/processed/hall_of_fame/player_bbb_batting_rates.csv` | Verified ball-by-ball batting strike rate inputs for Detailed Records. |
| `data/processed/hall_of_fame/player_bowling_milestones.csv` | Scorecard bowling milestone counts such as 3WI, 5WI, BBI helpers. |
| `data/processed/hall_of_fame/player_premierships.csv` | Player premiership counts and evidence match IDs. |
| `data/processed/hall_of_fame/player_scorecard_milestones.csv` | Scorecard batting milestones: 30s, 50s, 100s, ducks, HS. |
| `data/processed/hall_of_fame/player_win_rates.csv` | Result-mapped player win counts and win percentage. |
| `data/processed/hall_of_fame/premiership_wins.csv` | Verified FVCC premiership wins. |
| `data/processed/hall_of_fame/scorecard_record_links.csv` | Deploy-safe match IDs/links for scorecard links. |

Deploy-safe Season Overview detail files:

| File | Purpose |
| --- | --- |
| `data/processed/season_overview/bbb_batting_rates_by_scope.csv` | Verified ball-by-ball batting rates by season/team scope. |
| `data/processed/season_overview/bbb_bowling_dot_rates_by_scope.csv` | Verified ball-by-ball bowling dot rates by season/team scope. |
| `data/processed/season_overview/scorecard_batting_milestones_by_scope.csv` | Scorecard 30s/50s/100s/ducks/HS support by season/team scope. |
| `data/processed/season_overview/scorecard_bowling_milestones_by_scope.csv` | Scorecard 3WI/5WI/BBI support by season/team scope. |

Local match-centre files:

- `data/processed/match_centre/all_available/all_matches.csv`
- `data/processed/match_centre/all_available/all_ball_by_ball.csv`
- `data/processed/match_centre/all_available/all_scorecard_batting.csv`
- `data/processed/match_centre/all_available/all_scorecard_bowling.csv`
- `data/processed/match_centre/all_available/all_scorecard_fielding.csv`

Runtime boundary:

- Production app should not require `data/raw/match_centre/`, `data/processed/match_centre/`, or `data/processed/experimental/`.
- These folders are local generated sources used to build smaller deploy-safe summaries.
- Do not commit raw/full match-centre archives unless explicitly approved.

Refresh workflow:

- Main script: `scripts/refresh_data.py`
- Match-centre refresh: `scripts/refresh_match_centre_data.py`
- Match-centre all-available backfill: `scripts/backfill_match_centre_available.py`
- Season Overview detail export builder: `scripts/build_season_overview_detail_exports.py`
- Hall of Fame milestone builders include `scripts/build_match_centre_milestones.py` and `scripts/build_premiership_hall_of_fame_exports.py`.

Weekly refresh must rebuild both:

1. Aggregate scorecard/public-stat CSVs.
2. Match-centre-derived deploy-safe summaries for ball-by-ball or scorecard-per-innings metrics.

## 5. Data Quality Rules That Must Not Be Forgotten

### Canonical Player Identity

Players can have multiple PlayCricket profiles or name variants. The app merges confirmed variants through manual mapping files, not fuzzy unreviewed guesses.

Canonical fields:

- `raw_player_id`
- `raw_player_name`
- `canonical_player_id`
- `canonical_player_name`

Important files:

- `data/player_aliases.csv`
- `data/manual_player_merges.csv`
- `data/player_duplicate_audit.csv`
- `data/player_identity_summary.csv`

Confirmed examples:

- Baurel D'Mello + Baurel Dmello -> Baurel D'Mello
- Kalpesh Patel + Kalpeshkumar Patel + duplicate Kalpeshkumar profiles -> Kalpeshkumar Patel
- Faraz Khan + Mohammed Faraz Khan + Mohammad Faraz Khan -> Faraz Khan
- Gopi Krishna + Gopi Krishna Inturi -> Gopi Krishna

Rule:

- After merging profiles, recalculate derived stats from raw totals. Do not average precomputed averages.

### Team / Grade Cleaning

Use `src/utils/team_grade.py` for grade/team display normalization.

Important helpers:

- `clean_grade_name`
- `clean_team_name`
- `build_team_grade_display`
- `apply_team_grade_display_columns`
- `grade_sort_key`

Expected display examples:

- `1s (Jika Shield)`
- `2s (Jack Quick Shield)`
- `3s (B Grade)`
- `Jack Quick Shield`
- `Jack Kelly Shield`
- `B Grade`
- `C Grade`
- `Winter (North Division)`
- `OD (Robert Young DODC)`

Current preferred grade order:

1. Jika Shield
2. Jack Quick Shield
3. Jack Kelly Shield
4. `"B" Grade - John Adams Shield`
5. `"C" Grade - Les Horne Shield`
6. `"D" Grade - Bob Herman Shield`
7. `"E" Grade - Les Kemp Shield`
8. `"F" Grade - Syd Sault Shield`
9. `"F" Grade North - Dave Manion Shield`
10. `"F" Grade South - Harry Torrens Shield`
11. `"F" Grade Central`
12. Casey Radcliffe Shield
13. DODC - Casey Radcliffe Shield
14. DODC - Robert Young Shield
15. North Division
16. North Division - Bhatia Shield
17. North Division - SUNDAY
18. unknown/other grades alphabetically

### Ball-By-Ball Metric Doctrine

This is a hard rule for all current and future pages:

- Runs, innings, wickets, averages, HS, 30s, 50s, 100s, ducks, 4s, 6s, maidens, and BBI may use aggregate or scorecard data where appropriate.
- Any metric that requires delivery-level behaviour must use verified ball-by-ball computation only.
- Do not mix all-scorecard totals with ball-by-ball denominators.

Delivery-level batting examples:

- Bat SR when using balls faced from match-centre data
- batting Dot Ball %
- boundary percentage from balls
- balls per boundary
- balls per dismissal if based on ball-by-ball innings
- phase scoring rates

Delivery-level bowling examples:

- bowling Dot Ball %
- boundary ball %
- one/two/three-run ball distribution
- death-over economy
- powerplay/new-ball phase stats
- wicket phase rates

Correct example:

- Bat SR = ball-by-ball runs from verified ball-by-ball innings / ball-by-ball balls faced from those same innings * 100.

Incorrect example:

- Bat SR = total season scorecard runs / ball-by-ball balls from only the subset of live-scored matches.

Missing data rule:

- If verified ball-by-ball data is missing for the selected season/team scope, show blank or `N/A`.
- Do not display `0.0` for missing ball-by-ball coverage.

## 6. Page Inventory: Hall of Fame

Implementation:

- `src/ui/layout.py`
- main renderer: `render_hall_of_fame_page()`
- detailed state doc: `docs/hall_of_fame_current_state.md`

Purpose:

- All-time club history, all-time leaders, iconic performances, premierships, fastest innings, record holders, and detailed all-time records.

Intro content:

- `Hall of Fame 🏆`
- `Fiji Victorian Cricket Club`
- `The players who shaped the club's history.`
- `Players with multiple PlayCricket profiles are merged into one profile.`

Primary visual sections:

1. Premierships 🛡️
2. All-Time Leaders 👑
3. Iconic Performances 🌟
4. Fastest Innings ⚡
5. Record Holders 📘
6. Greatest Individual Seasons 🎖️
7. Detailed Records 📊

### Premierships 🛡️

Content:

- FVCC Premiership Wins
- Most Premierships
- season, grade, opponent, round, match date, result, captain if available, scorecard link

Source:

- `data/processed/hall_of_fame/premiership_wins.csv`
- `data/processed/hall_of_fame/player_premierships.csv`

Rules:

- Only count verified finals/premiership evidence.
- Player premiership counts use evidence match IDs.
- Do not infer premierships without validated finals detection.

Wireframing opportunities:

- Add a trophy timeline.
- Add per-premiership hero cards.
- Add "premiership squads" expandable detail.

### All-Time Leaders 👑

Cards:

- Most Matches
- Most Runs
- Most Wickets
- Most Catches

Interaction:

- Show top 6 by default.
- Subtle text control expands to top 10: `Show top 10 ↓`.
- Expanded state: `Show less ↑`.

Source:

- all-time aggregate summaries from `all_seasons_batting`, `all_seasons_bowling`, `all_seasons_fielding`.

Design:

- Compact leaderboard cards.
- Player names link to Player Profile.
- Avoid giant CTA-style expand buttons.

### Iconic Performances 🌟

Cards:

- Highest Individual Scores
- Best Bowling Innings

Interaction:

- Show top 6 by default.
- Expand to top 10 with the same subtle control.
- Scorecard links appear where available.

Sources:

- aggregate all-time data
- scorecard link support from `data/processed/hall_of_fame/scorecard_record_links.csv`

Sorting:

- Highest scores by score descending, not-out preferred on ties.
- Best bowling by wickets descending, then runs conceded ascending.

### Fastest Innings ⚡

Subtitle:

- `Based on matches with verified ball-by-ball data.`

Cards:

- Fastest 50s
- Fastest 100s

Source:

- `data/processed/hall_of_fame/fastest_batting_milestones.csv`

Rules:

- Verified ball-by-ball only.
- Wides do not count as balls faced.
- No-balls faced by the batter follow the milestone builder's balls-faced rule.
- Scorecard-only matches cannot prove fastest balls-to-50/100.

Wireframing opportunities:

- Add a "verified data coverage" note or badge.
- Show final innings score and match context more visually.

### Record Holders 📘

Cards:

- Most 100s
- Most 50s
- Most 4s
- Most 6s
- 5 Wicket Hauls
- Most Maidens
- Ducks
- Best Win %

Best Win %:

- Source: `data/processed/hall_of_fame/player_win_rates.csv`
- Minimum eligibility: 60 matches.
- Display: percentage plus `wins from matches`.

### Greatest Individual Seasons 🎖️

Desktop title:

- `Greatest Individual Seasons 🎖️`

Mobile title:

- `Greatest Seasons 🎖️`

Content:

- Best batting seasons.
- Best bowling seasons.
- Season cards include matches and key totals.

Source:

- aggregate season-level data.

### Detailed Records 📊

Format:

- Custom sortable HTML table.
- Sticky Player column.
- Compact 13px font.
- Three tabs: Batting, Bowling, Fielding.

Batting columns:

1. Player
2. Seasons
3. Debut Season
4. Latest Season
5. Matches
6. Win %
7. Runs
8. Bat Avg
9. Bat SR
10. HS
11. 30s
12. 50s
13. 100s
14. 0s
15. 4s
16. 6s

Batting definitions:

- Bat SR uses verified ball-by-ball only from `player_bbb_batting_rates.csv`.
- 30s = scorecard innings from 30 to 49 inclusive, including not-outs.
- HS sorts by numeric score, ignoring `*`, with not-outs treated appropriately for display.

Bowling columns:

1. Player
2. Seasons
3. Matches
4. Win %
5. Overs
6. Maidens
7. Wickets
8. Avg
9. Bowl SR
10. Econ
11. BBI
12. 3WI
13. 5WI
14. 10WM

Bowling definitions:

- 3WI = scorecard bowling innings with exactly 3 or 4 wickets.
- 5WI = scorecard bowling innings with 5+ wickets.
- BBI sorts by wickets descending, then runs ascending.

Fielding columns:

1. Player
2. Seasons
3. Matches
4. Catches
5. Stumpings
6. Run Outs
7. Dismissals

Known Hall of Fame gaps:

- Some deploy-safe files must be regenerated when match-centre coverage grows.
- Premiership detection should stay conservative until finals audit is fully validated.
- Win % depends on result-mapped match coverage; not every historical match may have reliable result data.
- Fastest Innings coverage is only as complete as verified ball-by-ball archive coverage.

## 7. Page Inventory: Season Overview

Implementation:

- `src/ui/layout.py`
- main render flow: `render_overview()`, `render_data_source_panel()`, `render_overall_section()`, `render_biggest_improvers()`, `render_team_specific_leaders()`, `render_full_stats_section()`

Purpose:

- Season-specific performance dashboard with slicers, standouts, improvers, leaders by team/grade, and detailed stats.

Header:

- `Season Overview 📊`
- `Fiji Victorian Cricket Club`
- `Track team performance, player leaders, and season-by-season club trends.`
- `Showing data for {season} • {team/grade scope}`

Filter card:

- Select Season
- Select Team/Grade
- Uses cleaned team/grade labels.
- Drives every Season Overview section.

Sections:

1. Season Standouts ✨
2. Biggest Improvers 📈
3. Leaders by Team/Grade 👥
4. Detailed Stats 📊

### Season Standouts ✨

Subtext:

- `Top performers across the selected season and team scope.`

Content:

- top run scorers
- top wicket takers
- top fielding/dismissal players
- record-style leader cards

Source:

- selected season/team scope from aggregate batting/bowling/fielding processed CSVs.

### Biggest Improvers 📈

Subtext:

- `Players with the strongest improvement compared to previous season.`

Cards:

- Biggest Run Improvement
- Biggest Wickets Improvement

Rules:

- Summer compares with previous Summer season.
- Winter compares with previous Winter season.
- Current and previous match thresholds apply.
- Winter minimum match threshold is lower than Summer because Winter seasons are shorter.
- Wickets improvement has an additional previous-season overs qualification rule: previous season overs >= 15, unless explicitly changed later.

Debug file:

- `data/debug_biggest_improvers.csv`
- Should generally not be committed unless intentionally reviewed.

### Leaders by Team/Grade 👥

Subtext:

- `Top performers and key totals by team/grade.`

Content:

- team/grade cards using cleaned labels.
- top batter, top bowler, fielding leader, totals.

Source:

- selected season aggregate rows grouped by cleaned team/grade.

### Detailed Stats 📊

Tabs:

- Batting
- Bowling
- Fielding

Batting visible columns:

1. Player
2. M
3. Innings
4. Runs
5. Bat Avg
6. Bat SR
7. HS
8. 30s
9. 50s
10. 100s
11. 0s
12. 4s
13. 6s

Batting definitions:

- Runs, innings, average, HS, 50s, 100s, ducks, 4s, 6s can come from aggregate/scorecard source.
- 30s uses scorecard innings where available and falls back conservatively from HS if needed for incomplete per-innings coverage.
- Bat SR is ball-by-ball-only when sourced from match-centre detail exports.
- Bat SR is displayed with `%` while keeping numeric sorting.
- Dot Ball % was removed from the visible batting table.

Bowling visible columns:

1. Player
2. M
3. Overs
4. Maidens
5. Wickets
6. Bowl Avg
7. Bowl SR
8. Eco
9. BBI
10. 3WI
11. 5WI

Bowling definitions:

- Overs display is cricket-style overs.
- Overs sorting must use actual balls bowled, not decimal-text sorting.
- 3WI = individual scorecard bowling innings with exactly 3 or 4 wickets.
- 5WI = 5+ wickets.
- Dot Ball % was removed from the visible bowling table.

Fielding visible columns:

1. Player
2. M
3. Catches
4. Stumpings
5. Run Outs
6. Total Dismissals

Source-specific notes:

- Season Overview detailed-table scorecard milestones come from `data/processed/season_overview/*_by_scope.csv`.
- Ball-by-ball metrics must use the same selected season/team scope.
- If weekly refresh updates aggregate stats but not match-centre deploy-safe summaries, rate metrics can become stale. The refresh workflow now documents that both must be rebuilt.

Known Season Overview gaps:

- Current page is still more report-like than story-led.
- Detailed Stats is functional but table-heavy.
- Some per-innings metrics rely on deploy-safe summaries and can lag if refresh workflow is not followed.
- Specific team/grade labels may still show inconsistencies if match-centre grade names are raw.
- A visible data-coverage indicator would help users understand ball-by-ball coverage.

## 8. Page Inventory: Season Overview v2 Hidden Preview

Implementation:

- route slug: `season-overview-v2`
- `SHOW_SEASON_OVERVIEW_V2 = os.getenv("FVCC_SHOW_EXPERIMENTAL") == "1"`
- data helper module: `src/data/season_story_analytics.py`
- UI renderers in `src/ui/layout.py`

Access:

- Hidden by default.
- Only appears in navigation when `FVCC_SHOW_EXPERIMENTAL=1`.
- Local preview: `http://localhost:8502/?page=season-overview-v2`

Purpose:

- Premium story-led season product.
- Designed for exploration and wireframing.
- Does not replace production Season Overview.

Current structure:

1. Filter bar
2. Page header
3. Season Story Hero
4. If the Season Ended Today
5. Season Awards
6. Season Pulse
7. Top Performances of the Season
8. Batting Depth Chart + Bowling Role Map
9. Season Records Broken
10. Club Strengths & Watchouts
11. Team/Grade Leaders
12. Detailed Stats

Header:

- `Season Overview v2 ✨`
- `Fiji Victorian Cricket Club`
- `A premium season story built from scorecards, records and match-centre insights.`
- `Showing data for {season} • {team/grade}`

### Season Story Hero

Purpose:

- Give the season a deterministic identity.

Tiles:

- Season record
- Season identity
- Top score
- Best spell

Identity labels currently generated:

- Bowling-led
- Batting-led
- Balanced
- Premiership pace
- Building

Source:

- aggregate batting/bowling/fielding
- match-centre match results where available

Current limitations:

- Result parsing is text-based and should be audited for edge cases.
- "Premiership pace" is a simple heuristic, not actual premiership confirmation.

### If the Season Ended Today 🏁

Cards currently include:

- Run leader
- Wicket leader
- Best batting average
- Best bowling average
- Fielding leader
- Best all-rounder
- Hidden MVP
- Fastest verified innings if ball-by-ball supports it

Sources:

- aggregate season rows
- ball-by-ball for fastest verified innings

### Season Awards 🏅

Cards currently include:

- Orange Cap
- Purple Cap
- Golden Gloves
- All-Round Star
- Economy Controller
- Strike Bowler
- Hidden MVP

Requested-but-not-yet-rich area:

- Breakout Player would ideally reuse Biggest Improvers logic but is not yet a full v2 award.
- Awards are currently deterministic/simple, not a complex model.

### Season Pulse 🧭

Purpose:

- Match-by-match story strip.

Each card aims to show:

- result badge
- opponent
- grade/team
- match date
- top FVCC batter
- best FVCC bowler
- scorecard link where supported by UI/source

Source:

- `data/processed/match_centre/all_available/all_matches.csv`
- scorecard batting/bowling from match-centre scope

Limitations:

- All-teams scope can produce a long strip.
- Grade labels may come from raw match-centre data.
- Scorecard link and opponent derivation should be validated across two-day games and byes/forfeits.

### Top Performances of the Season 🔥

Cards currently include:

- Best Batting Innings
- Best Bowling Innings
- Best All-Round Performance
- Biggest Carry Job

Requested future cards:

- Best fielding performance
- Highest wicket share

Source:

- scorecard batting/bowling rows for innings-level performances.
- aggregate data for all-round impact.

### Batting Depth Chart 🪜

Purpose:

- Show where runs come from by batting position.

Buckets:

- Openers
- No. 3
- No. 4
- No. 5
- No. 6
- No. 7
- No. 8
- No. 9
- Tail

Metrics:

- innings
- runs
- average
- share of runs

Source:

- match-centre scorecard batting with batting order.

Limitations:

- Requires scorecard batting order coverage.
- Does not yet split by team grade or match format beyond selected scope.

### Bowling Role Map 🎯

Role cards currently include:

- Strike Bowler
- Economy Controller
- Workhorse
- Breakthrough Bowler
- Wicket Share Leader

Source:

- aggregate bowling rows for selected scope.

Limitations:

- Phase-based roles are not claimed unless ball-by-ball support is added later.
- "Breakthrough" is currently wicket-rate based, not a true match-phase breakthrough measure.

### Season Records Broken 🧨

Current cards:

- Season best highest score
- Season best bowling
- Fastest verified innings if available

Important wording rule:

- Do not say "Club record" unless checked against all-time records.
- Use "Season best" when only selected-season data is compared.

### Club Strengths & Watchouts 🧠

Two-card section:

- Strengths
- Watchouts

Logic:

- deterministic, based on season identity, wicket spread, ducks, and ball-by-ball coverage.

Tone:

- Useful and grounded.
- Avoid dramatic or overconfident wording.

### Team/Grade Leaders

Current v2 reuses or enhances the existing team/grade leader concept.

Future opportunities:

- Add team record/win rate by grade.
- Add premiership indicator.
- Add hidden MVP by grade.
- Add top batter/top bowler/fielding leader with better visuals.

### Detailed Stats

Current v2 brings current Season Overview Detailed Stats near the bottom.

Rule:

- Do not make tables the top of the v2 page.

Known v2 technical debts:

- Needs unit tests for `src/data/season_story_analytics.py`.
- Match-centre player names may be abbreviated and not fully canonicalized in some cards.
- Some v2 sections use simple impact heuristics; those should be renamed or documented if they remain.
- Scorecard links should be audited across cards.
- Mobile spacing needs real-device review.
- Data-coverage indicators would make the page more trustworthy.

## 9. Page Inventory: Milestone

Implementation:

- `src/ui/layout.py`
- functions around milestone watchlist and exclusive club rendering.

Purpose:

- Active-player milestone watch.
- Focuses on players nearing major club milestones.

Header:

- `Players closing in on major club milestones 🎯`
- `Fiji Victorian Cricket Club`
- `Showing active players only — players who have appeared for FVCC in the last 3 seasons.`

Sections:

- Milestone Watchlist 🎯
- Exclusive Club 💪

Active player logic:

- players who appeared in the last 3 seasons.
- uses canonical identity.

Milestone categories:

- Matches
- Runs
- Wickets
- Catches
- Dismissals

Display:

- milestone cards and progress bars.
- filters by milestone category.

Removed/avoid:

- no dismissal milestone visual beyond appropriate fielding milestone handling.
- no cricket emoji in subtitle.

Future enhancements:

- Closest Milestone hero card.
- Talking Points for the Next Game.
- Tiered Exclusive Club.
- "Likely soon" / "within reach" labels.
- Shareable social media milestone cards.

## 10. Page Inventory: Player Profile

Implementation:

- `src/ui/layout.py`
- main renderer: `render_player_profile_page()`

Purpose:

- Search any player and explore their career story across seasons, grades, and formats.

Header:

- `Player Spotlight 🏏`
- `Fiji Victorian Cricket Club`
- `Search any player and explore their career story across seasons, teams, and formats.`

Search card:

- player selector/search.
- helper text: `Start typing a name to find a player from club records.`

Profile summary order:

1. PLAYER PROFILE
2. Player Name
3. Player Summary
4. Grades Played
5. Career Span
6. Classification badges

Sections:

1. Career Snapshot 📌
2. Career Highlights 🌟
3. Player vs Peers 📊
4. Season Trends 📈
5. Season History 📅
6. Grade Breakdown 🧭
7. Career Overview 🧩
8. Milestone Watch 🎯

### Career Snapshot / Summary

Content:

- player name
- career span with full season labels
- grades played with cleaned/deduplicated grades in standard order
- badges
- summary sentence

Source:

- canonical player aggregate rows across batting/bowling/fielding.

### Classification Badges

Desired behavior:

- Show all applicable tags.
- Keep badges wrapping neatly.
- Badge priority affects order.

Current/desired badge ideas include:

- Club Legend
- Genuine All-rounder
- All-round Contributor
- Upcoming Star
- Star Batter
- Dependable Batter
- Star Bowler
- Wicket Taker
- Golden Arm
- Partnership Breaker
- Economy Controller
- Big Hitter
- Values His Wicket
- Gap Finder
- Quick Scorer
- Workhorse
- Safe Hands
- Keeper Impact
- Season Standout
- Milestone Maker
- Club Veteran
- Club Contributor
- Emerging Player

Audit doc:

- `docs/player_profile_tags_audit.md`

### Career Highlights 🌟

Content:

- Highest Run Maker at Club
- Highest Run Maker in Grade
- Highest Wicket Taker at Club
- Highest Wicket Taker in Grade
- season/grade context included where available

### Player vs Peers 📊

Current subtitle:

- `Compared against players from the same seasons and grades.`

Visual:

- Purple dot = selected player.
- Grey marker = peer average.
- Range line = lowest to highest peer value.
- Status pill: Better than avg / Around avg / Worse than avg.

Peer group:

- same seasons selected player played in.
- same cleaned grade/team-grade contexts where possible.
- fallback to same-season peers if old rows have incomplete grade metadata.
- canonical identity.

Batting metrics currently rendered:

1. Batting Avg
2. Strike Rate
3. Balls per Dismissal
4. Minutes per Dismissal
5. Boundary Rate
6. Innings per Duck

Bowling metrics currently rendered:

1. Bowling Avg
2. Bowling SR
3. Economy Rate
4. Overs per Maiden
5. Overs per Extra

Important doc drift:

- `docs/player_vs_peers_calculation_audit.md` still mentions Unassisted Wicket % in the bowling table.
- Current rendered UI no longer includes Unassisted Wicket %.
- Future doc cleanup should remove or mark that metric as retired.

Label logic:

- Any better-than-peer result is `Better than avg`.
- Marginally worse within 10% is `Around avg`.
- More than 10% worse is `Worse than avg`.
- Higher-is-better: batting average, strike rate, balls/minutes per dismissal, boundary rate, innings per duck, overs per extra.
- Lower-is-better: bowling average, bowling strike rate, economy, overs per maiden.

Special duck rule:

- If player has zero ducks and at least 10 innings, Innings per Duck should be labelled `Better than avg`.
- If zero ducks but fewer than 10 innings, avoid overclaiming.

### Season Trends 📈

Content:

- trend charts for season-level batting/bowling performance.
- labels should avoid overlapping/cramping when many seasons appear.

Technical note:

- Altair `fontWeight` must use valid values such as `800` or `"bold"`, not string `"850"`.

### Season History 📅

Content:

- season-by-season batting/bowling/fielding tables.
- no visible total rows.
- no table filters.
- sticky Season column on mobile.

Bowling low-volume rule:

- A bowling row should appear for any bowling activity, even if wickets = 0.
- Activity includes overs, balls, runs conceded, maidens, wides/no-balls, or wickets.
- Bowling average/SR remain blank if wickets = 0.

### Grade Breakdown 🧭

Content:

- grade-wise batting/bowling/fielding summaries.
- cleaned grade labels and standard grade order.
- no visible total rows.
- no table filters.
- sticky Grade column on mobile.

### Career Overview 🧩

Batting order:

- Matches
- Runs
- Average
- 4s
- 6s
- 0s
- HS

Bowling includes:

- Strike Rate
- Maidens
- BBI

### Milestone Watch 🎯

Content:

- nearest meaningful milestones for selected player.
- no dismissal milestone visual unless explicitly reintroduced.

Known Player Profile gaps:

- Player vs Peers has no minimum-volume thresholds yet.
- Minutes per Dismissal often unavailable.
- Player Profile deep links work, but clickable player names throughout the entire app can still be expanded.
- Shareable player cards would be useful.
- Some charts/tables can become dense on mobile.

## 11. Hidden Experimental Match-Centre Concepts

These are not production pages while `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES = False`.

Available code areas:

- `src/data/match_centre_fetcher.py`
- `src/data/match_centre_parser.py`
- `src/data/ball_by_ball_parser.py`
- `src/analytics/match_centre_advanced.py`
- `src/data/player_dna_analytics.py`
- `src/data/scorebook_lab_analytics.py`
- `docs/experimental_match_centre_insights.md`
- `docs/scorebook_lab_analytics.md`

Potential insights already explored:

- 3-wicket hauls.
- Highest score in match.
- Best bowling figures in match.
- Master Chaser innings.
- Finals detection.
- Premierships won.
- Big Game Players.
- Player DNA.
- Scorebook Lab.

Wireframing caution:

- These are useful concept libraries, but should not be exposed in production navigation without explicit user approval.

## 12. Metrics Glossary And Sources

### Aggregate / Scorecard-Safe Metrics

These can generally use PlayCricket aggregate rows or scorecard innings, depending on the page:

- Matches
- Innings
- Runs
- Not outs
- Outs
- Batting average
- Highest score
- 30s
- 50s
- 100s
- Ducks / 0s
- 4s
- 6s
- Wickets
- Bowling average
- Bowling strike rate from aggregate balls/wickets
- Economy from aggregate runs/balls
- Overs
- Maidens
- BBI
- 3WI
- 5WI
- 10WM
- Catches
- Stumpings
- Run Outs
- Total Dismissals

### Scorecard-Per-Innings Metrics

These require individual scorecard innings rows rather than season aggregate rows:

- 30s = batting innings 30-49 inclusive, including not-outs.
- 3WI = bowling innings with exactly 3 or 4 wickets.
- 5WI = bowling innings with 5+ wickets.
- scorecard innings context for best innings and carry job.

### Ball-By-Ball-Only Metrics

These must use verified ball-by-ball rows:

- Fastest 50s
- Fastest 100s
- Bat SR when built from delivery-level balls faced
- batting Dot Ball %
- bowling Dot Ball %
- boundary ball %
- balls per boundary
- phase-based batting/bowling metrics
- bowling ball outcome distribution
- death-over/new-ball role analysis

### Derived Peer Metrics

Player vs Peers should avoid average-of-averages where possible. Pooled peer totals are preferred for:

- Batting Avg
- Strike Rate
- Balls per Dismissal
- Minutes per Dismissal
- Boundary Rate
- Innings per Duck
- Bowling Avg
- Bowling SR
- Economy Rate
- Overs per Maiden
- Overs per Extra

## 13. Analytics, Privacy, And Tracking

GA4 helper:

- `src/utils/analytics.py`

Configuration:

- Streamlit secret or environment variable: `GA4_MEASUREMENT_ID`

Production measurement ID discussed:

- `G-D0D39PLD1X`

Behavior:

- If the ID is missing, analytics silently does nothing.
- App should still run locally.
- Optional debug flag: `FVCC_ANALYTICS_DEBUG=1`

Events intended/tracked:

- page views for production pages.
- `player_profile_view` with player name/slug/id where available.
- Hall of Fame view events.
- filter changes where implemented.

Privacy rule:

- Do not track private user-entered text.
- Do not track emails, phone numbers, or sensitive data.
- Public player names/slugs already shown in the app are acceptable, with slug preferred.

## 14. Technical Debt And Risk Register

High priority:

- Keep ball-by-ball deploy-safe summaries fresh during weekly refresh.
- Add automated checks preventing mixed-source rate metrics.
- Clean up outdated docs where implementation moved on, especially Player vs Peers Unassisted Wicket %.
- Add unit tests for Season Overview detailed-table source rules.
- Add unit tests for `src/data/season_story_analytics.py`.
- Standardize player-name canonicalization between aggregate data and match-centre scorecard/ball-by-ball files.
- Standardize grade cleaning for match-centre grade labels.

Medium priority:

- Consolidate table rendering and numeric formatting helpers.
- Create a consistent "data availability" component for ball-by-ball coverage.
- Create a single deploy-safe match/scorecard summary layer used by Hall of Fame, Season Overview, v2, and future Player Profile enhancements.
- Reduce duplicated metric definitions across docs/scripts/layout helpers.
- Expand GA4 event tracking carefully without spamming reruns.
- Add screenshots/mobile visual checks before pushing major UI work.

Lower priority:

- Better page-level loading states.
- More expressive empty states with data source explanation.
- More consistent card components across pages.
- More flexible design tokens in `src/ui/theme.py`.
- A small admin/data-quality page for mappings and refresh status.

Known data risks:

- Historical ball-by-ball coverage is incomplete.
- Some match-centre scorecards can have abbreviations that do not match aggregate player names.
- Some match-centre two-day matches can have innings/ball-event mismatches.
- Public endpoints can change shape.
- Result text parsing can be brittle.
- Old grades/team names can remain messy if new raw variants appear.

## 15. Wireframing Opportunities

### Global App

- Add a "data coverage" badge to sections using ball-by-ball.
- Add page-level "last refreshed" indicator.
- Add lightweight breadcrumbs/deep-link copy buttons.
- Make player and season links universally consistent.
- Add shareable player/record cards.

### Hall of Fame

- Trophy timeline for Premierships.
- "Record Book" visual treatment for Detailed Records.
- Better distinction between all-time records and verified ball-by-ball records.
- Add "record context" cards: era, grade, opponent, scorecard.
- Add filters only if they do not clutter the page.

### Season Overview

- Use Season Overview v2 as the future direction.
- Put story, awards, pulse, role maps, and strengths/watchouts above tables.
- Add match-level "season arc" strip.
- Add "what changed since last week" after weekly refresh.
- Add a coverage card showing scorecard matches vs ball-by-ball matches.

### Season Overview v2

- Improve hero card with a more cinematic layout.
- Add a grade/team comparison strip.
- Add "selection talking points" based on deterministic rules.
- Add weekly snapshot cards.
- Turn depth chart and role map into the core middle of the page.
- Add "clutch moments" only after chase/finals logic is reliable.

### Milestone

- Add closest milestone hero.
- Add social talking points.
- Add time-to-milestone estimates based on recent rate.
- Add "exclusive club" tiering.

### Player Profile

- Add compact player story timeline.
- Add "best games" and "against/opponent strengths".
- Add downloadable/shareable player card image.
- Add peer sample size and data coverage.
- Add phase/rate stats only where ball-by-ball coverage exists.

## 16. Suggested ChatGPT Wireframing Prompts

Use one of these with this document:

```text
Using the attached Scorebook app context, propose a premium wireframe for Season Overview v2. Keep the current FVCC design language, put storytelling above tables, and identify which cards need scorecard data versus ball-by-ball data.
```

```text
Using the attached app context, redesign the Hall of Fame page as a premium sports record book. Preserve all existing sections and calculations, but improve layout, hierarchy, mobile behavior, and empty states.
```

```text
Using the attached app context, propose a Player Profile redesign focused on career story, peer comparison, and shareable player identity. Respect the current metric source rules and canonical identity logic.
```

```text
Using the attached app context, create a design-system inventory for The Scorebook: cards, tables, badges, links, expand controls, empty states, chart labels, and mobile rules.
```

## 17. Future Enhancements Log

Product ideas:

- Link player names across the whole app to Player Profile.
- Shareable player profile links.
- Download player card image.
- Team / Grade Profile page.
- Awards page.
- Compare players.
- Records near me for selected player.
- Timeline / career story.
- Club season report export.
- Milestone social media talking points.
- Data quality/admin page.
- Current-week change summary after refresh.

Advanced analytics:

- Boundary Dependency.
- Not Out Rate.
- Conversion Rate.
- Start Frequency.
- Bowling Discipline Index.
- Maiden Pressure Rate.
- Wickets per Over.
- Bowling Control Score.
- Fielding Impact per Match.
- Keeper Impact using wicketkeeper catches + stumpings.
- Direct Run-Out Impact.
- Grade Dominance.
- Era-Adjusted Impact.
- Season Consistency Score.
- All-Round Match Balance.
- Player DNA panel.
- Master Chaser.
- Big Game Player.
- Finals MVP.

Data/engineering:

- Automated weekly refresh with validation summary.
- Deploy-safe scorecard summary layer.
- Deploy-safe ball-by-ball summary layer.
- Metric source registry.
- Tests for every high-risk metric.
- Browser screenshot regression checks for key pages.
- Better stale-cache warnings.

## 18. Files To Maintain

Core docs:

- `docs/project_handover.md`
- `docs/app_wireframing_context.md`
- `docs/hall_of_fame_current_state.md`
- `docs/data_refresh_workflow.md`
- `docs/match_centre_refresh_workflow.md`
- `docs/player_profile_tags_audit.md`
- `docs/player_vs_peers_calculation_audit.md`
- `docs/experimental_match_centre_insights.md`

Core code:

- `app.py`
- `src/ui/layout.py`
- `src/ui/theme.py`
- `src/data/playcricket_ingestion.py`
- `src/data/playcricket_public.py`
- `src/data/season_story_analytics.py`
- `src/utils/player_identity.py`
- `src/utils/team_grade.py`
- `src/utils/analytics.py`

Mapping/audit files:

- `data/player_aliases.csv`
- `data/manual_player_merges.csv`
- `data/player_duplicate_audit.csv`
- `data/player_identity_summary.csv`
- `data/team_grade_display_audit.csv`

Deploy-safe summaries:

- `data/processed/hall_of_fame/*.csv`
- `data/processed/season_overview/*.csv`

Ignored/generated files:

- `data/raw/match_centre/`
- `data/processed/match_centre/`
- `data/processed/experimental/`
- `data/debug_biggest_improvers.csv`
- `data/debug_player_vs_peers.csv`

## 19. Final Notes For Future Sessions

Before making future app changes:

1. Read this document and `docs/project_handover.md`.
2. Check git status.
3. Create a checkpoint commit if there are uncommitted changes.
4. Keep changes scoped to the requested page/feature.
5. Preserve canonical player identity logic.
6. Preserve team/grade cleaning.
7. Preserve the ball-by-ball metric doctrine.
8. Run the app locally on port `8502`.
9. Commit locally after verification.
10. Do not push until Preet confirms.
