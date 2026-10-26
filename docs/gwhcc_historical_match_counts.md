# GWHCC dated historical match counts

This local candidate corrects only Chris Briginshaw and Matthew Briginshaw.
It does not approve other historical games rows or change the 63 existing
batting/bowling career anchors. Production release requires separate approval.

## Authority and cutoff

`gwhcc_dated_match_anchors.csv` records explicit public canonical IDs and closed
full-club career totals through Summer 2025/26. Only `approved_dated_career`
with high/confirmed/approved confidence applies. Review/rejected/unknown rows
remain audit-only. The original `gwhcc_record_overrides.csv` rows stay review.

- Chris: GH Sheet1 B107 = 390.5, AE107 `3+0/2+386+3/2`; original 2025-2026
  Senior Sheet1 K8/AC8 and Leading Players 2025-26 games table corroborate.
- Matthew: GH Sheet1 B109 = 296, AE109 `1+0/2+295+0/2`; original Senior
  Sheet1 K9/AC9 and the same Leading Players table corroborate.

The two formulas have zero legacy other-one-day half credits. Historical
full-career credit is retained as supplied, not reconstructed from incomplete
digital seasons. New eligible matches follow the club's June policy:
T20 0.5, played non-T20 1, no-play 0.

## Non-overlap rule

Authoritative Matches = the closed career anchor plus finalized, governed
annual appearance counts strictly after its cutoff. The annual source grain
is canonical ID / season ID / team ID / grade ID; duplicates, unknown counts,
invalid seasons, negative counts or non-half credits fail closed. Batting
innings, raw provider match counters and wins do not supply match counts.

In the released 37-match snapshot, both players have one unique eligible
2026/27 appearance: the finalized 10 October D Grade match against Kerrimuir
United, match `75c15b5e-5677-4838-81ba-3837124bfabd`. Therefore Chris is
390.5 + 1 = 391.5 and Matthew is 296 + 1 = 297. Matthew's two wickets do
not represent two appearances.

The 2025/26 games already overlap the career source and are never added again.
Chris's annual source 9-versus-digital-10 discrepancy remains unresolved in
the detailed season tables; it does not replace the independently confirmed
closed career total. No historical scorecards or annual/grade rows are made.

## Runtime and persistence

The central dated-career boundary applies the match decisions to HOF, profile,
and milestone frames after the digital prepared core is loaded. Prepared and
annual source files remain unchanged. The original digital value and source
provenance remain readable, repeated application is idempotent, and the source
signature invalidates caches when either a decision or later annual source
changes. Weekly refreshes retain this file and add only post-cutoff weights.

Win percentages and all non-match statistics retain their existing evidence.
The profile coverage note explicitly separates full supported career matches
from incomplete season/grade detail. Historical milestone attainment dates
are not inferred from undated career totals.

Other mapped historical match differences remain quarantined pending their
individual cutoff, source-credit and closed-customer-decision reconciliation.
