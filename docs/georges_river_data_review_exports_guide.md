# Georges River Data Review Exports Guide

This guide explains the decision-ready GRDCC anomaly review exports created for manual review before client preview.

## Review First

1. `clubs/georges-river-district/data/processed/validation/review_exports/playcricket_all_anomalies_decision_review_with_data.csv`
2. `clubs/georges-river-district/data/processed/validation/review_exports/playcricket_bowling_decision_review_with_data.csv`
3. `clubs/georges-river-district/data/processed/validation/review_exports/excel_all_anomalies_decision_review_with_data.csv`
4. `clubs/georges-river-district/data/processed/validation/review_exports/playcricket_duplicate_identity_decision_review_with_data.csv`

## Priority Meanings

- `P1`: Must resolve, approve, correct, or exclude before client preview.
- `P2`: Manual review needed. Preview can proceed only if the row is not app-facing dangerous.
- `P3`: Clean Excel row included for traceability. No decision required unless the reviewer spots an issue.

## App-Facing Status

- `excluded_from_app`: The row is already blocked from client-visible record calculations.
- `not_confirmed_safe`: The row is not confirmed safe and needs manual review before it should drive records.
- `feeds_app_records`: Clean row currently feeds safe aggregate records.
- `allowed_or_audit_only`: Audit row is allowed or informational only.

## Reviewer Decision Values

Use the blank `reviewer_decision` column with one of:

- `accept`
- `exclude`
- `correct`
- `merge_review`
- `needs_club_confirmation`
- `ignore_for_preview`

Use `reviewer_corrected_metric`, `reviewer_corrected_value`, and `reviewer_notes` when a correction is needed. Do not edit raw source files directly from these exports.

## Notes

- PlayCricket/PlayHQ exports include the grouped decision fields followed by normalized review fields and full `source_*` raw row columns.
- Excel exports include clean, review, and rejected row status so reviewers can see what is app-facing and what is audit-only.
- Rows marked `already_excluded_review_source` are currently blocked from app-facing records, but should still be reviewed if they represent source data that needs correction or source-provider escalation.
