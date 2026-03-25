"""Purpose: scientific method / experimentation runtime contracts.
Governance scope: typed descriptors for experiment designs, variables,
    control groups, results, falsification, replication, decisions,
    assessments, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every experiment references a hypothesis.
  - Experiments follow DESIGN -> RUNNING -> ANALYSIS -> COMPLETED lifecycle.
  - COMPLETED/FAILED experiments are terminal.
  - All outputs are frozen.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExperimentPhase(Enum):
    """Phase of an experiment lifecycle."""
    DESIGN = "design"
    SETUP = "setup"
    RUNNING = "running"
    ANALYSIS = "analysis"
    COMPLETED = "completed"
    FAILED = "failed"


class VariableRole(Enum):
    """Role of a variable in an experiment."""
    INDEPENDENT = "independent"
    DEPENDENT = "dependent"
    CONTROL = "control"
    CONFOUNDING = "confounding"


class FalsificationStatus(Enum):
    """Falsification status of a hypothesis."""
    UNFALSIFIED = "unfalsified"
    FALSIFIED = "falsified"
    INCONCLUSIVE = "inconclusive"
    REPLICATED = "replicated"


class ReplicationStatus(Enum):
    """Status of a replication attempt."""
    PENDING = "pending"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    PARTIAL = "partial"


class ResultSignificance(Enum):
    """Statistical significance of a result."""
    SIGNIFICANT = "significant"
    MARGINAL = "marginal"
    INSIGNIFICANT = "insignificant"
    UNDETERMINED = "undetermined"


class ExperimentRiskLevel(Enum):
    """Risk level for experiment operations."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExperimentDesign(ContractRecord):
    """An experiment design referencing a hypothesis."""

    design_id: str = ""
    tenant_id: str = ""
    hypothesis_ref: str = ""
    display_name: str = ""
    phase: ExperimentPhase = ExperimentPhase.DESIGN
    variable_count: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "design_id", require_non_empty_text(self.design_id, "design_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "hypothesis_ref", require_non_empty_text(self.hypothesis_ref, "hypothesis_ref"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.phase, ExperimentPhase):
            raise ValueError("phase must be an ExperimentPhase")
        object.__setattr__(self, "variable_count", require_non_negative_int(self.variable_count, "variable_count"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExperimentVariable(ContractRecord):
    """A variable in an experiment design."""

    variable_id: str = ""
    tenant_id: str = ""
    design_ref: str = ""
    name: str = ""
    role: VariableRole = VariableRole.INDEPENDENT
    unit: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "variable_id", require_non_empty_text(self.variable_id, "variable_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "design_ref", require_non_empty_text(self.design_ref, "design_ref"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not isinstance(self.role, VariableRole):
            raise ValueError("role must be a VariableRole")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ControlGroup(ContractRecord):
    """A control group in an experiment."""

    group_id: str = ""
    tenant_id: str = ""
    design_ref: str = ""
    display_name: str = ""
    sample_size: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "group_id", require_non_empty_text(self.group_id, "group_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "design_ref", require_non_empty_text(self.design_ref, "design_ref"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        object.__setattr__(self, "sample_size", require_non_negative_int(self.sample_size, "sample_size"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExperimentResult(ContractRecord):
    """A result from an experiment."""

    result_id: str = ""
    tenant_id: str = ""
    design_ref: str = ""
    significance: ResultSignificance = ResultSignificance.UNDETERMINED
    effect_size: float = 0.0
    p_value: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "design_ref", require_non_empty_text(self.design_ref, "design_ref"))
        if not isinstance(self.significance, ResultSignificance):
            raise ValueError("significance must be a ResultSignificance")
        object.__setattr__(self, "effect_size", require_unit_float(self.effect_size, "effect_size"))
        object.__setattr__(self, "p_value", require_unit_float(self.p_value, "p_value"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class FalsificationRecord(ContractRecord):
    """A falsification record for a hypothesis."""

    record_id: str = ""
    tenant_id: str = ""
    hypothesis_ref: str = ""
    status: FalsificationStatus = FalsificationStatus.UNFALSIFIED
    evidence_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "hypothesis_ref", require_non_empty_text(self.hypothesis_ref, "hypothesis_ref"))
        if not isinstance(self.status, FalsificationStatus):
            raise ValueError("status must be a FalsificationStatus")
        object.__setattr__(self, "evidence_ref", require_non_empty_text(self.evidence_ref, "evidence_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ReplicationRecord(ContractRecord):
    """A replication attempt for an experiment."""

    replication_id: str = ""
    tenant_id: str = ""
    original_ref: str = ""
    status: ReplicationStatus = ReplicationStatus.PENDING
    confidence: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "replication_id", require_non_empty_text(self.replication_id, "replication_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "original_ref", require_non_empty_text(self.original_ref, "original_ref"))
        if not isinstance(self.status, ReplicationStatus):
            raise ValueError("status must be a ReplicationStatus")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExperimentDecision(ContractRecord):
    """A decision made about an experiment."""

    decision_id: str = ""
    tenant_id: str = ""
    design_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "design_ref", require_non_empty_text(self.design_ref, "design_ref"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExperimentAssessment(ContractRecord):
    """Assessment summary of experimentation activity."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_designs: int = 0
    total_results: int = 0
    total_replications: int = 0
    success_rate: float = 0.0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_designs", require_non_negative_int(self.total_designs, "total_designs"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_replications", require_non_negative_int(self.total_replications, "total_replications"))
        object.__setattr__(self, "success_rate", require_unit_float(self.success_rate, "success_rate"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExperimentSnapshot(ContractRecord):
    """Point-in-time experiment state snapshot."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_designs: int = 0
    total_variables: int = 0
    total_groups: int = 0
    total_results: int = 0
    total_falsifications: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_designs", require_non_negative_int(self.total_designs, "total_designs"))
        object.__setattr__(self, "total_variables", require_non_negative_int(self.total_variables, "total_variables"))
        object.__setattr__(self, "total_groups", require_non_negative_int(self.total_groups, "total_groups"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_falsifications", require_non_negative_int(self.total_falsifications, "total_falsifications"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExperimentClosureReport(ContractRecord):
    """Summary report for experiment lifecycle closure."""

    report_id: str = ""
    tenant_id: str = ""
    total_designs: int = 0
    total_results: int = 0
    total_replications: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_designs", require_non_negative_int(self.total_designs, "total_designs"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_replications", require_non_negative_int(self.total_replications, "total_replications"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
