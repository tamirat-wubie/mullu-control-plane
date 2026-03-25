"""Purpose: ontology runtime integration bridge.
Governance scope: composing ontology runtime with data quality, customer product,
    service catalog, knowledge query, research, and memory consolidation layers;
    memory mesh and operational graph attachment.
Dependencies: ontology_runtime engine, event_spine, memory_mesh,
    core invariants.
Invariants:
  - Every ontology creation emits events.
  - Ontology state is attached to memory mesh.
  - All returns are immutable.
"""

from __future__ import annotations

from typing import Any

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
from .ontology_runtime import OntologyRuntimeEngine


def _now_iso_from(engine: OntologyRuntimeEngine) -> str:
    return engine._now()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, clock_source: OntologyRuntimeEngine) -> EventRecord:
    now = clock_source._now()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-oint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class OntologyRuntimeIntegration:
    """Integration bridge for ontology runtime with platform layers."""

    def __init__(
        self,
        ontology_engine: OntologyRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(ontology_engine, OntologyRuntimeEngine):
            raise RuntimeCoreInvariantError(
                "ontology_engine must be an OntologyRuntimeEngine"
            )
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._ontology = ontology_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helper
    # ------------------------------------------------------------------

    def _bridge_ontology(
        self,
        tenant_id: str,
        source_type: str,
        ref_field_name: str,
        ref_field_value: str,
        action_name: str,
    ) -> dict[str, Any]:
        """Register a concept from a bridge source."""
        self._bridge_seq += 1
        concept_id = stable_identifier("ont-c", {
            "tenant": tenant_id, "src": source_type, "seq": str(self._bridge_seq),
        })

        from ..contracts.ontology_runtime import ConceptKind

        c = self._ontology.register_concept(
            concept_id=concept_id,
            tenant_id=tenant_id,
            display_name=f"{source_type}:{ref_field_value}",
            kind=ConceptKind.ENTITY,
            canonical_form=f"{source_type}:{ref_field_value}",
        )

        _emit(self._events, action_name, {
            "concept_id": concept_id,
            ref_field_name: ref_field_value,
            "source_type": source_type,
        }, concept_id, self._ontology)

        return {
            "concept_id": c.concept_id,
            "tenant_id": tenant_id,
            ref_field_name: ref_field_value,
            "status": c.status.value,
            "kind": c.kind.value,
            "canonical_form": c.canonical_form,
            "source_type": source_type,
        }

    # ------------------------------------------------------------------
    # Bridge methods
    # ------------------------------------------------------------------

    def ontology_from_data_quality(
        self,
        tenant_id: str,
        quality_ref: str,
    ) -> dict[str, Any]:
        """Create ontology concept from a data quality event."""
        return self._bridge_ontology(
            tenant_id, "data_quality", "quality_ref", quality_ref,
            "ontology_from_data_quality",
        )

    def ontology_from_customer_product(
        self,
        tenant_id: str,
        product_ref: str,
    ) -> dict[str, Any]:
        """Create ontology concept from a customer product event."""
        return self._bridge_ontology(
            tenant_id, "customer_product", "product_ref", product_ref,
            "ontology_from_customer_product",
        )

    def ontology_from_service_catalog(
        self,
        tenant_id: str,
        service_ref: str,
    ) -> dict[str, Any]:
        """Create ontology concept from a service catalog event."""
        return self._bridge_ontology(
            tenant_id, "service_catalog", "service_ref", service_ref,
            "ontology_from_service_catalog",
        )

    def ontology_from_knowledge_query(
        self,
        tenant_id: str,
        query_ref: str,
    ) -> dict[str, Any]:
        """Create ontology concept from a knowledge query event."""
        return self._bridge_ontology(
            tenant_id, "knowledge_query", "query_ref", query_ref,
            "ontology_from_knowledge_query",
        )

    def ontology_from_research(
        self,
        tenant_id: str,
        research_ref: str,
    ) -> dict[str, Any]:
        """Create ontology concept from a research event."""
        return self._bridge_ontology(
            tenant_id, "research", "research_ref", research_ref,
            "ontology_from_research",
        )

    def ontology_from_memory_consolidation(
        self,
        tenant_id: str,
        consolidation_ref: str,
    ) -> dict[str, Any]:
        """Create ontology concept from a memory consolidation event."""
        return self._bridge_ontology(
            tenant_id, "memory_consolidation", "consolidation_ref", consolidation_ref,
            "ontology_from_memory_consolidation",
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_ontology_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist ontology state to memory mesh."""
        now = self._ontology._now()
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_concepts": self._ontology.concept_count,
            "total_relations": self._ontology.relation_count,
            "total_mappings": self._ontology.mapping_count,
            "total_alignments": self._ontology.alignment_count,
            "total_conflicts": self._ontology.conflict_count,
            "total_decisions": self._ontology.decision_count,
            "total_violations": self._ontology.violation_count,
        }

        mem = MemoryRecord(
            memory_id=stable_identifier("mem-ont", {
                "scope": scope_ref_id,
                "seq": str(self._memory.memory_count),
            }),
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            scope_ref_id=scope_ref_id,
            trust_level=MemoryTrustLevel.VERIFIED,
            title=f"Ontology state: {scope_ref_id}",
            content=content,
            source_ids=(scope_ref_id,),
            tags=("ontology", "semantic", "alignment"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(mem)

        _emit(self._events, "ontology_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mem.memory_id,
        }, scope_ref_id, self._ontology)
        return mem

    def attach_ontology_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return ontology state suitable for operational graph."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_concepts": self._ontology.concept_count,
            "total_relations": self._ontology.relation_count,
            "total_mappings": self._ontology.mapping_count,
            "total_alignments": self._ontology.alignment_count,
            "total_conflicts": self._ontology.conflict_count,
            "total_decisions": self._ontology.decision_count,
            "total_violations": self._ontology.violation_count,
        }
