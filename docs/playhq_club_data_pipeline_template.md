# PlayHQ Club Data Pipeline Template

This template describes the intended sequence for a future PlayHQ-backed club. Existing scripts are partially club-aware, but a fully automated new-club PlayHQ pipeline still needs club-specific IDs and source coverage confirmation.

## Standard Sequence

1. Identify PlayHQ club, organisation, team, competition, and season IDs.
2. Pull match lists by season, team, and competition.
3. Pull scorecards for each matched fixture.
4. Pull player stats.
5. Pull ball-by-ball for matches where available.
6. Build raw files under `clubs/<club_id>/data/raw/`.
7. Build processed app files under `clubs/<club_id>/data/processed/`.
8. Build app-facing aggregates:
   - player-season
   - career
   - Hall of Fame
   - milestones
   - season overview
   - scorecards
   - BBB summaries
9. Run validators.
10. Start the local app with `CLUB_ID=<club_id>`.

## Existing Commands

Dry-run the aggregate refresh:

```bash
./.venv-app/bin/python scripts/refresh_data.py --club <club_id> --dry-run
```

Refresh aggregate data when the club config has a valid PlayHQ/PlayCricket ID:

```bash
./.venv-app/bin/python scripts/refresh_data.py --club <club_id>
```

Refresh deploy-safe app outputs after aggregate data changes:

```bash
./.venv-app/bin/python scripts/refresh_club_outputs.py --club <club_id>
```

Dry-run match-centre scope discovery:

```bash
./.venv-app/bin/python scripts/refresh_match_centre_data.py --club <club_id> --dry-run
./.venv-app/bin/python scripts/backfill_match_centre_available.py --club <club_id> --dry-run
```

Run locally:

```bash
CLUB_ID=<club_id> SHOW_EXPERIMENTAL_MATCH_CENTRE_PAGES=false ./.venv-app/bin/python -m streamlit run app.py
```

## TODO Before Claiming Automation

- Confirm the current PlayHQ API coverage for the target club.
- Confirm whether ball-by-ball is available by match and season.
- Add explicit new-club validators for source coverage, duplicate identities, and grade/opponent review.
- Confirm the processed output builder handles empty BBB coverage without fake rates.
- Confirm no GRDCC Annual Report, Excel, match proxy, or exact-name merge rules are enabled unless explicitly configured.
