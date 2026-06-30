#!/usr/bin/env python3
"""Validate Universal Domain Operating Pack contracts.

Purpose: validate executable domain-pack schemas and lint governance gates.
Governance scope: UDOP schema validation, core authority ceiling, evidence
coverage, workflow state ladders, output-claim boundaries, receipts,
freshness, and rollback policy.
Dependencies: repository-local JSON schemas and shared schema validator.
Invariants:
  - Domain packs cannot grant authority above the core system.
  - Every allowed or conditional action has evidence and risk coverage.
  - Workflow transitions reference declared states only.
  - Output claims remain bounded by verified state.
  - Validation is read-only and deterministic.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any, Mapping


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance

DOMAIN_PACK_SCHEMA_PATH = REPO_ROOT / "schemas" / "universal_domain_ops" / "domain_pack.schema.json"

REQUIRED_TESTS = frozenset(
    (
        "activation_test",
        "boundary_test",
        "ontology_test",
        "evidence_test",
        "action_gate_test",
        "false_success_test",
        "stale_pack_test",
        "malicious_input_test",
        "conflict_composition_test",
        "tool_failure_test",
        "output_claim_test",
        "receipt_generation_test",
    )
)
REQUIRED_RECEIPTS = frozenset(
    (
        "pack_activation",
        "evidence_decision",
        "action_gate",
        "blocked_action",
        "output_claim",
        "refinement_delta",
    )
)
CORE_ESCALATING_ACTIONS = frozenset(
    (
        "execute_payment",
        "send_payment",
        "modify_vendor_bank_details",
        "delete_invoice_record",
        "send_external_message",
        "write_external_state",
        "claim_legal_compliance",
        "claim_tax_status",
    )
)


def validate_domain_pack(path: Path) -> list[str]:
    """Return schema and linter violations for one domain pack."""
    payload = _load_json(path)
    schema = _load_schema(DOMAIN_PACK_SCHEMA_PATH)
    errors = [
        f"schema:{message}"
        for message in _validate_schema_instance(schema, payload)
    ]
    if errors:
        return errors
    errors.extend(_lint_domain_pack(payload))
    return errors


def _lint_domain_pack(payload: Mapping[str, Any]) -> list[str]:
    errors: list[str] = []
    errors.extend(_lint_core_authority(payload))
    errors.extend(_lint_action_coverage(payload))
    errors.extend(_lint_workflow(payload))
    errors.extend(_lint_tests(payload))
    errors.extend(_lint_receipts(payload))
    errors.extend(_lint_versioning(payload))
    return errors


def _lint_core_authority(payload: Mapping[str, Any]) -> list[str]:
    governance = _mapping(payload.get("governance"))
    actions = _mapping(payload.get("actions"))
    allowed_actions = set(_strings(actions.get("allowed")))
    forbidden_actions = set(_strings(actions.get("forbidden")))
    escalating_allowed = sorted(allowed_actions.intersection(CORE_ESCALATING_ACTIONS))
    missing_forbidden = sorted(CORE_ESCALATING_ACTIONS.difference(forbidden_actions))
    errors: list[str] = []
    if governance.get("core_authority_ceiling") is not True:
        errors.append("governance.core_authority_ceiling_must_be_true")
    if governance.get("strictest_constraint_wins") is not True:
        errors.append("governance.strictest_constraint_wins_must_be_true")
    if governance.get("no_claim_beyond_verified_state") is not True:
        errors.append("governance.no_claim_beyond_verified_state_must_be_true")
    if governance.get("refinement_requires_validation") is not True:
        errors.append("governance.refinement_requires_validation_must_be_true")
    if escalating_allowed:
        errors.append(f"actions.allowed_escalates_core_authority:{','.join(escalating_allowed)}")
    if "execute_payment" not in forbidden_actions:
        errors.append("actions.forbidden_missing_execute_payment")
    if not forbidden_actions.intersection(CORE_ESCALATING_ACTIONS):
        errors.append(f"actions.forbidden_missing_core_escalation_guards:{','.join(missing_forbidden)}")
    return errors


def _lint_action_coverage(payload: Mapping[str, Any]) -> list[str]:
    actions = _mapping(payload.get("actions"))
    evidence = _mapping(payload.get("evidence"))
    risk = _mapping(payload.get("risk"))
    allowed_actions = set(_strings(actions.get("allowed")))
    conditional_actions = set(_mapping(actions.get("conditional")).keys())
    all_actions = allowed_actions.union(conditional_actions)
    evidence_actions = set(_mapping(evidence.get("required_by_action")).keys())
    risk_actions = set(_mapping(risk.get("action_risk")).keys())
    errors: list[str] = []
    missing_evidence = sorted(all_actions.difference(evidence_actions))
    missing_risk = sorted(all_actions.difference(risk_actions))
    if missing_evidence:
        errors.append(f"evidence.required_by_action_missing:{','.join(missing_evidence)}")
    if missing_risk:
        errors.append(f"risk.action_risk_missing:{','.join(missing_risk)}")
    vector_dimensions = set(_strings(evidence.get("vector_dimensions")))
    required_dimensions = {"authority", "freshness", "specificity", "chain_of_custody", "domain_relevance"}
    missing_dimensions = sorted(required_dimensions.difference(vector_dimensions))
    if missing_dimensions:
        errors.append(f"evidence.vector_dimensions_missing:{','.join(missing_dimensions)}")
    return errors


def _lint_workflow(payload: Mapping[str, Any]) -> list[str]:
    workflow = _mapping(payload.get("workflow"))
    states = set(_strings(workflow.get("states")))
    initial_state = str(workflow.get("initial_state", ""))
    terminal_states = set(_strings(workflow.get("terminal_states")))
    transitions = _mapping(workflow.get("transitions"))
    errors: list[str] = []
    if initial_state not in states:
        errors.append("workflow.initial_state_not_declared")
    missing_terminal_states = sorted(terminal_states.difference(states))
    if missing_terminal_states:
        errors.append(f"workflow.terminal_states_not_declared:{','.join(missing_terminal_states)}")
    for transition_name, raw_transition in transitions.items():
        transition = _mapping(raw_transition)
        from_state = str(transition.get("from_state", ""))
        to_state = str(transition.get("to_state", ""))
        if from_state not in states:
            errors.append(f"workflow.transition_from_state_not_declared:{transition_name}")
        if to_state not in states:
            errors.append(f"workflow.transition_to_state_not_declared:{transition_name}")
    if "approved" in states and "paid" in states:
        if _state_index(workflow, "approved") >= _state_index(workflow, "paid"):
            errors.append("workflow.false_success_ladder_invalid:approved_must_precede_paid")
    return errors


def _lint_tests(payload: Mapping[str, Any]) -> list[str]:
    declared = set(_strings(_mapping(payload.get("tests")).get("required")))
    missing = sorted(REQUIRED_TESTS.difference(declared))
    return [f"tests.required_missing:{','.join(missing)}"] if missing else []


def _lint_receipts(payload: Mapping[str, Any]) -> list[str]:
    declared = set(_strings(_mapping(payload.get("receipts")).get("required_for")))
    missing = sorted(REQUIRED_RECEIPTS.difference(declared))
    return [f"receipts.required_for_missing:{','.join(missing)}"] if missing else []


def _lint_versioning(payload: Mapping[str, Any]) -> list[str]:
    versioning = _mapping(payload.get("versioning"))
    errors: list[str] = []
    if versioning.get("semver") is not True:
        errors.append("versioning.semver_must_be_true")
    if versioning.get("rollback_required") is not True:
        errors.append("versioning.rollback_required_must_be_true")
    if versioning.get("stale_behavior") not in {"read_only", "block", "require_current_source"}:
        errors.append("versioning.stale_behavior_invalid")
    return errors


def _state_index(workflow: Mapping[str, Any], state: str) -> int:
    states = _strings(workflow.get("states"))
    try:
        return states.index(state)
    except ValueError:
        return -1


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, str) and item]


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a Universal Domain Operating Pack.")
    parser.add_argument("pack", type=Path, help="Path to the domain pack JSON file.")
    parser.add_argument("--json", action="store_true", help="Emit a JSON validation receipt.")
    args = parser.parse_args()

    errors = validate_domain_pack(args.pack)
    receipt = {
        "pack_path": str(args.pack),
        "schema_ref": str(DOMAIN_PACK_SCHEMA_PATH),
        "valid": not errors,
        "errors": errors,
    }
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    elif errors:
        print("DOMAIN PACK VALIDATION FAILED")
        for error in errors:
            print(f"  X {error}")
    else:
        print("DOMAIN PACK VALIDATION PASSED")
    raise SystemExit(1 if errors else 0)


if __name__ == "__main__":
    main()
