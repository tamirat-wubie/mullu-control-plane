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

from typing import Callable

from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityCertificationStatus,
    CapabilityRegistryEntry,
    DomainCapsule,
    DomainCapsuleCertificationStatus,
)
from mcoi_runtime.core.command_capability_admission import CommandCapabilityAdmissionGate
from mcoi_runtime.mcp.capability_bridge import MCPToolDescriptor, import_mcp_tool_as_capability

from gateway.capability_fabric import build_capability_admission_gate


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
