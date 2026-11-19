import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from src.data import prepared_customer_views as views


def test_prepared_sections_reject_moved_inputs_and_pin_accepted_bytes(tmp_path, monkeypatch):
    source = tmp_path / "privacy.csv"
    source.write_text("public")
    path = tmp_path / "sections.zip"
    monkeypatch.setattr(views, "archive_path", lambda club: path)
    monkeypatch.setattr(views, "generation", lambda club: (views.file_stamp(source),))
    monkeypatch.delenv("SCOREBOOK_IGNORE_PREPARED_HOF", raising=False)
    monkeypatch.delenv("FVCC_RUNTIME_IDENTITY_MAINTENANCE", raising=False)

    def write(club, value):
        manifest = {"schema":1, "club":club, "source_digest":views.content_digest(views.generation(club))}
        with ZipFile(path, "w") as archive:
            archive.writestr("manifest",json.dumps(manifest))
            archive.writestr("hof/search",json.dumps(value))

    write("fvcc", ["A public record"])
    first = views.load_views("fvcc")
    assert first and views.load_views("fvcc") is first
    assert views.load_views("glen-waverley-hawks") is None
    source.write_text("private")
    assert views.load_views("fvcc") is None
    write("fvcc", [])
    assert views.load_views("fvcc").read("hof/search") == []
    assert first.read("hof/search") == ["A public record"]
    monkeypatch.setenv("SCOREBOOK_IGNORE_PREPARED_HOF","1")
    assert views.load_views("fvcc") is None


def test_csv_offsets_include_quoted_lines_and_keep_id_selection(tmp_path):
    from scripts.prepare_profile_details import _offsets
    from src.data.profile_detail_index import read_ranges

    source = tmp_path/"records.csv"
    source.write_bytes(b'id,name,runs\r\nfirst,"A\nPlayer",0\r\nsecond,Same,18\r\nthird,Same,25\r\n')
    rows = _offsets(source)
    assert len(rows) == 3
    data = read_ranges(source,[rows[0],rows[2]],{"id":"object","name":"object","runs":"int64"})
    assert data.to_dict("records") == [{"id":"first","name":"A\nPlayer","runs":0},
                                        {"id":"third","name":"Same","runs":25}]


def test_peer_scope_uses_governed_population_on_overlap_or_missing_grade():
    from src.ui.layout import prepared_peer_scope_complete

    coverage = {"batting":{"public":[["2026","2026||First"]],"excluded":[["2026","2026||Second"]]},
                "bowling":{"public":[],"excluded":[]}}
    assert prepared_peer_scope_complete(coverage,("2025",),())
    assert prepared_peer_scope_complete(coverage,("2026",),("2026||First",))
    assert not prepared_peer_scope_complete(coverage,("2026",),())
    assert not prepared_peer_scope_complete(coverage,("2026",),("2026||Second",))
    assert not prepared_peer_scope_complete(coverage,("2026",),("2026||Missing",))


def test_profile_scope_failure_uses_governed_reader(monkeypatch):
    from src.data.profile_detail_index import indexed_profile
    from types import SimpleNamespace
    def unknown(key):
        raise KeyError(key)
    assert indexed_profile(SimpleNamespace(club="georges-river-district", read=unknown),"unlisted") is None
    assert indexed_profile(SimpleNamespace(club="fvcc", read=unknown),"unlisted") is None
    assert indexed_profile(SimpleNamespace(club="unknown"),"public") is None


def test_packed_table_reconstructs_complete_original_with_links_and_sort_metadata():
    import re
    from scripts.build_public_customer_views import pack_table

    cell = '<td class="runs" data-sort="0" data-missing="0">0</td>'
    link = '<td class="player"><a href="./?page=player-profile&amp;player=test">Test</a></td>'
    markup = '<table><thead></thead><tbody>' + ('<tr>'+link+cell+'</tr>')*100 + '</tbody></table>'
    wire = pack_table(markup)
    payload = re.search(r'<script type="application/json" id="scorebook-table-data">(.*?)</script>', wire, re.S)
    assert payload and len(wire.encode()) < len(markup.encode())
    head, columns, count, tail = json.loads(payload.group(1))
    rows = ["<tr>" + "".join(a + values[indices[i] if indices is not None else i] + b
                              for a,b,values,indices in columns) + "</tr>" for i in range(count)]
    assert head + "".join(rows) + tail == markup
