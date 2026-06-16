"""Tests for the optional simple platform FastAPI adapter.

Purpose: verify dashboard-ready action checks preserve the simple governed
outcomes without requiring FastAPI as a core dependency.
Governance scope: HTTP-shaped adapter must preserve SimplePlatformRuntime
validation, proof references, review escalation, and rejection envelopes.
Dependencies: simple platform API and optional FastAPI router adapter.
Invariants: route specs are stable, handlers remain governed, and missing
FastAPI is explicit when router creation is requested.
"""

from __future__ import annotations

from mcoi_runtime.core.simple_platform_api import SimplePlatformRuntime
from mcoi_runtime.core.simple_platform_fastapi_router import (
    SimplePlatformFastAPIAdapter,
    create_simple_platform_fastapi_router,
)


def _request(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "goal": "Review docs",
        "action": "view",
        "target": "docs/README.md",
        "allowed_area": "docs/**",
        "actor_id": "simple-http-test",
    }
    value.update(overrides)
    return value


def test_simple_platform_fastapi_adapter_route_specs_are_stable() -> None:
    specs = SimplePlatformFastAPIAdapter.route_specs()

    assert len(specs) == 12
    assert [(spec.method, spec.path, spec.handler_name) for spec in specs] == [
        ("GET", "/api/v1/simple/home", "simple_home"),
        ("GET", "/api/v1/simple/actions", "action_menu"),
        ("GET", "/api/v1/simple/start", "start_guide"),
        ("GET", "/api/v1/simple/documents/wiring", "document_manipulation_wiring"),
        ("GET", "/api/v1/simple/documents/wiring/contract", "document_manipulation_wiring_contract"),
        ("POST", "/api/v1/simple/actions/check", "check_action"),
        ("POST", "/api/v1/simple/actions/experience", "check_action_experience"),
        ("POST", "/api/v1/simple/actions/check/audit", "check_action_audit"),
        ("POST", "/api/v1/simple/tasks/check", "check_task"),
        ("POST", "/api/v1/simple/tasks/check/audit", "check_task_audit"),
        ("POST", "/api/v1/simple/workflows/check", "check_workflow"),
        ("POST", "/api/v1/simple/workflows/check/audit", "check_workflow_audit"),
    ]
    assert all(spec.purpose for spec in specs)


def test_simple_platform_runtime_menu_is_plain_and_governed() -> None:
    envelope = SimplePlatformRuntime().action_menu().to_dict()

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "listed"
    assert [item["action"] for item in envelope["payload"]["actions"]] == ["view", "change", "send", "verify"]
    assert [item["task"] for item in envelope["payload"]["tasks"]] == [
        "review_docs",
        "update_docs",
        "notify_support",
        "verify_artifact",
    ]
    assert [item["workflow"] for item in envelope["payload"]["workflows"]] == [
        "docs_update",
        "support_notice",
        "artifact_review",
    ]
    assert [item["outcome"] for item in envelope["payload"]["outcomes"]] == [
        "ready",
        "needs_review",
        "blocked",
    ]
    assert [item["visibility_level"] for item in envelope["payload"]["visibility_levels"]] == [
        "normal_user",
        "operator",
        "auditor_developer",
    ]


def test_simple_platform_fastapi_adapter_returns_simple_home() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.simple_home()

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["home"]["primary_command"] == "mullu menu"
    assert envelope["payload"]["home"]["choices"][0]["label"] == "Open the simple menu"
    assert envelope["payload"]["home"]["execution_allowed"] is False


def test_simple_platform_fastapi_adapter_returns_ready_envelope() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_action(_request())
    experience = envelope["payload"]["experience"]

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert experience["status_label"] == "Ready"
    assert experience["proof_details_hidden"] is True
    assert "proof_stamp_ref" not in experience


def test_simple_platform_fastapi_adapter_returns_action_audit_envelope() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_action_audit(_request())

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["check"]["title"] == "Ready"
    assert envelope["payload"]["check"]["proof_stamp_ref"].startswith("proof-")


def test_simple_platform_fastapi_adapter_returns_normal_user_experience() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_action_experience(
        _request(
            goal="Notify support",
            action="send",
            target="support@mullusi.com",
            allowed_area="support@mullusi.com",
        )
    )
    experience = envelope["payload"]["experience"]

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "needs_review"
    assert experience["visibility_level"] == "normal_user"
    assert experience["risk"] == "External message"
    assert experience["approval_needed"] is True
    assert experience["audit_details_available"] is True
    assert experience["audit_details_visible"] is False
    assert "operator_details" not in experience


def test_simple_platform_fastapi_adapter_returns_auditor_experience() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_action_experience(_request(visibility_level="auditor_developer"))
    experience = envelope["payload"]["experience"]

    assert envelope["status"] == "ready"
    assert experience["visibility_level"] == "auditor_developer"
    assert experience["operator_details"]["proof_stamp_ref"].startswith("proof-")
    assert experience["auditor_details"]["raw_decision"] == "allow"


def test_simple_platform_fastapi_adapter_returns_start_guide() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.start_guide()

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "listed"
    assert envelope["payload"]["guide"]["execution_allowed"] is False
    assert envelope["payload"]["guide"]["recommended_path"][0]["command"] == "mullu menu"


def test_simple_platform_fastapi_adapter_returns_document_wiring() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.document_manipulation_wiring()
    wiring = envelope["payload"]["wiring"]

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "listed"
    assert wiring["manipulation_ref"] == "docs_update"
    assert wiring["components"][2]["component_ref"] == "cli.workflow_docs_update"
    assert wiring["execution_allowed"] is False


def test_simple_platform_fastapi_adapter_returns_document_wiring_contract() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.document_manipulation_wiring_contract()
    contract = envelope["payload"]["contract"]

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "listed"
    assert contract["contract_ref"] == "simple_platform.document_manipulation_wiring.v1"
    assert contract["routes"][1]["path"] == "/api/v1/simple/documents/wiring/contract"
    assert "document wiring is read-only" in contract["invariants"]


def test_simple_platform_fastapi_adapter_returns_task_envelope() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_task(
        {
            "task": "review_docs",
            "target": "docs/README.md",
            "actor_id": "simple-http-test",
        }
    )

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["experience"]["status_label"] == "Ready"
    assert envelope["payload"]["experience"]["proof_details_hidden"] is True
    assert "proof_stamp_ref" not in envelope["payload"]["experience"]


def test_simple_platform_fastapi_adapter_returns_workflow_envelope() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_workflow(
        {
            "workflow": "docs_update",
            "target": "docs/README.md",
            "actor_id": "simple-http-test",
        }
    )

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["workflow"]["ready_count"] == 3
    assert envelope["payload"]["workflow"]["steps"][0]["status_label"] == "Ready"
    assert envelope["payload"]["workflow"]["proof_details_hidden"] is True
    assert "checks" not in envelope["payload"]["workflow"]


def test_simple_platform_fastapi_adapter_returns_workflow_audit_envelope() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_workflow_audit(
        {
            "workflow": "docs_update",
            "target": "docs/README.md",
            "actor_id": "simple-http-test",
        }
    )

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["workflow"]["checks"][0]["proof_stamp_ref"].startswith("proof-")


def test_simple_platform_fastapi_adapter_returns_review_envelope() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_action(
        _request(
            goal="Notify support",
            action="send",
            target="support@mullusi.com",
            allowed_area="support@mullusi.com",
        )
    )

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "needs_review"
    assert envelope["payload"]["experience"]["status_label"] == "Needs approval"
    assert envelope["payload"]["experience"]["risk"] == "External message"
    assert envelope["payload"]["experience"]["audit_details_visible"] is False
    assert "review_reasons" not in envelope["payload"]["experience"]


def test_simple_platform_fastapi_adapter_rejects_invalid_requests() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_action(_request(action="delete"))

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert "action must be one of" in envelope["error"]
    assert envelope["payload"] == {}


def test_simple_platform_fastapi_adapter_rejects_unknown_fields_without_reflection() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_action(_request(scope_override=True))

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert envelope["payload"] == {}
    assert envelope["error"] == "request contains unsupported fields"
    assert "scope_override" not in envelope["error"]


def test_simple_platform_fastapi_adapter_rejects_invalid_task() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_task({"task": "unknown-task", "target": "docs/README.md"})

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert "task must be one of" in envelope["error"]
    assert envelope["payload"] == {}


def test_simple_platform_fastapi_adapter_rejects_invalid_workflow() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_workflow({"workflow": "unknown-workflow", "target": "docs/README.md"})

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert "workflow must be one of" in envelope["error"]
    assert envelope["payload"] == {}


def test_create_simple_platform_fastapi_router_reports_missing_dependency() -> None:
    runtime = SimplePlatformRuntime()

    try:
        router = create_simple_platform_fastapi_router(runtime)
    except RuntimeError as exc:
        assert "FastAPI is required" in str(exc)
    else:
        assert router is not None
