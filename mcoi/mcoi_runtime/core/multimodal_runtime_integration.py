"""Purpose: multimodal runtime integration bridge.
Governance scope: composing multimodal runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create multimodal sessions
    from various platform surface sources.
Dependencies: multimodal_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every multimodal operation emits events.
  - Multimodal state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.multimodal_runtime import (
    InteractionMode,
    SessionChannel,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .multimodal_runtime import MultimodalRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-mmint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class MultimodalRuntimeIntegration:
    """Integration bridge for multimodal runtime with platform layers."""

    def __init__(
        self,
        multimodal_engine: MultimodalRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(multimodal_engine, MultimodalRuntimeEngine):
            raise RuntimeCoreInvariantError("multimodal_engine must be a MultimodalRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._multimodal = multimodal_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_session_id(self, tenant_id: str, source_type: str) -> str:
        """Generate deterministic session ID from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        return stable_identifier("sess-mmrt", {"tenant": tenant_id, "source": source_type, "seq": seq})

    def _multimodal_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        session_id: str,
        identity_ref: str,
        copilot_ref: str,
        mode: InteractionMode,
        channel: SessionChannel,
    ) -> dict[str, Any]:
        """Start a voice session for a given source."""
        if not session_id:
            session_id = self._next_session_id(tenant_id, source_type)
        else:
            self._bridge_seq += 1

        session = self._multimodal.start_voice_session(
            session_id=session_id,
            tenant_id=tenant_id,
            identity_ref=identity_ref,
            copilot_session_ref=copilot_ref,
            mode=mode,
            channel=channel,
        )

        _emit(self._events, f"multimodal_from_{source_type}", {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "ref": ref,
        }, session_id)

        return {
            "session_id": session_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "mode": session.mode.value,
            "channel": session.channel.value,
            "status": session.status,
            "identity_ref": identity_ref,
            "copilot_session_ref": copilot_ref,
        }

    # ------------------------------------------------------------------
    # Surface-specific multimodal methods
    # ------------------------------------------------------------------

    def multimodal_from_copilot_session(
        self,
        tenant_id: str,
        copilot_ref: str,
        session_id: str = "",
        identity_ref: str = "copilot_user",
        mode: InteractionMode = InteractionMode.VOICE,
        channel: SessionChannel = SessionChannel.WEB,
    ) -> dict[str, Any]:
        """Start multimodal session from a copilot session."""
        return self._multimodal_for_source(
            tenant_id=tenant_id,
            ref=copilot_ref,
            source_type="copilot_session",
            session_id=session_id,
            identity_ref=identity_ref,
            copilot_ref=copilot_ref,
            mode=mode,
            channel=channel,
        )

    def multimodal_from_operator_workspace(
        self,
        tenant_id: str,
        workspace_ref: str,
        session_id: str = "",
        identity_ref: str = "operator",
        mode: InteractionMode = InteractionMode.HYBRID,
        channel: SessionChannel = SessionChannel.WEB,
    ) -> dict[str, Any]:
        """Start multimodal session from an operator workspace."""
        return self._multimodal_for_source(
            tenant_id=tenant_id,
            ref=workspace_ref,
            source_type="operator_workspace",
            session_id=session_id,
            identity_ref=identity_ref,
            copilot_ref=workspace_ref,
            mode=mode,
            channel=channel,
        )

    def multimodal_from_product_console(
        self,
        tenant_id: str,
        console_ref: str,
        session_id: str = "",
        identity_ref: str = "product_user",
        mode: InteractionMode = InteractionMode.TEXT,
        channel: SessionChannel = SessionChannel.WEB,
    ) -> dict[str, Any]:
        """Start multimodal session from a product console."""
        return self._multimodal_for_source(
            tenant_id=tenant_id,
            ref=console_ref,
            source_type="product_console",
            session_id=session_id,
            identity_ref=identity_ref,
            copilot_ref=console_ref,
            mode=mode,
            channel=channel,
        )

    def multimodal_from_communication_surface(
        self,
        tenant_id: str,
        comm_ref: str,
        session_id: str = "",
        identity_ref: str = "caller",
        mode: InteractionMode = InteractionMode.VOICE,
        channel: SessionChannel = SessionChannel.PHONE,
    ) -> dict[str, Any]:
        """Start multimodal session from a communication surface."""
        return self._multimodal_for_source(
            tenant_id=tenant_id,
            ref=comm_ref,
            source_type="communication_surface",
            session_id=session_id,
            identity_ref=identity_ref,
            copilot_ref=comm_ref,
            mode=mode,
            channel=channel,
        )

    def multimodal_from_service_request(
        self,
        tenant_id: str,
        service_ref: str,
        session_id: str = "",
        identity_ref: str = "service_agent",
        mode: InteractionMode = InteractionMode.HYBRID,
        channel: SessionChannel = SessionChannel.CHAT,
    ) -> dict[str, Any]:
        """Start multimodal session from a service request."""
        return self._multimodal_for_source(
            tenant_id=tenant_id,
            ref=service_ref,
            source_type="service_request",
            session_id=session_id,
            identity_ref=identity_ref,
            copilot_ref=service_ref,
            mode=mode,
            channel=channel,
        )

    def multimodal_from_executive_control(
        self,
        tenant_id: str,
        directive_ref: str,
        session_id: str = "",
        identity_ref: str = "executive",
        mode: InteractionMode = InteractionMode.STREAMING,
        channel: SessionChannel = SessionChannel.API,
    ) -> dict[str, Any]:
        """Start multimodal session from executive control."""
        return self._multimodal_for_source(
            tenant_id=tenant_id,
            ref=directive_ref,
            source_type="executive_control",
            session_id=session_id,
            identity_ref=identity_ref,
            copilot_ref=directive_ref,
            mode=mode,
            channel=channel,
        )

    # ------------------------------------------------------------------
    # Persona-aware multimodal
    # ------------------------------------------------------------------

    def multimodal_with_persona(
        self,
        tenant_id: str,
        session_id: str,
        copilot_ref: str,
        persona_ref: str,
        channel: str = "web",
    ) -> dict[str, Any]:
        """Start a multimodal session with persona and copilot linkage."""
        if not session_id:
            session_id = self._next_session_id(tenant_id, "persona_linked")
        else:
            self._bridge_seq += 1

        chan = SessionChannel(channel) if channel in {c.value for c in SessionChannel} else SessionChannel.WEB

        session = self._multimodal.start_voice_session(
            session_id=session_id,
            tenant_id=tenant_id,
            identity_ref=persona_ref,
            copilot_session_ref=copilot_ref,
            mode=InteractionMode.HYBRID,
            channel=chan,
        )

        _emit(self._events, "multimodal_with_persona", {
            "tenant_id": tenant_id,
            "session_id": session_id,
            "copilot_ref": copilot_ref,
            "persona_ref": persona_ref,
            "channel": channel,
        }, session_id)

        return {
            "session_id": session_id,
            "tenant_id": tenant_id,
            "copilot_ref": copilot_ref,
            "persona_ref": persona_ref,
            "source_type": "persona_linked",
            "channel": session.channel.value,
            "mode": session.mode.value,
            "status": session.status,
        }

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_multimodal_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist multimodal state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-mmrt", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_sessions": self._multimodal.session_count,
            "total_turns": self._multimodal.turn_count,
            "total_transcripts": self._multimodal.transcript_count,
            "total_presence": self._multimodal.presence_count,
            "total_interruptions": self._multimodal.interruption_count,
            "total_plans": self._multimodal.plan_count,
            "total_decisions": self._multimodal.decision_count,
            "total_violations": self._multimodal.violation_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Multimodal state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("multimodal", "voice", "presence"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "multimodal_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_multimodal_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return multimodal state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_sessions": self._multimodal.session_count,
            "total_turns": self._multimodal.turn_count,
            "total_transcripts": self._multimodal.transcript_count,
            "total_presence": self._multimodal.presence_count,
            "total_interruptions": self._multimodal.interruption_count,
            "total_plans": self._multimodal.plan_count,
            "total_decisions": self._multimodal.decision_count,
            "total_violations": self._multimodal.violation_count,
        }
