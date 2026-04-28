"""Purpose: policy simulation integration bridge.
Governance scope: composing policy simulation with service, release,
    financial, workforce, marketplace, and constitutional policy changes;
    memory mesh and graph attachment.
Dependencies: policy_simulation engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every simulation action emits events.
  - Simulation state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.policy_simulation import (
    DiffDisposition,
    PolicyImpactLevel,
    SandboxScope,
    SimulationMode,
)
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from mcoi_runtime.governance.policy.simulation import PolicySimulationEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-psimint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class PolicySimulationIntegration:
    """Integration bridge for policy simulation with platform layers."""

    def __init__(
        self,
        simulation_engine: PolicySimulationEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(simulation_engine, PolicySimulationEngine):
            raise RuntimeCoreInvariantError(
                "simulation_engine must be a PolicySimulationEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._sim = simulation_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Simulate service policy change
    # ------------------------------------------------------------------

    def simulate_service_policy_change(
        self,
        request_id: str,
        tenant_id: str,
        scenario_id: str,
        baseline_outcome: str = "allowed",
        simulated_outcome: str = "denied",
        impact_level: PolicyImpactLevel = PolicyImpactLevel.MEDIUM,
    ) -> dict[str, Any]:
        sim = self._sim.register_simulation(
            request_id, tenant_id, "Service policy change simulation",
            SimulationMode.DRY_RUN, SandboxScope.SERVICE,
        )
        scenario = self._sim.add_scenario(
            scenario_id, request_id, tenant_id, "Service policy impact",
            "service_catalog", baseline_outcome, simulated_outcome, impact_level,
        )
        self._sim.start_simulation(request_id)
        self._sim.complete_simulation(request_id)
        result = self._sim.produce_result(request_id)
        _emit(self._events, "simulate_service_policy_change", {
            "request_id": request_id, "readiness": result.adoption_readiness.value,
        }, request_id)
        return {
            "request_id": sim.request_id,
            "scenario_id": scenario.scenario_id,
            "tenant_id": tenant_id,
            "target_runtime": "service_catalog",
            "impact_level": scenario.impact_level.value,
            "adoption_readiness": result.adoption_readiness.value,
            "readiness_score": result.readiness_score,
            "source_type": "service_policy",
        }

    # ------------------------------------------------------------------
    # Simulate release policy change
    # ------------------------------------------------------------------

    def simulate_release_policy_change(
        self,
        request_id: str,
        tenant_id: str,
        scenario_id: str,
        baseline_outcome: str = "allowed",
        simulated_outcome: str = "denied",
        impact_level: PolicyImpactLevel = PolicyImpactLevel.HIGH,
    ) -> dict[str, Any]:
        sim = self._sim.register_simulation(
            request_id, tenant_id, "Release policy change simulation",
            SimulationMode.DRY_RUN, SandboxScope.RUNTIME,
        )
        scenario = self._sim.add_scenario(
            scenario_id, request_id, tenant_id, "Release policy impact",
            "product_ops", baseline_outcome, simulated_outcome, impact_level,
        )
        self._sim.start_simulation(request_id)
        self._sim.complete_simulation(request_id)
        result = self._sim.produce_result(request_id)
        _emit(self._events, "simulate_release_policy_change", {
            "request_id": request_id, "readiness": result.adoption_readiness.value,
        }, request_id)
        return {
            "request_id": sim.request_id,
            "scenario_id": scenario.scenario_id,
            "tenant_id": tenant_id,
            "target_runtime": "product_ops",
            "impact_level": scenario.impact_level.value,
            "adoption_readiness": result.adoption_readiness.value,
            "readiness_score": result.readiness_score,
            "source_type": "release_policy",
        }

    # ------------------------------------------------------------------
    # Simulate financial policy change
    # ------------------------------------------------------------------

    def simulate_financial_policy_change(
        self,
        request_id: str,
        tenant_id: str,
        scenario_id: str,
        baseline_outcome: str = "allowed",
        simulated_outcome: str = "restricted",
        impact_level: PolicyImpactLevel = PolicyImpactLevel.MEDIUM,
    ) -> dict[str, Any]:
        sim = self._sim.register_simulation(
            request_id, tenant_id, "Financial policy change simulation",
            SimulationMode.DRY_RUN, SandboxScope.FINANCIAL,
        )
        scenario = self._sim.add_scenario(
            scenario_id, request_id, tenant_id, "Financial policy impact",
            "billing", baseline_outcome, simulated_outcome, impact_level,
        )
        self._sim.start_simulation(request_id)
        self._sim.complete_simulation(request_id)
        result = self._sim.produce_result(request_id)
        _emit(self._events, "simulate_financial_policy_change", {
            "request_id": request_id,
        }, request_id)
        return {
            "request_id": sim.request_id,
            "scenario_id": scenario.scenario_id,
            "tenant_id": tenant_id,
            "target_runtime": "billing",
            "impact_level": scenario.impact_level.value,
            "adoption_readiness": result.adoption_readiness.value,
            "readiness_score": result.readiness_score,
            "source_type": "financial_policy",
        }

    # ------------------------------------------------------------------
    # Simulate workforce policy change
    # ------------------------------------------------------------------

    def simulate_workforce_policy_change(
        self,
        request_id: str,
        tenant_id: str,
        scenario_id: str,
        baseline_outcome: str = "assigned",
        simulated_outcome: str = "reassigned",
        impact_level: PolicyImpactLevel = PolicyImpactLevel.LOW,
    ) -> dict[str, Any]:
        sim = self._sim.register_simulation(
            request_id, tenant_id, "Workforce policy change simulation",
            SimulationMode.SHADOW, SandboxScope.RUNTIME,
        )
        scenario = self._sim.add_scenario(
            scenario_id, request_id, tenant_id, "Workforce policy impact",
            "workforce", baseline_outcome, simulated_outcome, impact_level,
        )
        self._sim.start_simulation(request_id)
        self._sim.complete_simulation(request_id)
        result = self._sim.produce_result(request_id)
        _emit(self._events, "simulate_workforce_policy_change", {
            "request_id": request_id,
        }, request_id)
        return {
            "request_id": sim.request_id,
            "scenario_id": scenario.scenario_id,
            "tenant_id": tenant_id,
            "target_runtime": "workforce",
            "impact_level": scenario.impact_level.value,
            "adoption_readiness": result.adoption_readiness.value,
            "readiness_score": result.readiness_score,
            "source_type": "workforce_policy",
        }

    # ------------------------------------------------------------------
    # Simulate marketplace policy change
    # ------------------------------------------------------------------

    def simulate_marketplace_policy_change(
        self,
        request_id: str,
        tenant_id: str,
        scenario_id: str,
        baseline_outcome: str = "eligible",
        simulated_outcome: str = "ineligible",
        impact_level: PolicyImpactLevel = PolicyImpactLevel.HIGH,
    ) -> dict[str, Any]:
        sim = self._sim.register_simulation(
            request_id, tenant_id, "Marketplace policy change simulation",
            SimulationMode.DRY_RUN, SandboxScope.RUNTIME,
        )
        scenario = self._sim.add_scenario(
            scenario_id, request_id, tenant_id, "Marketplace policy impact",
            "marketplace", baseline_outcome, simulated_outcome, impact_level,
        )
        self._sim.start_simulation(request_id)
        self._sim.complete_simulation(request_id)
        result = self._sim.produce_result(request_id)
        _emit(self._events, "simulate_marketplace_policy_change", {
            "request_id": request_id,
        }, request_id)
        return {
            "request_id": sim.request_id,
            "scenario_id": scenario.scenario_id,
            "tenant_id": tenant_id,
            "target_runtime": "marketplace",
            "impact_level": scenario.impact_level.value,
            "adoption_readiness": result.adoption_readiness.value,
            "readiness_score": result.readiness_score,
            "source_type": "marketplace_policy",
        }

    # ------------------------------------------------------------------
    # Simulate constitutional change
    # ------------------------------------------------------------------

    def simulate_constitutional_change(
        self,
        request_id: str,
        tenant_id: str,
        scenario_id: str,
        baseline_outcome: str = "allowed",
        simulated_outcome: str = "denied",
        impact_level: PolicyImpactLevel = PolicyImpactLevel.CRITICAL,
    ) -> dict[str, Any]:
        sim = self._sim.register_simulation(
            request_id, tenant_id, "Constitutional change simulation",
            SimulationMode.FULL, SandboxScope.CONSTITUTIONAL,
        )
        scenario = self._sim.add_scenario(
            scenario_id, request_id, tenant_id, "Constitutional impact",
            "constitutional_governance", baseline_outcome, simulated_outcome, impact_level,
        )
        self._sim.start_simulation(request_id)
        self._sim.complete_simulation(request_id)
        result = self._sim.produce_result(request_id)
        _emit(self._events, "simulate_constitutional_change", {
            "request_id": request_id, "readiness": result.adoption_readiness.value,
        }, request_id)
        return {
            "request_id": sim.request_id,
            "scenario_id": scenario.scenario_id,
            "tenant_id": tenant_id,
            "target_runtime": "constitutional_governance",
            "impact_level": scenario.impact_level.value,
            "adoption_readiness": result.adoption_readiness.value,
            "readiness_score": result.readiness_score,
            "source_type": "constitutional_change",
        }

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def attach_simulation_state_to_memory_mesh(self, scope_ref_id: str) -> MemoryRecord:
        now = _now_iso()
        snap = self._sim.sandbox_snapshot(
            snapshot_id=stable_identifier("snap-psim", {"scope": scope_ref_id, "ts": now}),
            tenant_id=scope_ref_id,
        )
        content = {
            "total_simulations": snap.total_simulations,
            "completed_simulations": snap.completed_simulations,
            "total_scenarios": snap.total_scenarios,
            "total_diffs": snap.total_diffs,
            "total_impacts": snap.total_impacts,
            "total_violations": snap.total_violations,
        }
        mem = MemoryRecord(
            memory_id=stable_identifier("mem-psim", {"scope": scope_ref_id, "seq": str(self._memory.memory_count)}),
            scope_ref_id=scope_ref_id,
            title="Policy simulation state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("policy_simulation", "governance_sandbox", "what_if"),
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)
        _emit(self._events, "attach_simulation_state_to_memory_mesh", {
            "scope_ref_id": scope_ref_id,
        }, scope_ref_id)
        return mem

    # ------------------------------------------------------------------
    # Graph attachment
    # ------------------------------------------------------------------

    def attach_simulation_state_to_graph(self, scope_ref_id: str) -> dict[str, Any]:
        snap = self._sim.sandbox_snapshot(
            snapshot_id=stable_identifier("gsnap-psim", {"scope": scope_ref_id, "ts": _now_iso()}),
            tenant_id=scope_ref_id,
        )
        return {
            "scope_ref_id": scope_ref_id,
            "total_simulations": snap.total_simulations,
            "completed_simulations": snap.completed_simulations,
            "total_scenarios": snap.total_scenarios,
            "total_diffs": snap.total_diffs,
            "total_impacts": snap.total_impacts,
            "total_violations": snap.total_violations,
        }
