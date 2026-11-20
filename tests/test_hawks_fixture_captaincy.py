import json
from pathlib import Path

import pytest

from scripts.build_gwhcc_incremental_candidate import resolve_fixture_captain


FIXTURE = "4c03a077-e7d5-405c-a828-6f05f63cb093"
DECISION_PATH = (Path(__file__).resolve().parents[1]
                 / "clubs/glen-waverley-hawks/data/source/fixture_captaincy_decisions.json")


@pytest.fixture
def ambiguous_hawks_roster():
    return {
        "id": "5d2d88b2-5524-466f-9713-4c7f84a13d40",
        "players": [
            {"participantId": "cd62d17f-9d3c-41ec-a485-30df8c60016e",
             "name": "Aidan Griffin", "roles": ["Captain"]},
            {"participantId": "ac777130-399c-4a03-8533-dcc7c1d0017c",
             "name": "HARSHA KRISHNA MENDU", "roles": ["Captain"]},
        ],
    }


def test_owner_decision_resolves_exact_fixture_to_harsha(ambiguous_hawks_roster):
    decisions = json.loads(DECISION_PATH.read_text())
    assert set(decisions) == {FIXTURE}
    assert decisions[FIXTURE]["decision_date"] == "2026-11-20"
    assert resolve_fixture_captain(FIXTURE, [ambiguous_hawks_roster], decisions) == "Harsha Krishna Mendu"


def test_other_ambiguous_fixture_stays_unavailable(ambiguous_hawks_roster):
    decisions = json.loads(DECISION_PATH.read_text())
    assert resolve_fixture_captain("another-fixture", [ambiguous_hawks_roster], decisions) == ""


def test_approved_captain_must_be_on_exact_match_side(ambiguous_hawks_roster):
    decisions = json.loads(DECISION_PATH.read_text())
    with pytest.raises(ValueError, match="does not match the eligible Hawks side"):
        resolve_fixture_captain(FIXTURE, [{**ambiguous_hawks_roster, "id": "wrong-side"}], decisions)

    ambiguous_hawks_roster["players"].pop()
    with pytest.raises(ValueError, match="does not match one scorecard participant"):
        resolve_fixture_captain(FIXTURE, [ambiguous_hawks_roster], decisions)


def test_approved_captain_must_remain_public(ambiguous_hawks_roster):
    decisions = json.loads(DECISION_PATH.read_text())
    ambiguous_hawks_roster["players"][1]["name"] = "Private player"
    with pytest.raises(ValueError, match="does not resolve to the governed public identity"):
        resolve_fixture_captain(FIXTURE, [ambiguous_hawks_roster], decisions)
