# GRDCC presentation and Nick Condylios reconciliation

## Scope

GRDCC-only visual refinements on released `7c893f1`. No FVCC/Hawks data, historical
primary rows, identity mappings or accepted special-record counts are changed.
The only numerical presentation correction is Nick Condylios's career Runs.

## Nick's 459-run difference

The original GRDCC 2024/25 Annual Report, printed/PDF pages 98-99, records 3,259 in
its **ALL GRADES** club-runs table and 722 in the Frank Gray Shield subset table.
The retained official season/team/grade aggregates also total 3,259 through
2024/25, including those 722 Frank Gray runs. They add 263 in 2025/26 and 17 in
the accepted 2026/27 snapshot. The correct club total is therefore 3,539.

The previous presentation combined the all-grades and subset values, then froze
3,981 as a seed through 2025/26. This both counted Frank Gray again and omitted
the 263 subsequent-season runs:

| Calculation | Runs |
|---|---:|
| Previous display: 3,259 + 722 + 17 | 3,998 |
| Correct display: 3,259 + 263 + 17 | 3,539 |
| Difference: 722 - 263 | 459 |

Source PDF: <https://drive.google.com/file/d/1wbmPZ-8DDKz4GoyPG9dNza-mBnplmyUR/view>

PDF SHA256: `afbeae2b01523edee7d0929a80b33f1d969b560957ed790dc7baff3aa6dfb240`.

The exact canonical correction in
`data/source/reviewed_career_baseline_corrections.csv` changes the through-2025/26
seed to 3,522, while preserving the original seed/extraction as historical audit
evidence. Later eligible seasons are still added exactly once. It applies even
when a player has no later eligible contribution, and rejects ambiguous or
changed seed inputs. It is not a name-based merge or a source-season rewrite.

Raw prepared HOF already contains the correct digital sum. The normal governed
HOF, Player Profile and Milestones all use the same reviewed correction. Matches,
HS 130*, Not Outs and all other players' numerical values remain unchanged.
Nick no longer qualifies for the within-100-runs Upcoming card at 4,000; the
threshold rule itself is unchanged. No historical match IDs are invented where
only season aggregates are retained.

The older ALL GRADES + Frank Gray combination rule is also used for other
report players. This task does **not** apply speculative population-wide changes:
other approved headline values are retained. Extending this correction requires
independent per-player source/cutoff reconciliation, not merely subtracting each
Frank Gray subtotal.

## Presentation

- Local, licensed Manrope/Barlow typography, GRDCC tokens, clearer hierarchy and
  compact cards. Styles are injected only for GRDCC; reduced motion is respected.
- Larger, proportional existing crest with no image edit or cropping; contrasting
  active navigation and visible keyboard focus.
- Premiership accents use dark blue rather than low-contrast cyan.
- All six accepted hat-trick sequences remain. Two columns on desktop, one on
  mobile; date-descending and natural delivery ordering. Official deliveries
  confirm Francis Weeding's four caught wickets at 8.3-8.6: the accepted detector
  emits both overlapping three-wicket windows. Labels explain this without
  deleting or inventing records.
- Public partnership links use a uniform component style. Current released code
  already resolved both Nick links correctly; no player-specific exception was
  added. Private partner text remains unlinked, and existing figures remain.
- Round results show Date before Round. All 38 accepted current-season fixture
  schedules were checked, including six multi-day matches. The generated
  `season_overview/match_playing_dates.json` contains schedule metadata only.
  Historical rows without retained multi-day schedules use their stored official
  date; absent dates remain explicit, never inferred as first-day-plus-seven.
- Grade-strip controls reflect real overflow and position. Keyboard and touch
  scrolling work without intercepting vertical wheel gestures. Mobile cards keep
  Date first and retain accessible table headers.

Detailed source receipts, before/after screenshots, contrast measurements and
test commands are kept outside Git in the task checkpoint. Production release
requires separate owner approval.
