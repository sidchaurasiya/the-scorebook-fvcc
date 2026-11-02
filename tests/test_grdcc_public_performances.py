import pandas as pd
import pytest

from src.data.grdcc_public_performances import (
    CLUB, PublicAggregateReconciliationRequired, public_performance_frames, public_season_aggregate,
)


def rows():
    return pd.DataFrame([
        {"match_id":"m1","team_id":"t","participant_id":"p","player_name":"********","runs":13},
        {"match_id":"m2","team_id":"t","participant_id":"p","player_name":"Synthetic Player","runs":10},
    ])


def aggregate():
    return pd.DataFrame([{"team_id":"t","player_id":"p","player_name":"Synthetic Player","runs":13,"season":"Summer 2026/27"}])


def test_mixed_matches_keep_only_public_performance_without_rekeying():
    raw=rows(); public, protected=public_performance_frames({"batting":raw},club_id=CLUB)
    assert public["batting"].runs.sum()==10 and len(protected)==1
    assert public["batting"].participant_id.tolist()==["p"]
    assert raw.runs.sum()==23


def test_mask_propagates_across_disciplines_of_same_performance():
    raw=rows().iloc[:1]; other=raw.assign(player_name="Synthetic Player")
    public,_=public_performance_frames({"batting":raw,"fielding":other},club_id=CLUB)
    assert all(f.empty for f in public.values())


def test_named_aggregate_does_not_unmask_a_protected_performance():
    raw=aggregate(); out=public_season_aggregate(raw,{"batting":rows().iloc[:1]},club_id=CLUB)
    assert out.empty and raw.runs.sum()==13


def test_historical_public_profile_is_preserved_separately():
    old=aggregate().assign(season="Summer 2025/26",runs=100)
    current=public_season_aggregate(aggregate(),{"batting":rows().iloc[:1]},club_id=CLUB)
    assert pd.concat([old,current]).runs.sum()==100


def test_public_transition_does_not_restore_old_masked_performance():
    public,_=public_performance_frames({"batting":rows()},club_id=CLUB)
    assert public["batting"].match_id.tolist()==["m2"]


def test_mixed_aggregate_requires_public_reducer_not_naive_subtraction():
    with pytest.raises(PublicAggregateReconciliationRequired):
        public_season_aggregate(aggregate(),{"batting":rows()},club_id=CLUB)


@pytest.mark.parametrize("club",["fvcc","glen-waverley-hawks"])
def test_other_clubs_unchanged(club):
    raw=rows(); public,protected=public_performance_frames({"batting":raw},club_id=club)
    pd.testing.assert_frame_equal(raw,public["batting"])
    pd.testing.assert_frame_equal(aggregate(),public_season_aggregate(aggregate(),{"batting":raw},club_id=club))
    assert not protected


def test_missing_identity_fails_closed():
    with pytest.raises(ValueError):
        public_performance_frames({"batting":rows().assign(participant_id=None)},club_id=CLUB)


def test_history_cannot_be_accidentally_projected_as_current():
    with pytest.raises(ValueError):
        public_season_aggregate(pd.concat([aggregate(),aggregate().assign(season="Summer 2025/26")]),{"batting":rows().iloc[:1]},club_id=CLUB)
