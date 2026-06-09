# Georges River Source Overlap Discrepancy Report

## Executive Summary

- Overlap seasons compared: 50.
- Matched batting player-season rows: 2565.
- Matched bowling player-season rows: 0.
- Total metric comparisons: 33345.
- Exact matches: 15704; close matches: 120; material differences: 497.
- Manual review required recommendations: 2540.

## Batting Overlap

- Seasons compared: 50.
- Matched player-seasons: 2565.
- Unmatched Excel batting player-seasons: 815.
- Unmatched PlayCricket batting player-seasons: 1076.
- Major differences are concentrated where the same player-season aggregate totals differ materially or one source lacks a major stat.

### Top High-Severity Batting Discrepancies

| Season | Player | Metric | Excel | PlayCricket | Severity | Recommended |
|---|---|---|---:|---:|---|---|
| Summer 1970/71 | Graham Butt | innings | 17 | 2 | high | manual_review |
| Summer 1970/71 | Graham Butt | runs | 185 | 25 | high | manual_review |
| Summer 1970/71 | Graham Butt | high_score | 37 | 16 | high | manual_review |
| Summer 1973/74 | R Smith | innings | 1 | 0 | high | excel |
| Summer 1983/84 | Peter Trajkovski | matches | 6 | 7 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | innings | 7 | 7 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | not_outs | 2 | 2 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | runs | 30 | 30 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | high_score | 19 | 19 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | batting_average | 6 | 6 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | batting_strike_rate |  |  | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | balls_faced |  | 0 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | 50s |  | 0 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | 100s |  | 0 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | ducks |  | 0 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | fours |  | 0 | high | manual_review |
| Summer 1983/84 | Peter Trajkovski | sixes |  | 0 | high | manual_review |
| Summer 1988/89 | Rohan Clarke | runs | 543 | 421 | high | manual_review |
| Summer 1988/89 | Rohan Clarke | high_score | 89 | 69 | high | manual_review |
| Summer 1989/90 | Dean Magee | runs | 442 | 284 | high | manual_review |

## Bowling Overlap

- Seasons compared: 2.
- Matched player-seasons: 0.
- Unmatched Excel bowling player-seasons: 2.
- Unmatched PlayCricket bowling player-seasons: 3641.
- Excel bowling overlap is limited; BBI/5WI/10WM are marked not comparable unless both sources explicitly capture them.

### Top High-Severity Bowling Discrepancies

- None.

## Source Priority Recommendations

- Recommended Excel rows: 1.
- Recommended PlayCricket rows: 25.
- Recommended manual review rows: 2539.
- Use PlayCricket when both sources are sane and agree closely, especially for modern/current aggregate records.
- Use Excel when PlayCricket has high-severity anomaly status and Excel is clean and complete.
- Use manual review when values differ materially or identity matching is ambiguous.
- Use neither source for BBB-only metrics unless verified ball-by-ball data exists.

## Caveats

- Excel matches are weak/incomplete in some seasons and are grouped by normalized player name, not a manual merge decision.
- Excel bowling coverage is limited to early seasons.
- PlayCricket has anomaly rows that must remain filtered unless manually approved.
- Player identity matching by normalized name can be imperfect; ambiguous rows are flagged rather than merged.

## Recommended Next Step

- Review high-severity overlap discrepancies first.
- Then decide source priority for overlap seasons.
- Do not block private preview if discrepancies are not driving headline records.
