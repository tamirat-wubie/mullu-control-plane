"""Purpose: bridge between communication surface and domain engines.
Governance scope: message ingestion with event emission, obligation creation
    from messages, memory mesh recording, preference-based routing, and
    escalation chain resolution.
Dependencies: CommunicationSurfaceEngine, EventSpineEngine, ObligationRuntimeEngine,
    MemoryMeshEngine, MemoryMeshIntegration, core invariants.
Invariants:
  - Every inbound message produces an event and a memory record.
  - Delivery failures produce failure events.
  - Obligation extraction is explicit — no silent creation.
  - Preference routing respects blocked channels.
  - Escalation chains are evaluated in order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from ..contracts.communication_surface import (
    CallSession,
    CallSessionState,
    CallTranscript,
    ChannelType,
    CommunicationPolicyEffect,
    DeliveryReceipt,
    DeliveryStatus,
    InboundMessage,
    OutboundMessage,
)
from ..contracts.event import EventRecord, EventSource, EventType
from ..contracts.memory_mesh import MemoryScope, MemoryTrustLevel, MemoryType
from ..contracts.obligation import ObligationDeadline, ObligationOwner, ObligationTrigger
from .communication_surface import CommunicationSurfaceEngine
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier
from .memory_mesh import MemoryMeshEngine
from .memory_mesh_integration import MemoryMeshIntegration
from .obligation_runtime import ObligationRuntimeEngine


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class CommunicationSurfaceIntegration:
    """Bridge connecting the communication surface to event spine,
    obligation runtime, and memory mesh.
    """

    def __init__(
        self,
        comm_engine: CommunicationSurfaceEngine,
        event_spine: EventSpineEngine,
        obligation_runtime: ObligationRuntimeEngine,
        memory_engine: MemoryMeshEngine,
    ) -> None:
        if not isinstance(comm_engine, CommunicationSurfaceEngine):
            raise RuntimeCoreInvariantError("comm_engine must be a CommunicationSurfaceEngine")
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        if not isinstance(obligation_runtime, ObligationRuntimeEngine):
            raise RuntimeCoreInvariantError("obligation_runtime must be an ObligationRuntimeEngine")
        if not isinstance(memory_engine, MemoryMeshEngine):
            raise RuntimeCoreInvariantError("memory_engine must be a MemoryMeshEngine")
        self._comm = comm_engine
        self._events = event_spine
        self._obligations = obligation_runtime
        self._memory = MemoryMeshIntegration(memory_engine)

    # ------------------------------------------------------------------
    # Inbound message ingestion
    # ------------------------------------------------------------------

    def ingest_inbound_message(self, message: InboundMessage) -> dict[str, Any]:
        """Ingest an inbound message: store, emit event, create memory record.

        Returns dict with keys: message, event, memory.
        """
        # Store in comm engine
        stored = self._comm.ingest_inbound(message)

        # Emit event
        now = _now_iso()
        event = EventRecord(
            event_id=stable_identifier("evt-comm-in", {"msg": message.message_id}),
            event_type=EventType.COMMUNICATION_REPLIED,
            source=EventSource.COMMUNICATION_SYSTEM,
            correlation_id=message.conversation_id,
            payload={
                "message_id": message.message_id,
                "channel_type": message.channel_type.value,
                "sender_identity_id": message.sender_identity_id,
                "body_preview": message.body[:200] if message.body else "",
            },
            emitted_at=now,
        )
        self._events.emit(event)

        # Create memory record
        mem = self._memory.remember_event(
            event_id=event.event_id,
            event_type="inbound_message",
            scope=MemoryScope.DOMAIN,
            scope_ref_id=message.conversation_id,
            content={
                "message_id": message.message_id,
                "channel_type": message.channel_type.value,
                "sender": message.sender_identity_id,
                "subject": message.subject,
            },
            tags=("communication", "inbound", message.channel_type.value),
        )

        return {"message": stored, "event": event, "memory": mem}

    # ------------------------------------------------------------------
    # Outbound message dispatch
    # ------------------------------------------------------------------

    def send_outbound_message(
        self,
        message: OutboundMessage,
        *,
        policy_id: str | None = None,
    ) -> dict[str, Any]:
        """Send an outbound message: policy check, store, emit event, create memory.

        Returns dict with keys: message, event, memory, policy_decision (if checked).
        """
        result: dict[str, Any] = {}

        # Policy check if requested
        if policy_id is not None:
            decision = self._comm.evaluate_policy(policy_id, message.channel_type)
            result["policy_decision"] = decision
            if decision.effect == CommunicationPolicyEffect.DENY:
                # Emit denial event
                now = _now_iso()
                deny_event = EventRecord(
                    event_id=stable_identifier("evt-comm-deny", {"msg": message.message_id}),
                    event_type=EventType.COMMUNICATION_TIMED_OUT,
                    source=EventSource.COMMUNICATION_SYSTEM,
                    correlation_id=message.conversation_id,
                    payload={
                        "message_id": message.message_id,
                        "reason": decision.reason,
                        "channel_type": message.channel_type.value,
                    },
                    emitted_at=now,
                )
                self._events.emit(deny_event)
                result["event"] = deny_event
                return result

        # Store
        stored = self._comm.send_outbound(message)
        result["message"] = stored

        # Emit event
        now = _now_iso()
        event = EventRecord(
            event_id=stable_identifier("evt-comm-out", {"msg": message.message_id}),
            event_type=EventType.COMMUNICATION_SENT,
            source=EventSource.COMMUNICATION_SYSTEM,
            correlation_id=message.conversation_id,
            payload={
                "message_id": message.message_id,
                "channel_type": message.channel_type.value,
                "recipient_identity_id": message.recipient_identity_id,
            },
            emitted_at=now,
        )
        self._events.emit(event)
        result["event"] = event

        # Memory record
        mem = self._memory.remember_event(
            event_id=event.event_id,
            event_type="outbound_message",
            scope=MemoryScope.DOMAIN,
            scope_ref_id=message.conversation_id,
            content={
                "message_id": message.message_id,
                "channel_type": message.channel_type.value,
                "recipient": message.recipient_identity_id,
            },
            tags=("communication", "outbound", message.channel_type.value),
        )
        result["memory"] = mem

        return result

    # ------------------------------------------------------------------
    # Delivery receipt handling
    # ------------------------------------------------------------------

    def ingest_delivery_receipt(self, receipt: DeliveryReceipt) -> dict[str, Any]:
        """Record a delivery receipt: store, emit failure event if needed.

        Returns dict with keys: receipt, event (if failure).
        """
        stored = self._comm.record_receipt(receipt)
        result: dict[str, Any] = {"receipt": stored}

        if receipt.status in (DeliveryStatus.FAILED, DeliveryStatus.BOUNCED, DeliveryStatus.REJECTED):
            now = _now_iso()
            event = EventRecord(
                event_id=stable_identifier("evt-comm-fail", {"rcpt": receipt.receipt_id}),
                event_type=EventType.COMMUNICATION_TIMED_OUT,
                source=EventSource.COMMUNICATION_SYSTEM,
                correlation_id=receipt.message_id,
                payload={
                    "receipt_id": receipt.receipt_id,
                    "message_id": receipt.message_id,
                    "status": receipt.status.value,
                    "failure_reason": receipt.failure_reason,
                    "channel_type": receipt.channel_type.value,
                },
                emitted_at=now,
            )
            self._events.emit(event)
            result["event"] = event

        return result

    # ------------------------------------------------------------------
    # Call session lifecycle
    # ------------------------------------------------------------------

    def start_call_session(self, session: CallSession) -> dict[str, Any]:
        """Start a call session: store and emit event.

        Returns dict with keys: session, event.
        """
        stored = self._comm.start_call_session(session)

        now = _now_iso()
        event = EventRecord(
            event_id=stable_identifier("evt-call-start", {"session": session.session_id}),
            event_type=EventType.COMMUNICATION_SENT,
            source=EventSource.COMMUNICATION_SYSTEM,
            correlation_id=session.conversation_id,
            payload={
                "session_id": session.session_id,
                "channel_type": session.channel_type.value,
                "participant_ids": tuple(session.participant_ids),
                "state": session.state.value,
            },
            emitted_at=now,
        )
        self._events.emit(event)

        return {"session": stored, "event": event}

    def complete_call_session(
        self,
        session_id: str,
        state: CallSessionState,
        ended_at: str,
        duration_seconds: int,
    ) -> dict[str, Any]:
        """Complete a call session: update, emit event, create memory.

        Returns dict with keys: session, event, memory.
        """
        completed = self._comm.complete_call_session(
            session_id, state, ended_at, duration_seconds,
        )

        now = _now_iso()
        event = EventRecord(
            event_id=stable_identifier("evt-call-end", {"session": session_id}),
            event_type=EventType.COMMUNICATION_REPLIED,
            source=EventSource.COMMUNICATION_SYSTEM,
            correlation_id=completed.conversation_id,
            payload={
                "session_id": session_id,
                "state": state.value,
                "duration_seconds": duration_seconds,
            },
            emitted_at=now,
        )
        self._events.emit(event)

        mem = self._memory.remember_event(
            event_id=event.event_id,
            event_type="call_completed",
            scope=MemoryScope.DOMAIN,
            scope_ref_id=completed.conversation_id,
            content={
                "session_id": session_id,
                "state": state.value,
                "duration_seconds": duration_seconds,
                "channel_type": completed.channel_type.value,
            },
            tags=("communication", "call", completed.channel_type.value),
        )

        return {"session": completed, "event": event, "memory": mem}

    # ------------------------------------------------------------------
    # Obligation extraction from messages
    # ------------------------------------------------------------------

    def extract_obligations_from_message(
        self,
        message_id: str,
        obligations: list[dict[str, Any]],
    ) -> list[Any]:
        """Extract obligations from a message.

        Each obligation dict must have: description, owner_id, owner_type,
        display_name, deadline_id, due_at.

        Returns list of created ObligationRecords.
        """
        message = self._comm.get_inbound(message_id)
        if message is None:
            raise RuntimeCoreInvariantError(f"inbound message not found: {message_id}")

        created = []
        for obl_spec in obligations:
            owner = ObligationOwner(
                owner_id=obl_spec["owner_id"],
                owner_type=obl_spec["owner_type"],
                display_name=obl_spec["display_name"],
            )
            deadline = ObligationDeadline(
                deadline_id=obl_spec["deadline_id"],
                due_at=obl_spec["due_at"],
            )
            record = self._obligations.create_obligation(
                trigger=ObligationTrigger.COMMUNICATION_FOLLOW_UP,
                trigger_ref_id=message_id,
                owner=owner,
                deadline=deadline,
                description=obl_spec["description"],
                correlation_id=message.conversation_id,
            )
            created.append(record)

        return tuple(created)

    def extract_commitments_from_message(
        self,
        message_id: str,
        commitments: list[dict[str, Any]],
    ) -> list[Any]:
        """Extract commitments from a message as obligations.

        Same interface as extract_obligations_from_message but uses
        CUSTOM trigger and records in memory.
        """
        message = self._comm.get_inbound(message_id)
        if message is None:
            raise RuntimeCoreInvariantError(f"inbound message not found: {message_id}")

        created = []
        for idx, commit_spec in enumerate(commitments):
            owner = ObligationOwner(
                owner_id=commit_spec["owner_id"],
                owner_type=commit_spec["owner_type"],
                display_name=commit_spec["display_name"],
            )
            deadline = ObligationDeadline(
                deadline_id=commit_spec["deadline_id"],
                due_at=commit_spec["due_at"],
            )
            obl_id = stable_identifier("obl-commit", {
                "msg": message_id, "idx": idx,
                "deadline": commit_spec["deadline_id"],
            })
            record = self._obligations.create_obligation(
                obligation_id=obl_id,
                trigger=ObligationTrigger.CUSTOM,
                trigger_ref_id=message_id,
                owner=owner,
                deadline=deadline,
                description=commit_spec["description"],
                correlation_id=message.conversation_id,
                metadata={"source": "commitment_extraction", "message_id": message_id},
            )

            # Remember commitment in memory mesh
            self._memory.remember_obligation(
                obligation_id=record.obligation_id,
                state="created",
                scope=MemoryScope.OBLIGATION,
                scope_ref_id=record.obligation_id,
                content={
                    "description": commit_spec["description"],
                    "source_message_id": message_id,
                    "commitment": True,
                },
                tags=("commitment", "communication"),
            )

            created.append(record)

        return tuple(created)

    # ------------------------------------------------------------------
    # Memory recording
    # ------------------------------------------------------------------

    def remember_communication(
        self,
        conversation_id: str,
        summary: str,
        *,
        tags: tuple[str, ...] = (),
    ) -> Any:
        """Create a strategic memory record summarizing a communication thread."""
        return self._memory.remember_meta_snapshot(
            snapshot_id=stable_identifier("comm-summary", {"conv": conversation_id}),
            scope=MemoryScope.DOMAIN,
            scope_ref_id=conversation_id,
            content={"conversation_id": conversation_id, "summary": summary},
            tags=("communication", "summary") + tags,
        )

    # ------------------------------------------------------------------
    # Preference-based routing
    # ------------------------------------------------------------------

    def route_for_contact_preference(self, contact_id: str) -> ChannelType | None:
        """Return the preferred channel for a contact, respecting blocks."""
        pref = self._comm.get_contact_preference(contact_id)
        if pref is None:
            return None
        blocked = set(pref.blocked_channels)
        for ch in pref.preferred_channels:
            if ch not in blocked:
                return ch
        return None

    def route_for_escalation_preference(self, contact_id: str) -> tuple[ChannelType, ...]:
        """Return the escalation chain for a contact, filtering blocked channels."""
        pref = self._comm.get_contact_preference(contact_id)
        blocked = set(pref.blocked_channels) if pref else set()
        chain = self._comm.route_for_escalation(contact_id)
        return tuple(ch for ch in chain if ch not in blocked)
