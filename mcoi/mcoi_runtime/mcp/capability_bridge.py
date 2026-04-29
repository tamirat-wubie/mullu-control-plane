"""Purpose: convert MCP tool descriptors into governed capability contracts.
Governance scope: MCP import/export typing, authority defaults, evidence
obligations, isolation metadata, and certification gates.
Dependencies: governed capability fabric contracts and deterministic text
canonicalization.
Invariants:
  - Imported MCP tools are candidate Mullu capabilities, never executable tools.
  - Exported MCP tools must come from certified Mullu capability entries.
  - Capability identity is deterministic from MCP server id and tool name.
  - Original MCP descriptors are preserved as extension evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Any, Mapping

from mcoi_runtime.contracts._base import thaw_value_json
from mcoi_runtime.contracts.governed_capability_fabric import (
    CapabilityAuthorityPolicy,
    CapabilityCertificationStatus,
    CapabilityCostModel,
    CapabilityEffectModel,
    CapabilityEvidenceModel,
    CapabilityIsolationProfile,
    CapabilityObligationModel,
    CapabilityRecoveryPlan,
    CapabilityRegistryEntry,
)


_DANGEROUS_EFFECTS = {
    "database_modified",
    "deployment_started",
    "external_email_sent",
    "file_written",
    "money_moved",
    "payment_created",
    "public_post_created",
    "secret_accessed",
    "user_deleted",
}


@dataclass(frozen=True, slots=True)
class MCPToolDescriptor:
    """Canonical MCP tool descriptor accepted by the bridge."""

    server_id: str
    name: str
    description: str
    input_schema: Mapping[str, Any]
    annotations: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.server_id.strip():
            raise ValueError("server_id is required")
        if not self.name.strip():
            raise ValueError("tool name is required")
        if not self.description.strip():
            raise ValueError("tool description is required")
        if not isinstance(self.input_schema, Mapping):
            raise ValueError("input_schema must be an object")
        if not isinstance(self.annotations, Mapping):
            raise ValueError("annotations must be an object")


@dataclass(frozen=True, slots=True)
class MCPToolExport:
    """MCP tool descriptor exported from a certified Mullu capability."""

    name: str
    description: str
    input_schema: dict[str, Any]
    metadata: dict[str, Any] = field(default_factory=dict)


def import_mcp_tool_as_capability(
    tool: MCPToolDescriptor,
    *,
    version: str = "0.1.0",
    owner_team: str = "integrations",
    required_roles: tuple[str, ...] = ("operator",),
    max_estimated_cost: float = 0.05,
) -> CapabilityRegistryEntry:
    """Convert one MCP tool into a governed candidate capability entry."""
    capability_id = mcp_capability_id(tool.server_id, tool.name)
    expected_effects = _expected_effects(tool)
    risk_tier = _risk_tier_for_effects(expected_effects, tool.annotations)
    return CapabilityRegistryEntry(
        capability_id=capability_id,
        domain="mcp",
        version=version,
        input_schema_ref=f"mcp://{_slug(tool.server_id)}/{_slug(tool.name)}/input.schema.json",
        output_schema_ref=f"mcp://{_slug(tool.server_id)}/{_slug(tool.name)}/output.schema.json",
        effect_model=CapabilityEffectModel(
            expected_effects=expected_effects,
            forbidden_effects=_forbidden_effects(expected_effects),
            reconciliation_required=True,
        ),
        evidence_model=CapabilityEvidenceModel(
            required_evidence=(
                "mcp_server_id",
                "mcp_tool_name",
                "input_hash",
                "output_hash",
                "tool_call_receipt",
            ),
            terminal_certificate_required=True,
        ),
        authority_policy=CapabilityAuthorityPolicy(
            required_roles=required_roles,
            approval_chain=(),
            separation_of_duty=risk_tier == "high",
        ),
        isolation_profile=CapabilityIsolationProfile(
            execution_plane="external_mcp_server",
            network_allowlist=_annotation_string_tuple(tool.annotations.get("network_allowlist", ())),
            secret_scope=f"mcp:{_slug(tool.server_id)}",
        ),
        recovery_plan=CapabilityRecoveryPlan(
            rollback_capability="",
            compensation_capability="",
            review_required_on_failure=True,
        ),
        cost_model=CapabilityCostModel(
            budget_class=f"mcp:{_slug(tool.server_id)}",
            max_estimated_cost=max_estimated_cost,
        ),
        obligation_model=CapabilityObligationModel(
            owner_team=owner_team,
            failure_due_seconds=3600,
            escalation_route=f"{owner_team}:mcp-review",
        ),
        certification_status=CapabilityCertificationStatus.CANDIDATE,
        metadata={
            "display_name": tool.name,
            "description": tool.description,
            "risk_tier": risk_tier,
            "source": "mcp.import_tool",
        },
        extensions={
            "mcp": {
                "server_id": tool.server_id,
                "tool_name": tool.name,
                "description": tool.description,
                "input_schema": dict(tool.input_schema),
                "annotations": dict(tool.annotations),
            },
        },
    )


def export_capability_as_mcp_tool(entry: CapabilityRegistryEntry) -> MCPToolExport:
    """Expose a certified Mullu capability as an MCP tool descriptor."""
    if entry.certification_status is not CapabilityCertificationStatus.CERTIFIED:
        raise ValueError("only certified capabilities can be exported as MCP tools")
    input_schema = _export_input_schema(entry)
    return MCPToolExport(
        name=_export_tool_name(entry.capability_id),
        description=str(entry.metadata.get("description") or f"Governed capability {entry.capability_id}"),
        input_schema=input_schema,
        metadata={
            "capability_id": entry.capability_id,
            "domain": entry.domain,
            "owner_team": entry.obligation_model.owner_team,
            "evidence_required": list(entry.evidence_model.required_evidence),
            "terminal_certificate_required": entry.evidence_model.terminal_certificate_required,
        },
    )


def mcp_capability_id(server_id: str, tool_name: str) -> str:
    """Return deterministic Mullu capability id for an MCP tool."""
    server_slug = _slug(server_id)
    tool_slug = _slug(tool_name)
    if not server_slug or not tool_slug:
        raise ValueError("server_id and tool_name must produce non-empty capability identity")
    return f"mcp.{server_slug}_{tool_slug}"


def _expected_effects(tool: MCPToolDescriptor) -> tuple[str, ...]:
    raw_effects = tool.annotations.get("expected_effects")
    if isinstance(raw_effects, (list, tuple)) and raw_effects:
        effects = tuple(str(effect).strip() for effect in raw_effects if str(effect).strip())
        if effects:
            return effects
    if bool(tool.annotations.get("read_only", False)):
        return ("external_context_read",)
    return ("external_tool_invoked",)


def _forbidden_effects(expected_effects: tuple[str, ...]) -> tuple[str, ...]:
    forbidden = tuple(sorted(effect for effect in _DANGEROUS_EFFECTS if effect not in expected_effects))
    return forbidden or ("unregistered_external_effect",)


def _risk_tier_for_effects(expected_effects: tuple[str, ...], annotations: Mapping[str, Any]) -> str:
    requested = str(annotations.get("risk_tier", "")).strip().lower()
    if requested in {"low", "medium", "high"}:
        return requested
    if any(effect in _DANGEROUS_EFFECTS for effect in expected_effects):
        return "high"
    return "low" if annotations.get("read_only") else "medium"


def _annotation_string_tuple(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        stripped = value.strip()
        return (stripped,) if stripped else ()
    if isinstance(value, (list, tuple)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _export_input_schema(entry: CapabilityRegistryEntry) -> dict[str, Any]:
    mcp_extension = entry.extensions.get("mcp") if isinstance(entry.extensions, Mapping) else None
    if isinstance(mcp_extension, Mapping) and isinstance(mcp_extension.get("input_schema"), Mapping):
        return dict(thaw_value_json(mcp_extension["input_schema"]))
    return {
        "type": "object",
        "properties": {
            "params": {
                "type": "object",
                "description": f"Parameters validated by {entry.input_schema_ref}",
            },
        },
        "required": ["params"],
    }


def _export_tool_name(capability_id: str) -> str:
    return "mullu_" + _slug(capability_id).replace(".", "_")


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return re.sub(r"_+", "_", normalized)
