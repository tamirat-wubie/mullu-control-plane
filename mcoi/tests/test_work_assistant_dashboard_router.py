from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers.work_assistant_dashboard import ROUTE_PATH, router


_EFFECT_FALSE_FIELDS = (
    "live_connector_execution_allowed",
    "mailbox_read_allowed",
    "mailbox_mutation_allowed",
    "external_send_allowed",
    "calendar_write_allowed",
    "repository_write_allowed",
    "worker_dispatch_allowed",
    "live_receipt_append_allowed",
    "production_readiness_claim_allowed",
    "customer_readiness_claim_allowed",
    "autonomous_execution_authority_allowed",
)


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def _default_app_client() -> TestClient:
    from mcoi_runtime.app.server import app

    return TestClient(app)


def _assert_no_effect_dashboard_payload(body: dict[str, object]) -> None:
    assert body["dashboard_id"] == "governed_work_assistant_demo_operator_dashboard_v0"
    assert body["product_name"] == "Governed Work Assistant Demo v0"
    assert body["legacy_internal_pilot_id"] == "governed_team_assistant_pilot_v0"
    assert body["governed"] is True
    assert body["read_only"] is True
    assert body["fixture_backed"] is True
    assert body["stage"] == "no_effect_operator_projection"
    assert len(body["panels"]) >= 8
    assert {panel["panel_id"] for panel in body["panels"]} >= {
        "product_identity",
        "assistant_readiness",
        "skill_catalog",
        "blocked_actions",
        "draft_preview",
        "approval_preview",
        "receipt_trail",
        "closure_evidence",
        "no_effect_boundary",
    }
    for field in _EFFECT_FALSE_FIELDS:
        assert body["effect_boundary"][field] is False


def test_work_assistant_dashboard_route_returns_no_effect_projection() -> None:
    client = _client()

    response = client.get(ROUTE_PATH)
    body = response.json()

    assert response.status_code == 200
    _assert_no_effect_dashboard_payload(body)


def test_work_assistant_dashboard_route_boundary_is_no_effect() -> None:
    client = _client()

    response = client.get(ROUTE_PATH)
    route_boundary = response.json()["route_boundary"]

    assert route_boundary["method"] == "GET"
    assert route_boundary["read_only"] is True
    assert route_boundary["fixture_backed"] is True
    assert route_boundary["execution_allowed"] is False
    assert route_boundary["live_connector_execution_allowed"] is False
    assert route_boundary["external_send_allowed"] is False
    assert route_boundary["repository_write_allowed"] is False
    assert route_boundary["worker_dispatch_allowed"] is False
    assert route_boundary["live_receipt_append_allowed"] is False


def test_work_assistant_dashboard_route_rejects_post() -> None:
    client = _client()

    response = client.post(ROUTE_PATH, json={})

    assert response.status_code == 405


def test_work_assistant_dashboard_default_app_mount_is_no_effect() -> None:
    client = _default_app_client()

    response = client.get(ROUTE_PATH)
    body = response.json()

    assert response.status_code == 200
    _assert_no_effect_dashboard_payload(body)
    assert body["route_boundary"]["execution_allowed"] is False
    assert body["route_boundary"]["live_connector_execution_allowed"] is False
    assert body["route_boundary"]["repository_write_allowed"] is False
    assert body["route_boundary"]["worker_dispatch_allowed"] is False
    assert body["route_boundary"]["live_receipt_append_allowed"] is False


def test_work_assistant_dashboard_default_app_rejects_post() -> None:
    client = _default_app_client()

    response = client.post(ROUTE_PATH, json={})

    assert response.status_code == 405
