"""Purpose: verify coordination checkpoint/restore HTTP endpoints.
Governance scope: coordination HTTP endpoint integration tests only.
Dependencies: FastAPI test client, server app, coordination engine.
Invariants: checkpoint save returns governed response; restore returns status;
  audit trail records both operations.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    return TestClient(app)


def test_save_checkpoint(client: TestClient) -> None:
    resp = client.post("/api/v1/coordination/checkpoint", json={
        "checkpoint_id": "test-cp-1",
        "lease_duration_seconds": 3600,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["checkpoint_id"] == "test-cp-1"
    assert data["governed"] is True
    assert "lease_expires_at" in data


def test_restore_checkpoint(client: TestClient) -> None:
    # Save first
    client.post("/api/v1/coordination/checkpoint", json={
        "checkpoint_id": "test-cp-restore",
        "lease_duration_seconds": 3600,
    })
    # Restore
    resp = client.post("/api/v1/coordination/restore", json={
        "checkpoint_id": "test-cp-restore",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "resumed"
    assert data["governed"] is True


def test_restore_missing_checkpoint_returns_404(client: TestClient) -> None:
    resp = client.post("/api/v1/coordination/restore", json={
        "checkpoint_id": "nonexistent-cp",
    })
    assert resp.status_code == 404
    data = resp.json()
    assert data["detail"]["error_code"] == "checkpoint_not_found"


def test_checkpoint_appears_in_audit(client: TestClient) -> None:
    client.post("/api/v1/coordination/checkpoint", json={
        "checkpoint_id": "test-cp-audit",
        "lease_duration_seconds": 1800,
    })
    resp = client.get("/api/v1/audit?action=coordination.checkpoint.save&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("count", 0) >= 1


def test_restore_appears_in_audit(client: TestClient) -> None:
    client.post("/api/v1/coordination/checkpoint", json={
        "checkpoint_id": "test-cp-audit-r",
        "lease_duration_seconds": 3600,
    })
    client.post("/api/v1/coordination/restore", json={
        "checkpoint_id": "test-cp-audit-r",
    })
    resp = client.get("/api/v1/audit?action=coordination.checkpoint.restore&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("count", 0) >= 1
