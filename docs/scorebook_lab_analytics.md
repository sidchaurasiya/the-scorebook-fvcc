# Scorebook Lab Analytics

Scorebook Lab is an experimental, hidden analytics page for advanced club cricket stories. It is shown only when experimental match-centre pages are enabled.

## Data Sources

- Existing aggregate batting, bowling, and fielding processed CSVs.
- Local processed match-centre scorecard tables under `data/processed/match_centre/<scope>/`.
- Deploy-safe milestone records under `data/processed/hall_of_fame/fastest_batting_milestones.csv`.
- Ball-by-ball data only where already refreshed and available locally.

The Streamlit app does not fetch PlayCricket or PlayHQ data inside this page.

## Metrics

### Biggest Carry Jobs

Scorecard-based. Ranks batter innings by player runs as a percentage of team innings runs, then by final runs. Includes next-highest teammate score where the same innings scorecard is available.

### Highest Team-Run Contribution

Scorecard-based. Ranks innings by `player runs / team innings runs`. This highlights innings that carried a large share of the team total, even if the raw score was not a club record.

### Wicket Share Dominance

Scorecard-based. Ranks bowling spells by `bowler wickets / opposition wickets fallen`, then wickets and economy. It answers: who took the biggest share of the wickets FVCC claimed?

### Best All-Round Match Impact

Scorecard-based first version. The impact score is intentionally simple:

- batting points from runs and team-run contribution
- bowling points from wickets and wicket share
- fielding points from catches, run outs, stumpings, and assisted run outs

This is not a replacement-value or win-probability model. It is a transparent Scorebook MVP signal.

### Fielding Impact

Scorecard-based. Uses catches, run outs, stumpings, and assisted run outs where present. Keeper catches are included only when the processed source exposes them separately in a future pass.

### Ground Hunter

Scorecard-based. Uses venue, match result text, innings totals, batting rows, bowling rows, and fielding rows. It shows the ground profile, top players at a ground, best innings/spells, and impact rankings.

### Opponent Hunter

Scorecard-based. Uses opponent context from match-centre matches joined to batting, bowling, fielding, and innings rows. It shows rivalry profile, top performers, best scorecard performances, and dismissal pattern where batting dismissals exist.

### Position Intelligence

Scorecard-based. Uses batting order from scorecard batting rows. It builds a player batting-order ladder and a team-level best-player-by-position list.

### Match Story And Hidden MVP

Scorecard-based with optional partnership enhancement. The MVP card uses simple batting, bowling, and fielding points. The story timeline uses top contribution, top wicket share, best partnership when available, and innings scorecard context.

### Partnership Chemistry

Uses processed `all_partnerships.csv`. This section appears only when partnership rows have usable batter pair names. It ranks pairs by total partnership runs, average partnership, best stand, and scoring rate when balls are available.

## Limitations

- Match-centre coverage is incomplete for older or scorecard-only matches.
- Ball-by-ball metrics should be treated as verified only for matches with persisted ball events.
- Result records are derived from public result text and may need future hardening.
- Partnerships can be scorecard-derived or ball-derived depending on source availability, so pair analysis is a cautious first pass.
- Player identity depends on current canonical matching and may need review for duplicate or masked profiles.

## Product Guidance

Scorebook Lab should remain hidden until the sections are reviewed for data quality, copy, and usefulness. The stable published app should continue to expose only reviewed pages and the Hall of Fame fastest milestone records.
