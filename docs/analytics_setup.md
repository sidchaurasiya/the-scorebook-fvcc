# GA4 Analytics Setup

The Scorebook supports optional Google Analytics 4 tracking. If no GA4 measurement ID is configured, analytics stays off and the app runs normally. Multi-club event policy lives in `docs/analytics_tracking.md`.

Current shared GA4 Measurement ID: `G-D0D39PLD1X`.

## Create a GA4 Property

1. Go to [Google Analytics](https://analytics.google.com/).
2. Create one GA4 property for The Scorebook.
3. Add Web data streams for deployed Scorebook app URLs such as FVCC production and Le Page demo.
4. Copy the Measurement ID. It looks like `G-XXXXXXXXXX`.

## Configure Streamlit

In Streamlit Cloud, open the app settings and add this secret:

```toml
GA4_MEASUREMENT_ID = "G-D0D39PLD1X"
```

For local testing, either add the same value to `.streamlit/secrets.toml` or run with an environment variable:

```bash
export GA4_MEASUREMENT_ID="G-D0D39PLD1X"
./.venv-app/bin/streamlit run app.py --server.port 8502
```

Do not commit local secrets.

## Events Tracked

- `page_view`: Hall of Fame, Season Overview, Milestone, Player Profile.
- `scorebook_page_view`: Scorebook-specific page view event with club and page context.
- `hall_of_fame_view`: Hall of Fame page loaded.
- `fastest_milestones_view`: Fastest Batting Milestones section loaded.
- `player_profile_view`: a public player profile is viewed.
- `season_selected`: Season Overview season selection state.
- `team_selected`: Season Overview team/grade selection state.
- `scorecard_link_click`: PlayCricket scorecard link clicked where the link is rendered in app HTML.
- `section_view`: Major sections rendered in the app.

Tracked parameters are intentionally lightweight: page slug/title, public player slug/name, selected season/team labels, public PlayCricket match ID, scorecard URL, outbound flag, source parameters, and section name.

Across clubs, events are enriched with `app_area=scorebook`, `club_id`, and `club_name`. Use the same GA4 measurement ID for every pilot club unless a future club-specific override is explicitly introduced. Use `club_id` in GA4 reports or Explorations to separate FVCC, Le Page Park, GRDCC, Southside, and future club traffic.

Keep-awake GitHub Actions visits include `source=keep_awake` and `traffic_source=keep_awake`, so they can be filtered out of user-behaviour reporting.

## Privacy Notes

Analytics are for understanding app usage. The app should not track private user-entered text, emails, phone numbers, credentials, or sensitive personal data. Player names and slugs are already public within the app and sourced from public cricket records.

## Verify in GA4

1. Open Google Analytics and select the shared Scorebook property.
2. Go to **Reports → Realtime**.
3. Open a deployed app, such as FVCC production or Le Page demo.
4. Navigate between the four main pages.
4. Open a player profile.
5. Click a PlayCricket scorecard link.
6. Confirm events appear in Realtime after a short delay.
7. Inspect event parameters and confirm `club_id`, `club_name`, `page_slug`, and any relevant `selected_season`, `selected_team`, `player_slug`, or `section_name` values are present.

Use DebugView only when GA4 debug mode is explicitly enabled for a test session. Normal deployed app checks should use Realtime.

If events do not appear, confirm `GA4_MEASUREMENT_ID` is present in Streamlit secrets and reboot the Streamlit app.
