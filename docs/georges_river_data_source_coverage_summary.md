# Georges River Data Source Coverage Summary

## Final Source Decision

As of June 10, 2026, the app uses Historical Excel through `Summer 1971/72` and PlayCricket / PlayHQ from `Summer 1972/73` onward. Sources are never summed for the same player-season.

## Executive Summary

- PlayCricket / PlayHQ provides the primary modern aggregate source for batting, bowling and fielding, but it includes known anomaly rows that must remain filtered or manually reviewed before driving headline records.
- Historical Excel provides supplemental historical batting and bowling coverage, mostly filling older seasons and specific historical gaps not covered by PlayCricket / PlayHQ.
- Overlap seasons exist and should be treated as manual source-priority review zones rather than automatically merged without QA.
- Excel-derived data is suitable for clean aggregate batting and bowling summaries, but it is never suitable for ball-by-ball-only metrics.

## Source 1: PlayCricket / PlayHQ

- Batting Rows: 7789
- Bowling Rows: 7789
- Fielding Rows: 7789
- Match Rows: 0
- Batting Seasons: 57
- Bowling Seasons: 57
- Fielding Seasons: 57
- Batting Season Range: Summer 1968/69 to Summer 2025/26
- Bowling Season Range: Summer 1968/69 to Summer 2025/26
- Fielding Season Range: Summer 1968/69 to Summer 2025/26
- Unique Batting Players: 1561
- Unique Bowling Players: 1561
- Unique Fielding Players: 1561
- Unique Players Overall: 1561
- Teams Grades Detected: 52
- Key Columns Present: batting0s, batting100s, batting50s, battingAggregate, battingAverage, battingBallsFaced, battingFours, battingHighScore, battingInnings, battingMinutes, battingNotOuts, battingSixes, battingStrikeRate, bowling10WMs, bowling5WIs, bowlingAverage, bowlingBalls, bowlingBestInnings, bowlingEconomyRate, bowlingMaidens, bowlingNoBalls, bowlingRuns, bowlingStrikeRate, bowlingWickets, bowlingWicketsUnassisted, bowlingWides, canonical_player_id, canonical_player_name, club, competition_name, fieldingAssistedRunOuts, fieldingCatchesNonWK, fieldingCatchesWK, fieldingRunOuts, fieldingStumpings, fieldingTotalCatches, fieldingUnassistedRunOuts, grade_id, grade_name, isBattingHSNotOut
- Key Columns Missing: none
- Known anomaly rows: 1723
- High severity anomaly findings: 295
- Medium severity anomaly findings: 1428
- App-facing dangerous raw rows already excluded: 57

## Source 2: Historical Excel Spreadsheet

- Clean Batting Rows: 4980
- Clean Bowling Rows: 355
- Review Rows: 1139
- Rejected Rows: 308
- Batting Seasons: 86
- Bowling Seasons: 32
- Batting Season Range: Summer 1929/30 to Summer 2021/22
- Bowling Season Range: Summer 1929/30 to Summer 1974/75
- Unique Batting Players: 1785
- Unique Bowling Players: 168
- Unique Players Overall: 1791
- Teams Grades Detected: 1
- Key Columns Present: batting0s, batting100s, batting50s, battingAggregate, battingAverage, battingBallsFaced, battingFours, battingHighScore, battingInnings, battingMinutes, battingNotOuts, battingSixes, battingStrikeRate, bowling10WMs, bowling5WIs, bowlingAverage, bowlingBalls, bowlingBestInnings, bowlingEconomyRate, bowlingMaidens, bowlingNoBalls, bowlingRuns, bowlingStrikeRate, bowlingWickets, bowlingWicketsUnassisted, bowlingWides, canonical_player_id, canonical_player_name, club, competition_name, data_confidence, grade_id, grade_name, isBattingHSNotOut, matches, player_id, player_name, raw_player_id, raw_player_name, season
- Key Columns Missing: none
- Clean rows: 5335
- Review rows: 1139
- Rejected rows: 308
- Excel decision review rows: 7706

## Season Overlap

| Category | Count | Example Seasons |
|---|---:|---|
| Excel only seasons | 36 | Summer 1929/30, Summer 1930/31, Summer 1931/32, Summer 1932/33, Summer 1933/34, Summer 1934/35, Summer 1935/36, Summer 1936/37, +28 more |
| PlayCricket only seasons | 7 | Summer 1980/81, Summer 1992/93, Summer 1996/97, Summer 2022/23, Summer 2023/24, Summer 2024/25, Summer 2025/26 |
| Both-source seasons | 50 | Summer 1968/69, Summer 1969/70, Summer 1970/71, Summer 1971/72, Summer 1972/73, Summer 1973/74, Summer 1974/75, Summer 1975/76, +42 more |
| Seasons with batting overlap | 50 | |
| Seasons with bowling overlap | 2 | |
| Seasons with PlayCricket fielding only | 7 | |

## Metric Coverage

- Safe from clean Excel: matches, innings, not_outs, runs, high_score, batting_average, 50s, 100s, ducks, matches, overs, balls, maidens, bowling_runs_conceded, wickets, bowling_average, economy, bowling_strike_rate.
- Safe from sane PlayCricket / PlayHQ aggregates: matches, innings, not_outs, runs, high_score, batting_average, batting_strike_rate, balls_faced, 50s, 100s, ducks, fours, sixes, matches, overs, balls, maidens, bowling_runs_conceded, wickets, bowling_average, economy, bowling_strike_rate, best_bowling, bbi_wickets, bbi_runs, 5wi, 10wm, catches.
- Ball-by-ball-only metrics such as fastest 50/100, dot-ball rates, balls per boundary and phase metrics must remain verified-ball-by-ball-only.
- Excel BBI, 3WI, 5WI and 10WM should remain unavailable unless explicitly present and manually verified.

## Source Priority Rules

1. PlayCricket / PlayHQ is preferred for modern/current aggregate records where rows are sane.
2. Excel is preferred for historical seasons missing from PlayCricket / PlayHQ.
3. In overlap seasons, use manual source priority review if both sources materially differ.
4. Excel is never used for BBB-only metrics.
5. Any high-severity anomaly is excluded unless manually approved.

## Known Risks / Manual Review

- PlayCricket / PlayHQ anomaly findings remain in the review exports: 1723 issue rows.
- Excel review/rejected rows: 1139 review, 308 rejected.
- Duplicate/player identity risks: 13 rows.
- Seasons with overlapping source coverage needing source-priority review: 50.
- Metrics with incomplete or unavailable coverage should remain N/A rather than inferred.

## Recommended Next Step

- Use this report and the season coverage CSV to decide source priority by season.
- Inspect overlap seasons first, especially seasons with both batting and bowling coverage.
- Do not block private preview on P2 duplicate/identity items unless they affect headline records.

## Output Files

- `clubs/georges-river-district/data/processed/validation/source_coverage/grdcc_source_coverage_by_season.csv`
- `clubs/georges-river-district/data/processed/validation/source_coverage/grdcc_source_coverage_by_metric.csv`
- `clubs/georges-river-district/data/processed/validation/source_coverage/grdcc_source_coverage_by_player.csv`
- `clubs/georges-river-district/data/processed/validation/source_coverage/grdcc_source_overlap_summary.csv`
