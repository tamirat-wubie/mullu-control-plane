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
    assert payload["registry"]["skill_count"] >= 14
    assert "email.response.draft" in payload["registry"]["skill_ids"]


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
