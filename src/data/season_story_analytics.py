from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.data.name_normalization import normalize_opponent_club_name


def safe_number(value: object, default: float = 0.0) -> float:
    parsed = pd.to_numeric(value, errors="coerce")
    return default if pd.isna(parsed) else float(parsed)


def clean_text(value: object, default: str = "") -> str:
    text = str(value or "").strip()
    return default if text.casefold() in {"", "nan", "none"} else text


def load_match_centre_scope(processed_root: Path) -> dict[str, pd.DataFrame]:
    scope = processed_root / "all_available"
    return {
        "matches": read_csv(scope / "all_matches.csv"),
        "batting": read_csv(scope / "all_scorecard_batting.csv"),
        "bowling": read_csv(scope / "all_scorecard_bowling.csv"),
        "balls": read_csv(scope / "all_ball_by_ball.csv"),
    }


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def selected_team_ids(dashboard_data: dict[str, object]) -> set[str]:
    return {clean_text(team.get("id")) for team in dashboard_data.get("teams", []) if clean_text(team.get("id"))}


def filter_match_data(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    season = dashboard_data.get("season", {}) or {}
    season_id = clean_text(season.get("id"))
    season_name = clean_text(season.get("name"))
    team_ids = selected_team_ids(dashboard_data)
    matches = match_data.get("matches", pd.DataFrame()).copy()
    if not matches.empty:
        if season_id and "season_id" in matches:
            matches = matches[matches["season_id"].astype(str) == season_id]
        elif season_name and "season" in matches:
            matches = matches[matches["season"].astype(str).str.casefold() == season_name.casefold()]
        if team_ids:
            home = matches.get("home_team_id", pd.Series("", index=matches.index)).astype(str).isin(team_ids)
            away = matches.get("away_team_id", pd.Series("", index=matches.index)).astype(str).isin(team_ids)
            source = matches.get("source_team_ids", pd.Series("", index=matches.index)).astype(str).map(
                lambda value: bool(team_ids.intersection({part.strip() for part in value.split("|") if part.strip()}))
            )
            matches = matches[home | away | source].copy()
    match_ids = set(matches.get("match_id", pd.Series(dtype=str)).astype(str))
    scoped = {"matches": matches}
    for key in ["batting", "bowling", "balls"]:
        frame = match_data.get(key, pd.DataFrame()).copy()
        if not frame.empty and match_ids and "match_id" in frame:
            frame = frame[frame["match_id"].astype(str).isin(match_ids)].copy()
        if not frame.empty and team_ids and "team_id" in frame:
            frame = frame[frame["team_id"].astype(str).isin(team_ids)].copy()
        if not frame.empty and key == "balls" and team_ids:
            batting_team = frame.get("batting_team_id", pd.Series("", index=frame.index)).astype(str).isin(team_ids)
            bowling_team = frame.get("bowling_team_id", pd.Series("", index=frame.index)).astype(str).isin(team_ids)
            frame = frame[batting_team | bowling_team].copy()
        scoped[key] = frame
    return scoped


def top_player(df: pd.DataFrame, value_column: str, ascending: bool = False) -> dict[str, object] | None:
    if df.empty or value_column not in df:
        return None
    rows = df.copy()
    rows["_value"] = pd.to_numeric(rows[value_column], errors="coerce")
    rows = rows[rows["_value"].notna()]
    if rows.empty:
        return None
    if "player_name" in rows:
        rows["_name"] = rows["player_name"].fillna("").astype(str)
    else:
        rows["_name"] = ""
    rows = rows.sort_values(["_value", "_name"], ascending=[ascending, True])
    row = rows.iloc[0]
    return {
        "player": clean_text(row.get("player_name"), "Unknown player"),
        "player_id": clean_text(row.get("canonical_player_id") or row.get("player_id")),
        "value": safe_number(row.get(value_column)),
        "row": row,
    }


def build_season_story_summary(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> dict[str, object]:
    batting = dashboard_data.get("batting", pd.DataFrame())
    bowling = dashboard_data.get("bowling", pd.DataFrame())
    fielding = dashboard_data.get("fielding", pd.DataFrame())
    scoped_matches = filter_match_data(dashboard_data, match_data)
    matches = scoped_matches["matches"]
    runs = safe_number(pd.to_numeric(batting.get("battingAggregate"), errors="coerce").sum()) if not batting.empty else 0
    wickets = safe_number(pd.to_numeric(bowling.get("bowlingWickets"), errors="coerce").sum()) if not bowling.empty else 0
    catches = safe_number(pd.to_numeric(fielding.get("fieldingTotalCatches", fielding.get("catches_display")), errors="coerce").sum()) if not fielding.empty else 0
    top_score = top_player(batting, "battingHighScore")
    best_spell = best_bowling_spell(bowling)
    result = season_record(matches, selected_team_ids(dashboard_data))
    identity = season_identity(runs, wickets, batting, bowling, result)
    return {
        "identity": identity,
        "statement": story_statement(identity, dashboard_data.get("season", {}).get("name")),
        "record": result["label"],
        "top_score": top_score,
        "best_spell": best_spell,
        "tiles": [
            {"label": "Season record", "value": result["label"], "detail": "From available match results"},
            {"label": "Season identity", "value": identity, "detail": "Based on batting and bowling balance"},
            {"label": "Top score", "value": performance_label(top_score, "runs"), "detail": player_label(top_score)},
            {"label": "Best spell", "value": best_spell.get("figures", "-") if best_spell else "-", "detail": player_label(best_spell)},
        ],
    }


def season_record(matches: pd.DataFrame, team_ids: set[str]) -> dict[str, object]:
    wins = losses = draws = ties = 0
    if not matches.empty and "result_text" in matches:
        for _, row in matches.iterrows():
            result = clean_text(row.get("result_text")).casefold()
            winner = result.split(" won ")[0] if " won " in result else ""
            fvcc_winner = "fiji victorian" in winner
            if "draw" in result:
                draws += 1
            elif "tie" in result:
                ties += 1
            elif " won " in result and fvcc_winner:
                wins += 1
            elif " won " in result:
                losses += 1
    label = f"{wins}W - {losses}L"
    if draws:
        label += f" - {draws}D"
    if ties:
        label += f" - {ties}T"
    return {"wins": wins, "losses": losses, "draws": draws, "ties": ties, "label": label}


def season_identity(runs: float, wickets: float, batting: pd.DataFrame, bowling: pd.DataFrame, record: dict[str, object]) -> str:
    if safe_number(record.get("wins")) >= 6 and safe_number(record.get("losses")) <= 1:
        return "Premiership pace"
    run_leaders = pd.to_numeric(batting.get("battingAggregate"), errors="coerce").fillna(0) if not batting.empty else pd.Series(dtype=float)
    wicket_leaders = pd.to_numeric(bowling.get("bowlingWickets"), errors="coerce").fillna(0) if not bowling.empty else pd.Series(dtype=float)
    if wickets >= 20 and (runs <= 0 or wickets / max(len(bowling), 1) > runs / max(len(batting), 1) / 45):
        return "Bowling-led"
    if run_leaders.max() >= 250 or runs >= 900:
        return "Batting-led"
    if wicket_leaders[wicket_leaders > 0].count() >= 5 and run_leaders[run_leaders > 30].count() >= 5:
        return "Balanced"
    return "Building"


def story_statement(identity: str, season_name: object) -> str:
    season = clean_text(season_name, "This season")
    copy = {
        "Bowling-led": f"{season} is shaping as a bowling-led season, with FVCC's edge coming through wicket pressure and controlled spells.",
        "Batting-led": f"{season} has been driven by batting output, with the top run-makers setting the tone across the scorecards.",
        "Balanced": f"{season} looks balanced so far, with contributions spread across bat, ball and field.",
        "Premiership pace": f"{season} has the profile of a contender, with results and player impact lining up strongly.",
        "Building": f"{season} is still taking shape, with early patterns emerging across the available records.",
    }
    return copy.get(identity, copy["Building"])


def build_if_season_ended_today(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    batting = dashboard_data.get("batting", pd.DataFrame())
    bowling = dashboard_data.get("bowling", pd.DataFrame())
    fielding = dashboard_data.get("fielding", pd.DataFrame())
    awards = [
        award("Run leader", top_player(batting, "battingAggregate"), "runs"),
        award("Wicket leader", top_player(bowling, "bowlingWickets"), "wickets"),
        award("Best batting average", qualified_best(batting, "battingAverage", "battingInnings", 3, False), "avg"),
        award("Best bowling average", qualified_best(bowling, "bowlingAverage", "bowlingWickets", 2, True), "avg"),
        award("Fielding leader", top_player(fielding, "fieldingTotalCatches" if "fieldingTotalCatches" in fielding else "catches_display"), "dismissals"),
        award("Best all-rounder", all_round_star(batting, bowling), "impact pts"),
        award("Hidden MVP", hidden_mvp(batting, bowling, fielding), "impact pts"),
    ]
    fastest = fastest_verified_innings(dashboard_data, match_data)
    if fastest:
        awards.append(fastest)
    return [item for item in awards if item]


def build_season_awards(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    batting = dashboard_data.get("batting", pd.DataFrame())
    bowling = dashboard_data.get("bowling", pd.DataFrame())
    fielding = dashboard_data.get("fielding", pd.DataFrame())
    return [
        award("Orange Cap", top_player(batting, "battingAggregate"), "runs", "Most runs this season"),
        award("Purple Cap", top_player(bowling, "bowlingWickets"), "wickets", "Leading wicket-taker this season"),
        award("Golden Gloves", top_player(fielding, "fieldingTotalCatches" if "fieldingTotalCatches" in fielding else "catches_display"), "dismissals", "Most fielding dismissals"),
        award("All-Round Star", all_round_star(batting, bowling), "impact pts", "Best combined batting and bowling impact"),
        award("Economy Controller", qualified_best(bowling, "bowlingEconomyRate", "bowlingBalls", 60, True), "econ", "Best economy with a bowling workload"),
        award("Strike Bowler", wicket_rate_leader(bowling), "wickets/match", "Best wicket rate with a meaningful sample"),
        award("Hidden MVP", hidden_mvp(batting, bowling, fielding), "impact pts", "Simple scorecard impact across disciplines"),
    ]


def award(title: str, item: dict[str, object] | None, unit: str, reason: str | None = None) -> dict[str, object] | None:
    if not item:
        return None
    return {
        "title": title,
        "player": item.get("player", "Unknown player"),
        "player_id": item.get("player_id", ""),
        "value": item.get("value", 0),
        "unit": unit,
        "reason": reason or "",
    }


def qualified_best(df: pd.DataFrame, value_column: str, qualifier_column: str, minimum: float, lower_is_better: bool) -> dict[str, object] | None:
    if df.empty or value_column not in df or qualifier_column not in df:
        return None
    rows = df.copy()
    rows["_qualifier"] = pd.to_numeric(rows[qualifier_column], errors="coerce").fillna(0)
    rows = rows[rows["_qualifier"] >= minimum]
    rows["_value"] = pd.to_numeric(rows[value_column], errors="coerce")
    rows = rows[rows["_value"].notna() & (rows["_value"] > 0)]
    if rows.empty:
        return None
    rows = rows.sort_values("_value", ascending=lower_is_better)
    row = rows.iloc[0]
    return {"player": clean_text(row.get("player_name")), "player_id": clean_text(row.get("canonical_player_id")), "value": safe_number(row.get(value_column)), "row": row}


def all_round_star(batting: pd.DataFrame, bowling: pd.DataFrame) -> dict[str, object] | None:
    if batting.empty or bowling.empty:
        return None
    bat = batting[["canonical_player_id", "player_name", "battingAggregate"]].copy() if {"canonical_player_id", "player_name", "battingAggregate"}.issubset(batting.columns) else pd.DataFrame()
    bowl = bowling[["canonical_player_id", "bowlingWickets"]].copy() if {"canonical_player_id", "bowlingWickets"}.issubset(bowling.columns) else pd.DataFrame()
    if bat.empty or bowl.empty:
        return None
    merged = bat.merge(bowl, on="canonical_player_id", how="inner")
    merged["impact"] = pd.to_numeric(merged["battingAggregate"], errors="coerce").fillna(0) + pd.to_numeric(merged["bowlingWickets"], errors="coerce").fillna(0) * 25
    merged = merged[merged["impact"] > 0].sort_values("impact", ascending=False)
    if merged.empty:
        return None
    row = merged.iloc[0]
    return {"player": clean_text(row.get("player_name")), "player_id": clean_text(row.get("canonical_player_id")), "value": safe_number(row.get("impact")), "row": row}


def hidden_mvp(batting: pd.DataFrame, bowling: pd.DataFrame, fielding: pd.DataFrame) -> dict[str, object] | None:
    parts = []
    if not batting.empty and {"canonical_player_id", "player_name", "battingAggregate"}.issubset(batting.columns):
        part = batting[["canonical_player_id", "player_name", "battingAggregate"]].copy()
        part["impact"] = pd.to_numeric(part["battingAggregate"], errors="coerce").fillna(0)
        parts.append(part[["canonical_player_id", "player_name", "impact"]])
    if not bowling.empty and {"canonical_player_id", "player_name", "bowlingWickets"}.issubset(bowling.columns):
        part = bowling[["canonical_player_id", "player_name", "bowlingWickets"]].copy()
        part["impact"] = pd.to_numeric(part["bowlingWickets"], errors="coerce").fillna(0) * 25
        parts.append(part[["canonical_player_id", "player_name", "impact"]])
    field_col = "fieldingTotalCatches" if "fieldingTotalCatches" in fielding else "catches_display"
    if not fielding.empty and {"canonical_player_id", "player_name", field_col}.issubset(fielding.columns):
        part = fielding[["canonical_player_id", "player_name", field_col]].copy()
        part["impact"] = pd.to_numeric(part[field_col], errors="coerce").fillna(0) * 10
        parts.append(part[["canonical_player_id", "player_name", "impact"]])
    if not parts:
        return None
    merged = pd.concat(parts, ignore_index=True).groupby("canonical_player_id", as_index=False).agg(player_name=("player_name", "first"), impact=("impact", "sum"))
    merged = merged.sort_values("impact", ascending=False)
    if merged.empty or safe_number(merged.iloc[0].get("impact")) <= 0:
        return None
    row = merged.iloc[0]
    return {"player": clean_text(row.get("player_name")), "player_id": clean_text(row.get("canonical_player_id")), "value": safe_number(row.get("impact")), "row": row}


def wicket_rate_leader(bowling: pd.DataFrame) -> dict[str, object] | None:
    if bowling.empty or not {"bowlingWickets", "matches"}.issubset(bowling.columns):
        return None
    rows = bowling.copy()
    rows["wickets"] = pd.to_numeric(rows["bowlingWickets"], errors="coerce").fillna(0)
    rows["matches_num"] = pd.to_numeric(rows["matches"], errors="coerce").fillna(0)
    rows = rows[(rows["wickets"] >= 2) & (rows["matches_num"] > 0)]
    if rows.empty:
        return None
    rows["rate"] = rows["wickets"] / rows["matches_num"]
    row = rows.sort_values("rate", ascending=False).iloc[0]
    return {"player": clean_text(row.get("player_name")), "player_id": clean_text(row.get("canonical_player_id")), "value": safe_number(row.get("rate")), "row": row}


def build_season_pulse(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    scoped = filter_match_data(dashboard_data, match_data)
    matches = scoped["matches"].copy()
    if matches.empty:
        return []
    batting = scoped["batting"]
    bowling = scoped["bowling"]
    cards = []
    team_ids = selected_team_ids(dashboard_data)
    matches["_date"] = pd.to_datetime(matches.get("first_match_day"), errors="coerce", utc=True)
    for _, match in matches.sort_values("_date").iterrows():
        match_id = clean_text(match.get("match_id"))
        bat_rows = batting[batting.get("match_id", pd.Series(dtype=str)).astype(str) == match_id] if not batting.empty else pd.DataFrame()
        bowl_rows = bowling[bowling.get("match_id", pd.Series(dtype=str)).astype(str) == match_id] if not bowling.empty else pd.DataFrame()
        top_bat = scorecard_top_batter(bat_rows)
        top_bowl = scorecard_best_bowler(bowl_rows)
        cards.append(
            {
                "match_id": match_id,
                "result": result_badge(match, team_ids),
                "opponent": opponent_name(match, team_ids),
                "grade": clean_text(match.get("grade_name"), "Grade unknown"),
                "date": clean_text(match.get("first_match_day"))[:10],
                "top_batter": top_bat,
                "best_bowler": top_bowl,
            }
        )
    return cards


def result_badge(match: pd.Series, team_ids: set[str]) -> str:
    result = clean_text(match.get("result_text")).casefold()
    winner = result.split(" won ")[0] if " won " in result else ""
    if "draw" in result:
        return "DRAW"
    if "tie" in result:
        return "TIE"
    if " won " in result and "fiji victorian" in winner:
        return "WON"
    if " won " in result:
        return "LOST"
    return "UNKNOWN"


def opponent_name(match: pd.Series, team_ids: set[str]) -> str:
    home_id = clean_text(match.get("home_team_id"))
    home = clean_text(match.get("home_team_name"))
    away = clean_text(match.get("away_team_name"))
    return normalize_opponent_club_name(away if home_id in team_ids else home)


def scorecard_top_batter(rows: pd.DataFrame) -> dict[str, object] | None:
    if rows.empty or "runs_scored" not in rows:
        return None
    rows = rows.copy()
    rows["_runs"] = pd.to_numeric(rows["runs_scored"], errors="coerce").fillna(0)
    row = rows.sort_values("_runs", ascending=False).iloc[0]
    return {"player": clean_text(row.get("player_name")), "value": int(safe_number(row.get("runs_scored"))), "suffix": "runs"}


def scorecard_best_bowler(rows: pd.DataFrame) -> dict[str, object] | None:
    if rows.empty or "wickets_taken" not in rows:
        return None
    rows = rows.copy()
    rows["_wk"] = pd.to_numeric(rows["wickets_taken"], errors="coerce").fillna(0)
    rows["_runs"] = pd.to_numeric(rows.get("runs_conceded"), errors="coerce").fillna(999)
    row = rows.sort_values(["_wk", "_runs"], ascending=[False, True]).iloc[0]
    return {"player": clean_text(row.get("player_name")), "value": f"{int(safe_number(row.get('wickets_taken')))}-{int(safe_number(row.get('runs_conceded')))}", "suffix": ""}


def build_top_performances(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    scoped = filter_match_data(dashboard_data, match_data)
    batting = scoped["batting"]
    bowling = scoped["bowling"]
    performances = []
    if not batting.empty and "runs_scored" in batting:
        row = batting.assign(_runs=pd.to_numeric(batting["runs_scored"], errors="coerce").fillna(0)).sort_values("_runs", ascending=False).iloc[0]
        performances.append(performance_card("Best Batting Innings", clean_text(row.get("player_name")), f"{int(safe_number(row.get('runs_scored')))} runs", row))
        performances.append(carry_job_card(batting))
    if not bowling.empty and "wickets_taken" in bowling:
        rows = bowling.assign(_wk=pd.to_numeric(bowling["wickets_taken"], errors="coerce").fillna(0), _runs=pd.to_numeric(bowling.get("runs_conceded"), errors="coerce").fillna(999)).sort_values(["_wk", "_runs"], ascending=[False, True])
        row = rows.iloc[0]
        performances.append(performance_card("Best Bowling Innings", clean_text(row.get("player_name")), f"{int(safe_number(row.get('wickets_taken')))}-{int(safe_number(row.get('runs_conceded')))}", row))
    all_round = all_round_star(dashboard_data.get("batting", pd.DataFrame()), dashboard_data.get("bowling", pd.DataFrame()))
    if all_round:
        performances.append({"title": "Best All-Round Performance", "player": all_round["player"], "value": f"{all_round['value']:.0f} pts", "context": "Season scorecard impact", "match_id": ""})
    return [item for item in performances if item]


def performance_card(title: str, player: str, value: str, row: pd.Series) -> dict[str, object]:
    return {
        "title": title,
        "player": player,
        "value": value,
        "context": clean_text(row.get("grade_name"), "Selected season"),
        "match_id": clean_text(row.get("match_id")),
    }


def carry_job_card(batting: pd.DataFrame) -> dict[str, object] | None:
    if batting.empty or not {"runs_scored", "match_id"}.issubset(batting.columns):
        return None
    rows = batting.copy()
    rows["runs"] = pd.to_numeric(rows["runs_scored"], errors="coerce").fillna(0)
    totals = rows.groupby("match_id")["runs"].transform("sum")
    rows["share"] = rows["runs"] / totals.replace(0, pd.NA)
    rows = rows[rows["share"].notna()].sort_values("share", ascending=False)
    if rows.empty:
        return None
    row = rows.iloc[0]
    return performance_card("Biggest Carry Job", clean_text(row.get("player_name")), f"{row['share'] * 100:.0f}% of runs", row)


def build_batting_depth_chart(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    batting = filter_match_data(dashboard_data, match_data)["batting"]
    if batting.empty or "bat_order" not in batting:
        return []
    rows = batting.copy()
    rows["bat_order"] = pd.to_numeric(rows["bat_order"], errors="coerce")
    rows["runs"] = pd.to_numeric(rows.get("runs_scored"), errors="coerce").fillna(0)
    rows["out"] = rows.get("dismissal_type", pd.Series("", index=rows.index)).fillna("").astype(str).str.strip().ne("Not Out")
    rows["bucket"] = rows["bat_order"].map(position_bucket)
    grouped = rows.dropna(subset=["bucket"]).groupby("bucket", as_index=False).agg(innings=("runs", "count"), runs=("runs", "sum"), outs=("out", "sum"))
    order = ["Openers", "No. 3", "No. 4", "No. 5", "No. 6", "No. 7", "No. 8", "No. 9", "Tail"]
    grouped["order"] = grouped["bucket"].map({name: index for index, name in enumerate(order)})
    total_runs = max(float(grouped["runs"].sum()), 1.0)
    grouped["average"] = grouped.apply(lambda row: row["runs"] / row["outs"] if row["outs"] else pd.NA, axis=1)
    grouped["share"] = grouped["runs"] / total_runs * 100
    return grouped.sort_values("order").to_dict("records")


def position_bucket(order: object) -> str | None:
    if pd.isna(order):
        return None
    value = int(order)
    if value in {1, 2}:
        return "Openers"
    if 3 <= value <= 9:
        return f"No. {value}"
    return "Tail"


def build_bowling_role_map(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    bowling = dashboard_data.get("bowling", pd.DataFrame())
    roles = [
        role("Strike Bowler", top_player(bowling, "bowlingWickets"), "Most wickets"),
        role("Economy Controller", qualified_best(bowling, "bowlingEconomyRate", "bowlingBalls", 60, True), "Best economy"),
        role("Workhorse", top_player(bowling, "bowlingBalls"), "Most balls bowled"),
        role("Breakthrough Bowler", wicket_rate_leader(bowling), "Best wicket rate"),
        role("Wicket Share Leader", wicket_share_leader(bowling), "Highest share of wickets"),
    ]
    return [item for item in roles if item]


def wicket_share_leader(bowling: pd.DataFrame) -> dict[str, object] | None:
    if bowling.empty or "bowlingWickets" not in bowling:
        return None
    total = pd.to_numeric(bowling["bowlingWickets"], errors="coerce").fillna(0).sum()
    item = top_player(bowling, "bowlingWickets")
    if not item or total <= 0:
        return None
    item["value"] = safe_number(item["value"]) / total * 100
    return item


def role(title: str, item: dict[str, object] | None, reason: str) -> dict[str, object] | None:
    if not item:
        return None
    return {"title": title, "player": item.get("player"), "player_id": item.get("player_id"), "value": item.get("value"), "reason": reason}


def build_records_broken(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> list[dict[str, object]]:
    story = build_season_story_summary(dashboard_data, match_data)
    records = []
    if story.get("top_score"):
        records.append({"badge": "Season best", "title": "Highest score", "player": story["top_score"]["player"], "value": performance_label(story["top_score"], "runs")})
    if story.get("best_spell"):
        records.append({"badge": "Season best", "title": "Best bowling", "player": story["best_spell"]["player"], "value": story["best_spell"]["figures"]})
    fastest = fastest_verified_innings(dashboard_data, match_data)
    if fastest:
        records.append({"badge": "Verified BBB", "title": "Fastest innings", "player": fastest["player"], "value": fastest["value"]})
    return records


def fastest_verified_innings(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> dict[str, object] | None:
    balls = filter_match_data(dashboard_data, match_data)["balls"]
    if balls.empty or not {"striker_participant_id", "striker_runs_scored", "striker_balls_faced"}.issubset(balls.columns):
        return None
    team_ids = selected_team_ids(dashboard_data)
    if team_ids and "batting_team_id" in balls:
        balls = balls[balls["batting_team_id"].astype(str).isin(team_ids)].copy()
    if balls.empty:
        return None
    rows = balls.copy()
    rows["runs"] = pd.to_numeric(rows["striker_runs_scored"], errors="coerce")
    rows["balls"] = pd.to_numeric(rows["striker_balls_faced"], errors="coerce")
    rows = rows[(rows["runs"] >= 25) & (rows["balls"] > 0)]
    if rows.empty:
        return None
    row = rows.sort_values(["balls", "runs"], ascending=[True, False]).iloc[0]
    return {"title": "Fastest verified innings", "player": clean_text(row.get("striker_short_name"), "Verified batter"), "value": f"{int(row['runs'])} off {int(row['balls'])}", "unit": "", "reason": "From ball-by-ball coverage"}


def build_strengths_watchouts(dashboard_data: dict[str, object], match_data: dict[str, pd.DataFrame]) -> dict[str, list[str]]:
    batting = dashboard_data.get("batting", pd.DataFrame())
    bowling = dashboard_data.get("bowling", pd.DataFrame())
    story = build_season_story_summary(dashboard_data, match_data)
    strengths = []
    watchouts = []
    if story["identity"] == "Bowling-led":
        strengths.append("Bowling has controlled the season story so far.")
    if story["identity"] == "Batting-led":
        strengths.append("Run scoring has created the strongest edge.")
    if pd.to_numeric(bowling.get("bowlingWickets"), errors="coerce").fillna(0).gt(0).sum() >= 5:
        strengths.append("Wickets are spread across multiple bowling options.")
    if pd.to_numeric(batting.get("batting0s"), errors="coerce").fillna(0).sum() >= 5:
        watchouts.append("Ducks are worth monitoring across the batting card.")
    if not match_data.get("balls", pd.DataFrame()).empty:
        strengths.append("Verified ball-by-ball coverage supports richer insights.")
    else:
        watchouts.append("Ball-by-ball coverage is limited for this selection.")
    if not strengths:
        strengths.append("The season has enough scorecard data to identify emerging patterns.")
    if not watchouts:
        watchouts.append("Small samples can swing quickly; keep an eye on the next match.")
    return {"strengths": strengths[:3], "watchouts": watchouts[:3]}


def best_bowling_spell(bowling: pd.DataFrame) -> dict[str, object] | None:
    if bowling.empty or "bowlingBestInnings" not in bowling:
        return None
    rows = bowling.copy()
    figures = rows["bowlingBestInnings"].fillna("").astype(str).str.extract(r"(\d+)\s*[-/]\s*(\d+)")
    rows["_wk"] = pd.to_numeric(figures[0], errors="coerce").fillna(0)
    rows["_runs"] = pd.to_numeric(figures[1], errors="coerce").fillna(9999)
    rows = rows[rows["_wk"] > 0]
    if rows.empty:
        return None
    row = rows.sort_values(["_wk", "_runs"], ascending=[False, True]).iloc[0]
    return {"player": clean_text(row.get("player_name")), "player_id": clean_text(row.get("canonical_player_id")), "figures": clean_text(row.get("bowlingBestInnings")), "value": safe_number(row.get("_wk")), "row": row}


def performance_label(item: dict[str, object] | None, suffix: str) -> str:
    if not item:
        return "-"
    value = safe_number(item.get("value"))
    return f"{int(value):,} {suffix}" if value.is_integer() else f"{value:.1f} {suffix}"


def player_label(item: dict[str, object] | None) -> str:
    return clean_text(item.get("player") if item else "", "-")
