"""Build source offsets under the full published identity and privacy context."""
from __future__ import annotations

import csv
import json
from base64 import urlsafe_b64encode
from collections import defaultdict
from functools import lru_cache
from unittest.mock import patch

import pandas as pd


def _offsets(path):
    # csv.reader consumes entire logical records, including embedded newlines.
    ranges = []
    with path.open("rb") as source:
        lines = (line.decode("utf-8-sig") for line in iter(source.readline, b""))
        reader = csv.reader(lines)
        next(reader)
        for_start = source.tell()
        for row in reader:
            end = source.tell()
            if row:
                ranges.append((for_start, end - for_start))
            for_start = end
    return ranges


def compile_details(layout, index, emit):
    club = layout.get_active_club_id()
    profiles = {str(k): {"name": layout.player_name_match_key(n), "rows": {}}
                for k, n in index[["id", "name"]].itertuples(index=False, name=None)}
    schema = {}
    unindexed = set()
    for category, path in layout.profile_detail_paths().items():
        spec = {"types": [], "columns": [], "club_rows": []}
        schema[category] = spec
        if not path.is_file():
            continue
        offsets = _offsets(path)
        by_id = defaultdict(list)
        by_name = defaultdict(list)
        total = 0
        for chunk_id, raw in enumerate(pd.read_csv(path, chunksize=layout.PROFILE_SOURCE_CHUNK_SIZE, low_memory=False)):
            total += len(raw)
            spec["types"].append({k: str(v) for k,v in raw.dtypes.items()})
            rows = raw
            if club == layout.GRDCC_CLUB_ID:
                rows = layout.alias_summary_ids(layout.filter_public_player_rows(raw, club_id=club), club)
            spec["columns"] = list(rows.columns)
            for cols, dest, normalize in [
                (["canonical_player_id", "player_key", "player_id"], by_id, lambda x: str(x).strip()),
                (["canonical_player_name","display_player_name","player_name","raw_player_name"], by_name, layout.player_name_match_key),
            ]:
                cols = [col for col in cols if col in rows]
                if not cols:
                    continue
                groups = defaultdict(list)
                for row in rows[cols].itertuples(index=True, name=None):
                    for value in {normalize(x) for x in row[1:]}:
                        if value:
                            groups[value].append(offsets[row[0]])
                for value, ranges in groups.items():
                    dest[value].append((chunk_id,ranges))
            if category == "dismissal_fingerprint":
                if "scope" in rows:
                    mask = rows["scope"].astype(str).str.casefold().eq("club")
                elif "canonical_player_id" in rows:
                    mask = rows["canonical_player_id"].astype(str).str.strip().eq("__club__")
                else:
                    continue
                if mask.any():
                    spec["club_rows"].append((chunk_id,[offsets[i] for i in rows.index[mask]]))
        if total != len(offsets):
            raise ValueError(f"CSV record boundaries disagree for {category}")
        for key, profile in profiles.items():
            if key not in by_id and by_name.get(profile["name"]):
                # Keep name-only resolution on the original governed reader.
                # A public index must not crystallize a shared-name attribution.
                unindexed.add(key)
            profile["rows"][category] = by_id.get(key, [])
    emit("detail-schema", schema)
    for key, profile in profiles.items():
        if key in unindexed:
            continue
        emit("detail/"+urlsafe_b64encode(key.encode()).decode(),profile)


def compile_comparison_inputs(layout, index, historical, emit):
    public = set(index.id.astype(str))
    club = layout.get_active_club_id()
    peers = layout.load_player_peer_sources(layout.metadata_mtime(), layout.player_aliases_mtime(), club)
    # Never export a source identity absent from the governed public selector.
    coverage = {}
    for key, frame in zip(("batting","bowling"), peers, strict=True):
        selected = frame.canonical_player_id.astype(str).isin(public)
        scoped = layout.apply_team_grade_display_columns(frame.copy())
        frame = frame.copy()
        frame["_peer_scope_key"] = scoped.apply(lambda row: layout.peer_scope_key(row.get("season",""),layout.peer_scope_grade_label(row)),axis=1)
        coverage[key] = {name: json_records(frame.loc[mask,["season","_peer_scope_key"]].drop_duplicates())
                         for name,mask in [("excluded",~selected),("public",selected)]}
        frame = frame.loc[selected]
        emit("peers/"+key, {"columns":list(frame), "data":json_records(frame)})
    emit("peers/coverage", coverage)

    if club == layout.GRDCC_CLUB_ID:
        authority = layout.load_grdcc_profile_authority()
        columns = list(dict.fromkeys(k for k in ("canonical_player_id", *layout.GRDCC_AUTHORITY_METRICS,
                                *layout.GRDCC_AUTHORITY_SCOPE) if k in authority))
        frame = authority.loc[authority.canonical_player_id.astype(str).isin(public),columns]
        full = layout.get_authoritative_career_totals(layout.metadata_mtime(),layout.player_aliases_mtime(),
            layout.HALL_OF_FAME_DATA_VERSION,layout.hall_of_fame_override_signature(),club_id=club)
        full = full.loc[full.canonical_player_id.astype(str).isin(public),columns]
        try:
            pd.testing.assert_frame_equal(frame.reset_index(drop=True), full.reset_index(drop=True),check_dtype=False)
            authority_source = "validated narrow all-time reader"
        except AssertionError:
            frame = full
            authority_source = "full governed reader"
        emit("career/authority-source",authority_source)
        records = {str(k):json.loads(v.to_json(orient="records",double_precision=15))
                   for k,v in frame.groupby("canonical_player_id",sort=False,observed=True)}
        emit("career/authority",records)

    if club == "glen-waverley-hawks":
        authority = layout.get_authoritative_career_totals(
            layout.metadata_mtime(), layout.player_aliases_mtime(), layout.HALL_OF_FAME_DATA_VERSION,
            layout.hall_of_fame_override_signature(club), club_id=club,
        )
        authority = authority.loc[authority.canonical_player_id.astype(str).isin(public),
                                  ["canonical_player_id", "Runs", "Wickets", "Matches", "Catches"]]
        emit("career/authority", {
            str(key): json.loads(group.to_json(orient="records", double_precision=15))
            for key, group in authority.groupby("canonical_player_id", sort=False)
        })

    emit("badges/activity", layout.latest_profile_activity_seasons(club, layout.metadata_mtime()))
    wins, players = layout.load_premiership_records(club, layout.premiership_records_signature())
    names = set()
    for frame, column in ((wins, "captain_name"), (players, "display_player_name" if "display_player_name" in players else "canonical_player_name")):
        if column in frame:
            names.update(frame[column].dropna().map(layout.player_name_match_key))
    from src.data.gwhcc_identity import canonical_query_name
    badges = {}
    with patch.object(layout,"load_premiership_records",return_value=(wins,players)):
        for name in index.name:
            name_key = layout.player_name_match_key(canonical_query_name(name))
            if name_key in names:
                badges[name_key] = layout.player_premiership_profile_badges(pd.Series({"Player":name}))
    emit("badges/premiership", badges)

    leaders = {}
    for frame, metric, prefix in [(historical["batting_raw"],"battingAggregate","run"),
                                  (historical["bowling_raw"],"bowlingWickets","wicket")]:
        for by_grade in (False, True):
            groups = layout.profile_scope_leaders(frame, metric, by_grade)
            key = ("grade_" if by_grade else "club_") + prefix + "_leader"
            for player_id, rows in groups.groupby("canonical_player_id",sort=False,observed=True):
                player_id = str(player_id)
                if player_id in public:
                    leaders.setdefault(player_id,{})[key] = layout.profile_leader_labels(rows, by_grade)
    emit("highlights/leaders",leaders)

    fields = ["canonical_player_id","season","first_match_day","match_id",
              "runs_scored","balls_faced","runs_conceded","wickets_taken"]
    for mode, frame in layout.load_scorecard_record_rows(layout.scorecard_record_rows_signature()).items():
        columns = [k for k in fields if k in frame]
        selected = frame.loc[frame.canonical_player_id.astype(str).isin(public), columns] if "canonical_player_id" in frame else frame.head(0)
        players = {str(k):json_records(group) for k,group in selected.groupby("canonical_player_id", sort=False,observed=True)} if len(selected) else {}
        emit("highlights/"+mode, {"columns":columns,"players":players})


def json_records(frame):
    import json
    return json.loads(frame.to_json(orient="values",double_precision=15))


def compile_profile_memberships(layout, index, emit):
    from src.config.club_config import get_processed_dir, get_processed_path
    from src.data.playcricket_ingestion import _read_processed_table
    from src.data.profile_detail_index import profile_checksum
    from src.utils.player_identity import apply_player_identity_mapping, prepare_grdcc_profile_sources

    club = layout.get_active_club_id()
    if club not in {layout.GRDCC_CLUB_ID, "glen-waverley-hawks", "fvcc"}:
        return
    if club == "fvcc" and any(
        get_processed_path(f"all_seasons_{category}.csv", club_id=club).parent != get_processed_dir(club_id=club)
        for category in ("batting", "bowling", "fielding")
    ):
        return  # Legacy root fallbacks use the governed full reader.
    sources = {}
    offsets = {}
    frames = {}

    def annotated(path, version):
        from pathlib import Path
        p = Path(path)
        raw = pd.read_csv(p)
        offsets[p.name] = _offsets(p)
        if len(offsets[p.name]) != len(raw):
            raise ValueError("Source row boundary mismatch")
        dtypes = {column: str(dtype) for column, dtype in raw.dtypes.items()}
        if club == "fvcc":
            # The full CSV reader can return booleans in an object column
            # when some values are unavailable. Keep that type in row slices.
            for column, dtype in dtypes.items():
                if dtype == "object" and pd.api.types.infer_dtype(raw[column], skipna=True) == "boolean":
                    dtypes[column] = "boolean"
        sources[p.name] = {"columns":list(raw), "dtypes":dtypes}
        return raw.assign(_source_file=p.name, _source_position=range(len(raw)))

    for category in ("batting","bowling","fielding"):
        raw = _read_processed_table("all_seasons_"+category, club, annotated)
        frames[category] = apply_player_identity_mapping(raw, club_id=club)
    if club != layout.GRDCC_CLUB_ID:
        indices = {
            category: frame.groupby(frame.canonical_player_id.fillna("").astype(str).str.strip(), sort=False).indices
            for category, frame in frames.items()
        }
        emit("profile-schema", {"sources": sources})
        for key in index.id.astype(str):
            projected, ranges = {}, {}
            for category, frame in frames.items():
                rows = frame.iloc[indices[category].get(key, [])]
                for filename, selected in rows.groupby("_source_file", sort=False):
                    ranges[filename] = [offsets[filename][int(i)] for i in selected["_source_position"]]
                projected[category] = rows.drop(columns=["_source_file", "_source_position"])
            emit("profile/" + urlsafe_b64encode(key.encode()).decode(), {
                "target": key, "ranges": ranges,
                "types": {category: {c: str(t) for c, t in frame.dtypes.items()}
                          for category, frame in projected.items()},
                "source_system": {}, "checksum": profile_checksum(projected),
            })
        return
    pool = prepare_grdcc_profile_sources(frames)
    def with_scope(frame):
        scoped = layout.apply_team_grade_display_columns(frame.copy())
        scoped["_peer_scope_key"] = scoped.apply(
            lambda row: layout.peer_scope_key(row.get("season",""),layout.peer_scope_grade_label(row)), axis=1)
        return scoped

    # The build computes comparisons against the complete governed population.
    # Only the selected public player's display metrics are written to the archive.
    batting, bowling = (with_scope(f) for f in layout.load_player_peer_sources(
        layout.metadata_mtime(), layout.player_aliases_mtime(), club))
    bbb = with_scope(layout.read_match_centre_csv(layout.SEASON_OVERVIEW_BBB_BATTING_RATES_PATH))

    @lru_cache(maxsize=48)
    def cohort(seasons, scope):
        bat = layout.aggregate_peer_batting(layout.filter_peer_scope(batting,seasons,scope),seasons)
        bat = layout.add_bbb_peer_batting_rates(bat,seasons,scope,bbb)
        bowl = layout.aggregate_peer_bowling(layout.filter_peer_scope(bowling,seasons,scope),seasons)
        return bat, bowl

    scoped_keys = {}
    for frame in pool.frames.values():
        if frame.empty:
            continue
        scoped = with_scope(frame)
        for filename, ordinal, season, scope in scoped[["_source_file","_source_position","season","_peer_scope_key"]].itertuples(index=False,name=None):
            scoped_keys[(filename,int(ordinal))] = (str(season),scope)
    emit("profile-schema", {"sources":sources})
    reports = set(layout.report_profile_index(club).id)
    for key in index.id.astype(str):
        if key in reports:
            continue
        profile = pool.profile(key)
        types, ranges, projected, systems = {}, {}, {}, {}
        contexts = set()
        for category in frames:
            rows = profile[category]
            contexts.update(scoped_keys[(f,int(i))] for f,i in rows[["_source_file","_source_position"]].itertuples(index=False,name=None))
            if "source_system" in rows:
                systems[category] = json.loads(rows.source_system.to_json(orient="values"))
            for filename, selected in rows.groupby("_source_file", sort=False):
                ranges[filename] = [offsets[filename][int(i)] for i in selected["_source_position"]]
            projected[category] = rows.drop(columns=["_source_file","_source_position"])
            types[category] = {c:str(t) for c,t in projected[category].dtypes.items()}
        seasons = tuple(sorted({season for season,_ in contexts}, key=layout.profile_season_sort_key))
        scope = tuple(sorted({scope for _,scope in contexts}))
        bat, bowl = cohort(seasons,scope)
        comparison = {"seasons":seasons, "scope":scope,
                      "metrics":layout.peer_metrics_from_rows(key, bat, bowl, scope)}
        emit("profile/" + urlsafe_b64encode(key.encode()).decode(), {
            "target":profile["player_info"]["canonical_player_id"],"ranges":ranges,
            "comparison":comparison,"types":types,"source_system":systems,"checksum":profile_checksum(projected)})
