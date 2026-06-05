"""Purpose: verify tool permission primitive operator API routes.

Governance scope: route-level registration, bounded listing, dry-run
permission evaluation, and fail-closed absence handling.
Dependencies: FastAPI TestClient and app-level tool permission registry.
Invariants: registering a permission requires governed routing, evaluation does
not execute a tool, duplicate permissions fail closed, and missing permissions
deny with bounded reason codes.
"""

from __future__ import annotations

import os

import pytest
from fastapi import HTTPException

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.fixture
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from mcoi_runtime.app.server import app

    return TestClient(app)


def test_tool_permission_routes_register_list_and_evaluate(client) -> None:
    payload = _permission_payload("route-allow")

    create_response = client.post("/api/v1/tool-permissions", json=payload)
    list_response = client.get("/api/v1/tool-permissions", params={"tenant_id": payload["tenant_id"]})
    evaluate_response = client.post("/api/v1/tool-permissions/evaluate", json=_evaluation_payload("route-allow"))

    assert create_response.status_code == 200
    created = create_response.json()["permission"]
    listed = list_response.json()
    decision = evaluate_response.json()["decision"]
    assert created["permission_id"] == payload["permission_id"]
    assert created["schema_hash"].startswith("schema-")
    assert any(item["permission_id"] == payload["permission_id"] for item in listed["permissions"])
    assert listed["tenant_id"] == payload["tenant_id"]
    assert decision["allowed"] is True
    assert decision["reason_codes"] == ["permission_matched"]
    assert decision["grammar"] == created["grammar"]
    assert "action_proof" not in evaluate_response.json()


def test_tool_permission_routes_reject_duplicate_registration(client) -> None:
    payload = _permission_payload("route-duplicate")

    first_response = client.post("/api/v1/tool-permissions", json=payload)
    second_response = client.post("/api/v1/tool-permissions", json=payload)

    assert first_response.status_code == 200
    assert second_response.status_code == 400
    detail = second_response.json()["detail"]
    assert detail["error_code"] == "tool_permission_registration_failed"
    assert detail["governed"] is True
    assert "route-duplicate" not in str(detail)


def test_tool_permission_routes_deny_missing_permission_fail_closed(client) -> None:
    response = client.post(
        "/api/v1/tool-permissions/evaluate",
        json={
            "tenant_id": "tenant-missing-route",
            "tool_name": "send_payment",
            "arguments": {"account_id": "acct-1", "amount": 25.0},
            "budget_ref": "budget-finance",
            "audit_present": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    decision = payload["decision"]
    assert payload["governed"] is True
    assert decision["allowed"] is False
    assert decision["reason_codes"] == ["permission_not_found"]
    assert decision["permission_id"] == ""
    assert decision["argument_hash"]


def test_tool_permission_routes_reject_cross_tenant_listing() -> None:
    from mcoi_runtime.app.routers import tool_permissions

    with pytest.raises(HTTPException) as exc_info:
        tool_permissions.list_tool_permissions(_authed_request("tenant-a"), tenant_id="tenant-b")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "cross_tenant_denied"
    assert exc_info.value.detail["governed"] is True


def test_tool_permission_routes_reject_cross_tenant_evaluation() -> None:
    from mcoi_runtime.app.routers import tool_permissions

    request = tool_permissions.EvaluateToolPermissionRequest(
        tenant_id="tenant-b",
        tool_name="send_payment",
        arguments={"account_id": "acct-1", "amount": 25.0},
        budget_ref="budget-finance",
        audit_present=True,
    )

    with pytest.raises(HTTPException) as exc_info:
        tool_permissions.evaluate_tool_permission(request, _authed_request("tenant-a"))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "cross_tenant_denied"
    assert exc_info.value.detail["governed"] is True


def test_tool_permission_routes_reject_cross_tenant_registration() -> None:
    from mcoi_runtime.app.routers import tool_permissions

    request = tool_permissions.RegisterToolPermissionRequest(**_permission_payload("tenant-scope"))

    with pytest.raises(HTTPException) as exc_info:
        tool_permissions.register_tool_permission(request, _authed_request("tenant-a"), _="admin")

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail["code"] == "cross_tenant_denied"
    assert exc_info.value.detail["governed"] is True


def _schema() -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "account_id": {"type": "string"},
            "amount": {"type": "number"},
        },
        "required": ["account_id", "amount"],
        "additionalProperties": False,
    }


def _permission_payload(suffix: str) -> dict[str, object]:
    return {
        "permission_id": f"perm-{suffix}",
        "tenant_id": f"tenant-{suffix}",
        "tool_name": "send_payment",
        "argument_schema": _schema(),
        "budget_ref": "budget-finance",
        "audit_required": True,
        "description": "Permit governed payment dispatch",
    }


def _evaluation_payload(suffix: str) -> dict[str, object]:
    return {
        "tenant_id": f"tenant-{suffix}",
        "tool_name": "send_payment",
        "arguments": {"account_id": "acct-1", "amount": 25.0},
        "budget_ref": "budget-finance",
        "audit_present": True,
    }


class _State:
    def __init__(self, context: dict[str, object]) -> None:
        self.governance_context = context


class _Request:
    def __init__(self, context: dict[str, object]) -> None:
        self.state = _State(context)


def _authed_request(tenant_id: str) -> _Request:
    return _Request({"authenticated_tenant_id": tenant_id, "jwt_scopes": frozenset({"musia.admin"})})
