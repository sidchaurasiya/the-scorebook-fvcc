# Multi-Club Match-Centre Backfill Summary

Run date: 2026-05-26

Branch: `onboarding/multi-club-positive-responses`

Scope: six positive-response pilot clubs only. FVCC was not refreshed or backfilled; it was smoke-tested as a regression check only.

Raw/full match-centre data and review packs remain ignored and uncommitted under `data/raw/match_centre/`, `data/processed/match_centre/`, and `data/processed/experimental/`. Production/runtime files for the pilot clubs were rebuilt under `clubs/<club_id>/data/processed/`.

## Summary Table

| club_id | match-centre status | completed scorecards | ball-by-ball matches | ball events | deploy-safe files generated | app smoke | key warnings | recommended next action |
| --- | --- | ---: | ---: | ---: | --- | --- | --- | --- |
| `southside-east-caulfield` | Completed | 893 | 195 | 74,758 | HOF, Season Overview, Player Profile | Passed | Grade labels need light review; duplicate merges applied only for approved safe Southside groups | Client-preview candidate after final label check |
| `glen-waverley-hawks` | Completed | 3,475 | 698 | 241,113 | HOF, Season Overview, Player Profile | Passed | Historical grade labels are messy; duplicate risks remain review-only | Review team/grade mappings, then safe duplicate candidates |
| `ashwood` | Completed | 5,248 | 920 | 303,650 | HOF, Season Overview, Player Profile | Passed | Highest grade-label complexity; duplicate risks remain review-only | Review team/grade mappings before client preview |
| `plenty` | Completed | 3,214 | 503 | 200,539 | HOF, Season Overview, Player Profile | Passed | Junior and shield grade labels need mapping; duplicate risks remain review-only | Review duplicates and junior/team-grade labels |
| `reynella` | Completed | 3,110 | 572 | 244,422 | HOF, Season Overview, Player Profile | Passed | Sponsor, junior, T20, and association grade labels need mapping | Review safe duplicate groups and grade labels |
| `georges-river-district` | Completed | 2,604 | 295 | 155,573 | HOF, Season Overview, Player Profile | Passed | Largest identity pool; long historical data; official PlayCricket name is Georges River Cricket Club | Manual identity and grade review before client preview |

## Per-Club Detail

### Southside East Caulfield

- Seasons: 47; latest season: Winter 2026.
- Teams/grades: 115; players: 463.
- Match-centre matches found: 923 unique matches.
- Completed scorecards parsed: 893.
- Ball-by-ball coverage: 195 matches, 74,758 ball events.
- Parsed rows: 17,647 batting; 10,108 bowling; 4,464 fielding.
- Match-centre milestones: 415 rows; fastest 50s: 143; fastest 100s: 8.
- HOF deploy-safe highlights: 447 player win-rate rows, 178 BBB batting-rate rows, 432 scorecard milestone rows, 351 bowling milestone rows, 11,751 scorecard record-link rows, 415 fastest batting milestone rows.
- Season Overview deploy-safe highlights: 893 Season by Round rows, 477 BBB batting-rate scope rows, 348 BBB bowling dot-rate scope rows, 1,745 batting milestone scope rows, 1,210 bowling milestone scope rows.
- Player Profile deploy-safe highlights: 23,534 performance-breakdown rows, 1,654 batting-position rows, 442 bowling-phase rows, 1,055 dismissal-fingerprint rows, 7,045 recent-form batting rows, 4,683 recent-form bowling rows.
- Latest match date: 2026-05-23.
- Warnings: 0 validation errors. Mapping review is still recommended for winter/summer labels and senior grade labels. Premiership exports are header-only because no verified premiership evidence exists.
- App smoke: passed for Hall of Fame, Season Overview, Season by Round, Milestone, Player Profile, and Recent Form. No FVCC data/text, traceback, visible `NaN`/`None`, or internal IDs.

### Glen Waverley Hawks

- Seasons: 36; latest season: Summer 2026/27.
- Teams/grades: 330; players: 1,288.
- Match-centre matches found: 3,550 unique matches.
- Completed scorecards parsed: 3,475.
- Ball-by-ball coverage: 698 matches, 241,113 ball events.
- Parsed rows: 54,216 batting; 36,236 bowling; 13,357 fielding.
- Match-centre milestones: 784 rows; fastest 50s: 200; fastest 100s: 32.
- HOF deploy-safe highlights: 1,265 player win-rate rows, 483 BBB batting-rate rows, 1,239 scorecard milestone rows, 1,152 bowling milestone rows, 46,783 scorecard record-link rows, 784 fastest batting milestone rows.
- Season Overview deploy-safe highlights: 3,475 Season by Round rows, 1,348 BBB batting-rate scope rows, 1,321 BBB bowling dot-rate scope rows, 5,603 batting milestone scope rows, 4,379 bowling milestone scope rows.
- Player Profile deploy-safe highlights: 77,705 performance-breakdown rows, 6,248 batting-position rows, 1,631 bowling-phase rows, 3,361 dismissal-fingerprint rows, 26,423 recent-form batting rows, 20,204 recent-form bowling rows.
- Latest match date: 2026-03-15.
- Warnings: 0 validation errors. Historical grade/team labels are messy and need mapping. Duplicate-player risks remain review-only for this club.
- App smoke: passed for Hall of Fame, Season Overview, Season by Round, Milestone, Player Profile, and Recent Form.

### Ashwood

- Seasons: 68; latest season: Summer 2025/26.
- Teams/grades: 453; players: 1,201.
- Match-centre matches found: 5,391 unique matches.
- Completed scorecards parsed: 5,248.
- Ball-by-ball coverage: 920 matches, 303,650 ball events.
- Parsed rows: 61,173 batting; 44,273 bowling; 15,001 fielding.
- Match-centre milestones: 1,019 rows; fastest 50s: 265; fastest 100s: 23.
- HOF deploy-safe highlights: 1,177 player win-rate rows, 611 BBB batting-rate rows, 1,154 scorecard milestone rows, 1,054 bowling milestone rows, 47,266 scorecard record-link rows, 1,019 fastest batting milestone rows.
- Season Overview deploy-safe highlights: 5,248 Season by Round rows, 1,636 BBB batting-rate scope rows, 1,576 BBB bowling dot-rate scope rows, 4,696 batting milestone scope rows, 3,828 bowling milestone scope rows.
- Player Profile deploy-safe highlights: 87,084 performance-breakdown rows, 6,193 batting-position rows, 1,727 bowling-phase rows, 3,202 dismissal-fingerprint rows, 25,713 recent-form batting rows, 21,457 recent-form bowling rows.
- Latest match date: 2026-03-22.
- Warnings: 0 validation errors. Grade/team labels need the most review in this pilot set. Duplicate-player risks remain review-only.
- App smoke: passed for Hall of Fame, Season Overview, Season by Round, Milestone, Player Profile, and Recent Form.

### Plenty

- Seasons: 28; latest season: Summer 2025/26.
- Teams/grades: 327; players: 960.
- Match-centre matches found: 3,264 unique matches.
- Completed scorecards parsed: 3,214.
- Ball-by-ball coverage: 503 matches, 200,539 ball events.
- Parsed rows: 52,067 batting; 35,785 bowling; 11,435 fielding.
- Match-centre milestones: 745 rows; fastest 50s: 242; fastest 100s: 17.
- HOF deploy-safe highlights: 941 player win-rate rows, 360 BBB batting-rate rows, 928 scorecard milestone rows, 882 bowling milestone rows, 38,458 scorecard record-link rows, 745 fastest batting milestone rows.
- Season Overview deploy-safe highlights: 3,214 Season by Round rows, 1,028 BBB batting-rate scope rows, 922 BBB bowling dot-rate scope rows, 4,609 batting milestone scope rows, 3,735 bowling milestone scope rows.
- Player Profile deploy-safe highlights: 62,948 performance-breakdown rows, 5,018 batting-position rows, 1,120 bowling-phase rows, 2,711 dismissal-fingerprint rows, 21,042 recent-form batting rows, 17,312 recent-form bowling rows.
- Latest match date: 2026-03-20.
- Warnings: 0 validation errors. Junior age-group and senior shield labels need mapping review. Some legacy script report columns still use generic `fvcc_*` names for compatibility, but active club paths and outputs were club-specific.
- App smoke: passed for Hall of Fame, Season Overview, Season by Round, Milestone, Player Profile, and Recent Form.

### Reynella

- Seasons: 20; latest season: Summer 2025/26.
- Teams/grades: 334; players: 1,075.
- Match-centre matches found: 3,317 unique matches.
- Completed scorecards parsed: 3,110.
- Ball-by-ball coverage: 572 matches, 244,422 ball events.
- Parsed rows: 55,542 batting; 39,065 bowling; 11,701 fielding.
- Match-centre milestones: 702 rows; fastest 50s: 182; fastest 100s: 17.
- HOF deploy-safe highlights: 1,031 player win-rate rows, 532 BBB batting-rate rows, 1,023 scorecard milestone rows, 946 bowling milestone rows, 43,249 scorecard record-link rows, 702 fastest batting milestone rows.
- Season Overview deploy-safe highlights: 3,110 Season by Round rows, 1,559 BBB batting-rate scope rows, 1,543 BBB bowling dot-rate scope rows, 5,047 batting milestone scope rows, 4,076 bowling milestone scope rows.
- Player Profile deploy-safe highlights: 76,084 performance-breakdown rows, 5,328 batting-position rows, 1,818 bowling-phase rows, 3,102 dismissal-fingerprint rows, 24,023 recent-form batting rows, 19,117 recent-form bowling rows.
- Latest match date: 2026-03-22.
- Warnings: 0 validation errors. Sponsor, junior, T20, and association grade labels need review. Duplicate-player risks remain review-only.
- App smoke: passed for Hall of Fame, Season Overview, Season by Round, Milestone, Player Profile, and Recent Form.

### Georges River District

- Official PlayCricket identity: Georges River Cricket Club.
- Aggregate seasons table: 71 rows; match-centre backfill scope covered 58 seasons.
- Teams/grades: 432; players: 1,650.
- Match-centre matches found: 2,727 unique matches.
- Completed scorecards parsed: 2,604.
- Ball-by-ball coverage: 295 matches, 155,573 ball events.
- Parsed rows: 51,148 batting; 28,888 bowling; 14,306 fielding.
- Match-centre milestones: 555 rows; fastest 50s: 157; fastest 100s: 21.
- HOF deploy-safe highlights: 1,090 player win-rate rows, 329 BBB batting-rate rows, 1,068 scorecard milestone rows, 870 bowling milestone rows, 37,321 scorecard record-link rows, 555 fastest batting milestone rows.
- Season Overview deploy-safe highlights: 2,604 Season by Round rows, 899 BBB batting-rate scope rows, 654 BBB bowling dot-rate scope rows, 5,143 batting milestone scope rows, 3,562 bowling milestone scope rows.
- Player Profile deploy-safe highlights: 60,311 performance-breakdown rows, 4,445 batting-position rows, 770 bowling-phase rows, 3,150 dismissal-fingerprint rows, 22,761 recent-form batting rows, 14,483 recent-form bowling rows.
- Latest match date: 2026-03-22.
- Warnings: 0 validation errors. This remains the highest-risk club because of the large identity pool and long historical scope. Manual identity and grade review should happen before client preview.
- App smoke: passed for Hall of Fame, Season Overview, Season by Round, Milestone, Player Profile, and Recent Form.

## Validation Notes

- All six pilot clubs completed match-centre/backfill and deploy-safe rebuilds.
- No club was skipped.
- Season by Round row counts match completed scorecard counts for each club.
- Recent Form has batting and bowling rows where scorecards exist.
- Fastest Innings outputs were generated only from verified ball-by-ball match-centre milestone data.
- Missing ball-by-ball coverage should continue to render as `N/A`, blank, or a clean empty state rather than a misleading `0.0`.
- Scorecard-derived zeros remain valid when they are actual scorecard stats.
- Premiership exports are header-only for the pilot clubs because no verified premiership evidence was found; no premiership data was fabricated.
- `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES` remains `False`.
- GA4 routing and club-aware parameters were preserved.

## Recommended Review Order

1. Southside East Caulfield: safest client-preview candidate after a final grade-label pass.
2. Plenty: review duplicates and junior/team-grade labels.
3. Reynella: review safe duplicate groups and sponsor/junior/T20 labels.
4. Glen Waverley Hawks: review historical labels and duplicate candidates.
5. Ashwood: review grade/team mappings before client preview.
6. Georges River District: manual identity and naming review first.
