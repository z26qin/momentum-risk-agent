from __future__ import annotations

import pytest
from pydantic import ValidationError

from scripts.export_frontend_cases import export_cases
from scripts.run_console_case import run_case
from src.agent.console_case import ConsoleCase, build_console_case
from src.agent.orchestrator import run_orchestrated_investigation
from src.risk_state.provider import FrozenCaseProvider, UnsupportedCaseError


@pytest.mark.parametrize("date", FrozenCaseProvider().supported_dates)
def test_given_supported_case_when_serialized_then_console_preserves_agent_contract(
    date: str,
) -> None:
    case = FrozenCaseProvider().load(date)
    result = run_orchestrated_investigation(case, use_llm=False)

    console = build_console_case(
        result, case, source="export", elapsed_seconds=0.0
    )

    assert console.date == date
    assert console.risk_state.severity.score_is_probability is False
    assert console.trace.combined_stop == result.stop_reason
    assert console.note.citations == tuple(result.trace.calibrated["citations"])


def test_given_quiet_case_when_serialized_then_route_and_combine_exist_without_specialist() -> None:
    case = FrozenCaseProvider().load("2024-01-05")
    result = run_orchestrated_investigation(case, use_llm=False)

    console = build_console_case(
        result, case, source="export", elapsed_seconds=0.0
    )

    assert [event.kind for event in console.trace.loop] == ["route", "combine"]
    assert console.trace.specialists == ()


def test_given_unknown_console_field_when_validated_then_contract_rejects_it() -> None:
    case = FrozenCaseProvider().load("2026-05-29")
    result = run_orchestrated_investigation(case, use_llm=False)
    console = build_console_case(
        result, case, source="export", elapsed_seconds=0.0
    )
    payload = console.model_dump(mode="json")

    with pytest.raises(ValidationError):
        ConsoleCase.model_validate({**payload, "legacy_snapshot": {}})


def test_given_three_frozen_cases_when_exported_twice_then_json_is_identical(
    tmp_path,
) -> None:
    destination = tmp_path / "cases.json"

    first = export_cases(destination)
    second = export_cases(destination)

    assert first == second == destination.read_text(encoding="utf-8")


def test_given_unsupported_date_when_console_run_requested_then_it_fails_explicitly() -> None:
    with pytest.raises(UnsupportedCaseError, match="supported dates"):
        run_case("2026-06-30", source="live")
