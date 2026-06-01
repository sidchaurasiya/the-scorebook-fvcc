# Multi-Club Final Hardening Report

Final QA and handover report for the multi-club pilot branch.

## Branch

- Branch: `onboarding/multi-club-positive-responses`
- Audit start commit: `9a54f2c Fix fastest innings validation and HOF theming`
- Final local commit: `Finalize multi-club pilot deployment readiness` on this branch
- Scope: six pilot clubs plus FVCC regression
- Data source: existing local processed, deploy-safe, and match-centre outputs only
- No data fetch, full match-centre/backfill, push, or deployment was performed

## Prepared Clubs

| club_id | club | readiness | highest remaining caveat |
|---|---|---|---|
| `southside-east-caulfield` | Southside East Caulfield Cricket Club | Preview-ready with caveats | 14 manual duplicate groups remain for later review |
| `glen-waverley-hawks` | Glen Waverley Hawks Cricket Club | Preview-ready with caveats | duplicate and self-opponent mapping review before client handover |
| `ashwood` | Ashwood Cricket Club | Preview-ready with caveats | duplicate/team-grade review; Men/Women data present |
| `plenty` | Plenty Cricket Club | Preview-ready with caveats | duplicate/team-grade review and many historical premiership rows to spot-check |
| `reynella` | Reynella Cricket Club | Preview-ready with caveats | duplicate/team-grade review; Men/Women data present |
| `georges-river-district` | Georges River Cricket Club | Preview-ready with caveats | highest data-risk club after one malformed bowling row was fixed |
| `fvcc` | Fiji Victorian Cricket Club | Regression pass | FVCC fallback remains enabled only for FVCC |

Southside remains the safest first private deployment candidate. Georges River is the highest-risk pilot because it had the most suspicious strict duplicate groups and one malformed local scorecard bowling row that surfaced during final audit.

## Config And Fallback Audit

`scripts/check_club_config.py` passed for all six pilot clubs and FVCC.

| club_id | config load | processed path | mapping path | legacy fallback | status |
|---|---|---|---|---|---|
| `southside-east-caulfield` | pass | club-specific | club-specific | false | pass |
| `glen-waverley-hawks` | pass | club-specific | club-specific | false | pass |
| `ashwood` | pass | club-specific | club-specific | false | pass |
| `plenty` | pass | club-specific | club-specific | false | pass |
| `reynella` | pass | club-specific | club-specific | false | pass |
| `georges-river-district` | pass | club-specific | club-specific | false | pass |
| `fvcc` | pass | FVCC/current app | FVCC/current app | true | pass |

No pilot club is configured to fall back to FVCC data.

## Deploy-Safe Data Coverage

| club_id | seasons/teams/players | batting/bowling/fielding rows | HOF files/rows highlights | Season Overview rows | Player Profile rows | BBB coverage |
|---|---:|---:|---|---|---|---|
| `southside-east-caulfield` | available | 5,457 aggregate player-season rows with ids/seasons | win rates 420; scorecard milestones 406; fastest 390; premiership wins 5 | round scorecards 893; batting scope 1,745; bowling scope 1,210 | batting form 7,045; bowling form 4,683; breakdown 23,213 | BBB batting 162 players; scoped BBB 477/348 |
| `glen-waverley-hawks` | available | 17,007 aggregate player-season rows with ids/seasons | win rates 1,222; scorecard milestones 1,198; fastest 730; premiership wins 24 | round scorecards 3,475; batting scope 5,603; bowling scope 4,379 | batting form 26,423; bowling form 20,204; breakdown 76,982 | BBB batting 450 players; scoped BBB 1,348/1,321 |
| `ashwood` | available | 14,205 aggregate player-season rows with ids/seasons | win rates 1,093; scorecard milestones 1,071; fastest 940; premiership wins 13 | round scorecards 5,248; batting scope 4,696; bowling scope 3,828 | batting form 25,713; bowling form 21,457; breakdown 85,924 | BBB batting 546 players; scoped BBB 1,636/1,576 |
| `plenty` | available | 13,485 aggregate player-season rows with ids/seasons | win rates 873; scorecard milestones 866; fastest 704; premiership wins 44 | round scorecards 3,214; batting scope 4,609; bowling scope 3,735 | batting form 21,042; bowling form 17,312; breakdown 61,759 | BBB batting 308 players; scoped BBB 1,028/922 |
| `reynella` | available | 15,891 aggregate player-season rows with ids/seasons | win rates 933; scorecard milestones 926; fastest 645; premiership wins 11 | round scorecards 3,110; batting scope 5,047; bowling scope 4,076 | batting form 24,023; bowling form 19,117; breakdown 74,391 | BBB batting 465 players; scoped BBB 1,559/1,543 |
| `georges-river-district` | available | 23,367 aggregate player-season rows with ids/seasons | win rates 1,040; scorecard milestones 1,020; fastest 514; premiership wins 10 | round scorecards 2,604; batting scope 5,143; bowling scope 3,562 | batting form 22,761; bowling form 14,482; breakdown 59,799 | BBB batting 322 players; scoped BBB 899/654 |
| `fvcc` | available | 5,730 aggregate player-season rows with ids/seasons | win rates 293; scorecard milestones 290; fastest 187; premiership wins 8 | round scorecards 954; batting scope 1,875; bowling scope 1,357 | batting form 8,429; bowling form 5,488; breakdown 21,137 | BBB batting 79 players; scoped BBB 253/221 |

No required deploy-safe file was missing in the final read-only audit.

## High-Risk Metric Audit

| club_id | win% | 30s | fastest | premierships | links | theme | data risk | status |
|---|---|---|---|---|---|---|---|---|
| `southside-east-caulfield` | 420 rows, 329 non-zero; N/A available | 406 rows, 161 non-zero | no 50 < 9 balls; no 100 < 17 balls | 5 wins, 4 captains verified | app-relative ids present | Southside theme pass | medium duplicate caveat | ready with caveats |
| `glen-waverley-hawks` | 1,222 rows, 1,051 non-zero | 1,198 rows, 449 non-zero | thresholds pass | 24 wins, 17 captains | app-relative ids present | club theme pass | duplicate/self-opponent caveats | ready with caveats |
| `ashwood` | 1,093 rows, 960 non-zero | 1,071 rows, 388 non-zero | thresholds pass | 13 wins, 8 captains | app-relative ids present | club theme pass | duplicate/team-grade caveats | ready with caveats |
| `plenty` | 873 rows, 804 non-zero | 866 rows, 374 non-zero | thresholds pass | 44 wins, 30 captains | app-relative ids present | club theme pass | high historical mapping volume | ready with caveats |
| `reynella` | 933 rows, 812 non-zero | 926 rows, 310 non-zero | thresholds pass | 11 wins, 10 captains | app-relative ids present | club theme pass | duplicate/team-grade caveats | ready with caveats |
| `georges-river-district` | 1,040 rows, 869 non-zero | 1,020 rows, 510 non-zero | thresholds pass | 10 wins, 10 captains | app-relative ids present | club theme pass | highest due fixed malformed scorecard row | ready with caveats |
| `fvcc` | 293 rows, 246 non-zero | 290 rows, 133 non-zero | thresholds pass | 8 wins, 8 captains | app-relative ids present | FVCC navy/maroon/gold palette | low regression risk | pass |

Metric rules re-confirmed:

- Win % comes from deploy-safe `player_win_rates.csv`; missing coverage should be N/A, not fake `0.0%`.
- 30s are scorecard innings from 30 to 49 inclusive, including not-outs.
- 3WI is exactly 3 or 4 wickets; 5WI is 5+ wickets.
- BBI is sorted by wickets descending, then runs ascending.
- HS sorting ignores the not-out star.
- Batting strike rate from ball-by-ball uses BBB runs and BBB balls only.
- Fastest 50/100 uses verified batter-ball progression only.
- Premierships and captains are shown only when verified from finals or Grand Final scorecards.

## Final Fix Made

The final audit found a blocker-level malformed Georges River bowling figure where a local scorecard row was interpreted as `41/0`. This could incorrectly affect BBI, 5WI, and profile/season bowling breakdowns.

Fix:

- Added `src/data/scorecard_validation.py`.
- Filtered impossible scorecard bowling figures before deploy-safe season and player-profile exports.
- Preserved valid rare figures up to 10 wickets.
- Added focused unit tests for malformed wicket counts and valid 10-wicket innings.
- Rebuilt deploy-safe outputs from existing local inputs only.

Result:

- Georges River no longer surfaces `41/0`.
- The affected masked player now has BBI `4/22` in player milestones.
- Georges River public best BBI after rebuild is Anthony Ward `9/22`.
- No club has BBI wicket counts above 10.

## Fastest Innings Audit

The fastest-innings validation from `docs/multi_club_fastest_innings_audit.md` remains the source of truth. Final checks confirmed:

- no fastest 50 below 9 balls across the six pilot clubs or FVCC
- no fastest 100 below 17 balls across the six pilot clubs or FVCC
- fastest records continue to require verified ball-by-ball progression
- suspicious or incomplete BBB records are excluded from deploy-safe fastest records rather than shown with guessed values

## Link And Theme Audit

Static and route-level checks confirm:

- internal links use app-relative routing such as `./?page=...`
- non-FVCC player links use active-club canonical IDs where available
- unresolved player IDs render as text instead of broken links
- scorecard links are URL-shape valid PlayCricket links
- visible theming is driven by active club variables
- FVCC uses its shirt-inspired navy, maroon, and gold theme through FVCC config

The original source purple audit reported source-level hits in `src/ui`; those were retained only where backed by active club variables or the then-current FVCC defaults. Runtime smoke checks were used as the visibility check for non-FVCC theme leakage.

Post-hardening FVCC theme update: FVCC no longer uses the legacy purple-first config. Its active-club palette is navy `#24455F`, maroon `#A31952`, gold `#D4A83A`, and cool background `#F6F8FB`. Shared component defaults and legacy purple helper surfaces were moved onto active-club variables so pilot clubs keep their own palettes.

## Smoke Results

Local Streamlit smoke tests were run one server at a time with `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false`.

| club_id | Hall of Fame | Season Overview | Milestone | Player Profile | FVCC leakage | traceback | theme | status |
|---|---|---|---|---|---|---|---|---|
| `southside-east-caulfield` | pass | pass | pass | pass | none seen | none seen | Southside colours | pass |
| `glen-waverley-hawks` | pass | pass | pass | pass | none seen | none seen | club colours | pass |
| `ashwood` | pass | pass | pass | pass | none seen | none seen | club colours | pass |
| `plenty` | pass | pass | pass | pass | none seen | none seen | club colours | pass |
| `reynella` | pass | pass | pass | pass | none seen | none seen | club colours | pass |
| `georges-river-district` | pass | pass | pass | pass | none seen | none seen | club colours | pass |
| `fvcc` | pass | pass | pass | pass | not applicable | none seen | FVCC navy/maroon/gold | pass |

The in-app browser tooling did not expose a reliable viewport resize API during this final pass, so mobile/narrow smoke is recorded as a recommended final human check before sharing a link. Earlier Southside narrow-review issues were addressed in prior commits.

Streamlit can emit shutdown warnings when the browser disconnects during server stop; no page-load traceback was observed in the loaded app routes.

## Compile And Test Results

- `py_compile` passed for `app.py`, config, UI, analytics, data modules, scripts, and tests.
- `pytest` was attempted with `./.venv-app/bin/python -m pytest tests`, but `pytest` is not installed in the app virtual environment.
- Focused validation still covered config checks, deploy-safe row counts, high-risk metric assertions, fastest-innings thresholds, malformed bowling-figure filtering, and browser route smoke.

## Club Caveats

### Southside East Caulfield

- Strict safe duplicate merges already applied earlier; 14 manual duplicate groups remain untouched.
- 5 verified premiership wins; 4 captain rows verified locally.
- Men/Women HOF toggle is available.
- Opponent/ground mappings remain conservative.
- Safest first private preview candidate.

### Glen Waverley Hawks

- 9 suspicious strict-safe duplicate groups and 17 manual duplicate groups remain.
- 24 verified premiership rows; 17 captains verified.
- Self-opponent warnings are likely similarly named club teams/juniors and need human mapping review.

### Ashwood

- 11 suspicious strict-safe duplicate groups and 12 manual duplicate groups remain.
- Men/Women HOF toggle is available.
- Self-opponent warnings and team-grade mappings need light review.

### Plenty

- 14 suspicious strict-safe duplicate groups and 11 manual duplicate groups remain.
- 44 verified premiership rows; 30 captains verified.
- Historical data volume makes mapping review important before a client-facing share.

### Reynella

- 14 suspicious strict-safe duplicate groups and 12 manual duplicate groups remain.
- Men/Women HOF toggle is available.
- Team-grade and self-opponent warnings should be reviewed before sharing.

### Georges River

- 16 suspicious strict-safe duplicate groups and 11 manual duplicate groups remain.
- Final pass fixed one malformed local scorecard bowling row before it could remain a visible record.
- Highest-risk pilot for data QA, but route smoke and deploy-safe file audit now pass.

## What Must Not Be Committed

Do not stage or commit:

- `data/raw/match_centre/`
- `data/processed/match_centre/`
- `data/processed/experimental/`
- review packs
- `data/cache/`
- `data/backups/`
- raw PlayCricket JSON
- debug/audit CSVs such as `data/debug_biggest_improvers.csv` and `data/player_duplicate_audit.csv`

## When A Club Pays Or Approves

1. Choose the club-specific `CLUB_ID`.
2. Create one private Streamlit deployment for that club from this branch or a reviewed merge of this branch.
3. Set `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false`.
4. Set the existing shared `GA4_MEASUREMENT_ID` if analytics should be active.
5. Run the post-deployment smoke checklist in `docs/multi_club_deployment_handover.md`.
6. Share privately only after Hall of Fame, Season Overview, Milestone, Player Profile, links, theme, and GA4 realtime checks pass.

## Recommended Next Actions

- Deploy Southside first when approved.
- Review Georges River duplicate and mapping caveats before client share.
- Review self-opponent warnings for Glen Waverley, Ashwood, Plenty, Reynella, and Georges River.
- Do not apply non-Southside duplicate merges without the strict no-overlap review process.
- Keep fastest innings and all BBB-derived features tied to verified BBB data only.
- Run a human mobile/narrow visual check immediately before sending any private preview link.
