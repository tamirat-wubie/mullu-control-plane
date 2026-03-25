"""Purpose: continuity runtime integration bridge.
Governance scope: composing continuity runtime with assets, connectors,
    environments, fault campaigns, service requests, and programs;
    memory mesh and operational graph attachment.
Dependencies: continuity_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every continuity action emits events.
  - Continuity state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.continuity_runtime import (
    ContinuityScope,
    DisruptionSeverity,
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
from .continuity_runtime import ContinuityRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ContinuityRuntimeIntegration:
    """Integration bridge for continuity runtime with platform layers."""

    def __init__(
        self,
        continuity_engine: ContinuityRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(continuity_engine, ContinuityRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "continuity_engine must be a ContinuityRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._continuity = continuity_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Disruption creation helpers
    # ------------------------------------------------------------------

    def continuity_from_asset_failure(
        self,
        disruption_id: str,
        tenant_id: str,
        asset_ref: str,
        *,
        severity: DisruptionSeverity = DisruptionSeverity.HIGH,
        description: str = "",
    ) -> dict[str, Any]:
        """Record a disruption from an asset failure."""
        d = self._continuity.record_disruption(
            disruption_id, tenant_id,
            scope=ContinuityScope.ASSET, scope_ref_id=asset_ref,
            severity=severity,
            description=description or f"Asset failure: {asset_ref}",
        )
        _emit(self._events, "continuity_from_asset_failure", {
            "disruption_id": disruption_id, "asset_ref": asset_ref,
        }, disruption_id)
        return {
            "disruption_id": d.disruption_id,
            "tenant_id": d.tenant_id,
            "asset_ref": asset_ref,
            "scope": d.scope.value,
            "severity": d.severity.value,
            "source_type": "asset_failure",
        }

    def continuity_from_connector_failure(
        self,
        disruption_id: str,
        tenant_id: str,
        connector_ref: str,
        *,
        severity: DisruptionSeverity = DisruptionSeverity.HIGH,
        description: str = "",
    ) -> dict[str, Any]:
        """Record a disruption from a connector failure."""
        d = self._continuity.record_disruption(
            disruption_id, tenant_id,
            scope=ContinuityScope.CONNECTOR, scope_ref_id=connector_ref,
            severity=severity,
            description=description or f"Connector failure: {connector_ref}",
        )
        _emit(self._events, "continuity_from_connector_failure", {
            "disruption_id": disruption_id, "connector_ref": connector_ref,
        }, disruption_id)
        return {
            "disruption_id": d.disruption_id,
            "tenant_id": d.tenant_id,
            "connector_ref": connector_ref,
            "scope": d.scope.value,
            "severity": d.severity.value,
            "source_type": "connector_failure",
        }

    def continuity_from_environment_degradation(
        self,
        disruption_id: str,
        tenant_id: str,
        environment_ref: str,
        *,
        severity: DisruptionSeverity = DisruptionSeverity.MEDIUM,
        description: str = "",
    ) -> dict[str, Any]:
        """Record a disruption from environment degradation."""
        d = self._continuity.record_disruption(
            disruption_id, tenant_id,
            scope=ContinuityScope.ENVIRONMENT, scope_ref_id=environment_ref,
            severity=severity,
            description=description or f"Environment degradation: {environment_ref}",
        )
        _emit(self._events, "continuity_from_environment_degradation", {
            "disruption_id": disruption_id, "environment_ref": environment_ref,
        }, disruption_id)
        return {
            "disruption_id": d.disruption_id,
            "tenant_id": d.tenant_id,
            "environment_ref": environment_ref,
            "scope": d.scope.value,
            "severity": d.severity.value,
            "source_type": "environment_degradation",
        }

    def continuity_from_fault_campaign(
        self,
        disruption_id: str,
        tenant_id: str,
        campaign_ref: str,
        *,
        severity: DisruptionSeverity = DisruptionSeverity.MEDIUM,
        description: str = "",
    ) -> dict[str, Any]:
        """Record a disruption from a fault campaign (drill/injection)."""
        d = self._continuity.record_disruption(
            disruption_id, tenant_id,
            scope=ContinuityScope.SERVICE, scope_ref_id=campaign_ref,
            severity=severity,
            description=description or f"Fault campaign: {campaign_ref}",
        )
        _emit(self._events, "continuity_from_fault_campaign", {
            "disruption_id": disruption_id, "campaign_ref": campaign_ref,
        }, disruption_id)
        return {
            "disruption_id": d.disruption_id,
            "tenant_id": d.tenant_id,
            "campaign_ref": campaign_ref,
            "scope": d.scope.value,
            "severity": d.severity.value,
            "source_type": "fault_campaign",
        }

    # ------------------------------------------------------------------
    # Binding helpers
    # ------------------------------------------------------------------

    def bind_continuity_to_service_request(
        self,
        plan_id: str,
        service_request_ref: str,
    ) -> dict[str, Any]:
        """Bind a continuity plan to a service request."""
        plan = self._continuity.get_plan(plan_id)
        _emit(self._events, "continuity_bound_to_service_request", {
            "plan_id": plan_id, "service_request_ref": service_request_ref,
        }, plan_id)
        return {
            "plan_id": plan.plan_id,
            "name": plan.name,
            "service_request_ref": service_request_ref,
            "status": plan.status.value,
            "binding_type": "service_request",
        }

    def bind_continuity_to_program(
        self,
        plan_id: str,
        program_ref: str,
    ) -> dict[str, Any]:
        """Bind a continuity plan to a program."""
        plan = self._continuity.get_plan(plan_id)
        _emit(self._events, "continuity_bound_to_program", {
            "plan_id": plan_id, "program_ref": program_ref,
        }, plan_id)
        return {
            "plan_id": plan.plan_id,
            "name": plan.name,
            "program_ref": program_ref,
            "status": plan.status.value,
            "binding_type": "program",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_continuity_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist continuity state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_plans": self._continuity.plan_count,
            "total_recovery_plans": self._continuity.recovery_plan_count,
            "total_disruptions": self._continuity.disruption_count,
            "total_failovers": self._continuity.failover_count,
            "total_executions": self._continuity.execution_count,
            "total_objectives": self._continuity.objective_count,
            "total_verifications": self._continuity.verification_count,
            "total_violations": self._continuity.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-cont", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Continuity state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("continuity", "disaster_recovery", "failover"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "continuity_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_continuity_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return continuity state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_plans": self._continuity.plan_count,
            "total_recovery_plans": self._continuity.recovery_plan_count,
            "total_disruptions": self._continuity.disruption_count,
            "total_failovers": self._continuity.failover_count,
            "total_executions": self._continuity.execution_count,
            "total_objectives": self._continuity.objective_count,
            "total_verifications": self._continuity.verification_count,
            "total_violations": self._continuity.violation_count,
        }
