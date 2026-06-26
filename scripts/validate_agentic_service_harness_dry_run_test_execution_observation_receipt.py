#!/usr/bin/env python3
"""Validate dry-run test execution observation receipt.

Purpose: prove bounded dry-run test execution can be observed without granting
executed-test receipt admission, receipt append, filesystem-write authority, or
terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_dry_run_test_execution_observation_receipt.schema.json,
examples/agentic_service_harness_dry_run_test_execution_observation_receipt.foundation.json,
scripts.validate_agentic_service_harness_dry_run_test_runner_plan_receipt,
scripts.validate_agentic_service_harness_approved_branch_workspace_creation_observation_receipt,
scripts.validate_agentic_service_harness_executed_test_receipt_admission_preflight,
and scripts.validate_schemas.
Invariants:
  - Source dry-run plan, workspace observation, and executed-test admission
    preflight validate before this receipt is accepted.
  - Every selected command from the dry-run plan has one redacted observation.
  - Raw output, receipt append, filesystem-write authority, adapter execution,
    connector calls, PR creation, secrets, and terminal closure remain denied.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_approved_branch_workspace_creation_observation_receipt import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_WORKSPACE_OBSERVATION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_WORKSPACE_OBSERVATION_SCHEMA,
    validate_agentic_service_harness_approved_branch_workspace_creation_observation_receipt,
)
from scripts.validate_agentic_service_harness_dry_run_test_runner_plan_receipt import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_DRY_RUN_PLAN_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_DRY_RUN_PLAN_SCHEMA,
    validate_agentic_service_harness_dry_run_test_runner_plan_receipt,
)
from scripts.validate_agentic_service_harness_executed_test_receipt_admission_preflight import (  # noqa: E402
    DEFAULT_EXAMPLES as DEFAULT_EXECUTED_TEST_ADMISSION_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_EXECUTED_TEST_ADMISSION_SCHEMA,
    validate_agentic_service_harness_executed_test_receipt_admission_preflight,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT
    / "schemas"
    / "agentic_service_harness_dry_run_test_execution_observation_receipt.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT
    / "examples"
    / "agentic_service_harness_dry_run_test_execution_observation_receipt.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_dry_run_test_execution_observation_receipt_validation.json"
)
EXPECTED_RECEIPT_ID = "agentic_service_harness_dry_run_test_execution_observation_receipt"
EXPECTED_REPOSITORY_CONNECTION_ID = "repo-mullu-control-plane"
EXPECTED_REPOSITORY_SLUG = "tamirat-wubie/mullu-control-plane"
EXPECTED_BRANCH_NAME = "codex/harness-dry-run-test-execution-observation-20260626"
EXPECTED_PLAN_ID = "dry-run-test-runner-plan-foundation"
EXPECTED_SOURCE_REFS = {
    "dry_run_test_runner_plan_receipt": (
        "examples/agentic_service_harness_dry_run_test_runner_plan_receipt.foundation.json"
    ),
    "approved_branch_workspace_creation_observation_receipt": (
        "examples/agentic_service_harness_approved_branch_workspace_creation_observation_receipt.foundation.json"
    ),
    "executed_test_receipt_admission_preflight": (
        "examples/agentic_service_harness_executed_test_receipt_admission_preflight.foundation.json"
    ),
}
REQUIRED_NEXT_REFS = (
    "evidence://filesystem-write-rollback-plan",
    "evidence://workspace-write-authority",
    "evidence://non-empty-diff-admission-preflight",
    "evidence://redaction-policy-for-file-change-collection",
    "evidence://receipt-store-append-preflight",
    "evidence://test-output-captured-with-redaction",
    "evidence://receipt-redaction-policy",
    "evidence://receipt-append-rollback-plan",
    "evidence://receipt-store-write-path",
    "evidence://receipt-append-idempotency-key",
    "evidence://receipt-store-append-operator-approval",
    "evidence://github-pr-admission-preflight",
    "evidence://branch-write-authority-binding",
    "evidence://effect-reconciliation-before-pr",
    "evidence://cleanup-receipt-after-workspace-use",
    "evidence://effect-reconciliation-before-terminal-closure",
    "evidence://terminal-closure-certificate-candidate",
)
REQUIRED_RECEIPT_REFS = {
    "dry_run_test_execution_observation_schema": (
        "schemas/agentic_service_harness_dry_run_test_execution_observation_receipt.schema.json"
    ),
    "dry_run_test_execution_observation_example": (
        "examples/agentic_service_harness_dry_run_test_execution_observation_receipt.foundation.json"
    ),
    "dry_run_test_runner_plan_schema": (
        "schemas/agentic_service_harness_dry_run_test_runner_plan_receipt.schema.json"
    ),
    "approved_branch_workspace_creation_observation_schema": (
        "schemas/agentic_service_harness_approved_branch_workspace_creation_observation_receipt.schema.json"
    ),
    "executed_test_receipt_admission_preflight_schema": (
        "schemas/agentic_service_harness_executed_test_receipt_admission_preflight.schema.json"
    ),
}
REQUIRED_TRUE_FLAGS = (
    "observation_only",
    "dry_run_execution_observed",
    "all_exit_codes_zero",
    "output_redaction_applied",
    "dry_run_commands_observed",
    "receipt_is_not_terminal_closure",
    "terminal_closure_required",
    "required_for_closure",
)
REQUIRED_FALSE_FLAGS = (
    "executed_test_receipt_admitted",
    "receipt_store_append_enabled",
    "filesystem_write_authority_granted",
    "secret_values_serialized",
    "raw_stdout_serialized",
    "raw_stderr_serialized",
    "coverage_claimed",
    "test_result_summary_claimed",
    "raw_output_stored",
    "receipt_store_appended",
    "branch_pushed",
    "pull_request_opened",
    "adapter_executed",
    "connector_called",
    "mutation_route_admitted",
    "terminal_closure",
    "executed_test_receipt_admission_enabled",
    "filesystem_write_enabled",
    "branch_push_enabled",
    "pull_request_creation_enabled",
    "adapter_execution_enabled",
    "connector_calls_enabled",
    "runtime_state_write_enabled",
    "mutation_route_enabled",
    "raw_output_storage_enabled",
    "coverage_claim_enabled",
    "default_high_risk_authority",
)
REQUIRED_NEXT_ACTION_TERMS = (
    "filesystem write admission",
    "rollback",
    "workspace-write authority",
    "redaction",
    "non-empty diff admission",
    "receipt-store write path",
    "cleanup evidence",
    "adapter execution",
    "receipt append",
    "terminal closure",
)
ALLOWED_SECRET_KEYS = {"secret_values_serialized"}
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
class DryRunTestExecutionObservationReceiptValidation:
    """Validation report for dry-run test execution observation receipt."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_plan_ok: bool
    source_workspace_observation_ok: bool
    source_executed_test_admission_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_dry_run_test_execution_observation_receipt(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    dry_run_plan_schema_path: Path = DEFAULT_DRY_RUN_PLAN_SCHEMA,
    dry_run_plan_example_paths: Sequence[Path] = DEFAULT_DRY_RUN_PLAN_EXAMPLES,
    workspace_observation_schema_path: Path = DEFAULT_WORKSPACE_OBSERVATION_SCHEMA,
    workspace_observation_example_paths: Sequence[Path] = DEFAULT_WORKSPACE_OBSERVATION_EXAMPLES,
    executed_test_admission_schema_path: Path = DEFAULT_EXECUTED_TEST_ADMISSION_SCHEMA,
    executed_test_admission_example_paths: Sequence[Path] = DEFAULT_EXECUTED_TEST_ADMISSION_EXAMPLES,
) -> DryRunTestExecutionObservationReceiptValidation:
    """Validate dry-run test execution observation receipt examples."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "dry-run test execution observation schema", errors)

    plan_validation = validate_agentic_service_harness_dry_run_test_runner_plan_receipt(
        schema_path=dry_run_plan_schema_path,
        example_paths=dry_run_plan_example_paths,
    )
    if not plan_validation.ok:
        errors.extend(f"dry-run test runner plan: {error}" for error in plan_validation.errors)
    workspace_validation = (
        validate_agentic_service_harness_approved_branch_workspace_creation_observation_receipt(
            schema_path=workspace_observation_schema_path,
            example_paths=workspace_observation_example_paths,
        )
    )
    if not workspace_validation.ok:
        errors.extend(
            f"approved branch workspace observation: {error}"
            for error in workspace_validation.errors
        )
    admission_validation = validate_agentic_service_harness_executed_test_receipt_admission_preflight(
        schema_path=executed_test_admission_schema_path,
        example_paths=executed_test_admission_example_paths,
    )
    if not admission_validation.ok:
        errors.extend(
            f"executed test receipt admission preflight: {error}"
            for error in admission_validation.errors
        )

    dry_run_plan = _load_json_object(
        dry_run_plan_example_paths[0],
        "dry-run test runner plan source",
        errors,
    )
    workspace_observation = _load_json_object(
        workspace_observation_example_paths[0],
        "approved branch workspace observation source",
        errors,
    )
    executed_test_admission = _load_json_object(
        executed_test_admission_example_paths[0],
        "executed test receipt admission preflight source",
        errors,
    )

    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"dry-run test execution observation {_path_label(example_path)}",
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
            dry_run_plan,
            workspace_observation,
            executed_test_admission,
            errors,
            _path_label(example_path),
        )

    return DryRunTestExecutionObservationReceiptValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_plan_ok=plan_validation.ok,
        source_workspace_observation_ok=workspace_validation.ok,
        source_executed_test_admission_ok=admission_validation.ok,
    )


def write_dry_run_test_execution_observation_validation(
    validation: DryRunTestExecutionObservationReceiptValidation,
    output_path: Path = DEFAULT_OUTPUT,
) -> None:
    """Persist validation report for audit inspection."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_mutated_dry_run_test_execution_observation(
    **updates: Any,
) -> dict[str, Any]:
    """Return a mutated default fixture for negative validator tests."""

    payload = _load_json_object(
        DEFAULT_EXAMPLES[0],
        "default dry-run test execution observation fixture",
        [],
    )
    for dotted_key, value in updates.items():
        _set_nested(payload, dotted_key.split("__"), value)
    return payload


def _validate_receipt_semantics(
    payload: Mapping[str, Any],
    dry_run_plan: Mapping[str, Any],
    workspace_observation: Mapping[str, Any],
    executed_test_admission: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if payload.get("receipt_id") != EXPECTED_RECEIPT_ID:
        errors.append(f"{label}: receipt_id must be {EXPECTED_RECEIPT_ID}")
    if payload.get("observation_status") != "dry_run_test_execution_observed_without_receipt_append":
        errors.append(f"{label}: observation_status must record observation without receipt append")

    source_refs = _mapping(payload.get("source_refs"))
    for key, expected in EXPECTED_SOURCE_REFS.items():
        if source_refs.get(key) != expected:
            errors.append(f"{label}: source_refs.{key} must be {expected}")

    scope = _mapping(payload.get("scope"))
    if scope.get("repository_connection_id") != EXPECTED_REPOSITORY_CONNECTION_ID:
        errors.append(f"{label}: repository_connection_id mismatch")
    if scope.get("repository_slug") != EXPECTED_REPOSITORY_SLUG:
        errors.append(f"{label}: repository_slug mismatch")
    if scope.get("branch_name") != EXPECTED_BRANCH_NAME:
        errors.append(f"{label}: branch_name must be {EXPECTED_BRANCH_NAME}")
    if scope.get("foundation_phase") != "foundation_dry_run_test_execution_observation":
        errors.append(f"{label}: foundation_phase mismatch")

    plan_scope = _mapping(dry_run_plan.get("scope"))
    workspace_scope = _mapping(workspace_observation.get("scope"))
    admission_scope = _mapping(executed_test_admission.get("scope"))
    for source_name, source_scope in (
        ("dry_run_plan", plan_scope),
        ("workspace_observation", workspace_scope),
        ("executed_test_admission", admission_scope),
    ):
        if source_scope.get("repository_connection_id") != scope.get("repository_connection_id"):
            errors.append(f"{label}: {source_name} repository_connection_id mismatch")
        if source_scope.get("repository_slug") != scope.get("repository_slug"):
            errors.append(f"{label}: {source_name} repository_slug mismatch")

    observation = _mapping(payload.get("execution_observation"))
    if observation.get("plan_id") != EXPECTED_PLAN_ID:
        errors.append(f"{label}: execution_observation.plan_id mismatch")
    selected_commands = tuple(_mappings(_mapping(dry_run_plan.get("test_plan")).get("selected_commands")))
    observed_commands = tuple(_mappings(observation.get("observed_commands")))
    if observation.get("selected_command_count") != len(selected_commands):
        errors.append(f"{label}: selected_command_count must match dry-run plan")
    if observation.get("observed_command_count") != len(selected_commands):
        errors.append(f"{label}: observed_command_count must match dry-run plan")
    _validate_observed_commands(selected_commands, observed_commands, errors, label)

    _require_refs(
        _strings(observation.get("observation_evidence_refs")),
        (
            "evidence://dry-run-test-execution/all-selected-commands-observed",
            "evidence://dry-run-test-execution/all-exit-codes-zero",
            "evidence://dry-run-test-execution/output-redaction-applied",
            "evidence://dry-run-test-execution/no-raw-output-serialized",
        ),
        errors,
        f"{label}: execution_observation.observation_evidence_refs",
    )
    all_next_refs: list[str] = []
    for refs in _mapping(payload.get("required_next_evidence")).values():
        all_next_refs.extend(_strings(refs))
    _require_refs(all_next_refs, REQUIRED_NEXT_REFS, errors, f"{label}: required_next_evidence")

    receipt_refs = _mapping(payload.get("receipt_refs"))
    for key, expected in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected:
            errors.append(f"{label}: receipt_refs.{key} must be {expected}")

    next_action = str(payload.get("next_action", ""))
    for term in REQUIRED_NEXT_ACTION_TERMS:
        if term not in next_action:
            errors.append(f"{label}: next_action missing term {term}")

    for flag in REQUIRED_TRUE_FLAGS:
        if not _contains_bool(payload, flag, True):
            errors.append(f"{label}: expected true flag {flag}")
    for flag in REQUIRED_FALSE_FLAGS:
        if not _contains_bool(payload, flag, False):
            errors.append(f"{label}: expected false flag {flag}")
    _validate_no_forbidden_payload(payload, errors, label)


def _validate_observed_commands(
    selected_commands: Sequence[Mapping[str, Any]],
    observed_commands: Sequence[Mapping[str, Any]],
    errors: list[str],
    label: str,
) -> None:
    selected_by_id = {str(command.get("command_id")): command for command in selected_commands}
    observed_by_id = {str(command.get("command_id")): command for command in observed_commands}
    if set(selected_by_id) != set(observed_by_id):
        errors.append(f"{label}: observed command ids must match selected command ids")
        return
    for command_id, selected in selected_by_id.items():
        observed = observed_by_id[command_id]
        for field in ("command", "command_class", "path_scope"):
            if observed.get(field) != selected.get(field):
                errors.append(f"{label}: observed command {command_id} {field} mismatch")
        if observed.get("exit_code") != 0:
            errors.append(f"{label}: observed command {command_id} exit_code must be 0")
        if observed.get("raw_output_stored") is not False:
            errors.append(f"{label}: observed command {command_id} raw_output_stored must be false")
        for field in ("duration_ref", "output_digest_ref", "redacted_output_ref"):
            value = observed.get(field)
            if not isinstance(value, str) or not value.startswith("evidence://dry-run-test-execution/"):
                errors.append(f"{label}: observed command {command_id} {field} must be dry-run evidence ref")


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label} load failed: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return payload


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def _strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _require_refs(
    actual_refs: Sequence[str],
    required_refs: Sequence[str],
    errors: list[str],
    label: str,
) -> None:
    actual = set(actual_refs)
    for required_ref in required_refs:
        if required_ref not in actual:
            errors.append(f"{label}: missing {required_ref}")


def _contains_bool(value: Any, key: str, expected: bool) -> bool:
    if isinstance(value, Mapping):
        return any(
            (item_key == key and item_value is expected)
            or _contains_bool(item_value, key, expected)
            for item_key, item_value in value.items()
        )
    if isinstance(value, list):
        return any(_contains_bool(item, key, expected) for item in value)
    return False


def _validate_no_forbidden_payload(value: Any, errors: list[str], label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key).lower()
            if key_text not in ALLOWED_SECRET_KEYS and any(
                token in key_text for token in FORBIDDEN_SECRET_KEY_TOKENS
            ):
                errors.append(f"{label}: forbidden secret-bearing key {key}")
            _validate_no_forbidden_payload(item, errors, label)
        return
    if isinstance(value, list):
        for item in value:
            _validate_no_forbidden_payload(item, errors, label)
        return
    if isinstance(value, str):
        if MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string is forbidden")
        if any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: credential-like value is forbidden")


def _set_nested(payload: dict[str, Any], path: list[str], value: Any) -> None:
    cursor: Any = payload
    for part in path[:-1]:
        if isinstance(cursor, list):
            cursor = cursor[int(part)]
        else:
            cursor = cursor.setdefault(part, {})
    if isinstance(cursor, list):
        cursor[int(path[-1])] = value
    else:
        cursor[path[-1]] = value


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate dry-run test execution observation receipt."
    )
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, action="append", dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    validation = validate_agentic_service_harness_dry_run_test_execution_observation_receipt(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
    )
    write_dry_run_test_execution_observation_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS DRY-RUN TEST EXECUTION OBSERVATION RECEIPT VALID")
    else:
        for error in validation.errors:
            print(f"[FAIL] {error}")
    return 0 if validation.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
