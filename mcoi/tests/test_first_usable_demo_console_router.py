from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mcoi_runtime.app.routers import first_usable_demo_console as route_module


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(route_module.router)
    return TestClient(app)


def test_first_usable_demo_console_route_returns_no_effect_read_model() -> None:
    response = _client().get(route_module.ROUTE_PATH)

    assert response.status_code == 200
    payload = response.json()
    assert payload["governed"] is True
    assert payload["status"] == "foundation_read_only"
    assert payload["effect_boundary"]["execution_allowed"] is False
    assert payload["effect_boundary"]["live_connector_execution_allowed"] is False
    assert payload["effect_boundary"]["external_send_allowed"] is False
    assert payload["effect_boundary"]["memory_write_allowed"] is False
    assert payload["first_usable_demo"]["read_only"] is True
    assert payload["first_usable_demo"]["fixture_backed"] is True
    assert payload["first_usable_demo"]["effect_boundary"]["execution_allowed"] is False
    assert payload["first_usable_demo"]["effect_boundary"]["external_send_allowed"] is False
    assert payload["first_usable_demo"]["effect_boundary"]["money_movement_allowed"] is False
    assert payload["first_usable_demo_binding"]["read_only"] is True
    assert payload["first_usable_demo_binding"]["execution_allowed"] is False
    assert payload["first_usable_demo_binding"]["customer_readiness_claim_allowed"] is False
    assert payload["route_boundary"]["route_path"] == route_module.ROUTE_PATH
    assert payload["route_boundary"]["method"] == "GET"
    assert payload["route_boundary"]["read_only"] is True
    assert payload["route_boundary"]["default_mounted"] is False
    assert payload["route_boundary"]["live_receipt_append_allowed"] is False


def test_first_usable_demo_console_route_rejects_mutating_methods() -> None:
    response = _client().post(route_module.ROUTE_PATH)

    assert response.status_code == 405


def test_first_usable_demo_console_route_rejects_authority_drift(monkeypatch) -> None:
    def drifted_binding(*, generated_at: str) -> dict[str, object]:
        return {
            "governed": True,
            "effect_boundary": {
                "execution_allowed": True,
                "live_connector_execution_allowed": False,
                "external_send_allowed": False,
                "memory_write_allowed": False,
                "deployment_mutation_allowed": False,
            },
            "first_usable_demo": {
                "effect_boundary": {
                    "execution_allowed": False,
                    "live_connector_execution_allowed": False,
                    "connector_mutation_allowed": False,
                    "external_send_allowed": False,
                    "money_movement_allowed": False,
                    "memory_write_allowed": False,
                    "deployment_mutation_allowed": False,
                    "customer_readiness_claim_allowed": False,
                    "public_launch_claim_allowed": False,
                    "approval_is_execution": False,
                }
            },
            "first_usable_demo_binding": {
                "execution_allowed": False,
                "live_connector_execution_allowed": False,
                "external_send_allowed": False,
                "connector_mutation_allowed": False,
                "memory_write_allowed": False,
                "deployment_mutation_allowed": False,
                "customer_readiness_claim_allowed": False,
            },
        }

    monkeypatch.setattr(route_module, "build_first_usable_demo_console_binding", drifted_binding)

    response = _client().get(route_module.ROUTE_PATH)

    assert response.status_code == 409
    assert response.json()["detail"]["error"] == "first_usable_demo_console_authority_drift"
    assert "effect_boundary.execution_allowed must be false" in response.json()["detail"]["message"]
