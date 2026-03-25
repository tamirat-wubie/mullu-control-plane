"""Purpose: multimodal / voice / presence runtime contracts.
Governance scope: typed descriptors for voice sessions, presence state,
    speech turns, streaming transcripts, action plans, interruptions,
    decisions, violations, snapshots, and closure reports.
Dependencies: _base contract utilities.
Invariants:
  - Every record references a tenant.
  - All outputs are frozen and traceable.
  - Voice sessions are linked to copilot sessions.
  - Interruption status follows a deterministic state machine.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from ._base import (
    ContractRecord,
    freeze_value,
    require_datetime_text,
    require_non_empty_text,
    require_non_negative_float,
    require_non_negative_int,
    require_unit_float,
)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class InteractionMode(Enum):
    """Mode of multimodal interaction."""
    VOICE = "voice"
    TEXT = "text"
    HYBRID = "hybrid"
    STREAMING = "streaming"


class SessionChannel(Enum):
    """Channel through which a session is conducted."""
    PHONE = "phone"
    WEB = "web"
    CHAT = "chat"
    API = "api"
    IN_PERSON = "in_person"


class PresenceStatus(Enum):
    """Presence status of a participant."""
    AVAILABLE = "available"
    BUSY = "busy"
    AWAY = "away"
    DO_NOT_DISTURB = "do_not_disturb"
    OFFLINE = "offline"


class SpeechDisposition(Enum):
    """Disposition of a speech turn."""
    CAPTURED = "captured"
    TRANSCRIBED = "transcribed"
    PROCESSED = "processed"
    FAILED = "failed"


class InterruptionStatus(Enum):
    """Status of an interruption event."""
    DETECTED = "detected"
    ACKNOWLEDGED = "acknowledged"
    RESUMED = "resumed"
    DISMISSED = "dismissed"


class ConversationAttentionLevel(Enum):
    """Attention level in a conversation."""
    FOCUSED = "focused"
    PASSIVE = "passive"
    BACKGROUND = "background"
    DORMANT = "dormant"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class VoiceSession(ContractRecord):
    """A multimodal voice session linked to a copilot session."""

    session_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    copilot_session_ref: str = ""
    mode: InteractionMode = InteractionMode.VOICE
    channel: SessionChannel = SessionChannel.WEB
    status: str = "active"
    started_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "session_id", require_non_empty_text(self.session_id, "session_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        object.__setattr__(self, "copilot_session_ref", require_non_empty_text(self.copilot_session_ref, "copilot_session_ref"))
        if not isinstance(self.mode, InteractionMode):
            raise ValueError("mode must be an InteractionMode")
        if not isinstance(self.channel, SessionChannel):
            raise ValueError("channel must be a SessionChannel")
        object.__setattr__(self, "status", require_non_empty_text(self.status, "status"))
        require_datetime_text(self.started_at, "started_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class PresenceRecord(ContractRecord):
    """Presence state for a participant."""

    presence_id: str = ""
    tenant_id: str = ""
    identity_ref: str = ""
    status: PresenceStatus = PresenceStatus.AVAILABLE
    attention: ConversationAttentionLevel = ConversationAttentionLevel.FOCUSED
    updated_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "presence_id", require_non_empty_text(self.presence_id, "presence_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "identity_ref", require_non_empty_text(self.identity_ref, "identity_ref"))
        if not isinstance(self.status, PresenceStatus):
            raise ValueError("status must be a PresenceStatus")
        if not isinstance(self.attention, ConversationAttentionLevel):
            raise ValueError("attention must be a ConversationAttentionLevel")
        require_datetime_text(self.updated_at, "updated_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class SpeechTurn(ContractRecord):
    """A single speech turn in a voice session."""

    turn_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    speaker_ref: str = ""
    content: str = ""
    disposition: SpeechDisposition = SpeechDisposition.CAPTURED
    duration_ms: float = 0.0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "turn_id", require_non_empty_text(self.turn_id, "turn_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        object.__setattr__(self, "speaker_ref", require_non_empty_text(self.speaker_ref, "speaker_ref"))
        object.__setattr__(self, "content", require_non_empty_text(self.content, "content"))
        if not isinstance(self.disposition, SpeechDisposition):
            raise ValueError("disposition must be a SpeechDisposition")
        object.__setattr__(self, "duration_ms", require_non_negative_float(self.duration_ms, "duration_ms"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class StreamingTranscript(ContractRecord):
    """A streaming transcript fragment."""

    transcript_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    content: str = ""
    is_final: bool = False
    confidence: float = 1.0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "transcript_id", require_non_empty_text(self.transcript_id, "transcript_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        object.__setattr__(self, "content", require_non_empty_text(self.content, "content"))
        if not isinstance(self.is_final, bool):
            raise ValueError("is_final must be a bool")
        object.__setattr__(self, "confidence", require_unit_float(self.confidence, "confidence"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class VoiceActionPlan(ContractRecord):
    """An action plan derived from a voice session."""

    plan_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    intent_summary: str = ""
    target_runtime: str = ""
    disposition: str = "allowed"
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", require_non_empty_text(self.plan_id, "plan_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        object.__setattr__(self, "intent_summary", require_non_empty_text(self.intent_summary, "intent_summary"))
        object.__setattr__(self, "target_runtime", require_non_empty_text(self.target_runtime, "target_runtime"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class InterruptionRecord(ContractRecord):
    """An interruption event in a voice session."""

    interruption_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    status: InterruptionStatus = InterruptionStatus.DETECTED
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "interruption_id", require_non_empty_text(self.interruption_id, "interruption_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        if not isinstance(self.status, InterruptionStatus):
            raise ValueError("status must be an InterruptionStatus")
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MultimodalDecision(ContractRecord):
    """A decision made in the multimodal runtime."""

    decision_id: str = ""
    tenant_id: str = ""
    session_ref: str = ""
    disposition: str = ""
    reason: str = ""
    decided_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "decision_id", require_non_empty_text(self.decision_id, "decision_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "session_ref", require_non_empty_text(self.session_ref, "session_ref"))
        object.__setattr__(self, "disposition", require_non_empty_text(self.disposition, "disposition"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.decided_at, "decided_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MultimodalSnapshot(ContractRecord):
    """Point-in-time snapshot of multimodal runtime state."""

    snapshot_id: str = ""
    tenant_id: str = ""
    total_sessions: int = 0
    total_turns: int = 0
    total_transcripts: int = 0
    total_interruptions: int = 0
    total_violations: int = 0
    captured_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "snapshot_id", require_non_empty_text(self.snapshot_id, "snapshot_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "total_turns", require_non_negative_int(self.total_turns, "total_turns"))
        object.__setattr__(self, "total_transcripts", require_non_negative_int(self.total_transcripts, "total_transcripts"))
        object.__setattr__(self, "total_interruptions", require_non_negative_int(self.total_interruptions, "total_interruptions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.captured_at, "captured_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MultimodalViolation(ContractRecord):
    """A violation detected in the multimodal runtime."""

    violation_id: str = ""
    tenant_id: str = ""
    operation: str = ""
    reason: str = ""
    detected_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "violation_id", require_non_empty_text(self.violation_id, "violation_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "operation", require_non_empty_text(self.operation, "operation"))
        object.__setattr__(self, "reason", require_non_empty_text(self.reason, "reason"))
        require_datetime_text(self.detected_at, "detected_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class MultimodalClosureReport(ContractRecord):
    """Final closure report for multimodal runtime lifecycle."""

    report_id: str = ""
    tenant_id: str = ""
    total_sessions: int = 0
    total_turns: int = 0
    total_transcripts: int = 0
    total_interruptions: int = 0
    total_violations: int = 0
    created_at: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "report_id", require_non_empty_text(self.report_id, "report_id"))
        object.__setattr__(self, "tenant_id", require_non_empty_text(self.tenant_id, "tenant_id"))
        object.__setattr__(self, "total_sessions", require_non_negative_int(self.total_sessions, "total_sessions"))
        object.__setattr__(self, "total_turns", require_non_negative_int(self.total_turns, "total_turns"))
        object.__setattr__(self, "total_transcripts", require_non_negative_int(self.total_transcripts, "total_transcripts"))
        object.__setattr__(self, "total_interruptions", require_non_negative_int(self.total_interruptions, "total_interruptions"))
        object.__setattr__(self, "total_violations", require_non_negative_int(self.total_violations, "total_violations"))
        require_datetime_text(self.created_at, "created_at")
        object.__setattr__(self, "metadata", freeze_value(dict(self.metadata)))
