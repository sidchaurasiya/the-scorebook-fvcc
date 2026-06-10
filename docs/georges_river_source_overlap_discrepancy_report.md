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

## Why Manual Review Count Is High

- The original recommendation count is player-season level and becomes conservative when any one of many compared fields is missing or differs.
- Excel does not reliably capture several modern fields such as balls faced, strike rate, fours, sixes, and some match counts, so exhaustive comparison creates noise that does not affect client-visible records.
- The high-priority export removes exact, close, low-severity, both-missing, and expected non-core Excel gaps.

## What Actually Needs Review Before Preview

- High-priority discrepancy rows: 371.
- P1 rows: 104; P2 rows: 267; P3 rows: 0.
- Private preview blockers: 77.
- Review P1 headline and identity rows first. P2 rows affect core aggregates or source choice. P3 rows are supporting context.

## Recommended Source Rules

- Excel-only seasons: use clean Excel aggregates.
- PlayCricket-only seasons: use sane PlayCricket / PlayHQ aggregates.
- Overlap batting seasons: prefer sane PlayCricket; fall back to clean Excel when PlayCricket has a high-severity anomaly.
- Material core-metric differences require a source decision, and the two sources must never be summed for the same player-season.
- Bowling overlap has no matched player-season rows, so do not automatically merge it. Fielding remains PlayCricket-only.
- BBB-only metrics require verified ball-by-ball data.

## High-Priority Overlap Review File

- Use `grdcc_overlap_high_priority_review.csv` as the working decision file.
- It contains one row per decision-relevant player-season-metric discrepancy with blank reviewer decision and notes fields.
- The operating rules are recorded in `grdcc_source_priority_rules.csv`; compact counts are in `grdcc_overlap_review_summary.csv`.

## Private Preview Blocker Definition

- A discrepancy blocks private preview only when it is app-facing, high severity, not already excluded, and affects a headline record metric.
- Non-headline P2/P3 differences and already excluded anomalies remain review work but do not automatically block preview.

## Caveats

- Excel matches are weak/incomplete in some seasons and are grouped by normalized player name, not a manual merge decision.
- Excel bowling coverage is limited to early seasons.
- PlayCricket has anomaly rows that must remain filtered unless manually approved.
- Player identity matching by normalized name can be imperfect; ambiguous rows are flagged rather than merged.

## Recommended Next Step

- Review high-severity overlap discrepancies first.
- Then decide source priority for overlap seasons.
- Do not block private preview if discrepancies are not driving headline records.

## True App-Facing Preview Blockers

- Provisional headline discrepancies checked: 77.
- Rows that contribute to a current visible headline or leaderboard: 29.
- Confirmed true private-preview blockers: 0.
- High-priority rows moved to source review later: 371.
- Overlap discrepancies are source-priority review items, not automatically data errors. In overlap seasons the app uses sane PlayCricket by default and does not sum Excel with PlayCricket.
- A discrepancy blocks preview only when the selected app-facing PlayCricket row is itself high-severity anomalous, has not already been excluded, and drives a headline output.
- Review `grdcc_true_preview_blockers.csv` for the visibility trace and `grdcc_overlap_review_later.csv` for deferred source decisions.
