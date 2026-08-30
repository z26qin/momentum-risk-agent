"""Code-owned routing predicates over immutable deterministic state."""

from src.risk_state.models import RiskState


def crowding_signal_present(risk: RiskState) -> bool:
    return risk.mechanisms.crowded_theme_unwind == "triggered"


def recovery_setup_present(risk: RiskState) -> bool:
    return risk.mechanisms.bear_market_recovery_crash == "triggered"


def no_meaningful_risk_signal(risk: RiskState) -> bool:
    return not crowding_signal_present(risk) and not recovery_setup_present(risk)
