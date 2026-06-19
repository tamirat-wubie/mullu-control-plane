#!/usr/bin/env python3
"""Validate the ReadOnlyWorkerRuntimeActiveLeaseAdmissionWitness contract.

Purpose: verify Foundation Mode witness evidence for a future active runtime
lease admission boundary before any read_only_repo_inspection worker dispatch.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, and the
ReadOnlyWorkerLeasePreflight validator.
Invariants:
  - Validation is read-only and deterministic.
  - The witness applies only to read_only_repo_inspection.
  - Active lease admission, lease claim, distributed lease claim, distributed
    lease execution, dispatch admission, runtime dispatch, worker invocation,
    receipt append, and runtime receipt emission remain unperformed.
  - Operator approval, active temporal lease evidence, UAO, Phi_gov,
    WorkerFailureReceipt, and effect reconciliation remain mandatory.
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

from scripts.validate_read_only_worker_binding import EXPECTED_WORKER_PATH  # noqa: E402
from scripts.validate_read_only_worker_lease_preflight import (  # noqa: E402
    DEFAULT_PREFLIGHT_PATH,
    EXPECTED_BINDING_REF,
    EXPECTED_RUNTIME_CLOCK_REF,
    EXPECTED_TEMPORAL_SCHEMA_REF,
    EXPECTED_WORKER_ID,
    load_json_object as load_preflight_json_object,
    validate_preflight_record,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = (
    WORKSPACE_ROOT / "schemas" / "read_only_worker_runtime_active_lease_admission_witness.schema.json"
)
DEFAULT_RECEIPT_PATH = (
    WORKSPACE_ROOT / "examples" / "read_only_worker_runtime_active_lease_admission_witness.foundation.json"
)
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-runtime-active-lease-admission-witness:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker runtime active lease admission Witness"
EXPECTED_RECEIPT_VERSION = "read_only_worker_runtime_active_lease_admission_witness.v1"
EXPECTED_PREFLIGHT_REF = "examples/read_only_worker_lease_preflight.foundation.json"
EXPECTED_OPERATION_FAMILY = "local_repo_inspection"
EXPECTED_WITNESS_MODE = "ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_ONLY"
EXPECTED_LEASE_POLICY_ID = "lease-policy-read-only-repo-inspection-foundation"
EXPECTED_SCOPE_ID = "scope-read-only-repo-inspection-local"
EXPECTED_TARGET_ACTIVE_LEASE_REF = "candidate://runtime-lease/admission/read-only-repo-inspection"
EXPECTED_TARGET_DISPATCH_ADMISSION_REF = "candidate://runtime-dispatch/admission/read-only-repo-inspection"
EXPECTED_ADMISSION_DECISION = (
    "ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_BLOCKED_AWAITING_OPERATOR_APPROVAL_AND_LIVE_EVIDENCE"
)

REQUIRED_SOURCE_RECEIPT_REFS = (
    EXPECTED_BINDING_REF,
    EXPECTED_PREFLIGHT_REF,
)
REQUIRED_RUNTIME_INPUT_REFS = (
    "evidence://operator-approval/active-runtime-lease-admission",
    "evidence://tenant-actor-boundary",
    "evidence://resource-scope-boundary/read-only-repo-inspection",
    "evidence://active-temporal-lease-window",
    "evidence://distributed-lease-claim-receipt",
    "evidence://distributed-lease-execution-receipt",
    "evidence://uao-effect-admission",
    "evidence://phi-gov-lease-authorization",
    "evidence://worker-failure-receipt-on-error",
    "evidence://effect-reconciliation-passed",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_read_only_worker_runtime_active_lease_admission_witness.py",
    "scripts/validate_read_only_worker_lease_preflight.py",
    "scripts/validate_schemas.py",
    "scripts/validate_protocol_manifest.py",
    "scripts/validate_sdlc_artifact.py",
    "tests/test_validate_read_only_worker_runtime_active_lease_admission_witness.py",
)
REQUIRED_RECEIPT_REFS = {
    "read_only_worker_runtime_active_lease_admission_witness_schema": (
        "schemas/read_only_worker_runtime_active_lease_admission_witness.schema.json"
    ),
    "read_only_worker_lease_preflight_schema": "schemas/read_only_worker_lease_preflight.schema.json",
    "temporal_lease_window_receipt_schema": "schemas/temporal_lease_window_receipt.schema.json",
    "distributed_lease_claim_receipt_schema": "schemas/distributed_lease_claim_receipt.schema.json",
    "distributed_lease_execution_receipt_schema": "schemas/distributed_lease_execution_receipt.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "worker_mesh_schema": "schemas/worker_mesh.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_runtime_active_lease_admission_witness.schema.json",
    "examples/read_only_worker_runtime_active_lease_admission_witness.foundation.json",
    "scripts/validate_read_only_worker_runtime_active_lease_admission_witness.py",
    "tests/test_validate_read_only_worker_runtime_active_lease_admission_witness.py",
    "schemas/read_only_worker_lease_preflight.schema.json",
    "examples/read_only_worker_lease_preflight.foundation.json",
    "scripts/validate_read_only_worker_lease_preflight.py",
    "tests/test_validate_read_only_worker_lease_preflight.py",
    "schemas/temporal_lease_window_receipt.schema.json",
    "schemas/distributed_lease_claim_receipt.schema.json",
    "schemas/distributed_lease_execution_receipt.schema.json",
    "docs/80_read_only_worker_binding_contract.md",
)
LEASE_EVALUATION_TRUE_FIELDS = (
    "upstream_binding_validated",
    "upstream_lease_preflight_validated",
    "lease_policy_boundary_checked",
    "tenant_actor_boundary_required",
    "resource_scope_boundary_required",
    "active_temporal_lease_window_required",
    "fencing_token_required",
    "positive_sequence_required",
    "distributed_lease_claim_receipt_required",
    "distributed_lease_execution_receipt_required",
    "uao_admission_required_before_lease",
    "phi_gov_authorization_required_before_lease",
    "worker_failure_receipt_required_on_error",
    "effect_reconciliation_required",
    "mfidel_atomicity_preserved",
)
LEASE_EVALUATION_DENIED_FIELDS = (
    "active_runtime_lease_admission_performed",
    "lease_claim_performed",
    "distributed_lease_claim_performed",
    "distributed_lease_execution_performed",
    "dispatch_admission_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emitted",
    "receipt_append_performed",
)
DENIED_AUTHORITY_FIELDS = (
    "active_runtime_lease_admission_performed",
    "lease_claim_performed",
    "distributed_lease_claim_performed",
    "distributed_lease_execution_performed",
    "dispatch_admission_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "runtime_receipt_emission_allowed",
    "receipt_append_allowed",
    "external_network_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "connector_authority_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)


class ReadOnlyWorkerRuntimeActiveLeaseAdmissionWitnessError(ValueError):
    """Raised when an active lease admission witness artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerRuntimeActiveLeaseAdmissionWitnessError(f"{label} must be a JSON object")
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
            "authority_scope",
            "active_lease_admission_contract",
            "lease_evaluation",
            "admission_decision",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_active_lease_admission_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
    preflight: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one active lease witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("read-only worker runtime active lease admission witness must be a JSON object")
        return errors

    preflight_payload = preflight or load_preflight_json_object(DEFAULT_PREFLIGHT_PATH, "ReadOnlyWorkerLeasePreflight")
    errors.extend(f"preflight: {error}" for error in validate_preflight_record(preflight_payload))
    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match read_only_worker_runtime_active_lease_admission_witness.v1")
    if record.get("binding_ref") != EXPECTED_BINDING_REF:
        errors.append("binding_ref must point to the Foundation ReadOnlyWorkerBinding example")
    if record.get("lease_preflight_ref") != EXPECTED_PREFLIGHT_REF:
        errors.append("lease_preflight_ref must point to the Foundation ReadOnlyWorkerLeasePreflight example")
    if record.get("selected_worker_path") != EXPECTED_WORKER_PATH:
        errors.append("selected_worker_path must be read_only_repo_inspection")
    if preflight_payload.get("selected_worker_path") != record.get("selected_worker_path"):
        errors.append("active lease witness selected_worker_path must match lease preflight")
    _validate_authority_scope(record.get("authority_scope"), errors)
    _validate_admission_contract(record.get("active_lease_admission_contract"), preflight_payload, errors)
    _validate_lease_evaluation(record.get("lease_evaluation"), errors)
    _validate_admission_decision(record.get("admission_decision"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_active_lease_admission_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    preflight_path: Path = DEFAULT_PREFLIGHT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode witness."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "ReadOnlyWorkerRuntimeActiveLeaseAdmissionWitness")
    preflight = load_preflight_json_object(preflight_path, "ReadOnlyWorkerLeasePreflight")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_active_lease_admission_witness_record(receipt, schema, preflight))
    return errors


def build_mutated_active_lease_admission_witness(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default witness receipt."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "ReadOnlyWorkerRuntimeActiveLeaseAdmissionWitness")
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
    if scope.get("foundation_witness_only") is not True:
        errors.append("authority_scope.foundation_witness_only must be true")
    if scope.get("active_runtime_lease_admission_witness_defined") is not True:
        errors.append("authority_scope.active_runtime_lease_admission_witness_defined must be true")
    for field_name in DENIED_AUTHORITY_FIELDS:
        if scope.get(field_name) is not False:
            errors.append(f"authority_scope.{field_name} must be false")
    if scope.get("mfidel_atomicity_preserved") is not True:
        errors.append("authority_scope.mfidel_atomicity_preserved must be true")


def _validate_admission_contract(contract: Any, preflight: dict[str, Any], errors: list[str]) -> None:
    if not isinstance(contract, dict):
        errors.append("active_lease_admission_contract must be an object")
        return
    lease_contract = preflight.get("lease_contract", {})
    if contract.get("worker_id") != EXPECTED_WORKER_ID:
        errors.append("active_lease_admission_contract.worker_id must select worker_local_read_only_repo_inspection")
    if contract.get("worker_id") != lease_contract.get("worker_id"):
        errors.append("active_lease_admission_contract.worker_id must match lease preflight")
    if contract.get("capability") != EXPECTED_WORKER_PATH:
        errors.append("active_lease_admission_contract.capability must be read_only_repo_inspection")
    if contract.get("operation_family") != EXPECTED_OPERATION_FAMILY:
        errors.append("active_lease_admission_contract.operation_family must be local_repo_inspection")
    if contract.get("witness_mode") != EXPECTED_WITNESS_MODE:
        errors.append("active_lease_admission_contract.witness_mode must be ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_ONLY")
    if contract.get("lease_policy_id") != EXPECTED_LEASE_POLICY_ID:
        errors.append("active_lease_admission_contract.lease_policy_id is invalid")
    if contract.get("scope_id") != EXPECTED_SCOPE_ID:
        errors.append("active_lease_admission_contract.scope_id is invalid")
    if contract.get("source_binding_ref") != EXPECTED_BINDING_REF:
        errors.append("active_lease_admission_contract.source_binding_ref is invalid")
    if contract.get("source_lease_preflight_ref") != EXPECTED_PREFLIGHT_REF:
        errors.append("active_lease_admission_contract.source_lease_preflight_ref is invalid")
    if contract.get("temporal_lease_window_schema_ref") != EXPECTED_TEMPORAL_SCHEMA_REF:
        errors.append("active_lease_admission_contract.temporal_lease_window_schema_ref is invalid")
    if lease_contract.get("runtime_clock_ref") != EXPECTED_RUNTIME_CLOCK_REF:
        errors.append("lease preflight runtime_clock_ref must bind TrustedClock")
    if contract.get("target_active_runtime_lease_ref") != EXPECTED_TARGET_ACTIVE_LEASE_REF:
        errors.append("active_lease_admission_contract.target_active_runtime_lease_ref is invalid")
    if contract.get("target_runtime_dispatch_admission_ref") != EXPECTED_TARGET_DISPATCH_ADMISSION_REF:
        errors.append("active_lease_admission_contract.target_runtime_dispatch_admission_ref is invalid")
    _require_subset(contract, "required_source_receipt_refs", REQUIRED_SOURCE_RECEIPT_REFS, errors)
    _require_subset(contract, "required_runtime_input_refs", REQUIRED_RUNTIME_INPUT_REFS, errors)
    _require_subset(contract, "validation_refs", REQUIRED_VALIDATION_REFS, errors)
    obligations = contract.get("admission_obligations_checked")
    if not isinstance(obligations, list) or len(obligations) < 7:
        errors.append("admission_obligations_checked must list future active lease obligations")
    else:
        if not any(isinstance(item, str) and "operator approved" in item for item in obligations):
            errors.append("admission_obligations_checked must require operator approval")
        if not any(isinstance(item, str) and "lease_active" in item for item in obligations):
            errors.append("admission_obligations_checked must require lease_active temporal evidence")
        if not any(isinstance(item, str) and "distributed lease" in item for item in obligations):
            errors.append("admission_obligations_checked must require distributed lease evidence")
        if not any(isinstance(item, str) and "WorkerFailureReceipt" in item for item in obligations):
            errors.append("admission_obligations_checked must require WorkerFailureReceipt")
        if not any(isinstance(item, str) and "Mfidel atomicity" in item for item in obligations):
            errors.append("admission_obligations_checked must preserve Mfidel atomicity")


def _validate_lease_evaluation(evaluation: Any, errors: list[str]) -> None:
    if not isinstance(evaluation, dict):
        errors.append("lease_evaluation must be an object")
        return
    for field_name in LEASE_EVALUATION_TRUE_FIELDS:
        if evaluation.get(field_name) is not True:
            errors.append(f"lease_evaluation.{field_name} must be true")
    for field_name in LEASE_EVALUATION_DENIED_FIELDS:
        if evaluation.get(field_name) is not False:
            errors.append(f"lease_evaluation.{field_name} must be false")


def _validate_admission_decision(decision: Any, errors: list[str]) -> None:
    if not isinstance(decision, dict):
        errors.append("admission_decision must be an object")
        return
    if decision.get("decision") != EXPECTED_ADMISSION_DECISION:
        errors.append("admission_decision.decision must be ACTIVE_RUNTIME_LEASE_ADMISSION_WITNESS_BLOCKED_AWAITING_OPERATOR_APPROVAL_AND_LIVE_EVIDENCE")
    if decision.get("active_runtime_lease_admission_witness_defined") is not True:
        errors.append("admission_decision.active_runtime_lease_admission_witness_defined must be true")
    for field_name in (
        "active_runtime_lease_admitted",
        "active_temporal_lease_receipt_present",
        "distributed_lease_claim_admitted",
        "distributed_lease_execution_admitted",
        "runtime_dispatch_admitted",
        "terminal_closure_allowed",
    ):
        if decision.get(field_name) is not False:
            errors.append(f"admission_decision.{field_name} must be false")
    _require_subset(decision, "remaining_denied_until_refs", REQUIRED_RUNTIME_INPUT_REFS[:-1], errors)
    _require_subset(decision, "blocked_reason_refs", (
        "blocked://operator-approval/active-runtime-lease-admission-missing",
        "blocked://temporal-lease/not-active",
        "blocked://distributed-lease/claim-receipt-missing",
        "blocked://distributed-lease/execution-receipt-missing",
        "blocked://phi-gov/lease-not-authorized",
    ), errors)


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    contract = record.get("active_lease_admission_contract")
    evaluation = record.get("lease_evaluation")
    decision = record.get("admission_decision")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not all(isinstance(value, dict) for value in (contract, evaluation, decision, refs, summary)):
        errors.append("active lease contract, evaluation, decision, refs, and summary must be objects")
        return
    expected_counts = {
        "source_receipt_ref_count": _list_len(contract.get("required_source_receipt_refs")),
        "runtime_input_ref_count": _list_len(contract.get("required_runtime_input_refs")),
        "admission_obligation_count": _list_len(contract.get("admission_obligations_checked")),
        "validation_ref_count": _list_len(contract.get("validation_refs")),
        "lease_true_check_count": sum(1 for field_name in LEASE_EVALUATION_TRUE_FIELDS if evaluation.get(field_name) is True),
        "lease_denied_check_count": sum(1 for field_name in LEASE_EVALUATION_DENIED_FIELDS if evaluation.get(field_name) is False),
        "remaining_denied_until_ref_count": _list_len(decision.get("remaining_denied_until_refs")),
        "blocked_reason_ref_count": _list_len(decision.get("blocked_reason_refs")),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _list_len(value: Any) -> int | None:
    return len(value) if isinstance(value, list) else None


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate ReadOnlyWorkerRuntimeActiveLeaseAdmissionWitness artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate ReadOnlyWorkerRuntimeActiveLeaseAdmissionWitness contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--preflight", type=Path, default=DEFAULT_PREFLIGHT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_active_lease_admission_witness(args.schema, args.receipt, args.preflight)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "read_only_worker_runtime_active_lease_admission_witness_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "receipt_path": workspace_display_path(args.receipt),
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
        print("[PASS] read_only_worker_runtime_active_lease_admission_witness")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
