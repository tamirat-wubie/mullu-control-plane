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
    assert payload["registry"]["skill_count"] >= 15
    assert "email.response.draft" in payload["registry"]["skill_ids"]


def test_gateway_personal_assistant_console_read_model_exposes_lane_status() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/console/personal-assistant")
    post_response = client.post("/api/v1/console/personal-assistant", json={})
    payload = response.json()
    lane_status = payload["lane_status"]
    lane_ids = [lane["lane_id"] for lane in lane_status["lanes"]]

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["console_id"] == "personal_assistant_console_foundation"
    assert payload["status"] == "foundation_read_only"
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["governed"] is True
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
    assert "Foundation Lanes" in body
    assert "foundation_read_only" in body
    assert "/api/v1/console/personal-assistant" in body
    assert "Execution Allowed" in body
    assert "False" in body


def test_gateway_personal_assistant_readiness_demo_is_read_only() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/console/personal-assistant/readiness")
    post_response = client.post("/api/v1/console/personal-assistant/readiness", json={})
    payload = response.json()

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["governed"] is True
    assert payload["user_ask"] == "Show my assistant readiness."
    assert payload["inbox_projection_status"]["status"] == "projection_contract_ready"
    assert payload["inbox_projection_status"]["mailbox_read_allowed"] is False
    assert payload["inbox_projection_status"]["mailbox_mutation_allowed"] is False
    assert payload["calendar_projection_status"]["status"] == "projection_contract_ready"
    assert payload["calendar_projection_status"]["calendar_write_allowed"] is False
    assert payload["available_skills"]["skill_count"] >= 15
    assert "email.inbox.summarize" in payload["available_skills"]["read_only_skill_ids"]
    assert "calendar.day.brief" in payload["available_skills"]["read_only_skill_ids"]
    assert "send_email" in payload["blocked_actions"]
    assert payload["required_approvals"]["approval_before_send_required"] is True
    assert payload["required_approvals"]["approval_is_execution"] is False
    assert payload["receipts"]["viewer_binding"]["runtime_dispatch_allowed"] is False
    assert payload["effect_boundary"]["live_connector_execution_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False


def test_gateway_personal_assistant_pilot_read_model_packages_controlled_demo() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/personal-assistant/pilot/read-model")
    post_response = client.post("/api/v1/personal-assistant/pilot/read-model", json={})
    payload = response.json()
    stage_ids = [stage["stage_id"] for stage in payload["pilot_stages"]]

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["pilot_id"] == "governed_team_assistant_pilot"
    assert payload["status"] == "controlled_demo_productization"
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["governed"] is True
    assert payload["stage_count"] == 5
    assert stage_ids == [
        "teamops_terminal_closure",
        "personal_assistant_readiness_demo",
        "approval_queue_v0",
        "teamops_gmail_live_probe",
        "draft_only_assistant",
    ]
    assert all(stage["receipt_required"] is True for stage in payload["pilot_stages"])
    assert payload["required_approvals"]["approval_queue_v0_required_before_live_effect"] is True
    assert payload["required_approvals"]["approval_is_execution"] is False
    assert payload["effect_boundary"]["execution_allowed"] is False
    assert payload["effect_boundary"]["live_connector_execution_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert payload["effect_boundary"]["mailbox_mutation_allowed"] is False
    assert payload["effect_boundary"]["calendar_write_allowed"] is False
    assert payload["effect_boundary"]["task_write_allowed"] is False
    assert payload["effect_boundary"]["public_readiness_claim_allowed"] is False
    assert payload["effect_boundary"]["snet_live_execution_authority_allowed"] is False
    assert payload["stage_boundaries"]["draft_only_assistant"]["draft_preparation_allowed"] is True
    assert payload["stage_boundaries"]["draft_only_assistant"]["external_send_allowed"] is False
    assert payload["stage_boundaries"]["teamops_gmail_live_probe"]["external_provider_call_performed"] is False
    assert "live_gmail_send" in payload["blocked_actions"]
    assert "snet_live_execution_authority" in payload["blocked_actions"]


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
    queue_v0 = payload["approval_queue_v0"]

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
    assert queue_v0["queue_version"] == "v0"
    assert queue_v0["draft_action_count"] == 1
    assert queue_v0["draft_actions"][0]["action_id"] == "send_prepared_email_draft"
    assert queue_v0["risk_class"] == "P4"
    assert queue_v0["requested_approval"]["approval_state"] == "requested"
    assert queue_v0["requested_approval"]["explicit_approval_required"] is True
    assert sorted(queue_v0["decision_controls"]) == ["approve", "reject", "revise"]
    assert queue_v0["receipt"]["decision"] == "approval_required"
    assert "external_message_not_sent" in queue_v0["receipt"]["actions_not_taken"]
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


def test_gateway_personal_assistant_approval_queue_revise_projection_still_defers_execution() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    request_payload = {
        **_approval_preview_payload(),
        "decision": "revised",
        "reason_codes": ["draft_requires_revision"],
        "decided_at": "2026-06-14T10:36:00+00:00",
        "revision_request": "Revise the draft before any later approval.",
    }

    response = client.post(
        "/api/v1/personal-assistant/approval-queue/preview",
        json=request_payload,
    )
    payload = response.json()
    queue_v0 = payload["approval_queue_v0"]

    assert response.status_code == 200
    assert payload["approval"]["packet"]["approval_state"] == "revised"
    assert payload["receipt"]["decision"] == "deferred"
    assert "approval_revision_requested" in payload["receipt"]["actions_taken"]
    assert queue_v0["requested_approval"]["approval_state"] == "revised"
    assert queue_v0["state_counts"]["revised"] == 1
    assert queue_v0["receipt"]["decision"] == "deferred"
    assert queue_v0["effect_boundary"]["execution_allowed"] is False
    assert queue_v0["effect_boundary"]["external_send_allowed"] is False


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


def test_gateway_personal_assistant_drafts_read_model_is_no_effect() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/personal-assistant/drafts")
    post_response = client.post("/api/v1/personal-assistant/drafts", json={})
    payload = response.json()

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["status"] == "draft_only_available"
    assert payload["effect_boundary"]["draft_preparation_allowed"] is True
    assert payload["effect_boundary"]["execution_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert payload["effect_boundary"]["calendar_write_allowed"] is False
    assert payload["effect_boundary"]["task_write_allowed"] is False
    assert payload["approval_queue_required_before_effect"] is True


def test_gateway_personal_assistant_email_draft_preview_prepares_without_send() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/drafts/email/preview",
        json={
            "request_id": "pa_request_gateway_email_draft_001",
            "submitted_at": "2026-06-18T13:00:00+00:00",
            "generated_at": "2026-06-18T13:01:00+00:00",
            "connector_refs": [_gmail_connector_ref()],
            "draft_input": _email_draft_input(),
        },
    )
    payload = response.json()
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["execution_allowed"] is False
    assert payload["draft_projection"]["skill_id"] == "email.response.draft"
    assert payload["draft"]["approval_required_before_send"] is True
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert payload["effect_boundary"]["mailbox_mutation_allowed"] is False
    assert "email_not_sent" in receipt["actions_not_taken"]
    assert receipt["metadata"]["external_write_allowed"] is False


def test_gateway_personal_assistant_calendar_draft_preview_prepares_without_write() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/drafts/calendar/preview",
        json={
            "request_id": "pa_request_gateway_calendar_draft_001",
            "submitted_at": "2026-06-18T13:05:00+00:00",
            "generated_at": "2026-06-18T13:06:00+00:00",
            "connector_refs": [_calendar_connector_ref()],
            "draft_input": _calendar_draft_input(),
        },
    )
    payload = response.json()
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["draft_projection"]["skill_id"] == "calendar.event.draft"
    assert payload["draft"]["approval_required_before_create_or_invite"] is True
    assert payload["effect_boundary"]["calendar_write_allowed"] is False
    assert "calendar_event_not_created" in receipt["actions_not_taken"]
    assert "people_not_invited" in receipt["actions_not_taken"]
    assert receipt["metadata"]["connector_mutation_allowed"] is False


def test_gateway_personal_assistant_task_draft_preview_prepares_without_task_write() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.post(
        "/api/v1/personal-assistant/drafts/task/preview",
        json={
            "request_id": "pa_request_gateway_task_draft_001",
            "submitted_at": "2026-06-18T13:10:00+00:00",
            "generated_at": "2026-06-18T13:11:00+00:00",
            "draft_input": _task_draft_input(),
        },
    )
    payload = response.json()
    receipt = payload["receipt"]

    assert response.status_code == 200
    assert payload["draft_projection"]["skill_id"] == "task.create_draft"
    assert payload["draft"]["approval_required_before_task_write"] is True
    assert payload["effect_boundary"]["task_write_allowed"] is False
    assert payload["effect_boundary"]["memory_write_allowed"] is False
    assert "task_not_written" in receipt["actions_not_taken"]
    assert receipt["connectors_used"] == []


def test_gateway_personal_assistant_email_draft_preview_rejects_raw_payload() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))
    draft_input = _email_draft_input() | {"raw_message_body": "private mailbox body"}

    response = client.post(
        "/api/v1/personal-assistant/drafts/email/preview",
        json={
            "request_id": "pa_request_gateway_email_draft_raw_001",
            "submitted_at": "2026-06-18T13:12:00+00:00",
            "connector_refs": [_gmail_connector_ref()],
            "draft_input": draft_input,
        },
    )
    serialized = json.dumps(response.json(), sort_keys=True)

    assert response.status_code in {400, 422}
    assert "private mailbox body" not in serialized
    assert "email_response_draft_prepared" not in serialized


def test_gateway_personal_assistant_teamops_gmail_live_probe_readiness_is_no_effect(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    for key, value in {
        "MULLU_EMAIL_CALENDAR_WORKER_ADAPTER": "google",
        "EMAIL_CALENDAR_CONNECTOR_ID": "gmail",
        "MULLU_GMAIL_CONNECTOR_OPERATION_FAMILY": "read_only_search",
        "GMAIL_SCOPE_ID": "gmail.readonly",
        "GMAIL_OAUTH_CLIENT_ID": "client-id-secret-shaped-value",
        "GMAIL_OAUTH_CLIENT_SECRET": "client_secret=must-not-leak",
        "GMAIL_REFRESH_TOKEN": "refresh_token=must-not-leak",
        "MULLU_GMAIL_OAUTH_CONSENT_WITNESS_REF": "witness:gmail-consent",
        "MULLU_GMAIL_OAUTH_CLIENT_WITNESS_REF": "witness:gmail-client",
        "MULLU_GMAIL_LEAST_PRIVILEGE_SCOPE_RECEIPT_REF": "receipt:gmail-scope",
        "MULLU_GMAIL_REFRESH_TOKEN_STORAGE_RECEIPT_REF": "receipt:gmail-refresh-storage",
        "MULLU_GMAIL_REVOCATION_RECOVERY_RECEIPT_REF": "receipt:gmail-revocation-recovery",
    }.items():
        monkeypatch.setenv(key, value)
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/personal-assistant/teamops/gmail/live-probe/readiness")
    payload = response.json()
    serialized = json.dumps(payload, sort_keys=True)

    assert response.status_code == 200
    assert payload["status"] == "passed"
    assert payload["solver_outcome"] == "SolvedVerified"
    assert payload["connector_readiness"]["ready_for_live_probe"] is True
    assert payload["token_presence"]["all_present"] is False
    assert payload["durable_oauth_presence"]["all_present"] is True
    assert payload["mailbox_access_boundary"]["least_privilege_satisfied"] is True
    assert payload["effect_boundary"]["external_provider_call_performed"] is False
    assert payload["effect_boundary"]["mailbox_read_performed"] is False
    assert payload["effect_boundary"]["provider_mutation_performed"] is False
    assert "read_full_mailbox" in payload["blocked_actions"]
    assert "gmail_provider_not_called" in payload["actions_not_taken"]
    assert "client_secret=must-not-leak" not in serialized
    assert "refresh_token=must-not-leak" not in serialized
    assert "client-id-secret-shaped-value" not in serialized


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


def _email_draft_input() -> dict[str, object]:
    return {
        "message_ref": "msg:gateway-email-draft",
        "recipient_label": "operator-visible recipient",
        "sender_label": "operator",
        "subject_digest": "project update digest",
        "thread_summary_digest": "redacted thread summary",
        "response_goal": "I can review the packet today and send comments tomorrow.",
        "tone": "direct",
        "constraints": ["do not promise deployment"],
    }


def _calendar_draft_input() -> dict[str, object]:
    return {
        "meeting_goal": "Review the handoff packet.",
        "title_digest": "handoff review digest",
        "proposed_window": "2026-06-18 afternoon",
        "duration_minutes": 30,
        "attendee_labels": ["operator-visible teammate"],
        "location_label": "video call label",
        "agenda_digest": "review blockers and next action",
        "constraints": ["do not invite before approval"],
    }


def _task_draft_input() -> dict[str, object]:
    return {
        "task_goal": "Review release notes before the next closure step.",
        "source_ref": "conversation:release-notes",
        "title_digest": "review release notes digest",
        "priority": "medium",
        "due_hint": "next working session",
        "acceptance_digest": "notes reviewed and blockers recorded",
        "constraints": ["do not write task state before approval"],
    }
