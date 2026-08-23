# GWHCC Production Runtime Manifest

This manifest describes the files needed by the customer-facing Glen Waverley Hawks Scorebook when launched with `streamlit run app_gwhcc.py`.

## REQUIRED IN PRODUCTION

- `app_gwhcc.py`, `app.py`, and `src/`: application entrypoint, routing, shared UI, data preparation, identity, governance, analytics, and theme code.
- `requirements.txt`: pinned Python runtime dependencies.
- `.streamlit/config.toml`: shared Streamlit theme configuration. It does not set a server port.
- `assets/icons/`: KPI and navigation image assets used by the shared UI.
- `clubs/glen-waverley-hawks/club_config.yaml`: GWHCC identity, feature flags, theme, match policy, milestone policy, and repository-relative data paths.
- `clubs/glen-waverley-hawks/assets/logo.png`: customer logo.
- `clubs/glen-waverley-hawks/{player_aliases.csv,manual_player_merges.csv,team_grade_mappings.csv,opponent_mappings.csv,ground_mappings.csv}`: governed identity and display mappings read by the app.
- `clubs/glen-waverley-hawks/data/source/gwhcc_grade_competition_normalisation.csv`: governed grade labels, categories, scopes, and ordering metadata.
- `clubs/glen-waverley-hawks/data/source/document_overrides/gwhcc_record_overrides.csv`: approved career record supplements.
- `clubs/glen-waverley-hawks/data/source/document_overrides/gwhcc_premierships.csv`: approved premiership supplements.
- `clubs/glen-waverley-hawks/data/source/document_overrides/gwhcc_premiership_players.csv`: approved player-premiership supplements.
- `clubs/glen-waverley-hawks/data/source/document_overrides/gwhcc_document_player_aliases.csv`: approved document-to-PlayCricket identity aliases.
- `clubs/glen-waverley-hawks/data/source/document_overrides/gwhcc_historical_seasons.csv`: verified pre-PlayCricket season-existence metadata and concise historical facts used by Season Overview.
- `clubs/glen-waverley-hawks/data/metadata.json`: source refresh metadata used for cache versioning.
- `clubs/glen-waverley-hawks/data/processed/{all_seasons_batting.csv,all_seasons_bowling.csv,all_seasons_fielding.csv,all_seasons_matches.csv,players.csv,seasons.csv,teams.csv}`: core customer-facing match, player, season, and team data.
- `clubs/glen-waverley-hawks/data/processed/hall_of_fame/`: Hall of Fame source tables and the six deploy-safe `prepared_*` snapshots. `prepared_core_manifest.json` validates the snapshots against SHA-256 signatures of their authoritative inputs.
- `clubs/glen-waverley-hawks/data/processed/season_overview/`: Season by Round, scorecard milestone, and ball-by-ball scope tables.
- `clubs/glen-waverley-hawks/data/processed/player_profile/`: Career Breakdown, Player DNA, dismissal, and recent-form tables.

The GWHCC config sets `allow_legacy_fallback: false`, so the production app does not depend on the repository-level legacy `data/` tree.

## BUILD/ADMIN ONLY

- `scripts/`: PlayCricket refresh, processed-data builders, Hall of Fame snapshot builder, document extraction, reconciliation, and governance utilities.
- `clubs/glen-waverley-hawks/data/processed/all_seasons_scorecard_*.csv`: retained source/build outputs; normal customer rendering uses the derived Hall of Fame, Season Overview, and Player Profile tables.
- `clubs/glen-waverley-hawks/data/source/document_overrides/extracted/` and `review/`: extraction and review evidence, not read during customer rendering.

## TEST/VALIDATION ONLY

- `tests/`: automated calculation, privacy, identity, UI-contract, and release regression tests.
- `scripts/validate_*.py`: validation entrypoints.
- `clubs/glen-waverley-hawks/data/processed/validation/` and `data/processed/validation/`: audit evidence and generated validator results; not used to render the four production pages.

## DEVELOPMENT/DEBUG ONLY

- `.venv/`, `.venv-app/`, `.pytest_cache/`, `__pycache__/`, and Streamlit local cache/runtime directories.
- `data/debug_biggest_improvers.csv`, `data/debug_player_vs_peers.csv`, performance profiles, logs, temporary browser output, and local diagnostics.
- Runtime debug/profile exports are opt-in and disabled by default.

## RAW/ARCHIVE DATA NOT REQUIRED AT RUNTIME

- `clubs/glen-waverley-hawks/data/source/document_overrides/raw/`: club-supplied PDF/DOC evidence.
- `clubs/glen-waverley-hawks/data/source/excel/`: historical Excel evidence and reconciliation input.
- repository backups, recovery artifacts, and other clubs' raw/source data.

These sources remain valuable for governed rebuilds and auditability, but the deployed app reads the approved compact CSV overrides and processed app tables instead.
