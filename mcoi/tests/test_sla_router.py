"""SLA router proof-surface tests.

Purpose: verify SLA read-model endpoints expose bounded governed summaries and
violation projections.
Governance scope: data-plane SLA summary and violation read-model routes.
Dependencies: FastAPI TestClient, server bootstrap, and the shared SLA monitor.
Invariants:
  - SLA summary route is governed and bounded.
  - SLA violation route preserves filter scope.
  - Violation payloads expose thresholds without mutable monitor authority.
"""

from __future__ import annotations

import os

import pytest

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    FASTAPI_AVAILABLE = False


@pytest.fixture()
def client() -> TestClient:
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from mcoi_runtime.app.server import app

    return TestClient(app)


def test_sla_summary_endpoint_returns_bounded_governed_read_model(client: TestClient) -> None:
    response = client.get("/api/v1/sla")
    payload = response.json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["sla"]["targets"] >= 2
    assert "total_violations" in payload["sla"]
    assert "compliance" in payload["sla"]


def test_sla_violations_endpoint_filters_by_sla_id(client: TestClient) -> None:
    from mcoi_runtime.app.routers.deps import deps

    deps.sla_monitor.check("latency-p99", 800.0, route="/api/v1/sla/violations")
    response = client.get("/api/v1/sla/violations", params={"sla_id": "latency-p99"})
    payload = response.json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["count"] >= 1
    assert all(item["sla_id"] == "latency-p99" for item in payload["violations"])
    assert any(item["actual"] == 800.0 and item["threshold"] == 500.0 for item in payload["violations"])
