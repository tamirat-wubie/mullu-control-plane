#!/usr/bin/env python3
"""Validate the MfidelSubstrateConformanceReceipt contract.

Purpose: verify Mfidel substrate conformance receipts for grid bounds,
runtime digests, exact sequence preservation, no-normalization proof refs, and
cross-runtime evidence gaps.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: Python standard library, schema validation helpers, and local
MCOI Mfidel runtime modules.
Invariants:
  - Validation is read-only and deterministic.
  - Each fidel remains an atomic symbol; no decomposition is admitted.
  - Unicode normalization, decomposition, and recomposition remain denied.
  - Foundation Mode does not claim cross-runtime closure for SDK/kernel gaps.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
MCOI_ROOT = WORKSPACE_ROOT / "mcoi"
for import_path in (WORKSPACE_ROOT, MCOI_ROOT):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

from mcoi_runtime.core.mfidel_matrix import MfidelMatrix  # noqa: E402
from mcoi_runtime.substrate.mfidel.grid import (  # noqa: E402
    AUDIO_OVERLAY_EXCEPTIONS,
    GRID_COLS,
    GRID_ROWS,
    MFIDEL_GRID,
    VOWEL_ROW,
)
from scripts.validate_schemas import _load_schema, _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA_PATH = WORKSPACE_ROOT / "schemas" / "mfidel_substrate_conformance_receipt.schema.json"
DEFAULT_RECEIPT_PATH = WORKSPACE_ROOT / "examples" / "mfidel_substrate_conformance_receipt.foundation.json"
EXPECTED_SCHEMA_ID = "urn:mullusi:schema:mfidel-substrate-conformance-receipt:1"
EXPECTED_SCHEMA_TITLE = "Mfidel Substrate Conformance Receipt"
EXPECTED_RECEIPT_VERSION = "mfidel_substrate_conformance_receipt.v1"
EXPECTED_PROJECTION_MODE = "foundation_cross_runtime_conformance"
EXPECTED_GRID_ROWS = 34
EXPECTED_GRID_COLS = 8
EXPECTED_VECTOR_DIMENSION = 272
EXPECTED_NON_EMPTY_FIDEL_COUNT = 269
EXPECTED_EMPTY_SLOT_COUNT = 3
EXPECTED_EMPTY_SLOTS = ((20, 8), (21, 8), (24, 8))
EXPECTED_OVERLAY_EXCEPTIONS = ((1, 1, 17, 8), (3, 1, 17, 8))
LOCAL_RUNTIME_BINDINGS = {
    "python-substrate-grid",
    "python-legacy-matrix-view",
    "python-contracts-mfidel",
}
REQUIRED_AWAITING_BINDINGS = {
    "typescript-msic-sdk",
    "rust-tatoken-kernel",
    "rust-tarc-core",
}
REQUIRED_RECEIPT_REFS = {
    "mfidel_substrate_conformance_schema": "schemas/mfidel_substrate_conformance_receipt.schema.json",
    "mfidel_grid_runtime": "mcoi/mcoi_runtime/substrate/mfidel/grid.py",
    "mfidel_matrix_runtime": "mcoi/mcoi_runtime/core/mfidel_matrix.py",
    "mfidel_contract_runtime": "mcoi/mcoi_runtime/contracts/mfidel.py",
    "mfidel_atomicity_tests": "mcoi/tests/test_mfidel_atomicity.py",
    "mfidel_matrix_tests": "mcoi/tests/test_mfidel_matrix.py",
}
REQUIRED_EVIDENCE_REFS = (
    "schemas/mfidel_substrate_conformance_receipt.schema.json",
    "examples/mfidel_substrate_conformance_receipt.foundation.json",
    "scripts/validate_mfidel_substrate_conformance_receipt.py",
    "tests/test_validate_mfidel_substrate_conformance_receipt.py",
    "mcoi/mcoi_runtime/substrate/mfidel/grid.py",
    "mcoi/mcoi_runtime/core/mfidel_matrix.py",
    "mcoi/mcoi_runtime/contracts/mfidel.py",
    "mcoi/tests/test_mfidel_atomicity.py",
    "mcoi/tests/test_mfidel_matrix.py",
    "docs/27_mfidel_semantic_layer.md",
    "docs/85_mfidel_substrate_conformance_receipt_contract.md",
    "examples/sdlc/requirement_mfidel_substrate_conformance_receipt_20260616.json",
    "examples/sdlc/design_mfidel_substrate_conformance_receipt_20260616.json",
    "examples/sdlc/security_review_mfidel_substrate_conformance_receipt_20260616.json",
)
FALSE_GUARDS = (
    "unicode_normalization_allowed",
    "unicode_decomposition_allowed",
    "unicode_recomposition_allowed",
    "root_letter_model_allowed",
    "consonant_vowel_split_allowed",
    "lossy_transliteration_canonical_allowed",
    "phoneme_identity_substitution_allowed",
    "overlay_structural_decomposition_allowed",
    "raw_secret_material_included",
    "live_runtime_import_authority_allowed",
    "terminal_closure_allowed",
)
SOURCE_NORMALIZATION_PATTERNS = (
    "unicodedata",
    "normalize(",
    "NFD",
    "NFKD",
    "NFC",
    "NFKC",
)


class MfidelSubstrateConformanceReceiptError(ValueError):
    """Raised when a MfidelSubstrateConformanceReceipt artifact cannot load."""


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


def canonical_source_digest(source_path: Path) -> str:
    """Return the repository-stable SHA-256 digest for a text source file."""

    source_text = source_path.read_text(encoding="utf-8")
    canonical_text = source_text.replace("\r\n", "\n")
    return hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()


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
            "checked_at",
            "solver_outcome",
            "substrate_scope",
            "runtime_bindings",
            "grid_contract",
            "atomicity_guards",
            "exact_preservation_witnesses",
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
    """Return deterministic validation errors for one conformance receipt."""

    schema_payload = schema or _load_schema(DEFAULT_SCHEMA_PATH)
    errors = _validate_schema_instance(schema_payload, record)
    if not isinstance(record, dict):
        errors.append("mfidel substrate conformance receipt must be a JSON object")
        return errors

    if record.get("receipt_version") != EXPECTED_RECEIPT_VERSION:
        errors.append("receipt_version must match mfidel_substrate_conformance_receipt.v1")

    _validate_substrate_scope(record.get("substrate_scope"), errors)
    _validate_grid_contract(record.get("grid_contract"), errors)
    _validate_atomicity_guards(record.get("atomicity_guards"), errors)
    _validate_runtime_bindings(record.get("runtime_bindings"), errors)
    _validate_exact_preservation_witnesses(record.get("exact_preservation_witnesses"), errors)
    _validate_contract_summary(record, errors)
    _validate_receipt_refs(record.get("receipt_refs"), errors)
    _require_subset(record, "evidence_refs", REQUIRED_EVIDENCE_REFS, errors)
    _validate_solver_outcome(record, errors)
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
        target: Any = mutated
        segments = dotted_key.split("__")
        for segment in segments[:-1]:
            if isinstance(target, list):
                target = target[int(segment)]
                continue
            next_target = target.get(segment)
            if not isinstance(next_target, (dict, list)):
                next_target = {}
                target[segment] = next_target
            target = next_target
        final_segment = segments[-1]
        if isinstance(target, list):
            target[int(final_segment)] = value
        else:
            target[final_segment] = value
    return mutated


def workspace_display_path(path: Path) -> str:
    """Return a stable workspace-relative display path when possible."""

    resolved_path = path if path.is_absolute() else WORKSPACE_ROOT / path
    try:
        return str(resolved_path.resolve().relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def _validate_substrate_scope(scope: Any, errors: list[str]) -> None:
    if not isinstance(scope, dict):
        errors.append("substrate_scope must be an object")
        return
    if scope.get("projection_mode") != EXPECTED_PROJECTION_MODE:
        errors.append(f"substrate_scope.projection_mode must be {EXPECTED_PROJECTION_MODE}")
    if scope.get("foundation_mode") is not True:
        errors.append("substrate_scope.foundation_mode must be true")
    if scope.get("grid_rows") != GRID_ROWS or scope.get("grid_rows") != EXPECTED_GRID_ROWS:
        errors.append("substrate_scope.grid_rows must match runtime grid rows")
    if scope.get("grid_cols") != GRID_COLS or scope.get("grid_cols") != EXPECTED_GRID_COLS:
        errors.append("substrate_scope.grid_cols must match runtime grid cols")
    if scope.get("vector_dimension") != EXPECTED_VECTOR_DIMENSION:
        errors.append("substrate_scope.vector_dimension must be 272")
    non_empty_count = sum(1 for row in MFIDEL_GRID for glyph in row if glyph)
    empty_count = sum(1 for row in MFIDEL_GRID for glyph in row if not glyph)
    if scope.get("non_empty_fidel_count") != non_empty_count:
        errors.append("substrate_scope.non_empty_fidel_count must match runtime grid")
    if scope.get("empty_slot_count") != empty_count:
        errors.append("substrate_scope.empty_slot_count must match runtime grid")
    if scope.get("vowel_overlay_row") != VOWEL_ROW:
        errors.append("substrate_scope.vowel_overlay_row must match runtime vowel row")
    if scope.get("cross_runtime_closure_claimed") is not False:
        errors.append("substrate_scope.cross_runtime_closure_claimed must remain false in Foundation Mode")


def _validate_grid_contract(grid_contract: Any, errors: list[str]) -> None:
    if not isinstance(grid_contract, dict):
        errors.append("grid_contract must be an object")
        return
    if grid_contract.get("coordinate_reference") != "f[row][col]":
        errors.append("grid_contract.coordinate_reference must be f[row][col]")
    if grid_contract.get("row_min") != 1 or grid_contract.get("row_max") != GRID_ROWS:
        errors.append("grid_contract row bounds must match runtime grid")
    if grid_contract.get("col_min") != 1 or grid_contract.get("col_max") != GRID_COLS:
        errors.append("grid_contract col bounds must match runtime grid")
    if grid_contract.get("vowel_overlay_row") != VOWEL_ROW:
        errors.append("grid_contract.vowel_overlay_row must match runtime vowel row")
    empty_slots = tuple(
        sorted((item.get("row"), item.get("col")) for item in grid_contract.get("empty_slots", []))
    )
    if empty_slots != EXPECTED_EMPTY_SLOTS:
        errors.append("grid_contract.empty_slots must match canonical empty positions")
    overlay_exceptions = tuple(
        sorted(
            (
                item.get("source", {}).get("row"),
                item.get("source", {}).get("col"),
                item.get("overlay", {}).get("row"),
                item.get("overlay", {}).get("col"),
            )
            for item in grid_contract.get("overlay_exceptions", [])
            if isinstance(item, dict)
        )
    )
    runtime_overlay_exceptions = tuple(
        sorted((source.row, source.col, overlay.row, overlay.col) for source, overlay in AUDIO_OVERLAY_EXCEPTIONS.items())
    )
    if overlay_exceptions != EXPECTED_OVERLAY_EXCEPTIONS or overlay_exceptions != runtime_overlay_exceptions:
        errors.append("grid_contract.overlay_exceptions must match runtime overlay exceptions")
    if grid_contract.get("column_8_derivation") != "f[r][8] = f[r][2] + f[17][4]":
        errors.append("grid_contract.column_8_derivation must match Mfidel rule")
    if grid_contract.get("overlay_is_sound_metadata_only") is not True:
        errors.append("grid_contract.overlay_is_sound_metadata_only must be true")


def _validate_atomicity_guards(guards: Any, errors: list[str]) -> None:
    if not isinstance(guards, dict):
        errors.append("atomicity_guards must be an object")
        return
    for guard_name in FALSE_GUARDS:
        if guards.get(guard_name) is not False:
            errors.append(f"atomicity_guards.{guard_name} must be false")


def _validate_runtime_bindings(bindings: Any, errors: list[str]) -> None:
    if not isinstance(bindings, list):
        errors.append("runtime_bindings must be a list")
        return
    binding_ids = {binding.get("binding_id") for binding in bindings if isinstance(binding, dict)}
    missing_local = LOCAL_RUNTIME_BINDINGS - binding_ids
    missing_awaiting = REQUIRED_AWAITING_BINDINGS - binding_ids
    for binding_id in sorted(missing_local):
        errors.append(f"runtime_bindings missing local binding: {binding_id}")
    for binding_id in sorted(missing_awaiting):
        errors.append(f"runtime_bindings missing awaiting-evidence binding: {binding_id}")

    for index, binding in enumerate(bindings):
        if not isinstance(binding, dict):
            errors.append(f"runtime_bindings[{index}] must be an object")
            continue
        binding_id = binding.get("binding_id")
        implementation_ref = binding.get("implementation_ref")
        status = binding.get("conformance_status")
        digest = binding.get("digest_sha256")
        if binding_id in LOCAL_RUNTIME_BINDINGS:
            if status != "validated":
                errors.append(f"runtime_bindings[{index}].conformance_status must be validated")
            if not isinstance(implementation_ref, str):
                errors.append(f"runtime_bindings[{index}].implementation_ref must be a string")
                continue
            source_path = WORKSPACE_ROOT / implementation_ref
            if not source_path.exists():
                errors.append(f"runtime_bindings[{index}].implementation_ref missing: {implementation_ref}")
                continue
            source_text = source_path.read_text(encoding="utf-8")
            for pattern in SOURCE_NORMALIZATION_PATTERNS:
                if pattern in source_text:
                    errors.append(f"runtime_bindings[{index}] source contains forbidden normalization pattern: {pattern}")
            actual_digest = canonical_source_digest(source_path)
            if digest != actual_digest:
                errors.append(f"runtime_bindings[{index}].digest_sha256 does not match implementation_ref")
            if not binding.get("no_normalization_proof_refs"):
                errors.append(f"runtime_bindings[{index}].no_normalization_proof_refs required")
            if not binding.get("exact_preservation_proof_refs"):
                errors.append(f"runtime_bindings[{index}].exact_preservation_proof_refs required")
            if binding.get("gap_refs"):
                errors.append(f"runtime_bindings[{index}].gap_refs must be empty for validated local binding")
        elif binding_id in REQUIRED_AWAITING_BINDINGS:
            if status != "awaiting_evidence":
                errors.append(f"runtime_bindings[{index}].conformance_status must be awaiting_evidence")
            if digest is not None:
                errors.append(f"runtime_bindings[{index}].digest_sha256 must be null until evidence exists")
            if binding.get("no_normalization_proof_refs"):
                errors.append(f"runtime_bindings[{index}].no_normalization_proof_refs must be empty until evidence exists")
            if binding.get("exact_preservation_proof_refs"):
                errors.append(f"runtime_bindings[{index}].exact_preservation_proof_refs must be empty until evidence exists")
            if not binding.get("gap_refs"):
                errors.append(f"runtime_bindings[{index}].gap_refs required for awaiting-evidence binding")


def _validate_exact_preservation_witnesses(witnesses: Any, errors: list[str]) -> None:
    if not isinstance(witnesses, list):
        errors.append("exact_preservation_witnesses must be a list")
        return
    for index, witness in enumerate(witnesses):
        if not isinstance(witness, dict):
            errors.append(f"exact_preservation_witnesses[{index}] must be an object")
            continue
        input_sequence = witness.get("input_sequence")
        if not isinstance(input_sequence, str):
            errors.append(f"exact_preservation_witnesses[{index}].input_sequence must be a string")
            continue
        if witness.get("normalization_applied") is not False:
            errors.append(f"exact_preservation_witnesses[{index}].normalization_applied must be false")
        expected_codepoints = [f"U+{ord(char):04X}" for char in input_sequence]
        if witness.get("codepoints") != expected_codepoints:
            errors.append(f"exact_preservation_witnesses[{index}].codepoints must match input_sequence")
        try:
            sequence = MfidelMatrix.text_to_fidel_sequence(input_sequence)
        except ValueError as exc:
            errors.append(f"exact_preservation_witnesses[{index}].input_sequence rejected: {exc}")
            continue
        actual_positions = [{"row": fidel.row, "col": fidel.col} for fidel in sequence]
        if witness.get("expected_positions") != actual_positions:
            errors.append(f"exact_preservation_witnesses[{index}].expected_positions must match runtime lookup")
        if len(sequence) != len(input_sequence):
            errors.append(f"exact_preservation_witnesses[{index}] must preserve one fidel per input symbol")


def _validate_contract_summary(record: dict[str, Any], errors: list[str]) -> None:
    summary = record.get("contract_summary")
    if not isinstance(summary, dict):
        errors.append("contract_summary must be an object")
        return
    bindings = record.get("runtime_bindings", [])
    witnesses = record.get("exact_preservation_witnesses", [])
    evidence_refs = record.get("evidence_refs", [])
    if isinstance(bindings, list):
        validated_count = sum(1 for binding in bindings if isinstance(binding, dict) and binding.get("conformance_status") == "validated")
        awaiting_count = sum(1 for binding in bindings if isinstance(binding, dict) and binding.get("conformance_status") == "awaiting_evidence")
        if summary.get("runtime_binding_count") != len(bindings):
            errors.append("contract_summary.runtime_binding_count must match runtime_bindings")
        if summary.get("validated_binding_count") != validated_count:
            errors.append("contract_summary.validated_binding_count must match runtime_bindings")
        if summary.get("awaiting_evidence_binding_count") != awaiting_count:
            errors.append("contract_summary.awaiting_evidence_binding_count must match runtime_bindings")
    if isinstance(witnesses, list) and summary.get("exact_preservation_witness_count") != len(witnesses):
        errors.append("contract_summary.exact_preservation_witness_count must match exact_preservation_witnesses")
    if isinstance(evidence_refs, list) and summary.get("evidence_ref_count") != len(evidence_refs):
        errors.append("contract_summary.evidence_ref_count must match evidence_refs")


def _validate_receipt_refs(receipt_refs: Any, errors: list[str]) -> None:
    if not isinstance(receipt_refs, dict):
        errors.append("receipt_refs must be an object")
        return
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"receipt_refs.{key} must be {expected_value}")


def _validate_solver_outcome(record: dict[str, Any], errors: list[str]) -> None:
    bindings = record.get("runtime_bindings", [])
    awaiting_count = 0
    if isinstance(bindings, list):
        awaiting_count = sum(
            1 for binding in bindings if isinstance(binding, dict) and binding.get("conformance_status") == "awaiting_evidence"
        )
    if awaiting_count and record.get("solver_outcome") != "AwaitingEvidence":
        errors.append("solver_outcome must remain AwaitingEvidence while runtime bindings await evidence")


def _require_subset(record: dict[str, Any], field_name: str, required_values: tuple[str, ...], errors: list[str]) -> None:
    values = record.get(field_name)
    if not isinstance(values, list):
        errors.append(f"{field_name} must be a list")
        return
    observed = set(values)
    for required_value in required_values:
        if required_value not in observed:
            errors.append(f"{field_name} missing required ref: {required_value}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description="Validate Mfidel substrate conformance receipt.")
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA_PATH), help="Path to schema JSON.")
    parser.add_argument("--receipt", default=str(DEFAULT_RECEIPT_PATH), help="Path to receipt JSON.")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable result.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""

    args = parse_args(argv)
    schema_path = Path(args.schema)
    receipt_path = Path(args.receipt)
    errors = validate_mfidel_substrate_conformance_receipt(schema_path, receipt_path)
    if args.json:
        print(
            json.dumps(
                {
                    "status": "failed" if errors else "passed",
                    "schema_path": workspace_display_path(schema_path),
                    "receipt_path": workspace_display_path(receipt_path),
                    "errors": errors,
                },
                indent=2,
                sort_keys=True,
            )
        )
    elif errors:
        for error in errors:
            print(f"[FAIL] {error}")
        print("STATUS: failed")
    else:
        print("[PASS] mfidel_substrate_conformance_receipt")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
