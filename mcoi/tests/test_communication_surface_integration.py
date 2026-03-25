"""Integration tests for CommunicationSurfaceIntegration bridge."""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.communication_surface import (
    CallSession,
    CallSessionState,
    ChannelType,
    ContactPreference,
    DeliveryReceipt,
    DeliveryStatus,
    EscalationPreference,
    InboundMessage,
    OutboundMessage,
    CommunicationPolicy,
    CommunicationPolicyEffect,
)
from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.contracts.memory_mesh import MemoryType
from mcoi_runtime.core.communication_surface import CommunicationSurfaceEngine
from mcoi_runtime.core.communication_surface_integration import CommunicationSurfaceIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

NOW = "2026-03-20T12:00:00+00:00"
LATER = "2026-03-21T12:00:00+00:00"
DUE = "2026-03-25T12:00:00+00:00"


def _make_bridge():
    comm = CommunicationSurfaceEngine()
    events = EventSpineEngine()
    obligations = ObligationRuntimeEngine()
    memory = MemoryMeshEngine()
    bridge = CommunicationSurfaceIntegration(comm, events, obligations, memory)
    return comm, events, obligations, memory, bridge


def _inbound(mid="msg-in-1", **kw):
    defaults = dict(
        message_id=mid, conversation_id="conv-1",
        channel_type=ChannelType.SMS, sender_identity_id="id-1",
        body="I approve the request", received_at=NOW,
    )
    defaults.update(kw)
    return InboundMessage(**defaults)


def _outbound(mid="msg-out-1", **kw):
    defaults = dict(
        message_id=mid, conversation_id="conv-1",
        channel_type=ChannelType.EMAIL, recipient_identity_id="id-2",
        body="Please review", scheduled_at=NOW,
    )
    defaults.update(kw)
    return OutboundMessage(**defaults)


class TestCommunicationSurfaceIntegration:
    def test_invalid_comm_engine_rejected(self):
        with pytest.raises(RuntimeCoreInvariantError):
            CommunicationSurfaceIntegration(
                "bad", EventSpineEngine(), ObligationRuntimeEngine(), MemoryMeshEngine(),
            )

    # -- ingest_inbound_message --

    def test_ingest_inbound_creates_event_and_memory(self):
        comm, events, _, memory, bridge = _make_bridge()
        result = bridge.ingest_inbound_message(_inbound())
        assert result["message"].message_id == "msg-in-1"
        assert result["event"].event_type == EventType.COMMUNICATION_REPLIED
        assert result["memory"].memory_type == MemoryType.OBSERVATION
        assert events._events  # event was emitted
        assert memory.memory_count == 1

    # -- send_outbound_message --

    def test_send_outbound_creates_event_and_memory(self):
        comm, events, _, memory, bridge = _make_bridge()
        result = bridge.send_outbound_message(_outbound())
        assert result["message"].message_id == "msg-out-1"
        assert result["event"].event_type == EventType.COMMUNICATION_SENT
        assert result["memory"].memory_type == MemoryType.OBSERVATION
        assert events._events
        assert memory.memory_count == 1

    def test_send_outbound_with_policy_allow(self):
        comm, _, _, _, bridge = _make_bridge()
        comm.register_policy(CommunicationPolicy(
            policy_id="pol-1", name="Allow email",
            allowed_channels=(ChannelType.EMAIL,), created_at=NOW,
        ))
        result = bridge.send_outbound_message(_outbound(), policy_id="pol-1")
        assert result["policy_decision"].effect == CommunicationPolicyEffect.ALLOW
        assert "message" in result

    def test_send_outbound_with_policy_deny(self):
        comm, events, _, memory, bridge = _make_bridge()
        comm.register_policy(CommunicationPolicy(
            policy_id="pol-1", name="Deny fax",
            allowed_channels=(ChannelType.EMAIL,),
            denied_channels=(ChannelType.FAX,),
            created_at=NOW,
        ))
        result = bridge.send_outbound_message(
            _outbound(channel_type=ChannelType.FAX), policy_id="pol-1",
        )
        assert result["policy_decision"].effect == CommunicationPolicyEffect.DENY
        assert "message" not in result  # not sent
        assert "event" in result  # denial event emitted

    # -- ingest_delivery_receipt --

    def test_ingest_receipt_success(self):
        comm, events, _, _, bridge = _make_bridge()
        comm.send_outbound(_outbound("msg-1"))
        result = bridge.ingest_delivery_receipt(DeliveryReceipt(
            receipt_id="rcpt-1", message_id="msg-1",
            status=DeliveryStatus.DELIVERED, channel_type=ChannelType.EMAIL,
            created_at=NOW,
        ))
        assert result["receipt"].status == DeliveryStatus.DELIVERED
        assert "event" not in result  # no failure event

    def test_ingest_receipt_failure_emits_event(self):
        comm, events, _, _, bridge = _make_bridge()
        comm.send_outbound(_outbound("msg-1"))
        result = bridge.ingest_delivery_receipt(DeliveryReceipt(
            receipt_id="rcpt-1", message_id="msg-1",
            status=DeliveryStatus.FAILED, channel_type=ChannelType.EMAIL,
            failure_reason="Mailbox full", created_at=NOW,
        ))
        assert result["receipt"].status == DeliveryStatus.FAILED
        assert "event" in result
        assert result["event"].event_type == EventType.COMMUNICATION_TIMED_OUT

    # -- call sessions --

    def test_start_call_session(self):
        comm, events, _, _, bridge = _make_bridge()
        session = CallSession(
            session_id="call-1", conversation_id="conv-1",
            channel_type=ChannelType.VOICE,
            participant_ids=("p1", "p2"),
            state=CallSessionState.CONNECTED, started_at=NOW,
        )
        result = bridge.start_call_session(session)
        assert result["session"].session_id == "call-1"
        assert result["event"].event_type == EventType.COMMUNICATION_SENT

    def test_complete_call_session(self):
        comm, events, _, memory, bridge = _make_bridge()
        session = CallSession(
            session_id="call-1", conversation_id="conv-1",
            channel_type=ChannelType.VOICE,
            participant_ids=("p1",),
            state=CallSessionState.CONNECTED, started_at=NOW,
        )
        comm.start_call_session(session)
        result = bridge.complete_call_session(
            "call-1", CallSessionState.COMPLETED, LATER, 600,
        )
        assert result["session"].state == CallSessionState.COMPLETED
        assert result["event"].event_type == EventType.COMMUNICATION_REPLIED
        assert result["memory"].memory_type == MemoryType.OBSERVATION
        assert memory.memory_count == 1

    # -- obligation extraction --

    def test_extract_obligations_from_message(self):
        comm, _, obligations, _, bridge = _make_bridge()
        comm.ingest_inbound(_inbound("msg-1"))
        obl_specs = [
            {
                "description": "Follow up on approval",
                "owner_id": "op-1", "owner_type": "operator",
                "display_name": "Operator 1",
                "deadline_id": "dl-1", "due_at": DUE,
            },
        ]
        created = bridge.extract_obligations_from_message("msg-1", obl_specs)
        assert len(created) == 1
        assert created[0].description == "Follow up on approval"
        assert len(obligations._obligations) == 1

    def test_extract_obligations_missing_message_rejected(self):
        _, _, _, _, bridge = _make_bridge()
        with pytest.raises(RuntimeCoreInvariantError, match="not found"):
            bridge.extract_obligations_from_message("nope", [])

    # -- commitment extraction --

    def test_extract_commitments_creates_obligation_and_memory(self):
        comm, _, obligations, memory, bridge = _make_bridge()
        comm.ingest_inbound(_inbound("msg-1"))
        commits = [
            {
                "description": "I will deliver by Friday",
                "owner_id": "c1", "owner_type": "contact",
                "display_name": "Contact 1",
                "deadline_id": "dl-1", "due_at": DUE,
            },
        ]
        created = bridge.extract_commitments_from_message("msg-1", commits)
        assert len(created) == 1
        assert len(obligations._obligations) == 1
        assert memory.memory_count == 1  # commitment memory

    # -- remember_communication --

    def test_remember_communication(self):
        _, _, _, memory, bridge = _make_bridge()
        mem = bridge.remember_communication("conv-1", "Customer approved the proposal")
        assert mem.memory_type == MemoryType.STRATEGIC
        assert memory.memory_count == 1

    # -- routing --

    def test_route_for_contact_preference(self):
        comm, _, _, _, bridge = _make_bridge()
        comm.set_contact_preference(ContactPreference(
            preference_id="pref-1", contact_id="c1",
            preferred_channels=(ChannelType.SMS, ChannelType.EMAIL),
            created_at=NOW,
        ))
        assert bridge.route_for_contact_preference("c1") == ChannelType.SMS

    def test_route_for_contact_preference_respects_blocked(self):
        comm, _, _, _, bridge = _make_bridge()
        comm.set_contact_preference(ContactPreference(
            preference_id="pref-1", contact_id="c1",
            preferred_channels=(ChannelType.SMS, ChannelType.EMAIL),
            blocked_channels=(ChannelType.SMS,),
            created_at=NOW,
        ))
        assert bridge.route_for_contact_preference("c1") == ChannelType.EMAIL

    def test_route_for_contact_preference_missing(self):
        _, _, _, _, bridge = _make_bridge()
        assert bridge.route_for_contact_preference("nope") is None

    def test_route_for_escalation_preference(self):
        comm, _, _, _, bridge = _make_bridge()
        comm.set_escalation_preference(EscalationPreference(
            preference_id="esc-1", contact_id="c1",
            escalation_chain=(ChannelType.EMAIL, ChannelType.SMS, ChannelType.VOICE),
            created_at=NOW,
        ))
        chain = bridge.route_for_escalation_preference("c1")
        assert chain == (ChannelType.EMAIL, ChannelType.SMS, ChannelType.VOICE)

    def test_route_for_escalation_filters_blocked(self):
        comm, _, _, _, bridge = _make_bridge()
        comm.set_contact_preference(ContactPreference(
            preference_id="pref-1", contact_id="c1",
            preferred_channels=(ChannelType.EMAIL,),
            blocked_channels=(ChannelType.SMS,),
            created_at=NOW,
        ))
        comm.set_escalation_preference(EscalationPreference(
            preference_id="esc-1", contact_id="c1",
            escalation_chain=(ChannelType.EMAIL, ChannelType.SMS, ChannelType.VOICE),
            created_at=NOW,
        ))
        chain = bridge.route_for_escalation_preference("c1")
        assert ChannelType.SMS not in chain
        assert chain == (ChannelType.EMAIL, ChannelType.VOICE)
