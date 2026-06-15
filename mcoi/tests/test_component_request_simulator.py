"""Tests for the Component Harness request simulator.

Purpose: prove request simulation predicts governed component paths without
granting live execution, connector calls, mutation, or terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: FastAPI TestClient and component_request_simulator.
Invariants: simulation is preview-only, deterministic, and fail-closed for
unknown or blocked action requests.
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.component_request_simulator import (
    foundation_component_request_simulations,
    simulate_component_request,
)
from mcoi_runtime.app.routers.components import router


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_component_request_simulator_predicts_send_email_blocked() -> None:
    simulation = simulate_component_request("Send this email to the customer")

    assert simulation["intent"] == "send_email_request"
    assert simulation["outcome"] == "GovernanceBlocked"
    assert simulation["approval_required"] is True
    assert simulation["selected_component_ids"] == [
        "governance_core",
        "personal_assistant",
        "gmail_account_binding_gate",
    ]
    assert "send_email" in simulation["blocked_actions"]
    assert "authority_denial_receipt" in simulation["expected_receipts"]


def test_component_request_simulator_routes_deep_analysis_read_only() -> None:
    simulation = simulate_component_request("Analyze this idea deeply")

    assert simulation["intent"] == "deep_symbolic_analysis"
    assert simulation["outcome"] == "SolvedUnverified"
    assert simulation["approval_required"] is False
    assert simulation["selected_component_ids"] == [
        "governance_core",
        "inceptadive_shadow",
        "snet",
    ]
    assert simulation["can_execute"] is False
    assert "terminal_closure" in simulation["blocked_actions"]


def test_component_request_simulator_route_is_preview_only() -> None:
    client = _client()

    response = client.post(
        "/api/v1/components/simulate",
        json={"request_text": "Run this worker task"},
    )
    get_response = client.get("/api/v1/components/simulate")
    put_response = client.put(
        "/api/v1/components/simulate",
        json={"request_text": "Run this worker task"},
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["simulation_is_not_execution_authority"] is True
    assert payload["live_execution_enabled"] is False
    assert payload["can_call_connector"] is False
    assert payload["can_mutate"] is False
    assert payload["outcome"] == "GovernanceBlocked"
    assert get_response.status_code == 405
    assert put_response.status_code == 405


def test_component_request_simulator_unknown_request_awaiting_evidence() -> None:
    simulations = foundation_component_request_simulations()
    unknown = simulate_component_request("Classify this new component request")

    assert len(simulations) == 6
    assert unknown["intent"] == "unknown_component_request"
    assert unknown["outcome"] == "AwaitingEvidence"
    assert unknown["selected_component_ids"] == ["governance_core"]
    assert unknown["approval_required"] is True
    assert "component_request_intent_classification_receipt" in unknown["needed_evidence"]
