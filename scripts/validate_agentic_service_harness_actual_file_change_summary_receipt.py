#!/usr/bin/env python3
"""Validate Agentic Service Harness actual file-change summary receipt.

Purpose: prove actual file-change summary emission is receipt-modeled while
remaining blocked until workspace write authority, cleanup receipt, redaction
evidence, and UAO admission are explicit.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_actual_file_change_summary_receipt.schema.json,
examples/agentic_service_harness_actual_file_change_summary_receipt.foundation.json,
scripts.validate_agentic_service_harness_planned_file_change_collection_preflight,
and scripts.validate_schemas.
Invariants:
  - The receipt binds to the planned file-change collection preflight.
  - Changed file refs and diff refs remain empty while authority gates are false.
  - Raw file content, raw diffs, secret values, external effects, and terminal
    closure remain denied.
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

from scripts.validate_agentic_service_harness_planned_file_change_collection_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_PLANNED_PREFLIGHT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_PLANNED_PREFLIGHT_SCHEMA,
    validate_agentic_service_harness_planned_file_change_collection_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_actual_file_change_summary_receipt.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_actual_file_change_summary_receipt.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_actual_file_change_summary_receipt_validation.json"
)
EXPECTED_RECEIPT_ID = "agentic_service_harness_actual_file_change_summary_receipt"
EXPECTED_PLANNED_PREFLIGHT_REF = (
    "examples/agentic_service_harness_planned_file_change_collection_preflight.foundation.json"
)
EXPECTED_REPOSITORY_CONNECTION_ID = "repo-mullu-control-plane"
EXPECTED_REPOSITORY_SLUG = "tamirat-wubie/mullu-control-plane"
EXPECTED_CLEANUP_RECEIPT_REF = "receipt://sandbox-cleanup-branchwrite"
EXPECTED_REDACTION_EVIDENCE_REF = "evidence://redaction-policy-for-file-change-collection"
EXPECTED_UAO_ADMISSION_REF = "evidence://uao-file-change-summary-admission"
REQUIRED_BEFORE_SUMMARY_REFS = (
    EXPECTED_PLANNED_PREFLIGHT_REF,
    "evidence://branch-write-authority-binding",
    "evidence://operator-approval-for-branch-write",
    "evidence://workspace-write-authority",
    EXPECTED_CLEANUP_RECEIPT_REF,
    EXPECTED_REDACTION_EVIDENCE_REF,
    EXPECTED_UAO_ADMISSION_REF,
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://branch-write-authority/not-collected",
    "blocked://workspace-write-authority/not-granted",
    "blocked://operator-approval/not-collected",
    "blocked://cleanup-receipt/not-emitted",
    "blocked://redaction-evidence/not-collected",
    "blocked://uao-admission/not-verified",
)
REQUIRED_RECEIPT_REFS = {
    "actual_file_change_summary_receipt_schema": (
        "schemas/agentic_service_harness_actual_file_change_summary_receipt.schema.json"
    ),
    "planned_file_change_collection_preflight_schema": (
        "schemas/agentic_service_harness_planned_file_change_collection_preflight.schema.json"
    ),
    "planned_file_change_collection_preflight_example": EXPECTED_PLANNED_PREFLIGHT_REF,
    "agentic_service_harness_schema": "schemas/agentic_service_harness.schema.json",
    "cleanup_receipt_ref": EXPECTED_CLEANUP_RECEIPT_REF,
    "redaction_evidence_ref": EXPECTED_REDACTION_EVIDENCE_REF,
    "uao_admission_ref": EXPECTED_UAO_ADMISSION_REF,
}
REQUIRED_FALSE_FLAGS = (
    "actual_summary_allowed",
    "branch_write_authority_collected",
    "workspace_write_authority_granted",
    "operator_approval_collected",
    "cleanup_receipt_emitted",
    "redaction_evidence_collected",
    "uao_admission_verified",
    "actual_summary_receipt_emission_allowed",
    "raw_file_content_serialized",
    "absolute_paths_allowed",
    "parent_traversal_allowed",
    "secret_paths_allowed",
    "production_paths_allowed",
    "credential_value_serialization_allowed",
    "raw_secret_path_serialization_allowed",
    "raw_diff_serialization_allowed",
    "branch_created",
    "files_written",
    "actual_diff_collected",
    "file_change_summary_emitted",
    "commands_executed",
    "tests_executed",
    "pull_request_opened",
    "runtime_state_written",
    "receipt_store_appended",
    "connector_calls_observed",
    "external_effects_observed",
    "secret_values_serialized",
    "terminal_closure",
    "success_claim_allowed",
)
REQUIRED_TRUE_FLAGS = (
    "receipt_only",
    "planned_collection_preflight_verified",
    "path_allowlist_bound_to_planned_preflight",
    "secret_redaction_required",
    "diff_redaction_required",
    "receipt_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "secret_paths_allowed",
    "secret_redaction_required",
    "secret_values_serialized",
    "raw_secret_path_serialization_allowed",
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
class ActualFileChangeSummaryReceiptValidation:
    """Schema and semantic validation report for actual file-change summary receipt."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    planned_preflight_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_actual_file_change_summary_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    planned_preflight_schema_path: Path = DEFAULT_PLANNED_PREFLIGHT_SCHEMA,
    planned_preflight_example_paths: Sequence[Path] = DEFAULT_PLANNED_PREFLIGHT_EXAMPLES,
) -> ActualFileChangeSummaryReceiptValidation:
    """Validate actual file-change summary receipt examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "actual file-change summary receipt schema", errors)
    planned_validation = validate_agentic_service_harness_planned_file_change_collection_preflight(
        schema_path=planned_preflight_schema_path,
        example_paths=planned_preflight_example_paths,
    )
    if not planned_validation.ok:
        errors.extend(f"planned file-change collection preflight: {error}" for error in planned_validation.errors)
    planned_preflight = _load_json_object(
        planned_preflight_example_paths[0],
        "planned file-change collection preflight source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"actual file-change summary receipt example {_path_label(example_path)}",
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
        _validate_receipt_semantics(example, planned_preflight, errors, _path_label(example_path))
    return ActualFileChangeSummaryReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        planned_preflight_ref=EXPECTED_PLANNED_PREFLIGHT_REF,
    )


def write_actual_file_change_summary_receipt_validation(
    validation: ActualFileChangeSummaryReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic actual file-change summary validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_receipt(**updates: Any) -> dict[str, Any]:
    """Return the default example with nested updates for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default actual summary receipt example", [])
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
    planned_preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(receipt, ("receipt_id",), EXPECTED_RECEIPT_ID, errors, label)
    _check_value(receipt, ("source_planned_file_change_collection_preflight_ref",), EXPECTED_PLANNED_PREFLIGHT_REF, errors, label)
    _check_value(receipt, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _check_value(receipt, ("receipt_status",), "blocked_until_authority_and_uao", errors, label)
    _validate_scope(receipt, planned_preflight, errors, label)
    _validate_admission_gates(receipt, planned_preflight, errors, label)
    _validate_file_change_summary(receipt, errors, label)
    _validate_path_and_redaction(receipt, planned_preflight, errors, label)
    _validate_receipt_refs(receipt, errors, label)
    _validate_flags(receipt, errors, label)
    _scan_forbidden_text(receipt, errors, label)


def _validate_scope(
    receipt: Mapping[str, Any],
    planned_preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping(receipt.get("scope"))
    planned_scope = _mapping(planned_preflight.get("scope"))
    for field in ("project_id", "task_id", "run_id", "sandbox_id", "repository_connection_id", "repository_slug", "mode", "foundation_phase"):
        _check_value(scope, (field,), planned_scope.get(field), errors, label)
    _check_value(scope, ("repository_connection_id",), EXPECTED_REPOSITORY_CONNECTION_ID, errors, label)
    _check_value(scope, ("repository_slug",), EXPECTED_REPOSITORY_SLUG, errors, label)
    if planned_preflight.get("collection_status") != "AwaitingEvidence":
        errors.append(f"{label}: planned preflight must remain AwaitingEvidence before actual summary")


def _validate_admission_gates(
    receipt: Mapping[str, Any],
    planned_preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    gates = _mapping(receipt.get("admission_gates"))
    if planned_preflight.get("solver_outcome") != "SolvedVerified":
        errors.append(f"{label}: planned preflight must be SolvedVerified")
    _require_all_refs(
        gates.get("required_before_summary_refs", ()),
        REQUIRED_BEFORE_SUMMARY_REFS,
        "admission_gates.required_before_summary_refs",
        errors,
        label,
    )
    _require_all_refs(
        gates.get("blocked_reason_refs", ()),
        REQUIRED_BLOCKED_REASON_REFS,
        "admission_gates.blocked_reason_refs",
        errors,
        label,
    )


def _validate_file_change_summary(
    receipt: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    summary = _mapping(receipt.get("file_change_summary"))
    changed_refs = summary.get("changed_file_refs")
    diff_refs = summary.get("diff_refs")
    if summary.get("changed_file_count") != 0:
        errors.append(f"{label}: file_change_summary.changed_file_count must be 0 while authority is absent")
    if changed_refs != []:
        errors.append(f"{label}: file_change_summary.changed_file_refs must be empty while authority is absent")
    if diff_refs != []:
        errors.append(f"{label}: file_change_summary.diff_refs must be empty while authority is absent")
    if summary.get("raw_file_content_serialized") is not False:
        errors.append(f"{label}: file_change_summary.raw_file_content_serialized must be false")


def _validate_path_and_redaction(
    receipt: Mapping[str, Any],
    planned_preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    path_policy = _mapping(receipt.get("path_policy"))
    planned_path_policy = _mapping(planned_preflight.get("path_policy"))
    if path_policy.get("path_allowlist") != planned_path_policy.get("path_allowlist"):
        errors.append(f"{label}: path_policy.path_allowlist must match planned preflight")
    redaction_policy = _mapping(receipt.get("redaction_policy"))
    planned_redaction = _mapping(planned_preflight.get("redaction_policy"))
    if redaction_policy.get("redaction_evidence_ref") != planned_redaction.get("redaction_evidence_ref"):
        errors.append(f"{label}: redaction_policy.redaction_evidence_ref must match planned preflight")


def _validate_receipt_refs(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_refs = _mapping(receipt.get("receipt_refs"))
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"{label}: receipt_refs.{key} must be {expected_value}")


def _validate_flags(receipt: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(receipt):
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
    """Run actual file-change summary receipt validation."""
    args = build_arg_parser().parse_args(argv)
    examples = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_actual_file_change_summary_receipt(
        schema_path=args.schema,
        example_paths=examples,
    )
    write_actual_file_change_summary_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS ACTUAL FILE CHANGE SUMMARY RECEIPT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS ACTUAL FILE CHANGE SUMMARY RECEIPT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
