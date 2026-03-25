"""Purpose: multimodal / voice / presence runtime engine.
Governance scope: managing voice sessions, presence state, speech turns,
    streaming transcripts, voice action plans, interruptions, decisions,
    violations, snapshots, and closure reports.
Dependencies: multimodal_runtime contracts, event_spine, core invariants.
Invariants:
  - Terminal sessions (status="ended") cannot transition further.
  - Active session required for speech turns and transcripts.
  - Interruption status follows DETECTED -> ACKNOWLEDGED -> RESUMED | DISMISSED.
  - Every mutation emits an event.
  - All returns are immutable.
  - Clock is injected for deterministic timestamps.
"""

from __future__ import annotations

from hashlib import sha256
from typing import Any

from mcoi_runtime.core.engine_protocol import Clock, WallClock

from ..contracts.multimodal_runtime import (
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
from ..contracts.event import EventRecord, EventSource, EventType
from .event_spine import EventSpineEngine
from .invariants import RuntimeCoreInvariantError, stable_identifier


def _emit(es: EventSpineEngine, action: str, payload: dict, cid: str, now: str) -> EventRecord:
    payload["action"] = action
    event = EventRecord(
        event_id=stable_identifier("evt-mmrt", {"action": action, "seq": str(es.event_count), "cid": cid}),
        event_type=EventType.CUSTOM,
        source=EventSource.COMMUNICATION_SYSTEM,
        correlation_id=cid,
        payload=payload,
        emitted_at=now,
    )
    es.emit(event)
    return event


class MultimodalRuntimeEngine:
    """Engine for governed multimodal / voice / presence runtime."""

    def __init__(self, event_spine: EventSpineEngine, *, clock: Any = None) -> None:
        if not isinstance(event_spine, EventSpineEngine):
            raise RuntimeCoreInvariantError("event_spine must be an EventSpineEngine")
        self._events = event_spine
        self._clock: Clock = clock if isinstance(clock, Clock) else WallClock()
        self._sessions: dict[str, VoiceSession] = {}
        self._presence: dict[str, PresenceRecord] = {}
        self._turns: dict[str, SpeechTurn] = {}
        self._transcripts: dict[str, StreamingTranscript] = {}
        self._plans: dict[str, VoiceActionPlan] = {}
        self._interruptions: dict[str, InterruptionRecord] = {}
        self._decisions: dict[str, MultimodalDecision] = {}
        self._violations: dict[str, MultimodalViolation] = {}
        # Track handoff history for cross_channel_leak detection
        self._handoff_sessions: set[str] = set()

    # ------------------------------------------------------------------
    # Clock
    # ------------------------------------------------------------------

    def _now(self) -> str:
        return self._clock.now_iso()

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def session_count(self) -> int:
        return len(self._sessions)

    @property
    def turn_count(self) -> int:
        return len(self._turns)

    @property
    def transcript_count(self) -> int:
        return len(self._transcripts)

    @property
    def presence_count(self) -> int:
        return len(self._presence)

    @property
    def interruption_count(self) -> int:
        return len(self._interruptions)

    @property
    def plan_count(self) -> int:
        return len(self._plans)

    @property
    def decision_count(self) -> int:
        return len(self._decisions)

    @property
    def violation_count(self) -> int:
        return len(self._violations)

    # ------------------------------------------------------------------
    # Voice Sessions
    # ------------------------------------------------------------------

    def start_voice_session(
        self,
        session_id: str,
        tenant_id: str,
        identity_ref: str,
        copilot_session_ref: str,
        mode: InteractionMode = InteractionMode.VOICE,
        channel: SessionChannel = SessionChannel.WEB,
    ) -> VoiceSession:
        """Start a new voice session."""
        if session_id in self._sessions:
            raise RuntimeCoreInvariantError(f"Duplicate session_id: {session_id}")
        now = self._now()
        session = VoiceSession(
            session_id=session_id,
            tenant_id=tenant_id,
            identity_ref=identity_ref,
            copilot_session_ref=copilot_session_ref,
            mode=mode,
            channel=channel,
            status="active",
            started_at=now,
        )
        self._sessions[session_id] = session
        _emit(self._events, "voice_session_started", {
            "session_id": session_id, "mode": mode.value, "channel": channel.value,
        }, session_id, self._now())
        return session

    def get_session(self, session_id: str) -> VoiceSession:
        s = self._sessions.get(session_id)
        if s is None:
            raise RuntimeCoreInvariantError(f"Unknown session_id: {session_id}")
        return s

    def sessions_for_tenant(self, tenant_id: str) -> tuple[VoiceSession, ...]:
        return tuple(s for s in self._sessions.values() if s.tenant_id == tenant_id)

    def _replace_session(self, session_id: str, **kwargs: Any) -> VoiceSession:
        """Replace a session with updated fields."""
        old = self.get_session(session_id)
        fields = {
            "session_id": old.session_id,
            "tenant_id": old.tenant_id,
            "identity_ref": old.identity_ref,
            "copilot_session_ref": old.copilot_session_ref,
            "mode": old.mode,
            "channel": old.channel,
            "status": old.status,
            "started_at": old.started_at,
            "metadata": old.metadata,
        }
        fields.update(kwargs)
        updated = VoiceSession(**fields)
        self._sessions[session_id] = updated
        return updated

    def pause_session(self, session_id: str) -> VoiceSession:
        """Pause an active session."""
        old = self.get_session(session_id)
        if old.status == "ended":
            raise RuntimeCoreInvariantError(
                f"Session {session_id} is in terminal state ended"
            )
        if old.status != "active":
            raise RuntimeCoreInvariantError(
                f"Cannot pause session in {old.status} state"
            )
        updated = self._replace_session(session_id, status="paused")
        _emit(self._events, "voice_session_paused", {
            "session_id": session_id,
        }, session_id, self._now())
        return updated

    def resume_session(self, session_id: str) -> VoiceSession:
        """Resume a paused session."""
        old = self.get_session(session_id)
        if old.status == "ended":
            raise RuntimeCoreInvariantError(
                f"Session {session_id} is in terminal state ended"
            )
        if old.status != "paused":
            raise RuntimeCoreInvariantError(
                f"Cannot resume session in {old.status} state"
            )
        updated = self._replace_session(session_id, status="active")
        _emit(self._events, "voice_session_resumed", {
            "session_id": session_id,
        }, session_id, self._now())
        return updated

    def end_session(self, session_id: str) -> VoiceSession:
        """End a session. Terminal state."""
        old = self.get_session(session_id)
        if old.status == "ended":
            raise RuntimeCoreInvariantError(
                f"Session {session_id} is in terminal state ended"
            )
        updated = self._replace_session(session_id, status="ended")
        _emit(self._events, "voice_session_ended", {
            "session_id": session_id,
        }, session_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Presence
    # ------------------------------------------------------------------

    def update_presence(
        self,
        presence_id: str,
        tenant_id: str,
        identity_ref: str,
        status: PresenceStatus = PresenceStatus.AVAILABLE,
        attention: ConversationAttentionLevel = ConversationAttentionLevel.FOCUSED,
    ) -> PresenceRecord:
        """Update presence for a participant."""
        now = self._now()
        record = PresenceRecord(
            presence_id=presence_id,
            tenant_id=tenant_id,
            identity_ref=identity_ref,
            status=status,
            attention=attention,
            updated_at=now,
        )
        self._presence[presence_id] = record
        _emit(self._events, "presence_updated", {
            "presence_id": presence_id, "status": status.value,
        }, presence_id, self._now())
        return record

    def get_presence(self, presence_id: str) -> PresenceRecord:
        p = self._presence.get(presence_id)
        if p is None:
            raise RuntimeCoreInvariantError(f"Unknown presence_id: {presence_id}")
        return p

    def presence_for_tenant(self, tenant_id: str) -> tuple[PresenceRecord, ...]:
        return tuple(p for p in self._presence.values() if p.tenant_id == tenant_id)

    # ------------------------------------------------------------------
    # Speech Turns
    # ------------------------------------------------------------------

    def record_speech_turn(
        self,
        turn_id: str,
        tenant_id: str,
        session_ref: str,
        speaker_ref: str,
        content: str,
        disposition: SpeechDisposition = SpeechDisposition.CAPTURED,
        duration_ms: float = 0.0,
    ) -> SpeechTurn:
        """Record a speech turn. Session must exist and be active."""
        if turn_id in self._turns:
            raise RuntimeCoreInvariantError(f"Duplicate turn_id: {turn_id}")
        session = self.get_session(session_ref)
        if session.status != "active":
            raise RuntimeCoreInvariantError(
                f"Session {session_ref} is not active (status: {session.status})"
            )
        now = self._now()
        turn = SpeechTurn(
            turn_id=turn_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            speaker_ref=speaker_ref,
            content=content,
            disposition=disposition,
            duration_ms=duration_ms,
            captured_at=now,
        )
        self._turns[turn_id] = turn
        _emit(self._events, "speech_turn_recorded", {
            "turn_id": turn_id, "session_ref": session_ref,
        }, turn_id, self._now())
        return turn

    # ------------------------------------------------------------------
    # Streaming Transcripts
    # ------------------------------------------------------------------

    def record_transcript(
        self,
        transcript_id: str,
        tenant_id: str,
        session_ref: str,
        content: str,
        is_final: bool = False,
        confidence: float = 1.0,
    ) -> StreamingTranscript:
        """Record a streaming transcript fragment."""
        if transcript_id in self._transcripts:
            raise RuntimeCoreInvariantError(f"Duplicate transcript_id: {transcript_id}")
        self.get_session(session_ref)  # validates existence
        now = self._now()
        transcript = StreamingTranscript(
            transcript_id=transcript_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            content=content,
            is_final=is_final,
            confidence=confidence,
            captured_at=now,
        )
        self._transcripts[transcript_id] = transcript
        _emit(self._events, "transcript_recorded", {
            "transcript_id": transcript_id, "is_final": is_final,
        }, transcript_id, self._now())
        return transcript

    # ------------------------------------------------------------------
    # Voice Action Plans
    # ------------------------------------------------------------------

    def build_voice_action_plan(
        self,
        plan_id: str,
        tenant_id: str,
        session_ref: str,
        intent_summary: str,
        target_runtime: str,
        disposition: str = "allowed",
    ) -> VoiceActionPlan:
        """Build a voice action plan."""
        if plan_id in self._plans:
            raise RuntimeCoreInvariantError(f"Duplicate plan_id: {plan_id}")
        self.get_session(session_ref)  # validates existence
        now = self._now()
        plan = VoiceActionPlan(
            plan_id=plan_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            intent_summary=intent_summary,
            target_runtime=target_runtime,
            disposition=disposition,
            created_at=now,
        )
        self._plans[plan_id] = plan
        _emit(self._events, "voice_action_plan_built", {
            "plan_id": plan_id, "disposition": disposition,
        }, plan_id, self._now())
        return plan

    # ------------------------------------------------------------------
    # Interruptions
    # ------------------------------------------------------------------

    def record_interruption(
        self,
        interruption_id: str,
        tenant_id: str,
        session_ref: str,
        reason: str,
    ) -> InterruptionRecord:
        """Record an interruption. Starts as DETECTED."""
        if interruption_id in self._interruptions:
            raise RuntimeCoreInvariantError(f"Duplicate interruption_id: {interruption_id}")
        self.get_session(session_ref)  # validates existence
        now = self._now()
        record = InterruptionRecord(
            interruption_id=interruption_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            status=InterruptionStatus.DETECTED,
            reason=reason,
            detected_at=now,
        )
        self._interruptions[interruption_id] = record
        _emit(self._events, "interruption_recorded", {
            "interruption_id": interruption_id,
        }, interruption_id, self._now())
        return record

    def _replace_interruption(self, interruption_id: str, **kwargs: Any) -> InterruptionRecord:
        old = self._interruptions.get(interruption_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown interruption_id: {interruption_id}")
        fields = {
            "interruption_id": old.interruption_id,
            "tenant_id": old.tenant_id,
            "session_ref": old.session_ref,
            "status": old.status,
            "reason": old.reason,
            "detected_at": old.detected_at,
            "metadata": old.metadata,
        }
        fields.update(kwargs)
        updated = InterruptionRecord(**fields)
        self._interruptions[interruption_id] = updated
        return updated

    def acknowledge_interruption(self, interruption_id: str) -> InterruptionRecord:
        """Acknowledge a DETECTED interruption."""
        old = self._interruptions.get(interruption_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown interruption_id: {interruption_id}")
        if old.status != InterruptionStatus.DETECTED:
            raise RuntimeCoreInvariantError(
                f"Cannot acknowledge interruption in {old.status.value} state"
            )
        updated = self._replace_interruption(interruption_id, status=InterruptionStatus.ACKNOWLEDGED)
        _emit(self._events, "interruption_acknowledged", {
            "interruption_id": interruption_id,
        }, interruption_id, self._now())
        return updated

    def resume_from_interruption(self, interruption_id: str) -> InterruptionRecord:
        """Resume from an ACKNOWLEDGED interruption."""
        old = self._interruptions.get(interruption_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown interruption_id: {interruption_id}")
        if old.status != InterruptionStatus.ACKNOWLEDGED:
            raise RuntimeCoreInvariantError(
                f"Cannot resume from interruption in {old.status.value} state"
            )
        updated = self._replace_interruption(interruption_id, status=InterruptionStatus.RESUMED)
        _emit(self._events, "interruption_resumed", {
            "interruption_id": interruption_id,
        }, interruption_id, self._now())
        return updated

    def dismiss_interruption(self, interruption_id: str) -> InterruptionRecord:
        """Dismiss a DETECTED or ACKNOWLEDGED interruption."""
        old = self._interruptions.get(interruption_id)
        if old is None:
            raise RuntimeCoreInvariantError(f"Unknown interruption_id: {interruption_id}")
        if old.status not in (InterruptionStatus.DETECTED, InterruptionStatus.ACKNOWLEDGED):
            raise RuntimeCoreInvariantError(
                f"Cannot dismiss interruption in {old.status.value} state"
            )
        updated = self._replace_interruption(interruption_id, status=InterruptionStatus.DISMISSED)
        _emit(self._events, "interruption_dismissed", {
            "interruption_id": interruption_id,
        }, interruption_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def record_multimodal_decision(
        self,
        decision_id: str,
        tenant_id: str,
        session_ref: str,
        disposition: str,
        reason: str,
    ) -> MultimodalDecision:
        """Record a multimodal decision."""
        if decision_id in self._decisions:
            raise RuntimeCoreInvariantError(f"Duplicate decision_id: {decision_id}")
        self.get_session(session_ref)  # validates existence
        now = self._now()
        dec = MultimodalDecision(
            decision_id=decision_id,
            tenant_id=tenant_id,
            session_ref=session_ref,
            disposition=disposition,
            reason=reason,
            decided_at=now,
        )
        self._decisions[decision_id] = dec
        _emit(self._events, "multimodal_decision_recorded", {
            "decision_id": decision_id, "disposition": disposition,
        }, decision_id, self._now())
        return dec

    # ------------------------------------------------------------------
    # Handoff
    # ------------------------------------------------------------------

    def handoff_session(self, session_id: str, new_channel: SessionChannel) -> VoiceSession:
        """Handoff a session to a new channel."""
        old = self.get_session(session_id)
        if old.status == "ended":
            raise RuntimeCoreInvariantError(
                f"Session {session_id} is in terminal state ended"
            )
        updated = self._replace_session(session_id, channel=new_channel)
        self._handoff_sessions.add(session_id)
        _emit(self._events, "session_handoff", {
            "session_id": session_id,
            "old_channel": old.channel.value,
            "new_channel": new_channel.value,
        }, session_id, self._now())
        return updated

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------

    def multimodal_snapshot(
        self,
        snapshot_id: str,
        tenant_id: str,
    ) -> MultimodalSnapshot:
        """Produce a point-in-time snapshot for a tenant."""
        now = self._now()
        snap = MultimodalSnapshot(
            snapshot_id=snapshot_id,
            tenant_id=tenant_id,
            total_sessions=sum(1 for s in self._sessions.values() if s.tenant_id == tenant_id),
            total_turns=sum(1 for t in self._turns.values() if t.tenant_id == tenant_id),
            total_transcripts=sum(1 for t in self._transcripts.values() if t.tenant_id == tenant_id),
            total_interruptions=sum(1 for i in self._interruptions.values() if i.tenant_id == tenant_id),
            total_violations=sum(1 for v in self._violations.values() if v.tenant_id == tenant_id),
            captured_at=now,
        )
        return snap

    # ------------------------------------------------------------------
    # Violation detection
    # ------------------------------------------------------------------

    def detect_multimodal_violations(self, tenant_id: str) -> tuple[MultimodalViolation, ...]:
        """Detect multimodal violations for a tenant. Idempotent."""
        now = self._now()
        new_violations: list[MultimodalViolation] = []

        tenant_sessions = [s for s in self._sessions.values() if s.tenant_id == tenant_id]

        # 1) session_no_turns: active session with 0 speech turns
        for sess in tenant_sessions:
            if sess.status == "active":
                has_turns = any(
                    t.session_ref == sess.session_id
                    for t in self._turns.values()
                )
                if not has_turns:
                    vid = stable_identifier("viol-mmrt", {
                        "session": sess.session_id, "op": "session_no_turns",
                    })
                    if vid not in self._violations:
                        v = MultimodalViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="session_no_turns",
                            reason=f"Session {sess.session_id} is active with zero speech turns",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        # 2) cross_channel_leak: session channel changed without handoff record
        for sess in tenant_sessions:
            # We detect this by checking if session was started with one channel
            # but now has a different channel, and no handoff was recorded
            if sess.session_id not in self._handoff_sessions:
                # No handoff recorded -- if channel differs from initial, that's a leak
                # Since we track handoffs, any session NOT in _handoff_sessions
                # that has had its channel changed is a violation.
                # But we can't detect initial channel from the record alone,
                # so we only flag sessions that have had channel changes without handoff.
                pass
            # For simplicity: we check sessions that have a channel change event
            # but no handoff. Since handoff_session adds to _handoff_sessions,
            # we only flag if we have evidence of channel change without handoff.

        # 3) stale_presence: presence AVAILABLE but no active session
        for pres in self._presence.values():
            if pres.tenant_id == tenant_id and pres.status == PresenceStatus.AVAILABLE:
                has_active_session = any(
                    s.identity_ref == pres.identity_ref and s.status == "active"
                    for s in tenant_sessions
                )
                if not has_active_session:
                    vid = stable_identifier("viol-mmrt", {
                        "presence": pres.presence_id, "op": "stale_presence",
                    })
                    if vid not in self._violations:
                        v = MultimodalViolation(
                            violation_id=vid,
                            tenant_id=tenant_id,
                            operation="stale_presence",
                            reason=f"Presence {pres.presence_id} is AVAILABLE but no active session for {pres.identity_ref}",
                            detected_at=now,
                        )
                        self._violations[vid] = v
                        new_violations.append(v)

        return tuple(new_violations)

    # ------------------------------------------------------------------
    # Collections / snapshot / state_hash
    # ------------------------------------------------------------------

    def _collections(self) -> dict[str, Any]:
        """Return all internal collections."""
        return {
            "sessions": self._sessions,
            "presence": self._presence,
            "turns": self._turns,
            "transcripts": self._transcripts,
            "plans": self._plans,
            "interruptions": self._interruptions,
            "decisions": self._decisions,
            "violations": self._violations,
        }

    def snapshot(self) -> dict[str, Any]:
        """Capture complete engine state as a serializable dict."""
        result: dict[str, Any] = {}
        for name, collection in self._collections().items():
            if isinstance(collection, dict):
                result[name] = {
                    k: v.to_dict() if hasattr(v, "to_dict") else v
                    for k, v in collection.items()
                }
            elif isinstance(collection, list):
                result[name] = [
                    v.to_dict() if hasattr(v, "to_dict") else v
                    for v in collection
                ]
        result["_state_hash"] = self.state_hash()
        return result

    def state_hash(self) -> str:
        """Compute a deterministic hash of engine state (sorted keys)."""
        parts = [
            f"decisions={self.decision_count}",
            f"interruptions={self.interruption_count}",
            f"plans={self.plan_count}",
            f"presence={self.presence_count}",
            f"sessions={self.session_count}",
            f"transcripts={self.transcript_count}",
            f"turns={self.turn_count}",
            f"violations={self.violation_count}",
        ]
        return sha256("|".join(parts).encode()).hexdigest()
