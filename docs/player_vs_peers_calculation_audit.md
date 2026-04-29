# Player vs Peers Calculation Audit

## Peer Group Logic

The Player vs Peers section is rendered from `render_player_peer_comparison(profile_view)` in `src/ui/layout.py`.

The selected player's comparison seasons are taken from the selected player's `season_table`:

```python
seasons = tuple(
    sorted(
        season_table["Season"].dropna().astype(str).unique(),
        key=profile_season_sort_key,
    )
)
```

Those seasons are then passed into `get_player_peer_comparison(player_id, seasons, ...)`.

### Does the peer group change per selected player?

Yes. Because the peer comparison receives the selected player's canonical player id and the selected player's own season list, the peer dataset changes when a different player is selected.

### Does it only include players from the seasons the selected player played?

Yes, for the batting and bowling source rows used by the comparison.

If Player A played:

- Summer 2021/22
- Summer 2022/23
- Summer 2025/26

then the peer batting and bowling aggregations filter source rows to those same seasons only:

```python
scoped = batting[batting["season"].astype(str).isin(seasons)]
scoped = bowling[bowling["season"].astype(str).isin(seasons)]
```

The comparison then groups all players in those filtered rows by canonical player id.

### Important detail

Batting peer metrics are built from the all-seasons batting table. Bowling peer metrics are built from the all-seasons bowling table. A player with no batting row will not influence batting peer metrics, and a player with no bowling row will not influence bowling peer metrics.

This is reasonable for batting/bowling comparisons, but it means the peer population is metric-source specific rather than a single universal list of everyone who appeared in those seasons.

## Batting Metrics

Batting peer rows are created by `aggregate_peer_batting(batting, seasons)`.

For each canonical player in the selected player's seasons, the code calculates:

- total runs
- total innings
- total not outs
- total outs
- total balls faced
- reliable recent runs and balls faced for strike rate
- total 4s
- total 6s
- total 0s

| Metric | Selected Player Calculation | Peer Average Calculation | Lowest / Highest Peer Value | Better Direction | Missing / Zero Handling |
| --- | --- | --- | --- | --- | --- |
| Runs | Sum of `battingAggregate` across the selected player's peer seasons. | Mean of each peer player's total runs. | Min/max of peer player total runs. | Higher is better. | Missing numeric values become 0 through `sum_column`. |
| Balls Faced | Sum of `battingBallsFaced`. | Mean of each peer player's total balls faced. | Min/max of peer player balls faced. | Higher is better. | Missing numeric values become 0 through `sum_column`. |
| Batting Avg | `total runs / total outs`, where `outs = innings - not outs`. | Pooled peer calculation: `total peer runs / total peer outs`. | Min/max of peer player batting averages. | Higher is better. | If outs are 0, value becomes blank / unavailable. |
| Strike Rate | `reliable runs * 100 / reliable balls faced`, using only seasons from Summer 2024/25 onwards. | Pooled peer calculation: `total reliable peer runs * 100 / total reliable peer balls faced`. | Min/max of peer player reliable strike rates. | Higher is better. | If reliable balls faced are 0 or missing, value becomes blank / unavailable. |
| Boundaries | Sum of `battingFours + battingSixes`. | Mean of each peer player's total boundaries. | Min/max of peer player boundaries. | Higher is better. | Missing numeric values become 0 through `sum_column`. |
| 0s / Ducks | Sum of `batting0s`. | Mean of each peer player's total ducks. | Min/max of peer player ducks. | Lower is better. | Missing numeric values become 0 through `sum_column`. |

## Bowling Metrics

Bowling peer rows are created by `aggregate_peer_bowling(bowling, seasons)`.

For each canonical player in the selected player's seasons, the code calculates:

- total wickets
- total runs conceded
- total balls bowled
- total maidens

| Metric | Selected Player Calculation | Peer Average Calculation | Lowest / Highest Peer Value | Better Direction | Missing / Zero Handling |
| --- | --- | --- | --- | --- | --- |
| Wickets | Sum of `bowlingWickets`. | Mean of each peer player's total wickets. | Min/max of peer player wickets. | Higher is better. | Missing numeric values become 0 through `sum_column`. |
| Bowling Avg | `total runs conceded / total wickets`. | Pooled peer calculation: `total peer runs conceded / total peer wickets`. | Min/max of peer player bowling averages. | Lower is better. | If wickets are 0, value becomes blank / unavailable. |
| Bowling Strike Rate | `total balls bowled / total wickets`. | Pooled peer calculation: `total peer balls bowled / total peer wickets`. | Min/max of peer player bowling strike rates. | Lower is better. | If wickets are 0, value becomes blank / unavailable. |
| Economy Rate | `total runs conceded * 6 / total balls bowled`. | Pooled peer calculation: `total peer runs conceded * 6 / total peer balls bowled`. | Min/max of peer player economy rates. | Lower is better. | If balls bowled are 0, value becomes blank / unavailable. |
| Maidens | Sum of `bowlingMaidens`. | Mean of each peer player's total maidens. | Min/max of peer player maidens. | Higher is better. | Missing numeric values become 0 through `sum_column`. |

## Average-of-Averages Check

The selected player's derived metrics and the peer averages for derived metrics are now calculated from underlying totals.

### Selected player calculations

The selected player's values avoid average-of-averages:

- Batting Avg = total runs / total outs
- Strike Rate = reliable total runs / reliable total balls faced * 100
- Bowling Avg = total runs conceded / total wickets
- Bowling Strike Rate = total balls bowled / total wickets
- Economy Rate = total runs conceded * 6 / total balls bowled

### Peer average calculations

Peer averages for simple counting metrics are fine:

- Runs
- Balls Faced
- Boundaries
- 0s
- Wickets
- Maidens

Peer averages for derived rate/average metrics now use pooled total overrides:

- Batting Avg peer average = total peer runs / total peer outs
- Strike Rate peer average = total reliable peer runs * 100 / total reliable peer balls faced
- Bowling Avg peer average = total peer bowling runs conceded / total peer wickets
- Bowling Strike Rate peer average = total peer balls bowled / total peer wickets
- Economy Rate peer average = total peer bowling runs conceded * 6 / total peer balls bowled

Min/max range endpoints remain player-level min/max values.

## Strike Rate Reliability Check

Batting strike rate in Player vs Peers is restricted to Summer 2024/25 onwards.

The batting aggregation filters reliable strike-rate rows with:

```python
reliable = group[
    group["season"].map(profile_season_sort_key)
    >= profile_season_sort_key("Summer 2024/25")
]
```

Then it calculates:

```python
bat_sr = reliable_runs * 100 / reliable_balls
```

If a selected player has no reliable balls faced from Summer 2024/25 onwards, the strike-rate value is blank / unavailable.

## Issues Found

1. No minimum volume threshold is applied in this MVP. Low-volume players can affect peer min, max, and average values.

2. Batting and bowling peer groups are built from their respective source tables. Players without batting rows do not affect batting metrics, and players without bowling rows do not affect bowling metrics.

3. The peer group is dynamic and season-based, but it is not filtered by team/grade, role, match count, innings, balls faced, overs, or wickets.

## Recommended Fixes

1. Consider adding optional minimum-volume rules later so very small samples do not distort peer averages or ranges.

2. Consider displaying peer count per card or metric in the future, especially when reliable strike-rate data excludes older seasons.

3. Keep the current season-based peer grouping unless a future version needs team/grade-specific peer comparisons.
