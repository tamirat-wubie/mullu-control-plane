"""Purpose: bridge between contact/identity graph and domain engines.
Governance scope: identity registration from org/team/operator sources,
    message/escalation/notification routing, identity resolution from
    communication, memory mesh attachment, operational graph attachment.
Dependencies: ContactIdentityEngine, CommunicationSurfaceEngine,
    EventSpineEngine, MemoryMeshEngine, ObligationRuntimeEngine,
    OperationalGraph, OrgDirectory, core invariants.
Invariants:
  - Registration methods produce IdentityRecords + ChannelHandles.
  - Routing methods produce immutable IdentityRoutingDecisions.
  - Memory and graph attachments are explicit, never silent.
  - All IDs are deterministic via stable_identifier.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.contact_identity import (
    AvailabilityState,
    AvailabilityWindow,
    ChannelHandle,
    ChannelPreferenceLevel,
    ContactPreferenceRecord,
    EscalationChainRecord,
    EscalationMode,
    IdentityLink,
    IdentityRecord,
    IdentityResolutionRecord,
    IdentityRoutingDecision,
    IdentityType,
)
from ..contracts.communication_surface import ChannelType
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import (
    MemoryRecord,
    MemoryScope,
    MemoryTrustLevel,
    MemoryType,
)
from .contact_identity import ContactIdentityEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .memory_mesh_integration import MemoryMeshIntegration


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ContactIdentityIntegration:
    """Bridge connecting contact/identity graph to event spine,
    memory mesh, and operational graph.
    """

    def __init__(
        self,
        identity_engine: ContactIdentityEngine,
        event_spine: EventSpineEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(identity_engine, ContactIdentityEngine):
            raise RuntimeCoreInvariantError("identity_engine must be a ContactIdentityEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._identities = identity_engine
        self._events = event_spine
        self._memory_engine = memory_engine
        self._memory = MemoryMeshIntegration(memory_engine)

    # ------------------------------------------------------------------
    # Registration from org directory
    # ------------------------------------------------------------------

    def register_from_org_directory(
        self,
        person_id: str,
        name: str,
        email: str,
        organization_id: str = "",
        *,
        roles: tuple[str, ...] = (),
        tags: tuple[str, ...] = (),
    ) -> dict[str, Any]:
        """Register a person from org directory as an identity with email handle."""
        now = _now_iso()

        identity = IdentityRecord(
            identity_id=stable_identifier("id-org", {"pid": person_id}),
            identity_type=IdentityType.PERSON,
            display_name=name,
            organization_id=organization_id,
            role_ids=roles,
            tags=("org_directory",) + tags,
            created_at=now,
            updated_at=now,
        )
        identity = self._identities.add_identity(identity)

        handle = ChannelHandle(
            handle_id=stable_identifier("hd-email", {"pid": person_id}),
            identity_id=identity.identity_id,
            channel_type=ChannelType.EMAIL,
            address=email,
            verified=True,
            preference_level=ChannelPreferenceLevel.PRIMARY,
            created_at=now,
        )
        handle = self._identities.add_channel_handle(handle)

        return {"identity": identity, "handles": (handle,)}

    # ------------------------------------------------------------------
    # Registration from team runtime
    # ------------------------------------------------------------------

    def register_from_team_runtime(
        self,
        team_id: str,
        team_name: str,
        member_ids: tuple[str, ...] = (),
        organization_id: str = "",
    ) -> dict[str, Any]:
        """Register a team as an identity and link existing member identities."""
        now = _now_iso()

        identity = IdentityRecord(
            identity_id=stable_identifier("id-team", {"tid": team_id}),
            identity_type=IdentityType.TEAM,
            display_name=team_name,
            organization_id=organization_id,
            team_id=team_id,
            tags=("team_runtime",),
            created_at=now,
            updated_at=now,
        )
        identity = self._identities.add_identity(identity)

        links = []
        for mid in member_ids:
            # Only link if member identity already exists
            if self._identities.get_identity(mid) is not None:
                link = IdentityLink(
                    link_id=stable_identifier("lk-team", {"tid": team_id, "mid": mid}),
                    from_identity_id=mid,
                    to_identity_id=identity.identity_id,
                    relation="member_of",
                    created_at=now,
                )
                link = self._identities.link_identities(link)
                links.append(link)

        return {"identity": identity, "links": tuple(links)}

    # ------------------------------------------------------------------
    # Registration from operator identity
    # ------------------------------------------------------------------

    def register_from_operator_identity(
        self,
        operator_id: str,
        name: str,
        email: str,
        *,
        chat_address: str = "",
    ) -> dict[str, Any]:
        """Register an operator identity with email and optional chat handle."""
        now = _now_iso()

        identity = IdentityRecord(
            identity_id=stable_identifier("id-opr", {"oid": operator_id}),
            identity_type=IdentityType.OPERATOR,
            display_name=name,
            tags=("operator",),
            created_at=now,
            updated_at=now,
        )
        identity = self._identities.add_identity(identity)

        handles = []
        email_handle = ChannelHandle(
            handle_id=stable_identifier("hd-opr-email", {"oid": operator_id}),
            identity_id=identity.identity_id,
            channel_type=ChannelType.EMAIL,
            address=email,
            verified=True,
            preference_level=ChannelPreferenceLevel.PRIMARY,
            created_at=now,
        )
        handles.append(self._identities.add_channel_handle(email_handle))

        if chat_address:
            chat_handle = ChannelHandle(
                handle_id=stable_identifier("hd-opr-chat", {"oid": operator_id}),
                identity_id=identity.identity_id,
                channel_type=ChannelType.CHAT,
                address=chat_address,
                verified=True,
                preference_level=ChannelPreferenceLevel.SECONDARY,
                created_at=now,
            )
            handles.append(self._identities.add_channel_handle(chat_handle))

        return {"identity": identity, "handles": tuple(handles)}

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    def route_message_for_identity(
        self,
        identity_id: str,
        *,
        urgency: str = "normal",
    ) -> dict[str, Any]:
        """Route a message to the best handle for an identity and emit event."""
        decision = self._identities.route_contact(identity_id, urgency=urgency)
        if decision is None:
            return {"decision": None, "event": None}

        now = _now_iso()
        event = EventRecord(
            event_id=stable_identifier("evt-route", {"iid": identity_id, "ts": now}),
            event_type=EventType.CUSTOM,
            source=EventSource.COMMUNICATION_SYSTEM,
            correlation_id=identity_id,
            payload={
                "action": "message_routed",
                "identity_id": identity_id,
                "selected_handle_id": decision.selected_handle_id,
                "urgency": urgency,
            },
            emitted_at=now,
        )
        self._events.emit(event)

        return {"decision": decision, "event": event}

    def route_escalation_for_obligation(
        self,
        chain_id: str,
        obligation_id: str,
    ) -> dict[str, Any]:
        """Route escalation through a chain for an obligation and emit event."""
        decisions = self._identities.route_escalation(chain_id)

        now = _now_iso()
        event = EventRecord(
            event_id=stable_identifier("evt-esc", {"chain": chain_id, "obl": obligation_id, "ts": now}),
            event_type=EventType.OBLIGATION_ESCALATED,
            source=EventSource.COMMUNICATION_SYSTEM,
            correlation_id=obligation_id,
            payload={
                "action": "escalation_routed",
                "chain_id": chain_id,
                "obligation_id": obligation_id,
                "target_count": len(decisions),
                "target_ids": tuple(d.target_identity_id for d in decisions),
            },
            emitted_at=now,
        )
        self._events.emit(event)

        return {"decisions": decisions, "event": event}

    def route_notification_for_incident(
        self,
        chain_id: str,
        incident_ref: str,
    ) -> dict[str, Any]:
        """Route notification for an incident through an escalation chain."""
        decisions = self._identities.route_escalation(chain_id)

        now = _now_iso()
        event = EventRecord(
            event_id=stable_identifier("evt-notify", {"chain": chain_id, "inc": incident_ref, "ts": now}),
            event_type=EventType.CUSTOM,
            source=EventSource.COMMUNICATION_SYSTEM,
            correlation_id=incident_ref,
            payload={
                "action": "incident_notification_routed",
                "chain_id": chain_id,
                "incident_ref": incident_ref,
                "target_count": len(decisions),
            },
            emitted_at=now,
        )
        self._events.emit(event)

        return {"decisions": decisions, "event": event}

    # ------------------------------------------------------------------
    # Resolution from communication
    # ------------------------------------------------------------------

    def resolve_handles_from_communication(
        self,
        address: str,
        source_type: str = "communication",
    ) -> IdentityResolutionRecord | None:
        """Resolve an address from communication to a canonical identity."""
        return self._identities.resolve_identity(address, source_type)

    # ------------------------------------------------------------------
    # Memory mesh attachment
    # ------------------------------------------------------------------

    def remember_identity_decision(
        self,
        decision: IdentityRoutingDecision,
        *,
        tags: tuple[str, ...] = (),
    ) -> MemoryRecord:
        """Record a routing decision into the memory mesh."""
        return self._memory.remember_event(
            event_id=decision.decision_id,
            event_type="identity_routing_decision",
            scope=MemoryScope.DOMAIN,
            scope_ref_id=decision.target_identity_id,
            content={
                "decision_id": decision.decision_id,
                "target_identity_id": decision.target_identity_id,
                "selected_handle_id": decision.selected_handle_id,
                "reason": decision.reason,
                "fallback_count": len(decision.fallback_handle_ids),
            },
            tags=("identity", "routing") + tags,
            confidence=0.9,
            trust_level=MemoryTrustLevel.VERIFIED,
        )

    def attach_identity_to_memory_mesh(
        self,
        identity: IdentityRecord,
        *,
        tags: tuple[str, ...] = (),
    ) -> MemoryRecord:
        """Create a memory record for an identity registration."""
        return self._memory.remember_event(
            event_id=identity.identity_id,
            event_type="identity_registered",
            scope=MemoryScope.DOMAIN,
            scope_ref_id=identity.identity_id,
            content={
                "identity_id": identity.identity_id,
                "identity_type": identity.identity_type.value,
                "display_name": identity.display_name,
                "organization_id": identity.organization_id,
                "team_id": identity.team_id,
            },
            tags=("identity", "registration") + tags,
            confidence=1.0,
            trust_level=MemoryTrustLevel.VERIFIED,
        )
