## GRDCC Streamlit Production Setup

Recommended app name:
- `the-scorebook-grdcc`

Repository:
- Same GitHub repository as FVCC

Branch:
- `client/georges-river-district-build`
- If Streamlit Cloud is later confirmed to deploy from `main`, switch to the deployed branch only after the same GRDCC/FVCC commits land there.

Main file:
- `app.py`

Environment variables / secrets:
- `CLUB_ID=georges-river-district`
- `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false`

Recommended Streamlit configuration:
- Keep production headless
- Disable file watching if `.streamlit/config.toml` is used for server settings
- Do not enable debug or performance profiling flags in production unless troubleshooting

Expected production behaviour:
- GRDCC app opens directly as Georges River District Cricket Club
- FVCC app remains FVCC in its own Streamlit app
- No shared-state bleed between FVCC and GRDCC
- GRDCC Annual Report overrides remain active
- GRDCC source-priority rules remain active
- FVCC latest data remains isolated to the FVCC app

Deployment checklist:
1. Create a new Streamlit Cloud app
2. Select the existing GitHub repository
3. Select branch `client/georges-river-district-build`
4. Set main file to `app.py`
5. Add `CLUB_ID=georges-river-district`
6. Add `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false`
7. Deploy
8. Smoke test Hall of Fame, Season Overview, Player Profile, and Milestones
