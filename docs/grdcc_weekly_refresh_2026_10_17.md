# GRDCC weekly refresh through 17 October 2026

## Source window and lineage

Base: `50520b9fad938513f4213c3b9e6acf283a57f432`, including the released Hawks
weekly refresh and cosmetic changes. Work is isolated on
`data/grdcc-weekly-refresh-2026-10-17`; release requires separate approval.

Discovery observation started at **2026-10-18T00:06:16.661090+11:00 Australia/Sydney**.
Sydney had just passed midnight; the requested fixture eligibility ceiling remains
**17 October 2026**. No 18 October fixture is included. Receipts retain individual
fetch times; the API does not provide an atomic historical/as-of transaction.

Official PlayCricket organisation `a115d93f-87d8-eb11-a7ad-2818780da0cc` supplies
13 teams, 12 grades and 163 distinct fixtures. The finalized published cohort is
26 matches: 21 completed and five abandoned. Twenty have usable individual GRDCC
batting/bowling figures; result-only records do not invent player statistics.
Two STUMPS and one IN PROGRESS match remain excluded. Future and undated pending
fixtures are not provisional application contributions.

## Newly finalized matches

| Scheduled dates | Grade | Opposition | Official result | Match ID |
|---|---|---|---|---|
| 10-17 Oct | First Grade | Mt Pritchard Southern Districts 1st Grade | Georges River won by 82 runs | `c1166912-1497-4fb6-a704-0d5e4360cce6` |
| 10-17 Oct | Third Grade | Mt Pritchard Southern Districts 3rd Grade | Opposition won by an innings and 32 runs | `55d3f1c8-da78-4889-b940-e96bd6188455` |
| 10-17 Oct | Fourth Grade | Mt Pritchard Southern Districts 4th Grade | Opposition won by 139 runs | `312736b4-3607-4bc8-86c5-25c30b652ca9` |
| 11 Oct | Vintage | Hunter Taverners Vets CC Over 60 | GRDCC won by five wickets | `3f887215-ffd6-481f-89da-ed4b6a2f9dd6` |

Official scorecards:
[First Grade](https://play.cricket.com.au/match/c1166912-1497-4fb6-a704-0d5e4360cce6?tab=scorecard),
[Third Grade](https://play.cricket.com.au/match/55d3f1c8-da78-4889-b940-e96bd6188455?tab=scorecard),
[Fourth Grade](https://play.cricket.com.au/match/312736b4-3607-4bc8-86c5-25c30b652ca9?tab=scorecard),
[Vintage](https://play.cricket.com.au/match/3f887215-ffd6-481f-89da-ed4b6a2f9dd6?tab=scorecard).

All four were absent from the previous incorporated finalized set. Whole-season
discovery therefore recovers late-finalized older fixtures, not just Saturday's
start dates. Comparing old/new cached payloads with the SAME current parser found
four previously incorporated matches with changed scorecard details. Ten raw
payloads changed in total; metadata-only and numeric CSV representation changes
are not misreported as statistical corrections. The external audit records fields
and provenance for each decision; current official aggregates reconcile completely.

## Before and after

| Metric | Before | After | Change |
|---|---:|---:|---:|
| Finalized current matches | 22 | 26 | +4 |
| Historical match IDs | 2,604 | 2,604 | 0 |
| Total distinct match IDs | 2,626 | 2,630 | +4 |
| Public HOF records | 2,090 | 2,090 | 0 |
| Active public players | 168 | 169 | +1 |
| Sum of displayed career Matches | 39,568 | 39,850 | +282 |
| Career runs | 816,852 | 817,475 | +623 |
| Career wickets | 37,673 | 37,711 | +38 |
| Career catches | 12,712 | 12,732 | +20 |
| Career fifties | 1,843 | 1,853 | +10 |
| Career hundreds | 240 | 241 | +1 |
| Fastest evidence rows | 557 | 558 | +1 |
| Verified fastest fifties | 160 | 160 | 0 |
| Verified fastest hundreds | 19 | 19 | 0 |
| Hat-trick sequence rows | 6 | 6 | 0 |
| Partnership events | 2,579 | 2,601 | +22 |
| Selected wicket records | 10 | 10 | 0 |
| Captain summary rows | 10,474 | 10,490 | +16 |
| Captain batting runs | 312,251 | 312,681 | +430 |
| Premiership evidence rows | 10 | 10 | 0 |

Displayed Matches includes governed historical innings proxies and is NOT a count
of distinct club fixtures. The +282 is NOT 282 new current appearances.

## Returning-player Matches reconciliation

There are **46 new current-source appearances**. Another **236** reflect the
already-implemented GRDCC primary-career guard activating for three players whose
first later-season participation now extends their career. That guard retains
stronger existing PlayCricket primary counters instead of weaker partial historical
supplement counters; no governance rule, source values or identity decision changed.

| Player | Previous displayed Matches | New displayed Matches | Primary before | Primary after | Existing counter restoration |
|---|---:|---:|---:|---:|---:|
| Gavin Scott | 220 | 322 | 321 | 322 | 101 |
| Peter Remfrey | 303 | 391 | 390 | 391 | 87 |
| Kevin Croom | 393 | 442 | 441 | 442 | 48 |

The audit uses approved canonical-profile raw-ID membership, not name similarity.
Historical primary CSV bytes are unchanged. These effects must remain visible in
release review rather than being mistaken for new match contributions.

## Preservation and privacy gates

Route B retains the same 16 historical sufficient-statistic seeds used by the
previous accepted refresh, byte-verified against authoritative Git ref `f319846`.
Only the reconciled current-season partitions are replaced. Primary historical
bytes, eight match/season export prefixes and special-record historical prefixes
are preserved. All 2,604 historical match IDs and 10,327 historical Captain keys
remain. Premiership evidence bytes and 26 source/mapping/supplement files remain
unchanged. No historical JSON archive was fetched or rebuilt.

Existing canonical IDs remain; non-empty public canonical IDs are unique. No new
public canonical identity is added. Two newly observed source IDs have zero
participation and are excluded, not speculatively merged or published.

Nick retains HS `130*`, 3,988 runs and 171 matches. Harry retains HS `110` and
Matches `412*` with the separate innings-proxy footnote. Riley Orr updates to
2,684 runs and 212 matches. Actual profile totals agree with governed HOF values.
Historical unavailable Not Outs remain unavailable; known zeroes retain zero.
Report-only Warwick Geitz and Ben Worger remain unlinked. Unresolved report-only
identities remain withheld. The ninth-wicket record remains Mohammed Ismail /
Private player, 94; protected partner links/IDs are not published.

## Prepared data and validation

Prepared manifest accepted; raw/serialized-prepared frames compare exactly.
Six prepared artifact hashes reproduce deterministically. A valid prepared snapshot
performs zero raw HOF reconstruction calls; forced primary-statistic fallback passes.
No shared runtime dependencies were changed.

All 1,826 public player-metric checks and all 11 statistics-bearing team aggregate
checks reconcile, including 2,311 current-season public batting runs. Source
discrepancies/coverage classifications remain in external evidence; no totals were
forced to balance. BBB coverage continues to limit fastest/hat-trick/partnership
claims; a new hundred does not automatically establish a verified fastest hundred.

The focused suite recorded 201 passed; unavailable historical-cache integration
fixtures remain separately BLOCKED. Affected UI tests and committed-data snapshot
checks are run separately during final closure. No historical reconstruction is
performed to satisfy unavailable integration fixtures.

## Evidence and release discipline

External checkpoint:
`/Users/preetkaur/Documents/Codex/checkpoints/grdcc-weekly-refresh-2026-10-17/`.
It retains source receipts, pending/correction inventories, identity reconciliation,
before/after statistics, preservation proofs, prepared hashes, tests and browser
screenshots. Do not stage raw receipts, checkpoints, runtime caches or screenshots.

The data refresh and GRDCC-only UI refinements are separate local commits.
Do not merge, push, deploy, reboot production or clear production caches as part
of this task. Other clubs' data and existing Hawks UI changes are untouched.
