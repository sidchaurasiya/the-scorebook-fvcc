# Player vs Peers Calculation Audit

## Peer Group Logic

The Player vs Peers section is rendered from `render_player_peer_comparison(profile_view)` in `src/ui/layout.py`.

The selected player's peer scope is now based on two things:

1. The seasons the selected player appeared in.
2. The cleaned grade/team-grade contexts the selected player appeared in for those seasons.

The app builds a scope key in the form:

```text
Season||Cleaned grade/team context
```

The cleaned grade/team context uses the existing team/grade normalisation helper. It prefers `canonical_grade_label`, then falls back to `team_grade_display`, then to the cleaned team label if grade data is missing.

For example, if a player appeared in:

- Summer 2025/26 · Jack Quick Shield
- Summer 2024/25 · Jika Shield

then peers are drawn from those same season-grade combinations, not from unrelated grades in those seasons.

If older rows have incomplete grade metadata and the same-season/same-grade filter produces no rows, the code falls back to same-season peers so the section does not disappear. No minimum volume filters are applied yet.

## Batting Metrics

Batting peer rows are created by `aggregate_peer_batting(...)` from all-seasons batting rows after canonical player mapping and team/grade display normalisation.

The Player vs Peers batting card shows:

| Metric | Selected Player Calculation | Peer Average Calculation | Min / Max Range | Better Direction | Missing / Zero Handling |
| --- | --- | --- | --- | --- | --- |
| Batting Avg | Total runs / total outs. Outs = innings - not outs. | Pooled peer runs / pooled peer outs. | Player-level min/max batting average. | Higher is better. | Blank if outs are 0 or missing. |
| Strike Rate | Verified ball-by-ball runs * 100 / verified ball-by-ball balls faced, using all verified coverage for the player. | Pooled verified ball-by-ball peer runs * 100 / pooled verified ball-by-ball peer balls for players in the peer cohort. | Player-level min/max verified strike rate. | Higher is better. | Blank if verified ball-by-ball balls faced are 0 or missing. |
| Balls per Dismissal | Scorecard balls faced / scorecard outs across the peer scope. | Pooled scorecard balls faced / pooled scorecard outs. | Player-level min/max balls per dismissal. | Higher is better. | Blank if outs are 0 or missing. |
| Minutes per Dismissal | Scorecard batting minutes / scorecard outs where minutes are available. | Pooled scorecard minutes / pooled scorecard outs. | Player-level min/max minutes per dismissal. | Higher is better. | Hidden/blank if minutes are unavailable or zero. |
| Boundary Rate | (4s + 6s) / innings. | Pooled peer boundaries / pooled peer innings. | Player-level min/max boundary rate. | Higher is better. | Blank if innings are 0 or missing. |
| Innings per Duck | Innings / ducks. | Pooled peer innings / pooled peer ducks. | Player-level min/max innings per duck. | Higher is better. | Blank if ducks are 0. |

## Bowling Metrics

Bowling peer rows are created by `aggregate_peer_bowling(...)` from all-seasons bowling rows after canonical player mapping and team/grade display normalisation.

The Player vs Peers bowling card shows:

| Metric | Selected Player Calculation | Peer Average Calculation | Min / Max Range | Better Direction | Missing / Zero Handling |
| --- | --- | --- | --- | --- | --- |
| Bowling Avg | Runs conceded / wickets. | Pooled peer runs conceded / pooled peer wickets. | Player-level min/max bowling average. | Lower is better. | Blank if wickets are 0. |
| Bowling SR | Balls bowled / wickets. | Pooled peer balls bowled / pooled peer wickets. | Player-level min/max bowling strike rate. | Lower is better. | Blank if wickets are 0. |
| Economy Rate | Runs conceded * 6 / balls bowled. | Pooled peer runs conceded * 6 / pooled peer balls bowled. | Player-level min/max economy. | Lower is better. | Blank if balls bowled are 0. |
| Overs per Maiden | Overs / maidens. Overs are calculated from balls bowled. | Pooled peer overs / pooled peer maidens. | Player-level min/max overs per maiden. | Lower is better. | Blank if maidens are 0. |
| Balls per Extra | Legal balls bowled / (wides + no balls). | Pooled peer legal balls / pooled peer wides+no balls. | Player-level min/max balls per extra. | Higher is better. | Blank / friendly unavailable state if extras are 0. |
| Unassisted Wicket % | Unassisted wickets / wickets * 100. | Pooled peer unassisted wickets / pooled peer wickets * 100. | Player-level min/max unassisted wicket percentage. | Higher is treated as notable/better for this visual. | Blank if wickets are 0 or source data is unavailable. |

## Average-of-Averages Check

The displayed peer averages avoid average-of-averages wherever practical.

Pooled peer calculations are used for:

- Batting Avg
- Strike Rate
- Balls per Dismissal
- Minutes per Dismissal
- Boundary Rate
- Innings per Duck
- Bowling Avg
- Bowling SR
- Economy Rate
- Overs per Maiden
- Balls per Extra
- Unassisted Wicket %

Min/max values remain player-level min/max values so the range line still shows the lowest and highest individual peer values.

## Strike Rate Reliability Check

Player vs Peers batting strike rate uses verified ball-by-ball batting summaries only. The selected-player Strike Rate should match the Player Profile career Strike Rate because both use the same verified career ball-by-ball source.

The old Winter 2025 onward filter should not be used for:

- Balls per Dismissal
- Minutes per Dismissal

Those dismissal-frequency metrics use available scorecard balls/minutes and outs consistently across the selected peer scope.

## Marker Visuals

- Player marker: purple circular marker.
- Peer average marker: grey vertical marker with the shared `.peer-marker.avg-marker` styling.
- Dismissal Fingerprint should reuse the same grey benchmark marker class/style for club-average markers so the visual language remains consistent across Player DNA and Player vs Peers.

## Issues Found

1. No minimum volume threshold is applied in this MVP. Low-volume players can affect peer min, max, and pooled peer averages.

2. Batting and bowling peer groups are built from their respective source tables. Players without batting rows do not affect batting metrics, and players without bowling rows do not affect bowling metrics.

3. Players with zero ducks, zero maidens, or zero extras display blank values for those frequency metrics. This avoids divide-by-zero, but it does not yet show a friendly "No ducks", "No maidens", or "No extras" text.

4. Batting minutes appear to be mostly unavailable/zero in the current data. Minutes per Dismissal will hide or show blank unless usable minutes exist.

## Debug Output

A debug CSV is written to:

```text
data/debug_player_vs_peers.csv
```

It includes:

- peer grade scope
- peer count per metric
- metric name
- player value
- peer average
- peer min/max
- better direction
- comparison label

## Recommended Fixes

1. Consider adding optional minimum-volume rules later so tiny samples do not distort peer comparisons.

2. Consider a friendly special display for zero-denominator excellence, such as "No ducks", "No maidens", or "No extras".

3. Consider showing peer count in the UI once the section is stable.
