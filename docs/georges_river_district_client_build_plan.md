# Georges River District Client Build Plan

## Status

- Paid client: yes
- Build status: commencing full client-ready build
- Current branch: `client/georges-river-district-build`
- Base branch: `onboarding/multi-club-positive-responses`
- Club ID: `georges-river-district`
- Official PlayCricket ID: `a115d93f-87d8-eb11-a7ad-2818780da0cc`

## Branding Palette

| Token | Colour | Use |
|---|---|---|
| primary | `#0B3F9F` | Royal / deep blue brand anchor |
| primary_dark | `#082A66` | Navy sidebar and dark brand depth |
| secondary | `#79C8EE` | Light sky blue highlight |
| accent | `#D7193F` | Small red accent only |
| background | `#F3F9FD` | Very light blue-white page background |
| surface | `#FFFFFF` | Cards and panels |
| text | `#061A3D` | Main body text |
| muted_text | `#66758D` | Secondary and helper text |
| border | `#D8E8F5` | Card and table borders |
| positive | `#1B8A5A` | Success/positive states |
| negative | `#B23A48` | Errors/negative states |
| warning/gold | `#D6A732` | Trophy / premiership / award accents |

## Existing Pilot Status

- GRDCC already has a pilot club config and processed deploy-safe outputs.
- Latest processed season present locally: `Summer 2025/26`.
- Pilot state before this paid build: `Preview-ready with caveats`.
- Highest QA risk in the pilot notes: Georges River was called out as the highest-risk club after a malformed bowling row was fixed during final hardening.

## Known Pilot Caveats

- Duplicate player review is still needed for ambiguous merges.
- Team and grade naming still needs a human pass, especially where club and opponent labels are similar.
- Opponent and ground mappings are conservative and not fully complete.
- Premiership and captain evidence should stay strictly verified from finals / Grand Final scorecards.
- Women / men classification should be checked against the local data shape before exposing any toggle assumptions.
- Fastest innings records must remain validated against ball-by-ball progression only.
- Win-rate denominators should stay explicit so missing coverage does not become a fake zero.
- Scorecard links should be spot-checked on the live app before sharing.
- Mobile layout should get one final visual check before client preview.

## Highest-Risk Review Items Before Client Share

1. Duplicate profiles.
2. Team / grade naming.
3. Opponent / ground mappings.
4. Premiership and captain evidence.
5. Women / men classification, if applicable.
6. Scorecard link spot checks.
7. Fastest innings validation.
8. Win-rate denominator clarity.
9. Mobile smoke check.

## Proposed Next Phases

1. Branding and theme pass.
2. Data QA and mapping review.
3. GRDCC-specific smoke and UAT.
4. Client preview deployment.
5. Post-client feedback fixes.

## Notes

- Keep `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false`.
- Do not stage raw or debug/generated review-pack files.
- Do not fabricate premierships, captaincy, duplicate merges, or mapping rows.
- Do not fall back to FVCC data for non-FVCC clubs.
