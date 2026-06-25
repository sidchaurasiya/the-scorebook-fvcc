# FVCC Localhost Performance Audit

## Result

This applies the GRDCC optimization pattern from commit `5ccd9bb` to FVCC without changing displayed records, rankings, routes, or styling. FVCC already inherited persistent HOF caching from that shared change, but its cache key did not explicitly include the club and its single `Men` group still rebuilt equivalent all-time tables during render.

FVCC also ran player-identity duplicate audits, mapping exports, and canonical table maintenance inside the normal HOF load. Those maintenance tasks are now opt-in with `FVCC_RUNTIME_IDENTITY_MAINTENANCE=1`; normal runtime still applies the existing approved aliases but does not read/write audit outputs.

## Changes

- Prepared and historical HOF caches remain disk-persistent and now include `club_id` in their cache key.
- The equivalent FVCC single-group HOF rebuild is skipped while preserving the `men` scope passed to existing premiership and fastest-record renderers.
- Season detail, selected-season category rows, player profile index/detail/career views, premierships, and milestone source records use persistent club-safe cache keys.
- Profiling is opt-in with `FVCC_PERF_PROFILE=1` and writes only to FVCC validation output.
- Experimental match-centre pages remain hard-disabled; normal routes do not read validation/review-pack files.

## Timings

| Run | Time |
|---|---:|
| Pre-change baseline estimate | 18.2 s |
| First persistent build | 10.6 s app run; 15.3 s browser-ready |
| Fresh restart | 2.3 s |
| Warm rerun | 2.1 s |

The pre-change timing is a Streamlit AppTest baseline, while restart/rerun timings are browser measurements. It is retained as an estimate rather than presented as an identical harness comparison.

## Behaviour And Data

- FVCC HOF, Season Overview, Player Profile, and Milestones retain their existing calculations and presentation.
- FVCC theme values remain `#6D4DFF`, `#9F2747`, and `#F7F8FC`.
- No FVCC aggregate, deploy-safe, raw, alias, or mapping data was changed.
- GRDCC single-group behavior, source priority, and Annual Report override scoping remain unchanged.

## Caveat

The first-ever build still spends most time in all-time aggregation and Greatest Individual Seasons. Further vectorization could reduce that cost, but it was intentionally excluded because those routines determine official rankings.
