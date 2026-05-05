# GA4 Analytics Setup

The Scorebook supports optional Google Analytics 4 tracking. If no GA4 measurement ID is configured, analytics stays off and the app runs normally.

## Create a GA4 Property

1. Go to [Google Analytics](https://analytics.google.com/).
2. Create a GA4 property for The Scorebook.
3. Add a Web data stream for the deployed Streamlit app URL.
4. Copy the Measurement ID. It looks like `G-XXXXXXXXXX`.

## Configure Streamlit

In Streamlit Cloud, open the app settings and add this secret:

```toml
GA4_MEASUREMENT_ID = "G-XXXXXXXXXX"
```

For local testing, either add the same value to `.streamlit/secrets.toml` or run with an environment variable:

```bash
export GA4_MEASUREMENT_ID="G-XXXXXXXXXX"
./.venv-app/bin/streamlit run app.py --server.port 8502
```

Do not commit local secrets.

## Events Tracked

- `page_view`: Hall of Fame, Season Overview, Milestone, Player Profile.
- `hall_of_fame_view`: Hall of Fame page loaded.
- `fastest_milestones_view`: Fastest Batting Milestones section loaded.
- `player_profile_view`: a public player profile is viewed.
- `season_filter_change`: Season Overview season selection state.
- `team_filter_change`: Season Overview team/grade selection state.
- `playcricket_scorecard_click`: PlayCricket scorecard link clicked where the link is rendered in app HTML.

Tracked parameters are intentionally lightweight: page slug/title, public player slug/name, selected season/team labels, public PlayCricket match ID, and section name.

## Privacy Notes

Analytics are for understanding app usage. The app should not track private user-entered text, emails, phone numbers, credentials, or sensitive personal data. Player names and slugs are already public within the app and sourced from public cricket records.

## Verify in GA4

1. Open Google Analytics Realtime.
2. Open the deployed app.
3. Navigate between the four main pages.
4. Open a player profile.
5. Click a PlayCricket scorecard link.
6. Confirm events appear in Realtime or DebugView after a short delay.

If events do not appear, confirm `GA4_MEASUREMENT_ID` is present in Streamlit secrets and reboot the Streamlit app.
