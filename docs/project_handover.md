# Project Handover

This document is the working handover for The Scorebook / FVCC app. It is intended to let a fresh Codex session continue safely without relying on previous chat history. Where older requests conflict with the current app, treat the current code as the source of truth.

## 1. Project Overview

- App name / working name: The Scorebook / FVCC app
- Purpose: a Streamlit cricket analytics app for Fiji Victorian Cricket Club using PlayCricket Australia data.
- Main goal: make club records, season stats, milestones, and player profiles easy to explore.
- Repository: https://github.com/sidchaurasiya/the-scorebook-fvcc.git
- Deployment: Streamlit Cloud app is deployed from GitHub `main`.
- Local project path: `/Users/preetkaur/Documents/Codex/2026-04-24/you-are-an-expert-full-stack`
- Local run command:

```bash
./.venv-app/bin/streamlit run app.py --server.port 8502
```

- Current branch: `main`
- Important workflow:
  - Check git status before changes.
  - Create a checkpoint commit if there are uncommitted changes.
  - Keep changes scoped to the requested page or feature.
  - Run locally on port `8502` for review.
  - Commit locally after verification.
  - Do not push until Preet confirms.

## Multi-Club Scalability Foundation

- Phase 1 introduces a config foundation only; FVCC remains the default and only real configured club.
- Active config path: `clubs/fvcc/club_config.yaml`.
- Future-club starter template: `clubs/_template/club_config.yaml`.
- Active club selection checks `CLUB_ID` from the environment first, then Streamlit secrets, and falls back to `fvcc`.
- The new loader lives in `src/config/club_config.py`.
- Phase 3 copied production-safe FVCC processed CSVs into `clubs/fvcc/data/processed/...` and updated runtime reads to prefer those club-specific files.
- `scripts/check_club_config.py` verifies the active club config and key deploy-safe data folders without network calls or file writes.
- Phase 1 only wired low-risk display identity/contact values through config. Team/grade logic, identity aliases, opponent mappings, and ground mappings remain later-phase work.
- Phase 2 adds explicit club-aware path helpers for processed, Hall of Fame, Season Overview, Player Profile, match-centre, experimental, and root mapping paths.
- Low-risk runtime readers now use config-aware paths for deploy-safe Hall of Fame files, Season Overview files, Player Profile processed summaries, match-centre read roots, and aggregate processed CSV reads.
- Phase 2.5 validates active-club runtime selection: no `CLUB_ID` defaults to `fvcc`, `CLUB_ID=fvcc` resolves the same paths and app pages, and invalid club IDs fail clearly in `scripts/check_club_config.py`.
- Phase 4 made deploy-safe export builders club-aware.
- Phase 5 made aggregate refresh writes club-aware: `scripts/refresh_data.py --club <club_id>` writes processed aggregate CSVs to `clubs/<club_id>/data/processed/` by default.
- Legacy `data/...` files remain in place as fallback during migration. Raw/full match-centre data, experimental outputs, player identity mapping files, raw JSON backups, cache, and timestamped backups remain legacy/global for later phases.
- The detailed audit is in `docs/multi_club_architecture_audit.md`; the phased roadmap is in `docs/multi_club_scalability_plan.md`.

## Current Player Profile Work In Progress

- Player Profile is being refined on `main`; do not push until Preet confirms the local review.
- The current production section is `Career Breakdown 🧭`; earlier `Career Overview` naming was reviewed but the visible app section is now back to Career Breakdown.
- Player Profile now includes `Career Breakdown 🧭`, combining Season / Grade / Opponent / Ground / Home/Away views with Batting / Bowling / Fielding discipline views.
- Player Profile now includes `Player DNA 🧬` with Batting Position, Dismissal Fingerprint, and Bowling by Phase modules.
- Batting strike rate must use verified ball-by-ball runs and verified ball-by-ball balls from the same covered innings only. Do not mix all-scorecard runs with ball-by-ball denominators.
- Season Standout profile tags must count unique standout seasons only, not multiple club/grade or batting/bowling awards in the same season.
- Premiership Winner and Premiership Winning Captain tags are being added from deploy-safe premiership records when evidence exists.
- Batting Position uses scorecard batting-order groups; Bowling by Phase uses verified ball-by-ball only and must respect actual match type before phase buckets.
- Current UI fixes in progress: compact Batting Position rows, shared toggle styling for Career Breakdown and Bowling by Phase, Bowling by Phase table columns, dismissal benchmark marker reuse from Player vs Peers, and compact/wrapped Career Breakdown tables.
- Keep Hall of Fame, Season Overview, Milestone, routing, GA4, and experimental page visibility unchanged while this work is in progress.
- Current Player Profile split-average fix: Career Breakdown batting splits must exclude explicit `Did Not Bat` rows, count real batting innings only, and calculate average as `Runs / Outs` where `Outs = Innings - Not Outs`. True `0*` innings remain innings and not-outs; DNB rows are not innings.
- Current Player DNA visual fix: Dismissal Fingerprint should share the Player vs Peers comparison-bar classes/marker styling, Bowling by Phase values should render in dark table text, and the visible bowling-phase BBB footnote has been removed while the BBB-only calculation rule remains in code.
- Current Player Profile BBB split-rate fix: split-level Strike Rate still uses only BBB runs and BBB balls, but verified innings can now pass completeness validation when ball rows omit striker innings audit fields, as long as the aggregated BBB runs/balls match the scorecard innings runs/balls. This fixes Mohaneesh Pitre at Epping Recreation Reserve showing `40.0%` instead of `N/A`.
- Current Player Profile toggle styling: Career Breakdown dimension and discipline segmented controls should match the app tab pill style: light lavender-grey capsule, soft lavender active pill, fully rounded shape, no shadow, and consistent sizing.
- Current Player Profile QA status: a 50-player audit script/report was added and run locally. Latest audit result after QA follow-up: 0 Critical, 0 High, 0 Medium, 26 Low, 9 Info findings.
- Remaining Player Profile QA issues are mainly data-coverage and empty-state gaps, not confirmed formula bugs: older bowlers without verified ball-by-ball phase rows, sparse split views for players with no batting/bowling/fielding source rows, and documented missing BBB Strike Rate coverage.
- Bowling Phase must never fake missing ball-by-ball coverage. If no verified BBB phase summary exists for a bowler, show a calm empty state such as `Bowling phase data is not available for this player yet.`
- Player vs Peers no longer shows `Minutes per Dismissal`.
- Player vs Peers `Balls per Dismissal` is BBB-only: verified BBB balls faced divided by BBB dismissals from the same covered innings only. Never mix BBB balls with all-scorecard dismissals.
- Recommended permanent tests for Player Profile metric rules: batting average uses outs, BBB Strike Rate uses BBB runs/balls only, missing BBB is `N/A`, 30s are 30-49 inclusive, 3WI excludes 5WI, BBI parses wickets then runs, bowling phase respects match type, and known aliases resolve to one canonical profile.
- A lightweight permanent pytest file now covers those Player Profile metric doctrines at `tests/test_player_profile_metrics.py`; generated 50-player QA reports remain local under `data/processed/experimental/player_profile_qa/`.
- Current Player Profile polish: premiership profile tags are now top-priority (`Premiership Winning Captain` before `Premiership Winner`, both before other tags), Career Highlights leader cards use the season as their main context instead of repeating the selected player name, Batting Position `Best fit` now requires 4+ innings in a position, and Dismissal Fingerprint rows show compact club-average/difference detail beside each dismissal type.
- Current Player Profile and Milestone polish: Career Overview hides the Fielding card on mobile for non-keepers, Career Highlights uses compact two-per-row mobile cards, Career Breakdown toggles now sit inside the section card, Bowling Phase uses compact mobile table labels (`O`, `W`, `Avg`, `SR`, `Boundary %`) with a subtle BBB coverage footnote, Dismissal Fingerprint insight copy uses a 3+ percentage-point over-index threshold, and the Milestone page view toggle is embedded inside the content card using the shared Player Profile segmented styling with `st.session_state` instead of query-link navigation.
- Current Milestone bug fix: Exclusive Clubs category selection (`Matches`, `Runs`, `Wickets`, `Catches`) now follows the same `st.session_state` segmented-control pattern as the main Milestone view toggle, so it must not update query params, reset the page route, or jump the page.
- Player Profile now includes `Recent Form ⚡` directly below Career Overview. It reads deploy-safe `data/processed/player_profile/recent_form_batting.csv` and `recent_form_bowling.csv`, orders latest first, shows desktop latest 10 chips, hides to latest 5 chips on mobile, and no longer displays the `Latest first · 10 shown` helper copy. Bowling form only includes real bowling figures with wickets or runs conceded, so non-bowling matches are not padded as `0/0`.
- Season Overview now includes `Season by Round 🗓️` above Season Standouts. It reads deploy-safe `data/processed/season_overview/season_by_round_scorecards.csv`, shows one selected grade/team at a time, provides an in-card session-state grade/team toggle without an `All` option, keeps the desktop/tablet toggle in one horizontal row, shows latest five results before internal scroll, and uses complete result wording such as `won by 42 runs` / `lost by 5 wickets`.
- Season by Round verified premiership/finals wins are detected by exact `match_id` from `data/processed/hall_of_fame/premiership_wins.csv` and get subtle gold row/header trophy treatment. Mobile rows keep the scorecard link on its own clean line to avoid overlap.
- Season by Round Best Batter/Best Bowler combine all FVCC innings for the same player in a match, then display both innings performances in order, for example `20 & 24*` or `3-33 & 2-42`. Best Batter ranks by combined runs, then highest individual innings; Best Bowler ranks by combined wickets, then combined runs conceded, then best single-innings figure. Compact names may use first names on narrow layouts. Missing match-level data should render the compact empty state, not fake rows.
- Current data refresh state: `scripts/refresh_data.py` refreshes aggregate/public data, the current-season match-centre scope, and deploy-safe Season Overview, Player Profile, and Hall of Fame summaries. Winter 2026 match-centre data now includes R1 and R2, and Season by Round should show R2 first.
- Mobile Season by Round grade/team controls use compact wrapped rectangular pills inside the visual, avoiding the oversized capsule style that wrapped long grade names awkwardly.
- Shared folder-tab component: Season by Round grade/team selection, Milestone main view selection, and Player Profile Career Breakdown dimension selection now use a reusable `st.session_state` folder-tab pattern attached to the card/visual. It does not use query-param links and must not reset route/player/page state.
- Player Profile Career Breakdown now includes a `Captain` view. It reads deploy-safe `performance_breakdown_by_dimension.csv` rows when `dimension=Captain` exists; otherwise it shows `Captain breakdown is not available for this player yet.` Future Player Profile summary rebuilds can emit Captain rows only when reliable club-side captain fields exist in match exports.
- Batting / Bowling / Fielding controls remain the existing pill-style segmented controls and are left-aligned inside the Career Breakdown card; they are intentionally not folder tabs.
- Review-only wireframes for compact Recent Form and Season by Round remain under `docs/wireframes/` as design references; production implementation is local only until Preet confirms. Do not push.

## Current Opponent Name Normalization

- Opponent labels now use a shared club-name normalization helper so Player Profile opponent breakdowns, favourite opponent labels, standout context, and match-context labels can converge on clean club-level names.
- The helper maps bare names and `CC` variants to full `Cricket Club` names where reviewed, for example `Donath` -> `Donath Cricket Club`, `Holy Trinity` -> `Holy Trinity Cricket Club`, `Northern Socials` variants -> `Northern Socials Cricket Club`, and `Olympic Colts` variants -> `Olympic Colts Cricket Club`.
- Reviewed Darebin variants including `Darebin Chargers`, `Darebin Chargers RP`, and `Darebin Chargers Red` now map to `Darebin Chargers Cricket Club`; keep `Darebin Northern Riders Cricket Club` separate.
- Reviewed club merges now also map `West Preston Sharks Cricket Club` -> `West Preston Cricket Club`, `Strathewen Cougars Cricket Club` -> `Strathewen Cricket Club`, `Bellfield Bulls Cricket Club` -> `Bellfield Cricket Club`, and `Cobras Cricket Club` -> `Reservoir Cobras Cricket Club`.
- `CC` should display as `Cricket Club`, repeated `Cricket Club` wording should be removed, and team suffixes such as `1st XI`, `2nd XI`, `OD`, `T20`, colours, and `#1/#2` should not leak into club-level opponent labels.
- Do not over-merge similarly named clubs unless explicitly mapped. Keep distinct clubs such as Bellfield / Bellfield Rocketz, Darebin Chargers / Deccan Chargers, Lalor / Lalor Warriors, Reservoir Cobras / Reservoir Mayston, and Preston Footballers / Preston Baseballers / Preston Druids / Preston YCW District / Preston Himalayan separate.
- Local review CSVs for raw versus normalized opponent and ground names live under ignored `data/processed/experimental/name_normalization_audit/` and must not be committed unless Preet explicitly approves.

## Current Ground Name Normalization

- Ground labels use the same shared normalization module as opponent labels so Player Profile ground breakdowns, favourite ground labels, and match-context venue labels display clean venue-level names.
- Reviewed explicit merges include `J.C Donath Reserve (East)`, `J.C. Donath Reserve (Central)`, and `J.C. Donath Reserve (West)` -> `J.C. Donath Reserve`.
- Reviewed explicit merge: `Chelsworth Park North` and `Chelsworth Park South` -> `Chelsworth Park`.
- Reviewed explicit merge: `Shelley Park (Heidelberg Heights)` -> `Shelley Park`.
- Initial punctuation is normalized for reviewed venues such as `C.H. Sullivan Memorial Park`, `H.L.T. Oulten Park`, `H.P. Zwar Park`, `T.W. Blake Park`, `J.E. Moore Park`, `I.W. Dole Reserve`, and `W. Ruthven VC Reserve`.
- Reviewed venue-level cleanup strips obvious appended oval/surface suffixes from known venues, for example `C.H. Sullivan Memorial Park Oval #1 East` and `C.H. Sullivan Memorial Park #2 West` -> `C.H. Sullivan Memorial Park`.
- Do not generally merge directional venue names unless Preet has reviewed and explicitly mapped them.

## 2. Current App Pages / Navigation

The app has four main pages:

1. Hall of Fame
   - All-time club records.
   - All-time leaders.
   - Record holders.
   - Iconic performances.
   - Greatest Individual Seasons.
   - Detailed All-Time Records.

2. Season Overview
   - Season-specific stats.
   - Season and team/grade slicers.
   - Season Standouts.
   - Biggest Improvers.
   - Leaders by Team/Grade.
   - Detailed Season Stats.

3. Milestone
   - Active-player milestone tracking.
   - Milestone Watchlist.
   - Exclusive Club.
   - Active players only: players who appeared in the last 3 seasons.

4. Player Profile
   - Search/select player.
   - Player summary.
   - Classification badges.
   - Career Highlights.
   - Player vs Peers.
   - Season Trends.
   - Performance Breakdown.
   - Career Overview.
   - Player DNA.
   - Milestone Watch.

Navigation rules:

- Desktop/laptop must always show the custom persistent left sidebar.
- Desktop users should not rely on Streamlit's native sidebar toggle.
- Mobile should use the current mobile navigation selector/dropdown.
- Do not change the mobile navigation experience unless explicitly requested.
- Page order should remain:
  1. Hall of Fame
  2. Season Overview
  3. Milestone
  4. Player Profile

## 3. Design Direction

- Overall feel: premium modern sports analytics dashboard.
- Theme: white cards, dark navy text, and active-club accents. FVCC now uses shirt-inspired navy, maroon, and gold rather than the legacy purple-first palette.
- Avoid heavy gold styling. Normal medal emojis and rank badges are fine, but do not make the UI gold-themed.
- Hall of Fame can feel ceremonial, but it should remain restrained.
- Mobile should be clean, readable, and not cramped.
- Keep UI polished without over-designing.
- Emojis are allowed sparingly and tastefully in headings.
- Tables and charts should use light/white backgrounds on both desktop and mobile.
- Desktop sidebar must remain visible.
- Mobile nav card must not hide or overlap the "Choose a page" label.

Creator credit/footer text:

```text
App created by
Siddhanth Chaurasiya |
Preet Kaur
For feedback/enquiries:
siddhanthchaurasiya
@gmail.com
```

Footer placement:

- Desktop: sidebar/footer area.
- Mobile: bottom of each page, not inside the navigation card.
- Keep it compact, professional, and subtle.

## 4. Data Source / Local Backup / Caching

- PlayCricket Australia is the source data provider.
- Historical multi-season data is stored locally.
- The app should prefer local processed data over live API calls.
- Avoid hitting the PlayCricket API repeatedly.
- Raw source data should never be overwritten.
- Processed data can be regenerated from raw data plus mapping files.
- Use `st.cache_data` for heavy local loading and aggregation.
- Hall of Fame and Detailed All-Time Records can feel slow if heavy all-time calculations are not cached.
- Cache data computations, not UI rendering.
- If cached dataframes are modified later, copy them first.
- Keep cache invalidation simple, usually through file modified timestamps or existing metadata version helpers.

## 5. Player Identity / Duplicate Profile Logic

Some players have multiple PlayCricket profiles or name variants. The app uses canonical identity fields so records and summaries are merged correctly while keeping raw data auditable.

Canonical fields to preserve/use:

- `raw_player_id`
- `raw_player_name`
- `canonical_player_id`
- `canonical_player_name`

Rules:

- Raw PlayCricket profile data must remain untouched.
- Actual merges should come from manual alias/mapping files, not unreviewed fuzzy auto-merging.
- Exact confirmed cases can be supported, but keep merges auditable and reversible.
- Hall of Fame, Milestone, Player Profile, Player vs Peers, records, and all-time summaries should use canonical identity.
- Derived stats after merging must be recalculated from raw totals, not averaged from already-calculated averages.

Manually confirmed merges to preserve:

- Baurel D'Mello + Baurel Dmello -> Baurel D'Mello / `baurel_dmello`
- Kalpesh Patel + Kalpeshkumar Patel + duplicate Kalpeshkumar Patel profiles -> Kalpeshkumar Patel / `kalpeshkumar_patel`

Important mapping/audit files:

- `data/player_aliases.csv`
- `data/manual_player_merges.csv`
- `data/player_duplicate_audit.csv`
- `data/player_identity_summary.csv`

## 6. Team / Grade Cleaning Logic

Recent seasons usually have cleaner team names and grade names. Older seasons often duplicate competition/grade text in both fields.

Messy examples:

- `NMCA - Les Kemp Shield - "E" Grade (Les Kemp Shield - "E" Grade)`
- `NMCA - Jack Quick Shield - NMCA - Jack Quick Shield`
- `NMCA - Jack Quick Shield (Jack Quick Shield)`

Use the reusable helper in `src/utils/team_grade.py` for display normalization. Important helpers include:

- `clean_grade_name`
- `clean_team_name`
- `is_real_team_name`
- `names_are_equivalent`
- `build_team_grade_display`
- `apply_team_grade_display_columns`
- `grade_sort_key`

Display fields added/used by the helper:

- `raw_team_name`
- `raw_grade_name`
- `clean_team_name`
- `clean_grade_name`
- `canonical_team_label`
- `canonical_grade_label`
- `team_grade_display`

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

Preferred grade order:

1. Jika Shield
2. Jack Quick Shield
3. Jack Kelly Shield
4. B Grade
5. C Grade
6. D Grade
7. E Grade
8. F Grade
9. G Grade
10. Any unknown/other grades alphabetically

Apply this cleaning and ordering anywhere grade/team details are displayed:

- Season Overview team/grade slicer.
- Season Overview Leaders by Team/Grade.
- Player Profile Grades Played.
- Player Profile Grade Breakdown.
- Hall of Fame performance cards where grade/team appears.
- Any tooltip/label/card that uses team/grade names.

Audit file:

- `data/team_grade_display_audit.csv`

## 7. Hall of Fame Page Details

Header:

```text
Hall of Fame 🏆
Fiji Victorian Cricket Club
The players who shaped the club's history.
Players with multiple PlayCricket profiles are merged into one profile.
```

Header rules:

- Club name should be bold, purple, and close to the main header.
- Merge note should be italic.

KPI cards:

- Seasons Analysed
- Matches Recorded
- Players Scanned

Current section headings:

- All-Time Leaders 👑
- Iconic Performances 🌟
- Record Holders 📘
- Greatest Individual Seasons 🎖️
- Detailed All-Time Records 📊

Record Holders current code order:

1. Most 100s
2. Most 50s
3. Most 4s
4. Most 6s
5. 5 Wicket Hauls
6. Most Maidens
7. Ducks

Note: one older prompt mentioned "Most Runs" in this list, but current code uses "Most 100s" as the first Record Holders card. Treat the current code as final unless the user asks to change it.

Record Holders layout:

- Desktop should show 4 cards per row.
- Mobile remains responsive and compact.

Detailed All-Time Records:

- Batting/Bowling/Fielding views.
- "First Season" is displayed as "Debut Season".
- Bowling table includes Overs.
- Maidens appears immediately next to Wickets.
- 10-wicket match field is displayed as `10WM`.
- Batting includes 4s and 6s.
- Table filters/expander have been removed.
- Tables should remain light/white on mobile and desktop.

Iconic Performances:

- Previously called Match-Winning Performances.
- Highest-score tie logic should prefer not-out scores where relevant.

Greatest Individual Seasons:

- Shows best batting season and best bowling season.
- Include matches in both batting and bowling cards.
- Batting card removes innings and includes 0s after 6s.
- Bowling card includes 10WM when available.

## 8. Season Overview Page Details

Navigation label:

- `Season Overview`

Header structure:

```text
Season Overview 📊
Fiji Victorian Cricket Club
Track team performance, player leaders, and season-by-season club trends.
Showing data for [season] • [team/grade scope]
```

Header rules:

- Mirrors Hall of Fame header structure.
- Club name is bold and purple.
- "Showing data..." line is dynamic and non-bold.
- It should appear only once.

Filters:

- Season and Team/Grade slicers are simple and non-sticky.
- Team/Grade slicer must use cleaned grade/team labels, not duplicated raw strings.
- Keep `All teams - Whole club` as the default option.

Sections:

- Season Standouts ✨
  - Subtext: `Top performers across the selected season and team scope.`
- Biggest Improvers 📈
  - Subtext: `Players with the strongest improvement compared to previous season.`
- Leaders by Team/Grade 👥
  - Subtext: `Top performers and key totals by team/grade.`

Detailed Stats source rules:

- Runs, Innings, Batting Average, HS, 30s, 50s, 100s, ducks, 4s, and 6s may use scorecard/aggregate sources.
- Bat SR must be calculated only from verified ball-by-ball batting innings: ball-by-ball runs divided by ball-by-ball balls faced from the same innings.
- Batting Dot Ball % must be calculated only from verified ball-by-ball deliveries: batter dot balls divided by ball-by-ball balls faced.
- Any future batting metric that needs delivery-level data must also use ball-by-ball only. Examples: boundary percentage/rate from balls, balls per boundary, balls per dismissal, and similar quality/rate metrics.
- Never mix all-scorecard totals with ball-by-ball denominators.
- If verified ball-by-ball data is missing for the selected season/team scope, delivery-based metrics should show blank/`N/A`, not `0.0`.
- This rule matters after every weekly data refresh because new scorecard totals can appear before or without usable ball-by-ball detail.

Biggest Improvers logic:

- Cards:
  - Biggest Run Improvement
  - Biggest Wickets Improvement
- Current/Previous labels include units, e.g. `367 runs`, `24 wickets`.
- Minimum 8 matches in current season and 8 matches in previous season.
- Respects selected season and selected team/grade scope.
- Summer seasons compare to the previous Summer season.
- Winter seasons compare to the previous Winter season.
- Uses canonical player identity.
- Uses cleaned grade/team fields where required.
- If no player qualifies, show a clean empty state.

Debug file:

- `data/debug_biggest_improvers.csv`

Detailed Stats:

- Batting/Bowling/Fielding tabs.
- Table filters/expander removed.
- Team column removed.
- Bowling view:
  - Runs column removed.
  - Mdns/Maidens appears immediately after Wickets.
  - Suggested order: Player, M, Overs, Wickets, Mdns, Bowl Avg, Economy, Bowl SR, BBI, 4W, 5W.
- Player names can wrap to two lines on mobile.
- Keep numbers numeric/sortable.

## 9. Milestone Page Details

Navigation label:

- `Milestone`

Header:

```text
Players closing in on major club milestones 🎯
Fiji Victorian Cricket Club
Showing active players only — players who have appeared for FVCC in the last 3 seasons.
```

Rules:

- Subtitle is non-bold and muted.
- No cricket emoji in the subtitle.
- Active players only means players who appeared in the last 3 seasons.
- Player eligibility should use canonical identity.

Sections:

- Milestone Watchlist 🎯
- Exclusive Club 💪

Other notes:

- Dismissals milestone visual was removed.
- Keep existing milestone cards and logic unless explicitly requested.

Potential future improvements:

- Closest Milestone hero card.
- Talking Points for the Next Game.
- Tiered Exclusive Club.
- "Likely soon" / "within reach" milestone labels.

## 10. Player Profile Page Details

Header:

```text
Player Spotlight 🏏
Fiji Victorian Cricket Club
Search any player and explore their career story across seasons, teams, and formats.
```

Search card:

- Helper text: `Start typing a name to find a player from club records.`
- Helper text should sit close under the selector.

Player summary card order:

1. PLAYER PROFILE
2. Player Name
3. Player Summary
4. Grades Played
5. Career Span
6. Classification badges

Rules:

- Player Summary is regular/non-bold and muted.
- Grades Played uses cleaned, deduplicated grade labels only.
- Grade list follows the standard grade order.
- Career span uses full season labels, e.g. `Summer 2006/07 – Summer 2025/26`.
- Winter seasons should be ordered correctly relative to Summer seasons.

Current section headings/emojis:

- Player Spotlight 🏏
- Career Snapshot 📌
- Career Highlights 🌟
- Player vs Peers 📊
- Season Trends 📈
- Season History 📅
- Grade Breakdown 🧭
- Career Overview 🧩
- Milestone Watch 🎯

Tables:

- `Season-by-Season Performance` was renamed to `Season History`.
- `Grade-wise Performance` was renamed to `Grade Breakdown`.
- Table filters/expanders removed.
- Total rows removed from Season History and Grade Breakdown.
- First column should remain sticky/frozen on mobile:
  - Season column for Season History.
  - Grade column for Grade Breakdown.
- Tables should stay light/white on mobile and desktop.
- Keep tables compact and sortable.

Career Overview:

- Batting order: Matches, Runs, Average, 4s, 6s, 0s, HS.
- Bowling includes Strike Rate, Maidens, and BBI.

Career Highlights:

- Highest Run Maker at Club.
- Highest Run Maker in Grade.
- Highest Wicket Taker at Club.
- Highest Wicket Taker in Grade.
- Include season/grade details where relevant.
- Do not show "Tied leaders included".

Milestone Watch:

- Dismissals milestone is removed.

Future enhancement:

- Make player names across the app clickable so they open Player Profile for the selected `canonical_player_id`.

## 11. Player Profile Classification / Tag System

Source of truth in code:

- `src/ui/layout.py`
- Main functions:
  - `player_role_badges`
  - `select_profile_badges`
  - `player_profile_insight`
  - `season_standout_label`
  - `base_badge_label`

Display:

- Current code returns all selected badge candidates in priority order; there is no display cap in `select_profile_badges`.
- Badges should wrap neatly without overlap.
- Priority still matters for ordering.
- Fallback badges:
  - Club Contributor if no other badge applies and Matches >= 20.
  - Emerging Player if no other badge applies and Matches < 20.

Current badge logic:

| Badge | Current logic |
| --- | --- |
| Club Legend | Matches >= 200 OR Runs >= 4000 OR Wickets >= 250 |
| Genuine All-rounder | Runs >= 1000 AND Wickets >= 100 |
| All-round Contributor | Matches >= 30 AND Bat Avg > 12 AND Runs >= 300 AND Wickets >= 30; not shown if Genuine All-rounder applies |
| Upcoming Star | Matches >= 20 AND Matches < 50 AND (Bat Avg > 20 OR (0 < Bowl Avg < 20 AND Wickets >= 15)) |
| Star Batter | Matches >= 30 AND Bat Avg > 25 |
| Star Bowler | Matches >= 30 AND Wickets >= 30 AND 0 < Bowl Avg < 20 |
| Run Machine | Runs >= 2000 OR (Runs per match >= 25 AND Matches >= 50) |
| Dependable Batter | Matches >= 30 AND Bat Avg > 18 AND Star Batter is not applied |
| Wicket Taker | Matches >= 20 AND Wickets per match > 1 |
| Golden Arm | Matches >= 30 AND Wickets per match < 0.60 AND Wickets >= 15 AND 0 < Bowl Avg < 25 |
| Partnership Breaker | Overs > 150 AND Wickets >= 30 AND 0 < Bowling SR < 35 |
| Economy Controller | Overs > 150 AND 0 < Economy < 3.5 AND (Wickets >= 30 OR Matches >= 30) |
| Big Hitter | Matches >= 30 AND 6s per match > 0.3 |
| Values His Wicket | Matches >= 20 AND Balls per dismissal >= 30 |
| Gap Finder | Matches >= 30 AND 4s per match > 2 |
| Quick Scorer | Matches >= 20 AND reliable Bat SR >= 90 AND reliable balls faced >= 125 AND reliable runs >= 125 |
| Boundary Maker | Matches >= 20 AND boundaries per match > 2.5 AND Big Hitter is not applied AND Gap Finder is not applied |
| Workhorse | Overs >= 250 AND Matches >= 30 |
| Safe Hands | Stumpings <= 0 AND Matches >= 20 AND dismissals per match > 0.4 |
| Keeper Impact | Stumpings > 0 |
| Season Standout | Any club/grade season leader achievement count > 0; label becomes `Season Standout x N` when count > 1 |
| Milestone Maker | Runs >= 1000 OR Wickets >= 100 OR Matches >= 100, and Club Legend is not applied |
| Club Veteran | Matches >= 100 and Club Legend is not applied |
| Mr Consistent | At least 3 seasons with 200+ runs OR at least 3 seasons with 15+ wickets |
| Club Contributor | Fallback for Matches >= 20 |
| Emerging Player | Fallback for Matches < 20 |

Reliable batting strike rate rule:

- Player classification uses reliable batting components from `Summer 2024/25` onward in `reliable_batting_components`.
- Do not use older strike-rate data for Quick Scorer or strike-rate-derived player labels.

Summary logic:

- Only one summary sentence is displayed.
- `player_profile_insight` derives the sentence from the selected badge set.
- It combines legacy impact with playing identity where possible.

Current summary priority examples:

- Club Legend + Genuine All-rounder/All-round Contributor: `Long-serving club figure with major contributions across bat and ball.`
- Club Legend + batting/style: `Long-serving club figure with a major batting footprint across the record book.`
- Club Legend + bowling: `Long-serving club figure with sustained bowling impact across seasons.`
- Club Legend + fielding/keeping: `Long-serving club figure with strong fielding impact across the available records.`
- Club Legend fallback: `Long-serving club figure with a major footprint across the record book.`
- Genuine All-rounder: `Strong two-skill contributor across bat and ball.`
- All-round Contributor: `Contributes meaningfully with both bat and ball.`
- Upcoming Star: `Early-career player already showing strong signs of future impact.`
- Star Batter: `High-impact run-maker with strong batting returns across seasons.`
- Run Machine: `Consistent run scorer with a strong footprint across seasons.`
- Dependable Batter: `Reliable batting contributor with consistent returns across the record book.`
- Big Hitter: `Boundary-focused batter with a strong six-hitting profile.`
- Gap Finder / Boundary Maker: `Finds the boundary regularly through consistent four-hitting.`
- Values His Wicket: `Patient batter who spends time at the crease and values his wicket.`
- Quick Scorer: `Tempo-setting batter with strong recent scoring rate.`
- Star Bowler: `High-impact bowler with strong wicket-taking and average profile.`
- Partnership Breaker: `Regular wicket threat who can break games open with the ball.`
- Wicket Taker: `Consistently finds wickets across the available club records.`
- Golden Arm: `Makes an impact with the ball despite limited bowling volume.`
- Economy Controller: `Disciplined bowler who keeps scoring rates under control.`
- Workhorse: `Trusted to carry a heavy bowling workload across seasons.`
- Mr Consistent: `Delivers across seasons, not just in one standout year.`
- Safe Hands: `Reliable fielding contributor across the available records.`
- Keeper Impact: `Wicketkeeping contributor with impact behind the stumps.`
- Season Standout: `Has produced standout season-level performances in the club record book.`
- Milestone Maker: `Has crossed major club milestones across the available records.`
- Club Veteran: `Experienced club contributor with a long record across seasons.`
- Emerging Player: `Early career profile building across the available club records.`
- Fallback: `Club contributor across the available records.`

Audit file to keep updated:

- `docs/player_profile_tags_audit.md`

## 12. Player vs Peers Logic

Source of truth in code:

- `render_player_peer_comparison`
- `get_player_peer_comparison`
- `player_peer_grade_scope`
- `filter_peer_scope`
- `aggregate_peer_batting`
- `aggregate_peer_bowling`
- `build_peer_metric_rows`
- `peer_metric_status`
- `export_player_vs_peers_debug`

Section:

- Title: `Player vs Peers 📊`
- Current subtitle: `Compared against players from the same seasons and grades.`

Peer group:

- Dynamic per selected player.
- Uses canonical player identity.
- Compares the selected player against peers from:
  1. the same seasons the selected player appeared in, and
  2. the same cleaned grade/team-grade contexts the selected player appeared in.
- Uses `canonical_grade_label` first, then `team_grade_display`, then cleaned/canonical team fallback.
- If grade metadata is incomplete and no same-grade rows match, the code falls back to same-season peers instead of hiding the section.

Current Player vs Peers metrics:

Batting:

1. Batting Avg
   - Player: total runs / total outs.
   - Peer avg: pooled peer runs / pooled peer outs.
   - Higher is better.
2. Strike Rate
   - Uses Winter 2025 onward only.
   - Player: reliable runs * 100 / reliable balls faced.
   - Peer avg: pooled reliable peer runs * 100 / pooled reliable peer balls faced.
   - Higher is better.
3. Balls per Dismissal
   - Player: verified ball-by-ball balls faced / verified BBB dismissals from those same covered innings only.
   - Peer avg: pooled verified ball-by-ball peer balls faced / pooled verified BBB dismissals in the same peer scope.
   - Higher is better.
   - Non-BBB scorecard innings must be excluded entirely.
   - Missing BBB coverage should show `N/A`, not `0` or a mixed-source low value.
4. Boundary Rate
   - Current code: (4s + 6s) / innings.
   - Peer avg: pooled peer boundaries / pooled peer innings.
   - Higher is better.
5. Innings per Duck
   - Current code: innings / ducks.
   - Peer avg: pooled peer innings / pooled peer ducks.
   - Higher is better.
   - If ducks = 0, avoid divide-by-zero and show unavailable/neutral.

Bowling:

1. Bowling Avg
   - Player: runs conceded / wickets.
   - Peer avg: pooled peer runs conceded / pooled peer wickets.
   - Lower is better.
2. Bowling SR
   - Player: balls bowled / wickets.
   - Peer avg: pooled peer balls bowled / pooled peer wickets.
   - Lower is better.
3. Economy Rate
   - Player: runs conceded * 6 / balls bowled.
   - Peer avg: pooled peer runs conceded * 6 / pooled peer balls bowled.
   - Lower is better.
4. Overs per Maiden
   - Player: overs / maidens.
   - Peer avg: pooled peer overs / pooled peer maidens.
   - Lower is better because maidens are more frequent.
5. Overs per Extra
   - Player: overs / (wides + no-balls).
   - Peer avg: pooled peer overs / pooled peer extras.
   - Higher is better because extras are less frequent.
6. Unassisted Wicket %
   - Player: bowlingWicketsUnassisted * 100 / wickets.
   - Peer avg: pooled peer unassisted wickets * 100 / pooled peer wickets.
   - Higher is treated as notable/better for this MVP.

Average rule:

- Avoid average-of-averages.
- Derived peer averages are pooled from underlying totals.
- Min/max values remain peer-player-level min/max values.
- No peer volume filters are applied yet.

Label logic:

- If player/peer values are missing, zero, NaN, or invalid, show neutral/no comparison.
- Higher-is-better metrics:
  - If player value > peer average: `Better than avg`
  - Else if player value >= peer average * 0.90: `Around avg`
  - Else: `Worse than avg`
- Lower-is-better metrics:
  - If player value < peer average: `Better than avg`
  - Else if player value <= peer average * 1.10: `Around avg`
  - Else: `Worse than avg`
- Status colors:
  - Better than avg = green.
  - Around avg = grey/neutral.
  - Worse than avg = soft red/pink.

Visual:

- Legend:
  - Active club-colour dot = player.
  - Grey marker = peer average.
- Range line shows lowest to highest peer value.
- Cards use active club-colour / green accent headings.
- Mobile must remain readable.

Audit/debug files:

- `docs/player_vs_peers_calculation_audit.md`
- `data/debug_player_vs_peers.csv`

## 13. Deployment / Git Workflow

- GitHub repo: https://github.com/sidchaurasiya/the-scorebook-fvcc.git
- Branch: `main`
- Streamlit Cloud auto-deploys from GitHub `main` after push.
- Sometimes the deployed app may need Manage app -> Reboot app or cache clearing.
- Browser refresh alone may not be enough if Streamlit server/cache is stale.
- Local run:

```bash
cd "/Users/preetkaur/Documents/Codex/2026-04-24/you-are-an-expert-full-stack"
./.venv-app/bin/streamlit run app.py --server.port 8502
```

- Git auth in Codex terminal may fail with:

```text
fatal: could not read Username for 'https://github.com': Device not configured
```

- If terminal auth fails, push through GitHub Desktop.
- Always commit locally before pushing.
- User reviews locally at http://localhost:8502/ before push.

## 14. Known Issues / Debug Notes

- Desktop sidebar once disappeared on deployed desktop. It must remain persistent on desktop.
- Mobile navigation works and should not be broken.
- Streamlit can serve stale code if the app server started before latest changes; restart Streamlit after code changes.
- If features appear missing locally after commit, restart the local Streamlit server, not just the browser.
- Some mobile tables/charts previously rendered black backgrounds; keep all tables/charts light/white.
- Season Overview sticky/persistent filter bar caused repeated issues; it now uses simple non-sticky slicers.
- Debug CSVs can update when app logic runs; check git status after validation.
- The context window reached 91%, so this handover is critical for continuity.

## 15. Future Enhancements Log

Navigation/profile:

- Link player names across the app to Player Profile using `canonical_player_id`.
- Shareable player profile links.
- Downloadable player card image.
- Compare players.
- Records near me for selected player.
- Timeline / career story view.

New pages/features:

- Team / Grade Profile page.
- Awards page.
- Club season report export.
- Data quality/admin page.

Milestones/social:

- Milestone social media talking points.
- Closest Milestone hero card.
- Likely soon / within reach labels.
- Tiered Exclusive Club.

Analytics/tracking:

- Use URL query params such as `?club_ref=club_0001`.
- Log anonymized app usage to Google Sheets or Supabase.
- Do not collect names/emails silently.
- Optional enquiry form can collect name/email with explicit consent.

Classification/tag future review:

- Golden Arm.
- Upcoming Star.
- Values His Wicket.
- Genuine All-rounder.
- Workhorse.
- Run Machine.
- Mr Consistent.

Advanced analytics ideas:

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

## 16. Files / Docs To Maintain

Important docs:

- `docs/project_handover.md`
- `docs/multi_club_scalability_plan.md`
- `docs/analytics_tracking.md`
- `docs/analytics_setup.md`
- `docs/player_profile_tags_audit.md`
- `docs/player_vs_peers_calculation_audit.md`

Identity and cleaning files:

- `data/player_aliases.csv`
- `data/manual_player_merges.csv`
- `data/player_duplicate_audit.csv`
- `data/player_identity_summary.csv`
- `data/team_grade_display_audit.csv`

Debug/audit output:

- `data/debug_biggest_improvers.csv`
- `data/debug_player_vs_peers.csv`

Important source areas:

- `app.py`
- `src/ui/layout.py`
- `src/ui/theme.py`
- `src/utils/team_grade.py`
- Player identity helpers and cached data-loading helpers in `src/`

## 17. Multi-Club Refresh / Export Status

Phase 6 adds club-aware dry-run/reporting to match-centre refresh/backfill workflows without changing visible app behaviour. Phase 6.5 generalizes match-centre club ownership field names while preserving FVCC compatibility.

- Active club remains FVCC by default, or via `CLUB_ID=fvcc`.
- Runtime data is preferred from `clubs/fvcc/data/processed/...` with legacy `data/...` fallback.
- `scripts/refresh_data.py --club <club_id>` now reads `club.playcricket_club_id` from config and writes aggregate processed CSVs to `clubs/<club_id>/data/processed/` by default.
- `scripts/refresh_data.py --club <club_id> --dry-run` makes no network requests and no writes; it reports the PlayCricket club ID, processed output directory, raw/cache/metadata paths, planned aggregate CSV outputs, and next deploy-safe rebuild command.
- `scripts/refresh_match_centre_data.py --club <club_id> --dry-run` makes no network requests and no writes; scope args are optional in dry-run, and the report shows current legacy raw/generated match-centre output paths.
- `scripts/backfill_match_centre_available.py --club <club_id> --dry-run` uses club-aware `teams.csv`, `seasons.csv`, and `players.csv`, keeps aliases global, and reports scoped season/team counts without fetching or writing.
- `scripts/build_match_centre_milestones.py --club <club_id> --dry-run` reports the config PlayCricket ID and generated match-centre milestone output paths.
- `scripts/refresh_club_outputs.py --club <club_id> --dry-run` now lists the future weekly sequence: aggregate refresh, scoped match-centre refresh, all-available backfill, then deploy-safe summary rebuild.
- Match-centre ownership code now prefers `club_team_id`, `club_team_name`, and `is_club_player`.
- Existing FVCC generated files remain supported through fallback from `fvcc_team_id`, `fvcc_team_name`, and `is_fvcc_player`.
- `scripts/check_match_centre_ownership.py --club fvcc` is a read-only diagnostic for old/new ownership columns, fallback-derived team IDs/names, and player ownership counts.
- Use `--legacy-output` only when an explicit compatibility write to legacy `data/processed/` is required.
- Deploy-safe output builders now support `--club`, `--dry-run`, and explicit `--legacy-output`.
- Hall of Fame exports write to `clubs/<club_id>/data/processed/hall_of_fame/` by default.
- Season Overview exports write to `clubs/<club_id>/data/processed/season_overview/` by default.
- Player Profile exports write to `clubs/<club_id>/data/processed/player_profile/` by default.
- Raw JSON backups, cache files, timestamped backups, root-level player identity mapping/audit files, full match-centre raw/generated folders, and experimental folders remain legacy/global and must not be committed unless explicitly approved.

Safe planning commands:

```bash
./.venv-app/bin/python scripts/refresh_data.py --club fvcc --dry-run
./.venv-app/bin/python scripts/refresh_match_centre_data.py --club fvcc --dry-run
./.venv-app/bin/python scripts/backfill_match_centre_available.py --club fvcc --dry-run
./.venv-app/bin/python scripts/build_match_centre_milestones.py --club fvcc --dry-run
./.venv-app/bin/python scripts/refresh_club_outputs.py --club fvcc --dry-run
```

Future weekly order: aggregate refresh with `scripts/refresh_data.py --club fvcc`, controlled match-centre refresh/backfill, deploy-safe summaries with `scripts/refresh_club_outputs.py --club fvcc`, club config check, local smoke test, then commit only club-specific production processed/deploy-safe outputs and relevant code/docs.

Phase 4.5 validation: `scripts/refresh_club_outputs.py --club fvcc` ran from existing local inputs only, fetched no external data, and regenerated all deploy-safe summaries deterministically. All 19 club-specific Hall of Fame, Season Overview, and Player Profile CSVs matched their previous row counts and SHA-256 hashes, so no CSV changes were committed.

Phase 6.5 deliberately leaves raw/full match-centre data in ignored legacy folders: `data/raw/match_centre/`, `data/processed/match_centre/`, and `data/processed/experimental/`. Production pages should continue to depend only on deploy-safe summaries under `clubs/<club_id>/data/processed/...`. Legacy `fvcc_*` column names may still appear in deploy-safe CSV schemas and UI code for compatibility, but new parser/exporter logic should use the neutral `club_*` fields first. Before a second club relies on match-centre features, review club-specific team ownership mappings and raw/generated folder scoping.

Positive-response onboarding update:

- Configured and aggregate-refreshed six pilot clubs: `reynella`, `ashwood`, `glen-waverley-hawks`, `plenty`, `georges-river-district`, and `southside-east-caulfield`.
- Glen Waverley Hawks reused the existing local folder and was updated to the current structure.
- Georges River District uses folder id `georges-river-district`; the official PlayCricket identity is Georges River Cricket Club.
- Every non-FVCC pilot config has `allow_legacy_fallback: false`, `mapping_dir: clubs/<club_id>`, and all runtime processed output under `clubs/<club_id>/data/processed/`.
- Starter mapping files are club-local and header-only. Do not copy FVCC aliases, team/grade mappings, opponent mappings, or ground mappings into other clubs.
- Aggregate processed CSVs and `metadata.json` were written for each pilot club. Match-centre refresh/backfill was not run and still requires explicit approval per club.
- Review packs exist under `data/processed/experimental/<club_id>/review_pack/`; keep them ignored unless Preet explicitly approves committing them.
- Review packs now include `safe_auto_merge_candidates.csv` and `manual_duplicate_review_candidates.csv`. These are review-only duplicate-player proposals, not applied mapping changes.
- Safe auto-merge proposals require strict-normalized exact names, no season overlap across batting/bowling/fielding rows, and no match overlap where match IDs are available. Strict normalization only handles case, spacing, accents, and punctuation/special characters; it does not fuzzy-match, reorder names, or drop middle names.
- Same-season duplicate names, similar-but-not-exact names, initials/name-expansion differences, and uncertain cases remain manual review only.
- Non-FVCC duplicate review uses each club's own aggregate processed data and club-local mapping paths. Do not use FVCC mappings for any pilot club.
- Browser smoke passed for Hall of Fame, Season Overview, Milestone, and Player Profile for each pilot club, with clean empty states for unavailable scorecard/ball-by-ball sections.
- GA4 remains shared through `GA4_MEASUREMENT_ID` unless a later config explicitly overrides it. Event parameters should include `club_id` and `club_name` as custom dimensions.

Pilot match-centre/backfill update:

- Controlled match-centre/backfill completed for `southside-east-caulfield`, `glen-waverley-hawks`, `ashwood`, `plenty`, `reynella`, and `georges-river-district`.
- Runtime deploy-safe outputs were regenerated under each club's `clubs/<club_id>/data/processed/` folders for Hall of Fame, Season Overview, and Player Profile.
- Raw/full match-centre outputs remain ignored under `data/raw/match_centre/` and `data/processed/match_centre/`; regenerated review packs remain ignored under `data/processed/experimental/<club_id>/review_pack/`.
- FVCC was not refreshed or backfilled during the pilot-club run. It was smoke-tested only as a regression check and passed.
- All six pilot apps smoke-passed Hall of Fame, Season Overview, Season by Round, Milestone, Player Profile, and Recent Form with no FVCC data leakage, traceback, visible `NaN`/`None`, or internal IDs.
- Verified ball-by-ball coverage now exists for every pilot club, but coverage is partial by source availability. Missing ball-by-ball metrics must continue to render as `N/A`, blank, or clean empty states, not fabricated `0.0`.
- Pilot premiership exports are header-only where no verified premiership evidence exists; do not fabricate premiership or captain data.
- Southside East Caulfield is the only non-FVCC pilot with approved safe duplicate merges applied. Duplicate proposals for the other pilot clubs remain review-only.
- Next review focus before client previews: team/grade mappings for all clubs, duplicate-player review for non-Southside clubs, and manual identity/naming review for Georges River District / official Georges River Cricket Club.
- Detailed counts and recommendations are in `docs/multi_club_match_centre_backfill_summary.md`.

Fastest Innings validation update:

- Fastest Innings is now explicitly verified-ball-by-ball only across the six pilot clubs and FVCC.
- The milestone builder uses per-delivery batter runs unless source cumulative batter runs validate cleanly. This prevents false records from malformed source cumulative fields that jump to final scores early.
- Deploy-safe fastest 50s below 9 balls and fastest 100s below 17 balls are excluded unless a trustworthy delivery sequence explicitly verifies them.
- Known false-looking examples were corrected from local ball-by-ball data: Plenty Geoffrey King 52 balls, Reynella Cameron Pannach 63 balls, and Georges River Christopher McArthur 35 balls.
- HOF Iconic Performances and Fastest Innings styling uses active club colour variables. FVCC now resolves those variables from its shirt-inspired navy `#24455F`, maroon `#A31952`, gold `#D4A83A`, and cool background `#F6F8FB` config palette.
- FVCC theme refresh: shared sidebar, navigation, links, folder tabs, pill toggles, KPI accents, progress bars, Hall of Fame surfaces, Season Overview, Milestone, Player Profile, mobile navigation, and custom HTML table links now resolve through active-club variables. Other clubs keep their own config palettes.
- Detailed audit notes are in `docs/multi_club_fastest_innings_audit.md`.

## 18. Final Instructions For Future Codex Session

Before making any future change:

1. Read `docs/project_handover.md`.
2. Check git status.
3. Create a checkpoint commit if there are uncommitted changes.
4. Keep changes scoped to the requested page/feature.
5. Run local app on port 8502 for review.
6. Commit locally after verification.
7. Do not push until Preet confirms.
