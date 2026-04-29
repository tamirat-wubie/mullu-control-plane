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
    ownership_resource_refs: tuple[str, ...]
    approval_policy_ids: tuple[str, ...]
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
            "ownership_count": len(self.ownership_resource_refs),
            "approval_policy_count": len(self.approval_policy_ids),
            "escalation_policy_count": len(self.escalation_policy_ids),
            "capability_ids": list(self.capability_ids),
            "ownership_resource_refs": list(self.ownership_resource_refs),
            "approval_policy_ids": list(self.approval_policy_ids),
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
            ownership_resource_refs=(),
            approval_policy_ids=(),
            escalation_policy_ids=(),
            errors=(str(exc),),
        )

    capability_ids = tuple(entry.capability_id for entry in imported.entries)
    ownership_resource_refs = tuple(record.resource_ref for record in imported.authority_records.ownership)
    approval_policy_ids = tuple(policy.policy_id for policy in imported.authority_records.approval_policies)
    escalation_policy_ids = tuple(policy.policy_id for policy in imported.authority_records.escalation_policies)
    errors = _validate_import_shape(
        capability_ids=capability_ids,
        ownership_resource_refs=ownership_resource_refs,
        approval_policy_ids=approval_policy_ids,
        escalation_policy_ids=escalation_policy_ids,
    )
    return MCPCapabilityManifestValidation(
        manifest_path=manifest_path,
        manifest_ref=imported.manifest_ref,
        capability_ids=capability_ids,
        ownership_resource_refs=ownership_resource_refs,
        approval_policy_ids=approval_policy_ids,
        escalation_policy_ids=escalation_policy_ids,
        errors=tuple(errors),
    )


def _validate_import_shape(
    *,
    capability_ids: tuple[str, ...],
    ownership_resource_refs: tuple[str, ...],
    approval_policy_ids: tuple[str, ...],
    escalation_policy_ids: tuple[str, ...],
) -> list[str]:
    errors: list[str] = []
    if not capability_ids:
        errors.append("MCP manifest must produce at least one capability")
    if set(ownership_resource_refs) != set(capability_ids):
        errors.append("MCP manifest ownership records must match capability ids")
    if len(approval_policy_ids) != len(capability_ids):
        errors.append("MCP manifest approval policy count must match capability count")
    if not escalation_policy_ids:
        errors.append("MCP manifest must produce an escalation policy")
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
