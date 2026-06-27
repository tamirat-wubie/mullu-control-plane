#!/usr/bin/env python3
"""Validate Agentic Service Harness non-empty diff file summary receipt.

Purpose: prove non-empty diff/file summary receipt evidence remains blocked
until concrete filesystem-write receipt, redaction, UAO, and receipt-store
evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_non_empty_diff_file_summary_receipt.schema.json,
examples/agentic_service_harness_non_empty_diff_file_summary_receipt.foundation.json,
scripts.validate_agentic_service_harness_actual_diff_collection_receipt,
scripts.validate_agentic_service_harness_non_empty_diff_receipt_admission_preflight,
scripts.validate_agentic_service_harness_filesystem_write_admission_preflight,
and scripts.validate_schemas.
Invariants:
  - The receipt binds zero-diff, non-empty admission, and filesystem-write preflight sources.
  - Concrete filesystem-write receipt and redacted diff bundle remain AwaitingEvidence.
  - Raw diffs, raw file content, receipt append, mutation routes, secrets, and
    terminal closure remain denied.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_actual_diff_collection_receipt import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_ACTUAL_DIFF_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_ACTUAL_DIFF_SCHEMA,
    validate_agentic_service_harness_actual_diff_collection_receipt,
)
from scripts.validate_agentic_service_harness_filesystem_write_admission_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_FILESYSTEM_PREFLIGHT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_FILESYSTEM_PREFLIGHT_SCHEMA,
    validate_agentic_service_harness_filesystem_write_admission_preflight,
)
from scripts.validate_agentic_service_harness_non_empty_diff_receipt_admission_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_NON_EMPTY_PREFLIGHT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_NON_EMPTY_PREFLIGHT_SCHEMA,
    validate_agentic_service_harness_non_empty_diff_receipt_admission_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_non_empty_diff_file_summary_receipt.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_non_empty_diff_file_summary_receipt.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_non_empty_diff_file_summary_receipt_validation.json"
)
EXPECTED_RECEIPT_ID = "agentic_service_harness_non_empty_diff_file_summary_receipt"
EXPECTED_ACTUAL_DIFF_REF = "examples/agentic_service_harness_actual_diff_collection_receipt.foundation.json"
EXPECTED_NON_EMPTY_PREFLIGHT_REF = (
    "examples/agentic_service_harness_non_empty_diff_receipt_admission_preflight.foundation.json"
)
EXPECTED_FILESYSTEM_PREFLIGHT_REF = "examples/agentic_service_harness_filesystem_write_admission_preflight.foundation.json"
EXPECTED_FILESYSTEM_WRITE_RECEIPT_REF = "evidence://actual-filesystem-write-receipt"
EXPECTED_REDACTED_DIFF_BUNDLE_REF = "digest://redacted-diff-bundle"
EXPECTED_RECEIPT_STORE_WRITE_PATH_REF = "evidence://receipt-store-write-path-for-diff-collection"
EXPECTED_CLEANUP_RECEIPT_REF = "receipt://sandbox-cleanup-branchwrite"
EXPECTED_REDACTION_REF = "evidence://redaction-policy-for-file-change-collection"
EXPECTED_UAO_REF = "evidence://uao-non-empty-diff-file-summary"
REQUIRED_SOURCE_REFS = (
    EXPECTED_ACTUAL_DIFF_REF,
    EXPECTED_NON_EMPTY_PREFLIGHT_REF,
    EXPECTED_FILESYSTEM_PREFLIGHT_REF,
    EXPECTED_FILESYSTEM_WRITE_RECEIPT_REF,
    EXPECTED_REDACTED_DIFF_BUNDLE_REF,
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
REQUIRED_BEFORE_REFS = (
    EXPECTED_ACTUAL_DIFF_REF,
    EXPECTED_NON_EMPTY_PREFLIGHT_REF,
    EXPECTED_FILESYSTEM_PREFLIGHT_REF,
    EXPECTED_FILESYSTEM_WRITE_RECEIPT_REF,
    EXPECTED_REDACTED_DIFF_BUNDLE_REF,
    "evidence://branch-write-authority-binding",
    "evidence://workspace-write-authority",
    EXPECTED_CLEANUP_RECEIPT_REF,
    EXPECTED_REDACTION_REF,
    EXPECTED_UAO_REF,
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
)
REQUIRED_BLOCKERS = (
    "blocked://filesystem-write-receipt/not-verified",
    "blocked://redacted-diff-bundle/not-verified",
    "blocked://operator-approval/not-collected",
    "blocked://branch-write-authority/not-verified",
    "blocked://workspace-write-authority/not-verified",
    "blocked://cleanup-receipt/not-verified",
    "blocked://redaction-evidence/not-verified",
    "blocked://uao-non-empty-diff-file-summary/not-verified",
    "blocked://receipt-store-write-path/not-verified",
    "blocked://raw-diff-body/not-allowed",
    "blocked://secret-paths/not-allowed",
)
REQUIRED_NEXT_REFS = (
    "witness://github-pr-admission-preflight",
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "witness://diff-output-redacted",
    "witness://non-empty-file-summary-redacted",
)
REQUIRED_RECEIPT_REFS = {
    "non_empty_diff_file_summary_receipt_schema": (
        "schemas/agentic_service_harness_non_empty_diff_file_summary_receipt.schema.json"
    ),
    "non_empty_diff_receipt_admission_preflight_schema": (
        "schemas/agentic_service_harness_non_empty_diff_receipt_admission_preflight.schema.json"
    ),
    "filesystem_write_admission_preflight_schema": (
        "schemas/agentic_service_harness_filesystem_write_admission_preflight.schema.json"
    ),
    "actual_diff_collection_receipt_schema": "schemas/agentic_service_harness_actual_diff_collection_receipt.schema.json",
    "receipt_store_write_path_ref": EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "cleanup_receipt_ref": EXPECTED_CLEANUP_RECEIPT_REF,
    "uao_non_empty_diff_file_summary_ref": EXPECTED_UAO_REF,
}
REQUIRED_FALSE_FLAGS = (
    "filesystem_write_receipt_verified",
    "redacted_diff_bundle_verified",
    "non_empty_diff_file_summary_receipt_admitted",
    "branch_write_authority_verified",
    "workspace_write_authority_verified",
    "operator_approval_collected",
    "cleanup_receipt_verified",
    "redaction_evidence_verified",
    "uao_non_empty_diff_file_summary_verified",
    "receipt_store_write_path_verified",
    "raw_diff_body_serialized",
    "raw_file_content_serialized",
    "branch_write_enabled",
    "workspace_write_enabled",
    "filesystem_write_executed",
    "raw_diff_body_stored",
    "raw_file_content_stored",
    "receipt_store_append_enabled",
    "runtime_state_write_enabled",
    "connector_calls_enabled",
    "mutation_route_enabled",
    "secret_values_serialized",
    "terminal_closure",
    "raw_secret_value_storage_allowed",
    "raw_output_storage_allowed",
)
REQUIRED_TRUE_FLAGS = (
    "actual_diff_collection_receipt_verified",
    "non_empty_diff_receipt_admission_preflight_verified",
    "filesystem_write_admission_preflight_verified",
    "secret_redaction_required",
    "diff_redaction_required",
    "receipt_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "secret_redaction_required",
    "secret_values_serialized",
    "raw_secret_value_storage_allowed",
}
FORBIDDEN_SECRET_KEY_TOKENS = (
    "access_token",
    "api_key",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "secret_value",
    "token",
)
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class NonEmptyDiffFileSummaryReceiptValidation:
    """Schema and semantic validation report for non-empty diff file summary receipt."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    filesystem_write_receipt_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_non_empty_diff_file_summary_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> NonEmptyDiffFileSummaryReceiptValidation:
    """Validate non-empty diff file summary receipt examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "non-empty diff file summary receipt schema", errors)
    _validate_source_contracts(errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"non-empty diff file summary receipt example {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_receipt_semantics(example, errors, _path_label(example_path))
    return NonEmptyDiffFileSummaryReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        filesystem_write_receipt_ref=EXPECTED_FILESYSTEM_WRITE_RECEIPT_REF,
    )


def _validate_source_contracts(errors: list[str]) -> None:
    actual_diff = validate_agentic_service_harness_actual_diff_collection_receipt(
        schema_path=DEFAULT_ACTUAL_DIFF_SCHEMA,
        example_paths=DEFAULT_ACTUAL_DIFF_EXAMPLES,
    )
    if not actual_diff.ok:
        errors.extend(f"actual diff receipt: {error}" for error in actual_diff.errors)
    non_empty_preflight = validate_agentic_service_harness_non_empty_diff_receipt_admission_preflight(
        schema_path=DEFAULT_NON_EMPTY_PREFLIGHT_SCHEMA,
        example_paths=DEFAULT_NON_EMPTY_PREFLIGHT_EXAMPLES,
    )
    if not non_empty_preflight.ok:
        errors.extend(f"non-empty diff admission preflight: {error}" for error in non_empty_preflight.errors)
    filesystem_preflight = validate_agentic_service_harness_filesystem_write_admission_preflight(
        schema_path=DEFAULT_FILESYSTEM_PREFLIGHT_SCHEMA,
        example_paths=DEFAULT_FILESYSTEM_PREFLIGHT_EXAMPLES,
    )
    if not filesystem_preflight.ok:
        errors.extend(f"filesystem write admission preflight: {error}" for error in filesystem_preflight.errors)


def write_non_empty_diff_file_summary_receipt_validation(
    validation: NonEmptyDiffFileSummaryReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic non-empty diff file summary receipt validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_path


def build_mutated_receipt(**updates: Any) -> dict[str, Any]:
    """Return the default example with nested updates for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default non-empty diff file summary receipt example", [])
    mutated = deepcopy(payload)
    for dotted_key, value in updates.items():
        cursor: dict[str, Any] = mutated
        parts = dotted_key.split("__")
        for part in parts[:-1]:
            next_value = cursor.setdefault(part, {})
            if not isinstance(next_value, dict):
                raise ValueError(f"cannot descend into non-object field: {dotted_key}")
            cursor = next_value
        cursor[parts[-1]] = value
    return mutated


def _validate_receipt_semantics(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    _check_value(receipt, ("receipt_id",), EXPECTED_RECEIPT_ID, errors, label)
    _check_value(receipt, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _check_value(
        receipt,
        ("receipt_status",),
        "blocked_until_filesystem_write_receipt_redaction_uao_and_receipt_store",
        errors,
        label,
    )
    _require_all_refs(receipt.get("source_contract_refs"), REQUIRED_SOURCE_REFS, "source_contract_refs", errors, label)
    _validate_source_evidence(receipt, errors, label)
    _validate_admission_gates(receipt, errors, label)
    _validate_non_empty_summary(receipt, errors, label)
    _validate_receipt_refs(receipt, errors, label)
    _validate_next_action(receipt, errors, label)
    _validate_flags(receipt, errors, label)
    _scan_forbidden_text(receipt, errors, label)


def _validate_source_evidence(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    source = _mapping(receipt.get("source_evidence"))
    expected_values = {
        "actual_diff_collection_receipt_ref": EXPECTED_ACTUAL_DIFF_REF,
        "non_empty_diff_receipt_admission_preflight_ref": EXPECTED_NON_EMPTY_PREFLIGHT_REF,
        "filesystem_write_admission_preflight_ref": EXPECTED_FILESYSTEM_PREFLIGHT_REF,
        "filesystem_write_receipt_ref": EXPECTED_FILESYSTEM_WRITE_RECEIPT_REF,
        "redacted_diff_bundle_ref": EXPECTED_REDACTED_DIFF_BUNDLE_REF,
    }
    for key, expected_value in expected_values.items():
        if source.get(key) != expected_value:
            errors.append(f"{label}: source_evidence.{key} must be {expected_value}")


def _validate_admission_gates(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = _mapping(receipt.get("admission_gates"))
    _require_all_refs(
        gates.get("required_before_non_empty_summary_refs"),
        REQUIRED_BEFORE_REFS,
        "admission_gates.required_before_non_empty_summary_refs",
        errors,
        label,
    )
    _require_all_refs(gates.get("blocked_reason_refs"), REQUIRED_BLOCKERS, "admission_gates.blocked_reason_refs", errors, label)
    _require_all_refs(
        gates.get("next_required_evidence_refs"),
        REQUIRED_NEXT_REFS,
        "admission_gates.next_required_evidence_refs",
        errors,
        label,
    )


def _validate_non_empty_summary(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(receipt.get("non_empty_summary"))
    if summary.get("candidate_changed_file_count") != 0:
        errors.append(f"{label}: non_empty_summary.candidate_changed_file_count must be 0 until evidence exists")
    if summary.get("changed_file_refs") != []:
        errors.append(f"{label}: non_empty_summary.changed_file_refs must be empty")
    if summary.get("diff_refs") != []:
        errors.append(f"{label}: non_empty_summary.diff_refs must be empty")
    if summary.get("redacted_summary_ref") != "summary://not-admitted":
        errors.append(f"{label}: non_empty_summary.redacted_summary_ref must remain not-admitted")
    if summary.get("redacted_diff_bundle_ref") != "diff-bundle://not-admitted":
        errors.append(f"{label}: non_empty_summary.redacted_diff_bundle_ref must remain not-admitted")
    if summary.get("receipt_append_ref") != "blocked://receipt-store-write-path/not-verified":
        errors.append(f"{label}: non_empty_summary.receipt_append_ref must remain blocked")


def _validate_receipt_refs(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_refs = _mapping(receipt.get("receipt_refs"))
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"{label}: receipt_refs.{key} must be {expected_value}")


def _validate_next_action(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = receipt.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be text")
        return
    for phrase in ("concrete filesystem write receipt", "redacted diff bundle", "terminal closure blocked"):
        if phrase not in next_action:
            errors.append(f"{label}: next_action missing phrase {phrase}")


def _validate_flags(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(receipt):
        if not path:
            continue
        key = path[-1]
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {'.'.join(path)} must be false")
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {'.'.join(path)} must be true")


def _scan_forbidden_text(value: Any, errors: list[str], label: str) -> None:
    for path in _walk_paths(value):
        key = path[-1]
        normalized_key = key.lower()
        if key not in ALLOWED_SECRET_KEYS:
            for token in FORBIDDEN_SECRET_KEY_TOKENS:
                if token in normalized_key:
                    errors.append(f"{label}: forbidden secret-bearing key {'.'.join(path)}")
    for path, item in _walk(value):
        if isinstance(item, str):
            if MUTATION_ROUTE_PATTERN.search(item):
                errors.append(f"{label}: mutation route string at {'.'.join(path)}")
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(item):
                    errors.append(f"{label}: credential-like value at {'.'.join(path)}")


def _load_json_object(path: Path, description: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{description} load failed: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{description} must be a JSON object")
        return {}
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _check_value(payload: Mapping[str, Any], path: tuple[str, ...], expected: Any, errors: list[str], label: str) -> None:
    cursor: Any = payload
    for part in path:
        if not isinstance(cursor, Mapping) or part not in cursor:
            errors.append(f"{label}: missing {'.'.join(path)}")
            return
        cursor = cursor[part]
    if cursor != expected:
        errors.append(f"{label}: {'.'.join(path)} must be {expected}")


def _require_all_refs(observed: Any, required: Iterable[str], field: str, errors: list[str], label: str) -> None:
    observed_set = set(observed) if isinstance(observed, list) else set()
    for required_ref in required:
        if required_ref not in observed_set:
            errors.append(f"{label}: {field} missing required ref {required_ref}")


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            yield from _walk(nested, (*path, str(key)))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _walk(nested, (*path, str(index)))
    else:
        yield path, value


def _walk_paths(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[str, ...]]:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            nested_path = (*path, str(key))
            yield nested_path
            yield from _walk_paths(nested, nested_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            nested_path = (*path, str(index))
            yield nested_path
            yield from _walk_paths(nested, nested_path)


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", dest="examples", action="append", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run non-empty diff file summary receipt validation."""
    args = build_arg_parser().parse_args(argv)
    examples = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_non_empty_diff_file_summary_receipt(
        schema_path=args.schema,
        example_paths=examples,
    )
    write_non_empty_diff_file_summary_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS NON-EMPTY DIFF FILE SUMMARY RECEIPT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS NON-EMPTY DIFF FILE SUMMARY RECEIPT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
