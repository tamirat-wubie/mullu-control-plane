"""Tests for multimodal / voice / presence runtime engine."""

from __future__ import annotations

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
from mcoi_runtime.core.multimodal_runtime import MultimodalRuntimeEngine
from mcoi_runtime.core.event_spine import EventSpineEngine
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.engine_protocol import FixedClock


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TS = "2026-01-01T00:00:00+00:00"


@pytest.fixture
def clock():
    return FixedClock(TS)


@pytest.fixture
def es():
    return EventSpineEngine()


@pytest.fixture
def engine(es, clock):
    return MultimodalRuntimeEngine(es, clock=clock)


def _start(eng, sid="s1", tid="t-1", iref="u1", cop="cop1",
           mode=InteractionMode.VOICE, channel=SessionChannel.WEB):
    return eng.start_voice_session(sid, tid, iref, cop, mode, channel)


# =========================================================================
# Constructor
# =========================================================================


class TestConstructor:
    def test_valid_construction(self, es, clock):
        eng = MultimodalRuntimeEngine(es, clock=clock)
        assert eng.session_count == 0

    def test_invalid_event_spine(self, clock):
        with pytest.raises(RuntimeCoreInvariantError):
            MultimodalRuntimeEngine("not-an-es", clock=clock)

    def test_none_event_spine(self, clock):
        with pytest.raises(RuntimeCoreInvariantError):
            MultimodalRuntimeEngine(None, clock=clock)

    def test_default_clock(self, es):
        eng = MultimodalRuntimeEngine(es)
        assert eng.session_count == 0

    def test_clock_kwarg(self, es, clock):
        eng = MultimodalRuntimeEngine(es, clock=clock)
        assert eng.session_count == 0


# =========================================================================
# Properties (empty engine)
# =========================================================================


class TestEmptyProperties:
    def test_session_count_zero(self, engine):
        assert engine.session_count == 0

    def test_turn_count_zero(self, engine):
        assert engine.turn_count == 0

    def test_transcript_count_zero(self, engine):
        assert engine.transcript_count == 0

    def test_presence_count_zero(self, engine):
        assert engine.presence_count == 0

    def test_interruption_count_zero(self, engine):
        assert engine.interruption_count == 0

    def test_plan_count_zero(self, engine):
        assert engine.plan_count == 0

    def test_decision_count_zero(self, engine):
        assert engine.decision_count == 0

    def test_violation_count_zero(self, engine):
        assert engine.violation_count == 0


# =========================================================================
# Voice Sessions
# =========================================================================


class TestStartVoiceSession:
    def test_basic_start(self, engine):
        s = _start(engine)
        assert isinstance(s, VoiceSession)
        assert s.session_id == "s1"
        assert s.tenant_id == "t-1"
        assert s.status == "active"

    def test_mode_set(self, engine):
        s = _start(engine, mode=InteractionMode.HYBRID)
        assert s.mode is InteractionMode.HYBRID

    def test_channel_set(self, engine):
        s = _start(engine, channel=SessionChannel.PHONE)
        assert s.channel is SessionChannel.PHONE

    def test_session_count_increments(self, engine):
        _start(engine, sid="s1")
        _start(engine, sid="s2")
        assert engine.session_count == 2

    def test_duplicate_session_id_rejected(self, engine):
        _start(engine, sid="s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            _start(engine, sid="s1")

    def test_emits_event(self, engine, es):
        before = es.event_count
        _start(engine)
        assert es.event_count > before

    def test_all_modes(self, engine):
        for i, m in enumerate(InteractionMode):
            s = _start(engine, sid=f"s-mode-{i}", mode=m)
            assert s.mode is m

    def test_all_channels(self, engine):
        for i, c in enumerate(SessionChannel):
            s = _start(engine, sid=f"s-ch-{i}", channel=c)
            assert s.channel is c

    def test_started_at_uses_clock(self, engine):
        s = _start(engine)
        assert s.started_at == TS


class TestGetSession:
    def test_get_existing(self, engine):
        _start(engine, sid="s1")
        s = engine.get_session("s1")
        assert s.session_id == "s1"

    def test_get_unknown(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_session("nonexistent")


class TestSessionsForTenant:
    def test_empty(self, engine):
        assert engine.sessions_for_tenant("t-1") == ()

    def test_single(self, engine):
        _start(engine, sid="s1", tid="t-1")
        result = engine.sessions_for_tenant("t-1")
        assert len(result) == 1

    def test_multi_tenant_isolation(self, engine):
        _start(engine, sid="s1", tid="t-1")
        _start(engine, sid="s2", tid="t-2")
        assert len(engine.sessions_for_tenant("t-1")) == 1
        assert len(engine.sessions_for_tenant("t-2")) == 1

    def test_returns_tuple(self, engine):
        _start(engine, sid="s1")
        result = engine.sessions_for_tenant("t-1")
        assert isinstance(result, tuple)


class TestPauseSession:
    def test_pause_active(self, engine):
        _start(engine, sid="s1")
        s = engine.pause_session("s1")
        assert s.status == "paused"

    def test_pause_ended_rejected(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.pause_session("s1")

    def test_pause_paused_rejected(self, engine):
        _start(engine, sid="s1")
        engine.pause_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot pause"):
            engine.pause_session("s1")

    def test_pause_unknown_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.pause_session("nonexistent")

    def test_pause_emits_event(self, engine, es):
        _start(engine, sid="s1")
        before = es.event_count
        engine.pause_session("s1")
        assert es.event_count > before


class TestResumeSession:
    def test_resume_paused(self, engine):
        _start(engine, sid="s1")
        engine.pause_session("s1")
        s = engine.resume_session("s1")
        assert s.status == "active"

    def test_resume_active_rejected(self, engine):
        _start(engine, sid="s1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot resume"):
            engine.resume_session("s1")

    def test_resume_ended_rejected(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.resume_session("s1")

    def test_resume_unknown_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.resume_session("nonexistent")

    def test_resume_emits_event(self, engine, es):
        _start(engine, sid="s1")
        engine.pause_session("s1")
        before = es.event_count
        engine.resume_session("s1")
        assert es.event_count > before


class TestEndSession:
    def test_end_active(self, engine):
        _start(engine, sid="s1")
        s = engine.end_session("s1")
        assert s.status == "ended"

    def test_end_paused(self, engine):
        _start(engine, sid="s1")
        engine.pause_session("s1")
        s = engine.end_session("s1")
        assert s.status == "ended"

    def test_end_ended_rejected(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.end_session("s1")

    def test_end_unknown_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.end_session("nonexistent")

    def test_end_emits_event(self, engine, es):
        _start(engine, sid="s1")
        before = es.event_count
        engine.end_session("s1")
        assert es.event_count > before

    def test_double_end_rejected(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.end_session("s1")


class TestTerminalSessionBlocksMutations:
    """Terminal 'ended' sessions block all further mutations."""

    def test_ended_blocks_pause(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.pause_session("s1")

    def test_ended_blocks_resume(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.resume_session("s1")

    def test_ended_blocks_end(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.end_session("s1")

    def test_ended_blocks_handoff(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.handoff_session("s1", SessionChannel.PHONE)

    def test_ended_blocks_speech_turn(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello")


# =========================================================================
# Presence
# =========================================================================


class TestPresence:
    def test_update_presence(self, engine):
        p = engine.update_presence("p1", "t-1", "u1")
        assert isinstance(p, PresenceRecord)
        assert p.presence_id == "p1"
        assert p.status is PresenceStatus.AVAILABLE

    def test_update_with_status(self, engine):
        p = engine.update_presence("p1", "t-1", "u1", status=PresenceStatus.BUSY)
        assert p.status is PresenceStatus.BUSY

    def test_update_with_attention(self, engine):
        p = engine.update_presence("p1", "t-1", "u1",
                                   attention=ConversationAttentionLevel.PASSIVE)
        assert p.attention is ConversationAttentionLevel.PASSIVE

    def test_get_presence(self, engine):
        engine.update_presence("p1", "t-1", "u1")
        p = engine.get_presence("p1")
        assert p.presence_id == "p1"

    def test_get_unknown_presence(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.get_presence("nonexistent")

    def test_presence_overwrite(self, engine):
        engine.update_presence("p1", "t-1", "u1", status=PresenceStatus.AVAILABLE)
        engine.update_presence("p1", "t-1", "u1", status=PresenceStatus.BUSY)
        p = engine.get_presence("p1")
        assert p.status is PresenceStatus.BUSY

    def test_presence_count(self, engine):
        engine.update_presence("p1", "t-1", "u1")
        engine.update_presence("p2", "t-1", "u2")
        assert engine.presence_count == 2

    def test_presence_for_tenant(self, engine):
        engine.update_presence("p1", "t-1", "u1")
        engine.update_presence("p2", "t-2", "u2")
        result = engine.presence_for_tenant("t-1")
        assert len(result) == 1

    def test_presence_emits_event(self, engine, es):
        before = es.event_count
        engine.update_presence("p1", "t-1", "u1")
        assert es.event_count > before

    def test_all_presence_statuses(self, engine):
        for i, ps in enumerate(PresenceStatus):
            engine.update_presence(f"p-{i}", "t-1", "u1", status=ps)
            assert engine.get_presence(f"p-{i}").status is ps

    def test_all_attention_levels(self, engine):
        for i, al in enumerate(ConversationAttentionLevel):
            engine.update_presence(f"p-{i}", "t-1", "u1", attention=al)
            assert engine.get_presence(f"p-{i}").attention is al

    def test_presence_for_tenant_returns_tuple(self, engine):
        assert isinstance(engine.presence_for_tenant("t-1"), tuple)


# =========================================================================
# Speech Turns
# =========================================================================


class TestRecordSpeechTurn:
    def test_basic_turn(self, engine):
        _start(engine, sid="s1")
        t = engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello")
        assert isinstance(t, SpeechTurn)
        assert t.turn_id == "t1"
        assert t.content == "hello"

    def test_turn_count(self, engine):
        _start(engine, sid="s1")
        engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello")
        engine.record_speech_turn("t2", "t-1", "s1", "u1", "world")
        assert engine.turn_count == 2

    def test_duplicate_turn_rejected(self, engine):
        _start(engine, sid="s1")
        engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.record_speech_turn("t1", "t-1", "s1", "u1", "world")

    def test_unknown_session_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.record_speech_turn("t1", "t-1", "nonexistent", "u1", "hello")

    def test_ended_session_rejected(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="not active"):
            engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello")

    def test_paused_session_rejected(self, engine):
        _start(engine, sid="s1")
        engine.pause_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="not active"):
            engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello")

    def test_disposition_set(self, engine):
        _start(engine, sid="s1")
        t = engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello",
                                       disposition=SpeechDisposition.TRANSCRIBED)
        assert t.disposition is SpeechDisposition.TRANSCRIBED

    def test_duration_ms_set(self, engine):
        _start(engine, sid="s1")
        t = engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello",
                                       duration_ms=1500.0)
        assert t.duration_ms == 1500.0

    def test_turn_emits_event(self, engine, es):
        _start(engine, sid="s1")
        before = es.event_count
        engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello")
        assert es.event_count > before

    def test_captured_at_uses_clock(self, engine):
        _start(engine, sid="s1")
        t = engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello")
        assert t.captured_at == TS


# =========================================================================
# Streaming Transcripts
# =========================================================================


class TestRecordTranscript:
    def test_basic_transcript(self, engine):
        _start(engine, sid="s1")
        t = engine.record_transcript("tr1", "t-1", "s1", "hello world")
        assert isinstance(t, StreamingTranscript)
        assert t.transcript_id == "tr1"

    def test_transcript_count(self, engine):
        _start(engine, sid="s1")
        engine.record_transcript("tr1", "t-1", "s1", "hello")
        engine.record_transcript("tr2", "t-1", "s1", "world")
        assert engine.transcript_count == 2

    def test_duplicate_transcript_rejected(self, engine):
        _start(engine, sid="s1")
        engine.record_transcript("tr1", "t-1", "s1", "hello")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.record_transcript("tr1", "t-1", "s1", "world")

    def test_unknown_session_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.record_transcript("tr1", "t-1", "nonexistent", "hello")

    def test_is_final_set(self, engine):
        _start(engine, sid="s1")
        t = engine.record_transcript("tr1", "t-1", "s1", "hello", is_final=True)
        assert t.is_final is True

    def test_confidence_set(self, engine):
        _start(engine, sid="s1")
        t = engine.record_transcript("tr1", "t-1", "s1", "hello", confidence=0.85)
        assert t.confidence == 0.85

    def test_transcript_emits_event(self, engine, es):
        _start(engine, sid="s1")
        before = es.event_count
        engine.record_transcript("tr1", "t-1", "s1", "hello")
        assert es.event_count > before

    def test_captured_at_uses_clock(self, engine):
        _start(engine, sid="s1")
        t = engine.record_transcript("tr1", "t-1", "s1", "hello")
        assert t.captured_at == TS


# =========================================================================
# Voice Action Plans
# =========================================================================


class TestBuildVoiceActionPlan:
    def test_basic_plan(self, engine):
        _start(engine, sid="s1")
        p = engine.build_voice_action_plan("p1", "t-1", "s1", "navigate", "copilot")
        assert isinstance(p, VoiceActionPlan)
        assert p.plan_id == "p1"

    def test_plan_count(self, engine):
        _start(engine, sid="s1")
        engine.build_voice_action_plan("p1", "t-1", "s1", "navigate", "copilot")
        engine.build_voice_action_plan("p2", "t-1", "s1", "search", "copilot")
        assert engine.plan_count == 2

    def test_duplicate_plan_rejected(self, engine):
        _start(engine, sid="s1")
        engine.build_voice_action_plan("p1", "t-1", "s1", "navigate", "copilot")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.build_voice_action_plan("p1", "t-1", "s1", "search", "copilot")

    def test_unknown_session_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.build_voice_action_plan("p1", "t-1", "nonexistent", "nav", "cop")

    def test_disposition_allowed(self, engine):
        _start(engine, sid="s1")
        p = engine.build_voice_action_plan("p1", "t-1", "s1", "nav", "cop", "allowed")
        assert p.disposition == "allowed"

    def test_disposition_blocked(self, engine):
        _start(engine, sid="s1")
        p = engine.build_voice_action_plan("p1", "t-1", "s1", "nav", "cop", "blocked")
        assert p.disposition == "blocked"

    def test_plan_emits_event(self, engine, es):
        _start(engine, sid="s1")
        before = es.event_count
        engine.build_voice_action_plan("p1", "t-1", "s1", "nav", "cop")
        assert es.event_count > before

    def test_created_at_uses_clock(self, engine):
        _start(engine, sid="s1")
        p = engine.build_voice_action_plan("p1", "t-1", "s1", "nav", "cop")
        assert p.created_at == TS


# =========================================================================
# Interruptions
# =========================================================================


class TestRecordInterruption:
    def test_basic_interruption(self, engine):
        _start(engine, sid="s1")
        r = engine.record_interruption("i1", "t-1", "s1", "user spoke")
        assert isinstance(r, InterruptionRecord)
        assert r.status is InterruptionStatus.DETECTED

    def test_interruption_count(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason1")
        engine.record_interruption("i2", "t-1", "s1", "reason2")
        assert engine.interruption_count == 2

    def test_duplicate_interruption_rejected(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.record_interruption("i1", "t-1", "s1", "reason")

    def test_unknown_session_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.record_interruption("i1", "t-1", "nonexistent", "reason")

    def test_emits_event(self, engine, es):
        _start(engine, sid="s1")
        before = es.event_count
        engine.record_interruption("i1", "t-1", "s1", "reason")
        assert es.event_count > before


class TestAcknowledgeInterruption:
    def test_acknowledge_detected(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        r = engine.acknowledge_interruption("i1")
        assert r.status is InterruptionStatus.ACKNOWLEDGED

    def test_acknowledge_non_detected_rejected(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        engine.acknowledge_interruption("i1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot acknowledge"):
            engine.acknowledge_interruption("i1")

    def test_acknowledge_unknown_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.acknowledge_interruption("nonexistent")

    def test_emits_event(self, engine, es):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        before = es.event_count
        engine.acknowledge_interruption("i1")
        assert es.event_count > before


class TestResumeFromInterruption:
    def test_resume_acknowledged(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        engine.acknowledge_interruption("i1")
        r = engine.resume_from_interruption("i1")
        assert r.status is InterruptionStatus.RESUMED

    def test_resume_detected_rejected(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot resume"):
            engine.resume_from_interruption("i1")

    def test_resume_resumed_rejected(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        engine.acknowledge_interruption("i1")
        engine.resume_from_interruption("i1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot resume"):
            engine.resume_from_interruption("i1")

    def test_resume_unknown_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.resume_from_interruption("nonexistent")

    def test_emits_event(self, engine, es):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        engine.acknowledge_interruption("i1")
        before = es.event_count
        engine.resume_from_interruption("i1")
        assert es.event_count > before


class TestDismissInterruption:
    def test_dismiss_detected(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        r = engine.dismiss_interruption("i1")
        assert r.status is InterruptionStatus.DISMISSED

    def test_dismiss_acknowledged(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        engine.acknowledge_interruption("i1")
        r = engine.dismiss_interruption("i1")
        assert r.status is InterruptionStatus.DISMISSED

    def test_dismiss_resumed_rejected(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        engine.acknowledge_interruption("i1")
        engine.resume_from_interruption("i1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot dismiss"):
            engine.dismiss_interruption("i1")

    def test_dismiss_dismissed_rejected(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        engine.dismiss_interruption("i1")
        with pytest.raises(RuntimeCoreInvariantError, match="Cannot dismiss"):
            engine.dismiss_interruption("i1")

    def test_dismiss_unknown_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.dismiss_interruption("nonexistent")

    def test_emits_event(self, engine, es):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        before = es.event_count
        engine.dismiss_interruption("i1")
        assert es.event_count > before


class TestInterruptionLifecycle:
    """Full lifecycle: DETECTED -> ACKNOWLEDGED -> RESUMED/DISMISSED"""

    def test_full_lifecycle_resumed(self, engine):
        _start(engine, sid="s1")
        r = engine.record_interruption("i1", "t-1", "s1", "reason")
        assert r.status is InterruptionStatus.DETECTED
        r = engine.acknowledge_interruption("i1")
        assert r.status is InterruptionStatus.ACKNOWLEDGED
        r = engine.resume_from_interruption("i1")
        assert r.status is InterruptionStatus.RESUMED

    def test_full_lifecycle_dismissed_from_detected(self, engine):
        _start(engine, sid="s1")
        r = engine.record_interruption("i1", "t-1", "s1", "reason")
        assert r.status is InterruptionStatus.DETECTED
        r = engine.dismiss_interruption("i1")
        assert r.status is InterruptionStatus.DISMISSED

    def test_full_lifecycle_dismissed_from_acknowledged(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        engine.acknowledge_interruption("i1")
        r = engine.dismiss_interruption("i1")
        assert r.status is InterruptionStatus.DISMISSED

    def test_cannot_skip_acknowledge_to_resume(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.resume_from_interruption("i1")

    def test_resumed_is_terminal(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        engine.acknowledge_interruption("i1")
        engine.resume_from_interruption("i1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.dismiss_interruption("i1")

    def test_dismissed_is_terminal(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason")
        engine.dismiss_interruption("i1")
        with pytest.raises(RuntimeCoreInvariantError):
            engine.acknowledge_interruption("i1")

    def test_multiple_interruptions_independent(self, engine):
        _start(engine, sid="s1")
        engine.record_interruption("i1", "t-1", "s1", "reason1")
        engine.record_interruption("i2", "t-1", "s1", "reason2")
        engine.acknowledge_interruption("i1")
        # i2 still at DETECTED
        engine.dismiss_interruption("i2")
        engine.resume_from_interruption("i1")


# =========================================================================
# Decisions
# =========================================================================


class TestRecordDecision:
    def test_basic_decision(self, engine):
        _start(engine, sid="s1")
        d = engine.record_multimodal_decision("d1", "t-1", "s1", "approved", "ok")
        assert isinstance(d, MultimodalDecision)
        assert d.decision_id == "d1"

    def test_decision_count(self, engine):
        _start(engine, sid="s1")
        engine.record_multimodal_decision("d1", "t-1", "s1", "approved", "ok")
        engine.record_multimodal_decision("d2", "t-1", "s1", "denied", "nope")
        assert engine.decision_count == 2

    def test_duplicate_decision_rejected(self, engine):
        _start(engine, sid="s1")
        engine.record_multimodal_decision("d1", "t-1", "s1", "approved", "ok")
        with pytest.raises(RuntimeCoreInvariantError, match="Duplicate"):
            engine.record_multimodal_decision("d1", "t-1", "s1", "denied", "nope")

    def test_unknown_session_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.record_multimodal_decision("d1", "t-1", "nonexistent", "a", "b")

    def test_emits_event(self, engine, es):
        _start(engine, sid="s1")
        before = es.event_count
        engine.record_multimodal_decision("d1", "t-1", "s1", "approved", "ok")
        assert es.event_count > before

    def test_decided_at_uses_clock(self, engine):
        _start(engine, sid="s1")
        d = engine.record_multimodal_decision("d1", "t-1", "s1", "approved", "ok")
        assert d.decided_at == TS


# =========================================================================
# Handoff
# =========================================================================


class TestHandoffSession:
    def test_basic_handoff(self, engine):
        _start(engine, sid="s1", channel=SessionChannel.PHONE)
        s = engine.handoff_session("s1", SessionChannel.WEB)
        assert s.channel is SessionChannel.WEB

    def test_handoff_preserves_other_fields(self, engine):
        _start(engine, sid="s1", tid="t-1", iref="u1", cop="cop1")
        s = engine.handoff_session("s1", SessionChannel.CHAT)
        assert s.session_id == "s1"
        assert s.tenant_id == "t-1"
        assert s.identity_ref == "u1"
        assert s.status == "active"

    def test_handoff_ended_rejected(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        with pytest.raises(RuntimeCoreInvariantError, match="terminal"):
            engine.handoff_session("s1", SessionChannel.PHONE)

    def test_handoff_unknown_rejected(self, engine):
        with pytest.raises(RuntimeCoreInvariantError, match="Unknown"):
            engine.handoff_session("nonexistent", SessionChannel.PHONE)

    def test_handoff_emits_event(self, engine, es):
        _start(engine, sid="s1")
        before = es.event_count
        engine.handoff_session("s1", SessionChannel.PHONE)
        assert es.event_count > before

    def test_multiple_handoffs(self, engine):
        _start(engine, sid="s1", channel=SessionChannel.PHONE)
        engine.handoff_session("s1", SessionChannel.WEB)
        s = engine.handoff_session("s1", SessionChannel.CHAT)
        assert s.channel is SessionChannel.CHAT

    def test_handoff_paused_session(self, engine):
        _start(engine, sid="s1")
        engine.pause_session("s1")
        s = engine.handoff_session("s1", SessionChannel.PHONE)
        assert s.channel is SessionChannel.PHONE


# =========================================================================
# Snapshot (tenant-scoped)
# =========================================================================


class TestMultimodalSnapshot:
    def test_empty_snapshot(self, engine):
        snap = engine.multimodal_snapshot("snap1", "t-1")
        assert isinstance(snap, MultimodalSnapshot)
        assert snap.total_sessions == 0
        assert snap.total_turns == 0

    def test_snapshot_counts(self, engine):
        _start(engine, sid="s1", tid="t-1")
        engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello")
        engine.record_transcript("tr1", "t-1", "s1", "hello")
        snap = engine.multimodal_snapshot("snap1", "t-1")
        assert snap.total_sessions == 1
        assert snap.total_turns == 1
        assert snap.total_transcripts == 1

    def test_snapshot_tenant_isolation(self, engine):
        _start(engine, sid="s1", tid="t-1")
        _start(engine, sid="s2", tid="t-2")
        snap = engine.multimodal_snapshot("snap1", "t-1")
        assert snap.total_sessions == 1

    def test_snapshot_captured_at(self, engine):
        snap = engine.multimodal_snapshot("snap1", "t-1")
        assert snap.captured_at == TS


# =========================================================================
# Violation Detection
# =========================================================================


class TestDetectViolations:
    def test_no_violations_empty(self, engine):
        viols = engine.detect_multimodal_violations("t-1")
        assert viols == ()

    def test_session_no_turns_violation(self, engine):
        _start(engine, sid="s1", tid="t-1")
        viols = engine.detect_multimodal_violations("t-1")
        assert len(viols) == 1
        assert viols[0].operation == "session_no_turns"

    def test_session_with_turns_no_violation(self, engine):
        _start(engine, sid="s1", tid="t-1")
        engine.record_speech_turn("t1", "t-1", "s1", "u1", "hello")
        viols = engine.detect_multimodal_violations("t-1")
        # Only stale_presence if any, not session_no_turns
        for v in viols:
            assert v.operation != "session_no_turns"

    def test_stale_presence_violation(self, engine):
        engine.update_presence("p1", "t-1", "u1", status=PresenceStatus.AVAILABLE)
        viols = engine.detect_multimodal_violations("t-1")
        stale = [v for v in viols if v.operation == "stale_presence"]
        assert len(stale) == 1

    def test_presence_with_active_session_no_stale(self, engine):
        _start(engine, sid="s1", tid="t-1", iref="u1")
        engine.update_presence("p1", "t-1", "u1", status=PresenceStatus.AVAILABLE)
        viols = engine.detect_multimodal_violations("t-1")
        stale = [v for v in viols if v.operation == "stale_presence"]
        assert len(stale) == 0

    def test_idempotent_detection(self, engine):
        """Second call returns empty -- violations already recorded."""
        _start(engine, sid="s1", tid="t-1")
        v1 = engine.detect_multimodal_violations("t-1")
        v2 = engine.detect_multimodal_violations("t-1")
        assert len(v1) > 0
        assert len(v2) == 0

    def test_violation_count_increments(self, engine):
        _start(engine, sid="s1", tid="t-1")
        assert engine.violation_count == 0
        engine.detect_multimodal_violations("t-1")
        assert engine.violation_count > 0

    def test_tenant_isolation(self, engine):
        _start(engine, sid="s1", tid="t-1")
        _start(engine, sid="s2", tid="t-2")
        viols = engine.detect_multimodal_violations("t-1")
        for v in viols:
            assert v.tenant_id == "t-1"

    def test_ended_session_no_turns_no_violation(self, engine):
        _start(engine, sid="s1", tid="t-1")
        engine.end_session("s1")
        viols = engine.detect_multimodal_violations("t-1")
        session_no_turns = [v for v in viols if v.operation == "session_no_turns"]
        assert len(session_no_turns) == 0

    def test_offline_presence_no_stale_violation(self, engine):
        engine.update_presence("p1", "t-1", "u1", status=PresenceStatus.OFFLINE)
        viols = engine.detect_multimodal_violations("t-1")
        stale = [v for v in viols if v.operation == "stale_presence"]
        assert len(stale) == 0


# =========================================================================
# State hash and snapshot
# =========================================================================


class TestStateHashAndSnapshot:
    def test_empty_state_hash(self, engine):
        h = engine.state_hash()
        assert isinstance(h, str)
        assert len(h) == 64

    def test_state_hash_deterministic(self, engine):
        h1 = engine.state_hash()
        h2 = engine.state_hash()
        assert h1 == h2

    def test_state_hash_changes_after_mutation(self, engine):
        h1 = engine.state_hash()
        _start(engine, sid="s1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_snapshot_dict(self, engine):
        snap = engine.snapshot()
        assert isinstance(snap, dict)
        assert "_state_hash" in snap
        assert "sessions" in snap

    def test_snapshot_contains_all_collections(self, engine):
        snap = engine.snapshot()
        for key in ("sessions", "presence", "turns", "transcripts",
                    "plans", "interruptions", "decisions", "violations"):
            assert key in snap

    def test_snapshot_sessions_populated(self, engine):
        _start(engine, sid="s1")
        snap = engine.snapshot()
        assert "s1" in snap["sessions"]


class TestReplayWithFixedClock:
    """Replay: same ops with FixedClock -> same state_hash."""

    def _run_ops(self, clock):
        es = EventSpineEngine()
        eng = MultimodalRuntimeEngine(es, clock=clock)
        eng.start_voice_session("s1", "t-1", "u1", "cop1")
        eng.record_speech_turn("t1", "t-1", "s1", "u1", "hello")
        eng.record_transcript("tr1", "t-1", "s1", "hi", is_final=True, confidence=0.9)
        eng.update_presence("p1", "t-1", "u1", status=PresenceStatus.AVAILABLE)
        eng.record_interruption("i1", "t-1", "s1", "user spoke")
        eng.acknowledge_interruption("i1")
        eng.resume_from_interruption("i1")
        eng.build_voice_action_plan("plan1", "t-1", "s1", "nav", "cop")
        eng.record_multimodal_decision("d1", "t-1", "s1", "approved", "ok")
        return eng.state_hash()

    def test_replay_deterministic(self):
        h1 = self._run_ops(FixedClock(TS))
        h2 = self._run_ops(FixedClock(TS))
        assert h1 == h2

    def test_replay_same_hash_different_clock_instances(self):
        h1 = self._run_ops(FixedClock(TS))
        h2 = self._run_ops(FixedClock(TS))
        assert h1 == h2

    def test_different_clock_times_same_hash(self):
        """state_hash is based on counts, not timestamps."""
        h1 = self._run_ops(FixedClock(TS))
        h2 = self._run_ops(FixedClock("2099-12-31T23:59:59+00:00"))
        assert h1 == h2


# =========================================================================
# Golden scenarios
# =========================================================================


class TestGoldenScenarioOperatorVoice:
    """Operator asks by voice -> speech turn -> transcript -> evidence-backed answer."""

    def test_operator_voice_flow(self, engine):
        # 1. Start voice session for operator
        session = _start(engine, sid="op-sess", tid="t-1", iref="operator",
                         cop="workspace-1", mode=InteractionMode.VOICE)
        assert session.status == "active"

        # 2. Record speech turn
        turn = engine.record_speech_turn("turn-op-1", "t-1", "op-sess",
                                          "operator", "Show me Q3 revenue")
        assert turn.disposition is SpeechDisposition.CAPTURED

        # 3. Transcript streamed
        partial = engine.record_transcript("tr-op-1", "t-1", "op-sess",
                                           "Show me Q3", is_final=False, confidence=0.7)
        assert partial.is_final is False
        final = engine.record_transcript("tr-op-2", "t-1", "op-sess",
                                         "Show me Q3 revenue", is_final=True, confidence=0.95)
        assert final.is_final is True

        # 4. Decision: evidence-backed answer
        dec = engine.record_multimodal_decision("dec-op-1", "t-1", "op-sess",
                                                 "approved", "Revenue data found")
        assert dec.disposition == "approved"

        # 5. Action plan built
        plan = engine.build_voice_action_plan("plan-op-1", "t-1", "op-sess",
                                               "Display Q3 revenue chart", "copilot")
        assert plan.intent_summary == "Display Q3 revenue chart"

        # Verify counts
        assert engine.session_count == 1
        assert engine.turn_count == 1
        assert engine.transcript_count == 2
        assert engine.decision_count == 1
        assert engine.plan_count == 1


class TestGoldenScenarioInterruption:
    """User interrupts -> DETECTED -> ACKNOWLEDGED -> RESUMED correctly."""

    def test_interruption_flow(self, engine):
        _start(engine, sid="s1", tid="t-1")
        engine.record_speech_turn("t1", "t-1", "s1", "u1", "Starting task...")

        # Interruption detected
        ir = engine.record_interruption("i1", "t-1", "s1", "User spoke over agent")
        assert ir.status is InterruptionStatus.DETECTED

        # Acknowledged
        ir = engine.acknowledge_interruption("i1")
        assert ir.status is InterruptionStatus.ACKNOWLEDGED

        # Resumed
        ir = engine.resume_from_interruption("i1")
        assert ir.status is InterruptionStatus.RESUMED

        # Session still active
        s = engine.get_session("s1")
        assert s.status == "active"


class TestGoldenScenarioCrossTenantLeakage:
    """Cross-tenant/session leakage denied fail-closed."""

    def test_cross_tenant_session_isolation(self, engine):
        _start(engine, sid="s1", tid="t-1")
        _start(engine, sid="s2", tid="t-2")

        # t-1 sessions
        t1_sessions = engine.sessions_for_tenant("t-1")
        assert len(t1_sessions) == 1
        assert t1_sessions[0].session_id == "s1"

        # t-2 sessions
        t2_sessions = engine.sessions_for_tenant("t-2")
        assert len(t2_sessions) == 1
        assert t2_sessions[0].session_id == "s2"

    def test_cross_tenant_presence_isolation(self, engine):
        engine.update_presence("p1", "t-1", "u1")
        engine.update_presence("p2", "t-2", "u2")
        assert len(engine.presence_for_tenant("t-1")) == 1
        assert len(engine.presence_for_tenant("t-2")) == 1

    def test_cross_tenant_snapshot_isolation(self, engine):
        _start(engine, sid="s1", tid="t-1")
        _start(engine, sid="s2", tid="t-2")
        snap = engine.multimodal_snapshot("snap1", "t-1")
        assert snap.total_sessions == 1

    def test_cross_tenant_violation_isolation(self, engine):
        _start(engine, sid="s1", tid="t-1")
        _start(engine, sid="s2", tid="t-2")
        viols = engine.detect_multimodal_violations("t-1")
        for v in viols:
            assert v.tenant_id == "t-1"


class TestGoldenScenarioPhoneToWebHandoff:
    """Phone session hands off to web channel."""

    def test_phone_to_web_handoff(self, engine):
        session = _start(engine, sid="call-1", tid="t-1", iref="caller",
                         cop="comm-1", channel=SessionChannel.PHONE)
        assert session.channel is SessionChannel.PHONE

        # Record some turns on phone
        engine.record_speech_turn("t1", "t-1", "call-1", "caller", "I need help")

        # Handoff to web
        updated = engine.handoff_session("call-1", SessionChannel.WEB)
        assert updated.channel is SessionChannel.WEB
        assert updated.status == "active"

        # Can still record turns after handoff
        engine.record_speech_turn("t2", "t-1", "call-1", "caller", "Following up on web")
        assert engine.turn_count == 2


class TestGoldenScenarioExplanationVsDeferred:
    """Explanation mode vs deferred action mode."""

    def test_explanation_mode(self, engine):
        _start(engine, sid="s1", tid="t-1")
        engine.record_speech_turn("t1", "t-1", "s1", "u1", "Explain why this failed")
        # Explanation decision
        dec = engine.record_multimodal_decision("d1", "t-1", "s1",
                                                 "explanation", "Providing detailed reasoning")
        assert dec.disposition == "explanation"
        # No action plan needed for explanation
        assert engine.plan_count == 0

    def test_deferred_action_mode(self, engine):
        _start(engine, sid="s1", tid="t-1")
        engine.record_speech_turn("t1", "t-1", "s1", "u1", "Schedule a report for later")
        # Deferred decision
        dec = engine.record_multimodal_decision("d1", "t-1", "s1",
                                                 "deferred", "Scheduled for later execution")
        assert dec.disposition == "deferred"
        # Action plan created for deferred action
        plan = engine.build_voice_action_plan("p1", "t-1", "s1",
                                               "Generate report at 5pm", "scheduler",
                                               "deferred")
        assert plan.disposition == "deferred"


class TestGoldenScenarioReplay:
    """Replay with FixedClock: same ops -> same state_hash."""

    def _build_engine(self, clock):
        es = EventSpineEngine()
        eng = MultimodalRuntimeEngine(es, clock=clock)
        eng.start_voice_session("s1", "t-1", "u1", "cop1")
        eng.record_speech_turn("t1", "t-1", "s1", "u1", "hello")
        eng.record_transcript("tr1", "t-1", "s1", "hello", is_final=True)
        eng.update_presence("p1", "t-1", "u1")
        eng.record_interruption("i1", "t-1", "s1", "reason")
        eng.acknowledge_interruption("i1")
        eng.resume_from_interruption("i1")
        eng.build_voice_action_plan("plan1", "t-1", "s1", "nav", "cop")
        eng.record_multimodal_decision("d1", "t-1", "s1", "approved", "ok")
        eng.handoff_session("s1", SessionChannel.PHONE)
        eng.end_session("s1")
        return eng

    def test_same_ops_same_hash(self):
        e1 = self._build_engine(FixedClock(TS))
        e2 = self._build_engine(FixedClock(TS))
        assert e1.state_hash() == e2.state_hash()

    def test_same_ops_same_snapshot_structure(self):
        e1 = self._build_engine(FixedClock(TS))
        e2 = self._build_engine(FixedClock(TS))
        s1 = e1.snapshot()
        s2 = e2.snapshot()
        assert s1["_state_hash"] == s2["_state_hash"]
        assert set(s1.keys()) == set(s2.keys())


# =========================================================================
# Edge cases
# =========================================================================


class TestEdgeCases:
    def test_many_sessions(self, engine):
        for i in range(50):
            _start(engine, sid=f"s{i}", tid="t-1")
        assert engine.session_count == 50

    def test_many_turns_one_session(self, engine):
        _start(engine, sid="s1")
        for i in range(100):
            engine.record_speech_turn(f"t{i}", "t-1", "s1", "u1", f"turn {i}")
        assert engine.turn_count == 100

    def test_many_transcripts_one_session(self, engine):
        _start(engine, sid="s1")
        for i in range(100):
            engine.record_transcript(f"tr{i}", "t-1", "s1", f"chunk {i}")
        assert engine.transcript_count == 100

    def test_many_presence_updates(self, engine):
        for i in range(20):
            engine.update_presence(f"p{i}", "t-1", f"u{i}")
        assert engine.presence_count == 20

    def test_session_lifecycle_active_paused_active_ended(self, engine):
        _start(engine, sid="s1")
        engine.pause_session("s1")
        engine.resume_session("s1")
        engine.end_session("s1")
        assert engine.get_session("s1").status == "ended"

    def test_handoff_then_end(self, engine):
        _start(engine, sid="s1", channel=SessionChannel.PHONE)
        engine.handoff_session("s1", SessionChannel.WEB)
        engine.end_session("s1")
        assert engine.get_session("s1").status == "ended"

    def test_snapshot_after_violations(self, engine):
        _start(engine, sid="s1", tid="t-1")
        engine.detect_multimodal_violations("t-1")
        snap = engine.multimodal_snapshot("snap1", "t-1")
        assert snap.total_violations >= 1

    def test_state_hash_after_violations(self, engine):
        h1 = engine.state_hash()
        _start(engine, sid="s1", tid="t-1")
        engine.detect_multimodal_violations("t-1")
        h2 = engine.state_hash()
        assert h1 != h2

    def test_multiple_tenants_violations(self, engine):
        _start(engine, sid="s1", tid="t-1")
        _start(engine, sid="s2", tid="t-2")
        v1 = engine.detect_multimodal_violations("t-1")
        v2 = engine.detect_multimodal_violations("t-2")
        assert len(v1) > 0
        assert len(v2) > 0

    def test_presence_overwrite_does_not_increase_count(self, engine):
        engine.update_presence("p1", "t-1", "u1")
        engine.update_presence("p1", "t-1", "u1", status=PresenceStatus.BUSY)
        assert engine.presence_count == 1

    def test_speech_turn_on_resumed_session(self, engine):
        _start(engine, sid="s1")
        engine.pause_session("s1")
        engine.resume_session("s1")
        t = engine.record_speech_turn("t1", "t-1", "s1", "u1", "after resume")
        assert t.content == "after resume"

    def test_transcript_on_ended_session_allowed(self, engine):
        """Transcripts check session existence, not active status."""
        _start(engine, sid="s1")
        engine.end_session("s1")
        # record_transcript only checks existence, not status
        t = engine.record_transcript("tr1", "t-1", "s1", "late transcript")
        assert t.transcript_id == "tr1"

    def test_plan_on_ended_session_allowed(self, engine):
        """Plans check session existence, not active status."""
        _start(engine, sid="s1")
        engine.end_session("s1")
        p = engine.build_voice_action_plan("p1", "t-1", "s1", "nav", "cop")
        assert p.plan_id == "p1"

    def test_decision_on_ended_session_allowed(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        d = engine.record_multimodal_decision("d1", "t-1", "s1", "approved", "ok")
        assert d.decision_id == "d1"

    def test_interruption_on_ended_session_allowed(self, engine):
        _start(engine, sid="s1")
        engine.end_session("s1")
        r = engine.record_interruption("i1", "t-1", "s1", "reason")
        assert r.interruption_id == "i1"


class TestBoundedContractWitnesses:
    def test_invariant_messages_do_not_reflect_ids_or_statuses(self, engine):
        _start(engine, sid="s-secret")

        with pytest.raises(RuntimeCoreInvariantError) as duplicate_exc:
            _start(engine, sid="s-secret")
        duplicate_message = str(duplicate_exc.value)
        assert duplicate_message == "Duplicate session_id"
        assert "s-secret" not in duplicate_message
        assert "session_id" in duplicate_message

        engine.pause_session("s-secret")
        with pytest.raises(RuntimeCoreInvariantError) as active_exc:
            engine.record_speech_turn("turn-secret", "t-1", "s-secret", "u1", "hello")
        active_message = str(active_exc.value)
        assert active_message == "Session is not active"
        assert "paused" not in active_message
        assert "s-secret" not in active_message

        engine.end_session("s-secret")
        with pytest.raises(RuntimeCoreInvariantError) as terminal_exc:
            engine.handoff_session("s-secret", SessionChannel.PHONE)
        terminal_message = str(terminal_exc.value)
        assert terminal_message == "Session is in terminal state"
        assert "ended" not in terminal_message
        assert "s-secret" not in terminal_message

    def test_violation_reasons_are_bounded(self, engine):
        _start(engine, sid="s-no-turns", tid="t-1", iref="u-no-turns")
        engine.update_presence("p-stale", "t-1", "u-stale", status=PresenceStatus.AVAILABLE)

        violations = {v.operation: v.reason for v in engine.detect_multimodal_violations("t-1")}
        assert violations["session_no_turns"] == "Active session has zero speech turns"
        assert "s-no-turns" not in violations["session_no_turns"]
        assert "zero speech turns" in violations["session_no_turns"]

        assert violations["stale_presence"] == "Available presence has no active session"
        assert "p-stale" not in violations["stale_presence"]
        assert "u-stale" not in violations["stale_presence"]
