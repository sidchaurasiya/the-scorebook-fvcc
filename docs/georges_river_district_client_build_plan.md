# Georges River District Client Build Plan

## Status

- Paid client: yes
- Build status: commencing full client-ready build
- Current branch: `client/georges-river-district-build`
- Base branch: `onboarding/multi-club-positive-responses`
- Club ID: `georges-river-district`
- Official PlayCricket ID: `a115d93f-87d8-eb11-a7ad-2818780da0cc`

## Branding Palette

| Token | Colour | Use |
|---|---|---|
| primary | `#0B3F9F` | Royal / deep blue brand anchor |
| primary_dark | `#082A66` | Navy sidebar and dark brand depth |
| secondary | `#79C8EE` | Light sky blue highlight |
| accent | `#D7193F` | Small red accent only |
| background | `#F3F9FD` | Very light blue-white page background |
| surface | `#FFFFFF` | Cards and panels |
| text | `#061A3D` | Main body text |
| muted_text | `#66758D` | Secondary and helper text |
| border | `#D8E8F5` | Card and table borders |
| positive | `#1B8A5A` | Success/positive states |
| negative | `#B23A48` | Errors/negative states |
| warning/gold | `#D6A732` | Trophy / premiership / award accents |

## Existing Pilot Status

- GRDCC already has a pilot club config and processed deploy-safe outputs.
- Latest processed season present locally: `Summer 2025/26`.
- Pilot state before this paid build: `Preview-ready with caveats`.
- Highest QA risk in the pilot notes: Georges River was called out as the highest-risk club after a malformed bowling row was fixed during final hardening.
- Client logo added at `clubs/georges-river-district/assets/logo.png`.
- Historical Excel source added at `clubs/georges-river-district/data/source/bexley_stats_spreadsheets.xlsx`.

## Historical Excel Supplement

- Workbook audited in `docs/georges_river_excel_ingestion_audit.md`.
- Workbook coverage: annual sheets from `1929-30` through `2021-22`, plus an intro sheet.
- Empty annual sheets: `1941-42`, `1942-43`, `1943-44`, `1945-46`.
- Ingestion output folder: `clubs/georges-river-district/data/processed/supplemental/`.
- Clean app-safe supplemental rows: 5,335.
- Review rows excluded pending manual review: 1,139.
- Rejected rows: 308.
- Distinct player names detected: 2,115.
- The workbook contains historical season summaries, not match scorecards or ball-by-ball data.
- Supplemental rows are club-scoped and appended only for GRDCC seasons not already present in primary processed PlayCricket / PlayHQ tables.
- Excel QA safeguards are active: 3,203 validation/outlier issues, 5 column-mapping issues, and 1,294 reconciliation issues are written to supplemental audit outputs.
- Numeric-only player names are excluded from app-facing Excel records unless manually approved.
- Known regression example: `H Jolly`, `Summer 1944/45`, source row `17`, had `924` in the early bowling runs column. The corrected parser treats this as runs conceded, maps wickets as `81`, and reconciles `924 / 81 = 11.41` against the source bowling average. The previous `924 wickets` issue is fixed at source and cannot feed headline records.
- QA report: `docs/georges_river_excel_ingestion_quality_report.md`.

## Excel-Safe Metrics

- Career runs, innings, not-outs, high score, 50s, 100s, ducks, and batting average where the workbook provides enough summary fields.
- Career wickets, overs, maidens, runs conceded, and bowling average where early workbook bowling fields are present.
- Season-summary tables, provided the source is treated as `Historical Excel`.
- Only rows passing the Excel mapping, reconciliation, and outlier gates should feed Hall of Fame / Record Holders / Greatest Seasons style cards.

## PlayCricket / Ball-By-Ball Only Metrics

- Fastest 50s / 100s.
- Delivery-level batting strike rate unless the source row is later proven from scorecard balls faced.
- Batting dot-ball percentage.
- Bowling dot-ball percentage.
- Balls per boundary.
- Phase metrics.
- Any scorecard-link, match-result, or milestone claim requiring match-level evidence.
- Any Excel row flagged high or medium severity in `excel_outlier_audit.csv` until manually approved.
- Any Excel row in `excel_review_rows.csv` or `excel_rejected_rows.csv`.

## Known Pilot Caveats

- Duplicate player review is still needed for ambiguous merges.
- Team and grade naming still needs a human pass, especially where club and opponent labels are similar.
- Opponent and ground mappings are conservative and not fully complete.
- Premiership and captain evidence should stay strictly verified from finals / Grand Final scorecards.
- Women / men classification should be checked against the local data shape before exposing any toggle assumptions.
- Fastest innings records must remain validated against ball-by-ball progression only.
- Win-rate denominators should stay explicit so missing coverage does not become a fake zero.
- Scorecard links should be spot-checked on the live app before sharing.
- Mobile layout should get one final visual check before client preview.
- Historical Excel rows use conservative Excel-scoped IDs; manual alias/merge review remains required before client-facing all-time record sign-off.
- Workbook team/grade labels are inconsistent or absent, so grade-specific claims from Excel need manual evidence.
- Player Profile selectable lists exclude masked/hidden players and the Excel supplemental player identities until duplicate and alias QA is complete.

## Highest-Risk Review Items Before Client Share

1. Duplicate profiles.
2. Team / grade naming.
3. Opponent / ground mappings.
4. Premiership and captain evidence.
5. Women / men classification, if applicable.
6. Scorecard link spot checks.
7. Fastest innings validation.
8. Win-rate denominator clarity.
9. Mobile smoke check.

## Proposed Next Phases

1. Branding and theme pass.
2. Data QA and mapping review.
3. GRDCC-specific smoke and UAT.
4. Client preview deployment.
5. Post-client feedback fixes.

## Notes

- Keep `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false`.
- Do not stage raw or debug/generated review-pack files.
- Do not fabricate premierships, captaincy, duplicate merges, or mapping rows.
- Do not fall back to FVCC data for non-FVCC clubs.
