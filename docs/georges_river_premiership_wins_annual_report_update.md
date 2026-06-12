# Georges River Premiership Wins Annual Report Update

## Source

- GRDCC 2024/25 Annual Report, page 9, `Premierships` honours table.
- Pages 16, 25, 77 and 83 corroborate the Summer 2024/25 Vintage premiership.

## Reconciliation

- Annual Report premiership wins extracted: **22**.
- Existing scorecard-backed app wins: **10**.
- Existing wins retained without duplication: **10**.
- Annual Report honours added: **12**.
- Final GRDCC Premiership Wins count: **22**.
- Low-confidence or manual-review rows: **0**.

`Fifth Grade` in the Annual Report is treated as equivalent to the existing `Tim Creer Cup` label for Summer 2008/09. The scorecard-backed app row is retained, preventing a duplicate honour.

## Data Behaviour

The verified Hall of Fame `premiership_wins.csv` remains unchanged. A separate GRDCC source file contains the official Annual Report honours, and the app merges missing season/grade combinations at display time. Annual Report-only rows do not fabricate opponents, captains, scorecards or match IDs from PlayCricket.

## Sorting And UI

- Premiership wins sort by season descending, latest first.
- The latest seven wins are immediately visible.
- The remaining fifteen wins appear in a compact scrollable `Earlier premierships` area.
- Annual Report-only entries display as official club honours rather than inventing match details.
- A subtle `Source: GRDCC 2024/25 Annual Report` note appears in the GRDCC card.
