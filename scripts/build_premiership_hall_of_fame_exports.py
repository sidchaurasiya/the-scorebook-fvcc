#!/usr/bin/env python3
"""Build deploy-safe Hall of Fame premiership exports.

Reads the local premiership exploration outputs and writes small tracked CSVs
under data/processed/hall_of_fame/. The Streamlit app uses these deploy-safe
files instead of ignored experimental audit outputs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.club_refresh_utils import add_club_args, get_club_team_ids, print_club_header, print_outputs, print_paths, resolve_club_id  # noqa: E402
from src.config.club_config import get_club_name, get_club_short_name, get_experimental_dir, get_hall_of_fame_dir, get_processed_match_centre_dir, get_raw_match_centre_dir  # noqa: E402
from src.utils.player_identity import apply_player_identity_mapping, display_player_name


OUTPUT_DIR = REPO_ROOT / "data" / "processed" / "hall_of_fame"
OUTPUT_FILENAMES = ["premiership_wins.csv", "player_premierships.csv"]
PREMIERSHIP_WINS_COLUMNS = [
    "match_id",
    "season",
    "grade_name",
    "round_name",
    "match_date",
    "club_team_id",
    "club_team_name",
    "fvcc_team_name",
    "opponent_team_name",
    "captain_name",
    "result_text",
    "result_margin_display",
    "venue_name",
    "scoreboard_url",
    "confidence",
    "detection_reason",
]
PLAYER_PREMIERSHIPS_COLUMNS = [
    "canonical_player_id",
    "canonical_player_name",
    "display_player_name",
    "premiership_count",
    "seasons",
    "grades",
    "teams",
    "latest_premiership_season",
    "evidence_match_ids",
    "confidence",
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build deploy-safe Hall of Fame premiership exports.")
    add_club_args(parser)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    club_id = resolve_club_id(args.club)
    exploration_dir = get_experimental_dir(club_id=club_id) / "premiership_exploration"
    match_centre_dir = get_processed_match_centre_dir(club_id=club_id) / "all_available"
    raw_match_centre_dir = get_raw_match_centre_dir(club_id=club_id) / "all_available"
    output_dir = OUTPUT_DIR if args.legacy_output else get_hall_of_fame_dir(club_id=club_id)
    output_paths = [output_dir / filename for filename in OUTPUT_FILENAMES]

    print_club_header("Hall of Fame premiership export builder", club_id)
    print_paths(
        "Inputs",
        [
            exploration_dir / "fvcc_premiership_win_candidates.csv",
            exploration_dir / "premiership_players_candidate.csv",
            match_centre_dir / "all_matches.csv",
        ],
    )
    print_outputs("Outputs", output_paths)
    if args.dry_run:
        print("Dry run complete. No files were written.")
        return 0

    wins = read_csv(exploration_dir / "fvcc_premiership_win_candidates.csv")
    players = read_csv(exploration_dir / "premiership_players_candidate.csv")
    matches = read_csv(match_centre_dir / "all_matches.csv")

    if wins.empty:
        wins_export = build_local_grand_final_premiership_wins(matches, club_id=club_id, raw_match_centre_dir=raw_match_centre_dir)
        players_export = build_local_player_premierships(match_centre_dir, wins_export, club_id=club_id)
        if wins_export.empty:
            print("No verified premiership wins found. Writing empty deploy-safe premiership exports.")
        else:
            print("Built premiership wins from local completed Grand Final match-centre rows.")
    else:
        wins_export = build_premiership_wins(wins, matches)
        players_export = build_player_premierships(players, wins_export)

    validate_exports(wins_export, players_export)

    output_dir.mkdir(parents=True, exist_ok=True)
    wins_export.to_csv(output_dir / "premiership_wins.csv", index=False)
    players_export.to_csv(output_dir / "player_premierships.csv", index=False)

    print(f"Wrote {len(wins_export)} premiership wins")
    print(f"Wrote {len(players_export)} player premiership records")
    return 0


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def empty_premiership_wins() -> pd.DataFrame:
    return pd.DataFrame(columns=PREMIERSHIP_WINS_COLUMNS)


def empty_player_premierships() -> pd.DataFrame:
    return pd.DataFrame(columns=PLAYER_PREMIERSHIPS_COLUMNS)


def build_premiership_wins(wins: pd.DataFrame, matches: pd.DataFrame) -> pd.DataFrame:
    output = wins.copy()
    output = output[output.get("confidence", "").astype(str).str.casefold() == "high"].copy()

    match_columns = [
        "match_id",
        "venue_name",
        "first_match_day",
        "last_match_day",
        "home_team_name",
        "away_team_name",
    ]
    if not matches.empty:
        context = matches[[column for column in match_columns if column in matches]].drop_duplicates("match_id")
        output = output.merge(context, on="match_id", how="left")

    output["captain_name"] = output.get("fvcc_captain_name", "").map(display_or_blank)
    output["match_date"] = output.get("match_date", "").where(output.get("match_date", "") != "", output.get("first_match_day", ""))
    output["result_margin_display"] = output.apply(result_margin_display, axis=1)
    output["scoreboard_url"] = output["match_id"].map(playcricket_scorecard_url)
    output["venue_name"] = output.get("venue_name", "").map(clean_text)
    output["opponent_team_name"] = output.get("opponent_team_name", "").map(clean_text)
    output["club_team_name"] = output.get("club_team_name", output.get("fvcc_team_name", "")).map(clean_text)
    output["fvcc_team_name"] = output["club_team_name"]

    for column in PREMIERSHIP_WINS_COLUMNS:
        if column not in output:
            output[column] = ""

    return (
        output[PREMIERSHIP_WINS_COLUMNS]
        .drop_duplicates("match_id")
        .sort_values(["season", "grade_name", "match_date"], na_position="last")
        .reset_index(drop=True)
    )


def build_local_grand_final_premiership_wins(
    matches: pd.DataFrame,
    club_id: str | None = None,
    raw_match_centre_dir: Path | None = None,
) -> pd.DataFrame:
    if matches.empty or "match_id" not in matches:
        return empty_premiership_wins()

    club_team_ids = get_club_team_ids(club_id)
    club_tokens = club_name_tokens(club_id)
    records: list[dict[str, object]] = []
    for _, row in matches.iterrows():
        round_name = clean_text(row.get("round_name"))
        if "grand final" not in normalize_team_name(round_name):
            continue
        if not is_completed_match(row):
            continue

        club_team_id, club_team_name, opponent_team_name = selected_club_team(row, club_team_ids, club_tokens)
        if not club_team_name:
            continue
        winner = winner_name_from_result(row.get("result_text"))
        if not names_match(normalize_team_name(winner), normalize_team_name(club_team_name)):
            continue

        captain_name = extract_winning_team_captain(
            raw_match_centre_dir,
            match_id=clean_text(row.get("match_id")),
            club_team_id=club_team_id,
        )
        records.append(
            {
                "match_id": clean_text(row.get("match_id")),
                "season": clean_text(row.get("season")),
                "grade_name": clean_text(row.get("grade_name")),
                "round_name": round_name,
                "match_date": clean_text(row.get("last_match_day") or row.get("first_match_day")),
                "club_team_id": club_team_id,
                "club_team_name": club_team_name,
                "fvcc_team_name": club_team_name,
                "opponent_team_name": opponent_team_name,
                "captain_name": captain_name,
                "result_text": clean_text(row.get("result_text")),
                "result_margin_display": result_margin_display(pd.Series({"result_text": row.get("result_text"), "club_team_name": club_team_name})),
                "venue_name": clean_text(row.get("venue_name")),
                "scoreboard_url": playcricket_scorecard_url(row.get("match_id")),
                "confidence": "high",
                "detection_reason": "completed Grand Final result names active club as winner",
            }
        )

    if not records:
        return empty_premiership_wins()
    output = pd.DataFrame(records).drop_duplicates("match_id")
    for column in PREMIERSHIP_WINS_COLUMNS:
        if column not in output:
            output[column] = ""
    return output[PREMIERSHIP_WINS_COLUMNS].sort_values(["season", "grade_name", "match_date"], na_position="last").reset_index(drop=True)


def extract_winning_team_captain(raw_match_centre_dir: Path | None, *, match_id: str, club_team_id: str) -> str:
    if not raw_match_centre_dir or not match_id or not club_team_id:
        return ""
    path = raw_match_centre_dir / f"match={match_id}__scorecard.json"
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8")).get("payload", {})
    except (OSError, json.JSONDecodeError):
        return ""
    for team in payload.get("teams") or []:
        if clean_text(team.get("id")) != club_team_id:
            continue
        captain = captain_from_players(team.get("players") or [])
        if captain:
            return captain
    return ""


def captain_from_players(players: list[dict[str, object]]) -> str:
    for player in players:
        roles = player.get("roles") or []
        role_labels = [clean_text(role).casefold() for role in roles if clean_text(role)]
        if any(role == "captain" for role in role_labels):
            return display_or_blank(player.get("name"))
        name = clean_text(player.get("name"))
        if re.search(r"\(\s*c\s*\)\s*$", name, flags=re.IGNORECASE):
            return display_or_blank(re.sub(r"\(\s*c\s*\)\s*$", "", name, flags=re.IGNORECASE).strip())
    return ""


def build_local_player_premierships(match_centre_dir: Path, wins: pd.DataFrame, club_id: str | None = None) -> pd.DataFrame:
    if wins.empty or "match_id" not in wins:
        return empty_player_premierships()

    participant_frames = []
    for filename in ["all_scorecard_batting.csv", "all_scorecard_bowling.csv", "all_scorecard_fielding.csv"]:
        frame = read_csv(match_centre_dir / filename)
        if frame.empty or not {"match_id", "team_id", "participant_id", "player_name"}.issubset(frame.columns):
            continue
        participant_frames.append(frame[["match_id", "team_id", "participant_id", "player_name"]].copy())
    if not participant_frames:
        return empty_player_premierships()

    win_context = wins[["match_id", "club_team_id", "season", "grade_name", "fvcc_team_name", "confidence"]].copy()
    participants = pd.concat(participant_frames, ignore_index=True, sort=False)
    participants["match_id"] = participants["match_id"].astype(str)
    participants["team_id"] = participants["team_id"].astype(str)
    win_context["match_id"] = win_context["match_id"].astype(str)
    win_context["club_team_id"] = win_context["club_team_id"].astype(str)
    rows = participants.merge(win_context, on="match_id", how="inner")
    rows = rows[rows["team_id"] == rows["club_team_id"]].copy()
    if rows.empty:
        return empty_player_premierships()

    rows = rows.rename(columns={"participant_id": "raw_player_id", "player_name": "raw_player_name"})
    rows["player_name"] = rows["raw_player_name"]
    rows = apply_player_identity_mapping(rows, club_id=club_id)
    rows["display_player_name"] = rows["canonical_player_name"].map(display_or_blank)
    rows = rows.drop_duplicates(["canonical_player_id", "match_id"])

    records: list[dict[str, object]] = []
    for (player_id, player_name, display_name), group in rows.groupby(
        ["canonical_player_id", "canonical_player_name", "display_player_name"],
        dropna=False,
    ):
        if not clean_text(display_name):
            continue
        unique_matches = sorted(group["match_id"].dropna().astype(str).unique())
        seasons = sorted(group["season"].dropna().astype(str).unique(), key=season_sort_key)
        records.append(
            {
                "canonical_player_id": clean_text(player_id),
                "canonical_player_name": clean_text(player_name),
                "display_player_name": display_or_blank(display_name),
                "premiership_count": len(unique_matches),
                "seasons": ", ".join(seasons),
                "grades": join_unique(group["grade_name"]),
                "teams": join_unique(group["fvcc_team_name"]),
                "latest_premiership_season": seasons[-1] if seasons else "",
                "evidence_match_ids": ", ".join(unique_matches),
                "confidence": combine_confidence(group.get("confidence", pd.Series(dtype=str))),
            }
        )

    output = pd.DataFrame(records)
    if output.empty:
        return empty_player_premierships()
    return output.sort_values(
        ["premiership_count", "latest_premiership_season", "display_player_name"],
        ascending=[False, False, True],
        key=lambda series: series.map(season_sort_key) if series.name == "latest_premiership_season" else series,
    )[PLAYER_PREMIERSHIPS_COLUMNS].reset_index(drop=True)


def build_player_premierships(players: pd.DataFrame, wins: pd.DataFrame) -> pd.DataFrame:
    if players.empty or wins.empty:
        return empty_player_premierships()

    valid_matches = set(wins["match_id"].astype(str))
    merged = players[players["match_id"].astype(str).isin(valid_matches)].copy()
    merged["club_team_name"] = merged.get("club_team_name", merged.get("fvcc_team_name", "")).map(clean_text)
    merged["display_player_name"] = merged["canonical_player_name"].map(display_or_blank)
    merged["season_sort"] = merged["season"].map(season_sort_key)

    records = []
    for player_name, group in merged.groupby("display_player_name", dropna=False):
        if not player_name:
            continue
        unique_matches = sorted(group["match_id"].dropna().astype(str).unique())
        seasons = sorted(group["season"].dropna().astype(str).unique(), key=season_sort_key)
        latest = seasons[-1] if seasons else ""
        records.append(
            {
                "canonical_player_id": "",
                "canonical_player_name": player_name,
                "display_player_name": player_name,
                "premiership_count": len(unique_matches),
                "seasons": ", ".join(seasons),
                "grades": join_unique(group["grade_name"]),
                "teams": join_unique(group.get("club_team_name", group["fvcc_team_name"])),
                "latest_premiership_season": latest,
                "evidence_match_ids": ", ".join(unique_matches),
                "confidence": combine_confidence(group.get("confidence", pd.Series(dtype=str))),
            }
        )

    output = pd.DataFrame(records)
    if output.empty:
        return empty_player_premierships()
    return output.sort_values(
        ["premiership_count", "latest_premiership_season", "display_player_name"],
        ascending=[False, False, True],
        key=lambda series: series.map(season_sort_key) if series.name == "latest_premiership_season" else series,
    ).reset_index(drop=True)


def validate_exports(wins: pd.DataFrame, players: pd.DataFrame) -> None:
    duplicate_matches = wins["match_id"][wins["match_id"].duplicated()].tolist() if "match_id" in wins else []
    if duplicate_matches:
        raise SystemExit(f"Duplicate premiership match rows: {duplicate_matches}")

    if not players.empty:
        for _, row in players.iterrows():
            match_ids = [part.strip() for part in str(row.get("evidence_match_ids", "")).split(",") if part.strip()]
            expected = len(set(match_ids))
            actual = int(row.get("premiership_count", 0))
            if actual != expected:
                raise SystemExit(f"Premiership count mismatch for {row.get('display_player_name')}: {actual} != {expected}")

    bad_urls = [
        url
        for url in wins.get("scoreboard_url", pd.Series(dtype=str)).dropna().astype(str)
        if url and not url.startswith("https://play.cricket.com.au/match/")
    ]
    if bad_urls:
        raise SystemExit(f"Unexpected scoreboard URL format: {bad_urls[:3]}")


def is_completed_match(row: pd.Series) -> bool:
    status = normalize_team_name(row.get("status"))
    if status and "complete" in status:
        return True
    status_id = clean_text(row.get("status_id"))
    return status_id in {"3", "completed"}


def selected_club_team(row: pd.Series, club_team_ids: set[str], club_tokens: set[str]) -> tuple[str, str, str]:
    home_id = clean_text(row.get("home_team_id"))
    away_id = clean_text(row.get("away_team_id"))
    home_name = clean_text(row.get("home_team_name"))
    away_name = clean_text(row.get("away_team_name"))
    source_ids = split_ids(row.get("source_team_ids"))
    selected_ids = source_ids or club_team_ids
    home_is_club = bool(home_id and home_id in selected_ids)
    away_is_club = bool(away_id and away_id in selected_ids)

    if not home_is_club and not away_is_club:
        home_key = normalize_team_name(home_name)
        away_key = normalize_team_name(away_name)
        home_is_club = bool(home_key and any(names_match(home_key, token) for token in club_tokens))
        away_is_club = bool(away_key and any(names_match(away_key, token) for token in club_tokens))

    if home_is_club and not away_is_club:
        return home_id, home_name, away_name
    if away_is_club and not home_is_club:
        return away_id, away_name, home_name
    return "", "", ""


def winner_name_from_result(result_text: object) -> str:
    match = re.match(r"^(?P<winner>.+?)\s+won(?:\s|$)", clean_text(result_text), flags=re.IGNORECASE)
    return clean_text(match.group("winner")) if match else ""


def club_name_tokens(club_id: str | None = None) -> set[str]:
    values = {get_club_name(club_id), get_club_short_name(club_id)}
    tokens: set[str] = set()
    for value in values:
        normalized = normalize_team_name(value)
        if normalized:
            tokens.add(normalized)
            tokens.add(re.sub(r"\b(cricket|club|cc)\b", "", normalized).strip())
    return {token for token in tokens if token}


def names_match(left: str, right: str) -> bool:
    if not left or not right:
        return False
    return left == right or left.startswith(f"{right} ") or right.startswith(f"{left} ")


def normalize_team_name(value: object) -> str:
    text = clean_text(value).casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\b(cricket club|cc)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_ids(value: object) -> set[str]:
    return {part.strip() for part in re.split(r"[|,]", clean_text(value)) if part.strip()}


def result_margin_display(row: pd.Series) -> str:
    result = clean_text(row.get("result_text"))
    team = clean_text(row.get("club_team_name") or row.get("fvcc_team_name"))
    if not result:
        return ""
    if team and result.casefold().startswith(team.casefold()):
        return result[len(team) :].strip().capitalize()
    match = re.search(r"\bwon\b(.*)$", result, flags=re.IGNORECASE)
    if match:
        suffix = match.group(0).strip()
        return suffix[0].upper() + suffix[1:] if suffix else ""
    return result


def playcricket_scorecard_url(match_id: object) -> str:
    match_id_text = clean_text(match_id)
    if not match_id_text:
        return ""
    return f"https://play.cricket.com.au/match/{match_id_text}?tab=scorecard"


def display_or_blank(value: object) -> str:
    text = clean_text(value)
    return display_player_name(text) if text else ""


def clean_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.casefold() in {"", "nan", "none", "nat"}:
        return ""
    return re.sub(r"\s+", " ", text)


def join_unique(values: pd.Series) -> str:
    labels = []
    for value in values.dropna().astype(str):
        text = clean_text(value)
        if text and text not in labels:
            labels.append(text)
    return ", ".join(labels)


def combine_confidence(values: pd.Series) -> str:
    labels = {clean_text(value).casefold() for value in values if clean_text(value)}
    if "low" in labels:
        return "low"
    if "medium" in labels:
        return "medium"
    return "high" if labels else ""


def season_sort_key(value: object) -> int:
    text = clean_text(value)
    years = [int(year) for year in re.findall(r"(?:19|20)\d{2}", text)]
    if not years:
        return 0
    return max(years)


if __name__ == "__main__":
    raise SystemExit(main())
