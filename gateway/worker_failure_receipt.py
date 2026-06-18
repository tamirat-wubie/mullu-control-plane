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
        """Return the public schema-facing failure receipt payload."""
        completed_step_refs = _metadata_refs(self.metadata, "completed_step_refs")
        failed_step_refs = _metadata_refs(
            self.metadata,
            "failed_step_refs",
            default=(f"step://worker/{self.worker_receipt_id}/failed",),
        )
        partial_effect_refs = _metadata_refs(self.metadata, "partial_effect_refs")
        rollback_action_refs = _metadata_refs(self.metadata, "rollback_action_refs")
        recovery_action_refs = _metadata_refs(
            self.metadata,
            "recovery_action_refs",
            default=(self.recovery_ref,),
        )
        blocked_reason_refs = _metadata_refs(
            self.metadata,
            "blocked_reason_refs",
            default=(f"blocked://worker/{self.worker_receipt_id}/{self.reason}",),
        )
        return {
            "receipt_id": self.receipt_id,
            "receipt_version": "worker_failure_receipt.v1",
            "worker_dispatch_ref": f"receipt://worker-dispatch/{self.worker_receipt_id}",
            "request_id": self.request_id,
            "tenant_id": self.tenant_id,
            "actor_id": str(self.metadata.get("actor_id") or "operator_local_foundation"),
            "worker_id": str(self.metadata.get("worker_id") or self.worker_receipt_id),
            "capability": self.capability,
            "operation": self.operation,
            "command_id": self.command_id,
            "lease_id": self.lease_id,
            "created_at": self.generated_at,
            "solver_outcome": _solver_outcome(self),
            "receipt_state": _receipt_state(self),
            "failure_class": _failure_class(self),
            "effect_status": _effect_status(self),
            "rollback_required": _rollback_required(self),
            "recovery_required": True,
            "failure_summary": {
                "completed_step_count": len(completed_step_refs),
                "failed_step_count": len(failed_step_refs),
                "partial_effect_count": len(partial_effect_refs),
                "rollback_action_count": len(rollback_action_refs),
                "recovery_action_count": len(recovery_action_refs),
                "blocked_reason_count": len(blocked_reason_refs),
                "raw_output_included": False,
                "raw_secret_material_included": False,
            },
            "completed_step_refs": list(completed_step_refs),
            "failed_step_refs": list(failed_step_refs),
            "partial_effect_refs": list(partial_effect_refs),
            "rollback_action_refs": list(rollback_action_refs),
            "recovery_action_refs": list(recovery_action_refs),
            "blocked_reason_refs": list(blocked_reason_refs),
            "governance_guards": {
                "terminal_closure": False,
                "success_claim_allowed": False,
                "execution_authority_renewal_allowed": False,
                "raw_secret_material_included": False,
                "mfidel_atomicity_preserved": True,
                "partial_or_unknown_effect_requires_recovery": True,
            },
            "receipt_envelope": {
                "uao_ref": f"uao://worker-failure/{self.worker_receipt_id}",
                "causal_decision_trace_ref": f"trace://worker-failure/{self.worker_receipt_id}",
                "receipt_ref": f"receipt://worker-failure/{self.receipt_id}",
            },
            "evidence_refs": list(self.evidence_refs)
            or ["schemas/worker_failure_receipt.schema.json"],
            "metadata": {
                "foundation_mode": True,
                "worker_receipt_status": self.metadata.get("worker_receipt_status"),
                "worker_receipt_reason": self.metadata.get("worker_receipt_reason"),
                "source_receipt_hash": self.source_receipt_hash,
                "failure_hash": self.failure_hash,
            },
        }


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
        receipt_id=f"worker-failure-receipt-{failure_hash[:16]}",
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


def _metadata_refs(
    metadata: dict[str, Any],
    key: str,
    *,
    default: tuple[str, ...] = (),
) -> tuple[str, ...]:
    refs = metadata.get(key)
    if refs is None:
        return default
    if isinstance(refs, str):
        return (refs,)
    if isinstance(refs, list | tuple):
        normalized = tuple(str(ref) for ref in refs if str(ref))
        return normalized or default
    return default


def _solver_outcome(receipt: WorkerFailureReceipt) -> str:
    if receipt.failure_state == "rejected_before_handler":
        return "GovernanceBlocked"
    if receipt.failure_state == "partial_completion":
        return "AwaitingEvidence"
    return "AwaitingEvidence"


def _receipt_state(receipt: WorkerFailureReceipt) -> str:
    if receipt.failure_state == "rejected_before_handler":
        return "FAILED_BEFORE_EXECUTION"
    if receipt.failure_state == "partial_completion":
        return "PARTIAL_EXECUTION_RECORDED"
    if receipt.recovery_action == "safe_halt":
        return "SAFE_HALT_RECORDED"
    return "RECOVERY_REQUIRED"


def _failure_class(receipt: WorkerFailureReceipt) -> str:
    reason = receipt.reason.lower()
    if "timeout" in reason:
        return "timeout"
    if receipt.failure_state == "rejected_before_handler":
        return "policy_denial"
    if "budget" in reason:
        return "budget_blocked"
    if "tenant" in reason:
        return "tenant_scope_failure"
    return "worker_error"


def _effect_status(receipt: WorkerFailureReceipt) -> str:
    if receipt.partial_completion:
        return "partial_effect_recorded"
    if receipt.failure_state == "rejected_before_handler":
        return "no_effect_confirmed"
    return "effect_unknown"


def _rollback_required(receipt: WorkerFailureReceipt) -> bool:
    return receipt.partial_completion or receipt.failure_state not in {"rejected_before_handler"}
