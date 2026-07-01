## GRDCC Streamlit Production Setup

Recommended app name:
- `the-scorebook-grdcc`

Repository:
- Same GitHub repository as FVCC

Branch:
- `main`

Main file:
- `app_grdcc.py`

Reason:
- The FVCC production app continues to use `app.py`.
- The GRDCC production app should use `app_grdcc.py` so Streamlit Cloud has a distinct deploy target for the same repository and branch.
- `app_grdcc.py` forces `CLUB_ID=georges-river-district` before importing the shared app, so the first deploy cannot accidentally boot as FVCC if secrets are not applied immediately.

Environment variables / secrets:
- `CLUB_ID = "georges-river-district"`
- `SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES = "false"`
- `GA4_MEASUREMENT_ID = "G-D0D39PLD1X"`

Streamlit Secrets TOML:

```toml
CLUB_ID = "georges-river-district"
SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES = "false"
GA4_MEASUREMENT_ID = "G-D0D39PLD1X"
```

Note:
- `CLUB_ID` is also forced by `app_grdcc.py`, but keep it in secrets for clarity and consistency with other club deployments.
- GA4 remains optional in code, but production should set `GA4_MEASUREMENT_ID` so GRDCC traffic is tracked with club-aware event parameters.

FVCC production remains:
- App name: `the-scorebook-fvcc`
- Branch: `main`
- Main file: `app.py`
- Secrets:

```toml
CLUB_ID = "fvcc"
SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES = "false"
GA4_MEASUREMENT_ID = "G-D0D39PLD1X"
```

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
3. Select branch `main`
4. Set main file to `app_grdcc.py`
5. Paste the GRDCC Streamlit Secrets TOML above
7. Deploy
8. Smoke test Hall of Fame, Season Overview, Player Profile, and Milestones
