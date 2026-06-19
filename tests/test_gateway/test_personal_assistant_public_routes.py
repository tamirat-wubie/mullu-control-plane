"""Gateway personal-assistant public route tests.

Purpose: verify the Render-backed gateway app exposes governed personal-assistant
    read and preview endpoints without granting execution authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: FastAPI TestClient, gateway.server, and mcoi_runtime.personal_assistant.
Invariants:
  - Gateway personal-assistant routes compile previews only.
  - Public route responses deny live connector execution and external sends.
  - Clarification requests are explicit when a request lacks bindings.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from gateway.server import create_gateway_app
from mcoi_runtime.personal_assistant import (
    ApprovalScope,
    GovernedIntent,
    RequestExecutionMode,
    RequestInterface,
    SkillRiskLevel,
    build_personal_assistant_preview_plan,
)


class StubPlatform:
    """Minimal governed platform fixture for gateway app construction."""

    def connect(self, *, identity_id: str, tenant_id: str):
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):  # noqa: ANN001
        return type("Result", (), {"content": "ok", "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        return None


def test_gateway_personal_assistant_skills_route_is_read_only() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/personal-assistant/skills")
    post_response = client.post("/api/v1/personal-assistant/skills", json={"skill_id": "email.send"})
    payload = response.json()

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["live_connector_execution_allowed"] is False
    assert payload["registry"]["skill_count"] >= 15
    assert "email.response.draft" in payload["registry"]["skill_ids"]


def test_gateway_personal_assistant_console_read_model_exposes_lane_status() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/console/personal-assistant")
    post_response = client.post("/api/v1/console/personal-assistant", json={})
    payload = response.json()
    lane_status = payload["lane_status"]
    readiness = payload["assistant_readiness"]
    lane_ids = [lane["lane_id"] for lane in lane_status["lanes"]]

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["console_id"] == "personal_assistant_console_foundation"
    assert payload["status"] == "foundation_read_only"
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["governed"] is True
    assert payload["sections"]["assistant_readiness"]["item_count"] == 1
    assert readiness["user_prompt"] == "Show my assistant readiness."
    assert readiness["inbox_projection_status"]["skill_id"] == "email.inbox.summarize"
    assert readiness["calendar_projection_status"]["skill_id"] == "calendar.day.brief"
    assert readiness["available_skills"]["skill_count"] == payload["skills"]["skill_count"]
    assert readiness["live_connector_execution_allowed"] is False
    assert readiness["mailbox_mutation_allowed"] is False
    assert readiness["calendar_write_allowed"] is False
    assert readiness["external_send_allowed"] is False
    assert lane_status["lane_count"] == 12
    assert lane_ids == [
        "request_intake_whqr",
        "skill_registry",
        "approval_queue",
        "memory_observation",
        "read_only_projection",
        "draft_projection",
        "teamops_shared_inbox",
        "github_codex_review",
        "research_source_compare",
        "math_reasoning",
        "schedule_planning",
        "operator_console",
    ]
    assert lane_status["execution_allowed"] is False
    assert lane_status["live_connector_execution_allowed"] is False
    assert lane_status["connector_mutation_allowed"] is False
    assert lane_status["external_effect_allowed"] is False
    assert lane_status["customer_readiness_claim_allowed"] is False
    assert lane_status["nested_mind_live_activation_allowed"] is False
    assert all(lane["receipt_required"] is True for lane in lane_status["lanes"])
    assert all(lane["execution_allowed"] is False for lane in lane_status["lanes"])
    assert all(lane["live_connector_execution_allowed"] is False for lane in lane_status["lanes"])
    assert all(lane["connector_mutation_allowed"] is False for lane in lane_status["lanes"])
    assert all(lane["external_effect_allowed"] is False for lane in lane_status["lanes"])
    assert all(lane["customer_readiness_claim_allowed"] is False for lane in lane_status["lanes"])
    assert all(lane["nested_mind_live_activation_allowed"] is False for lane in lane_status["lanes"])


def test_gateway_personal_assistant_console_html_view_is_read_only() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/console/personal-assistant/view")
    post_response = client.post("/api/v1/console/personal-assistant/view", json={})
    body = response.text

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert "Mullu Personal Assistant Console" in body
    assert "Assistant Readiness" in body
    assert "Show my assistant readiness." in body
    assert "Foundation Lanes" in body
    assert "foundation_read_only" in body
    assert "/api/v1/console/personal-assistant" in body
    assert "Execution Allowed" in body
    assert "False" in body


def test_gateway_personal_assistant_preview_blocks_effects_and_emits_receipt() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/requests/preview",
        json={
            "user_request": "Check my inbox and draft replies for urgent messages.",
            "submitted_at": "2026-06-14T10:20:00+00:00",
            "include_console_read_model": True,
        },
    )
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["effect_boundary"]["execution_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert payload["effect_boundary"]["connector_mutation_allowed"] is False
    assert payload["receipt"]["actions_not_taken"]
    assert "send" in payload["receipt"]["actions_not_taken"]
    assert "send" not in payload["receipt"]["actions_taken"]
    assert payload["console_read_model"]["effect_boundary"]["external_send_allowed"] is False
    assert "raw_private_connector_payload" not in serialized


def test_gateway_personal_assistant_preview_requests_clarification_for_missing_binding() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/requests/preview",
        json={
            "user_request": "Send it to Daniel.",
            "submitted_at": "2026-06-14T10:21:00+00:00",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["outcome"] == "AwaitingEvidence"
    assert payload["plan"]["mode"] == "blocked"
    assert payload["clarification_bundle"]["clarification_count"] >= 1
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert "request_interpreted" in payload["receipt"]["actions_taken"]
    assert "send" not in payload["receipt"]["actions_taken"]
    assert "external_message_not_sent" in payload["receipt"]["actions_not_taken"]


def test_gateway_personal_assistant_preview_rejects_extra_private_connector_fields() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/requests/preview",
        json={
            "user_request": "Check my inbox and draft replies.",
            "submitted_at": "2026-06-14T10:22:00+00:00",
            "connector_refs": [
                {
                    "connector_id": "connector:gmail",
                    "connector_name": "gmail",
                    "proof_state": "Pass",
                    "private_data_allowed": False,
                    "scopes": ["metadata_only"],
                    "raw_private_connector_payload": "private transcript",
                }
            ],
        },
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 422
    assert "raw_private_connector_payload" in serialized
    assert "private transcript" not in serialized
    assert "request_interpreted" not in serialized


def test_gateway_personal_assistant_read_only_inbox_preview_summarizes_redacted_projection() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/read-only/inbox/preview",
        json={
            "request_id": "pa_request_gateway_read_only_inbox_001",
            "submitted_at": "2026-06-16T10:00:00+00:00",
            "generated_at": "2026-06-16T10:01:00+00:00",
            "connector_refs": [_gmail_connector_ref()],
            "messages": [
                {
                    "message_ref": "msg:redacted:001",
                    "received_at": "2026-06-16T09:30:00+00:00",
                    "sender_label": "known customer",
                    "subject_digest": "urgent invoice follow-up",
                    "snippet_digest": "redacted summary only",
                    "priority_signals": ["urgent"],
                    "needs_reply": True,
                    "has_attachment": True,
                },
                {
                    "message_ref": "msg:redacted:002",
                    "received_at": "2026-06-16T09:45:00+00:00",
                    "sender_label": "system notification",
                    "subject_digest": "weekly digest",
                    "snippet_digest": "redacted summary only",
                    "priority_signals": [],
                    "needs_reply": False,
                    "has_attachment": False,
                },
            ],
            "include_console_read_model": True,
        },
    )
    payload = response.json()
    projection_set = payload["read_only_projection"]
    projection = projection_set["projections"][0]
    summary = projection["summary"]
    receipt = payload["receipt"]
    serialized = json.dumps(payload, sort_keys=True)

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["effect_boundary"]["mailbox_read_allowed"] is False
    assert payload["effect_boundary"]["mailbox_mutation_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert projection_set["source_projection"] == "operator_supplied_redacted_projection"
    assert projection["skill_id"] == "email.inbox.summarize"
    assert summary["summary_type"] == "inbox_read_only"
    assert summary["message_count"] == 2
    assert summary["urgent_count"] == 1
    assert summary["needs_reply_count"] == 1
    assert "email_not_sent" in receipt["actions_not_taken"]
    assert "connector_state_not_mutated" in receipt["actions_not_taken"]
    assert payload["console_read_model"]["effect_boundary"]["external_send_allowed"] is False
    assert "raw_private_connector_payload" not in serialized


def test_gateway_personal_assistant_read_only_calendar_preview_summarizes_redacted_projection() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/read-only/calendar/preview",
        json={
            "request_id": "pa_request_gateway_read_only_calendar_001",
            "submitted_at": "2026-06-16T11:00:00+00:00",
            "generated_at": "2026-06-16T11:01:00+00:00",
            "connector_refs": [_calendar_connector_ref()],
            "events": [
                {
                    "event_ref": "event:redacted:001",
                    "starts_at": "2026-06-16T14:00:00+00:00",
                    "ends_at": "2026-06-16T14:30:00+00:00",
                    "title_digest": "operator sync",
                    "organizer_label": "internal",
                    "location_label": "video",
                    "attendee_count": 3,
                    "conflict_ref": "conflict:redacted:001",
                    "preparation_signals": ["agenda_missing"],
                }
            ],
        },
    )
    payload = response.json()
    projection = payload["read_only_projection"]["projections"][0]
    summary = projection["summary"]
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["effect_boundary"]["live_connector_execution_allowed"] is False
    assert payload["effect_boundary"]["calendar_write_allowed"] is False
    assert payload["effect_boundary"]["connector_mutation_allowed"] is False
    assert projection["skill_id"] == "calendar.day.brief"
    assert summary["summary_type"] == "calendar_day_read_only"
    assert summary["event_count"] == 1
    assert summary["conflict_count"] == 1
    assert summary["needs_preparation_count"] == 1
    assert "calendar_event_not_created" in receipt["actions_not_taken"]
    assert "people_not_invited" in receipt["actions_not_taken"]


def test_gateway_personal_assistant_read_only_preview_rejects_missing_connector_proof() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/read-only/inbox/preview",
        json={
            "request_id": "pa_request_gateway_read_only_missing_connector_001",
            "submitted_at": "2026-06-16T10:00:00+00:00",
            "messages": [
                {
                    "message_ref": "msg:redacted:001",
                    "received_at": "2026-06-16T09:30:00+00:00",
                    "sender_label": "known customer",
                    "subject_digest": "urgent invoice follow-up",
                    "snippet_digest": "redacted summary only",
                }
            ],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_read_only_inbox_preview"


def test_gateway_personal_assistant_read_only_preview_rejects_raw_projection_payload() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/read-only/calendar/preview",
        json={
            "request_id": "pa_request_gateway_read_only_raw_calendar_001",
            "submitted_at": "2026-06-16T11:00:00+00:00",
            "connector_refs": [_calendar_connector_ref()],
            "events": [
                {
                    "event_ref": "event:redacted:001",
                    "starts_at": "2026-06-16T14:00:00+00:00",
                    "ends_at": "2026-06-16T14:30:00+00:00",
                    "title_digest": "operator sync",
                    "organizer_label": "internal",
                    "attendee_count": 3,
                    "raw_event_body": "private calendar notes",
                }
            ],
        },
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 422
    assert "raw_event_body" in serialized
    assert "private calendar notes" not in serialized
    assert "calendar_day_brief_generated" not in serialized


def test_gateway_personal_assistant_email_draft_preview_prepares_draft_without_send() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/drafts/email/preview",
        json={
            "request_id": "pa_request_gateway_email_draft_001",
            "submitted_at": "2026-06-16T12:00:00+00:00",
            "generated_at": "2026-06-16T12:01:00+00:00",
            "connector_refs": [_gmail_connector_ref()],
            "draft_input": {
                "message_ref": "msg:redacted:reply-001",
                "recipient_label": "known customer",
                "sender_label": "operator",
                "subject_digest": "invoice follow-up",
                "thread_summary_digest": "customer asked for a revised timeline",
                "response_goal": "Confirm the revised timeline and request approval before sending.",
                "tone": "clear",
                "constraints": ["do not promise shipment date"],
            },
            "include_console_read_model": True,
        },
    )
    payload = response.json()
    draft_set = payload["draft_projection"]
    draft_projection = draft_set["drafts"][0]
    draft = draft_projection["draft"]
    receipt = payload["receipt"]
    serialized = json.dumps(payload, sort_keys=True)

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["effect_boundary"]["draft_preparation_allowed"] is True
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert payload["effect_boundary"]["mailbox_mutation_allowed"] is False
    assert payload["approval_boundary"]["approval_required_before_external_action"] is True
    assert draft_projection["skill_id"] == "email.response.draft"
    assert draft["draft_type"] == "email_response"
    assert draft["approval_required_before_send"] is True
    assert "wait for explicit approval" in draft["body"]
    assert "email_not_sent" in receipt["actions_not_taken"]
    assert "connector_state_not_mutated" in receipt["actions_not_taken"]
    assert payload["console_read_model"]["effect_boundary"]["external_send_allowed"] is False
    assert "raw_private_connector_payload" not in serialized


def test_gateway_personal_assistant_calendar_event_draft_preview_prepares_draft_without_invite() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/drafts/calendar-event/preview",
        json={
            "request_id": "pa_request_gateway_calendar_draft_001",
            "submitted_at": "2026-06-16T13:00:00+00:00",
            "generated_at": "2026-06-16T13:01:00+00:00",
            "connector_refs": [_calendar_connector_ref()],
            "draft_input": {
                "meeting_goal": "Review operator handoff boundaries",
                "title_digest": "handoff review",
                "proposed_window": "2026-06-17T15:00:00+00:00/PT30M",
                "duration_minutes": 30,
                "attendee_labels": ["operator", "reviewer"],
                "location_label": "video",
                "agenda_digest": "review no-effect route evidence",
                "constraints": ["no invite until approval"],
            },
        },
    )
    payload = response.json()
    draft_projection = payload["draft_projection"]["drafts"][0]
    draft = draft_projection["draft"]
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["effect_boundary"]["calendar_write_allowed"] is False
    assert payload["effect_boundary"]["connector_mutation_allowed"] is False
    assert draft_projection["skill_id"] == "calendar.event.draft"
    assert draft["draft_type"] == "calendar_event"
    assert draft["approval_required_before_create_or_invite"] is True
    assert draft["duration_minutes"] == 30
    assert "calendar_event_not_created" in receipt["actions_not_taken"]
    assert "people_not_invited" in receipt["actions_not_taken"]


def test_gateway_personal_assistant_task_draft_preview_prepares_draft_without_task_write() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/drafts/task/preview",
        json={
            "request_id": "pa_request_gateway_task_draft_001",
            "submitted_at": "2026-06-16T14:00:00+00:00",
            "generated_at": "2026-06-16T14:01:00+00:00",
            "draft_input": {
                "task_goal": "Track read-only and draft route closure",
                "source_ref": "conversation:personal-assistant-draft-preview",
                "title_digest": "close draft route PR",
                "priority": "high",
                "due_hint": "today",
                "acceptance_digest": "routes tested and CI passing",
                "constraints": ["do not write task system"],
            },
        },
    )
    payload = response.json()
    draft_projection = payload["draft_projection"]["drafts"][0]
    draft = draft_projection["draft"]
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["effect_boundary"]["task_write_allowed"] is False
    assert payload["effect_boundary"]["memory_write_allowed"] is False
    assert payload["draft_projection"]["connectors_used"] == []
    assert draft_projection["skill_id"] == "task.create_draft"
    assert draft["draft_type"] == "task"
    assert draft["approval_required_before_task_write"] is True
    assert "task_not_written" in receipt["actions_not_taken"]
    assert "memory_not_written" in receipt["actions_not_taken"]


def test_gateway_personal_assistant_email_draft_preview_rejects_missing_connector_proof() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/drafts/email/preview",
        json={
            "request_id": "pa_request_gateway_email_draft_missing_connector_001",
            "submitted_at": "2026-06-16T12:00:00+00:00",
            "draft_input": {
                "message_ref": "msg:redacted:reply-001",
                "recipient_label": "known customer",
                "sender_label": "operator",
                "subject_digest": "invoice follow-up",
                "thread_summary_digest": "customer asked for a revised timeline",
                "response_goal": "Confirm the revised timeline.",
            },
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_email_draft_preview"


def test_gateway_personal_assistant_draft_preview_rejects_raw_payload() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/drafts/email/preview",
        json={
            "request_id": "pa_request_gateway_email_draft_raw_001",
            "submitted_at": "2026-06-16T12:00:00+00:00",
            "connector_refs": [_gmail_connector_ref()],
            "draft_input": {
                "message_ref": "msg:redacted:reply-001",
                "recipient_label": "known customer",
                "sender_label": "operator",
                "subject_digest": "invoice follow-up",
                "thread_summary_digest": "customer asked for a revised timeline",
                "response_goal": "Confirm the revised timeline.",
                "raw_body": "private mailbox body",
            },
        },
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 422
    assert "raw_body" in serialized
    assert "private mailbox body" not in serialized
    assert "email_response_draft_prepared" not in serialized


def test_gateway_personal_assistant_approval_queue_read_model_is_empty_and_safe() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/personal-assistant/approval-queue")
    post_response = client.post("/api/v1/personal-assistant/approval-queue", json={})
    payload = response.json()
    queue = payload["approval_queue"]

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["live_connector_execution_allowed"] is False
    assert queue["approval_count"] == 0
    assert queue["approval_ids"] == []
    assert queue["records"] == []
    assert queue["execution_allowed"] is False
    assert queue["approval_is_execution"] is False
    assert queue["metadata"]["approval_decision_executes_action"] is False


def test_gateway_personal_assistant_approval_proposal_preview_does_not_enqueue() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/approval-proposals/preview",
        json={
            "user_request": "Send one approved email draft to Daniel.",
            "plan": _approval_proposal_plan(),
            "submitted_at": "2026-06-14T10:29:00+00:00",
            "approval_scope": "per_recipient",
            "include_console_read_model": True,
        },
    )
    payload = response.json()
    proposal = payload["approval_proposal"]
    review_packet = payload["approval_review_packet"]
    queue = payload["approval_queue"]
    console = payload["console_read_model"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["outcome"] == "AwaitingEvidence"
    assert proposal["execution_allowed"] is False
    assert proposal["approval_is_execution"] is False
    assert proposal["approval_scope"] == "per_recipient"
    assert proposal["risk_level"] == "P4"
    assert proposal["proposed_actions"][0]["skill_id"] == "email.send.with_approval"
    assert "send" in proposal["forbidden_without_approval"]
    assert review_packet["review_state"] == "preview_only"
    assert review_packet["reviewer_ref"] == "operator"
    assert review_packet["risk_level"] == proposal["risk_level"]
    assert review_packet["proposed_actions"] == proposal["proposed_actions"]
    assert review_packet["effect_boundary"]["execution_allowed"] is False
    assert review_packet["effect_boundary"]["approval_enqueued"] is False
    assert "confirm_external_recipient_or_target_scope" in review_packet["required_operator_checks"]
    assert queue["approval_count"] == 0
    assert queue["records"] == []
    assert payload["effect_boundary"]["approval_enqueued"] is False
    assert payload["effect_boundary"]["approval_is_execution"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert console["approval_queue"]["proposal_count"] == 1
    assert console["approval_queue"]["approval_count"] == 0
    assert console["approval_queue"]["proposal_execution_allowed"] is False


def test_gateway_personal_assistant_approval_proposal_rejects_non_approval_request() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/approval-proposals/preview",
        json={
            "user_request": "Check my inbox and draft replies only.",
            "submitted_at": "2026-06-14T10:29:30+00:00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_approval_proposal_preview"


def test_gateway_personal_assistant_approval_proposal_rejects_extra_private_connector_fields() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/approval-proposals/preview",
        json={
            "user_request": "Send one approved email draft to Daniel.",
            "submitted_at": "2026-06-14T10:29:45+00:00",
            "connector_refs": [
                {
                    "connector_id": "connector:gmail",
                    "connector_name": "gmail",
                    "proof_state": "Pass",
                    "private_data_allowed": False,
                    "scopes": ["metadata_only"],
                    "raw_private_connector_payload": "private transcript",
                }
            ],
        },
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 422
    assert "raw_private_connector_payload" in serialized
    assert "private transcript" not in serialized
    assert "approval_proposal" not in serialized


def test_gateway_personal_assistant_draft_approval_proposal_preview_does_not_enqueue() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/approval-proposals/from-draft/preview",
        json=_draft_approval_proposal_payload(),
    )
    payload = response.json()
    proposal = payload["approval_proposal"]
    review_packet = payload["approval_review_packet"]
    queue = payload["approval_queue"]
    console = payload["console_read_model"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["outcome"] == "AwaitingEvidence"
    assert payload["draft_ref"] == "pa_draft_projection_item_gateway_email_001"
    assert proposal["risk_level"] == "P4"
    assert proposal["approval_scope"] == "per_action"
    assert proposal["execution_allowed"] is False
    assert proposal["approval_is_execution"] is False
    assert proposal["proposed_actions"][0]["skill_id"] == "email.send.with_approval"
    assert proposal["proposed_actions"][0]["risk_level"] == "P4"
    assert "send_without_approval" in proposal["forbidden_without_approval"]
    assert "pa_draft_projection_item_gateway_email_001" in proposal["evidence_refs"]
    assert review_packet["reviewer_ref"] == "operator:tamirat"
    assert review_packet["risk_level"] == "P4"
    assert review_packet["effect_boundary"]["approval_enqueued"] is False
    assert review_packet["effect_boundary"]["external_send_allowed"] is False
    assert {denial["authority"] for denial in review_packet["authority_denials"]} >= {
        "execution",
        "approval_enqueue",
        "external_send",
    }
    assert queue["approval_count"] == 0
    assert queue["records"] == []
    assert payload["effect_boundary"]["approval_enqueued"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert console["approval_queue"]["proposal_count"] == 1
    assert console["approval_queue"]["approval_count"] == 0
    assert console["approval_queue"]["proposal_execution_allowed"] is False


def test_gateway_personal_assistant_calendar_draft_approval_proposal_preview_does_not_enqueue() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/approval-proposals/from-draft/preview",
        json=_draft_approval_proposal_payload(
            draft_ref="pa_draft_projection_item_gateway_calendar_001",
            draft_type="calendar_event",
            draft_skill_id="calendar.event.draft",
            summary="Prepared customer check-in calendar event without invites.",
            evidence_ref="proof://personal-assistant/draft/gateway-calendar-001",
        ),
    )
    payload = response.json()
    proposal = payload["approval_proposal"]
    review_packet = payload["approval_review_packet"]
    queue = payload["approval_queue"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert proposal["risk_level"] == "P3"
    assert proposal["approval_is_execution"] is False
    assert proposal["proposed_actions"][0]["skill_id"] == "calendar.event.create.with_approval"
    assert proposal["proposed_actions"][0]["effect_boundary"] == "calendar_event_create"
    assert "create_event" in proposal["forbidden_without_approval"]
    assert "invite_people" in proposal["forbidden_without_approval"]
    assert review_packet["risk_level"] == "P3"
    assert review_packet["effect_boundary"]["connector_mutation_allowed"] is False
    assert review_packet["effect_boundary"]["approval_enqueued"] is False
    assert "confirm_external_recipient_or_target_scope" not in review_packet["required_operator_checks"]
    assert queue["approval_count"] == 0
    assert payload["effect_boundary"]["approval_enqueued"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False


def test_gateway_personal_assistant_task_draft_approval_proposal_preview_does_not_enqueue() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/approval-proposals/from-draft/preview",
        json=_draft_approval_proposal_payload(
            draft_ref="pa_draft_projection_item_gateway_task_001",
            draft_type="task",
            draft_skill_id="task.create_draft",
            summary="Prepared follow-up task from redacted operator request.",
            evidence_ref="proof://personal-assistant/draft/gateway-task-001",
        ),
    )
    payload = response.json()
    proposal = payload["approval_proposal"]
    review_packet = payload["approval_review_packet"]
    queue = payload["approval_queue"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert proposal["risk_level"] == "P3"
    assert proposal["approval_is_execution"] is False
    assert proposal["proposed_actions"][0]["skill_id"] == "task.create.with_approval"
    assert proposal["proposed_actions"][0]["effect_boundary"] == "task_system_write"
    assert "system_of_record_write" in proposal["forbidden_without_approval"]
    assert "connector_mutation" in proposal["forbidden_without_approval"]
    assert review_packet["risk_level"] == "P3"
    assert review_packet["effect_boundary"]["system_of_record_write_allowed"] is False
    assert review_packet["effect_boundary"]["memory_write_allowed"] is False
    assert {denial["authority"] for denial in review_packet["authority_denials"]} >= {
        "execution",
        "approval_enqueue",
        "connector_mutation",
        "memory_write",
    }
    assert queue["approval_count"] == 0
    assert payload["effect_boundary"]["system_of_record_write_allowed"] is False
    assert payload["effect_boundary"]["memory_write_allowed"] is False


def test_gateway_personal_assistant_draft_approval_proposal_rejects_mismatched_source() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    request_payload = _draft_approval_proposal_payload()
    request_payload["draft"] = {
        **request_payload["draft"],
        "draft_skill_id": "calendar.event.draft",
    }

    response = client.post(
        "/api/v1/personal-assistant/approval-proposals/from-draft/preview",
        json=request_payload,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_draft_approval_proposal_preview"


def test_gateway_personal_assistant_draft_approval_proposal_rejects_raw_payload() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    request_payload = _draft_approval_proposal_payload()
    request_payload["draft"] = {
        **request_payload["draft"],
        "raw_private_connector_payload": "private email thread body",
    }

    response = client.post(
        "/api/v1/personal-assistant/approval-proposals/from-draft/preview",
        json=request_payload,
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 422
    assert "raw_private_connector_payload" in serialized
    assert "private email thread body" not in serialized
    assert "email.send.with_approval" not in serialized


def test_gateway_personal_assistant_draft_approval_proposal_rejects_unknown_draft_type() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    request_payload = _draft_approval_proposal_payload(
        draft_type="document_draft",
        draft_skill_id="document.draft",
    )

    response = client.post(
        "/api/v1/personal-assistant/approval-proposals/from-draft/preview",
        json=request_payload,
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_draft_approval_proposal_preview"


def test_gateway_personal_assistant_approval_queue_preview_records_pending_packet() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/approval-queue/preview",
        json=_approval_preview_payload(),
    )
    payload = response.json()
    queue = payload["approval_queue"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["outcome"] == "AwaitingEvidence"
    assert payload["approval"]["packet"]["approval_state"] == "requested"
    assert payload["receipt"]["decision"] == "approval_required"
    assert "approval_request_enqueued" in payload["receipt"]["actions_taken"]
    assert "external_message_not_sent" in payload["receipt"]["actions_not_taken"]
    assert queue["approval_count"] == 1
    assert queue["state_counts"]["requested"] == 1
    assert queue["execution_allowed"] is False
    assert payload["effect_boundary"]["approval_is_execution"] is False
    assert payload["effect_boundary"]["connector_mutation_allowed"] is False


def test_gateway_personal_assistant_approval_queue_approved_still_defers_execution() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    request_payload = {
        **_approval_preview_payload(),
        "decision": "approved",
        "reason_codes": ["operator_explicitly_approved_named_recipient"],
        "decided_at": "2026-06-14T10:31:00+00:00",
        "decision_evidence_ref": "proof://personal-assistant/approval/operator-click-gateway-001",
    }

    response = client.post(
        "/api/v1/personal-assistant/approval-queue/preview",
        json=request_payload,
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["approval"]["packet"]["approval_state"] == "approved"
    assert payload["receipt"]["decision"] == "deferred"
    assert payload["receipt"]["metadata"]["approval_is_execution"] is False
    assert payload["approval_queue"]["state_counts"]["approved"] == 1
    assert "approval_decision_recorded" in payload["receipt"]["actions_taken"]
    assert "external_message_not_sent" in payload["receipt"]["actions_not_taken"]
    assert payload["effect_boundary"]["execution_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False


def test_gateway_personal_assistant_approval_queue_expired_blocks_execution() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    request_payload = {
        **_approval_preview_payload(),
        "decision": "expired",
        "reason_codes": ["approval_window_elapsed"],
        "decided_at": "2026-06-14T10:41:00+00:00",
        "decision_evidence_ref": "proof://personal-assistant/approval/expired-gateway-001",
    }

    response = client.post(
        "/api/v1/personal-assistant/approval-queue/preview",
        json=request_payload,
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["approval"]["packet"]["approval_state"] == "expired"
    assert payload["receipt"]["decision"] == "blocked"
    assert payload["receipt"]["metadata"]["approval_is_execution"] is False
    assert payload["approval_queue"]["state_counts"]["expired"] == 1
    assert "approval_expiration_recorded" in payload["receipt"]["actions_taken"]
    assert "external_message_not_sent" in payload["receipt"]["actions_not_taken"]
    assert payload["effect_boundary"]["execution_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert payload["effect_boundary"]["connector_mutation_allowed"] is False


def test_gateway_personal_assistant_approval_queue_rejects_extra_private_action_fields() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    request_payload = _approval_preview_payload()
    request_payload["proposed_actions"] = [
        {
            **request_payload["proposed_actions"][0],
            "raw_private_connector_payload": "private transcript",
        }
    ]

    response = client.post(
        "/api/v1/personal-assistant/approval-queue/preview",
        json=request_payload,
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 422
    assert "raw_private_connector_payload" in serialized
    assert "private transcript" not in serialized
    assert "approval_request_enqueued" not in serialized


def test_gateway_personal_assistant_memory_read_model_is_empty_and_safe() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/personal-assistant/memory-observations")
    post_response = client.post("/api/v1/personal-assistant/memory-observations", json={})
    payload = response.json()
    read_model = payload["memory_read_model"]

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["live_memory_write_allowed"] is False
    assert payload["nested_mind_live_activation_allowed"] is False
    assert read_model["candidate_count"] == 0
    assert read_model["candidates"] == []
    assert read_model["candidate_only"] is True
    assert read_model["metadata"]["foundation_only"] is True
    assert read_model["metadata"]["live_memory_write_allowed"] is False


def test_gateway_personal_assistant_memory_preview_prepares_candidate_without_write() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/memory-observations/preview",
        json=_memory_preview_payload(),
    )
    payload = response.json()
    read_model = payload["memory_read_model"]
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["outcome"] == "SolvedVerified"
    assert payload["effect_boundary"]["live_memory_write_allowed"] is False
    assert payload["effect_boundary"]["nested_mind_live_activation_allowed"] is False
    assert payload["memory_observation"]["observation"]["nested_mind_status"] == "staging_only"
    assert "live_memory_not_written" in receipt["actions_not_taken"]
    assert "nested_mind_not_activated" in receipt["actions_not_taken"]
    assert read_model["candidate_count"] == 1
    assert read_model["live_memory_write_allowed"] is False
    assert read_model["secret_value_storage_allowed"] is False


def test_gateway_personal_assistant_memory_preview_rejects_raw_payload_and_activation() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    raw_payload = {
        **_memory_preview_payload(),
        "metadata": {"raw_chat_log": "private transcript"},
    }
    activation_payload = {
        **_memory_preview_payload(),
        "memory_observation_id": "pa_memory_gateway_activation_001",
        "nested_mind_status": "awaiting_evidence",
    }

    raw_response = client.post("/api/v1/personal-assistant/memory-observations/preview", json=raw_payload)
    activation_response = client.post(
        "/api/v1/personal-assistant/memory-observations/preview",
        json=activation_payload,
    )
    serialized_error = json.dumps(raw_response.json(), sort_keys=True)

    assert raw_response.status_code == 400
    assert activation_response.status_code == 400
    assert raw_response.json()["detail"]["governed"] is True
    assert activation_response.json()["detail"]["error_code"] == "invalid_personal_assistant_memory_observation_preview"
    assert "private transcript" not in serialized_error
    assert "raw_chat_log" not in serialized_error


def test_gateway_personal_assistant_memory_preview_rejects_extra_private_source_fields() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    request_payload = _memory_preview_payload()
    request_payload["source"] = {
        **request_payload["source"],
        "raw_private_connector_payload": "private transcript",
    }

    response = client.post(
        "/api/v1/personal-assistant/memory-observations/preview",
        json=request_payload,
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 422
    assert "raw_private_connector_payload" in serialized
    assert "private transcript" not in serialized
    assert "memory_observation_candidate_prepared" not in serialized


def test_gateway_personal_assistant_memory_review_preview_records_no_effect_review() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/memory-observations/review/preview",
        json={
            "candidate": _memory_preview_payload(),
            "review_id": "pa_memory_review_gateway_kept_001",
            "decision": "kept_for_operator_review",
            "reviewer_ref": "operator:tamirat",
            "reason_codes": ["operator_kept_for_review"],
            "reviewed_at": "2026-06-15T10:45:00+00:00",
            "review_evidence_ref": "proof://personal-assistant/memory/gateway-review-001",
        },
    )
    payload = response.json()
    review = payload["memory_review"]
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["effect_boundary"]["live_memory_write_allowed"] is False
    assert payload["effect_boundary"]["memory_admission_allowed"] is False
    assert payload["effect_boundary"]["nested_mind_live_activation_allowed"] is False
    assert review["decision"] == "kept_for_operator_review"
    assert receipt["decision"] == "deferred"
    assert "memory_observation_review_recorded" in receipt["actions_taken"]
    assert "memory_observation_not_admitted_to_live_memory" in receipt["actions_not_taken"]
    assert receipt["metadata"]["memory_admission_allowed"] is False


def test_gateway_personal_assistant_memory_review_preview_rejects_missing_revision_binding() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/memory-observations/review/preview",
        json={
            "candidate": _memory_preview_payload(),
            "review_id": "pa_memory_review_gateway_revision_001",
            "decision": "revision_requested",
            "reviewer_ref": "operator:tamirat",
            "reason_codes": ["needs_scope"],
            "reviewed_at": "2026-06-15T10:45:00+00:00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_memory_review_preview"


def test_gateway_personal_assistant_memory_review_preview_rejects_raw_payload() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    request_payload = {
        "candidate": _memory_preview_payload(),
        "review_id": "pa_memory_review_gateway_raw_001",
        "decision": "rejected",
        "reviewer_ref": "operator:tamirat",
        "reason_codes": ["unsafe_payload"],
        "reviewed_at": "2026-06-15T10:45:00+00:00",
        "metadata": {"raw_chat_log": "private transcript"},
    }

    response = client.post(
        "/api/v1/personal-assistant/memory-observations/review/preview",
        json=request_payload,
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 400
    assert "private transcript" not in serialized
    assert "memory_observation_review_recorded" not in serialized


def test_gateway_personal_assistant_teamops_preview_plans_without_provider_call() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/teamops/shared-inbox/plan/preview",
        json={
            "request_id": "pa_request_gateway_teamops_001",
            "submitted_at": "2026-06-15T11:00:00+00:00",
            "generated_at": "2026-06-15T11:01:00+00:00",
            "connector_refs": [_gmail_connector_ref()],
        },
    )
    payload = response.json()
    projection = payload["teamops_projection"]
    plan = projection["plan"]
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["effect_boundary"]["live_connector_execution_allowed"] is False
    assert payload["effect_boundary"]["live_probe_execution_allowed"] is False
    assert payload["effect_boundary"]["mailbox_read_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert projection["skill_id"] == "teamops.shared_inbox.plan"
    assert plan["live_probe_executed"] is False
    assert plan["live_probe_gate"]["external_provider_call_performed"] is False
    assert "gmail_not_called" in receipt["actions_not_taken"]
    assert "shared_inbox_not_read" in receipt["actions_not_taken"]


def test_gateway_personal_assistant_teamops_preview_rejects_missing_connector_proof() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/teamops/shared-inbox/plan/preview",
        json={
            "request_id": "pa_request_gateway_teamops_missing_connector_001",
            "submitted_at": "2026-06-15T11:00:00+00:00",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_teamops_shared_inbox_preview"


def test_gateway_personal_assistant_teamops_preview_rejects_raw_payload() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/teamops/shared-inbox/plan/preview",
        json={
            "request_id": "pa_request_gateway_teamops_raw_001",
            "submitted_at": "2026-06-15T11:00:00+00:00",
            "connector_refs": [_gmail_connector_ref()],
            "environment": {"raw_connector_payload": "private mailbox body"},
        },
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 400
    assert "private mailbox body" not in serialized
    assert "teamops_handoff_plan_prepared" not in serialized


def test_gateway_personal_assistant_github_codex_preview_reviews_without_github_call() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/github-codex/review/preview",
        json={
            "request_id": "pa_request_gateway_github_codex_001",
            "submitted_at": "2026-06-15T12:00:00+00:00",
            "generated_at": "2026-06-15T12:01:00+00:00",
            "connector_refs": [_github_connector_ref()],
            "repository_ref": "tamirat-wubie/mullu-control-plane",
            "pull_request_ref": "PR-1771",
            "change_summary": "Adds a no-effect TeamOps shared-inbox preview projection.",
            "changed_files": [
                "gateway/server.py",
                "schemas/personal_assistant_teamops_projection.schema.json",
            ],
            "risk_notes": ["must not call GitHub or mutate PR state"],
            "evidence_refs": ["proof://github/pr/1771"],
        },
    )
    payload = response.json()
    projection = payload["github_codex_projection"]
    plan = projection["plan"]
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["effect_boundary"]["live_connector_execution_allowed"] is False
    assert payload["effect_boundary"]["github_call_allowed"] is False
    assert payload["effect_boundary"]["repository_mutation_allowed"] is False
    assert payload["effect_boundary"]["pull_request_mutation_allowed"] is False
    assert payload["effect_boundary"]["deployment_mutation_allowed"] is False
    assert projection["skill_id"] == "github.pr.summarize"
    assert plan["evidence_gate"]["github_call_performed"] is False
    assert plan["evidence_gate"]["repository_write_performed"] is False
    assert "github_not_called" in receipt["actions_not_taken"]
    assert "pull_request_not_merged" in receipt["actions_not_taken"]


def test_gateway_personal_assistant_github_codex_preview_rejects_missing_connector_proof() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/github-codex/review/preview",
        json={
            "request_id": "pa_request_gateway_github_codex_missing_connector_001",
            "submitted_at": "2026-06-15T12:00:00+00:00",
            "change_summary": "Review a PR without connector proof.",
            "changed_files": ["gateway/server.py"],
            "evidence_refs": ["proof://github/pr/missing"],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_github_codex_review_preview"


def test_gateway_personal_assistant_github_codex_preview_rejects_secret_like_summary() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/github-codex/review/preview",
        json={
            "request_id": "pa_request_gateway_github_codex_raw_001",
            "submitted_at": "2026-06-15T12:00:00+00:00",
            "connector_refs": [_github_connector_ref()],
            "repository_ref": "tamirat-wubie/mullu-control-plane",
            "pull_request_ref": "PR-1771",
            "change_summary": "Use Bearer secret-token-value",
            "changed_files": ["gateway/server.py"],
            "evidence_refs": ["proof://github/pr/1771"],
        },
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 400
    assert "secret-token-value" not in serialized
    assert "github_codex_review_plan_prepared" not in serialized


def test_gateway_personal_assistant_research_preview_compares_without_web_search() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/research/source-compare/preview",
        json={
            "request_id": "pa_request_gateway_research_001",
            "submitted_at": "2026-06-15T13:00:00+00:00",
            "generated_at": "2026-06-15T13:01:00+00:00",
            "research_question": "Compare search receipt and personal assistant research boundaries.",
            "source_summaries": [
                {
                    "source_ref": "docs/78_search_receipt_contract.md",
                    "title": "Search Receipt Contract",
                    "publisher": "Mullusi repository",
                    "published_at": "2026-06-14",
                    "summary": "Defines evidence metadata and citation requirements.",
                    "trust_tier": "primary",
                    "citation_ref": "citation://docs/search-receipt-contract",
                }
            ],
            "citation_refs": ["citation://docs/search-receipt-contract"],
            "freshness_notes": ["operator supplied repository document"],
            "evidence_refs": ["proof://docs/search-receipt-contract"],
        },
    )
    payload = response.json()
    projection = payload["research_projection"]
    plan = projection["plan"]
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["effect_boundary"]["web_search_allowed"] is False
    assert payload["effect_boundary"]["web_search_performed"] is False
    assert payload["effect_boundary"]["external_submission_allowed"] is False
    assert payload["effect_boundary"]["public_post_allowed"] is False
    assert payload["effect_boundary"]["paid_subscription_allowed"] is False
    assert payload["effect_boundary"]["memory_write_allowed"] is False
    assert projection["skill_id"] == "research.web_search"
    assert plan["evidence_gate"]["web_search_performed"] is False
    assert plan["answer_claim_authority"] == "citation_backed_summary_only"
    assert "web_search_not_performed" in receipt["actions_not_taken"]
    assert "public_post_not_created" in receipt["actions_not_taken"]
    assert receipt["connectors_used"] == []


def test_gateway_personal_assistant_research_preview_rejects_non_research_intent() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/research/source-compare/preview",
        json={
            "request_id": "pa_request_gateway_research_wrong_intent_001",
            "submitted_at": "2026-06-15T13:00:00+00:00",
            "user_request": "Check my inbox.",
            "research_question": "Compare source metadata.",
            "source_summaries": [],
            "citation_refs": [],
            "evidence_refs": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_research_preview"


def test_gateway_personal_assistant_research_preview_rejects_raw_source_body() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/research/source-compare/preview",
        json={
            "request_id": "pa_request_gateway_research_raw_001",
            "submitted_at": "2026-06-15T13:00:00+00:00",
            "research_question": "Compare source metadata.",
            "source_summaries": [
                {
                    "source_ref": "source://raw",
                    "title": "Raw source",
                    "publisher": "operator",
                    "summary": "bounded",
                    "trust_tier": "operator_supplied",
                    "citation_ref": "citation://raw",
                    "raw_source_body": "full page body",
                }
            ],
            "citation_refs": ["citation://raw"],
            "evidence_refs": ["proof://raw"],
        },
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 422
    assert "full page body" not in serialized
    assert "research_source_compare_plan_prepared" not in serialized


def test_gateway_personal_assistant_math_preview_compares_without_effects() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/math/reasoning/preview",
        json={
            "request_id": "pa_request_gateway_math_001",
            "submitted_at": "2026-06-15T14:00:00+00:00",
            "generated_at": "2026-06-15T14:01:00+00:00",
            "problem_statement": "Compare baseline and proposed monthly software costs.",
            "known_values": [
                {
                    "label": "baseline platform",
                    "scenario_ref": "baseline",
                    "value": "100",
                    "unit": "usd_per_month",
                    "source_ref": "operator_supplied",
                    "notes": "planning estimate",
                },
                {
                    "label": "proposed platform",
                    "scenario_ref": "proposed",
                    "value": "80",
                    "unit": "usd_per_month",
                    "source_ref": "operator_supplied",
                    "notes": "planning estimate",
                },
            ],
            "assumptions": ["values are operator supplied"],
            "constraints": ["do not move money", "do not write records"],
            "evidence_refs": ["proof://operator/math-values"],
        },
    )
    payload = response.json()
    projection = payload["math_projection"]
    plan = projection["plan"]
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["effect_boundary"]["money_movement_allowed"] is False
    assert payload["effect_boundary"]["system_of_record_write_allowed"] is False
    assert payload["effect_boundary"]["connector_mutation_allowed"] is False
    assert payload["effect_boundary"]["deployment_allowed"] is False
    assert projection["skill_id"] == "math.reasoning.plan"
    assert plan["scenario_totals"] == [
        {"scenario_ref": "baseline", "unit": "usd_per_month", "total": "100"},
        {"scenario_ref": "proposed", "unit": "usd_per_month", "total": "80"},
    ]
    assert plan["evidence_gate"]["money_movement_performed"] is False
    assert plan["answer_claim_authority"] == "operator_supplied_values_only"
    assert "payment_not_moved" in receipt["actions_not_taken"]
    assert "system_of_record_not_written" in receipt["actions_not_taken"]
    assert receipt["connectors_used"] == []


def test_gateway_personal_assistant_math_preview_rejects_non_math_intent() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/math/reasoning/preview",
        json={
            "request_id": "pa_request_gateway_math_wrong_intent_001",
            "submitted_at": "2026-06-15T14:00:00+00:00",
            "user_request": "Check my inbox.",
            "problem_statement": "Compare costs.",
            "known_values": [],
            "evidence_refs": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_math_preview"


def test_gateway_personal_assistant_math_preview_rejects_raw_private_value() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/math/reasoning/preview",
        json={
            "request_id": "pa_request_gateway_math_raw_001",
            "submitted_at": "2026-06-15T14:00:00+00:00",
            "problem_statement": "Compare costs.",
            "known_values": [
                {
                    "label": "baseline",
                    "scenario_ref": "baseline",
                    "value": "100",
                    "unit": "usd_per_month",
                    "source_ref": "operator_supplied",
                    "notes": "planning estimate",
                    "raw_body": "private spreadsheet body",
                }
            ],
            "evidence_refs": ["proof://raw"],
        },
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 422
    assert "private spreadsheet body" not in serialized
    assert "calculation_plan_created" not in serialized


def test_gateway_personal_assistant_planning_preview_assigns_without_effects() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/planning/schedule/preview",
        json={
            "request_id": "pa_request_gateway_planning_001",
            "submitted_at": "2026-06-16T04:00:00+00:00",
            "generated_at": "2026-06-16T04:01:00+00:00",
            "objective": "Plan the operator work day from supplied windows and tasks.",
            "time_windows": [
                {
                    "window_ref": "morning",
                    "label": "Morning focus",
                    "start": "2026-06-16T09:00:00-04:00",
                    "end": "2026-06-16T11:00:00-04:00",
                    "capacity_minutes": 120,
                    "source_ref": "operator_supplied",
                    "notes": "planning estimate",
                },
                {
                    "window_ref": "afternoon",
                    "label": "Afternoon review",
                    "start": "2026-06-16T13:00:00-04:00",
                    "end": "2026-06-16T14:30:00-04:00",
                    "capacity_minutes": 90,
                    "source_ref": "operator_supplied",
                    "notes": "planning estimate",
                },
            ],
            "work_items": [
                {
                    "item_ref": "memo",
                    "title": "Write launch memo",
                    "estimated_minutes": 60,
                    "priority": 1,
                    "due": "2026-06-16T12:00:00-04:00",
                    "source_ref": "operator_supplied",
                    "notes": "planning estimate",
                },
                {
                    "item_ref": "receipts",
                    "title": "Review receipts",
                    "estimated_minutes": 45,
                    "priority": 2,
                    "due": "2026-06-16T15:00:00-04:00",
                    "source_ref": "operator_supplied",
                    "notes": "planning estimate",
                },
                {
                    "item_ref": "followups",
                    "title": "Triage followups",
                    "estimated_minutes": 30,
                    "priority": 3,
                    "due": "2026-06-16T17:00:00-04:00",
                    "source_ref": "operator_supplied",
                    "notes": "planning estimate",
                },
            ],
            "assumptions": ["values are operator supplied"],
            "constraints": ["do not create calendar events", "do not write tasks"],
            "evidence_refs": ["proof://operator/planning-values"],
        },
    )
    payload = response.json()
    projection = payload["planning_projection"]
    plan = projection["plan"]
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["effect_boundary"]["calendar_write_allowed"] is False
    assert payload["effect_boundary"]["task_write_allowed"] is False
    assert payload["effect_boundary"]["invite_allowed"] is False
    assert payload["effect_boundary"]["connector_mutation_allowed"] is False
    assert payload["effect_boundary"]["deployment_allowed"] is False
    assert projection["skill_id"] == "planning.optimize_schedule"
    assert plan["capacity_summary"][0]["assigned_minutes"] == "105"
    assert plan["capacity_summary"][0]["remaining_minutes"] == "15"
    assert plan["capacity_summary"][1]["assigned_minutes"] == "30"
    assert plan["capacity_summary"][1]["remaining_minutes"] == "60"
    assert [assignment["window_ref"] for assignment in plan["assignment_plan"]] == ["morning", "morning", "afternoon"]
    assert "calendar_event_not_created" in receipt["actions_not_taken"]
    assert "task_not_written" in receipt["actions_not_taken"]
    assert receipt["connectors_used"] == []


def test_gateway_personal_assistant_planning_preview_rejects_non_planning_intent() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/planning/schedule/preview",
        json={
            "request_id": "pa_request_gateway_planning_wrong_intent_001",
            "submitted_at": "2026-06-16T04:00:00+00:00",
            "user_request": "Check my inbox.",
            "objective": "Plan supplied work.",
            "time_windows": [],
            "work_items": [],
            "evidence_refs": [],
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"]["governed"] is True
    assert response.json()["detail"]["error_code"] == "invalid_personal_assistant_planning_preview"


def test_gateway_personal_assistant_planning_preview_rejects_raw_private_item() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/planning/schedule/preview",
        json={
            "request_id": "pa_request_gateway_planning_raw_001",
            "submitted_at": "2026-06-16T04:00:00+00:00",
            "objective": "Plan supplied work.",
            "time_windows": [
                {
                    "window_ref": "morning",
                    "label": "Morning",
                    "start": "2026-06-16T09:00:00-04:00",
                    "end": "2026-06-16T10:00:00-04:00",
                    "capacity_minutes": 60,
                    "source_ref": "operator_supplied",
                    "notes": "planning estimate",
                }
            ],
            "work_items": [
                {
                    "item_ref": "raw",
                    "title": "Raw task",
                    "estimated_minutes": 30,
                    "source_ref": "operator_supplied",
                    "raw_body": "private calendar body",
                }
            ],
            "evidence_refs": ["proof://raw"],
        },
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code == 422
    assert "private calendar body" not in serialized
    assert "schedule_plan_created" not in serialized


def _approval_preview_payload() -> dict[str, object]:
    return {
        "request_id": "pa_request_gateway_approval_001",
        "plan_id": "pa_plan_gateway_approval_001",
        "approver_ref": "operator:tamirat",
        "approval_scope": "per_recipient",
        "created_at": "2026-06-14T10:30:00+00:00",
        "approval_id": "pa_approval_gateway_email_send_001",
        "proposed_actions": [
            {
                "action_id": "send_prepared_email_draft",
                "skill_id": "email.send.with_approval",
                "risk_level": "P4",
                "effect_boundary": "external_email_send",
                "summary": "Send one approved email draft to one named recipient.",
            }
        ],
        "forbidden_without_approval": [
            "send",
            "forward",
            "recipient_unapproved",
            "connector_mutation",
        ],
        "evidence_refs": ["proof://personal-assistant/approval/gateway-email-send-001"],
    }


def _approval_proposal_plan() -> dict[str, object]:
    intent = GovernedIntent(
        request_id="pa_request_gateway_approval_proposal_001",
        submitted_at="2026-06-14T10:29:00+00:00",
        interface=RequestInterface.API_ROUTE,
        user_goal="Send one approved email draft to Daniel.",
        requested_capabilities=("email.send.with_approval",),
        requested_skill_ids=("email.send.with_approval",),
        risk_level=SkillRiskLevel.P4,
        requires_approval=True,
        execution_mode=RequestExecutionMode.EXECUTE_WITH_APPROVAL,
        approval_scope=ApprovalScope.PER_RECIPIENT,
        blocked_actions=("send", "forward", "connector_mutation"),
        evidence_refs=("proof://personal-assistant/gateway/approval-proposal-001",),
    )
    envelope = build_personal_assistant_preview_plan(
        intent,
        plan_id="pa_plan_gateway_approval_proposal_001",
        created_at="2026-06-14T10:29:00+00:00",
    )
    return dict(envelope.plan)


def _draft_approval_proposal_payload(
    *,
    draft_ref: str = "pa_draft_projection_item_gateway_email_001",
    draft_type: str = "email_response",
    draft_skill_id: str = "email.response.draft",
    summary: str = "Prepared email reply to Daniel using redacted thread evidence.",
    evidence_ref: str = "proof://personal-assistant/draft/gateway-email-001",
) -> dict[str, object]:
    return {
        "request_id": "pa_request_gateway_draft_approval_001",
        "plan_id": "pa_plan_gateway_draft_approval_001",
        "created_at": "2026-06-14T10:33:00+00:00",
        "approval_scope": "per_action",
        "approver_ref": "operator:tamirat",
        "include_console_read_model": True,
        "draft": {
            "draft_ref": draft_ref,
            "draft_type": draft_type,
            "draft_skill_id": draft_skill_id,
            "summary": summary,
            "evidence_refs": [evidence_ref],
        },
    }


def _memory_preview_payload() -> dict[str, object]:
    return {
        "request_id": "pa_request_gateway_memory_001",
        "memory_observation_id": "pa_memory_gateway_preference_001",
        "memory_type": "preference",
        "claim": "User prefers one-at-a-time repository closures.",
        "source": {
            "source_type": "user_confirmation",
            "source_ref": "conversation:personal-assistant-memory-preview",
            "observed_at": "2026-06-14T10:40:00+00:00",
        },
        "confidence": "high",
        "scope": "assistant_workflow",
        "mutable": True,
        "receipt_id": "pa_receipt_gateway_memory_source_001",
        "evidence_refs": ["proof://personal-assistant/memory/gateway-preference-001"],
        "observed_at": "2026-06-14T10:40:00+00:00",
    }


def _gmail_connector_ref() -> dict[str, object]:
    return {
        "connector_id": "connector:gmail:operator",
        "connector_name": "gmail",
        "proof_state": "Pass",
        "private_data_allowed": True,
        "scopes": ["gmail.readonly"],
    }


def _calendar_connector_ref() -> dict[str, object]:
    return {
        "connector_id": "connector:google-calendar:operator",
        "connector_name": "google_calendar",
        "proof_state": "Pass",
        "private_data_allowed": True,
        "scopes": ["calendar.readonly"],
    }


def _github_connector_ref() -> dict[str, object]:
    return {
        "connector_id": "connector:github:operator",
        "connector_name": "github",
        "proof_state": "Pass",
        "private_data_allowed": True,
        "scopes": ["repo.read"],
    }
