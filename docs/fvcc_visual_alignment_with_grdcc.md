# FVCC visual alignment with GRDCC

## Applied visual changes

- Premiership Wins keeps one continuous ordered list with six visible rows on desktop and five on mobile before vertical scrolling.
- FVCC Hall of Fame leader cards retain their desktop presentation and use five-row mobile scroll containers.
- Fastest Innings and Iconic Performances retain the existing desktop six-row/expand interaction and use five-row mobile scroll containers.
- Season by Round uses the shared horizontal grade/team panel strip. The internal folder selector is removed while the global season and grade/team selectors remain unchanged.
- Existing muted metadata, active badge, FVCC-themed link hover, compact table widths, and blank-value table presentation were retained where already shared safely.
- FVCC Milestones now defines active players from the dynamically ordered latest three FVCC seasons, including winter seasons.

## Skipped GRDCC-specific changes

- GRDCC blue palette and accent treatment: skipped to preserve the FVCC theme.
- Annual Report record overrides and supplements: skipped because they are GRDCC data/source behavior.
- Historical Excel matches proxy behavior: skipped because it changes record sourcing rather than presentation.
- GRDCC wording and abbreviated premiership result copy: skipped to retain FVCC language.
- GRDCC grade ordering, duplicate-team combination, and empty-grade filtering rules: skipped because they are club-specific data presentation rules.
- GRDCC active-player exclusions for veterans/classics and its two-season window: unchanged and not applied to FVCC.

## Behaviour confirmation

FVCC source data, statistical values, calculations, rankings, record ordering, palette, and deployment configuration are unchanged. The only non-visual behavior adjustment is the requested FVCC Milestones active-player window, which now uses the latest three available FVCC seasons dynamically and includes winter cricket.
