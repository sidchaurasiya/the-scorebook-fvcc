# GRDCC Season Overview Layout and Grade Update

## Purpose
This update keeps the GRDCC Season Overview compact when a season has many grades or teams, while preserving the existing season and team/grade dropdown slicers.

## Season By Round Selector
The Season by Round grade/team selector now uses a horizontal scroll control instead of wrapped folder-style tabs. The selected grade remains styled, and the list can scroll left-to-right when many competitions are available.

## Duplicate Competition Teams
When GRDCC fields multiple teams in the same competition in the same season, the app combines those teams into one competition view for Season by Round and Team/Grade Leaders. Raw source rows are unchanged.

Example: Summer 2025/26 Chappelow Cup teams are displayed as one Chappelow Cup competition view.

## Grade Ordering
Season Overview selectors and grade sections prefer this ordering when grades are present:

1. First Grade
2. Second Grade
3. Third Grade
4. Fourth Grade
5. Fifth Grade
6. First Grade Limited Overs
7. Frank Gray Shield

Remaining grades follow after the preferred grades.

## Empty Grade Exclusion
Grade/team options with no matches, batting rows, bowling rows, or fielding rows for the selected season are excluded from the display. This avoids empty options such as O65s Regionals in Summer 2025/26 when no usable rows are present.

## Bowling Extras Columns
The Season Overview detailed Bowling table now includes No Balls and Wides near the end of the table. Historical or unavailable values display as blank cells rather than `N/A`.

## Caveats
Historical Excel seasons may not include no-balls or wides. These fields remain blank where the source does not provide them.
