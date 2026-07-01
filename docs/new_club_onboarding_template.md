# New Club Onboarding Template

This checklist turns the current GRDCC-ready Scorebook experience into a repeatable setup for a new club. The reusable template layer owns layout, theme, responsive behavior, cards, tabs, scrolling, GA4 injection, caching, and Streamlit entrypoint shape. Club-specific historical or manual rules stay opt-in through club config flags.

## Architecture Layers

### 1. Reusable Template Layer

- Page layout and navigation
- Premium KPI cards and Career Highlights cards
- Season by Round desktop horizontal layout
- Season by Round mobile compact layout with right-side result badges
- Horizontal hover scrolling for wide visuals
- Milestone tabs and mobile one-line tab behavior
- Career Breakdown tabs and mobile two-row layout
- Player Profile visual system
- Hall of Fame card/list design
- Team/Grade Leaders card design
- Page performance and caching patterns
- GA4 injection with club metadata
- Dedicated Streamlit entrypoint pattern

### 2. Club Config Layer

- club_id
- display_name
- short_name
- slug
- data_dir
- logo_path
- primary_colour
- secondary_colour
- accent_colour
- background_colour
- link_colour
- link_hover_colour
- nav_active_colour
- source_systems
- playhq_config
- GA metadata
- Streamlit entrypoint
- Optional customer-facing URL

### 3. Reusable Data Pipeline

- PlayHQ club/player data pull
- PlayHQ match list pull
- PlayHQ scorecard pull
- PlayHQ ball-by-ball pull when available
- Player identity baseline
- Player-season aggregation
- Career aggregation
- Season Overview aggregation
- Hall of Fame aggregation
- Milestone aggregation
- Player Profile source generation

### 4. Optional Club-Specific Rule Modules

- Historical Excel ingestion
- Annual Report overrides
- Historical match-count proxy
- Exact-name no-season-overlap merge
- Grade/opponent normalisation maps
- Manual anomaly decisions
- Source-priority rules

These modules must be disabled by default for new clubs and enabled only through explicit club config flags.

## Onboarding Checklist

1. Create the new club config under `clubs/<club_id>/club_config.yaml`.
2. Add club colours and logo path after customer confirmation.
3. Confirm PlayHQ organisation, club, team, competition, and season IDs.
4. Confirm seasons to ingest.
5. Run data refreshes:
   - Match list
   - Scorecards
   - Player stats
   - Ball-by-ball where available
6. Validate data:
   - Match count
   - Player count
   - Scorecard coverage
   - BBB coverage
   - Duplicate identity check
   - Grade/opponent normalisation review
7. Validate app pages:
   - Hall of Fame
   - Season Overview
   - Player Profile
   - Milestones
8. Prepare deployment:
   - Dedicated `app_<club>.py` entrypoint
   - Streamlit app URL
   - Secrets TOML
   - GA4 check

## Dedicated Entrypoint Pattern

Future customer apps can use this pattern:

```python
"""Dedicated Streamlit Cloud entrypoint for <Club Name>."""

import os

os.environ["CLUB_ID"] = "<club-id>"
os.environ.setdefault("SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES", "false")

import app  # noqa: E402,F401
```

Do not create or wire a production entrypoint until the club config, data coverage, and customer URL are confirmed.
