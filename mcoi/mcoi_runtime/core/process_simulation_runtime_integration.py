"""Purpose: process simulation runtime integration bridge.
Governance scope: composing process simulation runtime engine with event spine,
    memory mesh, and operational graph. Provides convenience methods to create
    process simulations from various platform surface sources.
Dependencies: process_simulation_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every simulation operation emits events.
  - Process state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.process_simulation_runtime import (
    ProcessModelKind,
    SimulationDisposition,
    SimulationOutcomeKind,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .process_simulation_runtime import ProcessSimulationRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-pcsint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ProcessSimulationRuntimeIntegration:
    """Integration bridge for process simulation runtime with platform layers."""

    def __init__(
        self,
        simulation_engine: ProcessSimulationRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(simulation_engine, ProcessSimulationRuntimeEngine):
            raise RuntimeCoreInvariantError("simulation_engine must be a ProcessSimulationRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._simulation = simulation_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str, str, str]:
        """Generate deterministic model, scenario, run, and result IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        model_id = stable_identifier("mdl-pcsim", {"tenant": tenant_id, "source": source_type, "seq": seq})
        scenario_id = stable_identifier("scn-pcsim", {"tenant": tenant_id, "source": source_type, "seq": seq})
        run_id = stable_identifier("run-pcsim", {"tenant": tenant_id, "source": source_type, "seq": seq})
        result_id = stable_identifier("res-pcsim", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return model_id, scenario_id, run_id, result_id

    def _simulation_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        kind: ProcessModelKind = ProcessModelKind.THROUGHPUT,
        disposition: SimulationDisposition = SimulationDisposition.NOMINAL,
    ) -> dict[str, Any]:
        """Register a model, scenario, and run for a given source."""
        model_id, scenario_id, run_id, result_id = self._next_ids(tenant_id, source_type)

        model = self._simulation.register_process_model(
            model_id=model_id,
            tenant_id=tenant_id,
            display_name=f"{kind.value}_{source_type}",
            kind=kind,
        )
        scenario = self._simulation.register_simulation_scenario(
            scenario_id=scenario_id,
            tenant_id=tenant_id,
            model_ref=model_id,
            disposition=disposition,
            description="Process simulation scenario",
        )
        run = self._simulation.run_simulation(
            run_id=run_id,
            tenant_id=tenant_id,
            scenario_ref=scenario_id,
        )

        _emit(self._events, f"simulation_from_{source_type}", {
            "tenant_id": tenant_id,
            "model_id": model_id,
            "scenario_id": scenario_id,
            "run_id": run_id,
            "ref": ref,
        }, model_id)

        return {
            "model_id": model_id,
            "scenario_id": scenario_id,
            "run_id": run_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "kind": model.kind.value,
            "disposition": scenario.disposition.value,
            "status": run.status.value,
        }

    # ------------------------------------------------------------------
    # Surface-specific simulation methods
    # ------------------------------------------------------------------

    def simulation_from_factory_runtime(
        self,
        tenant_id: str,
        factory_ref: str,
        kind: ProcessModelKind = ProcessModelKind.THROUGHPUT,
        disposition: SimulationDisposition = SimulationDisposition.NOMINAL,
    ) -> dict[str, Any]:
        """Create simulation from factory runtime source."""
        return self._simulation_for_source(
            tenant_id=tenant_id,
            ref=factory_ref,
            source_type="factory_runtime",
            kind=kind,
            disposition=disposition,
        )

    def simulation_from_digital_twin(
        self,
        tenant_id: str,
        twin_ref: str,
        kind: ProcessModelKind = ProcessModelKind.THERMAL,
        disposition: SimulationDisposition = SimulationDisposition.NOMINAL,
    ) -> dict[str, Any]:
        """Create simulation from digital twin source."""
        return self._simulation_for_source(
            tenant_id=tenant_id,
            ref=twin_ref,
            source_type="digital_twin",
            kind=kind,
            disposition=disposition,
        )

    def simulation_from_asset_runtime(
        self,
        tenant_id: str,
        asset_ref: str,
        kind: ProcessModelKind = ProcessModelKind.DEGRADATION,
        disposition: SimulationDisposition = SimulationDisposition.NOMINAL,
    ) -> dict[str, Any]:
        """Create simulation from asset runtime source."""
        return self._simulation_for_source(
            tenant_id=tenant_id,
            ref=asset_ref,
            source_type="asset_runtime",
            kind=kind,
            disposition=disposition,
        )

    def simulation_from_quality_events(
        self,
        tenant_id: str,
        quality_ref: str,
        kind: ProcessModelKind = ProcessModelKind.YIELD,
        disposition: SimulationDisposition = SimulationDisposition.NOMINAL,
    ) -> dict[str, Any]:
        """Create simulation from quality events source."""
        return self._simulation_for_source(
            tenant_id=tenant_id,
            ref=quality_ref,
            source_type="quality_events",
            kind=kind,
            disposition=disposition,
        )

    def simulation_from_continuity_runtime(
        self,
        tenant_id: str,
        continuity_ref: str,
        kind: ProcessModelKind = ProcessModelKind.FLOW,
        disposition: SimulationDisposition = SimulationDisposition.NOMINAL,
    ) -> dict[str, Any]:
        """Create simulation from continuity runtime source."""
        return self._simulation_for_source(
            tenant_id=tenant_id,
            ref=continuity_ref,
            source_type="continuity_runtime",
            kind=kind,
            disposition=disposition,
        )

    def simulation_from_forecasting_runtime(
        self,
        tenant_id: str,
        forecast_ref: str,
        kind: ProcessModelKind = ProcessModelKind.TIMING,
        disposition: SimulationDisposition = SimulationDisposition.NOMINAL,
    ) -> dict[str, Any]:
        """Create simulation from forecasting runtime source."""
        return self._simulation_for_source(
            tenant_id=tenant_id,
            ref=forecast_ref,
            source_type="forecasting_runtime",
            kind=kind,
            disposition=disposition,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_process_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist process simulation state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-pcsim", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_models": self._simulation.model_count,
            "total_parameters": self._simulation.parameter_count,
            "total_scenarios": self._simulation.scenario_count,
            "total_runs": self._simulation.run_count,
            "total_results": self._simulation.result_count,
            "total_envelopes": self._simulation.envelope_count,
            "total_violations": self._simulation.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title="Process simulation state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("process_simulation", "physics", "engineering"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "process_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_process_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return process simulation state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_models": self._simulation.model_count,
            "total_parameters": self._simulation.parameter_count,
            "total_scenarios": self._simulation.scenario_count,
            "total_runs": self._simulation.run_count,
            "total_results": self._simulation.result_count,
            "total_envelopes": self._simulation.envelope_count,
            "total_violations": self._simulation.violation_count,
        }
