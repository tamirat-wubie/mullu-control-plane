"""Purpose: incentive runtime integration bridge.
Governance scope: composing incentive runtime with marketplace, partner,
    workforce, customer, billing, and contract engines;
    memory mesh and operational graph attachment.
Dependencies: incentive_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every incentive action emits events.
  - Incentive state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.incentive_runtime import (
    IncentiveKind,
    IncentiveStatus,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .incentive_runtime import IncentiveRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-icint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class IncentiveRuntimeIntegration:
    """Integration bridge for incentive runtime with platform layers."""

    def __init__(
        self,
        incentive_engine: IncentiveRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(incentive_engine, IncentiveRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "incentive_engine must be an IncentiveRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._incentive = incentive_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Cross-domain incentive creation
    # ------------------------------------------------------------------

    def incentive_from_marketplace(
        self,
        incentive_id: str,
        tenant_id: str,
        display_name: str,
        marketplace_ref: str,
        *,
        kind: IncentiveKind = IncentiveKind.DISCOUNT,
        target_actor_ref: str = "marketplace-actor",
        value: float = 0.0,
    ) -> dict[str, Any]:
        """Create an incentive from a marketplace listing."""
        record = self._incentive.register_incentive(
            incentive_id, tenant_id, display_name,
            kind=kind, target_actor_ref=target_actor_ref, value=value,
        )
        _emit(self._events, "incentive_from_marketplace", {
            "incentive_id": incentive_id, "marketplace_ref": marketplace_ref,
        }, incentive_id)
        return {
            "incentive_id": record.incentive_id,
            "tenant_id": record.tenant_id,
            "marketplace_ref": marketplace_ref,
            "kind": record.kind.value,
            "status": record.status.value,
            "source_type": "marketplace",
        }

    def incentive_from_partner(
        self,
        incentive_id: str,
        tenant_id: str,
        display_name: str,
        partner_ref: str,
        *,
        kind: IncentiveKind = IncentiveKind.COMMISSION,
        target_actor_ref: str = "partner-actor",
        value: float = 0.0,
    ) -> dict[str, Any]:
        """Create an incentive from a partner relationship."""
        record = self._incentive.register_incentive(
            incentive_id, tenant_id, display_name,
            kind=kind, target_actor_ref=target_actor_ref, value=value,
        )
        _emit(self._events, "incentive_from_partner", {
            "incentive_id": incentive_id, "partner_ref": partner_ref,
        }, incentive_id)
        return {
            "incentive_id": record.incentive_id,
            "tenant_id": record.tenant_id,
            "partner_ref": partner_ref,
            "kind": record.kind.value,
            "status": record.status.value,
            "source_type": "partner",
        }

    def incentive_from_workforce(
        self,
        incentive_id: str,
        tenant_id: str,
        display_name: str,
        workforce_ref: str,
        *,
        kind: IncentiveKind = IncentiveKind.BONUS,
        target_actor_ref: str = "workforce-actor",
        value: float = 0.0,
    ) -> dict[str, Any]:
        """Create an incentive from workforce management."""
        record = self._incentive.register_incentive(
            incentive_id, tenant_id, display_name,
            kind=kind, target_actor_ref=target_actor_ref, value=value,
        )
        _emit(self._events, "incentive_from_workforce", {
            "incentive_id": incentive_id, "workforce_ref": workforce_ref,
        }, incentive_id)
        return {
            "incentive_id": record.incentive_id,
            "tenant_id": record.tenant_id,
            "workforce_ref": workforce_ref,
            "kind": record.kind.value,
            "status": record.status.value,
            "source_type": "workforce",
        }

    def incentive_from_customer(
        self,
        incentive_id: str,
        tenant_id: str,
        display_name: str,
        customer_ref: str,
        *,
        kind: IncentiveKind = IncentiveKind.REWARD,
        target_actor_ref: str = "customer-actor",
        value: float = 0.0,
    ) -> dict[str, Any]:
        """Create an incentive from customer engagement."""
        record = self._incentive.register_incentive(
            incentive_id, tenant_id, display_name,
            kind=kind, target_actor_ref=target_actor_ref, value=value,
        )
        _emit(self._events, "incentive_from_customer", {
            "incentive_id": incentive_id, "customer_ref": customer_ref,
        }, incentive_id)
        return {
            "incentive_id": record.incentive_id,
            "tenant_id": record.tenant_id,
            "customer_ref": customer_ref,
            "kind": record.kind.value,
            "status": record.status.value,
            "source_type": "customer",
        }

    def incentive_from_billing(
        self,
        incentive_id: str,
        tenant_id: str,
        display_name: str,
        billing_ref: str,
        *,
        kind: IncentiveKind = IncentiveKind.DISCOUNT,
        target_actor_ref: str = "billing-actor",
        value: float = 0.0,
    ) -> dict[str, Any]:
        """Create an incentive from billing events."""
        record = self._incentive.register_incentive(
            incentive_id, tenant_id, display_name,
            kind=kind, target_actor_ref=target_actor_ref, value=value,
        )
        _emit(self._events, "incentive_from_billing", {
            "incentive_id": incentive_id, "billing_ref": billing_ref,
        }, incentive_id)
        return {
            "incentive_id": record.incentive_id,
            "tenant_id": record.tenant_id,
            "billing_ref": billing_ref,
            "kind": record.kind.value,
            "status": record.status.value,
            "source_type": "billing",
        }

    def incentive_from_contract(
        self,
        incentive_id: str,
        tenant_id: str,
        display_name: str,
        contract_ref: str,
        *,
        kind: IncentiveKind = IncentiveKind.THRESHOLD,
        target_actor_ref: str = "contract-actor",
        value: float = 0.0,
    ) -> dict[str, Any]:
        """Create an incentive from a contract obligation."""
        record = self._incentive.register_incentive(
            incentive_id, tenant_id, display_name,
            kind=kind, target_actor_ref=target_actor_ref, value=value,
        )
        _emit(self._events, "incentive_from_contract", {
            "incentive_id": incentive_id, "contract_ref": contract_ref,
        }, incentive_id)
        return {
            "incentive_id": record.incentive_id,
            "tenant_id": record.tenant_id,
            "contract_ref": contract_ref,
            "kind": record.kind.value,
            "status": record.status.value,
            "source_type": "contract",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_incentive_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist incentive state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_incentives": self._incentive.incentive_count,
            "total_observations": self._incentive.observation_count,
            "total_detections": self._incentive.detection_count,
            "total_effects": self._incentive.effect_count,
            "total_bindings": self._incentive.binding_count,
            "total_violations": self._incentive.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-incn", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Incentive state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("incentive", "mechanism_design", "gaming"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "incentive_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_incentive_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return incentive state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_incentives": self._incentive.incentive_count,
            "total_observations": self._incentive.observation_count,
            "total_detections": self._incentive.detection_count,
            "total_effects": self._incentive.effect_count,
            "total_bindings": self._incentive.binding_count,
            "total_violations": self._incentive.violation_count,
        }
