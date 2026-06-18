#!/usr/bin/env python3
"""Validate ReadOnlyWorkerRuntimeReceiptStoreOperatorApprovalWitness.

Purpose: verify the Foundation Mode operator-approval witness required before
runtime receipt-store activation or runtime receipt-emission admission.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schema validation helpers and read-only worker receipt-store
activation/emission witness contracts.
Invariants:
  - Approval remains AwaitingEvidence and uncollected.
  - The witness grants no receipt-store, dispatch, connector, filesystem,
    secret, mutation, success, or terminal-closure authority.
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
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = (
    WORKSPACE_ROOT / "schemas" / "read_only_worker_runtime_receipt_store_operator_approval_witness.schema.json"
)
DEFAULT_RECEIPT_PATH = (
    WORKSPACE_ROOT / "examples" / "read_only_worker_runtime_receipt_store_operator_approval_witness.foundation.json"
)
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-runtime-receipt-store-operator-approval-witness:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker runtime receipt-store operator approval Witness"
EXPECTED_RECEIPT_VERSION = "read_only_worker_runtime_receipt_store_operator_approval_witness.v1"
EXPECTED_WITNESS_MODE = "RECEIPT_STORE_OPERATOR_APPROVAL_WITNESS_ONLY"
EXPECTED_APPROVAL_PROFILE = "LOCAL_READ_ONLY_REPO_INSPECTION_RECEIPT_STORE_APPROVAL"
EXPECTED_DECISION = "RECEIPT_STORE_OPERATOR_APPROVAL_WITNESS_BLOCKED_AWAITING_OPERATOR_RESPONSE"
EXPECTED_ACTIVATION_WITNESS_REF = "examples/read_only_worker_runtime_receipt_store_activation_witness.foundation.json"
EXPECTED_EMISSION_ADMISSION_WITNESS_REF = (
    "examples/read_only_worker_runtime_receipt_emission_admission_witness.foundation.json"
)

REQUIRED_REQUESTED_EVIDENCE_REFS = (
    "evidence://operator-approval/live-runtime-receipt-store-activation",
    "evidence://operator-approval/live-runtime-receipt-emission-admission",
    "evidence://tenant-actor-boundary",
    "evidence://uao-effect-admission",
    "evidence://phi-gov-dispatch-authorization",
    "evidence://effect-reconciliation-passed",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_read_only_worker_runtime_receipt_store_operator_approval_witness.py",
    "scripts/validate_schemas.py",
    "scripts/validate_protocol_manifest.py",
    "tests/test_validate_read_only_worker_runtime_receipt_store_activation_witness.py",
)
REQUIRED_REMAINING_DENIED_UNTIL_REFS = (
    "evidence://operator-approval/live-runtime-receipt-store-activation",
    "evidence://operator-approval/live-runtime-receipt-emission-admission",
    "evidence://runtime-receipt-store-activation-live-evidence",
    "evidence://runtime-receipt-emission-admission-boundary/read-only-repo-inspection",
    "evidence://active-temporal-lease-window",
    "evidence://uao-effect-admission",
    "evidence://phi-gov-dispatch-authorization",
    "evidence://effect-reconciliation-passed",
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://operator-approval/live-runtime-receipt-store-activation-missing",
    "blocked://operator-approval/live-runtime-receipt-emission-admission-missing",
    "blocked://runtime-receipt-store/not-activated",
    "blocked://runtime-receipt-store/append-not-authorized",
    "blocked://runtime-receipt-emission/not-admitted",
    "blocked://temporal-lease/not-active",
    "blocked://phi-gov/dispatch-not-authorized",
    "blocked://effect-reconciliation/not-proven",
)
REQUIRED_RECEIPT_REFS = {
    "read_only_worker_runtime_receipt_store_operator_approval_witness_schema": (
        "schemas/read_only_worker_runtime_receipt_store_operator_approval_witness.schema.json"
    ),
    "read_only_worker_runtime_receipt_store_activation_witness_schema": (
        "schemas/read_only_worker_runtime_receipt_store_activation_witness.schema.json"
    ),
    "read_only_worker_runtime_receipt_emission_admission_witness_schema": (
        "schemas/read_only_worker_runtime_receipt_emission_admission_witness.schema.json"
    ),
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_runtime_receipt_store_operator_approval_witness.schema.json",
    "examples/read_only_worker_runtime_receipt_store_operator_approval_witness.foundation.json",
    "scripts/validate_read_only_worker_runtime_receipt_store_operator_approval_witness.py",
    "tests/test_validate_read_only_worker_runtime_receipt_store_activation_witness.py",
    "schemas/read_only_worker_runtime_receipt_store_activation_witness.schema.json",
    "schemas/read_only_worker_runtime_receipt_emission_admission_witness.schema.json",
    "schemas/universal_action_orchestration.schema.json",
)
AUTHORITY_TRUE_FIELDS = (
    "read_only",
    "foundation_witness_only",
    "mfidel_atomicity_preserved",
)
AUTHORITY_FALSE_FIELDS = (
    "operator_approval_collected",
    "operator_approval_granted",
    "receipt_store_activation_allowed",
    "receipt_emission_admission_allowed",
    "receipt_store_append_allowed",
    "runtime_dispatch_allowed",
    "worker_invocation_allowed",
    "external_network_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "connector_authority_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
APPROVAL_TRUE_FIELDS = (
    "operator_response_required",
    "activation_witness_bound",
    "emission_admission_witness_bound",
    "tenant_actor_boundary_required",
    "uao_required",
    "phi_gov_required",
)
APPROVAL_FALSE_FIELDS = (
    "operator_approval_collected",
    "operator_approval_granted",
    "receipt_store_activation_allowed",
    "receipt_emission_admission_allowed",
    "receipt_store_append_allowed",
)
ADMISSION_FALSE_FIELDS = (
    "operator_approval_collected",
    "receipt_store_activation_admitted",
    "receipt_emission_admission_admitted",
    "receipt_store_append_admitted",
    "terminal_closure_allowed",
)


class ReadOnlyWorkerRuntimeReceiptStoreOperatorApprovalWitnessError(ValueError):
    """Raised when the operator approval witness cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object with causal context."""

    if not json_path.exists():
        raise FileNotFoundError(f"{label} path does not exist: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerRuntimeReceiptStoreOperatorApprovalWitnessError(f"{label} must be a JSON object")
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
    return errors


def validate_operator_approval_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one operator approval witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("read-only worker runtime receipt-store operator approval witness must be a JSON object")
        return errors

    _require_equal(record, ("receipt_version",), EXPECTED_RECEIPT_VERSION, errors)
    _require_equal(record, ("selected_worker_path",), EXPECTED_WORKER_PATH, errors)
    _require_equal(record, ("solver_outcome",), "AwaitingEvidence", errors)
    _require_equal(record, ("approval_status",), "AwaitingEvidence", errors)
    _validate_authority_scope(record.get("authority_scope"), errors)
    _validate_contract(record.get("operator_approval_witness_contract"), errors)
    _validate_approval_evaluation(record.get("approval_evaluation"), errors)
    _validate_admission_decision(record.get("admission_decision"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_operator_approval_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode witness."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "ReadOnlyWorkerRuntimeReceiptStoreOperatorApprovalWitness")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_operator_approval_witness_record(receipt, schema))
    return errors


def build_mutated_operator_approval_witness(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default witness."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "ReadOnlyWorkerRuntimeReceiptStoreOperatorApprovalWitness")
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


def _validate_authority_scope(value: Any, errors: list[str]) -> None:
    scope = _mapping(value)
    for field_name in AUTHORITY_TRUE_FIELDS:
        if scope.get(field_name) is not True:
            errors.append(f"authority_scope.{field_name} must be true")
    for field_name in AUTHORITY_FALSE_FIELDS:
        if scope.get(field_name) is not False:
            errors.append(f"authority_scope.{field_name} must be false")


def _validate_contract(value: Any, errors: list[str]) -> None:
    contract = _mapping(value)
    _require_equal(contract, ("witness_mode",), EXPECTED_WITNESS_MODE, errors, "operator_approval_witness_contract")
    _require_equal(contract, ("approval_profile",), EXPECTED_APPROVAL_PROFILE, errors, "operator_approval_witness_contract")
    _require_equal(
        contract,
        ("target_activation_witness_ref",),
        EXPECTED_ACTIVATION_WITNESS_REF,
        errors,
        "operator_approval_witness_contract",
    )
    _require_equal(
        contract,
        ("target_emission_admission_witness_ref",),
        EXPECTED_EMISSION_ADMISSION_WITNESS_REF,
        errors,
        "operator_approval_witness_contract",
    )
    _require_subset(contract, "requested_evidence_refs", REQUIRED_REQUESTED_EVIDENCE_REFS, errors)
    _require_subset(contract, "validation_refs", REQUIRED_VALIDATION_REFS, errors)


def _validate_approval_evaluation(value: Any, errors: list[str]) -> None:
    evaluation = _mapping(value)
    for field_name in APPROVAL_TRUE_FIELDS:
        if evaluation.get(field_name) is not True:
            errors.append(f"approval_evaluation.{field_name} must be true")
    for field_name in APPROVAL_FALSE_FIELDS:
        if evaluation.get(field_name) is not False:
            errors.append(f"approval_evaluation.{field_name} must be false")


def _validate_admission_decision(value: Any, errors: list[str]) -> None:
    decision = _mapping(value)
    _require_equal(decision, ("decision",), EXPECTED_DECISION, errors, "admission_decision")
    if decision.get("operator_approval_witness_defined") is not True:
        errors.append("admission_decision.operator_approval_witness_defined must be true")
    for field_name in ADMISSION_FALSE_FIELDS:
        if decision.get(field_name) is not False:
            errors.append(f"admission_decision.{field_name} must be false")
    _require_subset(decision, "remaining_denied_until_refs", REQUIRED_REMAINING_DENIED_UNTIL_REFS, errors)
    _require_subset(decision, "blocked_reason_refs", REQUIRED_BLOCKED_REASON_REFS, errors)


def _validate_receipt_refs(value: Any, errors: list[str]) -> None:
    refs = _mapping(value)
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    summary = _mapping(record.get("contract_summary"))
    contract = _mapping(record.get("operator_approval_witness_contract"))
    decision = _mapping(record.get("admission_decision"))
    expected_counts = {
        "requested_evidence_ref_count": _list_len(contract.get("requested_evidence_refs")),
        "approval_obligation_count": _list_len(contract.get("approval_obligations_checked")),
        "validation_ref_count": _list_len(contract.get("validation_refs")),
        "remaining_denied_until_ref_count": _list_len(decision.get("remaining_denied_until_refs")),
        "blocked_reason_ref_count": _list_len(decision.get("blocked_reason_refs")),
        "receipt_ref_count": len(_mapping(record.get("receipt_refs"))),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_count in expected_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _require_equal(
    value: Any,
    path: tuple[str, ...],
    expected: Any,
    errors: list[str],
    prefix: str = "",
) -> None:
    current = value
    for segment in path:
        if not isinstance(current, dict):
            current = None
            break
        current = current.get(segment)
    if current != expected:
        label = ".".join((prefix, *path)) if prefix else ".".join(path)
        errors.append(f"{label} must be {expected}")


def _require_subset(
    value: Any,
    field_name: str,
    required_values: tuple[str, ...],
    errors: list[str],
) -> None:
    observed = value.get(field_name) if isinstance(value, dict) else None
    if not isinstance(observed, list):
        errors.append(f"{field_name} must be a list")
        return
    missing = tuple(item for item in required_values if item not in observed)
    if missing:
        errors.append(f"{field_name} missing required ref: {', '.join(missing)}")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_len(value: Any) -> int:
    return len(value) if isinstance(value, list) else -1


def _workspace_relative(path: Path) -> str:
    return str(path.resolve().relative_to(WORKSPACE_ROOT.resolve()))


def main() -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    errors = validate_operator_approval_witness(args.schema, args.receipt)
    if args.json:
        print(
            json.dumps(
                {
                    "status": "passed" if not errors else "failed",
                    "schema_path": _workspace_relative(args.schema),
                    "receipt_path": _workspace_relative(args.receipt),
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"FAIL: {error}")
    else:
        print("PASS: read-only worker runtime receipt-store operator approval witness")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
