# Le Page Park Demo Cleanup Report

## Status
The Le Page Park demo is now restricted to Steve McConchie in Player Profile flows.

Local demo URL: http://localhost:8510/?page=hall-of-fame
Demo default season: Summer 2022/23

## What Changed
- Merged the two Steve McConchie player identities into one demo-visible profile.
- Restricted player-profile links so only Steve McConchie remains clickable.
- Left all other player names as plain text in demo contexts.
- Rebuilt deploy-safe club outputs and the Le Page Park review pack from local inputs.

## Visible Checks
- Hall of Fame loads and uses the Le Page Park theme.
- Season Overview loads.
- Milestone loads.
- Player Profile loads.
- Player Profile selector now shows only Steve McConchie.
- Steve player links route correctly to Player Profile.
- Non-Steve player links are disabled/plain text in the demo.
- Steve bowling phase data is present and renders cleanly.
- Mobile/narrow layout still holds together.

## Data Caveats
- `safe_auto_merge_candidates.csv` has `0` rows for this club.
- `manual_duplicate_review_candidates.csv` still has `3` rows.
- Remaining manual duplicate review groups are:
  - Chris Woodford, season overlap blocks safe merge
  - Rehatt Singh, season overlap blocks safe merge
  - Kay Rabadi, similarity-only manual review
- The review pack still shows some masked player names as `********` from local source data. That is a source-data artifact, not a UI bug.
- Some scorecard-derived names still show mixed casing in lower-level chips/labels, but the demo profile itself is now cleanly centered on Steve.

## Potential Demo Risks
- A few masked identities remain in season-based source rows.
- Other player profiles are intentionally inaccessible in the demo, so any non-Steve deep link will fall back to plain text or the allowed Steve profile.
- The restriction is demo-only; it does not delete underlying data.
- The demo still retains Summer 2025/26 in the selector for comparison, but the landing season is now Summer 2022/23.

## Final Take
This is a safer client demo now: one clear selectable player, no confusing alternate profiles, and no clickable non-Steve player links to wander into.
