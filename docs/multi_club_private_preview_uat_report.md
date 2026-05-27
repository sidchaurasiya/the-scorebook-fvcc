# Multi-Club Private Preview UAT Report

Prepared from existing local processed outputs, deploy-safe exports, ignored review packs, and localhost smoke checks on the `onboarding/multi-club-positive-responses` branch.

No data fetch, match-centre/backfill rerun, Streamlit deployment, or push was performed.

## Summary

| Club | Status | Safe duplicate merges applied in this pass | Remaining duplicate review | Premiership status | Men/Women HOF | Theme | Smoke |
|---|---|---:|---:|---|---|---|---|
| Glen Waverley Hawks | Preview-ready with caveats | 45 groups / 90 rows | 9 suspicious strict-safe, 17 manual groups | 24 verified local Grand Final wins, 17 captains | Men only | Club colours applied | Pass |
| Ashwood | Preview-ready with caveats | 84 groups / 168 rows | 11 suspicious strict-safe, 12 manual groups | 13 verified local Grand Final wins, 8 captains | Men/Women | Club colours applied | Pass |
| Plenty | Preview-ready with caveats | 70 groups / 140 rows | 14 suspicious strict-safe, 11 manual groups | 44 verified local Grand Final wins, 30 captains | Men only | Club colours applied | Pass |
| Reynella | Preview-ready with caveats | 97 groups / 195 rows | 14 suspicious strict-safe, 12 manual groups | 11 verified local Grand Final wins, 10 captains | Men/Women | Club colours applied | Pass |
| Georges River District | Preview-ready with caveats | 58 groups / 116 rows | 16 suspicious strict-safe, 11 manual groups | 10 verified local Grand Final wins, 10 captains | Men only | Club colours applied | Pass |
| Southside East Caulfield | Preview-ready reference | Already applied previously | 14 manual groups | 5 verified local Grand Final wins, 4 captains | Men/Women | Club colours applied | Pass |

All six clubs are technically back-pocket deployment ready for private preview builds, with caveats. The next human step before sharing each non-Southside link is a light mapping review of team/grade and opponent labels, especially rows where another team name contains the club name.

## Shared Validation

- Deploy-safe Hall of Fame, Season Overview, and Player Profile files exist for all six clubs.
- Win-rate files are populated and no longer show an all-zero win-rate failure pattern.
- Scorecard milestone files are populated and 30s are non-zero where scorecard innings support them.
- HOF and Season Overview link source fields are present; localhost smoke found player and season links on the richer pages.
- Active club CSS variables are present for all clubs; FVCC retains its purple variables.
- Review packs were regenerated under ignored `data/processed/experimental/<club_id>/review_pack/` and were not staged.
- Source-level purple audit still finds FVCC-compatible theme references in shared UI source, but localhost smoke confirmed runtime club variables for each club.
- Self-opponent warnings remain for club-name variants such as junior colour teams, academy/team suffixes, or similarly named external clubs. These were not auto-mapped because some may be legitimate separate teams.

## Glen Waverley Hawks

Status: Preview-ready with caveats.

- Duplicate merge status: applied 45 non-suspicious strict-safe groups, adding 90 club-local merge rows. Skipped 9 suspicious strict-safe groups and left 17 manual duplicate groups untouched.
- Deploy-safe counts: HOF win rates 1,222 rows, scorecard milestones 1,198 rows, Season by Round 3,475 rows, recent form batting 26,423 rows.
- Premiership status: 24 verified local completed Grand Final wins were generated from local match-centre rows; 174 player premiership rows; 17 captains extracted where local winning team roles included captain evidence.
- Men/Women toggle status: Men only from available team-group classification, so the HOF toggle should stay hidden/default.
- Links status: HOF, Season Overview, Milestone, and Player Profile loaded on localhost. Season Overview exposes player links; HOF has player/season link sources.
- Theme status: Hawks primary `#0B4F2F`, accent `#4A8F45`, and link colour `#0B4F2F` were active at runtime.
- Key caveats: self-opponent warnings include Hawks colour/team variants, likely requiring manual team/opponent mapping review before client sharing.

## Ashwood

Status: Preview-ready with caveats.

- Duplicate merge status: applied 84 non-suspicious strict-safe groups, adding 168 club-local merge rows. Skipped 11 suspicious strict-safe groups and left 12 manual duplicate groups untouched.
- Deploy-safe counts: HOF win rates 1,093 rows, scorecard milestones 1,071 rows, Season by Round 5,248 rows, recent form batting 25,713 rows.
- Premiership status: 13 verified local completed Grand Final wins; 103 player premiership rows; 8 captains extracted.
- Men/Women toggle status: Men/Women data detected, so HOF should expose the team-group toggle.
- Links status: Season Overview smoke found player links; HOF/Season/Profile pages loaded after first-load settling with no errors.
- Theme status: Ashwood primary `#185A3D`, accent `#2F855A`, and link colour `#185A3D` were active at runtime.
- Key caveats: self-opponent warnings include Ashwood Pirates/Sharks and similar junior/local variants. Keep as mapping review; do not auto-collapse.

## Plenty

Status: Preview-ready with caveats.

- Duplicate merge status: applied 70 non-suspicious strict-safe groups, adding 140 club-local merge rows. Skipped 14 suspicious strict-safe groups and left 11 manual duplicate groups untouched.
- Deploy-safe counts: HOF win rates 873 rows, scorecard milestones 866 rows, Season by Round 3,214 rows, recent form batting 21,042 rows.
- Premiership status: 44 verified local completed Grand Final wins; 284 player premiership rows; 30 captains extracted.
- Men/Women toggle status: Men only from available team-group classification.
- Links status: HOF, Season Overview, Milestone, and Player Profile loaded; Season Overview and Milestone exposed player links.
- Theme status: Plenty primary `#123C2F`, accent `#2F7D5A`, and link colour `#123C2F` were active at runtime.
- Key caveats: self-opponent warnings include Plenty and Plenty Valley variants. Some may be legitimate opponents, so they need human mapping review.

## Reynella

Status: Preview-ready with caveats.

- Duplicate merge status: applied 97 non-suspicious strict-safe groups, adding 195 club-local merge rows. Skipped 14 suspicious strict-safe groups and left 12 manual duplicate groups untouched.
- Deploy-safe counts: HOF win rates 933 rows, scorecard milestones 926 rows, Season by Round 3,110 rows, recent form batting 24,023 rows.
- Premiership status: 11 verified local completed Grand Final wins; 88 player premiership rows; 10 captains extracted.
- Men/Women toggle status: Men/Women data detected, so HOF should expose the team-group toggle.
- Links status: HOF, Season Overview, Milestone, and Player Profile loaded after first-load settling; Season Overview exposed player links.
- Theme status: Reynella primary `#153E75`, accent `#2B7FC3`, and link colour `#153E75` were active at runtime.
- Key caveats: self-opponent warnings include Reynella Black/Grey and junior variants; review before preview.

## Georges River District

Status: Preview-ready with caveats.

- Duplicate merge status: applied 58 non-suspicious strict-safe groups, adding 116 club-local merge rows. Skipped 16 suspicious strict-safe groups and left 11 manual duplicate groups untouched.
- Deploy-safe counts: HOF win rates 1,040 rows, scorecard milestones 1,020 rows, Season by Round 2,604 rows, recent form batting 22,761 rows.
- Premiership status: 10 verified local completed Grand Final wins; 73 player premiership rows; 10 captains extracted.
- Men/Women toggle status: Men only from available team-group classification.
- Links status: HOF, Season Overview, Milestone, and Player Profile loaded after first-load settling; Season Overview exposed player links.
- Theme status: Georges River primary `#0F3B66`, accent `#2F80C0`, and link colour `#0F3B66` were active at runtime.
- Key caveats: self-opponent warnings include Georges River Navy/Sharks variants and should be reviewed as team/opponent mapping, not auto-corrected.

## Southside Reference

Status: Preview-ready reference.

- Duplicate merge status: safe Southside merges were applied in the earlier preview pass; 14 manual groups remain.
- Deploy-safe counts: HOF win rates 420 rows, scorecard milestones 406 rows, Season by Round 893 rows, recent form batting 7,045 rows.
- Premiership status: 5 verified local completed Grand Final wins; 48 player premiership rows; 4 captains extracted. One captain remains blank where local role evidence is absent.
- Men/Women toggle status: Men/Women data detected and HOF toggle is active.
- Links status: HOF, Season Overview, Milestone, and Player Profile passed localhost smoke with player/season links present on data-rich sections.
- Theme status: Southside primary `#173B63`, accent `#3E8AC7`, and link colour `#173B63` were active at runtime.
- Key caveats: opponent/ground mappings remain conservative starter mappings; manual duplicate groups remain untouched.

## FVCC Regression

- FVCC smoke passed on Hall of Fame, Season Overview, Milestone, and Player Profile.
- Runtime theme variables remained FVCC purple: primary/link/accent `#6D4DFF`.
- No Southside or other pilot-club leakage was detected in FVCC smoke.

## Recommendation

Southside remains the first private-preview candidate. The other five clubs are ready to keep in the deployment back pocket, but should receive one short human mapping review before a club-facing link is shared. Prioritise review in this order:

1. Glen Waverley Hawks: low team-group complexity, but many club-name opponent variants.
2. Ashwood: Men/Women toggle plus manageable duplicate/manual risk.
3. Reynella: Men/Women toggle plus larger safe-merge volume.
4. Georges River District: lower premiership volume but higher suspicious duplicate count.
5. Plenty: high verified premiership volume and several Plenty/Plenty Valley mapping caveats.

