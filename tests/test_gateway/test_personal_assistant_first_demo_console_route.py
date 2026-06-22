"""Gateway first usable demo console route tests.

Purpose: verify the existing Personal Assistant console route exposes the first
usable demo read model without granting effect authority.
Governance scope: read-only route projection, fixture-backed demo visibility,
and customer-readiness claim separation.
Invariants: route access does not execute skills, call connectors, create drafts,
send messages, write memory, mutate deployments, or claim customer readiness.
"""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from gateway.server import create_gateway_app


class StubPlatform:
    """Minimal governed platform fixture for gateway app construction."""

    def connect(self, *, identity_id: str, tenant_id: str):  # noqa: ANN001
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):  # noqa: ANN001
        return type("Result", (), {"content": "ok", "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        return None


def test_gateway_personal_assistant_console_route_exposes_first_usable_demo_read_model() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/console/personal-assistant")
    post_response = client.post("/api/v1/console/personal-assistant", json={})
    payload = response.json()
    first_demo = payload["first_usable_demo"]
    binding = payload["first_usable_demo_binding"]
    serialized = json.dumps(payload, sort_keys=True)

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["governed"] is True
    assert payload["sections"]["first_usable_demo"]["item_count"] == 1
    assert payload["sections"]["first_usable_demo"]["execution_allowed"] is False
    assert payload["sections"]["first_usable_demo"]["live_connector_execution_allowed"] is False
    assert payload["sections"]["first_usable_demo"]["external_send_allowed"] is False
    assert payload["sections"]["first_usable_demo"]["customer_readiness_claim_allowed"] is False
    assert first_demo["read_model_id"] == "first_usable_demo_operator_read_model_v1"
    assert first_demo["source_packet_id"] == "first_usable_demo_packet_v1"
    assert first_demo["demo_name"] == "Governed Personal Assistant First Usable Demo"
    assert first_demo["read_only"] is True
    assert first_demo["fixture_backed"] is True
    assert first_demo["effect_boundary"]["execution_allowed"] is False
    assert first_demo["effect_boundary"]["live_connector_execution_allowed"] is False
    assert first_demo["effect_boundary"]["connector_mutation_allowed"] is False
    assert first_demo["effect_boundary"]["external_send_allowed"] is False
    assert first_demo["effect_boundary"]["money_movement_allowed"] is False
    assert first_demo["effect_boundary"]["memory_write_allowed"] is False
    assert first_demo["effect_boundary"]["deployment_mutation_allowed"] is False
    assert first_demo["effect_boundary"]["customer_readiness_claim_allowed"] is False
    assert first_demo["assurance"]["packet_valid"] is True
    assert first_demo["assurance"]["authority_drift_detected"] is False
    assert first_demo["assurance"]["live_connector_execution_allowed"] is False
    assert binding["binding_state"] == "bound_to_existing_console_route"
    assert binding["execution_allowed"] is False
    assert binding["live_connector_execution_allowed"] is False
    assert binding["external_send_allowed"] is False
    assert binding["connector_mutation_allowed"] is False
    assert binding["memory_write_allowed"] is False
    assert binding["deployment_mutation_allowed"] is False
    assert binding["customer_readiness_claim_allowed"] is False
    assert "examples/first_usable_demo_packet.json" in payload["evidence_refs"]
    assert "mcoi/mcoi_runtime/personal_assistant/console_first_demo.py" in payload["evidence_refs"]
    assert "raw_private_connector_payload" not in serialized
    assert "secret-worker-token" not in serialized


def test_gateway_personal_assistant_console_html_view_still_renders_after_first_demo_binding() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/console/personal-assistant/view")
    post_response = client.post("/api/v1/console/personal-assistant/view", json={})
    body = response.text

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert "Mullu Personal Assistant Console" in body
    assert "Assistant Readiness" in body
    assert "Execution Allowed" in body
    assert "False" in body
    assert "secret-worker-token" not in body
