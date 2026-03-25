"""Purpose: epistemic runtime integration bridge.
Governance scope: composing epistemic runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create epistemic bindings
    from various platform surface sources (logic, causal, uncertainty, temporal,
    ontology, research).
Dependencies: epistemic_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every epistemic operation emits events.
  - Epistemic state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.epistemic_runtime import (
    AssertionMode,
    KnowledgeStatus,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .epistemic_runtime import EpistemicRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-epint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class EpistemicRuntimeIntegration:
    """Integration bridge for epistemic runtime with platform layers."""

    def __init__(
        self,
        epistemic_engine: EpistemicRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(epistemic_engine, EpistemicRuntimeEngine):
            raise RuntimeCoreInvariantError("epistemic_engine must be an EpistemicRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._epistemic = epistemic_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        """Generate deterministic claim and source IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        claim_id = stable_identifier("claim-epint", {"tenant": tenant_id, "source": source_type, "seq": seq})
        source_id = stable_identifier("src-epint", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return claim_id, source_id

    def _epistemic_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        status: KnowledgeStatus = KnowledgeStatus.REPORTED,
        assertion_mode: AssertionMode = AssertionMode.FACTUAL,
        confidence: float = 0.5,
    ) -> dict[str, Any]:
        """Register a claim for a given source."""
        claim_id, _ = self._next_ids(tenant_id, source_type)

        claim = self._epistemic.register_claim(
            claim_id=claim_id,
            tenant_id=tenant_id,
            content=f"{source_type}_{ref}",
            status=status,
            assertion_mode=assertion_mode,
            source_ref=ref,
            confidence=confidence,
        )

        _emit(self._events, f"epistemic_from_{source_type}", {
            "tenant_id": tenant_id,
            "claim_id": claim_id,
            "ref": ref,
        }, claim_id)

        return {
            "claim_id": claim_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "status": claim.status.value,
            "trust_level": claim.trust_level.value,
        }

    # ------------------------------------------------------------------
    # Surface-specific epistemic methods
    # ------------------------------------------------------------------

    def epistemic_from_logic(
        self,
        tenant_id: str,
        logic_ref: str,
        content: str = "logic_proven_claim",
    ) -> dict[str, Any]:
        """Register epistemic claim from a logic source (PROVEN)."""
        return self._epistemic_for_source(
            tenant_id=tenant_id,
            ref=logic_ref,
            source_type="logic",
            status=KnowledgeStatus.PROVEN,
            assertion_mode=AssertionMode.FACTUAL,
            confidence=0.9,
        )

    def epistemic_from_causal(
        self,
        tenant_id: str,
        causal_ref: str,
        content: str = "causal_inferred_claim",
    ) -> dict[str, Any]:
        """Register epistemic claim from a causal source (INFERRED)."""
        return self._epistemic_for_source(
            tenant_id=tenant_id,
            ref=causal_ref,
            source_type="causal",
            status=KnowledgeStatus.INFERRED,
            assertion_mode=AssertionMode.CONDITIONAL,
            confidence=0.7,
        )

    def epistemic_from_uncertainty(
        self,
        tenant_id: str,
        belief_ref: str,
        confidence: float = 0.5,
        content: str = "uncertainty_belief_claim",
    ) -> dict[str, Any]:
        """Register epistemic claim from an uncertainty source (REPORTED with belief confidence)."""
        return self._epistemic_for_source(
            tenant_id=tenant_id,
            ref=belief_ref,
            source_type="uncertainty",
            status=KnowledgeStatus.REPORTED,
            assertion_mode=AssertionMode.HYPOTHETICAL,
            confidence=confidence,
        )

    def epistemic_from_temporal(
        self,
        tenant_id: str,
        temporal_ref: str,
        content: str = "temporal_observed_claim",
    ) -> dict[str, Any]:
        """Register epistemic claim from a temporal source (OBSERVED)."""
        return self._epistemic_for_source(
            tenant_id=tenant_id,
            ref=temporal_ref,
            source_type="temporal",
            status=KnowledgeStatus.OBSERVED,
            assertion_mode=AssertionMode.FACTUAL,
            confidence=0.8,
        )

    def epistemic_from_ontology(
        self,
        tenant_id: str,
        concept_ref: str,
        content: str = "ontology_concept_claim",
    ) -> dict[str, Any]:
        """Register epistemic claim from an ontology source (REPORTED)."""
        return self._epistemic_for_source(
            tenant_id=tenant_id,
            ref=concept_ref,
            source_type="ontology",
            status=KnowledgeStatus.REPORTED,
            assertion_mode=AssertionMode.FACTUAL,
            confidence=0.6,
        )

    def epistemic_from_research(
        self,
        tenant_id: str,
        research_ref: str,
        evidence_strength: float = 0.5,
        content: str = "research_claim",
    ) -> dict[str, Any]:
        """Register epistemic claim from a research source.

        Status is derived from evidence_strength:
          >= 0.8 → PROVEN
          >= 0.5 → INFERRED
          else → REPORTED
        """
        if evidence_strength >= 0.8:
            status = KnowledgeStatus.PROVEN
        elif evidence_strength >= 0.5:
            status = KnowledgeStatus.INFERRED
        else:
            status = KnowledgeStatus.REPORTED

        return self._epistemic_for_source(
            tenant_id=tenant_id,
            ref=research_ref,
            source_type="research",
            status=status,
            assertion_mode=AssertionMode.FACTUAL,
            confidence=evidence_strength,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_epistemic_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist epistemic state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-eprt", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_claims": self._epistemic.claim_count,
            "total_sources": self._epistemic.source_count,
            "total_assessments": self._epistemic.assessment_count,
            "total_conflicts": self._epistemic.conflict_count,
            "total_reliability_updates": self._epistemic.reliability_update_count,
            "total_violations": self._epistemic.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Epistemic state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("epistemic", "trust", "knowledge"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "epistemic_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_epistemic_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return epistemic state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_claims": self._epistemic.claim_count,
            "total_sources": self._epistemic.source_count,
            "total_assessments": self._epistemic.assessment_count,
            "total_conflicts": self._epistemic.conflict_count,
            "total_reliability_updates": self._epistemic.reliability_update_count,
            "total_violations": self._epistemic.violation_count,
        }
