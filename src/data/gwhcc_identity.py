"""Explicitly approved Hawks name variants for public search and continuity."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

from src.config.club_config import get_active_club_id, get_mapping_path

CLUB = "glen-waverley-hawks"
NAME_VARIANT_APPROVAL = "customer_confirmed_name_variant_disjoint_seasons"
EXACT_APPROVAL = "customer_approved_exact_disjoint_seasons"


@lru_cache(maxsize=8)
def _approved_variants(path: str, signature: tuple[int, int]) -> tuple[tuple[str, str, str], ...]:
    from src.utils.player_identity import is_private_or_anonymised_player

    _ = signature
    frame = pd.read_csv(path, dtype=str).fillna("")
    required = {"club", "canonical_player_id", "canonical_player_name", "source_name", "decision"}
    if not required.issubset(frame):
        return ()
    rows = frame[frame.club.eq(CLUB) & frame.decision.eq(NAME_VARIANT_APPROVAL)]
    return tuple(
        (row.canonical_player_id, row.canonical_player_name, row.source_name)
        for row in rows.itertuples()
        if row.canonical_player_id and row.canonical_player_name and row.source_name
        and not is_private_or_anonymised_player(row.canonical_player_name)
        and not is_private_or_anonymised_player(row.source_name)
    )


def approved_search_variants(club_id: str | None = None) -> tuple[tuple[str, str, str], ...]:
    if (club_id or get_active_club_id()) != CLUB:
        return ()
    path = Path(get_mapping_path("player_aliases.csv", club_id=CLUB)).parent / "data/source/disjoint_season_identity_decisions.csv"
    if not path.exists():
        return ()
    stat = path.stat()
    return _approved_variants(str(path), (stat.st_size, stat.st_mtime_ns))


def player_search_label(name: object, club_id: str | None = None) -> str:
    """Keep one canonical option, with documented nicknames available to search."""
    text = str(name)
    variants = sorted({
        alias for _, canonical, alias in approved_search_variants(club_id)
        if canonical.casefold() == text.casefold() and alias.casefold() != text.casefold()
    })
    return f"{text} ({', '.join(variants)})" if variants else text


def canonical_query_name(name: str, club_id: str | None = None) -> str:
    matches = {canonical for _, canonical, alias in approved_search_variants(club_id)
               if alias.casefold() == name.casefold()}
    return next(iter(matches)) if len(matches) == 1 else name
