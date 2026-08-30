"""Immutable contracts at the deterministic-to-agent trust boundary."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

NEW_YORK = ZoneInfo("America/New_York")
MechanismStatus = Literal["triggered", "watch", "not_confirmed", "unavailable"]
MechanicalState = Literal[
    "NORMAL", "FRAGILITY_BUILDING", "ACTIVE_UNWIND", "STABILIZING_REVERSAL"
]


class FrozenModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class MechanismStates(FrozenModel):
    bear_market_recovery_crash: MechanismStatus
    crowded_theme_unwind: MechanismStatus
    short_book_reversal_crash: MechanismStatus


class BookState(FrozenModel):
    portfolio_drawdown: float | None = None
    short_loss_in_recovery: float | None = None
    long_beta_126d: float | None = None
    short_underlying_beta_126d: float | None = None


class MechanismScores(FrozenModel):
    book_vulnerability: int | None = Field(default=None, ge=0, le=100)
    crowded_unwind: int | None = Field(default=None, ge=0, le=100)
    dm_recovery: int | None = Field(default=None, ge=0, le=100)
    fundamental_repricing: int | None = Field(default=None, ge=0, le=100)


class SeverityState(FrozenModel):
    score: int | None = Field(default=None, ge=0, le=100)
    label: str = Field(min_length=1)
    primary_driver: str = Field(min_length=1)
    mechanism_scores: MechanismScores
    score_is_probability: Literal[False] = False


class RiskState(FrozenModel):
    schema_version: Literal["risk-state-v1"]
    as_of_date: date
    assessment_cutoff: datetime
    comparison_date: date | None = None
    market_regime: str = Field(min_length=1)
    mechanical_unwind_state: MechanicalState
    total_signal_count: int = Field(ge=1)
    triggered_signals: tuple[str, ...] = ()
    structural_flags: tuple[str, ...] = ()
    mechanisms: MechanismStates
    book: BookState
    theme_cluster: tuple[str, ...] = ()
    severity: SeverityState

    @field_validator("triggered_signals", "structural_flags")
    @classmethod
    def _unique_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(str(item).strip() for item in value if str(item).strip())
        if len(set(normalized)) != len(normalized):
            raise ValueError("state labels must be unique")
        return normalized

    @field_validator("theme_cluster")
    @classmethod
    def _normalize_symbols(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        normalized = tuple(str(item).strip().upper() for item in value if str(item).strip())
        if len(set(normalized)) != len(normalized):
            raise ValueError("theme symbols must be unique")
        return normalized

    @model_validator(mode="after")
    def _validate_boundary(self) -> RiskState:
        if len(self.triggered_signals) > self.total_signal_count:
            raise ValueError("triggered signals cannot exceed total signal count")
        cutoff = self.assessment_cutoff
        if cutoff.tzinfo is None:
            raise ValueError("assessment cutoff must be timezone-aware")
        local = cutoff.astimezone(NEW_YORK)
        if local.date() != self.as_of_date or local.timetz().replace(tzinfo=None) != time(16, 0):
            raise ValueError("assessment cutoff must be 16:00 America/New_York on as_of_date")
        return self

    @property
    def monitoring_trigger_count(self) -> int:
        return len(self.triggered_signals)

    @property
    def triggered_mechanisms(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, status in self.mechanisms.model_dump().items()
            if status == "triggered"
        )

    @property
    def unconfirmed_mechanisms(self) -> tuple[str, ...]:
        return tuple(
            name
            for name, status in self.mechanisms.model_dump().items()
            if status != "triggered"
        )


class Provenance(FrozenModel):
    source_repository: str = Field(min_length=1)
    source_commit: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    run_fingerprint: str = Field(min_length=1)


class EvidenceDocument(FrozenModel):
    evidence_id: str = Field(min_length=1)
    published_at: datetime
    source: str = Field(min_length=1)
    headline: str = Field(min_length=1)
    snippet: str = Field(min_length=1)
    channels: tuple[Literal["news", "positioning"], ...] = ("news",)
    symbols: tuple[str, ...] = ()
    stance: Literal["supporting", "contradicting", "contextual", "mixed"] | None = None

    @field_validator("symbols")
    @classmethod
    def _symbols_upper(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(str(item).strip().upper() for item in value if str(item).strip())


class HoldingObservation(FrozenModel):
    symbol: str = Field(min_length=1)
    leg: Literal["long", "short"]
    weight: float
    effective_month: date
    formation_date: date

    @field_validator("symbol")
    @classmethod
    def _symbol_upper(cls, value: str) -> str:
        return value.strip().upper()


class InvestigationCase(FrozenModel):
    schema_version: Literal["investigation-case-v1"]
    provenance: Provenance
    risk_state: RiskState
    prior_state: RiskState | None = None
    evidence: tuple[EvidenceDocument, ...] = ()
    holdings: tuple[HoldingObservation, ...] = ()

    @model_validator(mode="after")
    def _validate_prior(self) -> InvestigationCase:
        if self.prior_state is None:
            return self
        if self.risk_state.comparison_date != self.prior_state.as_of_date:
            raise ValueError("prior_state date must match risk_state comparison_date")
        if self.prior_state.as_of_date >= self.risk_state.as_of_date:
            raise ValueError("prior_state must predate risk_state")
        return self
