#!/usr/bin/env python3
"""Validate the MfidelSubstrateConformanceReceipt contract.

Purpose: verify Foundation Mode Mfidel substrate evidence without admitting
runtime SDK/kernel parity or any text-processing path that decomposes fidel.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library and scripts/validate_schemas.py.
Invariants:
  - Validation is read-only and deterministic.
  - Each fidel sequence is preserved exactly.
  - Unicode normalization, decomposition, recomposition, forbidden internal-letter modeling,
    and fidel-splitting paths remain denied.
  - Cross-runtime parity remains AwaitingEvidence until named fixtures exist.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import re
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "mfidel_substrate_conformance_receipt.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "mfidel_substrate_conformance_receipt.foundation.json"

EXPECTED_SCHEMA_ID = "urn:mullusi:schema:mfidel-substrate-conformance-receipt:1"
EXPECTED_SCHEMA_TITLE = "Mfidel Substrate Conformance Receipt"
EXPECTED_RECEIPT_VERSION = "mfidel_substrate_conformance_receipt.v1"
EXPECTED_GRID_BOUNDS = {
    "row_min": 1,
    "row_max": 34,
    "col_min": 1,
    "col_max": 8,
    "vibratory_overlay_row": 17,
    "column_8_derivation": "f[r][8] = f[r][2] + f[17][4]",
    "overlay_metadata_only": True,
}
FALSE_GUARDS = (
    "unicode_normalization_applied",
    "unicode_decomposition_performed",
    "unicode_recomposition_performed",
    "shape_decomposition_performed",
    "sound_decomposition_performed",
    "internal_letter_model_used",
    "sound_overlay_split_performed",
    "lossy_transliteration_canonical_store",
    "tokenizer_splits_fidel",
)
TRUE_GUARDS = (
    "exact_sequence_storage_required",
    "sound_overlay_metadata_only",
    "rejected_paths_logged",
)
REQUIRED_RECEIPT_REFS = {
    "mfidel_substrate_conformance_schema": "schemas/mfidel_substrate_conformance_receipt.schema.json",
    "mfidel_semantic_layer_doc": "docs/27_mfidel_semantic_layer.md",
    "cross_repo_opportunity_map": "docs/82_cross_repo_opportunity_map.md",
    "validator": "scripts/validate_mfidel_substrate_conformance_receipt.py",
    "tests": "tests/test_validate_mfidel_substrate_conformance_receipt.py",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/mfidel_substrate_conformance_receipt.schema.json",
    "examples/mfidel_substrate_conformance_receipt.foundation.json",
    "scripts/validate_mfidel_substrate_conformance_receipt.py",
    "tests/test_validate_mfidel_substrate_conformance_receipt.py",
    "docs/27_mfidel_semantic_layer.md",
    "docs/82_cross_repo_opportunity_map.md",
    "examples/sdlc/requirement_mfidel_substrate_conformance_receipt_20260616.json",
    "examples/sdlc/design_mfidel_substrate_conformance_receipt_20260616.json",
)
REQUIRED_PARITY_BLOCKERS = (
    "blocked://mfidel/python-runtime-fixture-not-bound",
    "blocked://mfidel/typescript-runtime-fixture-not-bound",
    "blocked://mfidel/rust-runtime-fixture-not-bound",
)
GRID_REF_RE = re.compile(r"^f\[(?P<row>[1-9][0-9]?)\]\[(?P<col>[1-8])\]$")


class MfidelSubstrateConformanceReceiptError(ValueError):
    """Raised when a Mfidel conformance receipt cannot be loaded."""


def load_json_object(json_path: Path, label: str) -> dict[str, Any]:
    """Load one JSON object from disk."""

    path = json_path if json_path.is_absolute() else WORKSPACE_ROOT / json_path
    if not path.exists():
        raise FileNotFoundError(f"missing {label}: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"{label} path is not a file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MfidelSubstrateConformanceReceiptError(f"{label} must be a JSON object")
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
            "source_family_refs",
            "substrate_digest",
            "grid_bounds",
            "atomic_sequence_fixtures",
            "normalization_guards",
            "cross_runtime_fixture_refs",
            "receipt_refs",
            "contract_summary",
            "evidence_refs",
        ):
            if field_name not in required_fields:
                errors.append(f"schema missing required field: {field_name}")
            if field_name not in properties:
                errors.append(f"schema missing property: {field_name}")
    return errors


def validate_mfidel_substrate_conformance_receipt_record(
    record: Any,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Return deterministic validation errors for one Mfidel conformance receipt."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("Mfidel substrate conformance receipt must be a JSON object")
        return errors

    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match mfidel_substrate_conformance_receipt.v1")
    _validate_source_family_refs(record.get("source_family_refs"), errors)
    _validate_grid_bounds(record.get("grid_bounds"), errors)
    _validate_atomic_sequence_fixtures(record.get("atomic_sequence_fixtures"), record.get("grid_bounds"), errors)
    _validate_normalization_guards(record.get("normalization_guards"), errors)
    _validate_cross_runtime_fixture_refs(record.get("cross_runtime_fixture_refs"), errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _validate_contract_summary(record, errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    return errors


def validate_mfidel_substrate_conformance_receipt(
    schema_path: Path = DEFAULT_SCHEMA_PATH,
    receipt_path: Path = DEFAULT_RECEIPT_PATH,
) -> list[str]:
    """Validate the schema artifact and default Foundation Mode receipt."""

    schema = _load_schema(schema_path)
    receipt = load_json_object(receipt_path, "MfidelSubstrateConformanceReceipt")
    errors = validate_schema_artifact(schema)
    errors.extend(validate_mfidel_substrate_conformance_receipt_record(receipt, schema))
    return errors


def build_mutated_mfidel_substrate_conformance_receipt(**updates: Any) -> dict[str, Any]:
    """Build a deterministic mutated copy of the default receipt."""

    receipt = load_json_object(DEFAULT_RECEIPT_PATH, "MfidelSubstrateConformanceReceipt")
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


def _validate_source_family_refs(source_refs: Any, errors: list[str]) -> None:
    if not isinstance(source_refs, dict):
        errors.append("source_family_refs must be an object")
        return
    if source_refs.get("live_source_reads_performed") is not False:
        errors.append("source_family_refs.live_source_reads_performed must be false in Foundation Mode")
    for field_name in ("msic_sdk_ref", "tatoken_kernel_ref", "tarc_core_ref"):
        value = source_refs.get(field_name)
        if not isinstance(value, str) or not value.startswith("repo-family://"):
            errors.append(f"source_family_refs.{field_name} must use repo-family:// prefix")


def _validate_grid_bounds(bounds: Any, errors: list[str]) -> None:
    if not isinstance(bounds, dict):
        errors.append("grid_bounds must be an object")
        return
    for field_name, expected_value in EXPECTED_GRID_BOUNDS.items():
        if bounds.get(field_name) != expected_value:
            errors.append(f"grid_bounds.{field_name} must be {expected_value!r}")


def _validate_atomic_sequence_fixtures(fixtures: Any, bounds: Any, errors: list[str]) -> None:
    if not isinstance(fixtures, list) or not fixtures:
        errors.append("atomic_sequence_fixtures must be a non-empty list")
        return
    row_min = int(bounds.get("row_min", 1)) if isinstance(bounds, dict) else 1
    row_max = int(bounds.get("row_max", 34)) if isinstance(bounds, dict) else 34
    col_min = int(bounds.get("col_min", 1)) if isinstance(bounds, dict) else 1
    col_max = int(bounds.get("col_max", 8)) if isinstance(bounds, dict) else 8
    fixture_ids: set[str] = set()
    for index, fixture in enumerate(fixtures):
        if not isinstance(fixture, dict):
            errors.append(f"atomic_sequence_fixtures[{index}] must be an object")
            continue
        fixture_id = fixture.get("fixture_id")
        if not isinstance(fixture_id, str) or not fixture_id:
            errors.append(f"atomic_sequence_fixtures[{index}].fixture_id must be non-empty")
        elif fixture_id in fixture_ids:
            errors.append(f"atomic_sequence_fixtures fixture_id duplicated: {fixture_id}")
        else:
            fixture_ids.add(fixture_id)
        sequence = fixture.get("fidel_sequence")
        preserved = fixture.get("preserved_sequence")
        if sequence != preserved:
            errors.append(f"atomic_sequence_fixtures[{index}] must preserve fidel_sequence exactly")
        if fixture.get("exact_sequence_preserved") is not True:
            errors.append(f"atomic_sequence_fixtures[{index}].exact_sequence_preserved must be true")
        if fixture.get("overlay_semantics") != "sound_overlay_metadata_only":
            errors.append(f"atomic_sequence_fixtures[{index}].overlay_semantics must be sound_overlay_metadata_only")
        grid_refs = fixture.get("grid_refs")
        if not isinstance(sequence, str) or not isinstance(grid_refs, list):
            errors.append(f"atomic_sequence_fixtures[{index}] sequence and grid_refs must be present")
            continue
        if len(sequence) != len(grid_refs):
            errors.append(f"atomic_sequence_fixtures[{index}].grid_refs must match fidel sequence length")
        for ref in grid_refs:
            match = GRID_REF_RE.match(ref) if isinstance(ref, str) else None
            if not match:
                errors.append(f"atomic_sequence_fixtures[{index}].grid_refs contains invalid ref: {ref!r}")
                continue
            row = int(match.group("row"))
            col = int(match.group("col"))
            if not (row_min <= row <= row_max and col_min <= col <= col_max):
                errors.append(f"atomic_sequence_fixtures[{index}].grid_refs contains out-of-bounds ref: {ref}")


def _validate_normalization_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("normalization_guards must be an object")
        return
    for guard_name in FALSE_GUARDS:
        if guards.get(guard_name) is not False:
            errors.append(f"normalization_guards.{guard_name} must be false")
    for guard_name in TRUE_GUARDS:
        if guards.get(guard_name) is not True:
            errors.append(f"normalization_guards.{guard_name} must be true")


def _validate_cross_runtime_fixture_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("cross_runtime_fixture_refs must be an object")
        return
    for field_name in ("python_fixture_ref", "typescript_fixture_ref", "rust_fixture_ref"):
        value = refs.get(field_name)
        if not isinstance(value, str) or not value.startswith("fixture://mfidel/"):
            errors.append(f"cross_runtime_fixture_refs.{field_name} must use fixture://mfidel/ prefix")
    if refs.get("parity_status") != "AWAITING_RUNTIME_EVIDENCE":
        errors.append("cross_runtime_fixture_refs.parity_status must remain AWAITING_RUNTIME_EVIDENCE")
    _require_subset(refs, "parity_blocked_reason_refs", REQUIRED_PARITY_BLOCKERS, errors)


def _validate_receipt_refs(refs: Any, errors: list[str]) -> None:
    if not isinstance(refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for field_name, expected_ref in REQUIRED_RECEIPT_REFS.items():
        if refs.get(field_name) != expected_ref:
            errors.append(f"receipt_refs.{field_name} must be {expected_ref}")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    fixtures = record.get("atomic_sequence_fixtures")
    refs = record.get("receipt_refs")
    evidence_refs = record.get("evidence_refs")
    source_refs = record.get("source_family_refs")
    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
        return
    expected_counts = {
        "fixture_count": len(fixtures) if isinstance(fixtures, list) else None,
        "receipt_ref_count": len(refs) if isinstance(refs, dict) else None,
        "evidence_ref_count": len(evidence_refs) if isinstance(evidence_refs, list) else None,
    }
    for field_name, expected_count in expected_counts.items():
        if expected_count is not None and summary.get(field_name) != expected_count:
            errors.append(f"contract_summary.{field_name} must match observed count")
    if isinstance(source_refs, dict) and summary.get("live_source_reads_performed") is not source_refs.get("live_source_reads_performed"):
        errors.append("contract_summary.live_source_reads_performed must match source_family_refs")
    if summary.get("runtime_parity_verified") is not False:
        errors.append("contract_summary.runtime_parity_verified must be false")
    if summary.get("terminal_closure_allowed") is not False:
        errors.append("contract_summary.terminal_closure_allowed must be false")


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    for missing_value in sorted(set(required_values) - set(values)):
        errors.append(f"{field_name} missing required ref: {missing_value}")


def main(argv: list[str] | None = None) -> int:
    """Validate MfidelSubstrateConformanceReceipt artifacts from the CLI."""

    parser = argparse.ArgumentParser(description="Validate MfidelSubstrateConformanceReceipt contract.")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH)
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT_PATH)
    parser.add_argument("--json", action="store_true", help="emit a machine-readable validation receipt")
    args = parser.parse_args(argv)
    errors = validate_mfidel_substrate_conformance_receipt(args.schema, args.receipt)
    if args.json:
        print(
            json.dumps(
                {
                    "receipt_id": "mfidel_substrate_conformance_receipt_validation",
                    "schema_path": workspace_display_path(args.schema),
                    "receipt_path": workspace_display_path(args.receipt),
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
        print("[PASS] mfidel_substrate_conformance_receipt")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
