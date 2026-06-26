#!/usr/bin/env python3
"""Validate the general-agent promotion operator checklist artifact.

Purpose: keep production-promotion execution steps machine-readable and aligned
with closure-plan, live receipt, and deployment witness gates.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, PRS]
Dependencies: examples/general_agent_promotion_operator_checklist.json.
Invariants:
  - The checklist names all approval-required residual review blockers.
  - Every required step has a command and evidence list.
  - Final validation remains gated by live evidence, environment binding, and
    terminal authority receipts.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_CHECKLIST = Path("examples") / "general_agent_promotion_operator_checklist.json"
REQUIRED_ENVIRONMENT_VARIABLES = frozenset({
    "MULLU_BROWSER_SANDBOX_EVIDENCE",
    "MULLU_VOICE_PROBE_AUDIO",
    "OPENAI_API_KEY",
    "EMAIL_CALENDAR_CONNECTOR_TOKEN",
    "MULLU_GATEWAY_URL",
    "MULLU_RUNTIME_WITNESS_SECRET",
    "MULLU_RUNTIME_CONFORMANCE_SECRET",
    "MULLU_DEPLOYMENT_WITNESS_SECRET",
    "MULLU_AUTHORITY_OPERATOR_SECRET",
})
REQUIRED_STEP_IDS = frozenset({
    "collect_adapter_evidence",
    "write_promotion_readiness",
    "write_source_closure_plans",
    "validate_adapter_closure_plan_schema",
    "validate_aggregate_closure_plan",
    "validate_environment_binding_receipt",
    "produce_live_adapter_receipts",
    "publish_deployment_witness",
    "validate_publication_and_promotion",
})
REQUIRED_APPROVAL_BLOCKERS = frozenset({
    "voice_dependency_missing:OPENAI_API_KEY",
    "email_calendar_dependency_missing:EMAIL_CALENDAR_CONNECTOR_TOKEN",
    "deployment_upstream_api_gate_not_ready",
    "capability_improvement_required:financial.refund",
    "capability_improvement_required:agentic_control.evidence.append",
    "capability_improvement_required:agentic_control.governance_gate.evaluate",
    "capability_improvement_required:agentic_control.code_change.plan",
    "capability_improvement_required:agentic_control.incident_recovery.plan",
})
REQUIRED_BLOCKING_GAPS = frozenset({
    "adapter_evidence_not_closed",
})
REQUIRED_STEP_COMMAND_TOKENS = {
    "collect_adapter_evidence": ("collect_capability_adapter_evidence.py",),
    "write_promotion_readiness": ("validate_general_agent_promotion.py", "--output"),
    "write_source_closure_plans": ("plan_capability_adapter_closure.py", "plan_deployment_publication_closure.py"),
    "validate_adapter_closure_plan_schema": (
        "validate_capability_adapter_closure_plan_schema.py",
        "capability_adapter_closure_plan_schema_validation.json",
        "--strict",
    ),
    "validate_aggregate_closure_plan": (
        "run_general_agent_promotion_closure_chain.py",
        "--json",
        "--strict",
    ),
    "validate_environment_binding_receipt": (
        "emit_general_agent_promotion_environment_binding_receipt.py",
        "validate_general_agent_promotion_environment_binding_receipt.py",
        "general_agent_promotion_environment_binding_receipt.json",
        "--require-ready",
        "--json",
    ),
    "produce_live_adapter_receipts": (
        "produce_browser_sandbox_evidence.py",
        "validate_sandbox_execution_receipt.py",
        "validate_browser_sandbox_evidence.py",
        "produce_capability_adapter_live_receipts.py",
        "--browser-sandbox-evidence",
        "--strict",
    ),
    "publish_deployment_witness": ("publish_gateway_publication.py", "--dispatch-witness"),
    "validate_publication_and_promotion": (
        "validate_deployment_publication_closure.py",
        "validate_general_agent_promotion.py",
        "--strict",
    ),
}
REQUIRED_STEP_EVIDENCE = {
    "write_promotion_readiness": frozenset({
        "readiness_level=pilot-governed-core",
        "capability_count=81",
        "capsule_count=13",
        "production blockers explicit",
    }),
    "validate_adapter_closure_plan_schema": frozenset({
        "capability_adapter_closure_plan_schema_validation.json ok=true",
        "adapter blocker coverage complete",
        "adapter action verification_command present",
        "adapter action receipt_validator present",
    }),
    "validate_aggregate_closure_plan": frozenset({
        "general_agent_promotion_closure_plan.json total_action_count=10",
        "general_agent_promotion_closure_plan_schema_validation.json ok=true",
        "general_agent_promotion_closure_plan_validation.json ok=true",
        "capability_improvement_portfolio.json plan_count=5",
        "general_agent_promotion_live_evidence_queue.json schema_valid=true",
        "live_evidence_queue ready_to_execute=false",
        "terminal approval receipt absent or schema-valid",
        "general_agent_promotion_terminal_certificate_gate.json schema_valid=true",
        "terminal_certificate_gate ready_for_terminal_certificate=false",
        "general_agent_promotion_terminal_certificate_candidates.json schema_valid=true",
        "terminal_certificate_candidates ready_for_terminal_certificate_minting=false",
        "general_agent_promotion_terminal_evidence_reconciliation.json schema_valid=true",
        "terminal_evidence_reconciliation ready_for_terminal_certificate_minting=false",
        "general_agent_promotion_terminal_minting_gate.json schema_valid=true",
        "terminal_minting_gate ready_for_terminal_certificate_minting=false",
        "approval_required_action_count=8",
        "source_plan_type includes adapter, deployment, and portfolio",
        "closure_chain status=passed_blocked",
        "closure_chain artifact_valid=true",
    }),
    "validate_environment_binding_receipt": frozenset({
        "general_agent_promotion_environment_binding_receipt.json exists",
        "receipt valid=true",
        "secret_serialization=forbidden",
        "value_serialized=false for all bindings",
    }),
    "produce_live_adapter_receipts": frozenset({
        "browser_sandbox_evidence.json verification_status=passed",
        "sandbox execution receipt validation valid=true",
        "browser_sandbox_evidence validation valid=true",
        "browser_live_receipt.json status=passed",
        "voice_live_receipt.json status=passed",
    }),
    "publish_deployment_witness": frozenset({
        "operator_approval_ref present",
        "deployment_witness.json deployment_claim=published",
    }),
    "validate_publication_and_promotion": frozenset({
        "general-agent promotion ready=false",
        "readiness_level=pilot-governed-core",
    }),
}


@dataclass(frozen=True, slots=True)
class PromotionOperatorChecklistValidation:
    """Validation result for the promotion operator checklist."""

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


def validate_general_agent_promotion_operator_checklist(
    checklist_path: Path = DEFAULT_CHECKLIST,
) -> PromotionOperatorChecklistValidation:
    """Validate one general-agent promotion operator checklist."""
    errors: list[str] = []
    payload = _load_json_object(checklist_path, errors)
    checklist_id = str(payload.get("checklist_id", ""))
    steps = payload.get("required_commands", [])
    if payload.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if checklist_id != "general-agent-promotion-operator-v1":
        errors.append("checklist_id must be general-agent-promotion-operator-v1")
    if payload.get("status") != "ready_for_final_validation":
        errors.append("status must be ready_for_final_validation")

    _require_superset(payload, "required_environment_variables", REQUIRED_ENVIRONMENT_VARIABLES, errors)
    _require_superset(payload, "approval_required_blockers", REQUIRED_APPROVAL_BLOCKERS, errors)
    _require_superset(payload, "conditional_approval_blockers", REQUIRED_APPROVAL_BLOCKERS, errors)
    _require_superset(payload, "blocking_gap_ids", REQUIRED_BLOCKING_GAPS, errors)
    _validate_steps(steps, errors)
    return PromotionOperatorChecklistValidation(
        checklist_path=checklist_path if payload else Path("<unavailable>"),
        checklist_id=checklist_id,
        valid=not errors,
        step_count=len(steps) if isinstance(steps, list) else 0,
        errors=tuple(errors),
    )


def _load_json_object(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        parsed = _loads_strict_json(path.read_text(encoding="utf-8"))
    except OSError:
        errors.append("checklist could not be read")
        return {}
    except (json.JSONDecodeError, ValueError):
        errors.append("checklist must be JSON")
        return {}
    if not isinstance(parsed, dict):
        errors.append("checklist root must be an object")
        return {}
    return parsed


def _loads_strict_json(raw: str) -> Any:
    return json.loads(raw, parse_constant=_reject_json_constant)


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


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
    missing = sorted(required - {str(item) for item in observed})
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
        for token in REQUIRED_STEP_COMMAND_TOKENS.get(step_id, ()):
            if token not in command:
                errors.append(f"{step_id or 'unnamed'} command missing token {token}")
        evidence = step.get("required_evidence", [])
        if not isinstance(evidence, list) or not evidence:
            errors.append(f"{step_id or 'unnamed'} required_evidence must be a non-empty list")
            continue
        missing_evidence = sorted(
            REQUIRED_STEP_EVIDENCE.get(step_id, frozenset()) - {str(item) for item in evidence}
        )
        if missing_evidence:
            errors.append(f"{step_id or 'unnamed'} required_evidence missing {missing_evidence}")
    missing_steps = sorted(REQUIRED_STEP_IDS - step_ids)
    if missing_steps:
        errors.append(f"required_commands missing steps {missing_steps}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse promotion operator checklist validation CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate general-agent promotion operator checklist.")
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for promotion operator checklist validation."""
    args = parse_args(argv)
    result = validate_general_agent_promotion_operator_checklist(Path(args.checklist))
    if args.json:
        print(json.dumps(result.as_dict(), indent=2, sort_keys=True))
    elif result.valid:
        print(f"general-agent promotion operator checklist ok steps={result.step_count}")
    else:
        for error in result.errors:
            print(f"error: {error}")
    return 0 if result.valid else 2


if __name__ == "__main__":
    raise SystemExit(main())
