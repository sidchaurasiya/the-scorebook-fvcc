# Georges River Excel Ingestion Quality Report

## Coverage

- Workbook: `clubs/georges-river-district/data/source/bexley_stats_spreadsheets.xlsx`
- Sheets scanned: 94
- Nonblank rows read: 6269
- Seasons detected: Summer 1929/30 through Summer 2021/22
- Distinct player names detected: 2115

## QA Counts

- Clean rows feeding app-safe supplemental records: 5335
- Review rows excluded pending manual review: 1139
- Rejected rows excluded from records: 308
- Column mapping issues found: 5
- Reconciliation issues found: 1294
- Outlier / validation issues found: 3203

## H Jolly Regression

- Result: found in clean bowling output with wickets `81`, runs conceded `924`, average `11.40740741`.
- Expected interpretation: `924` is bowling runs conceded and `81` is wickets, producing an average of about `11.41`.
- The clean app-facing bowling output must never contain `924` as H Jolly's wickets value.

## Safe To Show In App

- Clean Excel batting and bowling season-summary rows can feed aggregate records only.
- App-facing Excel supplemental files are `excel_all_seasons_batting.csv` and `excel_all_seasons_bowling.csv`; both are generated from clean/approved rows only.
- `excel_player_season_summary.csv` is audit/context output only and is not read by the app supplemental loader.
- `excel_review_rows.csv`, `excel_rejected_rows.csv`, and `excel_outlier_audit.csv` are not app-facing.
- Excel data remains barred from fastest milestones, dot-ball metrics, phase metrics, balls-per-boundary, and other ball-by-ball-only outputs.
- Review and rejected Excel rows must not feed Best Batting Season, Best Bowling Season, Record Holders, Hall of Fame leaders, Greatest Individual Seasons, Player Profile headline records, or milestones.

## Nathan Percy 101-Wicket Card Trace

- Root cause: the visible `Nathan Percy`, `Summer 1995/96`, `101 wickets` Best Bowling Season card was not produced by Excel. It came from primary processed PlayCricket aggregate rows in `clubs/georges-river-district/data/processed/all_seasons_bowling.csv`.
- Exact source rows: line `6163` had Nathan Percy, First Grade, `90` wickets, `2` runs conceded, `156` balls, BBI `1-45`, average `0.02`, economy `0.08`; line `6219` had Nathan Percy, Second Grade, `11` wickets, `214` runs conceded, `435` balls.
- Transformation step: Hall of Fame loaded `all_seasons_bowling` through `read_processed_table`, then `best_bowling_season` grouped by canonical player and season. The invalid `90` wickets plus the valid `11` wickets aggregated to the visible `101 wickets`.
- Fix: GRDCC app-facing primary bowling rows now pass a sanity gate before supplemental Excel rows are appended. It excludes impossible bowling rows where BBI wickets exceed season wickets, wickets exceed balls, wickets have zero balls, high wicket counts have fewer runs than wickets, derived average is below `1`, or derived economy is below `0.5` over a meaningful workload.
- Validation: `scripts/validate_grdcc_excel_app_outputs.py` now mirrors the app-facing load path, verifies audit/review Excel files are not loader sources, and fails if Nathan Percy `Summer 1995/96` still aggregates to `101+` wickets.
- Result: the invalid Nathan Percy `90`-wicket source row is excluded from app-facing records. Nathan Percy remains visible for `Summer 1995/96` only through the traceable `11`-wicket PlayCricket row.

## Manual Review Required

- Rows in `excel_review_rows.csv` need GRDCC/client review before they can be promoted.
- `excel_manual_approvals.csv` is header-only until explicit manual decisions are documented.
- Team/grade names in the workbook are conservative and should not be treated as definitive grade evidence without review.

## Top 30 Suspicious Records

| Player | Season | Group | Metric | Value | Severity | Reason |
|---|---|---|---|---:|---|---|
| 1 | Summer 1980/81 | batting | battingNotOuts | 16.0 | high | Not-outs cannot exceed innings. |
| 1 | Summer 1996/97 | batting | battingNotOuts | 15.0 | high | Not-outs cannot exceed innings. |
| 1 | Summer 1980/81 | batting | not_outs_not_above_innings | 16.0 | high | not_outs_not_above_innings cannot exceed innings. |
| 1 | Summer 1996/97 | batting | not_outs_not_above_innings | 15.0 | high | not_outs_not_above_innings cannot exceed innings. |
| 1 | Summer 1980/81 | batting | numeric_only_player_name | 1 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 1 | Summer 1992/93 | batting | numeric_only_player_name | 1 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 1 | Summer 1996/97 | batting | numeric_only_player_name | 1 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 10 | Summer 1935/36 | batting | numeric_only_player_name | 10 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 10 | Summer 1980/81 | batting | numeric_only_player_name | 10 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 10 | Summer 1992/93 | batting | numeric_only_player_name | 10 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 10 | Summer 1996/97 | batting | numeric_only_player_name | 10 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 11 | Summer 1980/81 | batting | battingNotOuts | 11.0 | high | Not-outs cannot exceed innings. |
| 11 | Summer 1992/93 | batting | battingNotOuts | 11.0 | high | Not-outs cannot exceed innings. |
| 11 | Summer 1980/81 | batting | not_outs_not_above_innings | 11.0 | high | not_outs_not_above_innings cannot exceed innings. |
| 11 | Summer 1992/93 | batting | not_outs_not_above_innings | 11.0 | high | not_outs_not_above_innings cannot exceed innings. |
| 11 | Summer 1980/81 | batting | numeric_only_player_name | 11 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 11 | Summer 1992/93 | batting | numeric_only_player_name | 11 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 11 | Summer 1996/97 | batting | numeric_only_player_name | 11 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 11 4 | Summer 1935/36 | batting | battingNotOuts | 3.0 | high | Not-outs cannot exceed innings. |
| 11 4 | Summer 1935/36 | batting | not_outs_not_above_innings | 3.0 | high | not_outs_not_above_innings cannot exceed innings. |
| 12 | Summer 1992/93 | batting | battingNotOuts | 10.0 | high | Not-outs cannot exceed innings. |
| 12 | Summer 1996/97 | batting | battingNotOuts | 15.0 | high | Not-outs cannot exceed innings. |
| 12 | Summer 1992/93 | batting | not_outs_not_above_innings | 10.0 | high | not_outs_not_above_innings cannot exceed innings. |
| 12 | Summer 1996/97 | batting | not_outs_not_above_innings | 15.0 | high | not_outs_not_above_innings cannot exceed innings. |
| 12 | Summer 1980/81 | batting | numeric_only_player_name | 12 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 12 | Summer 1992/93 | batting | numeric_only_player_name | 12 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 12 | Summer 1996/97 | batting | numeric_only_player_name | 12 | high | Numeric-only player names are likely row numbers or batting-order values. |
| 12 3 | Summer 1939/40 | batting | battingNotOuts | 2.0 | high | Not-outs cannot exceed innings. |
| 12 3 | Summer 1939/40 | batting | not_outs_not_above_innings | 2.0 | high | not_outs_not_above_innings cannot exceed innings. |
| 12 4 | Summer 1936/37 | batting | battingNotOuts | 7.0 | high | Not-outs cannot exceed innings. |
