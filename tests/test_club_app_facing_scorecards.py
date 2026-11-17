import pandas as pd
import pytest

from scripts.build_club_app_facing_scorecards import build_fielding_rows


@pytest.mark.parametrize(
    "club_id",
    ["georges-river-district", "glen-waverley-hawks", "fvcc"],
)
def test_scorecard_run_out_total_does_not_add_assisted_subset(club_id):
    source = pd.DataFrame(
        [
            {
                "match_id": "match-one",
                "team_id": "team-one",
                "participant_id": "11111111-1111-4111-8111-111111111111",
                "player_name": "Public Player",
                "catches": 1,
                "stumpings": 0,
                "run_outs": 2,
                "assisted_run_outs": 1,
            }
        ]
    )
    matches = pd.DataFrame(
        [{"match_id": "match-one", "season": "Summer 2026/27"}]
    )

    output = build_fielding_rows(
        source,
        matches,
        {"team-one"},
        club_id=club_id,
    )

    assert output.loc[0, "run_outs"] == 2
    assert output.loc[0, "catches"] == 1
