#!/usr/bin/env python3
"""Validate Agentic Service Harness workspace sandbox preflight.

Purpose: prove a future temporary branch workspace can be preflighted against
the existing harness sandbox contract without creating a branch, writing files,
executing commands, collecting approval, or claiming closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_workspace_sandbox_preflight.schema.json,
examples/agentic_service_harness_workspace_sandbox_preflight.foundation.json,
scripts.validate_agentic_service_harness_contract, and scripts.validate_schemas.
Invariants:
  - The preflight binds to the branch-write-awaiting-approval fixture.
  - Command allowlist, path allowlist, timeout, network, redaction, production
    mutation denial, and cleanup receipt ref match the source sandbox.
  - Branch creation, workspace writes, command execution, cleanup execution,
    external effects, secrets, approval grant, and terminal closure fail closed.
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

from scripts.validate_agentic_service_harness_contract import (  # noqa: E402
    DEFAULT_SCHEMA as DEFAULT_SOURCE_CONTRACT_SCHEMA,
    validate_agentic_service_harness_contract,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_workspace_sandbox_preflight.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_workspace_sandbox_preflight.foundation.json",
)
DEFAULT_SOURCE_CONTRACT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness.branch_write_awaiting_approval.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_workspace_sandbox_preflight_validation.json"
)
EXPECTED_SOURCE_CONTRACT_REF = "examples/agentic_service_harness.branch_write_awaiting_approval.json"
EXPECTED_PROJECT_ID = "project.foundation"
EXPECTED_TASK_ID = "task.branchwrite"
EXPECTED_RUN_ID = "run.branchwrite"
EXPECTED_SANDBOX_ID = "sandbox.branchwrite"
EXPECTED_APPROVAL_GATE_ID = "gate.branchwrite"
EXPECTED_PREFLIGHT_ID = "workspace-sandbox-preflight-foundation"
EXPECTED_PREFLIGHT_MODE = "PREFLIGHT_ONLY"
EXPECTED_WORKSPACE_INTENT = "temporary_branch_workspace"
EXPECTED_SOURCE_SANDBOX_REF = "sandbox://agentic-service-harness/sandbox.branchwrite"
REQUIRED_FORBIDDEN_ACTION_CLASSES = (
    "create_branch",
    "write_files",
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
REQUIRED_SOURCE_REFS = (
    EXPECTED_SOURCE_CONTRACT_REF,
    "schemas/agentic_service_harness.schema.json",
    "scripts/validate_agentic_service_harness_contract.py",
)
REQUIRED_GATE_REFS = (
    "gate://harness/no-branch-creation",
    "gate://harness/no-workspace-write",
    "gate://harness/no-command-execution",
    "gate://harness/no-cleanup-execution",
    "gate://harness/no-secret-serialization",
    "gate://harness/terminal-closure-denied",
)
REQUIRED_PREFLIGHT_OBLIGATIONS = (
    "obligation://bind-command-allowlist",
    "obligation://bind-path-allowlist",
    "obligation://bind-timeout-budget",
    "obligation://deny-network-access",
    "obligation://require-cleanup-receipt",
    "obligation://deny-workspace-effects",
)
REQUIRED_VALIDATION_REFS = (
    "scripts/validate_agentic_service_harness_workspace_sandbox_preflight.py",
    "scripts/validate_agentic_service_harness_contract.py",
)
REQUIRED_CLEANUP_REFS = (
    "evidence://workspace-path-confinement",
    "evidence://cleanup-receipt-emission",
    "evidence://operator-approval-for-branch-write",
    "evidence://effect-reconciliation-before-terminal-closure",
)
REQUIRED_CLEANUP_BLOCKERS = (
    "blocked://workspace/write-authority-not-granted",
    "blocked://cleanup/execution-not-admitted",
    "blocked://operator-approval/not-collected",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_RECEIPT_REFS = {
    "workspace_sandbox_preflight_schema": (
        "schemas/agentic_service_harness_workspace_sandbox_preflight.schema.json"
    ),
    "agentic_service_harness_schema": "schemas/agentic_service_harness.schema.json",
    "source_contract_example": EXPECTED_SOURCE_CONTRACT_REF,
}
REQUIRED_FALSE_FLAGS = (
    "approval_collected",
    "authority_granted",
    "branch_workspace_created",
    "workspace_write_enabled",
    "external_adapter_integrated",
    "secret_values_serialized",
    "production_mutation_allowed",
    "cleanup_receipt_emitted",
    "cleanup_execution_allowed",
    "branch_created",
    "files_written",
    "commands_executed",
    "tests_executed",
    "cleanup_executed",
    "adapter_executed",
    "pull_request_opened",
    "runtime_state_written",
    "receipt_store_appended",
    "connector_calls_observed",
    "external_effects_observed",
    "terminal_closure",
    "success_claim_allowed",
)
REQUIRED_TRUE_FLAGS = (
    "approval_required",
    "preflight_only",
    "secret_redaction_required",
    "cleanup_receipt_required",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "secret_redaction_required",
    "secret_mutation",
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
class WorkspaceSandboxPreflightValidation:
    """Schema and semantic validation report for workspace sandbox preflight."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_contract_ref: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_workspace_sandbox_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_contract_schema_path: Path = DEFAULT_SOURCE_CONTRACT_SCHEMA,
    source_contract_example_paths: Sequence[Path] = DEFAULT_SOURCE_CONTRACT_EXAMPLES,
) -> WorkspaceSandboxPreflightValidation:
    """Validate workspace sandbox preflight examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "workspace sandbox preflight schema", errors)
    source_validation = validate_agentic_service_harness_contract(
        schema_path=source_contract_schema_path,
    )
    if not source_validation.ok:
        errors.extend(f"source contract: {error}" for error in source_validation.errors)
    source_contract = _load_json_object(
        source_contract_example_paths[0],
        "branch-write source contract",
        errors,
    )
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"workspace sandbox preflight example {_path_label(example_path)}",
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
        _validate_preflight_semantics(example, source_contract, errors, _path_label(example_path))
    return WorkspaceSandboxPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_contract_ref=EXPECTED_SOURCE_CONTRACT_REF,
    )


def write_workspace_sandbox_preflight_validation(
    validation: WorkspaceSandboxPreflightValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic workspace sandbox preflight validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_preflight(**updates: Any) -> dict[str, Any]:
    """Return the default example with nested updates for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default preflight example", [])
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
    source_contract: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(preflight, ("source_contract_ref",), EXPECTED_SOURCE_CONTRACT_REF, errors, label)
    source_sandbox = _first_matching(
        source_contract.get("workspace_sandboxes", ()),
        "sandbox_id",
        EXPECTED_SANDBOX_ID,
    )
    source_run = _first_matching(source_contract.get("agent_runs", ()), "run_id", EXPECTED_RUN_ID)
    source_task = _first_matching(source_contract.get("agent_tasks", ()), "task_id", EXPECTED_TASK_ID)
    source_gate = _first_matching(
        source_contract.get("approval_gates", ()),
        "gate_id",
        EXPECTED_APPROVAL_GATE_ID,
    )
    if source_sandbox is None:
        errors.append(f"{label}: source contract missing sandbox {EXPECTED_SANDBOX_ID}")
        return
    if source_run is None:
        errors.append(f"{label}: source contract missing run {EXPECTED_RUN_ID}")
        return
    if source_task is None:
        errors.append(f"{label}: source contract missing task {EXPECTED_TASK_ID}")
        return
    if source_gate is None:
        errors.append(f"{label}: source contract missing gate {EXPECTED_APPROVAL_GATE_ID}")
        return
    _validate_scope(preflight, source_task, source_run, source_gate, errors, label)
    _validate_contract(preflight, errors, label)
    _validate_sandbox_controls(preflight, source_sandbox, errors, label)
    _validate_cleanup_gate(preflight, errors, label)
    _validate_required_refs(preflight, errors, label)
    _validate_flags(preflight, errors, label)
    _scan_forbidden_text(preflight, errors, label)


def _validate_scope(
    preflight: Mapping[str, Any],
    source_task: Mapping[str, Any],
    source_run: Mapping[str, Any],
    source_gate: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping(preflight.get("scope"))
    _check_value(scope, ("project_id",), source_task.get("project_id"), errors, label)
    _check_value(scope, ("task_id",), source_task.get("task_id"), errors, label)
    _check_value(scope, ("run_id",), source_run.get("run_id"), errors, label)
    _check_value(scope, ("sandbox_id",), source_run.get("sandbox_id"), errors, label)
    _check_value(scope, ("approval_gate_id",), source_gate.get("gate_id"), errors, label)
    _check_value(scope, ("mode",), source_task.get("mode"), errors, label)
    _check_value(scope, ("approval_required",), True, errors, label)
    _check_value(scope, ("approval_collected",), False, errors, label)
    _check_value(scope, ("authority_granted",), False, errors, label)
    if source_gate.get("status") != "pending":
        errors.append(f"{label}: source approval gate must remain pending")


def _validate_contract(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    contract = _mapping(preflight.get("workspace_preflight_contract"))
    _check_value(contract, ("preflight_id",), EXPECTED_PREFLIGHT_ID, errors, label)
    _check_value(contract, ("preflight_mode",), EXPECTED_PREFLIGHT_MODE, errors, label)
    _check_value(contract, ("workspace_intent",), EXPECTED_WORKSPACE_INTENT, errors, label)
    _check_value(contract, ("source_sandbox_ref",), EXPECTED_SOURCE_SANDBOX_REF, errors, label)
    if contract.get("allowed_action_classes") != ["preflight"]:
        errors.append(f"{label}: workspace_preflight_contract.allowed_action_classes must be ['preflight']")
    _require_all_refs(
        contract.get("forbidden_action_classes", ()),
        REQUIRED_FORBIDDEN_ACTION_CLASSES,
        "workspace_preflight_contract.forbidden_action_classes",
        errors,
        label,
    )
    _require_all_refs(
        contract.get("required_source_refs", ()),
        REQUIRED_SOURCE_REFS,
        "workspace_preflight_contract.required_source_refs",
        errors,
        label,
    )
    _require_all_refs(
        contract.get("required_gate_refs", ()),
        REQUIRED_GATE_REFS,
        "workspace_preflight_contract.required_gate_refs",
        errors,
        label,
    )
    _require_all_refs(
        contract.get("preflight_obligations_checked", ()),
        REQUIRED_PREFLIGHT_OBLIGATIONS,
        "workspace_preflight_contract.preflight_obligations_checked",
        errors,
        label,
    )
    _require_all_refs(
        contract.get("validation_refs", ()),
        REQUIRED_VALIDATION_REFS,
        "workspace_preflight_contract.validation_refs",
        errors,
        label,
    )


def _validate_sandbox_controls(
    preflight: Mapping[str, Any],
    source_sandbox: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    controls = _mapping(preflight.get("sandbox_controls"))
    for field in (
        "command_allowlist",
        "path_allowlist",
        "timeout_seconds",
        "network_policy",
        "secret_redaction_required",
        "production_mutation_allowed",
        "cleanup_receipt_ref",
    ):
        if controls.get(field) != source_sandbox.get(field):
            errors.append(f"{label}: sandbox_controls.{field} must match source sandbox")
    if controls.get("network_policy") != "none":
        errors.append(f"{label}: sandbox_controls.network_policy must stay none")


def _validate_cleanup_gate(preflight: Mapping[str, Any], errors: list[str], label: str) -> None:
    gate = _mapping(preflight.get("cleanup_gate"))
    _require_all_refs(
        gate.get("required_before_workspace_write_refs", ()),
        REQUIRED_CLEANUP_REFS,
        "cleanup_gate.required_before_workspace_write_refs",
        errors,
        label,
    )
    _require_all_refs(
        gate.get("blocked_reason_refs", ()),
        REQUIRED_CLEANUP_BLOCKERS,
        "cleanup_gate.blocked_reason_refs",
        errors,
        label,
    )


def _validate_required_refs(
    preflight: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    receipt_refs = _mapping(preflight.get("receipt_refs"))
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"{label}: receipt_refs.{key} must be {expected_value}")
    cleanup_ref = receipt_refs.get("cleanup_receipt_ref")
    controls = _mapping(preflight.get("sandbox_controls"))
    if cleanup_ref != controls.get("cleanup_receipt_ref"):
        errors.append(f"{label}: receipt_refs.cleanup_receipt_ref must match sandbox cleanup receipt")


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


def _first_matching(values: Any, key: str, expected_value: str) -> Mapping[str, Any] | None:
    if not isinstance(values, list):
        return None
    for value in values:
        if isinstance(value, Mapping) and value.get(key) == expected_value:
            return value
    return None


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


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
    """Run workspace sandbox preflight validation."""
    args = build_arg_parser().parse_args(argv)
    examples = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_workspace_sandbox_preflight(
        schema_path=args.schema,
        example_paths=examples,
    )
    write_workspace_sandbox_preflight_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS WORKSPACE SANDBOX PREFLIGHT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS WORKSPACE SANDBOX PREFLIGHT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 1


if __name__ == "__main__":
    raise SystemExit(main())
