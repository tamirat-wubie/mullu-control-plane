"""Purpose: process / physics simulation runtime contracts.
Governance scope: typed descriptors for process models, physical parameters,
    simulation scenarios, simulation runs, simulation results, constraint
    envelopes, process assessments, violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Float fields reject bool, inf, and nan but allow negative where noted.
  - COMPLETED/FAILED/CANCELLED runs are terminal.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_non_negative_float,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Local float validator
# ---------------------------------------------------------------------------


def _require_finite_float(value: float, field_name: str) -> float:
    """Validate that a float is finite (rejects bool, inf, nan; allows negative)."""
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("numeric value must be a number")
    fval = float(value)
    if not math.isfinite(fval):
        raise ValueError("numeric value must be finite")
    return fval


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ProcessSimulationStatus(Enum):
    """Lifecycle status of a simulation run."""
    CONFIGURED = "configured"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessModelKind(Enum):
    """Category of process model."""
    THROUGHPUT = "throughput"
    THERMAL = "thermal"
    FLOW = "flow"
    TIMING = "timing"
    YIELD = "yield"
    DEGRADATION = "degradation"


class SimulationDisposition(Enum):
    """Disposition of a simulation scenario."""
    NOMINAL = "nominal"
    STRESSED = "stressed"
    DEGRADED = "degraded"
    FAILURE = "failure"
    RECOVERY = "recovery"


class PhysicalConstraintStatus(Enum):
    """Status of a physical constraint check."""
    WITHIN_ENVELOPE = "within_envelope"
    WARNING = "warning"
    BREACH = "breach"
    CRITICAL = "critical"


class ProcessRiskLevel(Enum):
    """Risk level for process operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SimulationOutcomeKind(Enum):
    """Outcome kind for a simulation result."""
    PASS = "pass"
    MARGINAL = "marginal"
    FAIL = "fail"
    UNSAFE = "unsafe"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProcessModel(ContractRecord):
    """A process model for physics simulation."""

    model_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: ProcessModelKind = ProcessModelKind.THROUGHPUT
    parameter_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "model_id", require_non_empty_text(self.model_id, "model_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.kind, ProcessModelKind):
            raise ValueError("kind must be a ProcessModelKind")
        object.__setattr__(self, "parameter_count", require_non_negative_int(self.parameter_count, "parameter_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PhysicalParameter(ContractRecord):
    """A physical parameter within a process model."""

    parameter_id: str = ""
    tenant_id: str = ""
    model_ref: str = ""
    name: str = ""
    value: float = 0.0
    unit: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "parameter_id", require_non_empty_text(self.parameter_id, "parameter_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "model_ref", require_non_empty_text(self.model_ref, "model_ref"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        object.__setattr__(self, "value", _require_finite_float(self.value, "value"))
        object.__setattr__(self, "unit", require_non_empty_text(self.unit, "unit"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SimulationScenario(ContractRecord):
    """A simulation scenario for a process model."""

    scenario_id: str = ""
    tenant_id: str = ""
    model_ref: str = ""
    disposition: SimulationDisposition = SimulationDisposition.NOMINAL
    description: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "scenario_id", require_non_empty_text(self.scenario_id, "scenario_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "model_ref", require_non_empty_text(self.model_ref, "model_ref"))
        if not isinstance(self.disposition, SimulationDisposition):
            raise ValueError("disposition must be a SimulationDisposition")
        # description may be empty
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SimulationRun(ContractRecord):
    """A simulation run instance."""

    run_id: str = ""
    tenant_id: str = ""
    scenario_ref: str = ""
    status: ProcessSimulationStatus = ProcessSimulationStatus.CONFIGURED
    duration_ms: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "run_id", require_non_empty_text(self.run_id, "run_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "scenario_ref", require_non_empty_text(self.scenario_ref, "scenario_ref"))
        if not isinstance(self.status, ProcessSimulationStatus):
            raise ValueError("status must be a ProcessSimulationStatus")
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SimulationResult(ContractRecord):
    """A result from a simulation run."""

    result_id: str = ""
    tenant_id: str = ""
    run_ref: str = ""
    outcome: SimulationOutcomeKind = SimulationOutcomeKind.PASS
    expected_value: float = 0.0
    actual_value: float = 0.0
    deviation: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "run_ref", require_non_empty_text(self.run_ref, "run_ref"))
        if not isinstance(self.outcome, SimulationOutcomeKind):
            raise ValueError("outcome must be a SimulationOutcomeKind")
        object.__setattr__(self, "expected_value", _require_finite_float(self.expected_value, "expected_value"))
        object.__setattr__(self, "actual_value", _require_finite_float(self.actual_value, "actual_value"))
        object.__setattr__(self, "deviation", _require_finite_float(self.deviation, "deviation"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ConstraintEnvelope(ContractRecord):
    """A constraint envelope for a physical parameter."""

    envelope_id: str = ""
    tenant_id: str = ""
    parameter_ref: str = ""
    min_value: float = 0.0
    max_value: float = 0.0
    target_value: float = 0.0
    status: PhysicalConstraintStatus = PhysicalConstraintStatus.WITHIN_ENVELOPE
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "envelope_id", require_non_empty_text(self.envelope_id, "envelope_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "parameter_ref", require_non_empty_text(self.parameter_ref, "parameter_ref"))
        object.__setattr__(self, "min_value", _require_finite_float(self.min_value, "min_value"))
        object.__setattr__(self, "max_value", _require_finite_float(self.max_value, "max_value"))
        object.__setattr__(self, "target_value", _require_finite_float(self.target_value, "target_value"))
        if not isinstance(self.status, PhysicalConstraintStatus):
            raise ValueError("status must be a PhysicalConstraintStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcessAssessment(ContractRecord):
    """Assessment of process simulation state for a tenant."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_models: int = 0
    total_runs: int = 0
    total_violations: int = 0
    safety_score: float = 1.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_models", require_non_negative_int(self.total_models, "total_models"))
        object.__setattr__(self, "total_runs", require_non_negative_int(self.total_runs, "total_runs"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "safety_score", require_unit_float(self.safety_score, "safety_score"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcessViolation(ContractRecord):
    """A violation detected in process simulation."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcessSnapshot(ContractRecord):
    """Point-in-time snapshot of process simulation runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_models: int = 0
    total_parameters: int = 0
    total_scenarios: int = 0
    total_runs: int = 0
    total_envelopes: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_models", require_non_negative_int(self.total_models, "total_models"))
        object.__setattr__(self, "total_parameters", require_non_negative_int(self.total_parameters, "total_parameters"))
        object.__setattr__(self, "total_scenarios", require_non_negative_int(self.total_scenarios, "total_scenarios"))
        object.__setattr__(self, "total_runs", require_non_negative_int(self.total_runs, "total_runs"))
        object.__setattr__(self, "total_envelopes", require_non_negative_int(self.total_envelopes, "total_envelopes"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ProcessClosureReport(ContractRecord):
    """Final closure report for process simulation runtime lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_models: int = 0
    total_runs: int = 0
    total_results: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_models", require_non_negative_int(self.total_models, "total_models"))
        object.__setattr__(self, "total_runs", require_non_negative_int(self.total_runs, "total_runs"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
