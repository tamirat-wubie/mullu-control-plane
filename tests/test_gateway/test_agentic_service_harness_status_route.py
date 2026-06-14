"""Tests for the Agentic Service Harness read-only status route.

Purpose: verify the gateway exposes the harness status projection as a
read-only route without mutation, external adapter, secret, or high-risk
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: gateway.agentic_service_harness_status and gateway.server.
Invariants:
  - GET /api/v1/harness/status returns a bounded read-model projection.
  - POST on the harness status path is not admitted.
  - Unsafe source data fails closed without echoing secret-like values.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from fastapi.testclient import TestClient

from gateway.agentic_service_harness_status import (
    AgenticServiceHarnessReadModelSource,
    DEFAULT_READ_MODEL_PATH,
    PRODUCER_REHEARSAL_BLOCKER,
    ROUTE_IMPLEMENTATION_BLOCKER,
    RUNTIME_SOURCE_BLOCKER,
    build_agentic_service_harness_status_projection,
)
from gateway.agentic_service_harness_read_model_producer import (
    AgenticServiceHarnessRuntimeReadModelProducer,
)
from gateway.agentic_service_harness_live_task_run_producer import REHEARSAL_REPORT_ID
from gateway.server import create_gateway_app


class StubPlatform:
    """Minimal governed platform fixture for gateway app construction."""

    def connect(self, *, identity_id: str, tenant_id: str):
        return StubSession()


class StubSession:
    """Minimal governed session fixture."""

    def llm(self, prompt: str, **kwargs):  # noqa: ANN001
        return type("Result", (), {"content": "ok", "succeeded": True, "error": "", "cost": 0.0})()

    def close(self) -> None:
        return None


def test_harness_status_projection_accepts_default_fixture() -> None:
    payload = build_agentic_service_harness_status_projection()

    assert payload["route_id"] == "agentic_service_harness_status_read_model"
    assert payload["route_version"] == 1
    assert payload["read_only"] is True
    assert payload["status"] == "AwaitingEvidence"
    assert ROUTE_IMPLEMENTATION_BLOCKER not in payload["blockers"]
    assert payload["blockers"] == ["runtime_read_model_source_pending"]
    assert payload["permission_snapshot"]["can_deploy"] is False
    assert payload["producer_rehearsal"]["report_id"] == REHEARSAL_REPORT_ID
    assert payload["producer_rehearsal"]["producer_state"] == "local_dry_run_ready"
    assert payload["producer_rehearsal"]["read_only"] is True
    assert payload["producer_rehearsal"]["live_producer_implemented"] is False
    assert any(
        validator["validator_id"] == "agentic-service-harness-read-only-status-route"
        for validator in payload["validators"]
    )


def test_harness_status_gateway_route_is_read_only() -> None:
    client = TestClient(create_gateway_app(platform=StubPlatform()))

    response = client.get("/api/v1/harness/status")
    post_response = client.post("/api/v1/harness/status", json={"action": "mutate"})
    payload = response.json()

    assert response.status_code == 200
    assert post_response.status_code == 405
    assert payload["route_id"] == "agentic_service_harness_status_read_model"
    assert payload["status"] == "SolvedVerified"
    assert payload["blockers"] == []
    assert payload["read_only"] is True
    assert payload["report_is_not_terminal_closure"] is True
    assert payload["terminal_closure_required"] is True
    assert payload["permission_snapshot"]["can_merge"] is False
    assert payload["permission_snapshot"]["can_mutate_secrets"] is False
    assert payload["producer_rehearsal"]["local_rehearsal_only"] is True
    assert payload["producer_rehearsal"]["effect_boundary"]["external_adapter_integrated"] is False


def test_harness_status_gateway_route_reads_runtime_source() -> None:
    app = create_gateway_app(platform=StubPlatform())
    client = TestClient(app)
    runtime_source = _runtime_ready_source()
    app.state.agentic_service_harness_read_model_source.replace_runtime_read_model(runtime_source)

    response = client.get("/api/v1/harness/status")
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "SolvedVerified"
    assert payload["blockers"] == []
    assert payload["next_action"] == "Runtime read-model source is bound; keep route read-only."
    assert payload["read_only"] is True
    assert payload["permission_snapshot"]["can_deploy"] is False


def test_harness_status_runtime_source_clear_restores_foundation_fallback() -> None:
    source = AgenticServiceHarnessReadModelSource()
    source.replace_runtime_read_model(_runtime_ready_source())
    ready_payload = build_agentic_service_harness_status_projection(read_model_source=source)

    source.clear_runtime_read_model()
    fallback_payload = build_agentic_service_harness_status_projection(read_model_source=source)

    assert ready_payload["status"] == "SolvedVerified"
    assert fallback_payload["status"] == "AwaitingEvidence"
    assert fallback_payload["blockers"] == [RUNTIME_SOURCE_BLOCKER]
    assert fallback_payload["read_only"] is True


def test_harness_status_runtime_producer_feeds_source_after_override_clear() -> None:
    source = AgenticServiceHarnessReadModelSource(
        runtime_producer=AgenticServiceHarnessRuntimeReadModelProducer()
    )
    source.replace_runtime_read_model(_runtime_ready_source())
    override_payload = build_agentic_service_harness_status_projection(read_model_source=source)

    source.clear_runtime_read_model()
    producer_payload = build_agentic_service_harness_status_projection(read_model_source=source)

    assert override_payload["status"] == "SolvedVerified"
    assert producer_payload["status"] == "SolvedVerified"
    assert producer_payload["blockers"] == []
    assert producer_payload["tenant_id"] == "tenant.foundation"
    assert producer_payload["project_id"] == "project.foundation"
    assert producer_payload["next_action"] == "Runtime read-model producer is bound; keep route read-only."
    assert producer_payload["permission_snapshot"]["can_run_destructive_operations"] is False
    assert producer_payload["producer_rehearsal"]["producer_state"] == "local_dry_run_ready"
    assert producer_payload["producer_rehearsal"]["network_policy"] == "none"


def test_harness_status_blocks_unsafe_producer_rehearsal_without_echo() -> None:
    unsafe_rehearsal = {
        "report_id": REHEARSAL_REPORT_ID,
        "producer_state": "local_dry_run_ready",
        "planning_only": True,
        "local_rehearsal_only": True,
        "live_producer_implemented": False,
        "report_is_not_terminal_closure": True,
        "terminal_closure": False,
        "effect_boundary": {
            "ui_created": False,
            "mutation_endpoints_admitted": False,
            "external_adapter_integrated": True,
            "branch_write_enabled": False,
            "pull_request_creation_enabled": False,
            "deployment_enabled": False,
            "dns_mutation_enabled": False,
            "secret_mutation_enabled": False,
            "destructive_operation_enabled": False,
            "runtime_state_written": False,
            "network_policy": "none",
        },
        "access_token": "ghp_forbiddencredential",
    }

    payload = build_agentic_service_harness_status_projection(
        read_model_source=_runtime_ready_source(),
        producer_rehearsal_source=unsafe_rehearsal,
    )
    serialized_payload = json.dumps(payload, sort_keys=True)

    assert payload["status"] == "GovernanceBlocked"
    assert "local_producer_rehearsal_unsafe" in payload["blockers"]
    assert "secret_value_serialization_not_allowed" in payload["blockers"]
    assert payload["producer_rehearsal"]["producer_state"] == "GovernanceBlocked"
    assert payload["producer_rehearsal"]["live_producer_implemented"] is False
    assert "ghp_forbiddencredential" not in serialized_payload
    assert "access_token" not in serialized_payload


def test_harness_status_reports_missing_producer_rehearsal() -> None:
    class MissingProducerRehearsal:
        def produce(self):
            return None

    payload = build_agentic_service_harness_status_projection(
        read_model_source=_runtime_ready_source(),
        producer_rehearsal_source=MissingProducerRehearsal(),
    )

    assert payload["status"] == "AwaitingEvidence"
    assert payload["blockers"] == [PRODUCER_REHEARSAL_BLOCKER]
    assert payload["producer_rehearsal"]["read_only"] is True
    assert payload["producer_rehearsal"]["terminal_closure"] is False


def test_harness_status_missing_source_returns_awaiting_evidence(tmp_path: Path) -> None:
    payload = build_agentic_service_harness_status_projection(tmp_path / "missing.json")

    assert payload["status"] == "AwaitingEvidence"
    assert payload["blockers"] == ["missing_read_model_source"]
    assert payload["accounts"] == []
    assert payload["permission_snapshot"] == {}
    assert payload["read_only"] is True


def test_harness_status_blocks_high_risk_authority(tmp_path: Path) -> None:
    source = _default_source()
    source["permission_snapshot"]["can_deploy"] = True
    source_path = _write_source(tmp_path, source)

    payload = build_agentic_service_harness_status_projection(source_path)

    assert payload["status"] == "GovernanceBlocked"
    assert "high_risk_authority_not_allowed" in payload["blockers"]
    assert payload["runs"] == []
    assert payload["permission_snapshot"] == {}
    assert payload["read_only"] is True


def test_harness_status_blocks_secret_like_payload_without_echo(tmp_path: Path) -> None:
    source = _default_source()
    source["accounts"][0]["access_token"] = "ghp_forbiddencredential"
    source_path = _write_source(tmp_path, source)

    payload = build_agentic_service_harness_status_projection(source_path)
    serialized_payload = json.dumps(payload, sort_keys=True)

    assert payload["status"] == "GovernanceBlocked"
    assert "secret_value_serialization_not_allowed" in payload["blockers"]
    assert payload["accounts"] == []
    assert "ghp_forbiddencredential" not in serialized_payload
    assert "access_token" not in serialized_payload


def test_harness_status_blocks_terminal_closure_claim(tmp_path: Path) -> None:
    source = _default_source()
    source["result_summaries"][0]["terminal_closure"] = True
    source_path = _write_source(tmp_path, source)

    payload = build_agentic_service_harness_status_projection(source_path)

    assert payload["status"] == "GovernanceBlocked"
    assert "terminal_closure_claim_not_allowed" in payload["blockers"]
    assert payload["result_summaries"] == []
    assert payload["report_is_not_terminal_closure"] is True


def _default_source() -> dict[str, object]:
    return deepcopy(json.loads(DEFAULT_READ_MODEL_PATH.read_text(encoding="utf-8")))


def _runtime_ready_source() -> dict[str, object]:
    source = _default_source()
    source["result_summaries"][0]["blockers"] = []
    source["result_summaries"][0]["outcome"] = "AwaitingEvidence"
    source["result_summaries"][0]["user_visible_status"] = (
        "Read-only runtime source is bound for the static harness status route."
    )
    source["result_summaries"][0]["next_action"] = "Runtime read-model source is bound; keep route read-only."
    source["next_action"] = "Runtime read-model source is bound; keep route read-only."
    return source


def _write_source(tmp_path: Path, source: dict[str, object]) -> Path:
    source_path = tmp_path / "agentic_service_harness_read_models.foundation.json"
    source_path.write_text(json.dumps(source, sort_keys=True), encoding="utf-8")
    return source_path
