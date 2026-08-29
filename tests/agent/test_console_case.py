from src.agent.console_case import PM_SIGNALS, build_console_case, compact_from_snapshot
from src.agent.orchestrator import run_orchestrated_investigation
from src.agent.planner import HeuristicPlanner
from src.utils.io import REPO_ROOT
from tests.cases import leftover_quiet_risk, recovery_risk, semi_unwind_risk


def test_console_case_uses_agent_buckets() -> None:
    risk = leftover_quiet_risk()
    result = run_orchestrated_investigation(risk_state=risk, use_llm=False)
    case = build_console_case(result, case_id="quiet2024", label="Quiet control")
    assert case["trace"]["quiet"] is True
    assert case["trace"]["spawned"] == []
    assert case["trace"]["combined_stop"] == "NO_INVESTIGATION_NEEDED"
    assert case["risk_state"]["trigger_count"] == "0 / 4"
    assert case["note"]["score_is_probability"] is False
    assert "Citations" not in case["note"]["citations"]


def test_console_case_crowding_has_trace_and_citations_shape() -> None:
    result = run_orchestrated_investigation(
        risk_state=semi_unwind_risk(),
        planners={"crowding": HeuristicPlanner(focus="kl_crowding")},
        use_llm=False,
    )
    case = build_console_case(result, case_id="semi", label="Localized unwind")
    assert case["trace"]["spawned"] == ["crowding"]
    assert case["trace"]["specialists"][0]["focus"] == "kl_crowding"
    assert case["trace"]["specialists"][0]["decisions"]
    assert case["note"]["current_read"]
    assert isinstance(case["note"]["citations"], list)
    assert case["risk_state"]["trigger_count"].endswith(f"/ {len(PM_SIGNALS)}")
    assert [row["metric"] for row in case["risk_state"]["scorecard"]] == list(PM_SIGNALS)


def test_console_case_scorecard_matches_agent_four_signals() -> None:
    snapshot = REPO_ROOT / "outputs/snapshot_2026-05-29/structured_snapshot.json"
    risk = compact_from_snapshot(snapshot, semi_unwind_risk())
    result = run_orchestrated_investigation(risk_state=risk, use_llm=False)
    case = build_console_case(
        result,
        case_id="semi",
        label="Localized unwind",
        snapshot=snapshot,
    )
    assert case["risk_state"]["trigger_count"] == "0 / 4"
    assert case["note"]["observed"][0] == "0 / 4 deterministic signals triggered"
    assert case["trace"]["spawned"] == ["crowding"]
    assert {row["metric"] for row in case["risk_state"]["scorecard"]} == set(PM_SIGNALS)
    assert not any(row["triggered"] for row in case["risk_state"]["scorecard"])


def test_console_case_march_2020_uses_evaluation_snapshot() -> None:
    snapshot = REPO_ROOT / "data/evaluation/march_2020_reference/structured_snapshot.json"
    risk = compact_from_snapshot(snapshot, recovery_risk())
    result = run_orchestrated_investigation(risk_state=risk, use_llm=False)
    case = build_console_case(
        result,
        case_id="march2020",
        label="Recovery crash ref",
        snapshot=snapshot,
    )
    assert case["risk_state"]["trigger_count"] == "3 / 4"
    assert case["note"]["observed"][0] == "3 / 4 deterministic signals triggered"
    assert case["trace"]["spawned"] == ["recovery"]
    fired = {row["metric"] for row in case["risk_state"]["scorecard"] if row["triggered"]}
    assert fired == {
        "high_volatility_recovery",
        "short_minus_long_beta_gap",
        "short_loss_in_recovery",
    }
