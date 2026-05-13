"""Purpose: verify lineage query HTTP routes.

Governance scope: FastAPI route exposure for read-only lineage resolution.
Dependencies: server dependency registry, replay recorder, TestClient.
Invariants: routes expose governed documents, invalid URIs are bounded, and
missing lineage remains explicit.
"""

from __future__ import annotations

import os

import pytest

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False


@pytest.fixture()
def client():
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    os.environ["MULLU_CERT_ENABLED"] = "true"
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.routers.deps import deps
    from mcoi_runtime.app.server import app
    from mcoi_runtime.core.artifact_lineage_dag import ArtifactLineageDAG, hash_artifact_payload

    trace_id = "lineage-http-trace"
    if deps.replay_recorder.get_trace(trace_id) is None:
        deps.replay_recorder.start_trace(trace_id)
        deps.replay_recorder.record_frame(
            trace_id,
            "request.accepted",
            {
                "tenant_id": "tenant-http",
                "policy_version": "policy:http",
                "model_version": "model:http",
                "budget_id": "budget-http",
                "command_id": "cmd-http",
            },
            {"proof_id": "proof:http", "output_id": "out-http"},
        )
        deps.replay_recorder.complete_trace(trace_id)
    artifact_lineage = ArtifactLineageDAG(clock=lambda: "2026-05-13T14:00:00+00:00")
    artifact_lineage.register_artifact(
        artifact_id="source-http",
        artifact_hash=hash_artifact_payload({"source": "http"}),
        artifact_type="json",
        tenant_id="tenant-http",
        produced_by_event_id="event-source-http",
        metadata={"policy_version": "policy:http", "budget_ref": "budget-http"},
    )
    artifact_lineage.register_artifact(
        artifact_id="summary-http",
        artifact_hash=hash_artifact_payload({"summary": "http"}),
        artifact_type="json",
        tenant_id="tenant-http",
        produced_by_event_id="event-summary-http",
        metadata={"policy_version": "policy:http", "budget_ref": "budget-http"},
    )
    artifact_lineage.add_edge(
        upstream_artifact_id="source-http",
        downstream_artifact_id="summary-http",
        reason="summarize http artifact",
    )
    deps.set("artifact_lineage", artifact_lineage)
    return TestClient(app)


def test_lineage_resolve_route_returns_trace_document(client) -> None:
    response = client.post("/api/v1/lineage/resolve", json={"uri": "lineage://trace/lineage-http-trace"})
    data = response.json()

    assert response.status_code == 200
    assert data["governed"] is True
    assert data["verified"] is True
    assert data["document_id"].startswith("lineage-doc:")
    assert data["document_hash"].startswith("sha256:")
    assert data["permalink"] == "lineage://trace/lineage-http-trace"
    assert data["nodes"][0]["tenant_id"] == "tenant-http"
    assert data["nodes"][0]["proof_id"] == "proof:http"


def test_lineage_trace_permalink_route_returns_document(client) -> None:
    response = client.get("/api/v1/lineage/lineage-http-trace?depth=3")
    data = response.json()

    assert response.status_code == 200
    assert data["root_ref"]["ref_type"] == "trace"
    assert data["root_ref"]["ref_id"] == "lineage-http-trace"
    assert data["depth"] == 3
    assert data["nodes"]


def test_lineage_output_permalink_returns_unresolved_document(client) -> None:
    response = client.get("/api/v1/lineage/output/out-missing")
    data = response.json()

    assert response.status_code == 200
    assert data["verified"] is False
    assert data["root_ref"]["ref_type"] == "output"
    assert data["nodes"][0]["unresolved"] is True
    assert data["verification"]["reason_codes"] == ["trace_not_found"]


def test_lineage_output_permalink_resolves_indexed_trace(client) -> None:
    response = client.get("/api/v1/lineage/output/out-http?depth=2")
    data = response.json()

    assert response.status_code == 200
    assert data["verified"] is True
    assert data["root_ref"]["ref_type"] == "output"
    assert data["root_ref"]["ref_id"] == "out-http"
    assert data["nodes"][0]["trace_id"] == "lineage-http-trace"


def test_lineage_command_permalink_resolves_indexed_trace(client) -> None:
    response = client.get("/api/v1/lineage/command/cmd-http?depth=1")
    data = response.json()

    assert response.status_code == 200
    assert data["verified"] is True
    assert data["root_ref"]["ref_type"] == "command"
    assert data["root_ref"]["ref_id"] == "cmd-http"
    assert len(data["nodes"]) == 1


def test_lineage_artifact_permalink_resolves_persisted_dag(client) -> None:
    response = client.get("/api/v1/lineage/artifact/summary-http?depth=5")
    data = response.json()

    assert response.status_code == 200
    assert data["verified"] is True
    assert data["root_ref"]["ref_type"] == "artifact"
    assert data["root_ref"]["ref_id"] == "summary-http"
    assert data["nodes"][0]["node_id"] == "artifact:source-http"
    assert data["nodes"][1]["parent_node_ids"] == ["artifact:source-http"]
    assert data["edges"][0]["relation"] == "depends_on"


def test_lineage_resolve_rejects_invalid_uri(client) -> None:
    response = client.post("/api/v1/lineage/resolve", json={"uri": "https://trace/lineage-http-trace"})
    data = response.json()["detail"]

    assert response.status_code == 422
    assert data["error_code"] == "invalid_lineage_uri"
    assert data["governed"] is True
