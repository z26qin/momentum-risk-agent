"""Shared frozen-case shaped risk states. Not a copy of the original monitor farm."""


def quiet_risk(**overrides):
    payload = {
        "as_of_date": "2024-01-05",
        "data_cutoff": "2024-01-05T16:00:00-05:00",
        "overall_risk_state": "bear_low_volatility",
        "deterministic_trigger_count": 0,
        "triggered_channels": [],
        "structural_flags": [],
        "supported_mechanisms": [],
        "mechanism_statuses": {
            "bear_market_recovery_crash": "not_confirmed",
            "short_book_reversal_crash": "not_confirmed",
            "crowded_theme_unwind": "not_confirmed",
        },
        "mechanical_unwind_state": "NORMAL",
        "primary_driver": None,
        "theme_cluster": [],
        "score_is_probability": False,
        "next_checks": ["Continue ordinary monitoring."],
    }
    payload.update(overrides)
    return payload


def leftover_quiet_risk(**overrides):
    """January 2024 compact assessments can still label primary_driver crowded_unwind."""

    return quiet_risk(primary_driver="crowded_unwind", **overrides)


def semi_unwind_risk(**overrides):
    return quiet_risk(
        as_of_date="2026-05-29",
        data_cutoff="2026-05-29T16:00:00-04:00",
        overall_risk_state="normal",
        deterministic_trigger_count=1,
        triggered_channels=["portfolio_drawdown"],
        structural_flags=["crowded_theme_unwind", "portfolio_concentration"],
        supported_mechanisms=["crowded_theme_unwind"],
        mechanism_statuses={"crowded_theme_unwind": "triggered"},
        mechanical_unwind_state="FRAGILITY_BUILDING",
        primary_driver="crowded_unwind",
        theme_cluster=["CIEN", "COHR", "LITE"],
        why_not_act_yet="Liquidity is still absorbing; shorts are not being squeezed.",
        **overrides,
    )


crowding_risk = semi_unwind_risk


def recovery_risk(**overrides):
    return quiet_risk(
        as_of_date="2020-03-24",
        data_cutoff="2020-03-24T16:00:00-04:00",
        overall_risk_state="panic_elevated",
        deterministic_trigger_count=2,
        triggered_channels=["short_loss_in_recovery", "high_volatility_recovery"],
        structural_flags=["bear_market_recovery_crash"],
        supported_mechanisms=["bear_market_recovery_crash"],
        mechanism_statuses={"bear_market_recovery_crash": "triggered"},
        mechanical_unwind_state="ACTIVE_UNWIND",
        primary_driver="dm_recovery",
        theme_cluster=[],
        **overrides,
    )


def both_mechanisms_risk(**overrides):
    payload = semi_unwind_risk()
    payload.update(
        {
            "deterministic_trigger_count": 2,
            "triggered_channels": ["portfolio_drawdown", "short_loss_in_recovery"],
            "structural_flags": [
                "crowded_theme_unwind",
                "portfolio_concentration",
                "bear_market_recovery_crash",
            ],
            "supported_mechanisms": [
                "crowded_theme_unwind",
                "bear_market_recovery_crash",
            ],
            "mechanism_statuses": {
                "crowded_theme_unwind": "triggered",
                "bear_market_recovery_crash": "triggered",
            },
        }
    )
    payload.update(overrides)
    return payload
