#!/usr/bin/env python3
"""Validate the ReadOnlyWorkerRuntimeReceiptStoreWritePathWitness contract.

Purpose: verify Foundation Mode witness evidence for a future
read_only_repo_inspection runtime receipt-store write path without registering
that writer, appending a receipt, or admitting runtime dispatch.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers,
ReadOnlyWorkerRuntimeReceiptCandidate validation, and
ReadOnlyWorkerRuntimeReceiptSchemaBindingWitness validation.
Invariants:
  - Validation is read-only and deterministic.
  - The witness applies only to read_only_repo_inspection.
  - Receipt-store writer registration, write-path registration, append,
    runtime dispatch, and runtime receipt emission remain unperformed.
  - Raw output, secret material, external effects, filesystem writes,
    connector calls, success claims, and terminal closure remain denied.
  - WorkerFailureReceipt, idempotency, append-only replay, and effect
    reconciliation stay mandatory for future receipt-store evidence.
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
from scripts.validate_read_only_worker_rehearsal_receipt import EXPECTED_WORKER_ID  # noqa: E402
from scripts.validate_read_only_worker_runtime_receipt_candidate import (  # noqa: E402
    DEFAULT_RECEIPT_PATH as DEFAULT_CANDIDATE_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_CANDIDATE_SCHEMA_PATH,
    load_json_object as load_candidate_json_object,
    validate_runtime_receipt_candidate_record,
)
from scripts.validate_read_only_worker_runtime_receipt_schema_binding_witness import (  # noqa: E402
    DEFAULT_RECEIPT_PATH as DEFAULT_SCHEMA_BINDING_WITNESS_PATH,
    DEFAULT_SCHEMA_PATH as DEFAULT_SCHEMA_BINDING_WITNESS_SCHEMA_PATH,
    load_json_object as load_schema_binding_json_object,
    validate_schema_binding_witness_record,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "read_only_worker_runtime_receipt_store_write_path_witness.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "read_only_worker_runtime_receipt_store_write_path_witness.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-runtime-receipt-store-write-path-witness:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker Runtime Receipt Store Write Path Witness"
EXPECTED_RECEIPT_VERSION = "read_only_worker_runtime_receipt_store_write_path_witness.v1"
EXPECTED_SCHEMA_BINDING_WITNESS_REF = "examples/read_only_worker_runtime_receipt_schema_binding_witness.foundation.json"
EXPECTED_CANDIDATE_REF = "examples/read_only_worker_runtime_receipt_candidate.foundation.json"
EXPECTED_RUNNER_BINDING_WITNESS_REF = "examples/read_only_worker_runtime_runner_binding_witness.foundation.json"
EXPECTED_EMITTER_DRY_RUN_REF = "examples/read_only_worker_runtime_receipt_emitter_dry_run.foundation.json"
EXPECTED_HANDOFF_REF = "examples/read_only_worker_runtime_receipt_handoff.foundation.json"
EXPECTED_BINDING_REF = "examples/read_only_worker_binding.foundation.json"
EXPECTED_PREFLIGHT_REF = "examples/read_only_worker_lease_preflight.foundation.json"
EXPECTED_REHEARSAL_REF = "examples/read_only_worker_rehearsal_receipt.foundation.json"
EXPECTED_OPERATION_FAMILY = "local_repo_inspection"
EXPECTED_WITNESS_MODE = "RECEIPT_STORE_WRITE_PATH_WITNESS_ONLY"
EXPECTED_RUNTIME_RECEIPT_KIND = "future_worker_runtime_receipt"
EXPECTED_TARGET_WRITE_PATH_REF = "candidate://receipt-store/future-worker-runtime-receipt-append-only-write-path"
EXPECTED_WRITE_PATH_PROFILE = "APPEND_ONLY_DIGEST_ONLY_IDEMPOTENT_RECEIPT_STORE"
EXPECTED_ADMISSION_DECISION = (
    "RUNTIME_RECEIPT_STORE_WRITE_PATH_WITNESS_BLOCKED_AWAITING_LIVE_RUNNER_EMITTER_AND_STORE"
)
REQUIRED_SOURCE_RECEIPT_REFS = (
    EXPECTED_SCHEMA_BINDING_WITNESS_REF,
    EXPECTED_CANDIDATE_REF,
    EXPECTED_RUNNER_BINDING_WITNESS_REF,
    EXPECTED_EMITTER_DRY_RUN_REF,
    EXPECTED_HANDOFF_REF,
    EXPECTED_BINDING_REF,
    EXPECTED_PREFLIGHT_REF,
    EXPECTED_REHEARSAL_REF,
)
REQUIRED_WRITE_PATH_INPUT_REFS = (
    "evidence://runtime-receipt-schema-binding-witness",
    "evidence://future-worker-runtime-receipt-candidate",
    "evidence://append-only-receipt-store-profile",
    "evidence://idempotency-key-derivation",
    "evidence://tenant-actor-boundary",
    "evidence://output-digest-only-policy",
    "evidence://worker-failure-receipt-on-error",
    "evidence://effect-reconciliation-passed",
    "evidence://uao-effect-admission",
    "evidence://phi-gov-dispatch-authorization",
    "evidence://active-temporal-lease-window",
    "evidence://receipt-store-durability-replay",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_read_only_worker_runtime_receipt_store_write_path_witness.py",
    "scripts/validate_read_only_worker_runtime_receipt_schema_binding_witness.py",
    "scripts/validate_read_only_worker_runtime_receipt_candidate.py",
    "scripts/validate_read_only_worker_runtime_runner_binding_witness.py",
    "scripts/validate_schemas.py",
    "scripts/validate_protocol_manifest.py",
)
REQUIRED_REMAINING_DENIED_UNTIL_REFS = (
    "evidence://live-runtime-runner-registration-witness",
    "evidence://live-dispatch-endpoint-registration-witness",
    "evidence://runtime-receipt-emitter-registration-witness",
    "evidence://runtime-receipt-schema-binding-witness",
    "evidence://receipt-store-write-path-witness",
    "evidence://receipt-store-writer-registration",
    "evidence://active-temporal-lease-window",
    "evidence://uao-effect-admission",
    "evidence://phi-gov-dispatch-authorization",
    "evidence://effect-reconciliation-passed",
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://runtime-runner/not-registered",
    "blocked://dispatch-endpoint/not-registered",
    "blocked://runtime-receipt-emitter/not-registered",
    "blocked://runtime-receipt-schema/not-bound",
    "blocked://receipt-store/write-path-not-registered",
    "blocked://receipt-store/writer-not-registered",
    "blocked://receipt-store/append-not-admitted",
    "blocked://temporal-lease/not-active",
    "blocked://phi-gov/dispatch-not-authorized",
    "blocked://effect-reconciliation/not-proven",
)
REQUIRED_RECEIPT_REFS = {
    "read_only_worker_runtime_receipt_store_write_path_witness_schema": (
        "schemas/read_only_worker_runtime_receipt_store_write_path_witness.schema.json"
    ),
    "read_only_worker_runtime_receipt_schema_binding_witness_schema": (
        "schemas/read_only_worker_runtime_receipt_schema_binding_witness.schema.json"
    ),
    "read_only_worker_runtime_receipt_candidate_schema": (
        "schemas/read_only_worker_runtime_receipt_candidate.schema.json"
    ),
    "read_only_worker_runtime_runner_binding_witness_schema": (
        "schemas/read_only_worker_runtime_runner_binding_witness.schema.json"
    ),
    "read_only_worker_runtime_receipt_emitter_dry_run_schema": (
        "schemas/read_only_worker_runtime_receipt_emitter_dry_run.schema.json"
    ),
    "read_only_worker_runtime_receipt_handoff_schema": "schemas/read_only_worker_runtime_receipt_handoff.schema.json",
    "read_only_worker_binding_schema": "schemas/read_only_worker_binding.schema.json",
    "read_only_worker_lease_preflight_schema": "schemas/read_only_worker_lease_preflight.schema.json",
    "read_only_worker_rehearsal_receipt_schema": "schemas/read_only_worker_rehearsal_receipt.schema.json",
    "temporal_lease_window_receipt_schema": "schemas/temporal_lease_window_receipt.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "worker_mesh_schema": "schemas/worker_mesh.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_runtime_receipt_store_write_path_witness.schema.json",
    "examples/read_only_worker_runtime_receipt_store_write_path_witness.foundation.json",
    "scripts/validate_read_only_worker_runtime_receipt_store_write_path_witness.py",
    "tests/test_validate_read_only_worker_runtime_receipt_store_write_path_witness.py",
    "schemas/read_only_worker_runtime_receipt_schema_binding_witness.schema.json",
    EXPECTED_SCHEMA_BINDING_WITNESS_REF,
    "scripts/validate_read_only_worker_runtime_receipt_schema_binding_witness.py",
    "tests/test_validate_read_only_worker_runtime_receipt_schema_binding_witness.py",
    "schemas/read_only_worker_runtime_receipt_candidate.schema.json",
    EXPECTED_CANDIDATE_REF,
)
WRITE_PATH_EVALUATION_TRUE_FIELDS = (
    "upstream_schema_binding_witness_validated",
    "runtime_receipt_candidate_validated",
    "source_write_path_obligations_preserved",
    "append_only_policy_required",
    "idempotency_key_required",
    "tenant_actor_boundary_required",
    "output_digest_only_required",
    "worker_failure_receipt_required_on_error",
    "effect_reconciliation_required",
    "mfidel_atomicity_preserved",
)
WRITE_PATH_EVALUATION_DENIED_FIELDS = (
    "raw_output_retention_allowed",
    "secret_material_retention_allowed",
    "receipt_store_writer_registration_performed",
    "receipt_store_write_path_registered",
    "receipt_store_append_performed",
    "runtime_receipt_emitted",
)
DENIED_AUTHORITY_FIELDS = (
    "receipt_store_writer_registration_performed",
    "receipt_store_write_path_registered",
    "receipt_store_append_performed",
    "runtime_runner_registration_performed",
    "dispatch_endpoint_registration_performed",
    "runtime_receipt_emitter_registration_performed",
    "runtime_receipt_schema_binding_performed",
    "runtime_dispatch_allowed",
    "runtime_receipt_emission_allowed",
    "external_network_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "connector_authority_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)


class ReadOnlyWorkerRuntimeReceiptStoreWritePathWitnessError(ValueError):
    """Raised when a receipt-store write-path witness artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerRuntimeReceiptStoreWritePathWitnessError(f"{label} must be a JSON object")
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
            "write_path_witness_contract",
            "write_path_evaluation",
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


def validate_store_write_path_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
    schema_binding_witness: dict[str, Any] | None = None,
    runtime_receipt_candidate: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one receipt-store write-path witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("read-only worker runtime receipt-store write-path witness must be a JSON object")
        return errors

    candidate_payload = runtime_receipt_candidate or load_candidate_json_object(
        DEFAULT_CANDIDATE_PATH,
        "ReadOnlyWorkerRuntimeReceiptCandidate",
    )
    candidate_schema = _load_schema(DEFAULT_CANDIDATE_SCHEMA_PATH)
    errors.extend(
        f"runtime receipt candidate: {error}"
        for error in validate_runtime_receipt_candidate_record(candidate_payload, candidate_schema)
    )

    binding_witness_payload = schema_binding_witness or load_schema_binding_json_object(
        DEFAULT_SCHEMA_BINDING_WITNESS_PATH,
        "ReadOnlyWorkerRuntimeReceiptSchemaBindingWitness",
    )
    binding_witness_schema = _load_schema(DEFAULT_SCHEMA_BINDING_WITNESS_SCHEMA_PATH)
    errors.extend(
        f"schema binding witness: {error}"
        for error in validate_schema_binding_witness_record(
            binding_witness_payload,
            binding_witness_schema,
            candidate_payload,
        )
    )

    _validate_top_level_refs(record, candidate_payload, binding_witness_payload, errors)
    _validate_authority_scope(record.get("authority_scope"), errors)
    _validate_write_path_contract(record.get("write_path_witness_contract"), candidate_payload, errors)
    _validate_write_path_evaluation(record.get("write_path_evaluation"), errors)
    _validate_admission_decision(record.get("admission_decision"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_store_write_path_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
    schema_binding_witness_path: Path = DEFAULT_SCHEMA_BINDING_WITNESS_PATH,
    runtime_receipt_candidate_path: Path = DEFAULT_CANDIDATE_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode witness."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "ReadOnlyWorkerRuntimeReceiptStoreWritePathWitness")
    schema_binding_witness = load_schema_binding_json_object(
        schema_binding_witness_path,
        "ReadOnlyWorkerRuntimeReceiptSchemaBindingWitness",
    )
    runtime_receipt_candidate = load_candidate_json_object(
        runtime_receipt_candidate_path,
        "ReadOnlyWorkerRuntimeReceiptCandidate",
    )
    errors = validate_schema_artifact(schema)
    errors.extend(
        validate_store_write_path_witness_record(
            receipt,
            schema,
            schema_binding_witness,
            runtime_receipt_candidate,
        )
    )
    return errors


def build_mutated_store_write_path_witness(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default witness receipt."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "ReadOnlyWorkerRuntimeReceiptStoreWritePathWitness")
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


def _validate_top_level_refs(
    record: dict[str, Any],
    runtime_receipt_candidate: dict[str, Any],
    schema_binding_witness: dict[str, Any],
    errors: list[str],
) -> None:
    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match read_only_worker_runtime_receipt_store_write_path_witness.v1")
    expected_refs = {
        "schema_binding_witness_ref": EXPECTED_SCHEMA_BINDING_WITNESS_REF,
        "runtime_receipt_candidate_ref": EXPECTED_CANDIDATE_REF,
        "runner_binding_witness_ref": EXPECTED_RUNNER_BINDING_WITNESS_REF,
        "emitter_dry_run_ref": EXPECTED_EMITTER_DRY_RUN_REF,
        "handoff_ref": EXPECTED_HANDOFF_REF,
        "binding_ref": EXPECTED_BINDING_REF,
        "lease_preflight_ref": EXPECTED_PREFLIGHT_REF,
        "rehearsal_receipt_ref": EXPECTED_REHEARSAL_REF,
    }
    for field_name, expected_ref in expected_refs.items():
        if record.get(field_name) != expected_ref:
            errors.append(f"{field_name} must be {expected_ref}")
    if record.get("selected_worker_path") != EXPECTED_WORKER_PATH:
        errors.append("selected_worker_path must be read_only_repo_inspection")
    if record.get("selected_worker_path") != runtime_receipt_candidate.get("selected_worker_path"):
        errors.append("receipt-store write-path witness selected_worker_path must match runtime receipt candidate")
    if record.get("selected_worker_path") != schema_binding_witness.get("selected_worker_path"):
        errors.append("receipt-store write-path witness selected_worker_path must match schema binding witness")


def _validate_authority_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("authority_scope must be an object")
        return
    if scope.get("read_only") is not True:
        errors.append("authority_scope.read_only must be true")
    if scope.get("foundation_witness_only") is not True:
        errors.append("authority_scope.foundation_witness_only must be true")
    for field_name in DENIED_AUTHORITY_FIELDS:
        if scope.get(field_name) is not False:
            errors.append(f"authority_scope.{field_name} must be false")
    if scope.get("mfidel_atomicity_preserved") is not True:
        errors.append("authority_scope.mfidel_atomicity_preserved must be true")


def _validate_write_path_contract(
    contract: Any,
    runtime_receipt_candidate: dict[str, Any],
    errors: list[str],
) -> None:
    if not isinstance(contract, dict):
        errors.append("write_path_witness_contract must be an object")
        return
    candidate_contract = runtime_receipt_candidate.get("runtime_receipt_candidate_contract", {})
    if contract.get("worker_id") != EXPECTED_WORKER_ID:
        errors.append("write_path_witness_contract.worker_id must select worker_local_read_only_repo_inspection")
    if contract.get("worker_id") != candidate_contract.get("worker_id"):
        errors.append("write_path_witness_contract.worker_id must match runtime receipt candidate worker_id")
    if contract.get("capability") != EXPECTED_WORKER_PATH:
        errors.append("write_path_witness_contract.capability must be read_only_repo_inspection")
    if contract.get("operation_family") != EXPECTED_OPERATION_FAMILY:
        errors.append("write_path_witness_contract.operation_family must be local_repo_inspection")
    if contract.get("witness_mode") != EXPECTED_WITNESS_MODE:
        errors.append("write_path_witness_contract.witness_mode must be RECEIPT_STORE_WRITE_PATH_WITNESS_ONLY")
    if contract.get("runtime_receipt_kind") != EXPECTED_RUNTIME_RECEIPT_KIND:
        errors.append("write_path_witness_contract.runtime_receipt_kind must be future_worker_runtime_receipt")
    if contract.get("source_schema_binding_witness_ref") != EXPECTED_SCHEMA_BINDING_WITNESS_REF:
        errors.append("write_path_witness_contract.source_schema_binding_witness_ref is invalid")
    if contract.get("source_runtime_receipt_candidate_ref") != EXPECTED_CANDIDATE_REF:
        errors.append("write_path_witness_contract.source_runtime_receipt_candidate_ref is invalid")
    if contract.get("target_receipt_store_write_path_ref") != EXPECTED_TARGET_WRITE_PATH_REF:
        errors.append("write_path_witness_contract.target_receipt_store_write_path_ref is invalid")
    if contract.get("write_path_profile") != EXPECTED_WRITE_PATH_PROFILE:
        errors.append("write_path_witness_contract.write_path_profile is invalid")
    _require_subset(contract, "required_source_receipt_refs", REQUIRED_SOURCE_RECEIPT_REFS, errors)
    _require_subset(contract, "required_write_path_input_refs", REQUIRED_WRITE_PATH_INPUT_REFS, errors)
    _require_subset(contract, "validation_refs", REQUIRED_VALIDATION_REFS, errors)
    obligations = contract.get("write_path_obligations_checked")
    if not isinstance(obligations, list) or len(obligations) < 8:
        errors.append("write_path_obligations_checked must list future receipt-store write-path obligations")
    elif not any(isinstance(item, str) and "append-only" in item for item in obligations):
        errors.append("write_path_obligations_checked must require append-only receipt storage")
    elif not any(isinstance(item, str) and "idempotency" in item for item in obligations):
        errors.append("write_path_obligations_checked must require idempotency")
    elif not any(isinstance(item, str) and "WorkerFailureReceipt" in item for item in obligations):
        errors.append("write_path_obligations_checked must require WorkerFailureReceipt on failed or partial append")
    elif not any(isinstance(item, str) and "Mfidel atomicity" in item for item in obligations):
        errors.append("write_path_obligations_checked must preserve Mfidel atomicity")


def _validate_write_path_evaluation(evaluation: Any, errors: list[str]) -> None:
    if not isinstance(evaluation, dict):
        errors.append("write_path_evaluation must be an object")
        return
    for field_name in WRITE_PATH_EVALUATION_TRUE_FIELDS:
        if evaluation.get(field_name) is not True:
            errors.append(f"write_path_evaluation.{field_name} must be true")
    for field_name in WRITE_PATH_EVALUATION_DENIED_FIELDS:
        if evaluation.get(field_name) is not False:
            errors.append(f"write_path_evaluation.{field_name} must be false")


def _validate_admission_decision(decision: Any, errors: list[str]) -> None:
    if not isinstance(decision, dict):
        errors.append("admission_decision must be an object")
        return
    if decision.get("decision") != EXPECTED_ADMISSION_DECISION:
        errors.append(
            "admission_decision.decision must be "
            "RUNTIME_RECEIPT_STORE_WRITE_PATH_WITNESS_BLOCKED_AWAITING_LIVE_RUNNER_EMITTER_AND_STORE"
        )
    if decision.get("receipt_store_write_path_witness_defined") is not True:
        errors.append("admission_decision.receipt_store_write_path_witness_defined must be true")
    for field_name in (
        "receipt_store_write_path_registered",
        "receipt_store_append_admitted",
        "runtime_receipt_emission_admitted",
        "runtime_dispatch_admitted",
        "terminal_closure_allowed",
    ):
        if decision.get(field_name) is not False:
            errors.append(f"admission_decision.{field_name} must be false")
    _require_subset(decision, "remaining_denied_until_refs", REQUIRED_REMAINING_DENIED_UNTIL_REFS, errors)
    _require_subset(decision, "blocked_reason_refs", REQUIRED_BLOCKED_REASON_REFS, errors)


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    contract = record.get("write_path_witness_contract")
    evaluation = record.get("write_path_evaluation")
    decision = record.get("admission_decision")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not all(isinstance(value, dict) for value in (contract, evaluation, decision, refs, summary)):
        errors.append("write-path contract, evaluation, decision, refs, and summary must be objects")
        return
    expected_counts = {
        "source_receipt_ref_count": _list_len(contract.get("required_source_receipt_refs")),
        "write_path_input_ref_count": _list_len(contract.get("required_write_path_input_refs")),
        "write_path_obligation_count": _list_len(contract.get("write_path_obligations_checked")),
        "validation_ref_count": _list_len(contract.get("validation_refs")),
        "write_path_true_check_count": sum(
            1 for field_name in WRITE_PATH_EVALUATION_TRUE_FIELDS if evaluation.get(field_name) is True
        ),
        "write_path_denied_check_count": sum(
            1 for field_name in WRITE_PATH_EVALUATION_DENIED_FIELDS if evaluation.get(field_name) is False
        ),
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
    """Validate ReadOnlyWorkerRuntimeReceiptStoreWritePathWitness artifacts from the CLI."""

    parser = argparse.ArgumentParser(
        description="Validate ReadOnlyWorkerRuntimeReceiptStoreWritePathWitness contract."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--schema-binding-witness", type=Path, default=DEFAULT_SCHEMA_BINDING_WITNESS_PATH)
    parser.add_argument("--runtime-receipt-candidate", type=Path, default=DEFAULT_CANDIDATE_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable receipt")
    args = parser.parse_args(argv)
    errors = validate_store_write_path_witness(
        args.schema,
        args.receipt,
        args.schema_binding_witness,
        args.runtime_receipt_candidate,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "read_only_worker_runtime_receipt_store_write_path_witness_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "receipt_path": workspace_display_path(args.receipt),
                    "schema_binding_witness_path": workspace_display_path(args.schema_binding_witness),
                    "runtime_receipt_candidate_path": workspace_display_path(args.runtime_receipt_candidate),
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
        print("[PASS] read_only_worker_runtime_receipt_store_write_path_witness")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
