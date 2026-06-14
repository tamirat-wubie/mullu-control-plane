#!/usr/bin/env python3
"""Validate the ProblemStar compilation receipt contract.

Purpose: verify the public receipt that proves Phi-GPS v3 ProblemCompiler
separation before solver routing.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - ProblemStar field order preserves the Phi-GPS v2.2 kernel object.
  - Evidence, assumptions, unknowns, contradictions, actions, and proof
    obligations remain separated.
  - The receipt never grants runtime, connector, deployment, or terminal
    closure authority.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "problem_star_compilation_receipt.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "problem_star_compilation_receipt.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:problem-star-compilation-receipt:1"
EXPECTED_SCHEMA_TITLE = "ProblemStar Compilation Receipt"
EXPECTED_RECEIPT_VERSION = "problem_star_compilation_receipt.v1"
EXPECTED_COMPILER_NAME = "Phi-GPS ProblemCompiler"
EXPECTED_SCHEMA_VERSION = "phi2-gps-v3"
EXPECTED_KERNEL_SCHEMA_VERSION = "phi2-gps-v2.2"
EXPECTED_FIELD_ORDER = ("W", "B", "O", "I", "G", "U", "Lambda", "N", "A_e", "A_w", "T", "R", "K", "Pi")
REQUIRED_SEPARATED_SURFACES = (
    "evidence",
    "assumptions",
    "unknowns",
    "contradictions",
    "goals",
    "constraints",
    "risks",
    "available_actions",
    "proof_obligations",
)
FALSE_AUTHORITY_GUARDS = (
    "runtime_registration_claimed",
    "execution_authority_granted",
    "connector_authority_granted",
    "deployment_claimed",
    "terminal_closure",
)
TRUE_COMPILATION_GUARDS = (
    "evidence_assumption_separated",
    "contradictions_append_only",
    "proof_obligations_do_not_modify_identity_or_laws",
    "mfidel_atomicity_preserved",
)
RECEIPT_PREFIXES = {
    "uao_ref": "uao://",
    "causal_decision_trace_ref": "trace://",
    "receipt_ref": "receipt://",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/problem_star_compilation_receipt.schema.json",
    "examples/problem_star_compilation_receipt.foundation.json",
    "scripts/validate_problem_star_compilation_receipt.py",
    "tests/test_validate_problem_star_compilation_receipt.py",
    "examples/sdlc/requirement_problem_star_compilation_receipt_20260614.json",
    "examples/sdlc/design_problem_star_compilation_receipt_20260614.json",
)


class ProblemStarCompilationReceiptError(ValueError):
    """Raised when a ProblemStar compilation receipt cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ProblemStarCompilationReceiptError(f"{label} must be a JSON object")
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
            "receipt_id",
            "receipt_version",
            "compiler_name",
            "problem_id",
            "kernel_draft",
            "separated_surfaces",
            "governance_guards",
            "receipt_envelope",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
        errors.extend(_const_property_errors(properties, "receipt_version", EXPECTED_RECEIPT_VERSION))
        errors.extend(_const_property_errors(properties, "compiler_name", EXPECTED_COMPILER_NAME))
        errors.extend(_const_property_errors(properties, "schema_version", EXPECTED_SCHEMA_VERSION))
        errors.extend(_const_property_errors(properties, "kernel_schema_version", EXPECTED_KERNEL_SCHEMA_VERSION))
    return errors


def validate_receipt_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one receipt payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("receipt must be a JSON object")
        return errors

    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match problem_star_compilation_receipt.v1")
    if record.get("compiler_name") != EXPECTED_COMPILER_NAME:
        errors.append("compiler_name must remain Phi-GPS ProblemCompiler")
    if record.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        errors.append("schema_version must remain phi2-gps-v3")
    if record.get("kernel_schema_version") != EXPECTED_KERNEL_SCHEMA_VERSION:
        errors.append("kernel_schema_version must remain phi2-gps-v2.2")

    _validate_kernel_draft(record.get("kernel_draft"), record.get("problem_id"), errors)
    _validate_separated_surfaces(record.get("separated_surfaces"), errors)
    _validate_governance_guards(record.get("governance_guards"), errors)
    _validate_receipt_envelope(record.get("receipt_envelope"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_receipt(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode receipt."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "ProblemStar compilation receipt")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_receipt_record(receipt, schema))
    return errors


def build_mutated_receipt(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default receipt for tests."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "ProblemStar compilation receipt")
    mutated = deepcopy(receipt)
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


def _validate_kernel_draft(kernel_draft: Any, problem_id: Any, errors: list[str]) -> None:
    if not isinstance(kernel_draft, dict):
        errors.append("kernel_draft must be an object")
        return
    if kernel_draft.get("problem_id") != problem_id:
        errors.append("kernel_draft.problem_id must match receipt problem_id")
    if tuple(kernel_draft.get("field_order", ())) != EXPECTED_FIELD_ORDER:
        errors.append("kernel_draft.field_order must preserve canonical P* order")
    fields = kernel_draft.get("fields")
    if not isinstance(fields, dict):
        errors.append("kernel_draft.fields must be an object")
        return
    if tuple(fields.keys()) != EXPECTED_FIELD_ORDER:
        errors.append("kernel_draft.fields must preserve canonical P* object order")
    unknown_fields = kernel_draft.get("unknown_fields")
    if isinstance(unknown_fields, list):
        unknown_set = set(unknown_fields)
        if unknown_set - set(EXPECTED_FIELD_ORDER):
            errors.append("kernel_draft.unknown_fields contains non-canonical field names")
        for field_name in unknown_fields:
            field = fields.get(field_name)
            if isinstance(field, dict) and field.get("status") not in ("unknown", "conflicting", "partial"):
                errors.append(f"kernel_draft.unknown_fields includes resolved field: {field_name}")


def _validate_separated_surfaces(surfaces: Any, errors: list[str]) -> None:
    if not isinstance(surfaces, dict):
        errors.append("separated_surfaces must be an object")
        return
    for surface_name in REQUIRED_SEPARATED_SURFACES:
        if surface_name not in surfaces:
            errors.append(f"separated_surfaces missing: {surface_name}")
        elif not isinstance(surfaces[surface_name], list):
            errors.append(f"separated_surfaces.{surface_name} must be a list")
    if surfaces.get("evidence") == surfaces.get("assumptions"):
        errors.append("evidence and assumptions must remain distinct arrays")
    if not surfaces.get("proof_obligations"):
        errors.append("proof_obligations must not be empty")
    if not surfaces.get("available_actions"):
        errors.append("available_actions must not be empty")


def _validate_governance_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("governance_guards must be an object")
        return
    for guard_name in FALSE_AUTHORITY_GUARDS:
        if guards.get(guard_name) is not False:
            errors.append(f"governance_guards.{guard_name} must be false")
    for guard_name in TRUE_COMPILATION_GUARDS:
        if guards.get(guard_name) is not True:
            errors.append(f"governance_guards.{guard_name} must be true")


def _validate_receipt_envelope(envelope: Any, errors: list[str]) -> None:
    if not isinstance(envelope, dict):
        errors.append("receipt_envelope must be an object")
        return
    for field_name, prefix in RECEIPT_PREFIXES.items():
        value = envelope.get(field_name)
        if not isinstance(value, str) or not value.startswith(prefix):
            errors.append(f"receipt_envelope.{field_name} must use {prefix} prefix")


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def _const_property_errors(properties: dict[str, Any], field_name: str, expected_value: Any) -> list[str]:
    property_schema = properties.get(field_name)
    if not isinstance(property_schema, dict):
        return [f"schema property missing: {field_name}"]
    if property_schema.get("const") != expected_value:
        return [f"schema property {field_name} must const {expected_value!r}"]
    return []


def main(argv: list[str] | None = None) -> int:
    """Validate the ProblemStar compilation receipt from the command line."""

    parser = argparse.ArgumentParser(description="Validate ProblemStar compilation receipt.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_receipt(args.schema, args.receipt)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "problem_star_compilation_receipt_validation",
                    "schema_path": str(args.schema.relative_to(WORKSPACE_ROOT)),
                    "receipt_path": str(args.receipt.relative_to(WORKSPACE_ROOT)),
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
        print("[PASS] problem_star_compilation_receipt")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
