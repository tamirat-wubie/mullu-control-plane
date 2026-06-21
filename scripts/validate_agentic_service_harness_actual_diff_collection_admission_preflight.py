#!/usr/bin/env python3
"""Validate Agentic Service Harness actual diff collection admission preflight.

Purpose: prove non-empty diff collection remains blocked until actual-summary
receipt, authority, cleanup, redaction, UAO, and receipt-store evidence exist.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_actual_diff_collection_admission_preflight.schema.json,
examples/agentic_service_harness_actual_diff_collection_admission_preflight.foundation.json,
scripts.validate_agentic_service_harness_actual_file_change_summary_receipt,
and scripts.validate_schemas.
Invariants:
  - The preflight binds to the actual file-change summary receipt.
  - Non-empty changed-file refs and diff refs remain empty while authority gates are false.
  - Raw diffs, secret values, receipt-store append, external effects, and terminal
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

from scripts.validate_agentic_service_harness_actual_file_change_summary_receipt import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_ACTUAL_SUMMARY_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_ACTUAL_SUMMARY_SCHEMA,
    validate_agentic_service_harness_actual_file_change_summary_receipt,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_actual_diff_collection_admission_preflight.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_actual_diff_collection_admission_preflight.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_actual_diff_collection_admission_preflight_validation.json"
)
EXPECTED_RECEIPT_ID = "agentic_service_harness_actual_diff_collection_admission_preflight"
EXPECTED_ACTUAL_SUMMARY_REF = (
    "examples/agentic_service_harness_actual_file_change_summary_receipt.foundation.json"
)
EXPECTED_PLANNED_PREFLIGHT_REF = (
    "examples/agentic_service_harness_planned_file_change_collection_preflight.foundation.json"
)
EXPECTED_REPOSITORY_CONNECTION_ID = "repo-mullu-control-plane"
EXPECTED_REPOSITORY_SLUG = "tamirat-wubie/mullu-control-plane"
EXPECTED_CLEANUP_RECEIPT_REF = "receipt://sandbox-cleanup-branchwrite"
EXPECTED_REDACTION_EVIDENCE_REF = "evidence://redaction-policy-for-file-change-collection"
EXPECTED_UAO_DIFF_COLLECTION_ADMISSION_REF = "evidence://uao-actual-diff-collection-admission"
EXPECTED_RECEIPT_STORE_WRITE_PATH_REF = "evidence://receipt-store-write-path-for-diff-collection"
REQUIRED_BEFORE_DIFF_COLLECTION_REFS = (
    EXPECTED_ACTUAL_SUMMARY_REF,
    EXPECTED_PLANNED_PREFLIGHT_REF,
    "evidence://branch-write-authority-binding",
    "evidence://operator-approval-for-branch-write",
    "evidence://workspace-write-authority",
    EXPECTED_CLEANUP_RECEIPT_REF,
    EXPECTED_REDACTION_EVIDENCE_REF,
    EXPECTED_UAO_DIFF_COLLECTION_ADMISSION_REF,
    EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://branch-write-authority/not-collected",
    "blocked://workspace-write-authority/not-granted",
    "blocked://operator-approval/not-collected",
    "blocked://cleanup-receipt/not-emitted",
    "blocked://redaction-evidence/not-collected",
    "blocked://uao-diff-collection/not-verified",
    "blocked://receipt-store-write-path/not-verified",
)
REQUIRED_RECEIPT_REFS = {
    "actual_diff_collection_admission_preflight_schema": (
        "schemas/agentic_service_harness_actual_diff_collection_admission_preflight.schema.json"
    ),
    "actual_file_change_summary_receipt_schema": (
        "schemas/agentic_service_harness_actual_file_change_summary_receipt.schema.json"
    ),
    "actual_file_change_summary_receipt_example": EXPECTED_ACTUAL_SUMMARY_REF,
    "planned_file_change_collection_preflight_example": EXPECTED_PLANNED_PREFLIGHT_REF,
    "cleanup_receipt_ref": EXPECTED_CLEANUP_RECEIPT_REF,
    "redaction_evidence_ref": EXPECTED_REDACTION_EVIDENCE_REF,
    "uao_diff_collection_admission_ref": EXPECTED_UAO_DIFF_COLLECTION_ADMISSION_REF,
    "receipt_store_write_path_ref": EXPECTED_RECEIPT_STORE_WRITE_PATH_REF,
}
REQUIRED_FALSE_FLAGS = (
    "actual_diff_collection_allowed",
    "branch_write_authority_collected",
    "workspace_write_authority_granted",
    "operator_approval_collected",
    "cleanup_receipt_emitted",
    "redaction_evidence_collected",
    "uao_diff_collection_admission_verified",
    "receipt_store_write_path_verified",
    "non_empty_diff_allowed",
    "raw_diff_serialization_allowed",
    "absolute_paths_allowed",
    "parent_traversal_allowed",
    "secret_paths_allowed",
    "production_paths_allowed",
    "credential_value_serialization_allowed",
    "raw_secret_path_serialization_allowed",
    "branch_created",
    "files_written",
    "actual_diff_collected",
    "non_empty_file_change_summary_emitted",
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
    "effect_allowed",
)
REQUIRED_TRUE_FLAGS = (
    "receipt_only",
    "actual_file_change_summary_receipt_verified",
    "actual_summary_is_zero_file",
    "path_allowlist_bound_to_actual_summary",
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
class ActualDiffCollectionAdmissionPreflightValidation:
    """Schema and semantic validation report for actual diff collection preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    actual_summary_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_actual_diff_collection_admission_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    actual_summary_schema_path: Path = DEFAULT_ACTUAL_SUMMARY_SCHEMA,
    actual_summary_example_paths: Sequence[Path] = DEFAULT_ACTUAL_SUMMARY_EXAMPLES,
) -> ActualDiffCollectionAdmissionPreflightValidation:
    """Validate actual diff collection admission preflight examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "actual diff collection admission preflight schema", errors)
    actual_summary_validation = validate_agentic_service_harness_actual_file_change_summary_receipt(
        schema_path=actual_summary_schema_path,
        example_paths=actual_summary_example_paths,
    )
    if not actual_summary_validation.ok:
        errors.extend(f"actual file-change summary receipt: {error}" for error in actual_summary_validation.errors)
    actual_summary = _load_json_object(
        actual_summary_example_paths[0],
        "actual file-change summary receipt source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"actual diff collection preflight example {_path_label(example_path)}",
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
        _validate_preflight_semantics(example, actual_summary, errors, _path_label(example_path))
    return ActualDiffCollectionAdmissionPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        actual_summary_ref=EXPECTED_ACTUAL_SUMMARY_REF,
    )


def write_actual_diff_collection_admission_preflight_validation(
    validation: ActualDiffCollectionAdmissionPreflightValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic actual diff collection admission validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_preflight(**updates: Any) -> dict[str, Any]:
    """Return the default example with nested updates for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default actual diff collection preflight example", [])
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


def _validate_preflight_semantics(
    preflight: Mapping[str, Any],
    actual_summary: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(preflight, ("receipt_id",), EXPECTED_RECEIPT_ID, errors, label)
    _check_value(preflight, ("source_actual_file_change_summary_receipt_ref",), EXPECTED_ACTUAL_SUMMARY_REF, errors, label)
    _check_value(preflight, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _check_value(preflight, ("preflight_status",), "blocked_until_summary_authority_cleanup_redaction_uao_and_receipt_store", errors, label)
    _validate_scope(preflight, actual_summary, errors, label)
    _validate_admission_gates(preflight, actual_summary, errors, label)
    _validate_diff_collection_plan(preflight, errors, label)
    _validate_path_and_redaction(preflight, actual_summary, errors, label)
    _validate_workflow_stages(preflight, errors, label)
    _validate_receipt_refs(preflight, errors, label)
    _validate_flags(preflight, errors, label)
    _scan_forbidden_text(preflight, errors, label)


def _validate_scope(
    preflight: Mapping[str, Any],
    actual_summary: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping(preflight.get("scope"))
    summary_scope = _mapping(actual_summary.get("scope"))
    for field in ("project_id", "task_id", "run_id", "sandbox_id", "repository_connection_id", "repository_slug", "mode", "foundation_phase"):
        _check_value(scope, (field,), summary_scope.get(field), errors, label)
    _check_value(scope, ("repository_connection_id",), EXPECTED_REPOSITORY_CONNECTION_ID, errors, label)
    _check_value(scope, ("repository_slug",), EXPECTED_REPOSITORY_SLUG, errors, label)
    if actual_summary.get("solver_outcome") != "AwaitingEvidence":
        errors.append(f"{label}: actual summary receipt must remain AwaitingEvidence before diff collection")


def _validate_admission_gates(
    preflight: Mapping[str, Any],
    actual_summary: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    gates = _mapping(preflight.get("admission_gates"))
    summary = _mapping(actual_summary.get("file_change_summary"))
    summary_effect = _mapping(actual_summary.get("effect_boundary"))
    if summary.get("changed_file_count") != 0 or summary.get("diff_refs") != []:
        errors.append(f"{label}: source actual summary must be zero-file before diff admission preflight")
    if summary_effect.get("actual_diff_collected") is not False:
        errors.append(f"{label}: source actual summary must not collect actual diffs")
    _require_all_refs(
        gates.get("required_before_diff_collection_refs", ()),
        REQUIRED_BEFORE_DIFF_COLLECTION_REFS,
        "admission_gates.required_before_diff_collection_refs",
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


def _validate_diff_collection_plan(
    preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    plan = _mapping(preflight.get("diff_collection_plan"))
    if plan.get("candidate_changed_file_count") != 0:
        errors.append(f"{label}: diff_collection_plan.candidate_changed_file_count must be 0 while authority is absent")
    if plan.get("changed_file_refs") != []:
        errors.append(f"{label}: diff_collection_plan.changed_file_refs must be empty while authority is absent")
    if plan.get("diff_refs") != []:
        errors.append(f"{label}: diff_collection_plan.diff_refs must be empty while authority is absent")
    if plan.get("non_empty_diff_allowed") is not False:
        errors.append(f"{label}: diff_collection_plan.non_empty_diff_allowed must be false")
    if plan.get("raw_diff_serialization_allowed") is not False:
        errors.append(f"{label}: diff_collection_plan.raw_diff_serialization_allowed must be false")


def _validate_path_and_redaction(
    preflight: Mapping[str, Any],
    actual_summary: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    path_policy = _mapping(preflight.get("path_policy"))
    summary_path_policy = _mapping(actual_summary.get("path_policy"))
    if path_policy.get("path_allowlist") != summary_path_policy.get("path_allowlist"):
        errors.append(f"{label}: path_policy.path_allowlist must match actual summary")
    redaction_policy = _mapping(preflight.get("redaction_policy"))
    summary_redaction = _mapping(actual_summary.get("redaction_policy"))
    if redaction_policy.get("redaction_evidence_ref") != summary_redaction.get("redaction_evidence_ref"):
        errors.append(f"{label}: redaction_policy.redaction_evidence_ref must match actual summary")


def _validate_workflow_stages(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    stages = preflight.get("workflow_stages")
    if not isinstance(stages, list):
        errors.append(f"{label}: workflow_stages must be a list")
        return
    stage_ids: set[str] = set()
    for stage in stages:
        stage_map = _mapping(stage)
        stage_id = stage_map.get("stage_id")
        if not isinstance(stage_id, str):
            errors.append(f"{label}: workflow stage missing stage_id")
            continue
        if stage_id in stage_ids:
            errors.append(f"{label}: duplicate workflow stage {stage_id}")
        stage_ids.add(stage_id)
        if stage_map.get("effect_allowed") is not False:
            errors.append(f"{label}: workflow stage {stage_id} must keep effect_allowed false")
    for stage in stages:
        stage_map = _mapping(stage)
        stage_id = str(stage_map.get("stage_id"))
        predecessors = stage_map.get("predecessor_stage_ids")
        if not isinstance(predecessors, list):
            errors.append(f"{label}: workflow stage {stage_id} predecessor_stage_ids must be a list")
            continue
        for predecessor in predecessors:
            if predecessor not in stage_ids:
                errors.append(f"{label}: workflow stage {stage_id} has dangling predecessor {predecessor}")
    _assert_acyclic(stages, errors, label)


def _assert_acyclic(stages: Sequence[Any], errors: list[str], label: str) -> None:
    predecessor_map: dict[str, set[str]] = {}
    for stage in stages:
        stage_map = _mapping(stage)
        stage_id = stage_map.get("stage_id")
        predecessors = stage_map.get("predecessor_stage_ids")
        if isinstance(stage_id, str) and isinstance(predecessors, list):
            predecessor_map[stage_id] = {str(predecessor) for predecessor in predecessors}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(stage_id: str) -> None:
        if stage_id in visited:
            return
        if stage_id in visiting:
            errors.append(f"{label}: workflow stage cycle detected at {stage_id}")
            return
        visiting.add(stage_id)
        for predecessor in predecessor_map.get(stage_id, set()):
            if predecessor in predecessor_map:
                visit(predecessor)
        visiting.remove(stage_id)
        visited.add(stage_id)

    for stage_id in predecessor_map:
        visit(stage_id)


def _validate_receipt_refs(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_refs = _mapping(preflight.get("receipt_refs"))
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"{label}: receipt_refs.{key} must be {expected_value}")


def _validate_flags(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(preflight):
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
    """Run actual diff collection admission preflight validation."""
    args = build_arg_parser().parse_args(argv)
    examples = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_actual_diff_collection_admission_preflight(
        schema_path=args.schema,
        example_paths=examples,
    )
    write_actual_diff_collection_admission_preflight_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS ACTUAL DIFF COLLECTION ADMISSION PREFLIGHT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS ACTUAL DIFF COLLECTION ADMISSION PREFLIGHT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
