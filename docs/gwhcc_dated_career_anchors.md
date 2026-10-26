# GWHCC dated historical career anchors

The 23 October 2026 candidate restores only Chris Briginshaw and Matthew
Briginshaw. It does not enable the existing review-only record overrides or
change the 21 FB17C decisions. Production release requires separate approval.

The subsequent club-wide candidate is documented in
`gwhcc_clubwide_historical_reconciliation.md`. The original two source rows
remain unchanged; the additional source file uses explicit metric scopes
and individual cutoffs without changing these Briginshaw values.

## Source contract

`gwhcc_dated_career_anchors.csv` has one explicit canonical-ID decision per
player, a closed season cutoff, five independently supported career counts,
source row/fingerprint and an approval status. Only `approved_dated_career`
with high/confirmed/approved confidence is eligible. Review/rejected/pending
rows remain audit-only. There is no name fallback or new public identity.

GH Statistics 1980-2026.xlsx Sheet1 rows 107 and 109 supply career runs,
innings, not-outs, wickets and bowling runs conceded. The original 2025/26
Senior workbook Sheet1 rows 8 and 9 independently repeats those totals and
identifies the cutoff. The source fingerprint is that of the original shared
workbook; the retained workbook's values/formulas are identical despite a
different binary fingerprint. Sources are not read as Excel at runtime.

## Arithmetic and source overlap

Authoritative counts = closed full-career source counts through 2025/26,
plus **only** canonical season aggregates strictly after 2025/26. All earlier
digital figures overlap the source and are replaced, never added or maximized.
Future weekly builds must preserve this source decision file and continue
producing finalized, governed annual aggregates. They must not bake the
career anchor into annual rows or the digital prepared core.

Matthew's retained 2026/27 increment is two wickets and six runs conceded:
533 + 2 = 535 wickets; 10,600 + 6 = 10,606 conceded. Chris has no later
increment in the five supported counts. Batting averages use the same career
runs / (innings - not-outs); bowling averages use career conceded / wickets.
No average mixes source counts with a partial digital denominator.

Duplicate post-anchor aggregate keys or missing/invalid numeric evidence
raise an explicit error rather than silently creating zero or reverting to
an incomplete career. The small later-count cache is keyed by source-file
signatures; it does not retain complete season tables. The central document
override signature includes the anchor and season files.

## Public views and limits

HOF, profile and milestone consumers share the central governed career layer.
The HOF Not Outs display merge reapplies the same dated decisions so a tab or
table transformation cannot replace verified full-career counts with digital
counts. Profile season and grade tables remain unchanged and partial. Career
runs/innings/wickets can therefore exceed the sum of those tables. A scoped
profile note explains the distinction; no shared club styling changes.

Matches, catches, highest scores, fifties/hundreds, balls, overs and other
rate/fielding/detail fields keep their existing evidence. Historical match
counts 390.5/296 remained quarantined in the 23 October implementation. The
targeted 26 October local match-count candidate now has separate canonical-ID
decisions documented in `gwhcc_historical_match_counts.md`; it does not alter
the original five-metric rows or approve other review games overrides.
No annual rows, scorecards, partnerships,
hat-tricks, fastest innings or inferred innings/dismissals are created.

Original Premiership lists.pdf pages 2 and 1 and the supplied 2026 premiership
document establish Chris's U16 participation in 1989/90 and Matthew's in
1990/91. These are earliest evidenced participation seasons, **not exact
debuts**. Matthew's First XI debut remains 1992/93 G4; Chris's is 2002/03 G8.
Those narrower First XI facts are retained in the metadata source notes.

## Review and rollback

The outside-repository checkpoint contains source inventories, source cells,
before/after counts, focused tests and local screenshots. No production
release is authorized by this document. Review the changed-player inventory,
recheck remote ancestry and obtain explicit approval before releasing.
Rollback is a normal reviewed revert of the focused candidate commit, not a
reset, force push, data regeneration or speculative Streamlit reboot.
