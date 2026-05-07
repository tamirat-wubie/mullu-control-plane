"""Engine-level tests for CommunicationSurfaceEngine."""

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
from mcoi_runtime.core.communication_surface import CommunicationSurfaceEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError

NOW = "2026-03-20T12:00:00+00:00"
LATER = "2026-03-21T12:00:00+00:00"


def _identity(iid: str = "id-1", **kw) -> ChannelIdentity:
    defaults = dict(
        identity_id=iid, contact_id="c1",
        channel_type=ChannelType.EMAIL, address="a@b.com", created_at=NOW,
    )
    defaults.update(kw)
    return ChannelIdentity(**defaults)


def _conversation(cid: str = "conv-1", **kw) -> ConversationHandle:
    defaults = dict(
        conversation_id=cid, subject="Test", contact_ids=("c1",),
        channel_types=(ChannelType.EMAIL,), started_at=NOW,
    )
    defaults.update(kw)
    return ConversationHandle(**defaults)


def _inbound(mid: str = "msg-in-1", **kw) -> InboundMessage:
    defaults = dict(
        message_id=mid, conversation_id="conv-1",
        channel_type=ChannelType.SMS, sender_identity_id="id-1",
        body="Hello", received_at=NOW,
    )
    defaults.update(kw)
    return InboundMessage(**defaults)


def _outbound(mid: str = "msg-out-1", **kw) -> OutboundMessage:
    defaults = dict(
        message_id=mid, conversation_id="conv-1",
        channel_type=ChannelType.EMAIL, recipient_identity_id="id-2",
        body="Hi there", scheduled_at=NOW,
    )
    defaults.update(kw)
    return OutboundMessage(**defaults)


class TestCommunicationSurfaceEngine:
    def _engine(self) -> CommunicationSurfaceEngine:
        return CommunicationSurfaceEngine()

    # -- identities --

    def test_register_and_get_identity(self):
        e = self._engine()
        i = e.register_identity(_identity("id-1"))
        assert e.get_identity("id-1") is i
        assert e.identity_count == 1

    def test_duplicate_identity_rejected(self):
        e = self._engine()
        e.register_identity(_identity("id-1"))
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate") as exc_info:
            e.register_identity(_identity("id-1"))
        assert "id-1" not in str(exc_info.value)

    def test_get_identities_for_contact(self):
        e = self._engine()
        e.register_identity(_identity("id-1", contact_id="c1", channel_type=ChannelType.EMAIL))
        e.register_identity(_identity("id-2", contact_id="c1", channel_type=ChannelType.SMS, address="+1234"))
        e.register_identity(_identity("id-3", contact_id="c2", channel_type=ChannelType.EMAIL, address="x@y.com"))
        result = e.get_identities_for_contact("c1")
        assert len(result) == 2

    # -- conversations --

    def test_create_and_get_conversation(self):
        e = self._engine()
        c = e.create_conversation(_conversation("conv-1"))
        assert e.get_conversation("conv-1") is c
        assert e.conversation_count == 1

    def test_duplicate_conversation_rejected(self):
        e = self._engine()
        e.create_conversation(_conversation("conv-1"))
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate") as exc_info:
            e.create_conversation(_conversation("conv-1"))
        assert "conv-1" not in str(exc_info.value)

    # -- inbound --

    def test_ingest_and_get_inbound(self):
        e = self._engine()
        m = e.ingest_inbound(_inbound("msg-1"))
        assert e.get_inbound("msg-1") is m
        assert e.inbound_count == 1

    def test_duplicate_inbound_rejected(self):
        e = self._engine()
        e.ingest_inbound(_inbound("msg-1"))
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            e.ingest_inbound(_inbound("msg-1"))

    def test_list_inbound_for_conversation(self):
        e = self._engine()
        e.ingest_inbound(_inbound("m1", conversation_id="conv-1"))
        e.ingest_inbound(_inbound("m2", conversation_id="conv-1"))
        e.ingest_inbound(_inbound("m3", conversation_id="conv-2"))
        result = e.list_inbound_for_conversation("conv-1")
        assert len(result) == 2

    # -- outbound --

    def test_send_and_get_outbound(self):
        e = self._engine()
        m = e.send_outbound(_outbound("msg-1"))
        assert e.get_outbound("msg-1") is m
        assert e.outbound_count == 1

    def test_duplicate_outbound_rejected(self):
        e = self._engine()
        e.send_outbound(_outbound("msg-1"))
        with pytest.raises(RuntimeCoreInvariantError, match="duplicate"):
            e.send_outbound(_outbound("msg-1"))

    # -- receipts --

    def test_record_receipt(self):
        e = self._engine()
        e.send_outbound(_outbound("msg-1"))
        r = DeliveryReceipt(
            receipt_id="rcpt-1", message_id="msg-1",
            status=DeliveryStatus.DELIVERED, channel_type=ChannelType.EMAIL,
            created_at=NOW,
        )
        stored = e.record_receipt(r)
        assert e.receipt_count == 1
        receipts = e.get_receipts_for_message("msg-1")
        assert len(receipts) == 1

    def test_receipt_missing_outbound_rejected(self):
        e = self._engine()
        r = DeliveryReceipt(
            receipt_id="rcpt-1", message_id="msg-nope",
            status=DeliveryStatus.DELIVERED, channel_type=ChannelType.EMAIL,
            created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            e.record_receipt(r)
        assert "msg-nope" not in str(exc_info.value)

    # -- contact preferences --

    def test_set_and_get_contact_preference(self):
        e = self._engine()
        pref = ContactPreference(
            preference_id="pref-1", contact_id="c1",
            preferred_channels=(ChannelType.EMAIL,), created_at=NOW,
        )
        e.set_contact_preference(pref)
        assert e.get_contact_preference("c1") is pref

    def test_get_contact_preference_missing(self):
        e = self._engine()
        assert e.get_contact_preference("nope") is None

    # -- escalation preferences --

    def test_set_and_get_escalation_preference(self):
        e = self._engine()
        pref = EscalationPreference(
            preference_id="esc-1", contact_id="c1",
            escalation_chain=(ChannelType.EMAIL, ChannelType.SMS), created_at=NOW,
        )
        e.set_escalation_preference(pref)
        assert e.get_escalation_preference("c1") is pref

    # -- call sessions --

    def test_start_and_complete_call(self):
        e = self._engine()
        session = CallSession(
            session_id="call-1", conversation_id="conv-1",
            channel_type=ChannelType.VOICE,
            participant_ids=("p1", "p2"),
            state=CallSessionState.CONNECTED,
            started_at=NOW,
        )
        e.start_call_session(session)
        assert e.call_session_count == 1

        completed = e.complete_call_session(
            "call-1", CallSessionState.COMPLETED, LATER, 300,
        )
        assert completed.state == CallSessionState.COMPLETED
        assert completed.duration_seconds == 300

    def test_complete_missing_session_rejected(self):
        e = self._engine()
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            e.complete_call_session("nope", CallSessionState.COMPLETED, LATER, 0)
        assert "nope" not in str(exc_info.value)

    def test_complete_terminal_session_rejected(self):
        e = self._engine()
        session = CallSession(
            session_id="call-1", conversation_id="conv-1",
            channel_type=ChannelType.VOICE,
            participant_ids=("p1",),
            state=CallSessionState.COMPLETED,
            started_at=NOW, ended_at=LATER, duration_seconds=100,
        )
        e.start_call_session(session)
        with pytest.raises(RuntimeCoreInvariantError, match="terminal") as exc_info:
            e.complete_call_session("call-1", CallSessionState.FAILED, LATER, 0)
        assert "call-1" not in str(exc_info.value)
        assert "completed" not in str(exc_info.value).lower()

    # -- transcripts --

    def test_add_transcript(self):
        e = self._engine()
        e.start_call_session(CallSession(
            session_id="call-1", conversation_id="conv-1",
            channel_type=ChannelType.VOICE, participant_ids=("p1",),
            state=CallSessionState.CONNECTED, started_at=NOW,
        ))
        seg = TranscriptSegment(
            segment_id="seg-1", speaker_id="p1",
            text="Hello", started_at=NOW, ended_at=LATER,
        )
        tx = CallTranscript(
            transcript_id="tx-1", session_id="call-1",
            segments=(seg,), created_at=NOW,
        )
        e.add_transcript(tx)
        assert e.transcript_count == 1
        assert len(e.get_transcripts_for_session("call-1")) == 1

    def test_transcript_missing_session_rejected(self):
        e = self._engine()
        tx = CallTranscript(
            transcript_id="tx-1", session_id="nope",
            segments=(), created_at=NOW,
        )
        with pytest.raises(RuntimeCoreInvariantError, match="not found") as exc_info:
            e.add_transcript(tx)
        assert "nope" not in str(exc_info.value)

    # -- policy evaluation --

    def test_policy_allow(self):
        e = self._engine()
        pol = CommunicationPolicy(
            policy_id="pol-1", name="Standard",
            allowed_channels=(ChannelType.EMAIL, ChannelType.SMS),
            created_at=NOW,
        )
        e.register_policy(pol)
        decision = e.evaluate_policy("pol-1", ChannelType.EMAIL)
        assert decision.effect == CommunicationPolicyEffect.ALLOW
        assert decision.reason == "channel allowed"
        assert "Standard" not in decision.reason

    def test_policy_deny_explicit(self):
        e = self._engine()
        pol = CommunicationPolicy(
            policy_id="pol-1", name="Strict",
            allowed_channels=(ChannelType.EMAIL,),
            denied_channels=(ChannelType.FAX,),
            created_at=NOW,
        )
        e.register_policy(pol)
        decision = e.evaluate_policy("pol-1", ChannelType.FAX)
        assert decision.effect == CommunicationPolicyEffect.DENY
        assert decision.reason == "channel denied"
        assert "Strict" not in decision.reason
        assert "FAX" not in decision.reason

    def test_policy_deny_fail_closed(self):
        e = self._engine()
        pol = CommunicationPolicy(
            policy_id="pol-1", name="Limited",
            allowed_channels=(ChannelType.EMAIL,),
            created_at=NOW,
        )
        e.register_policy(pol)
        decision = e.evaluate_policy("pol-1", ChannelType.VOICE)
        assert decision.effect == CommunicationPolicyEffect.DENY
        assert decision.reason == "channel denied"
        assert "Limited" not in decision.reason
        assert "VOICE" not in decision.reason

    def test_policy_missing_fail_closed(self):
        e = self._engine()
        decision = e.evaluate_policy("nope", ChannelType.EMAIL)
        assert decision.effect == CommunicationPolicyEffect.DENY
        assert decision.reason == "no policy found"

    def test_policy_require_approval(self):
        e = self._engine()
        pol = CommunicationPolicy(
            policy_id="pol-1", name="Cautious",
            allowed_channels=(ChannelType.EMAIL,),
            require_approval_channels=(ChannelType.VOICE,),
            created_at=NOW,
        )
        e.register_policy(pol)
        decision = e.evaluate_policy("pol-1", ChannelType.VOICE)
        assert decision.effect == CommunicationPolicyEffect.REQUIRE_APPROVAL
        assert decision.reason == "channel requires approval"
        assert "Cautious" not in decision.reason
        assert "VOICE" not in decision.reason

    def test_policy_rate_limit_reason_is_bounded(self):
        e = self._engine()
        pol = CommunicationPolicy(
            policy_id="pol-1", name="Metered",
            allowed_channels=(ChannelType.EMAIL,),
            max_outbound_per_hour=1,
            created_at=NOW,
        )
        e.register_policy(pol)
        e.send_outbound(OutboundMessage(
            message_id="out-1",
            conversation_id="conv-1",
            channel_type=ChannelType.EMAIL,
            recipient_identity_id="id-1",
            body="hello",
            scheduled_at=NOW,
        ))
        decision = e.evaluate_policy("pol-1", ChannelType.EMAIL)
        assert decision.effect == CommunicationPolicyEffect.RATE_LIMITED
        assert decision.reason == "rate limit exceeded"
        assert "Metered" not in decision.reason
        assert "/" not in decision.reason

    # -- channel manifests --

    def test_register_and_get_manifest(self):
        e = self._engine()
        m = ChannelCapabilityManifest(
            manifest_id="man-1", channel_type=ChannelType.SMS,
            max_body_length=160, created_at=NOW,
        )
        e.register_channel_manifest(m)
        assert e.get_channel_manifest(ChannelType.SMS) is m

    # -- routing --

    def test_route_for_contact(self):
        e = self._engine()
        e.set_contact_preference(ContactPreference(
            preference_id="pref-1", contact_id="c1",
            preferred_channels=(ChannelType.SMS, ChannelType.EMAIL),
            created_at=NOW,
        ))
        assert e.route_for_contact("c1") == ChannelType.SMS

    def test_route_for_contact_missing(self):
        e = self._engine()
        assert e.route_for_contact("nope") is None

    def test_route_for_escalation(self):
        e = self._engine()
        e.set_escalation_preference(EscalationPreference(
            preference_id="esc-1", contact_id="c1",
            escalation_chain=(ChannelType.EMAIL, ChannelType.SMS, ChannelType.VOICE),
            created_at=NOW,
        ))
        chain = e.route_for_escalation("c1")
        assert chain == (ChannelType.EMAIL, ChannelType.SMS, ChannelType.VOICE)

    # -- state hash --

    def test_state_hash_deterministic(self):
        e = self._engine()
        e.register_identity(_identity("id-1"))
        h1 = e.state_hash()
        h2 = e.state_hash()
        assert h1 == h2

    def test_state_hash_changes(self):
        e = self._engine()
        h1 = e.state_hash()
        e.register_identity(_identity("id-1"))
        h2 = e.state_hash()
        assert h1 != h2
