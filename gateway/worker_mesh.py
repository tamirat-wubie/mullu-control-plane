"""Gateway networked worker mesh.

Purpose: govern distributed worker execution through leases, scoped operation
admission, budgets, receipts, verification references, and recovery references.
Governance scope: worker identity, tenant lease binding, budget accounting,
receipt emission, and recovery routing.
Dependencies: dataclasses, datetime, threading, and command-spine hashing.
Invariants:
  - No worker dispatch occurs without an active lease.
  - Tenant, capability, operation, budget, and expiry are checked before work.
  - Forbidden operations override allowed operations.
  - Every dispatch returns a command-bound receipt.
  - Worker receipts do not imply terminal closure; verification remains required.
"""

from __future__ import annotations

import threading
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Callable

from gateway.command_spine import canonical_hash


WorkerHandler = Callable[["WorkerDispatchRequest"], "WorkerHandlerResult"]
VALID_WORKER_STATUSES = frozenset({"succeeded", "failed", "rejected"})


@dataclass(frozen=True, slots=True)
class WorkerLeaseBudget:
    """Budget bound for one worker lease."""

    max_operations: int
    max_cost: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.max_operations, int) or isinstance(self.max_operations, bool):
            raise ValueError("max_operations_integer_required")
        if self.max_operations <= 0:
            raise ValueError("positive_operation_budget_required")
        if not isinstance(self.max_cost, int | float) or isinstance(self.max_cost, bool):
            raise ValueError("max_cost_number_required")
        if self.max_cost < 0:
            raise ValueError("nonnegative_max_cost_required")


@dataclass(frozen=True, slots=True)
class WorkerLeaseScope:
    """Resource and sandbox scope for one worker lease."""

    resource_refs: list[str] = field(default_factory=list)
    data_classes: list[str] = field(default_factory=list)
    network_allowlist: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_refs", list(self.resource_refs))
        object.__setattr__(self, "data_classes", list(self.data_classes))
        object.__setattr__(self, "network_allowlist", list(self.network_allowlist))


@dataclass(frozen=True, slots=True)
class WorkerLease:
    """Time-bounded authority grant for one worker."""

    worker_id: str
    capability: str
    tenant_id: str
    lease_id: str
    allowed_operations: list[str]
    forbidden_operations: list[str]
    budget: WorkerLeaseBudget
    scope: WorkerLeaseScope
    timeout_seconds: int
    sandbox: str
    policy_refs: list[str]
    receipt_schema_ref: str
    verification_ref: str
    recovery_ref: str
    expires_at: str
    issued_at: str
    lease_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_operations", list(self.allowed_operations))
        object.__setattr__(self, "forbidden_operations", list(self.forbidden_operations))
        object.__setattr__(self, "policy_refs", list(self.policy_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(frozen=True, slots=True)
class WorkerDispatchRequest:
    """One requested operation against a leased worker."""

    request_id: str
    tenant_id: str
    capability: str
    operation: str
    command_id: str
    input_hash: str
    estimated_cost: float = 0.0
    payload: dict[str, Any] = field(default_factory=dict)
    requested_at: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.estimated_cost, int | float) or isinstance(self.estimated_cost, bool):
            raise ValueError("estimated_cost_number_required")
        if self.estimated_cost < 0:
            raise ValueError("nonnegative_estimated_cost_required")
        object.__setattr__(self, "payload", dict(self.payload))


@dataclass(frozen=True, slots=True)
class WorkerHandlerResult:
    """Result returned by a local worker binding."""

    status: str
    output: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    error: str = ""
    cost: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.cost, int | float) or isinstance(self.cost, bool):
            raise ValueError("worker_cost_number_required")
        if self.cost < 0:
            raise ValueError("nonnegative_worker_cost_required")
        object.__setattr__(self, "output", dict(self.output))
        object.__setattr__(self, "evidence_refs", list(self.evidence_refs))


@dataclass(frozen=True, slots=True)
class WorkerDispatchReceipt:
    """Command-bound receipt emitted for every worker dispatch attempt."""

    receipt_id: str
    request_id: str
    worker_id: str
    capability: str
    tenant_id: str
    lease_id: str
    operation: str
    command_id: str
    status: str
    reason: str
    input_hash: str
    output_hash: str
    evidence_refs: list[str]
    verification_ref: str
    recovery_ref: str
    terminal_closure_required: bool
    dispatched_at: str
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", list(self.evidence_refs))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(slots=True)
class _WorkerBinding:
    lease: WorkerLease
    handler: WorkerHandler
    operation_count: int = 0
    cost_used: float = 0.0
    reserved_cost: float = 0.0


class NetworkedWorkerMesh:
    """Governed dispatch envelope for networked or local worker bindings."""

    def __init__(self, *, clock: Callable[[], str] | None = None) -> None:
        self._clock = clock or _utc_now
        self._bindings: dict[str, _WorkerBinding] = {}
        self._lock = threading.Lock()

    def register_worker(self, lease: WorkerLease, handler: WorkerHandler) -> WorkerLease:
        """Register one worker binding under a stamped lease."""
        validation_error = _validate_lease(lease)
        if validation_error:
            raise ValueError(validation_error)
        stamped = _stamp_lease(lease)
        with self._lock:
            self._bindings[stamped.lease_id] = _WorkerBinding(lease=stamped, handler=handler)
        return stamped

    def dispatch(self, lease_id: str, request: WorkerDispatchRequest) -> WorkerDispatchReceipt:
        """Dispatch one request through lease checks and return a receipt."""
        dispatched_at = self._clock()
        request = _stamp_request(request, requested_at=dispatched_at)
        with self._lock:
            binding = self._bindings.get(lease_id)
            if binding is None:
                return _receipt(
                    request=request,
                    lease=None,
                    worker_id="",
                    status="rejected",
                    reason="lease_not_found",
                    output={},
                    evidence_refs=[],
                    dispatched_at=dispatched_at,
                )
            denial = _admission_denial(binding, request, now=dispatched_at)
            if denial:
                return _receipt(
                    request=request,
                    lease=binding.lease,
                    worker_id=binding.lease.worker_id,
                    status="rejected",
                    reason=denial,
                    output={},
                    evidence_refs=[],
                    dispatched_at=dispatched_at,
                )
            binding.operation_count += 1
            binding.reserved_cost += request.estimated_cost
        try:
            result = binding.handler(request)
        except Exception as exc:  # pragma: no cover - worker exceptions are intentionally bounded.
            result = WorkerHandlerResult(status="failed", error=type(exc).__name__)
        result = _normalize_handler_result(result)
        with self._lock:
            binding.reserved_cost = max(0.0, binding.reserved_cost - request.estimated_cost)
            if _cost_budget_exceeded(binding, result.cost):
                result = replace(result, status="failed", error="worker_cost_budget_exceeded")
            binding.cost_used += result.cost
        if result.status == "succeeded" and not result.evidence_refs:
            result = replace(result, status="failed", error="worker_evidence_required")
        return _receipt(
            request=request,
            lease=binding.lease,
            worker_id=binding.lease.worker_id,
            status=result.status,
            reason=result.error or result.status,
            output=result.output,
            evidence_refs=result.evidence_refs,
            dispatched_at=dispatched_at,
        )

    def read_model(self) -> dict[str, Any]:
        """Return a bounded operator read model for worker leases."""
        with self._lock:
            return {
                "worker_count": len(self._bindings),
                "workers": [
                    {
                        "worker_id": binding.lease.worker_id,
                        "capability": binding.lease.capability,
                        "tenant_id": binding.lease.tenant_id,
                        "lease_id": binding.lease.lease_id,
                        "operation_count": binding.operation_count,
                        "max_operations": binding.lease.budget.max_operations,
                        "max_cost": binding.lease.budget.max_cost,
                        "cost_used": round(binding.cost_used, 6),
                        "reserved_cost": round(binding.reserved_cost, 6),
                        "expires_at": binding.lease.expires_at,
                    }
                    for binding in self._bindings.values()
                ],
            }


def _validate_lease(lease: WorkerLease) -> str:
    if not lease.worker_id:
        return "worker_id_required"
    if not lease.capability:
        return "capability_required"
    if not lease.tenant_id:
        return "tenant_required"
    if not lease.lease_id:
        return "lease_id_required"
    if not lease.allowed_operations:
        return "allowed_operations_required"
    if set(lease.allowed_operations).intersection(lease.forbidden_operations):
        return "operation_cannot_be_allowed_and_forbidden"
    if lease.timeout_seconds <= 0:
        return "positive_timeout_required"
    if not lease.sandbox:
        return "sandbox_required"
    if not lease.receipt_schema_ref:
        return "receipt_schema_ref_required"
    if not lease.verification_ref:
        return "verification_ref_required"
    if not lease.recovery_ref:
        return "recovery_ref_required"
    if not lease.expires_at:
        return "expires_at_required"
    if not lease.issued_at:
        return "issued_at_required"
    try:
        expires_at = _parse_time(lease.expires_at)
        issued_at = _parse_time(lease.issued_at)
    except ValueError:
        return "lease_time_invalid"
    if expires_at <= issued_at:
        return "lease_expiry_must_follow_issue"
    return ""


def _admission_denial(binding: _WorkerBinding, request: WorkerDispatchRequest, *, now: str) -> str:
    lease = binding.lease
    if _is_expired(lease.expires_at, now):
        return "lease_expired"
    if request.tenant_id != lease.tenant_id:
        return "tenant_mismatch"
    if request.capability != lease.capability:
        return "capability_mismatch"
    if request.operation in lease.forbidden_operations:
        return "operation_forbidden"
    if request.operation not in lease.allowed_operations:
        return "operation_not_allowed"
    if not request.request_id:
        return "request_id_required"
    if binding.operation_count >= lease.budget.max_operations:
        return "operation_budget_exhausted"
    if not request.command_id:
        return "command_id_required"
    if not request.input_hash:
        return "input_hash_required"
    if lease.budget.max_cost > 0 and binding.cost_used >= lease.budget.max_cost:
        return "cost_budget_exhausted"
    if lease.budget.max_cost > 0 and binding.cost_used + binding.reserved_cost + request.estimated_cost > lease.budget.max_cost:
        return "cost_budget_exhausted"
    try:
        _parse_time(request.requested_at)
    except ValueError:
        return "requested_at_invalid"
    return ""


def _cost_budget_exceeded(binding: _WorkerBinding, charged_cost: float) -> bool:
    return binding.lease.budget.max_cost > 0 and binding.cost_used + charged_cost > binding.lease.budget.max_cost


def _normalize_handler_result(result: WorkerHandlerResult) -> WorkerHandlerResult:
    if not isinstance(result, WorkerHandlerResult):
        return WorkerHandlerResult(status="failed", error="worker_result_contract_invalid")
    if result.status not in VALID_WORKER_STATUSES:
        return replace(result, status="failed", error="worker_status_invalid")
    return result


def _receipt(
    *,
    request: WorkerDispatchRequest,
    lease: WorkerLease | None,
    worker_id: str,
    status: str,
    reason: str,
    output: dict[str, Any],
    evidence_refs: list[str],
    dispatched_at: str,
) -> WorkerDispatchReceipt:
    output_hash = canonical_hash(output) if output else ""
    receipt = WorkerDispatchReceipt(
        receipt_id="pending",
        request_id=request.request_id,
        worker_id=worker_id,
        capability=request.capability,
        tenant_id=request.tenant_id,
        lease_id=lease.lease_id if lease else "",
        operation=request.operation,
        command_id=request.command_id,
        status=status,
        reason=reason,
        input_hash=request.input_hash,
        output_hash=output_hash,
        evidence_refs=evidence_refs,
        verification_ref=lease.verification_ref if lease else "",
        recovery_ref=lease.recovery_ref if lease else "",
        terminal_closure_required=True,
        dispatched_at=dispatched_at,
        receipt_hash="",
        metadata={
            "receipt_is_not_terminal_closure": True,
            "receipt_schema_ref": lease.receipt_schema_ref if lease else "",
            "estimated_cost": request.estimated_cost,
            "lease_hash": lease.lease_hash if lease else "",
            "worker_receipt_status": status,
        },
    )
    receipt_hash = canonical_hash(asdict(receipt))
    return replace(receipt, receipt_id=f"worker-receipt-{receipt_hash[:16]}", receipt_hash=receipt_hash)


def _stamp_request(request: WorkerDispatchRequest, *, requested_at: str) -> WorkerDispatchRequest:
    if request.requested_at:
        return request
    return replace(request, requested_at=requested_at)


def _stamp_lease(lease: WorkerLease) -> WorkerLease:
    payload = asdict(replace(lease, lease_hash=""))
    return replace(lease, lease_hash=canonical_hash(payload))


def _is_expired(expires_at: str, now: str) -> bool:
    return _parse_time(now) >= _parse_time(expires_at)


def _parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
