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

    assert len(specs) == 4
    assert [(spec.method, spec.path, spec.handler_name) for spec in specs] == [
        ("GET", "/api/v1/simple/actions", "action_menu"),
        ("POST", "/api/v1/simple/actions/check", "check_action"),
        ("POST", "/api/v1/simple/tasks/check", "check_task"),
        ("POST", "/api/v1/simple/workflows/check", "check_workflow"),
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


def test_simple_platform_fastapi_adapter_returns_ready_envelope() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_action(_request())

    assert envelope["governed"] is True
    assert envelope["ok"] is True
    assert envelope["status"] == "ready"
    assert envelope["payload"]["check"]["title"] == "Ready"
    assert envelope["payload"]["check"]["proof_stamp_ref"].startswith("proof-")


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
    assert envelope["payload"]["check"]["title"] == "Ready"


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
    assert envelope["payload"]["workflow"]["checks"][0]["title"] == "Ready"


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
    assert envelope["payload"]["check"]["review_reasons"] == ["External changes require approval."]
    assert envelope["payload"]["check"]["blocked_reasons"] == []


def test_simple_platform_fastapi_adapter_rejects_invalid_requests() -> None:
    adapter = SimplePlatformFastAPIAdapter(SimplePlatformRuntime())
    envelope = adapter.check_action(_request(action="delete"))

    assert envelope["governed"] is True
    assert envelope["ok"] is False
    assert envelope["status"] == "rejected"
    assert "action must be one of" in envelope["error"]
    assert envelope["payload"] == {}


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
