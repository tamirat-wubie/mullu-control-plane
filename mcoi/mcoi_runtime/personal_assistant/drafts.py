"""Purpose: draft-only personal-assistant artifact projections.
Governance scope: email response drafts, calendar event drafts, task draft
proposals, connector proof checks, receipt emission, and no-effect guarantees.
Dependencies: personal-assistant intake, registry contracts, and standard regex.
Invariants:
  - Draft helpers do not call live connectors or write to systems of record.
  - Email and calendar drafts require passing private connector proof.
  - Task drafts remain connector-free and memory-write-free.
  - Receipts record both draft creation and effect-bearing actions not taken.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .intake import GovernedIntent, RequestExecutionMode
from .skill_registry import PersonalAssistantSkillRegistry, load_default_skill_registry


EMAIL_RESPONSE_DRAFT_SKILL_ID = "email.response.draft"
CALENDAR_EVENT_DRAFT_SKILL_ID = "calendar.event.draft"
TASK_CREATE_DRAFT_SKILL_ID = "task.create_draft"
DRAFT_ASSISTANT_READ_MODEL_ROUTE = "/api/v1/personal-assistant/drafts"
EMAIL_DRAFT_PREVIEW_ROUTE = "/api/v1/personal-assistant/drafts/email/preview"
CALENDAR_DRAFT_PREVIEW_ROUTE = "/api/v1/personal-assistant/drafts/calendar/preview"
TASK_DRAFT_PREVIEW_ROUTE = "/api/v1/personal-assistant/drafts/task/preview"

_EMAIL_DRAFT_ALLOWED_FIELDS = frozenset(
    {
        "message_ref",
        "recipient_label",
        "sender_label",
        "subject_digest",
        "thread_summary_digest",
        "response_goal",
        "tone",
        "constraints",
    }
)
_CALENDAR_DRAFT_ALLOWED_FIELDS = frozenset(
    {
        "meeting_goal",
        "title_digest",
        "proposed_window",
        "duration_minutes",
        "attendee_labels",
        "location_label",
        "agenda_digest",
        "constraints",
    }
)
_TASK_DRAFT_ALLOWED_FIELDS = frozenset(
    {
        "task_goal",
        "source_ref",
        "title_digest",
        "priority",
        "due_hint",
        "acceptance_digest",
        "constraints",
    }
)
_FORBIDDEN_PRIVATE_FIELD_FRAGMENTS = (
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
_EMAIL_ACTIONS_NOT_TAKEN = (
    "email_not_sent",
    "email_not_forwarded",
    "email_not_archived",
    "email_not_deleted",
    "connector_state_not_mutated",
)
_CALENDAR_ACTIONS_NOT_TAKEN = (
    "calendar_event_not_created",
    "calendar_event_not_moved",
    "calendar_event_not_canceled",
    "people_not_invited",
    "connector_state_not_mutated",
)
_TASK_ACTIONS_NOT_TAKEN = (
    "task_not_written",
    "system_of_record_not_mutated",
    "memory_not_written",
    "external_submission_not_performed",
    "connector_state_not_mutated",
)


def build_draft_assistant_read_model(*, generated_at: str) -> dict[str, Any]:
    """Return the draft-only assistant route and authority read model.

    Input contract: caller supplies a non-empty generation timestamp. Output
    contract: JSON-safe read model for draft-only routes. Error contract:
    raises PersonalAssistantInvariantError for malformed timestamps.
    """

    timestamp = _require_text(generated_at, "generated_at")
    return {
        "read_model_id": "personal_assistant_draft_only_read_model",
        "generated_at": timestamp,
        "governed": True,
        "status": "draft_only_available",
        "solver_outcome": "SolvedVerified",
        "routes": {
            "read_model": DRAFT_ASSISTANT_READ_MODEL_ROUTE,
            "email_preview": EMAIL_DRAFT_PREVIEW_ROUTE,
            "calendar_preview": CALENDAR_DRAFT_PREVIEW_ROUTE,
            "task_preview": TASK_DRAFT_PREVIEW_ROUTE,
        },
        "draft_skills": [
            {
                "skill_id": EMAIL_RESPONSE_DRAFT_SKILL_ID,
                "draft_type": "email_response",
                "connector_required": "gmail",
                "approval_required_before_effect": True,
            },
            {
                "skill_id": CALENDAR_EVENT_DRAFT_SKILL_ID,
                "draft_type": "calendar_event",
                "connector_required": "google_calendar",
                "approval_required_before_effect": True,
            },
            {
                "skill_id": TASK_CREATE_DRAFT_SKILL_ID,
                "draft_type": "task",
                "connector_required": "",
                "approval_required_before_effect": True,
            },
        ],
        "effect_boundary": {
            "draft_preparation_allowed": True,
            "execution_allowed": False,
            "live_connector_execution_allowed": False,
            "mailbox_mutation_allowed": False,
            "external_send_allowed": False,
            "calendar_write_allowed": False,
            "task_write_allowed": False,
            "memory_write_allowed": False,
            "connector_mutation_allowed": False,
            "system_of_record_write_allowed": False,
            "deployment_mutation_allowed": False,
            "public_readiness_claim_allowed": False,
        },
        "private_payload_policy": {
            "input_source": "operator_supplied_redacted_projection",
            "raw_private_payload_serialized": False,
            "secret_values_serialized": False,
            "connector_payload_projection": "redacted_summary_or_none",
            "body_projection": "operator_visible_draft",
        },
        "blocked_actions": [
            "send_email",
            "forward_email",
            "archive_email",
            "delete_email",
            "create_calendar_event",
            "move_calendar_event",
            "cancel_calendar_event",
            "invite_people",
            "write_task",
            "write_memory",
            "mutate_connector_state",
            "write_system_of_record",
            "serialize_raw_private_payload",
            "serialize_secret_values",
        ],
        "receipt_required": True,
        "approval_queue_required_before_effect": True,
        "next_action": "bind approved draft actions through approval queue before any send, invite, or system write",
    }


@dataclass(frozen=True, slots=True)
class EmailDraftInput:
    """Redacted source projection for an email response draft."""

    message_ref: str
    recipient_label: str
    sender_label: str
    subject_digest: str
    thread_summary_digest: str
    response_goal: str
    tone: str = "clear"
    constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "message_ref", _require_text(self.message_ref, "message_ref"))
        object.__setattr__(self, "recipient_label", _require_text(self.recipient_label, "recipient_label"))
        object.__setattr__(self, "sender_label", _require_text(self.sender_label, "sender_label"))
        object.__setattr__(self, "subject_digest", _require_text(self.subject_digest, "subject_digest"))
        object.__setattr__(
            self,
            "thread_summary_digest",
            _require_text(self.thread_summary_digest, "thread_summary_digest"),
        )
        object.__setattr__(self, "response_goal", _require_text(self.response_goal, "response_goal"))
        object.__setattr__(self, "tone", _require_text(self.tone, "tone"))
        object.__setattr__(self, "constraints", _text_tuple(self.constraints, "constraints", allow_empty=True))

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "EmailDraftInput":
        """Build a redacted email draft input from a mapping."""
        _assert_projection_mapping(payload, _EMAIL_DRAFT_ALLOWED_FIELDS, "email draft")
        return EmailDraftInput(
            message_ref=_require_text(payload.get("message_ref"), "message_ref"),
            recipient_label=_require_text(payload.get("recipient_label"), "recipient_label"),
            sender_label=_require_text(payload.get("sender_label"), "sender_label"),
            subject_digest=_require_text(payload.get("subject_digest"), "subject_digest"),
            thread_summary_digest=_require_text(payload.get("thread_summary_digest"), "thread_summary_digest"),
            response_goal=_require_text(payload.get("response_goal"), "response_goal"),
            tone=_require_text(payload.get("tone", "clear"), "tone"),
            constraints=_text_tuple(payload.get("constraints", ()), "constraints", allow_empty=True),
        )


@dataclass(frozen=True, slots=True)
class CalendarEventDraftInput:
    """Redacted source projection for a calendar event draft."""

    meeting_goal: str
    title_digest: str
    proposed_window: str
    duration_minutes: int
    attendee_labels: tuple[str, ...] = ()
    location_label: str = ""
    agenda_digest: str = ""
    constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "meeting_goal", _require_text(self.meeting_goal, "meeting_goal"))
        object.__setattr__(self, "title_digest", _require_text(self.title_digest, "title_digest"))
        object.__setattr__(self, "proposed_window", _require_text(self.proposed_window, "proposed_window"))
        if not isinstance(self.duration_minutes, int) or self.duration_minutes <= 0:
            raise PersonalAssistantInvariantError("duration_minutes must be a positive integer")
        object.__setattr__(
            self,
            "attendee_labels",
            _text_tuple(self.attendee_labels, "attendee_labels", allow_empty=True),
        )
        object.__setattr__(self, "location_label", _require_text(self.location_label, "location_label", allow_empty=True))
        object.__setattr__(self, "agenda_digest", _require_text(self.agenda_digest, "agenda_digest", allow_empty=True))
        object.__setattr__(self, "constraints", _text_tuple(self.constraints, "constraints", allow_empty=True))

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "CalendarEventDraftInput":
        """Build a redacted calendar draft input from a mapping."""
        _assert_projection_mapping(payload, _CALENDAR_DRAFT_ALLOWED_FIELDS, "calendar draft")
        return CalendarEventDraftInput(
            meeting_goal=_require_text(payload.get("meeting_goal"), "meeting_goal"),
            title_digest=_require_text(payload.get("title_digest"), "title_digest"),
            proposed_window=_require_text(payload.get("proposed_window"), "proposed_window"),
            duration_minutes=_require_positive_int(payload.get("duration_minutes"), "duration_minutes"),
            attendee_labels=_text_tuple(payload.get("attendee_labels", ()), "attendee_labels", allow_empty=True),
            location_label=_require_text(payload.get("location_label", ""), "location_label", allow_empty=True),
            agenda_digest=_require_text(payload.get("agenda_digest", ""), "agenda_digest", allow_empty=True),
            constraints=_text_tuple(payload.get("constraints", ()), "constraints", allow_empty=True),
        )


@dataclass(frozen=True, slots=True)
class TaskDraftInput:
    """Source projection for a task draft proposal."""

    task_goal: str
    source_ref: str
    title_digest: str
    priority: str
    due_hint: str = ""
    acceptance_digest: str = ""
    constraints: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_goal", _require_text(self.task_goal, "task_goal"))
        object.__setattr__(self, "source_ref", _require_text(self.source_ref, "source_ref"))
        object.__setattr__(self, "title_digest", _require_text(self.title_digest, "title_digest"))
        object.__setattr__(self, "priority", _require_text(self.priority, "priority"))
        object.__setattr__(self, "due_hint", _require_text(self.due_hint, "due_hint", allow_empty=True))
        object.__setattr__(
            self,
            "acceptance_digest",
            _require_text(self.acceptance_digest, "acceptance_digest", allow_empty=True),
        )
        object.__setattr__(self, "constraints", _text_tuple(self.constraints, "constraints", allow_empty=True))

    @staticmethod
    def from_mapping(payload: Mapping[str, Any]) -> "TaskDraftInput":
        """Build a task draft input from a mapping."""
        _assert_projection_mapping(payload, _TASK_DRAFT_ALLOWED_FIELDS, "task draft")
        return TaskDraftInput(
            task_goal=_require_text(payload.get("task_goal"), "task_goal"),
            source_ref=_require_text(payload.get("source_ref"), "source_ref"),
            title_digest=_require_text(payload.get("title_digest"), "title_digest"),
            priority=_require_text(payload.get("priority"), "priority"),
            due_hint=_require_text(payload.get("due_hint", ""), "due_hint", allow_empty=True),
            acceptance_digest=_require_text(payload.get("acceptance_digest", ""), "acceptance_digest", allow_empty=True),
            constraints=_text_tuple(payload.get("constraints", ()), "constraints", allow_empty=True),
        )


@dataclass(frozen=True, slots=True)
class DraftAssistantProjection:
    """Draft artifact plus governed receipt for one draft-only skill."""

    request_id: str
    skill_id: str
    draft: Mapping[str, Any]
    receipt: Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _require_text(self.request_id, "request_id"))
        object.__setattr__(self, "skill_id", _require_text(self.skill_id, "skill_id"))
        if not isinstance(self.draft, Mapping):
            raise PersonalAssistantInvariantError("draft must be a mapping")
        if not isinstance(self.receipt, Mapping):
            raise PersonalAssistantInvariantError("receipt must be a mapping")
        object.__setattr__(self, "draft", MappingProxyType(dict(self.draft)))
        object.__setattr__(self, "receipt", MappingProxyType(dict(self.receipt)))

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready draft envelope."""
        return {
            "request_id": self.request_id,
            "skill_id": self.skill_id,
            "draft": dict(self.draft),
            "receipt": dict(self.receipt),
        }


def draft_email_response(
    intent: GovernedIntent,
    draft_input: EmailDraftInput | Mapping[str, Any],
    *,
    generated_at: str,
    registry: PersonalAssistantSkillRegistry | None = None,
) -> DraftAssistantProjection:
    """Prepare an email response draft without sending or mailbox mutation."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(EMAIL_RESPONSE_DRAFT_SKILL_ID)
    _assert_intent_admits_draft(intent, EMAIL_RESPONSE_DRAFT_SKILL_ID, "gmail")
    source = draft_input if isinstance(draft_input, EmailDraftInput) else EmailDraftInput.from_mapping(draft_input)
    draft = _email_draft(source)
    receipt = _draft_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        connectors_used=("gmail",),
        generated_at=generated_at,
        actions_taken=("redacted_email_context_read", "email_response_draft_prepared", "receipt_created"),
        actions_not_taken=_EMAIL_ACTIONS_NOT_TAKEN,
        redactions=("email_body_private", "recipient_identity_label_only", "thread_digest_only"),
        connector_payload_projection="redacted_summary",
        evidence_kind="email",
        metadata={
            "message_ref": source.message_ref,
            "approval_required_before_external_action": True,
            "draft_length_chars": len(draft["body"]),
        },
    )
    return DraftAssistantProjection(intent.request_id, skill.skill_id, draft, receipt)


def draft_calendar_event(
    intent: GovernedIntent,
    draft_input: CalendarEventDraftInput | Mapping[str, Any],
    *,
    generated_at: str,
    registry: PersonalAssistantSkillRegistry | None = None,
) -> DraftAssistantProjection:
    """Prepare a calendar event draft without creating or inviting."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(CALENDAR_EVENT_DRAFT_SKILL_ID)
    _assert_intent_admits_draft(intent, CALENDAR_EVENT_DRAFT_SKILL_ID, "google_calendar")
    source = (
        draft_input
        if isinstance(draft_input, CalendarEventDraftInput)
        else CalendarEventDraftInput.from_mapping(draft_input)
    )
    draft = _calendar_draft(source)
    receipt = _draft_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        connectors_used=("google_calendar",),
        generated_at=generated_at,
        actions_taken=("redacted_calendar_context_read", "calendar_event_draft_prepared", "receipt_created"),
        actions_not_taken=_CALENDAR_ACTIONS_NOT_TAKEN,
        redactions=("calendar_event_body_private", "attendee_identity_label_only", "calendar_payload_not_serialized"),
        connector_payload_projection="redacted_summary",
        evidence_kind="calendar",
        metadata={
            "duration_minutes": source.duration_minutes,
            "attendee_count": len(source.attendee_labels),
            "approval_required_before_external_action": True,
        },
    )
    return DraftAssistantProjection(intent.request_id, skill.skill_id, draft, receipt)


def draft_task(
    intent: GovernedIntent,
    draft_input: TaskDraftInput | Mapping[str, Any],
    *,
    generated_at: str,
    registry: PersonalAssistantSkillRegistry | None = None,
) -> DraftAssistantProjection:
    """Prepare a task draft without writing task state or memory."""
    skill_registry = registry or load_default_skill_registry()
    skill = skill_registry.get(TASK_CREATE_DRAFT_SKILL_ID)
    _assert_intent_admits_draft(intent, TASK_CREATE_DRAFT_SKILL_ID, None)
    source = draft_input if isinstance(draft_input, TaskDraftInput) else TaskDraftInput.from_mapping(draft_input)
    draft = _task_draft(source)
    receipt = _draft_receipt(
        intent=intent,
        skill_id=skill.skill_id,
        risk_level=skill.risk_level.value,
        connectors_used=(),
        generated_at=generated_at,
        actions_taken=("task_goal_interpreted", "task_draft_prepared", "receipt_created"),
        actions_not_taken=_TASK_ACTIONS_NOT_TAKEN,
        redactions=("task_source_digest_only", "task_system_payload_not_serialized"),
        connector_payload_projection="no_connector_payload",
        evidence_kind="task",
        metadata={
            "priority": source.priority,
            "approval_required_before_system_write": True,
            "task_write_allowed": False,
        },
    )
    return DraftAssistantProjection(intent.request_id, skill.skill_id, draft, receipt)


def _email_draft(source: EmailDraftInput) -> dict[str, Any]:
    constraints = "; ".join(source.constraints) if source.constraints else "none"
    body = (
        f"Hi {source.recipient_label},\n\n"
        f"{source.response_goal}\n\n"
        f"Context used: {source.thread_summary_digest}.\n"
        f"Constraints: {constraints}.\n\n"
        "I will wait for explicit approval before this is sent."
    )
    return {
        "draft_type": "email_response",
        "message_ref": source.message_ref,
        "recipient_label": source.recipient_label,
        "subject_line": f"Re: {source.subject_digest}",
        "tone": source.tone,
        "body": body,
        "effect_boundary": "draft_only_email_not_sent",
        "approval_required_before_send": True,
    }


def _calendar_draft(source: CalendarEventDraftInput) -> dict[str, Any]:
    return {
        "draft_type": "calendar_event",
        "title_digest": source.title_digest,
        "meeting_goal": source.meeting_goal,
        "proposed_window": source.proposed_window,
        "duration_minutes": source.duration_minutes,
        "attendee_labels": list(source.attendee_labels),
        "location_label": source.location_label,
        "agenda_digest": source.agenda_digest,
        "constraints": list(source.constraints),
        "effect_boundary": "draft_only_event_not_created",
        "approval_required_before_create_or_invite": True,
    }


def _task_draft(source: TaskDraftInput) -> dict[str, Any]:
    return {
        "draft_type": "task",
        "title_digest": source.title_digest,
        "task_goal": source.task_goal,
        "source_ref": source.source_ref,
        "priority": source.priority,
        "due_hint": source.due_hint,
        "acceptance_digest": source.acceptance_digest,
        "constraints": list(source.constraints),
        "effect_boundary": "draft_only_task_not_written",
        "approval_required_before_task_write": True,
    }


def _assert_intent_admits_draft(
    intent: GovernedIntent,
    skill_id: str,
    connector_name: str | None,
) -> None:
    if skill_id not in intent.requested_skill_ids:
        raise PersonalAssistantInvariantError(f"{skill_id} is not requested by intent {intent.request_id}")
    if intent.execution_mode is RequestExecutionMode.BLOCKED or intent.missing_bindings:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing bindings block draft projection")
    if connector_name is None:
        return
    connector_ref = next(
        (connector for connector in intent.connector_refs if connector.connector_name == connector_name),
        None,
    )
    if connector_ref is None:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: missing {connector_name} connector proof")
    if connector_ref.proof_state != "Pass" or not connector_ref.private_data_allowed:
        raise PersonalAssistantInvariantError(f"{intent.request_id}: {connector_name} connector proof must pass")


def _draft_receipt(
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
    evidence_kind: str,
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    timestamp = _require_text(generated_at, "generated_at")
    suffix = _request_suffix(intent.request_id)
    inputs_used = [f"{evidence_kind}_draft_redacted_projection"]
    if connectors_used:
        inputs_used.append("connector_proof_ref")
    return {
        "receipt_id": f"pa_receipt_{suffix}_{_safe_identifier(skill_id)}",
        "request_id": intent.request_id,
        "skill_id": skill_id,
        "mode": "draft",
        "risk_level": risk_level,
        "inputs_used": inputs_used,
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
            "body_projection": "operator_visible_draft",
        },
        "timestamp": timestamp,
        "evidence_refs": _receipt_evidence_refs(intent, evidence_kind),
        "memory_observation_refs": [],
        "replay_refs": [f"replay://personal-assistant/draft/{evidence_kind}/{suffix}"],
        "outcome": "SolvedVerified",
        "metadata": {
            **dict(metadata),
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_write_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
            "source_projection": "operator_supplied_redacted_projection",
        },
    }


def _receipt_evidence_refs(intent: GovernedIntent, evidence_kind: str) -> list[str]:
    refs: list[str] = []
    for evidence_ref in intent.evidence_refs:
        if evidence_ref not in refs:
            refs.append(evidence_ref)
    projection_ref = f"proof://personal-assistant/draft/{evidence_kind}/{_request_suffix(intent.request_id)}"
    if projection_ref not in refs:
        refs.append(projection_ref)
    return refs


def _assert_projection_mapping(payload: Mapping[str, Any], allowed_fields: frozenset[str], label: str) -> None:
    if not isinstance(payload, Mapping):
        raise PersonalAssistantInvariantError(f"{label} projection must be a mapping")
    for key in payload:
        key_text = str(key)
        normalized_key = key_text.lower()
        if any(fragment in normalized_key for fragment in _FORBIDDEN_PRIVATE_FIELD_FRAGMENTS):
            raise PersonalAssistantInvariantError(f"{label} projection contains forbidden private field {key_text}")
        if key_text not in allowed_fields:
            raise PersonalAssistantInvariantError(f"{label} projection contains unsupported field {key_text}")


def _text_tuple(values: Sequence[Any], field_name: str, *, allow_empty: bool) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise PersonalAssistantInvariantError(f"{field_name} must be a sequence")
    normalized: list[str] = []
    for index, value in enumerate(values):
        item = _require_text(value, f"{field_name}[{index}]")
        if item not in normalized:
            normalized.append(item)
    if not normalized and not allow_empty:
        raise PersonalAssistantInvariantError(f"{field_name} must contain at least one item")
    return tuple(normalized)


def _require_text(value: Any, field_name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise PersonalAssistantInvariantError(f"{field_name} must be a string")
    if not allow_empty and not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    if _contains_secret_like_value(value):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain secret-like values")
    return value


def _require_positive_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or value <= 0:
        raise PersonalAssistantInvariantError(f"{field_name} must be a positive integer")
    return value


def _contains_secret_like_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS)


def _request_suffix(request_id: str) -> str:
    return _safe_identifier(request_id.removeprefix("pa_request_"))


def _safe_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9_:-]+", "_", value.lower()).strip("_") or "projection"
