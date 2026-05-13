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
from typing import Any, Mapping, TypeVar, cast

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_int,
)


ContractT = TypeVar("ContractT")


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _require_optional_text(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    return require_non_empty_text(value, field_name)


def _freeze_text_mapping(value: Any, field_name: str) -> Mapping[str, str]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    normalized: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name} must contain only non-empty string keys")
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{field_name} must contain only non-empty string values")
        normalized[key] = item
    return cast(Mapping[str, str], freeze_value(normalized))


def _freeze_contract_array(
    values: Any,
    field_name: str,
    record_type: type[ContractT],
    record_type_name: str,
) -> tuple[ContractT, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, (tuple, list)):
        raise ValueError(f"{field_name} must be an array")
    normalized: list[ContractT] = []
    for value in values:
        if not isinstance(value, record_type):
            raise ValueError(f"{field_name} must contain only {record_type_name} instances")
        normalized.append(value)
    return cast(tuple[ContractT, ...], freeze_value(normalized))


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
        object.__setattr__(self, "policy_pack_id", _require_optional_text(self.policy_pack_id, "policy_pack_id"))
        object.__setattr__(
            self,
            "policy_pack_version",
            _require_optional_text(self.policy_pack_version, "policy_pack_version"),
        )
        object.__setattr__(
            self,
            "approval_actor_id",
            _require_optional_text(self.approval_actor_id, "approval_actor_id"),
        )


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
        object.__setattr__(self, "bindings", _freeze_text_mapping(self.bindings, "bindings"))


@dataclass(frozen=True, slots=True)
class RunbookStepResult(ContractRecord):
    """Result of executing one step of a runbook."""

    step_index: int
    step_name: str
    succeeded: bool
    error_message: str | None = None
    execution_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "step_index", require_non_negative_int(self.step_index, "step_index"))
        object.__setattr__(self, "step_name", require_non_empty_text(self.step_name, "step_name"))
        object.__setattr__(self, "succeeded", _require_bool(self.succeeded, "succeeded"))
        object.__setattr__(self, "error_message", _require_optional_text(self.error_message, "error_message"))
        object.__setattr__(self, "execution_id", _require_optional_text(self.execution_id, "execution_id"))


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
        object.__setattr__(self, "severity", require_non_empty_text(self.severity, "severity"))


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
        object.__setattr__(
            self,
            "step_results",
            _freeze_contract_array(
                self.step_results,
                "step_results",
                RunbookStepResult,
                "RunbookStepResult",
            ),
        )
        object.__setattr__(
            self,
            "drift_records",
            _freeze_contract_array(
                self.drift_records,
                "drift_records",
                DriftRecord,
                "DriftRecord",
            ),
        )
        if self.started_at is not None:
            object.__setattr__(self, "started_at", require_datetime_text(self.started_at, "started_at"))
        if self.finished_at is not None:
            object.__setattr__(self, "finished_at", require_datetime_text(self.finished_at, "finished_at"))
        object.__setattr__(self, "error_message", _require_optional_text(self.error_message, "error_message"))

    @property
    def has_drift(self) -> bool:
        return len(self.drift_records) > 0

    @property
    def succeeded(self) -> bool:
        return self.status is RunbookExecutionStatus.SUCCEEDED
