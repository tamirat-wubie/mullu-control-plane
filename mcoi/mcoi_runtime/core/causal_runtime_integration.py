"""Purpose: causal runtime integration bridge.
Governance scope: composing causal runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create causal bindings
    from various platform surface sources.
Dependencies: causal_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every causal operation emits events.
  - Causal state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.causal_runtime import (
    CausalEdgeKind,
    CausalStatus,
    AttributionStrength,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .causal_runtime import CausalRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-causint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class CausalRuntimeIntegration:
    """Integration bridge for causal runtime with platform layers."""

    def __init__(
        self,
        causal_engine: CausalRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(causal_engine, CausalRuntimeEngine):
            raise RuntimeCoreInvariantError("causal_engine must be a CausalRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._causal = causal_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        """Generate deterministic node IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        cause_id = stable_identifier("cn-causint", {"tenant": tenant_id, "source": source_type, "seq": seq, "role": "cause"})
        effect_id = stable_identifier("cn-causint", {"tenant": tenant_id, "source": source_type, "seq": seq, "role": "effect"})
        return cause_id, effect_id

    def _causal_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        cause_name: str = "",
        effect_name: str = "",
    ) -> dict[str, Any]:
        """Register a cause node and an effect node for a given source."""
        cause_id, effect_id = self._next_ids(tenant_id, source_type)

        cause_node = self._causal.register_causal_node(
            node_id=cause_id,
            tenant_id=tenant_id,
            display_name=cause_name or f"{source_type}_cause_{ref}",
        )
        effect_node = self._causal.register_causal_node(
            node_id=effect_id,
            tenant_id=tenant_id,
            display_name=effect_name or f"{source_type}_effect_{ref}",
        )

        edge_id = stable_identifier("ce-causint", {
            "tenant": tenant_id, "source": source_type, "seq": str(self._bridge_seq),
        })
        edge = self._causal.register_causal_edge(
            edge_id=edge_id,
            tenant_id=tenant_id,
            cause_ref=cause_id,
            effect_ref=effect_id,
        )

        _emit(self._events, f"causal_from_{source_type}", {
            "tenant_id": tenant_id,
            "cause_id": cause_id,
            "effect_id": effect_id,
            "edge_id": edge_id,
            "ref": ref,
        }, cause_id)

        return {
            "cause_id": cause_id,
            "effect_id": effect_id,
            "edge_id": edge_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
        }

    # ------------------------------------------------------------------
    # Surface-specific causal methods
    # ------------------------------------------------------------------

    def causal_from_remediation(
        self,
        tenant_id: str,
        remediation_ref: str,
        cause_name: str = "",
        effect_name: str = "",
    ) -> dict[str, Any]:
        """Register causal structure from a remediation source."""
        return self._causal_for_source(
            tenant_id=tenant_id,
            ref=remediation_ref,
            source_type="remediation",
            cause_name=cause_name,
            effect_name=effect_name,
        )

    def causal_from_continuity(
        self,
        tenant_id: str,
        continuity_ref: str,
        cause_name: str = "",
        effect_name: str = "",
    ) -> dict[str, Any]:
        """Register causal structure from a continuity source."""
        return self._causal_for_source(
            tenant_id=tenant_id,
            ref=continuity_ref,
            source_type="continuity",
            cause_name=cause_name,
            effect_name=effect_name,
        )

    def causal_from_forecasting(
        self,
        tenant_id: str,
        forecasting_ref: str,
        cause_name: str = "",
        effect_name: str = "",
    ) -> dict[str, Any]:
        """Register causal structure from a forecasting source."""
        return self._causal_for_source(
            tenant_id=tenant_id,
            ref=forecasting_ref,
            source_type="forecasting",
            cause_name=cause_name,
            effect_name=effect_name,
        )

    def causal_from_observability(
        self,
        tenant_id: str,
        observability_ref: str,
        cause_name: str = "",
        effect_name: str = "",
    ) -> dict[str, Any]:
        """Register causal structure from an observability source."""
        return self._causal_for_source(
            tenant_id=tenant_id,
            ref=observability_ref,
            source_type="observability",
            cause_name=cause_name,
            effect_name=effect_name,
        )

    def causal_from_executive_control(
        self,
        tenant_id: str,
        control_ref: str,
        cause_name: str = "",
        effect_name: str = "",
    ) -> dict[str, Any]:
        """Register causal structure from an executive control source."""
        return self._causal_for_source(
            tenant_id=tenant_id,
            ref=control_ref,
            source_type="executive_control",
            cause_name=cause_name,
            effect_name=effect_name,
        )

    def causal_from_process_simulation(
        self,
        tenant_id: str,
        simulation_ref: str,
        cause_name: str = "",
        effect_name: str = "",
    ) -> dict[str, Any]:
        """Register causal structure from a process simulation source."""
        return self._causal_for_source(
            tenant_id=tenant_id,
            ref=simulation_ref,
            source_type="process_simulation",
            cause_name=cause_name,
            effect_name=effect_name,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_causal_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist causal state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-causrt", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_nodes": self._causal.node_count,
            "total_edges": self._causal.edge_count,
            "total_interventions": self._causal.intervention_count,
            "total_counterfactuals": self._causal.counterfactual_count,
            "total_attributions": self._causal.attribution_count,
            "total_propagations": self._causal.propagation_count,
            "total_violations": self._causal.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Causal state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("causal", "counterfactual", "attribution"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "causal_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_causal_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return causal state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_nodes": self._causal.node_count,
            "total_edges": self._causal.edge_count,
            "total_interventions": self._causal.intervention_count,
            "total_counterfactuals": self._causal.counterfactual_count,
            "total_attributions": self._causal.attribution_count,
            "total_propagations": self._causal.propagation_count,
            "total_violations": self._causal.violation_count,
        }
