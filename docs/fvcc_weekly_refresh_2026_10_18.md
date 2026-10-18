# FVCC weekly refresh: 18 October 2026

Base: `472ef289d44219000c8c63aaae79dcae3cbd2cc8`, preserving the released
GRDCC/GWHCC updates. FVCC only; no shared application, theme, dependency,
runtime, source policy or other-club data changes.

## Frozen official scope

Discovery cutoff: **18 October 2026 06:39:14 Australia/Melbourne**
(`2026-10-17T19:39:14.188451+00:00`). Resumption does not extend this cutoff.
The official organisation inventory covers four Summer 2026/27 teams and one
Winter 2026 team, five grades and 75 fixtures. Fifty future Summer fixtures,
four cancelled fixtures and three unscheduled PENDING fixtures are unpublished.

The only newly finalized result is Fourth XI versus Camrea Stingrays 3rd XI,
NMCA Sid Sault ODC, Round 3, 17 October 2026:

- Match: `80a88932-8bd2-43c5-9f49-3db456a60ffd`.
- Camrea 55 in 32.1 overs; FVCC 1/56 in 4.3 overs; FVCC won by nine wickets.
- Official scorecard: <https://play.cricket.com.au/match/80a88932-8bd2-43c5-9f49-3db456a60ffd?tab=scorecard>.
- Both innings reconcile to batting plus extras and to the captured deliveries.
- Ten public appearances, 53 batter runs, ten wickets and four catches added.
- Two masked roster entries remain excluded from public player outputs.

At the frozen cutoff, the following 17 October matches are excluded completely:

| Team | Status | Match ID |
| --- | --- | --- |
| First XI | IN PROGRESS | `22342e82-4bc8-4dfa-ba67-5d9cb831247d` |
| Second XI | LIVE | `d454dfb9-b61d-4382-b6d2-f75594461198` |
| Third XI | STUMPS | `6175cdef-3b87-4450-a00d-2b381f4324f7` |

No previously pending match finalized in this increment. Provider aggregates for
these three teams are unchanged from the prior verified receipts, including
their numeric rate/innings/fielding statistics. Their provider appearance
counters still include cancelled fixtures; published appearances continue to
count verified selected players on finalized scored rosters, including DNBs.
Fresh cumulative feeds are not blindly substituted into finalized statistics.

## Preservation and generation

The existing frozen-bundle incremental builder regenerates only the five-match
finalized Summer partition over validated historical sufficient statistics.
No historical raw archive is reconstructed. Every pre-Summer aggregate key/value
is retained; previously published current contributions remain exactly once.
Source IDs, approved aliases, all five identities introduced in the previous
refresh, Captain evidence and privacy boundaries are preserved. No new public
identity or name-only merge is introduced.

The bundle normalizes raw identity provenance before canonical mapping and
preserves provider counters separately from published appearances. Early
quarantined candidates failed these gates and were never promoted. The final
candidate preserves all 296 canonical/public identities.

All 67 offline-generated CSVs reproduce deterministically. Append-only link and
fastest evidence retains the exact released byte prefix; only new records append.
Prepared manifests pass source hashes and FVCC privacy policy checks; all four
prepared frames equal the raw governed calculation. Valid prepared loading makes
zero raw all-time reconstruction calls. No unbounded cache or runtime work added.

## Before / after

| Metric | Before | After | Change |
| --- | ---: | ---: | ---: |
| Statistical seasons | 31 | 31 | 0 |
| Historical match IDs | 961 | 961 | 0 |
| Finalized Summer matches | 4 | 5 | +1 |
| Total match IDs | 965 | 966 | +1 |
| Public HOF/search | 296 | 296 | 0 |
| HOF active players, latest two seasons | 50 | 52 | +2 |
| Public career appearances | 9,674 | 9,684 | +10 |
| Runs | 126,439 | 126,492 | +53 |
| Wickets | 6,747 | 6,757 | +10 |
| Catches | 3,642 | 3,646 | +4 |
| Fifties / hundreds | 484 / 49 | 484 / 49 | 0 |
| Verified fastest 50s / 100s | 64 / 2 | 64 / 2 | 0 |
| Fastest-innings evidence rows, including 25-run records | 216 | 217 | +1 |
| Confirmed hat-tricks | 0 | 0 | 0 |
| Partnership events | 917 | 919 | +2 |
| Selected partnership records | 10 | 10 | 0 |
| Captain breakdown rows | 509 | 515 | +6 |
| Premiership contribution rows | 63 | 63 | 0 |
| Populated Not Outs aggregate rows | 1,957 | 1,961 | +4 |

Danny Singh remains 336 matches, 6,382 runs, HS **144**, not 144*.
Kalpeshkumar Patel remains **86***. Shaun Vikash remains 242 matches and
458 wickets. Paul Silva remains one match, 13 runs and two wickets. Jacob
Joseph's new 3/8 yields 18 career wickets; Rashim Kandel's 35*(18) yields 119
career runs. Ranjan David's canonical profile remains intact at two matches and
two wickets. Player DNA, peers, trends, recent form and milestone sources extend
through the same governed outputs.

## Existing exceptions and later receipt checks

- The accepted Second XI 10 October discrepancy remains: team 125 versus batter
  110 plus extras nine. No six runs invented or redistributed.
- The First XI 10 October BBB total remains 153 versus scorecard 152; affected
  whole-innings metrics remain excluded under the existing coverage rule.
- One scorecard differed only in array order, not statistics or identities.
- A later bounded freshness check on the three reused current-season delivery
  receipts found organisation short-name metadata changes and one unused
  provider dismissed-player strike-rate correction. Parsed deliveries, overs
  and partnerships are identical. The frozen bundle/cutoff was not changed.

## Validation and release boundary

Focused FVCC regressions: 136 unique tests pass, with the corrected DNB-roster
appearance guard included. Two selections are intentionally excluded: an
unrelated stale cross-club row-count assertion and a missing-archive integration.
Together with the five unrun historical detector integrations, six historical
raw-cache integrations remain BLOCKED, not passed. There are also 147 source
contribution checks, 52 candidate gates and 77 additional field-level checks.

Desktop and actual Chrome 390px navigation cover HOF categories/search, Summer
results/team filters, updated player profiles and all milestone views. The
official Fourth XI scorecard renders correctly. No tested app exceptions or
protected public links. Browser automation wait timeouts were resolved by
reading the completed DOM; they are not application exceptions.

Checkpoint, raw receipts, rejected candidates, comparison scripts and browser
evidence remain outside Git. Only curated FVCC outputs, focused tests and this
release note are committed. No push, merge, deployment, production reboot or
cache clearing is authorized by this refresh.
