from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.risk_state.models import InvestigationCase
from src.risk_state.provider import FrozenCaseProvider, UnsupportedCaseError


def _raw_case(**risk_updates):
    risk = {
        "schema_version": "risk-state-v1",
        "as_of_date": "2026-05-29",
        "assessment_cutoff": "2026-05-29T16:00:00-04:00",
        "comparison_date": "2026-04-30",
        "market_regime": "normal",
        "mechanical_unwind_state": "FRAGILITY_BUILDING",
        "total_signal_count": 4,
        "triggered_signals": [],
        "structural_flags": ["portfolio_concentration"],
        "mechanisms": {
            "bear_market_recovery_crash": "watch",
            "crowded_theme_unwind": "triggered",
            "short_book_reversal_crash": "not_confirmed",
        },
        "book": {
            "portfolio_drawdown": -0.07522682931760427,
            "short_loss_in_recovery": 0.15507930926767552,
            "long_beta_126d": 2.572822625616927,
            "short_underlying_beta_126d": 0.5050908492797432,
        },
        "theme_cluster": ["CIEN", "COHR", "LITE"],
        "severity": {
            "score": 96,
            "label": "high",
            "primary_driver": "crowded_unwind",
            "mechanism_scores": {
                "book_vulnerability": 56,
                "crowded_unwind": 96,
                "dm_recovery": 45,
                "fundamental_repricing": None,
            },
            "score_is_probability": False,
        },
    }
    risk.update(risk_updates)
    return {
        "schema_version": "investigation-case-v1",
        "provenance": {
            "source_repository": "momentum-tail-risk-monitor",
            "source_commit": "9ff0aff",
            "run_fingerprint": "fixture-fingerprint",
        },
        "risk_state": risk,
        "prior_state": None,
        "evidence": [],
        "holdings": [],
    }


def test_provider_loads_exact_supported_cases() -> None:
    provider = FrozenCaseProvider()

    may = provider.load("2026-05-29")
    quiet = provider.load("2024-01-05")
    march = provider.load("2020-03-24")

    assert provider.supported_dates == ("2020-03-24", "2024-01-05", "2026-05-29")
    assert may.risk_state.monitoring_trigger_count == 0
    assert may.risk_state.triggered_mechanisms == ("crowded_theme_unwind",)
    assert may.risk_state.theme_cluster == ("CIEN", "COHR", "LITE")
    assert may.risk_state.severity.score == 96
    assert quiet.risk_state.mechanical_unwind_state == "NORMAL"
    assert quiet.risk_state.triggered_mechanisms == ()
    assert quiet.risk_state.severity.primary_driver == "crowded_unwind"
    assert march.risk_state.monitoring_trigger_count == 3
    assert march.risk_state.triggered_mechanisms == ("bear_market_recovery_crash",)
    assert march.risk_state.severity.score == 100


def test_provider_rejects_unsupported_date_with_supported_values() -> None:
    provider = FrozenCaseProvider()

    with pytest.raises(UnsupportedCaseError) as exc_info:
        provider.load("2026-06-30")

    message = str(exc_info.value)
    assert "2026-06-30" in message
    assert "2026-05-29" in message
    assert "2024-01-05" in message
    assert "2020-03-24" in message


def test_risk_state_and_nested_values_are_immutable() -> None:
    case = InvestigationCase.model_validate(_raw_case())

    with pytest.raises(ValidationError):
        case.risk_state.market_regime = "panic_elevated"
    with pytest.raises(ValidationError):
        case.risk_state.book.portfolio_drawdown = -1.0
    with pytest.raises(ValidationError):
        case.risk_state.severity.score = 12


@pytest.mark.parametrize(
    "updates",
    [
        {"assessment_cutoff": "2026-05-29T15:59:00-04:00"},
        {"assessment_cutoff": "2026-05-30T16:00:00-04:00"},
        {"assessment_cutoff": "2026-05-29T16:00:00-05:00"},
        {"total_signal_count": 1, "triggered_signals": ["a", "b"]},
        {"score_is_probability": True},
    ],
)
def test_risk_state_rejects_invalid_safety_contracts(updates) -> None:
    raw = _raw_case()
    if "score_is_probability" in updates:
        raw["risk_state"]["severity"]["score_is_probability"] = updates.pop(
            "score_is_probability"
        )
    raw["risk_state"].update(updates)

    with pytest.raises(ValidationError):
        InvestigationCase.model_validate(raw)


def test_case_rejects_unknown_fields() -> None:
    raw = _raw_case()
    raw["risk_state"]["legacy_pm_narrative"] = "should not cross the boundary"

    with pytest.raises(ValidationError):
        InvestigationCase.model_validate(raw)


def test_provider_fails_closed_on_malformed_case_file(tmp_path: Path) -> None:
    case_dir = tmp_path / "2026-05-29"
    case_dir.mkdir(parents=True)
    (case_dir / "case.json").write_text(json.dumps(_raw_case(unknown=True)))

    with pytest.raises(ValidationError):
        FrozenCaseProvider(tmp_path).load("2026-05-29")

