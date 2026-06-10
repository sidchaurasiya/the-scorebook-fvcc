# Georges River Source Priority Decision

## Final Decision

Decision date: June 10, 2026.

- Historical Excel is the source of truth through `Summer 1971/72`.
- PlayCricket / PlayHQ is the source of truth from `Summer 1972/73` onward.
- Excel and PlayCricket rows are never summed for the same player-season.
- The rule is applied with chronological season sort keys, not string comparison.

## Reason

- Historical Excel provides the strongest available coverage for the club's earlier seasons.
- PlayCricket / PlayHQ provides structured modern batting, bowling and fielding coverage.
- A fixed boundary removes overlap ambiguity and prevents double counting.
- Modern PlayCricket rows remain subject to the GRDCC anomaly filters.

## Caveats

- Exact match counts remain unavailable unless reliable match-level files exist; they are not inferred from player-season rows.
- Historical Excel has no app-facing fielding source.
- Fastest milestones, dot-ball rates, phase metrics, balls per boundary and other delivery-level metrics require verified ball-by-ball rows.
- Known high-severity anomalies remain excluded. Other historical discrepancies and plausible statistical outliers remain review-later items.
