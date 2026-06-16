"""Tests for operational dashboard runtime API and FastAPI adapter.

Purpose: verify app-facing dashboard envelopes expose the simple home summary
without granting execution authority.
Governance scope: dashboard API remains projection-only and rejects invalid
state providers.
Dependencies: operational dashboard API, FastAPI adapter, and dashboard
projection dataclasses.
Invariants: full state and home endpoints are governed, read-only, and stable.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.operational_dashboard_api import OperationalDashboardRuntime
from mcoi_runtime.core.operational_dashboard_fastapi_router import (
    OperationalDashboardFastAPIAdapter,
    create_operational_dashboard_fastapi_router,
)
from mcoi_runtime.core.operational_dashboard_intelligence import (
    DashboardSimpleActionSummary,
    DashboardSimpleHomeAction,
    DashboardSimpleHomeSummary,
    DashboardSimpleStartGuideSummary,
    DashboardSimpleWorkflowSummary,
    DashboardSdlcReceiptSummary,
    OperationalDashboardState,
    WorkflowHealth,
)


def _dashboard_state() -> OperationalDashboardState:
    return OperationalDashboardState(
        dashboard_id="dashboard-test",
        projection_id="projection-test",
        active_project_count=1,
        ready_action_ids=(),
        blocked_action_ids=(),
        open_blocker_ids=(),
        open_conflict_ids=(),
        repair_ids=(),
        stale_high_impact_claim_ids=(),
        high_intensity_box_ids=(),
        constructive_delta_ids=(),
        fracture_delta_ids=(),
        memory_confidence_trend=1.0,
        workflow_health=WorkflowHealth.READY,
        execution_readiness="no_action_candidate_ready",
        interrogation_task_ids=(),
        simple_action_summaries=(
            DashboardSimpleActionSummary(
                action_ref="dashboard-simple-action-test",
                outcome="needs_review",
                status_label="Needs approval",
                message="Draft ready.",
                risk="External message",
                approval_needed=True,
                evidence_saved=True,
                next_step="Approve or edit the draft.",
                choices=("Approve", "Edit", "Cancel", "View audit details"),
                audit_details_available=True,
                audit_details_visible=False,
                receipts_visible=False,
                proof_details_hidden=True,
            ),
        ),
        simple_workflow_summaries=(
            DashboardSimpleWorkflowSummary(
                workflow_ref="dashboard-simple-workflow-test",
                workflow="support_notice",
                label="Support notice",
                outcome="needs_review",
                title="Needs approval",
                message="Draft ready.",
                next_step="Approve or edit the draft.",
                ready_count=1,
                review_count=1,
                blocked_count=0,
                action_refs=("dashboard-simple-action-ready", "dashboard-simple-action-test"),
            ),
        ),
        simple_start_guide=DashboardSimpleStartGuideSummary(
            title="Start with simple mode",
            message="Choose a task and review the result.",
            recommended_commands=("mullu menu", "mullu workflows"),
            outcomes=("Ready", "Needs approval", "Blocked"),
        ),
        simple_home_summary=DashboardSimpleHomeSummary(
            title="Ready",
            message="Users can start with the recommended simple workflow path.",
            primary_command="mullu menu",
            ready_workflow_count=1,
            review_workflow_count=0,
            blocked_workflow_count=0,
        ),
        simple_review_action_refs=("dashboard-simple-action-test",),
        simple_review_workflow_refs=("dashboard-simple-workflow-test",),
        sdlc_receipt_summaries=(
            DashboardSdlcReceiptSummary(
                receipt_ref="dashboard-sdlc-receipt-test",
                receipt_id="sdlc_artifact_validation_receipt",
                status="passed",
                valid=True,
                check_count=1,
                passed_check_names=("sdlc_schema_contracts",),
                failed_check_names=(),
                error_count=0,
                terminal_closure_required=True,
                receipt_is_not_terminal_closure=True,
            ),
        ),
        sdlc_passed_receipt_refs=("dashboard-sdlc-receipt-test",),
    )


def test_operational_dashboard_runtime_returns_simple_home_envelope() -> None:
    runtime = OperationalDashboardRuntime.from_state(_dashboard_state())
    envelope = runtime.simple_home().to_dict()

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["home"]["title"] == "Ready"
    assert envelope["payload"]["home"]["status_label"] == "Ready"
    assert envelope["payload"]["home"]["count_summary"] == "1 ready, 0 need approval, 0 blocked"
    assert envelope["payload"]["home"]["next_action"] == "Start with `mullu menu`."
    assert envelope["payload"]["home"]["action_items"] == []
    assert envelope["payload"]["home"]["command_guidance"] == ["mullu menu"]
    assert envelope["payload"]["home"]["start_here"]["title"] == "Start here"
    assert envelope["payload"]["home"]["start_here"]["status_label"] == "Ready"
    assert envelope["payload"]["home"]["start_here"]["command_guidance"] == ["mullu menu"]
    assert envelope["payload"]["home"]["primary_command"] == "mullu menu"
    assert envelope["payload"]["home"]["execution_allowed"] is False


def test_operational_dashboard_runtime_returns_normal_user_simple_state() -> None:
    runtime = OperationalDashboardRuntime.from_state(_dashboard_state())
    envelope = runtime.simple_state().to_dict()
    dashboard = envelope["payload"]["dashboard"]

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert dashboard["visibility_level"] == "normal_user"
    assert dashboard["audit_details_visible"] is False
    assert dashboard["receipts_visible"] is False
    assert dashboard["proof_details_hidden"] is True
    assert dashboard["home"]["primary_command"] == "mullu menu"
    assert dashboard["simple_action_summaries"][0]["action_ref"] == "dashboard-simple-action-test"
    assert dashboard["simple_action_summaries"][0]["status_label"] == "Needs approval"
    assert dashboard["simple_action_summaries"][0]["proof_details_hidden"] is True
    assert dashboard["simple_workflow_summaries"][0]["action_refs"] == [
        "dashboard-simple-action-ready",
        "dashboard-simple-action-test",
    ]
    assert dashboard["simple_start_guide"]["recommended_commands"] == ["mullu menu", "mullu workflows"]
    assert dashboard["simple_review_action_refs"] == ["dashboard-simple-action-test"]
    assert dashboard["simple_review_workflow_refs"] == ["dashboard-simple-workflow-test"]
    assert "sdlc_receipt_summaries" not in dashboard
    assert "decision_ref" not in dashboard["simple_action_summaries"][0]
    assert "operator_details" not in dashboard["simple_action_summaries"][0]
    assert "proof_stamp_ref" not in dashboard["simple_action_summaries"][0]
    assert all(
        not action_ref.startswith(("gate-decision-", "proof-", "witness-"))
        for summary in dashboard["simple_workflow_summaries"]
        for action_ref in summary["action_refs"]
    )
    assert dashboard["execution_allowed"] is False


def test_operational_dashboard_runtime_returns_normal_user_client_contract() -> None:
    runtime = OperationalDashboardRuntime.from_state(_dashboard_state())
    envelope = runtime.simple_state_contract().to_dict()
    contract = envelope["payload"]["contract"]

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "listed"
    assert contract["contract_ref"] == "operational_dashboard.normal_user_dashboard.v1"
    assert contract["visibility_level"] == "normal_user"
    assert contract["route"] == {
        "method": "GET",
        "path": "/api/v1/dashboard/simple",
        "payload_key": "dashboard",
    }
    assert contract["page_route"] == {
        "method": "GET",
        "path": "/api/v1/dashboard/simple/page",
        "content_type": "text/html",
    }
    assert "simple_action_summaries" in contract["visible_payload_fields"]
    assert "simple_workflow_summaries" in contract["visible_payload_fields"]
    assert "execution_allowed" in contract["visible_payload_fields"]
    assert "decision_ref" in contract["hidden_fields"]
    assert "operator_details" in contract["hidden_fields"]
    assert "proof_stamp_ref" in contract["hidden_fields"]
    assert "gate-decision-" in contract["hidden_ref_prefixes"]
    assert "proof-" in contract["hidden_ref_prefixes"]
    assert "normal user payloads never grant execution authority" in contract["invariants"]


def test_operational_dashboard_runtime_rejects_normal_user_internal_ref_leak() -> None:
    state = OperationalDashboardState(
        dashboard_id="dashboard-test",
        projection_id="projection-test",
        active_project_count=1,
        ready_action_ids=(),
        blocked_action_ids=(),
        open_blocker_ids=(),
        open_conflict_ids=(),
        repair_ids=(),
        stale_high_impact_claim_ids=(),
        high_intensity_box_ids=(),
        constructive_delta_ids=(),
        fracture_delta_ids=(),
        memory_confidence_trend=1.0,
        workflow_health=WorkflowHealth.READY,
        execution_readiness="no_action_candidate_ready",
        interrogation_task_ids=(),
        simple_home_summary=DashboardSimpleHomeSummary(
            title="Ready",
            message="Users can start with the recommended simple workflow path.",
            primary_command="mullu menu",
            ready_workflow_count=1,
            review_workflow_count=0,
            blocked_workflow_count=0,
            action_items=(
                DashboardSimpleHomeAction(
                    action_ref="proof-secret",
                    label="Open audit",
                    command="mullu menu",
                    reason="Internal proof ref should not leak.",
                    outcome="ready",
                ),
            ),
        ),
    )
    envelope = OperationalDashboardRuntime.from_state(state).simple_state().to_dict()

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert envelope["payload"] == {}
    assert "internal governance refs" in envelope["error"]


def test_operational_dashboard_runtime_returns_full_state_envelope() -> None:
    runtime = OperationalDashboardRuntime.from_state(_dashboard_state())
    envelope = runtime.state().to_dict()

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["payload"]["dashboard"]["dashboard_id"] == "dashboard-test"
    assert envelope["payload"]["dashboard"]["simple_home_summary"]["ready_workflow_count"] == 1
    assert envelope["payload"]["dashboard"]["sdlc_receipt_summaries"][0]["receipt_id"] == "sdlc_artifact_validation_receipt"
    assert envelope["payload"]["dashboard"]["execution_allowed"] is False


def test_operational_dashboard_runtime_returns_sdlc_receipts_envelope() -> None:
    runtime = OperationalDashboardRuntime.from_state(_dashboard_state())
    envelope = runtime.sdlc_receipts().to_dict()

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["sdlc_receipts"][0]["receipt_id"] == "sdlc_artifact_validation_receipt"
    assert envelope["payload"]["sdlc_receipts"][0]["execution_allowed"] is False
    assert envelope["payload"]["passed_receipt_refs"] == ["dashboard-sdlc-receipt-test"]
    assert envelope["payload"]["failed_receipt_refs"] == []


def test_operational_dashboard_runtime_rejects_invalid_provider() -> None:
    runtime = OperationalDashboardRuntime(lambda: object())  # type: ignore[arg-type, return-value]
    envelope = runtime.simple_home().to_dict()

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert "OperationalDashboardState" in envelope["error"]


def test_operational_dashboard_fastapi_adapter_route_specs_are_stable() -> None:
    specs = OperationalDashboardFastAPIAdapter.route_specs()

    assert [(spec.method, spec.path, spec.handler_name) for spec in specs] == [
        ("GET", "/api/v1/dashboard/home", "simple_home"),
        ("GET", "/api/v1/dashboard/simple", "simple_state"),
        ("GET", "/api/v1/dashboard/simple/contract", "simple_state_contract"),
        ("GET", "/api/v1/dashboard/simple/client-view", "simple_client_view"),
        ("GET", "/api/v1/dashboard/simple/page", "simple_client_page"),
        ("GET", "/api/v1/dashboard/state", "state"),
        ("GET", "/api/v1/dashboard/sdlc/receipts", "sdlc_receipts"),
    ]
    assert all(spec.purpose for spec in specs)


def test_operational_dashboard_fastapi_adapter_preserves_runtime_envelopes() -> None:
    adapter = OperationalDashboardFastAPIAdapter(OperationalDashboardRuntime.from_state(_dashboard_state()))

    home = adapter.simple_home()
    simple = adapter.simple_state()
    contract = adapter.simple_state_contract()
    client_view = adapter.simple_client_view()
    client_page = adapter.simple_client_page()
    state = adapter.state()
    receipts = adapter.sdlc_receipts()

    assert home["governed"] is True
    assert home["payload"]["home"]["primary_command"] == "mullu menu"
    assert simple["payload"]["dashboard"]["visibility_level"] == "normal_user"
    assert simple["payload"]["dashboard"]["simple_action_summaries"][0]["proof_details_hidden"] is True
    assert contract["payload"]["contract"]["route"]["path"] == "/api/v1/dashboard/simple"
    assert contract["payload"]["contract"]["page_route"]["path"] == "/api/v1/dashboard/simple/page"
    assert contract["payload"]["contract"]["page_route"]["content_type"] == "text/html"
    assert "raw_decision" in contract["payload"]["contract"]["hidden_fields"]
    assert client_view["payload"]["client_view"]["visibility_level"] == "normal_user"
    assert client_view["payload"]["client_view"]["action_cards"][0]["primary_action"] == "Review"
    assert client_page.startswith("<!doctype html>")
    assert 'data-visibility="normal_user"' in client_page
    assert state["payload"]["dashboard"]["simple_home_summary"]["execution_allowed"] is False
    assert receipts["payload"]["sdlc_receipts"][0]["execution_allowed"] is False


def test_operational_dashboard_fastapi_router_serves_normal_user_html_page() -> None:
    fastapi = pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")
    app = fastapi.FastAPI()
    runtime = OperationalDashboardRuntime.from_state(_dashboard_state())
    app.include_router(create_operational_dashboard_fastapi_router(runtime))

    response = testclient.TestClient(app).get("/api/v1/dashboard/simple/page")
    html = response.text

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert html.startswith("<!doctype html>")
    assert 'data-visibility="normal_user"' in html
    assert 'aria-label="Safety status"' in html
    assert 'data-proof-hidden="true"' in html
    assert 'data-execution-allowed="false"' in html
    assert "Needs approval" in html
    assert "Draft ready." in html
    assert "Actions locked" in html
    assert "disabled" in html
    assert "Governance status" not in html
    assert "Execution disabled" not in html
    assert "Evidence hidden" not in html
    assert "decision_ref" not in html
    assert "operator_details" not in html
    assert "proof_stamp_ref" not in html
    assert "gate-decision-" not in html
    assert "witness-" not in html


def test_operational_dashboard_fastapi_router_blocks_invalid_html_page_provider() -> None:
    fastapi = pytest.importorskip("fastapi")
    testclient = pytest.importorskip("fastapi.testclient")
    app = fastapi.FastAPI()
    runtime = OperationalDashboardRuntime(lambda: object())  # type: ignore[arg-type, return-value]
    app.include_router(create_operational_dashboard_fastapi_router(runtime))

    response = testclient.TestClient(app).get("/api/v1/dashboard/simple/page")
    html = response.text

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert html.startswith("<!doctype html>")
    assert "Blocked for safety" in html
    assert 'data-visibility="normal_user"' in html
    assert 'aria-label="Safety status"' in html
    assert 'data-proof-hidden="true"' in html
    assert 'data-execution-allowed="false"' in html
    assert "Evidence unavailable" in html
    assert "Actions locked" in html
    assert "Governance status" not in html
    assert "Execution disabled" not in html
    assert "Evidence hidden" not in html
    assert "decision_ref" not in html
    assert "operator_details" not in html
    assert "proof_stamp_ref" not in html
    assert "gate-decision-" not in html
    assert "witness-" not in html


def test_create_operational_dashboard_fastapi_router_reports_missing_dependency() -> None:
    runtime = OperationalDashboardRuntime.from_state(_dashboard_state())

    try:
        router = create_operational_dashboard_fastapi_router(runtime)
    except RuntimeError as exc:
        assert "FastAPI is required" in str(exc)
    else:
        assert router is not None
