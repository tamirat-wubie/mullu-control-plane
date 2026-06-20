#!/usr/bin/env python3
"""Validate Agentic Service Harness read-only repository task intake.

Purpose: prove repository task intake binds RepositoryConnection and AgentTask
scope without granting code execution, filesystem writes, branch creation,
pull-request creation, live adapter calls, secret disclosure, or terminal
closure authority.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_read_only_repo_task_intake.schema.json,
examples/agentic_service_harness_read_only_repo_task_intake.foundation.json,
and scripts.validate_schemas.
Invariants:
  - Repository and task identity must match across scope and intake bindings.
  - Intake mode is read-only and no commands are requested.
  - All effect-bearing authorities remain false until later approval evidence.
  - Secret-like keys, credential-like values, and mutation route strings fail closed.
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

from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_read_only_repo_task_intake.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_read_only_repo_task_intake.foundation.json",
)
DEFAULT_OUTPUT = (
    REPO_ROOT / ".change_assurance" / "agentic_service_harness_read_only_repo_task_intake_validation.json"
)
REQUIRED_FALSE_FLAGS = (
    "write_authority_granted",
    "code_execution_requested",
    "filesystem_write_requested",
    "external_adapter_requested",
    "execution_authority_granted",
    "branch_workspace_creation_granted",
    "pull_request_creation_granted",
    "terminal_closure_granted",
    "mutation_endpoint_admitted",
    "live_adapter_execution",
    "filesystem_write",
    "branch_creation",
    "pull_request_creation",
    "deployment",
    "dns_mutation",
    "secret_serialization",
    "destructive_operation",
    "terminal_closure",
)
REQUIRED_TRUE_FLAGS = (
    "read_only",
    "installation_ref_redacted",
    "repository_connection_verified",
    "repository_slug_matches_scope",
    "agent_task_matches_scope",
    "task_scope_bounded",
    "path_allowlist_present",
    "approval_required_before_effects",
    "report_is_not_terminal_closure",
    "terminal_closure_required",
)
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
ALLOWED_SECRET_KEYS = {
    "dns_mutation",
    "secret_serialization",
}
FORBIDDEN_CREDENTIAL_VALUE_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
    re.compile(r"\bghp_[A-Za-z0-9_]+\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]+\b"),
    re.compile(r"\bsk-[A-Za-z0-9_=-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ReadOnlyRepoTaskIntakeValidation:
    """Schema and semantic validation report for read-only repo task intake."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_read_only_repo_task_intake(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> ReadOnlyRepoTaskIntakeValidation:
    """Validate repo task intake examples against schema and invariants."""

    errors: list[str] = []
    schema = _load_json_object(schema_path, "read-only repo task intake schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(
            example_path,
            f"read-only repo task intake example {_path_label(example_path)}",
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
    return ReadOnlyRepoTaskIntakeValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
    )


def write_read_only_repo_task_intake_validation(
    validation: ReadOnlyRepoTaskIntakeValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic read-only repo task intake validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def _validate_semantics(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    scope = _object(payload.get("scope"))
    binding = _object(payload.get("repository_connection_binding"))
    intake = _object(payload.get("task_intake"))
    gates = _object(payload.get("preflight_gates"))
    denials = _object(payload.get("authority_denials"))

    if not scope:
        errors.append(f"{label}: scope must be an object")
    if not binding:
        errors.append(f"{label}: repository_connection_binding must be an object")
    if not intake:
        errors.append(f"{label}: task_intake must be an object")
    if not gates:
        errors.append(f"{label}: preflight_gates must be an object")
    if not denials:
        errors.append(f"{label}: authority_denials must be an object")
    if not scope or not binding or not intake:
        return

    if scope.get("repository_connection_id") != binding.get("repository_connection_id"):
        errors.append(f"{label}: repository_connection_id must match between scope and binding")
    if scope.get("repository_slug") != binding.get("repository_slug"):
        errors.append(f"{label}: repository_slug must match between scope and binding")
    if scope.get("agent_task_id") != intake.get("agent_task_id"):
        errors.append(f"{label}: agent_task_id must match between scope and task_intake")
    if intake.get("requested_mode") != "read_only":
        errors.append(f"{label}: requested_mode must be read_only")
    if intake.get("allowed_action_classes") != ["read_only"]:
        errors.append(f"{label}: allowed_action_classes must be read_only only")
    if intake.get("requested_commands") != []:
        errors.append(f"{label}: requested_commands must be empty for intake preflight")
    if not isinstance(intake.get("allowed_path_prefixes"), list) or not intake.get("allowed_path_prefixes"):
        errors.append(f"{label}: allowed_path_prefixes must not be empty")
    if not isinstance(intake.get("forbidden_path_prefixes"), list) or ".git/" not in intake.get("forbidden_path_prefixes", ()):
        errors.append(f"{label}: forbidden_path_prefixes must include .git/")
    if binding.get("provider") != "github":
        errors.append(f"{label}: repository provider must be github")
    if binding.get("connection_state") != "verified_read_only":
        errors.append(f"{label}: connection_state must be verified_read_only")

    _validate_boolean_flags(payload, errors, label)
    _validate_secret_surface(payload, errors, label)
    _validate_no_mutation_routes(payload, errors, label)


def _validate_boolean_flags(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
        key = path[-1] if path else ""
        if key in REQUIRED_FALSE_FLAGS and value is not False:
            errors.append(f"{label}: {'.'.join(path)} must be false")
        if key in REQUIRED_TRUE_FLAGS and value is not True:
            errors.append(f"{label}: {'.'.join(path)} must be true")


def _validate_secret_surface(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
        key = path[-1] if path else ""
        normalized_key = key.lower()
        if key not in ALLOWED_SECRET_KEYS and any(token in normalized_key for token in FORBIDDEN_SECRET_KEY_TOKENS):
            errors.append(f"{label}: forbidden secret-bearing key {'.'.join(path)}")
        if isinstance(value, str) and any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: credential-like value at {'.'.join(path)}")


def _validate_no_mutation_routes(payload: Mapping[str, Any], errors: list[str], label: str) -> None:
    for path, value in _walk(payload):
        if isinstance(value, str) and MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {'.'.join(path)}")


def _load_json_object(path: Path, description: str, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{description} missing: {_path_label(path)}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{description} invalid JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{description} must be a JSON object")
        return {}
    return payload


def _object(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _walk(value: Any, path: tuple[str, ...] = ()) -> Iterable[tuple[tuple[str, ...], Any]]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_path = path + (str(key),)
            yield child_path, child
            yield from _walk(child, child_path)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            child_path = path + (str(index),)
            yield child_path, child
            yield from _walk(child, child_path)


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point for read-only repo task intake validation."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", type=Path, action="append", dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args(argv)

    validation = validate_agentic_service_harness_read_only_repo_task_intake(
        schema_path=args.schema,
        example_paths=tuple(args.examples) if args.examples else DEFAULT_EXAMPLES,
    )
    if args.output:
        write_read_only_repo_task_intake_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS READ-ONLY REPO TASK INTAKE VALID")
    else:
        for error in validation.errors:
            print(f"[FAIL] {error}")
        print("STATUS: failed")
    return 0 if validation.ok else 1 if args.strict else 0


if __name__ == "__main__":
    raise SystemExit(main())
