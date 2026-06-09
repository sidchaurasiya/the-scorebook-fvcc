# Analytics Tracking

The Scorebook uses optional GA4 tracking through `GA4_MEASUREMENT_ID`. If the measurement ID is absent locally or in Streamlit secrets, analytics is a no-op and the app continues to run normally.

Current shared GA4 Measurement ID: `G-D0D39PLD1X`.

## Multi-Club Policy

- All configured clubs share the same GA4 measurement ID unless a future club config explicitly introduces an override.
- Do not create separate measurement IDs per club during onboarding.
- Include `club_id` and `club_name` on analytics events so GA4 can report usage by club through event parameters or custom dimensions.
- Include `app_area=scorebook` on Scorebook app events.

## Standard Event Context

Every event should include the shared context where available:

- `app_area`
- `club_id`
- `club_name`
- `page_name`
- `page_slug`
- `section_name`
- public `player_name` / `player_id` where relevant
- `player_slug`
- `selected_season`
- `selected_team`
- `scorecard_url`
- `outbound`
- `source` / `traffic_source` where a visit source is supplied

The app helper enriches events with `app_area=scorebook`, the active club id/name, and page context. Existing event-specific parameters remain lightweight and public.

## Keep-Awake Traffic

The scheduled keep-awake workflow appends `source=keep_awake` to each Streamlit URL. GA4 events from those visits include `source=keep_awake` and `traffic_source=keep_awake`, allowing dashboards to exclude automated traffic while still proving the app received a real browser visit.

Use Realtime to check immediate events. Use DebugView only when debug mode is deliberately enabled for a test session.

## Privacy

Do not track private user-entered data, emails, phone numbers, credentials, or sensitive personal information. Public player names, public player ids, seasons, team/grade labels, and public PlayCricket scorecard context are acceptable because they are already part of the public cricket record and visible in the app.

## Pilot Clubs

The current pilot onboarding uses shared GA4 tracking for:

- `fvcc`
- `le-page-park`
- `reynella`
- `ashwood`
- `glen-waverley-hawks`
- `plenty`
- `georges-river-district`
- `southside-east-caulfield`

For GA4 reporting, register `club_id` as a custom dimension before relying on club-level dashboards.
