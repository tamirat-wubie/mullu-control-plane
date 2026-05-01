#!/usr/bin/env python3
"""Validate the MCP operator handoff checklist artifact.

Purpose: keep MCP deployment handoff evidence machine-readable and ensure the
operator procedure names manifest validation, read-model inspection, runtime
conformance, and deployment preflight gates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/mcp_operator_handoff_checklist.json.
Invariants:
  - The checklist has a stable schema version and checklist id.
  - Every required gate has a command and required evidence list.
  - Runtime read-model and conformance fields include MCP manifest validity.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CHECKLIST = Path("examples") / "mcp_operator_handoff_checklist.json"
REQUIRED_ENVIRONMENT_VARIABLES = frozenset({
    "MULLU_MCP_CAPABILITY_MANIFEST_PATH",
    "MULLU_GATEWAY_URL",
    "MULLU_GATEWAY_HOST",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_AUTHORITY_OPERATOR_SECRET",
    "MULLU_DEPLOYMENT_ORCHESTRATION_OUTPUT",
})
REQUIRED_STEP_IDS = frozenset({
    "validate_manifest",
    "inspect_operator_read_model",
    "inspect_mcp_execution_evidence_bundle",
    "collect_runtime_conformance",
    "run_deployment_preflight",
    "write_orchestration_receipt",
})
REQUIRED_READ_MODEL_FIELDS = frozenset({
    "mcp_manifest_configured",
    "mcp_manifest_valid",
    "mcp_manifest_ref",
    "mcp_manifest_capability_count",
    "executor_enabled",
    "execution_audit_count",
    "execution_audits",
})
REQUIRED_CONFORMANCE_FIELDS = frozenset({
    "mcp_capability_manifest_configured",
    "mcp_capability_manifest_valid",
    "mcp_capability_manifest_capability_count",
    "capability_plan_bundle_canary_passed",
    "capability_plan_bundle_count",
    "open_conformance_gaps",
    "terminal_status",
    "signature",
})
REQUIRED_BLOCKING_GAPS = frozenset({
    "mcp_capability_manifest_invalid",
    "authority_responsibility_debt_present",
    "capability_fabric_admission_not_live",
    "capability_plan_evidence_bundle_not_witnessed",
})
REQUIRED_STEP_EVIDENCE = {
    "validate_manifest": frozenset({
        "valid=true",
        "capability_count>0",
    }),
    "inspect_operator_read_model": frozenset({
        "executor_enabled=true",
        "execution_audit_count>=0",
    }),
    "inspect_mcp_execution_evidence_bundle": frozenset({
        "bundle_id startswith mcp-evidence-bundle-",
        "evidence_refs non-empty",
    }),
    "collect_runtime_conformance": frozenset({
        "mcp_capability_manifest_configured=true",
        "mcp_capability_manifest_valid=true",
        "capability_plan_bundle_canary_passed=true",
    }),
    "run_deployment_preflight": frozenset({
        "runtime conformance endpoint step passed",
        "plan_bundle_passed=True",
        "ready=true",
    }),
    "write_orchestration_receipt": frozenset({
        "receipt_id startswith deployment-witness-orchestration-",
        "preflight_ready=true",
        "evidence_refs non-empty",
    }),
}
REQUIRED_STEP_COMMAND_TOKENS = {
    "validate_manifest": ("validate_mcp_capability_manifest.py", "--json"),
    "inspect_operator_read_model": ("/mcp/operator/read-model", "X-Mullu-Authority-Secret"),
    "inspect_mcp_execution_evidence_bundle": ("/mcp/operator/evidence-bundles/", "X-Mullu-Authority-Secret"),
    "collect_runtime_conformance": ("collect_runtime_conformance.py", "--authority-operator-secret"),
    "run_deployment_preflight": ("preflight_deployment_witness.py", "--mcp-capability-manifest"),
    "write_orchestration_receipt": ("orchestrate_deployment_witness.py", "--orchestration-output"),
}


@dataclass(frozen=True, slots=True)
class MCPOperatorChecklistValidation:
    """Validation result for the MCP operator handoff checklist."""

    checklist_path: Path
    checklist_id: str
    valid: bool
    step_count: int
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-ready validation output."""
        return {
            "valid": self.valid,
            "checklist_path": str(self.checklist_path),
            "checklist_id": self.checklist_id,
            "step_count": self.step_count,
            "errors": list(self.errors),
        }


def validate_mcp_operator_checklist(
    checklist_path: Path = DEFAULT_CHECKLIST,
) -> MCPOperatorChecklistValidation:
    """Validate one MCP operator handoff checklist artifact."""
    errors: list[str] = []
    payload = _load_json_object(checklist_path, errors)
    checklist_id = str(payload.get("checklist_id", ""))
    steps = payload.get("required_commands", [])
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if checklist_id != "mcp-operator-handoff-v1":
        errors.append("checklist_id must be mcp-operator-handoff-v1")
    if payload.get("status") != "ready_for_handoff":
        errors.append("status must be ready_for_handoff")

    _require_superset(payload, "required_environment_variables", REQUIRED_ENVIRONMENT_VARIABLES, errors)
    _require_superset(payload, "required_read_model_fields", REQUIRED_READ_MODEL_FIELDS, errors)
    _require_superset(payload, "required_conformance_fields", REQUIRED_CONFORMANCE_FIELDS, errors)
    _require_superset(payload, "blocking_gap_ids", REQUIRED_BLOCKING_GAPS, errors)
    _validate_steps(steps, errors)
    return MCPOperatorChecklistValidation(
        checklist_path=checklist_path,
        checklist_id=checklist_id,
        valid=not errors,
        step_count=len(steps) if isinstance(steps, list) else 0,
        errors=tuple(errors),
    )


def _load_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        errors.append(f"checklist could not be read: {exc}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"checklist must be JSON: {exc}")
        return {}
    if not isinstance(parsed, dict):
        errors.append("checklist root must be an object")
        return {}
    return parsed


def _require_superset(
    payload: dict[str, Any],
    field: str,
    required: frozenset[str],
    errors: list[str],
) -> None:
    observed = payload.get(field, [])
    if not isinstance(observed, list):
        errors.append(f"{field} must be a list")
        return
    observed_set = {str(item) for item in observed}
    missing = sorted(required - observed_set)
    if missing:
        errors.append(f"{field} missing {missing}")


def _validate_steps(steps: Any, errors: list[str]) -> None:
    if not isinstance(steps, list):
        errors.append("required_commands must be a list")
        return
    step_ids: set[str] = set()
    for step in steps:
        if not isinstance(step, dict):
            errors.append("required_commands entries must be objects")
            continue
        step_id = str(step.get("step_id", ""))
        if step_id in step_ids:
            errors.append(f"duplicate required_commands step_id {step_id}")
        step_ids.add(step_id)
        command = str(step.get("command", "")).strip()
        if not command:
            errors.append(f"{step_id or 'unnamed'} command is required")
        for token in REQUIRED_STEP_COMMAND_TOKENS.get(step_id, ()):
            if token not in command:
                errors.append(f"{step_id or 'unnamed'} command missing token {token}")
        evidence = step.get("required_evidence", [])
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{step_id or 'unnamed'} required_evidence must be a non-empty list")
            continue
        evidence_set = {str(item) for item in evidence}
        missing_evidence = sorted(REQUIRED_STEP_EVIDENCE.get(step_id, frozenset()) - evidence_set)
        if missing_evidence:
            errors.append(f"{step_id or 'unnamed'} required_evidence missing {missing_evidence}")
    missing_steps = sorted(REQUIRED_STEP_IDS - step_ids)
    if missing_steps:
        errors.append(f"required_commands missing steps {missing_steps}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse MCP operator checklist validation CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate MCP operator handoff checklist.")
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST))
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON validation output.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for MCP operator handoff checklist validation."""
    args = parse_args(argv)
    result = validate_mcp_operator_checklist(Path(args.checklist))
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"mcp operator checklist ok steps={result.step_count}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
