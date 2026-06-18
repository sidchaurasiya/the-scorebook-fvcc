# GRDCC Localhost Performance Audit

## Result

The dominant delay was not CSV I/O. Five processed source files loaded in about 242 ms. The HOF was then built once, but the single available `Men` team-group selection caused a second equivalent HOF path during the initial render. Prepared HOF results also existed only in the process cache, so restarting Streamlit forced the expensive build again.

The GRDCC single-group no-op rebuild is now skipped. The prepared and lower-level HOF caches use Streamlit's persistent disk cache with source metadata, player-alias, Annual Report override, and data-version keys. Normal runtime profiling remains disabled unless `GRDCC_PERF_PROFILE=1` is set.

## Top Slow Stages

| Rank | Stage | Time (ms) | Finding |
|---:|---|---:|---|
| 1 | Full first script run | 62,110 | Includes initial build and Streamlit's immediate rerun. |
| 2 | Prepared HOF first build | 49,866 | Cold derived-data build. |
| 3 | Concurrent/immediate prepared request | 46,751 | Waited for the first cache population. |
| 4 | Historical HOF data build | 36,476 | Identity, summaries, and all-time aggregation. |
| 5 | All-time player summary | 19,147 | Largest remaining computation. |
| 6 | Canonical category summaries | 12,914 | Player aggregation across disciplines. |
| 7 | Greatest Individual Seasons | 12,141 | Player-season grouping. |
| 8 | Canonical identity/team-grade mapping | 4,025 | Mapping across three source frames. |
| 9 | Detailed records rendering | 1,933 | Three complete sortable HTML tables. |
| 10 | All-Time Leaders rendering | 1,013 | Four top-15 cards and active-player checks. |

## Benchmarks

- Before cold browser-ready estimate: 100,286 ms.
- First build after the patch: 68,757 ms. This populates the persistent cache.
- Fresh Streamlit restart using the persistent cache: 16,363 ms.
- Warm browser rerun: 3,868 ms.

## Runtime Data Review

Normal HOF runtime reads the processed batting, bowling, fielding, seasons, and players files. Annual Report decision/supplement CSVs under validation are a deliberate app-facing lookup for approved career overrides; they are now memoized and their mtimes participate in the prepared-cache key. Other discrepancy, audit, and review-pack files are not loaded by normal page renderers.

Season Overview already filters aggregate category frames by selected season inside its cached loader. Player Profile uses cached player source rows and cached derived profile views. Milestones reuse the persisted lower-level HOF data cache.

## Remaining Opportunity

The first-ever build remains compute-heavy. Vectorizing `build_all_time_player_table`, `combine_player_rows`, and the Greatest Seasons grouping could reduce it further, but those routines determine official rankings and were intentionally left unchanged in this narrow, behavior-preserving optimization.
