"""Purpose: bind operational health read-model witnesses to exact test anchors.
Governance scope: health, readiness, monitoring, release, and snapshot read models.
Dependencies: FastAPI app server and health aggregation cores.
Invariants:
  - Health surfaces expose bounded read models only.
  - Scores remain in bounded ranges.
  - Exception details are sanitized.
  - Readiness, monitoring, release, and snapshot routes return governed summaries.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest

try:
    from fastapi.testclient import TestClient

    FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency guard
    FASTAPI_AVAILABLE = False


@pytest.fixture
def client() -> Iterator[TestClient]:
    if not FASTAPI_AVAILABLE:
        pytest.skip("FastAPI not installed")
    os.environ["MULLU_ENV"] = "local_dev"
    os.environ["MULLU_DB_BACKEND"] = "memory"
    os.environ["MULLU_CERT_INTERVAL"] = "0"
    from mcoi_runtime.app.server import app

    yield TestClient(app)


def test_deep_health_components_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/health/deep")
    payload = response.json()

    assert response.status_code == 200
    assert payload["overall"] in {"healthy", "degraded", "unhealthy"}
    assert len(payload["components"]) >= 3
    assert all(set(component) <= {"name", "status", "latency_ms", "detail"} for component in payload["components"])


def test_health_score_range_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/health/score")
    payload = response.json()

    assert response.status_code == 200
    assert 0.0 <= payload["score"] <= 1.0
    assert payload["status"] in {"healthy", "degraded", "unhealthy"}
    assert payload["checked_at"]


def test_health_score_components_weighted(client: TestClient) -> None:
    response = client.get("/api/v1/health/score")
    components = response.json()["components"]

    assert response.status_code == 200
    assert len(components) >= 3
    assert all(component["weight"] > 0 for component in components)
    assert all(0.0 <= component["score"] <= 1.0 for component in components)


def test_health_v2_degraded_state_supported() -> None:
    from mcoi_runtime.core.health_check_agg import HealthCheckAggregator, HealthCheckDef, HealthStatus

    aggregator = HealthCheckAggregator()
    aggregator.register(HealthCheckDef("healthy", lambda: {"status": "healthy"}, weight=1.0))
    aggregator.register(HealthCheckDef("slow", lambda: {"status": "degraded"}, weight=1.0))
    result = aggregator.run()

    assert result.status == HealthStatus.DEGRADED
    assert result.score == 75.0
    assert result.is_healthy is False


def test_health_v2_exception_sanitized() -> None:
    from mcoi_runtime.core.health_check_agg import HealthCheckAggregator, HealthCheckDef, HealthStatus

    def failing_check() -> dict[str, str]:
        raise RuntimeError("internal-health-secret")

    aggregator = HealthCheckAggregator()
    aggregator.register(HealthCheckDef("broken", failing_check, weight=1.0))
    result = aggregator.run()

    assert result.status == HealthStatus.UNHEALTHY
    assert result.checks[0].message == "health check error (RuntimeError)"
    assert "internal-health-secret" not in result.checks[0].message


def test_health_v3_weighted_aggregation() -> None:
    from mcoi_runtime.core.health_v3 import ComponentHealth, HealthAggregatorV3

    aggregator = HealthAggregatorV3()
    aggregator.register("critical", lambda: ComponentHealth.HEALTHY, weight=10.0)
    aggregator.register("optional", lambda: ComponentHealth.UNHEALTHY, weight=1.0)
    result = aggregator.check_all()

    assert result["status"] == "healthy"
    assert result["overall_score"] > 0.9
    assert result["components"][0]["weight"] == 10.0


def test_health_v3_recovery_tracking() -> None:
    from mcoi_runtime.core.health_v3 import ComponentHealth, HealthAggregatorV3

    aggregator = HealthAggregatorV3(recovery_threshold=3)
    aggregator.register("db", lambda: ComponentHealth.HEALTHY)
    result = {}
    for _ in range(3):
        result = aggregator.check_all()

    assert result["components"][0]["recovered"] is True
    assert result["components"][0]["consecutive_healthy"] == 3
    assert result["status"] == "healthy"


def test_health_routes_return_read_models(client: TestClient) -> None:
    paths = (
        "/api/v1/health/deep",
        "/api/v1/health/score",
        "/api/v1/health/extensions",
        "/api/v1/health/v2",
        "/api/v1/health/v3",
    )

    responses = [client.get(path) for path in paths]

    assert [response.status_code for response in responses] == [200, 200, 200, 200, 200]
    assert all(isinstance(response.json(), dict) for response in responses)
    assert all("action_proof" not in response.json() for response in responses)


def test_extension_health_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/health/extensions")
    payload = response.json()
    extensions = payload["extensions"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert set(extensions) == {
        "governed_swarm",
        "nested_mind",
        "nested_mind_observation_bridge",
        "nested_mind_observation_submitter",
        "note_memory",
        "tool_permission_registry",
    }
    assert set(extensions["governed_swarm"]) == {
        "registered",
        "enabled",
        "mounted",
        "state",
        "reason",
        "audit_store_configured",
    }
    assert set(extensions["note_memory"]) == {
        "registered",
        "enabled",
        "mounted",
        "state",
        "reason",
        "store_configured",
    }
    assert set(extensions["nested_mind"]) == {
        "registered",
        "enabled",
        "active",
        "state",
        "base_url_configured",
        "credential_configured",
    }
    assert set(extensions["nested_mind_observation_bridge"]) == {
        "registered",
        "enabled",
        "active",
        "state",
        "planner_configured",
    }
    assert set(extensions["nested_mind_observation_submitter"]) == {
        "registered",
        "enabled",
        "active",
        "state",
        "base_url_configured",
        "credential_configured",
    }
    assert set(extensions["tool_permission_registry"]) == {
        "registered",
        "persistent",
        "state",
        "path_configured",
    }
    assert extensions["governed_swarm"]["state"] in {
        "unregistered",
        "disabled",
        "enabled_unmounted",
        "mounted",
    }
    assert extensions["note_memory"]["state"] in {
        "unregistered",
        "disabled",
        "enabled_unmounted",
        "mounted",
    }
    assert extensions["nested_mind"]["state"] in {
        "unregistered",
        "disabled",
        "enabled_inactive",
        "standby",
        "active",
    }
    assert extensions["nested_mind_observation_bridge"]["state"] in {
        "unregistered",
        "disabled",
        "enabled_inactive",
        "standby",
        "active",
    }
    assert extensions["nested_mind_observation_submitter"]["state"] in {
        "unregistered",
        "disabled",
        "enabled_inactive",
        "standby",
        "active",
    }
    assert extensions["tool_permission_registry"]["state"] in {
        "unregistered",
        "memory",
        "persistent",
    }
    assert isinstance(extensions["governed_swarm"]["audit_store_configured"], bool)
    assert isinstance(extensions["note_memory"]["store_configured"], bool)
    assert isinstance(extensions["nested_mind"]["base_url_configured"], bool)
    assert isinstance(extensions["nested_mind"]["credential_configured"], bool)
    assert isinstance(extensions["nested_mind_observation_bridge"]["planner_configured"], bool)
    assert isinstance(extensions["nested_mind_observation_submitter"]["base_url_configured"], bool)
    assert isinstance(extensions["nested_mind_observation_submitter"]["credential_configured"], bool)
    assert isinstance(extensions["tool_permission_registry"]["persistent"], bool)
    assert isinstance(extensions["tool_permission_registry"]["path_configured"], bool)
    assert "audit_store_path" not in extensions["governed_swarm"]
    assert "store_path" not in extensions["note_memory"]
    assert "path" not in extensions["tool_permission_registry"]
    assert "base_url" not in extensions["nested_mind"]
    assert "token" not in extensions["nested_mind"]
    assert "base_url" not in extensions["nested_mind_observation_submitter"]
    assert "token" not in extensions["nested_mind_observation_submitter"]


def test_ops_dashboard_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard")
    payload = response.json()

    assert response.status_code == 200
    assert "health" in payload
    assert "source_count" in payload
    assert "captured_at" in payload


def test_production_readiness_checks_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/readiness")
    payload = response.json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert isinstance(payload["ready"], bool)
    assert payload["subsystems"] == len(payload["checks"])


def test_spatial_map_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/spatial-map")
    payload = response.json()
    spatial_map = payload["spatial_map"]
    judgments = {judgment["path_id"]: judgment for judgment in spatial_map["judgments"]}

    assert response.status_code == 200
    assert payload["governed"] is True
    assert spatial_map["frame"].startswith("gateway_architecture_space")
    assert len(spatial_map["entities"]) >= 10
    assert len(spatial_map["regions"]) >= 8
    assert {boundary["id"] for boundary in spatial_map["boundaries"]} >= {
        "cors",
        "readiness",
        "security_headers",
        "idempotency",
        "request_dedup",
        "finance_approval",
        "payment_provider",
        "observability",
        "support",
        "secrets",
    }
    assert judgments["dashboard_health_check"]["status"] == "allowed"
    assert judgments["bounded_exception_response"]["status"] == "allowed"
    assert judgments["bounded_exception_response"]["witness"][-1] == "path_valid"
    assert judgments["idempotency_suppression_path"]["status"] == "allowed"
    assert judgments["idempotency_suppression_path"]["witness"][-1] == "path_valid"
    assert judgments["request_deduplication_path"]["status"] == "allowed"
    assert judgments["request_deduplication_path"]["witness"][-1] == "path_valid"
    assert judgments["readiness_launch_gate"]["status"] == "unknown"
    assert judgments["finance_approval_path"]["status"] == "unknown"
    assert judgments["payment_provider_handoff_path"]["status"] == "unknown"
    assert judgments["observability_evidence_path"]["status"] == "unknown"
    assert judgments["support_escalation_path"]["status"] == "unknown"
    assert "evidence_required:finance_approval" in judgments["finance_approval_path"]["reasons"]
    assert "evidence_required:payment_provider" in judgments["payment_provider_handoff_path"]["reasons"]
    assert "evidence_required:observability" in judgments["observability_evidence_path"]["reasons"]
    assert "evidence_required:support" in judgments["support_escalation_path"]["reasons"]
    assert judgments["source_to_secret"]["status"] == "blocked"
    assert "blocked_boundary:secrets" in judgments["source_to_secret"]["reasons"]
    assert any(blocker.startswith("path:source_to_secret:") for blocker in spatial_map["blockers"])
    assert "bounded_exception_response_crosses_security_header_boundary" in spatial_map["witness"]
    assert "idempotency_boundary_preserves_duplicate_suppression_before_side_effects" in spatial_map["witness"]
    assert "request_dedup_boundary_preserves_tenant_scoped_replay_suppression" in spatial_map["witness"]
    assert "finance_and_payment_paths_require_approval_and_provider_evidence" in spatial_map["witness"]
    assert "operational_launch_boundaries_require_observability_and_support_evidence" in spatial_map["witness"]
    assert "secret_boundary_blocks_source_to_secret_path" in spatial_map["witness"]


def test_spatial_path_missing_boundary_blocks_explicitly() -> None:
    from mcoi_runtime.core.spatial_governance import SpatialPath, SpatialStatus, judge_path

    judgment = judge_path(
        SpatialPath("missing_boundary_path", "source", "target", ("undeclared",)),
        {},
    )

    assert judgment.status == SpatialStatus.BLOCKED
    assert judgment.reasons == ("dependency_missing:undeclared",)
    assert judgment.witness == (
        "path:missing_boundary_path",
        "source:source",
        "target:target",
        "missing_boundary:undeclared",
    )


def test_monitoring_vitals_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/monitor")
    payload = response.json()

    assert response.status_code == 200
    assert 0.0 <= payload["health_score"] <= 1.0
    assert payload["error_rate_pct"] >= 0.0
    assert payload["uptime_seconds"] >= 0.0


def test_shutdown_info_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/shutdown/info")
    payload = response.json()

    assert response.status_code == 200
    assert payload["hooks"] == len(payload["hook_names"])
    assert isinstance(payload["shutdown_started"], bool)
    assert isinstance(payload["shutdown_complete"], bool)
    assert (not payload["shutdown_complete"]) or payload["shutdown_started"]


def test_correlation_summary_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/correlation/active")
    payload = response.json()

    assert response.status_code == 200
    assert payload["active"] >= 0
    assert payload["completed"] >= 0
    assert set(payload) <= {"active", "completed", "contexts"}


def test_idempotency_summary_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/idempotency/summary")
    payload = response.json()
    summary = payload["idempotency"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert 0.0 <= summary["hit_rate"] <= 1.0
    assert summary["cached_entries"] <= summary["max_entries"]


def test_request_dedup_summary_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/dedup/summary")
    payload = response.json()
    summary = payload["dedup"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert 0.0 <= summary["duplicate_rate"] <= 1.0
    assert summary["tracked_entries"] <= summary["total_checked"]
    assert summary["tenants_tracked"] >= 0


def test_deployment_readiness_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/deploy/readiness")
    payload = response.json()
    readiness = payload["readiness"]

    assert response.status_code == 200
    assert payload["governed"] is True
    assert readiness["passed"] + readiness["failed"] + readiness["warned"] == len(readiness["checks"])
    assert isinstance(readiness["ready"], bool)


def test_release_info_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/release/latest")
    payload = response.json()

    assert response.status_code == 200
    assert payload["governed"] is True
    assert payload["version"]
    assert payload["endpoints"] > 0


def test_system_snapshot_read_model_bounded(client: TestClient) -> None:
    response = client.get("/api/v1/snapshot")
    payload = response.json()

    assert response.status_code == 200
    assert payload["environment"] == "local_dev"
    assert "audit" in payload
    assert "certification" in payload
