#!/usr/bin/env python3
"""Validate Agentic Service Harness redacted filesystem write execution receipt.

Purpose: prove redacted actual filesystem-write execution evidence can be
referenced without granting runtime write, receipt append, or PR authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_redacted_filesystem_write_execution_receipt.schema.json,
examples/agentic_service_harness_redacted_filesystem_write_execution_receipt.foundation.json,
scripts.validate_agentic_service_harness_actual_filesystem_write_receipt_admission,
and scripts.validate_schemas.
Invariants:
  - The receipt binds the prior actual filesystem-write admission and concrete
    candidate refs.
  - Changed-file, diff, and output evidence are redacted refs only.
  - Live writes, receipt append, raw outputs, PR creation, connector calls,
    mutation routes, secrets, and terminal closure remain denied.
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

from scripts.validate_agentic_service_harness_actual_filesystem_write_receipt_admission import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_ACTUAL_ADMISSION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_ACTUAL_ADMISSION_SCHEMA,
    validate_agentic_service_harness_actual_filesystem_write_receipt_admission,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_redacted_filesystem_write_execution_receipt.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_redacted_filesystem_write_execution_receipt.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_redacted_filesystem_write_execution_receipt_validation.json"
)
EXPECTED_RECEIPT_ID = "agentic_service_harness_redacted_filesystem_write_execution_receipt"
EXPECTED_ACTUAL_ADMISSION_REF = (
    "examples/agentic_service_harness_actual_filesystem_write_receipt_admission.foundation.json"
)
EXPECTED_CONCRETE_CANDIDATE_REF = (
    "examples/agentic_service_harness_concrete_filesystem_write_evidence_candidate.foundation.json"
)
EXPECTED_REPOSITORY_SLUG = "tamirat-wubie/mullu-control-plane"
EXPECTED_REDACTED_OUTPUT_REF = "witness://filesystem-write-output-redacted"
EXPECTED_ACTUAL_EXECUTION_REF = "witness://actual-filesystem-write-execution"
EXPECTED_REDACTED_BUNDLE_REF = "digest://redacted-filesystem-write-diff-bundle-candidate"
EXPECTED_RECEIPT_STORE_WRITE_PATH_REF = "evidence://receipt-store-write-path-for-filesystem-write"
EXPECTED_TERMINAL_CERTIFICATE_REF = "evidence://terminal-closure-certificate-required"
REQUIRED_BEFORE_REFS = (
    EXPECTED_ACTUAL_ADMISSION_REF,
    EXPECTED_CONCRETE_CANDIDATE_REF,
    "approval://operator/filesystem-write-execution",
    "evidence://branch-write-authority-binding",
    "evidence://workspace-write-authority",
    "evidence://cleanup-receipt-after-workspace-use",
    "evidence://filesystem-write-rollback-plan",
    "evidence://redaction-policy-for-file-change-collection",
    "evidence://uao-filesystem-write-admission",
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    EXPECTED_REDACTED_OUTPUT_REF,
    EXPECTED_REDACTED_BUNDLE_REF,
    EXPECTED_TERMINAL_CERTIFICATE_REF,
)
REQUIRED_BLOCKERS = (
    "blocked://live-filesystem-write/not-executed",
    "blocked://actual-filesystem-write-receipt/not-emitted",
    "blocked://receipt-store-write-path/not-verified",
    "blocked://receipt-store-append/not-enabled",
    "blocked://terminal-certificate/not-verified",
    "blocked://raw-command-output/not-allowed",
    "blocked://raw-diff-body/not-allowed",
    "blocked://raw-file-content/not-allowed",
    "blocked://secret-values/not-allowed",
    "blocked://mutation-route/not-enabled",
    "blocked://pull-request/not-opened",
)
REQUIRED_NEXT_REFS = (
    "witness://actual-filesystem-write-receipt",
    "witness://actual-non-empty-diff-receipt",
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    EXPECTED_TERMINAL_CERTIFICATE_REF,
)
REQUIRED_RECEIPT_REFS = {
    "redacted_filesystem_write_execution_receipt_schema": (
        "schemas/agentic_service_harness_redacted_filesystem_write_execution_receipt.schema.json"
    ),
    "redacted_filesystem_write_execution_receipt_example": (
        "examples/agentic_service_harness_redacted_filesystem_write_execution_receipt.foundation.json"
    ),
    "actual_filesystem_write_receipt_admission_example": EXPECTED_ACTUAL_ADMISSION_REF,
    "concrete_filesystem_write_evidence_candidate_example": EXPECTED_CONCRETE_CANDIDATE_REF,
    "redacted_output_ref": EXPECTED_REDACTED_OUTPUT_REF,
    "redacted_diff_bundle_ref": EXPECTED_REDACTED_BUNDLE_REF,
    "receipt_store_write_path_ref": EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "terminal_certificate_required_ref": EXPECTED_TERMINAL_CERTIFICATE_REF,
}
REQUIRED_FALSE_FLAGS = (
    "source_receipt_admission_allowed",
    "source_filesystem_write_executed",
    "source_receipt_store_appended",
    "raw_command_output_serialized",
    "raw_diff_body_serialized",
    "raw_file_content_serialized",
    "absolute_paths_allowed",
    "parent_traversal_allowed",
    "secret_paths_allowed",
    "production_paths_allowed",
    "filesystem_write_executed",
    "filesystem_write_receipt_emitted",
    "receipt_store_appended",
    "terminal_certificate_verified",
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
    "redacted_execution_evidence_collected",
    "actual_filesystem_write_receipt_admission_verified",
    "concrete_candidate_verified",
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
class RedactedFilesystemWriteExecutionReceiptValidation:
    """Schema and semantic validation report for redacted execution evidence."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    actual_admission_ref: str


def validate_agentic_service_harness_redacted_filesystem_write_execution_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    actual_admission_schema_path: Path = DEFAULT_ACTUAL_ADMISSION_SCHEMA,
    actual_admission_example_paths: Sequence[Path] = DEFAULT_ACTUAL_ADMISSION_EXAMPLES,
    strict: bool = False,
) -> RedactedFilesystemWriteExecutionReceiptValidation:
    """Validate schema structure, source admission, and semantic fail-closed rules."""

    errors: list[str] = []
    actual_admission_validation = validate_agentic_service_harness_actual_filesystem_write_receipt_admission(
        schema_path=actual_admission_schema_path,
        example_paths=actual_admission_example_paths,
    )
    if not actual_admission_validation.ok:
        errors.extend(
            f"actual_filesystem_write_receipt_admission: {error}"
            for error in actual_admission_validation.errors
        )

    actual_admission = _load_json_object(
        actual_admission_example_paths[0],
        "actual filesystem write receipt admission example",
        errors,
    )

    for example_path in example_paths:
        schema_errors = _validate_schema_instance(schema_path, example_path)
        errors.extend(schema_errors)
        receipt = _load_json_object(example_path, "redacted filesystem write execution receipt example", errors)
        if receipt:
            _validate_receipt_semantics(receipt, actual_admission, errors, str(example_path))

    return RedactedFilesystemWriteExecutionReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=str(schema_path),
        example_paths=tuple(str(path) for path in example_paths),
        example_count=len(example_paths),
        actual_admission_ref=EXPECTED_ACTUAL_ADMISSION_REF,
    )


def write_redacted_filesystem_write_execution_receipt_validation(
    validation: RedactedFilesystemWriteExecutionReceiptValidation,
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
    actual_admission: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(receipt, ("receipt_id",), EXPECTED_RECEIPT_ID, errors, label)
    _check_value(receipt, ("source_actual_filesystem_write_receipt_admission_ref",), EXPECTED_ACTUAL_ADMISSION_REF, errors, label)
    _check_value(receipt, ("source_concrete_filesystem_write_evidence_candidate_ref",), EXPECTED_CONCRETE_CANDIDATE_REF, errors, label)
    _validate_scope(receipt, errors, label)
    _validate_source_admission(receipt, actual_admission, errors, label)
    _validate_redacted_execution_evidence(receipt, actual_admission, errors, label)
    _validate_admission_gates(receipt, errors, label)
    _validate_receipt_refs(receipt, errors, label)
    _validate_next_action(receipt, errors, label)
    _validate_flags(receipt, errors, label)
    _scan_forbidden_text(receipt, errors, label)


def _validate_scope(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(receipt.get("scope"))
    _check_value(scope, ("repository_slug",), EXPECTED_REPOSITORY_SLUG, errors, label)
    _check_value(scope, ("foundation_phase",), "foundation_redacted_filesystem_write_execution_receipt", errors, label)


def _validate_source_admission(
    receipt: Mapping[str, Any],
    actual_admission: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    source = _mapping(receipt.get("source_admission"))
    admission_contract = _mapping(actual_admission.get("filesystem_write_receipt_contract"))
    admission_gates = _mapping(actual_admission.get("admission_gates"))
    effect_boundary = _mapping(actual_admission.get("effect_boundary"))
    _check_value(source, ("candidate_changed_file_count",), admission_contract.get("candidate_changed_file_count"), errors, label)
    _check_value(source, ("changed_file_refs",), admission_contract.get("changed_file_refs"), errors, label)
    _check_value(source, ("diff_refs",), admission_contract.get("diff_refs"), errors, label)
    _check_value(source, ("redacted_diff_bundle_ref",), EXPECTED_REDACTED_BUNDLE_REF, errors, label)
    if admission_gates.get("filesystem_write_receipt_admission_allowed") is not False:
        errors.append(f"{label}: source admission must not allow filesystem write receipt admission")
    if admission_gates.get("filesystem_write_executed") is not False:
        errors.append(f"{label}: source admission must not execute filesystem writes")
    if effect_boundary.get("receipt_store_appended") is not False:
        errors.append(f"{label}: source admission must not append receipt store")


def _validate_redacted_execution_evidence(
    receipt: Mapping[str, Any],
    actual_admission: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    evidence = _mapping(receipt.get("redacted_execution_evidence"))
    admission_contract = _mapping(actual_admission.get("filesystem_write_receipt_contract"))
    _check_value(evidence, ("actual_execution_ref",), EXPECTED_ACTUAL_EXECUTION_REF, errors, label)
    _check_value(evidence, ("redacted_output_ref",), EXPECTED_REDACTED_OUTPUT_REF, errors, label)
    _check_value(evidence, ("changed_file_count",), admission_contract.get("candidate_changed_file_count"), errors, label)
    _check_value(evidence, ("changed_file_refs",), admission_contract.get("changed_file_refs"), errors, label)
    _check_value(evidence, ("diff_refs",), admission_contract.get("diff_refs"), errors, label)
    _check_value(evidence, ("redacted_diff_bundle_ref",), EXPECTED_REDACTED_BUNDLE_REF, errors, label)
    for field in ("changed_file_refs", "diff_refs"):
        refs = evidence.get(field)
        if not isinstance(refs, list) or not refs:
            errors.append(f"{label}: redacted_execution_evidence.{field} must be non-empty")
            continue
        for ref in refs:
            if not isinstance(ref, str) or not ref.startswith("evidence://"):
                errors.append(f"{label}: redacted_execution_evidence.{field} entries must be evidence refs")


def _validate_admission_gates(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = _mapping(receipt.get("admission_gates"))
    _require_all_refs(gates.get("required_before_execution_receipt_refs"), REQUIRED_BEFORE_REFS, "admission_gates.required_before_execution_receipt_refs", errors, label)
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
        "redacted filesystem-write execution evidence",
        "actual non-empty diff receipt",
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
    validation = validate_agentic_service_harness_redacted_filesystem_write_execution_receipt(
        schema_path=args.schema,
        example_paths=example_paths,
        strict=args.strict,
    )
    write_redacted_filesystem_write_execution_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(asdict(validation), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS REDACTED FILESYSTEM WRITE EXECUTION RECEIPT VALID")
    else:
        print("AGENTIC SERVICE HARNESS REDACTED FILESYSTEM WRITE EXECUTION RECEIPT INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
