# Ball-by-Ball Data Discovery

Discovery spike for adding ball-by-ball data to The Scorebook app without changing the current UI or aggregate stats pipeline.

## Scope And Safety

- Branch: `ball-by-ball-spike`.
- No main app pages were changed.
- No private endpoints, login flows, hidden data, or access controls were bypassed.
- Requests were limited to a small number of public PlayCricket/PlayHQ documentation checks and one FVCC match sample.
- No bulk historical match pull was run.

## Current Data Pipeline

The current app is local-data-first. Normal dashboard usage reads committed CSVs from `data/processed/` and does not call live PlayCricket endpoints.

Refresh entry points:

- `scripts/refresh_data.py`
- `src/data/playcricket_ingestion.py`
- `src/data/playcricket_public.py`
- `src/data/playhq_api.py`
- `src/data/public_scraper.py`

Current public PlayCricket base URL:

```text
https://grassrootsapiproxy.cricket.com.au
```

Current PlayCricket public endpoints used by the refresh:

| Purpose | Endpoint | Auth |
| --- | --- | --- |
| Club season list | `/fixturesladders/organisations/{club_id}/seasons?jsconfig=eccn:true` | No app secret in current pipeline |
| Club teams for a season | `/fixturesladders/organisations/{club_id}/teams?seasonId={season_id}&jsconfig=eccn:true` | No app secret in current pipeline |
| Grade/team batting stats | `/participants/grades/{grade_id}/batting-statistics?teamId={team_id}&jsconfig=eccn:true` | No app secret in current pipeline |
| Grade/team bowling stats | `/participants/grades/{grade_id}/bowling-statistics?teamId={team_id}&jsconfig=eccn:true` | No app secret in current pipeline |
| Grade/team fielding stats | `/participants/grades/{grade_id}/fielding-statistics?teamId={team_id}&jsconfig=eccn:true` | No app secret in current pipeline |

Current raw files:

- `data/raw/playcricket_seasons_<timestamp>.json`
- `data/raw/playcricket_<season>_teams_<timestamp>.json`
- `data/raw/playcricket_<season>_<team>_batting_<timestamp>.json`
- `data/raw/playcricket_<season>_<team>_bowling_<timestamp>.json`
- `data/raw/playcricket_<season>_<team>_fielding_<timestamp>.json`

Current processed files:

- `data/processed/seasons.csv`
- `data/processed/teams.csv`
- `data/processed/players.csv`
- `data/processed/all_seasons_batting.csv`
- `data/processed/all_seasons_bowling.csv`
- `data/processed/all_seasons_fielding.csv`
- Empty placeholders already exist for `all_seasons_matches.csv`, `all_seasons_scorecard_batting.csv`, `all_seasons_scorecard_bowling.csv`, and `all_seasons_scorecard_fielding.csv`.

## Ball-By-Ball Availability

The PlayCricket public frontend uses additional match-centre endpoints that are not yet part of the app refresh. Static frontend inspection showed these public read paths:

| Purpose | Endpoint | Notes |
| --- | --- | --- |
| Team match list | `/scores/teams/{team_id}/matches?seasonId={season_id}&jsconfig=eccn:true` | Returns fixtures/results for a team and season, including match IDs, teams, venue, schedule, status, round, match type, and result text. |
| Grade match list | `/scores/grades/{grade_id}/matches?seasonId={season_id}&jsconfig=eccn:true` | Similar match list by grade. Not sampled in this spike. |
| Grade rounds | `/scores/grades/{grade_id}/rounds?seasonId={season_id}&jsconfig=eccn:true` | Could support round filters/navigation. Not sampled in this spike. |
| Match scorecard | `/scores/matches/{match_id}?responseModifier=includeScorecard&jsconfig=eccn:true` | Returns match summary, teams, players, schedule, venue, grade, innings, batting, bowling, fielding, extras, and fall of wickets. |
| Match ball events | `/scores/matches/{match_id}/balls?jsconfig=eccn:true` | Returns innings with ball-level events when `isBallByBall` is true. |
| Match highlights | `/scores/matches/{match_id}/highlights?jsconfig=eccn:true` | Public frontend uses this for replay/highlight links. Not sampled in this spike. |
| Match officials | `/scores/matches/{match_id}/officials?jsconfig=eccn:true` | Returns umpire/official names and roles when recorded. |

Important finding: a completed FVCC match returned historical ball-by-ball successfully from `/scores/matches/{match_id}/balls`. That means ball-by-ball is not only live-webhook data when PlayCricket has persisted the events for the public match centre.

Not every match should be assumed to have ball-by-ball. The scorecard response includes `isBallByBall`; future ingestion should check that before requesting/storing ball events.

## PlayHQ Public API And Webhooks

The repo already contains a lightweight PlayHQ client in `src/data/playhq_api.py` for:

- `/v1/organisations/{organisation_id}/seasons`
- `/v1/seasons/{season_id}/grades`
- `/v1/grades/{grade_id}/fixture`
- `/v1/games/{game_id}/summary`

Official PlayHQ support docs say Public APIs require headers:

- `x-api-key`
- `x-phq-tenant`, for Cricket Australia this is `ca`

They also say public APIs respect PlayHQ visibility settings and can retrieve seasons, grades, fixtures, game IDs, and public game summaries. The relevant official support page is:

```text
https://support.playhq.com/hc/en-us/articles/23949453276572-How-To-Use-PlayHQ-API-s
```

PlayHQ live scoreboard integration is a separate webhook product for cricket. Official docs describe live game score events, scorecard updates, undo/reset events, and game summary webhooks. The score event webhook captures each ball or score event during live scoring, while the game summary webhook does not provide live score updates. The relevant official support page is:

```text
https://support.playhq.com/hc/en-us/articles/23976170888476-Live-Scoreboard-Integration
```

Implication:

- Historical public match data can likely be collected from PlayCricket match-centre endpoints where available.
- Official PlayHQ Public API is a cleaner long-term route for fixtures, game summaries, and match metadata if FVCC/association can obtain credentials.
- Official PlayHQ live score webhooks are required for real-time ball capture, but they are integration-partner infrastructure, not a simple historical backfill API.

## Sample Captured

One completed FVCC match was sampled:

```text
Match ID: 53f979f1-6039-42bc-82dd-0ff36d0d7169
Match: Preston Baseballers CC 1st XI vs Fiji Victorian CC 1st XI
Round: Round 14
Grade: 01 - Jika Shield
Dates: 2026-02-07 and 2026-02-14
Venue: H.L.T Oulten Park, Oval #1 North
Status: COMPLETED
Result: Preston Baseballers CC 1st XI won by 5 wickets
```

Saved raw sample files:

- `data/raw/ball_by_ball_sample/manifest.json`
- `data/raw/ball_by_ball_sample/match_scorecard_53f979f1-6039-42bc-82dd-0ff36d0d7169.json`
- `data/raw/ball_by_ball_sample/match_balls_53f979f1-6039-42bc-82dd-0ff36d0d7169.json`
- `data/raw/ball_by_ball_sample/match_officials_53f979f1-6039-42bc-82dd-0ff36d0d7169.json`

Sample response sizes:

| File | Approx size |
| --- | ---: |
| Match scorecard | 44 KB |
| Match balls | 1.0 MB |
| Match officials | 4 KB |
| Manifest | 4 KB |

Sample ball data:

- `match_scorecard` returned `isBallByBall: true`.
- `match_balls` returned 3 innings with 979 ball/event records total.
- `match_scorecard` returned 4 innings. This mismatch was observed in the sample, so processing should outer-join cautiously by innings ID and preserve raw source IDs instead of assuming scorecard innings and ball innings always align one-to-one.

## Other Match Metadata APIs

The summary-style data requested for match pages appears available without building visuals yet:

| Data Needed | Best Source Found | Sample Result |
| --- | --- | --- |
| Teams playing | `/scores/teams/{team_id}/matches` and `/scores/matches/{match_id}?responseModifier=includeScorecard` | Returned both team IDs and display names. |
| Match date | Match list and scorecard `matchSchedule[]` | Returned both days for the sampled two-day match. |
| Venue and playing surface | Match list and scorecard `venue` | Returned venue, suburb/state, and playing surface with coordinates. |
| Format | Match list and scorecard `matchType`, `matchTypeId` | Returned `Two Day` and `1`. |
| Grade/round | Match list and scorecard `grade`, `round` | Returned `01 - Jika Shield` and `Round 14`. |
| Umpire/officials | `/scores/matches/{match_id}/officials` | Returned one umpire for the sampled match. |
| Captain/roles | Scorecard `teams[].players[].roles` | Field exists, but the sampled players had empty role arrays. Need more samples before relying on captain data. |
| Result | Match list and scorecard `matchSummary.resultText` | Returned the final result text. |

If official PlayHQ API credentials are obtained, `/v1/games/{game_id}/summary` should be evaluated as the preferred official equivalent for this summary page data. The current repo client already has a `get_game_summary()` method, but no real API key is committed or used in this spike.

## Sample Fields Available

Match metadata and summary:

- `id`
- `status`, `statusId`
- `matchType`, `matchTypeId`
- `isBallByBall`
- `resultText`
- `round.id`, `round.name`
- `grade.id`, `grade.name`
- `matchSchedule[].matchDay`
- `matchSchedule[].startDateTime`
- `venue.id`, `venue.name`, `venue.playingSurface.id`, `venue.playingSurface.name`
- `teams[].id`, `teams[].displayName`, `teams[].owningOrganisation`
- `teams[].players[].participantId`, `name`, `shortName`, `roles`
- `officials[].name`, `shortName`, `role`

Scorecard innings:

- `innings.id`
- `inningsNumber`, `inningsOrder`, `inningsName`
- `battingTeamId`
- `inningsCloseType`
- `isDeclared`, `isFollowOn`
- `byesRuns`, `legByesRuns`, `noBalls`, `wideBalls`, `penalties`, `totalExtras`
- `oversBowled`, `runsScored`, `numberOfWicketsFallen`
- `batting[]`
- `bowling[]`
- `fielding[]`
- `fallOfWickets[]`

Scorecard batting:

- `participantId`, `playerShortName`
- `batOrder`, `batInstance`
- `ballsFaced`, `foursScored`, `sixesScored`, `runsScored`
- `battingMinutes`, `strikeRate`
- `dismissalTypeId`, `dismissalType`, `dismissalText`

Scorecard bowling:

- `participantId`, `playerShortName`
- `bowlOrder`
- `oversBowled`, `maidensBowled`, `runsConceded`, `wicketsTaken`
- `wideBalls`, `noBalls`, `economy`

Ball events:

- `id`
- `overNumber`, `ballNumber`, `ballDisplayNumber`, `ballTime`
- `strikerParticipantId`, `strikerShortName`, `strikerRunsScored`, `strikerBallsFaced`
- `nonStrikerParticipantId`, `nonStrikerShortName`, `nonStrikerRunsScored`, `nonStrikerBallsFaced`
- `bowlerParticipantId`, `bowlerShortName`
- `runsBat`, `wides`, `noBalls`, `legByes`, `byes`, `penaltyRuns`
- `progressRuns`, `progressWickets`, `progressScore`
- `shortDescription`, `description`
- Wicket fields when applicable: `dismissalTypeId`, `dismissalType`, `dismissedParticipantId`, `fielderParticipantId`, `fielderAssistParticipantId`

## Sample Parser Findings

A sample-only parser was added for the single saved FVCC match. It reads only `data/raw/ball_by_ball_sample/`, makes no external requests, and writes pilot outputs under `data/processed/ball_by_ball_sample/`.

Parsed outputs:

| Output | Rows |
| --- | ---: |
| `all_match_scorecards.csv` | 1 |
| `all_ball_by_ball.csv` | 979 |
| `all_overs.csv` | 160 |
| `all_partnerships.csv` | 26 |
| `all_match_officials.csv` | 1 |
| `validation_report.csv` | 10 |

Parsed innings:

- Scorecard innings: 4
- Ball-event innings: 3
- Ball/event rows: 979

Validation summary:

- Pass: 9
- Warning: 1
- Fail/hard stop: 0

The one warning is the known scorecard/ball-event innings mismatch:

```text
2nd Innings - Preston Baseballers CC 1st XI
scorecard: present
ball events: missing
scorecard total: 0-0 from 0 overs
```

For the three innings that have ball events, validation passed for:

- total runs from ball events vs scorecard innings runs
- wickets from ball events vs scorecard wickets
- legal balls from ball events vs scorecard overs

Recommendation: a one-team pilot backfill is safe as the next discovery step, provided it stays narrow and resumable. The pilot should first collect team match lists and scorecards, request `/balls` only when `isBallByBall` is true, preserve source innings IDs, and write validation warnings instead of failing or inventing missing ball rows.

## Match Centre Data Strategy

The match-centre layer should be scorecard-first. Scorecard data should be collected for every completed public FVCC match because it is the base record for match metadata, teams, innings, batting, bowling, fielding, extras, result, grade, round, venue, and officials. Ball-by-ball should be treated as an optional enrichment layer and requested only when the scorecard indicates `isBallByBall` is true.

The offline match-centre sample parser writes isolated pilot outputs to `data/processed/match_centre_sample/` and does not affect the Streamlit app or the current aggregate refresh pipeline.

Recommended processed table structure:

| Table | Grain | Source |
| --- | --- | --- |
| `all_matches.csv` | One row per match | Scorecard metadata and manifest. |
| `all_match_innings.csv` | One row per scorecard innings | Scorecard innings. |
| `all_scorecard_batting.csv` | One row per batter innings | Scorecard batting, optionally enriched from matching wicket ball events. |
| `all_scorecard_bowling.csv` | One row per bowler innings | Scorecard bowling. |
| `all_scorecard_fielding.csv` | One row per fielder innings/stat | Scorecard fielding. |
| `all_fall_of_wickets.csv` | One row per fall of wicket | Scorecard fall-of-wickets when populated. |
| `all_match_officials.csv` | One row per official | Officials endpoint. |
| `all_ball_by_ball.csv` | One row per ball/score event | Ball endpoint only where available. |
| `all_overs.csv` | One row per over | Derived from ball events only. |
| `all_partnerships.csv` | One row per partnership | Prefer ball events; fall back to fall-of-wickets when ball events are unavailable. |
| `validation_report.csv` | One row per validation check | Derived parser checks. |

Scorecard-only analytics unlocked:

- Match results, venue/grade/round history, opponent history, team scorecards, innings totals, batting scorecards, bowling figures, fielding dismissals, officials, and scorecard-derived partnerships where fall-of-wickets is present.

Ball-by-ball-only analytics unlocked:

- Over-by-over run rates, worm and Manhattan charts, legal/dot ball tracking, boundary/wicket timelines, bowler spell shapes, batter strike rotation, pressure phases, and ball-event partnerships.

Validation approach:

- Keep validation warning-based, not failure-based.
- Compare scorecard innings runs against batting plus extras.
- Compare scorecard wickets against dismissed batting rows.
- Compare scorecard bowling wickets against bowler-credited dismissals where possible.
- Compare scorecard innings totals against final ball-event progress totals where ball data exists.
- Flag scorecard innings missing from ball data and ball innings missing from scorecard data.
- Flag missing player/source IDs, missing dismissal fields, and missing venue/team/grade metadata.

Sample match-centre parser findings:

- `all_matches.csv`: 1 row
- `all_match_innings.csv`: 4 rows
- `all_scorecard_batting.csv`: 33 rows
- `all_scorecard_bowling.csv`: 25 rows
- `all_scorecard_fielding.csv`: 10 rows
- `all_fall_of_wickets.csv`: 0 rows in this sample
- `all_match_officials.csv`: 1 row
- `all_ball_by_ball.csv`: 979 rows
- `all_overs.csv`: 160 rows
- `all_partnerships.csv`: 26 rows
- `validation_report.csv`: 26 rows, with 24 passes and 2 warnings

The two warnings are useful raw-data signals rather than blockers:

- One Preston Baseballers innings has scorecard total 194 but batting plus extras total 184 in the raw scorecard fields.
- The scorecard includes a fourth zero-run innings for Preston Baseballers that has no ball-event innings.

Recommendation for the next controlled pilot: backfill one recent FVCC team and season only. Pull match lists first, collect scorecards for completed matches, collect officials, and request ball events only for scorecards where `isBallByBall` is true. Keep outputs isolated from the aggregate app pipeline until validation rates and storage size are reviewed.

## One-Team One-Season Pilot Results

Pilot scope:

- Season: Winter 2025
- Season ID: `6169f605-4b96-4f21-87c5-0862f914624f`
- Team: FVCC Winter XI
- Team ID: `b0d2ee4c-be8f-4a75-b138-0740a52970c6`
- Raw cache: `data/raw/match_centre_pilot/season=6169f605-4b96-4f21-87c5-0862f914624f__team=b0d2ee4c-be8f-4a75-b138-0740a52970c6/`
- Processed outputs: `data/processed/match_centre_pilot/`

Endpoint counts:

| Endpoint type | Requests | Status |
| --- | ---: | --- |
| Team match list | 1 | 200 |
| Match scorecard | 9 | 200 |
| Match officials | 9 | 200 |
| Match balls | 9 | 200 |
| Total | 28 | All successful |

Coverage:

- Total matches found: 9
- Completed matches: 9
- Scorecards fetched: 9 of 9 completed matches
- Matches with ball-by-ball: 9
- Matches without ball-by-ball: 0

Processed row counts:

| Output | Rows |
| --- | ---: |
| `all_matches.csv` | 9 |
| `all_match_innings.csv` | 18 |
| `all_scorecard_batting.csv` | 209 |
| `all_scorecard_bowling.csv` | 133 |
| `all_scorecard_fielding.csv` | 54 |
| `all_fall_of_wickets.csv` | 144 |
| `all_match_officials.csv` | 9 |
| `all_ball_by_ball.csv` | 3,616 |
| `all_overs.csv` | 576 |
| `all_partnerships.csv` | 156 |
| `validation_report.csv` | 162 |

Validation summary:

- Pass: 154
- Warning: 8
- Error: 0

The warnings were scorecard wicket-vs-dismissal consistency checks in the raw source. There were no request failures and no validation errors. Scorecard coverage was complete for the pilot scope, and ball-by-ball coverage was complete for all completed Winter XI matches in Winter 2025.

Data size:

- Raw cached JSON files: 29 files
- Raw cache size: 4.172 MB
- This is roughly 0.46 MB per completed match for this Winter 2025 team-season pilot.

Recommendation: a broader backfill appears safe if it remains staged. The next step should be another controlled pilot for one summer team/season or one additional recent season, using the same cache/manifest approach. A full-club historical backfill should wait until two or three scoped pilots confirm request volume, scorecard coverage, validation-warning patterns, and repository/data-size impact.

## Representative Summer Pilot Results

Pilot scope:

- Season: Summer 2025/26
- Season ID: `a826b403-b813-4318-9805-5bbe4cf7f238`
- Teams:
  - Fiji Victorian CC 3rd XI, `04 - "B" Grade`, team ID `c3859c82-3451-460a-a8af-f55240f3fec9`
  - Fiji Victorian CC 4th XI, `05 - "C" Grade`, team ID `279aa49f-e6a9-4085-9db7-098edac9c90e`
- Raw cache: `data/raw/match_centre_summer_pilot/`
- Processed outputs: `data/processed/match_centre_summer_pilot/`

Request counts:

| Endpoint type | 3rd XI | 4th XI | Total |
| --- | ---: | ---: | ---: |
| Team match list | 1 | 1 | 2 |
| Match scorecard | 11 | 8 | 19 |
| Match officials | 11 | 8 | 19 |
| Match balls | 9 | 5 | 14 |
| Total | 32 | 22 | 54 |

All requested endpoints returned `200`. The script was rerun after the first fetch and skipped cached files, confirming the cache path is resumable.

Coverage:

| Team | Matches found | Completed | Scorecards fetched | With ball-by-ball | Without ball-by-ball | Officials rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fiji Victorian CC 3rd XI | 12 | 11 | 11 | 9 | 2 | 3 |
| Fiji Victorian CC 4th XI | 10 | 8 | 8 | 5 | 3 | 0 |
| Total | 22 | 19 | 19 | 14 | 5 | 3 |

Processed row counts:

| Output | Rows |
| --- | ---: |
| `all_matches.csv` | 19 |
| `all_match_innings.csv` | 42 |
| `all_scorecard_batting.csv` | 371 |
| `all_scorecard_bowling.csv` | 237 |
| `all_scorecard_fielding.csv` | 97 |
| `all_fall_of_wickets.csv` | 151 |
| `all_match_officials.csv` | 3 |
| `all_ball_by_ball.csv` | 7,131 |
| `all_overs.csv` | 1,126 |
| `all_partnerships.csv` | 226 |
| `validation_report.csv` | 331 |
| `validation_warnings_detail.csv` | 24 |
| `player_identity_audit.csv` | 195 |

Validation summary:

- Pass: 307
- Warning: 24
- Error: 0

The summer pilot is more representative than the Winter pilot. It includes completed scorecards without ball-by-ball, missing officials for lower-grade matches, and raw scorecard consistency warnings. The parser handled these as warnings and kept scorecard data as the base layer.

Player identity audit summary:

- Audit rows: 195 participant/team combinations
- Exact matches to existing player IDs or alias mappings: 51
- Likely name matches: 1
- No match: 143
- FVCC-only rows: 55, with 51 exact matches and 4 no matches

The high no-match count is expected because the pilot includes opposition players and masked placeholder participant records. This confirms the match-centre participant IDs should be audited before any canonical-player merge rule changes.

Data size:

- Raw cached JSON files: 56 files
- Raw cache size: 8.177 MB
- 3rd XI raw cache: 5.606 MB
- 4th XI raw cache: 2.571 MB

Recommendation: production backfill is technically feasible but should not go straight to all seasons. The safe next step is a staged recent-season backfill across current senior teams only, still using cached scorecard-first collection and ball-by-ball only when `isBallByBall` is true. Remaining risks are repository size, inconsistent official coverage, scorecard rows with raw total mismatches, masked/placeholder participant IDs, and identity reconciliation for opposition or duplicate FVCC player profiles.

## Recommended Raw File Structure

Use one folder per sample/bulk refresh scope so match-level files stay reviewable and replayable:

```text
data/raw/playcricket_match_centre/
  <timestamp>/
    manifest.json
    team_matches/
      season=<season_id>__team=<team_id>.json
    matches/
      match=<match_id>__scorecard.json
      match=<match_id>__balls.json
      match=<match_id>__officials.json
      match=<match_id>__highlights.json
```

The manifest should include:

- fetch timestamp
- source endpoint
- request params
- status code
- content type
- source season/team/grade IDs
- whether `isBallByBall` was true
- row/event counts after parsing

For this spike, the sample was saved in the requested location:

```text
data/raw/ball_by_ball_sample/
```

## Recommended Processed Tables

### `all_match_scorecards.csv`

One row per match, plus high-level match metadata.

Recommended columns:

- `match_id`
- `season_id`, `season`
- `grade_id`, `grade_name`
- `round_id`, `round_name`
- `match_type_id`, `match_type`
- `status_id`, `status`
- `result_text`
- `is_ball_by_ball`
- `home_team_id`, `home_team_name`
- `away_team_id`, `away_team_name`
- `fvcc_team_id`, `fvcc_team_name`
- `venue_id`, `venue_name`, `playing_surface_id`, `playing_surface_name`
- `start_date_time`, `match_day_count`
- `officials_json`
- `source_fetched_at`

### `all_match_events.csv`

One row per public match-centre event type, including innings state changes and official/highlight events if collected.

Recommended columns:

- `event_id`
- `match_id`
- `innings_id`
- `event_type`
- `event_order`
- `event_time`
- `team_id`
- `participant_id`
- `payload_json`
- `source_endpoint`

### `all_ball_by_ball.csv`

One row per ball/score event.

Recommended columns:

- `ball_event_id`
- `match_id`
- `innings_id`
- `innings_number`, `innings_order`
- `batting_team_id`, `bowling_team_id`
- `over_number_zero_based`, `over_number_display`
- `ball_number`, `ball_display_number`
- `legal_ball_number_in_over`
- `ball_time`
- `striker_participant_id`, `non_striker_participant_id`, `bowler_participant_id`
- `runs_bat`, `wides`, `no_balls`, `leg_byes`, `byes`, `penalty_runs`, `total_runs`
- `is_legal_delivery`
- `is_wicket`
- `dismissal_type_id`, `dismissal_type`
- `dismissed_participant_id`, `fielder_participant_id`, `fielder_assist_participant_id`
- `progress_runs`, `progress_wickets`, `progress_score`
- `short_description`, `description`

### `all_partnerships.csv`

Can be derived from ball events and/or scorecard fall-of-wickets.

Recommended columns:

- `match_id`
- `innings_id`
- `batting_team_id`
- `partnership_number`
- `batter_1_participant_id`
- `batter_2_participant_id`
- `start_over_ball`
- `end_over_ball`
- `runs`
- `balls`
- `wicket_ending_participant_id`
- `dismissal_type`

### `all_overs.csv`

Derived from ball events.

Recommended columns:

- `match_id`
- `innings_id`
- `batting_team_id`
- `bowling_team_id`
- `over_number_zero_based`
- `over_number_display`
- `bowler_participant_id`
- `runs`
- `wickets`
- `legal_balls`
- `wides`
- `no_balls`
- `boundaries`
- `run_rate_after_over`

## Estimated Data Size

The sampled two-day 1st XI match had:

- 979 ball/event records
- about 1.0 MB raw ball JSON
- about 44 KB raw scorecard JSON

Rule-of-thumb estimates:

- One one-day/T20 match: roughly 0.25 MB to 0.8 MB raw ball JSON.
- One two-day match: roughly 0.8 MB to 1.5 MB raw ball JSON.
- One season/team with 15 to 20 matches: roughly 10 MB to 30 MB raw JSON if most matches have ball-by-ball.
- Full FVCC recent-history backfill: likely hundreds of MB if every team and every season has ball-by-ball, but older seasons may have no ball events or incomplete events.

Use compressed archival storage or keep only parsed CSV plus raw manifest if repo size becomes a concern. Do not add a full historical backfill to Git until reviewed.

## Risks And Limitations

- Public endpoint stability: PlayCricket frontend endpoints are public but not documented as a stable public API contract.
- Availability varies by match: use `isBallByBall` and handle missing `/balls` data.
- Scorecard and ball innings can differ in count/order for multi-day cricket; processing must preserve IDs and avoid assuming perfect positional alignment.
- Older matches may have incomplete ball timing, balls faced, dismissal, or extras fields.
- Player identity mapping must reuse the current canonical player pipeline. Ball-by-ball participant IDs may not always match aggregate-stat participant IDs cleanly.
- Public visibility settings may hide teams, players, or match details.
- PlayHQ official API requires credentials. Do not fake or scrape private API access.
- Live PlayHQ webhook access appears to require integration-partner setup with PlayHQ, including subscription/filter configuration.
- Large backfills could create significant load and repo bloat. Any production backfill should use caching, rate limits, resumable manifests, and a small pilot season first.

## Visuals This Would Unlock

- Worm charts and run-rate progression.
- Manhattan over-by-over scoring charts.
- Partnerships by wicket and batter pair.
- Phase analysis: powerplay/opening overs, middle overs, death overs, chase phases.
- Batter wagon-free scoring profile: boundaries, dot-ball percentage, strike rotation, balls per boundary.
- Bowler spells: economy by over, wicket balls, pressure overs, dot-ball streaks.
- Match momentum timelines with wickets and boundaries.
- Dismissal networks: bowler/fielder/batter involvement.
- Captaincy/lineup context if roles are populated in team/player metadata.
- Venue and umpire context for match history pages.

## Recommended Next Step

Run a controlled pilot for one recent FVCC season and one team only:

1. Pull `/scores/teams/{team_id}/matches` for the selected season/team.
2. For each completed match, request `/scores/matches/{match_id}?responseModifier=includeScorecard`.
3. Request `/scores/matches/{match_id}/balls` only when `isBallByBall` is true.
4. Request `/scores/matches/{match_id}/officials` for match metadata.
5. Parse into the proposed processed tables without wiring any UI.
6. Compare parsed scorecard totals back to the current aggregate `all_seasons_batting/bowling/fielding` tables before any app integration.
