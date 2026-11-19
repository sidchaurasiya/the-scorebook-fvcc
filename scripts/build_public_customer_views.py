"""Compile HOF and milestone projections using the same public renderers as live fallback."""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class Sections:
    """Small, closed vocabulary of public content. Unexpected widgets fail the build."""
    def __init__(self, page):
        self.query_params = {"page": page}
        self.session_state = {}
        self.nodes = []

    @contextmanager
    def scope(self, children):
        parent = self.nodes
        self.nodes = children
        try:
            yield
        finally:
            self.nodes = parent

    def markdown(self, body, **kwargs):
        self.nodes.append({"kind": "markdown", "body": body, "kwargs": kwargs})

    def caption(self, body, **kwargs):
        self.nodes.append({"kind": "caption", "body": body, "kwargs": kwargs})

    def columns(self, spec, **kwargs):
        children = [[] for _ in range(spec if isinstance(spec, int) else len(spec))]
        self.nodes.append({"kind": "columns", "spec": spec, "kwargs": kwargs, "children": children})
        return [self.scope(child) for child in children]

    def container(self, **kwargs):
        children = []
        self.nodes.append({"kind": "container", "kwargs": kwargs, "children": children})
        return self.scope(children)

    def widget(self, kind, value):
        self.nodes.append({"kind": kind, "value": value})


def event_token(event, params):
    payload = json.dumps([event, params], ensure_ascii=True, sort_keys=True).encode()
    return "__SCOREBOOK_EVENT_" + base64.urlsafe_b64encode(payload).decode() + "__"


def pack_table(markup):
    """Factor repeated public cells for transport. Expansion is byte-for-byte lossless."""
    head, body = markup.split("<tbody>", 1)
    body, tail = body.split("</tbody>", 1)
    rows = [re.findall(r"<td\b[^>]*>[\s\S]*?</td>", row)
            for row in re.findall(r"<tr>(.*?)</tr>", body, flags=re.S)]
    if not rows or "".join("<tr>" + "".join(row) + "</tr>" for row in rows) != body:
        return markup
    columns = []
    for cells in zip(*rows, strict=True):
        prefix = os.path.commonprefix(cells)
        middle = [v[len(prefix):] for v in cells]
        suffix = os.path.commonprefix([v[::-1] for v in middle])[::-1]
        values = [v[:-len(suffix)] if suffix else v for v in middle]
        unique = list(dict.fromkeys(values))
        positions = {v:i for i,v in enumerate(unique)}
        indices = [positions[v] for v in values]
        if len(json.dumps([unique,indices])) < len(json.dumps(values)):
            columns.append([prefix,suffix,unique,indices])
        else:
            columns.append([prefix,suffix,values,None])
    data = [head+"<tbody>",columns,len(rows),"</tbody>"+tail]
    payload = json.dumps(data,ensure_ascii=False,separators=(",",":")).replace("<",r"\u003c")
    wire = ('<script type="application/json" id="scorebook-table-data">'+payload+'</script>'
            + """<script>(() => {
                const [head, columns, n, tail] = JSON.parse(document.getElementById("scorebook-table-data").textContent);
                function rows(start, end) {
                    const body = [];
                    for (let i = start; i < end; i++) {
                        body.push("<tr>");
                        for (const [a, b, v, index] of columns) body.push(a, v[index ? index[i] : i], b);
                        body.push("</tr>");
                    }
                    return body.join("");
                }
                const first = Math.min(n, 36);
                const shell = first < n ? head.replace("<tbody>", "<tbody data-scorebook-rows-pending>") : head;
                document.write(shell + rows(0, first) + tail);
                if (first === n) return;
                document.addEventListener("DOMContentLoaded", () => {
                    const tbody = document.querySelector("tbody[data-scorebook-rows-pending]");
                    if (!tbody) return;
                    const table = tbody.closest("table");
                    const append = () => {
                        tbody.insertAdjacentHTML("beforeend", rows(first, n));
                        table.dispatchEvent(new CustomEvent("scorebook-rows-appended", {detail: {start: first, end: n}}));
                        delete tbody.dataset.scorebookRowsPending;
                        table.dispatchEvent(new Event("scorebook-rows-ready"));
                    };
                    if (document.hidden) setTimeout(append, 0);
                    else requestAnimationFrame(() => setTimeout(append, 0));
                }, {once: true});
            })();</script>""")
    return wire if len(wire.encode()) < len(markup.encode()) else markup


def compile_season_views(layout, club, emit):
    """Prepare the active season and comparable season from the governed renderer."""
    import math

    version = layout.metadata_mtime()
    seasons = layout.merge_gwhcc_historical_seasons(layout.load_local_playcricket_seasons(club, version), club)
    latest = layout.latest_season_with_activity(club, version)
    current = next((season for season in seasons if str(season.get("name", "")).casefold() == latest.casefold()), None)

    def json_safe(value):
        if isinstance(value, dict):
            return {key: json_safe(v) for key, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [json_safe(v) for v in value]
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value

    navigation = {"seasons": seasons, "latest": latest, "teams": {}}
    previous = layout.previous_season_for(current) if current is not None else None
    sources = layout.load_season_overview_detail_sources(club, layout.season_overview_detail_source_signature())
    for season in (current, previous):
        if season is None or layout.gwhcc_historical_season_record(season, club):
            continue
        teams = layout.load_local_playcricket_teams(club, season["id"], version)
        teams = layout.prepare_season_team_options(season, teams, version)
        if not teams:
            continue
        navigation["teams"][str(season["id"])] = teams
        all_teams = {"id": "__all_teams__", "name": "All teams",
                     "grade": {"id": "__all_grades__", "name": "Whole club"}}
        for team in (all_teams, *teams):
            is_all = team is all_teams
            scoped_teams = teams if is_all else [team]
            frames = layout.prepared_season_frames(club, version, season, team, scoped_teams, is_all)
            dashboard = {"season": season, "team": team, "teams": scoped_teams, "is_all_teams": is_all, **frames}
            key = layout.season_archive_key(season["id"], team["id"])
            sections = Sections("season-overview")
            with patch.object(layout, "st", sections):
                rows = layout.build_season_round_rows(dashboard, sources["season_by_round"])
                round_html = layout.season_round_cards_html(rows) if rows else ""
                layout.render_overall_section(dashboard)
                layout.render_team_specific_leaders(dashboard)
                emit(key + "/sections", {"round": round_html, "leaders": sections.nodes})
                for category, sort in (("batting", layout.sort_batting_leaders),
                                       ("bowling", layout.sort_bowling_leaders),
                                       ("fielding", layout.sort_fielding_rows)):
                    output = layout.build_full_stats_frame(sort(frames[category]), category, False)
                    emit(f"{key}/{category}", layout.season_overview_detail_table_html(
                        output, category, f"season-detail-{category}-club",
                    ))
        print(f"{club} prepared {season['name']} at {len(teams) + 1} scopes", flush=True)
    emit("season/navigation", json_safe(navigation))


def build(club):
    os.environ["CLUB_ID"] = club
    if os.getenv("FVCC_RUNTIME_IDENTITY_MAINTENANCE") == "1":
        raise ValueError("Use a read-only serving configuration")
    from src.ui import layout
    from src.data.prepared_customer_views import archive_path, content_digest, generation
    import pandas as pd

    initial = generation(club)
    digest = content_digest(initial)
    dest = archive_path(club)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=dest.parent, delete=False) as handle:
        temporary = Path(handle.name)
    try:
        with ZipFile(temporary, "w", compression=ZIP_DEFLATED) as archive:
            def emit(key, value):
                member = ZipInfo(key, date_time=(1980, 1, 1, 0, 0, 0))
                member.compress_type = ZIP_DEFLATED
                archive.writestr(member, json.dumps(value, allow_nan=False, ensure_ascii=False,
                                                    separators=(",", ":")).encode())

            with patch.object(layout, "load_views", return_value=None), patch.object(layout, "ga4_link_onclick", event_token):
                sections = Sections("hall-of-fame")
                with patch.object(layout, "st", sections):
                    data = layout.get_hall_of_fame_data(layout.metadata_mtime(), layout.player_aliases_mtime(),
                        layout.HALL_OF_FAME_DATA_VERSION, layout.hall_of_fame_override_signature(), club_id=club,
                        include_details=False)
                    if len(layout.hall_of_fame_team_group_options(data)) > 1:
                        raise ValueError("A public projection for each team group is required")
                    layout.render_hof_highlights(data, None)
                    emit("hof/sections", sections.nodes)
                    index = layout.load_player_profile_index(club, layout.metadata_mtime(), layout.player_aliases_mtime())
                    emit("public/index", list(index[["id","name"]].astype(str).itertuples(index=False,name=None)))
                    names = layout.canonical_public_player_names(index)
                    assert names == layout.detailed_record_public_player_options()
                    emit("hof/search", names)
                    for category, formatter in (("batting",layout.format_all_time_batting_table),
                                                ("bowling",layout.format_all_time_bowling_table),
                                                ("fielding",layout.format_all_time_fielding_table)):
                        frame = layout.filter_detailed_record_tables_by_selected_player(
                            {category: formatter(data["all_time"])}, None)[category]
                        emit("hof/"+category+"/html",pack_table(layout.hof_sortable_table_html(frame,"hof_"+category+"_detail")))
                        players = {}
                        for label, group in frame.groupby(frame.Player.map(layout.link_display_label).str.casefold(), sort=False):
                            players[label] = json.loads(group.to_json(orient="values",double_precision=15))
                        emit("hof/"+category+"/rows", {"columns":list(frame.columns),"players":players})
                from scripts.prepare_profile_details import compile_details, compile_comparison_inputs, compile_profile_memberships
                compile_details(layout, index, emit)
                compile_profile_memberships(layout, index, emit)
                compile_comparison_inputs(layout, index, data, emit)
                compile_season_views(layout, club, emit)
                for view, category in [("upcoming",""),("achieved","")]+[
                    ("exclusive",key) for key,_ in layout.milestone_club_category_options()]:
                    sections = Sections("milestone")
                    sections.session_state.update(milestone_page_view=view,milestone_club_category=category)
                    with patch.object(layout,"st",sections), patch.object(layout,"_milestone_header"), \
                         patch.object(layout,"render_milestone_view_selector",lambda v:sections.widget("view_selector",v)), \
                         patch.object(layout,"render_milestone_club_selector",lambda v:sections.widget("category_selector",v)):
                        layout.render_approaching_milestones_page()
                    emit("milestone/"+view+("/"+category if category else ""),sections.nodes)
            emit("manifest",{"club":club,"schema":1,"source_digest":digest})
        if initial != generation(club):
            raise RuntimeError("Serving inputs changed during build")
        temporary.replace(dest)
        print(club, dest.name, dest.stat().st_size, digest)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("club", choices=("georges-river-district","glen-waverley-hawks","fvcc"))
    build(parser.parse_args().club)
