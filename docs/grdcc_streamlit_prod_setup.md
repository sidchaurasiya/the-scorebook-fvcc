## GRDCC Streamlit Production Setup

Recommended app name:
- `the-scorebook-grdcc`

Repository:
- Same GitHub repository as FVCC

Branch:
- `main`
- `client/georges-river-district-build` is also valid if branch-specific deployment is preferred, but `main` now contains the synced tested state.

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
   - or select `main` to mirror the now-synced FVCC production branch
4. Set main file to `app.py`
5. Add `CLUB_ID=georges-river-district`
6. Add `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false`
7. Deploy
8. Smoke test Hall of Fame, Season Overview, Player Profile, and Milestones
