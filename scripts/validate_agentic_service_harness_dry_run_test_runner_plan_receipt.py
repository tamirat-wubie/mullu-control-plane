#!/usr/bin/env python3
"""Validate Agentic Service Harness dry-run test runner plan receipt.

Purpose: prove selected harness validator and pytest commands are recorded as a
plan-only receipt before command execution, subprocess execution, test-result
claims, receipt append, adapter execution, or terminal closure can be admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_dry_run_test_runner_plan_receipt.schema.json,
examples/agentic_service_harness_dry_run_test_runner_plan_receipt.foundation.json,
scripts.validate_agentic_service_harness_approved_branch_workspace_creation_preflight,
and scripts.validate_schemas.
Invariants:
  - The approved branch workspace creation preflight passes first.
  - Selected commands are exact allowlisted command strings.
  - Commands are not executed and no test result or coverage claim is made.
  - Filesystem writes, adapter execution, connector calls, receipt append,
    secret serialization, mutation routes, and terminal closure fail closed.
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

from scripts.validate_agentic_service_harness_approved_branch_workspace_creation_preflight import (  # noqa: E402
    validate_agentic_service_harness_approved_branch_workspace_creation_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_dry_run_test_runner_plan_receipt.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_dry_run_test_runner_plan_receipt.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_dry_run_test_runner_plan_receipt_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_dry_run_test_runner_plan_receipt"
EXPECTED_REPOSITORY_CONNECTION_ID = "repo-mullu-control-plane"
EXPECTED_REPOSITORY_SLUG = "tamirat-wubie/mullu-control-plane"
EXPECTED_PLAN_ID = "dry-run-test-runner-plan-foundation"
EXPECTED_EXECUTION_MODE = "PLAN_ONLY"
EXPECTED_APPROVED_BRANCH_WORKSPACE_REF = (
    "examples/agentic_service_harness_approved_branch_workspace_creation_preflight.foundation.json"
)
REQUIRED_SOURCE_REFS = (
    "examples/agentic_service_harness_task_creation_admission_preflight.foundation.json",
    EXPECTED_APPROVED_BRANCH_WORKSPACE_REF,
    "scripts/validate_agentic_service_harness_readiness_map.py",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
ALLOWED_COMMANDS = (
    "python scripts/validate_agentic_service_harness_approved_branch_workspace_creation_preflight.py --strict",
    "python scripts/validate_agentic_service_harness_dry_run_test_runner_plan_receipt.py --strict",
    "python scripts/validate_agentic_service_harness_readiness_map.py",
    "python -m pytest tests/test_validate_agentic_service_harness_dry_run_test_runner_plan_receipt.py -q",
)
REQUIRED_SELECTION_REASON_REFS = (
    "evidence://approved-branch-workspace-preflight-valid",
    "evidence://test-runner-plan-validator-contract",
    "evidence://readiness-map-topology-boundary",
    "evidence://focused-unit-test-contract",
)
REQUIRED_BEFORE_COMMAND_EXECUTION_REFS = (
    "approval://operator/test-command-execution",
    "evidence://branch-workspace-created-with-approval",
    "evidence://workspace-path-confinement",
    "evidence://test-command-timeout-policy",
    "evidence://subprocess-output-redaction-policy",
)
REQUIRED_BEFORE_RESULT_CLAIM_REFS = (
    "evidence://commands-executed-in-approved-workspace",
    "evidence://test-command-exit-codes",
    "evidence://test-output-captured-with-redaction",
)
REQUIRED_BEFORE_RECEIPT_APPEND_REFS = (
    "evidence://receipt-store-write-path",
    "evidence://receipt-redaction-policy",
    "evidence://receipt-append-rollback-plan",
)
REQUIRED_RECEIPT_REFS = {
    "dry_run_test_runner_plan_receipt_schema": (
        "schemas/agentic_service_harness_dry_run_test_runner_plan_receipt.schema.json"
    ),
    "dry_run_test_runner_plan_receipt_example": (
        "examples/agentic_service_harness_dry_run_test_runner_plan_receipt.foundation.json"
    ),
    "approved_branch_workspace_creation_preflight_schema": (
        "schemas/agentic_service_harness_approved_branch_workspace_creation_preflight.schema.json"
    ),
    "approved_branch_workspace_creation_preflight_example": EXPECTED_APPROVED_BRANCH_WORKSPACE_REF,
    "readiness_map": "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
}
REQUIRED_FALSE_FLAGS = (
    "test_execution_admitted",
    "commands_executed",
    "test_results_claimed",
    "coverage_claimed",
    "secret_values_serialized",
    "command_execution_enabled",
    "subprocess_execution_enabled",
    "test_result_claim_enabled",
    "coverage_claim_enabled",
    "test_execution_enabled",
    "filesystem_write_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "adapter_execution_enabled",
    "connector_calls_enabled",
    "receipt_store_append_enabled",
    "runtime_state_write_enabled",
    "mutation_route_enabled",
    "terminal_closure",
    "default_high_risk_authority",
)
REQUIRED_AUTHORITY_DENIAL_KEYS = (
    "test_execution_enabled",
    "command_execution_enabled",
    "subprocess_execution_enabled",
    "filesystem_write_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "adapter_execution_enabled",
    "connector_calls_enabled",
    "receipt_store_append_enabled",
    "runtime_state_write_enabled",
    "mutation_route_enabled",
    "secret_values_serialized",
    "terminal_closure",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "plan_only",
    "read_only_sources",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
)
ALLOWED_SECRET_KEYS = {
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
class DryRunTestRunnerPlanReceiptValidation:
    """Schema and semantic validation report for dry-run test runner planning."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_validators_ok: bool
    selected_command_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_dry_run_test_runner_plan_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> DryRunTestRunnerPlanReceiptValidation:
    """Validate dry-run test runner plan receipt examples."""

    errors: list[str] = []
    source_errors = _validate_sources()
    errors.extend(source_errors)
    schema = _load_json_object(schema_path, "dry-run test runner plan receipt schema", errors)
    selected_command_count = 0

    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"dry-run test runner plan receipt example {_path_label(example_path)}",
            errors,
        )
        if not example:
            continue
        examples.append(example)
        selected_commands = _mapping(example.get("test_plan")).get("selected_commands")
        if isinstance(selected_commands, list):
            selected_command_count += len(selected_commands)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_semantics(example, errors, _path_label(example_path))

    return DryRunTestRunnerPlanReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_validators_ok=not source_errors,
        selected_command_count=selected_command_count,
    )


def write_dry_run_test_runner_plan_receipt_validation(
    validation: DryRunTestRunnerPlanReceiptValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic dry-run test runner plan validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_receipt(**updates: Any) -> dict[str, Any]:
    """Return the default example with nested updates for tests."""

    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default dry-run test runner receipt", [])
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


def _validate_sources() -> list[str]:
    source_validation = validate_agentic_service_harness_approved_branch_workspace_creation_preflight()
    if source_validation.ok:
        return []
    return (
        f"source approved_branch_workspace_creation_preflight invalid: {error}"
        for error in source_validation.errors
    )


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    _check_value(payload, ("report_id",), EXPECTED_REPORT_ID, errors, label)
    _check_value(payload, ("solver_outcome",), "SolvedVerified", errors, label)
    _check_value(payload, ("plan_status",), "AwaitingEvidence", errors, label)
    _validate_source_refs(payload, errors, label)
    _validate_scope(payload, errors, label)
    _validate_test_plan(payload, errors, label)
    _validate_authority_denials(payload, errors, label)
    _validate_required_evidence(payload, errors, label)
    _validate_receipt_refs(payload, errors, label)
    _validate_boolean_flags(payload, errors, label)
    _scan_forbidden_text(payload, errors, label)
    _validate_next_action(payload, errors, label)


def _validate_source_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    refs = payload.get("source_contract_refs")
    if not isinstance(refs, list):
        errors.append(f"{label}: source_contract_refs must be a list")
        return
    missing = sorted(set(REQUIRED_SOURCE_REFS) - {str(ref) for ref in refs})
    if missing:
        errors.append(f"{label}: missing source_contract_refs: {', '.join(missing)}")


def _validate_scope(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(payload.get("scope"))
    _check_value(scope, ("repository_connection_id",), EXPECTED_REPOSITORY_CONNECTION_ID, errors, label)
    _check_value(scope, ("repository_slug",), EXPECTED_REPOSITORY_SLUG, errors, label)
    _check_value(
        scope,
        ("foundation_phase",),
        "foundation_dry_run_test_runner_plan_receipt",
        errors,
        label,
    )
    _check_value(scope, ("approved_branch_workspace_preflight_id",), "gate.branchwrite", errors, label)


def _validate_test_plan(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    test_plan = _mapping(payload.get("test_plan"))
    _check_value(test_plan, ("plan_id",), EXPECTED_PLAN_ID, errors, label)
    _check_value(test_plan, ("execution_mode",), EXPECTED_EXECUTION_MODE, errors, label)
    _require_refs(
        test_plan.get("selection_reason_refs"),
        REQUIRED_SELECTION_REASON_REFS,
        f"{label}: test_plan.selection_reason_refs",
        errors,
    )
    commands = test_plan.get("selected_commands")
    if not isinstance(commands, list):
        errors.append(f"{label}: test_plan.selected_commands must be a list")
        return
    observed_commands = [str(_mapping(command).get("command")) for command in commands]
    if tuple(observed_commands) != ALLOWED_COMMANDS:
        errors.append(f"{label}: test_plan.selected_commands must match the allowlisted command order")
    command_ids = [str(_mapping(command).get("command_id")) for command in commands]
    if len(command_ids) != len(set(command_ids)):
        errors.append(f"{label}: test_plan.selected_commands command_id values must be unique")
    for command in commands:
        command_payload = _mapping(command)
        command_text = command_payload.get("command")
        if command_text not in ALLOWED_COMMANDS:
            errors.append(f"{label}: disallowed selected command: {command_text}")
        if command_payload.get("expected_result") != "planned_only_no_result_claim":
            errors.append(f"{label}: selected command expected_result must deny result claims")
        if command_payload.get("command_class") == "pytest" and command_payload.get("path_scope") != "tests_only":
            errors.append(f"{label}: pytest command must use tests_only path_scope")


def _validate_authority_denials(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    denials = _mapping(payload.get("authority_denials"))
    if set(denials) != set(REQUIRED_AUTHORITY_DENIAL_KEYS):
        errors.append(f"{label}: authority_denials must contain the expected denial keys")


def _validate_required_evidence(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    required_evidence = _mapping(payload.get("required_evidence"))
    _require_refs(
        required_evidence.get("must_have_before_command_execution"),
        REQUIRED_BEFORE_COMMAND_EXECUTION_REFS,
        f"{label}: required_evidence.must_have_before_command_execution",
        errors,
    )
    _require_refs(
        required_evidence.get("must_have_before_test_result_claim"),
        REQUIRED_BEFORE_RESULT_CLAIM_REFS,
        f"{label}: required_evidence.must_have_before_test_result_claim",
        errors,
    )
    _require_refs(
        required_evidence.get("must_have_before_receipt_append"),
        REQUIRED_BEFORE_RECEIPT_APPEND_REFS,
        f"{label}: required_evidence.must_have_before_receipt_append",
        errors,
    )


def _validate_receipt_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_refs = _mapping(payload.get("receipt_refs"))
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"{label}: receipt_refs.{key} must be {expected_value}")


def _validate_boolean_flags(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
        key = path[-1] if path else ""
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {'.'.join(path)} must be false")
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {'.'.join(path)} must be true")


def _scan_forbidden_text(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path in _walk_paths(payload):
        key = path[-1] if path else ""
        normalized_key = key.lower()
        if key not in ALLOWED_SECRET_KEYS:
            for token in FORBIDDEN_SECRET_KEY_TOKENS:
                if token in normalized_key:
                    errors.append(f"{label}: forbidden secret-bearing key {'.'.join(path)}")
    for path, value in _walk(payload):
        if isinstance(value, str):
            if MUTATION_ROUTE_PATTERN.search(value):
                errors.append(f"{label}: mutation route string at {'.'.join(path)}")
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {'.'.join(path)}")


def _validate_next_action(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = payload.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be a string")
        return
    for phrase in (
        "task record write UAO admission preflight",
        "test command execution",
        "blocked",
        "terminal closure",
    ):
        if phrase not in next_action:
            errors.append(f"{label}: next_action must mention {phrase}")


def _require_refs(
    actual: object,
    required: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(actual, list):
        errors.append(f"{label} must be a list")
        return
    actual_set = {str(item) for item in actual}
    for ref in required:
        if ref not in actual_set:
            errors.append(f"{label} missing required ref {ref}")


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


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _walk(value: object, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], object]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk(child, (*path, str(key)))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, (*path, str(index)))
    else:
        yield path, value


def _walk_paths(value: object, path: tuple[str, ...] = ()) -> Iterable[tuple[str, ...]]:
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
    """Run dry-run test runner plan receipt validation."""

    args = build_arg_parser().parse_args(argv)
    example_paths = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_dry_run_test_runner_plan_receipt(
        schema_path=args.schema,
        example_paths=example_paths,
    )
    write_dry_run_test_runner_plan_receipt_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS DRY-RUN TEST RUNNER PLAN RECEIPT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS DRY-RUN TEST RUNNER PLAN RECEIPT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
