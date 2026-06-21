#!/usr/bin/env python3
"""Validate Agentic Service Harness task creation admission preflight.

Purpose: prove task creation remains an evidence-bound admission preflight
without route creation, task record writes, runtime state writes, adapter
execution, branch effects, pull requests, receipt append, secret serialization,
or terminal closure.
Governance scope: [OCE, RAG, CDCV, CQTE, UWMA, SRCA, PRS]
Dependencies: schemas/agentic_service_harness_task_creation_admission_preflight.schema.json,
examples/agentic_service_harness_task_creation_admission_preflight.foundation.json,
source harness projection validators, and scripts.validate_schemas.
Invariants:
  - Source task intake, dashboard data, Receipt, and LoopStatus projections
    validate before admission is considered.
  - Task creation admission remains blocked with Unknown proof state.
  - Mutation routes, runtime writes, external effects, secrets, and terminal
    closure fail closed.
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

from scripts.validate_agentic_service_harness_dashboard_data_contract import (  # noqa: E402
    validate_agentic_service_harness_dashboard_data_contract,
)
from scripts.validate_agentic_service_harness_github_repo_task_intake import (  # noqa: E402
    validate_agentic_service_harness_github_repo_task_intake,
)
from scripts.validate_agentic_service_harness_loopstatus_projection import (  # noqa: E402
    validate_agentic_service_harness_loopstatus_projection,
)
from scripts.validate_agentic_service_harness_receipt_projection import (  # noqa: E402
    validate_agentic_service_harness_receipt_projection,
)
from scripts.validate_schemas import _validate_schema_instance  # noqa: E402


DEFAULT_SCHEMA = REPO_ROOT / "schemas" / "agentic_service_harness_task_creation_admission_preflight.schema.json"
DEFAULT_EXAMPLES = (
    REPO_ROOT / "examples" / "agentic_service_harness_task_creation_admission_preflight.foundation.json",
)
DEFAULT_OUTPUT = REPO_ROOT / ".change_assurance" / "agentic_service_harness_task_creation_admission_preflight_validation.json"
EXPECTED_REPORT_ID = "agentic_service_harness_task_creation_admission_preflight"
EXPECTED_DECISION = "TASK_CREATION_ADMISSION_BLOCKED_AWAITING_EVIDENCE"
EXPECTED_PROOF_STATE = "Unknown"
REQUIRED_SOURCE_REFS = (
    "examples/agentic_service_harness_github_repo_task_intake.foundation.json",
    "examples/agentic_service_harness_dashboard_data_contract.foundation.json",
    "examples/agentic_service_harness_receipt_evidence_read_models.foundation.json",
    "examples/agentic_service_harness_receipt_projection.foundation.json",
    "examples/agentic_service_harness_loopstatus_projection.foundation.json",
    "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
)
REQUIRED_POLICY_REFS = (
    "policy://harness/task-creation-read-only-boundary",
    "policy://harness/no-mutation-route-without-admission",
    "policy://harness/no-runtime-write-without-approval",
    "policy://harness/no-adapter-execution",
    "policy://harness/no-secret-serialization",
    "policy://harness/terminal-closure-denied",
)
REQUIRED_BLOCKERS = (
    "blocked://task-creation-route/not-admitted",
    "blocked://task-record-write/not-admitted",
    "blocked://runtime-state-write/not-admitted",
    "blocked://operator-approval/not-present",
    "blocked://terminal-closure/not-authorized",
)
REQUIRED_EVIDENCE_REFS = (
    "evidence://task-creation-route-contract",
    "evidence://operator-approval-for-task-creation",
    "evidence://task-write-rollback-plan",
    "evidence://uao-task-creation-admission",
    "evidence://receipt-store-append-authority",
)
REQUIRED_BEFORE_TASK_REFS = (
    *REQUIRED_EVIDENCE_REFS,
    "evidence://effect-reconciliation-before-terminal-closure",
)
EXPECTED_RECEIPT_REFS = {
    "task_creation_admission_preflight_schema": (
        "schemas/agentic_service_harness_task_creation_admission_preflight.schema.json"
    ),
    "task_creation_admission_preflight_fixture": (
        "examples/agentic_service_harness_task_creation_admission_preflight.foundation.json"
    ),
    "github_repo_task_intake_fixture": "examples/agentic_service_harness_github_repo_task_intake.foundation.json",
    "dashboard_data_contract_fixture": "examples/agentic_service_harness_dashboard_data_contract.foundation.json",
    "loopstatus_projection_fixture": "examples/agentic_service_harness_loopstatus_projection.foundation.json",
    "receipt_projection_fixture": "examples/agentic_service_harness_receipt_projection.foundation.json",
    "readiness_map": "MULLUSI_AGENTIC_SERVICE_HARNESS_READINESS_MAP.md",
}
REQUIRED_FALSE_FLAGS = frozenset(
    {
        "task_creation_route_admitted",
        "task_record_write_enabled",
        "runtime_state_write_enabled",
        "adapter_execution_enabled",
        "branch_creation_enabled",
        "pull_request_creation_enabled",
        "receipt_store_append_enabled",
        "secret_values_serialized",
        "terminal_closure_granted",
        "task_creation_admitted",
        "route_creation_admitted",
        "task_record_write_admitted",
        "runtime_state_write_admitted",
        "adapter_execution_admitted",
        "branch_creation_admitted",
        "pull_request_creation_admitted",
        "receipt_store_append_admitted",
        "terminal_closure_allowed",
        "task_creation_route_enabled",
        "branch_write_enabled",
        "repository_write_enabled",
        "mutation_endpoint_enabled",
        "external_connector_enabled",
        "terminal_closure",
    }
)
REQUIRED_TRUE_FLAGS = frozenset(
    {
        "read_only",
        "preflight_only",
        "task_creation_requested",
        "requested_runtime_write",
        "report_is_not_terminal_closure",
        "terminal_closure_required",
        "required_for_closure",
    }
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
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{8,}\b"),
    re.compile(r"\b(access_token|api_key|password|private_key|refresh_token)="),
)
MUTATION_ROUTE_PATTERN = re.compile(r"\b(POST|PUT|PATCH|DELETE)\s+/api\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class TaskCreationAdmissionPreflightValidation:
    """Schema and semantic validation report for task creation admission."""

    ok: bool
    errors: tuple[str, ...]
    schema_path: str
    example_paths: tuple[str, ...]
    example_count: int
    source_contracts_ok: bool

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["errors"] = list(self.errors)
        payload["example_paths"] = list(self.example_paths)
        return payload


def validate_agentic_service_harness_task_creation_admission_preflight(
    *,
    schema_path: Path = DEFAULT_SCHEMA,
    example_paths: Sequence[Path] = DEFAULT_EXAMPLES,
) -> TaskCreationAdmissionPreflightValidation:
    """Validate task creation admission preflight examples."""

    errors: list[str] = []
    source_validations = (
        validate_agentic_service_harness_github_repo_task_intake(),
        validate_agentic_service_harness_dashboard_data_contract(),
        validate_agentic_service_harness_receipt_projection(),
        validate_agentic_service_harness_loopstatus_projection(),
    )
    for source_validation in source_validations:
        if not source_validation.ok:
            errors.extend(f"source contract invalid: {error}" for error in source_validation.errors)

    schema = _load_json_object(schema_path, "task creation admission preflight schema", errors)
    examples: list[dict[str, Any]] = []
    for example_path in example_paths:
        example = _load_json_object(example_path, f"task creation admission example {_path_label(example_path)}", errors)
        if not example:
            continue
        examples.append(example)
        if schema:
            errors.extend(
                f"{_path_label(example_path)}: {error}"
                for error in _validate_schema_instance(schema, example)
            )
        _validate_preflight_semantics(example, errors, _path_label(example_path))

    return TaskCreationAdmissionPreflightValidation(
        ok=not errors,
        errors=tuple(errors),
        schema_path=_path_label(schema_path),
        example_paths=tuple(_path_label(path) for path in example_paths),
        example_count=len(examples),
        source_contracts_ok=all(source_validation.ok for source_validation in source_validations),
    )


def write_task_creation_admission_preflight_validation(
    validation: TaskCreationAdmissionPreflightValidation,
    output_path: Path,
) -> Path:
    """Write a deterministic task creation admission validation report."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(validation.as_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output_path


def build_mutated_preflight(**updates: object) -> dict[str, Any]:
    """Return a default example with double-underscore path updates applied."""

    payload = deepcopy(json.loads(DEFAULT_EXAMPLES[0].read_text(encoding="utf-8")))
    for path, value in updates.items():
        _set_path(payload, tuple(path.split("__")), value)
    return payload


def _validate_preflight_semantics(
    example: Mapping[str, Any],
    errors: list[str],
    label: str,
) -> None:
    _check_value(example, ("report_id",), EXPECTED_REPORT_ID, errors, label)
    _check_value(example, ("solver_outcome",), "AwaitingEvidence", errors, label)
    _check_value(example, ("admission_decision", "decision"), EXPECTED_DECISION, errors, label)
    _check_value(example, ("admission_decision", "proof_state"), EXPECTED_PROOF_STATE, errors, label)
    _require_refs(example.get("source_contract_refs"), REQUIRED_SOURCE_REFS, errors, label, "source_contract_refs")
    _require_refs(
        _get_path(example, ("admission_request", "required_source_refs")),
        REQUIRED_SOURCE_REFS[:4],
        errors,
        label,
        "admission_request.required_source_refs",
    )
    _require_refs(
        _get_path(example, ("admission_request", "required_policy_refs")),
        REQUIRED_POLICY_REFS,
        errors,
        label,
        "admission_request.required_policy_refs",
    )
    _require_refs(
        _get_path(example, ("admission_decision", "blocked_reason_refs")),
        REQUIRED_BLOCKERS,
        errors,
        label,
        "admission_decision.blocked_reason_refs",
    )
    _require_refs(
        _get_path(example, ("admission_decision", "missing_evidence_refs")),
        REQUIRED_EVIDENCE_REFS,
        errors,
        label,
        "admission_decision.missing_evidence_refs",
    )
    _require_refs(
        example.get("required_before_task_creation_refs"),
        REQUIRED_BEFORE_TASK_REFS,
        errors,
        label,
        "required_before_task_creation_refs",
    )
    for key, expected in EXPECTED_RECEIPT_REFS.items():
        _check_value(example, ("receipt_refs", key), expected, errors, label)
    _walk_flags(example, (), errors, label)
    _scan_forbidden_text(example, (), errors, label)


def _walk_flags(value: object, path: tuple[str, ...], errors: list[str], label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            next_path = (*path, str(key))
            if key in REQUIRED_FALSE_FLAGS and item is not False:
                errors.append(f"{label}: {_format_path(next_path)} must be false")
            if key in REQUIRED_TRUE_FLAGS and item is not True:
                errors.append(f"{label}: {_format_path(next_path)} must be true")
            _walk_flags(item, next_path, errors, label)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_flags(item, (*path, str(index)), errors, label)


def _scan_forbidden_text(value: object, path: tuple[str, ...], errors: list[str], label: str) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            next_path = (*path, key_text)
            if key_text not in ALLOWED_SECRET_KEYS and any(token in key_text.lower() for token in FORBIDDEN_SECRET_KEY_TOKENS):
                errors.append(f"{label}: forbidden secret-bearing key at {_format_path(next_path)}")
            _scan_forbidden_text(item, next_path, errors, label)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _scan_forbidden_text(item, (*path, str(index)), errors, label)
    elif isinstance(value, str):
        if MUTATION_ROUTE_PATTERN.search(value):
            errors.append(f"{label}: mutation route string at {_format_path(path)}")
        if any(pattern.search(value) for pattern in FORBIDDEN_CREDENTIAL_VALUE_PATTERNS):
            errors.append(f"{label}: credential-like value at {_format_path(path)}")


def _require_refs(
    observed: object,
    required: Iterable[str],
    errors: list[str],
    label: str,
    field_name: str,
) -> None:
    observed_set = set(observed) if isinstance(observed, list) else set()
    for required_ref in required:
        if required_ref not in observed_set:
            errors.append(f"{label}: {field_name} missing required ref {required_ref}")


def _check_value(
    example: Mapping[str, Any],
    path: tuple[str, ...],
    expected: object,
    errors: list[str],
    label: str,
) -> None:
    observed = _get_path(example, path)
    if observed != expected:
        errors.append(f"{label}: {_format_path(path)} must be {expected!r}; observed {observed!r}")


def _get_path(value: object, path: tuple[str, ...]) -> object:
    current = value
    for part in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _set_path(payload: dict[str, Any], path: tuple[str, ...], value: object) -> None:
    current: dict[str, Any] = payload
    for part in path[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    current[path[-1]] = value


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{label} missing: {_path_label(path)}")
        return {}
    except json.JSONDecodeError as exc:
        errors.append(f"{label} invalid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{label} must be a JSON object")
        return {}
    return value


def _path_label(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _format_path(path: tuple[str, ...]) -> str:
    return ".".join(path) if path else "<root>"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA)
    parser.add_argument("--example", action="append", type=Path, dest="examples")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    examples = tuple(args.examples) if args.examples else DEFAULT_EXAMPLES
    validation = validate_agentic_service_harness_task_creation_admission_preflight(
        schema_path=args.schema,
        example_paths=examples,
    )
    if args.output:
        write_task_creation_admission_preflight_validation(validation, args.output)
    if args.json:
        print(json.dumps(validation.as_dict(), indent=2, sort_keys=True))
    elif validation.ok:
        print("AGENTIC SERVICE HARNESS TASK CREATION ADMISSION PREFLIGHT VALID")
    else:
        for error in validation.errors:
            print(error, file=sys.stderr)
    return 1 if args.strict and not validation.ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
