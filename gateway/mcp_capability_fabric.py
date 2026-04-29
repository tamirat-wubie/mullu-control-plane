"""Gateway MCP Capability Fabric - governed MCP admission helpers.

Purpose: Convert externally described MCP tools into explicitly certified
    gateway capability fabric entries and install them into command admission.
Governance scope: MCP import certification, MCP domain capsule construction,
    and command admission gate creation.
Dependencies: gateway capability fabric loader and MCP capability bridge.
Invariants:
  - MCP tools are not executable until a certified registry entry is produced.
  - Installed MCP capabilities are admitted through the same gate as native domains.
  - The MCP domain capsule references only the supplied capability entries.
  - Certification provenance is recorded in capability metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from gateway.authority_obligation_mesh import ApprovalPolicy, EscalationPolicy, TeamOwnership
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
    DomainCapsule,
    DomainCapsuleCertificationStatus,
)
from mcoi_runtime.core.command_capability_admission import CommandCapabilityAdmissionGate
from mcoi_runtime.mcp.capability_bridge import MCPToolDescriptor, import_mcp_tool_as_capability

from gateway.capability_fabric import build_capability_admission_gate


@dataclass(frozen=True, slots=True)
class MCPAuthorityRecords:
    """Authority-obligation records required to activate certified MCP capabilities."""

    ownership: tuple[TeamOwnership, ...]
    approval_policies: tuple[ApprovalPolicy, ...]
    escalation_policies: tuple[EscalationPolicy, ...]


def certify_mcp_capability_entry(
    entry: CapabilityRegistryEntry,
    *,
    certified_by: str,
    certification_evidence_ref: str,
) -> CapabilityRegistryEntry:
    """Return a certified MCP capability entry with explicit provenance."""
    if entry.domain != "mcp":
        raise ValueError("only mcp capability entries can be certified by this helper")
    if not certified_by.strip():
        raise ValueError("certified_by is required")
    if not certification_evidence_ref.strip():
        raise ValueError("certification_evidence_ref is required")
    metadata = {
        **dict(entry.metadata),
        "certified_by": certified_by,
        "certification_evidence_ref": certification_evidence_ref,
    }
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
        metadata=metadata,
        extensions=entry.extensions,
    )


def build_mcp_domain_capsule(
    entries: tuple[CapabilityRegistryEntry, ...],
    *,
    capsule_id: str = "mcp.imported_tools.v0",
    owner_team: str = "integrations",
) -> DomainCapsule:
    """Build the MCP domain capsule for supplied certified capability entries."""
    if not entries:
        raise ValueError("at least one MCP capability entry is required")
    for entry in entries:
        if entry.domain != "mcp":
            raise ValueError("MCP domain capsule can only reference mcp capabilities")
        if entry.certification_status is not CapabilityCertificationStatus.CERTIFIED:
            raise ValueError("MCP domain capsule requires certified capabilities")
    capability_refs = tuple(entry.capability_id for entry in entries)
    return DomainCapsule(
        capsule_id=capsule_id,
        domain="mcp",
        version="0.1.0",
        ontology_refs=("ontologies/mcp/imported_tools.json",),
        capability_refs=capability_refs,
        policy_refs=("policies/mcp/imported_tools.policy.json",),
        evidence_rules=("evidence/mcp/imported_tools.evidence.json",),
        approval_rules=("approval/mcp/imported_tools.approval.json",),
        recovery_rules=("recovery/mcp/imported_tools.recovery.json",),
        test_fixture_refs=("tests/fixtures/mcp/imported_tools",),
        read_model_refs=("read_models/mcp/imported_tools.json",),
        operator_view_refs=("operator_views/mcp/imported_tools.json",),
        owner_team=owner_team,
        certification_status=DomainCapsuleCertificationStatus.CERTIFIED,
        metadata={"source": "mcp.import_tool"},
    )


def build_mcp_capability_admission_gate(
    *,
    entries: tuple[CapabilityRegistryEntry, ...],
    clock: Callable[[], str],
    capsule_id: str = "mcp.imported_tools.v0",
    owner_team: str = "integrations",
) -> CommandCapabilityAdmissionGate:
    """Build a command admission gate for certified MCP capability entries."""
    capsule = build_mcp_domain_capsule(entries, capsule_id=capsule_id, owner_team=owner_team)
    return build_capability_admission_gate(
        capsules=(capsule,),
        capabilities=entries,
        require_certified=True,
        clock=clock,
    )


def import_certified_mcp_tools_as_admission_gate(
    tools: tuple[MCPToolDescriptor, ...],
    *,
    clock: Callable[[], str],
    certified_by: str,
    certification_evidence_ref: str,
    owner_team: str = "integrations",
) -> CommandCapabilityAdmissionGate:
    """Import, certify, and install MCP tools into command admission."""
    entries = tuple(
        certify_mcp_capability_entry(
            import_mcp_tool_as_capability(tool, owner_team=owner_team),
            certified_by=certified_by,
            certification_evidence_ref=certification_evidence_ref,
        )
        for tool in tools
    )
    return build_mcp_capability_admission_gate(
        entries=entries,
        clock=clock,
        owner_team=owner_team,
    )


def build_mcp_authority_records(
    entries: tuple[CapabilityRegistryEntry, ...],
    *,
    tenant_id: str,
    primary_owner_id: str,
    fallback_owner_id: str,
    escalation_team: str,
    timeout_seconds: int = 300,
) -> MCPAuthorityRecords:
    """Derive authority-obligation records for certified MCP capabilities."""
    tenant = tenant_id.strip()
    primary_owner = primary_owner_id.strip()
    fallback_owner = fallback_owner_id.strip()
    escalation = escalation_team.strip()
    if not tenant:
        raise ValueError("tenant_id is required")
    if not primary_owner:
        raise ValueError("primary_owner_id is required")
    if not fallback_owner:
        raise ValueError("fallback_owner_id is required")
    if not escalation:
        raise ValueError("escalation_team is required")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")

    ownership: list[TeamOwnership] = []
    approval_policies: list[ApprovalPolicy] = []
    for entry in entries:
        _validate_certified_mcp_entry(entry)
        owner_team = entry.obligation_model.owner_team.strip()
        if not owner_team:
            raise ValueError("MCP capability owner_team is required")
        risk_tier = str(entry.metadata.get("risk_tier", "medium")).strip().lower()
        if risk_tier not in {"low", "medium", "high"}:
            raise ValueError("MCP capability risk_tier must be low, medium, or high")
        required_approver_count = _required_approver_count(entry, risk_tier)
        ownership.append(TeamOwnership(
            tenant_id=tenant,
            resource_ref=entry.capability_id,
            owner_team=owner_team,
            primary_owner_id=primary_owner,
            fallback_owner_id=fallback_owner,
            escalation_team=escalation,
        ))
        approval_policies.append(ApprovalPolicy(
            policy_id=_mcp_policy_id(entry.capability_id, risk_tier),
            tenant_id=tenant,
            capability=entry.capability_id,
            risk_tier=risk_tier,
            required_roles=entry.authority_policy.required_roles,
            required_approver_count=required_approver_count,
            separation_of_duty=entry.authority_policy.separation_of_duty,
            timeout_seconds=timeout_seconds,
            escalation_policy_id=_mcp_escalation_policy_id(tenant),
        ))

    escalation_policy = EscalationPolicy(
        policy_id=_mcp_escalation_policy_id(tenant),
        tenant_id=tenant,
        notify_after_seconds=timeout_seconds,
        escalate_after_seconds=timeout_seconds * 2,
        incident_after_seconds=timeout_seconds * 8,
        fallback_owner_id=fallback_owner,
        escalation_team=escalation,
    )
    return MCPAuthorityRecords(
        ownership=tuple(ownership),
        approval_policies=tuple(approval_policies),
        escalation_policies=(escalation_policy,),
    )


def _validate_certified_mcp_entry(entry: CapabilityRegistryEntry) -> None:
    if entry.domain != "mcp":
        raise ValueError("only mcp capability entries can be bound to MCP authority records")
    if entry.certification_status is not CapabilityCertificationStatus.CERTIFIED:
        raise ValueError("MCP authority records require certified capabilities")


def _required_approver_count(entry: CapabilityRegistryEntry, risk_tier: str) -> int:
    if entry.authority_policy.approval_chain:
        return len(entry.authority_policy.approval_chain)
    if risk_tier == "low":
        return 0
    return 2 if risk_tier == "high" and entry.authority_policy.separation_of_duty else 1


def _mcp_policy_id(capability_id: str, risk_tier: str) -> str:
    normalized = capability_id.replace(".", "-").replace("_", "-")
    return f"mcp-approval-{normalized}-{risk_tier}"


def _mcp_escalation_policy_id(tenant_id: str) -> str:
    normalized = tenant_id.replace(".", "-").replace("_", "-")
    return f"mcp-escalation-{normalized}"
