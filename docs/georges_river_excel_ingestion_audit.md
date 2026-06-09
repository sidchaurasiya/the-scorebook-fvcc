# Georges River DCC Excel Ingestion Audit

## Source

- Club: Georges River DCC / Georges River District Cricket Club
- Club ID: `georges-river-district`
- Source workbook: `clubs/georges-river-district/data/source/bexley_stats_spreadsheets.xlsx`
- Generated sheet audit CSV: `clubs/georges-river-district/data/processed/supplemental/excel_workbook_sheet_audit.csv`
- Ingestion script: `scripts/ingest_grdcc_excel_stats.py`

## Workbook Summary

- Sheets processed: 94
- Nonblank rows read: 6,269
- Accepted player-season summary rows: 5,928
- Rejected rows: 0
- Seasons detected from sheet names: Summer 1929/30 through Summer 2021/22
- Distinct player names detected: 2,115
- Empty annual sheets detected: `1941-42`, `1942-43`, `1943-44`, `1945-46`
- Workbook appears to contain historical season summary statistics, not match scorecards or ball-by-ball records.

## Sheet Names

`Intro`, `1929-30`, `1930-31`, `1931-32`, `1932-33`, `1933-34`, `1934-35`, `1935-36`, `1936-37`, `1937-38`, `1938-39`, `1939-40`, `1940-41`, `1941-42`, `1942-43`, `1943-44`, `1944-45`, `1945-46`, `1946-47`, `1947-48`, `1948-49`, `1949-50`, `1950-51`, `1951-52`, `1952-53`, `1953-54`, `1954-55`, `1955-56`, `1956-57`, `1957-58`, `1958-59`, `1959-60`, `1960-61`, `1961-62`, `1962-63`, `1963-64`, `1964-65`, `1965-66`, `1966-67`, `1967-68`, `1968-69`, `1969-70`, `1970-71`, `1971-72`, `1972-73`, `1973-74`, `1974-75`, `1975-76`, `1976-77`, `1977-78`, `1978-79`, `1979-80`, `1980-81`, `1981-82`, `1982-83`, `1983-84`, `1984-85`, `1985-86`, `1986-87`, `1987-88`, `1988-89`, `1989-90`, `1990-91`, `1991-92`, `1992-93`, `1993-94`, `1994-95`, `1995-96`, `1996-97`, `1997-98`, `1998-99`, `1999-00`, `2000-01`, `2001-02`, `2002-03`, `2003-04`, `2004-05`, `2005-06`, `2006-07`, `2007-08`, `2008-09`, `2009-10`, `2010-11`, `2011-12`, `2012-13`, `2013-14`, `2014-15`, `2015-16`, `2016-17`, `2017-18`, `2018-19`, `2019-20`, `2020-21`, `2021-22`.

## Detected Column Structures

The workbook uses two main season-summary shapes:

- Early annual sheets, generally `1929-30` to `1974-75`: `First Name`, `Surname`, `Games`, `Inns`, `NO`, `HS`, `Total`, `Ave`, spacer columns, `Overs`, `Mdns`, `Runs`, `Wkts`, `Ave`; some sheets also include `Catches`.
- Later annual sheets, generally `1975-76` to `2021-22`: `PLAYER`, `MAT`, `INN`, `NO`, `100S`, `50S`, `0S`, `4S`, `6S`, `MINS`, `HS`, `RUNS`, `AVE.`, `STR.`
- The `Intro` sheet contains workbook notes only.

Full per-sheet row counts and detected column names are preserved in `excel_workbook_sheet_audit.csv`.

## Content Classification

- Batting summaries: detected on 89 annual sheets.
- Bowling summaries: detected on 42 early annual sheets.
- Fielding summary columns: detected on 21 early annual sheets, usually as catches.
- Match results: not detected.
- Scorecards: not detected.
- Ball-by-ball: not present.

## Detected Seasons

The importer detected annual season labels from `Summer 1929/30` through `Summer 2021/22`. Four annual sheets in that range were blank and retained only in the audit: `Summer 1941/42`, `Summer 1942/43`, `Summer 1943/44`, and `Summer 1945/46`.

The GRDCC pilot processed data already contains many modern seasons, so the app supplemental layer appends Excel rows only for seasons absent from the primary PlayCricket/PlayHQ processed tables.

## Detected Teams And Grades

The workbook mostly records club-level annual summaries rather than consistent team or grade sections. The importer therefore assigns retained rows to:

- `team_name`: `Georges River DCC`
- `grade_name`: original detected heading when safely present, otherwise `Historical club summary`
- `competition_name`: `Historical Excel`

Manual review is still needed before using these rows for grade-specific claims.

## Detected Player Names

The audit detected 2,115 distinct displayed player names. Original workbook names are preserved. Supplemental rows receive stable Excel-scoped IDs only, and no aggressive canonical merges are created by the importer.

## Obvious Issues And Caveats

- Blank spacer/header columns appear throughout the workbook.
- Several annual sheets are empty.
- Date-level match information is missing, so match results and scorecards cannot be produced from this workbook.
- Team/grade naming is not consistently structured.
- Duplicate real-world player identities may exist because names are preserved conservatively.
- Later sheets include batting strike-rate columns, but the workbook does not provide underlying ball-by-ball data. These values must not be used for BBB-only metrics.
- Excel-derived data must not feed fastest milestones, dot-ball rates, phase metrics, balls-per-boundary metrics, or any record that requires ball-by-ball proof.

## Deploy-Safe Supplemental Outputs

- `clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_batting.csv`
- `clubs/georges-river-district/data/processed/supplemental/excel_all_seasons_bowling.csv`
- `clubs/georges-river-district/data/processed/supplemental/excel_player_season_summary.csv`
- `clubs/georges-river-district/data/processed/supplemental/excel_rejected_rows.csv`
- `clubs/georges-river-district/data/processed/supplemental/excel_ingestion_summary.csv`
- `clubs/georges-river-district/data/processed/supplemental/excel_workbook_sheet_audit.csv`
