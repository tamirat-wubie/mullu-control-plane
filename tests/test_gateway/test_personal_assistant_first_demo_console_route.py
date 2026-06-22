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
    walkthrough = first_demo["invoice_email_walkthrough"]
    binding = payload["first_usable_demo_binding"]
    serialized = json.dumps(payload, sort_keys=True)

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["governed"] is True
    assert payload["sections"]["first_usable_demo"]["item_count"] == 1
    assert payload["sections"]["first_usable_demo"]["walkthrough_count"] == 1
    assert payload["sections"]["first_usable_demo"]["draft_only_walkthrough_bound"] is True
    assert payload["sections"]["first_usable_demo"]["execution_allowed"] is False
    assert payload["sections"]["first_usable_demo"]["live_connector_execution_allowed"] is False
    assert payload["sections"]["first_usable_demo"]["external_send_allowed"] is False
    assert payload["sections"]["first_usable_demo"]["customer_readiness_claim_allowed"] is False
    assert first_demo["read_model_id"] == "first_usable_demo_operator_read_model_v1"
    assert first_demo["source_packet_id"] == "first_usable_demo_packet_v1"
    assert first_demo["demo_name"] == "Governed Personal Assistant First Usable Demo"
    assert first_demo["read_only"] is True
    assert first_demo["fixture_backed"] is True
    assert first_demo["walkthroughs"]["item_count"] == 1
    assert first_demo["walkthroughs"]["draft_only_walkthrough_bound"] is True
    assert first_demo["walkthroughs"]["external_send_allowed"] is False
    assert first_demo["walkthroughs"]["provider_draft_creation_allowed"] is False
    assert first_demo["walkthroughs"]["invoice_payment_allowed"] is False
    assert first_demo["walkthroughs"]["customer_readiness_claim_allowed"] is False
    assert first_demo["effect_boundary"]["execution_allowed"] is False
    assert first_demo["effect_boundary"]["live_connector_execution_allowed"] is False
    assert first_demo["effect_boundary"]["connector_mutation_allowed"] is False
    assert first_demo["effect_boundary"]["external_send_allowed"] is False
    assert first_demo["effect_boundary"]["money_movement_allowed"] is False
    assert first_demo["effect_boundary"]["memory_write_allowed"] is False
    assert first_demo["effect_boundary"]["deployment_mutation_allowed"] is False
    assert first_demo["effect_boundary"]["customer_readiness_claim_allowed"] is False
    assert first_demo["assurance"]["packet_valid"] is True
    assert first_demo["assurance"]["invoice_email_walkthrough_valid"] is True
    assert first_demo["assurance"]["authority_drift_detected"] is False
    assert first_demo["assurance"]["live_connector_execution_allowed"] is False
    assert walkthrough["read_model_id"] == "invoice_email_draft_walkthrough_panel_v1"
    assert walkthrough["walkthrough_id"] == "personal_assistant_invoice_email_draft_walkthrough_v1"
    assert walkthrough["read_only"] is True
    assert walkthrough["fixture_backed"] is True
    assert walkthrough["draft_status"] == "draft_preview_only"
    assert walkthrough["approval_required_before_send"] is True
    assert walkthrough["approval_is_execution"] is False
    assert walkthrough["effect_summary"]["execution_allowed"] is False
    assert walkthrough["effect_summary"]["external_send_allowed"] is False
    assert walkthrough["effect_summary"]["provider_draft_creation_allowed"] is False
    assert walkthrough["effect_summary"]["invoice_payment_allowed"] is False
    assert walkthrough["effect_summary"]["money_movement_allowed"] is False
    assert walkthrough["effect_summary"]["memory_write_allowed"] is False
    assert walkthrough["effect_summary"]["deployment_mutation_allowed"] is False
    assert walkthrough["effect_summary"]["customer_readiness_claim_allowed"] is False
    assert walkthrough["claim_summary"]["draft_preview_is_send_authority"] is False
    assert walkthrough["claim_summary"]["approval_review_is_execution"] is False
    assert walkthrough["assurance"]["walkthrough_valid"] is True
    assert walkthrough["assurance"]["draft_preview_only"] is True
    assert walkthrough["assurance"]["external_send_allowed"] is False
    assert walkthrough["assurance"]["provider_draft_creation_allowed"] is False
    assert "email_not_sent" in walkthrough["actions_not_taken"]
    assert "provider_draft_not_created" in walkthrough["actions_not_taken"]
    assert "invoice_not_paid" in walkthrough["actions_not_taken"]
    assert binding["binding_state"] == "bound_to_existing_console_route"
    assert binding["execution_allowed"] is False
    assert binding["live_connector_execution_allowed"] is False
    assert binding["external_send_allowed"] is False
    assert binding["connector_mutation_allowed"] is False
    assert binding["memory_write_allowed"] is False
    assert binding["deployment_mutation_allowed"] is False
    assert binding["customer_readiness_claim_allowed"] is False
    assert "examples/first_usable_demo_packet.json" in payload["evidence_refs"]
    assert "examples/personal_assistant_invoice_email_walkthrough.json" in payload["evidence_refs"]
    assert "mcoi/mcoi_runtime/personal_assistant/console_first_demo.py" in payload["evidence_refs"]
    assert "raw_private_connector_payload" not in serialized
    assert "secret-worker-token" not in serialized


def test_gateway_personal_assistant_console_html_view_renders_invoice_walkthrough_panel() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/console/personal-assistant/view")
    post_response = client.post("/api/v1/console/personal-assistant/view", json={})
    body = response.text

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert "Mullu Personal Assistant Console" in body
    assert "Assistant Readiness" in body
    assert "Invoice Email Draft Walkthrough" in body
    assert "personal_assistant_invoice_email_draft_walkthrough_v1" in body
    assert "Draft Status" in body
    assert "draft_preview_only" in body
    assert "Approval Required Before Send" in body
    assert "Provider Draft Creation Allowed" in body
    assert "Invoice Payment Allowed" in body
    assert "Customer Readiness Claim Allowed" in body
    assert "Execution Allowed" in body
    assert "False" in body
    assert "secret-worker-token" not in body
