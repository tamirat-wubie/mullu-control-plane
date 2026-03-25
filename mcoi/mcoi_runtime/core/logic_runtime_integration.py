"""Purpose: logic runtime integration bridge.
Governance scope: composing logic runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create logic bindings
    from various platform surface sources.
Dependencies: logic_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every logic operation emits events.
  - Logic state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.logic_runtime import (
    LogicalStatus,
    StatementKind,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .logic_runtime import LogicRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-logint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class LogicRuntimeIntegration:
    """Integration bridge for logic runtime with platform layers."""

    def __init__(
        self,
        logic_engine: LogicRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(logic_engine, LogicRuntimeEngine):
            raise RuntimeCoreInvariantError("logic_engine must be a LogicRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._logic = logic_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        """Generate deterministic statement and rule IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        stmt_id = stable_identifier("stmt-logint", {"tenant": tenant_id, "source": source_type, "seq": seq})
        rule_id = stable_identifier("rule-logint", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return stmt_id, rule_id

    def _logic_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        content: str = "default_assertion",
        kind: StatementKind = StatementKind.FACT,
    ) -> dict[str, Any]:
        """Register a statement for a given source."""
        stmt_id, rule_id = self._next_ids(tenant_id, source_type)

        stmt = self._logic.register_statement(
            statement_id=stmt_id,
            tenant_id=tenant_id,
            kind=kind,
            content=content or f"{source_type}_{ref}",
        )

        _emit(self._events, f"logic_from_{source_type}", {
            "tenant_id": tenant_id,
            "statement_id": stmt_id,
            "ref": ref,
        }, stmt_id)

        return {
            "statement_id": stmt_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "kind": kind.value,
        }

    # ------------------------------------------------------------------
    # Surface-specific logic methods
    # ------------------------------------------------------------------

    def logic_from_governance(
        self,
        tenant_id: str,
        governance_ref: str,
        content: str = "governance_assertion",
        source_type: str = "governance",
    ) -> dict[str, Any]:
        """Register logic from a governance source."""
        return self._logic_for_source(
            tenant_id=tenant_id,
            ref=governance_ref,
            source_type=source_type,
            content=content,
            kind=StatementKind.AXIOM,
        )

    def logic_from_assurance(
        self,
        tenant_id: str,
        assurance_ref: str,
        content: str = "assurance_assertion",
    ) -> dict[str, Any]:
        """Register logic from an assurance source."""
        return self._logic_for_source(
            tenant_id=tenant_id,
            ref=assurance_ref,
            source_type="assurance",
            content=content,
            kind=StatementKind.FACT,
        )

    def logic_from_research(
        self,
        tenant_id: str,
        research_ref: str,
        content: str = "research_hypothesis",
    ) -> dict[str, Any]:
        """Register logic from a research source."""
        return self._logic_for_source(
            tenant_id=tenant_id,
            ref=research_ref,
            source_type="research",
            content=content,
            kind=StatementKind.ASSUMPTION,
        )

    def logic_from_policy_simulation(
        self,
        tenant_id: str,
        simulation_ref: str,
        content: str = "simulation_conclusion",
    ) -> dict[str, Any]:
        """Register logic from a policy simulation source."""
        return self._logic_for_source(
            tenant_id=tenant_id,
            ref=simulation_ref,
            source_type="policy_simulation",
            content=content,
            kind=StatementKind.CONCLUSION,
        )

    def logic_from_self_tuning(
        self,
        tenant_id: str,
        tuning_ref: str,
        content: str = "tuning_rule",
    ) -> dict[str, Any]:
        """Register logic from a self-tuning source."""
        return self._logic_for_source(
            tenant_id=tenant_id,
            ref=tuning_ref,
            source_type="self_tuning",
            content=content,
            kind=StatementKind.RULE,
        )

    def logic_from_copilot(
        self,
        tenant_id: str,
        copilot_ref: str,
        content: str = "copilot_fact",
    ) -> dict[str, Any]:
        """Register logic from a copilot source."""
        return self._logic_for_source(
            tenant_id=tenant_id,
            ref=copilot_ref,
            source_type="copilot",
            content=content,
            kind=StatementKind.FACT,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_logic_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist logic state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-logrt", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_statements": self._logic.statement_count,
            "total_rules": self._logic.rule_count,
            "total_proofs": self._logic.proof_count,
            "total_assumptions": self._logic.assumption_count,
            "total_contradictions": self._logic.contradiction_count,
            "total_revisions": self._logic.revision_count,
            "total_violations": self._logic.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Logic state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("logic", "proof", "truth_maintenance"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "logic_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_logic_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return logic state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_statements": self._logic.statement_count,
            "total_rules": self._logic.rule_count,
            "total_proofs": self._logic.proof_count,
            "total_assumptions": self._logic.assumption_count,
            "total_contradictions": self._logic.contradiction_count,
            "total_revisions": self._logic.revision_count,
            "total_violations": self._logic.violation_count,
        }
