"""Tests for multimodal / voice / presence runtime contracts."""

from __future__ import annotations

import dataclasses
import math
from dataclasses import FrozenInstanceError
from types import MappingProxyType

import pytest

from mcoi_runtime.contracts.multimodal_runtime import (
    ConversationAttentionLevel,
    InteractionMode,
    InterruptionRecord,
    InterruptionStatus,
    MultimodalClosureReport,
    MultimodalDecision,
    MultimodalSnapshot,
    MultimodalViolation,
    PresenceRecord,
    PresenceStatus,
    SessionChannel,
    SpeechDisposition,
    SpeechTurn,
    StreamingTranscript,
    VoiceActionPlan,
    VoiceSession,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TS = "2025-06-01T12:00:00+00:00"
TS2 = "2025-06-15T09:00:00+00:00"


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def _voice_session(**ov) -> VoiceSession:
    d = dict(
        session_id="vs-001", tenant_id="t-1", identity_ref="user-1",
        copilot_session_ref="cop-1", mode=InteractionMode.VOICE,
        channel=SessionChannel.WEB, status="active", started_at=TS,
    )
    d.update(ov)
    return VoiceSession(**d)


def _presence(**ov) -> PresenceRecord:
    d = dict(
        presence_id="pr-001", tenant_id="t-1", identity_ref="user-1",
        status=PresenceStatus.AVAILABLE,
        attention=ConversationAttentionLevel.FOCUSED, updated_at=TS,
    )
    d.update(ov)
    return PresenceRecord(**d)


def _speech_turn(**ov) -> SpeechTurn:
    d = dict(
        turn_id="turn-001", tenant_id="t-1", session_ref="vs-001",
        speaker_ref="user-1", content="hello",
        disposition=SpeechDisposition.CAPTURED, duration_ms=0.0,
        captured_at=TS,
    )
    d.update(ov)
    return SpeechTurn(**d)


def _transcript(**ov) -> StreamingTranscript:
    d = dict(
        transcript_id="tr-001", tenant_id="t-1", session_ref="vs-001",
        content="hello world", is_final=False, confidence=1.0,
        captured_at=TS,
    )
    d.update(ov)
    return StreamingTranscript(**d)


def _action_plan(**ov) -> VoiceActionPlan:
    d = dict(
        plan_id="plan-001", tenant_id="t-1", session_ref="vs-001",
        intent_summary="navigate", target_runtime="copilot",
        disposition="allowed", created_at=TS,
    )
    d.update(ov)
    return VoiceActionPlan(**d)


def _interruption(**ov) -> InterruptionRecord:
    d = dict(
        interruption_id="int-001", tenant_id="t-1", session_ref="vs-001",
        status=InterruptionStatus.DETECTED, reason="user spoke",
        detected_at=TS,
    )
    d.update(ov)
    return InterruptionRecord(**d)


def _decision(**ov) -> MultimodalDecision:
    d = dict(
        decision_id="dec-001", tenant_id="t-1", session_ref="vs-001",
        disposition="approved", reason="policy ok", decided_at=TS,
    )
    d.update(ov)
    return MultimodalDecision(**d)


def _snapshot(**ov) -> MultimodalSnapshot:
    d = dict(
        snapshot_id="snap-001", tenant_id="t-1",
        total_sessions=1, total_turns=2, total_transcripts=3,
        total_interruptions=0, total_violations=0, captured_at=TS,
    )
    d.update(ov)
    return MultimodalSnapshot(**d)


def _violation(**ov) -> MultimodalViolation:
    d = dict(
        violation_id="viol-001", tenant_id="t-1",
        operation="session_no_turns", reason="no turns", detected_at=TS,
    )
    d.update(ov)
    return MultimodalViolation(**d)


def _closure(**ov) -> MultimodalClosureReport:
    d = dict(
        report_id="rpt-001", tenant_id="t-1",
        total_sessions=1, total_turns=2, total_transcripts=3,
        total_interruptions=0, total_violations=0, created_at=TS,
    )
    d.update(ov)
    return MultimodalClosureReport(**d)


# =========================================================================
# Enum tests
# =========================================================================


class TestInteractionMode:
    def test_values(self):
        assert InteractionMode.VOICE.value == "voice"
        assert InteractionMode.TEXT.value == "text"
        assert InteractionMode.HYBRID.value == "hybrid"
        assert InteractionMode.STREAMING.value == "streaming"

    def test_member_count(self):
        assert len(InteractionMode) == 4

    def test_identity(self):
        assert InteractionMode("voice") is InteractionMode.VOICE

    def test_invalid(self):
        with pytest.raises(ValueError):
            InteractionMode("invalid")

    def test_name(self):
        assert InteractionMode.VOICE.name == "VOICE"

    def test_iteration(self):
        names = {m.name for m in InteractionMode}
        assert names == {"VOICE", "TEXT", "HYBRID", "STREAMING"}


class TestSessionChannel:
    def test_values(self):
        assert SessionChannel.PHONE.value == "phone"
        assert SessionChannel.WEB.value == "web"
        assert SessionChannel.CHAT.value == "chat"
        assert SessionChannel.API.value == "api"
        assert SessionChannel.IN_PERSON.value == "in_person"

    def test_member_count(self):
        assert len(SessionChannel) == 5

    def test_identity(self):
        assert SessionChannel("web") is SessionChannel.WEB

    def test_invalid(self):
        with pytest.raises(ValueError):
            SessionChannel("zoom")


class TestPresenceStatus:
    def test_values(self):
        assert PresenceStatus.AVAILABLE.value == "available"
        assert PresenceStatus.BUSY.value == "busy"
        assert PresenceStatus.AWAY.value == "away"
        assert PresenceStatus.DO_NOT_DISTURB.value == "do_not_disturb"
        assert PresenceStatus.OFFLINE.value == "offline"

    def test_member_count(self):
        assert len(PresenceStatus) == 5

    def test_identity(self):
        assert PresenceStatus("offline") is PresenceStatus.OFFLINE

    def test_invalid(self):
        with pytest.raises(ValueError):
            PresenceStatus("invisible")


class TestSpeechDisposition:
    def test_values(self):
        assert SpeechDisposition.CAPTURED.value == "captured"
        assert SpeechDisposition.TRANSCRIBED.value == "transcribed"
        assert SpeechDisposition.PROCESSED.value == "processed"
        assert SpeechDisposition.FAILED.value == "failed"

    def test_member_count(self):
        assert len(SpeechDisposition) == 4

    def test_identity(self):
        assert SpeechDisposition("failed") is SpeechDisposition.FAILED


class TestInterruptionStatus:
    def test_values(self):
        assert InterruptionStatus.DETECTED.value == "detected"
        assert InterruptionStatus.ACKNOWLEDGED.value == "acknowledged"
        assert InterruptionStatus.RESUMED.value == "resumed"
        assert InterruptionStatus.DISMISSED.value == "dismissed"

    def test_member_count(self):
        assert len(InterruptionStatus) == 4

    def test_identity(self):
        assert InterruptionStatus("resumed") is InterruptionStatus.RESUMED


class TestConversationAttentionLevel:
    def test_values(self):
        assert ConversationAttentionLevel.FOCUSED.value == "focused"
        assert ConversationAttentionLevel.PASSIVE.value == "passive"
        assert ConversationAttentionLevel.BACKGROUND.value == "background"
        assert ConversationAttentionLevel.DORMANT.value == "dormant"

    def test_member_count(self):
        assert len(ConversationAttentionLevel) == 4

    def test_identity(self):
        assert ConversationAttentionLevel("dormant") is ConversationAttentionLevel.DORMANT


# =========================================================================
# VoiceSession
# =========================================================================


class TestVoiceSession:
    def test_basic_creation(self):
        s = _voice_session()
        assert s.session_id == "vs-001"
        assert s.tenant_id == "t-1"
        assert s.mode is InteractionMode.VOICE
        assert s.channel is SessionChannel.WEB
        assert s.status == "active"

    def test_frozen(self):
        s = _voice_session()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "session_id", "changed")
        # frozen dataclass blocks setattr through normal path
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "session_id", "changed")

    def test_slots(self):
        assert hasattr(VoiceSession, "__slots__")

    def test_empty_session_id_rejected(self):
        with pytest.raises(ValueError):
            _voice_session(session_id="")

    def test_whitespace_session_id_rejected(self):
        with pytest.raises(ValueError):
            _voice_session(session_id="   ")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _voice_session(tenant_id="")

    def test_empty_identity_ref_rejected(self):
        with pytest.raises(ValueError):
            _voice_session(identity_ref="")

    def test_empty_copilot_ref_rejected(self):
        with pytest.raises(ValueError):
            _voice_session(copilot_session_ref="")

    def test_empty_status_rejected(self):
        with pytest.raises(ValueError):
            _voice_session(status="")

    def test_invalid_mode_type(self):
        with pytest.raises(ValueError):
            _voice_session(mode="voice")

    def test_invalid_channel_type(self):
        with pytest.raises(ValueError):
            _voice_session(channel="web")

    def test_invalid_started_at(self):
        with pytest.raises(ValueError):
            _voice_session(started_at="not-a-date")

    def test_empty_started_at(self):
        with pytest.raises(ValueError):
            _voice_session(started_at="")

    def test_all_modes(self):
        for m in InteractionMode:
            s = _voice_session(mode=m)
            assert s.mode is m

    def test_all_channels(self):
        for c in SessionChannel:
            s = _voice_session(channel=c)
            assert s.channel is c

    def test_metadata_frozen(self):
        s = _voice_session(metadata={"key": "val"})
        assert isinstance(s.metadata, MappingProxyType)

    def test_metadata_nested_frozen(self):
        s = _voice_session(metadata={"nested": {"a": 1}})
        assert isinstance(s.metadata["nested"], MappingProxyType)

    def test_metadata_empty_default(self):
        s = _voice_session()
        assert isinstance(s.metadata, MappingProxyType)
        assert len(s.metadata) == 0

    def test_to_dict(self):
        s = _voice_session()
        d = s.to_dict()
        assert isinstance(d, dict)
        assert d["session_id"] == "vs-001"
        assert d["mode"] is InteractionMode.VOICE

    def test_to_json_dict(self):
        s = _voice_session()
        d = s.to_json_dict()
        assert d["mode"] == "voice"
        assert d["channel"] == "web"

    def test_to_json(self):
        s = _voice_session()
        j = s.to_json()
        assert isinstance(j, str)
        assert '"vs-001"' in j

    def test_equality(self):
        a = _voice_session()
        b = _voice_session()
        assert a == b

    def test_inequality(self):
        a = _voice_session()
        b = _voice_session(session_id="vs-002")
        assert a != b

    def test_dataclass_fields(self):
        names = [f.name for f in dataclasses.fields(VoiceSession)]
        assert "session_id" in names
        assert "metadata" in names

    def test_non_int_session_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            _voice_session(session_id=123)

    def test_status_paused(self):
        s = _voice_session(status="paused")
        assert s.status == "paused"

    def test_status_ended(self):
        s = _voice_session(status="ended")
        assert s.status == "ended"

    def test_repr_contains_session_id(self):
        s = _voice_session()
        assert "vs-001" in repr(s)


# =========================================================================
# PresenceRecord
# =========================================================================


class TestPresenceRecord:
    def test_basic_creation(self):
        p = _presence()
        assert p.presence_id == "pr-001"
        assert p.status is PresenceStatus.AVAILABLE
        assert p.attention is ConversationAttentionLevel.FOCUSED

    def test_frozen(self):
        p = _presence()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "presence_id", "changed")

    def test_slots(self):
        assert hasattr(PresenceRecord, "__slots__")

    def test_empty_presence_id_rejected(self):
        with pytest.raises(ValueError):
            _presence(presence_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _presence(tenant_id="")

    def test_empty_identity_ref_rejected(self):
        with pytest.raises(ValueError):
            _presence(identity_ref="")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            _presence(status="available")

    def test_invalid_attention_type(self):
        with pytest.raises(ValueError):
            _presence(attention="focused")

    def test_invalid_updated_at(self):
        with pytest.raises(ValueError):
            _presence(updated_at="bad")

    def test_empty_updated_at(self):
        with pytest.raises(ValueError):
            _presence(updated_at="")

    def test_all_statuses(self):
        for ps in PresenceStatus:
            p = _presence(status=ps)
            assert p.status is ps

    def test_all_attentions(self):
        for a in ConversationAttentionLevel:
            p = _presence(attention=a)
            assert p.attention is a

    def test_metadata_frozen(self):
        p = _presence(metadata={"key": "val"})
        assert isinstance(p.metadata, MappingProxyType)

    def test_to_dict(self):
        p = _presence()
        d = p.to_dict()
        assert d["presence_id"] == "pr-001"
        assert d["status"] is PresenceStatus.AVAILABLE

    def test_to_json_dict(self):
        p = _presence()
        d = p.to_json_dict()
        assert d["status"] == "available"
        assert d["attention"] == "focused"

    def test_to_json(self):
        p = _presence()
        j = p.to_json()
        assert '"pr-001"' in j

    def test_equality(self):
        assert _presence() == _presence()

    def test_inequality(self):
        assert _presence() != _presence(presence_id="pr-002")

    def test_whitespace_presence_id_rejected(self):
        with pytest.raises(ValueError):
            _presence(presence_id="   ")

    def test_whitespace_identity_ref_rejected(self):
        with pytest.raises(ValueError):
            _presence(identity_ref="   ")

    def test_repr_contains_id(self):
        p = _presence()
        assert "pr-001" in repr(p)


# =========================================================================
# SpeechTurn
# =========================================================================


class TestSpeechTurn:
    def test_basic_creation(self):
        t = _speech_turn()
        assert t.turn_id == "turn-001"
        assert t.content == "hello"
        assert t.duration_ms == 0.0
        assert t.disposition is SpeechDisposition.CAPTURED

    def test_frozen(self):
        t = _speech_turn()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(t, "turn_id", "changed")

    def test_slots(self):
        assert hasattr(SpeechTurn, "__slots__")

    def test_empty_turn_id_rejected(self):
        with pytest.raises(ValueError):
            _speech_turn(turn_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _speech_turn(tenant_id="")

    def test_empty_session_ref_rejected(self):
        with pytest.raises(ValueError):
            _speech_turn(session_ref="")

    def test_empty_speaker_ref_rejected(self):
        with pytest.raises(ValueError):
            _speech_turn(speaker_ref="")

    def test_empty_content_rejected(self):
        with pytest.raises(ValueError):
            _speech_turn(content="")

    def test_invalid_disposition_type(self):
        with pytest.raises(ValueError):
            _speech_turn(disposition="captured")

    def test_negative_duration_ms_rejected(self):
        with pytest.raises(ValueError):
            _speech_turn(duration_ms=-1.0)

    def test_duration_ms_nan_rejected(self):
        with pytest.raises(ValueError):
            _speech_turn(duration_ms=float("nan"))

    def test_duration_ms_inf_rejected(self):
        with pytest.raises(ValueError):
            _speech_turn(duration_ms=float("inf"))

    def test_duration_ms_zero(self):
        t = _speech_turn(duration_ms=0.0)
        assert t.duration_ms == 0.0

    def test_duration_ms_positive(self):
        t = _speech_turn(duration_ms=1500.0)
        assert t.duration_ms == 1500.0

    def test_duration_ms_int_coerced(self):
        t = _speech_turn(duration_ms=100)
        assert t.duration_ms == 100.0

    def test_duration_ms_bool_rejected(self):
        with pytest.raises(ValueError):
            _speech_turn(duration_ms=True)

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _speech_turn(captured_at="bad")

    def test_all_dispositions(self):
        for disp in SpeechDisposition:
            t = _speech_turn(disposition=disp)
            assert t.disposition is disp

    def test_metadata_frozen(self):
        t = _speech_turn(metadata={"key": "val"})
        assert isinstance(t.metadata, MappingProxyType)

    def test_to_dict(self):
        t = _speech_turn()
        d = t.to_dict()
        assert d["turn_id"] == "turn-001"
        assert d["disposition"] is SpeechDisposition.CAPTURED

    def test_to_json_dict(self):
        t = _speech_turn()
        d = t.to_json_dict()
        assert d["disposition"] == "captured"

    def test_to_json(self):
        t = _speech_turn()
        j = t.to_json()
        assert '"turn-001"' in j

    def test_equality(self):
        assert _speech_turn() == _speech_turn()

    def test_inequality(self):
        assert _speech_turn() != _speech_turn(turn_id="turn-002")

    def test_duration_ms_large_value(self):
        t = _speech_turn(duration_ms=999999.99)
        assert t.duration_ms == 999999.99

    def test_whitespace_content_rejected(self):
        with pytest.raises(ValueError):
            _speech_turn(content="   ")


# =========================================================================
# StreamingTranscript
# =========================================================================


class TestStreamingTranscript:
    def test_basic_creation(self):
        t = _transcript()
        assert t.transcript_id == "tr-001"
        assert t.is_final is False
        assert t.confidence == 1.0

    def test_frozen(self):
        t = _transcript()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(t, "transcript_id", "changed")

    def test_slots(self):
        assert hasattr(StreamingTranscript, "__slots__")

    def test_empty_transcript_id_rejected(self):
        with pytest.raises(ValueError):
            _transcript(transcript_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _transcript(tenant_id="")

    def test_empty_session_ref_rejected(self):
        with pytest.raises(ValueError):
            _transcript(session_ref="")

    def test_empty_content_rejected(self):
        with pytest.raises(ValueError):
            _transcript(content="")

    def test_is_final_true(self):
        t = _transcript(is_final=True)
        assert t.is_final is True

    def test_is_final_false(self):
        t = _transcript(is_final=False)
        assert t.is_final is False

    def test_is_final_int_rejected(self):
        with pytest.raises(ValueError):
            _transcript(is_final=1)

    def test_is_final_zero_rejected(self):
        with pytest.raises(ValueError):
            _transcript(is_final=0)

    def test_is_final_str_rejected(self):
        with pytest.raises(ValueError):
            _transcript(is_final="true")

    def test_is_final_none_rejected(self):
        with pytest.raises(ValueError):
            _transcript(is_final=None)

    def test_confidence_zero(self):
        t = _transcript(confidence=0.0)
        assert t.confidence == 0.0

    def test_confidence_one(self):
        t = _transcript(confidence=1.0)
        assert t.confidence == 1.0

    def test_confidence_mid(self):
        t = _transcript(confidence=0.5)
        assert t.confidence == 0.5

    def test_confidence_negative_rejected(self):
        with pytest.raises(ValueError):
            _transcript(confidence=-0.1)

    def test_confidence_over_one_rejected(self):
        with pytest.raises(ValueError):
            _transcript(confidence=1.01)

    def test_confidence_nan_rejected(self):
        with pytest.raises(ValueError):
            _transcript(confidence=float("nan"))

    def test_confidence_inf_rejected(self):
        with pytest.raises(ValueError):
            _transcript(confidence=float("inf"))

    def test_confidence_bool_rejected(self):
        with pytest.raises(ValueError):
            _transcript(confidence=True)

    def test_confidence_int_accepted(self):
        t = _transcript(confidence=1)
        assert t.confidence == 1.0

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _transcript(captured_at="bad")

    def test_metadata_frozen(self):
        t = _transcript(metadata={"k": "v"})
        assert isinstance(t.metadata, MappingProxyType)

    def test_to_dict(self):
        t = _transcript()
        d = t.to_dict()
        assert d["transcript_id"] == "tr-001"
        assert d["is_final"] is False

    def test_to_json_dict(self):
        t = _transcript()
        d = t.to_json_dict()
        assert d["confidence"] == 1.0

    def test_to_json(self):
        t = _transcript()
        j = t.to_json()
        assert '"tr-001"' in j

    def test_equality(self):
        assert _transcript() == _transcript()

    def test_inequality(self):
        assert _transcript() != _transcript(transcript_id="tr-002")

    def test_whitespace_content_rejected(self):
        with pytest.raises(ValueError):
            _transcript(content="   ")


# =========================================================================
# VoiceActionPlan
# =========================================================================


class TestVoiceActionPlan:
    def test_basic_creation(self):
        p = _action_plan()
        assert p.plan_id == "plan-001"
        assert p.intent_summary == "navigate"
        assert p.target_runtime == "copilot"
        assert p.disposition == "allowed"

    def test_frozen(self):
        p = _action_plan()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(p, "plan_id", "changed")

    def test_slots(self):
        assert hasattr(VoiceActionPlan, "__slots__")

    def test_empty_plan_id_rejected(self):
        with pytest.raises(ValueError):
            _action_plan(plan_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _action_plan(tenant_id="")

    def test_empty_session_ref_rejected(self):
        with pytest.raises(ValueError):
            _action_plan(session_ref="")

    def test_empty_intent_summary_rejected(self):
        with pytest.raises(ValueError):
            _action_plan(intent_summary="")

    def test_empty_target_runtime_rejected(self):
        with pytest.raises(ValueError):
            _action_plan(target_runtime="")

    def test_empty_disposition_rejected(self):
        with pytest.raises(ValueError):
            _action_plan(disposition="")

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _action_plan(created_at="bad")

    def test_metadata_frozen(self):
        p = _action_plan(metadata={"a": "b"})
        assert isinstance(p.metadata, MappingProxyType)

    def test_to_dict(self):
        p = _action_plan()
        d = p.to_dict()
        assert d["plan_id"] == "plan-001"

    def test_to_json_dict(self):
        p = _action_plan()
        d = p.to_json_dict()
        assert d["disposition"] == "allowed"

    def test_to_json(self):
        p = _action_plan()
        j = p.to_json()
        assert '"plan-001"' in j

    def test_equality(self):
        assert _action_plan() == _action_plan()

    def test_inequality(self):
        assert _action_plan() != _action_plan(plan_id="plan-002")

    def test_disposition_blocked(self):
        p = _action_plan(disposition="blocked")
        assert p.disposition == "blocked"

    def test_whitespace_plan_id_rejected(self):
        with pytest.raises(ValueError):
            _action_plan(plan_id="   ")


# =========================================================================
# InterruptionRecord
# =========================================================================


class TestInterruptionRecord:
    def test_basic_creation(self):
        r = _interruption()
        assert r.interruption_id == "int-001"
        assert r.status is InterruptionStatus.DETECTED

    def test_frozen(self):
        r = _interruption()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(r, "interruption_id", "changed")

    def test_slots(self):
        assert hasattr(InterruptionRecord, "__slots__")

    def test_empty_interruption_id_rejected(self):
        with pytest.raises(ValueError):
            _interruption(interruption_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _interruption(tenant_id="")

    def test_empty_session_ref_rejected(self):
        with pytest.raises(ValueError):
            _interruption(session_ref="")

    def test_invalid_status_type(self):
        with pytest.raises(ValueError):
            _interruption(status="detected")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            _interruption(reason="")

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            _interruption(detected_at="bad")

    def test_all_statuses(self):
        for st in InterruptionStatus:
            r = _interruption(status=st)
            assert r.status is st

    def test_metadata_frozen(self):
        r = _interruption(metadata={"k": "v"})
        assert isinstance(r.metadata, MappingProxyType)

    def test_to_dict(self):
        r = _interruption()
        d = r.to_dict()
        assert d["interruption_id"] == "int-001"
        assert d["status"] is InterruptionStatus.DETECTED

    def test_to_json_dict(self):
        r = _interruption()
        d = r.to_json_dict()
        assert d["status"] == "detected"

    def test_to_json(self):
        r = _interruption()
        j = r.to_json()
        assert '"int-001"' in j

    def test_equality(self):
        assert _interruption() == _interruption()

    def test_inequality(self):
        assert _interruption() != _interruption(interruption_id="int-002")

    def test_whitespace_reason_rejected(self):
        with pytest.raises(ValueError):
            _interruption(reason="   ")


# =========================================================================
# MultimodalDecision
# =========================================================================


class TestMultimodalDecision:
    def test_basic_creation(self):
        d = _decision()
        assert d.decision_id == "dec-001"
        assert d.disposition == "approved"
        assert d.reason == "policy ok"

    def test_frozen(self):
        d = _decision()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(d, "decision_id", "changed")

    def test_slots(self):
        assert hasattr(MultimodalDecision, "__slots__")

    def test_empty_decision_id_rejected(self):
        with pytest.raises(ValueError):
            _decision(decision_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _decision(tenant_id="")

    def test_empty_session_ref_rejected(self):
        with pytest.raises(ValueError):
            _decision(session_ref="")

    def test_empty_disposition_rejected(self):
        with pytest.raises(ValueError):
            _decision(disposition="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            _decision(reason="")

    def test_invalid_decided_at(self):
        with pytest.raises(ValueError):
            _decision(decided_at="bad")

    def test_metadata_frozen(self):
        d = _decision(metadata={"k": "v"})
        assert isinstance(d.metadata, MappingProxyType)

    def test_to_dict(self):
        d = _decision()
        dd = d.to_dict()
        assert dd["decision_id"] == "dec-001"

    def test_to_json_dict(self):
        d = _decision()
        dd = d.to_json_dict()
        assert dd["disposition"] == "approved"

    def test_to_json(self):
        d = _decision()
        j = d.to_json()
        assert '"dec-001"' in j

    def test_equality(self):
        assert _decision() == _decision()

    def test_inequality(self):
        assert _decision() != _decision(decision_id="dec-002")

    def test_disposition_denied(self):
        d = _decision(disposition="denied")
        assert d.disposition == "denied"

    def test_whitespace_decision_id_rejected(self):
        with pytest.raises(ValueError):
            _decision(decision_id="   ")


# =========================================================================
# MultimodalSnapshot
# =========================================================================


class TestMultimodalSnapshot:
    def test_basic_creation(self):
        s = _snapshot()
        assert s.snapshot_id == "snap-001"
        assert s.total_sessions == 1
        assert s.total_turns == 2
        assert s.total_transcripts == 3

    def test_frozen(self):
        s = _snapshot()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(s, "snapshot_id", "changed")

    def test_slots(self):
        assert hasattr(MultimodalSnapshot, "__slots__")

    def test_empty_snapshot_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(snapshot_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(tenant_id="")

    def test_negative_total_sessions_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_sessions=-1)

    def test_negative_total_turns_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_turns=-1)

    def test_negative_total_transcripts_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_transcripts=-1)

    def test_negative_total_interruptions_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_interruptions=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_violations=-1)

    def test_zero_counts(self):
        s = _snapshot(total_sessions=0, total_turns=0, total_transcripts=0,
                      total_interruptions=0, total_violations=0)
        assert s.total_sessions == 0

    def test_float_total_sessions_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_sessions=1.5)

    def test_bool_total_sessions_rejected(self):
        with pytest.raises(ValueError):
            _snapshot(total_sessions=True)

    def test_invalid_captured_at(self):
        with pytest.raises(ValueError):
            _snapshot(captured_at="bad")

    def test_metadata_frozen(self):
        s = _snapshot(metadata={"k": "v"})
        assert isinstance(s.metadata, MappingProxyType)

    def test_to_dict(self):
        s = _snapshot()
        d = s.to_dict()
        assert d["snapshot_id"] == "snap-001"
        assert d["total_sessions"] == 1

    def test_to_json_dict(self):
        s = _snapshot()
        d = s.to_json_dict()
        assert d["total_turns"] == 2

    def test_to_json(self):
        s = _snapshot()
        j = s.to_json()
        assert '"snap-001"' in j

    def test_equality(self):
        assert _snapshot() == _snapshot()

    def test_inequality(self):
        assert _snapshot() != _snapshot(snapshot_id="snap-002")


# =========================================================================
# MultimodalViolation
# =========================================================================


class TestMultimodalViolation:
    def test_basic_creation(self):
        v = _violation()
        assert v.violation_id == "viol-001"
        assert v.operation == "session_no_turns"

    def test_frozen(self):
        v = _violation()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(v, "violation_id", "changed")

    def test_slots(self):
        assert hasattr(MultimodalViolation, "__slots__")

    def test_empty_violation_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(violation_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _violation(tenant_id="")

    def test_empty_operation_rejected(self):
        with pytest.raises(ValueError):
            _violation(operation="")

    def test_empty_reason_rejected(self):
        with pytest.raises(ValueError):
            _violation(reason="")

    def test_invalid_detected_at(self):
        with pytest.raises(ValueError):
            _violation(detected_at="bad")

    def test_metadata_frozen(self):
        v = _violation(metadata={"k": "v"})
        assert isinstance(v.metadata, MappingProxyType)

    def test_to_dict(self):
        v = _violation()
        d = v.to_dict()
        assert d["violation_id"] == "viol-001"

    def test_to_json_dict(self):
        v = _violation()
        d = v.to_json_dict()
        assert d["operation"] == "session_no_turns"

    def test_to_json(self):
        v = _violation()
        j = v.to_json()
        assert '"viol-001"' in j

    def test_equality(self):
        assert _violation() == _violation()

    def test_inequality(self):
        assert _violation() != _violation(violation_id="viol-002")

    def test_whitespace_operation_rejected(self):
        with pytest.raises(ValueError):
            _violation(operation="   ")


# =========================================================================
# MultimodalClosureReport
# =========================================================================


class TestMultimodalClosureReport:
    def test_basic_creation(self):
        c = _closure()
        assert c.report_id == "rpt-001"
        assert c.total_sessions == 1
        assert c.total_turns == 2

    def test_frozen(self):
        c = _closure()
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(c, "report_id", "changed")

    def test_slots(self):
        assert hasattr(MultimodalClosureReport, "__slots__")

    def test_empty_report_id_rejected(self):
        with pytest.raises(ValueError):
            _closure(report_id="")

    def test_empty_tenant_id_rejected(self):
        with pytest.raises(ValueError):
            _closure(tenant_id="")

    def test_negative_total_sessions_rejected(self):
        with pytest.raises(ValueError):
            _closure(total_sessions=-1)

    def test_negative_total_turns_rejected(self):
        with pytest.raises(ValueError):
            _closure(total_turns=-1)

    def test_negative_total_transcripts_rejected(self):
        with pytest.raises(ValueError):
            _closure(total_transcripts=-1)

    def test_negative_total_interruptions_rejected(self):
        with pytest.raises(ValueError):
            _closure(total_interruptions=-1)

    def test_negative_total_violations_rejected(self):
        with pytest.raises(ValueError):
            _closure(total_violations=-1)

    def test_zero_counts(self):
        c = _closure(total_sessions=0, total_turns=0, total_transcripts=0,
                     total_interruptions=0, total_violations=0)
        assert c.total_sessions == 0

    def test_float_total_rejected(self):
        with pytest.raises(ValueError):
            _closure(total_sessions=1.5)

    def test_bool_total_rejected(self):
        with pytest.raises(ValueError):
            _closure(total_sessions=True)

    def test_invalid_created_at(self):
        with pytest.raises(ValueError):
            _closure(created_at="bad")

    def test_metadata_frozen(self):
        c = _closure(metadata={"k": "v"})
        assert isinstance(c.metadata, MappingProxyType)

    def test_to_dict(self):
        c = _closure()
        d = c.to_dict()
        assert d["report_id"] == "rpt-001"

    def test_to_json_dict(self):
        c = _closure()
        d = c.to_json_dict()
        assert d["total_sessions"] == 1

    def test_to_json(self):
        c = _closure()
        j = c.to_json()
        assert '"rpt-001"' in j

    def test_equality(self):
        assert _closure() == _closure()

    def test_inequality(self):
        assert _closure() != _closure(report_id="rpt-002")

    def test_whitespace_report_id_rejected(self):
        with pytest.raises(ValueError):
            _closure(report_id="   ")

    def test_large_counts(self):
        c = _closure(total_sessions=10000, total_turns=50000)
        assert c.total_sessions == 10000
        assert c.total_turns == 50000


# =========================================================================
# Cross-contract edge cases
# =========================================================================


class TestCrossContractEdgeCases:
    """Tests spanning multiple contract types for consistency."""

    def test_all_contracts_are_frozen(self):
        classes = [
            VoiceSession, PresenceRecord, SpeechTurn, StreamingTranscript,
            VoiceActionPlan, InterruptionRecord, MultimodalDecision,
            MultimodalSnapshot, MultimodalViolation, MultimodalClosureReport,
        ]
        for cls in classes:
            assert dataclasses.fields(cls)  # is a dataclass
            # frozen=True is encoded in __dataclass_params__
            assert cls.__dataclass_params__.frozen is True

    def test_all_contracts_have_slots(self):
        classes = [
            VoiceSession, PresenceRecord, SpeechTurn, StreamingTranscript,
            VoiceActionPlan, InterruptionRecord, MultimodalDecision,
            MultimodalSnapshot, MultimodalViolation, MultimodalClosureReport,
        ]
        for cls in classes:
            assert hasattr(cls, "__slots__")

    def test_all_contracts_have_to_dict(self):
        instances = [
            _voice_session(), _presence(), _speech_turn(), _transcript(),
            _action_plan(), _interruption(), _decision(), _snapshot(),
            _violation(), _closure(),
        ]
        for inst in instances:
            d = inst.to_dict()
            assert isinstance(d, dict)
            assert len(d) > 0

    def test_all_contracts_have_to_json_dict(self):
        instances = [
            _voice_session(), _presence(), _speech_turn(), _transcript(),
            _action_plan(), _interruption(), _decision(), _snapshot(),
            _violation(), _closure(),
        ]
        for inst in instances:
            d = inst.to_json_dict()
            assert isinstance(d, dict)

    def test_all_contracts_have_to_json(self):
        instances = [
            _voice_session(), _presence(), _speech_turn(), _transcript(),
            _action_plan(), _interruption(), _decision(), _snapshot(),
            _violation(), _closure(),
        ]
        for inst in instances:
            j = inst.to_json()
            assert isinstance(j, str)
            assert len(j) > 2

    def test_metadata_isolation(self):
        """Mutating original dict does not affect the record."""
        orig = {"key": "val"}
        s = _voice_session(metadata=orig)
        orig["key"] = "CHANGED"
        assert s.metadata["key"] == "val"

    def test_metadata_proxy_immutable(self):
        s = _voice_session(metadata={"key": "val"})
        with pytest.raises(TypeError):
            s.metadata["key"] = "changed"

    def test_to_dict_enum_preserved(self):
        """to_dict preserves enum objects, not string values."""
        s = _voice_session()
        d = s.to_dict()
        assert isinstance(d["mode"], InteractionMode)
        assert isinstance(d["channel"], SessionChannel)

    def test_to_json_dict_enum_to_value(self):
        """to_json_dict converts enums to their .value string."""
        s = _voice_session()
        d = s.to_json_dict()
        assert d["mode"] == "voice"
        assert d["channel"] == "web"

    def test_datetime_with_z_suffix_accepted(self):
        s = _voice_session(started_at="2025-06-01T12:00:00Z")
        assert s.started_at == "2025-06-01T12:00:00Z"

    def test_datetime_with_offset_accepted(self):
        s = _voice_session(started_at="2025-06-01T12:00:00+05:30")
        assert s.started_at == "2025-06-01T12:00:00+05:30"

    def test_datetime_naive_accepted(self):
        s = _voice_session(started_at="2025-06-01T12:00:00")
        assert s.started_at == "2025-06-01T12:00:00"

    def test_voice_session_different_metadata_not_equal(self):
        a = _voice_session(metadata={"a": 1})
        b = _voice_session(metadata={"b": 2})
        assert a != b

    def test_speech_turn_non_string_turn_id_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            _speech_turn(turn_id=42)

    def test_transcript_non_string_content_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            _transcript(content=42)

    def test_interruption_record_none_status(self):
        with pytest.raises((ValueError, TypeError)):
            _interruption(status=None)

    def test_snapshot_string_total_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            _snapshot(total_sessions="1")

    def test_closure_string_total_rejected(self):
        with pytest.raises((ValueError, TypeError)):
            _closure(total_turns="2")

    def test_presence_none_status(self):
        with pytest.raises((ValueError, TypeError)):
            _presence(status=None)

    def test_decision_none_disposition(self):
        with pytest.raises((ValueError, TypeError)):
            _decision(disposition=None)

    def test_violation_none_operation(self):
        with pytest.raises((ValueError, TypeError)):
            _violation(operation=None)
