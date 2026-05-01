"""Purpose: validate governed MCP capability execution wrapper.
Governance scope: certification gates, approval/budget/isolation witnesses,
MCP client invocation, and execution receipts.
Dependencies: mcoi_runtime.mcp capability bridge and governed executor.
Invariants:
  - MCP tools execute only as certified Mullu capabilities.
  - Execution context must carry command, approval, budget, and isolation witnesses.
  - Every MCP call returns deterministic input/output receipt hashes.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Mapping

import pytest

from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
)
from mcoi_runtime.mcp import (
    GovernedMCPExecutionContext,
    GovernedMCPExecutor,
    InMemoryMCPExecutionAuditStore,
    JsonlMCPExecutionAuditStore,
    MCPToolCallResult,
    MCPToolDescriptor,
    build_mcp_execution_audit_store_from_env,
    import_mcp_tool_as_capability,
)


class StubMCPClient:
    def __init__(self, result: MCPToolCallResult) -> None:
        self.result = result
        self.calls: list[dict[str, Any]] = []

    def call_tool(
        self,
        *,
        server_id: str,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> MCPToolCallResult:
        self.calls.append({
            "server_id": server_id,
            "tool_name": tool_name,
            "arguments": dict(arguments),
        })
        return self.result


class ExplodingMCPClient:
    def __init__(self) -> None:
        self.calls = 0

    def call_tool(
        self,
        *,
        server_id: str,
        tool_name: str,
        arguments: Mapping[str, Any],
    ) -> MCPToolCallResult:
        self.calls += 1
        raise RuntimeError("provider leaked secret-token")


def _candidate_capability() -> CapabilityRegistryEntry:
    return import_mcp_tool_as_capability(
        MCPToolDescriptor(
            server_id="GitHub Enterprise",
            name="Create Issue",
            description="Create an issue.",
            input_schema={
                "type": "object",
                "properties": {"title": {"type": "string"}},
                "required": ["title"],
            },
            annotations={"expected_effects": ["external_tool_invoked"]},
        )
    )


def _certified(entry: CapabilityRegistryEntry | None = None) -> CapabilityRegistryEntry:
    candidate = entry or _candidate_capability()
    return CapabilityRegistryEntry(
        capability_id=candidate.capability_id,
        domain=candidate.domain,
        version=candidate.version,
        input_schema_ref=candidate.input_schema_ref,
        output_schema_ref=candidate.output_schema_ref,
        effect_model=candidate.effect_model,
        evidence_model=candidate.evidence_model,
        authority_policy=candidate.authority_policy,
        isolation_profile=candidate.isolation_profile,
        recovery_plan=candidate.recovery_plan,
        cost_model=candidate.cost_model,
        obligation_model=candidate.obligation_model,
        certification_status=CapabilityCertificationStatus.CERTIFIED,
        metadata=candidate.metadata,
        extensions=candidate.extensions,
    )


def _context(**overrides) -> GovernedMCPExecutionContext:
    payload = {
        "tenant_id": "tenant-1",
        "identity_id": "identity-1",
        "command_id": "cmd-1",
        "approval_id": "approval-1",
        "budget_reservation_id": "budget-1",
        "isolation_boundary_id": "isolation-1",
    }
    payload.update(overrides)
    return GovernedMCPExecutionContext(**payload)


def test_governed_mcp_executor_calls_client_and_returns_receipt() -> None:
    client = StubMCPClient(MCPToolCallResult(
        content={"issue_id": "ISSUE-1"},
        metadata={"provider_request_id": "provider-1"},
    ))
    executor = GovernedMCPExecutor(
        client,
        worker_id="mcp-worker-1",
        clock=lambda: "2026-04-29T12:00:00+00:00",
    )

    result = executor.execute(
        capability=_certified(),
        context=_context(),
        params={"title": "Fix governed bridge"},
    )

    assert result.succeeded is True
    assert result.error == ""
    assert result.output == {"issue_id": "ISSUE-1"}
    assert result.receipt.receipt_id.startswith("mcp-execution-receipt-")
    assert result.receipt.capability_id == "mcp.github_enterprise_create_issue"
    assert result.receipt.server_id == "GitHub Enterprise"
    assert result.receipt.tool_name == "Create Issue"
    assert result.receipt.command_id == "cmd-1"
    assert result.receipt.approval_id == "approval-1"
    assert result.receipt.budget_reservation_id == "budget-1"
    assert result.receipt.isolation_boundary_id == "isolation-1"
    assert result.receipt.input_hash
    assert result.receipt.output_hash
    assert result.receipt.status == "succeeded"
    assert result.metadata["terminal_certificate_required"] is True
    audits = executor.audit_records()
    assert len(audits) == 1
    assert audits[0].audit_id.startswith("mcp-execution-audit-")
    assert audits[0].status == "succeeded"
    assert audits[0].reason == "mcp_tool_call_succeeded"
    assert audits[0].receipt_id == result.receipt.receipt_id
    assert audits[0].input_hash == result.receipt.input_hash
    assert audits[0].output_hash == result.receipt.output_hash
    assert audits[0].evidence_refs == result.receipt.evidence_refs
    assert executor.audit_records(command_id="cmd-1") == audits
    assert executor.audit_records(status="succeeded") == audits
    assert client.calls == [{
        "server_id": "GitHub Enterprise",
        "tool_name": "Create Issue",
        "arguments": {"title": "Fix governed bridge"},
    }]


def test_governed_mcp_executor_records_failed_tool_call_receipt() -> None:
    client = StubMCPClient(MCPToolCallResult(
        content="provider rejected request",
        is_error=True,
        metadata={"provider_request_id": "provider-2"},
    ))
    executor = GovernedMCPExecutor(client)

    result = executor.execute(
        capability=_certified(),
        context=_context(),
        params={"title": "Unsafe title"},
    )

    assert result.succeeded is False
    assert result.error == "mcp_tool_call_failed"
    assert result.receipt.status == "failed"
    assert result.receipt.output_hash
    assert result.metadata["mcp_call_metadata"] == {"provider_request_id": "provider-2"}
    audits = executor.audit_records(status="failed")
    assert len(audits) == 1
    assert audits[0].status == "failed"
    assert audits[0].reason == "mcp_tool_call_failed"
    assert audits[0].receipt_id == result.receipt.receipt_id
    assert executor.audit_records(status="succeeded") == ()
    assert client.calls[0]["arguments"] == {"title": "Unsafe title"}


def test_governed_mcp_executor_wraps_client_exception_in_failed_receipt() -> None:
    client = ExplodingMCPClient()
    executor = GovernedMCPExecutor(client)

    result = executor.execute(
        capability=_certified(),
        context=_context(),
        params={"title": "Transport failure"},
    )

    assert result.succeeded is False
    assert result.error == "mcp_tool_call_failed"
    assert result.output == {"error": "mcp_tool_call_exception"}
    assert result.receipt.status == "failed"
    assert result.receipt.output_hash
    assert result.metadata["mcp_call_metadata"] == {}
    audits = executor.audit_records()
    assert audits[0].status == "failed"
    assert audits[0].reason == "mcp_tool_call_failed"
    assert audits[0].receipt_id == result.receipt.receipt_id
    assert "secret-token" not in result.error
    assert client.calls == 1


def test_governed_mcp_executor_rejects_uncertified_capability() -> None:
    executor = GovernedMCPExecutor(StubMCPClient(MCPToolCallResult(content={})))

    with pytest.raises(ValueError, match="requires certified capability"):
        executor.execute(
            capability=_candidate_capability(),
            context=_context(),
            params={"title": "Blocked"},
        )

    audits = executor.audit_records(status="rejected")
    assert len(audits) == 1
    assert audits[0].capability_id == "mcp.github_enterprise_create_issue"
    assert audits[0].command_id == "cmd-1"
    assert audits[0].reason == "MCP capability execution requires certified capability"
    assert executor is not None
    assert _candidate_capability().certification_status is CapabilityCertificationStatus.CANDIDATE


def test_governed_mcp_executor_rejects_non_mcp_capability() -> None:
    capability = replace(_certified(), domain="enterprise")
    executor = GovernedMCPExecutor(StubMCPClient(MCPToolCallResult(content={})))

    with pytest.raises(ValueError, match="requires mcp domain"):
        executor.execute(
            capability=capability,
            context=_context(),
            params={"title": "Blocked"},
        )

    assert capability.domain == "enterprise"
    assert capability.certification_status is CapabilityCertificationStatus.CERTIFIED


def test_governed_mcp_execution_context_requires_governance_witnesses() -> None:
    with pytest.raises(ValueError, match="approval_id is required"):
        _context(approval_id="")

    with pytest.raises(ValueError, match="budget_reservation_id is required"):
        _context(budget_reservation_id="")

    with pytest.raises(ValueError, match="isolation_boundary_id is required"):
        _context(isolation_boundary_id="")


def test_governed_mcp_executor_audit_records_are_bounded_newest_first() -> None:
    executor = GovernedMCPExecutor(StubMCPClient(MCPToolCallResult(content={})))

    executor.execute(
        capability=_certified(),
        context=_context(command_id="cmd-1"),
        params={"title": "First"},
    )
    executor.execute(
        capability=_certified(),
        context=_context(command_id="cmd-2"),
        params={"title": "Second"},
    )
    audits = executor.audit_records(limit=1)

    assert len(audits) == 1
    assert audits[0].command_id == "cmd-2"
    assert executor.audit_records(command_id="missing") == ()


def test_governed_mcp_executor_persists_audits_through_store() -> None:
    store = InMemoryMCPExecutionAuditStore()
    executor = GovernedMCPExecutor(
        StubMCPClient(MCPToolCallResult(content={"ok": True})),
        audit_store=store,
    )

    executor.execute(
        capability=_certified(),
        context=_context(command_id="cmd-store-1"),
        params={"title": "Persist audit"},
    )

    stored = store.list(command_id="cmd-store-1", status="succeeded")
    assert len(stored) == 1
    assert stored[0].audit_id.startswith("mcp-execution-audit-")
    assert stored[0].receipt_id.startswith("mcp-execution-receipt-")
    assert executor.audit_records(command_id="cmd-store-1") == stored


def test_governed_mcp_executor_exports_execution_evidence_bundle() -> None:
    executor = GovernedMCPExecutor(
        StubMCPClient(MCPToolCallResult(content={"issue_id": "ISSUE-2"})),
        clock=lambda: "2026-04-29T12:00:00+00:00",
    )
    result = executor.execute(
        capability=_certified(),
        context=_context(command_id="cmd-bundle-1"),
        params={"title": "Bundle proof"},
    )

    bundle = executor.export_evidence_bundle(command_id="cmd-bundle-1")

    assert bundle.bundle_id.startswith("mcp-evidence-bundle-")
    assert bundle.bundle_hash
    assert bundle.command_id == "cmd-bundle-1"
    assert bundle.capability_id == "mcp.github_enterprise_create_issue"
    assert bundle.status == "succeeded"
    assert bundle.receipt_id == result.receipt.receipt_id
    assert bundle.input_hash == result.receipt.input_hash
    assert bundle.output_hash == result.receipt.output_hash
    assert bundle.evidence_refs == result.receipt.evidence_refs
    assert bundle.exported_at == "2026-04-29T12:00:00+00:00"


def test_governed_mcp_executor_rejects_missing_evidence_bundle_command() -> None:
    executor = GovernedMCPExecutor(StubMCPClient(MCPToolCallResult(content={})))

    with pytest.raises(KeyError, match="MCP execution audit not found"):
        executor.export_evidence_bundle(command_id="missing-command")

    with pytest.raises(ValueError, match="command_id is required"):
        executor.export_evidence_bundle(command_id="")


def test_jsonl_mcp_execution_audit_store_round_trips_records(tmp_path) -> None:
    audit_path = tmp_path / "mcp" / "execution_audits.jsonl"
    store = JsonlMCPExecutionAuditStore(audit_path)
    executor = GovernedMCPExecutor(
        StubMCPClient(MCPToolCallResult(content={"ok": True})),
        audit_store=store,
        clock=lambda: "2026-04-29T12:00:00+00:00",
    )

    first = executor.execute(
        capability=_certified(),
        context=_context(command_id="cmd-jsonl-1"),
        params={"title": "First durable audit"},
    )
    second = executor.execute(
        capability=_certified(),
        context=_context(command_id="cmd-jsonl-2"),
        params={"title": "Second durable audit"},
    )
    reopened_store = JsonlMCPExecutionAuditStore(audit_path)

    records = reopened_store.list(limit=2)
    filtered = reopened_store.list(command_id="cmd-jsonl-1", status="succeeded")

    assert audit_path.exists()
    assert len(audit_path.read_text(encoding="utf-8").splitlines()) == 2
    assert len(records) == 2
    assert records[0].command_id == "cmd-jsonl-2"
    assert records[0].receipt_id == second.receipt.receipt_id
    assert records[1].command_id == "cmd-jsonl-1"
    assert len(filtered) == 1
    assert filtered[0].receipt_id == first.receipt.receipt_id
    assert filtered[0].evidence_refs == first.receipt.evidence_refs


def test_jsonl_mcp_execution_audit_store_rejects_malformed_record(tmp_path) -> None:
    audit_path = tmp_path / "bad_audits.jsonl"
    audit_path.write_text(
        json.dumps({
            "audit_id": "audit-1",
            "capability_id": "mcp.docs_search_docs",
            "command_id": "cmd-1",
            "status": "succeeded",
            "reason": "mcp_tool_call_succeeded",
            "audited_at": "2026-04-29T12:00:00+00:00",
            "evidence_refs": [17],
        }),
        encoding="utf-8",
    )
    store = JsonlMCPExecutionAuditStore(audit_path)

    with pytest.raises(ValueError, match="invalid MCP execution audit JSONL record"):
        store.list()

    assert audit_path.exists()
    assert "mcp.docs_search_docs" in audit_path.read_text(encoding="utf-8")
    assert store.path == audit_path


def test_build_mcp_execution_audit_store_from_env_selects_durable_store(tmp_path) -> None:
    audit_path = tmp_path / "env_audits.jsonl"

    durable = build_mcp_execution_audit_store_from_env({
        "MULLU_MCP_EXECUTION_AUDIT_LOG_PATH": str(audit_path),
    })
    volatile = build_mcp_execution_audit_store_from_env({})

    with pytest.raises(ValueError, match="MCP execution audit store path is required"):
        JsonlMCPExecutionAuditStore(" ")

    assert isinstance(durable, JsonlMCPExecutionAuditStore)
    assert durable.path == audit_path
    assert isinstance(volatile, InMemoryMCPExecutionAuditStore)
    assert volatile.list() == ()
