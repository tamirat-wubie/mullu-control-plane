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
PHYSICAL_ACTION_RECEIPT_PAYLOAD_KEY = "physical_action_receipt"
PHYSICAL_ACTION_RECEIPT_SCHEMA_REF = "urn:mullusi:schema:physical-action-receipt:1"
WORKER_MESH_SCHEMA_REF = "urn:mullusi:schema:worker-mesh:1"
VALID_EVIDENCE_STAGES = (
    "PRECHECK",
    "STARTED",
    "CHECKPOINT",
    "DELTA_PROPOSED",
    "VALIDATED",
    "COMMITTED",
    "POSTCHECK",
    "CLOSED",
)
VALID_RESOURCE_ACCESS_MODES = (
    "OBSERVE",
    "READ",
    "APPEND",
    "WRITE",
    "DELETE",
    "PUBLISH",
    "EXTERNAL_SEND",
    "FINANCIAL_MOVE",
    "LEGAL_COMMIT",
    "READ_SHARED",
    "WRITE_EXCLUSIVE",
    "APPEND_ONLY",
    "OBSERVE_ONLY",
    "SIMULATE_ONLY",
    "HUMAN_APPROVAL_REQUIRED",
)
VALID_RESOURCE_CONFLICT_CLASSES = (
    "NO_CONFLICT",
    "READ_SHARED",
    "WRITE_EXCLUSIVE",
    "APPEND_ORDERED",
    "VERSIONED_MERGE",
    "HUMAN_APPROVAL_REQUIRED",
    "IRREVERSIBLE",
)
VALID_IDEMPOTENCY_CLASSES = (
    "SAFE_REPEAT",
    "SAFE_WITH_KEY",
    "RETRY_AFTER_REBASE",
    "MANUAL_RETRY_ONLY",
    "NEVER_RETRY_AUTOMATICALLY",
)
VALID_SIDE_EFFECT_CLASSES = (
    "REVERSIBLE",
    "COMPENSATABLE",
    "IRREVERSIBLE",
    "EXTERNAL_IRREVERSIBLE",
    "LEGAL_OR_FINANCIAL",
)
IRREVERSIBLE_SIDE_EFFECT_CLASSES = frozenset(
    {"IRREVERSIBLE", "EXTERNAL_IRREVERSIBLE", "LEGAL_OR_FINANCIAL"}
)
VALID_CONFLICT_SCOPES = (
    "LOCAL_TASK",
    "RESOURCE_BRANCH",
    "GOAL_BRANCH",
    "GLOBAL_MESH",
    "SAFETY_CRITICAL",
)


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
    resource_versions: dict[str, str] = field(default_factory=dict)
    access_mode: str = "READ_SHARED"
    conflict_class: str = "READ_SHARED"

    def __post_init__(self) -> None:
        object.__setattr__(self, "resource_refs", _normalized_text_list(self.resource_refs, "resource_refs"))
        object.__setattr__(self, "data_classes", _normalized_text_list(self.data_classes, "data_classes"))
        object.__setattr__(self, "network_allowlist", _normalized_text_list(self.network_allowlist, "network_allowlist"))
        object.__setattr__(self, "resource_versions", _normalized_text_map(self.resource_versions, "resource_versions"))
        object.__setattr__(
            self,
            "access_mode",
            _normalized_choice(self.access_mode, VALID_RESOURCE_ACCESS_MODES, "access_mode"),
        )
        object.__setattr__(
            self,
            "conflict_class",
            _normalized_choice(self.conflict_class, VALID_RESOURCE_CONFLICT_CLASSES, "conflict_class"),
        )


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
    physical_action_boundary_required: bool = False
    minimum_evidence_stage: str = "CLOSED"
    lease_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_operations", _normalized_text_list(self.allowed_operations, "allowed_operations"))
        object.__setattr__(self, "forbidden_operations", _normalized_text_list(self.forbidden_operations, "forbidden_operations"))
        object.__setattr__(self, "policy_refs", _normalized_text_list(self.policy_refs, "policy_refs"))
        object.__setattr__(
            self,
            "minimum_evidence_stage",
            _normalized_choice(self.minimum_evidence_stage, VALID_EVIDENCE_STAGES, "minimum_evidence_stage"),
        )
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
    resource_versions: dict[str, str] = field(default_factory=dict)
    idempotency_key: str = ""
    idempotency_class: str = "SAFE_REPEAT"
    side_effect_class: str = "REVERSIBLE"
    approval_ref: str = ""
    causal_parent_refs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.estimated_cost, int | float) or isinstance(self.estimated_cost, bool):
            raise ValueError("estimated_cost_number_required")
        if self.estimated_cost < 0:
            raise ValueError("nonnegative_estimated_cost_required")
        object.__setattr__(self, "payload", dict(self.payload))
        object.__setattr__(self, "resource_versions", _normalized_text_map(self.resource_versions, "resource_versions"))
        object.__setattr__(self, "idempotency_key", str(self.idempotency_key).strip())
        object.__setattr__(
            self,
            "idempotency_class",
            _normalized_choice(self.idempotency_class, VALID_IDEMPOTENCY_CLASSES, "idempotency_class"),
        )
        object.__setattr__(
            self,
            "side_effect_class",
            _normalized_choice(self.side_effect_class, VALID_SIDE_EFFECT_CLASSES, "side_effect_class"),
        )
        object.__setattr__(self, "approval_ref", str(self.approval_ref).strip())
        object.__setattr__(self, "causal_parent_refs", _normalized_text_list(self.causal_parent_refs, "causal_parent_refs"))


@dataclass(frozen=True, slots=True)
class WorkerHandlerResult:
    """Result returned by a local worker binding."""

    status: str
    output: dict[str, Any] = field(default_factory=dict)
    evidence_refs: list[str] = field(default_factory=list)
    error: str = ""
    cost: float = 0.0
    evidence_stage: str = "CLOSED"
    resource_versions_after: dict[str, str] = field(default_factory=dict)
    candidate_delta_hash: str = ""
    validation_refs: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not isinstance(self.cost, int | float) or isinstance(self.cost, bool):
            raise ValueError("worker_cost_number_required")
        if self.cost < 0:
            raise ValueError("nonnegative_worker_cost_required")
        object.__setattr__(self, "output", dict(self.output))
        object.__setattr__(self, "evidence_refs", list(self.evidence_refs))
        object.__setattr__(
            self,
            "evidence_stage",
            _normalized_choice(self.evidence_stage, VALID_EVIDENCE_STAGES, "evidence_stage"),
        )
        object.__setattr__(self, "resource_versions_after", _normalized_text_map(self.resource_versions_after, "resource_versions_after"))
        object.__setattr__(self, "candidate_delta_hash", str(self.candidate_delta_hash).strip())
        object.__setattr__(self, "validation_refs", _normalized_text_list(self.validation_refs, "validation_refs"))


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
    evidence_stage: str = "PRECHECK"
    resource_versions_before: dict[str, str] = field(default_factory=dict)
    resource_versions_after: dict[str, str] = field(default_factory=dict)
    idempotency_key: str = ""
    idempotency_class: str = "SAFE_REPEAT"
    side_effect_class: str = "REVERSIBLE"
    candidate_delta_hash: str = ""
    validation_refs: list[str] = field(default_factory=list)
    conflict_refs: list[str] = field(default_factory=list)
    progressive_evidence_complete: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "evidence_refs", list(self.evidence_refs))
        object.__setattr__(
            self,
            "evidence_stage",
            _normalized_choice(self.evidence_stage, VALID_EVIDENCE_STAGES, "evidence_stage"),
        )
        object.__setattr__(self, "resource_versions_before", _normalized_text_map(self.resource_versions_before, "resource_versions_before"))
        object.__setattr__(self, "resource_versions_after", _normalized_text_map(self.resource_versions_after, "resource_versions_after"))
        object.__setattr__(self, "idempotency_key", str(self.idempotency_key).strip())
        object.__setattr__(
            self,
            "idempotency_class",
            _normalized_choice(self.idempotency_class, VALID_IDEMPOTENCY_CLASSES, "idempotency_class"),
        )
        object.__setattr__(
            self,
            "side_effect_class",
            _normalized_choice(self.side_effect_class, VALID_SIDE_EFFECT_CLASSES, "side_effect_class"),
        )
        object.__setattr__(self, "candidate_delta_hash", str(self.candidate_delta_hash).strip())
        object.__setattr__(self, "validation_refs", _normalized_text_list(self.validation_refs, "validation_refs"))
        object.__setattr__(self, "conflict_refs", _normalized_text_list(self.conflict_refs, "conflict_refs"))
        object.__setattr__(self, "metadata", dict(self.metadata))


@dataclass(slots=True)
class _WorkerBinding:
    lease: WorkerLease
    handler: WorkerHandler
    operation_count: int = 0
    cost_used: float = 0.0
    reserved_cost: float = 0.0
    idempotency_keys: set[str] = field(default_factory=set)
    conflict_refs: list[str] = field(default_factory=list)
    conflict_scope: str = ""
    repair_refs: list[str] = field(default_factory=list)
    cancelled_at: str = ""
    cancellation_reason: str = ""


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
            if not denial and request.idempotency_key in binding.idempotency_keys:
                denial = "duplicate_idempotency_key"
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
                    conflict_refs=list(binding.conflict_refs),
                )
            binding.operation_count += 1
            binding.reserved_cost += request.estimated_cost
            if request.idempotency_key:
                binding.idempotency_keys.add(request.idempotency_key)
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
        if result.status == "succeeded":
            completion_denial = _completion_denial(binding.lease, result)
            if completion_denial:
                result = replace(result, status="failed", error=completion_denial)
        return _receipt(
            request=request,
            lease=binding.lease,
            worker_id=binding.lease.worker_id,
            status=result.status,
            reason=result.error or result.status,
            output=result.output,
            evidence_refs=result.evidence_refs,
            dispatched_at=dispatched_at,
            evidence_stage=result.evidence_stage,
            resource_versions_after=result.resource_versions_after,
            candidate_delta_hash=result.candidate_delta_hash,
            validation_refs=result.validation_refs,
            conflict_refs=list(binding.conflict_refs),
        )

    def read_model(self) -> dict[str, Any]:
        """Return a bounded operator read model for worker leases."""
        with self._lock:
            workers = []
            for binding in self._bindings.values():
                worker_status = "cancelled" if binding.cancelled_at else "active"
                if binding.conflict_refs:
                    worker_status = "conflict_frozen"
                workers.append(
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
                        "minimum_evidence_stage": binding.lease.minimum_evidence_stage,
                        "resource_version_count": len(binding.lease.scope.resource_versions),
                        "idempotency_key_count": len(binding.idempotency_keys),
                        "conflict_refs": list(binding.conflict_refs),
                        "repair_refs": list(binding.repair_refs),
                        "status": worker_status,
                        "cancelled_at": binding.cancelled_at,
                        "cancellation_reason": binding.cancellation_reason,
                    }
                )
            return {
                "worker_count": len(self._bindings),
                "workers": workers,
                "backpressure": _mesh_backpressure(workers),
            }

    def record_conflict(
        self,
        lease_id: str,
        *,
        conflict_ref: str,
        scope: str = "LOCAL_TASK",
        recorded_at: str | None = None,
    ) -> dict[str, Any]:
        """Freeze one lease branch until an explicit repair receipt is recorded."""
        normalized_ref = _required_text(conflict_ref, "conflict_ref")
        normalized_scope = _normalized_choice(scope, VALID_CONFLICT_SCOPES, "conflict_scope")
        observed_at = recorded_at or self._clock()
        with self._lock:
            binding = self._bindings.get(lease_id)
            if binding is None:
                return _control_receipt(
                    "worker-mesh-conflict",
                    lease_id=lease_id,
                    status="rejected",
                    reason="lease_not_found",
                    observed_at=observed_at,
                )
            if normalized_ref not in binding.conflict_refs:
                binding.conflict_refs.append(normalized_ref)
            binding.conflict_scope = normalized_scope
        return _control_receipt(
            "worker-mesh-conflict",
            lease_id=lease_id,
            status="recorded",
            reason="conflict_recorded",
            observed_at=observed_at,
            metadata={"conflict_ref": normalized_ref, "conflict_scope": normalized_scope},
        )

    def resolve_conflict(
        self,
        lease_id: str,
        *,
        repair_ref: str,
        resolved_at: str | None = None,
    ) -> dict[str, Any]:
        """Release a conflict freeze after a repair receipt has been preserved."""
        normalized_ref = _required_text(repair_ref, "repair_ref")
        observed_at = resolved_at or self._clock()
        with self._lock:
            binding = self._bindings.get(lease_id)
            if binding is None:
                return _control_receipt(
                    "worker-mesh-repair",
                    lease_id=lease_id,
                    status="rejected",
                    reason="lease_not_found",
                    observed_at=observed_at,
                )
            previous_conflicts = list(binding.conflict_refs)
            binding.conflict_refs.clear()
            binding.conflict_scope = ""
            binding.repair_refs.append(normalized_ref)
        return _control_receipt(
            "worker-mesh-repair",
            lease_id=lease_id,
            status="recorded",
            reason="conflict_resolved",
            observed_at=observed_at,
            metadata={"repair_ref": normalized_ref, "resolved_conflict_refs": previous_conflicts},
        )

    def cancel_lease(
        self,
        lease_id: str,
        *,
        reason: str,
        cancelled_at: str | None = None,
    ) -> dict[str, Any]:
        """Cancel one lease and block later worker actions under it."""
        normalized_reason = _required_text(reason, "cancellation_reason")
        observed_at = cancelled_at or self._clock()
        with self._lock:
            binding = self._bindings.get(lease_id)
            if binding is None:
                return _control_receipt(
                    "worker-mesh-cancellation",
                    lease_id=lease_id,
                    status="rejected",
                    reason="lease_not_found",
                    observed_at=observed_at,
                )
            binding.cancelled_at = observed_at
            binding.cancellation_reason = normalized_reason
        return _control_receipt(
            "worker-mesh-cancellation",
            lease_id=lease_id,
            status="recorded",
            reason="lease_cancelled",
            observed_at=observed_at,
            metadata={"cancellation_reason": normalized_reason},
        )


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
    if lease.receipt_schema_ref != WORKER_MESH_SCHEMA_REF:
        return "receipt_schema_ref_invalid"
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
    if binding.cancelled_at:
        return "lease_cancelled"
    if binding.conflict_refs:
        return "unresolved_conflict"
    if request.tenant_id != lease.tenant_id:
        return "tenant_mismatch"
    if request.capability != lease.capability:
        return "capability_mismatch"
    if request.operation in lease.forbidden_operations:
        return "operation_forbidden"
    if request.operation not in lease.allowed_operations:
        return "operation_not_allowed"
    if lease.physical_action_boundary_required:
        physical_denial = _physical_action_receipt_denial(
            request.payload.get(PHYSICAL_ACTION_RECEIPT_PAYLOAD_KEY),
            request=request,
        )
        if physical_denial:
            return physical_denial
    if not request.request_id:
        return "request_id_required"
    version_denial = _resource_version_denial(lease, request)
    if version_denial:
        return version_denial
    side_effect_denial = _side_effect_denial(request)
    if side_effect_denial:
        return side_effect_denial
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


def _normalized_text_list(values: list[str], field_name: str) -> list[str]:
    normalized: list[str] = []
    for index, value in enumerate(values):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name}_{index}_required")
        normalized.append(value.strip())
    return normalized


def _normalized_text_map(values: dict[str, str], field_name: str) -> dict[str, str]:
    if not isinstance(values, dict):
        raise ValueError(f"{field_name}_map_required")
    normalized: dict[str, str] = {}
    for key, value in values.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{field_name}_key_required")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field_name}_{key}_value_required")
        normalized[key.strip()] = value.strip()
    return normalized


def _required_text(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text:
        raise ValueError(f"{field_name}_required")
    return text


def _normalized_choice(value: str, valid_values: tuple[str, ...], field_name: str) -> str:
    normalized = str(value).strip().upper()
    if normalized not in valid_values:
        raise ValueError(f"{field_name}_invalid")
    return normalized


def _normalize_handler_result(result: WorkerHandlerResult) -> WorkerHandlerResult:
    if not isinstance(result, WorkerHandlerResult):
        return WorkerHandlerResult(status="failed", error="worker_result_contract_invalid")
    if result.status not in VALID_WORKER_STATUSES:
        return replace(result, status="failed", error="worker_status_invalid")
    return result


def _resource_version_denial(lease: WorkerLease, request: WorkerDispatchRequest) -> str:
    for resource_ref, expected_version in lease.scope.resource_versions.items():
        observed_version = request.resource_versions.get(resource_ref)
        if not observed_version:
            return "resource_version_required"
        if observed_version != expected_version:
            return "resource_version_mismatch"
    return ""


def _side_effect_denial(request: WorkerDispatchRequest) -> str:
    if request.idempotency_class == "SAFE_WITH_KEY" and not request.idempotency_key:
        return "idempotency_key_required"
    if request.side_effect_class not in IRREVERSIBLE_SIDE_EFFECT_CLASSES:
        return ""
    if not request.approval_ref:
        return "approval_ref_required_for_irreversible_side_effect"
    if request.idempotency_class not in {
        "SAFE_WITH_KEY",
        "MANUAL_RETRY_ONLY",
        "NEVER_RETRY_AUTOMATICALLY",
    }:
        return "irreversible_retry_policy_invalid"
    return ""


def _completion_denial(lease: WorkerLease, result: WorkerHandlerResult) -> str:
    if not _evidence_stage_satisfies(result.evidence_stage, lease.minimum_evidence_stage):
        return "worker_progressive_evidence_incomplete"
    if lease.scope.resource_versions and not result.resource_versions_after:
        return "worker_resource_versions_after_required"
    return ""


def _evidence_stage_satisfies(actual: str, minimum: str) -> bool:
    return VALID_EVIDENCE_STAGES.index(actual) >= VALID_EVIDENCE_STAGES.index(minimum)


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
    evidence_stage: str = "PRECHECK",
    resource_versions_after: dict[str, str] | None = None,
    candidate_delta_hash: str = "",
    validation_refs: list[str] | None = None,
    conflict_refs: list[str] | None = None,
) -> WorkerDispatchReceipt:
    output_hash = canonical_hash(output) if output else ""
    normalized_evidence_stage = _normalized_choice(evidence_stage, VALID_EVIDENCE_STAGES, "evidence_stage")
    resource_versions_after = resource_versions_after or {}
    validation_refs = validation_refs or []
    conflict_refs = conflict_refs or []
    minimum_evidence_stage = lease.minimum_evidence_stage if lease else "PRECHECK"
    progressive_evidence_complete = (
        _evidence_stage_satisfies(normalized_evidence_stage, minimum_evidence_stage)
        if lease else False
    )
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
        evidence_stage=normalized_evidence_stage,
        resource_versions_before=request.resource_versions,
        resource_versions_after=resource_versions_after,
        idempotency_key=request.idempotency_key,
        idempotency_class=request.idempotency_class,
        side_effect_class=request.side_effect_class,
        candidate_delta_hash=candidate_delta_hash,
        validation_refs=validation_refs,
        conflict_refs=conflict_refs,
        progressive_evidence_complete=progressive_evidence_complete,
        metadata={
            "receipt_is_not_terminal_closure": True,
            "receipt_schema_ref": lease.receipt_schema_ref if lease else "",
            "estimated_cost": request.estimated_cost,
            "lease_hash": lease.lease_hash if lease else "",
            "worker_receipt_status": status,
            "minimum_evidence_stage": minimum_evidence_stage,
            "evidence_stage": normalized_evidence_stage,
            "progressive_evidence_complete": progressive_evidence_complete,
            "resource_version_check_required": bool(lease and lease.scope.resource_versions),
            "resource_versions_before_bound": bool(request.resource_versions),
            "resource_versions_after_bound": bool(resource_versions_after),
            "idempotency_key_bound": bool(request.idempotency_key),
            "idempotency_class": request.idempotency_class,
            "side_effect_class": request.side_effect_class,
            "conflict_free": not conflict_refs,
            "conflict_refs": conflict_refs,
            "physical_action_boundary_required": lease.physical_action_boundary_required if lease else False,
            "physical_action_receipt_validated": (
                lease.physical_action_boundary_required
                and status != "rejected"
                if lease else False
            ),
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


def _mesh_backpressure(workers: list[dict[str, Any]]) -> dict[str, Any]:
    exhausted = [
        worker["lease_id"]
        for worker in workers
        if worker["operation_count"] >= worker["max_operations"]
    ]
    conflicted = [worker["lease_id"] for worker in workers if worker["conflict_refs"]]
    cancelled = [worker["lease_id"] for worker in workers if worker["status"] == "cancelled"]
    status = "backpressure" if exhausted or conflicted or cancelled else "normal"
    return {
        "status": status,
        "operation_budget_exhausted_leases": exhausted,
        "conflict_frozen_leases": conflicted,
        "cancelled_leases": cancelled,
    }


def _control_receipt(
    receipt_kind: str,
    *,
    lease_id: str,
    status: str,
    reason: str,
    observed_at: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "receipt_kind": receipt_kind,
        "lease_id": lease_id,
        "status": status,
        "reason": reason,
        "observed_at": observed_at,
        "terminal_closure_required": True,
        "receipt_is_not_terminal_closure": True,
        "metadata": metadata or {},
        "receipt_hash": "",
    }
    receipt_hash = canonical_hash(payload)
    return {
        **payload,
        "receipt_id": f"{receipt_kind}-{receipt_hash[:16]}",
        "receipt_hash": receipt_hash,
    }


def _physical_action_receipt_denial(receipt: Any, *, request: WorkerDispatchRequest) -> str:
    if not isinstance(receipt, dict):
        return "physical_action_receipt_required"
    if receipt.get("receipt_schema_ref") != PHYSICAL_ACTION_RECEIPT_SCHEMA_REF:
        return "physical_action_receipt_schema_invalid"
    if receipt.get("tenant_id") != request.tenant_id:
        return "physical_action_receipt_tenant_mismatch"
    if receipt.get("command_id") != request.command_id:
        return "physical_action_receipt_command_mismatch"
    if receipt.get("status") != "allowed":
        return "physical_action_receipt_not_allowed"
    if receipt.get("terminal_closure_required") is not True:
        return "physical_terminal_closure_required"
    if receipt.get("physical_worker_receipt_required") is not True:
        return "physical_worker_receipt_required"
    if receipt.get("manual_override_required") is not True:
        return "physical_manual_override_required"
    if receipt.get("emergency_stop_required") is not True:
        return "physical_emergency_stop_required"
    if receipt.get("simulation_passed") is not True:
        return "physical_simulation_required"
    if not receipt.get("actuator_id"):
        return "physical_actuator_id_required"
    if not receipt.get("receipt_hash"):
        return "physical_action_receipt_hash_required"
    if not _physical_action_receipt_hash_valid(receipt):
        return "physical_action_receipt_hash_mismatch"
    evidence_refs = receipt.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not evidence_refs:
        return "physical_action_evidence_required"
    if receipt.get("effect_mode") == "live" and receipt.get("operator_approval_required") is not True:
        return "physical_operator_approval_required"
    return ""


def _physical_action_receipt_hash_valid(receipt: dict[str, Any]) -> bool:
    expected_payload = {
        **receipt,
        "receipt_id": "pending",
        "receipt_hash": "",
    }
    return canonical_hash(expected_payload) == receipt.get("receipt_hash")


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
