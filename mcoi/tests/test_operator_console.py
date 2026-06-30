"""Purpose: verify operator console dashboard endpoints.
Governance scope: console view tests only.
Dependencies: FastAPI test client, server app.
Invariants: all views return governed responses with structured data.
"""

from __future__ import annotations

from dataclasses import replace

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


def test_console_whqr_clarifications_returns_active_job_status(client: TestClient) -> None:
    from mcoi_runtime.app.routers.deps import deps
    from mcoi_runtime.contracts.conversation import ClarificationRequest, ThreadStatus
    from mcoi_runtime.contracts.job import JobDescriptor, JobPriority, JobState, JobStatus, SlaStatus
    from mcoi_runtime.core.conversation import ConversationEngine
    from mcoi_runtime.core.job_integration import JobConversationBridge
    from mcoi_runtime.core.jobs import JobEngine

    previous_job_engine = deps.get("job_engine")
    previous_threads = deps.get("job_conversation_threads")
    job_engine = JobEngine(clock=lambda: "2026-03-18T12:00:00+00:00")
    conversation = ConversationEngine(clock=lambda: "2026-03-18T12:01:00+00:00")
    descriptor = JobDescriptor(
        job_id="job-whqr",
        name="WHQR Vendor Binding",
        description="Read-model job",
        priority=JobPriority.HIGH,
        created_at="2026-03-18T12:00:00+00:00",
    )
    thread = conversation.create_thread("WHQR Vendor Binding")
    request = ClarificationRequest(
        request_id="whqr-binding:1:vendor-node",
        thread_id=thread.thread_id,
        question="Which vendor entity reference and evidence reference bind WHQR target 'vendor'?",
        context="whqr_binding_gap target=vendor node_id=vendor-node expected_type=vendor issue_codes=missing_entity_ref,missing_evidence_ref",
        requested_from_id="operator",
        requested_at="2026-03-18T12:02:00+00:00",
    )
    waiting_thread = JobConversationBridge.persist_whqr_binding_clarification_requests(thread, (request,))
    active_thread, _response = JobConversationBridge.persist_whqr_binding_clarification_response(
        conversation,
        waiting_thread,
        request,
        "entity_ref=vendor:acme;evidence_ref=evidence:vendor-doc-1",
        "operator",
    )
    job_engine.restore_job(
        descriptor,
        JobState(
            job_id="job-whqr",
            status=JobStatus.IN_PROGRESS,
            sla_status=SlaStatus.ON_TRACK,
            thread_id=thread.thread_id,
            updated_at="2026-03-18T12:03:00+00:00",
        ),
    )
    deps.set("job_engine", job_engine)
    deps.set("job_conversation_threads", {thread.thread_id: active_thread})
    try:
        resp = client.get("/api/v1/console/whqr/clarifications")
        full = client.get("/api/v1/console")
    finally:
        deps.set("job_engine", previous_job_engine)
        deps.set("job_conversation_threads", previous_threads)

    body = resp.json()
    assert resp.status_code == 200
    assert body["governed"] is True
    assert body["summary"]["status_count"] == 1
    assert body["summary"]["ready_for_orchestration_count"] == 1
    assert body["statuses"][0]["job_id"] == "job-whqr"
    assert body["statuses"][0]["job_name"] == "WHQR Vendor Binding"
    assert body["statuses"][0]["whqr_binding"]["accepted_count"] == 1
    assert body["statuses"][0]["whqr_binding"]["next_step"] == "ready_for_orchestration"
    assert full.status_code == 200
    assert full.json()["whqr_clarifications"]["summary"]["ready_for_orchestration_count"] == 1
    assert active_thread.status == ThreadStatus.ACTIVE


def test_console_whqr_clarifications_rejects_malformed_replay_metadata(client: TestClient) -> None:
    from mcoi_runtime.app.routers.deps import deps
    from mcoi_runtime.contracts.conversation import ClarificationRequest
    from mcoi_runtime.contracts.job import JobDescriptor, JobPriority, JobState, JobStatus, SlaStatus
    from mcoi_runtime.core.conversation import ConversationEngine
    from mcoi_runtime.core.job_integration import JobConversationBridge
    from mcoi_runtime.core.jobs import JobEngine

    previous_job_engine = deps.get("job_engine")
    previous_threads = deps.get("job_conversation_threads")
    job_engine = JobEngine(clock=lambda: "2026-03-18T12:00:00+00:00")
    conversation = ConversationEngine(clock=lambda: "2026-03-18T12:01:00+00:00")
    descriptor = JobDescriptor(
        job_id="job-bad-whqr",
        name="Bad WHQR Replay",
        description="Malformed replay job",
        priority=JobPriority.NORMAL,
        created_at="2026-03-18T12:00:00+00:00",
    )
    thread = conversation.create_thread("Bad WHQR Replay")
    request = ClarificationRequest(
        request_id="whqr-binding:1:vendor-node",
        thread_id=thread.thread_id,
        question="Which vendor entity reference binds WHQR target 'vendor'?",
        context="whqr_binding_gap target=vendor node_id=vendor-node expected_type=vendor issue_codes=missing_entity_ref",
        requested_from_id="operator",
        requested_at="2026-03-18T12:02:00+00:00",
    )
    waiting_thread = JobConversationBridge.persist_whqr_binding_clarification_requests(thread, (request,))
    malformed_thread = replace(
        waiting_thread,
        messages=(replace(waiting_thread.messages[0], metadata={"whqr_binding": True}),),
    )
    job_engine.restore_job(
        descriptor,
        JobState(
            job_id="job-bad-whqr",
            status=JobStatus.IN_PROGRESS,
            sla_status=SlaStatus.ON_TRACK,
            thread_id=thread.thread_id,
            updated_at="2026-03-18T12:03:00+00:00",
        ),
    )
    deps.set("job_engine", job_engine)
    deps.set("job_conversation_threads", {thread.thread_id: malformed_thread})
    try:
        resp = client.get("/api/v1/console/whqr/clarifications")
    finally:
        deps.set("job_engine", previous_job_engine)
        deps.set("job_conversation_threads", previous_threads)

    body = resp.json()
    assert resp.status_code == 409
    assert body["detail"]["error"] == "whqr_clarification_replay_invalid"
    assert body["detail"]["thread_id"] == thread.thread_id
    assert body["detail"]["job_id"] == "job-bad-whqr"


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
    assert "whqr_clarifications" in data
    assert "spatial_map" in data
    assert "personal_assistant" in data
    assert "operator_console_first" in data
    assert data["spatial_map"]["frame"].startswith("gateway_architecture_space")
    assert data["personal_assistant"]["status"] == "foundation_read_only"
    assert data["personal_assistant"]["effect_boundary"]["execution_allowed"] is False
    assert data["operator_console_first"]["governed"] is True
    assert data["operator_console_first"]["projection_only"] is True
    assert data["operator_console_first"]["execution_authority"] is False
    assert data["operator_console_first"]["route_boundary"]["dispatch_allowed"] is False
    assert data["spatial_map"]["metrics"][0]["id"] == "readiness_subsystems"
    judgments = {judgment["path_id"]: judgment for judgment in data["spatial_map"]["judgments"]}
    assert judgments["dashboard_health_check"]["status"] == "allowed"
    assert judgments["readiness_launch_gate"]["status"] == "unknown"
    assert judgments["source_to_secret"]["status"] == "blocked"
    assert "blocked_boundary:secrets" in judgments["source_to_secret"]["reasons"]


def test_console_operator_console_first_panel_read_model(client: TestClient) -> None:
    resp = client.get("/api/v1/console/operator-console-first")
    assert resp.status_code == 200
    data = resp.json()
    panels = data["panels"]

    assert data["governed"] is True
    assert data["read_only"] is True
    assert data["projection_only"] is True
    assert data["execution_authority"] is False
    assert data["receipt_attached"] is False
    assert data["status"] == "waiting_approval"
    assert data["read_model_id"].startswith("ocf-console-read-model-")
    assert data["route_boundary"]["projection_only"] is True
    assert data["route_boundary"]["execution_allowed"] is False
    assert data["route_boundary"]["dispatch_allowed"] is False
    assert data["route_boundary"]["approval_write_allowed"] is False
    assert data["panel_keys"] == [
        "current_task",
        "state_snapshot",
        "proposed_plan",
        "risk_and_side_effects",
        "approval_lease",
        "controlled_execution_log",
        "verification_result",
        "receipt_bundle",
        "controls",
    ]
    assert panels["current_task"]["scope"]["mode"] == "foundation_read_only"
    assert panels["state_snapshot"]["present"] is True
    assert panels["proposed_plan"]["approval_needed"] is True
    assert panels["risk_and_side_effects"]["max_risk_score"] == 60
    assert panels["risk_and_side_effects"]["effect_bearing_action_count"] == 0
    assert panels["approval_lease"]["present"] is False
    assert panels["verification_result"]["present"] is False
    assert panels["receipt_bundle"]["present"] is False
    assert panels["controls"]["can_approve"] is True
    assert panels["controls"]["control_execution_authority"] is False
    assert "approval_required" in data["attention"]
    assert "approval_lease_missing" in data["attention"]
    assert "missing_state_snapshot" not in data["attention"]


def test_console_operator_console_first_html_view_renders_read_only_panel(client: TestClient) -> None:
    resp = client.get("/api/v1/console/operator-console-first/view")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Mullu Operator" in resp.text
    assert "Console First" in resp.text
    assert "json read model" in resp.text
    assert "approval_required" in resp.text
    assert "approval_lease_missing" in resp.text
    assert "Dispatch Allowed" in resp.text
    assert "False" in resp.text
    assert "ocf-foundation-plan-review" in resp.text
    assert "<script" not in resp.text


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_console_operator_console_first_route_rejects_mutation_methods(
    client: TestClient,
    method: str,
) -> None:
    resp = client.request(method.upper(), "/api/v1/console/operator-console-first", json={})

    assert resp.status_code == 405
    assert resp.json()["detail"] == "Method Not Allowed"


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_console_operator_console_first_view_rejects_mutation_methods(
    client: TestClient,
    method: str,
) -> None:
    resp = client.request(method.upper(), "/api/v1/console/operator-console-first/view", json={})

    assert resp.status_code == 405
    assert resp.json()["detail"] == "Method Not Allowed"


def test_console_personal_assistant_panel_read_model(client: TestClient) -> None:
    resp = client.get("/api/v1/console/personal-assistant")
    assert resp.status_code == 200
    data = resp.json()

    assert data["governed"] is True
    assert data["status"] == "foundation_read_only"
    assert data["effect_boundary"]["execution_allowed"] is False
    assert data["effect_boundary"]["external_send_allowed"] is False
    assert data["effect_boundary"]["nested_mind_live_activation_allowed"] is False
    assert data["sections"]["approvals"]["execution_allowed"] is False
    assert data["skills"]["skill_count"] >= 13
    assert "send_email" in data["blocked_actions"]


def test_console_personal_assistant_html_view_renders_read_only_panel(client: TestClient) -> None:
    resp = client.get("/api/v1/console/personal-assistant/view")

    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "Mullu Personal Assistant Console" in resp.text
    assert "Execution Allowed" in resp.text
    assert "Blocked Actions" in resp.text
    assert "json read model" in resp.text


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
