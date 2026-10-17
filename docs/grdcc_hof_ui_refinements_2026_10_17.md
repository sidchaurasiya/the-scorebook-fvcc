# GRDCC Hall of Fame responsive refinements

## Approved reference and scope

Reference: Hawks commits `3251a6f` and `345c3bb`, already present in base `50520b9`.
Only the implemented rounded category-control pattern is adapted; no premium
redesign concept, Hawks data or Hawks gold is imported.

GRDCC keeps its existing card layout, heading hierarchy and table columns. The
Batting/Bowling/Fielding control receives a neutral rounded container, equal grid
columns, rounded selected pill, 44px minimum target height and scoped focus outline.
Search, filtering, sorting and the underlying Streamlit widget are unchanged.

The existing `GRDCC Premiership Wins` heading and Captain evidence are retained;
season headings use the established GRDCC blue. Existing heading/card spacing and
border-radius hierarchy were already coherent and are not broadly redesigned.

The sidebar uses `assets/logo_trimmed.png`, with a near-square source and existing
contain/scale treatment. No additional source whitespace defect was established;
the logo, aspect ratio and sidebar alignment remain unchanged.

## Colours

All values come from `clubs/georges-river-district/club_config.yaml` and existing
`--club-*` variables. No new theme palette is introduced.

| Use | Existing token | Value |
|---|---|---|
| Selected pill and focus outline | `--club-primary` | `#0B3F9F` |
| Selected text | `--club-surface` | `#FFFFFF` |
| Neutral pill container | `--club-bg` | `#F3F9FD` |
| Border | `--club-border` | `#D8E8F5` |
| Inactive text | `--club-muted` | `#66758D` |

White-on-blue contrast exceeds4.5:1. The complete generated FVCC and Hawks theme
CSS remains byte-identical to base; new CSS is injected only when the active club
is GRDCC and is limited to the existing HOF controls and premiership season labels.

## Mobile conflict and correction

Browser testing at390px exposed a legacy mobile rule setting category button
width to one third. Applying that percentage inside the new three-column grid
shrunk each button to29px, causing ellipsis. The first flex/max-width adjustment
alone was insufficient because the old width selector still had higher specificity.

The final GRDCC selector includes the controls ancestor, category ancestor and
`stButtonGroup` attribute. It sets full grid-cell width, `flex:none` and
`max-width:none`; no navigation or widget rewrite is required.

Actual browser app viewports at390px and320px show button widths94.94px and71.60px
respectively. Full labels occupy52px,58px and57px; text scroll widths equal client
widths, with no ellipsis or page overflow. All three selections and keyboard Enter
activation are tested, along with mobile player search. Desktop retains370px group
width and the same equal-column appearance.

## Browser evidence method

The in-app browser's viewport override did not change its1280px top-level layout,
so those early images are NOT accepted as mobile evidence. Chrome initially proved
the390px regression, but later debugger attachment was interrupted by concurrent
browser use. No unrelated club tab was operated to recover that session.

Final independent local harnesses embed the FULL running Streamlit app in true
390x844 and320x844 CSS-pixel viewports. Inner `window.innerWidth`, document width,
computed geometry and actual widget interactions are measured. These are actual
responsive app renders, not narrowed crops of a desktop layout. The before-mobile
comparison uses exact committed base CSS with the same candidate data in an external
test harness; the desktop before screenshots were captured before the changes.

External evidence lives under:
`/Users/preetkaur/Documents/Codex/checkpoints/grdcc-weekly-refresh-2026-10-17/browser/`.
It includes before/after HOF and category images, premierships, the true mobile
comparison, mobile search and measured390/320px geometry. No screenshot or harness
is committed to the repository.

## Governance and tests

Historical/BBB/Not Outs/proxy/privacy qualifications are preserved, not hidden or
removed. Data, rankings, record eligibility and statistical methods are unchanged
by the style commit. Nick HS130*, Harry HS110 and Matches412* remain separate
regression anchors. Report-only players remain unlinked; the protected ninth-wicket
partner remains exactly `Private player` without a profile target.

Affected GRDCC/Hawks UI tests:17 passed. Completed data validation and the201-test
suite are carried forward; unavailable historical-cache integrations remain BLOCKED.
The data refresh and these cosmetic changes are separate local commits. No push,
merge, deployment, production reboot or cache clear is authorized by this work.
