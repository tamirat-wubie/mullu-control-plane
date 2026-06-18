#!/usr/bin/env python3
"""Validate the ReadOnlyWorkerBinding contract.

Purpose: verify the first Foundation Mode read-only worker path selection,
authority denials, receipt bindings, recovery refs, and no-dispatch boundary.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - The first worker path is local repo inspection.
  - Runtime dispatch, network, secrets, connector authority, writes, raw output
    retention, and terminal closure remain denied.
  - Worker failure receipt emission is mandatory before runtime admission.
  - Mfidel atomicity remains preserved.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "read_only_worker_binding.schema.json"
DEFAULT_BINDING_PATH = WORKSPACE_ROOT / "examples" / "read_only_worker_binding.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-binding:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker Binding"
EXPECTED_BINDING_VERSION = "read_only_worker_binding.v1"
EXPECTED_WORKER_PATH = "read_only_repo_inspection"
REQUIRED_RECEIPT_SCHEMA_REFS = (
    "schemas/worker_mesh.schema.json",
    "schemas/worker_failure_receipt.schema.json",
)
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_binding.schema.json",
    "examples/read_only_worker_binding.foundation.json",
    "scripts/validate_read_only_worker_binding.py",
    "tests/test_validate_read_only_worker_binding.py",
    "docs/80_read_only_worker_binding_contract.md",
    "docs/maps/MULLUSI_GAP_REGISTER.md",
    "examples/sdlc/requirement_read_only_worker_binding_20260614.json",
    "examples/sdlc/design_read_only_worker_binding_20260614.json",
)
DENIED_AUTHORITY_FIELDS = (
    "runtime_dispatch_allowed",
    "external_network_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "connector_authority_allowed",
    "terminal_closure_allowed",
    "raw_output_retention_allowed",
)


class ReadOnlyWorkerBindingError(ValueError):
    """Raised when a ReadOnlyWorkerBinding artifact cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerBindingError(f"{label} must be a JSON object")
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
            "binding_id",
            "binding_version",
            "selected_worker_path",
            "selection_state",
            "authority_scope",
            "worker_contract",
            "contract_summary",
            "governance_refs",
            "receipt_envelope",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
        binding_version_schema = properties.get("binding_version", {})
        if not isinstance(binding_version_schema, dict) or binding_version_schema.get("const") != EXPECTED_BINDING_VERSION:
            errors.append("schema property binding_version must const read_only_worker_binding.v1")
    return errors


def validate_binding_record(record: Any, schema: dict[str, Any] | None = None) -> list[str]:
    """Return deterministic validation errors for one ReadOnlyWorkerBinding payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("read-only worker binding must be a JSON object")
        return errors

    if record.get("binding_version") != EXPECTED_BINDING_VERSION:
        errors.append("binding_version must match read_only_worker_binding.v1")
    if record.get("selected_worker_path") != EXPECTED_WORKER_PATH:
        errors.append("selected_worker_path must be read_only_repo_inspection")
    _validate_authority_scope(record.get("authority_scope"), errors)
    _validate_worker_contract(record.get("worker_contract"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_binding(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    binding_path: Path = DEFAULT_BINDING_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode binding."""

    schema = _load_schema(schema_path)
    binding = load_json_object(binding_path, "ReadOnlyWorkerBinding")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_binding_record(binding, schema))
    return errors


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def build_mutated_binding(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default binding for tests."""

    binding = load_json_object(DEFAULT_BINDING_PATH, "ReadOnlyWorkerBinding")
    mutated = deepcopy(binding)
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


def _validate_authority_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("authority_scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append("authority_scope.read_only must be true")
    for field_name in DENIED_AUTHORITY_FIELDS:
        if scope.get(field_name) is not False:
            errors.append(f"authority_scope.{field_name} must be false")
    if scope.get("mfidel_atomicity_preserved") is not True:
        errors.append("authority_scope.mfidel_atomicity_preserved must be true")


def _validate_worker_contract(contract: Any, errors: list[str]) -> None:
    if not isinstance(contract, dict):
        errors.append("worker_contract must be an object")
        return
    if contract.get("worker_id") != "worker_local_read_only_repo_inspection":
        errors.append("worker_contract.worker_id must select worker_local_read_only_repo_inspection")
    if contract.get("capability") != "read_only_repo_inspection":
        errors.append("worker_contract.capability must be read_only_repo_inspection")
    if contract.get("operation_family") != "local_repo_inspection":
        errors.append("worker_contract.operation_family must be local_repo_inspection")
    network_allowlist = contract.get("network_allowlist")
    if network_allowlist != []:
        errors.append("worker_contract.network_allowlist must be empty")
    _require_subset(contract, "receipt_schema_refs", REQUIRED_RECEIPT_SCHEMA_REFS, errors)
    _require_forbidden_prefix(contract, "forbidden_input_refs", ("secret://", "network://", "tenant://other"), errors)
    _require_forbidden_prefix(
        contract,
        "forbidden_output_refs",
        ("raw-output://", "secret://", "external-request://", "filesystem-write://"),
        errors,
    )
    allowed_outputs = contract.get("allowed_output_refs")
    if isinstance(allowed_outputs, list):
        for output_ref in allowed_outputs:
            if isinstance(output_ref, str) and output_ref.startswith(("secret://", "external-request://", "filesystem-write://")):
                errors.append(f"worker_contract.allowed_output_refs contains forbidden effect ref: {output_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    contract = record.get("worker_contract")
    summary = record.get("contract_summary")
    if not isinstance(contract, dict) or not isinstance(summary, dict):
        errors.append("worker_contract and contract_summary must be objects")
        return
    counted_fields = {
        "allowed_input_count": contract.get("allowed_input_refs"),
        "forbidden_input_count": contract.get("forbidden_input_refs"),
        "network_allowlist_count": contract.get("network_allowlist"),
        "allowed_output_count": contract.get("allowed_output_refs"),
        "forbidden_output_count": contract.get("forbidden_output_refs"),
        "receipt_schema_count": contract.get("receipt_schema_refs"),
        "verification_ref_count": contract.get("verification_refs"),
        "rollback_ref_count": contract.get("rollback_refs"),
        "recovery_ref_count": contract.get("recovery_refs"),
    }
    for summary_field, collection in counted_fields.items():
        if isinstance(collection, list) and summary.get(summary_field) != len(collection):
            errors.append(f"contract_summary.{summary_field} must match {summary_field.removesuffix('_count')} list length")


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def _require_forbidden_prefix(record: dict[str, Any], field_name: str, prefixes: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for prefix in prefixes:
        if not any(isinstance(value, str) and value.startswith(prefix) for value in values):
            errors.append(f"{field_name} missing forbidden boundary prefix: {prefix}")


def main(argv: list[str] | None = None) -> int:
    """Validate ReadOnlyWorkerBinding artifacts from the command line."""

    parser = argparse.ArgumentParser(description="Validate ReadOnlyWorkerBinding contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--binding", type=Path, default=DEFAULT_BINDING_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_binding(args.schema, args.binding)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "read_only_worker_binding_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "binding_path": workspace_display_path(args.binding),
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
        print("[PASS] read_only_worker_binding")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
