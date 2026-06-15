"""Distributed lease execution receipt boundary.

Purpose: compose lease claim and adapter registry receipts into an execution
    admissibility receipt without executing a scheduler lease backend.
Governance scope: execution plan hash, adapter registry receipt hash, claim
    receipt hash, payload hash binding, execution mode, delegation status,
    blocked reasons, no-live-backend-call flags, and terminal closure.
Dependencies: dataclasses, gateway.command_spine, gateway.distributed_lease_adapters,
    and gateway.distributed_lease_boundary.
Invariants:
  - The evaluator never calls SQLite, Postgres, Redis, etcd, Consul, or HTTP.
  - Local execution is admissible only for a ready local compare-and-swap adapter.
  - External gateway execution is delegated, never locally performed.
  - A granted claim outcome is required before a delegated receipt can represent
    a bound external claim.
  - Raw secret-shaped material blocks receipt admission.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.distributed_lease_adapters import (
    DistributedLeaseAdapterRegistry,
    DistributedLeaseAdapterRegistryEvaluator,
    DistributedLeaseAdapterRegistryReceipt,
)
from gateway.distributed_lease_boundary import (
    DistributedLeaseClaimBoundaryRequest,
    _contains_secret_material,
    _normalize_list,
    _normalized_instant_text,
)


DISTRIBUTED_LEASE_EXECUTION_RECEIPT_SCHEMA_REF = (
    "urn:mullusi:schema:distributed-lease-execution-receipt:1"
)
DISTRIBUTED_LEASE_EXECUTION_MODES = (
    "plan_only",
    "local_compare_and_swap",
    "external_gateway",
)
DISTRIBUTED_LEASE_EXECUTION_STATUSES = (
    "execution_receipt_ready",
    "execution_delegated",
    "execution_blocked",
)
BASE_DISTRIBUTED_LEASE_EXECUTION_CONTROLS = (
    "distributed_lease_execution_plan_hash",
    "distributed_lease_adapter_registry_receipt_hash",
    "distributed_lease_claim_receipt_hash",
    "payload_hash_binding",
    "operation_payload_hash",
    "execution_mode",
    "adapter_status",
    "claim_receipt_status",
    "claim_outcome",
    "no_live_backend_call",
    "no_worker_dispatch",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class DistributedLeaseExecutionPlan:
    """Hash-bound plan for a lease execution boundary."""

    plan_id: str
    backend_kind: str
    execution_mode: str
    job_id: str
    worker_id: str
    expected_payload_hash: str
    operation_payload: dict[str, Any]
    operation_payload_hash: str
    adapter_registry_receipt_hash: str
    claim_receipt_hash: str
    plan_hash: str
    created_at: str

    def __post_init__(self) -> None:
        if self.execution_mode not in DISTRIBUTED_LEASE_EXECUTION_MODES:
            raise ValueError("distributed_lease_execution_mode_invalid")
        object.__setattr__(self, "operation_payload", dict(self.operation_payload))
        object.__setattr__(self, "created_at", _normalized_instant_text(self.created_at))


@dataclass(frozen=True, slots=True)
class DistributedLeaseExecutionReceipt:
    """Schema-backed non-terminal receipt for lease execution admissibility."""

    receipt_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    backend_kind: str
    execution_mode: str
    execution_status: str
    job_id: str
    worker_id: str
    expected_payload_hash: str
    operation_payload: dict[str, Any]
    operation_payload_hash: str
    execution_plan: dict[str, Any]
    execution_plan_hash: str
    adapter_registry_receipt: dict[str, Any]
    adapter_registry_receipt_hash: str
    claim_receipt_hash: str
    adapter_status: str
    claim_receipt_status: str
    claim_outcome: str
    execution_admissible: bool
    external_gateway_delegated: bool
    blocked_reasons: list[str]
    required_actions: list[str]
    required_controls: list[str]
    evidence_refs: list[str]
    evaluated_at: str
    receipt_schema_ref: str
    terminal_closure_required: bool
    lease_service_call_performed: bool
    adapter_backend_call_performed: bool
    scheduler_mutation_performed: bool
    worker_dispatch_performed: bool
    request_authentication_performed: bool
    raw_secret_stored: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.execution_mode not in DISTRIBUTED_LEASE_EXECUTION_MODES:
            raise ValueError("distributed_lease_execution_mode_invalid")
        if self.execution_status not in DISTRIBUTED_LEASE_EXECUTION_STATUSES:
            raise ValueError("distributed_lease_execution_status_invalid")
        object.__setattr__(self, "operation_payload", dict(self.operation_payload))
        object.__setattr__(self, "execution_plan", dict(self.execution_plan))
        object.__setattr__(
            self,
            "adapter_registry_receipt",
            dict(self.adapter_registry_receipt),
        )
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_actions", _normalize_list(self.required_actions))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "evaluated_at", _normalized_instant_text(self.evaluated_at))
        object.__setattr__(self, "metadata", dict(self.metadata))


class DistributedLeaseExecutionReceiptEvaluator:
    """Deterministic execution receipt evaluator."""

    def evaluate(
        self,
        request: DistributedLeaseClaimBoundaryRequest,
        registry: DistributedLeaseAdapterRegistry,
    ) -> DistributedLeaseExecutionReceipt:
        """Return a distributed lease execution receipt without live execution."""
        if _contains_secret_material(request.metadata):
            return self._blocked_for_secret(request, registry)

        adapter_receipt = DistributedLeaseAdapterRegistryEvaluator().evaluate(request, registry)
        execution_mode = _execution_mode(adapter_receipt)
        operation_payload = dict(adapter_receipt.claim_receipt["operation_payload"])
        operation_payload_hash = str(adapter_receipt.claim_receipt["operation_payload_hash"])
        execution_plan = _execution_plan(
            request=request,
            adapter_receipt=adapter_receipt,
            execution_mode=execution_mode,
            operation_payload=operation_payload,
            operation_payload_hash=operation_payload_hash,
        )
        blocked_reasons = _blocked_reasons(adapter_receipt, execution_mode)
        execution_status = _execution_status(adapter_receipt, execution_mode, blocked_reasons)
        execution_admissible = execution_status in {
            "execution_receipt_ready",
            "execution_delegated",
        }
        external_gateway_delegated = execution_status == "execution_delegated"
        metadata = {
            "receipt_is_not_terminal_closure": True,
            "execution_plan_hash_bound": True,
            "adapter_registry_receipt_hash_bound": True,
            "claim_receipt_hash_bound": True,
            "payload_hash_bound": True,
            "operation_payload_hash_bound": True,
            "lease_service_not_called": True,
            "adapter_backend_not_called": True,
            "scheduler_mutation_not_performed": True,
            "worker_dispatch_not_performed": True,
            "request_authentication_not_performed": True,
            "raw_secret_not_stored": True,
            "external_gateway_delegated": external_gateway_delegated,
            "execution_admissible": execution_admissible,
            "secret_absence_verified": "secret_values_disclosed" not in blocked_reasons,
        }
        receipt = DistributedLeaseExecutionReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            backend_kind=request.policy.backend_kind,
            execution_mode=execution_mode,
            execution_status=execution_status,
            job_id=request.job.job_id,
            worker_id=request.worker_id,
            expected_payload_hash=request.job.expected_payload_hash,
            operation_payload=operation_payload,
            operation_payload_hash=operation_payload_hash,
            execution_plan=asdict(execution_plan),
            execution_plan_hash=execution_plan.plan_hash,
            adapter_registry_receipt=asdict(adapter_receipt),
            adapter_registry_receipt_hash=adapter_receipt.receipt_hash,
            claim_receipt_hash=adapter_receipt.claim_receipt_hash,
            adapter_status=adapter_receipt.adapter_status,
            claim_receipt_status=adapter_receipt.claim_receipt_status,
            claim_outcome=adapter_receipt.claim_outcome,
            execution_admissible=execution_admissible,
            external_gateway_delegated=external_gateway_delegated,
            blocked_reasons=blocked_reasons,
            required_actions=_required_actions(execution_status),
            required_controls=_required_controls(execution_status, execution_mode),
            evidence_refs=adapter_receipt.evidence_refs,
            evaluated_at=request.runtime_now_utc,
            receipt_schema_ref=DISTRIBUTED_LEASE_EXECUTION_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            lease_service_call_performed=False,
            adapter_backend_call_performed=False,
            scheduler_mutation_performed=False,
            worker_dispatch_performed=False,
            request_authentication_performed=False,
            raw_secret_stored=False,
            metadata=metadata,
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"distributed-lease-execution-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )

    def _blocked_for_secret(
        self,
        request: DistributedLeaseClaimBoundaryRequest,
        registry: DistributedLeaseAdapterRegistry,
    ) -> DistributedLeaseExecutionReceipt:
        adapter_receipt = DistributedLeaseAdapterRegistryEvaluator().evaluate(request, registry)
        execution_mode = _execution_mode(adapter_receipt)
        operation_payload = dict(adapter_receipt.claim_receipt["operation_payload"])
        operation_payload_hash = str(adapter_receipt.claim_receipt["operation_payload_hash"])
        execution_plan = _execution_plan(
            request=request,
            adapter_receipt=adapter_receipt,
            execution_mode=execution_mode,
            operation_payload=operation_payload,
            operation_payload_hash=operation_payload_hash,
        )
        blocked_reasons = _unique([*adapter_receipt.blocked_reasons, "secret_values_disclosed"])
        receipt = DistributedLeaseExecutionReceipt(
            receipt_id="pending",
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            backend_kind=request.policy.backend_kind,
            execution_mode=execution_mode,
            execution_status="execution_blocked",
            job_id=request.job.job_id,
            worker_id=request.worker_id,
            expected_payload_hash=request.job.expected_payload_hash,
            operation_payload=operation_payload,
            operation_payload_hash=operation_payload_hash,
            execution_plan=asdict(execution_plan),
            execution_plan_hash=execution_plan.plan_hash,
            adapter_registry_receipt=asdict(adapter_receipt),
            adapter_registry_receipt_hash=adapter_receipt.receipt_hash,
            claim_receipt_hash=adapter_receipt.claim_receipt_hash,
            adapter_status=adapter_receipt.adapter_status,
            claim_receipt_status=adapter_receipt.claim_receipt_status,
            claim_outcome=adapter_receipt.claim_outcome,
            execution_admissible=False,
            external_gateway_delegated=False,
            blocked_reasons=blocked_reasons,
            required_actions=_required_actions("execution_blocked"),
            required_controls=_required_controls("execution_blocked", execution_mode),
            evidence_refs=adapter_receipt.evidence_refs,
            evaluated_at=request.runtime_now_utc,
            receipt_schema_ref=DISTRIBUTED_LEASE_EXECUTION_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            lease_service_call_performed=False,
            adapter_backend_call_performed=False,
            scheduler_mutation_performed=False,
            worker_dispatch_performed=False,
            request_authentication_performed=False,
            raw_secret_stored=False,
            metadata={
                "receipt_is_not_terminal_closure": True,
                "execution_plan_hash_bound": True,
                "adapter_registry_receipt_hash_bound": True,
                "claim_receipt_hash_bound": True,
                "payload_hash_bound": True,
                "operation_payload_hash_bound": True,
                "lease_service_not_called": True,
                "adapter_backend_not_called": True,
                "scheduler_mutation_not_performed": True,
                "worker_dispatch_not_performed": True,
                "request_authentication_not_performed": True,
                "raw_secret_not_stored": True,
                "external_gateway_delegated": False,
                "execution_admissible": False,
                "secret_absence_verified": False,
            },
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"distributed-lease-execution-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _execution_plan(
    *,
    request: DistributedLeaseClaimBoundaryRequest,
    adapter_receipt: DistributedLeaseAdapterRegistryReceipt,
    execution_mode: str,
    operation_payload: dict[str, Any],
    operation_payload_hash: str,
) -> DistributedLeaseExecutionPlan:
    plan_hash = canonical_hash(
        {
            "request_id": request.request_id,
            "backend_kind": request.policy.backend_kind,
            "execution_mode": execution_mode,
            "job_id": request.job.job_id,
            "worker_id": request.worker_id,
            "expected_payload_hash": request.job.expected_payload_hash,
            "operation_payload_hash": operation_payload_hash,
            "adapter_registry_receipt_hash": adapter_receipt.receipt_hash,
            "claim_receipt_hash": adapter_receipt.claim_receipt_hash,
            "created_at": _normalized_instant_text(request.runtime_now_utc),
        }
    )
    return DistributedLeaseExecutionPlan(
        plan_id=f"distributed-lease-execution-plan-{plan_hash[:16]}",
        backend_kind=request.policy.backend_kind,
        execution_mode=execution_mode,
        job_id=request.job.job_id,
        worker_id=request.worker_id,
        expected_payload_hash=request.job.expected_payload_hash,
        operation_payload=operation_payload,
        operation_payload_hash=operation_payload_hash,
        adapter_registry_receipt_hash=adapter_receipt.receipt_hash,
        claim_receipt_hash=adapter_receipt.claim_receipt_hash,
        plan_hash=plan_hash,
        created_at=request.runtime_now_utc,
    )


def _execution_mode(receipt: DistributedLeaseAdapterRegistryReceipt) -> str:
    if receipt.adapter_status == "adapter_ready":
        return "local_compare_and_swap"
    if receipt.adapter_status == "adapter_delegated":
        return "external_gateway"
    return "plan_only"


def _blocked_reasons(
    receipt: DistributedLeaseAdapterRegistryReceipt,
    execution_mode: str,
) -> list[str]:
    blocked = list(receipt.blocked_reasons)
    if receipt.claim_receipt["job_id"] != receipt.claim_receipt["job"]["job_id"]:
        blocked.append("distributed_lease_execution_job_mismatch")
    if (
        receipt.claim_receipt["expected_payload_hash"]
        != receipt.claim_receipt["observed_payload_hash"]
    ):
        if receipt.claim_receipt_status == "claim_receipt_bound":
            blocked.append("distributed_lease_execution_payload_hash_mismatch")
    if execution_mode == "external_gateway" and receipt.claim_receipt_status == "claim_receipt_bound":
        if receipt.claim_outcome != "granted":
            blocked.append("distributed_lease_execution_grant_required")
    if execution_mode == "plan_only" and not blocked:
        blocked.append("distributed_lease_execution_adapter_not_admissible")
    return _unique(blocked)


def _execution_status(
    receipt: DistributedLeaseAdapterRegistryReceipt,
    execution_mode: str,
    blocked_reasons: list[str],
) -> str:
    if blocked_reasons:
        return "execution_blocked"
    if execution_mode == "external_gateway":
        return "execution_delegated"
    if receipt.adapter_status == "adapter_ready":
        return "execution_receipt_ready"
    return "execution_blocked"


def _required_actions(execution_status: str) -> list[str]:
    if execution_status == "execution_blocked":
        return [
            "resolve_distributed_lease_execution_block",
            "retain_blocked_execution_receipt",
        ]
    if execution_status == "execution_delegated":
        return [
            "retain_execution_receipt",
            "delegate_execution_through_receipt_producing_gateway",
            "retain_terminal_closure_evidence",
        ]
    return [
        "retain_execution_receipt",
        "perform_local_compare_and_swap_only_in_authorized_scheduler_runtime",
        "retain_terminal_closure_evidence",
    ]


def _required_controls(execution_status: str, execution_mode: str) -> list[str]:
    controls = [*BASE_DISTRIBUTED_LEASE_EXECUTION_CONTROLS]
    if execution_mode == "external_gateway":
        controls.append("external_gateway_delegation")
    if execution_mode == "local_compare_and_swap":
        controls.append("local_compare_and_swap_runtime_authority")
    if execution_status == "execution_blocked":
        controls.append("distributed_lease_execution_block")
    return _unique(controls)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
