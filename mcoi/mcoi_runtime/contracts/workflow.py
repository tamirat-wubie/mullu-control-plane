"""Purpose: canonical cross-plane workflow runtime contract mapping.
Governance scope: workflow descriptor, stage, binding, transition, execution, and verification typing.
Dependencies: docs/21_workflow_runtime.md, shared contract base helpers, error taxonomy.
Invariants:
  - Every workflow carries explicit identity and a non-empty stage graph.
  - Stages are typed and may reference skills but impose no execution semantics.
  - Bindings reference only stages that exist in the same descriptor.
  - Frozen dataclasses ensure immutability after construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_datetime_text, require_non_empty_text

# Re-export legacy names for backward compatibility with existing imports.
# The old Workflow/WorkflowStep types are superseded by WorkflowDescriptor/WorkflowStage.

# --- Classification enums ---


class WorkflowStatus(StrEnum):
    """Lifecycle state of a workflow execution."""

    DRAFT = "draft"
    VALIDATED = "validated"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SUSPENDED = "suspended"


class StageType(StrEnum):
    """What kind of work a workflow stage performs."""

    SKILL_EXECUTION = "skill_execution"
    APPROVAL_GATE = "approval_gate"
    OBSERVATION = "observation"
    COMMUNICATION = "communication"
    WAIT_FOR_EVENT = "wait_for_event"


class StageStatus(StrEnum):
    """Terminal or in-progress status of a single stage."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class TransitionType(StrEnum):
    """How control flows between stages."""

    SEQUENTIAL = "sequential"
    CONDITIONAL = "conditional"
    ON_FAILURE = "on_failure"


# --- Contract types ---


@dataclass(frozen=True, slots=True)
class WorkflowStage(ContractRecord):
    """One unit of work within a workflow."""

    stage_id: str
    stage_type: StageType
    skill_id: str | None = None
    description: str = ""
    predecessors: tuple[str, ...] = ()
    timeout_seconds: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_id", require_non_empty_text(self.stage_id, "stage_id"))
        if not isinstance(self.stage_type, StageType):
            raise ValueError("stage_type must be a StageType value")
        if self.skill_id is not None:
            object.__setattr__(self, "skill_id", require_non_empty_text(self.skill_id, "skill_id"))
        object.__setattr__(self, "predecessors", freeze_value(list(self.predecessors)))
        for idx, pred in enumerate(self.predecessors):
            require_non_empty_text(pred, f"predecessors[{idx}]")
        if self.timeout_seconds is not None:
            if not isinstance(self.timeout_seconds, int) or self.timeout_seconds <= 0:
                raise ValueError("timeout_seconds must be a positive integer")


@dataclass(frozen=True, slots=True)
class WorkflowBinding(ContractRecord):
    """Data-flow edge from one stage's output to another stage's input."""

    binding_id: str
    source_stage_id: str
    source_output_key: str
    target_stage_id: str
    target_input_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "binding_id", require_non_empty_text(self.binding_id, "binding_id"))
        object.__setattr__(self, "source_stage_id", require_non_empty_text(self.source_stage_id, "source_stage_id"))
        object.__setattr__(self, "source_output_key", require_non_empty_text(self.source_output_key, "source_output_key"))
        object.__setattr__(self, "target_stage_id", require_non_empty_text(self.target_stage_id, "target_stage_id"))
        object.__setattr__(self, "target_input_key", require_non_empty_text(self.target_input_key, "target_input_key"))


@dataclass(frozen=True, slots=True)
class WorkflowDescriptor(ContractRecord):
    """Full identity and structure of a workflow."""

    workflow_id: str
    name: str
    description: str = ""
    stages: tuple[WorkflowStage, ...] = ()
    bindings: tuple[WorkflowBinding, ...] = ()
    created_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "workflow_id", require_non_empty_text(self.workflow_id, "workflow_id"))
        object.__setattr__(self, "name", require_non_empty_text(self.name, "name"))
        if not self.stages:
            raise ValueError("stages must contain at least one stage")
        object.__setattr__(self, "stages", freeze_value(list(self.stages)))
        object.__setattr__(self, "bindings", freeze_value(list(self.bindings)))
        # Validate all stages are WorkflowStage instances
        for stage in self.stages:
            if not isinstance(stage, WorkflowStage):
                raise ValueError("every stage must be a WorkflowStage instance")
        object.__setattr__(self, "created_at", require_datetime_text(self.created_at, "created_at"))


@dataclass(frozen=True, slots=True)
class WorkflowTransition(ContractRecord):
    """Typed edge describing how control flows between stages."""

    from_stage_id: str
    to_stage_id: str
    transition_type: TransitionType
    condition: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "from_stage_id", require_non_empty_text(self.from_stage_id, "from_stage_id"))
        object.__setattr__(self, "to_stage_id", require_non_empty_text(self.to_stage_id, "to_stage_id"))
        if not isinstance(self.transition_type, TransitionType):
            raise ValueError("transition_type must be a TransitionType value")


@dataclass(frozen=True, slots=True)
class StageExecutionResult(ContractRecord):
    """Result of executing one stage within a workflow."""

    stage_id: str
    status: StageStatus
    output: Mapping[str, Any] = field(default_factory=dict)
    error: Any = None  # StructuredError or None — typed loosely to avoid circular import
    started_at: str = ""
    completed_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "stage_id", require_non_empty_text(self.stage_id, "stage_id"))
        if not isinstance(self.status, StageStatus):
            raise ValueError("status must be a StageStatus value")
        object.__setattr__(self, "output", freeze_value(self.output))
        object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        object.__setattr__(self, "completed_at", require_datetime_text(self.completed_at, "completed_at"))


@dataclass(frozen=True, slots=True)
class WorkflowExecutionRecord(ContractRecord):
    """Full trace of a workflow run including per-stage results."""

    workflow_id: str
    execution_id: str
    status: WorkflowStatus
    stage_results: tuple[StageExecutionResult, ...] = ()
    started_at: str = ""
    completed_at: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "workflow_id", require_non_empty_text(self.workflow_id, "workflow_id"))
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        if not isinstance(self.status, WorkflowStatus):
            raise ValueError("status must be a WorkflowStatus value")
        object.__setattr__(self, "stage_results", freeze_value(list(self.stage_results)))


@dataclass(frozen=True, slots=True)
class WorkflowVerificationRecord(ContractRecord):
    """Post-execution verification of a completed workflow."""

    execution_id: str
    verified: bool
    mismatch_reasons: tuple[str, ...] = ()
    verified_at: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "execution_id", require_non_empty_text(self.execution_id, "execution_id"))
        if not isinstance(self.verified, bool):
            raise ValueError("verified must be a boolean")
        object.__setattr__(self, "mismatch_reasons", freeze_value(list(self.mismatch_reasons)))
        object.__setattr__(self, "verified_at", require_datetime_text(self.verified_at, "verified_at"))


# --- Legacy compatibility aliases ---
# The original Workflow and WorkflowStep names are kept so existing
# "from .workflow import Workflow, WorkflowStep" in __init__.py still works.

Workflow = WorkflowDescriptor
WorkflowStep = WorkflowStage
