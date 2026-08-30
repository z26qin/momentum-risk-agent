"""Mechanism specialists: routing, tools, prompt addendum, finish copy.

One table owns the names the rest of the agent refers to. Adding a monitor
means adding a row here, not copying orchestrator/synthesis/planner branches.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from src.agent.signals import (
    crowding_signal_present,
    no_meaningful_risk_signal,
    recovery_setup_present,
)
from src.risk_state.models import RiskState
from src.tools.registry import ToolRegistry, crowding_registry, recovery_registry

Signal = Callable[[RiskState], bool]
RegistryFactory = Callable[..., ToolRegistry]


@dataclass(frozen=True)
class Specialist:
    name: str
    focus: str
    label: str
    signal: Signal
    registry: RegistryFactory
    addendum: str
    finish_text: str


SPECIALISTS: tuple[Specialist, ...] = (
    Specialist(
        name="crowding",
        focus="kl_crowding",
        label="Crowding (Khandani–Lo)",
        signal=crowding_signal_present,
        registry=crowding_registry,
        addendum=(
            "Focus: Khandani–Lo crowding only. Question: is pressure a localized "
            "crowded unwind, or forced deleveraging? Use only the tools in "
            "allowed_tools. Do not investigate recovery. Localized theme reduction "
            "is not proof of forced deleveraging."
        ),
        finish_text=(
            "Localized crowding pressure is supported. Forced deleveraging "
            "and a book-wide unwind remain unconfirmed."
        ),
    ),
    Specialist(
        name="recovery",
        focus="dm_recovery",
        label="Recovery (Daniel–Moskowitz)",
        signal=recovery_setup_present,
        registry=recovery_registry,
        addendum=(
            "Focus: Daniel–Moskowitz recovery only. Question: is this a "
            "recovery-driven loser rebound / short-leg crash setup? Use only the "
            "tools in allowed_tools. Do not investigate crowding. "
            "score_is_probability is always false."
        ),
        finish_text=(
            "Recovery conditions were investigated. This remains an "
            "interpretation of the deterministic state, not a crash call."
        ),
    ),
)
BY_NAME = {spec.name: spec for spec in SPECIALISTS}
BY_FOCUS = {spec.focus: spec for spec in SPECIALISTS}
SCHEDULE = "parallel_shared_deadline"
QUIET_READ = (
    "The deterministic state does not justify additional evidence search. "
    "Continue ordinary monitoring."
)
UNRESOLVABLE_FINISH = (
    "Remaining uncertainty cannot be resolved into a confirmed "
    "unwind or crash from available tools."
)


def select_specialists(risk_state: RiskState) -> tuple[str, ...]:
    """Quiet books spawn nobody. Flags, not leftover primary_driver labels."""

    if no_meaningful_risk_signal(risk_state):
        return ()
    return tuple(spec.name for spec in SPECIALISTS if spec.signal(risk_state))


def finish_text_for(risk_state: RiskState, focus: str | None) -> str:
    for spec in SPECIALISTS:
        if spec.signal(risk_state) and focus in {None, spec.focus}:
            return spec.finish_text
    return UNRESOLVABLE_FINISH
