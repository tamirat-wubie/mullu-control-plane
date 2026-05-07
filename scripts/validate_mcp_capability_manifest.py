#!/usr/bin/env python3
"""Validate the gateway MCP capability manifest.

Purpose: ensure MCP tool imports bind capability admission, certification
provenance, ownership, approval policy, and escalation policy before startup.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: gateway.mcp_capability_fabric and examples/mcp_capability_manifest.json.
Invariants:
  - A manifest must produce at least one certified MCP capability.
  - Every certified capability must have ownership and approval records.
  - Every manifest import must produce an escalation policy.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
MCOI_ROOT = REPO_ROOT / "mcoi"
if str(MCOI_ROOT) not in sys.path:
    sys.path.insert(0, str(MCOI_ROOT))

from gateway.mcp_capability_fabric import build_mcp_gateway_import_from_manifest  # noqa: E402

DEFAULT_MANIFEST = Path("examples") / "mcp_capability_manifest.json"


@dataclass(frozen=True, slots=True)
class MCPCapabilityManifestValidation:
    """Validation result for one MCP capability import manifest."""

    manifest_path: Path
    manifest_ref: str
    capability_ids: tuple[str, ...]
    certified_by_refs: tuple[str, ...]
    certification_evidence_refs: tuple[str, ...]
    owner_teams: tuple[str, ...]
    ownership_resource_refs: tuple[str, ...]
    approval_policy_ids: tuple[str, ...]
    approval_policy_capabilities: tuple[str, ...]
    escalation_policy_ids: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        """Return whether the manifest satisfies hard checks."""
        return not self.errors

    def as_dict(self) -> dict[str, Any]:
        """Return a deterministic JSON-ready validation summary."""
        return {
            "valid": self.ok,
            "manifest_path": str(self.manifest_path),
            "manifest_ref": self.manifest_ref,
            "capability_count": len(self.capability_ids),
            "certified_by_refs": list(self.certified_by_refs),
            "certification_evidence_refs": list(self.certification_evidence_refs),
            "owner_teams": list(self.owner_teams),
            "ownership_count": len(self.ownership_resource_refs),
            "approval_policy_count": len(self.approval_policy_ids),
            "escalation_policy_count": len(self.escalation_policy_ids),
            "capability_ids": list(self.capability_ids),
            "ownership_resource_refs": list(self.ownership_resource_refs),
            "approval_policy_ids": list(self.approval_policy_ids),
            "approval_policy_capabilities": list(self.approval_policy_capabilities),
            "escalation_policy_ids": list(self.escalation_policy_ids),
            "errors": list(self.errors),
        }


def validate_mcp_capability_manifest(
    manifest_path: Path = DEFAULT_MANIFEST,
    *,
    clock: Callable[[], str] | None = None,
) -> MCPCapabilityManifestValidation:
    """Validate one MCP capability manifest through the runtime import builder."""
    try:
        imported = build_mcp_gateway_import_from_manifest(
            manifest_path,
            clock=clock or _validation_clock,
        )
    except ValueError as exc:
        return MCPCapabilityManifestValidation(
            manifest_path=manifest_path,
            manifest_ref="",
            capability_ids=(),
            certified_by_refs=(),
            certification_evidence_refs=(),
            owner_teams=(),
            ownership_resource_refs=(),
            approval_policy_ids=(),
            approval_policy_capabilities=(),
            escalation_policy_ids=(),
            errors=(str(exc),),
        )

    capability_ids = tuple(entry.capability_id for entry in imported.entries)
    certified_by_refs = tuple(str(entry.metadata.get("certified_by", "")) for entry in imported.entries)
    certification_evidence_refs = tuple(
        str(entry.metadata.get("certification_evidence_ref", "")) for entry in imported.entries
    )
    owner_teams = tuple(entry.obligation_model.owner_team for entry in imported.entries)
    ownership_resource_refs = tuple(record.resource_ref for record in imported.authority_records.ownership)
    approval_policy_ids = tuple(policy.policy_id for policy in imported.authority_records.approval_policies)
    approval_policy_capabilities = tuple(
        policy.capability for policy in imported.authority_records.approval_policies
    )
    escalation_policy_ids = tuple(policy.policy_id for policy in imported.authority_records.escalation_policies)
    errors = _validate_import_shape(
        entries=imported.entries,
        ownership_records=imported.authority_records.ownership,
        approval_policies=imported.authority_records.approval_policies,
        escalation_policies=imported.authority_records.escalation_policies,
        capability_ids=capability_ids,
        ownership_resource_refs=ownership_resource_refs,
        approval_policy_ids=approval_policy_ids,
        approval_policy_capabilities=approval_policy_capabilities,
        escalation_policy_ids=escalation_policy_ids,
    )
    return MCPCapabilityManifestValidation(
        manifest_path=manifest_path,
        manifest_ref=imported.manifest_ref,
        capability_ids=capability_ids,
        certified_by_refs=certified_by_refs,
        certification_evidence_refs=certification_evidence_refs,
        owner_teams=owner_teams,
        ownership_resource_refs=ownership_resource_refs,
        approval_policy_ids=approval_policy_ids,
        approval_policy_capabilities=approval_policy_capabilities,
        escalation_policy_ids=escalation_policy_ids,
        errors=tuple(errors),
    )


def _validate_import_shape(
    *,
    entries: tuple[Any, ...],
    ownership_records: tuple[Any, ...],
    approval_policies: tuple[Any, ...],
    escalation_policies: tuple[Any, ...],
    capability_ids: tuple[str, ...],
    ownership_resource_refs: tuple[str, ...],
    approval_policy_ids: tuple[str, ...],
    approval_policy_capabilities: tuple[str, ...],
    escalation_policy_ids: tuple[str, ...],
) -> list[str]:
    errors: list[str] = []
    if not capability_ids:
        errors.append("MCP manifest must produce at least one capability")
    for entry in entries:
        if getattr(entry, "domain", "") != "mcp":
            errors.append(f"MCP manifest capability must use mcp domain: {entry.capability_id}")
        if getattr(entry.certification_status, "value", "") != "certified":
            errors.append(f"MCP manifest capability must be certified: {entry.capability_id}")
        if not str(entry.metadata.get("certified_by", "")).strip():
            errors.append(f"MCP manifest capability missing certified_by provenance: {entry.capability_id}")
        if not str(entry.metadata.get("certification_evidence_ref", "")).strip():
            errors.append(f"MCP manifest capability missing certification evidence: {entry.capability_id}")
        if not str(entry.obligation_model.owner_team).strip():
            errors.append(f"MCP manifest capability missing owner team: {entry.capability_id}")
    if set(ownership_resource_refs) != set(capability_ids):
        errors.append("MCP manifest ownership records must match capability ids")
    for ownership in ownership_records:
        if not str(ownership.owner_team).strip():
            errors.append(f"MCP manifest ownership missing owner team: {ownership.resource_ref}")
        if not str(ownership.primary_owner_id).strip():
            errors.append(f"MCP manifest ownership missing primary owner: {ownership.resource_ref}")
        if not str(ownership.fallback_owner_id).strip():
            errors.append(f"MCP manifest ownership missing fallback owner: {ownership.resource_ref}")
        if not str(ownership.escalation_team).strip():
            errors.append(f"MCP manifest ownership missing escalation team: {ownership.resource_ref}")
    if len(approval_policy_ids) != len(capability_ids):
        errors.append("MCP manifest approval policy count must match capability count")
    if set(approval_policy_capabilities) != set(capability_ids):
        errors.append("MCP manifest approval policies must match capability ids")
    for policy in approval_policies:
        if not policy.required_roles:
            errors.append(f"MCP manifest approval policy missing required roles: {policy.policy_id}")
        if policy.timeout_seconds <= 0:
            errors.append(f"MCP manifest approval policy timeout must be positive: {policy.policy_id}")
        if policy.risk_tier == "high" and policy.required_approver_count < 2:
            errors.append(f"MCP manifest high-risk approval policy requires dual approval: {policy.policy_id}")
        if policy.risk_tier == "high" and not policy.separation_of_duty:
            errors.append(f"MCP manifest high-risk approval policy requires separation of duty: {policy.policy_id}")
        if policy.escalation_policy_id not in escalation_policy_ids:
            errors.append(f"MCP manifest approval policy references missing escalation policy: {policy.policy_id}")
    if not escalation_policy_ids:
        errors.append("MCP manifest must produce an escalation policy")
    for policy in escalation_policies:
        if policy.notify_after_seconds <= 0:
            errors.append(f"MCP manifest escalation notify timeout must be positive: {policy.policy_id}")
        if policy.escalate_after_seconds <= policy.notify_after_seconds:
            errors.append(f"MCP manifest escalation timeout ordering is invalid: {policy.policy_id}")
        if policy.incident_after_seconds <= policy.escalate_after_seconds:
            errors.append(f"MCP manifest incident timeout ordering is invalid: {policy.policy_id}")
        if not str(policy.fallback_owner_id).strip():
            errors.append(f"MCP manifest escalation missing fallback owner: {policy.policy_id}")
        if not str(policy.escalation_team).strip():
            errors.append(f"MCP manifest escalation missing escalation team: {policy.policy_id}")
    return errors


def _validation_clock() -> str:
    return "2026-04-29T12:00:00+00:00"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse MCP capability manifest validation CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate Mullu MCP capability manifest.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON validation output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for MCP capability manifest validation."""
    args = parse_args(argv)
    result = validate_mcp_capability_manifest(Path(args.manifest))
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.ok:
        print(
            "mcp capability manifest ok "
            f"capabilities={len(result.capability_ids)} "
            f"ownership={len(result.ownership_resource_refs)} "
            f"approval_policies={len(result.approval_policy_ids)}"
        )
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
