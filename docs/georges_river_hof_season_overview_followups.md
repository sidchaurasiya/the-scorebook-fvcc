# GRDCC HOF and Season Overview Follow-ups

## HOF Player Link Colour
GRDCC Hall of Fame player names in All-Time Leaders, Iconic Performances, and Fastest Innings now use the same GRDCC blue as scorecard links. Hover states use the same blue rather than purple or dark navy.

## Historical Matches Proxy
For Annual Report override players with Historical Excel-derived data and unreliable match counts, the app displays innings as the matches proxy with an asterisk. Example: Harry Milburn displays `412*`.

The table footnote remains:

`* Innings used where historical match counts are unavailable.`

Sorting uses the numeric proxy value, not the display string.

## Active Player Rule
GRDCC active-player indicators now use the latest two available seasons in app-facing data. Players are active only if they appeared in either of those seasons. This prevents older players such as Paul Thomas, whose latest season is Summer 2021/22, from being shown as active.

## Season By Round Panels
Season by Round no longer uses an internal grade filter. It renders grade/competition panels in a horizontal scroll strip ordered by preferred grade order:

1. First Grade
2. Second Grade
3. Third Grade
4. Fourth Grade
5. Fifth Grade
6. First Grade Limited Overs
7. Frank Gray Shield

Duplicate same-season/same-competition teams are combined into one panel, and empty grades remain excluded.

## Bowling Extras Placement
The Season Overview Bowling table now places extras columns after wicket milestones:

`... BBI, 3WI, 5WI, No Balls, Wides`

No Balls and Wides use compact numeric column widths. Missing values remain blank.

## Caveats
Historical Excel does not reliably capture every modern scorecard detail. No raw source data or source-priority rule was changed.
