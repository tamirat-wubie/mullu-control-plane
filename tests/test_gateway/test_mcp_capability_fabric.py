"""Gateway MCP capability fabric tests.

Tests: MCP capability import certification, MCP domain capsule admission, and
    end-to-end router execution through command fabric admission.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.capability_dispatch import CapabilityDispatcher  # noqa: E402
from gateway.command_spine import CommandLedger  # noqa: E402
from gateway.mcp_capabilities import register_mcp_capabilities  # noqa: E402
from gateway.mcp_capability_fabric import (  # noqa: E402
    build_mcp_capability_admission_gate,
    build_mcp_authority_records,
    build_mcp_domain_capsule,
    certify_mcp_capability_entry,
    import_certified_mcp_tools_as_admission_gate,
)
from gateway.router import GatewayMessage, GatewayRouter, TenantMapping  # noqa: E402
from mcoi_runtime.mcp import (  # noqa: E402
    GovernedMCPExecutor,
    MCPToolCallResult,
    MCPToolDescriptor,
    import_mcp_tool_as_capability,
)


def _clock() -> str:
    return "2026-04-29T12:00:00+00:00"


class StubPlatform:
    """Minimal platform stub; MCP router tests should not call fallback LLM."""

    def connect(self, *, identity_id: str, tenant_id: str):
        return StubSession()


class StubSession:
    def llm(self, prompt, **kwargs):
        raise AssertionError("MCP capability should dispatch before conversational fallback")

    def close(self):
        return None


class StubMCPClient:
    """MCP client fixture that records exact governed tool calls."""

    def __init__(self) -> None:
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
        return MCPToolCallResult(
            content={"result": "policy document"},
            metadata={"provider_request_id": "mcp-provider-1"},
        )


def _read_only_tool() -> MCPToolDescriptor:
    return MCPToolDescriptor(
        server_id="Docs",
        name="Search Docs",
        description="Search internal documents.",
        input_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        annotations={"read_only": True},
    )


def test_mcp_capability_admission_gate_requires_certified_entries() -> None:
    candidate = import_mcp_tool_as_capability(_read_only_tool())

    with pytest.raises(ValueError, match="requires certified capabilities"):
        build_mcp_domain_capsule((candidate,))

    certified = certify_mcp_capability_entry(
        candidate,
        certified_by="operator-1",
        certification_evidence_ref="evidence:mcp-docs-search",
    )
    gate = build_mcp_capability_admission_gate(entries=(certified,), clock=_clock)
    decision = gate.admit(command_id="cmd-1", intent_name=certified.capability_id)

    assert certified.certification_status.value == "certified"
    assert certified.metadata["certified_by"] == "operator-1"
    assert decision.status.value == "accepted"
    assert decision.capability_id == "mcp.docs_search_docs"
    assert gate.read_model()["domains"][0]["domain"] == "mcp"


def test_import_certified_mcp_tools_builds_gateway_admission_gate() -> None:
    gate = import_certified_mcp_tools_as_admission_gate(
        (_read_only_tool(),),
        clock=_clock,
        certified_by="operator-1",
        certification_evidence_ref="evidence:mcp-docs-search",
        owner_team="knowledge-ops",
    )

    decision = gate.admit(command_id="cmd-1", intent_name="mcp.docs_search_docs")

    assert decision.status.value == "accepted"
    assert decision.domain == "mcp"
    assert decision.owner_team == "knowledge-ops"
    assert "tool_call_receipt" in decision.evidence_required


def test_build_mcp_authority_records_binds_certified_capabilities_to_mesh() -> None:
    candidate = import_mcp_tool_as_capability(
        _read_only_tool(),
        owner_team="knowledge-ops",
        required_roles=("knowledge_operator",),
    )
    certified = certify_mcp_capability_entry(
        candidate,
        certified_by="operator-1",
        certification_evidence_ref="evidence:mcp-docs-search",
    )

    records = build_mcp_authority_records(
        (certified,),
        tenant_id="tenant-1",
        primary_owner_id="owner-1",
        fallback_owner_id="owner-2",
        escalation_team="platform-ops",
        timeout_seconds=600,
    )

    assert records.ownership[0].tenant_id == "tenant-1"
    assert records.ownership[0].resource_ref == "mcp.docs_search_docs"
    assert records.ownership[0].owner_team == "knowledge-ops"
    assert records.approval_policies[0].capability == "mcp.docs_search_docs"
    assert records.approval_policies[0].risk_tier == "low"
    assert records.approval_policies[0].required_approver_count == 0
    assert records.approval_policies[0].required_roles == ("knowledge_operator",)
    assert records.escalation_policies[0].policy_id == "mcp-escalation-tenant-1"
    assert records.escalation_policies[0].fallback_owner_id == "owner-2"


def test_build_mcp_authority_records_requires_certified_entries() -> None:
    candidate = import_mcp_tool_as_capability(_read_only_tool())

    with pytest.raises(ValueError, match="require certified capabilities"):
        build_mcp_authority_records(
            (candidate,),
            tenant_id="tenant-1",
            primary_owner_id="owner-1",
            fallback_owner_id="owner-2",
            escalation_team="platform-ops",
        )

    assert candidate.certification_status.value == "candidate"
    assert candidate.domain == "mcp"


def test_router_executes_certified_mcp_capability_through_fabric_admission() -> None:
    candidate = import_mcp_tool_as_capability(_read_only_tool(), owner_team="knowledge-ops")
    certified = certify_mcp_capability_entry(
        candidate,
        certified_by="operator-1",
        certification_evidence_ref="evidence:mcp-docs-search",
    )
    gate = build_mcp_capability_admission_gate(entries=(certified,), clock=_clock)
    client = StubMCPClient()
    executor = GovernedMCPExecutor(client, clock=_clock)
    dispatcher = CapabilityDispatcher()
    register_mcp_capabilities(dispatcher, capabilities=(certified,), executor=executor)
    router = GatewayRouter(
        platform=StubPlatform(),
        skill_dispatcher=dispatcher,
        command_ledger=CommandLedger(clock=_clock, capability_admission_gate=gate),
        clock=_clock,
    )
    router.register_tenant_mapping(TenantMapping(
        channel="test",
        sender_id="user1",
        tenant_id="tenant-1",
        identity_id="identity-1",
    ))

    response = router.handle_message(GatewayMessage(
        message_id="msg-mcp-1",
        channel="test",
        sender_id="user1",
        body='/run mcp.docs_search_docs {"query": "policy"}',
        conversation_id="conversation-1",
    ))

    assert response.body == "MCP capability executed."
    assert response.metadata["capability_id"] == "mcp.docs_search_docs"
    assert response.metadata["mcp_succeeded"] is True
    assert response.metadata["mcp_output"] == {"result": "policy document"}
    assert response.metadata["mcp_execution_receipt"]["command_id"] == response.metadata["command_id"]
    assert response.metadata["mcp_execution_receipt"]["approval_id"].startswith("apr-")
    assert response.metadata["mcp_execution_receipt"]["budget_reservation_id"].startswith("budget-reservation-")
    assert response.metadata["mcp_execution_receipt"]["isolation_boundary_id"].startswith("isolation-boundary-")
    assert response.metadata["closure_disposition"] == "committed"
    assert client.calls == [{
        "server_id": "Docs",
        "tool_name": "Search Docs",
        "arguments": {"query": "policy"},
    }]
