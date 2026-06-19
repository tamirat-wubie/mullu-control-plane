#!/usr/bin/env python3
"""Validate the Foundation CDG-RCCM component contract.

Purpose: verify the static component contract used by the Causal
Dependency-Gated Recursive Component Convergence Mesh before any separate
route, connector, deployment, or external-effect admission.
Governance scope: read-only deterministic validation.
Invariants:
  - The validator never executes components or convergence work.
  - Runtime guards fail closed.
  - Required evidence and receipt references are explicit.
  - The contract cannot claim route, connector, or deployment admission.
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


DEFAULT_SCHEMA_PATH = (
    WORKSPACE_ROOT
    / "mcoi"
    / "mcoi_runtime"
    / "convergence"
    / "cdg_rccm_component_contract.schema.json"
)
DEFAULT_CONTRACT_PATH = WORKSPACE_ROOT / "examples" / "cdg_rccm_component_contract.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:cdg-rccm-component-contract:1"
EXPECTED_SCHEMA_TITLE = "CDG-RCCM Component Contract"
EXPECTED_CONTRACT_VERSION = "cdg_rccm_component_contract.v1"
EXPECTED_PROTOCOL_VERSION = "cdg-rccm.v1"
EXPECTED_SURFACE = "foundation_cdg_rccm_component_contract"
REQUIRED_TRUE_GUARDS = (
    "component_self_certification_denied",
    "hidden_dependency_reads_denied",
    "direct_external_effects_denied",
    "cross_epoch_reads_denied",
    "stale_certificate_consumption_denied",
)
REQUIRED_FALSE_GUARDS = (
    "runtime_route_registration_claimed",
    "connector_authority_granted",
    "deployment_claimed",
)
REQUIRED_EVIDENCE_REFS = (
    "mcoi/mcoi_runtime/convergence/cdg_rccm_component_contract.schema.json",
    "examples/cdg_rccm_component_contract.foundation.json",
    "scripts/validate_cdg_rccm_component_contract.py",
    "mcoi/tests/test_cdg_rccm_component_contract.py",
    "mcoi/mcoi_runtime/convergence/contracts.py",
    "mcoi/mcoi_runtime/convergence/kernel.py",
    "docs/CDG_RCCM_RECURSIVE_CONVERGENCE_KERNEL.md",
    "examples/sdlc/requirement_cdg_rccm_recursive_convergence_kernel_20260618.json",
    "examples/sdlc/design_cdg_rccm_recursive_convergence_kernel_20260618.json",
)
RECEIPT_PREFIXES = {
    "uao_ref": "uao://",
    "causal_decision_trace_ref": "trace://",
    "receipt_ref": "receipt://",
}


class CdgRccmComponentContractError(ValueError):
    """Raised when a contract artifact cannot be loaded correctly."""


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise CdgRccmComponentContractError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: dict[str, Any]) -> list[str]:
    """Return deterministic schema-definition errors."""

    errors: list[str] = []
    if schema.get("$id") != EXPECTED_SCHEMA_ID:
        errors.append("schema $id is invalid")
    if schema.get("title") != EXPECTED_SCHEMA_TITLE:
        errors.append("schema title is invalid")
    if schema.get("type") != "object":
        errors.append("schema root type must be object")
    if schema.get("additionalProperties") is not False:
        errors.append("schema root must close additional properties")

    required = schema.get("required")
    properties = schema.get("properties")
    if not isinstance(required, list):
        errors.append("schema required field must be a list")
        return errors
    if not isinstance(properties, dict):
        errors.append("schema properties must be an object")
        return errors

    for field_name in (
        "contract_id",
        "contract_version",
        "protocol_version",
        "surface",
        "component_id",
        "purpose",
        "output_projections",
        "convergence_policy",
        "budgets",
        "runtime_guards",
        "receipt_envelope",
        "evidence_refs",
    ):
        if field_name not in required:
            errors.append(f"schema missing required field: {field_name}")
        if field_name not in properties:
            errors.append(f"schema missing property: {field_name}")

    errors.extend(
        _const_property_errors(properties, "contract_version", EXPECTED_CONTRACT_VERSION)
    )
    errors.extend(
        _const_property_errors(properties, "protocol_version", EXPECTED_PROTOCOL_VERSION)
    )
    errors.extend(_const_property_errors(properties, "surface", EXPECTED_SURFACE))
    return errors


def validate_contract_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic contract errors for one payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("contract must be a JSON object")
        return errors

    if record.get("contract_version") != EXPECTED_CONTRACT_VERSION:
        errors.append("contract_version must match CDG-RCCM component contract v1")
    if record.get("protocol_version") != EXPECTED_PROTOCOL_VERSION:
        errors.append("protocol_version must match cdg-rccm.v1")
    if record.get("surface") != EXPECTED_SURFACE:
        errors.append("surface must remain the Foundation CDG-RCCM component contract")

    _require_non_empty_unique_strings(record, "output_projections", errors)
    _require_non_empty_unique_strings(record, "immutable_invariants", errors)
    _require_non_empty_unique_strings(record, "local_invariants", errors)
    _require_non_empty_unique_strings(record, "boundary_contracts", errors)
    _require_required_evidence(record, errors)
    _validate_convergence_policy(record.get("convergence_policy"), errors)
    _validate_budgets(record.get("budgets"), errors)
    _validate_runtime_guards(record.get("runtime_guards"), errors)
    _validate_receipt_envelope(record.get("receipt_envelope"), errors)
    return errors


def validate_contract(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    contract_path: Path = DEFAULT_CONTRACT_PATH,
) -> list[str]:
    """Validate the schema and default Foundation contract."""

    schema = _load_schema(schema_path)
    contract = load_json_object(contract_path, "CDG-RCCM component contract")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_contract_record(contract, schema))
    return errors


def build_mutated_contract(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated contract for validator tests."""

    contract = load_json_object(DEFAULT_CONTRACT_PATH, "CDG-RCCM component contract")
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


def _require_non_empty_unique_strings(
    record: dict[str, Any],
    field_name: str,
    errors: list[str],
) -> None:
    values = record.get(field_name)
    if not isinstance(values, list) or not values:
        errors.append(f"{field_name} must be a non-empty list")
        return
    if any(not isinstance(value, str) or not value for value in values):
        errors.append(f"{field_name} must contain non-empty strings")
    if len(values) != len(set(values)):
        errors.append(f"{field_name} must not contain duplicates")


def _require_required_evidence(record: dict[str, Any], errors: list[str]) -> None:
    values = record.get("evidence_refs")
    if not isinstance(values, list):
        errors.append("evidence_refs must be a list")
        return
    for missing in sorted(set(REQUIRED_EVIDENCE_REFS) - set(values)):
        errors.append(f"evidence_refs missing required ref: {missing}")


def _validate_convergence_policy(policy: Any, errors: list[str]) -> None:
    if not isinstance(policy, dict):
        errors.append("convergence_policy must be an object")
        return
    maximum_iterations = policy.get("maximum_iterations")
    stable_iterations = policy.get("stable_iterations")
    if type(maximum_iterations) is not int or maximum_iterations < 1:
        errors.append("convergence_policy.maximum_iterations must be positive")
    if type(stable_iterations) is not int or stable_iterations < 1:
        errors.append("convergence_policy.stable_iterations must be positive")
    if policy.get("oscillation_detection") is not True:
        errors.append("convergence_policy.oscillation_detection must be true")


def _validate_budgets(budgets: Any, errors: list[str]) -> None:
    if not isinstance(budgets, dict):
        errors.append("budgets must be an object")
        return
    maximum_depth = budgets.get("maximum_depth")
    maximum_frames = budgets.get("maximum_frames")
    if type(maximum_depth) is not int or maximum_depth < 0:
        errors.append("budgets.maximum_depth must be non-negative")
    if type(maximum_frames) is not int or maximum_frames < 1:
        errors.append("budgets.maximum_frames must be positive")


def _validate_runtime_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("runtime_guards must be an object")
        return
    for guard_name in REQUIRED_TRUE_GUARDS:
        if guards.get(guard_name) is not True:
            errors.append(f"runtime_guards.{guard_name} must be true")
    for guard_name in REQUIRED_FALSE_GUARDS:
        if guards.get(guard_name) is not False:
            errors.append(f"runtime_guards.{guard_name} must be false")


def _validate_receipt_envelope(envelope: Any, errors: list[str]) -> None:
    if not isinstance(envelope, dict):
        errors.append("receipt_envelope must be an object")
        return
    for field_name, prefix in RECEIPT_PREFIXES.items():
        value = envelope.get(field_name)
        if not isinstance(value, str) or not value.startswith(prefix):
            errors.append(f"receipt_envelope.{field_name} must use {prefix} prefix")


def main(argv: list[str] | None = None) -> int:
    """Validate the default contract from the command line."""

    parser = argparse.ArgumentParser(description="Validate CDG-RCCM component contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    errors = validate_contract(args.schema, args.contract)
    receipt = {
        "receipt_id": "cdg_rccm_component_contract_validation",
        "schema_path": str(args.schema.relative_to(WORKSPACE_ROOT)),
        "contract_path": str(args.contract.relative_to(WORKSPACE_ROOT)),
        "status": "passed" if not errors else "failed",
        "errors": errors,
    }
    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
    else:
        print("[PASS] cdg_rccm_component_contract")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
