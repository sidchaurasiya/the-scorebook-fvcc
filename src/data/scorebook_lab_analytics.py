from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from src.data import player_dna_analytics as dna
from src.data.match_centre_ownership import ensure_club_ownership_columns


def load_scorebook_lab_data(app_root: str | Path) -> dict[str, Any]:
    """Load the local-only data needed for the hidden Scorebook Lab.

    This module never fetches external data. It reads the same processed
    match-centre and deploy-safe milestone outputs used elsewhere in the app.
    """
    data = dna.load_player_dna_data(app_root)
    match_centre = data.get("match_centre", {})
    batting = fvcc_rows(match_centre.get("batting", pd.DataFrame()))
    bowling = fvcc_rows(match_centre.get("bowling", pd.DataFrame()))
    fielding = fvcc_rows(match_centre.get("fielding", pd.DataFrame()))
    return {
        **data,
        "lab": {
            "matches": match_centre.get("matches", pd.DataFrame()).copy(),
            "innings": match_centre.get("innings", pd.DataFrame()).copy(),
            "batting": batting,
            "bowling": bowling,
            "fielding": fielding,
            "ball_by_ball": match_centre.get("ball_by_ball", pd.DataFrame()).copy(),
            "partnerships": match_centre.get("partnerships", pd.DataFrame()).copy(),
        },
    }


def calculate_carry_jobs(batting: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    if batting.empty:
        return []
    rows = batting.copy()
    rows["runs_scored"] = num(rows.get("runs_scored"))
    rows["team_total"] = num(rows.get("team_total"))
    rows["contribution_pct"] = rows.apply(lambda row: safe_div(row["runs_scored"] * 100, row["team_total"]) or 0, axis=1)
    rows["next_highest"] = rows.apply(lambda row: next_highest_score(rows, row), axis=1)
    rows["carry_gap"] = rows["runs_scored"] - rows["next_highest"]
    rows = rows[rows["runs_scored"] > 0].sort_values(["contribution_pct", "runs_scored"], ascending=[False, False]).head(limit)
    return [
        record(
            row,
            title=player_name(row),
            value=pct(row.get("contribution_pct")),
            subtitle=f"Final score: {int(row['runs_scored'])} out of {int(row['team_total']) if row['team_total'] else 'N/A'}",
            detail=f"Next highest: {int(row['next_highest'])}" if row["next_highest"] > 0 else "No teammate score context",
            badge=f"+{int(row['carry_gap'])} carry gap" if row["carry_gap"] > 0 else "Team share",
        )
        for _, row in rows.iterrows()
    ]


def calculate_team_run_contribution_records(batting: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    if batting.empty:
        return []
    rows = batting.copy()
    rows["runs_scored"] = num(rows.get("runs_scored"))
    rows["contribution_pct"] = num(rows.get("contribution_pct"))
    rows = rows[rows["runs_scored"] > 0].sort_values(["contribution_pct", "runs_scored"], ascending=[False, False]).head(limit)
    return [
        record(
            row,
            title=player_name(row),
            value=pct(row.get("contribution_pct")),
            subtitle=f"{int(row['runs_scored'])} runs from {safe_text(row.get('team_total'), 'team total')}",
            detail=context(row),
            badge="Team-run share",
        )
        for _, row in rows.iterrows()
    ]


def calculate_wicket_share_dominance(bowling: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    if bowling.empty:
        return []
    rows = bowling.copy()
    rows["wickets_taken"] = num(rows.get("wickets_taken"))
    rows["runs_conceded"] = num(rows.get("runs_conceded"))
    rows["wicket_share_pct"] = num(rows.get("wicket_share_pct"))
    rows["economy"] = num(rows.get("economy"))
    rows = rows[rows["wickets_taken"] > 0].sort_values(
        ["wicket_share_pct", "wickets_taken", "economy"],
        ascending=[False, False, True],
    ).head(limit)
    return [
        record(
            row,
            title=player_name(row),
            value=pct(row.get("wicket_share_pct")),
            subtitle=f"{int(row['wickets_taken'])}/{int(row['runs_conceded'])} | {int(row['wickets_taken'])} of {int(row['opposition_wickets']) if row.get('opposition_wickets') else 'N/A'} wickets",
            detail=context(row),
            badge=wicket_dots(row.get("wickets_taken"), row.get("opposition_wickets")),
        )
        for _, row in rows.iterrows()
    ]


def calculate_all_round_match_impact(
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
    limit: int = 8,
) -> list[dict[str, Any]]:
    frames = []
    if not batting.empty:
        bat = batting.copy()
        bat["bat_points"] = num(bat.get("runs_scored")) * 0.35 + num(bat.get("contribution_pct")) * 1.15
        bat = bat.groupby(["match_id", "player_key", "player_display_name"], as_index=False).agg(
            bat_points=("bat_points", "sum"),
            runs=("runs_scored", "sum"),
            contribution_pct=("contribution_pct", "max"),
            context=("opponent_name", first_text),
            season=("season", first_text),
            grade_name=("grade_name", first_text),
        )
        frames.append(bat)
    if not bowling.empty:
        bowl = bowling.copy()
        bowl["bowl_points"] = num(bowl.get("wickets_taken")) * 18 + num(bowl.get("wicket_share_pct")) * 0.9
        bowl = bowl.groupby(["match_id", "player_key", "player_display_name"], as_index=False).agg(
            bowl_points=("bowl_points", "sum"),
            wickets=("wickets_taken", "sum"),
            runs_conceded=("runs_conceded", "sum"),
            wicket_share_pct=("wicket_share_pct", "max"),
            context=("opponent_name", first_text),
            season=("season", first_text),
            grade_name=("grade_name", first_text),
        )
        frames.append(bowl)
    if not fielding.empty:
        fld = add_fielding_points(fielding)
        fld = fld.groupby(["match_id", "player_key", "player_display_name"], as_index=False).agg(
            field_points=("field_points", "sum"),
            field_dismissals=("field_dismissals", "sum"),
            context=("opponent_name", first_text),
            season=("season", first_text),
            grade_name=("grade_name", first_text),
        )
        frames.append(fld)
    if not frames:
        return []
    combined = frames[0]
    for frame in frames[1:]:
        combined = combined.merge(frame, on=["match_id", "player_key", "player_display_name"], how="outer", suffixes=("", "_alt"))
    for column in ["bat_points", "bowl_points", "field_points", "runs", "wickets", "runs_conceded", "field_dismissals"]:
        if column not in combined:
            combined[column] = 0
        combined[column] = num(combined[column])
    combined["impact_score"] = combined["bat_points"] + combined["bowl_points"] + combined["field_points"]
    for column in ["context", "season", "grade_name"]:
        matching_columns = [candidate for candidate in combined.columns if candidate == column or str(candidate).startswith(f"{column}_")]
        if matching_columns:
            combined[column] = combined[matching_columns].apply(first_row_text, axis=1)
    combined = combined[combined["impact_score"] > 0].sort_values("impact_score", ascending=False).head(limit)
    records = []
    for _, row in combined.iterrows():
        lines = []
        if row.get("runs", 0) > 0:
            lines.append(f"Batting: {int(row['runs'])} runs")
        if row.get("wickets", 0) > 0:
            lines.append(f"Bowling: {int(row['wickets'])}/{int(row.get('runs_conceded', 0))}")
        if row.get("field_dismissals", 0) > 0:
            lines.append(f"Fielding: {int(row['field_dismissals'])} dismissal involvements")
        records.append(
            {
                "title": player_name(row),
                "value": f"{row['impact_score']:.0f}",
                "subtitle": " | ".join(lines) or "Multi-skill contribution",
                "detail": context(row),
                "badge": "Impact score",
            }
        )
    return records


def calculate_fielding_impact(fielding: pd.DataFrame, limit: int = 8) -> list[dict[str, Any]]:
    if fielding.empty:
        return []
    rows = add_fielding_points(fielding)
    rows = rows[rows["field_dismissals"] > 0].sort_values(["field_dismissals", "field_points"], ascending=[False, False]).head(limit)
    return [
        record(
            row,
            title=player_name(row),
            value=f"{int(row['field_dismissals'])}",
            subtitle=fielding_line(row),
            detail=context(row),
            badge="Dismissal involvements",
        )
        for _, row in rows.iterrows()
    ]


def calculate_ground_hunter(
    matches: pd.DataFrame,
    innings: pd.DataFrame,
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
    ground: str,
) -> dict[str, Any]:
    if not ground:
        return empty_profile("ground")
    match_ids = set(matches.loc[clean(matches.get("venue_name")) == ground, "match_id"].astype(str)) if not matches.empty else set()
    bat = batting[clean(batting.get("venue_name")) == ground].copy() if not batting.empty else pd.DataFrame()
    bowl = bowling[clean(bowling.get("venue_name")) == ground].copy() if not bowling.empty else pd.DataFrame()
    fld = fielding[clean(fielding.get("venue_name")) == ground].copy() if not fielding.empty else pd.DataFrame()
    fvcc_scores = fvcc_innings_at(innings, matches, match_ids)
    return {
        "title": ground,
        "subtitle": f"{len(match_ids)} archived matches",
        "average_score": avg_score_label(fvcc_scores),
        "record": result_record(matches[matches["match_id"].astype(str).isin(match_ids)] if not matches.empty else pd.DataFrame()),
        "top_batter": top_batter_card(bat),
        "top_bowler": top_bowler_card(bowl),
        "best_innings": best_innings_card(bat),
        "best_bowling": best_bowling_card(bowl),
        "best_fielding": best_fielding_card(fld),
        "heatmap": dimension_player_list(bat, bowl, "ground"),
        "insight": ground_insight(fvcc_scores, innings, matches),
    }


def calculate_opponent_hunter(
    matches: pd.DataFrame,
    innings: pd.DataFrame,
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
    opponent: str,
) -> dict[str, Any]:
    if not opponent:
        return empty_profile("opponent")
    match_ids = set(matches.loc[clean(matches.get("opponent_name")) == opponent, "match_id"].astype(str)) if not matches.empty else set()
    bat = batting[clean(batting.get("opponent_name")) == opponent].copy() if not batting.empty else pd.DataFrame()
    bowl = bowling[clean(bowling.get("opponent_name")) == opponent].copy() if not bowling.empty else pd.DataFrame()
    fld = fielding[clean(fielding.get("opponent_name")) == opponent].copy() if not fielding.empty else pd.DataFrame()
    fvcc_scores = fvcc_innings_at(innings, matches, match_ids)
    opponent_scores = opponent_innings_at(innings, matches, match_ids)
    dismissals = dismissal_fingerprint(bat)
    return {
        "title": f"FVCC vs {opponent}",
        "subtitle": f"{len(match_ids)} archived matches",
        "average_score": avg_score_label(fvcc_scores),
        "opponent_average_score": avg_score_label(opponent_scores),
        "record": result_record(matches[matches["match_id"].astype(str).isin(match_ids)] if not matches.empty else pd.DataFrame()),
        "top_batter": top_batter_card(bat),
        "top_bowler": top_bowler_card(bowl),
        "best_innings": best_innings_card(bat),
        "best_bowling": best_bowling_card(bowl),
        "best_fielding": best_fielding_card(fld),
        "heatmap": dimension_player_list(bat, bowl, "opponent"),
        "dismissal": dismissals[0] if dismissals else None,
        "insight": "This opponent brings out their best cricket.",
    }


def calculate_position_intelligence(batting: pd.DataFrame, player_key: str = "") -> dict[str, Any]:
    if batting.empty:
        return {"player_positions": pd.DataFrame(), "team_positions": [], "insight": "No batting position data is available yet."}
    rows = batting.copy()
    rows["bat_order"] = num(rows.get("bat_order")).astype("Int64")
    rows = rows[rows["bat_order"].notna()].copy()
    rows["runs_scored"] = num(rows.get("runs_scored"))
    rows["balls_faced"] = num(rows.get("balls_faced"))
    rows["outs"] = dismissal_flags(rows).astype(int)
    if rows.empty:
        return {"player_positions": pd.DataFrame(), "team_positions": [], "insight": "No batting position data is available yet."}
    selected = rows[rows["player_key"].astype(str) == player_key].copy() if player_key else pd.DataFrame()
    player_positions = position_summary(selected) if not selected.empty else pd.DataFrame()
    team_positions = []
    for position, group in rows.groupby("bat_order"):
        summary = group.groupby(["player_key", "player_display_name"], as_index=False).agg(
            innings=("match_id", "count"),
            runs=("runs_scored", "sum"),
            outs=("outs", "sum"),
            contribution_pct=("contribution_pct", "mean"),
        )
        summary["average"] = summary.apply(lambda row: safe_div(row["runs"], row["outs"]), axis=1)
        summary["impact"] = summary["runs"] * 0.25 + summary["contribution_pct"].fillna(0) + summary["innings"] * 2
        best = summary.sort_values(["impact", "runs"], ascending=[False, False]).head(1)
        if not best.empty:
            row = best.iloc[0]
            team_positions.append(
                {
                    "title": f"No. {int(position)}",
                    "value": player_name(row),
                    "subtitle": f"{int(row['runs'])} runs | {fmt_decimal(row['average'])} avg",
                    "detail": f"{fmt_pct(row['contribution_pct'])} average contribution",
                    "badge": f"{int(row['innings'])} innings",
                }
            )
    insight = "His strongest impact comes from the highlighted batting role." if not player_positions.empty else "Select a player with match-centre batting rows to see position fit."
    return {"player_positions": player_positions, "team_positions": team_positions[:8], "insight": insight}


def calculate_dismissal_fingerprint(batting: pd.DataFrame, player_key: str = "") -> list[dict[str, Any]]:
    rows = batting.copy()
    if player_key:
        rows = rows[rows.get("player_key", pd.Series(dtype="object")).astype(str) == player_key].copy()
    return dismissal_fingerprint(rows)


def calculate_hidden_match_mvp(
    match: pd.Series,
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
) -> dict[str, Any]:
    match_id = safe_text(match.get("match_id"))
    bat = batting[batting.get("match_id", pd.Series(dtype="object")).astype(str) == match_id].copy()
    bowl = bowling[bowling.get("match_id", pd.Series(dtype="object")).astype(str) == match_id].copy()
    fld = fielding[fielding.get("match_id", pd.Series(dtype="object")).astype(str) == match_id].copy()
    score = {}
    for _, row in bat.iterrows():
        key = player_name(row)
        score.setdefault(key, {"player": key, "batting": 0, "bowling": 0, "fielding": 0, "lines": []})
        points = n(row.get("runs_scored")) * 0.35 + n(row.get("contribution_pct")) * 1.15
        score[key]["batting"] += points
        if n(row.get("runs_scored")) > 0:
            score[key]["lines"].append(f"{int(n(row.get('runs_scored')))} runs ({fmt_pct(row.get('contribution_pct'))})")
    for _, row in bowl.iterrows():
        key = player_name(row)
        score.setdefault(key, {"player": key, "batting": 0, "bowling": 0, "fielding": 0, "lines": []})
        points = n(row.get("wickets_taken")) * 18 + n(row.get("wicket_share_pct")) * 0.9
        score[key]["bowling"] += points
        if n(row.get("wickets_taken")) > 0:
            score[key]["lines"].append(f"{int(n(row.get('wickets_taken')))}/{int(n(row.get('runs_conceded')))} ({fmt_pct(row.get('wicket_share_pct'))} wicket share)")
    if not fld.empty:
        fld = add_fielding_points(fld)
        for _, row in fld.iterrows():
            key = player_name(row)
            score.setdefault(key, {"player": key, "batting": 0, "bowling": 0, "fielding": 0, "lines": []})
            score[key]["fielding"] += n(row.get("field_points"))
            if n(row.get("field_dismissals")) > 0:
                score[key]["lines"].append(fielding_line(row))
    players = []
    for row in score.values():
        row["total"] = row["batting"] + row["bowling"] + row["fielding"]
        players.append(row)
    players = sorted(players, key=lambda item: item["total"], reverse=True)
    mvp = players[0] if players else {"player": "No MVP available", "total": 0, "batting": 0, "bowling": 0, "fielding": 0, "lines": []}
    return {
        "match_title": match_label(match),
        "result": safe_text(match.get("result_text")),
        "mvp": mvp,
        "top_batting": first_or_none(calculate_team_run_contribution_records(bat, 1)),
        "top_bowling": first_or_none(calculate_wicket_share_dominance(bowl, 1)),
        "top_fielding": first_or_none(calculate_fielding_impact(fld, 1)),
        "players": players[:5],
    }


def calculate_match_story(
    match: pd.Series,
    innings: pd.DataFrame,
    batting: pd.DataFrame,
    bowling: pd.DataFrame,
    fielding: pd.DataFrame,
    partnerships: pd.DataFrame,
) -> list[dict[str, str]]:
    story = []
    match_id = safe_text(match.get("match_id"))
    bat = batting[batting.get("match_id", pd.Series(dtype="object")).astype(str) == match_id].copy()
    bowl = bowling[bowling.get("match_id", pd.Series(dtype="object")).astype(str) == match_id].copy()
    inns = innings[innings.get("match_id", pd.Series(dtype="object")).astype(str) == match_id].copy() if not innings.empty else pd.DataFrame()
    parts = partnerships[partnerships.get("match_id", pd.Series(dtype="object")).astype(str) == match_id].copy() if not partnerships.empty else pd.DataFrame()
    top_bat = first_or_none(calculate_team_run_contribution_records(bat, 1))
    if top_bat:
        story.append({"title": "Batting spine", "text": f"{top_bat['title']} carried the innings with {top_bat['subtitle'].replace('Final score: ', '')}."})
    top_bowl = first_or_none(calculate_wicket_share_dominance(bowl, 1))
    if top_bowl:
        story.append({"title": "Bowling punch", "text": f"{top_bowl['title']} claimed {top_bowl['subtitle']}."})
    if not parts.empty:
        parts["runs"] = num(parts.get("runs"))
        best = parts.sort_values("runs", ascending=False).head(1)
        if not best.empty:
            row = best.iloc[0]
            story.append({"title": "Partnership moment", "text": f"{safe_text(row.get('batter_1_name'))} and {safe_text(row.get('batter_2_name'))} added {int(row['runs'])}."})
    if not inns.empty:
        match = ensure_club_ownership_columns(pd.DataFrame([match])).iloc[0]
        club_team_id = safe_text(match.get("club_team_id") or match.get("fvcc_team_id"))
        fvcc = inns[inns.get("batting_team_id", pd.Series(dtype="object")).astype(str) == club_team_id].copy()
        if not fvcc.empty:
            row = fvcc.iloc[0]
            story.append({"title": "Scorecard frame", "text": f"FVCC made {safe_text(row.get('runs_scored'))}/{safe_text(row.get('wickets_fallen'))} from {safe_text(row.get('overs_bowled'))} overs."})
    if not story:
        story.append({"title": "Story building", "text": "More scorecard detail is needed to build a confident match timeline."})
    return story[:5]


def calculate_partnership_chemistry(partnerships: pd.DataFrame, limit: int = 8) -> dict[str, Any]:
    if partnerships.empty:
        return {"quality": "empty", "pairs": [], "insight": "No partnership rows are available yet."}
    rows = partnerships.copy()
    for column in ["batter_1_name", "batter_2_name"]:
        if column not in rows:
            rows[column] = ""
    rows["batter_1_name"] = clean(rows["batter_1_name"])
    rows["batter_2_name"] = clean(rows["batter_2_name"])
    rows = rows[(rows["batter_1_name"] != "") & (rows["batter_2_name"] != "")]
    if rows.empty:
        return {"quality": "limited", "pairs": [], "insight": "Partnership rows exist, but batter-pair names are incomplete."}
    rows["runs"] = num(rows.get("runs"))
    rows["balls"] = num(rows.get("balls"))
    rows["pair"] = rows.apply(lambda row: " + ".join(sorted([row["batter_1_name"], row["batter_2_name"]])), axis=1)
    grouped = rows.groupby("pair", as_index=False).agg(
        innings=("match_id", "count"),
        runs=("runs", "sum"),
        average=("runs", "mean"),
        balls=("balls", "sum"),
        best=("runs", "max"),
    )
    grouped["rate"] = grouped.apply(lambda row: safe_div(row["runs"] * 100, row["balls"]), axis=1)
    grouped = grouped.sort_values(["runs", "average"], ascending=[False, False]).head(limit)
    pairs = [
        {
            "title": row["pair"],
            "value": f"{int(row['runs'])}",
            "subtitle": f"{int(row['innings'])} partnerships | best {int(row['best'])}",
            "detail": f"{fmt_decimal(row['average'])} average | {fmt_decimal(row['rate'])} runs/100 balls" if row.get("rate") else f"{fmt_decimal(row['average'])} average",
            "badge": "Partnership runs",
        }
        for _, row in grouped.iterrows()
    ]
    return {"quality": "usable", "pairs": pairs, "insight": "These pairs have produced the strongest partnership returns in the current archive."}


def selector_options(frame: pd.DataFrame, column: str) -> list[str]:
    if frame.empty or column not in frame:
        return []
    values = clean(frame[column])
    return sorted([value for value in values.unique().tolist() if value])


def match_options(matches: pd.DataFrame) -> pd.DataFrame:
    if matches.empty:
        return pd.DataFrame(columns=["label", "match_id"])
    rows = matches.copy()
    rows["label"] = rows.apply(match_label, axis=1)
    return rows[["label", "match_id"]].drop_duplicates().sort_values("label")


def position_player_options(batting: pd.DataFrame) -> pd.DataFrame:
    if batting.empty:
        return pd.DataFrame(columns=["label", "player_key"])
    rows = batting[["player_key", "player_display_name"]].drop_duplicates().copy()
    rows = rows[clean(rows["player_display_name"]) != ""]
    rows["label"] = rows["player_display_name"]
    return rows.sort_values("label")


def position_summary(rows: pd.DataFrame) -> pd.DataFrame:
    grouped = rows.groupby("bat_order", as_index=False).agg(
        innings=("match_id", "count"),
        runs=("runs_scored", "sum"),
        outs=("outs", "sum"),
        balls=("balls_faced", "sum"),
        contribution_pct=("contribution_pct", "mean"),
    )
    grouped["average"] = grouped.apply(lambda row: safe_div(row["runs"], row["outs"]), axis=1)
    grouped["strike_rate"] = grouped.apply(lambda row: safe_div(row["runs"] * 100, row["balls"]), axis=1)
    grouped["impact"] = grouped["runs"] * 0.25 + grouped["contribution_pct"].fillna(0) + grouped["innings"] * 2
    return grouped.sort_values("impact", ascending=False)


def dismissal_fingerprint(batting: pd.DataFrame) -> list[dict[str, Any]]:
    if batting.empty:
        return []
    rows = batting[dismissal_flags(batting)].copy()
    if rows.empty:
        return []
    rows["bucket"] = rows.apply(dismissal_bucket, axis=1)
    grouped = rows.groupby("bucket", as_index=False).size().rename(columns={"bucket": "title", "size": "count"})
    grouped["pct"] = grouped["count"] / grouped["count"].sum() * 100
    grouped = grouped.sort_values("pct", ascending=False)
    return [
        {
            "title": row["title"],
            "value": pct(row["pct"]),
            "subtitle": f"{int(row['count'])} dismissals",
            "detail": "Most dismissals are caught, bowled, lbw, run out, stumped, or grouped as other.",
            "badge": "Dismissal share",
            "score": float(row["pct"]),
        }
        for _, row in grouped.iterrows()
    ]


def add_fielding_points(fielding: pd.DataFrame) -> pd.DataFrame:
    rows = fielding.copy()
    for column in ["catches", "run_outs", "stumpings", "assisted_run_outs"]:
        if column not in rows:
            rows[column] = 0
        rows[column] = num(rows[column])
    rows["field_dismissals"] = rows["catches"] + rows["run_outs"] + rows["stumpings"] + rows["assisted_run_outs"]
    rows["field_points"] = rows["catches"] * 8 + rows["run_outs"] * 12 + rows["stumpings"] * 14 + rows["assisted_run_outs"] * 6
    return rows


def fvcc_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    rows = frame.copy()
    mask = dna.get_fvcc_mask(rows)
    return rows[mask].copy() if len(mask) else rows


def fvcc_innings_at(innings: pd.DataFrame, matches: pd.DataFrame, match_ids: set[str]) -> pd.DataFrame:
    if innings.empty or matches.empty or not match_ids:
        return pd.DataFrame()
    matches = ensure_club_ownership_columns(matches)
    match_team = matches.set_index("match_id")["club_team_id"].to_dict() if "club_team_id" in matches else {}
    rows = innings[innings.get("match_id", pd.Series(dtype="object")).astype(str).isin(match_ids)].copy()
    rows = rows[rows.apply(lambda row: safe_text(row.get("batting_team_id")) == safe_text(match_team.get(row.get("match_id"))), axis=1)]
    return rows


def opponent_innings_at(innings: pd.DataFrame, matches: pd.DataFrame, match_ids: set[str]) -> pd.DataFrame:
    if innings.empty or matches.empty or not match_ids:
        return pd.DataFrame()
    matches = ensure_club_ownership_columns(matches)
    match_team = matches.set_index("match_id")["club_team_id"].to_dict() if "club_team_id" in matches else {}
    rows = innings[innings.get("match_id", pd.Series(dtype="object")).astype(str).isin(match_ids)].copy()
    rows = rows[rows.apply(lambda row: safe_text(row.get("batting_team_id")) != safe_text(match_team.get(row.get("match_id"))), axis=1)]
    return rows


def avg_score_label(innings: pd.DataFrame) -> str:
    if innings.empty or "runs_scored" not in innings:
        return "N/A"
    value = num(innings["runs_scored"]).mean()
    return "N/A" if pd.isna(value) else f"{value:.0f}"


def result_record(matches: pd.DataFrame) -> str:
    if matches.empty or "result_text" not in matches:
        return "Result record unavailable"
    text = clean(matches["result_text"])
    wins = text.str.contains("Fiji Victorian", case=False, na=False).sum()
    total = len(matches)
    return f"{wins}-{total - wins} by result text"


def top_batter_card(batting: pd.DataFrame) -> dict[str, Any] | None:
    if batting.empty:
        return None
    grouped = batting.copy()
    grouped["runs_scored"] = num(grouped.get("runs_scored"))
    grouped = grouped.groupby(["player_key", "player_display_name"], as_index=False).agg(
        runs=("runs_scored", "sum"),
        innings=("match_id", "count"),
        contribution=("contribution_pct", "mean"),
    ).sort_values("runs", ascending=False)
    if grouped.empty:
        return None
    row = grouped.iloc[0]
    return {"title": player_name(row), "value": int(row["runs"]), "subtitle": f"{int(row['innings'])} innings", "detail": f"{fmt_pct(row['contribution'])} avg contribution", "badge": "Top batter"}


def top_bowler_card(bowling: pd.DataFrame) -> dict[str, Any] | None:
    if bowling.empty:
        return None
    grouped = bowling.copy()
    grouped["wickets_taken"] = num(grouped.get("wickets_taken"))
    grouped = grouped.groupby(["player_key", "player_display_name"], as_index=False).agg(
        wickets=("wickets_taken", "sum"),
        innings=("match_id", "count"),
        share=("wicket_share_pct", "mean"),
    ).sort_values("wickets", ascending=False)
    if grouped.empty:
        return None
    row = grouped.iloc[0]
    return {"title": player_name(row), "value": int(row["wickets"]), "subtitle": f"{int(row['innings'])} spells", "detail": f"{fmt_pct(row['share'])} avg wicket share", "badge": "Top bowler"}


def best_innings_card(batting: pd.DataFrame) -> dict[str, Any] | None:
    records = calculate_team_run_contribution_records(batting, 1)
    return records[0] if records else None


def best_bowling_card(bowling: pd.DataFrame) -> dict[str, Any] | None:
    records = calculate_wicket_share_dominance(bowling, 1)
    return records[0] if records else None


def best_fielding_card(fielding: pd.DataFrame) -> dict[str, Any] | None:
    records = calculate_fielding_impact(fielding, 1)
    return records[0] if records else None


def dimension_player_list(batting: pd.DataFrame, bowling: pd.DataFrame, _mode: str) -> list[dict[str, Any]]:
    rows = []
    top_bat = calculate_team_run_contribution_records(batting, 4)
    top_bowl = calculate_wicket_share_dominance(bowling, 4)
    rows.extend(top_bat)
    rows.extend(top_bowl)
    return rows[:6]


def ground_insight(scores: pd.DataFrame, all_innings: pd.DataFrame, _matches: pd.DataFrame) -> str:
    if scores.empty or all_innings.empty:
        return "Ground profile will sharpen as more scorecards are refreshed."
    ground_avg = num(scores.get("runs_scored")).mean()
    archive_avg = num(all_innings.get("runs_scored")).mean()
    if pd.notna(ground_avg) and pd.notna(archive_avg) and ground_avg > archive_avg:
        return "This is where FVCC scores above its archive average."
    return "This ground has a distinct profile in the current scorecard archive."


def empty_profile(kind: str) -> dict[str, Any]:
    return {"title": f"No {kind} selected", "subtitle": "", "heatmap": [], "insight": "Select an option to build this view."}


def record(row: pd.Series, title: str, value: str, subtitle: str, detail: str, badge: str) -> dict[str, Any]:
    return {"title": title, "value": value, "subtitle": subtitle, "detail": detail or context(row), "badge": badge, "context": context(row)}


def match_label(row: pd.Series) -> str:
    parts = [safe_text(row.get("match_date_display")), safe_text(row.get("fvcc_team_name")), "vs", safe_text(row.get("opponent_name")), safe_text(row.get("grade_name"))]
    return " ".join([part for part in parts if part]).replace(" vs ", " vs ")


def context(row: pd.Series) -> str:
    parts = [row.get("opponent_name") or row.get("context"), row.get("season"), row.get("grade_name")]
    return " | ".join([safe_text(part) for part in parts if safe_text(part)])


def first_or_none(rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    return rows[0] if rows else None


def next_highest_score(batting: pd.DataFrame, row: pd.Series) -> float:
    peers = batting[
        (batting.get("match_id", pd.Series(dtype="object")).astype(str) == safe_text(row.get("match_id")))
        & (batting.get("innings_id", pd.Series(dtype="object")).astype(str) == safe_text(row.get("innings_id")))
        & (batting.get("participant_id", pd.Series(dtype="object")).astype(str) != safe_text(row.get("participant_id")))
    ]
    return float(num(peers.get("runs_scored")).max()) if not peers.empty else 0


def dismissal_flags(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype="bool")
    text = clean(frame.get("dismissal_type", pd.Series("", index=frame.index)))
    fallback = clean(frame.get("dismissal_text", pd.Series("", index=frame.index)))
    combined = text.where(text != "", fallback).str.casefold()
    return ~combined.isin({"", "not out", "retired not out", "retired hurt"})


def dismissal_bucket(row: pd.Series) -> str:
    text = f"{safe_text(row.get('dismissal_type'))} {safe_text(row.get('dismissal_text'))}".casefold()
    if "caught" in text or text.startswith("c "):
        return "Caught"
    if "bowled" in text:
        return "Bowled"
    if "lbw" in text:
        return "LBW"
    if "run out" in text:
        return "Run out"
    if "stump" in text:
        return "Stumped"
    return "Other"


def fielding_line(row: pd.Series) -> str:
    pieces = []
    for column, label in [("catches", "catches"), ("run_outs", "run outs"), ("stumpings", "stumpings"), ("assisted_run_outs", "assists")]:
        value = int(n(row.get(column)))
        if value:
            pieces.append(f"{value} {label}")
    return " | ".join(pieces) if pieces else "No fielding dismissals"


def wicket_dots(wickets: Any, total: Any) -> str:
    wickets_int = int(n(wickets))
    total_int = int(n(total))
    if total_int <= 0:
        return f"{wickets_int} wickets"
    dots = "●" * min(wickets_int, total_int) + "○" * max(total_int - wickets_int, 0)
    return f"{dots} {wickets_int} of {total_int}"


def first_text(values: pd.Series) -> str:
    for value in values:
        text = safe_text(value)
        if text:
            return text
    return ""


def first_row_text(row: pd.Series) -> str:
    for value in row:
        text = safe_text(value)
        if text:
            return text
    return ""


def player_name(row: pd.Series) -> str:
    return safe_text(row.get("player_display_name") or row.get("canonical_player_name") or row.get("player_name"), "Unknown player")


def clean(values: pd.Series) -> pd.Series:
    return values.fillna("").astype(str).str.replace(r"\s+", " ", regex=True).str.strip().replace({"nan": "", "None": "", "NaT": ""})


def safe_text(value: Any, fallback: str = "") -> str:
    if value is None or pd.isna(value):
        return fallback
    text = str(value).strip()
    if not text or text.casefold() in {"nan", "none", "nat"}:
        return fallback
    return " ".join(text.split())


def num(values: Any) -> pd.Series:
    if isinstance(values, pd.Series):
        return pd.to_numeric(values, errors="coerce").fillna(0)
    return pd.Series(pd.to_numeric(values, errors="coerce")).fillna(0)


def n(value: Any) -> float:
    numeric = pd.to_numeric(value, errors="coerce")
    return 0.0 if pd.isna(numeric) else float(numeric)


def safe_div(numerator: float, denominator: float) -> float | None:
    if denominator is None or pd.isna(denominator) or float(denominator) == 0:
        return None
    return float(numerator) / float(denominator)


def pct(value: Any) -> str:
    return fmt_pct(value)


def fmt_pct(value: Any) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    return "N/A" if pd.isna(numeric) else f"{float(numeric):.1f}%"


def fmt_decimal(value: Any) -> str:
    numeric = pd.to_numeric(value, errors="coerce")
    return "N/A" if pd.isna(numeric) else f"{float(numeric):.2f}"
