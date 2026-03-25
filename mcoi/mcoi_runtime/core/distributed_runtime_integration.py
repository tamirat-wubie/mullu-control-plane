"""Purpose: distributed runtime integration bridge.
Governance scope: connects distributed execution fabric to orchestration,
    service catalog, external execution, LLM runtime, factory, and research.
Dependencies: distributed_runtime engine, event_spine, memory_mesh.
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
from mcoi_runtime.core.distributed_runtime import DistributedRuntimeEngine
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
        event_id=stable_identifier("evt-disti", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class DistributedRuntimeIntegration:
    """Integration bridge for distributed execution fabric."""

    def __init__(
        self,
        distributed_engine: DistributedRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(distributed_engine, DistributedRuntimeEngine):
            raise RuntimeCoreInvariantError("distributed_engine must be a DistributedRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._dist = distributed_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # -- Bridge helpers --

    def _next_bridge_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        worker_id = stable_identifier("dw", {"tenant": tenant_id, "source": source_type, "seq": seq})
        queue_id = stable_identifier("dq", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return worker_id, queue_id

    def _bridge(
        self,
        tenant_id: str,
        source_type: str,
        display_prefix: str,
    ) -> dict[str, Any]:
        worker_id, queue_id = self._next_bridge_ids(tenant_id, source_type)
        worker = self._dist.register_worker(
            worker_id=worker_id, tenant_id=tenant_id,
            display_name=f"{display_prefix}-worker",
        )
        queue = self._dist.create_queue(
            queue_id=queue_id, tenant_id=tenant_id,
            display_name=f"{display_prefix}-queue",
        )
        _emit(self._events, f"distribute_for_{source_type}", {
            "tenant_id": tenant_id, "worker_id": worker_id, "queue_id": queue_id,
        }, worker_id)
        return {
            "worker_id": worker.worker_id,
            "queue_id": queue.queue_id,
            "tenant_id": tenant_id,
            "worker_status": worker.status.value,
            "queue_status": queue.status.value,
            "capacity": worker.capacity,
            "max_depth": queue.max_depth,
            "source_type": source_type,
        }

    # -- Bridge methods --

    def distribute_for_orchestration(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "orchestration", "orch")

    def distribute_for_service_catalog(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "service_catalog", "svc")

    def distribute_for_external_execution(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "external_execution", "ext")

    def distribute_for_llm_runtime(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "llm_runtime", "llm")

    def distribute_for_factory(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "factory", "fac")

    def distribute_for_research(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "research", "res")

    # -- Memory mesh --

    def attach_distributed_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-dist", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content = {
            "total_workers": self._dist.worker_count,
            "total_queues": self._dist.queue_count,
            "total_leases": self._dist.lease_count,
            "total_shards": self._dist.shard_count,
            "total_checkpoints": self._dist.checkpoint_count,
            "total_violations": self._dist.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Distributed runtime state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("distributed", "execution_fabric", "scale"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_distributed_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return record

    # -- Graph --

    def attach_distributed_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "total_workers": self._dist.worker_count,
            "total_queues": self._dist.queue_count,
            "total_leases": self._dist.lease_count,
            "total_shards": self._dist.shard_count,
            "total_checkpoints": self._dist.checkpoint_count,
            "total_violations": self._dist.violation_count,
        }
