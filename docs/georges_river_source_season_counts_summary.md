# GRDCC Source Season Counts Summary

## Final Source Decision

Final app-facing priority is Historical Excel through `Summer 1971/72` and PlayCricket / PlayHQ from `Summer 1972/73` onward. Season counts below describe captured source coverage; the app applies the fixed cutoff and never sums overlapping player-seasons.

## Purpose

This report compares season-level coverage across GRDCC PlayCricket / PlayHQ processed data and the Historical Excel spreadsheet. Counts use source rows as supplied and do not merge or infer missing records.

## Headline Counts

| Source | Seasons | Players | Team/Grade Combinations | Matches | Batting Rows | Bowling Rows | Fielding Rows |
|---|---:|---:|---:|---:|---:|---:|---:|
| PlayCricket / PlayHQ | 57 | 1641 | 52 | Unavailable | 7789 | 7789 | 7789 |
| Historical Excel | 86 | 1778 | 1 | Unavailable | 4980 | 355 | 0 |

## Season-Level Coverage

- Excel-only seasons: 36.
- PlayCricket-only seasons: 7.
- Overlap seasons: 50.
- Seasons with Excel batting: 86; Excel bowling: 32.
- Seasons with PlayCricket batting: 57; bowling: 57; fielding: 57.
- Season detail rows: 57 PlayCricket and 86 Excel.

## Data Quality Notes

- PlayCricket provides player-season aggregate batting, bowling and fielding rows.
- The requested PlayCricket match-level candidates are absent or contain no data rows, so exact match counts are unavailable and are not inferred from player-season `matches` values.
- Historical Excel has strong historical batting coverage and limited older-season bowling coverage.
- Excel match counts are unavailable and are not inferred from player-season rows.
- Excel team coverage uses a generic Georges River DCC / Historical club summary label; it should not be interpreted as a detailed team-grade history.
- Player counts exclude blank, masked, numeric-only and other names without alphabetic characters.

## How to Use

- Use the season CSV to identify seasons present in only one source versus both sources.
- Do not infer exact match counts from player-season aggregates.
- Use the overlap discrepancy reports for player-season source-priority decisions.
