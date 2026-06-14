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
