"""Purpose: verify hosted demo sandbox read models and routes.

Governance scope: read-only sandbox traces, lineage projections, and policy
evaluation examples.
Dependencies: hosted_demo_sandbox core and FastAPI router.
Invariants: sandbox data is deterministic; endpoints do not mutate state; missing
trace lookups fail closed.
"""

from __future__ import annotations

import os

import pytest

from mcoi_runtime.core.hosted_demo_sandbox import HostedDemoSandbox

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


def test_sandbox_summary_is_deterministic() -> None:
    first = HostedDemoSandbox().summary()
    second = HostedDemoSandbox().summary()

    assert first == second
    assert first["sandbox_url"] == "https://sandbox.mullusi.com"
    assert first["read_only"] is True
    assert first["trace_count"] == 2


def test_sandbox_lineage_contains_bounded_causal_graph() -> None:
    sandbox = HostedDemoSandbox()

    document = sandbox.lineage("sandbox-trace-policy-shadow")

    assert document is not None
    assert document["verified"] is True
    assert document["verification"]["checked_nodes"] == 3
    assert document["verification"]["checked_edges"] == 2
    assert document["document_hash"].startswith("sha256:")


def test_sandbox_policy_evaluations_are_read_only() -> None:
    evaluations = HostedDemoSandbox().policy_evaluations()

    assert len(evaluations) == 2
    assert all(item["read_only"] is True for item in evaluations)
    assert {item["verdict"] for item in evaluations} == {"allow", "deny"}


@pytest.fixture()
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    from mcoi_runtime.app.server import app

    return TestClient(app)


def test_sandbox_summary_route(client) -> None:
    response = client.get("/api/v1/sandbox/summary")
    data = response.json()

    assert response.status_code == 200
    assert data["governed"] is True
    assert data["read_only"] is True
    assert data["trace_count"] >= 2


def test_sandbox_traces_route(client) -> None:
    response = client.get("/api/v1/sandbox/traces")
    data = response.json()

    assert response.status_code == 200
    assert data["count"] == len(data["traces"])
    assert data["traces"][0]["lineage_uri"].startswith("lineage://trace/")
    assert data["read_only"] is True


def test_sandbox_lineage_route(client) -> None:
    response = client.get("/api/v1/sandbox/lineage/sandbox-trace-budget-cutoff")
    data = response.json()

    assert response.status_code == 200
    assert data["root_ref"]["ref_type"] == "trace"
    assert data["root_ref"]["ref_id"] == "sandbox-trace-budget-cutoff"
    assert data["governed"] is True


def test_sandbox_missing_lineage_route_fails_closed(client) -> None:
    response = client.get("/api/v1/sandbox/lineage/missing-trace")
    data = response.json()["detail"]

    assert response.status_code == 404
    assert data["error_code"] == "sandbox_trace_not_found"
    assert data["governed"] is True


def test_sandbox_policy_evaluations_route(client) -> None:
    response = client.get("/api/v1/sandbox/policy-evaluations")
    data = response.json()

    assert response.status_code == 200
    assert data["count"] == 2
    assert data["policy_evaluations"][0]["evaluation_hash"]
    assert data["read_only"] is True
