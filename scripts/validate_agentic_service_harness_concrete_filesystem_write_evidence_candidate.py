#!/usr/bin/env python3
"""Validate Agentic Service Harness concrete filesystem write evidence candidate.

Purpose: prove a non-empty redacted filesystem-write evidence candidate can be
represented without admitting live filesystem writes or serializing raw content.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_concrete_filesystem_write_evidence_candidate.schema.json,
examples/agentic_service_harness_concrete_filesystem_write_evidence_candidate.foundation.json,
scripts.validate_agentic_service_harness_filesystem_write_admission_preflight,
scripts.validate_agentic_service_harness_non_empty_diff_file_summary_receipt,
and scripts.validate_schemas.
Invariants:
  - The candidate binds to blocked source write and file-summary surfaces.
  - Candidate changed-file and diff refs are non-empty evidence refs only.
  - Raw diffs, raw file content, receipt append, PR creation, mutation routes,
    secrets, live writes, and terminal closure remain denied.
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

from scripts.validate_agentic_service_harness_filesystem_write_admission_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_FILESYSTEM_WRITE_ADMISSION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_FILESYSTEM_WRITE_ADMISSION_SCHEMA,
    validate_agentic_service_harness_filesystem_write_admission_preflight,
)
from scripts.validate_agentic_service_harness_non_empty_diff_file_summary_receipt import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_NON_EMPTY_DIFF_FILE_SUMMARY_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_NON_EMPTY_DIFF_FILE_SUMMARY_SCHEMA,
    validate_agentic_service_harness_non_empty_diff_file_summary_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_concrete_filesystem_write_evidence_candidate.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_concrete_filesystem_write_evidence_candidate.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_concrete_filesystem_write_evidence_candidate_validation.json"
)
EXPECTED_RECEIPT_ID = "agentic_service_harness_concrete_filesystem_write_evidence_candidate"
EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF = (
    "examples/agentic_service_harness_filesystem_write_admission_preflight.foundation.json"
)
EXPECTED_NON_EMPTY_DIFF_FILE_SUMMARY_REF = (
    "examples/agentic_service_harness_non_empty_diff_file_summary_receipt.foundation.json"
)
EXPECTED_REPOSITORY_SLUG = "tamirat-wubie/mullu-control-plane"
EXPECTED_REDACTION_REF = "evidence://redaction-policy-for-file-change-collection"
EXPECTED_CLEANUP_RECEIPT_REF = "evidence://cleanup-receipt-after-workspace-use"
EXPECTED_ROLLBACK_PLAN_REF = "evidence://filesystem-write-rollback-plan"
EXPECTED_UAO_REF = "evidence://uao-filesystem-write-admission"
EXPECTED_RECEIPT_STORE_WRITE_PATH_REF = "evidence://receipt-store-write-path-for-filesystem-write"
EXPECTED_REDACTED_BUNDLE_REF = "digest://redacted-filesystem-write-diff-bundle-candidate"
EXPECTED_RECEIPT_APPEND_REF = "blocked://receipt-store-write-path/not-verified"
REQUIRED_BEFORE_REFS = (
    "approval://operator/filesystem-write-execution",
    "evidence://branch-write-authority-binding",
    "evidence://workspace-write-authority",
    EXPECTED_CLEANUP_RECEIPT_REF,
    EXPECTED_REDACTION_REF,
    EXPECTED_UAO_REF,
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    EXPECTED_ROLLBACK_PLAN_REF,
    "witness://filesystem-write-output-redacted",
    EXPECTED_REDACTED_BUNDLE_REF,
)
REQUIRED_BLOCKERS = (
    "blocked://live-filesystem-write/not-executed",
    "blocked://operator-approval/not-collected",
    "blocked://branch-write-authority/not-verified",
    "blocked://workspace-write-authority/not-verified",
    "blocked://cleanup-receipt/not-verified",
    "blocked://redaction-evidence/not-verified",
    "blocked://uao-filesystem-write/not-verified",
    "blocked://receipt-store-write-path/not-verified",
    "blocked://raw-diff-body/not-allowed",
    "blocked://raw-file-content/not-allowed",
)
REQUIRED_NEXT_REFS = (
    "witness://actual-filesystem-write-receipt",
    "witness://actual-non-empty-diff-receipt",
    "witness://filesystem-write-output-redacted",
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "evidence://terminal-closure-certificate-required",
)
REQUIRED_RECEIPT_REFS = {
    "concrete_filesystem_write_evidence_candidate_schema": (
        "schemas/agentic_service_harness_concrete_filesystem_write_evidence_candidate.schema.json"
    ),
    "filesystem_write_admission_preflight_example": EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF,
    "non_empty_diff_file_summary_receipt_example": EXPECTED_NON_EMPTY_DIFF_FILE_SUMMARY_REF,
    "redacted_diff_bundle_ref": EXPECTED_REDACTED_BUNDLE_REF,
    "cleanup_receipt_ref": EXPECTED_CLEANUP_RECEIPT_REF,
    "rollback_plan_ref": EXPECTED_ROLLBACK_PLAN_REF,
    "receipt_store_write_path_ref": EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
    "uao_filesystem_write_ref": EXPECTED_UAO_REF,
}
REQUIRED_FALSE_FLAGS = (
    "source_filesystem_write_admitted",
    "source_non_empty_file_summary_emitted",
    "filesystem_write_executed",
    "branch_write_authority_verified",
    "workspace_write_authority_verified",
    "operator_approval_collected",
    "cleanup_receipt_verified",
    "redaction_evidence_verified",
    "uao_filesystem_write_verified",
    "receipt_store_write_path_verified",
    "raw_diff_body_serialized",
    "raw_file_content_serialized",
    "absolute_paths_allowed",
    "parent_traversal_allowed",
    "secret_paths_allowed",
    "production_paths_allowed",
    "branch_write_enabled",
    "workspace_write_enabled",
    "filesystem_write_enabled",
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
    "filesystem_write_admission_preflight_verified",
    "non_empty_diff_file_summary_receipt_verified",
    "filesystem_write_evidence_candidate_recorded",
    "non_empty_diff_candidate_present",
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
class ConcreteFilesystemWriteEvidenceCandidateValidation:
    """Schema and semantic validation report for write evidence candidates."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    filesystem_write_admission_ref: str
    non_empty_diff_file_summary_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_concrete_filesystem_write_evidence_candidate(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    filesystem_write_admission_schema_path: Path = DEFAULT_FILESYSTEM_WRITE_ADMISSION_SCHEMA,
    filesystem_write_admission_example_paths: Sequence[Path] = DEFAULT_FILESYSTEM_WRITE_ADMISSION_EXAMPLES,
    non_empty_diff_file_summary_schema_path: Path = DEFAULT_NON_EMPTY_DIFF_FILE_SUMMARY_SCHEMA,
    non_empty_diff_file_summary_example_paths: Sequence[Path] = DEFAULT_NON_EMPTY_DIFF_FILE_SUMMARY_EXAMPLES,
) -> ConcreteFilesystemWriteEvidenceCandidateValidation:
    """Validate concrete filesystem write evidence candidate examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "concrete filesystem write candidate schema", errors)
    filesystem_validation = validate_agentic_service_harness_filesystem_write_admission_preflight(
        schema_path=filesystem_write_admission_schema_path,
        example_paths=filesystem_write_admission_example_paths,
    )
    if not filesystem_validation.ok:
        errors.extend(f"filesystem write admission preflight: {error}" for error in filesystem_validation.errors)
    summary_validation = validate_agentic_service_harness_non_empty_diff_file_summary_receipt(
        schema_path=non_empty_diff_file_summary_schema_path,
        example_paths=non_empty_diff_file_summary_example_paths,
    )
    if not summary_validation.ok:
        errors.extend(f"non-empty diff file summary receipt: {error}" for error in summary_validation.errors)
    filesystem_preflight = _load_json_object(
        filesystem_write_admission_example_paths[0],
        "filesystem write admission preflight source",
        errors,
    )
    summary_receipt = _load_json_object(
        non_empty_diff_file_summary_example_paths[0],
        "non-empty diff file summary receipt source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"concrete filesystem write candidate example {_path_label(example_path)}",
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
        _validate_candidate_semantics(
            example,
            filesystem_preflight,
            summary_receipt,
            errors,
            _path_label(example_path),
        )
    return ConcreteFilesystemWriteEvidenceCandidateValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        filesystem_write_admission_ref=EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF,
        non_empty_diff_file_summary_ref=EXPECTED_NON_EMPTY_DIFF_FILE_SUMMARY_REF,
    )


def write_concrete_filesystem_write_evidence_candidate_validation(
    validation: ConcreteFilesystemWriteEvidenceCandidateValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic concrete filesystem write candidate validation."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_candidate(**updates: Any) -> dict[str, Any]:
    """Return the default example with nested updates for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default concrete filesystem write candidate example", [])
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


def _validate_candidate_semantics(
    candidate: Mapping[str, Any],
    filesystem_preflight: Mapping[str, Any],
    summary_receipt: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(candidate, ("receipt_id",), EXPECTED_RECEIPT_ID, errors, label)
    _check_value(candidate, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _check_value(candidate, ("candidate_status",), "candidate_recorded_without_live_write_authority", errors, label)
    _validate_scope(candidate, filesystem_preflight, errors, label)
    _validate_source_receipts(candidate, filesystem_preflight, summary_receipt, errors, label)
    _validate_candidate_evidence(candidate, errors, label)
    _validate_admission_gates(candidate, errors, label)
    _validate_receipt_refs(candidate, errors, label)
    _validate_next_action(candidate, errors, label)
    _validate_flags(candidate, errors, label)
    _scan_forbidden_text(candidate, errors, label)


def _validate_scope(
    candidate: Mapping[str, Any],
    filesystem_preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping(candidate.get("scope"))
    source_scope = _mapping(filesystem_preflight.get("scope"))
    for field in ("task_id", "run_id", "sandbox_id", "repository_connection_id", "repository_slug", "mode"):
        _check_value(scope, (field,), source_scope.get(field), errors, label)
    _check_value(scope, ("repository_slug",), EXPECTED_REPOSITORY_SLUG, errors, label)
    _check_value(scope, ("foundation_phase",), "foundation_concrete_filesystem_write_evidence_candidate", errors, label)


def _validate_source_receipts(
    candidate: Mapping[str, Any],
    filesystem_preflight: Mapping[str, Any],
    summary_receipt: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    source_receipts = _mapping(candidate.get("source_receipts"))
    _check_value(
        source_receipts,
        ("filesystem_write_admission_preflight_ref",),
        EXPECTED_FILESYSTEM_WRITE_ADMISSION_REF,
        errors,
        label,
    )
    _check_value(
        source_receipts,
        ("non_empty_diff_file_summary_receipt_ref",),
        EXPECTED_NON_EMPTY_DIFF_FILE_SUMMARY_REF,
        errors,
        label,
    )
    if filesystem_preflight.get("admission_status") != "AwaitingEvidence":
        errors.append(f"{label}: filesystem write admission source must remain AwaitingEvidence")
    if summary_receipt.get("receipt_status") != "blocked_until_filesystem_write_cleanup_redaction_uao_and_receipt_store":
        errors.append(f"{label}: non-empty diff file summary source must remain blocked")
    filesystem_gates = _mapping(filesystem_preflight.get("admission_gates"))
    summary_gates = _mapping(summary_receipt.get("admission_gates"))
    if filesystem_gates.get("filesystem_write_admitted") is not False:
        errors.append(f"{label}: source filesystem preflight must not admit filesystem writes")
    if summary_gates.get("non_empty_file_summary_emitted") is not False:
        errors.append(f"{label}: source non-empty file summary must not emit a summary")
    if source_receipts.get("source_filesystem_write_admitted") is not False:
        errors.append(f"{label}: source_receipts.source_filesystem_write_admitted must be false")
    if source_receipts.get("source_non_empty_file_summary_emitted") is not False:
        errors.append(f"{label}: source_receipts.source_non_empty_file_summary_emitted must be false")
    if source_receipts.get("source_changed_file_count") != 0:
        errors.append(f"{label}: source_receipts.source_changed_file_count must be 0")


def _validate_candidate_evidence(candidate: Mapping[str, Any], errors: list[str], label: str) -> None:
    evidence = _mapping(candidate.get("candidate_evidence"))
    _check_value(evidence, ("candidate_kind",), "redacted_non_empty_filesystem_write_evidence_candidate", errors, label)
    if not isinstance(evidence.get("candidate_changed_file_count"), int) or evidence["candidate_changed_file_count"] < 1:
        errors.append(f"{label}: candidate_evidence.candidate_changed_file_count must be non-empty")
    for field in ("changed_file_refs", "diff_refs"):
        refs = evidence.get(field)
        if not isinstance(refs, list) or not refs:
            errors.append(f"{label}: candidate_evidence.{field} must be non-empty")
            continue
        for ref in refs:
            if not isinstance(ref, str) or not ref.startswith("evidence://"):
                errors.append(f"{label}: candidate_evidence.{field} entries must be evidence refs")
    _check_value(evidence, ("redacted_diff_bundle_ref",), EXPECTED_REDACTED_BUNDLE_REF, errors, label)
    _check_value(evidence, ("cleanup_receipt_ref",), EXPECTED_CLEANUP_RECEIPT_REF, errors, label)
    _check_value(evidence, ("rollback_plan_ref",), EXPECTED_ROLLBACK_PLAN_REF, errors, label)
    _check_value(evidence, ("receipt_append_ref",), EXPECTED_RECEIPT_APPEND_REF, errors, label)


def _validate_admission_gates(candidate: Mapping[str, Any], errors: list[str], label: str) -> None:
    gates = _mapping(candidate.get("admission_gates"))
    _require_all_refs(
        gates.get("required_before_live_write_refs"),
        REQUIRED_BEFORE_REFS,
        "admission_gates.required_before_live_write_refs",
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


def _validate_receipt_refs(candidate: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_refs = _mapping(candidate.get("receipt_refs"))
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"{label}: receipt_refs.{key} must be {expected_value}")


def _validate_next_action(candidate: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = candidate.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be text")
        return
    required_phrases = (
        "actual filesystem-write receipt admission",
        "live filesystem writes",
        "terminal closure blocked",
    )
    for phrase in required_phrases:
        if phrase not in next_action:
            errors.append(f"{label}: next_action missing phrase {phrase}")


def _validate_flags(candidate: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(candidate):
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
    """Run concrete filesystem write evidence candidate validation."""
    args = build_arg_parser().parse_args(argv)
    examples = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_concrete_filesystem_write_evidence_candidate(
        schema_path=args.schema,
        example_paths=examples,
    )
    write_concrete_filesystem_write_evidence_candidate_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS CONCRETE FILESYSTEM WRITE EVIDENCE CANDIDATE VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS CONCRETE FILESYSTEM WRITE EVIDENCE CANDIDATE INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
