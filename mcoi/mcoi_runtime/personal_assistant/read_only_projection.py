"""Purpose: runtime read-only projection-set envelopes for personal assistant.
Governance scope: PR4 read-only inbox/calendar evidence composition, receipt
alignment, private-payload redaction, and no-effect authority boundaries.
Dependencies: personal-assistant intake and read-only projection helpers.
Invariants:
  - This module does not call live connectors, mailbox APIs, or calendar APIs.
  - Inputs are redacted read-only projections, never raw connector payloads.
  - Envelope effects remain false for execution, mutation, writes, and claims.
  - Receipt drift, duplicate projection identity, raw payload fields, and
    secret-like values are rejected before envelope emission.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from .contracts import PersonalAssistantInvariantError
from .intake import ConnectorProofRef, interpret_user_request
from .read_only import (
    RedactedCalendarEvent,
    RedactedInboxMessage,
    ReadOnlyAssistantProjection,
    summarize_calendar_day_read_only,
    summarize_inbox_read_only,
)


DEFAULT_READ_ONLY_PROJECTION_SET_ID = "pa_read_only_projection_foundation_001"
DEFAULT_READ_ONLY_PROJECTION_GENERATED_AT = "2026-06-14T00:02:00+00:00"

_PROJECTION_SET_ID_PATTERN = re.compile(r"^pa_read_only_projection_[a-z0-9][a-z0-9_:-]*$")
_PROJECTION_ID_PATTERN = re.compile(r"^pa_read_only_projection_item_[a-z0-9][a-z0-9_:-]*$")
_RECEIPT_ID_PATTERN = re.compile(r"^pa_receipt_[a-z0-9][a-z0-9_:-]*$")
_REQUEST_ID_PATTERN = re.compile(r"^pa_request_[a-z0-9][a-z0-9_:-]*$")
_ALLOWED_CONNECTORS = frozenset({"gmail", "google_calendar"})
_SUMMARY_EFFECT_BOUNDARIES = {
    "email.inbox.summarize": ("inbox_read_only", "read_only_no_mailbox_mutation"),
    "calendar.day.brief": ("calendar_day_read_only", "read_only_no_calendar_mutation"),
}
_FALSE_EFFECT_BOUNDARY = {
    "execution_allowed": False,
    "live_connector_execution_allowed": False,
    "mailbox_read_allowed": False,
    "mailbox_mutation_allowed": False,
    "external_send_allowed": False,
    "calendar_write_allowed": False,
    "task_write_allowed": False,
    "memory_write_allowed": False,
    "connector_mutation_allowed": False,
    "deployment_mutation_allowed": False,
    "public_readiness_claim_allowed": False,
}
_PRIVATE_PAYLOAD_POLICY = {
    "raw_private_payload_serialized": False,
    "secret_values_serialized": False,
    "connector_payload_projection": "redacted_summary",
    "body_projection": "redacted_summary",
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


def build_personal_assistant_read_only_projection_envelope(
    *,
    generated_at: str,
    projections: Sequence[tuple[str, ReadOnlyAssistantProjection | Mapping[str, Any]]],
    projection_set_id: str = DEFAULT_READ_ONLY_PROJECTION_SET_ID,
) -> dict[str, Any]:
    """Build a governed no-effect envelope around read-only skill projections."""
    timestamp = _require_non_empty_text(generated_at, "generated_at")
    envelope_id = _require_pattern(
        projection_set_id,
        "projection_set_id",
        _PROJECTION_SET_ID_PATTERN,
    )
    if isinstance(projections, (str, bytes)) or not isinstance(projections, Sequence):
        raise PersonalAssistantInvariantError("projections must be a sequence")
    if not projections:
        raise PersonalAssistantInvariantError("projections must contain at least one read-only projection")

    projection_items: list[dict[str, Any]] = []
    projection_ids: list[str] = []
    receipt_ids: list[str] = []
    connector_names: list[str] = []
    for projection_id, projection in projections:
        normalized_projection_id = _require_pattern(projection_id, "projection_id", _PROJECTION_ID_PATTERN)
        if normalized_projection_id in projection_ids:
            raise PersonalAssistantInvariantError(f"duplicate projection_id {normalized_projection_id}")
        projection_ids.append(normalized_projection_id)

        projection_payload = _projection_payload(projection)
        _scan_private_or_secret_payload(projection_payload, path=f"projection:{normalized_projection_id}")
        item = _projection_item(normalized_projection_id, projection_payload)
        receipt_id = item["receipt"]["receipt_id"]
        if receipt_id in receipt_ids:
            raise PersonalAssistantInvariantError(f"duplicate receipt_id {receipt_id}")
        receipt_ids.append(receipt_id)
        for connector_name in item["receipt"]["connectors_used"]:
            if connector_name not in connector_names:
                connector_names.append(connector_name)
        projection_items.append(item)

    envelope = {
        "projection_set_id": envelope_id,
        "generated_at": timestamp,
        "governed": True,
        "source_projection": "operator_supplied_redacted_projection",
        "projection_count": len(projection_items),
        "projection_ids": projection_ids,
        "receipt_ids": receipt_ids,
        "connectors_used": connector_names,
        "projections": projection_items,
        "effect_boundary": dict(_FALSE_EFFECT_BOUNDARY),
        "private_payload_policy": dict(_PRIVATE_PAYLOAD_POLICY),
        "assurance": {
            "assurance_id": "personal_assistant_read_only_projection_no_effect_assurance",
            "outcome": "SolvedVerified",
            "foundation_only": True,
            "ready_for_live_execution": False,
            "ready_for_customer_readiness_claim": False,
            "authority_drift_detected": False,
            "checked_controls": [
                "operator_redacted_projection_only",
                "no_live_connector_execution",
                "no_mailbox_mutation",
                "no_calendar_write",
                "no_external_send",
                "no_raw_private_payload_serialization",
                "no_secret_value_serialization",
                "receipt_actions_not_taken_recorded",
            ],
            "blocking_reasons": [],
            "next_action": "continue read-only evidence hardening before any live connector witness",
        },
        "metadata": {
            "foundation_only": True,
            "projection_contract": "read_only_redacted_evidence",
            "runtime_boundary": "no_live_connector_calls",
            "live_connector_execution_allowed": False,
            "connector_mutation_allowed": False,
            "external_send_allowed": False,
            "system_of_record_write_allowed": False,
        },
    }
    _scan_private_or_secret_payload(envelope, path="envelope")
    return envelope


def build_default_personal_assistant_read_only_projection(
    *,
    generated_at: str = DEFAULT_READ_ONLY_PROJECTION_GENERATED_AT,
    projection_set_id: str = DEFAULT_READ_ONLY_PROJECTION_SET_ID,
) -> dict[str, Any]:
    """Build deterministic fixture-shaped read-only evidence from redacted inputs."""
    inbox_intent = interpret_user_request(
        "Check my inbox today and summarize important items.",
        request_id="pa_request_readonly_inbox_001",
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
        "Summarize my calendar today.",
        request_id="pa_request_readonly_calendar_001",
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
    inbox_projection = summarize_inbox_read_only(
        inbox_intent,
        (
            RedactedInboxMessage(
                message_ref="msg:001",
                received_at="2026-06-14T08:00:00+00:00",
                sender_label="operator-visible sender A",
                subject_digest="deadline digest",
                snippet_digest="redacted summary digest only",
                priority_signals=("urgent", "deadline"),
                needs_reply=True,
                has_attachment=True,
            ),
            RedactedInboxMessage(
                message_ref="msg:002",
                received_at="2026-06-14T09:00:00+00:00",
                sender_label="operator-visible sender B",
                subject_digest="FYI digest",
                snippet_digest="redacted FYI digest only",
            ),
        ),
        generated_at=generated_at,
    )
    calendar_projection = summarize_calendar_day_read_only(
        calendar_intent,
        (
            RedactedCalendarEvent(
                event_ref="event:001",
                starts_at="2026-06-14T10:00:00+00:00",
                ends_at="2026-06-14T10:30:00+00:00",
                title_digest="planning digest",
                organizer_label="operator-visible organizer",
                location_label="redacted location label",
                attendee_count=3,
                conflict_ref="conflict:001",
                preparation_signals=("agenda_needed",),
            ),
            RedactedCalendarEvent(
                event_ref="event:002",
                starts_at="2026-06-14T11:00:00+00:00",
                ends_at="2026-06-14T11:45:00+00:00",
                title_digest="check-in digest",
                organizer_label="operator-visible organizer",
                location_label="",
                attendee_count=2,
            ),
        ),
        generated_at=generated_at,
    )
    return build_personal_assistant_read_only_projection_envelope(
        generated_at=generated_at,
        projection_set_id=projection_set_id,
        projections=(
            ("pa_read_only_projection_item_inbox_001", inbox_projection),
            ("pa_read_only_projection_item_calendar_001", calendar_projection),
        ),
    )


def _projection_payload(projection: ReadOnlyAssistantProjection | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(projection, ReadOnlyAssistantProjection):
        return projection.as_dict()
    if not isinstance(projection, Mapping):
        raise PersonalAssistantInvariantError("projection must be a read-only projection or mapping")
    return dict(projection)


def _projection_item(projection_id: str, projection: Mapping[str, Any]) -> dict[str, Any]:
    request_id = _require_pattern(str(projection.get("request_id", "")), "request_id", _REQUEST_ID_PATTERN)
    skill_id = _require_non_empty_text(projection.get("skill_id"), "skill_id")
    expected_summary = _SUMMARY_EFFECT_BOUNDARIES.get(skill_id)
    if expected_summary is None:
        raise PersonalAssistantInvariantError(f"unsupported read-only skill_id {skill_id}")

    summary = _require_mapping(projection.get("summary"), "summary")
    receipt = _require_mapping(projection.get("receipt"), "receipt")
    summary_type = _require_non_empty_text(summary.get("summary_type"), "summary.summary_type")
    summary_effect_boundary = _require_non_empty_text(summary.get("effect_boundary"), "summary.effect_boundary")
    if (summary_type, summary_effect_boundary) != expected_summary:
        raise PersonalAssistantInvariantError(
            f"{projection_id}: summary boundary does not match read-only skill {skill_id}"
        )

    _assert_receipt_alignment(
        projection_id=projection_id,
        request_id=request_id,
        skill_id=skill_id,
        receipt=receipt,
    )
    return {
        "projection_id": projection_id,
        "request_id": request_id,
        "skill_id": skill_id,
        "summary_type": summary_type,
        "summary": dict(summary),
        "receipt": dict(receipt),
    }


def _assert_receipt_alignment(
    *,
    projection_id: str,
    request_id: str,
    skill_id: str,
    receipt: Mapping[str, Any],
) -> None:
    receipt_id = _require_pattern(str(receipt.get("receipt_id", "")), "receipt.receipt_id", _RECEIPT_ID_PATTERN)
    if receipt.get("request_id") != request_id:
        raise PersonalAssistantInvariantError(f"{projection_id}: receipt.request_id must match projection")
    if receipt.get("skill_id") != skill_id:
        raise PersonalAssistantInvariantError(f"{projection_id}: receipt.skill_id must match projection")
    if receipt.get("approval_required") is not False:
        raise PersonalAssistantInvariantError(f"{projection_id}: receipt.approval_required must be false")
    if receipt.get("decision") != "allowed":
        raise PersonalAssistantInvariantError(f"{projection_id}: receipt.decision must be allowed")
    if not _non_empty_string_sequence(receipt.get("actions_taken")):
        raise PersonalAssistantInvariantError(f"{projection_id}: receipt.actions_taken must be non-empty")
    if not _non_empty_string_sequence(receipt.get("actions_not_taken")):
        raise PersonalAssistantInvariantError(f"{projection_id}: receipt.actions_not_taken must be non-empty")

    connector_names = tuple(receipt.get("connectors_used", ()))
    if not connector_names:
        raise PersonalAssistantInvariantError(f"{projection_id}: receipt.connectors_used must be non-empty")
    for connector_name in connector_names:
        if connector_name not in _ALLOWED_CONNECTORS:
            raise PersonalAssistantInvariantError(f"{projection_id}: unsupported connector {connector_name}")

    private_policy = _require_mapping(receipt.get("private_payload_policy"), "receipt.private_payload_policy")
    for field_name, expected_value in _PRIVATE_PAYLOAD_POLICY.items():
        if private_policy.get(field_name) != expected_value:
            raise PersonalAssistantInvariantError(f"{projection_id}: receipt.private_payload_policy.{field_name} drift")

    metadata = _require_mapping(receipt.get("metadata"), "receipt.metadata")
    for field_name in ("live_connector_execution_allowed", "connector_mutation_allowed", "external_write_allowed"):
        if metadata.get(field_name) is not False:
            raise PersonalAssistantInvariantError(f"{projection_id}: receipt.metadata.{field_name} must be false")
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
