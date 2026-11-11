from __future__ import annotations

import pandas as pd

from scripts.build_hall_of_fame_core_exports import prepare_core_export_frames
from src.data.playcricket_ingestion import metadata_mtime
from src.ui import layout
from src.utils.player_identity import player_aliases_mtime


CLUB = "georges-river-district"


def test_prepared_hof_core_keeps_only_mark_burgess_approved_career_runs(monkeypatch):
    monkeypatch.setenv("CLUB_ID", CLUB)
    monkeypatch.setenv("SCOREBOOK_IGNORE_PREPARED_HOF", "1")
    if hasattr(layout, "_load_hall_of_fame_data_cached"):
        layout._load_hall_of_fame_data_cached.clear()
    historical = layout.load_hall_of_fame_data(
        metadata_mtime(),
        player_aliases_mtime(club_id=CLUB),
        layout.HALL_OF_FAME_DATA_VERSION,
        club_id=CLUB,
    )
    assert historical is not None
    monkeypatch.delenv("SCOREBOOK_IGNORE_PREPARED_HOF")
    frames = prepare_core_export_frames(CLUB, historical, layout)
    if hasattr(layout, "_load_hall_of_fame_data_cached"):
        layout._load_hall_of_fame_data_cached.clear()
    mark = frames["all_time"].loc[frames["all_time"].Player.eq("Mark Burgess")]
    assert len(mark) == 1
    row = mark.iloc[0]
    assert float(row["Runs"]) == 225
    for metric in ["Matches", "Wickets", "Catches", "Innings", "Not Outs", "HS", "Bat Avg", "Bowl Avg", "Econ"]:
        if metric in row:
            assert pd.isna(row[metric]), metric

    canonical_id = str(row["canonical_player_id"])
    for category in ["batting", "bowling", "fielding"]:
        rows = frames[category].loc[frames[category].canonical_player_id.astype(str).eq(canonical_id)]
        assert len(rows) <= 1
        if rows.empty:
            continue
        for metric in ["matches", "Runs", "Wickets", "Catches", "battingAggregate", "bowlingWickets", "fieldingTotalCatches"]:
            if metric in rows:
                assert pd.to_numeric(rows[metric], errors="coerce").isna().all(), (category, metric)
