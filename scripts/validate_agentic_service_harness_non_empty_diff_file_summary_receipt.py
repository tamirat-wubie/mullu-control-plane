#!/usr/bin/env python3
"""Validate Agentic Service Harness non-empty diff file summary receipt.

Purpose: prove future non-empty diff file summaries remain blocked until
filesystem-write evidence, cleanup, redaction, UAO admission, and receipt-store
evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_non_empty_diff_file_summary_receipt.schema.json,
examples/agentic_service_harness_non_empty_diff_file_summary_receipt.foundation.json,
scripts.validate_agentic_service_harness_non_empty_diff_receipt_admission_preflight,
scripts.validate_agentic_service_harness_filesystem_write_admission_preflight,
scripts.validate_agentic_service_harness_actual_diff_collection_receipt, and
scripts.validate_schemas.
Invariants:
  - The receipt binds to non-empty diff admission, filesystem-write admission,
    and the zero-diff actual diff collection receipt.
  - Changed-file refs and diff refs remain empty while filesystem-write evidence
    is absent.
  - Raw diffs, raw file content, receipt append, mutation routes, PR creation,
    secrets, and terminal closure remain denied.
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
    DEFAULT_EXAMPLES as DEFAULT_ZERO_DIFF_RECEIPT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_ZERO_DIFF_RECEIPT_SCHEMA,
    validate_agentic_service_harness_actual_diff_collection_receipt,
)
from scripts.validate_agentic_service_harness_filesystem_write_admission_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_FILESYSTEM_WRITE_ADMISSION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_FILESYSTEM_WRITE_ADMISSION_SCHEMA,
    validate_agentic_service_harness_filesystem_write_admission_preflight,
)
from scripts.validate_agentic_service_harness_non_empty_diff_receipt_admission_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_NON_EMPTY_DIFF_ADMISSION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_NON_EMPTY_DIFF_ADMISSION_SCHEMA,
    validate_agentic_service_harness_non_empty_diff_receipt_admission_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_non_empty_diff_file_summary_receipt.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_non_empty_diff_file_summary_receipt.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_non_empty_diff_file_summary_receipt_validation.json"
)
EXPECTED_RECEIPT_ID = "agentic_service_harness_non_empty_diff_file_summary_receipt"
EXPECTED_NON_EMPTY_DIFF_ADMISSION_REF = (
    "examples/agentic_service_harness_non_empty_diff_receipt_admission_preflight.foundation.json"
)
EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF = (
    "examples/agentic_service_harness_filesystem_write_admission_preflight.foundation.json"
)
EXPECTED_ZERO_DIFF_RECEIPT_REF = (
    "examples/agentic_service_harness_actual_diff_collection_receipt.foundation.json"
)
EXPECTED_REPOSITORY_SLUG = "tamirat-wubie/mullu-control-plane"
EXPECTED_REDACTION_REF = "evidence://redaction-policy-for-file-change-collection"
EXPECTED_RECEIPT_STORE_WRITE_PATH_REF = "evidence://receipt-store-write-path-for-diff-collection"
EXPECTED_CLEANUP_RECEIPT_REF = "receipt://sandbox-cleanup-branchwrite"
EXPECTED_UAO_REF = "evidence://uao-non-empty-diff-file-summary"
REQUIRED_BEFORE_REFS = (
    "approval://operator/non-empty-diff-file-summary",
    EXPECTED_NON_EMPTY_DIFF_ADMISSION_REF,
    EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF,
    EXPECTED_ZERO_DIFF_RECEIPT_REF,
    "evidence://branch-write-authority-binding",
    "evidence://workspace-write-authority",
    EXPECTED_CLEANUP_RECEIPT_REF,
    EXPECTED_REDACTION_REF,
    EXPECTED_UAO_REF,
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "witness://no-secret-paths-in-diff",
    "witness://filesystem-write-output-redacted",
    "witness://diff-output-redacted",
    "digest://redacted-diff-bundle",
)
REQUIRED_BLOCKERS = (
    "blocked://filesystem-write-evidence/not-collected",
    "blocked://operator-approval/not-collected",
    "blocked://branch-write-authority/not-verified",
    "blocked://workspace-write-authority/not-verified",
    "blocked://cleanup-receipt/not-verified",
    "blocked://redaction-evidence/not-verified",
    "blocked://uao-non-empty-diff-file-summary/not-verified",
    "blocked://receipt-store-write-path/not-verified",
    "blocked://raw-diff-body/not-allowed",
    "blocked://raw-file-content/not-allowed",
    "blocked://secret-paths/not-allowed",
)
REQUIRED_NEXT_REFS = (
    "witness://github-pr-admission-preflight",
    "evidence://branch-write-authority-binding",
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "witness://diff-output-redacted",
    "witness://filesystem-write-output-redacted",
)
REQUIRED_RECEIPT_REFS = {
    "non_empty_diff_file_summary_receipt_schema": (
        "schemas/agentic_service_harness_non_empty_diff_file_summary_receipt.schema.json"
    ),
    "non_empty_diff_receipt_admission_preflight_example": EXPECTED_NON_EMPTY_DIFF_ADMISSION_REF,
    "filesystem_write_admission_preflight_example": EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF,
    "actual_diff_collection_receipt_example": EXPECTED_ZERO_DIFF_RECEIPT_REF,
    "receipt_store_write_path_ref": EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "cleanup_receipt_ref": EXPECTED_CLEANUP_RECEIPT_REF,
    "uao_non_empty_diff_file_summary_ref": EXPECTED_UAO_REF,
}
REQUIRED_FALSE_FLAGS = (
    "non_empty_file_summary_emitted",
    "filesystem_write_evidence_collected",
    "branch_write_authority_verified",
    "workspace_write_authority_verified",
    "operator_approval_collected",
    "cleanup_receipt_verified",
    "redaction_evidence_verified",
    "uao_non_empty_diff_file_summary_verified",
    "receipt_store_write_path_verified",
    "raw_diff_body_serialized",
    "raw_file_content_serialized",
    "absolute_paths_allowed",
    "parent_traversal_allowed",
    "secret_paths_allowed",
    "production_paths_allowed",
    "branch_write_enabled",
    "workspace_write_enabled",
    "raw_diff_body_stored",
    "raw_file_content_stored",
    "receipt_store_append_enabled",
    "runtime_state_write_enabled",
    "connector_calls_enabled",
    "mutation_route_enabled",
    "pr_creation_enabled",
    "secret_values_serialized",
    "terminal_closure",
    "raw_secret_value_storage_allowed",
    "raw_output_storage_allowed",
)
REQUIRED_TRUE_FLAGS = (
    "non_empty_diff_admission_verified",
    "filesystem_write_admission_preflight_verified",
    "zero_diff_receipt_verified",
    "secret_redaction_required",
    "diff_redaction_required",
    "receipt_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "secret_paths_allowed",
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
    """Schema and semantic validation report for non-empty diff file summary."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    non_empty_diff_admission_ref: str
    filesystem_write_admission_ref: str
    zero_diff_receipt_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_non_empty_diff_file_summary_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    non_empty_diff_admission_schema_path: Path = DEFAULT_NON_EMPTY_DIFF_ADMISSION_SCHEMA,
    non_empty_diff_admission_example_paths: Sequence[Path] = DEFAULT_NON_EMPTY_DIFF_ADMISSION_EXAMPLES,
    filesystem_write_admission_schema_path: Path = DEFAULT_FILESYSTEM_WRITE_ADMISSION_SCHEMA,
    filesystem_write_admission_example_paths: Sequence[Path] = DEFAULT_FILESYSTEM_WRITE_ADMISSION_EXAMPLES,
    zero_diff_receipt_schema_path: Path = DEFAULT_ZERO_DIFF_RECEIPT_SCHEMA,
    zero_diff_receipt_example_paths: Sequence[Path] = DEFAULT_ZERO_DIFF_RECEIPT_EXAMPLES,
) -> NonEmptyDiffFileSummaryReceiptValidation:
    """Validate non-empty diff file summary receipt examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "non-empty diff file summary schema", errors)
    non_empty_validation = validate_agentic_service_harness_non_empty_diff_receipt_admission_preflight(
        schema_path=non_empty_diff_admission_schema_path,
        example_paths=non_empty_diff_admission_example_paths,
    )
    if not non_empty_validation.ok:
        errors.extend(f"non-empty diff admission preflight: {error}" for error in non_empty_validation.errors)
    filesystem_validation = validate_agentic_service_harness_filesystem_write_admission_preflight(
        schema_path=filesystem_write_admission_schema_path,
        example_paths=filesystem_write_admission_example_paths,
    )
    if not filesystem_validation.ok:
        errors.extend(f"filesystem write admission preflight: {error}" for error in filesystem_validation.errors)
    zero_diff_validation = validate_agentic_service_harness_actual_diff_collection_receipt(
        schema_path=zero_diff_receipt_schema_path,
        example_paths=zero_diff_receipt_example_paths,
    )
    if not zero_diff_validation.ok:
        errors.extend(f"zero-diff receipt: {error}" for error in zero_diff_validation.errors)
    non_empty_preflight = _load_json_object(
        non_empty_diff_admission_example_paths[0],
        "non-empty diff admission preflight source",
        errors,
    )
    filesystem_preflight = _load_json_object(
        filesystem_write_admission_example_paths[0],
        "filesystem write admission preflight source",
        errors,
    )
    zero_diff_receipt = _load_json_object(
        zero_diff_receipt_example_paths[0],
        "zero-diff actual diff collection receipt source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"non-empty diff file summary example {_path_label(example_path)}",
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
        _validate_receipt_semantics(
            example,
            non_empty_preflight,
            filesystem_preflight,
            zero_diff_receipt,
            errors,
            _path_label(example_path),
        )
    return NonEmptyDiffFileSummaryReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        non_empty_diff_admission_ref=EXPECTED_NON_EMPTY_DIFF_ADMISSION_REF,
        filesystem_write_admission_ref=EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF,
        zero_diff_receipt_ref=EXPECTED_ZERO_DIFF_RECEIPT_REF,
    )


def write_non_empty_diff_file_summary_receipt_validation(
    validation: NonEmptyDiffFileSummaryReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic non-empty diff file summary validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_receipt(**updates: Any) -> dict[str, Any]:
    """Return the default example with nested updates for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default non-empty diff file summary example", [])
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


def _validate_receipt_semantics(
    receipt: Mapping[str, Any],
    non_empty_preflight: Mapping[str, Any],
    filesystem_preflight: Mapping[str, Any],
    zero_diff_receipt: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(receipt, ("receipt_id",), EXPECTED_RECEIPT_ID, errors, label)
    _check_value(receipt, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _check_value(
        receipt,
        ("receipt_status",),
        "blocked_until_filesystem_write_cleanup_redaction_uao_and_receipt_store",
        errors,
        label,
    )
    _check_value(
        receipt,
        ("source_non_empty_diff_receipt_admission_preflight_ref",),
        EXPECTED_NON_EMPTY_DIFF_ADMISSION_REF,
        errors,
        label,
    )
    _check_value(
        receipt,
        ("source_filesystem_write_admission_preflight_ref",),
        EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF,
        errors,
        label,
    )
    _check_value(
        receipt,
        ("source_actual_diff_collection_receipt_ref",),
        EXPECTED_ZERO_DIFF_RECEIPT_REF,
        errors,
        label,
    )
    _validate_scope(receipt, non_empty_preflight, errors, label)
    _validate_source_receipts(receipt, non_empty_preflight, filesystem_preflight, zero_diff_receipt, errors, label)
    _validate_admission_gates(receipt, filesystem_preflight, errors, label)
    _validate_file_summary_receipt(receipt, errors, label)
    _validate_receipt_refs(receipt, errors, label)
    _validate_next_action(receipt, errors, label)
    _validate_flags(receipt, errors, label)
    _scan_forbidden_text(receipt, errors, label)


def _validate_scope(
    receipt: Mapping[str, Any],
    non_empty_preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping(receipt.get("scope"))
    source_scope = _mapping(non_empty_preflight.get("scope"))
    for field in ("project_id", "task_id", "run_id", "sandbox_id", "repository_connection_id", "repository_slug", "mode"):
        _check_value(scope, (field,), source_scope.get(field), errors, label)
    _check_value(scope, ("repository_slug",), EXPECTED_REPOSITORY_SLUG, errors, label)
    _check_value(scope, ("foundation_phase",), "foundation_non_empty_diff_file_summary_receipt", errors, label)


def _validate_source_receipts(
    receipt: Mapping[str, Any],
    non_empty_preflight: Mapping[str, Any],
    filesystem_preflight: Mapping[str, Any],
    zero_diff_receipt: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    source_receipts = _mapping(receipt.get("source_receipts"))
    _check_value(
        source_receipts,
        ("non_empty_diff_receipt_admission_preflight_ref",),
        EXPECTED_NON_EMPTY_DIFF_ADMISSION_REF,
        errors,
        label,
    )
    _check_value(
        source_receipts,
        ("filesystem_write_admission_preflight_ref",),
        EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF,
        errors,
        label,
    )
    _check_value(
        source_receipts,
        ("actual_diff_collection_receipt_ref",),
        EXPECTED_ZERO_DIFF_RECEIPT_REF,
        errors,
        label,
    )
    if non_empty_preflight.get("admission_status") != "AwaitingEvidence":
        errors.append(f"{label}: non-empty diff admission preflight must remain AwaitingEvidence")
    if filesystem_preflight.get("admission_status") != "AwaitingEvidence":
        errors.append(f"{label}: filesystem write admission preflight must remain AwaitingEvidence")
    non_empty_gates = _mapping(non_empty_preflight.get("admission_gates"))
    filesystem_gates = _mapping(filesystem_preflight.get("admission_gates"))
    if non_empty_gates.get("non_empty_diff_receipt_admitted") is not False:
        errors.append(f"{label}: source non-empty diff preflight must not admit non-empty diff receipt")
    if filesystem_gates.get("filesystem_write_admitted") is not False:
        errors.append(f"{label}: source filesystem preflight must not admit filesystem writes")
    diff_receipt = _mapping(zero_diff_receipt.get("diff_collection_receipt"))
    if diff_receipt.get("changed_file_count") != 0:
        errors.append(f"{label}: zero-diff source changed_file_count must be 0")
    if diff_receipt.get("changed_file_refs") != []:
        errors.append(f"{label}: zero-diff source changed_file_refs must be empty")
    if diff_receipt.get("diff_refs") != []:
        errors.append(f"{label}: zero-diff source diff_refs must be empty")
    if source_receipts.get("source_changed_file_count") != 0:
        errors.append(f"{label}: source_receipts.source_changed_file_count must be 0")
    if source_receipts.get("source_changed_file_refs") != []:
        errors.append(f"{label}: source_receipts.source_changed_file_refs must be empty")
    if source_receipts.get("source_diff_refs") != []:
        errors.append(f"{label}: source_receipts.source_diff_refs must be empty")


def _validate_admission_gates(
    receipt: Mapping[str, Any],
    filesystem_preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    gates = _mapping(receipt.get("admission_gates"))
    filesystem_contract = _mapping(filesystem_preflight.get("filesystem_write_contract"))
    if filesystem_contract.get("changed_file_refs") != []:
        errors.append(f"{label}: source filesystem preflight changed_file_refs must be empty")
    if filesystem_contract.get("diff_refs") != []:
        errors.append(f"{label}: source filesystem preflight diff_refs must be empty")
    if filesystem_contract.get("raw_diff_body_serialized") is not False:
        errors.append(f"{label}: source filesystem preflight must not serialize raw diffs")
    if filesystem_contract.get("raw_file_content_serialized") is not False:
        errors.append(f"{label}: source filesystem preflight must not serialize raw file content")
    _require_all_refs(
        gates.get("required_before_file_summary_refs"),
        REQUIRED_BEFORE_REFS,
        "admission_gates.required_before_file_summary_refs",
        errors,
        label,
    )
    _require_all_refs(
        gates.get("blocked_reason_refs"),
        REQUIRED_BLOCKERS,
        "admission_gates.blocked_reason_refs",
        errors,
        label,
    )
    _require_all_refs(
        gates.get("next_required_evidence_refs"),
        REQUIRED_NEXT_REFS,
        "admission_gates.next_required_evidence_refs",
        errors,
        label,
    )


def _validate_file_summary_receipt(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    summary = _mapping(receipt.get("file_summary_receipt"))
    if summary.get("changed_file_count") != 0:
        errors.append(f"{label}: file_summary_receipt.changed_file_count must be 0")
    if summary.get("changed_file_refs") != []:
        errors.append(f"{label}: file_summary_receipt.changed_file_refs must be empty")
    if summary.get("diff_refs") != []:
        errors.append(f"{label}: file_summary_receipt.diff_refs must be empty")
    if summary.get("redacted_diff_bundle_ref") != "diff-bundle://not-collected":
        errors.append(f"{label}: file_summary_receipt.redacted_diff_bundle_ref must remain not-collected")
    if summary.get("raw_diff_body_serialized") is not False:
        errors.append(f"{label}: file_summary_receipt.raw_diff_body_serialized must be false")
    if summary.get("raw_file_content_serialized") is not False:
        errors.append(f"{label}: file_summary_receipt.raw_file_content_serialized must be false")
    if summary.get("receipt_append_ref") != "blocked://receipt-store-write-path/not-verified":
        errors.append(f"{label}: file_summary_receipt.receipt_append_ref must remain blocked")


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
    required_phrases = ("GitHub PR admission", "non-empty diff/file summary receipt", "terminal closure blocked")
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


def _check_value(
    payload: Mapping[str, Any],
    path: tuple[str, ...],
    expected: Any,
    errors: list[str],
    label: str,
) -> None:
    cursor: Any = payload
    for part in path:
        if not isinstance(cursor, Mapping) or part not in cursor:
            errors.append(f"{label}: missing {'.'.join(path)}")
            return
        cursor = cursor[part]
    if cursor != expected:
        errors.append(f"{label}: {'.'.join(path)} must be {expected}")


def _require_all_refs(
    observed: Any,
    required: Iterable[str],
    field: str,
    errors: list[str],
    label: str,
) -> None:
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
