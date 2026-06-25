"""Purpose: runtime draft-only projection-set envelopes for personal assistant.
Governance scope: PR5 draft evidence composition, approval separation, receipt
alignment, private-payload redaction, and no-effect authority boundaries.
Dependencies: personal-assistant intake and draft-only projection helpers.
Invariants:
  - This module does not call live connectors or write systems of record.
  - Inputs are draft-only projections, never raw connector payloads.
  - Draft preparation is allowed; execution, sends, writes, and mutation are
    false until a separate approval and execution lane exists.
  - Receipt drift, duplicate draft identity, raw payload fields, and
    secret-like values are rejected before envelope emission.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .drafts import (
    CalendarEventDraftInput,
    DraftAssistantProjection,
    EmailDraftInput,
    TaskDraftInput,
    draft_calendar_event,
    draft_email_response,
    draft_task,
)
from .intake import ConnectorProofRef, interpret_user_request


DEFAULT_DRAFT_PROJECTION_SET_ID = "pa_draft_projection_foundation_001"
DEFAULT_DRAFT_PROJECTION_GENERATED_AT = "2026-06-14T00:02:00+00:00"

_DRAFT_SET_ID_PATTERN = re.compile(r"^pa_draft_projection_[a-z0-9][a-z0-9_:-]*$")
_DRAFT_ID_PATTERN = re.compile(r"^pa_draft_projection_item_[a-z0-9][a-z0-9_:-]*$")
_RECEIPT_ID_PATTERN = re.compile(r"^pa_receipt_[a-z0-9][a-z0-9_:-]*$")
_REQUEST_ID_PATTERN = re.compile(r"^pa_request_[a-z0-9][a-z0-9_:-]*$")
_ALLOWED_CONNECTORS = frozenset({"gmail", "google_calendar"})
_SKILL_DRAFT_BOUNDARY = {
    "email.response.draft": ("email_response", "draft_only_email_not_sent", "approval_required_before_send"),
    "calendar.event.draft": (
        "calendar_event",
        "draft_only_event_not_created",
        "approval_required_before_create_or_invite",
    ),
    "task.create_draft": ("task", "draft_only_task_not_written", "approval_required_before_task_write"),
}
_EFFECT_BOUNDARY = {
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
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "connector_payload_projection": "mixed_redacted_or_no_connector",
    "body_projection": "operator_visible_draft",
}
_RAW_PRIVATE_FIELD_NAMES = frozenset(
    {
        "raw_private_connector_payload",
        "raw_connector_payload",
        "private_connector_payload",
        "connector_response",
        "message_body",
        "email_body",
        "calendar_payload",
        "mailbox_payload",
        "raw_message",
        "raw_thread",
        "raw_calendar_event",
        "raw_task_payload",
        "raw_chat_log",
        "chat_log",
        "transcript",
        "credential",
        "credentials",
        "token",
        "secret",
        "private_key",
        "authorization",
        "cookie",
    }
)
_ALLOWED_POLICY_FIELD_NAMES = frozenset(
    {
        "private_payload_policy",
        "raw_private_payload_serialized",
        "secret_values_serialized",
        "connector_payload_projection",
        "body_projection",
    }
)
_SECRET_VALUE_PATTERNS = (
    re.compile(r"sk_live_[A-Za-z0-9]+"),
    re.compile(r"ghp_[A-Za-z0-9]+"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]+"),
    re.compile(r"ya29\.[A-Za-z0-9._-]+"),
    re.compile(r"Bearer\s+[A-Za-z0-9._-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"secret-(?:token|worker|key)-value", re.IGNORECASE),
)


def build_personal_assistant_draft_projection_envelope(
    *,
    generated_at: str,
    drafts: Sequence[tuple[str, DraftAssistantProjection | Mapping[str, Any]]],
    draft_set_id: str = DEFAULT_DRAFT_PROJECTION_SET_ID,
) -> dict[str, Any]:
    """Build a governed no-effect envelope around draft-only projections."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(draft_set_id, "draft_set_id", _DRAFT_SET_ID_PATTERN)
    if isinstance(drafts, (str, bytes)) or not isinstance(drafts, Sequence):
        raise PersonalAssistantInvariantError("drafts must be a sequence")
    if not drafts:
        raise PersonalAssistantInvariantError("drafts must contain at least one draft projection")

    draft_items: list[dict[str, Any]] = []
    draft_ids: list[str] = []
    receipt_ids: list[str] = []
    connector_names: list[str] = []
    for draft_id, draft_projection in drafts:
        normalized_draft_id = _require_pattern(draft_id, "draft_id", _DRAFT_ID_PATTERN)
        if normalized_draft_id in draft_ids:
            raise PersonalAssistantInvariantError(f"duplicate draft_id {normalized_draft_id}")
        draft_ids.append(normalized_draft_id)

        projection_payload = _projection_payload(draft_projection)
        _scan_private_or_secret_payload(projection_payload, path=f"draft:{normalized_draft_id}")
        item = _draft_item(normalized_draft_id, projection_payload)
        receipt_id = item["receipt"]["receipt_id"]
        if receipt_id in receipt_ids:
            raise PersonalAssistantInvariantError(f"duplicate receipt_id {receipt_id}")
        receipt_ids.append(receipt_id)
        for connector_name in item["receipt"]["connectors_used"]:
            if connector_name not in connector_names:
                connector_names.append(connector_name)
        draft_items.append(item)

    envelope = {
        "draft_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_supplied_redacted_projection",
        "draft_count": len(draft_items),
        "draft_ids": draft_ids,
        "receipt_ids": receipt_ids,
        "connectors_used": connector_names,
        "drafts": draft_items,
        "effect_boundary": dict(_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "approval_boundary": {
            "risk_level": "P2",
            "approval_required_before_external_action": True,
            "approval_required_before_system_write": True,
            "approval_required_before_connector_mutation": True,
        },
        "assurance": {
            "assurance_id": "personal_assistant_draft_projection_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "operator_redacted_projection_only",
                "draft_preparation_only",
                "no_live_connector_execution",
                "no_external_send",
                "no_calendar_write",
                "no_task_write",
                "no_memory_write",
                "no_connector_mutation",
                "receipt_actions_not_taken_recorded",
            ],
            "blocking_reasons": [],
            "next_action": "continue approval-queue hardening before any effect-bearing draft execution",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "draft_only_redacted_evidence",
            "runtime_boundary": "no_live_connector_calls",
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
            "memory_write_allowed": False,
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def build_default_personal_assistant_draft_projection(
    *,
    generated_at: str = DEFAULT_DRAFT_PROJECTION_GENERATED_AT,
    draft_set_id: str = DEFAULT_DRAFT_PROJECTION_SET_ID,
) -> dict[str, Any]:
    """Build deterministic fixture-shaped draft evidence from redacted inputs."""
    email_intent = interpret_user_request(
        "Draft a response to this email.",
        request_id="pa_request_draft_email_001",
        submitted_at="2026-06-14T00:00:00+00:00",
        connector_refs=(
            ConnectorProofRef(
                connector_id="connector:gmail:operator",
                connector_name="gmail",
                proof_state="Pass",
                private_data_allowed=True,
                scopes=("gmail.readonly",),
            ),
        ),
    )
    calendar_intent = interpret_user_request(
        "Draft a calendar event for today.",
        request_id="pa_request_draft_calendar_001",
        submitted_at="2026-06-14T00:00:00+00:00",
        connector_refs=(
            ConnectorProofRef(
                connector_id="connector:google-calendar:operator",
                connector_name="google_calendar",
                proof_state="Pass",
                private_data_allowed=True,
                scopes=("calendar.readonly",),
            ),
        ),
    )
    task_intent = interpret_user_request(
        "Create a task draft for reviewing the release notes.",
        request_id="pa_request_draft_task_001",
        submitted_at="2026-06-14T00:00:00+00:00",
    )
    email_projection = draft_email_response(
        email_intent,
        EmailDraftInput(
            message_ref="msg:123",
            recipient_label="operator-visible recipient",
            sender_label="operator",
            subject_digest="project update digest",
            thread_summary_digest="redacted thread summary",
            response_goal="I can review the packet today and send comments tomorrow.",
            tone="direct",
            constraints=("do not promise deployment",),
        ),
        generated_at=generated_at,
    )
    calendar_projection = draft_calendar_event(
        calendar_intent,
        CalendarEventDraftInput(
            meeting_goal="Review the handoff packet.",
            title_digest="handoff review digest",
            proposed_window="2026-06-14 afternoon",
            duration_minutes=30,
            attendee_labels=("operator-visible teammate",),
            location_label="video call label",
            agenda_digest="review blockers and next action",
            constraints=("do not invite before approval",),
        ),
        generated_at=generated_at,
    )
    task_projection = draft_task(
        task_intent,
        TaskDraftInput(
            task_goal="Review release notes before the next closure step.",
            source_ref="conversation:release-notes",
            title_digest="review release notes digest",
            priority="medium",
            due_hint="next working session",
            acceptance_digest="notes reviewed and blockers recorded",
            constraints=("do not write task state before approval",),
        ),
        generated_at=generated_at,
    )
    return build_personal_assistant_draft_projection_envelope(
        generated_at=generated_at,
        draft_set_id=draft_set_id,
        drafts=(
            ("pa_draft_projection_item_email_001", email_projection),
            ("pa_draft_projection_item_calendar_001", calendar_projection),
            ("pa_draft_projection_item_task_001", task_projection),
        ),
    )


def _projection_payload(projection: DraftAssistantProjection | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(projection, DraftAssistantProjection):
        return projection.as_dict()
    if not isinstance(projection, Mapping):
        raise PersonalAssistantInvariantError("draft projection must be a draft projection or mapping")
    return dict(projection)


def _draft_item(draft_id: str, projection: Mapping[str, Any]) -> dict[str, Any]:
    request_id = _require_pattern(str(projection.get("request_id", "")), "request_id", _REQUEST_ID_PATTERN)
    skill_id = _require_non_empty_text(projection.get("skill_id"), "skill_id")
    expected_boundary = _SKILL_DRAFT_BOUNDARY.get(skill_id)
    if expected_boundary is None:
        raise PersonalAssistantInvariantError(f"unsupported draft-only skill_id {skill_id}")

    draft = _require_mapping(projection.get("draft"), "draft")
    receipt = _require_mapping(projection.get("receipt"), "receipt")
    draft_type = _require_non_empty_text(draft.get("draft_type"), "draft.draft_type")
    draft_effect_boundary = _require_non_empty_text(draft.get("effect_boundary"), "draft.effect_boundary")
    expected_type, expected_effect_boundary, approval_flag = expected_boundary
    if draft_type != expected_type or draft_effect_boundary != expected_effect_boundary:
        raise PersonalAssistantInvariantError(f"{draft_id}: draft boundary does not match skill {skill_id}")
    if draft.get(approval_flag) is not True:
        raise PersonalAssistantInvariantError(f"{draft_id}: draft.{approval_flag} must be true")

    _assert_receipt_alignment(
        draft_id=draft_id,
        request_id=request_id,
        skill_id=skill_id,
        receipt=receipt,
    )
    return {
        "draft_id": draft_id,
        "request_id": request_id,
        "skill_id": skill_id,
        "draft_type": draft_type,
        "draft": dict(draft),
        "receipt": dict(receipt),
    }


def _assert_receipt_alignment(
    *,
    draft_id: str,
    request_id: str,
    skill_id: str,
    receipt: Mapping[str, Any],
) -> None:
    receipt_id = _require_pattern(str(receipt.get("receipt_id", "")), "receipt.receipt_id", _RECEIPT_ID_PATTERN)
    if receipt.get("request_id") != request_id:
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt.request_id must match draft")
    if receipt.get("skill_id") != skill_id:
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt.skill_id must match draft")
    if receipt.get("mode") != "draft":
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt.mode must be draft")
    if receipt.get("risk_level") != "P2":
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt.risk_level must be P2")
    if receipt.get("approval_required") is not False:
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt.approval_required must be false")
    if receipt.get("decision") != "allowed":
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt.decision must be allowed")
    if not _non_empty_string_sequence(receipt.get("actions_taken")):
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt.actions_taken must be non-empty")
    if not _non_empty_string_sequence(receipt.get("actions_not_taken")):
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt.actions_not_taken must be non-empty")

    for connector_name in tuple(receipt.get("connectors_used", ())):
        if connector_name not in _ALLOWED_CONNECTORS:
            raise PersonalAssistantInvariantError(f"{draft_id}: unsupported connector {connector_name}")

    private_policy = _require_mapping(receipt.get("private_payload_policy"), "receipt.private_payload_policy")
    if private_policy.get("raw_private_payload_serialized") is not False:
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt raw private payload serialization drift")
    if private_policy.get("secret_values_serialized") is not False:
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt secret serialization drift")
    if private_policy.get("body_projection") != "operator_visible_draft":
        raise PersonalAssistantInvariantError(f"{draft_id}: receipt body_projection drift")

    metadata = _require_mapping(receipt.get("metadata"), "receipt.metadata")
    for field_name in (
        "live_connector_execution_allowed",
        "connector_mutation_allowed",
        "external_write_allowed",
        "system_of_record_write_allowed",
        "memory_write_allowed",
    ):
        if metadata.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{draft_id}: receipt.metadata.{field_name} must be false")
    _require_non_empty_text(receipt_id, "receipt.receipt_id")


def _scan_private_or_secret_payload(payload: Any, *, path: str) -> None:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).lower()
            if normalized_key not in _ALLOWED_POLICY_FIELD_NAMES and normalized_key in _RAW_PRIVATE_FIELD_NAMES:
                raise PersonalAssistantInvariantError(f"{path}.{key}: raw private or secret field is forbidden")
            _scan_private_or_secret_payload(value, path=f"{path}.{key}")
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            _scan_private_or_secret_payload(value, path=f"{path}[{index}]")
    elif isinstance(payload, str):
        if any(pattern.search(payload) for pattern in _SECRET_VALUE_PATTERNS):
            raise PersonalAssistantInvariantError(f"{path}: secret-like value must not be serialized")


def _require_mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise PersonalAssistantInvariantError(f"{field_name} must be a mapping")
    return dict(value)


def _require_non_empty_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PersonalAssistantInvariantError(f"{field_name} must be a non-empty string")
    if any(pattern.search(value) for pattern in _SECRET_VALUE_PATTERNS):
        raise PersonalAssistantInvariantError(f"{field_name} must not contain secret-like values")
    return value


def _require_pattern(value: str, field_name: str, pattern: re.Pattern[str]) -> str:
    text = _require_non_empty_text(value, field_name)
    if not pattern.fullmatch(text):
        raise PersonalAssistantInvariantError(f"{field_name} has invalid governed identifier shape")
    return text


def _non_empty_string_sequence(value: Any) -> bool:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        return False
    return bool(value) and all(isinstance(item, str) and bool(item.strip()) for item in value)
