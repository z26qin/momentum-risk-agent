"""Thin smoke that inherited monitor logic still loads.

The original regression farm lives in momentum-tail-risk-monitor. This repo
only checks a few engine invariants the investigation agent depends on.
"""

from __future__ import annotations

import pytest

from src.agent_prompts import (
    crowding_signal_present,
    no_meaningful_risk_signal,
    published_by_cutoff,
    recovery_setup_present,
)
from src.mvp.hermes_monitor import REQUIRED_ASSESSMENT_FIELDS, validate_evidence_cutoff
from src.mvp.monitoring_severity import severity_band
from tests.cases import leftover_quiet_risk, recovery_risk, semi_unwind_risk


def test_leftover_primary_driver_is_not_a_routing_signal() -> None:
    quiet = leftover_quiet_risk()
    assert crowding_signal_present(quiet) is False
    assert recovery_setup_present(quiet) is False
    assert no_meaningful_risk_signal(quiet) is True
    assert crowding_signal_present(semi_unwind_risk()) is True
    assert recovery_setup_present(recovery_risk()) is True


def test_evidence_cutoff_is_dst_safe() -> None:
    may = "2026-05-29T16:00:00-04:00"
    jan = "2024-01-05T16:00:00-05:00"
    assert published_by_cutoff("2026-05-29 16:00 ET", may, "2026-05-29") is True
    assert published_by_cutoff("2026-05-29 16:01 ET", may, "2026-05-29") is False
    assert published_by_cutoff("2024-01-05 16:00 ET", jan, "2024-01-05") is True
    assert published_by_cutoff("2024-01-05 16:01 ET", jan, "2024-01-05") is False
    assert published_by_cutoff("2026-06-15", may, "2026-05-29") is False


def test_compact_assessment_contract_and_relative_severity() -> None:
    assert "score_is_probability" in REQUIRED_ASSESSMENT_FIELDS
    assert "primary_driver" in REQUIRED_ASSESSMENT_FIELDS
    label, _emoji = severity_band(78)
    assert label == "elevated"
    assert validate_evidence_cutoff("2026-05-29", "2026-05-29 16:00 ET") == "2026-05-29 16:00 ET"
    with pytest.raises(ValueError):
        validate_evidence_cutoff("2026-05-29", "2026-05-29 09:30 ET")
