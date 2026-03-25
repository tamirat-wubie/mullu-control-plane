"""Golden scenario tests for the omni-channel communication surface.

Tests end-to-end flows spanning contracts, engine, integration bridge,
event spine, obligation runtime, and memory mesh.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.communication_surface import (
    CallSession,
    CallSessionState,
    CallTranscript,
    ChannelCapabilityManifest,
    ChannelIdentity,
    ChannelType,
    CommunicationPolicy,
    CommunicationPolicyEffect,
    ContactPreference,
    ConversationHandle,
    DeliveryReceipt,
    DeliveryStatus,
    EscalationPreference,
    InboundMessage,
    OutboundMessage,
    TranscriptSegment,
)
from mcoi_runtime.contracts.event import EventType
from mcoi_runtime.contracts.memory_mesh import MemoryScope, MemoryType
from mcoi_runtime.core.communication_surface import CommunicationSurfaceEngine
from mcoi_runtime.core.communication_surface_integration import CommunicationSurfaceIntegration
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.memory_mesh import MemoryMeshEngine
from mcoi_runtime.core.obligation_runtime import ObligationRuntimeEngine

NOW = "2026-03-20T12:00:00+00:00"
LATER = "2026-03-20T13:00:00+00:00"
DUE = "2026-03-25T12:00:00+00:00"


def _full_stack():
    """Create full stack: comm + events + obligations + memory + bridge."""
    comm = CommunicationSurfaceEngine()
    events = EventSpineEngine()
    obligations = ObligationRuntimeEngine()
    memory = MemoryMeshEngine()
    bridge = CommunicationSurfaceIntegration(comm, events, obligations, memory)
    return comm, events, obligations, memory, bridge


class TestGoldenInboundApprovalSMS:
    """Golden 1: inbound approval SMS creates obligation and memory record."""

    def test_inbound_sms_creates_obligation_and_memory(self):
        comm, events, obligations, memory, bridge = _full_stack()

        # Setup identity
        comm.register_identity(ChannelIdentity(
            identity_id="id-sms-1", contact_id="c1",
            channel_type=ChannelType.SMS, address="+15551234567",
            verified=True, created_at=NOW,
        ))

        # Create conversation
        comm.create_conversation(ConversationHandle(
            conversation_id="conv-approval",
            subject="Budget approval request",
            contact_ids=("c1",),
            channel_types=(ChannelType.SMS,),
            started_at=NOW,
        ))

        # Ingest inbound SMS
        msg = InboundMessage(
            message_id="sms-in-1",
            conversation_id="conv-approval",
            channel_type=ChannelType.SMS,
            sender_identity_id="id-sms-1",
            body="Approved. Please proceed with the Q2 budget allocation.",
            received_at=NOW,
        )
        result = bridge.ingest_inbound_message(msg)

        # Verify event emitted
        assert result["event"].event_type == EventType.COMMUNICATION_REPLIED
        assert len(events._events) == 1

        # Verify memory created
        assert result["memory"].memory_type == MemoryType.OBSERVATION
        assert memory.memory_count == 1

        # Extract obligation from the approval
        obl_specs = [{
            "description": "Proceed with Q2 budget allocation per SMS approval",
            "owner_id": "team-finance",
            "owner_type": "team",
            "display_name": "Finance Team",
            "deadline_id": "dl-q2",
            "due_at": DUE,
        }]
        created = bridge.extract_obligations_from_message("sms-in-1", obl_specs)
        assert len(created) == 1
        assert "Q2 budget" in created[0].description
        assert len(obligations._obligations) == 1


class TestGoldenFailedOutboundEvent:
    """Golden 2: failed outbound message emits delivery failure event."""

    def test_failed_outbound_emits_failure_event(self):
        comm, events, _, _, bridge = _full_stack()

        # Send outbound
        out_msg = OutboundMessage(
            message_id="out-fail-1",
            conversation_id="conv-1",
            channel_type=ChannelType.EMAIL,
            recipient_identity_id="id-2",
            body="Important update",
            scheduled_at=NOW,
        )
        bridge.send_outbound_message(out_msg)
        assert len(events._events) == 1  # send event

        # Record failure receipt
        result = bridge.ingest_delivery_receipt(DeliveryReceipt(
            receipt_id="rcpt-fail-1",
            message_id="out-fail-1",
            status=DeliveryStatus.BOUNCED,
            channel_type=ChannelType.EMAIL,
            failure_reason="Mailbox does not exist",
            created_at=LATER,
        ))

        assert result["receipt"].status == DeliveryStatus.BOUNCED
        assert "event" in result
        assert result["event"].event_type == EventType.COMMUNICATION_TIMED_OUT
        assert "Mailbox does not exist" in result["event"].payload["failure_reason"]
        assert len(events._events) == 2  # send + failure


class TestGoldenVoiceTranscriptCommitment:
    """Golden 3: voice transcript yields commitment extraction and obligation."""

    def test_voice_transcript_creates_commitment_obligation(self):
        comm, events, obligations, memory, bridge = _full_stack()

        # Setup call
        comm.create_conversation(ConversationHandle(
            conversation_id="conv-call-1",
            subject="Client onboarding call",
            contact_ids=("c1", "c2"),
            channel_types=(ChannelType.VOICE,),
            started_at=NOW,
        ))

        session = CallSession(
            session_id="call-onboard-1",
            conversation_id="conv-call-1",
            channel_type=ChannelType.VOICE,
            participant_ids=("c1", "c2"),
            state=CallSessionState.CONNECTED,
            started_at=NOW,
        )
        bridge.start_call_session(session)

        # Complete call
        result = bridge.complete_call_session(
            "call-onboard-1", CallSessionState.COMPLETED, LATER, 1800,
        )
        assert result["session"].duration_seconds == 1800
        assert result["memory"].memory_type == MemoryType.OBSERVATION

        # Add transcript
        segments = (
            TranscriptSegment(
                segment_id="seg-1", speaker_id="c1",
                text="I will have the contract ready by March 25th",
                started_at=NOW, ended_at=LATER, confidence=0.92,
            ),
            TranscriptSegment(
                segment_id="seg-2", speaker_id="c2",
                text="Great, I will review and send feedback within 2 days",
                started_at=NOW, ended_at=LATER, confidence=0.88,
            ),
        )
        transcript = CallTranscript(
            transcript_id="tx-onboard-1",
            session_id="call-onboard-1",
            segments=segments,
            created_at=LATER,
        )
        comm.add_transcript(transcript)

        # Now ingest a summary as inbound message for obligation extraction
        summary_msg = InboundMessage(
            message_id="msg-call-summary-1",
            conversation_id="conv-call-1",
            channel_type=ChannelType.VOICE,
            sender_identity_id="system",
            body="Transcript commitments: contract by March 25, feedback within 2 days",
            received_at=LATER,
        )
        comm.ingest_inbound(summary_msg)

        # Extract commitments
        commits = [
            {
                "description": "Contract ready by March 25th",
                "owner_id": "c1", "owner_type": "contact",
                "display_name": "Client Contact",
                "deadline_id": "dl-contract", "due_at": DUE,
            },
            {
                "description": "Review feedback within 2 days",
                "owner_id": "c2", "owner_type": "contact",
                "display_name": "Account Manager",
                "deadline_id": "dl-review", "due_at": "2026-03-27T12:00:00+00:00",
            },
        ]
        created = bridge.extract_commitments_from_message("msg-call-summary-1", commits)
        assert len(created) == 2
        assert len(obligations._obligations) == 2
        # Memory should have: call completed + 2 commitment memories
        assert memory.memory_count >= 3


class TestGoldenContactPreferenceRouting:
    """Golden 4: contact preference routes escalation to preferred channel."""

    def test_escalation_routes_to_preferred_channel(self):
        comm, _, _, _, bridge = _full_stack()

        # Set preferences
        comm.set_contact_preference(ContactPreference(
            preference_id="pref-1", contact_id="c1",
            preferred_channels=(ChannelType.SMS, ChannelType.EMAIL),
            blocked_channels=(ChannelType.VOICE,),
            created_at=NOW,
        ))
        comm.set_escalation_preference(EscalationPreference(
            preference_id="esc-1", contact_id="c1",
            escalation_chain=(ChannelType.SMS, ChannelType.VOICE, ChannelType.EMAIL),
            created_at=NOW,
        ))

        # Primary route
        primary = bridge.route_for_contact_preference("c1")
        assert primary == ChannelType.SMS

        # Escalation chain (voice blocked)
        chain = bridge.route_for_escalation_preference("c1")
        assert ChannelType.VOICE not in chain
        assert chain == (ChannelType.SMS, ChannelType.EMAIL)


class TestGoldenOmniChannelMemoryRetrieval:
    """Golden 5: omnichannel thread history retrieves relevant memory."""

    def test_omnichannel_thread_memory(self):
        comm, events, _, memory, bridge = _full_stack()

        # Conversation spanning email and SMS
        comm.create_conversation(ConversationHandle(
            conversation_id="conv-omni-1",
            subject="Support ticket #1234",
            contact_ids=("c1",),
            channel_types=(ChannelType.EMAIL, ChannelType.SMS),
            started_at=NOW,
        ))

        # Inbound email
        bridge.ingest_inbound_message(InboundMessage(
            message_id="email-1",
            conversation_id="conv-omni-1",
            channel_type=ChannelType.EMAIL,
            sender_identity_id="id-email-1",
            body="I have a billing issue with order #5678",
            received_at=NOW,
        ))

        # Outbound email reply
        bridge.send_outbound_message(OutboundMessage(
            message_id="email-reply-1",
            conversation_id="conv-omni-1",
            channel_type=ChannelType.EMAIL,
            recipient_identity_id="id-email-1",
            body="We are investigating your billing issue",
            scheduled_at=NOW,
        ))

        # Follow-up inbound SMS
        bridge.ingest_inbound_message(InboundMessage(
            message_id="sms-followup-1",
            conversation_id="conv-omni-1",
            channel_type=ChannelType.SMS,
            sender_identity_id="id-sms-1",
            body="Any update on my billing issue?",
            received_at=LATER,
        ))

        # Remember conversation summary
        bridge.remember_communication(
            "conv-omni-1",
            "Customer billing issue #5678 across email and SMS",
            tags=("billing", "support"),
        )

        # Verify memory records for this conversation
        from mcoi_runtime.contracts.memory_mesh import MemoryRetrievalQuery
        q = MemoryRetrievalQuery(
            query_id="qry-omni",
            scope=MemoryScope.DOMAIN,
            scope_ref_id="conv-omni-1",
        )
        result = memory.retrieve(q)
        # 3 message memories + 1 summary = 4
        assert result.total == 4

        # Events tracked
        assert len(events._events) == 3  # 2 inbound + 1 outbound


class TestGoldenPolicyDeniesChannel:
    """Golden 6: communication policy denies a prohibited channel and records reason."""

    def test_policy_denies_prohibited_channel(self):
        comm, events, _, _, bridge = _full_stack()

        # Register policy that denies fax
        comm.register_policy(CommunicationPolicy(
            policy_id="pol-strict",
            name="No fax policy",
            allowed_channels=(ChannelType.EMAIL, ChannelType.SMS),
            denied_channels=(ChannelType.FAX,),
            created_at=NOW,
        ))

        # Attempt to send via fax
        fax_msg = OutboundMessage(
            message_id="fax-1",
            conversation_id="conv-1",
            channel_type=ChannelType.FAX,
            recipient_identity_id="id-fax-1",
            body="Document for review",
            scheduled_at=NOW,
        )
        result = bridge.send_outbound_message(fax_msg, policy_id="pol-strict")

        # Verify denied
        assert result["policy_decision"].effect == CommunicationPolicyEffect.DENY
        assert "denied" in result["policy_decision"].reason.lower()
        assert "message" not in result  # not sent

        # Denial event emitted
        assert "event" in result
        assert len(events._events) == 1

        # Now send via allowed channel
        email_msg = OutboundMessage(
            message_id="email-1",
            conversation_id="conv-1",
            channel_type=ChannelType.EMAIL,
            recipient_identity_id="id-email-1",
            body="Document for review",
            scheduled_at=NOW,
        )
        result2 = bridge.send_outbound_message(email_msg, policy_id="pol-strict")
        assert result2["policy_decision"].effect == CommunicationPolicyEffect.ALLOW
        assert "message" in result2
        assert len(events._events) == 2  # denial + send
