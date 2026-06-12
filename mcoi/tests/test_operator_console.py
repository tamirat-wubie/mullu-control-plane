"""Purpose: verify operator console dashboard endpoints.
Governance scope: console view tests only.
Dependencies: FastAPI test client, server app.
Invariants: all views return governed responses with structured data.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _console_working_note(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "kind": "WorkingNote",
        "scope": "task",
        "content_summary": "operator console parser note",
        "source_ref": "test:operator-console",
        "proof_state": "Pass",
        "trust_zone": "workspace",
        "expires_at": "2999-01-01T00:00:00+00:00",
        "evidence_refs": ["test_operator_console"],
    }
    value.update(overrides)
    return value


@pytest.fixture
def client():
    from mcoi_runtime.app.server import app
    return TestClient(app)


def test_console_home(client: TestClient) -> None:
    resp = client.get("/api/v1/console/home")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "active_runs" in data
    assert "blocked_runs" in data
    assert "failed_runs" in data
    assert "llm_invocations" in data
    assert "health_score" in data
    assert "scheduler" in data


def test_console_runs(client: TestClient) -> None:
    resp = client.get("/api/v1/console/runs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "runs" in data
    assert "count" in data
    assert isinstance(data["runs"], list)


def test_console_runs_filtered(client: TestClient) -> None:
    resp = client.get("/api/v1/console/runs?outcome=success&limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert data["filters"]["outcome"] == "success"


@pytest.mark.parametrize(
    ("path", "limit"),
    [
        ("/api/v1/console/runs", "0"),
        ("/api/v1/console/runs", "501"),
        ("/api/v1/console/runs", "1.5"),
        ("/api/v1/console/audit", "-1"),
        ("/api/v1/console/audit", "999999"),
        ("/api/v1/console/audit", "not-a-limit"),
    ],
)
def test_console_audit_read_limits_reject_invalid_values(
    client: TestClient,
    path: str,
    limit: str,
) -> None:
    resp = client.get(path, params={"limit": limit})
    body = resp.json()

    assert resp.status_code == 422
    assert body["detail"]["error"] == "invalid_limit"
    assert "limit" in body["detail"]["message"]


def test_console_audit(client: TestClient) -> None:
    resp = client.get("/api/v1/console/audit?limit=20")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "entries" in data
    assert "aggregations" in data
    assert "by_action" in data["aggregations"]
    assert "by_outcome" in data["aggregations"]
    assert "by_actor" in data["aggregations"]
    assert "chain_intact" in data


def test_console_checkpoints(client: TestClient) -> None:
    resp = client.get("/api/v1/console/checkpoints")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "engine_state" in data
    assert "persisted_checkpoints" in data
    assert "checkpoint_count" in data


def test_console_providers(client: TestClient) -> None:
    resp = client.get("/api/v1/console/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "providers" in data
    assert "circuit_breaker" in data["providers"]
    assert "tenant_count" in data


def test_console_scheduler(client: TestClient) -> None:
    resp = client.get("/api/v1/console/scheduler")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "summary" in data
    assert "jobs" in data
    assert "recent_executions" in data


def test_console_note_memory_disabled(client: TestClient) -> None:
    resp = client.get("/api/v1/console/note-memory")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert data["status"] in {"disabled", "unregistered"}
    assert data["summary"]["event_count"] == 0
    assert data["summary"]["episode_capsule_count"] == 0
    assert data["summary"]["index_proof_state"] == "Unknown"
    assert data["summary"]["retrieval_filter_active"] is False
    assert data["summary"]["retrieval_filter_mode"] == "unfiltered"
    assert data["summary"]["retrieval_influence_count"] == 0
    assert data["summary"]["retrieval_influence_total_count"] == 0
    assert data["summary"]["retrieval_influence_filtered_out_count"] == 0
    assert data["summary"]["retrieval_receipt_count"] == 0
    assert data["summary"]["retrieval_receipt_total_count"] == 0
    assert data["summary"]["retrieval_receipt_filtered_out_count"] == 0
    assert data["filters"]["retrieval_receipt_ref"] == ""
    assert data["filters"]["retrieval_citing_note_ref"] == ""
    assert data["recent_notes"] == []
    assert data["retrieval_receipts"] == []
    assert data["retrieval_influence"] == []


def test_console_note_memory_html_disabled(client: TestClient) -> None:
    resp = client.get("/api/v1/console/note-memory/view")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Mullu Note Memory Console" in resp.text
    assert "json read model" in resp.text
    assert "Events" in resp.text
    assert "Episode Capsules" in resp.text
    assert "No records" in resp.text


def test_console_note_memory_enabled_read_model(client: TestClient, tmp_path) -> None:
    from mcoi_runtime.app.note_memory_integration import NoteMemoryBootstrap
    from mcoi_runtime.app.routers.deps import deps
    from mcoi_runtime.core.note_memory_api import NoteMemoryRuntime

    previous_bootstrap = deps.get("note_memory_bootstrap")
    note_store = tmp_path / "notes"
    runtime = NoteMemoryRuntime.from_path(note_store)
    captured = runtime.capture_note(_console_working_note()).to_dict()
    source_note_id = captured["payload"]["event"]["note_id"]
    retrieved = runtime.retrieve_notes({"query": "parser", "scope": "task"}).to_dict()
    decision = runtime.capture_note(
        _console_working_note(
            kind="DecisionRecord",
            content_summary="operator console decision cites retrieval receipt",
            source_ref="test:operator-console-decision",
            expires_at=None,
            retrieval_receipt_refs=[retrieved["payload"]["receipt"]["receipt_id"]],
        )
    ).to_dict()
    runtime.record_rejected_delta(
        {
            "summary": "Rejected unsafe console note promotion",
            "source_ref": "test:operator-console-rejected",
            "evidence_refs": ["blocked"],
        }
    )
    runtime.queue_promotion({"note_id": source_note_id})

    deps.set(
        "note_memory_bootstrap",
        NoteMemoryBootstrap(
            enabled=True,
            mounted=True,
            store_path=str(note_store),
            reason="mounted",
        ),
    )
    try:
        resp = client.get(
            f"/api/v1/console/note-memory?limit=5&retrieval_receipt_ref={retrieved['payload']['receipt']['receipt_id']}"
            f"&retrieval_citing_note_ref={decision['payload']['event']['note_id']}"
        )
    finally:
        deps.set("note_memory_bootstrap", previous_bootstrap)

    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert data["status"] == "ready"
    assert data["extension"]["mounted"] is True
    assert data["snapshot_id"].startswith("note-memory-dashboard-")
    assert len(data["snapshot_hash"]) == 64
    assert data["summary"]["event_count"] == 3
    assert data["summary"]["active_note_count"] == 2
    assert data["summary"]["episode_capsule_count"] == 0
    assert data["summary"]["pending_promotion_count"] == 1
    assert data["summary"]["rejected_delta_count"] == 1
    assert data["filters"]["retrieval_receipt_ref"] == retrieved["payload"]["receipt"]["receipt_id"]
    assert data["filters"]["retrieval_citing_note_ref"] == decision["payload"]["event"]["note_id"]
    assert data["summary"]["retrieval_filter_active"] is True
    assert data["summary"]["retrieval_filter_mode"] == "receipt_and_citing_note"
    assert data["summary"]["retrieval_influence_count"] == 1
    assert data["summary"]["retrieval_influence_total_count"] == 1
    assert data["summary"]["retrieval_influence_filtered_out_count"] == 0
    assert data["summary"]["retrieval_receipt_count"] == 1
    assert data["summary"]["retrieval_receipt_total_count"] == 1
    assert data["summary"]["retrieval_receipt_filtered_out_count"] == 0
    assert data["recent_notes"][0]["kind"] == "DecisionRecord"
    assert data["retrieval_receipts"][0]["receipt_id"] == retrieved["payload"]["receipt"]["receipt_id"]
    assert data["retrieval_influence"][0]["citing_note_id"] == decision["payload"]["event"]["note_id"]
    assert data["pending_promotions"][0]["source_note_id"] == source_note_id


def test_console_note_memory_html_enabled_escapes_rows(client: TestClient, tmp_path) -> None:
    from mcoi_runtime.app.note_memory_integration import NoteMemoryBootstrap
    from mcoi_runtime.app.routers.deps import deps
    from mcoi_runtime.core.note_memory_api import NoteMemoryRuntime

    previous_bootstrap = deps.get("note_memory_bootstrap")
    note_store = tmp_path / "notes"
    runtime = NoteMemoryRuntime.from_path(note_store)
    captured = runtime.capture_note(
        _console_working_note(content_summary="<script>alert('note')</script>")
    ).to_dict()
    source_note_id = captured["payload"]["event"]["note_id"]
    runtime.queue_promotion({"note_id": source_note_id})

    deps.set(
        "note_memory_bootstrap",
        NoteMemoryBootstrap(
            enabled=True,
            mounted=True,
            store_path=str(note_store),
            reason="mounted",
        ),
    )
    try:
        resp = client.get("/api/v1/console/note-memory/view?limit=5")
    finally:
        deps.set("note_memory_bootstrap", previous_bootstrap)

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Mullu Note Memory Console" in resp.text
    assert "Episode Capsules" in resp.text
    assert "Retrieval Receipts" in resp.text
    assert "Retrieval Influence" in resp.text
    assert "Pending Promotions" in resp.text
    assert "operator console parser note" not in resp.text
    assert "<script>alert('note')</script>" not in resp.text
    assert "&lt;script&gt;alert(&#x27;note&#x27;)&lt;/script&gt;" in resp.text
    assert source_note_id in resp.text


def test_console_note_memory_mounted_without_store_path_fails_closed(client: TestClient) -> None:
    from mcoi_runtime.app.note_memory_integration import NoteMemoryBootstrap
    from mcoi_runtime.app.routers.deps import deps

    previous_bootstrap = deps.get("note_memory_bootstrap")
    deps.set(
        "note_memory_bootstrap",
        NoteMemoryBootstrap(
            enabled=True,
            mounted=True,
            store_path="",
            reason="mounted",
        ),
    )
    try:
        resp = client.get("/api/v1/console/note-memory")
    finally:
        deps.set("note_memory_bootstrap", previous_bootstrap)

    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert data["status"] == "mounted_unconfigured"
    assert data["extension"]["mounted"] is False
    assert data["extension"]["store_configured"] is False
    assert data["summary"]["event_count"] == 0


def test_full_console(client: TestClient) -> None:
    resp = client.get("/api/v1/console")
    assert resp.status_code == 200
    data = resp.json()
    assert data["governed"] is True
    assert "home" in data
    assert "checkpoints" in data
    assert "providers" in data
    assert "scheduler" in data
    assert "note_memory" in data
    assert "spatial_map" in data
    assert data["spatial_map"]["frame"].startswith("gateway_architecture_space")
    assert data["spatial_map"]["metrics"][0]["id"] == "readiness_subsystems"
    judgments = {judgment["path_id"]: judgment for judgment in data["spatial_map"]["judgments"]}
    assert judgments["dashboard_health_check"]["status"] == "allowed"
    assert judgments["readiness_launch_gate"]["status"] == "unknown"
    assert judgments["source_to_secret"]["status"] == "blocked"
    assert "blocked_boundary:secrets" in judgments["source_to_secret"]["reasons"]


def test_console_spatial_map_panel_read_model(client: TestClient) -> None:
    resp = client.get("/api/v1/console/spatial-map")
    assert resp.status_code == 200
    data = resp.json()
    panels = {panel["title"]: panel for panel in data["panels"]}
    panel_path_ids = [
        path["path_id"]
        for panel in data["panels"]
        for path in panel["paths"]
    ]
    spatial_path_ids = [path["id"] for path in data["spatial_map"]["paths"]]

    assert data["governed"] is True
    assert data["summary"]["allowed_paths"] >= 2
    assert data["summary"]["unknown_paths"] >= 1
    assert data["summary"]["blocked_paths"] == 1
    assert data["summary"]["blocker_count"] >= 1
    assert data["summary"]["panel_path_count"] == len(panel_path_ids)
    assert sorted(panel_path_ids) == sorted(spatial_path_ids)
    assert len(panel_path_ids) == len(set(panel_path_ids))
    assert "Runtime Path Panel" in panels
    assert "Launch Boundary Panel" in panels
    assert "Fracture Panel" in panels
    assert panels["Runtime Path Panel"]["paths"][0]["path_id"] == "dashboard_health_check"
    assert panels["Runtime Path Panel"]["paths"][0]["status"] == "allowed"
    assert {path["path_id"] for path in panels["Runtime Path Panel"]["paths"]} >= {
        "bounded_exception_response",
        "cache_lookup_path",
        "idempotency_suppression_path",
        "request_deduplication_path",
        "rate_limit_guard_path",
        "backpressure_status_path",
    }
    assert panels["Launch Boundary Panel"]["paths"][0]["path_id"] == "readiness_launch_gate"
    assert panels["Launch Boundary Panel"]["paths"][0]["status"] == "unknown"
    assert {path["path_id"] for path in panels["Launch Boundary Panel"]["paths"]} >= {
        "production_health_declaration_path",
        "finance_approval_path",
        "payment_provider_handoff_path",
        "observability_evidence_path",
        "support_escalation_path",
        "rollback_recovery_path",
        "proof_verification_path",
        "audit_chain_verification_path",
        "runtime_conformance_path",
    }
    assert panels["Fracture Panel"]["paths"][0]["path_id"] == "source_to_secret"
    assert panels["Fracture Panel"]["paths"][0]["status"] == "blocked"
    assert "blocked_boundary:secrets" in panels["Fracture Panel"]["paths"][0]["reasons"]


def test_console_spatial_map_html_view_renders_blockers(client: TestClient) -> None:
    resp = client.get("/api/v1/console/spatial-map/view")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Mullu Spatial Governance Console" in resp.text
    assert "Runtime Path Panel" in resp.text
    assert "Launch Boundary Panel" in resp.text
    assert "Fracture Panel" in resp.text
    assert "rate_limit_guard_path" in resp.text
    assert "backpressure_status_path" in resp.text
    assert "payment_provider_handoff_path" in resp.text
    assert "production_health_declaration_path" in resp.text
    assert "rollback_recovery_path" in resp.text
    assert "proof_verification_path" in resp.text
    assert "audit_chain_verification_path" in resp.text
    assert "runtime_conformance_path" in resp.text
    assert "observability_evidence_path" in resp.text
    assert "support_escalation_path" in resp.text
    assert "source_to_secret" in resp.text
    assert "blocked_boundary:secrets" in resp.text
    assert "<script" not in resp.text
