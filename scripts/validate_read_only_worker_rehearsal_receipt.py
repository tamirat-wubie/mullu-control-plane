#!/usr/bin/env python3
"""Validate the ReadOnlyWorkerRehearsalReceipt contract.

Purpose: verify local rehearsal-only evidence for the selected read-only
worker path without granting runtime dispatch or terminal closure authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers,
ReadOnlyWorkerBinding, and ReadOnlyWorkerLeasePreflight validators.
Invariants:
  - Validation is read-only and deterministic.
  - The receipt applies only to read_only_repo_inspection.
  - Runtime dispatch, network, secrets, filesystem writes, connector calls,
    raw output retention, and terminal closure remain denied.
  - Local rehearsal evidence stays under repo://local/ and evidence://local-repo/.
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
from scripts.validate_read_only_worker_lease_preflight import (  # noqa: E402
    DEFAULT_PREFLIGHT_PATH,
    load_json_object as load_preflight_json_object,
    validate_preflight_record,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "read_only_worker_rehearsal_receipt.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "read_only_worker_rehearsal_receipt.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-rehearsal-receipt:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker Rehearsal Receipt"
EXPECTED_RECEIPT_VERSION = "read_only_worker_rehearsal_receipt.v1"
EXPECTED_BINDING_REF = "examples/read_only_worker_binding.foundation.json"
EXPECTED_PREFLIGHT_REF = "examples/read_only_worker_lease_preflight.foundation.json"
EXPECTED_WORKER_ID = "worker_local_read_only_repo_inspection"
EXPECTED_OPERATION_FAMILY = "local_repo_inspection"
EXPECTED_REHEARSAL_MODE = "LOCAL_DRY_RUN"
REQUIRED_FORBIDDEN_EFFECT_REFS = (
    "network://*",
    "secret://*",
    "filesystem-write://*",
    "connector-call://*",
    "terminal-closure://*",
    "raw-output://*",
)
REQUIRED_PREFLIGHT_REFS = (
    EXPECTED_BINDING_REF,
    EXPECTED_PREFLIGHT_REF,
)
REQUIRED_RECEIPT_REFS = {
    "read_only_worker_binding_schema": "schemas/read_only_worker_binding.schema.json",
    "read_only_worker_lease_preflight_schema": "schemas/read_only_worker_lease_preflight.schema.json",
    "read_only_worker_rehearsal_receipt_schema": "schemas/read_only_worker_rehearsal_receipt.schema.json",
    "temporal_lease_window_receipt_schema": "schemas/temporal_lease_window_receipt.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "worker_mesh_schema": "schemas/worker_mesh.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_rehearsal_receipt.schema.json",
    "examples/read_only_worker_rehearsal_receipt.foundation.json",
    "scripts/validate_read_only_worker_rehearsal_receipt.py",
    "tests/test_validate_read_only_worker_rehearsal_receipt.py",
    "schemas/read_only_worker_binding.schema.json",
    "schemas/read_only_worker_lease_preflight.schema.json",
    "examples/read_only_worker_binding.foundation.json",
    "examples/read_only_worker_lease_preflight.foundation.json",
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
DENIED_RESULT_FIELDS = (
    "raw_output_included",
    "raw_secret_material_included",
    "external_effects_observed",
    "filesystem_writes_observed",
    "connector_calls_observed",
    "terminal_closure",
    "success_claim_allowed",
)


class ReadOnlyWorkerRehearsalReceiptError(ValueError):
    """Raised when a ReadOnlyWorkerRehearsalReceipt artifact cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerRehearsalReceiptError(f"{label} must be a JSON object")
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
            "binding_ref",
            "lease_preflight_ref",
            "selected_worker_path",
            "authority_scope",
            "rehearsal_contract",
            "rehearsal_result",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_rehearsal_record(
    record: Any,
    schema: dict[str, Any] | None = None,
    binding: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one rehearsal receipt."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("read-only worker rehearsal receipt must be a JSON object")
        return errors

    binding_payload = binding or load_binding_json_object(DEFAULT_BINDING_PATH, "ReadOnlyWorkerBinding")
    preflight_payload = preflight or load_preflight_json_object(DEFAULT_PREFLIGHT_PATH, "ReadOnlyWorkerLeasePreflight")
    errors.extend(f"binding: {error}" for error in validate_binding_record(binding_payload))
    errors.extend(f"preflight: {error}" for error in validate_preflight_record(preflight_payload, binding=binding_payload))

    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match read_only_worker_rehearsal_receipt.v1")
    if record.get("binding_ref") != EXPECTED_BINDING_REF:
        errors.append("binding_ref must point to the Foundation ReadOnlyWorkerBinding example")
    if record.get("lease_preflight_ref") != EXPECTED_PREFLIGHT_REF:
        errors.append("lease_preflight_ref must point to the Foundation ReadOnlyWorkerLeasePreflight example")
    if record.get("selected_worker_path") != EXPECTED_WORKER_PATH:
        errors.append("selected_worker_path must be read_only_repo_inspection")
    if binding_payload.get("selected_worker_path") != record.get("selected_worker_path"):
        errors.append("rehearsal selected_worker_path must match binding selected_worker_path")
    if preflight_payload.get("selected_worker_path") != record.get("selected_worker_path"):
        errors.append("rehearsal selected_worker_path must match preflight selected_worker_path")

    _validate_authority_scope(record.get("authority_scope"), errors)
    _validate_rehearsal_contract(record.get("rehearsal_contract"), binding_payload, preflight_payload, errors)
    _validate_rehearsal_result(record.get("rehearsal_result"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_rehearsal_receipt(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    binding_path: Path = DEFAULT_BINDING_PATH,
    preflight_path: Path = DEFAULT_PREFLIGHT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode receipt."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "ReadOnlyWorkerRehearsalReceipt")
    binding = load_binding_json_object(binding_path, "ReadOnlyWorkerBinding")
    preflight = load_preflight_json_object(preflight_path, "ReadOnlyWorkerLeasePreflight")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_rehearsal_record(receipt, schema, binding, preflight))
    return errors


def build_mutated_rehearsal(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default receipt for tests."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "ReadOnlyWorkerRehearsalReceipt")
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
    if scope.get("local_rehearsal_only") is not True:
        errors.append("authority_scope.local_rehearsal_only must be true")
    if scope.get("lease_preflight_required") is not True:
        errors.append("authority_scope.lease_preflight_required must be true")
    for field_name in DENIED_AUTHORITY_FIELDS:
        if scope.get(field_name) is not False:
            errors.append(f"authority_scope.{field_name} must be false")
    if scope.get("mfidel_atomicity_preserved") is not True:
        errors.append("authority_scope.mfidel_atomicity_preserved must be true")


def _validate_rehearsal_contract(
    contract: Any,
    binding: dict[str, Any],
    preflight: dict[str, Any],
    errors: list[str],
) -> None:
    if not isinstance(contract, dict):
        errors.append("rehearsal_contract must be an object")
        return
    binding_contract = binding.get("worker_contract", {})
    lease_contract = preflight.get("lease_contract", {})
    if contract.get("worker_id") != EXPECTED_WORKER_ID:
        errors.append("rehearsal_contract.worker_id must select worker_local_read_only_repo_inspection")
    if contract.get("worker_id") != binding_contract.get("worker_id"):
        errors.append("rehearsal_contract.worker_id must match binding worker_id")
    if contract.get("worker_id") != lease_contract.get("worker_id"):
        errors.append("rehearsal_contract.worker_id must match lease preflight worker_id")
    if contract.get("capability") != EXPECTED_WORKER_PATH:
        errors.append("rehearsal_contract.capability must be read_only_repo_inspection")
    if contract.get("capability") != binding_contract.get("capability"):
        errors.append("rehearsal_contract.capability must match binding capability")
    if contract.get("capability") != lease_contract.get("capability"):
        errors.append("rehearsal_contract.capability must match lease preflight capability")
    if contract.get("operation_family") != EXPECTED_OPERATION_FAMILY:
        errors.append("rehearsal_contract.operation_family must be local_repo_inspection")
    if contract.get("rehearsal_mode") != EXPECTED_REHEARSAL_MODE:
        errors.append("rehearsal_contract.rehearsal_mode must be LOCAL_DRY_RUN")
    if contract.get("dispatch_admitted") is not False:
        errors.append("rehearsal_contract.dispatch_admitted must be false")
    if contract.get("filesystem_snapshot_required") is not True:
        errors.append("rehearsal_contract.filesystem_snapshot_required must be true")
    _require_prefixed_refs(
        contract,
        "allowed_resource_refs",
        "repo://local/",
        "rehearsal_contract.allowed_resource_refs must stay under repo://local/",
        errors,
    )
    _require_subset(contract, "forbidden_effect_refs", REQUIRED_FORBIDDEN_EFFECT_REFS, errors)
    _require_subset(contract, "required_preflight_refs", REQUIRED_PREFLIGHT_REFS, errors)


def _validate_rehearsal_result(result: Any, errors: list[str]) -> None:
    if not isinstance(result, dict):
        errors.append("rehearsal_result must be an object")
        return
    if result.get("result_state") != "REHEARSAL_RECORDED":
        errors.append("rehearsal_result.result_state must be REHEARSAL_RECORDED for the default receipt")
    _require_prefixed_refs(
        result,
        "inspected_resource_refs",
        "repo://local/",
        "rehearsal_result.inspected_resource_refs must stay under repo://local/",
        errors,
    )
    _require_prefixed_refs(
        result,
        "observed_evidence_refs",
        "evidence://local-repo/path-hash/",
        "rehearsal_result.observed_evidence_refs must be local path-hash evidence",
        errors,
    )
    for field_name in DENIED_RESULT_FIELDS:
        if result.get(field_name) is not False:
            errors.append(f"rehearsal_result.{field_name} must be false")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    contract = record.get("rehearsal_contract")
    result = record.get("rehearsal_result")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(contract, dict) or not isinstance(result, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("rehearsal_contract, rehearsal_result, receipt_refs, and contract_summary must be objects")
        return
    expected_counts = {
        "allowed_resource_ref_count": _list_len(contract.get("allowed_resource_refs")),
        "forbidden_effect_ref_count": _list_len(contract.get("forbidden_effect_refs")),
        "required_preflight_ref_count": _list_len(contract.get("required_preflight_refs")),
        "verification_ref_count": _list_len(contract.get("verification_refs")),
        "inspected_resource_ref_count": _list_len(result.get("inspected_resource_refs")),
        "observed_evidence_ref_count": _list_len(result.get("observed_evidence_refs")),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_prefixed_refs(
    record: dict[str, Any],
    field_name: str,
    required_prefix: str,
    error_message: str,
    errors: list[str],
) -> None:
    values = record.get(field_name)
    if not isinstance(values, list) or not values:
        errors.append(f"{field_name} must be a non-empty list")
        return
    if not all(isinstance(value, str) and value.startswith(required_prefix) for value in values):
        errors.append(error_message)


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate ReadOnlyWorkerRehearsalReceipt artifacts from the command line."""

    parser = argparse.ArgumentParser(description="Validate ReadOnlyWorkerRehearsalReceipt contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--binding", type=Path, default=DEFAULT_BINDING_PATH)
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_rehearsal_receipt(args.schema, args.receipt, args.binding, args.preflight)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "read_only_worker_rehearsal_receipt_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "receipt_path": workspace_display_path(args.receipt),
                    "binding_path": workspace_display_path(args.binding),
                    "preflight_path": workspace_display_path(args.preflight),
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
        print("[PASS] read_only_worker_rehearsal_receipt")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
