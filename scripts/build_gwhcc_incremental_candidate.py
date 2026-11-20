"""Build a disjoint-season Hawks candidate outside the repository.

Input is the checkpointed official-source bundle (parsed_current and cached
scorecards/aggregates). No fetching, historical reconstruction, or publication
occurs here. Acceptance requires a separate source/preservation validation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
CLUB = 'glen-waverley-hawks'


def resolve_fixture_captain(match_id: str, club_teams: list[dict], decisions: dict) -> str:
    """Resolve the club-side captain while retaining ambiguity by default."""
    decision = decisions.get(match_id)
    if decision is not None:
        if (decision["status"] != "owner_approved" or decision["scope"] != "whole_fixture"
                or len(club_teams) != 1 or club_teams[0]["id"] != decision["team_id"]):
            raise ValueError(f"Captaincy decision does not match the eligible Hawks side for {match_id}")
        participants = [
            player for player in club_teams[0].get("players", [])
            if player.get("participantId") == decision["participant_id"]
        ]
        if len(participants) != 1:
            raise ValueError(f"Approved captain does not match one scorecard participant for {match_id}")

        from src.utils.player_identity import apply_player_identity_mapping, filter_public_player_rows

        player = participants[0]
        identity = apply_player_identity_mapping(pd.DataFrame([{
            "player_id": player["participantId"], "player_name": player.get("name", ""),
        }]), club_id=CLUB)
        public = filter_public_player_rows(identity, club_id=CLUB)
        if public.empty or public.iloc[0]["canonical_player_id"] != decision["canonical_player_id"]:
            raise ValueError(f"Approved captain does not resolve to the governed public identity for {match_id}")
        return str(public.iloc[0]["canonical_player_name"])

    if len(club_teams) != 1:
        return ""
    captains = {
        player.get("participantId"): player.get("name", "")
        for player in club_teams[0].get("players", [])
        if "Captain" in (player.get("roles") or [])
    }
    # Without a decision, multiple names cannot establish innings-level captaincy.
    return next(iter(captains.values())) if len(captains) == 1 and None not in captains else ""


def preserve_existing_profile_names(frame: pd.DataFrame, canonical_names: dict[str, str]) -> pd.DataFrame:
    """Keep raw source names while retaining the published label for known IDs."""
    if frame.empty or 'canonical_player_id' not in frame or 'canonical_player_name' not in frame:
        return frame.copy()
    output = frame.copy()
    existing_names = output['canonical_player_id'].astype(str).map(canonical_names)
    mask = existing_names.notna() & existing_names.astype(str).str.strip().ne('')
    output.loc[mask, 'canonical_player_name'] = existing_names.loc[mask]
    return output


def add_verified_scorecard_appearances(
    appearances: pd.DataFrame,
    scorecard_frames: dict[str, pd.DataFrame],
    *,
    team_ids: set[str],
    match_weights: dict[str, float],
    baseline_public_ids: set[str],
) -> pd.DataFrame:
    """Union exact scorecard participants into selected-team appearances.

    Some finalized scorecards list an exact public participant omitted from the
    team-summary player list. Use only participant/team/match IDs from the
    official scorecard and keep identities that already resolve to a governed
    public profile. Ambiguous labels and reused masked tokens do not create a
    career identity here.
    """
    from src.data.gwhcc_masked_privacy import is_masked_hawks_participant_id
    from src.utils.player_identity import apply_player_identity_mapping, public_player_mask

    allowed_teams = {str(value) for value in team_ids}
    scorecard_rows = []
    for category in ("batting", "bowling", "fielding"):
        frame = scorecard_frames.get(category, pd.DataFrame())
        if frame.empty or not {"match_id", "team_id", "participant_id", "player_name"}.issubset(frame.columns):
            continue
        selected = frame.loc[
            frame["team_id"].astype(str).isin(allowed_teams)
            & frame["match_id"].astype(str).isin(match_weights)
        ]
        for row in selected[["match_id", "team_id", "participant_id", "player_name"]].to_dict("records"):
            match_id = str(row.get("match_id", "")).strip()
            team_id = str(row.get("team_id", "")).strip()
            player_id = str(row.get("participant_id", "")).strip()
            player_name = str(row.get("player_name", "")).strip()
            if not match_id or not team_id or not player_id or not player_name:
                continue
            if player_name.casefold() in {"nan", "none", "null"}:
                continue
            if is_masked_hawks_participant_id(player_id):
                continue
            # A DNB-only batting line does not establish a scorecard-only
            # appearance. Count it only when another official scorecard
            # discipline records actual play; existing selected-team roster
            # appearances remain in the base input.
            if category == "batting" and "dismissal_type" in frame.columns:
                source_row = selected.loc[
                    selected["match_id"].astype(str).eq(match_id)
                    & selected["team_id"].astype(str).eq(team_id)
                    & selected["participant_id"].astype(str).eq(player_id)
                ].iloc[0]
                dismissal = str(source_row.get("dismissal_type", "")).strip().casefold()
                runs = pd.to_numeric(pd.Series([source_row.get("runs_scored")]), errors="coerce").fillna(0).iloc[0]
                balls = pd.to_numeric(pd.Series([source_row.get("balls_faced")]), errors="coerce").fillna(0).iloc[0]
                if "did not bat" in dismissal and float(runs) == 0 and float(balls) == 0:
                    continue
            if category == "bowling":
                source_rows = selected.loc[
                    selected["match_id"].astype(str).eq(match_id)
                    & selected["team_id"].astype(str).eq(team_id)
                    & selected["participant_id"].astype(str).eq(player_id)
                ]
                evidence_columns = [
                    column
                    for column in ("overs_bowled", "runs_conceded", "wickets_taken", "wides", "no_balls", "maidens_bowled")
                    if column in source_rows.columns
                ]
                has_play = any(
                    pd.to_numeric(source_rows[column], errors="coerce").fillna(0).gt(0).any()
                    for column in evidence_columns
                )
                if not has_play:
                    continue
            if category == "fielding":
                source_rows = selected.loc[
                    selected["match_id"].astype(str).eq(match_id)
                    & selected["team_id"].astype(str).eq(team_id)
                    & selected["participant_id"].astype(str).eq(player_id)
                ]
                evidence_columns = [
                    column
                    for column in ("catches", "stumpings", "run_outs", "assisted_run_outs")
                    if column in source_rows.columns
                ]
                has_play = any(
                    pd.to_numeric(source_rows[column], errors="coerce").fillna(0).gt(0).any()
                    for column in evidence_columns
                )
                if not has_play:
                    continue
            scorecard_rows.append(
                {
                    "match_id": match_id,
                    "team_id": team_id,
                    "player_id": player_id,
                    "player_name": player_name,
                    "weight": float(match_weights[match_id]),
                }
            )
    if not scorecard_rows:
        return appearances.copy()

    scorecard_appearances = pd.DataFrame(scorecard_rows)
    # If one source ID carries conflicting visible labels in the selected
    # scorecards, do not use it to create an aggregate identity.
    names_per_id = scorecard_appearances.groupby("player_id")["player_name"].nunique()
    conflict_ids = set(names_per_id[names_per_id.gt(1)].index.astype(str))
    scorecard_appearances = scorecard_appearances.loc[
        ~scorecard_appearances["player_id"].astype(str).isin(conflict_ids)
    ].copy()
    if scorecard_appearances.empty:
        return appearances.copy()

    identity_rows = scorecard_appearances[["player_id", "player_name"]].drop_duplicates().copy()
    identity_rows["raw_player_id"] = identity_rows["player_id"]
    mapped = apply_player_identity_mapping(identity_rows, club_id=CLUB)
    public = public_player_mask(mapped, club_id=CLUB)
    mapped = mapped.loc[public & mapped["canonical_player_id"].astype(str).isin(baseline_public_ids)]
    safe_ids = set(mapped["player_id"].astype(str))
    scorecard_appearances = scorecard_appearances.loc[
        scorecard_appearances["player_id"].astype(str).isin(safe_ids)
    ].copy()
    if scorecard_appearances.empty:
        return appearances.copy()

    base = appearances.copy()
    for column in ("match_id", "team_id", "player_id", "player_name", "weight"):
        if column not in base:
            base[column] = pd.NA
    combined = pd.concat([scorecard_appearances, base], ignore_index=True, sort=False)
    combined = combined.drop_duplicates(["match_id", "team_id", "player_id"], keep="last")
    return combined.reset_index(drop=True)


def append_current_aggregates_preserving_anonymous_history(
    historical: pd.DataFrame,
    current: pd.DataFrame,
    keys: list[str],
) -> pd.DataFrame:
    """Append current public aggregates without merging anonymous history.

    The accepted baseline may contain privacy-safe historical rows whose
    player IDs were cleared. Keep those rows as separate anonymous statistics;
    validate the person-level append only for rows with an exact public identity.
    """
    from src.data.gwhcc_incremental import append_disjoint
    from src.utils.player_identity import is_private_or_anonymised_player

    from src.data.public_generic_identity_privacy import sanitize_public_identity_frame

    old = historical.copy()
    new = current.copy()
    for frame, label in ((old, "historical"), (new, "current")):
        if "player_id" not in frame:
            raise ValueError(f"{label} aggregate is missing player_id")

    # Clear source IDs from generic rows before they enter an aggregate output.
    # Their separate rows and numbers remain present, but they never participate
    # in the person-key duplicate check or a named career record.
    old, _ = sanitize_public_identity_frame(
        old, club_id=CLUB, relative_path="all_seasons_historical_aggregate.csv"
    )
    new, _ = sanitize_public_identity_frame(
        new, club_id=CLUB, relative_path="all_seasons_current_aggregate.csv"
    )
    name_columns = [column for column in ("player_name", "canonical_player_name", "Player") if column in old.columns]
    generic = pd.Series(False, index=old.index)
    for column in name_columns:
        generic |= old[column].map(is_private_or_anonymised_player)
    missing_id = old["player_id"].fillna("").astype(str).str.strip().eq("")
    anonymous = generic | missing_id
    unsupported_unidentified = missing_id & ~generic
    if unsupported_unidentified.any():
        raise ValueError(
            "Historical aggregate has blank player IDs without a generic privacy label"
        )
    new_generic = pd.Series(False, index=new.index)
    for column in ("player_name", "canonical_player_name", "Player"):
        if column in new.columns:
            new_generic |= new[column].map(is_private_or_anonymised_player)
    new_missing_id = new["player_id"].fillna("").astype(str).str.strip().eq("")
    if (new_missing_id & ~new_generic).any():
        raise ValueError("Current aggregate has blank player IDs without a generic privacy label")
    new_anonymous = new_generic | new_missing_id

    # Validate exact-identity historical/current keys; retain anonymous history
    # and scorecard-backed anonymous current rows separately, without
    # consolidating them through blank IDs.
    append_disjoint(old.loc[~anonymous].copy(), new.loc[~new_anonymous].copy(), keys)
    return pd.concat([old, new], ignore_index=True, sort=False)


def update_metadata(bundle: Path, candidate: Path, cutoff: str) -> None:
    data = candidate / 'clubs' / CLUB / 'data'
    path = data / 'metadata.json'
    metadata = json.loads(path.read_text())
    fetched = [json.loads(file.read_text()).get('request', {}).get('fetched_at', '')
               for file in (bundle / 'source_payloads').glob('*.json')]
    fetched_at = max(fetched)
    metadata['fetch_date_time'] = fetched_at
    metadata['last_successful_refresh_time'] = fetched_at
    metadata['matches_fetched'] = len(pd.read_csv(data / 'processed/all_seasons_matches.csv'))
    metadata['players_fetched'] = len(pd.read_csv(data / 'processed/players.csv'))
    metadata['teams_fetched'] = len(pd.read_csv(data / 'processed/teams.csv'))
    metadata['stat_rows'] = {kind:len(pd.read_csv(data / f'processed/all_seasons_{kind}.csv')) for kind in ['batting','bowling','fielding']}
    season = json.loads((bundle / 'task_state.json').read_text())['season']
    metadata['incremental_refresh'] = {'season': season['name'], 'cutoff': cutoff,
                                       'timezone':'Australia/Melbourne', 'source':'PlayCricket public scorecards and team statistics',
                                       'cached_source_payload_count':len(fetched),
                                       'historical_source_rows_preserved':True}
    metadata['source_endpoints_used'] = list(dict.fromkeys([
        *metadata.get('source_endpoints_used', []),
        '/scores/teams/{team_id}/matches',
        '/scores/matches/{match_id}?responseModifier=includeScorecard',
        '/scores/matches/{match_id}/balls',
    ]))
    metadata['notes'] = [note for note in metadata.get('notes', []) if not note.startswith('Public match/result/scorecard endpoints were not available')]
    for note in [
        'Current-season source-backed incremental refresh; historical match, Captain, premiership and governed career evidence retained.',
        'Request counters describe the prior full backup; the incremental build reads cached current-season source receipts.',
    ]:
        if note not in metadata['notes']:
            metadata['notes'].append(note)
    path.write_text(json.dumps(metadata, indent=2) + '\n')


def build(bundle: Path, candidate: Path, cutoff: str, baseline_root: Path = ROOT) -> dict:
    if candidate == ROOT or ROOT in candidate.parents or candidate.exists():
        raise ValueError('Candidate must be a new outside-repository directory')
    os.environ['CLUB_ID'] = CLUB
    from src.data.gwhcc_incremental import append_disjoint, eligible_match_ids, merge_summary, reconciled_delivery_innings, preserve_compact_dismissal_type, profile_fielding_input
    from src.config import club_config as config
    from src.data.playcricket_ingestion import normalize_teams, normalize_players
    from src.utils.player_identity import apply_player_identity_mapping, filter_public_player_rows
    from src.data.gwhcc_governance import annotate_grade_metadata

    club = baseline_root / 'clubs' / CLUB
    output_club = candidate / 'clubs' / CLUB
    shutil.copytree(club, output_club)
    # A statistical seed may predate the owner decision. Use the reviewed
    # policy from this checkout and retain it in the resulting candidate.
    relative_decisions = Path('data/source/fixture_captaincy_decisions.json')
    decision_path = ROOT / 'clubs' / CLUB / relative_decisions
    captaincy_decisions = json.loads(decision_path.read_text()) if decision_path.is_file() else {}
    if decision_path.is_file():
        shutil.copy2(decision_path, output_club / relative_decisions)
    processed = output_club / 'data/processed'
    state = json.loads((bundle / 'task_state.json').read_text())
    season = state['season']
    cache = bundle / 'source_payloads'
    team_receipt = json.loads((cache / 'teams_2026_27.json').read_text())
    organization = config.load_club_config(CLUB)['club']['playcricket_club_id']
    if f'/organisations/{organization}/teams' not in team_receipt['request']['url']:
        raise ValueError('Team receipt is not from the configured GWHCC organization')
    teams_payload = team_receipt['payload']['teams']
    frames = {key: pd.read_csv(bundle / 'parsed_current' / f'{filename}.csv', low_memory=False)
              for key, filename in {'matches':'all_matches', 'innings':'all_match_innings', 'batting':'all_scorecard_batting',
                                    'bowling':'all_scorecard_bowling', 'fielding':'all_scorecard_fielding',
                                    'balls':'all_ball_by_ball', 'overs':'all_overs', 'partnerships':'all_partnerships'}.items()}
    if not frames['matches']['season_id'].eq(season['id']).all() or not frames['matches']['season'].eq(season['name']).all():
        raise ValueError('Parsed matches and declared source season disagree')
    included = eligible_match_ids(frames['matches'], frames['innings'], cutoff)
    historical = pd.read_csv(processed / 'all_seasons_matches.csv')
    if included & set(historical['match_id']):
        raise ValueError('Match overlap with historical application data')
    if any(pd.read_csv(processed / f'all_seasons_{kind}.csv')['season'].eq(season['name']).any()
           for kind in ['batting','bowling','fielding']):
        raise ValueError('Season already contains statistics; changed-season reconciliation required')
    frames = {key: frame[frame['match_id'].isin(included)].copy() for key, frame in frames.items()}
    # All decisions must be explicitly source-ID scoped and approved outside UI.
    approvals = pd.read_csv(bundle / 'approved_identity_mappings.csv', dtype=str).fillna('')
    if not approvals['decision_status'].eq('customer_confirmed').all():
        raise ValueError('Unapproved identity mapping')
    baseline_profiles = pd.read_csv(
        processed / 'hall_of_fame/prepared_career_all_time.csv',
        usecols=['canonical_player_id', 'Player'],
        dtype=str,
    ).fillna('')
    if baseline_profiles['canonical_player_id'].duplicated().any():
        raise ValueError('Existing canonical HOF profiles must have unique IDs')
    baseline_profile_names = dict(zip(baseline_profiles['canonical_player_id'], baseline_profiles['Player']))
    baseline_ids = set(baseline_profile_names)
    if not set(approvals['canonical_player_id']) <= baseline_ids:
        raise ValueError('Identity continuity approval targets a nonexistent historical public profile')
    aliases_path = output_club / 'player_aliases.csv'
    aliases = pd.read_csv(aliases_path, dtype=str).fillna('')
    additions = []
    for row in approvals.to_dict('records'):
        additions.append({column: row.get(column, '') for column in aliases.columns})
    aliases = append_disjoint(aliases, pd.DataFrame(additions), ['raw_player_id'])
    aliases.to_csv(aliases_path, index=False)

    config.REPO_ROOT = candidate
    config.CLUBS_ROOT = candidate / 'clubs'
    config._load_club_config_cached.cache_clear()
    selected = {str(row.match_id): set(str(row.source_team_ids).split('|')) for row in frames['matches'].itertuples()}
    team_ids = {team['id'] for team in teams_payload}
    captains, participation = {}, []
    match_weights = {}
    from src.data.gwhcc_match_policy import match_format
    for match in frames['matches'].to_dict('records'):
        payload = json.loads((cache / f"match={match['match_id']}__scorecard.json").read_text())['payload']
        weight = 0.5 if match_format(pd.Series(match)) == 'T20' else 1.0
        match_weights[str(match['match_id'])] = weight
        club_teams = [team for team in payload.get('teams', [])
                      if team['id'] in selected[match['match_id']] and team['id'] in team_ids]
        for team in club_teams:
            for player in team.get('players', []):
                if player.get('participantId'):
                    participation.append({'match_id':match['match_id'], 'team_id':team['id'], 'player_id':player['participantId'],
                                          'player_name':player.get('name',''), 'weight':weight})
        if match['match_id'] in captaincy_decisions and payload.get('id') != match['match_id']:
            raise ValueError(f"Captaincy decision does not match the retained scorecard for {match['match_id']}")
        captain = resolve_fixture_captain(match['match_id'], club_teams, captaincy_decisions)
        if captain:
            captains[match['match_id']] = captain
    appearances = pd.DataFrame(participation).drop_duplicates(['match_id','team_id','player_id'])
    appearances = add_verified_scorecard_appearances(
        appearances,
        {key: frames[key] for key in ('batting', 'bowling', 'fielding')},
        team_ids=team_ids,
        match_weights=match_weights,
        baseline_public_ids=baseline_ids,
    )
    frames['matches']['club_captain_name'] = frames['matches']['match_id'].map(captains).fillna('')
    weights = appearances.groupby(['team_id','player_id'])['weight'].sum()
    new_teams = []
    for team in teams_payload:
        row = dict(team, season_id=season['id'], season=season['name'])
        new_teams.append(row)
    teams = normalize_teams(new_teams)
    teams = annotate_grade_metadata(teams, 'grade_name')
    old_teams = pd.read_csv(processed / 'teams.csv')
    pd.concat([old_teams[~old_teams['season_id'].eq(season['id'])], teams], ignore_index=True).to_csv(processed / 'teams.csv', index=False)
    aggregate_parts = {}
    from scripts import build_player_profile_insight_exports as profile
    from src.data.gwhcc_finalised_aggregates import (
        filter_club_appearances,
        finalised_aggregate,
        missing_provider_rows,
    )

    excluded = {}
    excluded_dir = bundle / 'parsed_excluded'
    for key in ['matches', 'batting', 'bowling', 'fielding']:
        path = excluded_dir / f'{key}.csv'
        excluded[key] = pd.read_csv(path, low_memory=False) if path.exists() else frames[key].iloc[:0].copy()
    if set(excluded['matches']['match_id']) & included:
        raise ValueError('Excluded source partition overlaps eligible matches')
    if not excluded['matches'].empty:
        excluded_innings = pd.read_csv(excluded_dir / 'innings.csv', low_memory=False)
        if eligible_match_ids(excluded['matches'], excluded_innings, cutoff):
            raise ValueError('Excluded source partition contains eligible played matches')
    prepared = {'batting': profile.prepare_batting(frames,club_id=CLUB),
                'bowling': profile.prepare_bowling(frames,club_id=CLUB), 'fielding':frames['fielding']}
    omitted = {'batting': profile.prepare_batting(excluded,club_id=CLUB),
               'bowling': profile.prepare_bowling(excluded,club_id=CLUB), 'fielding':excluded['fielding']}
    correction_path = bundle / 'verified_scorecard_corrections.csv'
    corrections = pd.read_csv(correction_path) if correction_path.exists() else pd.DataFrame()
    for correction in corrections.to_dict('records'):
        mid = correction['evidence_match_id']
        if mid not in included:
            raise ValueError('Correction certificate references a non-eligible match')
        for suffix, field in [('scorecard','scorecard_payload_sha256'),('balls','balls_payload_sha256')]:
            payload = json.loads((cache / f'match={mid}__{suffix}.json').read_text())['payload']
            digest = hashlib.sha256(json.dumps(payload,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if digest != correction[field]:
                raise ValueError('Correction source payload changed since independent verification')
    appearances = filter_club_appearances(appearances, team_ids)
    canonical_appearances = apply_player_identity_mapping(appearances,club_id=CLUB)
    for kind in ['batting','bowling','fielding']:
        new = pd.read_csv(bundle / f'current_aggregate_{kind}.csv')
        if not new['team_id'].isin(team_ids).all() or not new['season_id'].eq(season['id']).all():
            raise ValueError('Aggregate rows fall outside the discovered current GWHCC scope')
        new, partition_changes = finalised_aggregate(new, prepared[kind], omitted[kind], kind, corrections)
        partition_changes.to_csv(bundle / f'finalised_{kind}_aggregate_changes.csv',index=False)
        new, participation_rows = missing_provider_rows(new, canonical_appearances, frames, baseline_ids, kind, corrections)
        participation_rows.to_csv(bundle / f'participation_only_{kind}_rows.csv',index=False)
        new, _ = finalised_aggregate(new, prepared[kind], omitted[kind], kind, corrections)
        new['raw_playhq_matches'] = new['matches']
        new['matches'] = [weights.get((row.team_id, row.player_id), 0) for row in new.itertuples()]
        new = new[new['matches'].gt(0)].copy()
        new['season_start_date'] = season['startDate']
        new['competition_name'] = new['grade_name']
        new = apply_player_identity_mapping(new, club_id=CLUB)
        new = preserve_existing_profile_names(new, baseline_profile_names)
        new = annotate_grade_metadata(new, 'grade_name')
        new['record_scope'] = 'Whole club'
        new['match_count_policy_note'] = 'T20=0.5; played non-T20=1; no-play=0'
        old = pd.read_csv(processed / f'all_seasons_{kind}.csv', low_memory=False)
        combined = append_current_aggregates_preserving_anonymous_history(
            old, new, ['season_id', 'team_id', 'player_id']
        )
        combined.to_csv(processed / f'all_seasons_{kind}.csv', index=False)
        aggregate_parts[kind] = combined
    players = normalize_players(aggregate_parts)
    old_players = pd.read_csv(processed / 'players.csv')
    # Keep historical-only identities absent from provider aggregate source.
    players = pd.concat([old_players[~old_players['player_id'].isin(players['player_id'])], players], ignore_index=True)
    current_players = players['player_id'].isin(appearances['player_id'])
    players.loc[current_players, 'teams_played_for'] = players.loc[current_players, 'teams_played_for'].str.rstrip()
    players.to_csv(processed / 'players.csv', index=False)

    from scripts import build_club_app_facing_scorecards as scorecards
    scorecard_outputs = {
        'all_seasons_matches.csv': scorecards.build_match_rows(frames['matches'], frames['innings'], teams),
        'all_seasons_scorecard_batting.csv': scorecards.build_batting_rows(preserve_compact_dismissal_type(frames['batting']), frames['matches'], team_ids, CLUB),
        'all_seasons_scorecard_bowling.csv': scorecards.build_bowling_rows(frames['bowling'], frames['matches'], team_ids, CLUB),
        'all_seasons_scorecard_fielding.csv': scorecards.build_fielding_rows(frames['fielding'], frames['matches'], team_ids, CLUB),
    }
    for filename, new in scorecard_outputs.items():
        old = pd.read_csv(processed / filename, low_memory=False)
        if filename == 'all_seasons_matches.csv':
            new = annotate_grade_metadata(new, 'competition')
        if set(old['match_id']) & set(new['match_id']):
            raise ValueError('Scorecard match overlap')
        pd.concat([old, new], ignore_index=True, sort=False).to_csv(processed / filename, index=False)

    from scripts import build_player_profile_insight_exports as profile
    from scripts import build_season_overview_detail_exports as seasons
    from scripts import build_hall_of_fame_detail_exports as hof
    from src.ui import layout
    batting = profile.prepare_batting(frames, club_id=CLUB)
    bowling = profile.prepare_bowling(frames, club_id=CLUB)
    profile_fielding_frames = {**frames, 'fielding': profile_fielding_input(frames['fielding'])}
    fielding = profile.prepare_fielding(profile_fielding_frames, club_id=CLUB)
    balls = profile.prepare_ball_rows(frames, club_id=CLUB)
    bowling_frames = frames.copy()
    bowling_frames['balls'], bowling_evidence = reconciled_delivery_innings(frames['innings'], frames['balls'])
    bowling_balls = profile.prepare_ball_rows(bowling_frames, club_id=CLUB)
    from src.data.gwhcc_masked_privacy import (
        mask_hawks_participant_rows,
        mask_scorecard_record_links,
        sanitize_hawks_processed_tree,
    )

    # Keep source-detail rows for unlinked scorecard records, but do not
    # attribute reused masked IDs to a named profile or delivery-derived rate.
    link_batting, _ = mask_hawks_participant_rows(
        batting,
        id_columns=["participant_id", "player_id", "raw_player_id", "canonical_player_id"],
    )
    link_bowling, _ = mask_hawks_participant_rows(
        bowling,
        id_columns=["participant_id", "player_id", "raw_player_id", "canonical_player_id"],
    )
    balls, _ = mask_hawks_participant_rows(
        balls,
        id_columns=["striker_participant_id", "bowler_participant_id"],
        name_columns=[],
    )
    bowling_balls, _ = mask_hawks_participant_rows(
        bowling_balls,
        id_columns=["striker_participant_id", "bowler_participant_id"],
        name_columns=[],
    )
    bowling_evidence.to_csv(bundle/'current_bowling_delivery_evidence.csv', index=False)
    batting, bowling, fielding = [filter_public_player_rows(frame) for frame in [batting,bowling,fielding]]
    sums = ['innings','runs','outs','thirties','fifties','hundreds','ducks','fours','sixes',
            'bbb_runs','bbb_balls_faced','bbb_dismissals','bbb_batting_innings','bbb_matches',
            'matches','balls_bowled','runs_against','wickets','three_wicket_innings','five_wicket_innings','wides','no_balls',
            'catches','stumpings','run_outs','dismissals']
    rates = {'bat_avg':('runs','outs',1),'strike_rate':('bbb_runs','bbb_balls_faced',100),
             'bowl_avg':('runs_against','wickets',1),'bowl_sr':('balls_bowled','wickets',1),'eco':('runs_against','balls_bowled',6)}
    merged_paths = []
    def summary(relative, new, keys, count_columns, rate_columns=None, best=None):
        path = processed / relative
        old = pd.read_csv(path, dtype=str)
        new = filter_public_player_rows(new)
        # Established exports distinguish placeholder IDs by their source names.
        keys = list(dict.fromkeys([*keys, 'canonical_player_name', 'display_player_name']))
        result = merge_summary(old, new, keys=keys, sums=count_columns, rates=rate_columns, best=best)
        result.to_csv(path, index=False)
        merged_paths.append(relative)
        return result
    new_perf = profile.build_performance_breakdown(
        batting, bowling, fielding, balls,
        include_source_as_recorded=True,
    )
    perf = summary('player_profile/performance_breakdown_by_dimension.csv', new_perf,
                   ['canonical_player_id','dimension','discipline','breakdown_label'], sums, rates,
                   {'high_score':profile.best_high_score_from_labels,'bbi':profile.best_bbi_from_labels})
    perf_keys = ['canonical_player_id','dimension','discipline','breakdown_label','canonical_player_name','display_player_name']
    updated_perf_keys = set(map(tuple,new_perf[perf_keys].to_numpy()))
    for index, row in perf.iterrows():
        if tuple(row[key] for key in perf_keys) not in updated_perf_keys:
            continue
        if row['discipline'] == 'Batting' and pd.notna(row.get('high_score')):
            text = str(row['high_score'])
            perf.loc[index,'high_score_sort'] = layout.parse_high_score_value(text)[0]
            perf.loc[index,'high_score_not_out_sort'] = int('*' in text)
        if row['discipline'] == 'Bowling':
            perf.loc[index,'extras_pct'] = layout.calculate_extras_pct(row['no_balls'], row['wides'], row['balls_bowled'])
    perf.to_csv(processed / 'player_profile/performance_breakdown_by_dimension.csv',index=False)
    summary('player_profile/batting_position_summary.csv', profile.build_batting_position_summary(batting),
            ['canonical_player_id','position_group'], ['innings','runs','outs'], {'average':('runs','outs',1)})
    phase = summary('player_profile/bowling_phase_summary.csv', profile.build_bowling_phase_summary(bowling,bowling_balls),
                    ['canonical_player_id','phase_model','phase'], ['legal_balls','wickets','runs_conceded','dot_balls','boundary_balls','match_count'],
                    {'avg':('runs_conceded','wickets',1),'eco':('runs_conceded','legal_balls',6),'sr':('legal_balls','wickets',1),
                     'dot_ball_pct':('dot_balls','legal_balls',100),'boundary_rate':('boundary_balls','legal_balls',100)})
    phase['overs'] = phase['legal_balls'].map(layout.format_balls_as_overs)
    phase.to_csv(processed / 'player_profile/bowling_phase_summary.csv',index=False)
    new_dismissals = profile.build_dismissal_fingerprint_summary(batting)
    dismissals = summary('player_profile/dismissal_fingerprint_summary.csv', new_dismissals,
                         ['canonical_player_id','scope','dismissal_bucket'], ['count'])
    numeric_counts = pd.to_numeric(dismissals['count'], errors='raise')
    totals = numeric_counts.groupby([dismissals['scope'], dismissals['canonical_player_id']]).transform('sum')
    affected = dismissals['canonical_player_id'].isin(new_dismissals['canonical_player_id'])
    dismissals.loc[affected, 'total_dismissals'] = totals[affected]
    dismissals.loc[affected, 'pct'] = numeric_counts[affected]*100/totals[affected]
    dismissals.to_csv(processed / 'player_profile/dismissal_fingerprint_summary.csv',index=False)
    for kind, new in [('batting',profile.build_recent_form_batting(batting)),('bowling',profile.build_recent_form_bowling(bowling))]:
        path = processed / f'player_profile/recent_form_{kind}.csv'
        old = pd.read_csv(path)
        if set(old['match_id']) & set(new['match_id']):
            raise ValueError('Recent form overlap')
        pd.concat([old,new],ignore_index=True).sort_values(['canonical_player_name','match_date','order_sort'],ascending=[True,False,True]).to_csv(path,index=False)
    season_outputs = {
        'scorecard_batting_milestones_by_scope.csv': seasons.build_scorecard_batting(frames, club_id=CLUB),
        'scorecard_bowling_milestones_by_scope.csv': seasons.build_scorecard_bowling(frames, club_id=CLUB),
        'bbb_batting_rates_by_scope.csv': seasons.build_bbb_batting(
            frames, club_id=CLUB, include_source_as_recorded=True
        ),
        'bbb_bowling_dot_rates_by_scope.csv': seasons.build_bbb_bowling(bowling_frames, club_id=CLUB),
        'season_by_round_scorecards.csv': seasons.build_season_by_round(frames, club_id=CLUB),
    }
    for filename, new in season_outputs.items():
        path = processed / 'season_overview' / filename
        old = pd.read_csv(path, dtype=str)
        if old['season'].eq(season['name']).any():
            raise ValueError('Detailed season overlap')
        pd.concat([old,filter_public_player_rows(new)],ignore_index=True,sort=False).to_csv(path,index=False)
    summary('hall_of_fame/player_bbb_batting_rates.csv', hof.build_player_bbb_batting_rates(
                batting, balls, include_source_as_recorded=True
            ),
            ['canonical_player_id'], ['bbb_runs','bbb_balls_faced','bbb_dismissals','bbb_batting_innings','bbb_matches'],
            {'bat_sr':('bbb_runs','bbb_balls_faced',100)})
    milestones = summary('hall_of_fame/player_scorecard_milestones.csv', hof.build_player_scorecard_milestones(batting),
                         ['canonical_player_id'], ['thirties','fifties','hundreds','ducks'], best={'hs':profile.best_high_score_from_labels})
    milestones['hs_sort'] = milestones['hs'].map(lambda value: layout.parse_high_score_value(str(value))[0])
    milestones.to_csv(processed / 'hall_of_fame/player_scorecard_milestones.csv', index=False)
    bowler_milestones = summary('hall_of_fame/player_bowling_milestones.csv', hof.build_player_bowling_milestones(bowling),
                               ['canonical_player_id'], ['three_wicket_innings','five_wicket_innings','ten_wicket_matches'],
                               best={'bbi':profile.best_bbi_from_labels})
    bowler_milestones['bbi_wickets_sort'] = bowler_milestones['bbi'].map(lambda v:hof.parse_bbi(v)[0])
    bowler_milestones['bbi_runs_sort'] = bowler_milestones['bbi'].map(lambda v:hof.parse_bbi(v)[1])
    bowler_milestones.to_csv(processed / 'hall_of_fame/player_bowling_milestones.csv',index=False)
    outcomes = hof.club_result_outcomes(frames['matches'],club_id=CLUB)
    appearances = apply_player_identity_mapping(appearances,club_id=CLUB)
    appearances = filter_public_player_rows(appearances)
    appearances['win'] = appearances['match_id'].map(outcomes)
    appearances = appearances[appearances['win'].notna()].copy()
    appearances['wins'] = appearances['win'].astype(bool)*appearances['weight']
    win = appearances.groupby(['canonical_player_id','canonical_player_name'],as_index=False).agg(matches_with_result=('weight','sum'),wins=('wins','sum'),raw_wins=('win','sum'))
    win['losses'] = win['matches_with_result']-win['wins']
    win['player_key'] = win['canonical_player_id'];win['display_player_name'] = win['canonical_player_name']
    win['player_name_key'] = win['display_player_name'].map(layout.player_name_match_key)
    win['source_coverage_note'] = 'Hawks weighted match/win policy: T20=0.5, played non-T20=1, no-play=0.'
    summary('hall_of_fame/player_win_rates.csv',win,['canonical_player_id'],['matches_with_result','wins','losses','raw_wins'],{'win_pct':('wins','matches_with_result',100)})
    path = processed / 'hall_of_fame/scorecard_record_links.csv'
    old = pd.read_csv(path,dtype=str)
    new_links = hof.build_scorecard_record_links(link_batting, link_bowling)
    new_links, _ = mask_scorecard_record_links(new_links, set())
    pd.concat([old,new_links],ignore_index=True).to_csv(path,index=False)

    from src.data.match_centre_milestones import build_batting_milestones
    fastest = build_batting_milestones(bundle, players_path=processed/'players.csv',aliases_path=aliases_path,
                                      scope_names=['parsed_current'],club_team_ids=team_ids,club_name_token='Glen Waverley Hawks')
    path = processed / 'hall_of_fame/fastest_batting_milestones.csv'
    old = pd.read_csv(path,dtype=str)
    new_fastest = filter_public_player_rows(fastest.milestones)
    pd.concat([old,new_fastest],ignore_index=True,sort=False).to_csv(path,index=False)
    fastest.validation.to_csv(bundle/'current_fastest_validation.csv',index=False)

    from scripts import build_gwhcc_partnerships as partnerships
    from scripts import build_gwhcc_hat_tricks as hats
    from src.data.partnerships import prepare_ball_by_ball_partnerships, combine_partnership_events, build_partnership_record_holders
    from src.data.hat_tricks import detect_hat_tricks, public_hat_trick_events
    from src.data.gwhcc_governance import display_grade_name
    calculated = prepare_ball_by_ball_partnerships(frames['partnerships'],matches=frames['matches'],innings=frames['innings'],
                    selected_team_ids_by_match=selected,identity_lookup=partnerships.build_identity_lookup(frames['batting'],selected),grade_display=display_grade_name)
    old_events = pd.read_csv(processed/'partnerships/partnership_events.csv',dtype=str)
    events = combine_partnership_events(old_events,calculated.events)
    pd.concat([old_events, calculated.events], ignore_index=True, sort=False).to_csv(processed/'partnerships/partnership_events.csv',index=False)
    records_path = processed/'hall_of_fame/partnership_records.csv'
    records = build_partnership_record_holders(events)
    try:
        pd.testing.assert_frame_equal(pd.read_csv(records_path), records, check_dtype=False)
    except AssertionError:
        records.to_csv(records_path,index=False)
    coverage_path = processed/'validation/gwhcc_partnership_coverage_audit.csv'
    pd.concat([pd.read_csv(coverage_path),partnerships.coverage_rows(calculated.audit)],ignore_index=True).to_csv(coverage_path,index=False)
    calculated.audit.to_csv(bundle/'current_partnership_audit.csv',index=False)
    detected = detect_hat_tricks(frames['balls'],matches=frames['matches'],bowling_scorecard=frames['bowling'],batting_scorecard=frames['batting'],
                                selected_team_ids_by_match=selected,identity_lookup=hats.build_identity_lookup(frames['bowling'],selected))
    path = processed/'hall_of_fame/hat_tricks.csv'
    old = pd.read_csv(path)
    new_hat = public_hat_trick_events(detected.events)
    if not new_hat.empty:
        append_disjoint(old,new_hat,['event_id']).to_csv(path,index=False)
    detected.audit.to_csv(bundle/'current_hat_trick_audit.csv',index=False)
    # Reapply the club-only redaction to every public processed CSV after all
    # deploy-safe summaries and validation artifacts have been written.
    sanitize_hawks_processed_tree(processed)
    update_metadata(bundle, candidate, cutoff)
    return {'included_matches':len(included),'selected_appearances':len(participation),'captain_matches':len(captains),
            'new_fastest_rows':len(new_fastest),'new_hat_tricks':len(new_hat),'new_partnership_events':len(calculated.events),
            'profile_batting_innings':len(batting),'profile_bowling_rows':len(bowling),'candidate':str(candidate)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-bundle',type=Path,required=True)
    parser.add_argument('--candidate-root',type=Path,required=True)
    parser.add_argument('--cutoff',required=True)
    parser.add_argument('--baseline-root',type=Path,default=ROOT)
    args = parser.parse_args()
    result = build(args.source_bundle,args.candidate_root,args.cutoff,args.baseline_root)
    print(json.dumps(result,indent=2))
