#!/usr/bin/env python3
"""Validate Agentic Service Harness planned file-change collection preflight.

Purpose: prove planned file-change collection is bound to workspace sandbox,
branch-write authority, cleanup, path, redaction, and effect-denial gates before
any actual diff collection or file write can be admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_planned_file_change_collection_preflight.schema.json,
examples/agentic_service_harness_planned_file_change_collection_preflight.foundation.json,
scripts.validate_agentic_service_harness_workspace_sandbox_preflight,
scripts.validate_agentic_service_harness_github_pr_branch_write_authority_binding,
and scripts.validate_schemas.
Invariants:
  - The preflight binds to the workspace sandbox preflight and branch-write
    authority binding examples.
  - Branch-write authority, workspace write authority, approval, cleanup receipt
    emission, collection admission, actual diff collection, and file writes fail closed.
  - Path policy, cleanup receipt refs, and redaction policy are explicit.
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

from scripts.validate_agentic_service_harness_github_pr_branch_write_authority_binding import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_BRANCH_WRITE_AUTHORITY_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_BRANCH_WRITE_AUTHORITY_SCHEMA,
    validate_agentic_service_harness_github_pr_branch_write_authority_binding,
)
from scripts.validate_agentic_service_harness_workspace_sandbox_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_WORKSPACE_SANDBOX_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_WORKSPACE_SANDBOX_SCHEMA,
    validate_agentic_service_harness_workspace_sandbox_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_planned_file_change_collection_preflight.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_planned_file_change_collection_preflight.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_planned_file_change_collection_preflight_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_planned_file_change_collection_preflight"
EXPECTED_WORKSPACE_SANDBOX_REF = (
    "examples/agentic_service_harness_workspace_sandbox_preflight.foundation.json"
)
EXPECTED_BRANCH_WRITE_AUTHORITY_REF = (
    "examples/agentic_service_harness_github_pr_branch_write_authority_binding.foundation.json"
)
EXPECTED_COLLECTION_ID = "planned-file-change-collection-foundation"
EXPECTED_CLEANUP_RECEIPT_REF = "receipt://sandbox-cleanup-branchwrite"
EXPECTED_REPOSITORY_CONNECTION_ID = "repo-mullu-control-plane"
EXPECTED_REPOSITORY_SLUG = "tamirat-wubie/mullu-control-plane"
REQUIRED_FORBIDDEN_ACTION_CLASSES = (
    "create_branch",
    "write_files",
    "collect_actual_diff",
    "execute_commands",
    "run_tests",
    "open_pr",
    "append_receipt_store",
    "call_connector",
    "deploy",
    "dns_mutation",
    "secret_mutation",
    "destructive_operation",
    "terminal_closure",
)
REQUIRED_FILE_CHANGE_KINDS = (
    "schema_patch",
    "example_patch",
    "validator_patch",
    "test_patch",
    "documentation_patch",
    "ci_patch",
    "governance_preflight_patch",
)
REQUIRED_BEFORE_COLLECTION_REFS = (
    EXPECTED_WORKSPACE_SANDBOX_REF,
    EXPECTED_BRANCH_WRITE_AUTHORITY_REF,
    EXPECTED_CLEANUP_RECEIPT_REF,
    "evidence://operator-approval-for-branch-write",
    "evidence://workspace-write-authority",
    "evidence://redaction-policy-for-file-change-collection",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_agentic_service_harness_planned_file_change_collection_preflight.py",
    "scripts/validate_agentic_service_harness_workspace_sandbox_preflight.py",
    "scripts/validate_agentic_service_harness_github_pr_branch_write_authority_binding.py",
)
REQUIRED_BLOCKED_REASON_REFS = (
    "blocked://branch-write-authority/not-collected",
    "blocked://operator-approval/not-collected",
    "blocked://cleanup-receipt/not-emitted",
    "blocked://workspace-write-authority/not-granted",
    "blocked://actual-diff-collection/not-admitted",
)
REQUIRED_RECEIPT_REFS = {
    "planned_file_change_collection_preflight_schema": (
        "schemas/agentic_service_harness_planned_file_change_collection_preflight.schema.json"
    ),
    "workspace_sandbox_preflight_schema": (
        "schemas/agentic_service_harness_workspace_sandbox_preflight.schema.json"
    ),
    "workspace_sandbox_preflight_example": EXPECTED_WORKSPACE_SANDBOX_REF,
    "github_pr_branch_write_authority_binding_schema": (
        "schemas/agentic_service_harness_github_pr_branch_write_authority_binding.schema.json"
    ),
    "github_pr_branch_write_authority_binding_example": EXPECTED_BRANCH_WRITE_AUTHORITY_REF,
    "agentic_service_harness_schema": "schemas/agentic_service_harness.schema.json",
    "cleanup_receipt_ref": EXPECTED_CLEANUP_RECEIPT_REF,
}
REQUIRED_FALSE_FLAGS = (
    "workspace_write_authority_granted",
    "branch_write_authority_collected",
    "cleanup_receipt_emitted",
    "planned_file_change_collection_admitted",
    "actual_file_change_collection_started",
    "operator_approval_collected",
    "collection_admitted",
    "absolute_paths_allowed",
    "parent_traversal_allowed",
    "secret_paths_allowed",
    "production_paths_allowed",
    "credential_value_serialization_allowed",
    "raw_secret_path_serialization_allowed",
    "branch_created",
    "files_written",
    "actual_diff_collected",
    "file_change_summary_emitted",
    "commands_executed",
    "tests_executed",
    "cleanup_executed",
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
    "preflight_only",
    "workspace_write_authority_required",
    "planned_collection_only",
    "file_change_summary_required_after_collection",
    "diff_receipt_required_after_collection",
    "workspace_sandbox_preflight_verified",
    "branch_write_authority_binding_verified",
    "path_allowlist_bound_to_workspace_sandbox",
    "secret_redaction_required",
    "diff_redaction_required",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "secret_paths_allowed",
    "secret_redaction_required",
    "secret_mutation",
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
class PlannedFileChangeCollectionPreflightValidation:
    """Schema and semantic validation report for planned file-change collection."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    workspace_sandbox_preflight_ref: str
    branch_write_authority_binding_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_planned_file_change_collection_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    workspace_sandbox_schema_path: Path = DEFAULT_WORKSPACE_SANDBOX_SCHEMA,
    workspace_sandbox_example_paths: Sequence[Path] = DEFAULT_WORKSPACE_SANDBOX_EXAMPLES,
    branch_write_authority_schema_path: Path = DEFAULT_BRANCH_WRITE_AUTHORITY_SCHEMA,
    branch_write_authority_example_paths: Sequence[Path] = DEFAULT_BRANCH_WRITE_AUTHORITY_EXAMPLES,
) -> PlannedFileChangeCollectionPreflightValidation:
    """Validate planned file-change collection preflight examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "planned file-change collection schema", errors)
    workspace_validation = validate_agentic_service_harness_workspace_sandbox_preflight(
        schema_path=workspace_sandbox_schema_path,
        example_paths=workspace_sandbox_example_paths,
    )
    if not workspace_validation.ok:
        errors.extend(f"workspace sandbox preflight: {error}" for error in workspace_validation.errors)
    branch_authority_validation = validate_agentic_service_harness_github_pr_branch_write_authority_binding(
        schema_path=branch_write_authority_schema_path,
        example_paths=branch_write_authority_example_paths,
    )
    if not branch_authority_validation.ok:
        errors.extend(
            f"branch-write authority binding: {error}"
            for error in branch_authority_validation.errors
        )
    workspace_preflight = _load_json_object(
        workspace_sandbox_example_paths[0],
        "workspace sandbox preflight source",
        errors,
    )
    branch_authority = _load_json_object(
        branch_write_authority_example_paths[0],
        "branch-write authority binding source",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"planned file-change collection example {_path_label(example_path)}",
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
        _validate_preflight_semantics(
            example,
            workspace_preflight,
            branch_authority,
            errors,
            _path_label(example_path),
        )
    return PlannedFileChangeCollectionPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        workspace_sandbox_preflight_ref=EXPECTED_WORKSPACE_SANDBOX_REF,
        branch_write_authority_binding_ref=EXPECTED_BRANCH_WRITE_AUTHORITY_REF,
    )


def write_planned_file_change_collection_preflight_validation(
    validation: PlannedFileChangeCollectionPreflightValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic planned file-change collection validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_preflight(**updates: Any) -> dict[str, Any]:
    """Return the default example with nested updates for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default planned preflight example", [])
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
    payload: Mapping[str, Any],
    workspace_preflight: Mapping[str, Any],
    branch_authority: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(payload, ("report_id",), EXPECTED_REPORT_ID, errors, label)
    _check_value(payload, ("source_workspace_sandbox_preflight_ref",), EXPECTED_WORKSPACE_SANDBOX_REF, errors, label)
    _check_value(payload, ("source_branch_write_authority_binding_ref",), EXPECTED_BRANCH_WRITE_AUTHORITY_REF, errors, label)
    _check_value(payload, ("solver_outcome",), "SolvedVerified", errors, label)
    _check_value(payload, ("collection_status",), "AwaitingEvidence", errors, label)
    _validate_scope(payload, workspace_preflight, branch_authority, errors, label)
    _validate_collection_contract(payload, errors, label)
    _validate_authority_gates(payload, workspace_preflight, branch_authority, errors, label)
    _validate_path_and_redaction(payload, workspace_preflight, errors, label)
    _validate_receipt_refs(payload, errors, label)
    _validate_flags(payload, errors, label)
    _scan_forbidden_text(payload, errors, label)


def _validate_scope(
    payload: Mapping[str, Any],
    workspace_preflight: Mapping[str, Any],
    branch_authority: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping(payload.get("scope"))
    workspace_scope = _mapping(workspace_preflight.get("scope"))
    branch_scope = _mapping(branch_authority.get("scope"))
    for field in ("project_id", "task_id", "run_id", "sandbox_id", "mode", "foundation_phase"):
        _check_value(scope, (field,), workspace_scope.get(field), errors, label)
    _check_value(scope, ("repository_connection_id",), branch_scope.get("repository_connection_id"), errors, label)
    _check_value(scope, ("repository_slug",), branch_scope.get("repository_slug"), errors, label)
    _check_value(scope, ("repository_connection_id",), EXPECTED_REPOSITORY_CONNECTION_ID, errors, label)
    _check_value(scope, ("repository_slug",), EXPECTED_REPOSITORY_SLUG, errors, label)
    if workspace_scope.get("workspace_write_enabled") is not False:
        errors.append(f"{label}: source workspace preflight must keep workspace writes disabled")
    if branch_authority.get("authority_granted") is not False:
        errors.append(f"{label}: source branch-write binding must not grant authority")


def _validate_collection_contract(
    payload: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    contract = _mapping(payload.get("collection_contract"))
    _check_value(contract, ("collection_id",), EXPECTED_COLLECTION_ID, errors, label)
    _check_value(contract, ("collection_mode",), "PREFLIGHT_ONLY", errors, label)
    _check_value(contract, ("collection_kind",), "planned_file_change_collection", errors, label)
    if contract.get("allowed_action_classes") != ["preflight"]:
        errors.append(f"{label}: collection_contract.allowed_action_classes must be ['preflight']")
    _require_all_refs(
        contract.get("forbidden_action_classes", ()),
        REQUIRED_FORBIDDEN_ACTION_CLASSES,
        "collection_contract.forbidden_action_classes",
        errors,
        label,
    )
    _require_all_refs(
        contract.get("allowed_file_change_kinds", ()),
        REQUIRED_FILE_CHANGE_KINDS,
        "collection_contract.allowed_file_change_kinds",
        errors,
        label,
    )
    _require_all_refs(
        contract.get("required_before_collection_refs", ()),
        REQUIRED_BEFORE_COLLECTION_REFS,
        "collection_contract.required_before_collection_refs",
        errors,
        label,
    )
    _require_all_refs(
        contract.get("required_validation_refs", ()),
        REQUIRED_VALIDATION_REFS,
        "collection_contract.required_validation_refs",
        errors,
        label,
    )


def _validate_authority_gates(
    payload: Mapping[str, Any],
    workspace_preflight: Mapping[str, Any],
    branch_authority: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    gates = _mapping(payload.get("authority_gates"))
    if workspace_preflight.get("solver_outcome") != "SolvedVerified":
        errors.append(f"{label}: source workspace sandbox preflight must be SolvedVerified")
    if branch_authority.get("binding_status") != "AwaitingEvidence":
        errors.append(f"{label}: source branch-write binding must remain AwaitingEvidence")
    _require_all_refs(
        gates.get("blocked_reason_refs", ()),
        REQUIRED_BLOCKED_REASON_REFS,
        "authority_gates.blocked_reason_refs",
        errors,
        label,
    )


def _validate_path_and_redaction(
    payload: Mapping[str, Any],
    workspace_preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    path_policy = _mapping(payload.get("path_policy"))
    source_controls = _mapping(workspace_preflight.get("sandbox_controls"))
    if path_policy.get("path_allowlist") != source_controls.get("path_allowlist"):
        errors.append(f"{label}: path_policy.path_allowlist must match workspace sandbox preflight")
    redaction_policy = _mapping(payload.get("redaction_policy"))
    if redaction_policy.get("secret_redaction_required") != source_controls.get("secret_redaction_required"):
        errors.append(f"{label}: redaction_policy.secret_redaction_required must match workspace sandbox preflight")
    if redaction_policy.get("redaction_evidence_ref") != "evidence://redaction-policy-for-file-change-collection":
        errors.append(f"{label}: redaction_policy.redaction_evidence_ref must bind file-change redaction evidence")


def _validate_receipt_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_refs = _mapping(payload.get("receipt_refs"))
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"{label}: receipt_refs.{key} must be {expected_value}")


def _validate_flags(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
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
    """Run planned file-change collection preflight validation."""
    args = build_arg_parser().parse_args(argv)
    examples = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_planned_file_change_collection_preflight(
        schema_path=args.schema,
        example_paths=examples,
    )
    write_planned_file_change_collection_preflight_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS PLANNED FILE CHANGE COLLECTION PREFLIGHT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS PLANNED FILE CHANGE COLLECTION PREFLIGHT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
