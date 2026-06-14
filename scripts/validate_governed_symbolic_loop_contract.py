#!/usr/bin/env python3
"""Validate the governed symbolic loop contract.

Purpose: verify the Foundation Mode contract for a platform-wide governed
symbolic loop after read-model registry admission and before runtime
registration or authority admission.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - The contract may claim read-model registry admission only.
  - The contract is not a runtime loop registration.
  - No execution, connector, deployment, or terminal closure authority is granted.
  - Effect-bearing paths retain UAO, Phi_gov, rollback, rejection, and learning gates.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "governed_symbolic_loop_contract.schema.json"
DEFAULT_CONTRACT_PATH = WORKSPACE_ROOT / "examples" / "governed_symbolic_loop_contract.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:governed-symbolic-loop-contract:1"
EXPECTED_SCHEMA_TITLE = "Governed Symbolic Loop Contract"
EXPECTED_CONTRACT_VERSION = "governed_symbolic_loop_contract.v1"
EXPECTED_SURFACE = "foundation_governed_symbolic_loop_contract"
EXPECTED_SOLVER_OUTCOME = "AwaitingEvidence"
EXPECTED_ACTION_CLASSES = ("epistemic", "effect_bearing", "hybrid")
EXPECTED_PHASES = (
    "problem_compile",
    "action_classification",
    "governance_preflight",
    "capability_routing",
    "execution_or_observation",
    "verification",
    "receipt_emission",
    "rollback_or_recovery",
    "learning_admission",
)
REQUIRED_AUTHORITY_REFS = (
    "uao_policy_ref",
    "phi_gov_authority_ref",
    "life_meaning_judgment_ref",
    "operator_registration_decision_ref",
)
REQUIRED_EVIDENCE_REFS = (
    "problem_star_compilation_receipt",
    "action_classification_receipt",
    "capability_admission_receipt",
    "verification_receipt",
    "rollback_or_recovery_handoff_receipt",
    "learning_admission_receipt",
)
REQUIRED_CONTRACT_EVIDENCE_REFS = (
    "schemas/governed_symbolic_loop_contract.schema.json",
    "examples/governed_symbolic_loop_contract.foundation.json",
    "scripts/validate_governed_symbolic_loop_contract.py",
    "tests/test_validate_governed_symbolic_loop_contract.py",
    "examples/sdlc/requirement_governed_symbolic_loop_20260614.json",
    "examples/sdlc/design_governed_symbolic_loop_20260614.json",
)
TRUE_EFFECT_GUARDS = (
    "uao_required",
    "phi_gov_required",
    "life_meaning_judgment_required",
    "rollback_or_recovery_required",
    "rejected_deltas_logged",
    "raw_reasoning_rejected",
    "learning_after_verification_only",
    "mfidel_atomicity_preserved",
)
FALSE_RUNTIME_GUARDS = (
    "runtime_registration_claimed",
    "execution_authority_granted",
    "connector_authority_granted",
    "deployment_claimed",
    "terminal_closure",
)
RECEIPT_PREFIXES = {
    "uao_ref": "uao://",
    "causal_decision_trace_ref": "trace://",
    "receipt_ref": "receipt://",
}


class GovernedSymbolicLoopContractError(ValueError):
    """Raised when the governed symbolic loop contract cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise GovernedSymbolicLoopContractError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema artifact errors."""

    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")
    required_fields = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required_fields, list):
        errors.append("schema required field must be a list")
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
    if isinstance(required_fields, list) and isinstance(properties, dict):
        for field_name in (
            "contract_id",
            "contract_version",
            "surface",
            "solver_outcome",
            "action_classes",
            "canonical_phases",
            "effect_bearing_guards",
            "non_runtime_guards",
            "receipt_envelope",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
        errors.extend(_const_property_errors(properties, "contract_version", EXPECTED_CONTRACT_VERSION))
        errors.extend(_const_property_errors(properties, "surface", EXPECTED_SURFACE))
    return errors


def validate_contract_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one contract payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("contract must be a JSON object")
        return errors

    if record.get("contract_version") != EXPECTED_CONTRACT_VERSION:
        errors.append("contract_version must match governed symbolic loop contract v1")
    if record.get("surface") != EXPECTED_SURFACE:
        errors.append("surface must remain the Foundation Mode governed symbolic loop contract")
    if record.get("solver_outcome") != EXPECTED_SOLVER_OUTCOME:
        errors.append("solver_outcome must remain AwaitingEvidence before runtime admission")
    if tuple(record.get("action_classes", ())) != EXPECTED_ACTION_CLASSES:
        errors.append("action_classes must preserve epistemic, effect_bearing, hybrid order")
    if tuple(record.get("canonical_phases", ())) != EXPECTED_PHASES:
        errors.append("canonical_phases must preserve governed episode order")

    _require_subset(record, "required_authority", REQUIRED_AUTHORITY_REFS, errors)
    _require_subset(record, "required_evidence", REQUIRED_EVIDENCE_REFS, errors)
    _require_subset(record, "evidence_refs", REQUIRED_CONTRACT_EVIDENCE_REFS, errors)
    _validate_effect_guards(record.get("effect_bearing_guards"), errors)
    _validate_runtime_guards(record.get("non_runtime_guards"), errors)
    _validate_receipt_envelope(record.get("receipt_envelope"), errors)

    if not record.get("rollback_plan"):
        errors.append("rollback_plan is required")
    if not record.get("next_action"):
        errors.append("next_action is required")
    return errors


def validate_contract(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode contract."""

    schema = _load_schema(schema_path)
    contract = load_json_object(contract_path, "governed symbolic loop contract")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_contract_record(contract, schema))
    return errors


def build_mutated_contract(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default contract for tests."""

    contract = load_json_object(DEFAULT_CONTRACT_PATH, "governed symbolic loop contract")
    mutated = deepcopy(contract)
    for dotted_key, value in updates.items():
        target = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            next_target = target.get(segment)
            if not isinstance(next_target, dict):
                next_target = {}
                target[segment] = next_target
            target = next_target
        target[segments[-1]] = value
    return mutated


def _const_property_errors(
    properties: dict[str, Any],
    field_name: str,
    expected_value: Any,
) -> list[str]:
    property_schema = properties.get(field_name)
    if not isinstance(property_schema, dict):
        return [f"schema property missing: {field_name}"]
    if property_schema.get("const") != expected_value:
        return [f"schema property {field_name} must const {expected_value!r}"]
    return []


def _require_subset(
    record: dict[str, Any],
    field_name: str,
    required_values: tuple[str, ...],
    errors: list[str],
) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    missing_values = sorted(set(required_values) - set(values))
    for missing_value in missing_values:
        errors.append(f"{field_name} missing required ref: {missing_value}")


def _validate_effect_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("effect_bearing_guards must be an object")
        return
    for guard_name in TRUE_EFFECT_GUARDS:
        if guards.get(guard_name) is not True:
            errors.append(f"effect_bearing_guards.{guard_name} must be true")


def _validate_runtime_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("non_runtime_guards must be an object")
        return
    if guards.get("read_only") is not True:
        errors.append("non_runtime_guards.read_only must be true")
    if guards.get("read_model_registry_admission_claimed") is not True:
        errors.append("non_runtime_guards.read_model_registry_admission_claimed must be true")
    for guard_name in FALSE_RUNTIME_GUARDS:
        if guards.get(guard_name) is not False:
            errors.append(f"non_runtime_guards.{guard_name} must be false")


def _validate_receipt_envelope(envelope: Any, errors: list[str]) -> None:
    if not isinstance(envelope, dict):
        errors.append("receipt_envelope must be an object")
        return
    for field_name, prefix in RECEIPT_PREFIXES.items():
        value = envelope.get(field_name)
        if not isinstance(value, str) or not value.startswith(prefix):
            errors.append(f"receipt_envelope.{field_name} must use {prefix} prefix")


def main(argv: list[str] | None = None) -> int:
    """Validate the governed symbolic loop contract from the command line."""

    parser = argparse.ArgumentParser(description="Validate governed symbolic loop contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_contract(args.schema, args.contract)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "governed_symbolic_loop_contract_validation",
                    "schema_path": str(args.schema.relative_to(WORKSPACE_ROOT)),
                    "contract_path": str(args.contract.relative_to(WORKSPACE_ROOT)),
                    "status": "passed" if not errors else "failed",
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] governed_symbolic_loop_contract")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
