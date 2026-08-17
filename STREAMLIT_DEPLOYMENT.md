# GWHCC Streamlit Deployment

## Deployment Target

Streamlit Community Cloud

## Deployment Configuration

```text
Repository: sidchaurasiya/the-scorebook-fvcc
Branch: main
Main file path: app_gwhcc.py
Python version: 3.12
Secrets: none required
```

`app_gwhcc.py` sets `CLUB_ID=glen-waverley-hawks` before importing the shared application, so this entrypoint cannot silently fall back to FVCC. Select Python 3.12 in Streamlit Community Cloud's Advanced settings; the validated local release uses Python 3.12.13.

The customer-facing app uses committed processed data and does not need PlayHQ credentials. `GA4_MEASUREMENT_ID` is optional and may be added through Streamlit secrets if production analytics are wanted. Do not commit `.streamlit/secrets.toml`.

## Deployment Steps

1. In Streamlit Community Cloud, create an app from the repository above.
2. Select branch `main` and main file `app_gwhcc.py`.
3. Open Advanced settings and select Python 3.12.
4. Leave Secrets empty unless optional GA4 analytics are being configured.
5. Deploy and review the Cloud build log for dependency or file-path errors.

## Post-Deployment QA

- Confirm the header and sidebar identify Glen Waverley Hawks, with no FVCC or GRDCC content.
- Open Hall of Fame, Season Overview, Milestone, and Player Profile.
- Confirm Hall of Fame uses the prepared snapshots and loads without a long aggregate rebuild.
- In Summer 2025/26, verify Season by Round starts with Compare & Connect, C Grade, then D Grade.
- Test Whole club, C Grade, and D Grade filters and representative scorecard links.
- Open Paul Young, Grant Haye, Nathan Bungey, and one light-history player profile.
- Confirm masked/private players are absent from search, tables, cards, and links.
- Confirm the build diagnostic is hidden and no rerun loop or persistent high CPU occurs.
- If GA4 is configured, confirm page events contain the GWHCC club ID and club name.
