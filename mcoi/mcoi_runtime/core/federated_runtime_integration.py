"""Purpose: federated runtime integration bridge.
Governance scope: connects federated mesh to distributed runtime,
    partner, continuity, factory, epistemic, and identity runtimes.
Dependencies: federated_runtime engine, event_spine, memory_mesh.
Invariants:
  - Constructor validates all three engine types.
  - All outputs are frozen dicts or MemoryRecord instances.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.federated_runtime import FederatedRuntimeEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict[str, Any], cid: str) -> None:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-fedi", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class FederatedRuntimeIntegration:
    """Integration bridge for federated mesh / distributed knowledge."""

    def __init__(
        self,
        federated_engine: FederatedRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(federated_engine, FederatedRuntimeEngine):
            raise RuntimeCoreInvariantError("federated_engine must be a FederatedRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._fed = federated_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # -- Bridge helpers --

    def _next_bridge_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        node_id = stable_identifier("fn", {"tenant": tenant_id, "source": source_type, "seq": seq})
        claim_id = stable_identifier("fc", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return node_id, claim_id

    def _bridge(
        self,
        tenant_id: str,
        source_type: str,
        display_prefix: str,
    ) -> dict[str, Any]:
        node_id, claim_id = self._next_bridge_ids(tenant_id, source_type)
        node = self._fed.register_node(
            node_id=node_id, tenant_id=tenant_id,
            display_name=f"{display_prefix}-node",
        )
        claim = self._fed.register_claim(
            claim_id=claim_id, tenant_id=tenant_id,
            origin_node_ref=node_id,
            content=f"{source_type} bridge claim",
        )
        _emit(self._events, f"federate_for_{source_type}", {
            "tenant_id": tenant_id, "node_id": node_id, "claim_id": claim_id,
        }, node_id)
        return {
            "node_id": node.node_id,
            "claim_id": claim.claim_id,
            "tenant_id": tenant_id,
            "node_status": node.status.value,
            "claim_sync": claim.sync.value,
            "source_type": source_type,
        }

    # -- Bridge methods --

    def federated_from_distributed_runtime(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "distributed_runtime", "dist")

    def federated_from_partner(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "partner", "part")

    def federated_from_continuity(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "continuity", "cont")

    def federated_from_factory(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "factory", "fac")

    def federated_from_epistemic(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "epistemic", "epist")

    def federated_from_identity(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "identity", "id")

    # -- Memory mesh --

    def attach_federated_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-fed", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content = {
            "total_nodes": self._fed.node_count,
            "total_claims": self._fed.claim_count,
            "total_syncs": self._fed.sync_count,
            "total_reconciliations": self._fed.reconciliation_count,
            "total_partitions": self._fed.partition_count,
            "total_violations": self._fed.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Federated runtime state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("federated", "mesh", "knowledge"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_federated_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return record

    # -- Graph --

    def attach_federated_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "total_nodes": self._fed.node_count,
            "total_claims": self._fed.claim_count,
            "total_syncs": self._fed.sync_count,
            "total_reconciliations": self._fed.reconciliation_count,
            "total_partitions": self._fed.partition_count,
            "total_violations": self._fed.violation_count,
        }
