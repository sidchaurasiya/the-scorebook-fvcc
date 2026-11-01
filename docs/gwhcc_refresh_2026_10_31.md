# GWHCC Refresh Through 31 October 2026

Local candidate based on `e74ab8868565d9d9c38d9750d419c6b42825face`.
Production release requires separate owner approval.

## Publication Scope

- 42 eligible played fixtures: 38 completed and four terminal abandoned fixtures
  with verified play. Existing Hawks eligibility rules, not a new status policy.
- Five additions to the 37-match baseline: Second XI `be085026-67f3-4b1b-a368-810a74900af5`,
  First XI `42c98faf-7e79-404a-b0d5-d4fd119664a7`, Second XI
  `834b2932-93b4-40db-9c04-b039323b9126`, U13 internal fixture
  `b388f796-8b31-44ee-95f8-dbc793fa3a43`, and Third XI
  `a7670503-78f2-4c97-8714-c7e806daa211`.
- No-play fixtures, the U15 forfeit, six unfinished fixtures and November games
  remain excluded. T20 credit remains 0.5; eligible non-T20 credit remains 1.
- Historical pre-season reference: `ccf82a2667d16af287a7fcef97bcbf769be21940`.
  All 3,475 historical matches and all 17 historical authority fingerprints remain intact.

## Source Reconciliation

Ten retained scorecards were compared by match, innings, team and source player,
not positional JSON differences. Four removed empty innings; five changed
individual contributions; one had no contribution difference. Official removal
of Yojit Sardana's zero-ball DNB roster entry removes one appearance, not a
batting performance. Existing source-as-recorded arithmetic exceptions remain
limited to their previously approved matches and scope.

The finalised-aggregate boundary checks additive fields against eligible and
excluded scorecard partitions and rejects unexplained differences. Twelve
lagging Second XI fields require exact independently verified scorecard/delivery
certificates with immutable payload hashes. Missing provider rows are not
automatically treated as zero-performance rows. Jarrod Greaves's two runs and
Sundara Moorthi's one run require certified figures; Akshath Mantripragada's DNB
earns only the established participation credit. Unknown/protected identities
cannot be introduced by this missing-row pathway. Later provider rows replace
the missing-row route rather than adding duplicate contributions.

The source bundle and raw receipts are retained outside Git. Any later source
change invalidates a mismatching certificate; a refresh must reconcile it again,
not silently reuse old authority.

## Governed Outputs

Public population: 1,291 to 1,292. The sole new public source identity is Cameron
Stow (`raw_924e6387_5272_4b8c_8f33_2706f1d25472`), displayed in source order as
`Stow, Cameron`, with two eligible appearances and four runs. No identity merge
or historical identity publication is involved.

Chris Briginshaw remains 391.5 matches. Matthew becomes 299 (297 plus the two
verified new Second XI appearances). Noel becomes 107 (106 plus the new Third XI
appearance); this does not approve the separate held historical 106/107 dispute.
Mujib remains 25.5. Approved dated historical anchors and the nine-player release
remain authoritative. Historical season rows are not invented.

Three additional delivery-derived milestone innings and 15 partnership events
are supported by available deliveries. The scorecard-only Burwood match and
Third XI 31 October match do not create delivery-dependent achievements. The
780 older fastest-innings rows, historical partnership events, club partnership
records, premiership records and verified hat-trick remain unchanged.

## Acceptance Evidence

Durable receipts are under:
`/Users/preetkaur/Documents/Codex/checkpoints/gwhcc-refresh-2026-10-31/`.

- Untouched baseline: 281 passing tests.
- Candidate initial run: 246 passed, 43 failed; intermediate: 287 passed, two failed.
- Final relevant 17-module candidate run: 289 passed, zero failed/skipped.
- `regression_failure_dispositions.csv` retains all original failure details.
- Independent appearance ledger, 14,212 governed fields, 12,920 component fields,
  changed averages, best figures and win counts reconcile with original receipts.
- `serving_parity_result.json`: all governed career columns and all 4,221 Profile
  milestone rows agree between fresh prepared and forced-fallback paths.
- `category_serving_parity.json`: batting (29), bowling (27), and fielding (27)
  statistical/display columns agree for all 1,292 public profiles. Four diagnostic
  metadata columns are handled separately: 54 cells on 15 merged category rows
  intentionally retain baseline prepared metadata rather than recomputed raw-row
  counters. These counters are not statistical approvals or record-selection
  inputs; team/grade selection uses the raw team/grade classification. No career,
  ranking, privacy or record-eligibility difference is hidden by this distinction.
- Independent milestone arithmetic validates all 4,221 rows; no threshold policy
  or first-50 Profile alignment change is introduced.
- `repeat_build_hash_comparison.csv`: 119 data files byte-identical across clean
  builds using the same source bundle and historical reference.

Broader optional cross-club reconstruction tests require untracked raw
match-centre files absent in both candidate and untouched baseline. Those checks
are recorded as environment-blocked, not passed. GRDCC not-out semantics must be
tested with `CLUB_ID=georges-river-district`, not the Hawks environment.

No shared UI, dependencies, other-club files, historical source files or privacy
rules are changed. CSV row width changes in historical aggregate files reflect
the added optional source-coverage column; original historical values are tested
for exact parsed equality.
