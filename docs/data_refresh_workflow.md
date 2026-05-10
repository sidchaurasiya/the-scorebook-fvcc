# Weekly Data Refresh Workflow

The weekly refresh is designed to rebuild the shared app data layer, not page-specific hardcoded outputs. Any current or future visual that reads from the shared processed CSVs should automatically reflect refreshed PlayCricket data after `scripts/refresh_data.py` runs and the Streamlit app is restarted.

## Weekly Refresh Checklist

Use this checklist after FVCC has played and the scorecard/live scoring has been published on PlayCricket.

1. Confirm the latest match is visible on PlayCricket.

   - Open the FVCC PlayCricket page.
   - Check the latest season/team has updated stats.
   - If the match is not visible yet, wait before refreshing the app.

2. Open the project folder.

```bash
cd "/Users/preetkaur/Documents/Codex/2026-04-24/you-are-an-expert-full-stack"
```

3. Pull latest GitHub changes if needed.

   This keeps your local folder aligned before creating new refreshed data.

```bash
git pull
```

4. Check current local changes before refreshing.

```bash
git status
```

   If there are unrelated uncommitted changes, commit or stash them before continuing.

5. Run the dry-run first.

```bash
./.venv-app/bin/python scripts/refresh_data.py --dry-run
```

   Confirm the dry-run shows:

   - the expected latest season
   - no unexpected errors
   - no data files changed

6. Run the real refresh.

```bash
./.venv-app/bin/python scripts/refresh_data.py
```

   The refresh should:

   - create a timestamped rollback snapshot
   - write new timestamped raw PlayCricket backups
   - rebuild shared processed CSVs
   - reapply canonical player mapping
   - reapply team/grade cleaning
   - refresh current-season match-centre data for live-scored matches
   - rebuild deploy-safe Season Overview ball-by-ball detail summaries
   - print a refresh summary

7. Restart the local app.

```bash
./.venv-app/bin/streamlit run app.py --server.port 8502
```

8. Review the app locally.

```text
http://localhost:8502/
```

9. Check the key pages.

- Hall of Fame
- Season Overview
- Milestone
- Player Profile

10. Confirm the latest season/match appears where expected.

   Useful checks:

   - Season Overview season dropdown includes the latest season.
   - Season Overview ball-by-ball metrics include the latest live-scored match.
   - Player Profile shows new season rows for players who played.
   - Hall of Fame totals update where relevant.
   - Milestone totals update where relevant.
   - The latest match date appears in `data/processed/season_overview/*_by_scope.csv`.
   - Biggest Improvers uses the correct previous same-type season.

11. Check changed files.

```bash
git status
```

   Expected changes usually include:

   - `data/raw/playcricket_*_<timestamp>.json`
   - `data/processed/*.csv`
   - `data/metadata.json`
   - audit/debug CSVs such as `data/team_grade_display_audit.csv` or `data/debug_biggest_improvers.csv`

12. Commit the refreshed data after local review.

```bash
git add data README.md docs src scripts
git commit -m "Refresh PlayCricket data"
```

   Adjust the commit message if refreshing for a specific season, for example:

```bash
git commit -m "Refresh data for Winter 2026"
```

13. Push only when ready.

```bash
git push origin main
```

14. After pushing, check Streamlit Cloud.

   If the deployed app does not update after a few minutes:

   - open Streamlit Cloud
   - use Manage app -> Reboot app
   - refresh the browser after reboot

## Refresh Command

```bash
cd "/Users/preetkaur/Documents/Codex/2026-04-24/you-are-an-expert-full-stack"

./.venv-app/bin/python scripts/refresh_data.py
```

Preview mode:

```bash
./.venv-app/bin/python scripts/refresh_data.py --dry-run
```

Restart the app afterwards:

```bash
./.venv-app/bin/streamlit run app.py --server.port 8502
```

## Design Requirement

The refresh script must keep the app local-data-first:

- Pull PlayCricket data into timestamped raw backups.
- Rebuild shared processed datasets.
- Reapply canonical player mapping and manual aliases.
- Reapply team/grade display normalization.
- Leave raw historical backups intact.
- Avoid unnecessary repeated API calls by refreshing the live/current season and using cached historical responses.

Page code should consume the shared processed data layer. Avoid creating page-specific CSVs such as `hall_of_fame_output.csv` or `player_profile_output.csv` unless the source pull is genuinely different.

## Source Files Refreshed

The refresh process writes timestamped raw PlayCricket responses into `data/raw/`.

The raw files follow this pattern:

| Raw File Pattern | Purpose |
| --- | --- |
| `data/raw/playcricket_seasons_<timestamp>.json` | Club season list from PlayCricket. |
| `data/raw/playcricket_<season>_teams_<timestamp>.json` | Team/grade list for each season. |
| `data/raw/playcricket_<season>_<team>_batting_<timestamp>.json` | Public batting stats for a season/team/grade. |
| `data/raw/playcricket_<season>_<team>_bowling_<timestamp>.json` | Public bowling stats for a season/team/grade. |
| `data/raw/playcricket_<season>_<team>_fielding_<timestamp>.json` | Public fielding stats for a season/team/grade. |

The script also creates a local rollback snapshot before a normal refresh:

```text
data/backups/data_snapshot_<timestamp>/
```

These snapshot folders are intentionally ignored by Git. They are local rollback copies, not deployment data.

## Processed Files Regenerated

The shared processed data lives in `data/processed/`.

| Processed File | How It Is Used |
| --- | --- |
| `data/processed/seasons.csv` | Season slicers, season ordering, current/latest season detection, previous same-type season logic. |
| `data/processed/teams.csv` | Team/grade slicers, team/grade display labels, grade ordering, season/team scope. |
| `data/processed/players.csv` | Basic player index from refreshed PlayCricket data. |
| `data/processed/all_seasons_batting.csv` | Shared batting source for Hall of Fame, Season Overview, Milestone, Player Profile, Player vs Peers, Season History, Grade Breakdown, and all-time records. |
| `data/processed/all_seasons_bowling.csv` | Shared bowling source for the same app-wide views and all bowling-derived visuals. |
| `data/processed/all_seasons_fielding.csv` | Shared fielding source for catches, stumpings, run outs, dismissals, Player Profile, and all-time fielding records. |
| `data/processed/all_seasons_matches.csv` | Stable placeholder for future match/result data. Currently empty because the public match/result endpoint was not available during implementation. |
| `data/processed/all_seasons_scorecard_batting.csv` | Stable placeholder for future scorecard-level batting data. Currently empty. |
| `data/processed/all_seasons_scorecard_bowling.csv` | Stable placeholder for future scorecard-level bowling data. Currently empty. |
| `data/processed/all_seasons_scorecard_fielding.csv` | Stable placeholder for future scorecard-level fielding data. Currently empty. |

The refresh also updates:

| File | Purpose |
| --- | --- |
| `data/metadata.json` | Refresh metadata, source endpoints, row counts, cache hits, live requests, and failed requests. |
| `data/player_duplicate_audit.csv` | Duplicate/profile audit regenerated from the refreshed canonical data source. |
| `data/player_identity_summary.csv` | Canonical identity summary regenerated from the refreshed data. |
| `data/team_grade_display_audit.csv` | Team/grade display-normalization audit regenerated from refreshed batting/bowling/fielding/team data. |
| `data/debug_biggest_improvers.csv` | Debug output for the latest Biggest Improvers calculation when that helper runs. |

Manual mapping files are preserved and reapplied:

| File | Purpose |
| --- | --- |
| `data/player_aliases.csv` | Canonical player mapping. |
| `data/manual_player_merges.csv` | Manual merge rules. |
| `data/player_merge_validation.csv` | Validation notes for player merges. |

## Core Refresh Functions

The weekly script is `scripts/refresh_data.py`.

It coordinates these shared helpers:

| Helper | File | Role |
| --- | --- | --- |
| `refresh_playcricket_backup(...)` | `src/data/playcricket_ingestion.py` | Pulls seasons, teams, batting, bowling, and fielding; writes timestamped raw JSON; regenerates processed CSVs and metadata. |
| `rebuild_canonical_processed_tables(...)` | `src/utils/player_identity.py` | Reapplies canonical player fields to shared processed batting/bowling/fielding tables. |
| `ensure_player_alias_mappings(...)` | `src/utils/player_identity.py` | Preserves and reapplies manual aliases and confirmed mappings. |
| `ensure_identity_exports(...)` | `src/utils/player_identity.py` | Rebuilds duplicate audit and identity summary outputs. |
| `export_team_grade_display_audit(...)` | `src/utils/team_grade.py` | Rebuilds the team/grade display audit using cleaned/canonical display fields. |
| `apply_team_grade_display_columns(...)` | `src/utils/team_grade.py` | Adds cleaned team/grade display columns used by UI filters, cards, tables, and profile grade lists. |

## App Helpers That Consume Processed Files

Most app views read from `read_processed_table(...)` in `src/data/playcricket_ingestion.py`. That function uses file modified timestamps for cache invalidation, so restarted Streamlit sessions pick up refreshed CSVs.

Important consumers:

| Consumer | File | Data Used |
| --- | --- | --- |
| `load_local_playcricket_seasons(...)` | `src/ui/layout.py` | `seasons.csv` |
| `load_local_playcricket_teams(...)` | `src/ui/layout.py` | `teams.csv` |
| `load_local_category_frame(...)` | `src/ui/layout.py` | `all_seasons_batting.csv`, `all_seasons_bowling.csv`, `all_seasons_fielding.csv` |
| `load_local_all_team_frames(...)` | `src/ui/layout.py` | Shared category frames for selected season/scope. |
| `load_hall_of_fame_data(...)` | `src/ui/layout.py` | Shared category frames, `seasons.csv`, `players.csv`; builds all-time summaries and Hall of Fame data from shared processed files. |
| `get_hall_of_fame_data(...)` | `src/ui/layout.py` | Cached prepared Hall of Fame data from shared processed files. |
| `build_biggest_improvers(...)` | `src/ui/layout.py` | Shared category frames plus `seasons.csv` for current vs previous same-type season comparisons. |
| `build_approaching_milestone_watchlist(...)` | `src/ui/layout.py` | All-time summary built from shared processed batting/bowling/fielding. |
| `load_player_profile_index(...)` | `src/ui/layout.py` | Shared category frames with canonical identity. |
| `get_player_profile_data(...)` | `src/utils/player_identity.py` | Shared category frames scoped to one canonical player. |
| `render_player_peer_comparison(...)` and related helpers | `src/ui/layout.py` | Shared category frames, canonical identity, cleaned team/grade context. |

## Page Coverage

Because the pages consume shared processed files, a normal refresh should update:

- Hall of Fame
  - KPI totals
  - All-Time Leaders
  - Record Holders
  - Iconic Performances
  - Greatest Individual Seasons
  - Detailed All-Time Records
- Season Overview
  - Season slicer
  - Team/grade slicer
  - Season Standouts
  - Biggest Improvers
  - Leaders by Team/Grade
  - Detailed Stats
- Milestone
  - Active-player milestone calculations
  - Milestone Watchlist
  - Exclusive Club
- Player Profile
  - Player index
  - Career totals
  - Badges and summaries
  - Career Highlights
  - Player vs Peers
  - Season Trends
  - Season History
  - Grade Breakdown
  - Career Breakdown
  - Milestone Watch

## Future Visuals That Will Work Automatically

A future visual should update automatically after weekly refresh if it only needs:

- Player season/team/grade batting totals from `all_seasons_batting.csv`.
- Player season/team/grade bowling totals from `all_seasons_bowling.csv`.
- Player season/team/grade fielding totals from `all_seasons_fielding.csv`.
- Season/team/grade metadata from `seasons.csv` and `teams.csv`.
- Canonical player identity from the shared mapping layer.
- Cleaned team/grade display fields from `src/utils/team_grade.py`.

Examples that should work from the current shared data layer:

- New all-time leaderboards.
- New player career cards.
- New season/team/grade leader comparisons.
- New milestone types based on existing aggregate stat columns.
- New player peer comparisons using aggregate batting/bowling/fielding columns.
- New grade/team breakdowns based on cleaned grade labels.

## Future Visuals That Require Extending the Data Pull

Extend the data pull only when the visual needs data not currently present in the public aggregate stats.

Examples:

- Match-by-match scorecards.
- Ball-by-ball, innings-by-innings, or dismissal-by-dismissal analysis.
- Partnership analysis.
- Opposition, venue, toss, result, and match margin analytics.
- Individual match report pages.
- Player form over last N matches rather than season totals.
- Wagon-wheel style shot maps or detailed scoring zones.
- Keeper-specific catches if PlayCricket exposes them separately from current fielding totals.
- Fielding event context beyond aggregate catches/stumpings/run outs.
- Any visual requiring `all_seasons_matches.csv` or scorecard-level files to be populated with real rows.

If a future visual needs those details, add the source pull to `src/data/playcricket_ingestion.py`, write timestamped raw responses to `data/raw/`, regenerate shared processed files in `data/processed/`, and document the new fields here.
