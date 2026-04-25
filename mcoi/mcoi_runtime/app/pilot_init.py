"""Purpose: one-command pilot bring-up artifact scaffolding.

Governance scope: local pilot bootstrap files only; no network calls, no live
tenant mutation, and no provider credentials.
Dependencies: runtime invariant helpers and standard JSON serialization.
Invariants: generated artifacts are deterministic for identical inputs; existing
files are not overwritten unless explicitly forced; every pilot has tenant,
policy, budget, dashboard, audit, and lineage examples.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from mcoi_runtime.core.invariants import ensure_non_empty_text, stable_identifier


PILOT_FILE_NAMES = (
    "pilot.manifest.json",
    "tenant.json",
    "policy.json",
    "budget.json",
    "dashboard.json",
    "audit_queries.json",
    "lineage_examples.json",
    "README.md",
)


@dataclass(frozen=True, slots=True)
class PilotInitRequest:
    """Input contract for pilot scaffold generation."""

    tenant_id: str
    pilot_name: str
    output_dir: Path
    policy_pack_id: str = "default-safe"
    policy_version: str = "v0.1"
    max_cost: float = 100.0
    max_calls: int = 1000
    dashboard_url: str = "https://dashboard.mullusi.com"
    sandbox_url: str = "https://sandbox.mullusi.com"
    force: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "tenant_id", ensure_non_empty_text("tenant_id", self.tenant_id))
        object.__setattr__(self, "pilot_name", ensure_non_empty_text("pilot_name", self.pilot_name))
        object.__setattr__(self, "policy_pack_id", ensure_non_empty_text("policy_pack_id", self.policy_pack_id))
        object.__setattr__(self, "policy_version", ensure_non_empty_text("policy_version", self.policy_version))
        object.__setattr__(self, "dashboard_url", ensure_non_empty_text("dashboard_url", self.dashboard_url))
        object.__setattr__(self, "sandbox_url", ensure_non_empty_text("sandbox_url", self.sandbox_url))
        if self.max_cost < 0:
            raise ValueError("max_cost must be non-negative")
        if self.max_calls < 1:
            raise ValueError("max_calls must be at least 1")


@dataclass(frozen=True, slots=True)
class PilotInitResult:
    """Result contract for pilot scaffold generation."""

    pilot_id: str
    output_dir: Path
    files_written: tuple[Path, ...]
    manifest_path: Path

    def to_dict(self) -> dict[str, Any]:
        return {
            "pilot_id": self.pilot_id,
            "output_dir": str(self.output_dir),
            "files_written": [str(path) for path in self.files_written],
            "manifest_path": str(self.manifest_path),
            "governed": True,
        }


def initialize_pilot(request: PilotInitRequest) -> PilotInitResult:
    """Create a complete local pilot scaffold."""
    pilot_id = stable_identifier(
        "pilot",
        {
            "tenant_id": request.tenant_id,
            "pilot_name": request.pilot_name,
            "policy_pack_id": request.policy_pack_id,
            "policy_version": request.policy_version,
        },
    )
    output_dir = request.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    target_paths = tuple(output_dir / file_name for file_name in PILOT_FILE_NAMES)
    existing = tuple(path for path in target_paths if path.exists())
    if existing and not request.force:
        raise FileExistsError("pilot scaffold target contains existing files")

    payloads = _pilot_payloads(request, pilot_id)
    written: list[Path] = []
    for file_name, payload in payloads.items():
        path = output_dir / file_name
        if file_name.endswith(".md"):
            path.write_text(str(payload), encoding="utf-8")
        else:
            path.write_text(_stable_json(payload), encoding="utf-8")
        written.append(path)

    return PilotInitResult(
        pilot_id=pilot_id,
        output_dir=output_dir,
        files_written=tuple(written),
        manifest_path=output_dir / "pilot.manifest.json",
    )


def _pilot_payloads(request: PilotInitRequest, pilot_id: str) -> dict[str, Any]:
    budget_id = f"{request.tenant_id}-pilot-budget"
    manifest = {
        "pilot_id": pilot_id,
        "tenant_id": request.tenant_id,
        "pilot_name": request.pilot_name,
        "artifacts": list(PILOT_FILE_NAMES),
        "entrypoints": {
            "api": "https://api.mullusi.com",
            "docs": "https://docs.mullusi.com",
            "dashboard": request.dashboard_url,
            "sandbox": request.sandbox_url,
        },
        "governance": {
            "policy_pack_id": request.policy_pack_id,
            "policy_version": request.policy_version,
            "budget_id": budget_id,
            "lineage_enabled": True,
            "audit_required": True,
        },
    }
    return {
        "pilot.manifest.json": manifest,
        "tenant.json": {
            "tenant_id": request.tenant_id,
            "display_name": request.pilot_name,
            "environment": "pilot",
            "status": "scaffolded",
        },
        "policy.json": {
            "policy_pack_id": request.policy_pack_id,
            "policy_version": request.policy_version,
            "mode": "enforced",
            "shadow_policy": {
                "enabled": True,
                "candidate_version": f"{request.policy_version}-shadow",
            },
        },
        "budget.json": {
            "tenant_id": request.tenant_id,
            "budget_id": budget_id,
            "max_cost": request.max_cost,
            "max_calls": request.max_calls,
            "streaming_enforcement": "predictive_debit",
        },
        "dashboard.json": {
            "dashboard_url": request.dashboard_url,
            "sandbox_url": request.sandbox_url,
            "views": ["budget", "policy_decisions", "audit_trail", "lineage", "proof_coverage"],
        },
        "audit_queries.json": {
            "queries": [
                {
                    "name": "recent_policy_decisions",
                    "path": f"/api/v1/audit?tenant_id={request.tenant_id}&action=policy.decision&limit=25",
                },
                {
                    "name": "budget_events",
                    "path": f"/api/v1/audit?tenant_id={request.tenant_id}&action=budget.debit&limit=25",
                },
                {
                    "name": "tool_invocations",
                    "path": f"/api/v1/audit?tenant_id={request.tenant_id}&action=tool.invoke&limit=25",
                },
            ]
        },
        "lineage_examples.json": {
            "examples": [
                "lineage://trace/{trace_id}?depth=25&verify=true",
                "lineage://output/{output_id}?include=policy,model,tenant,budget,replay",
                "lineage://command/{command_id}?include=policy,tool",
            ]
        },
        "README.md": _readme(request=request, pilot_id=pilot_id),
    }


def _readme(*, request: PilotInitRequest, pilot_id: str) -> str:
    return (
        f"# {request.pilot_name} Pilot\n\n"
        f"Pilot ID: `{pilot_id}`\n\n"
        "## Bring-Up\n\n"
        "1. Review `tenant.json`, `policy.json`, and `budget.json`.\n"
        "2. Start the local governed API service.\n"
        "3. Use `audit_queries.json` to verify policy, budget, and tool-call events.\n"
        "4. Use `lineage_examples.json` to inspect causal proof paths.\n\n"
        "## Invariants\n\n"
        "- Tenant, policy, and budget are explicit.\n"
        "- Audit is required for pilot execution.\n"
        "- Lineage examples are present before the pilot demo.\n"
        "- Generated files are deterministic for the same pilot inputs.\n"
    )


def _stable_json(payload: Any) -> str:
    return json.dumps(payload, sort_keys=True, indent=2, separators=(",", ": ")) + "\n"
