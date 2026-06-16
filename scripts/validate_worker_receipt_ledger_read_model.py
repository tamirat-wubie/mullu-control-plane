#!/usr/bin/env python3
"""Validate the WorkerReceiptLedgerReadModel contract.

Purpose: verify that worker, lease, runtime receipt, failure, and connector
promotion evidence is projected as an operator read model without live receipt
store reads, worker dispatch, connector calls, writes, terminal closure, or raw
payload disclosure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, worker
receipt schemas, read-only worker contracts, and connector promotion gate.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example never performs live receipt-store reads.
  - Worker dispatch, connector authority, writes, terminal closure, and success
    claims remain denied.
  - Summary counts match the projected receipt chains.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "worker_receipt_ledger_read_model.schema.json"
DEFAULT_READ_MODEL_PATH = WORKSPACE_ROOT / "examples" / "worker_receipt_ledger_read_model.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:worker-receipt-ledger-read-model:1"
EXPECTED_SCHEMA_TITLE = "Worker Receipt Ledger Read Model"
EXPECTED_READ_MODEL_VERSION = "worker_receipt_ledger_read_model.v1"
EXPECTED_PROJECTION_MODE = "FOUNDATION_FIXTURE_PROJECTION"
REQUIRED_RECEIPT_REFS = {
    "worker_receipt_ledger_read_model_schema": "schemas/worker_receipt_ledger_read_model.schema.json",
    "worker_failure_receipt_schema": "schemas/worker_failure_receipt.schema.json",
    "distributed_lease_claim_receipt_schema": "schemas/distributed_lease_claim_receipt.schema.json",
    "distributed_lease_execution_receipt_schema": "schemas/distributed_lease_execution_receipt.schema.json",
    "scheduler_worker_runtime_receipt_handoff_schema": "schemas/scheduler_worker_runtime_receipt_handoff.schema.json",
    "scheduler_worker_runtime_receipt_emitter_dry_run_schema": "schemas/scheduler_worker_runtime_receipt_emitter_dry_run.schema.json",
    "read_only_worker_binding_schema": "schemas/read_only_worker_binding.schema.json",
    "read_only_worker_runtime_receipt_candidate_schema": "schemas/read_only_worker_runtime_receipt_candidate.schema.json",
    "connector_action_promotion_gate_schema": "schemas/connector_action_promotion_gate.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/worker_receipt_ledger_read_model.schema.json",
    "examples/worker_receipt_ledger_read_model.foundation.json",
    "scripts/validate_worker_receipt_ledger_read_model.py",
    "tests/test_validate_worker_receipt_ledger_read_model.py",
    "schemas/worker_failure_receipt.schema.json",
    "schemas/read_only_worker_runtime_receipt_candidate.schema.json",
    "schemas/connector_action_promotion_gate.schema.json",
    "docs/79_worker_failure_receipt_contract.md",
    "docs/84_worker_receipt_ledger_read_model_contract.md",
)
DENIED_AUTHORITY_FIELDS = (
    "live_receipt_store_read_allowed",
    "worker_dispatch_allowed",
    "runtime_receipt_emission_allowed",
    "connector_call_allowed",
    "external_write_allowed",
    "secret_access_allowed",
    "filesystem_write_allowed",
    "deployment_mutation_allowed",
    "terminal_closure_allowed",
    "success_claim_allowed",
    "raw_payload_included",
    "raw_secret_material_included",
)
DENIED_CHAIN_GUARD_FIELDS = (
    "terminal_closure_allowed",
    "success_claim_allowed",
    "raw_payload_included",
    "raw_secret_material_included",
    "live_dispatch_allowed",
)


class WorkerReceiptLedgerReadModelError(ValueError):
    """Raised when a WorkerReceiptLedgerReadModel artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise WorkerReceiptLedgerReadModelError(f"{label} must be a JSON object")
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
            "read_model_id",
            "read_model_version",
            "source_scope",
            "receipt_chains",
            "status_summary",
            "authority_denials",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_worker_receipt_ledger_read_model_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one worker receipt ledger read model."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("worker receipt ledger read model must be a JSON object")
        return errors

    _validate_top_level(record, errors)
    _validate_source_scope(record.get("source_scope"), errors)
    _validate_authority_denials(record.get("authority_denials"), errors)
    _validate_chains(record.get("receipt_chains"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_worker_receipt_ledger_read_model(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    read_model_path: Path = DEFAULT_READ_MODEL_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode read model."""

    schema = _load_schema(schema_path)
    read_model = load_json_object(read_model_path, "WorkerReceiptLedgerReadModel")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_worker_receipt_ledger_read_model_record(read_model, schema))
    return errors


def build_mutated_worker_receipt_ledger_read_model(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default read model."""

    read_model = load_json_object(DEFAULT_READ_MODEL_PATH, "WorkerReceiptLedgerReadModel")
    mutated = deepcopy(read_model)
    for dotted_key, value in updates.items():
        target = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            if segment.isdigit() and isinstance(target, list):
                target = target[int(segment)]
                continue
            next_target = target.get(segment)
            if isinstance(next_target, list):
                target = next_target
                continue
            if not isinstance(next_target, dict):
                next_target = {}
                target[segment] = next_target
            target = next_target
        final_segment = segments[-1]
        if final_segment.isdigit() and isinstance(target, list):
            target[int(final_segment)] = value
        else:
            target[final_segment] = value
    return mutated


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT))
    except ValueError:
        return str(path)


def _validate_top_level(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("read_model_version") != EXPECTED_READ_MODEL_VERSION:
        errors.append("read_model_version must match worker_receipt_ledger_read_model.v1")


def _validate_source_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("source_scope must be an object")
        return
    if scope.get("projection_mode") != EXPECTED_PROJECTION_MODE:
        errors.append("source_scope.projection_mode must be FOUNDATION_FIXTURE_PROJECTION")
    if scope.get("source_receipt_store_live_read_performed") is not False:
        errors.append("source_scope.source_receipt_store_live_read_performed must be false")
    if scope.get("fixture_projection") is not True:
        errors.append("source_scope.fixture_projection must be true")
    if scope.get("raw_payload_policy") != "DIGEST_AND_REF_ONLY":
        errors.append("source_scope.raw_payload_policy must be DIGEST_AND_REF_ONLY")


def _validate_authority_denials(authority_denials: Any, errors: list[str]) -> None:
    if not isinstance(authority_denials, dict):
        errors.append("authority_denials must be an object")
        return
    for field_name in DENIED_AUTHORITY_FIELDS:
        if authority_denials.get(field_name) is not False:
            errors.append(f"authority_denials.{field_name} must be false")
    if authority_denials.get("mfidel_atomicity_preserved") is not True:
        errors.append("authority_denials.mfidel_atomicity_preserved must be true")


def _validate_chains(chains: Any, errors: list[str]) -> None:
    if not isinstance(chains, list) or not chains:
        errors.append("receipt_chains must be a non-empty list")
        return
    for index, chain in enumerate(chains):
        if not isinstance(chain, dict):
            errors.append(f"receipt_chains[{index}] must be an object")
            continue
        _validate_one_chain(index, chain, errors)


def _validate_one_chain(index: int, chain: dict[str, Any], errors: list[str]) -> None:
    source_refs = chain.get("source_receipt_refs")
    receipt_kinds = chain.get("receipt_kinds")
    if not isinstance(source_refs, list) or not source_refs:
        errors.append(f"receipt_chains[{index}].source_receipt_refs must be a non-empty list")
    if not isinstance(receipt_kinds, list) or not receipt_kinds:
        errors.append(f"receipt_chains[{index}].receipt_kinds must be a non-empty list")
    if chain.get("latest_solver_outcome") == "SolvedVerified":
        errors.append(f"receipt_chains[{index}].latest_solver_outcome must not claim SolvedVerified in Foundation projection")
    if chain.get("chain_status") == "recovery_required":
        if chain.get("recovery_required") is not True:
            errors.append(f"receipt_chains[{index}].recovery_required must be true for recovery_required status")
        if not chain.get("recovery_obligation_refs"):
            errors.append(f"receipt_chains[{index}].recovery_obligation_refs required for recovery_required status")
    guards = chain.get("governance_guards")
    if not isinstance(guards, dict):
        errors.append(f"receipt_chains[{index}].governance_guards must be an object")
        return
    for field_name in DENIED_CHAIN_GUARD_FIELDS:
        if guards.get(field_name) is not False:
            errors.append(f"receipt_chains[{index}].governance_guards.{field_name} must be false")
    if guards.get("mfidel_atomicity_preserved") is not True:
        errors.append(f"receipt_chains[{index}].governance_guards.mfidel_atomicity_preserved must be true")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    chains = record.get("receipt_chains")
    refs = record.get("receipt_refs")
    summary = record.get("status_summary")
    contract_summary = record.get("contract_summary")
    if not isinstance(chains, list) or not isinstance(refs, dict):
        errors.append("receipt_chains and receipt_refs must be valid before summary validation")
        return
    if not isinstance(summary, dict) or not isinstance(contract_summary, dict):
        errors.append("status_summary and contract_summary must be objects")
        return
    chain_counts = _chain_counts(chains)
    for field_name, expected_count in chain_counts.items():
        if summary.get(field_name) != expected_count:
            errors.append(f"status_summary.{field_name} must match projected chains")
    blocked_reason_count = sum(_list_len(chain.get("blocked_reason_refs")) or 0 for chain in chains if isinstance(chain, dict))
    recovery_obligation_count = sum(_list_len(chain.get("recovery_obligation_refs")) or 0 for chain in chains if isinstance(chain, dict))
    expected_contract_counts = {
        "receipt_chain_count": len(chains),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
        "blocked_reason_ref_count": blocked_reason_count,
        "recovery_obligation_ref_count": recovery_obligation_count,
    }
    for field_name, expected_count in expected_contract_counts.items():
        if expected_count is not None and contract_summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match projected counts")


def _chain_counts(chains: list[Any]) -> dict[str, int]:
    object_chains = [chain for chain in chains if isinstance(chain, dict)]
    return {
        "chain_count": len(chains),
        "ready_chain_count": sum(1 for chain in object_chains if chain.get("chain_status") == "ready_for_review"),
        "blocked_chain_count": sum(1 for chain in object_chains if chain.get("chain_status") == "blocked_awaiting_evidence"),
        "failure_chain_count": sum(1 for chain in object_chains if chain.get("chain_status") == "failure_recorded"),
        "recovery_required_count": sum(1 for chain in object_chains if chain.get("chain_status") == "recovery_required"),
        "terminal_closure_allowed_count": sum(
            1 for chain in object_chains if chain.get("governance_guards", {}).get("terminal_closure_allowed") is True
        ),
        "success_claim_allowed_count": sum(
            1 for chain in object_chains if chain.get("governance_guards", {}).get("success_claim_allowed") is True
        ),
        "raw_payload_included_count": sum(
            1 for chain in object_chains if chain.get("governance_guards", {}).get("raw_payload_included") is True
        ),
        "raw_secret_material_included_count": sum(
            1 for chain in object_chains if chain.get("governance_guards", {}).get("raw_secret_material_included") is True
        ),
    }


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
    """Validate WorkerReceiptLedgerReadModel artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate WorkerReceiptLedgerReadModel contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--read-model", type=Path, default=DEFAULT_READ_MODEL_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_worker_receipt_ledger_read_model(args.schema, args.read_model)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "worker_receipt_ledger_read_model_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "read_model_path": workspace_display_path(args.read_model),
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
        print("[PASS] worker_receipt_ledger_read_model")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
