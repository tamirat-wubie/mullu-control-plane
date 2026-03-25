"""Purpose: external agent / tool execution runtime contracts.
Governance scope: typed descriptors for execution requests, targets,
    receipts, policies, results, failures, traces, snapshots,
    violations, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every execution references a tenant.
  - External actions are sandboxed and policy-checked.
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
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExecutionStatus(Enum):
    """Status of an external execution."""
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


class ExecutionKind(Enum):
    """Kind of external execution."""
    TOOL = "tool"
    AGENT = "agent"
    API_CALL = "api_call"
    SCRIPT = "script"
    WEBHOOK = "webhook"


class SandboxDisposition(Enum):
    """Sandbox disposition for an execution."""
    SANDBOXED = "sandboxed"
    PRIVILEGED = "privileged"
    ISOLATED = "isolated"
    RESTRICTED = "restricted"


class CredentialMode(Enum):
    """Credential mode for execution."""
    NONE = "none"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    DELEGATED = "delegated"
    EPHEMERAL = "ephemeral"


class RetryDisposition(Enum):
    """Retry disposition for a failed execution."""
    NO_RETRY = "no_retry"
    RETRY_PENDING = "retry_pending"
    RETRIED = "retried"
    EXHAUSTED = "exhausted"


class ExecutionRiskLevel(Enum):
    """Risk level of an execution."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ExecutionRequest(ContractRecord):
    """A request to execute an external tool or agent."""

    request_id: str = ""
    tenant_id: str = ""
    target_id: str = ""
    kind: ExecutionKind = ExecutionKind.TOOL
    status: ExecutionStatus = ExecutionStatus.PENDING
    sandbox: SandboxDisposition = SandboxDisposition.SANDBOXED
    credential_mode: CredentialMode = CredentialMode.NONE
    risk_level: ExecutionRiskLevel = ExecutionRiskLevel.LOW
    requested_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        if not isinstance(self.kind, ExecutionKind):
            raise ValueError("kind must be an ExecutionKind")
        if not isinstance(self.status, ExecutionStatus):
            raise ValueError("status must be an ExecutionStatus")
        if not isinstance(self.sandbox, SandboxDisposition):
            raise ValueError("sandbox must be a SandboxDisposition")
        if not isinstance(self.credential_mode, CredentialMode):
            raise ValueError("credential_mode must be a CredentialMode")
        if not isinstance(self.risk_level, ExecutionRiskLevel):
            raise ValueError("risk_level must be an ExecutionRiskLevel")
        require_datetime_text(self.requested_at, "requested_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionTarget(ContractRecord):
    """A registered external tool or agent target."""

    target_id: str = ""
    tenant_id: str = ""
    display_name: str = ""
    kind: ExecutionKind = ExecutionKind.TOOL
    capability_ref: str = ""
    sandbox_default: SandboxDisposition = SandboxDisposition.SANDBOXED
    credential_mode: CredentialMode = CredentialMode.NONE
    max_retries: int = 0
    timeout_ms: int = 0
    registered_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "display_name", require_non_empty_text(self.display_name, "display_name"))
        if not isinstance(self.kind, ExecutionKind):
            raise ValueError("kind must be an ExecutionKind")
        object.__setattr__(self, "capability_ref", require_non_empty_text(self.capability_ref, "capability_ref"))
        if not isinstance(self.sandbox_default, SandboxDisposition):
            raise ValueError("sandbox_default must be a SandboxDisposition")
        if not isinstance(self.credential_mode, CredentialMode):
            raise ValueError("credential_mode must be a CredentialMode")
        object.__setattr__(self, "max_retries", require_non_negative_int(self.max_retries, "max_retries"))
        object.__setattr__(self, "timeout_ms", require_non_negative_int(self.timeout_ms, "timeout_ms"))
        require_datetime_text(self.registered_at, "registered_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionReceipt(ContractRecord):
    """A receipt for a completed or failed execution."""

    receipt_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    duration_ms: float = 0.0
    output_ref: str = ""
    completed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "receipt_id", require_non_empty_text(self.receipt_id, "receipt_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.status, ExecutionStatus):
            raise ValueError("status must be an ExecutionStatus")
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        object.__setattr__(self, "output_ref", require_non_empty_text(self.output_ref, "output_ref"))
        require_datetime_text(self.completed_at, "completed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionPolicy(ContractRecord):
    """Policy governing an execution target."""

    policy_id: str = ""
    tenant_id: str = ""
    target_id: str = ""
    max_retries: int = 0
    timeout_ms: int = 0
    sandbox_required: SandboxDisposition = SandboxDisposition.SANDBOXED
    credential_mode: CredentialMode = CredentialMode.NONE
    risk_threshold: ExecutionRiskLevel = ExecutionRiskLevel.HIGH
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "policy_id", require_non_empty_text(self.policy_id, "policy_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "target_id", require_non_empty_text(self.target_id, "target_id"))
        object.__setattr__(self, "max_retries", require_non_negative_int(self.max_retries, "max_retries"))
        object.__setattr__(self, "timeout_ms", require_non_negative_int(self.timeout_ms, "timeout_ms"))
        if not isinstance(self.sandbox_required, SandboxDisposition):
            raise ValueError("sandbox_required must be a SandboxDisposition")
        if not isinstance(self.credential_mode, CredentialMode):
            raise ValueError("credential_mode must be a CredentialMode")
        if not isinstance(self.risk_threshold, ExecutionRiskLevel):
            raise ValueError("risk_threshold must be an ExecutionRiskLevel")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionResult(ContractRecord):
    """The output result of an execution."""

    result_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    success: bool = True
    output_summary: str = ""
    confidence: float = 0.0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", require_non_empty_text(self.result_id, "result_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        if not isinstance(self.success, bool):
            raise ValueError("success must be a bool")
        object.__setattr__(self, "output_summary", require_non_empty_text(self.output_summary, "output_summary"))
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionFailure(ContractRecord):
    """A recorded failure of an execution."""

    failure_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    reason: str = ""
    retry_disposition: RetryDisposition = RetryDisposition.NO_RETRY
    retry_count: int = 0
    failed_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "failure_id", require_non_empty_text(self.failure_id, "failure_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        if not isinstance(self.retry_disposition, RetryDisposition):
            raise ValueError("retry_disposition must be a RetryDisposition")
        object.__setattr__(self, "retry_count", require_non_negative_int(self.retry_count, "retry_count"))
        require_datetime_text(self.failed_at, "failed_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionTrace(ContractRecord):
    """A trace record for execution lineage."""

    trace_id: str = ""
    request_id: str = ""
    tenant_id: str = ""
    step_name: str = ""
    duration_ms: float = 0.0
    status: ExecutionStatus = ExecutionStatus.COMPLETED
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", require_non_empty_text(self.trace_id, "trace_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "step_name", require_non_empty_text(self.step_name, "step_name"))
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        if not isinstance(self.status, ExecutionStatus):
            raise ValueError("status must be an ExecutionStatus")
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionSnapshot(ContractRecord):
    """Point-in-time snapshot of execution state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_targets: int = 0
    total_requests: int = 0
    total_receipts: int = 0
    total_failures: int = 0
    total_results: int = 0
    total_traces: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_targets", require_non_negative_int(self.total_targets, "total_targets"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_receipts", require_non_negative_int(self.total_receipts, "total_receipts"))
        object.__setattr__(self, "total_failures", require_non_negative_int(self.total_failures, "total_failures"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_traces", require_non_negative_int(self.total_traces, "total_traces"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionViolation(ContractRecord):
    """A violation detected in execution governance."""

    violation_id: str = ""
    tenant_id: str = ""
    request_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "request_id", require_non_empty_text(self.request_id, "request_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class ExecutionClosureReport(ContractRecord):
    """Closure report for execution runtime."""

    report_id: str = ""
    tenant_id: str = ""
    total_targets: int = 0
    total_requests: int = 0
    total_receipts: int = 0
    total_failures: int = 0
    total_results: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_targets", require_non_negative_int(self.total_targets, "total_targets"))
        object.__setattr__(self, "total_requests", require_non_negative_int(self.total_requests, "total_requests"))
        object.__setattr__(self, "total_receipts", require_non_negative_int(self.total_receipts, "total_receipts"))
        object.__setattr__(self, "total_failures", require_non_negative_int(self.total_failures, "total_failures"))
        object.__setattr__(self, "total_results", require_non_negative_int(self.total_results, "total_results"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
