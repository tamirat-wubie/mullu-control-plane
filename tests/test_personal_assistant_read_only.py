"""Tests for personal-assistant read-only inbox and calendar projections.

Purpose: prove PR4 read-only skills summarize redacted connector projections
and emit receipts without live provider calls or mutation authority.
Governance scope: private connector proof, redacted projection validation,
receipt schema conformance, and no send/delete/archive/calendar-write effects.
Dependencies: mcoi_runtime.personal_assistant read-only projection helpers.
Invariants:
  - Read-only summaries require passing private connector proof.
  - Raw private connector payload fields and secret-like values are rejected.
  - Receipts record actions taken and forbidden actions not taken.
  - Calendar and inbox summaries do not mutate connector state.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    ConnectorProofRef,
    PersonalAssistantInvariantError,
    RedactedCalendarEvent,
    RedactedInboxMessage,
    interpret_user_request,
    summarize_calendar_day_read_only,
    summarize_inbox_read_only,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"
SUBMITTED_AT = "2026-06-14T00:00:00+00:00"
GENERATED_AT = "2026-06-14T00:01:00+00:00"


def test_inbox_read_only_summary_emits_schema_ready_receipt_without_mutation() -> None:
    intent = interpret_user_request(
        "Check my inbox today and summarize important items.",
        request_id="pa_request_readonly_inbox_001",
        submitted_at=SUBMITTED_AT,
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
    projection = summarize_inbox_read_only(
        intent,
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
        generated_at=GENERATED_AT,
    )
    receipt = dict(projection.receipt)
    serialized = json.dumps(projection.as_dict(), sort_keys=True)

    assert _validate_schema_instance(_load_schema(RECEIPT_SCHEMA_PATH), receipt) == []
    assert projection.skill_id == "email.inbox.summarize"
    assert projection.summary["message_count"] == 2
    assert projection.summary["urgent_count"] == 1
    assert projection.summary["needs_reply_count"] == 1
    assert receipt["connectors_used"] == ["gmail"]
    assert "email_not_sent" in receipt["actions_not_taken"]
    assert "email_not_deleted" in receipt["actions_not_taken"]
    assert receipt["private_payload_policy"]["raw_private_payload_serialized"] is False
    assert "raw_message" not in serialized


def test_inbox_projection_rejects_raw_body_fields_and_secret_like_values() -> None:
    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        RedactedInboxMessage.from_mapping(
            {
                "message_ref": "msg:raw",
                "received_at": "2026-06-14T08:00:00+00:00",
                "sender_label": "operator-visible sender",
                "subject_digest": "digest",
                "snippet_digest": "digest",
                "raw_message_body": "private mailbox body",
            }
        )

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        RedactedInboxMessage(
            message_ref="msg:secret",
            received_at="2026-06-14T08:00:00+00:00",
            sender_label="operator-visible sender",
            subject_digest="Bearer secret-token-value",
            snippet_digest="digest",
        )

    assert "forbidden private field raw_message_body" in str(raw_exc.value)
    assert "secret-like values" in str(secret_exc.value)
    assert "private mailbox body" not in str(raw_exc.value)


def test_calendar_day_brief_emits_read_only_receipt_and_conflict_summary() -> None:
    intent = interpret_user_request(
        "Summarize my calendar today.",
        request_id="pa_request_readonly_calendar_001",
        submitted_at=SUBMITTED_AT,
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
    projection = summarize_calendar_day_read_only(
        intent,
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
            {
                "event_ref": "event:002",
                "starts_at": "2026-06-14T11:00:00+00:00",
                "ends_at": "2026-06-14T11:45:00+00:00",
                "title_digest": "check-in digest",
                "organizer_label": "operator-visible organizer",
                "location_label": "",
                "attendee_count": 2,
            },
        ),
        generated_at=GENERATED_AT,
    )
    receipt = dict(projection.receipt)

    assert _validate_schema_instance(_load_schema(RECEIPT_SCHEMA_PATH), receipt) == []
    assert projection.skill_id == "calendar.day.brief"
    assert projection.summary["event_count"] == 2
    assert projection.summary["conflict_count"] == 1
    assert projection.summary["needs_preparation_count"] == 1
    assert receipt["connectors_used"] == ["google_calendar"]
    assert "calendar_event_not_created" in receipt["actions_not_taken"]
    assert "people_not_invited" in receipt["actions_not_taken"]
    assert receipt["metadata"]["connector_mutation_allowed"] is False


def test_calendar_projection_requires_passing_connector_proof() -> None:
    intent = interpret_user_request(
        "Summarize my calendar today.",
        request_id="pa_request_readonly_calendar_missing_proof_001",
        submitted_at=SUBMITTED_AT,
    )

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        summarize_calendar_day_read_only(intent, (), generated_at=GENERATED_AT)

    assert intent.missing_bindings[0].binding_id == "connector:google_calendar"
    assert "missing bindings block read-only projection" in str(exc_info.value)
    assert "google_calendar" in intent.missing_bindings[0].question


def test_read_only_projection_rejects_wrong_skill_boundary() -> None:
    intent = interpret_user_request(
        "Compare two cost scenarios.",
        request_id="pa_request_readonly_wrong_skill_001",
        submitted_at=SUBMITTED_AT,
    )

    with pytest.raises(PersonalAssistantInvariantError) as exc_info:
        summarize_inbox_read_only(intent, (), generated_at=GENERATED_AT)

    assert intent.requested_skill_ids == ("math.reasoning.plan",)
    assert "email.inbox.summarize is not requested" in str(exc_info.value)
    assert "pa_request_readonly_wrong_skill_001" in str(exc_info.value)
