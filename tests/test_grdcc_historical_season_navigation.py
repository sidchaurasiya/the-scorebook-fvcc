from src.ui import layout


def test_governed_historical_seasons_are_selectable(monkeypatch):
    monkeypatch.setenv('CLUB_ID','georges-river-district')
    rows=layout.load_local_playcricket_seasons('georges-river-district',layout.metadata_mtime())
    names=[r['name'] for r in rows]
    assert names.count('Summer 1929/30')==1
    assert names.count('Summer 1971/72')==1
    assert names.count('Summer 1972/73')==1
    historic=next(r for r in rows if r['name']=='Summer 1929/30')
    teams=layout.load_local_playcricket_teams('georges-river-district',historic['id'],layout.metadata_mtime())
    assert teams and teams[0]['grade']['name']=='Historical club summary'
    frame=layout.load_local_category_frame('georges-river-district','batting',historic['id'],teams[0]['id'],layout.metadata_mtime())
    assert not frame.empty
    assert set(frame.season)=={'Summer 1929/30'}
    assert set(frame.source_system)=={'excel'}


def test_other_clubs_do_not_get_grdcc_navigation():
    for club in ('fvcc','glen-waverley-hawks'):
        assert layout.grdcc_historical_navigation_rows(club,0).empty
