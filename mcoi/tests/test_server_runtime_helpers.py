"""Purpose: verify runtime helper contracts for the governed server.
Governance scope: helper validation tests only.
Dependencies: server runtime and runtime-stack helpers with pytest support.
Invariants: runtime helper composition remains deterministic and auditable.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from mcoi_runtime.app import server_runtime
from mcoi_runtime.app import server_runtime_stack
from mcoi_runtime.core.structured_output import StructuredOutputEngine
from mcoi_runtime.core.tool_use import ToolRegistry


def test_build_default_input_validator_registers_expected_schemas() -> None:
    validator = server_runtime.build_default_input_validator()

    assert validator.schema_count == 3
    assert validator.validate("api_request", {"tenant_id": "tenant-a"}).valid is True
    assert (
        validator.validate(
            "completion",
            {"prompt": "x", "max_tokens": 1, "temperature": 0.0},
        ).valid
        is True
    )


def test_bootstrap_server_runtime_stack_preserves_order_and_exported_bindings() -> None:
    captured: dict[str, object] = {}
    observability = object()
    access_runtime = object()
    temporal_runtime = object()
    guard_chain = object()
    shutdown_mgr = object()
    state_persistence = object()

    agent_bootstrap = SimpleNamespace(
        observability=observability,
        deep_health=object(),
        workflow_engine=object(),
    )
    subsystem_bootstrap = SimpleNamespace(
        event_bus=object(),
        access_runtime=access_runtime,
        temporal_runtime=temporal_runtime,
    )
    operational_bootstrap = SimpleNamespace(
        guard_chain=guard_chain,
    )
    capability_bootstrap = SimpleNamespace(
        shutdown_mgr=shutdown_mgr,
        state_persistence=state_persistence,
    )

    def fake_bootstrap_agent_runtime_fn(**kwargs):
        captured["agent_kwargs"] = kwargs
        return agent_bootstrap

    def fake_bootstrap_subsystems_fn(**kwargs):
        captured["subsystem_kwargs"] = kwargs
        return subsystem_bootstrap

    def fake_bootstrap_operational_services_fn(**kwargs):
        captured["operational_kwargs"] = kwargs
        return operational_bootstrap

    def fake_bootstrap_capability_services_fn(**kwargs):
        captured["capability_kwargs"] = kwargs
        return capability_bootstrap

    bootstrap = server_runtime_stack.bootstrap_server_runtime_stack(
        clock=lambda: "2026-01-01T00:00:00Z",
        env="test",
        runtime_env={"MULLU_ENV": "test"},
        store=object(),
        llm_bridge=object(),
        cert_daemon=object(),
        metrics=object(),
        default_model="stub",
        audit_trail=object(),
        tenant_budget_mgr=object(),
        tenant_gating=object(),
        pii_scanner=object(),
        content_safety_chain=object(),
        proof_bridge=object(),
        rate_limiter=object(),
        shell_policy=object(),
        jwt_authenticator=object(),
        evaluate_expression_fn=lambda value: value,
        bootstrap_agent_runtime_fn=fake_bootstrap_agent_runtime_fn,
        bootstrap_subsystems_fn=fake_bootstrap_subsystems_fn,
        bootstrap_operational_services_fn=fake_bootstrap_operational_services_fn,
        bootstrap_capability_services_fn=fake_bootstrap_capability_services_fn,
    )

    assert captured["subsystem_kwargs"]["observability"] is observability
    assert captured["subsystem_kwargs"]["deep_health"] is agent_bootstrap.deep_health
    assert (
        captured["operational_kwargs"]["workflow_engine"]
        is agent_bootstrap.workflow_engine
    )
    assert captured["operational_kwargs"]["event_bus"] is subsystem_bootstrap.event_bus
    assert captured["operational_kwargs"]["access_runtime"] is access_runtime
    assert captured["operational_kwargs"]["temporal_runtime"] is temporal_runtime
    assert captured["capability_kwargs"]["observability"] is observability
    assert bootstrap.observability is observability
    assert bootstrap.access_runtime is access_runtime
    assert bootstrap.guard_chain is guard_chain
    assert bootstrap.shutdown_mgr is shutdown_mgr
    assert bootstrap.state_persistence is state_persistence


def test_validate_or_raise_returns_bounded_422_payload() -> None:
    validator = server_runtime.build_default_input_validator()

    with pytest.raises(Exception) as exc_info:
        server_runtime.validate_or_raise(
            input_validator=validator,
            schema_id="completion",
            data={"prompt": "", "max_tokens": 0, "temperature": 3.0},
        )

    exc = exc_info.value
    assert getattr(exc, "status_code", None) == 422
    assert exc.detail["error"] == "Validation failed"
    assert exc.detail["governed"] is True
    assert exc.detail["validation_errors"]


def test_calculator_handler_uses_expression_engine() -> None:
    result = server_runtime.calculator_handler(
        {"expression": "2+3"},
        evaluate_expression_fn=lambda expression: 5 if expression == "2+3" else 0,
    )

    assert result == {"result": "5"}


def test_register_default_tools_registers_calculator_and_time() -> None:
    registry = ToolRegistry(clock=lambda: "2026-01-01T00:00:00Z")

    server_runtime.register_default_tools(
        tool_registry=registry,
        clock=lambda: "2026-01-01T00:00:00Z",
        evaluate_expression_fn=lambda expression: 7 if expression == "3+4" else 0,
    )

    listed = registry.list_tools()
    ids = {tool.tool_id for tool in listed}
    assert ids == {"calculator", "get_time"}
    assert registry.invoke("calculator", {"expression": "3+4"}).output == {"result": "7"}
    assert registry.invoke("get_time", {}).output == {"time": "2026-01-01T00:00:00Z"}


def test_register_default_output_schemas_registers_analysis_schema() -> None:
    engine = StructuredOutputEngine()
    server_runtime.register_default_output_schemas(engine)

    summary = engine.summary()
    assert summary["schemas"] == 1
    assert engine.list_schemas()[0].schema_id == "analysis"
