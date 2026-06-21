"""Worker failure receipt contract helper.

Purpose: project failed or rejected worker dispatch receipts into an explicit
recovery-oriented failure receipt.
Governance scope: worker failure classification, partial effect evidence,
rollback/recovery routing, and non-terminal closure discipline.
Dependencies: dataclasses, datetime, command-spine hashing, and worker mesh
receipts.
Invariants:
  - Successful worker dispatch receipts cannot mint failure receipts.
  - Completed units cannot exceed attempted units.
  - Failure receipts are not terminal closure certificates.
  - Source worker receipt hashes are preserved for causal traceability.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.worker_mesh import WorkerDispatchReceipt


WORKER_FAILURE_RECEIPT_VERSION = "worker_failure_receipt.v1"
VALID_SOLVER_OUTCOMES = frozenset(
    {"AwaitingEvidence", "SafeHalt", "GovernanceBlocked", "SolvedUnverified"}
)
VALID_RECEIPT_STATES = frozenset(
    {
        "FAILED_BEFORE_EXECUTION",
        "PARTIAL_EXECUTION_RECORDED",
        "TIMEOUT_WITH_UNKNOWN_EFFECT",
        "ROLLBACK_REQUIRED",
        "RECOVERY_REQUIRED",
        "SAFE_HALT_RECORDED",
    }
)
VALID_FAILURE_CLASSES = frozenset(
    {
        "timeout",
        "worker_error",
        "policy_denial",
        "tenant_scope_failure",
        "budget_blocked",
        "dependency_unavailable",
        "partial_effect_unknown",
        "rollback_failed",
        "recovery_required",
        "safety_floor",
    }
)
VALID_EFFECT_STATUSES = frozenset(
    {
        "no_effect_confirmed",
        "partial_effect_recorded",
        "effect_unknown",
        "rollback_pending",
        "recovery_pending",
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
    """Schema-shaped recovery receipt for a failed or rejected worker dispatch."""

    receipt_id: str
    receipt_version: str
    worker_dispatch_ref: str
    request_id: str
    tenant_id: str
    actor_id: str
    worker_id: str
    capability: str
    operation: str
    command_id: str
    lease_id: str
    created_at: str
    solver_outcome: str
    receipt_state: str
    failure_class: str
    effect_status: str
    rollback_required: bool
    recovery_required: bool
    failure_summary: dict[str, Any]
    completed_step_refs: tuple[str, ...] = ()
    failed_step_refs: tuple[str, ...] = ()
    partial_effect_refs: tuple[str, ...] = ()
    rollback_action_refs: tuple[str, ...] = ()
    recovery_action_refs: tuple[str, ...] = ()
    blocked_reason_refs: tuple[str, ...] = ()
    governance_guards: dict[str, Any] = field(default_factory=dict)
    receipt_envelope: dict[str, str] = field(default_factory=dict)
    evidence_refs: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.receipt_version != WORKER_FAILURE_RECEIPT_VERSION:
            raise ValueError("worker_failure_receipt_version_invalid")
        if not self.receipt_id.startswith("worker-failure-receipt-"):
            raise ValueError("worker_failure_receipt_id_invalid")
        if self.solver_outcome not in VALID_SOLVER_OUTCOMES:
            raise ValueError("worker_failure_solver_outcome_invalid")
        if self.receipt_state not in VALID_RECEIPT_STATES:
            raise ValueError("worker_failure_receipt_state_invalid")
        if self.failure_class not in VALID_FAILURE_CLASSES:
            raise ValueError("worker_failure_class_invalid")
        if self.effect_status not in VALID_EFFECT_STATUSES:
            raise ValueError("worker_failure_effect_status_invalid")
        if not self.failed_step_refs:
            raise ValueError("worker_failure_failed_step_refs_required")
        if self.rollback_required and not self.rollback_action_refs:
            raise ValueError("worker_failure_rollback_refs_required")
        if self.recovery_required and not (self.recovery_action_refs or self.blocked_reason_refs):
            raise ValueError("worker_failure_recovery_refs_required")
        if self.governance_guards.get("terminal_closure") is not False:
            raise ValueError("worker_failure_terminal_closure_forbidden")
        if self.governance_guards.get("success_claim_allowed") is not False:
            raise ValueError("worker_failure_success_claim_forbidden")
        if self.governance_guards.get("execution_authority_renewal_allowed") is not False:
            raise ValueError("worker_failure_execution_authority_renewal_forbidden")
        if self.governance_guards.get("raw_secret_material_included") is not False:
            raise ValueError("worker_failure_raw_secret_forbidden")
        if self.governance_guards.get("mfidel_atomicity_preserved") is not True:
            raise ValueError("worker_failure_mfidel_atomicity_required")
        if self.governance_guards.get("partial_or_unknown_effect_requires_recovery") is not True:
            raise ValueError("worker_failure_recovery_guard_required")
        object.__setattr__(self, "completed_step_refs", tuple(self.completed_step_refs))
        object.__setattr__(self, "failed_step_refs", tuple(self.failed_step_refs))
        object.__setattr__(self, "partial_effect_refs", tuple(self.partial_effect_refs))
        object.__setattr__(self, "rollback_action_refs", tuple(self.rollback_action_refs))
        object.__setattr__(self, "recovery_action_refs", tuple(self.recovery_action_refs))
        object.__setattr__(self, "blocked_reason_refs", tuple(self.blocked_reason_refs))
        object.__setattr__(self, "evidence_refs", tuple(self.evidence_refs))
        object.__setattr__(self, "failure_summary", dict(self.failure_summary))
        object.__setattr__(self, "governance_guards", dict(self.governance_guards))
        object.__setattr__(self, "receipt_envelope", dict(self.receipt_envelope))
        object.__setattr__(self, "metadata", dict(self.metadata))

    @property
    def worker_receipt_id(self) -> str:
        """Return the source worker receipt id preserved in metadata."""
        return str(self.metadata.get("worker_receipt_id", ""))

    @property
    def failure_state(self) -> str:
        """Return the compact legacy state used by operator read models."""
        return str(self.metadata.get("legacy_failure_state", _legacy_failure_state(self.receipt_state)))

    @property
    def recovery_action(self) -> str:
        """Return the compact recovery action used by operator read models."""
        return str(self.metadata.get("legacy_recovery_action", "operator_review"))

    @property
    def source_receipt_hash(self) -> str:
        """Return the causal hash of the source worker receipt."""
        return str(self.metadata.get("source_receipt_hash", ""))

    @property
    def failure_hash(self) -> str:
        """Return the deterministic hash used to derive the failure receipt id."""
        return str(self.metadata.get("failure_hash", ""))

    @property
    def terminal_closure_required(self) -> bool:
        """Failure receipts require a separate terminal closure chain."""
        return True

    @property
    def receipt_is_not_terminal_closure(self) -> bool:
        """Failure receipts cannot serve as terminal closure certificates."""
        return True

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible WorkerFailureReceipt schema payload."""
        payload = asdict(self)
        for field_name in (
            "completed_step_refs",
            "failed_step_refs",
            "partial_effect_refs",
            "rollback_action_refs",
            "recovery_action_refs",
            "blocked_reason_refs",
            "evidence_refs",
        ):
            payload[field_name] = list(payload[field_name])
        return payload


def build_worker_failure_receipt(
    worker_receipt: WorkerDispatchReceipt,
    *,
    attempted_units: int = 0,
    completed_units: int = 0,
    recovery_action: str | None = None,
    generated_at: str | None = None,
    actor_id: str = "operator_local_foundation",
    metadata: dict[str, Any] | None = None,
) -> WorkerFailureReceipt:
    """Build a schema-valid, hash-bound failure receipt from a worker dispatch."""
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
    if recovery_action is not None and recovery_action not in VALID_RECOVERY_ACTIONS:
        raise ValueError("worker_failure_recovery_action_invalid")

    partial_completion = completed_units > 0
    legacy_failure_state = _failure_state(worker_receipt, partial_completion=partial_completion)
    resolved_recovery_action = recovery_action or _default_recovery_action(legacy_failure_state)
    generated = generated_at or _utc_timestamp()
    receipt_state = _receipt_state(worker_receipt, legacy_failure_state=legacy_failure_state)
    failure_class = _failure_class(worker_receipt.reason, legacy_failure_state=legacy_failure_state)
    effect_status = _effect_status(receipt_state)
    rollback_required = receipt_state in {"PARTIAL_EXECUTION_RECORDED", "ROLLBACK_REQUIRED"}
    recovery_required = receipt_state in {
        "PARTIAL_EXECUTION_RECORDED",
        "TIMEOUT_WITH_UNKNOWN_EFFECT",
        "ROLLBACK_REQUIRED",
        "RECOVERY_REQUIRED",
        "SAFE_HALT_RECORDED",
    }
    completed_step_refs = tuple(
        f"step://worker/{worker_receipt.request_id}/completed-{index}"
        for index in range(1, completed_units + 1)
    )
    failed_step_refs = (f"step://worker/{worker_receipt.request_id}/failed-{_slug(worker_receipt.reason or worker_receipt.status)}",)
    partial_effect_refs = (
        (f"effect://worker/{worker_receipt.request_id}/partial-completion",)
        if partial_completion
        else ()
    )
    rollback_action_refs = (
        (f"rollback://worker/{worker_receipt.request_id}/remove-partial-effect",)
        if rollback_required
        else ()
    )
    recovery_action_refs = (
        (f"recovery://worker/{worker_receipt.request_id}/{_slug(resolved_recovery_action)}",)
        if recovery_required
        else ()
    )
    blocked_reason_refs = (f"blocked://worker/{worker_receipt.request_id}/{_slug(worker_receipt.reason or worker_receipt.status)}",)
    base_metadata = {
        "worker_receipt_id": worker_receipt.receipt_id,
        "worker_receipt_status": worker_receipt.status,
        "worker_receipt_reason": worker_receipt.reason,
        "source_receipt_hash": worker_receipt.receipt_hash,
        "legacy_failure_state": legacy_failure_state,
        "legacy_recovery_action": resolved_recovery_action,
        "recovery_ref": worker_receipt.recovery_ref,
        **(metadata or {}),
    }
    base_payload: dict[str, Any] = {
        "receipt_id": "worker-failure-receipt-pending",
        "receipt_version": WORKER_FAILURE_RECEIPT_VERSION,
        "worker_dispatch_ref": f"receipt://worker-dispatch/{worker_receipt.receipt_id}",
        "request_id": worker_receipt.request_id,
        "tenant_id": worker_receipt.tenant_id,
        "actor_id": actor_id,
        "worker_id": worker_receipt.worker_id or "unbound-worker",
        "capability": worker_receipt.capability,
        "operation": worker_receipt.operation,
        "command_id": worker_receipt.command_id,
        "lease_id": worker_receipt.lease_id or "unbound-lease",
        "created_at": generated,
        "solver_outcome": _solver_outcome(receipt_state),
        "receipt_state": receipt_state,
        "failure_class": failure_class,
        "effect_status": effect_status,
        "rollback_required": rollback_required,
        "recovery_required": recovery_required,
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
        "completed_step_refs": completed_step_refs,
        "failed_step_refs": failed_step_refs,
        "partial_effect_refs": partial_effect_refs,
        "rollback_action_refs": rollback_action_refs,
        "recovery_action_refs": recovery_action_refs,
        "blocked_reason_refs": blocked_reason_refs,
        "governance_guards": {
            "terminal_closure": False,
            "success_claim_allowed": False,
            "execution_authority_renewal_allowed": False,
            "raw_secret_material_included": False,
            "mfidel_atomicity_preserved": True,
            "partial_or_unknown_effect_requires_recovery": True,
        },
        "receipt_envelope": {
            "uao_ref": f"uao://worker-failure/{worker_receipt.command_id}/{worker_receipt.request_id}",
            "causal_decision_trace_ref": f"trace://worker-failure/{worker_receipt.command_id}/{worker_receipt.request_id}",
            "receipt_ref": "receipt://worker-failure/pending",
        },
        "evidence_refs": tuple(worker_receipt.evidence_refs) or (
            f"worker-dispatch://{worker_receipt.receipt_id}",
        ),
        "metadata": base_metadata,
    }
    failure_hash = canonical_hash(base_payload)
    receipt_id = f"worker-failure-receipt-{failure_hash[:16]}"
    final_payload = {
        **base_payload,
        "receipt_id": receipt_id,
        "receipt_envelope": {
            **base_payload["receipt_envelope"],
            "receipt_ref": f"receipt://worker-failure/{receipt_id}",
        },
        "metadata": {
            **base_metadata,
            "failure_hash": failure_hash,
        },
    }
    return WorkerFailureReceipt(**final_payload)


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
    if failure_state in {"failed_after_handler", "failed_during_handler"}:
        return "operator_review"
    return "operator_review"


def _receipt_state(worker_receipt: WorkerDispatchReceipt, *, legacy_failure_state: str) -> str:
    if legacy_failure_state == "partial_completion":
        return "PARTIAL_EXECUTION_RECORDED"
    if legacy_failure_state == "rejected_before_handler":
        return "FAILED_BEFORE_EXECUTION"
    if "timeout" in (worker_receipt.reason or "").lower():
        return "TIMEOUT_WITH_UNKNOWN_EFFECT"
    if worker_receipt.reason == "safety_floor":
        return "SAFE_HALT_RECORDED"
    if legacy_failure_state in {"failed_after_handler", "failed_during_handler"}:
        return "RECOVERY_REQUIRED"
    return "RECOVERY_REQUIRED"


def _solver_outcome(receipt_state: str) -> str:
    if receipt_state == "FAILED_BEFORE_EXECUTION":
        return "GovernanceBlocked"
    if receipt_state == "SAFE_HALT_RECORDED":
        return "SafeHalt"
    return "AwaitingEvidence"


def _failure_class(reason: str, *, legacy_failure_state: str) -> str:
    normalized = (reason or legacy_failure_state).lower()
    if "timeout" in normalized:
        return "timeout"
    if "tenant" in normalized:
        return "tenant_scope_failure"
    if "budget" in normalized or "cost" in normalized:
        return "budget_blocked"
    if "lease_not_found" in normalized or "lease_expired" in normalized:
        return "dependency_unavailable"
    if legacy_failure_state == "rejected_before_handler":
        return "policy_denial"
    if "partial" in normalized:
        return "partial_effect_unknown"
    if "safety" in normalized:
        return "safety_floor"
    if "rollback" in normalized:
        return "rollback_failed"
    if "recovery" in normalized:
        return "recovery_required"
    return "worker_error"


def _effect_status(receipt_state: str) -> str:
    if receipt_state == "FAILED_BEFORE_EXECUTION":
        return "no_effect_confirmed"
    if receipt_state == "PARTIAL_EXECUTION_RECORDED":
        return "partial_effect_recorded"
    if receipt_state == "ROLLBACK_REQUIRED":
        return "rollback_pending"
    if receipt_state == "SAFE_HALT_RECORDED":
        return "recovery_pending"
    return "effect_unknown"


def _legacy_failure_state(receipt_state: str) -> str:
    if receipt_state == "PARTIAL_EXECUTION_RECORDED":
        return "partial_completion"
    if receipt_state == "FAILED_BEFORE_EXECUTION":
        return "rejected_before_handler"
    return "failed_during_handler"


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value.strip())
    return "-".join(part for part in slug.split("-") if part) or "unknown"


def _utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
