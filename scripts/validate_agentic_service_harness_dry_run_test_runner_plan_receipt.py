#!/usr/bin/env python3
"""Validate Agentic Service Harness dry-run test runner plan receipt.

Purpose: prove harness-selected test commands are recorded as a plan receipt
without admitting command execution, test execution, raw output capture,
receipt-store append, adapter execution, filesystem writes, or terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_dry_run_test_runner_plan_receipt.schema.json,
examples/agentic_service_harness_dry_run_test_runner_plan_receipt.foundation.json,
and approved branch workspace creation preflight validation.
Invariants:
  - Source preflight validators pass first.
  - Selected commands are contract entries, not executed commands.
  - Raw output, environment values, secrets, receipt append, and terminal closure
    fail closed.
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
EXPECTED_ACTION = "plan_dry_run_test_runner"
EXPECTED_ROUTE_REF = "route://harness/test-runner/dry-run/not-admitted"
EXPECTED_RUNNER_MODE = "dry_run_plan_only"
REQUIRED_SOURCE_REFS = (
    "examples/agentic_service_harness_approved_branch_workspace_creation_preflight.foundation.json",
    "examples/agentic_service_harness_task_creation_admission_preflight.foundation.json",
    "schemas/agentic_service_harness.schema.json",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
REQUIRED_BEFORE_EXECUTION_REFS = (
    "approval://operator/test-runner-execution",
    "evidence://approved-branch-workspace-creation-preflight",
    "evidence://uao-test-runner-admission",
    "evidence://redaction-policy-for-command-output",
    "evidence://receipt-store-write-path",
)
REQUIRED_BLOCKERS = (
    "blocked://operator-approval/not-collected",
    "blocked://uao-admission/not-collected",
    "blocked://test-execution/not-admitted",
    "blocked://raw-output-capture/not-admitted",
    "blocked://receipt-store/append-not-admitted",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_NEXT_EVIDENCE = (
    "evidence://task-record-write-uao-admission",
    "evidence://receipt-store-append-admission",
    "approval://test-runner-execution/operator-decision",
)
REQUIRED_FALSE_FLAGS = (
    "command_execution_enabled",
    "test_execution_enabled",
    "raw_output_serialized",
    "receipt_store_append_enabled",
    "secret_values_serialized",
    "operator_approval_collected",
    "uao_admission_collected",
    "test_execution_admitted",
    "execution_admitted",
    "raw_output_capture_allowed",
    "raw_stdout_stored",
    "raw_stderr_stored",
    "environment_values_stored",
    "adapter_execution_enabled",
    "connector_calls_enabled",
    "filesystem_write_enabled",
    "branch_write_enabled",
    "runtime_state_write_enabled",
    "mutation_route_enabled",
    "terminal_closure",
    "default_high_risk_authority",
)
REQUIRED_TRUE_FLAGS = (
    "dry_run_only",
    "read_only_sources",
    "approved_branch_workspace_preflight_valid",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
)
ALLOWED_SECRET_KEYS = {"secret_values_serialized", "secret_patterns_blocked"}
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
COMMAND_ALLOWLIST_PATTERN = re.compile(
    r"^python (?:-m pytest tests/[A-Za-z0-9_./-]+\.py -q|scripts/[A-Za-z0-9_./-]+\.py --strict)$"
)


@dataclass(frozen=True, slots=True)
class DryRunTestRunnerPlanReceiptValidation:
    """Validation report for dry-run test runner plan receipt."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_validators_ok: bool

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
    schema = _load_json_object(schema_path, "dry-run test runner plan schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"dry-run test runner plan example {_path_label(example_path)}",
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
        _validate_semantics(example, errors, _path_label(example_path))

    return DryRunTestRunnerPlanReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_validators_ok=not source_errors,
    )


def write_dry_run_test_runner_plan_receipt_validation(
    validation: DryRunTestRunnerPlanReceiptValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic dry-run test runner plan validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_receipt(**changes: Any) -> dict[str, Any]:
    """Return a mutated copy of the default fixture for tests."""

    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default fixture", [])
    mutated = deepcopy(payload)
    for dotted_path, value in changes.items():
        cursor: dict[str, Any] = mutated
        path_parts = dotted_path.split("__")
        for key in path_parts[:-1]:
            next_cursor = cursor[key]
            if not isinstance(next_cursor, dict):
                raise TypeError(f"cannot mutate non-object path component {key}")
            cursor = next_cursor
        cursor[path_parts[-1]] = value
    return mutated


def _validate_sources() -> list[str]:
    source_validation = validate_agentic_service_harness_approved_branch_workspace_creation_preflight()
    if source_validation.ok:
        return []
    return [
        "source approved_branch_workspace_creation_preflight invalid: " + error
        for error in source_validation.errors
    ]


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    if payload.get("report_id") != EXPECTED_REPORT_ID:
        errors.append(f"{label}: report_id must be {EXPECTED_REPORT_ID}")
    _validate_source_refs(payload, errors, label)
    _validate_reference_integrity(payload, errors, label)
    _validate_ref_sets(payload, errors, label)
    _validate_selected_commands(payload, errors, label)
    _validate_redaction_policy(payload, errors, label)
    _validate_boolean_flags(payload, errors, label)
    _validate_secret_surface(payload, errors, label)
    _validate_no_mutation_routes(payload, errors, label)
    _validate_next_action(payload, errors, label)


def _validate_source_refs(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    refs = payload.get("source_contract_refs")
    if not isinstance(refs, list):
        errors.append(f"{label}: source_contract_refs must be a list")
        return
    missing = sorted(set(REQUIRED_SOURCE_REFS) - {str(ref) for ref in refs})
    if missing:
        errors.append(f"{label}: missing source_contract_refs: {', '.join(missing)}")


def _validate_reference_integrity(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _mapping(payload.get("scope"))
    plan = _mapping(payload.get("test_runner_plan"))
    if scope.get("repository_slug") != "tamirat-wubie/mullu-control-plane":
        errors.append(f"{label}: scope.repository_slug must bind the repository")
    if scope.get("foundation_phase") != "foundation_dry_run_test_runner_plan_receipt":
        errors.append(f"{label}: scope.foundation_phase must bind dry-run plan receipt")
    if plan.get("requested_action") != EXPECTED_ACTION:
        errors.append(f"{label}: test_runner_plan.requested_action must be {EXPECTED_ACTION}")
    if plan.get("requested_route_ref") != EXPECTED_ROUTE_REF:
        errors.append(f"{label}: test_runner_plan.requested_route_ref must remain not-admitted")
    if plan.get("runner_mode") != EXPECTED_RUNNER_MODE:
        errors.append(f"{label}: test_runner_plan.runner_mode must be {EXPECTED_RUNNER_MODE}")


def _validate_ref_sets(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    plan = _mapping(payload.get("test_runner_plan"))
    _require_refs(
        plan.get("required_before_execution_refs"),
        REQUIRED_BEFORE_EXECUTION_REFS,
        f"{label}: test_runner_plan.required_before_execution_refs",
        errors,
    )
    _require_refs(
        plan.get("blocked_reason_refs"),
        REQUIRED_BLOCKERS,
        f"{label}: test_runner_plan.blocked_reason_refs",
        errors,
    )
    _require_refs(
        plan.get("next_required_evidence_refs"),
        REQUIRED_NEXT_EVIDENCE,
        f"{label}: test_runner_plan.next_required_evidence_refs",
        errors,
    )


def _validate_selected_commands(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    commands = _mapping(payload.get("test_runner_plan")).get("selected_commands")
    if not isinstance(commands, list) or len(commands) < 2:
        errors.append(f"{label}: selected_commands must contain at least two planned commands")
        return
    command_ids: set[str] = set()
    for index, command_plan in enumerate(commands):
        if not isinstance(command_plan, Mapping):
            errors.append(f"{label}: selected_commands[{index}] must be an object")
            continue
        command_id = str(command_plan.get("command_id", ""))
        command = str(command_plan.get("command", ""))
        if command_id in command_ids:
            errors.append(f"{label}: duplicate command_id {command_id}")
        command_ids.add(command_id)
        if not COMMAND_ALLOWLIST_PATTERN.match(command):
            errors.append(f"{label}: selected_commands[{index}].command is not allowlisted")
        if command_plan.get("execution_admitted") is not False:
            errors.append(f"{label}: selected_commands[{index}].execution_admitted must be false")
        if command_plan.get("raw_output_capture_allowed") is not False:
            errors.append(
                f"{label}: selected_commands[{index}].raw_output_capture_allowed must be false"
            )


def _validate_redaction_policy(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    redaction = _mapping(payload.get("redaction_policy"))
    secret_patterns = redaction.get("secret_patterns_blocked")
    if not isinstance(secret_patterns, list) or len(secret_patterns) < 4:
        errors.append(f"{label}: redaction_policy.secret_patterns_blocked is incomplete")
    allowed_fields = redaction.get("allowed_receipt_fields")
    expected_fields = {
        "command_id",
        "command",
        "purpose",
        "allowlist_ref",
        "expected_evidence_ref",
        "timeout_seconds",
    }
    if not isinstance(allowed_fields, list) or set(allowed_fields) != expected_fields:
        errors.append(f"{label}: redaction_policy.allowed_receipt_fields must be exact")


def _validate_boolean_flags(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk_values(payload):
        key = path[-1] if path else ""
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {'.'.join(path)} must be false")
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {'.'.join(path)} must be true")


def _validate_secret_surface(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk_values(payload):
        key = path[-1] if path else ""
        lowered_key = key.lower()
        if (
            any(token in lowered_key for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"{label}: forbidden secret-bearing key {'.'.join(path)}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {'.'.join(path)}")


def _validate_no_mutation_routes(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk_values(payload):
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {'.'.join(path)}")


def _validate_next_action(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    next_action = payload.get("next_action")
    if not isinstance(next_action, str):
        errors.append(f"{label}: next_action must be a string")
        return
    for phrase in (
        "task record write UAO admission preflight",
        "test execution",
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


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label}: missing file {path}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label}: invalid JSON at line {exc.lineno}: {exc.msg}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label}: expected JSON object")
        return {}
    return payload


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _walk_values(value: object, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], object]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield from _walk_values(child, (*path, str(key)))
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk_values(child, (*path, str(index)))
        return
    yield path, value


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse dry-run test runner plan validation arguments."""

    parser = argparse.ArgumentParser(
        description="Validate the dry-run test runner plan receipt contract."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", action="append", type=Path, dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true", help="Print JSON validation output.")
    parser.add_argument("--strict", action="store_true", help="Return non-zero on validation failure.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    """Run dry-run test runner plan receipt validation."""

    args = parse_args(argv)
    example_paths = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_dry_run_test_runner_plan_receipt(
        schema_path=args.schema,
        example_paths=example_paths,
    )
    write_dry_run_test_runner_plan_receipt_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS DRY-RUN TEST RUNNER PLAN RECEIPT VALID")
    else:
        print("AGENTIC SERVICE HARNESS DRY-RUN TEST RUNNER PLAN RECEIPT INVALID")
        for error in validation.errors:
            print(f"- {error}")
    return 1 if args.strict and not validation.ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
