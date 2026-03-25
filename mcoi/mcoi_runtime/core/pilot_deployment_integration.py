"""Purpose: pilot deployment integration bridge.
Governance scope: connects the pilot deployment engine to regulated ops,
    research, factory, enterprise service, and financial control pilots;
    memory mesh and operational graph attachment.
Dependencies: PilotDeploymentEngine, EventSpineEngine, MemoryMeshEngine.
Invariants:
  - Constructor validates all three engine types.
  - All outputs are frozen dicts or MemoryRecord instances.
"""

from __future__ import annotations

from typing import Any

from mcoi_runtime.contracts.event import EventRecord, EventSource, EventType
from mcoi_runtime.contracts.pilot_deployment import (
    BootstrapStatus,
    ConnectorActivationStatus,
    MigrationStatus,
    PilotPhase,
)
from mcoi_runtime.contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError, stable_identifier
from mcoi_runtime.core.pilot_deployment import PilotDeploymentEngine
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
        event_id=stable_identifier("evt-pdint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.EXTERNAL,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)


class PilotDeploymentIntegration:
    """Integration bridge for pilot deployment runtime."""

    def __init__(
        self,
        pilot_engine: PilotDeploymentEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(pilot_engine, PilotDeploymentEngine):
            raise RuntimeCoreInvariantError("pilot_engine must be a PilotDeploymentEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._engine = pilot_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Bridge helpers
    # ------------------------------------------------------------------

    def _deploy_pilot(
        self, tenant_id: str, bootstrap_id: str, pilot_id: str, source_type: str,
    ) -> dict[str, Any]:
        """Bootstrap a tenant and register a pilot for a given source type."""
        bootstrap = self._engine.bootstrap_tenant(bootstrap_id, tenant_id, source_type)
        pilot = self._engine.register_pilot(pilot_id, tenant_id, source_type)
        _emit(self._events, f"deploy_{source_type}", {
            "tenant_id": tenant_id,
            "bootstrap_id": bootstrap_id,
            "pilot_id": pilot_id,
        }, bootstrap_id)
        return {
            "tenant_id": tenant_id,
            "bootstrap_id": bootstrap_id,
            "pilot_id": pilot_id,
            "bootstrap_status": bootstrap.status.value,
            "pilot_phase": pilot.phase.value,
            "source_type": source_type,
        }

    # ------------------------------------------------------------------
    # Deploy methods
    # ------------------------------------------------------------------

    def deploy_regulated_ops_pilot(
        self, tenant_id: str, bootstrap_id: str, pilot_id: str,
    ) -> dict[str, Any]:
        """Bootstrap tenant + register pilot for regulated operations."""
        return self._deploy_pilot(tenant_id, bootstrap_id, pilot_id, "regulated_ops_pilot")

    def deploy_research_pilot(
        self, tenant_id: str, bootstrap_id: str, pilot_id: str,
    ) -> dict[str, Any]:
        """Bootstrap tenant + register pilot for research."""
        return self._deploy_pilot(tenant_id, bootstrap_id, pilot_id, "research_pilot")

    def deploy_factory_pilot(
        self, tenant_id: str, bootstrap_id: str, pilot_id: str,
    ) -> dict[str, Any]:
        """Bootstrap tenant + register pilot for factory operations."""
        return self._deploy_pilot(tenant_id, bootstrap_id, pilot_id, "factory_pilot")

    def deploy_enterprise_service_pilot(
        self, tenant_id: str, bootstrap_id: str, pilot_id: str,
    ) -> dict[str, Any]:
        """Bootstrap tenant + register pilot for enterprise services."""
        return self._deploy_pilot(tenant_id, bootstrap_id, pilot_id, "enterprise_service_pilot")

    def deploy_financial_control_pilot(
        self, tenant_id: str, bootstrap_id: str, pilot_id: str,
    ) -> dict[str, Any]:
        """Bootstrap tenant + register pilot for financial control."""
        return self._deploy_pilot(tenant_id, bootstrap_id, pilot_id, "financial_control_pilot")

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_pilot_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        """Persist pilot deployment state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-pilot", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "total_bootstraps": self._engine.bootstrap_count,
            "total_connectors": self._engine.connector_count,
            "total_migrations": self._engine.migration_count,
            "total_pilots": self._engine.pilot_count,
            "total_checklists": self._engine.checklist_count,
            "total_runbooks": self._engine.runbook_count,
            "total_slos": self._engine.slo_count,
            "total_violations": self._engine.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Pilot deployment state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("pilot", "deployment", "bootstrap"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "attach_pilot_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return record

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_pilot_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        """Return pilot deployment state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_bootstraps": self._engine.bootstrap_count,
            "total_connectors": self._engine.connector_count,
            "total_migrations": self._engine.migration_count,
            "total_pilots": self._engine.pilot_count,
            "total_checklists": self._engine.checklist_count,
            "total_runbooks": self._engine.runbook_count,
            "total_slos": self._engine.slo_count,
            "total_violations": self._engine.violation_count,
        }
