"""Purpose: verify governed tool gateway receipts and causal ledger binding.
Governance scope: tool invocation policy, pre-execution cause checks, and
hash-only evidence recording.
Dependencies: governed tool gateway, governed tool use, and permission primitives.
Invariants: every invocation outcome is receipted; missing causes block execution.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.core.artifact_lineage_dag import ArtifactLineageDAG, hash_artifact_payload
from mcoi_runtime.core.causal_runtime_ledger import CausalRuntimeLedger
from mcoi_runtime.core.governed_tool_gateway import (
    GovernedToolGateway,
    ToolGatewayArtifactBinding,
    ToolGatewayRequest,
    tool_gateway_receipt_json,
)
from mcoi_runtime.core.governed_tool_use import GovernedToolRegistry, ToolDefinition
from mcoi_runtime.core.invariants import RuntimeCoreInvariantError
from mcoi_runtime.core.tool_permission_primitives import ToolCallPermission, ToolPermissionRegistry


def _clock() -> str:
    return "2026-05-13T12:30:00+00:00"


def _gateway() -> GovernedToolGateway:
    registry = GovernedToolRegistry(clock=_clock)
    ledger = CausalRuntimeLedger(clock=_clock)
    return GovernedToolGateway(registry=registry, ledger=ledger)


def _lineage_gateway(lineage: ArtifactLineageDAG | None = None) -> GovernedToolGateway:
    registry = GovernedToolRegistry(clock=_clock)
    ledger = CausalRuntimeLedger(clock=_clock)
    return GovernedToolGateway(
        registry=registry,
        ledger=ledger,
        artifact_lineage=lineage or ArtifactLineageDAG(clock=_clock),
    )


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


def test_gateway_registers_successful_tool_artifact_in_lineage() -> None:
    lineage = ArtifactLineageDAG(clock=_clock)
    gateway = _lineage_gateway(lineage)
    gateway.register(
        ToolDefinition(name="docs.render", description="Render document"),
        executor=lambda _name, _args: {"document_id": "doc-1"},
    )

    result = gateway.invoke(
        _request(
            tool_name="docs.render",
            arguments={"template": "policy"},
            produced_artifacts=(
                ToolGatewayArtifactBinding(
                    artifact_id="artifact-doc-1",
                    artifact_type="document",
                    payload={"document_id": "doc-1"},
                    metadata={"format": "markdown"},
                ),
            ),
        )
    )
    artifact = lineage.get_artifact("artifact-doc-1")

    assert result.status == "succeeded"
    assert result.receipt.artifact_ids == ("artifact-doc-1",)
    assert artifact is not None
    assert artifact.produced_by_event_id == result.ledger_event.event_id
    assert tool_gateway_receipt_json(result.receipt)["artifact_ids"] == ["artifact-doc-1"]


def test_gateway_links_produced_artifact_to_existing_dependency() -> None:
    lineage = ArtifactLineageDAG(clock=_clock)
    lineage.register_artifact(
        artifact_id="source-json",
        artifact_hash=hash_artifact_payload({"source": True}),
        artifact_type="json",
        tenant_id="tenant-1",
        produced_by_event_id="event-source",
    )
    gateway = _lineage_gateway(lineage)
    gateway.register(
        ToolDefinition(name="docs.summarize", description="Summarize source"),
        executor=lambda _name, _args: {"summary": "ok"},
    )

    result = gateway.invoke(
        _request(
            tool_name="docs.summarize",
            arguments={"source": "source-json"},
            produced_artifacts=(
                ToolGatewayArtifactBinding(
                    artifact_id="summary-json",
                    artifact_type="json",
                    payload={"summary": "ok"},
                    depends_on_artifact_ids=("source-json",),
                ),
            ),
        )
    )
    plan = lineage.replay_plan("summary-json")

    assert result.artifacts[0].artifact_id == "summary-json"
    assert plan.ready is True
    assert plan.artifact_ids == ("source-json", "summary-json")
    assert lineage.descendants_of("source-json") == ("summary-json",)


def test_gateway_requires_lineage_before_artifact_tool_execution() -> None:
    gateway = _gateway()
    calls: list[str] = []
    gateway.register(
        ToolDefinition(name="docs.render", description="Render document"),
        executor=lambda _name, _args: calls.append("called") or {"document_id": "doc-1"},
    )

    with pytest.raises(RuntimeCoreInvariantError, match="artifact lineage is required"):
        gateway.invoke(
            _request(
                tool_name="docs.render",
                produced_artifacts=(
                    ToolGatewayArtifactBinding(
                        artifact_id="artifact-doc-1",
                        artifact_type="document",
                        payload={"document_id": "doc-1"},
                    ),
                ),
            )
        )

    assert calls == []
    assert gateway.ledger.event_count == 0
    assert gateway.ledger.verify_chain().verified is True


def test_gateway_does_not_register_artifact_for_denied_tool() -> None:
    lineage = ArtifactLineageDAG(clock=_clock)
    gateway = _lineage_gateway(lineage)

    result = gateway.invoke(
        _request(
            tool_name="docs.render",
            produced_artifacts=(
                ToolGatewayArtifactBinding(
                    artifact_id="artifact-doc-1",
                    artifact_type="document",
                    payload={"document_id": "doc-1"},
                ),
            ),
        )
    )

    assert result.allowed is False
    assert result.receipt.artifact_ids == ()
    assert lineage.get_artifact("artifact-doc-1") is None
    assert lineage.artifact_count == 0


def test_gateway_supports_same_call_artifact_dependencies() -> None:
    lineage = ArtifactLineageDAG(clock=_clock)
    gateway = _lineage_gateway(lineage)
    gateway.register(
        ToolDefinition(name="docs.package", description="Package document"),
        executor=lambda _name, _args: {"package_id": "pkg-1"},
    )

    result = gateway.invoke(
        _request(
            tool_name="docs.package",
            arguments={"source": "draft"},
            produced_artifacts=(
                ToolGatewayArtifactBinding(
                    artifact_id="draft-md",
                    artifact_type="markdown",
                    payload={"draft": "body"},
                ),
                ToolGatewayArtifactBinding(
                    artifact_id="package-json",
                    artifact_type="json",
                    payload={"package_id": "pkg-1"},
                    depends_on_artifact_ids=("draft-md",),
                ),
            ),
        )
    )
    plan = lineage.replay_plan("package-json")

    assert result.status == "succeeded"
    assert result.receipt.artifact_ids == ("draft-md", "package-json")
    assert plan.artifact_ids == ("draft-md", "package-json")
    assert lineage.descendants_of("draft-md") == ("package-json",)


def test_gateway_blocks_same_call_artifact_cycles_before_execution() -> None:
    lineage = ArtifactLineageDAG(clock=_clock)
    gateway = _lineage_gateway(lineage)
    calls: list[str] = []
    gateway.register(
        ToolDefinition(name="docs.package", description="Package document"),
        executor=lambda _name, _args: calls.append("called") or {"package_id": "pkg-1"},
    )

    with pytest.raises(RuntimeCoreInvariantError, match="produced artifact cycle detected"):
        gateway.invoke(
            _request(
                tool_name="docs.package",
                produced_artifacts=(
                    ToolGatewayArtifactBinding(
                        artifact_id="artifact-a",
                        artifact_type="json",
                        payload={"a": True},
                        depends_on_artifact_ids=("artifact-b",),
                    ),
                    ToolGatewayArtifactBinding(
                        artifact_id="artifact-b",
                        artifact_type="json",
                        payload={"b": True},
                        depends_on_artifact_ids=("artifact-a",),
                    ),
                ),
            )
        )

    assert calls == []
    assert lineage.artifact_count == 0
    assert gateway.ledger.event_count == 0
