# GRDCC verified Summer 2026/27 refresh

## Scope And Source Window

The initial source snapshot was checked on 11 October 2026 at 04:00
Australia/Melbourne (10 October 2026 17:00 UTC). A bounded known-team status check
at 12 October 02:42 Melbourne found two additional finalized 11 October matches.
Only those two scorecards/BBB payloads and their two affected teams' aggregates
were refreshed. The final scope includes scheduled matches through 11 October,
not subsequent dates; the earlier snapshot remains preserved in the checkpoint.

Thirteen club teams provide 163 unique fixtures. Twenty-two finalized match IDs are
retained: 17 completed and five abandoned. Fifteen completed matches and one
scored abandoned match support player statistics. The two result-only completed
matches and four non-scoring abandoned matches do not fabricate player totals.
130 upcoming, nine pending, one LIVE and one STUMPS fixture were excluded from
final player statistics. Later dates require a separate refresh.

Official public aggregates reconcile with finalized scorecards: 1,639 player-metric
checks pass; 1,688 public batting runs match. The additional 15 masked scorecard runs
are not attributed to a public identity. Source match, innings, player and team IDs
are retained; the three aggregate files each append 144 rows without rewriting
historical bytes. No raw Excel, raw PlayCricket or Annual Report source is changed.

## Historical Preservation

Route B uses committed historical summary sufficient statistics as the baseline
and exclusively disjoint current-match contributions. All 2,604 historical match IDs
remain; current IDs add 22, giving 2,626 with zero overlap. Unchanged historical keys
and values are retained exactly. Captain breakdowns preserve 10,327 historical keys
and add 147. Historical premiership playing-XI and captain evidence is untouched.

Only Captain extraction and premiership captain evidence require historical raw
scorecard JSON. The unavailable cloud-placeholder cache is not needed by app runtime.
Do not run a broad historical profile/premiership rebuild against a partial cache.
The incremental merge utility rejects overlapping matches and duplicate summary keys,
sums additive counters only, recomputes ratios from their sufficient statistics,
keeps unavailable historical counts unavailable, and selects HS/BBI with their
evidence-aware markers. It never averages averages or appends overlapping career totals.

## Career And Identity Governance

The governed pre-refresh presentation at commit `f319846` is the explicit career
baseline through Summer 2025/26, not a new interpretation of raw Annual Report dates.
`career_refresh_baselines.csv` records that snapshot. Verified later-season totals
extend its additive records without duplicating any baseline season.

Six contemporary players also had primary career counters replaced by weaker partial
Excel supplements. For source-rule careers beginning from 1972 onward and extending
beyond the baseline, primary Matches/Innings, averages and other supported counters
are retained. Approved Runs/Wickets remain at least the stronger governed value.
Source-rule averages are not manufactured from a report total with unknown denominators.
Historical match proxies, unknown Not Outs and valid numeric zeroes retain their rules.

Verified BBB coverage counters have different semantics from unknown historical
career statistics: a missing coverage join contributes no verified deliveries.
The merge retains known later BBB contributions instead of erasing them with a
historical null. Nineteen summary keys affected by this defect were corrected;
ordinary statistics and unavailable historical Not Outs were not converted to zero.

Fifty-five new canonical identities are backed by positive-match official source rows
(51 at the initial snapshot, four from the end-of-day delta).
No prior canonical ID disappears and non-empty canonical IDs are unique. Nine exact
source-ID mappings retain established IDs in scoped views; no name-fallback aliases
are introduced. Verified same-name ID continuity takes precedence over older manual
slug namespaces only for GRDCC and fails closed on conflicting name evidence.
Eleven explicitly approved historical summary namespaces are mapped to established
canonical identities at read time. Native/manual-ID provenance and disjoint historical
match sets support the bridge; no similar-name inference is permitted. Archival
summary IDs remain intact, while ID-first readers include all approved historical
parts alongside current contributions. Name conflicts fail closed, unapproved IDs
remain distinct, and protected rows are excluded before bridging. The approval file
participates in runtime cache signatures and prepared-source fingerprints.

The two existing canonical IDs affected by automatic exact-name rekeying are preserved
by `canonical_player_continuity.csv`. No fuzzy identity matching is added.

Protected historical appearances never become public through a later public identity.
Warwick Geitz and Ben Worger remain unlinked report-only records; unresolved Annual
Report additions for R. Davey and Matthew Grealy remain withheld. The ninth-wicket
record stays Mohammed Ismail / Private player, 94, without a protected profile target.

## Accepted Baseline

| Item | Before | After |
|---|---:|---:|
| Governed HOF rows | 2,035 | 2,090 |
| Active public players | 155 | 168 |
| Statistical seasons | 92 | 93 |
| Prepared core rows | 2,063 | 2,118 |
| Fastest evidence rows | 540 | 557 |
| Hat-trick sequence rows | 4 | 6 |
| Retained partnership events | 2,463 | 2,579 |
| Verified wicket records | 10 | 10 |

The two new hat-trick rows are overlapping verified three-wicket windows in Francis
Weeding's four consecutive wickets, not two different matches. Historical evidence
rows are byte-preserved. Nick retains HS 130*, now spans 2015/16-2026/27 and has 12
seasons; his governed runs are 3,988 and primary matches 171. Harry retains HS 110
without an invented star and Matches 412* with the historical proxy footnote.

Prepared HOF regeneration is deterministic across six output hashes; the 16-source
fingerprint includes canonical continuity and summary namespace approvals. Raw/prepared equivalence,
zero raw reconstruction calls for a valid snapshot and forced raw fallback pass.
The current prepared files and presentation baselines are app-facing, tracked outputs.

## Validation And Release Discipline

The final relevant suite passes 200 tests, zero failures, one deselected integration
and one pandas null-comparison warning. Fourteen public counter-conservation checks
and 64 actual profile-reader source-part checks pass. Historical Captain keys,
disjoint source partitions and all 16 summary exports pass preservation checks.
Final focused GRDCC and shared synthetic regression results and browser evidence
are recorded outside Git in `grdcc-hs-2026-27-refresh`. Six cross-club raw-rebuild
integration tests require unavailable FVCC caches and are BLOCKED, not passing tests.
FVCC/GWHCC data is not regenerated; explicit synthetic branch tests retain their
existing mapping/override behavior. Stale pinned counts were updated only after
the new source-backed cohort and season count were independently reconciled.

Keep raw downloads, partially restored JSON, checkpoints, screenshots, quarantine
outputs and generated validation artifacts out of Git. Preserve the complete reviewed
commit chain; never use broad staging, reset/clean, force push or unreviewed deployment.
Release review and production verification are separate tasks.
