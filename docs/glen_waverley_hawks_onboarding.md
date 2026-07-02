# Glen Waverley Hawks Onboarding

This is a draft build in progress. Glen Waverley Hawks is not ready for production until the core match and scorecard tables are populated, app validation passes, and localhost smoke confirms the customer pages.

## Placeholder Config

- club_id: glen-waverley-hawks
- display_name: Glen Waverley Hawks Cricket Club
- short_name: Glen Waverley Hawks
- playhq_club_id: 50f7f1e3-86d8-eb11-a7ad-2818780da0cc
- playcricket_club_id: 50f7f1e3-86d8-eb11-a7ad-2818780da0cc
- playhq_org_id: TBD
- seasons: TBD
- logo_path: clubs/glen-waverley-hawks/assets/logo.png
- primary_colour: #FCD207
- secondary_colour: #280B04
- accent_colour: #62431A
- muted_accent_colour: #B39125
- cream_accent_colour: #EDC778

## Required Before Build

1. Confirm official club name and short name.
2. Confirm PlayHQ organisation ID, team IDs, competition IDs, and seasons if the public club UUID is not enough for a full refresh.
3. Confirm the saved logo asset renders cleanly in Streamlit.
4. Confirm whether historical Excel or manual records will be added later.
5. Keep optional GRDCC historical rules disabled unless Glen Waverley Hawks has equivalent reviewed source material.
6. Run the PlayHQ pipeline and validators before promoting the dedicated entrypoint to production.
