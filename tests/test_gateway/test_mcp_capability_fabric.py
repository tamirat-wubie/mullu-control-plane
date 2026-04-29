"""Gateway MCP capability fabric tests.

Tests: MCP capability import certification, MCP domain capsule admission, and
    end-to-end router execution through command fabric admission.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

import pytest
from fastapi.testclient import TestClient

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from gateway.authority_obligation_mesh import ApprovalChainStatus, AuthorityObligationMesh  # noqa: E402
from gateway.capability_dispatch import CapabilityDispatcher  # noqa: E402
from gateway.command_spine import CommandLedger  # noqa: E402
from gateway.mcp_capabilities import register_mcp_capabilities  # noqa: E402
from gateway.mcp_capability_fabric import (  # noqa: E402
    build_mcp_capability_admission_gate,
    build_mcp_authority_records,
    build_mcp_gateway_import_from_manifest,
    build_mcp_domain_capsule,
    certify_mcp_capability_entry,
    import_certified_mcp_tools_as_admission_gate,
    install_mcp_authority_records,
)
from gateway.mcp_operator_read_model import build_mcp_operator_read_model  # noqa: E402
from gateway.router import GatewayMessage, GatewayRouter, TenantMapping  # noqa: E402
from gateway.server import create_gateway_app  # noqa: E402
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


def _email_tool() -> MCPToolDescriptor:
    return MCPToolDescriptor(
        server_id="Mail",
        name="Send Email",
        description="Send outbound email.",
        input_schema={
            "type": "object",
            "properties": {"subject": {"type": "string"}, "body": {"type": "string"}},
            "required": ["subject", "body"],
        },
        annotations={
            "expected_effects": ["external_email_sent"],
            "network_allowlist": "mail.example.com",
        },
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

    with pytest.raises(ValueError, match="at least one MCP capability entry"):
        build_mcp_authority_records(
            (),
            tenant_id="tenant-1",
            primary_owner_id="owner-1",
            fallback_owner_id="owner-2",
            escalation_team="platform-ops",
        )

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


def test_build_mcp_authority_records_requires_dual_approval_for_high_risk() -> None:
    certified = certify_mcp_capability_entry(
        import_mcp_tool_as_capability(_email_tool(), owner_team="mail-ops"),
        certified_by="operator-1",
        certification_evidence_ref="evidence:mcp-mail-send",
    )

    records = build_mcp_authority_records(
        (certified,),
        tenant_id="tenant-1",
        primary_owner_id="owner-1",
        fallback_owner_id="owner-2",
        escalation_team="security-ops",
        timeout_seconds=120,
    )

    assert records.ownership[0].owner_team == "mail-ops"
    assert records.approval_policies[0].risk_tier == "high"
    assert records.approval_policies[0].required_approver_count == 2
    assert records.approval_policies[0].separation_of_duty is True
    assert records.escalation_policies[0].incident_after_seconds == 960


def test_install_mcp_authority_records_registers_mesh_policy() -> None:
    ledger = CommandLedger(clock=_clock)
    mesh = AuthorityObligationMesh(commands=ledger, clock=_clock)
    certified = certify_mcp_capability_entry(
        import_mcp_tool_as_capability(_email_tool(), owner_team="mail-ops"),
        certified_by="operator-1",
        certification_evidence_ref="evidence:mcp-mail-send",
    )
    records = build_mcp_authority_records(
        (certified,),
        tenant_id="tenant-1",
        primary_owner_id="owner-1",
        fallback_owner_id="owner-2",
        escalation_team="security-ops",
    )

    installed = install_mcp_authority_records(mesh, records)

    assert installed == records
    assert mesh.responsibility_witness().open_obligation_count == 0
    assert mesh.summary()["ownership_bindings"] == 1
    assert mesh.summary()["approval_policies"] == 1


def test_build_mcp_gateway_import_from_manifest_builds_admission_and_authority(tmp_path: Path) -> None:
    manifest_path = _write_mcp_manifest(tmp_path)

    imported = build_mcp_gateway_import_from_manifest(manifest_path, clock=_clock)
    decision = imported.admission_gate.admit(command_id="cmd-1", intent_name="mcp.docs_search_docs")

    assert imported.manifest_ref == manifest_path.resolve().as_uri()
    assert imported.entries[0].capability_id == "mcp.docs_search_docs"
    assert imported.authority_records.ownership[0].resource_ref == "mcp.docs_search_docs"
    assert imported.authority_records.approval_policies[0].required_roles == ("knowledge_operator",)
    assert decision.status.value == "accepted"
    assert decision.owner_team == "knowledge-ops"


def test_build_mcp_gateway_import_rejects_invalid_manifest_without_reflection(tmp_path: Path) -> None:
    missing_string_path = tmp_path / "missing_string_manifest.json"
    missing_string_path.write_text(
        json.dumps({
            "tools": [{
                "server_id": "Docs",
                "name": "Search Docs",
                "description": "Search internal documents.",
                "input_schema": {"type": "object"},
            }]
        }),
        encoding="utf-8",
    )
    invalid_tool_path = tmp_path / "invalid_tool_manifest.json"
    invalid_tool_path.write_text(json.dumps({"tools": [[]]}), encoding="utf-8")

    with pytest.raises(ValueError, match="MCP manifest requires a configured string field"):
        build_mcp_gateway_import_from_manifest(missing_string_path, clock=_clock)

    with pytest.raises(ValueError, match="MCP manifest tool entry must be an object"):
        build_mcp_gateway_import_from_manifest(invalid_tool_path, clock=_clock)

    assert missing_string_path.exists()
    assert invalid_tool_path.exists()


def test_gateway_startup_imports_mcp_manifest_authority_records(tmp_path: Path, monkeypatch) -> None:
    manifest_path = _write_mcp_manifest(tmp_path)
    monkeypatch.setenv("MULLU_MCP_CAPABILITY_MANIFEST_PATH", str(manifest_path))
    monkeypatch.delenv("MULLU_CAPABILITY_FABRIC_ADMISSION_ENABLED", raising=False)

    app = create_gateway_app(platform=StubPlatform())
    decision = app.state.capability_admission_gate.admit(
        command_id="cmd-1",
        intent_name="mcp.docs_search_docs",
    )
    summary = app.state.authority_obligation_mesh.summary()

    assert app.state.mcp_gateway_import is not None
    assert app.state.mcp_capability_entries[0].capability_id == "mcp.docs_search_docs"
    assert app.state.mcp_authority_records.ownership[0].owner_team == "knowledge-ops"
    assert decision.status.value == "accepted"
    assert summary["ownership_bindings"] == 1
    assert summary["approval_policies"] == 1
    assert summary["escalation_policies"] == 1


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


def test_router_installs_mcp_authority_records_and_waits_for_high_risk_quorum() -> None:
    certified = certify_mcp_capability_entry(
        import_mcp_tool_as_capability(_email_tool(), owner_team="mail-ops"),
        certified_by="operator-1",
        certification_evidence_ref="evidence:mcp-mail-send",
    )
    gate = build_mcp_capability_admission_gate(entries=(certified,), clock=_clock)
    records = build_mcp_authority_records(
        (certified,),
        tenant_id="tenant-1",
        primary_owner_id="owner-1",
        fallback_owner_id="owner-2",
        escalation_team="security-ops",
    )
    client = StubMCPClient()
    dispatcher = CapabilityDispatcher()
    register_mcp_capabilities(
        dispatcher,
        capabilities=(certified,),
        executor=GovernedMCPExecutor(client, clock=_clock),
    )
    ledger = CommandLedger(clock=_clock, capability_admission_gate=gate)
    mesh = AuthorityObligationMesh(commands=ledger, clock=_clock)
    router = GatewayRouter(
        platform=StubPlatform(),
        skill_dispatcher=dispatcher,
        command_ledger=ledger,
        authority_obligation_mesh=mesh,
        mcp_authority_records=records,
        clock=_clock,
    )
    router.register_tenant_mapping(TenantMapping(
        channel="test",
        sender_id="requester",
        tenant_id="tenant-1",
        identity_id="identity-1",
    ))

    pending = router.handle_message(GatewayMessage(
        message_id="msg-mcp-mail-1",
        channel="test",
        sender_id="requester",
        body='/run mcp.mail_send_email {"subject": "Hi", "body": "please send_email now"}',
    ))
    chain = mesh.approval_chain_for(pending.metadata["command_id"])

    assert pending.metadata["approval_required"] is True
    assert pending.metadata["request_id"].startswith("apr-")
    assert chain is not None
    assert chain.status is ApprovalChainStatus.PENDING
    assert chain.required_approver_count == 2
    assert chain.required_roles == ("operator",)
    assert mesh.responsibility_witness().pending_approval_chain_count == 1
    assert client.calls == []


def _write_mcp_manifest(tmp_path: Path) -> Path:
    manifest_path = tmp_path / "mcp_manifest.json"
    manifest_path.write_text(
        json.dumps({
            "tenant_id": "tenant-1",
            "primary_owner_id": "owner-1",
            "fallback_owner_id": "owner-2",
            "escalation_team": "platform-ops",
            "certified_by": "operator-1",
            "certification_evidence_ref": "evidence:mcp-docs-search",
            "owner_team": "knowledge-ops",
            "timeout_seconds": 600,
            "tools": [
                {
                    "server_id": "Docs",
                    "name": "Search Docs",
                    "description": "Search internal documents.",
                    "input_schema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                    "annotations": {"read_only": True},
                    "required_roles": ["knowledge_operator"],
                    "owner_team": "knowledge-ops",
                },
            ],
        }),
        encoding="utf-8",
    )
    return manifest_path


def test_mcp_operator_read_model_projects_capability_authority_and_audits() -> None:
    certified = certify_mcp_capability_entry(
        import_mcp_tool_as_capability(_read_only_tool(), owner_team="knowledge-ops"),
        certified_by="operator-1",
        certification_evidence_ref="evidence:mcp-docs-search",
    )
    gate = build_mcp_capability_admission_gate(entries=(certified,), clock=_clock)
    records = build_mcp_authority_records(
        (certified,),
        tenant_id="tenant-1",
        primary_owner_id="owner-1",
        fallback_owner_id="owner-2",
        escalation_team="platform-ops",
    )
    ledger = CommandLedger(clock=_clock, capability_admission_gate=gate)
    mesh = AuthorityObligationMesh(commands=ledger, clock=_clock)
    install_mcp_authority_records(mesh, records)
    client = StubMCPClient()
    executor = GovernedMCPExecutor(client, clock=_clock)
    dispatcher = CapabilityDispatcher()
    register_mcp_capabilities(dispatcher, capabilities=(certified,), executor=executor)
    router = GatewayRouter(
        platform=StubPlatform(),
        skill_dispatcher=dispatcher,
        command_ledger=ledger,
        authority_obligation_mesh=mesh,
        clock=_clock,
    )
    router.register_tenant_mapping(TenantMapping(
        channel="test",
        sender_id="user1",
        tenant_id="tenant-1",
        identity_id="identity-1",
    ))
    router.handle_message(GatewayMessage(
        message_id="msg-mcp-read-model-1",
        channel="test",
        sender_id="user1",
        body='/run mcp.docs_search_docs {"query": "policy"}',
    ))

    read_model = build_mcp_operator_read_model(
        capability_admission_gate=gate,
        authority_mesh_store=mesh._store,
        mcp_executor=executor,
        audit_limit=1,
    )

    assert read_model["enabled"] is True
    assert read_model["executor_enabled"] is True
    assert read_model["capability_count"] == 1
    assert read_model["capabilities"][0]["capability_id"] == "mcp.docs_search_docs"
    assert read_model["ownership"][0]["owner_team"] == "knowledge-ops"
    assert read_model["approval_policies"][0]["capability"] == "mcp.docs_search_docs"
    assert read_model["execution_audit_count"] == 1
    assert read_model["execution_audits"][0]["status"] == "succeeded"
    assert read_model["execution_audit_page"]["limit"] == 1


def test_mcp_operator_read_model_endpoint_reports_runtime_state() -> None:
    certified = certify_mcp_capability_entry(
        import_mcp_tool_as_capability(_read_only_tool(), owner_team="knowledge-ops"),
        certified_by="operator-1",
        certification_evidence_ref="evidence:mcp-docs-search",
    )
    gate = build_mcp_capability_admission_gate(entries=(certified,), clock=_clock)
    records = build_mcp_authority_records(
        (certified,),
        tenant_id="t1",
        primary_owner_id="owner-1",
        fallback_owner_id="owner-2",
        escalation_team="platform-ops",
    )
    mcp_client = StubMCPClient()
    executor = GovernedMCPExecutor(mcp_client, clock=_clock)
    app = create_gateway_app(
        platform=StubPlatform(),
        capability_admission_gate_override=gate,
        mcp_capability_entries=(certified,),
        mcp_executor=executor,
        mcp_authority_records=records,
    )
    app.state.router.register_tenant_mapping(TenantMapping(
        channel="web",
        sender_id="web-user",
        tenant_id="t1",
        identity_id="u1",
    ))
    http = TestClient(app)

    message_resp = http.post(
        "/webhook/web",
        content='{"body":"/run mcp.docs_search_docs {\\"query\\": \\"policy\\"}","user_id":"web-user"}',
        headers={"X-Session-Token": "mcp-read-model-token"},
    )
    command_id = message_resp.json()["metadata"]["command_id"]
    read_model_resp = http.get("/mcp/operator/read-model?audit_limit=1")
    filtered_resp = http.get("/mcp/operator/read-model?capability_id=mcp.docs_search_docs&audit_status=succeeded")
    evidence_bundle_resp = http.get(f"/mcp/operator/evidence-bundles/{command_id}")
    missing_bundle_resp = http.get("/mcp/operator/evidence-bundles/missing-command")

    assert message_resp.status_code == 200
    assert message_resp.json()["metadata"]["mcp_succeeded"] is True
    assert read_model_resp.status_code == 200
    assert read_model_resp.json()["capability_count"] == 1
    assert read_model_resp.json()["ownership_count"] == 1
    assert read_model_resp.json()["approval_policy_count"] == 1
    assert read_model_resp.json()["execution_audit_count"] == 1
    assert read_model_resp.json()["execution_audits"][0]["status"] == "succeeded"
    assert filtered_resp.json()["capability_filter"] == "mcp.docs_search_docs"
    assert filtered_resp.json()["execution_audit_status_filter"] == "succeeded"
    assert evidence_bundle_resp.status_code == 200
    assert evidence_bundle_resp.json()["bundle_id"].startswith("mcp-evidence-bundle-")
    assert evidence_bundle_resp.json()["command_id"] == command_id
    assert evidence_bundle_resp.json()["capability_id"] == "mcp.docs_search_docs"
    assert evidence_bundle_resp.json()["status"] == "succeeded"
    assert evidence_bundle_resp.json()["evidence_refs"]
    assert missing_bundle_resp.status_code == 404
