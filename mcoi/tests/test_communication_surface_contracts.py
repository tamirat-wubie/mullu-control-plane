"""Contract-level tests for communication_surface contracts."""

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
    CommunicationPolicyDecision,
    CommunicationPolicyEffect,
    ContactPreference,
    ConversationHandle,
    DeliveryReceipt,
    DeliveryStatus,
    EscalationPreference,
    InboundMessage,
    MessageDirection,
    OutboundMessage,
    TranscriptSegment,
)

NOW = "2026-03-20T12:00:00+00:00"
LATER = "2026-03-21T12:00:00+00:00"


# ---------------------------------------------------------------------------
# ChannelIdentity
# ---------------------------------------------------------------------------


class TestChannelIdentity:
    def _make(self, **overrides):
        defaults = dict(
            identity_id="id-1",
            contact_id="contact-1",
            channel_type=ChannelType.EMAIL,
            address="user@example.com",
            created_at=NOW,
        )
        defaults.update(overrides)
        return ChannelIdentity(**defaults)

    def test_valid(self):
        ci = self._make()
        assert ci.channel_type == ChannelType.EMAIL
        assert ci.verified is False

    def test_empty_address_rejected(self):
        with pytest.raises(ValueError):
            self._make(address="")

    def test_invalid_channel_type(self):
        with pytest.raises(ValueError):
            self._make(channel_type="pigeon")

    def test_frozen(self):
        ci = self._make()
        with pytest.raises(AttributeError):
            ci.address = "new@example.com"

    def test_all_channel_types(self):
        for ct in ChannelType:
            ci = self._make(channel_type=ct)
            assert ci.channel_type == ct

    def test_serialization(self):
        d = self._make().to_dict()
        assert d["channel_type"] == "email"


# ---------------------------------------------------------------------------
# ConversationHandle
# ---------------------------------------------------------------------------


class TestConversationHandle:
    def _make(self, **overrides):
        defaults = dict(
            conversation_id="conv-1",
            subject="Test conversation",
            contact_ids=("c1",),
            channel_types=(ChannelType.EMAIL,),
            started_at=NOW,
        )
        defaults.update(overrides)
        return ConversationHandle(**defaults)

    def test_valid(self):
        ch = self._make()
        assert ch.conversation_id == "conv-1"

    def test_empty_contact_ids_rejected(self):
        with pytest.raises(ValueError):
            self._make(contact_ids=())

    def test_invalid_channel_type_in_list(self):
        with pytest.raises(ValueError):
            self._make(channel_types=("invalid",))

    def test_metadata_frozen(self):
        ch = self._make(metadata={"k": "v"})
        with pytest.raises(TypeError):
            ch.metadata["new"] = "val"


# ---------------------------------------------------------------------------
# InboundMessage
# ---------------------------------------------------------------------------


class TestInboundMessage:
    def _make(self, **overrides):
        defaults = dict(
            message_id="msg-in-1",
            conversation_id="conv-1",
            channel_type=ChannelType.SMS,
            sender_identity_id="id-1",
            body="Hello",
            received_at=NOW,
        )
        defaults.update(overrides)
        return InboundMessage(**defaults)

    def test_valid(self):
        m = self._make()
        assert m.channel_type == ChannelType.SMS

    def test_empty_body_rejected(self):
        with pytest.raises(ValueError):
            self._make(body="")

    def test_attachments_frozen(self):
        m = self._make(attachments=("file1.pdf",))
        assert isinstance(m.attachments, tuple)

    def test_raw_payload_frozen(self):
        m = self._make(raw_payload={"raw": True})
        with pytest.raises(TypeError):
            m.raw_payload["new"] = "val"


# ---------------------------------------------------------------------------
# OutboundMessage
# ---------------------------------------------------------------------------


class TestOutboundMessage:
    def _make(self, **overrides):
        defaults = dict(
            message_id="msg-out-1",
            conversation_id="conv-1",
            channel_type=ChannelType.EMAIL,
            recipient_identity_id="id-2",
            body="Greetings",
            scheduled_at=NOW,
        )
        defaults.update(overrides)
        return OutboundMessage(**defaults)

    def test_valid(self):
        m = self._make()
        assert m.sent_at is None

    def test_with_sent_at(self):
        m = self._make(sent_at=LATER)
        assert m.sent_at == LATER

    def test_bad_sent_at_rejected(self):
        with pytest.raises(ValueError):
            self._make(sent_at="not-a-date")

    def test_empty_recipient_rejected(self):
        with pytest.raises(ValueError):
            self._make(recipient_identity_id="")


# ---------------------------------------------------------------------------
# DeliveryReceipt
# ---------------------------------------------------------------------------


class TestDeliveryReceipt:
    def _make(self, **overrides):
        defaults = dict(
            receipt_id="rcpt-1",
            message_id="msg-out-1",
            status=DeliveryStatus.DELIVERED,
            channel_type=ChannelType.EMAIL,
            created_at=NOW,
        )
        defaults.update(overrides)
        return DeliveryReceipt(**defaults)

    def test_valid(self):
        r = self._make()
        assert r.status == DeliveryStatus.DELIVERED

    def test_all_delivery_statuses(self):
        for ds in DeliveryStatus:
            r = self._make(status=ds)
            assert r.status == ds

    def test_delivered_at_optional(self):
        r = self._make(delivered_at=LATER)
        assert r.delivered_at == LATER


# ---------------------------------------------------------------------------
# ContactPreference
# ---------------------------------------------------------------------------


class TestContactPreference:
    def _make(self, **overrides):
        defaults = dict(
            preference_id="pref-1",
            contact_id="c1",
            preferred_channels=(ChannelType.EMAIL, ChannelType.SMS),
            created_at=NOW,
        )
        defaults.update(overrides)
        return ContactPreference(**defaults)

    def test_valid(self):
        p = self._make()
        assert len(p.preferred_channels) == 2

    def test_blocked_channels(self):
        p = self._make(blocked_channels=(ChannelType.FAX,))
        assert ChannelType.FAX in p.blocked_channels

    def test_invalid_preferred_channel(self):
        with pytest.raises(ValueError):
            self._make(preferred_channels=("carrier_pigeon",))

    def test_invalid_blocked_channel(self):
        with pytest.raises(ValueError):
            self._make(blocked_channels=("smoke_signal",))


# ---------------------------------------------------------------------------
# EscalationPreference
# ---------------------------------------------------------------------------


class TestEscalationPreference:
    def _make(self, **overrides):
        defaults = dict(
            preference_id="esc-1",
            contact_id="c1",
            escalation_chain=(ChannelType.EMAIL, ChannelType.SMS, ChannelType.VOICE),
            created_at=NOW,
        )
        defaults.update(overrides)
        return EscalationPreference(**defaults)

    def test_valid(self):
        e = self._make()
        assert len(e.escalation_chain) == 3
        assert e.max_attempts_per_channel == 3

    def test_empty_chain_rejected(self):
        with pytest.raises(ValueError):
            self._make(escalation_chain=())

    def test_zero_max_attempts_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_attempts_per_channel=0)

    def test_zero_timeout_rejected(self):
        with pytest.raises(ValueError):
            self._make(escalation_timeout_seconds=0)


# ---------------------------------------------------------------------------
# CallSession
# ---------------------------------------------------------------------------


class TestCallSession:
    def _make(self, **overrides):
        defaults = dict(
            session_id="call-1",
            conversation_id="conv-1",
            channel_type=ChannelType.VOICE,
            participant_ids=("p1", "p2"),
            state=CallSessionState.RINGING,
            started_at=NOW,
        )
        defaults.update(overrides)
        return CallSession(**defaults)

    def test_valid(self):
        s = self._make()
        assert s.state == CallSessionState.RINGING

    def test_all_states(self):
        for st in CallSessionState:
            s = self._make(state=st)
            assert s.state == st

    def test_empty_participants_rejected(self):
        with pytest.raises(ValueError):
            self._make(participant_ids=())

    def test_with_duration(self):
        s = self._make(
            state=CallSessionState.COMPLETED,
            ended_at=LATER,
            duration_seconds=300,
        )
        assert s.duration_seconds == 300


# ---------------------------------------------------------------------------
# TranscriptSegment and CallTranscript
# ---------------------------------------------------------------------------


class TestTranscriptSegment:
    def _make(self, **overrides):
        defaults = dict(
            segment_id="seg-1",
            speaker_id="p1",
            text="Hello, how can I help?",
            started_at=NOW,
            ended_at=LATER,
        )
        defaults.update(overrides)
        return TranscriptSegment(**defaults)

    def test_valid(self):
        s = self._make()
        assert s.confidence == 1.0

    def test_empty_text_rejected(self):
        with pytest.raises(ValueError):
            self._make(text="")

    def test_confidence_out_of_range(self):
        with pytest.raises(ValueError):
            self._make(confidence=1.5)


class TestCallTranscript:
    def _make_segment(self):
        return TranscriptSegment(
            segment_id="seg-1",
            speaker_id="p1",
            text="Hello",
            started_at=NOW,
            ended_at=LATER,
        )

    def test_valid(self):
        t = CallTranscript(
            transcript_id="tx-1",
            session_id="call-1",
            segments=(self._make_segment(),),
            created_at=NOW,
        )
        assert t.language == "en"

    def test_invalid_segment_rejected(self):
        with pytest.raises(ValueError):
            CallTranscript(
                transcript_id="tx-1",
                session_id="call-1",
                segments=("not a segment",),
                created_at=NOW,
            )


# ---------------------------------------------------------------------------
# CommunicationPolicy
# ---------------------------------------------------------------------------


class TestCommunicationPolicy:
    def _make(self, **overrides):
        defaults = dict(
            policy_id="pol-1",
            name="Default policy",
            allowed_channels=(ChannelType.EMAIL, ChannelType.SMS),
            created_at=NOW,
        )
        defaults.update(overrides)
        return CommunicationPolicy(**defaults)

    def test_valid(self):
        p = self._make()
        assert len(p.allowed_channels) == 2

    def test_denied_channels(self):
        p = self._make(denied_channels=(ChannelType.FAX,))
        assert ChannelType.FAX in p.denied_channels

    def test_rate_limits(self):
        p = self._make(max_outbound_per_hour=10, max_outbound_per_day=100)
        assert p.max_outbound_per_hour == 10

    def test_zero_rate_limit_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_outbound_per_hour=0)

    def test_invalid_allowed_channel(self):
        with pytest.raises(ValueError):
            self._make(allowed_channels=("bad",))


# ---------------------------------------------------------------------------
# CommunicationPolicyDecision
# ---------------------------------------------------------------------------


class TestCommunicationPolicyDecision:
    def test_valid(self):
        d = CommunicationPolicyDecision(
            decision_id="cpd-1",
            policy_id="pol-1",
            channel_type=ChannelType.EMAIL,
            effect=CommunicationPolicyEffect.ALLOW,
            reason="Allowed by policy",
            evaluated_at=NOW,
        )
        assert d.effect == CommunicationPolicyEffect.ALLOW

    def test_all_effects(self):
        for eff in CommunicationPolicyEffect:
            d = CommunicationPolicyDecision(
                decision_id=f"cpd-{eff.value}",
                policy_id="pol-1",
                channel_type=ChannelType.EMAIL,
                effect=eff,
                reason="test",
                evaluated_at=NOW,
            )
            assert d.effect == eff


# ---------------------------------------------------------------------------
# ChannelCapabilityManifest
# ---------------------------------------------------------------------------


class TestChannelCapabilityManifest:
    def _make(self, **overrides):
        defaults = dict(
            manifest_id="man-1",
            channel_type=ChannelType.EMAIL,
            supports_attachments=True,
            supports_threading=True,
            supports_rich_text=True,
            created_at=NOW,
        )
        defaults.update(overrides)
        return ChannelCapabilityManifest(**defaults)

    def test_valid(self):
        m = self._make()
        assert m.supports_attachments is True

    def test_max_body_length(self):
        m = self._make(max_body_length=160)
        assert m.max_body_length == 160

    def test_zero_body_length_rejected(self):
        with pytest.raises(ValueError):
            self._make(max_body_length=0)

    def test_capabilities_frozen(self):
        m = self._make(capabilities={"realtime": True})
        with pytest.raises(TypeError):
            m.capabilities["new"] = "val"

    def test_non_boolean_support_flag_is_bounded(self):
        with pytest.raises(ValueError) as exc:
            self._make(supports_attachments="yes")
        assert str(exc.value) == "value must be a boolean flag"
        assert "supports_attachments" not in str(exc.value)
        assert "yes" not in str(exc.value)


# ---------------------------------------------------------------------------
# Enum coverage
# ---------------------------------------------------------------------------


class TestEnumCoverage:
    def test_channel_type_count(self):
        assert len(ChannelType) == 8

    def test_message_direction_count(self):
        assert len(MessageDirection) == 2

    def test_delivery_status_count(self):
        assert len(DeliveryStatus) == 6

    def test_call_session_state_count(self):
        assert len(CallSessionState) == 7

    def test_communication_policy_effect_count(self):
        assert len(CommunicationPolicyEffect) == 4
