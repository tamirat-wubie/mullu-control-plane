"""Purpose: canonical execution result contract mapping and closure typing.
Governance scope: shared execution adoption and completion envelope typing.
Dependencies: execution schema and shared verification semantics.
Invariants: execution is not complete without verification closure or explicit accepted risk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text
from .verification import VerificationResult


class ExecutionOutcome(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionMode(StrEnum):
    """Runtime admission mode for effect-bearing or backend-bearing execution."""

    REAL = "real"
    DRY_RUN = "dry_run"
    SHADOW = "shadow"
    SIMULATION = "simulation"
    REPLAY = "replay"
    TEST = "test"


def coerce_execution_mode(value: ExecutionMode | str) -> ExecutionMode:
    """Return a canonical ExecutionMode or raise with causal context."""

    if isinstance(value, ExecutionMode):
        return value
    if not isinstance(value, str):
        raise ValueError("execution_mode must be an ExecutionMode or string value")
    try:
        return ExecutionMode(value)
    except ValueError as exc:
        allowed = ", ".join(mode.value for mode in ExecutionMode)
        raise ValueError(f"unknown execution_mode {value!r}; expected one of: {allowed}") from exc


def execution_mode_requires_backend(mode: ExecutionMode | str) -> bool:
    """Return whether the mode must be backed by a real execution provider."""

    return coerce_execution_mode(mode) in {ExecutionMode.REAL, ExecutionMode.SHADOW}


def execution_mode_allows_synthetic_output(mode: ExecutionMode | str) -> bool:
    """Return whether the mode may emit synthetic output without a backend."""

    return coerce_execution_mode(mode) in {
        ExecutionMode.DRY_RUN,
        ExecutionMode.SIMULATION,
        ExecutionMode.TEST,
    }


def execution_mode_requires_replay_evidence(mode: ExecutionMode | str) -> bool:
    """Return whether the mode must be sourced from existing replay evidence."""

    return coerce_execution_mode(mode) is ExecutionMode.REPLAY


@dataclass(frozen=True, slots=True)
class EffectRecord(ContractRecord):
    name: str
    details: Any = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "details", freeze_value(self.details))


def _freeze_effect_records(effects: tuple[EffectRecord, ...], field_name: str) -> tuple[EffectRecord, ...]:
    if isinstance(effects, (str, bytes)) or not isinstance(effects, (tuple, list)):
        raise ValueError(f"{field_name} must be an array of EffectRecord values")
    frozen = freeze_value(list(effects))
    for index, effect in enumerate(frozen):
        if not isinstance(effect, EffectRecord):
            raise ValueError(f"{field_name}[{index}] must be an EffectRecord")
    return frozen


@dataclass(frozen=True, slots=True)
class ExecutionResult(ContractRecord):
    execution_id: str
    goal_id: str
    status: ExecutionOutcome
    actual_effects: tuple[EffectRecord, ...]
    assumed_effects: tuple[EffectRecord, ...]
    started_at: str
    finished_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)
    execution_mode: ExecutionMode | str = ExecutionMode.REAL

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        object.__setattr__(self, "goal_id", require_non_empty_text(self.goal_id, "goal_id"))
        if not isinstance(self.status, ExecutionOutcome):
            raise ValueError("status must be an ExecutionOutcome value")
        object.__setattr__(self, "execution_mode", coerce_execution_mode(self.execution_mode))
        object.__setattr__(self, "actual_effects", _freeze_effect_records(self.actual_effects, "actual_effects"))
        object.__setattr__(self, "assumed_effects", _freeze_effect_records(self.assumed_effects, "assumed_effects"))
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "finished_at", require_datetime_text(self.finished_at, "finished_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))


@dataclass(frozen=True, slots=True)
class AcceptedRiskState(ContractRecord):
    risk_id: str
    execution_id: str
    reason: str
    accepted_at: str
    metadata: Mapping[str, Any] = field(default_factory=dict)
    extensions: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in ("risk_id", "execution_id", "reason"):
            object.__setattr__(self, field_name, require_non_empty_text(getattr(self, field_name), field_name))
        object.__setattr__(self, "accepted_at", require_datetime_text(self.accepted_at, "accepted_at"))
        object.__setattr__(self, "metadata", freeze_value(self.metadata))
        object.__setattr__(self, "extensions", freeze_value(self.extensions))


@dataclass(frozen=True, slots=True)
class ExecutionClosure(ContractRecord):
    execution_result: ExecutionResult
    verification_result: VerificationResult | None = None
    accepted_risk: AcceptedRiskState | None = None

    def __post_init__(self) -> None:
        has_verification = self.verification_result is not None
        has_risk = self.accepted_risk is not None
        if has_verification == has_risk:
            raise ValueError(
                "ExecutionClosure requires exactly one of verification_result or accepted_risk"
            )
        if has_verification and self.verification_result.execution_id != self.execution_result.execution_id:
            raise ValueError("verification_result.execution_id must match execution_result.execution_id")
        if has_risk and self.accepted_risk.execution_id != self.execution_result.execution_id:
            raise ValueError("accepted_risk.execution_id must match execution_result.execution_id")
