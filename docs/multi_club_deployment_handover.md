# Multi-Club Deployment Handover

This handover is for future private Streamlit previews of The Scorebook pilot clubs. Do not deploy a club until payment or explicit approval is received.

## Deployment Target

- Branch: `onboarding/multi-club-positive-responses`
- Final local commit: `Finalize multi-club pilot deployment readiness` or newer
- App entrypoint: `app.py`
- Runtime mode: production-style club preview
- Experimental pages: off

## Required Streamlit Settings

Set these per deployment:

| setting | value |
|---|---|
| `CLUB_ID` | the target club id, for example `southside-east-caulfield` |
| `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES` | `false` |
| `GA4_MEASUREMENT_ID` | existing shared GA4 id, if analytics should be active |

Do not create separate GA4 measurement IDs unless explicitly requested later. The app sends club context through event parameters.

## Recommended Deployment Model

Use one private Streamlit deployment per approved club. This reduces the risk of switching a shared deployment to the wrong `CLUB_ID` and makes rollback simple.

| club_id | Streamlit `CLUB_ID` | readiness | caveats | recommended deploy order |
|---|---|---|---|---:|
| `southside-east-caulfield` | `southside-east-caulfield` | Preview-ready with caveats | 14 manual duplicate groups; one premiership captain remains blank where not locally verified | 1 |
| `glen-waverley-hawks` | `glen-waverley-hawks` | Preview-ready with caveats | duplicate and self-opponent mapping review recommended | 2 |
| `ashwood` | `ashwood` | Preview-ready with caveats | duplicate/team-grade review; Men/Women data present | 3 |
| `reynella` | `reynella` | Preview-ready with caveats | duplicate/team-grade review; Men/Women data present | 4 |
| `plenty` | `plenty` | Preview-ready with caveats | large historical premiership set; mapping review recommended | 5 |
| `georges-river-district` | `georges-river-district` | Preview-ready with caveats | highest data QA risk; duplicate review and mapping review recommended | 6 |

FVCC is regression-only for this branch unless explicitly deploying the current FVCC app.

## What To Do When A Club Pays

1. Confirm the target `club_id` and official club name.
2. Confirm the branch is up to date locally and reviewed.
3. Confirm the club has a clean go/no-go note or caveat summary.
4. Create a private Streamlit app using this branch.
5. Add required settings:
   - `CLUB_ID=<club_id>`
   - `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false`
   - `GA4_MEASUREMENT_ID=<existing id>` if analytics is enabled
6. Deploy privately.
7. Run the post-deploy smoke checklist below.
8. Share only after smoke checks pass.

## Post-Deployment Smoke Checklist

For each deployed club:

- Open Hall of Fame.
- Confirm club name, colours, and sidebar are correct.
- Confirm no FVCC text/data appears in non-FVCC apps.
- Confirm Premierships are populated only where verified or show a clean empty state.
- Confirm Iconic Performances and Fastest Innings use club colours.
- Confirm Fastest Innings has no impossible 50/100 values.
- Open Season Overview.
- Confirm Season by Round loads and scorecard links are present where expected.
- Open Milestone.
- Confirm tabs and milestone cards load.
- Open Player Profile.
- Confirm player selector, Recent Form, Career Breakdown, and Player DNA sections load or show clean empty states.
- Click a representative player link and a scorecard link.
- Check no visible `NaN`, `None`, raw GUIDs, or tracebacks.
- Check GA4 Realtime shows an event with `club_id` and `club_name`.
- Confirm experimental pages are not exposed.
- Run a mobile/narrow visual check before sending the link.

## Rollback Plan

If a private preview has a blocker:

- Disable or delete the preview deployment.
- If testing on a shared deployment, switch `CLUB_ID` back to the previous safe value.
- Do not merge the branch to main until the blocker is fixed and re-smoked.
- Do not attempt to patch raw/generated match-centre files in production.

## Refresh Workflow

Use the normal local refresh workflow only after approval:

1. Run config checks for the club.
2. Run dry-run refresh checks.
3. Run aggregate refresh only if needed.
4. Run match-centre/backfill only when explicitly approved.
5. Rebuild deploy-safe outputs.
6. Regenerate review pack, but keep it ignored.
7. Re-run smoke and compile checks.
8. Commit only curated runtime data, code, docs, and mapping changes.

## Caveat Language For Clubs

Suggested preview wording:

> This is a private preview built from PlayCricket/PlayHQ scorecards and verified local match data. Some historical duplicates, opponent/ground labels, and older scorecard gaps may still need club review before public release. Ball-by-ball-derived records only appear where verified ball-by-ball data exists.

For premierships:

> Premierships are shown only where a finals or Grand Final scorecard can verify the result. Captains are shown only when the winning team list explicitly records the captain.

For duplicate players:

> Obvious duplicate PlayCricket profiles are merged only when strict no-overlap rules are satisfied. Remaining ambiguous duplicates are held for manual confirmation.

## Do Not Commit Or Deploy

Do not commit or deploy:

- raw PlayCricket JSON
- `data/raw/match_centre/`
- `data/processed/match_centre/`
- `data/processed/experimental/`
- review packs
- cache files
- backups
- generated debug/audit CSVs

## Final Notes

Southside is the recommended first deployment candidate. Georges River should receive the most careful data QA before a client preview because it had the highest remaining duplicate risk and a malformed local bowling figure that was fixed during final hardening.
