# Experimental Match-Centre Insights

This note is exploration-only. None of these metrics are currently exposed in the main Streamlit app, and generated experimental CSVs should stay out of git until the logic has been reviewed.

## Available Local Inputs

Current scorecard-level files:

| File | Useful Fields | Notes |
| --- | --- | --- |
| `data/processed/all_seasons_matches.csv` | `season`, `match_id`, `date`, `team`, `opponent`, `venue`, `competition`, `result`, `runs_for`, `wickets_for`, `runs_against`, `wickets_against` | Good for FVCC match context, but not enough by itself to prove innings order or chase state. |
| `data/processed/all_seasons_scorecard_batting.csv` | `season`, `match_id`, `player_id`, `player_name`, `runs`, `balls`, `fours`, `sixes`, `strike_rate`, `dismissal` | Good for FVCC batting scorecard metrics. Does not currently include opposition batters. |
| `data/processed/all_seasons_scorecard_bowling.csv` | `season`, `match_id`, `player_id`, `player_name`, `overs`, `maidens`, `runs_conceded`, `wickets`, `wides`, `no_balls`, `economy` | Good for FVCC bowling scorecard metrics. Does not currently include opposition bowlers. |
| `data/processed/all_seasons_scorecard_fielding.csv` | `season`, `match_id`, `player_id`, `player_name`, `catches`, `stumpings`, `run_outs` | Useful for fielding impact in specific matches. |

Ball-by-ball / richer match-centre files may support stronger versions later, but the definitions below should not require live API calls.

## Proposed Metrics

### 3-Wicket Hauls

Definition: count bowler innings where `wickets >= 3`.

Data needed: scorecard bowling rows with `season`, `match_id`, `player_id`, `player_name`, `wickets`, `overs`, `runs_conceded`, `competition` or cleaned grade context if available.

Reliability: high from scorecard data.

Possible outputs:
- Most 3-wicket hauls.
- Most 3-wicket hauls in a season.
- Best conversion from bowling innings to 3-wicket hauls.

Suggested future UI placement: Hall of Fame record holders or Player Profile career highlights.

### Highest Score In The Match

Definition: for each match, identify the highest individual batting score across both teams, then flag whether an FVCC player top-scored.

Current reliability: medium-low with current local files, because `all_seasons_scorecard_batting.csv` appears to hold FVCC batting rows only. It can identify the FVCC top scorer, but not confidently prove match top scorer unless opposition scorecards are added.

Data needed for robust version: both teams' batting scorecards for each `match_id`.

Possible outputs:
- Match top scorer.
- FVCC top scorer.
- Player top-scored in match flag.
- Count of times a player top-scored in a match.

Suggested future UI placement: Match Story, Hall of Fame iconic performances, Player Profile highlights.

### Best Bowling Figures Of The Match

Definition: for each match, identify the best bowling figures across both teams, then flag whether an FVCC player had the best figures.

Sorting:
1. Most wickets.
2. Fewest runs conceded.
3. Fewest overs if a tie-breaker is needed.

Current reliability: medium-low with current local files, because `all_seasons_scorecard_bowling.csv` appears to hold FVCC bowling rows only. It can identify the FVCC best bowler, but not confidently prove match best bowler unless opposition scorecards are added.

Data needed for robust version: both teams' bowling scorecards for each `match_id`.

Suggested future UI placement: Match Story, Hall of Fame iconic performances, Player Profile highlights.

### Master Chaser

Definition: batting innings where an FVCC player was not out in a winning chase and meaningfully contributed.

Exploration rules:
- Batting team is FVCC.
- FVCC batted second or was chasing target where derivable.
- FVCC won the match.
- Player was not out.
- Player scored at least 20 or 25 runs.
- Optional: calculate player share of team runs in the chase.

Current reliability: low until innings order and chase target can be reliably derived. Two-innings or two-day matches need careful handling.

Data needed for robust version: innings order, batting team by innings, target/chase context, final result, scorecard batting dismissal text.

Suggested future UI placement: Player Profile badge, Match Story, Hall of Fame special records.

### Finals Detection

Goal: identify semi-finals, preliminary finals, grand finals, and other finals-like matches for future premiership and big-game records.

Candidate fields:
- `round_name`
- `competition` / cleaned grade name
- `match_type`
- `result`
- raw match summary fields, if available from match-centre payloads

Detection terms should be case-insensitive:
- `final`
- `finals`
- `semi final`
- `semi-final`
- `semifinal`
- `preliminary final`
- `prelim final`
- `grand final`
- `gf`

Proposed normalized `finals_stage` values:
- `home_away`
- `semi_final`
- `preliminary_final`
- `grand_final`
- `final_unknown`
- `unknown`

Reliability: medium once round names are available. Low if only current `all_seasons_matches.csv` is used, because it does not currently show round names.

Suggested audit output:
`data/processed/experimental/finals_match_audit.csv`

Suggested columns:
- `match_id`
- `season`
- `grade_name`
- `round_name`
- `match_date`
- `teams`
- `result_text`
- `detected_finals_stage`
- `detection_reason`
- `confidence`

### Premierships Won

Only build this after finals detection is manually validated.

Definition:
- Identify grand finals.
- Identify winning team.
- If an FVCC team won, count premiership for players listed in that FVCC team scorecard.

Potential Player Profile metrics:
- Premierships won.
- Grand finals played.
- Finals appearances.

Reliability: dependent on finals detection, scorecard player lists, and reliable winning-team parsing.

### Big Game Players

Use validated finals matches only.

Possible stats:
- Runs in finals.
- Wickets in finals.
- Fielding dismissals in finals.
- Highest score in finals.
- Best bowling in finals.
- Semi-final, preliminary final, and grand final splits.

Avoid advanced scoring initially. Start with simple totals and best performances, then review reliability before adding any "impact score".

## Suggested Experimental Script

If implemented later, create:

`scripts/explore_match_centre_insights.py`

Suggested behaviour:
- Read local processed scorecard and match-centre files only.
- Do not fetch external data.
- Do not change app UI.
- Write optional audit CSVs under `data/processed/experimental/`.
- Support `--dry-run` so summaries can be inspected without writing files.

Potential outputs:
- `three_wicket_hauls_summary.csv`
- `match_top_performers_summary.csv`
- `master_chaser_candidates.csv`
- `finals_match_audit.csv`
- `big_game_players_preview.csv`

Generated files in `data/processed/experimental/` should remain ignored until explicitly approved for version control.

## Reliability Concerns

- Current local scorecard batting/bowling files appear to contain FVCC player rows, not both teams. Match-wide "highest score" and "best bowling figures" need opposition scorecards before they can be claimed confidently.
- Master Chaser requires innings order and chase context. Result alone is not enough.
- Finals detection needs round/stage fields. Current match summary columns may not include enough information.
- Premiership counts should not be added until grand final detection and winning team parsing are manually audited.
- All player outputs should use canonical player identity after the metric logic is proven.
