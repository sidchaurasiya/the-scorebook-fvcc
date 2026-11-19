import pandas as pd

from src.analytics.playcricket_stats import combine_player_match_counts, combine_player_rows


def test_match_count_projection_keeps_name_precedence_and_fractional_weights():
    frame = pd.DataFrame({
        "player_name": ["Original spelling", "Alternate spelling", "Second player"],
        "canonical_player_id": ["one", "one", "two"],
        "canonical_player_name": ["Verified spelling", "Verified spelling", "Second player"],
        "matches": [0.5, 1, None],
        "battingInnings": [1, 2, 1],
        "battingNotOuts": [0, 1, 1],
    })
    for discipline in ("batting", "bowling", "fielding"):
        expected = combine_player_rows(frame, discipline)[["player_name", "matches"]]
        pd.testing.assert_frame_equal(combine_player_match_counts(frame), expected, check_dtype=False)
