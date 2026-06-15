#!/usr/bin/env python3
"""Validate Component Harness lifecycle transition receipts.

Purpose: prove each current component lifecycle state has a receipt-bound
transition, evidence refs, and hard live-authority denial.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/component_lifecycle_transition_receipts.schema.json,
examples/component_lifecycle_transition_receipts.foundation.json,
examples/component_registry.foundation.json, and component registry validation.
Invariants:
  - Every registered component has exactly one current-state transition receipt.
  - Receipt target state, wiring state, and authority level match the registry.
  - Live execution, connector send, mutation, external effect, and terminal
    closure remain blocked.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import sys
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_component_registry import validate_component_registry  # noqa: E402
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "component_lifecycle_transition_receipts.schema.json"
DEFAULT_RECEIPTS = REPO_ROOT / "examples" / "component_lifecycle_transition_receipts.foundation.json"
DEFAULT_REGISTRY = REPO_ROOT / "examples" / "component_registry.foundation.json"
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "component_lifecycle_transition_receipts_validation.json"

REQUIRED_VALIDATOR_COMMANDS = {
    "component_lifecycle_transition_receipts_validator": (
        "python scripts/validate_component_lifecycle_transition_receipts.py"
    ),
    "component_lifecycle_transition_receipts_tests": (
        "python -m pytest tests/test_validate_component_lifecycle_transition_receipts.py -q"
    ),
}
ALLOWED_TRANSITIONS = frozenset(
    {
        ("not_present", "present"),
        ("present", "registered"),
        ("registered", "validated"),
        ("validated", "bootstrapped"),
        ("bootstrapped", "mounted"),
        ("mounted", "read_only"),
        ("mounted", "draft_only"),
        ("draft_only", "live_probe"),
        ("live_probe", "approval_required"),
        ("approval_required", "blocked"),
    }
)
OPERATOR_APPROVAL_REQUIRED_TO_STATES = frozenset({"live_probe", "approval_required", "blocked"})
DISALLOWED_FOUNDATION_TARGET_STATES = frozenset({"approved_live_action"})
LIVE_GUARDRAIL_FLAGS = (
    "can_execute",
    "can_mutate",
    "can_call_connector",
    "can_write_files",
    "can_send_external_message",
    "can_claim_terminal_closure",
)


@dataclass(frozen=True, slots=True)
class ComponentLifecycleTransitionReceiptValidation:
    """Validation report for lifecycle transition receipts."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    receipt_path: str
    registry_path: str
    receipt_count: int
    component_count: int
    allowed_transition_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        return payload


def validate_component_lifecycle_transition_receipts(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    receipt_path: Path = DEFAULT_RECEIPTS,
    registry_path: Path = DEFAULT_REGISTRY,
) -> ComponentLifecycleTransitionReceiptValidation:
    """Validate lifecycle transition receipts against registry state."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "component lifecycle transition receipt schema", errors)
    receipts = _load_json_object(receipt_path, "component lifecycle transition receipt example", errors)
    registry = _load_json_object(registry_path, "component registry example", errors)

    registry_validation = validate_component_registry(example_paths=(registry_path,))
    if not registry_validation.ok:
        errors.extend(f"component registry validation failed: {error}" for error in registry_validation.errors)

    if schema and receipts:
        errors.extend(
            f"{_path_label(receipt_path)}: {error}"
            for error in _validate_schema_instance(schema, receipts)
        )
    if receipts and registry:
        _validate_receipt_set(receipts, registry, errors, _path_label(receipt_path))

    receipt_entries = receipts.get("transition_receipts", ()) if isinstance(receipts, dict) else ()
    component_entries = registry.get("components", ()) if isinstance(registry, dict) else ()
    allowed_entries = receipts.get("allowed_transition_graph", ()) if isinstance(receipts, dict) else ()
    return ComponentLifecycleTransitionReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        receipt_path=_path_label(receipt_path),
        registry_path=_path_label(registry_path),
        receipt_count=len(receipt_entries) if isinstance(receipt_entries, list) else 0,
        component_count=len(component_entries) if isinstance(component_entries, list) else 0,
        allowed_transition_count=len(allowed_entries) if isinstance(allowed_entries, list) else 0,
    )


def write_component_lifecycle_transition_receipt_validation(
    validation: ComponentLifecycleTransitionReceiptValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic lifecycle transition receipt validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_receipt_set(
    receipts: dict[str, Any],
    registry: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if receipts.get("source_registry") != "examples/component_registry.foundation.json":
        errors.append(f"{label}: source_registry must be examples/component_registry.foundation.json")
    if receipts.get("receipt_set_is_not_execution_authority") is not True:
        errors.append(f"{label}: receipt_set_is_not_execution_authority must be true")
    for flag_name in ("live_execution_enabled", "live_connector_send_enabled"):
        if receipts.get(flag_name) is not False:
            errors.append(f"{label}: {flag_name} must be false")
    if receipts.get("terminal_closure_required") is not True:
        errors.append(f"{label}: terminal_closure_required must be true")
    _validate_validators(receipts, errors, label)
    _validate_allowed_transition_graph(receipts, errors, label)

    component_by_id = _component_by_id(registry, errors, label)
    receipt_entries = receipts.get("transition_receipts")
    if not isinstance(receipt_entries, list):
        errors.append(f"{label}: transition_receipts must be a list")
        return

    receipt_ids: set[str] = set()
    receipt_components: set[str] = set()
    for receipt in receipt_entries:
        if not isinstance(receipt, dict):
            errors.append(f"{label}: transition receipt entries must be objects")
            continue
        receipt_id = str(receipt.get("receipt_id", ""))
        component_id = str(receipt.get("component_id", ""))
        if receipt_id in receipt_ids:
            errors.append(f"{label}: duplicate receipt_id {receipt_id}")
        receipt_ids.add(receipt_id)
        if component_id in receipt_components:
            errors.append(f"{label}: duplicate component receipt for {component_id}")
        receipt_components.add(component_id)
        component = component_by_id.get(component_id)
        if component is None:
            errors.append(f"{label}: receipt component {component_id} is not registered")
            continue
        _validate_receipt(receipt, component, errors, label)

    missing_receipts = sorted(set(component_by_id) - receipt_components)
    extra_receipts = sorted(receipt_components - set(component_by_id))
    if missing_receipts:
        errors.append(f"{label}: registered components missing lifecycle receipts {missing_receipts}")
    if extra_receipts:
        errors.append(f"{label}: lifecycle receipts for unknown components {extra_receipts}")


def _validate_validators(receipts: dict[str, Any], errors: list[str], label: str) -> None:
    validators = receipts.get("validators")
    if not isinstance(validators, list):
        errors.append(f"{label}: validators must be a list")
        return
    validator_by_id: dict[str, dict[str, Any]] = {}
    for validator in validators:
        if not isinstance(validator, dict):
            errors.append(f"{label}: validator entries must be objects")
            continue
        validator_id = str(validator.get("validator_id", ""))
        validator_by_id[validator_id] = validator
    for validator_id, expected_command in REQUIRED_VALIDATOR_COMMANDS.items():
        validator = validator_by_id.get(validator_id)
        if validator is None:
            errors.append(f"{label}: missing validator {validator_id}")
            continue
        if validator.get("command") != expected_command:
            errors.append(f"{label}: validator {validator_id} command must be {expected_command!r}")
        if validator.get("required_for_closure") is not True:
            errors.append(f"{label}: validator {validator_id} must be required_for_closure")


def _validate_allowed_transition_graph(
    receipts: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    graph = receipts.get("allowed_transition_graph")
    if not isinstance(graph, list):
        errors.append(f"{label}: allowed_transition_graph must be a list")
        return
    graph_pairs: set[tuple[str, str]] = set()
    for transition in graph:
        if not isinstance(transition, dict):
            errors.append(f"{label}: allowed transition entries must be objects")
            continue
        pair = (str(transition.get("from_state")), str(transition.get("to_state")))
        graph_pairs.add(pair)
        if pair not in ALLOWED_TRANSITIONS:
            errors.append(f"{label}: transition {pair[0]} -> {pair[1]} is not allowed")
        if transition.get("requires_evidence") is not True:
            errors.append(f"{label}: transition {pair[0]} -> {pair[1]} must require evidence")
        if transition.get("external_effect") is not False:
            errors.append(f"{label}: transition {pair[0]} -> {pair[1]} must have external_effect false")
    missing_pairs = sorted(ALLOWED_TRANSITIONS - graph_pairs)
    if missing_pairs:
        formatted = [f"{from_state}->{to_state}" for from_state, to_state in missing_pairs]
        errors.append(f"{label}: allowed transition graph missing pairs {formatted}")


def _validate_receipt(
    receipt: dict[str, Any],
    component: dict[str, Any],
    errors: list[str],
    label: str,
) -> None:
    component_id = str(component.get("id", "<missing>"))
    from_state = str(receipt.get("from_state"))
    to_state = str(receipt.get("to_state"))
    pair = (from_state, to_state)
    if pair not in ALLOWED_TRANSITIONS:
        errors.append(f"{label}: component {component_id} transition {from_state} -> {to_state} is not allowed")
    if to_state in DISALLOWED_FOUNDATION_TARGET_STATES:
        errors.append(f"{label}: component {component_id} cannot target {to_state} in foundation mode")
    if receipt.get("to_state") != component.get("lifecycle_state"):
        errors.append(
            f"{label}: component {component_id} receipt to_state must match registry lifecycle_state {component.get('lifecycle_state')}"
        )
    if receipt.get("wiring_state") != component.get("wiring_state"):
        errors.append(
            f"{label}: component {component_id} receipt wiring_state must match registry wiring_state {component.get('wiring_state')}"
        )
    if receipt.get("authority_level") != component.get("authority_level"):
        errors.append(
            f"{label}: component {component_id} receipt authority_level must match registry authority_level {component.get('authority_level')}"
        )
    if receipt.get("proof_state") != "Pass":
        errors.append(f"{label}: component {component_id} proof_state must be Pass")
    if receipt.get("receipt_is_not_execution_authority") is not True:
        errors.append(f"{label}: component {component_id} receipt_is_not_execution_authority must be true")
    if receipt.get("receipt_is_not_terminal_closure") is not True:
        errors.append(f"{label}: component {component_id} receipt_is_not_terminal_closure must be true")
    if receipt.get("external_effect") is not False:
        errors.append(f"{label}: component {component_id} external_effect must be false")
    if to_state in OPERATOR_APPROVAL_REQUIRED_TO_STATES and receipt.get("operator_approval_required") is not True:
        errors.append(f"{label}: component {component_id} transition to {to_state} must require operator approval")
    blocked_actions = set(_string_list(receipt.get("blocked_actions")))
    if "terminal_closure" not in blocked_actions:
        errors.append(f"{label}: component {component_id} blocked_actions must include terminal_closure")
    _validate_guardrails(receipt, component_id, errors, label)
    _validate_evidence_refs(receipt, component_id, errors, label)


def _validate_guardrails(
    receipt: dict[str, Any],
    component_id: str,
    errors: list[str],
    label: str,
) -> None:
    guardrails = receipt.get("authority_guardrails")
    if not isinstance(guardrails, dict):
        errors.append(f"{label}: component {component_id} authority_guardrails must be an object")
        return
    for flag_name in LIVE_GUARDRAIL_FLAGS:
        if guardrails.get(flag_name) is not False:
            errors.append(f"{label}: component {component_id} authority_guardrails.{flag_name} must be false")


def _validate_evidence_refs(
    receipt: dict[str, Any],
    component_id: str,
    errors: list[str],
    label: str,
) -> None:
    evidence_refs = _string_list(receipt.get("evidence_refs"))
    if not evidence_refs:
        errors.append(f"{label}: component {component_id} evidence_refs must not be empty")
    for evidence_ref in evidence_refs:
        if not (REPO_ROOT / evidence_ref).exists():
            errors.append(f"{label}: component {component_id} evidence_ref missing on disk: {evidence_ref}")
    validator_refs = _string_list(receipt.get("required_validator_refs"))
    if "component_registry_validator" not in validator_refs:
        errors.append(f"{label}: component {component_id} must require component_registry_validator")


def _component_by_id(
    registry: dict[str, Any],
    errors: list[str],
    label: str,
) -> dict[str, dict[str, Any]]:
    components = registry.get("components")
    if not isinstance(components, list):
        errors.append(f"{label}: registry components must be a list")
        return {}
    result: dict[str, dict[str, Any]] = {}
    for component in components:
        if not isinstance(component, dict):
            errors.append(f"{label}: registry component entries must be objects")
            continue
        component_id = component.get("id")
        if not isinstance(component_id, str) or not component_id:
            errors.append(f"{label}: registry component entries must carry id")
            continue
        result[component_id] = component
    return result


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError("non-finite JSON constants are not permitted")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse lifecycle transition receipt validation arguments."""

    parser = argparse.ArgumentParser(description="Validate Component Harness lifecycle transition receipts.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--receipts", default=str(DEFAULT_RECEIPTS))
    parser.add_argument("--registry", default=str(DEFAULT_REGISTRY))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for lifecycle transition receipt validation."""

    args = parse_args(argv)
    validation = validate_component_lifecycle_transition_receipts(
        schema_path=Path(args.schema),
        receipt_path=Path(args.receipts),
        registry_path=Path(args.registry),
    )
    write_component_lifecycle_transition_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("COMPONENT LIFECYCLE TRANSITION RECEIPTS VALID")
    else:
        print(f"COMPONENT LIFECYCLE TRANSITION RECEIPTS INVALID errors={list(validation.errors)}")
    return 0 if validation.ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
