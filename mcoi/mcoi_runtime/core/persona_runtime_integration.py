"""Purpose: persona runtime integration bridge.
Governance scope: composing persona runtime engine with event spine, memory mesh,
    and operational graph. Provides convenience methods to create persona bindings
    from various platform surface sources.
Dependencies: persona_runtime engine, event_spine, memory_mesh, core invariants.
Invariants:
  - Every persona operation emits events.
  - Persona state is attached to memory mesh.
  - All returns are immutable dicts or MemoryRecord instances.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..contracts.persona_runtime import (
    AuthorityMode,
    InteractionStyle,
    PersonaKind,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .persona_runtime import PersonaRuntimeEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str) -> EventRecord:
    now = _now_iso()
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-psint", {"action": action, "ts": now, "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class PersonaRuntimeIntegration:
    """Integration bridge for persona runtime with platform layers."""

    def __init__(
        self,
        persona_engine: PersonaRuntimeEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(persona_engine, PersonaRuntimeEngine):
            raise RuntimeCoreInvariantError("persona_engine must be a PersonaRuntimeEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._persona = persona_engine
        self._events = event_spine
        self._memory = memory_engine
        self._bridge_seq = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _next_ids(self, tenant_id: str, source_type: str) -> tuple[str, str]:
        """Generate deterministic persona and binding IDs from seq."""
        self._bridge_seq += 1
        seq = str(self._bridge_seq)
        persona_id = stable_identifier("prs-psrt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        binding_id = stable_identifier("bnd-psrt", {"tenant": tenant_id, "source": source_type, "seq": seq})
        return persona_id, binding_id

    def _persona_for_source(
        self,
        tenant_id: str,
        ref: str,
        source_type: str,
        persona_id: str,
        session_ref: str,
        kind: PersonaKind,
        interaction_style: InteractionStyle = InteractionStyle.CONCISE,
        authority_mode: AuthorityMode = AuthorityMode.GUIDED,
    ) -> dict[str, Any]:
        """Register a persona and bind to session for a given source."""
        if not persona_id:
            persona_id, binding_id = self._next_ids(tenant_id, source_type)
        else:
            self._bridge_seq += 1
            seq = str(self._bridge_seq)
            binding_id = stable_identifier("bnd-psrt", {"tenant": tenant_id, "source": source_type, "seq": seq})

        persona = self._persona.register_persona(
            persona_id=persona_id,
            tenant_id=tenant_id,
            display_name=f"{kind.value}_{source_type}",
            kind=kind,
            interaction_style=interaction_style,
            authority_mode=authority_mode,
        )
        binding = self._persona.bind_persona_to_session(
            binding_id=binding_id,
            tenant_id=tenant_id,
            persona_ref=persona_id,
            session_ref=session_ref,
        )

        _emit(self._events, f"persona_from_{source_type}", {
            "tenant_id": tenant_id,
            "persona_id": persona_id,
            "binding_id": binding_id,
            "ref": ref,
        }, persona_id)

        return {
            "persona_id": persona_id,
            "binding_id": binding_id,
            "source_type": source_type,
            "tenant_id": tenant_id,
            "kind": persona.kind.value,
            "status": persona.status.value,
            "interaction_style": persona.interaction_style.value,
            "authority_mode": persona.authority_mode.value,
        }

    # ------------------------------------------------------------------
    # Surface-specific persona methods
    # ------------------------------------------------------------------

    def persona_for_operator_workspace(
        self,
        tenant_id: str,
        workspace_ref: str,
        persona_id: str = "",
        session_ref: str = "",
    ) -> dict[str, Any]:
        """Register OPERATOR persona and bind to session for operator workspace."""
        return self._persona_for_source(
            tenant_id=tenant_id,
            ref=workspace_ref,
            source_type="operator_workspace",
            persona_id=persona_id,
            session_ref=session_ref or workspace_ref,
            kind=PersonaKind.OPERATOR,
        )

    def persona_for_product_console(
        self,
        tenant_id: str,
        console_ref: str,
        persona_id: str = "",
        session_ref: str = "",
    ) -> dict[str, Any]:
        """Register TECHNICAL persona and bind to session for product console."""
        return self._persona_for_source(
            tenant_id=tenant_id,
            ref=console_ref,
            source_type="product_console",
            persona_id=persona_id,
            session_ref=session_ref or console_ref,
            kind=PersonaKind.TECHNICAL,
        )

    def persona_for_executive_control(
        self,
        tenant_id: str,
        directive_ref: str,
        persona_id: str = "",
        session_ref: str = "",
    ) -> dict[str, Any]:
        """Register EXECUTIVE persona and bind to session for executive control."""
        return self._persona_for_source(
            tenant_id=tenant_id,
            ref=directive_ref,
            source_type="executive_control",
            persona_id=persona_id,
            session_ref=session_ref or directive_ref,
            kind=PersonaKind.EXECUTIVE,
            authority_mode=AuthorityMode.AUTONOMOUS,
        )

    def persona_for_customer_support(
        self,
        tenant_id: str,
        customer_ref: str,
        persona_id: str = "",
        session_ref: str = "",
    ) -> dict[str, Any]:
        """Register CUSTOMER_SUPPORT persona and bind to session."""
        return self._persona_for_source(
            tenant_id=tenant_id,
            ref=customer_ref,
            source_type="customer_support",
            persona_id=persona_id,
            session_ref=session_ref or customer_ref,
            kind=PersonaKind.CUSTOMER_SUPPORT,
            interaction_style=InteractionStyle.CONVERSATIONAL,
        )

    def persona_for_regulatory_response(
        self,
        tenant_id: str,
        regulatory_ref: str,
        persona_id: str = "",
        session_ref: str = "",
    ) -> dict[str, Any]:
        """Register REGULATORY persona and bind to session."""
        return self._persona_for_source(
            tenant_id=tenant_id,
            ref=regulatory_ref,
            source_type="regulatory_response",
            persona_id=persona_id,
            session_ref=session_ref or regulatory_ref,
            kind=PersonaKind.REGULATORY,
            interaction_style=InteractionStyle.FORMAL,
            authority_mode=AuthorityMode.RESTRICTED,
        )

    def persona_for_multimodal_session(
        self,
        tenant_id: str,
        multimodal_ref: str,
        persona_id: str = "",
        session_ref: str = "",
    ) -> dict[str, Any]:
        """Register OPERATOR (default) persona for multimodal session."""
        return self._persona_for_source(
            tenant_id=tenant_id,
            ref=multimodal_ref,
            source_type="multimodal_session",
            persona_id=persona_id,
            session_ref=session_ref or multimodal_ref,
            kind=PersonaKind.OPERATOR,
        )

    # ------------------------------------------------------------------
    # Memory mesh and graph attachment
    # ------------------------------------------------------------------

    def attach_persona_state_to_memory_mesh(
        self,
        scope_ref_id: str,
    ) -> MemoryRecord:
        """Persist persona state to memory mesh."""
        now = _now_iso()
        mid = stable_identifier("mem-psrt", {
            "scope": scope_ref_id,
            "seq": str(self._memory.memory_count),
        })
        content: dict[str, Any] = {
            "scope_ref_id": scope_ref_id,
            "total_personas": self._persona.persona_count,
            "total_policies": self._persona.policy_count,
            "total_bindings": self._persona.binding_count,
            "total_decisions": self._persona.decision_count,
            "total_violations": self._persona.violation_count,
            "total_style_directives": self._persona.style_directive_count,
            "total_escalation_directives": self._persona.escalation_directive_count,
        }
        record = MemoryRecord(
            memory_id=mid,
            scope_ref_id=scope_ref_id,
            title=f"Persona state for {scope_ref_id}",
            memory_type=MemoryType.OBSERVATION,
            scope=MemoryScope.GLOBAL,
            trust_level=MemoryTrustLevel.VERIFIED,
            content=content,
            source_ids=(scope_ref_id,),
            tags=("persona", "behavior", "role"),
            confidence=1.0,
            created_at=now,
            updated_at=now,
        )
        self._memory.add_memory(record)
        _emit(self._events, "persona_state_attached_to_memory", {
            "scope_ref_id": scope_ref_id,
            "memory_id": mid,
        }, scope_ref_id)
        return record

    def attach_persona_state_to_graph(
        self,
        scope_ref_id: str,
    ) -> dict[str, Any]:
        """Return persona state suitable for operational graph consumption."""
        return {
            "scope_ref_id": scope_ref_id,
            "total_personas": self._persona.persona_count,
            "total_policies": self._persona.policy_count,
            "total_bindings": self._persona.binding_count,
            "total_decisions": self._persona.decision_count,
            "total_violations": self._persona.violation_count,
            "total_style_directives": self._persona.style_directive_count,
            "total_escalation_directives": self._persona.escalation_directive_count,
        }
