"""Tests for personal-assistant draft-only projections.

Purpose: prove PR5 draft-only skills prepare operator-visible email, calendar,
and task drafts while preserving approval and no-mutation boundaries.
Governance scope: P2 draft receipts, connector proof gating, task write
blocking, raw payload denial, and secret serialization denial.
Dependencies: mcoi_runtime.personal_assistant draft helpers.
Invariants:
  - Email/calendar drafts require passing private connector proof.
  - Task drafts are connector-free and do not write task systems or memory.
  - Draft receipts record effect-bearing actions not taken.
  - Raw private fields and secret-like values are rejected before drafting.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mcoi_runtime.personal_assistant import (
    CalendarEventDraftInput,
    ConnectorProofRef,
    EmailDraftInput,
    PersonalAssistantInvariantError,
    RequestExecutionMode,
    SkillRiskLevel,
    TaskDraftInput,
    draft_calendar_event,
    draft_email_response,
    draft_task,
    interpret_user_request,
)
from scripts.validate_personal_assistant_receipt import validate_personal_assistant_receipt_payload
from scripts.validate_schemas import _load_schema, _validate_schema_instance


ROOT = Path(__file__).resolve().parent.parent
RECEIPT_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_receipt.schema.json"
REQUEST_SCHEMA_PATH = ROOT / "schemas" / "personal_assistant_request.schema.json"
SUBMITTED_AT = "2026-06-14T00:00:00+00:00"
GENERATED_AT = "2026-06-14T00:02:00+00:00"


def test_email_response_draft_emits_receipt_without_sending() -> None:
    intent = interpret_user_request(
        "Draft a response to this email.",
        request_id="pa_request_draft_email_001",
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
    projection = draft_email_response(
        intent,
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
        generated_at=GENERATED_AT,
    )
    receipt = dict(projection.receipt)
    serialized = json.dumps(projection.as_dict(), sort_keys=True)

    assert _validate_schema_instance(_load_schema(RECEIPT_SCHEMA_PATH), receipt) == []
    assert validate_personal_assistant_receipt_payload(receipt) == ()
    assert intent.execution_mode is RequestExecutionMode.READ_AND_DRAFT_ONLY
    assert projection.skill_id == "email.response.draft"
    assert projection.draft["approval_required_before_send"] is True
    assert "email_not_sent" in receipt["actions_not_taken"]
    assert receipt["private_payload_policy"]["body_projection"] == "operator_visible_draft"
    assert receipt["metadata"]["external_write_allowed"] is False
    assert "raw_message" not in serialized


def test_calendar_event_draft_emits_receipt_without_creating_or_inviting() -> None:
    intent = interpret_user_request(
        "Draft a calendar event for today.",
        request_id="pa_request_draft_calendar_001",
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
    projection = draft_calendar_event(
        intent,
        CalendarEventDraftInput(
            meeting_goal="Review the handoff packet.",
            title_digest="handoff review digest",
            proposed_window="2026-06-14 afternoon",
            duration_minutes=30,
            attendee_labels=("operator-visible teammate",),
            location_label="video call label",
            agenda_digest="review blockers and next action",
        ),
        generated_at=GENERATED_AT,
    )
    receipt = dict(projection.receipt)

    assert _validate_schema_instance(_load_schema(RECEIPT_SCHEMA_PATH), receipt) == []
    assert validate_personal_assistant_receipt_payload(receipt) == ()
    assert projection.skill_id == "calendar.event.draft"
    assert projection.draft["approval_required_before_create_or_invite"] is True
    assert projection.draft["duration_minutes"] == 30
    assert "calendar_event_not_created" in receipt["actions_not_taken"]
    assert "people_not_invited" in receipt["actions_not_taken"]
    assert receipt["metadata"]["connector_mutation_allowed"] is False


def test_task_draft_is_connector_free_and_does_not_write_task_state() -> None:
    intent = interpret_user_request(
        "Create a task draft for reviewing the release notes.",
        request_id="pa_request_draft_task_001",
        submitted_at=SUBMITTED_AT,
    )
    request_payload = intent.as_request_dict()
    projection = draft_task(
        intent,
        TaskDraftInput(
            task_goal="Review release notes before the next closure step.",
            source_ref="conversation:release-notes",
            title_digest="review release notes digest",
            priority="medium",
            due_hint="next working session",
            acceptance_digest="notes reviewed and blockers recorded",
        ),
        generated_at=GENERATED_AT,
    )
    receipt = dict(projection.receipt)

    assert _validate_schema_instance(_load_schema(REQUEST_SCHEMA_PATH), request_payload) == []
    assert _validate_schema_instance(_load_schema(RECEIPT_SCHEMA_PATH), receipt) == []
    assert validate_personal_assistant_receipt_payload(receipt) == ()
    assert intent.requested_skill_ids == ("task.create_draft",)
    assert intent.connector_refs == ()
    assert intent.risk_level is SkillRiskLevel.P2
    assert projection.skill_id == "task.create_draft"
    assert receipt["connectors_used"] == []
    assert "task_not_written" in receipt["actions_not_taken"]
    assert receipt["private_payload_policy"]["connector_payload_projection"] == "no_connector_payload"
    assert receipt["metadata"]["task_write_allowed"] is False


def test_draft_inputs_reject_raw_payload_fields_and_secret_like_values() -> None:
    with pytest.raises(PersonalAssistantInvariantError) as raw_exc:
        EmailDraftInput.from_mapping(
            {
                "message_ref": "msg:raw",
                "recipient_label": "operator-visible recipient",
                "sender_label": "operator",
                "subject_digest": "digest",
                "thread_summary_digest": "digest",
                "response_goal": "draft reply",
                "raw_message_body": "private body",
            }
        )

    with pytest.raises(PersonalAssistantInvariantError) as secret_exc:
        TaskDraftInput(
            task_goal="review secret-token-value",
            source_ref="conversation:secret",
            title_digest="digest",
            priority="medium",
        )

    assert "forbidden private field raw_message_body" in str(raw_exc.value)
    assert "private body" not in str(raw_exc.value)
    assert "secret-like values" in str(secret_exc.value)


def test_draft_projection_requires_unblocked_intent_and_matching_skill() -> None:
    missing_connector_intent = interpret_user_request(
        "Draft a response to this email.",
        request_id="pa_request_draft_email_missing_connector_001",
        submitted_at=SUBMITTED_AT,
    )
    math_intent = interpret_user_request(
        "Compare two cost scenarios.",
        request_id="pa_request_draft_wrong_skill_001",
        submitted_at=SUBMITTED_AT,
    )

    with pytest.raises(PersonalAssistantInvariantError) as missing_exc:
        draft_email_response(
            missing_connector_intent,
            {
                "message_ref": "msg:123",
                "recipient_label": "operator-visible recipient",
                "sender_label": "operator",
                "subject_digest": "digest",
                "thread_summary_digest": "digest",
                "response_goal": "draft reply",
            },
            generated_at=GENERATED_AT,
        )

    with pytest.raises(PersonalAssistantInvariantError) as wrong_skill_exc:
        draft_task(
            math_intent,
            {
                "task_goal": "turn this into a task",
                "source_ref": "conversation:math",
                "title_digest": "task digest",
                "priority": "low",
            },
            generated_at=GENERATED_AT,
        )

    assert missing_connector_intent.execution_mode is RequestExecutionMode.BLOCKED
    assert "missing bindings block draft projection" in str(missing_exc.value)
    assert math_intent.requested_skill_ids == ("math.reasoning.plan",)
    assert "task.create_draft is not requested" in str(wrong_skill_exc.value)
