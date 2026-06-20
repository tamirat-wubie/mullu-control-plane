#!/usr/bin/env python3
"""Validate Agentic Service Harness temporary branch workspace preflight.

Purpose: prove the harness can bind a future temporary branch workspace to
path, command, timeout, cleanup, and authority-denial gates without creating a
branch workspace or writing files.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_temporary_branch_workspace_preflight.schema.json,
examples/agentic_service_harness_temporary_branch_workspace_preflight.foundation.json,
examples/agentic_service_harness.branch_write_awaiting_approval.json, and
scripts.validate_schemas.
Invariants:
  - The preflight binds to the branch-write-awaiting-approval harness contract.
  - Branch workspace creation, filesystem writes, PR creation, runtime state
    writes, mutation routes, external adapter execution, and terminal closure
    remain denied.
  - Cleanup evidence is required before any future terminal closure claim.
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
    DEFAULT_EXAMPLES as DEFAULT_SOURCE_CONTRACT_EXAMPLES,
    DEFAULT_SCHEMA as DEFAULT_SOURCE_CONTRACT_SCHEMA,
    validate_agentic_service_harness_contract,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = (
    REPO_ROOT / "schemas" / "agentic_service_harness_temporary_branch_workspace_preflight.schema.json"
)
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_temporary_branch_workspace_preflight.foundation.json",
)
DEFAULT_SOURCE_CONTRACT = REPO_ROOT / "examples" / "agentic_service_harness.branch_write_awaiting_approval.json"
DEFAULT_OUTPUT = (
    REPO_ROOT
    / ".change_assurance"
    / "agentic_service_harness_temporary_branch_workspace_preflight_validation.json"
)
EXPECTED_SOURCE_CONTRACT_REF = "examples/agentic_service_harness.branch_write_awaiting_approval.json"
EXPECTED_REPORT_ID = "agentic_service_harness_temporary_branch_workspace_preflight"
EXPECTED_PREFLIGHT_STATE = "BRANCH_WORKSPACE_CREATE_BLOCKED_AWAITING_APPROVAL"
EXPECTED_BRANCH_WORKSPACE_MODE = "temporary_branch_preflight_only"
EXPECTED_BRANCH_NAME_TEMPLATE = "codex/harness-branch-workspace-{run_id}"
EXPECTED_REQUESTED_ACTION_CLASS = "write_to_branch"
EXPECTED_SOURCE_SANDBOX_ID = "sandbox.branchwrite"
EXPECTED_APPROVAL_GATE_ID = "gate.branchwrite"
REQUIRED_COMMAND_ALLOWLIST = (
    "git.status",
    "git.diff",
    "python.pytest",
    "python.validator",
)
REQUIRED_PATH_ALLOWLIST = (
    ".",
    "schemas/",
    "examples/",
    "scripts/",
    "tests/",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
REQUIRED_BEFORE_CREATE_REFS = (
    "approval-request://harness/gate.branchwrite",
    "gateway-approval://operator/branch-write",
    "receipt://sandbox-cleanup-branchwrite",
    "policy://approval-required",
    "gate://harness/no-secret-serialization",
)
REQUIRED_BLOCKERS = (
    "blocked://operator-approval/not-present",
    "blocked://branch-workspace/create-not-admitted",
    "blocked://filesystem-write/not-admitted",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_RECEIPT_REFS = {
    "temporary_branch_workspace_preflight_schema": (
        "schemas/agentic_service_harness_temporary_branch_workspace_preflight.schema.json"
    ),
    "agentic_service_harness_schema": "schemas/agentic_service_harness.schema.json",
    "branch_write_contract": EXPECTED_SOURCE_CONTRACT_REF,
    "readiness_map": "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
}
REQUIRED_FALSE_FLAGS = (
    "branch_created",
    "filesystem_write_enabled",
    "external_adapter_integrated",
    "secret_values_serialized",
    "branch_workspace_create_enabled",
    "branch_write_enabled",
    "pull_request_creation_enabled",
    "receipt_store_append_enabled",
    "runtime_state_write_enabled",
    "mutation_route_enabled",
    "live_adapter_execution_enabled",
    "deployment_enabled",
    "dns_mutation_enabled",
    "secret_mutation_enabled",
    "destructive_operation_enabled",
    "terminal_closure",
    "default_high_risk_authority",
    "production_mutation_allowed",
    "cleanup_verified",
    "residual_state_allowed",
)
REQUIRED_TRUE_FLAGS = (
    "preflight_only",
    "secret_redaction_required",
    "cleanup_required",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)
ALLOWED_SECRET_KEYS = {
    "gate://harness/no-secret-serialization",
    "secret_mutation_enabled",
    "secret_redaction_required",
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
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class TemporaryBranchWorkspacePreflightValidation:
    """Schema and semantic validation report for branch workspace preflight."""

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


def validate_agentic_service_harness_temporary_branch_workspace_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
    source_contract_path: Path = DEFAULT_SOURCE_CONTRACT,
) -> TemporaryBranchWorkspacePreflightValidation:
    """Validate temporary branch workspace preflight examples."""
    errors: list[str] = []
    schema = _load_json_object(schema_path, "temporary branch workspace preflight schema", errors)
    source_contract = _load_json_object(source_contract_path, "branch-write harness contract", errors)
    source_validation = validate_agentic_service_harness_contract(
        schema_path=DEFAULT_SOURCE_CONTRACT_SCHEMA,
        example_paths=DEFAULT_SOURCE_CONTRACT_EXAMPLES,
    )
    if not source_validation.ok:
        errors.extend(f"source contract: {error}" for error in source_validation.errors)

    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"temporary branch workspace preflight example {_path_label(example_path)}",
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

    return TemporaryBranchWorkspacePreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_contract_ref=EXPECTED_SOURCE_CONTRACT_REF,
    )


def write_temporary_branch_workspace_preflight_validation(
    validation: TemporaryBranchWorkspacePreflightValidation,
    output_path: Path,
) -> Path:
    """Write one deterministic temporary branch workspace preflight report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_preflight(**changes: Any) -> dict[str, Any]:
    """Return a mutated copy of the default preflight fixture for tests."""
    payload = _load_json_object(DEFAULT_EXAMPLES[0], "default preflight fixture", [])
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


def _validate_preflight_semantics(
    example: Mapping[str, Any],
    source_contract: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _validate_source_binding(example, source_contract, errors, label)
    _validate_workspace_preflight(example, source_contract, errors, label)
    _validate_boolean_flags(example, errors, label)
    _validate_ref_sets(example, errors, label)
    _validate_receipt_refs(example, errors, label)
    _validate_secret_surface(example, errors, label)
    _validate_no_mutation_routes(example, errors, label)


def _validate_source_binding(
    example: Mapping[str, Any],
    source_contract: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    if example.get("report_id") != EXPECTED_REPORT_ID:
        errors.append(f"{label}: report_id must be {EXPECTED_REPORT_ID}")
    if example.get("source_contract_ref") != EXPECTED_SOURCE_CONTRACT_REF:
        errors.append(f"{label}: source_contract_ref must bind branch-write harness contract")
    scope = example.get("scope")
    if not isinstance(scope, Mapping):
        errors.append(f"{label}: scope must be an object")
        return
    source_scope = _source_scope(source_contract)
    for key in ("tenant_id", "organization_id", "project_id"):
        if scope.get(key) != source_scope.get(key):
            errors.append(f"{label}: scope.{key} must match source contract")
    repository = _first_mapping(source_contract.get("repository_connections"))
    if not repository:
        errors.append(f"{label}: source contract must include repository connection")
    else:
        if scope.get("repository_connection_id") != repository.get("connection_id"):
            errors.append(f"{label}: scope.repository_connection_id must match source repository")
        if scope.get("repository_slug") != repository.get("repository_slug"):
            errors.append(f"{label}: scope.repository_slug must match source repository")
    run = _first_mapping(source_contract.get("agent_runs"))
    if not run:
        errors.append(f"{label}: source contract must include AgentRun")
    else:
        if scope.get("agent_run_id") != run.get("run_id"):
            errors.append(f"{label}: scope.agent_run_id must match source AgentRun")
        if scope.get("sandbox_id") != run.get("sandbox_id"):
            errors.append(f"{label}: scope.sandbox_id must match source sandbox")
    gate = _first_mapping(source_contract.get("approval_gates"))
    if not gate:
        errors.append(f"{label}: source contract must include approval gate")
    else:
        if scope.get("approval_gate_id") != gate.get("gate_id"):
            errors.append(f"{label}: scope.approval_gate_id must match source approval gate")
        if gate.get("approval_collected") is not False:
            errors.append(f"{label}: source approval gate must not be collected")
        if gate.get("authority_granted") is not False:
            errors.append(f"{label}: source approval gate must not grant authority")
    if scope.get("requested_action_class") != EXPECTED_REQUESTED_ACTION_CLASS:
        errors.append(f"{label}: requested_action_class must be {EXPECTED_REQUESTED_ACTION_CLASS}")


def _validate_workspace_preflight(
    example: Mapping[str, Any],
    source_contract: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    preflight = example.get("workspace_preflight")
    if not isinstance(preflight, Mapping):
        errors.append(f"{label}: workspace_preflight must be an object")
        return
    source_sandbox = _first_mapping(source_contract.get("workspace_sandboxes"))
    if not source_sandbox:
        errors.append(f"{label}: source contract must include WorkspaceSandbox")
    else:
        if preflight.get("source_sandbox_id") != source_sandbox.get("sandbox_id"):
            errors.append(f"{label}: workspace_preflight.source_sandbox_id must match source sandbox")
        if preflight.get("cleanup_receipt_ref") != source_sandbox.get("cleanup_receipt_ref"):
            errors.append(f"{label}: workspace_preflight.cleanup_receipt_ref must match source sandbox")
        if set(preflight.get("command_allowlist", ())) != set(source_sandbox.get("command_allowlist", ())):
            errors.append(f"{label}: workspace_preflight.command_allowlist must match source sandbox")
        if preflight.get("timeout_seconds") != source_sandbox.get("timeout_seconds"):
            errors.append(f"{label}: workspace_preflight.timeout_seconds must match source sandbox")
        if preflight.get("network_policy") != source_sandbox.get("network_policy"):
            errors.append(f"{label}: workspace_preflight.network_policy must match source sandbox")
    if preflight.get("preflight_state") != EXPECTED_PREFLIGHT_STATE:
        errors.append(f"{label}: workspace_preflight.preflight_state must be {EXPECTED_PREFLIGHT_STATE}")
    if preflight.get("branch_workspace_mode") != EXPECTED_BRANCH_WORKSPACE_MODE:
        errors.append(f"{label}: workspace_preflight.branch_workspace_mode must be {EXPECTED_BRANCH_WORKSPACE_MODE}")
    if preflight.get("branch_name_template") != EXPECTED_BRANCH_NAME_TEMPLATE:
        errors.append(f"{label}: workspace_preflight.branch_name_template must be {EXPECTED_BRANCH_NAME_TEMPLATE}")
    if set(preflight.get("command_allowlist", ())) != set(REQUIRED_COMMAND_ALLOWLIST):
        errors.append(f"{label}: workspace_preflight.command_allowlist must match required set")
    if set(preflight.get("path_allowlist", ())) != set(REQUIRED_PATH_ALLOWLIST):
        errors.append(f"{label}: workspace_preflight.path_allowlist must match required set")
    if preflight.get("timeout_seconds") != 300:
        errors.append(f"{label}: workspace_preflight.timeout_seconds must be 300")
    if preflight.get("network_policy") != "none":
        errors.append(f"{label}: workspace_preflight.network_policy must be none")


def _validate_boolean_flags(
    payload: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if key_lower in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {path} must be false")
        if key_lower in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {path} must be true")


def _validate_ref_sets(example: Mapping[str, Any], errors: list[str], label: str) -> None:
    preflight = example.get("workspace_preflight")
    if not isinstance(preflight, Mapping):
        return
    _require_refs(
        preflight.get("required_before_create_refs"),
        REQUIRED_BEFORE_CREATE_REFS,
        f"{label}: workspace_preflight.required_before_create_refs",
        errors,
    )
    _require_refs(
        preflight.get("blocked_reason_refs"),
        REQUIRED_BLOCKERS,
        f"{label}: workspace_preflight.blocked_reason_refs",
        errors,
    )


def _validate_receipt_refs(example: Mapping[str, Any], errors: list[str], label: str) -> None:
    receipt_refs = example.get("receipt_refs")
    if not isinstance(receipt_refs, Mapping):
        errors.append(f"{label}: receipt_refs must be an object")
        return
    for key, expected_value in REQUIRED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected_value:
            errors.append(f"{label}: receipt_refs.{key} must be {expected_value}")


def _validate_secret_surface(payload: Any, errors: list[str], label: str) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS):
            if key_lower not in ALLOWED_SECRET_KEYS and str(value) not in ALLOWED_SECRET_KEYS:
                errors.append(f"{label}: forbidden secret-bearing key at {path}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {path}")
                    break


def _validate_no_mutation_routes(payload: Any, errors: list[str], label: str) -> None:
    for path, value in _walk_strings(payload):
        if MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {path}")


def _require_refs(
    observed: Any,
    required: Sequence[str],
    label: str,
    errors: list[str],
) -> None:
    if not isinstance(observed, list):
        errors.append(f"{label} must be a list")
        return
    observed_set = set(str(item) for item in observed)
    for required_ref in required:
        if required_ref not in observed_set:
            errors.append(f"{label} missing required ref {required_ref}")


def _source_scope(source_contract: Mapping[str, Any]) -> Mapping[str, Any]:
    project = _first_mapping(source_contract.get("projects")) or {}
    organization = _first_mapping(source_contract.get("organizations")) or {}
    return {
        "tenant_id": project.get("tenant_id") or organization.get("tenant_id"),
        "organization_id": project.get("organization_id"),
        "project_id": project.get("project_id"),
    }


def _first_mapping(value: Any) -> Mapping[str, Any] | None:
    if not isinstance(value, list) or not value:
        return None
    first = value[0]
    if not isinstance(first, Mapping):
        return None
    return first


def _walk_json(payload: Any, path: str = "$") -> Iterable[tuple[str, str, Any]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            child_path = f"{path}.{key}"
            yield child_path, str(key), value
            yield from _walk_json(value, child_path)
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_json(item, f"{path}[{index}]")


def _walk_strings(payload: Any, path: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield from _walk_strings(value, f"{path}.{key}")
    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            yield from _walk_strings(item, f"{path}[{index}]")
    elif isinstance(payload, str):
        yield path, payload


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    if not path.exists():
        errors.append(f"{label} file missing: {_path_label(path)}")
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"), parse_constant=_reject_json_constant)
    except (json.JSONDecodeError, ValueError):
        errors.append(f"{label} JSON parse failed")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{label} JSON root must be an object")
        return {}
    return payload


def _reject_json_constant(raw_constant: str) -> None:
    raise ValueError(f"non-finite JSON constants are not permitted: {raw_constant}")


def _path_label(path: Path) -> str:
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.name


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse temporary branch workspace preflight validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate the harness temporary branch workspace preflight contract."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--source-contract", default=str(DEFAULT_SOURCE_CONTRACT))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for temporary branch workspace preflight validation."""
    args = parse_args(argv)
    example_paths = (
        tuple(Path(example) for example in args.example)
        if args.example
        else DEFAULT_EXAMPLES
    )
    validation = validate_agentic_service_harness_temporary_branch_workspace_preflight(
        schema_path=Path(args.schema),
        example_paths=example_paths,
        source_contract_path=Path(args.source_contract),
    )
    write_temporary_branch_workspace_preflight_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS TEMPORARY BRANCH WORKSPACE PREFLIGHT VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS TEMPORARY BRANCH WORKSPACE PREFLIGHT INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
