"""Purpose: read-only inbox and calendar projections for personal assistant.
Governance scope: private connector proof checks, redacted projection intake,
receipt emission, and no-mutation guarantees for PR4 read-only skills.
Dependencies: personal-assistant intake, registry contracts, and standard regex.
Invariants:
  - This module does not call live connectors, mailbox APIs, or calendar APIs.
  - Inputs must already be redacted operator-visible projections.
  - Receipts record actions taken and actions explicitly not taken.
  - Raw private payloads, secrets, connector mutation, and external writes are
    rejected before summary projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .intake import GovernedIntent, RequestExecutionMode
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


INBOX_SUMMARY_SKILL_ID = "email.inbox.summarize"
CALENDAR_DAY_BRIEF_SKILL_ID = "calendar.day.brief"

_INBOX_ALLOWED_FIELDS = frozenset(
    {
        "message_ref",
        "received_at",
        "sender_label",
        "subject_digest",
        "snippet_digest",
        "priority_signals",
        "needs_reply",
        "has_attachment",
    }
)
_CALENDAR_ALLOWED_FIELDS = frozenset(
    {
        "event_ref",
        "starts_at",
        "ends_at",
        "title_digest",
        "organizer_label",
        "location_label",
        "attendee_count",
        "conflict_ref",
        "preparation_signals",
    }
)
_RAW_PRIVATE_FIELD_FRAGMENTS = (
    "raw",
    "body",
    "payload",
    "secret",
    "token",
    "credential",
    "private_key",
    "authorization",
    "cookie",
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)
_BLOCKED_INBOX_ACTIONS = (
    "email_not_sent",
    "email_not_deleted",
    "email_not_archived",
    "email_not_forwarded",
    "connector_state_not_mutated",
)
_BLOCKED_CALENDAR_ACTIONS = (
    "calendar_event_not_created",
    "calendar_event_not_moved",
    "calendar_event_not_canceled",
    "people_not_invited",
    "connector_state_not_mutated",
)


@dataclass(frozen=True, slots=True)
class RedactedInboxMessage:
    """Operator-visible redacted inbox message projection."""

    message_ref: str
    received_at: str
    sender_label: str
    subject_digest: str
    snippet_digest: str
    priority_signals: tuple[str, ...] = ()
    needs_reply: bool = False
    has_attachment: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_ref", _require_projection_text(self.message_ref, "message_ref"))
        object.__setattr__(self, "received_at", _require_projection_text(self.received_at, "received_at"))
        object.__setattr__(self, "sender_label", _require_projection_text(self.sender_label, "sender_label"))
        object.__setattr__(self, "subject_digest", _require_projection_text(self.subject_digest, "subject_digest"))
        object.__setattr__(self, "snippet_digest", _require_projection_text(self.snippet_digest, "snippet_digest"))
        object.__setattr__(
            self,
            "priority_signals",
            _projection_text_tuple(self.priority_signals, "priority_signals", allow_empty=True),
        )
        if not isinstance(self.needs_reply, bool):
            raise PersonalAssistantInvariantError("needs_reply must be a boolean")
        if not isinstance(self.has_attachment, bool):
            raise PersonalAssistantInvariantError("has_attachment must be a boolean")

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "RedactedInboxMessage":
        """Build one inbox message projection from a mapping."""
        _assert_projection_mapping(payload, _INBOX_ALLOWED_FIELDS, "inbox message")
        return RedactedInboxMessage(
            message_ref=_require_projection_text(payload.get("message_ref"), "message_ref"),
            received_at=_require_projection_text(payload.get("received_at"), "received_at"),
            sender_label=_require_projection_text(payload.get("sender_label"), "sender_label"),
            subject_digest=_require_projection_text(payload.get("subject_digest"), "subject_digest"),
            snippet_digest=_require_projection_text(payload.get("snippet_digest"), "snippet_digest"),
            priority_signals=tuple(payload.get("priority_signals", ())),
            needs_reply=_require_bool(payload.get("needs_reply", False), "needs_reply"),
            has_attachment=_require_bool(payload.get("has_attachment", False), "has_attachment"),
        )

    def summary_item(self) -> dict[str, Any]:
        """Return a JSON-ready redacted message summary item."""
        return {
            "message_ref": self.message_ref,
            "received_at": self.received_at,
            "sender_label": self.sender_label,
            "subject_digest": self.subject_digest,
            "snippet_digest": self.snippet_digest,
            "priority_signals": list(self.priority_signals),
            "needs_reply": self.needs_reply,
            "has_attachment": self.has_attachment,
        }


@dataclass(frozen=True, slots=True)
class RedactedCalendarEvent:
    """Operator-visible redacted calendar event projection."""

    event_ref: str
    starts_at: str
    ends_at: str
    title_digest: str
    organizer_label: str
    location_label: str
    attendee_count: int
    conflict_ref: str = ""
    preparation_signals: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_ref", _require_projection_text(self.event_ref, "event_ref"))
        object.__setattr__(self, "starts_at", _require_projection_text(self.starts_at, "starts_at"))
        object.__setattr__(self, "ends_at", _require_projection_text(self.ends_at, "ends_at"))
        object.__setattr__(self, "title_digest", _require_projection_text(self.title_digest, "title_digest"))
        object.__setattr__(self, "organizer_label", _require_projection_text(self.organizer_label, "organizer_label"))
        object.__setattr__(
            self,
            "location_label",
            _require_projection_text(self.location_label, "location_label", allow_empty=True),
        )
        if not isinstance(self.attendee_count, int) or self.attendee_count < 0:
            raise PersonalAssistantInvariantError("attendee_count must be a non-negative integer")
        object.__setattr__(
            self,
            "conflict_ref",
            _require_projection_text(self.conflict_ref, "conflict_ref", allow_empty=True),
        )
        object.__setattr__(
            self,
            "preparation_signals",
            _projection_text_tuple(self.preparation_signals, "preparation_signals", allow_empty=True),
        )

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "RedactedCalendarEvent":
        """Build one calendar event projection from a mapping."""
        _assert_projection_mapping(payload, _CALENDAR_ALLOWED_FIELDS, "calendar event")
        return RedactedCalendarEvent(
            event_ref=_require_projection_text(payload.get("event_ref"), "event_ref"),
            starts_at=_require_projection_text(payload.get("starts_at"), "starts_at"),
            ends_at=_require_projection_text(payload.get("ends_at"), "ends_at"),
            title_digest=_require_projection_text(payload.get("title_digest"), "title_digest"),
            organizer_label=_require_projection_text(payload.get("organizer_label"), "organizer_label"),
            location_label=_require_projection_text(payload.get("location_label", ""), "location_label", allow_empty=True),
            attendee_count=_require_non_negative_int(payload.get("attendee_count", 0), "attendee_count"),
            conflict_ref=_require_projection_text(payload.get("conflict_ref", ""), "conflict_ref", allow_empty=True),
            preparation_signals=tuple(payload.get("preparation_signals", ())),
        )

    def summary_item(self) -> dict[str, Any]:
        """Return a JSON-ready redacted event summary item."""
        return {
            "event_ref": self.event_ref,
            "starts_at": self.starts_at,
            "ends_at": self.ends_at,
            "title_digest": self.title_digest,
            "organizer_label": self.organizer_label,
            "location_label": self.location_label,
            "attendee_count": self.attendee_count,
            "conflict_ref": self.conflict_ref,
            "preparation_signals": list(self.preparation_signals),
        }


@dataclass(frozen=True, slots=True)
class ReadOnlyAssistantProjection:
    """Read-only summary plus governed receipt for one skill projection."""

    request_id: str
    skill_id: str
    summary: Mapping[str, Any]
    receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_projection_text(self.request_id, "request_id"))
        object.__setattr__(self, "skill_id", _require_projection_text(self.skill_id, "skill_id"))
        if not isinstance(self.summary, Mapping):
            raise PersonalAssistantInvariantError("summary must be a mapping")
        if not isinstance(self.receipt, Mapping):
            raise PersonalAssistantInvariantError("receipt must be a mapping")
        object.__setattr__(self, "summary", MappingProxyType(dict(self.summary)))
        object.__setattr__(self, "receipt", MappingProxyType(dict(self.receipt)))

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready projection envelope."""
        return {
            "request_id": self.request_id,
            "skill_id": self.skill_id,
            "summary": dict(self.summary),
            "receipt": dict(self.receipt),
        }


def summarize_inbox_read_only(
    intent: GovernedIntent,
    messages: Sequence[RedactedInboxMessage | Mapping[str, Any]],
    *,
    generated_at: str,
    registry: PersonalAssistantSkillRegistry | None = None,
) -> ReadOnlyAssistantProjection:
    """Summarize redacted inbox projections without mailbox mutation."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(INBOX_SUMMARY_SKILL_ID)
    _assert_intent_admits_read_only_projection(intent, INBOX_SUMMARY_SKILL_ID, "gmail")
    redacted_messages = _inbox_message_tuple(messages)
    summary = _inbox_summary(redacted_messages)
    receipt = _read_only_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        connectors_used=("gmail",),
        generated_at=generated_at,
        actions_taken=("redacted_inbox_projection_read", "inbox_summary_generated", "receipt_created"),
        actions_not_taken=_BLOCKED_INBOX_ACTIONS,
        redactions=("email_body_private", "sender_identity_label_only", "message_refs_operator_scoped"),
        connector_payload_projection="redacted_summary",
        body_projection="redacted_summary",
        evidence_kind="inbox",
        metadata={
            "message_count": len(redacted_messages),
            "urgent_count": summary["urgent_count"],
            "needs_reply_count": summary["needs_reply_count"],
            "has_attachment_count": summary["has_attachment_count"],
        },
    )
    return ReadOnlyAssistantProjection(intent.request_id, skill.skill_id, summary, receipt)


def summarize_calendar_day_read_only(
    intent: GovernedIntent,
    events: Sequence[RedactedCalendarEvent | Mapping[str, Any]],
    *,
    generated_at: str,
    registry: PersonalAssistantSkillRegistry | None = None,
) -> ReadOnlyAssistantProjection:
    """Summarize redacted calendar projections without calendar mutation."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(CALENDAR_DAY_BRIEF_SKILL_ID)
    _assert_intent_admits_read_only_projection(intent, CALENDAR_DAY_BRIEF_SKILL_ID, "google_calendar")
    redacted_events = _calendar_event_tuple(events)
    summary = _calendar_summary(redacted_events)
    receipt = _read_only_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        connectors_used=("google_calendar",),
        generated_at=generated_at,
        actions_taken=("redacted_calendar_projection_read", "calendar_day_brief_generated", "receipt_created"),
        actions_not_taken=_BLOCKED_CALENDAR_ACTIONS,
        redactions=("calendar_event_body_private", "attendee_identity_count_only", "event_refs_operator_scoped"),
        connector_payload_projection="redacted_summary",
        body_projection="redacted_summary",
        evidence_kind="calendar",
        metadata={
            "event_count": len(redacted_events),
            "conflict_count": summary["conflict_count"],
            "needs_preparation_count": summary["needs_preparation_count"],
        },
    )
    return ReadOnlyAssistantProjection(intent.request_id, skill.skill_id, summary, receipt)


def _assert_intent_admits_read_only_projection(
    intent: GovernedIntent,
    skill_id: str,
    connector_name: str,
) -> None:
    if skill_id not in intent.requested_skill_ids:
        raise PersonalAssistantInvariantError(f"{skill_id} is not requested by intent {intent.request_id}")
    if intent.execution_mode is RequestExecutionMode.BLOCKED or intent.missing_bindings:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing bindings block read-only projection")
    connector_ref = next(
        (connector for connector in intent.connector_refs if connector.connector_name == connector_name),
        None,
    )
    if connector_ref is None:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing {connector_name} connector proof")
    if connector_ref.proof_state != "Pass" or not connector_ref.private_data_allowed:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: {connector_name} connector proof must pass")


def _inbox_summary(messages: tuple[RedactedInboxMessage, ...]) -> dict[str, Any]:
    urgent_items = tuple(message for message in messages if _has_priority_signal(message.priority_signals))
    needs_reply_items = tuple(message for message in messages if message.needs_reply)
    attachment_items = tuple(message for message in messages if message.has_attachment)
    ordered_items = tuple(urgent_items + tuple(message for message in messages if message not in urgent_items))
    return {
        "summary_type": "inbox_read_only",
        "message_count": len(messages),
        "urgent_count": len(urgent_items),
        "needs_reply_count": len(needs_reply_items),
        "has_attachment_count": len(attachment_items),
        "top_items": [message.summary_item() for message in ordered_items[:5]],
        "effect_boundary": "read_only_no_mailbox_mutation",
    }


def _calendar_summary(events: tuple[RedactedCalendarEvent, ...]) -> dict[str, Any]:
    conflict_items = tuple(event for event in events if event.conflict_ref)
    preparation_items = tuple(event for event in events if event.preparation_signals)
    return {
        "summary_type": "calendar_day_read_only",
        "event_count": len(events),
        "conflict_count": len(conflict_items),
        "needs_preparation_count": len(preparation_items),
        "events": [event.summary_item() for event in events[:8]],
        "effect_boundary": "read_only_no_calendar_mutation",
    }


def _read_only_receipt(
    *,
    intent: GovernedIntent,
    skill_id: str,
    risk_level: str,
    connectors_used: tuple[str, ...],
    generated_at: str,
    actions_taken: tuple[str, ...],
    actions_not_taken: tuple[str, ...],
    redactions: tuple[str, ...],
    connector_payload_projection: str,
    body_projection: str,
    evidence_kind: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    timestamp = _require_projection_text(generated_at, "generated_at")
    suffix = _request_suffix(intent.request_id)
    return {
        "receipt_id": f"pa_receipt_{suffix}_{_safe_identifier(skill_id)}",
        "request_id": intent.request_id,
        "skill_id": skill_id,
        "mode": "preview",
        "risk_level": risk_level,
        "inputs_used": [f"{evidence_kind}_redacted_projection", "connector_proof_ref"],
        "connectors_used": list(connectors_used),
        "decision": "allowed",
        "approval_required": False,
        "approval_ref": "",
        "actions_taken": list(actions_taken),
        "actions_not_taken": list(actions_not_taken),
        "redactions": list(redactions),
        "private_payload_policy": {
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": connector_payload_projection,
            "body_projection": body_projection,
        },
        "timestamp": timestamp,
        "evidence_refs": _receipt_evidence_refs(intent, evidence_kind),
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/{evidence_kind}/{suffix}"],
        "outcome": "SolvedVerified",
        "metadata": {
            **dict(metadata),
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "source_projection": "operator_supplied_redacted_projection",
        },
    }


def _receipt_evidence_refs(intent: GovernedIntent, evidence_kind: str) -> list[str]:
    refs: list[str] = []
    for evidence_ref in intent.evidence_refs:
        if evidence_ref not in refs:
            refs.append(evidence_ref)
    projection_ref = f"proof://personal-assistant/read-only/{evidence_kind}/{_request_suffix(intent.request_id)}"
    if projection_ref not in refs:
        refs.append(projection_ref)
    return refs


def _inbox_message_tuple(
    messages: Sequence[RedactedInboxMessage | Mapping[str, Any]],
) -> tuple[RedactedInboxMessage, ...]:
    if isinstance(messages, (str, bytes)) or not isinstance(messages, Sequence):
        raise PersonalAssistantInvariantError("messages must be a sequence")
    return tuple(
        message if isinstance(message, RedactedInboxMessage) else RedactedInboxMessage.from_mapping(message)
        for message in messages
    )


def _calendar_event_tuple(
    events: Sequence[RedactedCalendarEvent | Mapping[str, Any]],
) -> tuple[RedactedCalendarEvent, ...]:
    if isinstance(events, (str, bytes)) or not isinstance(events, Sequence):
        raise PersonalAssistantInvariantError("events must be a sequence")
    return tuple(
        event if isinstance(event, RedactedCalendarEvent) else RedactedCalendarEvent.from_mapping(event)
        for event in events
    )


def _assert_projection_mapping(payload: Mapping[str, Any], allowed_fields: frozenset[str], label: str) -> None:
    if not isinstance(payload, Mapping):
        raise PersonalAssistantInvariantError(f"{label} projection must be a mapping")
    for key in payload:
        key_text = str(key)
        normalized_key = key_text.lower()
        if any(fragment in normalized_key for fragment in _RAW_PRIVATE_FIELD_FRAGMENTS):
            raise PersonalAssistantInvariantError(f"{label} projection contains forbidden private field {key_text}")
        if key_text not in allowed_fields:
            raise PersonalAssistantInvariantError(f"{label} projection contains unsupported field {key_text}")


def _projection_text_tuple(values: Sequence[Any], field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    for index, value in enumerate(values):
        item = _require_projection_text(value, f"{field_name}[{index}]")
        if item not in normalized:
            normalized.append(item)
    if not normalized and not allow_empty:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _require_projection_text(value: Any, field_name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise PersonalAssistantInvariantError(f"{field_name} must be a string")
    if not allow_empty and not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    if _contains_secret_like_value(value):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain secret-like values")
    return value


def _require_bool(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise PersonalAssistantInvariantError(f"{field_name} must be a boolean")
    return value


def _require_non_negative_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-negative integer")
    return value


def _contains_secret_like_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


def _has_priority_signal(signals: tuple[str, ...]) -> bool:
    normalized_signals = {signal.lower() for signal in signals}
    return bool({"urgent", "important", "deadline", "blocked", "needs_reply"}.intersection(normalized_signals))


def _request_suffix(request_id: str) -> str:
    return _safe_identifier(request_id.removeprefix("pa_request_"))


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_:-]+", "_", value.lower()).strip("_") or "projection"
