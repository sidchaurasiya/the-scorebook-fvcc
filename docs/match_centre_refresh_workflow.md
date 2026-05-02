# Match Centre Refresh Workflow

Match-centre data is match-level PlayCricket data from public match-centre endpoints. It includes fixtures/results, scorecards, innings, batting cards, bowling cards, fielding cards, fall of wickets, officials, and optional ball-by-ball events.

This pipeline is separate from the existing aggregate stats refresh. It does not replace `scripts/refresh_data.py`, does not alter the Streamlit app, and does not write into the existing aggregate `data/processed/*.csv` tables.

## Data Strategy

Scorecard data is the base layer because every completed public match can have useful scorecard information even when ball-by-ball is missing. Ball-by-ball is an enrichment layer and should only be fetched when the scorecard says `isBallByBall` is true.

This means:

- Completed matches without ball-by-ball still populate scorecard tables.
- Ball-by-ball-derived tables are populated only where events exist.
- Validation warnings are reviewed, not treated as hard failures.
- Raw files are cached so reruns avoid repeated public requests.

## Safe Refresh Examples

Single team:

```bash
python scripts/refresh_match_centre_data.py \
  --season-id a826b403-b813-4318-9805-5bbe4cf7f238 \
  --team-id c3859c82-3451-460a-a8af-f55240f3fec9 \
  --output-scope-name summer_2025_26_3rd_xi
```

Two-team controlled scope:

```bash
python scripts/refresh_match_centre_data.py \
  --season-id a826b403-b813-4318-9805-5bbe4cf7f238 \
  --team-id c3859c82-3451-460a-a8af-f55240f3fec9 \
  --team-id 279aa49f-e6a9-4085-9db7-098edac9c90e \
  --output-scope-name summer_2025_26_3rd_4th_xi
```

Small test run:

```bash
python scripts/refresh_match_centre_data.py \
  --season-id a826b403-b813-4318-9805-5bbe4cf7f238 \
  --team-id c3859c82-3451-460a-a8af-f55240f3fec9 \
  --output-scope-name test_match_centre_scope \
  --max-matches 2
```

Use `--force-refresh` only when you intentionally want to refetch cached raw files.

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

- `is_fvcc_player`
- `existing_player_match_status`
- `existing_player_id`
- `existing_canonical_name`
- `possible_reason_for_no_match`

Common no-match reasons include opposition players, masked placeholder participants, and FVCC players not yet present in the existing aggregate player data.

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

After recent scoped pilots have been reviewed, the controlled all-available runner can refresh every locally known FVCC season/team combination from `data/processed/teams.csv`:

```bash
python scripts/backfill_match_centre_available.py --dry-run
python scripts/backfill_match_centre_available.py --max-seasons 1 --max-teams 1 --max-matches 3
python scripts/backfill_match_centre_available.py
```

The runner writes one ignored combined scope:

- `data/raw/match_centre/all_available/`
- `data/processed/match_centre/all_available/`

It reuses cached files, sleeps between uncached public requests, deduplicates matches across team lists, fetches ball-by-ball only when `isBallByBall` is true, and regenerates batting milestone records for the `all_available` scope.
