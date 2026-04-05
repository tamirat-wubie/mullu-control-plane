"""Purpose: industry pack integration bridge.
Governance scope: connects the industry pack engine to regulated operations,
    research operations, factory operations, financial control, enterprise
    service runtimes, memory mesh, and operational graph.
Dependencies: IndustryPackEngine, EventSpineEngine, MemoryMeshEngine.
Invariants:
  - Constructor validates all three engine types.
  - All outputs are frozen dicts or MemoryRecord instances.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.industry_pack import (
    PackCapabilityKind,
    PackDomain,
)
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.industry_pack import IndustryPackEngine
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
        event_id=stable_identifier("evt-ipki", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class IndustryPackIntegration:
    """Integration bridge for industry pack runtime."""

    def __init__(
        self,
        pack_engine: IndustryPackEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(pack_engine, IndustryPackEngine):
            raise RuntimeCoreInvariantError("pack_engine must be an IndustryPackEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._engine = pack_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # -- Bridge helpers --

    def _next_bridge_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        pack_id = stable_identifier("ipk-bridge", {"t": tenant_id, "src": source_type, "seq": seq})
        cid = stable_identifier("cid-ipk", {"t": tenant_id, "src": source_type, "seq": seq})
        return pack_id, cid

    def _bridge_result(self, pack_id: str, tenant_id: str, source_type: str) -> dict[str, Any]:
        pack = self._engine.get_pack(pack_id)
        return {
            "pack_id": pack.pack_id,
            "tenant_id": tenant_id,
            "domain": pack.domain.value,
            "capability_count": pack.capability_count,
            "status": pack.status.value,
            "source_type": source_type,
        }

    # -- Bridge methods --

    def pack_from_regulated_operations(self, tenant_id: str, pack_id: str) -> dict[str, Any]:
        """Bootstrap a Regulated Operations Control Tower pack."""
        summary = self._engine.bootstrap_regulated_ops_pack(pack_id, tenant_id)
        _emit(self._events, "pack_from_regulated_operations", {
            "pack_id": pack_id, "tenant_id": tenant_id,
        }, pack_id)
        result = self._bridge_result(pack_id, tenant_id, "regulated_operations")
        return result

    def pack_from_research_operations(self, tenant_id: str, pack_id: str) -> dict[str, Any]:
        """Create a Research Lab pack with relevant capabilities."""
        self._engine.register_pack(pack_id, tenant_id, "Research Lab Pack", PackDomain.RESEARCH_LAB)
        kinds = [
            PackCapabilityKind.INTAKE,
            PackCapabilityKind.EVIDENCE,
            PackCapabilityKind.REPORTING,
            PackCapabilityKind.DASHBOARD,
            PackCapabilityKind.OBSERVABILITY,
            PackCapabilityKind.COPILOT,
            PackCapabilityKind.GOVERNANCE,
        ]
        for kind in kinds:
            self._engine.add_capability(
                capability_id=f"{pack_id}-cap-{kind.value}",
                tenant_id=tenant_id,
                pack_ref=pack_id,
                kind=kind,
                target_runtime=f"rt-{kind.value}",
                enabled=True,
            )
        _emit(self._events, "pack_from_research_operations", {
            "pack_id": pack_id, "tenant_id": tenant_id,
        }, pack_id)
        return self._bridge_result(pack_id, tenant_id, "research_operations")

    def pack_from_factory_operations(self, tenant_id: str, pack_id: str) -> dict[str, Any]:
        """Create a Factory Quality pack with relevant capabilities."""
        self._engine.register_pack(pack_id, tenant_id, "Factory Quality Pack", PackDomain.FACTORY_QUALITY)
        kinds = [
            PackCapabilityKind.INTAKE,
            PackCapabilityKind.CASE_MANAGEMENT,
            PackCapabilityKind.EVIDENCE,
            PackCapabilityKind.REPORTING,
            PackCapabilityKind.DASHBOARD,
            PackCapabilityKind.OBSERVABILITY,
            PackCapabilityKind.CONTINUITY,
        ]
        for kind in kinds:
            self._engine.add_capability(
                capability_id=f"{pack_id}-cap-{kind.value}",
                tenant_id=tenant_id,
                pack_ref=pack_id,
                kind=kind,
                target_runtime=f"rt-{kind.value}",
                enabled=True,
            )
        _emit(self._events, "pack_from_factory_operations", {
            "pack_id": pack_id, "tenant_id": tenant_id,
        }, pack_id)
        return self._bridge_result(pack_id, tenant_id, "factory_operations")

    def pack_from_financial_control(self, tenant_id: str, pack_id: str) -> dict[str, Any]:
        """Create a Financial Control pack with relevant capabilities."""
        self._engine.register_pack(pack_id, tenant_id, "Financial Control Pack", PackDomain.FINANCIAL_CONTROL)
        kinds = [
            PackCapabilityKind.INTAKE,
            PackCapabilityKind.APPROVAL,
            PackCapabilityKind.EVIDENCE,
            PackCapabilityKind.REPORTING,
            PackCapabilityKind.GOVERNANCE,
            PackCapabilityKind.OBSERVABILITY,
            PackCapabilityKind.DASHBOARD,
        ]
        for kind in kinds:
            self._engine.add_capability(
                capability_id=f"{pack_id}-cap-{kind.value}",
                tenant_id=tenant_id,
                pack_ref=pack_id,
                kind=kind,
                target_runtime=f"rt-{kind.value}",
                enabled=True,
            )
        _emit(self._events, "pack_from_financial_control", {
            "pack_id": pack_id, "tenant_id": tenant_id,
        }, pack_id)
        return self._bridge_result(pack_id, tenant_id, "financial_control")

    def pack_from_enterprise_service(self, tenant_id: str, pack_id: str) -> dict[str, Any]:
        """Create an Enterprise Service pack with relevant capabilities."""
        self._engine.register_pack(pack_id, tenant_id, "Enterprise Service Pack", PackDomain.ENTERPRISE_SERVICE)
        kinds = [
            PackCapabilityKind.INTAKE,
            PackCapabilityKind.CASE_MANAGEMENT,
            PackCapabilityKind.APPROVAL,
            PackCapabilityKind.REPORTING,
            PackCapabilityKind.DASHBOARD,
            PackCapabilityKind.COPILOT,
            PackCapabilityKind.GOVERNANCE,
        ]
        for kind in kinds:
            self._engine.add_capability(
                capability_id=f"{pack_id}-cap-{kind.value}",
                tenant_id=tenant_id,
                pack_ref=pack_id,
                kind=kind,
                target_runtime=f"rt-{kind.value}",
                enabled=True,
            )
        _emit(self._events, "pack_from_enterprise_service", {
            "pack_id": pack_id, "tenant_id": tenant_id,
        }, pack_id)
        return self._bridge_result(pack_id, tenant_id, "enterprise_service")

    # -- Memory mesh --

    def attach_pack_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        """Attach industry pack state summary to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-ipk", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content = {
            "total_packs": self._engine.pack_count,
            "total_capabilities": self._engine.capability_count,
            "total_configs": self._engine.config_count,
            "total_bindings": self._engine.binding_count,
            "total_deployments": self._engine.deployment_count,
            "total_violations": self._engine.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title="Industry pack state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("industry_pack", "deployment", "operations"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_pack_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return record

    # -- Graph --

    def attach_pack_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        """Attach industry pack state summary for graph integration."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_packs": self._engine.pack_count,
            "total_capabilities": self._engine.capability_count,
            "total_configs": self._engine.config_count,
            "total_bindings": self._engine.binding_count,
            "total_deployments": self._engine.deployment_count,
            "total_violations": self._engine.violation_count,
        }
