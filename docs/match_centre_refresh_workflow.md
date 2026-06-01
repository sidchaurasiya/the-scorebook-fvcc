# Match Centre Refresh Workflow

Match-centre data is match-level PlayCricket data from public match-centre endpoints. It includes fixtures/results, scorecards, innings, batting cards, bowling cards, fielding cards, fall of wickets, officials, and optional ball-by-ball events.

This pipeline is separate from the existing aggregate stats refresh. It does not replace `scripts/refresh_data.py`, does not alter the Streamlit app, and does not write into the existing aggregate `data/processed/*.csv` tables.

The weekly `scripts/refresh_data.py --club fvcc --with-current-match-centre`
workflow runs a narrow current-season match-centre refresh after the aggregate
PlayCricket refresh, then rebuilds the small deploy-safe Season Overview,
Player Profile, and Hall of Fame exports. Follow it with
`scripts/refresh_club_outputs.py --club fvcc` so the reviewed deploy-safe wrapper
is exercised explicitly. This prevents aggregate leader totals and scorecard
detail such as Season by Round from drifting apart.

## Data Strategy

Scorecard data is the base layer because every completed public match can have useful scorecard information even when ball-by-ball is missing. Ball-by-ball is an enrichment layer and should only be fetched when the scorecard says `isBallByBall` is true.

This means:

- Completed matches without ball-by-ball still populate scorecard tables.
- Ball-by-ball-derived tables are populated only where events exist.
- Season by Round and Player Profile Recent Form should read deploy-safe processed summaries at runtime, not `data/processed/match_centre/`.
- Recent Form bowling exports should skip non-bowling matches and should not output padded `0/0` figures.
- Validation warnings are reviewed, not treated as hard failures.
- Raw files are cached so reruns avoid repeated public requests.

## Ball-By-Ball Metric Source Rule

Season Overview can use scorecard or aggregate data for normal totals such as Runs, Innings, Batting Average, HS, 30s, 50s, 100s, ducks, 4s, and 6s.

Any metric that depends on delivery-level behaviour must come only from verified ball-by-ball computation in the same selected season/team scope. This includes:

- Bat SR
- Batting Dot Ball %
- boundary percentage or boundary rate from balls
- balls per boundary
- balls per dismissal
- any future batting quality/rate metric requiring delivery-level data

Do not mix all-scorecard totals with ball-by-ball denominators. A bad example is total scorecard runs from all matches divided by balls faced from only ball-by-ball matches.

If a player has no verified ball-by-ball data in the selected scope, delivery-based metrics should display blank/`N/A`, not `0.0`.

## Safe Refresh Examples

Single team:

```bash
python scripts/refresh_match_centre_data.py \
  --club fvcc \
  --season-id a826b403-b813-4318-9805-5bbe4cf7f238 \
  --team-id c3859c82-3451-460a-a8af-f55240f3fec9 \
  --output-scope-name summer_2025_26_3rd_xi
```

Two-team controlled scope:

```bash
python scripts/refresh_match_centre_data.py \
  --club fvcc \
  --season-id a826b403-b813-4318-9805-5bbe4cf7f238 \
  --team-id c3859c82-3451-460a-a8af-f55240f3fec9 \
  --team-id 279aa49f-e6a9-4085-9db7-098edac9c90e \
  --output-scope-name summer_2025_26_3rd_4th_xi
```

Small test run:

```bash
python scripts/refresh_match_centre_data.py \
  --club fvcc \
  --season-id a826b403-b813-4318-9805-5bbe4cf7f238 \
  --team-id c3859c82-3451-460a-a8af-f55240f3fec9 \
  --output-scope-name test_match_centre_scope \
  --max-matches 2
```

Use `--force-refresh` only when you intentionally want to refetch cached raw files.

## Deploy-Safe Season Overview Exports

After current-season match-centre data has been refreshed, rebuild the tracked Season Overview summaries:

```bash
python scripts/build_season_overview_detail_exports.py
```

This reads local processed match-centre scopes, including `all_available` and current-season scopes such as `current_winter_2026`, then de-duplicates overlapping matches. It writes small deploy-safe CSVs under:

```text
data/processed/season_overview/
```

These files power Season Overview ball-by-ball and scorecard-derived detailed-table metrics:

- `bbb_batting_rates_by_scope.csv`
- `bbb_bowling_dot_rates_by_scope.csv`
- `scorecard_batting_milestones_by_scope.csv`
- `scorecard_bowling_milestones_by_scope.csv`

Do not commit `data/raw/match_centre/` or `data/processed/match_centre/`. Commit only the small deploy-safe `data/processed/season_overview/` exports when they are intentionally refreshed.

## Outputs

Raw files are written to:

```text
data/raw/match_centre/<output_scope_name>/
```

Processed files are written to:

```text
data/processed/match_centre/<output_scope_name>/
```

Processed outputs:

- `all_matches.csv`
- `all_match_innings.csv`
- `all_scorecard_batting.csv`
- `all_scorecard_bowling.csv`
- `all_scorecard_fielding.csv`
- `all_fall_of_wickets.csv`
- `all_match_officials.csv`
- `all_ball_by_ball.csv`
- `all_overs.csv`
- `all_partnerships.csv`
- `validation_report.csv`
- `validation_warnings_detail.csv`
- `player_identity_audit.csv`
- `refresh_summary.csv`

## Validation Checks

The refresh writes warning rows instead of failing hard. Checks include:

- innings runs vs batting runs plus extras
- wickets vs dismissed batting rows
- bowling wickets vs bowler-credited dismissals
- scorecard innings total vs ball-by-ball final progress score
- scorecard innings missing ball events
- ball innings missing scorecard innings
- missing player/source IDs
- missing dismissal text
- missing venue, grade, or team fields

Review `validation_warnings_detail.csv` before using a scope in the app.

## Player Identity Audit

`player_identity_audit.csv` compares match-centre participant IDs with the current player and alias data. It is audit-only and does not change canonical player merge rules.

Important columns:

- `is_club_player`
- `is_fvcc_player`
- `existing_player_match_status`
- `existing_player_id`
- `existing_canonical_name`
- `possible_reason_for_no_match`

Common no-match reasons include opposition players, masked placeholder participants, and selected-club players not yet present in the existing aggregate player data. `is_fvcc_player` remains in generated files as a compatibility column; new code should prefer `is_club_player`.

## Milestone Records

Fastest 50s and fastest 100s require ball-by-ball data. Scorecard-only matches can confirm that a player reached 50 or 100, but they cannot verify how many balls it took, so they must not be used for fastest milestone records.

After refreshing reviewed match-centre scopes, build the milestone table with:

```bash
python scripts/build_match_centre_milestones.py
```

This writes:

- `data/processed/match_centre/all_batting_milestones.csv`
- `data/processed/match_centre/batting_milestones_validation.csv`

To make Hall of Fame fastest milestone records complete, match-centre refresh needs to be run for all available teams and seasons, then the milestone builder needs to be rerun. Missing ball-by-ball does not mean the record did not happen; it only means the record cannot be verified from the currently available data.

## Review Steps

Before wiring outputs into the app:

1. Check `refresh_summary.csv` for request scope, coverage, data size, and validation counts.
2. Review `validation_warnings_detail.csv`.
3. Review FVCC rows in `player_identity_audit.csv`.
4. Confirm scorecard coverage is acceptable for the intended season/team scope.
5. Confirm ball-by-ball coverage is treated as optional.
6. Confirm raw and processed data sizes are acceptable for the repo/deployment.
7. Only then plan UI integration.

Do not run a full historical backfill until staged recent-season scopes have been reviewed and approved.

## Available-Scope Backfill

After recent scoped pilots have been reviewed, the controlled all-available runner can refresh every locally known club season/team combination from the active club `teams.csv`:

```bash
python scripts/backfill_match_centre_available.py --club fvcc --dry-run
python scripts/backfill_match_centre_available.py --club fvcc --max-seasons 1 --max-teams 1 --max-matches 3
python scripts/backfill_match_centre_available.py --club fvcc
```

The runner writes one ignored combined scope:

- `data/raw/match_centre/all_available/`
- `data/processed/match_centre/all_available/`

It reuses cached files, sleeps between uncached public requests, deduplicates matches across team lists, fetches ball-by-ball only when `isBallByBall` is true, and regenerates batting milestone records for the `all_available` scope.

## Multi-Club Phase 4 / Phase 6.5 Notes

Match-centre raw/full generated folders remain legacy ignored paths through Phase 6.5. They are still used as local inputs for deploy-safe builders, but production runtime should read only small tracked summaries under `clubs/<club_id>/data/processed/...`.

Dry-run commands:

```bash
./.venv-app/bin/python scripts/refresh_match_centre_data.py --club fvcc --dry-run
./.venv-app/bin/python scripts/backfill_match_centre_available.py --club fvcc --dry-run
./.venv-app/bin/python scripts/build_match_centre_milestones.py --club fvcc --dry-run
./.venv-app/bin/python scripts/refresh_club_outputs.py --club fvcc --dry-run
```

Deploy-safe builders write to club folders by default:

- Hall of Fame: `clubs/<club_id>/data/processed/hall_of_fame/`
- Season Overview: `clubs/<club_id>/data/processed/season_overview/`
- Player Profile: `clubs/<club_id>/data/processed/player_profile/`

Use `--legacy-output` only when an explicit compatibility rebuild is required.

Phase 4.5 confirmed that the club-aware deploy-safe wrapper can rebuild FVCC summaries from these existing local inputs without changing the committed club CSVs. The rebuild did not fetch external data and produced identical hashes for all 19 deploy-safe Hall of Fame, Season Overview, and Player Profile CSVs.

Phase 5 made the aggregate refresh command club-aware, but it deliberately did not move match-centre raw/generated folders. The weekly shape is now:

1. `scripts/refresh_data.py --club fvcc` for aggregate processed CSVs under `clubs/fvcc/data/processed/`.
2. `scripts/refresh_match_centre_data.py --club fvcc ...` for controlled current-scope refreshes, or `scripts/backfill_match_centre_available.py --club fvcc` for reviewed all-available refreshes. Both continue to write ignored raw/generated files under `data/raw/match_centre/` and `data/processed/match_centre/`.
3. `scripts/refresh_club_outputs.py --club fvcc` rebuilds deploy-safe summaries from those local inputs into the club data folder.

Phase 6 adds reporting-only safety for match-centre workflows:

- `--dry-run` for scoped refresh and all-available backfill makes no network requests and writes no files.
- dry-run output prints the active club, config PlayCricket ID, input paths, legacy ignored raw/generated output paths, and whether a real run would fetch.
- `scripts/build_match_centre_milestones.py --club fvcc --dry-run` now reports the config PlayCricket ID and explicitly states external fetch is `no`.
- `scripts/refresh_club_outputs.py --club fvcc --dry-run` lists the future weekly sequence, including aggregate refresh, match-centre refresh/backfill, and deploy-safe rebuild.

Phase 6.5 generalized match-centre ownership naming:

- preferred columns are `club_team_id`, `club_team_name`, and `is_club_player`.
- legacy columns `fvcc_team_id`, `fvcc_team_name`, and `is_fvcc_player` are still read and preserved for compatibility with existing FVCC generated files and deploy-safe schemas.
- `src/data/match_centre_ownership.py` provides the fallback shim used by parsers, exporters, and diagnostics.
- `scripts/check_match_centre_ownership.py --club fvcc` reports old/new ownership columns, fallback-derived club team IDs/names, and player ownership counts without fetching or writing.

Do not place raw/full match-centre data under `clubs/<club_id>/data/processed`. Club-specific raw/generated paths such as `data/raw/match_centre/<club_id>/` and `data/processed/match_centre/<club_id>/` are later-phase candidates. Before a second club relies heavily on ball-by-ball or match-centre features, review club-specific team ownership mappings and raw/generated folder scoping.
