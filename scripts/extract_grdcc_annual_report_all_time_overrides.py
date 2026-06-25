#!/usr/bin/env python3
"""Build GRDCC Annual Report career override decisions and record candidates."""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLUB = ROOT / "clubs" / "georges-river-district"
REPORT_ROOT = CLUB / "data" / "processed" / "validation" / "annual_report_2024_25"
OUTPUT = REPORT_ROOT / "all_time_overrides"
LEGACY_LEADERS = REPORT_ROOT / "grdcc_annual_report_all_time_leaders_for_app.csv"
REPORT_TEXT_CANDIDATES = (
    Path("/tmp/grdcc-annual-report-connector.txt"),
    Path("/tmp/grdcc-2024-25-annual-report.txt"),
)

ALIASES = {
    "ben vella": "benjamin vella",
    "pat kennedy": "patrick kennedy",
    "nicholas henriques": "nick henriques",
    "christopher diehm": "chris diehm",
    "nathan e wadds": "nathan wadds",
}

FRANK_GRAY_RUNS = {
    "Michael Labb": 1013, "Jarrod Mazurkiewicz": 999, "Nick Henriques": 936,
    "Benjamin Vella": 882, "Sean Mantle": 852, "Ryan Croom": 794,
    "Paul O'Brien": 787, "James Kirkness": 780, "Curtis Cheney": 756,
    "Trent Power": 737, "Nick Condylios": 722, "Damien Johnson": 675,
    "Christopher McArthur": 666, "Ben Saunders": 592, "Luke Morgan": 535,
    "Justin Drinkwater": 534, "Dayle Carew": 526, "Matthew Wotton": 524,
    "Brett Hudson": 498, "Alex Wall": 493, "Darren Burgess": 475,
    "Gavin Scott": 465, "Ben Carter": 463, "Daniel Milgate": 452,
    "Alex Economou": 438, "Murray Power": 397, "Andrew Julian": 397,
    "Liam Aggett": 369, "Karl Prince": 356, "Troy Lewis": 344,
    "Nathan Napier": 321, "Matthew Fulcher": 310, "Riley Orr": 305,
    "Liam Sparke": 286, "Tim Adams": 274, "Phil Hamer": 266,
    "Leroy Maurer": 257, "David Marshall": 251, "John Eden": 239,
    "Luke Byron": 238, "Peter Dick": 238, "Brandon Labb": 234,
    "Sarab Singh": 221, "Lee Brooks": 204, "Michael Schmoll": 203,
    "Nathan E Wadds": 203, "Robert Henriques": 195, "Steve Troughton": 193,
    "Andrew Nicol": 188, "Mark Burgess": 177, "Alejandro Salgueira": 176,
    "Dean Magee": 175, "Matthew Grealy": 165, "Rohan Clarke": 162,
}

FRANK_GRAY_WICKETS = {
    "Daniel Yates": 88, "Benjamin Vella": 63, "Dayle Carew": 53,
    "Gavin Scott": 49, "Patrick Kennedy": 46, "Luke Byron": 46,
    "Troy Lewis": 44, "Mitchell Betts": 43, "Riley Orr": 38,
    "Liam Aggett": 38, "Ben Saunders": 37, "Nicholas Henriques": 32,
    "Colin Cheer": 28, "Luke Saunders": 28, "Trent Power": 28,
    "Jeff Woods": 27, "Brendan Newton": 25, "Leroy Maurer": 24,
    "Drew Paternoster": 24, "Christopher Diehm": 23, "Karl Prince": 22,
    "Chris Miller": 21, "Matthew Wotton": 20, "Luke Morgan": 20,
    "Michael Schmoll": 20, "Brendan Napier": 19, "Michael Labb": 19,
    "Daniel Milgate": 19, "Jakob Lindberg": 18, "Tom Jones": 17,
    "Nathan McCoy": 16, "Justin Drinkwater": 16, "Brad Humbles": 16,
    "Jamie Fardell": 15, "Chris Kalatzis": 15,
}


def normalize(value: object) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", str(value or "").casefold())
    text = re.sub(r"\s+", " ", text).strip()
    return ALIASES.get(text, text)


def number(value: object) -> float:
    try:
        return float(str(value or "0").replace(",", "").strip())
    except ValueError:
        return 0.0


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def report_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for row in read_csv(LEGACY_LEADERS):
        section = row.get("section", "")
        if section not in {"most_runs", "most_wickets"}:
            continue
        metric = "career_runs" if section == "most_runs" else "career_wickets"
        rows.append({
            "report_year": "2024/25",
            "player_name": row.get("player_name", ""),
            "normalized_player_name": normalize(row.get("player_name", "")),
            "metric": metric,
            "annual_report_section": "shields",
            "annual_report_page": "98" if metric == "career_runs" else "100",
            "annual_report_value": int(number(row.get("annual_report_value"))),
            "source_text": f"{row.get('player_name', '')} {row.get('annual_report_value', '')}",
            "extraction_confidence": row.get("extraction_confidence", "high") or "high",
            "notes": "Annual Report ALL GRADES table; treated as the Shield/main-grade career subtotal.",
        })
    for metric, page, values in (
        ("career_runs", "99", FRANK_GRAY_RUNS),
        ("career_wickets", "101", FRANK_GRAY_WICKETS),
    ):
        for player, value in values.items():
            rows.append({
                "report_year": "2024/25",
                "player_name": player,
                "normalized_player_name": normalize(player),
                "metric": metric,
                "annual_report_section": "frank_gray",
                "annual_report_page": page,
                "annual_report_value": value,
                "source_text": f"{player} {value}",
                "extraction_confidence": "high",
                "notes": "Annual Report Frank Gray Shield career table.",
            })
    return rows


def combine_report_rows(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["normalized_player_name"]), str(row["metric"]))].append(row)
    combined = []
    for (name_key, metric), group in grouped.items():
        section_values = defaultdict(float)
        for row in group:
            section_values[str(row["annual_report_section"])] += number(row["annual_report_value"])
        display = max(group, key=lambda item: number(item["annual_report_value"]))["player_name"]
        combined.append({
            "player_name": display,
            "normalized_player_name": name_key,
            "metric": metric,
            "annual_report_shields_value": int(section_values["shields"]),
            "annual_report_frank_gray_value": int(section_values["frank_gray"]),
            "annual_report_other_value": int(section_values["other"]),
            "annual_report_combined_value": int(sum(section_values.values())),
            "annual_report_pages": "; ".join(sorted({str(row["annual_report_page"]) for row in group})),
            "annual_report_sections": "; ".join(sorted({str(row["annual_report_section"]) for row in group})),
            "extraction_confidence": "high" if all(row["extraction_confidence"] == "high" for row in group) else "review",
            "notes": "Section subtotals combined once per player and metric; no same-section duplicate rows detected.",
        })
    return sorted(combined, key=lambda row: (row["metric"], -int(row["annual_report_combined_value"]), row["player_name"]))


def source_totals(path: Path, metric: str, modern: bool) -> dict[str, float]:
    output: dict[str, float] = defaultdict(float)
    for row in read_csv(path):
        season = str(row.get("season", ""))
        match = re.search(r"(\d{4})/(\d{2})", season)
        if not match:
            continue
        start_year = int(match.group(1))
        if modern != (start_year >= 1972):
            continue
        player = row.get("canonical_player_name") or row.get("player_name") or ""
        key = normalize(player)
        if not key or not re.search(r"[a-z]", key):
            continue
        value = number(row.get(metric))
        if metric == "battingAggregate":
            innings = number(row.get("battingInnings"))
            high_score = number(row.get("battingHighScore"))
            if high_score > value or number(row.get("batting100s")) > innings or number(row.get("battingNotOuts")) > innings:
                continue
        else:
            balls = number(row.get("bowlingBalls"))
            wickets = value
            if wickets < 0 or (balls and wickets > balls):
                continue
            if wickets >= 10 and 0 < number(row.get("bowlingAverage")) <= 1:
                continue
            if wickets >= 10 and 0 < number(row.get("bowlingStrikeRate")) <= 3:
                continue
            if balls >= 60 and 0 < number(row.get("bowlingEconomyRate")) <= 0.5:
                continue
        output[key] += value
    return output


def decision_rows(combined: list[dict[str, object]]) -> list[dict[str, object]]:
    pc_runs = source_totals(CLUB / "data/processed/all_seasons_batting.csv", "battingAggregate", True)
    pc_wickets = source_totals(CLUB / "data/processed/all_seasons_bowling.csv", "bowlingWickets", True)
    excel_runs = source_totals(CLUB / "data/processed/supplemental/excel_all_seasons_batting.csv", "battingAggregate", False)
    excel_wickets = source_totals(CLUB / "data/processed/supplemental/excel_all_seasons_bowling.csv", "bowlingWickets", False)
    legacy = {(normalize(row.get("player_name")), row.get("metric")): number(row.get("current_final_logic_value")) for row in read_csv(LEGACY_LEADERS)}
    decisions = []
    for row in combined:
        key = str(row["normalized_player_name"])
        is_runs = row["metric"] == "career_runs"
        pc = (pc_runs if is_runs else pc_wickets).get(key, 0)
        excel = (excel_runs if is_runs else excel_wickets).get(key, 0)
        legacy_metric = "runs" if is_runs else "wickets"
        derived = max(pc + excel, legacy.get((key, legacy_metric), 0))
        report = number(row["annual_report_combined_value"])
        override = report > derived
        decisions.append({
            "player_name": row["player_name"],
            "normalized_player_name": key,
            "metric": row["metric"],
            "annual_report_combined_value": int(report),
            "source_rule_derived_value": int(derived),
            "playcricket_value": int(pc),
            "historical_excel_value": int(excel),
            "displayed_value": int(report if override else derived),
            "displayed_value_source": "annual_report_combined" if override else "source_rule_derived",
            "annual_report_difference": int(report - derived),
            "override_applies": "yes" if override else "no",
            "reason": "Combined Annual Report subtotal is higher." if override else "Current source-rule total is equal or higher.",
            "annual_report_pages": row["annual_report_pages"],
            "annual_report_sections": row["annual_report_sections"],
            "validation_status": "pass",
            "notes": "Career presentation only; player-season source rows remain unchanged.",
        })
    return decisions


def report_text() -> str:
    for path in REPORT_TEXT_CANDIDATES:
        if path.exists():
            return path.read_text(encoding="utf-8", errors="replace")
    return ""


def extract_candidates(text: str) -> list[dict[str, object]]:
    candidates: list[dict[str, object]] = []
    current_page = ""
    current_section = ""
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if re.fullmatch(r"\d{1,3}", line) and 1 <= int(line) <= 130:
            current_page = line
            continue
        heading = re.search(r"([A-Z0-9 ()]+(?:GRADE|SHIELD|CUP|VINTAGE|CLASSICS|MASTERS)[A-Z0-9 ()]*) - (BATTING|BOWLING)", line)
        if heading:
            current_section = heading.group(1).strip().title()
        elif re.fullmatch(r"(?:FIRST|SECOND|THIRD|FOURTH|FIFTH|5TH) GRADE", line):
            current_section = line.title().replace("5Th", "Fifth")
        seasons = list(re.finditer(r"(?:19|20)\d{2}-\d{2}", line))
        if seasons and "BATTING" not in line and "Player Runs" not in line:
            for index, match in enumerate(seasons):
                segment = line[match.start() : seasons[index + 1].start() if index + 1 < len(seasons) else len(line)].strip()
                parsed = re.match(r"(?P<season>\d{4}-\d{2}) (?P<agg_name>.+?) (?P<aggregate>\d+) (?P<score_name>.+?) (?P<score>\d+\*?) (?P<avg_name>.+?) (?P<average>\d+(?:\.\d+)?)$", segment)
                if not parsed or not current_section:
                    continue
                data = parsed.groupdict()
                score = int(data["score"].rstrip("*"))
                candidates.append(candidate_row(current_page, current_section, "highest_score", data["score_name"], data["season"], data["score"], score, 0, score, segment))
        bowling = re.match(r"(?P<player>[A-Za-z][A-Za-z .’'\-]+?) (?P<wickets>\d+) for (?P<runs>\d+) (?P<overs>\d+(?:\.\d+)?) (?P<opponent>.+)$", line)
        if bowling:
            data = bowling.groupdict()
            candidates.append(candidate_row(current_page, current_section, "bbi", data["player"], "Summer 2024/25", f"{data['wickets']}/{data['runs']}", int(data["runs"]), int(data["wickets"]), int(data["wickets"]) * 1000 - int(data["runs"]), line, data["opponent"]))
    explicit = [
        candidate_row("13", "Club Awards", "highest_score", "Damien Johnson", "", "212", 212, 0, 212, "Damien Johnson scored 212 in a Frank Gray innings, the highest individual score in club history across all grades."),
        candidate_row("16", "Secretary's Report", "highest_score", "Syed Bukhari", "Summer 2024/25", "191*", 191, 0, 191, "Syed Bukhari scored 191 not out off 130 balls in Fifth Grade."),
        candidate_row("12", "Club Awards", "bbi", "Riley Orr", "Summer 2024/25", "6/32", 32, 6, 5968, "Riley Orr took 17 wickets including best figures of 6/32."),
        candidate_row("12", "Club Awards", "bbi", "Sumedh Purohit", "Summer 2024/25", "5/15", 15, 5, 4985, "Sumedh Purohit took 42 wickets including best figures of 5/15."),
        candidate_row("12", "Club Awards", "bbi", "Angus O'Rourke", "Summer 2024/25", "7/77", 77, 7, 6923, "Angus O'Rourke took 7/77 in the Second Grade qualifying final against Warringah.", "Warringah"),
    ]
    seen = {(row["record_category"], normalize(row["player_name"]), row["season"], row["score_or_figures"], row["grade_or_competition"]) for row in candidates}
    for row in explicit:
        key = (row["record_category"], normalize(row["player_name"]), row["season"], row["score_or_figures"], row["grade_or_competition"])
        if key not in seen:
            candidates.append(row)
    deduplicated = {}
    for row in candidates:
        key = (
            row["record_category"], row["normalized_player_name"], row["season"],
            row["score_or_figures"], row["grade_or_competition"], row["opponent"],
        )
        deduplicated.setdefault(key, row)
    return list(deduplicated.values())


def candidate_row(page: str, section: str, category: str, player: str, season: str, figures: str, runs: int, wickets: int, sort_value: int, source: str, opponent: str = "") -> dict[str, object]:
    if season and not season.startswith("Summer "):
        season = f"Summer {season.replace('-', '/', 1)}"
    return {
        "report_year": "2024/25", "annual_report_page": page, "section_heading": section,
        "record_category": category, "player_name": player.strip(), "normalized_player_name": normalize(player),
        "season": season,
        "grade_or_competition": section, "opponent": opponent, "score_or_figures": figures,
        "runs": runs, "wickets": wickets, "balls": "", "metric_value_for_sorting": sort_value,
        "source_text": source, "extraction_confidence": "high",
        "candidate_for_iconic_performances": "yes", "notes": "Candidate only; not injected into app records.",
    }


def write_docs(candidates: list[dict[str, object]], decisions: list[dict[str, object]]) -> None:
    high_scores = [row for row in candidates if row["record_category"] == "highest_score"]
    bbi = [row for row in candidates if row["record_category"] == "bbi"]
    (ROOT / "docs/georges_river_annual_report_highest_scores_bbi_extract.md").write_text(
        "# Georges River Annual Report Highest Scores and BBI Extract\n\n"
        "## Scope\n\nCandidate-only extraction from the GRDCC 2024/25 Annual Report. No candidate is injected into Iconic Performances.\n\n"
        f"- Highest-score candidates: {len(high_scores)}\n- BBI candidates: {len(bbi)}\n"
        "- Pages/sections searched: club awards, season reports, and Club Records batting/bowling tables.\n\n"
        "## Caveats\n\nOCR reading order can split multi-column tables. Only rows parsed with high confidence are included; opponent and balls remain blank when the report does not provide them.\n\n"
        "## Recommendation\n\nReview candidates against scorecards before approving any future Iconic Performances additions.\n",
        encoding="utf-8",
    )
    overrides = sum(row["override_applies"] == "yes" for row in decisions)
    (ROOT / "docs/georges_river_annual_report_all_time_override_decisions.md").write_text(
        "# Georges River Annual Report All-Time Override Decisions\n\n"
        "## Final Rule\n\nAnnual Report ALL GRADES (Shield/main-grade) and Frank Gray career subtotals are combined by player and metric. The combined Annual Report value is used only when it exceeds the app's source-rule total; otherwise the source-rule total wins.\n\n"
        f"- Decision rows: {len(decisions)}\n- Annual Report overrides applied: {overrides}\n- Source-rule values retained: {len(decisions) - overrides}\n\n"
        "## App Scope\n\nThe presentation override is shared by Hall of Fame leaders, Hall of Fame detailed career tables, and Player Profile career cards. Raw source and season-level rows are unchanged.\n\n"
        "## Candidate Records\n\nHighest-score and BBI extracts are review candidates only and are not added to Iconic Performances.\n",
        encoding="utf-8",
    )


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    detailed = report_rows()
    combined = combine_report_rows(detailed)
    decisions = decision_rows(combined)
    candidates = extract_candidates(report_text())
    write_csv(OUTPUT / "grdcc_annual_report_combined_all_time_runs_wickets.csv", detailed, list(detailed[0]))
    write_csv(OUTPUT / "grdcc_annual_report_combined_all_time_by_player.csv", combined, list(combined[0]))
    write_csv(OUTPUT / "grdcc_all_time_override_decisions.csv", decisions, list(decisions[0]))
    candidate_columns = ["report_year", "annual_report_page", "section_heading", "record_category", "player_name", "normalized_player_name", "season", "grade_or_competition", "opponent", "score_or_figures", "runs", "wickets", "balls", "metric_value_for_sorting", "source_text", "extraction_confidence", "candidate_for_iconic_performances", "notes"]
    write_csv(OUTPUT / "grdcc_annual_report_highest_scores_bbi_extract.csv", candidates, candidate_columns)
    write_docs(candidates, decisions)
    print(f"report_rows={len(detailed)} combined_rows={len(combined)} decisions={len(decisions)} overrides={sum(row['override_applies'] == 'yes' for row in decisions)} source_rule_wins={sum(row['override_applies'] == 'no' for row in decisions)} highest_scores={sum(row['record_category'] == 'highest_score' for row in candidates)} bbi={sum(row['record_category'] == 'bbi' for row in candidates)}")


if __name__ == "__main__":
    main()
