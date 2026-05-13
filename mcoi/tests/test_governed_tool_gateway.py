"""Purpose: verify governed tool gateway receipts and causal ledger binding.
Governance scope: tool invocation policy, pre-execution cause checks, and
hash-only evidence recording.
Dependencies: governed tool gateway, governed tool use, and permission primitives.
Invariants: every invocation outcome is receipted; missing causes block execution.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.causal_runtime_ledger import CausalRuntimeLedger
from mcoi_runtime.core.governed_tool_gateway import GovernedToolGateway, ToolGatewayRequest
from mcoi_runtime.core.governed_tool_use import GovernedToolRegistry, ToolDefinition
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.tool_permission_primitives import ToolCallPermission, ToolPermissionRegistry


def _clock() -> str:
    return "2026-05-13T12:30:00+00:00"


def _gateway() -> GovernedToolGateway:
    registry = GovernedToolRegistry(clock=_clock)
    ledger = CausalRuntimeLedger(clock=_clock)
    return GovernedToolGateway(registry=registry, ledger=ledger)


def _request(**overrides: object) -> ToolGatewayRequest:
    payload: dict[str, object] = {
        "tenant_id": "tenant-1",
        "actor_id": "agent-1",
        "session_id": "session-1",
        "tool_name": "docs.search",
        "arguments": {"query": "policy"},
        "budget_ref": "budget-search",
        "correlation_id": "corr-1",
    }
    payload.update(overrides)
    return ToolGatewayRequest(**payload)  # type: ignore[arg-type]


def test_gateway_records_success_receipt_and_ledger_event() -> None:
    gateway = _gateway()
    gateway.register(
        ToolDefinition(name="docs.search", description="Search documents"),
        executor=lambda _name, args: {"hits": [args["query"]]},
    )

    result = gateway.invoke(_request())

    assert result.allowed is True
    assert result.status == "succeeded"
    assert result.receipt.ledger_event_id == result.ledger_event.event_id
    assert gateway.ledger.verify_chain().verified is True
    assert result.ledger_event.metadata["tool_name"] == "docs.search"


def test_gateway_records_denied_unregistered_tool() -> None:
    gateway = _gateway()

    result = gateway.invoke(_request(tool_name="shell.run", arguments={"command": "whoami"}))

    assert result.allowed is False
    assert result.status == "denied"
    assert "not registered" in result.registry_result.error
    assert result.ledger_event.outcome == "denied"
    assert "denial:tool not registered" in result.ledger_event.constraint_refs


def test_gateway_blocks_unknown_cause_before_executor_runs() -> None:
    gateway = _gateway()
    calls: list[str] = []
    gateway.register(
        ToolDefinition(name="docs.search", description="Search documents"),
        executor=lambda _name, _args: calls.append("called") or {"hits": []},
    )

    with pytest.raises(RuntimeCoreInvariantError, match="cause event not found"):
        gateway.invoke(_request(cause_event_ids=("missing-cause",)))

    assert calls == []
    assert gateway.ledger.event_count == 0
    assert gateway.ledger.verify_chain().verified is True


def test_gateway_binds_permission_decision_to_receipt() -> None:
    permission_registry = ToolPermissionRegistry()
    permission = permission_registry.register(
        ToolCallPermission(
            tenant_id="tenant-1",
            tool_name="docs.search",
            argument_schema={
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
                "additionalProperties": False,
            },
            budget_ref="budget-search",
        )
    )
    registry = GovernedToolRegistry(clock=_clock)
    registry.bind_permission_registry(permission_registry)
    gateway = GovernedToolGateway(
        registry=registry,
        ledger=CausalRuntimeLedger(clock=_clock),
    )
    gateway.register(
        ToolDefinition(name="docs.search", description="Search documents"),
        executor=lambda _name, args: {"hits": [args["query"]]},
    )

    result = gateway.invoke(_request())

    assert result.allowed is True
    assert result.receipt.permission_id == permission.permission_id
    assert result.receipt.reason_codes == ("permission_matched",)
    assert f"permission:{permission.permission_id}" in result.ledger_event.constraint_refs
    assert result.ledger_event.metadata["reason_codes"] == ["permission_matched"]
