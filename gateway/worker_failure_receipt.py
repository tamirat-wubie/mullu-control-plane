"""Worker failure receipt contract helper.

Purpose: project failed or rejected worker dispatch receipts into an explicit
recovery-oriented failure receipt.
Governance scope: worker failure classification, partial completion evidence,
recovery routing, and non-terminal closure discipline.
Dependencies: dataclasses, datetime, command-spine hashing, and worker mesh
receipts.
Invariants:
  - Successful worker dispatch receipts cannot mint failure receipts.
  - Completed units cannot exceed attempted units.
  - Failure receipts are not terminal closure certificates.
  - Source worker receipt hashes are preserved for causal traceability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.worker_mesh import WorkerDispatchReceipt


WORKER_FAILURE_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:worker-failure-receipt:1"
VALID_FAILURE_STATES = frozenset(
    {
        "rejected_before_handler",
        "failed_during_handler",
        "failed_after_handler",
        "partial_completion",
        "unknown_failure",
    }
)
VALID_RECOVERY_ACTIONS = frozenset(
    {"retry_same_lease", "retry_new_lease", "operator_review", "safe_halt", "no_retry"}
)
_POST_HANDLER_FAILURE_REASONS = frozenset(
    {
        "worker_evidence_required",
        "worker_status_invalid",
        "worker_cost_budget_exceeded",
    }
)


@dataclass(frozen=True, slots=True)
class WorkerFailureReceipt:
    """Recovery-oriented receipt for a failed or rejected worker dispatch."""

    schema_ref: str
    receipt_id: str
    worker_receipt_id: str
    request_id: str
    command_id: str
    capability: str
    operation: str
    tenant_id: str
    lease_id: str
    failure_state: str
    reason: str
    partial_completion: bool
    attempted_units: int
    completed_units: int
    recovery_action: str
    recovery_ref: str
    evidence_refs: tuple[str, ...]
    terminal_closure_required: bool
    receipt_is_not_terminal_closure: bool
    generated_at: str
    source_receipt_hash: str
    failure_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.schema_ref != WORKER_FAILURE_RECEIPT_SCHEMA_REF:
            raise ValueError("worker_failure_schema_ref_invalid")
        if self.failure_state not in VALID_FAILURE_STATES:
            raise ValueError("worker_failure_state_invalid")
        if self.recovery_action not in VALID_RECOVERY_ACTIONS:
            raise ValueError("worker_failure_recovery_action_invalid")
        if self.attempted_units < 0 or self.completed_units < 0:
            raise ValueError("worker_failure_units_nonnegative_required")
        if self.completed_units > self.attempted_units:
            raise ValueError("worker_failure_completed_units_exceed_attempted")
        if self.terminal_closure_required is not True:
            raise ValueError("worker_failure_terminal_closure_required")
        if self.receipt_is_not_terminal_closure is not True:
            raise ValueError("worker_failure_non_terminal_flag_required")
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible failure receipt payload."""
        payload = asdict(self)
        payload["evidence_refs"] = list(self.evidence_refs)
        return payload


def build_worker_failure_receipt(
    worker_receipt: WorkerDispatchReceipt,
    *,
    attempted_units: int = 0,
    completed_units: int = 0,
    recovery_action: str | None = None,
    generated_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> WorkerFailureReceipt:
    """Build a hash-bound failure receipt from a failed worker dispatch."""
    if worker_receipt.status == "succeeded":
        raise ValueError("worker_failure_receipt_requires_failed_or_rejected_status")
    if worker_receipt.status not in {"failed", "rejected"}:
        raise ValueError("worker_failure_receipt_status_invalid")
    if not worker_receipt.receipt_hash:
        raise ValueError("worker_failure_source_receipt_hash_required")
    if attempted_units < 0 or completed_units < 0:
        raise ValueError("worker_failure_units_nonnegative_required")
    if completed_units > attempted_units:
        raise ValueError("worker_failure_completed_units_exceed_attempted")

    partial_completion = completed_units > 0
    failure_state = _failure_state(worker_receipt, partial_completion=partial_completion)
    resolved_recovery_action = recovery_action or _default_recovery_action(failure_state)
    generated = generated_at or _utc_timestamp()
    receipt = WorkerFailureReceipt(
        schema_ref=WORKER_FAILURE_RECEIPT_SCHEMA_REF,
        receipt_id="pending",
        worker_receipt_id=worker_receipt.receipt_id,
        request_id=worker_receipt.request_id,
        command_id=worker_receipt.command_id,
        capability=worker_receipt.capability,
        operation=worker_receipt.operation,
        tenant_id=worker_receipt.tenant_id,
        lease_id=worker_receipt.lease_id,
        failure_state=failure_state,
        reason=worker_receipt.reason or worker_receipt.status,
        partial_completion=partial_completion,
        attempted_units=attempted_units,
        completed_units=completed_units,
        recovery_action=resolved_recovery_action,
        recovery_ref=worker_receipt.recovery_ref or "recovery:operator-review",
        evidence_refs=tuple(worker_receipt.evidence_refs),
        terminal_closure_required=True,
        receipt_is_not_terminal_closure=True,
        generated_at=generated,
        source_receipt_hash=worker_receipt.receipt_hash,
        metadata={
            "worker_receipt_status": worker_receipt.status,
            "worker_receipt_reason": worker_receipt.reason,
            **(metadata or {}),
        },
    )
    failure_hash = canonical_hash(asdict(receipt))
    return replace(
        receipt,
        receipt_id=f"worker-failure-{failure_hash[:16]}",
        failure_hash=failure_hash,
    )


def _failure_state(worker_receipt: WorkerDispatchReceipt, *, partial_completion: bool) -> str:
    if partial_completion:
        return "partial_completion"
    if worker_receipt.status == "rejected":
        return "rejected_before_handler"
    if worker_receipt.reason in _POST_HANDLER_FAILURE_REASONS:
        return "failed_after_handler"
    if worker_receipt.status == "failed":
        return "failed_during_handler"
    return "unknown_failure"


def _default_recovery_action(failure_state: str) -> str:
    if failure_state == "partial_completion":
        return "safe_halt"
    if failure_state == "rejected_before_handler":
        return "no_retry"
    if failure_state == "failed_after_handler":
        return "operator_review"
    if failure_state == "failed_during_handler":
        return "operator_review"
    return "operator_review"


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
