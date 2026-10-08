from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import pytest

from src.data.featured_record_overrides import apply_featured_record_overrides
from src.ui import layout


FORMATTERS = [
    layout.format_all_time_batting_table,
    layout.format_all_time_bowling_table,
    layout.format_all_time_fielding_table,
]
MISSING_IDS = [None, float("nan"), pd.NA, "", "  ", "nan", "NaN", "None", "null", "NULL", "<NA>", "NaT"]


class PlayerCells(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.cells = []
        self.current = None
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "td" and "hof-col-player" in attrs.get("class", "").split():
            self.current = {"text": "", "hrefs": []}
        elif tag == "a" and self.current is not None:
            self.current["hrefs"].append(attrs.get("href", ""))

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data

    def handle_endtag(self, tag):
        if tag == "td" and self.current is not None:
            self.cells.append(self.current)
            self.current = None


@pytest.fixture(scope="module")
def governed():
    core = pd.read_csv("clubs/georges-river-district/data/processed/hall_of_fame/prepared_career_all_time.csv")
    return apply_featured_record_overrides(core, "georges-river-district")


@pytest.fixture(autouse=True)
def grdcc(monkeypatch):
    monkeypatch.setenv("CLUB_ID", "georges-river-district")


def render(frame, formatter):
    markup = layout.hof_sortable_table_html(formatter(frame), "prod_001")
    return markup, PlayerCells(markup).cells


@pytest.mark.parametrize("formatter", FORMATTERS)
def test_governed_report_only_records_in_actual_table(governed, formatter):
    before = governed.copy(deep=True)
    markup, cells = render(governed, formatter)
    by_name = {cell["text"]: cell for cell in cells}
    assert len(cells) == 2035
    for name in ["Warwick Geitz", "Ben Worger"]:
        assert governed.loc[governed.Player.eq(name), "canonical_player_id"].isna().all()
        assert by_name[name]["hrefs"] == []
    assert "player_id=nan" not in markup
    assert not governed.canonical_player_id.dropna().duplicated().any()
    pd.testing.assert_frame_equal(governed, before)


@pytest.mark.parametrize("formatter", FORMATTERS)
@pytest.mark.parametrize("missing_id", MISSING_IDS)
def test_missing_id_variants_are_escaped_plain_names(governed, formatter, missing_id):
    row = governed.loc[governed.Player.eq("Nick Condylios")].copy()
    row["canonical_player_id"] = pd.Series([missing_id], index=row.index, dtype=object)
    row["Player"] = "A & <Club>"
    markup, cells = render(row, formatter)
    assert cells == [{"text": "A & <Club>", "hrefs": []}]
    assert "A &amp; &lt;Club&gt;" in markup
    assert "page=player-profile" not in markup


@pytest.mark.parametrize("formatter", FORMATTERS)
@pytest.mark.parametrize("club_id", ["georges-river-district", "fvcc", "glen-waverley-hawks"])
def test_public_canonical_link_target_preserved(governed, formatter, club_id, monkeypatch):
    monkeypatch.setenv("CLUB_ID", club_id)
    row = governed.loc[governed.Player.eq("Nick Condylios")].copy()
    _, cells = render(row, formatter)
    assert cells[0]["text"] == "Nick Condylios"
    assert len(cells[0]["hrefs"]) == 1
    assert parse_qs(urlsplit(cells[0]["hrefs"][0]).query) == {
        "page": ["player-profile"],
        "player_id": [row.iloc[0].canonical_player_id],
    }


@pytest.mark.parametrize("formatter", FORMATTERS)
@pytest.mark.parametrize("name", ["Private player", "********", "Name withheld"])
def test_protected_names_never_gain_profile_links(governed, formatter, name):
    row = governed.loc[governed.Player.eq("Nick Condylios")].copy()
    row["Player"] = name
    row["canonical_player_id"] = "synthetic_protected_id"
    markup, cells = render(row, formatter)
    assert cells[0]["hrefs"] == []
    assert "synthetic_protected_id" not in markup
    assert "page=player-profile" not in markup
