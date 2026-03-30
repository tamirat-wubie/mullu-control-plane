"""Purpose: verify compliance proof export endpoints.
Governance scope: compliance export tests only.
Dependencies: FastAPI test client, server app.
Invariants: packages are self-contained, hashed, and governed.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    return TestClient(app)


def _seed_audit(client: TestClient) -> None:
    """Create some audit entries via the adapter protocol."""
    reg = client.post("/api/v1/agent/register", json={
        "agent_name": "compliance-test-agent",
        "capabilities": ["analyze"],
    }).json()
    client.post("/api/v1/agent/action-request", json={
        "agent_id": reg["agent_id"],
        "action_type": "analyze",
        "target": "dataset",
        "tenant_id": "compliance-tenant",
    })


# --- Audit Package ---


def test_audit_package_export(client: TestClient) -> None:
    _seed_audit(client)
    resp = client.post("/api/v1/compliance/audit-package", json={
        "limit": 100,
        "include_chain_verification": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["package_type"] == "audit"
    assert data["governed"] is True
    assert "package_hash" in data
    assert "generated_at" in data
    assert "entry_count" in data
    assert "actions_summary" in data
    assert "outcomes_summary" in data
    assert isinstance(data["entries"], list)


def test_audit_package_has_chain_verification(client: TestClient) -> None:
    resp = client.post("/api/v1/compliance/audit-package", json={
        "include_chain_verification": True,
    })
    data = resp.json()
    assert "chain_verification" in data


# --- Incident Package ---


def test_incident_package_export(client: TestClient) -> None:
    resp = client.post("/api/v1/compliance/incident-package", json={
        "limit": 100,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["package_type"] == "incident"
    assert data["governed"] is True
    assert "package_hash" in data
    assert "incident_count" in data
    assert "blocked_count" in data
    assert "error_count" in data


# --- Compliance Mapping ---


def test_compliance_mapping_export(client: TestClient) -> None:
    _seed_audit(client)
    resp = client.post("/api/v1/compliance/mapping", json={
        "framework": "generic",
        "limit": 100,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["package_type"] == "compliance_mapping"
    assert data["framework"] == "generic"
    assert data["governed"] is True
    assert "controls" in data
    for control in ("access_control", "audit_logging", "policy_enforcement"):
        assert control in data["controls"]


# --- Summary ---


def test_compliance_summary(client: TestClient) -> None:
    resp = client.get("/api/v1/compliance/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "total_audit_entries" in data
    assert "chain_intact" in data
    assert "available_exports" in data
    assert "audit_package" in data["available_exports"]
    assert "supported_frameworks" in data


# --- Export is self-audited ---


def test_export_appears_in_audit_trail(client: TestClient) -> None:
    client.post("/api/v1/compliance/audit-package", json={"limit": 10})
    resp = client.get("/api/v1/audit?action=compliance.export.audit_package&limit=5")
    assert resp.status_code == 200
    assert resp.json().get("count", 0) >= 1
