"""Purpose: canonical runbook execution and drift detection contracts.
Governance scope: runbook execution request, record, step result, decision, and drift typing.
Dependencies: shared contract base helpers.
Invariants:
  - Only admitted runbooks may be executed.
  - Execution respects current policy/autonomy/provider conditions.
  - Drift from baseline is explicit and typed.
  - Each execution step is individually recorded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping

from ._base import ContractRecord, freeze_value, require_non_empty_text


class RunbookExecutionStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED_POLICY = "blocked_policy"
    BLOCKED_AUTONOMY = "blocked_autonomy"
    BLOCKED_PROVIDER = "blocked_provider"
    BLOCKED_LIFECYCLE = "blocked_lifecycle"
    STEP_FAILED = "step_failed"
    DRIFT_DETECTED = "drift_detected"


class DriftType(StrEnum):
    PROVIDER_MISMATCH = "provider_mismatch"
    AUTONOMY_MISMATCH = "autonomy_mismatch"
    POLICY_PACK_MISMATCH = "policy_pack_mismatch"
    VERIFICATION_MISMATCH = "verification_mismatch"
    STEP_COUNT_MISMATCH = "step_count_mismatch"
    OUTCOME_MISMATCH = "outcome_mismatch"


@dataclass(frozen=True, slots=True)
class RunbookExecutionContext(ContractRecord):
    """Runtime context bound to a runbook execution."""

    operator_id: str
    autonomy_mode: str
    policy_pack_id: str | None = None
    policy_pack_version: str | None = None
    approval_actor_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "operator_id", require_non_empty_text(self.operator_id, "operator_id"))
        object.__setattr__(self, "autonomy_mode", require_non_empty_text(self.autonomy_mode, "autonomy_mode"))


@dataclass(frozen=True, slots=True)
class RunbookExecutionRequest(ContractRecord):
    """Request to execute an admitted runbook."""

    request_id: str
    runbook_id: str
    context: RunbookExecutionContext
    bindings: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "runbook_id", require_non_empty_text(self.runbook_id, "runbook_id"))
        if not isinstance(self.context, RunbookExecutionContext):
            raise ValueError("context must be a RunbookExecutionContext instance")
        object.__setattr__(self, "bindings", freeze_value(self.bindings))


@dataclass(frozen=True, slots=True)
class RunbookStepResult(ContractRecord):
    """Result of executing one step of a runbook."""

    step_index: int
    step_name: str
    succeeded: bool
    error_message: str | None = None
    execution_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_name", require_non_empty_text(self.step_name, "step_name"))
        if not isinstance(self.step_index, int) or self.step_index < 0:
            raise ValueError("step_index must be a non-negative integer")


@dataclass(frozen=True, slots=True)
class DriftRecord(ContractRecord):
    """One detected drift from baseline behavior."""

    drift_type: DriftType
    field_name: str
    baseline_value: str
    current_value: str
    severity: str = "warning"

    def __post_init__(self) -> None:
        if not isinstance(self.drift_type, DriftType):
            raise ValueError("drift_type must be a DriftType value")
        object.__setattr__(self, "field_name", require_non_empty_text(self.field_name, "field_name"))
        object.__setattr__(self, "baseline_value", require_non_empty_text(self.baseline_value, "baseline_value"))
        object.__setattr__(self, "current_value", require_non_empty_text(self.current_value, "current_value"))


@dataclass(frozen=True, slots=True)
class RunbookExecutionRecord(ContractRecord):
    """Full record of a runbook execution attempt."""

    record_id: str
    runbook_id: str
    request_id: str
    status: RunbookExecutionStatus
    context: RunbookExecutionContext
    step_results: tuple[RunbookStepResult, ...] = ()
    drift_records: tuple[DriftRecord, ...] = ()
    started_at: str | None = None
    finished_at: str | None = None
    error_message: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "record_id", require_non_empty_text(self.record_id, "record_id"))
        object.__setattr__(self, "runbook_id", require_non_empty_text(self.runbook_id, "runbook_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        if not isinstance(self.status, RunbookExecutionStatus):
            raise ValueError("status must be a RunbookExecutionStatus value")
        if not isinstance(self.context, RunbookExecutionContext):
            raise ValueError("context must be a RunbookExecutionContext instance")
        object.__setattr__(self, "step_results", freeze_value(list(self.step_results)))
        object.__setattr__(self, "drift_records", freeze_value(list(self.drift_records)))

    @property
    def has_drift(self) -> bool:
        return len(self.drift_records) > 0

    @property
    def succeeded(self) -> bool:
        return self.status is RunbookExecutionStatus.SUCCEEDED
