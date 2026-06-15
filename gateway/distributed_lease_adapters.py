"""Distributed lease adapter registry receipt evaluator.

Purpose: evaluate distributed lease adapter capability records before a
    scheduler lease claim receipt can be trusted.
Governance scope: backend capability, adapter mode, production readiness,
    fencing-token support, compare-and-swap support, claim receipt hash,
    registry hash, no-live-backend-call flags, and secret absence.
Dependencies: dataclasses, datetime, gateway.command_spine, and
    gateway.distributed_lease_boundary.
Invariants:
  - The evaluator never calls SQLite, Postgres, Redis, etcd, Consul, or HTTP.
  - Adapter readiness is explicit and hash-bound to the lease claim receipt.
  - Non-production or disabled adapters block admission with named reasons.
  - External gateway adapters are delegation boundaries, not local execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any

from gateway.command_spine import canonical_hash
from gateway.distributed_lease_boundary import (
    DISTRIBUTED_LEASE_BACKENDS,
    DistributedLeaseClaimBoundaryRequest,
    DistributedLeaseClaimPlanner,
    _contains_secret_material,
    _normalize_list,
    _normalized_instant_text,
)


DISTRIBUTED_LEASE_ADAPTER_REGISTRY_RECEIPT_SCHEMA_REF = (
    "urn:mullusi:schema:distributed-lease-adapter-registry-receipt:1"
)
DISTRIBUTED_LEASE_ADAPTER_MODES = (
    "local_compare_and_swap",
    "native_client",
    "external_gateway",
    "disabled",
)
DISTRIBUTED_LEASE_ADAPTER_STATUSES = (
    "adapter_ready",
    "adapter_delegated",
    "adapter_blocked",
)
BASE_DISTRIBUTED_LEASE_ADAPTER_CONTROLS = (
    "adapter_registry_hash",
    "adapter_capability_hash",
    "distributed_lease_claim_receipt_hash",
    "backend_kind",
    "adapter_mode",
    "production_readiness",
    "fencing_token_capability",
    "compare_and_swap_capability",
    "secret_absence",
    "no_live_adapter_call",
    "terminal_closure",
)


@dataclass(frozen=True, slots=True)
class DistributedLeaseAdapterCapability:
    """One backend adapter capability advertised by the registry."""

    backend_kind: str
    mode: str
    fencing_tokens_supported: bool
    compare_and_swap_supported: bool
    production_ready: bool
    required_environment: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        backend_kind = str(self.backend_kind).strip()
        mode = str(self.mode).strip()
        if backend_kind not in DISTRIBUTED_LEASE_BACKENDS:
            raise ValueError("distributed_lease_adapter_backend_kind_invalid")
        if mode not in DISTRIBUTED_LEASE_ADAPTER_MODES:
            raise ValueError("distributed_lease_adapter_mode_invalid")
        object.__setattr__(self, "backend_kind", backend_kind)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(
            self,
            "required_environment",
            _normalize_list(self.required_environment),
        )
        object.__setattr__(self, "reasons", _normalize_list(self.reasons))
        object.__setattr__(self, "metadata", dict(self.metadata))
        if _contains_secret_material(self.metadata) or _contains_secret_material(
            self.required_environment
        ):
            raise ValueError("distributed_lease_adapter_secret_values_disclosed")


@dataclass(frozen=True, slots=True)
class DistributedLeaseAdapterRegistry:
    """Capability registry for distributed lease claim adapters."""

    registry_id: str
    generated_at: str
    capabilities: list[DistributedLeaseAdapterCapability] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        registry_id = str(self.registry_id).strip()
        if not registry_id:
            raise ValueError("distributed_lease_adapter_registry_id_required")
        object.__setattr__(self, "registry_id", registry_id)
        object.__setattr__(self, "generated_at", _normalized_instant_text(self.generated_at))
        normalized_capabilities = list(self.capabilities)
        if not normalized_capabilities:
            raise ValueError("distributed_lease_adapter_capabilities_required")
        for capability in normalized_capabilities:
            if not isinstance(capability, DistributedLeaseAdapterCapability):
                raise ValueError("distributed_lease_adapter_capability_required")
        object.__setattr__(self, "capabilities", normalized_capabilities)
        object.__setattr__(self, "metadata", dict(self.metadata))
        if _contains_secret_material(self.metadata):
            raise ValueError("distributed_lease_adapter_secret_values_disclosed")

    @classmethod
    def production_default(cls, *, generated_at: str) -> "DistributedLeaseAdapterRegistry":
        """Return the borrowed Nested Mind adapter inventory as a local contract."""
        return cls(
            registry_id="distributed-lease-adapter-registry-production-default",
            generated_at=generated_at,
            capabilities=[
                DistributedLeaseAdapterCapability(
                    backend_kind="sqlite_compare_and_swap",
                    mode="local_compare_and_swap",
                    fencing_tokens_supported=True,
                    compare_and_swap_supported=True,
                    production_ready=True,
                    required_environment=["MULLU_EVENT_DB"],
                    reasons=[
                        "SQLite compare-and-swap claim path is registry-ready for one local writer"
                    ],
                ),
                DistributedLeaseAdapterCapability(
                    backend_kind="postgres_advisory_lock",
                    mode="native_client",
                    fencing_tokens_supported=True,
                    compare_and_swap_supported=True,
                    production_ready=False,
                    required_environment=["DATABASE_URL"],
                    reasons=[
                        "Postgres advisory lock adapter boundary defined; native client implementation pending"
                    ],
                ),
                DistributedLeaseAdapterCapability(
                    backend_kind="redis_redlock",
                    mode="native_client",
                    fencing_tokens_supported=True,
                    compare_and_swap_supported=False,
                    production_ready=False,
                    required_environment=["REDIS_URL"],
                    reasons=[
                        "Redis Redlock adapter boundary defined; production safety review required"
                    ],
                ),
                DistributedLeaseAdapterCapability(
                    backend_kind="etcd_lease",
                    mode="native_client",
                    fencing_tokens_supported=True,
                    compare_and_swap_supported=True,
                    production_ready=False,
                    required_environment=["ETCD_ENDPOINTS"],
                    reasons=[
                        "etcd lease adapter boundary defined; native client implementation pending"
                    ],
                ),
                DistributedLeaseAdapterCapability(
                    backend_kind="consul_session",
                    mode="native_client",
                    fencing_tokens_supported=True,
                    compare_and_swap_supported=True,
                    production_ready=False,
                    required_environment=["CONSUL_HTTP_ADDR"],
                    reasons=[
                        "Consul session adapter boundary defined; native client implementation pending"
                    ],
                ),
                DistributedLeaseAdapterCapability(
                    backend_kind="external_http_gateway",
                    mode="external_gateway",
                    fencing_tokens_supported=True,
                    compare_and_swap_supported=True,
                    production_ready=False,
                    required_environment=["MULLU_LEASE_GATEWAY_URL"],
                    reasons=[
                        "external lease gateway must return hash-bound claim receipts"
                    ],
                ),
                DistributedLeaseAdapterCapability(
                    backend_kind="postgres_advisory_lock",
                    mode="disabled",
                    fencing_tokens_supported=False,
                    compare_and_swap_supported=False,
                    production_ready=False,
                    reasons=["disabled fallback marker; enabled capability must be explicit"],
                ),
            ],
        )

    def capability_for(self, backend_kind: str) -> DistributedLeaseAdapterCapability | None:
        """Return the first enabled capability for the backend, if one exists."""
        for capability in self.capabilities:
            if capability.backend_kind == backend_kind and capability.mode != "disabled":
                return capability
        return None


@dataclass(frozen=True, slots=True)
class DistributedLeaseAdapterRegistryReceipt:
    """Schema-backed receipt for one adapter registry evaluation."""

    receipt_id: str
    registry_id: str
    request_id: str
    tenant_id: str
    actor_id: str
    command_id: str
    backend_kind: str
    adapter_mode: str
    adapter_status: str
    production_ready: bool
    fencing_tokens_supported: bool
    compare_and_swap_supported: bool
    required_environment: list[str]
    registry_hash: str
    capability_hash: str
    claim_receipt: dict[str, Any]
    claim_receipt_hash: str
    claim_receipt_status: str
    claim_outcome: str
    adapter_claim_admissible: bool
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
    request_authentication_performed: bool
    raw_secret_stored: bool
    receipt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.adapter_mode not in DISTRIBUTED_LEASE_ADAPTER_MODES:
            raise ValueError("distributed_lease_adapter_mode_invalid")
        if self.adapter_status not in DISTRIBUTED_LEASE_ADAPTER_STATUSES:
            raise ValueError("distributed_lease_adapter_status_invalid")
        object.__setattr__(self, "required_environment", _normalize_list(self.required_environment))
        object.__setattr__(self, "blocked_reasons", _normalize_list(self.blocked_reasons))
        object.__setattr__(self, "required_actions", _normalize_list(self.required_actions))
        object.__setattr__(self, "required_controls", _normalize_list(self.required_controls))
        object.__setattr__(self, "evidence_refs", _normalize_list(self.evidence_refs))
        object.__setattr__(self, "claim_receipt", dict(self.claim_receipt))
        object.__setattr__(self, "evaluated_at", _normalized_instant_text(self.evaluated_at))
        object.__setattr__(self, "metadata", dict(self.metadata))


class DistributedLeaseAdapterRegistryEvaluator:
    """Deterministic adapter registry evaluator."""

    def evaluate(
        self,
        request: DistributedLeaseClaimBoundaryRequest,
        registry: DistributedLeaseAdapterRegistry,
    ) -> DistributedLeaseAdapterRegistryReceipt:
        """Return an adapter registry receipt without executing an adapter."""
        claim_receipt = DistributedLeaseClaimPlanner().evaluate(request)
        claim_receipt_dict = asdict(claim_receipt)
        capability = registry.capability_for(request.policy.backend_kind)
        registry_hash = canonical_hash(asdict(registry))
        capability_dict = asdict(capability) if capability else {}
        capability_hash = canonical_hash(capability_dict)
        blocked_reasons = list(claim_receipt.blocked_reasons)

        if capability is None:
            adapter_mode = "disabled"
            production_ready = False
            fencing_tokens_supported = False
            compare_and_swap_supported = False
            required_environment: list[str] = []
            blocked_reasons.append("distributed_lease_adapter_backend_not_registered")
        else:
            adapter_mode = capability.mode
            production_ready = capability.production_ready
            fencing_tokens_supported = capability.fencing_tokens_supported
            compare_and_swap_supported = capability.compare_and_swap_supported
            required_environment = capability.required_environment
            if not capability.fencing_tokens_supported and request.policy.fencing_tokens_required:
                blocked_reasons.append("distributed_lease_adapter_fencing_token_unsupported")
            if capability.mode == "native_client" and not capability.production_ready:
                blocked_reasons.append("distributed_lease_adapter_not_production_ready")
            if capability.mode == "disabled":
                blocked_reasons.append("distributed_lease_adapter_disabled")

        external_gateway_delegated = adapter_mode == "external_gateway" and not blocked_reasons
        adapter_ready = (
            adapter_mode == "local_compare_and_swap"
            and production_ready
            and not blocked_reasons
        )
        adapter_claim_admissible = adapter_ready or external_gateway_delegated
        adapter_status = _adapter_status(
            blocked_reasons=blocked_reasons,
            adapter_ready=adapter_ready,
            external_gateway_delegated=external_gateway_delegated,
        )
        evaluated_at = _normalized_instant_text(request.runtime_now_utc)
        required_controls = _required_controls(
            adapter_status=adapter_status,
            adapter_mode=adapter_mode,
            request=request,
        )
        metadata = {
            "receipt_is_not_terminal_closure": True,
            "registry_hash_bound": True,
            "capability_hash_bound": True,
            "claim_receipt_hash_bound": True,
            "lease_service_not_called": True,
            "adapter_backend_not_called": True,
            "request_authentication_not_performed": True,
            "raw_secret_not_stored": True,
            "external_gateway_delegated": external_gateway_delegated,
            "adapter_claim_admissible": adapter_claim_admissible,
            "secret_absence_verified": "secret_values_disclosed" not in blocked_reasons,
        }
        receipt = DistributedLeaseAdapterRegistryReceipt(
            receipt_id="pending",
            registry_id=registry.registry_id,
            request_id=request.request_id,
            tenant_id=request.tenant_id,
            actor_id=request.actor_id,
            command_id=request.command_id,
            backend_kind=request.policy.backend_kind,
            adapter_mode=adapter_mode,
            adapter_status=adapter_status,
            production_ready=production_ready,
            fencing_tokens_supported=fencing_tokens_supported,
            compare_and_swap_supported=compare_and_swap_supported,
            required_environment=required_environment,
            registry_hash=registry_hash,
            capability_hash=capability_hash,
            claim_receipt=claim_receipt_dict,
            claim_receipt_hash=claim_receipt.receipt_hash,
            claim_receipt_status=claim_receipt.status,
            claim_outcome=claim_receipt.claim_outcome,
            adapter_claim_admissible=adapter_claim_admissible,
            external_gateway_delegated=external_gateway_delegated,
            blocked_reasons=_unique(blocked_reasons),
            required_actions=_required_actions(adapter_status, claim_receipt.required_actions),
            required_controls=required_controls,
            evidence_refs=claim_receipt.evidence_refs,
            evaluated_at=evaluated_at,
            receipt_schema_ref=DISTRIBUTED_LEASE_ADAPTER_REGISTRY_RECEIPT_SCHEMA_REF,
            terminal_closure_required=True,
            lease_service_call_performed=False,
            adapter_backend_call_performed=False,
            request_authentication_performed=False,
            raw_secret_stored=False,
            metadata=metadata,
        )
        receipt_hash = canonical_hash(asdict(receipt))
        return replace(
            receipt,
            receipt_id=f"distributed-lease-adapter-registry-receipt-{receipt_hash[:16]}",
            receipt_hash=receipt_hash,
        )


def _adapter_status(
    *,
    blocked_reasons: list[str],
    adapter_ready: bool,
    external_gateway_delegated: bool,
) -> str:
    if blocked_reasons:
        return "adapter_blocked"
    if external_gateway_delegated:
        return "adapter_delegated"
    if adapter_ready:
        return "adapter_ready"
    return "adapter_blocked"


def _required_actions(adapter_status: str, claim_actions: list[str]) -> list[str]:
    if adapter_status == "adapter_blocked":
        return _unique(
            [
                "resolve_distributed_lease_adapter_block",
                "retain_adapter_registry_receipt",
                *claim_actions,
            ]
        )
    if adapter_status == "adapter_delegated":
        return _unique(
            [
                "submit_claim_through_receipt_producing_gateway",
                "retain_adapter_registry_receipt",
                "retain_external_gateway_claim_receipt",
                *claim_actions,
            ]
        )
    return _unique(
        [
            "retain_adapter_registry_receipt",
            "withhold_live_backend_call_until_execution_receipt",
            *claim_actions,
        ]
    )


def _required_controls(
    *,
    adapter_status: str,
    adapter_mode: str,
    request: DistributedLeaseClaimBoundaryRequest,
) -> list[str]:
    controls = [*BASE_DISTRIBUTED_LEASE_ADAPTER_CONTROLS]
    if adapter_mode == "external_gateway":
        controls.append("external_gateway_delegation")
    if request.policy.fencing_tokens_required:
        controls.append("fencing_token_required")
    if adapter_status == "adapter_blocked":
        controls.append("distributed_lease_adapter_block")
    return _unique(controls)


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
