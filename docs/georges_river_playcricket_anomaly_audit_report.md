# Georges River PlayCricket/PlayHQ Anomaly Audit

## Rows Scanned

- `clubs/georges-river-district/data/processed/all_seasons_batting.csv`: 7789
- `clubs/georges-river-district/data/processed/all_seasons_bowling.csv`: 7789
- `clubs/georges-river-district/data/processed/all_seasons_fielding.csv`: 7789
- `clubs/georges-river-district/data/processed/all_seasons_matches.csv`: 0

## Severity Counts

- High: 295
- Medium: 1428
- Low: 0

## Issue Code Counts

- `duplicate_batting_player_season_grade`: 472
- `duplicate_bowling_player_season_grade`: 352
- `batting_strike_rate_gt_300`: 335
- `duplicate_fielding_player_season_grade`: 202
- `invalid_player_name`: 129
- `app_facing_primary_bowling_excluded`: 57
- `bowling_average_gt_100`: 41
- `bbi_wickets_gt_total_wickets`: 32
- `balls_lt_wickets_x2`: 20
- `wickets_gt_balls`: 16
- `wickets_with_zero_overs`: 16
- `same_name_season_multiple_canonical_ids`: 13
- `strike_rate_lt_3`: 7
- `bowling_average_lt_1`: 5
- `economy_lt_0_5`: 5
- `runs_lte_wickets_high_workload`: 4
- `high_score_gt_runs`: 3
- `bbi_runs_gt_total_runs`: 3
- `batting_average_gt_250`: 2
- `maidens_gt_overs`: 2
- `strike_rate_gt_300`: 2
- `wickets_ge_50_runs_le_10`: 2
- `wickets_gt_80`: 2
- `runs_with_zero_innings`: 1

## Top 30 High-Severity Records

| Source | Row | Player | Season | Group | Metric | Value | Issue | Severity | Action |
|---|---:|---|---|---|---|---:|---|---|---|
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 25 | ******** | Summer 2025/26 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 87 | ******** | Summer 2025/26 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 266 | ******** | Summer 2025/26 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 270 | ******** | Summer 2025/26 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 283 | ******** | Summer 2025/26 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 288 | ******** | Summer 2025/26 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 388 | ******** | Summer 2024/25 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 499 | ******** | Summer 2024/25 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 528 | ******** | Summer 2024/25 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 547 | ******** | Summer 2024/25 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 572 | ******** | Summer 2024/25 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 585 | ******** | Summer 2024/25 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 777 | ******** | Summer 2023/24 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 793 | ******** | Summer 2023/24 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 825 | ******** | Summer 2023/24 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 836 | ******** | Summer 2023/24 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 846 | ******** | Summer 2023/24 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1004 | ******** | Summer 2022/23 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1030 | ******** | Summer 2022/23 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1032 | ******** | Summer 2022/23 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1049 | ******** | Summer 2022/23 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1125 | ******** | Summer 2021/22 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1291 | ******** | Summer 2021/22 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1344 | ******** | Summer 2020/21 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1448 | ******** | Summer 2020/21 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1510 | ******** | Summer 2020/21 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1543 | ******** | Summer 2019/20 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1660 | ******** | Summer 2019/20 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1733 | ******** | Summer 2019/20 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 1960 | ******** | Summer 2018/19 | batting | player_name | ******** | invalid_player_name | high | exclude_from_records |

## Top 30 Medium-Severity Records

| Source | Row | Player | Season | Group | Metric | Value | Issue | Severity | Action |
|---|---:|---|---|---|---|---:|---|---|---|
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 9 | Venkateswara Reddy Avula | Summer 2025/26 | batting | battingStrikeRate | 1050.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 88 | Khurram Mahmood | Summer 2025/26 | batting | battingStrikeRate | 573.68 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 92 | Jose Villa | Summer 2025/26 | batting | battingStrikeRate | 916.67 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 100 | Naveed Aslam | Summer 2025/26 | batting | battingStrikeRate | 580.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 110 | Darren Smith | Summer 2025/26 | batting | battingAverage | 302.0 | batting_average_gt_250 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 110 | Darren Smith | Summer 2025/26 | batting | battingStrikeRate | 308.16 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 112 | Scott Sigmond | Summer 2025/26 | batting | battingStrikeRate | 856.25 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 113 | Edward Gray | Summer 2025/26 | batting | battingStrikeRate | 1172.73 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 114 | george hodgson | Summer 2025/26 | batting | battingStrikeRate | 678.95 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 115 | John Adamson | Summer 2025/26 | batting | battingStrikeRate | 963.64 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 116 | Peter Remfrey | Summer 2025/26 | batting | battingStrikeRate | 365.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 123 | Vince Ungvary | Summer 2025/26 | batting | battingStrikeRate | 900.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 127 | Adam Scott | Summer 2025/26 | batting | battingStrikeRate | 800.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 256 | Dean Elliott | Summer 2025/26 | batting | battingStrikeRate | 560.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 291 | Tasbeeh Hossain | Summer 2025/26 | batting | battingStrikeRate | 2350.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 428 | Scott Sigmond | Summer 2024/25 | batting | battingStrikeRate | 3040.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 429 | Lindsay Le Bas | Summer 2024/25 | batting | battingStrikeRate | 986.67 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 432 | george hodgson | Summer 2024/25 | batting | battingStrikeRate | 1000.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 433 | Edward Gray | Summer 2024/25 | batting | battingStrikeRate | 618.75 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 435 | Kevin Croom | Summer 2024/25 | batting | battingStrikeRate | 556.25 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 436 | Ian Pryde | Summer 2024/25 | batting | battingStrikeRate | 612.5 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 439 | Gregory Thomas | Summer 2024/25 | batting | battingStrikeRate | 311.11 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 445 | Vince Ungvary | Summer 2024/25 | batting | battingStrikeRate | 900.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 579 | Muhammad Faisal | Summer 2024/25 | batting | battingStrikeRate | 332.81 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 581 | sohail sarwar | Summer 2024/25 | batting | battingStrikeRate | 469.7 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 590 | Mohammed Ismail | Summer 2023/24 | batting | battingStrikeRate | 342.67 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 593 | Manish Subramanian | Summer 2023/24 | batting | battingStrikeRate | 421.62 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 594 | Vinoth Kumar | Summer 2023/24 | batting | battingStrikeRate | 436.36 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 596 | Rameshraja Deenadayalan | Summer 2023/24 | batting | battingStrikeRate | 396.0 | batting_strike_rate_gt_300 | medium | needs_manual_review |
| clubs/georges-river-district/data/processed/all_seasons_batting.csv | 597 | Srikanth Thirumalachari | Summer 2023/24 | batting | battingStrikeRate | 576.47 | batting_strike_rate_gt_300 | medium | needs_manual_review |

## Bowling Seasons Over 70 Wickets

| Player | Season | Team | Grade | Metric | Value |
|---|---|---|---|---|---:|
| Nathan Percy | Summer 1995/96 | First Grade | First Grade | bowlingWickets | 90.0 |
| Robert Southwell | Summer 1994/95 | First Grade | First Grade | bowlingWickets | 88.0 |

## Batting Seasons Over 1000 Runs

- None.

## Duplicate And Identity Risks

- Duplicate / identity audit rows: 13
- These are report-only. No player merges were created or changed.

## Nathan Percy Root Cause And Status

- The `Nathan Percy`, `Summer 1995/96`, `101 wickets` Hall of Fame card came from primary processed PlayCricket bowling data, not Excel.
- Source row line `6163` in `all_seasons_bowling.csv` has `90` wickets, `2` runs conceded, `156` balls, BBI `1-45`, average `0.02`, and economy `0.08`.
- Source row line `6219` has a plausible `11` wickets and `214` runs conceded.
- Current app-facing status: raw rows=2 raw_wickets=101 app_facing_after_filter=11.

## John Young Current Best Bowling Season Trace

- Current trace status: rows=2 app_facing_wickets=80.
- John Young `Summer 1975/76` is the current app-facing Best Bowling Season after the Nathan Percy anomaly is filtered.

## Recommended Manual Decisions Before Client Preview

- Review all high-severity bowling contradictions before promoting any affected records.
- Decide whether app-facing filtered PlayCricket rows should be corrected, permanently excluded, or escalated to source-provider review.
- Review bowling seasons above 70 wickets and batting seasons above 1000 runs as plausible-but-high workloads.
- Review duplicate/player identity rows before merging or renaming players.
