from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pandas as pd
import pytest

from src.data.featured_record_overrides import apply_featured_record_overrides
from src.ui import layout


FORMATTERS = [
    (layout.format_all_time_batting_table, "Runs"),
    (layout.format_all_time_bowling_table, "Wickets"),
    (layout.format_all_time_fielding_table, "Catches"),
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


@pytest.mark.parametrize("formatter,metric", FORMATTERS)
def test_governed_report_only_records_in_actual_table(governed, formatter, metric):
    before = governed.copy(deep=True)
    markup, cells = render(governed, formatter)
    by_name = {cell["text"]: cell for cell in cells}
    eligible = layout.eligible_career_rows(governed, "georges-river-district")
    values = pd.to_numeric(eligible.get(metric, pd.Series(pd.NA, index=eligible.index)), errors="coerce")
    kind = eligible.get(layout.RECORD_KIND, pd.Series("", index=eligible.index)).fillna("").astype(str)
    scoped = kind.isin({"primary_historical", "annual_report_record"})
    incompatible = scoped & values.isna()
    if metric == "Wickets":
        incompatible |= kind.eq("primary_historical")
    assert len(cells) == int((~incompatible).sum())

    report_records = {
        "Warwick Geitz": ("report_grdcc_annual_2024_25_warwick_geitz", "Runs", 5119),
        "Ben Worger": ("report_grdcc_annual_2024_25_ben_worger", "Runs", 2312),
        "Phil Eldridge": ("report_grdcc_annual_2024_25_phil_eldridge", "Wickets", 227),
    }
    for name, (record_id, record_metric, value) in report_records.items():
        row = governed.loc[governed.Player.eq(name)]
        assert len(row) == 1 and pd.isna(row.iloc[0].canonical_player_id)
        if metric != record_metric:
            assert name not in by_name
            assert pd.isna(row.iloc[0][metric])
            continue
        assert name in by_name
        assert len(by_name[name]["hrefs"]) == 1
        assert parse_qs(urlsplit(by_name[name]["hrefs"][0]).query) == {
            "page": ["player-profile"],
            "player_id": [record_id],
        }
        assert pd.to_numeric(row.iloc[0][metric], errors="coerce") == value
    assert "player_id=nan" not in markup
    assert not governed.canonical_player_id.dropna().duplicated().any()
    pd.testing.assert_frame_equal(governed, before)


@pytest.mark.parametrize("formatter,metric", FORMATTERS)
@pytest.mark.parametrize("missing_id", MISSING_IDS)
def test_missing_id_variants_are_escaped_plain_names(governed, formatter, metric, missing_id):
    row = governed.loc[governed.Player.eq("Nick Condylios")].copy()
    row["canonical_player_id"] = pd.Series([missing_id], index=row.index, dtype=object)
    row["Player"] = "A & <Club>"
    markup, cells = render(row, formatter)
    assert cells == [{"text": "A & <Club>", "hrefs": []}]
    assert "A &amp; &lt;Club&gt;" in markup
    assert "page=player-profile" not in markup


@pytest.mark.parametrize("formatter,metric", FORMATTERS)
@pytest.mark.parametrize("club_id", ["georges-river-district", "fvcc", "glen-waverley-hawks"])
def test_public_canonical_link_target_preserved(governed, formatter, metric, club_id, monkeypatch):
    monkeypatch.setenv("CLUB_ID", club_id)
    row = governed.loc[governed.Player.eq("Nick Condylios")].copy()
    _, cells = render(row, formatter)
    assert cells[0]["text"] == "Nick Condylios"
    assert len(cells[0]["hrefs"]) == 1
    assert parse_qs(urlsplit(cells[0]["hrefs"][0]).query) == {
        "page": ["player-profile"],
        "player_id": [row.iloc[0].canonical_player_id],
    }


@pytest.mark.parametrize("formatter,metric", FORMATTERS)
@pytest.mark.parametrize("name", ["Private player", "********", "Name withheld"])
def test_protected_names_never_gain_profile_links(governed, formatter, metric, name):
    row = governed.loc[governed.Player.eq("Nick Condylios")].copy()
    row["Player"] = name
    row["canonical_player_id"] = "synthetic_protected_id"
    markup, cells = render(row, formatter)
    assert cells[0]["hrefs"] == []
    assert "synthetic_protected_id" not in markup
    assert "page=player-profile" not in markup
