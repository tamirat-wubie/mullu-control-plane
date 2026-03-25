"""Purpose: uncertainty runtime integration bridge.
Governance scope: composing uncertainty runtime with forecasting, research,
    copilot, executive reporting, assurance, and policy simulation layers;
    memory mesh and operational graph attachment.
Dependencies: uncertainty_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every uncertainty action emits events.
  - Uncertainty state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.uncertainty_runtime import (
    BeliefStatus,
    EvidenceWeight,
    HypothesisDisposition,
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
from .uncertainty_runtime import UncertaintyRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-uint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class UncertaintyRuntimeIntegration:
    """Integration bridge for uncertainty runtime with platform layers."""

    def __init__(
        self,
        uncertainty_engine: UncertaintyRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(uncertainty_engine, UncertaintyRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "uncertainty_engine must be an UncertaintyRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._uncertainty = uncertainty_engine
        self._events = event_spine
        self._memory = memory_engine

    # ------------------------------------------------------------------
    # Cross-domain belief creation helpers
    # ------------------------------------------------------------------

    def uncertainty_from_forecasting(
        self,
        belief_id: str,
        tenant_id: str,
        forecast_ref: str,
        *,
        content: str = "Belief derived from forecasting",
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Create a belief from forecasting uncertainty."""
        b = self._uncertainty.register_belief(
            belief_id, tenant_id, content, confidence=confidence,
        )
        _emit(self._events, "uncertainty_from_forecasting", {
            "belief_id": belief_id, "forecast_ref": forecast_ref,
        }, belief_id)
        return {
            "belief_id": b.belief_id,
            "tenant_id": b.tenant_id,
            "forecast_ref": forecast_ref,
            "status": b.status.value,
            "confidence": b.confidence,
            "source_type": "forecasting",
        }

    def uncertainty_from_research(
        self,
        belief_id: str,
        tenant_id: str,
        research_ref: str,
        *,
        content: str = "Belief derived from research",
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Create a belief from research findings."""
        b = self._uncertainty.register_belief(
            belief_id, tenant_id, content, confidence=confidence,
        )
        _emit(self._events, "uncertainty_from_research", {
            "belief_id": belief_id, "research_ref": research_ref,
        }, belief_id)
        return {
            "belief_id": b.belief_id,
            "tenant_id": b.tenant_id,
            "research_ref": research_ref,
            "status": b.status.value,
            "confidence": b.confidence,
            "source_type": "research",
        }

    def uncertainty_from_copilot(
        self,
        belief_id: str,
        tenant_id: str,
        copilot_ref: str,
        *,
        content: str = "Belief derived from copilot interaction",
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Create a belief from copilot interaction."""
        b = self._uncertainty.register_belief(
            belief_id, tenant_id, content, confidence=confidence,
        )
        _emit(self._events, "uncertainty_from_copilot", {
            "belief_id": belief_id, "copilot_ref": copilot_ref,
        }, belief_id)
        return {
            "belief_id": b.belief_id,
            "tenant_id": b.tenant_id,
            "copilot_ref": copilot_ref,
            "status": b.status.value,
            "confidence": b.confidence,
            "source_type": "copilot",
        }

    def uncertainty_from_executive_reporting(
        self,
        belief_id: str,
        tenant_id: str,
        report_ref: str,
        *,
        content: str = "Belief derived from executive reporting",
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Create a belief from executive reporting data."""
        b = self._uncertainty.register_belief(
            belief_id, tenant_id, content, confidence=confidence,
        )
        _emit(self._events, "uncertainty_from_executive_reporting", {
            "belief_id": belief_id, "report_ref": report_ref,
        }, belief_id)
        return {
            "belief_id": b.belief_id,
            "tenant_id": b.tenant_id,
            "report_ref": report_ref,
            "status": b.status.value,
            "confidence": b.confidence,
            "source_type": "executive_reporting",
        }

    def uncertainty_from_assurance(
        self,
        belief_id: str,
        tenant_id: str,
        assurance_ref: str,
        *,
        content: str = "Belief derived from assurance assessment",
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Create a belief from assurance assessment."""
        b = self._uncertainty.register_belief(
            belief_id, tenant_id, content, confidence=confidence,
        )
        _emit(self._events, "uncertainty_from_assurance", {
            "belief_id": belief_id, "assurance_ref": assurance_ref,
        }, belief_id)
        return {
            "belief_id": b.belief_id,
            "tenant_id": b.tenant_id,
            "assurance_ref": assurance_ref,
            "status": b.status.value,
            "confidence": b.confidence,
            "source_type": "assurance",
        }

    def uncertainty_from_policy_simulation(
        self,
        belief_id: str,
        tenant_id: str,
        simulation_ref: str,
        *,
        content: str = "Belief derived from policy simulation",
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Create a belief from policy simulation results."""
        b = self._uncertainty.register_belief(
            belief_id, tenant_id, content, confidence=confidence,
        )
        _emit(self._events, "uncertainty_from_policy_simulation", {
            "belief_id": belief_id, "simulation_ref": simulation_ref,
        }, belief_id)
        return {
            "belief_id": b.belief_id,
            "tenant_id": b.tenant_id,
            "simulation_ref": simulation_ref,
            "status": b.status.value,
            "confidence": b.confidence,
            "source_type": "policy_simulation",
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_uncertainty_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist uncertainty state to memory mesh."""
        now = _now_iso()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_beliefs": self._uncertainty.belief_count,
            "total_hypotheses": self._uncertainty.hypothesis_count,
            "total_weights": self._uncertainty.weight_count,
            "total_intervals": self._uncertainty.interval_count,
            "total_updates": self._uncertainty.update_count,
            "total_sets": self._uncertainty.set_count,
            "total_violations": self._uncertainty.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-uncert", {"id": scope_ref_id}),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Uncertainty state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("uncertainty", "belief", "hypothesis"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "uncertainty_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id)
        return mem

    def attach_uncertainty_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return uncertainty state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_beliefs": self._uncertainty.belief_count,
            "total_hypotheses": self._uncertainty.hypothesis_count,
            "total_weights": self._uncertainty.weight_count,
            "total_intervals": self._uncertainty.interval_count,
            "total_updates": self._uncertainty.update_count,
            "total_sets": self._uncertainty.set_count,
            "total_violations": self._uncertainty.violation_count,
        }
