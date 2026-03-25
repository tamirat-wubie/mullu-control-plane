"""Purpose: meta-orchestration / cross-runtime composition contracts.
Governance scope: typed descriptors for orchestration plans, steps,
    dependencies, runtime bindings, decisions, execution traces,
    snapshots, violations, assessments, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every plan references a tenant.
  - Steps execute in dependency order.
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


class OrchestrationStatus(Enum):
    """Status of an orchestration plan or step."""
    DRAFT = "draft"
    READY = "ready"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestrationStepKind(Enum):
    """Kind of orchestration step."""
    INVOKE = "invoke"
    GATE = "gate"
    TRANSFORM = "transform"
    FALLBACK = "fallback"
    ESCALATION = "escalation"


class DependencyDisposition(Enum):
    """Disposition of a step dependency evaluation."""
    SATISFIED = "satisfied"
    BLOCKED = "blocked"
    SKIPPED = "skipped"
    FAILED = "failed"


class CoordinationMode(Enum):
    """Mode of cross-runtime coordination."""
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    FALLBACK = "fallback"


class CompositionScope(Enum):
    """Scope of the orchestration composition."""
    TENANT = "tenant"
    PROGRAM = "program"
    CAMPAIGN = "campaign"
    SERVICE = "service"
    CASE = "case"
    GLOBAL = "global"


class OrchestrationDecisionStatus(Enum):
    """Status of an orchestration decision."""
    APPROVED = "approved"
    DENIED = "denied"
    DEFERRED = "deferred"
    ESCALATED = "escalated"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class OrchestrationPlan(ContractRecord):
    """A multi-runtime orchestration plan."""

    plan_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    status: OrchestrationStatus = OrchestrationStatus.DRAFT
    coordination_mode: CoordinationMode = CoordinationMode.SEQUENTIAL
    scope: CompositionScope = CompositionScope.TENANT
    step_count: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.status, OrchestrationStatus):
            raise ValueError("status must be an OrchestrationStatus")
        if not isinstance(self.coordination_mode, CoordinationMode):
            raise ValueError("coordination_mode must be a CoordinationMode")
        if not isinstance(self.scope, CompositionScope):
            raise ValueError("scope must be a CompositionScope")
        object.__setattr__(self, "step_count", require_non_negative_int(self.step_count, "step_count"))
        object.__setattr__(self, "completed_steps", require_non_negative_int(self.completed_steps, "completed_steps"))
        object.__setattr__(self, "failed_steps", require_non_negative_int(self.failed_steps, "failed_steps"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OrchestrationStep(ContractRecord):
    """A single step within an orchestration plan."""

    step_id: str = ""
    plan_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: OrchestrationStepKind = OrchestrationStepKind.INVOKE
    target_runtime: str = ""
    target_action: str = ""
    status: OrchestrationStatus = OrchestrationStatus.DRAFT
    sequence_order: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_id", require_non_empty_text(self.step_id, "step_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.kind, OrchestrationStepKind):
            raise ValueError("kind must be an OrchestrationStepKind")
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "target_action", require_non_empty_text(self.target_action, "target_action"))
        if not isinstance(self.status, OrchestrationStatus):
            raise ValueError("status must be an OrchestrationStatus")
        object.__setattr__(self, "sequence_order", require_non_negative_int(self.sequence_order, "sequence_order"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class StepDependency(ContractRecord):
    """A dependency between two orchestration steps."""

    dependency_id: str = ""
    plan_id: str = ""
    tenant_id: str = ""
    from_step_id: str = ""
    to_step_id: str = ""
    disposition: DependencyDisposition = DependencyDisposition.BLOCKED
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "dependency_id", require_non_empty_text(self.dependency_id, "dependency_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "from_step_id", require_non_empty_text(self.from_step_id, "from_step_id"))
        object.__setattr__(self, "to_step_id", require_non_empty_text(self.to_step_id, "to_step_id"))
        if not isinstance(self.disposition, DependencyDisposition):
            raise ValueError("disposition must be a DependencyDisposition")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class RuntimeBinding(ContractRecord):
    """A binding between an orchestration step and a runtime."""

    binding_id: str = ""
    step_id: str = ""
    tenant_id: str = ""
    runtime_name: str = ""
    action_name: str = ""
    config_ref: str = ""
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "step_id", require_non_empty_text(self.step_id, "step_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "runtime_name", require_non_empty_text(self.runtime_name, "runtime_name"))
        object.__setattr__(self, "action_name", require_non_empty_text(self.action_name, "action_name"))
        object.__setattr__(self, "config_ref", require_non_empty_text(self.config_ref, "config_ref"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OrchestrationDecision(ContractRecord):
    """A decision made during orchestration execution."""

    decision_id: str = ""
    plan_id: str = ""
    step_id: str = ""
    tenant_id: str = ""
    status: OrchestrationDecisionStatus = OrchestrationDecisionStatus.APPROVED
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "step_id", require_non_empty_text(self.step_id, "step_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.status, OrchestrationDecisionStatus):
            raise ValueError("status must be an OrchestrationDecisionStatus")
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionTrace(ContractRecord):
    """A trace record of a step execution."""

    trace_id: str = ""
    plan_id: str = ""
    step_id: str = ""
    tenant_id: str = ""
    runtime_name: str = ""
    action_name: str = ""
    status: OrchestrationStatus = OrchestrationStatus.COMPLETED
    duration_ms: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", require_non_empty_text(self.trace_id, "trace_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "step_id", require_non_empty_text(self.step_id, "step_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "runtime_name", require_non_empty_text(self.runtime_name, "runtime_name"))
        object.__setattr__(self, "action_name", require_non_empty_text(self.action_name, "action_name"))
        if not isinstance(self.status, OrchestrationStatus):
            raise ValueError("status must be an OrchestrationStatus")
        if not isinstance(self.duration_ms, (int, float)) or isinstance(self.duration_ms, bool):
            raise ValueError("duration_ms must be a number")
        if self.duration_ms < 0:
            raise ValueError("duration_ms must be non-negative")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OrchestrationSnapshot(ContractRecord):
    """Point-in-time snapshot of orchestration state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_plans: int = 0
    active_plans: int = 0
    total_steps: int = 0
    completed_steps: int = 0
    failed_steps: int = 0
    total_traces: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_plans", require_non_negative_int(self.total_plans, "total_plans"))
        object.__setattr__(self, "active_plans", require_non_negative_int(self.active_plans, "active_plans"))
        object.__setattr__(self, "total_steps", require_non_negative_int(self.total_steps, "total_steps"))
        object.__setattr__(self, "completed_steps", require_non_negative_int(self.completed_steps, "completed_steps"))
        object.__setattr__(self, "failed_steps", require_non_negative_int(self.failed_steps, "failed_steps"))
        object.__setattr__(self, "total_traces", require_non_negative_int(self.total_traces, "total_traces"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OrchestrationViolation(ContractRecord):
    """An orchestration violation."""

    violation_id: str = ""
    plan_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class CompositionAssessment(ContractRecord):
    """An assessment of orchestration composition health."""

    assessment_id: str = ""
    tenant_id: str = ""
    total_plans: int = 0
    active_plans: int = 0
    completion_rate: float = 0.0
    failure_rate: float = 0.0
    total_violations: int = 0
    assessed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "assessment_id", require_non_empty_text(self.assessment_id, "assessment_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_plans", require_non_negative_int(self.total_plans, "total_plans"))
        object.__setattr__(self, "active_plans", require_non_negative_int(self.active_plans, "active_plans"))
        object.__setattr__(self, "completion_rate", require_unit_float(self.completion_rate, "completion_rate"))
        object.__setattr__(self, "failure_rate", require_unit_float(self.failure_rate, "failure_rate"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.assessed_at, "assessed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class OrchestrationClosureReport(ContractRecord):
    """Closure report for orchestration."""

    report_id: str = ""
    tenant_id: str = ""
    total_plans: int = 0
    total_steps: int = 0
    total_traces: int = 0
    total_decisions: int = 0
    total_violations: int = 0
    total_bindings: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_plans", require_non_negative_int(self.total_plans, "total_plans"))
        object.__setattr__(self, "total_steps", require_non_negative_int(self.total_steps, "total_steps"))
        object.__setattr__(self, "total_traces", require_non_negative_int(self.total_traces, "total_traces"))
        object.__setattr__(self, "total_decisions", require_non_negative_int(self.total_decisions, "total_decisions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        object.__setattr__(self, "total_bindings", require_non_negative_int(self.total_bindings, "total_bindings"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
