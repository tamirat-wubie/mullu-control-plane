"""Purpose: verify policy-version registry HTTP endpoints.

Governance scope: operator-facing registration, promotion, rollback, diff, and
shadow evaluation routes.
Dependencies: FastAPI test client and policy-version registry dependency.
Invariants: routes are governed; shadow evaluation does not promote; invalid
references fail closed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from mcoi_runtime.app.server import app

    return TestClient(app)


def _artifact_payload(version: str, *, write_action: str = "deny") -> dict:
    return {
        "policy_id": "endpoint-policy",
        "version": version,
        "rules": [
            {
                "rule_id": "write-governance",
                "description": "Govern write effects",
                "condition": "has_write_effects",
                "action": write_action,
            },
            {
                "rule_id": "read-allowance",
                "description": "Allow read-only work",
                "condition": "read_only",
                "action": "allow",
            },
        ],
    }


def _register(client: TestClient, version: str, *, write_action: str = "deny"):
    return client.post(
        "/api/v1/policies/endpoint-policy/versions",
        json=_artifact_payload(version, write_action=write_action),
    )


def test_policy_version_register_and_fetch(client: TestClient) -> None:
    response = _register(client, "v-register")
    data = response.json()
    fetch = client.get("/api/v1/policies/endpoint-policy/versions/v-register")
    fetched = fetch.json()

    assert response.status_code == 200
    assert data["governed"] is True
    assert data["artifact"]["artifact_hash"].startswith("policy-artifact-")
    assert fetch.status_code == 200
    assert fetched["artifact"]["version"] == "v-register"


def test_policy_version_promote_diff_shadow_and_rollback(client: TestClient) -> None:
    _register(client, "v-active", write_action="deny")
    _register(client, "v-shadow", write_action="escalate")

    promote_active = client.post("/api/v1/policies/endpoint-policy/versions/v-active/promote")
    promote_shadow = client.post("/api/v1/policies/endpoint-policy/versions/v-shadow/promote")
    diff = client.get("/api/v1/policies/endpoint-policy/diff?from_version=v-active&to_version=v-shadow")
    shadow = client.post(
        "/api/v1/policies/endpoint-policy/shadow/v-shadow",
        json={
            "policy_input": {
                "subject_id": "subject-http",
                "goal_id": "goal-http",
                "has_write_effects": True,
            }
        },
    )
    rollback = client.post("/api/v1/policies/endpoint-policy/rollback")

    assert promote_active.status_code == 200
    assert promote_shadow.status_code == 200
    assert diff.json()["diff"]["changed"] is True
    assert shadow.json()["result"]["active_version"] == "v-shadow"
    assert shadow.json()["result"]["shadow_version"] == "v-shadow"
    assert shadow.json()["result"]["promoted"] is False
    assert rollback.status_code == 200
    assert rollback.json()["active"]["version"] == "v-active"


def test_policy_version_routes_fail_closed(client: TestClient) -> None:
    mismatch = client.post(
        "/api/v1/policies/endpoint-policy/versions",
        json={**_artifact_payload("v-mismatch"), "policy_id": "other-policy"},
    )
    missing_promote = client.post("/api/v1/policies/endpoint-policy/versions/missing/promote")
    missing_fetch = client.get("/api/v1/policies/endpoint-policy/versions/missing")

    assert mismatch.status_code == 400
    assert mismatch.json()["detail"]["error_code"] == "policy_id_mismatch"
    assert missing_promote.status_code == 400
    assert missing_promote.json()["detail"]["error_code"] == "policy_version_promotion_failed"
    assert missing_fetch.status_code == 404
    assert missing_fetch.json()["detail"]["governed"] is True
