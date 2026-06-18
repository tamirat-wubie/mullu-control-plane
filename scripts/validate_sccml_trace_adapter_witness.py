#!/usr/bin/env python3
"""Validate the SccmlTraceAdapterWitness contract.

Purpose: verify that SCCML trace evidence remains witness-only, digest-bound,
and separated from live kernel execution, replay, state mutation, proof
commitment, and terminal governance authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, kernel proof,
trace entry, UAO, and LifeMeaningJudgment schemas.
Invariants:
  - Validation is read-only and deterministic.
  - The Foundation example stores no raw trace, raw state, or raw secret values.
  - Live kernel execution, subprocess execution, instruction replay, state
    mutation, proof commitment, governance proof acceptance, connector calls,
    external writes, terminal closure, and success claims remain denied.
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


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "sccml_trace_adapter_witness.schema.json"
DEFAULT_WITNESS_PATH = WORKSPACE_ROOT / "examples" / "sccml_trace_adapter_witness.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:sccml-trace-adapter-witness:1"
EXPECTED_SCHEMA_TITLE = "SCCML Trace Adapter Witness"
EXPECTED_WITNESS_VERSION = "sccml_trace_adapter_witness.v1"
REQUIRED_RECEIPT_REFS = {
    "sccml_trace_adapter_witness_schema": "schemas/sccml_trace_adapter_witness.schema.json",
    "kernel_proof_schema": "schemas/kernel_proof.schema.json",
    "trace_entry_schema": "schemas/trace_entry.schema.json",
    "universal_action_orchestration_schema": "schemas/universal_action_orchestration.schema.json",
    "life_meaning_judgment_schema": "schemas/life_meaning_judgment.schema.json",
}
REQUIRED_ARTIFACT_REFS = (
    "schemas/sccml_trace_adapter_witness.schema.json",
    "examples/sccml_trace_adapter_witness.foundation.json",
    "scripts/validate_sccml_trace_adapter_witness.py",
    "tests/test_validate_sccml_trace_adapter_witness.py",
    "docs/90_sccml_trace_adapter_witness_contract.md",
    "schemas/kernel_proof.schema.json",
    "schemas/trace_entry.schema.json",
    "schemas/universal_action_orchestration.schema.json",
    "schemas/life_meaning_judgment.schema.json",
    "docs/82_cross_repo_opportunity_map.md",
)
DENIED_AUTHORITY_FIELDS = (
    "live_kernel_execution_performed",
    "subprocess_execution_performed",
    "external_repo_read_performed",
    "instruction_replay_performed",
    "state_mutation_performed",
    "proof_committed",
    "governance_proof_accepted",
    "unsupported_op_ignored",
    "connector_call_performed",
    "external_write_performed",
    "file_write_performed",
    "raw_trace_stored",
    "raw_state_stored",
    "raw_secret_value_stored",
    "terminal_closure_allowed",
    "success_claim_allowed",
)
REQUIRED_TRUE_GUARD_FIELDS = (
    "digest_refs_required",
    "state_hashes_required",
    "unsupported_ops_declared",
    "private_payload_redacted",
    "operator_review_required",
    "adapter_gap_review_required",
)
REQUIRED_FALSE_GUARD_FIELDS = (
    "raw_trace_retained",
    "raw_state_retained",
)
DIGEST_FIELDS = (
    ("trace_scope", "instruction_trace_ref"),
    ("trace_scope", "pre_state_hash_ref"),
    ("trace_scope", "post_state_hash_ref"),
    ("trace_scope", "proof_ref"),
    ("trace_scope", "unsupported_op_gap_ref"),
    ("trace_artifacts", "instruction_trace_digest_ref"),
    ("trace_artifacts", "pre_state_digest_ref"),
    ("trace_artifacts", "post_state_digest_ref"),
    ("trace_artifacts", "proof_digest_ref"),
    ("trace_artifacts", "unsupported_ops_digest_ref"),
    ("trace_artifacts", "adapter_manifest_ref"),
)


class SccmlTraceAdapterWitnessError(ValueError):
    """Raised when a SccmlTraceAdapterWitness artifact cannot load."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SccmlTraceAdapterWitnessError(f"{label} must be a JSON object")
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
            "witness_id",
            "witness_version",
            "trace_scope",
            "trace_artifacts",
            "authority_boundary",
            "trace_integrity_guard",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_sccml_trace_adapter_witness_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one SCCML trace adapter witness."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("sccml trace adapter witness must be a JSON object")
        return errors

    _validate_top_level(record, errors)
    _validate_trace_scope(record.get("trace_scope"), errors)
    _validate_authority_boundary(record.get("authority_boundary"), errors)
    _validate_trace_integrity_guard(record.get("trace_integrity_guard"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_ARTIFACT_REFS, errors)
    return errors


def validate_sccml_trace_adapter_witness(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    witness_path: Path = DEFAULT_WITNESS_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode witness."""

    schema = _load_schema(schema_path)
    witness = load_json_object(witness_path, "SccmlTraceAdapterWitness")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_sccml_trace_adapter_witness_record(witness, schema))
    return errors


def build_mutated_sccml_trace_adapter_witness(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default witness."""

    witness = load_json_object(DEFAULT_WITNESS_PATH, "SccmlTraceAdapterWitness")
    mutated = deepcopy(witness)
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


def _validate_top_level(record: dict[str, Any], errors: list[str]) -> None:
    if record.get("witness_version") != EXPECTED_WITNESS_VERSION:
        errors.append("witness_version must match sccml_trace_adapter_witness.v1")
    for parent_name, field_name in DIGEST_FIELDS:
        parent = record.get(parent_name)
        value = parent.get(field_name) if isinstance(parent, dict) else None
        _validate_digest_ref(f"{parent_name}.{field_name}", value, errors)


def _validate_trace_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("trace_scope must be an object")
        return
    if scope.get("source_kernel_family") != "symbolic-causal-chain-machine-language":
        errors.append("trace_scope.source_kernel_family must be symbolic-causal-chain-machine-language")
    if scope.get("adapter_mode") != "witness_only_operator_supplied_refs":
        errors.append("trace_scope.adapter_mode must be witness_only_operator_supplied_refs")
    if scope.get("tenant_scope") != "foundation-local-only":
        errors.append("trace_scope.tenant_scope must be foundation-local-only")
    if scope.get("life_meaning_judgment_ref") != REQUIRED_RECEIPT_REFS["life_meaning_judgment_schema"]:
        errors.append(
            "trace_scope.life_meaning_judgment_ref must be "
            f"{REQUIRED_RECEIPT_REFS['life_meaning_judgment_schema']}"
        )
    if not isinstance(scope.get("uao_ref"), str) or scope.get("uao_ref") == "":
        errors.append("trace_scope.uao_ref must be non-empty")


def _validate_authority_boundary(boundary: Any, errors: list[str]) -> None:
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
        return
    for field_name in DENIED_AUTHORITY_FIELDS:
        if boundary.get(field_name) is not False:
            errors.append(f"authority_boundary.{field_name} must be false")


def _validate_trace_integrity_guard(guard: Any, errors: list[str]) -> None:
    if not isinstance(guard, dict):
        errors.append("trace_integrity_guard must be an object")
        return
    for field_name in REQUIRED_TRUE_GUARD_FIELDS:
        if guard.get(field_name) is not True:
            errors.append(f"trace_integrity_guard.{field_name} must be true")
    for field_name in REQUIRED_FALSE_GUARD_FIELDS:
        if guard.get(field_name) is not False:
            errors.append(f"trace_integrity_guard.{field_name} must be false")
    if not isinstance(guard.get("retention_policy_ref"), str) or guard.get("retention_policy_ref") == "":
        errors.append("trace_integrity_guard.retention_policy_ref must be non-empty")


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    boundary = record.get("authority_boundary")
    guard = record.get("trace_integrity_guard")
    refs = record.get("receipt_refs")
    summary = record.get("contract_summary")
    if not isinstance(boundary, dict) or not isinstance(guard, dict) or not isinstance(refs, dict) or not isinstance(summary, dict):
        errors.append("authority_boundary, trace_integrity_guard, receipt_refs, and contract_summary must be typed")
        return
    if summary.get("witness_only") is not True:
        errors.append("contract_summary.witness_only must be true")
    if summary.get("kernel_authority_denied") is not True:
        errors.append("contract_summary.kernel_authority_denied must be true")
    if summary.get("unsupported_ops_gap_declared") is not True:
        errors.append("contract_summary.unsupported_ops_gap_declared must be true")
    expected_counts = {
        "authority_denial_count": len(DENIED_AUTHORITY_FIELDS),
        "integrity_guard_count": len(guard),
        "receipt_ref_count": len(refs),
        "evidence_ref_count": _list_len(record.get("evidence_refs")),
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")


def _validate_digest_ref(label: str, value: Any, errors: list[str]) -> None:
    if not isinstance(value, str) or value == "":
        errors.append(f"{label} must be non-empty")
        return
    if not value.startswith("hash://sha256/"):
        errors.append(f"{label} must use hash://sha256/ digest ref")
    if "http://" in value or "https://" in value or "file://" in value:
        errors.append(f"{label} must not store raw trace URL, file path, or body")


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
    """Validate SccmlTraceAdapterWitness artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate SccmlTraceAdapterWitness contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--witness", type=Path, default=DEFAULT_WITNESS_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_sccml_trace_adapter_witness(args.schema, args.witness)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "sccml_trace_adapter_witness_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "witness_path": workspace_display_path(args.witness),
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
        print("[PASS] sccml_trace_adapter_witness")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
