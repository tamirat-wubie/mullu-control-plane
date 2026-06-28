#!/usr/bin/env python3
"""Validate Agentic Service Harness actual non-empty diff receipt binding.

Purpose: bind redacted non-empty changed-file and diff refs from filesystem-write
execution evidence into the next non-empty diff receipt step without granting
receipt append, PR, connector, mutation-route, raw-content, secret, or terminal
authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_actual_non_empty_diff_receipt_binding.schema.json,
examples/agentic_service_harness_actual_non_empty_diff_receipt_binding.foundation.json,
scripts.validate_agentic_service_harness_redacted_filesystem_write_execution_receipt,
scripts.validate_agentic_service_harness_non_empty_diff_file_summary_receipt,
and scripts.validate_schemas.
Invariants:
  - The binding copies only redacted non-empty refs from the redacted execution
    receipt.
  - The source non-empty file summary receipt remains blocked.
  - Raw diffs, raw file content, receipt append, connector calls, mutation
    routes, PR creation, secrets, and terminal closure remain denied.
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

from scripts.validate_agentic_service_harness_non_empty_diff_file_summary_receipt import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_NON_EMPTY_SUMMARY_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_NON_EMPTY_SUMMARY_SCHEMA,
    validate_agentic_service_harness_non_empty_diff_file_summary_receipt,
)
from scripts.validate_agentic_service_harness_redacted_filesystem_write_execution_receipt import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_REDACTED_EXECUTION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_REDACTED_EXECUTION_SCHEMA,
    validate_agentic_service_harness_redacted_filesystem_write_execution_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_actual_non_empty_diff_receipt_binding.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_actual_non_empty_diff_receipt_binding.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_actual_non_empty_diff_receipt_binding_validation.json"
)
EXPECTED_RECEIPT_ID = "agentic_service_harness_actual_non_empty_diff_receipt_binding"
EXPECTED_REDACTED_EXECUTION_REF = (
    "examples/agentic_service_harness_redacted_filesystem_write_execution_receipt.foundation.json"
)
EXPECTED_NON_EMPTY_SUMMARY_REF = (
    "examples/agentic_service_harness_non_empty_diff_file_summary_receipt.foundation.json"
)
EXPECTED_REPOSITORY_SLUG = "tamirat-wubie/mullu-control-plane"
EXPECTED_ACTUAL_NON_EMPTY_DIFF_REF = "witness://actual-non-empty-diff-receipt"
EXPECTED_REDACTED_OUTPUT_REF = "witness://filesystem-write-output-redacted"
EXPECTED_REDACTED_BUNDLE_REF = "digest://redacted-filesystem-write-diff-bundle-candidate"
EXPECTED_RECEIPT_APPEND_REF = "blocked://receipt-store-append/not-enabled"
EXPECTED_TERMINAL_CERTIFICATE_REF = "evidence://terminal-closure-certificate-required"
REQUIRED_BEFORE_REFS = (
    EXPECTED_REDACTED_EXECUTION_REF,
    EXPECTED_NON_EMPTY_SUMMARY_REF,
    EXPECTED_ACTUAL_NON_EMPTY_DIFF_REF,
    EXPECTED_REDACTED_OUTPUT_REF,
    EXPECTED_REDACTED_BUNDLE_REF,
    "evidence://redaction-policy-for-file-change-collection",
    "evidence://receipt-store-write-path-for-diff-collection",
    "evidence://receipt-store-write-path-for-filesystem-write",
    EXPECTED_TERMINAL_CERTIFICATE_REF,
)
REQUIRED_BLOCKERS = (
    "blocked://non-empty-file-summary/not-emitted",
    "blocked://actual-filesystem-write-receipt/not-emitted",
    EXPECTED_RECEIPT_APPEND_REF,
    "blocked://terminal-certificate/not-verified",
    "blocked://raw-diff-body/not-allowed",
    "blocked://raw-file-content/not-allowed",
    "blocked://secret-values/not-allowed",
    "blocked://mutation-route/not-enabled",
    "blocked://pull-request/not-opened",
)
REQUIRED_NEXT_REFS = (
    "witness://github-pr-admission-preflight",
    "evidence://receipt-store-write-path-for-diff-collection",
    EXPECTED_TERMINAL_CERTIFICATE_REF,
)
REQUIRED_RECEIPT_REFS = {
    "actual_non_empty_diff_receipt_binding_schema": (
        "schemas/agentic_service_harness_actual_non_empty_diff_receipt_binding.schema.json"
    ),
    "actual_non_empty_diff_receipt_binding_example": (
        "examples/agentic_service_harness_actual_non_empty_diff_receipt_binding.foundation.json"
    ),
    "redacted_filesystem_write_execution_receipt_example": EXPECTED_REDACTED_EXECUTION_REF,
    "non_empty_diff_file_summary_receipt_example": EXPECTED_NON_EMPTY_SUMMARY_REF,
    "actual_non_empty_diff_receipt_ref": EXPECTED_ACTUAL_NON_EMPTY_DIFF_REF,
    "receipt_store_append_ref": EXPECTED_RECEIPT_APPEND_REF,
    "terminal_certificate_required_ref": EXPECTED_TERMINAL_CERTIFICATE_REF,
}
REQUIRED_FALSE_FLAGS = (
    "source_non_empty_file_summary_emitted",
    "non_empty_file_summary_emitted",
    "actual_filesystem_write_receipt_emitted",
    "receipt_store_appended",
    "terminal_certificate_verified",
    "raw_diff_body_serialized",
    "raw_file_content_serialized",
    "absolute_paths_allowed",
    "parent_traversal_allowed",
    "secret_paths_allowed",
    "production_paths_allowed",
    "branch_created",
    "workspace_written",
    "files_written",
    "commands_executed",
    "tests_executed",
    "pull_request_opened",
    "runtime_state_written",
    "connector_calls_observed",
    "external_effects_observed",
    "secret_values_serialized",
    "terminal_closure",
    "success_claim_allowed",
)
REQUIRED_TRUE_FLAGS = (
    "receipt_only",
    "redacted_filesystem_write_execution_receipt_verified",
    "non_empty_diff_file_summary_receipt_verified",
    "actual_non_empty_diff_refs_bound",
    "receipt_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "secret_paths_allowed",
    "secret_values_serialized",
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
class ActualNonEmptyDiffReceiptBindingValidation:
    """Schema and semantic validation report for actual non-empty diff binding."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    redacted_execution_ref: str
    non_empty_summary_ref: str


def validate_agentic_service_harness_actual_non_empty_diff_receipt_binding(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    redacted_execution_schema_path: Path = DEFAULT_REDACTED_EXECUTION_SCHEMA,
    redacted_execution_example_paths: Sequence[Path] = DEFAULT_REDACTED_EXECUTION_EXAMPLES,
    non_empty_summary_schema_path: Path = DEFAULT_NON_EMPTY_SUMMARY_SCHEMA,
    non_empty_summary_example_paths: Sequence[Path] = DEFAULT_NON_EMPTY_SUMMARY_EXAMPLES,
    strict: bool = False,
) -> ActualNonEmptyDiffReceiptBindingValidation:
    """Validate schema structure, source receipts, and fail-closed binding rules."""

    errors: list[str] = []
    redacted_validation = validate_agentic_service_harness_redacted_filesystem_write_execution_receipt(
        schema_path=redacted_execution_schema_path,
        example_paths=redacted_execution_example_paths,
        strict=strict,
    )
    if not redacted_validation.ok:
        errors.extend(f"redacted_filesystem_write_execution_receipt: {error}" for error in redacted_validation.errors)

    summary_validation = validate_agentic_service_harness_non_empty_diff_file_summary_receipt(
        schema_path=non_empty_summary_schema_path,
        example_paths=non_empty_summary_example_paths,
    )
    if not summary_validation.ok:
        errors.extend(f"non_empty_diff_file_summary_receipt: {error}" for error in summary_validation.errors)

    redacted_execution = _load_json_object(
        redacted_execution_example_paths[0],
        "redacted filesystem write execution receipt example",
        errors,
    )
    non_empty_summary = _load_json_object(
        non_empty_summary_example_paths[0],
        "non-empty diff file summary receipt example",
        errors,
    )

    for example_path in example_paths:
        schema_errors = _validate_schema_instance(schema_path, example_path)
        errors.extend(schema_errors)
        receipt = _load_json_object(example_path, "actual non-empty diff receipt binding example", errors)
        if receipt:
            _validate_receipt_semantics(receipt, redacted_execution, non_empty_summary, errors, str(example_path))

    return ActualNonEmptyDiffReceiptBindingValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=str(schema_path),
        example_paths=tuple(str(path) for path in example_paths),
        example_count=len(example_paths),
        redacted_execution_ref=EXPECTED_REDACTED_EXECUTION_REF,
        non_empty_summary_ref=EXPECTED_NON_EMPTY_SUMMARY_REF,
    )


def write_actual_non_empty_diff_receipt_binding_validation(
    validation: ActualNonEmptyDiffReceiptBindingValidation,
    output_path: Path = DEFAULT_OUTPUT,
) -> None:
    """Write an auditable JSON validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(validation), indent=2, sort_keys=True), encoding="utf-8")


def build_mutated_receipt(**updates: Any) -> dict[str, Any]:
    """Build a mutated fixture for validator tests using __ as path separator."""

    payload = json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8"))
    for dotted_path, value in updates.items():
        path = dotted_path.split("__")
        cursor: Any = payload
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
    return payload


def _validate_receipt_semantics(
    receipt: Mapping[str, Any],
    redacted_execution: Mapping[str, Any],
    non_empty_summary: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(receipt, ("receipt_id",), EXPECTED_RECEIPT_ID, errors, label)
    _check_value(receipt, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _check_value(receipt, ("receipt_status",), "actual_non_empty_diff_refs_bound_without_receipt_append", errors, label)
    _check_value(receipt, ("source_redacted_filesystem_write_execution_receipt_ref",), EXPECTED_REDACTED_EXECUTION_REF, errors, label)
    _check_value(receipt, ("source_non_empty_diff_file_summary_receipt_ref",), EXPECTED_NON_EMPTY_SUMMARY_REF, errors, label)
    _validate_scope(receipt, redacted_execution, errors, label)
    _validate_source_receipts(receipt, redacted_execution, non_empty_summary, errors, label)
    _validate_actual_non_empty_diff_binding(receipt, redacted_execution, errors, label)
    _validate_admission_gates(receipt, errors, label)
    _validate_receipt_refs(receipt, errors, label)
    _validate_next_action(receipt, errors, label)
    _validate_flags(receipt, errors, label)
    _scan_forbidden_text(receipt, errors, label)


def _validate_scope(
    receipt: Mapping[str, Any],
    redacted_execution: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping(receipt.get("scope"))
    source_scope = _mapping(redacted_execution.get("scope"))
    for field in ("project_id", "task_id", "run_id", "sandbox_id", "repository_connection_id", "repository_slug", "mode"):
        _check_value(scope, (field,), source_scope.get(field), errors, label)
    _check_value(scope, ("repository_slug",), EXPECTED_REPOSITORY_SLUG, errors, label)
    _check_value(scope, ("foundation_phase",), "foundation_actual_non_empty_diff_receipt_binding", errors, label)


def _validate_source_receipts(
    receipt: Mapping[str, Any],
    redacted_execution: Mapping[str, Any],
    non_empty_summary: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    source = _mapping(receipt.get("source_receipts"))
    redacted_evidence = _mapping(redacted_execution.get("redacted_execution_evidence"))
    summary_gates = _mapping(non_empty_summary.get("admission_gates"))
    summary_receipt = _mapping(non_empty_summary.get("file_summary_receipt"))
    if summary_gates.get("non_empty_file_summary_emitted") is not False:
        errors.append(f"{label}: source non-empty file summary must remain blocked")
    if summary_receipt.get("changed_file_count") != 0:
        errors.append(f"{label}: source non-empty file summary changed_file_count must remain 0")
    if summary_receipt.get("changed_file_refs") != []:
        errors.append(f"{label}: source non-empty file summary changed_file_refs must remain empty")
    if summary_receipt.get("diff_refs") != []:
        errors.append(f"{label}: source non-empty file summary diff_refs must remain empty")
    _check_value(source, ("redacted_execution_changed_file_count",), redacted_evidence.get("changed_file_count"), errors, label)
    _check_value(source, ("redacted_execution_changed_file_refs",), redacted_evidence.get("changed_file_refs"), errors, label)
    _check_value(source, ("redacted_execution_diff_refs",), redacted_evidence.get("diff_refs"), errors, label)
    _check_value(source, ("redacted_execution_bundle_ref",), EXPECTED_REDACTED_BUNDLE_REF, errors, label)
    _check_value(source, ("redacted_execution_output_ref",), EXPECTED_REDACTED_OUTPUT_REF, errors, label)
    if redacted_evidence.get("changed_file_count") != 1:
        errors.append(f"{label}: redacted execution source changed_file_count must be 1")
    for field in ("redacted_execution_changed_file_refs", "redacted_execution_diff_refs"):
        refs = source.get(field)
        if not isinstance(refs, list) or not refs:
            errors.append(f"{label}: source_receipts.{field} must be non-empty")


def _validate_actual_non_empty_diff_binding(
    receipt: Mapping[str, Any],
    redacted_execution: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    binding = _mapping(receipt.get("actual_non_empty_diff_binding"))
    redacted_evidence = _mapping(redacted_execution.get("redacted_execution_evidence"))
    _check_value(binding, ("actual_non_empty_diff_receipt_ref",), EXPECTED_ACTUAL_NON_EMPTY_DIFF_REF, errors, label)
    _check_value(binding, ("changed_file_count",), redacted_evidence.get("changed_file_count"), errors, label)
    _check_value(binding, ("changed_file_refs",), redacted_evidence.get("changed_file_refs"), errors, label)
    _check_value(binding, ("diff_refs",), redacted_evidence.get("diff_refs"), errors, label)
    _check_value(binding, ("redacted_diff_bundle_ref",), EXPECTED_REDACTED_BUNDLE_REF, errors, label)
    _check_value(binding, ("redacted_output_ref",), EXPECTED_REDACTED_OUTPUT_REF, errors, label)
    _check_value(binding, ("receipt_append_ref",), EXPECTED_RECEIPT_APPEND_REF, errors, label)
    for field in ("changed_file_refs", "diff_refs"):
        refs = binding.get(field)
        if not isinstance(refs, list) or not refs:
            errors.append(f"{label}: actual_non_empty_diff_binding.{field} must be non-empty")
            continue
        for ref in refs:
            if not isinstance(ref, str) or not ref.startswith("evidence://"):
                errors.append(f"{label}: actual_non_empty_diff_binding.{field} entries must be evidence refs")


def _validate_admission_gates(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = _mapping(receipt.get("admission_gates"))
    _require_all_refs(gates.get("required_before_binding_refs"), REQUIRED_BEFORE_REFS, "admission_gates.required_before_binding_refs", errors, label)
    _require_all_refs(gates.get("blocked_reason_refs"), REQUIRED_BLOCKERS, "admission_gates.blocked_reason_refs", errors, label)
    _require_all_refs(gates.get("next_required_evidence_refs"), REQUIRED_NEXT_REFS, "admission_gates.next_required_evidence_refs", errors, label)


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
    required_phrases = (
        "GitHub PR admission",
        "actual non-empty diff receipt binding",
        "terminal certificate evidence",
    )
    for phrase in required_phrases:
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
            next_path = (*path, str(key))
            yield next_path
            yield from _walk_paths(nested, next_path)
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            yield from _walk_paths(nested, (*path, str(index)))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, action="append", dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="print JSON validation report")
    parser.add_argument("--strict", action="store_true", help="run source validators in strict mode")
    args = parser.parse_args(argv)

    example_paths = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_actual_non_empty_diff_receipt_binding(
        schema_path=args.schema,
        example_paths=example_paths,
        strict=args.strict,
    )
    write_actual_non_empty_diff_receipt_binding_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(asdict(validation), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS ACTUAL NON-EMPTY DIFF RECEIPT BINDING VALID")
    else:
        print("AGENTIC SERVICE HARNESS ACTUAL NON-EMPTY DIFF RECEIPT BINDING INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
