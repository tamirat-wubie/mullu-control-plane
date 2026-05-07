"""Purpose: experiment runtime integration bridge.
Governance scope: composing experiment runtime with research, self-tuning,
    policy simulation, quality events, process simulation, and forecasting;
    memory mesh and operational graph attachment.
Dependencies: experiment_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every experiment action emits events.
  - Experiment state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.experiment_runtime import (
    ExperimentPhase,
    ResultSignificance,
    VariableRole,
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
from .experiment_runtime import ExperimentRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-exint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class ExperimentRuntimeIntegration:
    """Integration bridge for experiment runtime with platform layers."""

    def __init__(
        self,
        experiment_engine: ExperimentRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(experiment_engine, ExperimentRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "experiment_engine must be an ExperimentRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._experiment = experiment_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Cross-domain experiment creation
    # ------------------------------------------------------------------

    def experiment_from_research(
        self,
        design_id: str,
        tenant_id: str,
        hypothesis_ref: str,
        research_ref: str,
        display_name: str,
    ) -> dict[str, Any]:
        """Create an experiment from a research hypothesis."""
        design = self._experiment.register_design(
            design_id, tenant_id, hypothesis_ref, display_name,
        )
        _emit(self._events, "experiment_from_research", {
            "design_id": design_id, "research_ref": research_ref,
        }, design_id)
        return {
            "design_id": design.design_id,
            "tenant_id": design.tenant_id,
            "hypothesis_ref": hypothesis_ref,
            "research_ref": research_ref,
            "phase": design.phase.value,
            "source_type": "research",
        }

    def experiment_from_self_tuning(
        self,
        design_id: str,
        tenant_id: str,
        hypothesis_ref: str,
        tuning_ref: str,
        display_name: str,
    ) -> dict[str, Any]:
        """Create an experiment from a self-tuning signal."""
        design = self._experiment.register_design(
            design_id, tenant_id, hypothesis_ref, display_name,
        )
        _emit(self._events, "experiment_from_self_tuning", {
            "design_id": design_id, "tuning_ref": tuning_ref,
        }, design_id)
        return {
            "design_id": design.design_id,
            "tenant_id": design.tenant_id,
            "hypothesis_ref": hypothesis_ref,
            "tuning_ref": tuning_ref,
            "phase": design.phase.value,
            "source_type": "self_tuning",
        }

    def experiment_from_policy_simulation(
        self,
        design_id: str,
        tenant_id: str,
        hypothesis_ref: str,
        policy_sim_ref: str,
        display_name: str,
    ) -> dict[str, Any]:
        """Create an experiment from a policy simulation scenario."""
        design = self._experiment.register_design(
            design_id, tenant_id, hypothesis_ref, display_name,
        )
        _emit(self._events, "experiment_from_policy_simulation", {
            "design_id": design_id, "policy_sim_ref": policy_sim_ref,
        }, design_id)
        return {
            "design_id": design.design_id,
            "tenant_id": design.tenant_id,
            "hypothesis_ref": hypothesis_ref,
            "policy_sim_ref": policy_sim_ref,
            "phase": design.phase.value,
            "source_type": "policy_simulation",
        }

    def experiment_from_quality_events(
        self,
        design_id: str,
        tenant_id: str,
        hypothesis_ref: str,
        quality_ref: str,
        display_name: str,
    ) -> dict[str, Any]:
        """Create an experiment from data quality events."""
        design = self._experiment.register_design(
            design_id, tenant_id, hypothesis_ref, display_name,
        )
        _emit(self._events, "experiment_from_quality_events", {
            "design_id": design_id, "quality_ref": quality_ref,
        }, design_id)
        return {
            "design_id": design.design_id,
            "tenant_id": design.tenant_id,
            "hypothesis_ref": hypothesis_ref,
            "quality_ref": quality_ref,
            "phase": design.phase.value,
            "source_type": "quality_events",
        }

    def experiment_from_process_simulation(
        self,
        design_id: str,
        tenant_id: str,
        hypothesis_ref: str,
        process_sim_ref: str,
        display_name: str,
    ) -> dict[str, Any]:
        """Create an experiment from a process simulation run."""
        design = self._experiment.register_design(
            design_id, tenant_id, hypothesis_ref, display_name,
        )
        _emit(self._events, "experiment_from_process_simulation", {
            "design_id": design_id, "process_sim_ref": process_sim_ref,
        }, design_id)
        return {
            "design_id": design.design_id,
            "tenant_id": design.tenant_id,
            "hypothesis_ref": hypothesis_ref,
            "process_sim_ref": process_sim_ref,
            "phase": design.phase.value,
            "source_type": "process_simulation",
        }

    def experiment_from_forecasting(
        self,
        design_id: str,
        tenant_id: str,
        hypothesis_ref: str,
        forecast_ref: str,
        display_name: str,
    ) -> dict[str, Any]:
        """Create an experiment from a forecasting signal."""
        design = self._experiment.register_design(
            design_id, tenant_id, hypothesis_ref, display_name,
        )
        _emit(self._events, "experiment_from_forecasting", {
            "design_id": design_id, "forecast_ref": forecast_ref,
        }, design_id)
        return {
            "design_id": design.design_id,
            "tenant_id": design.tenant_id,
            "hypothesis_ref": hypothesis_ref,
            "forecast_ref": forecast_ref,
            "phase": design.phase.value,
            "source_type": "forecasting",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_experiment_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist experiment state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_designs": self._experiment.design_count,
            "total_variables": self._experiment.variable_count,
            "total_groups": self._experiment.group_count,
            "total_results": self._experiment.result_count,
            "total_falsifications": self._experiment.falsification_count,
            "total_replications": self._experiment.replication_count,
            "total_violations": self._experiment.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-expt", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title="Experiment state",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("experiment", "scientific_method", "falsification"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "experiment_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_experiment_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return experiment state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_designs": self._experiment.design_count,
            "total_variables": self._experiment.variable_count,
            "total_groups": self._experiment.group_count,
            "total_results": self._experiment.result_count,
            "total_falsifications": self._experiment.falsification_count,
            "total_replications": self._experiment.replication_count,
            "total_violations": self._experiment.violation_count,
        }
