# GRDCC HOF Supplements And Scroll Update

## Scope

This update is limited to the Georges River District Cricket Club Hall of Fame page.

## Scroll Behaviour

- Premiership Wins now targets 6 visible rows on desktop, with the remaining rows available in one continuous internal scroll area.
- Premiership Wins now targets 5 visible rows on mobile, with the remaining rows available in one continuous internal scroll area.
- Most Premierships now targets 5 visible rows on mobile, while the current desktop layout and height remain unchanged.

## Stats Table Blank Cells

- GRDCC Hall of Fame detailed stats tables now render unavailable values as blank cells instead of `N/A`.
- This is a display-only cleanup.
- Legitimate numeric zero values are preserved.

## Annual Report Override Player Supplements

- Players with approved GRDCC Annual Report all-time override decisions now receive Historical Excel-derived supporting career fields where available.
- Career runs and career wickets still follow the existing override rule:
  - use the combined Annual Report value only when it is higher than the source-rule derived total
  - otherwise keep the source-rule derived total
- Supplement fields include, where available:
  - seasons
  - matches
  - innings
  - not outs
  - high score
  - batting average
  - 50s
  - 100s
  - wickets
  - overs / balls
  - maidens
  - bowling average
  - bowling strike rate

## Matches Proxy Caveat

- Historical Excel matches use the explicit Excel `matches` field where available.
- If `matches` is unavailable, a conservative innings-based proxy is used only when season totals provide enough context.
- The proxy uses:
  - player innings
  - season total matches
  - season maximum innings
- Proxy values are capped to the known season total matches.

## 50s / 100s Caveat

- Explicit Excel 50s and 100s are used when present.
- If they are unavailable, a conservative minimum is derived from season high score only:
  - HS >= 100 adds one century for that season
  - 50 <= HS < 100 adds one fifty for that season
- These derived values are minimums only and are traceable in the supplement CSV.

## Iconic Performances Excel Coverage

- Iconic Performances already evaluates the final app-facing raw batting and bowling tables.
- That means GRDCC Historical Excel rows remain eligible through the final source-rule split:
  - Excel through Summer 1971/72
  - PlayCricket / PlayHQ from Summer 1972/73 onward
- No unsupported ball-by-ball-only Excel fields are used.
- Annual Report highest score / BBI candidate extracts remain out of scope for display until explicitly approved.
