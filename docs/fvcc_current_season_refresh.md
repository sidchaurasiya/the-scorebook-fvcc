# FVCC Summer 2026/27 refresh

The frozen source cutoff is 12 October 2026 13:53:25 UTC, equivalent to
13 October 2026 00:53:25 Australia/Melbourne. Official organisation
`7b78f08d-87d8-eb11-a7ad-2818780da0cc` supplies four Summer teams and the
Winter XI. The bounded inventory contains 75 fixtures: four new completed
Summer matches, ten existing completed Winter matches, four cancelled Summer
fixtures, and 57 upcoming Summer fixtures. Winter's numeric aggregate values
match the existing committed baseline.

The four 10 October matches contribute 45 supported player-team appearances,
486 batting runs, 20 bowling wickets, eight catches, and five new public source
identities. Provider appearance counts include cancelled fixtures; the original
counts are retained in `provider_appearance_count`, while new published `matches`
count only participation on finalized scored scorecards. No historical count
policy is rewritten and no other club's weighted-match rule is applied.

Historical aggregates are retained by key and value. Disjoint current match IDs
extend existing sufficient-statistic exports, with ratios recomputed from their
counters rather than averaging averages. All historical Captain keys and
premiership evidence remain. Unknown ordinary historical statistics remain
unknown. The existing club-aware exporters produce current summaries and the
governed fastest/hat-trick/partnership detectors process only the new source
scope. Historical detector evidence is retained instead of rebuilding it from
unavailable ignored caches.

The incremental entrypoint is:

```sh
python scripts/refresh_fvcc_app_data.py \
  --source-bundle /path/to/frozen-fvcc-bundle \
  --baseline-root /path/to/verified-baseline \
  --candidate-root /path/to/new-outside-repo-candidate
```

The bundle includes source receipts, discovery metadata, parsed current tables,
current official aggregates, baseline mapping files, and the declared cutoff.
Candidates fail closed on duplicate/overlapping match or contribution keys,
unfinalized/future/no-score participation, and existing season statistics.
Inspect source receipts and candidate reconciliation before promoting any files.
Build the supported FVCC prepared HOF snapshot only after promoting validated
inputs; its manifest includes the FVCC public-filter token and source fingerprints.

Source limitations are retained explicitly:

**SOURCE EXCEPTION ACCEPTED BY CUSTOMER** on 12 October 2026:
FVCC 2nd XI vs Strathewen Cougars. The six-run discrepancy below is an accepted
provider limitation and is no longer a release blocker. Preserve the official
innings total of 125, the published individual batting scores, and the official
result (FVCC won by six wickets). Do not invent the six runs, allocate them to
extras, modify career totals, or derive unsupported innings metrics. Source
provenance and discrepancy evidence remain retained. Acceptance is not a
provider correction or proof of innings reconciliation.

- Match `cdf93da6-f0d4-405b-b1f3-d30744e4774e`: the provider reports an innings
  total of 125, but listed batter runs 110 plus extras nine total 119. Both
  scorecard and official player aggregate report the same player contributions;
  no additional six runs are allocated to a player. This match has no BBB.
- Match `b51f12f3-3c4a-4f15-8735-928f005fb2d2`: the FVCC batting innings delivery
  sum is 153 versus the scorecard 152. Full-innings bowling phase/rate coverage
  uses only reconciled innings. Exact batting milestones retain their existing
  detector evidence requirements.
- Historical full-source FVCC/GRDCC partnership/hat-trick reconstruction tests
  remain blocked by unavailable ignored match-centre caches. This refresh does
  not rebuild those other-club caches or classify blocked checks as passing.

Public HOF/search rows increase from 291 to 296, statistical seasons 30 to 31,
and source player index 330 to 335. New sufficient-statistic rows support Recent
Form, all Career Breakdown dimensions, Player DNA, peers, trends and milestones.
Existing privacy boundaries and HS/Not Outs semantics remain: Danny Singh 144,
Kalpeshkumar Patel 86*, and all 1,957 batting aggregate rows have known Not Outs.

Raw receipts, checkpoints, candidate/quarantine outputs, validation scratch data,
browser screenshots, and local caches are excluded from Git. Release/push and
production verification require a separate task.

## Final release gate

Remote main remains `34a805133fd2819bc8fa47b7762a39f5113a3ff0`, the original
refresh base; no integration is required. The refresh commit `34dae8b` is
preserved, with a documentation/test-only follow-up. No data or shared application
logic changed during this gate, so the 168 reconciliation checks, raw/prepared
equivalence, deterministic generation, fallback, privacy/link safeguards and
local browser UAT are carried forward without rebuilding or repeating them.

The obsolete Not Outs test now requires exactly 1,957 populated FVCC rows.
A frozen normalized SHA-256 from base `34a8051` guards all 1,912 historical
batting keys and values. New-contribution checks require exactly 45 unique
canonical player-team contributions per discipline and identical contribution
sets. The same cross-club test also contained a pre-existing stale GRDCC row
count; it now requires the 7,933 rows already present in approved main and its
metadata. GRDCC data, historical missing-value expectations and average checks
are unchanged.

Final focused tests: 33 FVCC/cross-club Not Outs and incremental-refresh tests,
eight clean-process GWHCC Not Outs tests, and 26 clean-process GRDCC/shared HS
tests pass (67 total). Six unavailable historical reconstruction integrations
remain BLOCKED, not PASS. The accepted six-run source exception is not a release
blocker; the separate one-run BBB discrepancy remains excluded from affected
whole-innings bowling analytics. The original statistical anchors are unchanged.

This candidate is ready for controlled Git release review, not yet released.
No push, deployment, Streamlit reboot or cache clearing is authorized here.
