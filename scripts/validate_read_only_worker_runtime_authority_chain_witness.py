#!/usr/bin/env python3
"""Validate the ReadOnlyWorkerRuntimeAuthorityChainWitness contract.

Purpose: verify the Foundation Mode read_only_repo_inspection runtime authority
chain witness that binds lease admission, dispatch authorization, receipt
emission, receipt-store, failure, recovery, and replay evidence.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, and the
active lease and runtime dispatch admission witness validators.
Invariants:
  - Validation is read-only and deterministic.
  - The witness applies only to read_only_repo_inspection.
  - Lease admission, UAO dispatch authorization, Phi_gov dispatch
    authorization, runtime dispatch, worker invocation, receipt emission,
    receipt append, terminal closure, and success claims remain denied.
  - WorkerFailureReceipt, rollback or recovery, deterministic replay, and
    effect reconciliation remain mandatory before future runtime admission.
  - Mfidel atomicity remains preserved.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import sys
from pathlib import Path
from typing import Any, Mapping


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_read_only_worker_binding import EXPECTED_WORKER_PATH  # noqa: E402
from scripts.validate_read_only_worker_runtime_active_lease_admission_witness import (  # noqa: E402
    validate_active_lease_admission_witness,
)
from scripts.validate_read_only_worker_runtime_dispatch_admission_witness import (  # noqa: E402
    validate_runtime_dispatch_admission_witness,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = (
    WORKSPACE_ROOT / "schemas" / "read_only_worker_runtime_authority_chain_witness.schema.json"
)
DEFAULT_RECEIPT_PATH = (
    WORKSPACE_ROOT / "examples" / "read_only_worker_runtime_authority_chain_witness.foundation.json"
)
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:read-only-worker-runtime-authority-chain-witness:1"
EXPECTED_SCHEMA_TITLE = "Read-Only Worker runtime authority chain Witness"
EXPECTED_RECEIPT_VERSION = "read_only_worker_runtime_authority_chain_witness.v1"
EXPECTED_CHAIN_DECISION = "RUNTIME_AUTHORITY_CHAIN_BLOCKED_AWAITING_COMPLETE_LIVE_EVIDENCE"

REQUIRED_STAGE_REFS = {
    "binding": "examples/read_only_worker_binding.foundation.json",
    "lease_preflight": "examples/read_only_worker_lease_preflight.foundation.json",
    "rehearsal": "examples/read_only_worker_rehearsal_receipt.foundation.json",
    "runtime_receipt_candidate": "examples/read_only_worker_runtime_receipt_candidate.foundation.json",
    "receipt_schema_binding": "examples/read_only_worker_runtime_receipt_schema_binding_witness.foundation.json",
    "receipt_store_write_path": "examples/read_only_worker_runtime_receipt_store_write_path_witness.foundation.json",
    "receipt_emission_admission": (
        "examples/read_only_worker_runtime_receipt_emission_admission_witness.foundation.json"
    ),
    "active_lease_admission": (
        "examples/read_only_worker_runtime_active_lease_admission_witness.foundation.json"
    ),
    "uao_dispatch_authorization": "examples/read_only_worker_uao_dispatch_authorization_witness.foundation.json",
    "phi_gov_dispatch_authorization": (
        "examples/read_only_worker_phi_gov_dispatch_authorization_witness.foundation.json"
    ),
    "runtime_dispatch_admission": (
        "examples/read_only_worker_runtime_dispatch_admission_witness.foundation.json"
    ),
    "failure_receipt": "examples/worker_failure_receipt.foundation.json",
}
REQUIRED_EVIDENCE_INPUT_REFS = (
    "evidence://operator-approval/runtime-authority-chain",
    "evidence://active-temporal-lease-window",
    "evidence://distributed-lease-claim-receipt",
    "evidence://distributed-lease-execution-receipt",
    "evidence://uao-effect-admission",
    "evidence://phi-gov-dispatch-authorization",
    "evidence://runtime-receipt-emission-admission",
    "evidence://receipt-store-append-only-path",
    "evidence://worker-failure-receipt-on-error",
    "evidence://replay-or-recovery-handoff",
    "evidence://effect-reconciliation-passed",
)
REQUIRED_RECEIPT_REFS = {
    "authority_chain_schema": "schemas/read_only_worker_runtime_authority_chain_witness.schema.json",
    "active_lease_admission_schema": (
        "schemas/read_only_worker_runtime_active_lease_admission_witness.schema.json"
    ),
    "runtime_dispatch_admission_schema": (
        "schemas/read_only_worker_runtime_dispatch_admission_witness.schema.json"
    ),
    "uao_dispatch_authorization_schema": "schemas/read_only_worker_uao_dispatch_authorization_witness.schema.json",
    "phi_gov_dispatch_authorization_schema": (
        "schemas/read_only_worker_phi_gov_dispatch_authorization_witness.schema.json"
    ),
    "receipt_emission_admission_schema": (
        "schemas/read_only_worker_runtime_receipt_emission_admission_witness.schema.json"
    ),
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/read_only_worker_runtime_authority_chain_witness.schema.json",
    "examples/read_only_worker_runtime_authority_chain_witness.foundation.json",
    "scripts/validate_read_only_worker_runtime_authority_chain_witness.py",
    "tests/test_validate_read_only_worker_runtime_authority_chain_witness.py",
    "examples/read_only_worker_runtime_active_lease_admission_witness.foundation.json",
    "examples/read_only_worker_runtime_dispatch_admission_witness.foundation.json",
    "examples/read_only_worker_uao_dispatch_authorization_witness.foundation.json",
    "examples/read_only_worker_phi_gov_dispatch_authorization_witness.foundation.json",
    "examples/read_only_worker_runtime_receipt_emission_admission_witness.foundation.json",
    "examples/read_only_worker_runtime_receipt_store_write_path_witness.foundation.json",
    "examples/worker_failure_receipt.foundation.json",
    "schemas/worker_failure_receipt.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "docs/80_read_only_worker_binding_contract.md",
)
AUTHORITY_TRUE_FIELDS = (
    "read_only",
    "foundation_witness_only",
    "runtime_authority_chain_defined",
    "mfidel_atomicity_preserved",
)
AUTHORITY_DENIED_FIELDS = (
    "active_runtime_lease_admitted",
    "uao_dispatch_authorized",
    "phi_gov_dispatch_authorized",
    "runtime_dispatch_admitted",
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
CHAIN_TRUE_FIELDS = (
    "binding_validated",
    "lease_preflight_validated",
    "runtime_receipt_candidate_validated",
    "receipt_schema_binding_required",
    "receipt_store_write_path_required",
    "receipt_emission_admission_required",
    "active_lease_admission_required",
    "uao_dispatch_authorization_required",
    "phi_gov_dispatch_authorization_required",
    "runtime_dispatch_admission_required",
    "worker_failure_receipt_required",
    "effect_reconciliation_required",
    "mfidel_atomicity_preserved",
)
CHAIN_DENIED_FIELDS = (
    "active_runtime_lease_admitted",
    "uao_dispatch_authorized",
    "phi_gov_dispatch_authorized",
    "runtime_dispatch_admitted",
    "worker_invocation_performed",
    "runtime_receipt_emitted",
    "receipt_append_performed",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
RECOVERY_TRUE_FIELDS = (
    "worker_failure_receipt_required_on_error",
    "rollback_or_recovery_ref_required",
    "deterministic_replay_evidence_required",
    "effect_reconciliation_required",
    "incident_handoff_required_for_unknown_effects",
)
RECOVERY_DENIED_FIELDS = (
    "rollback_completed_claimed",
    "replay_completed_claimed",
    "terminal_closure_allowed",
)


class ReadOnlyWorkerRuntimeAuthorityChainWitnessError(ValueError):
    """Raised when a runtime authority chain witness artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    if not json_path.exists():
        raise FileNotFoundError(f"missing {label}: {json_path}")
    if not json_path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {json_path}")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ReadOnlyWorkerRuntimeAuthorityChainWitnessError(f"{label} must be a JSON object")
    return payload


def validate_schema_artifact(schema: Mapping[str, Any]) -> list[str]:
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


def validate_runtime_authority_chain_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one authority chain witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("read-only worker runtime authority chain witness must be a JSON object")
        return errors

    errors.extend(f"active_lease: {error}" for error in validate_active_lease_admission_witness())
    errors.extend(f"dispatch_admission: {error}" for error in validate_runtime_dispatch_admission_witness())
    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match read_only_worker_runtime_authority_chain_witness.v1")
    if record.get("selected_worker_path") != EXPECTED_WORKER_PATH:
        errors.append("selected_worker_path must be read_only_repo_inspection")
    if record.get("chain_decision") != EXPECTED_CHAIN_DECISION:
        errors.append("chain_decision must remain blocked awaiting complete live evidence")

    _validate_boolean_map("authority_scope", record.get("authority_scope"), AUTHORITY_TRUE_FIELDS, True, errors)
    _validate_boolean_map("authority_scope", record.get("authority_scope"), AUTHORITY_DENIED_FIELDS, False, errors)
    _validate_string_map("chain_stage_refs", record.get("chain_stage_refs"), REQUIRED_STAGE_REFS, errors)
    _require_subset(record, "required_evidence_refs", REQUIRED_EVIDENCE_INPUT_REFS, errors)
    _validate_boolean_map("chain_evaluation", record.get("chain_evaluation"), CHAIN_TRUE_FIELDS, True, errors)
    _validate_boolean_map("chain_evaluation", record.get("chain_evaluation"), CHAIN_DENIED_FIELDS, False, errors)
    _validate_boolean_map("recovery_and_replay", record.get("recovery_and_replay"), RECOVERY_TRUE_FIELDS, True, errors)
    _validate_boolean_map("recovery_and_replay", record.get("recovery_and_replay"), RECOVERY_DENIED_FIELDS, False, errors)
    _validate_string_map("receipt_refs", record.get("receipt_refs"), REQUIRED_RECEIPT_REFS, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    _validate_contract_summary(record, errors)
    return errors


def validate_runtime_authority_chain_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode witness."""

    schema = _load_schema(schema_path)
    errors = validate_schema_artifact(schema)
    receipt = load_json_object(receipt_path, "ReadOnlyWorkerRuntimeAuthorityChainWitness")
    errors.extend(validate_runtime_authority_chain_witness_record(receipt, schema))
    return errors


def build_mutated_runtime_authority_chain_witness(**overrides: Any) -> dict[str, Any]:
    """Return a deep-copied fixture with optional nested overrides."""

    record = load_json_object(DEFAULT_RECEIPT_PATH, "ReadOnlyWorkerRuntimeAuthorityChainWitness")
    mutated = deepcopy(record)
    for dotted_key, value in overrides.items():
        target: dict[str, Any] = mutated
        parts = dotted_key.split("__")
        for part in parts[:-1]:
            next_target = target.setdefault(part, {})
            if not isinstance(next_target, dict):
                raise ReadOnlyWorkerRuntimeAuthorityChainWitnessError(
                    f"cannot apply nested override through non-object: {dotted_key}"
                )
            target = next_target
        target[parts[-1]] = value
    return mutated


def _validate_string_map(
    field_name: str,
    value: Any,
    expected_items: Mapping[str, str],
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field_name} must be an object")
        return
    for key, expected_value in expected_items.items():
        if value.get(key) != expected_value:
            errors.append(f"{field_name}.{key} is invalid")


def _validate_boolean_map(
    field_name: str,
    value: Any,
    expected_fields: tuple[str, ...],
    expected_value: bool,
    errors: list[str],
) -> None:
    if not isinstance(value, dict):
        errors.append(f"{field_name} must be an object")
        return
    for key in expected_fields:
        if value.get(key) is not expected_value:
            errors.append(f"{field_name}.{key} must be {str(expected_value).lower()}")


def _require_subset(
    record: Mapping[str, Any],
    field_name: str,
    required_values: tuple[str, ...],
    errors: list[str],
) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    present = set(values)
    for required_value in required_values:
        if required_value not in present:
            errors.append(f"{field_name} missing required ref: {required_value}")


def _validate_contract_summary(record: Mapping[str, Any], errors: list[str]) -> None:
    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
        return
    observed_counts = {
        "stage_ref_count": len(record.get("chain_stage_refs", {}))
        if isinstance(record.get("chain_stage_refs"), dict)
        else -1,
        "required_evidence_ref_count": len(record.get("required_evidence_refs", []))
        if isinstance(record.get("required_evidence_refs"), list)
        else -1,
        "chain_true_check_count": len(CHAIN_TRUE_FIELDS),
        "chain_denied_check_count": len(CHAIN_DENIED_FIELDS),
        "recovery_true_check_count": len(RECOVERY_TRUE_FIELDS),
        "recovery_denied_check_count": len(RECOVERY_DENIED_FIELDS),
        "receipt_ref_count": len(record.get("receipt_refs", {}))
        if isinstance(record.get("receipt_refs"), dict)
        else -1,
        "evidence_ref_count": len(record.get("evidence_refs", []))
        if isinstance(record.get("evidence_refs"), list)
        else -1,
    }
    for field_name, observed_count in observed_counts.items():
        if summary.get(field_name) != observed_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _workspace_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def main() -> int:
    """CLI entry point."""

    parser = argparse.ArgumentParser(description="Validate the runtime authority chain witness.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--json", action="store_true", help="Emit a JSON validation report.")
    args = parser.parse_args()

    errors = validate_runtime_authority_chain_witness(args.schema, args.receipt)
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
        print("[FAIL] read_only_worker_runtime_authority_chain_witness")
        for error in errors:
            print(f"- {error}")
    else:
        print("[PASS] read_only_worker_runtime_authority_chain_witness")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
