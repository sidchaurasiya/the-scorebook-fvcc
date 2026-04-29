# Player vs Peers Calculation Audit

## Peer Group Logic

The Player vs Peers section is rendered from `render_player_peer_comparison(profile_view)` in `src/ui/layout.py`.

The selected player's comparison seasons are taken from the selected player's `season_table`, then passed into `get_player_peer_comparison(player_id, seasons, ...)`.

The peer group is dynamic per selected player. If a different player is selected, their own season list is used, so the comparison group changes.

For each card:

- Batting metrics use all canonical players found in the all-seasons batting rows for the selected player's seasons.
- Bowling metrics use all canonical players found in the all-seasons bowling rows for the selected player's seasons.
- No minimum peer filters are applied yet.
- The peer group is not currently filtered by team, grade, match count, innings, balls faced, overs, or wickets.

Example: if a player appeared in Summer 2021/22, Summer 2022/23, and Summer 2025/26, the peer calculations use all batting/bowling rows from those same seasons only.

## Batting Metrics

Batting peer rows are created by `aggregate_peer_batting(batting, seasons)`.

The Player vs Peers batting card now shows only quality/rate metrics:

| Metric | Selected Player Calculation | Peer Average Calculation | Lowest / Highest Peer Value | Better Direction | Missing / Zero Handling |
| --- | --- | --- | --- | --- | --- |
| Batting Avg | `total runs / total outs`, where `outs = innings - not outs`. | Pooled peer calculation: `total peer runs / total peer outs`. | Min/max of peer player batting averages. | Higher is better. | If outs are 0, value becomes blank / unavailable. |
| Strike Rate | `reliable runs * 100 / reliable balls faced`, using only rows from Winter 2025 onward. | Pooled peer calculation: `total reliable peer runs * 100 / total reliable peer balls faced`, also from Winter 2025 onward. | Min/max of peer player reliable strike rates. | Higher is better. | If reliable balls faced are 0 or missing, value becomes blank / unavailable. |
| Boundary Rate | `(4s + 6s) / innings`. | Pooled peer calculation: `total peer boundaries / total peer innings`. | Min/max of peer player boundary rates. | Higher is better. | If innings are 0, value becomes blank / unavailable. |
| Innings per Duck | `innings / ducks`. | Pooled peer calculation: `total peer innings / total peer ducks`. | Min/max of peer player innings-per-duck values. | Higher is better. | If ducks are 0, value becomes blank / unavailable. |

Removed from Player vs Peers only:

- Runs
- Balls Faced
- Raw total Boundaries
- Raw total Ducks

These metrics still exist elsewhere in the app.

## Bowling Metrics

Bowling peer rows are created by `aggregate_peer_bowling(bowling, seasons)`.

The Player vs Peers bowling card now shows only quality/rate metrics:

| Metric | Selected Player Calculation | Peer Average Calculation | Lowest / Highest Peer Value | Better Direction | Missing / Zero Handling |
| --- | --- | --- | --- | --- | --- |
| Bowling Avg | `total runs conceded / total wickets`. | Pooled peer calculation: `total peer runs conceded / total peer wickets`. | Min/max of peer player bowling averages. | Lower is better. | If wickets are 0, value becomes blank / unavailable. |
| Bowling SR | `total balls bowled / total wickets`. | Pooled peer calculation: `total peer balls bowled / total peer wickets`. | Min/max of peer player bowling strike rates. | Lower is better. | If wickets are 0, value becomes blank / unavailable. |
| Economy Rate | `total runs conceded * 6 / total balls bowled`. | Pooled peer calculation: `total peer runs conceded * 6 / total peer balls bowled`. | Min/max of peer player economy rates. | Lower is better. | If balls bowled are 0, value becomes blank / unavailable. |
| Overs per Maiden | `overs / maidens`, where overs are calculated from balls bowled. | Pooled peer calculation: `total peer overs / total peer maidens`. | Min/max of peer player overs-per-maiden values. | Lower is better. | If maidens are 0, value becomes blank / unavailable. |

Removed from Player vs Peers only:

- Wickets
- Maidens

These metrics still exist elsewhere in the app.

## Average-of-Averages Check

The current Player vs Peers quality metrics avoid average-of-averages for the displayed peer average.

Pooled peer averages are used for:

- Batting Avg
- Strike Rate
- Boundary Rate
- Innings per Duck
- Bowling Avg
- Bowling SR
- Economy Rate
- Overs per Maiden

Min/max values remain player-level min/max values so the range line still shows the lowest and highest individual peer values.

## Strike Rate Reliability Check

Player vs Peers batting strike rate now uses only data from Winter 2025 onward.

Rows before Winter 2025 are excluded from the strike-rate numerator and denominator for both the selected player and peer averages.

If a player has no Winter 2025 onward balls faced, the value displays as blank / unavailable.

## Issues Found

1. No minimum volume threshold is applied in this MVP. Low-volume players can affect peer min, max, and pooled peer averages.

2. Batting and bowling peer groups are built from their respective source tables. Players without batting rows do not affect batting metrics, and players without bowling rows do not affect bowling metrics.

3. Players with zero ducks or zero maidens do not receive an Innings per Duck or Overs per Maiden marker. This avoids divide-by-zero, but it means excellent zero-event players are shown as unavailable rather than with a special infinity-style value.

## Recommended Fixes

1. Consider adding optional minimum-volume rules later so tiny samples do not distort peer comparisons.

2. Consider a special friendly display for zero ducks or zero maidens, such as "No ducks" or "No maidens", if that proves clearer than a blank value.

3. Consider displaying peer counts in a future version, especially for strike rate because it only uses Winter 2025 onward data.
