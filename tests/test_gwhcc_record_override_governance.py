from __future__ import annotations

import pandas as pd

from src.data import gwhcc_document_overrides as overrides


def apply_override_rows(monkeypatch, rows: list[dict[str, object]], source: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            **row,
            "metric_key": str(row.get("metric", "")).strip().casefold().replace("games", "matches"),
        }
        for row in rows
    ]
    monkeypatch.setattr(overrides, "load_record_overrides", lambda: pd.DataFrame(rows))
    monkeypatch.setattr(overrides, "apply_historical_career_supplements", lambda frame: frame)
    monkeypatch.setattr(overrides, "apply_historical_career_metric_decisions", lambda frame: frame)
    return overrides.apply_record_overrides(source, write_decisions=False)


def test_record_confidence_allowlist_preserves_review_and_rejected_rows(monkeypatch) -> None:
    source = pd.DataFrame(
        [
            {"Player": "Glen Mahoney", "Runs": 7734, "Wickets": 120, "Catches": 180},
            {"Player": "Confirmed Player", "Runs": 100, "Wickets": 2, "Catches": 1},
            {"Player": "Customer Career Player", "Matches": 10, "Runs": 50, "Wickets": 1},
            {"Player": "Rejected Player", "Catches": 4},
        ]
    )
    rows = [
        {
            "player_name": "G. Mahoney",
            "metric": "runs",
            "document_value": 11040,
            "confidence": "review",
            "_override_source": "record_overrides",
        },
        {
            "player_name": "Confirmed Player",
            "metric": "wickets",
            "document_value": 5,
            "confidence": "confirmed",
            "_override_source": "record_overrides",
        },
        {
            "player_name": "Customer Career Player",
            "metric": "matches",
            "document_value": 20,
            "confidence": "high",
            "_override_source": "customer_career_overrides",
        },
        {
            "player_name": "Rejected Player",
            "metric": "catches",
            "document_value": 10,
            "confidence": "rejected",
            "_override_source": "record_overrides",
        },
    ]

    result = apply_override_rows(monkeypatch, rows, source)

    assert result.loc[result["Player"].eq("Glen Mahoney"), "Runs"].iloc[0] == 7734
    assert result.loc[result["Player"].eq("Confirmed Player"), "Wickets"].iloc[0] == 5
    assert result.loc[result["Player"].eq("Customer Career Player"), "Matches"].iloc[0] == 20
    assert result.loc[result["Player"].eq("Rejected Player"), "Catches"].iloc[0] == 4


def test_multiple_metrics_are_governed_independently_and_missing_players_stay_unchanged(monkeypatch) -> None:
    source = pd.DataFrame([{"Player": "Glen Mahoney", "Runs": 7734, "Wickets": 120}])
    rows = [
        {
            "player_name": "G. Mahoney",
            "metric": "runs",
            "document_value": 11040,
            "confidence": "review",
            "_override_source": "record_overrides",
        },
        {
            "player_name": "G. Mahoney",
            "metric": "wickets",
            "document_value": 125,
            "confidence": "approved",
            "_override_source": "record_overrides",
        },
        {
            "player_name": "Absent Player",
            "metric": "runs",
            "document_value": 999,
            "confidence": "confirmed",
            "_override_source": "record_overrides",
        },
    ]

    result = apply_override_rows(monkeypatch, rows, source)

    assert result.iloc[0]["Runs"] == 7734
    assert result.iloc[0]["Wickets"] == 125
    assert len(result) == 1


def test_approved_fb17c_metric_source_remains_separate_from_record_governance(monkeypatch) -> None:
    source = pd.DataFrame(
        [
            {
                "Player": "Historical Player",
                "Runs": 100,
                "Wickets": 2,
                "historical_career_metrics_applied": True,
            }
        ]
    )
    result = apply_override_rows(monkeypatch, [], source)
    assert result.equals(source)


def test_record_override_eligibility_uses_source_aware_allowlist() -> None:
    assert overrides.is_production_approved_record_override(
        pd.Series({"confidence": "confirmed", "_override_source": "record_overrides"})
    )
    assert overrides.is_production_approved_record_override(
        pd.Series({"confidence": "approved", "_override_source": "record_overrides"})
    )
    assert not overrides.is_production_approved_record_override(
        pd.Series({"confidence": "review", "_override_source": "record_overrides"})
    )
    assert not overrides.is_production_approved_record_override(
        pd.Series({"confidence": "rejected", "_override_source": "record_overrides"})
    )
    assert overrides.is_production_approved_record_override(
        pd.Series({"confidence": "high", "_override_source": "customer_career_overrides"})
    )


def test_empty_override_sources_still_return_a_valid_audit_frame(monkeypatch) -> None:
    monkeypatch.setattr(overrides, "write_empty_source_files", lambda: None)
    monkeypatch.setattr(overrides, "read_csv", lambda _path: pd.DataFrame(columns=overrides.RECORD_COLUMNS))

    result = overrides.load_record_overrides()

    assert result.empty
    assert set(overrides.RECORD_COLUMNS + ["metric_key", "_override_source"]).issubset(result.columns)
