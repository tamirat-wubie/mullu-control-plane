#!/usr/bin/env python3
"""Validate the ReadOnlyWorkerLeasePreflight contract.

Purpose: verify that the selected read-only worker path is bound to a temporal
lease preflight envelope while Foundation Mode still denies runtime dispatch.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, scripts/validate_schemas.py, and the
ReadOnlyWorkerBinding validator.
Invariants:
  - Validation is read-only and deterministic.
  - The preflight applies only to read_only_repo_inspection.
  - Runtime dispatch remains denied until temporal lease evidence exists.
  - Fencing token, positive sequence, runtime clock, worker mesh, and worker
    failure receipt bindings remain mandatory.
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

from scripts.validate_read_only_worker_binding import (  # noqa: E402
    DEFAULT_BINDING_PATH,
    EXPECTED_WORKER_PATH,
    load_json_object as load_binding_json_object,
    validate_binding_record,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "read_only_worker_lease_preflight.schema.json"
DEFAULT_PREFLIGHT_PATH = WORKSPACE_ROOT / "examples" / "read_only_worker_lease_preflight.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-lease-preflight:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker Lease Preflight"
EXPECTED_PREFLIGHT_VERSION = "read_only_worker_lease_preflight.v1"
EXPECTED_BINDING_REF = "examples/read_only_worker_binding.foundation.json"
EXPECTED_WORKER_ID = "worker_local_read_only_repo_inspection"
EXPECTED_RUNTIME_CLOCK_REF = "gateway.temporal_kernel.TrustedClock"
EXPECTED_TEMPORAL_SCHEMA_REF = "schemas/temporal_lease_window_receipt.schema.json"
REQUIRED_RECEIPT_REFS = {
    "read_only_worker_binding_schema": "schemas/read_only_worker_binding.schema.json",
    "read_only_worker_lease_preflight_schema": "schemas/read_only_worker_lease_preflight.schema.json",
    "temporal_lease_window_receipt_schema": EXPECTED_TEMPORAL_SCHEMA_REF,
    "worker_mesh_schema": "schemas/worker_mesh.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_lease_preflight.schema.json",
    "examples/read_only_worker_lease_preflight.foundation.json",
    "scripts/validate_read_only_worker_lease_preflight.py",
    "tests/test_validate_read_only_worker_lease_preflight.py",
    "schemas/read_only_worker_binding.schema.json",
    "examples/read_only_worker_binding.foundation.json",
    "schemas/temporal_lease_window_receipt.schema.json",
    "docs/80_read_only_worker_binding_contract.md",
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


class ReadOnlyWorkerLeasePreflightError(ValueError):
    """Raised when a ReadOnlyWorkerLeasePreflight artifact cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerLeasePreflightError(f"{label} must be a JSON object")
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
            "preflight_id",
            "preflight_version",
            "binding_ref",
            "selected_worker_path",
            "authority_scope",
            "lease_contract",
            "dispatch_gate",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_preflight_record(
    record: Any,
    schema: dict[str, Any] | None = None,
    binding: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one lease preflight payload."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("read-only worker lease preflight must be a JSON object")
        return errors

    binding_payload = binding or load_binding_json_object(DEFAULT_BINDING_PATH, "ReadOnlyWorkerBinding")
    errors.extend(f"binding: {error}" for error in validate_binding_record(binding_payload))
    if record.get("preflight_version") != EXPECTED_PREFLIGHT_VERSION:
        errors.append("preflight_version must match read_only_worker_lease_preflight.v1")
    if record.get("binding_ref") != EXPECTED_BINDING_REF:
        errors.append("binding_ref must point to the Foundation ReadOnlyWorkerBinding example")
    if record.get("selected_worker_path") != EXPECTED_WORKER_PATH:
        errors.append("selected_worker_path must be read_only_repo_inspection")
    if binding_payload.get("selected_worker_path") != record.get("selected_worker_path"):
        errors.append("preflight selected_worker_path must match binding selected_worker_path")
    _validate_authority_scope(record.get("authority_scope"), errors)
    _validate_lease_contract(record.get("lease_contract"), binding_payload, errors)
    _validate_dispatch_gate(record.get("dispatch_gate"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_preflight(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    preflight_path: Path = DEFAULT_PREFLIGHT_PATH,
    binding_path: Path = DEFAULT_BINDING_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode preflight."""

    schema = _load_schema(schema_path)
    preflight = load_json_object(preflight_path, "ReadOnlyWorkerLeasePreflight")
    binding = load_binding_json_object(binding_path, "ReadOnlyWorkerBinding")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_preflight_record(preflight, schema, binding))
    return errors


def build_mutated_preflight(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default preflight for tests."""

    preflight = load_json_object(DEFAULT_PREFLIGHT_PATH, "ReadOnlyWorkerLeasePreflight")
    mutated = deepcopy(preflight)
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


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _validate_authority_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("authority_scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append("authority_scope.read_only must be true")
    if scope.get("lease_preflight_required") is not True:
        errors.append("authority_scope.lease_preflight_required must be true")
    for field_name in DENIED_AUTHORITY_FIELDS:
        if scope.get(field_name) is not False:
            errors.append(f"authority_scope.{field_name} must be false")
    if scope.get("mfidel_atomicity_preserved") is not True:
        errors.append("authority_scope.mfidel_atomicity_preserved must be true")


def _validate_lease_contract(contract: Any, binding: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(contract, dict):
        errors.append("lease_contract must be an object")
        return
    binding_contract = binding.get("worker_contract", {})
    if contract.get("worker_id") != EXPECTED_WORKER_ID:
        errors.append("lease_contract.worker_id must select worker_local_read_only_repo_inspection")
    if contract.get("worker_id") != binding_contract.get("worker_id"):
        errors.append("lease_contract.worker_id must match binding worker_id")
    if contract.get("capability") != EXPECTED_WORKER_PATH:
        errors.append("lease_contract.capability must be read_only_repo_inspection")
    if contract.get("capability") != binding_contract.get("capability"):
        errors.append("lease_contract.capability must match binding capability")
    if contract.get("operation_family") != "local_repo_inspection":
        errors.append("lease_contract.operation_family must be local_repo_inspection")
    if contract.get("runtime_clock_ref") != EXPECTED_RUNTIME_CLOCK_REF:
        errors.append("lease_contract.runtime_clock_ref must bind TrustedClock")
    if contract.get("temporal_lease_window_schema_ref") != EXPECTED_TEMPORAL_SCHEMA_REF:
        errors.append("lease_contract.temporal_lease_window_schema_ref must bind temporal lease window receipt")
    if contract.get("fencing_token_required") is not True:
        errors.append("lease_contract.fencing_token_required must be true")
    if contract.get("positive_sequence_required") is not True:
        errors.append("lease_contract.positive_sequence_required must be true")
    allowed_patterns = contract.get("allowed_resource_patterns")
    if not isinstance(allowed_patterns, list) or not allowed_patterns:
        errors.append("lease_contract.allowed_resource_patterns must be a non-empty list")
    elif not all(isinstance(value, str) and value.startswith("repo://local/") for value in allowed_patterns):
        errors.append("lease_contract.allowed_resource_patterns must stay under repo://local/")


def _validate_dispatch_gate(gate: Any, errors: list[str]) -> None:
    if not isinstance(gate, dict):
        errors.append("dispatch_gate must be an object")
        return
    if gate.get("dispatch_admitted") is not False:
        errors.append("dispatch_gate.dispatch_admitted must be false")
    if gate.get("foundation_mode") is not True:
        errors.append("dispatch_gate.foundation_mode must be true")
    if gate.get("blocked_without_lease_receipt") is not True:
        errors.append("dispatch_gate.blocked_without_lease_receipt must be true")
    if gate.get("missing_lease_reason") != "lease_snapshot_required":
        errors.append("dispatch_gate.missing_lease_reason must be lease_snapshot_required")
    if gate.get("worker_failure_receipt_required_on_failure") is not True:
        errors.append("dispatch_gate.worker_failure_receipt_required_on_failure must be true")
    if gate.get("terminal_closure_required") is not True:
        errors.append("dispatch_gate.terminal_closure_required must be true")
    statuses = gate.get("required_temporal_statuses")
    if not isinstance(statuses, list) or "lease_active" not in statuses:
        errors.append("dispatch_gate.required_temporal_statuses must include lease_active")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    contract = record.get("lease_contract")
    gate = record.get("dispatch_gate")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(contract, dict) or not isinstance(gate, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("lease_contract, dispatch_gate, receipt_refs, and contract_summary must be objects")
        return
    expected_counts = {
        "allowed_resource_pattern_count": len(contract.get("allowed_resource_patterns", []))
        if isinstance(contract.get("allowed_resource_patterns"), list)
        else None,
        "required_temporal_status_count": len(gate.get("required_temporal_statuses", []))
        if isinstance(gate.get("required_temporal_statuses"), list)
        else None,
        "receipt_ref_count": len(refs),
        "evidence_ref_count": len(record.get("evidence_refs", []))
        if isinstance(record.get("evidence_refs"), list)
        else None,
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate ReadOnlyWorkerLeasePreflight artifacts from the command line."""

    parser = argparse.ArgumentParser(description="Validate ReadOnlyWorkerLeasePreflight contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT_PATH)
    parser.add_argument("--binding", type=Path, default=DEFAULT_BINDING_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_preflight(args.schema, args.preflight, args.binding)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "read_only_worker_lease_preflight_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "preflight_path": workspace_display_path(args.preflight),
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
        print("[PASS] read_only_worker_lease_preflight")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
