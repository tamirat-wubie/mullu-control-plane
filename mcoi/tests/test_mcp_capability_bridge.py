"""Purpose: validate MCP tool import/export governed capability bridge.
Governance scope: capability identity, candidate admission contracts,
certified export gating, and MCP descriptor preservation.
Dependencies: mcoi_runtime.mcp.capability_bridge and governed capability
fabric contracts.
Invariants:
  - Imported MCP tools become candidate capability registry entries.
  - Imported tools carry authority, evidence, isolation, recovery, cost, and obligations.
  - Exported MCP tools require certified Mullu capability entries.
"""

from __future__ import annotations

import pytest

from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
)
from mcoi_runtime.mcp.capability_bridge import (
    MCPToolDescriptor,
    export_capability_as_mcp_tool,
    import_mcp_tool_as_capability,
    mcp_capability_id,
)


def _tool_descriptor(**overrides) -> MCPToolDescriptor:
    payload = {
        "server_id": "GitHub Enterprise",
        "name": "Create Issue",
        "description": "Create a repository issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string"},
                "title": {"type": "string"},
            },
            "required": ["repo", "title"],
        },
        "annotations": {},
    }
    payload.update(overrides)
    return MCPToolDescriptor(**payload)


def _certified(entry: CapabilityRegistryEntry) -> CapabilityRegistryEntry:
    return CapabilityRegistryEntry(
        capability_id=entry.capability_id,
        domain=entry.domain,
        version=entry.version,
        input_schema_ref=entry.input_schema_ref,
        output_schema_ref=entry.output_schema_ref,
        effect_model=entry.effect_model,
        evidence_model=entry.evidence_model,
        authority_policy=entry.authority_policy,
        isolation_profile=entry.isolation_profile,
        recovery_plan=entry.recovery_plan,
        cost_model=entry.cost_model,
        obligation_model=entry.obligation_model,
        certification_status=CapabilityCertificationStatus.CERTIFIED,
        metadata=entry.metadata,
        extensions=entry.extensions,
    )


def test_import_mcp_tool_creates_candidate_capability_contract() -> None:
    entry = import_mcp_tool_as_capability(
        _tool_descriptor(),
        owner_team="devops",
        required_roles=("developer",),
    )

    assert entry.capability_id == "mcp.github_enterprise_create_issue"
    assert entry.domain == "mcp"
    assert entry.certification_status is CapabilityCertificationStatus.CANDIDATE
    assert entry.authority_policy.required_roles == ("developer",)
    assert entry.evidence_model.terminal_certificate_required is True
    assert "tool_call_receipt" in entry.evidence_model.required_evidence
    assert entry.effect_model.reconciliation_required is True
    assert entry.isolation_profile.execution_plane == "external_mcp_server"
    assert entry.recovery_plan.review_required_on_failure is True
    assert entry.recovery_plan.compensation_capability == "mcp.operator_review_compensation"
    assert entry.obligation_model.owner_team == "devops"
    assert entry.metadata["source"] == "mcp.import_tool"
    assert entry.extensions["governed_record"]["read_only"] is False
    assert entry.extensions["governed_record"]["world_mutating"] is True
    assert entry.extensions["governed_record"]["requires_approval"] is True
    assert entry.extensions["governed_record"]["requires_sandbox"] is True
    assert entry.extensions["governed_record"]["allowed_roles"] == ("developer",)
    assert entry.extensions["governed_record"]["allowed_tools"] == ("governed_mcp_executor.execute",)
    assert entry.extensions["governed_record"]["rollback_or_compensation_required"] is True
    assert entry.extensions["mcp"]["tool_name"] == "Create Issue"


def test_import_mcp_tool_classifies_read_only_and_high_risk_effects() -> None:
    read_only = import_mcp_tool_as_capability(
        _tool_descriptor(
            name="Search Docs",
            annotations={"read_only": True},
        )
    )
    high_risk = import_mcp_tool_as_capability(
        _tool_descriptor(
            name="Send Email",
            annotations={
                "expected_effects": ["external_email_sent"],
                "network_allowlist": "mail.example.com",
            },
        )
    )

    assert read_only.metadata["risk_tier"] == "low"
    assert read_only.effect_model.expected_effects == ("external_context_read",)
    assert read_only.effect_model.reconciliation_required is False
    assert read_only.authority_policy.separation_of_duty is False
    assert read_only.recovery_plan.compensation_capability == ""
    assert read_only.extensions["governed_record"]["read_only"] is True
    assert read_only.extensions["governed_record"]["requires_approval"] is False
    assert read_only.extensions["governed_record"]["requires_sandbox"] is True
    assert high_risk.metadata["risk_tier"] == "high"
    assert high_risk.effect_model.expected_effects == ("external_email_sent",)
    assert high_risk.authority_policy.separation_of_duty is True
    assert high_risk.isolation_profile.network_allowlist == ("mail.example.com",)
    assert high_risk.extensions["governed_record"]["allowed_networks"] == ("mail.example.com",)
    assert high_risk.extensions["governed_record"]["requires_approval"] is True


def test_export_rejects_uncertified_capability() -> None:
    entry = import_mcp_tool_as_capability(_tool_descriptor())

    with pytest.raises(ValueError, match="only certified capabilities"):
        export_capability_as_mcp_tool(entry)

    assert entry.certification_status is CapabilityCertificationStatus.CANDIDATE
    assert entry.capability_id == "mcp.github_enterprise_create_issue"


def test_export_certified_capability_as_mcp_tool_preserves_schema() -> None:
    entry = _certified(import_mcp_tool_as_capability(_tool_descriptor()))

    exported = export_capability_as_mcp_tool(entry)

    assert exported.name == "mullu_mcp_github_enterprise_create_issue"
    assert exported.description == "Create a repository issue."
    assert exported.input_schema["required"] == ["repo", "title"]
    assert exported.metadata["capability_id"] == entry.capability_id
    assert exported.metadata["terminal_certificate_required"] is True
    assert exported.metadata["evidence_required"] == list(entry.evidence_model.required_evidence)


def test_mcp_capability_id_is_deterministic_and_bounded() -> None:
    first = mcp_capability_id("GitHub Enterprise", "Create Issue")
    second = mcp_capability_id("github---enterprise", "create   issue")

    assert first == "mcp.github_enterprise_create_issue"
    assert second == first
    assert "." in first
