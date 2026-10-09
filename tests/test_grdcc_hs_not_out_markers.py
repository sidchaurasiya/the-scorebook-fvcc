import html
import re

import pandas as pd
import pytest

from src.data.dismissal_status import is_not_out_values
from src.data.featured_record_overrides import apply_featured_record_overrides
from src.ui import layout


@pytest.mark.parametrize("value,expected", [
    ("177", "177"), (177, "177"), (177.0, "177"),
    ("110*", "110*"), ("130*", "130*"), ("0*", "0*"),
    (None, ""), (pd.NA, ""), (float("nan"), ""), ("", ""),
])
def test_hs_display_does_not_invent_a_not_out(value, expected):
    assert layout.format_high_score_text(value) == expected
    assert layout.hof_detail_display_value("HS", value) == expected


@pytest.mark.parametrize("dismissal,expected", [
    (None, True), (pd.NA, True), (float("nan"), True),
    ("bowled", False), ("caught", False), ("not out", True),
    ("retired hurt", True),
])
def test_supplied_scorecard_status_retains_provider_semantics(dismissal, expected):
    assert layout.parse_batting_score("130", dismissal) == (130, expected)


def test_blank_scorecard_provider_semantics_are_not_changed():
    assert is_not_out_values("") is True
    assert layout.parse_batting_score("130", "") == (130, True)
    assert layout.parse_batting_score("130") == (130, False)


@pytest.mark.parametrize("missing", [None, pd.NA, float("nan"), ""])
def test_nullable_scorecard_status_is_distinct_from_omitted_hs_metadata(missing):
    assert layout.parse_batting_score("130", missing) == (130, is_not_out_values(missing))
    assert layout.parse_batting_score("130") == (130, False)
    assert layout.format_high_score_text("130") == "130"


def test_unrelated_career_not_outs_do_not_mark_highest_score():
    row = pd.Series({"HS": "177", "Not Outs": 30, "Matches": 393})
    assert layout.hof_detail_display_value("HS", row.HS, row) == "177"
    assert row["Not Outs"] == 30


def test_tied_maximum_uses_only_qualifying_innings_not_out_status():
    rows = pd.DataFrame({"battingHighScore": [130, 130, 12],
                         "isBattingHSNotOut": [False, True, True]})
    assert layout.best_high_score(rows) == "130*"
    rows.loc[1, "isBattingHSNotOut"] = False
    assert layout.best_high_score(rows) == "130"


def test_governed_population_final_html_and_nick_anchor(monkeypatch):
    monkeypatch.setenv("CLUB_ID", "georges-river-district")
    core = pd.read_csv("clubs/georges-river-district/data/processed/hall_of_fame/prepared_career_all_time.csv")
    governed = apply_featured_record_overrides(core, "georges-river-district")
    before = governed.copy(deep=True)
    table = layout.format_all_time_batting_table(governed)
    markup = layout.hof_sortable_table_html(table, "hs_marker_invariant")
    cells = [html.unescape(cell) for cell in re.findall(r'<td class="hof-col-hs"[^>]*>(.*?)</td>', markup)]
    expected = []
    for value in table.HS:
        match = re.fullmatch(r"\s*(\d+)(?:\.0+)?(\*)?\s*", str(value))
        expected.append(f"{match[1]}{match[2] or ''}" if match else "-" if str(value) == "-" else "")
    assert cells == expected
    assert not all(cell.endswith("*") for cell in cells if cell)
    assert governed.loc[governed.Player.eq("Nick Condylios"), "HS"].iloc[0] == "130*"
    pd.testing.assert_frame_equal(governed, before)


def test_matches_proxy_marker_remains_independent(monkeypatch):
    monkeypatch.setenv("CLUB_ID", "georges-river-district")
    row = pd.Series({"Matches": 412, "Innings": 412, "Matches Proxy": True,
                     "Matches Source": "historical_innings_proxy", "HS": "110"})
    assert layout.hof_detail_display_value("Matches", 412, row) == "412*"
    assert layout.hof_detail_display_value("HS", "110", row) == "110"
