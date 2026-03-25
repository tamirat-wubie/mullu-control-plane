"""Purpose: formal verification runtime integration bridge.
Governance scope: connects formal verification to governance, orchestration,
    external execution, workflow, financial, and continuity runtimes.
Dependencies: verification_formal_runtime engine, event_spine, memory_mesh.
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
from mcoi_runtime.core.verification_formal_runtime import FormalVerificationEngine
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
        event_id=stable_identifier("evt-fvri", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class FormalVerificationIntegration:
    """Integration bridge for formal verification runtime."""

    def __init__(
        self,
        verification_engine: FormalVerificationEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(verification_engine, FormalVerificationEngine):
            raise RuntimeCoreInvariantError("verification_engine must be a FormalVerificationEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._ver = verification_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # -- Bridge helpers --

    def _next_bridge_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        spec_id = stable_identifier("vs", {"tenant": tenant_id, "source": source_type, "seq": seq})
        prop_id = stable_identifier("vp", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return spec_id, prop_id

    def _bridge(
        self,
        tenant_id: str,
        source_type: str,
        display_prefix: str,
    ) -> dict[str, Any]:
        spec_id, prop_id = self._next_bridge_ids(tenant_id, source_type)
        spec = self._ver.register_specification(
            spec_id=spec_id, tenant_id=tenant_id,
            display_name=f"{display_prefix}-spec",
            target_runtime=source_type,
        )
        prop = self._ver.add_property(
            property_id=prop_id, tenant_id=tenant_id,
            spec_ref=spec_id,
            expression=f"{source_type} safety property",
        )
        _emit(self._events, f"verify_for_{source_type}", {
            "tenant_id": tenant_id, "spec_id": spec_id, "property_id": prop_id,
        }, spec_id)
        return {
            "spec_id": spec.spec_id,
            "property_id": prop.property_id,
            "tenant_id": tenant_id,
            "spec_status": spec.status.value,
            "property_status": prop.status.value,
            "source_type": source_type,
        }

    # -- Bridge methods --

    def verify_governance(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "governance", "gov")

    def verify_orchestration(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "orchestration", "orch")

    def verify_external_execution(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "external_execution", "ext")

    def verify_workflow(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "workflow", "wf")

    def verify_financial(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "financial", "fin")

    def verify_continuity(self, tenant_id: str) -> dict[str, Any]:
        return self._bridge(tenant_id, "continuity", "cont")

    # -- Memory mesh --

    def attach_verification_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        mid = stable_identifier("mem-fvr", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content = {
            "total_specs": self._ver.spec_count,
            "total_properties": self._ver.property_count,
            "total_runs": self._ver.run_count,
            "total_certificates": self._ver.certificate_count,
            "total_counterexamples": self._ver.counterexample_count,
            "total_invariants": self._ver.invariant_count,
            "total_violations": self._ver.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Formal verification state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("formal_verification", "proof", "safety"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_verification_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return record

    # -- Graph --

    def attach_verification_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        return {
            "scope_ref_id": scope_ref_id,
            "total_specs": self._ver.spec_count,
            "total_properties": self._ver.property_count,
            "total_runs": self._ver.run_count,
            "total_certificates": self._ver.certificate_count,
            "total_counterexamples": self._ver.counterexample_count,
            "total_invariants": self._ver.invariant_count,
            "total_violations": self._ver.violation_count,
        }
