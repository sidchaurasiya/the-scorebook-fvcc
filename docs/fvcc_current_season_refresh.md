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
