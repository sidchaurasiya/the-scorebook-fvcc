# GRDCC Final Private Preview Audit

## Final Source Rule

- Historical Excel is used through `Summer 1971/72`.
- PlayCricket / PlayHQ is used from `Summer 1972/73` onward.
- The app never sums both sources for the same player-season.
- Fielding remains PlayCricket-only, and delivery-level metrics remain verified-ball-by-ball-only.

## Final Coverage

| Coverage | Final App-Facing Count |
|---|---:|
| Excel seasons | 39 |
| PlayCricket seasons | 53 |
| Batting seasons | 92 |
| Bowling seasons | 77 |
| Fielding seasons | 57 |
| Excel batting rows | 1,586 |
| Excel bowling rows | 344 |
| PlayCricket batting rows | 7,735 |
| PlayCricket bowling rows | 7,681 |
| PlayCricket fielding rows | 7,746 |

Boundary checks:

- `Summer 1971/72`: 40 batting rows from Excel; no clean bowling rows are available for that season.
- `Summer 1972/73`: 42 batting and 42 bowling rows from PlayCricket.

## Data Quality Checks

- Duplicate normalized player-season conflicts across Excel and PlayCricket: 0.
- Source-priority validation failures: 0.
- Odd-stat findings after app-facing filters: 1.
- Preview-blocking odd-stat findings: 0.
- Explicit regressions pass: H Jolly is not exposed with 924 wickets, and Nathan Percy does not aggregate to 101 or more wickets in `Summer 1995/96`.
- The remaining review-later finding is Darren Smith's PlayCricket batting average of 322.00 in `Summer 2013/14`; it is plausible from the supplied aggregate denominators and is not structurally impossible.
- Invalid player labels, impossible batting denominator relationships and high-severity bowling anomalies are excluded at the GRDCC app-facing loader boundary.
- Exact match counts remain unavailable because no populated match-level source file exists.

## Remaining Review-Later Items

- Overlap discrepancy rows remain available for historical review, but the fixed season cutoff removes mixed-source ambiguity from the app.
- GRDCC may review historical differences later without blocking the private preview.
- No review-later discrepancy is currently permitted to combine both sources or override the final season boundary.

## Preview Readiness

GRDCC is private-preview ready under the final source rule. The final validation found no source conflicts, no boundary failures and no preview-blocking odd statistics.

## Smoke Results

- GRDCC and FVCC Streamlit servers returned HTTP 200 with no server tracebacks.
- Streamlit `AppTest` completed Season Overview and Player Profile routes with zero exceptions under GRDCC.
- Streamlit `AppTest` completed Player Profile with zero exceptions under FVCC.
- Hall of Fame, Home and Milestone route harnesses terminate at Streamlit's page-stop boundary before emitting the test footer; the running servers remained healthy with no traceback. The in-app browser connection was unavailable for an additional visual pass.
