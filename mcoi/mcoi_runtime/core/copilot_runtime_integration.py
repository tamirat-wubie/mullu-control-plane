"""Purpose: copilot runtime integration bridge.
Governance scope: composing copilot runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create copilot sessions
    from various platform surface sources.
Dependencies: copilot_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every copilot operation emits events.
  - Copilot state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.copilot_runtime import (
    ConversationMode,
    IntentKind,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .copilot_runtime import CopilotRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-cpint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class CopilotRuntimeIntegration:
    """Integration bridge for copilot runtime with platform layers."""

    def __init__(
        self,
        copilot_engine: CopilotRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(copilot_engine, CopilotRuntimeEngine):
            raise RuntimeCoreInvariantError("copilot_engine must be a CopilotRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._copilot = copilot_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        """Generate deterministic session and intent IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        session_id = stable_identifier("sess-cprt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        intent_id = stable_identifier("int-cprt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return session_id, intent_id

    def _copilot_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        session_id: str,
        identity_ref: str,
        mode: ConversationMode,
        intent_kind: IntentKind,
        raw_input: str,
    ) -> dict[str, Any]:
        """Start a session and classify intent for a given source."""
        # Use provided session_id or generate one
        if not session_id:
            session_id, intent_id = self._next_ids(tenant_id, source_type)
        else:
            self._bridge_seq += 1
            seq = str(self._bridge_seq)
            intent_id = stable_identifier("int-cprt", {"tenant": tenant_id, "source": source_type, "seq": seq})

        session = self._copilot.start_session(
            session_id=session_id,
            tenant_id=tenant_id,
            identity_ref=identity_ref,
            mode=mode,
        )
        intent = self._copilot.classify_intent(
            intent_id=intent_id,
            tenant_id=tenant_id,
            session_ref=session_id,
            kind=intent_kind,
            raw_input=raw_input,
        )

        _emit(self._events, f"copilot_from_{source_type}", {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "intent_id": intent_id,
            "ref": ref,
        }, session_id)

        return {
            "session_id": session_id,
            "intent_id": intent_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "mode": session.mode.value,
            "status": session.status.value,
            "intent_kind": intent.kind.value,
            "raw_input": raw_input,
        }

    # ------------------------------------------------------------------
    # Surface-specific copilot methods
    # ------------------------------------------------------------------

    def copilot_for_operator_workspace(
        self,
        tenant_id: str,
        workspace_ref: str,
        session_id: str = "",
        identity_ref: str = "operator",
        mode: ConversationMode = ConversationMode.INTERACTIVE,
        intent_kind: IntentKind = IntentKind.QUERY,
        raw_input: str = "Operator workspace query",
    ) -> dict[str, Any]:
        """Start copilot for an operator workspace."""
        return self._copilot_for_source(
            tenant_id=tenant_id,
            ref=workspace_ref,
            source_type="operator_workspace",
            session_id=session_id,
            identity_ref=identity_ref,
            mode=mode,
            intent_kind=intent_kind,
            raw_input=raw_input,
        )

    def copilot_for_product_console(
        self,
        tenant_id: str,
        console_ref: str,
        session_id: str = "",
        identity_ref: str = "product_user",
        mode: ConversationMode = ConversationMode.GUIDED,
        intent_kind: IntentKind = IntentKind.EXPLAIN,
        raw_input: str = "Product console query",
    ) -> dict[str, Any]:
        """Start copilot for a product console."""
        return self._copilot_for_source(
            tenant_id=tenant_id,
            ref=console_ref,
            source_type="product_console",
            session_id=session_id,
            identity_ref=identity_ref,
            mode=mode,
            intent_kind=intent_kind,
            raw_input=raw_input,
        )

    def copilot_for_service_request(
        self,
        tenant_id: str,
        service_ref: str,
        session_id: str = "",
        identity_ref: str = "service_agent",
        mode: ConversationMode = ConversationMode.INTERACTIVE,
        intent_kind: IntentKind = IntentKind.ACTION,
        raw_input: str = "Service request query",
    ) -> dict[str, Any]:
        """Start copilot for a service request."""
        return self._copilot_for_source(
            tenant_id=tenant_id,
            ref=service_ref,
            source_type="service_request",
            session_id=session_id,
            identity_ref=identity_ref,
            mode=mode,
            intent_kind=intent_kind,
            raw_input=raw_input,
        )

    def copilot_for_case_and_remediation(
        self,
        tenant_id: str,
        case_ref: str,
        session_id: str = "",
        identity_ref: str = "case_manager",
        mode: ConversationMode = ConversationMode.GUIDED,
        intent_kind: IntentKind = IntentKind.SUMMARIZE,
        raw_input: str = "Case remediation query",
    ) -> dict[str, Any]:
        """Start copilot for case and remediation."""
        return self._copilot_for_source(
            tenant_id=tenant_id,
            ref=case_ref,
            source_type="case_remediation",
            session_id=session_id,
            identity_ref=identity_ref,
            mode=mode,
            intent_kind=intent_kind,
            raw_input=raw_input,
        )

    def copilot_for_customer_account(
        self,
        tenant_id: str,
        customer_ref: str,
        session_id: str = "",
        identity_ref: str = "customer",
        mode: ConversationMode = ConversationMode.INTERACTIVE,
        intent_kind: IntentKind = IntentKind.QUERY,
        raw_input: str = "Customer account query",
    ) -> dict[str, Any]:
        """Start copilot for a customer account."""
        return self._copilot_for_source(
            tenant_id=tenant_id,
            ref=customer_ref,
            source_type="customer_account",
            session_id=session_id,
            identity_ref=identity_ref,
            mode=mode,
            intent_kind=intent_kind,
            raw_input=raw_input,
        )

    def copilot_for_executive_control(
        self,
        tenant_id: str,
        directive_ref: str,
        session_id: str = "",
        identity_ref: str = "executive",
        mode: ConversationMode = ConversationMode.AUTONOMOUS,
        intent_kind: IntentKind = IntentKind.ESCALATE,
        raw_input: str = "Executive control directive",
    ) -> dict[str, Any]:
        """Start copilot for executive control."""
        return self._copilot_for_source(
            tenant_id=tenant_id,
            ref=directive_ref,
            source_type="executive_control",
            session_id=session_id,
            identity_ref=identity_ref,
            mode=mode,
            intent_kind=intent_kind,
            raw_input=raw_input,
        )

    # ------------------------------------------------------------------
    # Persona-aware copilot
    # ------------------------------------------------------------------

    def copilot_with_persona(
        self,
        tenant_id: str,
        session_id: str,
        persona_ref: str,
        workspace_ref: str = "",
    ) -> dict[str, Any]:
        """Start a copilot session with persona-aware behavior."""
        if not session_id:
            session_id, _ = self._next_ids(tenant_id, "persona_aware")
        else:
            self._bridge_seq += 1

        session = self._copilot.start_session(
            session_id=session_id,
            tenant_id=tenant_id,
            identity_ref=persona_ref,
            mode=ConversationMode.INTERACTIVE,
        )

        _emit(self._events, "copilot_with_persona", {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "persona_ref": persona_ref,
            "workspace_ref": workspace_ref,
        }, session_id)

        return {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "persona_ref": persona_ref,
            "workspace_ref": workspace_ref,
            "source_type": "persona_aware",
            "status": session.status.value,
            "mode": session.mode.value,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_copilot_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist copilot state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-cprt", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_sessions": self._copilot.session_count,
            "total_turns": self._copilot.turn_count,
            "total_intents": self._copilot.intent_count,
            "total_plans": self._copilot.plan_count,
            "total_decisions": self._copilot.decision_count,
            "total_responses": self._copilot.response_count,
            "total_violations": self._copilot.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title="Copilot state",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("copilot", "conversation", "assistant"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "copilot_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_copilot_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return copilot state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_sessions": self._copilot.session_count,
            "total_turns": self._copilot.turn_count,
            "total_intents": self._copilot.intent_count,
            "total_plans": self._copilot.plan_count,
            "total_decisions": self._copilot.decision_count,
            "total_responses": self._copilot.response_count,
            "total_violations": self._copilot.violation_count,
        }
