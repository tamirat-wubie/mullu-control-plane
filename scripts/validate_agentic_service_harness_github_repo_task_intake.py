#!/usr/bin/env python3
"""Validate Agentic Service Harness GitHub repository task intake contract.

Purpose: prove the first GitHub repository task intake remains read-only,
contract-only, and non-terminal before code execution, adapter execution,
branch writes, pull-request creation, receipt-store append, runtime-state
writes, secret serialization, deployment, DNS mutation, destructive operation,
or terminal closure is admitted.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_github_repo_task_intake.schema.json,
examples/agentic_service_harness_github_repo_task_intake.foundation.json,
scripts.validate_agentic_service_harness_github_repo_task_service, and
scripts.validate_schemas.
Invariants:
  - Source GitHub repo task service evidence validates before intake.
  - Repository connection and task scope refs are consistent.
  - Intake remains read-only, preflight-only, and contract-only.
  - Execution, repository effects, receipt append, mutation routes, secrets,
    and terminal closure fail closed.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_agentic_service_harness_github_repo_task_service import (  # noqa: E402
    validate_agentic_service_harness_github_repo_task_service,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_github_repo_task_intake.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_github_repo_task_intake.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_github_repo_task_intake_validation.json"
)
EXPECTED_REPORT_ID = "agentic_service_harness_github_repo_task_intake"
EXPECTED_SOURCE_CONTRACT_REF = "examples/agentic_service_harness_github_repo_task_service.foundation.json"
EXPECTED_DECISION = "READ_ONLY_REPO_TASK_INTAKE_ACCEPTED_CONTRACT_ONLY"
EXPECTED_FORBIDDEN_ACTION_CLASSES = frozenset(
    {
        "execute_adapter",
        "write_to_branch",
        "open_pr",
        "append_receipt_store",
        "deploy",
        "dns_mutation",
        "secret_mutation",
        "destructive_operation",
        "terminal_closure",
    }
)
EXPECTED_GATE_REFS = frozenset(
    {
        "gate://harness/no-live-adapter-execution",
        "gate://harness/no-branch-write",
        "gate://harness/no-pr-creation",
        "gate://harness/no-receipt-store-append",
        "gate://harness/no-secret-serialization",
        "gate://harness/terminal-closure-denied",
    }
)
EXPECTED_RECEIPT_REFS = {
    "github_repo_task_intake_schema": (
        "schemas/agentic_service_harness_github_repo_task_intake.schema.json"
    ),
    "github_repo_task_service_schema": (
        "schemas/agentic_service_harness_github_repo_task_service.schema.json"
    ),
    "github_repo_task_service_fixture": (
        "examples/agentic_service_harness_github_repo_task_service.foundation.json"
    ),
    "agentic_service_harness_schema": "schemas/agentic_service_harness.schema.json",
    "readiness_map": "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
}
REQUIRED_FALSE_FLAGS = frozenset(
    {
        "live_probe_executed",
        "adapter_executed",
        "runtime_state_write_enabled",
        "receipt_store_append_enabled",
        "secret_values_serialized",
        "writes_repository",
        "creates_branch",
        "opens_pull_request",
        "route_admitted",
        "executes_adapter",
        "intake_recorded_in_runtime_state",
        "execution_admitted",
        "adapter_execution_admitted",
        "branch_workspace_required",
        "branch_write_admitted",
        "pull_request_creation_admitted",
        "receipt_emission_admitted",
        "terminal_closure_allowed",
        "live_adapter_execution_enabled",
        "branch_write_enabled",
        "pull_request_creation_enabled",
        "repository_write_enabled",
        "mutation_route_enabled",
        "deployment_enabled",
        "dns_mutation_enabled",
        "secret_mutation_enabled",
        "destructive_operation_enabled",
        "terminal_closure",
        "default_high_risk_authority",
    }
)
REQUIRED_TRUE_FLAGS = frozenset(
    {
        "read_only",
        "intake_preflight_only",
        "permission_scope_read_only",
        "approval_required_for_effects",
        "task_scope_valid",
        "repository_connection_valid",
        "report_is_not_terminal_closure",
        "terminal_closure_required",
        "required_for_closure",
    }
)
ALLOWED_SECRET_KEYS = {
    "dns_mutation_enabled",
    "secret_mutation_enabled",
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
class GitHubRepoTaskIntakeValidation:
    """Schema and semantic validation report for GitHub repo task intake."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    forbidden_action_class_count: int
    source_service_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_github_repo_task_intake(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> GitHubRepoTaskIntakeValidation:
    """Validate GitHub repo task intake examples against schema and invariants."""
    errors: list[str] = []
    source_validation = validate_agentic_service_harness_github_repo_task_service()
    if not source_validation.ok:
        errors.extend(
            f"source GitHub repo task service invalid: {error}"
            for error in source_validation.errors
        )
    schema = _load_json_object(schema_path, "GitHub repo task intake schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"GitHub repo task intake example {_path_label(example_path)}",
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
        _validate_intake_semantics(example, errors, _path_label(example_path))
    return GitHubRepoTaskIntakeValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        forbidden_action_class_count=len(EXPECTED_FORBIDDEN_ACTION_CLASSES),
        source_service_ok=source_validation.ok,
    )


def write_github_repo_task_intake_validation(
    validation: GitHubRepoTaskIntakeValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic GitHub repo task intake validation report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_intake_semantics(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(example, ("report_id",), EXPECTED_REPORT_ID, errors, label)
    _check_value(example, ("source_contract_ref",), EXPECTED_SOURCE_CONTRACT_REF, errors, label)
    _check_value(example, ("intake_decision", "decision"), EXPECTED_DECISION, errors, label)
    _validate_ref_consistency(example, errors, label)
    _validate_task_scope(example, errors, label)
    _validate_decision(example, errors, label)
    _validate_receipt_refs(example, errors, label)
    _validate_validators(example, errors, label)
    _validate_boolean_flags(example, errors, label)
    _validate_secret_surface(example, errors, label)
    _validate_no_mutation_routes(example, errors, label)


def _validate_ref_consistency(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    scope = _mapping_at(example, ("scope",))
    repository_check = _mapping_at(example, ("repository_connection_check",))
    task_scope = _mapping_at(example, ("task_scope_intake",))
    if not scope or not repository_check or not task_scope:
        errors.append(f"{label}: scope, repository_connection_check, and task_scope_intake are required")
        return
    for key in ("repository_connection_id", "repository_slug"):
        if scope.get(key) != repository_check.get(key):
            errors.append(f"{label}: scope.{key} must match repository_connection_check.{key}")
    for key in ("intake_id", "task_service_id"):
        if scope.get(key) != task_scope.get(key):
            errors.append(f"{label}: scope.{key} must match task_scope_intake.{key}")
    if repository_check.get("provider") != "github":
        errors.append(f"{label}: repository_connection_check.provider must be github")
    metadata_fields = repository_check.get("metadata_fields")
    if not isinstance(metadata_fields, list) or len(metadata_fields) < 4:
        errors.append(f"{label}: metadata_fields must contain repository connection evidence")
    source_refs = repository_check.get("source_refs")
    if not isinstance(source_refs, list) or EXPECTED_SOURCE_CONTRACT_REF not in source_refs:
        errors.append(f"{label}: repository source_refs must include source contract ref")


def _validate_task_scope(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    task_scope = _mapping_at(example, ("task_scope_intake",))
    if not task_scope:
        errors.append(f"{label}: task_scope_intake must be an object")
        return
    allowed = set(str(item) for item in task_scope.get("allowed_action_classes", ()))
    forbidden = set(str(item) for item in task_scope.get("forbidden_action_classes", ()))
    gates = set(str(item) for item in task_scope.get("required_gate_refs", ()))
    blocked = task_scope.get("blocked_reason_refs")
    if allowed != {"read_only"}:
        errors.append(f"{label}: allowed_action_classes must be read_only only")
    missing_forbidden = sorted(EXPECTED_FORBIDDEN_ACTION_CLASSES - forbidden)
    if missing_forbidden:
        errors.append(f"{label}: forbidden_action_classes missing {missing_forbidden}")
    missing_gates = sorted(EXPECTED_GATE_REFS - gates)
    if missing_gates:
        errors.append(f"{label}: required_gate_refs missing {missing_gates}")
    if not isinstance(blocked, list) or not blocked:
        errors.append(f"{label}: blocked_reason_refs must not be empty")


def _validate_decision(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    decision = _mapping_at(example, ("intake_decision",))
    if not decision:
        errors.append(f"{label}: intake_decision must be an object")
        return
    next_refs = decision.get("next_required_evidence_refs")
    if not isinstance(next_refs, list) or not next_refs:
        errors.append(f"{label}: next_required_evidence_refs must not be empty")
    if decision.get("execution_admitted") is not False:
        errors.append(f"{label}: intake_decision.execution_admitted must be false")
    if decision.get("terminal_closure_allowed") is not False:
        errors.append(f"{label}: intake_decision.terminal_closure_allowed must be false")


def _validate_receipt_refs(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    receipt_refs = _mapping_at(example, ("receipt_refs",))
    if not receipt_refs:
        errors.append(f"{label}: receipt_refs must be an object")
        return
    for key, expected in EXPECTED_RECEIPT_REFS.items():
        if receipt_refs.get(key) != expected:
            errors.append(f"{label}: receipt_refs.{key} must be {expected}")


def _validate_validators(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    validators = example.get("validators")
    if not isinstance(validators, list) or not validators:
        errors.append(f"{label}: validators must not be empty")
        return
    commands = {str(item.get("command")) for item in _objects(validators)}
    expected_command = "python scripts/validate_agentic_service_harness_github_repo_task_intake.py --strict"
    if expected_command not in commands:
        errors.append(f"{label}: validators must include {expected_command}")


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


def _validate_secret_surface(
    payload: Any,
    errors: list[str],
    label: str,
) -> None:
    for path, key, value in _walk_json(payload):
        key_lower = key.lower()
        if (
            any(token in key_lower for token in FORBIDDEN_SECRET_KEY_TOKENS)
            and key_lower not in ALLOWED_SECRET_KEYS
        ):
            errors.append(f"{label}: forbidden secret-bearing key at {path}")
        if isinstance(value, str):
            for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS:
                if pattern.search(value):
                    errors.append(f"{label}: credential-like value at {path}")
                    break


def _validate_no_mutation_routes(
    payload: Any,
    errors: list[str],
    label: str,
) -> None:
    for path, value in _walk_strings(payload):
        if MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {path}")


def _check_value(
    payload: Mapping[str, Any],
    path: tuple[str, ...],
    expected: Any,
    errors: list[str],
    label: str,
) -> None:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            errors.append(f"{label}: {'.'.join(path)} is required")
            return
        current = current[key]
    if current != expected:
        errors.append(f"{label}: {'.'.join(path)} must be {expected}")


def _mapping_at(payload: Mapping[str, Any], path: tuple[str, ...]) -> Mapping[str, Any]:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping):
            return {}
        current = current.get(key)
    return current if isinstance(current, Mapping) else {}


def _objects(collection: Any) -> tuple[dict[str, Any], ...]:
    if not isinstance(collection, list):
        return ()
    return tuple(item for item in collection if isinstance(item, dict))


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
    """Parse GitHub repo task intake validation arguments."""
    parser = argparse.ArgumentParser(
        description="Validate the read-only harness GitHub repository task intake contract."
    )
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--example", action="append", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for GitHub repo task intake validation."""
    args = parse_args(argv)
    example_paths = (
        tuple(Path(example) for example in args.example)
        if args.example
        else DEFAULT_EXAMPLES
    )
    validation = validate_agentic_service_harness_github_repo_task_intake(
        schema_path=Path(args.schema),
        example_paths=example_paths,
    )
    write_github_repo_task_intake_validation(validation, Path(args.output))
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS GITHUB REPO TASK INTAKE VALID")
    else:
        print(
            "AGENTIC SERVICE HARNESS GITHUB REPO TASK INTAKE INVALID "
            f"errors={list(validation.errors)}"
        )
    return 0 if validation.ok or not args.strict else 2


if __name__ == "__main__":
    raise SystemExit(main())
