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

The verified Hall of Fame `premiership_wins.csv` remains unchanged. A separate GRDCC source file contains the official Annual Report honours, and the app merges missing season/grade combinations at display time. The Annual Report remains authoritative for whether the premiership was won; local PlayCricket data is supporting match context only.

For Summer 2008/09 onward, the merge checks the local Season by Round scorecard data by season and normalized grade:

- A clearly labelled Grand Final retains normal opponent, margin and scorecard treatment.
- A finals row without an explicit Grand Final label is included with medium confidence.
- If no final exists, the latest available match is labelled `Last available PlayCricket match` and is not represented as the premiership final.
- If no matching local row exists, the honour remains Annual Report-only.
- Captains are retained only from the existing verified Hall of Fame source; they are not inferred from the fallback match list.

## Sorting And UI

- Premiership wins sort by season descending, latest first.
- The full list is one continuous scrollable container; no rows are sticky or fixed.
- The card height exposes approximately the latest seven wins before scrolling.
- There is no separate `Earlier premierships` subsection.
- Annual Report-only entries display as official club honours rather than inventing match details.
- A subtle `Source: GRDCC 2024/25 Annual Report` note appears in the GRDCC card.
