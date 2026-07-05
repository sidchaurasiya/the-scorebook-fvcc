"""Hawks-specific match-count policy helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[2]
CLUB_ID = "glen-waverley-hawks"
PROCESSED = ROOT / "clubs" / CLUB_ID / "data" / "processed"
MATCH_CENTRE = ROOT / "data" / "processed" / "match_centre" / CLUB_ID / "all_available"
RAW_MATCH_CENTRE = ROOT / "data" / "raw" / "match_centre" / CLUB_ID / "all_available"

NO_PLAY_TERMS = {
    "abandoned",
    "washout",
    "washed out",
    "forfeit",
    "forfeited",
    "bye",
    "cancelled",
    "canceled",
    "no play",
    "no result",
}


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, low_memory=False)


def cricket_overs_to_balls(value: object) -> int:
    if pd.isna(value):
        return 0
    text = str(value).strip()
    if not text:
        return 0
    try:
        whole, _, part = text.partition(".")
        overs = int(float(whole)) if whole else 0
        balls = int(part[:1] or 0) if part else 0
        if balls >= 6:
            return int(round(float(text) * 6))
        return overs * 6 + balls
    except (TypeError, ValueError):
        return 0


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def match_format(row: pd.Series) -> str:
    text = " ".join(
        clean_text(row.get(column))
        for column in ["match_type", "grade_name", "competition", "round_name"]
        if column in row.index
    ).casefold()
    if re.search(r"\b(t20|twenty20|20\s*over|20-over)\b", text):
        return "T20"
    if "one day" in text or re.search(r"\b(35|40|45|50|60|70|80)\s*overs?\b", text):
        return "One Day"
    if "two day" in text or "2 day" in text:
        return "Two Day"
    return "Unknown"


def load_config_policy() -> dict[str, float | str]:
    path = ROOT / "clubs" / CLUB_ID / "club_config.yaml"
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    return config.get("match_count_policy", {})


def load_policy_frames() -> dict[str, pd.DataFrame]:
    return {
        "matches": read_csv(MATCH_CENTRE / "all_matches.csv"),
        "innings": read_csv(MATCH_CENTRE / "all_match_innings.csv"),
        "balls": read_csv(MATCH_CENTRE / "all_ball_by_ball.csv"),
        "overs": read_csv(MATCH_CENTRE / "all_overs.csv"),
        "batting": read_csv(MATCH_CENTRE / "all_scorecard_batting.csv"),
        "bowling": read_csv(MATCH_CENTRE / "all_scorecard_bowling.csv"),
        "fielding": read_csv(MATCH_CENTRE / "all_scorecard_fielding.csv"),
        "teams": read_csv(PROCESSED / "teams.csv"),
        "players": read_csv(PROCESSED / "players.csv"),
    }


def club_team_ids(teams: pd.DataFrame) -> set[str]:
    if teams.empty or "team_id" not in teams:
        return set()
    return set(teams["team_id"].dropna().astype(str))


def selected_club_team_id(row: pd.Series, team_ids: set[str]) -> str:
    for column in ["home_team_id", "away_team_id"]:
        value = clean_text(row.get(column))
        if value in team_ids:
            return value
    for value in clean_text(row.get("source_team_ids")).split("|"):
        value = value.strip()
        if value in team_ids:
            return value
    return ""


def has_status_no_play_text(row: pd.Series) -> bool:
    text = " ".join(clean_text(row.get(column)) for column in ["status", "result_text"]).casefold()
    return any(term in text for term in NO_PLAY_TERMS)


def batting_activity(frame: pd.DataFrame) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=bool)
    dismissal = frame.get("dismissal_type", pd.Series("", index=frame.index)).fillna("").astype(str).str.casefold()
    text = frame.get("dismissal_text", pd.Series("", index=frame.index)).fillna("").astype(str).str.casefold()
    passive = dismissal.isin({"did not bat", "absent"}) | text.isin({"did not bat", "absent"})
    numeric_cols = ["runs_scored", "balls_faced", "fours_scored", "sixes_scored", "batting_minutes"]
    numeric = pd.Series(False, index=frame.index)
    for column in numeric_cols:
        if column in frame:
            numeric = numeric | pd.to_numeric(frame[column], errors="coerce").fillna(0).gt(0)
    active_dismissal = ~(dismissal.isin({"", "did not bat", "absent"}) | text.isin({"did not bat", "absent"}))
    return (~passive) & (numeric | active_dismissal)


def build_match_policy_table(frames: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    frames = frames or load_policy_frames()
    matches = frames["matches"].copy()
    if matches.empty:
        return pd.DataFrame()
    matches["match_id"] = matches["match_id"].astype(str)

    innings = frames["innings"].copy()
    balls = frames["balls"].copy()
    overs = frames["overs"].copy()
    batting = frames["batting"].copy()
    bowling = frames["bowling"].copy()
    fielding = frames["fielding"].copy()
    teams = frames["teams"].copy()
    team_ids = club_team_ids(teams)
    policy = load_config_policy()
    t20_weight = float(policy.get("t20_weight", 0.5))
    played_weight = float(policy.get("default_played_weight", 1.0))
    no_play_weight = float(policy.get("no_play_weight", 0.0))

    innings_match = pd.DataFrame({"match_id": matches["match_id"]})
    if not innings.empty:
        innings["match_id"] = innings["match_id"].astype(str)
        innings["_balls_from_overs"] = innings.get("overs_bowled", pd.Series(index=innings.index)).map(cricket_overs_to_balls)
        innings_match = innings.groupby("match_id", as_index=False).agg(
            innings_rows=("innings_id", "count"),
            innings_runs=("runs_scored", "sum"),
            innings_wickets=("wickets_fallen", "sum"),
            innings_balls=("_balls_from_overs", "sum"),
            innings_overs=("overs_bowled", "sum"),
        )

    ball_match = pd.DataFrame(columns=["match_id", "bbb_rows", "legal_balls"])
    if not balls.empty:
        balls["match_id"] = balls["match_id"].astype(str)
        ball_match = balls.groupby("match_id", as_index=False).agg(
            bbb_rows=("ball_event_id", "count"),
            legal_balls=("is_legal_delivery", lambda values: pd.Series(values).astype(str).str.casefold().isin({"true", "1"}).sum()),
        )

    over_match = pd.DataFrame(columns=["match_id", "over_rows", "over_legal_balls"])
    if not overs.empty:
        overs["match_id"] = overs["match_id"].astype(str)
        over_match = overs.groupby("match_id", as_index=False).agg(
            over_rows=("over_number", "count"),
            over_legal_balls=("legal_balls", "sum"),
        )

    bat_match = pd.DataFrame(columns=["match_id", "batting_rows", "active_batting_rows"])
    if not batting.empty:
        batting["match_id"] = batting["match_id"].astype(str)
        batting["_active"] = batting_activity(batting)
        bat_match = batting.groupby("match_id", as_index=False).agg(
            batting_rows=("participant_id", "count"),
            active_batting_rows=("_active", "sum"),
        )

    bowl_match = pd.DataFrame(columns=["match_id", "bowling_rows", "bowling_balls", "bowling_activity_rows"])
    if not bowling.empty:
        bowling["match_id"] = bowling["match_id"].astype(str)
        bowling["_balls"] = bowling.get("overs_bowled", pd.Series(index=bowling.index)).map(cricket_overs_to_balls)
        numeric_cols = ["runs_conceded", "wickets_taken", "maidens_bowled", "wides", "no_balls"]
        activity = bowling["_balls"].gt(0)
        for column in numeric_cols:
            if column in bowling:
                activity = activity | pd.to_numeric(bowling[column], errors="coerce").fillna(0).gt(0)
        bowling["_active"] = activity
        bowl_match = bowling.groupby("match_id", as_index=False).agg(
            bowling_rows=("participant_id", "count"),
            bowling_balls=("_balls", "sum"),
            bowling_activity_rows=("_active", "sum"),
        )

    field_match = pd.DataFrame(columns=["match_id", "fielding_rows", "fielding_activity_rows"])
    if not fielding.empty:
        fielding["match_id"] = fielding["match_id"].astype(str)
        activity = pd.Series(False, index=fielding.index)
        for column in ["catches", "run_outs", "stumpings", "assisted_run_outs"]:
            if column in fielding:
                activity = activity | pd.to_numeric(fielding[column], errors="coerce").fillna(0).gt(0)
        fielding["_active"] = activity
        field_match = fielding.groupby("match_id", as_index=False).agg(
            fielding_rows=("participant_id", "count"),
            fielding_activity_rows=("_active", "sum"),
        )

    out = matches.copy()
    for frame in [innings_match, ball_match, over_match, bat_match, bowl_match, field_match]:
        out = out.merge(frame, on="match_id", how="left")
    for column in [
        "innings_rows",
        "innings_runs",
        "innings_wickets",
        "innings_balls",
        "innings_overs",
        "bbb_rows",
        "legal_balls",
        "over_rows",
        "over_legal_balls",
        "batting_rows",
        "active_batting_rows",
        "bowling_rows",
        "bowling_balls",
        "bowling_activity_rows",
        "fielding_rows",
        "fielding_activity_rows",
    ]:
        out[column] = pd.to_numeric(out.get(column), errors="coerce").fillna(0)

    out["club_team_id"] = out.apply(lambda row: selected_club_team_id(row, team_ids), axis=1)
    selected_counts = raw_selected_player_counts(out)
    out = out.merge(selected_counts, on="match_id", how="left")
    out["selected_player_count"] = pd.to_numeric(out.get("selected_player_count"), errors="coerce").fillna(0)
    out["detected_match_format"] = out.apply(match_format, axis=1)
    out["status_no_play_signal"] = out.apply(has_status_no_play_text, axis=1)
    out["total_balls_detected"] = out[["legal_balls", "over_legal_balls", "innings_balls", "bowling_balls"]].max(axis=1)
    out["has_activity"] = (
        out["total_balls_detected"].gt(0)
        | out["active_batting_rows"].gt(0)
        | out["bowling_activity_rows"].gt(0)
        | out["fielding_activity_rows"].gt(0)
        | out["innings_runs"].gt(0)
        | out["innings_wickets"].gt(0)
    )
    out["is_no_play"] = (~out["has_activity"]) & (out["status_no_play_signal"] | out["selected_player_count"].gt(0))
    out["review_required"] = (out["status_no_play_signal"] & out["has_activity"]) | (
        (~out["has_activity"]) & (~out["status_no_play_signal"]) & out["selected_player_count"].eq(0)
    )
    out["match_weight"] = played_weight
    out.loc[out["detected_match_format"].eq("T20"), "match_weight"] = t20_weight
    out.loc[out["is_no_play"], "match_weight"] = no_play_weight
    out["gap_note"] = out.apply(match_gap_note, axis=1)
    return out


def raw_selected_player_counts(policy_seed: pd.DataFrame) -> pd.DataFrame:
    if policy_seed.empty:
        return pd.DataFrame(columns=["match_id", "selected_player_count"])
    match_lookup = policy_seed.set_index("match_id").to_dict("index")
    rows: list[dict[str, object]] = []
    for path in sorted(RAW_MATCH_CENTRE.glob("match=*__scorecard.json")):
        match_id = path.name.split("__", 1)[0].replace("match=", "", 1)
        match = match_lookup.get(match_id)
        if not match:
            continue
        club_team_id = clean_text(match.get("club_team_id"))
        if not club_team_id:
            continue
        payload = raw_scorecard_payload(path)
        selected = 0
        for team in payload.get("teams", []) or []:
            if clean_text(team.get("id")) == club_team_id:
                selected = len([player for player in team.get("players", []) or [] if clean_text(player.get("participantId"))])
                break
        rows.append({"match_id": match_id, "selected_player_count": selected})
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["match_id", "selected_player_count"])


def match_gap_note(row: pd.Series) -> str:
    notes: list[str] = []
    if bool(row.get("is_no_play")):
        notes.append("no play/activity detected")
    if bool(row.get("review_required")) and bool(row.get("status_no_play_signal")) and bool(row.get("has_activity")):
        notes.append("status suggests no-play but scorecard activity exists")
    if (
        not bool(row.get("has_activity"))
        and not bool(row.get("is_no_play"))
        and float(row.get("selected_player_count", 0) or 0) == 0
    ):
        notes.append("missing scorecard/player activity; treated as coverage gap, not no-play")
    if clean_text(row.get("detected_match_format")) == "Unknown" and not bool(row.get("is_no_play")):
        notes.append("match format unknown; default played weight used")
    if float(row.get("batting_rows", 0) or 0) == 0:
        notes.append("no batting scorecard rows")
    if float(row.get("bowling_rows", 0) or 0) == 0:
        notes.append("no bowling scorecard rows")
    return "; ".join(notes)


def raw_scorecard_payload(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    payload = raw.get("payload") if isinstance(raw, dict) else {}
    return payload if isinstance(payload, dict) else {}


def selected_player_rows(policy: pd.DataFrame | None = None) -> pd.DataFrame:
    policy = policy if policy is not None else build_match_policy_table()
    if policy.empty:
        return pd.DataFrame()
    match_lookup = policy.set_index("match_id").to_dict("index")
    rows: list[dict[str, object]] = []
    for path in sorted(RAW_MATCH_CENTRE.glob("match=*__scorecard.json")):
        match_id = path.name.split("__", 1)[0].replace("match=", "", 1)
        match = match_lookup.get(match_id)
        if not match:
            continue
        club_team_id = clean_text(match.get("club_team_id"))
        if not club_team_id:
            continue
        payload = raw_scorecard_payload(path)
        for team in payload.get("teams", []) or []:
            if clean_text(team.get("id")) != club_team_id:
                continue
            for player in team.get("players", []) or []:
                participant_id = clean_text(player.get("participantId"))
                if not participant_id:
                    continue
                rows.append(
                    {
                        "match_id": match_id,
                        "season": match.get("season", ""),
                        "season_id": match.get("season_id", ""),
                        "team_id": club_team_id,
                        "grade_id": match.get("grade_id", ""),
                        "grade_name": match.get("grade_name", ""),
                        "player_id": participant_id,
                        "player_name": clean_text(player.get("name")),
                        "detected_match_format": match.get("detected_match_format", ""),
                        "is_no_play": bool(match.get("is_no_play")),
                        "match_weight": float(match.get("match_weight", 0) or 0),
                    }
                )
    return pd.DataFrame(rows)


def player_season_weights(policy: pd.DataFrame | None = None) -> pd.DataFrame:
    selected = selected_player_rows(policy)
    if selected.empty:
        return pd.DataFrame()
    grouped = selected.groupby(["season", "season_id", "team_id", "grade_id", "player_id"], dropna=False, as_index=False).agg(
        player_name=("player_name", "first"),
        raw_selected_matches=("match_id", "nunique"),
        t20_matches=("detected_match_format", lambda values: (values == "T20").sum()),
        no_play_matches=("is_no_play", "sum"),
        weighted_matches=("match_weight", "sum"),
    )
    return grouped


def apply_weighted_matches_to_frame(frame: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or weights.empty or "matches" not in frame:
        return frame
    output = frame.copy()
    keys = ["season", "team_id", "grade_id", "raw_player_id"]
    if any(column not in output for column in keys):
        return output
    lookup = weights.rename(columns={"player_id": "raw_player_id"})[
        ["season", "team_id", "grade_id", "raw_player_id", "weighted_matches"]
    ].copy()
    for column in ["season", "team_id", "grade_id", "raw_player_id"]:
        output[column] = output[column].astype(str)
        lookup[column] = lookup[column].astype(str)
    output = output.merge(lookup, on=keys, how="left")
    output["raw_playhq_matches"] = pd.to_numeric(output.get("raw_playhq_matches", output["matches"]), errors="coerce").fillna(
        pd.to_numeric(output["matches"], errors="coerce").fillna(0)
    )
    output["matches"] = pd.to_numeric(output["weighted_matches"], errors="coerce").fillna(
        pd.to_numeric(output["matches"], errors="coerce").fillna(0)
    )
    return output.drop(columns=["weighted_matches"])


def apply_hawks_match_policy_to_app_data() -> dict[str, object]:
    policy = build_match_policy_table()
    weights = player_season_weights(policy)
    changed: dict[str, object] = {
        "policy_matches": len(policy),
        "selected_player_match_rows": int(len(selected_player_rows(policy))),
        "player_season_weight_rows": int(len(weights)),
        "files": [],
    }
    for filename in ["all_seasons_batting.csv", "all_seasons_bowling.csv", "all_seasons_fielding.csv"]:
        path = PROCESSED / filename
        frame = read_csv(path)
        if frame.empty:
            continue
        before = pd.to_numeric(frame.get("matches"), errors="coerce").fillna(0).sum()
        output = apply_weighted_matches_to_frame(frame, weights)
        after = pd.to_numeric(output.get("matches"), errors="coerce").fillna(0).sum()
        output.to_csv(path, index=False)
        changed["files"].append({"path": str(path), "rows": len(output), "matches_before": float(before), "matches_after": float(after)})
    write_weighted_win_rates(policy)
    return changed


def write_weighted_win_rates(policy: pd.DataFrame | None = None) -> pd.DataFrame:
    policy = policy if policy is not None else build_match_policy_table()
    selected = selected_player_rows(policy)
    if selected.empty:
        return pd.DataFrame()
    outcomes = policy[["match_id", "result_text", "home_team_name", "away_team_name", "club_team_id", "home_team_id", "away_team_id"]].copy()
    outcomes["match_id"] = outcomes["match_id"].astype(str)
    outcomes["win"] = outcomes.apply(classify_hawks_win, axis=1)
    selected = selected.merge(outcomes[["match_id", "win"]], on="match_id", how="left")
    selected = selected[selected["win"].notna() & selected["match_weight"].gt(0)].copy()
    if selected.empty:
        return pd.DataFrame()
    selected = apply_identity_lookup(selected)
    selected["weighted_win"] = selected["match_weight"] * selected["win"].astype(float)
    grouped = selected.groupby(["canonical_player_id", "canonical_player_name", "display_player_name"], as_index=False).agg(
        matches_with_result=("match_weight", "sum"),
        wins=("weighted_win", "sum"),
    )
    grouped["losses"] = grouped["matches_with_result"] - grouped["wins"]
    grouped["win_pct"] = grouped.apply(lambda row: row["wins"] * 100 / row["matches_with_result"] if row["matches_with_result"] else pd.NA, axis=1)
    grouped["player_key"] = grouped["canonical_player_id"]
    grouped["player_name_key"] = grouped["display_player_name"].astype(str).str.casefold().str.replace(r"[^a-z0-9]+", " ", regex=True).str.strip()
    grouped["source_coverage_note"] = "Hawks weighted match-count policy: T20=0.5, played non-T20=1, no-play=0."
    output = grouped[
        [
            "player_key",
            "canonical_player_id",
            "canonical_player_name",
            "display_player_name",
            "player_name_key",
            "matches_with_result",
            "wins",
            "losses",
            "win_pct",
            "source_coverage_note",
        ]
    ].sort_values("display_player_name")
    out_path = PROCESSED / "hall_of_fame" / "player_win_rates.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(out_path, index=False)
    return output


def apply_identity_lookup(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    lookup = raw_to_canonical_lookup()
    output["raw_player_id"] = output["player_id"].astype(str)
    output = output.merge(lookup, on="raw_player_id", how="left")
    fallback_key = output["raw_player_id"].map(lambda value: f"raw_{str(value).replace('-', '_')}")
    output["canonical_player_id"] = output["canonical_player_id"].fillna(fallback_key)
    output["canonical_player_name"] = output["canonical_player_name"].fillna(output["player_name"])
    output["display_player_name"] = output["display_player_name"].fillna(output["canonical_player_name"])
    return output


def raw_to_canonical_lookup() -> pd.DataFrame:
    parts = []
    for filename in ["all_seasons_batting.csv", "all_seasons_bowling.csv", "all_seasons_fielding.csv"]:
        frame = read_csv(PROCESSED / filename)
        required = {"raw_player_id", "canonical_player_id", "canonical_player_name"}
        if frame.empty or not required.issubset(frame.columns):
            continue
        rows = frame[["raw_player_id", "canonical_player_id", "canonical_player_name"]].copy()
        rows["display_player_name"] = rows["canonical_player_name"]
        parts.append(rows)
    if not parts:
        return pd.DataFrame(columns=["raw_player_id", "canonical_player_id", "canonical_player_name", "display_player_name"])
    output = pd.concat(parts, ignore_index=True, sort=False)
    for column in ["raw_player_id", "canonical_player_id", "canonical_player_name", "display_player_name"]:
        output[column] = output[column].astype(str)
    output = output[output["raw_player_id"].str.strip().ne("")]
    return output.drop_duplicates("raw_player_id", keep="last")


def classify_hawks_win(row: pd.Series) -> object:
    result = clean_text(row.get("result_text"))
    if not result or result.casefold() in {"result pending", "match drawn", "drawn"}:
        return pd.NA
    if not re.search(r"\bwon\b", result, flags=re.IGNORECASE):
        return pd.NA
    winner = re.split(r"\bwon\b", result, flags=re.IGNORECASE)[0].strip()
    club_team_id = clean_text(row.get("club_team_id"))
    club_name = clean_text(row.get("home_team_name")) if clean_text(row.get("home_team_id")) == club_team_id else clean_text(row.get("away_team_name"))
    if not winner or not club_name:
        return pd.NA
    return normalize_name(winner) == normalize_name(club_name)


def normalize_name(value: object) -> str:
    text = clean_text(value).casefold()
    text = re.sub(r"\b(cricket|club|cc)\b", " ", text)
    return re.sub(r"[^a-z0-9]+", " ", text).strip()
